# 47 — The vendor GUI: what Kodak/Pakon actually shipped

A specification of the vendor's client applications, extracted from the
binaries and the shipped manual — not reconstructed from memory or forum
folklore. This is the reference for what a replacement has to be able to do,
and for which of the vendor's ideas are worth keeping.

## Sources and method

Everything below is **[EXTRACTED]** unless marked **[INFERRED]**.

| Source | What it yielded | How |
|---|---|---|
| `Pakon Update 3/program files/Pakon/PSI/PSI.exe` (v3.0.3.26, 2007-04-23) | 61 dialog templates, 3 menus, 3 toolbars, 331 strings, 46 accelerators, version info | PE resource parse (`RT_DIALOG`/`RT_MENU`/`RT_STRING`/`RT_ACCELERATOR`/`RT_TOOLBAR`/`RT_VERSION`/`RT_DLGINIT`), pefile + custom DLGTEMPLATE(EX)/MENU decoder |
| `PSI/WebHelp/PSI.chm` (2007-04-19) | 100 help topics + UI screenshots incl. the full main window (`image9.jpg`) | `7z x`, read every topic |
| `fx35install/.../F-X35 COM SERVER/TLXClientDemo.exe` (v3.1.0.28) | 9 dialogs, 1 menu, 66 strings — the engineering client over TLX | same PE parse |
| `fx35install/.../PTS/PTS.exe` + `Calibration.dll` (v3.1.0.28, .NET) | technician tool ("Pakon Troubleshooter") control inventory, calibration registry schema, framing-algorithm phase names | UTF-16 string extraction (WinForms designer names + UI text) |
| `PSI/mrd.mdb`, `PSI/*.avi` | print-product DB; instructional film-loading clips per model | listing only (mrd already dumped in `research/mrd-dump/`) |
| `docs/04-api-surface.md` | the COM surface both clients sit on (`IScanPictures`, `ICalibrationWizard`, `SCANW_*`, `WTO_*`, `EC_*`) | prior work, [VERIFIED] there |

Resource dumps live at `/tmp/pakon-gui/res/<binary>/` (regenerate with the
parser script; it is ~300 lines of Python against `pefile`). Dialog IDs cited
as `PSI:130` = dialog resource 130 in PSI.exe.

The product is two applications plus a technician tool:

* **PSI** ("Pakon Scanner Interface") — scan, review, correct, order products.
  MFC, one main window, modal dialogs. Two personalities: **Classic view**
  (menus + toolbars, operator is a technician) and **EasyOrder** (full-screen
  wizard with giant buttons, operator is a minilab clerk).
* **IQueue III** — the output spooler (prints, CDs, minilab). Out of scope for
  a home scanner; noted only where it defines the export contract.
* **PTS** ("Pakon Troubleshooter") + PSI's built-in **Calibration Wizard** —
  service and calibration.

---

## 1. Every window and dialog

### 1.1 PSI main window (Classic view)

From `PSI.chm:image9.jpg` (screenshot with the manual's own tooltip map in
`Getting_Started.htm`) plus dialog/toolbar resources:

```
┌─ PSI ────────────────────────────────────────────────────────────────────┐
│ Order  Picture  Setup  Tools  Help                                       │
│ [New][Scan][Open][Save][Products][Go1][Go2][Go3][Framing][Rot L|180|R]   │
│ [Color][?][Power]                                    ← TOOLBAR PSI:128   │
│ [Mode] Scanning ▓▓▓░ [Stop] | Idle ░░░ [Cancel] | ◀ ⏸ ▶ | cols [3▾]     │
│                                                      ← DIALOG PSI:128    │
│ ┌──────────┬──────────┬──────────┐                              ┌──────┐ │
│ │ thumb  6 │ thumb  6 │ thumb  6 │  per-frame badge stack:      │ Prev │ │
│ │ [1]    0 │ [2]    0 │ [3]    0 │  contrast/brightness/        │ Next │ │
│ │        0 │        0 │        0 │  R-C / G-M / B-Y             │Accept│ │
│ │        0 │        0 │        0 │  (grey/white/red/green/blue) │Reject│ │
│ ├──────────┼──────────┼──────────┤                              │SelAll│ │
│ │   …      │   …      │   …      │  selected frame = red border │ Size │ │
│ └──────────┴──────────┴──────────┘                   ← DIALOG PSI:400    │
│ [Rotate] [Sharpness▲▼] [Brightness▲▼] [Contrast▲▼] [R▲G▲B▲ C▼M▼Y▼]      │
│ [View Order Status]                [Edit Quantities] ← DIALOG PSI:1033   │
│ For Help, press F1        ROLL ID: 5108   Total Pictures = 35  Prints=0 │
└──────────────────────────────────────────────────────────────────────────┘
```

* **Toolbar `PSI:128`** (button order from `RT_TOOLBAR 128`): New Order ·
  Add Roll From Scanner · Add Roll From File · Save As/Export · Create
  Products · Run Package 1/2/3 · Frame Placement · Rotate 90° L / 180 / 90° R
  · Color · Context Help · System Shutdown.
* **Status strip `PSI:128` (dialog)**: two independent progress lanes —
  **scan** (label + progress + `Stop`) and **save/export** (label + progress
  + `Cancel`) — plus transport buttons (Advance / Stop / Reverse film,
  cmd ids 32839/32838/32840) and the preview-columns combo (`Fit All`, 1–9;
  `Preview_Size.htm`). Scanning and exporting run **concurrently** and are
  cancellable independently. This is load-bearing for lab throughput.
* **Right rail `PSI:400`**: Previous · Next · Accept · Reject · Select All ·
  Preview Size · Start Over.
* **Bottom edit bar `PSI:1033/1034/1035`** (three interchangeable strips):
  image edits (rotate, sharpness, brightness, contrast, R/G/B up + C/M/Y
  down) · print quantities (per-size ± for order and for selection) ·
  saturation/B&W-effect strip (Saturate/Desaturate, Sharpen/Blur,
  None/Normal/Cool/Sepia).
* **Per-thumbnail badges**: the five correction values (contrast, brightness,
  R-C, G-M, B-Y) rendered beside every frame, and index number in the corner
  (`Color_Preferences.htm`, `captured image.bmp`). Corrections are always
  visible, not hidden in an inspector.

### 1.2 Scan Settings (`PSI:130`, variants 237/242/1036/1037)

One dialog per scanner model/firmware capability — F-135 Plus gets `PSI:130`:

* **Film Color**: Neg / Pos / B&W radio (35 mm dialogs); the 24 mm variants
  read Neg / C41 B/W (`PSI:1036/1037`). Manual: "The F-135 scans color
  negative film only so this option is not available" (`How_to_Scan.htm`) —
  the Plus scans all three.
* **Resolution**: 4 Base / 8 Base / 16 Base radio. Manual pixel table:
  4Base = 1000×1500, 8Base = 1400×2100, 16Base = 2000×3000
  (`How_to_Scan.htm`). Availability varies by model (F-135: 4/8 only).
* **Film Format**: 35 mm / 24 mm (APS).
* **Number of Strips**: Single / Multiple, and Frames per Strip 4/5/6 —
  matches `STRIP_MODE_*` in the TLX API (docs/04).
* **Roll ID**: alphanumeric field with an on-screen keypad (labs used
  touchscreens; also `Enter_Roll_ID.htm`).
* **Dust and Scratch Removal / Digital ICE** checkbox — "not available when
  scanning in Black and White mode" (`How_to_Scan.htm`).
* **Premium Color Path** checkbox — maps to `SCAN_UsePremiumColorPath`.
* OK / Cancel / Notes-Label…

Keyboard: **Ctrl-S** opens this dialog; **Ctrl-Shift-S scans again with the
same settings, no dialog** (`How_to_Scan.htm`) — the fast path for a stack of
strips.

### 1.3 Per-frame edit dialogs

| Dialog | Controls | Source |
|---|---|---|
| **Color Adjust** `PSI:132` | five sliders + live numeric readouts: R-C, G-M, B-Y, Brightness, Contrast; OK/Cancel | resource + `Color.htm` |
| combined variant `PSI:233` | same five + Sharpness slider + **"Apply Scene Balance"** checkbox | resource |
| **Sharpening** `PSI:231` | one slider + readout | resource + `Sharpening.htm` |
| **Saturation** `PSI:244` | one slider + readout | resource |
| **Black and White Effect** `PSI:246` | None / Normal / Cool / Sepia radio + Apply | resource; matches `warm_bw`/`cold_bw`/`sepia` profiles in docs/11 §4 |
| **Horizontal Frame Adjust** `PSI:131` | six buttons: Min/Med/Max Left, Min/Med/Max Right | resource + `Frame_Placement.htm` |
| **Frame Type** `PSI:241` | High / Panoramic / Classic (APS aspect ratios; 24 mm only) | resource + `Picture_Menu.htm` |
| **Index Number** `PSI:137` | numeric keypad + "Index All" re-numbering | resource + `Index_Number.htm` |
| **Roll ID** `PSI:173` | keypad + scope radio: first selected roll / all selected rolls / all rolls in order | resource + `Roll_ID.htm` |
| **Notes/Label** `PSI:146` | label + notes text, "Use for every order" | resource |
| **Crop** (enlarged view) | double-click a frame → full-window view, crop marquee with corner handles preserving aspect and edge handles freeing it; cropped area shaded black; toggle cropped/original | `How_to_Crop_an_Image.htm`, `crop tools.bmp` — no dialog template, drawn in the view |

Color keyboard model (`Color.htm`): **E/R/T/A** select the channel (red /
green / blue / brightness-density), **S/F/D** decrease / increase / neutral,
**c/v** copy/paste one frame's corrections to another. Plus accelerator-table
pairs Alt+R/G/B/C/D/E with Shift variants (`RT_ACCEL 128`, cmds 32769–32780).
Whole correction grammar is printer-operator language: CMY/density in fixed
steps, one keystroke per click, values always on screen.

### 1.4 Setup dialogs (property sheet pages)

* **General** `PSI:126` — Auto-Start IQueue; **Maximum Image Storage [N] MB**
  with **Delete Files…** (the archive is self-pruning at a size cap).
* **Appearance** `PSI:127` — show/hide the per-picture color descriptors;
  UI color scheme picker.
* **Lamp** `PSI:188` — "Enable lamp saver"; wait [N] min → standby; wait
  [N] min → lamp off. (F-235's incandescent lamp; F-135 LEDs don't need it.
  `Lamp_Warm-Up_Time.htm` documents the warm-up delay it trades against.)
* **Roll ID** `PSI:1021` — numeric-only toggle, min/max, auto-increment.
* **Scan Mode** `PSI:1025` — **Normal Roll / Long Roll / Splice Roll** modes
  (roll-feeder support); **Auto Run** (run package N on every new roll +
  "Scan of next order" auto-chaining); **Portrait Mode** — limits the range
  of roll color correction for same-lighting rolls and enables auto rotation
  (`Scan_Mode.htm`).
* **Advanced (framing)** `PSI:1027` — **Aggressive Framing** checkbox
  (= `SCAN_AggressiveFraming`), Driver/Processed Ringtail + Trigger bytes,
  Dark Point Correction Interval (min), No Film Timeout (sec), Reset All.
  Manual: "Do not change any values unless directed by a Pakon authorized
  technician" (`Advanced_Scanner_Settings.htm`).
* **Color Preferences** (sheet, `Color_Preferences.htm` + strings 106–109) —
  default five-value correction per source class: Color Negative Scans,
  Color Reversal Scans, Black and White Scans, Images Opened from File.
  Menu 145 shows a hidden "Save Setting 2 / Apply setting 2" pair —
  a stored correction preset. [INFERRED: debug/service feature]
* **Save As / Options** `PSI:186` + **Image Settings** `PSI:184` — see §4.
* **EasyOrder General** `PSI:224` — which options the wizard exposes vs
  pre-decides (ICE, resolution, strip mode, frames/strip, film types,
  premium color, "Skip Preview And Edit Screen"), password, packages setup,
  source media setup.
* **Products** `PSI:120`/`141`/`177`, **Packages** `PSI:176`, **Select
  Icon** `PSI:175/222`, **Source Media** `PSI:223/1028`, CD setup
  `PSI:133/166/187`, passwords `PSI:1029/1030` — lab output config; the
  fifteen named packages of the EasyOrder flow.

### 1.5 EasyOrder wizard screens

Full-screen pages at 289×192 DLU with Arial 18pt (`PSI:401 → 403 → 402 →
1031/238 → 404 → 1033/1034/1035` + sidebar 400, bottom strip 405):
Enter Roll ID (keypad) → Select Source Media (15 tiles) → Select a Package
(15 tiles, Matte/Gloss) → Specify Film (film color / single-roll vs cut
strips, resolution, frames per strip, ICE, premium color) → **Scanning**
(`PSI:404`: an animation control playing the model-specific
`scanroll*.avi` / `scanstrips*.avi` clip showing how to feed the film +
status line + Cancel) → Image Editing (grid + big-button bars). Every page:
Prev / Next / Order Status; password-gated exit back to Classic
(`Switching_to_Order_Form_Mode.htm`).

### 1.6 Progress/utility dialogs

`PSI:229` "Media not found — please insert media into reader"; `PSI:1032`
Print Quantities Adjust (Small/Medium/Large ±); About `PSI:100` (§5.4).

### 1.7 TLXClientDemo (engineering client)

One window (`TLX:102`): thumbnail area, Advance Film / Scan / Cancel Scan /
Save / Cancel Save, roll group management ("Move Oldest Roll in Scan Group To
Save Group", "Release Rolls in Save Group"), per-picture attributes (strip
num, film product/specifier, frame num, selected/hidden), Hi/Lo buffer
toggle, twin progress bars, "Load Firmware At Startup", "Self Test At
Startup", Reset Leds. Its dialogs expose the raw API:

* **Scan Settings** (`TLX:130`): film format 35 mm / 24 mm extracted / 24 mm
  cartridge; color Neg/Pos/B&W/B&W-C41; Base 4/8/16; single/4/5/6-frame
  strips; **RFT Splice Mode, Aggressive Framing, Scratch Removal, Film Drag,
  Exercise Steppers, Premium Color Path**; Pre-Scan; Force-Corrections group:
  **Light Correction / Film Track Test / Focus Correction / Set Film Track /
  Reset Motor Speed Adjust**.
* **Save Settings** (`TLX:131`): picture selection; size (original / display
  / sized-for-saving + DPI/W/H); rotation + mirror; **"Use low resolution
  buffer for a faster save when quality is not required"**; **"Use Scratch
  Removal (if available)"**; **"Use Color Correction (12 bit RPD)"**; **"Use
  Color Scene Balance Algorithm (8 bit sRGB)"**; **"Use Color Adjustments
  (apply color sliders adjustments)"** — the pipeline stages of docs/11 as
  user-facing checkboxes; save to disk (type + compression) vs client memory
  (planar 16/8, DIB, header, top-down, fast updates, worker thread).
* **Framing Adjustment** (`TLX:133`): numeric left/top/right/bottom against
  the hi-res buffer, adjust-framing vs adjust-cropping modes, and a
  **"Framing Risk"** readout (= `FRAMING_RISK_*` from the API).
* **Color Adjustment** (`TLX:134`): Red, Green, Blue, Brightness, Contrast,
  Sharpness sliders.
* **Pre-Scan Framing Adjust** (`TLX:135`): frame height/width in pixels and
  mm×1000, crop L/R/T/B — the geometry constants of `FRAME_SIZES_*`.
* **Advance Motor** (`TLX:137`): duration ms (−1 = until cancelled), speed
  in **tenths of mm/sec, forward 10–355, reverse −10 to −355**.
* Menu: Pre-Scan per format/base; **Control → Lamp off / Lamp dim / Lamp on**
  (the three-state lamp of `FILM_COLOR_LAMP_*`), Rollers release, APS manual
  retract.

### 1.8 PTS (Pakon Troubleshooter) + Calibration.dll

WinForms; control inventory from designer strings. Tabs/areas: Setup tests,
Advanced (Calibrate, Live Acquire incl. IR channel, EEPROM actions incl.
**Erase EEProm**, scanner identification / type switch, 4-Channel Save),
DX test, Focus test, Film Track / Transport (fwd/rev fast/slow jog + stop),
Optical Alignment (guided tilt/skew: "Loosen top screw N and M/8 turns",
"Tilt within tolerance"), light calibration with **live scan-line display**
("Display entire scan line", "Display each pixel", offset left/right/reset,
per-channel avg/min/max/gain readouts), firmware update per board, Motor
Speed / Mag tests, Digital Pots, Lens/CCD Stepper tests, Filter Wheel test.

Calibration.dll writes per-mode registry sets — `Gain_R/G/B`,
`Offset_R/G/B`, `CcdExposureOpenGate_*`, `Current_*`, `DutyCycle_*`,
`DutyCycleOpenGate_*`, `IrLEDStartTime`, motor speeds, stepper positions,
`NegMatrix`/`PosMatrix` — under `SOFTWARE\Pakon\TL{A,B,C}\Scan\DpiBase{4,8,16}_{24,35}`,
and archives them as `{model}_SN{serial:04d}_0.reg` under `\Calibration\`.
(Consistent with the recovered registry in `docs/37`.)

Track-test diagnostics name the framing algorithm's phases: **Good Dx
Count · LookForNicePictures · FramingLookInBetweenEnds · LookAtBeginning ·
LookAtEnd · FramingBlindlyPlacePictures** — i.e. detection first tries
well-exposed frames, then gaps between anchors, then the roll ends, then
falls back to blind placement at nominal pitch. [EXTRACTED names;
phase-order reading is INFERRED from the names.]

---

## 2. The menu tree (PSI Classic, `RT_MENU 128`)

```
Order                             Picture                        Setup
  New                Ctrl+N        Select All        Ctrl+A       Package ▸ 1/2/3   Ctrl+1/2/3
  ────                             ────                           ────
  Add Roll From Scanner… Ctrl+S    Reject            Del          Twain Select…
  Cancel Scan                      Accept            Ins          Scanner ▸
  ────                             Insert                           Calibration Wizard…
  Add Roll From File…  Ctrl+O      ────                             Custom Framing…
  Add Roll From Archive…           Frame Placement…                 Scan Mode…
  Add Roll From TWAIN Device…      Rotate ▸ 90°R / 90°L / 180       Advanced…
  ────                             Flip ▸ Up-Down / Left-Right    ────
  Save As…                         ────                           Pakon CDR…
  Create Products…     Ctrl+P      Color…            Ctrl+C       Kodak Picture CD…
  Run Package 1/2/3  Ctrl+Sh+1/2/3 Sharpness…                     ────
  Cancel Export                    Saturation…                    General…
  ────                             Black and White…               Color Preferences…
  Notes/Label…                     ────                           IQueue…
  View Properties…                 Roll ID…                       EasyOrder…
  Exit                             Index Number…
  Products Again     Ctrl+Sh+P     Frame Type…                  Tools
                                   ────                           EasyOrder
Help                               View Properties…               Advance Film
  Help Topics… / Context Help                                     Stop Advance Film
  About Pakon…                                                    Reverse Film
```

Context menu on a frame (`RT_MENU 150`): Select All, Frame Placement, the
rotations/flips, Color, Sharpness, Roll ID, Index Number, Frame Type, view
picture/order properties. Hidden debug menu (`RT_MENU 145`): calibration
wizard button-state/timer fakes, Lamp Saver STAND BY / SLEEP, bottom-bar
cycling, color setting save/apply.

---

## 3. The operator's workflow (power-on → files)

From `Getting_Started.htm`, `How_to_Scan.htm`, `Scanning.htm`,
`Scanner_Status.htm`, status strings `PSI:RT_STRING`:

1. **Power on scanner, wait five seconds, launch PSI** (manual is explicit).
   PSI initialises the scanner (status `Initializing`, string 148; failure
   text names an initialization stage number, string 24). Firmware update
   offered if stale (string 5, with the do-not-power-off warning). EEPROM
   trouble surfaces as a warning number (string 171).
2. Lamp warms if incandescent (status `Lamp Warming`, string 144; F-235 only).
3. **New order** (Ctrl-N) — the order is the unit of work; the roll joins an
   order.
4. **Add Roll From Scanner** (Ctrl-S) → Scan Settings dialog (§1.2) → OK.
   Status `Preparing To Scan` (1142) → "wait to insert film" prompt (61212).
5. **Insert film when the Film LED blinks green** (F-135 LED legend,
   `How_to_Scan.htm`: power/status/film LEDs; blinking yellow = remove film).
   DX code read automatically; emulsion/tail warnings if inserted wrong
   (strings 36/37/39 — scan continues, quality warning only).
6. Status `Scanning` (149) with progress bar; **the whole strip feeds
   through at constant speed** — this is a transport scanner, film enters
   the right, exits the left. Multi-strip mode loops "Insert and remove each
   film strip one at a time. Press Stop when finished" (61210).
7. Frames appear in the grid as detected; scanning of the next strip and
   review of already-scanned frames overlap. Status returns to `Idle` (153);
   save lane shows `Updating Images` (161) as edits render.
8. **Review**: select frames (grid, red border), Accept/Reject (Ins/Del),
   correct color/density from the keyboard (E/R/T/A + S/F/D) or bottom bar,
   crop via double-click, fix mis-framed frames via Frame Placement,
   re-index / re-roll-ID as needed.
9. **Output**: Create Products (Ctrl-P) or Run Package 1–3, or **Save As**
   to disk. Save lane: `Waiting for Export` (156) → `Exporting Images` (159)
   / `Transferring Images` (157), cancellable. "A new order may be started
   once the current order begins exporting" (`Scanner_Saving_Status.htm`) —
   scan-ahead while the previous roll exports.
10. Ctrl-N, next roll. At day's end, the toolbar power button shuts the
    whole station down (`How_to_Shutdown_the_System.htm`).

Throughput features worth naming: Ctrl-Shift-S (rescan, same settings, no
dialog); Auto Run (auto-package + auto-next-scan chaining = hands-free roll
after roll); the twin status lanes; per-roll auto-incrementing Roll ID.

---

## 4. Settings the vendor exposed

| Domain | Setting | Values / notes | Source |
|---|---|---|---|
| Scan | Film color | Neg / Pos / B&W (/ B&W C41 for 24 mm) | `PSI:130`, TLX:130 |
| Scan | Resolution | Base 4 / 8 / 16 (1000×1500 / 1400×2100 / 2000×3000) | `PSI:130`, `How_to_Scan.htm` |
| Scan | Film format | 35 mm / 24 mm APS (extracted or cartridge) | `PSI:130`, TLX:130 |
| Scan | Strips | single roll / multiple strips of 4·5·6 frames | `PSI:130` |
| Scan | Digital ICE | on/off; unavailable for B&W | `PSI:130` |
| Scan | Premium Color Path | on/off (`SCAN_UsePremiumColorPath`) | `PSI:130/224` |
| Scan | Roll ID | keypad, numeric-only rule, min/max, auto-increment | `PSI:130/1021` |
| Scan mode | Normal / Long Roll / Splice | roll-feeder workflows; restart required | `PSI:1025`, `Scan_Mode.htm` |
| Scan mode | Portrait Mode | narrows roll SBA range, enables auto-rotation | `Scan_Mode.htm` |
| Framing | Aggressive Framing, ringtail/trigger bytes, dark-point interval, no-film timeout | technician-only | `PSI:1027` |
| Color | per-class default corrections | ColNeg / ColRev / B&W / imported | `Color_Preferences.htm` |
| Lamp | lamp saver | standby after N min, off after M min | `PSI:188` |
| Export | format | **TIFF / Bitmap / JPEG / EXIF JPEG** (+ JPEG quality slider, estimated size) | `PSI:184` + DLGINIT |
| Export | size | use scanned resolution / don't scale up / height px + DPI | `PSI:184` |
| Export | naming | prefix with **ROLLID** and **COUNT** tokens → `01_5625_Pakon_AAA004.jpg`; or keep original names | `PSI:186`, `Save_As.htm` |
| Export | destination | root directory + subdirectory per Roll ID | `PSI:186` |
| Export | **Save As Raw** | "without any color correction. The image will appear as a negative." | `PSI:186`, `Save_As.htm` |
| Export | scope | selected only / all except rejected | `PSI:186` |
| Archive | max image storage MB, auto-prune, delete-files | `PSI:126` |
| EasyOrder | option visibility matrix, 15 packages, 15 source media, password | `PSI:224` |

The engineering save surface adds (TLX:131): 16-bit planar to memory, DIB,
low-res-buffer fast save, and stage toggles for RPD correction / scene
balance / slider adjustments — capabilities the consumer UI hides.

---

## 5. Feedback during a scan

### 5.1 Status lanes

Scan lane strings (`RT_STRING`): `Initializing` · `Lamp Warming` ·
`Preparing To Scan` · `Scanning` · `Advancing Film` · `Focusing` ·
`Calibrating` · `Importing` · `Idle`. Save lane: `Updating Images` ·
`Waiting for Export` · `Transferring Images` · `Exporting Images`. Each lane:
text + progress bar + its own Stop/Cancel (`PSI:128`).

### 5.2 Hardware status language

* F-135 LED legend (Power / Status / Film; solid/blink green/yellow/red) —
  the manual teaches film handling entirely through the Film LED
  (`How_to_Scan.htm`; string 4: "Blinking yellow - remove film / Blinking
  green - insert film").
* PTS worker states: Warming Lamp, Advancing Film, Moving Film Guides,
  Moving Film Rollers, Testing DX Sensors, Running Diagnostics, Running
  Corrections, Exercising Steppers, Retracting APS, Updating {APS, CCD, DX,
  Lamp, Motor} Firmware.

### 5.3 Warnings and errors (user-facing text, extracted verbatim)

| Condition | Vendor text (abridged) | Source |
|---|---|---|
| Dirty illuminator | "The illuminator inside the scanner needs cleaning. Cancel Scan? Yes/No" | string 32768/32804 |
| Dim lamp | "An insufficient light condition exists. Scans may not be optimal." | string 32769 |
| Burned-out lamp | "The lamp in the scanner is burned out. Please replace." | string 40 |
| Hardware fault | "The scanner has reported a hardware fault. The fault code is 0x%X." | string 35 |
| Scanner error | "…error code is %d. If the problem persists, contact technical support." | string 41 |
| Film jam / over-length | "Either the film jammed during the scan or the film strip is longer than the scanner is configured to capture in one scan." | string 44 |
| No film | "The scanner timed out waiting for film." | string 42 |
| Emulsion down / tail first / emulsion out | quality warnings, scan continues | strings 36/37/39 |
| EEPROM | "problems reading EEPROM during initialization… Warning Number: %d" | string 171 |
| Wrong film state | remove-film / reverse-first instructions keyed to the LED legend | strings 4/6 |
| Busy / not initialised / nothing to cancel | short statuses | strings 112/120/121 |

The API's `SCANW_*` warnings (DX good/bad, framing good/fair/bad, motor
speed to ±0.5 %, light dim, max film length; docs/04) are the wire-level
source feeding these. TLXClientDemo surfaces `WTO_*` worker errors raw.

### 5.4 About box as diagnostics (`PSI:100`)

Scanner Model · Serial Number · Hardware Version · USB Driver Version ·
**CCD / Light / DX / Motor board versions** (+ APS board in TLX) · TLA
version · TLX version. Support procedure expects these + the log folders
(`Error_Log_Files.htm`: `F-X35 Com Server\Logs`, IQueue logs).

---

## 6. Whole-roll handling

* **Frame detection is post-hoc on a continuous strip.** The scanner streams
  the whole strip; framing then places frame windows (phase names in §1.8).
  Quality is graded (`SCANW_FRAMING_GOOD/FAIR/BAD`, `FRAMING_RISK_*`) and the
  worst cases surface in TLX's Framing dialog as a numeric risk.
* **Correction of framing, not re-scan**: Frame Placement nudges a frame
  window left/right (six coarse buttons in PSI; exact pixel offsets in TLX);
  Insert adds a frame the detector missed (`Picture -> Insert`); Custom
  Framing (`Setup -> Scanner -> Custom Framing…`) edits the geometry defaults.
  **There is no per-frame re-scan** — the transport cannot seek backwards to
  a frame; the fix is always re-run the whole strip (Ctrl-Shift-S) or adjust
  the window into the already-captured buffer. This is the honest physics of
  a transport scanner and the replacement should adopt the same model
  [EXTRACTED capability set; "no re-scan" additionally INFERRED from absence
  of any such command in PSI, TLX API and manual].
* **Roll-level color**: corrections are per-frame offsets on top of a
  roll-level scene balance (docs/11 §5); Portrait Mode narrows the roll
  balance range; c/v copies one frame's corrections to others; Color
  Preferences sets per-class defaults.
* **Accept/Reject** is the selection model for export — rejected frames stay
  visible (marked) but never export.
* **Multi-strip rolls** accumulate into one roll/order; strips of 4/5/6
  frames; DX code read per strip; index numbers editable when the DX read
  fails (duplicate-index guard: string 105).
* **Archive**: every scanned order lands in a size-capped archive
  (`Add Roll From Archive…`, search by Roll ID / date window `PSI:129`), so
  "re-print" never means "re-scan".

## 7. What the vendor got right (keep) / wrong (drop)

**Keep — these are the product:**

1. **Scan-ahead pipelining** — scanning strip N+1 while N exports; two
   independent cancellable status lanes.
2. **Zero-dialog rescan** (Ctrl-Shift-S) and Auto-Run chaining — feed roll
   after roll without touching the mouse.
3. **Keyboard color grammar with always-visible values** — channel select +
   inc/dec/neutral, copy/paste corrections, numeric badges on every frame.
   (Modernise the units, keep the philosophy: corrections are visible state,
   not hidden dialog state.)
4. **The film LED contract** — the machine tells you when to insert/remove
   film; the software repeats the same language. Map to on-screen transport
   prompts.
5. **Honesty about framing** — framing risk graded and surfaced; one-click
   frame nudge; insert-missed-frame.
6. **Roll-level color before per-frame offsets** (docs/11) — per-frame-only
   balancing breaks the look.
7. **Emulsion/tail warnings that don't abort** — warn and continue.
8. **Save As Raw** as the escape hatch (uncorrected negative out).
9. **Self-pruning archive with search** — bounded disk use, re-export
   without re-scan.
10. **About box = full hardware manifest** — every board version + serial
    visible for support.

**Drop:**

* The lab order/product/package/IQueue layer (CDs, prints, kiosks, minilab) —
  the home replacement exports files.
* EasyOrder's giant-button wizard (its job — deskilling minilab clerks — is
  gone; its lesson — a guided scan flow — survives as good defaults).
* Modal dialog editing (Color/Sharpness/etc. as blocking popups), fixed
  3-column thumbnail-only review, no large loupe view in Classic.
* CMY-print-channel units for corrections (operators knew printer channels;
  photographers today think in exposure/WB/curves — keep R/G/B/density
  *semantics* underneath).
* 8-bit-only export (TIFF/BMP/JPEG/EXIF; 16-bit existed only via the
  engineering to-memory path) — the replacement's pipeline is 16-bit planar
  end-to-end (docs/04, docs/11) and should export it.
* Hidden technician settings behind "do not change" warnings — put them in a
  Diagnostics surface with real telemetry instead.

## 8. Open items / not extracted

* PSIBitmapButtons.dll (7.9 MB) holds ~180 owner-draw button bitmaps; not
  individually catalogued (EOM screenshots in the CHM cover the ones that
  matter).
* IQueue III internals beyond the manual topics — out of scope.
* Exact numeric range/step of the five correction sliders — not in resources
  (set at runtime); badges in screenshots show small signed integers around
  0, contrast default 6. [UNKNOWN]
* `Hardware_Fault_Codes.htm` documents no code table; fault codes surface as
  raw hex (string 35). The `EC_*` enum in docs/04 is the real table.
