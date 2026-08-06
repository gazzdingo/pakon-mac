#!/usr/bin/env python3
"""Read the light board's lamp registers. READ ONLY -- no register is written.

Asked after U34's repair, when the obvious next question was "does the lamp
work too?". The answer is not a command away, and this tool exists to gather
the evidence rather than guess.

WHY THE LAMP IS NOT A SIMPLE ON/OFF -- docs/14-lamp-decoded.md, from the binary
------------------------------------------------------------------------------
The F-135 Plus illuminant is a temperature-stabilised LED array behind a
thermal interlock:

  * 0x81 (5 B) LED levels and 0x82 (12 B) duty cycles are PER-UNIT CALIBRATION.
    They are currents into an LED array; inventing them risks overdriving the
    illuminant, which is not recoverable.
  * 0x8B-0x8F are temperature setpoints driving a TEC. Wrong values risk
    thermal damage to the illuminant, also not recoverable.

Every previous lamp attempt in this project wrote only 0xD0/0xD1, never the
setpoint blocks -- so the loop was unconfigured, FN_bLampTemperatureStable
could never be satisfied, and the lamp stayed dark while the board happily
ACKed the enable. That is the documented explanation for the whole pattern.

So this reads and reports. Turning the lamp on needs the unit's calibrated
values recovered first (FN_GetCalibrateInfoLight, or the per-unit calibration
EEPROM at I2C 0x52 which is already backed up under backups/eeprom-i2c/).

REGISTERS READ
--------------
  0x83  1 B   lamp status   (docs/14: 0x00 -> 0x10 once the board acts on an enable)
  0x84  2 B   lamp temperature
  0x80  1 B   enable bitmask (1 visible, 2 IR, 3 both)

The read packet is `01 03 <board> <len> <reg>`, the same type-1 fetch form
picm_read_flash.py uses. Type 1 is a read; nothing here can write.
"""
from __future__ import annotations

import sys

try:
    import usb.core
    import usb.util
except ImportError:
    sys.exit("pyusb is required:  pip install pyusb")

VID, PID = 0x0F05, 0xF135
EP_CMD_OUT, EP_CMD_IN = 0x01, 0x81
LIGHT = 0x40                      # AD_PICL_PLUS, docs/03-protocol.md:116
HOST = 0x10

REGS = [(0x80, 1, "enable bitmask (1=visible 2=IR 3=both)"),
        (0x83, 1, "lamp status"),
        (0x84, 2, "lamp temperature"),
        # The values needed to light the lamp safely. If the board already
        # holds its calibrated values, reading them means nothing has to be
        # invented -- which is the whole blocker. Reads cannot harm anything.
        (0x81, 5, "LED LEVELS      <- per-unit calibration"),
        (0x82, 12, "LED DUTY CYCLES <- per-unit calibration"),
        (0x8B, 2, "temp setpoint 0x8B"),
        (0x8C, 2, "temp setpoint 0x8C"),
        (0x8D, 2, "temp setpoint 0x8D"),
        (0x8E, 2, "temp setpoint 0x8E"),
        (0x8F, 2, "temp setpoint 0x8F")]


def open_scanner():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        sys.exit(f"scanner {VID:#06x}:{PID:#06x} not found -- run "
                 "tools/pakon_load.py first")
    try:
        dev.set_configuration()
    except usb.core.USBError:
        pass
    usb.util.claim_interface(dev, 0)
    for ep in (EP_CMD_OUT, EP_CMD_IN):
        try:
            dev.clear_halt(ep)
        except usb.core.USBError:
            pass
    return dev


def send(dev, pkt, timeout=2000):
    try:
        dev.write(EP_CMD_OUT, pkt, timeout)
        return bytes(dev.read(EP_CMD_IN, 64, timeout))
    except usb.core.USBError:
        return None


def clear_fault(dev):
    for _ in range(8):
        r = send(dev, bytes([0x01, 0x03, HOST, 0x02, 0x03]))
        if isinstance(r, bytes) and len(r) > 3 and not (r[3] & 0x20):
            return True
        send(dev, bytes([0x04, 0x03, HOST, 0x00, 0x85]))
    return False


def read_reg(dev, reg, length):
    pkt = bytes([0x01, 0x03, LIGHT, length, reg])
    resp = send(dev, pkt)
    return pkt, resp


def main() -> int:
    dev = open_scanner()
    print(f"scanner open: {VID:#06x}:{PID:#06x}")
    print(f"light board:  {LIGHT:#04x}  (PICL / U11)\n")
    clear_fault(dev)
    for reg, length, name in REGS:
        pkt, resp = read_reg(dev, reg, length)
        line = f"  {reg:#04x}  {name:<40}"
        if resp is None:
            print(line + "no response")
            continue
        status = resp[3] if len(resp) > 3 else None
        data = resp[4:4 + length] if len(resp) >= 4 + length else b""
        print(f"{line}status={status}  data={data.hex(' ') or '-'}"
              f"   raw={resp.hex(' ')}")
    print("\nread only -- nothing was written. See the module docstring for why "
          "lighting the lamp needs the unit's calibrated values first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
