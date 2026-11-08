"""ABB B21/B23/B24 register map and decoding.

Kept free of Home Assistant imports so it can be tested on its own.

Source: ABB "B21/B23/B24 user manual", chapter "Communication with Modbus".
All values are big-endian (high word first). Quantities a meter variant does
not measure read back as an "invalid" sentinel (all ones for unsigned,
max-positive for signed), which is decoded to ``None`` here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RegType(StrEnum):
    """Register encodings used by the meter."""

    U16 = "u16"
    S16 = "s16"
    U32 = "u32"
    S32 = "s32"
    U64 = "u64"
    S64 = "s64"


_WORDS = {
    RegType.U16: 1,
    RegType.S16: 1,
    RegType.U32: 2,
    RegType.S32: 2,
    RegType.U64: 4,
    RegType.S64: 4,
}

_INVALID = {
    RegType.U16: 0xFFFF,
    RegType.S16: 0x7FFF,
    RegType.U32: 0xFFFF_FFFF,
    RegType.S32: 0x7FFF_FFFF,
    RegType.U64: 0xFFFF_FFFF_FFFF_FFFF,
    RegType.S64: 0x7FFF_FFFF_FFFF_FFFF,
}


@dataclass(frozen=True, kw_only=True)
class Register:
    """One quantity in the meter's register map."""

    key: str
    address: int
    reg_type: RegType
    scale: float

    @property
    def words(self) -> int:
        """Number of 16-bit registers this quantity occupies."""
        return _WORDS[self.reg_type]


@dataclass(frozen=True, kw_only=True)
class Block:
    """A contiguous range read with one Modbus request."""

    address: int
    count: int


# Instantaneous values: one read of 0x5B00..0x5B3D.
INSTANTANEOUS = Block(address=0x5B00, count=0x3E)
# Total energy accumulators: one read of 0x5000..0x501F.
ENERGY = Block(address=0x5000, count=0x20)
BLOCKS = (INSTANTANEOUS, ENERGY)

# Identification, read once at setup.
SERIAL_NUMBER = Register(key="serial", address=0x8900, reg_type=RegType.U32, scale=1)
TYPE_DESIGNATION_ADDRESS = 0x8960
TYPE_DESIGNATION_WORDS = 6
FIRMWARE_ADDRESS = 0x8908
FIRMWARE_WORDS = 8


def _r(key: str, address: int, reg_type: RegType, scale: float) -> Register:
    return Register(key=key, address=address, reg_type=reg_type, scale=scale)


U32, S32, U16, S16, U64, S64 = (
    RegType.U32,
    RegType.S32,
    RegType.U16,
    RegType.S16,
    RegType.U64,
    RegType.S64,
)

REGISTERS: tuple[Register, ...] = (
    # Voltages, 0.1 V
    _r("voltage_l1_n", 0x5B00, U32, 0.1),
    _r("voltage_l2_n", 0x5B02, U32, 0.1),
    _r("voltage_l3_n", 0x5B04, U32, 0.1),
    _r("voltage_l1_l2", 0x5B06, U32, 0.1),
    _r("voltage_l3_l2", 0x5B08, U32, 0.1),
    _r("voltage_l1_l3", 0x5B0A, U32, 0.1),
    # Currents, 0.01 A
    _r("current_l1", 0x5B0C, U32, 0.01),
    _r("current_l2", 0x5B0E, U32, 0.01),
    _r("current_l3", 0x5B10, U32, 0.01),
    _r("current_n", 0x5B12, U32, 0.01),
    # Active power, 0.01 W
    _r("active_power", 0x5B14, S32, 0.01),
    _r("active_power_l1", 0x5B16, S32, 0.01),
    _r("active_power_l2", 0x5B18, S32, 0.01),
    _r("active_power_l3", 0x5B1A, S32, 0.01),
    # Reactive power, 0.01 var
    _r("reactive_power", 0x5B1C, S32, 0.01),
    _r("reactive_power_l1", 0x5B1E, S32, 0.01),
    _r("reactive_power_l2", 0x5B20, S32, 0.01),
    _r("reactive_power_l3", 0x5B22, S32, 0.01),
    # Apparent power, 0.01 VA
    _r("apparent_power", 0x5B24, S32, 0.01),
    _r("apparent_power_l1", 0x5B26, S32, 0.01),
    _r("apparent_power_l2", 0x5B28, S32, 0.01),
    _r("apparent_power_l3", 0x5B2A, S32, 0.01),
    # Frequency, 0.01 Hz
    _r("frequency", 0x5B2C, U16, 0.01),
    # Power factor, 0.001
    _r("power_factor", 0x5B3A, S16, 0.001),
    _r("power_factor_l1", 0x5B3B, S16, 0.001),
    _r("power_factor_l2", 0x5B3C, S16, 0.001),
    _r("power_factor_l3", 0x5B3D, S16, 0.001),
    # Total energy accumulators, 0.01 kWh / kvarh / kVAh
    _r("active_energy_import", 0x5000, U64, 0.01),
    _r("active_energy_export", 0x5004, U64, 0.01),
    _r("active_energy_net", 0x5008, S64, 0.01),
    _r("reactive_energy_import", 0x500C, U64, 0.01),
    _r("reactive_energy_export", 0x5010, U64, 0.01),
    _r("reactive_energy_net", 0x5014, S64, 0.01),
    _r("apparent_energy_import", 0x5018, U64, 0.01),
    _r("apparent_energy_export", 0x501C, U64, 0.01),
)

REGISTERS_BY_KEY = {reg.key: reg for reg in REGISTERS}


def decode_raw(words: list[int], reg_type: RegType) -> int | None:
    """Combine big-endian words into an integer; ``None`` for the invalid sentinel."""
    raw = 0
    for word in words:
        raw = (raw << 16) | (word & 0xFFFF)
    if raw == _INVALID[reg_type]:
        return None
    if reg_type in (RegType.S16, RegType.S32, RegType.S64):
        bits = 16 * len(words)
        if raw >= 1 << (bits - 1):
            raw -= 1 << bits
    return raw


def decode_block(block: Block, words: list[int]) -> dict[str, float | None]:
    """Decode every register that lies inside ``block`` from its raw words."""
    if len(words) != block.count:
        raise ValueError(f"expected {block.count} registers, got {len(words)}")
    values: dict[str, float | None] = {}
    end = block.address + block.count
    for reg in REGISTERS:
        if not block.address <= reg.address < end:
            continue
        offset = reg.address - block.address
        raw = decode_raw(words[offset : offset + reg.words], reg.reg_type)
        values[reg.key] = None if raw is None else raw * reg.scale
    return values


def decode_ascii(words: list[int]) -> str:
    """Decode an ASCII string register range, dropping padding."""
    data = b"".join(word.to_bytes(2, "big") for word in words)
    return data.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
