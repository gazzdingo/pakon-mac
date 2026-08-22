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

## THE PART THAT MAKES IT BYTE-FOR-BYTE — do not skip

The hook capture gives the internal values. To *certify* byte-for-byte we
also need the vendor's own input and output for the SAME frames:

6. In PSI, **export both the RAW and the finished TIFF** for the frames you
   just scanned — same scan, same session. (These are the `raw*.tif` /
   `*.tif` pairs.) The raw is the pipeline's input; the finished TIFF is the
   target. Pairing them from the SAME scan is essential — a trace matched to
   TIFFs from a different scan is the §162 error that has cost this project
   before.

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
