# 54 — The vendor's own render has genuine deep blacks

**Date: 2026-08-13.** Direct measurement of PSI's output on real film, obtained
to settle the "washed out / no real blacks" defect tracked against the port.

## Question

The port's rendered frames come out with no real blacks — darkest ~1% of pixels
sitting around sRGB **60–110/255** instead of near 0, across many rolls and on
both the Python and Go engines. Eleven-plus investigation passes cleared every
software mechanism checked (tone-curve math, balance shifts, FUGC, Dmin
measurement, the `fpo` constant), all bit-exact against the real DLL. The one
thing nobody had was **the vendor software's own output on real film**.

## Answer

**The real vendor software produces genuine deep blacks on this material.**

Measured on frames recovered from the Windows VM, 8-bit luminance
(`0.2126R + 0.7152G + 0.0722B`), verified-coherent frames only:

| frame | size | p0.1 | p1 | p50 | p99 |
|---|---|---|---|---|---|
| `img_48` | 2941×1960 | **6** | **9** | 135 | 229 |
| `img_77` | 2941×1960 | 31 | 33 | 109 | 226 |
| 23 coherent frames | mixed | median **11** | median **18** | — | — |

`img_48` is visually confirmed as a complete, coherent photograph. Its darkest
1% sits at **9/255** and its darkest 0.1% at **6/255** — an order of magnitude
below the port's 60–110 floor.

**Conclusion: the washed-out look is a port artefact.** It is not inherent to
the scanner, the film stock, this unit's calibration, or the recovered LED
values. Whatever the port is doing to lift the shadow point, the vendor's own
pipeline does not do it on the same hardware.

## How the frames were obtained, and the limits of that

PSI has **no off-machine export path configured** — `StartIQueue = 0`,
`RunDLSQueue = 0`, and every configured export folder is a local `C:\` path
(`HKLM\SOFTWARE\Pakon\PSI\IQueue II`, `…\IQueue II\DLSQueue`). The operator
saved frames manually to `My Documents\1`, and Parallels Tools is not installed,
so there is no host↔guest file channel.

They were therefore **carved by signature scan** out of the VM's virtual disk
(`.hds`), read-only, with the VM running. 83 candidates; files live in
`~/pakon-findings/carved/` on the Mac.

**Signature carving cannot follow NTFS fragmentation**, so a substantial share
of the output is wrong even when it decodes without error. This bit:
`img_81_2941x1960.jpg` decoded cleanly at full height and measured `p1 = 0.6` —
apparently perfect blacks — but is **scrambled noise** containing a black
rectangle. Three other frames (`img_02`, `img_41`, `img_05`) measured
`p1 = 77/78/60`, which would have supported the *opposite* conclusion, and are
also mis-carves.

Real frames were separated from mis-carves by a **row-vs-column discontinuity
ratio**: `mean|Δrow| / mean|Δcol|`. Natural images sit near 1.0; fragment-
spliced ones are dominated by horizontal streaking and run 3.6–14.1.

```
img_48   ratio 1.18   coherent      <- also visually verified
img_77   ratio 1.25   coherent
img_05   ratio 3.63   SCRAMBLED
img_41   ratio 9.85   SCRAMBLED
img_02   ratio 14.11  SCRAMBLED
img_81   ratio 11.21  SCRAMBLED
```

**Only frames below ~1.35 should be used for anything numerical.**

## Caveats — do not over-read this

1. **The frames appear to be black & white.** The port's defect is tracked
   against *colour negative*. If this roll is B&W, this is not a like-for-like
   test of the colour pipeline, only of the tone/shadow behaviour.
2. **8-bit JPEG, carved rather than exported.** Adequate for "are there blacks
   or not"; **not** adequate for stage-by-stage numerical comparison against the
   port, which needs 16-bit TIFF for real shadow precision.
3. **Only two full-resolution frames survived intact.** Small sample.
4. The saved frames are **2941×1960**, not the `HiResExport` profile
   (`Width 1536`, `Height 1024`, `Quality 100`, `FileType 3`), so the operator's
   Save As used different settings than that profile would have applied.

## What would make this definitive

A clean export rather than a carve: colour negative film, PSI's default
automatic settings with no manual exposure or contrast correction, exported as
**16-bit TIFF**, copied off via USB mass storage (a stick already passes through
to this VM) rather than recovered from the disk image.

That removes every caveat above at once and gives a frame that can be compared
against the port stage by stage.
