# Capture architecture and whole-roll scanning — 2026-08-06

Two questions: what language for the capture path, and how a whole roll actually
gets scanned. The second answers the first.

## 1. The Pakon is a line-scan scanner — this changes everything

It does not photograph frames. Film moves continuously past a fixed sensor line,
the CCD clocks out one line at a time, and **frame boundaries are found in
software afterwards**. That is why the machine is fast and why it has no
frame-registration mechanism.

So "scan a whole roll" is **one continuous capture**, not 36 acquisitions:

```
lamp on -> motor runs at calibrated speed -> EP 0x86 streams continuously
        -> one long strip in memory/disk -> find frames offline -> colour -> TIFFs
```

The registry gives the calibrated transport speeds per DPI base, which is
exactly the parameter this loop needs:

```
MotorSpeedPlus / _Ir     DpiBase4   5917 / 4850
                         DpiBase8  11467 / 7580
                         DpiBase16 25802 / 19335
MotorAdjust 1000    MotorAdjustDrag 1008
```

**Consequence for the architecture:** the real-time constraint applies to
*nothing except moving bytes to disk*. Framing, colour and file writing all
happen afterwards, unconstrained. That decoupling is the whole design.

Rough size: at ~30 MB/s, a roll taking 60 s is ~1.8 GB of raw strip. Large but
entirely ordinary to write and re-read.

## 2. Language — measure before rewriting

**30 MB/s is not fast.** USB 2.0 high-speed tops out at 60 MB/s; this is half of
that. The bottleneck is not language execution speed, it is **whether transfers
are queued asynchronously**.

With libusb's async API and a ring of pre-submitted transfers, the kernel keeps
the pipe full and the host language only services completion callbacks. At
30 MB/s with 64 KB buffers that is **~460 callbacks/second** — trivial for
Python. The actual byte copying happens inside libusb, in C, either way.

So the first move is **not** a rewrite:

> Convert the existing Python capture from synchronous `dev.read()` to libusb
> **async** transfers with 8–16 pre-submitted buffers, write straight to disk,
> and measure sustained rate and drop count over 60 seconds.

If that holds, there is no language question. Synchronous single-buffer reads
are the likely culprit, not Python.

### If a native core is genuinely needed

Ranked for *this* job:

| | Verdict |
|---|---|
| **Rust + `nusb`** | **Best choice.** `nusb` is pure Rust, async-native, no libusb C dependency, works on macOS arm64. Single static binary, no memory-management bugs in the transfer ring — which is exactly where this class of code goes wrong. |
| Rust + `rusb` | Fine, but binds libusb, so you inherit the C dependency you were trying to bundle anyway. |
| C | Smallest and most direct, but a hand-rolled ring of async transfers in C is precisely the code that produces silent overruns. |
| Swift | Reasonable if a Mac GUI is wanted later, but USB support means C interop with libusb regardless, so it buys little for the capture core specifically. |
| Go | Workable; cgo friction for libusb and GC pauses are a small real-time risk. No advantage here. |

### What must NOT be rewritten

**The colour pipeline stays in Python.** `tools/pakon_color.py` reproduces the
vendor's density LUT to within 0.000050 across all 16,384 entries. That accuracy
is verified and hard-won; porting it to another language risks it for no gain,
since it runs offline with no real-time constraint.

The right split:

```
capture core   (Python-async, or Rust if measured necessary)
               USB -> ring buffer -> raw strip on disk.  Dumb and fast.
orchestration  Python.  Lamp, motor, CCD, sequencing.
framing        Python.  Offline, on the saved strip.
colour         Python.  Already done and verified.
```

## 3. The whole-roll sequence

Steps marked **[open]** are not yet solved.

1. Load FX2 firmware — `tools/pakon_load.py`, **done**
2. Probe both PIC boards — `tools/probe_picm_alive.py`, **done**
3. Programme CCD gain/offset for the chosen mode — now known per mode from the
   registry (`Gain_R/G/B` 13/13/13, `Offset_R/G/B` −18/−26/−20) — **[open]**
4. Lamp on — **[open]**, calibration recovered, encoding pending
5. Detect film present — `FilmPresent` exists in TLB.dll strings — **[open]**
6. Start acquisition (CCD register `0x82` bit 0) and begin streaming EP 0x86 —
   **[open]**
7. Start transport at the calibrated `MotorSpeedPlus` for the DPI base
   (`02 05 44 02 A5 lo hi`, then `04 03 44 00 A0`) — **primitives done**
8. Stream to disk until the roll ends — **[open]**, this is the throughput task
9. Stop transport (`04 03 44 00 A2`) and lamp off — **primitives done**
10. Offline: recover line length and channel order, split the strip into frames
    — **[open]**
11. Offline: colour-correct each frame → 16-bit TIFF — **done**

Steps 1, 2, 7, 9 and 11 already work. The gating unknowns are 4 (lamp), 6/8
(acquisition and sustained capture) and 10 (framing).

## 4. Order of attack

1. **Characterise EP 0x86** — free, read-only, and it may show the stream is
   already structured (see `docs/42` §B).
2. **Async capture benchmark** — 60 s sustained, count drops. Settles the
   language question with data instead of opinion.
3. **Lamp**, once the encoding is confirmed safe.
4. **Framing**, which can be developed entirely offline against a saved strip
   and needs no hardware once one good capture exists.

Note that 4 needs the scanner exactly once. After a single successful strip
capture, most remaining work is offline.
