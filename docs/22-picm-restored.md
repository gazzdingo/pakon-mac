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

## After a cold boot — the application runs but does not answer I2C

The flash repair is real and persistent. From a cold power-on the front LEDs
now read **green / orange / orange**, where before the repair all three were
red. The board starts on its own, so the restored reset vector is being used.

But from a cold boot neither address answers:

```
0x10 host       07 02 10 00   PRESENT
0x40 light      07 02 40 00   PRESENT
0x44 main APP   07 02 44 01   absent
0x46 main BOOT  07 02 46 01   absent
```

Note this differs from the pre-repair state, where the **bootloader** answered
at 0x46. Nothing answering there now is consistent with the application having
started and the bootloader having correctly stood down.

Immediately after the in-session restart (`picm_run_app.py --run`) the
application *did* answer at 0x44 and accepted the entire CCD bring-up. After a
power cycle it does not. So the application starts, and then stops responding.

### Working hypothesis

The application boots, runs its built-in self test, fails something, and halts
or declines to service I2C. The two orange LEDs are consistent with that, and
the vendor has error codes for exactly this class of failure:

```
EC_BistPicmVinFail  EC_BistPicm13VFail  EC_BistPicm12VFail
EC_BistPicm6VFail   EC_BistPicm5VFail   EC_BistPicm3VFail
EC_BistPicmMotorFail
EC_BistPiclMotherBdFpgaCommFail   (the light board testing the motherboard)
```

This is a hypothesis, not a conclusion. What would confirm it is finding where
the application reports BIST results and reading them.

### Host and light board status, cold boot (reads only)

```
host 0x10  reg 0x00  88 03 00     reg 0x03  88 0f 03   (fault bit clear)
           reg 0x02  88 46 32     reg 0x07  88 0f 03
           reg 0x09  88 02 03     reg 0x0a+ status 0x20 = does not exist
light 0x40 reg 0x00  88 00 80
```

Both boards are healthy. Neither obviously reports why the PICM is quiet.

### The EEPROM byte 0 reverted again

The scanner enumerated as bare `04b4:8613` after this power cycle, so the
format signature has gone back to `0x5c` a second time. Bytes 1-8 have held
both times; only byte 0 reverts. `pakon_load.py` works around it, but the write
is evidently not committing durably the way the others did.
