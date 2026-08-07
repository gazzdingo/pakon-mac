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
per-column flat field                      -> replace with the real gain table
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
