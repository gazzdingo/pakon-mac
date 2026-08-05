# 30 — The Pakon Reference

The definitive reference on Kodak/Pakon scanner hardware and software, written to
support two decisions: **(a)** repairing this broken F-135 Plus, and **(b)** a
native macOS port.

Every non-obvious claim is tagged:

- **[VERIFIED]** — checked directly against local evidence (a file, a binary, a
  hardware measurement, or a primary document read in full) and cited.
- **[REPORTED]** — a source states it; not independently verified here.
- **[SPECULATION]** — reasoned inference, no direct evidence.

Local evidence is cited as `path:line` or `file @ address`. Online sources are
cited by URL. Where a fact could not be established, it is named explicitly in
§11 (Open Questions) rather than omitted — a named gap is useful; a silent one is
not.

> **Provenance note.** Much of the deep hardware/firmware/protocol material
> derives from the prior investigation captured in this repo (`docs/00`–`docs/27`,
> `docs/evidence.html`, `tools/`, `analysis/`, and 67 commits of `git log`). That
> work is itself evidence and is cited as such. The service-manual and
> troubleshooting-guide facts derive from PDFs in `~/Downloads/` read in full for
> this document.

---

## Table of contents

1. [The product family](#1-the-product-family)
2. [Host interface — USB, and the PCI-software question](#2-host-interface--usb-and-the-pci-software-question)
3. [Board-level hardware and bill of materials](#3-board-level-hardware-and-bill-of-materials)
4. [Firmware](#4-firmware)
5. [The wire protocol, byte by byte](#5-the-wire-protocol-byte-by-byte)
6. [How the data flows — end to end](#6-how-the-data-flows--end-to-end)
7. [PIC18F452 replacement feasibility](#7-pic18f452-replacement-feasibility)
8. [Community and prior art](#8-community-and-prior-art)
9. [Service documentation and fault codes](#9-service-documentation-and-fault-codes)
10. [Colour science](#10-colour-science)
11. [The macOS port — current state](#11-the-macos-port--current-state)
12. [Parts and sourcing](#12-parts-and-sourcing)
13. [OPEN QUESTIONS AND WHAT WOULD ANSWER THEM](#13-open-questions-and-what-would-answer-them)

---

## 1. The product family

Pakon Inc. (Golden Valley, Minnesota) built roller-transport film scanners for
the minilab/photofinishing market. The line was absorbed into Kodak's minilab
business and the scanners were sold under the "Kodak" brand with Pakon model
numbers. The desktop "F-series" — F-135, F-235, F-335 and the FX-35 variant — is
what survives in the used market and is what this document concerns.

### 1.1 Confirmed model characteristics (from primary local documents)

| Model | Formats | Resolutions (px) | Interface | Light source | IR/ICE | Source |
|---|---|---|---|---|---|---|
| **F-135** | 35mm colour negative only; cut strips 3–40 frames (≥4 for DX) | 4Base 1000×1500, 8Base 1500×2250 | USB 2.0 | LED | Digital ICE hardware present | F-135 Service Manual p.1–2, p.6 |
| **F-135 Plus** | as F-135 | 4Base 1000×1500, 8Base 1500×2250, **16Base 2000×3000** | USB 2.0 | LED | Digital ICE (IR channel) | F-135 Service Manual p.1 |
| **F-235 / F-235C** | 35mm + APS (24mm) + MOF magnetics | Base 4/8/16 (per API `RESOLUTION_000`) | USB 2.0 | LED + incandescent | IR channel | `04-api-surface.md`; FX35 manual |
| **F-335 / F-335C** | 35mm + APS + MOF; higher throughput tier | Base 4/8/16 | USB 2.0 | LED + incandescent | IR channel | `04-api-surface.md`; FX35 manual |
| **FX-35** | umbrella service name for the F-235/F-335 family | — | USB 2.0 | — | — | "Pakon FX35 Service Manual" |

Key verified facts:

- **The F-135 handles 35mm colour negative only.** "The F-135 is designed to
  scan 35 MM. color negative film." [VERIFIED — F-135 Service Manual p.2]. B&W
  and slide (positive) are handled by the *software* colour path, not different
  hardware (see §10); the community notes "C41 B&W works just fine" and there is
  a `FILM_COLOR_POSITIVE` mode [VERIFIED — API enum `FILM_COLOR_*`,
  `04-api-surface.md:113`].
- **The Plus difference is purely the 16Base 2000×3000 resolution mode** plus the
  IR channel exposed for scratch removal. Both base and Plus share USB ID
  `0F05:F135` and are distinguished only *after* init, in software, via
  `SCANNER_TYPE_F_135_PLUS` and by which PIC firmware set is loaded (NL/NM =
  Plus, PL/PM = base) [VERIFIED — `01-usb-layer.md:57`, `04-api-surface.md:121`].
- **The F-235/F-335 add APS (24mm) film and MOF** (Magnetics On Film — the APS
  magnetic data layer) and a `70MM` format enum exists but is almost certainly
  vestigial [VERIFIED — `FILM_FORMAT_35MM/_24MM/_70MM/_MOUNTED`,
  `04-api-surface.md:112`]. The FX35 troubleshooting guide has entire sections
  on APS jams and MOF reading [VERIFIED — FX35 manual §10.4].
- **No Pakon F-series scanner handles 120 / medium format.** The transport is a
  fixed 35mm/APS roller path; the widest format enum is 70mm and there is no
  120 handling anywhere in the API, the manuals, or the transport design. The
  film-track and light bar are sized for 35mm. [VERIFIED — no 120/220/medium
  reference in any local document; transport described as 35mm/24mm roller,
  F-135 Service Manual p.6, `00-overview.md:5`]. If medium-format scanning is a
  requirement, no Pakon meets it — full stop.

### 1.2 Sensor, optics, transport (F-135, from the service manual)

- **CCD:** trilinear (senses R, G, B on three separate pixel rows), fixed focus.
  "The CCD chip is trilinear — it senses three colors: red, green, and blue."
  [VERIFIED — F-135 Service Manual p.7]
- **A/D:** **14-bit**, on the CCD board. "the data is converted into raw digital
  data through the 14 bit A/D chip on the CCD board." [VERIFIED — F-135 Service
  Manual p.7]. Data is padded to 16-bit for transport (§6).
- **Light source:** LED array, "should outlast the life span of the scanner."
  [VERIFIED — F-135 Service Manual p.2, p.8]. There is *also* a thermo-electric
  cooler (TEC) under the LED board to hold the LEDs at a controlled temperature
  (§3).
- **Transport:** a single powered roller; film must be pushed in by hand far
  enough to reach it. Two staggered DX sensors read the DX code on both film
  edges and detect frame index; the exit-side DX sensor also acts as a
  film-present sensor. [VERIFIED — F-135 Service Manual p.6, p.10]
- **Focus:** fixed at manufacture. The lens is positioned in a focus fixture and
  the clamp is glued; "the scanner should not lose focus unless the optical path
  is manipulated." [VERIFIED — F-135 Service Manual p.8]. There are, however,
  CCD-stepper and lens-stepper motors in the API (`iStepperCCD`, `iStepperLens`)
  [VERIFIED — `04-api-surface.md:89`] — so at least the F-235/335 (and possibly
  Plus) have a motorised optical stage; the base F-135's "fixed focus" may be a
  factory-set stepper position rather than a truly static lens.
- **Physical:** 6.75″ × 8.5″ × 14.75″; external supply **15 V, 2.4 A**, centre-
  positive, 5.5mm/2.5mm barrel. [VERIFIED — F-135 Service Manual p.1]

### 1.3 Era, price, serviceability

- The F-135 Service Manual is dated **Feb 2006** (Pakon part #125307-B). The
  FX35 Service Manual is dated **Nov 2005**. So the F-235/F-335/FX-35 predate the
  F-135, which was the later, cheaper, 35mm-only consumer-facing unit.
  [VERIFIED — PDF footers]
- Community model-spec consensus adds: F-235(+) = 14-bit A/D, **halogen** lamp
  (EIKO 12V/50W GU5.3 MR16 consumable, ~1,000 h), ~800 frames/h without ICE /
  400 with; F-335 = 16-bit path, LED, whole roll in <3 min, single-pass, up to
  40-frame uncut rolls; F-135 non-Plus commonly quoted as 8-bit output.
  [REPORTED — Rangefinderforum comparison, Machine Planet writeup]
- Corporate arc: Pakon Inc. founded 1985 (Minnesota, out of Pako Corp.); Kodak
  acquired it Feb 2001; operations ceased ~2008; Kodak's Jan 2012 Chapter 11
  triggered the minilab sell-off and the **2013–2015 liquidation flood**
  ($300–$750 F-135 Plus units). Today: ~$1,200–2,700 working units; AAA Imaging
  refurbs at $1,795. Details and part sources: §8.4, §12. [VERIFIED/REPORTED —
  camera-wiki, resurrectedcamera, aaaimaging, PicClick]

### 1.4 Software required per model

- All models use Windows software: **PSI** (Pakon Scanner Interface), **PTS**
  (Pakon Test Suite / diagnostic), and the **TLX** engine (`tlx.dll` →
  `TLA/TLB/TLC.dll`). [VERIFIED — `00-overview.md:29`, install tree]
- Minimum host per the F-135 manual: Pentium III/Athlon ≥700 MHz, **Windows 2000
  or XP**, 256 MB RAM, USB 2.0, 4 GB free disk sustaining ≥30 MB/s. [VERIFIED —
  F-135 Service Manual p.1]. The 30 MB/s figure is the EP 0x86 image-stream rate
  (§6); a disk that cannot keep up produces the community-documented
  memory/overflow errors (§9).
- Why XP 32-bit specifically, the 3 GB RAM ceiling, VM error 149, and the
  community VMware/VirtualBox workarounds: **see §8 and §9**.

---

## 2. Host interface — USB, and the PCI-software question

### 2.1 The bottom line on PCI

**The owner asked specifically about the "PCI software" — whether a PCI/PCIe
interface card path exists and whether its software stack is a cleaner route to
reimplementing the scanner than the USB/FX2 stack.** The definitive
local-evidence answer, with the online investigation in §2.4:

- **Every F-series Pakon in local evidence is USB 2.0.** The F-135 rear panel has
  exactly three things: USB (type B), power barrel, power switch — no card, no
  SCSI, no FireWire. [VERIFIED — F-135 Service Manual p.3 photo]. "The F-135 film
  scanner is a stand alone USB 2.0 device." [VERIFIED — p.6]. The F-235/F-335
  drivers (`F235usb2.sys`, `FX35usb2.sys`) are USB drivers, and the firmware
  images all carry USB device descriptors [VERIFIED — `01-usb-layer.md`,
  install tree]. There is **no PCI/PCIe interface card in any local material**
  for the F-135/F-235/F-335/FX-35 desktop scanners.
- The one PCI mention in the entire F-135 manual is a *host BIOS* setting ("PCI
  Latency Timer 248", "PCI to DRAM Prefetch Disable") for the bundled PC — i.e.
  the host motherboard's PCI bus, not a scanner interface. [VERIFIED — F-135
  Service Manual p.5]
- The online question — whether *any* Pakon product ever (e.g. earlier minilab
  scanners, or the Kodak HS1800 which is related to the F-335) used a PCI
  framegrabber card — is covered in §2.4 (web research).

**Consequence for the port:** the transport we must speak is USB. There is no
PCI card to obtain, and Thunderbolt-to-PCIe is moot for these units. The more
important half of the owner's question — *is the PCI-era / integrator software
better documented and reusable?* — resolves to the **TLX SDK** question, covered
in §2.4 and §8, because TLX is the documented API layer regardless of transport.

### 2.2 The three USB identities [VERIFIED — `01-usb-layer.md`, `F235usb2.inf`]

A Pakon presents **three identities** over its life; a driver must handle all
three:

```
power on
   ├─ no boot EEPROM ─────────────► 04B4:8613 (bare Cypress FX2) or 0547:1002 (Anchor)
   │                                    │ load PknInit.hex
   ├─ boot EEPROM present ─────────► 0F05:F235 REV AAxx  (xx = 05/07/08: model tag)
   │                                    │ host downloads matching Intel HEX to 8051 RAM
   └─ re-enumerates ──────────────► 0F05:F135 REV 0002   ← the only state that can scan
```

| Unloaded VID:PID | REV | Meaning | Firmware to load |
|---|---|---|---|
| `04B4:8613` | any | Bare Cypress EZ-USB FX2, EEPROM not loaded | `PknInit.hex` |
| `0547:1002` | — | Bare Anchor EZ-USB | `PknInit.hex` |
| `0F05:F235` | `AA05` | Pakon USB board, model tag 5 | `Pakon5.hex` |
| `0F05:F235` | `AA07` | Pakon USB board, model tag 7 (**this unit**) | `Pakon7.hex` |
| `0F05:F235` | `AA08` | Pakon USB board, model tag 8 | `Pakon8.hex` |
| `4705:0211` | `0000` | Development board | `PknInit.hex` |

| Loaded VID:PID | REV | Model | Driver | Product string |
|---|---|---|---|---|
| `0F05:F135` | `0002` | **F-135 / F-135 Plus** | `F135usb2.sys` | `F135-USB Film Scanner` |
| `0F05:35F2` | `0001/0002` | F-235 | `F235usb2.sys` | `F235-USB Film Scanner` |
| `0F05:F335` | `0002` | F-235 / F-335 | `FX35usb2.sys` | `FX35-USB Film Scanner` |

**For this F-135 Plus, load `Pakon7.hex`; it re-enumerates as `0F05:F135`.**
[VERIFIED — `01-usb-layer.md:72`]

### 2.3 The USB endpoint map [VERIFIED — HEX descriptor scan, `01-usb-layer.md:79`]

Identical across all four firmware images (endpoint layout does not vary by
model):

| Endpoint | Dir | Type | Max packet (HS) | Purpose |
|---|---|---|---|---|
| `0x01` | OUT | Bulk | 512 | Command packets to scanner |
| `0x81` | IN | Bulk | 512 | Response packets from scanner |
| `0x86` | IN | Bulk | 512 | Scan image data stream (~30 MB/s) |

- The device declares a **vendor-specific interface class**, so **macOS needs no
  kext/DriverKit** — libusb can claim interface 0 of configuration 1 directly.
  [VERIFIED — `01-usb-layer.md:112`]
- The device **re-enumerates mid-session** after firmware download; the host must
  close its handle, wait 1–3 s, and reopen by the *loaded* VID/PID.
- The Windows kernel drivers contain **no scanner intelligence** — a 12.9 KB
  `.sys` whose entire string table is "selecting configuration/interface". "There
  is no scanner intelligence in kernel space to port." [VERIFIED —
  `00-overview.md:74`]. All intelligence lives in the userspace DLLs.

### 2.4 The PCI-software question, answered

The owner's real question was: **does a PCI-based software stack give a cleaner,
better-documented route to reimplementing the scanner than the USB/FX2 stack?**
Two findings settle it:

1. **There is no PCI/PCIe Pakon.** No F-series desktop Pakon used a PCI interface
   card; all are USB 2.0 (FX2). The one "PCI" mention anywhere is a host-BIOS
   setting. The Kodak **HS-1800** — sometimes guessed to be a PCI-connected
   Pakon relative — is actually a **Noritsu** scanner, unrelated. [VERIFIED —
   §2.1; community search, §8.4]. *(A dedicated deeper web sweep of pre-Kodak
   Pakon minilab hardware is still running; if it surfaces any PCI-era product it
   will be added, but the desktop F-series answer is firm.)*

   <!-- PCI_WEB_PENDING -->

2. **The better-documented route is not a different transport — it is the TLX COM
   API layer, and its documentation survives.** The vendor **F235 COM Reference
   Manual (124580-I)** and **COM Users Guide (124579-I)** PDFs, plus the original
   **TLA demo source**, are preserved online in `eatfrog/PakonClient/docs`
   [VERIFIED — §8.0]. Combined with the locally-recovered TLX type library (1,139
   identifiers, `04-api-surface.md`) and the community's low-level notes
   (`tlx-lowlevel.md`: IOCTL `0x222090`, `\\.\Pakon135`, packet examples), this
   gives a **documented API contract** describing every capability the hardware
   exposes.

**So the honest answer:** the PCI *hardware* path does not exist and is a dead
end. But the *software* the owner was reaching for — a legibly-documented layer
that explains device behaviour without byte-by-byte RE — **does exist**, in the
form of the versioned **FX35 SDK** (1.2→3.1, confirmed by the vendor's own PSI
release notes — §8.1), whose surviving documentation is the **F235 COM Reference
Manual / Users Guide** PDFs, plus the community's reverse-engineering notes.
Those document the API and the IOCTL/packet boundary; the on-wire I²C
register/command semantics (§5) still had to be recovered by disassembly, and
that work is largely done. Nothing about a PCI card would have made the wire
protocol more legible. The minilab-integration path that does exist is
**software** (the DLSQueue interface in PSI for Kodak DLS systems), again over
the same USB scanner.

---

## 3. Board-level hardware and bill of materials

> **Imagery caveat.** Board frames exist at
> `/Users/guy/www/pakon-mac/analysis/board/` but the source video is only
> **512×288**. They are adequate for *layout* (where parts sit, which header is
> where) and were used as such below, but **cannot resolve chip markings**. No
> part number below is marked VERIFIED on the basis of those frames. Parts are
> VERIFIED only where a legible photo, the firmware, a datasheet-level
> cross-check, or a service-manual parts list supports them. Everything else is
> marked UNKNOWN with a note on what photograph would settle it.

### 3.1 Board inventory and the part-number discrepancy

The F-135 is built from these assemblies [VERIFIED — F-135 Service Manual p.16
FRU list and p.33 parts list]:

| Assembly | FRU part # | Parts-list # | Role |
|---|---|---|---|
| Scanner **Motherboard** | 125040 | 125040 | Motor control, DX, USB comm, power regulation |
| **CCD Board** | 125038 | 125038 | Trilinear CCD + 14-bit A/D + optical readout |
| CCD Chip | (in 125038) | 123528 | The trilinear sensor itself |
| Lens | — | 125166 | Fixed lens; Lens Clamp 125034 |
| **LED Assembly** (light board) | 125031 | — | LED illuminator PCB |
| **Thermo-electric Cooler** | 125159 | 125159 | Peltier under the LED board |
| Film Transport | 125055 | 125055 | Roller, gate, guides |
| DX Sensor | — | 125154 | DX-code / film-present optical sensors |
| Plastic Cover | — | 125115 | — |
| CCD Cable | — | 125158 | CCD board ↔ motherboard ribbon |
| CCD Spring | — | 125035 | — |

> **Discrepancy to resolve.** The service-manual motherboard FRU is **#125040**,
> but the silkscreen on *this* unit's main board reads **#125430 REV C**
> [VERIFIED — `docs/evidence.html` §05, `26-HANDOFF.md:91`]. 125040 vs 125430 is
> a digit transposition apart. Two readings, both plausible: (a) the Plus uses a
> different board number (125430) than the base F-135 (125040); (b) 125430 is the
> bare-PCB number and 125040 the assembled-FRU number. The firmware readme maps
> `NM05yy` → "PCB #125430C" [VERIFIED — `18-main-board-recovery.md:70`], which
> ties 125430C to the Plus firmware, favouring reading (a). **[SPECULATION on
> which.]** A photo of the board's FRU sticker vs silkscreen would settle it.

### 3.2 Main / motor board (#125430 REV C) — the BOM

This is the board with the fault (the PIC's I²C is silent). It carries the FX2
USB bridge, the main PIC, the Xilinx FPGA, the motor drivers, the CCD/FPGA
register interface, and the multi-rail power supply.

**Active silicon identified with confidence:**

| Ref | Marking on package | Real part | Package | Role | Evidence |
|---|---|---|---|---|---|
| **U6** | `CY7C68013A-128AXC` | Cypress EZ-USB **FX2** (8051 + USB 2.0 PHY + GPIF/slave-FIFO) | 128-TQFP | USB bridge: host↔I²C relay, image FIFO to EP 0x86 | [VERIFIED — legible photo; `26-HANDOFF.md:94`] |
| **U11** | `125507A 2208` (**Kodak house number — relabelled**) | Microchip **PIC18F452** | 44-TQFP | Main-board MCU (**"PICM"**): motor control, CCD/FPGA register agent, power supervision, I²C slave at board addr 0x44 | [VERIFIED — firmware declares `;PIC18F452`; 39.32 MHz HSPLL timing matches; `27-icsp-procedure.md:54`] |
| **?** (U-unknown) | `XC3S150E` + speed/pkg suffix | Xilinx **Spartan-3E, 150 K gates** | likely TQFP-144 or FT256 | CCD timing/pixel pipeline (see §6.3) | [VERIFIED — package marking, `analysis/board/README.md:20`; **ref-des UNKNOWN**] |

> **Relabelled-part flag.** U11's package is marked with the Kodak house number
> **`125507A 2208`**, not "PIC18F452" or "Microchip". Anyone reading the board
> cold will not recognise it as a PIC. Its identity is established from the
> firmware (which self-declares `;PIC18F452`) and from the blink-timing
> arithmetic requiring a 9.8304 MHz × 4 HSPLL = 39.32 MHz clock, which is a
> PIC18F452 configuration. [VERIFIED — `analysis/led_decode.md`, evidence §3a]

**Active silicon inferred to exist but not yet identified on the package
(ref-des and exact part UNKNOWN — these are the photograph targets):**

| Function (must exist) | Why we know it exists | What to look for |
|---|---|---|
| **Multi-rail switching supply** generating **13 V, 12 V, 6 V, 5 V, 3 V** | BIST names `EC_BistPicm{Vin,13V,12V,6V,5V,3V}Fail` enumerate exactly these rails [VERIFIED — `04-api-surface.md:206`, `18-main-board-recovery.md:90`]. Board photos show ≥3 switching inductors marked "100 M80" + bulk electrolytics + a large transformer [VERIFIED-layout — `analysis/board/board_t14s.png`] | Buck/boost controller ICs (e.g. an SOIC-8/10 near each "100 M80" inductor); a 15 V→rails topology |
| **Stepper/DC motor driver(s)** for film drive (and, on Plus/235/335, CCD & lens steppers) | PIC controls motors; API enumerates `FilmDrive/FilmGuide/FilterWheel/CCD_Stepper/Lens_Stepper` motor faults [VERIFIED — `04-api-surface.md:95`] | Motor-driver ICs (e.g. Allegro/TI H-bridge or stepper driver in SOIC/PowerSOIC), near the motor connector |
| **CCD/FPGA↔PIC ADC supervision** (rail ADC uses the PIC's own 10-bit ADC) | Blink fault bit 1 "covers ADC channels 0-3" for rail sensing [VERIFIED — `25-root-cause.md:109`] | Resistor dividers into PIC AN0–AN3; no external ADC needed for rail sense |
| **I²C pull-ups on SCL/SDA** (directly relevant to the live fault) | The I²C bus is shared by U11 (0x44), light board (0x40), boot EEPROMs (0x51/0x52) [VERIFIED — evidence §3b]. Pull-ups **must** exist for the bus to work, and the light board + EEPROMs demonstrably ACK | **UNKNOWN: location, value, and which rail.** Two SMD resistors (typ. 2.2k–4.7k) tied to SCL and SDA, pulled to the logic rail (likely 3 V or 5 V). Likely near the FX2 (U6) which is the bus master, or near a bus junction. **This is worth photographing precisely** — if a pull-up is to a rail that is out of tolerance, or if the fault is a short on SDA/SCL near U11, that bears directly on why U11 alone is silent while the shared bus otherwise works. |

> **On the live fault and the pull-ups.** The bus is proven good — the light
> board and both EEPROMs sit on the *same two wires* and ACK perfectly, so
> neither SCL nor SDA is being held low, and the pull-ups are doing their job for
> the rest of the bus [VERIFIED — evidence §02 "The I²C bus itself is good"]. The
> fault is confined to U11's *own* connection to those wires (RC3=SCL pin 37,
> RC4=SDA pin 42) or to its MSSP peripheral, or to firmware never reaching MSSP
> init. Candidate causes remain: (1) a supply rail out of tolerance feeding a bus
> buffer on U11's segment; (2) RC3/RC4 electrically open (cracked joint/broken
> trace); (3) MSSP peripheral damage; (4) undiscovered flash corruption above
> 0x2000. [VERIFIED — `25-root-cause.md:106`, evidence §06]

**Connectors and headers on the main board:**

| Ref | Type | Pinout | Runs to / carries | Evidence |
|---|---|---|---|---|
| **JM11** | 5-pin header beside U11 (with its own crystal) | **Presumed** MCLR / VDD / VSS / PGD / PGC (standard ICSP order). **Only pin1→U11 pin18 (MCLR/VPP) is assumed; full mapping UNVERIFIED** | **PIC ICSP** (in-circuit programming of U11) | [VERIFIED it is a 5-pin header by U11; pinout UNVERIFIED — `27-icsp-procedure.md:66`] |
| **JM10** | 2×5 (10-pin) header | FPGA JTAG (TCK/TMS/TDI/TDO/…); exact pin map not decoded | **Xilinx Spartan JTAG** — **not** the PIC header | [VERIFIED it is the FPGA JTAG, `27-icsp-procedure.md:71`; pinout UNKNOWN] |
| CCD ribbon | ribbon connector (part #125158 cable) | LVDS/parallel pixel bus + power | Motherboard ↔ CCD board | [VERIFIED exists — F-135 Service Manual p.25; signal detail UNKNOWN] |
| Light-board connector | multi-pin, shares I²C (SCL/SDA) + LED power + TEC | Motherboard ↔ LED assembly | I²C bus to light board 0x40, LED drive, TEC drive | [VERIFIED shares I²C — evidence §02; pinout UNKNOWN] |
| Motor / transport connector(s) | — | Motor phases, DX sensors, film-present | Motherboard ↔ transport | [VERIFIED exists — F-135 Service Manual p.20 photo; pinout UNKNOWN] |
| Power in | barrel + switch | 15 V 2.4 A | External PSU | [VERIFIED — F-135 Service Manual p.3] |

> **U11 pin map (44-TQFP), needed for ICSP** [VERIFIED — `26-HANDOFF.md:95`,
> Microchip DS39564B]: MCLR/VPP = 18; PGC = 16; PGD = 17; VDD = 7, 28; VSS = 6,
> 29; RC3/SCL = 37; RC4/SDA = 42. Pin numbering runs CCW from the dot: 1–11 left
> edge top→bottom, 12–22 bottom L→R, 23–33 right edge bottom→top, 34–44 top edge
> R→L.

### 3.3 CCD board (#125038)

| Item | Detail | Evidence |
|---|---|---|
| CCD sensor (#123528) | Trilinear RGB line sensor; pixels-per-line UNKNOWN (see §6) | [VERIFIED trilinear — F-135 Service Manual p.7; exact part UNKNOWN] |
| A/D converter | **14-bit**, on this board | [VERIFIED — F-135 Service Manual p.7] |
| CCD power module | Local regulator with a **fuse** (F-235/335; may differ on F-135) | [REPORTED — FX35 Service Manual p.151, error 151 cause] |
| **U5 config PROM** (F-235/335 CCD board) | Atmel **AT17LV512A** (512 Kbit serial FPGA config EEPROM); manual says if it reads `AT17C512A` (5 V) replace with `AT17LV512A` (3.3 V) | [REPORTED — FX35 Service Manual p.151]. **Note:** this implies the F-235/335 CCD board has its *own* small FPGA/CPLD configured by U5. Whether the F-135 CCD board is the same is UNKNOWN — the F-135 manual mentions only the 14-bit A/D. |

The CCD board connects to the motherboard by the #125158 ribbon cable carrying
the pixel data and control; the "No Light" and "Horizontal Lines"
troubleshooting flows reference an **LVDS cable at the CCD & USB end** [VERIFIED
— FX35 Service Manual p.170 flow chart], confirming the CCD→main-board link is
**LVDS**.

### 3.4 Light board / LED assembly (#125031) + TEC (#125159)

| Item | Detail | Evidence |
|---|---|---|
| Light-board PIC ("**PICL**") | A second PIC (firmware `nl*`/`pl*`) at I²C board address **0x40** | [VERIFIED — board 0x40 answers as light board; firmware set NL/PL; `01-usb-layer.md:60`] |
| LED array | Per-channel R/G/B + **IR** LEDs, PWM-driven, with per-channel level and duty registers | [VERIFIED — registers 0x81/0x82, `pakon_commands.py:295`] |
| Incandescent lamp | Separate incandescent path (F-235/335) alongside the LEDs | [VERIFIED — `CalibrationGetLightIncandescent`, `04-api-surface.md:148`] |
| Temperature sensor(s) | Lamp temp read at register 0x84 (1/16 °C units); motherboard + light-board temp sensors both exist | [VERIFIED — reg 0x84, `pakon_commands.py:298`; BIST `MotherBdTempSensorFail`/`LightBdTempSensorFail`, `04-api-surface.md:205`] |
| **TEC (Peltier)** | Thermo-electric cooler under the LED board, driven from the light board, holds LEDs at a working setpoint in **[37.0, 48.0] °C** | [VERIFIED — TEC FRU #125159, F-135 Service Manual p.16, p.24; setpoint clamp `pakon_commands.py:568`] |
| Current drivers | LED constant-current drivers | [VERIFIED — BIST `CurrentDriversCommFail`, `04-api-surface.md:205`] |
| DX sensors (#125154) | Two staggered optical DX-code readers (entry + exit); exit doubles as film-present | [VERIFIED — F-135 Service Manual p.10; BIST `DxEntryFail`/`DxExitFail`] |

> **The two-PIC topology and the BIST split** [VERIFIED — `04-api-surface.md:203`]:
> - **PICM** (main board, addr 0x44, firmware `nm*`) self-tests: the **power
>   rails** (Vin/13V/12V/6V/5V/3V), **CcdCommFail**, **MotorFail**.
> - **PICL** (light board, addr 0x40, firmware `nl*`/`pl*`) self-tests:
>   **MotherBdFpgaCommFail**, **MotherBdTempSensorFail**, **LightBdTempSensorFail**,
>   **TeCoolerFail**, **CurrentDriversCommFail**, **DxEntryFail**, **DxExitFail**.
>
> The BIST groupings are slightly counter-intuitive (the light-board PIC reports
> the FPGA-comm and motherboard-temp results), which suggests the two PICs share
> supervision duties across a partly-merged sensor bus. The exact physical
> placement of each temp sensor and of the FPGA-comm watchdog is **UNKNOWN** and
> is a photograph/probe target.

### 3.5 Power supply

- External brick: **15 V, 2.4 A**, centre-positive. [VERIFIED — manual p.1]
- On-board, the 15 V is converted to the internal rails **13 V, 12 V, 6 V, 5 V,
  3 V** (from the BIST rail names). [VERIFIED rails exist — `04-api-surface.md:206`]
- Front-panel **Power LED = "+5V is functioning"** [VERIFIED — F-135 Service
  Manual p.13], so the 5 V rail is the one surfaced to the user.
- The specific regulator ICs generating each rail are **UNKNOWN** (photograph
  target — see §3.2). The board layout shows a switching topology (multiple
  power inductors + a transformer, likely for the higher rails / TEC drive).

---

## 4. Firmware

### 4.1 Two firmware layers

There are two entirely separate firmware layers:

1. **FX2 8051 firmware** — downloaded into the Cypress FX2's RAM at every boot
   (the "Pakon N.hex" images). This is what makes the device re-enumerate and
   relay the packet protocol.
2. **PIC firmware** — resident in each PIC's flash (the `nm*`/`nl*`/`pm*`/`pl*`
   Intel-HEX images). This runs the motors, lamp, CCD interface, DX reader.

### 4.1a The complete firmware inventory [VERIFIED — direct listing of `Config/Firmware/`]

`…/F-X35 COM SERVER/Config/Firmware/` holds **56** PIC images (note: doc
`02-firmware.md` says "58" — the recount is 56) plus `FirmwareLoader.exe`
(61,440 B) and three readmes. Board prefixes, from the vendor readmes
[VERIFIED — `16-acquisition-decoded.md:382`]:

| Prefix | Board | Count | Notes |
|---|---|---|---|
| `PL` / `NL` | Light (PICL) — base / **Plus** | 11 / 10 | Plus light images 43–77 KB |
| `PM` / `NM` | Motor (PICM) — base / **Plus** | 6 / 5 | `nm0506.HEX` = this unit, 29,977 B, 2006-08-17 |
| `LP` / `LQ` | Lamp controller (F-235/335) | 2 / 4 | `lq010C.hex` (2008-03-06) is the newest file in the whole distribution |
| `MC` / `MD` | F-335 motor | 5 / 3 | |
| `DX` / `DY` | DX code reader | 2 / 2 | |
| `AP` | APS cartridge handler | 4 | |
| `CD` / `CE` | **CCD board (own PIC)** | 1 / 1 | Confirms the CCD board has its own PIC in the 235/335 family |

Naming: `XXvvff.HEX`, `vv` = **hardware** revision, `ff` = **firmware** revision.
Version digits per `ReadmeF135.txt` [VERIFIED — read from the vendor file]:
hardware `02`=PCB #125039A (base F-135), `03/04/05` = PCB #125430A/B/C (Plus),
with the explicit warning that Plus images **must not** be used on #125039A.
Firmware digits (NL): `07` initial, `08` Plus/Hybrid, `09` direct TEC control,
`0A` film-at-powerup state machine. (NM): `05` initial, `06` Plus/Hybrid.

`nm0506.HEX` internal structure: data at `0x0400–0x0403` + `0x0408–0x2D7B`
(10,612 B) + config words at `0x300000–0x30000D`. **Nothing below 0x400** — the
basis of the bootloader-is-irreplaceable finding (§4.4).

FX2-side images (Intel HEX for 8051 download): `PknInit.hex` (10,741 B data,
2004) and `Pakon5/7/8.hex` (~10.3 KB data each). **Two different `PknInit.hex`
generations exist** — the F-235-era 5,377-byte one (fits in internal RAM) and
the 2004 10,741-byte one; and two revisions of `Pakon7.hex` ship in one tree
(2004-08-02 vs 2006-02-07). FX2 memory: internal RAM 0x0000–0x3FFF; the main
segment overruns to ~0x47AC, hence the two-stage external-RAM load (§4.2); the
USB device descriptor sits at exactly offset 0x1000 in each image. [VERIFIED —
`02-firmware.md:65`, `pakon_hex.py` output]

### 4.2 FX2 firmware images and the two-stage load [VERIFIED — `01-usb-layer.md`, `pakon_load.py`]

| HEX file | Loaded identity | Product string |
|---|---|---|
| `PknInit.hex` | `0F05:35F2` rev 0002 | F235-USB Film Scanner |
| `Pakon5.hex` | `0F05:35F2` rev 0002 | F235-USB Film Scanner |
| **`Pakon7.hex`** | **`0F05:F135` rev 0002** | **F135-USB Film Scanner** |
| `Pakon8.hex` | `0F05:F335` rev 0002 | FX35-USB Film Scanner |

Load is the standard Cypress EZ-USB two-stage sequence, reimplemented in
userspace by `tools/pakon_load.py`: (1) hold 8051 in reset via vendor request
`0xA0` to `CPUCS`, (2) download stage-1 loader, (3) stage-1 copies the main image
into external RAM, (4) release reset, (5) device re-enumerates. No kext required.
[VERIFIED — `00-overview.md:80`, `4c2f32e`/`4f3539c` commits]

### 4.3 PIC firmware images [VERIFIED — `18-main-board-recovery.md`, install tree]

Naming: **`NM`**=main/motor PIC (Plus), **`NL`**=light PIC (Plus); **`PM`**/**`PL`**
= base F-135. `NMxxyy`: `xx` = PCB hardware revision, `yy` = firmware revision.

| Image | Targets PCB | Notes |
|---|---|---|
| `nm0306.HEX` | #125430**A** | — |
| `nm0406.HEX` | #125430**B** | — |
| **`nm0506.HEX`** | **#125430C** | **This unit.** `yy=06` = "Add F135 Plus/Hybrid support" |

- **The resident image on this unit is confirmed `nm0506`** — flash at 0x1000 and
  0x2000 (the addresses that discriminate nm0406 from nm0506) both matched, and
  the LED blink constants match its computed timing four-for-four. [VERIFIED —
  `26-HANDOFF.md:66`, evidence §02]
- **Choosing the wrong revision is destructive** — the readme warns 03/04/05
  images must not be crossed onto the wrong PCB. Do not reflash without matching
  the silkscreen. [VERIFIED — `18-main-board-recovery.md:74`]

### 4.4 The PIC bootloader — and why it is the crux of the repair

- Each PIC has a **serial bootloader in flash `0x0000`–`0x03FF`** (PICM) /
  `0x0000`–`0x033F` (PICL), factory-programmed. **No copy of it exists in any
  shipped file** — all 348 HEX files across every install tree were parsed; every
  PICM image starts at `0x400`, every PICL at `0x340`; no embedded HEX in any DLL
  (ASCII or UTF-16); a PIC18 code-density scan of 2,992 files returned zero hits.
  [VERIFIED — `25-root-cause.md:96`, `evidence.html` §06]
- **Therefore the bootloader region is irreplaceable.** Reading it out over ICSP
  is worth doing regardless of outcome — it exists nowhere else. [VERIFIED]
- **What broke this machine:** a blind command sweep sent `04 03 44 00 0d` — Type
  4 command **`0x0D`**, which `nm0506` implements as `0x1DAC → 0x1ABE → GOTO
  0x000000` (jump into the bootloader). Bootloader entry **erased the
  application's vector rows** at `0x0400`–`0x047F` (128 bytes = two 64-byte PIC18
  rows). Command `0x01` is `RESET`. [VERIFIED — `25-root-cause.md:6`, firmware
  disassembly]
- **The vectors were repaired** (8 blocks at 0x400–0x47F rewritten from
  `nm0506.HEX`, verified 8/8), and the board now boots on its own with a green
  power LED. But the PIC's **I²C slave still does not acknowledge at 0x44** — the
  remaining fault (§3.2). [VERIFIED — `26-HANDOFF.md:114`]

### 4.5 The PIC bootloader protocol, in full [VERIFIED — disassembly + hardware, `19`/`20`/`22`, `flash_picm.py`]

**Addressing.** Each PIC's bootloader answers at **application address + 2**
(hardcoded in `FN_bUpdate`): PICM Plus app `0x44` → boot **`0x46`**; PICL Plus
`0x40` → `0x42`; legacy `0x24`→`0x26`, `0x20`→`0x22`.

**Entering:** any of — write register `0x0a` with payload `{0x00, 0x55}`
("arm", `FN_bPicToBootLoaderState`); write register `0x97` = 1 on the app
address (`FN_bUpdate`'s enter command); or Type-4 command `0x0D` (= `GOTO
0x000000`, which is what broke this unit) after arming. Type-4 command `0x01` =
`RESET`.

**Exiting** (the hardware-confirmed sequence):
```
04 03 46 00 08            command 8: exit bootloader        → 07 02 46 00
(wait ~8 s)
02 05 44 02 0a 00 aa      write EEPROM[0]=0xAA "app valid"  → 07 02 44 00
```

**Command set** (uses the ordinary §5 packet framing addressed to the boot
address; hardware-confirmed):

| Cmd | dataLen | Effect | Wire format |
|---|---|---|---|
| **1** | 3 | Read: set 16-byte read address | `02 06 <boot> 03 01 <a7:0> <a15:8> <a23:16>` then fetch `01 03 <boot> <len> 07` → data at `resp[4..]`; address auto-increments, ~60 B max/fetch |
| **2** | 19 | **Write 16 bytes** at a 24-bit LE address | `02 16 <boot> 13 02 <a7:0> <a15:8> <a23:16> <16 data>`; sleep 10 ms after each |
| **4** | 3 | **Erase the 64-byte row** at a 24-bit LE address | `02 06 <boot> 03 04 <a7:0> <a15:8> <a23:16>`; sleep 1 ms |
| **8** | 0 | **Finalise / exit to application** | `04 03 <boot> 00 08` |

The vendor's `FN_bLoadPicLarge` makes **two passes**: pass 1 erases every
64-byte row to be written (command 4, address += 0x40); pass 2 writes 16 bytes
at a time (command 2) and never erases. Verify rule: `(actual & expected) ==
expected ? rewrite-and-retry : abort` — which only makes sense on freshly erased
flash, clinching command 4 = erase. (An earlier doc-20 reading of command 4 as
"set address" and of `0xbb8` as a 3-second delay is **superseded** — `0xbb8` is
a progress-callback value.) [VERIFIED — `flash_picm.py:25-57`,
`22-picm-restored.md:66`]

> **The internal-EEPROM "app valid" gate.** The bootloader will only jump to the
> application if internal EEPROM index 0 = `0xAA`. This is exactly what Kodak's
> updater writes (`02 05 44 02 0a 00 aa`) after every firmware update. A freshly
> flashed application will not run until `EEPROM[0]=0xAA` is set. [VERIFIED —
> `25-root-cause.md:91`, `27-icsp-procedure.md:213`]

### 4.6 Internal EEPROM (PIC on-chip, 256 bytes) index map [VERIFIED — boot-path disassembly, `27-icsp-procedure.md:113`]

| Index | Meaning |
|---|---|
| 0 | Bootloader "application valid" gate. Should be `0xAA`. |
| 1 | (paired with 0; not read by the application) |
| 2 | Gates the fault-code clear on the warm boot path (`0x0019AC`) |
| 4 | → RAM 0x135 / 0x138. The suspected stray `0x0D` write (see §9). |
| **5** | **The persisted fault code** (`0x0019EC` → RAM 0x02A). Its low nibble is what the diagnostic LED blinks. |
| 6 | → RAM 0x027 (`0x0019FA`) |
| 3 | referenced as an EEADR literal; meaning not pinned |

Reading index 5 over ICSP is the unambiguous way to read the fault code (the LED
is ambiguous — see §9.3).

### 4.6a PIC memory map — flash and the RAM variables that matter

**Flash (32 KB, PIC18F452), as established for `nm0506` on this unit:**

| Range | Contents | Status |
|---|---|---|
| `0x0000–0x03FF` | **Factory bootloader** (incl. real ISR entries at 0x0008/0x0018, forwarded to the app) | **Never shipped, never dumped — irreplaceable until ICSP-read** |
| `0x0400–0x047F` | Application reset + interrupt vector rows (two 64-byte rows); `0x400` = `GOTO 0x2BC2` | Erased by the incident; **rewritten and verified 8/8** |
| `0x0480–0x2D7F` | Application body (~10.6 KB). Landmarks: `0x1682` blink routine; `0x160C` 32-bit restoring divider; `0x168E–0x173C` blink period computation; `0x1746` POR/BOR branch; `0x1956` cold/warm fault path; `0x198E/0x19AC/0x19EC` fault-code writes; `0x1A8C` **MSSP init** (`SSPCON1=0x36`, `SSPADD←RAM 0x134`); `0x1AAE` RESET handler (cmd 0x01); `0x1ABE` bootloader jump (cmd 0x0D); `0x1DA8/0x1DAC` command dispatch; `0x2A86`/`0x2B14` the two LED state machines; `0x2BC2` app entry; `0x2C62` `MOVLW 0x44` address literal; `0x2C8E–0x2D78` main loop | Verified at 0x800/0x1000/0x2000 + 0x400–0x4F0; **~3 KB above 0x2000 never read back** |
| `0x2D80–0x7FFF` | Blank (not in image) | — |
| `0x300000–0x30000D` | Config words (§4.7) | Verified |

**RAM variables recovered** [VERIFIED — disassembly, `analysis/led_decode.md`,
evidence §3a]:

| RAM | Meaning |
|---|---|
| `0x02A` | The fault code (loaded from internal EEPROM idx 5 on warm boot; cleared on cold path). Low nibble drives LED machine A. |
| `0x134` | Multi-use argument slot: SSPADD source (0x44) at boot; blink machine A's display value (← 0x02A at `0x2CC0`) |
| `0x0EC` / `0x1EC` | Machine A bit index (3→0, MSB first) |
| `0x1FD` | Machine B display value — **hardcoded literal sequence 5→6→0**, a device/stage ID, not a diagnosis |
| `0x1FE` | Machine B bit index |
| `0x0ED/0x0EE`, `0x0EF/0x0F0`, `0x0F1/0x0F2` | Blink periods: 3000 ms gap / 600 ms "1" / 200 ms "0" |
| `0x135` / `0x138` | Loaded from internal EEPROM idx 4 |
| `0x027` | Loaded from internal EEPROM idx 6 |

### 4.7 Config words (fuses) [VERIFIED — `nm0506.HEX`, `27-icsp-procedure.md`]

| Word | Value | Meaning |
|---|---|---|
| CONFIG2H | `0x0D` | **WDTEN=1** — watchdog **enabled in hardware**, ~1.15 s, cannot be disabled in software. Any test firmware must `CLRWDT` in its loop. |
| CONFIG2L | `0x06` | BOR enabled @ 4.2 V, PWRT enabled |
| CONFIG4L | `0x81` | **LVP disabled** (bit 2 clear) → **HV programmer required** (PICkit 3/4, not SNAP) |
| CONFIG5L / 5H | `0x0f` / `0xc0` | code protection **OFF** — ICSP can read and rewrite everything |
| CONFIG6H | `0xe0` | write protection OFF |

### 4.8 The repo's own FX2 diagnostic firmware [VERIFIED — `fx2/` sources]

Three purpose-built 8051 programs exist for the FX2 (results read back via
vendor request 0xA0 with the CPU halted; each ≤1.5 KB, read-only on the bus):

- **`fx2/i2c_scan.c`** — raw 128-address I²C scan (address-ACK only, far more
  sensitive than the vendor presence probe). Hard-won rules encoded in it: never
  STOP before START (sets BERR on everything); after a read-direction ACK,
  clock one byte with LASTRD or the slave wedges SDA.
- **`fx2/eeprom_read.c`** — proper 24Cxx random-read of the boot EEPROM.
- **`fx2/mclr_window.c`** — the **MCLR window catcher**: runs a tight two-address
  probe loop while the operator pulses U11's MCLR, to catch a bootloader
  listen-window in the first milliseconds after PIC reset — the one test that
  distinguishes "application fails to arm the MSSP" (firmware, reflashable)
  from "MSSP/pins dead" (hardware) without a programmer. Complements the ICSP
  plan in `27-icsp-procedure.md`.

---

## 5. The wire protocol, byte by byte

This section documents the host↔scanner packet protocol to the byte level so the
host side can be reimplemented without the vendor software. Sources of record:
`tools/pakon_commands.py` (verified constant/builder library),
`docs/12-command-protocol.md`, `docs/03-protocol.md`, and the deep extraction of
docs 02/03/12/19/20/22.

### 5.0 The Windows transport above the packets [VERIFIED — `03-protocol.md:23`, ezusb.h]

On Windows, packets are wrapped in `DeviceIoControl` on device paths
`\\.\Pakon135` / `\\.\PakonX35`. The full IOCTL set:

| Code | Name |
|---|---|
| `0x222014` | `IOCTL_Ezusb_VENDOR_REQUEST` |
| `0x222059` | `IOCTL_EZUSB_VENDOR_OR_CLASS_REQUEST` (EEPROM path) |
| `0x22205C` | `IOCTL_EZUSB_GET_LAST_ERROR` |
| `0x22206D` | `IOCTL_EZUSB_ANCHOR_DOWNLOAD` |
| `0x222088` | `IOCTL_PAKON_READ_DIRECT` |
| `0x22208C` | `IOCTL_PAKON_WRITE_DIRECT` |
| `0x222090` | `IOCTL_PAKON_SEND_AND_RECEIVE_PACKET` (= bulk write EP1 + bulk read EP 0x81) |

On macOS none of this exists — the same bytes go straight to the bulk endpoints
via libusb. Responses are read in a 64-byte buffer.

### 5.1 Framing [VERIFIED — `pakon_commands.py:101`]

All command packets go **out on EP 0x01**; all responses come back **in on EP
0x81**. General shape:

```
<TYPE> <LEN> <ADDR> <N> <REG/CMD> [payload...]
```

- `TYPE` — packet type (see 5.2)
- `LEN` — number of bytes that follow the length byte (so total = LEN + 2)
- `ADDR` — target board's I²C 8-bit write address (see 5.3)
- `N` — count field: for reads = bytes to read; for writes = payload length
- `REG/CMD` — register index or command code
- No checksum is present in the host↔FX2 framing observed; integrity is handled
  by USB. (The FX2↔PIC I²C layer has its own ACK/NAK — surfaced as the status
  byte, 5.5.) [VERIFIED — no checksum field in any builder, `pakon_commands.py`]

There is **no on-wire checksum byte**; the status codes 2 (format) and 3
(checksum) in the response space refer to the FX2's validation of the relayed
I²C transaction, not a host-packet CRC. [VERIFIED — `25-root-cause.md:68`]

### 5.2 Packet types [VERIFIED — `pakon_commands.py:101`]

| Type | Name | Purpose | Wire example |
|---|---|---|---|
| `0x01` | READ | Read `N` bytes of a register | `01 03 40 01 83` = read 1 byte of reg 0x83 on light board |
| `0x02` | WRITE | Write `N` bytes to a register | `02 04 40 01 80 01` = write 0x01 to reg 0x80 (lamp on) |
| `0x03` | POLL | Poll device-ready/status | `03 01 10` = poll FX2 |
| `0x04` | COMMAND | Execute a command (no payload) | `04 03 44 00 A0` = motor forward |
| `0x07` | RESPONSE | Response type for WRITE and COMMAND acks | `07 02 44 00` = accepted |

> **Do not send any Type outside 1–4.** Type 0 (or ≥5 as a *command*) wedges the
> FX2 firmware until a physical power cycle. `pakon_cmd.py` refuses. [VERIFIED —
> `06-roadmap.md:72`]

**Register reads are two packets, not one** [VERIFIED — `25-root-cause.md:27`]:
```
01 03 <board> <n> <reg>      request
01 03 <board> <n> 07         fetch → 01 <n+3> <board> <status> <data...>
```
Only the *second* response carries data; the first echoes the request. Every dump
taken before this was understood recorded request-echo as if it were data.

### 5.3 Board addresses (I²C, 8-bit) [VERIFIED — `pakon_commands.py:116`, evidence §3b]

| Addr (8-bit) | 7-bit | Board | Notes |
|---|---|---|---|
| `0x10` | `0x08` | **AD_HOST** — the FX2 itself | Handled locally, never relayed to I²C. The FX2 answers this on the host's behalf. |
| `0x20` | — | AD_PICL (legacy light) | No-acks on a Plus unit |
| `0x24` | — | AD_PICM (legacy motor) | No-acks on a Plus unit |
| `0x28` | — | AD_PICF (focus/lens steppers) | Present on 235/335; role per API |
| **`0x40`/`0x41`** | `0x20` | **AD_LIGHT (PICL_PLUS)** | Lamps, LEDs, DX, temp. Answers fully. `0x41` = read alias. |
| **`0x44`/`0x45`** | `0x22` | **AD_MOTOR (PICM_PLUS)** | Film drive **and** CCD/FPGA registers. **Silent on this unit.** `0x45` = read alias. |
| `0x46`/`0x47` | `0x23` | — | Floating-bus noise, **not** a device (over-read earlier as a bootloader) [VERIFIED — `18-main-board-recovery.md:156`] |
| `0xa2`/`0xa3` | `0x51` | **Boot EEPROM** (I²C serial EEPROM) | Holds FX2 personality (§5.7) |
| `0xa4`/`0xa5` | `0x52` | **Second I²C EEPROM** | Holds `01 00 00 0c 37 59 f1` — do not touch |

A Type-4 ping (`04 03 <addr> 00 00`) across all 256 addresses finds **exactly
nine responders**, confirming these are I²C addresses on a small bus, not a
register file. [VERIFIED — `13-eeprom-repair.md:14`]

**The app/bootloader address family table** (bootloader = app + 2, hardcoded in
`FN_bUpdate`; the probe orchestrator cycles 0x44 → 0x46 → 0x24 → 0x26)
[VERIFIED — `19-review-picm-bootloader-path.md:229`]:

| Family | Motor app | Motor boot | Light app | Light boot | Firmware prefix |
|---|---|---|---|---|---|
| F-135 Plus/Hybrid | 0x44 | **0x46** | 0x40 | 0x42 | NM / NL |
| F-135 classic | 0x24 | 0x26 | 0x20 | 0x22 | PM / PL |

Note the reconciliation: on a *healthy* Plus with the app running, 0x46 is
silent (nothing listens there), and probing it reads floating-bus noise; when
the PICM is *in its bootloader*, 0x46 ACKs and 0x44 does not — both states were
observed on this unit at different times, which is what made the early evidence
so confusing. [VERIFIED — `20-picm-in-bootloader.md:11`, `18:156`]

### 5.4 Registers, per board [VERIFIED — `pakon_commands.py`]

**Light board (0x40):**

| Reg | Width | R/W | Meaning | Notes |
|---|---|---|---|---|
| 0x01 | 3 B | W | 24-bit block-read pointer | |
| 0x80 | 1 B | W | **Lamp enable bitmask** | bit0=visible, bit1=IR (0/1/2/3) |
| 0x81 | 5 B | R/W | LED level array | slot order `[B, Ir, R, 0x00, G]` |
| 0x82 | 12 B | R/W | LED duty cycles (PWM) | six u16 LE `[on_B,on_Ir,on_R,0,on_G,N]` |
| 0x83 | 1 B | R | Hardware status | |
| 0x84 | 2 B | R | Lamp temperature | units 1/16 °C |
| 0x8B | 4 B | W | Motherboard temp warning band (absolute i16 lo/hi) | |
| 0x8C | 4 B | W | Lamp temp **fault** band (signed offsets) | |
| 0x8D | 4 B | W | Motherboard temp fault band (absolute) | |
| 0x8E | 2 B | W | Lamp working setpoint (u16, [592,768]=37–48 °C) | per-unit; **danger, drives TEC** |
| 0x8F | 4 B | W | Lamp temp **warning** band (signed offsets) | |
| 0x91 | 3 B | W | DX start | |
| 0x97 | 1 B | W | Firmware-update gate — do not poke | |
| 0xD0 | 1 B | W | :=0 at temperature init | |
| 0xD1 | 1 B | W | :=1 at temperature init | |

Additional light-board registers found later [VERIFIED — deep extraction]:
`0x87` (word write) and `0x89` (byte write) — InitCcd prerequisites, both
written 0; `0x8E` (u16) — lamp working setpoint via a separate emitter; read
registers `0x02` = pending error, `0x88` = temperatures MB + LB (two u16).

Light-board **commands**: `0x00` ping; `0x8A` FIFO reset (half of
bDrvResetFifos); `0x92` DX stop.

> ⚠️ **Commands `0xd8`–`0xdf` on the light board gate the CCD stream** —
> hardware-observed: EP 0x86 level dipped at `0xd8` and the stream stopped
> entirely from `0xdf`, requiring a power cycle. Semantics and boundaries not
> established; this is "the stream gate that could not be found by static
> analysis." Do not send blind. [VERIFIED observed — `14-lamp-decoded.md:107`]

**Focus/lens board (0x28, F-235/335 only, absent on this unit):** registers
`0x88` and `0x8B` (u16) and commands `0x87`/`0x8A`
(`FN_bDrvMoveFocusSteppers`); status read `01 03 28 01 EA`. [VERIFIED —
`12-command-protocol.md:483`]

**Motor / main board (0x44):**

| Reg | Width | R/W | Meaning | Notes |
|---|---|---|---|---|
| 0xA5 | 2 B | W | Film-drive speed | u16; Plus clamp [1000, 32766]; units UNKNOWN |
| 0x82 | indexed | W | **FPGA register file** (see 5.6) | `02 06 44 03 82 <idx> <lo> <hi>` |
| 0x84 | indexed | W | **CCD A/D register file** (see 5.6) | `02 06 44 03 84 <idx> <lo> <hi>` |

Motor **commands**: `0xA0` forward, `0xA1` reverse, `0xA2` stop. Advancing film =
`set speed (reg 0xA5)` then `forward/reverse`, then host-side dwell, then `stop`
— there is no on-board timer. [VERIFIED — `pakon_commands.py:736`]

**Host / FX2 (0x10):**

| Reg | Width | R/W | Meaning |
|---|---|---|---|
| 0x01 | 3 B | W | 24-bit block-read pointer |
| 0x03 | 2 B | R | Host status word (also DEVINFO select on PIC boards) |
| 0x07 | n B | R | Block-read data window |
| 0x84 | 1 B | W | FIFO reset (value 0x02) |
| 0x8F | 1 B | W | Toggled 0→1→0 during bInit2; meaning **UNKNOWN** |

Host **command** `0x85` = clear/ack (sent when host status bit 5 / 0x20 is set).

**Device-info sequence (any PIC board):** write `0x03`:=1 to select, then read 12
bytes of reg `0x07`; version is bytes [1]=major, [2]=minor. A 30-byte info string
is at reg `0x90`. [VERIFIED — `pakon_commands.py:879`]

### 5.5 Status / error codes [VERIFIED — `25-root-cause.md:67`, `pakon_commands.py:128`]

**Type 7 responses** (answers to WRITE/COMMAND) put a status *enum* in `resp[3]`
(switch at TLB.dll `0x100087d7`); the EC error codes are the same ones in the
service manual's table (§9.1):

| Status | Meaning | EC logged |
|---|---|---|
| 0 | success — I²C ACKed and executed | — |
| 1 | **no I²C acknowledgement at all** (board absent/silent) | **1011** `EC_DRV_PacketHostErrorNoAck` |
| 2 | invalid packet / unknown command form | 1012 |
| 3 | bad checksum on the inter-PIC bus (retried) | 1013 |
| 4 | — | 1014 |
| 6, 9 | bus errors | 1017–1019 |

**Type 1 / Type 3 responses** carry a status *bitfield* in `resp[3]`:

| Bit | Mask | Meaning |
|---|---|---|
| 0 | 0x01 | busy / not ready → retry (Type-3 poll retries up to 44×) |
| 1 | 0x02 | error (in the 0x36 error mask) |
| 2 | 0x04 | error / FIFO overflow → EC 1010 |
| 3 | 0x08 | ready / OK |
| 4 | 0x10 | comm error → EC 1009 |
| 5 | 0x20 | on host reg 3 only: triggers `04 03 10 00 85` clear + retry (100×) |
| 7 | 0x80 | set by the light board; **not** in the error mask — benign [INFERRED] |

So `0x88` (light) and `0x08` (motor) are both clean. A write is **only**
accepted when `resp[0]==0x07 and resp[3]==0x00` — acceptance on any other basis
is the tooling bug that concealed the original damage. `STATUS_ERROR_MASK =
0x36`. [VERIFIED — `12-command-protocol.md:180-211`, `25-root-cause.md:66`]

**Important nuance:** status 0 on a write proves only that *a device ACKed the
I²C transaction* — the light board ACKs writes to nonsense registers just as
readily as real ones. Never read an ACK as "command understood." [VERIFIED —
`16-acquisition-decoded.md:522`]

### 5.6 CCD/FPGA register files (indexed, on board 0x44) [VERIFIED — `pakon_commands.py:758`]

Written as `02 06 44 03 <RR> <idx> <lo> <hi>` where `RR`=0x82 (FPGA) or 0x84
(A/D).

**FPGA (0x82) indices:**

| Idx | Meaning | Notes |
|---|---|---|
| 0x00 | 10-bit control register | bit0=**acquire enable** (start of scan); bit1 unknown; bits 5-6 (0x060) unknown; bit8 (0x100)=IR mode |
| 0x01–0x03 | :=0 at InitCcd | |
| 0x04 | pixel offset (`uiCcdPixelOffset`) | start pixel of the readout window |
| 0x05 | pixel end (offset + height) | [INFERRED] |
| 0x06 | integration time (`uiCcdIntegrationTime`) | exposure window |
| 0x09 | front-panel status LEDs | encoding UNKNOWN |
| 0x0A | :=0x400 at InitCcd | |
| 0x0B | :=0 in PutCcdFpgaSettings | |

> The FPGA control register (idx 0x00) has **no read path anywhere in TLB.dll** —
> the driver keeps a host-side shadow and always writes the full 10-bit word. A
> reimplementation must track it host-side. [VERIFIED — `pakon_commands.py:800`]

**A/D (0x84) indices:**

| Idx | Meaning |
|---|---|
| 0x00 | :=0x78 at InitCcd |
| 0x01 | :=0x80 at InitCcd |
| 0x02 / 0x03 / 0x04 | **Gain R / G / B** (clamped to 0x3F=63) [channel order INFERRED] |
| 0x05 / 0x06 / 0x07 | **Exposure/offset R / G / B** [channel order INFERRED] |

### 5.7 FX2 boot-EEPROM formats (I²C EEPROM at 0x51) [VERIFIED — `13-eeprom-repair.md`]

The Cypress FX2 reads a small I²C EEPROM at power-on. Byte 0 is the **format
signature**:

- **`0xC0`** — "supplies VID/PID": FX2 takes VID/PID/rev from the EEPROM but still
  needs firmware downloaded (the "unloaded 0F05:F235" state).
- **`0xC2`** — "full firmware in EEPROM": FX2 boots entirely from EEPROM (not used
  by Pakon's downloadable-firmware model).

The 9-byte `C0` personality (`DEVICE_PERSONALITY`, `F135Loader.h`):

```
byte0  C0     format signature (0xC0 supplies VID/PID; 0xC2 = full firmware)
byte1-2 05 0f idVendor  0x0F05  (little-endian)
byte3-4 35 f2 idProduct 0xF235
byte5-6 07 aa bcdDevice 0xAA07
byte7   04     config
byte8   02     personality index / board variant
```

Shipped personality images (`FirmwareLoader/Personalities/`):

| File | Bytes | rev |
|---|---|---|
| `USB DDR.bin` | `c0 05 0f 35 f2 05 aa 04 02` | aa05 |
| **`USB F135.bin`** | **`c0 05 0f 35 f2 07 aa 04 02`** | **aa07 — this unit** |
| `USB F335.bin` | `c0 05 0f 35 f2 08 aa 04 02` | aa08 |
| `USB FIFO.bin` | `c0 05 0f 35 f2 05 aa 04 01` | aa05, cfg 01 |

**The EEPROM read/write path — SOLVED** (this supersedes the "unsolved"
correction in `13-eeprom-repair.md`; doc 17 is later and hardware-confirmed):
with the **vendor stage-1 loader** running, personality access is plain vendor
control transfers:

- **Read** = bRequest **`0xA9`** (`PAKON_GET_PERSONALITY` in `F135Loader.h:88`),
  `wValue=0`, `wIndex=0` → 8–9 bytes.
- **Write** = bRequest **`0xA2`**, **`wValue` = byte address**, one byte per
  transfer, `wIndex=0`. Each committed write leaves the loader unresponsive, so
  **re-upload the stage-1 loader between bytes**; if a write is interrupted,
  finish it before power-cycling (a partial write leaves a dangerous
  valid-signature/garbage-IDs state).
- Only a **power cycle** proves an EEPROM write committed — same-session
  read-backs prove nothing.

[VERIFIED — `17-eeprom-repaired.md:60-88`; executed on hardware to repair this
unit.] The separate TLB.dll generic path uses `wValue = ((n|0x50)<<1)|readBit`
with `wIndex=0x1234` as an I²C-device *selector* across bRequest `0xA0`,
`0xA2`–`0xAC` — the earlier "0x1234 is a magic unlock" reading is retracted.
[VERIFIED — `16-acquisition-decoded.md:47`, `13-eeprom-repair.md:186`]

**Damage history of this unit's boot EEPROM** [VERIFIED — `17-eeprom-repaired.md:8`]:

| Stage | Content | Cause |
|---|---|---|
| healthy | `c0 05 0f 35 f2 07 aa 04 02` | — |
| damage 1 | `5c 05 …` (signature byte only) | ~384 blind writes across I²C addresses mistaken for board registers |
| damage 2 | `5c b5 db 05 d9 47 d7 04` (7 of 8 bytes) | repair attempt using the wrong (push-order) transfer recipe |
| repaired | `c0 05 0f 35 f2 07 aa 04 02` | the byte-at-a-time procedure above |
| **regressed** | byte 0 → non-C0 again (unit enumerates as bare `04b4:8613`) | **unexplained — byte 0 has reverted twice while bytes 1–8 held.** Open item. |

---

## 6. How the data flows — end to end

This section names the actual signals, buses and transforms in both directions,
so a reimplementer knows what to build, in order, to get an image out.

Sources: the acquisition/lamp/calibration disassembly record (docs 14/15/16),
the imaging-pipeline decode (doc 11), and the hardware logs.

### 6.1 Image path (film → file)

```
LED array ──light──► film ──► fixed lens ──► trilinear CCD (R,G,B rows)
   │                                              │ analog
   │                                              ▼
   │                                    14-bit A/D (on CCD board)
   │                                              │ digital pixels
   │                                              ▼  LVDS cable (#125158)
   │                              Xilinx Spartan-3E XC3S150E (main board)
   │                                              │  ??? interface
   │                                              ▼
   │                                    Cypress FX2 (U6) FIFO
   │                                              │  USB 2.0 bulk
   │                                              ▼
   │                                    Host EP 0x86 IN  (~30 MB/s, 512-B packets)
   │                                              │
   │                                              ▼
   │                          host: line assembly → deskew → dark/flat-field
   │                                → colour matrix + density LUT → 16-bit planar RGB → file
```

Stage-by-stage:

1. **Illumination.** Per-channel R/G/B(+IR) LEDs, PWM-driven via light-board
   registers 0x81 (levels) and 0x82 (duty/period). Almost certainly **strobed
   per scan line** in sync with CCD integration, which is why static "lamp on"
   toggles do not produce continuous light outside a real scan. [VERIFIED lamp
   registers; strobe hypothesis SPECULATION — `06-roadmap.md:188`]
2. **Sensor.** Trilinear CCD, three colour rows physically offset, so the three
   channels of a given film line are captured a few scan-lines apart and must be
   **deskewed** (re-registered) downstream. Pixels-per-line and exact CCD part
   are **UNKNOWN** (see §13). [VERIFIED trilinear — manual p.7]
3. **A/D.** 14-bit conversion on the CCD board; gains (A/D idx 0x02–0x04) and
   offsets (idx 0x05–0x07) are per-channel, clamped to 63 for gain. Output padded
   to 16-bit. [VERIFIED — manual p.7, `pakon_commands.py:780`]
4. **FPGA (Xilinx Spartan-3E XC3S150E).** This is the **biggest single unknown in
   the whole chain.** It certainly generates CCD timing (integration window,
   pixel offset/height come from FPGA registers 0x04/0x05/0x06) and gates
   acquisition (control bit0). It very likely also buffers lines, packs pixels
   for the FX2 FIFO, and may perform the trilinear deskew and any binning for the
   Base-4/8/16 resolution modes. **None of the FPGA's internal behaviour is
   decoded.** What is known: it is register-controlled by the PIC over I²C
   (board 0x44, reg 0x82 indexed), and its output feeds the FX2. [VERIFIED
   registers; internal function SPECULATION — §5.6]
5. **FPGA → FX2 interface.** The FX2 has a GPIF/slave-FIFO; the Spartan almost
   certainly clocks pixel data into the FX2 slave FIFO which the FX2 streams to
   EP 0x86. The exact interface (GPIF vs slave FIFO), clock and bus width are
   **UNKNOWN**. [SPECULATION — standard FX2 design; not decoded]
6. **FX2 → USB EP 0x86.** Free-running bulk IN stream, 512-byte HS packets,
   ~30 MB/s. The stream is **free-running and must be drained fast enough** — the
   `EC_DRV_FifoOverflow`, `EC_DRV_RingTailOverflow`, `EC_DRV_CannotFindStartOfScanLine`
   error codes all describe exactly this. The **scan-line sync marker** that tells
   the host where a line/frame begins is **not yet identified** — finding it is a
   prerequisite for assembling an image. [VERIFIED stream; sync marker UNKNOWN —
   `01-usb-layer.md:99`, `06-roadmap.md:89`]
6a. **What EP 0x86 carries when idle** (measured on this unit): a **period-3
   interleave** of three static levels (e.g. ~608 / ~593 / ~741), whose
   de-interleave phase shifts with FIFO flush alignment; illumination changes
   none of them, and the idle pattern differs across power cycles (1240;
   593/608/740; 0xFFFE). Conclusion: when no scan is armed, the FPGA is not
   clocking the sensor — the endpoint carries downstream-generated filler, not
   dark CCD data. Every earlier "constant mean" reading was an average of the
   three streams. [VERIFIED — `16-acquisition-decoded.md:270-299`, `:548`]

6b. **The line-start marker.** `EC_DRV_CannotFindStartOfScanLine` implies scan
   data carries a **sync marker per line** for the host to lock onto;
   `FN_bDrvReadScanLine` (enum 130) is the per-line read call. The marker's
   byte pattern has never been observed (no real scan has run). [VERIFIED the
   implication; marker UNKNOWN — `16-acquisition-decoded.md:334`]

7. **Host assembly + pipeline** — the vendor's order of operations is now fully
   established (TLA.dll block-graph, verified): see §10.2a. In brief: DICE (IR)
   → **density LUT → 3×4 matrix → clamp to 12-bit RPD** (in place, 16-bit planar,
   values masked to 14 bits) → rotate → **roll-level Ansel scene balance**
   (RPD→PCS→sRGB, 8-bit, perceptual) → scale/rotate → colour adjust
   (saturation/B&W-effect profiles collapsed into one CMS transform, **then**
   unsharp mask) → 8-bit reduction → save. The 16-bit planar client path taps
   the buffer before reduction.

### 6.2 Control path (host → machine)

1. **Host → FX2 (USB).** Commands on EP 0x01 OUT, responses on EP 0x81 IN
   (§5). Firmware download and EEPROM access use vendor control transfers
   (request `0xA0` for 8051 reset; a different, unsolved request for EEPROM).
2. **FX2 → I²C → PICs.** The FX2 is the **I²C bus master**. A host packet
   addressed to board 0x40/0x44 becomes an I²C transaction to that 7-bit address;
   the PIC is an **interrupt-driven I²C slave** (MSSP armed at boot). The status
   byte reflects the I²C ACK/NAK. [VERIFIED — evidence §02]
3. **PIC → actuators.** PICM (0x44) drives the film motor (and CCD/lens steppers
   on 235/335), programs the FPGA and A/D registers, and supervises the power
   rails via its own ADC. PICL (0x40) drives the LED array (levels + PWM), the
   TEC, reads temperatures and the DX sensors. [VERIFIED — §3.4, BIST split]
4. **Return path.** Faults propagate up as: PIC ADC/sensor → PIC fault state →
   status byte / register reads → FX2 → EP 0x81 → host; plus the on-board
   diagnostic LED blink (a 4-bit fault nibble from internal EEPROM index 5) and
   the front-panel LEDs (§9). BIST results (`ForceDiagnostics`) return structured
   pass/fail per subsystem.

### 6.3 Calibration and startup state — what must happen before a scan

> **Major correction to earlier assumptions:** the disassembly of
> `FN_GetCalibrateInfoLight` / `FN_bReadEEPromToRegistry` (doc 15) proves the
> per-unit **light** calibration is **not inside the scanner at all**. It lives
> in the **Windows registry** (`HKLM\Software\Pakon\TLB\Scan\DpiBase{4,8,16}_35\
> <filmMode>` — 18 `CiConfigLight` instances: per-channel LED `Current_R/G/B/Ir`,
> `Gain_R/G/B`, `Offset_R/G/B`, duty cycles, detection thresholds), produced by a
> **closed-loop search** against the CCD (`FN_bCalibrateFindLedCurrent`: start
> at 1, step +1 until max pixel ≥ 64000/64000/65500/40000 for R/G/B/IR). The
> **scanner main-board EEPROM holds motor calibration only** — two CRC32
> sections (398 B + 36 B) carrying motor speeds/adjusts per DPI — plus
> identification. There is **no per-pixel flat-field map** in evidence anywhere.
> [VERIFIED — `15-calibration-read.md:6-16, 185-234, 376-437`]

| Data | Where it lives | Recoverable how |
|---|---|---|
| FX2 personality (VID/PID) | boot I²C EEPROM (0x51) | vendor requests 0xA9 read / 0xA2 write via stage-1 loader (§5.7 — solved) |
| Bootloader "app valid" gate | PIC internal EEPROM idx 0 | ICSP, or the `02 05 44 02 0a 00 aa` packet |
| Persisted fault code | PIC internal EEPROM idx 5 | ICSP read |
| **Motor calibration** (speeds/adjusts per DPI, clamped 900–1100) | **scanner main-board EEPROM** (2 CRC32 sections, 398 + 36 B) | `FN_bReadEEPromToRegistry` path over the protocol; back it up |
| **Light calibration** (LED currents, A/D gains/offsets, duty cycles, per DPI × film mode) | **Windows registry of a calibrated install** (`HKLM\Software\Pakon\TLB`) — *not in the scanner* | (a) `reg export` from any calibrated Windows/VM install — the single highest-value artefact to obtain; or (b) re-run the decoded closed-loop search natively |
| Lamp TEC working setpoint (`LampTempWorking`, 37–48 °C window) | same registry (`\TLB\Test`) | registry dump; **do not guess — it drives the TEC** |
| Film-stock corrections, negative matrix + LUT, profiles | host-side `Config/ColorCorrection/` files | already in hand (§10) |

Startup sequence the host must drive before an image is possible (from the API
`InitializeScanner` + the manual's "Scanner corrections") [VERIFIED — manual
p.12, `04-api-surface.md`]:

1. Load FX2 firmware, re-enumerate.
2. Discover boards (`FindPicController`: `04 03 <addr> 00 00` to 0x10/0x40/0x44).
3. Read identity/versions (devinfo sequence).
4. Read motor calibration from the scanner EEPROM (**and back it up**); obtain
   light calibration from a calibrated install's registry or by running the
   decoded auto-calibration search (§6.3 note above).
5. Init CCD — the exact `FN_bDrvInitCcd` sequence is decoded and ported
   (`tools/init_ccd.py`): light reg 0x87:=0, dark-reference LampOn (explicit
   zero duty — **deliberately dark**, do not reuse its literals for
   illumination), LampOff, light reg 0x89:=0, FPGA settings (pixel offset 62,
   height 2000, integration 4093 = idx 4/5/6), FPGA idx1–3:=0, idx 0x0A:=0x400,
   idx 0x0B:=0, control bits 0x100|0x060|0x002; A/D idx0:=0x78, idx1:=0x80;
   then acquire = control |= 0x001 (fully-armed word 0x163). Constraints:
   height multiple of 4; integration ≤ 4093; CCD heights 1060/2120 appear as
   limits. [VERIFIED — `14-lamp-decoded.md:368`, `16-acquisition-decoded.md:126`,
   `init_ccd.py`]
6. Lamp warm-up to the TEC working setpoint; wait for stable
   (`WTO_LampWarmUpProgress`). Note `FN_bLampTemperatureStable` polls an
   in-process flag, not register 0x84; and the thermal-setpoint registers are
   **not on the lamp-on path** — the lamp lights without them (compiled-in
   defaults), which is how it was lit here. [VERIFIED — `15-calibration-read.md:663`, `:713`]
7. Startup corrections: gain/exposure control corrections (auto-expose against a
   clear-film/white reference), focus check.
8. Frame detection / DX read as film advances.
9. Acquire: set FPGA integration + pixel window, set acquire bit, advance film at
   the calibrated speed, drain EP 0x86, find scan-line sync, assemble.

> **The current blocker** is between "device responds / lamp lights / motor
> moves" and "usable scanner": EP 0x86 delivers data that does not respond to
> illumination, because (a) the light is likely strobed per line and only lit
> during a real scan sequence, and/or (b) the FPGA is not clocking the sensor
> into the FIFO for the programmed window, and/or (c) — most decisively — **the
> main board (0x44) is currently silent**, so the FPGA/A/D registers cannot be
> programmed at all. The hardware fault (§3.2) must be fixed before the
> acquisition path can even be exercised. [VERIFIED — `06-roadmap.md`, evidence]

---

## 7. PIC18F452 replacement feasibility

**Bottom line: the chip is cheap, plentiful, and still in production through
~2048. Availability is a non-issue. The constraints are (a) the irreplaceable
bootloader, and (b) the fact that the current diagnosis does not actually point
at a dead die.**

### 7.0 Availability and pricing (checked 2026-08-04)

- **Status: Active** at DigiKey in all three packages; a distributor aggregator
  quotes Microchip's **projected EOL as 2048-10-03**. (Microchip's own site
  blocked automated access — lifecycle wording not confirmed at the source.)
  [VERIFIED at DigiKey; EOL date REPORTED via findchips.com]
- Prices/stock [VERIFIED at listed sources, 2026-08-04]:

| Part | Package | Price @1 | Stock | Source |
|---|---|---|---|---|
| **PIC18F452-I/PT** | **44-TQFP (this board)** | **$9.04** | **2,328** | DigiKey |
| PIC18F452-I/P | 40-PDIP | $8.31 | 1,494 | DigiKey |
| PIC18F452-I/L | 44-PLCC | $9.35 | 183 (5-wk lead) | DigiKey |
| PIC18F452-I/PT | 44-TQFP | $8.87 @1 / $6.23 @100 | 102 | LCSC |

  (Mouser and Microchip Direct pages timed out — no price obtained; Newark ~$6.80,
  TME ~$9.09 REPORTED via aggregator.)
- **Counterfeit risk:** no PIC18F452-specific incident documented; generic
  recycled/remarked-part risk on eBay/AliExpress applies. At $6–9 from franchised
  distributors there is **no reason to touch the secondary market**. [VERIFIED
  negative / REPORTED general risk]

### 7.1 Near-drop-in alternatives — hardware yes, firmware no

The **PIC18F4520** is Microchip's designated migration part: "100% pinout
compatibility" in 40- and 44-pin packages [VERIFIED — migration doc DS39647A,
read in full by the research agent]. **But the Pakon HEX will not run unmodified
on it**:

- ADCON0/ADCON1 bit allocations differ; ADCON2 is new; some 452 ADC configs have
  no exact equivalent. (The PICM uses its ADC for rail supervision — §3.2.)
- **PBADEN gotcha:** on the 4520, PORTB<4:0> default to *analog* at POR.
- Oscillator config bits moved (OSCSEN gone; FCMEN/IESO added) — the HSPLL setup
  would need remapping.
- Flash write block 32 B vs 8 B; **boot block 2 KB vs 512 B** — directly
  incompatible with the Pakon's 0x000–0x3FF bootloader layout and its 64-byte-row
  erase protocol (§4.5).
- WDT base period differs; some config bits erase to opposite states; RA4 is
  open-drain on the 452 but push-pull on the 4520 — and **RA4 drives the
  diagnostic LED** on this board.

**Conclusion: only a genuine PIC18F452 is a drop-in.** The 4520/4525/4620 would
require rebuilding firmware we possess only as a binary. Ironically the modern
parts are cheaper (4520-I/PT $6.36 @1, 6,300 in stock; 4620-I/PT $8.02, 5,124)
— but that is irrelevant here. [VERIFIED — DS39647A; DigiKey prices]

### 7.2 Programming facts (cross-checked against local evidence)

- ICSP pins: MCLR/VPP, VDD, VSS, RB6=PGC, RB7=PGD. **HVP needs VPP = 9.0–13.25 V**;
  VDD must be **4.5–5.5 V for bulk erase**. [VERIFIED — programming spec DS39576B]
- The 452 supports LVP in principle, but **this chip has LVP disabled**
  (CONFIG4L=0x81, §4.7), so HVP is mandatory — consistent between the datasheet
  and the local config-word read.
- **MPLAB SNAP cannot program it** (no programmable VPP — Microchip's own
  comparison table: "Programmable VPP — Snap: No, PICkit 4: Yes"). **PICkit 4**
  does HVP on "all Flash MCUs". **PICkit 3** requires old MPLAB X (≤~5.35; support
  later dropped). **PICkit 2/3 driven by third-party PICkitPlus** explicitly
  lists PIC18F452 (device ID 0x0420). [VERIFIED — SNAP info sheet DS50002787A;
  pickitplus.co.uk supported-parts; matches `27-icsp-procedure.md`]
- 44-TQFP rework: hot air or **ChipQuik low-melt alloy** for removal; **clamshell
  TQFP-44 0.8 mm 10×10 mm programming sockets** (OTQ-44-0.8-14 on DIP adapters;
  Proto-Advantage TQFP-44→DIP-44) let you program a blank chip before soldering.
  [REPORTED — live retail listings]

> **Correction to a research-agent claim:** the agent speculated the Pakon's
> relabelled chip is "presumably code-protected." **It is not** — local evidence
> is definitive that code protection is OFF (`CONFIG5L=0x0f, CONFIG5H=0xc0,
> CONFIG6H=0xe0`; §4.7), so the full flash including the factory bootloader is
> ICSP-readable. That is precisely why the read-first plan works.

### 7.3 What a chip swap would involve (local constraints) [VERIFIED — §4.7, `27-icsp-procedure.md`]

- **The part is a PIC18F452 in 44-TQFP** (relabelled `125507A 2208`). A drop-in
  must be the same die/package or a pin-and-code-compatible successor.
- **A fresh chip will not boot the scanner even if perfectly flashed**, because:
  1. The **bootloader (`0x0000`–`0x03FF`) exists in no file** — a new chip has no
     bootloader unless you first read this one out over ICSP and merge it into the
     image. [VERIFIED — §4.4]
  2. **MPLAB bulk-erases the whole chip** before writing, so every image
     programmed must be a **single merged file** containing bootloader +
     application (`nm0506.HEX`) + config words + `EEPROM[0]=0xAA`. Programming
     `nm0506.HEX` alone erases the bootloader permanently; programming the
     bootloader as a second pass erases the application. [VERIFIED — the
     "merged-image rule", `27-icsp-procedure.md:235`]
  3. **LVP is disabled** (CONFIG4L=0x81) → a **high-voltage programmer** is
     required (PICkit 3 or 4; **not** MPLAB SNAP). [VERIFIED]
  4. **WDT is enabled in hardware** (CONFIG2H=0x0D) — relevant to any test
     firmware. [VERIFIED]
- **Therefore the correct sequence for a chip replacement is:** (a) read this
  chip's bootloader + full flash + internal EEPROM + config over ICSP via JM11;
  (b) build a merged image; (c) if the old chip is dead, solder a fresh
  PIC18F452 and program the merged image; if the old chip is alive, the swap is
  unnecessary — the fault is more likely electrical (rail/joint). [VERIFIED
  reasoning — evidence §06]
- **But note:** the current diagnosis does **not** point at a dead PIC die. The
  PIC executes (blink timing proves clock/PLL/CPU), arms its MSSP, and runs its
  main loop — it simply does not ACK on I²C. That is more consistent with an
  electrical fault (rail/joint on RC3/RC4) or MSSP damage than with a chip that
  needs wholesale replacement. A chip swap is a **last resort**, after ICSP
  read-out and the pin/peripheral tests in `27-icsp-procedure.md` §6. [VERIFIED —
  evidence §02, §06]

---

## 8. Community and prior art

### 8.0 The single most important prior-art finding

**Official Kodak/Pakon COM API documentation survives online, and a native macOS
reimplementation already exists.** Two facts reframe the whole port:

1. **The TLX COM API is documented in vendor PDFs that still exist.** The GitHub
   repo `eatfrog/PakonClient` preserves, in its `/docs`, **"F235 COM Reference
   Manual 124580-I.pdf"** and **"F235 COM Users Guide 124579-I.pdf"** — Kodak
   part-numbered documents — plus the original **TLA demo source**. [VERIFIED —
   file listing at https://github.com/eatfrog/PakonClient/tree/master/docs]. This
   is the "better-documented route" the owner asked about: the API layer
   (`ITLXMain`, `ScanPictures`, calibration, save modes) is formally documented,
   even though the *wire protocol* beneath it still had to be reverse-engineered.
2. **`pakonscan.com` is a shipping, commercial, native macOS app** that speaks
   the scanner's USB protocol directly — no XP, no VM, no kext — with a rebuilt
   Pakon colour engine, Digital ICE, DX reading, XPan/half-frame detection,
   16-bit TIFF/JPEG, $99 one-time, F-135/F-135 Plus supported (F-235/335 "on the
   roadmap, same protocol"). [VERIFIED — https://pakonscan.com/]. It is
   closed-source, so it cannot be reused, but it is **existence proof that the
   native-macOS port this project is attempting is achievable end to end.**

### 8.1 What the local material already establishes about the software stack

- The Windows stack is: **PSI.exe / PTS.exe / IQueue III.exe / TLXClientDemo.exe**
  (apps) → **tlx.dll** (`TLXMain` COM server, the API) → **TLA/TLB/TLC.dll**
  (imaging/per-model back-ends) → thin USB `.sys` drivers. [VERIFIED —
  `00-overview.md:29`, install tree]. `TLA`=F-135 back-end, `TLB`/`TLC`=other
  models [VERIFIED — community RE, `04-api-surface.md`].
- **TLX is a documented COM API surface** — `Interop.TLXLib.dll` preserves the
  full type library; **1,139 identifiers** were recovered locally, and the vendor
  **F235 COM Reference Manual/Users Guide PDFs survive online** (§8.0). See §5/§6
  for how those capabilities map to the wire protocol.
- `TLXClientDemo.exe` is the SDK's sample client; `IQueue`/`PSI` are the
  production apps. The community uses TLXClientDemo to extract **16-bit planar raw
  base-16 scans** and unlock B&W/positive/16-Base modes normally greyed out.
- **The "FX35 SDK" was a real, versioned Kodak product.** The local `PSI Release
  Notes.doc` states PSI 3.0 was "Built with **FX35 SDK 3.1** that adds black and
  white scanning on an F135 and F135 Plus"; earlier builds cite **FX35 SDK 3.0**
  ("premium color path… Ansel 4.1") and **FX35 1.2** ("supports the F135 Plus").
  The notes also reference a **DLSQueue** interface — the Kodak DLS minilab
  integration path (untested in that release). So the integrator-SDK story is
  confirmed from the vendor's own release notes; the surviving SDK documentation
  is the COM manuals in §8.0. [VERIFIED — `~/Downloads/Pakon Update 2/PSI
  Release Notes.doc`, converted and read]

### 8.2 GitHub / community projects (verified, most useful first)

| Project | What it is | Reuse value |
|---|---|---|
| **`ktkaufman03/FX35`** (C++, ~36★) | Clean-room **64-bit Windows drivers** (loader + USB core + INF/firmware package), source released. Kai Kaufman's pivotal RE; found the one-byte driver bug that broke post-XP use. [VERIFIED — https://github.com/ktkaufman03/FX35] | The driver logic maps 1:1 to what we do in libusb; the firmware-load and IOCTL sequences are directly informative |
| **`eatfrog/PakonClient`** (C#, ~18★) | Modern .NET F-135 Plus client; **32-bit TLX COM isolated over named pipes**; `/docs` has the **official COM manuals + RE notes** (`tlx.md`, `tlx-lowlevel.md`, `tlx-colour.md`). By Henri Toivonen. [VERIFIED — https://github.com/eatfrog/PakonClient] | **The single best external documentation set** — the low-level doc gives IOCTL `0x222090`, `\\.\Pakon135`, packet examples, PFS ring buffer |
| **`veroc/psix`** (Python, ~2★) | **Linux userspace driver via libusb** — no kernel module; uploads EZ-USB `.hex`, Flask web UI, C-41 pipeline + IR dust removal, 3/4-channel scan. Proof of concept, 1 commit. [VERIFIED — https://github.com/veroc/psix] | **Closest prior art to this project** — a working non-Windows libusb driver. Study its firmware-upload + acquisition path directly |
| **`eatfrog/pakonrawconverter`** (C#) | TLXClientDemo base-16 planar raw → 16-bit PNG with colour correction. [VERIFIED] | Reference for raw layout + inversion |
| **`alibosworth/pakon-planar-raw-converter`** (JS) | Browser converter/inverter for 16-bit planar raw. [VERIFIED repo] | Raw format handling |
| **`sgharvey/pakon-tlx-addons`** (AutoIt, GPL-3) | UI-automation add-ons: reindex frames, unlock B&W/positive/16-Base, keyboard colour control. [VERIFIED] | Documents which hidden modes exist |
| **`juancholehmann-cpu/pakon-win11-enhanced`** (PowerShell) | Patched PSI.exe for Win11: half-frame split, 16-bit planar raw, positive mode, DX bypass. [VERIFIED] | — |
| **`plonsker/pakon-scanning-software`**, **`nunocruz/pakon_135plus`** | Archives of the official software + community fixes (error-149, registry, raw→TIFF scripts). [VERIFIED] | The software bundle + known fixes |
| `RimitAnand/Pakon` | README-only support hub, no code. [VERIFIED] | — |

**Negative results (searched, not found):** no public **PICM/PIC bootloader dump,
ICSP writeup, or FPGA/CCD-level reverse engineering** exists anywhere — the repo's
own ICSP work (§4) would be **the first**. No GitLab projects, no published
sigrok/Wireshark USB captures, no SANE backend (psix is the only Linux work), no
open-source macOS attempt (PakonScan is closed). "PakonBatch", "PakonScanXP",
"aunextdoor"/"gerber", and `pakonf135.com` all returned nothing (likely
misremembered names / dead domains). [VERIFIED negative — community research]

### 8.3 Forums, manuals, distribution hubs

- **The primary historical distribution hub is the Facebook group "Kodak / Pakon
  F135 Scanner"** (facebook.com/groups/PakonF135) — latest software in its Files
  section. Also a Flickr group (489 members, mostly dormant since ~2021). [VERIFIED
  group exists; content FB-walled]
- **minilabhelp.com** threads are publicly *readable* (downloads need an account).
  Period service knowledge lives there — e.g. an F-235 error-3001 thread discusses
  TLA version upgrades (24RC6→24RC7) and CCD-board power/fuse failures. [VERIFIED
  one thread fetched]
- **Photrio/APUG, Rangefinderforum, Filmwasters, PentaxForums** carry model
  comparisons and repair chatter (403 to fetchers; visible via snippets). The
  community model-spec consensus: F-235(+) uses a **halogen** lamp (failure-prone),
  F-335 uses LED and is 16-bit. [REPORTED — Rangefinderforum, Machine Planet blog]
- **Scribd doc 820403015** = **"Pakon FX35 Service Manual Error Codes –
  Troubleshooting Guide"**, 32 pp. **This is the exact document read in full for
  §9** (it is present locally as `~/Downloads/Pakon FX35 Trouble Shooting
  Guide.pdf`). An F-235 Service Manual is also on Scribd (271653917) and mirrored
  on pdfcoffee. [VERIFIED metadata — https://www.scribd.com/document/820403015]
- **Board-level repair does happen in the field:** FRAME Lab (Taiwan) posted a
  "Pakon F135+ 0x2000000 error" PCB repair with photos (Jan 2023); Dynamics
  Circuit (Singapore) posted an F-135 Plus repair video. [VERIFIED FRAME Lab post;
  REPORTED video]

### 8.4 Corporate history and the liquidation flood

- **Pakon, Inc.** was founded **1985** in Minnesota out of the older **Pako
  Corporation** (photofinishing equipment). **Eastman Kodak acquired Pakon in
  February 2001**; the F-X35 line shipped under Kodak, standalone and inside
  minilab systems (branded Nexlab/Kodak/Pakon on the same hardware). Pakon ceased
  operations **~2008**; **Kodak's January 2012 Chapter 11** precipitated the
  equipment sell-off. [VERIFIED — camera-wiki.org/wiki/Pakon; Kaufman blog;
  aaaimaging.com]
- **Kodak "HS1800" is a misattribution** — the HS-1800 is a **Noritsu** scanner,
  unrelated to Pakon/TLX. There is no PCI Pakon hiding under that name. [VERIFIED —
  community search; relevant to the §2 PCI question]

---

## 9. Service documentation and fault codes

Three primary documents were read in full for this reference:

| Document | Pakon part # | Date | Pages | Content |
|---|---|---|---|---|
| **F-135 Service Manual** | 125307-B | Feb 2006 | 34 | Specs, install, theory, FRU list, cover/board removal, replacement procedures, LED tables, part numbers |
| **Pakon FX35 Service Manual §10** ("Trouble Shooting Guide") | — | Nov 2005 | pp.141–172 | **The full troubleshooting section incl. the hardware error-code table and flow charts** — highest-value document |
| **"Pakon Error Codes"** (community Facebook-group doc by Garrick Fujii, Nov 2013) | — | 2013 | 5 | PSI/host software errors (149 memory, 162 save path, 218 clean, 1003 lost sync, 2015, 3013) and VM workarounds |

Online availability [VERIFIED metadata — community research]: Scribd document
**820403015** is exactly the FX35 troubleshooting guide held locally; an
**F-235 Service Manual** exists at Scribd 271653917 with a pdfcoffee mirror
(candidate source for the missing "HW EC" bitmask appendix — §9.2);
ManualsLib hosts F-135 / F-235-series / F-335-series manuals; minilabhelp.com
threads are readable without an account (downloads are not).

### 9.1 The hardware error-code table (EC codes) [VERIFIED — FX35 Service Manual §10.6, pp.160–165, read in full]

This is the fault-code table. Each code has a **type key** (last column): **P**=
programming bug, **W**=Windows/OS, **I**=install, **C**=comms, **H**=hardware,
**U**=user.

| EC | Name | Meaning | Type |
|---|---|---|---|
| 10 | Scanner Not Initialized | A scanner function was attempted before init | P |
| 11 | No Pictures Or Strips | Operated on a picture/strip that doesn't exist | P |
| 12 | Too Many Rolls | Max rolls reached; delete some. Check Hi-Res MB/Roll to confirm install | I/U |
| 15 | Invalid Parameter | One or more function parameters invalid | P/I |
| 25 | Previous Error | Marks a prior error in the call-stack trace | P |
| **28** | **Lamp Error** | **Lamp error: low voltage OR high temperature OR slow fan OR burn-out** | **H** |
| 29 | Changing Frame Number with APS | Attempt to change APS frame number (not allowed) | U |
| 104 | APS Film Jam Extract | APS film stopped before reaching light bar (jam) | H |
| 105 | APS Film Jam Scan | APS film stopped during scan (jam) | H |
| 106 | APS Film Jam Retract | APS film stopped while retracting (jam) | H |
| 109 | APS Park | APS cartridge could not be parked after retraction | H |
| **127** | **EEProm Warning Check Sum Bad** | **Internal problem with the scanner's EEPROM — the EEPROM data is corrupt. Call a technician.** | **H** |
| **131** | **Focus Curvature Threshold** | **Focus is out of alignment.** Fix via Force Corrections, else Calibration Wizard | **H** |
| **140** | **Lamp Warm Up Failure** | **Lamp failed to reach a stable state during warm-up.** Try replacing bulb | **H** |
| **151** | **Scan Line Acquisition** | **TLX has trouble communicating with the scanner.** Check USB cable/connections; else the scanner needs technician diagnosis/repair | **C/H** |
| 159 | Time Out | A time-out (e.g. buffer not ready when saving to client memory) | — |
| 165 | WIN Device Io Control | TLX config; cycle power / reboot / reinstall TLX | W/I/C |
| **1002** | **DRV Ring Tail Overflow** | **Breakdown in the comms link between TLX and scanner over USB.** Verify USB cable length/quality; reboot; verify via PTS | C/H |
| **1003** | **DRV Lost Sync** | Same as 1002. *If running PSI 1.4 (TLA 28.10), upgrade to 2.0 (29.2) or replace Pakon5.hex* | C/H |
| **1004** | **DRV Invalid Packet Type** | Same as 1002 | W/I/C/H |
| **1005** | **DRV Packet Busy** | Same as 1002 | W/I/C |
| **1006** | **DRV Fifo Overflow** | Same as 1002 | W/I/C |
| **1011** | **DRV Packet Host Error No Ack** | Same as 1002 — **the scanner did not ACK.** Verify USB cable | W/I/C |

> **Direct relevance to this unit.** Code **1011 "DRV Packet Host Error No Ack"**
> is the exact name of **status byte 1** returned by our silent board 0x44
> (§5.5). Code **151 "Scan Line Acquisition — TLX has trouble communicating with
> the scanner"** is what the *host* software would report given a non-responding
> main board. Code **127** is the EEPROM-corrupt case. These three are the
> vendor's own names for the failure modes this machine is exhibiting. [VERIFIED —
> cross-ref §5.5]

### 9.2 The "hardware fault" bitmask codes [VERIFIED — FX35 Service Manual §10.1/10.3/10.5]

Distinct from the EC codes above, the manual and community also refer to **large
numeric "hardware fault" values** that behave like a **bitmask** (each bit = a
subsystem), surfaced by PSI:

| Value | Likely bit | Meaning per manual | Source |
|---|---|---|---|
| **200** | 0x200 | "Double EPROM" corrupted (dual-EEPROM init problem) — run Scanner Cure, reload Double EPROM | FX35 §10.1 |
| **4000** (=0x4000=16384) | 0x4000 | **Lamp board** fault — fan slow / lamp firmware corrupted (also "Lamp error 16384") | FX35 §10.3/10.5 |
| **800000** | 0x800000 | **Filter wheel** sensor stuck | FX35 §10.5 |

These map onto the same subsystem set as the `EC_BistPicm*`/`EC_BistPicl*` BIST
enums (§3.4, §4). The full bit assignment is **not fully enumerated** in the
manual excerpt; the three above are the ones stated. This bitmask is the
"Hardware Fault Codes"/"Device Code" table the owner was after — the FX35 manual
gives these three points; a complete table would need the full §10.2 "HW EC"
appendix, which in this excerpt only says "A repeated HW EC after OK → call Pakon
Technical Support" (no per-bit list). **[Named gap — see §13.]**

### 9.3 The on-board diagnostic LED blink code (this unit) [VERIFIED — `analysis/led_decode.md`]

Separate from the three front-panel LEDs (§9.4), the main board has an internal
**green diagnostic LED** that blinks a fault code. Decoded state:

- The blink is generated by **two state machines** driving RA4, displaying **two
  4-bit fields** interleaved (observed as six pulses/cycle `0 1 0 1 0 0`, cycle
  gap ~3 s):
  - **Machine A = the fault code**: RAM 0x134 ← RAM 0x02A (the fault code loaded
    from internal EEPROM index 5), 4 bits MSB-first.
  - **Machine B = a hardcoded sequence** (literals 5→6→0), a device/stage
    identifier, **not** a diagnosis.
- Because the two fields interleave and 6 ≠ 4+4, **the fault code cannot be read
  unambiguously off the LED alone.** It is one of {4, 5, 20}.
- **The unambiguous read is internal EEPROM index 5 over ICSP** (`0x0019EC MOVFF
  0x001 → 0x02A`). That byte's low nibble *is* the fault code. [VERIFIED —
  `analysis/led_decode.md:71`]
- A blinking LED (rather than solid-on) proves the last reset was **not** a
  power-on reset — it was a WDT timeout, MCLR, the RESET instruction, or a stack
  overflow — **and** EEPROM index 5 holds a non-zero fault byte. [VERIFIED —
  evidence §3a]

### 9.4 Front-panel LED tables (F-135) [VERIFIED — F-135 Service Manual p.13]

| Power LED | Meaning |
|---|---|
| Solid green | +5 V functioning |
| Off | +5 V not functioning |

| Status LED | Meaning |
|---|---|
| Solid green | Scanner ready |
| Blinking green | Scanning |
| Blinking yellow | Unable to scan at the moment |
| Blinking red | **Scanner error** |
| Off | Not functioning |

| Film LED | Meaning |
|---|---|
| Solid green | Film being scanned |
| Blinking green | Insert film to be scanned |
| Blinking yellow | Remove film from scanner |
| Off | No film in scanner |

### 9.5 Start-up / firmware / lamp / transport / picture-quality tables [VERIFIED — FX35 Service Manual §10.1/10.3/10.5/10.7/10.8]

Selected high-value entries (full tables in the source):

- **Scanner won't initialize** → corrupt registry files → run magnification test,
  run film-speed test.
- **Scanner not acknowledged by computer** → faulty USB cable / software not
  loaded / **faulty USB board in scanner** → replace cable, load software,
  replace USB board.
- **PSI won't start up** → scanner not on, or **firmware on one of the boards
  corrupted** → reload all firmware.
- **Error 151 (scan-line acquisition)** → **(U5) chip on CCD board failed** (if it
  reads `AT17C512A` replace with `AT17LV512A`), or **CCD power-module fuse
  blown**, or CCD firmware corrupt → reload CCD firmware / replace CCD power
  module. [This is the key CCD-board hardware detail — §3.3.]
- **Error 1006 in PSI** → **boot EEPROM version wrong** → in "Help/About" check
  USB version: Version (1) = older USB boards → select [USB Board Rev B1];
  Version (2) = new USB board → select [USB Board Rev D DDR FIFO]. (Confirms the
  `AA05`/`AA07`/`AA08` personality tags map to USB-board hardware revisions.)
- **Double EPROM problems during init** → run PTS "Advance" tab → Erase EEProm →
  reload double EPROM through calibration wizard; or bad USB board.
- **Scanner doesn't make noise on start-up** → **motor board not initializing** →
  reload motor-board firmware / replace Motor Control Board.
- **PSI error 250** → DX firmware corrupt → reload DX firmware.
- **PSI error 240** → CCD board → reload CCD firmware, else replace CCD board.
- **PSI error 244** → motor-board firmware → reload.
- **PSI error 800000** → filter-wheel sensor stuck → clean filter-wheel sensor.
- **Lamp error 16384 / lamp comes on then off / locks up after bulb replacement**
  → lamp-board firmware corrupted → reload lamp-board firmware.
- **Lamp current running high / lamp goes out when scan starts** → shorted lamp
  filament → replace bulb (F-235/335 incandescent path).

Troubleshooting **flow charts** exist for: Soft Focus, No Light, Low Light,
Horizontal Lines, DX, Stretched Images. Notable leaf actions: "Replace IR LED PCB
(if lines in ICE scans only)", "Replace CCD chip", "Check LVDS cable at CCD & USB
end", "Replace USB PCB", "Run Filter Wheel Test in PTS". [VERIFIED — FX35 Service
Manual pp.166–172]

### 9.6 Host-software (PSI) error codes [VERIFIED — "Pakon Error Codes" doc, read in full]

| Error | Meaning / fix |
|---|---|
| **149** | Memory error — PSI storage bucket too small for the incoming data rate. Assign **≥512 MB (1024 recommended), no more than 3 GB** to XP; `pakon-error149-fix.zip` tunes memory + disables IQueue, USB sleep, NTFS last-access. Some MacBooks can't run PSI/TLX without a 149 even after all fixes → **dual-boot XP** rather than VM. |
| **162** | Save directory missing / not writeable / set to root C:\ |
| **218** | Clean the unit (LEDs, lens, sensor, DX sensors, film track). No acetone/ammonia/benzene/carbon-tetrachloride. |
| **1003 / 3001** | `EC_DRV_LostSync` — IO APIC on / dynamic VDI fragmentation / N:\ on same physical drive as C:\ (F-235/335) |
| **2015** | `EC_PI_INVALID_FILE_FORMAT` — PakonUpdate.zip not fully extracted; re-extract and reinstall |
| **3013** | Second (scanner-buffer) hard drive is bad — replace |

This document also confirms the **community VM workaround** (Windows XP in
VMware/VirtualBox/Parallels, ≤3 GB RAM, IO APIC off, fixed/pre-allocated VDI, N:\
buffer on a separate drive) that keeps these scanners usable on modern hosts.

---

## 10. Colour science

Sources: docs 08/09/10/11 (profile format, film database, B&W, imaging
pipeline), verified against the vendor files on disk.

### 10.1 What Pakon's colour rendering *is*, and why it is portable [VERIFIED — `00-overview.md`, evidence §04]

Pakon's negative rendering — the reason these scanners are still wanted — ships
as **data, not code**, in `F-X35 COM SERVER/Config/ColorCorrection/`, so it can
be transplanted rather than reverse-engineered:

| Asset | What it is |
|---|---|
| `_ClientColNegMat.txt` | the **3×4 negative colour matrix**, plain text |
| `_ClientColNegLut.txt` | a **16,384-entry (14-bit) inversion/density curve** |
| `defaults.ini` | **per-film-stock corrections keyed by DX/film product ID**, grouped by manufacturer (92 film IDs parsed; Ilford at 105–110) |
| `*.pf`, `*.lut` | 22 output profiles: saturation ±3…±15, warm/cold B&W, sepia, sRGB, ROMM, RPD |

### 10.2 The verified colour maths [VERIFIED — evidence §04, `pakon_color.py`]

- **Density LUT:** `LUT[i] = -3500 · log₁₀(i / 16383)` reproduces the shipped
  16,384-entry `_ClientColNegLut.txt` to a **worst deviation of 0.000050** (the
  file's own 4-decimal rounding). Best-fit constant 3500.000155.
- **3×4 matrix** (from `_ClientColNegMat.txt`):
  ```
  R' =  1.11882·R − 0.10130·G − 0.01161·B −  82.60334
  G' = −0.20096·R + 1.10082·G + 0.11698·B − 586.90975
  B' = −0.11657·R + 0.04834·G + 1.08274·B − 707.78706
  ```
- **Kernel** (verified against the vendor MMX): `and 0x3fff` → LUT → `pmulhw` ×3 →
  `paddsw` offset → clamp to 0–4092 (12-bit).
- A **3×10 polynomial** matrix form also exists (`CalibrationGetColorMatrix3By10`,
  `fMatrixValue0_0…2_9`) for premium colour paths. [VERIFIED — `04-api-surface.md:146`]
- The `.pf` profiles are **standard ICC v2** (Kodak KCMS) — macOS ColorSync can
  consume them directly. [VERIFIED — `06-roadmap.md:35`]

> **Caveat:** the maths is verified against the vendor's own tables and MMX
> code, **not yet against a scanned photograph** — no frame has been scanned on
> this unit, and no pixel-for-pixel A/B against PSI output exists. [VERIFIED —
> evidence §04 caveat]

### 10.2a The full pipeline order — now established [VERIFIED — TLA.dll block graph, doc 11]

The vendor's order of operations (the thing the evidence log still listed as
unknown) has been decoded from `CiImage::bLoadImageFromBuffer` /
`CiImage::bSaveToFile` control flow — confirmed from basic-block graphs, not
address order:

1. DICE scratch/dust removal using the IR plane [position INFERRED]
2. **Colour correction:** `and 0x3fff` (14-bit) → **density LUT** → **3×4 matrix**
   (3×3 `pmulhw` + offset column `paddsw`) → clamp to **12-bit RPD** (0–4092).
   Order inside the stage is *LUT first, matrix second, offset third, clamp
   last*; in place; 16-bit planar; coefficients int16 = coeff×8192. The
   scan-path and save-path routines are byte-identical apart from scratch
   globals — **there is exactly one colour-correction routine to port.**
3. Rotate.
4. **Ansel colour scene balance — roll-level and two-pass.** The balance is
   computed for the *whole roll* (`PIAnselStartNewRoll` → per-frame
   `PIAnselAddScene` → `PIAnselEndRoll`/`AnalyzeRoll`) and then applied
   per frame; final rendering is **RPD → PCS → sRGB, 8-bit, perceptual intent**
   (from the shipped `profile-Rpd2Srgb.dpi`). **A per-frame port that balances
   each frame independently will not reproduce the Pakon look.**
5. Scale/rotate.
6. **Colour adjust:** input profile ∘ saturation profile ∘ B&W-effect profile ∘
   output profile, all four **collapsed into one CMS transform**, then
   **unsharp mask after** the colour transform.
7. 16-bit planar → 8-bit (the 16-bit client path taps the buffer before this).
8. Save.

Getting 2 and 3 the wrong way round, sharpening before colour, or per-frame
balancing "will each visibly break the Pakon look." [VERIFIED —
`11-imaging-pipeline.md:27-62, 370-402, 562-581`]

One open interior question: whether measured **Dmin** is folded into the matrix
offset column when the int16 context is built (the context-build routine was
never found). [INFERRED mechanism, named gap — `11-imaging-pipeline.md:277`]

### 10.2b Profile-format facts worth keeping [VERIFIED — doc 08 + files on disk]

- All 18 `.pf` files in `Config/ColorCorrection/` are **standard ICC v2** (CMM
  `KCMS`; `srgb.pf` is the stock HP/Lino sRGB). `unity.pf` is a bit-exact Lab
  identity (±1 LSB over all 6,859 CLUT nodes) — the Rosetta Stone for the
  encoding. Saturation profiles scale a*/b* by exactly (1 ± N/100) — confirmed
  by Kodak's own embedded metadata ("boostFactor: 1.15").
- **The B&W `.pf` files are toning effects, not film profiles** — per-picture
  CIELAB tint offsets (sepia = (0,+9,+22) etc.). "Do not go looking for
  `hp5.pf`; the concept does not exist in this architecture."
- `ColRevLut1.pf` is a device-link (Pakon CMY densities → ROMM12) whose CLUT
  performs the reversal inversion; `ColRevLutS6.lut` is a 4096-entry 12-bit
  text LUT whose consumer is **UNKNOWN** (reaches `PIBegin` as the 5th profile
  argument).
- `rpd.pf` carries six **undecoded Kodak private tags** (`K070`, `K113`,
  `K120`–`K123`; entropy 6.2–7.8 bits/B — likely compressed characterisation
  data). **Not needed**: the standard `A2B0` table is complete on its own.

### 10.2c The film "database" — what per-film really means [VERIFIED — doc 09]

- Film IDs are the **PIMA/I3A DX film-edge barcode** (Part 1 = product 0–127,
  Part 2 = specifier 0–15), not a Pakon invention. Ilford = products 105–110.
- **The shipped `defaults.ini` is an all-empty template** — 92 sections, zero
  slider values. Per-stock behaviour in a stock install comes from the Ansel
  data files: ISO-binned noise reduction, a handful of hand-tuned scene-balance
  overrides (e.g. Kodak 400BW chromogenics at `fpa = -94 -94 -94`), and
  **family-level** FPIM→RPD profiles (k200/k400/f200/…) — **not a unique LUT
  per emulsion.** The "per-film magic" reputation is mostly DX-identified ISO
  handling plus a few overrides.
- No film *names* ship anywhere in the vendor tree; the ID→name mapping is
  community-compiled (`research/film-products.json`, 492 rows).

### 10.2d B&W — the architectural truth [VERIFIED — doc 10]

- B&W is a **scan class** (`FILM_COLOR_BnW_NORMAL` / `_BnW_C41`), not a film
  product. Each class gets its own analog front end (per-class gain/offset/
  exposure/IR settings), but there is **no B&W matrix and no B&W inversion
  LUT** — B&W rides the colour-negative density machinery, and there is **no
  Ansel B&W scene-balance path at all**. This is the architectural root of the
  community's B&W contrast/tint complaints, and the main thing a macOS port can
  do *better* than the vendor: host-side density inversion anchored on per-roll
  measured film base (the plan in `10-bw-films.md` §"proposed handling").
- The NORMAL/C41 split exists because silver-image B&W is **IR-opaque** —
  Digital ICE physically cannot work on conventional B&W; C-41 dye B&W keeps it.

### 10.3 Undecoded / partially-decoded vendor colour data (the honest ledger)

| Item | Status |
|---|---|
| Kodak private ICC tags (`K070`, `K113`, `K120`–`K123` in `rpd.pf`) | bodies undecoded (high-entropy); not needed for the transform |
| `ColRevLutS6.lut` consumer | format decoded; which stage consumes it UNKNOWN |
| `defaults.ini` slider-unit → pipeline-parameter scale factor | in code, not data; UNKNOWN |
| `_ClientColNeg*.txt` producer | runtime dumps by the COM server [INFERRED]; exact producer unknown |
| Dmin folding into the offset column | mechanism INFERRED, routine not found |
| Ansel internal sub-stage order | UNKNOWN (trace strings are source-order) |
| `iBnWEffect` integer → profile mapping | UNKNOWN |
| Per-unit LED currents / `LampTempWorking` | not in any file or the scanner — registry-only (§6.3) |

---

## 11. The macOS port — current state

Honest status of the native port, and the concrete gap between "device responds"
and "usable scanner." [VERIFIED — `06-roadmap.md`, evidence]

| Stage | Status |
|---|---|
| 1. Enumerate + load firmware | ✅ **working, automated, no kext** (`pakon_load.py`) |
| 2. Command round-trip (EP1) | ✅ **working** (`pakon_cmd.py`) — both PIC boards *did* answer |
| 3. Read scanner identity/registers | 🟡 partial — protocol decoded; boards must answer |
| 4. Lamp on / motor move | ✅ both worked (lamp visually confirmed **bright blue**; motor by ear, 3 speeds + reverse) |
| 5. Acquire raw scan lines (EP 0x86) | ❌ **blocker** — stream is live (30 MB/s, 3-ch 16-bit) but does not respond to illumination; **and** the main board is now silent |
| 6. Full strip scan → file | ❌ |
| 7. Imaging/colour pipeline | ✅ **implemented, verified to 0.000050 against vendor data** (not yet against a photo) |

**What works concretely:** userspace EZ-USB firmware load with re-enumeration; the
command/response channel on EP1; the free-running EP 0x86 image stream; the full
colour pipeline (density LUT + 3×4 matrix + 12-bit clamp → 16-bit TIFF); ICC
profile handling via ColorSync.

**The gap to a usable scanner:**

1. **The hardware fault first.** Board 0x44 (PICM) does not ACK its I²C address,
   so the FPGA/A/D/motor cannot be programmed. Until the §3.2 fault is resolved
   (ICSP read-out via JM11, then the pin/peripheral/rail tests in
   `27-icsp-procedure.md`), acquisition cannot even be attempted on this unit.
2. **Transport control** — decoded (`set speed 0xA5` + `forward/reverse/stop`),
   but units of the speed register are UNKNOWN; the API speaks tenths of mm/s and
   divides by 1000, so calibration per resolution/film-type is needed.
3. **Focus** — fixed at manufacture on the base F-135; stepper-positioned on
   235/335/Plus. Focus calibration (`CalibrationFocus`) not exercised.
4. **Frame detection** — DX sensors + framing warnings exist; not implemented.
5. **Calibration** — corrected picture (§6.3): the scanner EEPROM holds *motor*
   calibration (back it up); the *light* calibration lives only in a calibrated
   Windows install's registry. **A single `reg export
   "HKLM\Software\Pakon\TLB"` from any calibrated install/VM collapses nearly
   all remaining calibration unknowns** — the highest-value artefact after a
   USB capture. Alternatively the decoded auto-calibration search can be re-run
   natively.
6. **The scan pipeline / image assembly** — the **scan-line sync marker** in the
   EP 0x86 stream is unidentified; trilinear deskew and shading specifics
   undecided. The colour pipeline order-of-operations **is now decoded**
   (§10.2a), including the roll-level two-pass scene balance.

**The three highest-leverage actions**: (a) a **USB capture of the original
Windows software** doing init→calibrate→scan (collapses every remaining
transport unknown — needs a physical x86 PC, not an Apple-Silicon VM); (b) a
**registry export from any calibrated install** (`HKLM\Software\Pakon\TLB`) —
collapses the calibration unknowns (§6.3); (c) continued **static decode of
TLB.dll** via the validated Unicorn emulator (`tools/emulate_tlb.py`) — note it
hooks `fcn.10008530`, but the CCD path emits via `fcn.100095a0`, so extend the
hook before trusting its coverage of acquisition.

**Existence proofs and prior art worth studying** (§8): `pakonscan.com` proves a
native no-VM macOS driver + colour engine is commercially achievable for the
F-135/Plus; `veroc/psix` is an open-source Linux libusb proof of concept of the
same transport; `ktkaufman03/FX35` documents the driver layer; the vendor's own
COM manuals survive in `eatfrog/PakonClient/docs`.

**Porting difficulty summary** [VERIFIED — `00-overview.md:78`]:

| Windows layer | macOS replacement | Difficulty |
|---|---|---|
| `F235Ldr.sys` firmware download | libusb control transfers (vendor req 0xA0) | Low |
| `F*usb2.sys` bulk pipes | libusb bulk on EP1/EP6 | Low (no kext/DriverKit/signing) |
| `tlx.dll` packet protocol | new implementation | High (the real RE work — mostly done) |
| `TLA/TLB/TLC.dll` imaging | new implementation | Medium (can be written fresh) |

---

## 12. Parts and sourcing

Market data checked 2026-08-04. eBay itself blocked automated fetches; current
asking prices were taken from PicClick (a live eBay mirror) and sellers' own
sites — tags note which.

### 12.1 Whole units (donor machines)

| Unit | Price seen | Condition | Source |
|---|---|---|---|
| F-135 Plus | **$1,200–$2,687** asking (typ. $1,700–1,850 "tested working") | working | PicClick/eBay [VERIFIED on PicClick] |
| F-135 (non-Plus, Nexlab) | $1,200 | tested | PicClick [VERIFIED] |
| **F-135 Plus, refurbished** | **$1,795, in stock** | refurb + warranty | **AAA Imaging Solutions** (aaaimaging.com) [VERIFIED on their site] |
| F-235 Plus | $1,950 (sold) | working | PicClick [REPORTED] |
| F-335 | £1,499 (sold, eBay UK) | working | PicClick [REPORTED] |

History for context: liquidation-era (2013–2015) prices were **$300–$750** for an
F-135 Plus; today's $1,800+ is collector/refurb pricing. AAA Imaging (California,
since 1998) was and remains the best-known refurbisher. [VERIFIED —
resurrectedcamera 2015 writeup; aaaimaging.com]

**For-parts units: effectively absent from the market** — dead units get parted
out by dealers rather than sold whole. [VERIFIED negative on PicClick samples]

### 12.2 Boards and spares — the key seller

**`internationalphotoequipment`** (eBay store, Tavares FL, 25+ years, 100%
positive) is the dominant Pakon parts source [VERIFIED via PicClick]:

| Part (F-135 Plus unless noted) | Price |
|---|---|
| **Main circuit board, tested + 45-day warranty** | **$580** (4 in stock) |
| Lamp circuit board | $520 |
| "Parts board" | $540 |
| LED/CCD module PCBs | $125–$887 |
| Load assembly (tested, warranty) | $680 |
| Transport belt/roller | $190 |
| Belt + spring set | $298 |
| Spring | $90 |
| F-235: CCD power board / sensor board / lamp board / LED PCB / engine panel | $150–$887 |
| F-235: transport assy w/ motors $498; film guide $99; filter wheel $479; PSU (SP-150-15) $570–698 | — |
| Repair service listing | $888 |

**Repair-decision consequence:** a **tested, warrantied main board for $580** is
the cost ceiling on any heroic repair of this unit's board. The ICSP route
(PICkit ~$20–90 + hours) is still first — it preserves the per-unit calibration
EEPROM contents on *this* board and would produce the first-ever public PICM
bootloader dump (§8.2) — but if the board proves electrically dead beyond the
PIC, the donor board is the rational fallback, followed by a whole donor unit at
~$1,200–1,800.

### 12.3 What commonly fails (community + vendor evidence)

- **#1 practical failure is software/OS support**, not hardware — solved by the
  XP VM route or Kaufman's 64-bit drivers (§8). [VERIFIED]
- **F-235/335 halogen bulb** — a consumable (EIKO 12V/50W GU5.3 MR16, ~$10–14,
  ~1,000 h). The F-135's LED source does not have this failure. [VERIFIED —
  Machine Planet writeup; F-135 manual]
- **Calibration/transport-sensing faults** (red blinking status LED, "film in
  guides", hangs at Corrections) — documented on minilabhelp with **no known
  fix**. [VERIFIED thread]
- **PSU failures** (F-235 spare PSUs sell at $570–698 — the price implies
  demand). [VERIFIED listings; inference]
- Belts/springs/rollers as wear items (dedicated replacement sets are stocked).
- Vendor-documented board failures: USB board, motor control board, CCD board /
  U5 PROM / CCD fuse, EEPROM corruption, lamp-board firmware, filter-wheel
  sensor, DX sensors (§9.5). No community reports found for EEPROM corruption or
  LED blink codes specifically — the §9.3 blink-decode work appears to be novel.
  [VERIFIED negative]

### 12.3a Repair assets already prepared on this machine [VERIFIED — read directly]

- **`~/pakon-windows-repair/`** — a complete, ready-to-run Windows recovery kit
  for the vendor's own documented fix ("reload motor board firmware"): `driver\`
  (F235usb2.inf/.sys + FX2 images), `firmware\` (NL/NM images + readme),
  `loader\` (FirmwareLoader.exe + FirmwareLoaderCom.dll + Personalities),
  `PTS\` (PTS.exe + Calibration.dll), `COM-SERVER\` (full tree). Requires
  **32-bit x86 Windows** (XP / 32-bit Win7 easiest; Win10/11 x64 needs
  signature enforcement disabled; **Apple Silicon cannot run it** — the app
  needs the `ezusb.sys` kernel driver, which Windows-on-ARM does not emulate).
  [VERIFIED — `~/pakon-windows-repair/README-FIRST.txt`]
- **`~/pakon-eeprom-backup/`** — EEPROM read attempts sorted into `verified/`,
  `INVALID/`, `real_SUSPECT/` (two directories quarantined as read artifacts —
  trust only `verified/`). **`~/pakon-full-dump-20260802-1924/`** — full
  project/scanner/vendor state snapshot. [VERIFIED — evidence.html footer,
  directory listing]
- Front-panel state on this unit for reference: Power **solid green** (+5 V OK),
  Status **yellow** ("unable to scan at the moment" — deliberately *not*
  blinking-red "Scanner Error"), Film **yellow**. The scanner considers itself
  alive but not ready — consistent with the vendor's "motor board not
  initializing" condition whose documented fix is firmware reload / board
  replacement. [VERIFIED — README-FIRST.txt, `24-vendor-documentation.md`]

### 12.4 What commonly fails per the service documentation [VERIFIED — §9]

The vendor troubleshooting tables point at these recurring failures: **USB board**
(not-acknowledged), **motor control board** (no start-up noise), **CCD board / U5
config PROM / CCD power-module fuse** (error 151), **EEPROM corruption** (127,
"double EPROM 200"), **lamp board firmware / incandescent bulb** (lamp errors,
16384), **filter-wheel sensor** (800000), **DX sensors** (dust/alignment), and
**belt/transport** (stretched images).

---

## 13. OPEN QUESTIONS AND WHAT WOULD ANSWER THEM

Named gaps, each with the specific action that would settle it.

**Hardware / the repair**

1. **Why does U11's I²C not ACK, when it executes and arms its MSSP?** — Read the
   chip over ICSP via JM11 (bootloader 0x0000–0x03FF, full flash, internal EEPROM,
   config), then run the pin-hold and bit-bang tests in `27-icsp-procedure.md` §6
   to separate "RC3/RC4 open" from "MSSP dead" from "flash corruption above
   0x2000." Measure the 13/12/6/5/3 V rails with a meter.
2. **JM11 pinout** — only pin1→MCLR is assumed. *Meter it out* (continuity JM11
   pins → U11 pins 18/16/17/7/6) before connecting a programmer.
3. **The fault code (index 5 low nibble)** — ICSP-read internal EEPROM index 5;
   its low nibble is the code (resolves the LED 4-vs-6 ambiguity).
4. **Board-number discrepancy 125040 vs 125430C** — photograph the FRU sticker
   and the silkscreen.
5. **The full BOM** (regulators, motor drivers, I²C pull-up value/rail, FPGA exact
   part/package, CCD sensor part, ref-des for the FPGA) — **close-up, in-focus
   photographs of each board** (phone macro ~10–15 cm, several overlapping shots).
   The current 512×288 frames cannot resolve markings.
6. **I²C pull-up location/value/rail** — trace SCL(U11 pin37)/SDA(pin42) to their
   pull-up resistors on a photo; measure resistance to each rail with power off.

**Firmware / protocol**

7. **Why does boot-EEPROM byte 0 keep reverting?** The `0xC0` signature has been
   restored twice and has twice reverted (bytes 1–8 hold both times). Unexplained.
   Understand before rewriting a third time — instrument with a read at every
   session start. (The write path itself is solved — §5.7.)
8. **The `0xd8`–`0xdf` light-board command range** — hardware-observed to gate
   the EP 0x86 stream (0xdf kills it until power cycle); semantics unknown.
   Decode statically, never probe.
9. **FPGA control-word bits 1, 5–6** and the **status-LED (FPGA idx 9) encoding** —
   trace `PutCcdFpgaSettings`/`FN_bDrvSetLed` in TLB.dll. Also the units of
   motor speed register 0xA5, and the R/G/B/Ir identity of the 0x81 slot order
   (layout is `[B, Ir, R, 0, G]` per `pakon_commands.py` but doc 12 marks the
   channel assignment inferred).
10. **The complete hardware-fault bitmask table** — the FX35 §10.2 "HW EC"
    appendix (this excerpt gives only bits 0x200, 0x4000, 0x800000). Find a fuller
    copy of the FX-35/F-235 service manual (Scribd 271653917 F-235 manual /
    pdfcoffee mirror).
10a. **Whether I²C device 0x52 (`0xa4`) is the calibration EEPROM** (it holds
    `01 00 00 0c 37 59 f1` and the service manual says calibration lives in "the
    EEPROM of the scanner") — read it safely (reads only) and diff against the
    398+36-byte CRC32 motor-calibration sections.

**Acquisition / imaging (the port blocker)**

11. **The EP 0x86 scan-line sync marker** — capture EP 0x86 during a real scan
    (needs the main board answering) or a Windows USB capture.
12. **What the FPGA actually does** (deskew? binning? packing? FPGA→FX2 interface:
    GPIF vs slave FIFO, clock, width) — the single biggest chain unknown; a
    Windows USB capture + FPGA-register trace would constrain it.
13. **Whether the lamp is strobed per scan line** — resolved by a full scan
    sequence or a USB capture, not static toggles.
14. **CCD pixels-per-line and exact sensor part** — identify the CCD chip
    (#123528) from a legible photo; derive line length from a captured scan.
15. **Per-unit light calibration values** — obtain `reg export
    "HKLM\Software\Pakon\TLB"` from any calibrated install (the four LED
    `Current_*` values, `LampTempWorking`, gains/offsets per DPI × film mode
    exist nowhere else); scanner-EEPROM motor calibration to be read and backed
    up over the protocol.
16. **Colour pipeline order** — SOLVED (§10.2a). Remaining interior gaps: Dmin
    folding, Ansel sub-stage order, `ColRevLutS6.lut` consumer, `iBnWEffect`
    mapping (§10.3). Final proof = pixel A/B of a native render vs a
    known-good vendor scan of the same frame.
17. **Cross-document contradictions to keep flagged** (do not silently
    harmonise): bootloader command 4 (doc 20 "set address" vs the operative
    erase reading); `0xbb8` delay-vs-progress; doc 02's "58 HEX files" (actual
    56); the retracted `wIndex=0x1234` "unlock"; doc 16's internal
    contradiction on whether a CCD board exists (it does, in the 235/335
    family); doc 14's lamp-duty base superseded by doc 15's density
    attenuation.

**Remaining web-research items** (two subagents still in flight; resolved inline
when they land): the §1 product-family fill-in (F-235/335 speeds, original list
prices) and the §2.4 deep sweep for any PCI-era pre-Kodak Pakon hardware.
