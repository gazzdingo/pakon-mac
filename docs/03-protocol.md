# 03 — Command Protocol

> **Confidence warning.** This is the least-verified document in the set. The
> framing below comes from Kaufman's write-up **[EXTERNAL]** and has *not* been
> confirmed against hardware or independently re-derived from `tlx.dll` here.
> Everything corroborated locally is tagged. Treat the rest as a strong starting
> hypothesis, not fact.

## Transport

Command packets travel over the bulk endpoint pair on interface 0:

```
  host ──── EP 0x01 OUT (bulk, 512 B) ────► scanner     command
  host ◄─── EP 0x81 IN  (bulk, 512 B) ──── scanner     response
  host ◄─── EP 0x86 IN  (bulk, 512 B) ──── scanner     image stream
```

On Windows this is wrapped in `DeviceIoControl` with control code **`0x222090`**
**[EXTERNAL]**. That wrapper disappears entirely on macOS — libusb bulk
transfers go straight to the endpoints.

Three further IOCTL codes were recovered locally from `F135usb2.sys` by scanning
for the `FILE_DEVICE_UNKNOWN` control-code pattern: **`0x222014`, `0x22205C`,
`0x22206D`** — [INFERRED], candidates only, purpose unknown. They are likely
reset / abort-pipe / stream-control operations. They matter only for
interpreting a Windows capture, not for the macOS implementation.

## Packet format — [EXTERNAL]

```
  offset  size  field
  ──────────────────────────────────────────────────────
    0       1   packet type      (enum)
    1       1   data length      (count of bytes following)
    2..     n   packet data      (up to 34 bytes)
                 ├─ [0]  destination address
                 └─ [1..] address-specific payload
```

Maximum ~36 bytes total. This comfortably fits a single 512-byte bulk
transfer, so **no fragmentation is needed on the command channel** — one packet
per transfer. [INFERRED]

A checksum is present somewhere in the packet: the API exposes both
`EC_DRV_PacketChecksumErr` and `EC_DRV_PacketHostErrorCkSum`, and status code
`3` means "invalid checksum". Its position and algorithm are **[UNKNOWN]** —
almost certainly a trailing 8-bit sum or XOR over the packet body, but this must
be determined before a single valid packet can be sent.

**This is the #1 blocking unknown for the entire project.**

## Address enum — [EXTERNAL], partially corroborated locally

| Value | Name | Board |
|---|---|---|
| `0x10` | `AD_HOST` | the host itself (responses) |
| `0x20` | `AD_PICL` | PICL — light board controller |
| `0x24` | `AD_PICM` | PICM — motor controller — **[INFERRED]** |
| `0x40` | `AD_PICL_PLUS` | PICL Plus — **F-135 Plus** light controller |
| `0x44` | `AD_PICM_PLUS` | PICM Plus — **F-135 Plus** motor controller |
| — | boot variants | separate addresses for bootloader mode |

### Local corroboration

The firmware distribution's `ReadmeF135.txt` documents four PIC firmware
families — `PL` (PICL), `PM` (PICM), `NL` (PICL **Plus**), `NM` (PICM **Plus**)
— matching the enum's four board addresses and, critically, matching *which two
are the `_PLUS` variants*. Two independent sources agreeing on an unusual
four-way split is meaningful. **[VERIFIED corroboration of an EXTERNAL claim]**

**For an F-135 Plus, the relevant addresses are `0x40` and `0x44`,** not `0x20`
and `0x24`.

The spacing (`0x20`/`0x24`, `0x40`/`0x44`) suggests the low nibble encodes a
sub-function or bootloader/application selector — e.g. `0x2n` = PICL family
where `n` selects boot vs. app. **[INFERRED, untested]**

## Status codes — [EXTERNAL]

Returned in **response byte 4**:

| Code | Meaning |
|---|---|
| `0`, `8` | Success |
| `1` | Packet not acknowledged |
| `2` | Invalid packet |
| `3` | Invalid checksum |
| `4`–`6` | USB-related error |
| `9` | Bus error |

### Cross-check against the API error enum — [VERIFIED]

The driver-level error codes recovered from `Interop.TLXLib.dll` map onto these
almost one-to-one, which is good evidence the enum is real:

| Status | Matching `EC_DRV_*` code |
|---|---|
| `1` | `EC_DRV_PacketHostErrorNoAck` |
| `2` | `EC_DRV_InvalidPacketType`, `EC_DRV_PacketHostErrorFormat` |
| `3` | `EC_DRV_PacketChecksumErr`, `EC_DRV_PacketHostErrorCkSum` |
| `4`–`6` | `EC_DRV_PacketHostErrorEndPointFormat`, `…EndPointLength`, `…EndPointTimeOut` |
| `9` | `EC_DRV_PacketHostErrorBus` |

Additional driver errors with no status-code counterpart — these describe the
**stream** path rather than the command path:

```
EC_DRV_CannotFindStartOfScanLine    EC_DRV_LostSync
EC_DRV_FifoOverflow                 EC_DRV_RingTailOverflow
EC_DRV_TransferInProgress           EC_DRV_PacketBusy
EC_DRV_PacketOverFlowErr            EC_DRV_PacketReadWriteMismatch
EC_DRV_PacketCommErr                EC_DRV_PacketCmdErr
EC_DRV_PacketHostErrorAlgo          EC_DRV_PacketHostErrorUndefined
EC_DRV_ProcessedRingTailOverflow
```

## The image stream (EP 0x86) — [INFERRED]

No direct documentation exists, but the API's buffer-management parameters
describe the mechanism precisely. From `Interop.TLXLib.dll` **[VERIFIED]**:

```
i_uiRingTailDriverBytes        i_uiRingTailProcessedBytes
i_uiDriverTriggerBytes         i_uiProcessedTriggerBytes
i_uiScanPacketReadyTimeOut     i_uiNoFilmTimeOut
i_pByteStartPointer            i_pByteStartPointerHeader
i_pByteStartPointerOptical     i_pByteStartPointerMag
iByteCount / iByteCountHeader / iByteCountOptical / iByteCountMag
```

This is a **ring buffer with a trigger watermark**: the driver fills a ring from
EP6, and signals the client once `DriverTriggerBytes` have accumulated. The
`RingTail*Overflow` errors fire when the consumer falls behind the producer.

The four `pByteStartPointer*` / `iByteCount*` pairs indicate a scan line is
delivered as **four parallel data streams**:

| Stream | Content |
|---|---|
| `Header` | per-line metadata |
| `Optical` | the image pixels |
| `Mag` | APS magnetic track data |
| (base) | the combined/whole buffer |

`EC_DRV_CannotFindStartOfScanLine` and `EC_DRV_LostSync` imply the stream
carries **a sync marker at the start of each line** that the host must search
for — the stream is free-running and not self-framing at the USB transfer level.
Finding that marker pattern is the second major unknown.

`iScanLines` and the `FRAME_SIZES_*` constants give expected geometry:
`FRAME_SIZES_HR_WIDTH_BASE8_35_135`, `..._LR_HEIGHT_BASE8_35_135` etc. — the
`_135` suffix marks F-135-specific dimensions. Their numeric values are in the
`Interop.TLXLib.dll` metadata blob and can be recovered with a proper .NET
metadata reader.

## What must be determined next

Ordered by how much they block:

1. **Checksum algorithm and position.** Nothing can be sent without it.
2. **Packet type enum values.** Which byte-0 values mean read-version,
   set-lamp, move-motor, start-scan.
3. **Scan-line sync marker** on EP6.
4. Whether EP6 needs an explicit start command.
5. Pixel format on EP6 — bit depth, channel interleave, byte order.

Items 1–3 fall out immediately from a single USB capture of the Windows software
performing an init and one scan. Without a capture they require disassembling
`tlx.dll` (294 KB, x86 PE) — feasible, but a different order of effort. See
[`06-roadmap.md`](06-roadmap.md).
