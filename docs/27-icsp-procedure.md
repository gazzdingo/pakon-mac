# ICSP procedure — PICkit 3 on U11

Written 2026-08-04, the day before the programmer arrives. Follow in order.
Revised 2026-08-05 (safety review): five reads instead of three, automated
per-region verification, and the write interlock below.

**The governing rule: read everything before writing anything.** No copy of the
PICM bootloader (`0x0000`–`0x03FF`) exists anywhere. 348 HEX files across every
vendor install tree were parsed; every PICM image starts at `0x400`. If a write
clobbers it, it is gone permanently and this scanner is unrecoverable in a way
it currently is not.

## 0a. The write interlock — engaged

`tools/WRITES_LOCKED` exists. While it does, every tool with a write, erase,
program, mode-switch, or blind-sweep path refuses to start (`flash_picm.py`,
`eeprom_repair.py`, `picm_run_app.py --run/--enter`, `pakon_cmd.py`,
`find_light_path.py`, `find_acquire.py`, `probe_sensor_path.py`,
`init_ccd.py`, `start_acquire.py`, `lamp_on.py`, `test_extcode.py`). The
compiled raw-I2C writer was quarantined
(`tools/i2c_eeprom.hex.DANGEROUS-WRITES`). Do not delete the lock file until
its checklist is satisfied. Even after that, the flash/EEPROM writers demand a
typed phrase at a TTY before touching non-volatile state — a wrong flag or a
script can never reach a write on its own.

Note also: `ipecmd` run **by hand** is outside these guards. During the read
session, only ever run it through `icsp_read_all.py`, which refuses the
`-E`/`-F`/`-M`/`-U`/`-S`/`-Z` programming flags outright.

## 0b. Before ICSP: read the EXTERNAL EEPROMs five times

The I²C serial EEPROMs (7-bit `0x50`–`0x57`) do not need the programmer at
all, and one of them — the **PCS/calibration EEPROM, believed to be the device
at 0x52** — holds per-unit magnification / optical-alignment / motor-speed
data that is exactly as irreplaceable as the bootloader (see the inventory in
§8). Before the PICkit is even unboxed:

```
for i in 1 2 3 4 5; do
  ./eeprom_backup.py --out ~/pakon-eeprom-backup-run$i --length 512
done
```

then compare the five runs per device (`md5 ~/pakon-eeprom-backup-run*/ *.bin`).
`--length 512` matters: the decoded calibration payload is 398 + 36 bytes,
which does not fit in the old 256-byte default. `eeprom_backup.py` is
read-only (vendor request `0xA9` with the vendor's own parameters) and warns
if every address returns identical bytes (i.e. the read is not addressing).

---

## 0. Before it arrives — do this tonight

**PICkit 3 support was dropped from recent MPLAB X.** The tool was moved to
legacy status and later removed. Recent MPLAB X (v6.x) may refuse to see it at
all.

* Download an **older MPLAB X IPE** (v5.50 or similar vintage) *before* you need
  it. Verify the exact last-supporting version — do not take v5.50 on trust.
* Confirm **PIC18F452** appears in that version's device list.
* macOS may gatekeeper-block an old unsigned installer; sort that tonight too.

Command-line route (preferable — repeatable and scriptable):
`ipecmd.sh` / `ipecmd.jar`, shipped inside the MPLAB X install. Worth locating
in advance. Note `pk2cmd` is **PICkit 2** and will not drive a PICkit 3.

### Apple Silicon status (checked 2026-08-04)

Machine is **macOS 26.5.2, arm64, Rosetta 2 present and working**. No Microchip
software installed yet.

Old MPLAB X is an Intel build, so Rosetta carries it — that hurdle is cleared.
The remaining unknown is whether a ~2021-era Intel Java app and its USB layer
behave on macOS 26. **Testable tonight without the programmer:** install, launch,
confirm PIC18F452 is in the device list, locate `ipecmd`. Only the USB handshake
with the PICkit itself needs the hardware present.

### If MPLAB X won't cooperate

1. **x86 Linux or Windows machine** — most reliable fallback.
2. **UTM VM, x86 Linux, USB passthrough** — emulated and slow, but works.
3. **PICkit 4** — natively supported by current MPLAB X on Apple Silicon,
   removes both the version and the architecture risk.

> **Do NOT buy an MPLAB SNAP as a cheap backup.** SNAP cannot do high-voltage
> programming, and `CONFIG4L = 0x81` means **LVP is disabled** on this chip
> (bit 2 clear). It requires VPP on MCLR. A SNAP would be dead money. PICkit 3
> and PICkit 4 both do HV programming.

---

## 1. Wiring

**Target chip: U11** — the 44-pin TQFP marked `125507A 2208` (Kodak relabelled
it; it does not say PIC18F452). Beside JM11, with its own crystal.

| Signal | U11 pin |
|---|---|
| MCLR/VPP | 18 |
| PGC | 16 |
| PGD | 17 |
| VDD | 7, 28 |
| VSS | 6, 29 |

**JM11 is the 5-pin header beside U11.** Standard ICSP order is
MCLR / VDD / VSS / PGD / PGC. Only `JM11 pin 1 → U11 pin 18` is assumed, and it
is **unverified** — confirm the full mapping with a meter before connecting, or
connect to the U11 pins directly.

> `JM10` is the 2×5 FPGA JTAG header for the Xilinx Spartan. **Not that one.**

### Power

Power the board from **its own supply**, not the PICkit. The PICkit 3 sources
~30 mA; the board draws far more, and browning it out mid-read is exactly the
kind of accident to avoid. Let the PICkit sense VDD rather than provide it.

Do **not** have the scanner enumerated over USB or any tool from `tools/`
running during ICSP. One master at a time.

---

## 2. First contact — read the device ID

Read the device ID at `0x3FFFFE` before anything else. It confirms ICSP works
and touches nothing. If this fails, stop and fix wiring — do not escalate.

## 3. Verify the read chain against known values

Read the config words. **We already know what they should be**, from
`nm0506.HEX`, so this proves the whole read chain is trustworthy before we rely
on it:

| Word | Expected |
|---|---|
| CONFIG4L | `0x81` |
| CONFIG5L | `0x0f` |
| CONFIG5H | `0xc0` |
| CONFIG6H | `0xe0` |

Nothing is code-protected, so reads are unrestricted. If these match, believe
subsequent reads. If they don't, believe nothing and debug.

## 4. Read and save — FIVE full-device reads, verified

Run `./icsp_read_all.py --execute`. It performs, in order: device ID, config
words to screen, bootloader to screen, then **five** independent full-device
reads (`-GF`), each containing every region:

| Region | Size | Why |
|---|---|---|
| `0x0000`–`0x03FF` bootloader | 1 KB | **Irreplaceable — no copy exists** |
| Full flash `0x0000`–`0x7FFF` | 32 KB | Complete picture |
| Config words `0x300000`–`0x30000D` | 14 B | Trust gate + WDT/BOR truth |
| Internal EEPROM | 256 B | See index map below |
| User IDs `0x200000`–`0x200007` | 8 B | For completeness (optional) |

It then parses all five files and compares them **per region, by SHA-256**
(whole-file MD5/SHA-256 are also printed for the record), checks the config
words against the values known from `nm0506.HEX`, checks the bootloader is
not a single repeated byte (five identical reads of a stuck line still
match each other), and **exits non-zero with an explicit DO-NOT-WRITE message
on any disagreement**, naming which read and which region differ. The
comparison logic itself is provable without hardware:
`./icsp_read_all.py --self-test` (7 cases, all must PASS), and saved reads can
be re-verified any time with `./icsp_read_all.py --verify <dir>`.

**Internal EEPROM index map** (recovered from the boot path — read these, they
are diagnostic):

| Index | Meaning |
|---|---|
| 0 | Bootloader "application valid" gate. Should be `0xAA` |
| 2 | Gates the fault-code clear on the warm path (`0x0019AC`) |
| 4 | → RAM `0x135`/`0x138`. The suspected stray `0x0D` |
| **5** | **The persisted fault code** (`0x0019EC` → RAM `0x02A`). **Should match the nibble read off the LED.** |
| 6 | → RAM `0x027` (`0x0019FA`) |

All five land in `~/pakon-icsp-backup-<date>/` with their checksums printed.
**Do not proceed unless the tool says all five reads agree** — then copy the
directory somewhere off this machine, twice.

---

## 4b. Read the device ID and RECORD it

Before anything else, read `0x3FFFFE`/`0x3FFFFF` and write the value down. If it
is not a PIC18F452, every downstream assumption changes — including the
merged-image rule. The firmware analysis is consistent with a 452, but the
device ID is the only actual proof.

## 5. The diff that might end this without any test firmware

Compare the full flash read against `nm0506.HEX`.

Only four points have ever been verified: `0x400`–`0x47F` (repaired),
`0x800`, `0x1000`, `0x2000`. **The other ~29 KB has never been read.** If there
is corruption anywhere in it, this diff finds it — and that would be the fault,
found, with nothing written.

Vendor image:
`/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/Config/Firmware/nm0506.HEX`

**Two 20-byte windows to check FIRST** — if either differs from `nm0506.HEX`,
that is the fault, found, with nothing written:

* `0x001A8C`–`0x001A96` — `MOVLW 0x36` → SSPCON1, and `MOVFF 0x134` → SSPADD.
  If the `0x36` literal loses bit 5 it becomes `0x16`: **SSPEN = 0**, the module
  is disabled, and RC3/RC4 revert to plain inputs. Nothing would ACK at any
  address — exactly what we observe.
* `0x002C62`–`0x002C6C` — the `0x44` address literal. Note `0x44 → 0x40` (one
  bit) would put the PICM at 7-bit `0x20`, **colliding with the light board and
  invisible to an address scan** — the one gap in our 128-address sweep.

Also check EEPROM index 4 for `0x0D` — the reconstructed stray write.
`probe_sensor_path.py:115` restores "default gain 13", and 13 is `0x0D`, so a
match corroborates that reconstruction exactly.

---

## 6. Only then: the pin test

If the flash is clean, the fault is electrical or in the MSSP peripheral. Flash
a small test program (backups now exist, so this is recoverable):

**Test A — is the pin connected to the bus?**
Hold SDA (RC4) low. Ask the host to talk to the light board at `0x40`.
* Light board **stops** answering → U11's pin reaches the bus; copper is fine.
* Light board **keeps** answering → open stub; U11 isn't on the bus at all.

**Test B — is it the pins or the peripheral?**
Bit-bang a full I²C master transaction from U11 to the light board, bypassing
MSSP entirely.
* Works → pins are fine, **the MSSP peripheral is dead**.
* Fails → the pins themselves are dead.

That distinction decides everything downstream. If only the MSSP is dead, a
firmware fix — reimplementing the I²C slave as bit-bang — becomes possible
without touching hardware. Speculative, and the slave side is timing-sensitive,
but it is a real road and it only exists if Test B is run.

### THE WATCHDOG IS ENABLED IN HARDWARE

`CONFIG2H = 0x0D` at `0x300003` → **WDTEN = 1**, postscaler 1:64, ≈1.15 s typical.
It **cannot be disabled in software** on this part.

So `BRA $` — an infinite loop — will be reset by the watchdog roughly once a
second, forever. A pin-hold test written that way reads as a *flicker*, not a
static level, and would be misread as "the pin does nothing".

**Every test program must `CLRWDT` inside its loop.** Alternatively reprogram
CONFIG2H — but then you must remember to restore it, and that is one more thing
to get wrong.

`CONFIG2L = 0x06` → BOR enabled at 4.2 V, PWRT enabled. A sagging PIC supply
therefore produces a reset loop, not a steady blink — which, combined with the
clock being verified correct from the blink timing, rules out the PIC's own
supply as a cause.

### Two traps in the test firmware

**1. `ORG 0x0400`, never `ORG 0x0000`.** The default start for a PIC program is
the reset vector at `0x0000` — which is *inside the bootloader*. A naively
written test program lands exactly on top of the one thing that cannot be
replaced. Every test source must be explicitly ORG'd at `0x400` or above, where
it overwrites only the application, which `nm0506.HEX` restores.

**2. The bootloader must be told the app is valid.** It gates the jump on an
"application valid" flag — internal EEPROM address 0 = `0xAA`. This is already
known: it is what the vendor's `02 05 44 02 0a 00 aa` packet writes after a
firmware update. A test app at `0x400` will not run unless `EEPROM[0] = 0xAA`,
which ICSP can set directly.

### Toolchain — verified working 2026-08-04

No XC8 needed for firmware this small. `gputils` is installed and proven
end-to-end:

* `gpasm 1.5.2`, `p18f452` in the device list
* header at `/opt/homebrew/share/gputils/header/p18f452.inc`
* test build assembled correctly to `0x400`:
  `BCF LATC,4` → `988B`, `BCF TRISC,4` → `9894`, `BRA $` → `D7FF`

Build line: `gpasm -p p18f452 -o out.hex in.asm`

---

## 7. Restore — READ THIS BEFORE PROGRAMMING ANYTHING

> ### THE MERGED-IMAGE RULE
>
> **MPLAB programming bulk-erases the whole chip first** — program memory,
> EEPROM *and* config — then writes the file. It does not merge with what is
> already there.
>
> Therefore: **every HEX ever programmed into this chip must be a single merged
> image containing all of — the bootloader `0x0000`–`0x03FF` from our backup,
> the application, the config words, and the EEPROM data.**
>
> **Never program a file that lacks the bootloader region.** Consequences of
> getting this wrong:
>
> * Programming `nm0506.HEX` alone (it starts at `0x400`) erases the bootloader
>   and writes nothing back there. It is then gone from silicon permanently.
> * Programming the bootloader backup as a *second* pass erases the application
>   that the first pass just wrote. Two passes never coexist.
> * `nm0506.HEX` contains **no EEPROM records at all** (verified), so a chip
>   erase also destroys `EEPROM[0] = 0xAA` — the bootloader's "application
>   valid" gate — and nothing in the vendor file restores it. The app will not
>   run afterwards until that byte is rewritten.
>
> This applies to the §6 test firmware too. **`ORG 0x400` protects nothing
> here.** That rule matters only for writes mediated by the serial bootloader;
> an ICSP flash of a perfectly ORG'd test program still bulk-erases
> `0x0000`–`0x03FF` first.

### Consequence for the backup

The merged-image rule means everything depends on the step-4 backup being
genuine. Before any write is even contemplated:

* **Read the full device FIVE times and compare per-region hashes.** Read
  stability is the only self-contained proof the backup is real.
  `icsp_read_all.py` does all of this itself and refuses to bless a
  mismatched set — do not hand-wave past its exit code.
* Confirm the bootloader region is not a single repeated byte value. A stuck
  PGD line yields 1 KB of `0x00`, which looks like data and is not. (Also
  automated — five identical reads of garbage are still garbage, so hash
  equality alone is never accepted.)
* Verify the config words read back match the expected values below. If they do
  not, believe nothing else in the read. (Also automated.)
* `flash_diff.py` must issue a verdict, not WITHHELD. Its trust gates now also
  withhold when the bootloader region or the internal EEPROM is absent from
  the read, or when the HEX transfer contains malformed records —
  `./flash_diff.py --self-test` proves all seven gate/verdict cases.

---

## 8. Non-volatile store inventory — "all of the EEPROMs, all 6"

PTS displays six board firmware versions (APS / CCD / Lamp / DX / Motor /
USB) because it serves the whole FX35 family. On **this physical F-135
Plus**, the stores that actually exist in evidence, and their read coverage:

| # | Store | Where it lives | Read with | Covered? | Risk |
|---|---|---|---|---|---|
| 1 | U11 flash 32 KB **incl. bootloader `0x0000`–`0x03FF`** | inside U11 (PIC18F452) | `icsp_read_all.py --execute` (5×, verified) | **tomorrow** | Bootloader exists nowhere else. Bulk-erase on any programming pass |
| 2 | U11 config words `0x300000`–`0x30000D` | inside U11 | same (in `-GF` + `-GC`) | **tomorrow** | erased by any programming pass; values known from `nm0506.HEX` |
| 3 | U11 internal EEPROM 256 B (idx 0 app-valid `0xAA`; idx 5 **persisted fault code**; idx 4 suspected `0x0D`) | inside U11 | same — the tool prints idx 0/2/4/5/6 by name and **fails if the EEPROM region is absent** from the read | **tomorrow** | per-unit state; erased by any programming pass |
| 4 | FX2 boot EEPROM (personality, 9 B) | I²C `0x51` (8-bit `0xA2`) | `eeprom_backup.py` (0xA9, vendor params); `fx2/eeprom_read.c` | yes — content also known (`c0 05 0f 35 f2 07 aa 04 02`) | replaceable from `USB F135.bin`; write path locked (`eeprom_repair.py`) |
| 5 | **PCS / calibration EEPROM** — per-unit magnification, optical alignment, hardware version, per-format motor speeds (2 CRC32 sections, 398 B + 36 B) | **believed: the I²C EEPROM at `0x52`** (8-bit `0xA4`). Evidence: `FN_bReadEEPromToRegistry` reads it via `fcn.100160a0`, whose wrapper pushes `wValue 0xA4` = device n=2 → I²C `0x52` (docs/13 §, docs/15 §1e); `0x52` ACKs on this unit | `eeprom_backup.py --length 512`, five runs, compare (§0b) | **NO — never read. HIGHEST-PRIORITY GAP.** | **irreplaceable per-unit data, like the bootloader.** Read it BEFORE the ICSP session. If it truly reads all-`0xFF`, escalate: that would mean the calibration is already gone |
| 6 | Light-board PIC (PICL_PLUS, I²C `0x20` 7-bit): own flash, internal EEPROM, config | inside the light-board PIC | ICSP on that board's PIC only | no | working — **do not ICSP a working board tomorrow**. Vendor `lp*` images are PIC16 **and include `0x0000`–`0x03FF`**, so its firmware (unlike U11's) is restorable from files; unknown whether its internal EEPROM holds per-unit data |
| 7 | FX2 firmware (the "USB" version in PTS) | not persistent — RAM-loaded from host (`Pakon7.hex`) each power-on | on disk already | yes | none |
| 8 | Other I²C serial EEPROMs, if any, in `0x50`–`0x57` | main board | `eeprom_backup.py` sweeps all eight addresses | §0b covers | unknown devices get backed up for free |

Not in evidence on the F-135 Plus: an APS board (35 mm-only model), a DX-board
MCU (DX sensors are read by the light board), a CCD-board MCU (the F-135 CCD
board carries the 14-bit A/D; only the F-235/335 CCD board is known to have
its own PIC and an AT17LV512A FPGA-config PROM). The Spartan FPGA on this main
board is programmed by the PICM at runtime; no FPGA config PROM has been
identified on this board — if one is ever found near JM10, it joins this
table.

**Discrepancy to resolve on hardware (§0b does it):** the boot EEPROM at
`0x51` was repaired and read back correct on 2026-08-02 (docs/17), but a later
report says the `0xA2`/`0xA4` devices read all-`0xFF`. All-identical bytes
from `eeprom_backup.py` across addresses means the read is NOT addressing
(its own warning says so) — do not conclude "erased" from a read that fails
that check.

---

## Context

Full evidence log: `docs/evidence.html`. Current state summary:
`docs/26-HANDOFF.md`. Root cause: `docs/25-root-cause.md`.

Established facts relevant here: U11 executes code (blink timing matches four
firmware constants), the MSSP was armed at address `0x44` on the only path to
the main loop, the I²C bus itself is good (the light board shares those wires
and works), and nothing on the chip is code-protected.
