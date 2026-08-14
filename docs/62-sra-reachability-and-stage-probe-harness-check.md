# 62 — SRA/CN reachability breakpoint test, and a harness-config check on
`docs/61`'s two "distinct failures"

**Date: 2026-08-13.** Written for whoever is at the Windows/Parallels
machine next, after reading `docs/61-stage-probe-and-sra-correction.md`
in full. Two things: the breakpoint test that would settle SRA/CN
reachability (unchanged from before this doc existed), and a
respectfully-flagged, evidence-based concern about `docs/61`'s own two
"distinct failures" — both look explainable by the probe's own harness
configuration rather than the production render path, and this repo's
own already-verified numbers (from the port's real `main`/
`calibration-and-tone-port` branch, not this `finding/` branch) already
contradict one of them directly.

`docs/61`'s SRA correction itself is independently cross-confirmed —
see below — and its measured vendor transfer curve is a genuinely
valuable, still-fully-usable artifact regardless of the rest of this
doc. Nothing here is a dismissal of that work; it's a check worth
doing before building on the other two conclusions.

## 1 — `docs/61`'s SRA correction: independently confirmed, same finding

`docs/61` found the port never applies the SRA forward LUT on the real
path (`self.sra_lut` only referenced inside the `else:` branch that
never runs once `setshifts_out` is populated). This was checked
independently, same session, same conclusion: `pakon_ansel.py`'s
`self.sra_lut` is applied only in `render_scene`'s legacy fallback
branch, never in the `shasta_stand_in=True` path real F-135/CN-Enhanced
renders actually take. Two independent checks, same answer — solid.

## 2 — The two "distinct failures" in `docs/61`: a harness-config check

`docs/61`'s own probe banner reports `shasta_stand_in=False`. That
matters more than it might look like at a glance: `AnselEngine`'s own
dataclass default is `shasta_stand_in: bool = False`
(`pakon_ansel.py:681`), and `docs/61`'s own probe tool
(`pakon_stage_probe.py`) calls `A.AnselEngine.load(...)` directly and
never sets it — confirmed by reading the tool's own source
(`eng = A.AnselEngine.load(...)` then `print(f"...
shasta_stand_in={getattr(eng, 'shasta_stand_in', '?')}")`, with no
assignment anywhere in between). The real production entry points —
`tools/pakon_decode.py` and `tools/pakon_render.py` — both explicitly
set `shasta_stand_in = True` for `--model f135` (documented directly in
`AnselEngine`'s own class comment: *"F-135: use the two-anchor stand-in
instead of the assembled toneLut... Set by pakon_decode.py /
pakon_render.py for --model f135. Off elsewhere"*). `docs/61`'s own
"structural point" — that the probe measured Shasta's assembled tone
LUT running, not `ColorNegativePath::analyzeAutoTone`'s six subsystems —
is consistent with, and directly explained by, running with the
default `False` instead of production's `True`. This looks like the
same *class* of trap `docs/61` itself already caught once (the
inversion not happening inside `render_scene`), not caught a second
time.

**This is checkable independently of anything on this branch.** The
port's own `docs/74-washed-out-tone-chain-architecture-and-dmin-
methodology.md` (on the public-facing worktree branch
`worktree-tender-gliding-abelson`, `main`/`calibration-and-tone-port`
history, not this `finding/` branch) has been testing the real
production path — `pakon_render.open_capture` →
`Roll.engine()` with `shasta_stand_in` explicitly set `True`, matching
`pakon_render.py`'s own real configuration — all session, against
several real rolls including the exact same physical scan as this
branch's own `research/vendor-scans/`. **That already shows the
identical washed-out floor** (shadow `p1` in the 60-120 range across
every frame tested) *on the correct, production-matching path* — so
whichever tone stage is actually running on a real F-135 render, the
defect is present either way. Worth being precise about what that does
and doesn't mean: it doesn't prove `docs/61`'s probe ran the wrong
branch (only reading `pakon_stage_probe.py`'s own source does that), but
it does mean "the real production path already shows this defect" was
already established before this branch existed, so the probe's own
`shasta_stand_in=False` result isn't the thing that discovered the
defect — worth confirming whether it's independently informative once
re-run with the production config, or whether it was measuring a
different (Shasta) code path's own, separate washout the whole time.

**Concretely, worth 10 minutes before trusting the "wrong tone stage
entirely" conclusion**: re-run `pakon_stage_probe.py` (or add one line
to it) with `eng.shasta_stand_in = True` set explicitly right after
`AnselEngine.load(...)` returns, same input, and see whether the
reported stage list changes to show `real_auto_tone`/`analyzeAutoTone`
running instead of the Shasta LUT path, and whether the measured
floor/span numbers change at all. If they don't change, that's
independently interesting (both tone paths produce a similar defect).
If they do change, `docs/61`'s own specific "we're running a tone stage
the vendor doesn't run at all" framing needs revising — the defect
would then need to be re-measured on the *correct* stage, which per the
port's own `docs/74` (§8-9, §14, §16-17) is where eleven-plus
independent passes have already spent the most effort, all converging
on "the six subsystems are individually and now assembled-verified
bit-exact against the real DLL, on real image data, and the defect
survives regardless."

## 3 — The inversion-clipping finding: likely the same class of issue

`docs/61`'s "Item 1" (`f135_negative->positive` driving B to
`p50 = 4095`, half the channel pinned at ceiling) is worth the same
scrutiny, for a different reason: `docs/61`'s own probe fed it
`rawAA005` scaled ×16 as an **approximation** for true 12-bit RPD12 —
its own words: *"PSI's RAW export is 8-bit and partly processed, not
true RPD12... read the shape of the collapse, not the absolute codes."*
That's an honest, correctly-flagged approximation, but it means this
specific number (B clipping at the inversion step) was measured on
already-vendor-processed 8-bit data multiplied up, not on this
project's own real 12-bit capture pipeline. Cross-check: the port's own
`docs/74` traced the real `f135_rom12_to_rpd12` inversion stage on
**real captured 14-bit sensor data** (not an approximation) across
multiple real rolls this same session and found **zero clipping** at
that stage every time (`0.0% >= 4095`, every channel, every frame
checked). That's a real discrepancy worth resolving — most likely
explained by the ×16-scaled-8-bit-approximation input differing enough
from true 12-bit sensor data to manufacture an artificial ceiling clip,
but worth confirming rather than assuming either way.

## 4 — What's still genuinely valuable in `docs/61`, unaffected by any
of the above

**The measured vendor transfer curve** (`docs/61`'s own final table,
built from the pixel-registered raw/rendered pairs, peak correlation
0.90 at `dy=dx=0`) is a real, clever, independently-obtained
measurement that doesn't depend on which tone stage the port's own
probe happened to exercise. It's a genuine empirical target for
whatever the real fix turns out to be, and stands on its own regardless
of how items 2-3 above resolve. Worth keeping and building on.

## 5 — The SRA/CN-reachability breakpoint test (unchanged ask)

Separately from all of the above: a disassembly pass (this session,
`worktree-tender-gliding-abelson`'s `docs/74` §18) traced
`AnsSraCapabilityImpl::analyze`'s (`0x101a7080`) and `makeSRALUTS`'s
(`0x101a6be0` — not `0x10594b78`, which is only that function's own
self-naming string) real callers through the full call graph. **All
four real Color-Negative path variants in the DLL** —
`AnsCnPremiumPath`, `AnsCnOpticalPath`, `AnsCnLockbeamPath`,
`AnsCnEnhancedPath` — were individually disassembled at their own
`analyzeScene` entry points, and none of them calls into SRA anywhere
in the tree. SRA is only reachable from Color-Positive (slide film),
Archive, and a separate "Dc" path family — not from a colour negative,
at the level checked.

This is in real, unresolved tension with `docs/56`'s own live evidence
that both SRA LUT files get opened during an actual PSI render of real
colour-negative film — a file being opened proves it was considered,
not that it executed, and two real unconfirmed candidates exist for who
else might be opening those same files on a CN render: **DSba** (its
own distinct LUT-key strings, `dsba_sra_fwd_lut_key`/
`dsba_sra_data_key`, not traced), or a capability-declaration-time load
unrelated to which path actually renders.

**The test that would settle it, unchanged**: a single debugger
breakpoint, not a full DynamoRIO trace. Attach a debugger to `PSI.exe`
(WinDbg / x64dbg / OllyDbg, whatever's available), set breakpoints in
`PakonIMAu.dll` (image base `0x10000000`) at:

* `0x101a7080` — `AnsSraCapabilityImpl::analyze`
* `0x101a6be0` — `makeSRALUTS`

Run one real colour-negative scan through PSI start to finish, default
automatic settings. If neither fires, SRA genuinely doesn't execute for
CN renders — closes the hypothesis, real negative result. If either
fires, that's real CN-reachability the static call-graph read missed,
and the breakpoint hit hands back the actual caller (return address /
call stack) for free.

## Bottom line, in priority order for whoever picks this up

1. **Re-run the stage probe with `shasta_stand_in = True` set
   explicitly** — 10 minutes, resolves whether item 2's "wrong tone
   stage" framing holds once the probe matches production config.
2. **The breakpoint test (§5)** — resolves SRA/CN reachability
   directly, independent of item 1.
3. **Keep and build on the measured vendor transfer curve (§4)**
   regardless of how 1-2 resolve — it's real, and it's the actual
   target either way.
