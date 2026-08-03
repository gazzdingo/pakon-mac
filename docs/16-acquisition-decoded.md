# 16 — The acquisition path, decoded from TLB.dll

Everything here came from reading the vendor binary, not from probing hardware.
Two techniques did the work, and both are reusable.

## Technique 1 — the vendor strings are UTF-16

`strings` on macOS reports ASCII by default and finds almost nothing useful in
`TLB.dll`. The interesting material is UTF-16LE. Use radare2:

```sh
r2 -q -c "izz" TLB.dll | grep utf16le
```

That yields 1,115 wide strings including **359 `FN_*` function names**, the
`EC_*` error enum, and the log format strings. An earlier ASCII-only search
produced zero `FN_` hits and led to the false conclusion that those symbols did
not exist. They do.

## Technique 2 — symbolicate via the logger

Every function logs under its own numeric enum. `fcn.100170b0` is the
enum → name table (a large switch, one `push str.FN_...` per case), so the case
index *is* the enum. The logger is `fcn.1001acd0`, called as:

```
push <errorCode>
push <functionEnum>     <- identifies the calling function
push <logHandle>
call fcn.1001acd0
```

So `push <enum>` immediately before the handle push names the function. Parse
the table, then search for the enum:

| enum | name |
|-----:|------|
| 82  | `FN_bDrvCcdAcquireControl` |
| 130 | `FN_bDrvReadScanLine` |
| 131 | `FN_bDrvResetFifos` |
| 205 | `FN_bGetScanLines` |
| 333 | `FN_bDrvCcdAcquireAndDxStart` |

Note `push imm8` only encodes values ≤ 0x7F; larger enums assemble as
`68 xx 00 00 00`. Searching for the wrong encoding finds nothing.

## The two IOCTLs

`TLB.dll` calls `DeviceIoControl` at four sites. Two are
`IOCTL_DISK_GET_DRIVE_GEOMETRY` and unrelated to the scanner. The other two:

| IOCTL | method | purpose |
|-------|--------|---------|
| `0x222090` | METHOD_BUFFERED | the 64-byte packet path |
| `0x222059` | METHOD_IN_DIRECT | `IOCTL_EZUSB_VENDOR_OR_CLASS_REQUEST` |

`0x222059` (`fcn.10015d80`) sends a **USB control transfer** with the Cypress
DDK's 10-byte `VENDOR_OR_CLASS_REQUEST_CONTROL` struct:

```
base+0  direction      base+4  bRequest
base+1  requestType    base+6  wValue
base+2  recipient      base+8  wIndex
base+3  reserved       out buffer <= 0x5000 bytes
```

It validates `bRequest` before sending — `0xA0`, and `0xA2`–`0xAC`:

```asm
cmp bl, 0xa0 ; je  accept
cmp bl, 0xa1 ; jbe reject
cmp bl, 0xac ; jbe accept
```

Only four call sites exist, all EEPROM or firmware. `wValue` is computed as
`((n | 0x50) << 1) | readBit` with `n <= 7` — a 7-bit I²C address in the
`0x50`–`0x57` serial-EEPROM range — with `0xA2` = write and `0xA9` = read, and
`wIndex = 0x1234`.

**This is the vendor-sanctioned EEPROM path**, and it is *not* the raw I²C
packet route that damaged this unit's boot EEPROM. Any future repair should go
through here. It also explains the earlier dead end where `wIndex = 0x1234`
looked like a "magic unlock": the value is real but only meaningful paired with
these `bRequest` codes.

Acquisition does **not** use vendor requests.

## CCD register 0x82 — acquire control

`FN_bDrvCcdAcquireControl` (enum 82) is `fcn.10029810`, a thin wrapper over
`fcn.10029770`:

```asm
mov si, word [edi + 0x358]     ; host-side shadow of the register
and eax, 0x3ff                 ; 10-bit mask
set:   new = shadow |  mask
clear: new = shadow & ~mask
                               ; early-out if unchanged -- no packet sent
push 0x82                      ; CCD register 0x82
call fcn.1000a5d0              ; PutRegisterCcd
mov word [edi + 0x358], si     ; shadow updated only on success
```

The register is **write-only with a host-side shadow**, so it cannot be read
back; the host must track it. Masks used at the call sites:

| mask | bit | set by |
|-----:|----:|--------|
| `0x001` | 0 | `FN_bDrvCcdAcquireControl` — master acquire enable |
| `0x002` | 1 | `fcn.1002c340` |
| `0x060` | 5,6 | `fcn.1002c340`, set together |
| `0x100` | 8 | `fcn.10029860` |

## PutRegisterCcd packet format — confirmed

`fcn.1000a5d0` builds:

```
02 <len> <board> 03 <reg> <idx> <lo> <hi>
```

with `board` read from `[esi+0x130]` (0x44 on this unit) and a register
whitelist of exactly `0x82` and `0x84` — anything else is rejected and logged
as `ucCommand`. This confirms the encoding already used in `tools/`.

## CCD init constraints — fcn.1002c340

The assertion strings name the configuration parameters and their limits:

- `uiCcdPixelHeight`, `uiCcdPixelOffset`, `uiCalibrationOffset`
- `0 != (uiCcdPixelHeight % 4)` — height must be a multiple of 4
- `(CALIBRATION_HEIGHT + CALIBRATION_OFFSET) < (uiCcdPixelHeight + uiCcdPixelOffset)`
- `uiCcdIntegrationTime`, bounded by `0xFFD` (4093)
- compares against `0x424` (1060) and `0x848` (2120) — the two CCD heights

The sequence is: validate geometry → `fcn.10029860` (mask `0x100`) →
integration time → `PutRegisterCcd(0x82, idx 6, integrationTime)`.

**Register 0x82 is indexed.** `fcn.1002c340` writes `idx 6`, while
`FN_bDrvCcdAcquireControl` writes `idx 0`. The bit masks and the indices are
separate things, and a full bring-up writes several indices.

## Hardware result so far

Setting `0x82` index 0 bit 0 alone is **not** sufficient. Measured on the unit
with `tools/start_acquire.py`:

- write accepted (`07 02 44 01`)
- EP 0x86 mean `647.4` → `647.6`, stdev `66.05` → `66.14`
- A/D gain 0 → 255 still moves the mean by `0.08` and the stdev by `0.28`

For reference, before this power cycle the same stream sat at a constant `1240`
rather than `647`. **The constant differs across firmware loads**, which is
itself evidence that it is firmware-side filler and not sensor readout.

Remaining work is the rest of the `fcn.1002c340` bring-up: the geometry
registers, the integration time at `0x82` index 6, and `fcn.10029860`'s
`0x100`. Acquisition needs the full sequence, not one bit.

## Colour correction — authoritative vendor data found

`Config/ColorCorrection/` holds the real vendor data, which supersedes anything
derived:

- `_ClientColNegMat.txt` — the 3×4 negative matrix
- `_ClientColNegLut.txt` — 16,384-entry density LUT
- `rpd.pf`, `unity.pf`, `srgb.pf`, `romm.pf`, `ColRevLut1.pf`
- `satplus03..15` / `satminus03..15` — saturation variants
- `cold_bw.pf`, `warm_bw_ld0_1_4-5.pf`, `sepia_ld0_9_22.pf` — B&W toning
- `defaults.ini` — film product ID → manufacturer

The matrix:

```
R' =  1.11882*R - 0.10130*G - 0.01161*B -  82.60334
G' = -0.20096*R + 1.10082*G + 0.11698*B - 586.90975
B' = -0.11657*R + 0.04834*G + 1.08274*B - 707.78706
```

This is exactly the `out[i] = sum_c coeff[i][c]*LUT[raw_c] + offset[i]` form
already implemented; the `coeff_*_3` terms are the offsets.

The LUT verifies the density formula against the vendor's own table:

```
LUT[i] = -3500 * log10(i / 16383)
```

Best-fit constant `3500.000155`, worst absolute deviation **0.000050** across
all 16,384 entries — that residual is just the file's 4-decimal rounding.
`LUT[0]` is clamped to 16383 because the logarithm is undefined at zero.

`defaults.ini` groups film product IDs by manufacturer, including
**Ilford Imaging = IDs 105–110**, plus `[BnW]`, `[POSITIVE]` and `[IMPORTED]`
categories — directly relevant to the HP5 / FP4 / Delta 3200 request.

## Corrections to earlier claims in this project

- The `FN_*` symbols **do** exist; an ASCII-only `strings` run missed them.
  `FN_bDrvMoveFilterWheel` and `EC_MotorFault_FilterWheel` are real.
- The CCD is **not** a separate board. `ReadmeF135.txt` documents PICL (light)
  and PICM (motor/main) only, and notes PICM firmware carries the
  "default CCD board config" — so CCD registers correctly go to board `0x44`.
  The flat A/D gain sweep is not a wrong-board error.
- `fcn.1000bdd0` polls `0x40`, `0x44`, `0x28`; `0x28` is gated behind a
  presence check and is most likely the optional APS unit.

## Hardware result — full FPGA bring-up run

`tools/init_ccd.py` ran the complete ported sequence. Every register write was
accepted by the board, and the stream did not change:

```
before init   mean 647.4  stdev 66.51
after  init   mean 647.3  stdev 66.45
A/D gain 0 vs 255, after init: mean moves 0.26, stdev moves 0.10
```

So register 0x82 is configured correctly and acquisition still does not run.

## What the enum names actually say

The logger enum table renames the pieces and corrects a wrong assumption:

| enum | name |
|-----:|------|
| 120 | `FN_bDrvPutCcdFpgaControlReg` |
| 121 | `FN_bDrvPutCcdFpgaSettings` |
| 128 | `FN_bDrvPutRegisterCcd` |
| 129 | `FN_bDrvPutRegisterWord` |

Register 0x82 is the **FPGA**, not the CCD chip: `fcn.10029770` is
`PutCcdFpgaControlReg` and `fcn.1002c340` is `PutCcdFpgaSettings`. Programming
the FPGA is necessary but evidently not sufficient.

## The two remaining prerequisites

`FN_bDrvInitCcd` issues two `PutRegisterWord` calls *before* any FPGA
programming, and neither has been ported:

```asm
mov al, byte [esi + 0x2f9]     ; 0x40 -- the LIGHT board address
mov ecx, dword [var_14h]
push 0
push 0x87                      ; register 0x87
push ecx                       ; board 0x40
push edi
call fcn.10009d40              ; FN_bDrvPutRegisterWord
...
push 0x89                      ; register 0x89
push eax
push edi
call fcn.10009ba0
```

These target a **different register space on a different board** — the light
board at 0x40, not the motor board at 0x44 where every CCD/FPGA register goes.
`PutRegisterWord` uses its own packet builder (`fcn.10009ae0`, which sets
`Type = 2` and funnels into `fcn.100095a0`), so its wire encoding is not the
`02 06 44 03 <reg> <idx> <lo> <hi>` form used by `PutRegisterCcd`.

That encoding must be decoded from `fcn.10009ae0` before anything is sent.
Guessing a packet format is what damaged this unit's boot EEPROM; it is not
worth repeating for a register write.

Note also that `fcn.100095a0`, not `fcn.10008530`, is the real low-level
sender. `tools/emulate_tlb.py` hooks the latter and therefore captures nothing
from the CCD bring-up path.

## What EP 0x86 actually contains

Statistics hid this for a long time. The raw bytes have a **period-3
interleave**:

```
604 590 736 | 602 596 742 | 612 594 746 | 606 592 748 | 606 588 738
```

Three streams at roughly 608, 593 and 741, with only 36 distinct values across
4096 samples. Every mean computed before this — the famous "constant 1240",
later "647" — was the average of three separate levels, which is why it looked
featureless.

It is still not sensor data. Sampling each stream separately with the lamp off,
on, and off again gives the same three numbers every time:

```
lamp OFF   608.3  593.4  740.7
lamp ON    740.5  608.2  593.3
lamp OFF   593.4  740.7  608.3
```

Those are one set of values, rotated — the de-interleave phase shifts with the
FIFO flush alignment, nothing more. Illumination changes none of them.

So EP 0x86 carries a static three-level pattern. Combined with the A/D gain
having no effect, the conclusion is unchanged: the FPGA is not clocking the
sensor, and what reaches the endpoint is generated downstream of it.

## Endpoint map — confirmed on hardware

```
ep 0x01 OUT BULK 512    commands
ep 0x81 IN  BULK 512    responses
ep 0x86 IN  BULK 512    data
```

There is no second data endpoint, so 0x86 is the only place a scan can arrive.

## FN_bDrvPutRegisterWord — encoding derived and confirmed

`fcn.10009ae0` is the generic builder behind every register write:

```
02 <PktLen> <board> <dataLen> <reg> <data...>      PktLen = dataLen + 3
```

With `dataLen = 3` this reproduces the known-good `PutRegisterCcd` packets
(`02 06 44 03 82 00 63 01`), which is what validates it. A word write is
`dataLen = 2`.

Both `InitCcd` prerequisites were then sent and **accepted with status 0**:

```
02 05 40 02 87 00 00   ->  07 02 40 00
02 05 40 02 89 00 00   ->  07 02 40 00
```

The full sequence — prerequisites, geometry, FPGA settings, A/D config and
control word 0x163 — now runs end to end with every packet accepted, and EP
0x86 is still unchanged. Whatever starts the sensor clock is not in
`FN_bDrvInitCcd`.

Next: `FN_bDrvCcdAcquireAndDxStart` (enum 333, `fcn.10029b80`) and
`FN_bDrvReadScanLine` (enum 130). InitCcd only configures; those two are what
the scan loop calls per line, and `EC_DRV_CannotFindStartOfScanLine` implies
the data carries a line-start marker to synchronise on.

## The motor board is not answering — root cause

A read-register sweep across board addresses shows the problem that every
other experiment was downstream of:

```
board  response to Type 1 read
0x10   01 04 10 88 46 32     Type 1 -- real data (host / FX2)
0x40   01 04 40 88 22 00     Type 1 -- real data (light board)
0x44   07 02 44 01           Type 7, status 1
0x20   07 02 20 01           Type 7, status 1
0x28   07 02 28 01           Type 7, status 1
0x48   07 02 48 01           Type 7, status 1
```

Board 0x44 answers exactly like an address with nothing attached. Sweeping
registers 0x00-0x1f on 0x44 yields **zero** data responses; the same sweep on
0x40 returns data.

**Status byte 1 is an error.** Successful writes to the light board return
`07 02 40 00` -- status 0. Every CCD and FPGA register write in this project
goes to board 0x44 and comes back status 1, i.e. rejected. The tooling printed
"ok" merely because a response arrived; it never checked the status byte.

So the whole chain of reasoning about registers 0x82 and 0x84 was sound but
untestable: the board that owns those registers was never listening. Setting
the acquire bit, the geometry, the integration time and the edge-triggered
0->1 transition all wrote into a void.

This also explains the static three-level pattern on EP 0x86. With the motor
board silent the FPGA is never configured, so nothing clocks the sensor and
the endpoint emits whatever the FX2 has in its FIFO.

Note the motor board *did* work earlier in this project -- film transport at
three speeds plus reverse was confirmed by ear. So this is a change in the
unit's state, not a permanent absence.

Open question, and the next thing to establish: whether the PICM board needs
its firmware downloaded (Config/Firmware/nm0506.HEX for an F-135 Plus, per
ReadmeF135.txt, with FirmwareLoader.exe as the vendor's tool), or whether it
is held in reset until something enables it. Until 0x44 answers a read, no
amount of register programming can start a scan.

## Board firmware prefixes, from ReadmeF235/F335

`ReadmeF135.txt` documents only PICL and PICM, but the other model readmes
name the rest of the family:

| prefix | board |
|--------|-------|
| `PL` / `NL` | light board (PICL) |
| `PM` / `NM` | motor board (PICM) |
| `CE` / `CD` | **CCD board** |
| `DX` / `DY` | DX board |
| `LP` / `LQ` | LED / lamp board |
| `MC` / `MD` | motor board (F-335) |
| `AP` | APS board |

So a CCD board with its own PIC does exist in the family, consistent with the
version string reporting a CCD version for every model.

### Verified three ways, and not recoverable in software

The silence of 0x44 is not an artifact of the wrong register range or the
wrong packet type:

| test | 0x10 host | 0x40 light | 0x44 motor |
|------|-----------|------------|------------|
| read regs 0x00-0x1f | data | data | none |
| read regs 0x80-0xaf | -- | -- | none |
| Type 4 command 0x00 | status 0 | status 0 | **status 1** |

A basic Type 4 command is accepted by the host and the light board and
rejected by the motor board, so the board is not answering at all rather than
lacking a particular register.

A USB-level `reset()` does not help, and firmware survives it -- the loader
reports "already loaded; power-cycle it to reload firmware". So restoring the
motor board needs a physical power cycle at minimum; it cannot be done from
the host.

### Reading the status byte

For future tooling: byte 3 of a Type 7 response is the status, and it is not
optional to check.

```
07 02 40 00     status 0   accepted
07 02 44 01     status 1   rejected
07 02 40 02     status 2   unsupported packet type
```

Byte 3 of a Type 1 data response carries flags, where `0x20` is the fault bit
(the same bit `clear_fault` polls). Host registers 0x0a-0x1f all return
`01 04 10 20 00 00`, i.e. fault -- those registers do not exist. Only the low
host registers are real.

### Full board discovery — only two boards are alive

Sweeping every address 0x00-0xff with a Type 1 read finds five responders, but
a repeatability test separates real boards from a floating bus. Reading the
same register five times:

```
0x10 reg 0x00: 0300 0300 0300 0300 0300   STABLE   host / FX2
0x40 reg 0x00: 0000 0000 0000 0000 0000   STABLE   light board
0x46 reg 0x00: c7cf c483 c481 c6b5 c71f   VARIES   noise
0x47 reg 0x00: 0be3 ea6e e96e ff0a 1508   VARIES   noise
0x41           same value for every register       alias/echo
```

0x41, 0x46 and 0x47 are pickup on unterminated addresses, not boards. **The
only live boards are the host at 0x10 and the light board at 0x40.**

The motor/main board is absent from the bus entirely. That board hosts:

- the motor and film transport
- CCD registers 0x84 (A/D gains, offsets, mode)
- FPGA registers 0x82 (geometry, integration time, acquire control)

which is why none of the acquisition work could take effect, and why EP 0x86
emits a static pattern. It is not a missing register sequence and never was.

Note the board address is not a constant: the driver reads it from the device
object at `[esi+0x130]`, populated from device info. This project assumed 0x44
throughout, and on a healthy unit that is presumably right -- film transport
worked earlier via 0x44 -- but the address should be discovered, not assumed.

This cannot be repaired from the host. A USB reset does not help and firmware
survives it. Next steps require the physical unit: a power cycle, confirmation
of whether the motor still runs, and the LED state.

## Confirmed with the vendor's own discovery routine

`FN_bDrvFindPicController` (enum 92, `fcn.10008ba0`) builds:

```asm
mov byte [var_10h], 4      ; Type 4, command
mov byte [var_11h], 3      ; PktLen
mov byte [var_12h], cl     ; board address
mov byte [var_13h], 0
mov byte [var_14h], 0      ; command 0x00
mov edi, 2                 ; two attempts
call fcn.10008530
```

which is `04 03 <addr> 00 00` — byte for byte the probe used here. The vendor
discovers PIC boards with exactly this packet, and board 0x44 fails it after a
clean power cycle with the physical connections confirmed intact.

TLB.dll carries a dedicated error for this state: **`EC_PicM_NotFound`**
(enum 236). There is also `EC_PicF_NotFound`, `FN_bPicToBootLoaderState`,
`FN_bLoadPic`, `FN_bVerifyPic`, and a built-in self-test suite for the PICM
power rails:

```
EC_BistPicmVinFail   EC_BistPicm13VFail  EC_BistPicm12VFail
EC_BistPicm6VFail    EC_BistPicm5VFail   EC_BistPicm3VFail
EC_BistPicmMotorFail EC_BistPiclMotherBdFpgaCommFail
```

So the real Windows driver, run against this unit as it stands, would report
`EC_PicM_NotFound`. This is not a porting gap.

## State of the machine

| subsystem | state |
|-----------|-------|
| USB / FX2 (0x10) | working — enumerates, stable register reads |
| light board (0x40) | **fully working** — every command status 0, lamp lights bright blue, operator-confirmed |
| main board / PICM (0x44) | **not on the bus** — fails the vendor's own discovery |
| boot EEPROM | damaged earlier in this project; needs `--hex` to load |

The light board being perfect isolates the fault cleanly. Both boards share the
same I²C bus and the same master, so a bus or firmware-side explanation does
not survive: two devices answer and one does not.

The existence of PICM power-rail BIST codes suggests supply rails to that board
are worth checking, since a rail failure would produce exactly this signature.

## Correction: what the status byte actually means

Status 0 on a write means only that **a device ACKed the I2C transaction at
that address**. It does not mean the register was valid. The known-good light
board accepts nonsense registers exactly as readily as real ones:

```
board 0x40  reg 0x80 (valid lamp) : status 0
board 0x40  reg 0x99 (nonsense)   : status 0
board 0x40  reg 0xf0 (nonsense)   : status 0
board 0x46  reg 0x82 (valid FPGA) : status 0
board 0x46  reg 0x99 (nonsense)   : status 0
```

So "16/16 config writes accepted on 0x46" is not evidence that 0x46 is the
main board. It is evidence that *something* ACKs there.

What survives:

- nothing ACKs at 0x44 (7-bit 0x22)
- something ACKs at 0x46/0x47 (7-bit 0x23), 0x40/0x41 (0x20), and
  0xa2-0xa5 (0x51, 0x52)
- reads from 0x46 are unstable, which does not fit a healthy board

The board address is read from device info at `[esi+0x130]`, not hardcoded, so
0x44 was always an assumption inherited from the emulator setup in this
project. Whether the main board is at 0x46 or simply absent is still open.

## EP 0x86 changes character across power cycles

Three different idle patterns have now been observed on the same endpoint:

```
mean 1240      before one power cycle
593/608/740    three-level interleave, after the next
65534 (0xFFFE) after the most recent
```

A sensor readout would not change because the host power-cycled. This is
further evidence the endpoint is emitting FX2-side filler rather than data.

## EEPROM: still no valid backup

Do not trust any dump taken so far. See ~/pakon-eeprom-backup, where both
attempts are quarantined with READMEs. Nothing has been written to any EEPROM.
