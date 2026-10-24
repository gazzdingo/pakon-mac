# libpakon

A scanner driver and colour pipeline for the Kodak Pakon F-135 Plus film scanner (also F-235 / F-335 families, beta), written in C99.
It talks to the scanner over USB (libusb), decodes the scan lines, finds the frames and renders finished pictures.

**No Kodak files are in this repository.** The driver needs your own copy of the Pakon Software Interface (PSI) 3.0.4.27 install
(firmware images and colour data). `pakon vendor import <folder>` verifies them by SHA-256 and copies what it needs into a store of its own.

What is here: `core/` (library, `pakon` command line, tests), `tools/` (the roll exporter and renderer the tests use, the vendor manifest generator).

## Build

    cmake -S core -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j && ctest --test-dir build

Needs a C99 compiler, CMake 3.16 and (for the scanner) libusb 1.0 (`brew install libusb pkg-config`). The build uses `-Werror`.

## What the public tree leaves out

- **Digital ICE.** Its 88 per-pixel routines are generated from Kodak's code and are not published. The public build has `PK_WITH_ICE=OFF`:
  `pk_ice_available()` returns 0, `pk_ice_apply()` returns `PK_E_UNSUPPORTED`, and a frontend should say that dust and scratch removal is not available.
- **Colour.** The colour pipeline reads tables that were extracted from the PSI install (`vendor/derived`: KCMS tables and `imau_tables`).
  There is no extractor in this tree yet, so colour is unavailable until one exists. Scanner control, scan decode and framing need only the PSI install.
- **Kodak-match tests.** They compare the code with output recorded from Kodak's own software, and those vectors are not published.
  Each such test reports itself as skipped (exit 77) when its vectors, the PSI install or `vendor/derived` are missing.
- Reverse-engineering notes and lab tooling stay private.

## Licence

No licence has been chosen yet. Until one is added, all rights are reserved.
