# pan (producer)

## Summary: the "pan" capability (`AnsPanDetectCapability`) in `ColorNegativePath::analyzeAutoTone`'s dependency set

Method: radare2 (`aaa` full analysis + a prior cached r2 project already on this machine at `/private/tmp/pakon_re/PakonIMAu.dll`, extracted fresh from `research/sdk/PAKONF135.iso` → `fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`), plus a Python-based direct-call reachability walk (`walk.py`, already in that scratch dir, doing exactly what the calibration numbers describe: walk direct calls, tally unique callees/bytes, count indirect/`ucall` sites). r2ghidra was available but not needed — plain disassembly plus each function's own self-logged class-qualified name string (a convention used everywhere in this DLL) was sufficient to identify every address.

### 1. Addresses (verified, not assumed)

Source: `\Atc\ansel\src\libPanDetect.ansel\`.

| Symbol | Address | Size (realsz) | How identified |
|---|---|---|---|
| `AnsPanDetectCapability::acquire` | `0x10126860` | 1206 B | self-logs its own name; single caller |
| `AnsPanDetectCapability::analyze` (Cap wrapper) | `0x101262b0` | 333 B | self-logs its own name; called from `ColorNegativePath::analyzePostBalance` |
| **`AnsPanDetectCapabilityImpl::analyze`** | **`0x1021db80`** | **3635 B** | self-logs its own name; single caller (the Cap wrapper above) |
| `AnsPanDetectCapabilityImpl::AnsPanDetectCapabilityImpl` (ctor) | `0x1021d0f0` | 1639 B | self-logged |
| `AnsPanDetectCapabilty::initialize` (vendor's own typo, missing "i") | `0x101256c0` | 2251 B | self-logged |

**Correction to existing project documentation, verified from the binary:** `pakon_shasta.py:537`, `shasta.go:92` and `docs/63-port-status.md:85` all cite `0x10064d70` as `AnsCnEnhancedPath::declare`. It is not — `0x10064d70` is a 201‑byte, single‑basic‑block field‑zeroing base‑class constructor with 6 unrelated call sites (a generic capability-object ctor, likely shared by many capability types). The real `AnsCnEnhancedPath::declare` is **`method.AnsCnEnhancedPath.virtual_44` @ `0x10066b00`** (6142 B, 145 basic blocks) — it self-logs the string `"AnsCnEnhancedPath::declare"` repeatedly and, within it, pushes the capability class-name strings `AnsFilmLutCapability`, `AnsFleshCapability`, `AnsPanDetectCapability` at strictly increasing addresses (`0x10066d33` < `0x10066e32` < `0x10066ef4`), which matches the documented order (filmLut, flesh, pan, …) exactly. A parallel function, `method.AnsCnPremiumPath.virtual_44` @ `0x10052bc0`, is CN‑Premium's own declare with the same three strings in the same relative order — i.e. these two path classes each have their own declare, not a shared one.

### 2. Size (measured, same methodology as the calibration numbers)

Reachability walk from `AnsPanDetectCapabilityImpl::analyze` (`0x1021db80`):

**69 functions / 20,722 code bytes / 196 indirect (vtable) call sites.**

For scale against the given calibration: `AnsShastaCapabilityImpl::analyze` = 189/44,427/386; the whole 6‑subsystem `analyzeAutoTone` chain = 166/67,896/615. Pan is roughly a third of Shasta's function count, under half its bytes, and about a third of the whole tone chain's total size — a real, moderate subsystem, not a stub, but clearly smaller than either calibration point.

### 3. Execution-gate verdict: reachable and executed on `AnsCnEnhancedPath`, verified two independent ways — not gated like Shasta

- **Acquire.** `AnsPanDetectCapability::acquire` (`0x10126860`) is called from a shared routine at `0x10113b50` — which self-logs as `"declareBalance"` (`\Atc\ansel\src\libPaths.ansel\balanceMethods.cpp`), and which literally constructs a `std::string("pan")` (`push 0x105740b4 ; "pan"`) at `0x10113ea7` immediately before calling acquire at `0x10113ee0`, guarded only by one boolean field test (`byte[edi+2]`), not by any path-name switch. This `declareBalance` routine is called identically from **all four** `Cn*Path::virtual_4` methods: `AnsCnPremiumPath` (`0x1004ffa0`), `AnsCnOpticalPath` (`0x1005b921`), `AnsCnLockbeamPath` (`0x1006098a`), and **`AnsCnEnhancedPath` (`0x10065164`)**. No case excludes CN‑Enhanced — this is the opposite of what was found for Shasta (a jump table with no CN‑Premium/CN‑Enhanced case reaching its acquire).
- **Analyze.** `AnsPanDetectCapability::analyze` (`0x101262b0`) → `AnsPanDetectCapabilityImpl::analyze` (`0x1021db80`) is called at `0x100fe172` from inside **`ColorNegativePath::analyzePostBalance`** (`0x100fdc40` — confirmed by its own self-logged string `"ColorNegativePath::analyzePostBalance"` and `cnMethods.cpp`), which project docs already place inside the `CnEnhanced_analyzeSceneSpecific` chain: `analyzePostBalance → analyzeFugc → balanceAreaImage → … → analyzeAutoTone`.

What I could **not** fully trace: the runtime truth-value of the single boolean gate (`byte[edi+2]`) in `declareBalance` that decides whether the "pan" acquire branch is taken at execution time (vs. just being reachable code) — I did not chase back to the DPI/params struct that feeds it. Given it is the identical gate for all four `Cn*` classes and CN‑Enhanced's own `declare` (virtual_44) lists `AnsPanDetectCapability` specifically (not shared boilerplate), this is very likely on by default, matching the pattern already established for the 6 tone subsystems (`declareAutoTone` sets all enable bytes to 1 except `pfd`) — but I'm stating this as inferred, not measured.

### 4. What it writes, and its relevance to tone/exposure/density

`AnsPanDetectCapabilityImpl::analyze` guards on `"Image buffer is empty."` (it does take real pixel data), calls `find(AnsContextDmin, …)` to pull **"dmin"** out of `AnsSceneContext` as an input reference, then extracts and inspects four specific pixel bands: **first row, last row, top interior row, bottom interior row** of the frame (each with its own guarded error string, e.g. `"Can't extract top interior row of image."`). That is a border/mask-row inspection — the classic way to detect a panoramic (letterboxed) frame by checking whether the top/bottom bands are film-base/blank relative to `dmin`.

Its published output, per the vendor's own debug-dump string, is `AnsPanDetectResults:` with exactly one named field, **`bIsPanoramic`** — a boolean. I found no per-channel numeric field, LUT, gain, or offset written by this capability.

**Verdict: geometric/format classification, disconnected from per-pixel RGB/density math.** It *consumes* `dmin` (an exposure-adjacent quantity) only as a reference threshold to tell frame content from border; it does not write anything resembling a density, gain, or colour value. I could not conclusively identify every downstream reader of `bIsPanoramic` — a small accessor call follows the analyze() call at `0x100fe1da` (`fcn.10126830`) whose exact purpose I didn't resolve — but I searched for the capability-name strings of all six `analyzeAutoTone` tone subsystems (cna/dra/toneHelper/contrast/ast/citras) and found none referencing `"pan"` or `bIsPanoramic`; this is suggestive but not exhaustive proof that tone math never reads it.

### 5. Existing ported coverage: none

`grep -rli "pandetect\|bIsPanoramic\|AnsPanDetect" tools/` (both `tools/ansel/python-pipeline/*.py` and `tools/ansel/pipeline/*.go`) returns **zero hits**. By contrast, per `docs/63-port-status.md`, FUGC is 12/13 flags ported and SCPLut/`SCP_LUT_*` is 3/4 flags ported. Pan has no ported code at all — it is a genuine, currently-untouched gap.

---

**Verified from the binary:** all addresses/sizes in §1–2, the acquire-path fan-out across all four `Cn*Path` classes in §3, the `analyzePostBalance` call site in §3, the image-row/`dmin` reads and `bIsPanoramic` output in §4, and the zero-coverage grep in §5.
**Inferred, not measured:** that the `declareBalance` enable-gate is true by default for CN‑Enhanced at runtime (§3); that `bIsPanoramic` is consumed only by framing/geometry logic and never by the six tone subsystems (§4, searched but not exhaustively disassembled).
**Correction offered, not requested:** the address `0x10064d70` used elsewhere in this repo (`pakon_shasta.py`, `shasta.go`, `docs/63`) for `AnsCnEnhancedPath::declare` is wrong; the real one is `0x10066b00` (`method.AnsCnEnhancedPath.virtual_44`).

Scratch files used/produced live under `/private/tmp/pakon_re/` (pre-existing on this machine, same binary) — notably `out/afl.txt`, `out/strings.txt`, and `walk.py`; my own additional queries' raw output is at `/tmp/pan_walk.json`, `/tmp/pan_fcn10113b50.log`. No files in `/Users/guy/www/pakon-mac` were modified (read-only, as instructed).