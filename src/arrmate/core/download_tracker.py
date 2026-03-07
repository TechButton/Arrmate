"""Background download tracker — polls Sonarr/Radarr and notifies users.

When a user submits a media request, this tracker periodically checks
Sonarr/Radarr for:

  1. Queue presence  → "Your download has started" (notified_queued)
  2. History import  → "Ready in your library!"  (notified_imported)

Each notification fires exactly once per request.  The tracker only looks
at requests that are still open (status != 'rejected', notified_imported=0).

Polling interval: POLL_INTERVAL seconds (default 5 minutes).
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

POLL_INTERVAL = 300  # 5 minutes


async def run_tracker() -> None:
    """Long-running asyncio task — call once from app startup."""
    logger.info("Download tracker started (polling every %ds)", POLL_INTERVAL)
    while True:
        try:
            await _poll_once()
        except Exception:
            logger.exception("Download tracker unexpected error")
        await asyncio.sleep(POLL_INTERVAL)


async def _poll_once() -> None:
    from ..auth.user_db import get_trackable_requests
    from ..config.settings import settings

    requests = get_trackable_requests()
    if not requests:
        return

    # Build a quick lookup: lowercased title → list of request dicts
    by_title: dict[str, list[dict]] = {}
    for req in requests:
        key = req["title"].lower().strip()
        by_title.setdefault(key, []).append(req)

    if settings.sonarr_url and settings.sonarr_api_key:
        await _check_service("sonarr", by_title, settings)

    if settings.radarr_url and settings.radarr_api_key:
        await _check_service("radarr", by_title, settings)


async def _check_service(service: str, by_title: dict, settings_obj) -> None:
    """Check one service's queue and history, firing notifications as needed."""
    try:
        if service == "sonarr":
            from ..clients.sonarr import SonarrClient
            client = SonarrClient(settings_obj.sonarr_url, settings_obj.sonarr_api_key)
        else:
            from ..clients.radarr import RadarrClient
            client = RadarrClient(settings_obj.radarr_url, settings_obj.radarr_api_key)

        try:
            queue_data = await client.get_queue(page_size=100)
            history_data = await client.get_history(page_size=50)
        finally:
            await client.close()

    except Exception as e:
        logger.warning("Download tracker: %s unreachable — %s", service, e)
        return

    # ── Queue check (downloading) ──────────────────────────────────────────
    for record in queue_data.get("records", []):
        title = _extract_title(record, service)
        if not title:
            continue
        for req in by_title.get(title.lower().strip(), []):
            if not req.get("notified_queued"):
                _fire_queued_notification(req, title, settings_obj)

    # ── History check (imported) ───────────────────────────────────────────
    for record in history_data.get("records", []):
        if record.get("eventType") != "downloadFolderImported":
            continue
        title = _extract_title(record, service)
        if not title:
            continue
        for req in by_title.get(title.lower().strip(), []):
            if not req.get("notified_imported"):
                _fire_imported_notification(req, title, settings_obj)
                # Mark in-memory so we don't double-notify in the same poll
                req["notified_imported"] = True


def _extract_title(record: dict, service: str) -> str:
    """Pull the series/movie title out of a Sonarr or Radarr API record."""
    if service == "sonarr":
        return (record.get("series") or {}).get("title") or ""
    else:
        return (record.get("movie") or {}).get("title") or ""


def _fire_queued_notification(req: dict, title: str, settings_obj) -> None:
    """Send 'download started' notification and mark request as queued."""
    from ..auth.user_db import mark_request_queued, create_notification
    from ..auth.notifications import send_slack, send_discord

    if not mark_request_queued(req["id"]):
        return  # Another process already marked it

    message = f"⬇️ '{title}' has started downloading."
    notif_title = "Download Started"

    create_notification(req["requested_by"], message, type="info", request_id=req["id"])

    slack_url = getattr(settings_obj, "slack_webhook_url", None)
    discord_url = getattr(settings_obj, "discord_webhook_url", None)
    if slack_url:
        send_slack(slack_url, message, title=notif_title, color="#0ea5e9")
    if discord_url:
        send_discord(discord_url, message, title=notif_title)

    logger.info("Queued notification sent for request %s (%s)", req["id"], title)


def _fire_imported_notification(req: dict, title: str, settings_obj) -> None:
    """Send 'ready in library' notification and close the request."""
    from ..auth.user_db import mark_request_imported, create_notification
    from ..auth.notifications import send_slack, send_discord

    if not mark_request_imported(req["id"]):
        return  # Another process already marked it

    message = f"🎉 '{title}' is now available in your library!"
    notif_title = "Media Ready"

    create_notification(req["requested_by"], message, type="success", request_id=req["id"])

    slack_url = getattr(settings_obj, "slack_webhook_url", None)
    discord_url = getattr(settings_obj, "discord_webhook_url", None)
    if slack_url:
        send_slack(slack_url, message, title=notif_title, color="#22c55e")
    if discord_url:
        send_discord(discord_url, message, title=notif_title, color=0x22C55E)

    logger.info("Imported notification sent for request %s (%s)", req["id"], title)
