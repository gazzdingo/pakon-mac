# 11 — Imaging Pipeline: Order of Operations

Reverse-engineering notes on the *sequence* of the Kodak/Pakon F-135 image
processing chain, recovered from:

- `fx35install/program files/Pakon/F-X35 COM SERVER/TLA.dll` (593 920 B) — the
  scanner back-end / orchestrator.
- `.../PakonIMAu.dll` (7 598 080 B) — the imaging engine (Kodak "Ansel" +
  Kodak CMS + Kodak `Ima*` operation framework, all statically linked).
- `.../Config/ColorCorrection/*` and `.../anselinstalldir/**`.

Every claim is tagged:

- **[VERIFIED]** — proven by disassembly / by parsing shipped data files, with
  the address or file cited. Reproducible.
- **[INFERRED]** — strong hypothesis consistent with all evidence, not directly
  proven.
- **[UNKNOWN]** — could not be determined from these binaries.

Addresses are image-relative virtual addresses at the DLL's preferred base
`0x10000000`.

---

## 0. Headline result

The pipeline is **two-level**. `TLA.dll` owns the order; `PakonIMAu.dll` owns
the maths. The entire cross-DLL surface is 19 `GetProcAddress`-resolved
entry points, so the pipeline order is literally the order in which `TLA.dll`
calls them. [VERIFIED — loader at `TLA.dll:0x100178c0`, jump table stored at
`this+0x24 … this+0x6c`, table pointer cached in global `0x10080f84`.]

```
raw 14-bit planar RGB(+IR)
  │
  ├─ (1) DICE scratch/dust removal, uses the IR plane            [INFERRED position]
  │
  ├─ (2) PIColorCorrectColNegPlanarScan / …Save / …ColRevPlanar  [VERIFIED]
  │        density LUT  →  3×4 matrix  →  clamp   ⇒ 12-bit RPD
  │
  ├─ (3) PIRotatePlanar                                          [VERIFIED]
  │
  ├─ (4) PIAnselColorSceneBalancePlanar                          [VERIFIED]
  │        applies the per-scene Ansel transform (SBA + tone +
  │        RPD→PCS→sRGB rendering)
  │
  ├─ (5) PIScaleAndRotatePlanar                                  [VERIFIED]
  │
  ├─ (6) PIColorAdjustPlanar                                     [VERIFIED]
  │        [input profile] ∘ saturation.pf ∘ bw/sepia.pf ∘ [output profile]
  │        combined into ONE CMS transform, then unsharp mask
  │
  ├─ (7) 16-bit planar → 8-bit planar / DIB                      [VERIFIED]
  │
  └─ (8) PISaveFilePlanar_8                                      [VERIFIED]
```

Steps 2–5 live inside `CiImage::bLoadImageFromBuffer`
(`TLA.dll:0x1002caa0`); steps 6–8 in `CiImage::bSaveToFile`
(`TLA.dll:0x1002d980`, which calls `bLoadImageFromBuffer` first).
Both orders were confirmed from the **basic-block graph**, not merely from
address order.

---

## 1. How the order was established [VERIFIED]

`TLA.dll` carries a debug-symbol registry: a 362-case switch at
`0x1001b4f1` (jump table at `0x1001df80`) that maps an integer function-ID to a
UTF-16 name string `FN_…`, and a 46-case switch at `0x1001b170` mapping a
class-ID to `CN_…`. Every error path calls the logger `0x1001ed80` as
`log(classId, fnId, errCode, …)`. Decoding those two tables recovers the
vendor's own names for ~360 functions and 46 classes. That is how the functions
below are named.

The 19 `PakonIMAu` entry points and their slots in the dispatch struct:

| slot | export |
|---|---|
| `+0x24` | `PIEnd` |
| `+0x28` | `PIBegin` |
| `+0x2c` | `PISaveFilePlanar_8` |
| `+0x30` | `PIFileSpecsPlanar_8` |
| `+0x34` | `PIFileOpenPlanar` |
| `+0x38` | `PIColorAdjustPlanar` |
| `+0x3c` | `PIRotatePlanar` |
| `+0x40` | `PIScaleAndRotatePlanar` |
| `+0x44` | `PIColorCorrectColNegPlanarScan` |
| `+0x48` | `PIColorCorrectColNegPlanarSave` |
| `+0x4c` | `PIColorCorrectColRevPlanar` |
| `+0x50` | `PIAnselStartNewRoll` |
| `+0x54` | `PIAnselAddScene` |
| `+0x58` | `PIAnselEndRoll` |
| `+0x5c` | `PIAnselAnalyzeRoll` |
| `+0x60` | `PIAnselAnalyzeScene` |
| `+0x64` | `PIAnselColorSceneBalancePlanar` |
| `+0x68` | `PIAnselDeleteRoll` |
| `+0x6c` | `PIAnselDeleteScene` |

Anchoring on loads of the table pointer `0x10080f84` gives an exhaustive,
false-positive-free list of every call into the imaging engine:

| caller (vendor name) | addr | calls |
|---|---|---|
| `CiColorCorrectionKodak::bApplyKodakColorCorrection` | `0x10014ff0` | ColNegSave / ColNegScan / ColRev |
| `bRotate` | `0x10029d30` | `PIRotatePlanar` |
| `bScale` | `0x10029af0` | `PIScaleAndRotatePlanar` |
| `bApplyColorAdjustments` | `0x1002a5a0` | `PIColorAdjustPlanar` |
| `bLoadImageFromBuffer` | `0x1002caa0` | `PIAnselColorSceneBalancePlanar` |
| `bSaveToFile` | `0x10029e90` | `PISaveFilePlanar_8` |
| `bInit2` | `0x1002ede0` | `PIBegin` |
| `bKcdfsCorrections` | `0x1003f720` | roll-level Ansel analysis (§5) |

---

## 2. Stage 2 — colour correction (the core) [VERIFIED]

### 2.1 Dispatch

`CiColorCorrectionKodak::bApplyKodakColorCorrection` (`0x10014ff0`) switches on
a film-class argument:

| case | matrix context | LUT | engine call |
|---|---|---|---|
| 1 | `this+0xd8` | `this+0x40` | `…ColNegPlanarSave` if a flag is set, else `…ColNegPlanarScan` |
| 2 | `this+0x168` | `this+0x44` | `…ColRevPlanar` |
| 4 | `this+0x48` | `this+0x40` | `…ColNegPlanarSave` |
| 3, default | — | — | no-op |

Case 1 = colour negative, case 2 = colour reversal. Case 4 shares the
colour-negative LUT but a *third* matrix context; **[INFERRED]** it is the
black-and-white (and/or imported-image) path. The three contexts are 0x90
(144) bytes apart — the same stride seen in the global config
(`+0x1650` colour-negative, `+0x16e0` colour reversal). [VERIFIED stride.]

### 2.2 The kernel

`PIColorCorrectColNegPlanarScan` (`0x100064d0`) and
`PIColorCorrectColNegPlanarSave` (`0x10006440`) are thin wrappers over
`0x1001c470` and `0x1001ca10` respectively. **Those two functions are
byte-identical apart from the addresses of their scratch globals**
(`0x106b5b30…0x106b5b6c` vs `0x106b5b70…0x106b5bac`): 37 differing bytes in the
first 1440, every one of them inside a `mov`/`lea` displacement field.
[VERIFIED by binary
diff.] The duplication exists so the scan thread and the save thread can run the
non-reentrant MMX kernel concurrently. *For the port there is exactly one
colour-correction routine.*

Signature (recovered from the argument shuffle):

```
core(width, height, src, dst /* == src, in-place */, unused,
     uint32 *lut /* 16384 entries */, ctx *matrix)
```

The MMX inner loop (`0x1001c563`–`0x1001c707`) processes 4 pixels of 3 planes
per iteration:

```asm
; per plane, per 16-bit sample:
and  eax, 0x3fff              ; 14-bit index
mov  eax, dword [esi+eax*4]   ; LUT lookup, 4-byte stride, low word used
...
; then, per output channel i:
pmulhw mm3, [edx+0x00/0x18/0x30]   ; c[i][0] * R
pmulhw mm4, [edx+0x08/0x20/0x38]   ; c[i][1] * G
pmulhw mm5, [edx+0x10/0x28/0x40]   ; c[i][2] * B
paddsw ...                          ; sum
paddsw mm3, [edx+0x60/0x68/0x70]   ; + offset[i]      (the 4th matrix column)
paddw  mm3, mm7                     ; + 0x8000        (signed→unsigned bias)
paddusw mm3, mm6                    ; + 0x7003 \  saturating clamp
psubusw mm3, [edx+0x58]             ; - 0xF003 /
```

So **the order inside stage 2 is: LUT first, matrix second, offset third, clamp
last.** [VERIFIED]

Matrix-context layout (0x78 bytes, each coefficient broadcast 4× as an
`int16` in a qword):

| offset | contents |
|---|---|
| `+0x00 … +0x40` | 3×3 coefficients, row-major (`c00 c01 c02 c10 c11 c12 c20 c21 c22`) |
| `+0x48` | `0x8000` — signed→unsigned bias |
| `+0x50` | `0x7003` — clamp add |
| `+0x58` | `0xF003` — clamp subtract |
| `+0x60/68/70` | per-channel offsets = matrix column 3 |

The clamp `+0x7003 / −0xF003` on unsigned-saturating arithmetic maps the result
to **0 … 0x0FFC = 4092**, i.e. **12-bit output**. [VERIFIED] This matches the
vendor's own UI label in `TLXClientDemo.exe`: *"Use Color Correction (12 bit
RPD)"*.

The scalar tail (`0x1001c785` onward, for widths not a multiple of 4) does the
same arithmetic in x87 and pins down the fixed-point scaling:

- coefficients are `int16`, converted with `× 2^-13` (`0x105761b8` = `1/8192`),
  so **`stored_int16 = coefficient × 8192`**;
- LUT entries are read as **unsigned 32-bit** (`fild dword`, `+2^32` if
  negative) and multiplied by `0.5` (`0x10574f40`);
- the channel sum is multiplied by `0.25` (`0x105756e0`) before the offset is
  added.

Net: **`out[i] = ( Σ_c coeff[i][c] · LUT[raw_c] ) / 8 + offset[i]`, clamped to
0…4092.** [VERIFIED]

### 2.3 What the 16384-entry LUT actually is

`CiConfigColorKodak::bLoadDefaultLut` (`TLA.dll:0x10013730`, class-ID 14,
fn-ID 65) generates it:

```c
lut[0] = S0 * 0x3FFF;
for (i = 1; i < 0x4000; i++)
    lut[i] = (int)( -(S0*S1) * log10( i * 6.103888176768602e-05 ) );
```

`6.103888176768602e-05` is **exactly `1/16383`** [VERIFIED — constant at
`0x100665f0`]. So

> **LUT[i] = −S · log₁₀(i / 16383)** — an *optical-density* transform, not a
> naïve invert.

This is confirmed independently by the shipped template
`Config/ColorCorrection/_ClientColNegLut.txt` (16384 lines, `index<TAB>value`).
With `S = 3500` the formula reproduces the file exactly:

| i | file value | `−3500·log₁₀(i/16383)` |
|---|---|---|
| 0 | 16383.0000 | (clamp) |
| 1 | 14750.3770 | 14750.377 |
| 2 | 13696.7720 | 13696.772 |
| 3 | 13080.4526 | 13080.4526 |
| 10 | 11250.3770 | 11250.377 |
| 16382 | 0.0928 | 0.0928 |
| 16383 | 0.0000 | 0.0 |

[VERIFIED] The negative→positive inversion is *inherent in the log*: density
increases where the negative is dense, i.e. where the scene was bright.

Two LUTs exist per configuration: `+0x40` (colour negative / B&W) and `+0x44`
(colour reversal), generated with different scale terms. Either can be replaced
by a client file (`ClientColNegLut.txt` / `ClientColRevLut.txt`) via
`bReadLut` (`0x10013050`, called with count `0x4000`). [VERIFIED]

### 2.4 What the 3×4 matrix is

`CiConfigColorKodak::bGetColorMatrix` (`0x100128a0`, fn-ID 196) returns
`this+0x200` for colour negative and `this+0x260` for colour reversal — 0x60 =
96 bytes = **3×4 doubles**. `bLoadClientMatrix` (`0x10012c20`, fn-ID 229) fills
them from `ClientColNegMat.txt` / `ClientColRevMat.txt`. [VERIFIED]

The shipped template `_ClientColNegMat.txt`:

```
coeff_0_0: 1.11882   coeff_0_1: -0.10130  coeff_0_2: -0.01161  coeff_0_3:  -82.60334
coeff_1_0: -0.20096  coeff_1_1:  1.10082  coeff_1_2:  0.11698  coeff_1_3: -586.90975
coeff_2_0: -0.11657  coeff_2_1:  0.04834  coeff_2_2:  1.08274  coeff_2_3: -707.78706
```

Reading: the 3×3 block is a **dye-crosstalk / unmixing matrix** in *density*
space (diagonal ≈ 1.1, small negative off-diagonals). Column 3 is a **per-channel
density offset in output code values** — R smallest, B largest, which is exactly
the signature of subtracting a C-41 orange mask / film-base density. [VERIFIED
values; the "orange-mask subtraction" reading is [INFERRED] but strongly
supported.]

So stage 2 as a whole is: *linear counts → density → unmix dyes → subtract film
base → clamp to 12-bit "RPD"*.

**RPD = Reference Printing Density.** Corroborated by
`anselinstalldir/dataPathItems/sba/SbaDPI/sba.map`, which documents the Ansel
metric enum: `metric == 1 → ANS_PD12`, `2 → ANS_RIM12`, `3 → ANS_ROM12`.
[VERIFIED from the shipped map file.]

### 2.5 Where Dmin fits [INFERRED]

`piDmin_R/_G/_B` are reported per scan, and `TLA.dll` has
`FN_bFindDmin` / `FN_bFindTmax` and an `INITIALIZE_ReportDminAsTmax` flag.
The matrix's offset column already *is* a fixed film-base subtraction, and the
`int16` matrix context used by the kernel is a per-instance copy distinct from
the `double` matrix in the config object. The natural reading is that the
measured Dmin is folded into the offset column when the `int16` context is
built. **I did not find that build routine**, so this is [INFERRED], not proven.
See §8.

---

## 3. Stages 3–5 — inside `bLoadImageFromBuffer` [VERIFIED]

`TLA.dll:0x1002caa0` (`FN_bLoadImageFromBuffer`). Confirmed from the
basic-block graph, so this is control-flow order, not just address order:

```
0x1002ce17  block →  call bApplyKodakColorCorrection   (0x1002ce44)
              ↓ success
0x1002ce71  branch: skip-rotate?  ──────────────┐
0x1002ce7f  block →  call bRotate               │      (0x1002ce9a → PIRotatePlanar)
              ↓                                 │
0x1002cf6c  block →  call [tbl+0x64]            │      PIAnselColorSceneBalancePlanar
              ↓                                 │
0x1002d067  block →  call bScale  ←─────────────┘      (0x1002d092 → PIScaleAndRotatePlanar)
```

Notes:

- Rotation happens **before** scene balance and **before** scaling. Both the
  rotate and the scene-balance blocks are individually skippable (the
  `SAV_UseCurrentRotation` / `SAV_UseColorSceneBalance` flags). [VERIFIED
  structure; the flag↔branch mapping is [INFERRED].]
- `PIScaleAndRotatePlanar` at the end also carries a rotation argument, so the
  final geometry is resolved there; the earlier `PIRotatePlanar` is
  [INFERRED] the "bake in the user's 90°/180° choice before analysis" step.

---

## 4. Stage 6 — `PIColorAdjustPlanar` [VERIFIED]

`PakonIMAu.dll:0x10013bc0`, invoked only from
`TLA.dll:0x1002a5a0` (`bApplyColorAdjustments`), which `bSaveToFile` calls
*after* `bLoadImageFromBuffer` and *before* the 16→8-bit conversion. [VERIFIED
from the `bSaveToFile` block graph.]

It builds a chain of named Kodak `Ima*` transform objects, in this order:

1. `ImaXformTransform_profile0` — input profile
2. `ImaXformTransform_SaturationProfile` — `satMinus15.pf` … `satPlus15.pf`, or
   `unity.pf`; selected by `params+0x50` (an 11-way switch, i.e. saturation
   −5…+5)
3. `ImaXformTransform_BnWEffectProfile` — `params+0x4c`:
   `1 → warm_bw_ld0_1_4-5.pf`, `2 → cold_bw.pf`, `3 → sepia_ld0_9_22.pf`,
   otherwise `unity.pf`
4. `ImaXformTransform_profile1` — output profile
5. `ImaXformCombineTransform_profileCombined` — **all four collapsed into one
   transform** (`SpCombineXforms` in `kodakcms.dll`)
6. `ImaMemorySourceOperation` — image source
7. `ImaUnsharpMaskOperation` — **sharpening, applied after the colour transform**

[VERIFIED — string references at `0x10013d59`, `0x10013f81`, `0x10014197`,
`0x10014352`, `0x10014569`, `0x10014735`, `0x10014dad`.]

### Which profiles are `profile0` / `profile1`

`PIBegin` (`0x10006a50`) `wcscpy`s its arguments into fixed globals; `TLA.dll`
supplies them from `CiConfigColorKodak` getters whose member offsets are
unambiguous (`TLA.dll:0x10016eb0` sets the paths; `0x10013c80`…`0x10013d40` are
the getters):

| config offset | file | → PakonIMAu global | role |
|---|---|---|---|
| `+0x2c0` | `romm.pf` | `0x106b2708` | alternate input profile |
| `+0x2d0` | `rpd.pf` | `0x106b1f08` | **`profile0`** |
| `+0x2e0` | `srgb.pf` | `0x106b1708` | **`profile1`** |
| `+0x2f0` | `ColRevLut1.pf` | `0x106b2f08` | colour-reversal profile |
| `+0x300` | `ColRevLutS6.lut` | (5th arg) | colour-reversal LUT |

[VERIFIED]

`params+0x48` selects the input profile: `0` → *no* input profile at all, `4` →
`romm.pf`, otherwise → `rpd.pf`. The "no input profile" case is what makes this
stage safe to run after the Ansel scene-balance step has already rendered to
sRGB. [VERIFIED that three branches exist and which profile each loads; the
exact enum→meaning mapping is [INFERRED].]

`EC_PI_RPD2ROMM_PROFILE` is the error code for the `rpd.pf → romm.pf` branch.
[INFERRED]

---

## 5. The Ansel scene-balance stage (stage 4) — it is **two-pass** [VERIFIED]

This is the single most important structural fact after the LUT/matrix order.
`PIAnselColorSceneBalancePlanar` does **not** compute a balance; it *applies* a
transform that was computed earlier for the whole roll.

`CiColorCorrectionAnsel::bColorSceneBalancePlanar`
(`PakonIMAu.dll:0x10002c40`) calls `getTransform(order, scene)`, then builds
`ImaMemorySourceOperation` + `transformGroupPtr` and runs it. If the transform
is missing it errors with *"bgetTransform failed"* / *"NULL Transform"*.
[VERIFIED from the diagnostic strings and their code references.]

The transform is produced by `TLA.dll:0x1003f720` (`FN_bKcdfsCorrections`),
whose call sequence is:

```
PIColorCorrectColRevPlanar or PIColorCorrectColNegPlanarScan   (prime the colour path)
PIAnselDeleteRoll
PIAnselStartNewRoll
  for each frame:  bSaveToMemory(…)  →  PIAnselAddScene
PIAnselEndRoll
PIAnselAnalyzeRoll
```

[VERIFIED — the calls are anchored on loads of `0x10080f84` at `0x1003f83a`,
`0x1003f855`, `0x1003f868`, `0x1003f9c0`, `0x1003fb6d`, `0x1003fc25`,
`0x1003fc40`.]

So the balance is **roll-level**: every frame is added, the whole order is
analysed together (`AnsOrder::analyzeOrder`,
`ColorNegativePath::analyzeBalanceOrder`), and only then does each frame get a
per-scene transform. A per-frame port that balances each frame independently
will *not* reproduce the Pakon look on a roll.

The legacy name "KCDFS" (also `EC_PI_KCDFS_INIT_FAILED`,
`SAV_ObsoleteUseColorKcdfs`, a stray path string `C:\KCDFS`) refers to the
*older* Kodak colour engine that this function now fronts; the function body
drives Ansel. [INFERRED]

### What Ansel does internally

`PakonIMAu.dll` statically links the whole Kodak "Ansel" framework — the source
paths are still in `.rdata` (`\Atc\ansel\src\libAREA.ansel\…`, `libSba.ansel`,
`libFugc.ansel`, `libShasta.ansel`, …), and the data files ship under
`anselinstalldir/dataPathItems/`. The colour-negative path class
`AnsColorNegativePath` exposes these stages (names from its own trace strings):

`declareAttributes`, `declareFalloff`, `declareFugc`, `declareAsea`,
`declareAutoTone`, `declareManualTone`, `declareSharpening`, `declareDei`,
`declareDtt`; then `analyzeAttributes`, `analyzeFalloff`, `analyzeAneOrder`,
`analyzeBalanceOrder`, `analyzeScpLutBalance`, `balanceAreaImage`,
`analyzeAsea`, `analyzeFugc`, `analyzeAutoTone` / `analyzeManualTone`,
`analyzePostBalance`, `analyzeSharpening`, `CalcDei`, `setShifts`; then
`exportAsea`, `exportFalloff`, `exportFugc`, `exportAutoTone`,
`exportManualTone`, `exportSharpening`, `exportsAggressiveToneScale`.

**[UNKNOWN] — the execution order of these sub-stages.** They are declare /
analyze / export triples, so the coarse order is certainly
declare → analyze → export, but the order *within* each group could not be
established from the binary: the strings are one-per-function trace labels, so
their address order is source order, not call order.

The final Ansel output rendering is a data-file-driven profile pair.
`anselinstalldir/dataPathItems/profile/profile-Rpd2Srgb.dpi` reads:

```
profile1 = Rpd2Pcs_HR200_QS_v5s10.pf
profile2 = Srgb_v2.pf
dataType = U8
renderIntent = P
colorSpaceMin = 0 ; colorSpaceMax = 255
```

i.e. **RPD → PCS → sRGB, 8-bit, perceptual**. [VERIFIED from the shipped file.]
That matches the vendor UI string *"Use Color Scene Balance Algorithm (8 bit
sRGB)"*.

`CiColorCorrectionAnsel::iProcessDigital` (`0x10010800`, 2712 bytes) is the
parallel entry for *imported digital* images: it loads `sRGB.pf` →
`AdobeGamut.pf` → `Romm.pf`, combines them, and applies
`ImaICCEffectOperation_ProfileFinal` — i.e. it converts an incoming sRGB image
*into* the ROMM working space so Ansel can process it. [VERIFIED]

---

## 6. Where the three film paths diverge

| | colour negative | colour reversal (slide) | black & white |
|---|---|---|---|
| dispatch case (`0x10014ff0`) | 1 | 2 | 4 **[INFERRED]** |
| density LUT | `cfg+0x40` (ColNeg) | `cfg+0x44` (ColRev) | `cfg+0x40` (shared with ColNeg) |
| 3×4 matrix | `cfg+0xd8` / global `+0x1650` | `cfg+0x168` / global `+0x16e0` | `cfg+0x48` |
| client override files | `ClientColNegLut.txt`, `ClientColNegMat.txt` | `ClientColRevLut.txt`, `ClientColRevMat.txt` | — |
| extra stage | none | `ColRevLut1.pf` + `ColRevLutS6.lut` applied **after** LUT+matrix (`PIColorCorrectColRevPlanar` at `0x10009360` calls the shared kernel first, then builds further `Ima*` ops) | — |
| Ansel path | `AnsColorNegativePath` | `AnsColorPositivePath` | — |
| B&W / sepia toning | — | — | done later, in `PIColorAdjustPlanar` step 3 (`warm_bw` / `cold_bw` / `sepia`) |

[VERIFIED for the dispatch table, the LUT/matrix pointers, the ColRev extra
stage's existence and its two data files. [INFERRED] that case 4 is B&W.]

The error codes corroborate the split: `EC_PI_INPUT_PROFILE` /
`EC_PI_OUTPUT_PROFILE` / `EC_PI_COMBINE_INPUT_OUTPUT_PROFILE` for the main path,
and the `EC_PI_CR_*` family (`CR_INPUT_PROFILE`,
`CR_COMBINE_INPUT_OUTPUT_PROFILE`, `CR_LUTS6`) for the colour-reversal path.
`CR` = colour reversal. [INFERRED, consistent with everything else.]

The `defaults.ini` in `Config/ColorCorrection/` confirms the same three-way
classification at the film-product level: numbered sections per film product
code, plus `[BnW]`, `[POSITIVE]` and `[IMPORTED]`. [VERIFIED]

---

## 7. Bit depths and buffers [VERIFIED unless noted]

- Input to stage 2: 16-bit planar, values masked to 14 bits (`and eax,0x3fff`).
- Planes are contiguous: plane stride = `2·width·height` bytes; the kernel reads
  `[src]`, `[src+stride]`, `[src+2·stride]`.
- Stage 2 is **in-place** (`src == dst` in the wrapper's argument shuffle).
- Output of stage 2: 12-bit RPD in 16-bit containers, clamped 0…4092.
- Stages 3–6 stay 16-bit planar.
- `bPlanar16ToPlanar8` (`TLA.dll:0x1002a1d0`) / `bPlanarToDib8` (`0x1002a2b0`)
  do the depth reduction, after colour adjustment.
- File output is 8-bit (`PISaveFilePlanar_8`, `PIFileSpecsPlanar_8`).
- The 16-bit planar path exposed to clients
  (`iFILE_FORMAT_SAVE_TO_MEMORY_PLANAR_16`) taps the buffer before that
  reduction. [INFERRED]

---

## 8. What is still unresolved

1. **Where DICE (scratch removal) sits.** [UNKNOWN]
   `TLA.dll` loads `DMLDICELib.dll` in `CiDLLDigitalIce`
   (`0x10017650`), caching `DMLDICEBegin@+0x24`, `DMLDICEEnd@+0x28`,
   `DICEVersion@+0x30`, `DMLDICEProcess@+0x34`, `DMLDICEDefectCount@+0x38`, and
   the object is constructed inside the scan worker at `0x1003f26c`
   (stored at `**(ctx+0x48)`). `DMLDICEBegin` is called immediately with a
   static tag containing the value `14` — consistent with 14-bit data.
   **I could not locate the `DMLDICEProcess` call site**; only `DMLDICEEnd`
   (`0x10018063`, destructor) is reachable by pattern search.
   *Position in the diagram is [INFERRED]* from the constraint that DICE needs
   the infrared plane, which only exists in the raw scan buffer — therefore it
   must run before stage 2 destroys the 4-plane layout.
   **Evidence that would resolve it:** a full decompilation of the scan worker
   (the unnamed function spanning ≈ `0x1003ee20`–`0x10041000`), or a runtime
   trace of `DMLDICELib.dll` entry points under Wine/a VM.

2. **How measured Dmin enters the maths.** [UNKNOWN]
   Proven: the matrix offset column is a fixed per-channel density subtraction,
   and the `int16` MMX context is a *derived copy* of the `double` 3×4 matrix.
   Not proven: whether `FN_bFindDmin`'s per-scan result modifies that offset
   column, modifies the LUT, or is merely reported to the client.
   **Evidence that would resolve it:** find the routine that converts
   `cfg+0x200` (3×4 doubles) into the `int16` context at `cfg+0x48/0xd8/0x168`
   — it must multiply coefficients by 8192 — and check whether it reads
   `piDmin_*`. Failing that, scan the same negative twice with
   `INITIALIZE_ReportDminAsTmax` toggled and diff the output.

3. **The 3×10 polynomial.** [UNKNOWN]
   `CalibrationGetColorMatrix3By10` and `FN_bReadMatrix_3x10` exist, but the
   colour-correction kernel is unambiguously 3×3 + offset. The 3×10 is
   therefore **not** in the per-pixel path examined here. [VERIFIED negative
   result.] It is most likely a *calibration-time* fit used to derive the 3×4,
   or used by the calibration wizard only. **Evidence that would resolve it:**
   locate the callers of `FN_bReadMatrix_3x10` (fn-ID 279) and check whether its
   output ever reaches `cfg+0x200`.

4. **Ansel's internal stage order.** [UNKNOWN] — see §5.
   **Evidence that would resolve it:** the `.map` / `.dpi` files under
   `anselinstalldir/dataPathItems/` are plain text and name each capability
   (`sba.map`, `color.map`, `profile.map`, `contrast.map`, `flare.map`,
   `fugc-lutMap.map`, …); a systematic read of all of them, plus
   `AnsProcessingPathMgr::findPath`, would give the capability graph.

5. **Exact meaning of dispatch case 4** (B&W vs imported). [INFERRED only]
   **Evidence that would resolve it:** the `iCurrentScanType` enum in the type
   library, or a trace of `FN_bSetCurrentScanType`.

6. **`ColRevLutS6.lut` format and where in the reversal path it applies.**
   [UNKNOWN] The file name reaches `PIBegin` as the 5th profile argument;
   `EC_PI_CR_LUTS6` exists. The Ansel tree also ships
   `common/luts6_postROMM_equalRGBshort.lut`, whose name suggests "LUT set 6,
   applied *after* ROMM" — which would place it late in the reversal chain.
   [INFERRED] **Evidence that would resolve it:** parse both `.lut` files
   (see `docs/08-profile-format.md` tooling) and find the consumer of `PIBegin`
   argument 12 inside `PakonIMAu.dll`.

7. **Whether `PIRotatePlanar` before scene balance is user rotation or an
   internal orientation normalisation.** [INFERRED as the former]

---

## 9. Minimum viable reimplementation order

For the macOS port, the order that must be respected:

1. de-Bayer / gain / offset / fixed-pattern correction — **scanner-side**, done
   by calibration before the data reaches this pipeline (`FN_bCalibrate*`,
   `FN_bKcdfsCorrections` is *not* part of it).
2. `D = −S·log₁₀(raw / 16383)` per channel, via a 16384-entry table.
3. `out = (M₃ₓ₃ · D)/8 + offset₃`, clamp 0…4092. **12-bit RPD.**
4. Rotation.
5. Roll-level scene balance → per-frame transform → apply. Renders
   RPD → PCS → sRGB (`Rpd2Pcs_HR200_QS_v5s10.pf` + `Srgb_v2.pf`).
6. Scale.
7. Combined CMS transform `[input] ∘ saturation ∘ bw/sepia ∘ [output]`, then
   unsharp mask.
8. 16 → 8 bit, write file.

Getting 2 and 3 the wrong way round, or applying the sharpening before the
colour transform, or balancing per-frame instead of per-roll, will each visibly
break the "Pakon look".
