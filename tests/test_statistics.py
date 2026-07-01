"""Tests for the statistics builder (pure logic)."""

from datetime import datetime, timedelta, timezone

from custom_components.octopus_spain.statistics import build_statistics


def _r(hour, value):
    """Build a single hourly reading."""
    start = datetime(2026, 6, 28, hour, 0, tzinfo=timezone.utc)
    return {"start": start, "end": start + timedelta(hours=1), "value": value}


def test_cumulative_sum_from_zero():
    """build_statistics() accumulates the running sum from zero."""
    stats = build_statistics([_r(0, 1.0), _r(1, 2.0), _r(2, 0.5)])
    assert [s["sum"] for s in stats] == [1.0, 3.0, 3.5]
    assert stats[0]["start"].tzinfo is not None


def test_continues_from_start_sum_and_filters_after():
    """build_statistics() continues from start_sum and drops readings <= after."""
    after = datetime(2026, 6, 28, 0, 0, tzinfo=timezone.utc)
    stats = build_statistics([_r(0, 1.0), _r(1, 2.0)], start_sum=10.0, after=after)
    assert len(stats) == 1
    assert stats[0]["sum"] == 12.0
