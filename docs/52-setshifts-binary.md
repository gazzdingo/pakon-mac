# 52 — `ColorNegativePath::setShifts` control words (CN auto)

DLL: `PakonIMAu.dll` image base `0x10000000`.
Closes the control-word provenance for CN auto rolls. Does **not** port the
`(1,2)` transform maths or enable `PREFERENCE_SHIFTS_PORTED`.

---

## Call site

`analyzeBalanceOrder` @ `0x10101220` calls `setShifts` @ `0x10101f89`
(cdecl, 5 stack args). Immediately before the call, QI
(`0x104ffdd6`) selects:

| Arg | Source | Type (RTTI near QI) |
|-----|--------|---------------------|
| 1 | `lea …` OUT buffer | 3×int16 destination |
| 2 | prior QI → `edi` | `AnsSbaCapability` (`0x106927b4`) |
| 3 | `[esp+0x54]` | SBA Cap (getShifts #1) |
| 4 | QI result | **`AnsSCPLutCapability`** (`0x106927d4`) |
| 5 | `[esp+0x20]−4` | second getShifts Cap / accumulate peer |

`setShifts` @ `0x10100260` uses arg4 as `ecx` for `0x10122a70`.

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

`0x10122150` → `0x10212100`: reads three signed words from
`*(Impl+0x10)` (SCPLut work/LUT base) for table indexing — **not** ported.

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

For shipped CN SCPLut dpi, setShifts runs **`(1, 2)`**, which **transforms**
Preference/`getShifts` words through `0x60e` + SCPLut LUT indices +
`×0x186a0` axes. It is **not** a Preference passthrough.

Therefore:

* Raw Preference `+0x3a38` words are **not** proven apply LUT inputs for CN auto.
* `PREFERENCE_SHIFTS_PORTED` stays **False**.
* Full `(1, 2)` closed form + golden vs DLL remain **UNKNOWN** (next RE).

Optional: if a configuration forced `(0, 0)`, passthrough would copy
Preference words to OUT — that is **not** the shipped CN path.

---

## File map

| File | Role |
|------|------|
| This doc | setShifts control-word / branch report |
| `docs/49-preference-fpu-binary.md` | Preference FPU; points here for setShifts |
| `docs/46-ansel-parity-checklist.md` | Blockers / next RE |
| `tools/ansel/pakon_sba_apply.py` | Apply helper; setShifts cites |
| `tools/ansel/pakon_analyse_roll.py` | balanceOrder / setShifts I/O |
| `tools/ansel/pakon_scp_lut.py` | ntd/ctd → int16 helpers |
| `tools/ansel/pakon_sba_preference.py` | Preference fragments; port flag False |
