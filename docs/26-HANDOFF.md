# 26 — HANDOFF: current state, and the one test that matters

Read this first. It supersedes anything conflicting in docs/18 and docs/23,
both of which contain conclusions later proven wrong.

## The single most important thing to do next

**Power the scanner on and send it NOTHING for 60 seconds.** No firmware load,
no probing, nothing on the bus. Then load firmware and probe 0x44 **once**.

Why: on PIC18, a byte left in `SSPBUF` sets the `BF` flag, and **BF makes the
MSSP NAK its own address**. Only reading SSPBUF or resetting the module clears
it. The PICM application's I2C init at `0x1A8C` **never reads SSPBUF** and never
toggles SSPEN (it writes 0x36 over an already-0x36 register, which does not
reset the module).

So if the bootloader ACKs anything during its hand-off window and jumps to the
application without draining the buffer, the application inherits BF and
**NAKs every address forever, while running its main loop and blinking**.
That is exactly the observed symptom.

The two cases differ in precisely this way:

```
WORKED : bootloader quiescent -> command 8 -> 8 s of silence -> then traffic
FAILED : power-up -> hand-off -> host loading firmware and probing within 1-2 s
```

**`tools/catch_bootloader.py` probes as early as possible at power-on, so it
would re-trigger this on every attempt.** Do not run it again until this test
is done.

Outcome:
- **0x44 answers** -> our own bus traffic during boot was poisoning the MSSP.
  Fully recoverable in software; the fix is a startup delay in the host port.
  Then send command 0x10 with data 1 to refresh EEPROM[2] and clear the stale
  fault code.
- **Silent** -> every software-reachable cause is excluded by evidence, and
  ICSP via JM11 is the honest next step.

## What is proven, and what caused this

**The breaking packet was `04 03 44 00 0d`.** The sweep log's "commands
0x01-0x0d accepted" means the board answered up to 0x0d and then stopped.
`nm0506` implements 0x0d as `GOTO 0x000000` -- bootloader entry, which erases
the application's vector rows. That is exactly the 128 bytes found blank at
`0x000400-0x00047F`.

**Two tooling bugs concealed it for hours:**
1. Writes were reported "ok" on any response without checking the status byte.
   A write is accepted only when `resp[0] == 0x07 and resp[3] == 0x00`.
2. Register reads are **two packets**, not one:
   `01 03 <board> <n> <reg>` then `01 03 <board> <n> 07`, data at `resp[4..]`.
   Every dump taken before this fix recorded the request echoing back.

Both are fixed in the tools.

## Exonerated by evidence, not argument

- **Flash.** The application physically cannot write flash: `nm0506` contains no
  `TBLWT` and never sets `EEPGD`. `tools/flash_picm.py` cannot emit an address
  below 0x400. Pre-flash reads matched factory content at 0x800/0x1000/0x2000.
  Flash today is byte-identical to flash during the working session, bootloader
  included.
- **The resident image is `nm0506`**, confirmed: 0x1000 and 0x2000 are the
  addresses that discriminate nm0406 from nm0506, and both matched.
- **`02 05 44 02 0a 00 aa`** writes 0xAA to PIC internal EEPROM address 0 -- the
  bootloader's "application is valid" flag, and exactly what Kodak's updater
  sends after every firmware update. The application never reads EEPROM 0 or 1.
- **The stray EEPROM write** from the sweep's command 0x0A is real (best
  reconstruction `EEPROM[4] = 0x0D`, from stale buffer bytes left by
  `probe_sensor_path.py`'s gain-restore packet). It probably explains the fault
  code and the orange LEDs. It **cannot** explain the missing ACK: on a cold
  boot the app never reads EEPROM before arming the MSSP, and no fault state
  touches SSPCON1 or SSPADD.

## What the hardware is telling us

- The PIC **executes**: its diagnostic LED blinks a stable repeating pattern
  whose measured widths (234 / 635-700 / 368-401 / ~3000 ms) match the
  firmware's computed constants (200 / 600 / 400 / 3000 ms) four for four.
- **The I2C slave was armed.** `SSPCON1 = 0x36` and `SSPADD = 0x44` are written
  at `0x1A8C`, reachable only from `0x2C6A`, before the first modulated LED
  activity and before the main loop at `0x2C8E`. No bypass path exists.
- **Blink code 0 is solid-on**, so a blinking LED means a non-zero fault code.
- The **bus is good**: the light board shares those two wires and answers
  perfectly.

## Hardware identification

- PCB **#125430 REV C** -> `nm0506.HEX` is the correct image
- `U11` = the PIC, PIC18F452, 44-pin TQFP, relabelled `125507A 2208`
- `JM11` = 5-pin ICSP header beside it. `JM10` = 2x5, FPGA JTAG -- not that one
- `U6` = `CY7C68013A-128AXC`, the FX2
- 44-pin TQFP: `MCLR/VPP` = 18, `PGC` = 16, `PGD` = 17, `VDD` = 7/28,
  `VSS` = 6/29, `RC3/SCL` = 37, `RC4/SDA` = 42
- Nothing is code- or write-protected (`CONFIG5L=0x0f`, `CONFIG5H=0xc0`,
  `CONFIG6H=0xe0`), so ICSP can read **and** rewrite everything
- LVP is disabled (`CONFIG4L=0x81`), so a high-voltage programmer is required

## If a programmer is needed

**PICkit 3** (~$20 clone). MPLAB IPE runs natively on macOS and reads flash,
EEPROM and config in one operation. Use MPLAB X **v5.35 or earlier** -- PICkit 3
support was dropped in v5.50. Five female-to-female jumpers to reach JM11.
Verify `JM11` pin 1 has continuity to chip pin 18 before connecting: pin 1 is
MCLR/VPP and carries up to 12 V.

**Read before writing.** In order: the bootloader at `0x0000-0x03FF` (exists in
no file Kodak ever shipped), the 256 bytes of internal EEPROM, then all of
flash. Only then consider writing.

## Repaired and verified

- **Boot EEPROM**: `c0 05 0f 35 f2 07 aa 04 02`, matching Kodak's
  `USB F135.bin`. Survives power cycles; `pakon_load.py` auto-selects
  `Pakon7.hex` with no `--hex` override.
- **PICM vectors**: 8 blocks at `0x400-0x47F` rewritten from `nm0506.HEX` and
  verified 8/8. The board now boots on its own.
- **Colour correction**: complete and verified exact against Kodak's own data.
  Density LUT `-3500*log10(i/16383)` reproduces the shipped 16,384-entry
  `_ClientColNegLut.txt` with worst deviation 0.000050. The 3x4 matrix loads
  from `_ClientColNegMat.txt`. 92 film IDs parsed, Ilford at 105-110.

## The lesson

Do not sweep an unknown command space on a live controller, and check the
status byte on every packet. The first would have prevented the damage; the
second would have revealed it in minutes instead of hours.
