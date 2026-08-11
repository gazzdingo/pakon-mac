# Handover — read this first if you have zero context on this project

Written 2026-08-11 for an agent (or person) picking this up cold, in case
the current session runs out before the work is finished. Assumes nothing.

## What this project is

A native macOS port of the software for a **Kodak/Pakon F-135 Plus film
scanner** — a real, physical, discontinued (2002–2007) device that shipped
with 32-bit Windows XP-only drivers and has no vendor support on any modern
OS. Two halves:

1. **Hardware**: talking to the scanner's own USB/firmware interface
   directly (no vendor driver), controlling the lamp, motor/film transport,
   and CCD readout.
2. **Colour science**: reimplementing the vendor's actual image-processing
   pipeline — the code that turns raw CCD data into a correct-looking photo
   — by reverse-engineering the original Windows DLL, in Python (verified)
   and Go (the app's real render path).

The owner's own words, unprompted, and still true: **"we need to be very
careful not to break this device it is very expensive."** Read the hardware
safety section below before touching anything hardware-related.

## The repo has two remotes, and it matters which one you're looking at

```
origin  = https://github.com/gazzdingo/pakon-mac.git          (public)
private = https://github.com/gazzdingo/pakon-mac-private.git  (private mirror)
```

**They have diverged and are not simple superset/subset of each other.**
Concretely, as of this write-up:

- Public `docs/` jumps from `docs/06-roadmap.md` straight to
  `docs/62-colour-engine-consolidation.md`. **Docs 07–61 are not missing by
  accident** — they exist (`git log --all` finds the commits) but were
  deliberately never pushed to the public remote. They cover the entire
  hardware-repair saga: EEPROM corruption and recovery, PICM bootloader
  recovery, lamp bring-up, calibration recovery, temperature sensor
  decoding, component mapping, and more (`docs/08` through `docs/52` on the
  `private` remote).
- The `private` remote is itself **behind** on the colour work — its
  `docs/` listing stops at `docs/52`, meaning it does not yet have
  `docs/62`–`docs/68` (this file included). The two remotes have not been
  reconciled.
- **If you only have access to the public repo**, you will not see the
  hardware-repair history at all — only this file's summary of it below.
  **If you have access to `private`**, read `docs/26-HANDOFF.md` and
  `docs/46-handover-ansel.md` there for the detailed blow-by-blow (both are
  themselves handover docs from earlier sessions, same idea as this one).

Nobody has asked for these two remotes to be reconciled, and doing so
(merge or force-sync) is a real, history-altering git operation — don't
attempt it without an explicit ask. Just be aware the split exists so you
don't conclude work is "missing" when it's actually just on the other
remote.

## Hardware status — public docs are stale, read this instead

**`docs/06-roadmap.md` (public) is out of date.** It describes the lamp not
lighting and CCD readout not responding to illumination as unresolved
blockers. That was true when it was written; it no longer is. Real
photographs exist in this project's `captures/` directory and the entire
colour-science port (docs 58–67) is built and verified against **real
scanned frames** from this physical unit — the scanner works, the lamp
works, capture works. The private-repo docs (specifically `docs/26`, `docs/
31`, `docs/37`, `docs/40` — bootloader recovery, calibration recovery, lamp
sequencing) tell that resolution story; `docs/06` in public was simply never
updated to reflect it. If you only trust one thing here, trust this
paragraph over `docs/06`.

### Hardware safety rules — these are absolute, not situational

- **This is a real, expensive, hard-to-replace device.** Treat any
  hardware-touching action as higher-stakes than a normal software bug.
- **No hardware access is needed or expected for the colour-science
  work.** Everything in `docs/62`–`docs/68` is static analysis (radare2) or
  emulation (Unicorn) against the vendor DLL — never live hardware. If
  you're doing colour-port work, you should never need to touch the
  scanner at all.
- **Always turn the lamp off when done**, if you are doing hardware work.
- **Every capture and calibration read is always saved to disk first,
  never discarded.** Never delete a calibration — timestamp it and keep it.
- **`captures/`** (the owner's own photographs, scanned on this unit) is
  **never** committed, pushed, or described in any report or commit
  message, under any circumstances. This includes derived data that could
  reveal capture content (e.g. binary per-stage image buffers) — when in
  doubt, leave it out and say so rather than pushing it.
- Per `docs/06`'s own rules (still valid): never send USB packet Type 0 or
  outside 1–4 (wedges the firmware, requires a physical power cycle); never
  flash PIC firmware; never write calibration data without having read and
  backed up the existing EEPROM contents first.

## Standing project-wide rules (apply to every task, not just hardware)

- **No autonomous `git push` or PR creation.** Always ask first, every
  time, even if you pushed five minutes ago for a different change. Always
  run `git status`/`git diff` before staging, and stage explicit file
  lists — never `git add -A`. Watch for known scratch/litter files at repo
  root (`patch_sed8.py`, `replace.txt`, similar one-off patch scripts) and
  leave them out of commits unless asked.
- **Model tiering**: build with Sonnet, review/verify with Opus only if a
  Sonnet result looks questionable. This is explicit, standing guidance —
  don't default to the most expensive available model for routine
  reverse-engineering or port work.
- **Never round partial progress up to "done."** This project's own
  convention (`*_PORTED = True/False` flags, `raise RuntimeError` on any
  unported path if called) exists specifically so nothing silently
  no-ops. Follow the same spirit in prose: if something is 80% done, say
  80% done.

## Where the colour-science work actually stands right now

Read in this order:

1. **`docs/65-colour-science-status.md`** — the living dashboard. What's
   verified working, what isn't, and why each gap matters. Has its own
   "if you're picking this up cold" section at the top (§0).
2. **`docs/66-autotone-port-plan.md`** — the live, actively-maintained
   execution plan for the specific port in progress right now
   (`ColorNegativePath::analyzeAutoTone`, the vendor's real tone-curve
   stage, replacing a known-buggy stand-in that causes a visible shadow
   crush in every rendered frame). Has a phase-by-phase status table kept
   current as work lands — check this for exactly what's done vs. not.
3. **`docs/67-re-playbook.md`** — reusable reverse-engineering and
   verification patterns learned during this port, written with the next
   capability to port (`area` — dust/scratch/blemish removal, likely the
   scanner's advertised "Digital Ice" feature, currently 0% implemented
   and the single largest unported piece of the scanner's real
   functionality) specifically in mind.
4. **`docs/64-pruned-tone-producers.md`** — catalogue of every other real,
   currently-unported scanner feature found while scoping the tone port
   (vignetting correction, auto-rotation, sharpening, source-type
   detection, and `area` itself) — the backlog beyond this one bug fix.

**As of this write-up**: the tone-curve port's orchestration shell and all
six of its subsystems are done and Unicorn-verified bit-exact against the
real vendor DLL. What's left for that one port: `citras`-apply (a large,
~218-function piece with genuine unnamed math, in progress — check
`docs/66`'s status table for exactly where), then a mandatory final
assembled-verification pass that swaps the render path over. None of this
port's work is wired into the actual rendered image yet — that's
deliberate, it happens only at that final pass, after everything is proven
to agree with the real DLL end to end.

## Tooling available to you

- **radare2 + r2ghidra** — the only disassembler available. No IDA, no
  Ghidra standalone, no Binary Ninja.
- **Unicorn** (`UC_ARCH_X86, UC_MODE_32`) — emulates the real vendor DLL's
  actual machine code with controlled inputs, to prove a Python port is
  bit-exact. This project's core verification method, referred to as
  "golden" files (`pakon_*_golden.py`).
- **`tools/re/reachability.py`** — canonical reachable-function-set /
  byte-count / indirect-call-count tool, calibrated against known-good
  numbers from an earlier port. Use this instead of hand-rolling scope
  measurement.
- The vendor DLL (`PakonIMAu.dll`) is not pre-extracted anywhere in the
  repo — it's inside `research/sdk/PAKONF135.iso` (171MB, gitignored on
  purpose — deliberately excluded from any commit as disproportionate
  redistribution, unlike the smaller vendor data files under `vendor/`,
  which ARE committed on purpose). Extract fresh per task.

## If you're resuming mid-session

Check `docs/66-autotone-port-plan.md`'s status table first — it's kept
current. If a background agent was dispatched and this handover exists
because the session ran out before it finished, the agent's work (if it
committed anything, which agents in this project are generally told not to
do directly — the orchestrating session commits and pushes after review)
will show up as uncommitted files in the working tree; check `git status`
and `git log` to see what actually landed vs. what's still in flight. Don't
assume a task is done just because a doc says "in progress" — verify by
actually running the relevant `pakon_*_golden.py` file and checking for
`ALL OK`, the same standard this whole project holds itself to.
