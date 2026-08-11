# citras (subsystem)

## Summary — citras subsystem (`ColorNegativePath::analyzeAutoTone` stage 6)

**Binary:** `PakonIMAu.dll` (MD5 `eea9dcf7...`), analyzed with radare2 6.1.8 + r2ghidra, from `research/sdk/PAKONF135.iso` (mounted at `/Volumes/Pakon 135 v3.0`) via the extracted install at `/private/tmp/pakon_iso_extract/.../F-X35 COM SERVER`. Scratch work in `/private/tmp/citras_work/` (`citras_bfs_out.json`, `citras_analyze_pdg.txt`, `citras_afl.txt`, etc.).

### 1. Address correction, then size

**The task-given analyze address, `0x10223860`, is not a valid instruction boundary** — verified directly: linear disassembly at that address (with and without relocs applied) decodes to garbage (`test dword [ebx+0x68000000],ebp; das; ...`), mid-instruction of the neighboring `allocateMemory` function. The real `AnsCitrasCapabilityImpl::analyze` entry, found by backtracking from the five in-body xrefs to the string `"AnsCitrasCapabilityImpl::analyze"`, is **`0x10223a20`** (valid `push ebp`-style SEH prologue, 627 bytes, confirmed by decompilation — it's the function that calls `allocateMemory` at `0x10223810`, the function 0x10223860 falls inside).

Direct-call reachability BFS from `0x10223a20` (same method: r2pipe, `pdfj` per function, follow `call` with resolved `jump`, count `call`/`ucall`/`rcall` with no resolved target as indirect):

- **24 functions**
- **3,703 bytes** (span) / **3,674 bytes** (realsz)
- **72 indirect call sites**

Of the 24 functions, only **6 are citras-specific** (~2,062 bytes: `analyze` 627B, the param-validator `0x10223180` 394B, `allocateMemory` 299B, plus a ~742B out-of-range-exception-object cluster used only on the validation-failure path). The other 18 are generic CRT/STL plumbing (`operator new`, exception unwind helpers, string ctors/dtors) shared by the whole DLL. Essentially **all 72 "indirect" sites are IAT calls** (`call dword [sym.imp.MSVCP71.dll_...]`, `KERNEL32.dll_...`) — string/ostringstream/critical-section/`time` plumbing, not polymorphic vtable dispatch.

This is **not a strict subtraction from the 166/67,896/615 whole-chain total** — same caveat already applies to the Shasta comparison figure (189/44,427/386) the task cites: each subsystem's `Impl::analyze` is reached from `analyzeAutoTone` only through an indirect/vtable call, so a single BFS from `0x100fb730` doesn't cross into any subsystem's own body at all; each must be (and was) measured separately from its own entry point.

### 2. What it reads and computes

Decompiled `0x10223a20` and its first callee `0x10223180` (r2ghidra). Confirmed directly from the real F-X35 install (`.../anselinstalldir/dataPathItems/`, 43 subdirectories listed) that **no `citras/` or `ast/` directory exists** — corroborating "no data files, built-in" independent of the code comments.

- `0x10223180` is a **parameter validator** over 8 built-in scalar fields at fixed offsets in the `AnsCitrasCapabilityImpl` object: `sigma` (+0x10, must be >0), `blockSize` (+0x18, >0), `minAvoidance` (+0x1a, ≤100), `maxGradient` (+0x1c, ≥0), `lowGradientThreshold` (+0x1e, -1 or ≥0), `highGradientThreshold` (+0x20, -1 or ≥0, > low), `minValue`/`maxValue` (+0x22/+0x24, min<max). These are compiled-in defaults (no file to read them from).
- `analyze()` itself, after validating those 8 fields, does **no histogram, percentile, or LUT-build arithmetic**. It allocates a buffer (via `allocateMemory`) sized to an input count and performs a **plain `memcpy`** (4-byte-chunk loop + byte remainder) of an int16 array — handed to it as an argument by the caller, not fetched by name from the scene context — into its own private storage.
- Supporting strings (`AnsCitrasOperand::setToneLut`, `ImaI16CitrasOp`, `ImaCitrasOperationT<F>`, `AnsImaCitrasAggregate`) indicate citras packages that array as a **tone-LUT operand** for later per-pixel application; the actual gradient/sigma-driven computation the parameter names imply (edge-avoidance-style smoothing) evidently happens in those separate `Ima*CitrasOp` apply-time classes, which are **outside** `analyze()`'s own reachable set (not in the 24-function BFS).

Net characterization: **a parameter-validate + snapshot/store stage**, not a stats or LUT-build stage — the smallest and simplest of the six by a wide margin, consistent with having no DPI infrastructure to drive.

### 3. Execution-gate verdict: genuinely reachable — confirmed independently

Two independent checks, both from raw disassembly (not trusted from the doc comment):

- **`ColorNegativePath::declareAutoTone` (`0x100f95f0`)**: the citras registration block pushes `"citras"`, and at **`0x100f9cd8`** does `mov byte [eax+0xc], 1` unconditionally (guarded only by a debug-assert global at `0x106b5bd4` that's 0 in normal builds) — matches the doc's claim exactly, now binary-verified for citras specifically, not just cited.
- **`ColorNegativePath::analyzeAutoTone` (`0x100fb730`)** itself references `"citras"` by name at `0x100fbd00`, performs a context lookup (`call fcn.10020a40`), `RTDynamicCast`s the result, and has a `"Citras capability not found."` fallback string at `0x100fbddb` reached only on cast failure — i.e., the normal path is "found → proceed," with the standard `+0xc` byte test / virtual-call dispatch pattern used identically for every stage in this function. No additional citras-specific disabling condition (like dra's fatal `find("lighting")`) was found.

**Verdict: genuinely executed for a colour negative**, same as the other five non-pfd stages.

One honest gap: I could not fully pin down which small function is the literal per-capability "acquire" analogous to the doc's per-stage table (e.g. cna's `0x10132dc0`) — chasing that address showed it's called from *inside* `analyzeAutoTone` and itself hardcodes a call to cna's `Impl::analyze` (`0x1022ea50`), meaning the table's "acquire" column denotes a different, smaller wrapper than the ~1.2KB declare-time constructor I initially found. For citras, my best candidate for that declare-time constructor is **`0x1012c5a0`** (1206 bytes real, called from `declareAutoTone` at `0x100f9c2a`; contains both `"Failed in 'new AnsCitrasCapabilityImpl'..."` and `"Failed in 'new AnsCitrasCapability'..."` bad_alloc strings plus the `"AnsCitrasCapability::acquire"` assert label) — but I did not achieve the same certainty here as for the analyze address, the size numbers, the data reads, or the enable-byte gate, and I'm flagging that explicitly rather than asserting it.

### 4. Existing project coverage: none

`grep -rli citras tools/ansel/` returns only comments/docstrings in `tools/ansel/pipeline/main.go`, `shasta.go`, `tools/ansel/python-pipeline/pakon_ansel.py`, `pakon_shasta.py` — all documentation of the *gap*, zero implementation. No `.py`/`.go` code reads, parses, or reproduces any citras behavior.

---

**Verified from the binary this session:** analyze's real address (`0x10223a20`, correcting the task's `0x10223860`); the 24/3,703–3,674/72 BFS numbers; the 8-field parameter validator and memcpy-only body of analyze; the `+0xc=1` enable-byte write in `declareAutoTone`; the name-lookup/RTTI-check/not-found-fallback block for citras inside `analyzeAutoTone`; the absence of any `citras/`/`ast/` dataPathItems directory in the real install; zero implementation coverage in `tools/ansel/`.

**Not fully resolved:** the exact address of the small per-capability "acquire" wrapper the existing doc table's addressing scheme refers to (best candidate `0x1012c5a0`, moderate not high confidence) — tracing the full 395-basic-block body of `analyzeAutoTone` to place every stage's exact call site precisely was not completed in the time available.