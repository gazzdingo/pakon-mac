<p align="center">
  <img src="https://github.com/user-attachments/assets/f9b63009-a7c3-4c32-984e-52093fa22add" alt="Pakon Mac" width="240">
</p>
<p align="center">
  <img width="400" alt="image" src="https://github.com/user-attachments/assets/6f061022-3565-4f91-8b8a-c39bf5877b49" />
</p>


<h2 align="center" >⚠️ WARNING WIP⚠️</h2>
The application and some of the image processing pipelines are **NOT working 100% yet**. This repository is highly experimental and in active development. Please do not run this or attempt to interface with your scanner unless you know exactly what you are doing.

**Colour is currently in progress.** See
[`docs/74-washed-out-tone-chain-architecture-and-dmin-methodology.md`](docs/74-washed-out-tone-chain-architecture-and-dmin-methodology.md)
for the full, running, evidence-cited investigation log — the summary below
is a snapshot, that doc is the source of truth.

**Verified against the real vendor DLL and/or real hardware, not assumed:**
- The six-subsystem F-135 colour-negative tone chain (`analyzeAutoTone`:
  cna/dra/toneHelper/contrast/ast/citras) — bit-exact via live Unicorn
  emulation of the real `PakonIMAu.dll`, including at real full-frame
  scale, not just synthetic test vectors.
- The ICC transform, AFE gain register, the F-135 raw→RPD polynomial
  conversion (`PolyPixel`), and the SBA balance-shift math — each
  independently bit-exact under the same live-execution standard.
- `fpo` (opening RGB) — confirmed via a live hook capture on the real
  physical scanner that this unit genuinely uses the generic stock value,
  not a per-unit correction.
- The lamp duty sequence (open-gate vs. with-film, the real per-channel
  PWM values) — matches a real captured vendor USB trace to six figures.
- The six-subsystem call order and shared internal state — confirmed live
  via hooking the real DLLs during an actual scan on the real hardware,
  not just read from disassembly.

**Known-open, real problems, not yet solved:**
- Even with all of the above independently verified correct, the port's
  rendered output still shows a real, uniform brightness offset (measured
  directly against the vendor's own PSI software output on the same
  physical film) whose root cause is not yet found. 14+ specific
  hypotheses have been checked and ruled out with real evidence; the
  investigation is ongoing.
- The verified tone chain above is **not yet wired into the production Go
  render path** (`tools/ansel/pipeline/`) — it still uses
  `ShastaToneRpd`, an explicit placeholder (`AutoTonePorted = false`).
  The app currently defaults to the Python engine, which does use the
  verified chain, as an interim measure.
- Black & white film scanning is currently broken: it uses the same lamp
  exposure as colour negative, which is tuned to compensate for an orange
  mask B&W film doesn't have, driving two of three colour channels into
  real sensor clipping. See
  [`docs/75-bw-scan-time-duty-mismatch-sensor-ceiling-clipping.md`](docs/75-bw-scan-time-duty-mismatch-sensor-ceiling-clipping.md).
- F-235 and F-335 support exists in the code but has not been verified
  against real F-235/F-335 hardware or vendor DLLs — real hardware access
  this project has had so far is to one F-135 unit only. Treat F-235/F-335
  behavior as unverified until tested against real units.

**The Electron app UI is not finished.** It exists to exercise the scan and
decode pipeline end to end, not as a polished product yet — expect rough
edges, placeholder screens, and controls that don't do anything yet.

Native macOS support for Kodak/Pakon F-135, F-235 and F-335 film scanners.

These scanners shipped in 2002–2007 with 32-bit Windows XP drivers and have no
vendor support on any modern OS. This project documents the hardware interface
and reimplements the host side in userspace on macOS.

## Status

Active development. See [`docs/06-roadmap.md`](docs/06-roadmap.md) for where things stand.

## Architecture & Pipelines

This project includes two separate imaging pipelines for processing the raw scanner data:
1. **Python Pipeline**: The original research and reference implementation (`tools/pakon_render.py`). Uses NumPy for processing.
2. **Go Pipeline**: The newer, production-oriented implementation (`tools/ansel/pipeline/`). This is significantly faster than the Python version due to being a compiled language with better multi-threading and memory management for heavy image operations.

## Hardware Backups & Repair (`backups/`)

This repository contains raw hardware dumps from a Pakon scanner in the `backups/` folder. These are preserved here for anyone attempting to repair a bricked scanner:
- **`eeprom-i2c/`**: Dumps of the I2C EEPROM chips. `eeprom_52.bin` contains the irreplaceable per-unit optical/motor calibration data, while `eeprom_51.bin` holds the FX2 boot personality.
- **`u11-picl/`**: PIC18 firmware dumps of the U11 Light Control chip. Critically, this contains a real, un-patched Kodak factory bootloader.
- **`u34-picm/`**: PIC18 firmware dumps of the U34 Motor Control chip. 

*See the `README.md` inside each subfolder for exact memory maps, SHA256 checksums, and flashing notes.*

The Windows kernel drivers (`F235Ldr.sys`, `F235Lib.sys`, `F135usb2.sys`) are
generic USB plumbing — a firmware loader and a bulk-pipe passthrough. None of
the scanner logic lives in kernel space; it all lives in userspace DLLs
(`tlx.dll` → `TLA/TLB/TLC.dll`) that push packets through a single
`DeviceIoControl`.

That means **macOS needs no kernel extension and no DriverKit driver.**
Everything can be done from userspace with libusb.

## Documentation

| Doc | Contents |
|---|---|
| [`00-overview.md`](docs/00-overview.md) | System architecture, Windows stack, porting strategy |
| [`01-usb-layer.md`](docs/01-usb-layer.md) | VID/PID table, enumeration states, endpoint map |
| [`02-firmware.md`](docs/02-firmware.md) | EZ-USB firmware load, scanner sub-processor firmware |
| [`03-protocol.md`](docs/03-protocol.md) | Command packet format, addresses, status codes |
| [`04-api-surface.md`](docs/04-api-surface.md) | The TLX API — operations, parameters, error codes |
| [`05-source-material.md`](docs/05-source-material.md) | What's in the vendor distribution and where |
| [`06-roadmap.md`](docs/06-roadmap.md) | Implementation plan, open questions, how to help |
| [`74-washed-out-tone-chain-architecture-and-dmin-methodology.md`](docs/74-washed-out-tone-chain-architecture-and-dmin-methodology.md) | The colour pipeline's own running investigation log — what's verified against the real vendor DLL/hardware, what's still open |
| [`75-bw-scan-time-duty-mismatch-sensor-ceiling-clipping.md`](docs/75-bw-scan-time-duty-mismatch-sensor-ceiling-clipping.md) | Why black & white film scanning currently fails, and what fixing it needs |

## Provenance and confidence

Every claim in these docs is tagged:

- **[VERIFIED]** — read directly out of a vendor binary or data file in this
  repo's source material. Reproducible with the scripts in `tools/`.
- **[INFERRED]** — deduced from naming, structure, or cross-referencing two
  sources. Probably right, not proven.
- **[EXTERNAL]** — from third-party reverse engineering (see credits). Not
  independently confirmed here.
- **[UNKNOWN]** — called out explicitly so gaps aren't mistaken for coverage.

This tagging describes the *hardware-interface* documentation
(`docs/00`-`docs/06`) specifically. The colour pipeline is held to a
stricter, separate standard — see "Colour is currently in progress" above
and `docs/74`/`docs/75` — where claims are verified either by live Unicorn
emulation of the real vendor DLL, or by hooking/capturing the real DLL
running on real physical hardware, and are labeled accordingly rather than
tagged with this scheme. Real hardware (one physical F-135 unit) has been
used extensively for calibration, wire-protocol capture, and live DLL
hooking; treat anything not explicitly described as hardware-verified
above as a map, not a guarantee.

## Credits

Kyle Kaufman's [Pakon reverse engineering
write-up](https://ktkaufman03.github.io/blog/2022/09/04/pakon-reverse-engineering/)
established the command packet framing, the address enum, and the identification
of `F235Ldr.sys` as Anchor Chips' ezloader. Facts taken from it are tagged
**[EXTERNAL]**.

## Legal

Not affiliated with Kodak, Eastman Kodak Company, or Pakon in any way.
Kodak and Pakon are trademarks of their respective owners.

This is hobby reverse engineering. I'm not responsible for damage to your
scanner, your film, or anything else. Use it at your own risk.
