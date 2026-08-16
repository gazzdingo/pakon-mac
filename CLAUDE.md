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

- `tools/pakon_render.py` (Python) — has the verified `analyzeAutoTone`
  chain wired in. **Currently the app's default**, as an interim measure.
- `tools/ansel/pipeline/` (Go) — production-oriented, faster, but still
  uses `ShastaToneRpd` (an explicit placeholder, `AutoTonePorted = false`),
  **not** the verified chain. Porting the verified chain into Go is real,
  outstanding work — don't assume the Go path is colour-correct.

## Where things stand / what's left

Full status: `README.md`'s "Colour is currently in progress" section,
`docs/74` (colour pipeline master investigation log, evidence-cited,
currently ~56 sections), `docs/75` (B&W scan root cause).

**The live, standing mystery:** a real, uniform ~88–89 sRGB code brightness
offset between this port's automatic render and the real Pakon PSI
software's own automatic render of the same frame. 14+ specific hypotheses
independently verified and ruled out (tone chain, film_base, colour matrix,
lamp duty, AFE gain/offset, SCPLut, framing, applyLut, and more) — root
cause not yet found. Don't re-litigate a ruled-out hypothesis without new
evidence; check `docs/74` first.

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
