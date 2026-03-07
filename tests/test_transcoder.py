"""Tests for transcoder path validation."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_allowed_roots_empty_skips_validation(tmp_path):
    """When allowed_roots is empty, any path is accepted."""
    from arrmate.clients.transcoder import _transcode_sync_validated

    dummy_file = tmp_path / "movie.mkv"
    dummy_file.touch()

    with patch("arrmate.clients.transcoder._transcode_sync", return_value=(True, "")) as mock_sync:
        success, error = _transcode_sync_validated(str(dummy_file), 28, "medium", [])

    mock_sync.assert_called_once_with(str(dummy_file), 28, "medium")
    assert success is True


def test_allowed_roots_blocks_path_outside_roots(tmp_path):
    """When allowed_roots is set, a file outside those roots is rejected."""
    from arrmate.clients.transcoder import _transcode_sync_validated

    allowed_dir = tmp_path / "media"
    allowed_dir.mkdir()
    forbidden_file = tmp_path / "other" / "movie.mkv"
    forbidden_file.parent.mkdir()
    forbidden_file.touch()

    with patch("arrmate.clients.transcoder._transcode_sync") as mock_sync:
        success, error = _transcode_sync_validated(
            str(forbidden_file), 28, "medium", [str(allowed_dir)]
        )

    mock_sync.assert_not_called()
    assert success is False
    assert "allowed" in error.lower() or "not within" in error.lower()


def test_allowed_roots_permits_path_inside_roots(tmp_path):
    """When allowed_roots is set, a file inside those roots is permitted."""
    from arrmate.clients.transcoder import _transcode_sync_validated

    media_dir = tmp_path / "media"
    media_dir.mkdir()
    ok_file = media_dir / "movie.mkv"
    ok_file.touch()

    with patch("arrmate.clients.transcoder._transcode_sync", return_value=(True, "")) as mock_sync:
        success, error = _transcode_sync_validated(
            str(ok_file), 28, "medium", [str(media_dir)]
        )

    mock_sync.assert_called_once()
    assert success is True


def test_allowed_roots_blocks_path_traversal(tmp_path):
    """Path traversal attempts (../../etc) are blocked when allowed_roots is set."""
    from arrmate.clients.transcoder import _transcode_sync_validated

    allowed_dir = tmp_path / "media"
    allowed_dir.mkdir()
    # Construct a path that traverses out of the allowed directory
    traversal_path = str(allowed_dir) + "/../../etc/passwd"

    with patch("arrmate.clients.transcoder._transcode_sync") as mock_sync:
        success, error = _transcode_sync_validated(
            traversal_path, 28, "medium", [str(allowed_dir)]
        )

    mock_sync.assert_not_called()
    assert success is False
