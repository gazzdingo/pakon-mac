# 75 — Real B&W frames fail to render via FindDmin's own sentinel: a
genuine scan-time exposure mismatch, not a render bug — the with-film lamp
duty is colour-negative-specific and has no B&W profile anywhere in this
codebase

A separate investigation from docs/74 (which is about a ColNeg brightness
gap, upstream of `analyzeAutoTone`, on correctly-exposed data). This one is
about real black-and-white film failing to render at all, with a different
mechanism, at a different stage of the pipeline (the sensor, not the tone
curve). Kept in its own file per this project's own convention of not
folding unrelated mechanisms into one doc just because they surfaced the
same night.

## Summary

**Root cause found, and it is scan-time, not software.** The F-135's
with-film lamp duty — the PWM on-counts the light board runs at once film
is detected in the gate — is, by this project's own code and its own prior
documentation (docs/59, dated 2026-08-13, unrelated to tonight), an exact
implementation of the vendor's **colour-negative orange-mask base-density
compensation**: it multiplies the open-gate (no-film) duty by `10^D` per
channel, with `D = 0.144 / 0.400 / 0.715` for R/G/B respectively — i.e. it
deliberately drives *far* more light through green and especially blue than
red, to compensate for what a colour negative's orange mask absorbs.
**Nothing in this codebase makes that duty film-type-aware.**
`ScanConfig.film_path` (`tools/pakon_scan.py:546-553`) is scan metadata
only — "Not a register — nothing here is sent to the scanner" — and the
actual duty switch, `lamp_switch_to_scan_duty`
(`tools/pakon_scan.py:1021-1048`), always moves to `cfg.on_counts`
regardless of what film type was selected, with its own docstring stating
in as many words that this is "exactly compensating for what the orange
mask absorbs" (line 1028). A true panchromatic B&W negative has **no**
orange mask (confirmed independently from the vendor's own
`defaults.ini`, `tools/film_ids.py:20-21`: "no orange mask, and no
per-stock colour matrix"). Running B&W film under a duty tuned to add back
what an orange mask removes overexposes green and blue at the sensor —
consistent, channel-for-channel, with the UI's own per-frame readout
(`11037-16356-16383` R-G-B, §1) and with the roll-wide `FindDmin` refusal
this investigation started from.

This is a genuine hardware/calibration gap, not a bug in `FindDmin`, the
histogram walk, or the render pipeline — `check_film_base`'s refusal is
shown (§6) to be working exactly as designed for genuinely clipped film.
Frames already scanned with green and blue pinned at or near the sensor
ceiling across most of their area are very likely **not recoverable** by
any software fix (§7) — the ADC never captured the information. What would
fix this for *future* B&W rolls is a B&W-specific with-film duty, which
does not exist anywhere in this codebase yet and would need real
measurement against actual B&W film in the gate (§8).

## 1 — Where the UI's own per-frame Dmin panel comes from: a completely
different measurement from the roll-wide `FindDmin` that's failing

The screenshot's `11037-16356-16383` / `Shadows 0.00%` / `Highlights 1.77%`
readout is **not** related to `pakon_decode.film_base_codes`/`FindDmin` (the
histogram-walk that's raising `FilmBaseNotFound`) — different code,
different data population, different statistic, different domain.

Traced end to end:

- **Route**: `GET /roll/<id>/hist/<frame>` (`tools/pakon_app.py:2139-2140`)
  → `pr.frame_histogram(roll, index)`.
- **Function**: `pakon_render.frame_histogram`
  (`tools/pakon_render.py:1413-1434`):

  ```python
  def frame_histogram(roll: Roll, index: int, params: dict | None = None) -> dict:
      """RGB histogram of the 14-bit source plus the facts frame.html shows."""
      f = roll.frames[index]
      seg = roll.slice14(f.a, f.b, 4)
      hist = {}
      for c, name in enumerate("rgb"):
          h, _ = np.histogram(seg[:, :, c], bins=64, range=(0, dec.RAW14_MAX))
          hist[name] = [int(v) for v in h]
      dmin = [float(np.percentile(seg[:, :, c], 99.0)) for c in range(3)]
      clipped = float((seg >= dec.RAW14_MAX - 1).mean() * 100.0)
      floored = float((seg <= 1).mean() * 100.0)
      return {
          "hist": hist,
          "dmin": [round(v, 1) for v in dmin],
          "clipped_pct": round(clipped, 3),
          "clipped_shadow_pct": round(floored, 3),
          "lines": [f.a, f.b],
      }
  ```

- **Frontend**: `app/src/api.js:238` (`histUrl`), consumed by
  `app/src/FrameEditor.jsx:461-463`, which labels `hist.dmin` "Dmin",
  `hist.clipped_shadow_pct` "Shadows", `hist.clipped_pct` "Highlights".

**Data domain**: `seg = roll.slice14(f.a, f.b, 4)` is the calibrated 14-bit
per-frame block (`tools/pakon_render.py:571-578`): the cached raw sensor
strip run through `dec.apply_unit_calibration` (dark subtraction + per-
channel gain, clamped to `[0, RAW14_MAX=16383]`). This is upstream of the
colour matrix (`pc.poly_hwc`) and upstream of any log-density inversion —
i.e. it is essentially raw sensor data, one step removed from the ADC.

**Statistic**: `dmin` is the **per-channel 99th percentile of this one
frame's own raw14 pixels** (`np.percentile(seg[:,:,c], 99.0)`), sampled
`4`-line-decimated. `clipped_pct` ("Highlights") is the fraction of *all*
`R+G+B` samples (not per-channel) at or above `RAW14_MAX - 1 = 16382`.
`clipped_shadow_pct` ("Shadows") is the fraction at or below raw code `1`.

This is architecturally unrelated to `FindDmin`: no histogram walk, no
0.1%-threshold sentinel, no roll-wide accumulation, no film-area line mask
(`film_base_window`), and no film-class awareness. It is a blunt, per-frame,
per-channel percentile taken directly off the calibrated sensor plane. The
"Dmin" name is a UI convenience (on a negative, high raw signal = high
transmission = clear film base), not a claim that it implements the vendor's
`FindDmin` algorithm — it doesn't, and was never meant to.

**Reading the actual numbers.** R=11037 sits at 67% of the 16383 ceiling.
G=16356 sits at 99.8% of ceiling. B=16383 is **exactly** the ceiling. Given
`clipped_pct=1.77%` is computed over all three channels pooled, and R is
nowhere near clipped, essentially all of that 1.77% is coming out of G and
B — meaning **at least 1% of this frame's own G pixels, and at least 1% of
its B pixels, individually exceed 16356/16383 respectively** (that is what
a 99th-percentile reading at/near the ceiling means by construction), with
the true per-channel clip fraction for G and B plausibly several times
higher than the pooled 1.77% figure. **The R < G < B ordering of how close
each channel sits to the ceiling exactly matches the R < G < B ordering of
the with-film duty's own compensation ratio** — see §4 — which is the first
concrete link between this readout and the duty mechanism, not yet the full
argument.

## 2 — `BW_OFFSET_DELTA`/`quantise_matrix_bw`: real, correctly-ported vendor
logic — for the wrong scanner model. Dead code on the F-135 path this
project actually renders through, and not merely unwired

`tools/pakon_color.py:429-440`:

```python
# The B&W context is built from the same 3x4 with the offset column perturbed.
# Doubles at TLA 0x10066f78 / 0x10066f70 / 0x10066f68.
BW_OFFSET_DELTA = (397.05, 12.08, -167.31)


def quantise_matrix_bw(matrix, coeff_scale: int = COEFF_FIXED,
                       offset_scale: int = OFFSET_SCALE):
    """`TLA.dll:0x100158f0` builds cfg+0x48 from cfg+0x200 with the offsets bumped."""
    bumped = [list(row) for row in matrix]
    for i in range(3):
        bumped[i][3] += BW_OFFSET_DELTA[i]
    return quantise_matrix(bumped, coeff_scale, offset_scale)
```

Both function and constant are cited against **`TLA.dll`**, not `TLB.dll`.
`pakon_color.py`'s own module docstring (line 6) is explicit that
`TLA.dll`, `TLB.dll` and `TLC.dll` are **three separate per-model builds**
of the same COM server — and this project's real F-135 render path uses
`TLB.dll`'s stage-2 polynomial exclusively: `poly_hwc`
(`tools/pakon_color.py:747-802`, docstring "`fcn.1000d880` (TLB.dll @
`0x1000d880`)"), the same `fcn.1000d880` the task's own already-established
fact cites for the filmClass 1/4/8 dispatch (`this+0x50`, identical for
ColNeg and both BnW classes). `pakon_color.py:877` states this split in as
many words when logging which colour path a render used: *"F-135, TLB.dll
3x10 polynomial"* vs *"F-235/F-335, TLA.dll LUT + 3x4 matrix"* — two
different products, two different colour architectures. `quantise_matrix`
and `quantise_matrix_bw` (TLA's `buildContext`, a LUT + 3x4-matrix scheme)
have no F-135/TLB equivalent to be wired into: TLB's `fcn.1000d880` is a
3x10 polynomial with no separate B&W offset table anywhere in its own
dispatch (confirmed by the already-established filmClass fact this task
supplied — 1/4/8 all read the identical matrix at `this+0x50`).

**Both real call sites of `quantise_matrix_bw` are diagnostic, and both are
for F-235/F-335, not F-135:**

1. `show_matrix()` (`tools/pakon_color.py:977-1017`) — a CLI printout. Its
   `model == "f135"` branch (`:978-996`) returns **before** the function
   ever reaches the `quantise_matrix_bw` call at line 1004; that call is
   only reached for the non-f135 (F-235/F-335) branch.
2. `verify()`'s checkpoint 3 (`tools/pakon_color.py:1186-1208`), explicitly
   labelled `"matrix quantisation, F-235/F-335 (docs/58 section 14.3)"` — a
   self-test against vendor-captured F-235/F-335 numbers, not a render path.

`grep`-confirmed: neither `BW_OFFSET_DELTA` nor `quantise_matrix_bw` is
referenced anywhere in `pakon_render.py` (the actual render/`scene_rpd12`
call chain) or `pakon_app.py`. This is not "a real mechanism that's
currently unwired" — it is a correctly reverse-engineered piece of a
*different scanner model's* driver, present in this repo purely as
verified documentation/test fixture, with no path by which it could affect
an F-135 render even if someone wired it in today. Even setting the model
mismatch aside: it operates on the colour matrix, which runs *after* the
raw sensor capture this bug is actually about (§4) — it could not have
prevented G/B from clipping at the ADC regardless of which model it
targeted.

## 3 — No B&W-aware exposure configuration exists anywhere in this
codebase — checked at every layer between the UI's film-type picker and
the lamp

- **`ScanConfig`** (`tools/pakon_scan.py:521-554`): `afe_gains` defaults to
  a single fixed `(13, 13, 13)`; `on_counts`/`open_gate_on_counts` are
  single fixed triples with no film-type parameter. `film_path` is stored
  (line 553) but its own docstring says plainly: *"WHAT THE OPERATOR SAID
  THE FILM WAS. Not a register — nothing here is sent to the scanner."*
- **`lamp_switch_to_scan_duty`** (`tools/pakon_scan.py:1021-1048`), the
  function that actually writes the with-film duty to the light board
  (`pc.REG_LIGHT_LED_DUTY`) the instant film is detected: takes `cfg`,
  reads `cfg.on_counts`, and switches to it unconditionally. No branch on
  `cfg.film_path`, no BnW case, nothing — confirmed by reading the full
  function body, not inferred from its signature.
- **`calib_wizard.py`**'s duty search, `step_duty`
  (`tools/calib_wizard.py:867-965`): searches
  `on_counts_R_G_B` against a **dark/bright probe with an empty gate**
  (`bcal.solve_duty`, `dark_cap`) — no film-type parameter anywhere in its
  signature or body either. `grep -n "BnW" tools/calib_wizard.py` returns
  nothing.
- **`calibration/README.json`** (this unit's current, live calibration,
  `generated_by: tools/calib_wizard.py`, `generated_at:
  2026-08-14T06:50:06`): one `on_counts_R_G_B` field, `[912, 938, 804]`,
  used for every scan regardless of `film_path`. Its own `note` field
  states this explicitly — quoted in full in §4, because it also answers
  where that number came from.

So: at every one of the four layers between "operator picks BnW in the
scan dialog" (`app/src/ScanModal.jsx:58`, `app/src/Dialogs.jsx:10`) and
"the lamp board's PWM registers", the film-type selection is dropped. It
survives only as descriptive metadata that later selects a render-side
colour matrix (filmClass, already established as identical for BnW/ColNeg
anyway) — never as anything that reaches the light board.

## 4 — The with-film duty currently in force is, by this project's own
prior documentation, the colour-negative orange-mask compensation exactly
— not a hypothesis, verified to six figures

`calibration/README.json`'s `note` field, in full:

> "SCAN-READY OVERRIDE, 2026-08-14. dark_2000x3.npy/gain_2000x3.npy/
> afe_offsets/afe_gains are this unit's own fresh self-calibration, searched
> today against the real hardware — unmodified. `on_counts_R_G_B` here is
> NOT the wizard's own output — the wizard measured against an empty gate
> (dark/bright references), so its own `on_counts_R_G_B` (`[643,580,508]`,
> preserved below as `flat_field_on_counts_R_G_B`) is this unit's real,
> fresh OPEN-GATE duty. For actual film scanning, `on_counts_R_G_B` is
> overridden to docs/59-lamp-sequence-captured.md's real vendor with-film
> capture (`[912,938,804]`) — a directly captured value off this exact
> unit's own wire during an actual PSI scan, not derived."

So the duty this unit runs for **every** scan, regardless of film type, is
a value captured directly off the wire during a real vendor PSI scan — and
docs/59 (2026-08-13, written before and independently of tonight's B&W
investigation) already identifies exactly what that captured duty *is*:

> "the vendor keeps **two duty sets**, and `FN_bBeforeScan` (`0x1002e137` →
> `0x1002d7f0`) selects `DutyCycle_*` with film in the gate and
> `DutyCycleOpenGate_*` without. They differ by exactly **10^D**, the
> colour-negative base density — the with-film set adds back what the
> orange mask absorbs."
>
> ```
> ch   with-film   open-gate      ratio     10^D      D
> R     0.917161    0.658333   1.393157   EXACT   0.1440
> G     0.955468    0.380378   2.511891   EXACT   0.4000
> B     0.865802    0.166885   5.188016   EXACT   0.7150
> ```

verified there "against the registry, exact to six figures" and again
independently "against the captured pair" (docs/59 lines 3-21). The same
document flags the safety consequence in as many words (lines 28-30):
*"`--full` is the with-film set and **saturates blue on a bare gate**. The
default is the open-gate set, which is correct for a bare gate."* — i.e.
this duty is already known, in this repo, to over-saturate blue even with
**no film at all** in the gate.

`pakon_scan.py`'s own docstring for the function that performs this switch
agrees, independently of docs/59 (`tools/pakon_scan.py:1024-1028`):
*"Real PSI does not run one fixed lamp duty for a whole roll: the captured
trace shows the light board written at the dimmer open-gate duty while the
leader is going through..., then switched to a brighter with-film duty...
at the instant the film sensors report film present — **exactly
compensating for what the orange mask absorbs, which the leader does
not have**."*

Three independent statements in this codebase — the calibration record's
own note, docs/59's registry/wire-trace verification, and the scan code's
own docstring — agree on the same fact: the with-film duty this unit uses
for every scan is calibrated specifically, and by design, to add back a
colour-negative orange mask's absorption, weighted by channel exactly as an
orange mask would demand (R barely touched, G boosted 2.5x, B boosted
5.2x). A true panchromatic B&W negative has no orange mask to add back.

**This channel ordering (R « G < B in compensation strength) is exactly the
ordering the screenshot's own numbers show in how close each channel sits
to the raw ceiling** (§1: R=11037 well under, G=16356 near, B=16383 at) —
the two are not just consistent in direction, they rank identically across
all three channels.

## 5 — Independent corroboration, from the vendor's own shipped
configuration, not this project's reverse-engineering

`tools/film_ids.py`, which parses the vendor's own
`Config/ColorCorrection/defaults.ini` (not reverse-engineered — read
directly from the vendor tree), states in its own module docstring
(lines 8, 20-23):

> "`[BnW]` black and white, both C41 process and conventional"
>
> "...HP5, FP4 and Delta 3200 are conventional black and white negatives:
> **no orange mask**, and no per-stock colour matrix. They render through
> the `[BnW]` path, where the density LUT does the inversion and the
> matrix degenerates to a neutral transform with a measured film-base
> offset."

This is the vendor's own categorisation, independent of any wire capture or
disassembly: real B&W stock has no orange mask, confirming the premise the
duty mismatch in §4 depends on from a second, independent source.

## 6 — `FindDmin`'s refusal is working exactly as designed, checked against
its own docstring — this is not the software bug

`check_film_base` (`tools/pakon_decode.py:892-951`), the function that
raises the `FilmBaseNotFound` error quoted in the bug report, documents
exactly this scenario in its own docstring (`:904-911`, written before
tonight):

> "This still fires, and has to. What changed is only *what it is a
> statement about*: `FindDmin` now walks the film area
> (`film_base_window`), so a 0 here means **the film itself is clipped**
> over more than 0.1% of its area, at the sensor (raw 16383) or at the
> polynomial's ceiling... **That is the case where lowering the gain is
> the right answer.** It is no longer raised by a clear leader or by the
> gate edge outside the vendor's CCD window, because those are not film
> and are no longer in the histogram."

The window this walks (`film_base_window`, `:795-813`) already excludes
leader/gap by a per-line saturation test (`film_base_line_mask`, `:780-792`,
threshold `FILM_BASE_LINE_SATURATION=0.5`) and refuses outright if fewer
than half the roll's lines survive that test
(`FILM_BASE_MIN_FILM_FRACTION=0.5`, `:761`, `film_base_codes:828-834`). The
0 sentinel for G/B is therefore not a histogram-walk bug, a leader-
contamination bug (that was §31.2/§41's fix in docs/74, already landed and
unrelated to B&W), or a framing bug (§43's fix, also unrelated) — it is
the walk correctly finding that G and B are clipped at the 4095
polynomial ceiling (fed by a sensor already at or near its own 16383
ceiling, per §1) over more than the 0.1% threshold across the *film area
itself*, roll-wide, on real B&W rolls — exactly the condition its own
docstring names as "lowering the gain is the right answer," which is what
the live error message tells the user, verbatim.

This matches the bug report's own cross-frame consistency: two different
frames from the same roll(s) both returned `R != 0, G == 0, B == 0` — a
roll-wide duty problem produces a roll-wide symptom, not a one-frame
anomaly, which is what a per-frame algorithm bug would more plausibly look
like.

## 7 — Verdict

1. **The UI's Dmin panel** (§1) is a simple per-frame, per-channel 99th-
   percentile of calibrated raw14 data — architecturally unrelated to the
   roll-wide `FindDmin` walk that's failing, but its numbers on this frame
   (R=11037, G=16356, B=16383) are real, load-bearing evidence: G and B are
   at or within 30 codes of the 16383 sensor ceiling.
2. **`BW_OFFSET_DELTA`/`quantise_matrix_bw`** (§2) is real, correctly-
   ported vendor logic for a *different scanner model's* driver
   (`TLA.dll`, F-235/F-335) that this project does not scan with. It is
   dead code relative to the F-135 (`TLB.dll`) path this project actually
   renders through, has no F-135 equivalent to be "wired into", and
   operates downstream of the sensor in any case — it could not fix this
   even if it targeted the right model.
3. **No BnW-specific exposure configuration exists anywhere in this
   codebase** (§3) — not in `ScanConfig`, not in the live duty-switch
   function, not in the calibration wizard's duty search, not in the
   committed calibration file. `film_path` is metadata only.
4. **The with-film duty currently in force is the colour-negative
   orange-mask compensation, confirmed from three independent sources in
   this repo** (§4: the calibration record's own note, docs/59's six-
   figure registry/wire-trace verification from the night before, and the
   live scan code's own docstring) — and the vendor's own shipped
   configuration independently confirms real B&W stock has no orange mask
   to compensate for (§5).
5. **`FindDmin`'s refusal is functioning as designed** (§6), confirmed
   against its own pre-existing docstring: a 0 sentinel here specifically
   means the film itself is clipped over the film area, which is exactly
   what a colour-negative-tuned duty applied to panchromatic film would
   produce.

**This is a real, scan-time exposure/gain mismatch — hardware/calibration,
not software.** No amount of render-pipeline or `FindDmin`-algorithm work
can fix it, because the defect is upstream of everything this project's
software touches: green and blue are driven to or past the ADC's own
ceiling before a single byte reaches this codebase. Frames already scanned
under this duty, wherever their own G/B sit at or very near 16383 across
most of the frame (consistent with what both the roll-wide `FindDmin`
failure and the UI's own per-frame readout are reporting — no `captures/`
pixel data was read to reach this conclusion, only code, calibration
metadata, and the project owner's own aggregate percentile screenshot),
are almost certainly **not recoverable** by any software fix: clipped ADC
codes destroy the actual density information, not just its presentation,
and no downstream transform can reconstruct what was never digitised.

## 8 — What would actually fix this, for future B&W scans only

Nothing here should be read as "recompute past B&W captures correctly" —
per §7, that data is very likely gone on the clipped channels. For **new**
B&W scans, the fix is a real, separate with-film duty for the `BnW` film
path, which requires two things this investigation did not do and should
not fake:

1. **A real measurement.** The one number already in hand that's closer to
   correct than the current default is this unit's own fresh **open-gate**
   duty, `flat_field_on_counts_R_G_B = [643, 580, 508]`
   (`calibration/README.json`) — captured against an empty gate, i.e. zero
   base density, which is closer to a clear/lightly-tinted panchromatic
   B&W base than a colour-negative's orange mask is. It is very likely
   still not exactly right (real B&W stock has *some* base density and
   sensitivity curve, not zero), so the honest next step is a proper duty
   search analogous to `calib_wizard.py`'s existing `step_duty` (which
   already knows how to search `on_counts_R_G_B` against a target, just
   never against real B&W film) run with actual B&W negative in the gate,
   not against an empty aperture.
2. **Wiring `film_path` through to duty selection.** `ScanConfig` would
   need a second on-counts field (e.g. `on_counts_bnw`), `calibration/
   README.json`'s schema would need to carry it, and
   `lamp_switch_to_scan_duty` (`tools/pakon_scan.py:1021-1048`) would need
   to select between `cfg.on_counts` and that new field based on
   `cfg.film_path` — currently the one piece of film-type information that
   exists at scan time but is never read past the metadata sidecar (§3).

Neither of these was implemented here: (1) requires access to real B&W
negative stock and hardware time this investigation did not have, and (2)
without a real, measured target duty to wire in would just be plumbing a
guess. Implementing the wiring with a placeholder number would be worse
than the current explicit failure — it would silently under- or over-
expose future B&W rolls instead of refusing loudly the way this pipeline
does today. The refusal in the bug report, per §6, is the pipeline doing
its job correctly on genuinely bad input; the real fix is upstream, at the
light board, for the next B&W scan, not in this codebase's render path.
