# 00 — Architecture Overview

## The device

The Pakon F-135 / F-235 / F-335 are roller-transport 35mm/24mm film scanners.
Internally they are a small distributed system: a USB bridge chip talks to a set
of PIC microcontrollers that run the lamp, motors, film transport, CCD and DX
code reader. The host does not talk to those PICs directly over USB — it
addresses them by ID through a packet protocol that the USB bridge relays.

```
                                     ┌──────────────────────────────────────┐
                                     │            SCANNER                   │
  ┌──────────┐                       │                                      │
  │   HOST   │  USB 2.0              │  ┌───────────┐    ┌───────────────┐  │
  │   (Mac)  │◄─────────────────────►│  │  EZ-USB   │◄──►│ PICL  (light) │  │
  │          │   EP1 OUT  commands   │  │   FX2     │    │ PICM  (motor) │  │
  │          │   EP1 IN   responses  │  │  bridge   │    │ DX    (codes) │  │
  │          │   EP6 IN   image data │  │  (8051)   │    │ CCD board     │  │
  └──────────┘                       │  └───────────┘    └───────────────┘  │
                                     └──────────────────────────────────────┘
```

The EZ-USB bridge has **no firmware of its own in flash on some units** — it
enumerates as a bare Cypress chip, the host downloads 8051 code into its RAM,
and it re-enumerates as a Pakon device. See [`02-firmware.md`](02-firmware.md).

## The Windows software stack

```
   PSI.exe / PTS.exe / IQueue III.exe / TLXClientDemo.exe     ← applications
                            │  COM
                            ▼
                        tlx.dll  (TLXMain COM server)          ← API + orchestration
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
             TLA.dll     TLB.dll     TLC.dll                   ← imaging / per-model
                            │
                            │  DeviceIoControl(0x222090)       ← [EXTERNAL]
                            ▼
       ╔═══════════════════════════════════════════╗
       ║  F135usb2.sys / F235usb2.sys / FX35usb2.sys ║           ← kernel: bulk pipes
       ║  F235Lib.sys      (generic library driver)  ║
       ║  F235Ldr.sys      (firmware loader)         ║
       ╚═══════════════════════════════════════════╝
                            │  USB
                            ▼
                        scanner
```

### What each kernel component actually does — [VERIFIED]

| File | Size | Role |
|---|---|---|
| `F235Ldr.sys` | 16 KB | Firmware loader. Anchor Chips "ezloader", modified to read Intel HEX from disk rather than embedding it. **[EXTERNAL]** |
| `F235Lib.sys` | 16 KB | Generic WDM library driver. Derived from the sample code in Walter Oney's *Programming the Microsoft Windows Driver Model*. **[EXTERNAL]** |
| `F135usb2.sys` | 12.9 KB | Per-model device driver. Its entire string table is device-configuration logging. |
| `F235usb2.sys` | 12.9 KB | Same, F-235. |
| `FX35usb2.sys` | 12.9 KB | Same, F-235/F-335 dual. |

A 12.9 KB driver whose only strings are:

```
F235usb2 - StartDevice: Configuring device from %ws
F235usb2 - StartDevice: Product is %ws
F235usb2 - StartDevice: Serial number is %ws
F235usb2 - StartDevice: Selecting configuration named %ws
F235usb2 - StartDevice: Selecting interface named %ws
```

…is doing nothing but selecting a configuration and exposing pipes. **This is
the single most important finding in this project**: there is no scanner
intelligence in kernel space to port.

## Porting strategy for macOS

| Windows layer | macOS replacement | Difficulty |
|---|---|---|
| `F235Ldr.sys` firmware download | libusb control transfers, vendor request `0xA0` | **Low** — standard, well-documented EZ-USB procedure |
| `F235Lib.sys` + `F*usb2.sys` bulk pipes | libusb bulk transfers on EP1 OUT / EP1 IN / EP6 IN | **Low** — no kext, no DriverKit, no code signing |
| `tlx.dll` packet protocol | New implementation | **High** — the actual reverse engineering work |
| `TLA/TLB/TLC.dll` imaging pipeline | New implementation | **Medium** — signal processing, can be written fresh rather than reproduced |

### Why no kernel extension is needed

macOS will not claim these devices with a class driver — they present a
vendor-specific interface with no matching Apple driver. A userspace process can
open them directly through IOKit/libusb without unloading anything and without
the kext-signing and Reduced Security dance that a DriverKit port would require.

This is the key reason a native port is realistic in 2026 rather than a
Windows-VM-with-USB-passthrough workaround.

### The imaging pipeline is a rewrite, not a port

`TLA/TLB/TLC.dll` implement dark-point/white-point correction, the CCD colour
matrix, negative inversion, scene balance, scratch removal (DICE), and framing.
Reproducing them bit-exactly is neither necessary nor desirable — the scanner
delivers linear CCD data, and a modern pipeline can do better. What *is* needed
from the vendor side is the **calibration data and correction coefficients**,
which are recoverable:

- per-unit values live in the scanner's EEPROM (readable via the protocol —
  see `CalibrationPutEEProm`, `EC_EEPromAddress` in
  [`04-api-surface.md`](04-api-surface.md))
- the colour profiles ship as data files, not code, in
  `F-X35 COM SERVER/Config/ColorCorrection/` — [VERIFIED]

A reasonable target is **raw linear output** (DNG or 16-bit planar TIFF), leaving
inversion and colour to existing tools like Negative Lab Pro or `darktable`.
That sidesteps the hardest and least valuable part of the port.

## Recommended implementation order

1. **Enumerate and load firmware** — get the device to re-enumerate as
   `0F05:F135`. Proves the USB layer end to end.
2. **Echo a command packet** — smallest possible round trip on EP1, confirming
   the framing and checksum.
3. **Read scanner identity** — serial number, model, firmware versions. Proves
   the response parsing.
4. **Lamp on / motor move** — proves command dispatch to the PICs.
5. **Acquire a raw scan line** on EP6 — proves the streaming path.
6. **Full strip scan → raw file.**
7. Imaging pipeline.

Step 1 is achievable with the information already documented here. Steps 2–3
are the point at which a USB capture from working Windows software becomes the
difference between days and months.
