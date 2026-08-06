# 33 — Component map: what everything is and what it is for

One page to orient anyone picking this up. Hardware, vendor software, firmware
images, our tools, and captured data — named, explained, and cross-referenced.

---

## 1. HARDWARE

### Boards

| Board | Kodak FRU | Contains |
|---|---|---|
| **Motherboard** | **#125040** (PCB silkscreen `#125430 REV C`) | Everything below. Kodak: *"houses the motor control, DX, USB communication, and power regulation"* |
| CCD board | #125038 | The sensor. CCD chip itself is #123528 |
| Light assembly | #125031 | LED array + optics. **No processor** — driven from the motherboard |
| Lens | #125166 | |
| TE cooler | #125159 | Sensor cooling |
| Film transport | #125055 | |
| DX sensor | #125154 | Reads film edge codes |

### Chips on the motherboard

| Ref | Part | Marked | Role | I2C |
|---|---|---|---|---|
| **U11** | PIC18F452 | `125507A 2208` | **PICL** — light control, LED drivers, TEC, DX sensors | app `0x40`, boot `0x42` |
| **U34** | PIC18F452 | `125506A 2208` | **PICM** — motor control, transport, filter wheel, rail monitoring | app `0x44`, boot `0x46` |
| U6 | Cypress CY7C68013A | | **FX2** — USB 2.0 bridge, I2C bus master | host addr `0x10` |
| U18 | Xilinx **XC3S150E** | | FPGA — sensor pipeline. **Role not fully understood** | — |
| U9 | MT46V16M16 | | SDRAM — scan buffer | — |
| U21–U29 | **A6275ELWT** ×6 | | 8-bit serial LED drivers — the illuminator | — |
| U15, U17 | LP3966ES | | Voltage regulators | — |
| — | 24Cxx | | **FX2 boot EEPROM** — USB personality | `0xA2` (7-bit `0x51`) |
| — | 24Cxx | | **CALIBRATION EEPROM** — per-unit data | `0xA4` (7-bit `0x52`) |

### Headers

| Ref | What | Use |
|---|---|---|
| `JM11` | 5-pin ICSP | **U34 (PICM)** programming |
| (other) | 5-pin ICSP | **U11 (PICL)** programming |
| `JM10` | 2×5 JTAG | **Xilinx FPGA. NOT for the PICs** |

### I2C address map (8-bit form, as used in packets)

```
0x10  AD_HOST            the FX2 itself, answered internally, never on the wire
0x20/0x22   AD_PICL / AD_BOOT_PICL          non-Plus models
0x24/0x26   AD_PICM / AD_BOOT_PICM          non-Plus models
0x28        unknown
0x40/0x42   AD_PICL_PLUS / AD_BOOT_PICL_PLUS   <-- U11 on this machine
0x44/0x46   AD_PICM_PLUS / AD_BOOT_PICM_PLUS   <-- U34 on this machine
0xA2/0xA4   the two EEPROMs
```
Corroborated independently by ktkaufman03's reverse engineering.

---

## 2. FIRMWARE IMAGES — which prefix goes where

From `Config/Firmware/ReadmeF135.txt`. Format is `XXhhvv.HEX` where `hh` is the
**hardware** version and `vv` the **firmware** version.

| Prefix | Board | Notes |
|---|---|---|
| `PL` | PICL | non-Plus |
| `PM` | PICM | non-Plus |
| **`NL`** | **PICL PLUS** | `NL05vv` = PCB #125430C |
| **`NM`** | **PICM PLUS** | `NM05vv` = PCB #125430C |
| `AP`, `DX`, `DY`, `LP`, `LQ`, `MC`, `MD`, `CD`, `CE` | other boards / F-235 / F-335 family | |

**This machine uses `nm0506.HEX` (PICM) and `nl050A.HEX` (PICL).**
`hh=05` means PCB #125430**C**. Do not use `hh` values below 05 on this board.

Layout differs between the two:
* PICL app base `0x0340`, so its boot block is `0x0000`–`0x033F`
* PICM app base `0x0400`, so its boot block is `0x0000`–`0x03FF`

**No vendor file contains a bootloader.** The PIC16 images that include
`0x0000` are older pre-bootloader standalone builds.

FX2 firmware: `Pakon5/7/8.hex`, `PknInit.hex` — host-loaded into RAM at every
connect, never resident.

---

## 3. VENDOR SOFTWARE STACK

```
  PSI  /  TLXClientDemo  /  PTS            <- applications
            |
          TLX                              <- façade, COM server
            |
   TLA  /  TLB  /  TLC                     <- per-model client libraries
            |                                 TLB = F-135
   F135usb2.sys / F235Ldr.sys / F235Lib.sys   <- Windows kernel drivers
            |
          USB  ->  FX2  ->  I2C  ->  PICs
```

| Component | What it is |
|---|---|
| **PSI** | "Pakon Scanning Interface" — the minilab operator application |
| **PTS** | "Pakon Troubleshooter" — field diagnostics. .NET. Replaced older tools (`Scanner Cure`, `Setup1300`, `mfctest`) |
| **TLXClientDemo** | Sample app shipped with the SDK. Used by hobbyists for options PSI hides |
| **TLX** | COM server, the documented public API |
| **TLB.dll** | The F-135 client library. **Where packets are actually built** |
| `PakonIMAu.dll` | Imaging — the colour pipeline lives here |
| `F235Ldr.sys` | Firmware loader, derived from Anchor Chips "ezloader" |

**Documented API**: `research/sdk/f235-com-ref.pdf` (Pakon #124580 Rev I, ~150pp)
and `f235-com-guide.pdf` (#124579). Interfaces `ITLAMain`, `IScanPictures`,
`ISavePictures`. **Not yet read properly — highest-value unread material.**

Also shipped: **`TLAs.dll`, a scanner-less simulator.** Potentially very useful
for testing a port with no hardware.

---

## 4. THE WIRE PROTOCOL

```
byte 0  packet type   0x01 read, 0x02 write, 0x04 command
byte 1  length        wire size = len + 2
byte 2  board address
byte 3  data length   (status byte in a response)
byte 4  register / command
byte 5+ data
```

Status in `resp[3]`: `0`/`8` accepted, `1` no-ACK, `2` format, `3` checksum,
`9` bus error.

**Register reads are TWO packets:**
```
01 03 <board> <n> <reg>     request
01 03 <board> <n> 07        fetch — payload at response offset 4
```
**DANGER:** that `07` is one bit from `0x0B` (write 16 bytes) and `0x0F`
(erase a row).

**Bootloader commands:** `1` read 16 bytes, `2` write 16 bytes, `4` erase a
64-byte row, `8` finalise and run. App-valid gate = internal EEPROM index 0
== `0xAA`.

---

## 5. OUR TOOLS

| Tool | Purpose |
|---|---|
| `tools/pakon_load.py` | Download FX2 firmware, bring the scanner up |
| `tools/eeprom_oneshot.py` | **Read both I2C EEPROMs. ONE read per power cycle** (see read trap) |
| `tools/icsp_read_all.py` | ICSP read via `ipecmd`, 5 passes, per-region SHA-256, trust gates |
| `tools/flash_diff.py` | Diff a flash read against `nm0506`, withholds verdict on a bad read |
| `tools/pakon_color.py` | **The colour pipeline. Verified exact** |
| `tools/mclr_window.py` | Catch a bootloader reset window. **Never run** |
| `tools/i2c_raw_scan.py` + `fx2/i2c_scan.c` | Raw 128-address I2C scan via custom FX2 firmware |
| `fx2/eeprom_dump_all.c` | FX2 firmware to dump both EEPROMs |
| `build/build_picm_image.py` | **Build the replacement-chip image** |
| `tools/WRITES_LOCKED` | Interlock — blocks 11 tools that can write. **Leave in place** |

---

## 6. CAPTURED DATA

| File | What | Status |
|---|---|---|
| `backups/u11-picl/u11-full-{A,B,C}.hex` | U11 full device — **contains the only known Kodak PIC18 bootloader** | 3 reads identical |
| `backups/eeprom-i2c/eeprom_52.bin` | **Per-unit calibration. Irreplaceable** | 2 power cycles, identical |
| `backups/eeprom-i2c/eeprom_51.bin` | FX2 boot personality — erased, contents known | |
| `build/picm-staged.hex` | Replacement image, stays in bootloader | under review |
| `build/picm-run.hex` | Replacement image, runs the app | under review |
| `research/sdk/` | Service manuals, COM SDK docs, 171MB software ISO | |
| `analysis/led_decode.md` | The diagnostic LED decoded | |

---

## 7. DATA FLOW — and where the gaps are

```
film -> lamp (A6275 drivers <- PICL) -> optics -> CCD (#123528)
     -> A/D  (gain/offset regs 0x84 idx 2-7)
     -> FPGA XC3S150E   ** WHAT DOES IT DO? deskew? binning? packing? **
     -> FX2 -> USB EP 0x86   ** HOW ARE LINES/FRAMES DELIMITED? **
     -> host: assembly -> calibration -> colour pipeline -> TIFF/JPEG
                             ** HOW IS CALIBRATION APPLIED? **

control: host -> USB -> FX2 -> I2C -> PICL (light) / PICM (motors)
     ** WHAT IS THE SCAN SEQUENCE? **
```

**Four unknowns, all in acquisition.** All four would be answered by capturing
one real scan from the vendor software against a working scanner — which is
why the macOS port is blocked on the repair.

Everything else — firmware load, protocol, register access, EEPROM, colour —
already works natively on Apple Silicon.
