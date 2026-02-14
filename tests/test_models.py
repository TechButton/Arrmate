"""Test core models."""

import pytest

from arrmate.core.models import ActionType, Intent, MediaType


def test_intent_creation():
    """Test creating an Intent object."""
    intent = Intent(
        action=ActionType.REMOVE,
        media_type=MediaType.TV,
        title="Angel",
        season=1,
        episodes=[1, 2],
    )

    assert intent.action == ActionType.REMOVE
    assert intent.media_type == MediaType.TV
    assert intent.title == "Angel"
    assert intent.season == 1
    assert intent.episodes == [1, 2]


def test_intent_without_optional_fields():
    """Test Intent with only required fields."""
    intent = Intent(
        action=ActionType.LIST,
        media_type=MediaType.MOVIE,
    )

    assert intent.action == ActionType.LIST
    assert intent.media_type == MediaType.MOVIE
    assert intent.title is None
    assert intent.season is None
