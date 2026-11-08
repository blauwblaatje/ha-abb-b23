"""Config flow for ABB B21/B23/B24 meters."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from modbus_connection import ModbusError, ModbusTimeoutError
import probatio

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SerialPortSelector,
    TextSelector,
)

from .const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_STOPBITS,
    DEFAULT_UNIT_ID,
    DOMAIN,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .meter import AbbMeter, MeterInfo, create_modbus_params

_LOGGER = logging.getLogger(__name__)


def _int_box(minimum: int, maximum: int | None = None) -> probatio.All:
    config = NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=minimum)
    if maximum is not None:
        config["max"] = maximum
    return probatio.All(NumberSelector(config), probatio.Coerce(int))


def _serial_schema(defaults: Mapping[str, Any]) -> probatio.Schema:
    schema: dict[Any, Any] = {}
    # Pre-fill the port of a meter already set up, so adding the next meter on
    # the same bus is just a matter of changing the address.
    if CONF_DEVICE in defaults:
        schema[probatio.Required(CONF_DEVICE, default=defaults[CONF_DEVICE])] = (
            SerialPortSelector()
        )
    else:
        schema[probatio.Required(CONF_DEVICE)] = SerialPortSelector()
    schema.update(
        {
            probatio.Required(
                CONF_BAUDRATE, default=defaults.get(CONF_BAUDRATE, DEFAULT_BAUDRATE)
            ): _int_box(1200, 115200),
            probatio.Required(
                CONF_PARITY, default=defaults.get(CONF_PARITY, DEFAULT_PARITY)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=["N", "E", "O"],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_PARITY,
                )
            ),
            probatio.Required(
                CONF_STOPBITS, default=defaults.get(CONF_STOPBITS, DEFAULT_STOPBITS)
            ): _int_box(1, 2),
            probatio.Required(CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)): _int_box(1, 247),
        }
    )
    return probatio.Schema(schema)


def _tcp_schema(defaults: Mapping[str, Any]) -> probatio.Schema:
    return probatio.Schema(
        {
            probatio.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): TextSelector(),
            probatio.Required(
                CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)
            ): _int_box(1, 65535),
            probatio.Required(CONF_UNIT_ID, default=defaults.get(CONF_UNIT_ID, DEFAULT_UNIT_ID)): _int_box(1, 247),
        }
    )


class _MeterSilentError(Exception):
    """The port opened, but no meter answers at that address."""


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> MeterInfo:
    """Identify the meter behind these settings, or raise."""
    params = create_modbus_params(data)
    async with async_get_temporary_unit(hass, params, int(data[CONF_UNIT_ID])) as unit:
        try:
            return await AbbMeter(unit).async_identify()
        except ModbusTimeoutError as err:
            if unit.connected:
                raise _MeterSilentError from err
            raise


class AbbB23ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add an ABB meter."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask how the meter is reached."""
        return self.async_show_menu(step_id="user", menu_options=[TYPE_SERIAL, TYPE_TCP])

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Meter on an RS-485 port: local adapter or ESPHome serial proxy."""
        return await self._async_step_link(TYPE_SERIAL, user_input)

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Meter behind a Modbus TCP gateway."""
        return await self._async_step_link(TYPE_TCP, user_input)

    def _defaults(self, connection_type: str) -> dict[str, Any]:
        """Settings of the last meter added over this link type, next address up."""
        for entry in reversed(self._async_current_entries(include_ignore=False)):
            if entry.data.get(CONF_TYPE) == connection_type:
                defaults = dict(entry.data)
                defaults[CONF_UNIT_ID] = min(int(defaults[CONF_UNIT_ID]) + 1, 247)
                return defaults
        return {}

    async def _async_step_link(
        self, connection_type: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        defaults = self._defaults(connection_type)
        if user_input is not None:
            data = {CONF_TYPE: connection_type, **user_input}
            defaults = data
            try:
                info = await _async_probe(self.hass, data)
            except _MeterSilentError:
                errors["base"] = "no_response"
            except HomeAssistantError:
                errors["base"] = "device_in_use"
            except (ModbusError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error probing meter")
                errors["base"] = "unknown"
            else:
                link = data.get(CONF_DEVICE) or f"{data[CONF_HOST]}:{data[CONF_PORT]}"
                await self.async_set_unique_id(
                    info.serial_number or f"{link}-{data[CONF_UNIT_ID]}"
                )
                self._abort_if_unique_id_configured(updates=data)
                model = info.model or "B2x"
                return self.async_create_entry(
                    title=f"ABB {model} (address {data[CONF_UNIT_ID]})", data=data
                )

        schema = (
            _serial_schema(defaults)
            if connection_type == TYPE_SERIAL
            else _tcp_schema(defaults)
        )
        return self.async_show_form(
            step_id=connection_type, data_schema=schema, errors=errors
        )
