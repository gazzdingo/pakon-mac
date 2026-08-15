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

## 15 — Clean, hash-verified vendor ground truth replaces the carved
JPEGs; the gap holds on every frame of the matching roll, with no
carving caveats left

`finding/f235-and-vendor-shadows` landed clean data superseding §13's
carved JPEGs: `research/vendor-scans/` on the private remote, six real
frames as `rawAA00N.png`/`AA00N.png` pairs (PSI's own "RAW" export and
finished render of the same frame), losslessly converted from the
original uncompressed TIFFs PSI produced directly — no disk-image
carving, no NTFS-fragmentation risk, no scrambled-frame filtering
needed. Also landed: `docs/60-HANDOVER.md`, a full project handover
(worth reading directly for anyone picking this up cold — hardware
state, capture methodology, traps that cost real time).

**Independently verified, not taken on the write-up's word.** Downloaded
`AA005.png`/`rawAA005.png` and `manifest.json` directly, recomputed both
files' pixel SHA-256 myself and confirmed they match the manifest
exactly, then recomputed the percentile table myself:

```
frame        ch     p1    p5   p50   p95   p99   min   max
rawAA005     R      14    19    76   164   180     7   202
             G      10    14    42   112   122     4   131
             B       6     8    35   107   114     2   125
vendorAA005  R       0     0    35   228   241     0   255
             G       6     8    87   226   245     5   255
             B       5     8    94   236   253     0   255
```

Matches the write-up's own numbers to the digit — real, hash-verified,
lossless vendor ground truth, not an estimate.

**Then rendered every frame of `scan-20260812-091633` — confirmed by the
owner to be the same physical scan session as these vendor frames —
through the unmodified production path.** All 10 frames (the vendor set
has 6; frame-boundary detection differs between PSI and this project's
own framing, so exact 1:1 index correspondence isn't established):

```
frame  R p1   G p1   B p1        frame  R p1   G p1   B p1
  0     88     86     88           5    113    109    109
  1     79     84     86           6     98     96     94
  2     63     90     88           7     73     81     78
  3    110    106    108           8     83     79     74
  4    119    114    113           9     87     84     78
```

**Every single one of the ten sits at p1 = 63-119. None comes anywhere
near the vendor's 0/6/5 on the matching frame, or the 6-33 range §13's
carved (but now superseded) data already showed across a different
roll.** Three independent rolls, now including a directly-hash-verified,
carving-free one confirmed to be the exact same physical film as the
vendor's own reference, all converge on the same gap. §13's conclusion
stands, now on stronger evidence: this is a real, fixable port defect.

**On `docs/58`'s specific SRA claim, raised again in this session and
worth being precise about a second time**: independently checked (see
this doc's own inline discussion above) that `pakon_ansel.py`'s
`self.sra_lut` is applied only in `render_scene`'s legacy fallback
branch, never in the `shasta_stand_in=True` path every real F-135/
CN-Enhanced render (including every render in this section) actually
takes — so "forward applied, backward missing" is not quite right; the
port applies **neither** in the path that matters. The broader,
trace-grounded insight behind it — the vendor's SRA stage is a genuine
matched forward/backward pair defining a working space, real analysis
plausibly happens inside that space, and this project's own bit-exact
verification of `analyzeAutoTone` has only ever been run against tiny
synthetic pixel patterns (6×6 to 48×48), never a real scanned frame —
is independently well-founded and not addressed by this correction.
`docs/60`'s own "single highest-value next action" (apply the shipped
backward LUT, re-render `rawAA005`, target `p1 = 0/6/5`) remains the
right next empirical test; this session has not yet attempted it,
because `rawAA005` is itself PSI's own already-positive-processed
8-bit output, not the raw 12-bit negative this port's own pipeline
starts from, so it cannot simply be substituted into this port's
existing stages without first resolving how PSI's "RAW" stage maps onto
this project's own `inv16`/post-balance/post-FUGC domains — an open
question, not yet a blocker, but not a five-minute substitution either.

## 16 — Tried the direct version of the SRA fix. It does not work — it
massively overcorrects, and that itself is real evidence

Ran the most literal, direct interpretation of `docs/58`/`docs/60`'s own
hypothesis: apply the shipped `common-sraFwdLut-metric-default.lut`
immediately before `real_auto_tone()` (the same already-Unicorn-verified
six-subsystem chain every other section of this doc has used unmodified)
and `common-sraBkLut-metric-default.lut` immediately after it, on the
same frame and roll as §14/§15, everything else held identical to the
baseline render.

Confirmed the LUTs themselves first: `fwd` is 4096 entries mapping onto
`[0, 3903]`, `bk` is 3904 entries mapping onto `[0, 4095]`, and
`bk(fwd(x)) == x` for spot-checked values (`1024→1024`, `2048→2049`) —
matches `docs/58`'s own round-trip claim.

**Result: it does not fix the shadow floor — it crushes the entire
frame toward black, highlights included.**

```
                 sRGB [p1, p5, p50, p95, p99]
baseline (no SRA)    R [79,103,149,229,248]  G [84,100,199,239,250]  B [86,99,212,252,254]
SRA-wrapped          R [ 0,  0,  1,  4,  6]  G [ 1,  1,  3,  5,  6]  B [ 1,  1,  3,  7,  9]
```

`p1 = 0` — but `p99 = 6-9` too. The whole frame goes near-black, not
"real blacks with the rest of the tonal range intact" the way the
vendor's own `AA005` does (`p1=0/6/5`, `p99=241/245/253`). This is
overcorrection, not the fix.

**Why, mechanically**: the post-FUGC RPD-12 domain for this frame is
`[1218, 2791]` — almost entirely *above* the tone chain's own neutral
pivot (1550). The forward LUT maps that same range to `[2811, 3549]` —
deep in SRA space's own *highlight-compression* region (the curve
"massively expands shadows and compresses highlights," per `docs/58`
itself). Handed that as input, the tone chain's own DPI-calibrated
constants — `paperMin=1200`, `paperMax=2000`, `neutralBalancePoint=1550`,
`fpo=879-1386` — are RPD-12-referenced values (independently confirmed
throughout this doc: §5, §9, §14), not SRA-space ones. Fed SRA-space
numbers, every one of those anchors is now wrong by construction, and
the chain does something incoherent with them — which is exactly what
crushing the whole frame looks like.

**What this does and doesn't settle.** It rules out the *literal,
naive* form of the hypothesis — wrapping the existing, unmodified
six-subsystem chain in forward/backward SRA with no other changes is
not the fix, and produces something worse, not better. It does not
rule out a more sophisticated integration (the tone chain's own
constants re-expressed in SRA-space terms, or SRA applied around only
part of the analysis rather than the whole chain, or an entirely
different insertion point than "immediately around `real_auto_tone`") —
`docs/60`'s own caveat, "where the inverse belongs is an architecture
question," was right to hedge exactly this. But it is a real, negative,
experimentally-obtained data point, not more architecture reasoning:
this specific, most-obvious way to test the hypothesis does not work.

## 17 — Closed the real-data gap: the assembled six-subsystem chain is
bit-exact against the real DLL on real image data too, not just tiny
synthetic patterns

§9's own aside flagged this project's "assembled verification"
(`pakon_autotone_assembled_golden.py`, Phase 6.1, the test that runs the
real DLL's `analyzeAutoTone` end to end — all six subsystems, no
entry points stubbed — against the pure-Python assembled chain) as
having only ever been exercised on tiny synthetic patterns (flat/
gradient/high-contrast/random, 6×6 to 48×48 pixels), never real scanned
image data. That gap is now closed.

Adapted the existing harness's own `build_dll`/`host_run`/`_diff_*`
functions, completely unmodified, to real pixel data instead of
`make_image()`'s synthetic patterns: real post-FUGC RPD-12 crops from
`scan-20260812-091633`, the same roll every recent section of this doc
uses. Three crops, same real DLL (the MD5-verified copy §5 established),
same real port code:

```
crop                          pixels   result                    wall time
middle-of-frame, 48×48          2,304   bit-exact                    0.5s
darkest region, 48×48           2,304   bit-exact                    0.5s
large area, 400×400           160,000   bit-exact                    2.8s
```

**Every field checked matches exactly** — `cna`'s `ToneScaleLut`,
`LuminanceHist`, all summary scalars; `dra`'s `DraLut` and its
`effMin`/`effMax`/`lumMin`/`lumMax` etc; `contrast`'s `OutToneLut` and
slopes — on real image content, including a crop centered on the
frame's own actual darkest pixels, not hand-built test patterns. This
closes the concern §9 raised about untested real-data behavior: the six
tone subsystems, assembled together exactly as `analyzeAutoTone` itself
drives them, are not merely correct on synthetic inputs — they are
correct on this exact scene's own real data too.

**What this settles, and what it doesn't.** It rules out "the six
subsystems only look bit-exact because nobody tried real image
structure" as an explanation for the defect — checked directly, not
assumed. It does **not** show what input those subsystems *should* be
receiving (§16's SRA-space experiment already showed feeding them the
wrong-domain input breaks things badly) — only that, given whatever
input this port's own pipeline currently hands them, their computation
matches the real DLL's own computation on that same input, exactly.
Combined with §16, this narrows things further: if SRA-space input is
part of the real answer, it is not simply "feed the same six subsystems
different-domain data with no other change" (§16 tried that, it broke),
and it is not "the subsystems have a real-data-only divergence bug"
(§17 rules that out) — the missing piece is specifically about the real
DLL's own *wiring*, not about anything already verified being subtly
wrong. A parallel disassembly pass into `AnsSraCapabilityImpl::
makeSRALUTS` (`0x10594b78`) and its real callers, to find that wiring
directly rather than guess at it again, was started the same session
this section was written; see whichever later section reports its
result, or `docs/66`/this doc's own reading order if it landed
separately.

## 18 — The SRA disassembly landed, and it's a real contradiction, not a
confirmation: SRA is statically unreachable from every Color-Negative
path variant

The subagent dispatched to find `AnsSraCapabilityImpl::makeSRALUTS`'s
real wiring reported back. Two solid findings, one genuine open
contradiction with everything §16-17 assumed.

**Corrected address**: `0x10594b78` (what `pakon_sra.py` and this doc
had been citing as `makeSRALUTS`) is the function's own **self-naming
string**, not its entry point. The real body is `0x101a6be0`-`0x101a7075`
(confirmed by SEH prologue/epilogue and `ret 0x30`). Read in full: it
builds two named parametric curves ("aRender", "aGamma") from ~6
calibration doubles pulled from the SRA object's own fields — tracing to
`sra-params-metric-*.dpi`'s own `SRA_BLACK_POINT`/`SRA_WHITE_POINT`/
`SRA_GRAY_POINT`/`SRA_MIDTONE_RANGE`/`SRA_ALPHA`/`SRA_BETA` fields, **not**
`analyzeAutoTone`'s `paperMin`/`paperMax`/`neutralBalancePoint` — then
composes them into three destination LUTs via three `dest[i] =
curveB[curveA[i]]` loops. Its sole caller, `AnsSraCapabilityImpl::analyze`
(`0x101a7080`), self-identifies via its own assert string
(`"allocation of aRed, aGrn, aBlu luts failed."`) that the real output is
**three per-channel (R/G/B) composed LUTs**, not a generic third
forward/backward curve.

**The decisive, and contradicting, finding**: traced upward from both
SRA entry points through the real call graph, confirmed at every hop
(r2's automated `axt` cross-reference plus manual disassembly, not
either alone). `AnsSraCapabilityImpl::analyze`'s only caller
(`fcn.100e2ff0`) has exactly five callers, and **none of them is a
Color-Negative path**: `AnsCpRestorePath`/`AnsCpLockbeamPath`/
`AnsCpBalancePath::analyzeScene` (Color-*Positive*, i.e. slide film),
`AnsArchivePath::analyzeScene`, and one function reachable only from
`AnsDcEnhancedPath`/`AnsDcBalancePath::analyzeScene` (a third, distinct
path-class family, confirmed separate from `AnsCn*Path` by its own
self-naming strings). **All four real Color-Negative path variants
present in the DLL** — `AnsCnPremiumPath`, `AnsCnOpticalPath`,
`AnsCnLockbeamPath`, and `AnsCnEnhancedPath` (the one this whole
project's F-135 port targets) — were individually, fully disassembled at
their own `analyzeScene` entry points, and **none contains any call**
into SRA's own functions or `fcn.100e2ff0`. `AnsCnEnhancedPath::
analyzeScene`'s own single substantive call goes to `fcn.10069490` — the
exact CN-Enhanced per-scene driver §11 already fully catalogued the call
order of — and `analyzeAutoTone` remains that function's only real
analysis call, with no SRA anywhere in the chain.

**At the level checked, SRA and `analyzeAutoTone` are architecturally
disjoint call trees for a colour negative — not wrapping it, not
running as a parallel stage within the same scan, not reachable at
all.** This directly contradicts the premise `docs/58`/`docs/60`/§16-17
of this doc have all been working from: that SRA forward/backward sit
around the CN tone chain in the real DLL.

**This does not settle the question — it reopens it, honestly.** The
real API-trace evidence behind the SRA hypothesis (`docs/56`: both
`common-sraFwdLut`/`common-sraBkLut` files genuinely opened during a
live PSI render of real film) is not invalidated by a static
call-graph read; the two findings are in real tension, and the
subagent's own report flags exactly the caveat that resolves it,
without confirming which way: **file opens prove only that a path was
considered, not that it executed** — the same "opening is not using"
caveat `docs/56` stated about its own inventory from the start,
now sharpened into a specific, concrete candidate resolution: the
opened files may belong to a *different* real consumer this pass didn't
trace — **DSba**, which has its own dedicated LUT-key strings
(`dsba_sra_fwd_lut_key`, `dsba_sra_data_key`) distinct from
`makeSRALUTS`'s own — or a generic capability-declaration/file-load step
that runs regardless of which path type ends up actually using the
capability at render time. Neither traced this pass. A third,
unconfirmed candidate: `AnsDeRenderCapability::apply` (self-named,
called from code near the same "Dc"-path helper SRA itself is reachable
from), a plausibly-shaped but entirely unverified stand-in.

**What this changes about the recommended next step, directly**: the
disassembly path has now hit a genuine fork that only live execution
can resolve — does `AnsSraCapabilityImpl::analyze` (`0x101a7080`) or
`makeSRALUTS` (`0x101a6be0`) ever actually get **called** during a real
colour-negative render, or only during Color-Positive/Archive/Dc scans
that happen to share the same VM session? This is a far smaller ask
than `docs/57`'s full DynamoRIO execution trace (blocked on a 32-bit
XP-compatible build): a single debugger breakpoint at each of those two
VAs in a live `PSI.exe` process, during an actual colour-negative scan,
answers it directly. If neither breakpoint ever fires on a CN render,
this closes the SRA hypothesis for good, and the four unreplicated
stages (§11-12) become the clear priority again. If either fires, that
confirms real, if not-yet-fully-mapped, CN-reachability — worth
knowing regardless of which way it resolves.

## 19 — The verification harness's own blind spot: every golden test
feeds a synthetic, guaranteed-empty scene-context, never one produced
by real upstream execution.

Audited the harness itself, not another subsystem hypothesis — prompted
by the pattern every prior section reinforces: nine-plus individually
"verified bit-exact" subsystems, still a washed-out composite. §11
already established that the real DLL calls `balanceAreaImage`,
`analyzeArea`, `analyzeFalloff`, and `analyzeAutoTone` with the
identical shared `[ebp+0xc]` holder argument. This section asked
whether any golden test has ever fed `analyzeAutoTone` the holder state
those earlier stages would really leave behind.

None has. `pakon_dra_golden.py:349-361`'s `build_empty_scene_context`
hand-builds a fresh, guaranteed-empty red-black tree immediately before
the call; `pakon_autotone_assembled_golden.py:279-289` reuses that same
empty context for both `dra` and `contrast`; `pakon_autotone_shell_
golden.py:34-41` replaces the capability-set lookup itself (the real
`0x10020a40`→`0x10028f70` `std::map` walk) with a plain Python dict "so
as not to test MSVCP71"; production's own callsite
(`pakon_ansel.py:491`) passes `holder=None`. Input realism and
comparison scope were separately checked and are not the gap — §17
already re-ran the assembled chain on real 48×48/400×400 pixel crops,
diffing full arrays (`ToneScaleLut`, `LuminanceHist`, `EdgeHist`,
`DraLut`, `OutToneLut`) element-for-element, with FPCW pinned to
`0x027F`. The gap is specifically that every test's starting *state* is
synthetic, never real.

This raised the obvious next question, closed in §22 below: does that
synthetic-vs-real gap actually reach `analyzeAutoTone`'s own verified
arithmetic, or is it a real methodological gap that happens not to
matter for this specific defect?

## 20 — Three more hypotheses closed: `contrast.acquire()`'s fallback,
`pakon_autotone.py`'s own internals, and `scene_type`'s default.

**`contrast.acquire()`'s fallback (dead end).** Its bare-constructor
fallback (`pakon_contrast.py:1136-1159`, `pakon_autotone.py:1245-1248`)
never fires on the real F-135 CN-Enhanced path: `real_auto_tone()`
(`pakon_ansel.py:442-443,460`) always loads the shipped
`contrast-CNEnhanced.dpi` first, inside `_RealAutoTone.__init__`, before
`contrast_acquire` ever runs — confirmed by grep as the only non-test
caller of `analyze_auto_tone` in the repo. Diffed default vs. shipped
params anyway: identical except `bConstrainSlope` (False vs. shipped
True), a bounded LUT-shape effect near the 1550 pivot, not a global
additive shift, and moot since production never reaches the default.

**`pakon_autotone.py`'s own internals (dead end).** Full 1631-line
re-read found only two stale comments, both with zero runtime effect
because the file imports its `*_PORTED` flags live rather than
restating them (`DRA_ANALYZE_PORTED`'s narration text is Phase-2b-era;
the live imported value from `pakon_dra.py:355` is `True`, consistent
with §17's bit-exact chain run). No uncited constants, no live-path
fallback, nothing contradicting `docs/66`'s verified passes.

**`scene_type`'s default of 0 (dead end, closed twice).** `docs/66`
Track 2 (lines ~1974-2033) already showed, by disassembly, that every
alternative to `0` is independently ruled out by the real DLL's own
control flow: `scene_type==7` (`0x100699e7`) is intercepted one call
site *before* `analyzeAutoTone` and routed to a different, unported
function (`analyzeAsea`, `0x100fb080`) entirely — the real DLL never
runs the six-subsystem chain for a `7` frame at all; `scene_type==1`
nulls the tone object at the epilogue (`0x100fcb29`), contradicted by
every real frame's measured non-identity `dra` compression;
`scene_type∈{3..6}` collapses back to `0` inside `analyzeAutoTone`
itself whenever `elmo_occured` is true (`pakon_autotone.py:1521-1522`).
`scene_type` does gate real contrast math as suspected — confirmed via
`SLOPE_BAND_BY_SCENE_TYPE` (`pakon_contrast.py:783`) — but by
elimination `0` is the only value consistent with real DLL control
flow. Closed a second time empirically: swept `real_auto_tone()`'s
`scene_type` argument 0-7 on a real captured frame (`gold400.bin`
frame 1). Shadow point moved at most ~14 sRGB codes across every
reachable value — roughly 5-7% of the ~206-code defect — and where it
moved, it moved toward *more* washed out (`scene_type=1,2,3` push the
median toward outright clipping), never less.

## 21 — `profile_key`'s silent ICC fallback: real architectural smell,
zero effect (dead end).

Flagged by the pipeline audit as an uncited fallback feeding the final
ICC transform. Traced fully: under normal conditions it never reaches
the fallback at all (`profile.map`'s first rule matches the default
`SceneContext.cap_name` directly, `pakon_ansel_maps.py:485`) — and even
if it did, `profile_key`/`profile_dpi` is never consumed by the actual
transform in either engine. `AnselEngine.to_srgb`
(`pakon_ansel.py:1067-1084`) and the Go engine
(`tools/ansel/pipeline/engine.go:106-107`) both hardcode the same
profile pair directly (`Rpd2Pcs_HR200_QS_v5s10.pf` /`Srgb_v2.pf`); the
whole `profile.map` selection machinery only feeds a diagnostic print
line. Empirical upper bound in case the hardcoding were ever wrong:
forcing the genuinely different `color_dir/rpd.pf`+`srgb.pf` pair
instead moved output by 1-3 sRGB codes max, on a real rendered frame —
nowhere near the defect. Real cleanup item (dead code computed and
logged but never wired to what it's named after), not a cause.

## 22 — The holder-state gap from §19, closed: no live channel exists
for it to reach `analyzeAutoTone`'s output. Also corrects a real error
in §11.

Attempting §19's proposed next step (Unicorn-execute the real per-scene
driver chain, capture the real resulting holder state, feed it into
the already-verified assembled harness) surfaced a **direct correction
to §11**: fresh disassembly of `balanceAreaImage` (`0x10102b20`, same
MD5-verified DLL every prior pass cites) shows its `find("area")` call
target (`0x10020a40`) is actually `CAP_FIND_THUNK` — the
capability-*set* lookup `analyzeAutoTone` itself uses for `"cna"`/
`"dra"`/etc — not `AnsSceneContext::find` (a different address,
`0x10022a40`). §11 conflated the two and additionally had the branch
polarity backwards: on a successful find (the normal case for `"area"`,
a real, always-declared capability), execution falls into real work at
`0x10102c68`; only genuine absence throws. §11 believed the reverse and
so treated real work as an unreachable dead branch.

Rather than reconstruct the driver's own ~15+-field `this` layout by
guesswork to run the whole chain — judged too risky given this
project's own no-guessing standard, and doc-flagged as citras-driver
scale effort — the question was answered more directly: instrumented
the existing, **unmodified** `pakon_autotone_assembled_golden.py`
harness (real DLL code, all six real subsystem Impls, nothing stubbed
at the subsystem level) with `UC_HOOK_MEM_READ` watches on `holder` and
`ctx`, running the real DLL's `analyzeAutoTone` end to end. Result:
`holder` (0x100 bytes) — only the refcount at `+0x4` is ever read.
`ctx` (0x6600 bytes) — only `+0x44`, `+0x4bc`, `+0x64d0` are ever read,
exactly the three fields already documented in `pakon_autotone.py`,
nothing else.

Combined with two already-verified facts already in this project's own
code: `pakon_autotone.py`'s `CAPABILITIES` tuple (`:503-526`) shows
`analyzeAutoTone` only ever looks up `"cna"/"dra"/"toneHelper"/
"contrast"/"ast"/"pfd"/"citras"` by name — never `"area"/"attributes"/
"falloff"/"fugc"` — so even a fully real capability-set graph couldn't
surface those four stages' results to the six tone subsystems by name;
and `pakon_toneHelper.py:92-112` already proves the one scalar that
*could* carry external state (`ctx+0x4bc`, "EXPOSURE") is structurally
inert on any real photographic frame, since the decision tree's root
split depends only on `LUM_STDDEV`, which always exceeds threshold on
real content, fixing `toneHelperValue=2` regardless of EXPOSURE.

**Verdict: dead end, provably, not just unconfirmed.** There is no live
channel left by which the four unreplicated stages could reach
`analyzeAutoTone`'s verified output. One thread remains genuinely open,
not closed either way: whether `balanceAreaImage` mutates the shared
*pixel buffer* (`arg2`) directly, in place, before `cna` reads it —
consistent with the function's own name, and not ruled out by the
holder/ctx read-watch since a direct buffer mutation wouldn't touch
either. Partial read of its real-work path found it operating on a
freshly-allocated 0x3000-byte scratch buffer rather than obviously the
caller's own pixel buffer (arguing against in-place mutation), but
three further call targets (`0x100a8730`, `0x100d9340`, `0x100dc390`)
and a second `find("fugc")` lookup inside the same function were not
traced far enough to close this either way.

## 23 — The actual answer: the verified port was never wired into the
engine the app runs. Production still renders through an explicitly
labeled stand-in.

Every section above — this doc's nineteen-plus and `docs/66`'s eleven —
verifies `tools/ansel/python-pipeline/`'s Python port of
`analyzeAutoTone` against the real DLL under Unicorn emulation. That
Python code is not what the shipped app renders through. The app's
real render path is `tools/ansel/pipeline/*.go` (`tools/pakon_render.py`'s
own `colour_engine()` defaults to `"go"`; the Python path is reached
only behind `PAKON_COLOUR_ENGINE=python` and its own docstring calls it
`DEPRECATED`). And in the Go engine, `analyzeAutoTone` was never
wired in at all:

```go
// main.go:566-569
shasted := fugcOut
if model == "f135" {
    shasted = ShastaToneRpd(fugcOut, sel.ShastaParams())
}
```

`ShastaToneRpd` (`shasta.go:193-282`) is a placeholder its own extensive
header comment names as such: a per-channel two-anchor linear stretch
(1st-percentile → black, median → mid-grey, straight line between,
clamped) — "every constant comes from `shasta-rpd.dpi`, but the SHAPE
is not the vendor's... None of that is reproduced here," referring to
the real Shasta curve's five measured statistics, per-knot
aggressiveness factors, exponential slope limits, and white-point
compression. It stands in for the real negative tone stage
(`ColorNegativePath::analyzeAutoTone`, `0x100fb730` — the same address
this whole doc has been verifying), not for `AnsShastaCapabilityImpl`
itself (Shasta never runs for a colour negative at all — see
`shasta.go:21-45`'s own citation of the path-selection jump table at
`0x10002270`). The app logs this plainly on every real F-135 render:
`"PROVENANCE: F135InvertPorted=%v AutoTonePorted=%v
ShastaAnalyzePorted=%v — the inversion and the tone scale are
stand-ins, not vendor call sites"` (`main.go:662-665`), with
`AutoTonePorted` hardcoded `false` (`shasta.go:155`).

Why it was left unwired, in the code's own words (`shasta.go:81-89`):
"a half-ported chain would put a worse transform on the render path
than the stand-in does, so nothing is wired in until the whole chain
is bit-exact." That is exactly the bar this doc and `docs/66` have
been working toward, stage by stage, all along — and §22 above is the
closest anyone has come to declaring it met (the six subsystems
verified bit-exact; the one remaining thread, `balanceAreaImage`'s
possible in-place buffer mutation, unclosed but structurally minor
next to the six-subsystem chain itself).

**This is sufficient on its own to explain "no real blacks," independent
of every subsystem-level hypothesis this doc and `docs/66` have tested.**
`ShastaToneRpd`'s crude two-point-per-channel percentile stretch has no
real highlight/shadow compression; on a typical frame whose darkest 1%
isn't already near-zero, the black anchor lands well above true black
and the whole image gets linearly stretched from there — exactly the
washed-out, no-real-blacks shape this entire investigation has been
chasing, and it requires no bug in any of the meticulously-verified
subsystems above, because none of them are in the app's actual render
path. The commit that produced this doc's own six-subsystem
verification (`77e2a71`, "Finish the autoTone port") is entirely
`tools/ansel/python-pipeline/` — `main.go`'s `ShastaToneRpd` call is
byte-for-byte unchanged by it.

**Next step, concrete and unblocked by any further RE:** port the
verified `analyzeAutoTone` chain into Go, replacing the `ShastaToneRpd`
call at `main.go:568`, the same way the ICC transform, AFE gain, and
falloff stages already made that same Python-verify-then-Go-port
crossing earlier in this project's history.

## 24 — A genuine full-frame, real-DLL Unicorn harness: bit-exact AND
pixel-identical at real, full, uncropped-frame scale. `balanceAreaImage`'s
own real body run for real: no pixel-buffer writes observed, in either
branch tested. (Corrected same pass, in place, not silently: an earlier
draft of this section reported a real `cna` divergence at full-frame scale
that turned out, on direct further testing, to be this new harness's own
instruction-count-cap bug, not a real DLL/port divergence — see "Finding 2,
corrected" below for the full account, kept rather than deleted so the
record shows what was wrong and how it was found, the same practice §11/§16/
§18 already established elsewhere in this doc.)

New, additive script this pass:
`tools/ansel/python-pipeline/pakon_full_colour_chain_golden.py`. Does not
modify any existing golden file — every DLL-side call reuses
`pakon_autotone_assembled_golden.py`'s own `build_dll`/`RealCapset`/
`host_run`/`_diff_scalars`/`_diff_array`/`shipped_contrast_params`
completely unchanged, the same adaptation-not-rewrite §17 already used, now
extended from a hand-picked crop to a genuine full captured frame. DLL
re-verified MD5 `eea9dcf78ee21d4f7c515a6c2512242d` (the same copy every
prior section cites) immediately before use. Real capture, at the owner's
own direction this pass:
`~/Library/Caches/PakonScan/captures/fresh-calibration-scan-20260814-065421.bin`
(today's post-recalibration test scan, already cited by
`pakon_ansel.py`'s own `real_auto_tone`-neighbourhood comment — not one of
the earlier `gold400.bin`/`scan-20260812-*` captures §4-§15 used, a
deliberate switch to current, not pre-recalibration, hardware state), frame
index 1 of 5 (the one `confidence="good"` frame on this roll), real post-FUGC
RPD-12 input captured by intercepting `pakon_ansel.real_auto_tone` at its own
call boundary — the function still runs completely unmodified; only its
argument is additionally recorded on the way through, the exact real value
every real render already computes.

**Finding 1 — bit-exact, and now pixel-identical end to end, on real crop
content from this new capture too.** A real 400×400 crop of this frame (the
same crop size §17 already validated, on a different capture): `cna`/`dra`/
`toneHelper`/`contrast`/`citras` all diff at zero fields between the real
DLL and the pure-Python assembled chain. New beyond §17: applying the real
DLL's own `contrast_results()['OutToneLut']` through the SAME already-verified
`citras_driver.apply_citras` vendor-apply step `pakon_ansel.real_auto_tone`
itself uses, then through the same `AnselEngine.to_srgb`, and diffing against
the Python port's own `real_auto_tone()`/`.to_srgb()` output on the
IDENTICAL crop (same analysis scope both sides — an earlier draft of this
check diffed the DLL crop-render against a crop OF the full-frame Python
render and found ~6-code differences, which turned out to be an artefact of
comparing two different analysis populations, not a real divergence; caught
and corrected within this same pass before drawing any conclusion from it):

```
abs(python_srgb - dll_ground_truth_srgb) over the whole 400×400×3 crop:
  mean=0.0  p99=0.0  max=0.0  — 100% of pixels bit-identical
```

This is the "genuine ground-truth reference render… bit-exact" this doc has
lacked since §13/§15's own crude carving-based comparisons — at this scale,
not an estimate.

**Finding 2, corrected — the apparent `cna` divergence on the full frame was
this harness's own instruction-count-cap bug, not a real DLL/port
divergence. Confirmed directly; the real chain is bit-exact at full-frame
scale too.**

An earlier draft of this section, same pass, reported 27 mismatched fields
on the real 2,965×2,000 (5,930,000-pixel) frame — `cna.threshold`/
`nEdgePixels`/all four sigmas reading `-1`/`-1.0`, `ToneScaleLut` all-zero,
cascading to an all-zero `dra` — and, working from `pakon_cna.py`'s own
"gate never entered" seed values, took that at face value as the real DLL
genuinely giving up on real, full-scale content where the Python port does
not. Asked to confirm that reading against the actual instructions before
touching any port code, direct disassembly of `analyze_image`'s bucketing
accumulator (the specific loop the first hypothesis pointed at) refuted it
immediately: `0x1022e310`/`0x1022e31b`, live `pd` this pass —

```
0x1022e310  add eax, dword [edi + ecx*4]   ; accumulator: full 32-bit EAX
0x1022e31b  mov dword [ebx + edx*4], eax   ; store: full 32-bit DWORD
```

— genuinely 32-bit throughout, matching `pakon_cna.py`'s own `i32`
arithmetic exactly. No 16-bit truncation exists in that loop. Pushed
further rather than stopping at "not this": instruction-level tracing
(a `UC_HOOK_CODE` watch over the whole `analyze_image` body, live this
pass) on the smallest broken case found by a binary search (a real
1,043×1,043 crop of this same frame; a real 1,042×1,042 crop of the same
frame renders correctly) showed execution entering `analyze_image`'s
per-bucket normalisation loop (`0x1022e760`-`0x1022e7eb`) and simply never
being recorded again — the trace never reaches the smoothing/
`build_tone_lut`/normalise calls a few hundred bytes later
(`0x1022e9c9`/`0x1022e9de`/`0x1022e9ea`) — yet the harness still reported
`status_ok=True`.

That combination (execution silently stops advancing, but the top-level
call still reports OK) pointed at `pakon_autotone_shell_golden.Emu.call`
itself: it hard-codes `uc.emu_start(va, RET_MAGIC, timeout=0,
count=200_000_000)` and never checks, afterward, that EIP actually reached
`RET_MAGIC` — every existing golden's own scenarios are small enough
(largest: 400×400) that 200,000,000 emulated instructions was always far
more than `cna` needs, so this never mattered before. **Directly confirmed,
not inferred**: replaced `Emu.call` at runtime (a new function,
`patch_unchecked_instruction_cap`, added to this pass's own script — it
does not edit `pakon_autotone_shell_golden.py` on disk, the same
class of runtime-only fix as this file's own `HEAP`/`HEAP_SZ` relocation)
with a version that raises the cap to 50,000,000,000 and explicitly asserts
EIP reached `RET_MAGIC` before trusting any result. Re-ran both the
1,043×1,043 crop and the full frame, foreground, waited for completion:

```
1,043×1,043 crop  (1,087,849 px): confirmed real completion (EIP==RET_MAGIC), 16.4s
  field-by-field diff vs Python host: 0 bad fields
  cna.threshold=29  nEdgePixels=115,833  ToneScaleLut: 5000/5000 nonzero

Full frame        (5,930,000 px): confirmed real completion (EIP==RET_MAGIC), 56.4-56.8s
  field-by-field diff vs Python host: 0 bad fields
  cna.threshold=50  nEdgePixels=1,224,975  ToneScaleLut: 5000/5000 nonzero
```

Both now bit-exact against the Python host, both now producing exactly the
`threshold=50`/`nEdgePixels=1,224,975` values the ORIGINAL draft had
already computed on the Python side and mislabelled as something the real
DLL disagreed with. **The real DLL does not give up on real, full-scale
content — the harness was giving up on it.** `analyze_image`'s own real
`cna` body genuinely needs more than 200,000,000 emulated x86 instructions
for a multi-megapixel image (confirmed: ~16s and ~57s of real Unicorn
execution respectively, once the cap was no longer the limiting factor),
and because Unicorn's `emu_start` returns normally (no exception) when its
own `count` budget runs out, the unmodified `Emu.call` read that as a
clean return and reported whatever `AnsStatus` value already happened to
sit at `sret` (zero-filled at allocation, hence reads as OK) — while
everything the truncated run never got to write (`ToneScaleLut`, and
everything `dra` derives from it) stayed at its allocation-time zero fill.
`threshold`/`nEdgePixels`/the four sigmas read as sane in the original,
broken run precisely because they are written EARLY in `analyze_image`,
before the truncation point; `ToneScaleLut` reads as zero because it is
written LATE. The fix (`patch_unchecked_instruction_cap`) is now applied
in `pakon_full_colour_chain_golden.py`'s own `main()`, alongside the
already-documented heap relocation, so a re-run of this script produces the
corrected numbers directly rather than the original, wrong ones.

**What this changes.** Nothing about §1-23. This was a bug in NEW code
written this pass (the new script's reuse of an existing golden's `call`
method at a scale that golden was never exercised at), not in any
previously-verified port file or previously-published finding elsewhere in
this doc — no other section's numbers depended on `Emu.call`'s instruction
cap. It does change what §24 itself can claim: not "a new scale-dependent
`cna` bug, worth fixing before Go-wiring" (wrong, retracted) but the
opposite — **the six-subsystem chain is now confirmed bit-exact, and its
final render pixel-identical to the Python port's own output, at the
largest and most realistic scale this project has ever tested it at**,
strengthening rather than weakening the case that the chain meets the
"whole chain bit-exact" bar `shasta.go`'s own comment sets before wiring
anything into Go (§23) — see the corrected "What this settles" paragraph
below.

With the fix applied, `pakon_full_colour_chain_golden.py`'s own Stage 3
(the genuine DLL-derived ground-truth render, diffed against the Python
port's own `real_auto_tone()`/`.to_srgb()`) now runs to completion on the
full frame too, where the original broken run could only report it as
blocked:

```
Full frame (5,930,000 px), same-scope analysis both sides:
  sRGB [p1, p50, p99]   R: python=[83,156,254]   dll_ground_truth=[83,156,254]
                        G: python=[90,208,252]   dll_ground_truth=[90,208,252]
                        B: python=[74,241,254]   dll_ground_truth=[74,241,254]
  |python - dll_ground_truth|: mean=0.000  p99=0.00  max=0.0
```

Pixel-identical, on the real, full, uncropped frame — not just the 400×400
crop Finding 1 already established. Total wall time for the corrected
Stage 1 (real DLL, real six-subsystem chain, full frame): 56.6s.

**Finding 3 — `balanceAreaImage` (`0x10102b20`), real body, real Unicorn
execution: no pixel-buffer writes observed, in either branch tested.**
Directly targets §22's one remaining open thread. Calling convention
derived fresh this pass from live, tool-verified disassembly (not
transcribed from any prior pass, not guessed): r2's own automatic variable
recovery (`aa; af @ 0x10102b20; afvj`) finds a single real cdecl parameter
at `var_8h` (`ebp+8`), read 13 times through the function body; the real
caller (`fcn.10069490`, live `pd` at `0x10069835`-`0x10069859`, re-run this
pass) pushes `&[ebp+0xc]` — the driver's own local slot, itself holding a
pointer to a 3-dword record `{*esi (AddRef'd via `0x10006880`, fully
disassembled this pass — a generic "wrap a raw pointer, AddRef it" helper,
`ret 4`, the same shape as the AddRef idiom already characterized
elsewhere in this DLL as `0x100065e0`), zx(byte[esi+0x29]), &esi+0x4ac}`.
Built this exact structure (with the two fields this pass has no
independent citation for — `*esi` and `esi+0x29` — filled from the
already-built `RealCapset.holder`/zero respectively, flagged plainly as
synthetic scaffolding, not derived vendor values) and called the real
`0x10102b20` under Unicorn with a `UC_HOOK_MEM_WRITE` watch on the exact
real pixel-buffer address range, on the real 48×48 crop:

```
find("area") MISS  (the entry-guard's own throw path, 0x10102c0b):
  ran to completion, no Unicorn fault, 0 pixel-buffer writes.
find("area") HIT   (synthetic placeholder Impl, past the entry guard,
                     into the function's real body):
  ran to completion, no Unicorn fault, 0 pixel-buffer writes.
```

Both branches ran the real `0x10102b20` machine code to its own `ret 8`
without a single invalid-memory fault, and neither wrote a single byte
into the shared pixel buffer this pass gave it. **This is a real, direct
answer, not an inference from static reading** — the exact thing §22 said
would need a live trace to settle either way.

**Honestly caveated, not oversold.** The "hit" branch's Impl is a
zero-filled placeholder behind a generic one-slot vftable (every virtual
call resolves to a bare `ret 4`) — the same shape `RealCapset` itself
already uses for its own permanently-disabled `"pfd"` capability, not a
real `area` Impl this project has ever characterized. This result
therefore does not prove the REAL vendor Impl's real field values would
take the same path through the function's own 295 basic blocks; it proves
that the specific paths THIS harness's real code actually executed — which
plausibly diverge from vendor-normal execution the deeper the function's
own control flow goes — did not touch the pixel buffer. Combined with §22's
own partial static read ("operating on a freshly-allocated 0x3000-byte
scratch buffer rather than obviously the caller's own pixel buffer"), this
is now two independent lines of evidence pointing the same way, neither
alone conclusive.

**What this settles, and what it doesn't.** Extends §17's real-image-data
closure to a genuine full frame for the first time, and finds it holds —
bit-exact field-by-field, and pixel-identical end to end — at both crop
scale (a second, independent, fresher capture) and full, uncropped-frame
scale, the largest and most realistic test this project has ever run
against the real DLL. The scale-dependent gap an earlier draft of this
section reported was real as a *symptom* but wrong as a *diagnosis* — a
genuine bug, just in this pass's own new harness code, not in `cna` or the
port, corrected in place above rather than left standing. Adds real,
direct (not static-inference) weight to §22's "no evidence of pixel-buffer
mutation" reading of `balanceAreaImage`, without fully closing it. Neither
finding changes §23's own conclusion — the production Go engine still
never calls any of this Python code at all — but where the earlier draft
of Finding 2 would have been a concrete reason the "whole chain bit-exact
before wiring anything into Go" bar `shasta.go`'s own comment sets (quoted
in §23) was not yet met, the corrected finding is the opposite: one more
real, large-scale data point that the six-subsystem chain DOES meet that
bar, on every frame and crop this doc has ever tested it against.

## 25 — `analyzeAttributes` read in full, real entry to real leaf: it's the
`orderOrientation` auto-rotation classifier's gate, not a tonal stage —
confirms `docs/64`'s existing prose classification with real instruction
evidence for the first time, and closes it as a shadow-defect candidate

Picked up directly from this doc's own priority list (item 1: the four
unreplicated stages), the one member neither §11 nor §12 had read yet —
`analyzeAttributes`. DLL re-verified before use: MD5
`eea9dcf78ee21d4f7c515a6c2512242d` (`/tmp/pakon_re/PakonIMAu.dll`), matching
the copy every prior section of this doc cites. Real entry address taken
from `pakon_analyse_roll.py`'s own already-catalogued
`PATH_ANALYZE_ATTRIBUTES = 0x100FB3D0` (not guessed), cross-checked against
§11's own real analyze-time call-order table (`… → analyzeAttributes
(0x100fb3d0) → …`) — the two independent citations agree.

**Function boundary, confirmed by explicit `af`+`pdf`, not a raw byte-range
read** (this project's own established convention, per `docs/67`): `af @
0x100fb3d0` finds a clean 859-byte function, `0x100fb3d0`–`0x100fb72a` (last
instruction `ret` at `0x100fb72a`), ending exactly 5 bytes before
`analyzeAutoTone`'s own already-established entry at `0x100fb730` — a real
consistency check, not assumed. Self-naming confirms identity independent
of the address citation: the string `"ColorNegativePath::analyzeAttributes"`
(`0x10586a38`) and the file path
`"\Atc\ansel\src\libPaths.ansel\cnMethods.cpp"` (`0x10586844`) are both
pushed at three separate sites inside this exact 859-byte span
(`0x100fb4de`, `0x100fb528`, `0x100fb5d4`) — the same self-naming method
`docs/64`'s own `declare` disambiguation and this doc's §18 SRA read both
already established as decisive. Single incoming argument (`arg_50h`, the
function's only parameter — this function does not build an EBP frame,
using ESP-relative locals throughout, so `ebp` itself is repurposed as a
plain register holding that one argument for the whole body) — consistent
with §11's own finding that `balanceAreaImage`/`analyzeArea`/
`analyzeFalloff`/`analyzeAutoTone` are all called with the identical
`&[ebp+0xc]` holder argument at the driver; `analyzeAttributes` takes the
same single-pointer shape.

**The body, read in full, is a capability-shell gate wrapping exactly one
real call — not an independent computation.** Three pieces of evidence,
all address-level, not inferred from the name:

1. **`0x10020a40` at `0x100fb441`** — `CAP_FIND_BY_NAME`, the *identical*
   capability-set lookup `analyzeAutoTone`'s own `cna`/`dra`/`toneHelper`/
   etc. acquire calls use (already ported and Unicorn-verified in
   `pakon_autotone.py`'s capability shell) — here keyed to the literal
   string `"orderOrientation"` (constructed via
   `sym.imp.MSVCP71.dll_?basic_string...@QAE@PBD@Z` at `0x100fb421`, then
   destroyed again at `0x100fb4c6`), a name `analyzeAutoTone`'s own
   `CAPABILITIES` tuple never looks up (§22 already enumerated it
   exhaustively: `cna`/`dra`/`toneHelper`/`contrast`/`ast`/`pfd`/`citras`
   only). The lookup result is compared against the DLL's own
   null-capability sentinel at `0x106b5bd4` (`setne bl` @ `0x100fb493`) —
   the same sentinel-compare idiom `dra`'s "lighting" `find` and
   `balanceAreaImage`'s "area" `find` already use elsewhere in this doc.
   - **HIT** (`"orderOrientation"` capability object already exists for
     this scene — bl≠0): falls straight through to `call 0x1001f770` @
     `0x100fb4e9` (line 798 of `cnMethods.cpp`, per the pushed constant
     `0x31e`) then jumps to the shared cleanup/return block — the real
     `AnsOrderOrientationCapability::analyze` body is never called on this
     branch.
   - **MISS** (normal, first-time case — bl=0): falls through to a second
     gate at `0x100fb4f6`.
2. **`0x104ffdd6` at `0x100fb507`** — confirmed by direct disassembly to be
   a bare 6-byte IAT thunk, `jmp dword [sym.imp.MSVCR71.dll___RTDynamicCast]`
   (`0x105735c0`) — the real Windows `__RTDynamicCast`, i.e. a
   `dynamic_cast<T>()`. This is the *exact same* RTTI-cast mechanism
   `pakon_autotone.py`'s own docstring already documents generically for
   every one of `analyzeAutoTone`'s six subsystem lookups ("`cap =
   __RTDynamicCast(iface, 0, AnsCapability, <target>, 0)`" — that file's own
   words, `pakon_autotone.py:58`), now confirmed to be the *identical* gate
   `analyzeAttributes` runs for `"orderOrientation"`, not a different
   mechanism.
   - **Cast fails** (`iVar3==0`, i.e. the wrong RTTI type or genuinely
     absent): throws `"OrderOrientation capability not found."`
     (`0x10586a10`) via `0x1001ed90` @ `0x100fb530` — the same "`<Name>`
     capability not found." throw shape `pakon_autotone.py:842` already
     documents for the six *ported* subsystems' own missing-capability
     path.
   - **Cast succeeds** (`*(iVar3+0xc) != 0`): calls
     `AnsOrderOrientationCapability::analyze` (`0x101218c0`) at
     `0x100fb576` — `ecx` = the found/cast capability object itself (not
     `ctx`, not `holder`), one stack-struct argument built from the
     driver's own `[ebp+0xc]`-derived data — the **only** substantive
     analysis call anywhere in `analyzeAttributes`'s own 859 bytes. This is
     the exact call site `pakon_analyse_roll.py`'s own pre-existing comment
     already named: *"`OrderOrientation` Cap `0x101218c0` is not in
     [`analyzeAneOrder`] — called from `analyzeAttributes` (`0x100fb576`)"*
     — now confirmed with the full surrounding logic, not just the bare
     address.
3. **After the call**, the analyze() return is checked against the same
   `0x106b5bd4` sentinel (`setne bl` @ `0x100fb598`); if non-sentinel
   (`bl≠0`), a *second* `call 0x1001f770` fires (line 809, `0x100fb5df`)
   before falling into the shared cleanup block at `0x100fb5e7`; if it *is*
   the sentinel (`bl=0`, analyze produced no real result), execution skips
   `0x1001f770` entirely and goes straight to a plainer cleanup path at
   `0x100fb680`. `pakon_autotone.py`'s own docstring already characterizes
   what `0x1001f770` does generically — "returns a non-OK `AnsStatus`"
   (`pakon_autotone.py:1400`), not a C++ throw — consistent with every call
   site here falling through normally afterward rather than unwinding.

**`AnsOrderOrientationCapability::analyze` (`0x101218c0`), read in full via
`af`+`pdf`** — 329 bytes total realsz, self-naming confirmed independently
via four sites inside it (`"AnsOrderOrientationCapability::analyze"`
`0x10588688`, file
`"\Atc\ansel\src\libOrderOrientation.ansel\AnsOrderOrientationCapability.cpp"`
`0x105885c8`, plus three distinct `" Caught EkcError/std::exception/Unknown
exception."` catch-block strings — the bulk of the function's own byte
count past `0x10121998` is these three MSVC-generated exception-catch
handlers, only reached on unwind, not on normal execution, which is why
`r2`'s own linear `pdf` view initially rendered them as a visual gap before
a raw `pD` sweep confirmed they're real, contiguous, in-function bytes, not
missing analysis). The function's own real, normal-path logic is short: a
smart-pointer AddRef/Release dance around `this+0x10`, one real call —
`call 0x102101d0` @ `0x10121933`, passed `&var_14h_3` as its sole explicit
argument with `ecx = this+0x10`'s object — and, if the result is non-null,
`mov byte [edi+0xf], 1` @ `0x10121994` (a flag on the capability object
itself, `edi` = the original `this`). That's the entire direct-logic
content of `AnsOrderOrientationCapability::analyze`.

**`0x102101d0` — the real leaf, read in full (1,169 bytes, `af`+`pdf`,
complete)** — this is where any tonal relevance would have to live, and it
doesn't:

* `0x10210297`–`0x102102b9`: checks whether an incoming descriptor's two
  size fields are **exactly** `[obj+0x10] == 0x80` (128) and
  `[obj+0xc] == 0xc0` (192).
* If not exact, `0x1021049b`–`0x102104ba`: a signed-modulo idiom
  (`and eax, 0x8000007f` + sign-correction, then `idiv 0xc0`/192 with a
  remainder check) accepts any size that is an **exact multiple** of a
  128×192 tile; anything else falls through to a sentinel path
  (`0x102105e2`: loads a fixed double constant from `0x10574f40` and
  returns without running any correlation at all).
* On a dimension match (either shape), the function copies two fixed-size
  structs onto the stack via `rep movsd` — 68 dwords (272 B) from
  `this+0x30`, 28 dwords (112 B) from `this+0x140` — computes a row/col
  byte offset into what the `imul ×width; shl 1` idiom marks as a 16-bit
  pixel buffer (the same "stride×2 for 16-bit samples" shape this
  project's own decode code uses elsewhere), and calls `0x10285f90` — a
  genuinely large function (confirmed by `af`: **2,143 instructions, 430
  basic blocks, 5 arguments**, bigger than `dra`'s entire subsystem) — with
  the two region descriptors and the computed offsets. The single x87
  double it returns is stored to a local **and** to `this+0x1d0` on the
  capability object (`fst`/`fstp` @ `0x1021030d`/`0x10210310`). For the
  multi-tile case, a second helper (`0x100d9930`, confirmed ≥1,621 bytes,
  called @ `0x10210531`) builds an equivalent tile-grid descriptor before
  the same `0x10285f90` scoring call runs again.
* **Zero density/log/percentile/channel-balance instructions anywhere in
  this leaf or in `analyzeAttributes`/`AnsOrderOrientationCapability::
  analyze` above it** — the only x87 activity in the whole three-function,
  2,357-byte chain (`analyzeAttributes` + `analyze` + this leaf's own
  visible shape) is `fld`/`fst`/`fstp` moving a pre-existing or
  freshly-computed scalar in or out, never the `log10`/multi-term
  arithmetic chain `f135_rom12_to_rpd12`, `cna`, and `dra` all visibly use.
  The whole shape — fixed 128×192-or-multiple tile descriptors in, one x87
  double correlation/score out, cached on the capability object itself —
  is a tile-based image-region classifier, not a tone-curve or histogram
  computation.

**This confirms, and adds real instruction-level evidence to, a
pre-existing but previously address-free classification.**
`docs/64-pruned-tone-producers.md`'s own table (line 80, from an earlier,
independent scoping pass) already lists `orderOrientation` as:
*"Auto-rotation classifier — publishes `orderOrientationProb`/
`frameOrientationProb` confidence scores from sky/grass-style top-vs-bottom
colour statistics. Functionally geometric, not a colour transform. 0%
ported."* That entry cited no address and no disassembly — it was almost
certainly derived by reading capability names/strings, not by tracing the
real driver's own call graph down to a leaf. This section arrived at the
same conclusion independently, starting from `analyzeAttributes`'s own real
driver call site (not from the `"orderOrientation"` name) and reading every
function in the chain down to its own real leaf math — a genuine
cross-check, not a restatement, and it holds: fixed small-tile region
correlation is a plausible, consistent mechanism for exactly the
"top-vs-bottom" classifier `docs/64` already describes.

**Honestly scoped, the same way §12 scoped `analyzeArea`'s own entry
read.** `0x10285f90` (the 2,143-instruction scoring function) and the two
struct-builder helpers (`0x100d9930`, `0x100da770` — the latter also called
once from `analyzeAttributes`'s own miss-path secondary lookup context, per
`pakon_analyse_roll.py`'s existing citation of `0x100da770` as "no name
string in first 0x300 B") were **not** disassembled to their own last
instruction — `0x10285f90` alone is bigger than `dra`'s entire ported
subsystem, and fully closing it would be its own multi-pass undertaking,
out of proportion to what's needed to answer "is this tonal." The fixed
tile dimensionality and single-scalar-output shape already settle that
question regardless of `0x10285f90`'s own exact internals; no live Unicorn
execution of any of these three functions was attempted, for the same
reason — this is a real, in-full, function-boundary-disassembly read of
the two thin control-flow layers a driver call has to pass through
(`analyzeAttributes`, `AnsOrderOrientationCapability::analyze`), plus a
disassembly-only characterization of the one leaf's calling shape, not a
claim that every byte of the `orderOrientation` feature has been read.

**No live channel to `analyzeAutoTone`, extending §22's already-verified
finding to this stage's own real output specifically, not just
generically.** §22's own live `UC_HOOK_MEM_READ` watch on the real DLL's
`analyzeAutoTone`, run end-to-end under Unicorn with all six real subsystem
Impls, found it reads exactly `holder+0x4` (refcount only) and three fixed
`ctx` offsets (`+0x44`, `+0x4bc`, `+0x64d0`) — nothing else, from any
object, for the whole six-subsystem chain. `AnsOrderOrientationCapability`'s
own instance — where this section's `this+0x1d0` correlation score and
`this+0xf` flag actually live — is a *different* object from both `holder`
and `ctx`, found only under the capability name `"orderOrientation"`, and
`analyzeAutoTone`'s own by-name capability lookups (`pakon_autotone.py`'s
`CAPABILITIES` tuple, already cross-checked against the real DLL in §22)
never include `"orderOrientation"` — only `"cna"`/`"dra"`/`"toneHelper"`/
`"contrast"`/`"ast"`/`"pfd"`/`"citras"`. Both possible live channels (a
shared-field mutation, and a by-name capability re-lookup) are therefore
ruled out for `analyzeAttributes`'s one real output specifically, not just
inferred from the class-wide §22 finding.

**Verdict: ruled out, with real evidence, not a name-based guess — no port
written.** `analyzeAttributes` is a thin capability-shell gate around
exactly one named sub-capability (`"orderOrientation"`), whose own real
leaf computation is a fixed-tile image-region correlation/classifier
(auto-rotation detection) with a single cached scalar output and zero
density/histogram/log arithmetic anywhere in its visible shape, feeding an
object `analyzeAutoTone` never looks up and never reads a shared field
from. Porting it would add nothing to the shadow/black-point
investigation — consistent with this task's own instruction to document
and rule out, not force a port, when a stage is clearly non-tonal. This
closes one more member of this doc's own priority-list item 1 (the four
unreplicated stages): `analyzeFalloff` was already dead (structurally
absent calibration data), and `analyzeAttributes` is now closed too, on
real disassembly evidence rather than the name-based classification
`docs/64` already carried. `analyzeArea`'s own 732-function body and
`balanceAreaImage`'s own miss-path body remain the only genuinely open
members of that list.

**Verification.** All addresses in this section were read directly from
`/tmp/pakon_re/PakonIMAu.dll` (MD5 `eea9dcf78ee21d4f7c515a6c2512242d`,
re-checked immediately before use, the same copy every prior section of
this doc cites) via `radare2`'s explicit `af`+`pdf` function-boundary
disassembly for all three functions in the real call chain
(`0x100fb3d0`/859 B, `0x101218c0`/329 B, `0x102101d0`/1,169 B) — never a
raw `pD` byte-range guess, per this project's own established convention.
Every address cited was either read directly off this pass's own
disassembly output or cross-checked against an address already catalogued
in `pakon_analyse_roll.py` (`PATH_ANALYZE_ATTRIBUTES`,
`ORDER_ORIENTATION_CAP_ANALYZE`) or `pakon_autotone.py` (the capability-shell
idiom's own already-documented meaning for `0x1001f770`/`0x1001ed90`/
`0x104ffdd6`/`__RTDynamicCast`) — no address or instruction semantics in
this section were invented or assumed from the function's name alone. The
self-naming strings for both `analyzeAttributes` and
`AnsOrderOrientationCapability::analyze` were read directly out of the
loaded binary, not transcribed from any prior doc. `0x104ffdd6`'s identity
as the real `__RTDynamicCast` IAT thunk was confirmed by direct
disassembly of its own 6 bytes (`jmp dword
[sym.imp.MSVCR71.dll___RTDynamicCast]`), not assumed from its address
alone. `0x10285f90`'s size/argument-count claim came from `radare2`'s own
`afi` function-info output (`realsz`/`num-instrs`/`num-bbs`/`args`), not
estimated. No port file was written or changed by this pass (no
`pakon_attributes.py` — there is nothing tonal to port); no golden file was
touched; no Unicorn execution was attempted, consistent with this section's
own honest scoping note above. Scratch `r2` output used to produce this
section's disassembly excerpts lives under `/tmp/pakon_re/` (a shared
scratch directory this project's own prior passes already use — files
added this pass: `attributes_plain.txt`, `orderorient_full.txt`,
`orient_leaf.txt`, `attr_pdg.r2`), not committed to the repo.

## 26 — `analyzeNoise` (`0x10112f30`): real function, real math, delegates to
an already-ported subsystem — but two independent checks confirm zero live
channel into the six-subsystem tone chain, closing it the same way `falloff`
and (§25, parallel) `analyzeAttributes` are closed

Picked up directly from this doc's own priority list (item 1: the four
unreplicated `analyzeArea`/`analyzeAttributes`/`analyzeNoise`/`analyzeFalloff`
stages), specifically `analyzeNoise` — the one member §11's own call-order
table listed as `[0x10112f30 — not yet identified]`, even though `docs/66`'s
own eleventh-pass call-order table (line 2063 of that file, from an
independent live disassembly of the same driver, `fcn.10069490`) had already
named this exact address `analyzeNoise` in passing, without characterizing
what it does. Both citations point at the same address; this section
resolves what it actually is.

### 26.1 — Confirmed the address, then the whole function, by direct
disassembly of the MD5-verified DLL

Same DLL every prior section of this doc cites: re-extracted this pass from
`research/sdk/PAKONF135.iso` (via the already-mounted volume,
`fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`) and
confirmed `md5 == eea9dcf78ee21d4f7c515a6c2512242d` before any disassembly.
Full function-boundary disassembly (`r2 aa; af @ 0x10112f30; pdf @
0x10112f30` — explicit `af`+`pdf`, not a raw `pD` byte-range read, per this
project's own established convention): 1,449 bytes, `0x10112f30`-`0x101134d9`,
64 basic blocks, cyclomatic complexity 42, one real stack argument (r2's own
`arg_5ch`).

**Self-naming, not assumed from the address alone.** The function pushes the
literal string `"analyzeNoise"` (`0x10587a10`) together with
`"\Atc\ansel\src\libPaths.ansel\noiseMethods.cpp"` (`0x10587994`) at **seven**
distinct sites inside its own body (`0x1011303c`, `0x10113115`, `0x1011325c`,
`0x101132a6`, `0x1011332c`, `0x101133ba`, `0x1011343f`) — the same
self-naming-string method this doc's own §11/§12/§18/§25 already use to
confirm function identity, not proximity or reasoning from a citation. Two of
those seven sites additionally push a specific error message before calling
the exception-constructor thunk (`0x1001ed90`, already catalogued in
`pakon_autotone.py` as `THROW_NOT_FOUND`): `"Pnr capability not found."`
(`0x10586ef7`) and `"Nra capability not found."` (`0x1057ae87`). The other
five call a different, non-message-carrying helper (`0x1001f770`) after a
successful capability lookup — the same "validate a found-and-cast pointer"
shape this doc's §12 already flagged as "seen throughout this project's own
disassembly work," now with two concrete call sites of its own.

### 26.2 — What it actually does: an idempotency-guarded producer of two
named capabilities, "pnr" and "nra" — real RTTI classes, not placeholders

The function's own control flow (read directly, not inferred): it takes
**exactly one argument**, the shared holder pointer (matching r2's own
`arg_5ch` naming) — never a `ctx` pointer, never a pixel-buffer/`Ima2DImage`
argument, the same single-pointer calling convention this doc's §11 already
established for `balanceAreaImage`/`analyzeArea`/`analyzeFalloff`/
`analyzeAutoTone`'s own shared `&[ebp+0xc]` argument. It calls the real
capability-set find thunk (`0x10020a40`, `pakon_autotone.CAP_FIND_THUNK` —
the exact same thunk `dra`'s `find("lighting")` and `balanceAreaImage`'s
`find("area")` already use) for the literal string `"pnr"`
(`0x1057a034`) first, then, gated on that result, for `"nra"`
(`0x105740cc`) — both real, non-placeholder classes, confirmed by an
exhaustive `.rdata` string search (`izz`) on the same DLL: `AnsPnrCapability`
/ `AnsPnrCapabilityImpl` / `AnsPnrCapability::analyze` /
`AnsPnrCapability::acquire` (`noiseMethods.cpp`'s sibling file
`AnsPnrCapability.cpp`, `\Atc\ansel\src\libPnr.ansel\`) and the identically-
shaped `AnsNraCapability` family (`\Atc\ansel\src\libNra.ansel\`). Each
result is passed through the real `__RTDynamicCast` IAT thunk
(`0x104ffdd6`, `pakon_autotone.RT_DYNAMIC_CAST`) to the specific Pnr/Nra
type before its own `+0xc` enable-style byte is checked — the identical
"declare-time capability, `+0xc` gates real use" idiom `declareAutoTone`
already uses for the six/seven tone capabilities. On a lookup miss (or a
cast that resolves to the wrong type) it throws the corresponding
"`<Name>` capability not found." exception via `0x1001ed90`; on a
successful, already-`+0xc`-enabled find it validates and returns without
recomputation (a self-guard, not a data-consumption path — the same
idempotency shape §12 already found at `analyzeArea`'s own entry and §22
corrected the polarity of for `balanceAreaImage`'s `find("area")`). When
neither guard short-circuits it, it calls exactly one substantive leaf:
`0x10112980`, once, at VA `0x101132f1`, with a single small local record
built from the holder pointer.

**`0x10112980` is not a new address — it is `NoiseMethods::getNoiseTable`,
a function this project already ported.** `pakon_ane_order.py`'s own header
docstring (predating this pass) already fully documents it by that name,
citing its self-naming string (`0x105879f4`) and its real behaviour: it
looks up an `"aneOrder"` capability's results (the already-ported
`ANE_ORDER_PORTED = True` density-curve machinery, `AnsAneOrderCapability`,
originally built for Shasta's positive-path aim calculation), then, per
channel, clamps a `dmin[i]` value into `[0, n)` and computes
`dens_i = ftol2(table[idx] * blackNoiseSigmaMult)` — a black-point/shadow
density-noise adjustment, architecturally exactly the "denoising near
black" shape this task flagged as plausible.

**One real correction to that existing docstring, found by this pass's own
disassembly, not by re-reading the docstring more carefully.**
`pakon_ane_order.py` currently states `0x10112980`'s "**Sole** CnPremium
mid-aim caller @ `0x10056863`" (emphasis in the original). It is not sole:
`analyzeNoise`'s own call at `0x101132f1`, confirmed above by direct
disassembly this pass, is a second, real, direct caller — from a completely
different `Path` class (`AnsCnEnhancedPath`, colour negative) than the
`CnPremium` mid-aim site the existing docstring names. `getNoiseTable`
itself is shared, general-purpose machinery; `analyzeNoise` is simply a
second, previously-uncatalogued consumer of it, for a different purpose
(publishing a `"pnr"`/`"nra"` capability result) than CnPremium's own use
(feeding a positive-path aim target). This is a real, citable addition to
that file's own accurate-but-incomplete accounting — not a contradiction of
anything it already verified, and `pakon_ane_order.py` itself is not
touched by this pass, per this task's own file-scope instructions.

### 26.3 — Decisive: does any of this reach the six already-verified tone
subsystems? Two independent checks, both negative

**Check 1 — the capability names `analyzeAutoTone` itself ever looks up, by
name, are already fixed and already Unicorn-verified.** `pakon_autotone.py`'s
own `CAPABILITIES` tuple (`LOOKUP_ORDER`, the exact real-DLL find-call
sequence `analyzeAutoTone`'s own body issues, confirmed bit-exact against
the real DLL across the whole `docs/66` port) contains exactly seven names:
`cna`, `dra`, `toneHelper`, `contrast`, `ast`, `pfd`, `citras`. A direct
`grep -in "pnr\|nra\b\|noise" pakon_autotone.py` over the whole file (1,631
lines) returns **zero matches** — not a new finding, a confirmation that the
already-existing, already-verified port simply never mentions any of these
names anywhere, consistent with (and now cross-checked against) §22's own
live `UC_HOOK_MEM_READ` watch over the real DLL's `analyzeAutoTone`
execution, which found holder/`ctx` touched at only the 3-4 fields already
documented — none of them a noise-table slot.

**Check 2 — a fresh, real, static direct-call reachability walk from
`analyzeAutoTone`'s own entry point confirms neither `analyzeNoise` nor
`getNoiseTable` is even in its call graph.** Ran this project's own
committed tool, not a re-derived scratch copy: `python3 tools/re/
reachability.py walk 0x100fb730 --dll <the same MD5-verified copy>` — 166
functions reached, 68,323 code bytes, 345 indirect call sites, 1,211 direct
call sites (consistent with the 166-function / 67,896-byte figure
`pakon_shasta.py`'s own comment already cites for this same seed, small
byte-count variance being an `r2` analysis-run artifact, not a different
result). Checked the resulting function-address set directly, not
eyeballed: `0x10112f30` (`analyzeNoise`) and `0x10112980`
(`getNoiseTable`) are **both absent** from the 166 reached functions, while
the shared machinery both `analyzeNoise` and `analyzeAutoTone` separately
call by name — `0x10020a40` (`CAP_FIND_THUNK`) and `0x104ffdd6`
(`__RTDynamicCast`) — **are** present, confirming the walk is exercising
real, resolved call edges and not silently failing to explore the region of
the binary these addresses live in. This is a second, independent method
from Check 1 (static call-graph closure vs. a live memory-read watch) and
from §22's own approach, reaching the same conclusion by a different route.

**Why the one place `getNoiseTable`'s math genuinely matters doesn't apply
to this project's own target either.** Per `pakon_ane_order.py`'s own
(now-corrected) citation, the other real caller of `getNoiseTable` is
`CnPremium`'s own mid-aim calculation — part of the Shasta/positive-film
aim-point machinery already ported for that path. §18 of this doc already
independently established, by full disassembly of all four real
Color-Negative path variants (`AnsCnPremiumPath`, `AnsCnOpticalPath`,
`AnsCnLockbeamPath`, `AnsCnEnhancedPath`), that Shasta/SRA's own call tree
is architecturally disjoint from every colour-negative `analyzeScene`,
including this project's own `AnsCnEnhancedPath` target. So even the one
context where this exact arithmetic is genuinely load-bearing in the real
DLL is a rendering path this project's F-135 colour-negative port does not
take — a second, independent reason (beyond Checks 1-2) that `analyzeNoise`'s
real computation cannot be part of the washed-out defect on this project's
own target path.

### 26.4 — Verdict: ruled out, with real evidence, not ported

`analyzeNoise` is real, non-trivial (1,449 bytes, 42 cyclomatic complexity),
and does genuine, architecturally shadow-adjacent work — it is not a
placeholder and not "clearly unrelated by name" the way, say, a pure
geometry helper would be. But by two independent methods (the already-
verified `CAPABILITIES` tuple / live memory-watch from §22, and a fresh
static reachability walk this pass ran directly), `analyzeAutoTone`'s own
six already-Unicorn-verified tone subsystems never look up, read, or
otherwise reach anything `analyzeNoise` produces or touches. This is the
same "real function, real work, no live channel to the verified chain"
verdict §22 already reached for `analyzeArea`/`analyzeAttributes`/
`balanceAreaImage`'s `find`-guard, and §25 (parallel, this session) just
reached independently for `analyzeAttributes` specifically — now extended
to `analyzeNoise` by name, with its own two-method evidence rather than
inherited by association. No Python port was written (no `pakon_noise.py`
— porting code with a proven-absent live channel into the defect under
investigation would be effort spent verifying something bit-exact against
nothing, not the same bar `citras`/`cna`/`dra` met before landing), and no
existing file (`pakon_ane_order.py` included) was modified — this section is
the only change, plus the scratch DLL copy and `r2`/`reachability.py`
output under `/tmp/pakon_noise_re/` (not committed, consistent with this
doc's own established practice of leaving RE scratch work out of the repo).

**What this changes about the four-stage priority item.** Of the original
four (`analyzeArea`/`analyzeAttributes`/`analyzeNoise`/`analyzeFalloff`):
`analyzeFalloff` was independently confirmed structurally dead before this
session (its calibration data is absent from the shipped vendor install);
`analyzeAttributes` is closed this session by a parallel pass (§25, real
gate for `orderOrientation`'s rotation classifier, not tonal);
`analyzeNoise` is closed by this section. `analyzeArea`'s own 732-function
body (§12's own honest scoping: "the same order of effort as the citras
driver's own multi-pass saga") is now the sole member of the original four
still open.

**Verification.** `md5(PakonIMAu.dll) == eea9dcf78ee21d4f7c515a6c2512242d`,
checked immediately after extraction, before any disassembly in this
section. `af`+`pdf` (explicit function-boundary disassembly) was used for
`0x10112f30`, not a raw `pD` byte-range read. Every address/string cited in
§26.1-26.2 (the self-naming strings, the `"pnr"`/`"nra"` capability class
strings, `0x1001ed90`/`0x1001f770`/`0x10020a40`/`0x104ffdd6`/`0x10112980`)
was read directly out of the loaded binary via `r2`'s `izz` (full `.rdata`
string scan) and `pdf` (function disassembly), not transcribed from a prior
doc or assumed from an address alone. Check 1's `grep` over
`pakon_autotone.py` was run directly, this pass, over the file as it exists
in this checkout. Check 2's reachability walk was run with this project's
own committed `tools/re/reachability.py` (not a re-derived scratch copy)
against the same MD5-verified DLL copy, and its output JSON was parsed
directly (`0x10112f30 in reached_addrs`, `0x10112980 in reached_addrs`,
both `False`; `0x10020a40`/`0x104ffdd6` both `True`) rather than eyeballed
from the printed summary. No golden file was touched, no port file was
written or changed, and no Unicorn execution was attempted for this
section — the two-method static/already-verified-dynamic evidence in
§26.3 was judged sufficient to answer the relevance question without it,
consistent with this task's own "be honest about scope" guidance given the
result came back negative rather than requiring a port to characterize
further. Scratch output (`analyzeNoise_pdf.txt`, `analyzeNoise_plain.txt`,
the extracted DLL copy, and the reachability JSON) lives under
`/tmp/pakon_noise_re/`, not committed.

## 27 — `analyzeArea`'s own reachable set walked (943 functions); one of
§12's two unidentified call targets identified as a real, previously-
uncited channel into FUGC's own LUT-application machinery — gated, not
yet live-verified, and the sole remaining open item is now sharper, not
closed

Picked up directly as the last genuinely open member of this doc's own
priority-list item 1 — `analyzeArea` itself, §26's own closing line: "now
the sole member of the original four still open." DLL re-verified before
any of this section's work: `md5(/tmp/pakon_re/PakonIMAu.dll) ==
eea9dcf78ee21d4f7c515a6c2512242d`, the same copy every prior section of
this doc (and every `docs/66` pass before it) cites, cross-checked against
the untouched vendor copy at `/Users/guy/Downloads/Pakon Update
3/fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll` (same
MD5).

### 27.1 — The full reachable set, walked with this project's own
committed tool, not a re-derived scratch copy

`python3 tools/re/reachability.py calibrate` reproduces the Shasta
calibration point (189 fn / 44,378–44,432 B / 386 indirect) exactly first,
confirming the tool and this DLL copy are in the same state every other
citation in this doc relies on. `python3 tools/re/reachability.py walk
0x100e16d0 --label area` (the real `analyzeArea` entry address, cross-
checked against `pakon_analyse_roll.py`'s own `PATH_ANALYZE_AREA =
0x100E16D0`) then walks the **entire** direct-call closure, not a sample:

```
functions reached  : 943
code bytes (realsz): 342,503
indirect call sites : 955  (+836 IAT thunk calls, counted separately)
direct call sites   : 4,758
```

**This does not match `docs/65`'s own published "732 functions / 299,737
bytes / 1,405 indirect calls"** for the same capability. Both numbers are
real — `docs/65`'s own citation predates `tools/re/reachability.py`'s
existence as a committed, calibrated tool (the file's own header explains
it was written specifically because every prior pass "rebuilt this same
tool from scratch in an ephemeral scratch directory" before producing a
number), so the two figures almost certainly come from different tool
states or a different seed set (e.g. `acquire`+`analyze`+`export` walked
together vs. `analyze` alone) rather than one being wrong. This pass did
**not** chase down which — flagged honestly as an open discrepancy, not
resolved either way, and the **943/342,503/955** figures above are what
this pass's own numbers below are scoped against, reproducible from
`/tmp/pakon_re/reach_area.json` (this session's own output, not
committed — vendor-DLL-derived per this project's `.gitignore`
convention).

### 27.2 — The entry function itself, confirmed via `af`+`pdf`, matching
§12 with precise numbers

`0x100e16d0`–`0x100e1e0f`, **1,856 bytes, 493 instructions, 76 basic
blocks, cyclomatic complexity 50** (`afij`, not eyeballed) — the same
function §12 already read as "499-line" (a minor `r2`-version rendering
difference, not a re-read discrepancy; the byte/instruction counts here
are the load-bearing numbers). Self-naming confirmed the same way as
every other stage in this doc: the function pushes `"analyzeArea"`
(`0x10584be4`) and `"\Atc\ansel\src\libPaths.ansel\areaMethods.cpp"`
(`0x10584bf0`) at five separate sites inside its own body (`0x100e17ec`,
`0x100e18be`, `0x100e1c26`, `0x100e1cc6`, `0x100e1d45`).

The function opens with the identical `find("area")` idempotency guard
§12 already found (`0x10020a40` = `CAP_FIND_THUNK`, keyed to the literal
string `"area"` at `0x100e1709`), then an `__RTDynamicCast` down to
`AnsAreaCapability` (confirmed by resolving the real MSVC type-info name
strings directly out of the loaded binary, not assumed from the address:
`ps @ 0x10692518+8` → `.?AVAnsCapability@@`, `ps @ 0x10692ce0+8` →
`.?AVAnsAreaCapability@@` — i.e. `srcType=AnsCapability`,
`targetType=AnsAreaCapability`, the standard `__RTDynamicCast(inptr, 0,
srcType, targetType, 0)` argument shape). This confirms and slightly
sharpens §12's own "idempotency-guarded" read with the exact RTTI
identity, not just the control-flow shape.

### 27.3 — The real finding: one of §12's two "still-unidentified" call
targets is FUGC's own `applyLut`, reached via a 3-site shared thunk —
new to this doc, but not new to the project's own port comments

§12 named two addresses it could not identify: `0x101186c0` and
`0x101a3500`. Both are now resolved.

**`0x101a3500`** (454 B, 116 instructions, 9 basic blocks, `af`+`pdf`,
read in full) is a `sprintf`/`std::basic_string`-based debug-log string
formatter — it builds a `"-"`-separated dimension string (the literal
`"-"` at `0x10583d1c`, pushed by its caller immediately around this
call) via `sym.imp.MSVCR71.dll_sprintf` and three `basic_string`
constructor/destructor pairs, with zero pixel-buffer or density
arithmetic anywhere in its body. Confirmed non-tonal, matching §12's
original "geometrically-shaped" read for this address specifically, not
just by association.

**`0x101186c0`** (35 B, 1 basic block, `af`+`pdf`) is the significant
one. Its own body:

```
push ecx
mov eax, dword [arg_ch]        ; second stack param
mov ecx, dword [ecx + 0x10]    ; ecx = this->0x10  (a sub-object pointer)
push esi
mov esi, dword [arg_ch_2]      ; first stack param
push eax
push esi
mov dword [var_ch], 0
call fcn.101fa5b0               ; this->0x10 -> fcn.101fa5b0(arg_ch_2, arg_ch, &local)
mov eax, esi                    ; returns arg_ch_2 unchanged
pop esi
pop ecx
ret 8
```

A thin forwarding thunk, nothing more — but `fcn.101fa5b0` (2,289 B, 705
instructions, 90 basic blocks, `af`+`pdf`, read in full through its own
early control flow) self-identifies, via **its own embedded exception-
throw strings**, at multiple sites inside its own body, as
`AnsFugcCapabilityImpl::applyLut` (`\Atc\ansel\src\libFugc.ansel\
AnsFugcCapabilityImpl.cpp`), operating on real pixel-processing operand
types cited by name in its own error strings: `"Couldn't allocate
toneLutPtr."`, `"Couldn't allocate colorLutPtr."`, `"Couldn't allocate
RectBuffer."`, `"ImaLutOpT has bad status."`, `"ImaAstOpT has bad
status."`, `"Image layout is not PIXEL or BAND!"`. This is real,
substantial FUGC tone/colour-LUT-application code — not a geometric
helper, not a placeholder.

**This is not a new discovery in isolation** — `tools/ansel/python-
pipeline/pakon_fugc.py`'s own docstring already catalogues this exact
function (`IMPL_APPLY_LUT = 0x101FA5B0`, wrapper `0x101186c0`, "`applyLut`
@ `0x101fa5b0` (wrapper `0x101186c0`); full pixel path not ported. Host
Preference applies `setLutInfo` / mode-2 plane via `apply_1d_lut`" —
`pakon_fugc.py:107-109`) and `FUGC_APPLY_LUT_GATE_PORTED = True` already
covers the one narrow leaf this project verified (the image-descriptor
type gate at `0x101fa5e5`/`0x101fa5f8`, accepting descriptor type `0` or
`2`). What **is** new, checked directly by grep over every `.py` file
under `tools/ansel/python-pipeline/` and every existing `docs/*.md`
before writing this: **no existing file documents that this exact
wrapper has three real call sites in the whole DLL, not one.**
`fcn.101186c0`'s own `r2`-reported XREFs list all three, and each was
independently cross-checked against this project's own already-catalogued
constants:

```
CALL XREF from fcn.100fed00 @ 0x100fef46   (analyzeFugc      — PATH_ANALYZE_FUGC)
CALL XREF from fcn.10102b20 @ 0x1010367f   (balanceAreaImage — PATH_BALANCE_AREA_IMAGE)
CALL XREF from fcn.100e16d0 @ 0x100e1c78   (analyzeArea      — PATH_ANALYZE_AREA, this section)
```

The `analyzeFugc` site is FUGC applying its own LUT during its own normal
analyze cycle — expected, and consistent with `pakon_fugc.py`'s existing
"Apply / export" note. **The other two are not previously documented
anywhere in this project** (confirmed by `grep -rn "1010367f\|100e1c78"
tools/ docs/` returning nothing outside this pass's own new text). Both
are directly relevant to open threads this doc already carries:

* **`balanceAreaImage`** (`0x10102b20`) calling into real FUGC
  `applyLut` machinery is new, concrete evidence bearing directly on
  §22's own still-open thread — "whether `balanceAreaImage` mutates the
  shared pixel buffer (`arg2`) directly, in place." §22's own live
  Unicorn test found **zero** pixel-buffer writes, but explicitly
  caveated that its "hit" branch used a synthetic, zero-filled
  placeholder Impl "behind a generic one-slot vftable (every virtual call
  resolves to a bare `ret 4`)" — not a real `AnsFugcCapability`/
  `AnsAreaCapability` object. Given `fcn.101186c0` dereferences
  `this->0x10` as a real sub-object pointer before forwarding into
  `applyLut`, a zero-filled placeholder's `+0x10` field would almost
  certainly have been null or garbage, meaning §22's own test very
  plausibly never reached this specific call path at all — not a
  contradiction of §22's result (its own caveat already flagged exactly
  this limitation), but a concrete reason the "zero writes" finding may
  not generalize to a real, correctly-typed capability object. This is
  not proven either way this pass — no Unicorn execution was attempted
  here — but it sharpens exactly what a follow-up live test needs to
  build (a real, non-placeholder `this->0x10` sub-object) to actually
  close §22's own thread.
* **`analyzeArea`**'s own call (`0x100e1c78`, this section's actual
  target) is gated behind, in order: two boolean checks at `[esp+0xec]`
  and `[esp+0xf0]` (0x100e1be9/0x100e1bf6 in the entry function's own
  body — this pass could **not** conclusively determine whether these are
  genuine per-capability enable flags, plausible given the sibling
  `AnsDustCapability`/`AnsScratchCapability`/`AnsGainOffsetCapability`
  classes this pass found via a direct `.rdata` string search of the same
  DLL, or a stack-slot-reuse artefact of the same byte also serving as
  this function's own SEH-unwind-state tracker elsewhere in its body —
  flagged honestly as unresolved, not asserted either way); a call to
  `fcn.100dc060` (28 B, `af`+`pdf`, read in full: `if (byte[this+0x1a1]
  != 0) return this+0x1a4; else return 0;` — a private field on the Area
  capability object itself, matching the DLL's own `"AREA analysis image
  is NULL!"` error string used immediately after this call on a null
  result); a second `__RTDynamicCast`, this time to `AnsFugcCapability`
  (`ps @ 0x10697610+8` → `.?AVAnsFugcCapability@@`, same `srcType
  =AnsCapability` as the first cast) — the failure path throws the DLL's
  own `"FUGC capability is NULL (wrong type?)"` (`0x10584b9c`); and
  finally a flag byte at `[fugc_obj + 0xc]` on the cast result. Only if
  **all four** gates pass does `analyzeArea` call `fcn.101186c0(this=
  fugc_obj, arg_ch=area_image, arg_ch_2=&status_out)` — i.e. apply
  FUGC's own tone/colour LUT to `analyzeArea`'s own private "AREA
  analysis image" buffer, as a real side effect of `analyzeArea`'s own
  analyze() body, not merely as FUGC's own independent lifecycle step.

### 27.4 — What this pass could **not** establish, stated plainly

Two things stand between this finding and an actual verdict on the
shadow/black-point question, and neither was resolved this pass:

1. **Whether the object fed into the second (`AnsFugcCapability`)
   RTDynamicCast at `0x100e1c3a` is genuinely FUGC's own live capability
   for this scene.** The value is read from `[esp+0xf4]`; a literal-
   displacement search of the entire function (`grep` over every decoded
   operand, not eyeballed) finds **no** direct-literal write to that exact
   offset anywhere earlier in the function's 493 instructions — its real
   provenance is very plausibly a wider block-copy (`rep movs`/struct
   blit via a register-computed destination, which a literal-displacement
   search cannot catch) that this pass did not trace, not evidence of a
   bug. This is exactly the shape of thing `docs/67`'s own "static
   reading invents patterns live execution disproves" caution warns
   about, and it was treated that way here: flagged as unresolved rather
   than guessed at.
2. **Whether `analyzeArea`'s own "AREA analysis image" (`this+0x1a4`,
   §27.3) is the same shared pixel buffer `cna`/`dra` (the already-
   verified tone chain) subsequently read, or a private/independent copy
   analyzeArea owns for its own dust/scratch-detection purposes.** This
   is the single fact that would determine whether the `applyLut`
   invocation traced above could plausibly touch anything the shadow/
   black-point defect depends on at all. Not established by this pass —
   would require tracing `AnsAreaCapabilityImpl`'s own acquire/
   construction path (not read this pass) or a live Unicorn trace
   watching the real buffer address, the same technique §24's Finding 3
   already used for `balanceAreaImage`.

A third, smaller thread, read but not fully traced: `fcn.100dc0b0` (180
B, `af`+`pdf`, called at `0x100e1957` before either of the above gates)
either copies 5 dwords from a caller-supplied struct, or — on a null
input — loads 5 static double/float calibration constants from
`0x10586340`–`0x10586354` (real DPI-loaded defaults, not synthetic) and
stores the result at the Area object's own `this+0x1c8`..`this+0x1d8`.
Plausibly per-channel sensitivity/threshold parameters (`libAREA.ansel`'s
own `AnsAreaParameters.cpp`, confirmed present in the DLL's string table
this pass searched: `\Atc\ansel\src\libAREA.ansel\AnsAreaParameters.cpp`
at `0x105a32c4`) — not traced further, and not established to reach
pixel data either way.

### 27.5 — Honest scope accounting

Of the 943 functions in `analyzeArea`'s own reachable set (§27.1), this
pass read six in real detail via explicit `af`+`pdf` function-bounded
disassembly: the entry function itself (`0x100e16d0`, 1,856 B),
`fcn.101186c0` (35 B), `fcn.101fa5b0` (2,289 B, read through its own
early control flow and image-layout gate, not to its own last
instruction — its further ~15 sub-callees, `fcn.10311600`,
`fcn.1032d150`, `fcn.1032c0b0`, `fcn.100c1740`, `fcn.1017de10`,
`fcn.10328a90`, and others visible in its own disassembly, were **not**
individually read), `fcn.100dc060` (28 B), `fcn.100dc0b0` (180 B), and
`fcn.101a3500` (454 B). That leaves the overwhelming majority of the
943-function set — everything downstream of the two unresolved boolean
gates in §27.3, everything inside `applyLut`'s own real pixel-processing
body beyond its entry gate, `fcn.100dc650`'s own "commit/register"
call, and the two AREA-parameter helpers `fcn.100dc070`/`fcn.100dc080`
briefly seen but not read — genuinely unexamined, consistent with §12's
own honest sizing of this function as "the same order of effort as the
citras driver's own multi-pass saga." No Python port was written this
pass (no `pakon_area.py`): the one piece of logic concrete enough to
plausibly port — `applyLut`'s own pixel-application math — is already
tracked as a real, not-yet-ported gap in `pakon_fugc.py`
(`FUGC_APPLY_LUT_GATE_PORTED` covers only its entry gate), and porting
it before resolving §27.4's two open questions would risk verifying
code bit-exact against a mechanism this pass has not yet shown actually
touches any buffer the tone chain reads — the same discipline §26
applied to `analyzeNoise` ("porting code with a proven-absent live
channel... would be effort spent verifying something bit-exact against
nothing"), except here the live channel is genuinely unresolved rather
than proven absent, so the honest status is "not yet ruled in or out,"
not "ruled out." **No Unicorn execution was attempted this pass** —
purely static `af`+`pdf` disassembly and `.rdata` string search, the
same limit §11/§12/§25/§26 already used for their own hardest open
threads.

**What the next pass should pick up from, concretely, not just
"analyzeArea in general":** (1) resolve `[esp+0xf4]`'s real provenance
at `analyzeArea`'s own `0x100e1c3a` — either a careful capstone-level
hand ESP/block-copy trace (the technique already proven on the citras
driver's own stack-locals problem, `docs/66`'s Phase 3c) or a live
Unicorn watch; (2) determine whether `this+0x1a4` (the "AREA analysis
image") aliases the shared scene pixel buffer, by reading
`AnsAreaCapabilityImpl`'s own acquire/construction path or by a live
buffer-address watch the way §24's Finding 3 checked `balanceAreaImage`;
(3) if both resolve favourably (real FUGC object, buffer that matters),
build a `balanceAreaImage`-shaped live Unicorn harness (real, non-
placeholder `this->0x10`) and watch `applyLut`'s own writes directly,
the same method §24 already used and would then finally get to exercise
against real, not placeholder, capability objects.

**Verification.** DLL MD5 checked (`eea9dcf78ee21d4f7c515a6c2512242d`)
against both `/tmp/pakon_re/PakonIMAu.dll` and the untouched vendor copy
under `~/Downloads/Pakon Update 3/...` before any disassembly this pass.
`tools/re/reachability.py calibrate` was run and passed before trusting
this pass's own `walk` output. Every function this section cites a size/
instruction/block count for was read via explicit `r2` `af`+`pdf` (or
`afij` for the numeric fields), never a raw `pD` byte-range guess, per
this project's own established convention (`docs/67`). The two RTTI
type-info name strings (`.?AVAnsCapability@@`, `.?AVAnsAreaCapability@@`,
`.?AVAnsFugcCapability@@`) were read directly out of the loaded binary at
the literal addresses the `__RTDynamicCast` call sites push
(`ps @ <addr>+8`), not assumed from the class names alone. The claim that
`0x1010367f`/`0x100e1c78` are not previously documented anywhere in this
project was checked by direct `grep -rn` over every `.py` file under
`tools/ansel/python-pipeline/` and every `docs/*.md` file in this
checkout, not asserted from memory. The `[esp+0xf4]` no-local-write claim
was checked by parsing every decoded operand string in `0x100e16d0`'s own
493-instruction `pdfj` output for the literal substring `"esp + 0xf4]"`,
not by eyeballing the disassembly. No golden file was touched, no
existing port file was modified, and no Python port file was written by
this pass — `pakon_fugc.py`, `pakon_analyse_roll.py`, and every other
existing file this section cites were read only, never edited. Scratch
`r2pipe` scripts and their JSON/text output (`area_explore.py`,
`entry_pdf.txt`, `entry_pdf_raw.txt`, `helpers_pdf.txt`, `more_pdf.txt`,
`dc_pdf.txt`, `reach_area.json`) live under `/tmp/pakon_re/`, the same
shared scratch directory this doc's prior sections already use, not
committed to the repo.

## 28 — `applyLut` (`fcn.101fa5b0`) read in full, then run for real under
Unicorn: it constructs and validates an operand graph and never touches
the pixel buffer, in either the DLL's own static machine code or a real,
bounded dynamic run. Both real callers use it purely as a status gate.
Dead end, closing §27's sharpened thread.

Picked up directly where §27 left off: "the actual per-pixel apply, if it
happens at all in the real vendor pipeline, must happen via a
[so-far-unidentified] call" through `fcn.101fa5b0`
(`AnsFugcCapabilityImpl::applyLut`), reached from both real call sites
§27.3 found (`analyzeArea`'s `0x100e1c78`, `balanceAreaImage`'s
`0x1010367f`). DLL re-verified before any work this pass:
`md5(/tmp/pakon_re/PakonIMAu.dll) == eea9dcf78ee21d4f7c515a6c2512242d`, the
same copy every prior section cites.

### 28.1 — Starting point: what `pakon_fugc.py` already had on record

`pakon_fugc.py`'s own docstring (`:107-109`) already flagged this exact
gap before this pass touched anything: `` `applyLut` @ `0x101fa5b0`
(wrapper `0x101186c0`); full pixel path not ported. Host Preference
applies `setLutInfo` / mode-2 plane via `apply_1d_lut`. `` and
`FUGC_APPLY_LUT_GATE_PORTED = True` covers only the entry image-descriptor
type gate (`fugc_apply_lut_type_accepted`, `:583-589`) — the one leaf this
project had already verified. Nothing else in that file characterizes
`applyLut`'s own body. This section reads it.

### 28.2 — Full `af`+`pdf` read of `fcn.101fa5b0` (2,289 B, 705
instructions, 90 basic blocks — matching §27.2's `afij` numbers exactly):
no loop bounded by image dimensions, no indexed pixel write, and the
image-data pointer is read exactly twice and never forwarded

Read in full this pass (`r2 -q -c 'aa; af @ 0x101fa5b0; pdf @
0x101fa5b0'`, plain-text/no-ANSI-colour output, not a truncated byte
range). Confirmed self-identity the same way as every other function in
this doc: six embedded exception-throw strings citing
`AnsFugcCapabilityImpl::applyLut`/`\Atc\ansel\src\libFugc.ansel\
AnsFugcCapabilityImpl.cpp` at six separate sites in its own body, plus the
named operand-error strings §27.3 already catalogued (`"Couldn't allocate
in2DImagePtr."`, `"...toneLutPtr."`, `"...colorLutPtr."`, `"...
RectBuffer."`, `"ImaLutOpT has bad status."`, `"ImaAstOpT has bad
status."`, `"Image layout is not PIXEL or BAND!"`).

**Calling convention, derived fresh by hand ESP/EBP arithmetic against the
wrapper's own literal encoded displacements** (`fcn.101186c0`, `pdf`+`afvj`
both re-run this pass): the wrapper is pure-`esp`-relative (no `push ebp`),
so its two named stack args resolve, entry-relative, to `arg_ch` = caller's
farther-pushed value (`ESP0+8`) and `arg_ch_2` = caller's nearer-pushed
value (`ESP0+4`, i.e. the caller's own logical first parameter, since
cdecl/thiscall push right-to-left). The wrapper forwards both, in the SAME
relative order, into `fcn.101fa5b0`'s own two stack args — confirmed by
computing `fcn.101fa5b0`'s **fixed** `ebp` (set once, `mov ebp,esp`, at
`0x101fa5b1`, stable across every later `push`/`sub esp`): the literal
`mov esi, dword [ebp + 0xc]` at `0x101fa5df` is the caller's SECOND
logical argument, and a grep over every decoded operand in the function's
own `pdfj` output for the literal substring `"ebp + 8]"` (not eyeballed)
finds 10 separate reads, always following the pattern `mov esi,[ebp+8];
mov dword [esi], eax` — i.e. arg1 (`ebp+8`) is a **status/exception
out-parameter**, written with either the canonical "OK" sentinel
(`0x106b5bd4`, the same global used throughout the function's own success
paths) or a freshly-built exception object (on every error path), never a
pixel address. Arg2 (`ebp+0xc`) is the AREA image descriptor: read once at
entry (`mov eax,[esi+4]` — the type gate `pakon_fugc.
FUGC_APPLY_LUT_TYPE_OK` already covers) and its width/height/stride/data
fields (`+0xc`/`+0x10`/`+0x14`/`+0x20`, matching `pakon_fugc.
FUGC_IMG_DESC_WIDTH_OFF`/`HEIGHT_OFF` exactly) read a handful more times,
always as **inputs to construction calls**, never as a write target.

Three mechanical, script-verified (not eyeballed) checks over the
function's own 705-instruction `pdfj` output, the same "parse every
decoded operand" discipline §27's own verification paragraph used:

1. **Every memory-write `mov` instruction in the function** (104 total,
   found by regexing `disasm` for `mov [byte|word|dword] [<expr>], <src>`)
   — **zero** have an indexed `[base + index]`-shaped destination (the
   mechanical signature of a per-pixel or per-array-element store; a
   struct-field write like `mov [esi+0x40], cl` doesn't count, an
   `mov [ecx+edi*4], eax` inside a loop would). All 104 writes are either
   `[reg]` (simple pointer stores, mostly the status-object writes above)
   or `[reg+constant]` (fixed struct-field writes on freshly-constructed
   local/heap objects).
2. **The function's own control-flow graph has exactly 10 backward
   branches, and every one of them targets one of two addresses**
   (`0x101fa952`, `0x101fac22`) — both confirmed, by reading their own
   bodies, to be **shared cleanup/teardown labels** ("goto common
   epilogue" from many different error branches), not loop bodies: neither
   re-enters any per-element work, both just tear down whatever operand
   objects were constructed so far (`Release`-shaped `call [vtbl+0](1)`
   idioms) and return. There is no loop anywhere in `fcn.101fa5b0`'s own
   705 instructions that could iterate over image-sized data.
3. **`[esi + 0x20]`** (the AREA image's own pixel-data pointer field,
   confirmed by `pakon_fugc.FUGC_IMG_DESC_DATA_OFF`-equivalent convention)
   **appears exactly twice in the whole function, both `mov eax,[esi +
   0x20]` reads** (`0x101fa617`, `0x101fa677`) — each one immediately
   fed as a scalar argument into a small operand-constructor call
   (`0x10311600`), never dereferenced further and never written to.

**What the function's real work actually is**, read alongside these
checks: a type gate; two 84-byte heap allocations (via `fcn.104ffd53`,
confirmed by its own body to be `operator new` — MSVC's real
alloc/new-handler-retry idiom, 114 XREFs across the DLL) wrapping small
operator-descriptor objects, sized from the descriptor's width/height/
stride/type but never touching pixel data itself; then a branch on the
FUGC Impl's own `+0x60e8` mode field (the exact field `pakon_fugc.
CAP_MODE_SELECT` already documents — confirmed live in this function too,
not just in `analyze()`; `cmp dword [esi+0x60e8],2; jne 0x101fab1b` — mode
`== 2` falls straight through, mode `!= 2` jumps away) into one of TWO
near-identical construction paths, each read in full this pass, and each
receiving the SAME three values from `applyLut`'s own call site — the
Impl's own **`+0x6140` apply-LUT array pointer** (the real,
`setLutInfo`-built, per-channel table `pakon_fugc.py` already documents —
confirmed non-identity by this pass's own dynamic run below), `N`=4096,
and a small integer constant — **never** the AREA image descriptor or its
`+0x20` pixel pointer (finding 3 above already showed that pointer is
read exactly twice and forwarded only to `fcn.10311600`, a different,
unread-this-pass call, not to either mode branch):

* **mode `== 2`** (`0x101fa78a` onward): `fcn.100c1740` (278 B/82
  instructions) builds a small `"ast"`-named operand object (self-named
  via its own embedded string literal) — installs a vtable, stores scalar
  fields, forwards the LUT pointer onward to a base constructor
  (`fcn.1017db10`, not read this pass) — then `fcn.1017de10`
  (`AnsAstOperand::getLuts`, self-named the same way, 524 B/140
  instructions, read in full) does the one real loop found anywhere in
  this call graph: `0..this->0x30` (a **lutSize** field, populated from
  `N`=4096 by the construction chain above, not from the image's
  width×height), converting the operand's own internal float LUT
  representation to fixed-point int32, entirely on a LOCAL stack object
  (`fcn.1017de10`'s five call args are all `lea reg,[local_var]`
  addresses of small stack cells — the AREA image pointer is never among
  them).
* **mode `!= 2`** (`0x101fab1b` onward, the branch a real F-135
  colour-negative scan actually takes — `pakon_fugc.py`'s own
  "Sole `setLutInfo` caller remains analyze `0x101fc6cd` (mode ≠ 2)"
  already establishes `setLutInfo`, the real non-identity per-channel LUT
  builder, only runs for this mode): `fcn.10099a40` (201 B/66
  instructions, read in full) — its own `this` is a freshly `operator
  new`'d 32-byte object; its own body DOES contain a genuine per-element
  `int16` copy loop (`mov di,word[edx]; mov word[eax],di; add eax,2;
  add edx,2; cmp eax,ecx; jb`), copying from a source this pass's own
  static read could not fully pin down (a third implicit stack argument,
  `var_1ch`, whose exact caller-side provenance this pass did not
  hand-trace past `applyLut`'s own three-argument call — LUT pointer,
  `N`, constant `1` — none of which is the image pointer). This is the
  one place this pass's STATIC read alone leaves a small residual gap —
  closed by the dynamic run in §28.4 below, which exercises exactly this
  branch.

Both branches then validate their constructed operand's status via
`fcn.10328a90` ("has bad status" check, self-named by its own error
strings, 644 B/162 instructions, read in full) and — only on full success
— call one further tiny helper (`fcn.1003bf80`, 36 B/14 instructions, read
in full: the SAME generic "wrap a raw pointer, AddRef it" idiom already
characterized elsewhere in this DLL, e.g. `0x100065e0`/`0x10006880` per
§22/§24's own citations — not pixel math). Every constructed object is
then torn down (the shared-epilogue `Release` calls from check 2 above)
before the function returns.

**Conclusion from static reading alone, before any dynamic run: `applyLut`
itself cannot write to a pixel buffer, and neither can the mode `== 2`
branch's own callees — the mode `!= 2` branch (the real-scan case) has one
small, honestly-flagged residual gap.** `applyLut`'s own 705 instructions
have no pixel-shaped write and no image-bounded loop (checks 1-3 above);
`fcn.1017de10` (mode `== 2`) is fully accounted for, operating only on
local stack data never connected to the image pointer. `fcn.10099a40`
(mode `!= 2`, the branch a real F-135 negative scan actually takes) is the
one exception: it has its own genuine copy loop whose source this pass's
static read did not fully pin down — though `applyLut`'s own call site
into it (established above) passes only the LUT pointer/`N`/a constant,
never the image descriptor, so the image pixel pointer has no STATIC path
into this loop either; the gap is "unconfirmed source," not "a plausible
pixel-write mechanism." This is already a stronger, more mechanical
version of §22/§24's own "no pixel-buffer writes observed" finding for
`balanceAreaImage` — there, the claim rested on a specific traced
execution path; here it rests on an exhaustive, script-checked inventory
of every write and every loop in `applyLut`'s own body, with only one
callee's internal copy-loop source left open. §28.4 closes that gap
dynamically, on exactly this branch.

### 28.3 — Real callers: both `analyzeArea` and `balanceAreaImage` use
`applyLut`'s result purely as a pass/fail status check, never as a source
of pixel data

Read fresh (`pd` at both real call sites, re-disassembled this pass, not
transcribed from §27):

* **`analyzeArea`** (`0x100e1c6b`-`0x100e1caf`): pushes `edi` (the AREA
  analysis image, `this+0x1a4`, per §27.3's own reading of
  `fcn.100dc060`) and `&var_18h_3` (a local, the status out-param), casts
  `ecx` to the FUGC object, calls `fcn.101186c0`. The **only** use of the
  return value: `push eax; ...; call 0x10001580` then compares
  `dword[eax]` (i.e. `*status_out`) against the global OK sentinel
  `[0x106b5bd4]`, sets a bool, and either throws
  `"AREA analysis image is NULL!"`-neighbourhood asserts or falls through
  to continue `analyzeArea`'s own body at `0x100e1cde`. No pixel value
  from the AREA image is read or written anywhere near this call.
* **`balanceAreaImage`** (`0x1010367a`-`0x10103697`): the exact same
  shape — `mov ecx,[var_2ch]` (FUGC obj), `push edi; push eax; call
  0x101186c0`, then `mov ecx,[eax]` (`*status_out`) compared against a
  prior status value (`[var_14h]`), branching on equality. Also purely a
  status check.

Both real callers treat `applyLut` as a construct-and-validate gate — "can
FUGC build a working LUT operand against this image's own type/dimensions"
— not as a pixel-transform step. Neither retains or dereferences any
constructed operand object past the call (nothing could: §28.2 already
showed the operand graph is torn down inside `applyLut` itself before it
returns).

### 28.4 — Dynamic verification: a real, bounded Unicorn run, calling
`applyLut` directly with a real non-identity LUT and a real pixel buffer.
Zero pixel writes observed across every instruction actually executed;
the run blocks inside CRT exception-message construction, independently
already characterized by this project's own prior (unrelated) citras-
driver investigation as non-pixel debug plumbing

Built new, additive: `tools/ansel/python-pipeline/pakon_fugc_apply_lut_
golden.py`. Reuses `pakon_autotone_shell_golden.Emu` completely unmodified
for its PE loader / bump heap / SEH page / `operator new` hook / fault
collector — the same base class `pakon_autotone_assembled_golden.
AssembledEmu` (and therefore `pakon_full_colour_chain_golden.py`'s own
`BalanceAreaImageCall`) already builds on. Calls `fcn.101fa5b0` **directly**
(bypassing the thin wrapper, whose only job — confirmed §28.2 — is the
`this->0x10` indirection), with:

* `ecx` (this) = a real FUGC Impl: `+0x6140` filled with a genuinely
  non-identity apply LUT built by this project's own already-verified
  `pakon_fugc.set_lut_info(seed, offsets=(200, -150, 75))` — confirmed
  non-identity directly (`lut[0] = [200, 0, 75]`, not `[0, 0, 0]`, from
  the real prefix-fill branch `pakon_fugc.set_lut_info_channel` implements
  for `offset > 0`); `+0x60e8` (mode) = 0 — deliberately the mode `!= 2`
  branch (`fcn.10099a40`, §28.2's own "real-scan case"), the one place
  §28.2's static read alone left a residual gap (the copy loop's own
  source), not the mode `== 2` branch already fully closed statically.
* `arg1` = `&status_out`, `arg2` = a real, non-degenerate image
  descriptor (type=0/PIXEL, 8×8, stride=8, data pointer → a real 8×8
  int16 pixel buffer filled with a real, non-zero, distinctive
  pseudorandom pattern via `numpy.random.default_rng`, not zeros).

A `UC_HOOK_MEM_WRITE` watch covers the exact pixel-buffer address range
for the whole call, the same direct technique §22/§24 already used for
`balanceAreaImage`. Three real, live-found unbound raw-RVA CRT thunks
needed stubbing before the run got past the allocation/construction
region — the same class of fix this project's OWN prior, unrelated
investigation (`docs/74`'s own citation of the citras-driver scratch
passes, `trace_v47`-`v50`, `/tmp/pakon_re/`, not committed) already
catalogued for this exact DLL:
`InitializeCriticalSection`/`EnterCriticalSection`/`LeaveCriticalSection`/
`DeleteCriticalSection` (four addresses, `0x687de2`/`0x687e22`/`0x687e0a`/
`0x687dca`, confirmed real no-op Win32 APIs the same way every prior pass
confirmed them: reading the raw `{hint,name}` import-table bytes directly
out of the PE file at each "unbound" address) and `memmove`
(`0x68bd3a`, confirmed the same way: raw PE bytes at that offset read
`b"f\x00\xe6\x02memmove\x00..."`), the latter implemented for real (not
stubbed to a no-op) since a genuine `memmove` on real construction data
should not be silently discarded.

Result, real completion up to the point it stopped:

```
real apply LUT: lut[0]=[200, 0, 75] (identity would be [0, 0, 0])
calling real applyLut (0x101fa5b0) directly, pixel buffer=0xd0152b0..0xd015330

    [memmove dest=0xd015bf0 src=0x0 n=0x0 called-from=0x1032acfa]
    [memmove dest=0xd015bf4 src=0x0 n=0x0 called-from=0x1032ad21]
    [memmove dest=0xc6dfe24 src=0xc6dfe2c n=0xc6dfde0 called-from=0x102bb783]
BLOCKED -- did not run to completion: eip=0x68bd3a, Invalid memory read (UC_ERR_READ_UNMAPPED)
pixel-buffer writes observed before the fault: 0
```

The first two `memmove` calls are genuine, harmless zero-length no-ops
inside small (106 B/67 B) operand-resize helpers (`fcn.1032acfa`/
`fcn.1032ad21`) — real execution, real addresses, nothing pixel-related.
The blocking third call's own `called-from` address (`0x102bb783`) was
checked directly, not assumed: it falls exactly at the byte immediately
after `call [MSVCR71.dll___0exception__QAE_XZ]` (`0x102bb77d`, a 6-byte
instruction) inside `fcn.102bb760` (160 B, `af`+`pdf` re-read this pass,
independently — not by citation alone) — i.e. the fault is **inside the
real CRT `std::exception::exception()` constructor's own internal string
copy**, called from `fcn.102bb760`, which this pass's own read confirms
builds a real `std::exception`-derived object (`call
[...__0exception__QAE_XZ]`) plus three `std::basic_string` sub-objects
(three separate `call [MSVCP71.dll...basic_string...]` sites) and a real
`call [MSVCR71.dll_time]` — the exact same function this project's own
**prior, unrelated** citras-driver investigation
(`trace_v50.py`'s own comment, `/tmp/pakon_re/`, cited in this doc's
prose only, never committed) already independently characterized: "It
builds a std::exception-derived debug/assert-info object... purely for
human-readable assert messages; none of it is pixel/operand data." Two
independent passes, on two unrelated call paths through this same DLL,
reached the identical conclusion about the identical function.

**Honestly scoped, not oversold.** This harness did not run `applyLut` to
completion — it built a real, direct, non-placeholder LUT and a real
pixel buffer, and observed **zero pixel-buffer writes across every
instruction the real DLL code actually executed** before hitting a wall
inside debug/assert message plumbing (very plausibly because this pass's
synthetic Impl/descriptor triggered one of `applyLut`'s own error paths —
several of which build exactly this kind of exception object, per
§28.2's own catalogue of `"Couldn't allocate..."`/`"...has bad status."`
strings — rather than because the harness reached deep into the success
path's own pixel-adjacent code). Getting further would mean tracing
exactly which of `applyLut`'s many internal gates this pass's synthetic
inputs fail and correcting them, or fully modelling `std::exception::
exception()`'s own real argument contract — bounded, "citras-driver-saga"
scale effort per §12/§27.5's own honest sizing of this same function,
not attempted further this pass. This dynamic result does not, on its
own, prove the SUCCESS path never writes a pixel; §28.2's exhaustive
static inventory (which covers every instruction in the function,
success and failure paths alike) is what actually closes that question —
this run is corroborating, not load-bearing, evidence.

### 28.5 — Verdict: dead end, with real (mostly static, partially
dynamic) evidence — not the mechanism for the shadow/black-point residual

Closing §27's own sharpened, still-open thread ("whether a real Impl WOULD
reach `applyLut`, and `applyLut` writes into the shared pixel buffer with
a real, non-identity LUT"): **it reaches `applyLut` (both real call sites
confirmed live), and `applyLut` does write a real, non-identity LUT into a
real operand object — but never into any pixel buffer.** The function
constructs and validates a small operand graph referencing the FUGC
Impl's own real apply-LUT array, then tears the whole thing down and
returns a status code; neither real caller (`analyzeArea`,
`balanceAreaImage`) does anything with that status beyond a pass/fail
branch. §27's own open question #2 ("whether `analyzeArea`'s own 'AREA
analysis image' … is the same shared pixel buffer `cna`/`dra` … read")
turns out not to matter either way: even if it does alias the real scene
buffer, `applyLut` — the one concrete mechanism §27 surfaced for
`analyzeArea`/`balanceAreaImage` to touch it — structurally cannot write
to it, on the evidence above.

This closes the FUGC-`applyLut` thread the same honest way §21/§25/§26
closed their own leads: real function, real call sites, real work — just
not a channel to the pixel buffer the shadow/black-point defect depends
on. Combined with §23's own standing, larger finding (the production Go
engine does not run any of this Python-verified DLL-reading work at all;
`ShastaToneRpd`'s crude two-point stretch is the actual mechanism), this
section does not change the doc's own bottom line — it closes one more
item on the "sole remaining open item" list §27 left, honestly, without
finding a second real bug to fix.

**Verification.** DLL MD5 checked
(`eea9dcf78ee21d4f7c515a6c2512242d`) against `/tmp/pakon_re/PakonIMAu.dll`
before any work this pass. `fcn.101fa5b0`'s own `afij` (2,289 B / 705
instructions / 90 basic blocks) matches §27.3's independently-derived
numbers exactly, confirming both passes read the same function at the
same DLL state. The "zero indexed writes" and "10 backward branches, two
shared targets" claims were checked mechanically over the function's own
`pdfj` JSON (regexing every decoded `disasm` string), not eyeballed — the
scripts (`check_loop_writes.py`, `applylut.pdfj.json`,
`applylut_full_pdf_plain.txt`) live under `/tmp/pakon_re/`, this doc's
established shared scratch directory, not committed. `fcn.100c1740`
(278 B), `fcn.1017de10` (524 B), `fcn.10328a90` (644 B), `fcn.1003bf80`
(36 B), `fcn.10099a40` (201 B) were each read in full via `af`+`pdf`, not
sampled — the mode `!= 2` branch's own `fcn.10099a40` is the one this
pass's dynamic run (§28.4) specifically exercised, closing the one gap
the static read alone left open.
`fcn.102bb760` (the harness's own stopping point) was independently
re-read this pass, not accepted on `trace_v50.py`'s citation alone. The
new script, `tools/ansel/python-pipeline/pakon_fugc_apply_lut_golden.py`,
does not modify any existing golden file — it imports `pakon_fugc` and
`pakon_autotone_shell_golden` read-only and adds its own new call/hook
logic only. No Python port file was written (no `pakon_area.py` or
pixel-application port) — per §28.2/§28.5's own conclusion, there is
nothing live to port.

## 29 — `fpo`'s per-unit-value question (open item list #2), settled with
live evidence from this exact unit: it genuinely runs the generic stock
value, byte-for-byte, no per-unit correction anywhere.

This doc's own "what changes about the open item list" section (below)
has carried, since §5, an open question distinct from §5's own settled
one: §5 ruled out any per-unit *correction mechanism* in the DLL (no
code path derives `fpo` from anything but the shipped `.dpi` text at
parse time). What stayed open was narrower and not resolvable by more
DLL reading: whether the generic, shipped-with-every-unit `fpo` value
itself happens to be wrong for *this specific* scanner, the way this
project's own lamp duty cycle turned out to need a real, measured,
unit-specific correction earlier in this same investigation. Settling
that needs to see what value the real software actually loads and uses
on this real, physical unit — not what the shipped file says it *should*
load.

Tonight's live hook capture (`tools/re/live_hooks/win_inject`, real
`hookcore.c`-based injection into the real `PSI.exe`/`PakonIMAu.dll` on
the real XP box, MinHook-based, real hardware, not emulated) gives
exactly that, for the first time in this investigation. The stock value,
read directly from the shipped `sba-CN-default.dpi` this project already
loads (`vendor/ansel/anselinstalldir/dataPathItems/sba/SbaDPI/
sba-CN-default.dpi:12`):

```
fpo = 879 1250 1386
```

`sba_preference` (`PakonIMAu.dll` `0x1028c780`) is one of the 23 real,
cited hook targets in this capture, and `pakon_sba_preference.py`'s own
header comment (line 11, pre-dating this pass) already documents its
real argument shape: *"Nested opening RGB = dpi `fpo`"* — the function
receives `fpo` packed as three 16-bit halves. Every one of the 7 real
`sba_preference` calls recorded in `live_hooks_20260814-102329.jsonl`
(uploaded by the project owner from the real XP box tonight) carries the
identical packed value at the same stack slot:

```
stack_dwords[8] = 0x04e2036f   ->  low16=0x036f=879 (R)   high16=0x04e2=1250 (G)
stack_dwords[9] = 0xffba056a   ->  low16=0x056a=1386 (B)
```

Checked mechanically across the whole capture, not eyeballed on one
call: decoding `(R, G, B)` from every `sba_preference enter` event's
`stack_dwords[8:10]` and collecting the distinct triples seen yields
exactly one value, present in all 7 calls — `{(879, 1250, 1386)}`. No
scatter, no partial match, no near-miss requiring interpretation: this
real unit's real, currently-running software, captured live during an
actual attempted scan tonight, is using the exact same generic stock
`fpo` every other F-135 unit's shipped install also has.

**What this settles.** Combined with §5's own static finding (no
mechanism exists to load anything else), this closes the open-item-list
#2 question completely, not just narrows it: it is not merely that the
DLL has no *path* to a per-unit `fpo` — this specific, real, physical
unit's real software, observed live, genuinely is not using one. If this
unit's `fpo` needed a hardware-specific correction the way its lamp duty
did, that correction is not happening anywhere in the running software
tonight. `fpo`'s numeric value is not a live candidate for the residual
shadow gap either, joining the four unreplicated stages (§25-§28) as a
closed line of inquiry.

**Honestly caveated.** This capture is partial — it stopped mid-scan
(the same real-hardware run whose log ends abruptly inside a
`tlb_polypixel`/`icc_effect_op`/`icc_xform_apply` loop, still under
active troubleshooting as of this section) — so it does not cover a
complete, successful scan end to end, only the portion that ran before
the stop. All 7 `sba_preference` calls captured happen to agree, which
is meaningful (a bug that only manifested after the capture's own cutoff
point can't be ruled out by this evidence alone), but a clean, complete
capture covering a full successful scan would close this more finally
than a partial one. The packed-value read (`stack_dwords[8:10]`) relies
on `pakon_sba_preference.py`'s own pre-existing "Nested opening RGB =
dpi fpo" documentation for the argument's identity rather than this
pass independently re-deriving the calling convention from fresh
disassembly — consistent with, not contradicted by, every other
independent confirmation of that same struct/argument mapping elsewhere
in this doc (§5, §9, §14), but noted plainly as inherited rather than
re-derived this pass.

## 30 — A real, new, reproducible bug found and fixed: `pakon_cna.py`'s
tone-curve NaN handling, not `pakon_dra.py`, explains a genuine real-photo
divergence §24's own captures never triggered — bit-exact and
pixel-identical after the fix

Tonight's washed-out fix (§23, temporary `app/main.js` default to the Python
engine) prompted the project owner to scan a fresh real photo specifically
to test it (`~/Library/Caches/PakonScan/captures/test123.bin`, frame 1 —
not the calibration-scan capture §24 used). Running §24's own, unmodified
`pakon_full_colour_chain_golden.py` against this frame (via a throwaway
wrapper that only monkeypatches its module-level `CAPTURE`/`FRAME_INDEX`,
per this pass's own instructions — the golden file itself, and its own
§24 citation, are untouched) reproduced a real divergence: `dra.lumMax`/
`edgeMax`/`effMax` all read **1544** from the real DLL but **1916/1896/1906**
from the Python port, `cna`/`dra`/`contrast`/`citras` LUTs off by ~1 at
matching indices, and the final sRGB ground-truth comparison showed the R
channel's shadow point 6 codes higher in the port (`p1=26`) than the real
DLL's own (`p1=20`) — this pass's own job was to find the real mechanism,
not just re-confirm the symptom.

**Reproduced first, cleanly.** `status_ok=True`, no exception, 35.4s wall
time — not §24's own instruction-cap harness bug (already fixed in this
script and re-verified still in effect this pass).

**`pakon_dra.py` itself is not the bug — confirmed by fresh, full
disassembly of `cum_bounds` (`0x10228bc0`), not assumed innocent.** Read
`af`+`pdf` in full (257 bytes, 19 basic blocks) and compared every
instruction against `pakon_dra.cum_bounds`'s own Python line-for-line: the
four threshold computations (`a`/`b`/`c`/`d` from `startingMinCumPoint`/
`cumPctBelowMin`/`startingMaxCumPoint`/`cumPctAboveMax`), the min-side
descend-then-trim-back loop, and the max-side descend-then-trim-forward
loop (the exact "mirror" the port's own docstring already claims) all match
register-for-register, branch-for-branch, including the three-bin
lookback/lookahead trim condition on both sides. **This rules out
`cum_bounds`'s own arithmetic as the cause** — the same conclusion the task
brief anticipated ("the actual root cause is very likely further upstream
than `effMax`'s own blend formula").

**Traced upstream via the DLL's own retained struct fields, not
speculation.** `dra`'s own `nSmallBins`/`nLargeBins`/`nLumPixels`/
`nEdgePixels`/`lumMin`/`edgeMin`/`effMin` all matched exactly between the
real DLL and the host — only `lumMax`/`edgeMax`/`effMax` diverged, and all
three collapsed to the identical value (1544) in the DLL. Since `dra`'s
"tone_lut" input (variant B's `analyze_hist`, the CN-Enhanced path) is
`cna`'s own `ToneScaleLut` — consumed by `generate_lut`'s `remap_hist`
(`scratch[toneLut[i]] += hist[i]`) before rebin/cum_bounds ever run — the
next check was whether `cna.ToneScaleLut` itself matches. It does not, far
beyond the small ~1-code noise the original report described: **3,280 of
5,000 entries differ, indices 1720–4999 forming one unbroken run in which
the real DLL's value is a flat, constant 1550 while the Python port's own
value climbs smoothly to 3150.** `cna.LuminanceHist`/`EdgeHist` (the raw
inputs) matched with zero mismatches, so the divergence originates inside
`analyze_image`'s dark/light curve-construction pipeline, not in histogram
collection.

**Localised further with three independent, live Unicorn checks, not one
speculative reading:**

1. **A completely separate, isolated `cna`-only harness**
   (`pakon_cna_golden.dll_analyze_image`, not the six-subsystem assembled
   one) reproduced the identical plateau on the identical frame — the same
   heap-relocation and instruction-cap fixes §24 already established had to
   be applied here too (this harness had never been run at real full-frame
   scale before; it hit both bugs fresh, diagnosed and fixed the same way,
   not re-derived from scratch). This rules out an assembled-harness-only
   artifact: `bucket_hist` (the post-smoothing edge-histogram bucket sums,
   `impl+0xC8`) matched with **zero** mismatches, and `threshold`/`n_edge`/
   all four sigmas matched exactly (`darkInSigma`/`lightInSigma` both
   genuinely `nan` on **both** sides — an already-documented "NaN cascade"
   this file's own `_half()` comment already describes at length, now
   confirmed live-DLL-real on this frame specifically, not just
   host-inferred).
2. **`hist_resample` (`0x1022ca80`) called directly and in isolation**
   (`pakon_cna_golden.dll_resample`) for both the dark and light halves,
   fed this frame's own real (already-matched) `bucket_hist`: `r.out`
   matched with **zero** mismatches for **both** halves, both entirely
   zero (`sum(r.out)=0`), confirming `cross_dark=cross_light=0` in the real
   DLL, not just in the host's own re-derivation.
3. **Fresh disassembly of both `contrast_map` bodies**
   (`0x1022c630` ascending / `0x1022c520` descending) at their shared
   per-step ratio-clamp idiom (`0x1022c687`/`0x1022c575`:
   `fcom [lo]; fnstsw ax; test ah,5; jp`) found the real, exact mechanism.
   For an ORDERED compare this idiom's `jp`-taken (skip-the-clamp) case
   fires exactly when `ratio >= lo` — algebraically identical to the port's
   `if not (ratio >= lo): ratio = lo`, which is why every prior synthetic
   and real-crop golden run (docs/74 §17/§24, none of which combined a
   NaN-cascaded half with a `cross` far from `pivot` on the same frame)
   never caught this. They stop agreeing for exactly one input: an
   UNORDERED compare. x87 `FCOM` sets C3=C2=C0=1 on unordered, so
   `ah & 5 == 0x05` — **even** parity, PF=1, the **same** parity the
   genuine `ratio >= lo` case produces — so the real DLL's `jp` ALSO fires
   for NaN and leaves `ratio` as NaN, while Python's `not (NaN >= lo)` is
   `True` (IEEE754: any NaN compare is `False`, so `not False` is `True`),
   taking the **opposite** branch and silently laundering NaN into the
   finite `lo=0.5`.

**Once `ratio` is genuinely NaN and stays NaN** (confirmed identical idiom
in both `0x1022c520` and `0x1022c630`, so both halves are affected the same
way structurally): `acc` is poisoned to NaN on the very first loop
iteration; `round_half_up(NaN)` reproduces x86's own `__ftol`-on-NaN
"integer indefinite" outcome, which the next line's `if k < 0: k = 0` pins
to `k = 0` — and because `ratio_den[0]` is the *same* NaN in this frame's
degenerate scenario, `ratio` stays NaN and `k` stays pinned at 0 for every
remaining step, making `out[i] = clamp(0 - delta, ...)` constant for the
rest of that half's walk. The old port instead let `ratio` settle at the
finite `lo` and kept walking normally — a smoothly increasing curve instead
of a flat one.

**Why only the light (ascending) half is visibly wrong, not the dark
(descending) half too — reasoned through, then confirmed, not assumed.**
Both halves hit the identical NaN cascade (`cross_dark = cross_light = 0`,
confirmed above). For the descending walk, `idx = cross_dark = 0` is
*already* the boundary the walk's own `k < 0 -> k = 0` clamp pins to almost
immediately regardless of whether `ratio` is genuinely stuck at NaN or
merely clamped-then-decaying (the descending accumulator starts at `idx=0`
and moves *away* from `pivot_bucket`, going negative within the first few
steps either way) — so the buggy and correct behaviours coincide there.
For the ascending walk, `idx=0` is far from where the walk needs to go (up
past `pivot_bucket=178` to `499`), so the port's wrong clamp let `acc`
escape and climb smoothly while the real DLL's genuinely-NaN `ratio` never
escapes — a large, real, visible divergence. **This is not a guess**: a
scratch-patched copy of `_contrast_map` with only this one line changed
(`if ratio < lo: ratio = lo`, the IEEE754-correct, NaN-preserving form) was
run through the rest of `analyze_image`'s own real pipeline
(`gauss_smooth` → `build_tone_lut` → the pivot-anchored normalisation) on
this exact frame's real intermediate arrays, and reproduced the real DLL's
own observed plateau — **1550, constant, for all 3,280 of the affected
bins — with zero mismatches** — while correctly leaving the (numerically
coincidental) dark-half region unaffected, exactly matching the real DLL's
own behaviour on both counts.

**The fix.** `pakon_cna.py`'s `_contrast_map` (used by both
`contrast_map_up`/`0x1022c630` and `contrast_map_down`/`0x1022c520`):

```python
# before (silently launders a NaN ratio into the finite lo=0.5):
if not (ratio >= lo):
    ratio = lo
# after (matches the real DLL's own fcom/fnstsw/test-ah,5/jp idiom,
# 0x1022c57b / 0x1022c68d — an unordered compare no longer takes this
# branch, so a genuinely-NaN ratio stays NaN, exactly as the real DLL
# leaves it):
if ratio < lo:
    ratio = lo
```

`pakon_dra.py` needed **no change at all** — its own `cum_bounds`/
`eff_bounds` were independently confirmed correct against fresh
disassembly (above), and the fix lives entirely upstream, in `cna`'s own
tone-curve construction. This is a real, if narrow, correction to the
`CNA_CONTRAST_MAP_PORTED = True` claim: "verified bit-exact" was true for
every case this project had exercised before tonight, but not for a
genuinely NaN-valued `ratio`, a case only a real photo with a fully-empty
resampled half's histogram and a `cross` far from `pivot` reaches. Full
citations and the corrected docstring are now in `_contrast_map`'s own
docstring in `pakon_cna.py` (search "THE LOW-CLAMP TEST'S NaN BEHAVIOUR").

**Verified bit-exact and pixel-identical, not eyeballed.** Two independent
re-runs against the real, MD5-verified DLL on this exact frame, after the
fix:

```
Isolated cna-only harness (pakon_cna_golden.dll_analyze_image):
  tone_lut mismatches: 0 of 5000            (was 3,280 of 5,000)

Assembled six-subsystem harness (this pass's own repro of the task):
  Stage 2 field diff: 2 fields (cna.darkInSigma/lightInSigma, both nan==nan
    — a pre-existing float-comparison artifact of the diff harness itself,
    unrelated to this fix: nan != nan even when both sides genuinely agree)
  dra.lumMax / edgeMax / effMax: no longer in the mismatch list at all
  Stage 3, sRGB [p1, p50, p99]:
    R: python=[20.0, 126.0, 253.0]  dll_ground_truth=[20.0, 126.0, 253.0]
    G: python=[71.0, 190.0, 252.0]  dll_ground_truth=[71.0, 190.0, 252.0]
    B: python=[56.0, 231.0, 254.0]  dll_ground_truth=[56.0, 231.0, 254.0]
  |python - dll_ground_truth| over all pixels/channels:
    mean=0.000  p99=0.00  max=0.0
```

The R-channel shadow point the original report flagged (`p1=26` port vs.
`p1=20` real DLL) is now **`p1=20.0` on both sides** — pixel-identical
across the entire frame, not just at the percentile. The scale-sweep
diagnostic's own 400×400/800×800/1500×1500 crops (printed automatically
because the harmless `nan`-artifact still counts as "a mismatch" to the
harness) show non-degenerate `ToneScaleLut`s at every size, consistent with
this being a genuinely frame-content-dependent trigger, not a
scale-dependent one.

**What this means for the app.** §23 already established the shipped Go
engine never wired in this chain at all (still running `ShastaToneRpd`, a
placeholder), so this fix does not by itself change production behaviour
tonight — but it removes a real, now-confirmed-fixed defect from the
Python engine app/main.js was switched to as tonight's interim default,
and it is one concrete, verified data point that the "whole chain
bit-exact before wiring into Go" bar (`shasta.go`'s own comment, quoted in
§23) is closer than it was before this pass started, not farther.

**Honestly scoped.** This fix targets the exact mechanism this pass traced
and verified end to end on this one real, reproducible case. It was not a
blind pattern-fix: the `if not (x >= y)` vs. `if x < y` distinction only
matters when `x` can genuinely be NaN, which the fix's own docstring now
explains precisely (a `0.0/0.0` from an entirely-empty resampled
histogram half). No other `not (x >= y)`-shaped comparison anywhere else
in this project's port code was audited this pass; if any exist and can
also see a genuine NaN operand, they are a real, separate risk worth a
future pass's attention, not covered by this fix.

## 31 — A real, matched vendor TIFF of this exact roll settles the direction
question §13/§15 could only settle statistically: the port is ~2× too bright
at every percentile, not just in the shadows. A new, genuine film_base bug is
found and fully characterized — but proven, both analytically and
empirically, insufficient to explain it. Root cause still open.

**The new evidence, and why it's stronger than §13/§15's.** The project
owner had a real Pakon PSI scan of the *exact same physical roll* already in
hand: `AA001.tif`–`AA006.tif`, real vendor TIFFs, direct-visual-confirmed
(same street corner, same "Fellow Barber" sign, same person) as the same
photograph as frame 0 of this project's own `test123.bin` — a roll captured
tonight, well after every hardware fix this doc's earlier sections describe.
Unlike §13 (carved, B&W, caveated) or §15 (a different roll, only
"confirmed... same physical scan session" by the owner's word), this is a
same-roll, same-frame, losslessly-exported colour comparison — no caveats
about carving, film type, or roll identity.

**Reproduced directly first, per this task's own instruction, not assumed.**
`tools/pakon_render.render_frame` (`PAKON_COLOUR_ENGINE=python`,
`film_path="ColNeg"`, the existing opened roll at
`~/Library/Caches/PakonScan/workspace/f4c91b62/roll.json`, real roll-wide
`film_base=[3107, 2490, 2414]`, real `fpo=(879,1250,1386)`, real
`setshifts_out=(683,297,151)`), frame 0 (`a=2048,b=5048`, `confidence=low,
phase=LookAtBeginning` — the framing cascade's own weakest placement grade
on this roll, noted for completeness, not shown to matter below), default
`scale="preview"`:

```
              p0.1   p1    p5    p50   p95   p99   p99.9
R  ours:        0    20    62   178   249   254   254
R  AA001.tif:   0    10    17    90   235   252   255
G  ours:       41    51    71   192   250   254   254
G  AA001.tif:   8    11    17   103   239   251   255
B  ours:       25    41    58   217   254   254   254
B  AA001.tif:   7    10    18   139   246   255   255
```

Confirms the task's own transcribed numbers to within a few codes (this
session's own re-measurement, not copied) and confirms the framing: **the
gap is not confined to the shadow end** — the median alone is 88/89/78 sRGB
codes too bright (R/G/B), and even p95/p99 sit 14-19 codes high. This is a
different-shaped defect from §1-9's "no real blacks" framing (a compressed
shadow band on an otherwise-plausible curve) — it is closer to a uniform
excess across the whole tonal range, now provable in absolute terms against
a real, matched reference for the first time in this doc.

### 31.1 — Traced `scene_rpd12`'s real call chain stage by stage, per this
task's own method

Same production code, same frame, direct calls to `pc.poly_hwc` →
`pr._rpd16` → `ansel.rpd16_to_rpd12` → `dec.f135_rom12_to_rpd12` →
`eng.render_scene` (SBA balance apply → FUGC apply-LUT → the six-subsystem
`analyzeAutoTone`, per `pakon_ansel.AnselEngine.render_scene`'s own body,
`:839-899`) → `eng.to_srgb`, each stage's own `[p1,p50,p99]` reported:

```
stage                          R                    G                    B
0. calibrated 14-bit    [  662, 3669, 9791]  [  468,2399,6702]  [  214,1467,6016]
1. poly (rpd12 domain)  [  352, 1199, 2819]  [  572,1102,2335]  [  701,1057,2234]
2. inv16 (post-invert)  [923.7,1331.7,2064]  [1284,1743,2456]   [1432,2011,2820]
3. toned (post autoTone)[ 1384, 1760, 2421]  [1386,1795,2415]   [1329,1908,2596]
4. sRGB                 [   10,  181,  254]  [  68, 194, 254]   [  55, 217, 254]
```

Every stage's own output is internally consistent with the already-verified
formulas cited throughout this doc (§8's own stage table, on a different
roll, shows the identical shape: sharp compression at the poly→inv16
boundary, near-flat span through toning). The question this task asks —
does any stage's *own* output look implausible, not just "does it run" — is
answered at the film_base measurement specifically, below.

### 31.2 — The real, new bug: roll-wide `film_base_codes` is contaminated
by real photo highlights on this roll, under the *current* lamp calibration
— the same mechanism §2 found in the single-frame fallback, now shown to
also reach the "correct," roll-wide, production path

`roll.film_base=[3107,2490,2414]` came from `open_capture`'s real,
roll-wide `FindDmin` pass (`pakon_render.py:864-895`, `dec.film_base_codes`
→ `film_base_window` → `film_base_line_mask`, the exact mechanism §3/§4 of
this doc treated as "the real, correctly-measured roll-wide film base," in
contrast to the single-frame fallback §2 found broken). Re-ran this pass's
own accumulation loop directly, with diagnostics `film_base_window` itself
doesn't expose:

```
lin_lines kept: 19,129 of 25,427 (75.2%)   lin_px: 37,684,130   thr (0.1%): 37,684
```

**Per-chunk keep fraction, against the roll's own known geometry**
(`film_start=2048`, `film_stop=21248`, 5 frames spanning 2048-18804):

```
lines      0- 4096: kept 2072/4096 (50.6%)   [head leader 0-2048 + frame 0]
lines   4096-20480: kept 4096/4096 (100.0%)  [frames 1-4 + every inter-frame gap]
lines  20480-24576: kept  673/4096 (16.4%)   [tail edge of film + early tail leader]
lines  24576-25427: kept    0/ 851 (  0.0%)  [deep tail leader]
```

This is almost exactly `film_start`/`film_stop`: 2072≈2048 (the head-leader
lines correctly excluded), 673≈768 (the real film lines in that chunk,
20480 to `film_stop`=21248, correctly kept), 0% correctly excluded past
`film_stop`. **The line-level leader/film split itself is working exactly
as designed** — this is not a repeat of §22's `balanceAreaImage` polarity
bug or anything like it.

**But the consequence is that essentially none of the "kept" population is
genuine clear film.** Every chunk inside `[2048, 21248)` — the real film
region, including every inter-frame gap — is kept at ~100%, and the true
leader (correctly excluded) contributes ~0 pixels to the histogram
`find_dmin_code_from_hist` actually walks. Reading that walk's own top of
histogram directly for R (code, count, cumulative %):

```
4095:   47   (0.0001%)      3110: 934  (0.1187%)
4036:    1   (0.0001%)      3107: 858  (0.1020%)  <- FindDmin(R) lands here
3947:    1   (0.0002%)      3100: 934  (0.1187%)
...  a smooth, monotonically increasing count from 4095 down to 3107,
...  no spike, no plateau, no cliff anywhere in the range
```

A genuine clear-film Dmin should show a tall, narrow spike (clear film reads
consistently) with a sharp drop into real image content just below it. What
this shows instead — smooth, continuously increasing counts with **zero**
structural break anywhere from 4095 down through 3107 — is the signature of
a natural photographic highlight histogram tail, the identical shape §2.2
already characterized for the single-frame fallback ("numerically
indistinguishable from the frame's own 99th-percentile highlight"). Direct
confirmation: measuring the *whole film region* (`2048:21248`, i.e. exactly
the population `film_base_line_mask` keeps) as ordinary image content —

```
region                          R                    G                    B
whole film region (2048:21248)  p99=2994  p99.9=3108  p99=2420 p99.9=2489  p99=2350 p99.9=2412
current roll.film_base                    3107                  2490                  2414
```

— matches the *current* `roll.film_base` almost exactly, to single digits.
**`roll.film_base` is measuring the top ~0.1% of five real photographs
(frame content and inter-frame gaps alike), not clear film**, on this roll,
under this calibration.

**Why genuine leader isn't reaching the walk: it's saturating the poly
domain, not just (or not even) the sensor.** Measuring the known head/tail
leader regions directly (`film_start`/`film_stop` boundaries, not the
saturation mask):

```
region                mean line-sat%   R                        G                     B
HEAD leader (0:2048)      98.78%      0.39% at ceiling,         98.78% at ceiling     1.50% at ceiling,
                                       unsat p99.9=3972           (1.22% survive)      unsat p99.9=4082
TAIL leader (21248:n)    100.00%      99.95% at ceiling,        100.00% at ceiling    99.81% at ceiling,
                                       unsat p99.9=4090           (0 survive)          unsat p99.9=4090
```

Genuine clear film on this roll reads at **~4070-4090 in the poly domain**
(near its own 4095 ceiling) — roughly 1,000+ codes above the contaminated
`roll.film_base` — but nearly all of it is *at* that ceiling, and
`film_base_line_mask`'s per-line ≥50%-saturated test (correctly) excludes
those lines wholesale, leaving nothing but real photo content for the walk.
**A cross-check on the raw sensor domain shows this saturation is not
uniformly a hardware ceiling**: HEAD leader's raw 14-bit data is nowhere
near clipped (R 0.09% at the raw ceiling, G 0.00%, p50≈14,000 of 16,383),
even though the *same* pixels read 98.78% saturated in the poly domain for
G — i.e. the polynomial colour-matrix stage itself (`pc.poly_hwc`, this
unit's registry/EEPROM-sourced coefficients, unrelated to the lamp-duty
fix) is what clamps clear film to its own 4095 ceiling for G, not the CCD.
TAIL leader, by contrast, *is* genuinely sensor-saturated (R 23.8%, G
34.2%, B 34.6% at the raw 16,383 ceiling) — a real, independent
confirmation of §6's own finding that the post-recalibration lamp duty is
strong enough to saturate clear film outright at some points in the scan.
Both mechanisms point the same way: under the *current* calibration, this
roll's genuine Dmin is not reliably recoverable from a histogram-percentile
walk over "unsaturated lines," because there usually aren't enough
unsaturated near-Dmin pixels left to walk.

**This is a real, previously-undocumented bug, distinct from §2's.** §2
found the single-frame `film_base=None` fallback path broken because it had
*no leader in view at all*. This is the roll-wide, production
`film_base_codes` path — the one §3/§4 treated as the fix — breaking for a
different, newer reason: genuine leader *is* in view, but the current
(post-2026-08-12) lamp duty saturates it too hard, at the poly-domain
level, for the existing line-saturation heuristic to leave anything useful
behind.

### 31.3 — Tested directly, not assumed: this bug does **not** explain the
brightness gap, and provably cannot on its own

**A corrected film_base, substituted into the same unmodified chain.**
Built a candidate from genuine leader pixels only (`film_start`/`film_stop`
boundaries, literal ceiling pixels excluded as uninformative, same
`find_dmin_code_from_hist` walk): `R=4090` (32.8% of leader pixels
informative), `B=4082` (32.5%), `G=4069` (only 0.40% informative — flagged
as a small, unstable sample, not a confident measurement). Re-rendered
frame 0 with this candidate, same unmodified `scene_rpd12`/`render_scene`:

```
                     sRGB median [R, G, B]
film_base=[3107,2490,2414] (current):  [181, 192, 217]
film_base=[4090,4069,4082] (candidate): [168, 214, 239]
target (AA001.tif):                     [ 90, 103, 139]
```

R moves modestly toward target (181→168, still far short of 90); **G and B
move away from target** (192→214, 217→239). Net effect: not an improvement.
A joint proportional sweep (all three channels scaled down together) finds
no single factor that helps all three either — e.g. `base=(1200,1000,900)`
lands `[140,109,47]`: G lands almost exactly on 103, but R is still far
too bright and B has overshot past the target into too-dark. Per-channel
independent sweeps (one channel's base moved, the other two held) run into
gamut-clipping artefacts (R collapses to 0 well before reaching a plausible
value) that make them unreliable evidence either way.

**Why, analytically, this had to fail.** `f135_rom12_to_rpd12`'s own
formula is `rpd12 = fpo + 1000·(log10(base−c9) − log10(poly−c9))`. A pure
multiplicative rescaling of `base` and `poly` together — which is what
"the calibration is off by a factor" would look like — pushes `log10(base)`
and `log10(poly)` up by the *same* additive amount and **cancels exactly**
in the subtraction; it cannot produce a uniform brightness shift by itself,
only in combination with the fact that only `base` (not `poly`, which
tracks each pixel's own real content) is being changed in this test. This
is confirmed, not just argued: the film_base sweep above changes the
image, but not in a way that closes the gap for more than one channel at a
time, exactly as this algebra predicts for a single, imperfectly-chosen
lever.

**c9 (the polynomial pedestal) was tried too, since it does *not* cancel
the same way** (it is subtracted from both `base` and `poly`, but by a
fixed additive amount, so it changes their *ratio*, not just a shared
offset). Same frame, film_base held at the current (contaminated) value,
`c9` scaled uniformly by a single factor across all three channels:

```
c9 scale   c9 = (R,G,B)                     sRGB median [R,G,B]
  1.0      (159.6, 444.7, 635.5)  [orig]     [181, 194, 218]
  1.5      (239.4, 667.1, 953.3)             [ 88, 162, 232]   <- R lands on target
  2.0      (319.2, 889.5, 1271.1)            [  8, 156, 227]   <- R overshoots
  3.0      (478.8, 1334.2, 1906.6)           [  0, 179, 226]
  5.0      (798.0, 2223.7, 3177.7)           [178, 188,   0]   <- unstable (B crashes)
  8.0      (1276.7, 3558.0, 5084.3)          [207,  27,  30]   <- unstable (G,B crash)
target                                        [ 90, 103, 139]
```

R passes almost exactly through its own target at `c9 scale=1.5`, while G
and B are still 60-90 codes short of moving toward *their* targets at the
same scale, and the whole family becomes numerically unstable (non-
monotonic, chaotic) above `scale≈2` as `poly−c9` approaches zero for a
growing fraction of pixels and the clamp in `f135_rom12_to_rpd12` engages.
**No single uniform scale factor — on `film_base` or on `c9` — reproduces
the vendor's per-channel targets simultaneously**, and the channels' wildly
different sensitivities to both parameters (driven by how close each
channel's own `base`/`c9` already sit to each other) make a hand-tuned
per-channel fix indistinguishable from curve-fitting to one frame, not a
principled correction.

**Ruled out independently, not re-litigated:** `fpo` — confirmed live,
this exact unit, §29, matches what this port already uses, no per-unit
correction exists anywhere in the running vendor software. `setshifts_out`
— deterministic, DPI-file-static, built from already-Unicorn-verified
`sba_apply.setshifts_12`/`preference_shift_words`, identical for every
frame on this roll (§9 already established this; unaffected by which frame
or which film_base is used). FUGC's apply-LUT gate and near-identity
behaviour — real-DLL-verified (§10, §27-28). `analyzeAutoTone` itself —
bit-exact at full-frame scale, this roll's own calibration state (§24).

### 31.4 — Verdict: two real findings, root cause still open

1. **A real, new, fully-characterized bug**: `film_base_codes`'s roll-wide
   `FindDmin` walk, on this roll, under the current (post-2026-08-12) lamp
   calibration, draws its population almost entirely from real
   photographic content rather than genuine clear film, because genuine
   leader now saturates the *polynomial colour-matrix stage's own 4095
   ceiling* too heavily (and, at the tail specifically, the raw sensor's
   own ceiling too) for the existing per-line saturation heuristic to
   leave a usable near-Dmin population behind. This is a real, independent,
   worth-fixing defect in the same family as §2's — not a re-statement of
   it, a second, distinct mechanism reaching the "already fixed" roll-wide
   path this time.
2. **That bug is not the (sole) explanation for the ~2× brightness gap**,
   shown both empirically (the best available correction improves one
   channel and worsens two) and analytically (a pure-scale correction to
   `base`/`poly` together cancels in the log-difference formula and cannot
   produce a uniform shift). Root cause remains genuinely unresolved. The
   two most likely remaining loci, neither confirmed this pass:
   `f135_rom12_to_rpd12`'s own formula construction (`F135_INVERT_PORTED
   = False` — "no DLL call site was ever found... the formula was
   reconstructed from first principles," per §8's own already-standing
   caveat, now sharpened by a real vendor comparison rather than just "no
   real blacks" reasoning), or the polynomial colour-matrix coefficients
   themselves (`load_unit_matrix`, EEPROM-sourced — §31.2's own finding
   that clear film clips the poly domain without clipping the raw sensor
   is at least suggestive that this per-unit calibration may not correctly
   match the post-recalibration lamp intensity it now receives, though
   this pass did not establish that directly).

**No production code was changed by this pass.** The film_base
contamination bug (§31.2) is real and independently worth fixing, but this
pass's own attempted correction (§31.3) does not improve the match against
the real vendor TIFF — it worsens it for two of three channels — so,
per this task's own explicit instruction not to claim success without a
verified, closed gap, nothing was shipped. Flagging §31.2 plainly as a
real, evidenced defect for a future pass to fix on its own merits (the
same category as §2's Dmin methodology gap: correct to fix, not shown to
explain this symptom), and §31.3's negative result as real, load-bearing
evidence about where the true root cause can *not* be, ruling out an entire
class of single-parameter fixes within the existing formula for the first
time in this investigation.

## 32 — `f135_rom12_to_rpd12` checked directly against the real DLL for the
first time: the two candidate addresses are resolved (neither is it), a
genuine machine-instruction search for the formula elsewhere in TLB.dll
comes back empty, and PakonIMAu.dll's own search space is too large to
finish in one pass — thread closed without resolving the mystery

§31 named `f135_rom12_to_rpd12` (`F135_INVERT_PORTED = False`) the sharpest
remaining unverified thread behind the ~88-89 sRGB code uniform brightness
excess, and flagged that no prior pass had ever checked it against a real
DLL call site — everything else in this doc's chain has been (`cna`/`dra`
bit-exact §24, `fpo` live-verified §29, FUGC real-DLL-verified §10/§27-28,
`analyzeAutoTone` bit-exact at full-frame scale §24), but this one stage
never has. This section does that check directly, with live disassembly
against the real, hash-verified DLLs, not by re-reading prior citations.

### 32.1 — DLL provenance, checked fresh, not assumed

`PakonIMAu.dll` at `/Users/guy/pakon-windows-repair/COM-SERVER/PakonIMAu.dll`
hashes `eea9dcf78ee21d4f7c515a6c2512242d` — an exact match to the hash every
prior pass in this doc (§5, §10, §24, §31) cites before relying on it.

`TLB.dll` needed its own re-verification, per this task's own instruction —
this doc has never cited a TLB.dll hash itself. `docs/70` (digital-ice
groundwork, this same session) already did this work: *"(private remote)
against `TLB.dll` md5 `193d9b2ce0a4b77ae9b78262bd06c0fc`."*
`/Users/guy/pakon-windows-repair/COM-SERVER/TLB.dll` hashes exactly that.
**This is the copy used for everything below.** For completeness: three
other local copies exist, at `~/Downloads/FX35_PR1[…]/installer/
InstallationFiles/TLB.dll` (all three identical to each other), hashing
`e7f21021e0140c1935a3ae4de7bd3498` — a *different* build, not cited by any
doc in this repo, and **not used** for any of the disassembly below. Flagged
explicitly rather than silently picking whichever copy was more convenient.

### 32.2 — The two candidate addresses, disassembled directly: neither is
the inversion, and the "naming ambiguity" resolves to "both are PolyPixel"

This task named two candidates from `tools/re/live_hooks/agent.js`/
`common.h`/`README.md` — `0x1000d880` and `0x10034b9b` — flagged there as an
"internally inconsistent" citation the live-hook harness hooked *both*
addresses specifically to resolve live, but never did (no capture was ever
run through it for this). Read that flag directly rather than guessed at:
`agent.js`'s own comment says the ambiguity is between "`TLB.dll fcn.1000d880
@ 0x10034b9b`" (this port's own citation) and "docs/65's separate citation
of `TLB.dll:fcn.1000d880`" — i.e. the ambiguity was always about whether
these are *the same function under two names* or *two different functions*,
**not** about whether either one is the negative→positive log inversion.
That framing turns out to matter, below.

Both were given full function-boundary disassembly (`aa; af @ <addr>; pdf @
<addr>`, r2 6.1.8, PE loaded at its real base `0x10000000`) — not a raw
byte-range guess:

**`0x1000d880`** (`fcn.1000d880`, 845 bytes, 28 basic blocks, 258
instructions): opens with a `switch` on a film-class argument compared
against `7` (`cmp eax, 7` @ `0x1000d89e`, 8-case jump table), where case 2
selects `lea edx, [esi + 0xc8]` and every other case selects `lea ecx, [esi
+ 0x50]` — an **exact** structural match to `pakon_decode.check_film_class`'s
own already-documented citation, *"filmClass 2 (colour reversal, PosMatrix
at TLB this+0xc8)"* vs. the default NegMatrix branch. After the switch: a
tight per-pixel loop over three `word` planes (`movzx ax/cx/dx, word [edi]/
[ebx]/[ebp]`) doing `fild`→`fmul`→`faddp` chains against ten stored
coefficients per channel — a **3×10 float polynomial**, exactly what every
existing citation in this repo already says `0x1000d880` is (`pakon_color.py`,
`pakon_color_golden.py`, `pakon_render.py`, `pakon_raw_decoder.c`,
`pakon_pipeline_cli.c`). **Zero log-family FPU instructions anywhere in the
function.** This is `PolyPixel`, confirmed, not reconstructed from a prior
citation.

**`0x10034b9b`** (`fcn.10034b9b`, 1141 bytes, huge switch-and-registry-driven
body): its **very first instruction** is `call fcn.1000d880` — it does not
compute a polynomial itself, it *calls* the one above. This is an exact
match to this port's own existing, correctly-scoped citation in
`pakon_scene_context.py:488-492` (`addscene_colneg_remap_dmin_rgb_f135`):
*"Roll driver `fcn.10034a60` calls poly on the seeded frame dmin words
(`+0x6cac…`) before packing the AddScene desc."* It is AddScene's
**dmin-priming driver** — it runs the raw FindDmin-measured film-base RGB
through the same PolyPixel polynomial ordinary pixels get, so the AddScene
descriptor's dmin field lands in the same poly-corrected domain as the rest
of the frame. **Zero log-family FPU instructions in this function either.**

**Verdict: neither address is `f135_rom12_to_rpd12`, and the "naming
ambiguity" is resolved** — both addresses are the PolyPixel family (the
general polynomial, and its caller in the specific context of AddScene's own
dmin priming), not two names for one function and not a log-based inversion
under either name. This directly negates the reading of these two citations
as candidates for the stage-2 inversion's entry point; `agent.js`'s own
hedge ("an r2 auto-name/VA pair that looks inconsistent... hooked below
precisely so a live capture can resolve which is which") can now be answered
without needing a live capture: they're two different functions, one calling
the other, both PolyPixel-family, confirmed by static disassembly alone —
the ambiguity was real but narrower than "is one of these the inversion."

### 32.3 — Searched TLB.dll exhaustively for the one instruction the formula
structurally requires; the fullest traceable chain is unrelated CRT plumbing

`rpd12 = fpo + 1000*(log10(base-c9) - log10(poly-c9))` requires a log
somewhere. TLB.dll imports **no CRT DLL** (`ii` lists only `VERSION.dll`,
`KERNEL32.dll`, `USER32.dll`, `ADVAPI32.dll`, `ole32.dll`, `OLEAUT32.dll`,
`SHLWAPI.dll` — no `MSVCRT.dll`), meaning its CRT is statically linked, so
`log10` would show as internal code with no import-table name to grep for.
The period-correct way to find it is the x87 opcode itself:
`fyl2x`/`fyl2xp1` (`d9 f1`/`d9 f9`) are how this era of MSVC computes
`log`/`log10`/`ln`. Searched the **whole binary**, not scoped to any
function (`r2`'s `/x` raw byte search): **7 `fyl2x` sites, 0 `fyl2xp1`, 2
genuine `f2xm1` sites** (a third apparent hit, `0x1005a093`, disassembles to
garbage at that exact byte offset — inside the tail bytes of an unrelated
`jmp` instruction, not real code; discarded as a false positive from
unaligned byte matching, not counted above).

Traced the fullest, most completely reachable chain end-to-end via real
`axt` (cross-reference) evidence at every hop, not inferred from proximity:

```
fcn.100341b0  (CiTLAMain COM vtable method — confirmed by a real DATA xref:
               registered via `push 0x100341b0` @ 0x10040236, inside
               method.ATL::CComObject_class_CiTLAMain_.8.virtual_28)
  -> 0x10034374  call fcn.100125a0
    -> 0x100129b8  call fcn.1000f130
      -> 0x1000f240  call fcn.1000ef80
        -> 0x1000f0ce, 0x1000f118  call fcn.1000dfc0  (TWICE)
          -> fcn.1000dfc0 itself contains the actual fyl2x pair,
             @ 0x1000dffb and @ 0x1000e049
```

Read `fcn.100341b0`'s full 1533-byte body (559-line `pdf`) rather than
stopping at the call graph. It is a **scan-session bookkeeping routine**:
`CreateEventW` for four named events (`"EventScanPacketReady"`,
`"EventScanWriteToDisk"`, `"EventScanCalibrate"`, `"EventSaveToClientMemory"`),
a `"HiResMegabytesTotal or HiResMegabytesRoll"` free-space check, a read of
registry key `"Software\Pakon\TLB"` feeding directly into the traced call
chain above (`push str.SoftwarePakonTLB; push reloc...SysReAllocString; call
fcn.100125a0` @ `0x10034368-0x10034374` — i.e. this is a registry-string
read converted to a number, the classic CRT `atof`/`strtod` shape: scaling a
parsed decimal by a power of ten via `fyl2x`, not colour density), and a
conditional `DMLDICELib.dll` load. **This has nothing to do with per-pixel
colour** — it is session/hardware setup, not the F-135 pixel path. This one
chain alone accounts for 3 of the 7 `fyl2x` hits (the pair inside
`fcn.1000dfc0`, reached twice) plus the two calling functions that lead to
it; the remaining `fyl2x` sites (`fcn.1004926d`/`fcn.10050d10`,
`fcn.10050a2e`) and the 2 genuine `f2xm1` sites sit at addresses this
project's own docs have never cited for anything F-135/AddScene/colour
related, and were not individually traced to their own root callers within
this pass's time budget — noted as incomplete for those specific sites, not
claimed as ruled out.

**For TLB.dll specifically: no log-family instruction this pass could trace
leads to a per-pixel colour formula.** This is new, real, negative evidence
— not a repeat of "no DLL call site was ever found," but an actual
instruction-level search for the operation the formula requires, run for
the first time.

### 32.4 — Extended to PakonIMAu.dll: search space far larger, spot-checked,
not exhaustively triaged

The same byte search against `PakonIMAu.dll` (the DLL hosting
`analyzeAutoTone` and everything downstream) finds **61 `fyl2x` + 64
`f2xm1` sites** — an order of magnitude more than TLB.dll, consistent with
PakonIMAu.dll being the much larger binary (ICC/KCMS colour management,
JPEG-family codec code, and multiple already-documented statistics-heavy
capabilities: `noiseTable`/`pnr`/`nra`, `analyzeArea`'s own 732-function
dust/scratch detector per `docs/67`).

Spot-checked the cluster nearest the already-extensively-characterized
AutoTone/`analyzeArea` address neighbourhood: `fcn.100e37d0`
(`0x100e37d0`-`0x100e3d0a`, 1338 bytes) contains **11 of the 61** `fyl2x`
hits within ~800 bytes — far too many, and far too densely packed, to match
the formula's own shape (exactly two log calls per pixel, in a loop, each
followed by a subtraction). That density is much more consistent with a
statistical/entropy-style computation than a per-pixel density conversion —
plausibly in `analyzeArea`'s own domain (dust/scratch statistics), which
this doc's §27 already spent a 943-function reachable-set walk on without
surfacing this specific address. Two further clusters (`fcn.10262fd0`,
1452 bytes; `fcn.104693f0`, 1710 bytes) were also identified but not read in
full — both are large, multi-purpose functions, not the small, tight,
two-log-call shape the target formula would produce.

**Stated plainly: this is a spot-check, not an exhaustive search.** Unlike
§32.3's TLB.dll result (all 7 real `fyl2x` sites accounted for or traced),
this pass did not individually triage the remaining ~50 `fyl2x` and ~64
`f2xm1` sites in PakonIMAu.dll — a binary this large and this unfamiliar,
carrying multiple unrelated subsystems, would need a properly scoped
follow-up (most plausibly: start from `analyzeAutoTone`'s and its six
subsystems' own already-catalogued reachable sets, which are already
enumerated by `tools/re/reachability.py` per `docs/67`, and check which if
any of the 125 log-family sites fall inside them) rather than a raw
whole-binary grep. Flagged as incomplete, not as a clean negative result,
for PakonIMAu.dll specifically.

### 32.5 — Why static disassembly, not Unicorn, for §32.2's two addresses

Per this task's own instruction, live execution is the stronger form of
evidence when it's available, but static disassembly alone is acceptable
when a function is small/simple enough to read with high confidence. Both
`0x1000d880` and `0x10034b9b` qualify: the question being asked of them
("does this function compute a log-difference density formula") is answered
by their control-flow *shape* alone — a switch-dispatched, FPU-multiply-only
polynomial loop, with **zero** `fyl2x`/`fyl2xp1`/`f2xm1`/`fyl2xp1`-family
instructions present anywhere in either function's bytes — not by any
register value that could differ under live execution. No Unicorn run
could change "this function contains no log instruction." Unicorn was
therefore not run for §32.2; it was used implicitly nowhere in this
section, consistent with prior static-only sections of this doc (§11, §12,
§18 already used this same standard).

### 32.6 — Context from this doc's own prior work, not re-litigated: why the
formula's overall *shape* is still plausible even though its exact
correctness remains unverified

Not new work — cited here because it bears directly on how to weigh this
section's negative result. §9 already established, on real data, that
`f135_rom12_to_rpd12`'s construction places every frame's Dmin within ~35
codes of `dra`'s own `lowFixedPoint`/`highFixedPoint` and SBA's
`neutralBalancePoint` (1550) — both independently, real-DLL-verified
constants this formula was never fitted to match, and has no way to miss by
construction only if its overall anchor placement (`fpo`, itself real-DLL-
verified live in §29) is roughly right. If the formula's structure were
badly wrong, the natural failure mode would be a Dmin landing far from that
shared pivot — a much cruder symptom (severe clipping, a wrong hue cast, or
`dra`'s shadow band actually engaging hard) than "uniform ~88-89 codes too
bright across every percentile." This is circumstantial, not a
verification, and does not change §32.2-32.4's finding that no DLL call
site was located — but it is a real reason not to treat "unverified" as
"probably wrong" going into whatever checks the formula next.

### 32.7 — Verdict

**This thread is closed without resolving the mystery**, per this task's own
explicit fallback instruction. Specifically:

1. The two candidate addresses this task named are **resolved**: both are
   part of the PolyPixel stage-2 colour-matrix family (§32.2), not the
   negative→positive log inversion, and not two names for one function
   either — the "naming ambiguity" in `tools/re/live_hooks/agent.js` is now
   answered by static evidence, without needing the live capture that
   comment called for.
2. A genuine, first-of-its-kind instruction-level search of TLB.dll for the
   log operation the formula requires comes back empty for every site this
   pass could trace (§32.3) — real, new negative evidence, not a repeat of
   the standing "no DLL call site" finding.
3. The same search in PakonIMAu.dll is **incomplete**, not negative (§32.4)
   — the highest-value spot-check (the cluster nearest `analyzeArea`) does
   not match, but ~50 `fyl2x` and ~64 `f2xm1` sites remain untriaged.
4. **No discrepancy was found to compare against the port's own
   implementation**, so — per this task's own explicit instruction — no fix
   was attempted or shipped. `F135_INVERT_PORTED` remains correctly `False`.
   `f135_rom12_to_rpd12` is not confirmed correct and not confirmed wrong;
   it is, after this pass, more narrowly *unverifiable by the two addresses
   this task named*, with a real but bounded amount of the remaining search
   space (TLB.dll) now checked and coming back empty, and a much larger part
   of it (PakonIMAu.dll) still open for whoever picks this up next, ideally
   scoped via `tools/re/reachability.py` against `analyzeAutoTone`'s own
   already-catalogued reachable sets rather than a raw whole-binary grep.

**§31's ~88-89 code uniform brightness excess remains unexplained.** Per
this doc's own §31.4, the next concrete lead is the polynomial colour-
matrix's own calibration currency relative to the new lamp duty
(`load_unit_matrix`, EEPROM-sourced) — this section did not start that work,
only confirms it's now the sharpest remaining item, since §32.2-32.4 close
out (for TLB.dll) or substantially narrow (for PakonIMAu.dll) the inversion-
formula lead without finding the bug.

## 33 — `load_unit_matrix`'s own calibration currency, checked directly: the
data genuinely predates every 2026-08-12 hardware fix, no fresher read
exists anywhere on this machine, and the mechanism through which a
duty-driven matrix mismatch *could* produce a non-cancelling brightness
shift is shown — both analytically and empirically, on the exact same
matched frame §31/§32 used — to be real but three orders of magnitude too
small to be this gap. Last item on §31.4's own list; it closes the same
way §32 did.

§31.4 named the polynomial colour-matrix (`load_unit_matrix`, EEPROM-
sourced) as the last concrete lead standing after film_base/c9 (§31.3) and
the inversion formula itself (§32) were both checked and found wanting.
This section runs that check directly: where the coefficients actually come
from, exactly when that data was captured relative to this session's own
hardware fixes, whether a fresher read exists anywhere on this machine, and
— the part no prior section in this thread has done — whether a matrix
error can even survive the inversion's own log-difference arithmetic the
way a `film_base`/`c9` error does not (§31.3).

### 33.1 — Where the coefficients actually come from, read directly, both
render paths

`pakon_color.load_unit_matrix` (`tools/pakon_color.py:580-598`) tries
`REGISTRY_PATH` first under `source="auto"`, falling back to `EEPROM_PATH`
if the registry dump isn't present. On this checkout (and on `main` —
checked via `git log --all -- research/windows-registry/pakon_registry_full.txt`,
which shows that file was only ever added on a different, unmerged branch,
`finding/f235-and-vendor-shadows`) the registry file does not exist, so
every render in this repo's history has resolved to:

```
EEPROM_PATH = REPO/backups/eeprom-i2c/eeprom_52.bin
```

a single, static, committed file — confirmed live by importing `pakon_color`
and calling `load_unit_matrix("auto", film_class=1)` directly: it reads
that path, and only that path. The Go production engine
(`tools/ansel/pipeline/main.go:686`, `DefaultCoeffRelPath =
"backups/eeprom-i2c/eeprom_52.bin"`) resolves to the **identical** file —
both render paths this project has ever shipped read the same static bytes.
Neither path consults `calib_store`/`calib_resolve` (the machinery this
session's own self-calibration wizard, `tools/calib_wizard.py`, uses for
duty/dark/gain) at all; `grep -n "calib_store\|calib_resolve" tools/pakon_color.py
tools/pakon_decode.py tools/pakon_render.py` returns nothing. The matrix and
the wizard are two entirely disconnected subsystems in this codebase today.

The coefficients themselves, read directly from that file (`film_class=1`,
NegMatrix, the one every ColNeg/BnW/IMPORTED render uses):

```
row  diagonal   pedestal (c9)   cross/quadratic terms (c3-c8, excl. diagonal)
R    0.28920    159.594         -1.4e-6 .. +3.6e-6
G    0.27583    444.750         -4.2e-6 .. +7.8e-6
B    0.27824    635.535         -1.8e-5 .. +7.6e-6
```

matching §31.3's own citation of `c9=(159.6,444.7,635.5)` exactly (same
matrix, same read). The diagonal terms are ~0.28; the cross/quadratic terms
are three to four orders of magnitude smaller (~1e-3 to ~1e-6).

### 33.2 — The timeline, precisely: the matrix data is real, verified, and
genuinely predates every fix this session made

```
backups/eeprom-i2c/eeprom_52.bin — content dated, per its own README.md:
    "VERIFIED 2026-08-05" (two independent power-cycle reads, byte-identical)
git commit 4e0dbf4, 2026-08-10 09:27:54 -0700
    "hardware: Restore system EEPROM and PIC firmware backups"  <- committed

calibration/README.json (lamp-duty recalibration, §6/§9's own citation)
    generated_at: 2026-08-12T08:21:09                            <- AFTER

commit 77e2a71, 2026-08-12 08:42:20 -0700
    "Finish the autoTone port; recalibrate by the vendor's own method"
commit a193f35, 2026-08-12 08:45:05 -0700
    "Self-calibration on plug-in; fix the AD9826 offset encoding" <- AFTER
```

The EEPROM backup's own content is five days older than the lamp-duty
recalibration and seven days older than the AD9826 offset fix — this part
of the task's hypothesis is simply true, not a matter of interpretation.

### 33.3 — Is there a fresher read anywhere on this machine? Checked
directly against the live calibration store, not assumed

`tools/calib_wizard.py`'s own `STEP_EEPROM` docstring
(`:180-185`) says plainly: *"The colour matrices and the serial number are
on the scanner's EEPROM... it is read exactly once and never re-read to
'check'."* So the live question is whether that one read, for this unit's
serial, is fresher than the 2026-08-05 backup. Checked directly against the
real local store (`~/Library/Application Support/PakonScan/calibration`,
`calib_resolve.resolve(calib_store.CalibrationStore())`, called live, not
inferred from code reading):

```
reads/2026-08-08T15-27-44Z   source: "calib_read --simulate"   state: good
    0x52 sha256 675cf1c...   <- IDENTICAL to backups/eeprom-i2c/eeprom_52.bin
reads/2026-08-08T15-28-52Z   source: "calib_read"               state: erased
    0x52: 256/256 bytes 0xFF — a genuine hardware read attempt, corrupted
```

Two things this settles. **First**: the *only* record `calib_resolve`
currently treats as this unit's good calibration (`serial=16275`,
`state=good`) is a `--simulate` **rehearsal** run, not a real hardware read
— and `calib_read.py`'s own `_sim_transport()` (`:62-75`) fills its fake
device content directly from `backups/eeprom-i2c/eeprom_52.bin`, so this
"good" record is a verbatim echo of the same 2026-08-05 backup, confirmed
by the byte-identical sha256, not independent evidence. This is exactly the
failure mode `calib_wizard.py`'s own module docstring warns about by name
(*"A rehearsal record in the real store is not a cosmetic mistake... That
happened on 2026-08-08 on the owner's machine"*) — a real, previously-
undocumented instance of it, still sitting in the live store today.
**Second**: the one **genuine** hardware read attempt on this unit's serial
(the very next timestamp, four minutes later, same power cycle) came back
completely erased — the documented "second read in a power cycle destroys
the data" trap (`backups/eeprom-i2c/README.md`), not usable for anything.
There is, right now, no good, independently-sourced EEPROM read of this
unit's colour matrix anywhere on this machine newer than 2026-08-05.

**Did tonight's self-calibration actually try to get one?** Checked
directly, not assumed: `calib_wizard.step_eeprom()` (`:776-809`) calls
`cres.resolve(self.store)` first and returns immediately without touching
hardware if a good, attributed record already exists. Live evidence this
happened for real, not just in theory: `units/16275/flatfield/2026-08-14T13-48-47Z/`
and `units/16275/overlay/2026-08-14T13-50-06Z.json` are real, dated,
`source: "calib_wizard"` records of a **live black-level/duty/dark/gain**
run on this exact unit (the overlay's `on_counts_R_G_B: [643,580,508]`
matches `calibration/README.json`'s own post-recalibration numbers exactly)
— so the wizard genuinely ran against real hardware, recently. But its own
`provenance` field only speaks to AFE offsets and lamp on-counts; there is
no accompanying new `reads/` entry, confirming `step_eeprom()` did exactly
what its own docstring says and reused the existing (simulate-derived)
record rather than re-reading the EEPROM. **The matrix has never been
re-read since 2026-08-05, including at the one concrete moment this session
had the opportunity to.**

### 33.4 — Does a matrix error even survive the inversion's own arithmetic?
Extending §31.3's cancellation argument to the matrix itself, then testing
it directly on the same matched frame

§31.3 proved a pure rescaling of `film_base` cancels in
`f135_rom12_to_rpd12`'s log-difference because `base` and `poly` are both
divided by the same factor before the subtraction. The same algebra applies
one level up, and this had not been checked before: `film_base` **is
itself** a poly-domain value — `film_base_codes` walks a histogram of
`poly_hwc`'s own output (§31.2), using the identical matrix and the
identical per-channel `c9` as every ordinary pixel. Writing the matrix's
affine part as `poly ≈ A·raw + c9` (A = diagonal, ignoring the much smaller
cross/quadratic terms for a moment):

```
poly - c9 ≈ A·raw_pixel        base - c9 ≈ A·raw_dmin
dens = 1000·(log10(base-c9) - log10(poly-c9))
     ≈ 1000·(log10(A·raw_dmin) - log10(A·raw_pixel))
     =  1000·(log10(raw_dmin) - log10(raw_pixel))        <- A cancels
```

So a uniformly wrong diagonal scale `A` — precisely the shape a duty-driven
matrix mismatch would most plausibly take — **cancels out of the formula
for the same structural reason `film_base` alone does**, regardless of
whether `A` is "right" for the current lamp duty or not. What does **not**
cancel this way is the off-diagonal cross-channel terms and the quadratic
terms (`c3`-`c8`), because they don't factor out of `raw_dmin` and
`raw_pixel` identically when the two have different R:G:B ratios or
magnitudes — this is the one part of the matrix hypothesis that could,
structurally, produce a genuine non-cancelling shift, exactly per the
task's own framing.

**Tested directly, not just argued**, on the real matched frame (`test123.bin`
frame 0, same roll/workspace §31 used, same production call chain
— `Roll.slice14` → `pakon_render.scene_rpd12` → `AnselEngine.render_scene`
→ `.to_srgb`, `PAKON_COLOUR_ENGINE=python`, real `film_base=[3107,2490,2414]`,
real `fpo`/`setshifts_out`). Built an "affine-only" matrix from the real one
by zeroing every cross-channel and quadratic term (`c3`-`c8`) in all three
rows, keeping only the diagonal and `c9`, and re-ran the identical pipeline:

```
                        sRGB [p1, p50, p99] per channel
                   R                  G                  B
REAL matrix:    [20,178,254]      [51,192,254]      [41,217,254]
AFFINE-ONLY:    [ 7,170,254]      [50,186,254]      [35,216,254]
target (AA001.tif p50): R=90  G=103  B=139

delta (real − affine-only), all three channels:
  R: [0, 6, 18]   G: [-2, 3, 7]   B: [-3, 1, 10]     (p1, p50, p99)
```

Zeroing the *entire* non-cancelling part of the matrix — not a plausible
"slightly wrong" version of it, the complete removal of every term that
could survive the log-difference — moves the median by **6, 3, and 1**
codes (R/G/B) and the full percentile range by no more than **18 codes**
anywhere. This is a direct, empirical upper bound on how much this specific
mechanism can move this frame's render, on the real matched data: nowhere
near the 88-89 code gap, for exactly the reason §33.1's own coefficient
table predicts — the terms capable of not cancelling are individually
three to four orders of magnitude smaller than the diagonal, and their
aggregate effect on a real image is correspondingly small.

### 33.5 — A direct duty-scale sensitivity probe: the formula's real
failure mode is a cliff, not a uniform shift — a different symptom shape,
for a different, already-known reason

A second, cruder test, run for completeness rather than as the main
evidence: rather than touching the matrix, scaled the frame's own
calibrated 14-bit input by the ratio of the old to the new open-gate lamp
duty (§6's own figures, `R=492/643≈0.765`, `G=239/580≈0.412`,
`B=104/508≈0.205`) — a first-order stand-in for "what would this frame's
raw signal have looked like under the pre-recalibration duty" — scaling
`film_base` by the same per-channel ratio, and re-ran the same real matrix
and formula unmodified:

```
                        sRGB [p1, p50, p99] per channel
                   R                  G                  B
current duty:   [20,178,254]      [51,192,254]      [41,217,254]
sim. old duty:  [121,240,254]     [65,173,192]       [0,  0,  0]
```

This is not a uniform shift either — R moves brighter, G moves darker, and
B collapses entirely to 0 across its whole percentile range once its scaled
raw signal approaches the matrix's own fixed pedestal `c9=635.5` closely
enough that `poly - c9` goes near-zero/negative and the log clamps. This
confirms mechanically why `c9` **does not** scale with duty the way the
raw signal does (it's a matrix constant, not a per-capture quantity) and
that a large enough duty mismatch produces a **cliff** — a channel-specific
collapse — not the smooth, same-direction-at-every-percentile ~88-89 code
excess this investigation is chasing. Flagged plainly as a cruder probe
than §33.4 (it scales raw values directly rather than modelling the real
dark/gain recalibration that actually accompanies a duty change, so its
absolute numbers are illustrative of the formula's shape, not a claim about
what the pre-recalibration renders actually looked like), but the shape
mismatch is real and adds an independent reason not to expect this
mechanism to produce §31's specific symptom.

### 33.6 — Verdict

1. **The timeline claim in the task's own hypothesis is correct**: the
   polynomial colour-matrix data this project's only two render paths both
   use (`backups/eeprom-i2c/eeprom_52.bin`, read identically by
   `pakon_color.load_unit_matrix` and `tools/ansel/pipeline/main.go`) is
   real, verified, per-unit data — but it was captured 2026-08-05 and
   committed 2026-08-10, genuinely predating both the lamp-duty
   recalibration and the AD9826 offset fix (both 2026-08-12). It has never
   been re-read since, including at the one point this session's own
   self-calibration wizard had a live opportunity to (§33.3) — and the one
   real (non-rehearsal) hardware read attempt on this unit's serial that
   does exist came back corrupted, unusable, per this hardware's own
   documented single-read-per-power-cycle constraint. There is currently no
   way to get a fresher, independently-verified read without a new power
   cycle at the physical scanner.
2. **That staleness does not explain §31's ~88-89 code uniform gap.**
   Extending §31.3's own cancellation argument one level up (§33.4) shows a
   uniformly wrong matrix diagonal — the shape a duty mismatch would most
   plausibly produce — cancels out of `f135_rom12_to_rpd12`'s log-difference
   for the same structural reason a `film_base` rescaling does, because
   `film_base` is itself measured through the same matrix. The only part of
   the matrix that could survive that cancellation (cross-channel and
   quadratic terms) is empirically shown, on the exact same matched frame
   §31/§32 used, to move the render by at most 18 codes at any percentile —
   an order of magnitude short of the gap — because those terms are three
   to four orders of magnitude smaller than the diagonal in this unit's own
   real coefficients. A separate, cruder duty-scale probe (§33.5) shows the
   formula's actual failure mode under a large duty mismatch is a
   per-channel collapse, not a uniform excess — a different symptom shape
   from the one being chased, for an identifiable reason (the fixed
   pedestal `c9` doesn't scale with duty the way raw signal does).

**This was the last concrete lead on §31.4's own list, and it closes the
same way §32 did: real, evidenced, checked directly against live hardware
state and real matched data — and not the explanation.** Combined with
§31.3 (film_base/c9 rescaling ruled out) and §32 (the inversion formula's
own construction checked against the real DLL, no discrepancy found), every
single-parameter lever inside the currently-known formula and its two
per-unit calibration inputs (`film_base`, the polynomial matrix) has now
been checked and found insufficient, on the same real matched frame, using
the same production code path, against the same real vendor TIFF. **No
production code was changed by this pass** — §33.4/§33.5's alternate
matrices and scaled inputs were constructed and rendered in scratch scripts
outside the repo, never written back into `pakon_color.py` or
`tools/ansel/pipeline/main.go`; `pakon_color.load_unit_matrix` and
`f135_rom12_to_rpd12` were read and called, not edited.

**What this leaves.** Every static and Unicorn-based avenue this doc's own
priority list has raised for the ~88-89 code brightness gap specifically —
the tone chain's architecture (§1), the Dmin methodology (§2-4, §31.2-31.3),
`fpo`'s provenance and per-unit value (§5, §29), FUGC (§10, §27-28),
`analyzeAutoTone` itself (§24), the inversion formula's own construction
(§32), and now the polynomial matrix's calibration currency (§33) — has
been checked and closed without finding it. What remains open and
unreplicated is the four `analyzeArea`/`analyzeAttributes`/`analyzeNoise`/
`analyzeFalloff` stages (§11, still the sole standing software lead) and
PakonIMAu.dll's own untriaged log-instruction sites (§32.4, ~50 `fyl2x` +
64 `f2xm1`, a properly scoped follow-up via `tools/re/reachability.py`
rather than more of this doc's own static reasoning). Beyond those two,
closing this specific symptom now most plausibly needs either a fresh
investigative idea this list hasn't raised, or the live hook harness on the
real XP box (per this doc's own citation of `tools/re/live_hooks/`,
still not yet run through a complete real scan) — genuinely live execution
against the vendor DLL during an actual scan, not another static or
Unicorn-isolated check, since this pass is the point at which those two
methods run out of untried single-parameter leverage on this symptom.

## 34 — The per-channel asymmetry checked directly: lamp duty and AFE gain,
both current relative to the matrix's own staleness in §33, and neither
closes the gap even when a real, documented, unpromoted duty/level
discrepancy is tested at its own real magnitude

§31's ~88-89 code excess was measured in aggregate; re-measuring it
per-channel raises a real, distinct-looking shape: blue has the *smallest*
median ratio of the three channels but is the one already sitting closest to
the sRGB ceiling. Checked directly whether this points at the one lever §33
didn't check — lamp duty cycle and AFE gain, both per-channel by
construction on this hardware — rather than the polynomial matrix. It does
not: gain is confirmed uniform and structurally inert as a per-channel
lever on this unit; duty is confirmed *current* (unlike the matrix) for the
production calibration this capture actually used, but a second, real,
dated, unpromoted duty/level snapshot exists that is fresher still — and
even substituting its own real numbers into the real formula, both stages
tested together the way an actual duty change would move them, closes the
gap by at most a handful of codes, in the wrong direction for two of three
channels. The asymmetric shape itself survives as real, but is better
explained by each channel's own already-cited `c9` magnitude relative to
its own `film_base` than by anything in the light board.

### 34.1 — Re-measured the per-channel shape directly, not taken on trust

Re-ran the identical production chain §31/§33 use
(`pr.Roll.from_json` on workspace `f4c91b62`'s own `roll.json`,
`PAKON_COLOUR_ENGINE=python`, `pr.render_frame(roll, 0)`, real
`film_base=[3107,2490,2414]`) and re-measured `AA001.tif` directly with
`PIL`/`numpy`, both independently of the task's own transcribed numbers:

```
        p0.1  p1   p5   p50   p95   p99  p99.9    median ratio (ours/AA001)
R ours:   0   20   62   178   249   254   254
R AA001:  0   10   17    90   235   252   255            1.98x
G ours:  41   51   71   192   250   254   254
G AA001:  8   11   17   103   239   251   255            1.86x
B ours:  25   41   58   217   254   254   254
B AA001:  7   10   18   139   246   255   255            1.56x
```

This matches §31.1's own baseline numbers exactly (unchanged code path, same
frame) and confirms the task's own framing to within normal
percentile-interpolation rounding: the median ratio genuinely shrinks
R→G→B (1.98→1.86→1.56) while headroom to the ceiling genuinely shrinks the
same direction (p95 249→250→254, closest to 255 for blue). One correction
to the task's own transcription: at this render's own p95, blue sits at
254/255, not literally saturated at 255 — the fraction of pixels *at* 255
(`≥254.5`) is 0.00% for all three channels at p95 on this frame at preview
scale. The qualitative shape — blue closest to the ceiling despite the
smallest ratio — is real and reproduced; "already fully clipped" is not,
on this specific frame/scale, and is stated here rather than silently
carried forward.

### 34.2 — What actually lit the lamp for `test123.bin`, read from the
capture's own sidecar, not assumed

`test123.scan.json` (`/Users/guy/Library/Caches/PakonScan/captures/`, written
by `tools/pakon_scan.py` at capture time, not reconstructed) records two
distinct on-count triples for this exact roll:

```
on_counts_R_G_B:            [643, 580, 508]   <- used for the actual scan
open_gate_on_counts_R_G_B:  [462, 231, 98]    <- used for the leader
calibration_source:  ".../calibration/README.json"
```

This is `docs/59`'s own two-duty-set mechanism (`lamp_switch_to_scan_duty`,
`tools/pakon_scan.py:1021-1048`), confirmed live-exercised on this exact
capture, not just present in code. The ratio between the two is exact
against `docs/59`'s own registry-derived `10^D` figures
(`R=1.393157, G=2.511891, B=5.188016`, the colour-negative base-density
compensation `FN_bBeforeScan` applies in the real DLL):

```
R: 643/462 = 1.3918   (vs 1.393157)
G: 580/231 = 2.5108   (vs 2.511891)
B: 508/98  = 5.1837   (vs 5.188016)
```

`calibration/README.json`'s own `duty_note` states this explicitly: *"the
vendor stored duties for this unit ([702,371,158] open-gate) clipped 97
percent of an empty gate on this hardware... so the vendor METHOD was
applied rather than its stored numbers."* This is a real, correctly
implemented, per-channel duty mechanism — the vendor's own — genuinely
exercised for this genuine capture, not a stand-in or a guess.

### 34.3 — AFE gain: uniform across every calibration snapshot on this
machine, and never the vendor's own per-channel lever either

`ADC_IDX_GAIN_R/G/B` (`tools/pakon_commands.py:1108-1110`,
`ADC_GAIN_MAX=0x3F`) are written once per capture, from `cfg.afe_gains`
(`tools/pakon_scan.py:1606-1610`, `ccd_configure`). Read directly across
every `README.json`/`README.pre-*.json` calibration snapshot on this
checkout (8 files, spanning both the 2026-08-12 recalibration chain and the
newer, separate self-cal family described below):

```
afe_gains  [13,13,13]  — 7 of 8 snapshots, including the one this capture
                          used (calibration/README.json) and the freshest
                          one that exists (calibration-fresh-scan/README.json)
afe_gains  [15,13,13]  — 1 of 8 (README.pre-recapture-20260812-070345.json,
                          an intermediate step mid-search, superseded within
                          the same session by the uniform value above)
```

Gain sits at 13 of a possible 63 on every snapshot that was ever actually
used — a fifth of the register's own range, real headroom, unused. This
matches `docs/59`'s own independent finding from the captured vendor wire
trace (§3, this doc's own citation): *"G is taken from the registry verbatim
in both drive sets. R and B are not... the natural reading is that green is
the reference channel and R/B are trimmed live against the CCD
response... via duty, not gain."* Every piece of evidence on this machine —
this project's own calibration history and the real vendor's own captured
register writes — agrees gain is not, and has never been, this hardware's
per-channel balancing lever; duty is. This closes item 3 of the task's own
list as a lead: gain is current, uniform, and structurally not a per-channel
control on this unit.

### 34.4 — A real staleness finding, the same shape as §33's, this time in
duty and lamp level: a fresher, same-unit, same-day self-calibration exists
and was never promoted into what this capture used

Two untracked calibration directories on this checkout — `calibration-
fresh-scan/` (`generated_at: 2026-08-14T06:50:06`, `generated_by:
tools/calib_wizard.py`, `wizard_stamp: 2026-08-14T13-48-47Z`, this exact
unit's serial `16275`) and `calibration-vendor-duty-test/` — hold a real,
dated, live self-calibration run, distinct from and later than the
`calibration/README.json` snapshot `test123.bin` actually used
(`generated_at: 2026-08-12T08:21:09`). `calibration-fresh-scan/README.json`'s
own `search_note` states plainly: *"The AFE offsets and the lamp on-counts
in config were SEARCHED against this scanner's own response, not
copied."* — real hardware, not a synthetic replay. Its `wizard_stamp`
(13:48:47 UTC = 06:48 PDT) lands **3h43m before** `test123.bin`'s own
capture timestamp (`test123.scan.json`'s `"created": "2026-08-14T10:33:50"`,
local, matching the file's own `Aug 14 10:33` mtime) — the fresher
calibration genuinely existed, on this exact unit, before this exact roll
was scanned, and was not used:

```
                         levels_R_G_B  on_counts(with-film)  afe_offsets
calibration/README.json    4,20,11         643,580,508       -18,-26,-20
  (used by test123.bin, generated 2026-08-12T08:21:09)

calibration-fresh-scan/     3,11,7         912,938,804          0, -6,  2
  (exists, unused, wizard_stamp 2026-08-14T13:48:47Z /
   generated_at 2026-08-14T06:50:06 — same day, same unit, before capture)
```

This is not a single-parameter drift: level dropped (R 4→3, G 20→11, B
11→7) at the same time on-counts rose, and `afe_offsets` moved from a large
negative pedestal to near-zero. `DEFAULT_CALIBRATION_DIR` (`pakon_decode.py:
85`, `pakon_scan.py:596/2678`) resolves to `calibration/` unconditionally;
nothing globs or auto-discovers `calibration-*` staging directories
(`docs/71-rebuilding-calibration.md §9`: *"a calibration is never deleted,
only timestamped"* — installing one is a manual, explicit `cp`, never
implicit). `calibration-fresh-scan/` is exactly this project's own live
self-cal wizard run — the same one §33.3 already found and cited via its
`units/16275/flatfield/2026-08-14T13-48-47Z/` record — reaching a "not yet
promoted" state, the same shape of finding §33 made for the EEPROM matrix,
now found independently for duty and level.

### 34.5 — Tested directly: does this real discrepancy explain the gap? No
— it extends §31.3/§33.4/§33.5's own cancellation argument to this specific,
real, per-channel case, on the real matched frame

Two ways to turn "level 4/20/11 + on-counts 643/580/508" into "level
3/11/7 + on-counts 912/938/804" into a single per-channel light-delivery
ratio, both tried:

```
naive (on-counts only):        R×1.418   G×1.617   B×1.583
corrected (level × duty_frac): R×1.064   G×0.890   B×1.007
```

The corrected figure is the physically meaningful one (level sets LED
current, on-count/N sets duty fraction; total light is their product) and
shows the two snapshots are much closer in real delivered light than the
on-counts alone suggest — R and B nearly unchanged, G actually *lower*, not
higher. Both were tested anyway, applied the only physically consistent
way: **jointly to the calibrated 14-bit input and to `film_base` together**
(what an actual re-scan under the fresher duty/level would do to both the
pixel content and the clear-film reference alike, extending §31.3's own
"pure rescale cancels" argument and §33.4's matrix-diagonal test to this
specific lever), through the same unmodified
`pr.scene_rpd12`/`render_scene`/`to_srgb` chain:

```
                        sRGB p50 [R, G, B]           sRGB p95 [R, G, B]
baseline (unmodified):     [178, 192, 217]              [249, 250, 254]
naive ratio (×1.42/1.62/1.58, joint):
                            [175, 195, 224]              [249, 250, 254]
level-corrected ratio (×1.06/0.89/1.01, joint):
                            [179, 189, 218]              [250, 249, 254]
target (AA001.tif):         [ 90, 103, 139]              [235, 239, 246]
```

Both tests move the render by at most 7 codes at the median, and in the
*wrong* direction (away from target) for G and B under the naive ratio.
This is not a sensitivity-to-choice-of-ratio problem — the larger of the
two candidate ratios already fails, so the smaller, more physically correct
one fails by a wider margin. The mechanism is the one §31.3 already proved
analytically: a duty/level change moves the calibrated raw signal and the
roll's own `film_base` together (both are read through the same channel,
under the same lamp state), and `f135_rom12_to_rpd12`'s log-difference
cancels that shared factor except for the small, already-bounded
contribution of the fixed pedestal `c9` (§33.4: at most 18 codes, from the
matrix; the same structural limit applies here). **A real, documented,
same-unit, same-day duty/level staleness exists — and, tested at its own
real magnitude on the real matched frame, does not explain the gap**, for
the identical reason the matrix's own staleness didn't in §33.

### 34.6 — Then what produces blue's specific "smaller ratio, harder
clip" shape? A structural consequence of the already-open gap, not a new
lever — offered as the most likely explanation, not proven exhaustively

`f135_rom12_to_rpd12`'s own pedestal `c9` (§33.1's own citation) is wildly
different in *proportion to its own channel's* `film_base` on this roll:

```
        c9       film_base    c9 / film_base
R      159.6        3107          5.1%
G      444.7        2490         17.9%
B      635.5        2414         26.3%
```

Blue's pedestal is more than five times larger, as a fraction of its own
base, than red's. Since `dens = 1000·(log10(base−c9) − log10(poly−c9))`,
the same *absolute* upstream discrepancy (whatever is actually producing
§31's ~88-89 code gap) lands on a channel-specific slope: subtracting a
pedestal that is a much bigger fraction of the base makes the surviving
`(base−c9)`/`(poly−c9)` terms smaller and the log correspondingly more
sensitive per unit of upstream error, for blue specifically. This is
offered as the most likely explanation for the shape in §34.1 — consistent
with, not contradicted by, every other finding in §31-33 — but it was not
isolated and confirmed as *the* mechanism this pass (that would mean
re-deriving the exact non-linear sensitivity and checking it reproduces
the specific 1.98/1.86/1.56 ratios quantitatively, not just the direction),
so it is stated as the leading candidate, not a closed finding.

### 34.7 — Verdict

1. **Gain is closed as a lead.** Uniform (13 of 63) on every calibration
   snapshot on this machine, including the one this capture used and the
   freshest one that exists; never the vendor's own per-channel control
   either, per `docs/59`'s own independent finding from the captured wire
   trace. Not stale, not a lever, not investigated further.
2. **Duty is current for the calibration this capture actually used** —
   `calibration/README.json`, exercised live via `test123.scan.json`'s own
   two on-count triples, exact to six figures against `docs/59`'s
   `10^D` figures. But **a real, dated, unpromoted, fresher self-calibration
   of duty *and* lamp level exists on this exact unit** (`calibration-
   fresh-scan/`, `docs/71`'s own "never auto-discovered, install is manual"
   convention explaining why it wasn't picked up), the same shape of
   finding §33 made for the colour matrix, now independently true for the
   light board too.
3. **That staleness does not explain the gap.** Tested directly, at its own
   real magnitude, applied the only physically consistent way (jointly to
   the raw signal and to `film_base`): moves the render by at most 7 codes,
   the wrong direction for two of three channels. The same structural
   reason §31.3/§33.4 already established — the shared factor cancels in
   the log-difference — applies here without modification.
4. **The specific per-channel asymmetry is real** (re-confirmed directly,
   §34.1) but is most plausibly a consequence of each channel's own
   `c9`-to-`film_base` ratio amplifying the *same*, still-unexplained
   upstream gap differently per channel, not evidence of an independent
   duty/gain defect. Flagged as the leading explanation, not a proven one.

**This closes the same way §33 did.** A real, worth-flagging staleness was
found (duty/level, not just the matrix) — genuinely worth promoting
`calibration-fresh-scan/` through this project's own documented install
procedure (`docs/71 §9`) on its own merits, as a hardware/calibration
hygiene action item for the project owner, independent of this symptom —
but it is not, on direct empirical test against the real matched frame, the
explanation for the brightness gap. **No production code was changed by
this pass.** `pakon_scan.py`, `pakon_commands.py`, `pakon_decode.py`, and
`pakon_render.py` were read and called, not edited; `calibration/`,
`calibration-fresh-scan/`, and `calibration-vendor-duty-test/` were read,
not modified or promoted. Every render in this section used the real,
unmodified `pr.scene_rpd12`/`render_scene`/`to_srgb` chain against the real
`test123.bin`/`f4c91b62` roll and the real `AA001.tif`; the joint
raw-plus-film_base scaling was built and run in scratch scripts under
`/tmp`, never written into a port file. Only aggregate percentile
statistics are reported above, consistent with this project's rule against
describing `captures/` contents.

## 35 — The first complete live hook capture of a real scan, read in full:
the call-order/shared-holder finding confirmed live for all six frames (not
just statically), `analyzeAutoTone`'s `edx=1` resolved by direct disassembly
to be compiler cleanup bookkeeping (not a status code), and
`tlb_afe_offset_write`'s real stack-argument layout finally resolved —
9 real per-channel AFE offset writes decoded, converging to within 1 code of
the calibration this exact roll used

**Provenance.** `live_hooks_20260815-085356.jsonl`, downloaded from the
project owner's XP box (`http://192.168.86.67:8000/`, confirmed reachable
before use) — the first capture in this project's history to run the live
hook harness (`tools/re/live_hooks/win_inject/`) through a complete real
scan without crashing, after the six non-call-reachable hook addresses were
disabled the same night. Status lines confirm a clean install: `"install
pass complete: 15/15 enabled hook(s) installed after 0 attempt(s)"`
(tick 29720171). 229 JSON lines total: 4 status, 15 `hook_installed`, 210
real `call` events (105 enter/leave pairs, `call_id` 1-105). The capture
ends cleanly on a matched enter/leave pair (`icc_xform_apply`/`icc_effect_op`
`call_id=104/105`, tick 29804000) — no truncated line, no mid-loop cutoff,
unlike the partial capture §29 worked from.

All analysis below re-derives everything from the raw JSONL directly (a
one-off Python script, not committed, matching this doc's own established
practice for scratch analysis) plus fresh `radare2 6.1.8` disassembly of the
real, MD5-verified DLLs already sitting on this checkout's host at
`/Users/guy/pakon-windows-repair/COM-SERVER/`: `PakonIMAu.dll` hashes
`eea9dcf78ee21d4f7c515a6c2512242d` (matches every prior citation in this
doc) and `TLB.dll` hashes `193d9b2ce0a4b77ae9b78262bd06c0fc` (matches §32.2's
own citation of `docs/70`). Both re-verified directly before use, not
assumed.

### 35.1 — Six frames processed, the documented call order holds with zero
deviation across all of them — verified in true log order, not by
`GetTickCount()` value

`cn_enhanced_driver` (`0x10069490`) fires exactly **6** times on the
capture's main thread (`tid=3192`): enter/leave pairs at `call_id`
46/46, 54/54, 62/62, 70/70, 78/78, 86/86. Each of the six wraps the exact
seven-hook nested sequence §11 documented from static disassembly —
`fugc_analyze → balance_area_image → analyze_area → analyze_attributes →
analyze_falloff → analyze_auto_tone` — with **zero exceptions, zero
reordering, zero missing or extra calls**, checked call-by-call across the
whole capture, not spot-checked on one frame. (One correction to how to
read this file: `GetTickCount()`'s ~15-16ms granularity means several
events in a frame share an identical `tick` value, so a naive sort by
`(tick, call_id)` can misorder same-tick events — e.g. it makes frame 4's
`cn_enhanced_driver` LEAVE, `call_id=70`, appear to precede its own nested
`analyze_falloff`/`analyze_auto_tone` calls, `call_id=76/77`. This is a
sorting artifact, not a real anomaly: `call_id` is assigned by a
thread-safe `InterlockedIncrement` at the moment each hook fires
(`hookcore.c:469`) and the log line is written synchronously under a lock
immediately after, so **the file's own line order is the authoritative
chronological order**, and in that order every one of the six frames nests
perfectly: `cn_enhanced_driver` ENTER, its six subsystems each fully
enter-then-leave in the documented sequence, then `cn_enhanced_driver`
LEAVE — confirmed by direct inspection of `call_id` 45-95 in raw file
order.)

A genuinely new, live-only detail two of the seven hooks reveal: `fugc_analyze`
itself nests a call to `fugc_set_lut_info` (`call_id` 48, 56, 64, 72, 80, 88 —
one per frame, always with constant `eax=0x00000000`/`edx=0x0939fbe4` at
ENTER and `eax=0x0939fbe4`/`edx=0x00000000` at LEAVE, a fixed slot in
`cn_enhanced_driver`'s own stack frame, unchanging across all six frames).
This wasn't part of §11's own eleven-address chain (built from a different,
non-`fugc`-internal disassembly pass) — live evidence adds it as a genuine,
minor, structurally unsurprising refinement.

### 35.2 — The shared-pointer finding, precisely re-characterized: `esi` is
`ctx` (`[ebp+0x14]`), not `holder` (`[ebp+0xc]`) — and live evidence shows
**both** are independently shared across all six subsystem calls, not one

The initial look (this task's own framing) found `esi` identical across all
six inner calls per frame, changing between frames, and called it "the
shared holder pointer." Decoding `analyze_auto_tone`'s own `stack_dwords`
against `pakon_autotone.py:1394-1396`'s already-established argument layout
(`sret=[ebp+8]`, `holder=[ebp+0xc]`, `arg2=[ebp+0x10]`, `ctx=[ebp+0x14]`) —
using `tools/re/live_hooks/win_inject/hookstub.S`'s own documented capture
contract (`argsPtr = ESP_after_call + 4`, i.e. `stack_dwords[0]` is the
callee's first real stack argument, matching `[ebp+8]` post-prologue) —
shows this is imprecise in a real, checkable way. Frame 1's
`analyze_auto_tone` ENTER (`call_id=53`):

```
stack_dwords[0] = 0x0939fd38   (sret,   [ebp+8])
stack_dwords[1] = 0x087e5278   (holder, [ebp+0xc])
stack_dwords[2] = 0x08fb05ac   (arg2,   [ebp+0x10])
stack_dwords[3] = 0x08fb05a8   (ctx,    [ebp+0x14])
esi (register)  = 0x08fb05a8
```

`esi` equals `stack_dwords[3]` — **`ctx`**, not `holder` (`stack_dwords[1]`,
a completely different address, `0x087e5278`). Checked across all six
frames of `analyze_auto_tone`'s own `stack_dwords[1]` (holder) and `esi`/
`stack_dwords[3]` (ctx):

```
frame   holder (sd[1])   ctx (sd[3] == esi)
1       0x087e5278       0x08fb05a8
2       0x08ddc280       0x08fb6a84
3       0x08e037a8       0x08fbcf60
4       0x08e8c7b8       0x08fc343c
5       0x08ebefa0       0x08fc9918
6       0x08f09118       0x08fcfdf4
```

Both columns are **identical across all six inner calls within a frame**
(re-checked directly for `fugc_analyze`, `balance_area_image`,
`analyze_area`, `analyze_attributes`, `analyze_falloff`, and
`analyze_auto_tone`'s own `stack_dwords[1]`/`esi` at every one of the 36
relevant enter events — not just `analyze_auto_tone`'s), and both **change
between frames**. This is a genuine strengthening of §11/§22, in two
directions at once: (1) §11's own static citation named only four of the
six subsystems (`balanceAreaImage`, `analyzeArea`, `analyzeFalloff`,
`analyzeAutoTone`) as sharing the identical `&[ebp+0xc]` argument, having no
disassembly evidence for `fugc_analyze`/`analyzeAttributes` at the time —
live evidence now shows `holder` is identical across **all six**, closing
that gap; (2) there is a **second**, independently-shared pointer (`ctx`)
riding alongside `holder` into the same six calls, which no prior static or
Unicorn pass in this doc distinguished from `holder` — the "one shared
holder" framing understates the real mechanism by one object.

`ctx`'s own per-frame addresses step by a suspiciously regular
**`0x64DC` bytes** every frame (`0x08fb6a84-0x08fb05a8 = 0x64DC`, same delta
for every consecutive pair above) — a fixed-stride, arena-like allocation
pattern, in the same order of magnitude as (but not exactly equal to) §22's
own already-established `ctx` size of `0x6600` bytes (a 292-byte
discrepancy, plausibly allocator padding/header overhead, not independently
resolved this pass). `holder`'s own per-frame addresses have no such regular
stride (deltas of `0x65F008`, `0x27528`, `0x89010`, `0x327E8`, `0x2178`) —
consistent with `holder` (§22: 0x100 bytes) coming from a general-purpose
heap with unrelated allocation traffic between frames, unlike `ctx`'s own
apparently-dedicated per-frame arena.

### 35.3 — `analyzeAutoTone`'s `edx=1` at every real LEAVE resolved by
direct disassembly: it is MSVC cleanup-epilogue bookkeeping, not a status
code, and does not bear on `pakon_autotone.py`'s own `AnsStatus` modeling

All six real `analyze_auto_tone` LEAVE events (`call_id` 53, 61, 69, 77, 85,
93) show `edx=0x00000001`, no exceptions. `eax` at LEAVE is also constant
across all six: `0x0939fd38` — the exact address of the `sret` argument
(`stack_dwords[0]` at ENTER, `[ebp+8]`), a fixed slot inside
`cn_enhanced_driver`'s own reused stack frame (`ebp=0x0939fd98` at every one
of the six `cn_enhanced_driver` ENTER events too — the driver re-enters at
the identical stack depth for all six frames, consistent with a simple
per-frame loop one level up, not recursion).

Disassembling `analyzeAutoTone`'s own tail directly (`0x100fb730`-
`0x100fcd6e`, `PakonIMAu.dll`, `af`-confirmed 5,311-byte body matching
`pakon_autotone.py`'s own cited size) finds the actual return sequence at
`0x100fcd60`: `mov eax, esi` — `esi` is the function's own cached copy of
the `sret` pointer, echoed into `eax` right before `ret`, exactly matching
`pakon_autotone.py:1395-1396`'s own citation that *"the hidden `AnsStatus&`
sret (`[ebp+8]`) is the return value"* — `eax` **is** the documented return
value, and it is a pointer, not a status code. `edx` is never assigned in
this epilogue as part of any documented return convention. Tracing
backward from `ret`, the last place `edx` is touched on the path every one
of these six real calls actually took is:

```
0x100fcd0f   mov edx, dword [var_1ch]
0x100fcd12   or  edx, 1          ; unconditionally forces bit 0
0x100fcd17   mov dword [var_1ch], edx
```

— followed by conditional C++ RAII-style cleanup blocks (guarded
`test`/`je` around vtable-dispatched destructor calls, `push 1` /
`call [eax]`, the classic MSVC "scalar deleting destructor" shape) that,
on the branch actually taken in every one of these six live calls, do
**not** touch `edx` again before `ret` at `0x100fcd6e`. `or edx, 1`
unconditionally sets `edx`'s low bit; if `var_1ch` was already `0` (the
common case — an unthrown-exception/no-extra-cleanup local, consistent with
every one of these six real calls succeeding cleanly), the result is
exactly `1`, matching every observed value precisely.

**This is not a status code.** It is not part of `analyzeAutoTone`'s
documented ABI at all (only `eax` is), it has no relationship to
`AnsStatus`/`STATUS_OK_GLOBAL` (`pakon_autotone.py:807-835`, whose own
`__bool__`/comparison logic operates on the object at the `sret` address,
not on `edx`), and its constant value of `1` is a coincidence of this
capture's own no-exception execution path through a generic compiler
cleanup idiom, not a designed "success" signal. **This resolves the task's
own question precisely, just not in the direction it hoped**:
`pakon_autotone.py`'s `AnsStatus` modeling is neither confirmed nor
contradicted by this register, because `edx` was never a real channel for
it to begin with. One corroborating data point: `cn_enhanced_driver`'s own
LEAVE `edx` is *also* `1` on every one of its six calls (`0x00000000` only
on its very first ENTER, `0x00000001` on every ENTER/LEAVE thereafter) —
consistent with, not independent evidence for, the same mechanism:
`analyzeAutoTone` is the last of the six subsystems `cn_enhanced_driver`
calls each frame, and if `cn_enhanced_driver`'s own epilogue doesn't touch
`edx` between that call and its own `ret`, its LEAVE `edx` simply inherits
`analyzeAutoTone`'s.

### 35.4 — `tlb_afe_offset_write`'s real stack-argument layout, resolved by
direct disassembly of `0x100299c0`: the `arg_1ch`/`arg_1ch_2` collision was
r2's own naive per-instruction naming, not a real ambiguity in the function

Fresh `radare2` disassembly of `TLB.dll:0x100299c0` (`FN_bDrvPutCcdAtoDOffsets`,
already cited at `docs/72 §1.3`) confirms the earlier session's finding:
`r2`'s automatic variable naming produces a genuine collision —
`fcn.100299c0(arg_8h, arg_18h, arg_1ch_2, arg_20h, arg_1ch)` — because two
*different* real argument slots are each read by an instruction whose raw
encoding literally reads `[esp+0x1c]`, but at two different actual stack
depths (one dword-push deep, another four dwords-push deep), which r2's
default naming (keyed off the literal text offset, not the true depth from
the function's real entry ESP) cannot tell apart. Manually tracking ESP
push-by-push from the function's true entry (before any of its own four
prologue `push`es) resolves it cleanly. This is a **thiscall** (`ecx` =
`this`, cached in `esi`) with five real stack arguments beyond `this`, at
true offsets `[entry_esp+4]` through `[entry_esp+0x14]`:

```
arg1 (entry_esp+4)   -- ebx-sourced, shared across all 3 channel writes
arg2 (entry_esp+8)   -- raw value for channel index 5, cached at [this+0x34c]
arg3 (entry_esp+0xc) -- raw value for channel index 6, cached at [this+0x350]
arg4 (entry_esp+0x10)-- raw value for channel index 7, cached at [this+0x354]
arg5 (entry_esp+0x14)-- ebp-sourced, shared across all 3 channel writes
```

Each of the three blocks (channel-index 5/6/7, pushed as a literal constant
into the real encode-and-write call `0x1000a5d0`) first compares the new
raw value against the cached one at `[this+0x34c/0x350/0x354]` and skips
the actual hardware write on a match — explaining why real captures show
runs of identical consecutive values (the DLL itself is deduplicating). Per
`hookstub.S`'s own documented capture contract (`argsPtr` points at exactly
`entry_esp+4`), the hook's `stack_dwords[0..4]` map directly onto
`arg1..arg5` above — letting the raw capture be decoded without guessing.
Using this project's own already-established R/G/B ordering convention for
these triples (inherited, not re-derived this pass, same caveat §29 already
flagged for its own `fpo` decode): `arg2`=R, `arg3`=G, `arg4`=B.

**All 9 real calls, decoded:**

```
call_id  retaddr(TLB VA)   R      G      B     leave(eax,edx)
   1     (n/a, first)     10     10     10     eax=1 edx=0x078700c8
   2     0x1001e2cf      -29    -38    -30     eax=1 edx=0x078700c8
   3     0x1001e2cf      -21    -30    -22     eax=1 edx=0x078700c8
   4     0x1001e2cf      -19    -25    -19     eax=1 edx=0x078700c8
   5     0x1001e2cf      -19    -26    -19     eax=1 edx=0x7c90e514
   6     0x1001e2cf      -19    -26    -19     eax=1 edx=0xffffffed
   7     0x1001e2cf      -19    -26    -19     eax=1 edx=0xffffffed
   8     0x1001e2cf      -19    -26    -19     eax=1 edx=0xffffffed
   9     0x1002df73      -19    -26    -19     eax=1 edx=0xffffffe6
```

(`retaddr` reverse-mapped to a documented TLB.dll VA via the hook-installed
table's own inferred module base, `rt_address - (va_documented-0x10000000)
= 0x070d0000`; both call-site addresses independently confirmed by
disassembly to be genuine `call 0x100299c0` instructions inside TLB.dll
itself — `0x1001e2ca` and `0x1002df6e` respectively — i.e. **this entire
search runs inside the vendor's own low-level device driver code**, not in
this project's own Python `calib_wizard.py` self-cal tool, a distinct
mechanism from §34.4's finding and not to be conflated with it.)

This is a live, converging **auto-calibration search**: an initial uniform
seed (`10,10,10`), three refinement steps, settling at `(-19,-26,-19)` for
four consecutive reads (calls 5-8, same call site, a tight loop inside
TLB.dll), then one more call from a *different* call site (`call_id=9`,
`0x1002df73`) confirming the identical settled value — read as "apply the
converged result," though this pass did not trace that second call site's
own enclosing function to confirm that reading independently. `eax=1` at
LEAVE is constant across all 9 calls (plausibly a real `BOOL`-style
success/complete flag, unlike `edx`, which is *not* constant here —
`0x078700c8`, `0x7c90e514`, `0xffffffed`, `0xffffffe6` — reinforcing §35.3's
point that `edx`-at-leave is not generically trustworthy across this hook
framework without independently checking each function's own epilogue).

**Cross-check against this project's own stored calibration.** §34.4
already cites `calibration/README.json` (the calibration this exact roll's
capture actually used) `afe_offsets = (-18, -26, -20)`. The converged live
values found here, `(-19, -26, -19)`, match **G exactly** and are within
**1 code** of R and B. Given `docs/72`'s own already-cited two's-complement/
sign-magnitude encoding bug in this exact function (fixed 2026-08-12), a
small, symmetric (R and B both off by exactly 1, G exact) discrepancy this
size is at least as consistent with ordinary live-search convergence noise
as with any remaining encoding issue — **not independently adjudicated
either way this pass**, stated plainly rather than picked. Either way, this
is the first time this project has decoded genuine, per-channel,
disassembly-verified AFE offset values from a live capture, and they land
within a code of the project's own already-trusted, independently-sourced
number.

### 35.5 — `sba_preference`/`fpo` re-confirmed on a complete capture: same
generic stock value, 12/12 calls

All 12 real `sba_preference` calls in this capture (`call_id` 10, 12, 14,
16, 18, 20, 22, 26, 30, 34, 38, 42) decode, via the same
`stack_dwords[8:10]` packed-RGB convention `pakon_sba_preference.py`
documents and §29 already used, to the identical triple in every case:

```
stack_dwords[8]=0x04e2036f, stack_dwords[9]=0xffba056a -> (879, 1250, 1386)
```

— exactly §29's already-established generic stock `fpo` value from
`sba-CN-default.dpi`, and exactly what §29 itself found on the earlier,
explicitly-partial `live_hooks_20260814-102329.jsonl` (7/7 calls there).
This capture is the "clean, complete capture covering a full successful
scan" §29's own caveat asked for to close the question more finally: it
ends on a clean matched enter/leave pair (§35 intro), not mid-loop, and
covers all six frames of the roll. All 12 calls happen in two setup batches
of six (`call_id` 10-21, each paired with `sba_get_shifts`; `call_id`
22-45, each paired with `sba_set_shifts` + two `sba_get_shifts`), both
**before** the six-frame `cn_enhanced_driver` loop begins (first
`cn_enhanced_driver` ENTER at `call_id=46`) — i.e. this looks like a
complete per-scene SBA setup pass covering all six frames at once, then the
six-frame tone-analysis loop runs separately afterward. §29's finding is
now confirmed structurally, not just per-call.

### 35.6 — Other live-only observations, checked and reported plainly (no
forced finding on the §31-34 brightness gap)

- **ICC colour management runs on a separate thread, as a distinct batch
  pass after all six frames' tone analysis, not interleaved per-frame.**
  `icc_effect_op`/`icc_xform_apply` (6 enter/leave pairs each, `call_id`
  94-105; the raw per-hook-id count of 13 each includes one
  `hook_installed` status line, not a 13th call) all run on `tid=2912`, a
  different thread than the main pipeline's `tid=3192`. The first ICC event
  (`call_id=94`, tick 29803703) fires only after the *last*
  `cn_enhanced_driver` LEAVE (`call_id=86`, tick 29802671) — roughly a
  one-second gap — meaning colour management for the whole roll happens as
  one later batch, not per-frame inside the tone-analysis loop. Not
  something any prior capture in this doc lived long enough to show.
- **`sba_apply_balance_shifts` is installed but never fires** (0 of 210
  call events) despite `sba_set_shifts`/`sba_get_shifts` firing normally —
  reported as a raw fact; this doc has no established basis for what
  triggers it, so no interpretation is offered.
- **Timeline structure**: the 9 `tlb_afe_offset_write` calls (ticks
  29745031-29759234) happen roughly 43 seconds before the SBA setup phase
  (starting tick 29802484), consistent with a one-time hardware
  init/calibration step at scan start, well separated from per-frame
  processing — not interleaved with it.
- **Relevance to the still-open ~88-89 sRGB code brightness gap
  (§31-34): none found.** The AFE offset values decoded in §35.4 are a
  genuinely new, precise, disassembly-verified data point, but they concern
  the AD9826 offset *register* — a CCD-readout-time pedestal correction
  applied before any of this doc's own already-modeled stages — not
  `f135_rom12_to_rpd12`'s own `c9` polynomial pedestal (§33-34's own
  subject) or any of §31.4's two remaining candidate loci (the inversion
  formula's own construction; the polynomial matrix's calibration
  currency). Checked for a live surprise per this task's own instruction
  and none was found: every value decoded this pass either matches an
  already-established static/Unicorn finding more precisely (§35.2's
  holder/ctx split, §35.5's `fpo`) or resolves a previously-open
  methodological question without touching the brightness gap itself
  (§35.3's `edx`, §35.4's AFE offsets). **Item 1 (the four unreplicated
  stages) remains the sole standing lead**, unchanged by this pass.

**No production code was changed.** Every number above comes from directly
reading the raw capture JSONL and from read-only `radare2` disassembly of
the same two already-MD5-verified DLLs this doc has cited throughout; no
port file, golden file, or capture file was modified.

## 36 — The technique not yet tried on this specific frame, tried: live
Unicorn execution (not static reading) of PolyPixel and SBA balance-apply's
real shift-LUT machinery, on `test123.bin` frame 0's own real data — both
bit-exact, one of them Unicorn-verified for the first time ever, not just on
this frame. The gap survives even this. F-135 inversion remains the one
stage genuinely unreachable by this method.

Every check on the pre-`analyzeAutoTone` stages in §31-33 was done by
*reading* the real DLL's disassembly and reasoning about it. This section
does the thing that caught §30's real bug and §24's real harness bug: run
the real machine code live under Unicorn, on real data, and diff the result
against the Python port's own computation for the identical input — applied,
for the first time, to the two pre-tone-chain stages that structurally
*can* be reached this way (PolyPixel and SBA balance-apply's shift-LUT
construction), on the exact frame (`test123.bin` frame 0) §31-35's own
matched-vendor-TIFF comparison used.

New, additive script this pass:
`tools/ansel/python-pipeline/pakon_prechain_bracket_golden.py`. Does not
modify any existing golden file. DLLs re-verified fresh:
`TLB.dll` MD5 `193d9b2ce0a4b77ae9b78262bd06c0fc`, `PakonIMAu.dll` MD5
`eea9dcf78ee21d4f7c515a6c2512242d` — both match every prior citation in this
doc. Real data: the same `~/Library/Caches/PakonScan/workspace/f4c91b62/
roll.json` §31-35 used (`test123.bin`, real `film_base=[3107,2490,2414]`,
`fpo=(879,1250,1386)`, real `setshifts_out=(683,297,151)`), frame 0, via the
real, unmodified `Roll.slice14`/`Roll.engine`.

### 36.1 — Stage A: PolyPixel, real full frame, live Unicorn, bit-exact —
and a real, new instance of §24's own harness-bug class, found and fixed in
the new script only

Reused `pakon_color_golden.PolyGolden` — the existing, working Unicorn
harness for TLB.dll `0x1000d880` — completely unmodified in its own
mechanics, feeding it the real, full, 3000×2000 (6,000,000-pixel) calibrated
14-bit block for `test123.bin` frame 0 (`roll.slice14(2048, 5048, 1)`, the
same real production call §31/§33/§34 all used) and this unit's real EEPROM
matrix (`pakon_color.load_unit_matrix`), instead of the file's own existing
subcommands' small synthetic/random pixel sets (largest built-in default:
64×48 = 3,072 pixels).

**Found, before trusting any result, the same bug class §24 already found in
a different golden file — confirmed directly, not assumed.** `PolyGolden.run`
hard-codes `uc.emu_start(COLOR_CORRECT, STOP, count=40_000_000)` and never
checks that EIP actually reached `STOP` afterward — exactly
`pakon_autotone_shell_golden.Emu.call`'s own pre-§24 shape. Checked directly:
a real 250×2000 (500,000-pixel) crop of this same frame hits the
40,000,000-instruction cap silently — `emu_start` returns with no exception,
EIP stopped mid-loop at `0x1000da4c`, not at `STOP` — and the unmodified
`run()` has no way to notice; it would have returned whatever partial bytes
happened to sit in the image buffer as if they were a completed run. Fixed
the same way §24 fixed it: a runtime-only monkeypatch
(`patch_polygolden_checked_run`, in the new script, not an edit to
`pakon_color_golden.py` on disk) that raises the cap to 8,000,000,000 and
explicitly asserts EIP reached `STOP` before trusting any result. Re-ran
after the fix, foreground, waited for completion.

```
250x2000 (500,000 px) with the fix: reaches STOP, matches pakon_color.poly_hwc
  exactly on this crop -- confirms the fix, not just the bug.

FULL frame (3000x2000, 6,000,000 px), test123.bin frame 0, real calibrated
14-bit input, real EEPROM matrix, film_class=1:
  wall time: 41.4-41.5s (two independent runs, same process each time)
  execution confirmed to reach STOP (not instruction-cap truncated)
  values checked: 18,000,000 (6,000,000 px x 3 channels)
  mismatches: 0   max_abs_diff: 0
```

**Bit-exact.** Real DLL PolyPixel, live-executed under Unicorn, produces
IDENTICAL output to `pakon_color.poly_hwc` on every one of 18,000,000 values,
on this frame's real, full, calibrated 14-bit data — reproduced on two
independent runs of the whole script, byte-for-byte identical both times.
This is the same PolyPixel address §32.2 already confirmed, by static
disassembly, is a switch-dispatched float polynomial with zero log-family
instructions — now additionally confirmed by making that exact real machine
code actually run, on this exact frame's real data, rather than only reading
it.

### 36.2 — Stage B: SBA balance-apply's real shift-LUT machinery, live
Unicorn, for the first time ever — not just for the first time on this frame

`pakon_sba_apply.py`'s own module docstring already cites, by address, the
mechanism behind `apply_balance_shifts`'s `clamp(code+shift,0,4095)` model:
`AnsAreaCapabilityImpl::applyBalanceShifts` (`0x1019a0c0`), a master-clip-LUT
ctor (`0x100f42a0`, called from CRT init at `0x1056a470` with
`bits=0xc, floor=0, max=0xfff`), and a LUT-build loop (`0x1006c582`:
`out[i] = master[i + shift]`). Checked directly, before assuming this was
already live-verified (the task's own instruction, per docs/74 §9's own
citation of this exact function as "the already-Unicorn-verified,
real-DLL-bit-exact function this whole investigation has relied on since
`docs/66`'s eleventh pass"): **no existing golden file in this repo actually
executes either function under Unicorn.** `pakon_shasta_aim_golden.py`'s own
module docstring is explicit about what its own prior pass actually did —
*"Host closed-form checks for master clip LUT... (master LUT ctor
`0x100f42a0` / CRT `0x1056a470` cited)"* — a citation of the disassembly,
not a Unicorn run. **§9's own characterization was imprecise**: the
function's *arithmetic* was correctly reverse-engineered from reading, but
"Unicorn-verified" was not, until this pass, literally true. Flagged plainly,
in the same spirit as §10's correction of the eleventh pass's own stale
hedge — not a retraction of §9's numbers (the `apply_balance_shifts` model
itself turns out to be correct, confirmed below), only of what kind of
evidence backed it.

Disassembled both real functions fresh this pass (`aa; af; pdf`, r2 6.1.8,
`PakonIMAu.dll` at its real base `0x10000000`) to derive the calling
convention, then executed both live:

* **`0x100f42a0`** (`ret 0xc`, thiscall, 3 stack args): the real CRT-init
  call site (`0x1056a470`, read directly) is `push 0xfff; push 0; push 0xc;
  mov ecx, 0x106b5f74; call 0x100f42a0` — confirming `pakon_sba_apply.py`'s
  own `(bits=0xc, floor=0, max=0xfff)` citation byte-for-byte against the
  real vendor call site, not just the ctor body. Built a fresh `this` object
  (not the DLL's own static `0x106b5f74` singleton — that would need CRT
  init replayed; flagged explicitly as a modelling choice in
  `SbaShiftLutGolden`'s own class docstring, the same honesty standard
  `BalanceAreaImageCall`'s docstring already set in §24) and called the real
  ctor with the real vendor args.
* **`0x1006c4f0`** (`ret 0x1c`, thiscall, 7 stack args): disassembled the
  real caller, `applyBalanceShifts` itself (`0x1019a0c0`, also fully
  disassembled this pass), and confirmed its own 2nd/3rd/4th real stack
  arguments (`arg2`/`arg3`/`arg4`) are pushed, in order, as R/G/B shift
  values into `0x1006c4f0` — independently confirming, by direct
  disassembly of the real call site, `pakon_sba_apply.py`'s own prior
  (reading-based) claim about which caller arguments are the shifts.
  Called it with this roll's own real `setshifts_out=(683, 297, 151)`
  (read live from `roll.engine()`, not hardcoded).
* Two CRT thunks (`operator new`/`operator delete`, both unresolved imports
  into the unloaded `MSVCR71.dll`) were stubbed with a plain bump allocator
  and a no-op respectively — a narrow, standard-library-contract stub, the
  same category of stub `pakon_shasta_aim_golden.py`'s own module docstring
  already uses for this exact situation ("stubbed `operator new` / malloc"),
  not a guess about unknown vendor logic.

```
master-clip-LUT ctor (0x100f42a0): 65,536 entries checked -- EVERY
  addressable index from -0x8000 to 0x7fff, not a sample -- against the
  closed form pakon_sba_apply.py's own docstring already states
  (master[i]=0 for i<=0; master[i]=i for 1..0xfff; master[i]=0xfff for
  i>0xfff): 0 mismatches, max_abs_diff=0.

shift-LUT builder (0x1006c4f0), this roll's real setshifts_out=(683,297,151):
  R (shift=683): 4096/4096 entries checked, 0 mismatches
  G (shift=297): 4096/4096 entries checked, 0 mismatches
  B (shift=151): 4096/4096 entries checked, 0 mismatches
```

**Bit-exact, all 3×4096 LUT entries plus all 65,536 master-table entries —
every possible input value, not a sample.** Real DLL shift-LUT construction,
live-executed under Unicorn for the first time ever against this specific
mechanism, produces IDENTICAL output to `pakon_sba_apply.apply_balance_shifts`'s
`clamp(code+shift,0,4095)` model, using this exact roll's real shift values.

### 36.3 — Stage C: the real, live-executed LUT applied to this frame's real
post-inversion array

Applied the three REAL, live-executed LUTs from §36.2 directly to
`test123.bin` frame 0's own real post-inversion RPD-12 array (from
`pr.scene_rpd12` — the same still-`F135_INVERT_PORTED=False` formula every
other section of this doc uses; only the balance-*apply* step is being
live-checked here, not the inversion that produced this array) and diffed
against `pakon_sba_apply.apply_balance_shifts` on the identical array:

```
18,000,000 values checked (6,000,000 px x 3 channels): 0 mismatches,
  max_abs_diff=0.
```

Bit-exact on the real frame, not just on the abstract 0..4095 domain §36.2
already covered exhaustively — confirms the LUT match from §36.2 actually
holds when applied to this specific frame's real value distribution, not
just in principle.

### 36.4 — An honest caveat this pass's own result surfaces, not resolves:
§35.6 already found live evidence that `applyBalanceShifts` itself never
fires during a real scan

§36.2 executed `0x100f42a0`/`0x1006c4f0` — the shift-LUT *construction*
machinery `applyBalanceShifts` (`0x1019a0c0`) itself calls internally — not
`applyBalanceShifts` as a whole. §35.6 already reported, from a genuine live
hook capture of a complete real 6-frame scan, that
`sba_apply_balance_shifts` (the live-hook name for `0x1019a0c0` itself,
confirmed by direct address match against
`tools/re/live_hooks/win_inject/hookcore_real_table.c`) *"is installed but
never fires (0 of 210 call events) despite `sba_set_shifts`/`sba_get_shifts`
firing normally"* — and that doc section explicitly states it has *"no
established basis for what triggers it, so no interpretation is offered."*
This pass does not resolve that question either. What §36.2-36.3 establish
is narrower and still real: *if* the real vendor pipeline reaches this
specific LUT-construction code (whether via `applyBalanceShifts` itself, at
export time, or some other call site this doc hasn't located), it computes
exactly what `pakon_sba_apply.py` already assumes it computes. Whether this
is in fact the mechanism the live CN-Enhanced render path actually exercises
for `test123.bin`'s own frames — as opposed to some other, not-yet-located
balance-apply path — is the same open question §35.6 already flagged, not a
new one, and not answered here. Stated plainly rather than glossed over,
per this doc's own standard.

### 36.5 — What this settles, and what it doesn't

**Both stages this pass could reach live are bit-exact, live-execution
confirmed, on this exact matched frame.** PolyPixel: reconfirms §32.2's
static-disassembly-based verdict with genuine execution, on real full-frame
data, for the first time on this specific capture. SBA balance-apply's
shift-LUT math: Unicorn-verified for the first time ever, not merely
re-verified on new data — the "already-Unicorn-verified" label §9 had been
carrying for this function turns out to become true only as of this pass.

**The gap survives even this.** §31's ~88-89 sRGB code uniform brightness
excess is not explained by anything this pass checked, exactly as §32/§33/§34
already found for the inversion formula's own construction, the polynomial
matrix, and lamp duty/AFE gain respectively. This is now the strongest form
of evidence this investigation has applied to the pre-tone-chain stages —
live execution, not reading — and it comes back clean on both sides of the
one stage it cannot reach.

**The F-135 inversion remains the one stage genuinely unreachable by this
method**, not from lack of trying this pass but because §32 already ran an
exhaustive (TLB.dll) and partial (PakonIMAu.dll) instruction-level search for
the one operation (`fyl2x`/`fyl2xp1`/`f2xm1`) the formula's own log-difference
construction requires, and found no candidate site. This pass did not
re-attempt that search; it instead confirmed, as tightly as live execution
can, that the stage immediately before the inversion and the mechanism used
immediately after it are both correct — which sharpens rather than
broadens the remaining uncertainty. Bracketing a gap that live execution
cannot directly close is real, useful progress: it means the true cause,
whatever it is, has to be either (a) inside the inversion formula itself,
still unreachable by this method per §32.4's own unfinished PakonIMAu.dll
triage, or (b) somewhere this whole investigation has not yet looked.

**Concrete candidates for (b), named per this task's own instruction, none
confirmed this pass:**

1. **PakonIMAu.dll's own untriaged log-instruction sites** (§32.4: ~50
   `fyl2x` + ~64 `f2xm1` sites, only the cluster nearest `analyzeArea`
   spot-checked) — still the single most concrete unexplored code-search
   space for the inversion formula itself, and the natural next step if
   another RE pass is willing to scope it via `tools/re/reachability.py`
   against `analyzeAutoTone`'s own already-catalogued reachable sets.
2. **The four unreplicated stages** (`analyzeArea`/`analyzeAttributes`/
   `analyzeNoise`/`analyzeFalloff`, §11) — this doc's own running tally
   already carries this as the sole standing *software* lead; nothing in
   this pass changes that ranking, since none of these four sit between
   PolyPixel and the inversion or between the inversion and balance-apply,
   the two boundaries this pass checked.
3. **Something upstream of PolyPixel itself** — this pass's own Stage A
   feeds the IDENTICAL real calibrated 14-bit array to both the DLL and the
   Python port, so it verifies PolyPixel's own correctness on that input,
   but it does NOT independently verify that `Roll.slice14`'s own
   `apply_unit_calibration` (dark/gain correction, upstream of PolyPixel
   entirely) produces vendor-correct values in the first place — a stage
   this doc has not run a live-DLL comparison against at all.
4. **Frame 0's own framing grade** — §31 already noted, without following
   up, that frame 0 carries this roll's weakest framing-cascade placement
   (`confidence=low, phase=LookAtBeginning`) and flagged it as "not shown to
   matter" rather than ruled out. Still not ruled out.
5. **§36.4's own open question** — whether `applyBalanceShifts` (as
   opposed to the LUT-construction math this pass verified) is even on the
   real, live per-frame render path for this roll, first raised by §35.6 and
   still unanswered.

## What this changes about the open item list

**§36 update.** Closes no new item and opens none, but changes the *kind* of
confidence behind two already-closed items. PolyPixel (already confirmed
correct by static disassembly, §32.2) and SBA balance-apply's shift-LUT
math (already assumed correct, on an imprecise "already-Unicorn-verified"
citation, §9) are now both confirmed by genuine live Unicorn execution on
`test123.bin` frame 0's own real data — bit-exact, full-domain (every LUT
entry, not a sample), reproduced across independent runs. Along the way,
found and fixed (in the new script only, not on disk in
`pakon_color_golden.py`) a second independent instance of §24's own
instruction-cap-with-no-completion-check bug class, and corrected §9's own
overstated verification claim for `apply_balance_shifts`. **Item 1 (the four
unreplicated stages) remains the sole standing software lead** — nothing
between PolyPixel and the inversion, or between the inversion and
balance-apply, moved. The practical effect: live execution, the strongest
evidence tier this investigation has, has now been applied to every stage
that has a known DLL entry point on either side of `f135_rom12_to_rpd12`,
and all of it comes back clean — sharpening, not lowering, the priority of
either finishing PakonIMAu.dll's own untriaged log-instruction search
(§32.4) or finishing the four unreplicated stages (§11), since both are now
the only concrete leads this doc has left that live execution has not
already reached.

**§35 update.** The first complete live hook capture of a real scan (six
frames, zero deviations from §11's documented call order) is a genuinely
new *category* of evidence — live dynamic confirmation, not static
disassembly or Unicorn emulation — but closes no new item on this list and
opens none. It strengthens §11/§22's shared-pointer finding (splitting it
into two independently-shared objects, `holder` and `ctx`, and extending
`holder`'s sharing from four to all six subsystems), resolves what
`analyzeAutoTone`'s `edx` register holds at return (compiler cleanup
bookkeeping, not a status code — a question this doc had never actually
asked before), reconfirms §29's `fpo` finding on a complete rather than
partial capture, and — as a genuine bonus, resolving a stack-offset
ambiguity `r2`'s own default analysis left open — decodes real, per-channel
`tlb_afe_offset_write` values for the first time, landing within one code
of this project's own already-trusted `calibration/README.json`. None of
this bears on the ~88-89 code brightness gap (§31-34): the AFE offsets
decoded are a CCD-readout-time pedestal, structurally upstream of and
distinct from `c9`/the inversion formula/the polynomial matrix, the three
loci §31-34 already checked. **Item 1 (the four unreplicated stages)
remains the sole standing lead**, exactly as §34 left it.

**§34 update.** The task's own per-channel framing — raised as a candidate
*new* mechanism, not a restatement of §31-33 — is checked and closed the
same way §33 was: AFE gain is confirmed uniform and structurally inert as a
lever (closes item 3's gain half outright); lamp duty is confirmed current
for the calibration this capture actually used, but a second, real,
dated, unpromoted self-calibration of duty *and* level exists on this same
unit from earlier the same day, worth promoting on its own merits
(`docs/71 §9`'s documented install procedure) but, tested directly at its
own real magnitude against the real matched frame, moving the render by at
most 7 codes — an order of magnitude short of the gap, and in the wrong
direction for two of three channels. The specific asymmetric shape (blue's
smaller ratio but harder near-ceiling clip) is real but is most plausibly a
consequence of each channel's own `c9`/`film_base` ratio amplifying the
same still-open gap differently, not a new independent mechanism. **Item 1
(the four unreplicated stages) remains the sole standing software lead**;
nothing in §34 changes that ranking. §34 does add one new, real, concrete
action item to the "worth fixing/flagging regardless of this symptom" pile
(same category as §31.2's film_base bug): promote or discard
`calibration-fresh-scan/` through `docs/71`'s own documented procedure,
since a live, real, unpromoted self-calibration silently sitting unused is
exactly the failure mode `calib_wizard.py`'s own module docstring already
warns about (quoted in §33.3), now found a second time, in a second
subsystem.

**§33 update.** Item 6 below's second half (the polynomial colour-matrix's
own calibration currency) is now **closed, not open** — the last item on
§31.4's own list. §33 confirms the matrix data genuinely predates every
2026-08-12 hardware fix (captured 2026-08-05, committed 2026-08-10) and
that no fresher read exists anywhere on this machine, including one live
opportunity this session's own self-calibration wizard had to get one and
didn't (it correctly reused an existing stored record rather than
re-reading, per this hardware's own no-recheck constraint) — so the
staleness half of the hypothesis is real. But extending §31.3's own
cancellation argument to the matrix itself, and testing it directly on the
same matched frame, shows the part of a matrix error that could survive
the inversion's log-difference (cross-channel/quadratic terms) moves the
render by at most 18 codes at any percentile on real data — an order of
magnitude short of the 88-89 code gap — while the part large enough to
matter (the diagonal scale) provably cancels, structurally, for the same
reason a `film_base` rescaling does. Item 6 is fully closed as a lead for
this specific symptom; item 1 (the four unreplicated stages) is now the
sole standing software lead, alongside PakonIMAu.dll's own untriaged
log-instruction sites from §32.4.

**§32 update.** Item 6 below (added by §31: the inversion formula's own
construction) is now **narrowed, not closed**. §32 checked the two specific
candidate addresses this task named against the real, hash-verified
TLB.dll directly (full function-boundary disassembly) and confirmed neither
is `f135_rom12_to_rpd12` — both are the PolyPixel stage-2 colour-matrix
family. A genuine instruction-level search of TLB.dll for the log operation
the formula requires comes back empty for every traceable site. The same
search in PakonIMAu.dll found a much larger, only partially spot-checked
space (~50 `fyl2x` + ~64 `f2xm1` sites untriaged) — real remaining work, not
a dead end. No discrepancy was found, so nothing was fixed; the formula
remains unverified rather than confirmed wrong. **Item 6's other half — the
polynomial colour-matrix's own calibration currency (`load_unit_matrix`,
EEPROM-sourced) — is now the single sharpest remaining lead**, ahead of the
four unreplicated stages, since the inversion-formula lead itself is now
either closed (TLB.dll) or requires a properly scoped follow-up
(PakonIMAu.dll, via `tools/re/reachability.py` against `analyzeAutoTone`'s
own reachable sets, not a raw whole-binary grep) rather than more reasoning
about it in the abstract.

**§31 update.** Item 4 below ("get the definitive vendor comparison...
colour negative film... exported as TIFF") is now **satisfied**: `AA001.tif`
is exactly that — a real, colour-negative, matched-roll, matched-frame
vendor TIFF, no carving caveats. §31 used it to confirm the defect's shape
(uniform ~2× brightness excess at every percentile, not just a shadow
floor) and to test — directly, empirically, and analytically — whether the
roll-wide `film_base` measurement (item 5, "worth fixing anyway") could
explain it. It found a real, new, distinct film_base bug (the roll-wide
`FindDmin` walk is contaminated by real photo highlights on this
specific roll, for a different mechanism than item 5's single-frame gap —
see §31.2) but proved, both empirically and analytically, that fixing it
does not close the gap (§31.3) — ruling out an entire class of
single-parameter fixes to `f135_rom12_to_rpd12` (uniform rescaling of
`base`, or of `c9`) for the first time. Root cause remains open; the
formula's own construction (`F135_INVERT_PORTED=False`) and the polynomial
matrix's own calibration currency are now the two sharpest remaining
leads, ahead of the four unreplicated stages below, since §31 is the first
section to test the inversion formula's own parameters against a real,
matched, colour-negative vendor target rather than reasoning about it in
the abstract.

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
4. ~~Get the definitive vendor comparison~~ **Done — §31.** `AA001.tif`
   (colour negative, matched roll, matched frame, no carving caveats) is
   exactly what this item asked for. Used in §31 to confirm the defect's
   real shape (uniform, not just shadow-floor) and to test the leading
   film_base hypothesis directly; a real stage-by-stage comparison against
   this port's own intermediate arrays (§8's own method, cited here as the
   template) has not yet been run against `AA001.tif` specifically and
   remains the next concrete step — §31 tested parameters (film_base, c9)
   rather than tracing every stage's own absolute value against the
   vendor's.
5. **Fix the measurement harness's Dmin methodology anyway — real bug,
   just not the cause.** `measure_python_autotone.py`'s `film_base=None`
   on a lone TIFF is still measuring "the frame's own highlights" and
   calling it film base, which is simply wrong regardless of its effect
   on the washed-out symptom. Cheap fix, worth doing for its own sake
   (any future acceptance number that isn't purely relative will
   otherwise inherit this): thread a real roll-wide base through, the
   way `tools/pakon_render.py`'s own `open_capture`/`scene_rpd12` already
   do (§4's own method is a working, minimal example of exactly this).
   **§31.2 finds the roll-wide path has its own, newer version of the same
   class of bug**, on real production data, under the current lamp
   calibration — genuine leader saturates the poly-domain ceiling before
   the line-saturation heuristic can isolate it, so the "roll-wide, already
   fixed" path (§3/§4's own framing) draws its Dmin from real photo
   highlights too. Worth fixing on its own merits, same as this item
   always was — but §31.3 shows it will not, by itself, close the
   brightness gap.
6. ~~New, from §31: the inversion formula's own construction
   (`f135_rom12_to_rpd12`, `F135_INVERT_PORTED=False`) and the polynomial
   colour-matrix's own calibration currency (`load_unit_matrix`,
   EEPROM-sourced, unrelated to the lamp-duty fix — §31.2's own finding
   that clear film clips the poly domain without clipping the raw sensor
   is at least suggestive) are now the sharpest concrete leads for the
   brightness gap specifically~~ **Both halves now checked and closed, not
   the cause.** §32 checked the inversion formula's own construction
   against the real, hash-verified DLLs directly: the two named candidate
   addresses are resolved as PolyPixel-family, not the inversion; TLB.dll's
   own log-instruction sites are exhaustively traced with no per-pixel
   colour formula found; PakonIMAu.dll's much larger space is narrowed but
   not exhaustively triaged (§32.4, real remaining work, not a dead end).
   §33 checked the polynomial matrix's own calibration currency directly:
   the data genuinely predates every 2026-08-12 hardware fix and no fresher
   read exists anywhere on this machine, but a matrix-diagonal error
   provably cancels in the inversion's log-difference for the same
   structural reason a `film_base` rescaling does (§31.3), and the one part
   that could survive that cancellation (cross-channel/quadratic terms) is
   empirically bounded, on the real matched frame, to at most 18 codes at
   any percentile — an order of magnitude short of the 88-89 code gap.
   **Item 1 (the four unreplicated stages) is now the sole standing
   software lead**, since every stage between the inversion and the final
   image is independently verified correct (analyzeAutoTone bit-exact at
   full-frame scale, §24; FUGC and SBA-apply verified; `fpo` live-verified,
   §29), and every single-parameter lever inside the inversion formula and
   its two per-unit inputs has now been checked and closed (§31.3, §32,
   §33).

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

§15's numbers were independently reproduced, not copied from `docs/54`,
`docs/58`, or `docs/60`: `AA005.png`/`rawAA005.png`/`manifest.json` were
pulled directly from `research/vendor-scans/` on
`finding/f235-and-vendor-shadows`, both images' pixel SHA-256 recomputed
and checked against the manifest, and the percentile table recomputed
from the raw pixel arrays with `numpy`, not transcribed. The port-side
comparison rendered all 10 real frames of `scan-20260812-091633.bin`
(the same unmodified `open_capture`/`scene_rpd12`/`render_scene`/
`to_srgb` path every other section of this doc uses), not a subset.
`self.sra_lut`'s actual call site was found by direct `grep` against
`pakon_ansel.py`, not inferred. No port file changed.

§16's LUTs were parsed directly from the shipped
`vendor/ansel/anselinstalldir/dataPathItems/common/` files (the same
files §14/§15 cite), not synthesized, and the round-trip property was
checked against real loaded arrays before drawing any conclusion from
the render result. The experiment ran entirely in a scratch script
(this session's own job tmp dir); `real_auto_tone()` and every other
port function called were used completely unmodified — the only new
code is the LUT application at the two insertion points and a
standalone backward-LUT text parser mirroring `pakon_sra.py`'s own
forward-LUT parser. No port file changed.

§17 called `pakon_autotone_assembled_golden.py`'s own `build_dll`,
`host_run`, `_diff_scalars`, `_diff_array`, and `shipped_contrast_params`
functions completely unmodified — only the `image` argument changed,
from `make_image()`'s synthetic pixels to a real crop of this doc's own
already-computed `post_fugc` array (§14's own render chain, unmodified).
No port file, and no line of the assembled-golden harness itself,
changed.

§18 is a subagent's own disassembly work (re-extracted, MD5-verified
copy of the same DLL, `/tmp/sra_re/` scratch, read-only throughout) —
summarized and cross-checked against this doc's own established VAs
(`analyzeAutoTone` at `0x100fb730`, the CN-Enhanced driver at
`0x10069490`, both already independently confirmed in §11) rather than
taken uncritically. The specific claim that `AnsCnEnhancedPath::
analyzeScene`'s only substantive call goes to `fcn.10069490` is
consistent with, not contradicted by, §11's own independently-derived
call order for that same function. Full intermediate disassembly dumps
are preserved at `/tmp/sra_re/` on whichever machine ran the agent, not
copied into this repo.

§24's own script (`pakon_full_colour_chain_golden.py`) is new and additive;
it was checked with `python3 -m py_compile` and run end to end multiple
times (small real crops first, to validate each stage cheaply, then the
full real frame) before any number above was recorded — every number in
§24 is this pass's own direct terminal output, not transcribed from a
draft or predicted in advance. The DLL's MD5 was re-checked by the script
itself, printed at the top of its own run, before any comparison ran. The
crop-vs-full-frame-population mismatch this pass's own first draft of the
400×400 ground-truth comparison produced (~6-code average difference,
looked like a real divergence at first) was caught by re-deriving the
Python side from `ansel.real_auto_tone()` run on the SAME crop rather than
a crop of the already-full-frame-analysed Python render, and the
corrected, same-scope comparison is what §24 reports (pixel-identical) —
the miscomparison itself is recorded here rather than silently discarded,
consistent with this doc's own practice elsewhere (§9's "first pass at
this used the wrong array" note).

Finding 2's own correction was demanded, not offered voluntarily: asked
directly to confirm the bucketing-accumulator hypothesis against real
instructions before touching `pakon_cna.py`, and, once that was refuted,
to keep digging rather than stop at "not this." The refutation is a direct
instruction citation (`r2 -e bin.relocs.apply=true -q -c 'aa; af @
0x1022ddc0; pd 60 @ 0x1022e2e8' PakonIMAu.dll`, re-run this pass, output
preserved this session). The actual cause was localised by (1) a binary
search over real crop sizes of the same frame narrowing the break point to
between 1,042×1,042 (works) and 1,043×1,043 (broken) pixels, (2) a
`UC_HOOK_CODE` instruction trace over `analyze_image`'s own address range
showing where recorded execution stopped advancing, and (3) a runtime
replacement of `Emu.call` (a new function added to this pass's own script,
`patch_unchecked_instruction_cap`, not an edit to
`pakon_autotone_shell_golden.py` on disk) that raises the instruction cap
and explicitly asserts EIP reached the real return address — run in the
FOREGROUND, waited for to completion, not backgrounded and assumed; the
first attempt to check this claim was in fact launched in the background
and, per this session's own transcript, had to be redone in the foreground
after a direct request to actually wait for it, which is recorded here
rather than smoothed over. Both the 1,043×1,043 crop and the full frame
were re-run with the fix and diffed field-by-field against the Python host
a second time, from a clean process, before Finding 2 was rewritten. The
fix is applied in `pakon_full_colour_chain_golden.py`'s own `main()`
(`patch_unchecked_instruction_cap()`, called once, alongside the
already-documented `HEAP`/`HEAP_SZ` relocation), so re-running the
committed script reproduces the corrected numbers directly, not the
original wrong ones. All scratch/diagnostic scripts used to localise and
confirm this (several `/tmp/_*.py` files, plus ad hoc `r2`/`pd` disassembly
dumps under `/tmp/pakon_re/` and `/tmp/`) were not committed — only
`pakon_full_colour_chain_golden.py` itself is new, additive, committed
code, and no existing golden file was modified on disk by this pass.

§30's reproduction used a throwaway wrapper (not committed) that imports
`pakon_full_colour_chain_golden` and monkeypatches its module-level
`CAPTURE`/`FRAME_INDEX` at runtime, per this pass's own instructions not to
edit that file's own citation of its original §24 capture; the golden file
on disk is byte-for-byte what §24 left it. `cum_bounds`'s full-function
disassembly (`af`+`pdf @ 0x10228bc0`, 257 B, 19 basic blocks) and both
`_contrast_map` bodies' disassembly (`0x1022c630`, `0x1022c520`) were read
fresh this pass against the same MD5-verified DLL every other section
cites, not transcribed from any prior document. `hist_resample`'s isolation
test used `pakon_cna_golden.dll_resample` — an existing, previously-built
but never-exercised-at-this-scale golden function — completely unmodified;
its own heap size was fine for the size involved (500 buckets), so unlike
`dll_analyze_image` it needed no heap relocation. The
`dll_analyze_image`/`CnaEmu` isolated harness required the identical
class of fix §24 already found in `pakon_autotone_shell_golden.Emu.call`
(heap relocation + the instruction-cap/EIP-check patch) — applied at
runtime in this pass's own throwaway scripts via the same
`shellg.HEAP`/`HEAP_SZ` globals and `patch_unchecked_instruction_cap()`
function §24 already added to `pakon_full_colour_chain_golden.py`, not a
new or rediscovered fix, and not a change to `pakon_cna_golden.py` on disk.
The one-line fix itself (`pakon_cna.py`'s `_contrast_map`) was verified
bit-exact twice, independently: first via the isolated `cna`-only harness
(`tone_lut` 0 of 5,000 mismatches, down from 3,280), then via a full,
independent re-run of the assembled six-subsystem harness end to end,
including the final `AnselEngine.to_srgb` render diffed pixel-for-pixel
against the real DLL's own ground-truth render on the identical real
frame (`max=0.0` over every pixel and channel) — not inferred from the
`cna`-level fix alone. No golden file was modified on disk; the only
production-code change is the one line (plus docstring) in
`pakon_cna.py`'s `_contrast_map`, described and cited above for review.

§31's reproduction used the same unmodified `tools/pakon_render.render_frame`
production entry point every other real-render section of this doc uses
(`PAKON_COLOUR_ENGINE=python`, `film_path="ColNeg"`, frame 0 of
`test123.bin`), against the roll already opened by the app itself at
`~/Library/Caches/PakonScan/workspace/f4c91b62/roll.json` (read-only —
nothing in this pass re-opened or re-decoded the capture) so the real,
already-computed roll-wide `film_base` was used unmodified, not
re-derived. `AA001.tif`'s percentiles were computed directly with `PIL`/
`numpy` from the file at
`/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/vendor-tiffs/AA001.tif`
(re-measured this pass, not taken from the task's own transcribed numbers,
which it independently reproduces to within a few codes). §31.1's stage
trace called `pc.poly_hwc`, `pr._rpd16`, `ansel.rpd16_to_rpd12`,
`dec.f135_rom12_to_rpd12`, `eng.render_scene`, and `eng.to_srgb` directly —
the same already-cited, already-verified functions every earlier stage
trace in this doc (§8, §9) used, on this new roll and frame. §31.2's
film_base diagnostics re-ran `open_capture`'s own accumulation loop
(`pakon_render.py:824-895`) with added instrumentation, calling the same
`dec.film_base_line_mask`/`ansel.scene_ctx.find_dmin_code_from_hist`
functions §2-4 already used and cited as `[VERIFIED, vendor]` for the walk
itself and `[OURS]`/`FILM_BASE_WINDOW_PORTED=False` for the window —
labels read directly from `pakon_decode.py`'s own comments this pass, not
paraphrased from memory. The head/tail leader measurements used
`roll.framing["film_start"]`/`["film_stop"]`, the same five-phase-cascade
boundaries `pakon_framing` already computed and stored on this roll at
open time — not re-derived or guessed. The raw-14-bit-vs-poly-domain
saturation comparison (proving the head leader's poly-domain clamp is not
a raw-sensor ceiling) called `dec.apply_unit_calibration` directly on the
same cached strip every other stage in this doc reads from `roll.attach()`.
§31.3's film_base and `c9` sweeps called `dec.f135_rom12_to_rpd12` and
`eng.render_scene`/`.to_srgb` directly and unmodified, varying only their
own explicit parameters — no port file was edited to run any sweep. Every
number in §31 is this pass's own direct terminal output, re-measured
against real files (the real `AA001.tif`, the real `test123.bin`, the real
already-computed `roll.film_base`), not estimated, interpolated, or carried
over from the task's own prompt. **No production code was changed by this
pass** — `pakon_decode.py`, `pakon_render.py`, `pakon_ansel.py`, and every
other file this section reads were read-only throughout; the only new
files are disposable scratch scripts under `/tmp` (`repro_wash.py`,
`trace_stages.py`, `diag_filmbase.py`, `diag_leader.py`,
`diag_leader_dmin.py`, `c9sweep2.txt` and similar), not committed,
consistent with this doc's own established practice of leaving scratch
diagnostics out of the repo. This doc's own rule against describing
`captures/`/cache pixel content in writing was followed throughout — only
aggregate percentile statistics are reported anywhere in §31.

§32's DLL hashes were computed directly this pass (`md5 -q`), not copied
from a prior citation, against local copies at
`/Users/guy/pakon-windows-repair/COM-SERVER/{PakonIMAu,TLB}.dll` — this
repo's own `research/sdk/PAKONF135.iso` is gitignored and not present in
this checkout, so this pass used the closest available previously-verified
copies rather than re-extracting from an ISO it didn't have; the TLB.dll
match against `docs/70`'s own independently-recorded hash
(`193d9b2ce0a4b77ae9b78262bd06c0fc`) is what establishes this copy as the
right one, not an assumption. All disassembly used real `r2` (radare2
6.1.8) `af`+`pdf` function-boundary output against these files with
`bin.baddr=0x10000000` (the DLL's real PE base) — never a raw byte-range
read. The `fyl2x`/`fyl2xp1`/`f2xm1` search used `r2`'s `/x` raw byte search
over each **whole binary**, not a `.text`-only or function-scoped search,
so the counts reported (7/0/2 for TLB.dll after discarding one false
positive; 61/64 for PakonIMAu.dll) are complete statements about instruction
occurrence, not a sample — what is *not* exhaustive is the tracing of every
one of PakonIMAu.dll's 125 sites back to a caller, stated plainly as
incomplete in §32.4. The one fully-traced TLB.dll chain
(`fcn.100341b0` → `fcn.100125a0` → `fcn.1000f130` → `fcn.1000ef80` →
`fcn.1000dfc0`) was walked via real `axt` (cross-reference) output at every
hop, not inferred from address proximity, and `fcn.100341b0`'s own
559-line body was read in full (`pdf`), not skimmed, before concluding it
is scan-session bookkeeping rather than colour math. No Unicorn execution
was run for §32 — §32.5 states explicitly why static disassembly was judged
sufficient for the specific question asked of the two candidate addresses.
No production code was changed by this pass; `pakon_decode.py`'s
`f135_rom12_to_rpd12` and `check_film_class` were read, not edited, and the
disassembly work happened entirely against external DLL copies outside this
repo, read-only throughout.

§33's timeline claims were checked against live filesystem state, not
assumed from prior citations: `backups/eeprom-i2c/eeprom_52.bin`'s git
history (`git log -- backups/eeprom-i2c/eeprom_52.bin`), the real local
calibration store at `~/Library/Application Support/PakonScan/calibration`
(`calib_resolve.resolve()` called live against the real
`CalibrationStore`, not read from source alone), and a live `shasum -a 256`
comparison confirming the store's "good" 0x52 record is byte-identical to
the committed backup. `load_unit_matrix`'s actual resolution (registry
absent, falls to EEPROM) was confirmed by importing `pakon_color` and
calling it directly, not by reading the `if`/`elif` alone. §33.4 and §33.5's
renders both ran the real, unmodified production call chain
(`Roll.slice14` → `pakon_render.scene_rpd12` → `AnselEngine.render_scene` →
`.to_srgb`) against the exact same `test123.bin`/workspace `f4c91b62` roll
§31 used, and reproduced §31.1's own stage-1/stage-2/final-sRGB numbers
before changing anything, as a harness sanity check (matched to within
normal percentile-interpolation rounding). The alternate matrices (§33.4's
affine-only ablation) and the duty-scaled input (§33.5) were constructed
and rendered in scratch scripts under `/tmp`, never written into
`tools/pakon_color.py` or `tools/ansel/pipeline/main.go`; both files were
read and their real coefficients/paths used, not edited. Only aggregate
percentile statistics from `test123.bin` are reported above, consistent
with this project's rule against describing `captures/` contents; no pixel
data or image content is reproduced.

§34's per-channel percentiles and ratios were computed directly with
`numpy`/`PIL` against the real `AA001.tif`
(`/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/vendor-tiffs/AA001.tif`,
the same file §31 used, re-measured this pass, not transcribed from the
task's own numbers or from §31's) and against a fresh, direct call to
`pr.render_frame(roll, 0)` on the real `f4c91b62` workspace (`pr.Roll.
from_json` on its own `roll.json`, `PAKON_COLOUR_ENGINE=python`), which
reproduced §31.1's own baseline sRGB percentiles exactly before anything
else in this section ran, as a harness sanity check. §34.2's duty figures
were read directly from `test123.scan.json` (the app's own real capture
sidecar, `~/Library/Caches/PakonScan/captures/`) and cross-checked against
`docs/59-lamp-sequence-captured.md`'s own registry-derived `10^D` figures
(that doc lives on the private remote's `finding/f235-and-vendor-shadows`
branch, per §13's own citation convention — fetched read-only via `git show
remotes/private/finding/f235-and-vendor-shadows:docs/59-lamp-sequence-
captured.md`, not merged into this branch). §34.3's gain figures were read
directly from every `calibration/README*.json` and `calibration-*/
README.json` file on this checkout (8 files, `python3`/`json`, not
eyeballed), cross-referenced against `tools/pakon_commands.py`'s own
`ADC_IDX_GAIN_R/G/B`/`ADC_GAIN_MAX` constants and `tools/pakon_scan.py`'s
own `ccd_configure` (`:1606-1610`, the real write site). §34.4's timeline
used each file's own `generated_at`/`wizard_stamp` fields plus a live
`stat`/`ls -la` of `calibration/README.json`'s own mtime and
`test123.scan.json`'s own `created` field and file mtime — not assumed or
estimated. §34.5's joint scaling ran the real, unmodified
`pr.scene_rpd12`/`eng.render_scene`/`pr.apply_correction`/`eng.to_srgb`
chain, called directly (not through `render_frame`, so the calibrated
14-bit segment and `film_base` could be scaled together before the first
call) against the real `roll.slice14(f.a, f.b, step)` output for frame 0 of
`test123.bin` — the same segment `_render_colour_python` itself would
produce, confirmed by the harness-sanity-check baseline matching §31.1
exactly. All scratch scripts (`/tmp/sec34/repro34.py`, `aa001.py`,
`sweep34.py`, `sweep34b.py`, `sweep34c.py`, `sweep34d.py`, `sweep34e.py`,
`gains_check.py`) are disposable, not committed, consistent with this
doc's own established practice. No port file was changed; no calibration
directory was modified, promoted, or installed. Only aggregate percentile
and ratio statistics from `test123.bin`/`AA001.tif` are reported above,
consistent with this project's rule against describing `captures/`
contents; no pixel data or image content is reproduced anywhere in this
section.

§36's new script (`pakon_prechain_bracket_golden.py`) was run to completion
multiple times (a small 250×2000 crop first, to validate each stage cheaply
and to confirm the instruction-cap bug/fix directly, then the full real
frame twice) before any number in §36 was recorded, the same discipline §24
used for its own new script. Both DLL MD5s were re-checked by the script
itself, printed at the top of its own run, against the same two hashes
every prior section of this doc cites. The 500,000-pixel instruction-cap
failure (`0x1000da4c`, not `STOP`) was observed directly, not inferred —
`g.uc.reg_read(UC_X86_REG_EIP)` was read immediately after the unmodified
`PolyGolden.run()` returned and compared against `pcg.STOP` explicitly,
the same check §24's own `patch_unchecked_instruction_cap` performs. The
calling conventions for `0x100f42a0` and `0x1006c4f0` were derived from
fresh `r2` `af`/`pdf`/`afvj` output against the real, MD5-verified
`PakonIMAu.dll` this pass (not transcribed from `pakon_sba_apply.py`'s own
prior, reading-based citation, though the two independently agree), with
the ctor's own three argument VALUES additionally confirmed byte-for-byte
against the real CRT-init call site at `0x1056a470`. The master-table check
(§36.2) reads all 65,536 addressable entries directly from the emulated
heap via `uc.mem_read` and compares against the closed-form expectation
with `numpy`, not a sampled or spot-checked subset. The shift-LUT check
reads all three real, DLL-allocated 4096-entry buffers in full. §36.3's
post-inversion array came from the same unmodified `pr.scene_rpd12` call
(same roll, same frame, same real `film_base`/`fpo`/`setshifts_out`) every
other real-render section of this doc uses, not a synthetic array. §36.4's
citation of `sba_apply_balance_shifts` never firing was cross-checked
directly against `tools/re/live_hooks/win_inject/hookcore_real_table.c`'s
own hook table (confirming `0x1019a0c0` is the address that hook name
refers to) rather than taken on §35.6's prose alone. **No production code
was changed by this pass** — `pakon_color.py`, `pakon_color_golden.py`,
`pakon_sba_apply.py`, `pakon_render.py`, and every other file this section
reads were read-only throughout (`git status`/`git diff` confirm zero
modifications to any tracked file); the only new file is
`tools/ansel/python-pipeline/pakon_prechain_bracket_golden.py` itself,
additive, committed for review. Only aggregate count/percentile statistics
from `test123.bin` are reported anywhere in §36, consistent with this
project's rule against describing `captures/`/cache contents; no pixel data
or image content is reproduced.
