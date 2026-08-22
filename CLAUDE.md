# CLAUDE.md

Guidance for Claude Code (or any agent) working in this repository. Read this
before touching colour-pipeline or reverse-engineering code — the standards
here are load-bearing, not stylistic preference.

## What this is

A from-scratch macOS/Linux port of the Kodak/Pakon F-135/F-235/F-335 35mm
film scanners — discontinued 2002–2007 hardware with 32-bit Windows XP-only
vendor software and no modern-OS support. This project reverse-engineers the
USB/firmware layer and the vendor's colour-science DLLs (`TLB.dll` = F-135,
`TLA.dll` = F-235, `TLC.dll` = F-335, plus shared `PakonIMAu.dll`) and
reimplements the host side in userspace.

Real hardware in this project's possession: **one physical F-135 Plus unit,
only.** F-235/F-335 support exists in code but has never touched real F-235/
F-335 hardware — treat it as unverified until tested against real units.

## The core standard: "golden" means bit-exact against the real vendor, not "looks right"

This is the single most important thing to internalize. This project does
not accept "the output looks plausible" or "the structure matches" as
confirmation of anything. There is a strict evidence hierarchy, strongest to
weakest:

1. **Live Unicorn CPU emulation of the real vendor DLL**, executed on real
   captured input data, diffed bit-exact/byte-exact against the Python
   port's own output for the identical input. This is the only tier that
   counts as "confirmed." See `tools/ansel/python-pipeline/*_golden.py` for
   ~30 existing examples of this pattern.
2. **Live hardware hook capture** (`tools/re/live_hooks/`) — real DLL
   functions hooked on the real scanner during a real scan, arguments and
   buffers dumped. Strong evidence for what real hardware actually does at
   runtime, but not a substitute for tier 1 when the question is "does this
   arithmetic match."
3. **Static disassembly / reachability analysis** (`radare2` via `r2pipe`,
   `tools/re/reachability.py`) — triage only. Useful for finding candidates
   and ruling things out, never sufficient on its own to claim a match.
   Never use raw `pD` byte-range disassembly to characterize a function's
   purpose — only `af`+`pdf` real function-boundary disassembly counts;
   `pD` is acceptable only as a "this is not real code" diagnostic.
4. **Empirical end-to-end comparison** against a real vendor-produced
   reference (e.g. a real Pakon PSI-software TIFF) — useful for ruling
   hypotheses in/out by magnitude, but doesn't by itself explain *why*.

A structurally-suggestive function name or a shape that "looks like" the
target formula is **not** a finding until it clears the actual bar. The
project's own history has several near-misses (suggestively-named functions
that turned out to be dead code) — read full function bodies, don't infer
from names.

**Target state:** every stage of the pipeline, from clicking "scan" through
to the final rendered image — lamp warm-up, LED sequencing, motor/CCD
handoff, AFE capture, the colour/tone chain, frame detection — verified at
the appropriate tier above. Not there yet; see "Where things stand" below.

## Repo/RE conventions

- **Hash every DLL before touching it** (`md5`) and cite by hash, not just
  path, in any doc claiming something about its contents.
- **`tools/re/reachability.py walk`** is the standard tool for "is this
  function actually reachable from a real, live entry point" — don't assert
  reachability from proximity or naming, run the walk.
- **Never commit scratch RE scripts.** One-off triage scripts live under
  `/tmp/pakon_re/` and are not committed — only the doc section they produced
  is.
- **Doc citation style is dense and evidence-first.** See
  `docs/74-washed-out-tone-chain-architecture-and-dmin-methodology.md` for
  the house style: every claim cites its evidence tier, every negative
  result is stated as plainly as a positive one, "structurally matches" and
  "confirmed bit-exact" are never conflated.
- **Section numbering collisions are a real, recurring hazard** when
  multiple agents work on the same doc concurrently — always re-grep for
  the section number you intend to use immediately before writing, not just
  at task start.

## Calibration data

- **Never overwrite `calibration/*` — only timestamp.** Every calibration
  promotion keeps the prior file as `README.pre-<reason>-<date>.json` (and
  matching `.csv`/`.npy` backups). See `docs/71-rebuilding-calibration.md`.
- Don't guess between two historical calibration values when they disagree —
  get a fresh live measurement. A past regression in `afe_offsets` was found
  and *deliberately left unfixed* pending a real live multi-round
  convergence run rather than picking a value on vibes (docs/74 §53).
- **Never fabricate a hardware measurement.** If live hardware isn't
  connected, say so and pivot to real historical/file evidence — don't
  simulate a result.

## Safety conventions (physical hardware)

- Commands that expose or drive film (duty search, B&W calibration) require
  explicit confirmation the correct film type is physically loaded — this is
  by design, not an oversight to work around.
- Motor jog (`motor_jog()` / the UI Advance/Rewind controls) is bounded and
  pulse-based with hard caps, and is mutually exclusive with an active scan.
  Don't improvise raw/unbounded motor commands from an ambiguous instruction.

## Testing

Standard regression suite, run before claiming anything works:
```
python3 tools/pakon_gate.py
python3 tools/test_calib.py
python3 tools/test_render_f135.py
```
Plus whichever `tools/test_*.py` covers the area you touched
(`test_motor_jog.py`, `test_extcode.py`, `test_gold400_parity.py`, etc.).

## Two render engines — know which one is live

**`colour_engine()` defaults to `"go"`.** Read that function before trusting
any statement about "the default" — including this one. Its own docstring calls
Python *"deprecated, explicit only"*. An earlier revision of this file claimed
Python was the app's default; it was wrong, and that error made every
Python-side colour measurement describe something the app does not run.

- `tools/ansel/pipeline/` (Go) — **the product path, and the default.** Its
  `analyzeAutoTone` APPLY half is now bit-exact against the Python reference
  (66.4 M samples, docs/74 §182), and its ICC is bit-exact against the vendor
  CMM (§179). Absent an `OutToneLut` supplied over the ABI it falls back to the
  `ShastaToneRpd` stand-in, and the provenance banner says which ran. Do not
  assume the Go path is colour-correct.

  **Corrected 2026-08-21 (§191):** this section used to say the ANALYSIS half
  was "not ported". That was stale. Four of the six subsystems — cna, dra,
  toneHelper, contrast — plus the shell exist in Go under
  `tools/ansel/pipeline/ans*/`, each verified bit-exact against its Python
  reference, and `ansautotone.Analyze()` returns the `OutToneLut` directly. The
  remaining two (ast, citras-analyze) only *read* the finished LUT and never
  write it back, so their absence cannot change the curve. The accurate
  statement is **not ported → not wired**: computing the curve in Go is
  Phase 6.2, a deliberate un-taken step, not a missing port.

  Phase 6.1 — the assembled chain diffed against the real DLL end to end — is
  **closed** on the Python side and passes today; treat
  `pakon_shasta.AUTO_TONE_PORTED = False` as "the render path has not been
  swapped", not as "the chain is unverified".
- `tools/pakon_render.py` (Python) — has the verified six-subsystem
  `analyzeAutoTone` chain, and is where the colour work in docs/74 §157–§182 was
  measured. Reached only with `PAKON_COLOUR_ENGINE=python`.

**They also diverge upstream of tone** (§182.3), so a correct tone stage alone
will not make their outputs agree: Go inverts against the FRAME's dmin where
Python uses the ROLL's (`req.FilmBase` is never read by the render), FUGC
`ebp18` provenance differs, and Go truncates the FUGC index where Python
`rint`s.

## Where things stand / what's left

Full status: `README.md`'s "Colour is currently in progress" section,
`docs/74` (colour pipeline master investigation log, evidence-cited,
currently ~56 sections), `docs/75` (B&W scan root cause).

**The ~88–89 sRGB brightness offset: SOLVED (docs/74 §170–§175).** It was not
an anchor, which is why 14+ hypotheses (tone chain, film_base, colour matrix,
lamp duty, AFE gain/offset, SCPLut, framing, applyLut…) all failed to explain
it — they were tuning terms the vendor's inversion does not contain.

The F-135 inverts **before** stage 2, not after, with a fixed table:

    out = clamp(14750 − 3500·log10(in), 0, 16383)

no film base, no Dmin, no pedestal (`c9`), no `fpo` — this port had all four,
at 1000 codes/decade instead of 3500, applied after the polynomial. The real
16384-entry table is captured (`vendor_invert_table.npy`); the closed form is
a ±1 approximation (87.5 % exact) and is the fallback. Using it in the vendor's
position takes the six-frame comparison from **59.14 MAE / +58.90 bias to
23.59 / −3.18**. Opt-in via `PAKON_VENDOR_INVERT=1` — still off by default
(one roll, one table, and it re-architects the front of the chain).

**Bit-exact against the real DLLs** (don't re-derive these): the OutToneLut
construction; the shift-LUT builder `fcn.1006c4f0`; and the ICC — the vendor's
tetrahedral CLUT interpolator, ported and proven over **all 16.7 M possible u8
triples** (`pakon_kcms_clut.py`, §176). `to_srgb` uses it by default;
`PAKON_ICC_LCMS=1` falls back to lcms, which is ~1.8 codes dark.

**What is actually left** (docs/74 §159–§168, §175.4): the vendor computes the
per-channel additive RPD shift **per frame**; this port computes one triple per
roll in `AnselEngine.load()`. Applying the vendor's own values is worth 11.6
MAE. Within it, δ — a uniform per-frame scalar — is confirmed on two rolls but
its source is still uncaptured. All three of its variable terms now trace to
**one** function, `fcn.102aece0` (24,516 B) — mapped, not ported (§192). Note
that function's earlier citation as `fcn.1028b8d0` (2,958 B) was wrong: that is
the *caller*.

**Framing is bit-exact but not wired, and the distinction matters** (§194).
`FRAMING_PORTED = False` is the only ledger entry that can affect a render, but
it no longer means "unported": the whole vendor chain is bit-exact — 15
functions up to and including the entry `fcn.100072c0` and its threshold search,
1,429 checks. It stays False because `find_frames` still runs Otsu, and because
the entry consumes the vendor's **8-bit per-line RGB summary** while this port
holds **float 14-bit non-inverted**. Guessing that quantisation would move every
boundary *invisibly to the golden*, which feeds both sides the same synthetic
bytes. **That capture needs the real scanner** — the `tlb_framing_line_reduce`
hook is written and enabled for it.

**Run `python3 tools/porting_state.py` before making any claim about what is
ported** (§188). Four separate documents — this file twice — have carried stale
porting claims that the tree contradicted.

**A methodological warning worth reading before tuning anything** (§171.3): at
least two errors in this chain have opposite sign, so a stage tuned by watching
the end-to-end number alone can be tuned in the *wrong* direction. Fixing the
ICC correctly made the composite metric slightly worse. Verify stages against
the vendor individually.

**Tracked work item list (all of it — done, partial, and open):**
https://github.com/users/gazzdingo/projects/1 — "Pakon Scanner Port:
Verification & Remaining Work". Check here before starting new verification
work to avoid duplicating something already closed, and update it when you
close or open something real.

## Git

- `origin` → `gazzdingo/pakon-mac` (**public**). `private` →
  `gazzdingo/pakon-mac-private` (private). Both are in active use, on
  different branches — **check `git branch -vv` before pushing, don't
  assume.** Some branches (e.g. `calibration-and-tone-port` on the main
  checkout) track `private` for RE-heavy work; this worktree's branch
  (`worktree-tender-gliding-abelson`) tracks `origin` and has been pushing
  full RE detail (DLL addresses, hook internals, live capture data) there
  by explicit owner choice. If you're on a branch with no clear precedent,
  ask before pushing anything containing vendor DLL specifics rather than
  assuming either remote.
- Never push to `main`/`master`. Never force-push. This repo's own
  convention throughout has been small, evidence-cited commits — one real
  finding or one real fix per commit, not batched.
