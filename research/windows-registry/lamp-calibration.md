# Lamp calibration recovered from the VM disk image

Extracted offline from `PakonScanXP-F135.pvm` — the VM was never booted (its
Parallels licence has expired). Source: the `HKLM\SOFTWARE` hive carved from
the virtual disk. Full dump in `pakon_registry_full.txt`.

All 18 calibration keys live under:

```
HKLM\SOFTWARE\Pakon\TLB\Scan\DpiBase{4,8,16}_35\{BnW,BnWIr,BnW_C41,BnW_C41Ir,ColNeg,ColNegIr}
```

**Read `NOTES.md` before using any of these numbers.** They are real calibrated
values, but the evidence says they belong to scanner serial **16275**, which may
not be this unit.

## Per-key values

Rows where R=G=B=Ir=1 are uncalibrated placeholders, not measurements.

### `DpiBase16_35\BnW`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `63500` |
| `DetectFilm_G` | `61500` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase16_35\BnWIr`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `63500` |
| `DetectFilm_G` | `61500` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase16_35\BnW_C41`

last written **2025-07-28 02:50:07**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `-19` |
| `Offset_G` | `-26` |
| `Offset_B` | `-20` |
| `Current_R` | `3` |
| `Current_G` | `7` |
| `Current_B` | `3` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.853484` |
| `DutyCycle_G` | `0.897672` |
| `DutyCycle_B` | `0.617586` |
| `DutyCycle_Ir` | `0.500000` |
| `DutyCycleOpenGate_R` | `0.677946` |
| `DutyCycleOpenGate_G` | `0.504798` |
| `DutyCycleOpenGate_B` | `0.347294` |
| `DutyCycleOpenGate_Ir` | `0.415882` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `1753667580` |

### `DpiBase16_35\BnW_C41Ir`

last written **2025-07-23 04:28:32**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `-19` |
| `Offset_G` | `-26` |
| `Offset_B` | `-20` |
| `Current_R` | `5` |
| `Current_G` | `13` |
| `Current_B` | `4` |
| `Current_Ir` | `5` |
| `DutyCycle_R` | `0.820907` |
| `DutyCycle_G` | `0.970009` |
| `DutyCycle_B` | `0.773802` |
| `DutyCycle_Ir` | `0.866253` |
| `DutyCycleOpenGate_R` | `0.652069` |
| `DutyCycleOpenGate_G` | `0.545476` |
| `DutyCycleOpenGate_B` | `0.435141` |
| `DutyCycleOpenGate_Ir` | `0.720518` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `1753243550` |

### `DpiBase16_35\ColNeg`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase16_35\ColNegIr`

last written **2025-07-23 04:23:10**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `-18` |
| `Offset_G` | `-26` |
| `Offset_B` | `-20` |
| `Current_R` | `5` |
| `Current_G` | `20` |
| `Current_B` | `11` |
| `Current_Ir` | `4` |
| `DutyCycle_R` | `0.917161` |
| `DutyCycle_G` | `0.955468` |
| `DutyCycle_B` | `0.865802` |
| `DutyCycle_Ir` | `0.887000` |
| `DutyCycleOpenGate_R` | `0.658333` |
| `DutyCycleOpenGate_G` | `0.380378` |
| `DutyCycleOpenGate_B` | `0.166885` |
| `DutyCycleOpenGate_Ir` | `0.887000` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `1668114895` |

### `DpiBase4_35\BnW`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `63500` |
| `DetectFilm_G` | `61500` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase4_35\BnWIr`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `63500` |
| `DetectFilm_G` | `61500` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase4_35\BnW_C41`

last written **2025-07-23 04:23:48**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `-17` |
| `Offset_G` | `-25` |
| `Offset_B` | `-19` |
| `Current_R` | `3` |
| `Current_G` | `7` |
| `Current_B` | `3` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.924671` |
| `DutyCycle_G` | `0.980369` |
| `DutyCycle_B` | `0.684175` |
| `DutyCycle_Ir` | `0.500000` |
| `DutyCycleOpenGate_R` | `0.734492` |
| `DutyCycleOpenGate_G` | `0.551302` |
| `DutyCycleOpenGate_B` | `0.384740` |
| `DutyCycleOpenGate_Ir` | `0.415882` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `1753244628` |

### `DpiBase4_35\BnW_C41Ir`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase4_35\ColNeg`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase4_35\ColNegIr`

last written **2025-07-23 04:23:10**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `-17` |
| `Offset_G` | `-25` |
| `Offset_B` | `-19` |
| `Current_R` | `5` |
| `Current_G` | `20` |
| `Current_B` | `11` |
| `Current_Ir` | `4` |
| `DutyCycle_R` | `0.916904` |
| `DutyCycle_G` | `0.951920` |
| `DutyCycle_B` | `0.862093` |
| `DutyCycle_Ir` | `0.881640` |
| `DutyCycleOpenGate_R` | `0.658148` |
| `DutyCycleOpenGate_G` | `0.378966` |
| `DutyCycleOpenGate_B` | `0.166171` |
| `DutyCycleOpenGate_Ir` | `0.881640` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `1668115286` |

### `DpiBase8_35\BnW`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `63500` |
| `DetectFilm_G` | `61500` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase8_35\BnWIr`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `63500` |
| `DetectFilm_G` | `61500` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase8_35\BnW_C41`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase8_35\BnW_C41Ir`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `0` |
| `Offset_G` | `0` |
| `Offset_B` | `0` |
| `Current_R` | `1` |
| `Current_G` | `1` |
| `Current_B` | `1` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.000000` |
| `DutyCycle_G` | `0.000000` |
| `DutyCycle_B` | `0.000000` |
| `DutyCycle_Ir` | `0.000000` |
| `DutyCycleOpenGate_R` | `0.000000` |
| `DutyCycleOpenGate_G` | `0.000000` |
| `DutyCycleOpenGate_B` | `0.000000` |
| `DutyCycleOpenGate_Ir` | `0.000000` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

### `DpiBase8_35\ColNeg`

last written **2022-11-10 21:11:25**

| value | data |
|---|---|
| `Gain_R` | `15` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `-19` |
| `Offset_G` | `-26` |
| `Offset_B` | `-20` |
| `Current_R` | `4` |
| `Current_G` | `18` |
| `Current_B` | `10` |
| `Current_Ir` | `1` |
| `DutyCycle_R` | `0.996500` |
| `DutyCycle_G` | `0.949083` |
| `DutyCycle_B` | `0.836299` |
| `DutyCycle_Ir` | `0.500000` |
| `DutyCycleOpenGate_R` | `0.715282` |
| `DutyCycleOpenGate_G` | `0.377837` |
| `DutyCycleOpenGate_B` | `0.161199` |
| `DutyCycleOpenGate_Ir` | `0.500000` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `1668114685` |

### `DpiBase8_35\ColNegIr`

last written **2022-11-10 21:13:56**

| value | data |
|---|---|
| `Gain_R` | `13` |
| `Gain_G` | `13` |
| `Gain_B` | `13` |
| `Offset_R` | `-18` |
| `Offset_G` | `-26` |
| `Offset_B` | `-20` |
| `Current_R` | `6` |
| `Current_G` | `23` |
| `Current_B` | `14` |
| `Current_Ir` | `5` |
| `DutyCycle_R` | `0.906337` |
| `DutyCycle_G` | `0.978982` |
| `DutyCycle_B` | `0.809069` |
| `DutyCycle_Ir` | `0.845659` |
| `DutyCycleOpenGate_R` | `0.650564` |
| `DutyCycleOpenGate_G` | `0.389740` |
| `DutyCycleOpenGate_B` | `0.155950` |
| `DutyCycleOpenGate_Ir` | `0.845659` |
| `DetectWhite_G` | `61000` |
| `DetectFilm_G` | `54000` |
| `SpliceDarkness` | `237` |
| `Max_Ir` | `0` |
| `FullLightCorrections` | `0` |

