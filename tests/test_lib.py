"""Tests for the API client (lib/octopus_spain.py)."""

from datetime import datetime, timezone

import pytest

import custom_components.octopus_spain.lib.octopus_spain as mod
from custom_components.octopus_spain.lib.octopus_spain import OctopusApiError, OctopusSpain


class _FakeClient:  # pylint: disable=too-few-public-methods
    """Fake GraphQL client returning a fixed response."""

    def __init__(self, response):
        self._response = response

    async def execute_async(self, query, variables=None):  # pylint: disable=unused-argument
        """Return the canned response, ignoring the query."""
        return self._response


class _SeqClient:  # pylint: disable=too-few-public-methods
    """Fake client returning paginated responses per flow (import/export)."""

    def __init__(self, by_field):
        self._by_field = {k: list(v) for k, v in by_field.items()}

    async def execute_async(self, query, variables=None):  # pylint: disable=unused-argument
        """Return the next page for the flow referenced by the query."""
        field = "importReadings" if "importReadings" in query else "exportReadings"
        return self._by_field[field].pop(0)


def _patch(monkeypatch, response):
    """Patch GraphqlClient with a fake returning a fixed response."""
    monkeypatch.setattr(mod, "GraphqlClient", lambda *a, **k: _FakeClient(response))


def _conn(field, nodes, has_next, end_cursor=None):
    """Build a readings connection response (one page)."""
    return {
        "data": {
            "supplyPoints": {
                "edges": [
                    {
                        "node": {
                            "readings": {
                                field: {
                                    "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor},
                                    "edges": [{"node": n} for n in nodes],
                                }
                            }
                        }
                    }
                ]
            }
        }
    }


def _node(hour, value):
    """Build a single reading node."""
    return {
        "value": value,
        "units": "KILOWATT_HOURS",
        "intervalStart": f"2026-06-28T{hour:02d}:00:00+02:00",
        "intervalEnd": f"2026-06-28T{hour + 1:02d}:00:00+02:00",
    }


_START = datetime(2026, 6, 28, tzinfo=timezone.utc)
_END = datetime(2026, 6, 29, tzinfo=timezone.utc)


async def test_cups_returns_identifiers(monkeypatch):
    """cups() extracts the CUPS identifiers from the account."""
    _patch(monkeypatch, {"data": {"account": {"properties": [{"electricitySupplyPoints": [{"cups": "ES0021000013208057RM"}]}]}}})
    api = OctopusSpain("e", "p")
    api._token = "t"  # pylint: disable=protected-access
    assert await api.cups("A-1") == ["ES0021000013208057RM"]


async def test_readings_paginates_and_concatenates(monkeypatch):
    """readings() follows pageInfo.endCursor and concatenates every page."""
    page1 = _conn("importReadings", [_node(0, "1.0")], True, "c1")
    page2 = _conn("importReadings", [_node(1, "2.0")], False)
    export = _conn("exportReadings", [], False)
    monkeypatch.setattr(mod, "GraphqlClient", lambda *a, **k: _SeqClient({"importReadings": [page1, page2], "exportReadings": [export]}))
    api = OctopusSpain("e", "p")
    api._token = "t"  # pylint: disable=protected-access
    out = await api.readings("A-1", _START, _END)
    assert [r["value"] for r in out["import"]] == [1.0, 2.0]
    assert out["export"] == []


async def test_readings_no_supply_point_returns_empty(monkeypatch):
    """readings() returns empty lists when there is no supply point."""
    _patch(monkeypatch, {"data": {"supplyPoints": {"edges": []}}})
    api = OctopusSpain("e", "p")
    api._token = "t"  # pylint: disable=protected-access
    out = await api.readings("A-1", _START, _END)
    assert out == {"import": [], "export": []}


async def test_readings_raises_on_api_errors(monkeypatch):
    """readings() raises OctopusApiError when the API returns errors (no data)."""
    _patch(monkeypatch, {"errors": [{"message": "Query exceeds maximum allowed node count."}]})
    api = OctopusSpain("e", "p")
    api._token = "t"  # pylint: disable=protected-access
    with pytest.raises(OctopusApiError) as exc:
        await api.readings("A-1", _START, _END)
    assert "node count" in str(exc.value)
