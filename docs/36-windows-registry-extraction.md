# Brief for the agent on the Windows machine

**Goal: recover this scanner's lamp calibration from the Windows registry.**

Everything here is **read-only** on the Windows side — registry *exports* and
file copies. Nothing is written to the registry, nothing is installed, and the
scanner does not need to be connected or powered.

## Why this is needed

The Pakon F-135's LED drive values are not stored on the scanner. Verified from
TLB.dll: `FN_bReadEEPromToRegistry` reads only motor and offset fields from the
scanner EEPROM, and *"no LED current, no LED duty cycle, no lamp temperature is
read from the scanner"* (`docs/15-calibration-read.md` §1e). They live in
`CiConfigLight`, persisted to the **Windows registry** by `CiConfigLight::Save`.

So this machine's registry is the only place this unit's calibrated values
exist. Without them the lamp cannot be lit safely — guessed LED currents or TEC
setpoints risk unrecoverable damage to the illuminant (`docs/14-lamp-decoded.md`).

## What to find

These value names were recovered from TLB.dll's string table and are the
targets. They map onto `FN_bDrvLampOn`'s four level arguments and four duty
doubles:

```
Current_R   Current_G   Current_B   Current_Ir      <- LED drive currents
Duty_R      Duty_G      Duty_B      Duty_Ir         <- LED duty cycles
TempSetpoint   TempLB   TempMB                      <- TEC / lamp temperature
```

Also wanted, because our scanner EEPROM dump is missing them (it is one 256-byte
page of a larger device, and the section the driver reads is 398 B):

```
Offset   MotorSpeed   MotorAdjust   MotorAdjustDrag   MotorAdjust_Ir
MotorAdjustDrag_Ir
```

Related config classes seen in the binary, all worth capturing if present:
`CiConfigLight`, `CiConfigDpi`, `CiConfigMain`, `CiConfigScan`,
`CiConfigColorKodak`, `CiConfigFixedPatternCorrection`, `CiConfigMemory`,
`CiConfigTest`.

## Steps

### 1. Locate the key — search, don't assume the path

The exact path is not known. `Current_R` is distinctive enough to find it.
In an **Administrator** command prompt:

```cmd
reg query HKLM\SOFTWARE /f Current_R /s /v > %USERPROFILE%\Desktop\find_hklm.txt 2>&1
reg query HKCU\SOFTWARE /f Current_R /s /v > %USERPROFILE%\Desktop\find_hkcu.txt 2>&1
```

On 64-bit Windows the Pakon software is 32-bit, so **also** check the
redirected hive explicitly:

```cmd
reg query HKLM\SOFTWARE\WOW6432Node /f Current_R /s /v > %USERPROFILE%\Desktop\find_wow.txt 2>&1
```

If those come back empty, widen the search — try `TempSetpoint`, then `Duty_R`,
then look for the vendor roots directly:

```cmd
reg query HKLM\SOFTWARE\Pakon /s > %USERPROFILE%\Desktop\pakon_tree.txt 2>&1
reg query HKLM\SOFTWARE\Kodak /s > %USERPROFILE%\Desktop\kodak_tree.txt 2>&1
reg query HKLM\SOFTWARE\WOW6432Node\Pakon /s >> %USERPROFILE%\Desktop\pakon_tree.txt 2>&1
reg query HKLM\SOFTWARE\WOW6432Node\Kodak /s >> %USERPROFILE%\Desktop\kodak_tree.txt 2>&1
```

**Report what you found even if it is nothing.** A confirmed absence is a real
result — it tells us the software was never run on this machine, and we stop
looking here.

### 2. Export the whole containing tree

Once found, export the vendor root — the whole tree, not just the one key, since
the surrounding values (DPI, scan, colour, motor) matter too. Substitute the
path you actually found:

```cmd
reg export "HKLM\SOFTWARE\Pakon" %USERPROFILE%\Desktop\pakon_hklm.reg /y
reg export "HKLM\SOFTWARE\Kodak" %USERPROFILE%\Desktop\kodak_hklm.reg /y
reg export "HKLM\SOFTWARE\WOW6432Node\Pakon" %USERPROFILE%\Desktop\pakon_wow.reg /y
reg export "HKCU\SOFTWARE\Pakon" %USERPROFILE%\Desktop\pakon_hkcu.reg /y
```

Any of these that error with "unable to find the specified registry key" simply
did not exist — that is fine, skip it and say so.

### 3. Grab the lamp log and any calibration files

`PakonLampLog.txt` records `TempMB` / `TempLB` over time and would independently
bound the temperature setpoints:

```cmd
dir /s /b C:\PakonLampLog.txt C:\*LampLog*.txt 2>nul
dir /s /b "C:\Program Files\Pakon" 2>nul > %USERPROFILE%\Desktop\pakon_files.txt
dir /s /b "C:\Program Files (x86)\Pakon" 2>nul >> %USERPROFILE%\Desktop\pakon_files.txt
```

Copy any `*.ini`, `*.cal`, `*LampLog*`, or `Config\` contents you find under the
Pakon install directory.

### 4. Commit and push

Put everything under `vendor/windows-registry/` in the repo on that machine:

```
vendor/windows-registry/
    pakon_hklm.reg          (and whichever others exported)
    find_hklm.txt           the search output, even if empty
    pakon_files.txt
    PakonLampLog.txt        if it exists
    NOTES.md                see below
```

Write a short `NOTES.md` recording, plainly:

* which registry paths existed and which did not;
* whether `Current_R` was found, and under exactly which key;
* whether the Pakon software is actually installed on this machine, and its
  version if visible;
* whether this machine was ever connected to the scanner, if you can tell.

Then commit and push:

```cmd
git add vendor/windows-registry
git commit -m "Windows registry export: Pakon lamp calibration search"
git push
```

## Important

* **Do not write to the registry.** `reg export` and `reg query` only. Never
  `reg add`, `reg import` or `reg delete`.
* **Do not install or run the Pakon software** to "make the keys appear". A
  fresh install would write *default* values, and defaults are exactly what we
  must not have — we need the values calibrated against this physical unit. If
  the keys are absent, that is the answer, and it is a useful one.
* If the values are found, **do not edit or round them.** Export verbatim.
