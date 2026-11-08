"""Talk to one ABB B2x meter over a Modbus unit handed out by Home Assistant."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from modbus_connection import (
    ModbusError,
    ModbusExceptionError,
    ModbusSerialParams,
    ModbusTcpParams,
    ModbusUnit,
)

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE

from .const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_PARITY,
    DEFAULT_STOPBITS,
    REQUEST_TIMEOUT_SECONDS,
    TYPE_SERIAL,
)
from .registers import (
    BLOCKS,
    FIRMWARE_ADDRESS,
    FIRMWARE_WORDS,
    SERIAL_NUMBER,
    TYPE_DESIGNATION_ADDRESS,
    TYPE_DESIGNATION_WORDS,
    decode_ascii,
    decode_block,
    decode_raw,
)


def create_modbus_params(
    data: Mapping[str, Any],
) -> ModbusSerialParams | ModbusTcpParams:
    """Build the Modbus link parameters from config entry data.

    Equal parameters share one connection in Home Assistant's ``modbus``
    integration, so every meter on the same RS-485 bus shares the port.
    """
    if data[CONF_TYPE] == TYPE_SERIAL:
        return ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=int(data[CONF_BAUDRATE]),
            parity=data.get(CONF_PARITY, DEFAULT_PARITY),
            stopbits=int(data.get(CONF_STOPBITS, DEFAULT_STOPBITS)),
        )
    return ModbusTcpParams(host=data[CONF_HOST], port=int(data[CONF_PORT]))


@dataclass(frozen=True, kw_only=True)
class MeterInfo:
    """Identity of a meter."""

    serial_number: str | None
    model: str | None
    firmware: str | None


class AbbMeter:
    """An ABB B21/B23/B24 meter behind a Modbus unit."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Wrap a unit; no I/O happens here."""
        self.unit = unit
        unit.require_timeout(REQUEST_TIMEOUT_SECONDS)

    async def async_identify(self) -> MeterInfo:
        """Read serial number, type designation and firmware version."""
        # Timeouts and link errors propagate: they mean "no meter here".
        # An exception *response* means a meter answered but lacks the field.
        try:
            words = await self.unit.read_holding_registers(
                SERIAL_NUMBER.address, SERIAL_NUMBER.words
            )
        except ModbusExceptionError:
            serial = None
        else:
            serial = decode_raw(words, SERIAL_NUMBER.reg_type)
        return MeterInfo(
            serial_number=None if serial is None else str(serial),
            model=await self._async_read_ascii(
                TYPE_DESIGNATION_ADDRESS, TYPE_DESIGNATION_WORDS
            ),
            firmware=await self._async_read_ascii(FIRMWARE_ADDRESS, FIRMWARE_WORDS),
        )

    async def _async_read_ascii(self, address: int, count: int) -> str | None:
        """Read an optional text field; older firmware may not have it."""
        try:
            text = decode_ascii(await self.unit.read_holding_registers(address, count))
        except ModbusError:
            return None
        return text or None

    async def async_read(self) -> dict[str, float | None]:
        """Read all measurements."""
        values: dict[str, float | None] = {}
        for block in BLOCKS:
            words = await self.unit.read_holding_registers(block.address, block.count)
            values.update(decode_block(block, words))
        return values
