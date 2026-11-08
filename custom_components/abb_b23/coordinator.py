"""Poll an ABB meter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from modbus_connection import ModbusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_SECONDS
from .meter import AbbMeter, MeterInfo

_LOGGER = logging.getLogger(__name__)


@dataclass
class AbbRuntimeData:
    """What a loaded entry keeps around."""

    coordinator: AbbCoordinator
    info: MeterInfo


type AbbConfigEntry = ConfigEntry[AbbRuntimeData]


class AbbCoordinator(DataUpdateCoordinator[dict[str, float | None]]):
    """Fetch all measurements of one meter."""

    config_entry: AbbConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: AbbConfigEntry, meter: AbbMeter
    ) -> None:
        """Set up the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.meter = meter

    async def _async_update_data(self) -> dict[str, float | None]:
        """Read the meter."""
        try:
            return await self.meter.async_read()
        except (ModbusError, OSError) as err:
            raise UpdateFailed(f"Error reading meter: {err}") from err
