# 56 — The Ansel colour engine's real data flow, captured from a live render

**Date: 2026-08-13.** Companion to `docs/55`. Same method — API Monitor hooking
`CreateFileA`/`CreateFileW` inside `PSI.exe` — but filtered on file opens during
an actual **render**, not initialisation. 218 distinct vendor data files.

## The engine's root, and a correction to an assumption

The vendor's Ansel install is **inside the COM server directory**:

```
C:\Program Files\Pakon\F-X35 COM Server\anselInstallDir\dataPathItems\...
```

Not a separate Ansel product. `pathConfiguration.dpi` is the first file the
engine opens and is presumably what resolves everything below it.

Also opened, before `pathConfiguration.dpi`:
`F-X35 COM Server\Config\ColorCorrection\ColRevLutS6.lut`, and elsewhere
`Config\ColorCorrection\srgb.pf` and `unity.pf`. Note the port's ICC pair is
`dataPathItems\profile\Rpd2Pcs_HR200_QS_v5s10.pf` + `Srgb_v2.pf` — and
`Config\ColorCorrection\srgb.pf` is a **different file entirely** (3,144 B,
matrix/TRC) from `Srgb_v2.pf` (124,246 B, `mft2` CLUT). Whether the render path
uses one, the other, or both for different stages is `[UNKNOWN]` and worth
settling.

## Stage inventory

Every directory the engine touched, i.e. the full stage list:

```
area        pnr         nra        noiseTable   color      dtt
sra         common      filmLut    flesh        pan        sba
SCPLut      orderOrientation       dei          falloff    fugc
cna         dra         tonehelper contrast     pfd        sharpenAdjust
adaptSharp  ane         flare      shasta       exposure   dyefade
dsba        lighting    gainOffset neutralGammaAdjust
noiseFiltering          blackPrinting           deRender   reRender
sharpenRecommend        jpegDeblock
```

The six subsystems the port has ported (`cna`, `dra`, `toneHelper`, `contrast`,
`ast`, `citras`) are a **subset** of this. Stages with no port equivalent at all
include `pfd`, `dtt`, `dsba`, `ane`, `dei`, `falloff`, `flare`, `dyefade`,
`lighting`, `gainOffset`, `blackPrinting`, `noiseFiltering`, `deRender`,
`reRender`, `neutralGammaAdjust`, `pan`, `area`, `nra`, `pnr`.

## Findings against the port's open questions

**SRA — the suspected cause of the range collapse (`docs/65`).** The engine
opens a far richer SRA set than the port models:

```
sra\sra-params-metric-default.dpi   -rim12   -rom12
common\common-sraFwdLut-metric-default.lut   -erimm  -rim12  -rom12
common\common-sraBkLut-metric-default.lut    -rim12  -rom12      <- a BACK LUT
common\common-sraData-metric-default.dpi     -erimm  -rim12  -rom12
```

There is a **metric** axis (`default` / `erimm` / `rim12` / `rom12`), a
**backward** LUT as well as a forward one, and separate params and data DPIs.
The port loads a single SRA forward LUT. If the vendor selects a different
metric variant for CN-Enhanced, the port is applying the wrong curve — which
is exactly the shape of the 7x range collapse measured in `docs/54`.

**toneHelper has no CN-Enhanced file.** The tree is:

```
tonehelper\toneHelper-CNFps.dpi   toneHelper-CNPremium.dpi
toneHelper-DCPremium.dpi          toneHelper-default.dpi      toneHelper.map
```

No `toneHelper-CNEnhanced.dpi`. So on the CN-Enhanced path toneHelper must
resolve through `toneHelper.map` to `-default` (or to `-CNPremium`). `docs/66`
lists this resolution as an open question; the answer is constrained to those
four files.

**contrast DOES have a CN-Enhanced file**: `contrast\contrast-CNEnhanced.dpi`,
alongside `-CNPremium`, `-DCPremium`, `-romm`, `-rpd`, `ansel-contrast-default`
and `contrast.map`. So contrast is path-specialised where toneHelper is not.

**`pfd` is a real stage with CN- and format-specific data**, matching the
`analyzeAutoTone` chain that `pakon_ansel.py`'s comment lists as
"cna, dra, toneHelper, contrast, ast, **pfd**, citras":

```
pfd\pfd-CN-35-default.dpi   pfd-CN-110-default   pfd-CN-120-default
pfd-CN-APS-default          pfd-CN-archive-default   pfd-CN-default-default
```

**Shasta's files are opened**, including `shasta-rpd.dpi` (whose constants the
port's stand-in uses) plus `shasta-erimm`, `-fps`, `-low` variants and
`shasta.map`. Opening is not proof of use — see the caveat below — but it does
mean the shasta tree is enumerated on a CN render.

**dra ships tone curves as `.ttc`**: `lowNormal`, `highNormal`, `lowBacklit`,
`highBacklit`, `lowFrontlit`, `highFrontlit` — a lighting-class axis.

**FUGC**: three map files (`fugc-lutMap`, `fugc-neutral-lutMap`,
`fugc-rgb-lutMap`), `fugc-defaultParams.dpi`, the `fugc-generic*` LUT family and
a **`NoShift_` variant** family (`NoShift_fugc-generic045.lut` among them).

**Colour-space conversions exist as profiles**: `deRender\Romm12_to_ERIMM.pf`
and `reRender\Erimm_to_Romm.pf`.

## Caveat — opening is not using

Whole families appear (every `pnr-srcType-speed-*`, every `nra-*`, every
`falloff-*`), which is what map-driven resolution looks like: the engine reads
the `.map` and stats/opens candidates before selecting one. **Do not read this
as an execution trace.** It is an inventory of what the CN-Enhanced render path
*considers*, which is still far more than the port currently knows about.

To turn it into a true execution trace, hook `ReadFile` as well and correlate
by handle — deliberately skipped here because the volume would have buried the
opens.

## Method note

The first analysis of this capture wrongly reported it as nearly empty. That was
an extraction bug on my side: the paths are **ANSI** (`CreateFileA`), and the
decoder only walked UTF-16. Anyone parsing an `.apmx86` should search both
encodings. Format details are in `docs/55`.

Artefact: `~/pakon-findings/incoming/capture2.apmx86`.
