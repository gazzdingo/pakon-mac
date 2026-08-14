# 71 — Rebuilding the per-pixel dark and gain calibration

**Status:** tool written and verified against the committed tables; capture
procedure specified but **not executed** — it needs hardware and this work was
software only.

**Scope note.** Nothing here touched hardware. No USB device was opened, no
lamp was driven, no motor was spun, and `calibration/` was not modified. Every
number below comes from captures already on disk, from static reading of
`pakon_decode.py` / `pakon_gate.py` / `pakon_scan.py`, and from one live
measurement supplied by the owner (§4).

---

## 1. What was missing

`calibration/dark_2000x3.npy` and `gain_2000x3.npy` were produced ad-hoc on
2026-08-07. The only record of how was the message of commit `8c9bcf1`. That is
not a procedure — nobody could regenerate the tables, and they now need
regenerating, because the lamp drive has changed and the tables are valid only
for the exposure they were captured under.

`tools/build_calibration.py` is that procedure, written down and executable.

There is a second reason it matters. The lamp values live only in the Windows
registry and are **not recoverable from the EEPROM**. A second owner's F-135
therefore has no duty cycles to copy — the only way to get them is to search
for them against the scanner's own response, which is what the vendor's
calibration wizard does and what `solve` (§5) does here.

---

## 2. The formula, corrected

Commit `8c9bcf1` recorded:

```
dark = mean down the strip                    (2000 x 3)
gain = flat.mean() / (bright - dark)          (2000 x 3)
corrected = (raw - dark) * gain, then clamp to 14 bits
```

`flat.mean()` reads as one scalar over the whole array. **It is not.** Each
channel is normalised by its own mean:

```
dark[px, ch] = mean over lines of the raw wire word
flat[px, ch] = mean over lines of bright  -  dark
gain[px, ch] = flat[:, ch].mean() / flat[px, ch]     <- per channel
```

That matters: per-channel normalisation makes each channel's gain average ~1
and **preserves** the R/G/B balance set by the lamp duty and the AFE gains,
rather than folding it into the gain table. Using one global scalar reproduces
the committed tables only to within 0.6 %, per channel, in a constant ratio —
which is how the discrepancy was pinned down. The per-channel constants are the
committed `flat_field_k`:

| channel | `flat[:, ch].mean()` |
|---|---|
| R | 49084.0485 |
| G | 48519.2461 |
| B | 48755.3779 |

Their mean, 48786.2, is the single scalar `pakon_gate.Gate.from_calibration`
derives for its thresholds — a different and looser use, and not the gain
normaliser.

### 2.1 The domain

The tables are stored in the **EP 0x86 wire u16** domain, recorded as
`"domain": "wire_u16"`. The two consumers deliberately disagree and both must
keep working:

| consumer | expects |
|---|---|
| `pakon_decode.load_unit_calibration` | multiplies dark by `0.25` on load, because `to_rgb14` already did `>> 2` |
| `pakon_gate.Gate.from_calibration` | uses the table **as-is**, because it classifies raw wire lines |

So build from wire words. Do **not** shift, and do **not** mask the sync flag
in bit 0 — the committed tables did not, and matching the domain the consumers
expect matters more than the one count of bias that flag puts on the first
pixel of red. Gain is a ratio and is therefore domain-independent.

Segmentation goes through `pakon_decode.load_u16` / `segment_lines`. Never a
hand-rolled word de-interleave: sync and phase correctness is not obvious from
a hex dump, and getting it wrong in this project has produced confidently-wrong
answers before.

---

## 3. Verification — the tables reproduce bit for bit

The 2026-08-07 source captures are still on this machine, so the formula could
be checked against its own output rather than argued about:

```
$ python3 tools/build_calibration.py selftest
  dark   14482 lines, 0 losses
  bright 7626 lines, 0 losses

  PASS  dark lines   == 14482
  PASS  bright lines ==  7626
  PASS  dark losses   == 0
  PASS  bright losses == 0
  PASS  dark_2000x3.npy bit-identical
  PASS  gain_2000x3.npy bit-identical
  PASS  dark_2000x3.csv byte-identical
  PASS  gain_2000x3.csv byte-identical
  PASS  clipping check passes the known-good bright reference
SELFTEST PASS
```

Line counts, loss counts and per-channel means all match `README.json` exactly
(dark 1120.5/1443.0/1160.9, bright 50204.6/49962.2/49916.2), and a full `build`
run through the real code path produces all four files **byte-identical** to
what is committed. That is the strongest available evidence that both the
formula and the domain handling are right.

`.csv` twins are formatted from the float64 values (`%.2f` for dark, `%.6f` for
gain), not from the float32 that goes into the `.npy` — those round differently
in the last digit. The point of the `.csv` files is that the calibration stays
readable without numpy, so that format is fixed by what is already committed.

---

## 4. The exposure target: 64000, and why this unit cannot reach it

The vendor does not calibrate at whatever duty happens to be set. Its wizard
**searches** the per-channel LED duty until the empty gate reads a target, then
calibrates there — `FN_bCalibrateFindLedCurrent`, target **G = 64000** (docs/42,
quoted in `pakon_framing.py`, which derives `DetectWhite_G = 61000` and
`DetectFilm_G = 54000` as fractions of it). 64000 is therefore the tool's
default target, and the historical ~50000 is a superseded default, not a rule.

But 64000 is a target for the **level** — the mean over the illuminated columns
— and **this unit cannot reach it without clipping.** Measured on
`captures/ref_bright.bin`:

| quantity | value |
|---|---|
| level (mean over illuminated columns 28..2000) | 50587.1 |
| brightest single sample over those columns | 55986 |
| peak / level | **1.1067** |
| highest clip-free level (peak 1000 below the 65535 rail) | **≈ 58312** |

At a level of 64000 the brightest sample would read 64000 × 1.1067 ≈ **70830**
against a 65535 rail. The top of the PRNU distribution would be pinned, where
bright-minus-dark understates the true signal and the computed gain is wrong in
the direction that brightens those pixels further. The vendor's target assumes
a flatter field than this unit has: its spread is 10.7 % above the level, and
the rail leaves only 2.4 %.

**This is not hypothetical.** At the vendor Base-8 `ColNeg` duty now in
`calibration/README.json` (on-counts 672/640/564, N 675, integration 2813), the
owner measured an empty-gate clear level of **65477** — hard against the rail,
so that figure is a *lower bound* on a value that is already clipped.

Fitting the linear model of §5 to `ref_bright.bin` and scaling by the
integration ratio (2813/4093) says how far over it really is:

| channel | predicted true base-8 level | vs rail |
|---|---|---|
| R | ≈ 68,900 | 1.1× |
| G | ≈ 132,900 | 2.0× |
| B | ≈ 268,600 | 4.1× |

Consistent with the hard-clipped measurement, and the reason the back-off in
§5.1 bisects instead of solving. **The registry duties overshoot badly on this
unit and must come down.**

> Caveat, stated plainly: the model above ignores the change in `Current_*`
> levels (G 20→18, B 11→10) and AFE gain (R 13→15) between the two
> configurations, so the predicted levels are indicative, not exact. The
> conclusion — massively over the rail, bisect — does not depend on the
> precision.

---

## 5. `solve` — the duty search

The vendor's relationship, recorded in `calibration/README.json`:

```
on_ch = floor(N_float * duty_ch),  clamped to <= N - 2,  N_float = integration * 0.24
```

The LED is a current source pulsed at fixed peak, so illumination — and
therefore signal above dark — is linear in duty:

```
level_ch = dark_ch + K_ch * duty_ch
```

One measurement at a known duty gives `K_ch`, and the duty for any target
follows. `solve` is a one-shot solve rather than the vendor's iteration because
the relationship is linear and all three channels are measured at once; the
operator still re-probes to confirm, which is the part of the search that
matters.

```
python3 tools/build_calibration.py solve --bright captures/probe_bright.bin
```

It prints three things and lets a human choose: the on-counts that hit the
requested target, the highest clip-free level this unit's measured PRNU allows,
and the on-counts that hit *that*. It refuses to pretend 64000 is reachable
when the measurement says it is not.

`--dark` supplies a matching dark capture; without it the installed dark table
is used, which is a good stand-in because the dark level is AFE offset and read
noise and barely moves with lamp duty.

### 5.1 A clipped probe bisects, it does not solve

A clipped reading is a lower bound, so any scale factor derived from it is an
over-estimate — and a *saturated* probe carries almost no scale information at
all. From the live 65477 measurement, scaling to a 45000 target gives
(45000−1241)/(65477−1241) = 0.68, which per §4 would leave G and B still
clipped, and the next round would repeat the mistake.

So `solve` takes **the smaller of a straight halving and the model-implied
scale**. Halving cannot be fooled: it converges from any overshoot in
log2(overshoot) rounds, which for 4.1× is two. From the current duty it
recommends `[336, 320, 282]`.

Repeat until the probe comes back unclipped; then the linear solve lands it in
one step.

---

## 6. The procedure

**Film is OUT of the gate for every capture here.** Both references are
empty-gate; the only difference between them is the lamp. Close the lid.

### Step 1 — probe, and settle the duty

```bash
python3 tools/pakon_scan.py run captures/probe_bright.bin \
    --base 8 --no-dx --max-bytes 24000000

python3 tools/build_calibration.py solve --bright captures/probe_bright.bin
```

If it reports the probe is clipped, edit `on_counts_R_G_B` in
`calibration/README.json` to the on-counts it prints, and repeat. Expect about
two rounds from the current Base-8 duty. When it reports an unclipped probe,
set `on_counts_R_G_B` to the recommended value and go on.

`--base 8` matches the `DpiBase8_35` now in `calibration/README.json`, so
`ScanConfig.from_calibration` reads the committed base-8 triad directly and no
`--force` is needed. Base 8 decodes to the same 6000-word lines as base 16
(`DECODABLE_BASES`), so the table geometry is unchanged.

### Step 2 — the dark reference (lamp OFF, ~14,000 lines)

```bash
python3 tools/pakon_scan.py run captures/ref_dark.bin \
    --base 8 --no-lamp --no-dx --max-bytes 180000000
```

`--no-lamp` runs the transport with the lamp off and suppresses the gate's DARK
stop, which would otherwise fire immediately and correctly.

### Step 3 — the bright reference (lamp ON, empty gate, ~7,600 lines)

```bash
python3 tools/pakon_scan.py run captures/ref_bright.bin \
    --base 8 --no-dx --max-bytes 96000000
```

Roll-end cannot stop this run — it only arms after film has been seen
(`pakon_gate` line 483, `s.seen_film and s.clear_run >= roll_end`) and no film
ever enters the gate. The byte limit is what ends it.

**Do not touch the gate, the lamp, or any exposure setting between steps 2 and
3.** A dark and a bright reference from different setups produce a table that
is silently wrong, not noisy. The tool refuses if the two sidecars disagree.

Byte budget: one 3-channel line is 6000 words = 12,000 bytes, so
`--max-bytes N` ≈ N/12000 lines. 180 MB ≈ 15,000 lines; 96 MB ≈ 8,000.

### Step 4 — build

```bash
python3 tools/build_calibration.py build \
    --dark captures/ref_dark.bin \
    --bright captures/ref_bright.bin \
    --out calibration-build/$(date +%Y%m%d-%H%M%S)
```

### Step 5 — read the numbers, then install by hand

The tool prints the new per-channel means beside the previous ones, the gain
ratio per channel, any exposure change, and a `pakon_gate.Gate` reconstruction
proving the second consumer still accepts the set. It installs nothing. When
the numbers look right, run the `cp` commands it printed.

---

## 7. Telling a good reference from a bad one

| check | good | bad |
|---|---|---|
| sync losses | **0** on both | any non-zero — re-capture, don't `--allow-losses` |
| lines | ≥ 4,000; 14,482 / 7,626 historically | < 2,000 is refused: read noise ends up in the table |
| bright vs dark | swing ≈ 48,000 wire counts per channel | < 4,000 refused — lamp off, dying, or the same capture twice |
| clipping | 0 samples at/above 65408 | any channel > 0.01 % — the gain is wrong at the ceiling |
| level | near the clip-free ceiling (~58,000 here) | far below it: valid, but wastes ADC range and carries more noise |
| illuminated columns | ~28..2000 | a narrow span means the light path is blocked |
| gain | min ~0.9, mean ~1.1, max ~25 at the far edge | any non-positive or non-finite value is refused |

The edge columns legitimately have large gains — column 0 is ~17–25× because it
sees a fraction of nominal light. `pakon_gate` excludes columns whose mean gain
exceeds `EDGE_GAIN_LIMIT = 1.5`, which is how it arrives at valid columns
38..2000.

---

## 8. What `build` refuses

A bad table does not announce itself; it silently corrupts every subsequent
scan. These refuse rather than warn:

- either capture has sync losses (`--allow-losses` overrides, loudly)
- either capture is 4-channel/IR — the IR plane is **not** a 4-way interleave
  (3N interleaved visible words then N contiguous IR words, see
  `pakon_decode.to_rgb14`) and unpacking it as one would produce a table that
  looks fine and is wrong. Digital ICE calibration is separate work.
- either capture has no `.scan.json` sidecar — absence of evidence that the
  exposures matched is not evidence that they did
- the two sidecars disagree on any exposure-defining key
- bright is not meaningfully above dark on any channel
- any pixel has a non-positive or non-finite flat value
- the bright reference clips
- the output directory already holds a table set, or is `calibration/`

---

## 9. Installing — never overwrite

The standing rule is that a calibration is never deleted, only timestamped.
`calibration/` already holds `README.pre-dutyfix-*.json` and
`README.pre-vendor-base8-*.json` on that convention; this extends it to the
tables themselves, which have never been rotated because they have never been
rebuilt. `build` prints the exact commands, of the form:

```bash
# back up what is there now (never deleted, only timestamped)
cp calibration/dark_2000x3.npy calibration/dark_2000x3.pre-LABEL-TIMESTAMP.npy
cp calibration/dark_2000x3.csv calibration/dark_2000x3.pre-LABEL-TIMESTAMP.csv
cp calibration/gain_2000x3.npy calibration/gain_2000x3.pre-LABEL-TIMESTAMP.npy
cp calibration/gain_2000x3.csv calibration/gain_2000x3.pre-LABEL-TIMESTAMP.csv
cp calibration/README.json    calibration/README.pre-LABEL-TIMESTAMP.json

# install the new set
cp OUT/{dark_2000x3.npy,dark_2000x3.csv,gain_2000x3.npy,gain_2000x3.csv,README.json} \
   calibration/

# confirm both consumers still load
python3 tools/pakon_gate.py selftest
```

Nothing that follows a timestamped-backup naming pattern is picked up by any
loader: `pakon_decode.calibration_names` and `Gate.from_calibration` both use
exact filenames, and nothing globs `calibration/`.

`--label` names the backup. Existing labels describe the change being made
(`pre-dutyfix` = "the README before the duty fix").

After installing, `pakon_gate.py selftest` will report a reconstruction error
against `captures/ref_bright.bin` — **expected**, because that capture is from
the old exposure and the new tables are not for it. Judge the new set on
`build`'s own Gate reconstruction instead.

---

## 10. Not verified without hardware

Stated plainly, because the rest of this document is verified and these are not:

1. **No capture command in §6 was executed.** The flags were read out of
   `pakon_scan.py`'s parser and its `cmd_run` body; the claims that `--no-lamp`
   suppresses the DARK stop (`res.dark_stop_suppressed = not lamp`) and that
   roll-end cannot arm without film are read from source, not observed.
2. **The line-count-to-byte-budget mapping** is arithmetic on a 12,000-byte
   line, not a measured throughput.
3. **The linear duty model** (§5) is verified only in that it reproduces the
   relationship implied by one capture and is consistent with the owner's live
   65477 reading. It has never been checked by setting a duty and measuring
   the result — which is exactly what step 1 does, and why step 1 iterates
   rather than trusting the first solve.
4. **The clip-free ceiling of ~58,312** is measured from `ref_bright.bin`'s PRNU
   at the old exposure. The spread should be a property of the optics and
   sensor rather than the drive, but a new bright reference will re-measure it,
   and `build` reports the number it actually saw.
5. **4-channel/IR calibration** is refused, not implemented.
