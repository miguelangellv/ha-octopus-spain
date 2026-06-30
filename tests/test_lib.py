"""Tests del cliente API (lib/octopus_spain.py)."""

from datetime import datetime, timezone

import custom_components.octopus_spain.lib.octopus_spain as mod
from custom_components.octopus_spain.lib.octopus_spain import OctopusSpain


class _FakeClient:
    """Cliente GraphQL simulado que devuelve una respuesta fija."""

    def __init__(self, response):
        self._response = response

    async def execute_async(self, query, variables=None):
        return self._response


def _patch(monkeypatch, response):
    monkeypatch.setattr(mod, "GraphqlClient", lambda *a, **k: _FakeClient(response))


async def test_cups_extrae_identificadores(monkeypatch):
    _patch(monkeypatch, {"data": {"account": {"properties": [
        {"electricitySupplyPoints": [{"cups": "ES0021000013208057RM"}]}
    ]}}})
    api = OctopusSpain("e", "p")
    api._token = "t"
    assert await api.cups("A-1") == ["ES0021000013208057RM"]


async def test_readings_parsea_import_y_export_vacio(monkeypatch):
    resp = {"data": {"supplyPoints": {"edges": [{"node": {"readings": {
        "importReadings": {"edges": [
            {"node": {"value": "5.356", "units": "KILOWATT_HOURS",
                      "intervalStart": "2026-06-28T01:00:00+02:00",
                      "intervalEnd": "2026-06-28T02:00:00+02:00"}}]},
        "exportReadings": {"edges": []},
    }}}]}}}
    _patch(monkeypatch, resp)
    api = OctopusSpain("e", "p")
    api._token = "t"
    out = await api.readings("A-1", datetime(2026, 6, 28, tzinfo=timezone.utc),
                             datetime(2026, 6, 29, tzinfo=timezone.utc))
    assert out["export"] == []
    assert len(out["import"]) == 1
    assert out["import"][0]["value"] == 5.356
    assert out["import"][0]["start"].hour == 1


async def test_readings_sin_punto_devuelve_vacio(monkeypatch):
    _patch(monkeypatch, {"data": {"supplyPoints": {"edges": []}}})
    api = OctopusSpain("e", "p")
    api._token = "t"
    out = await api.readings("A-1", datetime(2026, 6, 28, tzinfo=timezone.utc),
                             datetime(2026, 6, 29, tzinfo=timezone.utc))
    assert out == {"import": [], "export": []}
