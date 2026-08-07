# Handover to the Ansel colour task — 2026-08-07

Things changed under you tonight. Read this before using any capture.

## 1. Capture is now lossless. Old captures are not.

The tears and shears in every earlier frame were **my capture loop**, not the
hardware and not throughput. It called `FN_bDrvResetFifos` before *every* read,
discarding whatever the FPGA had buffered since the last one. The vendor resets
twice in `BeforeScan` (`0x1002dcf5`, `0x1002e0ee`) and then never again for the
whole strip.

```
                         intact    losses
with per-read resets     94.79 %      960
resets only at start    100.00 %        0     694.8 MB in 60 s, 11.6 MB/s
```

**Consequences for you:**

* `strip_cal.bin` and `strip60.bin` **contain real data loss** — 960 non-6000
  gaps in `strip_cal.bin`, all after marker 10,505. The first 10,505 markers are
  clean. If you are debugging colour against those files, restrict yourself to
  the clean prefix or you will chase artefacts that are not colour bugs.
* Anything captured from now on is clean. Async libusb and the Rust core are
  **struck from the plan** — plain synchronous reads hold the rate losslessly.

## 2. New calibration references — both lossless, use these

| file | lines | contents |
|---|---|---|
| `captures/ref_dark.bin` | 14,482 | lamp OFF, acquisition running |
| `captures/ref_bright.bin` | 7,626 | lamp ON, empty gate, unclipped |

```
dark     R  1120.5 ±9.6     G  1443.0 ±10.1    B  1160.9 ±10.7
bright   R 50204.6 ±5573    G 49962.2 ±6162    B 49916.2 ±6194
```

These are what the vendor's per-pixel **dark** and **gain** tables get built
from — `FN_bCalibrateFindDarkOffset` (`0x1001e1c0`) and
`FN_bCalibrateFixedPatternBright` (`0x1001f550`). The prior decode analysis
found the per-pixel gain is **mandatory for basic recognisability**, not a
quality refinement: column PRNU plus lamp falloff dominates the raw signal.

The bright reference is deliberately at ~50,000 rather than the vendor's 64,000
target, so no channel clips. A clipped channel records no variation and is
useless as a flat field — the first attempt had B at 65534 with **zero**
standard deviation.

## 3. The timing bug that made exposure unrepeatable

FPGA integration was **2150** while the lamp PWM ran **N=982**. N is
`trunc(exposure × 0.24)`, so 982 belongs to exposure **4093**. The lamp pulsed
on one period while the CCD integrated on another, and the beat made every
per-line maximum unpredictable — green read 13,376 at one on-count and 65,406 at
a slightly higher one, non-monotonic and unrepeatable.

**Locked configuration, DpiBase16 non-IR:**

```
FPGA 0x82 idx6 integration = 4093        vendor value (fcn.10011a60)
lamp PWM N                 = 982         = trunc(4093 × 0.24)
light 0x91 line rate       = 60          = clock × 237 / (exposure × pixels)
                                           clock = 2,083,333.3
```

With those locked, four consecutive reads returned byte-identical maxima and
exposure convergence took **two** iterations instead of oscillating forever.
**If you change integration, you must recompute N and `0x91` together.** They
are one setting in three registers.

## 4. Decode recipe as it stands

```
accept only lines whose sync markers are exactly 6000 words apart
plane_k = line[k::3]                       per-pixel R,G,B; nothing to crop
phase may ONLY change where the preceding gap was not 6000
  -- re-evaluating per line causes false channel rotations that paint a hard
     band across otherwise clean frames. This was a real bug, not a nicety.
+3 line shift on channel 0                 measured by correlation; unconfirmed
per-pixel dark×gain                        calibration/*.npy (default in
                                           pakon_decode; --no-calibration to skip)
per-frame percentile stretch               -> replace with density LUT + matrix
frame pitch ~1460 lines                    measured from gap spacing
```

Bit 0 of every u16 is the line-start flag, so data is effectively 15-bit even
values and `0xFFFE` is the **clipped maximum**, not a sentinel — nothing in
TLB.dll tests for it.

## 5. Still open, and yours if you want them

* **Orientation.** Six variants tried, all judged wrong by the owner. Needs the
  vendor's actual frame-buffer indexing from `fcn.100246d0`'s destination
  arithmetic (`0x10024b43`–`0x10024b65`) and `FN_bGetScanLines`. A lens inverts
  the image; a flip may be required that I never applied.
* **A residual band** in loss-free regions, distinct from the phase bug above.
  Best remaining candidate is the **smear accumulator** — a per-line scalar,
  decayed against `0x1007d380/88/90` and refreshed from the previous line's sum
  (`0x10025877`–`0x100258d6`). A wrong initial value would produce exactly a
  band that decays. I never implemented smear at all.
* **Trilinear registration.** Is my +3 line shift real, or is it an artefact?
  Cross-correlation gave lags of 0–3 with r = 0.94–0.98.

## 6. Housekeeping

`captures/` is gitignored and holds the owner's personal photographs — do not
commit anything from it, do not copy images out, do not describe their content.
The repo is private. `app/node_modules` is gitignored (538 MB).

---

## 7. CORRECTION — calibration policy, and smear does not exist here

Traced from the bytes 2026-08-07. Two things in §5 above are wrong.

### Smear is NOT a candidate for the band — it has no implementation

I named the smear accumulator as the best remaining explanation for the
residual band. **That was wrong.** `fcn.100079c0` is not
`FN_bCalibrateFindSmearAndFPC` — the recovered FN map gives it as
`FN_iFramePictures`, and its only two call sites are inside `FN_bAfterScan`
(`0x1002aba5`, `0x1002abb8`), doing post-capture frame detection.

The string `FN_bCalibrateFindSmearAndFPC` (`0x10061af0`) is referenced exactly
once in the whole image, at `0x10018be6`, inside the FN-id→name table used for
logging. **There is no implementation bound to it in this build, and smear is
not part of any calibration path.** Do not chase it.

### Calibration policy — the vendor does NOT recalibrate per scan

The gate is at `0x1002ded2`, on `[scanner+0x130]` — the vendor's own
`iCalibrateControl` (named at `0x10040b16`). Zeroed at the top of every
`FN_bBeforeScan`, so it is per-call scratch, not persistent state. It fires on:

1. **no per-pixel table for this configuration** (`+0x20 == 0`) — true after
   process start, any parameter change, or an aborted scan
2. **> 60 minutes** since this configuration last calibrated. Hardcoded in the
   `CiConfigScan` constructor (`0x100120a2`, `mov eax, 0x3c`), never
   registry-backed, not configurable
3. **> 20 hours** since the last *full* light calibration — `0x11940` seconds,
   compared against the persisted registry value `FullLightCorrections`

Conditions 1–2 rerun dark offsets, per-pixel dark, duty cycle, per-pixel bright
and IR-lag. Condition 3 *additionally* reruns the LED current search from
`Current_* = 1`.

**Otherwise nothing runs at all.** A whole roll calibrates at most once.

### Purely time-based. No temperature trigger — proven, not assumed

Every caller of the three invalidation routines was enumerated. Nothing reaches
them from the light-board monitor thread, and the gate's entire call graph is
`time()`, `Invalidate()` and the 20-hour test. **A temperature reading can never
trigger recalibration in this build.** The 3.7 % warm-up droop is handled by
`WaitForLamp_*` settling sleeps instead.

### What persists, what does not

| artefact | persisted? | redone when |
|---|---|---|
| per-pixel dark, bright/gain, IR-lag | **no** — heap only | any gate hit; every process start |
| AFE dark offsets `Offset_R/G/B` | yes, registry | every calibration run |
| AFE gains `Gain_R/G/B` | yes, registry | every calibration run |
| LED duty cycle | yes, registry | every calibration run |
| **LED current** | yes, registry | **only** on 20-hour expiry |

Identity is **(DPI base × film colour × IR)** — 18 independent records, each with
its own table pointer and timestamps. Changing resolution, film colour, film
format or IR calls `fcn.10011420` at `0x1003c494` and **destroys the tables for
all 18**.

### So, for our port

* **Do not regenerate before every scan.** The vendor does not.
* **Once per session is right** — and is effectively what the vendor does, since
  its per-pixel tables cannot survive a restart.
* **Regenerate after 60 minutes**, and on any change of DPI base, film colour,
  film format or IR. Those are hard invalidations in the vendor code.
* `calibration/dark_2000x3.npy` and `gain_2000x3.npy` correspond to something
  the vendor never writes to disk, so reusing them across sessions has no vendor
  precedent. It is a defensible choice, but the vendor's own bound is 60 minutes
  and one configuration — and stale corrections look exactly like the
  column-structured residual we are already chasing.

### Also corrected: `[scanner+0x298]`

`docs/15` says that flag "is set by the light-board monitor". A byte search for
stores with displacement `0x298` finds 11 hits and **none is a store** — nothing
in TLB.dll writes it. `fcn.1002cf10` is a DSP/ringtail completion wait (250 ms
poll, 300 s timeout), not a lamp-temperature wait.
