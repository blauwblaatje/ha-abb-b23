# ABB B21/B23/B24 energy meter for Home Assistant

Reads ABB B21, B23 and B24 kWh meters over Modbus RTU, using Home Assistant's
shared Modbus connections (HA 2026.11+). One config entry per meter; meters on
the same RS-485 bus share one connection automatically.

The bus can be reached through:

- an **ESPHome serial proxy** (e.g. a LilyGO T-CAN485 with a `serial_proxy:`
  entry, `port_type: RS485`, on its RS-485 UART),
- a local USB-RS-485 adapter, or
- a Modbus TCP gateway.

## Install

Marketplace (HACS) → ⋮ → *Custom repositories* → add this repository as an
*Integration*, install, restart Home Assistant.

## Set up

*Settings → Devices & services → Add integration → ABB B21/B23/B24 energy meter*

1. Pick **Serial port**, then the port listed under *Serial proxies*.
2. Baud rate / parity / stop bits must match the meter (factory: 19200, even, 1).
3. Enter the meter's Modbus address. Repeat for each meter; the form
   pre-fills the port and the next address.

## Sensors

Voltages (L-N, and L-L disabled by default), currents, active/reactive/apparent
power (total and per phase), frequency, power factor, and the total energy
accumulators (import / export / net, full 64-bit). Quantities the meter variant
does not measure (it reports an "invalid" value, e.g. reactive power on a
B23 112-100) are not created.
