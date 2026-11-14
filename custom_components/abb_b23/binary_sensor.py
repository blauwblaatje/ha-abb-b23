"""Binary sensors for ABB B21/B23/B24 meters."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AbbConfigEntry
from .entity import AbbEntity

# The manual documents the flag registers but not the meaning of each bit, so
# the sensor only says "the meter reports a problem" and shows the raw words.
_PROBLEM_FLAGS = ("error_flags", "alarm_flags")
_ALL_FLAGS = ("error_flags", "warning_flags", "alarm_flags", "information_flags")

PROBLEM = BinarySensorEntityDescription(
    key="problem",
    translation_key="problem",
    device_class=BinarySensorDeviceClass.PROBLEM,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AbbConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the problem sensor if the meter reports its flags."""
    first = entry.runtime_data.coordinator.data or {}
    if any(first.get(key) is not None for key in _PROBLEM_FLAGS):
        async_add_entities([AbbProblemSensor(entry.runtime_data.coordinator, PROBLEM)])


class AbbProblemSensor(AbbEntity, BinarySensorEntity):
    """On while the meter has error or alarm flags set."""

    @property
    def is_on(self) -> bool | None:
        """Return whether any error or alarm flag is set."""
        flags = [self.coordinator.data.get(key) for key in _PROBLEM_FLAGS]
        if all(value is None for value in flags):
            return None
        return any(value for value in flags)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Show the raw flag words, for comparing with ABB support or the manual."""
        return {
            key: None if (value := self.coordinator.data.get(key)) is None
            else f"0x{int(value):016X}"
            for key in _ALL_FLAGS
        }
