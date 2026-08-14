# Live Frida hooks — real vendor pipeline, real scan, real Windows VM

**What this is.** A Frida instrumentation harness that hooks the REAL
`PakonIMAu.dll` / `TLA.dll` / `TLB.dll`, live, inside a real running `PSI.exe`
process, during a real scan of real film — not static Unicorn emulation, not
disk-image carving. It logs every hooked function's entry/exit (raw
registers, stack, and best-effort buffer previews) to structured JSONL,
tagged with a `call_id` per invocation and a `frame_id` per scene, so a human
can diff each real intermediate stage directly against this port's own
Python pipeline (`tools/ansel/python-pipeline/pakon_ansel.py` and friends)
run on the same frame.

**Why Frida, not x32dbg/x64dbg or an injected DLL.** Frida needs no target
rebuild, attaches to an already-running or freshly-spawned process without
installing a driver, and its JS agent runs inside the target process with
full read access to its memory — which is exactly what's needed to dump
buffer contents at each hook, not just register values at a breakpoint. A
debugger script (x64dbg) could do the same job but requires manual
breakpoint scripting per hook and a human present to step through it, rather
than a single script that runs unattended through an entire scan and streams
structured output. An injected IAT-hooking DLL would need a real build step
and target-process cooperation to load, which a debugger-free live capture
doesn't need. Given `PakonIMAu.dll`/`TLA.dll`/`TLB.dll` are documented
32-bit PE (PE32, `docs/62`), Frida's stock Windows support handles this
without any special configuration.

**What's here:**

- `agent.js` — the Frida agent (runs inside the target process). Defines
  every hook as `{dll, va, id, desc, cite}`, with a full citation to the
  `docs/` line or file each address comes from. Read the file's own header
  comment before touching it — it explains the VA→runtime-address rebasing
  convention and exactly why no hook invents a stack-offset argument decode.
- `host.py` — the Python controller (runs as a normal process, uses the
  `frida` pip package to attach/spawn, loads `agent.js`, and streams its
  `send()` messages to a JSONL log file on disk).

## Setup, on the Windows VM, once

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

## Hook table (see `agent.js` for the authoritative, cited list)

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
