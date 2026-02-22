"""H.265/HEVC transcoding client using ffmpeg.

Scans Sonarr/Radarr libraries for files not already encoded in H.265 and
transcodes them in the background, replacing originals on success.

Requires:
  - ffmpeg installed (included in Docker image)
  - Media directories mounted into the Arrmate container at the same paths
    that Sonarr/Radarr report (configure via volume mounts in compose).
"""

import asyncio
import logging
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from ..config.settings import settings

logger = logging.getLogger(__name__)

# Codec strings that Sonarr/Radarr report for H.265/HEVC files (already done)
_H265_CODECS = {"hevc", "x265", "h265", "h.265"}

# In-memory job store  {job_id: job_dict}
_jobs: Dict[str, Dict[str, Any]] = {}


# ── Public job store helpers ───────────────────────────────────────────────────


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Return a job by ID, or None if not found."""
    return _jobs.get(job_id)


def get_all_jobs() -> List[Dict[str, Any]]:
    """Return all jobs, newest first."""
    return sorted(_jobs.values(), key=lambda j: j["created_at"], reverse=True)


def cancel_job(job_id: str) -> bool:
    """Request cancellation of a running job. Returns True if job found."""
    job = _jobs.get(job_id)
    if job and job["status"] in ("pending", "running"):
        job["cancelled"] = True
        return True
    return False


# ── Codec helpers ──────────────────────────────────────────────────────────────


def _already_h265(codec: str) -> bool:
    return codec.strip().lower() in _H265_CODECS


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ── Library scanning ───────────────────────────────────────────────────────────


async def _get_radarr_files(title_filter: Optional[str]) -> List[Dict[str, Any]]:
    """Fetch movie files from Radarr that are not yet H.265."""
    if not settings.radarr_url or not settings.radarr_api_key:
        return []

    base = settings.radarr_url.rstrip("/")
    headers = {"X-Api-Key": settings.radarr_api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{base}/api/v3/movie", headers=headers)
        resp.raise_for_status()
        movies = resp.json()

    results = []
    for movie in movies:
        if title_filter and title_filter.lower() not in movie.get("title", "").lower():
            continue
        mf = movie.get("movieFile")
        if not mf:
            continue
        codec = mf.get("mediaInfo", {}).get("videoCodec", "")
        if codec and _already_h265(codec):
            continue
        path = mf.get("path")
        if path:
            results.append({
                "title": movie.get("title", "Unknown"),
                "path": path,
                "codec": codec or "unknown",
                "media_type": "movie",
                "size": mf.get("size", 0),
            })
    return results


async def _get_sonarr_files(title_filter: Optional[str]) -> List[Dict[str, Any]]:
    """Fetch episode files from Sonarr that are not yet H.265."""
    if not settings.sonarr_url or not settings.sonarr_api_key:
        return []

    base = settings.sonarr_url.rstrip("/")
    headers = {"X-Api-Key": settings.sonarr_api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{base}/api/v3/series", headers=headers)
        resp.raise_for_status()
        all_series = resp.json()

        if title_filter:
            all_series = [s for s in all_series if title_filter.lower() in s.get("title", "").lower()]

        # Cap concurrent episode-file requests to avoid overwhelming Sonarr
        sem = asyncio.Semaphore(5)

        async def fetch_series_files(series: Dict) -> List[Dict]:
            async with sem:
                try:
                    r = await client.get(
                        f"{base}/api/v3/episodefile",
                        params={"seriesId": series["id"]},
                        headers=headers,
                    )
                    r.raise_for_status()
                    items = []
                    for ef in r.json():
                        codec = ef.get("mediaInfo", {}).get("videoCodec", "")
                        if codec and _already_h265(codec):
                            continue
                        path = ef.get("path")
                        if path:
                            items.append({
                                "title": f"{series['title']} — {ef.get('relativePath', path)}",
                                "path": path,
                                "codec": codec or "unknown",
                                "media_type": "tv",
                                "size": ef.get("size", 0),
                            })
                    return items
                except Exception as e:
                    logger.warning("Failed to get files for %s: %s", series.get("title"), e)
                    return []

        batches = await asyncio.gather(*[fetch_series_files(s) for s in all_series])

    return [f for batch in batches for f in batch]


async def scan_for_transcode(
    media_type: str,
    title: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return all library files that need H.265 transcoding.

    Args:
        media_type: 'tv', 'movie', or 'all'
        title: Optional case-insensitive title filter

    Returns:
        List of file dicts: {title, path, codec, media_type, size}
    """
    tasks = []
    if media_type in ("movie", "all"):
        tasks.append(_get_radarr_files(title))
    if media_type in ("tv", "all"):
        tasks.append(_get_sonarr_files(title))

    if not tasks:
        return []

    results = await asyncio.gather(*tasks, return_exceptions=True)
    files = []
    for r in results:
        if isinstance(r, Exception):
            logger.error("Error scanning library: %s", r)
        else:
            files.extend(r)
    return files


# ── ffmpeg execution ───────────────────────────────────────────────────────────


def ffmpeg_available() -> bool:
    """Return True if ffmpeg is installed."""
    return shutil.which("ffmpeg") is not None


def _transcode_sync(file_path: str, crf: int, preset: str) -> tuple[bool, str]:
    """Blocking transcode of one file to H.265.

    Outputs to a .tmp.mkv sibling, then atomically renames over the original.
    Returns (success, error_message).
    """
    src = Path(file_path)
    if not src.exists():
        return False, f"File not found: {file_path}"

    tmp = src.with_suffix(".tmp.mkv")

    try:
        cmd = [
            "ffmpeg", "-i", str(src),
            "-c:v", "libx265",
            "-crf", str(crf),
            "-preset", preset,
            "-c:a", "copy",
            "-c:s", "copy",
            "-tag:v", "hvc1",
            "-y",
            str(tmp),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=14400,  # 4-hour limit per file
        )
        if proc.returncode != 0:
            if tmp.exists():
                tmp.unlink()
            stderr_tail = proc.stderr[-500:] if proc.stderr else "unknown error"
            return False, f"ffmpeg exited {proc.returncode}: {stderr_tail}"

        tmp.replace(src)
        return True, ""

    except subprocess.TimeoutExpired:
        if tmp.exists():
            tmp.unlink()
        return False, "Timed out after 4 hours"
    except Exception as exc:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        return False, str(exc)


# ── Background job runner ──────────────────────────────────────────────────────


async def run_transcode_job(job_id: str, files: List[Dict[str, Any]]) -> None:
    """Background coroutine: processes all files in a transcode job."""
    job = _jobs.get(job_id)
    if not job:
        return

    job["status"] = "running"
    loop = asyncio.get_event_loop()
    crf = settings.transcode_crf
    preset = settings.transcode_preset

    for file_info in files:
        if job.get("cancelled"):
            break

        job["current_file"] = file_info["path"]
        original_size = file_info.get("size", 0)

        try:
            success, error = await loop.run_in_executor(
                None, _transcode_sync, file_info["path"], crf, preset
            )

            if success:
                try:
                    new_size = Path(file_info["path"]).stat().st_size
                except OSError:
                    new_size = 0
                saved = max(0, original_size - new_size)
                job["completed"] += 1
                job["saved_bytes"] += saved
                job["completed_files"].append({
                    "title": file_info["title"],
                    "original_size": _format_bytes(original_size),
                    "new_size": _format_bytes(new_size),
                    "saved": _format_bytes(saved),
                })
            else:
                job["failed"] += 1
                job["errors"].append(f"{file_info['title']}: {error}")

        except Exception as exc:
            job["failed"] += 1
            job["errors"].append(f"{file_info['title']}: {exc}")

    job["current_file"] = None
    job["status"] = "cancelled" if job.get("cancelled") else "completed"
    job["finished_at"] = datetime.now(timezone.utc).isoformat()


# ── Job creation ───────────────────────────────────────────────────────────────


def create_job(
    files: List[Dict[str, Any]],
    media_type: str,
    title: Optional[str] = None,
) -> str:
    """Create a new transcode job entry and return its ID."""
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {
        "id": job_id,
        "status": "pending",
        "media_type": media_type,
        "title": title,
        "total": len(files),
        "completed": 0,
        "failed": 0,
        "saved_bytes": 0,
        "current_file": None,
        "errors": [],
        "completed_files": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "cancelled": False,
    }
    return job_id
