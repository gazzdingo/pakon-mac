# The lamp calibration has been recovered

**Date: 2026-08-06. This supersedes the plan in `docs/36-windows-registry-extraction.md`.**

If you are the agent picking this up: read this file first, then
`research/windows-registry/NOTES.md` for the evidence, then
`research/windows-registry/lamp-calibration.md` for all 18 keys in full.

## What happened

The values were not obtained by running anything on Windows. The Parallels
licence on the Mac has expired, so the VM cannot boot at all. Instead the
`HKLM\SOFTWARE` hive was carved directly out of the VM's virtual disk file and
parsed offline. The VM was never started; no registry was written.

## The headline

**We have this scanner's own LED calibration.** It is in the registry of the
Parallels VM, and it is real — written by a calibration routine while the
scanner was physically attached over USB.

```
HKLM\SOFTWARE\Pakon\TLB\Scan\DpiBase16_35\ColNegIr     (and DpiBase4_35\ColNegIr)
    Current_R              5
    Current_G              20
    Current_B              11
    Current_Ir             4
    DutyCycle_R            "0.917161"
    DutyCycle_G            "0.955468"
    DutyCycle_B            "0.865802"
    DutyCycle_Ir           "0.887000"
    DutyCycleOpenGate_R    "0.658333"
    DutyCycleOpenGate_G    "0.380378"
    DutyCycleOpenGate_B    "0.166885"
    DutyCycleOpenGate_Ir   "0.887000"
    Gain_R/G/B             13 / 13 / 13
    Offset_R/G/B           -18 / -26 / -20
    DetectWhite_G          61000
    DetectFilm_G           54000
    SpliceDarkness         237
```

These map onto `FN_bDrvLampOn`'s four level arguments and four duty doubles
(`docs/15-calibration-read.md`).

## The trap — read this before using any number

The VM is **not** an image of our original machine. It is a prebuilt Pakon XP
image circulated in the Facebook Pakon community (`RegisteredOwner: Pakon F135`,
`RegisteredOrganization: Pakon F135 on Facebook`, installed 2016-06-23), and it
came with **another scanner's** calibration already in it —
`ScannerSerialNumber 16275`, calibrated 2022-11-10.

So the hive holds two different scanners' values side by side. They are told
apart by *when they were written*:

* **2022-11-10** — the image builder's unit (serial 16275). `DpiBase8_35\ColNeg`
  and `DpiBase8_35\ColNegIr`. **Do not use.**
* **2025-07-23 / 2025-07-28** — ours, written after this VM was created
  (2025-07-22), while our scanner was connected. **These are the ones.**
* Everything else — `Current_*` all `1`, `DutyCycle_*` all `0.000000`.
  Placeholders, no information.

The two populations disagree for the same film mode (`ColNegIr`: ours
5/20/11/4, theirs 6/23/14/5). Do not average, reconcile, or fall back from one
to the other.

**Open action:** read the serial off the physical scanner. If it happens to be
16275, the 2022 values are ours too and the picture simplifies. If it is not,
the split above stands and the 2022 values are the dangerous ones —
`docs/14-lamp-decoded.md` puts unrecoverable illuminant damage on the other side
of that mistake.

## How we know the 2025 values are ours

Not by assumption — by correlation.

`parallels.log` shows USB device `0f05:f135` ("F135-USB Film Scanner") attaching
to the VM successfully (`ConnectToBus: result: 0`) in four sessions on
2025-07-23, 07-27 and 07-28, for 20–63 minutes each.

The guest clock runs 7h57m52s behind host-local time. Correcting for that, all
five 2025-stamped calibration keys were written *inside* those attach windows —
five for five. A calibration routine cannot produce per-channel values without
hardware, and the hardware was there, connected, at exactly those moments.

## Two premises in `docs/36` were wrong

Worth knowing, because they were load-bearing for the old plan:

1. **The Mac is Intel** (Core i5-7360U), not Apple Silicon.
2. **USB passthrough to this VM worked**, for the scanner specifically, four
   times. The belief that the scanner "never attached" is what made a negative
   result seem likely; in fact it attached and calibrated.

## What is still open

* **The serial check** on the physical unit (above). Highest value, costs
  nothing.
* **TEC / temperature setpoints are not here.** `UseTemperatureSetpoints = 0`
  and no `TempSetpoint`, `TempLB` or `TempMB` value exists anywhere in the hive
  — those strings live only in TLB.dll. If the TEC needs driving, the registry
  is not the source and another route is required.
* **`PakonLampLog.txt` and the Pakon install directory** were not recovered.
  They are on the same virtual disk; extracting files (as opposed to registry
  hives) needs NTFS parsing, which was not done. `docs/36` steps 3 and 4 still
  apply if that becomes worthwhile.
* **`DpiBase8_35` has no 2025 calibration** — our unit was only calibrated at
  the 4 and 16 DPI bases, in ColNegIr / BnW_C41 / BnW_C41Ir modes. Other modes
  have placeholders only.

## Motor values, as a bonus

The fields missing from our EEPROM dump (it was one 256-byte page of a larger
device) are all present in the registry:

```
MotorAdjust 1000    MotorAdjustDrag 1008    MotorAdjust_Ir 1000
MotorAdjustDrag_Ir 1008
MotorSpeedPlus / _Ir   5917/4850 (16_35), 11467/7580 (4_35), 25802/19335 (8_35)
Offset  55 (16_35), 54 (4_35), 27 (8_35)
StepperLens 3133    StepperCCD 970
```

## Parsing gotchas

* `Offset_R/G/B` are **signed** ints stored as `REG_DWORD`. Read as int32;
  unsigned parsing gives ~4.29e9 for the negatives.
* `DutyCycle_*` and `DutyCycleOpenGate_*` are `REG_SZ` **strings**, not numbers.
  `CiConfigLight` round-trips the doubles through text.

## Where everything is

```
research/windows-registry/
    README.md                     folder index and how to reproduce
    NOTES.md                      verdict, provenance, trust tiers
    lamp-calibration.md           all 18 keys as tables
    pakon_registry_full.txt/.json 122 keys, Pakon + Kodak
    extract_hive.py               the hive walker
    tools/                        the 7-step extraction pipeline
    evidence/                     USB attach log, timeline correlation, raw carves
```

The single most useful file for checking this work is
`research/windows-registry/evidence/usb-timeline-correlation.txt` — it shows, key
by key, which scanner each set of values belongs to and why.
