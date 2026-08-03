# 22 — The PICM is restored. What actually happened.

**The main board is working again.** Board 0x44 answers, the bootloader at
0x46 has stood down, and every CCD and FPGA register write is accepted.

## What was actually wrong

The firmware was never lost. Reading the application flash back through the
bootloader showed:

```
0x000400 - 0x00047F   BLANK (0xFF)     8 blocks, 128 bytes
0x000480 - 0x002D7F   MATCHES the vendor image exactly
```

Exactly two 64-byte rows were erased, and they hold the **reset and interrupt
vectors**. `0x400` should contain `e1 ef 15 f0`, a PIC18 `GOTO` to the
application entry point. With it blank, the bootloader had nothing to hand
control to, so the application could never start -- which is why 0x44 stayed
silent through every earlier attempt.

That is the vendor's bootloader-entry command working as designed: erase the
vectors so the application cannot run, leaving the bootloader in charge. A
deliberate, minimal action, not corruption.

## How it was triggered

Entering the bootloader is two packets, both to the application address:

```
02 05 44 02 0a 00 55     arm
04 03 44 00 01           enter bootloader
```

`tools/find_light_path.py` walked all 256 Type 4 commands at board 0x44 hunting
for the lamp, so it sent `04 03 44 00 01`. The tool logged it as "accepted" and
nothing more, because it only watched EP 0x86 for illumination -- a mode change
is invisible to that test.

## The repair

1. Read the flash back and map the damage: 8 blocks, `0x400`-`0x47F`
2. `flash_picm.py --write --limit 8` -- erase 2 rows (already blank), write 8
   blocks from `nm0506.HEX`
3. Verify all 8 against the vendor image: **8/8 match**
4. `picm_run_app.py --run` -- the three-step restart

```
step 1  04 03 46 00 08          exit bootloader        ok  07 02 46 00
step 2  wait 8 x 1000 ms
step 3  02 05 44 02 0a 00 aa    hand-off to 0x44       ok  07 02 44 00

0x44 application : PRESENT
0x46 bootloader  : absent
```

128 bytes written, not the full 10,616. The rest of the firmware was intact
throughout.

## Confirmed on hardware

- **Read-back payload offset is 4.** The last unproven assumption in the
  flasher, now measured rather than derived.
- **Reads take two packets**, not one: `02 06 46 03 01 <addr24 LE>` to set the
  address, then `01 03 46 <len> 07` to fetch. A single packet only ACKs.
- The bootloader's command set is confirmed: 1 read, 2 write, 4 erase,
  8 finalise.

## Known bug

`flash_picm.py`'s `read_block()` still uses the old single-packet read, so its
verify pass aborts. That abort is the safety net behaving correctly -- it
refused to send command 8 without verification. Verification was done instead
with `picm_read_flash.py`, which has the correct two-packet form. **Fix
`read_block()` before using the flasher again.**

## Where acquisition stands

With 0x44 restored, the full CCD bring-up runs and every write is accepted:

```
reg 0x82 idx 4/5/6/10/11   geometry, integration time
reg 0x84 idx 0..7          A/D mode, gains, offsets
reg 0x82 idx 0 = 0x163     control word
all -> ok  07 02 44 00
```

EP 0x86 still does not track the A/D gain (mean moves 0.16 across gain 0..255),
so acquisition is not yet running. But this is now an ordinary software problem
against a board that responds, rather than a dead board.

## Lesson

Do not sweep an unknown command space on a live controller. This one cost the
project twice: the boot EEPROM via an address sweep, and the PICM's vectors via
a command sweep. Both times the answer was already in `TLB.dll`.
