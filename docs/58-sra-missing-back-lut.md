# 58 — The port applies SRA's forward LUT and never inverts it

**Date: 2026-08-13.** A concrete, verifiable defect upstream of the entire tone
chain. Found by comparing the file set the vendor actually opens during a render
(`docs/56`) against what the port loads.

## The finding

The vendor's SRA stage is a **matched forward/backward LUT pair**. The port
loads the forward LUT and **never loads the backward one** — `sraBkLut`,
`sra_bk` and `BkLut` do not appear anywhere in either the Python or the Go
engine.

```
vendor ships and opens:
    common\common-sraFwdLut-metric-{default,erimm,rim12,rom12}.lut
    common\common-sraBkLut-metric-{default,rim12,rom12}.lut
    common\common-sraData-metric-{default,erimm,rim12,rom12}.dpi
    sra\sra-params-metric-{default,rim12,rom12}.dpi

port loads:
    common\common-sraFwdLut-metric-default.lut          <- and nothing else
```

## They are an exact inverse pair

Parsed from the shipped files (`SRA_NUM_FORWARDLUT = 4096`,
`SRA_NUM_BACKWARDLUT = 3904`; a `KEY = <first value>` line followed by bare
integers, one per line):

```
forward : 4096 entries, range 0..3903
backward: 3904 entries, range 0..4095

  in  ->  fwd  ->  bk(fwd)
   0  ->    0  ->    0
  64  -> 1016  ->   64
 256  -> 1648  ->  256
 512  -> 2113  ->  512
1024  -> 2663  -> 1024
1618  -> 3058  -> 1618
2048  -> 3268  -> 2049
3072  -> 3637  -> 3073
4095  -> 3903  -> 4095
```

`bk(fwd(x)) == x` across the whole domain, to within one code value at the top
end (rounding in the 4096→3904→4096 resampling). This is a round trip by
construction.

## Why it matters

The forward LUT is a log/density curve that **massively expands shadows and
compresses highlights**: input 64 becomes 1016, i.e. 1.5 % of the input range
occupies 26 % of the output range. That is a reasonable *working* space to do
analysis in, and it is plainly designed to be undone afterwards.

Applied without its inverse, every downstream stage receives data in a space it
was not calibrated for:

```
vendor:   forward -> (work in SRA space) -> backward -> tone chain
port:     forward -> (work in SRA space) ------------> tone chain
```

**This explains the standing paradox.** All six tone subsystems (`cna`, `dra`,
`toneHelper`, `contrast`, `ast`, `citras`-analyze) are Unicorn-verified
bit-exact against the real DLL, and the rendered output is still wrong. Both can
be true at once if the *input* to that chain is in the wrong space. The maths is
right; the data reaching it is not.

It is also consistent with the range collapse measured in `docs/54`: the raw
negative uses ~78 % of its code range, and what reaches the tone stage uses
~11 % (spans 462/236/144 of 4095, per `shasta_two_anchor_tone`'s own docstring).

And it matches what that docstring already predicted:

> The real fix is upstream, in the unported `AnsColorNegativePath` /
> `AnsSraCapabilityImpl::makeSRALUTS`.

## Second, smaller gap: the metric axis

`sra_fwd_lut_name()` in `pakon_ansel_maps.py` handles `rom12` and `rim12` and
falls through to `-default` for everything else. The vendor also ships
**`common-sraFwdLut-metric-erimm.lut`**, which has no branch — so an `erimm`
metric silently gets the default curve. Whether the CN-Enhanced path ever
selects `erimm` is `[UNKNOWN]`; the port's default metric is `METRIC_PD12`.

Note also the backward set has **no `erimm` variant** while the forward set
does, so the two axes are not symmetric — worth understanding before wiring the
inverse in.

## What is proven, and what is not

**Proven:** the two LUTs invert each other; the vendor opens both during a real
render; the port loads only the forward one.

**Not proven:** that this is the whole of the washed-out defect. It is a strong
candidate — it is upstream of the tone chain, it is a range-space error, and it
matches both the measured collapse and the repo's own prediction — but it has
not yet been tested end to end.

## Test that would settle it

Apply `common-sraBkLut-metric-default.lut` at the point the round trip should
close, then re-render `rawAA005.tif` (in `~/pakon-findings/incoming/`, with the
vendor's own render `AA005.tif` alongside it as ground truth) and compare the
shadow point. `docs/54` gives the target: the vendor reaches **p1 = 6/255** on
that frame, against the port's 60-110 floor.

Where exactly the inverse belongs is an architecture question for whoever owns
the pipeline — the vendor does its analysis in SRA space, so the inverse goes
after that work, not immediately after the forward LUT.
