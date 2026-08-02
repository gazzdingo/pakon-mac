# 14 — Lamp control, decoded from TLB.dll

This supersedes the "lamp = one register write" reading. That reading was
incomplete, and acting on it produced a long series of accepted-but-dark
results.

## What `FN_bDrvLampOn` actually does — [VERIFIED-FROM-BINARY]

`FN_bDrvLampOn` = `TLB.dll:fcn.1002c5f0`. It is **2,175 bytes**, not a single
register poke, and it issues **three** register writes to the light board:

| Reg | Width | Emitter | Contents |
|---|---|---|---|
| `0x80` | 1 B | `fcn.10009ba0` `PutRegisterByte` | enable bitmask |
| `0x81` | 5 B | `fcn.10009ae0` `PutRegister` | **LED levels** |
| `0x82` | 12 B | `fcn.10009ae0` `PutRegister` | **LED duty cycles** |

Each write is guarded by a comparison against cached state
(`[esi+0x29c]`, `[esi+0x2a4]`, `[esi+0x2a8]`, `[esi+0x2ac]`, `[esi+0x2b0]`) —
the function only transmits a register whose value has changed.

Enable bitmask construction:

```
    edi = 0
    if (arg_ch  != 0) edi  = 1      ; bit 0 = visible lamps
    if (arg_10h != 0) edi |= 2      ; bit 1 = IR lamp
```

The `0x81` write, exactly:

```
    PutRegister(log, addr=<light board>, reg=0x81, buf=&var_5ch, n=5, nolock=0)
        buf[0] = cl   buf[1] = al   buf[2] = dl   buf[4] = bl
```

The `0x82` payload is assembled from **four float→byte conversions**
(`fcn.10048e9c` / `fcn.100490b0`), one per channel — R, G, B, IR.

## Why every static "lamp on" attempt failed — [VERIFIED]

Two independent reasons, both now clear:

1. **`0x81` and `0x82` are write-only.** Reading them returns the block-read
   window, not the LED settings. An earlier session read `0x81` as
   `40 06 00 40 25`, concluded "levels are non-zero, so drive is not the
   problem", and moved on. **That conclusion was unfounded** — the read never
   touched the level registers. The levels were plausibly zero throughout.
2. **`0x80` alone is only an enable.** With zero drive programmed, enabling
   yields exactly the observed behaviour: `07 02 40 00` success and darkness.

## Where the drive values come from — [VERIFIED-FROM-BINARY]

`FN_bBeforeScan` (`fcn.1002dbd0`) calls `LampOn` at `0x1002e40a` with:

```
    push ebx                 ; log
    push 1                   ; visible = 1   (literal)
    push [esi+0x378]         ; IR flag
    push [eax+0x58]          ;
    push [eax+0x5c]          ;  five integer light parameters
    push [eax+0x60]          ;
    push [eax+0x64]          ;
    push [eax+0x28]          ;
    ; and four doubles pushed via the FPU:
    ;   [eax+0x90] [eax+0x98] [eax+0xa0] [eax+0xa8]
```

`eax` points to a light-configuration structure (`CiConfigLight`). The four
doubles are the per-channel **duty cycles**, matching the API fields
`dfDutyCycle_R / _G / _B / _Ir`; the five integers correspond to the
`iCurrent_R / _G / _B / _Ir` family.

At `LampOn` entry all four duty-cycle locals are initialised from the constant
at `.rdata:0x10067008`, which is the double **`-1.0`** — a "not specified"
sentinel. So a caller that supplies no duty cycles programs no drive.

## Consequence

**The lamp cannot be lit without programming drive values**, and those values
are per-unit calibration data. They are read from the scanner via the
`CalibrationGetLightLED` path, not invented.

The correct sequence is therefore:

1. read the unit's LED settings (calibration path)
2. write `0x81` — 5 bytes of levels
3. write `0x82` — 12 bytes of duty cycles
4. write `0x80` — enable bitmask (`1` visible, `2` IR, `3` both)

Steps 2 and 3 were missing from every attempt so far.

> **Do not invent LED drive values.** These are currents into an LED array.
> Guessing risks overdriving the illuminant, which is not a recoverable
> mistake. Read the unit's calibrated values first.

## Still open

- The exact byte order within the `0x81` (5 B) and `0x82` (12 B) payloads.
  The assembly assigns `buf[0]`, `buf[1]`, `buf[2]`, `buf[4]` from separate
  registers; `buf[3]` is not written in the path examined.
- The scaling applied by `fcn.10048e9c` / `fcn.100490b0` when converting the
  duty-cycle doubles to bytes.
- Where `CiConfigLight` is populated at start-up, which is what would give
  known-safe defaults without a live calibration read.

## Separately: acquisition gating — [VERIFIED on hardware]

Type 4 commands `0xd8`–`0xdf` on the light board affect the CCD stream. The
EP 0x86 level dipped at `0xd8` and the stream stopped entirely from `0xdf`,
requiring a power cycle to recover. This is the stream gate that could not be
found by static analysis. The precise command boundaries are not yet
established — narrowing them is eight targeted commands, not a sweep.

## The real reason the lamp never lit — [VERIFIED-FROM-BINARY]

The F-135 Plus illuminant is a **temperature-stabilised LED array**. TLB.dll
carries a whole subsystem for it, recovered from the FN name table:

```
FN_bLampWarmUp              FN_bLampWarmupFromStandby
FN_bLampTemperatureStable   FN_bSetLockedLampTemp
FN_bSetLampStartingDifferential
FN_bDrvInitLampTemperatures FN_bChangeLampTemperature{,Scanning,LampOff,AfterDelay}
FN_bDrvPutLampLevel         FN_bDrvPutLampLevelIr
FN_bLampDelayOff            FN_bLogHardwareStatusLamp
```

Corroborating hardware evidence: the built-in self test includes
`EC_BistPiclTeCoolerFail` — there is a thermo-electric cooler on the light
board.

`FN_bDrvInitLampTemperatures` (`fcn.1002d190`) writes **seven** registers:

| Reg | Emitter | Note |
|---|---|---|
| `0x8F` | `fcn.10009ae0` `PutRegister` | temperature setpoint block |
| `0x8C` | `PutRegister` | temperature setpoint block |
| `0x8B` | `PutRegister` | temperature setpoint block |
| `0x8D` | `PutRegister` | temperature setpoint block |
| `0x8E` | `fcn.1000a9e0` | separate emitter |
| `0xD0` | `PutRegisterByte` | |
| `0xD1` | `PutRegisterByte` | |

**Every lamp attempt in this project wrote only `0xD0` and `0xD1`.** The four
setpoint blocks `0x8B`–`0x8F` and `0x8E` were never written. With no setpoints
programmed, the temperature loop is unconfigured, `FN_bLampTemperatureStable`
can never be satisfied, and a temperature-locked LED array will not fire.

This explains the entire pattern observed on hardware:

- `02 04 40 01 80 01` returns `07 02 40 00` (the board accepts the enable)
- lamp status reg `0x83` changes `00` → `0x10` (the board acts on it)
- LED levels and duty cycles are programmed and non-zero
- and the illuminant stays dark

The enable is genuine; the lamp is simply held off by its thermal interlock.

### Correct lamp-on sequence

1. `FN_bDrvInitLampTemperatures` — write setpoints `0x8B`, `0x8C`, `0x8D`,
   `0x8E`, `0x8F`, then `0xD0`, `0xD1`
2. `FN_bLampWarmUp` — poll until `FN_bLampTemperatureStable`
   (lamp temperature is readable at reg `0x84`, 2 bytes)
3. `FN_bDrvPutLampLevel` / `FN_bDrvPutLampLevelIr`
4. `FN_bDrvLampOn` — registers `0x81`, `0x82`, then `0x80`

> **Do not invent temperature setpoints.** These drive a TEC controlling an LED
> array. Wrong values risk thermal damage to the illuminant, which is not
> recoverable. The setpoints are per-unit calibration and must be read from the
> scanner (`FN_GetCalibrateInfoLight`) or recovered from the calibration
> block, not guessed.

### Still needed

- The payload layout and source of the `0x8B`–`0x8F` setpoint blocks.
- The read path for the unit's calibrated temperatures
  (`FN_GetCalibrateInfoLight`, and the `Config/` calibration data).
- Whether `FN_bLampWarmUp` polls reg `0x84` against a threshold, and what
  that threshold is.

## Where the setpoints come from — [VERIFIED-FROM-BINARY]

`FN_bDrvInitLampTemperatures` sources its values from a **host-side global
configuration structure**, not from a scanner read:

```
    esi = [0x10075554]            ; global config pointer
    ax  = word [esi + 0x165c]     ; temperature value
    esi += 0x15a0                 ; sub-structure
    neg ax                        ; NEGATED
    buf[0] = lo(ax)
    buf[1] = hi(ax)               ; after sar eax, 8
    buf[2] = byte [esi + 0xc4]    ; = [global + 0x1664]
    buf[3] = byte [esi + 0xc5]    ; = [global + 0x1665]
    PutRegister(log, addr, reg=0x8F, buf, n=4, nolock=0)
```

The remaining setpoint registers (`0x8C`, `0x8B`, `0x8D`, `0x8E`) follow the
same pattern with different offsets into the same structure.

**Implication:** the temperature setpoints are *configuration*, not per-unit
calibration burned into the scanner. They are therefore recoverable from the
vendor's defaults rather than requiring a live calibration read — a materially
easier and safer problem than first assumed.

Note the negation (`neg ax`): the value programmed into the register is the
two's-complement negative of the configured temperature. Any reimplementation
must reproduce that, or the thermal loop will be driven the wrong way.

### Next decode

1. Find where `[0x10075554 + 0x165c]` and `+0x1664/0x1665` are populated at
   start-up — registry (`Software\Pakon\TLB`), a config file, or compiled-in
   defaults.
2. Recover the same for `0x8B`, `0x8C`, `0x8D`, `0x8E`.
3. Determine the stability threshold `FN_bLampWarmUp` polls reg `0x84` against.

Only then is it safe to program the loop and warm the lamp.

## Hunting the setpoint defaults — where the trail currently ends

Searched and ruled out:

- **Shipped config files** — no `TempSetpoint`, `LampTempWorking` or
  `UseTemperatureSetpoints` in any `.ini`/`.txt`/`.cfg`/`.dat`/`.def`/`.dpi`
  under the distribution.
- **Both MSIs** — the installer Registry tables contain none of these names, so
  they are not installed registry defaults.
- `TempMB TempLB TempSetpoint VisOn IrOn Curr…` in TLB.dll is a **CSV log
  header** for `PakonLampLog.txt` / `PakonCalibrationLog_*.csv`, not a set of
  config keys. Do not mistake it for one.

Still live:

- `LampTempWorking`, `UseTemperatureSetpoints`, `LampTempFaultHigh/Low`,
  `LampTempWarningHigh/Low` exist as **UTF-16** strings in TLB.dll, which is
  the encoding used for registry value names elsewhere in the binary
  (`Software\Pakon\TLB`). They are most likely read at runtime with
  compiled-in fallbacks.
- The config structure at `[0x10075554]` has **155 references** across TLB.dll,
  so isolating the routine that initialises offset `+0x165c` needs targeted
  work rather than a pattern search.

### The specific next step

Find the initialiser for `[0x10075554] + 0x165c`, `+0x1664`, `+0x1665` and the
equivalents feeding registers `0x8B`, `0x8C`, `0x8D`, `0x8E`. Two viable
routes:

1. Set a data breakpoint conceptually — trace which function writes those
   offsets, by disassembling the config-allocation path and following the
   defaults it stores.
2. Read the values off a **working** F-135 running the vendor software, via the
   lamp log (`PakonLampLog.txt`), which records `TempMB`, `TempLB` and
   `TempSetpoint` per scan. That file would give real, in-service values
   directly, and is the lowest-effort path if any Pakon user can supply one.

Route 2 is worth pursuing first — a single lamp log from a working scanner
would settle the setpoints empirically without any further disassembly.

## What the vendor documentation says — [VERIFIED from PSI.chm and UserManualF135.pdf]

Extract `PSI.chm` with `7z x PSI.chm` (172 topics). The F-135 user manual PDF
text is recoverable by inflating its content streams.

### The documented start-up sequence

From `UserManualF135.pdf`:

> "There are two types of calibration for the F-135. Color calibration is set
> during the manufacturing process, as well as any service that involves the
> CCD or any optical filter. They consist of a series of steps performed when
> the scanner is first turned on, as shown below:
> **Start-up corrections → Initial LED warm-up → Gain and exposure Control
> Corrections → Run Time Corrections**"

**This is the missing system-level piece.** The illuminant is brought up as part
of an initialisation sequence — `InitializeScanner` — not by a standalone lamp
command. Every attempt in this project sent isolated register writes to a
scanner that had never been initialised.

`FN_bInit2` (`fcn.1000b100`) is the driver-level entry point; the corrections
above map onto `ForceCorrections`, `FN_bDrvInitCcd`, `FN_bDrvInitLampTemperatures`
and the gain/exposure setters (`fcn.100298b0` / `fcn.100299c0`).

### Panel LEDs — red is not documented

The manual lists only:

| LED | States |
|---|---|
| Power | solid green = +5 V present; off = not |
| Status | solid green = ready; blinking green = scanning; blinking yellow = cannot scan |
| Film | green = safe to load film |

**No red state is documented for any panel LED.** The red glow the operator
reports is inside the machine, which is consistent with the illumination bar or
an internal indicator rather than a fault lamp.

### Lamp warm-up topic is F-235 only

`Lamp_Warm-Up_Time.htm` is explicitly titled "(F-235 Only)" and describes an
incandescent **bulb** with a lamp-saver timeout (`Setup → General`, settable to
9999 to disable). There is also `Light_Bulb_Replacement.htm`.

That is the F-235's illuminant. The F-135 uses an **LED array** — hence
"Initial LED warm-up" in its manual, and hence the temperature-stabilised
control path (`FN_bDrvInitLampTemperatures`, TEC, `WaitForLamp_*`). Do not
apply F-235 lamp guidance to an F-135.

## Revised conclusion

The lamp is not lit by a command. It is lit as a consequence of running the
scanner's initialisation and correction sequence, which programs the thermal
setpoints, warms the LED array, then sets gain and exposure. Reproducing
`InitializeScanner` is the actual remaining task — not finding a "lamp on"
packet.

## `FN_bInit2` decoded — board bring-up only

`FN_bInit2` = `TLB.dll:fcn.1000b100`. Sequence:

```
    fcn.10008460                     open \\.\Pakon135
    PutCommand(0x10, cmd=0x85)       host clear / ack
    PutRegisterByte(0x10, 0x8F, ..)  bus/relay enable
    PutRegisterByte(0x10, 0x8F, ..)  toggle
    Sleep(100 ms)                    <-- note the delay
    fcn.10008ba0(0x28, ..)           FindPicController, focus board (absent here)
    PutRegisterByte(0x10, 0x8F, ..)  toggled around each probe (x4)
    fcn.1000afd0                     board probe sweep (0x44,0x46,0x24,0x26,...)
    fcn.10016a90                     
    fcn.1000a0c0(0x10, ..)           GetRegisterWord, readback/verify
    fcn.1001c3e0  x2                 firmware-update gate
```

This is **only the board bring-up layer**. It contains no lamp, CCD, gain or
exposure work. Most of it was already replicated by hand in this project
(host clear and the `0x8F` toggle), which is why board communication works.

The illuminant is brought up **above** this, in the corrections chain that
`InitializeScanner` runs — the four documented stages: start-up corrections,
initial LED warm-up, gain and exposure control corrections, run-time
corrections.

### The remaining task, stated precisely

Reproduce the corrections chain, not `FN_bInit2`. Entry points already
identified:

| Stage | Function |
|---|---|
| board bring-up | `FN_bInit2` `fcn.1000b100` — **done, replicated** |
| CCD init | `FN_bDrvInitCcd` `fcn.1002d5c0` |
| lamp thermal init | `FN_bDrvInitLampTemperatures` `fcn.1002d190` |
| LED warm-up | `FN_bLampWarmUp`, `FN_bLampTemperatureStable` |
| gain / offset / exposure | `fcn.100298b0`, `fcn.100299c0` (FN 117/118/119) |
| FPGA settings | `FN_bDrvPutCcdFpgaSettings` `fcn.1002c340` |
| lamp on | `FN_bDrvLampOn` `fcn.1002c5f0` |
| before scan | `FN_bBeforeScan` `fcn.1002dbd0` |
| scan | `FN_iScanStrips` `fcn.10029b80` |

This is a bounded decode of roughly eight functions with known addresses, not
an open-ended search. It is, however, real work — each one must be read for its
register writes and their value sources, as was done for `FN_bDrvLampOn`.

## `FN_bDrvInitCcd` — and why its LampOn call is not illumination

`FN_bDrvInitCcd` = `fcn.1002d5c0`. Sequence with literal values:

```
    PutRegisterWord(reg=0x87, ..)
    LampOn(log, visible=1, IR=0, 0,0,0,0, 0xFFD,          <- 4093
           duty_R=0.0, duty_G=0.0, duty_B=0.0, duty_Ir=0.0)
    LampOff (fcn.1000c4d0)
    PutRegisterByte(reg=0x89, ..)
    PutCcdFpgaSettings(0x7D0=2000, 0x3E=62, 0xFFD=4093)
    PutRegisterCcd(reg=0x82, ..)      x3      FPGA register file
    PutRegisterCcd(reg=0x82, idx=0x0A, val=0x400=1024)
    PutRegisterCcd(reg=0x84, val=0x78=120)    CCD A/D register
    PutRegisterCcd(reg=0x84, val=0x80=128)
```

The four duty cycles come from `.rdata:0x1005c1c8`, which is the double
**`0.0`** — not a sentinel, an explicit zero. (Contrast `.rdata:0x10067008` =
`-1.0`, the "not specified" sentinel used at `LampOn` entry.)

**So this LampOn call deliberately enables the lamp with zero drive.** That is
consistent with its purpose: CCD initialisation measures the **dark
reference**, for which the illuminant must be enabled but producing no light.

It is therefore *not* the call that illuminates film, and its literals must not
be reused for that purpose.

## Where the real illumination values come from

`FN_bBeforeScan` (`fcn.1002dbd0`) calls `LampOn` with duty cycles read from a
`CiConfigLight` structure at `[eax+0x90 / +0x98 / +0xa0 / +0xa8]`, plus five
integer parameters from `[eax+0x58 / +0x5c / +0x60 / +0x64 / +0x28]`.

That structure is populated by `FN_GetCalibrateInfoLight` from the scanner's
**factory colour calibration** — which the F-135 user manual confirms is "set
during the manufacturing process".

**Decoding `FN_GetCalibrateInfoLight`'s read path is the next task.** Until
those per-unit values are read, there is no legitimate source for the
illumination drive levels, and inventing them risks the LED array.

## Session summary of what is now known end to end

| Stage | State |
|---|---|
| firmware load | working, automated |
| command protocol | decoded, drives real hardware |
| board identification | verified against shipped PIC firmware |
| **motor / film transport** | **working — three speeds and reverse confirmed audibly** |
| CCD stream | 30 MB/s, characterised |
| CCD init sequence | decoded with literal values |
| lamp enable path | decoded (`0x80`/`0x81`/`0x82`, thermal setpoints `0x8B`-`0x8F`) |
| lamp drive values | **still needed** — read via `FN_GetCalibrateInfoLight` |
| colour correction | implemented, verified exact to 0.000050 |

## Duty cycles are derived, not stored — [VERIFIED-FROM-BINARY]

`fcn.1001e020` computes the four duty cycles into the light config:

```
    n = [cfg + 0x58]                       per-channel current (iCurrent_R)
    if (n >= 3)  duty = ((n - 1) * base) / n
    else         duty = base * 0.5         ; .rdata:0x1005d348 = 0.5
    [cfg + 0x90] = duty                    ; duty_R
```

and identically for `+0x5c → +0x98`, `+0x60 → +0xa0`, `+0x64 → +0xa8`
(G, B, IR). `base` is a double held in a local, loaded earlier in the function.

So the duty cycles passed to `LampOn` are **derived at run time** from:

- the four per-channel **current** integers (`iCurrent_R/_G/_B/_Ir`), and
- a **base exposure** value

Neither is a stored duty cycle. Chasing "the duty cycle values" was therefore
the wrong target — the real inputs are the currents and the base exposure, both
of which come from the calibration read further up the call chain.

### Remaining chain to decode

```
    FN_GetCalibrateInfoLight            reads factory calibration
        -> populates CiConfigLight: currents at +0x58/+0x5c/+0x60/+0x64,
           and the base exposure
    fcn.1001e020                        derives duty cycles into +0x90..+0xa8
    FN_bBeforeScan (fcn.1002dbd0)       passes both to LampOn
    FN_bDrvLampOn (fcn.1002c5f0)        writes regs 0x81, 0x82, 0x80
```

Two links are decoded (the derivation and the LampOn writes). The unresolved
link is the calibration read itself.

Note: the FN name table is **not** index-linear with FN ids — a calibration
attempt using `FN_bDrvLampOn` (id 112, table index 247) produced negative and
inconsistent predictions for other entries. Do not rely on table position to
recover FN ids; find each function by its logger call site instead.

## Duty-cycle formula fully resolved — [VERIFIED-FROM-BINARY]

Constants recovered from `.rdata`:

| RVA | Value | Role |
|---|---|---|
| `0x10065c78` | `1.0` | base, loaded once per channel |
| `0x1005d348` | `0.5` | multiplier for the `n < 3` branch |
| `0x1005c3b8` | `4294967296.0` | 2^32 — the standard `fild` signed→unsigned fixup, **not** a tuning constant |
| `0x1005c1c8` | `0.0` | InitCcd's explicit zero duty (dark reference) |
| `0x10067008` | `-1.0` | `LampOn` "not specified" sentinel |

With `base = 1.0` the derivation in `fcn.1001e020` reduces to:

```
    duty_channel =  (n - 1) / n      if n >= 3
                    0.5              if n < 3
```

where `n` is the per-channel current, read as an **unsigned** integer.

So the duty-cycle computation is completely solved. Given the four currents,
the four duty cycles follow deterministically.

## The single remaining unknown

**The four per-channel current values** (`iCurrent_R/_G/_B/_Ir`), which are
per-unit factory calibration. Everything else in the lamp chain is now decoded:

| Link | State |
|---|---|
| register writes `0x80`/`0x81`/`0x82` | decoded |
| thermal setpoints `0x8B`–`0x8F`, `0xD0`/`0xD1` | decoded (values still from config) |
| duty-cycle derivation | **fully solved** — `(n-1)/n` |
| CCD init literals | decoded (FPGA 2000/62/4093, A/D 120→128, idx 0x0A = 1024) |
| orchestrator `fcn.10020dc0` | identified; calls FpgaSettings, LampOff, gain setters, LampOn |
| **per-channel currents** | **UNKNOWN — the last link** |

Route to the currents: `FN_GetCalibrateInfoLight`, reached from
`fcn.10021590 → fcn.10020dc0`. It is a read, so obtaining them is safe once the
path is decoded.

Context from the SDK release notes: "Reduce IR light level from 60,000 to
40,000 to prevent lag issues seen with newer CCD chips" — light *levels* are
five-figure numbers. Whether the `n` in the duty formula is that same quantity
or a separate small integer is not yet established; if `n` were 40000 the duty
would be 0.999975, which seems unlikely to be the intent. Resolve this before
using any assumed value.
