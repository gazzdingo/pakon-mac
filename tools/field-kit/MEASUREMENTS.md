# Physical measurements taken by the owner — 2026-08-05

All taken on the actual board with a multimeter, scanner **off and unplugged**.
These are measured facts, not assumptions.

---

## 1. JM11 header — the ICSP connector

**Board silkscreen reads: pin 1 LEFT, pin 5 RIGHT.**

Measured in **resistance mode** (20 kΩ range):

| JM11 pin | Connects to | Measured | Signal |
|---|---|---|---|
| **1** | U11 pin 18 | **0.78 kΩ (780 Ω)** | MCLR / VPP |
| **2** | U11 pin 28 | connected | VDD |
| **3** | chassis ground | connected | VSS |
| **4** | U11 pin 17 | **0.10 kΩ (100 Ω)** | PGD (data) |
| **5** | U11 pin 16 | **0.10 kΩ (100 Ω)** | PGC (clock) |

**Conclusion: standard ICSP header, standard orientation, wire the PICkit
straight through 1→1, 2→2, 3→3, 4→4, 5→5. PICkit pin 6 unconnected.**

### IMPORTANT GOTCHA
Pins 1, 4 and 5 have **series resistors**, so a **continuity / beep test reads
them as OPEN**. That misled us initially — pin 1 appeared unconnected. Use
**resistance mode**, not continuity, if re-checking. Anything showing a number
is connected; only `OL` / `1` / blank means open.

---

## 2. U11 I2C pins — are they electrically on the bus?

Measured from the pin to VDD (U11 pin 28). The I2C bus has pull-up resistors to
VDD, so a connected pin reads the pull-up; a broken trace reads open.

| Measurement | Result | Meaning |
|---|---|---|
| U11 **pin 37** (RC3/SCL) → pin 28 | **5.42 kΩ** | **CONNECTED to the bus** |
| U11 **pin 42** (RC4/SDA) → pin 28 | **1.05 kΩ** | **CONNECTED to the bus** |

**Conclusion: U11's I2C pins physically reach the bus. Traces and solder joints
are intact. The "broken trace / cracked joint" hypothesis is DEAD — which was
the one scenario in which replacing the chip would have fixed nothing.**

(Outstanding: a control measurement on a non-I2C pin, e.g. U11 pin 20 or 21 to
pin 28, which should read `OL`. Not yet taken.)

---

## 3. The diagnostic LED — decoded

Green LED on the motherboard. Decoded from video (frame-by-frame, green channel
isolated) AND confirmed independently by the owner watching it.

**Pattern: `0 1 0 1 0 0`** — six pulses, then a long dark gap, repeating.

| Element | Measured | Firmware value |
|---|---|---|
| short pulse = bit 0 | 235 ms | 200 ms |
| long pulse = bit 1 | 638–705 ms | 600 ms |
| gap between bits | 369–403 ms | 400 ms |
| gap between cycles | 2553–3057 ms | 3000 ms |

Four complete cycles, all identical. Encoding confirmed from firmware
disassembly (`0x2B3E BTFSS` → bit set loads the 600 ms value).

**Caveat: two state machines drive this pin.** Machine A (index RAM `0x1EC`)
shows the real fault code from RAM `0x02A`; machine B (index `0x1FE`, value
`0x1FD`) walks a **hardcoded** 5→6→0 sequence. So part of what is visible is a
constant, not a diagnosis. The fault code is one of {4, 5, 20} and cannot be
resolved from the LED alone — **internal EEPROM index 5 settles it.**

---

## 4. Front panel LEDs (owner observations, over time)

- Initially: **green / orange / orange** (left to right)
- At one point after the fault: **all three red**
- After the vector repair: **green power LED**, board booted on its own

---

## 5. I2C EEPROM contents — read over USB, VERIFIED

Read with custom FX2 firmware. **Verified by agreement between first-reads from
two separate power cycles** (see the read trap below).

| Device | Non-0xFF bytes | SHA-256 (first 16) | Content |
|---|---|---|---|
| 7-bit **0x51** (8-bit 0xA2) | 17 / 256 | `9d384a543af290ec` | FX2 boot personality — **erased** |
| 7-bit **0x52** (8-bit 0xA4) | 254 / 256 | `675cf1cff78a2e0f` | **PER-UNIT CALIBRATION — intact** |

Files: `backups/eeprom-i2c/eeprom_51.bin`, `eeprom_52.bin`

### THE READ TRAP
These EEPROMs return good data on the **FIRST** transaction after a power cycle
and **degrade on every read after it**. The second read of a cycle already
differed in 180/256 bytes; by the third, both read entirely 0xFF — while still
returning status `ok`. A repeated-read hash comparison therefore converges on
**stable garbage** (a 7-pass run reported "STABLE, trustworthy" for 256 bytes of
0xFF). **Power cycle, ONE read, then compare against reads from OTHER power
cycles.**

---

## 6. Hardware identification

| Item | Value | How known |
|---|---|---|
| Board | Scanner motherboard, Pakon **#125040** | F-135 Service Manual FRU list |
| PCB silkscreen | `#125430 REV C` | visible on board |
| U11 | PIC18F452, 44-TQFP, relabelled **`125507A 2208`** | firmware declares `;PIC18F452`; timing constants confirm 39.32 MHz HSPLL |
| U6 | Cypress CY7C68013A-128AXC (FX2) | package marking |
| FPGA | Xilinx Spartan XC3S150E | package marking |
| JM10 | 2×5 FPGA JTAG — **NOT the one to use** | beside the Spartan |
| PICkit 3 | USB `04d8:900a`, serial **`BUR195068601`** | enumerated |

**There is no separate motor board.** Kodak's service manual: *"The scanner
motherboard houses most of the scanner's electronic circuitry. It houses the
motor control, DX, USB communication, and power regulation."*

---

## 7. U11 pin reference (44-TQFP, viewed from above, CCW from the pin-1 dot)

```
                TOP EDGE  (44 -> 34, left to right)
      44   43  [42]  41   40   39   38  [37]  36   35   34
   ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
●1 ┤                                           ├ 33
 2 ┤                                           ├ 32
 3 ┤                                           ├ 31
 4 ┤                                           ├ 30
 5 ┤        PIC18F452 (125507A 2208)           ├[29] VSS
[6]┤  VSS                                      ├[28] VDD
[7]┤  VDD                                      ├ 27
 8 ┤                                           ├ 26
 9 ┤                                           ├ 25
10 ┤                                           ├ 24
11 ┤                                           ├ 23
   └───┬───┬───┬───┬───┬───┬───┬───┬───┬───┬───┘
      12  13  14  15 [16][17][18] 19  20  21  22
                BOTTOM EDGE  (12 -> 22, left to right)
```

| Pin | Signal |
|---|---|
| 16 | PGC (clock) — bottom edge, 5th from left |
| 17 | PGD (data) — bottom edge, 6th from left |
| 18 | MCLR/VPP — bottom edge, 7th from left |
| 6, 29 | VSS (ground) |
| 7, 28 | VDD (power) |
| 37 | RC3 / SCL — top edge, 8th from left |
| 42 | RC4 / SDA — top edge, 3rd from left |

Sanity check for the pin counting: **6↔29 should beep** (both ground) and
**7↔28 should beep** (both power).
