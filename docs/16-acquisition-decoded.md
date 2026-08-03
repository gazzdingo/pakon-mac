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
