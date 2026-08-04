# ICSP procedure — PICkit 3 on U11

Written 2026-08-04, the day before the programmer arrives. Follow in order.

**The governing rule: read everything before writing anything.** No copy of the
PICM bootloader (`0x0000`–`0x03FF`) exists anywhere. 348 HEX files across every
vendor install tree were parsed; every PICM image starts at `0x400`. If a write
clobbers it, it is gone permanently and this scanner is unrecoverable in a way
it currently is not.

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

## 4. Read and save, in this order

| # | Region | Size | Why |
|---|---|---|---|
| 1 | `0x0000`–`0x03FF` bootloader | 1 KB | **Irreplaceable — no copy exists** |
| 2 | Full flash `0x0000`–`0x7FFF` | 32 KB | Complete picture |
| 3 | Internal EEPROM | 256 B | Holds the suspected stray `0x0D` at addr 4 |

Save all three to `~/pakon-icsp-backup-<date>/`, take checksums, and **verify the
files are non-empty and plausible before proceeding.** Copy them somewhere off
this machine.

---

## 5. The diff that might end this without any test firmware

Compare the full flash read against `nm0506.HEX`.

Only four points have ever been verified: `0x400`–`0x47F` (repaired),
`0x800`, `0x1000`, `0x2000`. **The other ~29 KB has never been read.** If there
is corruption anywhere in it, this diff finds it — and that would be the fault,
found, with nothing written.

Vendor image:
`/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/Config/Firmware/nm0506.HEX`

Also check EEPROM address 4 for `0x0D` — the reconstructed stray write.
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

* **Read the flash twice and compare hashes.** Read stability is the only
  self-contained proof the backup is real.
* Confirm the bootloader region is not a single repeated byte value. A stuck
  PGD line yields 1 KB of `0x00`, which looks like data and is not.
* Verify the config words read back match the expected values below. If they do
  not, believe nothing else in the read.

---

## Context

Full evidence log: `docs/evidence.html`. Current state summary:
`docs/26-HANDOFF.md`. Root cause: `docs/25-root-cause.md`.

Established facts relevant here: U11 executes code (blink timing matches four
firmware constants), the MSSP was armed at address `0x44` on the only path to
the main loop, the I²C bus itself is good (the light board shares those wires
and works), and nothing on the chip is code-protected.
