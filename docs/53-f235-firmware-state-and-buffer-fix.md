# 53 — The scanner has F-235 firmware loaded and has not been power-cycled

**Date: 2026-08-13.** Finding from the Parallels/XP side while investigating two
initialisation failures in the vendor software. `[VERIFIED]` unless marked.

## Headline

**The F-135 is running F-235 firmware.** It enumerates as USB PID `0x35F2`,
which `tools/pakon_load.py` — this project's own FX2 loader — lists in its
`LOADED` table:

```python
LOADED = {
    (0x0F05, 0xF135): "F-135 / F-135 Plus",
    (0x0F05, 0x35F2): "F-235",
    (0x0F05, 0xF335): "F-235 / F-335",
}
def find_unloaded():   # bootloader identities
    (0x0F05, 0xF235), (0x04B4, 0x8613), (0x0547, 0x1002), (0x4705, 0x0211)
```

`0x35F2` is a **loaded-firmware** identity, not a bootloader one. Corroborated
by Kodak's own `vendor/FX35/FX35Package/F135.inf`, which binds
`USB\VID_0F05&PID_35F2` to `F235usb2` "Version 2".

The boot EEPROM is **not** implicated. Nothing needs repairing there.

## Why the bootloader identity never appears in today's log

```
07-23 (working):   36x  0f05|f235    then  28x  0f05|f135
08-13 (today):     51x  0f05|35f2    and nothing else
```

The scanner has **not been power-cycled since the F-235 firmware was loaded**.
Firmware lives in volatile FX2 RAM, so the device holds `0x35F2` indefinitely
until mains power is removed. `parallels.log` only observes the device while the
VM is running, so it has never witnessed the load event — which happened outside
that window, most plausibly during the 08-02 to 08-07 PICM/EEPROM work.

## Fix

**Power-cycle the scanner at the mains.** Not a USB re-plug — the FX2 must lose
power to drop its firmware and return to the `0x0F05:0xF235` bootloader identity.

Then load the correct firmware. This is doable entirely over USB from the Mac —
`tools/pakon_load.py` implements the FX2 download (`0xA0`/`0xA3`, CPUCS at
`0xE600`, with the AN2131 `MAX_INTERNAL_ADDRESS = 0x1B3F` split already handled),
and the F-135 images are in `vendor/FX35/FX35Package/F135/`.

Success is the two-stage sequence seen on 07-23/27/28: **`0f05:f235` first, then
`0f05:f135`** within ~20 s. Seeing `35f2` again after a mains cycle would mean
something is actively loading F-235 firmware, and *then* the loader config is
worth investigating.

## Corrections made while writing this document

Recorded because the reasoning matters more than the conclusion:

1. **First version:** "F-235 firmware is loaded" — from the `Enum\USB` driver
   bindings. **Correct**, but the supporting argument was weak: it leaned on
   `Pid_35f2` carrying a serial number, and those registry entries are undated
   historical records that cannot establish current state.
2. **Second version:** "the boot EEPROM PID field is byte-swapped" — wrong.
   Fitted to the absence of `0xF235` in today's log, without accounting for the
   simpler explanation that the device had not been power-cycled. `0x35F2` and
   `0xF235` being byte-reverses of each other is a coincidence, not a mechanism.
3. **This version:** settled by `tools/pakon_load.py`'s own `LOADED` /
   `find_unloaded` tables, which are direct project evidence rather than
   inference from logs.

## Supporting evidence

### Driver bindings

From `HKLM\SYSTEM\ControlSet001\Enum\USB`, read offline from the VM disk:

| PID | DeviceDesc | Service |
|---|---|---|
| `Vid_0f05&Pid_f235` | Pakon F135 USB 2.0 Scanner - F135 Motherboard | **`WDGTLDR`** (loader) |
| `Vid_0f05&Pid_f135` | Pakon **F135** USB 2.0 Scanner - Version 2 | `F135usb2` |
| `Vid_0f05&Pid_35f2` | Pakon **F235** USB 2.0 Scanner - Version 2 | `F235usb2` |

Note these entries are undated historical records — they show which driver
*would* bind to each identity, not what the device is doing now. The `LOADED`
table in `tools/pakon_load.py` is the authority for that.

### It explains both observed failures

* The vendor software binds `HKLM\SOFTWARE\Pakon\TLA\Scan` (`ScannerType 7`)
  rather than `TLB\Scan` (`ScannerType 1351`, serial 16275) — over USB the
  device genuinely *is* an F-235 right now.
* Initialisation then dies with
  `EC_DRV_PacketHostErrorNoAck (1011) Addr 0xF4, Cmd 0x03` inside
  `FN_bDrvGetDevInfo` → `CN_CiFirmware FN_bUpdate`. `0xF4` is not a valid board
  address on this unit — `docs/16`'s sweep found only `0x10` (host/FX2), `0x40`
  (light board), `0x44` (motor/main). F-235 firmware addressing F-135 hardware
  is a sufficient explanation. `[INFERRED]`

## Do NOT remove the F235 driver

Uninstalling `F235usb2` or deleting the `Pid_35f2` device does not help:

* `Pid_f235` → `WDGTLDR` is **required** — that is the bootloader binding the
  scanner needs to receive firmware at all. Removing it makes the unit
  unrecoverable from the host.
* Removing `F235usb2` only leaves the currently-enumerated device with no
  driver. Windows is behaving correctly given a device that is, at this moment,
  reporting itself as an F-235.

## Not the blocker: `UseF135 = 0`

`HKLM\SOFTWARE\Pakon\FirmwareLoader` has `UseF135 = 0` and `UseF335 = 0`, which
looks suspicious but is not the cause: the key has not been written since
**2017-04-19**, read identically in the 2026-08-06 snapshot, and was already `0`
throughout the working July sessions. Leave it alone unless a mains power-cycle
still yields `35f2`.

## Not the blocker: the EEPROM checksum warning

The same dialog shows
`CN_CiConfigMain FN_bReadEEPromData EC_EEPromWarningCheckSumBad (127)`. Real, but
non-fatal — verified from the binary:

* `fcn.10015d30` is a standard CRC-32 (reflected, table-driven, init
  `0xFFFFFFFF`, final `NOT` — zlib/PNG-compatible), 256-entry table in the
  config object.
* `FN_bReadEEPromToRegistry` (FN id 270, `fcn.10016a90`) checks two sections,
  **398 B** and **36 B**, each CRC'd from **offset 8**, so each has an 8-byte
  header (offset 0 is the length; offset 4 is presumably the stored CRC
  `[INFERRED]`).
* Status is a bitmask: **bit 1 = checksum bad** (logged 127), **bit 0 = blank**
  (logged 126). After logging bit 1 the code **falls through and continues** —
  no error return.

Motor values it reads are clamped to `[900, 1100]`, limiting the damage.
Verifying the CRC needs a **full dump** of the config EEPROM — the only capture
we hold (`eeprom_52.bin`, 256 B) is smaller than the 398-byte section.

## Related fix applied the same session

`TLA\Scan` had been auto-created with factory defaults `HiResPath = 'N:'` and
`HiResMegabytesTotal = 0`, failing as
`CN_CiBufferFileSystem FN_bSelectHardDriveP EC_WIN_FileOpen (167) … \\.\N:`.
Patched offline in the SOFTWARE hive to `'C:'` / `4800` to match `TLB\Scan`;
initialisation now gets past the buffer stage and reaches the firmware path.
Rollback bytes recorded. That key had **0 values** in the 2026-08-06 snapshot,
so those defaults were written within the last week — when the software first
bound to the F-235 identity.
