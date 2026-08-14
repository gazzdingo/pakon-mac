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
