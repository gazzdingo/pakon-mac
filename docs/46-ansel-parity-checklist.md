# 46 — Ansel / colour-path parity checklist

Quick scan: what matches Pakon vs stand-ins vs UNKNOWN.
Rule: **same** items need a Pakon cite (DLL VA / shipped file). Never invent.

Vendor: `PakonIMAu.dll` image base `0x10000000`, data under
`anselinstalldir/dataPathItems` + `Config/ColorCorrection`.

Tools: `tools/ansel/` (host Ansel/SBA only), entry CLI `tools/pakon_decode.py`.
See `tools/ansel/README.md`.

---

## Verified same as Pakon

### Pipeline order / COM surface
- [x] Host colour order: ColNeg/ColRev → rotate → Ansel apply → scale → ColorAdjust → 16→8 → save (cite: `docs/11-imaging-pipeline.md`, `TLA.dll` jump table / `bLoadImageFromBuffer`)
- [x] Ansel is two-pass: roll analyze then per-scene apply (`PIAnselAnalyzeRoll` / `PIAnselColorSceneBalancePlanar`; cite: `docs/11` §5, `CiColorCorrectionAnsel` strings)

### Stage-2 colour (pre-Ansel LUTs)
- [x] 14-bit → log LUT → 3×4 matrix → clip to 12-bit RPD `0…0x0FFC` (cite: `docs/11` §2, `PIColorCorrectColNegPlanar*`)
- [x] Film-base / matrix sources from shipped `ClientColNegMat.txt` / ColRev mats (cite: `docs/11` §2)

### Ansel data selection
- [x] `.map` first-match selection (`AnsKeySelector` style) for SBA / Shasta / FUGC / profile keys (cite: shipped `*.map`; impl `tools/ansel/pakon_ansel_maps.py`)
- [x] CN-Premium SBA DPI fields loaded: `neutralBalancePoint`, `minDmin`, `neu`/`neo`/`fpo`, `pcode`, `sfsTable` (cite: `sba-CN-default.dpi` / selected dpi)

### SBA pcode
- [x] Stage-1 `SbaDecodePcode` @ `0x102884b0` → `0x1A8` struct, stop on `0xFA`, trailing stage-2 words (cite: DLL; `tools/ansel/pakon_sba_pcode.py`, 9/9 shipped pcodes)
- [x] Stage-2 VM parse @ `0x102a8f40`: version `0xFD`/9, dims opcode 0 → **24×36** for all shipped, op arrays, terminator `0xFF` (cite: DLL; `tools/ansel/pakon_sba_stage2.py`, 9/9)

### SFS / Makesfs
- [x] On-disk SFS is ASCII four-int rows (cite: shipped `sba/Sfs/sfsTable*`)
- [x] ASCII → six packed `4×int16` records at `AnsSfsTableDef+0x0c` via `operator>>` @ `0x102ac8c0` (cite: DLL; `tools/ansel/pakon_sba_makesfs.py`)
- [x] Makesfs validate **range** checks on those records @ `0x102b7280` (null/`0xe`/field ranges → `0xa`/`0xb`/`0xc`/`0xd`) (cite: DLL; partial port in `tools/ansel/pakon_sba_makesfs.py`)
- [x] Makesfs **expand** @ `0x102ac590` → 120×`(int16,int16)`, mod `0x78`, weight LUT `0x105a8830` (cite: DLL; `makesfs_expand` in `pakon_sba_makesfs.py`). Post `0x102ac430` still UNKNOWN.

### SBA shift *apply* maths (when shifts known)
- [x] Shifts live at scene `+0x3a38/+0x3a3a/+0x3a3c`; `getShifts` @ `0x10124000` copies them (cite: DLL)
- [x] Writers: `Preference` @ `0x1028c780` (from `analyzePass2` @ `0x10216433` with `scene+0x3a30`; final store loop @ `0x1028cce7` after `add esi,8`) (cite: DLL)
- [x] Master LUT for apply: ctor `0x100f42a0` / singleton `0x106b5f74` — identity `0…0xfff` with clamp skirts; `out[i]=master[i+shift]` @ `0x1006c4f0` ⇒ `clamp(code+shift,0,4095)` (cite: DLL; helper `tools/ansel/pakon_sba_apply.py`, **not** default path)
- [x] Preference **I/O contract** + opening RGB→opponent (`1/√3`, `1/√6`, `1/√2` @ `0x105a6f38/30/28`) (cite: DLL; `tools/ansel/pakon_sba_preference.py`)
- [x] Preference input blob fill `0x10214f20` — full scene→blob map documented; first RGB ← `scene+0x4d0e`; hardcodes `+0x28=0x32`, `+0x2a=0x53`, `+0x3e=0x8c` (cite: DLL)
- [x] Helper `0x1028c540`: `(R,G,B)·0.001` → mean/`1/√2`/`1/√6` doubles (cite: DLL; same module)
- [x] Preference **FPU body mapped** (`0x1028c780`…`cd02`): mode→aims, combine, Y-clamp, inverse opponent, shifts=`inv(t',−U,−V)`; external calls only helper+`_ftol2` (no soft walls); common mode `0x11`/`w1e=0` fragment in `pakon_sba_preference.py` — **`PREFERENCE_SHIFTS_PORTED=False`** (cite: DLL; `docs/49`)
- [x] `Sba()` @ `0x1028b8d0` **call-site arg list** from pass2 (13 args incl. `+0x1a`, `+0x3bc8`, `+0x388c`, `+0x290c`, `+0x38a2`) + shared `×0x186a0` opening constant with `createAlgData` @ `0x1028ceb0` (cite: DLL; `tools/ansel/pakon_sba_core.py` — fragments only, **not** a full port)

### Shasta / SRA (architecture + data load)
- [x] Shasta dpi selection via `shasta/shasta.map` → `shasta-*.dpi` (cite: shipped; maps)
- [x] Shasta dpi **scalar** load (`metricGray`, `white`, `maxValue`, `analysisImageDim`, …) matching `AnsShastaDpi` ASCII surface (cite: shipped dpi + dump strings @ `0x10589478`; `tools/ansel/pakon_shasta.py`)
- [x] Capability addresses: `analyze` @ `0x101e5250` / `export` / `getToneLut` @ `0x101e4670` / `setToneLut` / `generateOtherLuts` @ `0x101e2030`; CapabilityImpl tone vector @ `+0x3e0` → int16[] (cite: DLL; `pakon_shasta.py`)
- [x] Path glue: `analyzeWithShastaTriage` / `genShastaImages` (`shastaMethods.cpp`); `ImaShastaOp` I16-only (cite: DLL)
- [x] **Analyze→toneLut chain:** `analyze` → `0x1027be10` → generate `0x10245ed0` → builder `0x10293ee0` (working `toneLut` @ `+0x3b0`, dump `toneLut.lut`); prep `0x1027b1c0`; curve helper `0x10293960` (uses `0.95` / `0.75`) (cite: DLL)
- [x] **Aim-code store:** `0x1027be10` writes analyze args → working `+0x2b0…+0x2bc`, then prep / `sampled`+`blockAvg` helpers — image→four-arg maths still UNKNOWN (cite: DLL; `pakon_shasta.py`)
- [x] **Cap `+0x3e0` vs work `+0x3b0`:** Cap `get/setToneLut` int32 @ `+0x3e0`; Generate `+0x3b0`=toneLut, Generate `+0x3e0`=`slopeLut.lut` (`sar 3`); analyze has no Cap`+0x3e0`←work`+0x3b0` assign in scanned body (cite: DLL)
- [x] **Fragments ported:** clamp `[0,1]`; breakpoint prep; seed `toneLut[code]=code`; aim-code store; partial `0x10293d50` index/adjust; `ImaShastaOp` I16/float LUT-index apply loops — **not** a complete toneLut (`SHASTA_TONE_LUT_PORTED=False`) (cite: DLL; `pakon_shasta.py`)
- [x] **Curve helpers cited UNKNOWN:** `0x10293960` (~994 B); dispatcher `0x10293510` → exp leaves `0x10293330`/`0x10293410` — not ported (cite: DLL)
- [x] **SRA ≠ Shasta toneLut:** shipped `common-sraFwdLut-metric-*.lut` is `AnsCommonSraFwdLutDPI::readAscii` (`0x105954a0`); `makeSRALUTS` separate (`0x10594b78`) (cite: DLL; `pakon_sra.py`)
- [x] SRA fwd lut file load → 4096-entry table (cite: shipped + `pakon_sra.py`; engine **stand-in** for missing Shasta `toneLut`)
- [x] **FUGC address catalog:** path/Cap/Impl analyze/export/histogram/metrics/setLutInfo/setContrast/applyLut (cite: DLL; `pakon_fugc.py`)
- [x] **FUGC seed vs apply:** `fugc-lutMap` → contrast → `fugc-generic*.lut` is **LutDpi seed** (`+0xe6`); `setLutInfo` @ `0x101f82c0` builds apply LUT @ `+0x6140` via `offset = (+0x60ec) - (+0x60f8) + (+0x60f2)` then shift/clamp (cite: DLL; fragment in `pakon_fugc.py`)
- [x] **FUGC analyze chain cited:** lutMap select `0x101fb140` → `setContrast` → seed install `0x101f7b10` → `setLutInfo` (mode≠2) / metrics+`generateHistogram` (mode==2) (cite: DLL)
- [x] **FUGC aim fields ≠ histogram:** `+0x60f8`←`aTableDmin`; `+0x60f2`←analyze `[ebp+0x14]`; `+0x60ec`←`[ebp+0x18]` or Cap `+0x12` (ParamsDpi copy `0x10118380`); metrics write `+0x14178…` only (cite: DLL; `fill_setlutinfo_aim_words`)
- [x] **AnalyseRoll call graph (cited, not ported):** TLA `JT+0x5c` → Ci `AnalyzeRoll` `0x10002843` → `0x10020100` → `AnsOrder::analyzeOrder` `0x1001fc30` → `CnPremium_analyzeOrderWide` `0x10059d90` → `analyzeBalanceOrder` `0x10101220` (×2, with AneOrder/PreBalance/ScpLut/getCnContext around it). Apply: Ci `bColorSceneBalancePlanar` `~0x10002c50` / TLA `JT+0x64` (cite: DLL; `pakon_analyse_roll.py`)
- [x] **`analyzeBalanceOrder` body (cited):** scene walk stride `0x64dc`; pass1 → FOS analyze → pass2 → path `setShifts` → `getShifts` accumulate; FOS → Impl `0x1023ff80` → `SbaCalcFosResults` `0x1028f570` (cite: DLL; `pakon_analyse_roll.py` / `pakon_fos.py`)
- [x] **`setShifts` I/O + control words:** consumes `getShifts` → OUT; does **not** write `+0x3a38`. Control words = SCPLut Cap `+0x10+0x18` `ntdChoice`/`ctdChoice` (`+0x38`/`+0x3a`); shipped CN dpi → **`(1,2)`** → `0x60e`+LUT+`×0x186a0` (**not** Preference passthrough). `(0,0)`/`(2,2)` are passthrough A/B only. Lighting-adjust / `ans_*_pass` conflation refuted for control source (`docs/52`) (cite: DLL; `pakon_sba_apply.py` / `pakon_scp_lut.py`)
- [x] **FOS Cap→Impl→calc (cited; OUT layout known; opening ported):** Cap `0x1013cb30` → Impl `0x1023ff80` → `SbaCalcFosResults` `0x1028f570` (10 args; OUT `Impl+0x18` = `SbaFOSResults`). Cap dump names OUT fields (`numPixels`/`gmRSquare`/`illRSquare` at `+0x1e/+20/+22`). Opening RGB→3-axis `×0x186a0` fragment ported; dens/R²/slope **equations** still **UNKNOWN** (`FOS_ANALYZE_PORTED=False`; `pakon_fos.py` / `docs/47`)
- [x] **AneOrder chain (cited; not ported):** Path `0x100fad90` → Cap `0x10110540` → Impl `0x101ed3a0`; `getResults` Cap `0x10110830` / Impl `0x101ebe90` → sole caller `exportNoise` `0x10112aab`. Order-only before PreBalance/balanceOrder; **no** static edge into SBA/FOS/ScpLut/`+0x3a38` (`ANE_ORDER_PORTED=False`; cite: DLL; `pakon_ane_order.py`)
- [x] **OrderOrientation pin (separate):** Cap `0x101218c0` → Impl `0x102101d0`; from `analyzeAttributes` `0x100fb576`, **not** AneOrder (cite: DLL; `pakon_ane_order.py`)
- [x] **ScpLutBalance (cited; dpi parse only):** Path `0x100fd190` → Cap `0x101226c0` → Impl `0x102128f0`; SBA/FOS-disabled **logs**; zeroes FUGC `+0x4b6/+0x4b8/+0x4ba` @ `0x100fd8be`; `afterSCPLutSba`/`Fos` names. Sole shipped dpi; maths UNKNOWN (`SCP_LUT_BALANCE_PORTED=False`; cite: DLL; `pakon_scp_lut.py`)
- [x] **`PIColorAdjustPlanar` chain (cited; selectors ported):** IMAu `0x10013bc0`; TLA `bApplyColorAdjustments` `0x1002a5a0` after `bLoadImageFromBuffer` (Kodak→rotate→**Ansel** `slot+0x64`→scale) then ColorAdjust `slot+0x38`. profile0 ∘ sat ∘ BnW ∘ profile1 → `SpCombineXforms` → unsharp → ICC effect. Sat `params+0x50` +5 → 11 files; BnW `params+0x4c` 1/2/3→warm/cold/sepia. Unsharp amounts UNKNOWN (`COLOR_ADJUST_PORTED=False`; `SELECTORS_PORTED=True`; cite: DLL; `pakon_color_adjust.py`)

### ICC out
- [x] Shipped profiles `Rpd2Pcs_HR200_QS_v5s10.pf` + `Srgb_v2.pf` used for RPD→PCS→sRGB (cite: `docs/11` §5; Ansel engine loads these)
- [x] 4096-entry mft2 encodes with `code·255/4095` style U8 path for those tables (cite: profile + `pakon_ansel` ICC path)

### Tables used as data (not full ops)
- [x] FUGC seed lut from `fugc-lutMap` / selected `fugc-generic*.lut` (cite: shipped + maps; **seed**, not full analyze apply)

---

## Implemented but NOT Pakon-same (stand-ins)

- [ ] **SBA channel balance** — median equalise (`channel_balance`). Preference FPU **mapped** (`docs/49`); `pcls=w1e` solved (shipped 0); `setShifts` control words **closed** (shipped `(1,2)`); apply blocked on `(1,2)` maths + golden (`PREFERENCE_SHIFTS_PORTED=False`; `docs/52`).
- [ ] **Tone** — we apply shipped **SRA** fwd lut as tone. Pakon CN auto-tone builds **Shasta** `toneLut` via analyze→export→`ImaShastaOp`. SRA table is a real artefact but **wrong stage** for Shasta parity.
- [ ] **FUGC apply** — we apply shipped **seed** `fugc-generic*.lut`. Pakon may `setLutInfo`-shift it from analyze aims (`+0x6140`). Offset-0 matches seed; non-zero aims not wired.
- [ ] **Post-balance aim** — `aim_medians(…, neutralBalancePoint)` stand-in.
- [ ] **Makesfs post** — expand ported; `0x102ac430` + analyzePass consumer **UNKNOWN**.
- [ ] **Stage-2 VM** — parse only; runtime evaluation **UNKNOWN**.
- [ ] **Preview 8-bit stretch** in `pakon_decode` (when Ansel off) — non-Pakon percentile stand-in.
- [ ] **Roll-level AnalyseRoll** — stub/mean-of-medians; not `PIAnselAnalyzeRoll`.
- [ ] **Map edge cases** — not every AnsKeySelector token proven against DLL.

---

## Not started / UNKNOWN

### Preference / SBA core (honest blockers)
- [x] **Nested opening RGB identity + writers** — `scene+0x4d0e` = embedded `AnsSbaDPI+0x80` **`fpo`**; writers = ctor defaults / `AnsSbaDPI::readAscii` / assign-`rep movsd`. FOS OUT `+0x1e/+20/+22` remain different fields. See `docs/48-preference-opening-rgb.md` / `pakon_sba_preference.py`.
- [x] **Preference FPU equation map** — mode aims, combine, clamp, inverse, shift store; see `docs/49-preference-fpu-binary.md`.
- [x] **`w1e` = dpi `pcls`** — `inner+0x24` / `scene+0x4d14`; dump `0x102ae48f`; parse `0x102ad38d`; all shipped `sba-*.dpi` = 0 (`docs/49`).
- [ ] Full `Sba()` / `createAlgData` (separate from Preference FPU map)
- [ ] Preference **end-to-end port** — `setShifts` `(1,2)` transform maths + mode/`aimY` when lo≠1; golden vs DLL (`PREFERENCE_SHIFTS_PORTED=False`; control words in `docs/52`)
- [ ] FOS/HISTORY → nested `fpo` overwrite before Preference (static edge **not** found; Cap dump tags derivation at `Impl+0x3c` only)
- [ ] Full `0x102b7280` after range checks; Makesfs post `0x102ac430`
- [ ] `analyzePass1` histogram / paxel; wire `apply_balance_shifts`

### Shasta (not blocked on `+0x4d0e`; blocked on image→aims + curve)
- [ ] Analysis-image → four analyze-arg codes (feeds `+0x2b0…+0x2bc`) and aim doubles (`+0xd8/+0xb0/…`) — **UNKNOWN**
- [ ] Curve fill `0x10293960` + exp leaves `0x10293330`/`0x10293410` (+ `0x10292*`) → full `toneLut` — **UNKNOWN** (too large; pivoted)
- [ ] Full `0x10293d50` blackNoise / `+0x3c0` path (partial index fragment only)
- [ ] CapabilityImpl `+0x3e0` ← working `+0x3b0` automatic path — **UNKNOWN** (API `setToneLut` only writer found; Generate `+0x3e0` is slopeLut)
- [ ] Full `ImaShastaOp` / `ShastaApply` aggregate wiring (LUT-index loops cited)
- [ ] In-memory `AnsShastaDpi` field↔offset table (`scanOneLine`)
- [ ] `AnsSraCapabilityImpl::makeSRALUTS`

### FUGC / CN-Premium / roll
- [ ] FUGC aim **values** at `obj+0x4b6` / `obj+0x3c` — **static writer WALL** (only ScpLut zeroing of `+0x4b6`); dynamic RE needed
- [ ] Full ParamsDpi `aFilmAimDmin` → Cap `+0x12` byte map (copy site cited)
- [ ] `generateHistogram` / `calcFugcMetrics` bodies (work metrics @ `+0x14178…`; **not** `setLutInfo` aims)
- [ ] `applyLut` / export `"fugc-lut"` operand pixel path
- [ ] Wire `setLutInfo` into host only with Pakon-produced aim words
- [ ] **`PIAnselAnalyzeRoll` byte-faithful** — graph + balanceOrder sequence cited (`ANALYSE_ROLL_PORTED=False`); pass1/pass2 maths open
- [ ] **FOS dens/R²/slope closed forms** — OUT field map known (`docs/47`); opening axes + `fosDmin` min ported; equations UNKNOWN (`FOS_ANALYZE_PORTED=False`)
- [ ] FOS → pass2 / Preference data edge (ordering cited; Cap `Impl+0x3c` derivation tag; **no** static copy of OUT into nested `fpo` — `docs/48`)
- [ ] AneOrder Impl dens/residual maths + `getResults` payload map (`ANE_ORDER_PORTED=False`; chain cited)
- [ ] OrderOrientation Cap/Impl bodies (addresses pinned; Attributes path)
- [ ] ScpLutBalance Cap/Impl analyze maths + how slopes/offsets feed second balanceOrder (`SCP_LUT_BALANCE_PORTED=False`; path/dpi cited)
- [ ] Remaining CN-Premium declare/analyze/export order (SceneSpecific stage list partially cited)
- [ ] ColorAdjust unsharp amounts + `SpCombineXforms` / contrast-lut gating (`COLOR_ADJUST_PORTED=False`; selectors ported)
- [ ] DICE order, geometry parity, DX→Ansel beyond maps

### Nested-object breakthrough (static, Update 3 DLL)

- [x] **`scene+0x4d0e` layout solved:** nested object at ``scene+0x4cf0`` (ctor ``0x10289a60`` via ``+0x4c70``/``+0x80``); opening RGB = ``this+0x1e/+0x20/+0x22``. Defaults ``930,1260,1470`` (cite: DLL; `pakon_sba_preference.py`).
- [x] **FOS OUT layout solved:** ``esi`` = ``Impl+0x18`` (`SbaFOSResults`); Cap dump names ``+0x1e=numPixels``, ``+0x20=gmRSquare``, ``+0x22=illRSquare`` — **not** Preference opening RGB (cite: DLL; `docs/47` / `pakon_fos.py`).
- [x] **Runtime writers of nested opening RGB solved:** field = AnsSbaDPI **`fpo`**; ctor / `AnsSbaDPI::readAscii` (`0x1028a400` → parse `0x102ad31b`) / `operator=`+vtable copy `rep movsd` (`0x10289e40` / `0x10289ee0`). Pass1/pass2/Sba/FOS dens do **not** store it (cite: DLL; `docs/48`).
- [ ] **FOS/HISTORY → nested `fpo` swap** — Cap dump tags `Impl+0x3c`; no static copy of OUT `orderFpo` into nested `fpo` found (`docs/48`).
- [x] **Preference FPU map** — equations + mode tables in `docs/49`; portable mode-`0x11` fragment only.
- [x] **`setShifts` control words for CN auto** — SCPLut `ntd`/`ctd` = `(1,2)` (`docs/52`).
- [ ] **Port Preference → apply** — close `setShifts` `(1,2)` maths + lo≠1 aims; set `PREFERENCE_SHIFTS_PORTED` only when byte-faithful.
- [ ] **FOS dens closed forms** (slopes / R²) — structure cited; equations UNKNOWN (`FOS_ANALYZE_PORTED=False`) — for FOS parity, not Preference RGB.
- [ ] **FUGC non-zero `obj+0x4b6` / `+0x3c`** — only ScpLut **zero** stores found; still needs more binary work or dynamic RE.
- [ ] **Shasta image→aims + curve** — still UNKNOWN.

### Honest blockers (current)
1. **Close Preference → apply**: control words **proven** shipped `(1,2)` (`docs/52`); still need `(1,2)` closed-form maths + golden vs DLL before `PREFERENCE_SHIFTS_PORTED` / default apply. Mode-`0x11`/`pcls=0` Preference fragment remains diagnostic-only (`docs/49`).
2. **lo≠1 / user-balance modes** — `aimY` from `scene+0x38a2` / FOS arg1 when tokens present.
3. **Confirm / refute FOS `orderFpo` → nested `fpo`** (static: absent; dynamic only if needed).
4. **FOS dens closed form** (FOS parity, not Preference RGB).
5. FUGC / Shasta as before (aim writers; toneLut curve / AnalyseRoll pass1).

### Dynamic RE — only if needed for FOS-on Preference parity
| Gap | Status |
|-----|--------|
| `scene+0x4d0e` *layout* | **Solved** (nested `+0x1e` = dpi `fpo`) |
| `scene+0x4d0e` *writers* | **Solved** (ctor / readAscii / assign-copy) |
| Preference FPU → shifts *equations* | **Mapped** (`docs/49`); port flag False |
| `inner+0x24` (`w1e`) | **Solved** = dpi `pcls` (shipped = 0) |
| `setShifts` → apply words | **Control words closed** — shipped `(1,2)`; transform maths UNKNOWN (`docs/52`) |
| FOS OUT `+0x1e/+20/+22` | **Solved** as stats (`numPixels`/`gmRSquare`/`illRSquare`) |
| FOS → nested `fpo` | **UNKNOWN** (no static edge; Cap tag only) |
| FOS dens equations | Structure cited; closed forms UNKNOWN (`docs/47`) |
| FUGC `+0x4b6` non-zero | Still no store besides ScpLut zero |
| Shasta curve | Large; still open |

---

## Suggested next RE order (Pakon-only)

1. **Port / golden `setShifts` `(1,2)`** (`0x60e` + `0x10122150` LUT + `×0x186a0`) → apply LUT inputs; then consider wiring.
2. User-balance / lo≠1 `aimY` paths if needed.
3. FOS dens closed form (FOS parity — not Preference RGB).
4. FUGC aim writers / `setLutInfo` wiring.
5. Shasta curve helpers / ColorAdjust unsharp.

---

## File map

| File | Role |
|------|------|
| `tools/ansel/pakon_sba_pcode.py` | Stage-1 decode (verified) |
| `tools/ansel/pakon_sba_stage2.py` | Stage-2 parse (verified) |
| `tools/ansel/pakon_sba_makesfs.py` | ASCII→binary + range validate + expand |
| `tools/ansel/pakon_sba_apply.py` | Verified apply helper (unwired) |
| `tools/ansel/pakon_sba_preference.py` | Preference I/O + FPU fragments; `fpo`/`pcls` helpers; `PREFERENCE_SHIFTS_PORTED=False` |
| `docs/48-preference-opening-rgb.md` | Nested opening RGB = `fpo`; writer hunt |
| `docs/49-preference-fpu-binary.md` | Preference FPU map → shifts; mode/clamp/inverse |
| `tools/ansel/pakon_sba_core.py` | `Sba()` / `createAlgData` cites (not a port) |
| `tools/ansel/pakon_shasta.py` | Shasta dpi + toneLut chain/fragments (curve UNKNOWN) |
| `tools/ansel/pakon_fugc.py` | FUGC seed + `setLutInfo` + aim-store fragments; analyze UNKNOWN |
| `tools/ansel/pakon_analyse_roll.py` | AnalyseRoll / balanceOrder / setShifts I/O catalog (`PORTED=False`) |
| `tools/ansel/pakon_fos.py` | FOS Cap/Impl/calc; OUT layout + opening/dmin fragments (`ANALYZE_PORTED=False`) |
| `tools/ansel/pakon_ane_order.py` | AneOrder / OrderOrientation catalog (`*_PORTED=False`) |
| `tools/ansel/pakon_scp_lut.py` | ScpLutBalance path/Cap + dpi parse (`BALANCE_PORTED=False`) |
| `tools/ansel/pakon_color_adjust.py` | PIColorAdjustPlanar catalog + sat/BnW selectors (`PORTED=False`) |
| `tools/ansel/pakon_sra.py` | `AnsCommonSraFwdLutDPI` load (not Shasta toneLut) |
| `tools/ansel/pakon_ansel.py` | Engine; median SBA + SRA-as-tone stand-ins |
| `tools/ansel/pakon_ansel_maps.py` | `.map` selection |
| `tools/ansel/README.md` | Folder boundary |
| `tools/pakon_decode.py` | Strip decode CLI |
| `docs/11-imaging-pipeline.md` | Host pipeline (broader) |
| `docs/46-ansel-parity-checklist.md` | This checklist |
| `docs/47-sba-fos-binary.md` | `SbaCalcFosResults` ABI / OUT layout / dens UNKNOWN |
| `docs/48-preference-opening-rgb.md` | Nested opening RGB = dpi `fpo`; writer hunt |
| `docs/49-preference-fpu-binary.md` | Preference FPU → `+0x3a38` equation map |
| `docs/52-setshifts-binary.md` | setShifts control words = SCPLut ntd/ctd; CN `(1,2)` |
