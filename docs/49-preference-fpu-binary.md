# 49 — Preference FPU → shifts (binary)

Durable cite-backed notes for Pakon Update 3 `PakonIMAu.dll`
(image base `0x10000000`). Builds on
[`docs/48-preference-opening-rgb.md`](48-preference-opening-rgb.md) (opening RGB =
dpi `fpo`) and [`tools/ansel/pakon_sba_preference.py`](../tools/ansel/pakon_sba_preference.py).

Do **not** invent missing aim/mode inputs. Mark UNKNOWN honestly.
`PREFERENCE_SHIFTS_PORTED` stays **False** until a cited end-to-end path
(including mode/`aimY`/`w1e`) is byte-faithful.

---

## Verdict

| Item | Status |
|------|--------|
| Preference body `0x1028c780`…`0x1028cd02` (~0x583 B) | Mapped |
| External calls | **No soft walls** — only `0x1028c540` + `_ftol2` `0x104ffe44` |
| Opening RGB → opponent Y/U/V | **Solved** (prior; consts `0x105a6f38/30/28`) |
| Inverse opponent → RGB (store path) | **Solved** (+ `√(2/3)` @ `0x105a6f40`) |
| Mode word `scene+0x5074` → aim Y/U/V | **Solved** (tables below) |
| Final shifts store @ `scene+0x3a38` | **Solved** — `inv(t', −U_r, −V_r)` after `add esi,8` |
| `analyzePass2` common mode shape | Often forces **hi=0x10**; lo often **1** → `dU=dV=0`, `dY=w1e` |
| `inner+0x24` (`w1e` / blob `+0x1e`) | **Solved** — dpi **`pcls`** (dump `0x102ae48f`, parse `0x102ad38d`); all shipped `sba-*.dpi` = **0** |
| `setShifts` before apply | Control words = SCPLut `ntd`/`ctd` (**closed**); shipped CN → `(1,2)` transform — **not** passthrough (`docs/52`) |
| Full byte-faithful port / apply wiring | **Blocked** (`(1,2)` maths + lo≠1 aims + golden) |

---

## Call site (`analyzePass2`)

From `0x1021641a…44` (scene in `esi`):

| Stack arg | Source | Role |
|-----------|--------|------|
| `ebp+0x8` | `scene+0x38a2` | Param / pcode-related words (`edi` in body) |
| `ebp+0xc` | `0x1013c4e0` (FOS Cap get) | Optional aim words; **null → error `0x18a4`** if mode needs it |
| `ebp+0x10` | `scene+0x3a30` | Working / output base (`esi` in body) |
| `ebp+0x14` | `ebp-0x20c` after `0x10214f20` | Input blob |
| `ebp+0x18` | `scene+0x5074` | Mode word |

Error string: `"Preference() failed, return code %d\n"` @ `0x1059de68`.

Mode setup (same function, before call):

* Low nibble ← `[ebp-0x28]` ∈ `{0,1,2,3,4}` or default `0` / `1` (`0x10215e7b…114`).
* High nibble ← OR of `{0x10,0x20,0x30,0x40}` from `[ebp-0x2c]` (`0x102161a8…209`).
* Special force: `and …0x0f; or …0x10` @ `0x10216356` (hi→`0x10`);
  or `and …0xf0; or edi(=1)` @ `0x1021640e` (lo→`1`).

---

## External calls (Preference body)

| VA | Target | Role | Soft wall? |
|----|--------|------|------------|
| `0x1028caa2` | `0x1028c540` | `(R,G,B)·0.001` → mean / `1/√2` / `1/√6` | **No** — ported |
| `0x1028cb2b/4d/77` | `0x104ffe44` | MSVC `_ftol2`-style round→`eax` | **No** — use `round` (not bit-claimed) |
| `0x1028ccc2/ce9` | `0x104ffe44` | Same for store loops | **No** |

No other `call`s. Preference FPU is self-contained.

---

## Stack / blob map (inputs used by FPU)

Blob fill `0x10214f20` (scene → `edi`); Preference reads via `ebx=[ebp+0x14]`.

| Blob | Scene / dpi | Preference use |
|------|-------------|----------------|
| `+0x00…04` | `+0x4d0e` = **`fpo`** | Opening RGB → `Y,U,V` @ `0x1028c7e0` |
| `+0x06…0a` | `+0x4cf0` = **`fpa`** | Second opponent triple → `Y2,U2,V2` @ `0x1028cae7` |
| `+0x0c…10` | **`neu`** | `0x1028c540` when `dY ≤ 0` |
| `+0x12…16` | **`neo`** | `0x1028c540` when `dY > 0` |
| `+0x1e` | `inner+0x24` = **`pcls`** (ctor **0**; shipped dpi **0**) | `w1e` in `dY` / `Y_r−w1e` |
| `+0x30` | **`nonFlashAdj`** (`inner+0x2c`) | `scale = ·0.001` (UV path when `iDU/iDV≠0`) |
| `+0x42/+0x44` | `fist(neutralButton · under/overConstraint)` | Clamp lo/hi |
| `+0x46` | ≈ `round(neutralBalancePoint · √3)` | Clamp pivot `lim46` |

`fpo` / `fpa` / `neu` / `neo` / `pcls` / clamp fields parse in host
`SbaParams` (`pakon_ansel.py`). Preference should consume those ints as the
blob fields above — **not** invent FOS OUT stats.

**`pcls` identity (solved):** dump prints `\tpcls = \t` from `[ebx+0x24]` @
`0x102ae48f`; `readAscii` `"pcls"` → `%hd` into `obj+0x24` @ `0x102ad38d`.
Blob fill copies `scene+0x4d14` → blob `+0x1e` @ `0x10214f91`. Imm `0x4d14`
has **no** store sites — only dpi load / assign-copy write it.

---

## Mode → aims

After opening opponent (`Y,U,V` kept: `Y` on FPU + `[esp+0x70]`,
`U`→`[esp+0x78]`, `V`→`[esp+0x80]`):

### Low nibble → `aimY` (`0x1028c92f`)

| lo | `aimY` | Cite |
|----|--------|------|
| `1` | `Y` (opening) | `fld st(0)` |
| `2` | `int16[param+0x12] · √3` (`0x105a69e0`) | |
| `3` | `int16[arg1+0]` | needs arg1 |
| `4` | `int16[param+0x40] + Y` | |
| else (`0`) | `int16[param+0]` | |

### High nibble → `aimU`,`aimV` (`0x1028c98e`)

| hi | `aimU`,`aimV` | Cite |
|----|---------------|------|
| `0x10` | opening `U`,`V` | ⇒ **`dU=dV=0`** |
| `0x20` | opponent of `param+0xc/0xe/0x10` | |
| `0x30` | `int16[arg1+2], [arg1+4]` | needs arg1 |
| `0x40` | `int16[param+0x42], [param+0x44]` | |
| else | `int16[param+2], [param+4]` | |

Then (`0x1028ca4c…63`):

```
dU = aimU − U
dV = aimV − V
dY = w1e + aimY − Y     // stored [esp+0x40]; compared to 0 for neu/neo pick
```

---

## Core FPU (verified equation fragments)

Constants: `1/√3` `0x105a6f38`, `1/√6` `0x105a6f30`, `1/√2` `0x105a6f28`,
`√(2/3)` `0x105a6f40`, `0.001` float `0x105a0800`, `0` @ `0x10573c40`.

### Helper pick + combine (`0x1028ca7b…cbad`)

```
(m, o1, o2) = helper_1028c540( neo if dY>0 else neu )
iDY = round(dY);  iDU = round(dU);  iDV = round(dV)
scale = nonFlashAdj * 0.001

Y_r = Y + Y2 + m  * iDY
U_r = U + U2 + scale * iDU + o1 * iDY
V_r = V + V2 + scale * iDV + o2 * iDY
```

with `(Y2,U2,V2) = opponent(fpa)` (same forward transform as opening).

Because opponent is linear: `(Y+Y2,U+U2,V+V2) = opponent(fpo+fpa)` (RGB sum).

### Y clamp (`0x1028cbb1…cc1f`)

```
t  = Y_r − w1e
s  = lim46 − t
s' = clamp(s, blob+0x42, blob+0x44)
t' = lim46 − s'          // ≡ clamp(t, lim46−hi, lim46−lo)
```

`lim46` ≈ `neutralBalancePoint · √3` (integer path @ blob fill `0x10215084…`).

### Inverse opponent (`0x1028cc33…ccb8`)

```
R = t'/√3 − U/√6 − V/√2
G = t'/√3 + U·√(2/3)
B = t'/√3 − U/√6 + V/√2
```

### Stores (`0x1028ccc0…ccf8`)

| Dest | Value |
|------|-------|
| `scene+0x3a32/+34/+36` (`esi+2`) | `round(inv(t',  U_r,  V_r))` |
| `scene+0x3a38/+3a3a/+3a3c` (`esi+8`) | `round(inv(t', −U_r, −V_r))` ← **shifts** |

Also copies assorted param words into the `+0x3a30` block (non-shift); see disasm
`0x1028c802…905`.

---

## Common `analyzePass2` reduction (mode `0x11`, `w1e=0`)

When lo=`1`, hi=`0x10`, `w1e=0`:

```
dY = dU = dV = 0
Y_r,U_r,V_r = opponent(fpo + fpa)          // RGB component sum
t' = clamp_Y(Y_r, lim46, lo, hi)
shifts = round( inv(t', −U_r, −V_r) )
```

Helper `neu`/`neo` is still *called* but multiplied by `iDY=0` (dead).
CN-default fragment yields Preference words ≈ `(1421, 1035, 889)` — these are
**`+0x3a38` stores**, not proven apply LUT inputs after `setShifts`.

---

## `getShifts` / `setShifts` / `applyBalanceShifts`

| Step | VA | Behaviour |
|------|-----|-----------|
| `getShifts` | `0x10124000` | Copies 3×int16 from scene `+0x3a38` (raw Preference store) |
| `setShifts` | `0x10100260` | Control words = SCPLut Cap `+0x10+0x18` `ntdChoice`/`ctdChoice` (`+0x38`/`+0x3a`). `(0,0)`→passthrough A; `(2,2)`→passthrough B; shipped CN `(1,2)`→`0x60e`+LUT+`×0x186a0` — see **`docs/52-setshifts-binary.md`** |
| Cap apply | `0x100dc310` → Impl `0x1019a0c0` | Three int16 args → LUT `0x1006c4f0` as **additive** `master[i+shift]` |

Call site `areaMethods` `0x100e1b63` pushes `[buf+0/+2/+4]` into apply — buffer
provenance is the setShifts/accumulate path in `analyzeBalanceOrder`.
**CN auto (shipped SCPLut dpi): `(1,2)` transform — Preference words are not
apply inputs.** Blocks `PREFERENCE_SHIFTS_PORTED` until `(1,2)` maths + golden.

---

## Host dpi exposure

`SbaParams.load` parses `fpo`, `fpa`, `pcls`, `neu`/`neo`,
`neutralBalancePoint`, `neutralButton`, under/over constraints.
Helpers: `opening_rgb_from_sba_fpo`, `preference_shifts_from_dpi_fields`
(diagnostic only). Default Ansel still uses median `channel_balance`.

---

## Remaining UNKNOWNs (block apply wiring)

1. **Golden `setShifts` `(1,2)`** — closed form in `docs/52` / `setshifts_12`; need DLL compare before wiring.
2. **Exact mode distribution** when user color/neutral balance tokens present.
3. **`aimY` when lo≠1** — `scene+0x38a2` word map / pcode coupling.
4. **arg1** payload when hi∈{`0x30`} or lo=`3` (FOS get `0x1013c4e0`).
5. **Bit-identical `_ftol2`** vs `round` (edge ties / negatives).
6. Golden Preference/`setShifts`(1,2)/apply chain vs DLL.

---

## File map

| File | Role |
|------|------|
| This doc | Preference FPU binary report |
| `docs/48-preference-opening-rgb.md` | Opening RGB = `fpo` writers |
| `docs/52-setshifts-binary.md` | setShifts control words / CN `(1,2)` |
| `tools/ansel/pakon_sba_preference.py` | Portable fragments; `PREFERENCE_SHIFTS_PORTED=False` |
| `tools/ansel/pakon_sba_apply.py` | Apply when shifts known (unwired) |
