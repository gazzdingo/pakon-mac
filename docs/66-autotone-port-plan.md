# Port `ColorNegativePath::analyzeAutoTone` — execution plan + live status

This is the working copy of the plan approved for this port. Unlike a
session-local plan file, this one lives in the repo so **any agent — a fresh
session, a different machine, a different Claude account — can pick this up
cold.** Keep it current: when a phase's status changes, edit its row here,
don't just leave it in a chat transcript.

**End goal this port serves**: a full native port of the F-135's real colour
science, not just this one stage. `analyzeAutoTone` is the current blocker
because it's the proven cause of the shadow-crush bug; once it's done, the
scanner still has real unported features (`docs/64`) — `area` (dust/scratch
removal, likely "Digital Ice") chief among them. See `docs/67` for what this
port has already learned that will transfer to that one.

## Live status (edit this table as phases complete)

| Phase | What | Status |
|---|---|---|
| 0a | Fix `dra` "miss is fatal" doc bug | done |
| 0b | Resolve whether `flesh` is a real input | done — OUT, see `docs/64` |
| 0c | Commit `tools/re/reachability.py`, restore Go parity CLI | done |
| 0d/0e | `contrast` + `ast` recon | done |
| 1 | Orchestration shell (`pakon_autotone.py`) | done, Unicorn-golden |
| 2a | `cna` subsystem | done, Unicorn-golden, all flags `True` |
| 2b | `dra` subsystem | **in progress** — see below |
| 2c | `toneHelper` subsystem | done, Unicorn-golden (2 flags intentionally `False`, see note) |
| 2d | `contrast` subsystem | done, Unicorn-golden (1 flag intentionally `False`, see note) |
| 2e | `ast` subsystem | done, Unicorn-golden (2 flags intentionally `False`, see note) |
| 2f | `citras`-analyze | done, Unicorn-golden (`CITRAS_APPLY_PORTED` is separately Phase 3) |
| 3 | `citras`-apply (218 fn / 86,062 B) | not started |
| 4 | `flesh` port | n/a — Phase 0b ruled it out of scope |
| 5 | `docs/64` dei row cleanup | done |
| 6 | Assembled verification + render-path swap + acceptance test | not started, blocked on 2b + 3 |

**Intentional `False` flags are not gaps.** `TONEHELPER_ACQUIRE_IMAGE_PORTED`,
`TONEHELPER_IMAGE_HISTOGRAM_PORTED`, `CONTRAST_SELECT_DPI_TREE_PORTED`,
`AST_DPI_PORTED`, `AST_EXPORT_PORTED` are all confirmed-dead-or-unreached
paths on `AnsCnEnhancedPath`, documented in their own file's comment next to
the flag. Don't "finish" these without re-reading why they're `False` first.

### `dra` — what's actually left (Phase 2b)

As of this write-up, `tools/ansel/python-pipeline/pakon_dra.py` has these
flags `True`: entry points, lighting branch/dispatch, DPI/TTC parse, results
layout, rebin, lum histogram, compose-tone, cumulative bounds, eff-bounds,
`keepMidPtLut`, TTC slope, **and** — new — `validate_params`, `alloc`,
`generateLut`, `analyze_image`, `analyze_hist`. A background agent has live
end-to-end matches for `analyze_hist` against the real DLL (identity tone
LUT, lum-only, edge-only, non-identity tone LUT, spiky histograms — all bit
exact) and for `analyze_image`.

**What's not done yet**: `pakon_autotone.py:324` still hardcodes
`DRA_ANALYZE_PORTED = False` instead of importing it — every other subsystem
follows the pattern `from pakon_dra import DRA_ANALYZE_PORTED  # noqa: E402`
(see how `cna`/`toneHelper`/`ast`/`citras` are wired at lines 284, 349, 377,
386). `pakon_dra.py` itself has no umbrella `DRA_ANALYZE_PORTED` constant
yet either — only the two split `DRA_ANALYZE_IMAGE_PORTED` /
`DRA_ANALYZE_HIST_PORTED`. The file's own trailer `print()` block (bottom of
`main()`) still labels `GENERATE_LUT`/`ALLOC`/`VALIDATE_PARAMS`/
`ANALYZE_IMAGE`/`ANALYZE_HIST` as "NOT ported" even though the flags above
say `True` — that's stale self-reporting text, not a real gap, but fix it
when you touch this file so it doesn't mislead the next reader.

**To resume**: don't restart from scratch. Check whether the background
agent (dispatched as "Assemble dra's generateLut and finish the port") is
still running; if it finished, read its final report before touching the
file. If it's gone and the file is in the state described above, the
remaining work is: (1) add `DRA_ANALYZE_PORTED = DRA_ANALYZE_IMAGE_PORTED and
DRA_ANALYZE_HIST_PORTED` (or equivalent) to `pakon_dra.py`, only if both are
genuinely verified — check `pakon_dra_golden.py` and
`pakon_dra_lighting_golden.py` actually exercise both overloads end-to-end,
not just their sub-pieces in isolation; (2) wire it into
`pakon_autotone.py:324`; (3) run the full `pakon_autotone_shell_golden.py`
suite to confirm the assembled shell still passes with `dra` now live instead
of stubbed.

## Context (why this port exists)

The F-135 colour pipeline's negative→positive inversion, polynomial, FUGC and
ICC stages are all verified correct. The one remaining confirmed defect is a
mislabelled two-anchor stand-in (`ShastaToneRpd` in Go,
`shasta_two_anchor_tone` in Python) sitting where the real vendor tone-curve
stage — `ColorNegativePath::analyzeAutoTone`, `PakonIMAu.dll` VA
`0x100fb730` — should be. It's the proven cause of a visible shadow crush in
every rendered frame: the stand-in clips 8.65% of its own toned output under
code 257, and a correct FUGC fix already proved the crush is downstream of
FUGC entirely (39.21%→39.19% shadow-region clipping — ruled a fail, not an
improvement).

**Scale, stated plainly:**

| | functions | bytes | indirect calls | vs. Shasta (189/44,427/386) |
|---|---|---|---|---|
| Confirmed scope (core 166 + citras-apply 218) | 384 | 157,822 | 879 | ~2.0× fn / ~3.6× bytes / ~2.3× indirect |

(`flesh` is confirmed OUT — see `docs/64` — so the earlier ~751-function
ceiling doesn't apply; this is a settled number, not a range.)

This is realistically 8–11 Shasta-sized-or-smaller sub-efforts plus one
mandatory assembled-verification pass. Shasta itself found 5 real bugs only
at that final assembled step, not leaf-by-leaf — budget for the same here.

## Conventions to follow exactly

- **Live stand-in call sites** (what gets replaced, only once verified): Go
  `tools/ansel/pipeline/main.go:565`, impl `tools/ansel/pipeline/shasta.go:223`.
  Python `tools/ansel/python-pipeline/pakon_ansel.py:690` (inside
  `render_scene`, guarded by `self.shasta_stand_in`), impl `pakon_shasta.py`.
  **Neither has been touched yet** — confirmed by direct grep, most recently
  2026-08-11. Do not touch either until Phase 6.
- **Unicorn "golden" harness, two shapes**: a simple leaf-call harness
  (`pakon_shasta_curve_golden.py`) for pure arithmetic, and a full-orchestrator
  `Emu`-class harness (`pakon_shasta_analyze_golden.py`) for real entry points
  with a bump-allocator heap, CRT stubs, and `hook()`/`watch()` interception.
- **FPCW must be `0x027F`** (MSVC/Windows extended precision) — Unicorn's
  default silently diverges from the real DLL on x87 code. Every subsystem
  ported so far needed this. See `docs/67` for the full pattern and how to
  prove it with a negative control.
- **File/flag convention**: one `pakon_<subsystem>.py` per subsystem (port +
  flags), paired with `pakon_<subsystem>_<piece>_golden.py` files split by
  verification difficulty. `SCREAMING_SNAKE_CASE_PORTED = True/False`, each
  `False` flag commented with exact VAs, reachability numbers, and why it
  isn't ported yet. `False`-flagged functions `raise RuntimeError` if called
  (pattern at `pakon_shasta.py:2404-2405`) — never silently no-op. Go gets the
  verified Python port transcribed after, as terse constants — Python
  verifies (Unicorn is a Python library), Go transcribes. Intentional
  asymmetry, already established by the Shasta port.
- **Binary access**: `research/sdk/PAKONF135.iso` (171MB, gitignored) is not
  pre-extracted anywhere — extract fresh to a scratch dir per task (`7z x` or
  mount+copy, both attested). Canonical path once extracted:
  `fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`, MD5
  `eea9dcf78ee21d4f7c515a6c2512242d`. `vendor/ansel/anselinstalldir/dataPathItems/{cna,dra,toneHelper,contrast}/`
  DPI data is already committed; `ast`/`citras` have no DPI files in a full
  install — confirmed built-in constants.
- **Tests**: no pytest — narrative "why this exists, root-caused to a real
  bug" comments (`dmin_test.go`, `cabi_test.go` style). Golden-file
  DLL-exactness stays separate from behaviour-regression tests.
- **Model tiering** (explicit user instruction): build with Sonnet, review
  with Opus only if needed. Cost-conscious by design — don't default to the
  most expensive model for mechanical port work.
- **Standing rules that apply to every task in this repo, not just this
  port**: never touch the physical scanner for any of this — it's all
  static/emulated (radare2 + Unicorn); `captures/` (the owner's personal
  photographs) never gets committed, pushed, or described in any report,
  ever; calibration data is never deleted, only timestamped; no autonomous
  `git push`/`gh pr create` without an explicit ask in the same
  conversation; check `git status`/`git diff` before any push, always as an
  explicit file list, never `git add -A`.

## Litter to check for before any commit

Scratch files from earlier sessions sometimes sit untracked at repo root —
seen so far: `patch_sed8.py`, `replace.txt`, `tools/ansel/pipeline/patch_main.py`,
`taps/`. These are one-off sed/patch scripts and scratch output, not part of
the port. Check `git status` and leave them out of any commit unless you've
confirmed they're meant to land.

## Phase definitions

**Phase 0** — prerequisites, see status table above; all done.

**Phase 1 — Orchestration shell.** `analyzeAutoTone` itself minus the six
subsystems' own bodies: the tone object threaded via `ctx+0x64d0` (seeded 0 at
`0x100fb787`) plus `ctx+0x4bc`; the six acquire→enable-byte(`+0xc`)→dispatch
blocks; `pfd`'s confirmed-dead seventh slot (acquire-but-skip, kept — its
absence may be load-bearing for object layout); the `AnsSceneContext::find`
lookup/RTTI/not-found-fallback pattern. Done — `pakon_autotone.py` +
`pakon_autotone_shell_golden.py`.

**Phase 2 — The six subsystems.**

| Task | Entry | Status |
|---|---|---|
| cna | `0x1022ea50` | done |
| dra | `0x1022af20` (image) / `0x1022b530` (hist) | in progress, see above |
| toneHelper | `0x101dd1b0` (live histogram-fed path — corrected from an earlier brief that had this backwards) | done |
| contrast | `0x101d8880` (wraps `0x101d8240`) | done |
| ast | `0x10227160` | done |
| citras-analyze | `0x10223a20` (corrected from `0x10223860`, which decodes to garbage mid-instruction) | done |

**Phase 3 — citras-apply** (218 fn / 86,062 bytes — bigger alone than
Shasta). Split explicitly, do not attempt as one task: **3a** scaffolding
(class/vtable plumbing, object layout, whichever of `virtual_56/60/64` turns
out mechanical); **3b/3c** the two genuinely-unnamed-math virtuals — budget
these as independent recon-plus-port tasks, not pre-estimated. Depends on 2f
for the object shape it consumes. Not started.

**Phase 4 — `flesh`.** Ruled out in Phase 0b. No work here.

**Phase 5 — `dei` doc cleanup.** Done, see `docs/64`.

**Phase 6 — Mandatory assembled verification (strictly last).**

6.1 Full Unicorn bit-exactness of the *assembled* chain (Phase 1 shell + all
Phase 2 subsystems + Phase 3) against real DLL execution on representative
input, compared field-by-field via an `AUTOTONE_WORK_LAYOUT` table.

6.2 Render-path swap at both call sites, flip `AutoTonePorted`/
`AUTO_TONE_PORTED` to true (note: `ShastaOnCnRenderPath` stays `false` —
Shasta genuinely never runs here). Re-render
`captures/out_test/frames/08_raw14.tiff` — **do not commit anything from
`captures/`**, this is a local check only.

**Hard acceptance criterion**: current shadow-region-under-code-16 is
39.21%; a correct FUGC-only fix moved it to 39.19% and that was ruled a
**fail** — noise, not improvement. The port is only accepted if the
shadow-clip percentage moves by a margin clearly outside that noise band.
Script this as a reusable, checked-in measurement rather than a one-off
manual number. Corroborate with a real visual check on the rendered image,
same standard already used for the inversion stage.

6.3 Go transcription — verify with `tools/pakon_parity.py` that Go and
Python agree bit-exact before calling this done.

## Verification summary

Every phase ends in a Unicorn-golden comparison against real DLL execution.
The project-wide acceptance test is Phase 6.2's shadow-clip measurement plus
a direct visual check on the reference frame — nothing is called "fixed"
without both.
