# 24 — What the vendor documentation says about this exact fault

Three documents were obtained after the hardware work: the F-135 User Manual,
the F-135 Service Manual, and the FX35 Troubleshooting Guide. The last one
turned out to describe this scanner's condition precisely.

## The LEDs, decoded (User Manual p.7)

| Power LED | |
|---|---|
| Solid green | +5V is functioning |
| Off | +5V is not functioning |

| Status LED | |
|---|---|
| Solid green | Scanner Ready |
| Blinking green | Scanner is Scanning |
| **Blinking yellow** | **Scanner is unable to scan at the moment** |
| Blinking red | Scanner Error |
| Off | Scanner not Functioning |

| Film LED | |
|---|---|
| Solid green | Film is being scanned |
| Blinking green | Insert film to be scanned |
| **Blinking yellow** | **Remove film from scanner** |
| Off | No film in the scanner |

This unit reads **green / yellow / yellow**. So: the 5V rail is fine, and the
scanner reports itself *not ready* rather than *in error*. It is specifically
**not** "Blinking Red -- Scanner Error" and **not** "Off -- Scanner not
Functioning". That is a materially better state than it appeared.

## The fault is documented, with a fix (Troubleshooting Guide 10.1)

> **Problem:** Scanner doesn't make noise on start up
> **Cause:** Motor board not initializing
> **Solution:** 1. Reload motor board firmware  2. Replace Motor Control Board

and

> **Problem:** PSI error code 244
> **Cause:** Motor board firmware
> **Solution:** Reload motor board firmware

That is this scanner exactly: the motor board does not initialise, the motor
makes no noise, and the documented remedy is to reload its firmware. This is a
known field condition with a standard fix, not an exotic failure.

The same table treats every board the same way -- corrupt lamp board firmware,
corrupt DX firmware, corrupt CCD firmware -- each with "reload X firmware" as
the first remedy. Reloading PIC firmware in the field was routine.

## The service tools, and we have them

The guide names tools that are present in the install tree:

| tool | location | purpose |
|------|----------|---------|
| **PTS.exe** | `program files/Pakon/PTS/` | the service tool. Firmware tab with per-board load, and an Advanced tab that erases the EEPROM |
| `FirmwareLoader.exe` | `Config/Firmware/` | loads PIC firmware |
| Calibration Wizard | in PSI | reloads the "double EPROM", writes calibration |
| MFC Test | -- | changes the boot EPROM version |
| Scanner Cure | -- | for "Hardware fault 200" |

`PTS.exe` carries exactly the UI this repair needs:

```
FirmwareLoad  FirmwareStore  FirmwareAction
m_tbMotorBoard  m_cbMotorBoardChange
m_lblFirmwareCurrentVersion  m_lblFirmwareNewVersion
m_lblFirmwareEEProm  m_lblFirmwareCCDBoard  m_lblFirmwareLampBoard
EEPromErase  EEPromLoad  AdvancedAction
```

## What the Service Manual does NOT contain

No firmware recovery procedure, no ICSP header, no jumper, no service mode. It
is a field-service manual: diagnose to board level, then fit
**Motherboard #125040**. Its troubleshooting section amounts to reading the
error logs and contacting Pakon Technical Support.

So the documented recovery path runs entirely through the Windows service
tools, not through anything on the board itself.

## A concern the Service Manual raises

> "The motherboard has an EEPROM chip built into it to store calibration
> information. The Calibration Wizard program writes all calibration data to
> this EEPROM chip."
> "All calibration settings are stored in the EEPROM of the scanner, on the
> scanner main board."

The blind sweep early in this project wrote to I2C addresses `0xa2`-`0xa5`,
which are EEPROMs. One is the FX2 boot EEPROM, now repaired. **The other may be
this calibration EEPROM.** If per-unit calibration was corrupted -- motor
speeds per resolution and film type, colour calibration -- that data exists in
no file here and would need the Calibration Wizard to regenerate.

Unverified, and separate from the current fault, but it should not be
discovered later by surprise.

## Consequence for this port

The bundle at `~/pakon-windows-repair/` now contains the driver, both loaders,
PTS, the full COM SERVER tree and a README describing the fault and the fix.
On an Intel Mac via Boot Camp or a VM with USB passthrough, PTS's Firmware tab
is the vendor's own answer to the exact problem this scanner has.
