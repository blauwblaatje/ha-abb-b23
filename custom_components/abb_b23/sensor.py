"""Sensors for ABB B21/B23/B24 meters."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_UNIT_ID, DOMAIN, MANUFACTURER
from .coordinator import AbbConfigEntry, AbbCoordinator


@dataclass(frozen=True, kw_only=True)
class AbbSensorDescription(SensorEntityDescription):
    """Describes one meter quantity.

    ``support_key`` names the register whose validity on the first read
    decides whether the meter variant measures this quantity at all; meters
    without e.g. reactive measurement report the invalid sentinel there.
    ``None`` means the sensor is always created.
    """

    support_key: str | None = None


def _voltage(key: str, enabled: bool = True) -> AbbSensorDescription:
    return AbbSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        entity_registry_enabled_default=enabled,
    )


def _current(key: str, support_key: str | None = None) -> AbbSensorDescription:
    return AbbSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        support_key=support_key,
    )


def _power(
    key: str, device_class: SensorDeviceClass, unit: str, support_key: str | None
) -> AbbSensorDescription:
    return AbbSensorDescription(
        key=key,
        translation_key=key,
        device_class=device_class,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=unit,
        suggested_display_precision=1,
        support_key=support_key,
    )


def _energy(
    key: str,
    device_class: SensorDeviceClass,
    unit: str,
    state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING,
) -> AbbSensorDescription:
    return AbbSensorDescription(
        key=key,
        translation_key=key,
        device_class=device_class,
        state_class=state_class,
        native_unit_of_measurement=unit,
        suggested_display_precision=2,
        support_key=key,
    )


def _power_factor(key: str) -> AbbSensorDescription:
    return AbbSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    )


_ACTIVE = (SensorDeviceClass.POWER, UnitOfPower.WATT)
_REACTIVE = (SensorDeviceClass.REACTIVE_POWER, UnitOfReactivePower.VOLT_AMPERE_REACTIVE)
_APPARENT = (SensorDeviceClass.APPARENT_POWER, UnitOfApparentPower.VOLT_AMPERE)

SENSORS: tuple[AbbSensorDescription, ...] = (
    _voltage("voltage_l1_n"),
    _voltage("voltage_l2_n"),
    _voltage("voltage_l3_n"),
    _voltage("voltage_l1_l2", enabled=False),
    _voltage("voltage_l3_l2", enabled=False),
    _voltage("voltage_l1_l3", enabled=False),
    _current("current_l1"),
    _current("current_l2"),
    _current("current_l3"),
    _current("current_n", support_key="current_n"),
    *(
        _power(f"active_power{suffix}", *_ACTIVE, support_key=None)
        for suffix in ("", "_l1", "_l2", "_l3")
    ),
    *(
        _power(f"reactive_power{suffix}", *_REACTIVE, support_key="reactive_power")
        for suffix in ("", "_l1", "_l2", "_l3")
    ),
    *(
        _power(f"apparent_power{suffix}", *_APPARENT, support_key="apparent_power")
        for suffix in ("", "_l1", "_l2", "_l3")
    ),
    AbbSensorDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
    ),
    _power_factor("power_factor"),
    _power_factor("power_factor_l1"),
    _power_factor("power_factor_l2"),
    _power_factor("power_factor_l3"),
    _energy("active_energy_import", SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),
    _energy("active_energy_export", SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR),
    _energy(
        "active_energy_net",
        SensorDeviceClass.ENERGY,
        UnitOfEnergy.KILO_WATT_HOUR,
        SensorStateClass.TOTAL,
    ),
    _energy(
        "reactive_energy_import",
        SensorDeviceClass.REACTIVE_ENERGY,
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
    ),
    _energy(
        "reactive_energy_export",
        SensorDeviceClass.REACTIVE_ENERGY,
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
    ),
    _energy(
        "reactive_energy_net",
        SensorDeviceClass.REACTIVE_ENERGY,
        UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
        SensorStateClass.TOTAL,
    ),
    # HA has no apparent-energy device class; keep the unit, drop the class.
    _energy("apparent_energy_import", None, "kVAh"),  # type: ignore[arg-type]
    _energy("apparent_energy_export", None, "kVAh"),  # type: ignore[arg-type]
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AbbConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors this meter variant supports."""
    coordinator = entry.runtime_data.coordinator
    first = coordinator.data or {}
    async_add_entities(
        AbbSensor(coordinator, description)
        for description in SENSORS
        if description.support_key is None
        or first.get(description.support_key) is not None
    )


class AbbSensor(CoordinatorEntity[AbbCoordinator], SensorEntity):
    """One measured quantity."""

    _attr_has_entity_name = True
    entity_description: AbbSensorDescription

    def __init__(
        self, coordinator: AbbCoordinator, description: AbbSensorDescription
    ) -> None:
        """Set up the sensor."""
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

    @property
    def native_value(self) -> float | None:
        """Return the latest reading; ``None`` while the meter reports it invalid."""
        return self.coordinator.data.get(self.entity_description.key)
