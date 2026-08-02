# 09 — The Film-Stock Database

How the Pakon F-X35 family (F-135/F-235/F-335) identifies film emulsions and applies
per-stock handling, recovered from the "Pakon Update 2" Windows install tree.

Verification tags: **[VERIFIED]** = read directly from shipped files or confirmed by at
least two independent sources; **[INFERRED]** = consistent with evidence but not stated
outright; **[UNKNOWN]** = not recoverable from the sources at hand.

---

## 1. The headline answers

- **Ilford IS present.** [VERIFIED] `defaults.ini` reserves product IDs **105–110** under
  `;Ilford Imaging`, and the ISO table has live data for product 110 (XP-series, all ISO 400).
- **The ID scheme is not a Pakon invention.** [VERIFIED] Pakon's *film product* is the
  **DX number Part 1** ("combination code", 0–127) and its *film specifier* is **DX number
  Part 2** ("generation code", 0–15) from the PIMA/I3A DX film-edge barcode standard.
  The shipped table's own header says so: *"a film ISO speed for each Part1/Part2 PIMA
  code combination as publish by PIMA"*.
- The user's target stocks all have registered DX codes: [VERIFIED]

  | Stock | Part 1 | Part 2 | Composite DX number (P1×16+P2) |
  |---|---|---|---|
  | Ilford HP5 Plus | 109 | 9 | 1753 |
  | Ilford FP4 Plus | 109 | 12 | 1756 |
  | Ilford Delta 3200 Professional | 108 | 10 | 1738 |
  | Ilford XP2 Super | 110 | 4 | 1764 |

  (Cross-checked against crowd-sourced cartridge-barcode decodes in the Flickr
  "DX barcode numbers on 135 film" thread and the ffindr community database — see §7.)

---

## 2. Where the database lives

There is **no single film database file**. The install carries four cooperating pieces:

| Piece | Path (relative to `fx35install/program files/Pakon/`) | Role |
|---|---|---|
| DX decoder | `F-X35 COM SERVER/TLA.dll` (also TLB/TLC per model) | Reads the film-edge barcode; class `CiDxCode`; logs `Product = %d, Specifier = %d` per strip to `Logs\PakonDxLog.txt` / `Logs\DxCode.txt` [VERIFIED — binary strings] |
| ISO lookup | `F-X35 COM SERVER/anselinstalldir/dataPathItems/common/common-ProdCodeTable.dpi` | 128×16 table: (Part 1, Part 2) → film ISO speed [VERIFIED] |
| Per-stock image-chain overrides | `anselinstalldir/dataPathItems/{sba,pnr,nra,filmLut,...}` + `.map` selector files | Scene balance, noise reduction, film LUT selected by `productCode i16 genCode i16` [VERIFIED] |
| Per-stock user slider defaults | `F-X35 COM SERVER/Config/ColorCorrection/defaults.ini` | Red/Green/Blue/Brightness/Contrast/Sharpness in hundredths of a slider click, per product ID [VERIFIED] |

The COM API exposes the pair as `piFilmProduct`/`piFilmSpecifier` (per image),
`piFilmProductFromStrip`/`piFilmSpecifierFromStrip`, `iDefaultFilmProduct`/
`iDefaultFilmSpecifier`, and `Put24mmFilmId` (APS cartridge ID — a separate number).
PSI.exe shows the value in the UI as "Film Product:". [VERIFIED — binary strings]

### Dead ends checked
- `program files/Pakon/PSI/mrd.mdb` — **not** the film database. It is a Jet4 Access file
  containing a single **empty** table `Production(Period, Product, Unit, Quantity)` —
  a leftover stub (see `tools/dump_mrd.py`). [VERIFIED]
- `program files/Pakon/IQ/DEVICES.DEF`, `DEVLIST.TXT` — CD/DVD-writer compatibility
  lists, nothing to do with film. [VERIFIED]
- No film *names* are shipped anywhere in the install — not in the binaries (ASCII and
  UTF-16LE string sweeps of PSI.exe, PTS.exe, PakonIMAu.dll, tlx/TLA/TLB/TLC.dll) and not
  in any data file. Names live only in the (proprietary) I3A registry; the software never
  needs them. [VERIFIED]

---

## 3. The DX film-edge barcode (how IDs get onto film)

Per the I3A/ANSI IT1.14 standard ("DX Film Edge Barcode"), every half-frame of 135 film
carries a latent-image clock track + data track below the sprocket holes. The data track
encodes: [VERIFIED — public documentation, §7 sources]

- **Part 1, 7 bits (values 0–127)** — product/combination code = manufacturer + emulsion
- **Part 2, 4 bits (0–15)** — generation/specifier code
- half-frame number (added 1990) and parity

The 4-digit "DX number" printed on cartridge labels and encoded in the cartridge barcode
is `Part1 × 16 + Part2`. Example worked in the sources: Fuji part1 34, part2 6 → 550.

The scanner decodes this from the developed strip (TLA.dll: "DX Codes" log block, "Good
Dx Count", "Max Correctness of %d found at %d"), so it identifies emulsions without the
cartridge. [VERIFIED]

---

## 4. Manufacturer allocation of Part-1 codes

From `defaults.ini` groupings [VERIFIED — in-box], byte-identical to the public 2008 I3A
allocation reproduced on Wikipedia's "DX number" page [VERIFIED — cross-referenced]:

| Manufacturer | Part-1 codes |
|---|---|
| Agfa-Gevaert | 1, 3, 5, 7, 17, 31, 44, 45, 46, 47, 49, 51, 113, 115 |
| China Lucky Film | 60, 90, 100 |
| Eastman Kodak | 4, 6, 11, 13, 14, 19, 20, 23, 43, 52, 53, 64, 67, 70, 78, 79, 80, 81, 82, 83, 84, 91, 92, 93, 94, 95, 112, 116 (+ 96, 97 added later — 96 appears in ProdCodeTable rev 6/6/06) |
| ERA | 68 |
| Ferrania Imaging | 15, 18, 24, 66, 85, 86, 87 |
| Fuji Photo Film | 8, 10, 12, 32, 33, 34, 35, 36, 37, 38, 39, 42 |
| **Ilford Imaging** (Harman Technology) | **105, 106, 107, 108, 109, 110** |
| Konica | 2, 16, 25, 26, 28, 30, 40, 48, 50, 72, 77 |
| ORWO Media | 120, 121, 122, 123 |
| Shanghai General Photo | 88 |
| SVEMA Production Assoc. | 9 |
| Xiamen FUDA (typo "Xia]men" in file) | 98 |

`defaults.ini` also defines three pseudo-products for the non-DX paths: `[BnW]`
("Black and White (C41 and regular)"), `[POSITIVE]` ("Color reversal film and
kodachrome"), `[IMPORTED]` ("Imported images such as from file"). [VERIFIED]

**Important:** every section in the shipped `defaults.ini` is *empty* — it is a template
listing known product IDs with zero slider adjustment. The per-stock colour behaviour
does **not** come from this file in a stock install; it comes from the Ansel image chain
(§6). [VERIFIED]

---

## 5. The ISO table (`common-ProdCodeTable.dpi`)

ASCII file, 128 rows (Part 1 = 0–127) × 16 columns (Part 2 = 0–15), value = ISO speed,
0 = unassigned/unknown. Header comments date revisions 9/8/00 → 6/6/06 and name films as
they were added (e.g. "33-9 Fujicolor Nexia H400", "43-04..07 Kodak Max 800", "96-01..03
Kodak Gold 400 Gen 9", "49-13 Agfa Optima Prestige 200 Professional"). 46 rows contain
non-zero data. [VERIFIED]

Row comments give brand families (KONICA CENTURIA, FUJI SUPERIA 135, KODAK GOLD MAX VR
B&W PJ, AGFACOLOR HDC/VISTA, "Illford" [sic], LUCKYCOLOR, ORWO, FUDA, ...). [VERIFIED]

Selected rows (full table in `research/film-products.json`):

| P1 | Pakon comment | ISO by gen 0–15 |
|---|---|---|
| 26 | KONICA CENTURIA | 400 800 100 200 1600 400 800 0 ... |
| 35 | FUJI SUPERIA 135 | 1600 800 400 200 160 100 100 100 1600 800 400 400 100 100 100 400 |
| 78 | KODAK GOLD MAX VR B&W PJ | 400 100 200 400 100 200 400 800 400 100 100 200 200 400 200 800 |
| 79 | (Kodak VR / Portra) | 0 200 200 100 400 100 100 200 400 400 100 160 100 400 800 400 |
| 110 | Illford | 0 **400 400 400 400** 0 ... |

**Ilford in this table:** only row 110 (the chromogenic XP family — XP1 400, XP1 400 P1,
XP2, XP2 Super, all ISO 400) has data. Rows 105–109 are all zeros: the conventional B&W
stocks (HP5+, FP4+, Delta, Pan F) were never given ISO entries because the C-41 colour
pipeline doesn't process them — B&W goes through the `[BnW]` path. The DX decoder itself
is emulsion-agnostic and still reports Product/Specifier for any film whose edge barcode
it can read. [VERIFIED table contents; INFERRED rationale]

---

## 6. Per-stock correction parameters (what actually differs per film)

The Ansel pipeline (`PakonIMAu.dll`, Kodak's imaging science library — source paths in
the binary point at `\Atc\ansel\src\libCommon.ansel\AnsCommonProdCodeTable.cpp`) selects
data files through `.map` selector tables whose keys include `productCode i16 genCode
i16`. [VERIFIED]

What ships:

1. **ISO-driven noise reduction** [VERIFIED]: (P1,P2) → ISO via ProdCodeTable, then
   `pnr/`(and legacy `nra/`) select speed-binned DPIs: `negative35-0025 ... -3200`,
   `negativeAPS-0100 ... -0800`.
2. **Per-stock scene-balance overrides** (`sba/SbaDPI/sba.map`) [VERIFIED]:
   - `78-13` → Kodak Black-and-White +400 (chromogenic): dedicated file, `fpa = -94 -94
     -94` vs default `-70 -55 -45`; comment: "created 03/03/04 in response to
     chromogenic B&W ITS #13396... based on print judging of 75 images from 12 rolls".
   - `79-15` → Kodak Portra 400BW (chromogenic): same treatment.
   - `96-*` (Gold 400 Gen 9) and `43-*` (Max Zoom 800): `fpa = -75 -50 -25`, "created
     5/17/05 after initial tests of Pakon 135 in DPS900".
3. **Per-stock noise "scrub" profiles** (`pnr.map`, FPS path) [VERIFIED] for eleven
   (P1,P2) pairs: 26-3, 35-1/2/3, 43-1/2, 78-2, 79-7, 82-3, 87-2, 113-12 — i.e. Konica
   Centuria S200, Fuji Superia 800/400/200, Kodak Max 800, Gold 200, VR200, Max 400,
   Ferrania FG200, Agfa Vista 200-N. (Stock names via community DX db.) [names INFERRED]
4. **Film-family colour profiles** (`pnr/profiles/*_fpim_to_rpd_*.pf`) [VERIFIED files,
   INFERRED naming]: a200 (Agfa), c200, f200/f400/f800 (Fuji), ferr200 (Ferrania),
   k200/k400/k800 (Kodak), kvr200 (Kodak VR) — FPIM→RPD (reference print density) input
   characterisation per family/speed, not per exact emulsion.
5. **Per-(scanner, product, gen) film LUT hook**
   (`filmLut/filmLut-scanner-prod-gen-default-default-default.lut`): the naming scheme
   supports per-stock LUTs but only the 4096-entry identity default ships. [VERIFIED]
6. **`defaults.ini` slider defaults**: mechanism present, all zero as shipped (§4).

So the celebrated "per-stock colour" is largely: DX-identified ISO → speed-tuned noise
reduction + a handful of hand-tuned per-stock scene-balance/noise overrides + family
colour profiles — not a unique LUT per emulsion. [INFERRED summary of VERIFIED parts]

---

## 7. ID → stock-name table

The Pakon install itself resolves IDs only to manufacturer + brand-family + ISO. Full
per-(P1,P2) stock names come from outside sources and are compiled in
**`research/film-products.json`** (492 name rows):

- ffindr/dxcode-film-db (community-compiled from the I3A "DX Codes for 135-Size Film"
  list; LGPL-3.0) — bulk of the names.
- Flickr "DX barcode numbers on 135 film" crowd-sourced decodes — independent
  confirmation for ~25 stocks.
- Wikipedia "DX number" — Part-1 allocation table and worked examples.

Confidence: rows where the Pakon ISO table agrees gen-for-gen with the community name's
ISO are effectively **[VERIFIED]** (all of rows 26, 35, 78, 79, 110 checked; also 113
except gens 11–13 which post-date the 2006 table). Community rows with no Pakon ISO to
check against (all-B&W and E-6 rows, incl. Ilford 108/109) rest on two community sources
agreeing and are tagged accordingly in the JSON. [VERIFIED/INFERRED as stated]

### Ilford in full [VERIFIED against both community sources]

| P1-P2 | Stock |
|---|---|
| 108-7 | SFX 200 |
| 108-10 | **Delta 3200 Professional** |
| 109-1/5/13 | Pan F (P1) / Pan F / Pan F Plus |
| 109-2/3 | Ilford Pan 100 / Pan 400 |
| 109-6 | FP4 / Ortho Plus |
| 109-7 / 109-9 | HP5 / **HP5 Plus** |
| 109-8 / 109-11 | Delta 400 Pro / 400 Delta |
| 109-12 | **FP4 Plus** |
| 109-14 / 109-15 | 100 Delta / 100 Delta Pro |
| 110-1..4 | XP1 400 (P1), XP1 400, XP2, XP2 Super |
| 105, 106, 107 | Reserved to Harman; no registered products found [UNKNOWN] |

---

## 8. What remains unknown

- **[UNKNOWN]** Official names for every (P1,P2) — the definitive source is I3A's
  proprietary *DX Codes for 135-Size Film* (last edition Jan 2009; I3A is defunct). An
  archived copy ("I3A_DX_codes.pdf", referenced by aurelien.lawley.com.au as recovered
  via the Wayback Machine) would settle the remaining rows.
- **[UNKNOWN]** Whether F-135 firmware gates DX decoding by film type in B&W scan mode
  (the decode lives in host-side TL*.dll, so likely not, but untested on hardware).
- **[UNKNOWN]** The exact runtime translation from `defaults.ini` slider units
  (hundredths of a click) to pipeline parameters (`EC_PI_MIN_MAX_RANGE_*` bounds exist in
  TLA.dll; the scale factor is in code, not data).

### Practical consequence for the macOS port
Ilford support needs no new IDs: decode the edge barcode, report 109-9 / 109-12 / 108-10
/ 110-4, route conventional B&W to the BnW path (ProdCodeTable gives ISO 0), and route
XP2 Super (110-4, ISO 400) through the colour-negative chain like the scanner already
does for Kodak chromogenics (which got dedicated SBA tuning at 78-13 / 79-15 — a good
template for an XP2 profile).

## Sources

- In-box: `defaults.ini`, `common-ProdCodeTable.dpi`, `sba.map`/`pnr.map` + DPI files,
  string dumps of TLA/TLB/TLC/tlx.dll, PakonIMAu.dll, PSI.exe, PTS.exe (paths above).
- [Wikipedia — DX number](https://en.wikipedia.org/wiki/DX_number)
- [Wikipedia — DX encoding](https://en.wikipedia.org/wiki/DX_encoding)
- [Decoding 35mm DX film edge barcodes (aurelien.lawley.com.au)](https://aurelien.lawley.com.au/posts/decoding_35mm_dx_film_edge_barcodes/)
- [Flickr group thread: DX barcode numbers on 135 film](https://www.flickr.com/groups/67377471@N00/discuss/72157634429783414/)
- [ffindr/dxcode-film-db (GitHub)](https://github.com/ffindr/dxcode-film-db)
