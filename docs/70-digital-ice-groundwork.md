# 70 — Digital ICE: groundwork

Status after pass 1 (2026-08-12). **No IR capture exists and none was made.**
Nothing in this document has been seen working on film. What is here is: the
vendor algorithm located and identified, the infrared data path mapped end to
end out of the binaries, and the decoder made able to segment and unpack a
4-channel line without regressing the 3-channel one.

Read `docs/54` §2.5 first for what the UI used to promise. That entry said the
blocker was "the decoder accepts 6000 only". **That blocker is gone.** The
blockers that remain are listed in §5 and none of them is a line length.

---

## 0. The one-paragraph version

Digital ICE on this scanner is **not** in `PakonIMAu.dll`. It is a separate
third-party library, `DMLDICELib.dll`, shipped in the same directory and loaded
by `GetProcAddress` from **`TLB.dll`** — the transport library — so ICE runs on
the raw planar scan data *before* the imaging library ever sees it. Its whole
public surface is five C functions. The scan-side plumbing (IR lamp bit, IR
FPGA mode bit, IR dark/gain, IR crosstalk, IR transport speed) is all in
`TLB.dll` and is now mapped. `ColorNegativePath::CalcDei`, the lead this pass
was told to chase first, is **not** ICE — see §1.

---

## 1. `CalcDei` — REFUTED. DEI is not Digital ICE.

The hypothesis was that "DEI" means *Defect Elimination by Infrared*. It does
not. DEI is a **scene enhancement index**: a weighted score plus a CART
decision tree that decides how aggressively to tone an image.

The decisive evidence is not in the binary at all, it is the vendor's own data
file, shipped uncompressed on the install ISO at
`fx35install/program files/Pakon/F-X35 COM SERVER/anselinstalldir/dataPathItems/dei/dei-default.dpi`:

```
version = 1.3
key = DeiDPI

# The following value will adjust the Tonehelper Dei score
# depending on whether or not tonehelper would have chosen aggressive/
# not aggressive & the User Contrast Position or enabled capabilities
# override the tonehelper decision.
adjToneHelperDeiValue = 2

# The following are algorithms followed by their corresponding weights
#  for dei (linear) calculation.
flesh = 10
toneHelper = 12
nra = 5
fugc = 0

# CART analysis for DEI
decisionTree = dTree1
```

and its tree, `dei/dTree1`, whose metrics are `AGGRESSIVENESS`, `ABS_FLESH`,
`LUM_MAX`, `LUM_MIN`, `EXPOSURE`, `EDGE_MIN`, `EDGE_MAX` — 17 nodes, terminal
class 0 or 1. Not one of them is infrared, spatial, or defect-shaped.

Corroborating, from `strings PakonIMAu.dll`: the DEI parameter block is
`DeiExpCorrHigh/Mid/Low`, `DeiExposureLevel`, `DeiFugcWorkHigh/Mid/Low/Total`,
`DeiNeuFugc`, `DeiScpLut`, `DeiLumMin/Max`, `DeiEdgeMin/Max`,
`DeiAggressiveness`, `DeiFleshButton`. Source paths `\Atc\ansel\src\libDei.ansel\`.
`AnsDeiParams::verifyDecisionTreee` [sic], `AnsDeiDpi::readDecisionTree`.

So `docs/64`'s ruling — dei OUT of the tone port, by execution order — remains
correct, and it was also correct to leave it alone. It is simply a different
feature. `ColorNegativePath::CalcDei` at `0x101081e0` computes an exposure /
enhancement decision, not a defect map.

**Two other near-misses, ruled out for the record:**

* `docs/64` states that `AnsAreaCapability` / `libAREA.ansel` "is almost
  certainly what the Frosty — Digital Ice Technology badge refers to". That is
  **wrong**. AREA is red-eye and blemish work: its strings include
  `KRD_RE_Grow::Find_Best_Area()`, `Redeye MaxArea exceeded`,
  `defect Y, H, Sat=(`, `correction_glint_mask_%s_defect_%d.tif`,
  `correction_recolored_border_…`, `correction_regrained_…`. KRD = Kodak
  Red-eye Detection. It is a portrait retoucher, not a film-defect remover.
  The 732-function scope figure in `docs/64` is a real number attached to the
  wrong feature.
* `libDr.ansel` (`AnsDustCapability`, `AnsScratchCapability`,
  `ImaDROperationT<DRdustSettings, ImaDefectOp>`) *is* dust and scratch
  removal, but it is **operator-driven and visible-light only** — its API is
  `AnsDustCapabilityImpl::addRectangle`, `<Rectangle,Dust Settings:`, and its
  parameters (`dr/dust/dust-colorNegative.su`) are density thresholds
  (`DUST_DARK_THRESHOLD = 2352`, `DUST_LIGHT_THRESHOLD = 1176`,
  `DUST_FILTER_SIZE = 11`, `DUST_EROSION_PIXELS = 6`) with the file's own
  comment explaining they are `200/255 × 3000` printing density. You draw a
  box, it fills it. Nothing infrared.

**There is no string containing `ICE`, `IR`, or `Infrared` anywhere in
`PakonIMAu.dll`.** The imaging library never sees the infrared channel.

---

## 2. Where Digital ICE actually is

### 2.1 `DMLDICELib.dll`

`fx35install/program files/Pakon/F-X35 COM SERVER/DMLDICELib.dll`
md5 `10e2095015c2580998e063b563407041`, 241,664 bytes, PE32 i386,
built **2000-06-01**, MSVC, static CRT. `DICEVersion()` returns **34**.

Full export list — this is the entire public surface:

```
?DICEVersion@@YAJXZ                                          0x1002b630
?DMLDICEBegin@@YAPAXKUDICEInfoStaticTag@@@Z                  0x1002b640
?DMLDICEEnd@@YAJPAX@Z                                        0x1002b6d0
?DMLDICEProcess@@YAJPAXUDICEInfoDynamicTag@@@Z               0x1002b6f0
?DMLDICEDefectCount@@YAJPAXUDICEInfoDynamicTag@@PAK2@Z       0x1002b780
```

It imports **only KERNEL32** (69 symbols; everything else is statically linked
CRT). That matters — see §4.

### 2.2 Who loads it

`TLB.dll`, `TLA.dll` and `TLC.dll` all contain the mangled names.
`PakonIMAu.dll`, `tlx.dll` and `AIDToolkit.dll` do not. The loader in
`TLB.dll` is at **`0x10012ca0`**, `"%s\\DMLDICELib.dll"` at `0x10067c30`:

```
0x10012cea  call GetProcAddress   "?DMLDICEBegin@@…"        -> [ebx+0x24]
0x10012cf8  call GetProcAddress   "?DICEVersion@@YAJXZ"     -> [ebx+0x30]
0x10012d06  call GetProcAddress   "?DMLDICEProcess@@…"      -> [ebx+0x34]
0x10012d14  call GetProcAddress   "?DMLDICEDefectCount@@…"  -> [ebx+0x38]
0x10012d22  call GetProcAddress   "?DMLDICEEnd@@YAJPAX@Z"   -> [ebx+0x28]
```

Handle from `Begin` is cached at `[ebx+0x2c]`; the destructor at `0x10013350`
calls `[esi+0x28]` (`End`) on it. `DMLDICEProcess` is invoked at
**`0x10026fe6`** (`mov edx, [esi+0x2c]; push edx; call dword [esi+0x34]`), the
48-byte dynamic tag having been `rep movsd`'d onto the stack immediately
before.

### 2.3 `DICEInfoStaticTag` — 32 bytes, 8 dwords

`DMLDICEBegin(key, tag)` requires `key == 0x65` (101) exactly
(`0x1002b65d cmp ecx, 0x65`), then allocates a **0xc38c8-byte (800,968)**
context. `TLB.dll` builds the tag at `0x10012d5b`–`0x10012da8` as:

| offset | value TLB passes | meaning |
|---|---|---|
| +0x00 | `0x20` | struct size |
| +0x04 | `2` | **must be 2 or `DefectCount` returns −5** (`0x1002b7c5 cmp dword [ebx+0xc], 2`) |
| +0x08 | `1` | unknown |
| +0x0c | `14` | **bits per sample.** `fcn.10001130` at `0x10001174`: 12 → full scale `0x457ff000` = 4095.0f, 14 → `0x467ffc00` = 16383.0f, stored at `this+0x28a8` |
| +0x10 | `2` | unknown |
| +0x14…+0x1c | `0,0,0` | reserved |

14-bit at 16383.0 full scale is exactly what `pakon_decode.to_rgb14` produces.

### 2.4 `DICEInfoDynamicTag` — 48 bytes, 12 dwords

`fcn.100011c0` copies all 12 dwords to `this+0x28`. Field map, from that copy
plus the ROI derivation at `0x10001202`–`0x10001215`:

| offset | → object | TLB passes | meaning |
|---|---|---|---|
| +0x00 | +0x28 | `0x30` | struct size (48) |
| +0x04 | +0x2c | `[ebp+0x58]` | **pointer to the 4-plane image buffer** |
| +0x08 | +0x30 | `[ebp+0x2c]` | width |
| +0x0c | +0x34 | `[ebp+0x30]` | height |
| +0x10 | +0x38 | `0x12c` (300) | unknown scalar |
| +0x14 | +0x3c | `(retval != 2)` | flag from a preceding call |
| +0x18 | +0x40 | `0` | **custom-ROI flag.** 0 ⇒ ROI is the whole frame |
| +0x1c…+0x24 | +0x44…+0x4c | `0, 0, w−1` | ROI x0, y0, x1 |
| +0x28 | +0x50 | `h−1` | ROI y1 |
| +0x2c | +0x54 | `0` | reserved |

With the ROI flag 0, `this+0x44..0x50` are set to `(0, 0, width−1, height−1)`.

### 2.5 The input buffer layout — 4 contiguous planes, IR last

**This is the load-bearing fact.** `fcn.10016890`, the main entry point,
computes its plane bases at `0x10016956`–`0x10016962`:

```
0x10016937  mov  edi, dword [esp+0x1c4]   ; width
0x10016944  mov  eax, dword [esp+0x1c8]   ; height
0x1001694f  mov  edx, dword [esp+0x1c0]   ; buffer  = plane 0
0x10016956  mov  ecx, edi
0x10016958  imul ecx, eax                 ; ecx = width*height
0x1001695b  lea  ebp, [edx + ecx*2]       ; plane 1 = buf + 2wh bytes
0x1001695e  lea  edx, [ebp + ecx*2]       ; plane 2 = buf + 4wh
0x10016962  lea  ebx, [edx + ecx*2]       ; plane 3 = buf + 6wh
0x10016a4a  mov  cx,  word [ebx]          ; first read is from plane 3
```

Four planes of `width × height` uint16, contiguous, **plane 3 is the infrared
record** and is what the algorithm reads first. Corroborated independently by
the statistics pass `fcn.10001550` at `0x100015f5`–`0x10001606`, which walks
plane 0 with the ROI offset applied and pairs it with a pointer exactly
`3·width·height` uint16 further on.

`pakon_decode.planar_rgbir()` produces this exact buffer.

### 2.6 Algorithm selection — width 2000 is above the split

`fcn.100012d0` at `0x100012e5`:

```
mov eax, dword [esi+0x30]   ; width
cmp eax, 0x7cf              ; 1999
jle  <narrow path>
mov ecx, dword [esi+0x40]   ; custom-ROI flag
```

giving four entry points:

| width | ROI | entry |
|---|---|---|
| > 1999 | no | **`fcn.10016890`** ← the Pakon's 2000-px case |
| > 1999 | yes | `fcn.10020ed0` |
| ≤ 1999 | no | `fcn.100021e0` |
| ≤ 1999 | yes | `fcn.1000c4b0` |

`fcn.10016890` is 22,042 bytes, 5,458 instructions, 533 basic blocks,
cyclomatic complexity 218, out-degree 61. Each of the four entry points spawns
exactly one worker thread (`CreateThread` at `0x10016a27` for this one) and
`WaitForSingleObject`s it — a straightforward split-the-image-in-half
parallelisation, not a pipeline.

---

## 3. The infrared data path in `TLB.dll`

All addresses [VERIFIED-FROM-BINARY] from `research/native/TLB.text.asm`
(private remote) against `TLB.dll` md5 `193d9b2ce0a4b77ae9b78262bd06c0fc`.

### 3.1 Turning IR on — two independent switches

**The lamp.** `FN_bDrvLampOn` = `0x1002c5f0`. Register **`0x80`** on the lamp
board is an on/off bitmask: **bit 0 = visible group, bit 1 = IR**
(`0x1002c64f mov edi, 1` / `0x1002c659 or edi, 2`, written at `0x10009ba0`
with `push 0x80`). Registers `0x81` (levels) and `0x82` (on-times) are as
already documented in `pakon_scan.lamp_on`, and their IR slots are the ones
this repo already fills with zeros.

`fcn.100203c0`, previously recorded here as a *clamp*, is more precisely a
**minimum on-time / warm-up table**, selected by scanner type `[ecx+0x2f8] == 0x44`
and by `bIrOn`, writing four out-params (R, G, B, Ir):

```
type 'D' (0x44), IR on : 8, 0x18, 0x18, 8      (0x100203dd..0x100203f3)
type 'D',       IR off : 4, 0x14, 0x14, 0      (0x10020408..0x1002041e)
other,          IR on  : 8, 8,    8,    8      (0x10020437..0x1002044d)
other,          IR off : 6, 8,    8,    0      (0x10020462..0x10020478)
```

The fourth out-param is 0 exactly when IR is off, which is what identifies it
as the IR slot. The numbers are unchanged from what `pakon_scan` already
enforces; the reading of *why* they rise with IR on is unchanged too.

**The sensor.** Separate and mandatory: `FN_bDrvPutCcdIrMode` = `0x10029860`
sets **bit 8 (`0x100`) of the CCD FPGA control register**:

```
0x10029872  push 0x100                    ; the bit
0x1002987a  call 0x10029770               ; bDrvPutCcdFpgaControlReg
```

`FN_bDrvPutCcdFpgaControlReg` = `0x10029770` keeps a 10-bit shadow at
`this+0x358` and pushes it through **command `0x82`, sub-index `0`** on the CCD
board object at `this+0x1c8`. Known bits: `0x001` acquire/DX-start, `0x002`
toggled with integration-time changes, `0x060` set once on first FPGA config,
`0x100` IR mode.

The register-write primitive is `0x1000a5d0`, which accepts only commands
`0x82` and `0x84` (`0x1000a61a sub eax, 0x82` / `0x1000a621 sub eax, 2`);
`0x83` reads back what `0x82` wrote.

`FN_bDrvPutCcdFpgaSettings` = `0x1002c340` is the only caller of IR mode:
`(errCtx, uiCcdPixelHeight, uiCcdPixelOffset, uiCcdIntegrationTime, bIrMode,
bBinning, …)` — argument names taken from its own assertion strings. It also
writes sub-index 4 = pixel offset, 5 = offset+height, 6 = integration time
(max `0xffd` = 4093). The non-IR call in `FN_bDrvInitCcd` at `0x1002d6f5`
passes height `0x7d0` = **2000** and offset `0x3e` = 62 — this is the origin of
"2000 px".

`FN_bHaveIROn` (enum id 329) **could not be located**: the id never appears in
`.text` and the function is not exported. Name only.

### 3.2 The 4-channel wire line — 3N interleaved RGB, then N IR

`FN_bGetScanLines` = `0x1001d170`, signature
`(errCtx, pAccumR, pAccumG, pAccumB, pAccumIr, uiChannels, uiStartPixel,
uiPixelsPerLine, uiLines)`.

Nothing hard-codes 6000 or 8000. The line size is computed:

```
0x1001d195  imul ebp, dword [esp+0x54]    ; channels * pixelsPerLine
0x1001d1a2  cmp  eax, 4                   ; is this a 4-channel scan?
```

Sync marker, confirming bit 0:

```
0x1001d2b0  test byte [ebp], 1
0x1001d2b4  jne  0x1001d2be
0x1001d2b6  add  ebp, 2
```

Visible de-interleave, **6-byte stride = 3 words per pixel**:

```
0x1001d300  movzx ebx, word [eax]         -> R
0x1001d305  movzx ebx, word [eax+2]       -> G
0x1001d30e  movzx ebx, word [eax+2]       -> B
0x1001d321  add   eax, 2                  ; total +6 bytes per pixel
```

IR extraction, only when 4-channel, **2-byte stride from word 3N**:

```
0x1001d338  je   0x1001d360               ; skipped entirely when 3-channel
0x1001d341  mov  ecx, dword [esp+0x54]    ; N
0x1001d345  lea  edx, [edi + ecx*2]       ; startPixel + 2N
0x1001d348  add  edx, ecx                 ; startPixel + 3N
0x1001d34c  lea  ecx, [ebp + edx*2]       ; src = lineBase + 2*(3N + startPixel)
0x1001d357  add  ecx, 2                   ; one word per pixel
```

Line advance `0x1001d372 lea ebp, [ebp + eax*2]` with `eax = channels*N`.

Independently confirmed in the MMX correction pass: the visible loop at
`0x10024ba0` consumes 24 bytes (4 px × 3 ch) per iteration, and when it exits
`esi` — sitting exactly at word 3N — is used unchanged as the base of the IR
loop at `0x100251b0`.

**So the note in `docs/54` §2.5 was right**: 3n interleaved RGB words followed
by n IR words. For N = 2000 that is words 0…5999 RGB, words 6000…7999 IR,
8000 words / 16,000 bytes per line.

### 3.3 IR calibration in the vendor

The fixed-pattern correction object carries, per pixel:

| offset | field | type |
|---|---|---|
| +0x20/24/28/**2c** | Dark_R/G/B/**Ir** | `u16*` |
| +0x30/34/38/**3c** | Gain_R/G/B/**Ir** | `u32*` |
| +0x40/44/48 | SmearC_R/G/B | scalar |
| +0x4c/50/54 | Smear_R/G/B | `u16*` |

**There is no `Smear_Ir` and no `SmearC_Ir`.** The IR channel gets dark and
gain only. Conversion into the MMX operands at `0x10024aa0` stores `Dark_Ir` as
u16 and `Gain_Ir` as the u32 gain `>> 2`.

`FN_bCalibrateFixedPatternIrLag` = `0x1001fb80` acquires with **visible lamps
off and the IR LED on** (`0x1001fc0d push 1` = bIrOn, `0x1001fc0f push 0` =
bVisOn), 128 lines averaged (`0x1001fc2d push 0x80`). Its three
post-processing loops then read the **R, G and B** accumulators — never the IR
one — and bias each so the plane minimum lands on **300** (`0x1001fd15 cmp esi,
0x12c`). That is what "IR lag" means here: how much of the IR exposure leaks
into the visible channels. It produces three visible-channel offset tables.

Calibration acquisition line counts (`FN_bCalibrateAcquireAndAverageLines` =
`0x1001d590`, arg `a5`): dark offset 32, fixed-pattern dark 128, LED current
32, LED duty cycle 32, fixed-pattern bright 128, **IR lag 128**. Its
accumulators are four contiguous u32 planes of N entries, R/G/B/Ir
(`0x1001d5cf`–`0x1001d5d9`), zeroing `N*16` bytes when 4-channel and `N*12`
when 3 (`0x1001d5f0 shl ecx, 4` vs `0x1001d5f8 shl ecx, 2`). Its log header is
`"R\tG\tB\tIr\t%u\t%u\t%u\r\n"`.

**Not determined:** the routine that *computes* `Gain_Ir` from a bright IR
reference. It is somewhere in `FN_bCalibrateFindCorrections`
(`0x100214xx`–`0x100218xx`); consumers, storage type and logger are known, the
producer is not.

### 3.4 IR crosstalk — visible bleeds into IR, removed proportionally

Registry key `IrCrossTalkFactor`, read at `0x10010d95` into settings `+0x40`
(global `g+0x15e0`). **Default 10** (`0x10010c31 mov dword [esi+0x40], 0xa`),
clamped to **[1, 20]** at `0x10010da9`–`0x10010dbb`. Converted to a fixed-point
reciprocal `0x10000 / factor` at `0x10024b18` and splatted into four u16 MMX
lanes.

The arithmetic, `0x100251b0`–`0x100251d1`:

```
movq    mm2, qword [esi+eax]              ; raw IR words
psubusw mm2, qword [eax+0x10079438]       ; - Dark_Ir
movq    mm3, qword [edx]                  ; corrected R plane
pmulhuw mm3, mm1                          ; R / IrCrossTalkFactor
pmulhuw mm2, qword [eax+0x10078490]       ; * Gain_Ir
paddusw mm2, mm0 ; psubw mm2, mm0         ; clamp to 0x3FFF
psubusw mm2, mm3                          ; - the visible bleed
```

i.e. `IR = sat14((IR_raw − Dark_Ir)·Gain_Ir) − R_corrected / factor`.
Only the **red** plane contributes — no green or blue term was found. It runs
inside the same pass that applies the IR dark and gain, and it consumes the
*finished* red output plane, so ordering is fixed.

Ported as `pakon_decode.apply_ir_crosstalk` (§4 below).

The corrected output layout, set at `0x10024b43`–`0x10024b65`, is four separate
planar u16 planes R (base), G (base+2N), B (base+4N), Ir (base+6N) — the same
shape `DMLDICEProcess` wants, one line at a time.

### 3.5 `IrChannelSavedInPlanarFile` and the planar file

Read at `0x10010cc8` into settings `+0x20` (global `g+0x15c0`), **default 0**
(`0x10010bc3`). One read site, `0x100364a3`, forwarding it as arg 13 of
`FN_bSaveToMemory` (`0x10028520`), which probes for a capability and **silently
forces the flag back to 0 if unsupported** (`0x10028674 mov dword [esp+0x60], 0`).

The "planar file" is the multi-plane 16-bit intermediate handed to
`PakonIMAu.dll` through a `GetProcAddress` table bound at `0x10012f43`:
`PIFileOpenPlanar`, `PISaveFilePlanar_8`, `PIFileSpecsPlanar_8`,
`PIColorAdjustPlanar`, `PIRotatePlanar`, `PIScaleAndRotatePlanar`,
`PIAnselColorSceneBalancePlanar`. `PIRotatePlanar` is not IR-specific.

**Not determined:** how the planar file header encodes 4 planes (inside
`0x10026c90` / `PakonIMAu.dll`). `PlanarFileHeaderVersion` (settings `+0x24`,
`0x10010ce5`) is the likely companion knob.

### 3.6 IR transport

Per-resolution motor profiles at parent offsets `+0x80` (Base16_35), `+0x618`
(Base8_35), `+0xbb0` (Base4_35), stride `0x598`, each carrying **separate
visible and IR speed and adjust**. Registry reader `0x10010500`:

| member | key |
|---|---|
| +0x24 / +0x28 | `MotorAdjust` / `MotorAdjust_Ir` |
| +0x2c / +0x30 | `MotorAdjustDrag` / `MotorAdjustDrag_Ir` |
| +0x44 / +0x48 | `MotorSpeed`(`Plus`) / `MotorSpeed_Ir`(`Plus_Ir`) |

`Plus` variants selected by a flag at `+0x54` (`0x10010645`). Packed into the
wire packet at `0x10010916`: `packet[2..3] = MotorSpeed`, `packet[4..5] =
MotorSpeed_Ir`, both LE u16; adjusts at `0x1001674c` into words 0/4/2/6. The
config dump string `"Offset %u, Speed %d, Speed_Ir %d, Adjust %d, Adjust_Ir %d"`
is written by `0x10016780`.

`pakon_scan.MOTOR_SPEED_IR = {4: 19335, 8: 7580, 16: 4850}` is already this
table. Also per-IR: `WaitForLamp_Ir` (double, settings `+0xa8`), `Current_Ir`
(exposure record `+0x64`), `Max_Ir` (`+0x68`, the IR LED current ceiling),
`DutyCycle_Ir` (`+0x88`), `DutyCycleOpenGate_Ir`.

---

## 4. What changed in this repo

The theme: **the decoder stops assuming 3 channels, and every place that would
have failed *quietly* on a 4-channel capture now fails loudly instead.** No
arithmetic on the 3-channel path changed — proven in §6.

### `tools/pakon_decode.py`

* New geometry vocabulary beside the existing constants: `CHANNELS_IR = 4`,
  `WORDS_PER_LINE_IR = 8000`, `SUPPORTED_CHANNELS`, `LINE_WORD_CANDIDATES`,
  and the helpers `words_per_line()`, `channels_for_words()`.
  `WORDS_PER_LINE = 6000` is untouched and remains every caller's default.
* `detect_line_words(words)` — modal sync-gap detector, restricted to known
  lengths, raising on anything else rather than guessing.
* `segment_lines(words, expect)` — `expect=None` now auto-detects. **New
  wrong-geometry guard before any line is cut**: if the modal sync gap is
  itself a supported line length but not the requested one, refuse and name
  the real geometry. This closes a real hole. The pre-existing last-marker
  branch (`end = s + expect`, with no next marker to check against) fabricated
  exactly one sheared line on an 8000-word capture segmented as 6000, which
  meant the modal-gap fallback never ran and the caller got a "successful"
  one-line decode. One bad line is worse than none.
* `to_rgb14(lines)` — channel count from the line width. For 8000-word lines
  it unpacks **3N interleaved then N contiguous**, per §3.2. Getting this
  wrong (a naive `reshape(n, 2000, 4)`) is the single easiest mistake here and
  was in fact the first thing written in this pass before the binary evidence
  came back.
* `split_visible_ir(planes)` — the one place that knows IR is index 3.
* `apply_ir_crosstalk(...)` — §3.4's arithmetic, exactly. Dark and gain tables
  are **arguments, not loaded from disk**, so it cannot be run against tables
  that do not exist.
* `planar_rgbir(planes)` — the `DMLDICEProcess` buffer contract from §2.5.
* `ICE_PORTED = False` and `apply_ice()`, which raises. Per repo convention a
  False flag raises rather than no-opping — and specifically because
  `docs/54` §2.5 flagged an inert `ice` parameter that could label a frame as
  ICE-processed with nothing applied to pixels.
* `calibration_names(channels)`; `load_unit_calibration(cal_dir, channels)`.
* `average_profile(..., expect)` pass-through.
* `measure_pitch_lines(capture, line_words=None)` — this reader strides
  blindly and never checks a marker, so it now detects the line length first,
  and takes the mean over the **visible** channels only.

### `tools/pakon_gate.py`

Kept deliberately independent of the decode path, as its own docstring
requires — so it got its own copy of the geometry rather than an import.

* `CHANNELS_IR`, `WORDS_PER_LINE_IR`, `LINE_WORD_CANDIDATES`.
* `split_lines(buf, phase, line_words=WORDS_PER_LINE)` and
  `find_phase(buf, line_words)`. **No auto-detect here on purpose**: the live
  capture loop already knows what it asked the hardware for, and a detector
  guessing wrong mid-roll would look exactly like a lamp failure.
* `classify_lines` derives the channel count from the line width and
  classifies the **visible channels only**. An IR plane says nothing about
  whether the white LEDs are lit, and folding it into the level would drag the
  dark/clear decision toward a channel the thresholds in `calibration/` were
  never measured against.

### `tools/pakon_app.py`

`probe_channels()` now answers two questions that stopped being the same one:

* `unpackable` — `pakon_decode` can segment and unpack this geometry (6000 or
  8000).
* `decodable` — the *rendering* path can make a picture. Still 3-channel only:
  `rgb14.npy`, the committed `dark_2000x3`/`gain_2000x3` tables and the Go
  TIFF hand-off are all RGB.

`job_open` still refuses a 4-channel capture, but now says the true reason
(no IR dark/gain reference, ICE not ported) instead of blaming the decoder.

### `tools/pakon_framing.py`

`_load()` strides blindly with no sync check. It now verifies the modal marker
spacing over the first few lines and refuses a recognised-but-wrong geometry.

### `tools/pakon_scan.py`

`lamp_on()` **still refuses IR** — this pass wrote nothing to hardware and
changed no register. Only the refusal *message* changed, because the reason it
gave was now false. It lists the four things in §5 instead.

---

## 5. What remains on the hardware side — specification only

**None of this was implemented. Do not enable IR by flipping one flag.**
Every item below needs review before it is written to the scanner.

1. **IR FPGA mode.** Set bit `0x100` of the CCD FPGA control register through
   command `0x82`, sub-index `0`, on the CCD board — §3.1. This is separate
   from the lamp and both are required. `pakon_scan` has no equivalent today.
2. **IR lamp enable.** Lamp register `0x80` bitmask, bit 1 = IR (§3.1). The
   existing `0x81`/`0x82` encodings already carry IR slots; they are only ever
   fed zeros.
3. **Levels for this unit.** From the vendor's own `ColNegIr` key for this
   scanner (device EEPROM serial 16275 matches; see
   `research/windows-registry/lamp-calibration.md` on the private remote):
   `Current_R/G/B/Ir = 5/20/11/4`,
   `DutyCycle = 0.917161/0.955468/0.865802/0.887000`,
   `DutyCycleOpenGate = 0.658333/0.380378/0.166885/0.887000`,
   Gain 13/13/13, Offset −18/−26/−20. Note `Current_R = 5` is legal **only**
   with IR on — with IR off the minimum-on-time table caps R at 4.
4. **IR exposure triad.** `DpiBase16_35` IR integration **2498**
   (non-IR 4093), so `N = trunc(2498 × 0.24) = 599`. Base 8 → 2128, base 4 →
   1250. `pakon_scan` currently derives the triad for the non-IR case only.
5. **IR transport speed.** `MOTOR_SPEED_IR` is already tabled in `pakon_scan`
   (`{4: 19335, 8: 7580, 16: 4850}`) and nothing selects it. Also
   `MotorAdjust_Ir` / `MotorAdjustDrag_Ir`, which this repo has never read.
6. **IR calibration references, which do not exist.** This is the real cost.
   * `dark_2000x4.npy` / `gain_2000x4.npy` — an infrared dark and an infrared
     clear reference. `calibration/` has neither, and
     `pakon_decode.calibration_names(4)` names the files that would be needed.
   * The visible tables must be **retaken**, not reused. Turning IR on changes
     the visible channels: each is lit for a shorter fraction of the cycle,
     which is exactly why the minimum-on-time table rises to R≤8/G≤24/B≤24.
     A dark taken at integration 4093 with IR off is a wrong number, not a
     noisy one, against a capture taken at 2498 with IR on. `calibration/`'s
     own `README.json` triad-checking machinery already says so.
   * The vendor's own IR-lag step (§3.3) is a *fifth* reference: visible lamps
     off, IR on, 128 lines, producing three visible-channel offset tables
     biased to a minimum of 300. Whether the port needs it is open.
7. **Sidecar.** `levels_R_G_B_Ir` already exists in `calibration/README.json`
   and the scan sidecar, set to `[…, 0]`. An IR capture must record a non-zero
   fourth entry and the IR triad, or `check_capture_exposure` will not be able
   to tell the two calibration regimes apart.

---

## 6. Verification

Run from the repo root. Results as of this pass.

| command | result |
|---|---|
| `python3 tools/pakon_gate.py selftest` | **PASS** — 4 captures, `ref_dark`/`ref_bright`/`test_nofifo`/`roll`, clear-reference reconstruction −0.93 counts on 50029 |
| `python3 tools/pakon_decode.py geometry captures/gold400.bin captures/strip_cal.bin` | **PASS** — worst residual 1.3 % against 5 % tolerance |
| `python3 tools/test_render_f135.py` | **PASS** |
| `python3 tools/test_calib.py` | **PASS** — 141/141 |
| `python3 tools/pakon_decode.py verify-lut` | **MATCH** |
| `python3 tools/pakon_render.py verify captures/strip_cal.bin --sba-default` | **FAIL — PRE-EXISTING.** "frame count differs — reference 14, ours 17". Confirmed by re-running with `HEAD:tools/pakon_decode.py` and `HEAD:tools/pakon_gate.py` swapped in: identical failure, identical numbers. It is a framing disagreement between the CLI and the app renderer, not a decode-geometry problem. |
| `python3 tools/test_gold400_parity.py` | **FAIL — PRE-EXISTING.** 183,770 / 9,000,000 sample mismatches, max magnitude 2758. Identical with the baseline decoder swapped in. Colour path. |
| `python3 tools/pakon_parity.py` | **FAIL — PRE-EXISTING.** "parity driver disagrees with AnselEngine.render_scene in 147335 samples". Identical with the baseline decoder swapped in. Colour path; the tree has uncommitted Ansel work. |

**The strongest single result** — direct byte-equality of the decode path
before and after, on real captures, not synthetic:

```
captures/strip_cal.bin  segment_lines identical=True  to_rgb14 identical=True  pitch 1349.0 -> 1349.0
captures/gold400.bin    segment_lines identical=True  to_rgb14 identical=True  pitch 1656.0 -> 1656.0
```

(17,450 × 6000 and 31,203 × 6000 arrays compared elementwise against
`HEAD:tools/pakon_decode.py`.)

Plus a synthetic 4-channel line built to the §3.2 layout — R=100, G=200,
B=300 interleaved, IR=999 contiguous — which unpacks to `(5, 2000, 4)` with
`[100, 200, 300, 999]`, splits, planarises to `(4, …)` with plane 3 = 999, and
round-trips through the gate's splitter at 8000 words. Both `segment_lines`
directions refuse the wrong geometry with a message naming the right one.

---

## 7. Open

1. **`fcn.10016890` is not ported and no line of it is.** 22 KB, 533 basic
   blocks. A hand port is a multi-pass project on the scale of the tone work.
2. **But it is unusually well suited to the harness this repo already has.**
   `DMLDICELib.dll` imports **only KERNEL32** — no MSVCRT, no COM, no
   registry, no file I/O on the hot path — and the five-function API takes
   flat structs by value. That is a smaller emulation surface than
   `pakon_shasta_analyze_golden.py` already handles. The one complication is
   `CreateThread`: each entry point spawns exactly one worker and waits on it,
   so the stub must run the thread body inline before returning a fake handle.
   **Recommended next step: stand up a Unicorn golden for `DMLDICEProcess`
   against a synthetic 4-plane buffer, before writing any Python.** That gives
   a reference oracle first, which is the order everything else on this
   project was done in.
3. **`Gain_Ir`'s producer is unlocated** (§3.3). Needed before an IR clear
   reference can be computed the vendor's way rather than by analogy with the
   visible one.
4. **`FN_bHaveIROn` unlocated** (§3.1); enum id 329 appears nowhere in `.text`.
5. **Planar file header plane count unlocated** (§3.5). Only matters if this
   project ever wants to read or write vendor planar files.
6. **`DICEInfoStaticTag` fields +0x08 and +0x10, and `DICEInfoDynamicTag`
   +0x10 (300) and +0x14, are unidentified.** TLB passes 1, 2, 300 and a
   derived flag; nothing yet says what they select.
7. **No IR capture exists.** Everything above is inference from binaries and
   from this unit's own vendor calibration. The first real 4-channel capture
   is the thing that turns all of it into knowledge, and making one requires
   §5 in full.
8. `docs/64`'s attribution of Digital ICE to `AnsAreaCapability` should be
   corrected there; §1 has the evidence.
