# 03 — Command Protocol

Most of this document is now **[VERIFIED]** — confirmed either by disassembling
`TLB.dll` (the F-135 client library) or by exchanging real packets with a real
F-135 Plus over libusb on macOS. Where something is still a guess it says so.

> **Semantics live in [`12-command-protocol.md`](12-command-protocol.md).** This
> file covers the transport and framing. Doc 12 decodes what the packets *mean*
> — the per-board register and command maps, and the exact byte layouts for
> lamp, motor, scan and identity — with the `TLB.dll` evidence for each.
> Builders for all of it: [`../tools/pakon_commands.py`](../tools/pakon_commands.py).

## Transport — [VERIFIED]

Command packets travel over the bulk endpoint pair on interface 0:

```
  host ──── EP 0x01 OUT (bulk, 512 B) ────► scanner     command
  host ◄─── EP 0x81 IN  (bulk, 512 B) ──── scanner     response
  host ◄─── EP 0x86 IN  (bulk, 512 B) ──── scanner     image stream
```

On Windows this is wrapped in `DeviceIoControl` with control code `0x222090`
(`IOCTL_PAKON_SEND_AND_RECEIVE_PACKET`). From the driver source, that IOCTL is
*literally* a bulk write followed by a bulk read:

```c
case IOCTL_PAKON_SEND_AND_RECEIVE_PACKET:
    Ezusb_Read_Write_Direct(fdo, Irp, FALSE);   // write to EP1 OUT
    Ezusb_Read_Write_Direct(fdo, Irp, TRUE);    // read from EP 0x81
```

So on macOS the wrapper disappears entirely — two libusb calls. Transfers are
capped at `0x200` bytes by the driver.

Other IOCTLs, all confirmed against `ezusb.h` static asserts:

| Code | Name |
|---|---|
| `0x222014` | `IOCTL_Ezusb_VENDOR_REQUEST` |
| `0x22205C` | `IOCTL_EZUSB_GET_LAST_ERROR` |
| `0x22206D` | `IOCTL_EZUSB_ANCHOR_DOWNLOAD` |
| `0x222088` | `IOCTL_PAKON_READ_DIRECT` |
| `0x22208C` | `IOCTL_PAKON_WRITE_DIRECT` |
| `0x222090` | `IOCTL_PAKON_SEND_AND_RECEIVE_PACKET` |

Windows device path: `\\.\Pakon135` (also `\\.\PakonX35`, `\\.\Loopback`).

## Packet format — [VERIFIED]

`TLB.dll` carries its own format string, which settles the layout beyond doubt:

```
"Type %x, PktLen %x, Address %x"
    movzx ecx, byte [ebx]        ; Type    = buf[0]
    movzx eax, byte [ebx + 1]    ; PktLen  = buf[1]
    movzx edx, byte [ebx + 2]    ; Address = buf[2]
```

```
  offset  size  field
  ────────────────────────────────────────────────
    0       1   Type
    1       1   PktLen    -- number of bytes following
    2       1   Address   -- destination board (first payload byte)
    3..     n   payload
```

**Wire size = PktLen + 2**, taken from the call site (`add edx, 2` feeding
`nInBufferSize`). The response buffer is **64 bytes** (`nOutBufferSize = 0x40`).

> **The host computes no checksum.** Earlier accounts (including an earlier
> draft of this document) assumed the host had to build one because the error
> enum contains `EC_DRV_PacketChecksumErr`. It does not — no checksum appears
> anywhere in the host packet construction. Framing and checksums are added
> below the host, by the FX2 firmware and the PIC link layer.

## Packet types — [VERIFIED]

Recovered by cataloguing every builder that calls the send/receive wrapper
(`TLB.dll` `fcn.10008530`), then confirmed on hardware:

| Type | Meaning | Evidence |
|---|---|---|
| 1 | **Read** n+1 bytes from a register | builders + hardware |
| 2 | **Write** n bytes to a register | builder `fcn.10008f80` + hardware |
| 3 | Query (`AD_HOST` handled locally by the FX2) | builder `fcn.10008d70` |
| 4 | Ping / presence check | builder `fcn.10008ba0` |
| 7 | **Response** | `resp[0] == 7` check in `TLB.dll` |

> ⚠️ **Type 0 is emitted by no builder and must never be sent.** It wedges the
> firmware permanently: the device stops draining EP 0x01 OUT and stays wedged
> across USB resets, because the firmware lives in RAM and a USB reset does not
> restart it. Only a scanner power cycle clears it. This was learned the hard
> way. An invalid *payload* is harmless (status 2); an invalid *Type* is not.

### Observed forms

```
Type 3   03 01 <addr>                                   query
Type 4   04 03 <addr> 00 00                             ping  (payload must be 00 00)
Type 1   01 03 <addr> <n> <reg>                         read  -> returns n+1 bytes
Type 2   02 <3+n> <addr> <n> <reg> <n data bytes>       write
```

The Type 2 layout was decoded from stack offsets in `fcn.10008f80`, which
writes a 24-bit little-endian value as `02 06 <addr> 03 01 <v0> <v1> <v2>`.

## Address enum — [VERIFIED on hardware]

| Value | Name | Board | This unit (F-135 Plus) |
|---|---|---|---|
| `0x10` | `AD_HOST` | the FX2 itself | responds locally |
| `0x20` | `AD_PICL` | light controller | **no-ack** |
| `0x24` | `AD_PICM` | motor controller | **no-ack** |
| `0x40` | `AD_PICL_PLUS` | Plus light controller | **responds** |
| `0x44` | `AD_PICM_PLUS` | Plus motor controller | **responds** |

A full 0x00–0xFF sweep found **only these** — every other address returns bus
error. That `0x20`/`0x24` no-ack while `0x40`/`0x44` answer is an independent
hardware confirmation that this is a **Plus** unit, matching the `NL*`/`NM*`
firmware families in `ReadmeF135.txt`.

## Status codes — [VERIFIED]

Returned in **response byte 3** (not byte 4 as previously recorded):

| Code | Meaning | Seen |
|---|---|---|
| `0`, `8` | Success | ✅ |
| `1` | Not acknowledged | ✅ (base PICL/PICM on a Plus) |
| `2` | Invalid packet | ✅ (bad payload — recoverable) |
| `3` | Invalid checksum | — |
| `4`–`6` | USB-related error | — |
| `9` | Bus error | ✅ (unpopulated addresses) |

`TLB.dll` treats `resp[0] == 7 && resp[3] == 0` as success and retries twice.

## Real exchanges

Captured on an F-135 Plus, macOS 26.5, libusb:

```
-> 03 01 10                  <- 03 04 10 08 aa aa    AD_HOST, local handler
-> 04 03 40 00 00            <- 07 02 40 00          PICL_PLUS ping: SUCCESS
-> 04 03 44 00 00            <- 07 02 44 00          PICM_PLUS ping: SUCCESS
-> 04 03 20 00 00            <- 07 02 20 01          no-ack (not fitted)
-> 01 03 40 00 00            <- 01 02 40 88          read 1 byte
-> 01 03 40 03 00            <- 01 05 40 88 00 80 01 read 4 bytes
-> 02 06 40 03 01 00 00 00   <- 07 02 40 00          write: SUCCESS
```

### Motor board register map — [VERIFIED, meaning UNKNOWN]

`01 03 44 01 <reg>` across `reg` 0x00–0x1F:

```
00:0800  01:09    02:0800  03:0800  04:2800  05:2800  06:0800  07:0800
08:2981  09:3b81  0a:3b81  0b:3b81  0c:3b81  0d:3b81  0e:3b81  0f:3b81
10:0800  11:08b8  12:28b8  13:28b8  14:28b8  15:28b8  16:28b8  17:28b8
18:28b8  19:28b8  1a:28b8  1b:28b8  1c:28b8  1d:28b8  1e:28b8  1f:28b8
```

The light board exposes only registers 0 and 1; all others error.

## The image stream (EP 0x86) — [VERIFIED]

**The CCD stream is free-running.** With the scanner idle and the lamp off,
EP 0x86 delivers data immediately at roughly **30 MB/s** — full USB 2.0 high
speed. No command is needed to start it.

Format, from a 1 MB capture: **3-channel interleaved 16-bit little-endian**.
Channel means 1169 / 1132 / 1445, full range 1080–1498 — dark-level sensor
noise, correct for an unilluminated CCD. Values are consistent with 14-bit data
(0–16383) sitting near black.

No line-sync marker was found in the dark-level capture (no `0x0000`/`0xFFFF`
words appear at all). `EC_DRV_CannotFindStartOfScanLine` and `EC_DRV_LostSync`
imply one exists during a real scan. **[UNKNOWN]**

Host-side buffering is a ring with a trigger watermark, fully specified by
`RING_TAIL` in the driver source (`ringtail.h`): `m_iNumPackets`,
`m_iMinimumPacketsForReady`, `m_bOverFlow`, and an event signalled once enough
packets accumulate.

## What is still unknown

1. **Lamp control.** No register write on either board changed illumination
   (verified by using EP 0x86 as a light meter against a dark baseline).
   `LampManualControl` in the API, plus `EC_LampWarmUpFailure` and
   `WTO_LampWarmUpProgress`, suggest a warm-up state machine rather than a
   single register poke.
2. **Film transport.** `AdvanceFilm`, `iAdvanceSpeed`, `iAdvanceMilliseconds`.
3. **Scan start**, and what makes EP 0x86 emit real image lines instead of the
   free-running dark data.
4. The meaning of the motor-board registers above.
5. The scan-line sync marker.

Items 1–3 are the only things standing between this project and a working scan.
