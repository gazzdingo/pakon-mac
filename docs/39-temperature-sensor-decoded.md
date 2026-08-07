# 39 — The lamp temperature sensor path, decoded

Resolves most of what `docs/15-calibration-read.md` §6d left `[UNKNOWN]`, and
corrects §6b/§6d on which register carries which quantity.

Source: `research/native/TLB.text.asm`, function `fcn.1000b890` — the light-board
monitor. All addresses below are verifiable in that file.
`[VERIFIED-FROM-BINARY]` unless marked.

## Headline

**There are three temperature quantities, not one, and they come from two
different registers.** Register `0x84` is the *setpoint readback*; register
`0x88` returns the two *measured* temperatures — lamp and motherboard — packed
as two little-endian `u16`. Everything is in **1/16 °C**.

Doc 15 §6b/§6d describe `0x84` as "the temperature". It is the reference the
firmware compares against, not the measurement.

## Register map

| reg | width | call site | contents |
|---|---|---|---|
| `0x83` | 1 | `0x1000b8fe` → `fcn.10009700` | status byte, bit flags |
| `0x84` | 2 | `0x1000b99b` → `fcn.1000a0c0` | **lamp temperature setpoint**, u16, 1/16 °C |
| `0x88` | 4 | `0x1000ba65` → `fcn.1000a040` | **two measurements**, see below |

Register `0x88`'s four bytes unpack at `0x1000ba93`–`0x1000baa7`:

```
bytes [0:2]  ->  edi  =  measured LAMP temperature        (u16 LE, 1/16 °C)
bytes [2:4]  ->  eax  =  measured MOTHERBOARD temperature (u16 LE, 1/16 °C)
```

The unit is confirmed the same way doc 15 §6b found it: each value is `fild`-ed
and multiplied by `qword [0x1005c3b0]` = **0.0625**. (`qword [0x1005c3b8]` =
2³² is the unsigned-fixup addend applied when the `fild` sign bit is set — a
conversion artefact, not a scale factor. It appears only in the logging path.)

## The supervision logic

At `0x1000bc71` the code loads `ecx = [0x10075554] + 0x15a0` — that is **`LC`,
the temperature config object of doc 15 §6a**, at the same address the field map
uses. Every comparison below indexes it, which is what makes the field
assignments certain.

Writing `S` for the setpoint (reg `0x84`), `L` for measured lamp temp and `M`
for measured motherboard temp (reg `0x88`):

| test | address | condition | error bit set |
|---|---|---|---|
| lamp fault low | `0x1000bc87` | `L < S − LC[0xb8]` (`LampTempFaultLow`) | `0x00010000` |
| lamp warn low | `0x1000bca0` | `L < S − LC[0xbc]` (`LampTempWarningLow`) | `0x00020000` |
| lamp fault high | `0x1000bcb5` | `L > S + LC[0xc8]` (`LampTempFaultHigh`) | `0x00000800` |
| lamp warn high | `0x1000bccb` | `L > S + LC[0xc4]` (`LampTempWarningHigh`) | `0x00000400` |
| MB fault low | `0x1000bcd9` | `M < LC[0xcc]` (`MotherBoardTempFaultLow`) | `0x00040000` |
| MB warn low | `0x1000bceb` | `M < LC[0xd0]` (`MotherBoardTempWarningLow`) | `0x00080000` |
| MB fault high | `0x1000bcfd` | `M > LC[0xd8]` (`MotherBoardTempFaultHigh`) | `0x04000000` |
| MB warn high | `0x1000bd19` | `M > LC[0xd4]` (`MotherBoardTempWarningHigh`) | `0x02000000` |

Fault and warning are `if/else` pairs — a fault suppresses the matching warning.
All comparisons are **unsigned** (`jae`).

**This independently confirms doc 15 §6c from the opposite direction.** §6c
found that registers `0x8C`/`0x8F` carry *offsets relative to the setpoint* while
`0x8B`/`0x8D` carry *absolute* motherboard temperatures — derived from the write
path. The read path does exactly the same arithmetic: lamp bands are `S ± offset`,
motherboard bands are absolute. Two independent derivations, same structure.

## The abort mask decomposes exactly

`FN_bLampTemperatureStable` aborts on `[this+0x38] & 0x40548C0` (doc 15 §6d).
That constant is not arbitrary — it is precisely the fault bits above plus the
status-byte bits, with **every warning bit excluded**:

```
0x00000040  status 0x83 bit 5        -> set at 0x1000b9fe
0x00000080  status 0x83 bit 6        -> set at 0x1000ba05
0x00000800  LAMP FAULT HIGH
0x00004000  status 0x83 bit 0, and only if cfg[0x47c] >= 4   -> 0x1000b9e7
0x00010000  LAMP FAULT LOW
0x00040000  MB FAULT LOW
0x04000000  MB FAULT HIGH
----------
0x040548C0  exact, no leftover bits
```

Warnings `0x400`, `0x20000`, `0x80000`, `0x2000000` are deliberately absent:
warnings are logged, faults abort the wait. That the mask reconstructs bit-exact
from an independently derived table is strong evidence the decode is right.

## `TempSetpoint` / `TempLB` / `TempMB` are these three quantities

The light-stability log's columns (see `docs/38-lamp-temperature.md`) map onto
exactly the three values decoded here — `TempSetpoint` = `S`, `TempLB` = lamp
(light board) = `L`, `TempMB` = motherboard = `M`. The whole formatting block at
`0x1000bac9`–`0x1000bc5d` is gated at `0x1000babd` on
`[root + 0x162c]` — and `0x162c − 0x15a0 = 0x8c` = **`WriteLightStabilityLog`**,
which is `0` in our registry. That is why no log was ever produced, and it
confirms the LC field map's first entry from the read side too.

## What is still unresolved: the stability counter

Doc 15 §6d flags the predicate that sets `[this+0x298]` as unknown. The finding
here is sharper and stranger:

**Nothing in `TLB.dll` ever writes `+0x298`.** All ten references in `.text` are
reads (`0x100216c1`, `0x1002cf2c`, `0x1002cf8a`, `0x1002d007`, `0x1002d073`,
`0x1002d0f1`), two address-takes in a constructor/destructor pair
(`0x10037900`, `0x1004279c`), and two EH unwind funclets (`0x1005a439`,
`0x1005a915`). There is no `mov`/`inc`/`add` to that displacement anywhere.

The constructor at `0x10037820` builds a subobject at `+0x298` via
`fcn.10001c30`, whose first act is `mov dword [esi], 0x1005b368` — a **vtable
pointer**. If the object read by `FN_bLampTemperatureStable` is that class, then
`[this+0x298]` is a vtable address, always `> 0`, and the 300-second wait loop is
**unreachable** — the function returns TRUE immediately, every time.

Two candidate readings, and they are worth separating before anyone relies on
the wait:

1. **Same class** → the stability wait is dead code in this build, and lamp
   warm-up is governed only by `WaitForLamp_*` (5 s per channel) plus whatever
   the board does internally. `[INFERRED]`
2. **Different classes** → `+0x298` is a genuine counter written by another
   module (TLA.dll is the candidate; it is the layer that owns `TlaControlLeds`).
   `[INFERRED]`

The monitor `fcn.1000b890` does not settle it: its `this` has a different layout
(`+0xac` Timeout, `+0xb0` int, `+0xd0`–`+0xe0`, `+0xf0`–`+0x108` doubles, `+0x131`
board address), so the monitor object is **not** the object holding `+0x298`. The
monitor reports faults by OR-ing bits into a caller-supplied status word
(`[ebp+0x14]`), which is how `[this+0x38]` gets its bits — not by touching any
counter.

**To settle it:** disassemble TLA.dll and search for a write to `+0x298`, or for
whoever calls into the class constructed at `0x10037820`. That is the one
remaining thread.

## Practical consequences

* **Reading temperatures needs no calibration and no setpoint.** Poll register
  `0x88` and scale by `1/16`. You get lamp and motherboard °C directly. This
  works regardless of `UseTemperatureSetpoints`.
* **Register `0x84` tells you the setpoint the board is actually using** — which
  is how to discover the board's internal default without ever writing `0x8E`.
  Worth reading once at bring-up and recording; it is the number doc 38 lists as
  unknown.
* **Watch the status byte `0x83`.** Bits 5 and 6 abort on their own, before any
  temperature is even read.
* **A safe host-side supervisor** can replicate the eight comparisons above with
  your own thresholds without writing anything to the board.

## Note on binaries

Two copies of `TLB.dll` are on this Mac, both **536 576 bytes** — matching doc
15's build size — but with **different MD5s**:

```
193d9b2ce0a4b77ae9b78262bd06c0fc   Downloads/Pakon Update/fx35install/.../TLB.dll
e7f21021e0140c1935a3ae4de7bd3498   Downloads/FX35_PR1/installer/InstallationFiles/TLB.dll
```

Same size, different content — so there are at least two builds in circulation
and size alone does not identify one. Analysis should be pinned to a hash.
`research/native/TLB.text.asm` is not currently attributed to either.
