# Registry extraction — results and what they mean

Done on **2026-08-06**, on the Mac, offline. Nothing was run inside the VM,
nothing was written to any registry, and the VM was never booted — its Parallels
licence has expired. The `HKLM\SOFTWARE` hive was carved directly out of the
virtual disk.

## Verdict

**The calibration is present, it is real, and this unit's own values are here —
alongside a different scanner's values, which must not be confused with them.**

Neither of the two outcomes the brief anticipated ("absent" / "factory
defaults") is what happened. The hive contains *three* populations, and telling
them apart is the whole result.

## The VM is a community image, but the scanner really was attached to it

The Windows install is not an image of our original machine:

```
RegisteredOwner         Pakon F135
RegisteredOrganization  Pakon F135 on Facebook
InstallDate             2016-06-23 10:46:04 UTC
ProductName             Microsoft Windows XP, SP3, build 2600
```

It is a prebuilt Pakon XP image circulated in the Facebook Pakon community. It
arrived carrying its builder's scanner identity and calibration:

```
HKLM\SOFTWARE\Pakon\TLB\Scan          (last written 2022-11-10)
    ScannerType          1351      (F-135)
    ScannerVersionHw     400
    ScannerSerialNumber  16275     <- the IMAGE BUILDER's unit, not necessarily ours
```

**But USB passthrough to this VM did work, and our scanner was attached to it.**
`parallels.log` records the device `0f05:f135` "F135-USB Film Scanner"
connecting successfully — `ConnectToBus: result: 0` — in four sessions:

| attached (host local) | released | duration |
|---|---|---|
| 2025-07-23 12:04:22 | 12:44:15 | 40 min |
| 2025-07-23 13:12:24 | 14:15:40 | 63 min |
| 2025-07-27 20:22:57 | 20:42:44 | 20 min |
| 2025-07-28 10:23:24 | 11:09:42 | 46 min |

(The `-2147483647` results in the same log are redundant *manual* re-attach
attempts on an already-connected device, not failures to attach.)

## The decisive correlation

The guest clock runs **7h57m52s behind** host-local time (established from
`Windows NT\CurrentVersion` written 2025-07-22 02:57:19 guest vs first VM boot
07-22 10:55:11 host). Correcting for that, every 2025 calibration write lands
*inside* a window when the scanner was physically attached:

| key | guest write time | = host local | |
|---|---|---|---|
| `DpiBase16_35\ColNegIr` | 2025-07-23 04:23:10 | 12:21:02 | inside window 1 |
| `DpiBase4_35\ColNegIr` | 2025-07-23 04:23:10 | 12:21:02 | inside window 1 |
| `DpiBase4_35\BnW_C41` | 2025-07-23 04:23:48 | 12:21:40 | inside window 1 |
| `DpiBase16_35\BnW_C41Ir` | 2025-07-23 04:28:32 | 12:26:24 | inside window 1 |
| `DpiBase16_35\BnW_C41` | 2025-07-28 02:50:07 | 10:47:59 | inside window 4 |

Five for five. These were written by a calibration routine running against real,
connected hardware — **our** hardware.

## Trust tiers — which numbers to use

1. **USE THESE — this unit, calibrated 2025-07-23 / 07-28 with the scanner
   attached:**
   * `DpiBase16_35\ColNegIr` R=5 G=20 B=11 Ir=4
   * `DpiBase4_35\ColNegIr` R=5 G=20 B=11 Ir=4
   * `DpiBase16_35\BnW_C41Ir` R=5 G=13 B=4 Ir=5
   * `DpiBase16_35\BnW_C41` R=3 G=7 B=3 Ir=1
   * `DpiBase4_35\BnW_C41` R=3 G=7 B=3 Ir=1

2. **DO NOT USE — scanner 16275's values, inherited in the image, written
   2022-11-10 before this VM existed:**
   * `DpiBase8_35\ColNeg` R=4 G=18 B=10 Ir=1
   * `DpiBase8_35\ColNegIr` R=6 G=23 B=14 Ir=5

   These are genuine measurements, which is exactly what makes them dangerous:
   they are another unit's. Unless the physical scanner's serial reads 16275,
   driving our LEDs from these is the unrecoverable-damage case in
   `docs/14-lamp-decoded.md`.

3. **Empty placeholders** — the remaining 11 keys, `Current_*` all `1`,
   `DutyCycle_*` all `0.000000`, bulk-written 2022-11-10. No information.

Tier 1 and tier 2 disagree for `ColNegIr` (5/20/11/4 vs 6/23/14/5). That is the
two different scanners, and it is a good sanity check that the split is real —
do not average or reconcile them.

**Still worth doing:** read the serial off the physical unit. If it is 16275 the
image builder's machine *was* our machine and tier 2 becomes usable too. If it
is anything else, the tier split above stands as written.

## Also recovered

* `Offset_R/G/B` are **signed negatives** (e.g. -18, -26, -20) stored as
  `REG_DWORD`. Parse as int32 — unsigned parsing yields ~4.29e9.
* `DutyCycle_*` / `DutyCycleOpenGate_*` are `REG_SZ` **strings**
  (`"0.917161"`), not numeric types — `CiConfigLight` round-trips the doubles
  through text. These map to the four duty doubles in `FN_bDrvLampOn`.
* Motor fields absent from our EEPROM dump are all here: `MotorAdjust` 1000,
  `MotorAdjustDrag` 1008, `MotorAdjust_Ir` 1000, `MotorAdjustDrag_Ir` 1008,
  per-DPI `MotorSpeedPlus`/`_Ir` (5917/4850, 11467/7580, 25802/19335), `Offset`
  27/54/55, `StepperLens`, `StepperCCD`.
* `UseTemperatureSetpoints = 0`, and **no `TempSetpoint`, `TempLB` or `TempMB`
  value exists anywhere in the hive** — those names occur only in TLB.dll's
  string table. TEC setpoints are not registry-persisted on this install.

## Correction to the premise in `docs/36`

That brief states this is an Apple Silicon Mac and that USB passthrough for the
scanner never worked. Both are wrong for this machine: the host is an **Intel**
Core i5-7360U, and the scanner attached successfully four times. The reasoning
built on "the scanner has never touched this VM" does not hold — which is
fortunate, because it is why tier 1 exists.

## Method (reproducible)

`extract_hive.py`. The SOFTWARE hive sits at image offset `0x118bcbe00` in

```
~/Parallels/PakonScanXP-F135.pvm/PakonScanXP-F135-disk001-fixed.hdd/
    PakonScanXP-F135-disk001-fixed.hdd.0.{5fbaabe3-...}.hds
```

The `.hds` is a Parallels expanding image, but the hive region is contiguous, so
cell offsets resolve linearly: `file_offset = 0x118bcbe00 + 0x1000 + cell`. The
script walks `nk`/`vk`/`lf`/`lh`/`ri` records directly — no mount, no qemu, no
NTFS driver.

## Files

See `README.md` for the full folder index. In short:

| file | what |
|---|---|
| `pakon_registry_full.txt` | full `HKLM\SOFTWARE\Pakon` + `\Kodak` dump, .reg-ish, 122 keys |
| `pakon_registry_full.json` | same, machine-readable |
| `lamp-calibration.md` | the 18 calibration keys as tables |
| `extract_hive.py` | the extractor |
| `tools/` | the seven-step pipeline, including `07_correlate_usb_timeline.py` which produced the attach-window correlation above |
| `evidence/` | raw scan offsets, the `0f05:f135` USB log lines, the correlation output, and the wide 5 MB carve |

---

## Independent verification from the Mac side — 2026-08-06

Re-parsed `pakon_registry_full.json` without reference to the summary. The
date-based split holds exactly:

```
18 keys carry Current_R
  2025-07-23 / 07-28 :  5 keys   OURS
  2022-11-10         : 13 keys   community image (serial 16275)
                                 of which 11 are placeholders
                                 (Current_*=1, DutyCycle_*=0.000000)
```

Our five, verified:

| key | Current R/G/B/Ir | DutyCycle_R |
|---|---|---|
| `DpiBase16_35\ColNegIr` | 5 / 20 / 11 / 4 | 0.917161 |
| `DpiBase4_35\ColNegIr` | 5 / 20 / 11 / 4 | 0.916904 |
| `DpiBase16_35\BnW_C41Ir` | 5 / 13 / 4 / 5 | 0.820907 |
| `DpiBase16_35\BnW_C41` | 3 / 7 / 3 / 1 | 0.853484 |
| `DpiBase4_35\BnW_C41` | 3 / 7 / 3 / 1 | 0.924671 |

**Internal consistency is good**, which is corroboration the summary did not
claim: `ColNegIr` reads 5/20/11/4 at *both* base 4 and base 16, and `BnW_C41`
reads 3/7/3/1 at both. Same currents across DPI bases is what you would expect
from a real calibration of one illuminant.

### One correction to the summary

It states the two sets "disagree for the same film mode — ours 5/20/11/4 vs
theirs 6/23/14/5". They are **not** the same mode: ours is `ColNegIr` at
DpiBase16/DpiBase4, theirs is `ColNegIr` at **DpiBase8**. The two sets do not
overlap in any mode at all.

That does not weaken the "don't mix them" conclusion — it strengthens it. There
is no shared mode, so 16275's numbers cannot even be used to sanity-check ours,
and any fallback between them would be substituting a different unit's
illuminant for a different scan resolution.

### The finding that may unblock the lamp

```
TLB\Scan\Test  UseTemperatureSetpoints = 0        [2022-11-10]
TLA\Scan\Test  LampWarmUpSlope         = -.22     [2017-02-09]
```

and **no `TempSetpoint` / `TempLB` / `TempMB` value exists anywhere in the
hive** — those strings appear only in TLB.dll.

`docs/14-lamp-decoded.md` concluded the lamp never lit here because the
setpoint blocks `0x8B`–`0x8F` were never programmed. If the vendor software
itself runs with `UseTemperatureSetpoints = 0`, then programming them may not be
required at all, and the real gate is the LED levels and duty cycles — **which
we now have for this unit.**

**Do not act on that yet.** It is an inference from a config flag, not from
code. The check that settles it: does `FN_bDrvInitLampTemperatures`
(`fcn.1002d190`) read this flag and skip the `0x8B`–`0x8F` writes when it is 0?
That is a static question about TLB.dll, answerable offline, with no hardware
risk. Do it before any lamp attempt.

Caveat worth carrying: this flag is stamped 2022-11-10, so it belongs to the
community image's configuration rather than to our 2025 calibration session.
