# Reverse-engineering playbook — patterns that transfer to the next capability

Everything below was learned porting `ColorNegativePath::analyzeAutoTone`
and its six subsystems (`docs/66`). None of it is specific to tone curves —
it's the reusable shape of *how this vendor DLL is built* and *how this
project verifies a port of it*. Written down here so the next capability
doesn't have to rediscover it.

**The capability this was written for is `area`** (`AnsAreaCapability` /
`libAREA.ansel`) — dust, scratch and blemish detection/correction, almost
certainly what the "Frosty — Digital Ice Technology" badge on the scanner
refers to. It's the single largest unported capability found on this
project: 732 functions / 299,737 bytes / 1,405 indirect calls, confirmed
running unconditionally on the colour-negative path, currently 0% ported.
Full writeup: `docs/64` §"The big one". Everything in this doc is written
with that port specifically in mind, but applies to `falloff`, `orderOrientation`,
`noiseTable`/`pnr`/`nra`, `dtt`, `pan`, `asea` too — the whole `docs/64`
backlog.

## 1. The generic capability-class shape

Every `Ans*CapabilityImpl` ported so far (`cna`, `dra`, `toneHelper`,
`contrast`, `ast`, `citras`) follows the same skeleton:

```
acquire()               — construct/fetch the Impl object, seed defaults
validate_parameters()   — sanity-check DPI-loaded params, can fatal
allocate_memory()       — size output buffers off validated params
analyze(...)            — the actual algorithm, writes results into ctx
```

dispatched through a `ctx+0xc` enable byte and looked up via
`AnsSceneContext::find` (`0x10022a40`) — a name-keyed, RTTI-typed lookup with
a documented miss behaviour (usually "continue with a default", occasionally
fatal — check per capability, don't assume). `AnsAreaCapability` almost
certainly has the same four-method shape and the same `find`-based wiring
into whichever driver function calls it (`AnsCnEnhancedPath`'s own code,
directly and unconditionally, per `docs/64`).

**Practical implication for `area`**: don't start by reading the 732-function
graph cold. Start by finding its `acquire`/`validate_parameters`/
`allocate_memory`/`analyze` four (or however many) entry points the same way
`citras`'s were found — self-naming assert/log strings first (see §4), vtable
slot layout second. That alone will probably prune the 732 down to a much
smaller "core orchestration" plus a long tail of leaf math, the same shape
`analyzeAutoTone` turned out to have (166 orchestration + subsystem bodies).

## 2. FPCW — check this before anything else

Unicorn's default x87 floating-point control word does **not** match what
the real DLL runs under. Every subsystem ported on this project needed it
set to `0x027F` (MSVC/Windows extended-precision default) to match real DLL
output. Getting this wrong doesn't crash — it silently produces plausible
but wrong numbers, which is far more dangerous than a crash.

**How to actually prove it matters** (don't just set it and move on — prove
it with a negative control): run the same golden case at the wrong FPCW
(Unicorn's default) and confirm it diverges from the real DLL's output. If
it doesn't diverge, that particular code path may not be FPCW-sensitive
(this happened with `dra`'s `keep_midpt_lut` — ~400 attempts to construct a
divergent case failed, and this was documented as a real limitation rather
than faked). `area`'s masking/correction math is very likely to include x87
float work (blend weights, distance falloffs) — assume FPCW-sensitivity
until you've tried to disprove it, not the other way around.

## 3. x87 double-rounding is a real, recurring vendor bug class

Found in `toneHelper`'s `calcStats`: the vendor's own code rounds a value,
writes the *rounded* result to memory, but leaves the *unrounded* value on
the x87 FPU stack — and downstream code reads the stack value, not memory.
This produces a genuine 1-ULP mismatch that only shows up if your port reads
memory (the "obviously correct" place to read from) instead of replicating
the same stack-vs-memory divergence. Watch for this anywhere the vendor code
computes a value, stores it, then keeps using it without reloading from
memory — a `fstp`/`fst` followed by continued FPU-stack use of the
pre-store value, not the stored one.

## 4. Finding real entry points and fixing wrong addresses

`PakonIMAu.dll` is unstripped — it retains C++ assert/log strings naming
their own source file and function (e.g. `"AnsCnEnhancedPath::declare"`,
`"\Atc\ansel\src\libPaths.ansel\CN-Enhanced.cpp"`). This has been the
single most reliable way to resolve a disputed or wrong address on this
project — **more reliable than static call-graph inference alone**, which
has produced multiple wrong-address claims that self-naming strings then
refuted:

- citras's real `analyze()` is `0x10223a20`, not the `0x10223860` an early
  report claimed (which decodes to garbage mid-instruction, inside the
  neighbouring `allocateMemory`).
- `AnsCnEnhancedPath::declare` had three competing candidates from three
  independent reports; resolved by finding the one address whose only
  in-image references were its own two self-naming strings.
- `cna`'s and `dra`'s "second variant" addresses were swapped in an early
  brief — found independently by two agents doing an E8 direct-call-site
  scan and cross-checking which capability's Impl class actually calls each
  candidate.

**When scoping `area`**: expect the same. With 732 functions, static
inference alone will produce wrong candidates; budget time to grep the
binary's string table for `"AnsArea"`-prefixed self-naming strings and use
those as the anchor, the same way `declare` was resolved.

## 5. DPI/TTC file conventions

`vendor/ansel/anselinstalldir/dataPathItems/<capability>/` holds each
capability's calibration data as `.dpi` (flat key/value) and `.ttc` (tone
curve — points/slopes, sometimes multiple parsed arrays per file: `dra`'s
`build_ttc_slopes` was a *third* array silently missing from an earlier
"verified" parser, see §7). Not every capability has DPI files in a full
vendor install — `ast` and `citras` don't; their params are confirmed
built-in constants instead. **Check whether `area` has a DPI directory
before assuming it needs a parser at all** — it may not.

## 6. Harness/tooling gotchas that will bite `area` too

These cost real debugging time on this port and will recur on any
732-function capability with a comparably large golden harness:

- **Duplicate CRT hook registration.** The shared `Emu` base harness class
  already hooks certain CRT VAs (e.g. `operator delete[]`). Adding a second
  hook at the *same* VA in a subsystem-specific golden file is not additive
  — both callbacks fire, double-popping the stack and corrupting execution
  in a way that looks like a real bug in the port. Check what `Emu` already
  hooks before adding your own.
- **Undersized scratch buffers cause silent overflow, not a crash.** `cna`'s
  golden harness under-sized a gaussian scratch buffer; the DLL wrote past
  it into adjacent allocation and produced a "plausible but wrong" reference
  value that took real effort to catch. Size scratch allocations generously,
  and when a golden comparison looks *almost* right, suspect the harness
  before suspecting the port.
- **A validation stub that always returns success is worse than no stub.**
  Found in `contrast`'s harness — every simulated vendor error path was
  silently converted to success, meaning bad test inputs were "passing" that
  should have been rejected. Any harness for a large capability like `area`
  will need CRT/error-path stubs; make them fail when the real path would
  fail, not unconditionally succeed.
- **Static reading invents patterns live execution disproves.** `dra`'s
  `keep_midpt_lut` had an early static reading that inferred a
  "monotonicity" rule from what looked like a meaningful register; live
  Unicorn register tracing proved it was a stale constant, not real logic.
  Treat any pattern inferred from disassembly alone as a hypothesis until a
  live trace confirms it, especially in a function as large as `area`'s
  detection/correction math is likely to be.

## 7. "Verified" can be quietly incomplete — re-derive the full read/write set

`DRA_TTC_PARSE_PORTED` was marked `True` and passed its golden tests for a
long time before a later pass discovered a whole third parsed array
(`build_ttc_slopes`, `0x10227e93`-`0x10227eab`) that the original "verified"
parser simply never touched. The golden tests that existed didn't fail — they
just never exercised the missing piece. **Lesson for `area`, which is 4× the
size of anything ported so far**: after a first pass declares a piece
"ported", do a second pass whose only job is to re-derive the complete set
of fields the real struct/class reads and writes (byte-offset dump, not
function-by-function), and diff that against what the port actually touches.
Don't trust "the tests pass" as proof of completeness on a capability this
size — it's proof of correctness only for what the tests happened to cover.

## 8. `flesh`'s accumulator is a real, already-located dependency of `area`

Not a process lesson — a concrete fact that saves `area` some work.
`docs/64` proved `flesh`'s per-channel accumulator (bytes `0x4b6`-`0x4bb` of
the shared driver state, written at `0x100fe471`-`0x100fe47d`) is **not**
read by `analyzeAutoTone`, but it *is* one of three confirmed real
consumers — and one of them is `analyzeArea` (`0x100e16d0`, driver call at
`0x10069a1d`... check `docs/64` for the exact citation). When `area` gets
ported, `flesh`'s accumulator is a required input, already located, with its
write site already identified. Start there instead of re-deriving it.

## 9. General project conventions that still apply

- `SCREAMING_SNAKE_CASE_PORTED = True/False` flags, one `pakon_<capability>.py`
  file, `False`-flagged code paths `raise RuntimeError` rather than
  silently no-op.
- Python ports + Unicorn-verifies against the real DLL; Go gets the verified
  result transcribed after, as terse constants. Don't invert this — Go isn't
  where the reverse-engineering happens.
- `tools/re/reachability.py` is the canonical BFS/reachable-set/set-diff
  tool, calibrated against Shasta's published numbers. Use it to scope
  `area` the same way it scoped `analyzeAutoTone`'s subsystems, rather than
  hand-rolling another scratch script.
- Extract `PakonIMAu.dll` fresh from `research/sdk/PAKONF135.iso` per task
  (it's gitignored, not pre-extracted anywhere). MD5
  `eea9dcf78ee21d4f7c515a6c2512242d`.
- Never touch the physical scanner for any of this work — everything is
  static analysis (radare2) or emulated (Unicorn), never live hardware.
- `captures/` (the owner's personal photographs) never gets committed,
  pushed, or described in any report, ever — this applies to `area`
  especially, since dust/scratch work will likely involve looking at real
  capture frames during development.

## Source

Drawn from the six-subsystem `analyzeAutoTone` port (`docs/66`) and its
predecessor scoping pass (`docs/63`, `docs/64`,
`docs/reports/autotone-scope-2026-08-10/`). Update this doc as new patterns
turn up in later ports — it's meant to accumulate, not freeze.
