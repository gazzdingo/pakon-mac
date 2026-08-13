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

**Third update, same day**: §6 below establishes that every capture this
doc (and, per its own dating, almost certainly all eleven `docs/66`
passes before it) has ever tested was captured **before** this session's
own real hardware fixes — a scanning-lamp duty-cycle recalibration
(open-gate duty roughly doubled for green, quintupled for blue) and a
genuine CCD dark-pedestal encoding bug fix, both landed 2026-08-12, both
after every real-photo capture in this repo. This doesn't retract §1-5's
software findings — they're real, about real code, independent of which
capture they were checked on — but it raises the question of whether the
whole investigation had been running against uncleanly-calibrated data.

**Fourth update, same day — §6's own recommendation, tested, and it does
NOT explain the defect**: §7 below finds that a real roll captured
*after* the recalibration already exists (via the app's own live API, not
a new capture triggered by this session), renders it through the same
real production path, and finds the washed-out defect survives
unchanged — darkest 1% still ~65-90/255, and the blue-clipping symptom is
if anything *worse* on fresh data (23-44% vs. the original 18-22%). So
§6's hardware-calibration hypothesis, while a real and independently
worth-knowing fact about this project's own test data, is now also ruled
out as *the* explanation, joining §1-5's software findings in the
"real, checked, not the cause" column. Six for six.

**Fifth update, same day**: §8 traces every stage from raw capture to
final sRGB on the fresh post-recalibration roll and finds the dynamic
range collapses at exactly one point — the negative→positive log
inversion (`f135_rom12_to_rpd12`) — while every stage before and after it
preserves span. This is also the one stage in the whole chain with no
DLL call site to Unicorn-verify against, unlike everything else this doc
and `docs/66` have checked. Not proven wrong; now the sharpest concrete
lead. Separately, in parallel: a real vendor-app comparison (running the
actual Pakon `PSI.exe` against real hardware and comparing its own output
directly) is in progress on separate hardware as of this writing — not
part of this doc's own evidence, noted here so a later reader knows to
check whether that landed before treating this doc's own priority list
as current.

**Sixth update, 2026-08-13 — the decisive one**: §13 reports the real
vendor-app comparison landed. The real vendor software, running on this
exact physical unit, produces genuine deep blacks (sRGB p1 ≈ 9-33/255)
on real film — an order of magnitude below this port's own 60-110/255,
every roll, every frame, this doc has ever measured. **This settles the
question §12's own "worth stating plainly" item raised**: it is not
vendor-intended behaviour, not a hardware or calibration limit — it is a
real, fixable defect somewhere in this port. Caveated (signature-carved
from a VM disk image, apparently black & white film, 8-bit JPEG, small
verified-coherent sample) but the caveats bound the *precision*, not the
*direction*, of the finding — see §13 for the full honest accounting.

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

## 6 — Every capture this investigation (all twelve passes, this doc
included) has ever tested predates this session's own hardware fixes —
and the lamp-duty change alone is large

This is the most consequential finding in this doc, and it sits earlier
than anything above: not in the render pipeline at all, but in the raw
capture data every pass has been feeding it.

**The dates, checked directly, not assumed:**

```
captures/gold400.bin                          captured 2026-08-07
captures/out_test/frames/08_raw14.tiff         captured 2026-08-09
calibration/README.pre-dutyfix-...json         2026-08-12 00:28  (first recal step)
calibration/README.json (current)              2026-08-12 08:21  (last of 5 recal steps)
```

Every real-photographic-content capture in this repo — including both
captures this doc itself used in §1-5, and (per `docs/68`'s own account)
almost certainly the reference frame and "real roll" every one of
`docs/66`'s eleven prior passes used too — was captured **before** this
session's own physical recalibration chain even started. The only
captures dated on or after 2026-08-12 in this repo (`vf_bright.bin`,
`vf_bright2.bin`, `vf_p1.bin`, `flat_bright_01.bin`, `flat_dark_01.bin`)
are calibration-target captures (view-finder / flat-field references),
not real photographic negatives — there is currently **no real-scene
capture anywhere in this repo taken under the corrected calibration.**

**What actually changed is not small.** Diffing `calibration/README.json`
(current) against `README.pre-dutyfix-20260812-002813.json` (the oldest
preserved snapshot, closest to what `gold400.bin`/`08_raw14.tiff` would
have been scanned under) shows the scanning-lamp open-gate duty cycle
(`on_counts_R_G_B`) changed from:

```
OLD (pre-fix, what every test capture used): R=492  G=239  B=104
NEW (current, post-fix):                     R=643  G=580  B=508
```

R +31%, **G +143%, B +388%**. The current file's own `duty_note` explains
why: *"The vendor stored duties for this unit ([702,371,158] open-gate)
clipped 97 percent of an empty gate on this hardware — its LEDs read
well below their 2022 values — so the vendor METHOD was applied rather
than its stored numbers."* Separately (per `docs/68`, and confirmed
present in this checkout's `tools/pakon_scan.py` at the AD9826 offset
encoding site, ~line 1716): a genuine CCD analog-front-end register bug
— 9-bit sign-magnitude sent as two's complement — *"silently zeroed the
dark pedestal at certain configs"*, fixed the same session, same day.

**Why this matters for everything above.** A blue channel scanned at
roughly a fifth of its correct lamp duty (and green at under half) reads
much closer to the CCD's own dark-noise floor for every pixel — which
directly compresses that channel's achievable dynamic range and pushes
its whole histogram toward the low-signal end, independent of anything
in the render pipeline. That is the same *shape* of defect this whole
investigation has been chasing in software: a narrow native code span
(§ — the ~800-900 code post-balance span measured on the reference
frame), and a pronounced, hard-to-explain R-vs-B asymmetry (blue
consistently the most compressed/clipped channel in every measurement
this doc and `docs/66` have made). A zeroed dark pedestal on top of that
would independently push measured "black" upward, compounding it.

**What this is not.** This is not a demonstrated fix — no capture exists
yet to test it against, and this doc does not claim the software findings
in §1-5 are wrong or unnecessary (the tone chain's architecture, the
Dmin methodology gap, and `fpo`'s provenance are all real findings about
real code, independent of what capture data they were checked against).
It is a real, dated, quantified fact that **the input data itself has
never been clean of two significant, since-fixed hardware defects**, and
no test in this investigation's history has controlled for that.

**The single highest-leverage next step, and it needs no more RE work at
all**: capture one real roll of real photographic film under the current
(post-2026-08-12) calibration, and re-run this doc's own §1-4 percentile
checks (or `tools/measure_shadow_clip.py`) against it. If the washed-out
numbers substantially improve on fresh data, this was hardware all
along and the four-unreplicated-stages / FUGC-live-verification leads in
"What this changes about the open item list" below drop in priority
sharply. If they don't improve, that's strong evidence the software
leads are still live and this was a real but insufficient contributing
factor. Either way this is now the load-bearing unknown, and it is a
data point, not a re-derivation — cheap by this investigation's
standards, but requires the physical scanner, so per this project's own
hardware-safety rules it should be run by the owner, interactively, not
launched autonomously from a background session.

## 7 — §6 tested directly, same day: a real post-recalibration roll exists
now, and the defect survives it — if anything, worse

§6 recommended capturing one real roll under the corrected calibration as
the single highest-leverage next step, and flagged it as needing the
owner at the physical scanner. That happened within the same session —
the app's own backend (`pakon_app.py`, already running, queried live via
its `/api/app/rolls` endpoint rather than guessed at) reports a real roll,
`scan-20260812-091633`, captured **09:16:33**, i.e. *after* the
recalibration chain finished at 08:21. Its capture file lives outside
this repo, at `~/Library/Caches/PakonScan/captures/` (the app's own
cache directory, not `captures/` — this is why §6's filesystem search of
the repo found nothing newer). Its own roll-wide `FindDmin` (queried live
from the app, not re-derived) already shows the calibration fix's effect
directly in the data: `film_base = [3219, 2580, 2492]`, dramatically
higher than `gold400.bin`'s `[2200, 1352, 1217]` — exactly the outcome
§6's lamp-duty numbers predicted.

**Rendered three real frames from this new roll**, same code path as §4
(`pakon_render.open_capture` → `scene_rpd12` → `AnselEngine.render_scene`
→ `.to_srgb`, real roll-wide film base, nothing mocked):

```
                    sRGB [p1, p50, p99]                          % pixels
                R              G              B                  B ≥ 239
frame 0    [ 88,187,252]  [ 86,200,252]  [ 88,221,254]            23.2%
frame 1    [ 79,149,248]  [ 84,199,250]  [ 86,212,254]            39.1%
frame 2    [ 63,152,252]  [ 90,203,252]  [ 88,234,254]            44.2%
```

**The defect survives.** Darkest 1% of pixels still sits at sRGB
63-90/255 — no real blacks, the same defect in kind and magnitude as
every capture tested before the recalibration. And on the specific
"blue channel clipping toward white" symptom `docs/68`'s handover
originally quantified at 18-22% — it is **worse** here, 23-44% across
these three frames, not better.

**This corrects §6's own framing, not the software findings above it.**
The hardware fixes were real (`film_base` moving from ~1200-2400 to
~2500-3200 confirms the lamp-duty change genuinely changed what the CCD
reads) and are presumably still worth having for other reasons, but they
are **not the explanation for the washed-out defect** — this doc's own
"if the numbers move substantially..." test in §6 has now been run, and
they didn't move in the direction that would explain it. The five
software findings in §1-5 (tone chain architecture, Dmin methodology,
`fpo` provenance) stand as before; §6 is downgraded from "the
highest-leverage next step" to "a real, now-tested, ruled-out
possibility" — the same status as §2-5's other candidates. The priority
list below is updated accordingly.

## 8 — A full stage-by-stage trace, raw capture to sRGB, on the fresh
post-recalibration roll: where the compression actually happens

Requested directly: trace every stage from decode to image and find
where it washes out. Traced frame 1 of the same fresh, post-recalibration
roll §7 used (`scan-20260812-091633`, captured 09:16, after the 08:21
recalibration), through every real stage boundary in the actual
production code (`Roll.attach`/`slice14` → `poly_hwc` →
`f135_rom12_to_rpd12` → `apply_balance_shifts` →
`build_setlutinfo_apply_lut` → `render_scene`'s real `analyzeAutoTone` →
`to_srgb`), reporting each channel's `[p1, p50, p99]` and the
`p99−p1` span at every boundary:

```
stage                         R span   G span   B span   domain   R span %
0. raw 14-bit (pre-cal)        10351     7025     6770    16383      63%
1. calibrated 14-bit            9761     6706     6564    16383      60%
2. poly (colour matrix)         2587     1916     1700     4095      63%
3. inv16 (neg→pos inversion)     785      924     1064     4095      19%
4. post balance shifts           785      924     1064     4095      19%
5. post FUGC                     786      935     1065     4095      19%
6-7. FINAL toned (autoTone)      677      756      868     4095      17%
8. sRGB                          169      166      168      255      66%*
```
(*sRGB's own "span" isn't directly comparable — the ICC profile is
steeply nonlinear, see below.)

**The compression happens in exactly one place: the negative→positive
log inversion (stage 2→3).** Every stage before it preserves the
*fractional* span of its own domain almost exactly (raw and calibrated
14-bit both ~60-63%; poly, rescaled onto the 12-bit domain, is *still*
~63% — a matrix transform, not a compressor). The inversion collapses
that to ~17-19% of the 4095 domain in one step. Every stage *after* it —
balance shifts, FUGC, the full real `analyzeAutoTone` chain — leaves the
span essentially unchanged (785→677 for R, a mild net *narrowing*, not a
stretch). This is the same conclusion §1 reached by reading `dra`'s own
LUT values instead of measuring end-to-end spans, now confirmed a second,
independent way, on fresh data, with the full chain traced rather than
one subsystem: **nothing downstream of the inversion is a levels/contrast
stretch, so whatever code range the inversion produces is what survives
to the final image**, then gets visually amplified by the ICC profile's
own steep response curve in exactly this code region (pass 10's own
table: RPD-12 800-2300 maps to essentially the *entire* sRGB 0-254 range;
above ~2300 the curve is already flat).

**Reconfirmed, not taken on one frame's word.** Re-ran the full trace
independently: byte-identical numbers on a second run (no caching
artifact). Then ran the narrower `poly% → inv16% → toned%` span check
across 5 frames of this same fresh roll and, separately, 3 frames of the
old pre-recalibration `gold400.bin` (2 different rolls, both
calibration states):

```
fresh roll (post-recal)         poly%              inv16%             toned%
  frame 0                 [59.2,42.6,36.9]   [21.9,23.2,25.2]   [19.0,20.5,21.7]
  frame 1                 [63.2,46.8,41.5]   [19.2,22.6,26.0]   [16.5,18.5,21.2]
  frame 2                 [62.3,43.6,38.3]   [22.0,23.2,24.6]   [18.9,19.9,20.6]
  frame 3                 [59.7,43.9,39.4]   [18.5,21.4,24.6]   [13.0,15.1,17.2]
  frame 4                 [58.6,42.9,39.1]   [17.9,20.1,23.7]   [13.9,15.8,19.1]

gold400.bin (pre-recal)         poly%              inv16%             toned%
  frame 0                 [39.2,18.1,11.6]   [24.6,19.4,19.2]   [16.8,12.6,13.3]
  frame 1                 [44.7,24.1,15.5]   [30.0,24.4,23.2]   [19.9,14.5,12.7]
  frame 2                 [49.1,24.7,15.8]   [30.0,23.3,21.3]   [21.4,14.4,12.1]
```

Same shape in all 8 frames across both rolls: poly stage always well
above the inv16/toned stages (roughly double or more), the drop always
lands at the inversion step, and toning never recovers it — only ever
narrows it slightly further. The old roll's poly-stage numbers are
themselves lower for G/B (consistent with §6's own finding that this
roll's lamp duty was weak on those channels), but the *shape* of the
collapse — real headroom pre-inversion, collapsed post-inversion, flat
through toning — is identical regardless of which roll or which
calibration state. This is a structural property of the pipeline as
currently written, not a one-frame artifact or a one-roll artifact.

**Is the inversion's own compression a bug, or is it how this format is
supposed to work?** Genuinely open, and this doc does not resolve it —
but it's now clear exactly what to check. `f135_rom12_to_rpd12`'s own
docstring documents the design intent directly: `rpd12 = fpo + 1000 *
(log10(filmBase − c9) − log10(poly − c9))` is a **density-referenced**
encoding (RPD = "Reflection/Reproduction Print Density × 1000", a
standard photofinishing convention, not an arbitrary constant) where
`filmBase` (Dmin, clear film) is anchored to land at `fpo`, which balance
then carries to the neutral point (`fpo + setShifts ≈ nbp = 1550`,
confirmed in the docstring's own worked numbers). A real negative's own
usable density range is conventionally well under half of what a 4095
(≈4.1 density units) domain could represent, so *some* compression
relative to the raw/poly domains may be entirely correct and expected —
consistent with everything found in §1 about this being a
density/paper-referred system, not a display-linear one. What is **not**
settled: whether the specific numbers this formula produces — the exact
"1000" scale, the pedestal removal, `fpo`'s placement — reproduce the
*real* vendor formula's own numbers, because **this is the single
least-verified stage in the entire chain**: `F135_INVERT_PORTED = False`
is not a partial-port flag like the others in this doc, it's an
acknowledgment that no DLL call site was ever found for this specific
hardware path — the formula was reconstructed from first principles and
"confirmed correct by the owner's own eye on a real photo," never
Unicorn-verified bit-exact against the real DLL the way every stage
after it has been. Every other stage in this seven-finding investigation
that *has* been checked against the real DLL has come back correct; this
is the one stage that structurally can't be checked that way (no
reference implementation exists to check against) and has the largest
single effect on the final code range of anything in the chain.

## 9 — Pushed further into the inversion formula: the "1000" scale isn't
the lever, and balance parks every frame's shadow within ~35 codes of
`dra`'s own pivot, on every single frame of the fresh roll

Two follow-up checks on §8's lead, both against the fresh
post-recalibration roll, both self-correcting along the way.

**Check 1 — is the inversion's own "1000" density scale a plausible
culprit?** Recomputed `f135_rom12_to_rpd12`'s own formula
(`out = fpo + scale·(log10(base−c9) − log10(poly−c9))`, clamped) with
`scale` swept from 1000 (shipped) to 2500, same frame, same real
`base`/`c9`/`fpo`:

```
scale    R [p1, p99, span]        G [p1, p99, span]        B [p1, p99, span]
1000     [ 874, 1658,  785]       [1242, 2166,  924]       [1385, 2449, 1064]
1300     [ 872, 1892, 1020]       [1240, 2440, 1201]       [1385, 2768, 1384]
1600     [ 871, 2126, 1255]       [1237, 2715, 1478]       [1385, 3087, 1703]
2000     [ 869, 2438, 1569]       [1234, 3082, 1848]       [1384, 2135, 1128]
2500     [ 866, 2827, 1961]       [1230, 3539, 2310]       [1384, 4044, 2661]
```

Scaling this constant up does widen the span substantially — but almost
entirely by pushing the **highlight** end up; `p1` (the shadow point)
barely moves at all (R: 874→866 across the whole 2.5× sweep). This
follows directly from the formula's own structure: at `poly ≈ base`
(true Dmin, the darkest possible reading), the log-difference term is
already ≈0 by construction, so scaling a near-zero term by any factor
still leaves it ≈0 and `rpd12 ≈ fpo` regardless of `scale`. **This rules
out the "1000" constant as an explanation for "no real blacks"
specifically** — it's the wrong knob; it could only ever explain a
too-narrow *highlight* range, not a too-high shadow floor. (It doesn't
rule the constant out as *wrong* for other reasons — just not as this
symptom's cause.)

**Check 2 — does `dra`'s shadow band ever actually get real room to
work, on this roll?** §1 found it a complete no-op on the `docs/66`
reference frame. First pass at checking this on the fresh roll used the
wrong number — raw `inv16`'s own `p1` (which *is* comfortably below
`lowFixedPoint`=1550 on every frame) — before catching that balance runs
before `cna`/`dra` ever see the data. Redone against what actually feeds
the tone chain, `apply_balance_shifts`'s own output, across all 10 frames
of the roll:

```
frame  R margin   G margin   B margin      (positive = below lowFixedPoint, dra CAN engage)
  0      -53        -33        -33
  1       -6         12         14
  2      -32        -23        -15
  3      -25        -10         -2
  4      -29        -11         -1
  5      -30        -16         -5
  6      -12         -2          5
  7      -32        -21        -11
  8       -5         11         15
  9      -26        -12         -9
max      -5         12         15
```

**R never drops below `lowFixedPoint` on any of the 10 frames — dra's
shadow band never engages for red on this entire roll.** G/B dip below
it on a handful of frames, by at most 12-15 codes — a sliver, not a real
working range. This isn't scene-dependent noise: `setShifts_out =
(683, 297, 151)` and `fpo = (879, 1250, 1386)` are the same for every
frame on this roll (balance is a fixed per-stock formula, §5), so this
~35-code band around 1550 is structurally where every frame's shadow
point lands, by calibration, not by chance. It matches the design intent
`f135_rom12_to_rpd12`'s own docstring already states outright — `fpo +
setShifts` is *supposed* to land near `nbp` (1550) — which means
`dra`'s low-band mechanism having almost nothing to do is not an
accident of these particular photos; it's what this calibration produces
on any negative shot on this stock with this unit's current fpo/setShift
values.

**What this newly, sharply raises, not yet checked**: `fpo` is a
*generic*, shipped-with-the-stock constant (§5, confirmed DPI-static,
identical across every CN-default stock variant per the eleventh pass);
`base` (Dmin) and `c9` (the polynomial pedestal) are *measured on this
specific unit*. The formula's own construction guarantees `rpd12(Dmin) =
fpo` regardless of a unit's own base/c9 values — so `fpo` can't be
"wrong for this unit" in the sense of not matching Dmin, that's true by
definition. But `fpo`'s own *value* (879/1250/1386) was presumably tuned
by the vendor against a factory-fresh, factory-typical unit's own
characteristics — and this repo already has independent, documented
evidence this specific unit measurably drifts from its own factory
calibration (`docs/68`'s own account: "this unit's LEDs read well below
their 2022 registry values"). Whether that same kind of drift also
shifts where a *typical* negative's own density lands relative to a
generic `fpo` — i.e., whether this unit needs a unit-specific `fpo`
adjustment the same way it needed a unit-specific lamp-duty
recalibration — is a genuinely new question this pass raises and does
not answer. It would need either the real DLL's own output (the pending
comparison) or a documented factory calibration procedure for `fpo`
itself, neither of which this pass has.

## 10 — Correction: FUGC's `setLutInfo` was already real-DLL-verified,
including the exact near-identity case — this item is closed, not open

This doc's own priority list (below, until this section) carried
"FUGC's near-identity dmin correction — still not live-DLL-verified" as
item 3, citing the eleventh pass's own hedge (`pakon_fugc_golden.py`'s
`setLutInfo` cases "confirmed host-vs-host, not against the real DLL
specifically"). Picking that up directly rather than re-deriving it: it
was wrong, or at least stale. `pakon_fugc_golden.py`'s `run_set_lut_info`
already drives a genuine Unicorn execution of the real
`0x101f82c0`/`setLutInfo` entry point (`uc.emu_start` against the actual
DLL bytes, with hooked memory reads for the output LUT) — this is not
host-vs-host, and hasn't been since a *different*, earlier pass (`docs/66`
§"6.2 — parallel track… Track 1", 2026-08-11, not the eleventh pass)
added it while fixing a real, separate bug (`set_lut_info_channel` used
to raise on negative offsets; the real DLL handles them gracefully).

Ran it directly against the freshly re-extracted, MD5-verified DLL (same
one §5 confirmed): **all 12 offset cases pass, including
`identity_shipped_frame offsets=(0, -1, 1)` — the exact near-identity
case this whole thread has been asking about.** That case's offsets
(`0, -1, 1`) are described in the test's own comment as "this frame's
near-no-op offsets" — i.e., this is not a generic sanity check, it's the
specific input shape the reference frame's own FUGC stage actually sees,
and the real DLL reproduces the port's own near-identity output for it
exactly.

**FUGC's near-identity behaviour is therefore not an open question — it
is confirmed, bit-exact, real-DLL-verified correct.** The eleventh
pass's hedge was accurate as a statement about what that pass itself had
personally re-checked, but the underlying coverage already existed and
this pass has now independently re-run it and confirmed it still holds.
Removed from the priority list below as a live lead.

## 11 — The four unreplicated stages, picked up directly: the real
analyze-time call order and a first concrete (and ruled-out) cross-
capability mechanism

`docs/66`'s second/eighth/tenth passes established `analyzeArea`/
`analyzeAttributes`/`analyzeNoise`/`analyzeFalloff` all run between FUGC
and `autoTone` at **export** time, but explicitly left "whether any
mutate the pixel buffer `cna`/`dra` subsequently read… unclear yet" and
"not advanced by a live trace" every time it came up. Picked this up
directly, at the **analyze**-time driver instead (the one that actually
runs during rendering, not the export-pack-construction one pass 10
already read) — `AnsCnEnhancedPath`'s own per-scene analyze routine,
`0x10069490`-`0x10069d80` (already cited, but not fully disassembled, by
`docs/reports/autotone-scope-2026-08-10/falloff.md`).

**The real call order, read directly from a full disassembly of this
routine** (self-naming/address-matched against every constant already
catalogued in `pakon_analyse_roll.py`, not guessed):

```
… → analyzeFugc (0x100fed00)
  → balanceAreaImage (0x10102b20)
  → analyzeArea (0x100e16d0)
  → analyzeAttributes (0x100fb3d0)
  → [0x10112f30 — not yet identified]
  → analyzeFalloff (0x100fe960)
  → [0x100fb080 — not yet identified]
  → analyzeAutoTone (0x100fb730)          ← cna/dra/… all acquire here
  → analyzeSharpening (0x10106780)
  → [0x101081e0 — likely defects]
  → [0x100e04a0 — not yet identified]
```

Confirms the order the tenth pass already established from export-time
evidence, now from the side that actually matters (render-time
execution), and adds real precision: `balanceAreaImage`,
`analyzeArea`, `analyzeFalloff`, and `analyzeAutoTone` are **all four
called with the identical argument** — `&[ebp+0xc]` at every one of
these call sites. Cross-checked against `pakon_autotone.py`'s own
already-Unicorn-verified docstring for `analyzeAutoTone` itself: *"holder
is `[ebp+0xc]`, a by-value refcounted pointer"* — the exact same object
every one of the six tone subsystems' `acquire`/`analyze` calls receive.
This is a real, concrete, previously-undocumented fact: whatever these
"unreplicated" stages do to the shared `holder`, `analyzeAutoTone`'s own
subsystems receive that *same* object afterward — a genuine channel for
cross-stage influence that no prior pass had located (they knew these
stages ran nearby in program order; not that they share memory with the
already-verified subsystems).

**First concrete candidate through that channel, checked and ruled
out.** `balanceAreaImage` — by name, the most immediately relevant of
these to a "balance"/washed-out investigation — opens by calling
`AnsSceneContext::find` (`0x10020a40`, the exact `CAP_FIND_BY_NAME`
mechanism `dra`'s already-verified "lighting" lookup uses) for the
literal string `"area"`. Read the branch that follows the result flag
(`bl`, set by `setne` off the miss-sentinel comparison) in full: **a
*hit* (area's results already present) leads straight to an exception
throw** (`ColorNegativePath::balanceAreaImage`, `cnMethods.cpp` — a
genuine error path, not a "use area's data" branch); **a *miss* falls
through to the function's normal body.** Since `analyzeArea` runs *after*
`balanceAreaImage` in this same driver (per the call order above) and
nothing else populates `"area"` before this point for a fresh render,
this lookup is a miss on every real F-135 negative — the same
"defined, non-fatal miss" pattern `dra`'s own `find("lighting")` already
established, not a live data-consumption path. **This specific
mechanism does not carry `analyzeArea`'s output into balance.**

**What's still genuinely open, sized honestly**: `balanceAreaImage`'s own
*miss*-path body (what it does on every normal render, not yet read past
the branch above), `analyzeArea` itself (732 functions, the single
largest capability found in this whole project per `docs/65`),
`analyzeAttributes`/`analyzeFalloff`'s own bodies, and the three
addresses above not yet identified at all. Establishing the call order
and the shared-`holder` fact was tractable in the time available; fully
resolving whether any of these bodies write a `holder` field one of the
six tone subsystems reads is the same order of effort as the citras
driver's own multi-pass saga in `docs/66` — not something to finish in
one more sitting.

## 12 — A third independent post-recalibration roll still washes out;
`analyzeArea`'s own entry function read directly

**Wash check, 2026-08-13.** The app's own `/api/app/rolls` endpoint
still shows only `scan-20260812-091633` (§7's roll) as opened, but its
own cache directory (`~/Library/Caches/PakonScan/captures/`, checked
directly, read-only) has a capture the app hasn't opened yet:
`scan-20260812-094912.bin`, captured 09:50 the same day — a third,
independent, post-recalibration roll nobody has looked at through this
lens before. Rendered three of its frames through the same unmodified
production path as §7/§8:

```
                    sRGB [p1, p50, p99]                  % pixels B ≥ 239
frame 0    R[88,189,254]  G[84,200,253]  B[84,221,254]         26.7%
frame 1    R[72,142,250]  G[80,198,251]  B[79,212,254]         41.0%
frame 2    R[45,147,254]  G[87,202,253]  B[83,235,254]         46.7%
```

Same defect, same magnitude, third roll in a row. §7's finding holds.

**`analyzeArea`'s own entry function** (`0x100e16d0`, the exact address
called from the analyze-time driver in §11), read in full via a proper
function-bounded disassembly (499 lines): it opens with the identical
`find("area")` self-guard `balanceAreaImage` uses (checking whether area
has already been analyzed for this scene — an idempotency guard, not a
data-consumption path), then its own visible top-level calls are
dominated by a cluster of small helper functions (`0x100dc060`-
`0x100dc650`, unread individually) and two calls to `0x10199680` — the
address `pakon_analyse_roll.py` already cites as the
`"minArea4BaseWidth/Height"` strings, i.e. **geometric/dimensional setup,
not tonal computation** — plus repeated calls to the same validation/
error-throw helper (`0x1001f770`) seen throughout this project's own
disassembly work. No histogram, density, or brightness-shaped call is
visible at this level. The function ends with local-object cleanup and a
plain `ret`, no visible "register my result under this name" call back
into the shared `holder` the way `find()` implies a counterpart `add()`
must exist somewhere.

**Honestly scoped**: this is the *entry* function only — one address out
of `area`'s own 732. Its real defect-detection math (if any of it
touches tone) is necessarily buried in the un-traced sub-calls, chiefly
two still-unidentified addresses (`0x101186c0`, `0x101a3500`) and the
`0x100dcXXX` helper cluster. What this pass *does* establish: nothing
at the entry level resembles the kind of computation that would feed a
global brightness/level correction — the visible shape matches "area" 's
own name and role (spatial dust/scratch/blemish masking) more than a
tonal one. That's suggestive, not conclusive, and doesn't close the item
— consistent with §11's own honest sizing, fully resolving this would
mean working through a meaningful fraction of 732 functions, an
undertaking on the same scale as the citras driver's multi-pass saga,
not something to continue unprompted past this point.

## 13 — Settled: the real vendor software produces genuine deep blacks on
real film. The washed-out look is a port defect, not vendor-intended,
not a hardware limit.

**2026-08-13, from `finding/f235-and-vendor-shadows` on the private
remote** (a separate Claude Code session working from the Parallels/
Windows side, with the real F-135 physically connected — not this
session, not simulated). This closes the one question every section
above could not: what does the *real* vendor DLL, running the *real*
vendor software, produce on real film from this exact unit.

**Measured directly on frames recovered from the vendor software's own
render**, 8-bit luminance:

```
frame     size         p0.1   p1    p50   p99
img_48    2941×1960     6      9    135   229
img_77    2941×1960    31     33    109   226
23 coherent frames (median)   11    18     —    —
```

Compare to the port's own numbers throughout this doc: darkest 1% at
sRGB **60-110/255**, every roll, every frame, before and after the
hardware recalibration. The vendor's own render puts the same statistic
at **9-33/255** — a full order of magnitude lower, genuine deep black,
not "less washed out."

**Conclusion, stated as plainly as the evidence allows: the washed-out
look is a port artefact.** Not the scanner, not this unit's calibration,
not the film stock, not (per §9's structural argument, now empirically
confirmed rather than just architecturally suspected) something the
vendor's own tone chain also fails to do. Whatever produces real blacks
in the vendor's own pipeline, this port's own `analyzeAutoTone`
assembly — bit-exact against the real DLL leaf-by-leaf, per eleven
`docs/66` passes and this doc's own five further checks — is not
reproducing it end to end.

**How the frames were obtained, honestly caveated** (from the source
doc, not softened here): PSI has no configured off-machine export path,
so frames were recovered by raw signature-carving the VM's virtual disk
image, read-only, while the VM ran. Carving cannot follow NTFS
fragmentation, so a majority of the 83 candidates are scrambled
fragments, not real images — one, `img_81`, decoded cleanly and measured
`p1 = 0.6` (apparently perfect blacks) but is confirmed scrambled noise
containing a black rectangle; three others measured artificially dark
in a way that would have supported the *wrong* conclusion and are also
mis-carves. Real frames were separated from corrupted ones by a
row/column discontinuity ratio (natural images ≈1.0; fragment-spliced
ones run 3.6-14.1) — only `img_48` (1.18) and `img_77` (1.25) pass, and
`img_48` was additionally confirmed by eye as a complete, coherent
photograph. Two further real caveats: the recovered frames appear to be
**black & white**, not the colour negative this port's own defect is
tracked against — a like-for-like test of the tone/shadow mechanism, not
yet a full colour-pipeline comparison — and they're 8-bit JPEG, adequate
for "are there real blacks" but not for a stage-by-stage numeric
comparison, which needs 16-bit TIFF.

**Separately, and worth recording since it explains real trouble along
the way**: getting to this measurement surfaced a genuine, unrelated
finding — the scanner had **F-235 firmware loaded in the FX2's volatile
RAM** (PID `0x35F2`, a loaded-firmware identity, not the `0xF235`
bootloader personality this thread discussed earlier in this
conversation, which remains correctly diagnosed and unaffected). This
came from firmware-load activity during earlier hardware/EEPROM work
this month, persisted because FX2 firmware survives until *mains* power
is removed (a USB replug is not enough), and explains both the vendor
software's own initialization failures and why the wrong `TLA\Scan`
registry path (`ScannerType 7`, F-235's) was bound instead of
`TLB\Scan` (this unit's real `ScannerType 1351`, serial 16275). Fixed by
a mains power-cycle followed by `tools/pakon_load.py`, this project's
own loader, which correctly re-loads F-135 firmware — full derivation in
`docs/53-f235-firmware-state-and-buffer-fix.md` on the same branch. This
never affected any of this project's own Python/Go renders (`gold400.bin`,
every `scan-20260812-*.bin`, everything §1-12 above tested): `pakon_scan.py`'s
own connection gate has always hard-required PID `0xF135` to open at
all, so nothing this doc measured was ever captured through
mis-loaded firmware.

**What would make this fully definitive**: a clean export — colour
negative film, PSI's own default automatic settings, no manual exposure/
contrast correction, saved as 16-bit TIFF via USB mass storage (already
passes through to this VM) rather than recovered from the disk image.
That removes every caveat above and enables a real stage-by-stage
comparison against the port's own intermediate arrays, the way §8 traced
the port's own pipeline. Not yet done as of this writing.

## 14 — DX code check: this doc's own renders have already been using
the default stock the whole time, and it makes no difference anyway

Raised directly: the fresh roll's auto-detected DX (`dx_part1=4,
dx_part2=4`, shown as `"4-4"` in the app's own `/api/app/rolls`) is
known wrong for this film. Worth checking whether that's been quietly
affecting every render in this doc.

**It hasn't, for two independent reasons.** First: every render §4
onward in this doc constructed its own `Roll`/`AnselEngine` via
`open_capture(..., film_path="ColNeg")`, which — per `Roll.engine()`'s
own branch order (`if self.stock: … elif self.film_path: …`) — never
threads a DX code through at all; it always took the generic-fallback
path, the same one `scene_from_filmstock`'s own docstring calls
`stock_defaulted`. None of this doc's numbers ever depended on "4-4"
being right, because none of them used it. Second, checked directly by
constructing the engine both ways on the same frame: `dx_part1=4,
dx_part2=4` and the no-DX default both resolve to the *identical* file,
`sba-CN-default.dpi`, with identical `fpo`, identical `setShifts`, and
byte-identical rendered output — `"4-4"` isn't a code this project's
maps table has a specific stock-DPI entry for, so it falls through to
the same generic default regardless. Whether `"4-4"` is the right DX
code for this film is a real question worth fixing in the app's own
detection, but it has had zero effect on anything measured in this
document.

## What this changes about the open item list

**§13 changes the question this list is answering.** It used to be "is
this even a bug." It no longer is: the real vendor software, on this
exact unit, produces genuine deep blacks (§13 — sRGB p1 9-33/255 vs.
this port's own 60-110/255, an order of magnitude apart). Item 3 below
(prior wording: "may be vendor-correct for this exposure") is **refuted,
not just deprioritised** — kept here struck through, not deleted, so the
record shows it was a real hypothesis that got a real answer, not
quietly dropped. Everything else on this list keeps its prior status;
what changes is confidence that finishing it will find a real,
fixable bug rather than a dead end.

`docs/66`'s eleventh pass left two things open: FUGC's near-identity
dmin correction, and the four unreplicated
`analyzeArea`/`analyzeAttributes`/`analyzeNoise`/`analyzeFalloff` stages.
FUGC is now closed (§10). The four stages are **still open** — this doc
made real progress (§11-12) without closing them. What this doc's
sections close, cumulatively: the tone chain's own architecture is fully
characterized and is not the cause (§1); the Dmin/level hypothesis is
checked on real production data, before and after the hardware fix, and
is not the cause (§2-4, §7); the most architecturally attractive
software hypothesis this doc itself raised — a missing per-scene
`fpo` — is checked against fresh DLL disassembly and is not the cause
(§5); FUGC's near-identity behaviour is confirmed correct against the
real DLL (§10); §8-9's full stage trace pins the compression to the
negative→positive log inversion specifically and rules out its own
"1000" scale constant as the mechanism; and §13 now confirms, with real
(if caveated) vendor-software evidence, that this is a genuine port
defect, not vendor-intended behaviour. Updated priority order:

1. **The four unreplicated stages
   (`analyzeArea`/`analyzeAttributes`/`analyzeNoise`/`analyzeFalloff`)
   are the sole remaining concrete software lead**, and §13 raises the
   stakes on finishing this from "worth checking" to "very likely where
   the real bug lives," since every other software mechanism has now
   been checked against the real DLL and confirmed correct. §11 made
   real progress (the real analyze-time call order, the shared-`holder`
   fact connecting these stages to `cna`/`dra`'s own inputs,
   `balanceAreaImage`'s own `find("area")` channel ruled out
   specifically) and §12 read `analyzeArea`'s entry function directly
   (idempotency-guarded, geometrically-shaped, not obviously tonal) —
   without closing the item. `analyzeArea`'s own 732-function body,
   `analyzeAttributes`, `analyzeFalloff`, `balanceAreaImage`'s own
   miss-path, and three still-unidentified call targets remain unread.
2. **`fpo`'s own numeric value** (§9): whether this generic,
   shipped-with-the-stock constant needs a unit-specific correction the
   way this unit's lamp duty did — not resolvable by more DLL reading
   (`fpo`'s provenance is already settled, §5); needs either a
   definitive vendor-output comparison (partially available now via
   §13, though on B&W film — a colour-negative vendor comparison would
   settle this specifically) or a documented factory `fpo` calibration
   procedure this project doesn't have.
3. ~~Worth stating plainly after eight convergent findings: it remains
   possible this is not a software or hardware-calibration defect at
   all... the vendor's own real output would look similar on the same
   source material.~~ **Refuted by §13.** The vendor's own real output
   on this exact unit does not look similar — it has real blacks. Kept
   here, struck through, as the record of a real hypothesis that was
   tested and closed, not silently dropped.
4. **Get the definitive vendor comparison** — §13's own "what would make
   this fully definitive": colour negative film (not B&W), PSI's
   default automatic settings, exported as 16-bit TIFF via USB mass
   storage rather than carved from the disk image. Removes every
   caveat in §13 at once and enables a real stage-by-stage comparison
   against this port's own intermediate arrays (§8's own method is a
   ready-made template for that comparison once the file exists).
5. **Fix the measurement harness's Dmin methodology anyway — real bug,
   just not the cause.** `measure_python_autotone.py`'s `film_base=None`
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

§6's dates and calibration numbers were read directly off filesystem
metadata (`stat`, not assumed from filenames) and the calibration
directory's own preserved `.pre-*-<timestamp>.json` snapshots (this
project's own "never delete a calibration" convention, which is what
made this comparison possible at all) and the current `README.json`,
both parsed as JSON, not eyeballed. No capture content was read for
this section — only its filesystem timestamp and the separately-stored
calibration config, consistent with this project's rule against
describing `captures/` contents.

§7's roll was identified via the running app's own `/api/app/rolls`
endpoint (`pakon_app.py`, already running as this project's own backend,
queried read-only over the loopback HTTP API it already exposes — no
new capture was triggered, no hardware was touched, nothing about this
session's own tooling fired any new scanner activity) rather than
assumed or guessed. The capture itself was then opened and rendered
through the same unmodified `tools/pakon_render.open_capture` /
`scene_rpd12` / `AnselEngine.render_scene` / `.to_srgb` path §4 used, in
this session's own scratch workspace — the app's own live workspace for
this roll was never read from or written to. Only aggregate percentile
and clip-fraction statistics are reported above, per this project's rule
against describing `captures/` (or, here, the app's own cache directory)
contents.

§8 traced the same frame §7 already established shows the defect,
through every real intermediate array the production code itself
produces (`Roll.attach()`'s raw cache, `Roll.slice14()`'s calibrated
output, `pc.poly_hwc`'s direct return, `pr.scene_rpd12`'s direct return,
`sba_apply.apply_balance_shifts`'s direct return, the FUGC apply LUT's
direct output, `AnselEngine.render_scene`'s final output, and
`AnselEngine.to_srgb`'s output) — no stage was skipped or approximated,
and every function called is the same unmodified production code every
other section of this doc has been exercising. Re-run independently
after the fact specifically to check it wasn't a fluke: the full
per-percentile trace reproduced byte-for-byte identical on a second run,
and the narrower `poly%→inv16%→toned%` span check was then run across 5
frames of the fresh roll and 3 frames of the old pre-recalibration
`gold400.bin` — 8 frames, 2 rolls, both calibration states, same
collapse-at-inversion shape every time. No port file changed by any of
this.

§9's scale sweep re-derived `f135_rom12_to_rpd12`'s own formula directly
from real `base`/`c9`/`fpo` values (not approximated) at five scale
values; its "margin" table ran `sba_apply.apply_balance_shifts` (the
already-Unicorn-verified, real-DLL-bit-exact function this whole
investigation has relied on since `docs/66`'s eleventh pass) on all 10
real frames of the fresh roll, not a sample. The first ("Check 2") pass
at this used the wrong array (pre-balance `inv16`) and produced a
misleading result; caught and corrected within the same investigation
rather than left in — the corrected numbers are what's reported above.
No port file changed.

§10 was verified by directly running `pakon_fugc_golden.py` against the
freshly re-extracted, MD5-checked DLL (§5's own copy) — not by re-citing
the file's own docstring claims. §11's call-order table and the
`balanceAreaImage` branch analysis were both read from a full `r2`
disassembly of `0x10069490`-`0x10069d80` and `0x10102b20` onward — every
call target address was cross-checked against `pakon_analyse_roll.py`'s
own already-catalogued constants (`PATH_ANALYZE_FUGC`,
`PATH_BALANCE_AREA_IMAGE`, `PATH_ANALYZE_AREA`,
`PATH_ANALYZE_ATTRIBUTES`, `PATH_ANALYZE_FALLOFF`,
`PATH_ANALYZE_SHARPENING`) rather than assumed from proximity, and the
shared-`holder` argument was confirmed by literal byte match against
`[ebp+0xc]`, cross-referenced against `pakon_autotone.py`'s own
independently-already-verified identification of that exact offset. No
Unicorn execution was attempted for §11 (static disassembly only,
explicitly scoped that way — see §11's own closing paragraph on cost);
no port file changed.

§12's roll check queried the running app's own `/api/app/rolls` endpoint
and its cache directory's own file listing (both read-only) rather than
assume no new data existed, then rendered the newly-found capture
through the same unmodified production path every other section of this
doc uses. Its `analyzeArea` read used `af`+`pdf` (explicit function
boundary, not a raw byte-range guess) to get the complete, correctly
bounded 499-line disassembly of `0x100e16d0`, and every call target
address distinguishing "geometric helper" from "unidentified" above was
checked against `pakon_analyse_roll.py`'s own catalogued constants, not
assumed from context. No port file changed; no Unicorn execution
attempted.

§13's own evidence and methodology live entirely in
`docs/53-f235-firmware-state-and-buffer-fix.md` and
`docs/54-vendor-render-shadow-measurement.md` on the private remote's
`finding/f235-and-vendor-shadows` branch (`git fetch private`, not
merged into this branch — cite those docs directly for anything beyond
the summary above, including the full carving methodology, the
row/column discontinuity check, and the registry/firmware forensics).
This section only summarizes and cross-references; it does not
re-derive or re-verify that work independently. No port file changed by
this session as a result of §13 — it's a finding to act on, not yet
acted on.
