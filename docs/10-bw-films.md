# 10 — Black & White Films (HP5 Plus, FP4 Plus, Delta 3200)

How the Pakon treats traditional silver B&W film differently from C-41 colour
negative, and what a macOS implementation needs in order to scan Ilford
HP5 Plus, FP4 Plus and Delta 3200 well.

Evidence: strings and config files from the `Pakon Update 2` distribution
(paths below), the recovered TLX API ([04-api-surface.md](04-api-surface.md)),
Ilford's published datasheets, and community sources (labelled as such).
The binary `.pf` container format is documented separately in
`08-profile-format.md` — this document deliberately reasons about the B&W
profiles only from their names, sizes and the code that references them.

---

## A. How the B&W path differs from the colour-negative path

### A1. B&W is a scan *class*, not a film *product* — [VERIFIED]

The film-colour enum has two distinct B&W members plus a wildcard:

```
FILM_COLOR_NEGATIVE   FILM_COLOR_POSITIVE
FILM_COLOR_BnW_NORMAL FILM_COLOR_BnW_C41   FILM_COLOR_BnW_ANY
```

`Config/ColorCorrection/defaults.ini` (per-film-product colour-slider
defaults) lists ~90 numeric product IDs grouped by manufacturer for colour
film, but B&W gets exactly one category section:

```ini
;Black and White (C41 and regular)
[BnW]
```

alongside `[POSITIVE]` and `[IMPORTED]`. PSI's UI matches: film-type choices
"Black and white normal" / "Black and white C41", and per-class registry
preferences `ColorPreferences\BnW`, `35mmBnW`, `24mmBnW` (PSI.exe strings).
There is no per-product machinery for B&W anywhere in the shipped config.

**Consequence:** adding HP5+, FP4+ and Delta 3200 does *not* mean adding
film-product entries. The scanner-side distinction the pipeline cares about
is only the class: silver B&W vs chromogenic B&W.

### A2. Why BnW_NORMAL vs BnW_C41 exist — [VERIFIED mechanism, standard optics]

The two enums encode a physical difference in the developed image:

| | BnW_NORMAL (HP5+, FP4+, Delta 3200) | BnW_C41 (XP2 Super, BW400CN) |
|---|---|---|
| Image-forming material | metallic silver | C-41 dyes (silver removed in bleach/fix) |
| Spectral density | essentially neutral/flat | dye absorption, brownish; BW400CN adds a mask tint |
| Infrared | **opaque** — silver blocks/scatters IR | transparent, like colour negative |
| Digital ICE (IR channel) | **cannot work** — the whole image looks like a defect | works normally |

The IR point is why the split must exist: the F-135 Plus has a fourth IR LED
channel driving Kodak DICE scratch removal (`iCurrent_Ir`,
`SCAN_UseScratchRemoval`, `DMLDICELib.dll`). Silver-image film defeats
IR-based dust detection — long-established for all ICE scanners
(Wikipedia: Digital ICE, Infrared cleaning; confirmed by Pakon users).
BnW_C41, being a dye image, keeps ICE and is calibrated alongside colour
negative — PSI's calibration wizard labels the gain strip
**"35mm Color Negative / B&W C41"** [VERIFIED string; the pairing of CN with
B&W-C41 in one calibration strip is INFERRED from that label].

### A3. Each class gets its own analog front end — [VERIFIED]

TLA.dll (the F-135 back end) writes a calibration log with one line per
class, and the class list is exactly the four film colours:

```
%-14s Gain - R = %2.2f, G = %2.2f, B = %2.2f; Offset - R = %d, ...
Exp - R = %4u, G = %4u, B = %4u; IrLEDOnTime = %4u, VisIrRatio = %2.2f, ...
COLOR_NEGATIVE   BnW_C41   COLOR_POSITIVE   BnW_NORMAL
```

So traditional B&W has its own per-channel analog gain / offset / CCD
exposure / lamp / IR settings, calibrated separately from colour negative.
PSI exposes it as a first-class calibration option: *"35 mm black and white
film scanning"*, *"24 mm black and white film scanning"* (distinct from the
negative and positive options). PTS's `Calibration.dll` parameterises
calibration by `iFilmColor` and errors with "Film Color not supported".

This is physically necessary: a colour negative's orange mask forces very
unequal R/G/B channel gains, while a silver negative is neutral — near-equal
channel response, different overall exposure point.

Storage detail: TLA.dll contains registry key fragments `\ColNeg`, `\ColPos`,
`\BnW_C41` but **no plain `\BnW` key** [VERIFIED strings]; TLB/TLC (F-235/335)
have `\ColNeg`, `\ColNegIr`, `\BnW_C41`, `\BnW_C41Ir`, `\BnWIr`. Where the
BnW_NORMAL visible-channel values persist on the F-135 (fourth registry key
built at runtime, EEPROM section, or derived from another class) is
**[UNKNOWN]** — the log format proves the class is calibrated, not where it
is stored.

### A4. There is no B&W matrix and no B&W inversion LUT — [VERIFIED absence]

The colour-negative path's host-side assets are explicit and film-class-named:

- `_ClientColNegMat.txt` — 3×4 matrix; note the large per-channel constant
  offsets (−82.6 / −586.9 / −707.8) which subtract the orange-mask/Dmin
  pedestal per channel;
- `_ClientColNegLut.txt` — 16,384-entry monotone-*decreasing* LUT
  (0 → 16383.0 … downward): the density-domain inversion table;
- `ColRevLut1.pf` / `ColRevLutS6.lut` for colour reversal;
- registry-stored `NegMatrix0..11` and `PosMatrix0..11` in TLA
  (`0..29`, i.e. 3×10 polynomial, in TLB/TLC).

There is no `BnWMatrix`, no B&W client LUT, no B&W entry in the
input/output-profile error set (`EC_PI_INPUT_PROFILE`, `EC_PI_OUTPUT_PROFILE`,
`EC_PI_RPD2ROMM_PROFILE`, `EC_PI_CR_INPUT_PROFILE` — CN, output, RPD→ROMM and
colour-reversal only).

**[INFERRED]** B&W scans therefore ride the colour-negative inversion
machinery (per-channel LUT + Neg matrix) with only the front-end calibration
changed. Community observation supports this: PSI B&W output "still ha[s]
some color and ha[s] to be turned grayscale" and comes out "way contrasty and
annoyingly sepia toned" — exactly what a neutral silver negative pushed
through CN-tuned colour processing would look like (see A5, and sources in
§C).

### A5. The Ansel scene-balance engine has no B&W path — [VERIFIED]

`PakonIMAu.dll` (Kodak "Ansel" imaging pipeline) enumerates its processing
paths: `ColorNegativePath` (`AnsCnEnhancedPath`, `AnsCnPremiumPath`,
`AnsCnOpticalPath`, `AnsCnLockbeamPath`), colour-positive
(`AnsCpBalancePath`, `AnsCpRestorePath`, `AnsCpLockbeamPath`) and
digital-camera (`AnsDc*`). **No B&W path exists.** The `dsba`
(scene-balance) parameter files in `anselinstalldir/dataPathItems/` cover
`colorPositive`, `digitalCamera` and a colour-negative default — nothing for
B&W.

So beyond the front end, the Pakon has no B&W-specific rendering
intelligence at all; B&W frames get colour-negative scene balancing, whose
colour-cast correction has nothing valid to lock onto in a neutral image.
This is the architectural root of the community's contrast/tint complaints,
and the main thing a macOS port can do *better* rather than merely reproduce.

### A6. The B&W `.pf` files are output *toning effects*, not film profiles — [VERIFIED]

`PutPictureBnWEffect` / `GetPictureBnWEffect` (`iBnWEffect`) is a per-picture
property — an effect applied to an already-rendered image, available for
*any* film type (PSI applies it from a "Black and White Effect" dialog with
options including "Sepia"; also "Desaturate" in the adjustments list).
`PakonIMAu.dll` contains the loader (`ImaXformTransform_BnWEffectProfile`)
and names the files directly, in one list with the saturation-effect
profiles:

```
warm_bw_ld0_1_4-5.pf   cold_bw.pf   sepia_ld0_9_22.pf
unity.pf   satPlus03..15.pf   satMinus03..15.pf
```

A third variant, `cold_bw_ld5_n0-5_n2-5.pf`, ships in
`anselinstalldir/icc/effect/`. The B&W trio are 59,128–59,488 bytes — a
tight size family, distinct from the 77,948–77,956-byte `sat*` family —
consistent with one common structure per effect type (format details:
`08-profile-format.md`).

**Filename suffix decode — [INFERRED, medium-high confidence]:** the suffix
is a CIELAB tint offset: `ld` = L* delta, then a* delta, b* delta, with `n`
meaning minus and `-` the decimal point:

| file | L*Δ | a*Δ | b*Δ | reading |
|---|---|---|---|---|
| `sepia_ld0_9_22.pf` | 0 | +9 | +22 | classic sepia tone (strong yellow-red) |
| `warm_bw_ld0_1_4-5.pf` | 0 | +1 | +4.5 | slightly warm neutral |
| `cold_bw_ld5_n0-5_n2-5.pf` | +5 | −0.5 | −2.5 | lifted, slightly blue "cold tone" |

The sepia values landing on textbook sepia a*/b* offsets is what supports
the decode. Which `iBnWEffect` integer maps to which profile is **[UNKNOWN]**
(needs a run against real hardware or PSI).

**Consequence:** none of these files will help scan HP5+ — they are
cosmetic post-render toners. Do not go looking for `hp5.pf`; the concept
does not exist in this architecture.

### A7. DX film-edge reading and B&W — [VERIFIED mechanics, INFERRED mapping]

The scanner reads the DX film-edge barcode during transport (dedicated DX
sensor pairs, `PakonDxLog.txt`, log line
`... Product = %d, Specifier = %d, Scan Warnings ...`, API
`piFilmProductFromStrip` / `piFilmSpecifierFromStrip`, warnings
`SCANW_DX_GOOD/_BAD`). The edge barcode encodes a 7-bit "DX number part 1"
and 4-bit "part 2" (Wikipedia: DX encoding) — matching the Pakon's
Product / Specifier pair sizes exactly **[INFERRED: Product = part 1,
Specifier = part 2]**.

Supporting arithmetic: community-collected DX numbers (Flickr "DX barcode
numbers on 135 film" thread — community data, unverified) give
HP5+ = 017534/017533, FP4+ = 017564/017563, Delta 3200 = 017384,
Delta 100 = 017593, Delta 400 = 017524, XP2 Super = 017644. Taking the
middle four digits as part1×16+part2 yields part 1 = **109** for
HP5+/FP4+/Delta 100/400, **108** for Delta 3200, **110** for XP2 Super — and
`defaults.ini`'s ";Ilford Imaging" block is exactly products
`[105]…[110]`. Three independently-derived values landing inside the
labelled six-ID block is strong support, but the ×16 packing rule itself is
not confirmed by a primary source — treat as [INFERRED] until a known film
is scanned and the logged Product value checked.

Practical upshot: Ilford's conventional B&W films are DX-coded (cassette
*and* edge barcode — the edge code is a latent image that develops with the
film), so auto-identification of HP5+/FP4+/D3200 rolls is *possible*. It is
a nice-to-have: the pipeline only branches on class, not product (A1).
Whether the DX reader reliably reads B&W-developed edge codes (different
silver density than C-41 dye codes) is untested — expect `SCANW_DX_BAD`
sometimes; the scan must not depend on it.

---

## B. What adding HP5+ / FP4+ / Delta 3200 actually requires

**Short answer: no new film-product entry and no new `.pf` profile. It is
(1) the BnW_NORMAL scan class + per-unit B&W gain calibration on the
scanner side, and (2) a host-side density-domain inversion curve — which the
Windows stack never had for B&W and which we should build properly.**

Concretely, for the macOS implementation:

1. **Scan class.** Issue the scan with `FILM_COLOR_BnW_NORMAL` (film colour
   is a scan parameter — PSI/TLXClientDemo both expose it). This selects the
   B&W front-end calibration class (A3). For XP2 Super / BW400CN use
   `FILM_COLOR_BnW_C41` instead.
2. **Scratch removal off** for silver film (`SCAN_UseScratchRemoval` clear).
   Allow it for BnW_C41. Do not offer ICE on BnW_NORMAL at all (A2).
3. **Calibration data.** The unit must hold BnW-class gain/exposure
   calibration (Gain/Offset/CcdExposure per channel). Read and archive the
   EEPROM/registry calibration before anything else (see warning in
   [04-api-surface.md](04-api-surface.md)). If the B&W class was never
   calibrated on a given unit, the calibration wizard path
   (`CalibrationBegin/Acquire/...`) with a B&W strip is the vendor-sanctioned
   route — write paths only after EEPROM backup.
4. **Capture raw.** Save 16-bit planar (`SAVE_TO_MEMORY_PLANAR_16` /
   raw-to-disk). Do not use the 8-bit rendered path for B&W — this is where
   the Windows stack loses the game (A4/A5).
5. **Invert on the host, in density space, per roll** (see §C below for the
   per-stock numbers):
   - Estimate film-base level per channel from the clear rebate
     (inter-frame gaps / sprocket margin). The API's `iDmin_R/_G/_B`
     properties exist for exactly this per-roll base measurement
     [VERIFIED properties; semantics INFERRED] — cross-check against our own
     rebate sampling.
   - Convert linear transmittance to density `d = −log10(x / x_base)` so the
     film base maps to d = 0. This replaces both the CN matrix's constant
     offsets and the 16,384-entry CN LUT (which is precisely a density-domain
     inversion table for masked film — [VERIFIED shape], see A4).
   - Collapse to one channel *after* base normalisation: a weighted mean of
     R,G,B (silver is spectrally neutral, so averaging mostly buys ~√3 noise
     reduction; green-only is a defensible alternative if channel focus
     differs). Do not run any colour-balance logic.
   - Map density → output with a print-like tone curve: linear-ish mid
     section scaled so the stock's useful density range fills the output,
     soft toe and shoulder rolloff at both ends. Community practice agrees:
     Negative Lab Pro recommends its "Linear + Gamma" profile for B&W
     ("gamma set to mimic traditional black and white photo paper")
     [COMMUNITY].
   - A plain linear invert (`65535 − x`) is wrong because equal *scene* steps
     are equal *density* steps (the film's D–logE line), which are
     *multiplicative* in transmittance: linear inversion compresses shadows
     (thin areas) and stretches highlights, and it hard-codes the base level
     into black instead of anchoring on the measured rebate.
6. **Optional toning** (sepia/warm/cold) as Lab-offset presets per A6's
   decode — cosmetic, off by default.
7. **Per-stock presets** = small parameter sets for step 5 (expected base
   density, aim contrast, shoulder behaviour) — §C. Nothing else is
   per-stock.

---

## C. Per-stock handling

Manufacturer data below is from Ilford/HARMAN technical datasheets
(HP5+ and FP4+ rev. Nov 2018; Delta 3200 rev. Jun 2025), fetched from
ilfordphoto.com. Curve readings are my measurements off the published
graphs — treat as ±0.05D / ±10% indicative, not spec.

| | HP5 Plus | FP4 Plus | Delta 3200 |
|---|---|---|---|
| ISO (datasheet) | 400/27° | 125/22° | **1000/31°** measured in ID-11; *sold* as EI 3200 |
| Recommended EI range | 400 native; usable 400–3200 pushed | 125 native; 50–200 | EI 3200 nominal; good 400–6400; usable to 25000 with tests |
| Published curve | Ilfotec HC 1+31, 6½ min: long straight line, D≈2.0 at top of range; average gradient ≈0.65 over ~2.5 log E [graph reading] | Ilfotec HC 1+31, 8 min: S-curve with a **pronounced shoulder** flattening near D≈1.9–2.0 [graph reading] | DD-X 1+4 & Microphen at 7/9/12/16 min: family of curves, long toe, Dmax ≈2.0–2.4 at 16 min [graph reading]; Ḡ vs time published: ~0.4→0.9 (DD-X), ~0.35→0.8 (Microphen) |
| Base+fog (from curve floor) | ≈0.2 [graph reading] | ≈0.15–0.2 [graph reading] | **≈0.35–0.5, visibly elevated**, rising with push time [graph reading] |
| Spectral sensitisation | panchromatic, cutoff ≈650 nm (wedge spectrogram, 2850 K) | panchromatic (wedge spectrogram, 2850 K) | panchromatic, extended red, cutoff ≈690 nm (wedge spectrogram, 2856 K) |
| DX | DX-coded cassettes [datasheet]; edge/cassette DX number 017533/017534 [COMMUNITY] → product 109 [INFERRED] | DX-coded cassettes [datasheet]; 017563/017564 [COMMUNITY] → product 109 [INFERRED] | DX-coded cassettes [datasheet]; 017384 [COMMUNITY] → product 108 [INFERRED] |

Film spectral *sensitivity* matters only at exposure time; at scan time the
silver image is neutral, so the table's spectrogram rows are context, not
scanner configuration. What the scanner sees is the density figures.

### HP5 Plus — the baseline stock

Well-behaved: low base, long straight line, gentle toe. Default preset:
base-anchored inversion, aim gradient mapping ~2.0D of negative range onto
the output scale, standard soft shoulder. Pushed HP5 (EI 800–3200 is
explicitly supported by Ilford) develops to higher contrast and higher
Dmax — the per-roll base anchor plus a contrast slider covers it; no
separate preset needed.

### FP4 Plus — respect the built-in shoulder

FP4+'s published curve already rolls its highlights off above ~D 1.8; the
negative has done part of the tone mapping. Preset: slightly lower aim
contrast and a *weaker* additional shoulder than HP5+ (double-shouldering
flattens skies). Low fog and fine grain make it the easiest of the three at
the sensor level.

### Delta 3200 — the special case

Delta 3200 is a true-ISO-1000 emulsion engineered to be push-processed: the
datasheet is explicit that 1000/31° is the ISO measurement and EI 3200 "and
given extended development" is the design point. For scanning this means:

- **High base+fog, always.** Even normally processed rolls sit ≈0.2–0.3D
  above HP5+'s base; push development raises fog further. The front-end
  exposure for the roll must be referenced to the *measured* film base, not
  an absolute level, or every frame starts a stop down. This is the stock
  that most stresses the per-roll Dmin anchor in §B.5.
- **Shadows are thin and low-contrast.** A push raises development contrast
  in the mids/highs but cannot create shadow exposure that never happened;
  shadow detail lives just above fog at low local contrast, embedded in
  heavy grain. Capture in 16-bit, anchor black *below* the fog level (do
  not clip to Dmin), and apply shadow boost gently — this is where 8-bit
  render-then-adjust visibly falls apart.
- **Expect roll-to-roll variance.** EI 400 through 25000 are all legitimate
  uses; Dmax and fog vary with the chosen development. The preset should
  set expectations (base ≈0.4, aim range ≈1.8–2.2D above base) and let the
  per-roll measurement dominate.
- Frame detection risk: dense, foggy, grainy rolls with low inter-frame
  contrast are harder to frame; the Pakon frames from perforations + image
  content (`SCAN_AggressiveFraming`, `FRAMING_RISK_*`). Anticipate more
  manual reframing on D3200 [INFERRED from mechanism; community reports of
  Pakon framing errors are generic, not D3200-specific].

### Community knowledge on Pakon + B&W — [COMMUNITY, treat as anecdote]

Consistent across sources, and consistent with §A's findings:

- PSI renders traditional B&W too contrasty and with a colour cast
  ("way contrasty and annoyingly sepia toned" — Toivonen; "black & white
  scans still have some color and have to be turned grayscale ... lower the
  contrast to at least −20, possibly −40" — The Resurrected Camera).
- The favoured workaround is TLXClientDemo with the greyed-out B&W/positive
  film-colour options force-enabled via an AutoIt script, Base16 raw planar
  16-bit output, then external inversion (custom converters, Ali Bosworth's
  Pakon Planar Raw Converter with `--mode bw`, or Negative Lab Pro).
- Nobody in the community reports per-stock scanner settings for B&W — all
  differentiation is done in post. This matches the architecture (A1): the
  scanner genuinely has nothing per-stock to set.

Our design in §B is essentially "what the community converged on, built in
properly, minus the AutoIt duct tape".

---

## D. What cannot be determined without hardware testing

Stated plainly:

1. **The actual BnW_NORMAL analog settings** (per-channel gain/offset/CCD
   exposure) for our unit — they are per-unit calibration products, not
   shipped constants; and where the F-135 persists them (A3 storage gap).
2. **Whether tlx applies the Neg matrix/LUT or a bypass to BnW_NORMAL
   pixels** in the rendered path (A4 inference). Only disassembly of
   `tlx.dll`/`PakonIMAu.dll` or an A/B scan of a step wedge settles it —
   irrelevant to the port if we take raw planar output, but it caps how much
   we trust rendered-path comparisons.
3. **Raw linearity**: whether 16-bit planar data is linear CCD counts after
   analog gain (assumed here and by community converters) and whether any
   fixed-pattern/dark-frame correction is already applied.
4. **DX reading of B&W edge codes in practice**, and confirmation of the
   Product=DX-part-1 mapping (scan a known HP5+ roll, check the logged
   Product/Specifier against 109).
5. **`iBnWEffect` value → profile mapping** (A6), if we ever care about
   PSI-compatible toning semantics.
6. **`iDmin_R/G/B` semantics** — measured per roll vs calibration constant,
   and measurement timing (`INITIALIZE_ReportDminAsTmax` suggests
   configurable reporting).
7. **Framing reliability on dense/pushed Delta 3200 rolls.**
8. Every sensitometric number in §C's table that is marked "graph reading" —
   good enough to size the pipeline, not a substitute for scanning a real
   step wedge or a known-exposure roll per stock.

---

## Sources

**Local binaries/config** (all under
`/Users/guy/Downloads/Pakon Update 2/`): `fx35install/.../F-X35 COM
SERVER/Config/ColorCorrection/defaults.ini`, `_ClientColNegMat.txt`,
`_ClientColNegLut.txt` and the `.pf` files listed in A6; UTF-16LE/ASCII
strings from `program files/Pakon/PSI/PSI.exe`, `F-X35 COM SERVER/tlx.dll`,
`TLA.dll`, `TLB.dll`, `TLC.dll`, `PakonIMAu.dll`, and
`Pakon/PTS/Calibration.dll`; `anselinstalldir/dataPathItems/` and
`anselinstalldir/icc/effect/`.

**Manufacturer:**
- Ilford HP5 Plus Technical Information, Nov 2018 —
  https://www.ilfordphoto.com/amfile/file/download/file/1903/product/691/
- Ilford FP4 Plus Technical Information, Nov 2018 —
  https://www.ilfordphoto.com/amfile/file/download/file/1919/product/690/product_datasheet_fp4plus.pdf
- Ilford Delta 3200 Professional Technical Information, Jun 2025 —
  https://www.ilfordphoto.com/amfile/file/download/file/1913/product/682/

**Reference:**
- DX encoding (cassette barcode digit layout; edge-barcode 7-bit part 1 /
  4-bit part 2 / frame number) — https://en.wikipedia.org/wiki/DX_encoding
- Digital ICE / infrared cleaning vs silver B&W —
  https://en.wikipedia.org/wiki/Digital_ICE,
  https://en.wikipedia.org/wiki/Infrared_cleaning

**Community (anecdotal, labelled [COMMUNITY] above):**
- Toivonen, "Getting nice 16 bit black and white/slide scans from the Kodak
  Pakon F135+" —
  https://toivonenphoto.com/blog/2021/2/27/getting-nice-16-bit-black-and-white-scans-from-the-kodak-pakon-f135
- The Resurrected Camera, Pakon posts —
  https://resurrectedcamera.wordpress.com/tag/pakon/
- Pakon Planar Raw Converter — http://pprc.alibosworth.com/
- Negative Lab Pro forum, Pakon threads —
  https://forums.negativelabpro.com/t/pakon-scanners-negative-lab-pro/1803
- Flickr group thread "DX barcode numbers on 135 film (please contribute)" —
  https://www.flickr.com/groups/67377471@N00/discuss/72157634429783414/
