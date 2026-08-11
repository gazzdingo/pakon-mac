# cna (subsystem)

## cna capability — ColorNegativePath::analyzeAutoTone, stage 1/6

**Binary:** `PakonIMAu.dll` (MD5 `eea9dcf78ee21d4f7c515a6c2512242d`), sourced from `research/sdk/PAKONF135.iso` → `program files/Pakon/.../F-X35 COM SERVER/` (mounted as `/Volumes/Pakon 135 v3.0`). Tools: radare2 6.1.8 + r2ghidra (`pdg`), 32-bit x86.

### 1. Size — direct-call reachability from analyze (0x1022ea50)

Same BFS method used for the whole-chain figure (166 funcs / 67,896 bytes / 615 indirect), re-run seeded at cna's own entry points:

| seed | functions | code bytes | indirect (vtable) call sites |
|---|---|---|---|
| analyze only (0x1022ea50) | 36 | 11,635 | 94 |
| acquire only (0x10132dc0) | 37 | 11,857 | 96 |
| acquire ∪ analyze | 37 | 11,857 | 96 |

acquire's reachable set is a strict superset of analyze's (acquire literally calls into 0x1022ea50 as part of construction) — one extra function only. All 37 addresses verified as a proper subset of the previously-captured 166-function whole-chain reachability set (`/private/tmp/reach_out_autotone.json`), confirming methodology consistency.

**cna's share of the six-subsystem chain: 37/166 functions (22.3%), 11,857/67,896 bytes (17.5%), 96/615 indirect call sites (15.6%).** By far the smallest of the six stages by these metrics (dra alone, with its 6 `.ttc` curve files, is expected to dwarf it — not measured here, out of scope).

### 2. What it reads and computes

`vendor/ansel/anselinstalldir/dataPathItems/cna/ansel-cna-default-default.dpi` is plain `key = value` text (source path confirmed live in the binary as a literal string: `\Atc\ansel\src\libCna.ansel\AnsCnaCapabilityImpl.cpp`). Fields, read verbatim from the file:

```
redShift, greenShift, blueShift
histSize=5000, bucketSize=10
minSlope=0.3, maxSlope=2, blend=1.0
pivot=1550, minPivotPercentile=0.1, maxPivotPercentile=0.9
thresholdMultiplier=1.5, thresholdReductionFactor=0.949, minPosThreshold=4
minLapPixelRatio=0.1, smoothingSizeFactor=4.0
laplacianHistSmoothingSigma=10.0, coarseHistSmoothingSigma=2.0, toneScaleSmoothingSigma=4.0
darkMaxContrastGain=1.33333, lightMaxContrastGain=2
darkMeanSigma=190.0, lightMeanSigma=270.0
minGaussSigma=1.0, maxGaussSigma=50.0
elmoNeutralLimit=1500, elmoRedLimit=1600, elmoGreenLimit=2100, elmoBlueLimit=2100
elmoSatThreshold=400, elmoCriticalPercent=5.0, elmoAggressiveness=ANS_LOW_TONE_AGGRESSIVENESS
```

Verified real use, not just parsing: `fcn.1022ceb0` (called first inside analyze) is a straight-line range/order validator that checks each of these fields against min/max bounds at fixed struct offsets (+0x8…+0x78) before any computation proceeds — e.g. bucketSize must divide histSize evenly, min<max ordering enforced on the slope/percentile/sigma pairs, elmoRed/Green/BlueLimit clamped to 0…0xfff (12-bit).

The computation (in `fcn.1022d970` → allocates ~15 scratch buffers sized off image height/histogram size, feeding `fcn.1022c340`/`fcn.1022c3e0`/`fcn.1022c520`/`fcn.1022c630`/`fcn.1022c740`/`fcn.1022ddc0`) is a **histogram + percentile/slope tone-pivot pass**, not a LUT build and not a trivial scalar decision:
- `fcn.1022c340` is a discrete 5-point Laplacian convolution (`center*-4 + 4 neighbours`) — matches `laplacianHistSmoothingSigma`.
- `fcn.1022c520`/`fcn.1022c630` build clamped index-mapping arrays sized by `histSize`/`bucketSize` (histogram bucketing).
- `fcn.1022c740` does iterative tail extrapolation/smoothing of a curve array (matches `coarseHistSmoothingSigma`/`toneScaleSmoothingSigma`).
- `fcn.1022c3e0` scans a float array for the point of maximum local second-difference (steepest-knee finder — plausible source of the `pivot`/`minSlope`/`maxSlope` result).

Net effect: builds a per-channel smoothed histogram, finds a percentile-bounded pivot point and a bounded contrast slope/gain, and separately checks red/green/blue "elmo" chroma limits — a statistical/smoothing pass producing scalar tone parameters (pivot, slope, gain) that get threaded onward via the CN context, not a full output LUT itself.

### 3. Execution gate — confirmed genuinely reachable

Decompiled `ColorNegativePath::declareAutoTone` (0x100f95f0) directly: immediately after pushing the literal string `"cna"` and a successful registration call (0x10132f00), the code does

```
eax = var_10h; byte[eax+0xc] = 1; byte[eax+0xd] = 1;
```

unconditionally on the success path — no further gate — before moving on to push `"dra"` and repeat the same pattern. This is the first of the six `+0xc=1` writes the earlier chain-wide note catalogued (0x100f9723 = cna, matching the byte offsets cited for dra/toneHelper/contrast/ast/citras that follow it, vs. pfd's `+0xc=0` at 0x100f9da2). `analyzeAutoTone` gates each stage on that same `+0xc` byte before calling it. **Confirmed for cna specifically, from the binary: it is set to 1 unconditionally on the registration-success path, no additional gate found.** `ColorNegativePath::analyzeAutoTone`'s one caller is `AnsCnEnhancedPath::CnEnhanced_analyzeSceneSpecific` (0x10069a1d), which is the negative's live render path (Shasta is confirmed dead for CN-Enhanced per the existing `shasta.go` note) — so cna does genuinely execute for a colour negative.

### 4. Existing coverage — none

`grep -rn "AnsCna\|Cna(" tools/` and case-insensitive `cna` search across `tools/ansel/*.go`/`*.py` return only prose/comments (in `shasta.go`, `main.go`, `pakon_ansel.py`, `pakon_shasta.py`) documenting the six-stage chain table — no struct, parser, or computation named for cna anywhere. `vendor/README.md` states outright: "cna/, dra/ and toneHelper/ are the data for the colour-negative auto-tone stage… nothing reads them yet." **Zero ported/verified code for cna exists in this project.**

### What was measured vs. not

Measured directly from the binary: reachability counts (functions/bytes/indirect call sites) from both acquire and analyze entry points; the DPI field list (plaintext file); the parameter-validator's exact range checks tying struct offsets to those fields; the shapes of the smoothing/histogram worker functions; the unconditional `+0xc=1` write for `"cna"` in `declareAutoTone`. Not fully determined: the precise semantic role of each worker function beyond its algorithmic shape (no full end-to-end trace of what pivot/slope value comes out for a given histogram — that would need dynamic tracing, not attempted here), and the exact meaning of `elmo*` (not spelled out in the binary; inferred from field names/usage only, not confirmed against source or docs).