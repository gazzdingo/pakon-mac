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
