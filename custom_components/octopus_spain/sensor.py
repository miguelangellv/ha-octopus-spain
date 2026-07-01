"""Sensor platform for Octopus Spain."""

import logging
from datetime import timedelta
from typing import Mapping, Any

import homeassistant.util.dt as dt_util
from tariff_td import Tariff20TD
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity

from homeassistant.const import (
    CURRENCY_EURO,
)

from homeassistant.components.sensor import SensorEntityDescription, SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_PASSWORD, CONF_EMAIL, UPDATE_INTERVAL, PERIOD_PEAK_WITH_TAXES, PERIOD_STANDARD_WITH_TAXES, PERIOD_VALLEY_WITH_TAXES
from .coordinator import EnergyCoordinator
from .lib.octopus_spain import OctopusSpain

_LOGGER = logging.getLogger(__name__)

PRICE_PER_KWH = "€/kWh"
PERIOD_KEY = {"P1": "peak", "P2": "standard", "P3": "valley"}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup sensor platform."""

    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    sensors = []
    coordinator = OctopusCoordinator(hass, email, password)
    await coordinator.async_config_entry_first_refresh()

    accounts = coordinator.data.keys()
    single = len(accounts) == 1
    for account in accounts:
        sensors.append(OctopusWallet(account, "solar_wallet", "Solar Wallet", coordinator, single))
        sensors.append(OctopusWallet(account, "octopus_credit", "Octopus Credit", coordinator, single))
        sensors.append(OctopusInvoice(account, coordinator, single))
        if coordinator.data[account].get("prices"):
            sensors.append(OctopusCurrentPrice(account, coordinator, single))
            sensors.append(OctopusPrice(account, "peak", "Precio Punta", coordinator, single))
            sensors.append(OctopusPrice(account, "standard", "Precio Llano", coordinator, single))
            sensors.append(OctopusPrice(account, "valley", "Precio Valle", coordinator, single))
            sensors.append(OctopusPrice(account, "surplus", "Precio Excedente", coordinator, single))

    # Non-blocking refresh: if energy fails, the balance sensors still load and
    # the coordinator retries on its interval (it does not break the integration).
    energy = EnergyCoordinator(hass, email, password)
    await energy.async_refresh()
    for cups in energy.data or {}:
        sensors.append(OctopusLastDayConsumption(cups, energy))

    async_add_entities(sensors)


class OctopusCoordinator(DataUpdateCoordinator):
    """Coordinator for Octopus Spain data."""

    def __init__(self, hass: HomeAssistant, email: str, password: str):
        super().__init__(hass=hass, logger=_LOGGER, name="Octopus Spain", update_interval=timedelta(hours=UPDATE_INTERVAL))
        self._api = OctopusSpain(email, password)
        self._data = {}

    async def _async_update_data(self):
        if await self._api.login():
            self._data = {}
            accounts = await self._api.accounts()
            for account in accounts:
                self._data[account] = await self._api.account(account)

        return self._data


class OctopusWallet(CoordinatorEntity, SensorEntity):
    """Representation of an Octopus Wallet."""

    def __init__(self, account: str, key: str, name: str, coordinator, single: bool):
        super().__init__(coordinator=coordinator)
        self._state = None
        self._key = key
        self._account = account
        self._attrs: Mapping[str, Any] = {}
        self._attr_name = f"{name}" if single else f"{name} ({account})"
        self._attr_unique_id = f"{key}_{account}"
        self.entity_description = SensorEntityDescription(
            key=f"{key}_{account}",
            icon="mdi:piggy-bank-outline",
            native_unit_of_measurement=CURRENCY_EURO,
            state_class=SensorStateClass.MEASUREMENT,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self.coordinator.data[self._account][self._key]
        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        return self._state


class OctopusInvoice(CoordinatorEntity, SensorEntity):
    """Representation of an Octopus Invoice."""

    def __init__(self, account: str, coordinator, single: bool):
        super().__init__(coordinator=coordinator)
        self._state = None
        self._account = account
        self._attrs: Mapping[str, Any] = {}
        self._attr_name = "Última Factura Octopus" if single else f"Última Factura Octopus ({account})"
        self._attr_unique_id = f"last_invoice_{account}"
        self.entity_description = SensorEntityDescription(
            key=f"last_invoice_{account}",
            icon="mdi:currency-eur",
            native_unit_of_measurement=CURRENCY_EURO,
            state_class=SensorStateClass.MEASUREMENT,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data[self._account]["last_invoice"]
        self._state = data["amount"]
        self._attrs = {"Inicio": data["start"], "Fin": data["end"], "Emitida": data["issued"]}
        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        return self._state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return self._attrs


class OctopusPrice(CoordinatorEntity, SensorEntity):
    """Representation of an Octopus Price."""

    def __init__(self, account: str, key: str, name: str, coordinator, single: bool):
        super().__init__(coordinator=coordinator)
        self._state = None
        self._key = key
        self._account = account
        self._attrs: Mapping[str, Any] = {}
        self._attr_name = f"{name}" if single else f"{name} ({account})"
        self._attr_unique_id = f"{key}_price_{account}"
        self.entity_description = SensorEntityDescription(
            key=f"{key}_price_{account}",
            icon="mdi:transmission-tower-export" if key == "surplus" else "mdi:transmission-tower",
            native_unit_of_measurement=PRICE_PER_KWH,
            state_class=SensorStateClass.MEASUREMENT,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        prices = self.coordinator.data[self._account].get("prices") or {}
        if self._key == "surplus":
            self._state = prices.get("surplus")
        else:
            self._state = prices.get(f"{self._key}_with_taxes")
            self._attrs = {"without_taxes": prices.get(self._key)}
        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        return self._state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return self._attrs


class OctopusLastDayConsumption(CoordinatorEntity, SensorEntity):
    """Consumption (kWh) of the last day available from the API."""

    def __init__(self, cups: str, coordinator):
        super().__init__(coordinator=coordinator)
        self._cups = cups
        self._state = None
        self._attrs: Mapping[str, Any] = {}
        self._attr_name = "Consumo Último Día"
        self._attr_unique_id = f"last_day_consumption_{cups}"
        self.entity_description = SensorEntityDescription(
            key=f"last_day_consumption_{cups}",
            icon="mdi:transmission-tower-import",
            native_unit_of_measurement="kWh",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update_value()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._handle_coordinator_update_value()
        self.async_write_ha_state()

    def _handle_coordinator_update_value(self) -> None:
        data = (self.coordinator.data or {}).get(self._cups) or {}
        self._state = data.get("last_day_kwh")
        self._attrs = {"Fecha": data.get("last_day_date")}

    @property
    def native_value(self) -> StateType:
        return self._state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return self._attrs


class OctopusCurrentPrice(CoordinatorEntity, SensorEntity):
    """Representation of an Octopus Current Price."""

    def __init__(self, account: str, coordinator, single: bool):
        super().__init__(coordinator=coordinator)
        self._state = None
        self._account = account
        self._attrs: Mapping[str, Any] = {}
        self._attr_name = "Precio Actual" if single else f"Precio Actual ({account})"
        self._attr_unique_id = f"current_price_{account}"
        self.entity_description = SensorEntityDescription(
            key=f"current_price_{account}",
            icon="mdi:transmission-tower-import",
            native_unit_of_measurement=PRICE_PER_KWH,
            state_class=SensorStateClass.MEASUREMENT,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_track_time_change(self.hass, self._tick, minute=0, second=10))
        self._update()

    @callback
    def _tick(self, _) -> None:
        self._update()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update()

    def _update(self) -> None:
        prices = self.coordinator.data[self._account].get("prices") or {}
        tariff = Tariff20TD(
            p1=prices.get(PERIOD_PEAK_WITH_TAXES),
            p2=prices.get(PERIOD_STANDARD_WITH_TAXES),
            p3=prices.get(PERIOD_VALLEY_WITH_TAXES),
        )
        now = dt_util.now()
        period = tariff.get_period(now)
        self._state = tariff.get_price(now)
        self._attrs = {"period": period, "without_taxes": prices.get(PERIOD_KEY.get(period))}
        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        return self._state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return self._attrs
