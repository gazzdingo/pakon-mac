# 06 — Status and Roadmap

## Where this stands

| Stage | Status |
|---|---|
| 1. Enumerate and load firmware | ✅ **working, automated** |
| 2. Command round-trip | ✅ **working** |
| 3. Read scanner identity | 🟡 partial — boards respond, registers not decoded |
| 4. Lamp on / motor move | ✅ **both working** — lamp visually confirmed |
| 5. Acquire raw scan lines | ❌ **THE BLOCKER** — EP 0x86 does not respond to light |
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

## Appendix — the lamp flash, and why it was not the lamp command

During a write sweep across boards `0xa2`-`0xa5`, one measurement recorded a
genuine illumination event: EP 0x86 level jumped from a dark baseline of 1244
to a mean of 17539 with a peak of 53400, and the operator independently
observed the lamp **flicker**. The apparent trigger was:

```
02 05 a2 02 08 01 01     Type 2 write, board 0xa2, reg 0x08, data 01 01
```

**This does not reproduce, and should not be treated as the lamp command.**
Ruled out by:

- re-sending the packet immediately afterwards: dark
- sweeping every value 0x01..0xff in that register: dark
- firing it in a tight loop for 4 s (366 samples): no illumination at all
- replaying the exact preceding write order: dark
- replaying the **entire** 384-write history plus the trigger: dark

The most likely explanation is that the light board performed a spontaneous
self-test or warm-up attempt that coincided with the write. The API supports
this reading: `EC_LampWarmUpFailure`, `WTO_LampWarmUpProgress` and
`FILM_COLOR_LAMP_STANDBY` all describe a lamp state machine that can act
without host prompting.

### What the episode did establish

1. **The illumination was real** — peak 53400 against a 1244 dark baseline is
   bright-field data, not noise.
2. **The light meter method works**, but only with a correct detector. The CCD
   FIFO is free-running and stalls full of stale data, so EP 0x86 must be
   flushed (~384 KB) immediately before each measurement. Every earlier
   "no change in illumination" result taken without flushing is unreliable and
   was re-run.
3. **Four previously undocumented board addresses exist**: `0xa2`, `0xa3`,
   `0xa4`, `0xa5`, plus `0x41`/`0x45` as alternate views of `0x40`/`0x44`.
   A Type 4 ping sweep across all 256 addresses found exactly nine responders.
4. **The FX2 reports its firmware as `"F235 Boot"`** (AD_HOST register 0x02),
   which suggests the operational firmware layer is not started by the
   firmware download alone.

### Lesson

Blind register writes on these boards return "accepted" almost unconditionally,
so acceptance carries no information, and any effect observed once may be
coincidental. Reproduce before believing. The reliable route to lamp control is
the static decode of `TLB.dll`, not further sweeping.

## Appendix — lamp bring-up attempts, all negative

Every documented step below was executed on hardware. All returned success
(`07 02 40 00`). **None produced illumination**, measured with a correctly
flushed EP 0x86 light meter against a ~1242 dark baseline.

| Step | Packet | Result |
|---|---|---|
| host fault clear to convergence | `04 03 10 00 85` | status `0xa8` → `0x88`, error bits cleared in 1 iteration |
| bus/relay enable | `02 04 10 01 8F 01` / `00` | accepted |
| FIFO reset | `02 04 10 01 84 02` | accepted |
| lamp temperature init | `02 04 40 01 D0 00`, `02 04 40 01 D1 01` | accepted; temp reads `0x0280` |
| lamp enable, visible | `02 04 40 01 80 01` | accepted, dark |
| lamp enable, visible+IR | `02 04 40 01 80 03` | accepted, dark |
| FPGA acquire | `02 06 44 03 82 00 01 00` | accepted, dark |
| DX start | `02 06 40 03 91 01 00 00` | accepted, dark |

Supporting reads, all healthy:

```
LED levels    reg 0x81 -> 40 06 00 40 25          non-zero
duty cycles   reg 0x82 -> 40 06 00 40 25 10 ...   non-zero
lamp status   reg 0x83 -> 00 / 0x10 after enable  changes with state
lamp temp     reg 0x84 -> 80 02
device info   0x40 -> hw 05 fw 0A, 0x44 -> hw 05 fw 06
```

So the enable register does latch and change state, the levels are programmed,
and the boards are healthy and correctly identified. The lamp still does not
light.

### Leading hypotheses, untested

1. **The LEDs are strobed per scan line**, synchronised to CCD integration by
   the FPGA, so "enabled" never means "continuously lit" outside a real scan.
   This fits a line-scan design and would explain success responses with no
   light. It also means the correct test is a full scan sequence, not a static
   lamp toggle.
2. **The corrupted boot EEPROM leaves the unit in a fault state** that inhibits
   the lamp. The unit lights a red LED after every firmware load. Restoring the
   EEPROM byte would eliminate this variable.

Both are worth resolving before any further lamp experiments. Resolve (2)
first — it is one byte, the correct value is known, and it removes a confound.

### Do not

Continue sweeping registers hoping to find the lamp. That approach is what
corrupted the boot EEPROM in the first place: the "board addresses" being swept
were I2C addresses, and the writes landed in an EEPROM. Any further hardware
experimentation should send only packets with specific binary evidence behind
them.

---

# CORRECTED SUMMARY (end of first session)

The operator visually confirmed **a bright blue light** from the LED
illuminator during the lamp bring-up. **The lamp works.**

That invalidates the bulk of this session's diagnosis. For most of the session
"EP 0x86 stays dark" was read as "the lamp is not lighting", which drove a
long and wrong investigation: a thermal interlock theory, a hunt for
per-unit calibration currents, and an assumption that illumination could not
work without values from a calibrated Windows registry. None of that was the
problem. The compiled-in defaults light the lamp.

## Actual state

| | |
|---|---|
| firmware loading | ✅ userspace, automated, no kext |
| command protocol | ✅ decoded, verified against hardware |
| board identification | ✅ matches shipped PIC firmware exactly |
| film transport | ✅ three commanded speeds + reverse, confirmed by ear |
| **lamp** | ✅ **confirmed lit — bright blue** |
| EP 0x86 stream | ✅ live, 30 MB/s, 3-channel 16-bit |
| **illuminated image** | ❌ **the blocker** |
| colour correction | ✅ implemented, exact to 0.000050 |

## The one remaining problem

EP 0x86 carries data that does not respond to illumination. Mean pinned at
~1239 across: lamp on/off (genuinely on), LED levels 1-24 on every channel,
CCD A/D gains and offsets, FPGA exposure window and control word.

Two candidate causes, in order:

1. **Blocked optical path.** `FILM_COLOR_FILTER_WHEEL_BLOCKED`,
   `FN_bDrvMoveFilterWheel`, `EC_MotorFault_FilterWheel` all exist. A lit lamp
   behind a parked filter wheel yields exactly these observations. **Untested.**
   A full emulator sweep found no reachable filter-wheel command, so it sits
   behind a state guard.
2. **The FPGA is not clocking the sensor into the FIFO**, so EP 0x86 carries
   readout unrelated to the programmed integration window.

## Method note for whoever continues

`tools/emulate_tlb.py` runs the vendor's own x86 code under Unicorn and logs
the packets it would emit. It is validated: emulating
`FN_bDriveMotorAdvanceFilm` reproduces byte-for-byte the motor sequence
confirmed to physically move this scanner. Use it rather than hand-decoding —
hand-decoding in this session produced four confidently-stated conclusions that
were later shown wrong.

Note also: the FN name table is a packed UTF-16 blob indexed by computed
offset, not an array of pointers. Pointer searches for it return nothing, and
name-table *position* does not equal FN id.
