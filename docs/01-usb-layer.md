# 01 — USB Layer

## Enumeration states

A Pakon scanner presents **three different identities** over its lifetime. This
is the single most confusing thing about the device and the first thing a driver
must handle.

```
   power on
      │
      ▼
 ┌─────────────────────┐   no EEPROM on USB board
 │ 04B4:8613  Cypress  │───────────────────────────┐
 │ 0547:1002  Anchor   │                           │
 └─────────────────────┘                           │
      │ EEPROM present                             │
      ▼                                            │
 ┌─────────────────────┐                           │
 │ 0F05:F235 REV_AAxx  │  "unloaded" — identifies  │
 │ (xx = 05/07/08)     │   which model it is       │
 └─────────────────────┘                           │
      │                                            │
      │  host downloads matching Intel HEX ◄───────┘
      │  into 8051 RAM, releases reset
      ▼
 ┌─────────────────────┐
 │  RE-ENUMERATES as   │  ← the "loaded" identity; this is the
 │  0F05:F135 REV_0002 │    only state that can actually scan
 └─────────────────────┘
```

## VID/PID table — [VERIFIED] from `F235usb2.inf`

### Unloaded (needs firmware download)

| VID:PID | REV | Meaning | Firmware to load |
|---|---|---|---|
| `04B4:8613` | any | Bare Cypress EZ-USB FX2, EEPROM not loaded | `PknInit.hex` |
| `0547:1002` | — | Bare Anchor EZ-USB, EEPROM not loaded | `PknInit.hex` |
| `0F05:F235` | `AA05` | Pakon USB board, model tag 5 | `Pakon5.hex` |
| `0F05:F235` | `AA07` | Pakon USB board, model tag 7 | `Pakon7.hex` |
| `0F05:F235` | `AA08` | Pakon USB board, model tag 8 | `Pakon8.hex` |
| `4705:0211` | `0000` | Development board, unloaded | `PknInit.hex` |

The INF also lists each `AAxx` with an alternate spelling `::xx` (`REV_::05`
etc.). `0x3A3A` vs `0x4141` — two EEPROM content variants in the field.

### Loaded (ready to scan)

| VID:PID | REV | Model | Driver | USB product string |
|---|---|---|---|---|
| `0F05:F135` | `0002` | **F-135 / F-135 Plus** | `F135usb2.sys` | `F135-USB Film Scanner` |
| `0F05:35F2` | `0001`, `0002` | F-235 | `F235usb2.sys` | `F235-USB Film Scanner` |
| `0F05:F335` | `0002` | F-235 / F-335 | `FX35usb2.sys` | `FX35-USB Film Scanner` |

> **F-135 Plus note:** the Plus shares `0F05:F135` with the base F-135. The
> variant is *not* distinguishable from the USB IDs — it is identified later,
> from the loaded PIC firmware set (`NL*`/`NM*` = Plus, `PL*`/`PM*` = base) and
> from `SCANNER_TYPE_F_135_PLUS` reported through the API. See
> [`02-firmware.md`](02-firmware.md).

### Firmware→identity mapping — [VERIFIED]

Extracted by parsing the USB device descriptor embedded at offset `0x1000` in
each HEX image (`tools/pakon_hex.py --descriptors`):

| HEX file | Becomes | Product string |
|---|---|---|
| `PknInit.hex` | `0F05:35F2` rev `0002` | `F235-USB Film Scanner` |
| `Pakon5.hex` | `0F05:35F2` rev `0002` | `F235-USB Film Scanner` |
| `Pakon7.hex` | **`0F05:F135` rev `0002`** | **`F135-USB Film Scanner`** |
| `Pakon8.hex` | `0F05:F335` rev `0002` | `FX35-USB Film Scanner` |

All four report iManufacturer `Pakon` and iSerialNumber `010-203-04`.

**For an F-135 / F-135 Plus, the file you need is `Pakon7.hex`.**

## Endpoint map — [VERIFIED]

Extracted by scanning each HEX image for `07 05` endpoint-descriptor signatures.
Identical across all four firmware images — the endpoint layout does not vary by
model:

| Endpoint | Dir | Type | Max packet (FS) | Max packet (HS) | Purpose |
|---|---|---|---|---|---|
| `0x01` | OUT | Bulk | 64 | 512 | **Command packets** to scanner |
| `0x81` | IN | Bulk | 64 | 512 | **Response packets** from scanner |
| `0x86` | IN | Bulk | — | 512 | **Scan image data stream** |

Each image contains two descriptor sets — one full-speed (64-byte), one
high-speed (512-byte) — as required for a USB 2.0 device. On any modern Mac the
device will negotiate high speed, so **512-byte max packet applies**.

This independently confirms the "3 endpoints" observation in Kaufman's
write-up **[EXTERNAL]**, and assigns purposes to them:

- EP1 is a matched OUT/IN command pair — a request/response channel.
- EP6 IN is a lone high-bandwidth inbound stream — necessarily the pixel data.
  The `EC_DRV_FifoOverflow`, `EC_DRV_RingTailOverflow` and
  `EC_DRV_CannotFindStartOfScanLine` error codes in the API all describe a
  free-running stream that the host must drain fast enough. **[INFERRED]**

## Configuration and interface

`F135usb2.sys` selects a configuration and interface **by name**, per its log
strings — meaning it reads the string descriptors rather than hardcoding index
0. A macOS implementation can simply select configuration 1, interface 0, since
each image declares `bNumConfigurations = 1`. **[VERIFIED]**

## macOS specifics

- **No kernel extension required.** The device declares a vendor-specific
  interface class; macOS has no matching class driver, so nothing needs to be
  unloaded or overridden before claiming it.
- **No code signing / Reduced Security required**, unlike a DriverKit or kext
  approach.
- libusb (`brew install libusb`) can claim the interface directly.
- The device re-enumerates mid-session after firmware download. The driver must
  release its handle, wait for the new device to appear (typically 1–3 s), and
  re-open by the *loaded* VID/PID. Do not assume the same device address.

## Open questions — [UNKNOWN]

- Whether EP6 requires an explicit "start streaming" command on EP1, or begins
  producing as soon as a scan is commanded.
- Whether any alternate interface settings exist with different EP6 bandwidth.
- Whether the device needs `SET_INTERFACE` before EP6 becomes live.

All three are answerable in minutes with the hardware attached.
