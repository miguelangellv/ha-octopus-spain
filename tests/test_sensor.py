"""Tests for Octopus Spain sensors."""

from unittest.mock import AsyncMock, patch, MagicMock

from homeassistant.core import HomeAssistant

from custom_components.octopus_spain.sensor import async_setup_entry, OctopusWallet


async def test_async_setup_entry_creates_sensors(hass: HomeAssistant):
    """Test that async_setup_entry creates the expected sensors."""
    # Mock data to be returned by coordinator
    mock_data = {
        "12345": {
            "solar_wallet": 10.0,
            "octopus_credit": 20.0,
            "last_invoice": {"amount": 50.0, "issued": "2026-06-01", "start": "2026-05-01", "end": "2026-05-31"},
            "prices": {
                "peak": 0.1,
                "standard": 0.05,
                "valley": 0.02,
                "peak_with_taxes": 0.12,
                "standard_with_taxes": 0.07,
                "valley_with_taxes": 0.04,
                "surplus": 0.01,
            },
        }
    }

    # Patch OctopusCoordinator to avoid real API calls and return mock data
    with patch("custom_components.octopus_spain.sensor.OctopusCoordinator", autospec=True) as mock_coordinator_class:
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.data = mock_data
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()

        # Mock entry and async_add_entities
        mock_entry = MagicMock()
        mock_entry.data = {"email": "test@test.com", "password": "password"}
        mock_async_add_entities = MagicMock()

        # Call the function
        await async_setup_entry(hass, mock_entry, mock_async_add_entities)

        # Verify that async_add_entities was called
        assert mock_async_add_entities.called
        sensors = mock_async_add_entities.call_args[0][0]

        # We expect sensors for:
        # Wallet, Credit, Invoice, CurrentPrice, Price(peak), Price(standard), Price(valley), Price(surplus)
        # That's 8 sensors
        assert len(sensors) == 8


async def test_wallet_sensor_value():
    """Test the wallet sensor value is correctly updated from the coordinator."""
    mock_data = {
        "12345": {
            "solar_wallet": 10.0,
        }
    }
    mock_coordinator = MagicMock()
    mock_coordinator.data = mock_data

    sensor = OctopusWallet("12345", "solar_wallet", "Solar Wallet", mock_coordinator, True)
    sensor.async_write_ha_state = MagicMock()

    # pylint: disable=protected-access
    sensor._handle_coordinator_update()

    assert sensor.native_value == 10.0
