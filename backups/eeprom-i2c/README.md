# I2C EEPROM backups — VERIFIED 2026-08-05

Two chips on the scanner's I2C bus, both on the motherboard.

| File | Device | Content |
|---|---|---|
| `eeprom_51.bin` | 7-bit 0x51 (8-bit 0xA2) | FX2 boot personality. **Erased** — only 17/256 bytes non-0xFF, and none of them the C0 signature. Replaceable: correct contents are `c0 05 0f 35 f2 07 aa 04 02` |
| `eeprom_52.bin` | 7-bit 0x52 (8-bit 0xA4) | **THE PER-UNIT CALIBRATION.** 254/256 bytes populated. IRREPLACEABLE |

## Why 0x52 matters

Kodak's F-135 Service Manual (`research/sdk/F135_SM.txt`, p.10):

> "The motherboard has an EEPROM chip built into it to store calibration
> information. The Calibration Wizard program writes all calibration data to
> this EEPROM chip. When the scanner interface software is launched, this
> calibration data in the EEPROM is written to the Windows registry."

And p.9, on motor speed: *"as all calibration settings are stored in the EEPROM
of the scanner, on the scanner main board."*

Located independently in `TLB.dll`: `FN_bReadEEPromToRegistry` -> `fcn.100160a0`,
whose wrapper pushes `wValue 0xA4` = this device.

This describes THIS scanner's optics and transport — magnification, optical
alignment, per-format motor speeds. It cannot be downloaded, derived, or
recreated from any vendor file. Unlike the PIC bootloader (which we can rebuild
from a 12-byte vector stub, since the application has zero dependencies on it),
**this data has no substitute.**

## HOW IT WAS VERIFIED — and the trap

These EEPROMs return good data on the FIRST transaction after a power cycle and
**degrade on every read after it**. The second read of a power cycle already
differed in 180 of 256 bytes; by the third, both devices read entirely 0xFF.
Status stays `ok` throughout — nothing in the protocol reveals the data is junk.

A repeated-read hash comparison is therefore WORSE than useless here: it
converges on stable garbage. A 7-pass run reported "STABLE — backup is
trustworthy" for 256 bytes of 0xFF.

**Correct protocol: power cycle, ONE read, save, then compare against reads
taken in OTHER power cycles.** These files are two such first-reads, from
separate power cycles, byte-identical.

Use `tools/eeprom_oneshot.py`. Never `--compare` within one power cycle.
