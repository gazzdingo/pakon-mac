# Live pipeline hooks — real vendor pipeline, real scan, real Windows XP

**What this is.** Instrumentation that hooks the REAL `PakonIMAu.dll` /
`TLA.dll` / `TLB.dll`, live, inside a real running PSI process, during a
real scan of real film — not static Unicorn emulation, not disk-image
carving. Every hooked function's entry/exit (raw registers, stack, and
best-effort buffer previews) is logged to structured JSONL, tagged with a
`call_id` per invocation, so a human can diff each real intermediate stage
directly against this port's own Python pipeline
(`tools/ansel/python-pipeline/pakon_ansel.py` and friends) run on the same
frame.

**Three things live in this directory** — use the one that matches reality:

| | **`win_inject/`** | **`native/`** | **`agent.js` + `host.py`** |
|---|---|---|---|
| **Status** | **The chosen path for the real XP box.** | An earlier alternative, built and working, but **not** the one chosen — kept for reference. | Fallback for a non-XP target, if that's ever relevant. |
| Hooking mechanism | Vendored MinHook (trampoline/JMP hooking) + a hand-written generic entry/exit engine | Hand-rolled `INT3` single-step software breakpoints, no MinHook | Frida's `Interceptor.attach` |
| Needs on target | Nothing but 2 compiled files | Nothing but 2 compiled files | Python 3 + `pip install frida frida-tools` |
| Runs on genuine Windows XP? | Yes — verified CRT-free, KERNEL32-only, XP-stamped (see below) | Yes — same verification | **No** — see "Does this run on Windows XP?" below |

Why `win_inject/` over `native/` for the real machine: this project has 23
real hook targets across three vendor DLLs, with genuinely unknown
prologues, running against a real, physical, irreplaceable scanner
mid-scan. A general-purpose, widely-used, disassembler-based trampoline
engine (MinHook) is judged safer for that many varied targets than a
hand-rolled equivalent, even though the hand-rolled `INT3` approach in
`native/` also works and has one real advantage of its own (see
`native/README`-equivalent comments in `native/hookdll.c` — no code
relocation at all, just a 1-byte patch, always fully restored before the
real instruction runs). `native/` is left in the tree, not deleted,
because it represents real, independently-verified working effort worth
keeping for comparison — but it is not what `win_inject/`'s instructions
below assume, and the two should not be run against the same process at
the same time.

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
forward. Chasing down and trusting a 5-year-old debugger build for
something that touches a live, hardware-controlling process was judged not
worth it next to building a native injected-DLL solution fresh, verified
end-to-end in this repo, instead.)

**Native injection (`win_inject/`, and `native/`): yes**, and it's built
and verified for exactly that in this checkout, not just claimed — see the
next section for the specific, mechanically-checked evidence.

## `win_inject/` — the path for the real XP box

**What's here (`win_inject/` + `vendor/minhook/`):**

- `vendor/minhook/` — MinHook vendored in full (`VENDOR.md` in that
  directory has the exact source commit and a license correction — it's
  BSD-2-Clause, not MIT as originally described when this was decided).
  MinHook's job is the one part of this whole design that requires
  correctly parsing x86 instruction lengths to safely relocate a
  function's real prologue before overwriting it with a jump — exactly
  the part worth trusting to a small, widely-used, disassembler-based
  library instead of a one-off hand-rolled implementation, given this
  runs against real, irreplaceable hardware.
- `win_inject/mincrt.h` + `win_inject/freestanding_memfuncs.c` — **read
  `mincrt.h`'s header comment first.** This project's Homebrew mingw-w64
  toolchain has no way to produce a binary linked against genuine legacy
  `msvcrt.dll` — every normal build path (including `-mcrtdll=msvcrt` and
  explicit `-lmsvcrt`) resolves through `api-ms-win-crt-*.dll`, the
  Windows-10-era Universal CRT "API set" DLLs, which **do not exist on
  Windows XP**. A first build looked fine under Wine only because Wine
  stubs those DLLs for compatibility — masking exactly this problem.
  `mincrt.h` hand-rolls every string/formatting/file-I/O primitive this
  harness needs on top of `kernel32.dll` alone;
  `freestanding_memfuncs.c` separately provides real `memcpy`/`memset`
  (which vendored MinHook calls directly) the same way, in a translation
  unit that never includes `windows.h` at all — seeing why that
  separation matters (a same-file macro-redirect approach genuinely
  failed to compile, colliding with mingw's own `restrict`-qualified
  declarations) is in that file's own header comment.
- `win_inject/hookcore.h` — **read this file's header comment next.** It
  explains, in detail, why entry+exit logging for all 23 hooks needed a
  hand-written, calling-convention-agnostic generic engine (a
  "return-address swap" technique) rather than 23 typed MinHook detours:
  none of these 23 real functions' true signatures (cdecl vs stdcall vs
  thiscall vs fastcall, argument count) have ever been re-derived from a
  live disassembly — `agent.js`'s own header comment says exactly the same
  thing about the prior Frida version. Writing typed detours would mean
  inventing 23 unconfirmed signatures, which this project's own rules
  forbid.
- `win_inject/hookcore.c` — the engine implementation: JSONL logging (via
  `mincrt.h`'s `StrBuf`), `hooks.cfg` parsing, the MinHook install loop,
  and the two C functions (`HookEntryC`, `LogExitC`) called from the asm
  side.
- `win_inject/hookstub.S` — the ONE hand-written x86 asm file: a shared
  entry handler + return-address-swap exit thunk + 23 tiny per-hook
  stubs (`Thunk_00`..`Thunk_22`), all mechanically identical in shape.
  Full derivation of the stack layout is in this file's own header
  comment.
- `win_inject/hookcore_real_table.c` — the real 23-hook table. A
  byte-for-byte transcription of `agent.js`'s own `HOOKS` array (same
  addresses, same ids, same citations, same order — reused, not
  re-derived). `win_inject/check_table_sync.py` mechanically diffs the
  two files' `(dll, va, id)` triples so this is a checked fact:

  ```
  $ python3 tools/re/live_hooks/win_inject/check_table_sync.py
  OK: 23 hooks, identical (dll, va, id) in identical order.
  ```

- `win_inject/hookdll.c` — `DllMain` + a worker thread (install/logging
  work is deliberately kept OFF the loader-locked `DllMain` thread itself)
  that builds the real table and installs hooks, retrying for 60s for any
  DLL not yet loaded (same idea as `agent.js`'s own retry loop).
- `win_inject/injector.c` — the injector executable: classic
  `OpenProcess`/`VirtualAllocEx`/`WriteProcessMemory`/`CreateRemoteThread`+
  `LoadLibraryA`, confirmed fine for XP specifically (see the file's own
  header comment on why this technique, which has real caveats on modern
  ASLR-enabled Windows, is actually textbook-correct on XP, which has no
  ASLR at all).
- `win_inject/selftest.c` + `win_inject/build.sh selftest` — a dynamic,
  **actually-run** correctness test (see "What was actually verified"
  below) — not just a compile check. Dev-only, never copied to the XP box,
  built with the ordinary (non-freestanding) recipe since it only ever
  runs here under Wine.
- `win_inject/hooks.cfg.example` — copy to `hooks.cfg` next to
  `hookdll.dll` on the XP box to enable/disable individual hooks (or just
  their exit-hooking) without a rebuild.

### Build it (from this Mac, or anywhere with Homebrew)

```
brew install mingw-w64
cd tools/re/live_hooks/win_inject
./build.sh
```

This produces `hookdll.dll` and `injector.exe`. `build.sh` itself
re-verifies, via `objdump`, that both import **nothing but
`KERNEL32.dll`** and are stamped for the Windows XP (5.1) subsystem/OS
version — and fails the build if anything else shows up. This isn't a
claim taken on faith, it's checked mechanically every time:

```
== verifying no CRT dependency at all (must show ONLY KERNEL32.dll) ==
	DLL Name: KERNEL32.dll
	DLL Name: KERNEL32.dll
OK: only KERNEL32.dll referenced -- no CRT, UCRT, or anything else.
== subsystem/OS version stamp (must be 5.1 for XP) ==
MajorSubsystemVersion	5
MinorSubsystemVersion	1
```

`i686-w64-mingw32-gcc` (not the `x86_64-w64-mingw32-gcc` variant, also
installed by the same formula) is what targets 32-bit — using the 64-bit
cross-compiler would silently build a DLL that can never load into a
32-bit XP process. Both `hookdll.dll` and `injector.exe` are confirmed
genuine 32-bit PE binaries (`file` reports `PE32 executable ... Intel
80386, for MS Windows`), matching the confirmed-32-bit target
(`docs/68` line 10, `docs/70` line 105: `PakonIMAu.dll`/`TLA.dll`/
`TLB.dll` are PE32 i386).

### What was actually verified (not just "it compiles")

Beyond the clean, `-Wall -Wextra` build and the objdump import/subsystem
checks above, three separate things were dynamically tested under Wine
(`brew install wine`) before writing this section:

1. **`./build.sh selftest`** compiles `selftest.c` — four synthetic target
   functions, one per relevant Windows x86 calling convention (`__cdecl`,
   `__stdcall`, `__attribute__((thiscall))`, `__attribute__((fastcall))`)
   — installs real hooks on all four via the exact same engine
   (`hookcore.c`+`hookstub.S`+vendored MinHook) used for the real 23, then
   calls each hundreds of times (including 8-deep recursion on the cdecl
   target, and a second thread hammering the fastcall target concurrently
   with the main thread) and checks every result against an independently
   computed reference. **Actually run, under Wine, on this Mac:**
   `ALL PASS (0 failure(s))` — every call across all four conventions,
   recursion, and concurrent-thread use returned byte-identical results to
   the un-hooked reference. The resulting JSONL log showed exactly 330
   `enter` and 330 `leave` events (perfectly balanced) with correct LIFO
   nesting order on the recursive calls (a deeper call's `leave` logged
   before its parent's) — real evidence the return-address-swap shadow
   stack is behaving correctly under real recursion, not just "the numbers
   happened to match". All 667 log lines from that run were confirmed
   valid JSON.
2. **A real-but-throwaway end-to-end injection test**: a second, separate
   Wine process (`idle_target_for_testing.c`, not part of the shipped
   tooling, not committed) was launched, and the freestanding
   `injector.exe` was run against it by process name exactly the way it
   will be run against `PSI.exe` on the XP box. `injector.exe` found the
   target by name via `CreateToolhelp32Snapshot`, opened it, allocated
   memory, wrote the DLL path, resolved `LoadLibraryA`, and
   `CreateRemoteThread` genuinely returned a nonzero module handle — i.e.
   `hookdll.dll` really loaded into a separate, real process via the
   exact injection sequence that will run on the XP box, using the
   final, CRT-free, KERNEL32-only build. `hookdll.dll`'s own
   `DllMain`→worker-thread→`HookCore_Init` path ran for real inside that
   other process and produced a real JSONL log (`"hookdll.dll attached,
   23 hooks defined..."`) — the only reason no hooks installed in that
   specific test is that the synthetic target process never loads
   `PakonIMAu.dll`/`TLA.dll`/`TLB.dll`, which is exactly the expected,
   correct behavior.
3. **Two real bugs were caught this way, not by inspection**: (a) an
   early version of the per-call stack-dword hex buffer was sized for the
   wrong (shorter, unquoted) format and silently truncated mid-array,
   producing invalid trailing commas in the JSONL output (`,,,]`); (b) the
   first CRT-avoidance attempt (macro-redirecting `memcpy`/`memset` to
   hand-written replacements) failed to even compile, because mingw's own
   `string.h` declares those names too and the blind `-D` substitution
   collided with it — resolved by giving the replacements their own
   translation unit instead (`freestanding_memfuncs.c`). Both are direct
   evidence for why dynamically testing under Wine and mechanically
   checking the import table — not just getting a clean compile — was
   worth doing before trusting any of this against real hardware.

**What this does NOT prove:** none of the above ever ran against the real
vendor DLLs — those only exist on the real XP box, and this Mac cannot run
32-bit x86 code against real `PakonIMAu.dll`/`TLA.dll`/`TLB.dll` (no XP
environment here to load them into). The self-test proves the *mechanism*
— MinHook install, register/stack preservation, the return-address-swap
exit technique, thread-safety, and (separately) that the injector and DLL
genuinely load cross-process with zero CRT dependency — is sound. It does
NOT prove any of the specific 23 documented addresses are real function
entry points with prologues MinHook can safely relocate — that can only be
confirmed on the real box (see "Safety" below).

### Running it on the real XP box

1. Copy `hookdll.dll` and `injector.exe` (and, optionally, a `hooks.cfg`
   built from `hooks.cfg.example`) onto the XP box. Nothing else is
   needed — no Python, no Frida, no Visual C++ redistributable, no .NET,
   no network access from the XP box at all.
2. Start `PSI.exe` normally, as you always would.
3. From a command prompt on the XP box:

   ```
   injector.exe PSI.exe hookdll.dll
   ```

   (If `PSI.exe`'s actual process name differs, `tasklist | findstr /i psi`
   first, or pass a numeric PID directly — `injector.exe` accepts either.)

   `injector.exe` prints exactly what happened at each step (target PID
   found, DLL path resolved, remote thread created, `LoadLibraryA`'s
   return value) and exits nonzero with a plain-English reason on any
   failure — nothing about a failed injection attempt touches the
   scanner; it only ever reads/writes the target *process's* memory, never
   device I/O.
4. `hookdll.dll` installs hooks on a background thread inside PSI (retrying
   for up to 60s for any DLL not yet loaded) and starts writing
   `live_hooks_<timestamp>.jsonl` next to wherever `hookdll.dll` itself is
   (or at `HOOKDLL_LOG_PATH` if you set that env var before running
   `injector.exe`). **Go trigger a real scan in PSI's own UI** once you see
   `hook_installed` lines accumulate for the DLLs you expect to already be
   loaded.
5. The JSONL schema is deliberately close to the Frida version's:
   `status`, `hook_installed`, `hook_failed`, and `call` (`event: "enter"`
   / `"leave"`) records, with `hook_id`/`call_id`/raw register+stack
   fields — existing analysis habits from a Frida session carry over.

No separate "detach" step is needed — hooks stay installed for the life of
the process; just close PSI normally when done. If you need to remove them
without closing PSI, that isn't currently wired up as a live control (unlike
Frida's `rpc.exports.rescan()`) — worth adding if it turns out to matter in
practice, but not built speculatively here.

### Safety

- **Never touches the physical scanner directly.** Exactly like the Frida
  path, this only hooks software functions inside the vendor DLLs that run
  on already-captured frame data in process memory — no USB packet is ever
  sent, no calibration/EEPROM data is ever touched, no PIC firmware is ever
  flashed. Per `docs/68-handover.md`'s own hardware-safety rules, this
  falls squarely under "no hardware access is needed" for the same reason
  the Frida-based colour-science work does.
- **The real risk is a crash mid-scan, not corrupted hardware data.** If a
  hook installs against an address that turns out not to be a real
  function entry point (see the two `approximate: true` addresses below),
  or if MinHook's relocation genuinely can't handle a specific prologue, the
  realistic failure mode is `PSI.exe` crashing or hanging while a physical
  scan is in progress — which could leave the lamp on or the carriage
  mid-travel until manually recovered, not because this tooling sends any
  hardware command, but because the *controlling software* stopped running
  cleanly. **Recommended first-run sequence, not skipped for convenience:**
  run the injector against a running `PSI.exe` that is NOT mid-scan first
  (just sitting idle, or previewing without physically moving anything),
  confirm `hook_installed` lines look sane and PSI stays responsive for a
  few minutes, *then* trust it during an actual physical scan. Always turn
  the lamp off when finished, per the project's standing rule.
- **Two addresses are disabled by default, on purpose:**
  `fugc_mode_dispatch` and `tlb_f135_poly_remap` are flagged
  `approximate: true` in both `agent.js` and `hookcore_real_table.c` —
  their own citations say they were never independently re-confirmed as
  real function entry points (one has a literal "..." in its source
  citation). Hooking a non-entry address is exactly the scenario MinHook's
  prologue relocation isn't guaranteed to handle safely. Both stay OFF
  until you've verified the real entry address from a live disassembly on
  the XP box itself (x32dbg, or `r2 -c 'pd 10 @ <address>'` against the
  extracted DLL) — see `hooks.cfg.example` for how to turn one on once
  verified.
- **`tla_colneg_mmx_kernel`** is described in its own citation (carried
  over verbatim from `agent.js`) as "the inner MMX kernel itself" — if that
  turns out to run per-scanline or per-pixel-block rather than once per
  frame, entry+exit hooking it live could be high-frequency (log volume,
  measurable slowdown). It's on by default like everything else, but
  `hooks.cfg` lets you turn off just its exit-hooking, or disable it
  entirely, without a rebuild if a first live run shows it's too hot.
- **One real, explicitly-not-hidden technical assumption**: the generic
  entry/exit engine's exit path (the "return-address swap" — see
  `hookcore.h`'s header comment for the full derivation) assumes the
  hooked function returns via a normal `ret`/`ret N`. A function that
  instead unwinds via a C++ exception or SEH, skipping its own `ret`,
  would leave that call's shadow-stack slot unpopped — not a memory-safety
  bug (nothing is ever jumped to based on a stale slot), but that call's
  exit never gets logged, and in the worst case a later call at the exact
  same thread+recursion-depth could log against the wrong slot. Nothing
  about these 23 functions' documented behavior suggests they throw in the
  normal per-frame path, but this is exactly the kind of thing to notice
  in a live log (an exit record that looks like it belongs to the wrong
  call) rather than assume can't happen.
- MinHook itself is vendored, unmodified, from a well-established
  open-source project (`vendor/minhook/VENDOR.md`) — the part of this
  design most consequential to get right (safe prologue relocation) is
  handled by that library, not by anything hand-rolled in this repo.

## `native/` — an earlier alternative (not chosen, kept for reference)

Before landing on MinHook, a hand-rolled `INT3` single-step-breakpoint
approach was also built and independently verified working (also
CRT-free/KERNEL32-only/XP-stamped, via its own `native/minicrt.h` — the
identical toolchain problem `win_inject/mincrt.h` documents was hit and
solved the same way there first). It uses one-byte software breakpoints
rather than MinHook's trampoline relocation, with a disclosed limitation
around a few-instruction race window in multithreaded targets (see the
comment at the top of `native/hookdll.c`). Between the two working
approaches, MinHook was chosen for the real hardware run: a general,
widely-exercised trampoline/disassembler engine was judged safer than a
hand-rolled equivalent for this many hook targets (23) with genuinely
unknown, varied prologues across three DLLs. `native/hookload.exe` +
`native/hookdll.dll` are still there and still buildable
(`native/build.sh`) if `win_inject/`'s approach ever needs a point of
comparison — but the instructions above, not `native/`'s own README
section that used to live here, are what apply to the real XP box. Don't
run both against the same PSI process at once.

## Frida path — `agent.js` / `host.py`

**Use this only if the actual target machine ever turns out to be
something other than the real XP box** (e.g. a future non-XP dev/test
machine) — see "Does this run on Windows XP?" above for why it's not an
option for the real unit. Kept working and documented for that
contingency, not because it's expected to be used against the real unit
going forward.

**Why Frida, not x32dbg/x64dbg, for THAT case.** Frida needs no target
rebuild, attaches to an already-running or freshly-spawned process without
installing a driver, and its JS agent runs inside the target process with
full read access to its memory — good properties on a machine where
installing Python+Frida is easy. On the real XP box specifically, neither
Frida nor current x32dbg/x64dbg builds work at all (see above) — the
native path is not just preferred there, it's the only option.

**What's here:**

- `agent.js` — the Frida agent (runs inside the target process). Defines
  every hook as `{dll, va, id, desc, cite}`, with a full citation to the
  `docs/` line or file each address comes from. Read the file's own header
  comment before touching it — it explains the VA→runtime-address rebasing
  convention and exactly why no hook invents a stack-offset argument decode.
- `host.py` — the Python controller (runs as a normal process, uses the
  `frida` pip package to attach/spawn, loads `agent.js`, and streams its
  `send()` messages to a JSONL log file on disk).

## Setup, on the target machine, once (Frida path only — see above for native)

1. Install Python 3 on the target machine if it isn't already there (any
   recent 3.x; this was written against no version-specific Frida API).
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
3. Copy (or share, if the target machine already has repo access) this
   `tools/re/live_hooks/` directory onto it.

## Running it, during a real scan (Frida path)

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

Each `call` record's `pointer_scan` field (on `enter`, Frida path only —
the native/win_inject path logs raw stack dwords directly instead, see
`win_inject/hookcore.c`) previews every register/stack value that resolves
to live, readable memory — up to 64 bytes each, as both hex and a
signed-int16 array — plus a `known_constant_hits` list flagging any value
that matches a constant `docs/74` already documents (`1550` =
`neutralBalancePoint`/`lowFixedPoint`/`highFixedPoint`/setShifts pivot
`0x60E`; `1200` = `paperMin`; `2000` = `paperMax`; the shipped CN `fpo`
defaults `879`/`1250`/`1386`; that frame's `setShifts_out` example
`683`/`297`/`151` — all from `docs/74` §1/§9). Use those hits to identify
which register or stack slot holds which named field for a given hook,
empirically, from real data.

## Hook table (authoritative source: `agent.js`'s `HOOKS` array and
`win_inject/hookcore_real_table.c`, hand-kept in sync — see
`win_inject/check_table_sync.py`)

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
`HOOKS` in `agent.js` AND `hookcore_real_table.c` (re-run
`check_table_sync.py`) the same way every other entry is — cited, not
guessed.

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
part of building any of this. Both `agent.js` and `win_inject/hookcore.c`
never treat a documented VA as a literal runtime address — they always
resolve `base(dll) + (documented_VA - 0x10000000)` at hook-install time,
so a real running process's actual (rebased) load addresses are handled
correctly regardless. If a `TLA.dll`/`TLB.dll` hook looks wrong once you
have live data (garbage register state that never looks like a sane
prologue), that's a concrete signal the `0x10000000` assumption is wrong
for that specific DLL — open it in a live debugger and compare its own PE
header's preferred `ImageBase` directly.
