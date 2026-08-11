# Pruned from the `analyzeAutoTone` port — real features, wrong stage

`docs/63` scoped `ColorNegativePath::analyzeAutoTone` (`0x100fb730`), the real
vendor tone stage causing the current shadow-crush bug. A 22-agent scoping
pass checked 16 candidate producer capabilities `analyzeAutoTone` might read
from, to prune what's irrelevant before spending expensive Unicorn-verified
reverse-engineering effort on it.

**14 of 16 got pruned from that port.** Pruned does not mean "not real" or
"not running" — most of these are genuine, mostly-executed features of the
scanner's colour pipeline. They were pruned because `analyzeAutoTone`'s own
166-function reachable set never calls into them, not because they don't do
anything. This doc is the backlog for them: what each one actually is, in
plain terms, and whether it's worth porting later. Not now — nothing here
blocks the colour-crush fix.

## The big one: dust and scratch removal (`area`)

**By far the largest item found in the entire scoping pass — bigger than
everything else combined.** Measured at **732 functions / 299,737 code bytes
/ 1,405 indirect call sites — 3.9× the size of the whole 6-subsystem tone
chain**, larger than any other single capability measured on this project,
including Shasta.

It's `AnsAreaCapability` / `libAREA.ansel` — dust, scratch and blemish
**detection and correction**: `AnsAreaDefect` (with a 2D `center` coordinate),
`AnsAreaCorrection` (automatic and manual correction levels), `AnsAreaCandidate`,
a "percent of frame masked" figure. This is almost certainly what the "Frosty
— Digital Ice Technology" badge on the scanner's own housing refers to.

**Confirmed running on your scanner's colour-negative path** — unlike Shasta,
there's no jump-table gate excluding it. `AnsAreaCapability::acquire` is
called directly and unconditionally from `AnsCnEnhancedPath`'s own code, one
of only 12 such direct callers in the whole binary, matching exactly the 12
concrete scan-path classes. `balanceAreaImage`, a real earlier stage in the
same scene sequence, references it by name too.

**Port status: essentially zero.** The only piece of it touched anywhere in
this repo is `applyBalanceShifts` (already known, already proven shape-null —
one shared curve plus three integer offsets, can only balance, not add
contrast), ported for an unrelated reason. Nothing else — `AnsAreaParameters`,
`AnsAreaCorrection`, `AnsAreaDefect`, `AnsAreaCandidate`, `AnsAreaOperand` —
has any code here at all.

**Why it doesn't matter for the colour crush**: it writes spatial defect
coordinates and correction levels, not RGB or density values, and
`analyzeAutoTone` never reads it. **Why it matters eventually**: if you want
this scanner's actual dust/scratch removal working — the feature the badge
advertises — this is the entire scope of that project, and right now it does
nothing.

## Runs before the tone stage, feeds a sibling stage instead

These genuinely affect the final image's colour — just not through
`analyzeAutoTone`. They compose into the pixel buffer in `balanceAreaImage`
or a parallel `exportParameterPack` path, before or alongside the tone stage
runs, not through it.

| Capability | What it actually is | Port status here |
|---|---|---|
| **fugc** | Per-channel density LUT. Best-covered producer in the whole set — 12/13 flags ported. Currently being fixed in a separate task (known Go-side bugs: wrong map selection, wrong branch, wrong bias formula) — that fix is live right now. | 12/13 ported |
| **scpLut** (+ `afterSCPLutSba`) | Per-channel gain/bias, consumed by `analyzeScpLutBalance`. | 3/4 ported |
| **fos** | Density-regression statistics (`gmSlope`, `illSlope`, `fosDmin`…) feeding SBA/`setShifts` — a separate exposure-balance mechanism upstream of the tone stage. | 11/13 ported |
| **filmLut** | Static per-(scanner, product, generation) 3-band 4096-entry LUT. Fatal-gated — a real 135-negative run cannot skip it — but on this unit's shipped install the file is confirmed pure identity on all bands. Currently a live no-op, not dead code. | 0% ported |
| **asea** | Real per-channel RGB LUT plus flare/contrast — genuinely tone-shaped data, unlike most of this list. Applied via the parallel `exportParameterPack` path rather than the balance stage. | 0% ported |
| **falloff** | Per-pixel radial lens/scanner vignetting correction, sourced from calibration data rather than scene content. Confirmed unconditional — no film-class gate — and runs before the tone stage in the same transform sequence (`… area, falloff, asea, autoTone, sharpening, defects`). | 0% ported |

## Image-quality features, not colour features

| Capability | What it actually is | Port status here |
|---|---|---|
| **noiseTable** | A density-typed table (per-channel `dens = table[idx] × blackNoiseSigmaMult`) with two confirmed uses: a CnPremium tone-curve mid-aim point (documented elsewhere on this project), and — newly confirmed here — an input to `analyzeSharpening`'s adaptive/noise-aware sharpening amount, for CN-Enhanced specifically. | Partially, via unrelated Ane work |
| **pnr** | Pixel noise reduction — a Laplacian-pyramid chroma/luminance grain suppressor, exposure-zone-scaled. Its own denoise effect touches pixels directly, but the one field it publishes back to the scene context (`"mode"`, a generic status scalar used at ~10 unrelated sites) doesn't look like a tone input. | 0% ported |
| **nra** | A second, distinct denoise operator (`ImaNraOp`) — a spatial noise-reduction kernel. Its output travels through the same export pack as the tone stage, as a sibling, not an input to it. | 0% ported |

## Classification / metadata, not pixel transforms

| Capability | What it actually is | Port status here |
|---|---|---|
| **orderOrientation** | Auto-rotation classifier — publishes `orderOrientationProb` / `frameOrientationProb` confidence scores from sky/grass-style top-vs-bottom colour statistics. Functionally geometric, not a colour transform. | 0% ported |
| **dtt** | Most likely a source-type classifier — archive / digital / colour-positive / colour-negative — inferred from the four `.dpi` variant filenames it loads (`dtt-srcType-archive.dpi` etc.). Confirmed genuinely executed on this path, unlike most of this list. | 0% ported |
| **pan** | Panorama (letterboxed-frame) detector — inspects the top/bottom border rows against the frame's `dmin` to guess whether the frame is a panoramic crop. | 0% ported |

## Both remaining open questions — now RESOLVED

Both `dei` and `flesh` started as genuinely unresolved — real circumstantial
evidence each way, no agent had traced the actual call site. Both have since
been run down properly. Neither is required by `analyzeAutoTone`.

- **`dei` — OUT, by execution order.** `AnsDeiResults`'s field named
  `adjToneHelperDeiValue` and `toneHelper`'s own `deiTree1` decision tree
  looked like a real dependency. Settled two ways: full decompilation of all
  four previously-unread `toneHelper` callees found zero reads of dei data,
  and — decisively — `ColorNegativePath::CalcDei` (`0x101081e0`) is called
  *after* `analyzeAutoTone` in the scene driver (`fcn.10069490`: `CalcDei` at
  `0x10069aca`, `analyzeAutoTone` at `0x10069a1d`), so it structurally cannot
  be an input regardless of what it computes. The suggestive naming describes
  a *different* caller of the same shared `toneHelper::analyze` code, reached
  from the separate CnPremium/Shasta path, not this one.
- **`flesh` — OUT, but not for the easy reason.** The call-order trick that
  closed `dei` doesn't apply here: `analyzePostBalance` (which calls
  `flesh::analyze`) runs at `0x10069503`, *before* `analyzeAutoTone` at
  `0x10069a1d` — the opposite order. So this was closed the harder way: the
  real flesh accumulator was located precisely (bytes `0x4b6`–`0x4bb` of the
  shared driver state, written by real per-channel R/G/B arithmetic at
  `0x100fe471`–`0x100fe47d`), then every one of `analyzeAutoTone`'s 13 uses of
  that same driver-state pointer was checked by hand, along with all 73
  indirect call sites in both functions (all proven to be smart-pointer
  destructor calls, not data dispatch — so nothing could carry the value out
  through an unresolved vtable call either) and every string/global
  cross-reference. None reach byte `0x4b6`. Checked against a 225-function
  reachable set, larger than the 166-function baseline used elsewhere in this
  doc — a conservative negative, not a lucky miss.

  **Not a dead end, though** — the accumulator is real, live, cross-step
  state, and it does feed three real consumers: the `color` capability's
  shifts (`0x100fe708`), the shift-LUT builder on global `0x106b5f74`
  (`0x100fe807`), and — most notably — `analyzeArea` (`0x100e16d0`, driver
  call at `0x100698b1`). So if `area` (the dust/scratch/blemish feature
  described above) is ever ported, `flesh` becomes a real, required
  dependency *there*, not of the tone stage.

Total `analyzeAutoTone` scope is now a settled number, not a range: the core
166-function chain plus `citras`'s confirmed apply-time code (218 functions) —
**384 functions / 157,822 bytes / 879 indirect calls total**. The
`flesh`-inclusive ceiling this doc's earlier version left open (~751
functions) does not apply.

## One discrepancy from this same scoping pass — RESOLVED

Several reports tried to correct the citation of
`AnsCnEnhancedPath::declare` at `0x10064d70` — everyone agreed that address
is wrong (a shared 201-byte field-zeroing constructor with 6 unrelated
callers) — but they did not agree on the right one: some said
`virtual_4 @ 0x10064ff0`, one said `virtual_20 @ 0x10068490`, and one
independently claimed `virtual_44 @ 0x10066b00`.

Run down directly against `PakonIMAu.dll` (ImageBase `0x10000000`, so file
VAs are the cited VAs). **`declare` is `virtual_4 @ 0x10064ff0`.** The
`AnsCnEnhancedPath` vtable begins at `0x1057adb4` (RTTI col `0x105e096c`) and
has 15 slots:

| slot | addr | what it is |
| --- | --- | --- |
| `virtual_4` | `0x10064ff0` | **`declare`** — `0x10064ff0..0x1006598d`, 2461 B |
| `virtual_16` | `0x10065990` | `exportParameterPack` (already cited in `docs/62`) |
| `virtual_20` | `0x10068490` | branch-free 21-name push list, `..0x10068afb` |
| `virtual_44` | `0x10066b00` | `initialize` |
| `virtual_48` | `0x10066700` | `match` |

The deciding evidence is that `0x10064ff0` **names itself**: it pushes
`"AnsCnEnhancedPath::declare"` (`0x1057ac58`) alongside
`"\Atc\ansel\src\libPaths.ansel\CN-Enhanced.cpp"` (`0x1057ac74`) at ten log
and exception sites, and a full scan of `.text` finds those ten are the
*only* references to that string in the image. It also ends at `0x1006598d`,
immediately before `exportParameterPack` at `0x10065990` — the independent
consistency check `pnr.md` predicted.

The `virtual_44 @ 0x10066b00` claim is **refuted**: that function self-logs
`"AnsCnEnhancedPath::initialize"` (`0x1057ad58`), not `declare`. It does push
capability class names in order, which is what made it look right, but
`initialize` constructing capabilities in declaration order is expected. Its
neighbour `virtual_48 @ 0x10066700` self-logs `"AnsCnEnhancedPath::match"`,
and a start-of-function scan lands on `0x10066700` for anything inside it —
the likely source of the mislabelling.

The `virtual_20 @ 0x10068490` claim is **also not `declare`**, but it is a
real corroborator of the *order*: branch-free, 98 calls, and it pushes 21 of
the capability names as immediates in exactly the recorded relative order —
color, filmLut, flesh, scpLut, afterSCPLutSba, area, orderOrientation, asea,
noiseTable, falloff, fugc, toneHelper, contrast, citras, sharpenAdjust,
adaptSharp, blemish, date, dust, scratch, redeye. Note it is 21 names, not
32; the reports quoting a 32-name list from this address were quoting more
than it contains, though what it does contain is a strict subsequence of that
list, with `toneHelper` immediately after `fugc` as `shasta.go` claims.

Fixed in `tools/ansel/pipeline/shasta.go` and
`tools/ansel/python-pipeline/pakon_shasta.py`, each with the disassembly
evidence in the comment. `docs/63-port-status.md` was reported as a third
site carrying this citation; it is not — it contains no `0x10064…` address at
all, only the capability order in prose.

## Source

All of the above is drawn from the individual agent reports behind
`docs/63`'s scoping pass, not restated from memory — the raw reports are
substantially longer and include addresses, byte counts, and exact
disassembly evidence for each capability above.
