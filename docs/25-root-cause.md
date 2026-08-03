# 25 — Root cause, and the bug that hid it

Two findings that supersede earlier documents, plus what independent
re-analysis confirmed and corrected.

## The breaking packet was `04 03 44 00 0d`

`tools/find_light_path.py` walked the whole Type 4 command space at board 0x44
hunting for the lamp. Its log recorded "commands 0x01-0x0d accepted".

That was read at the time as "only the low commands are valid". It means the
opposite: **the board answered up to 0x0d and then stopped**. Commands 0x0e
through 0xff NAKed because nothing was there to answer.

So the breaking packet is the last one accepted: `04 03 44 00 0d`.

Confirmed in the PIC firmware: `nm0506` implements command `0x0d` at `0x1DAC`
-> `0x1ABE` -> `GOTO 0x000000` (jump to bootloader) and command `0x01` at
`0x1DA8` -> `0x1AAE` -> `RESET`. Bootloader entry erases the application
vectors, which is exactly the 128 bytes later found blank at
`0x000400-0x00047F`.

**Not a fragile board, not bad luck.** A documented vendor command, sent blind
into a command space that had not been identified.

## Register reads are two packets, not one

```
01 03 <board> <n> <reg>      request
01 03 <board> <n> 07         fetch -> 01 <n+3> <board> <status> <data...>
```

`FN_bDrvGetByteArrayNL` (`fcn.10009410`) issues the request, then rewrites the
register byte to `0x07` and sends again; only the second response carries data.

Validated on hardware: host 0x10 register 3 returns `01 04 10 88 0f 03` = FX2
firmware v3.15. With the correct form the light board returns real values for
the first time in this project:

```
reg 0x02  pending error   -> 0x02
reg 0x83  hardware status -> 0x12
reg 0x84  temperature     -> 0x0280
reg 0x88  temps MB + LB   -> 0x0282, 0x01f2
```

**Every register dump taken before this fix is meaningless** -- they recorded
the request echoing back. That includes the dump used in docs/18 to conclude
0x46 was "floating bus noise". That conclusion was unfounded, and it is what
dismissed the bootloader hypothesis, which was correct.

## How the two bugs combined

After command `0x0d`, board 0x44 stopped answering. Every subsequent CCD and
FPGA register write was **NAKed** -- but the tools reported "ok" on any
response without checking the status byte. Hours were spent believing the
sensor was configured while not one packet reached the board.

That single unchecked byte is why the damage was invisible, why the acquisition
work appeared correct and did nothing, and why the investigation went through
the lamp, the optical path, a filter wheel and the wrong board in turn.

Both fixed: a write is accepted only when `resp[0] == 0x07 and resp[3] == 0x00`;
a read is two packets with data at `resp[4...]`.

## Status byte

Type 7 responses, `resp[3]`: 0 accepted, 1 `EC_DRV_PacketHostErrorNoAck`
(the board never acknowledged its I2C address), 2 format, 3 checksum,
6 endpoint timeout, 9 bus error. Type 1 data responses use `resp[3]` as a
bitmask: `0x01` busy, `0x04` FIFO overflow, `0x10` comm error, `0x20` command
error.

So `07 02 44 01` is not "the board declined" -- it is **no I2C acknowledgement
at all**, a hardware-level fact.

## What independent re-analysis established

- **Boot order verified by hand.** `SSPCON1 = 0x36` and `SSPADD = 0x44` are
  written at `0x1A8C`, reached only from `0x2C6A`, before the first modulated
  LED activity and before the main loop at `0x2C8E`. There is no bypass path.
  **A stable repeating blink therefore proves the I2C slave was armed at 0x44.**
- **The blink engine's constants match the hardware.** 200 ms / 600 ms /
  400 ms / 3000 ms decoded from the binary against 234 / 635-700 / 368-401 /
  ~3000 ms measured. A four-way match; the blinking device is running this
  firmware from a normal boot, so the vector repair is intact.
- **Code 0 blinks solid on.** So a blinking LED means a non-zero fault code.
- **On a cold boot the fault measurement is fresh**, taken that boot
  (`0x1956` branches on `/POR`), not restored from EEPROM. The orange front
  panel reflects a live fault.
- **`02 05 44 02 0a 00 aa` is exonerated.** It writes 0xAA to PIC internal
  EEPROM address 0 -- the bootloader's "application is valid" flag, and exactly
  what the vendor's updater sends after every firmware update. The application
  never reads EEPROM 0 or 1. Its only cost was removing the bootloader safety
  net.
- **No copy of the PICM bootloader exists** in any shipped file: every PICM
  image starts at 0x400, every PICL image at 0x340. Only ICSP can recover
  `0x0000-0x03FF`.

## Where it stands

The PIC executes, arms its I2C slave, runs its main loop, blinks a fault code,
and does not acknowledge its address. The bus is proven good -- the light board
shares those two wires and answers perfectly.

Remaining candidates, none yet distinguished:

1. **A supply rail out of tolerance.** Blink bit 1 covers ADC channels 0-3
   (`EC_BistPicmVinFail`/13V/12V/6V). A dead logic rail feeding a bus buffer on
   the PICM's segment explains the LED, the blink, the front panel and the
   silence with one fault.
2. **A corrupted `MOVLW 0x44` at `0x2C62`**, which loads SSPADD. That byte sits
   in the ~3 KB above 0x2000 never verified after the repair. A flipped bit
   puts the PIC on a different address, alive and invisible. Partly argued
   against by a full 0x00-0xff sweep finding nothing unexplained -- though that
   sweep sent whole packets, and an address-only scan could still differ.
3. **RC3/RC4 electrically open** (pins 37 and 42 on the 44-pin TQFP).

## Hardware

- PCB **#125430 REV C**, so `nm0506.HEX` is the correct image.
- `U11` = the PIC, 44-pin TQFP, relabelled `125507A 2208`.
- `JM11` = 5-pin ICSP header beside it. `JM10` = 2x5, FPGA JTAG.
- `U6` = `CY7C68013A-128AXC`, the FX2.
- Nothing is code- or write-protected, so ICSP can read and rewrite everything
  including the bootloader.

## Lesson

Do not sweep an unknown command space on a live controller, and check the
status byte on every packet. The first would have prevented the damage; the
second would have revealed it in minutes rather than hours.
