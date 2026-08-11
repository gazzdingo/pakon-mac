# 62 — Colour engine consolidation

**Status:** **§7's recommendation is SUPERSEDED — see §12.** The owner has decided the colour
pipeline consolidates on **Go**, and the app will render through it. §12 records that
decision, its cost, what phase 1 built and fixed, the measured per-stage parity, and the
phase-2 plan for wiring the app.

Everything in §0–§11 stands. Its *findings* — the stage-by-stage gap analysis in §1 and §2,
the ABI in §3, the metadata contract in §4, the packaging audit in §5, the risks in §10 and
the honest list of unknowns in §11 — are what phase 1 was built from and remain the
reference. Only §7's **conclusion** is overturned.

**Date:** 2026-08-10 (§0–§11); §12 appended the same day.
**Scope:** the three implementations of the F-135 colour chain, and what to do about them.

---

## 0. Summary, and an objection

The brief asks for the colour stages to be consolidated **behind Go**, on the grounds that
`tools/ansel/pipeline/` is "the most correct". I went through both engines stage by stage
and I do not think that premise survives contact with the code. My recommendation is
different from the one asked for, and the argument is in §2 and §7.

**What I agree with, completely:** the duplication is real, it is the cause of the defect
that shipped, and it must end. One implementation, one place to fix a bug.

**Where I disagree:** the Go pipeline is not the more correct of the two. It reads the wrong
FUGC map file (§2.1), takes the FUGC branch that `docs/58` §7 lists as *not ported* (§2.2),
computes that branch's bias with a formula that is not the vendor's (§2.3), measures the film
base per frame instead of per roll — the exact bug Python's own comment warns about (§2.6) —
and has none of the refusals (§2.7). It is right about two things Python gets wrong, and both
are worth taking (§2.9, §2.10). But "port Python's correctness into Go" is a rewrite of the
Go side, not a consolidation onto it.

**Three of the brief's premises are factually wrong, and the plan depends on them:**

| premise | reality |
|---|---|
| "the existing Go-vs-Python parity check (currently within ~2% per channel)" | **There is no Go-vs-Python parity check.** No `*_test.go` anywhere; no script compares the two. The "within 2 %" strings are prose in comments (`tools/ansel/pipeline/main.go:418`, `:447`, `tools/pakon_decode.py:588`) about unrelated round-trips. |
| "a reference table of per-frame means from `captures/strip_cal.bin` in `docs/`" | **No such table exists**, in `docs/` or anywhere. The only published number for that capture is a single whole-strip RPD-12 mean `[966.7, 1280.2, 2123.7]` in `docs/61-decoder-parity-audit.md`, which is **history-only** (`git show 70b6a65:docs/61-decoder-parity-audit.md`) and is not per frame. |
| "the Go pipeline is significantly faster" (`README.md:26`) | **Measured today, it is slower.** On an identical synthetic 1439×1000 frame: Go 1.11 s, Python 0.79 s. See §6. |

The instrument the migration plan is supposed to be verified with does not exist. **Building
it is step 1 of any plan here, whichever engine wins.**

---

## 1. Gap analysis, stage by stage

Reference points:
`render_frame` — `tools/pakon_render.py:950`.
`cmd_strip` — `tools/pakon_decode.py:957`.
Go — `processImage`, `tools/ansel/pipeline/main.go:245`.

### 1.1 The chain, three ways

| # | stage | `pakon_render.render_frame` | `pakon_decode.cmd_strip` | Go `processImage` |
|---|---|---|---|---|
| 0 | capture → lines → rgb14 | `open_capture` (`pakon_render.py:593`), memmapped | inline (`pakon_decode.py:987-995`) | **absent** — takes a TIFF |
| 1 | per-pixel dark × gain | `Roll.slice14` → `dec.apply_unit_calibration` (`pakon_render.py:517`) | `pakon_decode.py:1015` | **absent** |
| 2 | trilinear CCD deskew | done at open, carried in cache | `pakon_decode.py:1022-1042`, `auto` default | present but **off by default** (`main.go:42`, `:681`) |
| 3 | framing / frame spans | `pakon_framing` five-phase cascade (`pakon_render.py:787`) | `dec.find_frames`, one-pass (`pakon_decode.py:1117`) | **absent** — one TIFF = one frame |
| 4 | transport scale | `dec.resolve_transport_scale` (`pakon_render.py:847`) | same (`pakon_decode.py:1060`) | **absent** |
| 5 | **stage 2 polynomial** | `_rpd16` → `pc.poly_hwc` (`pakon_render.py:335`) | `render_rpd` (`pakon_decode.py:321`) | `PolyPixel` (`poly.go:163`) — **same maths** |
| 6 | coefficient source | `pc.load_unit_matrix("auto")` — **prefers registry** (`pakon_color.py:590`) | same | `LoadMatrixCoeffs` — **prefers EEPROM** (`poly.go:50`) — *documented disagreement, see §2.11* |
| 7 | film base (Dmin) | **per roll**, whole strip (`pakon_render.py:721-742`) | per strip (`pakon_decode.py:616`) | **per frame** (`main.go:468`) — §2.6 |
| 8 | **F-135 log inversion** | `dec.f135_rom12_to_rpd12` via `scene_rpd12` (`pakon_render.py:380`) | `pakon_decode.py:1164` | `main.go:486-507` — **same formula** |
| 9 | film-base sentinel refusal | `dec.check_film_base` (`pakon_decode.py:528`) | same | **absent** — clamps to 1, renders black §2.7 |
| 10 | film-class refusal (slide) | `dec.check_film_class` (`pakon_render.py:345`) | `pakon_decode.py:980` | **absent** §2.7 |
| 11 | SBA Preference → setShifts | `sba_apply.setshifts_12` (`pakon_ansel.py:551`) | same | `SetShifts12` (`sba.go:112`) — **same maths** |
| 12 | balance apply | `apply_balance_shifts` (`pakon_ansel.py:640`) | same | `ApplyBalanceShifts` (`sba.go:122`) — **same** |
| 13 | **stage order** | balance → **Shasta** → **FUGC** → ColorAdjust | same | balance → **FUGC** → **Shasta** (`main.go:522`, `:554`, `:571`) — §2.5 |
| 14 | **FUGC map selection** | `fugc-rgb-lutMap.map` via `mode = RGB` (`pakon_ansel_maps.py:331`) | same | **`fugc-lutMap.map`** (`maps.go:417`) — §2.1 |
| 15 | **FUGC branch** | `setLutInfo` (mode ≠ 2) (`pakon_ansel.py:727`) | same | **mode 2** (`main.go:529`) — §2.2 |
| 16 | FUGC aim words | `a_table_dmin` read from the LUT file; `ebp18` = FindDmin on `balanced` (`pakon_ansel.py:706`) | same | hardcoded `{500,500,500}` / `{500,1000,1000}`; **`ebp18` never computed** (`main.go:525-526`) — §2.4 |
| 17 | Shasta tone | `shasta_two_anchor_tone`, `np.percentile` (`pakon_ansel.py:300`) | same | `ShastaToneRpd`, 4096-bin histogram (`shasta.go:96`) — §2.10 |
| 18 | ColorAdjust leaf | `apply_preference_color_adjust_i16` (`pakon_ansel.py:743`) | same | **absent** — no-op today §2.8 |
| 19 | **ICC RPD→sRGB** | quantise to **u8** then lcms (`pakon_ansel.py:775`, `:229`) | same | own mft2 at **16-bit** (`icc.go:248`) — §2.9 |
| 20 | ICC profile selection | `profile.map` resolved but **unused**; pair hardcoded (`pakon_ansel.py:779-780`) | same | pair hardcoded (`main.go:714-715`) — *equal footing* |
| 21 | unsquash + rot90 | after colour (`pakon_render.py:983`) | after colour, at write (`pakon_decode.py:923`) | **before** colour — it is baked into the input TIFF §3.4 |
| 22 | user corrections | `apply_correction`, button-steps (`pakon_render.py:937`) | absent | **absent** |
| 23 | geometry (rotate/flip/crop) | `_apply_geometry` (`pakon_render.py:905`) | absent | absent |

### 1.2 What Go already implements identically

The polynomial (`poly.go:163` vs `pakon_color.py:747`, including the float32 spill emulation
`f32` at `poly.go:21`), the EEPROM coefficient reader (`poly.go:67`, offsets `0x25`/`0x9d`),
the SBA Preference→setShifts chain (`sba.go:112-219`), the balance apply, `FindDmin`'s
downward histogram walk (`dmin.go:20`), and the F-135 log inversion arithmetic
(`main.go:493` vs `pakon_decode.py:620`) are the same operation on both sides. Those five
are genuinely dual-maintained and are the strongest case for consolidation of *some* kind.

### 1.3 What Go does not have at all

Everything in rows 0–4, 9, 10, 18, 22, 23 of the table above. In particular: capture decode,
calibration, framing, transport geometry, both refusals, the ColorAdjust leaf and the entire
parameter model. Go is not "the colour half of the app"; it is one frame of the middle of it.

---

## 2. Where the two disagree, and which side is right

### 2.1 Go reads the wrong FUGC map — **Python is right** [established]

`maps.go:417` opens `fugc/fugc-lutMap.map`.

`tools/ansel/python-pipeline/pakon_ansel_maps.py:331-365` refuses to, and cites
`AnsFugcMapping` @ `0x101fb140`: the DLL chooses between `fugc-neutral-lutMap.map` and
`fugc-rgb-lutMap.map` on the FUGC mode, and the shipped
`vendor/ansel/anselinstalldir/dataPathItems/fugc/fugc-defaultParams.dpi:3` says `mode = RGB`.
`fugc-lutMap.map` is the 08/28/2002 original both variants were split out of, and nothing
selects it.

Measured, in the shipped data:

* `fugc-rgb-lutMap.map` has every per-film rule commented out; the only live rule is
  `film = X X X 2.25`, so **every** stock lands on `NoShift_fugc-generic0225.lut`.
* `fugc-lutMap.map` routes ISO 400 to `2.25` → `fugc-generic0225.lut` and ~100 other DX codes
  to `2.50`.
* `fugc-generic0225.lut` and `NoShift_fugc-generic0225.lut` differ in **705 of 3201 rows**,
  by up to **60 codes**, over indices 237…943.

So Go applies a different tone LUT from Python for every film stock, and for some stocks a
different *contrast class* as well. This is the single largest numeric divergence between
the two engines and it is not a judgement call.

### 2.2 Go takes the FUGC branch that is not ported — **Python is right** [established]

`main.go:528-532`: `if model == "f135" { fugcApplyLut = BuildMode2ApplyLut(...) }`.
`pakon_ansel.py:711-733`: `if self.fugc_mode == 2: … else: build_setlutinfo_apply_lut(…)`,
and `fugc_mode` defaults to `1` (`pakon_ansel.py:458`) with nothing in the tree setting it
to 2.

`docs/58-colour-pipeline.md` §7 (history-only, `git show 70b6a65:docs/58-colour-pipeline.md`)
lists the ported pieces as "… **FUGC mode ≠ 2** …" and the not-ported as "… `useAvg ≠ 0` and
**FUGC mode 2**". Go's F-135 path is unconditionally the unported branch.

These are not variants of one calculation. `setLutInfo` builds three per-channel LUTs from
three per-channel aim offsets; mode 2 builds **one** plane from the seed's red column and
replicates it across RGB (`fugc.go:127-131`). Different transform, different colour.

### 2.3 Go's mode-2 bias is not the vendor's — **Python is right** [established]

`fugc.go:92`:

```go
bias := int(int16(capParamsAim[1]) - int16(aTableDmin[1]) + int16(argEbp14[1]))
```

Green channel only, no clamp, no averaging.

`pakon_fugc.py:394-414` (`fugc_work_bias`), instruction-cited to `0x101f79b0`:

```
bias = avg3( max(0, int16(60ec_i + arg_i)) ) − avg3( int16(60f8_i) )
```

with the signed `/3` implemented as the DLL's `imul 0x55555556` magic (`pakon_fugc.py:385`)
and an `int16` wrap on the result. Go's is a three-term expression standing in for a
nine-term one; it drops the per-channel `max(0, …)` floor, drops R and B entirely, and
drops the `+1` rounding bias inside the division.

Note the rest of Go's mode-2 plane fill (`fugc.go:103-125`) *is* faithful to
`mode2_apply_lut_plane` (`pakon_fugc.py:574`) — including the negative-bias tail, where Go's
loop bound differs by one but writes the same value. The bias is the only error there.

### 2.4 Go never computes `ebp18`, so the aim policy branch never runs — **Python is right** [established]

`pakon_fugc.py` module docstring, lines 44-56, cites the branch at `0x101fc3c4…`: analyze
arg `[ebp+0x18]` (the frame Dmin from the bag, `getCnContext find("dmin")`) is compared
against Cap `+0x12` with factor `0.2` @ `0x10588eb8`; if `0.2·params ≤ arg ≤ 2.0·params` in
**all three** channels it is copied to `+0x60ec`, otherwise the ParamsDpi value is.

Python implements it (`fugc_ebp18_policy_pass`, `pakon_fugc.py:311`) and feeds it the frame
Dmin measured on the **post-balance, pre-Shasta** array (`pakon_ansel.py:705-710`).

Go ports the policy function (`fugc.go:8-33`) and then never calls it on the F-135 path:
`BuildMode2ApplyLut` has no `argEbp18` parameter at all (`fugc.go:91`). Go always takes the
fallback. It also passes `{500,1000,1000}` as `capParamsAim` and `{500,500,500}` as
`aTableDmin` (`main.go:525-526`) rather than reading them.

**Severity note, in Go's favour:** those two hardcodes happen to be correct for every file in
this install — I checked all thirteen shipped `fugc-*.lut` and all carry
`aTableDmin = 500 500 500`, and `fugc-defaultParams.dpi` carries `aFilmAimDmin = 500 1000 1000`.
So this is a latent hazard, not a live numeric difference. The missing `ebp18` **is** live.

### 2.5 Stage order — **I could not establish which is right**

Python (`pakon_ansel.py:636-746`): balance → Shasta → FUGC → ColorAdjust.
Go (`main.go:511-573`): balance → FUGC → Shasta, with an explicit comment at `main.go:522`
("Shasta runs after FUGC on final RPD12 values") and no reasoning behind it.

These do not commute: FUGC is a clamped 1-D translation of a nonlinear seed curve, Shasta is
a per-channel affine stretch with clamps at both ends. `L∘A ≠ A∘L` wherever either clamps.

The evidence I found, and why it is not conclusive:

**Weakly for Go.** `docs/58` §16.3 gives the scene order out of
`CnEnhanced_analyzeSceneSpecific` `0x10068bd0` as
`… analyzePostBalance 0x100fdc40 → analyzeFugc 0x100fed00 → balanceAreaImage 0x10102b20 → …
→ analyzeAutoTone 0x100fb730 …`, and records that `balanceAreaImage` composes
`filmLut_c ∘ scpLut_c ∘ shift_c ∘ fugc_c` and applies it through `AnsImageData::applyLut`
`0x100d9340`. Shasta is not in that composition; its apply is `ImaShastaOp`, reached through
`analyzeWithShastaTriage` / `genShastaImages` (`docs/46` line 126). If Shasta's apply happens
downstream of `balanceAreaImage`, Go's order is the vendor's.

**Why that does not settle it.** `docs/58` §16.5 lists as still open: *"Whether
`balanceAreaImage`'s composed 3-band LUT reaches the **rendered** image or only the
area/analysis image. It operates on the area image passed in; the render side goes out
through `acquire()` into an `AnsOrder`/`ImaTransform` chain that has not been traced."* If
that composition is analysis-only, it says nothing about render order.

**Also weighing on it:** on this install every shipped 3-band table is `R = G = B`
(`docs/58` §16.3), and the FUGC LUT Python selects is one of them. A channel-independent 1-D
LUT commutes with a *global* affine map but not with Python's Shasta, which derives its
anchors per channel from the data. So the order matters here only because both stand-ins are
per-channel — i.e. the ordering question is partly an artefact of two unported stages, not a
pure statement about the vendor.

**Recommendation:** do not "fix" the order in either direction on the current evidence. Put
it behind an explicit, logged flag with both orders available, and settle it by tracing the
`acquire()` / `ImaTransform` chain. Until then, changing it silently would be exactly the
class of change that produced this session's defect.

### 2.6 Film base per frame vs per roll — **Python is right** [established]

`main.go:468`: `filmBase := frameDminRgbFromPlanes(planeR, planeG, planeB, 4096)` — measured
inside `processImage`, from this frame's own pixels.

`pakon_render.py:448-453` states the rule and `:721-742` implements it: the film base is
FindDmin over the **whole strip**, taken once at open, "because it is a property of the
stock, not of one frame, and measuring it per frame makes the same negative render
differently depending on which frames you happened to export."
`pakon_decode.f135_rom12_to_rpd12`'s `film_base` parameter (`pakon_decode.py:573`, docstring
at `:603-608`) exists for precisely this.

Go's per-frame measurement is the defect that parameter was added to prevent. On a roll with
a mixture of dense and thin frames it makes each frame anchor its own inversion, which is a
per-frame exposure shift with no operator control over it.

### 2.7 The refusals — **Python is right** [established, and this is a product rule]

Two guards exist only in Python:

* `check_film_base` (`pakon_decode.py:528-565`). FindDmin returns **0** as a sentinel when
  the top bin alone exceeds threshold. Feeding 0 into the inversion is not a degraded render,
  it is a fabricated one — `base − c9` clamps to 1, `log10` of it is 0, and every pixel comes
  out at `fpo − 1000·log10(…)`: a black frame, silently. Go clamps and carries on
  (`main.go:475-479`).
* `check_film_class` (`pakon_decode.py:503-521`). `--film-path POSITIVE` selects filmClass 2,
  and the whole downstream chain is written for a negative. Python refuses by name. Go has no
  film-class concept and would render slide film through NegMatrix and then invert it.

`cmd_strip` also refuses `--icc` without an explicit film selection
(`pakon_decode.py:967-976`), and `Roll.engine` mirrors that refusal for the app
(`pakon_render.py:541-545`). Go defaults `-dx 96-1`, `-iso 400`, `-ansel-path CN-Premium`,
`-source-type 1` (`main.go:683-686`) with no way to say "unknown".

### 2.8 ColorAdjust — Go has no equivalent, but it is a no-op today

`pakon_ansel.py:735-746` runs `apply_preference_color_adjust_i16` after FUGC. With
factory-zero params it is skipped (`COLOR_ADJUST_DEFAULT_SKIP_PORTED`), and measured cost is
5 ms. Latent gap, no live divergence. Note also that `docs/46` line 91 places the host
`PIColorAdjustPlanar` at **stage 6**, after Ansel *and* after scale — so Python's in-Ansel
placement is itself worth re-checking, independently of Go.

### 2.9 ICC precision — **Go is right, with a caveat** [mostly established]

Python: `rpd12_to_icc_u8` (`pakon_ansel.py:229-236`) quantises the 12-bit RPD to **u8**, then
runs lcms 8-bit→8-bit (`pakon_ansel.py:775-792`). That throws away 4 of 12 bits *before* the
transform.

Go: `IccRpd12ToSrgb8` (`icc.go:248`) scales RPD12 to u16, evaluates both profiles' mft2 at
16 bits, and only then narrows to u8.

The profile headers settle the intent. I read them directly:

```
Rpd2Pcs_HR200_QS_v5s10.pf   ICC v2.2  scnr  RGB → Lab   A2B0 mft2  grid 31  input table 4096  output table 512
Srgb_v2.pf                  ICC v2.0  spac  RGB → Lab   B2A0 mft2  grid 25  input table  256  output table 4096
```

The RPD-side profile's input table has **4096 entries** — it was built to be indexed by a
12-bit code. Python's u8 quantisation reaches only 256 of those 4096 knots. `docs/58` §1's
chain diagram labels stage 4 "**12-bit RPD in → 8-bit sRGB out**". Python's own docstring
(`pakon_ansel.py:230`) says "for 4096-entry ICC input tables" and then maps to u8 anyway —
because `ImageCms.applyTransform` needs a PIL image and PIL has no 16-bit RGB mode. It is a
library limitation that became a colour decision.

**The caveat, and it is real.** `profile-Rpd2Srgb.dpi` (which I read in
`vendor/ansel/anselinstalldir/dataPathItems/profile/`) declares:

```
dataType = U8      renderIntent = P
colorSpaceBands = 3   colorSpaceMin = 0   colorSpaceMax = 255
```

Read as "the transform's data type is U8", that supports Python. Read as "the *output*
description" — which is what the comment above it in the file says: `# Output description -
datatype, color space, render intent` — it supports Go. I read it as output-only, and the
chain diagram agrees, but it is not airtight.

**Two further divergences inside the ICC hop, neither established:**

1. Go's CLUT interpolation is **trilinear** (`icc.go:132`). lcms2's default for 3D CLUTs is
   **tetrahedral**. They differ, most visibly near the grey axis. The vendor used neither —
   it used `kodakcms.dll` (`tools/ansel/python-pipeline/pakon_kcms_unicorn.py`), whose
   interpolation is untraced.
2. Go hands the PCS u16 straight from `A2B0` to `B2A0`. That is only correct because both
   profiles are ICC **v2** with Lab PCS and therefore share the legacy Lab encoding; lcms
   would handle a v2/v4 mix, Go would silently mis-encode it. Worth an assertion in the
   loader, not just a comment.

### 2.10 Percentiles: histogram vs sort — **Go is right, and it is also 60× cheaper**

`shasta.go:47` takes its anchors from a 4096-bin histogram. `pakon_ansel.py:341-342` uses
`np.percentile` and `np.median`, which are exact order statistics over float64.

The vendor's own idiom is the histogram — `FindDmin` at `0x100093f0` is a histogram walk, and
`pakon_scene_context.find_dmin_code_from_hist` reproduces it. Go's choice is both the
cheaper one and the one that matches the surrounding code. Python's exact percentile is a
*different* number from the vendor's binned one whenever the bin is wide.

### 2.11 Coefficient source — a documented disagreement, currently masked

`pakon_color.load_unit_matrix` docstring (`tools/pakon_color.py:580-598`): `auto` **prefers
the registry**, on the grounds that "TLB reads the `NegMatrix*` REG_SZ values into its
runtime float32 matrix, so those are the values a byte-accurate replay must use".

`poly.go:41-49`: prefers the EEPROM, on the grounds that the registry was written with `%f`
and quantises the ~1e-6 quadratic terms, three of thirty to zero, worth up to ~116 codes of
4095.

Both arguments are correct — they are answering different questions ("replay the vendor" vs
"render the best image"). Today the disagreement is invisible because `REGISTRY_PATH`
(`pakon_color.py:111`) does not exist in the tree, so Python falls through to the EEPROM
(`pakon_color.py:592`). If anyone restores that dump, the two engines diverge by **14–57 RPD
codes** at input `(4000,4000,4000)` (`docs/61-decoder-parity-audit.md`, history-only).

**This must become an explicit, required choice in the new interface**, not an `auto`.

### 2.12 Smaller Go gaps, for completeness

* `SelectShastaKey` (`maps.go:212-252`) ignores the tone-strategy and aggressiveness columns
  by requiring `fs[1] == "any"`; Python's `AnsKeySelector` port matches them properly.
* `tokenMatches` (`maps.go:146-159`) treats any `(lo,hi)` image-size cell as a wildcard.
* Go has no `profile.map` selection; Python resolves `profile_key`
  (`pakon_ansel_maps.py:470`) and then ignores it (`pakon_ansel.py:779-780`). Both hardcode
  the same pair. Equal, and both wrong if a different path ever selects a different profile.
* `main.go` writes an unconditional `*_bypass.png` debug file (`:605-607`) — a second file
  per frame, which the product rule forbids.
* `main.go` prints eight `DEBUG:`/`OUTPUT` lines to stdout per frame (`:369`, `:481`, `:534`,
  `:545`, `:598`…). Any stdout protocol has to move these to stderr first.

---

## 3. The interface contract

### 3.1 What is wrong with the current one

`main.go:671-760` takes `<input.tiff> <output.png>` and writes **two** PNGs. That breaks the
product rule twice over: an intermediate TIFF on the way in, two files on the way out. It
also means the Go side works on a frame that has already been **unsquashed and rotated** —
`write_tiff16` (`pakon_decode.py:943`) calls `to_frame_image` (`:923`) first — so Go's colour
maths runs on resampled pixels while Python's runs on the raw grid. That alone would prevent
byte parity even if every stage agreed.

### 3.2 Options, measured

I benchmarked all three on this machine (M-series, macOS 25.5, Go 1.24.4 driving the 1.25.0
toolchain, Python 3.10.13). Buffer sizes are one frame at each render scale, RGB, u16 in /
u8 out.

**c-shared library via ctypes** — `go build -buildmode=c-shared` (verified working, 6.4 s
build, 1.1 MB arm64 dylib):

| | empty call | preview 720×500 | display 1439×1000 | full 2878×2000 |
|---|---|---|---|---|
| ctypes → Go, zero-copy on the numpy buffer | **2.8 µs** | 0.72 ms | 2.49 ms | 9.18 ms |

(The non-empty figures include a full read-and-write pass over both buffers, so they are the
memory-bandwidth floor, not pure overhead.)

**long-lived process over pipes:**

| | spawn | preview | display | full |
|---|---|---|---|---|
| trivial Go exe, bare spawn | **6.6 ms** | — | — | — |
| framed request/response round-trip | — | 3.48 ms | 18.91 ms | 62.88 ms |

Marginal transport cost over the in-process case: **+16 ms at display, +54 ms at full**, per
render, every render.

**per-frame subprocess:** spawn is 6.6 ms for a trivial binary; the real `pakonpipeline`
loads all its tables (16384-row LUT, 3201-row FUGC, two ICC profiles, 12288-row 3-band LUT,
the `.map`/`.dpi` set) in **~10-30 ms** total wall time — cheap, but you pay it on every
slider nudge, plus the transport cost, plus you lose all warm state.

### 3.3 Recommendation: c-shared library via ctypes

**Reasons, in order:**

1. **Precedent, already load-bearing.** This repo already calls two Go/C shared libraries
   from Python by exactly this mechanism: `tools/libpakon_color.dylib` (loaded at
   `pakon_color.py:718-724`, used at `:767-776`) and
   `tools/ansel/python-pipeline/libpakon_ansel.dylib` (`pakon_sba_apply.py:136-140`). The
   packaging, the path resolution and the numpy-buffer ABI are all solved problems here.
   A process boundary would be a new architecture; a dylib is the existing one.
2. **Slider latency.** 2.8 µs vs 6.6 ms + 19 ms. On a drag settling to *display*, the pipe
   transport alone is ~13 % of the current 147 ms budget and ~2.4 % of the measured 790 ms
   one; the dylib is 0.
3. **No disk round-trip, no serialisation.** The 14-bit frame is already a contiguous numpy
   view of a memmap (`Roll.slice14`, `pakon_render.py:517`). Pass `arr.ctypes.data` and the
   shape; Go reads it in place with `unsafe.Slice`. Nothing is copied and nothing is written.
4. **Cancellation is simpler than it looks.** A slider render is 10–600 ms of pure compute;
   the honest design is *don't cancel, coalesce*. The app already caches by parameter key
   (`pakon_app.py:1600-1607`); a render generation counter that discards stale results is
   sufficient and is what the UI already needs regardless of engine.

**The costs, stated plainly:**

* **A crash in Go takes the whole backend down.** A subprocess would contain it. Mitigation:
  the Go entry point must recover panics at the boundary and return an error code, never
  panic across the FFI line. This has to be enforced by review, because it is not enforced by
  the compiler.
* **Go's runtime lives inside the Python process.** GC and the scheduler are now shared with
  the HTTP server thread pool (`ThreadingHTTPServer`, `pakon_app.py:2225`). Set
  `GOGC`/`GOMEMLIMIT` explicitly.
* **cgo callbacks and the GIL.** Release the GIL around the call (`ctypes.CDLL` does this for
  you on non-`PYFUNCTYPE` calls) so the server stays responsive.

**Rejected: long-lived process over stdin/stdout.** It buys crash isolation at 16-54 ms per
render, needs a framing protocol, needs the eight `DEBUG:` prints moved off stdout first, and
needs its own supervision/restart logic in an app that already supervises a scanner
(`ScanSupervisor`, `pakon_app.py:1017`). If crash isolation later proves necessary, this is
the fallback — but the ABI below is designed so that swapping the transport does not change
the contract.

**Rejected: per-frame subprocess.** Table reload plus spawn plus transport on every nudge,
and it forces intermediates on disk unless you pipe anyway.

### 3.4 The ABI

One entry point, no hidden state, no defaults:

```c
// Returns 0 on success, negative on error. On error, msg receives a NUL-terminated
// explanation (never a partial image), and out is untouched.
int PakonColorRender(
    const PakonColorRequest *req,   // versioned struct, see below
    const uint16_t *in,             // (h, w, 3) contiguous, 14-bit codes in 16-bit words
    int32_t h, int32_t w,
    uint8_t *out,                   // (h, w, 3) contiguous sRGB, caller-allocated
    char *msg, int32_t msg_len);
```

`PakonColorRequest` carries a `version` word first, then every input as an explicit value
with an explicit "unknown" encoding (§4). Two more entry points:

```c
int  PakonColorOpen(const char *ansel_root, const char *fx35_root,
                    char *msg, int32_t msg_len);   // loads tables once, per process
void PakonColorClose(void);
```

**Boundary properties, all of which are contract, not implementation detail:**

* **Input is the raw calibrated 14-bit frame slice on the capture's own grid** — *before*
  `unsquash_transport` and *before* `rot90`. Go must not resample. This reverses the current
  TIFF handoff (§3.1) and is what makes byte parity possible at all.
* Go writes only into `out`. No files, ever. `main.go:605-614` moves to a separate
  `cmd/pakonpipeline` CLI that links the same package for offline work.
* Everything Go currently prints goes to a caller-supplied log callback or to stderr.
  stdout stays clean.
* A recovered panic returns `-EINTERNAL` with the panic text in `msg`.

---

## 4. Metadata: the contract must make guessing impossible

### 4.1 What the app passes today

`job_open` (`pakon_app.py:655-664`) passes `dx`, `film_path`, `sba_key`, `sba_default`,
`max_lines`, `name`. That is the whole set. Notably **not** passed: motor speed, DPI base,
line rate, ISO, exposure. `open_capture` (`pakon_render.py:593-601`) has no parameters for
them either.

Geometry is recovered rather than passed: `_frame_roll` calls
`dec.resolve_transport_scale(capture=…, measured_pitch_lines=…)` (`pakon_render.py:847`) with
**only** those two arguments, so of the five inputs that function accepts
(`pakon_decode.py:803-810`) three are always `None` from the app. The CLI passes all five
(`pakon_decode.py:1060-1067`). ISO reaches colour only indirectly, via `film.lookup(dx)` →
`roll.stock["iso"]` (`pakon_render.py:631-638`) → `scene_from_filmstock`; with no DX there is
no ISO at all.

So the brief's assumption holds: **the app passes strictly less than the CLI.**

### 4.2 The rule

Every field is one of three things, and the wire format must be able to say which:

* **a value**, with its provenance recorded as a string;
* **explicitly unknown**, which the callee may treat as a wildcard *only where the vendor's
  own selector has a wildcard cell*;
* **explicitly refused**, meaning the render must not proceed.

There is no fourth state and no default. Concretely, `dxPart1 = -1` is not "96"; it is
"unspecified", and it is legal only because `sba.map` and `fugc-rgb-lutMap.map` genuinely
have `X` cells for it. `iso = 0` is legal for the same reason. But `filmPath` has **no**
wildcard, because `check_film_class` needs it, so `filmPath = ""` is a hard error.

### 4.3 The fields

| field | type | unknown? | why, and who needs it |
|---|---|---|---|
| `dxPart1`, `dxPart2` | int16 | `-1` = wildcard | `sba.map`, `fugc-*-lutMap.map` selectors |
| `iso` | int32 | `0` = wildcard | `fugc-*-lutMap.map` film rules |
| `filmPath` | enum | **no** | `check_film_class`; POSITIVE must refuse |
| `anselPath` | string | **no** | `sba.map` / `shasta.map` / `profile.map` |
| `sourceType` | int32 | **no** | `sba.map` |
| `sbaKeyOverride` | string | `""` = none | operator override, must be distinguishable from "no match" |
| `coeffSource` | enum `EEPROM`\|`REGISTRY` | **no** | §2.11 — this must stop being `auto` |
| `filmBaseR/G/B` | int32 ×3 | **no** | the ROLL's, measured by the caller (§2.6). `0` is FindDmin's sentinel and must be rejected, not clamped |
| `fugcStageOrder` | enum | **no** | §2.5 — explicit until traced |
| `iccInputDepth` | enum `U8`\|`U12` | **no** | §2.9 — explicit until settled |
| `userSteps[3]` | float32 ×3 | **no** | `apply_correction`'s button-steps; zero is a legitimate value |
| `transportScale` | float64 | **no** | *not used by colour* — carried only so the callee can refuse if it is asked to resample. See §6 of the "what not to move" list |
| `dpiBase`, `motorSpeed`, `lineRate` | int32 | `0` = unknown | not colour inputs; carried for provenance in the log line |

`PakonColorOpen` returns the resolved selection — sba key, shasta key, fugc map file, fugc
LUT file, contrast, coefficient source, and the reason string for each — so the app can show
it. `Roll` already has the fields to hold it (`transport_source`, `framing`) and the app
already surfaces that pattern.

### 4.4 The corresponding app-side work

The app must acquire and pass what it currently does not: ISO independent of DX (an operator
field, since a DX-less roll has none), and the film path as a first-class required choice
rather than one of four alternatives. `Roll.has_film()` (`pakon_render.py:526`) accepts any
of four; the new contract needs the *resolved* film path, not "one of these was truthy".

---

## 5. Packaging

### 5.1 What ships today

`app/package.json:43-61` — `extraResources` copies `../tools` **wholesale** into
`Resources/tools`, filtering only `__pycache__` and `WRITES_LOCKED`. `app/main.js:27-29`:

```js
function repoRoot() {
  return app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');
}
```

and the backend is spawned as bare `python3` off `PATH` (`app/main.js:78`), overridable via
`PAKON_PYTHON`.

### 5.2 The stale-copy problem is worse than "the packaged build has carried old copies"

There is **no packaged build on this machine at all** — `app/dist/` holds only vite output,
there is no `.app`, no `Resources/tools`, and electron-builder has never run here. The
staleness is upstream of packaging, in the artefacts themselves:

* `tools/ansel/pipeline/pakonpipeline` was built 12:24:52; `main.go` was edited 12:27:44 and
  `icc.go` at 12:54:00. **Both binaries predate their own sources.**
* `pipeline_test` (12:28:06) is a *second, different* build — same byte size, different
  SHA-256, 1,592,119 differing bytes. `go version -m` gives identical buildinfo for both
  (`vcs.modified=true`), so **there is no way to tell what source produced either.**
* `tools/libpakon_color.dylib` (Aug 9 13:10) predates `tools/pakon_color_c.c`
  (Aug 10 09:46) by ~20 hours. Same for `tools/pakon_color_cli`.
* All are gitignored (`.gitignore:27-28`, `:37`, `:41`) and untracked.

Because `extraResources` copies `../tools` wholesale, **the contents of a package are a
function of whatever untracked binaries happen to be on the builder's disk.** A stale dylib
ships; a missing one is silently omitted and `pakon_color.py:742-743` falls back to numpy
with no log line. That silent fallback is the same failure shape as the missing inversion.

### 5.3 What to do

1. **Build script, in the repo.** There is currently no Makefile, no shell script and no CI
   anywhere; the only recorded build command in the entire tree is a comment at
   `tools/pakon_pipeline_cli.c:3`. Add `tools/build-native.sh` that builds every native
   artefact with recorded flags, and make it the only sanctioned way.
2. **Universal binaries.** Every existing artefact is `arm64` only (`lipo -info`: non-fat).
   `app/package.json` has no `arch` key, so the dmg/zip is arm64-only too. Build
   `-arch arm64 -arch x86_64` and `lipo` them, or drop Intel explicitly and say so in the
   README.
3. **Pin the toolchain.** `tools/ansel/pipeline/go.mod:2` requires `go 1.25.0`; the installed
   toolchain is `1.24.4`. This builds only because `GOTOOLCHAIN=auto` fetched 1.25.0 into the
   module cache. On a network-isolated builder or with `GOTOOLCHAIN=local` it fails outright.
   Either lower `go.mod` or vendor the toolchain requirement into the build script.
4. **Kill the stale-copy class, don't manage it.** Three changes, together:
   * The build script stamps a `tools/native-manifest.json` with each artefact's SHA-256 and
     the git rev it was built from.
   * `electron-builder` gets an `afterPack` hook that *fails the build* if the manifest is
     missing, if any hash mismatches, or if any source file is newer than its artefact.
   * The loader stops failing silently: if `libpakon_colour.dylib` is absent or its hash does
     not match the manifest, **raise**, do not fall back. A numpy fallback that nobody
     notices is how you ship the wrong engine.
5. **Narrow `extraResources`.** Copy an explicit allow-list of `tools/*.py`,
   `tools/ansel/python-pipeline/*.py`, the manifest and the named native artefacts — not
   `**/*`. Today a stray `.o`, a `.dylib` from a half-finished experiment, and every
   gitignored CLI binary all ship.
6. **Fix the `dist` collision.** vite writes `app/dist` with `emptyOutDir: true`
   (`app/vite.config.mjs:11-12`) and electron-builder's default output is also `app/dist`,
   which `files: ["dist/**/*"]` then globs. Set `directories.output` to something else.
7. **`tools/ansel/pipeline/pipeline_test`** — delete it. It is an untracked duplicate build
   with a misleading name (it is not a Go test binary). The build script should produce one
   artefact with one name.
8. **The Python runtime is still the biggest packaging risk** and is unrelated to Go: the
   packaged app shells out to whatever `python3` is on the user's `PATH` and shows an error
   box telling them to install numpy and Pillow (`app/main.js:388-392`). Whatever happens to
   the colour engine, that has to be solved separately.

---

## 6. Performance: the measured position

Measured today on identical synthetic 14-bit frames (not from `captures/`), same machine:

| | display 1439×1000 | full 2878×2000 |
|---|---|---|
| Go `pakonpipeline -model f135 -dx 96-1 -iso 400` (incl. 2 PNG writes) | **1.11 s** | **4.34 s** |
| Python colour stages only (`scene_rpd12` + `render_scene` + `to_srgb`) | **0.79 s** | **3.19 s** |

Neither is close to the 147 ms / 630 ms that `pakon_render.py`'s docstring records for the
same sizes (`tools/pakon_render.py:62-66`); that measurement predates the inversion work and
should be re-taken.

Breaking the Python 790 ms down at display size:

| | ms |
|---|---|
| `_rpd16` (poly + scale, via the C dylib) | 8 |
| F-135 log inversion | 46 |
| `render_scene` | 668 |
| `to_srgb` (lcms) | 69 |

and inside `render_scene`:

| | ms |
|---|---|
| `apply_balance_shifts` | 2 |
| `shasta_two_anchor_tone` (`np.percentile` + `np.median`) | 84 |
| **FUGC block** | **596** |
| ColorAdjust | 5 |

and inside the FUGC block:

| | ms |
|---|---|
| **`scene_ctx.frame_dmin_rgb_from_planes`** | **554** |
| `build_setlutinfo_apply_lut` | 0 |
| `apply_1d_lut` | 29 |

`find_dmin_code_from_samples` (`pakon_scene_context.py:350`) builds a Python-list histogram
and loops over every sample in pure Python — 4.3 M iterations per frame. The numpy
equivalent already exists in this repo, at `pakon_decode._film_base_code`
(`tools/pakon_decode.py:479-488`), which uses `np.bincount`.

I ran both against the same data:

```
pure-Python loop :   599.2 ms -> (4090, 4090, 4091)
np.bincount      :    10.0 ms -> (4090, 4090, 4091)
identical: True
```

**60× faster, bit-identical, one function, already written elsewhere in the tree.** That
single change takes the display render from ~790 ms to ~250 ms and the full render from
~3.2 s to ~1.0 s — better than the Go pipeline is today, without touching Go.

This is the fact that decides the recommendation. The performance argument for moving to Go
rests on a Python implementation detail that has a 60× fix sitting in the next file.

---

## 7. Recommendation — **SUPERSEDED by §12**

> **This section's conclusion was not adopted.** The owner decided the other way: consolidate
> on Go. The *reasoning* below is still worth reading — it is the honest case against, and
> §12 answers it point by point rather than pretending it was wrong. Note in particular that
> this section's own closing paragraph ("If the owner still wants Go, the preconditions
> are…") is the plan that was actually followed.

**Do not consolidate onto `tools/ansel/pipeline/` as it stands.** Consolidate onto the
Python implementation, fix the two things Go is right about inside it, and keep Go as an
independent oracle rather than the product engine — with the door open to moving the *stage
kernels* (not the policy) into a Go c-shared library later, once there is a harness that can
prove such a move changed nothing.

The reasoning:

1. **The correctness argument runs the other way.** §2.1–2.4, 2.6, 2.7, 2.12 are Python
   right / Go wrong, and §2.1 alone means Go applies a different tone LUT to every stock.
   §2.9 and §2.10 are Go right / Python wrong, and both are a few dozen lines to port into
   Python. Moving to Go means re-porting a dozen DLL-cited leaves that already exist and are
   golden-tested; moving Go's two wins into Python means writing two functions.
2. **The performance argument does not survive measurement** (§6).
3. **The refusals are the product.** `check_film_base`, `check_film_class` and the
   `--icc` film-selection refusal are the reason this app does not silently emit wrong
   images. They live in Python, they are woven into `Roll` and the job model, and they are
   the least portable part of the whole system.
4. **The actual pain — "every fix applied two or three times" — is not Python-vs-Go.** It is
   `cmd_strip` and `render_frame` being two hand-maintained arrangements of the same stages.
   That is fixable in a day, in Python, and it is what would have prevented the defect that
   shipped. Look at the table in §1.1: rows 5–19 are *already* the same calls in both Python
   entry points; they diverged only in what order and with what arguments they were called.
   Go was never in that loop — it is not wired into the app at all (`grep` for
   `pakonpipeline` across `*.py`/`*.js`/`*.jsx` returns zero hits).

**If the owner still wants Go**, the preconditions are: the parity harness first (§8 step 1),
then §2.1, §2.2, §2.3, §2.4, §2.6 and §2.7 fixed *in Go* and proven equal to Python, then
the ABI in §3.4, then packaging §5. That is a substantially larger project than the plan
below and it starts by making Go agree with Python — which is the same work, in the harder
direction.

---

## 8. Migration plan

Each step is independently verifiable and independently revertable. No step leaves the app
rendering worse than it does now. Steps 1–4 are worth doing under *either* recommendation.

### Step 1 — Build the parity harness. **Nothing else starts until this passes.**

It does not exist (§0). Build `tools/test_colour_parity.py`, modelled on the working
byte-comparison in `pakon_render.cmd_verify` (`tools/pakon_render.py:1261-1325`):

* fixtures: the synthetic frames used in §6 (checked in as a generator, not as data), **plus**
  `captures/strip_cal.bin` locally where available;
* compares, per frame: `cmd_strip`'s `frames/NN_srgb.png`, `render_frame(scale="full")`, and
  the Go binary's PNG;
* reports per-channel mean, max abs delta, and differing-sample count at every intermediate
  tap — RPD12 after stage 2, after inversion, after balance, after FUGC, after Shasta, after
  ICC — not just at the end. A single end-of-chain number cannot localise a regression.
* **Establish the reference table the brief assumed exists**, and check it in: per-frame
  means at every tap for `strip_cal.bin`, generated by the harness, so future steps have a
  fixed target.

*Verification:* the harness runs and reports; Python-vs-Python is byte-exact today
(`cmd_verify` already claims this) and must stay so.

### Step 2 — Collapse Python's own duplication. **This is the fix for the stated pain.**

Extract one module, `tools/pakon_colour_chain.py`, holding the ordered stage sequence
exactly once: stage 2 → inversion → balance → tone/FUGC → ICC, with the refusals in it.
Rewrite `render_frame` (`pakon_render.py:950`) and `cmd_strip`'s colour block
(`pakon_decode.py:1131-1197`) to be thin callers. Nothing changes numerically.

*Verification:* Step 1 harness reports zero differing samples on every frame, before and
after. This is the strongest guarantee in the plan and it is available immediately.

### Step 3 — The `bincount` fix.

Replace the pure-Python histogram in `pakon_scene_context.find_dmin_code_from_samples`
(`:350`) with the `np.bincount` form already in `pakon_decode._film_base_code`
(`pakon_decode.py:479-488`). Keep the vendor's walk (`find_dmin_code_from_hist`) untouched.

*Verification:* harness reports **byte-identical** output (proven above on random data), and
the timing table in §6 drops from 554 ms to 10 ms. If it is not byte-identical, stop.

### Step 4 — Metadata contract, in Python.

Introduce the request struct of §4.3 as a Python dataclass, with `coeffSource`,
`fugcStageOrder` and `iccInputDepth` **required**. Make `open_capture` and `render_frame`
take it. Make the app fill it, and refuse rather than default. Log the resolved selection.

*Verification:* harness passes with the struct populated to today's effective values; a
second harness case asserts that omitting `filmPath` raises rather than rendering.

### Step 5 — Take Go's two wins, one at a time, behind the flags from step 4.

5a. **`iccInputDepth = U12`.** Port `icc.go`'s mft2 evaluator to numpy (it is ~80 lines and
fully vectorisable: two 1-D interps and a trilinear gather). Keep `U8` as the default until
5c.

5b. **Histogram percentiles in Shasta.** Replace `np.percentile`/`np.median`
(`pakon_ansel.py:341-342`) with the 4096-bin form from `shasta.go:47`.

5c. **Decide the defaults** on evidence from the harness and by eye on a real roll, and
record the decision in this document. Note that 5a's default flip is a *deliberate* visible
change; it must be announced, not slipped in.

*Verification:* for each, the harness shows the intended tap changing and every earlier tap
unchanged. Go's output becomes a third column that should now agree more closely at the ICC
tap — the first time the Go binary earns its keep.

### Step 6 — Settle the open questions (§2.5, §2.9, §2.11).

Trace the `acquire()` / `ImaTransform` chain for stage order. Decide the coefficient source
policy. These are research, not engineering, and they gate nothing above.

### Step 7 — *Only if* §6's numbers are still short of budget: native kernels.

Move the per-pixel loops — poly, inversion, LUT applies, ICC eval — into a Go c-shared
library with the ABI of §3.4, called from `pakon_colour_chain.py` by ctypes, exactly as
`libpakon_color.dylib` is today. Policy (selection, refusals, film base, metadata) stays in
Python. Packaging per §5.

*Verification:* the harness's Python and native paths must agree byte-for-byte at every tap,
with the native path behind an env switch so both can run in the same session.

---

## 9. What must NOT move to Go

* **Capture decode and calibration** — `load_u16`, `segment_lines`, `to_rgb14`,
  `apply_unit_calibration` (`pakon_decode.py:94-296`). Working, cheap (~6 s of a 26 s open),
  and tied to the memmap cache the whole render path depends on.
* **Framing** — `pakon_framing`'s five-phase cascade and its per-frame `phase` /
  `framing_risk` provenance (`pakon_render.py:787-843`). It is the app's most user-visible
  correctness feature and has no colour coupling at all.
* **Transport geometry** — `resolve_transport_scale` and `unsquash_transport`
  (`pakon_decode.py:803-921`). Deliberately *after* colour (`pakon_render.py:983`);
  resampling 14-bit codes before the polynomial is a different operation. The Go interface
  must be structurally unable to resample (§3.4).
* **The refusals** — `check_film_class`, `check_film_base`, the `--icc` selection refusal,
  and `Roll.engine`'s mirror of it. These are policy, they need to produce operator-readable
  prose, and they are the product's honesty guarantee.
* **The parameter model and user corrections** — `DEFAULT_PARAMS`, `UNAVAILABLE_CONTROLS`,
  `merged_params`, `apply_correction`, `_apply_geometry` (`pakon_render.py:134-177`,
  `:905-947`). `UNAVAILABLE_CONTROLS` in particular is a list of things the app deliberately
  refuses to invent; it belongs next to the UI, not in a rendering kernel.
* **Export, naming, sidecars, the job model** — `plan_export` / `export_frame`
  (`pakon_render.py:1106-1220`), the whole of `pakon_app.py`.
* **Film-stock lookup** — `pakon_filmstock` / `research/film-products.json`. Data, not maths.
* **The `.map` / `.dpi` selection logic** — this is the surprising one. `maps.go` looks like
  the natural thing to move, but §2.1, §2.2 and §2.12 are all selection bugs, and the Python
  port is the one with the instruction citations. Selection is policy; keep it in Python and
  pass the *resolved* file paths across the boundary (§3.4's `PakonColorOpen` returns them).
  A native layer that re-derives its own selection is how the two engines drift again.

---

## 10. Risks, ranked

1. **The plan's instrument does not exist** (§0). Every "prove equivalence at each step"
   claim in the brief is currently unbacked. Mitigation: step 1, and nothing before it.
   *Consequence if ignored:* the next silent divergence ships exactly like the last one.
2. **Adopting Go's FUGC selection would visibly change every render** (§2.1) — a different
   tone LUT per stock, up to 60 codes. If consolidation onto Go proceeds without fixing this
   first, every image changes and nobody will be able to say whether it improved.
3. **Go's per-frame film base** (§2.6) makes the same negative render differently depending
   on which frames were exported. This is the hardest class of bug to notice and the worst to
   discover after an export.
4. **The build/packaging pipeline cannot currently reproduce anything** (§5.2). Two
   same-sized, different-content binaries with identical buildinfo, both older than their
   sources, all untracked, swept into the package by a `**/*` glob. Adding a third native
   artefact to that pipeline before fixing it multiplies the problem.
5. **Silent fallbacks** — `pakon_color.py:742-743` and `pakon_sba_apply.py:136-140` both
   degrade to numpy without a word if the dylib is missing or the wrong arch. Any new native
   dependency must fail loudly (§5.3.4).
6. **The 12-bit ICC change is a deliberate visible change** (§2.9/5a). It should improve
   gradients, but it will change every pixel. It needs to be announced and reversible.
7. **In-process Go shares a crash domain with the backend** (§3.3). Panic recovery at the
   boundary is a review discipline, not a compiler guarantee.
8. **`go.mod` requires a toolchain newer than the one installed** (§5.3.3). Works today only
   because a network fetch already happened.
9. **The documents the code cites are not in the tree.** `docs/58` is referenced 63 times in
   comments; it exists only in git history. Anyone verifying a colour claim has to know to
   run `git show 70b6a65:docs/58-colour-pipeline.md`. Consider restoring them, or at least
   noting the rev in `docs/00-overview.md`.

---

## 11. What I could not establish

Stated plainly, because a guess here is worse than a gap:

* **Whether balance → Shasta → FUGC or balance → FUGC → Shasta is correct** (§2.5). The
  evidence leans slightly toward Go's order, and `docs/58` §16.5 explicitly leaves open the
  one fact that would settle it. I did not resolve it and I do not think it should be changed
  until someone does.
* **Whether the vendor's Ansel ICC hop is 8-bit or 12-bit at its input** (§2.9). The chain
  diagram and the 4096-entry input table say 12-bit; `dataType = U8` in
  `profile-Rpd2Srgb.dpi` can be read either way. I read it as an output description, which is
  what the file's own comment says, but that is an interpretation.
* **Which CLUT interpolation the vendor used** (§2.9). Not trilinear-vs-tetrahedral as a
  matter of taste — `kodakcms.dll` is a third implementation and nobody has traced it.
* **Which FUGC mode the F-135 path runs at.** `docs/58` §7 tells us mode 2 is *not ported*,
  which is why Python's default is right *for us*; it does not tell us what the scanner did.
  `CAP_MODE_SELECT = 0xC` (`pakon_fugc.py:180`) is a runtime field.
* **Whether `_LIB_C`'s C polynomial and Go's `PolyPixel` agree bit-for-bit.**
  `tools/test_gold400_parity.py` proves C == numpy; nothing proves Go == either. The float32
  spill emulation is present on all three sides (`poly.go:21`, `pakon_color.py:784-787`) but
  unverified across the language boundary. Step 1's harness should cover it.
* **The real per-frame timings on a real roll after the inversion landed.** My §6 numbers are
  on synthetic frames; `pakon_render.py:55-66`'s table is stale by roughly 5×. Someone should
  re-run `pakon_render.py check`.

---

# 12 — Decision: consolidate on Go. Phase 1 report and phase 2 plan.

**Date:** 2026-08-10. **Supersedes §7.**

## 12.0 The decision, and what it costs

The owner has decided: **the colour pipeline consolidates on Go, and the app renders through
it.** §7 recommended the opposite. That recommendation is superseded, not retracted — its
findings drove every fix below — but the direction is settled and this section does not
re-argue it.

The honest cost, stated once and plainly:

* **§7's correctness argument was right about the code, and phase 1 is the bill for it.**
  Six of the seven divergences §2 found were Go-wrong / Python-right. Closing them was a
  rewrite of Go's FUGC selection, its FUGC bias, its film-base policy and its whole
  parameter model. That work is done (§12.2) and it took the direction §7 predicted it would:
  Go was made to agree with Python.
* **§7's performance argument still stands and the decision does not rest on speed.** On the
  256×384 harness fixture: Python 0.20 s, Go 0.42 s. Go is *slower*, and the `np.bincount`
  fix §6 identified would widen that further. Anyone justifying this migration on performance
  is justifying it on a number that has never been measured in Go's favour. The case for Go
  has to be made on something else — one language for the render kernel, a typed request
  struct the compiler checks, and no Python runtime in the shipped app — and those are
  legitimate, but they are not speed.
* **The refusals had to be ported, not moved.** §7.3 called them "the least portable part of
  the whole system". They are now duplicated: `check_film_base` / `check_film_class` exist in
  both `tools/pakon_decode.py` and `tools/ansel/pipeline/request.go`. Until phase 2 deletes
  the Python render path, **a refusal fixed in one place is a refusal still broken in the
  other.** That is the exact pain the consolidation is meant to end, and consolidating onto
  Go makes it temporarily worse before it makes it better.
* **The ICC hop will not reach parity, and should not be expected to.** Go evaluates its own
  mft2; Python calls littleCMS. They differ by up to 43 of 255 codes on real pixels (§12.3).
  One of them has to become the reference and the other has to be judged against it by eye,
  because there is no third implementation to arbitrate — the vendor's was `kodakcms.dll` and
  nobody has traced it.

## 12.1 The parity harness — `tools/pakon_parity.py`

§0 established there was no Go-vs-Python comparison anywhere: no `*_test.go`, no script, and
every "within ~2 %" figure in the tree was prose about an unrelated round-trip. That is fixed
first, because nothing else can be verified without it.

```
python3 tools/pakon_parity.py                 # one command, ~3 s including the Go build
python3 tools/pakon_parity.py --sensitivity   # also price the two unsettled choices
```

**What it does.** Generates a deterministic synthetic 14-bit frame, runs both engines over
*the same array with the same explicit parameters*, and reports divergence **per stage**:

| tap | what it is |
|---|---|
| `poly` | stage 2 polynomial output, linear 12-bit (TLB `fcn.1000d880`) |
| `inv` | after the F-135 negative→positive log, RPD-12 |
| `balance` | after `applyBalanceShifts` |
| `shasta` | after the Shasta two-anchor tone stand-in |
| `fugc` | after the FUGC apply LUT |
| `ansel` | the toned RPD-12 handed to the ICC hop (post-ColorAdjust) |
| `icc` | 8-bit sRGB |

`shasta` and `fugc` are tapped **by name, not by position**, so the two stage orders can be
compared against each other as well as across engines. Per tap it reports the differing-sample
percentage, the fraction differing by more than one code, and the mean / p99.9 / max absolute
delta per channel — a single end-of-chain mean cannot localise a regression, which is the
whole point.

**Design decisions worth knowing:**

* **Synthetic fixture, checked in as a generator, never as data.** It is deterministic, it
  spans the 14-bit domain far more evenly than a photograph, and — this took two attempts —
  its clear-film leader is sized against the **polynomial's** 4095 ceiling, not the sensor's
  16383. A leader that clips after stage 2 drives `FindDmin` to its sentinel and both engines
  correctly refuse to render, which makes for a useless fixture. `--raw` takes a real frame
  for local runs. **Nothing from `captures/` is ever written inside the repo:** the fixture,
  the binary and the taps all go to a scratch directory outside it.
* **The Go binary is rebuilt from source into scratch on every run.** §5.2 found two
  same-sized, different-content binaries in `tools/ansel/pipeline/` with identical buildinfo,
  both older than their own sources. A harness that measured one of those would be measuring
  an unknown program.
* **The Python column is checked against itself.** The Python driver is a re-statement of
  `AnselEngine.render_scene`'s call sequence with taps inserted. That is only worth anything
  if it *is* the same computation, so at `--stage-order shasta-fugc` (render_scene's own
  order) the harness asserts the driver and `render_scene` agree **bit-for-bit** at the
  `ansel` tap and aborts if they do not. It reports **0 differing samples** today.
* **It fails the run if Go writes to stdout.** §3.4 requires stdout to stay clean for the
  phase-2 transport; this is where a regression on that shows up. All eight `DEBUG:`/`OUTPUT`
  lines §2.12 complained about now go to stderr.

## 12.2 The gap fixes

All in `tools/ansel/pipeline/`. Each closes a numbered finding from §2.

### 12.2.1 The FUGC map (§2.1) — fixed

`maps.go` now resolves the lutMap the way `AnsFugcMapping` (`0x101fb140`) does: read `mode`
from `fugc/fugc-defaultParams.dpi`, `RGB` → `fugc-rgb-lutMap.map`, `NEUTRAL` →
`fugc-neutral-lutMap.map`. `fugc-lutMap.map` (08/28/2002) is no longer opened by anything;
it is the original both variants were split out of and nothing in the DLL selects it. If the
dpi carries no `mode` the loader **refuses** rather than falling back.

Measured on the shipped data:

```
seed LUT rows differing: 705 of 4096 (indices 237..943), max delta 60
render impact, post-FUGC RPD-12, on the harness fixture:
    7.41 % of samples differ, mean |d| 0.06 / 1.15 / 0.07, max 2 / 29 / 2
```

Go and Python now select the **same file** — `NoShift_fugc-generic0225.lut` — for the first
time. The harness prints both engines' choice on every run.

`aTableDmin` is now read from the selected `.lut` header and `aFilmAimDmin` from
`fugc-defaultParams.dpi`, instead of the hardcoded `{500,500,500}` / `{500,1000,1000}`.
§2.4's note that those happened to be correct for every file in this install is confirmed —
this was a latent hazard, and it is neither latent nor a hazard now.

### 12.2.2 The FUGC bias formula and `ebp18` (§2.3, §2.4) — fixed

`fugc.go` gains `signedDiv3` (the `imul 0x55555556` magic at `0x101f7a08` with the
sign-correction add at `0x101f7a1f`) and `FugcWorkBias`, which is the vendor's nine-term
expression:

```
bias = avg3( max(0, int16(60ec_i + arg_i)) ) − avg3( int16(60f8_i) )
```

`BuildMode2ApplyLut` now takes `argEbp18` and calls `fillSetLutInfoAimWords` first, so the
frame's own Dmin reaches the aim through the `0x101fc3c4` policy branch instead of the
fallback being taken unconditionally. `ebp18` is measured on the **post-balance, pre-Shasta**
array, which is where `pakon_ansel.py:705-710` measures it.

Measured on the harness fixture's actual aim words:

```
mode-2 bias: old (green-only, no clamp, no averaging) = 792
             vendor (0x101f79b0)                      = 703      delta 89
mode-2 apply LUT: 1824 of 4096 entries differ, max delta 89
```

**Which side matches the vendor:** Python. The formula is instruction-cited to `0x101f79b0`
in `pakon_fugc.py:fugc_work_bias`, term by term, including the `max(0, …)` floors at
`0x101f79c0 / d2 / e4` and the `+1` rounding bias inside each division. Go's three-term
green-only expression had no citation behind it. This is not a judgement call.

While in there: `setLutInfoChannel` now **refuses** a negative offset instead of falling
through its bounds check and writing `n-1` (white) for every index. `pakon_fugc.py` raises on
the same condition; Go was silently blowing out the channel. The mode-2 plane fill's
off-by-one negative tail (§2.3's closing note) was checked and is genuinely harmless — Go's
extra index writes `seed[n-1]+ax`, which is exactly the `last` value Python's second loop
writes there.

**FUGC mode is now an explicit, logged flag** (`-fugc-mode`, default **1**). §11 lists which
mode the F-135 path runs at as *not established*, and `docs/58` §7 lists mode 2 as **not
ported**; defaulting to the ported branch is what Python does and is the only defensible
default. It is a stated choice now rather than a hardcoded `if model == "f135"`.

### 12.2.3 Film base per roll (§2.6) — fixed

`main.go` no longer measures the film base. `-film-base R,G,B` is **required** on the f135
path and is the ROLL's — `FindDmin` over the whole strip, supplied by the caller. There is an
explicit, loudly-logged `-film-base-from-frame` escape hatch for offline analysis of a frame
with no roll context; it is never correct for the app and says so on stderr every time.

### 12.2.4 The refusals (§2.7) — fixed

`request.go` ports both, with the same prose the Python versions produce:

* `CheckFilmBase` — 0 is `FindDmin`'s "no valid Dmin" sentinel, not a measurement. Feeding it
  to the inversion emits a black frame silently. Go clamped to 1 and carried on; it now
  refuses, and reports the per-channel clipped-pixel percentage so the operator knows why.
* `CheckFilmClass` — `-film-path POSITIVE` selects filmClass 2 and the F-135 reversal branch
  is not ported. Go had no film-class concept at all and would render slide through the
  NegMatrix and then invert it.

Every input that has no vendor wildcard cell is now required and has no default:
`-film-path`, `-iso`, `-coeff-source`, `-film-base`. `-coeff-source` in particular is the
§2.11 disagreement made explicit — there is no `auto`, the caller says `eeprom` or
`registry`, and a mismatch between the named source and the file's actual format is an error
rather than a silent re-parse. Verified refusals:

```
(no -film-path)          no film path: pass -film-path ColNeg|BnW|IMPORTED|POSITIVE …
-film-path POSITIVE      selects filmClass 2 (colour reversal, PosMatrix at TLB this+0xc8) …
(no -coeff-source)       required for f135: eeprom | registry. There is no 'auto' — §2.11
(no -film-base)          required for f135: the ROLL's film base … not this frame's
-film-base 3010,0,3583   FindDmin found no film base (channel(s) [1] came back 0 …)
(no -iso)                the fugc lutMap picks the contrast LUT from the film speed …
```

### 12.2.5 Stage order (§2.5) — **settled from the binary. Go was right.**

`-stage-order fugc-shasta | shasta-fugc`, defaulting to **`fugc-shasta`** — the vendor's.
§2.5 and §11 both recorded this as unresolved and §2.5 recommended not changing it in either
direction "on the current evidence". There is new evidence: it was traced in PakonIMAu.dll
and it is now established. The full chain and its addresses are in §12.4.1. Short version:
the render transform chain is built **strictly linearly in parameter-pack order**
(`AnsImaBuilder::getImaTransformGroup` @ `0x100346a0`), and `AnsCnPremiumPath::exportParameterPack`
(`0x10050e20`) emits balance as operand 2, FUGC as operand 3 and Shasta as operand 7.

Both orders stay implemented and tapped by name, because the harness has to be able to price
the difference and because §12.4.1 turns up a second question that may matter more.

### 12.2.6 ICC precision (§2.9) — **settled from the binary. Go was right.**

`-icc-input u12 | u8`, default **u12**. The vendor does not quantise to 8 bit before the CMS;
`dataType = U8` in `profile-Rpd2Srgb.dpi` is the *output* description, exactly as the file's
own comment says, and the DLL says so literally (§12.4.2). `u8` is kept only so the harness
can put the two engines on the same footing at that tap and separate the *implementation*
difference from the *bit-depth* difference.

### 12.2.7 Python's two wins (§2.9, §2.10) — confirmed, one already present

* **Histogram percentiles: already correct in Go, confirmed.** `dmin.go`'s
  `findDminCodeFromSamples` is a 4096-bin histogram; `shasta.go`'s anchors come from a
  4096-bin histogram. The only `sort` call in the whole package is in `LinkedPercentileTone`
  — which has **zero callers**. It is dead code on every path. Nothing to fix; the `np.bincount`
  item is a Python-side change and belongs to whoever owns `pakon_scene_context`.
* **The metadata contract: implemented.** `-scan-json` reads the capture sidecar
  (`tools/pakon_scan.py:write_capture_metadata`, the same file
  `pakon_decode.load_capture_sidecar` reads) and takes `film.film_path` and `film.dx` from it
  where the caller did not state them. Explicit flags always win; the provenance of every
  field is recorded and logged. It deliberately does **not** supply ISO — a DX-less roll has
  none, and inventing one is the class of guess this contract exists to prevent.

### 12.2.8 Smaller items from §2.12

* The unconditional `*_bypass.png` second file is now opt-in (`-bypass-png`). One render, one
  file, by default.
* The eight `DEBUG:` / `OUTPUT` stdout lines are on stderr. The harness fails the run if
  anything reaches stdout.
* `-raw-in H,W` reads a bare `(h, w, 3)` little-endian u16 blob — the calibrated frame on the
  capture's own grid, *before* unsquash and *before* `rot90`. §3.1 identified the TIFF
  hand-off as itself a divergence (Go's colour maths ran on resampled pixels while Python's
  ran on the raw grid); this is the shape phase 2's ABI passes by pointer, and it is why byte
  parity is achievable at all. The TIFF path still works for existing callers.

Not done, and deliberately: `SelectShastaKey`'s tone-strategy columns, `tokenMatches`'
`(lo,hi)` wildcard, and `profile.map` selection (§2.12). None is on the CN-Premium path this
install takes, none changes a number today, and all three are selection logic that phase 2
has to revisit anyway.


## 12.3 Parity, measured

Fixture: synthetic 256×384 (294 912 samples), DX 96-1, ISO 400, ColNeg, CN-Premium,
sourceType 1, EEPROM coefficients, FUGC mode 1, `-stage-order fugc-shasta` (the vendor's),
roll film base (3009, 3828, 3582) supplied identically to both engines. Both engines select
`NoShift_fugc-generic0225.lut` via `fugc-rgb-lutMap.map`, both compute setShifts
(688, 292, 130), both measure `ebp18` = (2300, 2246, 2067) on the post-balance array and both
take the same `ebp18` policy branch (fail → ParamsDpi aim). The harness prints all of that on
every run so a selection drift cannot hide behind a pixel number.

**As the two engines actually run today** — i.e. including the 12→16→12-bit round trip
`pakon_decode.render_rpd` performs on the Python side, which Go does not:

| tap | differ % | >1 code % | mean abs Δ R/G/B | max abs Δ R/G/B |
|---|---|---|---|---|
| `poly` | 99.57 | 0.00 | 0.015 / 0.015 / 0.015 | 0.031 / 0.031 / 0.031 |
| `inv` | 99.88 | 0.00 | 0.005 / 0.004 / 0.004 | 0.026 / 0.018 / 0.016 |
| `balance` | 0.43 | 0.00 | 0.002 / 0.006 / 0.005 | 1 / 1 / 1 |
| `fugc` | 0.43 | 0.01 | 0.002 / 0.006 / 0.005 | 1 / 2 / 1 |
| `shasta` | 0.41 | 0.41 | 0.012 / 0.027 / 0.034 | 5.5 / 5.2 / 7.1 |
| `ansel` | 0.41 | 0.41 | 0.011 / 0.026 / 0.035 | 5 / 5 / 8 |
| `icc` | 45.51 | 7.57 | 0.84 / 0.52 / 0.64 | 43 / 14 / 23 |

**With that round trip removed** (`--no-rpd16-roundtrip`), which isolates what the two
engines themselves disagree about:

| tap | differ % | >1 code % | max abs Δ R/G/B |
|---|---|---|---|
| `poly` | **0.00** | 0.00 | **0 / 0 / 0** — bit-identical |
| `inv` | 80.94 | 0.00 | 4.5e-13 / 9.1e-13 / 9.1e-13 — float64 `log10` noise |
| `balance` | 0.02 | 0.00 | 0 / 1 / 1 |
| `fugc` | 0.02 | 0.01 | 0 / 2 / 1 |
| `shasta` | **0.00** | 0.00 | **0 / 0 / 0** — bit-identical |
| `ansel` | **0.00** | 0.00 | **0 / 0 / 0** — bit-identical |
| `icc` | 45.48 | 7.57 | 43 / 14 / 23 |

**Read these carefully, because the headline is genuinely good and the caveat is genuinely
load-bearing.**

1. **At the vendor's stage order, with the Python-side 16-bit round trip removed, the two
   engines produce a BIT-IDENTICAL toned RPD-12 image.** Every colour stage from the
   polynomial to the hand-off to the ICC transform now agrees exactly on 294 912 samples.
   That is the result phase 1 was for, and before this week nothing in the tree could have
   said it either way.
2. **The stage-2 polynomial is bit-identical across the language boundary**, which settles
   §11's "Whether `_LIB_C`'s C polynomial and Go's `PolyPixel` agree bit-for-bit" — they do,
   float32 spill emulation included.
3. **The Shasta stand-in is bit-identical**, so Go's 4096-bin histogram percentiles and
   `np.percentile` agree *on this data*. They remain different algorithms (`np.percentile`
   interpolates; the histogram returns the first code whose cumulative count exceeds the
   target) and can diverge where bins are wide. Latent, not live.
4. **The 12→16→12 round trip is the entire source of the sub-code noise in the first table.**
   It is a Python-side artefact of `render_rpd` storing 12-bit values as u16, worth up to
   0.031 codes at `poly` and — once it flips an integer-truncation boundary — up to 8 codes
   by the `ansel` tap. **Phase 2 must not carry it across the ABI.**
5. **The ICC hop is the only substantive divergence left, and it will not close on its own.**
   45.5 % of samples differ, 7.6 % by more than one code, up to 43 of 255. Both columns are at
   `u8` in these runs, so this is **not** bit depth — it is Go's own mft2 evaluator with
   trilinear CLUT interpolation against littleCMS with tetrahedral. Binned by the input
   pixel's chroma (max−min RPD), same fixture:

   | input chroma | n | mean max-channel Δ | max |
   |---|---|---|---|
   | 0–20 | 58 | 0.88 | 2 |
   | 20–60 | 343 | 0.99 | 3 |
   | 60–150 | 1 995 | 0.98 | 5 |
   | 150–400 | 8 125 | 1.28 | 39 |
   | 400+ | 14 055 | 1.45 | 43 |

   The error **grows with chroma**, which rules out the simplest story (the two
   interpolations differing near the grey axis) and points at CLUT interpolation error where
   the transform is most nonlinear. Neither implementation is the vendor's — that was
   `kodakcms.dll`, and §12.4.2 traces how it was *called* but not how it interpolates.

   At Go's own default (`-icc-input u12`) the gap against Python's u8 lcms widens as expected:
   54.7 % of samples, 19.4 % by more than one code, max 46 / 14 / 24. **That widening is
   correct and deliberate** — §12.4.2 establishes the vendor fed the CMS 16-bit data — but it
   means switching the app to Go changes every pixel of the ICC output, visibly. It has to be
   announced, not slipped in.

**Sensitivity — what the choices cost**, measured within one engine so nothing else varies:

| question | tap | differ % | mean abs Δ R/G/B | max |
|---|---|---|---|---|
| stage order, vendor `fugc-shasta` vs Python's `shasta-fugc` | `ansel` | 90.68 | 59.2 / 81.7 / 55.4 | 688 / 792 / 630 |
| stage order, same | `icc` | 57.05 | 2.3 / 5.4 / 2.7 | 24 / 46 / 21 |
| ICC input depth, `u12` vs `u8` (Go) | `icc` | 41.80 | 0.63 / 0.52 / 0.60 | 24 / 6 / 12 |

**The stage order is worth roughly sixty times every parity gap in this document combined.**
§2.5's instinct — "do not fix the order in either direction on the current evidence" — was
right for its evidence and is vindicated by its own price tag. There is now evidence, and it
says Python has been rendering in the wrong order. **Every image the app has produced is
affected**, by a mean of 2.3–5.4 sRGB codes and up to 46. That is the largest single
correctness change in this document and it belongs in the phase-2 announcement.

**Timing**, same fixture and machine: Python 0.20 s, Go 0.42 s (Go excludes the build,
includes table load). Consistent with §6: Go is slower. Recorded because §12.0 says the
decision does not rest on speed, and a number that inconvenient should be visible rather than
quietly absent.

## 12.4 Established from the binary vs assumed

The brief asked to be explicit about this, and the distinction matters more than the
conclusions. The DLLs are not in the repo. They were found in the SDK ISO the repo already
carries — `research/sdk/PAKONF135.iso` — extracted with `7z x` to a scratch directory
(`PakonIMAu.dll` 7 598 080 bytes, `TLB.dll` 536 576, `kodakcms.dll` 540 672). PakonIMAu.dll
is PE32 x86 based at `0x10000000`, **not stripped**, and retains per-function assert strings
naming the C++ source files (`cnMethods.cpp`, `balanceMethods.cpp`, `ImaICCProfile.cpp`, …),
so function identification below is by the DLL's own names, not by inference. Every address
`docs/58` cites lands on a real function start, so this is the same build those documents
were written against; no rebase was needed. Tooling was radare2 6.1.8 with r2ghidra.

### 12.4.1 Stage order — **ESTABLISHED**

Three findings, each from disassembly:

**(a) The render chain is strictly linear in parameter-pack order.**
`AnsImaBuilder::getImaTransformGroup` @ `0x100346a0` walks the operand list by index,
switches on each operand's type and connects it to the previous one. Loop tail
`0x1003a9d5…0x1003aa64`: the first operand is bound to `"input"` (`0x1003a9e3`), each
subsequent one is `connect(prev, cur)` (`ImaTransform::connect` `0x1033fa00`, called at
`0x1003aa33`), and after the loop `prev` is bound to `"output"` (`0x1003aac3`).
`0x1033fa00` is confirmed as `connect()` by its own error string at `0x105b8ad4`. **There is
no reordering stage** — pack order *is* render order. This is what §2.5 said would settle it.

**(b) The CN-Premium pack order.** `AnsCnPremiumPath::exportParameterPack` @ `0x10050e20`
emits, in order: noise (`0x101124e0`), **balance** (`BalanceMethods_export` `0x101142a0`),
**FUGC** (`ColorNegativePath::exportFugc` `0x100ff770`), area (`0x100e2080`), falloff
(`0x100ff400`), flare, **Shasta**, **ColorAdjust**, sharpening (`0x100ffb00`), defects
(`0x100e0db0`). The flare/Shasta/ColorAdjust operands are `apuAppendParamPack` calls at
`0x10051a6d` / `0x10051c02` / `0x10051c9a` whose capability pointers are the ones stored
after the `"flare"` / `"shasta"` / `"manualBalanceTwo"` lookups at `0x10051224` /
`0x10051320` / `0x1005155a` — read from raw `[ebp-N]` operands rather than from r2's
variable naming. ContrastAdjust is folded into the Shasta operand (guard at `0x10051bdf`),
not a separate stage.

**(c) It also closes `docs/58` §16.5.** `BalanceMethods_export` appends `filmLut`
(`0x1011442b`), then `scpLut` (`0x10114698`), then one shift LUT built from the labelled
`"color"` / `"flesh"` / `"afterSCPLutSba"` / `"sba"` contributions (`0x10114757…0x101148a5`).
Followed by operand 3 that is `filmLut → scpLut → shift → fugc` — **the same four stages, in
the same order, that `balanceAreaImage` (`0x10102b20`) pre-composes into one 3-band LUT.**
So that composition is not analysis-only; it is the first four links of the render chain,
merely cascaded into a single table on the analysis side. That was the one open fact §2.5
said would decide the question.

**Conclusion: balance → FUGC → … → Shasta. Go's order is the vendor's. Python's is not.**

**A second finding, which is NOT established and may matter more.**
`AnsCnEnhancedPath::exportParameterPack` @ `0x10065990` never calls `apuAppendParamPack` at
all — its pack is noise, balance, FUGC, area, falloff, asea (`0x100ff0a0`), autoTone
(`0x10106f30`), sharpening, defects. **No flare, no Shasta, no ColorAdjust** — and
`genShastaImages` (`0x101154e0`) has exactly two callers, `CnPremium_analyzeSceneSpecific`
(`0x10054800`) and the DC-Premium equivalent, neither of them CN-Enhanced. Meanwhile the path
selector `PIAnselStartNewRoll` → `0x10001e70` has a switch table at `0x10002270` mapping
`0 → DC-Premium, 1 → CN-Enhanced, 2 → CN-Enhanced, 3 → CN-Lockbeam, 4 → CP-Balance`.
**There is no case that yields CN-Premium.** TLB.dll computes that enum at
`0x10034bcb…0x10034c32` and passes it at `0x10034d01`.

If a 135 colour negative selects CN-Enhanced — which is what 1 and 2 map to — then **Shasta
is not on the F-135 render path at all**, and both engines' two-anchor Shasta stand-in is
standing in for a stage the scanner does not run, while `analyzeAutoTone` (which neither
engine implements) is the stage it does. That would make it a bigger error than the stage
order. It is **not established**: nobody has run the hardware to see which media-type code a
135 negative produces, and the agent that found this did not execute anything. It is
recorded here as the highest-value open question in the colour chain, ahead of everything
else in §12.6.

### 12.4.2 ICC input bit depth — **ESTABLISHED** (the depth; not the scale)

`dataType = U8` in `profile-Rpd2Srgb.dpi` is the **output** description. The DLL says so:
`AnsImaProfileAggregate`'s constructor `0x100938c0` compares the field against `"U8"` at
`0x10093bd6`, `setne cl`, and passes that boolean to the ImaDataType factory `0x10311600`
(case 0 → `unsigned char`, case 1 → `short`) for the **output** plane, then feeds the type
code to `[esi+0x28]->vt[0x24]` at `0x10093c0f`. The DPI reader's field-name table
(`0x1059128c…0x105912e0`: `dataType`, `renderIntent`, `colorSpaceBands`, `colorSpaceMin`,
`colorSpaceMax`) has **no input datatype field at all**. §2.9 read it as output-only and
called that "an interpretation"; it is now a fact.

The CMS call: `ImaICCXForm::apply` @ `0x102f8420` (`.\ImaICCProfile.cpp`) builds source and
destination descriptors and calls `SpEvaluate` at `0x102f884c` (KODAKCMS import thunk
`0x10500338`). Datatype selection at `0x102f85f4…0x102f8692`: `u8` planes → Sp datatype 1;
`short`/`unsigned short` planes → Sp datatype 4, then `fld qword [ebp+0x10]; fcomp qword
[0x105a17e0]` where **`0x105a17e0` is the constant `4096.0`** — if the caller's max value is
exactly 4096.0 it stays type 4 (the 12-bit mode), otherwise it becomes type 5 (full 16-bit).
Anything else is a hard error, `"Sprofile software supports only 8-16 bit data"`
(`0x105adc94`).

**So the vendor hands KCMS 16-bit planes, with an explicit 0…4095 mode selected purely by the
caller's max-value argument. Go's 16-bit evaluation is right and Python's u8 quantisation is a
PIL limitation, exactly as §2.9 argued.**

**What is NOT established: the scale.** `ImaICCEffectOp` @ `0x1016ede0` passes `this+0x118`
(source max) and `this+0x120` (dest max) into `apply` at `0x1016ee84…0x1016eef8`. The only
writer to `+0x118` that could be found is the constructor `0x1016e680`, loading the hard-coded
**32767.0** from `0x1058fac0`. Taken at face value that selects Sp datatype **5** — full
16-bit — not the 4096 mode. A later setter was not ruled out (only `fstp qword [reg+0x118]`
forms within that range were checked, not `mov`-pair writes reached from elsewhere). Go
currently scales RPD-12 to u16 by `×65535/4095`, which is neither 4095 nor 32767. **This is
an open question worth resolving before the ICC output is called correct**, and it is
plausibly part of why §12.3's ICC divergence grows with chroma.

### 12.4.3 What remains assumed

Stated plainly, because a guess here is worse than a gap:

* **FUGC mode.** `-fugc-mode` defaults to 1 because `docs/58` §7 lists mode 2 as *not ported*
  and `pakon_ansel.py` defaults to 1. Which mode the F-135 actually runs at is still
  unestablished — `CAP_MODE_SELECT = 0xC` is a runtime field. The default is a stated choice,
  not a finding.
* **The F-135 inversion.** `F135InvertPorted` is still `false` on both sides. No call site
  computes `fpo + 1000·(log10(base − c9) − log10(lin − c9))`. Every constant in it is the
  vendor's; the arrangement is ours. Bit-identical agreement between two engines that
  implement the same stand-in is not evidence the stand-in is right.
* **The Shasta curve.** `ShastaAnalyzePorted` is `false` on both sides. The two-anchor
  stand-in is not the vendor's shape, and §12.4.1's second finding raises the possibility it
  should not be running at all.
* **CLUT interpolation.** Trilinear (Go) vs tetrahedral (lcms) vs whatever `kodakcms.dll`
  does. The *call* into KCMS is now traced; the interpolation inside it is not.
* **The coefficient source.** `-coeff-source` is now required, which converts §2.11's
  disagreement from a hidden default into a stated one. It does not answer which is right;
  that still depends on whether the goal is byte-replay or best image.
* **Real captures.** Every number in §12.3 is from the synthetic fixture. Nothing here has
  been run against `captures/` — deliberately, since none of it may be staged — and the
  harness's `--raw` path exists for whoever does that locally.

## 12.5 Phase 2 — wiring the app

Phase 1 deliberately stopped short of touching the app. `grep` for `pakonpipeline` across
`*.py` / `*.js` / `*.jsx` still returns zero hits: **Go is not wired into anything.** What
follows is the plan for changing that. It is a plan, not an implementation, and it needs its
own pass.

### 12.5.0 Preconditions — none of this starts until all four hold

1. **§12.3's bit-identical result holds on a real capture**, not just the synthetic fixture.
   Run `tools/pakon_parity.py --raw` against a frame from a real roll, locally. If a real
   frame diverges where the fixture does not, the fixture is missing a case and phase 2 waits.
2. **The `.scan.json` contract is complete enough to drive a render.** Today the sidecar
   carries `film.film_path` and `film.dx` but **not ISO** (§12.2.7), and ISO is required. The
   app must acquire it — as an operator field for a DX-less roll — before it can call Go at
   all.
3. **The build is reproducible.** §5.2/§5.3 are untouched by phase 1 and every one of their
   findings still stands: no build script, no CI, untracked binaries older than their sources,
   `extraResources` copying `../tools` wholesale, and `go.mod` requiring a toolchain newer
   than the installed one. Adding a *shipped* native artefact to that pipeline before fixing
   it multiplies §10.4. The parity harness sidesteps this by rebuilding into scratch every
   run; a packaged app cannot.
4. **§12.4.1's second finding is resolved or explicitly deferred with the owner's sign-off.**
   If a 135 negative selects CN-Enhanced, Shasta should not be in the chain at all, and
   wiring the app to a chain with a spurious stage in it is wiring in a known error.

### 12.5.1 Transport: c-shared library, per §3.3 — with one change

§3.3's recommendation stands and its measurements stand: `go build -buildmode=c-shared`,
called by ctypes on the numpy buffer, 2.8 µs of call overhead against 6.6 ms + 19 ms for a
pipe round-trip at display size. The precedent is already load-bearing in this repo
(`tools/libpakon_color.dylib`, `tools/ansel/python-pipeline/libpakon_ansel.dylib`).

**The change:** §3.3's cost list must be enforced, not reviewed. A panic crossing the FFI
line takes the whole backend down, and "enforced by review" is how it will eventually not be.
The single exported entry point wraps its body in `defer recover()` and returns
`-EINTERNAL` with the panic text in `msg`; nothing else in the package is exported. Add a
test that panics deliberately inside the boundary and asserts the process survives.

### 12.5.2 The ABI

§3.4's shape, with the phase-1 request struct behind it. `RenderRequest`
(`tools/ansel/pipeline/request.go`) already carries every field of §4.3 that phase 1 needed,
with the "explicitly unknown" encodings and the refusals attached. Phase 2 adds a versioned
C-ABI mirror of it and the three entry points:

```c
int  PakonColorOpen(const char *ansel_root, const char *fx35_root, char *msg, int32_t n);
int  PakonColorRender(const PakonColorRequest *req,
                      const uint16_t *in, int32_t h, int32_t w,
                      uint8_t *out, char *msg, int32_t msg_len);
void PakonColorClose(void);
```

Boundary properties, all contract:

* **Input is the calibrated 14-bit frame slice on the capture's own grid**, before
  `unsquash_transport` and before `rot90`. Phase 1's `-raw-in H,W` reader already takes
  exactly this shape, which is the point: the TIFF hand-off (§3.1) resampled the pixels before
  the colour maths and made byte parity impossible. `Roll.slice14` is already a contiguous
  numpy view of a memmap; pass `arr.ctypes.data` and the shape, copy nothing.
* **Go writes only into `out`.** No files. `processImage`'s PNG writing moves to a
  `cmd/pakonpipeline` CLI that links the same package for offline work and for the harness.
* **stdout stays clean.** Phase 1 moved every log line to stderr and the harness fails the
  run if anything reaches stdout; phase 2 routes them to a caller-supplied callback instead.
* **`PakonColorOpen` returns the resolved selection** — sba key, shasta key, fugc map file,
  fugc LUT, contrast, aim words, coefficient source, and the reason for each — so the app can
  show it. Phase 1 already computes and logs all of it (`FilmSelection.Print`, the tap
  manifest); it needs marshalling, not deriving.
* **No 12→16→12 round trip.** §12.3 point 4. The ABI takes 14-bit codes in and 8-bit sRGB
  out; the 16-bit RPD intermediate is a `render_rpd` implementation detail that must not
  cross.

### 12.5.3 Order of work

Each step is independently verifiable with the phase-1 harness and independently revertable.

**Step 1 — the sidecar becomes the only source of film metadata.**
Make `pakon_app.job_open` pass the resolved request rather than the four-of-anything
`Roll.has_film()` accepts (§4.4). Add the operator ISO field. Nothing calls Go yet; this is a
Python-side change whose only test is that the app refuses what it should refuse. Verify with
a second harness case asserting that omitting `filmPath` raises rather than rendering.

**Step 2 — roll-level film base becomes an explicit input on both sides.**
`pakon_render.py` already accumulates it over the whole strip (`:721-742`) and
`f135_rom12_to_rpd12` already takes it as a parameter. Thread it through the request struct
so the app holds it and both engines are handed the same number. This is the last piece of
§2.6 and it is a Python-side change; Go's half is done. **Coordinate with whoever owns the
`FindDmin` fix currently in flight in `tools/pakon_decode.py` — do not touch that logic.**

**Step 3 — build the c-shared library and add it to the harness as a third column.**
The harness gains `--engine dylib`. It must agree with the `pakonpipeline` binary
**bit-for-bit at every tap**, because it is the same Go code; any difference is a boundary
bug and nothing else. This is the cheapest possible test of the FFI and it comes free.

**Step 4 — switch the app's render path behind a flag, off by default.**
`PAKON_COLOUR_ENGINE=go`. Both engines available in the same session, so a frame can be
rendered twice and compared without a restart. Run the harness on every real roll the owner
opens during this period and keep the reports.

**Step 5 — announce the visible changes, then flip the default.**
Three things change every pixel, and all three are corrections, not regressions:
  * **the stage order** (§12.4.1) — mean 2.3–5.4 sRGB codes, up to 46;
  * **the ICC input depth** (§12.4.2) — mean 0.5–0.6, up to 24;
  * **the FUGC map**, if the Python side has not already taken it — §12.2.1.
Flipping them silently is precisely the class of change that produced the defect this
document was written about. They get announced, and the flag stays available for a release.

**Step 6 — delete the Python render path.**
Not before step 5 has held on real work for a release. Until this step, **the refusals are
duplicated and a fix in one is not a fix in the other** (§12.0). This step is what actually
ends the "every fix applied two or three times" pain; everything before it makes that pain
temporarily worse. It should not be allowed to slip indefinitely.

### 12.5.4 What still must not move to Go

§9's list is unchanged by this decision and is worth re-reading in full. In particular:
capture decode and calibration, framing, transport geometry, the parameter model and user
corrections, export/naming/sidecars/the job model, and film-stock lookup all stay in Python.

**One item on that list deserves re-examination and one does not.**

* **Re-examine: the `.map` / `.dpi` selection logic.** §9 argued selection is policy and
  should stay in Python, with resolved file paths passed across. Phase 1 went the other way —
  it *fixed* Go's selection (§12.2.1) rather than removing it. Both engines now select
  independently and agree, which is a duplication in the same shape as the refusals. Phase 2
  should decide: either Python resolves and passes the paths (§3.4's `PakonColorOpen` return
  is already shaped for it), or Go owns selection outright and Python stops. Two independent
  selectors that happen to agree today is how §2.1 happened.
* **Do not re-examine: the refusals.** They must end up in exactly one place, and after step 6
  that place is Go. They are already there and already produce operator-readable prose.

## 12.6 Open questions, ranked by what they are worth

1. **Does the F-135 take CN-Enhanced rather than CN-Premium?** (§12.4.1) If so, Shasta is not
   on the render path and `analyzeAutoTone` (`0x10106f30`, unported on both sides) is. Worth
   more than everything below. Needs the path enum a 135 negative actually produces —
   hardware, or a deeper trace of TLB.dll `0x10034bcb…0x10034d01`.
2. **The ICC max-value scale** (§12.4.2). 4095 vs 32767 vs Go's `×65535/4095`. Selects
   between two different KCMS datatypes and plausibly explains part of §12.3's chroma-growing
   ICC divergence.
3. **The F-135 inversion has no call site** (`F135InvertPorted = false`). Two engines agreeing
   bit-for-bit on the same stand-in is not evidence the stand-in is right.
4. **CLUT interpolation.** Go trilinear, lcms tetrahedral, `kodakcms.dll` untraced. Now
   reachable: the call is located at `0x102f884c` and the DLL is extractable from the repo's
   own ISO.
5. **FUGC mode** (§12.4.3). Explicit and defaulted, not established.
6. **The coefficient source** (§2.11). Now a required choice rather than a hidden default;
   which choice is right is still open.
7. **Build reproducibility** (§5.2/§5.3). Untouched by phase 1 and a hard precondition for
   phase 2 step 3.
