# 05 — Source Material

What the vendor distribution contains and where the useful parts live. Nothing
here is redistributed in this repository — these are notes for locating things
in your own copy.

## The distribution

The starting point was a folder named `Pakon Update 2` (164 MB, 756 files) —
the Pakon PSI F-X35 installer, product version 3.0.4.27, dated 2007.

Two independent trees, and **the second is far more valuable**:

```
Pakon Update 2/
├── Pakon PSI F-X35.msi          the end-user scanning application
├── PknInit.hex                  EZ-USB bootstrap firmware
├── F235usb2.inf                 driver INF -- the VID/PID Rosetta Stone
├── F235Ldr.sys / F235Lib.sys / F135usb2.sys / F235usb2.sys / FX35usb2.sys
├── program files/Pakon/
│   ├── PSI/                     the PSI application
│   └── IQ/                      IQueue III
└── fx35install/                 ◄── THE FX35 SDK. Look here first.
    ├── Pakon5.hex  Pakon7.hex  Pakon8.hex
    └── program files/Pakon/
        ├── F-X35 COM SERVER/    tlx.dll, TLA/TLB/TLC.dll, PakonIMAu.dll,
        │   ├── Config/
        │   │   ├── Firmware/            58 PIC firmware images + readmes
        │   │   └── ColorCorrection/     ICC profiles, LUTs, film database
        │   └── TLXClientDemo.exe        SDK sample client
        ├── FirmwareLoader/
        ├── PTS/                 Interop.TLXLib.dll  ◄── the API contract
        ├── F-135/ F-235/ F-335/ per-model driver packages
        └── Scanner Documentation/  UserManualF135/F235/F335.pdf
```

## The highest-value files

| File | Why it matters |
|---|---|
| `F235usb2.inf` | Complete VID/PID table, unloaded→loaded mapping, and the registry map from device revision to firmware image. Everything in [`01-usb-layer.md`](01-usb-layer.md) comes from here. |
| `Pakon7.hex` | The F-135 firmware. Its embedded USB descriptors gave the endpoint map before any hardware was attached. |
| `PTS/Interop.TLXLib.dll` | .NET COM interop assembly — preserves the **entire type library**. 1,139 identifiers: every operation, parameter and error code. This is the vendor's own API contract, not a reconstruction. |
| `F-X35 COM SERVER/TLB.dll` | **The F-135 client library.** Contains the command packet construction and the `"Type %x, PktLen %x, Address %x"` format string. Primary target for protocol work. |
| `F-X35 COM SERVER/TLA.dll` | Contains the imaging pipeline — the density LUT generator and the MMX colour kernel. Source of the exact colour maths. |
| `Config/ColorCorrection/` | The colour science, shipped as **data**: ICC v2 profiles, the 16,384-entry density LUT, the 3×4 negative matrix, and the film-product table. |
| `Config/Firmware/Readme*.txt` | Documents the PIC board families and hardware revisions. Independently corroborates the packet address enum. |
| `Scanner Documentation/*.pdf` | Official user manuals for all three models. |

`TLA.dll` / `TLB.dll` / `TLC.dll` are the client libraries for the **F-235**,
**F-135** and **F-335** respectively. They share most routines, so a reading
taken from one can be corroborated against the other two — useful when a
disassembly is ambiguous.

## Third-party material

**[ktkaufman03/FX35](https://github.com/ktkaufman03/FX35)** — full source for
64-bit Windows replacement drivers, by the author of the reverse-engineering
write-up. Contains `FX35Loader/Loader.c` with the **embedded stage-1 loader**
that makes firmware loading possible at all, and `FX35USB/driver/` with the
IOCTL definitions and the `RING_TAIL` scan-buffer structure.

> The upstream repository ships **no LICENSE file**, so nothing from it is
> redistributed here. `vendor/` is gitignored, and `tools/extract_stage1.py`
> regenerates what is needed from your own clone.

**[Kai Kaufman's write-up](https://ktkaufman03.github.io/blog/2022/09/04/pakon-reverse-engineering/)**
— established the packet framing and the address enum, and identified
`F235Ldr.sys` as Anchor's ezloader. Note the article does not link the source
repository; it has to be found separately.

Other community projects (client software using the COM API rather than the
wire protocol): `plonsker/pakon-scanning-software`, `eatfrog/PakonClient`,
`nunocruz/pakon_135plus`, `sgharvey/pakon-tlx-addons`.

## Reproducing the analysis

Tools used, all available on macOS:

```sh
brew install radare2 libusb sdcc wireshark
python3 -m pip install pyusb
```

- `radare2` — PE disassembly of the 32-bit x86 DLLs and `.sys` drivers
- `sdcc` — 8051 compiler, used to build the hardware probe in
  [`02-firmware.md`](02-firmware.md)
- `libusb` + `pyusb` — all device communication
- `mdbtools` — for `mrd.mdb` (turned out to be an empty stub)

Things that do **not** work on Apple Silicon, so don't waste time on them:

- **Windows VM with USB passthrough.** Parallels on an M-series Mac runs only
  Windows 11 ARM, which cannot load 32-bit x86 kernel drivers. A USB capture of
  the original software needs a physical x86 PC.
- **macOS USB packet capture.** Apple removed the `XHC` pcap taps on Apple
  Silicon; `dumpcap -D` lists no USB interface.

## A note on the `.hex` files

There are two completely separate firmware layers, and conflating them is the
easiest way to get lost:

- `PknInit.hex`, `Pakon5/7/8.hex` — for the **EZ-USB bridge**, loaded over USB
  at every power-on.
- `Config/Firmware/*.HEX` — for the scanner's **internal PIC boards**, pushed
  over the command protocol, and only when deliberately updating.

See [`02-firmware.md`](02-firmware.md). Do not flash the second kind.
