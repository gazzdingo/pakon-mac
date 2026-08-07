# 38 — Lamp temperature: there is no per-unit calibration, and that is fine

Follows `docs/37-calibration-recovered.md`. Answers "we recovered the LED
currents — where is the matching temperature calibration?"

**Headline: there isn't one, by design.** The lamp's thermal loop runs on the
light board itself. The host has only *optional overrides* for the fault and
warning bands, they live in a diagnostics key, and on this install they were
never set and the override switch is **off**.

## What was searched

The whole 11.8 GB virtual disk, not just the Pakon subtree — registry hives and
binaries alike.

| string | occurrences on the entire disk |
|---|---|
| `LampTempWorking` | **0** |
| `LampTempWarningLow` / `WarningHigh` | **0** |
| `LampTempFaultLow` / `FaultHigh` | **0** |
| `MotherBoardTemp*` | **0** |
| `TempSetpoint`, `TempLB`, `TempMB` | 4, all inside binary string tables |
| `UseTemperatureSetpoints` | 1 — a registry value, `= 0` |
| `WriteLightStabilityLog` | 1 — a registry value, `= 0` |
| `WaitForLamp_R/_G/_B/_Ir` | 1 each — registry values, `"5.000000"` |

## `TempSetpoint` / `TempLB` / `TempMB` are log columns, not registry values

This is the trap that made them look recoverable. `docs/36` listed them as
registry targets. They are not. Every occurrence is a tab-separated run inside a
binary's string table — a log file header row:

```
TempMB \t TempLB \t TempSetpoint \t VisOn \t IrOn \t Current_R \t Current_G ...
TECooler_I \t TECooler_DutyCycle \t VisOn \t IrOn \t Current_R ...
TempAmbient \t TempLocked \t TempVisible ...
```

These are the column headers of the light-stability log — the file
`WriteLightStabilityLog` would produce if it were enabled. They are **telemetry
field names for measurements**, never keys for stored settings. There is nothing
to recover, because nothing of that shape was ever persisted.

And `WriteLightStabilityLog = 0`, so the log was never written. That is also why
no `PakonLampLog.txt` exists anywhere on the disk.

## The real names, and where they live

`docs/15-calibration-read.md` §6a maps the temperature config object
`LC = [0x10075554] + 0x15a0` and infers its registry subkey as
`Software\Pakon\TLB\Test`.

**Correction, now verified empirically:** the key is
**`HKLM\SOFTWARE\Pakon\TLB\Scan\Test`** — note the `Scan`. It exists, and it
contains the object's fields in exactly the order §6a predicts:

```
[HKEY_LOCAL_MACHINE\SOFTWARE\Pakon\TLB\Scan\Test]      33 values, written 2022-11-10
    ...
    WriteLightStabilityLog   REG_DWORD  0          <- LC+0x8c
    WaitForLamp_R            REG_SZ     5.000000   <- LC+0x90
    WaitForLamp_G            REG_SZ     5.000000   <- LC+0x98
    WaitForLamp_B            REG_SZ     5.000000   <- LC+0xa0
    WaitForLamp_Ir           REG_SZ     5.000000   <- LC+0xa8
    WriteEEPromDebugFile     REG_DWORD  0          <- LC+0xb0
    UseTemperatureSetpoints  REG_DWORD  0          <- LC+0xb4
```

The field map is confirmed to `LC+0xb4`. Then it stops. `LampTempFaultLow`
(`+0xb8`) through `MotherBoardTempFaultHigh` (`+0xd8`) — the entire temperature
block — **are simply not present as values.** The loader reads them, finds
nothing, and the compiled-in clamps supply the range.

## Why they are under a key called `Test`

Because they are not calibration — they are service overrides. Look at what else
is in that key:

```
DrawDxLines, DxDesperation, LockSteppers, UsePpbDebugTraces, HighWaterTest,
UseTimeCriticalPriority, FPCCreateDebugFile, DxCreateDebugFiles,
WriteEEPromDebugFile, WriteLightStabilityLog, AnselOrientation, ...
```

That is an engineering/diagnostics block, and `CiConfigTest` is its class. The
temperature fields sit there because the host does not normally own the thermal
loop at all. Three independent facts from doc 15 say the same thing:

1. **Register `0x8E` — the working setpoint — is written only if
   `UseTemperatureSetpoints != 0`** (§6c). Default off, and off here. On this
   machine the host never sent a setpoint.
2. **The clamps are unconditional and narrow.** `LampTempWorking` is forced into
   `[592, 768]` = **37.0–48.0 °C** (units are 1/16 °C, §6b) no matter what the
   registry says. A per-unit calibrated value would not be clamped to a fixed
   window — an operating limit would.
3. **Stability is reported by the board, not computed by the host** (§6d).
   `FN_bLampTemperatureStable` never reads the temperature register; it polls an
   in-process flag set by the light-board monitor reading registers `0x83`
   (status) and `0x84` (temperature). The host waits; the board regulates.

So the thermal loop is closed on the light board. What the host can do is narrow
the fault/warning bands around it, for service work. Nobody did.

## What this means practically

* **Nothing is missing.** There is no per-unit temperature calibration to hunt
  for — not on the original machine, not anywhere. The LED currents in doc 37
  are the per-unit data; temperature is not per-unit.
* **The scanner demonstrably worked this way.** The July 2025 LED calibration
  runs (doc 37) happened on this exact install, with
  `UseTemperatureSetpoints = 0`. The lamp came up, stabilised, and a closed-loop
  current search completed against the CCD. Whatever the board does on its own
  was sufficient.
* **Do not send register `0x8E`** when bringing the lamp up. Leave the setpoint
  alone and let the board regulate, exactly as the vendor software did here.
  `0x8F`/`0x8C`/`0x8B`/`0x8D` (the warning/fault bands) are likewise unnecessary.
* **The one genuinely useful number recovered:** `WaitForLamp_R/_G/_B/_Ir =
  5.000000` seconds — the per-channel settling delay fed to `Sleep()` before a
  reading is trusted (doc 15 §0, correction 1). Use 5 s per channel.

## Still unknown

* The predicate that sets the stability flag `[this+0x298]` — doc 15 §6d flags
  this as unresolved, and nothing in the registry bears on it. It needs the
  monitor thread in `fcn.1000b890` decoded.
* `LampTempWorking`'s actual value for any unit. It is not in the registry, has
  no compiled-in default, and the string does not appear on this disk at all.
  Only the enforced window `[37.0 °C, 48.0 °C]` is known. Since the board
  regulates itself, this is not blocking.
