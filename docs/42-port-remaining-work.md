# What is left to finish the macOS port — 2026-08-06

Written the day U34 was repaired and the lamp calibration recovered. Both
changed the shape of the remaining work, so this supersedes the status table in
`docs/06-roadmap.md`.

**Correction to `docs/06` first:** its stage-4 row reads "lamp visually
confirmed". That is wrong and `docs/14-lamp-decoded.md` supersedes it — the
board ACKs the enable and the illuminant stays dark. Do not plan against that
row.

## Where it actually stands

| Stage | Status |
|---|---|
| 1. Enumerate + load FX2 firmware | **done**, automated, no kext |
| 2. Command round-trip | **done**, both PIC boards answer |
| 3. Scanner identity / registers | partial — reads work, semantics thin |
| 4a. Motor / transport | **done today** — verified turning |
| 4b. Lamp | blocked → now *probably* unblocked, see below |
| 5. Acquire scan lines | the old blocker; **status changed today** |
| 6. Strip scan → file | not started |
| 7. Imaging pipeline | **done and verified** |
| 8. Packaging | not started |

Stage 7 landing before 4–6 is unusual but deliberate: the colour work needed no
hardware and is the part that actually distinguishes this scanner.

## The three things that changed today

1. **U34 (PICM, the motor board) was repaired.** One erased 64-byte flash row
   restored. Motor confirmed turning; both boards answer on I²C.
2. **EP 0x86 now looks different.** `docs/06` recorded it pinned near a dark
   baseline of ~1242 and unresponsive — the reason stage 5 was "THE BLOCKER".
   It now reads mean ~2531 with a real distribution (min ~1092, max ~3486).
   **PICM drives CCD timing**, so the repair is a plausible cause. Unverified.
3. **This unit's LED calibration was recovered** from a Windows registry hive
   carved out of a VM disk (`docs/37`, `research/windows-registry/`).

Points 1 and 2 together are the important part: **stage 5 may have been blocked
by the broken chip all along**, not by a missing command. That reframes the
single largest unknown in the project.

## Remaining work, in dependency order

### A. Light the lamp — in progress
Calibrated `Current_*` and `DutyCycle_*` are in hand. Two open questions, both
static and answerable offline (Fable is on them):
* is setpoint programming gated on `UseTemperatureSetpoints = 0`, which would
  mean `docs/14`'s "setpoints are the blocker" no longer applies;
* **how do registry values become register payloads** — `Current_R = 5` and
  `DutyCycle_R = "0.917161"` must become bytes in `0x81` (5 B) and `0x82`
  (12 B). Scale, layout, channel order and the 5th byte of `0x81` are all
  undetermined. Right numbers in the wrong encoding are as damaging as wrong
  numbers.

### B. Establish what EP 0x86 is actually carrying — do this next, it is cheap
Pure reads, no risk, and it may retire the project's oldest blocker:
* is the new distribution structured (line sync, per-channel interleave) or
  noise? Autocorrelate for a repeating line length.
* does it respond to a physical light change — open the gate, shine a torch,
  compare means. That is the light-meter test `docs/06` used, now worth
  re-running against repaired hardware.
* does it change when the motor runs?

**Do B before A if the lamp answer is slow.** It needs no calibration data and
no writes, and a positive result changes the plan for everything after it.

### C. CCD initialisation and acquisition
`tools/init_ccd.py` and `tools/start_acquire.py` exist and are interlocked.
`FN_bDrvCcdAcquireControl` sets bit 0 of CCD register `0x82` (`docs/12`).
Needed: confirm what must be programmed before acquisition is meaningful —
`Gain_R/G/B` (13/13/13) and `Offset_R/G/B` (−18/−26/−20) are now known per mode
from the registry, which is new.

### D. Scan-line framing
Find the sync marker in the EP 0x86 stream and recover line length, channel
order and bit packing. Note `docs/06:139` — the FIFO free-runs and stalls full
of stale data, so it must be flushed before any measurement is trusted.

### E. Transport choreography
Motor primitives work (`0xA5` speed, `0xA0/0xA1` run, `0xA2` stop). Needed:
frame detection, film-present sensing (`FilmPresent` appears in TLB.dll's
strings), and the advance/settle/scan loop. Registry gives real per-mode motor
values: `MotorSpeedPlus/_Ir` 5917/4850, 11467/7580, 25802/19335,
`MotorAdjust` 1000, `MotorAdjustDrag` 1008.

### F. Assemble frames and hand off to the colour pipeline
The pipeline is done and verified to 0.000050 against the vendor tables. This
step is plumbing: lines → frame buffer → `tools/pakon_color.py` → 16-bit TIFF.
**This is where the project starts producing photographs.**

### G. Packaging
A CLI that runs a whole roll end to end, then whatever UI is wanted. Nothing
here is research.

## Known gaps worth closing separately

* **The scanner EEPROM is only partly read.** `0x52` is one 256-byte page; the
  driver reads a 398-byte section, and our page contains none of the documented
  motor fields. Other pages (`0x53`+) are unread. One read per power cycle —
  see `backups/eeprom-i2c/README.md`, these parts degrade silently after the
  first read.
* **`PakonLampLog.txt` was never recovered** — it needs NTFS parsing of the same
  VM disk image the registry came from.
* **Read the physical unit's serial.** If it is 16275, the 2022 registry
  calibration is also ours and we gain a `DpiBase8` set we currently lack.
* **`DpiBase8_35` has no 2025 calibration** — this unit was only calibrated at
  bases 4 and 16.

## Honest assessment

The hard reverse-engineering is done: protocol, firmware loading, colour
science, motor control, and now a repaired machine that answers. What is left is
mostly **sequencing and format work against a scanner that finally responds** —
different in kind from the last several months, which were spent fighting a
chip with a hole in its flash.

The single highest-value next action is **B**, because it is free, it is
read-only, and it may retire the oldest blocker in the project.

## macOS-specific notes

**Host confirmed: Apple M2 Max, arm64, macOS 26.5.2.**

Reconciling two conflicting claims now in the repo: `docs/36` said "Apple
Silicon" and `research/windows-registry/NOTES.md` says "this Mac is Intel
(i5-7360U)". Both are right about *different machines* — the M2 Max is this
development Mac, the i5-7360U is the laptop that hosted the Parallels VM and
where the scanner actually attached in July 2025. The recovered calibration is
unaffected: the attach records are in the VM's own log.

### What is already solved, and it was the biggest macOS risk

The vendor shipped a kernel driver (`F235Ldr.sys` / `F135USB3.sys`). **None of
it is needed.** `tools/pakon_load.py` reimplements the two-stage EZ-USB load in
userspace over libusb, and today the entire chain — load, re-enumerate, command
round-trip, motor, register reads, EP 0x86 capture — ran natively on arm64. No
kext, no Rosetta, no VM. That was the single largest "will this port at all"
question and it is answered.

### The real macOS engineering risk: sustained throughput

EP 0x86 delivers **~30 MB/s**. Synchronous single-buffer `dev.read()` in Python
is fine for the 16 KB probes used so far and will very likely **not** hold that
rate for a whole roll — one stall and the free-running FIFO overruns, which
`docs/06:139` already warns about.

Needed before stage F:
* libusb **asynchronous** transfers with a submitted ring of buffers, not
  blocking reads;
* measure actual sustained rate and drop behaviour before designing the frame
  assembler around it;
* if Python cannot hold it, a small C or Swift capture core writing to a ring
  buffer, with Python retained for orchestration and colour.

Treat this as a measurement task, not an assumption — nobody has yet captured
more than a few buffers in a row.

### Packaging

* libusb is currently a Homebrew dependency; a distributable app must bundle it.
* Code signing and notarisation for anything shipped outside the dev machine.
* No special entitlement is required for libusb bulk I/O to a device macOS has
  not claimed. If a system class driver ever claims the interface, it must be
  detached first — not currently an issue for `0f05:f135`.

### One macOS advantage worth using

The vendor `.pf` colour profiles are standard ICC v2 (Kodak KCMS), so
**ColorSync consumes them directly** (`tools/pakon_profile.py`). Rendering can
hand off to the system colour engine rather than reimplementing it.

---

## EP 0x86 CHARACTERISED — 2026-08-06, read-only

Ran `tools/characterise_stream.py` against the repaired scanner. No writes, no
acquisition started, no lamp.

```
mean 1421.4   sd 122.3   min 1082   max 1656
three captures, spread across captures 1.2   -- very stable
```

### 1. The stream is 3-channel interleaved, confirmed from the data

Correctly normalised autocorrelation:

```
lag 3, 6, 9, 12, 15, 18, 21, 27  ->  r = +0.987
lag 1, 2, 5, 10, 50, 100         ->  r = -0.22
```

A clean period of **exactly 3 samples = 6 bytes**. `docs/06` asserted "3-channel
16-bit"; this confirms it directly and fixes the layout: **R/G/B interleaved per
pixel, 16-bit little-endian each, 6 bytes per pixel.**

Per-channel DC levels differ, which is what produces the strong period-3
correlation and the negative r between unlike channels:

```
channel 0  mean 1338.0  sd 53.3
channel 1  mean 1349.7  sd 68.7
channel 2  mean 1575.3  sd 40.9
```

### 2. Line length: 2151 pixels (strong candidate)

Per-channel autocorrelation peaks land at **exact integer multiples of 2151**:

```
2151 x2 = 4302    x4 = 8604     x5 = 10755
         x6 = 12906   x8 = 17208    x9 = 19359
```

Drift gives a smooth monotonic decline; discrete harmonically-related peaks do
not come from drift. So **line length ≈ 2151 px = 12,906 bytes/line** at
3 channels x 16-bit.

**Caveat:** r sits ~0.96 across all of these, a narrow range, so some
low-frequency component is present too. Treat 2151 as a strong candidate to be
confirmed — ideally against a line whose content changes, i.e. with the lamp on
or the transport moving.

### 3. A methodological warning worth keeping

The first version of the autocorrelation divided by the full-length sum of
squares while sub-sampling with a stride. It returned **r = +1.681** — impossible
for a normalised autocorrelation — and printed "STRUCTURED: strong period at 66
samples", which was false; adjacent lags 66/69/72/75/78 all scored identically,
the signature of drift. **If |r| > 1 the normalisation is wrong.** Fixed in the
tool, with the trap documented in its docstring.

### What this means for the roadmap

Stage 5 was "THE BLOCKER — EP 0x86 does not respond to light". The stream is
demonstrably **structured and stable**, and its pixel format and probable line
length are now known — all without writing a single register. That is most of
step D (scan-line framing) obtained for free.

Still open: does it respond to illumination? That needs the lamp, or a torch at
the gate, and is the one part of the light-meter test not yet re-run.

---

## ACQUISITION DECODED — 2026-08-06

Full call-site analysis of TLB.dll plus one free hardware test. **The FPGA has
never been configured.** That is why the sensor clocks but does not integrate.

### The decisive test — free, read-only

Line sync is **bit 0 of each u16 sample**. Proven at two independent sites:
`fcn.1002f240` @`0x1002f287` and the scan worker `fcn.1002f550` @`0x1002ff03`
both loop `test byte [esi],1`, and exhaustion raises
`EC_DRV_CannotFindStartOfScanLine` (1001). Because the search tests *every*
word, bit 0 must be 0 on every word except the first of a line.

Measured on our stream:

```
262,144 samples   words with bit 0 set: 0   (0.00%)
```

**Zero markers.** The FPGA is emitting no line starts. This distinguishes
"unconfigured FPGA" from "configured but not integrating" — it is the former.
The period-3 interleave we measured is the AFE clocking three channels; the
line framing the FPGA would add is simply absent.

### The likely original error

`tools/init_ccd.py` writes control word **`0x163`**. The correct value is
**`0x061`**. Bit 8 (`0x100`) is **IR mode** and bit 1 (`0x002`) is **binning**,
and the vendor sets neither for a normal colour scan. Worse, the geometry
(offset 62 + height 2000 = 2062) violates the binning limit of 1060. A
structured stream that ignores visible light is exactly what that produces.

### Corrections

* **`0x82`/`0x84` ARE readable.** `docs/12` §8 says no Type-1 read of `0x82`
  exists so the shadow cannot be recovered. Wrong — `PutRegisterCcd` has a
  verify path (`0x1000a69c`) using read-back register `0x83` for FPGA, `0x85`
  for A/D:
  ```
  02 04 44 01 83 <idx>      select readback index
  01 03 44 02 07            read 2 bytes -> the value
  ```
  Every FPGA/AFE write can be verified instead of trusted.
* **`InitCcd` is not called from `BeforeScan`** — it lives in `FN_bInit3`, once
  at bring-up. `docs/12` §6 has the order wrong.
* **`0x84` idx 5/6/7 are offsets, not "CCD exposures".** `docs/12` §3 is wrong;
  `FN_bDrvPutCcdExposures` has no implementation in this binary.
* **The event ACK is NOT the blocker.** Verified four ways: `fcn.1000bdd0` has
  one caller (a background poll); the packet error decoder never tests bit 7;
  the acquisition path's only status poll is `GetPpbHostStatusByte`; and our
  lamp sequence worked with bit 7 set throughout. Worth adding for hygiene, but
  it will not change EP 0x86. **My hypothesis was wrong.**
* **Our 2151 px/line is not corroborated** — the binary says 2000 for
  DpiBase16. Do not hard-code either: **segment on bit 0**, as the vendor does.
* **Gains/offsets do NOT gate integration**, only data quality — `InitCcd`
  never programs them and the dark phase acquires with offsets 0,0,0. Program
  them anyway (6 packets, no risk): a gain of 0 would mask a real light
  response and the power-on default is unknowable.

### Ordering that matters

**The host read must be armed BEFORE the acquire bit.**
`FN_bCalibrateStartDataFlow` issues the overlapped `ReadFile` (`0x10020150`),
expects `ERROR_IO_PENDING`, and only then calls `CcdAcquireControl(1)`
(`0x1002016d`). Teardown reverses it.

`0x060` in the control word is **required but of unknown meaning**, and is
written only when the integration shadow is −1 — which `InitCcd` sets. That is
the mechanism behind "these init writes are not optional".

### Channel identity is NOT determined by the binary

Which sub-stream is R, G or B is not named anywhere. Given the lamp registers
run **B, Ir, R, –, G**, do not assume RGB. Cheap test once integrating: drive
one LED channel at a time and see which sub-stream moves.

---

## THE SENSOR WORKS — 2026-08-06

**The FIFO reset was the blocker.** Two packets never sent in this project:

```
02 04 10 01 84 02        FN_bDrvResetFifos, part a
04 03 40 00 8a           part b
```

Result, immediately:

```
                          mean      max     sync words
before (all session)     1236        -           0
FIFO reset, lamp off      290      374         5-6      <- FIRST SYNC MARKERS
FIFO reset, lamp lit    64924    65534         5        <- LIGHT RESPONSE
```

The FIFO had been stalled full of stale data, exactly as `docs/06:139` warned.
**Every measurement this project ever took from EP 0x86 was that stale content** —
which is why it never responded to anything: not the chip repair, not the lamp,
not the AFE reprogramming. The "structured but unresponsive" stream was a frozen
buffer.

Note the ordering that matters: the lamp coming on did **not** change the
reading. Only resetting the FIFO *again, with the lamp already lit*, showed the
light. So reset the FIFO after every state change, before trusting a reading.

### Line length confirmed at 2000 px

5-6 sync markers per 32,768 samples ≈ 6,000 samples per line = **2000 px x 3
channels**, matching the binary's DpiBase16 value. **Our autocorrelation figure
of 2151 was wrong** — it was measuring the integration time (read back as
`0x0866` = 2150), not the line length. Segment on bit 0, not on a measured
period.

### 64924 near full scale is expected

Empty gate + lit lamp = saturation. The calibration search stops at 64000
(`0x1001e8da`), so this is the right order of magnitude for an unattenuated
path. Film in the gate should bring it down into range.

### Where this leaves the port

Stage 5 — "acquire raw scan lines", the blocker since the project began — is
**solved**. Remaining: segment lines on bit 0, identify which sub-stream is R/G/B
(not determined by the binary — drive one LED at a time), couple transport speed
to line rate, and feed the existing colour pipeline.
