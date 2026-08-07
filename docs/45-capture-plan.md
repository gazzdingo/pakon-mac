# Fixing capture, and the checklist for everything else

> **RESOLVED 2026-08-07. Suspect A was correct.** Removing the in-loop
> `FN_bDrvResetFifos` calls took a 60 s capture from 94.79 % intact / 960 losses
> to **100.00 % intact / 0 losses**, 694.8 MB at 11.6 MB/s sustained with plain
> synchronous reads. It was never a throughput problem — the capture loop was
> discarding the FPGA's buffer before every read. **Async libusb and the Rust
> core are unnecessary.** Every tear and shear in earlier frames came from this.

## 1. Capture — the plan

**Symptom:** ~5 % of words missing from ~13 s into a run. 960 non-6000 gaps in
`strip_cal.bin`, all after marker 10,505. These are the tears in the frames.

### Suspect A — my own FIFO resets. Check this FIRST, it is free.

Every capture loop I wrote calls `FN_bDrvResetFifos` **before every single
read**. The vendor resets **twice, both in `BeforeScan`** (`0x1002dcf5` and
`0x1002e0ee`) and then **never again for the whole strip** — `FN_iScanStrips`
just streams.

Resetting mid-stream discards whatever the FPGA has buffered since the last
read. That is a near-perfect explanation for periodic losses that begin once the
transport is up to speed and the FIFO starts actually filling between reads.

**Test:** re-run a capture with exactly two resets at the start and none in the
loop. If the non-6000 gap count collapses, this was never a throughput problem
and async is a nice-to-have rather than a fix. Ten minutes of work.

### Suspect B — synchronous single-buffer reads

Even without the resets, one blocking `dev.read()` at a time leaves the pipe
idle between calls. At ~30 MB/s the FPGA's FIFO overruns during that gap.

**Fix:** libusb **asynchronous** transfers with a ring of pre-submitted buffers.

* use `python-libusb1` (exposes `libusb_submit_transfer`), not `pyusb`, which
  has no usable async path
* submit **16 transfers of 256 KB** up front; resubmit each in its completion
  callback so the queue never empties
* callback does nothing but hand the buffer to a writer thread — no parsing, no
  numpy, no allocation on the hot path
* write to a preallocated file or `O_DIRECT`-ish sink; disk must sustain 30 MB/s
  (any SSD will)
* **instrument it**: count transfers, bytes, and any short/failed completions.
  Success is measured by the non-6000 gap count on the resulting file, not by
  "it looked fine"

**Acceptance test:** a 60 s run with **zero** non-6000 gaps, i.e. 100 % of sync
markers exactly 6000 words apart, versus today's 94.8 %.

### Fallback — a small Rust capture core

Only if Python cannot hold the rate after the above. `nusb` (pure Rust, async,
no libusb C dependency) writing to a ring buffer, Python keeping orchestration
and decode. **Do not start here** — measure first; 30 MB/s is half of USB 2.0
high-speed and the copying happens inside libusb either way.

### Order of work

1. remove the in-loop FIFO resets, re-capture, count gaps
2. if still lossy, async ring, re-capture, count gaps
3. if still lossy, Rust core
4. record the gap count for each attempt so the improvement is evidence, not
   impression

---

## 2. Checklist for the rest

### Capture
- [x] remove in-loop FIFO resets (Suspect A) — **this was the whole fix**
- [~] async libusb ring — **not needed**, sync reads hold 11.6 MB/s losslessly
- [x] gap-count instrumentation as the acceptance metric
- [x] sustained 60 s run with zero losses — 57,900 lines, 0 losses
- [ ] clean the film gate — there is a hair at column ~804 casting a 155 px shadow

### Decode
- [x] line layout: 6000 words, per-pixel RGB, `plane_k = line[k::3]`
- [x] sync on bit 0, accept only exact-6000 gaps
- [ ] frame splitting *(in flight, `ansel-color-v1`)*
- [ ] settle orientation against the vendor's frame-buffer indexing
- [ ] eliminate the residual band in loss-free regions

### Colour
- [ ] Ansel module from SBA/Shasta/FUGC dpi data *(in flight)*
- [ ] per-pixel dark table from a lamp-off capture
- [ ] per-pixel gain table from an empty-gate capture
- [ ] smear correction (per-line scalar, decayed)
- [ ] density LUT + 3×3 matrix via `tools/pakon_color.py`

### Calibration
- [ ] re-derive `Current_R/G/B` on this unit with the vendor's search from n=1
- [ ] capture proper dark and bright references (current ones are single 98 KB
      buffers — too short)
- [ ] read the physical serial; if 16275, the 2022 registry set is also ours

### Workflow
- [ ] one command: firmware → configure → lamp → transport → capture → decode → TIFF
- [ ] film-present detection (register `0x93`, analogue, needs thresholding)
- [ ] lamp-off on every exit path, including errors

### UI
- [ ] local web UI: pick DPI base and film type, scan, watch the strip build,
      review frames, export
- [ ] **do this after capture is clean** — a UI over a lossy capture path bakes
      the tears into every scan

### Housekeeping
- [x] `captures/` gitignored, repo private
- [ ] `docs/06-roadmap.md` still has the stale "lamp visually confirmed" row
- [ ] `tools/flash_picm.py:242` `read_block()` still the broken single-packet form
