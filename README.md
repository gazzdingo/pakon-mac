# pakon-mac

> ⚠️ **Work in Progress** — this project is under active development. Nothing
> here is production-ready. APIs, protocols, and tools may change without notice.

Native macOS support for Kodak/Pakon F-135, F-235 and F-335 film scanners.

These scanners shipped in 2002–2007 with 32-bit Windows XP drivers and have no
vendor support on any modern OS. This project documents the hardware interface
and reimplements the host side in userspace on macOS.

## Status

**Active development / research phase.** See [`docs/06-roadmap.md`](docs/06-roadmap.md)
for where things currently stand.

## Why this is feasible

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

## Provenance and confidence

Every claim in these docs is tagged:

- **[VERIFIED]** — read directly out of a vendor binary or data file in this
  repo's source material. Reproducible with the scripts in `tools/`.
- **[INFERRED]** — deduced from naming, structure, or cross-referencing two
  sources. Probably right, not proven.
- **[EXTERNAL]** — from third-party reverse engineering (see credits). Not
  independently confirmed here.
- **[UNKNOWN]** — called out explicitly so gaps aren't mistaken for coverage.

Nothing here has been tested against real hardware yet. Treat all of it as a
map, not a guarantee.

## Credits

Kyle Kaufman's [Pakon reverse engineering
write-up](https://ktkaufman03.github.io/blog/2022/09/04/pakon-reverse-engineering/)
established the command packet framing, the address enum, and the identification
of `F235Ldr.sys` as Anchor Chips' ezloader. Facts taken from it are tagged
**[EXTERNAL]**.

## Legal Disclaimer

**This project is not affiliated with, endorsed by, or in any way connected to
Kodak, Eastman Kodak Company, Pakon Inc., or any of their successors, assigns,
or affiliates.** Kodak, Pakon, and related product names are trademarks of their
respective owners. Use of these names is purely for descriptive purposes to
identify the hardware this software is designed to interoperate with.

This software is provided **"as is", without warranty of any kind**, express or
implied, including but not limited to the warranties of merchantability, fitness
for a particular purpose, and non-infringement. In no event shall the author or
contributors be liable for any claim, damages, or other liability — whether in
an action of contract, tort, or otherwise — arising from, out of, or in
connection with this software or the use of it. **Use at your own risk.**

This includes but is not limited to: damage to scanning hardware, loss of film
or photographs, data loss, system instability, or any other direct, indirect,
incidental, special, exemplary, or consequential damages.

Reverse engineering conducted for interoperability purposes under applicable
law — enabling hardware you own to work on an operating system its vendor
abandoned. No vendor binaries or firmware images are redistributed in this
repository; the documentation describes interfaces only, and the tools operate
on files you supply from your own licensed copy of the vendor distribution.
