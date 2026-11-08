"""ABB B21/B23/B24 energy meters over Home Assistant's shared Modbus connections."""

from __future__ import annotations

from modbus_connection import ModbusError

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_UNIT_ID
from .coordinator import AbbConfigEntry, AbbCoordinator, AbbRuntimeData
from .meter import AbbMeter, create_modbus_params

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AbbConfigEntry) -> bool:
    """Set up one meter."""
    unit = async_get_unit(
        hass, entry, create_modbus_params(entry.data), int(entry.data[CONF_UNIT_ID])
    )
    meter = AbbMeter(unit)
    try:
        info = await meter.async_identify()
    except (ModbusError, OSError) as err:
        raise ConfigEntryNotReady(f"Meter not reachable: {err}") from err

    coordinator = AbbCoordinator(hass, entry, meter)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = AbbRuntimeData(coordinator=coordinator, info=info)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AbbConfigEntry) -> bool:
    """Unload a meter; the shared connection closes behind the last user."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
