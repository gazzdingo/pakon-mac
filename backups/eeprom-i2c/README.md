# I2C EEPROM backups — read 2026-08-05, **superseded 2026-08-18**

> **These two files are NOT usable backups.** Run
> `python3 tools/pakon_eeprom_check.py backups/eeprom-i2c/*.bin` — neither
> verifies. Keep them as historical artefacts and as the input that docs/69
> §5.5 was derived from; do not restore from them, and do not treat this
> directory as covering the irreplaceable chip.
>
> Several claims in the original version of this file were wrong. They are
> corrected below rather than deleted, because two of them propagated into
> other files (`tools/pakon_usb_guard.py`'s docstring, among others) and the
> record of where the error came from is worth more than a clean page.

Two chips on the scanner's I2C bus, both on the motherboard.

| File | Device | Status now |
|---|---|---|
| `eeprom_51.bin` | 7-bit 0x51 | FX2 boot personality. 4 distinct byte values, no `C0` signature. Replaceable — correct contents are `c0 05 0f 35 f2 07 aa 04 02` |
| `eeprom_52.bin` | 7-bit 0x52 | **THE PER-UNIT CALIBRATION.** Real data (102 distinct values, serial decodes), but **shifted by one byte** and only 256 of ~2596 bytes |

## What was wrong here

**1. "254/256 bytes populated" / "0x52 is a 256-byte device."** No. docs/69
§5.2: the vendor keeps two copies of two sections, primary A at `0x000` with a
backup at `0x400`, primary B at `0x800` with a backup at `0xA00`, the highest
byte touched being `0xA24` = **2596**. The part is at least 4 Kbit with a
2-byte word address. A 256-byte dump holds under a tenth of it.

**2. "magnification, optical alignment, per-format motor speeds."** Not
supported by anything we have decoded. The verified map (docs/69 §4.1) is the
scanner serial (`u32` at `0x0F` of this file), `NegMatrix0..29` and a truncated
`PosMatrix`; the vendor's own registry copy additionally names `MotorAdjust`,
`MotorAdjustDrag(_Ir)`, `MotorSpeedPlus(_Ir)` and `Offset` per DPI base,
`StepperLens`/`StepperCCD`, and the per-mode lamp calibration. **No
magnification field has been found.** "Optical alignment" was a guess about
`Offset`.

**3. "`FN_bReadEEPromToRegistry` → `fcn.100160a0`, whose wrapper pushes
`wValue 0xA4` = this device."** Two errors, both corrected in docs/69 §5:
`FN_bReadEEPromToRegistry` is `fcn.10016a90`, and **`0xA4` is a `bRequest`,
not a `wValue`** (`0x10016175: push 0xa4`). The `0xA4 ≈ 0x52 << 1` coincidence
is real but incidental. This misreading is what produced the broken read
described next.

**4. The dump is off by one.** `eeprom_52.bin[k] = EEPROM[k+1]`, four
independent anchors in docs/69 §5.5. It is visible in the first three bytes:
the file starts `01 00 00`, and prefixing the byte the read ate — `0x8E` —
gives `0x0000018E` = **398**, exactly section A's length. Cause strongly
indicated as an extra priming read in `fx2/eeprom_dump_bus.c`'s `dump()`.

## The "degradation" story below is now doubtful

The original text is kept verbatim because the observations were real. The
*explanation* probably was not.

> These EEPROMs return good data on the FIRST transaction after a power cycle
> and **degrade on every read after it**. The second read of a power cycle
> already differed in 180 of 256 bytes; by the third, both devices read
> entirely 0xFF. Status stays `ok` throughout — nothing in the protocol
> reveals the data is junk.
>
> A repeated-read hash comparison is therefore WORSE than useless here: it
> converges on stable garbage. A 7-pass run reported "STABLE — backup is
> trustworthy" for 256 bytes of 0xFF.
>
> **Correct protocol: power cycle, ONE read, save, then compare against reads
> taken in OTHER power cycles.** These files are two such first-reads, from
> separate power cycles, byte-identical.

Against this: issue #50 reports reading the same chip **repeatedly** with the
correct `0xA4`-select sequence and getting CRC-valid sections, byte-identical
across two power cycles. "Reads decay to 0xFF" and "a read that never selects
the chip returns bus idle" produce the same observation, and only the second
one has a mechanism. Treat the one-read-per-power-cycle rule as unexplained
folklore until someone re-runs it with the corrected sequence.

**This is unresolved and needs the scanner.** It is not a settled correction.

## Why 0x52 matters

Kodak's F-135 Service Manual (`research/sdk/F135_SM.txt`, p.10):

> "The motherboard has an EEPROM chip built into it to store calibration
> information. The Calibration Wizard program writes all calibration data to
> this EEPROM chip. When the scanner interface software is launched, this
> calibration data in the EEPROM is written to the Windows registry."

It cannot be downloaded, derived, or recreated from any vendor file. Unlike the
PIC bootloader (rebuildable from a 12-byte vector stub), **this data has no
substitute** — which is precisely why a dump that fails validation must not be
filed as a backup.

## Taking a real backup

`tools/eeprom_backup.py` now issues the vendor's two-request sequence and
refuses to save a dump that does not verify. It has **not yet been run against
this project's scanner** — doing so, and replacing these files, is issue #50.
