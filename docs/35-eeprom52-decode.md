# Decoding `eeprom_52.bin` for LED values — 2026-08-06

**Result: the LED values are not in this EEPROM, and cannot be. Decoding it
further will not produce them.** Two independent findings, either sufficient.

Source: `backups/eeprom-i2c/eeprom_52.bin`, 256 B, sha256 `675cf1cff78a2e0f…`,
two byte-identical first-reads from separate power cycles.

---

## 1. The binary says light calibration is not stored on the scanner

`docs/15-calibration-read.md` §1e, `[VERIFIED-FROM-BINARY]`:

> `FN_bReadEEPromToRegistry` (FN id 270) = `fcn.10016a90` … `fcn.10016610`
> writes only:
>
> ```
> [dpiObj+0x20]  Offset
> [dpiObj+0x44]  MotorSpeed(Plus)
> [dpiObj+0x48]  MotorSpeed(Plus)_Ir
> [dpiObj+0x24]  clamp(u16, 900, 1100)  MotorAdjust
> [dpiObj+0x2c]  clamp(u16, 900, 1100)  MotorAdjustDrag
> [dpiObj+0x28]  clamp(u16, 900, 1100)  MotorAdjust_Ir
> [dpiObj+0x30]  clamp(u16, 900, 1100)  MotorAdjustDrag_Ir
> ```
>
> **No LED current, no LED duty cycle, no lamp temperature is read from the
> scanner.**

The LED drive values live in `CiConfigLight` — `Current_X` at `+0x58`, `+0x5c`,
`+0x60`, `+0x64`, and the four duty doubles at `+0x90`, `+0x98`, `+0xa0`,
`+0xa8` — persisted to the **Windows registry** by `CiConfigLight::Save`
(`fcn.1000ff90`), not to the scanner. This is why `CalibrationGetLightLED` is a
host-side call.

So the premise "recover the LED values from the 0x52 EEPROM" is wrong at the
source. The EEPROM never held them.

## 2. Our dump is a fragment of the calibration area anyway

`FN_bReadEEPromToRegistry` reads **two CRC32-checked sections, 398 B and 36 B**.
398 B does not fit in a 256-byte device, so the calibration EEPROM is larger
than the page we captured.

Checked directly rather than assumed — the documented `MotorAdjust` fields are
`clamp(u16, 900, 1100)`, so at least one u16 in 900–1100 must appear if this
page held them:

```
u16 LE in 900..1100 : 0 candidates
u16 BE in 900..1100 : 0 candidates
```

**Zero, both endiannesses.** So this page does not contain the motor fields
either. `0x52` is very likely one page of a multi-page device (a 24C04/24C08
exposes further pages as `0x53`, `0x54`, …), and the rest of the calibration is
in pages we have not read.

That is a gap worth closing on its own merits — but note the one-read-per-power-
cycle rule in `backups/eeprom-i2c/README.md`: these parts return good data only
on the first transaction after power-up and degrade silently afterwards.

## 3. What the page we do have actually contains

Not guesswork — a structure test. Interpreting as IEEE-754 and counting
plausible values (`0`, or `1e-8 < |v| < 1e8`) across both endiannesses and all
four alignments:

```
LE offset 1 : 57/63 plausible      <- best by a clear margin
BE offset 0 : 54/64
others      : 27-32/64
```

Little-endian floats at byte offset 1, and the layout repeats in **three**
groups:

| Feature | Offsets | Spacing |
|---|---|---|
| large values 159.59 / 444.75 / 635.54 | `0x49`, `0x71`, `0x99` | exactly 40 B |
| `0.25` | `0x9d`, `0xc9`, `0xf5` | exactly 44 B |

Three of everything, consistent with three channels. Typical values include
`0.2892`, `0.2758`, `0.2782` (three near-identical scale factors) and clusters
of very small signed coefficients around `±1e-6`, which look like polynomial
correction terms.

**The fields are not named here on purpose.** Two spacings (40 and 44) coexist,
which means the record boundary is not yet established, and nothing in this page
matches the one documented layout we have. Naming fields from pattern-matching
alone would be exactly the kind of guess `docs/14` warns against.

## 4. Where the LED values actually are, and how to get them

In the Windows registry of a machine that has run **this** scanner, under
`CiConfigLight`. Concretely:

1. **A registry export from the owner's own previous Windows installation.**
   That is this unit's own calibrated values — the correct data, not a
   substitute. Best option by far.
2. A registry export from any working F-135 Plus, as a sanity reference for
   range and units (not as this unit's values).
3. `PakonLampLog.txt` from a working scanner (`docs/14:255`), which records
   `TempMB` / `TempLB` and would bound the temperature setpoints.

None of these need the scanner powered, and none can harm the illuminant.

## 5. What NOT to do

Do not derive LED currents or TEC setpoints from the floats above. They are
unattributed, this page demonstrably lacks the one field layout we can check,
and `docs/14` is explicit that wrong values risk unrecoverable damage to the LED
array or its thermoelectric cooler.
