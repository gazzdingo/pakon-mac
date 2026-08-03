# 20 — The PICM is alive in its bootloader

**This supersedes the conclusions in docs/18.** The main board has not failed.

## The decisive test

`FN_bDrvFindPicController` (TLB.dll `fcn.10008ba0`) considers a board present
iff a Type 4 command `04 03 <addr> 00 00` returns `resp[0] == 7 && resp[3] == 0`.
Applying that criterion, with control addresses that must be empty:

```
TARGETS
  0x44  PICM application     absent    07 02 44 01
  0x46  PICM BOOTLOADER      PRESENT   07 02 46 00
  0x40  light board          PRESENT   07 02 40 00

CONTROLS (must be empty)
  0x48  absent   07 02 48 01
  0x4a  absent   07 02 4a 01
  0x60  absent   07 02 60 01
  0x62  absent   07 02 62 01
  0x50  absent   07 02 50 01
  0x52  absent   07 02 52 01
```

Every control NAKs while 0x46 ACKs. A floating bus would ACK the controls too,
so 0x46 is a real device, not pickup.

## Why docs/18 got it wrong

The retraction there rested on 0x46 answering register reads with values that
varied between reads, and concluded "floating bus". That inference is invalid:
**a bootloader implements no register file**, so unstable reads cannot
distinguish a bootloader from a floating bus. The control-address test can, and
does.

## The vendor expects exactly this

`FN_bUpdate` (`fcn.1001c3e0`) deliberately continues when 0x44 is silent and
flashes `NMxxyy.HEX` from `Config\Firmware\` through the PICM bootloader at
**0x46**, hardcoded at `0x1001c6d5`, via `FN_bPicToBootLoaderState`
(`fcn.1001b9b0`) and `FN_bLoadPicLarge` (`fcn.1001bb10`). `fcn.1000afd0`
cycles 0x44 → 0x46 → 0x24 → 0x26 for the same reason.

So "application address silent, bootloader address answering" is a state the
vendor's own updater is written to recover from.

## Likely cause

Writing register **0x97 = 1** to a live board is the enter-bootloader command
(`0x1001c4ca`). The blind write sweep early in this project — the same one that
damaged the boot EEPROM — could have issued it. This is most likely
self-inflicted, and therefore repairable rather than a hardware failure.

## What this means

The board needs `nm0506.HEX` (PICM, F-135 Plus, PCB #125430C — check the PCB
number before choosing) flashed through the bootloader at 0x46. Until the
`FN_bLoadPicLarge` wire format is decoded, **send nothing else to 0x46**: it is
a bootloader awaiting a specific protocol, and guessing at it is exactly the
class of action that caused the original damage.

## Status-byte discipline

The review also found that `init_ccd.py` and `start_acquire.py` reported "ok"
on any response, without checking the status byte. Against a NAKing board the
entire init sequence appeared to succeed. Fixed: a write is accepted only when
`resp[0] == 0x07 and resp[3] == 0x00`.

```
status 0  accepted
status 1  rejected (NAK)
status 2  unsupported packet type
```

Also fixed: register 0x89 in the InitCcd prologue is a **byte** write
(`02 04 <board> 01 89 <val>`, via `fcn.10009ba0`), not the word write used
previously.
