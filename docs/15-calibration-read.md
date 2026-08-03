# 15 — Light calibration: where the numbers live

Answers the question "how does TLB.dll read the scanner's per-unit light
calibration, and what are `iCurrent_R/_G/_B/_Ir` plus the base exposure?"

**Headline result:** there is no per-unit light calibration *in the scanner*.
`FN_GetCalibrateInfoLight` performs **no device I/O at all** — it is a getter
over a host-side, registry-backed config tree at
`HKLM\Software\Pakon\TLB\Scan\DpiBase{16,8,4}_35\<filmMode>`, values
`Current_R/_G/_B/_Ir`. The per-unit values are produced by a closed-loop search
against the CCD (`FN_bCalibrateFindLedCurrent`) and persisted there. They cannot
be read out of the hardware.

There **are** compiled-in defaults — all four currents default to **1** — but
they are placeholders, not calibration (§2c).

**The 40 000 question, answered up front:** `n` is a small drive-step index in
`[1, 24]`, transmitted as one byte. The "40,000 IR light level" in the SDK
release note is a *target CCD code value* compared against the maximum pixel of
an averaged line — an entirely different quantity. See §4.

What *can* be recovered from the binary — and is recovered below — is the
complete **legal range and wire encoding** of every one of those values, which
is enough to bring the lamp up safely by replicating the vendor's own search.

Tags: `[VERIFIED-FROM-BINARY]` / `[INFERRED]` / `[UNKNOWN]`.

Binary: `TLB.dll`, timestamp 2007-04-18, 536 576 bytes.

---

## 0. Corrections to `14-lamp-decoded.md`

Two claims in doc 14 are wrong and are superseded here.

1. **`[cfg+0x90/0x98/0xa0/0xa8]` used inside `FN_bDrvLampOn` are not duty
   cycles.** In `fcn.1002c5f0` the base register is
   `ebx = [0x10075554] + 0x15a0`, which is the **lamp/temperature config
   object**, not a `CiConfigLight`. At `+0x90/+0x98/+0xa0/+0xa8` that object
   holds `WaitForLamp_R/_G/_B/_Ir` (doubles) — settling times. They feed a
   `Sleep()` at `0x1002ce2e` (`× 1000.0` → ms), not the PWM.
   `[VERIFIED-FROM-BINARY]` — the name→offset binding is proven by the config
   loader `fcn.10010cc0` at `0x10010f8d`–`0x10010fdf`.

2. **Register write order inside `FN_bDrvLampOn` is `0x80` → `0x81` → `0x82`**,
   not `0x81, 0x82, 0x80`. `0x80` is written first, at `0x1002c6a4`, guarded by
   `cmp [esi+0x29c], edi` (write only if the enable mask changed).
   `[VERIFIED-FROM-BINARY]`. See §7 — the recommended host order is the
   *reverse*, and is strictly safer.

3. **`[0x10075554]` is not a `CiConfigLight` pointer.** It is the root of the
   whole config tree (a `0x1c28`-byte object allocated at `0x10034324` and
   stored at `0x10034350`). A `CiConfigLight` is reached only through the two
   selectors of §1a/§1b, e.g. `[0x10075554] + 0x4d8 + 0xb8` for
   `DpiBase16_35\ColNeg`. In `FN_bCalibrateLEDs` (`fcn.10020dc0`) `esi` *starts*
   as `[0x10075554]` at `0x10020dce` but is reloaded from the third argument at
   `0x10020ea9` (`mov esi, dword [ebp+0x10]`) before any `+0x58` access — that
   argument is the `CiConfigLight`, threaded down from
   `FN_bBeforeScan` → `fcn.10021590` (arg 2) ← `scanner->0x59c`.
   `[VERIFIED-FROM-BINARY]`. Reading `[0x10075554]+0x58` as `Current_R` would
   give an unrelated field.

---

## 1. `FN_GetCalibrateInfoLight` — the read path

FN id **195** (`fcn.100170b0` case 195 → `str.FN_GetCalibrateInfoLight`).
Body: `method.ATL::CComObject_class_CiTLAMain_::virtual_44` @ **`0x1003dfb0`**,
628 bytes, `ret 0x64` (24 parameters). `[VERIFIED-FROM-BINARY]`

It calls exactly two helpers and then copies struct fields. **No emitter, no
`DeviceIoControl`, no packet.** `[VERIFIED-FROM-BINARY]`

```
0x1003e097  call fcn.1000f330      ; select DPI config object
0x1003e0af  call fcn.100109f0      ; select film-mode light config
0x1003e155.. mov/fld from [eax+..] ; 20 field copies, then LeaveCriticalSection
```

### 1a. `fcn.1000f330(&out, dpiIndex, kind)` — DPI object selector

`[VERIFIED-FROM-BINARY]`

| `kind` | `dpiIndex` | result |
|---|---|---|
| ≠1 | — | `*out = 0` (fail) |
| 1 | 0 | `[0x10075554] + 0x1008` |
| 1 | 1 | `[0x10075554] + 0x0a70` |
| 1 | 2 | `[0x10075554] + 0x04d8` |
| 1 | other | `*out = 0` |

Cross-referenced against `fcn.100120e0`, which constructs the same three objects
at `root+0xbb0`, `root+0x618`, `root+0x80` and names their registry subkeys:

| object | registry subkey | `[VERIFIED-FROM-BINARY]` |
|---|---|---|
| `[0x10075554]+0x04d8` | `\DpiBase16_35` | `0x100121b6` |
| `[0x10075554]+0x0a70` | `\DpiBase8_35` | `0x10012221` |
| `[0x10075554]+0x1008` | `\DpiBase4_35` | `0x10012288` |

### 1b. `fcn.100109f0(dpiObj, filmColor, useIr)` — film-mode selector

`[VERIFIED-FROM-BINARY]` (`0x100109f0`)

| `filmColor` | `useIr` | offset | registry subkey |
|---|---|---|---|
| 1 | 0 | `+0x0b8` | `\ColNeg` |
| 1 | ≠0 | `+0x188` | `\ColNegIr` |
| 4 | 0 | `+0x258` | `\BnW` |
| 4 | ≠0 | `+0x328` | `\BnWIr` |
| 8 | 0 | `+0x3f8` | `\BnW_C41` |
| 8 | ≠0 | `+0x4c8` | `\BnW_C41Ir` |
| other | — | returns `0` |

Subkey names proven at `fcn.10011a60` `0x10011a94`, `0x10011b00`, `0x10011b6b`,
`0x10011be0`, `0x10011c37`, `0x10011c98`.

So there are **18** `CiConfigLight` instances (3 DPI bases × 6 film modes),
stride `0xd0`.

### 1c. Where the bytes actually come from

`CiConfigLight::Load` = **`fcn.1000fd80`**. Every field is fetched with
`fcn.1000c940`, which is:

```
fcn.1000c940(name, &field):
    if fcn.10022c30(hive, subkey, name, &field)   -> RegOpenKeyExW +
                                                     RegQueryValueExW (REG_DWORD, cb==4)
        return 1
    if fcn.10022cd0(hive, subkey, name, field)    -> RegCreateKeyExW +
                                                     RegSetValueExW  (writes the
                                                     *current* value back as default)
        return 1
    field = 0; return 0
```
`[VERIFIED-FROM-BINARY]` (`0x10022c30`, `0x10022cd0`)

Root key string: `Software\Pakon\TLB` at `.rdata:0x10067cac`.
`[VERIFIED-FROM-BINARY]`.

**The hive is `HKEY_LOCAL_MACHINE` — now `[VERIFIED-FROM-BINARY]`, previously
tagged `[INFERRED]`.** Chain:

```
0x10034350  mov  dword [0x10075554], eax      ; root config object
0x10034368  push str.SoftwarePakonTLB         ; arg2 = "Software\Pakon\TLB"
0x1003436d  push 0x80000002                   ; arg1 = HKEY_LOCAL_MACHINE
0x10034372  mov  ecx, eax
0x10034374  call fcn.100125a0
```

`fcn.100125a0` prologue: `push -1; push handler; push fs:[0]` (0xc) +
`sub esp,0x244` ⇒ `[esp+0x254]` is arg1 and `[esp+0x258]` is arg2. At
`0x100125dc` it does `mov dword [esi+8], eax` with `eax = [esp+0x254]` — the
hive lands at `root+8`. It is then copied verbatim down the tree:
`fcn.10011a60` `0x10011a8c` (`[esi+8] = arg1`) and `0x10011ab3`
(`[ebx+8] = [esi+8]` for each of the six lights), and `fcn.10022c30` uses
`[esi+8]` directly as the `hKey` argument to `RegOpenKeyExW`.

> radare2 mis-symbolises `0x80000002` at `0x1003436d` as
> `reloc.OLEAUT32.dll_SysReAllocString`. It is a `push imm32`
> (`68 02 00 00 80`), not a relocation.

Full path `[VERIFIED-FROM-BINARY]` (concatenation order proven at
`fcn.100125a0` `0x100128ea` → `fcn.100120e0` `0x100121b6` → `fcn.10011a60`
`0x10011a94`):

```
HKLM\Software\Pakon\TLB\Scan\DpiBase16_35\ColNeg
HKLM\Software\Pakon\TLB\Scan\DpiBase16_35\ColNegIr
HKLM\Software\Pakon\TLB\Scan\DpiBase8_35\...
HKLM\Software\Pakon\TLB\Scan\DpiBase4_35\...
... (3 × 6 = 18 keys, each with Current_R/_G/_B/_Ir)
```

Note the `\Scan` level: the three DPI containers hang off the scan-group object
at `root+0x458`, whose subkey is `<base>\Scan` (`0x100128ea`, assigned to
`root+0x458` at `0x10012913` immediately before `call fcn.100120e0`).
Siblings `\Save` (`root+0x1680`) and `\Memory` (`root+0x16b8`) exist but hold no
`CiConfigLight`. `[VERIFIED-FROM-BINARY]`

### 1d. `CiConfigLight` field map `[VERIFIED-FROM-BINARY]` (`fcn.1000fd80`)

| offset | type | registry value name |
|---|---|---|
| `+0x28` | i32 | *(not registry — see §3)* base exposure |
| `+0x30` | i32 | `FullLightCorrections` |
| `+0x34/38/3c` | i32 | `Gain_R` / `Gain_G` / `Gain_B` |
| `+0x40` | i32 | `SpliceDarkness` |
| `+0x44` | i32 | `DetectWhite_G` |
| `+0x48` | i32 | `DetectFilm_G` |
| `+0x4c/50/54` | i32 | `Offset_R` / `Offset_G` / `Offset_B` |
| **`+0x58`** | **i32** | **`Current_R`** |
| **`+0x5c`** | **i32** | **`Current_G`** |
| **`+0x60`** | **i32** | **`Current_B`** |
| **`+0x64`** | **i32** | **`Current_Ir`** |
| `+0x70/78/80/88` | f64 | `DutyCycle_R/_G/_B/_Ir` |
| `+0x90/98/a0/a8` | f64 | `DutyCycleOpenGate_R/_G/_B/_Ir` |

`FN_PutCalibrateInfoLight` (FN id 256, `0x1003e230`) writes the same fields
straight back into memory (`0x1003e730`: `[ecx+0x58] = ebp`, `+0x5c = ebx`,
`+0x60 = esi`, `+0x64 = edx`) and then `SetEvent`. Persistence to the registry
happens separately via `CiConfigLight::Save` = `fcn.1000ff90`, driven by
`fcn.100106d0` over all six instances. `[VERIFIED-FROM-BINARY]`

### 1e. The scanner EEPROM does **not** hold light calibration

`FN_bReadEEPromToRegistry` (FN id 270) = **`fcn.10016a90`**. It reads two
CRC32-checked EEPROM sections (398 B at one address, 36 B at another) via
`fcn.100163c0` → `fcn.100160a0`, then distributes them with `fcn.10016860` →
`fcn.10016610`. `fcn.10016610` writes only:

```
[dpiObj+0x20] = u16      ; Offset
[dpiObj+0x44] = u16      ; MotorSpeed(Plus)
[dpiObj+0x48] = u16      ; MotorSpeed(Plus)_Ir
[dpiObj+0x24] = clamp(u16, 900, 1100)   ; MotorAdjust
[dpiObj+0x2c] = clamp(u16, 900, 1100)   ; MotorAdjustDrag
[dpiObj+0x28] = clamp(u16, 900, 1100)   ; MotorAdjust_Ir
[dpiObj+0x30] = clamp(u16, 900, 1100)   ; MotorAdjustDrag_Ir
and zeroes  +0xe8 +0x1b8 +0x288 +0x358 +0x428 +0x4f8
            (= each light config's FullLightCorrections flag)
```
`[VERIFIED-FROM-BINARY]` (`0x10016610`–`0x10016717`; the six zeroed offsets are
exactly `lightcfg_base + 0x30` for all six bases).

**No LED current, no LED duty cycle, no lamp temperature is read from the
scanner.** `[VERIFIED-FROM-BINARY]`

There is no block-read of light-board registers `0x01`/`0x03`/`0x07` anywhere in
the illumination path — the only light-board reads in the whole binary are
`0x83` (status, `0x1000b8fe`) and `0x84` (temperature, `0x1000b99b` and
`0x100209c0`). `[VERIFIED-FROM-BINARY]`

---

## 2. The four `n` values — what they are and their legal range

`n` = `Current_X` = `CiConfigLight[+0x58/+0x5c/+0x60/+0x64]`.

### 2a. They are the LampOn *level* arguments

`FN_bCalibrateFindLedCurrent` (`fcn.1001e7b0`) calls `FN_bDrvLampOn`
(`fcn.1002c5f0`) at `0x1001e860` with `[esi+0x58]`, `[esi+0x5c]`, `[esi+0x60]`,
`[esi+0x64]` as the four level arguments and `[esi+0x28]` as the exposure,
plus `[esi+0x90/0x98/0xa0/0xa8]` as the four duty doubles.
`[VERIFIED-FROM-BINARY]`

`FN_bDrvLampOn` signature, recovered from `ret 0x40` and the argument uses:

```
BOOL FN_bDrvLampOn(
    void*  log,        // ebp+0x08
    int    visibleOn,  // ebp+0x0c  -> enable bit 0
    int    irOn,       // ebp+0x10  -> enable bit 1
    int    level_R,    // ebp+0x14
    int    level_G,    // ebp+0x18
    int    level_B,    // ebp+0x1c
    int    level_Ir,   // ebp+0x20
    int    exposure,   // ebp+0x24
    double duty_R,     // ebp+0x28
    double duty_G,     // ebp+0x30
    double duty_B,     // ebp+0x38
    double duty_Ir);   // ebp+0x40
```
`[VERIFIED-FROM-BINARY]`

### 2b. Hardware limits — compiled in, and enforced

`fcn.100203c0` returns the four maxima; `fcn.1002c5f0` clamps against them at
`0x1002c6fb`–`0x1002c743`. `[VERIFIED-FROM-BINARY]`

Board select is `byte [this+0x2f8] == 0x44`, which is the **main-board address**
(the light board is `[this+0x2f9]` = `0x40`). See §9 — this is a board-generation
discriminator, `0x44/0x40` vs the legacy `0x24/0x20`.

| board | `irOn` | max R | max G | max B | max Ir |
|---|---|---|---|---|---|
| `0x44` | yes | **8** | **24** | **24** | **8** |
| `0x44` | no  | **4** | **20** | **20** | **0** |
| other  | yes | 8 | 8 | 8 | 8 |
| other  | no  | 6 | 8 | 8 | 0 |

Exposure is clamped to **`0xffd` = 4093** (`0x1002c739`).
`[VERIFIED-FROM-BINARY]`

So `n ∈ [1, 8]` for R and IR and `n ∈ [1, 24]` for G and B. They are small
integers — a drive-step index, not a DAC code. The lower bound is **1**, not 0:
see §2c. Also note the register field is a **single byte** on the wire (§5a),
which alone caps `n` at 255 regardless of the software clamp.

### 2c. Compiled-in defaults — corrected

> **Correction (independent re-verification).** An earlier revision of this
> section claimed "the compiled-in default is 0 — i.e. lamp dark". That is
> **wrong**. It came from searching only for stores at *container-relative*
> offsets (`parent+0x110 / +0x1e0 / …`). The defaults are written in the
> `CiConfigLight` constructor using `this`-relative offsets, so that search
> missed them.

`CiConfigLight::CiConfigLight` = **`fcn.1000fc10`** (`0x1000fc10`–`0x1000fd06`,
vtable `0x1005cf94` installed at `0x1000fcbf`, class id `0x11` at `+0x1c`).
Called six times per DPI container from `fcn.10010280` at `0x100102cc`,
`0x100102dc`, `0x100102ec`, `0x100102fc`, `0x1001030c`, `0x1001031c` — i.e. for
all 18 instances. `[VERIFIED-FROM-BINARY]`

| field | offset | compiled-in default | instruction |
|---|---|---|---|
| `Current_R` | `+0x58` | **1** | `0x1000fce5 mov [esi+0x58], ecx` |
| `Current_G` | `+0x5c` | **1** | `0x1000fcee mov [esi+0x5c], ecx` |
| `Current_B` | `+0x60` | **1** | `0x1000fcf7 mov [esi+0x60], ecx` |
| `Current_Ir` | `+0x64` | **1** | `0x1000fd00 mov [esi+0x64], ecx` |
| `Gain_R/_G/_B` | `+0x34/38/3c` | **13** (`0xd`) | `0x1000fc43/4c/55`, `edi = 0xd` @ `0x1000fc14` |
| `SpliceDarkness` | `+0x40` | **237** (`0xed`) | `0x1000fcd8` |
| `Offset_R/_G/_B` | `+0x4c/50/54` | 0 | `0x1000fc79/82/8b`, `eax = 0` |
| exposure | `+0x28` | 0 (overwritten, §3) | `0x1000fc70` |
| `DutyCycle_*` | `+0x70/78/80/88` | **0.0** | `fld [0x1005c1c8]` = 0.0 |
| `DutyCycleOpenGate_*` | `+0x90/98/a0/a8` | **0.0** | same |

`ecx = 1` is loaded once at `0x1000fc3b` and is not clobbered before the four
stores (the only intervening `ecx` write, `lea ecx,[esi+0xc]`, is at
`0x1000fc19`, and the only call, `0x1000fc25`, is also earlier).
`.rdata:0x1005c1c8` = `0.0`. `[VERIFIED-FROM-BINARY]`

**Second compiled-in literal: the calibration reset.** `FN_bCalibrateLEDs`
(`fcn.10020dc0`, FN id 40) begins a *full* recalibration — when its 4th argument
is non-zero — by resetting all four currents to **1** and all four
`DutyCycleOpenGate_*` to **1.0**, then walking upward:

```
0x100210cd  fld  qword [0x10065c78]      ; 1.0
0x100210d3  mov  eax, 1
0x100210d8  fstp qword [esi+0x90]        ; DutyCycleOpenGate_R = 1.0
0x100210de  mov  dword [esi+0x58], eax   ; Current_R  = 1
0x100210e7  mov  dword [esi+0x5c], eax   ; Current_G  = 1
0x100210ea  mov  dword [esi+0x60], eax   ; Current_B  = 1
0x100210f9  mov  dword [esi+0x64], eax   ; Current_Ir = 1
...         (+0x98/+0xa0/+0xa8 = 1.0)
```
`[VERIFIED-FROM-BINARY]` (`.rdata:0x10065c78` = `1.0`).

So the vendor's own search **starts at 1**, not 0 — which is the value a host
should also start from.

### 2c-bis. Their per-unit values are still NOT in the binary

Defaults exist, but they are placeholders, not calibration. The only writes to
`lightcfg+0x58…0x64` anywhere in `TLB.dll` are:

| site | what it does |
|---|---|
| `fcn.1000fc10` `0x1000fce5…0x1000fd00` | constructor default = 1 |
| `fcn.1000fd80` (via `fcn.1000c940` out-params) | registry read |
| `fcn.10020dc0` `0x100210de…0x100210f9` | reset to 1 before full recalibration |
| `fcn.10020dc0` `0x100212d3`, `0x10021318`, `0x1002135d`, `0x1002138d` | `+1` calibration step |
| `fcn.1001e7b0` `0x1001e8f6`, `0x1001e949`, `0x1001e996`, `0x1001e9da` | `+1` calibration step |

`[VERIFIED-FROM-BINARY]` — enumerated by disassembling the whole `.text` section
and grepping every store to `[reg+0x58/0x5c/0x60/0x64]`, then classifying each
containing function by its vtable / logger FN id. **No packet read, no file read,
no EEPROM read appears in that list.**

**`[UNKNOWN]`: the actual `Current_R/_G/_B/_Ir` for this or any specific
scanner.** They are not in TLB.dll, not in TLA.dll/TLC.dll, and not in the
scanner's EEPROM. The only ways to obtain them are (a) read them from the
registry of a working Windows install of the Pakon software that has been
calibrated against *this* unit, or (b) re-run the search of §2d starting from 1.

**`[UNKNOWN]`: the actual `Current_R/_G/_B/_Ir` for this or any specific
scanner.** They are not in TLB.dll, not in TLA.dll/TLC.dll, and not in the
scanner's EEPROM. The only ways to obtain them are (a) read them from the
registry of a working Windows install of the Pakon software that has been
calibrated against *this* unit, or (b) re-run the search of §2d.

### 2d. How the vendor finds them — `FN_bCalibrateFindLedCurrent`

`fcn.1001e7b0`, FN id 31. `[VERIFIED-FROM-BINARY]`

Per iteration: call `FN_bDrvLampOn` with the current levels, acquire and average
lines, take the per-channel **maximum pixel value**, then:

```
; visible channel (this instance operates on Current_B, [esi+0x60]):
0x1001e97a   cmp  max, 0xffdc          ; 65500
             ja   -> stop (saturated -> flag 2)
0x1001e98c   eax = [esi+0x60]
             cmp  eax, <max_B>         ; the 24/20 clamp from fcn.100203c0
             jae  -> stop (flag 1, at limit)
             inc  eax
             [esi+0x60] = eax          ; +1 and retry

; IR channel (Current_Ir, [esi+0x64]):
0x1001e9c8   cmp  max, 0x9c40          ; 40000
             ja   -> stop
0x1001e9d0   eax = [esi+0x64]
             cmp  eax, <max_Ir>        ; the 8/0 clamp
             jae  -> stop
             inc  eax
             [esi+0x64] = eax
```

It is a **monotone +1 walk from the current value upward**, bounded above by the
hardware clamp, stopping as soon as the measured signal exceeds the target.
Starting from 1 (§2c) this is inherently safe: every step is the smallest
possible increase, and it never exceeds the compiled-in maximum.

#### 2d-bis. The four stop thresholds are NOT all the same

Important for anyone replicating the walk. The four comparison sites in
`fcn.1001e7b0`, together with the plane each one indexes in the averaged-line
buffer, are:

| channel | plane index | threshold | `cmp` site | increments |
|---|---|---|---|---|
| R | `base + ecx*4` (plane 0) | `0xfa00` = **64000** | `0x1001e8da` | `[esi+0x58]` |
| G | `base + edi*4 + ecx*4` (plane 1) | `0xfa00` = **64000** | `0x1001e92d` | `[esi+0x5c]` |
| B | `base + 2·edi*4 + ecx*4` (plane 2) | `0xffdc` = **65500** | `0x1001e97a` | `[esi+0x60]` |
| IR | `base + 3·edi*4 + ecx*4` (plane 3) | `0x9c40` = **40000** | `0x1001e9c8` | `[esi+0x64]` |

`[VERIFIED-FROM-BINARY]`. (`edi` is the per-plane pixel count; `[esp+0x28]` is
pre-computed at `0x1001e7f3`–`0x1001e7fe` as `base + 2·edi*4`, which is what
makes planes 2 and 3 identifiable.) The green `cmp` is mis-synced by radare's
linear disassembly, which shows garbage at `0x1001e930`. Raw bytes settle it:

```
0x1001e925  8b 44 24 10        mov  eax, [esp+0x10]
0x1001e929  85 c0              test eax, eax
0x1001e92b  75 29              jne  0x1001e956
0x1001e92d  81 fa 00 fa 00 00  cmp  edx, 0xfa00      <-- 64000
0x1001e933  76 0a              jbe  0x1001e93f       ; -> inc [esi+0x5c]
0x1001e935  c7 44 24 10 02..   mov  dword [esp+0x10], 2
```

The sense of every test is `jbe → keep increasing`, so the loop raises the
current while `max ≤ threshold`.

---

## 3. The base exposure

`CiConfigLight[+0x28]`. It is **not** registry-backed — `fcn.1000fd80` never
touches `+0x28`. It is written unconditionally by **`fcn.10010760`** as a
compiled-in constant selected by `dpiObj[+0x5c]`. `[VERIFIED-FROM-BINARY]`
(`0x10010760`–`0x100107df`; the six destination offsets `+0xe0 +0x1b0 +0x280
+0x350 +0x420 +0x4f0` are exactly `lightcfg_base + 0x28` for all six bases.)

| `dpiObj[+0x5c]` | non-IR modes (`ColNeg`, `BnW`, `BnW_C41`) | IR modes (`ColNegIr`, `BnWIr`, `BnW_C41Ir`) |
|---|---|---|
| 0 | **2323** (`0x913`) | **1549** (`0x60d`) |
| 1 | **3485** (`0xd9d`) | **2323** (`0x913`) |
| other | **4080** (`0xff0`) | **3098** (`0xc1a`) |

All ≤ 4093, consistent with the `0xffd` clamp. `[VERIFIED-FROM-BINARY]`

`[INFERRED]` `dpiObj[+0x5c]` is a scan-speed/mode index; `fcn.10011510` calls
`fcn.10010760` once per DPI base. Its exact provenance is `[UNKNOWN]`.

---

## 4. Magnitude sanity check — the 60 000 → 40 000 question

**The SDK note "reduce IR light level from 60,000 to 40,000" refers to a target
CCD code value, not to `n`.** `[VERIFIED-FROM-BINARY]`

`0x9c40` = 40000 appears exactly twice in `.text`:

- `0x1001e9c8` — `cmp edx, 0x9c40` in `FN_bCalibrateFindLedCurrent`, where `edx`
  is the maximum pixel value of the averaged IR line.
- `0x1001f18e` — the same comparison in `FN_bCalibrateFindLedDutyCycle`
  (`fcn.1001ec90`).

The companion visible-channel target in the same function is `0xffdc` = **65500**
(`0x1001e97a`) — i.e. ~99.9 % of a 16-bit full scale. 40000/65535 ≈ 61 %, a
sensible headroom target for an IR channel. `[VERIFIED-FROM-BINARY]`

`n` cannot be 40000, for three independent reasons, any one of which is
sufficient. `[VERIFIED-FROM-BINARY]`

1. **It does not fit on the wire.** `n` is transmitted as a *single byte*
   (`mov byte [esp+…], al` at `0x1002cc04`, `0x1002cc08`, `0x1002cc1e`,
   `0x1002cc38`, in a 5-byte payload written to light-board register `0x81`).
   Max representable value 255.
2. **It is clamped in software.** `fcn.1002c5f0` `0x1002c6fb`–`0x1002c736`
   clamps each level to the `fcn.100203c0` maxima (8/24/24/8) *before* the byte
   store. 40000 would be silently reduced to 8.
3. **The search that produces it counts by one from one.** Constructor default 1
   (`0x1000fce5`), `FN_bCalibrateLEDs` reset to 1 (`0x100210de`), then `inc` per
   iteration (`0x100212d3` etc.). Reaching 40000 would require 40000 CCD
   acquisitions and would hit the `jae` limit test at step 8 or 24.

If `n` *were* 40000, `duty = (n-1)/n` would evaluate to 0.999975 — the exact
pathological case the question flags. **That case does not arise.** The 40000 in
the release note is the IR channel's target CCD code value, a completely
different quantity that lives only in `cmp` instructions and never in the config
struct.

### 4a. Refinement of the duty-derivation formula

`fcn.1001e020` is confirmed, with one correction: `base` is **not** 1.0.

```
fcn.1001e020(cfg, doVisible, doIr):
    base_R = base_G = base_B = base_Ir = 1.0
    fcn.10020230(1, &base_R, &base_G, &base_B, &base_Ir)   ; overwrites them

    for ch in (R@0x58->0x90, G@0x5c->0x98, B@0x60->0xa0, Ir@0x64->0xa8):
        n = cfg[in]
        cfg[out] = (n >= 3) ? base_ch * (n-1)/n
                            : base_ch * 0.5
```
`[VERIFIED-FROM-BINARY]`. Destination fields are `DutyCycleOpenGate_*`
(`+0x90/98/a0/a8`), i.e. the **open-gate** (no film) duty set — *not*
`DutyCycle_*` at `+0x70/78/80/88`.

`fcn.10020230` computes `base_ch = 1 / 10^(D_ch)` — an optical-density
attenuation — selected by `[this+0x374]`. `fcn.10049210` is MSVC `_CIpow`
(identified by its `stmxcsr` / `fnstcw` preamble at `0x10049210`).
`[VERIFIED-FROM-BINARY]`

| `[this+0x374]` | `D_R` | `D_G` | `D_B` | `D_Ir` | `base_R` | `base_G` | `base_B` | `base_Ir` |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.144 | 0.4 | 0.715 | 0.0 | 0.7178 | 0.3981 | 0.1928 | 1.0 |
| 8 | 0.1 | 0.25 | 0.25 | 0.08 | 0.7943 | 0.5623 | 0.5623 | 0.8318 |
| other | 0.0 | 0.03 | 0.0 | 0.08 | 1.0 | 0.9332 | 1.0 | 0.8318 |

Constants read from `.rdata`: `0x10065eb8`=10.0, `0x10065eb0`=0.03,
`0x10065ea8`=0.08, `0x10065ea0`=0.1, `0x10065e98`=0.25, `0x10065e90`=0.144,
`0x10065e88`=0.4, `0x10065e80`=0.715. `[VERIFIED-FROM-BINARY]`

Worked example, `[this+0x374]` = other, `n_G = 24`:
`duty_G = 0.9332 × 23/24 = 0.894`. Sane. With `n_R = 8`:
`duty_R = 1.0 × 7/8 = 0.875`. Sane.

---

## 5. The wire encoding of `0x81` and `0x82`

Recovered by tracking exact `esp` offsets through `fcn.1002c5f0`
(`0x1002cbfd`–`0x1002ce08`). `[VERIFIED-FROM-BINARY]`

### 5a. Register `0x81` — LED levels, 5 bytes

```
buf[0] = level_B     (ebp+0x1c, clamped <= 24)
buf[1] = level_Ir    (ebp+0x20, clamped <= 8)
buf[2] = level_R     (ebp+0x14, clamped <= 8)
buf[3] = 0x00        (hard zero, 0x1002cc33)
buf[4] = level_G     (ebp+0x18, clamped <= 24)
```

This supersedes doc 14's "which slot is R/G/B/IR is UNKNOWN".
The channel order **B, Ir, R, (unused), G** is confirmed independently by the
`0x82` payload below, which uses the identical ordering.

### 5b. Register `0x82` — LED PWM, 12 bytes = six LE u16

```
u16[0] = on_B      u16[1] = on_Ir    u16[2] = on_R
u16[3] = 0x0000    u16[4] = on_G     u16[5] = N   (period)
```
(byte offsets `0x54..0x5f` relative to the pre-sequence `esp`; `u16[3]` is the
two hard zeros written at `0x1002cd40` / `0x1002cd45`.)

Period and on-counts `[VERIFIED-FROM-BINARY]` (`0x1002cb6d`–`0x1002cdbd`):

```
N_float  = (exposure * 1e6) / (2 * clock)          ; clock = 833333.3  (.rdata 0x1005db68)
         = exposure * 0.6
N        = ftol(N_float)
on_ch    = ftol(floor(N_float * duty_ch))
           clamped to  <= N - 2                     ; 0x1002cd17 `lea edi,[ebx-2]`
```

`0x10067000` = 1000000.0, `0x1005db68` = 833333.3 → the factor is exactly 0.6.
`[VERIFIED-FROM-BINARY]`

Example: `exposure = 2323` → `N = 1393`; `duty_G = 0.894` → `on_G = 1245`.

Note `on_ch ≤ N-2` means **100 % duty is not representable** — the firmware
always gets at least 2 ticks of off-time. Any host implementation must preserve
this.

---

## 6. Temperature: setpoints, units, and the stability wait

### 6a. The temperature config object

`LC = [0x10075554] + 0x15a0`. Loaded by **`fcn.10010cc0`**; registry subkey is
`Software\Pakon\TLB\Test` `[INFERRED]` (string pushed at `0x10012149`,
concatenated at `0x1001215c`, assigned to `(root+0x1148)+0xc` at `0x1001217b`
immediately before `call fcn.10010cc0`; `root+0x1148 == [0x10075554]+0x15a0`
because `root+0x80 == [0x10075554]+0x4d8`).

Field map `[VERIFIED-FROM-BINARY]` (`fcn.10010cc0`, `0x10010f86`–`0x100111b2`):

| offset | type | value name | compiled-in clamp |
|---|---|---|---|
| `+0x8c` | i32 | `WriteLightStabilityLog` | — |
| `+0x90/98/a0/a8` | f64 | `WaitForLamp_R/_G/_B/_Ir` | — |
| `+0xb0` | i32 | `WriteEEPromDebugFile` | — |
| `+0xb4` | i32 | `UseTemperatureSetpoints` | — |
| `+0xb8` | i32 | `LampTempFaultLow` | `[WarnLow+8, WarnLow+32]` |
| `+0xbc` | i32 | `LampTempWarningLow` | **`[8, 32]`** |
| `+0xc0` | i32 | `LampTempWorking` | **`[592, 768]`** |
| `+0xc4` | i32 | `LampTempWarningHigh` | **`[8, 32]`** |
| `+0xc8` | i32 | `LampTempFaultHigh` | `[WarnHigh+8, WarnHigh+32]` |
| `+0xcc` | i32 | `MotherBoardTempFaultLow` | ≥ 160 (`0xa0`) … |
| `+0xd0` | i32 | `MotherBoardTempWarningLow` | — |
| `+0xd4` | i32 | `MotherBoardTempWarningHigh` | — |
| `+0xd8` | i32 | `MotherBoardTempFaultHigh` | — |

Clamps at `0x100110a3`–`0x10011151`. These are applied **after** the registry
read, unconditionally, so no registry value can push the working setpoint out of
`[592, 768]`. `[VERIFIED-FROM-BINARY]`

### 6b. Units — 1/16 °C

`0x10020a31`: the raw value read from register `0x84` (and from `0x88`) is
multiplied by `.rdata:0x1005c3b0` = **0.0625**. `[VERIFIED-FROM-BINARY]`

So the register unit is **1/16 °C**, and:

- `LampTempWorking ∈ [592, 768]` = **[37.0 °C, 48.0 °C]**
- warning offsets `∈ [8, 32]` = **[0.5 °C, 2.0 °C]**
- fault offsets = warning + `[8, 32]` = up to **4.0 °C** from the setpoint

`[UNKNOWN]`: the actual `LampTempWorking` for a given unit. It is a registry
value with no compiled-in default. Only the enforced window is known.

### 6c. `FN_bDrvInitLampTemperatures` — the five payloads

FN id 342, **`fcn.1002d190`**. Board address is `byte [this+0x2f9]` (= `0x40`).
Emitter is `fcn.10009ae0` (`PutRegister`, n=4) except where noted.
All offsets verified by exact `esp` tracking. `[VERIFIED-FROM-BINARY]`

| reg | n | payload |
|---|---|---|
| `0x8F` | 4 | `i16 LE(-LampTempWarningLow)`, `i16 LE(+LampTempWarningHigh)` |
| `0x8C` | 4 | `i16 LE(-LampTempFaultLow)`, `i16 LE(+LampTempFaultHigh)` |
| `0x8B` | 4 | `i16 LE(MotherBoardTempWarningLow)`, `i16 LE(MotherBoardTempWarningHigh)` |
| `0x8D` | 4 | `i16 LE(MotherBoardTempFaultLow)`, `i16 LE(MotherBoardTempFaultHigh)` |
| `0x8E` | 2 | `u16 LE(LampTempWorking)` — via `fcn.1000a9e0` → `fcn.10009d40` (`PutRegisterWord`); **only if `UseTemperatureSetpoints != 0`** |
| `0xD0` | 1 | `0x00` — `fcn.10009ba0` |
| `0xD1` | 1 | `0x01` — `fcn.10009ba0` |

Written in that exact order; the function aborts on the first failure and logs
FN 342. `[VERIFIED-FROM-BINARY]`

Key structural insight: **`0x8B`/`0x8D` carry absolute motherboard temperatures;
`0x8C`/`0x8F` carry signed offsets relative to the working setpoint** (the low
bound is negated at `0x1002d1af` / `0x1002d214`, the high bound is not). `0x8E`
carries the absolute working setpoint. This matches the doc-14 note that `0x8F`
is `[lo(-temp), hi(-temp), cfg+0x1664, cfg+0x1665]` — `cfg+0x1664` and
`cfg+0x1665` are the two bytes of `LampTempWarningHigh` at `LC+0xc4`.

Note `0x8E` is issued **before** `0xD0`/`0xD1`, and `0xD0=0`/`0xD1=1`
`[INFERRED]` latch/enable the loaded setpoints.

### 6d. `FN_bLampTemperatureStable`

FN id 346, **`fcn.1002cf10`**. `[VERIFIED-FROM-BINARY]`

It does **not** read register `0x84`. It waits on an in-process flag:

```
if ([this+0x298] > 0) return TRUE;                 ; already stable
timer = Timeout(0x493e0)                           ; 300000 ms = 300 s
loop:
    if ([this+0x38] & 0x40548c0) -> log FN 346 msg 0x8c, set caller bit 0, fail
    if (fcn.10033ed0(timer) expired)               -> same failure path
    every 10 s: progress callback fcn.10032580(..., 0x18, seconds+1000)
    Sleep(250)                                     ; fcn.10022f70
    elapsed += 1000
    until ([this+0x298] > 0)
```

- Poll interval **250 ms**, overall timeout **300 s**, progress every **10 s**.
- The `[this+0x298]` flag is set by the light-board monitor that reads registers
  `0x83` (status, `fcn.1000b890` @ `0x1000b8fe`, `GetRegisterByte`) and `0x84`
  (temperature, `0x1000b99b`, `GetRegisterWord`). `[VERIFIED-FROM-BINARY]`
- **`[UNKNOWN]`: the exact predicate that sets `[this+0x298]`.** The comparison
  against the setpoint/tolerance was not traced to a specific instruction.
  Resolving it means decoding the monitor thread in `fcn.1000b890`.

Caller context: `fcn.10021590` (per-film-type light setup) at `0x1002173e`,
preceded by two progress dialogs (message ids 22 and 24, 2000 ms and 1000 ms) and
a `fcn.1002ce70` lamp bring-up. `[VERIFIED-FROM-BINARY]`

### 6e. `FN_bLampWarmUp`

FN id 226. **`[UNKNOWN]` — body not located.** It has no `fcn.1001acd0` logger
call site, so the "recover by logger id" technique yields nothing. The observable
warm-up behaviour in the scan path is entirely `fcn.10021590` → `fcn.1002ce70` →
`fcn.1002cf10` (§6d). Resolving this would need either a cross-check against
TLA.dll/TLC.dll or tracing the COM vtable entry that dispatches FN 226.

---

## 7. SAFE SEQUENCE TO SEND

> **Read this first.** The four `Current_*` values for your unit are not
> recoverable from any artefact in hand (§2c). Do **not** invent them. The
> sequence below is safe precisely because it starts at the bottom of the
> compiled-in legal range and walks up by one step, which is exactly what
> `FN_bCalibrateFindLedCurrent` does.
>
> Do not send temperature setpoints at all unless you have a real
> `LampTempWorking` from a calibrated install. §7.0 is the reason.

### 7.0 Temperature — the one thing to leave alone

`FN_bDrvInitLampTemperatures` is **not** on the lamp-on path. Its only caller is
`fcn.10028d30` @ `0x10029402` `[VERIFIED-FROM-BINARY]`, and `FN_bDrvLampOn`
never touches `0x8B`–`0x8F`, `0xD0` or `0xD1`.

The lamp can therefore be lit without programming any thermal setpoint. Since
`LampTempWorking` is `[UNKNOWN]` per-unit and a wrong value commands a TEC to the
wrong temperature, **omit registers `0x8B`, `0x8C`, `0x8D`, `0x8E`, `0x8F`,
`0xD0` and `0xD1` entirely.** Leave whatever the firmware powered up with.

If you later do program them, every field must satisfy the §6a clamps, and `0x8E`
must be within `[592, 768]` (37–48 °C).

### 7.1 The packets

Board `0x40` (light). All packets are `Type 2` writes; expect `07 02 40 00`.

**Step 1 — confirm the lamp is off.**

```
02 04 40 01 80 00
│  │  │  │  │  └── mask = 0x00: bit0 visible off, bit1 IR off
│  │  │  │  └───── register 0x80  (lamp enable)
│  │  │  └──────── count = 1 byte
│  │  └─────────── address 0x40   (light board)
│  └────────────── PktLen = 4  -> wire size 6
└───────────────── Type 2 (write)
```
Source: `fcn.1002c5f0` @ `0x1002c6a4`, `PutRegisterByte(log, addr, 0x80, mask, 0)`.

**Step 2 — program the PWM period and on-counts (register `0x82`, 12 B).**

Pick `exposure` from §3. Use the smallest, `1549`, for first light.

```
N       = round(1549 * 0.6) = 929  = 0x03A1
duty    = 0.5 (deliberately conservative; the real value comes from §4a once
          Current_* are known)
on      = floor(929 * 0.5) = 464   = 0x01D0     (must be <= N-2 = 927)
```

Enable **one** channel only — green, the largest legal headroom (max 24):

```
02 0F 40 0C 82 00 00 00 00 00 00 00 00 D0 01 A1 03
│  │  │  │  │  └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘ └─┬─┘
│  │  │  │  │    │     │     │     │     │     └── u16[5] = N        = 929
│  │  │  │  │    │     │     │     │     └──────── u16[4] = on_G     = 464
│  │  │  │  │    │     │     │     └────────────── u16[3] = 0 (hard zero, §5b)
│  │  │  │  │    │     │     └──────────────────── u16[2] = on_R     = 0
│  │  │  │  │    │     └────────────────────────── u16[1] = on_Ir    = 0
│  │  │  │  │    └──────────────────────────────── u16[0] = on_B     = 0
│  │  │  │  └── register 0x82 (LED PWM)
│  │  │  └───── count = 12
│  │  └──────── address 0x40
│  └─────────── PktLen = 0x0F (12+3) -> wire size 17
└────────────── Type 2
```
Channel order and the `u16[3]` zero: `fcn.1002c5f0` `0x1002cd2f`–`0x1002ce04`.
`N` formula: `0x1002cb6d`–`0x1002cb97`. `on <= N-2`: `0x1002cd17`.

**Step 3 — program the LED levels (register `0x81`, 5 B).** Start at **1**.

```
02 08 40 05 81 00 00 00 00 01
│  │  │  │  │  │  │  │  │  └── buf[4] = level_G  = 1     (max 24)
│  │  │  │  │  │  │  │  └───── buf[3] = 0 (hard zero, 0x1002cc33)
│  │  │  │  │  │  │  └──────── buf[2] = level_R  = 0     (max 8)
│  │  │  │  │  │  └─────────── buf[1] = level_Ir = 0     (max 8)
│  │  │  │  │  └────────────── buf[0] = level_B  = 0     (max 24)
│  │  │  │  └── register 0x81 (LED levels)
│  │  │  └───── count = 5
│  │  └──────── address 0x40
│  └─────────── PktLen = 8 (5+3) -> wire size 10
└────────────── Type 2
```
Slot order: `fcn.1002c5f0` `0x1002cc04`–`0x1002cc38`. Maxima: `fcn.100203c0`.

**Step 4 — enable the visible lamps (register `0x80`).**

```
02 04 40 01 80 01
                └── mask = 0x01: bit0 visible on, bit1 IR off
```
Enable-mask construction: `fcn.1002c5f0` `0x1002c63f`–`0x1002c659`.

**Step 5 — measure, then step up.**

Acquire a line. Take the maximum pixel value. Then, exactly as
`FN_bCalibrateFindLedCurrent` does:

- if `max > threshold(channel)` → stop, you are at/over target; step **back down**.
- else if `level == max(channel)` → stop, at the hardware limit.
- else `level += 1`, re-send Step 3, re-measure.

**The threshold is per-channel — do not use one value for all four** (§2d-bis):

| channel | stop threshold | ceiling (board `0x44`, IR on) |
|---|---|---|
| R | 64000 (`0xfa00`) | 8 |
| G | 64000 (`0xfa00`) | 24 |
| B | 65500 (`0xffdc`) | 24 |
| IR | 40000 (`0x9c40`) | 8 |

Start every channel at `level = 1`, which is both the constructor default and the
value `FN_bCalibrateLEDs` resets to before its own walk (§2c).

**Step 6 — lamp off when done.** `02 04 40 01 80 00`.

### 7.2 Ordering rationale

`FN_bDrvLampOn` itself writes `0x80` → `0x81` → `0x82` (§0). That order is safe
*for the driver* only because it caches previous state and skips unchanged
registers, so in a steady-state scan loop the levels are already correct when the
enable is asserted. A host starting from unknown firmware state has no such
guarantee: enabling first could assert the lamp with whatever drive the firmware
happens to hold.

The order above (`0x80`=off → `0x82` → `0x81` → `0x80`=on) reaches the identical
end state with the lamp provably dark while the drive registers are in flux.
Use it.

### 7.3 What must never be sent blind

- Registers `0x8B`, `0x8C`, `0x8D`, `0x8E`, `0x8F`, `0xD0`, `0xD1` — thermal.
  See §7.0.
- `level_R > 8`, `level_G > 24`, `level_B > 24`, `level_Ir > 8`
  (or `>4 / >20 / >20 / 0` with IR disabled).
- `exposure > 4093`.
- `on_ch > N - 2`.
- Register `0x97` (firmware-update gate).

---

## 8. Summary of what is still unknown

| item | status | what would resolve it |
|---|---|---|
| `Current_R/_G/_B/_Ir` values | `[UNKNOWN]` | registry dump from a calibrated Windows install, or re-run §2d against the CCD |
| `LampTempWorking` value | `[UNKNOWN]` | same registry dump (`…\TLB\Test\LampTempWorking`) |
| Predicate setting `[this+0x298]` | `[UNKNOWN]` | decode the monitor loop in `fcn.1000b890` (reads `0x83`, `0x84`) |
| `FN_bLampWarmUp` body | `[UNKNOWN]` | COM vtable dispatch for FN 226, or cross-check TLA/TLC |
| `dpiObj[+0x5c]` provenance | `[UNKNOWN]` | trace `fcn.10011510` callers |
| ~~Registry hive (HKLM vs HKCU)~~ | **RESOLVED — HKLM** `[VERIFIED-FROM-BINARY]` | see §1c |
| `[this+0x2f8]`/`[this+0x2f9]` provenance | **RESOLVED** `[VERIFIED-FROM-BINARY]` | see §9 |

The single highest-value next action is the **registry dump**: one
`reg export "HKLM\Software\Pakon\TLB"` from any machine that has run the Pakon
calibration wizard against a real F-135 supplies `Current_R/_G/_B/_Ir`,
`DutyCycle*`, `Gain_*`, `Offset_*` and `LampTempWorking` in one shot, and
collapses every remaining `[UNKNOWN]` in this table except the last two.

---

## 9. Board addresses `[this+0x2f8]` / `[this+0x2f9]`

`fcn.100203c0` gates the current maxima on `byte [this+0x2f8] == 0x44`. Both
bytes are set together, and they are the two **board addresses**:

```
0x1000af87  mov byte [esi+0x130], 0x44     ; main / motor board
0x1000af8e  mov byte [esi+0x131], 0x40     ; light board
   -- alternate path --
0x1000b093  mov byte [esi+0x130], 0x24     ; older main board
0x1000b09a  mov byte [esi+0x131], 0x20     ; older light board
```
`[VERIFIED-FROM-BINARY]`. `esi` here is the comms object that lives at
`scanner+0x1c8`, so `comms+0x130 == scanner+0x2f8` and
`comms+0x131 == scanner+0x2f9` — which is why the same two fields are addressed
both ways throughout the binary (`lea ecx,[esi+0x1c8]` for the emitter `this`,
`byte [esi+0x2f9]` for the address argument).

Consequence for §2b: the "board `0x44`" row is the **newer address pair
(0x44 main / 0x40 light)**, i.e. the address map this project targets. The
"other" row is the legacy `0x24`/`0x20` pair. Every light-board packet in §5
and §7 therefore uses address `0x40`, and the 8/24/24/8 maxima are the correct
ones for it. `[VERIFIED-FROM-BINARY]`

`[UNKNOWN]`: which runtime condition selects `fcn.1000afd0`'s `0x44/0x40` branch
versus `0x24/0x20`. Not required for the F-135 path.

---

## 10. Independent re-verification pass

Sections 2b, 2c, 2c-bis, 2d-bis, 1c and 9 were produced by a second, independent
static pass over `TLB.dll` (radare2 `aaa` + full `.text` linear disassembly,
mechanical `esp` tracking, no reuse of the first pass's notes). Points of
agreement and disagreement:

**Confirmed independently** — the `0x81` slot order `B, Ir, R, 0, G`; the `0x82`
12-byte layout with the period in `u16[5]`; the `on ≤ N-2` clamp; the
`8/24/24/8` and `4/20/20/0` maxima and the `0xffd` exposure clamp; the registry
value names and `CiConfigLight` field map; `FN_GetCalibrateInfoLight` (FN 195,
`0x1003dfb0`) performing zero device I/O and copying `+0x58…+0x64` straight to
its out-params at `0x1003e185`–`0x1003e1a3`; `fcn.10020230` multiplying
caller-supplied bases rather than returning 1.0.

**Corrected** — §2c (defaults are **1**, not 0); §2d-bis (R/G stop at 64000, not
65500); §1c (hive is provably HKLM); §9 (`+0x2f8`/`+0x2f9` are board addresses,
not an opaque model byte).

**FN-id recovery method, re-derived and cross-checked.** The name table is the
jump table at `.rdata:0x10019ed0` (362 entries) used by `fcn.10017430`:
`lea eax,[ecx-1]; cmp eax,0x169; ja default; jmp [eax*4 + 0x10019ed0]`.
Therefore **`FN id = jump-table index + 1`**, and each case block is
`mov ecx,[esp+0x14]; push <name ptr>; call fcn.10031ca0`. Decoding the whole
table yields `FN_bDrvLampOn = 112` — the known-good calibration point — plus
`FN_bCalibrateFindLedCurrent = 31`, `FN_bCalibrateFindLedCurrentSub = 32`,
`FN_bCalibrateFindLedDutyCycle = 33`, `FN_bCalibrateLEDs = 40`,
`FN_bCalibrateFindCorrections = 27`, `FN_GetCalibrateEEProm = 192`,
`FN_GetCalibrateInfoColorMatrix = 193`, `FN_GetCalibrateInfoDpi = 194`,
`FN_GetCalibrateInfoLight = 195`, `FN_PutCalibrateInfoLight = 256`.
`[VERIFIED-FROM-BINARY]`

At a logger call `fcn.1001acd0`, the argument order is
`(logObj, FN_id, EC_id, …)` — i.e. the **first** pushed constant of the pair is
the error code and the **second** is the FN id. Example: `fcn.10020dc0`
`0x100214fd` pushes `0xda` then `0x28` ⇒ FN 40 (`FN_bCalibrateLEDs`), EC 218.
Reading them the other way round is the trap that produced the "index-linear"
dead end.

**Corroboration from the sibling DLLs.** `TLC.dll` (F-335) carries a light log
header `TECooler_I\tTECooler_DutyCycle\tVisOn\tIrOn\tCurrent_R\tCurrent_G\t
Current_B\tCurrent_Ir\t`, and `TLB.dll` has the matching one at
`.rdata:0x1005c1d0` with format string `.rdata:0x1005c37c` =
`%d\t%d\t%f\t%f\t%f\t%d\t%d\t%u\t%u\t%u\t%u\t%f\t%f\t%f\t%f\t%u`. The four
`Current_*` are `%u` while the four `Duty_*` are `%f` — consistent with small
integers plus doubles, and inconsistent with `Current_*` being a five-figure
light level. `TLA.dll` (F-235) formats it as
`… IrLEDOnTime = %4u, VisIrRatio = %2.2f, Current_Ir = %4u`.
`[VERIFIED-FROM-BINARY]`
