# 60 — Handover

**Date: 2026-08-13.** Written for an agent picking this up cold. Everything
here is either verifiable in the repo or flagged as inference. Read the traps
section before touching hardware.

Branch: `finding/f235-and-vendor-shadows`. Not yet merged to `main`.

---

## 1. Where the project actually is

The scanner **works**. The hardware is repaired, the firmware loads correctly,
and the vendor software (PSI, on the XP VM) scans film and renders it properly.

The open problem is entirely on the **port** side: our rendered output is
washed out — raised blacks, collapsed range — while the vendor's, from the same
scanner and the same frame, is not.

Six tone subsystems (`cna`, `dra`, `toneHelper`, `contrast`, `ast`,
`citras`-analyze) are Unicorn-verified **bit-exact** against the real DLL, and
the output is still wrong. That paradox is the central fact of this handover,
and `docs/58` proposes the resolution.

---

## 2. The live question: the washout

### The leading hypothesis (`docs/58`)

The vendor's SRA stage is a matched **forward/backward LUT pair**. The port
loads the forward LUT and **never loads the backward one** — `sraBkLut`,
`sra_bk`, `BkLut` appear nowhere in either the Python or the Go engine.

Proven, by parsing the shipped files: `bk(fwd(x)) == x` across the whole domain
to within one code value. The forward curve expands shadows hard (input 64 →
1016) — a working space plainly designed to be undone.

```
vendor:   forward -> (analysis in SRA space) -> backward -> tone chain
port:     forward -> (analysis in SRA space) ------------> tone chain
```

That explains the paradox: the maths is right, the data reaching it is in the
wrong space.

**This is not yet confirmed as the cause.** It is a proven asymmetry and a
strong candidate. The confirming test is in §4.

### The second gap

`sra_fwd_lut_name()` in `pakon_ansel_maps.py` handles `rom12` and `rim12` and
falls through to `-default`. The vendor also ships
`common-sraFwdLut-metric-erimm.lut`, which has no branch. Note the backward set
has **no** `erimm` variant, so the two axes are not symmetric — understand that
before wiring the inverse in.

### What else is unported

`docs/56` inventoried the vendor's real render from a live capture: **218 data
files**, and ~19 stages with no port equivalent (`pfd`, `dtt`, `dsba`, `ane`,
`dei`, `falloff`, `flare`, `dyefade`, `lighting`, `gainOffset`,
`blackPrinting`, `noiseFiltering`, `deRender`, `reRender`,
`neutralGammaAdjust`, `pan`, `area`, `nra`, `pnr`).

**Caveat that matters:** a file being *opened* proves only that the path
*considered* it. Map-driven resolution opens whole families. `docs/57` is a
written-and-ready recipe for turning that inventory into a real execution trace
with DynamoRIO — it needs a 32-bit XP-compatible build, which is the blocker.

---

## 3. Ground truth: the vendor scans

`research/vendor-scans/` — 12 images, six frames, each as a **pair**:

| file | what it is |
|---|---|
| `rawAA00N.png` | PSI's "RAW" export — least-processed stage it will emit |
| `AA00N.png` | PSI's finished render of the same frame |

Same scanner, same session, same film. This is the only end-to-end ground
truth in the project.

### Two traps in this data

1. **`rawAA00N` is NOT 12-bit sensor data.** It is **8-bit RGB**, and it is
   already substantially processed — a positive image, not a negative. Do not
   treat it as CCD output. The real 12-bit path is not exported by PSI at all.
2. **They were converted TIFF → PNG** to keep the repo from tripling in size
   (208 MB → 103 MB). The conversion is **lossless and verified per file** —
   every PNG round-trips to pixel-identical bytes. `manifest.json` carries the
   SHA-256 of both the original TIFF and the raw pixel buffer for each, so
   identity is checkable. The originals had no vendor metadata: 16 structural
   TIFF tags, nothing else, identical between raw and rendered.

### The measurement that defines "washed out"

All values 0-255, per channel, from the files in `research/vendor-scans/`:

```
frame        ch     p1    p5   p50   p95   p99   min   max
rawAA005     R      14    19    76   164   180     7   202
             G      10    14    42   112   122     4   131
             B       6     8    35   107   114     2   125
vendorAA005  R       0     0    35   228   241     0   255
             G       6     8    87   226   245     5   255
             B       5     8    94   236   253     0   255
```

**The vendor reaches p1 = 0/6/5 with true black and uses the full 0-255.** The
port's floor on the same frame is 60-110. That gap is the whole defect.

`docs/54` has the original measurement and establishes that the floor is a
**port artefact**, not something inherent to the scanner.

---

## 4. The single highest-value next action

Apply `common-sraBkLut-metric-default.lut` at the point the round trip should
close, re-render `rawAA005`, and compare against `AA005`.

Target: **p1 = 0/6/5**. Current: 60-110.

If the range opens up, `docs/58` is confirmed and the remaining work is scoped.
If it does not, the hypothesis is dead and `docs/57`'s execution trace becomes
the priority. Either outcome is worth more than more static analysis.

Where the inverse belongs is an architecture question — the vendor does its
analysis *in* SRA space, so the inverse goes after that work, not immediately
after the forward LUT.

---

## 5. Hardware state — read before connecting anything

### Repaired, do not re-break

The boot EEPROM was damaged: **byte 0 was `0x5C` instead of `0xC0`**. That one
byte caused the scanner to enumerate as an **F-235**, load the wrong firmware,
bind the wrong TLA slot, and no-ACK on `0xF4`. It was repaired with a single
one-byte write and verified across a power cycle (`docs/17`).

Healthy personality: `c0 05 0f 35 f2 07 aa 04 02` — C0 signature, VID `0x0F05`,
PID `0xF235`, rev `0xAA07`.

### Do not run these

* **`tools/eeprom_repair.py --write`.** It still contains the buggy write
  (`ctrl_transfer(..., payload, 8000)` — 9 bytes at `wValue=0`) that `docs/17`
  blames for making the original damage worse. Reads are fine. **Do not pass
  `--write`.**
* **`~/pakon-findings/ccd_bringup.py`.** Built on `docs/42`'s ordering, which
  `docs/55` proved wrong.
* **`tools/start_acquire.py`'s verdict string.** It prints "ACQUISITION IS
  RUNNING" while the numbers show no gain response. The numbers are right; the
  verdict is not.

### USB identity

```
04b4:8613  bare Cypress FX2, no personality
0f05:f235  personality loaded, firmware not yet
0f05:f135  firmware loaded -- this is the working state
```

`tools/pakon_load.py` holds the authoritative tables.

---

## 6. What we captured from the vendor, and how

USB sniffing failed on **every** route: SnoopyPro's filter driver wedged the
Windows USB stack twice and produced zero packets; USBlyzer's vendor is gone;
and macOS exposes no USB capture interface at all, so Wireshark on the host
cannot see what Parallels passes through.

**The working method is API Monitor v2r13 inside `PSI.exe`.** `tlx.dll` is an
in-process COM server, so every command is built and dispatched in `PSI.exe`'s
own address space and is reachable from user mode — no kernel driver, nothing
that can wedge the stack. Hook `DeviceIoControl` for register traffic,
`CreateFileA`/`CreateFileW` for the data flow.

`.apmx86` format: text banner, magic `RBAPM`, then a **plain ZIP at offset
0xda**. Buffers are in `process/0/data`.

Captures live in `~/pakon-findings/incoming/` (`apmcap/`, `cap2/`).

### What came out of it

* `docs/55` — the real CCD bring-up. **Supersedes `docs/42`'s ordering.**
* `docs/56` — the full colour data flow, 218 files.
* `docs/59` — the complete lamp/LED sequence.

---

## 7. The lamp, if you need light

`docs/59`. The port's LEDs never lit because `0x80` is an **enable, not a
brightness**, and `0x81`/`0x82` — the actual drive — were never written with
real values. They are write-only, so they cannot be read back either.

This unit's captured values (wire order is **`B, Ir, R, –, G`**, not RGB):

```
0x81 levels   B=7 Ir=0 R=3 G=11
0x82 PWM      calibration B=156 R=654 G=374 / scan B=804 R=912 G=938, N=982
```

`tools/lamp_replay_vendor.py` replays the sequence. Dry run by default; refuses
anything outside the firmware clamps; programs drive before enable.

**Only `0x81` and `0x82` are per-unit** — everything else in the sequence is
protocol or a firmware constant and transfers to any F-135 Plus. Use
`--levels` / `--duty` for a different scanner. It does *not* transfer to legacy
`0x20`/`0x24` boards, which run a different clock.

Unresolved and interesting: green is taken from the registry **verbatim** in
both drive sets while R and B are not, twice, on independent value sets. Reads
as green-reference white balance with R/B trimmed live against the CCD. If so,
a correct port runs the calibration search rather than replaying stored values.

---

## 8. Traps that cost real time

Every one of these produced a confident wrong conclusion before being caught.

* **A capture that looks empty probably is not.** `docs/56` was first reported
  as nearly empty because the decoder only walked UTF-16 while the paths were
  ANSI. Search **both** encodings.
* **`docs/55` under-counted its own capture** — the regex `02 <len> <board> 03`
  matched only 3-byte-payload packets, hiding the entire light board. 46
  reported, 126 actual. Frame packets properly:
  `<type> <pktlen> <addr> <paylen> <reg> <payload>`, `pktlen == paylen + 3`.
* **PE section headers: `PointerToRawData` is at offset 20, not 16.** Getting
  this wrong produced a spurious "these are different builds" conclusion that
  had to be withdrawn.
* **"Decodes cleanly" is not "is valid".** A carved image decoded at full
  height and was scrambled noise. Use a row-vs-column discontinuity ratio to
  detect mis-carves before drawing conclusions from statistics.
* **`TLB.tbl.txt` is alphabetical.** An `id = line − 4` symbolication scheme was
  derived from it and is invalid. Four names were withdrawn.
* **Do not shallow-clone this repo.** `--depth 50` breaks pushes with
  `missing blob object`. Full clone.
* **CCD A/D offsets are sign-magnitude**, sign in bit 8 — not two's complement.
  `0x011D` = −29.

---

## 9. Environment

* **Scanner** connects to macOS directly (libusb/pyusb) or passes through to the
  XP Parallels VM for PSI. Not both.
* **XP VM** runs the vendor stack: PSI, the F-X35 COM Server, API Monitor.
* **A file drop** for moving things between host and VM:
  `python3 ~/pakon-findings/dropbox_server.py` → `http://10.211.55.2:8000/`,
  saving into `~/pakon-findings/incoming/`. Files to hand *to* the VM go in
  `~/pakon-findings/serve/` → port 8001.
* **libusb**: if enumeration returns 0 devices, copy the bundled dylib to
  `/usr/local/lib/libusb-1.0.dylib`.
* **`~/pakon-findings/`** is deliberately outside git — scratch, captures,
  scripts. `~/pakon-mac` is the public repo; this one is private.

---

## 10. Reading order

1. `docs/58` — the SRA gap. The live hypothesis.
2. `docs/54` — how the washout was measured, and why it is a port artefact.
3. `docs/56` — what the colour engine actually runs.
4. `docs/57` — how to get an execution trace, when someone has a 32-bit
   XP-capable DynamoRIO.
5. `docs/55` + `docs/59` — the hardware sequences, both captured ground truth.
6. `docs/17` — the EEPROM repair, so you do not undo it.
