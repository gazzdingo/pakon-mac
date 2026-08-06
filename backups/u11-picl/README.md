# U11 (PICL) full device read — 2026-08-06

Read over ICSP with a PICkit 3. **Three passes, byte-identical**
(sha256 `d21a2c2d722b3079...`). Read only; nothing was programmed or erased.

## Why this matters enormously

It contains a **real Kodak PIC18 bootloader at 0x0000-0x03FF** — 800 non-0xFF
bytes. Until today we believed no copy of a PIC18 bootloader existed anywhere:
348 vendor HEX files were parsed and every single one starts at 0x400.

This is PICL's bootloader (answers I2C 0x42). PICM's answers at 0x46. Kodak
almost certainly used one design for both PICs on this board, differing in the
slave-address constant. **That makes a replacement PICM viable with a genuine
Kodak bootloader rather than the 12-byte stub we had planned.**

```
0x0000  GOTO 0x00001c     reset -> bootloader body
0x0008  GOTO 0x000348     high-priority ISR
0x0018  GOTO 0x003d00     low-priority ISR, forwarded into the application
```

## It also settles which chip is which

The application region matches **nl050A.HEX at 100.0% (26458/26458 bytes)** —
PICL PLUS firmware, hardware 05 = PCB #125430C, version 0A.

* **U11 = PICL** — light control, I2C 0x40, healthy, reads perfectly
* **U34 = PICM** — motor control, I2C 0x44, silent on I2C AND silent on ICSP

U34 is the failed chip. That is now evidence, not inference: same programmer,
same cables, same method, one chip answers and the other does not.

## Contents

| Region | Notes |
|---|---|
| `0x0000-0x03FF` | **Bootloader.** 800 non-0xFF bytes |
| `0x0400-0x7FFF` | Application = nl050A, 100% match |
| `0x300000-0x30000D` | Config: `00 26 06 09 00 01 81 00 0f c0 0f e0 0f 40` |
| `0xF00000+` | Internal EEPROM, 256 B. **Index 0 = 0xAA**, the app-valid gate |

Note CONFIG2H here is `0x09`, where nm0506 (PICM) specifies `0x0D` — different
watchdog postscale between the two chips.

## Provenance

Device reported: `PIC18F452`, Revision ID 7. Read via `ipecmd -P18F452 -TPPK3
-OD -GF`, MPLAB X v5.50, PICkit 3 serial BUR195068601, firmware suite
01.56.09. Wired through the 5-pin ICSP header beside U11, straight through.
