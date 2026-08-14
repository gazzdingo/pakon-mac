# Live pipeline hooks — real vendor pipeline, real scan, real Windows VM

**What this is.** Two independent, interchangeable ways to hook the REAL
`PakonIMAu.dll` / `TLA.dll` / `TLB.dll`, live, inside a real running PSI
process, during a real scan of real film — not static Unicorn emulation, not
disk-image carving. Both log every hooked function's entry/exit (raw
registers, stack, and best-effort buffer previews) to structured JSONL,
tagged with a `call_id` per invocation and a `frame_id` per scene, so a human
can diff each real intermediate stage directly against this port's own
Python pipeline (`tools/ansel/python-pipeline/pakon_ansel.py` and friends)
run on the same frame.

- **`native/`** — a standalone, prebuilt `hookload.exe` + `hookdll.dll`, no
  Python, no Frida, no install step. **Use this one** if the target machine
  is genuine Windows XP (see below for why) — this is what this project's
  own target VM actually needs.
- **`agent.js` + `host.py`** (this directory) — the Frida-based path. Keep
  this documented and available for a NEWER Windows target (Windows 7+),
  where it's genuinely less work than the native path; see "Does this run
  on Windows XP" just below for why it is not the right choice for XP
  itself.

## Does this run on Windows XP?

**The Frida path (`agent.js`/`host.py`): no, not on genuine Windows XP,**
and this project's own docs confirm the target really is XP —
`docs/68-handover.md`: *"shipped with 32-bit Windows XP-only drivers and has
no vendor support on any modern OS."* Two independent, stacked blockers,
checked directly rather than assumed:

1. **CPython itself dropped Windows XP support in 3.5** (October 2015) —
   the official python.org installers for 3.5 and later require Windows
   Vista or newer; Python 3.4 is the last release that officially supports
   XP, and current `frida`/`frida-tools` wheels are not published for it.
   `pip install frida frida-tools` as instructed further down simply cannot
   complete on a genuine XP box.
2. **Frida's own native core has never had solid, maintained XP support.**
   A user-reported XP failure in `frida-website` issue #8 (2014) went
   unanswered; the project's own position (per its GitHub issue history) is
   that the SDK has been built against a toolchain/runtime that assumed no
   further XP demand since the VS2013-era upgrade, and XP support would
   only be revived by a volunteer XP maintainer stepping up, which hasn't
   happened.

(The debugger-script fallback originally considered instead of Frida,
`x32dbg`/`x64dbg`, was checked too and is **also** not an option on current
builds: `x64dbg/x64dbg` issue #2545 confirms a Dec-2020 snapshot switched to
`PSAPI_VERSION 2`, which needs Windows 7+, breaking XP support going
forward — the last snapshot confirmed still XP-compatible was
`2020-12-14_15-31`. Chasing down and trusting a 5-year-old debugger build
for something that touches a live, hardware-controlling process was judged
not worth it next to building `native/` fresh, verified end-to-end in this
repo, instead.)

**The native path (`native/`): yes**, and it's built and verified for
exactly that in this checkout, not just claimed. `hookload.exe` and
`hookdll.dll` are cross-compiled 32-bit PE binaries that import **nothing
but `KERNEL32.dll`** (no CRT of any kind — see `native/minicrt.h` and
`native/build.sh` for exactly why even the C runtime was dropped) and are
stamped with a 5.1 (Windows XP) subsystem/OS version. `native/build.sh`
re-verifies the import table with `objdump` on every build and fails the
build if anything else shows up — this isn't a claim taken on faith, it's
checked mechanically every time. See `native/README` section below for the
full walkthrough.

**Why not an injected IAT-hooking DLL as a compromise, or x32dbg's old
snapshot?** `native/` effectively **is** the injected-DLL approach — that
was always the documented fallback if Frida wasn't practical. Once genuine
XP support ruled out Frida, building it for real (rather than a stale
debugger snapshot) was the direct, verifiable choice.

**What's here:**

- `agent.js` — the Frida agent (runs inside the target process). Defines
  every hook as `{dll, va, id, desc, cite}`, with a full citation to the
  `docs/` line or file each address comes from. Read the file's own header
  comment before touching it — it explains the VA→runtime-address rebasing
  convention and exactly why no hook invents a stack-offset argument decode.
- `host.py` — the Python controller (runs as a normal process, uses the
  `frida` pip package to attach/spawn, loads `agent.js`, and streams its
  `send()` messages to a JSONL log file on disk).
- `native/hookload.exe` + `native/hookdll.dll` — **prebuilt, ready to copy
  onto the XP VM and run as-is.** `native/hookload.c` / `native/hookdll.c` /
  `native/common.h` / `native/minicrt.h` are the source; `native/build.sh`
  is the exact cross-compile command (needs `i686-w64-mingw32-gcc`, e.g.
  `brew install mingw-w64` on macOS) if you ever need to rebuild after
  editing the hook table.

## Using the native tool (`native/`) — the one to use on real XP

**On the Windows XP machine:**

1. Copy `native/hookload.exe` and `native/hookdll.dll` into the **same
   folder** together (`hookload.exe` looks for `hookdll.dll` right next to
   itself). Nothing else needs installing — no Python, no Visual C++
   redistributable, no .NET. If you ever rebuild from source, re-copy both
   files again as a pair; they're not independently versioned.
2. **Self-test before the real thing** (strongly recommended — this
   confirms the whole inject → breakpoint → log → single-step → re-arm
   pipeline actually works on your specific machine before you trust it on
   a real scan, since none of this could be tested against real Windows
   XP or the real vendor DLLs while building it):
   - Create an empty file named `selftest.flag` in the same folder as the
     two binaries.
   - Run `hookload.exe notepad` (or open Notepad first, then run
     `hookload.exe` with no argument and pick it from the list).
   - Within a couple of seconds, `pakon_hooks_pid<PID>.jsonl` should start
     growing with `"hook_id":"selftest_gettickcount"` entries (Notepad, like
     almost every Windows process, calls `GetTickCount` constantly) —
     `"event":"enter"` and `"event":"leave"` pairs, with real register/stack
     data. If you see those, the mechanism works end to end on this
     machine.
   - Delete `selftest.flag` before moving on (see below for why).
3. **The real run.** Delete (or never create) `selftest.flag` — leaving it
   in place also hooks `GetTickCount`, which fires so often it would flood
   the log for no diagnostic value during an actual scan. Run:
   ```
   hookload.exe pakon
   ```
   (or whatever your PSI executable is actually named — `hookload.exe` with
   no argument lists every running process so you can pick the right one
   if "pakon" doesn't match). It prints the exact log file path, something
   like `pakon_hooks_pid4212.jsonl` next to the two binaries.
4. **Trigger a real scan** in the target application's own UI now — every
   hook that actually gets called during the scan appends to that JSONL
   file in real time (tail it, or just watch its size grow).
5. There's no explicit "stop" step — the hooks stay installed for the life
   of that process. Close the target application (or just stop watching
   the log) when you're done. If you want the hooks fully removed without
   closing the target, there's currently no unload command built in;
   killing/restarting the target process is the clean way to reset.

**Log format** is the same JSON-lines shape as the Frida path (`call_id`,
`frame_id`, `hook_id`, `event`, `regs`, `stack`, `pointer_scan`,
`known_constant_hits`) — see "Diffing against the Python pipeline" below,
which applies to both paths identically. One native-specific field:
`"approximate_address"` mirrors `agent.js`'s per-hook flag for the two
addresses with a citation ambiguity (see the hook table below).

**Multithreading note.** The native tool uses one-byte `INT3` software
breakpoints, the same technique every from-scratch Windows debugger uses —
deliberately, not an inline jmp-trampoline hook (a trampoline needs a real
x86 length disassembler to safely relocate the bytes it overwrites; getting
that wrong corrupts the target's code, and this touches a live process
driving real hardware mid-scan — a 1-byte patch, always fully restored
before the real instruction runs, has no equivalent failure mode). This has
one disclosed, honest limitation: a few-instruction race window during the
restore/single-step/re-arm sequence on one thread, where a *different*
thread hitting the exact same address at that exact moment will run the
real instruction unlogged rather than triggering the breakpoint. This is a
known property of software breakpoints in multithreaded targets in general,
not specific to this file — see the comment at the top of
`native/hookdll.c` for the full explanation, including how entry+exit
pairing is tracked per-thread (TLS-based call stack, keyed by the real
return address read off the stack at function entry).

## Setup, on the Windows VM, once (Frida path only — see above for native)

1. Install Python 3 on the Windows VM if it isn't already there (any recent
   3.x; this was written against no version-specific Frida API).
2. Install Frida:

   ```
   pip install frida frida-tools
   ```

   `frida-tools` also gives you `frida-ps` (list running processes) and
   `frida-ls-devices`, useful for sanity-checking the setup before running
   `host.py`. No `frida-server` is needed — this all runs against Frida's
   **local** device (same machine as the target process), which is the
   normal case for instrumenting a native Windows process from Windows
   itself. `frida-server` is only needed for remote targets (Android/iOS,
   or a separate machine over USB/network) — not this setup.
3. Copy (or share, if the VM already has repo access) this
   `tools/re/live_hooks/` directory onto the Windows VM.

## Running it, during a real scan

**Attach to an already-running PSI:**

```
python host.py --process PSI.exe --out session1.jsonl
```

(If PSI's actual process name differs — check with `frida-ps` first, e.g.
`frida-ps | findstr /i psi` — pass whatever name or PID that shows.)

**Or spawn it fresh under Frida** (lets hooks install before any DLL loads,
at the cost of starting PSI itself from this script rather than by hand):

```
python host.py --spawn "C:\Program Files\Pakon\PSI\PSI.exe" --out session1.jsonl
```

Either way, once it prints `[hook_installed] ...` lines for the hooks whose
DLL is already loaded (and, for ones still pending, `[status] N hook(s)
waiting on module load...` — they retry for 60s), **go trigger a real scan
in PSI's own UI**: load a real colour-negative strip, let it preview/render
a frame, export if that's part of your normal workflow. Every hooked
function that actually executes during that scan gets logged.

When done, press **Enter** in the `host.py` console (or Ctrl+C) to detach
cleanly. This flushes and closes the JSONL file — nothing is lost by
stopping mid-scan either, since every event is written and flushed as it
arrives, not buffered until exit.

**Output:**

- `session1.jsonl` — one JSON object per line: `hook_installed`,
  `hook_failed`, `status`, and `call` (`event: "enter"` / `"leave"`) records.
  Every `call` record carries `call_id` (unique per invocation) and
  `frame_id` (bumped each time the per-scene driver, `0x10069490`, is
  re-entered) so you can `grep`/`jq`-filter to "everything that happened for
  frame 3" or "just the FUGC `setLutInfo` calls".
- `session1_buffers/` — only populated if you've wired up
  `dumpFullBuffer()` in `agent.js` for a specific hook (see below); empty by
  default.

## Diffing against the Python pipeline

Each `call` record's `pointer_scan` field (on `enter`) and
`pointer_scan_at_return` (on `leave`) previews every register/stack value
that resolves to live, readable memory — up to 64 bytes each, as both hex
and a signed-int16 array — plus a `known_constant_hits` list flagging any
value that matches a constant `docs/74` already documents (`1550` =
`neutralBalancePoint`/`lowFixedPoint`/`highFixedPoint`/setShifts pivot
`0x60E`; `1200` = `paperMin`; `2000` = `paperMax`; the shipped CN `fpo`
defaults `879`/`1250`/`1386`; that frame's `setShifts_out` example
`683`/`297`/`151` — all from `docs/74` §1/§9). Use those hits to identify
which register or stack slot holds which named field for a given hook,
empirically, from real data — then either read the value directly off the
JSONL for that call, or extend `agent.js` to call `dumpFullBuffer(hookId,
callId, tag, ptr, byteLen)` (already implemented, just not wired to a
specific pointer by default — see the file's header comment) once you've
confirmed which pointer is the real pixel/scanline buffer, to get a full
byte-exact capture into `session1_buffers/` for direct comparison against
the Python pipeline's own array at the equivalent stage.

## Hook table (see `agent.js` and `native/common.h` for the authoritative, cited list — hand-kept in sync between the two, same ids)

| id | module | VA (assumed base `0x10000000`) | what it is |
|---|---|---|---|
| `cn_enhanced_driver` | PakonIMAu.dll | `0x10069490` | per-scene driver — frame boundary marker |
| `analyze_auto_tone` | PakonIMAu.dll | `0x100fb730` | `ColorNegativePath::analyzeAutoTone` — tone-chain boundary |
| `sba_set_shifts` | PakonIMAu.dll | `0x10100260` | `ColorNegativePath::setShifts` — SBA neutral-balance OUT |
| `sba_set_shifts_12` | PakonIMAu.dll | `0x10100a37` | shipped CN `(1,2)` closed-form setShifts entry |
| `sba_get_shifts` | PakonIMAu.dll | `0x10124000` | `getShifts` |
| `sba_preference` | PakonIMAu.dll | `0x1028c780` | `Preference` — the confirmed writer of `+0x3a38` |
| `sba_apply_balance_shifts` | PakonIMAu.dll | `0x1019a0c0` | `AnsAreaCapabilityImpl::applyBalanceShifts` — real per-pixel apply |
| `fugc_analyze` | PakonIMAu.dll | `0x100fed00` | `analyzeFugc` |
| `fugc_set_lut_info` | PakonIMAu.dll | `0x101f82c0` | `setLutInfo` — FUGC's real apply-LUT build |
| `fugc_mode_dispatch` | PakonIMAu.dll | `0x101fc518` | FUGC mode dispatch — **approximate**, verify live |
| `analyze_falloff` | PakonIMAu.dll | `0x100fe960` | `analyzeFalloff` |
| `balance_area_image` | PakonIMAu.dll | `0x10102b20` | `balanceAreaImage` |
| `analyze_area` | PakonIMAu.dll | `0x100e16d0` | `analyzeArea` entry — docs/74's top remaining suspect |
| `analyze_attributes` | PakonIMAu.dll | `0x100fb3d0` | `analyzeAttributes` |
| `icc_xform_apply` | PakonIMAu.dll | `0x102f8420` | `ImaICCXForm::apply` — ICC transform |
| `icc_effect_op` | PakonIMAu.dll | `0x1016ede0` | `ImaICCEffectOp` — source/dest max scale (unresolved in docs/62 §12.4.2) |
| `icc_effect_op_ctor` | PakonIMAu.dll | `0x1016e680` | `ImaICCEffectOp` ctor — writes `this+0x118` |
| `tla_baddscene` | TLA.dll | `0x1003f7db` | `bAddScene` — real writer of FUGC's "dmin" bag |
| `tla_colneg_planar_scan` | TLA.dll | `0x100064d0` | `PIColorCorrectColNegPlanarScan` |
| `tla_colneg_mmx_kernel` | TLA.dll | `0x1001c470` | inner MMX kernel |
| `tlb_f135_poly_remap` | TLB.dll | `0x10034b9b` | F-135 ColNeg poly remap — **naming ambiguity, see agent.js** |
| `tlb_polypixel` | TLB.dll | `0x1000d880` | `PolyPixel` — general stage-2 3×10 quadratic |
| `tlb_afe_offset_write` | TLB.dll | `0x100299c0` | `FN_bDrvPutCcdAtoDOffsets` — AD9826 offset register |

## AFE gain — honestly unresolved

The task this harness was built for asks for an "AFE gain application"
hook. What's actually documented (`docs/72` §1.3) is the AD9826 **offset**
register encoder, `FN_bDrvPutCcdAtoDOffsets` @ `TLB.dll:0x100299c0`
(hooked above, `tlb_afe_offset_write`) — this port had a real two's-
complement-vs-sign-magnitude bug there, fixed 2026-08-12. **No distinct
address for a gain-register write function was found documented anywhere
in `docs/62` through `docs/74`** — only the *values* (`afe_gains` in
`tools/pakon_scan.py`, e.g. `[13,13,13]`) are tracked, not a named/addressed
vendor DLL function that writes them. Rather than invent a plausible
address next to the offset one, this is left as an open TODO with a
concrete search strategy, per this project's own RE playbook
(`docs/67-re-playbook.md` §4 — "grep the binary's string table for
self-naming assert/log strings first, more reliable than static call-graph
inference alone"):

```
# with TLB.dll extracted on the Windows box (or anywhere with radare2):
r2 -q -c 'izz~AtoD' TLB.dll
```

look for a self-naming string near `bDrvPutCcdAtoDOffsets` (e.g.
`bDrvPutCcdAtoDGains` or similar — the vendor's own naming convention for
this driver family is `FN_bDrv...`, confirmed for offsets, IR mode,
lamp-on, FPGA control/settings in `docs/70`) and its cross-reference
(`axt` in r2) gives the real entry address directly. Once found, add it to
`HOOKS` in `agent.js` the same way every other entry is — cited, not
guessed. Alternatively, since `FN_bDrvPutCcdAtoDOffsets` is already hooked
live, its `pointer_scan` capture during a real scan will show the raw
register/stack state right around the time gains are also being
programmed (these driver calls tend to run back-to-back during init) —
inspect the surrounding calls in the JSONL log by `tid` and rough
`call_id` proximity as a live lead, without needing r2 at all.

## Address-base caveat

Every VA above is quoted the way this project's own docs quote it — as an
absolute address assuming the owning DLL loads at `0x10000000`. This is
independently confirmed for `PakonIMAu.dll` (`tools/re/reachability.py`'s
own header: *"It loads at bin.baddr=0x10000000, which is what makes every
VA in docs/ line up"*; `docs/62` line ~1246: *"PakonIMAu.dll is PE32 x86
based at 0x10000000"*). `TLA.dll`/`TLB.dll` VAs throughout `docs/62`,
`docs/65`, `docs/66`, `docs/72` are all in the same address range for
files of a few hundred KB, consistent with the same convention, but this
was **not** independently re-confirmed for those two DLLs specifically as
part of building this harness. `agent.js` never treats a documented VA as
a literal runtime address — it always resolves
`Module.findBaseAddress(dll) + (documented_VA - 0x10000000)` at hook-install
time, so a real running process's actual (rebased) load addresses are
handled correctly regardless. If a `TLA.dll`/`TLB.dll` hook looks wrong
once you have live data (garbage register state that never looks like a
sane prologue), that's a concrete signal the `0x10000000` assumption is
wrong for that specific DLL — open it in a live debugger and compare its
own PE header's preferred `ImageBase` directly.

## Safety

Never touches the physical scanner directly — it only reads process memory
of the already-running vendor software. Standard hardware-safety rule for
this project still applies to the *scan itself* (this harness doesn't
initiate scanning, a human does, through PSI's normal UI) — see
`docs/68-handover.md`.
