"""Base entity for ABB B21/B23/B24 meters."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_UNIT_ID, DOMAIN, MANUFACTURER
from .coordinator import AbbCoordinator


class AbbEntity(CoordinatorEntity[AbbCoordinator]):
    """An entity of one meter."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AbbCoordinator, description: EntityDescription
    ) -> None:
        """Set up the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        info = entry.runtime_data.info
        device_id = str(entry.unique_id)
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            model=info.model,
            sw_version=info.firmware,
            serial_number=info.serial_number,
            name=f"ABB meter {entry.data[CONF_UNIT_ID]}",
        )
