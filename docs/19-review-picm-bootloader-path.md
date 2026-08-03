# 19 — Independent review: colour pipeline verified, tool bugs, and the PICM bootloader path decoded from TLB.dll

An adversarial review of this port against the vendor binaries in
`/Users/guy/Downloads/Pakon Update 2/`. Everything below was re-derived from
the binaries and data files, not from this repo's own docs. Addresses are
image-base virtual addresses as radare2 loads each DLL (`r2 <dll>`).

Three headline results:

1. The colour pipeline maths in `tools/pakon_color.py` is **correct**,
   independently re-verified numerically and against the real MMX kernel —
   which lives in **PakonIMAu.dll**, not TLA.dll (doc bug only).
2. The four reviewed tools contain one recurring real bug — **Type 7 status
   bytes are never checked**, so NAKed writes print as `ok` — plus one wrong
   packet form in `init_ccd.py` (reg 0x89 written as a word; vendor writes a
   byte).
3. The "board 0x44 is absent, recovery is electrical-only" conclusion in
   doc 18 is **premature**. TLB.dll itself contains a complete software
   recovery path for a motor PIC whose application is dead: `FN_bUpdate`
   proceeds to flash `NMxxyy.HEX` through the **bootloader at 0x46** exactly
   when the app address 0x44 is silent. The doc-18 retraction's evidence does
   not distinguish "bootloader" from "floating bus"; a decisive control
   experiment is specified below.

---

## 1. Colour pipeline — verification results

### 1.1 Density LUT: exact match

Computed independently against
`Config/ColorCorrection/_ClientColNegLut.txt` (16384 entries, index column
monotonic 0..16383):

```
LUT[i] = -3500 * log10(i / 16383),  LUT[0] = 16383.0
worst |vendor - formula| = 4.99977e-05  at i = 6664
after rounding the formula to the file's 4 decimals: worst = 0.0 (all 16384)
S = 3499 or 3501     -> worst jumps to ~4.2   (S is exactly 3500)
divisor 16384        -> worst 0.0928          (divisor is exactly 16383)
```

The residual 5e-05 is purely the file's 4-decimal printing. The claim in
`pakon_color.py` ("worst deviation 0.000050") is confirmed.

Generator confirmed in **TLA.dll at 0x10013730** (this address in the
docstring is correct):

- `0x10013762`: `imul eax, [esi+0x30], 0x3fff` → `LUT[0] = m * 16383`
- `0x1001377e`: `fmul qword [0x100665f0]` — the double at 0x100665f0 is
  exactly 1/16383
- `fldlg2; fyl2x` → `log10(i/16383)`; multiplied by `-([esi+0x20]*[esi+0x30])`
  (= −3500 when scale=3500, m=1); stored int32 via `_ftol` (0x10051644).
  Note the **runtime LUT is integer**; the shipped .txt has 4 decimals.

### 1.2 The MMX kernel is in PakonIMAu.dll, not TLA.dll

`pakon_color.py`'s docstring cites "TLA.dll:0x1001c563". TLA.dll contains
**zero** `pmulhw`/`paddsw` instructions; its 0x1001c563 is inside the
FN-name logging switch. The kernel is at **PakonIMAu.dll:0x1001c563** — the
offset is right, the module name is wrong. Fix the comment.

Kernel verified instruction by instruction (PakonIMAu.dll):

```
0x1001c57e  and eax, 0x3fff            ; 14-bit mask on raw value
0x1001c583  mov eax, [esi + eax*4]     ; LUT lookup (32-bit entries)
...4 pixels x 3 channels deinterleaved...
0x1001c684  pmulhw  mm4, mm1           ; (coeff * lutval) >> 16, per row
0x1001c68d  paddsw  mm3, mm4           ; sum the 3 channel products
0x1001c697  paddsw  mm3, [edx+0x60]    ; + offset row (post-multiply domain)
0x1001c69f  paddw   mm3, mm7           ; + 0x8000 (wrap bias, mm7 = 0x8000 x4)
0x1001c6a2  paddusw mm3, mm6           ; mm6 = 0x7003 x4 (saturating)
0x1001c6a5  psubusw mm3, [edx+0x58]    ; 0xF003 x4 (saturating)
```

The 0x8000/0x7003/0xF003 vectors are built in the prologue at
0x1001c50e–0x1001c531 into the parameter block at +0x48/+0x50/+0x58. Net
effect of the last three instructions on the signed post-offset value v:
clamp to **0..4092** (0xFFFF − 0xF003 = 0xFFC). Confirms:

- LUT strictly **before** the matrix ✔
- 3×3 multiply via `pmulhw` (>>16) then offset added **after** the multiply ✔
- 12-bit output, clamp 0..4092 ✔ (the docstring omits the `paddw 0x8000`
  bias but the arithmetic in `render_pixel` is equivalent)
- matrix rows at param +0x00/08/10 (row 0), +0x18/20/28 (row 1),
  +0x30/38/40 (row 2); offsets at +0x60/68/70.

### 1.3 What is consistent but NOT directly proven

- **coeff scale 8192**: `pmulhw` is >>16, so `out = coeff*d/8` holds iff
  int16 coeffs are `round(coeff * 8192)`. The only 8192.0 constant found in
  PakonIMAu.dll (0x1058f1b8) is used by the **unsharp-mask** kernel builder
  (0x10164461, with `+0.5; ftol` rounding — same rounding as
  `quantise_matrix()`). The colour-matrix block builder was not located, so
  8192 for the colour matrix is inference (it is the only power of two that
  fits near-unity coeffs in int16 with headroom and lands the LUT range in
  12 bits), not disassembly fact.
- **offset column domain**: the kernel adds the offset in the post-/8
  output domain, which is what `render_pixel` does. Whether the vendor loads
  `_ClientColNegMat.txt` column 3 into that slot verbatim (as
  `pakon_color.py` assumes) was not confirmed. Note the module docstring's
  phrase "in density code values" contradicts its own code if taken to mean
  the 14-bit LUT domain — in that case column 3 would need /8 as well.
  The values (−82.6/−586.9/−707.8) are plausible either way; flagged.
- **rounding**: hardware truncates each product (`pmulhw`, per-channel)
  before summing and uses an integer LUT; Python sums exact float products
  and truncates once. Expect occasional ±1–2 LSB differences from a
  bit-exact vendor render. Irrelevant visually; document it.

`write_tiff()` was checked field by field (IFD offsets 122/128, SHORT
packing, BitsPerSample array) — correct.

---

## 2. Tool bugs found (file:line)

### 2.1 The status-byte bug — again, in current tools

Established elsewhere in this project: a Type 7 response carries
STATUS at byte 3 (0 = accepted, 1 = NAK, 2 = unsupported). The vendor's own
presence check (below) requires `resp[0]==7 && resp[3]==0`.

- **tools/init_ccd.py:102–105 (`put`) and 122–127 (`put_word`)** — any
  response at all prints `ok`. Against the currently-NAKing board 0x44,
  every single write in the "geometry / CCD config / A/D config / control
  word" sequence prints `ok` while being rejected (`07 02 44 01`). The
  script's verdict logic then reasons about a bring-up that never happened.
  Same class of bug that already cost a day. `put()`/`put_word()` must check
  `r[0] == 7 and r[3] == 0` (and length ≥ 4) before claiming success.
- **tools/start_acquire.py:76–79 (`put_ccd`)** — returns the raw response;
  no caller checks status. `gain_sweep()` (118–136) silently tolerates
  NAKs; main() prints the response hex once (line 160) but proceeds
  regardless. Same fix needed.
- **tools/init_ccd.py:130–136 / start_acquire.py:82–87 (`clear_fault`)** —
  reads flags byte of the reply to `01 03 10 02 03` without verifying the
  reply type byte. Minor, but a Type 7 NAK would be misread as flags.

### 2.2 init_ccd.py sends the wrong packet form for reg 0x89

Verified in TLB.dll `FN_bDrvInitCcd` (fcn.1002d5c0, logger enum 341/0x155):

```
0x1002d61a  push 0x87 ... call 0x10009d40   ; PutRegisterWord(reg 0x87, 0x0000)
                                            ; -> 02 05 40 02 87 00 00
0x1002d67d  call 0x1002c5f0                 ; LampOn(0xffd)
0x1002d6a9  call 0x1000c4d0                 ; LampOff
0x1002d6c8  push 0x89 ... call 0x10009ba0   ; PutRegisterBYTE(reg 0x89, 0x00)
                                            ; -> 02 04 40 01 89 00
```

- `init_ccd.py:216` sends `put_word(d, LIGHT, 0x89, 0)` =
  `02 05 40 02 89 00 00` — **word write; the vendor writes one byte**
  (`02 04 40 01 89 00`). The 0x87 write at :215 is correct.
- Also note the vendor interleaves **LampOn(0xffd) / LampOff between the
  0x87 and 0x89 writes**; the docstring lists this but the code skips it.
  If InitCcd order matters (likely — it is an AFE/lamp settling sequence),
  the port should reproduce it.

Byte order (lo, hi), the PutRegisterCcd form `02 06 44 03 <reg> <idx> <lo>
<hi>`, and the geometry constants (2000, 62, 0xffd) all check out against
fcn.10009bf0 / fcn.1002d5c0.

### 2.3 pakon_load.py — one latent boundary bug, rest sound

- **tools/pakon_load.py:129–134**: records are re-chunked from *merged
  segments* (`HexImage.segments()` coalesces adjacent hex records), so a
  16-byte chunk can straddle `MAX_INTERNAL_ADDRESS` 0x1B3F (start ≤ 0x1B3F,
  end > 0x1B3F). Such a chunk is classified internal and sent whole via
  0xA0 with the CPU held. Harmless on FX2 (0xA0 reaches 0x0000–0x3FFF; the
  F-135 Plus is FX2), but on a genuine AN2131 unit the bytes above 0x1B3F
  would be lost, and they are also excluded from pass 1. Fix: split any
  chunk crossing 0x1B3F, or chunk external/internal ranges separately.
- The identity handling is correct and vendor-confirmed: unloaded
  `0f05:F235 rev AA05/07/08` → WDGTLDR → `Pakon5/7/8.hex`, and loaded PIDs
  `35F2` (F-235), `F135`, `F335` all match `F235usb2.inf` /
  `vendor/FX35/FX35Package/F135.inf`. The refusal to fall back to
  PknInit.hex and the post-load PID sanity check are right.
- `reset_8051()` writing both CPUCS addresses (0x7F92 then 0xE600) is
  fxload-style and safe on FX2; note only.

### 2.4 eeprom_repair.py — sound, two notes

- Writes 9 bytes but `read_personality()` verifies only the first 8 (0xA9
  returns 8); the final `0x02` is unverifiable via this path. Disclose in
  the output rather than claiming full verification.
- The read-stability gate (4 identical reads required) and
  read-before-write ordering are good. The 0xA2 write path is empirically
  validated (this unit now enumerates 0f05:f235/aa07 → f135).

---

## 3. New: the board bring-up protocol decoded from TLB.dll

All of this is new decoding, verified in disassembly. It supersedes parts of
doc 18.

### 3.1 Packet helper functions (TLB.dll)

| fcn | form on the wire | meaning |
|-----|------------------|---------|
| fcn.10009ae0 | `02 <len> <board> <n> <reg> <data…>`, len = n+3 | generic register write |
| fcn.10009ba0 | `02 04 <board> 01 <reg> <val>` | write byte (log enum 0x7f) |
| fcn.10009d40 | `02 05 <board> 02 <reg> <lo> <hi>` | write word, little-endian (enum 0x81) |
| fcn.10009bf0 | `02 06 <board> 03 82 00 <lo> <hi>` | CCD control word (reg 0x82 idx 0) |
| fcn.10009a40 | `04 03 <board> 00 <cmd>` | Type 4 command (enum 0x7b) |
| fcn.1000a0c0 | read register → word | e.g. board 0x10 reg 3 = interface version |
| fcn.10008ba0 | `04 03 <board> 00 00`, 2 tries | **FN_bDrvFindPicController** (enum 0x5c): present iff `resp[0]==7 && resp[3]==0` |

The presence probe used throughout this project is byte-identical to the
vendor's. Status 1 means "the interface board got no I2C ACK at that
address" — the interface board itself synthesises the `07 02 <addr> 01`
reply.

### 3.2 Board addresses: constructor defaults and the two families

Driver-object constructor at 0x1000af20:

```
0x1000af7a  word  [esi+0x68]  = 0x10    ; host/interface board
0x1000af87  byte  [esi+0x130] = 0x44    ; motor/main PIC (PICM), app address
0x1000af8e  byte  [esi+0x131] = 0x40    ; light PIC (PICL), app address
```

Probe orchestrator fcn.1000afd0 cycles **0x44 → 0x46 → 0x24 → 0x26** via
FindPicController. If 0x24/0x26 answers it rewrites `+0x130 = 0x24`,
`+0x131 = 0x20` (0x1000b093) — the older F-135 hardware family. So:

| family | motor app | motor boot | light app | light boot | firmware prefix |
|--------|-----------|------------|-----------|------------|-----------------|
| F-135 Plus/Hybrid | 0x44 | **0x46** | 0x40 | 0x42 | NM (motor), NL (light) |
| F-135 classic | 0x24 | 0x26 | 0x20 | 0x22 | PM (motor), PL (light) |

The bootloader address is app+2 — hardcoded in FN_bUpdate (0x1001c6d5:
`0x46` for the NM path; 0x1001c6fe: `0x26`; 0x1001c776: `0x42`;
0x1001c78c: `0x22`). This unit's light board answers at 0x40, so it is the
0x44 family; there is **no** alternative addressing convention under which a
healthy F-135 Plus main board sits anywhere but 0x44 (app) / 0x46 (boot).

### 3.3 FN_bInit2 (fcn.1000b100, enum 0xd6) — the bring-up order

```
1. fcn.10009a40(board 0x10, cmd 0x85)          ; same "clear fault" cmd the tools use
2. optional: write board 0x10 reg 0x8f = 1     ; power-enable for an aux board
   Sleep(100ms); FindPicController(0x28)       ; probe aux board at 0x28
   (reg 0x8f = 0 powers it off)
3. fcn.1000afd0                                ; motor address cycle 44/46/24/26
4. read board 0x10 reg 3 (word)                ; interface board version
5. FN_bUpdate(motor board)                     ; see 3.4
6. FN_bUpdate(light board = [+0x131])
```

There is **no** hidden power/reset/enable packet for the motor board before
its probe. The only power-gating discovered is board 0x10 reg 0x8f, and it
gates the board at 0x28 (aux — DX/feeder family), not 0x44. A healthy main
board needs nothing before answering `04 03 44 00 00`.

### 3.4 FN_bUpdate (fcn.1001c3e0, enum 0x13d) — PIC firmware check/flash

```
1. FindPicController(app addr)                  ; 0x1001c481
   - if PRESENT (first time): write reg 0x97 = 1 (one byte) to the app addr
     (0x1001c4ca via fcn.10009ba0)              ; enter-bootloader command
   - if ABSENT: CONTINUES ANYWAY                ; <-- the recovery path
2. Select image: FindFirstFile on
   Config\Firmware\{NM|PM|NL|PL}{hw:02x}??.hex  ; 0x1001c7ce
   scan for highest firmware rev yy; skip flash if board fw >= file fw
3. fcn.1001c150: read the hex file (64 KB buffer)
4. fcn.1001b810: parse hex lines into 0x4000-byte flash image(s)
5. fcn.1001b9b0 = FN_bPicToBootLoaderState (enum 0xf5)
6. fcn.1001bb10 = FN_bLoadPicLarge       (enum 0xee)  ; download via app+2
7. wait 3000 ms (0x1001caf9), re-probe, FN_bDrvGetDevInfo
```

`FN_bDrvGetDevInfo` (fcn.1000a370, enum 0x5e) is **not** a USB-descriptor
read: it writes register 3 = 1 to the board (`02 04 <board> 01 03 01`) and
then reads a 12-byte info block; bytes [1] and [2] are the version pair used
for the filename match. `[esi+0x130]` is populated by the constructor and
the 0x1000afd0 probe, not by GetDevInfo (doc correction).

Hardware revision mapping (ReadmeF135.txt): NM03=PCB 125430A,
NM04=125430B, NM05=125430C; `nm0506.HEX` is the newest for PCB #125430C.
**Read the PCB number off the board before flashing.**

Danger note for register-sweep hygiene: **writing 1 to register 0x97 on a
live PIC is the enter-bootloader command.** A blind write sweep over a live
board 0x44 would knock it off its app address by design; garbage written to
the bootloader at 0x46 afterwards could corrupt application flash. This is a
plausible mechanism for the current fault, given this unit's EEPROM was
damaged by exactly such a sweep.

---

## 4. Re-assessment of the "board 0x44 is absent" diagnosis

What is solid: the probe method is the vendor's own; status 1 at 0x44 means
no I2C ACK there; the light board works; no enable sequence is missing.

What is *not* solid is doc 18's retraction of the bootloader hypothesis.
Its evidence — 0x46/0x47 answering all 80 probed registers with unstable
values, unlike the light board's 16 stable ones — assumed a bootloader
would present a register file. It does not. The register protocol is an
*application* protocol; a PIC bootloader speaks its own raw format
(`FN_bLoadPicLarge`'s, not yet decoded), so register reads against it
*should* return protocol garbage. "Unstable register reads" is what both a
floating bus **and** a bootloader look like through register-shaped probes.
Meanwhile the ping result (`status 0` at 0x46) is the vendor's own presence
criterion, and TLB.dll's FN_bUpdate treats "app silent at 0x44" as a normal,
recoverable state that it fixes by flashing through 0x46.

### 4.1 The decisive experiment (10 minutes, read-only)

Ping, with the exact FindPicController form `04 03 <addr> 00 00`, checking
`resp[0]==7 && resp[3]==0`:

```
0x44  (expected: status 1 — known)
0x46  (the question)
0x24, 0x26 (completeness; expected status 1)
CONTROLS — addresses where nothing can exist:
0x48, 0x4a, 0x60, 0x62  (expected status 1 if the bus/firmware is honest)
```

- If the **controls NAK (status 1) but 0x46 ACKs (status 0)**: something
  real ACKs at 0x46, and per the vendor binaries the only thing ever at
  0x46 is the PICM bootloader → the board is alive and software-recoverable.
  Next step: decode FN_bLoadPicLarge (fcn.1001bb10) + FN_bPicToBootLoaderState
  (fcn.1001b9b0) in TLB.dll — or the same functions in FirmwareLoaderCom.dll
  (enum table at fcn.10006270; FN_bLoadPicLarge=39, FN_bPicToBootLoaderState=44,
  fcn.1000e2e0) — and port the flash of `nm0506.HEX` (PCB rev permitting).
  Until that protocol is fully understood, **send nothing but the ping to
  0x46**; unknown bytes to a bootloader can erase flash.
- If the **controls also "ACK"** or return junk data: the interface board's
  NAK reporting is untrustworthy at those addresses, doc 18's retraction
  stands, and the fault is electrical → measure the PICM rails (the BIST
  names enumerate them: Vin, 13V, 12V, 6V, 5V, 3V).

### 4.2 If it is the bootloader: port order

1. Decode FN_bLoadPicLarge's wire format (fcn.1001bb10; its caller passes
   the parsed 0x4000-byte image, the bootloader address, and the byte at
   FN_bUpdate's `[esp+0x24]` slot). Cross-check against FirmwareLoaderCom.dll's
   implementation — two independent implementations ship in the vendor tree.
2. Implement hex parse (fcn.1001b810 semantics — note `%*c%*c%*02x%02x`
   filename scan and the 0x2004-byte line buffer).
3. Flash NM image matching the PCB revision; wait 3 s; re-probe 0x44;
   GetDevInfo must return the new version.

---

## 5. Current port state (for the next agent)

Working, vendor-verified:
- USB enumeration, EEPROM personality repaired (`c0 05 0f 35 f2 07 aa 04 02`),
  two-stage firmware load (pakon_load.py), light board fully alive,
  colour-negative rendering maths (this doc, §1).

Blocked on: motor/main board at 0x44 (motor, CCD A/D 0x84, FPGA 0x82).
Next action: §4.1 control experiment, then either bootloader port (§4.2) or
rail measurements.

Fix before further hardware debugging (they corrupt conclusions):
- status-byte checking in init_ccd.py / start_acquire.py (§2.1)
- reg 0x89 packet form in init_ccd.py (§2.2)
- LampOn/LampOff steps missing from init_ccd.py's InitCcd port (§2.2)
- pakon_color.py docstring: kernel is PakonIMAu.dll:0x1001c563 (§1.2)
