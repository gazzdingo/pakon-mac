# 63 — Both of `docs/61`'s localisation findings are withdrawn

**Date: 2026-08-13.** `docs/62` flagged two harness problems in `docs/61`. Both
are correct. I had independently caught the second one minutes before that
message arrived, on the fixture test below, so this confirms from two sides.

## 1. The probe measured the wrong branch

`AnselEngine.shasta_stand_in` defaults to **False** (`pakon_ansel.py:510`), and
every production entry point sets it **True**:

```
pakon_decode.py:1520   engine.shasta_stand_in = True
pakon_render.py:604    eng.shasta_stand_in = True
test_render_f135.py:63 eng.shasta_stand_in = True
```

`pakon_stage_probe.py` called `AnselEngine.load()` and never set it, so it
measured the **assembled Shasta tone-LUT** branch — which no real F-135 render
takes.

Re-run on the production branch, same input:

| | assembled Shasta (what `docs/61` measured) | production stand-in |
|---|---|---|
| tone stage | `SHASTA apply (real)` | `TONE two-anchor STAND-IN` |
| R out p1 / span | 1553 / 828 | **0 / 4095** |
| G out p1 / span | 1493 / 991 | **0 / 4095** |

So **"the tone stage floors at ~1460 and compresses span 2.5×" was a property
of the branch I accidentally selected, not of the pipeline.** On the real path
that stage produces a full-range result.

That also kills `docs/61`'s structural conclusion — "we are running a tone stage
the vendor does not run at all". Production runs `shasta_two_anchor_tone`, which
is the stand-in *for* `analyzeAutoTone`, not Shasta. The framing was wrong.

`docs/62` also notes their side gets the same 60-120 washed-out floor on the
correct path across several real rolls, established before my branch existed.
**The defect is real; my localisation of it was not.**

## 2. The inversion clipping was an input artefact

`docs/61` reported `f135_rom12_to_rpd12` driving B to `p50 = 4095`. That came
from `rawAA005` (PSI's 8-bit export) scaled ×16 as a stand-in for RPD12.

The formula is

```
dens = 1000 * ( log10(base - ped) - log10(max(lin - ped, 1)) )
```

with per-channel pedestal `c9 = (159.59, 444.75, 635.54)` — a constant in the
**real linear 12-bit domain**. Scaled 8-bit blue has `p50 = 560`, which is
*below* the 635.54 pedestal, so `max(lin - ped, 1)` floors for more than half
the channel and every one of those pixels lands on the same clipped maximum.

Tested against the repo's own valid fixture (`synthetic_negative` → `_rpd16` →
`rpd16_to_rpd12`):

```
poly pedestal c9        = [159.59 444.75 635.54]
valid lin12 p1/p50/p99  = R [276 1739 3125]  G [523 1571 2686]  B [701 1498 2228]
  pixels below pedestal : R 0.00%   G 0.00%   B 0.00%
  clipped at 4095       : R 0.000%  G 0.000%  B 0.000%
```

Zero, on all three channels. `docs/62` reports the same from real 14-bit sensor
data across multiple rolls. **There is no clipping bug in the inversion.**

## What survives from `docs/61`

* **The SRA correction.** The port never applies the forward LUT on the live
  path — `pakon_ansel.py:795` is inside the fallback `else:` at 789, and
  `setshifts_out` is set in production. `docs/62` reaches the same conclusion
  from static disassembly. Two independent routes.
* **The vendor transfer curve.** The raw/render pairs are pixel-registered
  (peak |corr| 0.90 at `dy=dx=0`), so the vendor's end-to-end transform is
  measurable per channel per code value with no instrumentation. Untouched by
  any of the above, and still the most directly useful artefact.
* **The polarity trap.** `render_scene` does not invert;
  `f135_rom12_to_rpd12` does, before it. Calling `render_scene` directly on
  negative data gives output correlating +0.99 with its own input.
* **The tool**, now fixed: it sets `shasta_stand_in = True` to match
  production, and `--assembled-shasta` opts into the other branch explicitly
  and says so in the banner.

## The lesson, since `docs/60` has a traps section

Three harness bugs in one session, all of the same shape: **the rig was wrong in
a way that produced a plausible, alarming, publishable-looking result.**

1. Wrong input polarity → "the port doesn't invert the negative" (+0.99 corr).
2. Wrong input domain → "the inversion clips half the blue channel".
3. Wrong code branch → "the tone stage floors at 1460 and halves the span".

Each looked like a major finding. None was. The common failure is calling an
engine's internals directly instead of through the entry point production uses,
and feeding it data that is only approximately in the right space.

**Rule for anyone using `pakon_stage_probe.py`:** before believing a number it
prints, check the banner line. If `shasta_stand_in` is not `True`, or the input
is not real RPD12, the numbers describe a configuration nobody ships.

For measurements that must be trusted, drive `pakon_render.render_frame` or
`pakon_decode`'s own path and tap inside — do not assemble the chain by hand.
