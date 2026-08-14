# 61 — Per-stage probe, and a correction to `docs/58`

**Date: 2026-08-13.** Built to answer "where does our render break". It does,
and the answer is not what `docs/58` said.

## `docs/58` is wrong on its central claim

`docs/58` said the port **applies the SRA forward LUT and never inverts it**,
leaving the tone chain in the wrong space. The first half of that is false on
the path that actually runs.

`pakon_ansel.py:795` — the only `apply_1d_lut(x, self.sra_lut)` in the engine —
sits inside the `else:` branch at line 789. That branch runs only when
`setshifts_out is None`. Live, `PREFERENCE_SHIFTS_PORTED=True` and
`setshifts_out = (688, 292, 130)`, so **the preference branch runs and the SRA
forward LUT is never applied at all.** It is loaded (`SRA=common-sraFwdLut-
metric-default.lut[200]=1509` appears in the engine banner) and then unused.

Confirmed by the probe: exactly one `apply_1d_lut` call fires per render, and it
carries FUGC's `apply_lut`, not the SRA table.

### What `docs/58` still gets right

* The forward and backward LUTs are exact inverses — `bk(fwd(x)) == x`. Proven
  by parsing, unaffected.
* The vendor opens both during a real render (`docs/56`).
* The port never loads the back LUT anywhere.
* `sra_fwd_lut_name()` has no `erimm` branch though the vendor ships that file.

So the **asymmetry is real**; the **mechanism** proposed for the washout is not.
An unbalanced round trip cannot explain a defect on a path that never does the
round trip. Treat `docs/58` as a correct observation about the SRA data files
with a wrong conclusion attached.

## The tool

`tools/ansel/python-pipeline/pakon_stage_probe.py`. Drop it beside the engine in
the public repo's `python-pipeline/` and run it.

It **wraps the functions the engine calls** rather than editing the engine.
`render_scene` has several branches and which one runs depends on what loaded,
so wrapping records whichever actually executed — the stage list is evidence,
not assumption. If a stage does not appear, it did not run.

```
./pakon_stage_probe.py --from-vendor-raw rawAA005.tif --compare AA005.tif
```

## Trap this cost me, recorded so it does not cost anyone else

`render_scene` does **not** invert the negative. That happens earlier, in
`pakon_decode.f135_rom12_to_rpd12`, guarded by `test_scene_rpd12_inverts` in
`tools/test_render_f135.py`.

Calling `render_scene` directly on negative data produces output correlating
**+0.99 with its own input** and −0.88 with the vendor. That looks exactly like
a catastrophic port defect and is not one — it is a harness bug. I reported it
as a finding before catching it. The tool now runs the inversion itself
(`corr(in,out) = −0.939`) and `--no-invert` is the only way to skip it.

## Where the range actually dies

Input is `rawAA005` scaled ×16. **Approximation** — PSI's RAW export is 8-bit
and partly processed, not true RPD12 — so read the shape of the collapse, not
the absolute codes. All values 0-4095 until the last row.

```
 #  stage                        ch    in p1  in p50  in p99 ->     p1    p50    p99   span
-1  f135 negative->positive      R      224    1216    2880 ->    899   1310   2525   1626
                                 G      160     672    1952 ->   1264   2085   4095   2831
                                 B       96     560    1824 ->   1409   4095   4095   2686
 1  SBA setshifts balance        R      898    1309    2524 ->   1586   1997   3212   1626
                                 G     1263    2085    4095 ->   1555   2377   4095   2540
                                 B     1408    4095    4095 ->   1538   4095   4095   2557
 2  SHASTA apply (real)          R     1586    1997    3212 ->   1553   1780   2381    828
                                 G     1555    2377    4095 ->   1493   1892   2484    991
                                 B     1538    4095    4095 ->   1461   2484   2484   1023
 4  apply_1d_lut (FUGC)          R     1553    1780    2381 ->   1550   1779   2380    830
 5  ColorAdjust                  R     1550    1779    2380 ->   1550   1779   2380    830
 6  rpd12->icc u8                R     1550    1779    2380 ->     97    111    148     51
                                 G     1475    1891    2483 ->     92    118    155     63
                                 B     1457    2483    2483 ->     91    155    155     64
```

**Two distinct failures, both upstream of the tone maths:**

1. **The inversion clips.** `f135_negative->positive` drives B to `p50 = 4095`
   and `p99 = 4095`, and G to `p99 = 4095`. Half the blue channel is already
   pinned at the ceiling before any tone stage runs. Highlights are gone at the
   very first step.

2. **The tone stage floors at ~1460 and halves the span.** Span goes
   1626→828 (R), 2540→991 (G), 2557→1023 (B) — roughly 2.5× compression — and
   the minimum never goes below ~1460 of 4095, i.e. 36 % of range. That floor
   is what becomes u8 91-97.

FUGC and ColorAdjust are near no-ops here (span changes by ≤2 codes). They are
not the problem.

Final: ours **p1 = 97/92/91**, vendor **p1 = 0/6/5**. That reproduces `docs/54`'s
60-110 floor faithfully, so the probe is measuring the real defect.

## The structural point

The banner says `shasta_stand_in=False`, so the **assembled Shasta tone LUT**
ran. But `render_scene`'s own comment says Shasta **never runs for CN-Enhanced**
— the vendor runs `ColorNegativePath::analyzeAutoTone` (`0x100fb730`), the
`cna → dra → toneHelper → contrast → ast → citras` chain.

So on a colour negative we are running a tone stage the vendor does not run at
all. That is a better-supported explanation for the washout than `docs/58`'s:
it is upstream of everything, it is where the probe measures the compression,
and it explains the standing paradox directly — the six subsystems verify
bit-exact because they are correct, and they are not being used.

## The vendor curve, measured without touching the DLL

The raw/render pairs in `research/vendor-scans/` are **pixel-registered** —
verified, peak |correlation| 0.90 at `dy=dx=0`. So the vendor's end-to-end
transform can be measured directly from the pair. No DynamoRIO, no Unicorn, no
instrumentation of a closed pipeline.

```
 raw | vendor R  ours R     d | vendor G  ours G     d | vendor B  ours B     d
  12 |      241     253   +12 |      235     254   +19 |      201     254   +53
  36 |      144     211   +67 |      116     236  +120 |       92     252  +160
  60 |       66     180  +114 |       49     191  +142 |       39     199  +160
  84 |       34     177  +143 |       23     170  +147 |       20     167  +147
 108 |       28     174  +146 |       10     143  +133 |        7     109  +102
 124 |       21     165  +144 |        7      98   +91 |        4      72   +68
```

The vendor's curve keeps falling into the deep shadows; ours flattens out around
165-180 and stops. The largest divergence is in the **midtones-to-shadows**
(raw 60-124), not at the extremes — consistent with a tone curve of the wrong
shape rather than a clipping or scaling error.

This curve is a **fitting target**. Whatever replaces the tone stage can be
scored against it directly, per channel, per code value, without waiting for an
execution trace.

## Next

1. Fix the inversion clipping first — B at `p50 = 4095` is unambiguous and
   independent of the tone question.
2. Then treat the vendor transfer curve as the target for the tone stage.
3. `docs/57`'s DynamoRIO trace is now **lower** priority: the question it was
   going to answer — which stages run — is partly answered by the probe for our
   side, and the vendor's net effect is measurable from the scan pairs.
