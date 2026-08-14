# 57 — Recipe: trace what actually executes inside the colour DLLs

**Date: 2026-08-13.** Written to be run later, on the XP VM. Follows `docs/55`
(register bring-up) and `docs/56` (data-flow inventory), both captured by
hooking API boundaries. This one goes *inside* the DLL.

## Why another tool is needed

API hooking can only intercept symbols that cross a module boundary by name.
That is why `docs/55` worked — the register writes go through
`DeviceIoControl` — and why the colour maths cannot be captured the same way:
`PakonIMAu.dll` exports **200 symbols and they are all EXIF/JPEG plumbing**
(`ExifParser`, `ExifTagList`, `JpegCompress`, …). `cna`, `dra`, `toneHelper`,
`contrast`, `ast`, `pfd`, `citras`, `analyzeAutoTone` are **internal** and are
reachable only by address.

Seeing those requires **dynamic binary instrumentation** — tracing at
basic-block level regardless of exports.

## The question worth answering

`docs/56` found ~19 stages with no port equivalent (`pfd`, `dtt`, `dsba`, `ane`,
`dei`, `falloff`, `flare`, `dyefade`, `lighting`, `gainOffset`,
`blackPrinting`, `noiseFiltering`, `deRender`, `reRender`,
`neutralGammaAdjust`, `pan`, `area`, `nra`, `pnr`). But a *file being opened*
proves only that the path considered it — map-driven resolution opens whole
families.

**Coverage of one render answers which of them actually execute for a colour
negative**, and that determines how much is genuinely left to port. It also
settles, directly rather than by inference from a source comment, whether
Shasta runs on the CN-Enhanced path.

## Recommended: DynamoRIO + drcov

Chosen over Intel Pin because **drcov ships prebuilt** — no compiler and no
build environment on XP, which Pin's pintools require.

1. Download a **32-bit (ia32) DynamoRIO** release that still supports Windows
   XP. **Verify the XP support claim before committing time** — newer releases
   dropped it, and the last XP-capable version needs checking rather than
   assuming.
2. Extract somewhere simple, e.g. `C:\dr\`.
3. Run PSI under coverage:

   ```
   C:\dr\bin32\drrun.exe -t drcov -- "C:\Program Files\Pakon\PSI\PSI.exe"
   ```

4. **Render one frame**, then close PSI cleanly so the log is flushed.
5. Collect `drcov.PSI.exe.*.proc.log` (written to the working directory).
6. Upload it.

Coverage, not a full instruction trace: a complete trace of a render would be
enormous, and coverage answers the question.

## What I need back

The `.log`, plus — if drcov does not record them — the **module load addresses**
for `PakonIMAu.dll` and `TLB.dll`. drcov normally writes a module table, which
is what makes the log usable.

That table matters because the DLLs get rebased. In the `docs/56` capture
`PakonIMAu.dll` loaded at `0x08a40000` while its preferred base is
`0x10000000`, so a documented address maps as:

```
runtime = load_base + (documented_addr - 0x10000000)
0x08a40000 + (0x100fb730 - 0x10000000) = 0x08b3b730     <- analyzeAutoTone
```

Coverage must be normalised to **module + offset** before it means anything.
drcov does this itself; a raw instruction trace would not.

## What I will do with it

Map covered blocks back to module offsets and check them against the addresses
the port is already built on — `ColorNegativePath::analyzeAutoTone`
(`0x100fb730`), the six ported subsystems, and the unported stages named above.
The output is a straight answer to "which stages run for a colour negative",
and therefore a scoped remaining-work list rather than an estimate.

## Fallbacks

- **Intel Pin** — the standard DBI tool; a `calltrace` pintool gives ordered
  function entries rather than coverage. **Pin 2.14 is the last XP-compatible
  line** (3.x requires Win7+), and pintools must be compiled, which is the
  reason it is second choice here.
- **OllyDbg 1.10** — XP-native, no setup, has a run-trace that logs every
  instruction. Brutally slow and produces huge logs, but needs nothing
  installed and is a reasonable last resort for a short, targeted trace.

## Caveats

- Both DBI tools slow execution substantially. A render that takes seconds may
  take minutes. That is expected; let it finish.
- Instrumenting a process that drives hardware over USB can change timing.
  If the scan misbehaves under instrumentation, capture coverage of a **render
  from an already-scanned frame** instead of a live scan — the colour path is
  what we are tracing, and it does not need the scanner.
- If DynamoRIO will not run on this XP build at all, say so early rather than
  fighting it. The Unicorn harness already gives per-function truth on the Mac;
  what a live trace adds is *real state* — the actual selections and branch
  decisions a genuine render makes — not better arithmetic.
