# 08 — Pakon/Kodak Colour Profile Format (`.pf`, `.lut`)

Reverse-engineering notes for the files in
`fx35install/program files/Pakon/F-X35 COM SERVER/Config/ColorCorrection/`.

Every claim is tagged:

- **[VERIFIED]** — proven by parsing/diffing the actual files; reproducible with
  `tools/pakon_profile.py`.
- **[INFERRED]** — strong hypothesis consistent with all evidence, not directly proven.
- **[UNKNOWN]** — could not be determined.

---

## 1. Headline result

**[VERIFIED] The `.pf` files are standard ICC v2 colour profiles.** Not a
proprietary binary format. Every `.pf` file in the directory:

- begins with a big-endian `uint32` profile size that **exactly equals the file
  size** (all 17 files checked);
- has the ICC magic `acsp` at offset 36;
- has CMM signature `KCMS` at offset 4 (Kodak Color Management System) — except
  `srgb.pf` which has `Lino` (it is the stock HP/Lino sRGB IEC61966-2.1 profile);
- has ICC version `0x02100000` (v2.1) or `0x02200000` (v2.2) at offset 8;
- has a well-formed ICC tag table at offset 128 whose tags all parse with the
  standard ICC v2 type encodings (`mft2`, `curv`, `XYZ `, `desc`, `text`,
  `pseq`, `view`, `meas`, `sig `).

The `.pf` extension is Kodak's own naming for ICC profile files used by their
"KODAK Precision" CMS: `kodakcms.dll` (in `fx35install/System32/`) exports the
Precision Transform API (`PTCheckIn`, `PTEval`, `PTChain`, `PTGetItbl`,
`PTGetGtbl`, `PTGetOtbl`, …) and contains strings "Kodak Precision API error or
missing", "No KODAK PRECISION ProfileAPI Component". [VERIFIED strings/exports;
the `.pf` = "Precision file" reading of the extension is [INFERRED].]

Note how `PTGetItbl` / `PTGetGtbl` / `PTGetOtbl` map 1:1 onto the ICC `mft2`
structure (input tables / grid table / output tables) — the CMM's internal
model *is* the mft2 model.

**Practical consequence for the macOS port:** these files can be loaded by any
ICC-capable CMM (ColorSync, LittleCMS). No custom parser is required to *use*
them; `tools/pakon_profile.py` exists to *inspect* them.

## 2. File-by-file inventory [VERIFIED]

| File | Size | ICC class | In → PCS | Payload | desc string |
|---|---|---|---|---|---|
| `romm.pf` | 1004 | `mntr` | RGB → XYZ | matrix + gamma-1.8 curves | "KODAK Reference Output Medium Metric color space" |
| `srgb.pf` | 3144 | `mntr` | RGB → XYZ | matrix + 1024-pt curves | "sRGB IEC61966-2.1" (stock HP profile, CMM `Lino`) |
| `unity.pf` | 89532 | `abst` | Lab → Lab | mft2, grid 19³ | "Unity Profile" |
| `satplus03..15.pf` | 77948–77952 | `abst` | Lab → Lab | mft2, grid 17³ | "Saturation Boost N%" |
| `satminus03..15.pf` | 77952–77956 | `abst` | Lab → Lab | mft2, grid 17³ | "Saturation Boost −N%" |
| `cold_bw.pf` | 59128 | `abst` | Lab → Lab | mft2, grid 21³ | "Cold B&W Effect" |
| `warm_bw_ld0_1_4-5.pf` | 59488 | `abst` | Lab → Lab | mft2, grid 21³ | "PCS to PCS Effect, /home/brust/matlab/…" |
| `sepia_ld0_9_22.pf` | 59472 | `abst` | Lab → Lab | mft2, grid 21³ | "PCS to PCS Effect, /home/brust/matlab/…" |
| `ColRevLut1.pf` | 183048 | `link` | RGB → RGB | mft2, grid 31³ | "Pakon CMY to ROMM12 Profile" |
| `rpd.pf` | 216444 | `scnr` | RGB → Lab | mft2, grid 31³ | "RPD Rendering Profile Created by rpd_2_pcs_profile_gui" |

(The Matlab paths in the desc strings — `/home/brust/matlab/color_manage/…` —
show the effect profiles were authored on a Unix box in Matlab.)

The size variation inside the saturation series (77948/77952/77956) is entirely
due to `desc`/`dmdd` tag string lengths ("Saturation Boost 3%" vs "… −15%") plus
4-byte tag alignment; the `A2B0` payload is 77242 bytes in **all ten** files.
[VERIFIED by tag-table dump.]

## 3. mft2 (lut16Type) layout — the actual payload [VERIFIED]

All the big profiles carry their transform in a single `A2B0` tag of ICC type
`mft2` (lut16Type). Standard ICC v2 layout, all values **big-endian**:

```
off  size
  0   4   'mft2'
  4   4   reserved (0)
  8   1   input channel count  i   (3 in all files here)
  9   1   output channel count o   (3)
 10   1   CLUT grid points     g   (17/19/21/31 here)
 11   1   pad
 12  36   3×3 matrix, s15Fixed16   (identity in ALL files checked)
 48   2   n = input table entries  (2 … 4096 here)
 50   2   m = output table entries (2 … 4096 here)
 52   —   input tables:  i × n × uint16
  …   —   CLUT:          gⁱ × o × uint16   (index order: ch0 slowest, chN-1 fastest)
  …   —   output tables: o × m × uint16
```

For every file, `52 + 2(i·n + gⁱ·o + o·m)` **exactly equals** the declared tag
size [VERIFIED]:

| File | g | n_in | n_out | computed = declared |
|---|---|---|---|---|
| unity.pf | 19 | 3856 | 4096 | 88918 |
| sat*.pf | 17 | 3856 | 4096 | 77242 |
| cold_bw.pf | 21 | 256 | 256 | 58690 |
| warm_bw / sepia | 21 | 2 | 512 | 58702 |
| ColRevLut1.pf | 31 | 511 | 2 | 181876 |
| rpd.pf | 31 | 4096 | 256 | 204910 |

### 3.1 The Rosetta Stone: unity.pf is a bit-exact identity [VERIFIED]

The abstract profiles use the ICC v2 **legacy 16-bit Lab encoding**:
L in 0…0xFF00 (0xFF00 = L\*=100), a/b in 0…0xFFFF (0x8000 = 0).

- unity CLUT node (i,j,k) equals
  `( round(i/(g-1)·0xFF00), round(j/(g-1)·0xFFFF), round(k/(g-1)·0xFFFF) )`
  within **±1 LSB over all 19³ = 6859 nodes**.
- Output tables are exact linear ramps 0→65535 (max sampled error 0).
- Input tables for a/b are exact linear ramps. The **L input table** is a ramp
  with slope 65535/65280 (≈1.0039) that clips to 65535 at index 3840 of 3856
  (3840/3855 = 0.9961 = 0xFF00/0xFFFF): it re-expands the 0…0xFF00 L encoding
  to full scale before CLUT indexing. Mid-grey sanity check:
  `CLUT[9,9,9] = (32640, 32768, 32768)` = (0xFF00/2, 0x8000, 0x8000).

That is a complete, closed-form identity — the format is decoded.

### 3.2 Saturation profiles: chroma gain of exactly (1 ± N/100) [VERIFIED]

Byte-diffing `satplus03` … `satplus15`:

- header creation timestamp (offsets 24–35) differs — first differing byte is 35
  (seconds field);
- input tables and output tables are **byte-identical across all ten files and
  identical to unity.pf's**;
- L-channel CLUT entries are **identical** (0 differing L entries between ±3%
  and ±15%);
- only a/b CLUT entries differ.

At the CLUT node with input a\* offset +16383 (node j=12 of 17, L mid, b=0),
output a−0x8000 across the series:

| profile | a_out − 32768 | ratio to 16383 |
|---|---|---|
| satminus15 | +13926 | 0.8500 |
| satminus09 | +14909 | 0.9101 |
| satminus03 | +15892 | 0.9700 |
| satplus03 | +16874 | 1.0300 |
| satplus09 | +17857 | 1.0900 |
| satplus15 | +18840 | 1.1500 |

Interpolating to 0% gives 16383 = the input, exactly. A least-squares fit of
`(a,b)_out = k·(a,b)_in` over interior nodes gives k = 1.15000 for satplus15;
over *all* nodes the fit drops (1.089 for +15%) because boosted values clip at
the gamut/encoding edge. So: **sat profiles scale a\*,b\* by (1 ± N/100) around
neutral, leave L\* untouched, and clip at the encoding limits.**

Kodak then confirms this in the metadata: each sat profile's `dmdd` tag reads
e.g. `"saturation_profile; boostFactor: 1.15; by l505929"` (satplus15) /
`"boostFactor: 0.85"` (satminus15) — matching the measured gains exactly.
[VERIFIED]

### 3.3 ColRevLut1.pf — the colour-negative reversal [VERIFIED structure, INFERRED semantics]

Device-link RGB→RGB, desc "Pakon CMY to ROMM12 Profile", `pseq` lists two
KODA/ROMM entries. Structure [VERIFIED]:

- input tables: 511 entries, **different per channel**, strongly non-linear
  (film characteristic / density domain shaping);
- CLUT 31³, **decreasing** along the grey diagonal: 65535 → 96 (R), i.e. the
  negative-to-positive inversion lives in the CLUT;
- output tables: 2 entries (0, 65535) = identity.

[INFERRED] This is the "colour reversal" step of the scan pipeline: scanner CMY
densities in, ROMM12 RGB out (the class name `ColorMetricROMM12` appears in
`PakonIMAu.dll`, and `PIColorCorrectColRevPlanar` in TLA/TLB/TLC.dll).

### 3.4 rpd.pf — scanner RPD → PCS [VERIFIED structure]

Scanner-class profile, RGB→Lab, "RPD Rendering Profile" (RPD = Reference Print
Density, cf. `ColorMetricRPD12` in PakonIMAu.dll). mft2 grid 31³, input tables
4096 entries (12-bit domain), identical for all three channels: linear with
slope ≈1.365 clipping to 65535 around index 3000 — i.e. RPD code ~3000 of 4095
is mapped to full scale [VERIFIED numbers, interpretation INFERRED]. Output
tables 256-pt linear ramps.

`rpd.pf` also carries six **Kodak private tags** — see §5. Its `dmdd` tag reads
`"RPD_dls_3.pf {}, yellow5.pf {} cascaded by l628860"`: the profile is a cascade
(concatenation) of two source profiles, built with Kodak-internal tooling.
[VERIFIED string]

## 4. The non-ICC files

### 4.1 `ColRevLutS6.lut` [VERIFIED]

Plain ASCII, CRLF line endings, one integer per line, **4096 lines**, values
4…4095. Starts as the ramp `4·(i+1)`, goes non-linear, reaches 4095 at index
3498, then stays clamped (one benign wobble 4092→4091 at index 3360). It is a
12-bit → 12-bit 1D lookup table in text form. [INFERRED] Given the name
("Color Reversal LUT, S6" — the F235/F335 firmware family is "S6"), it is a
per-channel pre-LUT used in the reversal pipeline. Which stage consumes it was
not located in the binaries [UNKNOWN].

### 4.2 `_ClientColNegLut.txt`, `_ClientColNegMat.txt` [VERIFIED contents]

- `_ClientColNegMat.txt`: a 3×4 affine matrix as `coeff_R_C:` lines. Row
  offsets (column 3) are in 14-bit code values (−82.6, −586.9, −707.8).
- `_ClientColNegLut.txt`: 16384 lines `index<TAB>value`, index 0…16383, value
  float 16383.0 → 0.0, **strictly decreasing** — a 14-bit negative-inversion
  curve.

These describe the *client-side* colour-negative pipeline: a 3×4 crosstalk/
balance matrix plus a 14-bit inversion LUT. **Neither table appears inside any
`.pf`/`.lut` file** (byte search for the LUT as u16 LE/BE found nothing; the
`.pf` tables all have ≤4096 entries) [VERIFIED absence]. The leading `_` and
"Client" naming suggest they are runtime dumps written by the COM server for
the client, not static config [INFERRED]; no binary in the tree contains the
literal string `_ClientColNeg` (it is presumably built with a format string)
[VERIFIED absence of string].

Their value here is as documentation of *what the pipeline does numerically*:
14-bit (0…16383) linear-ish scanner data → 3×4 matrix → per-channel inversion
LUT.

## 5. Kodak private ICC tags [VERIFIED presence, UNKNOWN content]

The KCMS-authored profiles carry private tags:

- `K070`, type `ui08`, 10 bytes total = 8-byte type header + **2 bytes**:
  `06 06` in unity/sat/cold_bw, `04 06` in rpd.pf. Meaning [UNKNOWN]
  (plausibly in/out bit-depth or precision hints, but no evidence).
- `rpd.pf` only: `K113` (type `K003`, 307 B), `K120` (`K001`, 9436 B),
  `K121` (`K004`, 472 B), `K122` (`K002`, 108 B), `K123` (`K004`, 208 B).
  Bodies have Shannon entropy 6.2–7.8 bits/byte and decode to garbage as
  int16/int32/float32/float64 in either endianness. [UNKNOWN — likely
  compressed, encrypted, or non-tabular characterisation data. Not needed to
  evaluate the transform: the `A2B0` mft2 is complete on its own.]

## 6. What was NOT determined

- Semantics of `K070`/`K113`/`K120`–`K123` private tags (§5). The transforms
  work without them.
- Which pipeline stage consumes `ColRevLutS6.lut`, and the exact producer of
  the `_ClientColNeg*` text files.
- Why the abstract profiles use n_in = 3856 (= 16×241) input-table entries;
  the *values* are fully decoded (§3.1), only the choice of count is
  unexplained.
- Whether the scanner firmware itself consumes any of these files, or whether
  they are host-side only (the PT API in kodakcms.dll strongly suggests
  host-side only [INFERRED]).

## 7. Reproduction

```
python3 tools/pakon_profile.py info  <file.pf>       # header + tag table
python3 tools/pakon_profile.py dump  <file.pf>       # decode mft2/curv/matrix to text
python3 tools/pakon_profile.py csv   <file.pf> out/  # CSV: input tables, CLUT, output tables
python3 tools/pakon_profile.py verify-unity <unity.pf>   # re-run the ±1 LSB identity proof
python3 tools/pakon_profile.py lut   <ColRevLutS6.lut>   # parse the text LUT
```
