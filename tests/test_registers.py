"""Tests for the register decoding (no Home Assistant needed)."""

import importlib.util
from pathlib import Path
import sys

import pytest

# Load registers.py directly so the package __init__ (which needs HA) is skipped.
_PATH = Path(__file__).parents[1] / "custom_components" / "abb_b23" / "registers.py"
_spec = importlib.util.spec_from_file_location("abb_registers", _PATH)
reg = importlib.util.module_from_spec(_spec)
sys.modules["abb_registers"] = reg
_spec.loader.exec_module(reg)


def _put(words: list[int], block, address: int, value: int, n: int) -> None:
    off = address - block.address
    for i in range(n):
        words[off + i] = (value >> (16 * (n - 1 - i))) & 0xFFFF


def test_instantaneous_block() -> None:
    block = reg.INSTANTANEOUS
    words = [0] * block.count
    _put(words, block, 0x5B00, 2316, 2)  # 231.6 V
    _put(words, block, 0x5B0E, 8, 2)  # 0.08 A
    _put(words, block, 0x5B12, 0xFFFF_FFFF, 2)  # neutral current unsupported
    _put(words, block, 0x5B18, 1051, 2)  # 10.51 W
    _put(words, block, 0x5B1A, (-250) & 0xFFFF_FFFF, 2)  # -2.5 W
    _put(words, block, 0x5B1C, 0x7FFF_FFFF, 2)  # reactive unsupported
    _put(words, block, 0x5B2C, 4999, 1)  # 49.99 Hz
    _put(words, block, 0x5B2D, 0x7FF9, 1)  # phase angle, must not leak into Hz
    _put(words, block, 0x5B3C, (-1) & 0xFFFF, 1)  # PF -0.001
    _put(words, block, 0x5B3A, 0x7FFF, 1)  # PF invalid

    values = reg.decode_block(block, words)

    assert values["voltage_l1_n"] == pytest.approx(231.6)
    assert values["current_l2"] == pytest.approx(0.08)
    assert values["current_n"] is None
    assert values["active_power_l2"] == pytest.approx(10.51)
    assert values["active_power_l3"] == pytest.approx(-2.5)
    assert values["reactive_power"] is None
    assert values["frequency"] == pytest.approx(49.99)
    assert values["power_factor_l2"] == pytest.approx(-0.001)
    assert values["power_factor"] is None


def test_energy_block_uses_full_64_bits() -> None:
    block = reg.ENERGY
    words = [0] * block.count
    _put(words, block, 0x5000, 87099 + (1 << 32), 4)  # beyond 32 bits
    _put(words, block, 0x5004, 0xFFFF_FFFF_FFFF_FFFF, 4)
    _put(words, block, 0x5008, (-500) & 0xFFFF_FFFF_FFFF_FFFF, 4)

    values = reg.decode_block(block, words)

    assert values["active_energy_import"] == pytest.approx((87099 + (1 << 32)) / 100)
    assert values["active_energy_export"] is None
    assert values["active_energy_net"] == pytest.approx(-5.0)


def test_blocks_cover_every_register() -> None:
    covered = set()
    for block in reg.BLOCKS:
        covered |= set(reg.decode_block(block, [0] * block.count))
    assert covered == set(reg.REGISTERS_BY_KEY)
    for r in reg.REGISTERS:
        block = next(b for b in reg.BLOCKS if b.address <= r.address < b.address + b.count)
        assert r.address + r.words <= block.address + block.count, r.key


def test_decode_ascii() -> None:
    words = [int.from_bytes(b"B2", "big"), int.from_bytes(b"3 ", "big"),
             int.from_bytes(b"11", "big"), int.from_bytes(b"2-", "big"),
             int.from_bytes(b"10", "big"), int.from_bytes(b"0\x00", "big")]
    assert reg.decode_ascii(words) == "B23 112-100"
