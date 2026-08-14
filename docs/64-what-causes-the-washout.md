# 64 — What causes the washout

**Date: 2026-08-13.** The answer, with the evidence, after three wrong ones
(`docs/58`, `docs/61` ×2, all withdrawn — see `docs/63`).

## The cause

**The tone stage is a straight line where the vendor has a five-knot curve.**

The port runs `shasta_two_anchor_tone` (`pakon_ansel.py`), flagged
`SHASTA_TWO_ANCHOR_PORTED = False  # shape is ours; only the aims are vendor`.
Its own docstring is explicit about what it is not:

> This reproduces two anchors only — `shadowPercent` → `black`, median →
> `metricGray`, **straight line between them**, clamped to
> `[minValue, maxValue]`. Constants are the dpi's; the shape is not.

The vendor, by contrast, builds its curve from **five measured statistics**:

```
extShadowPercent   0.1        blackButtons        10.466
shadowPercent      1.0        shadowButtons        6.67
scene grey                    highlightButtons     3.67
highlightPercent  99.0        extHighlightButtons  7.68
extHighlightPercent 99.9      codeValuesPerButton 75.0
```

each moved toward an aim placed in *buttons* either side of `metricGray`, with
**per-knot aggressiveness factors, exponential slope limits and white-point
compression**. None of that is reproduced.

## Why that produces exactly this defect

The stand-in's two anchors are the **1st percentile** and the **median**. So:

* **Nothing anchors the deep shadows.** The vendor's `extShadowPercent = 0.1`
  and `blackButtons = 10.466` place a knot `10.466 × 75 ≈ 785` code values below
  `metricGray` specifically to pull the bottom of the range down to black. The
  port's lowest anchor is p1 mapped to `black`, and everything below p1 clamps
  flat. **The floor cannot go lower than that anchor, which is the washout.**
* **Nothing compresses the highlights.** Above the median the port linearly
  extrapolates to a clamp; the vendor rolls off with slope limits and
  white-point compression.
* **It runs per channel**, which a vendor tone scale does not — a second,
  separate defect that also shifts colour.

This matches the measurement precisely. Against the vendor's own curve, ours
tracks at the extremes and diverges most in the **midtones-to-shadows**: the
vendor keeps falling toward black while ours flattens around 165-180 and stops.
That is the signature of a missing curve shape, not of clipping or scaling.

## It is a known, planned gap — not an oversight

`docs/66-autotone-port-plan.md` on public `main`:

| Phase | What | Status |
|---|---|---|
| 1 | Orchestration shell | done, Unicorn-golden |
| 2a-2f | All six tone subsystems | **closed 2026-08-11** |
| 3 | `citras`-apply (218 fn / 86,062 B) | **not started** |
| 6 | Assembled verification + render-path swap | not started, blocked on 3 |

and commit `59e7bbd`: *"Not wired into the render path yet — that's Phase 6,
deliberately last, after Phase 3 lands too."*

**This also resolves the standing paradox.** The six tone subsystems verify
bit-exact against the DLL *and* the render is wrong, because those six are not
the ones running. `shasta_two_anchor_tone` is. Both facts were always
compatible.

## The acceptance test for Phase 6

`tools/ansel/python-pipeline/pakon_acceptance.py` (public repo).

PSI's RAW export and its finished render are **pixel-registered** (peak |corr|
0.9019 at `dy=dx=0`, checked, not assumed), so the vendor's end-to-end transfer
function is derivable directly from the pair — no DLL instrumentation. That
becomes the target curve; a candidate render is scored against it as max
absolute deviation per channel, in 8-bit code values.

Baseline: `research/acceptance/vendor_baseline_AA005.json` (57 buckets, kept
private — derived from the owner's own film; the tool takes a path so no
photographs need shipping).

**Current score, stand-in tone stage:**

```
ch    max dev   mean dev   worst at raw   buckets
R         191       49.0             68        24
G          97       30.2             28        17
B         130       35.7              4        16

worst channel deviation: 191 of 255
```

When Phase 6 swaps the real chain in, that number should collapse. If it does
not, this says so immediately and names the part of the range still wrong.

Usage:

```
pakon_acceptance.py --baseline <json> --raw RAW.tif --candidate ours.png
pakon_acceptance.py --baseline <json> --raw RAW.tif --render --fail-over 40
```

`--render` drives the engine from the 8-bit vendor RAW, which is an
**approximation** (`docs/63`) — the absolute score above carries that caveat.
The *baseline* does not: it is derived from two vendor outputs only. Scoring a
candidate rendered from real RPD12 against it is sound, and that is how Phase 6
should use it.

## Caveat

That the stand-in is *the* cause is strongly evidenced — it is the only
unported stage in the render path, the divergence has the right shape, and the
plan already identifies it. It is not *proven* to be the whole of it. Phase 6
plus this test is what proves it, and the test is now ready and waiting.
