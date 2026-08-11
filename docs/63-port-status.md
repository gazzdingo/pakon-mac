# Port status — everything not yet ported, and how much actually is

A full inventory, built by grepping every `*_PORTED` flag and every "not
ported" / "unported" comment across `tools/` and `tools/ansel/`, rather than
from memory. Two things fell out of doing it this way rather than guessing:

1. **The remaining gap list is short.** Of ~95 port-status markers in the
   tree, only 16 are `False`. The rest — the Ansel/Ane/Fos/ColorAdjust/
   SceneContext/FUGC infrastructure underneath the render path — is already
   ported and Unicorn- or closed-form-verified.
2. **A "not ported" is not automatically a bug.** Several are ours by
   necessity (measured, no vendor call site exists to match against) and
   several are deliberate refusals (film paths this project has decided not
   to support yet, rather than support wrong). Each entry below says which.

Read `_PORTED = True` as "Unicorn-verified bit-exact against the real DLL, or
a closed form checked the same way" unless its own comment says otherwise —
that is the standard this project holds itself to; see `docs/62`.

## 1. The real gaps — everything currently `False`

### Colour math, live on the render path today

| Flag | File(s) | What it means |
|---|---|---|
| `AUTO_TONE_PORTED` / `AutoTonePorted` | `pakon_shasta.py`, `shasta.go` | **The current shadow-crush cause.** `ColorNegativePath::analyzeAutoTone` (`0x100fb730`) is the real vendor tone stage for a colour negative. Not one function — an orchestrator over 6 capability subsystems (cna, dra, toneHelper, contrast, ast, citras) plus up to 16 producer capabilities it may read from. Currently scoped by a background workflow; see §3. |
| `SHASTA_TWO_ANCHOR_PORTED` | `pakon_ansel.py` | The stand-in `shasta_two_anchor_tone` currently live in its place. "Shape is ours; only the aims are vendor" — i.e. even the aim values it's fed are real, but the two-anchor curve shape connecting them is not. Retired once `AUTO_TONE_PORTED` lands. |
| `F135_INVERT_PORTED` / `F135InvertPorted` | `pakon_decode.py`, `main.go` | The negative→positive inversion (the `c9` log formula). Verified correct by measurement and by the owner's own eye on a real photo, but no DLL call site has been shown to compute this exact arithmetic — `docs/58` §3.5 is [VERIFIED] that no density LUT runs between the polynomial and Ansel, so *something* not yet located does this in the vendor. Ours until that something is found. |
| `SRA_MAKE_LUTS_PORTED` | `pakon_sra.py` | `AnsSraCapabilityImpl::makeSRALUTS` (`0x101a6be0`). Traced and **ruled out** as the mask-removal mechanism — it's one shared neutral curve plus additive per-channel offsets, which can only balance, not change contrast (`docs/58` §16). Staying `False` is correct; this is not live work. |

### Balance / SBA

| Flag | File | What it means |
|---|---|---|
| `SBA_CORE_PORTED` | `pakon_sba_preference.py` | The SBA orchestration core. `PREFERENCE_SHIFTS_PORTED` and `PREFERENCE_HI_UV_PORTED` (both `True`) cover the preference-shift maths this feeds into; the core orchestrator around them does not. |
| `ANALYSE_ROLL_PORTED` | `pakon_analyse_roll.py` | No balance, FPO, or Preference maths ported at the whole-roll level — this file explicitly does not invent a substitute (see the `FOS dens → orderFpo` note below). |
| `SCP_LUT_BALANCE_PORTED` | `pakon_scp_lut.py` | The SCP-LUT balance step itself. `SCP_LUT_DPI_PARSE_PORTED`, `THREE_BAND_LUT_ASCII_PORTED` and `SCP_LUT_ANALYZE_LEAVES_PORTED` (all `True`) cover file parsing and the analyze leaves; the balance application does not run. |

### FUGC and ColorAdjust — narrow, specific pieces

| Item | File | What it means |
|---|---|---|
| `FUGC_EXPORT_PORTED` | `pakon_fugc.py` | One export path; `FUGC_ANALYZE_PORTED`, `FUGC_SET_LUT_INFO_PORTED`, `FUGC_SEED_LUT_PORTED` and 9 other FUGC flags are `True`. Host Preference applies `setLutInfo` / the mode-2 plane in its place. |
| Kodak `SpCombineXforms` (4 xforms → 1) | `pakon_color_adjust.py:39` | Not ported. `COLOR_ADJUST_PORTED` and its ~18 sibling flags in the same file are `True` — this is one specific compose step inside an otherwise-ported chain. |
| `ImaUnsharpMaskOperation` apply | `pakon_color_adjust.py:1984` | Not ported, distinct from `COLOR_ADJUST_UNSHARP_APPLY_PORTED = True` (which covers the parameter/gate side, not this operation's own apply). |
| FOS dens → `orderFpo` | `pakon_fos.py`, cited from `pakon_ansel.py:550` | Not ported; the code explicitly refuses to invent a substitute rather than guess. `FOS_ANALYZE_PORTED` and 10 sibling flags in `pakon_fos.py` are `True` — this is the one piece that feeds `ANALYSE_ROLL_PORTED` above. |

### Deliberately ours, not vendor call sites — measured and working, not gaps to close

| Flag | File(s) | Why it's `False` on purpose |
|---|---|---|
| `CCD_DESKEW_PORTED` | `pakon_decode.py` | The trilinear CCD row-spacing correction is measured by cross-correlation on real captures, not read from a vendor table. Verified working; there is nothing to port it *against*. |
| `FILM_BASE_WINDOW_PORTED` / `FilmBaseWindowPorted` | `pakon_decode.py`, `dmin.go` | The FindDmin column/line window (the fix for the leader/CCD-offset clipping bug). Same situation — ours, verified, no vendor call site computes this specific window. |

### Deliberately refused, not attempted

| Flag | File(s) | Why |
|---|---|---|
| `F135_REVERSAL_PORTED` / `F135ReversalPorted` | `pakon_decode.py`, `request.go` | Slide/positive film. `CheckFilmClass` refuses `-film-path POSITIVE` outright rather than render it through the wrong matrix — this unit's PosMatrix is an uncalibrated 0.25 diagonal, and the rest of the chain is written for a negative. Refusing is the correct behaviour, not a TODO. |

## 2. Stale markers found along the way — trust the flag, not always the prose

Two older comments contradict newer, more specific flags in the same
codebase. Recorded here so nobody acts on the stale one:

- `pakon_shasta_sample_golden.py` and an older docstring in `pakon_shasta.py`
  say the Iem histogram fill (`0x104ea940`) is "not ported." It now is —
  `SHASTA_IEM_HIST_FILL_PORTED = True`, and the analyze-port work executed it
  on a real plane set and matched it bit-for-bit against
  `hist_counts_from_plane0`. The comment predates that work.
- `pakon_decode.py:1518` says "`AnsShastaCapabilityImpl::analyze` is
  unported." This is now partially stale: `SHASTA_ANALYZE_INNER_PORTED =
  True` covers the *inner* image-processing stage (`0x1027be10`), Unicorn-
  verified end to end. What's still genuinely true is narrower: the Cap-level
  `0x101e5250` wrapper itself — its vector plumbing, the `Cap+0x2e0` POD copy,
  and the `+0x3c0` blackNoise percentile block — remains unported. Also still
  true and important: **Shasta is not on the colour-negative render path at
  all** (`SHASTA_ON_CN_RENDER_PATH = False`, proven from the binary — see the
  `AUTO_TONE_PORTED` entry above), so none of this currently matters for what
  the app renders.

## 3. `AUTO_TONE_PORTED` dependency scope — being pruned now

A background workflow (`wf_bfc4f768-88e`) is static-triaging the 16 producer
capabilities `analyzeAutoTone` may read from (`filmLut`, `flesh`, `pan`,
`fos`, `scpLut`, `afterSCPLutSba`, `area`, `orderOrientation`, `asea`,
`noiseTable`, `pnr`, `nra`, `dei`, `dtt`, `falloff`, `fugc`) plus the 6 tone
subsystems themselves, to prune what's provably irrelevant to tone/density
math before committing bit-exact Unicorn verification effort to it. This
section gets filled in with the real, evidence-based scope and task
breakdown once that reports back — not before.

## 4. What's already ported and verified — by subsystem, not line by line

Counted from the flags above rather than restated individually (there are
~79 `True` markers; listing each would bury the point):

| Subsystem | File | Roughly how much is `True` |
|---|---|---|
| Ane order / Laplacian analyze | `pakon_ane_order.py` | 15 flags, the whole chain from histogram bins through neighbour-merge and curve-row packing |
| Shasta (curve leaves, tone-LUT builder, image sampling, apply) | `pakon_shasta.py` | 18 flags — everything except the Cap-level wrapper and `AUTO_TONE_PORTED` above |
| ColorAdjust | `pakon_color_adjust.py` | ~19 flags — selectors, contrast LUT, unsharp params, the whole `SpConnect`/`PtCombine`/`PtGetPtInfo` COM-wrapper chain |
| FOS | `pakon_fos.py` | 11 flags — paxel walk, eigen, slopes/offsets, FPO compose |
| FUGC | `pakon_fugc.py` | 12 of 13 flags — only `FUGC_EXPORT_PORTED` open |
| Scene context / Dmin | `pakon_scene_context.py` | 8 flags — bag I/O, ScpLut remap, ColNeg remap for both F-135 and its predecessor |
| Ane collect | `pakon_ane_collect.py` | 5 flags |
| SBA apply / setShifts | `pakon_sba_apply.py`, `pakon_setshifts_golden.py` | Verified Unicorn-golden |
| SBA preference | `pakon_sba_preference.py` | 2 of 3 flags — only the orchestration core open |
| SCP LUT | `pakon_scp_lut.py` | 3 of 4 flags — only balance-application open |

Nothing above is asserted from memory — every row traces to a flag or a
comment quoted in §1/§2, greppable at any time with:

```
grep -rn "_PORTED\s*=\s*\(True\|False\)" tools/ | grep -v __pycache__
grep -rn "Ported\s*=\s*\(true\|false\)" tools/ansel/pipeline/*.go
```
