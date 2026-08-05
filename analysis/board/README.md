# Board imagery

Frames extracted from `~/Downloads/PXL_20260803_155551949.mp4`
(main/motor board #125430 REV C), 2x lanczos upscale + unsharp.

## LIMITATION — READ THIS

**The source video is only 512x288.** Upscaling adds no real detail. These
frames are adequate for LAYOUT — where parts sit, relative positions, which
header is where — but they are NOT sufficient to read chip markings for a
full bill of materials.

Chips identified so far were read from higher-resolution photos taken
separately, or inferred from firmware:

| Ref | Part | How identified |
|---|---|---|
| U6  | CY7C68013A-128AXC (Cypress FX2) | package marking, legible photo |
| U11 | PIC18F452, 44-TQFP, relabelled `125507A 2208` | firmware declares `;PIC18F452`; timing constants confirm 39.32MHz HSPLL |
| ?   | Xilinx Spartan XC3S150E | package marking |

**To complete the BOM we need new photographs**: each board, well lit, in
focus, close enough that package markings are legible. Phone macro or a
camera at ~10-15cm. Several overlapping shots per board beat one wide shot.
