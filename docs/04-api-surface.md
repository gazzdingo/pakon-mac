# 04 — TLX API Surface

Everything in this document is **[VERIFIED]** — extracted from
`PTS/Interop.TLXLib.dll`, a .NET COM-interop assembly that wraps `tlx.dll`.
Because interop assemblies preserve the full type library, this is the vendor's
own API contract, not a reconstruction. 1,139 identifiers were recovered.

Reproduce with: `tools/dump_tlx_api.py <path-to-Interop.TLXLib.dll>`

This does **not** describe the wire protocol — it describes the layer directly
above it. Its value is that it enumerates *every capability the hardware has*,
which tells you what the wire protocol must be able to express.

## COM shape

```
TLXMain  (coclass, TLXMainClass)
 ├── ITLXMain
 ├── IScanPictures, IScanPictures2
 ├── ISavePictures, ISavePictures1, ISavePictures2, ISavePictures3
 ├── ICalibrationWizard
 └── _ITLXMainEvents        ← outbound event sink
     ICallBackClient, ILongOpsCB
```

`tlx.dll` dispatches to `TLA.dll` / `TLB.dll` / `TLC.dll` — the error codes
`EC_CoCreateInstanceTLA/TLB/TLC` and `EC_FeatureNotSupportedTLA/TLB/TLC` show
these are three interchangeable back-ends, selected per model or per feature
tier.

## Lifecycle operations

```
InitializeScanner            GetInitializeWarnings      GetAndClearLastError
ScanPictures / ScanCancel    AdvanceFilm / StopFilmDrive
SaveToDisk / SaveToClientMemory / SaveCancel
ImportFromFile / ImportFromFile2
ResetFactoryDefaults         ResetStatusLeds
ForceCorrections             ForceDiagnostics
LampManualControl            AdjustMotorSpeed
ApsManualRetract             Put24mmFilmId
```

### Initialisation flags — `INITIALIZE_CONTROL_000`

```
INITIALIZE_MotorSelfTest              INITIALIZE_FirmwareUpdate
INITIALIZE_FocusBoardConnected        INITIALIZE_CSharpClient
INITIALIZE_ReportDminAsTmax           INITIALIZE_ProgressUpdatesAsPercent
```

`INITIALIZE_FirmwareUpdate` is the flag that triggers Layer-2 PIC flashing —
leave it clear.

### Scan flags — `SCAN_CONTROL_000`

```
SCAN_None                    SCAN_PreScan
SCAN_AggressiveFraming       SCAN_HasFilmDrag
SCAN_UseScratchRemoval       SCAN_UsePremiumColorPath
SCAN_Use24mmAutoLoader       SCAN_RFT_SenseSplice
SCAN_UseOrderAnalysisCallbacks
```

## Hardware capabilities implied by the API

These matter because each one must be expressible in the wire protocol.

### Optics and sensor

```
iCcdExposure_R/_G/_B                  iCcdExposureOpenGate_R/_G/_B
iGain_R/_G/_B                         iOffset_R/_G/_B
iCurrent_R/_G/_B/_Ir                  iCurrentOpenGate_Ir
dfDutyCycle_R/_G/_B/_Ir               iIrLEDStartTime / …OpenGate
iDetectFilm_G   iDetectWhite_G        iDmin_R/_G/_B
```

Per-channel exposure, gain and offset, plus a **fourth infrared channel** — the
IR channel is what drives `SCAN_UseScratchRemoval` (Kodak DICE, dust/scratch
detection). The light source is LED-based with per-channel duty cycle, and there
is a separate incandescent lamp: `CalibrationGetLightIncandescent` /
`CalibrationGetLightLED`.

### Mechanics

```
iMotorSpeed / iMotorSpeed_Ir          piMotorAdjust / piMotorAdjustDrag
iStepperCCD / iStepperLens            piStepperCCDAdjust
GetFilmGuidePosition / PutFilmGuidePosition
CalibrationPutFilmPressureRollerPosition
CalibrationPutFilterWheelPosition
```

Motor faults enumerate the movable parts: `EC_MotorFault_FilmDrive`,
`_FilmGuide`, `_FilterWheel`, `_CCD_Stepper`, `_Lens_Stepper`, `_PowerFail`.
So: film transport, film guide, filter wheel, CCD stage, lens stage.

### Resolutions — `RESOLUTION_000`

```
RESOLUTION_BASE_4    RESOLUTION_BASE_8    RESOLUTION_BASE_16
```

PhotoCD "Base" multiples. Frame geometry constants exist per resolution, film
format and hi/lo-res buffer, e.g.
`FRAME_SIZES_HR_WIDTH_BASE16_35`, `FRAME_SIZES_LR_HEIGHT_BASE8_35_135`.

### Film handling

```
FILM_FORMAT_35MM / _24MM / _70MM / _MOUNTED / _INDETERMINATE / _IMPORTED
FILM_COLOR_NEGATIVE / _POSITIVE / _BnW_NORMAL / _BnW_C41 / _BnW_ANY
FILM_COLOR_LAMP_OFF / _LAMP_STANDBY / _FILTER_WHEEL_BLOCKED
STRIP_MODE_FULL_ROLL / _MULTI_STRIPS_4_FRAMES / _5_FRAMES / _6_FRAMES
```

### Scanner identity — `SCANNER_TYPE_000`

```
SCANNER_TYPE_F_135      SCANNER_TYPE_F_135_PLUS       ← your unit
SCANNER_TYPE_F_235      SCANNER_TYPE_F_235C
SCANNER_TYPE_F_335      SCANNER_TYPE_F_335C
SCANNER_TYPE_UNKNOWN
```

Confirming [`01-usb-layer.md`](01-usb-layer.md): the Plus is distinguished
**after** initialisation, in software, not by USB ID.

Hardware version enum: `SCANNER_VERSION_HW_PRODUCTION`, `…_BRIDGE`,
`…_FLATBELT`, `…_RFT_SPLICE_235/_335`, plus Alpha/Beta/Charlie/Pre-Production.

Readable identity fields: `piScannerSerialNumber`, `piScannerType`,
`piScannerVersionHw`, `pbstrRomVersion`, `pbstrScannerModel`, `pbstrTLXVersion`.

> **Reading these is the ideal first protocol milestone** — pure query, no
> mechanism moves, and the answer is self-evidently right or wrong.

## Calibration

```
CalibrationBegin / CalibrationEnd / CalibrationAcquire / CalibrationChange
CalibrationEnable / CalibrationAdvanceFilm
CalibrationFocus / CalibrationFocusResults
CalibrationGetDpi / CalibrationPutDpi
CalibrationGetColorMatrix3By4  / CalibrationPutColorMatrix3By4
CalibrationGetColorMatrix3By10 / CalibrationPutColorMatrix3By10
CalibrationGetLightIncandescent / CalibrationPutLightIncandescent
CalibrationGetLightLED / CalibrationPutLightLED
CalibrationPutEEProm / CalibrationPutIdentification
CalibrationStepperTest / CalibrationStepperTestResults
CalibrationMofReader
FilmTrackTest / FilmTrackTestResults
```

The colour matrices are exposed as flat float fields
`fMatrixValue0_0 … fMatrixValue2_9` — a 3×4 and a 3×10 matrix. The 3×10 form is
a polynomial colour correction.

`CalibrationPutEEProm` plus `EC_EEPromAddress` / `EC_EEPromLength` /
`EC_EEPromCorrupted` / `EC_EEPromWarningBlank` / `EC_EEPromWarningCheckSumBad`
confirms **per-unit calibration lives in an EEPROM inside the scanner, readable
and writable over the protocol.** Recovering that data is essential for
good image quality — it is unique to your physical unit and exists nowhere else.

> ⚠️ `CalibrationPut*` and `ResetFactoryDefaults` write persistent per-unit
> calibration. A bug there is not recoverable from a file. Read paths only,
> until there is a verified backup of the EEPROM contents.

## Output formats

```
iFILE_FORMAT_RAW    ← the target for a first implementation
iFILE_FORMAT_TIF    iFILE_FORMAT_BMP    iFILE_FORMAT_JPG
iFILE_FORMAT_JPG_2000    iFILE_FORMAT_EXIF    iFILE_FORMAT_ROLL
iFILE_FORMAT_SAVE_TO_MEMORY_PLANAR_16   ← 16-bit planar, the useful one
iFILE_FORMAT_SAVE_TO_MEMORY_PLANAR_8
iFILE_FORMAT_SAVE_TO_MEMORY_DIB_8
```

`SAVE_TO_MEMORY_PLANAR_16` confirms the pipeline is **16-bit planar RGB**
internally. That is the natural output target for a macOS implementation.

## Warnings worth surfacing to a user

```
SCANW_DX_GOOD / _BAD                        SCANW_FRAMING_GOOD/_FAIR/_BAD
SCANW_MOTOR_SPEED_GOOD/_FAIR/_BAD           SCANW_LIGHT_DIM
SCANW_MOTOR_SPEED_{HALF,ONE}_PERCENT_{FAST,SLOW}
SCANW_MAX_FILM_LENGTH_EXCEEDED              SCANW_FRAMING_AT_BEGINNING/_END
SCANW_MOF_FAILED_MAGNETICS / _PERFORATIONS
FRAMING_RISK_VERY_LOW … _VERY_HIGH
```

The motor-speed warnings quantify transport error to half a percent — this
scanner self-measures its own film speed, which is how it corrects geometric
distortion. Worth reproducing.

## Built-in self test

`EC_BistPicl*` / `EC_BistPicm*` enumerate what the scanner can test itself:

```
PICL: MotherBdFpgaCommFail  MotherBdTempSensorFail  LightBdTempSensorFail
      TeCoolerFail  CurrentDriversCommFail  DxEntryFail  DxExitFail
PICM: 3V/5V/6V/12V/13V/Vin rail failures, CcdCommFail, MotorFail
```

A BIST invocation would be an excellent early protocol target — it exercises the
full command path and returns structured results without moving film.
