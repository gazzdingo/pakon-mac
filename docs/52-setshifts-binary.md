# 52 — `ColorNegativePath::setShifts` (CN auto)

DLL: `PakonIMAu.dll` image base `0x10000000`.
Closes control-word provenance and the shipped **`(1,2)`** closed form.
`(1,2)` closed form is **golden vs DLL** (Unicorn). Does **not** enable
`PREFERENCE_SHIFTS_PORTED` (Preference→A/B + apply wiring still open).

---

## Call site

`analyzeBalanceOrder` @ `0x10101220` calls `setShifts` @ `0x10101f89`
(cdecl, 5 stack args). Immediately before the call, QI
(`0x104ffdd6`) selects:

| Arg | Source | Role (VERIFIED) |
|-----|--------|-----------------|
| 1 | `lea [esp+0x9c]` | smart-ptr / return glue (not shift OUT) |
| 2 | QI → `edi` | **`AnsSbaCapability`** (`0x106927b4`) — getShifts **A** Cap |
| 3 | `[esp+0x4c]` QI | **same Sba Cap** — getShifts **B** Cap (stack-arg fixups) |
| 4 | QI result | **`AnsSCPLutCapability`** (`0x106927d4`) — control words |
| 5 | `[esp+0x20]−4` = **`scene+0x4b6`** | **3×int16 OUT** destination |

`setShifts` @ `0x10100260` uses arg4 as `ecx` for `0x10122a70`.
Shift OUT stores (`0x101004aa`, `0x10100f31`, …) write **`[esp+0xbc]` =
arg5 = `scene+0x4b6`**, not arg1.

**Buffer A ≡ B:** both getShifts Caps are the scene Sba Cap → same
Preference `+0x3a38` words. Shipped `(1,2)` is therefore
`setshifts_12(A, A, lut)`.

**OrderWide:** first `analyzeBalanceOrder` (flag 0) can
`getShifts`→**add** into `scene+0x4b6`; ScpLut **zeroes** `+0x4b6`;
second pass (afterSCPLut) **writes** setShifts OUT there. Apply sees the
second-pass OUT.

---

## Control-word provenance (VERIFIED)

1. Stack object ctor `0x101d0200` → `lea ecx, [esp+0x4c]`.
2. `0x10122a70`: `source = *(Cap+0x10) + 0x18` → `0x10122190` copy into stack obj.
3. `0x10122190` copies words at source `+0x38` / `+0x3a` (among other fields).
4. After four pushes, setShifts reads:

   * `[esp+0x84]` = stack obj `+0x38`
   * `[esp+0x86]` = stack obj `+0x3a`

5. Dump of the same Cap+0x10+0x18 blob @ `0x101d0050` prints
   **`AnsSCPLutDPI:`** with:

   * `m_ntdChoice` ← `word [obj+0x38]`
   * `m_ctdChoice` ← `word [obj+0x3a]`

So setShifts control words **are** SCPLut DPI `ntdChoice` / `ctdChoice`,
not Preference mode bits and not lighting-adjust runtime state.

---

## `AnsSCPLutDPI::readAscii` enums (VERIFIED)

`readAscii` @ `0x101d03b0` (string `0x10599620`). Keys (case-insensitive
`_stricmp` via IAT `0x1057345c`):

| DPI key | Token strings | Store |
|---------|---------------|-------|
| `ntdchoice` | `ans_first_pass` / `ans_lut_first_pass` / `ans_second_pass` | `+0x38` → 0 / 1 / 2 |
| `ctdchoice` | same three tokens | `+0x3a` → 0 / 1 / 2 |

Token VAs: `0x10599574`, `0x10599560`, `0x10599550`.
Value encodes at `0x101d07f4` / `0x101d0810` / `0x101d0834` (`+0x38`) and
`0x101d088f` / `0x101d08ab` / `0x101d08cf` (`+0x3a`).

### Shipped CN dpi → `(1, 2)`

`dataPathItems/SCPLut/SCPLut-scanner-prod-gen-default-default-default.dpi`:

```
ntdChoice = ANS_LUT_FIRST_PASS   → +0x38 = 1
ctdChoice = ANS_SECOND_PASS      → +0x3a = 2
```

Parser defaults in `tools/ansel/pakon_scp_lut.py` match those tokens.

---

## Branch catalog in `setShifts` (VERIFIED)

`edi` is set to `1` @ `0x1010029c` and used as the “mode 1” compare.
Two `getShifts` results:

* buffer A @ `[esp+0x10]` (arg3 Cap — Preference/`+0x3a38`)
* buffer B @ `[esp+0x1c]` (arg5 Cap)

| `(ntd, ctd)` | VA entry | Behaviour |
|--------------|----------|-----------|
| `(0, 0)` | `0x101004aa` | **Passthrough** copy A → OUT |
| `(2, 2)` | `0x101004e1` | **Passthrough** copy B → OUT |
| `(0, 2)` | `0x10100510` | `0x60e − ch` on A&B then `×0x186a0` 3-axis path |
| `(2, 0)` | `0x101006fb` | same family (`0x60e` / `×0x186a0`) |
| `(1, 0)` | `0x101008e7` | `0x60e` + Cap LUT helper `0x10122150` |
| `(1, 2)` | `0x10100a37` | **CN shipped path**: `0x60e − A`, LUT index via `0x10122150` → `0x10212100`, then `0x60e − B` + `×0x186a0` combine |
| `(0, 1)` | `0x10100ca5` | `0x60e` + LUT (`cmp ctd, edi`) |
| `(2, 1)` | `0x10100f42` | `0x60e` + LUT |
| `(1, 1)` | `0x10100be0` | `0x60e` + LUT |
| other | `0x10101112` | error log line `0xbd7` |

**Correction vs earlier notes:** `(2, 2)` is **not** the `0x60e` path; it
is passthrough of getShifts buffer B. The `0x60e` (1550) pivot appears on
the mixed / mode-1 branches, including shipped `(1, 2)`.

`0x10122150` → `0x10212100`: reads **`Ans3BandLutParams`** at
`AnsSCPLutCapabilityImpl+0x10` (allocated in SCPLut Impl ctor
`0x10213123`; fail string cites
`AnsSCPLutCapabilityImpl.cpp` + `Ans3BandLutParams`):

| Out slot (after stack-arg fixups) | Field | Use in `(1,2)` |
|-----------------------------------|-------|----------------|
| `[esp+0x28]` | `+0` `NUM_LUT` (int16→i32) | planar band stride |
| `[esp+0x30]` | `+2` `NUM_BANDS` | dump / unused in index |
| `[esp+0x2c]` | `+4` `int16*` table | planar LUT base |

Dump `@ 0x1026bf90` names `NUM_LUT` / `NUM_BANDS` / `LUT_NAME`.

---

## `(1, 2)` maths (VERIFIED closed form)

Entry `@ 0x10100a37`. Same combine tail as `(0, 2)` `@ 0x10100510`
(merge `@ 0x10100651` / OUT `@ 0x10100f31`→`0x1010109d`); only the
**Y** source differs.

Shared axis helpers = FOS opening (`fos_opening_axes` / `×0x186a0` +
MSVC magic) — see `tools/ansel/pakon_fos.py`.

### Steps

1. **Pivot A:** `A' = 0x60e − A` (int16), `0x60e = 1550`.
2. **3-band LUT lookup** (planar `int16[NUM_BANDS * NUM_LUT]`):

   ```
   L_r = lut[A'_r]
   L_g = lut[A'_g + NUM_LUT]
   L_b = lut[A'_b + 2·NUM_LUT]
   ```

3. **Y from LUT RGB:** `Y = axis_y(L)` (= FOS opening Y).
4. **Pivot B:** `B' = 0x60e − B`.
5. **Chrominance from B':** `C1 = axis_c1(B')`, `C2 = axis_c2(B')`.
6. **Axis → code** (same magics, axis·scale ± bias):

   ```
   Yc  = magic_y (Y  · 0x186a0 ± BIAS_Y)
   C1c = magic_c1(C1 · 0x186a0 ± BIAS_C1)
   C2c = magic_c2(C2 · 0x186a0 ± BIAS_C2)
   C1×2 = magic_c1(C1 · 0x30d40 ± BIAS_C1)   // 0x30d40 = 2·0x186a0
   ```

7. **Reconstruct RGB codes:**

   ```
   R = Yc  − C1c − C2c
   G = Yc  + C1×2
   B = Yc  − C1c + C2c
   ```

8. **OUT:** `OUT = 0x60e − (R,G,B)` (int16) @ `0x10100f31` / `0x1010109d`.

`(0, 2)` is identical with step 2–3 replaced by `Y = axis_y(A')`
(no LUT).

### Shipped 3-band LUT data

* Index dpi: `anselinstalldir/dataPathItems/common/common-3BandLuts.dpi`
  → `LUT_DPI = luts6_postROMM_equalRGBshort.lut`
* File: ASCII `NUM_LUT = 4096`, `NUM_BANDS = 3`, rows
  `index R G B` (interleaved). Equal-RGB short post-ROMM
  (brightness 1.34, gamma 1.1).
* Runtime table is **planar** (indexing above). Host loader should
  de-interleave into `R||G||B` of length `NUM_LUT` each.

### Port flags / golden

* Closed form in `pakon_sba_apply.setshifts_12` /
  `fos_opening_axes_inverse`.
* **Golden:** `tools/ansel/pakon_setshifts_golden.py` maps
  `PakonIMAu.dll` in Unicorn, enters `@ 0x10100a37`, stops at OUT
  `@ 0x101010ac`, compares to `setshifts_12` on the shipped 3-band lut.
  All harness cases match → `SETSHIFTS_12_PORTED = True`.
* `PREFERENCE_SHIFTS_PORTED` stays **False** (no host wire yet).

---

## Not the same: `AnsLightingAdjust`

* Ctor @ `0x10138c20` (`lightingAdjust-default` @ `0x105a0410`) sets
  **`+0x38 = 0`**; does **not** store `+0x3a`.
* Shipped `lighting-*.dpi` has only backlit/frontlit scalars — **no**
  ntd/ctd keys.
* Assign `0x10237e80` copies `+0x38` then dword `+0x3c` (**skips `+0x3a`**).
* Full member copy `0x1010b450` does copy `+0x3a`.

`ans_*_pass` strings live only in **`AnsSCPLutDPI::readAscii`**. Do **not**
treat lighting-adjust `+0x38` as setShifts control words.

---

## CN-auto conclusion (apply wiring)

For shipped CN SCPLut dpi, setShifts runs **`(1, 2)`**:

* **Luma/tone** from 3-band LUT of pivoted Preference words (buffer A).
* **Chroma** from pivoted second getShifts (buffer B).
* **Not** Preference passthrough.

Therefore:

* Raw Preference `+0x3a38` words are **not** apply LUT inputs for CN auto.
* Apply words = `setshifts_12(A, A)` → `scene+0x4b6` (CN afterSCPLut).
* Host wires that through `apply_balance_shifts` with Preference
  mode-`0x11` fragment for `A` (`pakon_ansel.cn_setshifts_apply_words`).
* `SETSHIFTS_12_PORTED = True`. `PREFERENCE_SHIFTS_PORTED` stays **False**
  (Preference fragment / lo≠1 still open).

Optional: `(0, 0)` would copy Preference → OUT — **not** shipped CN.

---

## File map

| File | Role |
|------|------|
| This doc | setShifts control words + `(1,2)` closed form |
| `docs/49-preference-fpu-binary.md` | Preference FPU; points here for setShifts |
| `docs/46-ansel-parity-checklist.md` | Blockers / next RE |
| `tools/ansel/pakon_sba_apply.py` | Apply helper + `setshifts_12` (`PORTED=True`) |
| `tools/ansel/pakon_setshifts_golden.py` | Unicorn golden vs DLL `(1,2)` |
| `tools/ansel/pakon_fos.py` | Shared `×0x186a0` axes + inverse |
| `tools/ansel/pakon_analyse_roll.py` | balanceOrder / setShifts I/O |
| `tools/ansel/pakon_scp_lut.py` | ntd/ctd + 3-band lut ASCII load |
| `tools/ansel/pakon_sba_preference.py` | Preference fragments; port flag False |
