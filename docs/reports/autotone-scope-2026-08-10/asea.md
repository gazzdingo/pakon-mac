# asea (producer)

## ColorNegativePath::analyzeAutoTone — "asea" capability scoping report

Binary: `PakonIMAu.dll` extracted from `research/sdk/PAKONF135.iso` (`fx35install/program files/Pakon/F-X35 COM SERVER/PakonIMAu.dll`, PE32, 7,598,080 bytes). Tooling: radare2 6.1.8 + r2pipe, working copy at `/tmp/pakon_work/PakonIMAu.dll`, full-analysis project saved at `/tmp/pakon_work/asea.r2p` (`aaa` completed in 427.6s). All addresses below were located by string cross-reference and then **confirmed by a raw-byte scan for `E8` relative-call opcodes** whose computed target matches the address (i.e. verified direct call edges, not inferred from proximity or naming alone).

### 1. Addresses — found, not assumed

| Function | Address | Size | Evidence |
|---|---|---|---|
| `ColorNegativePath::declareAsea` | `0x100f91f0` | 501 B | pushes own name + `\Atc\ansel\src\libPaths.ansel\cnMethods.cpp` |
| `ColorNegativePath::analyzeAsea` | `0x100fb080` | 846 B | same cpp string; guards with `"Asea capability not found."` |
| `ColorNegativePath::exportAsea` | `0x100ff0a0` | 864 B | same cpp string + same guard string |
| `AnsAseaCapability::AnsAseaCapability` (ctor) | `0x101d0e60` | 576 B | pushes own qualified name |
| `AnsAseaCapability::acquire` | `0x101d1260` | 1418 B | pushes own name; `"Failed in 'new AnsAseaCapability'."` |
| `AnsAseaCapability::analyze` (Cap-level wrap) | `0x101d1120` | 221 B | direct `call fcn.10274d10` |
| `AnsAseaCapabilityImpl::AnsAseaCapabilityImpl` (ctor) | `0x10273ed0` | 1685 B | pushes own qualified name (6×, SEH landing pads) |
| `AnsAseaCapabilityImpl::allocateMemory` | `0x10274590` | 423 B | pushes own name |
| **`AnsAseaCapabilityImpl::analyze`** | **`0x10274d10`** | **1240 B** | pushes `\Atc\ansel\src\libAsea.ansel\AnsAseaCapabilityImpl.cpp` + own name |
| `AnsAseaCapabilityImpl::export` | `0x102751f0` | — | pushes own name |

Verified direct call chain (each arrow = one confirmed `E8` edge):
`method.AnsCnEnhancedPath.virtual_4` (declare, `0x1006545a`) → `declareAsea` → `acquire` → `AnsAseaCapability` ctor → `AnsAseaCapabilityImpl` ctor.
`CnEnhanced_analyzeSceneSpecific` (`0x10069490`, called from `virtual_8`/`virtual_12`/`fcn.1006a160`) → `analyzeAsea` (call site `0x100699fe`) → `AnsAseaCapability::analyze` wrap (`0x101d1170`) → `AnsAseaCapabilityImpl::analyze`.

### 2. Size — measured, method cross-checked against calibration

BFS over direct-call edges only from `AnsAseaCapabilityImpl::analyze` (`0x10274d10`), single-project analysis, indirect count re-verified in a clean dedup pass (an initial run had a duplicate-queue bug inflating the indirect tally — corrected):

**29 functions / 6,831 code bytes / 111 indirect (vtable) call sites.**

Method sanity check: re-running the same script against the given calibration point `0x100fb730` (analyzeAutoTone) produced **166 functions / 71,760 bytes / 615 indirect** — function count and indirect count match the stated calibration (166 / 615) exactly; bytes are ~5.7% higher (71,760 vs 67,896), which I can't fully reconcile (possibly a build/analysis-pass difference) but is close enough to trust the method. I did **not** separately BFS from `declareAsea`/`analyzeAsea`/`acquire`/`analyze`-wrap — the 29/6,831/111 figure is scoped to the `Impl::analyze` entry only, mirroring how the Shasta calibration (189/44,427/386) was scoped to `AnsShastaCapabilityImpl::analyze`.

### 3. Execution gate — genuinely reachable/executed for CN-Enhanced, verified

`declareAsea` and `analyzeAsea` are called by **direct, unconditional `E8` calls from AnsCnEnhancedPath's own vtable methods** — `virtual_4` (declare) and the `analyzeSceneSpecific` chain — not through any shared switch/jump-table dispatch. `analyzeAsea`'s call site (`0x100699fe`) sits inside the same function and ~31 bytes before that function's call to `analyzeAutoTone` itself (`0x10069a1d`), i.e. asea runs in the same scene-analysis pass, immediately ahead of the tone stage. This is categorically different from the Shasta case, where the gate lived in the *caller* (`PIAnselStartNewRoll`'s jump table with no CN-Premium case) — here there is no such table anywhere in the chain; `declareAsea`/`analyzeAsea`/`exportAsea` are shared `ColorNegativePath` base code, but they are reached from CN-Enhanced's own class-specific methods unconditionally.

Caveat: I found no inline enable/disable-byte pattern (unlike autoTone's own `ctx+0xc` per-substage flag) gating asea, but a data/DPI-driven runtime disable wouldn't show up in static control flow, so I can't rule that out — only the absence of a code-level gate is verified.

### 4. What it writes, and plausible tone relevance

`AnsAseaCapabilityImpl::analyze` populates an `AnsAseaOperand` (methods found via string xref: `setRedAseaLut`, `setGreenAseaLut`, `setBlueAseaLut`, `setFlareAseaLut`, `setContrastAseaLut`, `dup`) — its own disassembly calls the same internal helper (`fcn.10273430`) three times, consistent with building one LUT per RGB channel, plus separate flare and contrast computations. This is read back by `ColorNegativePath::exportAsea` (`0x100ff0a0`, part of `AnsCnEnhancedPath::exportParameterPack`): `find("asea")` → RTTI `dynamic_cast` to `AnsAseaCapability*` → guard (`"Asea capability not found."`) → shared pack-append call (`fcn.100d4240`), folding the Asea operand into the same exported parameter pack that (per `docs/62-colour-engine-consolidation.md`, independently corroborated here) also carries `autoTone` (`0x10106f30`), `area`, `falloff`, `noise`, `balance`, `FUGC`, sharpening and defects.

Assessment: per-channel RGB LUT + flare + contrast is structurally tone/density-shaped data — not geometric/orientation/cosmetic (contrast with `orderOrientation`, a rotate/flip flag). However, `analyzeAutoTone`'s own 166-function direct-call closure contains **no** function that references the `"asea"` string, so `analyzeAutoTone` does not read Asea's operand itself; any effect on the rendered image is a **separate, parallel** contribution applied via the exported parameter pack alongside (not through) the tone stage. I did not trace `fcn.100d4240` or the downstream pixel-apply consumer, so "plausible tone effect" is the honest characterization, not a proven one.

### 5. Existing coverage in tools/ansel/ — none

`grep -rin asea tools/ansel/` (case-insensitive) turns up only three passing mentions in comments/docstrings (`shasta.go:94`, `pakon_analyse_roll.py:42`, `pakon_shasta.py:538`) that list "asea" as one of the 16 producer capabilities `analyzeAutoTone` may read — no ported function, no `_PORTED` flag, no DPI parser, nothing executable. By contrast `fugc` has 12/13 `_PORTED` flags true and `scpLut` has 3/4 (DPI parse, three-band-LUT parse, analyze-leaves all done; only balance-application open). No `asea/` directory exists under `vendor/ansel/anselinstalldir/dataPathItems/` (only `cna/`, `dra/`, `toneHelper/` were copied in), and I found none on the mounted FX-35 install disk either, consistent with asea being built-in-defaults rather than DPI-file-driven — inferred from absence within the standard tree, not an exhaustive ISO search.

---
Working files: `/tmp/pakon_work/PakonIMAu.dll`, `/tmp/pakon_work/asea.r2p` (r2 project), `/tmp/pakon_work/bfs_driver.py` + `/tmp/pakon_work/bfs_asea_out.json` (raw BFS reachability data), `/tmp/pakon_work/recount_indirect.py` (corrected indirect-site tally). Some earlier-session scratch files from a concurrent/prior instance of this same investigation (`/tmp/pakon_re/`, `/tmp/pakon_scratch/`) were read and cross-checked but not blindly trusted — every load-bearing claim above was independently re-verified against the binary in this session.