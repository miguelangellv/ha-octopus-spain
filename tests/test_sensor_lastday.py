"""Test for the last-day consumption sensor."""

from datetime import date
from types import SimpleNamespace

from custom_components.octopus_spain.sensor import OctopusLastDayConsumption


def test_sensor_exposes_kwh_and_date():
    """The sensor exposes the last-day kWh as state and the date as attribute."""
    coord = SimpleNamespace(data={"ES0021000013208057RM": {"last_day_kwh": 10.705, "last_day_date": date(2026, 6, 28)}})
    sensor = OctopusLastDayConsumption("ES0021000013208057RM", coord)

    sensor._handle_coordinator_update_value()  # pylint: disable=protected-access

    assert sensor.native_value == 10.705
    assert sensor.extra_state_attributes["Fecha"] == date(2026, 6, 28)
