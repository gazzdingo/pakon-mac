# 06 — Status and Roadmap

## Where this stands

| Stage | Status |
|---|---|
| 1. Enumerate and load firmware | ✅ **working, automated** |
| 2. Command round-trip | ✅ **working** |
| 3. Read scanner identity | 🟡 partial — boards respond, registers not decoded |
| 4. Lamp on / motor move | ❌ **the blocker** |
| 5. Acquire raw scan lines | 🟡 stream works; needs illumination + film motion |
| 6. Full strip scan → file | ❌ |
| 7. Imaging pipeline | ✅ **implemented and verified** |

Stage 7 being done before stages 4–6 is unusual, but the colour work was
independent of hardware control and is the part users actually care about.

## What works, concretely

**Firmware loading** (`tools/pakon_load.py`) — reimplements the vendor's
two-stage EZ-USB sequence in userspace. Loads, re-enumerates as
`0f05:f135 "F135-USB Film Scanner"`, fully automated, no kext.

**Command channel** (`tools/pakon_cmd.py`) — packets go out on EP 0x01, Type 7
responses come back on EP 0x81. Both PIC boards answer.

**Image stream** — EP 0x86 delivers 3-channel 16-bit CCD data at ~30 MB/s
without any command. Verified against a 1 MB capture.

**Colour correction** (`tools/pakon_color.py`) — the density LUT
`-3500·log10(i/16383)` matches the vendor's shipped 16,384-entry table to within
**0.000050** across every entry. The 3×4 matrix and 12-bit RPD clamp are
implemented. Renders real scanner data to 16-bit TIFF.

**Profile handling** (`tools/pakon_profile.py`) — the `.pf` files are standard
ICC v2 (Kodak KCMS), so macOS ColorSync can consume them directly.

## The blocker

**Lamp control.** Everything else is in place; without illumination there is
nothing to scan.

What has been ruled out empirically, using EP 0x86 as a light meter against a
dark baseline of ~1245:

- every `Type 4` selector other than `00 00` (all rejected, status 2)
- `Type 2` writes to every accepted register on both boards, widths 1/2/4
- no write produced any change in illumination

What that suggests: lamp control is not a single register poke. The API implies
a sequence with its own state machine — `LampManualControl`,
`EC_LampWarmUpFailure`, `WTO_LampWarmUpProgress`, `FILM_COLOR_LAMP_OFF` /
`_LAMP_STANDBY`, plus separate LED and incandescent paths
(`CalibrationGetLightLED` / `CalibrationGetLightIncandescent`).

### How to resolve it

In order of expected value:

1. **Static decode of `TLB.dll`.** It is an ATL COM server, so the
   `IDispatchImpl` vtables and embedded typelib tie method names
   (`LampManualControl`, `AdvanceFilm`, `ScanPictures`) to functions, which can
   then be traced to the packet builders that call `fcn.10008530`. This is the
   reliable path and needs no hardware.
2. **A USB capture from working Windows software.** Would settle everything in
   minutes. Requires a physical x86 PC — not possible in a VM on Apple Silicon,
   because Windows-on-ARM cannot load the 32-bit x86 kernel driver.
3. Further empirical probing — **low value, real cost.** An invalid packet Type
   wedges the firmware until a physical power cycle, and blind register writes
   leave state you cannot observe.

## Do not do these

- **Do not send packet Type 0** (or any type outside 1–4). It wedges the
  firmware until the scanner is power cycled. `pakon_cmd.py` refuses.
- **Do not flash PIC firmware** (`Config/Firmware/*.HEX`). The scanner already
  has working firmware. The readme warns that a hardware-revision mismatch is
  destructive, and this is one of the few genuinely irreversible operations.
- **Do not write calibration** (`CalibrationPut*`, `ResetFactoryDefaults`) until
  the EEPROM has been read out and backed up. That data is unique to the
  physical unit and exists nowhere else.

## After the blocker clears

1. Lamp on, confirm via EP 0x86 light level.
2. Read per-unit calibration from EEPROM — **back it up before anything else**.
   Dark/white points, CCD gain and offset, and the per-unit colour matrix live
   there and cannot be recovered if lost.
3. Advance film, capture EP 0x86, find the scan-line sync marker.
4. Assemble lines into a frame; save 16-bit planar raw.
5. Run the raw through `pakon_color.py`; compare against a known-good scan of
   the same frame from the original software.
6. Roll-level scene balance (two-pass — a per-frame approximation will not
   reproduce the look).
7. B&W path: host-side density-domain inversion anchored on per-roll measured
   film base, for HP5+ / FP4+ / Delta 3200. See [`10-bw-films.md`](10-bw-films.md).

## Notes for anyone picking this up

The single most useful thing you could contribute is **a USB capture of the
original Windows software performing an initialise, calibrate and scan**. It
would collapse the remaining unknowns immediately.

Failing that, the second most useful is a decode of the `TLB.dll` command
builders — the packet plumbing is fully understood, so it is purely a question
of which bytes mean which operation.
