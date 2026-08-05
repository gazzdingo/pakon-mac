# LED fault-code decode — 2026-08-04

Source video: `~/Downloads/PXL_20260803_155551949.mp4` (41.5 s, 29.77 fps, 512x288).
Green LED located at pixel (266, 94); isolated as `green - max(red, blue)` because
the board is brightly lit and greyscale washes the LED out.
Signal saved as `led_green_signal.npy`.

## MEASUREMENT (this is fact)

Four complete cycles, delimited by ~3000 ms dark gaps, all IDENTICAL:

| Cycle start | Pulses |
|---|---|
| 12.87 s | 0 1 0 1 0 0 |
| 20.12 s | 0 1 0 1 0 0 |
| 27.41 s | 0 1 0 1 0 0 |
| 34.70 s | 0 1 0 1 0 0 |

Timings: short pulse 235 ms, long pulse 638-705 ms, inter-bit gap 369-403 ms,
cycle gap 2553-3057 ms. These match the firmware-derived encoding exactly
(600 ms = 1, 200 ms = 0, 400 ms gap, 3000 ms repeat).

**Six pulses per cycle**, with uniform gaps between all six.

## FIRMWARE (also fact)

State machine B at `0x002B14`:

```
0x2B14  MOVF  0x1FD,W        load the fault code
0x2B16  ANDLW 0x0F           <-- masked to the LOW NIBBLE: 4 bits
0x2B18  XORLW 0x00
0x2B1A  BZ    0x002BA4       zero -> LED solid on
0x2B2C  MOVFF 0x0FD -> 0x000 copy to scratch
0x2B30  MOVF  0x0FE,W        bit index -> counter 0x001
0x2B36  BCF   STATUS,C
0x2B38  RRNCF 0x000          rotate right by index
0x2B3A  DECFSZ 0x001
0x2B3E  BTFSS 0x000,0        test bit 0
0x2B42  bit SET   -> load 600 ms (0x0EF/0x0F0)
0x2B4C  bit CLEAR -> load 200 ms (0x0F1/0x0F2)
```

Index initialised to **3** at `0x002AEC`/`0x002AEE`, decremented at `0x002B06`,
reloaded to 3 when it reaches 0 (`0x002AE8` `MOVF 0xEC,W` / `BNZ`).

So the firmware says: **4 bits, MSB first, low nibble only.**

## THE UNRESOLVED CONFLICT

Firmware says 4 bits. Video says 6 pulses. Both measurements are solid and they
disagree. Do NOT pick one silently.

Candidate readings:

| Reading | Bits | Value |
|---|---|---|
| First four pulses are the nibble | `0101` | **5** |
| Last four pulses are the nibble | `0100` | **4** |
| All six are meaningful | `010100` | **20** (0x14) |

Possible explanations not yet tested:
* There are TWO state machines driving RA4 (`0x002A86` and `0x002B14`). The
  second may contribute pulses the first does not, so the visible train may be
  two concatenated fields rather than one nibble.
* RAM `0x1FD` (machine B's source) may not be RAM `0x02A` (the fault code loaded
  from EEPROM index 5). The link between them is assumed, not traced.
* The cycle boundary may not be where the ~3000 ms gap falls.

## HOW TO SETTLE IT

Read **internal EEPROM index 5** over ICSP. That byte IS the persisted fault
code (`0x0019EC MOVFF 0x001 -> 0x02A`). Its low nibble must match whichever
reading is correct, which resolves the conflict outright.

Until then the fault code is one of {4, 5, 20} and no further inference should
be built on it.
