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

## Progress on the flash protocol (incomplete)

`FN_bLoadPicLarge` = `fcn.1001bb10`. It sends through
`FN_bFirmwarePutProgramData` = `fcn.10008ee0` (enum 162), which builds a packet
and hands it to `fcn.10008e30`, which fills in the Type and PktLen bytes before
calling the usual `fcn.10008530` transport.

Layout recovered so far, relative to the buffer base:

```
base+0   Type            written by fcn.10008e30
base+1   PktLen          written by fcn.10008e30
base+2   board address
base+3..5   not yet identified
base+6   arg2
base+7   data length     (the memcpy count)
base+8   arg3
base+9.. program data    rep movsd/movsb from the caller's buffer
```

`FN_bLoadPicLarge` itself shifts a 24-bit value (`shr eax, 0x10`, `shr ecx, 8`)
into separate bytes before the call, which is the flash address being split
into high/mid/low. It also sleeps 1 ms between packets and re-reads for
verification.

Related entry points, all in TLB.dll:

| enum | name | address |
|-----:|------|---------|
| 159 | `FN_bFirmwareGetByteArrayNL` | — |
| 160 | `FN_bFirmwareGetProgramWord` | — |
| 161 | `FN_bFirmwareGetProgramWords8` | — |
| 162 | `FN_bFirmwarePutProgramData` | `fcn.10008ee0` |
| 163 | `FN_bFirmwarePutProgramWord` | — |
| 164 | `FN_bFirmwareWritePacketNL` | — |
| 245 | `FN_bPicToBootLoaderState` | `fcn.1001b9b0` |
| — | `FN_bLoadPicLarge` | `fcn.1001bb10` |
| — | `FN_bUpdate` | `fcn.1001c3e0` |

**Not yet determined**, and all of it is required before writing anything:

- the meaning of header bytes 2..5 and 8
- the flash address encoding and page/row size
- whether an erase must precede a write, and its command
- the verify sequence (`FN_bVerifyPicLarge`) and what a failure looks like
- what happens if a write is interrupted mid-flash

**Do not send anything to 0x46 until these are known.** The PICM is currently
in a clean, recoverable bootloader state. A partially-understood flash write is
the one action that could turn a recoverable board into a dead one, and this
project has already twice demonstrated what improvising a protocol costs.

## The flash protocol reuses the ordinary packet format

`FN_bFirmwareWritePacketNL` (enum 164, `fcn.10008e30`) is the last stop before
the transport, and it shows the flash path is not a separate protocol:

```asm
mov al, byte [esi + 3]     ; dataLen, already placed in the buffer
test al, al
sete cl                    ; cl = 1 when dataLen == 0
add al, 3
mov byte [esi + 1], al     ; PktLen = dataLen + 3
lea ecx, [ecx + ecx + 2]   ; ecx = 4 when dataLen == 0, else 2
mov byte [esi], cl         ; Type
call fcn.10008530          ; the usual transport
```

So flashing uses the same family already decoded here:

```
data packet:     02 <dataLen+3> <board> <dataLen> <cmd> <data...>
command packet:  04 3            <board> 0         <cmd>
```

`PktLen = dataLen + 3` is the same rule confirmed earlier for
`PutRegisterCcd` and `PutRegisterWord`. This is a large simplification: no new
transport is needed, only the bootloader's command codes and its address
encoding.

`FN_bLoadPicLarge` splits a 24-bit flash address into bytes (`shr eax, 0x10`,
`shr ecx, 8`) inside its own buffer before calling
`FN_bFirmwarePutProgramData`, so the address travels as part of the payload
rather than in the header.

Still required before any write: the specific command codes for
enter-bootloader / erase / write / verify, the page or row size, and the
behaviour on an interrupted write.

## Bootloader commands recovered

`FN_bLoadPicLarge` (enum 238, `fcn.1001bb10`) makes two calls to
`FN_bFirmwarePutProgramData` (enum 162, `fcn.10008ee0`), whose signature is:

```
PutProgramData(ctx, board, command, dataPtr, dataLen)
   arg2 = board       [esp+0x2c] at entry
   arg3 = command     [esp+0x30]
   arg4 = dataPtr     [esp+0x40] after three pushes
   arg5 = dataLen     [esp+0x3c] after one push
```

### Command 4 — set address

```asm
mov byte [esp + 0x58], al      ; S+0x58  address bits 0..7
shr eax, 0x10
push edx                       ; edx = &S+0x58
mov byte [esp + 0x5e], al      ; S+0x5a  address bits 16..23
push 4                         ; command
shr ecx, 8
push eax                       ; board
mov byte [esp + 0x65], cl      ; S+0x59  address bits 8..15
```

Accounting for the intervening pushes, the three stores land on **consecutive**
bytes S+0x58, S+0x59, S+0x5a, low byte first. So:

```
command 4, dataLen 3, payload = 24-bit flash address, little-endian
```

### Command 2 — write program data

```
command 2, dataLen 0x13 (19), payload built byte-by-byte before the call
```

The 19 bytes are assembled from a run of `mov byte [var_XX], cl/ch` stores,
consistent with 16 bytes of program data plus a 3-byte address or count.

### Register 0x0a — bootloader command register

`FN_bPicToBootLoaderState` (enum 245, `fcn.1001b9b0`) writes register `0x0a`
with a 2-byte payload whose second byte is `0x55`, then sleeps 100 ms:

```asm
push 0 ; push 2          ; dataLen 2
push eax                 ; data
push 0xa                 ; register 0x0a
push ebx                 ; board
mov byte [arg_14h], 0    ; data[0] = 0
mov byte [arg_41h], 0x55 ; 0x55 magic
call fcn.10009ae0
...
push 0x64                ; Sleep(100)
cmp bl, 0x24             ; board 0x24 is special-cased
```

This unit's PICM is already in the bootloader, so the entry command is not
needed for recovery -- only the flash commands.

### Still missing before any write

- what command 2's 19-byte payload contains exactly, field by field
- whether an erase command exists and must precede writing
- the verify path (`FN_bVerifyPicLarge`) and how failure is reported
- the row/page size and whether addresses must be aligned
- the behaviour if a write is interrupted

## All PutProgramData call sites

`fcn.10008ee0` has exactly five callers:

| site | function | command | dataLen |
|------|----------|--------:|--------:|
| `0x1001bbd7` | `FN_bLoadPicLarge` | 4 | 3 |
| `0x1001bd31` | `FN_bLoadPicLarge` | 2 | 19 |
| `0x1001bf4b` | `fcn.1001bdf0` (verify path) | 2 | 3 |
| `0x1001bfb7` | `fcn.1001bdf0` | 2 | 19 |
| `0x1001cba7` | `FN_bUpdate` (`fcn.1001c3e0`) | 8 | — |

So the bootloader command set in use is **{2, 4, 8}**:

- **4** — set address. Payload is a 24-bit little-endian address, confirmed by
  the three consecutive byte stores after accounting for intervening pushes.
- **2** — the bulk command, used with both 3-byte and 19-byte payloads, in the
  write path and the verify path alike.
- **8** — issued once from `FN_bUpdate`; semantics not yet established.

`fcn.1001bdf0` splits an address the same way (`shr edx, 0x10`, stores at
`+0x54` and `+0x56`), which fits a read-back-and-compare verify.

**Open question that matters most:** command 2 appears with two different
payload lengths, so either the length disambiguates it or a mode byte inside
the payload does. Writing a 19-byte command 2 without knowing which would be
guessing, and this is the one command that modifies flash.

## Status of the port

Decoded and confident:

- the transport (ordinary packet family, `PktLen = dataLen + 3`)
- `PutProgramData` argument order
- command 4 as a 24-bit little-endian set-address
- register `0x0a` as the bootloader command register, magic `0x55`
- the PICM is in its bootloader at 0x46, proven with control addresses

Not yet safe to act on:

- command 2's payload layout, field by field
- command 8's meaning
- erase semantics, row alignment, and interrupted-write behaviour
- the verify comparison and its failure reporting
