# The one scan that closes the colour pipeline

This single scan captures — together, correctly paired, in one roll — every
gap that is currently blocking byte-for-byte:

- **the per-frame statistics vector** (`sba_measure`, object `+0x3c`) — the
  input the per-frame balance is computed from. Without it, the balance
  triple can only be *borrowed* from a capture, not *computed*.
- **δ's writer** (`apb_scene`, entry+exit on `scene+0x4b6`) — settles which
  of three calls applies the per-frame shift.
- **framing** — positions (`framing_slots`) and the vendor's own 8-bit
  per-line array (`framing_lines`).

Build (v51), selftest-passed:
```
hookdll_v51.dll        b311c6f4b05a45e2b741f912efb59c80
injector_v51.exe       db503b491e9b109b2c691d6482f9de52
hooks_v51_everything.cfg   (validated: 31 hooks, incl. sba_measure,
                            analyze_post_balance, all three framing)
```
**Hash what you copy** — PE timestamps make these non-reproducible.

## On the XP box

1. Copy the three files. Rename `hooks_v51_everything.cfg` → `hooks.cfg`,
   next to `hookdll_v51.dll`.
2. Start PSI, NOT mid-scan.
3. `injector_v51.exe PSI.exe hookdll_v51.dll`
4. Confirm `hook_installed` lines appear (should be ~31). Let PSI sit idle a
   moment to confirm it stays responsive.
5. **Scan one roll.** Lamp off when done.

## What actually certifies byte-for-byte (corrected)

The PSI-exported "raw" is NOT the pipeline's true input — it is an 8-bit
export, already downsampled from the real 14-bit sensor data. So a raw+TIFF
pair is NOT an input->output byte reference. Do not treat it as one.

The real ground truth is the HOOK data: the DLL's own internal buffers on the
true sensor input. Two things it gives:

* **Correctness (the main prize, no export needed):** the sba_measure vector,
  apb_scene delta, and framing arrays let us PORT and verify those stages
  bit-exact against the real DLL. Porting them closes the blue, provably
  matching the vendor's arithmetic.
* **A partial true byte test:** the captured PIXEL PLANES (poly_input_r/
  poly_output_r, scene brackets, lut_src/dst) are the vendor's real internal
  pixels. Feed our pipeline the captured input plane, compare to the captured
  output plane — byte-for-byte on real data, no 8-bit export involved. Capped
  per §189.5, so this covers a few frames, not the whole roll.

6. Optionally export the finished TIFFs too, but ONLY as a visual sanity
   reference — they are 8-bit and cannot certify byte-identity. The hook
   pixel planes are what a byte test uses.

## Getting it back

Upload the `live_hooks_<timestamp>.jsonl` AND the raw+TIFF exports to the
drop. **Tell me the .jsonl size** — I compare against Content-Length before
reading a byte (§178.1: a whole analysis was once drawn from a capture still
uploading).

Expect the .jsonl ~110–180 MB. The framing hooks add little (they fire a
handful of times, not per line).

## What each piece unlocks, once the capture is in

- vector + balance triple, same frame → **port the per-frame balance**
  (the R−B deficit / the blue).
- apb_scene entry vs exit → **which call writes δ** → port it.
- framing_slots + framing_lines → **wire framing** and close FRAMING_PORTED.
- raw+TIFF same-scan pair → the FIRST real byte-for-byte measurement; every
  number until now has been on an 8-bit export at a guessed scale.
