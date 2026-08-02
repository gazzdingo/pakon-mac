# 02 — Firmware

There are **two entirely separate firmware layers**, loaded at different times by
different mechanisms. Conflating them is the most common way to get lost here.

| Layer | Target | Files | Loaded by | When |
|---|---|---|---|---|
| **1. USB bridge** | Cypress EZ-USB FX2 (8051) | `PknInit.hex`, `Pakon5/7/8.hex` | Host, over USB control transfers | Every power-on |
| **2. Scanner sub-processors** | PICL, PICM, DX, lamp, motor, CCD, APS | `Config/Firmware/*.HEX` (58 files) | Host, over the EP1 packet protocol | Only when updating |

---

## Layer 1 — EZ-USB bridge firmware

### Target chip — [VERIFIED]

`F235Ldr.sys` contains the string `Ezusb_StartDevice`, identifying it as
Cypress/Anchor's **ezusb** reference driver. The constant `0x00E600` — the FX2's
`CPUCS` register — appears 10× in the binary, including at file offset `0x0949`
as `push 0 / push 0xE600`, the argument pattern of the reference driver's
`Ezusb_DownloadTo8051(…, CPUCS, …)`.

The Anchor-era `CPUCS` address `0x7F92` appears once, consistent with residual
support for the older `0547:1002` AN2131 boards.

`F235Ldr.sys` reads its HEX from disk rather than embedding it — the driver
carries `FirmwareDirectory = \SystemRoot\System32\F235Firmware` and a registry
map `F235_AA05 → Pakon5.hex`, `F235_AA07 → Pakon7.hex`, `F235_AA08 →
Pakon8.hex`. That is why one loader serves every model. **[VERIFIED from INF]**

### Download procedure

This is the standard EZ-USB sequence, unchanged by Pakon:

```
1.  Hold 8051 in reset:
      bmRequestType = 0x40  (host→device, vendor, device)
      bRequest      = 0xA0
      wValue        = 0xE600      (CPUCS)
      wIndex        = 0x0000
      data          = { 0x01 }

2.  For each contiguous block of the HEX image:
      bmRequestType = 0x40
      bRequest      = 0xA0        (internal RAM)   ── see caveat below
      wValue        = target address
      wIndex        = 0x0000
      data          = up to 4096 bytes (use 1024 for safety)

3.  Release 8051 from reset:
      bmRequestType = 0x40
      bRequest      = 0xA0
      wValue        = 0xE600
      wIndex        = 0x0000
      data          = { 0x00 }

4.  Device disconnects and re-enumerates with its loaded VID/PID.
```

### Memory layout of the images — [VERIFIED]

Parsed with `tools/pakon_hex.py --segments`. All four images share an identical
three-region structure:

```
Pakon7.hex (F-135)  — 10,355 bytes across 11 segments

  0x0000-0x0002     3 B   reset vector (LJMP)
  0x0033-0x0035     3 B   ┐
  0x0043-0x0045     3 B   │ 8051 interrupt vectors
  0x004B-0x004D     3 B   │ (0x43 = EZ-USB USB interrupt)
  0x0053-0x0055     3 B   ┘
  0x1000-0x10BD   ~183 B  USB descriptors  ← device descriptor at exactly 0x1000
  0x2000-0x47AC  10157 B  main 8051 program
```

### Caveat: the image exceeds FX2 internal RAM — [UNKNOWN]

The FX2 (CY7C68013A) has **16 KB of internal RAM at `0x0000–0x3FFF`**. The main
code segment runs to `0x47AC` (`Pakon7`) / `0x492E` (`PknInit`) — past the end of
internal RAM.

Two possible explanations, not yet distinguished:

1. **External code memory on the Pakon USB board.** The reference ezusb driver
   uses request `0xA0` (`ANCHOR_LOAD_INTERNAL`) for internal RAM and `0xA3`
   (`ANCHOR_LOAD_EXTERNAL`) for external RAM. The INF's service names
   ("Gated Fifo Write Enable", "Rev E FX2") describe a custom FIFO board that
   plausibly carries external SRAM.
2. **A smaller-RAM FX2 variant with a two-stage load**, where `PknInit.hex`
   is a stage-1 loader that implements the `0xA3` handler.

**This must be resolved empirically before the loader can be trusted.** The
safe implementation is to send `0xA0` for addresses below `0x4000` and `0xA3`
at or above it, and to verify by reading back. `tools/pakon_fw.py` implements
exactly this with a `--split-at` flag so the boundary can be moved during
bring-up.

Getting this wrong is not dangerous — a failed download simply leaves the device
unenumerated, and a power cycle resets it. The FX2's RAM is volatile; nothing is
written permanently by this step.

---

## Layer 2 — scanner sub-processor firmware

58 Intel HEX images ship in
`F-X35 COM SERVER/Config/Firmware/`. These are **not** for the USB chip — they
are for the PIC microcontrollers inside the scanner, pushed over the EP1 packet
protocol to the addresses documented in [`03-protocol.md`](03-protocol.md).

### Naming scheme — [VERIFIED] from `ReadmeF135.txt`

Files are `XXvvff.HEX` where `XX` is the board, `vv` the **hardware** revision
and `ff` the **firmware** revision.

| Prefix | Board | Packet address |
|---|---|---|
| `PL` | PICL — light board controller | `AD_PICL` `0x20` **[EXTERNAL]** |
| `PM` | PICM — motor controller | `AD_PICM` `0x24` **[INFERRED]** |
| `NL` | **PICL Plus** — F-135 Plus/Hybrid light controller | `AD_PICL_PLUS` `0x40` **[EXTERNAL]** |
| `NM` | **PICM Plus** — F-135 Plus/Hybrid motor controller | `AD_PICM_PLUS` `0x44` **[EXTERNAL]** |
| `LQ`, `LP` | Lamp controller | — |
| `MD`, `MC` | Motor drive | — |
| `DX`, `DY` | DX code reader | — |
| `AP` | APS cartridge handler | — |
| `CD`, `CE` | CCD board | — |

The `NL`/`NM` ↔ `AD_*_PLUS` correspondence is strong independent corroboration
of Kaufman's address enum: the readme says `NL`/`NM` are the F-135 **Plus**
boards, and the enum has exactly two `_PLUS` addresses.

### For an F-135 Plus specifically — [VERIFIED]

From `ReadmeF135.txt`, hardware revisions and their PCB part numbers:

| `vv` | Hardware |
|---|---|
| `02` | F-135 Charlie / Pre-Production / Production (PCB 125039A) |
| `03` | F-135 **Plus**/Hybrid Production (PCB 125430A) |
| `04` | F-135 **Plus**/Hybrid Production (PCB 125430B) |
| `05` | F-135 **Plus**/Hybrid Production (PCB 125430C) |

> ⚠️ The readme warns in capitals: revisions `03`/`04`/`05` **DO NOT USE ON PCB
> #125039A**. The hardware revision digit must match the physical board. A
> mismatched flash is one of the few genuinely destructive operations available
> here.

Latest available for the Plus:

| Board | Newest file | Firmware rev notes |
|---|---|---|
| PICL Plus | `nl030A` / `nl040A` / `nl050A` | `0A` — "Initialize state machine to report film in scanner at powerup" |
| PICM Plus | `nm0306` / `nm0406` / `nm0506` | `06` — "Add F135 Plus/Hybrid support" |
| Lamp | `lq010C.hex` (2008-03-06) | newest file in the whole distribution |
| Motor | `md0006.hex` (2007-10-12) | |
| DX | `dx0211.HEX` | |

**Do not attempt Layer 2 flashing until Layer 1 and the protocol are working and
verified.** Reading the currently-installed versions is safe and is a good early
milestone; writing is not. The scanner already has working firmware — there is
no reason to touch it.

## Colour correction data — [VERIFIED]

`Config/ColorCorrection/` ships as plain data, not code:

```
_ClientColNegLut.txt   _ClientColNegMat.txt   defaults.ini
ColRevLut1.pf   ColRevLutS6.lut   romm.pf   rpd.pf   srgb.pf   unity.pf
cold_bw.pf   warm_bw_ld0_1_4-5.pf   sepia_ld0_9_22.pf
satminus03..15.pf   satplus03..15.pf
```

These are the vendor's negative-inversion matrices, LUTs and output profiles.
They are useful reference for an imaging pipeline but are **not required** —
raw linear output bypasses all of it. See
[`00-overview.md`](00-overview.md#the-imaging-pipeline-is-a-rewrite-not-a-port).
