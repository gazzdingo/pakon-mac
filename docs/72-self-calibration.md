# 72 — Calibrating a scanner nobody has ever seen

**Status:** blocker resolved and the cause proved on real data; the whole flow
implemented, wired to the backend and the UI, and exercised end to end against
the simulator. **No hardware was run by this work.** Every capture referenced
below already existed on disk.

**Scope note.** `calibration/` was not modified. No `pakon_scan.py run`, no
`calib_read.py read`, no lamp, no motor. The one live confirmation in §1 comes
from two captures the owner took himself while this was being written.

---

## 1. THE BLOCKER — verdict: a wire-encoding bug, not a physics problem

### 1.1 What was believed

> At the base-8 configuration the dark reference reads all zeros (mean 0.0,
> max 1), where the base-16 reference reads 1120/1443/1161. The working
> hypothesis is that the AFE offsets (−19/−26/−20) null the pedestal at base
> 8's shorter integration (2813 vs 4093).

### 1.2 The hypothesis is refuted by the data it was drawn from

Three findings, all from files already on disk:

**(a) Green and blue never changed.** The base-16 config is
`afe_gains [13,13,13]`, `afe_offsets [−18,−26,−20]`; the base-8 config is
`[15,13,13]` / `[−19,−26,−20]`. Green's offset (−26) and gain (13) are
**identical** in both, and so are blue's (−20, 13). Only red differs. Yet green
went 1443 → 0 and blue 1161 → 0 along with red. Offsets that did not change
cannot be what nulled those channels.

**(b) The base-16 pedestal is not integration-dependent.** Measured from
`calibration/dark_2000x3.npy`: per-channel spatial standard deviation
1.22 / 1.05 / 1.06 counts against means of 1120.5 / 1443.0 / 1160.9 — a spread
of **0.07 % to 0.11 %**. Integrated dark current carries per-pixel
non-uniformity of several percent. A pedestal that flat is an electronic DC
level, and shortening the integration by 31 % cannot remove 100 % of it. Even
if it were *entirely* dark current, proportional scaling predicts
770 / 991 / 797 at base 8 — not zero.

**(c) It is a hard rail, not a small number.** In
`calibration_new_20260812-071142/dark_2000x3.npy` exactly **one** of 6,000
pixel-channels is non-zero: pixel 0 of red, value exactly 1.0 — the line-sync
flag in bit 0, which `build_calibration.py` deliberately does not mask. Every
other pixel-channel is exactly 0.0, averaged over 33,226 lines. So every one of
~199 million samples was ADC code 0. Read noise around a genuinely small
pedestal cannot do that; only clipping can.

### 1.3 The actual cause

**The AD9826's offset register is nine bits of SIGN-MAGNITUDE with the sign in
bit 8. This port was writing two's complement.**

The AFE is an Analog Devices AD9826, identified from TLB.dll alone by four
independent alignments. `docs/42-ccd-analog-front-end.md` was removed from the
working tree by a `git filter-repo`, but survives — `git show
402729c:docs/42-ccd-analog-front-end.md` — and records the vendor's encoder,
`FN_bDrvPutCcdAtoDOffsets` at `0x100299c0`, `[VERIFIED-FROM-BINARY]`:

```
if (v <= -255) -> error path, no write        ; 0x100299dc  jle
if (v >=  255) v = 255                        ; 0x100299e4
mag = abs(v)                                  ; cdq / xor / sub
if (v < 0) mag |= 0x100                       ; 0x100299fc  or eax, 0x100
```

with an explicit warning that turned out to be a prophecy:

> **Not two's complement.** Magnitude in bits 0–7, sign flag in **bit 8**.
> Range ±255. A port that writes a two's-complement `int16` will program a
> large positive offset instead of a small negative one — which is exactly the
> kind of fault that yields a sensor that clocks but reads flat.

`tools/pakon_scan.py` did exactly that:

```python
link.ack(pc.adc_write(idx, int(o) & 0xFFFF), ...)
```

| requested | sent | AD9826 reads (low 9 bits) | actually applied |
|---|---|---|---|
| −18 | `0xFFEE` | `0x1EE` → sign 1, magnitude 238 | **−238** |
| −19 | `0xFFED` | `0x1ED` → sign 1, magnitude 237 | **−237** |
| −20 | `0xFFEC` | `0x1EC` → sign 1, magnitude 236 | **−236** |
| −26 | `0xFFE6` | `0x1E6` → sign 1, magnitude 230 | **−230** |

An offset roughly **twelve times** the intended one, on every channel at once,
in the direction that removes signal. That is what put the black level under
the ADC's bottom rail.

### 1.4 Why base 16 looked healthy and base 8 did not — it was never the base

The variable is not the DPI base. It is *when the capture was taken*.

| | |
|---|---|
| `captures/ref_dark.bin` written | **2026-08-07 07:34:27** |
| `captures/ref_bright.bin` written | 2026-08-07 07:43:57 |
| `tools/pakon_scan.py` first committed (`3e76674`) | **2026-08-07 15:36:38** |
| base-8 dark reference captured | 2026-08-12 |

At the commit immediately before `ref_dark.bin` (`4f9a842`, 07:33:19) the only
tools in the tree that touch register `0x84` are `init_ccd.py`, which writes
indices 5/6/7 as **literal 0**, and `start_acquire.py`, which writes gains only.

So the committed base-16 tables were measured with **the offset DACs at zero**,
and the base-8 reference was the first capture ever taken with them written —
and written wrongly. Both observations follow from one bug and neither has
anything to do with integration time.

A consequence worth recording: **`calibration/README.json`'s `afe_offsets:
[-18,-26,-20]` was never in force for the tables it describes.** It was
transcribed from the vendor registry, not measured from the capture. The
`config` block mixes measured settings with registry-transcribed ones and the
distinction was not visible.

### 1.5 Confirmed on the hardware, without running the hardware

While this was being written the owner took two base-16 empty-gate-ish captures
twelve minutes apart. The second one ran through the fix.

| | `captures/vf_bright.bin` 08:05 | `captures/vf_bright2.bin` 08:17 |
|---|---|---|
| `exposure.afe_offset_words` | *absent* (pre-fix) | `['0x112','0x11a','0x114']` |
| minimum sample R/G/B | **0 / 0 / 0** | 5121 / 4608 / 3840 |
| fraction of samples ≤ 1 | **0.65 % / 0.65 % / 0.70 %** | **0 / 0 / 0** |
| columns 0..5 (vignetted edge) | pinned at 0 | 5420 / 4842 / 4094 |

Same unit, same base, same integration, same nominal `afe_offsets`, same
on-counts. The only difference is the encoder. **The black level came back.**

And then, at 08:21, the owner rebuilt the whole calibration through the fixed
path — `calibration/README.json` now carries the `floor_fraction` field this
work added, so it came out of the new `build_calibration.py`:

```
dark means        990.1 / 670.6 / 610.6      floor_fraction 0 / 0 / 0
dark spatial std   64.0 /  34.6 /  29.8      (was 1.22 / 1.05 / 1.06)
bright level      57401                      no clipping
```

Two things to read off that. The pedestal is healthy and inside the
400–4000 band, and the offsets are now doing what the vendor meant them to do —
a *small* correction downward from the offsets-at-zero 1120/1443/1161, largest
on green, which carries the largest negative offset. And the spatial spread has
gone from ~1.1 counts to 30–64: **real per-pixel dark structure, which was
always there and could not be seen before.** It is now measurable and therefore
correctable, which is the whole purpose of a dark table.

### 1.6 Why a clipped pedestal is not cosmetic

The 46 pixel-channels that came back `bright <= dark` and forced the tables to
be hand-patched were **columns 0 to 17 and nothing else** — checked directly.
In the committed base-16 gain table those same columns read 4.4× to 24.5×: they
are the vignetted edge, the columns that see least light. They are the first
thing a clipped black level destroys, and in a real scan the next thing is the
deepest shadows. Dark subtraction cannot recover any of it, because the
per-pixel structure was never digitised.

### 1.7 What was changed

* `pakon_commands.afe_offset_word()` / `afe_offset_value()` — the vendor's own
  encoder, including its asymmetry: clamp at `+255`, **refuse** at `−255`
  rather than wrap.
* `pakon_scan.ccd_configure` uses it, and refuses rather than sending a value
  the vendor's own code would not send.
* The capture sidecar now records `afe_offset_words` and
  `afe_offset_encoding`, so a capture from before the fix can never be compared
  with one from after it on the strength of its `afe_offsets` field alone — the
  same field meant a different thing to the hardware.
* `build_calibration.check_dark_floor()` **refuses** a dark reference whose
  samples pile up on ADC code 0. This is the refusal that did not exist; it
  would have caught the whole thing before anything was hand-patched.

### 1.8 And the black level still has to be searched

Fixing the encoder does not make the offsets a constant. The vendor keeps
`Offset_R/G/B` **per `DpiBase` × film mode** — recovered values include
`DpiBase16_35\ColNegIr` −18/−26/−20, `DpiBase8_35\ColNeg` −19/−26/−20,
`DpiBase4_35\ColNeg_C41` −17/−25/−19 — and, like `Current_*` and
`DutyCycle_*`, **none of them are on the EEPROM at any offset** (docs/69 §5.4).
They are Calibration Wizard output. So the black level joins the lamp duty as
something a second owner can only obtain by measuring it, and it is measured
first, because every number the lamp search produces is a number above it.

`build_calibration.py solve-offset` does the solve, and refuses to assume a
direction it has not measured: the sign the committed calibration exhibits
(more-negative register → higher pedestal) is suggestive but comes from three
*different channels*, so it is not a calibration of anything.

---

## 2. The flow, and what the operator sees

The original brief specified a wizard with a "remove the film" prompt and a
Calibrate button. The owner corrected it mid-flight and was right: the hardware
already reports whether the gate is empty, so the common case needs no prompt
and no button. **§2.2 is a further correction to that correction**, forced by
the measurements.

### 2.1 States

| state | what the operator sees | control offered | device traffic |
|---|---|---|---|
| `ready` | "This scanner is calibrated." | none | **none at all** |
| `needs-calibration` | "Setting this scanner up. This runs by itself." | none | starts by itself |
| `running` | the current step and a progress bar | none | yes |
| `film-in-gate` | **"Remove the film to finish setup."** | one button, "I have taken the film out" | stopped |
| `ambiguous` | "Which one is plugged in?" | one button per stored serial, **no default** | none |
| `unreachable` | the lamp cannot reach the target | the full report (§2.4) | stopped |
| `failed` | why, in one sentence | none | stopped |
| `done` | "Calibrated. This scanner will not need to do that again." | none | none ever again |

Exactly two states expect anything of a person, and one of them
(`ambiguous`) exists only when two scanners have been calibrated on one
computer — which nothing on the wire can disambiguate, because every F-135
reports the same USB `iSerialNumber` (docs/69 §3).

### 2.2 How the machine decides the gate is empty — the signals are NOT symmetric

This is the part that is easy to get wrong, and the brief's assumption about it
was wrong. From the owner's own 2026-08-12 pair:

| | film loaded (`vf_bright`) | empty gate (`vf_bright2`) |
|---|---|---|
| `film_sense.available` | `True` | **`False`** |
| `film_sense.present` | `True` | `None` |
| `film_sense.status_reports` | 244 | **0** |
| `run_detector.state` | `film` (9,984 film lines) | `clear` (19,712 clear lines) |

**An empty gate produces no sensor opinion at all.** The DX board's status
nibble rides on record 0 of a DX packet; an idle transport queues no events, so
there is no nibble. Therefore:

* treating "sensors unavailable" as *ask the human* would put a prompt in front
  of precisely the case that is supposed to be silent;
* treating it as *assume empty* would eventually calibrate through film.

It is neither. It is **undetermined**, and the gate classifier is what settles
it. So:

1. **No-motion DX poll first** (`calib_wizard.film_precheck`, bounded at 2 s,
   light-board register reads only). If it positively says film, the motor
   never turns.
2. Otherwise the short lamp-on probe the duty search needs anyway. Its live
   `window` events are the gate classifier; its own DX polling is the sensors
   again, this time with the transport moving.
3. Film from either one stops the capture **mid-run** (SIGTERM, so
   `pakon_scan`'s handler still stops the transport and the lamp) and nothing
   is stored.

The sensors win when they speak; the classifier decides when they do not; and
with neither the answer is `None`, never `False`. Six checks in
`tools/test_calib.py` pin exactly this, including the case where the two
disagree.

One more asymmetry, found in simulation and fixed: **the classifier's opinion
is only meaningful with the lamp on.** With the lamp off every window is dark
by construction, and an early version aborted a perfectly good black-level
capture reporting film that was not there.

### 2.3 The steps

| step | hardware | what it produces |
|---|---|---|
| gate | register reads only | is the gate empty |
| EEPROM | one I2C read, once per scanner ever | serial + colour matrices + pedestals |
| black level | short lamp-off captures | `afe_offsets` |
| lamp duty | short lamp-on captures | `on_counts_R_G_B` |
| dark reference | ~15,000 lines, lamp off | per-pixel dark |
| bright reference | ~8,000 lines, lamp on | per-pixel gain |
| build | none | `dark_2000x3`, `gain_2000x3`, `README.json` |
| store | none | all of it, under that serial |

The two references are captured from **one `config` dict that is not touched
between them**. `build_calibration.check_config` compares the two sidecars on
eleven exposure-defining keys and refuses on any disagreement.

The exposure target is a **maximum**, not a mean — docs/15 records that the
vendor's check compares "the maximum pixel of an averaged CCD line". Aiming the
*mean* at 64000 on this unit pins about three quarters of the illuminated field
at the rail. `build_calibration` grew a `--metric {max,level}` switch defaulting
to `max`; `level` is kept because the 2026-08-07 tables were judged on it and
docs/71 is written in those terms.

### 2.4 An unreachable target is reported, never clamped

Verified by running it (§4). Verbatim:

```
channel(s) R are already at the PWM ceiling of N-2 = 980 and still short of
the 64000 target. The lamp cannot be driven for longer than the line period,
so more duty is not available.

This is what an aged LED looks like, and it is not a failure of the search.
The legitimate response is to raise the LED CURRENT for those channels --
levels_R_G_B_Ir, the vendor's Current_* -- which raises the peak the duty is
a fraction of. With IR off the hardware clamps them at R<=4, G<=20, B<=20
(fcn.100203c0), and the current levels are [4, 20, 11, 0].

Nothing has been stored and nothing has been clamped silently. Calibrating at
a lower target is also valid -- the gain table is a ratio and normalises out
-- it simply uses less of the ADC range.
```

Raising `Current_*` automatically was deliberately **not** implemented: it
raises peak LED current on somebody else's hardware, and the report gives a
person everything needed to decide.

### 2.5 Nothing automated writes into `calibration/`

Each candidate exposure is written under the calibration store and handed to
`pakon_scan.py run --cal-dir`, which is new. The repo's `calibration/` is read
only, for the borrowed gate reference. A test builds a `Wizard` and asserts
that every directory it would write to is outside `calibration/` and inside the
store — behavioural, not a grep, because a grep is satisfied by renaming a
variable and trips over a module merely discussing the subject.

Finished tables go to `<store>/units/<serial>/flatfield/<stamp>/`, append-only.
`save_flatfield` refuses a partial set (a new dark table beside an old gain
table is not a partial calibration, it is a wrong one that loads without
complaint) and assembles into a uniquely-named directory then renames, so a
crash mid-copy cannot leave a half set. It contains no delete path, which
`test_calib.py` enforces by reading the module's own source.

---

## 3. Files changed

| file | change |
|---|---|
| `tools/pakon_commands.py` | `afe_offset_word` / `afe_offset_value`, `ADC_IDX_OFFSET_*`, `ADC_OFFSET_MAX/SIGN`; the AD9826 identification recorded; stale "INFERRED channel order" comments corrected |
| `tools/pakon_scan.py` | **the encoder fix**; `afe_offset_words` in the sidecar; `--cal-dir`; `from_calibration(config=, source=)` split and `from_store()` (docs/69 §7.5) |
| `tools/build_calibration.py` | `check_dark_floor` refusal; `floor_stats`/`is_floored`; `--metric max\|level` (default `max`) and `channel_maxima`/`peak_over`; `solve-offset`; black level recorded in the README |
| `tools/calib_store.py` | `save_flatfield` / `flatfield` / `flatfields` / `has_flatfield_for` — per-serial measured tables, append-only |
| **`tools/calib_wizard.py`** | **new.** The whole flow: `assess`, `plan`, `film_precheck`, `verdict_from_run`, `Wizard`, CLI `status` / `plan` / `run` / `selftest` |
| `tools/pakon_app.py` | docs/69 §7.1–7.3 applied (`resolution`, `profile`, `units`, `setup`; the ambiguity branch; `select` by serial); `POST calibration/run` + `job_calibrate` |
| `app/src/api.js` | `calibrationRead`, `calibrationSelect`, `calibrationRun`, `SETUP` |
| `app/src/Info.jsx` | the "not implemented" stub replaced by a live `Setup` card that starts by itself |
| `tools/test_calib.py` | 50 new checks; **191/191 pass** |
| `docs/72` | this file |

`calibration/` — **not touched.** `calib_read.py` — **not touched**; its
ordering and refusals are load-bearing and the wizard calls `do_read` through
the front door.

---

## 4. What was verified, and how

* `build_calibration.py selftest` — **PASS**, still reproduces the 2026-08-07
  tables **bit-identically**, verified against
  `calibration/*.pre-recal-20260812.*`. The metric and refusal changes are
  additive.

  Run against the tables installed at 08:21 it now FAILS, and **that is the
  check working**, not a regression: it compares the 2026-08-07 captures with
  the installed tables, and the installed tables are no longer built from them.
  Two other selftests fail for the same single reason and are worth stating
  plainly so nobody hunts for a bug —

  | selftest | symptom | cause |
  |---|---|---|
  | `build_calibration selftest` | four "bit-identical" checks fail | installed tables are a different set |
  | `pakon_gate selftest` | "reconstruction is biased", +6714 counts | ditto; docs/71 §9 predicts exactly this after installing |
  | `pakon_scan selftest` | `dark-stops` never exits | `captures/ref_dark.bin` classifies as **film** under the new tables (new dark level 759 vs the capture's 1241) |

  All three are the 2026-08-07 reference captures being from a superseded
  exposure. Fixing them means retaking `ref_dark.bin` / `ref_bright.bin` at the
  current configuration, or pinning a calibration inside the selftests so they
  stop depending on whatever is installed. See §6.
* `tools/test_calib.py` — **191/191**, up from 141.
* `tools/pakon_scan.py selftest` — **PASS** with the encoder fix in place
  (every stop path, including SIGKILL recovery).
* `cd app && npm run build` — clean.
* `python3 -m py_compile` on every Python file touched.
* **End to end against the simulator**, replaying the 2026-08-07 references
  through the real subprocess capture path: gate → EEPROM (resolved from the
  store, no device read) → black level (settled first round at
  1120.2/1443.3/1160.8, not floored) → lamp duty → dark reference → bright
  reference → build → store. Final state `done`, tables written under serial
  16275 with dark means 1120.5/1443.0/1160.9, floor fraction 0/0/0, and gain
  means 1.0956/1.1102/1.1283 — the known-good numbers. `calibration/`
  unchanged.
* The `film-in-gate` and `unreachable` branches were both reached and their
  reports read (§2.4).

---

## 5. What still needs a human

Two things, and only two.

1. **Take the film out**, if it is in. One sentence, one button, and the run
   continues by itself. On a scanner that is plugged in empty — the normal
   case — nobody is asked anything.
2. **Say which scanner is plugged in**, and only when two have been calibrated
   on the same computer. Unavoidable: every F-135 reports the same USB serial
   descriptor, and the per-unit serial is on the EEPROM page that must not be
   re-read (docs/69 §3). One click, and only ever once per swap.

Plus one that is a hardware fact rather than a question: **power-cycle the
scanner before the first calibration.** The EEPROM read needs a fresh power
cycle and `PowerCycleGuard` will refuse without one. It is refused clearly, not
silently, and only ever matters once per scanner.

---

## 6. Before a second owner's scanner genuinely works end to end

Ordered by what stands between here and a correct scan on a unit that is not
this one.

1. **Run it on this scanner, once.** Everything is verified in simulation and
   against captures already on disk; the searches have never driven a real
   lamp. The first live run is the real test, and the honest procedure is:
   power-cycle, empty gate, `python3 tools/calib_wizard.py run --json`, and
   read the measurements it prints before believing any of them. Expect the
   black-level step to need two rounds on a scanner whose offsets have never
   been set, because the first round only measures where the level *is*.
2. **The black-level slope has never been measured on hardware.**
   `solve_offset` refuses to extrapolate through a slope it has not seen, so
   the failure mode is a refusal rather than a wrong number — but the size of
   one AD9826 offset step in wire counts is still unknown, and the first live
   run is what determines it. Record it here when it is known.
3. **`calibration/README.json`'s `afe_offsets` are not what its tables were
   measured at** (§1.4). Harmless today because the black level is now
   searched rather than copied, but the file says something untrue and should
   be corrected — with a timestamped backup, per the standing rule — the next
   time it is touched.
4. **The reversal matrix is still six coefficients short**, and the motor
   constants and the true serial are still on EEPROM pages nothing has read.
   Unchanged by this work; docs/69 §5.6 has the procedure and it is not
   implemented.
5. **Auto-start currently fires when the Setup card is on screen**, not at app
   launch. That was deliberate caution about starting hardware from a render in
   an app the owner is actively using; promoting it to launch is a few lines in
   `App.jsx` once the first live run has been watched.
6. **`line_rate_0x91` is not recomputed when integration changes.** The triad
   doctrine (docs/46 §3) says integration, lamp N and `0x91` are one setting in
   three registers, and `ScanConfig` recomputes the first two and passes the
   third through. At base 8 the formula wants ≈ 88, not 60. It did not matter
   here because the wizard calibrates at base 16, where 60 is correct — but it
   is a live inconsistency and it belongs in whatever work moves the wizard to
   another base.
7. **Three selftests now depend on a superseded calibration** (§4). The
   cheapest fix is to retake `captures/ref_dark.bin` and `ref_bright.bin` at
   the installed configuration — they are the same two captures the wizard
   takes anyway, so a wizard run produces them as a side effect. The better
   fix is to give `pakon_gate` and `pakon_scan`'s selftests a pinned
   calibration of their own, so that installing a new one stops breaking
   tests that are not about it. Until then those three failures are expected
   and are not evidence of anything.

8. **`docs/60-calibration-safety.md` is still cited eight times and still does
   not exist** (docs/69 §8.5). Unchanged.
