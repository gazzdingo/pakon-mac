# Vendored: MinHook

**Source:** https://github.com/TsudaKageyu/minhook
**Vendored from commit:** `d94c64d32ea37bc4f5ee47d580709f70c6fb6080` (2026-06-13,
`master` branch at the time this was vendored, 2026-08-14).
**Files taken:** `include/MinHook.h`, `src/*.c`, `src/*.h`, `src/hde/*`
(the full library is a handful of small C files — nothing trimmed).

## License — correction from "MIT"

This was requested as "the small, well-tested, MIT-licensed C hooking
library" — MinHook is indeed small and well-tested, but its actual
license, per its own `LICENSE.txt` (copied verbatim below this directory)
and its README's own badge, is **BSD-2-Clause** (plus a second BSD-2-Clause
block for the vendored HDE — Hacker Disassembler Engine — portions),
**not** MIT. Both are short, permissive, OSI-approved licenses with
materially the same terms (attribution + disclaimer, no copyleft), so
this doesn't change the licensing analysis for this project's own
build/distribution — but the exact license name matters for accuracy,
so it's corrected here rather than silently left mislabeled.

## Why MinHook (recap of the decision)

Chosen over hand-rolling entry-only trampolines: this project has 23 real
hook targets with unknown, varied prologues across three different vendor
DLLs, running against a real, physical, irreplaceable scanner mid-scan.
MinHook's job in this design is specifically the one part that requires
correctly parsing x86 instruction lengths well enough to safely relocate
a function's prologue bytes before overwriting them with a jump —
getting that wrong is a real crash/corruption risk in the target process.
MinHook is small, focused, has been used in production hooking scenarios
for over a decade, and vendoring it here means that risk is carried by a
widely-exercised, disassembler-based implementation (via the bundled
HDE32/HDE64 engines) rather than a one-off first attempt at the same
problem. See `../../win_inject/hookcore.h`'s header comment for how the
rest of this harness (the actual entry/exit logging engine) is built
*around* MinHook rather than by hand-patching prologues itself.

## What was NOT changed

Nothing in `include/` or `src/` was modified from upstream — this is a
straight vendor drop, not a fork. If MinHook itself needs a fix, prefer
pulling a newer upstream commit over patching the vendored copy in place;
if a local patch is ever unavoidable, note it here.
