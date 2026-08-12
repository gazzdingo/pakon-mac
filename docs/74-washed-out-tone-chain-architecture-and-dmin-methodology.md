# The washed-out defect — tone-chain architecture, and a real methodology
# gap in all eleven prior passes' own acceptance numbers

**Update, same day, same pass**: §4 below settles the question §2/§3 left
open, with a real production render on a real roll. Short version: fixing
the Dmin methodology gap does **not** make the washed-out defect go away —
using the real, correctly-measured roll-wide film base on an actual real
roll's actual frame, through the actual `render_scene` production path,
still produces the same "no real blacks" result (darkest 1% at sRGB
~70-110/255), matching `docs/68`'s own real-roll figure (~90-114) almost
exactly. The defect is confirmed real and independent of this
methodology gap, not an artifact of it.

**Second update, same day**: §5 below checks the next most promising lead
this doc itself raised — that `fpo` ("opening RGB", the fixed value the
whole SBA/Preference shift chain anchors to) might be missing a real
per-scene source in the vendor DLL, silently replaced by this port with a
static per-film-stock default. Checked directly against the real DLL,
freshly re-extracted: refuted. `fpo` genuinely is DPI-file-static in the
vendor's own code too, populated once at `.dpi`-parse time, not derived
from any per-scene pixel analysis. This is now the second concrete
candidate cause this doc has raised and ruled out on real evidence, not
just re-confirmed something already known.

Written 2026-08-12, a fresh read-only investigation into `docs/66`'s
"washed out" defect, picking up exactly where the eleventh pass's own "What
is still open" list left off (FUGC's dmin correction; the four unreplicated
`analyzeArea`/`analyzeAttributes`/`analyzeNoise`/`analyzeFalloff` stages).
**No port code was changed.** Everything below is read-only instrumentation
of already-Unicorn-verified port code (`pakon_dra.py`, `pakon_cna.py`,
`pakon_decode.py`, `pakon_ansel.py`) plus fresh disassembly-free re-reading
of `pakon_decode.py`'s own already-documented caveats. Scratch scripts used
to gather the numbers below are not committed (they lived under this
session's own job tmp dir, not `/tmp` or the repo).

## Summary

Two distinct findings, neither of which is "the bug fixed" — both are
new, evidenced, and change what the next pass should look at:

1. **The tone chain's own architecture, now pinned down at the LUT-value
   level (not just median deltas like the tenth pass's table)**: `cna` and
   `dra`, both individually Unicorn-verified bit-exact, compose into a
   curve that pivots on the fixed neutral-gray anchor (code **1550**,
   shared by `dra`'s `lowFixedPoint`/`highFixedPoint` *and* SBA's
   `neutralBalancePoint`) and only mildly compresses the extremes. It is
   **not** an auto-levels / black-and-white-point-stretch algorithm, even
   when it runs correctly. On the reference frame, `dra`'s own shadow band
   is a **complete no-op** — see §1.
2. **A real, independent methodology gap**: the reference frame's own
   "film base" (Dmin) — the input to the negative→positive log inversion
   that everything downstream depends on — is measured by treating the
   *entire single exported frame* as if it were clear film leader, because
   `measure_python_autotone.py` (and, almost certainly, whatever ad hoc
   script produced the tenth pass's "real roll frame 0" cross-check — see
   §3) calls `film_base=None` on a lone TIFF with no roll/strip context.
   The measured "base" for this reference frame is **numerically
   indistinguishable from the frame's own 99th-percentile highlight** —
   not a plausible clear-film reading. This means **every quantitative
   acceptance number in all eleven prior passes rests on an input whose
   absolute density calibration was never actually validated.** See §2.
   A controlled sensitivity test (§2.3) shows this specific bug does
   **not** explain the "too light" direction of the defect — it's a
   real, worth-fixing gap in the investigation's own instrumentation, not
   the root cause. Flagged plainly as that, not oversold.

Net effect: this pass does **not** close the washed-out investigation. It
sharpens two things worth doing before a twelfth RE pass spends more
budget: fix the measurement harness's Dmin methodology (cheap, and
currently undermines confidence in every published number), and reframe
the open question from "why doesn't autoTone fix the shadows" to "why
does the frame's own content sit so far from the pipeline's fixed neutral
anchor in the first place" (upstream of `analyzeAutoTone` entirely,
consistent with, and sharper than, the tenth/eleventh passes' own
conclusion).

## 1 — `dra`'s shadow band is a no-op on this frame; `cna` does the only
real shadow work, and neither is a black-point stretch

`pakon_dra.DraParams.load(VENDOR_DRA_DIR)` for the shipped
`ansel-dra-default-default.dpi`:

```
lowFixedPoint = highFixedPoint = 1550   (degenerate — a single point, not a band)
paperMin = 1200   paperMax = 2000
lowNormalTTC = highNormalTTC = IDENTITY curve (x=[0,1,10], y=[0,1,10], slope=[1,1])
```

`lighting` is hardcoded `0` ("Normal") for CN-Enhanced —
`pakon_autotone.py`'s own comment: `find("lighting")` always misses, and a
miss yields lighting `0`, confirmed against the real DLL
(`pakon_dra_golden.check_lighting`). So the **Normal** low/high curves are
what always runs, and both are literal `y = x` identity curves — the only
non-trivial curve in the whole `DraParams` file is `lowBacklitTTC`, which
never gets selected for CN-Enhanced.

Ran `pakon_dra.keep_midpt_lut` directly (`0x102290b0`) on this project's
own reference frame (`captures/out_test/frames/08_raw14.tiff`) with its
real analyzed bounds, `effMin=1670`, `effMax=2578` (from `pakon_dra`'s
`generate_lut`, itself fed by `cna`'s luminance/edge histograms — these
numbers match the tenth pass's own published `dra` output exactly, same
frame, same pipeline state, cross-checked). Reading `keep_midpt_lut`'s low
side directly (`pakon_dra.py:1088-1104`, VA `0x102293ad`..`0x102294b7`):

```python
lo_gap = low_fp - max(eff_min, paper_min)
denom_lo = float(low_fp - eff_min)
esi = low_fp - 1                       # 1549, and only decreases
while esi >= 0:
    if esi >= eff_min:                 # 1670 — NEVER true for esi <= 1549
        ...interpolate against low.x/low.slope...
    else:
        newv = out[esi + 1] - 1        # "ramp": ready-written neighbour, -1
    out[esi] = two_sided_clamp(newv)
    esi -= 1
```

Because `eff_min` (1670) is numerically **above** `low_fp - 1` (1549), the
`esi >= eff_min` branch is unreachable for every index the low loop ever
visits. The entire low band — indices 0..1549, i.e. **all of it** —
collapses to the "ramp" arm: `out[esi] = out[esi+1] - 1`, starting from the
midpoint-band's own identity fill at `out[1550] = 1550`. That recurrence is
just `out[esi] = esi` — **pure identity**, confirmed by direct execution:

```
keep_midpt_lut(0, low, high, 4095, 1550, 1550, 1200, 2000, 0.25, 1670, 2578)
  lut[0..10]   = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]        # identity
  lut[1665:1675] = [1600, 1601, 1601, ..., 1604]            # HIGH band, not low
```

So for this frame, `dra`'s own shadow-band mechanism (the thing the tenth
pass's "already exists and is correct" conclusion was about) contributes
**zero** shaping below the neutral point. Whatever shape the final `DraLut`
shows below 1550 is **entirely inherited from `cna`'s own
`ToneScaleLut`**, confirmed by directly checking the composition formula
`pakon_dra`'s own module docstring already documents
(`0x1022bb0f`: `draLut[i] = keepMidPtOutput[toneLut[i]]`):

```
i     cna.tone_scale_lut[i]   keepMidPtOutput[tsl[i]]   actual DraLut[i]
0     416                     416                       416     (exact match)
1000  1270                    1270                      1270
1629  1629                    1585                       1585
2578  2594                    2016                       2016
4095  3390                    2812                       2812
```

`cna.tone_scale_lut` (also independently Unicorn-verified,
`CNA_ANALYZE_IMAGE_PORTED=True`) is itself only mildly compressive around
the *same* 1550 anchor — `tone_scale_lut[0] = 416` (a lift, not a stretch
to 0), `tone_scale_lut[1550] = 1550` (identity at the anchor),
`tone_scale_lut[1629] = 1629` (still identity near the anchor).

**The takeaway, stated plainly**: two independently, bit-exact-verified
subsystems compose into a curve whose entire design is "protect a fixed
neutral reference point (1550, shared with SBA's own
`neutralBalancePoint`) and mildly compress values far from it." Nowhere in
this — correctly ported — mechanism is there a step that says "take
whatever this scene's own darkest content is and pull it down to true
black." That is a *design* fact about the vendor's own `analyzeAutoTone`,
not a port defect; it explains, precisely, why the ninth pass's real fix
(replacing the interim citras stand-in with the real driver) cleared the
shadow-*crush* symptom (over-darkening) but left the frame reading "too
light" — the mechanism was never going to close a gap between where a
scene's content sits and where the pipeline expects it to sit relative to
1550. That gap is set entirely by whatever runs *before* `analyzeAutoTone`
— balance/SBA, FUGC, and (per the tenth/eleventh passes' own still-open
item) the four unreplicated stages.

## 2 — The reference frame's own Dmin: measured from itself, not from film

### 2.1 — What's actually happening in `film_base_codes(film_base=None)`

`pakon_decode.film_base_codes` (`FindDmin`, `FILM_BASE_WINDOW_PORTED =
False` — an already-documented "ours, not the vendor's" convention) is,
by its own docstring, **roll-level by design**: "the base is a property of
the stock, not of one frame... `lin12` must be the whole strip." Its
mechanism for telling film from clear leader/empty gate
(`film_base_line_mask`) flags a line as *not* film when more than 50% of
its aperture is saturated — a leader/gate line saturates almost the whole
line; a line with real photographic content essentially never does.

`tools/measure_python_autotone.py` — the single tool behind every
quantitative claim in all eleven `docs/66` passes — reads **one exported
frame TIFF**, with **no roll/strip context**, and calls
`f135_rom12_to_rpd12(..., film_base=None, capture=None)`. Its own comment
already flags this as a known stand-in: *"film_base=None: measure from
THIS frame (there is no roll context here, only one exported frame) ...
not a claim this is the roll's true film base."* No prior pass followed
that thread to see what it actually does numerically.

### 2.2 — What it actually measures, on the real reference frame

```
film_base_window(poly, capture=None):  col0=30  lines_kept=2000/2000  clip_pct≈0

measured "film base" (per-frame):        R=2412   G=1406   B=1263
frame's own poly percentiles:  p99       R=2410   G=1404   B=1262
```

`lines_kept = 2000/2000` — **every single line** of this single-frame
export is classified as "film" (there is no leader/gate content in a
cropped single-frame TIFF for the saturation test to catch), so
`film_base_window` hands the *entire frame* to the Dmin walk. The result:
the measured "base" is, per channel, numerically indistinguishable from
the frame's **own 99th-percentile highlight** — R 2412 vs. p99 2410, G
1406 vs. p99 1404, B 1263 vs. p99 1262. This is not measuring clear film
(which should read far brighter than any photographed content on the same
negative — realistically close to the CCD's own headroom, not ~1-2%
above the frame's own bright content). It is measuring "the top 0.1-1% of
this photograph," dressed up as a film-base constant.

This directly undermines the absolute-brightness trustworthiness of every
number in `docs/66`'s eleven passes — all of them, including the
much-cited "toned output sits ~290 codes above the display's gray point
and ~780 codes short of white" figure in `docs/68`, were computed from
`inv16` produced with this per-frame Dmin.

### 2.3 — Does this explain "too light"? Tested directly — no

Sensitivity test: re-ran the negative→positive inversion on the same
frame with the measured base scaled ×1.3, ×1.6, ×2.0, ×3.0 (i.e.,
approximating what a much-brighter, more plausible clear-film reading
would produce):

```
R channel percentiles, [p1, p50, p99], and p99-p1 span:
  base ×1.0 (measured, buggy):  946, 1444, 1755   span=809
  base ×1.3:                   1067, 1565, 1876   span=809
  base ×1.6:                   1162, 1660, 1970   span=808
  base ×2.0:                   1263, 1760, 2071   span=808
  base ×3.0:                   1444, 1941, 2252   span=808
```

Raising `base` shifts the **whole** distribution up by an almost-constant
amount (a pure additive/level shift in this log-difference formula,
`rpd12 = fpo + 1000*(log10(base-c9) - log10(poly-c9))` — for `base` well
above `poly`, scaling `base` shifts `log10(base-c9)` by close to
`log10(scale)` uniformly for every pixel) — it does **not** widen or
narrow the p1-to-p99 spread at all (809 → 808 across a 3× range). Two
consequences, stated plainly:

* A too-low measured `base` is **not** a source of the narrow-contrast /
  "no real blacks" *compression* — contrast (span) is essentially
  invariant to this bug.
* The **direction** is the opposite of what would explain "too light":
  the currently-measured (too-low) base produces a **lower** (darker)
  `rpd12` than a correctly-higher base would. If this bug were fixed with
  a genuinely higher, correctly-measured base, the frame would render
  **brighter still**, not less washed out — and per §1, nothing
  downstream would pull that brighter content back down, since the tone
  chain doesn't stretch toward black, it just gently protects the 1550
  anchor.

**This is therefore a real, independently worth-fixing bug in the
project's own measurement instrumentation — not a candidate explanation
for the washed-out defect's direction.** Flagged as exactly that, not
oversold either way.

## 3 — This almost certainly affected the tenth pass's "real roll" cross-
check too, not just the shared reference frame

The tenth pass's own re-confirmation ("frame 0 of a real roll measured p1
R/G/B = 90/87/88... blue alone clipping to sRGB ≥239 on 18-22% of
pixels") does not document what tool produced those numbers, and that
scratch script was not preserved (same as the un-dispatched twelfth
pass's own prompt). What can be checked without re-deriving it: **no
`roll.json` exists anywhere under this repo's `captures/` tree** (`find
captures -iname roll.json` → zero results). `tools/pakon_render.py`'s own
comments are explicit that a real, correctly-measured roll-wide
`film_base` requires a live `Roll` object with `roll.film_base` populated
from a whole-strip `FindDmin` pass over real leader/gate lines — and that
a **preview Roll (single frame, no strip context) always falls back to
exactly the same per-frame `film_base=None` path** this section just
measured as broken. Given no roll-wide film-base data exists anywhere in
this project's local capture set, and the only documented measurement
tool (`measure_python_autotone.py`) only ever accepts a single TIFF, the
far more likely explanation is that the tenth pass's "real roll"
cross-check used the *same* single-frame methodology on an extracted
frame from that roll — not `tools/pakon_render.py`'s real production
roll-wide path.

**This is not proven** (the exact script is gone), but it is well
corroborated circumstantially, and it means the tenth pass's own
"re-confirmed... not test-frame-specific" claim may itself need
re-examination with a genuine roll-wide Dmin before being trusted as
"the same defect on a second, independent data point." Whoever runs the
next pass should check this explicitly, ideally by running an actual real
roll through `tools/pakon_render.py`'s own `Roll`-based path (which does
compute `film_base` correctly, per docs/73's own confirmation that
"the Python engine never had this bug — it already used the roll-wide
base unconditionally") rather than a lone exported TIFF, before drawing
any further conclusions from "real roll" numbers.

## 4 — Settled directly: a real roll, real production render, correctly-
measured roll-wide Dmin — the defect survives

§3 above was circumstantial (the tenth pass's script wasn't preserved).
This section settles it directly, with a real capture and the real
production code path, not a re-derivation.

**Method.** `tools/pakon_render.open_capture` (the same function the real
app/CLI uses to open a roll) was run against `captures/gold400.bin` — a
real capture with genuine clear-leader content, already cited by
`pakon_decode.py`'s own comments as the reference example for the
leader/film line-saturation split (2,105 leader lines, ~29,000 film
lines, 31,203 total). This runs the **real** whole-strip `FindDmin` pass
(`pakon_render.py` lines ~817-912, the exact code §2 read but did not yet
run end-to-end) and produced a real `roll.film_base`:

```
roll.film_base (whole-strip FindDmin, real leader lines excluded): R=2200  G=1352  B=1217
```

For frame index 1 of that same roll (1,578 real lines, a real
photographic frame, no synthetic data), the same single-frame-fallback
method §2 exercised (`dec.film_base_codes(poly, capture=None)` on just
that frame's own slice, no leader in view) gives:

```
per-frame (buggy) base for this one frame:                     R=1961  G=1301  B=1174
```

Confirms §2's direction on real data: the buggy per-frame method
under-measures the true base by a real, modest amount here (R +12%, G
+4%, B +4% once corrected) — not the ×1.3-×3.0 synthetic range §2.3 used
to test direction/sensitivity, but the same direction, on a real roll
this time, not speculation.

**The actual test**: rendered this same real frame twice, through the
real `AnselEngine.render_scene` (`shasta_mod.AUTO_TONE_PORTED = True`,
the real ninth-pass tone chain, identical to every prior pass), once with
each base, everything else held fixed (same `eng`, same `off`, same
frame data):

```
                          sRGB [p1, p50, p99]
                    R                G                B
BUGGY per-frame:    [ 98, 231, 254]  [70, 186, 232]   [67, 182, 221]
REAL roll-wide:     [108, 234, 254]  [74, 186, 232]   [72, 184, 222]
```

Two things this settles:

1. **Direction confirmed on real data, not just the log-formula argument
   in §2.3**: the correctly-measured (higher) roll-wide base renders
   *slightly brighter*, not darker. Fixing the methodology bug moves the
   frame a few sRGB codes in the wrong direction to explain "washed out."
2. **The defect is real, and is not the Dmin methodology bug**: even with
   the correct, real, whole-strip-measured film base, on a real roll,
   through the real production render path, the darkest 1% of this
   frame's pixels still lands at sRGB **~70-110 out of 255** — no real
   blacks, the exact defect `docs/68`'s handover describes ("~90-114"),
   reproduced independently here with a controlled, methodology-clean
   input. This frame was not cherry-picked for the defect — it's simply
   frame index 1 of a real capture already in this repo, rendered through
   the same code every prior pass used.

**What this means for §3's speculation**: it doesn't matter anymore
whether the tenth pass's own "real roll" cross-check happened to hit the
same bug — even a rigorously bug-free Dmin measurement on an independent
real roll reproduces the same washed-out result. The methodology gap in
§2 is still real and still worth fixing (it's simply wrong, regardless of
its effect on this one symptom), but it is conclusively **not** the
explanation, and the investigation should not spend further time on it as
a root-cause candidate.

## 5 — `fpo` is genuinely DPI-static in the real DLL too — a promising
lead, checked and ruled out

§1-4 leave one architecturally attractive hypothesis unchecked: `fpo`
("opening RGB", the single value the whole SBA/Preference shift chain
anchors to — see §4's per-frame numbers) is, in this project's own
Python port, read straight from the shipped `.dpi` file
(`pakon_ansel.SbaParams.load`: `fpo = d["fpo"]`, and every
`preference_shifts_*` function in `pakon_sba_preference.py` takes `fpo`
as a plain parameter — no pixel/histogram data anywhere in that call
chain). If the *real* DLL instead derived `fpo` per-scene from actual
roll content — plausibly via the genuinely-unported
`CiColorCorrectionAnsel::AnalyzeRoll` / `analyzeBalanceOrder`'s own
`pass1`/FOS/`pass2` sequence, `ANALYSE_ROLL_PORTED=False`,
`pakon_analyse_roll.py`'s own "UNKNOWN/blockers" list still carries
*"Preference / `+0x4d0e` → no alternate `+0x3a38` writer"* and
*"pass1/FOS/pass2 bodies; FPO/scale memory layout: UNKNOWN"* — that would
directly explain why this port's fixed-per-stock `fpo` leaves every
frame sitting wherever its actual exposure happens to land, with nothing
downstream (§1) able to correct for it.

**Checked directly against the real DLL** (`PakonIMAu.dll`, re-extracted
fresh from `research/sdk/PAKONF135.iso` this pass, MD5
`eea9dcf78ee21d4f7c515a6c2512242d` — confirmed identical to the file
every prior pass used before relying on it). A raw byte-pattern search
for the little-endian displacement `0e 4d 00 00` (i.e. every
compile-time-constant `[reg+0x4d0e]` memory operand anywhere in the
binary, read or write) finds **exactly three occurrences in the whole
DLL**: `0x10214e32`, `0x10214f29`, `0x102150e1`. All three disassemble to
the same shape — `lea eax, [ecx+0x4d0e]` immediately followed by reading
`dword [eax]`/`word [eax+N]` and copying it elsewhere (a small family of
near-identical "pack scene fields into an output blob" accessor
functions, one of which — `0x10214f20` — `pakon_sba_preference.py`
already cites by address, `PREF_IN_PLUS_0x28`/etc, from a prior pass).
**None of the three is a write.** There is no other place in the entire
DLL that references this exact field by its compile-time offset.

This corroborates a comment already sitting in `pakon_sba_preference.py`
(pre-dating this pass, easy to miss reading top-to-bottom rather than
chasing this specific question) that already answers it directly:
*"Nested opening RGB = `AnsSbaDPI+0x80` fpo (docs/48). Ctor defaults @
`0x10289ad0`/`ad6`/`adc` — overwritten by `readAscii` when dpi loads."*
`fpo` genuinely is populated once, at DPI-file-parse time
(`readAscii`), from the shipped `.dpi` text — not from any per-scene
pixel analysis — in the **real vendor DLL itself**, not just in this
project's port. The port's choice to read it straight from the parsed
DPI file is therefore correct, not a gap.

**Verdict: a real, well-motivated hypothesis, checked with fresh
disassembly against the real DLL, and refuted.** `ANALYSE_ROLL_PORTED`'s
own `pass1`/FOS/`pass2` sequence remains genuinely unported and its real
output is still undetermined — but it does not feed `fpo`. (Circumstantial
support this doesn't matter for CN-Enhanced specifically:
`tools/pakon_render.py`'s own comment on `AnalyseRoll`'s port stand-in,
"median roll scale", already notes *"Preference OUT is the channel
balance — skip median roll_scale (it cancels R/G/B ratios from
setShifts)"* whenever Preference/setShifts is active, which it is on
every path this investigation has touched — i.e. this project's own
architecture already treats `AnalyseRoll`'s stand-in as superseded here,
not silently missing.) No further static or live work on this specific
question is recommended — it's closed, not just paused.

## What this changes about the open item list

`docs/66`'s eleventh pass left two things open: FUGC's near-identity
dmin correction, and the four unreplicated
`analyzeArea`/`analyzeAttributes`/`analyzeNoise`/`analyzeFalloff` stages.
Both are **still open** — nothing in this doc closes either one. What
this doc's five sections *do* close, cumulatively: the tone chain's own
architecture is now fully characterized and is not the cause (§1); the
Dmin/level hypothesis is checked on real production data and is not the
cause (§2-4); and the most architecturally attractive remaining
hypothesis this doc itself raised — a missing per-scene `fpo` — is
checked against fresh DLL disassembly and is not the cause either (§5).
Updated priority order for whoever picks this up next:

1. **The four unreplicated stages
   (`analyzeArea`/`analyzeAttributes`/`analyzeNoise`/`analyzeFalloff`)
   are now the single most concrete remaining lead**, not one of several.
   Every other candidate this doc and the eleven `docs/66` passes
   together have checked — the tone chain's math and design (§1),
   `apply_balance_shifts`'s mechanism and real shipped values (`docs/66`
   eleventh pass), the Dmin/level chain end to end on real production
   data (§2-4), and `fpo`'s own provenance (§5) — comes back "correct,
   not the cause." This is real, if unglamorous, progress: the search
   space has narrowed from "somewhere in six subsystems plus three
   upstream stages" to "one specific set of four stages, or nothing left
   that's a software bug at all" (see item 3).
2. **FUGC's near-identity dmin correction** — still not live-DLL-verified
   per the eleventh pass's own note (`pakon_fugc_golden.py`'s
   `setLutInfo` cases were confirmed host-vs-host, not against the real
   DLL specifically). Cheaper than item 1 if whoever picks this up wants
   a quick sanity check first.
3. **Worth stating plainly given how much has now been ruled out**: it
   remains possible this is not a software defect at all — that this
   project's reference frame(s) and test roll(s) are negatives whose
   real exposure/calibration genuinely sits where SBA/Preference's fixed
   per-stock `fpo` (§5) doesn't fully compensate for, and the vendor's
   own real output would look similar on the same source material. This
   doc does not claim that — it has not been tested (would need the real
   DLL's own end-to-end output on this exact frame, the one thing no
   pass has yet obtained) — but after five converging "correct, not the
   cause" results, it belongs on the list of live possibilities, not
   just "the four stages."
4. **Fix the measurement harness's Dmin methodology anyway — real bug,
   just not this one.** `measure_python_autotone.py`'s `film_base=None`
   on a lone TIFF is still measuring "the frame's own highlights" and
   calling it film base, which is simply wrong regardless of its effect
   on the washed-out symptom. Cheap fix, worth doing for its own sake
   (any future acceptance number that isn't purely relative will
   otherwise inherit this): thread a real roll-wide base through, the
   way `tools/pakon_render.py`'s own `open_capture`/`scene_rpd12` already
   do (§4's own method is a working, minimal example of exactly this).

## Verification

No port file changed. All numbers above were produced by directly calling
already-Unicorn-verified functions (`pakon_dra.keep_midpt_lut`,
`pakon_dra.generate_lut` via the real `analyze_auto_tone` shell,
`pakon_decode.film_base_codes`/`film_base_window`,
`pakon_decode.f135_rom12_to_rpd12`) with real data
(`captures/out_test/frames/08_raw14.tiff`, the same reference frame all
eleven prior passes used) — no new subsystem math was written, no golden
file was touched, no flag was flipped. `find captures -iname roll.json`
was run read-only, over aggregate filenames only, consistent with this
project's rule against describing `captures/` contents.

§4 additionally ran the real, unmodified `tools/pakon_render.open_capture`
and `pakon_render.scene_rpd12`/`AnselEngine.render_scene`/`.to_srgb`
against `captures/gold400.bin` (a real capture already in this repo, real
leader + real film, 31,203 lines, 16 real frames) end to end — no
synthetic data, no mocked stages, the same code path the app itself opens
a roll through. Only aggregate percentile statistics are reported above,
per this project's rule against describing `captures/` contents; no pixel
data, image, or per-pixel content from this or any capture is reproduced
anywhere in this file. No port file was changed by this pass; the only
"write" was this doc.

§5's DLL was re-extracted this pass from `research/sdk/PAKONF135.iso`
(`fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll` on the
mounted volume) rather than reused from any cached copy, and its MD5
(`eea9dcf78ee21d4f7c515a6c2512242d`) was checked equal to the one every
prior `docs/66` pass cites before relying on it. The `0x4d0e` search was
exhaustive over the whole binary (`r2`'s `/x` raw byte search, not a
`.text`-only or function-scoped search), so "exactly three occurrences,
all reads" is a complete statement about this DLL, not a sample. All
three sites were disassembled and read in full, not skimmed.
