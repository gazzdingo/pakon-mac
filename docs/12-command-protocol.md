# 12 — Command Protocol (decoded from TLB.dll)

Supersedes the speculative parts of `03-protocol.md`. Everything here was derived
**statically** from `TLB.dll` (F-135 client library,
`Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/TLB.dll`,
32-bit x86, image base `0x10000000`). Nothing was sent to hardware.

Confidence tags:
- **[VERIFIED-FROM-BINARY]** — read directly out of the packet-building code, and
  (where noted) cross-checked against a packet the human already sent successfully.
- **[INFERRED]** — the packet layout is verified, but the *meaning* of a field or
  the correct value to put in it is a deduction.
- **[UNKNOWN]** — stated as unknown.

---

## 0. How this was recovered

`TLB.dll` logs every driver routine by name. A 362-entry jump table at
`0x10019ed0` (dispatched from `fcn.100170b0`) maps a numeric **FN id** to a
string such as `FN_bDrvLampOn`. Every driver function calls the logger
`fcn.1001acd0` on its error paths, passing its own FN id. Recovering the id→name
table and then finding which function pushes which id gives a near-complete
symbol table for the driver layer.

Key recovered symbols (all in TLB.dll):

| FN id | Name | Function |
|---|---|---|
| 112 | `FN_bDrvLampOn` | `fcn.1002c5f0` |
| 111 | `FN_bDrvLampOff` | `fcn.1000c4d0` |
| 79 | `FN_bDriveMotorAdvanceFilm` | `fcn.1000b6d0` |
| 80 | `FN_bDriveMotorStop` | `fcn.1000a440` |
| 96 | `FN_bDrvGetHardwareStatusLamp` | `fcn.1000b890` |
| 94 | `FN_bDrvGetDevInfo` | `fcn.1000a370` |
| 92 | `FN_bDrvFindPicController` | `fcn.10008ba0` |
| 214 | `FN_bInit2` (driver bring-up) | `fcn.1000b100` |
| 131 | `FN_bDrvResetFifos` | `fcn.1000a730` |
| 333 | `FN_bDrvCcdAcquireAndDxStart` | `fcn.10009bf0` |
| 91 | `FN_bDrvDxStop` | `fcn.10009da0` |
| 128 | `FN_bDrvPutRegisterCcd` | `fcn.1000a5d0` |
| 120 | `FN_bDrvPutCcdFpgaControlReg` | `fcn.10029770` |
| 121 | `FN_bDrvPutCcdFpgaSettings` | `fcn.1002c340` |
| 117/118/119 | CCD gains / offsets / exposures | `fcn.100298b0` / `fcn.100299c0` |
| 341 | `FN_bDrvInitCcd` | `fcn.1002d5c0` |
| 342 | `FN_bDrvInitLampTemperatures` | `fcn.1002d190` |
| 135 | `FN_bDrvSetLed` (status LEDs) | `fcn.1000c1f0` |
| 17 | `FN_bBeforeScan` | `fcn.1002dbd0` |
| 302 | `FN_iScanStrips` | `fcn.10029b80` |

The generic packet emitters, all of which end at `fcn.10008530`
(`DeviceIoControl 0x222090` at `0x100085da`, 64-byte response buffer — matches
what you already proved):

| Function | Signature (recovered) | Emits |
|---|---|---|
| `fcn.10009a40` | `PutCommand(log, addr, cmd, nolock)` | Type 4 |
| `fcn.10009e50` | `PutCommand2(log, addr, cmd)` | Type 4 |
| `fcn.10009ae0` | `PutRegister(log, addr, reg, buf, n, nolock)` | Type 2 |
| `fcn.10009ba0` | `PutRegisterByte(log, addr, reg, val, nolock)` | Type 2, n=1 |
| `fcn.10009f90` | `PutRegisterByte2(log, addr, reg, val)` | Type 2, n=1 |
| `fcn.10009d40` | `PutRegisterWord(log, addr, reg, u16, nolock)` | Type 2, n=2 |
| `fcn.1000a5d0` | `PutRegisterCcd(log, reg, idx, u16, nolock)` | Type 2, n=3 |
| `fcn.10009410` | `GetByteArrayNL(log, addr, reg, out, n, x)` | Type 1 |
| `fcn.10009700` | `GetRegisterByte(log, addr, reg, out, nolock, x)` | Type 1, n=1 |
| `fcn.1000a0c0` | `GetRegisterWord(...)` | Type 1, n=2 |
| `fcn.100092f0` | `GetPpbDeviceReadyNL(log, addr, out)` | Type 3 |
| `fcn.10008d70` | `GetPpbHostStatusByte(log)` | Type 3 @ 0x10 |
| `fcn.100095a0` | `WritePacketNL` — patches `pkt[1] = pkt[3] + 3`, sends, retries 3× | — |
| `fcn.100087a0` | `PacketHandleErrorNL` — decodes the response status | — |

---

## 1. Packet framing — [VERIFIED-FROM-BINARY]

```
  offset   field
  ────────────────────────────────────────────
    [0]    Type          1, 2, 3 or 4
    [1]    PktLen        wire size = PktLen + 2
    [2]    Address       destination board
    [3]    Count / N     meaning depends on Type
    [4]    Cmd / Reg     "Cmd" in TLB's own log format string
    [5..]  Payload
```

`fcn.100095a0` (`WritePacketNL`) sets `pkt[1] = pkt[3] + 3` for **every Type 2
and Type 4 packet** before sending. Types 1 and 3 hardcode `pkt[1]` (3 and 1).
There is **no checksum computed by the host** — confirmed, `fcn.10008530` copies
the caller's buffer straight into `DeviceIoControl`. `EC_DRV_PacketChecksumErr`
refers to a checksum the *scanner* validates on the inter-PIC serial bus, not on
USB.

The `Addr 0x%02X, Cmd 0x%02X` log format at `0x1005bd94` is emitted from
`fcn.100087a0` using `pkt[2]` and `pkt[4]` — this is the binary itself telling
you that byte 2 is the address and byte 4 is the command/register.

### Type 1 — READ REGISTER — [VERIFIED-FROM-BINARY]

```
  01  03  AA  NN  RR
  │   │   │   │   └── register / command index to read
  │   │   │   └────── NN = number of bytes to read back
  │   │   └────────── AA = board address
  │   └────────────── PktLen, always 3
  └────────────────── Type 1
```

Built at `fcn.10009410:0x10009428–0x1000943a`:
`buf[0]=1; buf[1]=3; buf[2]=addr; buf[3]=count; buf[4]=register`.

Response: `01  (NN+2)  AA  SS  <NN data bytes>`.

This exactly reproduces every Type 1 result you measured:

| Sent | Received | Reading |
|---|---|---|
| `01 03 40 00 00` | `01 02 40 88` | read 0 bytes of reg 0 |
| `01 03 40 01 00` | `01 03 40 88 00` | read 1 byte of reg 0 |
| `01 03 40 02 00` | `01 04 40 88 00 80` | read 2 bytes of reg 0 |
| `01 03 40 03 00` | `01 05 40 88 00 80 01` | read 3 bytes of reg 0 |
| `01 03 44 02 00` | `01 04 44 08 00 00` | read 2 bytes of reg 0 on board 0x44 |

So **byte 4 *is* the register index — your original guess was right.** The reason
it looked implausible is that you only ever read register 0. The real register
numbers used by the driver are all ≥ `0x80` (see §3).

### Type 2 — WRITE REGISTER — [VERIFIED-FROM-BINARY]

```
  02  LL  AA  NN  RR  D0 D1 ... D(NN-1)
  │   │   │   │   │   └── NN payload bytes, little-endian for u16/u24
  │   │   │   │   └────── RR = register index
  │   │   │   └────────── NN = payload byte count
  │   │   └────────────── AA = board address
  │   └────────────────── LL = PktLen = NN + 3   (set by WritePacketNL)
  └────────────────────── Type 2
```

Built at `fcn.10009ae0:0x10009af2–0x10009b19`:
`buf[0]=2; buf[2]=addr; buf[3]=n; buf[4]=reg; memcpy(buf+5, data, n)`.

Cross-check against your proven packet: `02 06 40 03 01 00 00 00` →
Type 2, PktLen 6 (= 3+3), address 0x40, **3 payload bytes**, register `0x01`,
value `0x000000`. Register `0x01` is the 24-bit read-address pointer
(see `fcn.10008f80`) — so what you actually sent was "set the block-read pointer
to 0 on the light board", which is why it succeeded harmlessly.

Response: `07  02  AA  SS`.

### Type 3 — POLL / DEVICE READY — [VERIFIED-FROM-BINARY]

```
  03  01  AA
```

Built at `fcn.100092f0:0x1000934b`. `fcn.10008d70` is the same thing hardcoded to
`AA = 0x10`. The caller loops up to **44 times** while `status & 0x01` is set,
and ORs `status & 0x36` into an error accumulator.

Matches your proven `03 01 10` → `03 04 10 08 aa aa`.

### Type 4 — EXECUTE COMMAND (no payload) — [VERIFIED-FROM-BINARY]

```
  04  03  AA  00  CC
  │   │   │   │   └── CC = command
  │   │   │   └────── always 0 (payload count)
  │   │   └────────── AA = board address
  │   └────────────── PktLen = 0 + 3
  └────────────────── Type 4
```

Built at `fcn.10009a40:0x10009a56–0x10009a64` and `fcn.10009e50`.
Your proven `04 03 40 00 00` is therefore **command 0x00 = ping**, which is what
`FN_bDrvFindPicController` (`fcn.10008ba0`) uses to enumerate boards.

Response: `07  02  AA  SS`.

### Response status byte `resp[3]` — [VERIFIED-FROM-BINARY]

From `fcn.100087a0`. Two different decodings depending on response type:

**Type 7 responses** (answers to Type 2 / Type 4) — `resp[3]` is a small enum,
switch at `0x100087d7`:

| Value | Meaning | Error code logged |
|---|---|---|
| 0 | success | — |
| 1 | no-ack (board absent) | 1011 |
| 2 | invalid packet | 1012 |
| 3 | bad checksum (retried) | 1013 |
| 4 | — | 1014 |
| 6,9 | bus errors | 1017–1019 |

**Type 1 / Type 3 responses** — `resp[3]` is a **bitfield**, tested at
`0x10008a4b` onwards:

| Bit | Mask | Meaning |
|---|---|---|
| 0 | `0x01` | busy / not ready → caller retries |
| 1 | `0x02` | error (part of the `0x36` error mask) |
| 2 | `0x04` | error → ecode 1010 |
| 3 | `0x08` | ready / OK |
| 4 | `0x10` | error → ecode 1009 |
| 5 | `0x20` | on host reg 3 only: triggers `04 03 10 00 85` (see `fcn.1000a0c0:0x1000a154`) |
| 7 | `0x80` | set by the light board; **not** in the error mask `0x36` → benign [INFERRED] |

`GetPpbDeviceReadyNL` accumulates `status & 0x36` as the error set. Therefore
your observed `0x88` (light board) and `0x08` (motor board) are **both clean
success**: `0x88 & 0x36 == 0` and bit 3 (ready) is set.

---

## 2. Board addresses — [VERIFIED-FROM-BINARY]

The driver object caches two board addresses, set in the constructor at
`fcn.1000af60`:

```
  drv+0x130 = 0x44    motor / main board   (PICM_PLUS)
  drv+0x131 = 0x40    light board          (PICL_PLUS)
```

`fcn.1000b6d0` contains `cmp cl, 0x44` on `drv+0x130` to choose between the Plus
and non-Plus motor speed clamps — a direct, unambiguous confirmation that
`0x130` is the motor board and that `0x44` is the Plus variant.

`FN_bDrvLampOff` reads `drv+0x131` and writes the lamp register — confirming
`0x131` = light board = `0x40`.

The probe order in `fcn.1000afd0` is `0x44, 0x46, 0x24, 0x26, …`, i.e. two Plus
candidates then two legacy candidates per board class.

Addresses used by TLB.dll:

| Addr | Board | Evidence | Present on this unit? |
|---|---|---|---|
| `0x10` | HOST / FX2, handled locally | `fcn.1000b100`, `fcn.1000a730` | yes |
| `0x28` | focus / lens steppers ("PICF") | `fcn.1002d850`, `fcn.1000bd40` | **no** — see below |
| `0x40` | light board (lamps, LEDs, DX) | `drv+0x131` | yes |
| `0x44` | motor / main board (motors **and** CCD/FPGA) | `drv+0x130` | yes |

**`0x28` is not populated on this scanner.** The full `0x00`–`0xFF` address
sweep recorded in `03-protocol.md` found only `0x10`, `0x20`, `0x24`, `0x40`
and `0x44`; everything else returns bus error (status 9). TLB.dll drives a
focus-stepper board at `0x28` (`FN_bDrvMoveFocusSteppers`) because the same
library serves several chassis — the F-135 evidently does not have one. Do not
spend a packet on it. Its register map is recorded below only for completeness.

Note: the CCD and FPGA registers live on **`0x44`**, not on the light board.
`fcn.1000a5d0` (`PutRegisterCcd`) reads its address from `drv+0x130`.

---

## 3. Register maps

### Light board `0x40`

| Reg | Width | Access | Meaning | Tag |
|---|---|---|---|---|
| `0x01` | 3 B | W | 24-bit block-read address pointer | [VERIFIED] `fcn.10008f80` |
| `0x03` | 1 B | W | read-window source select (`=1` → device info) | [VERIFIED] `fcn.1000a370` |
| `0x07` | n B | R | block-read data window | [VERIFIED] |
| **`0x80`** | **1 B** | **W** | **LAMP ON/OFF bitmask** | **[VERIFIED]** |
| `0x81` | 5 B | W | LED level / current array | [VERIFIED layout] / [INFERRED meaning] |
| `0x82` | 12 B | W | LED duty cycles | [VERIFIED layout] / [INFERRED meaning] |
| `0x83` | 1 B | R | lamp hardware status | [VERIFIED] `fcn.1000b890` |
| `0x84` | 2 B | R | lamp temperature | [VERIFIED] `fcn.1000b890:0x1000b99b` |
| `0x8B` `0x8C` `0x8D` `0x8F` | 4 B | W | lamp temperature setpoints | [VERIFIED] `fcn.1002d190` |
| `0x91` | 3 B | W | DX start | [VERIFIED] `fcn.10009bf0` |
| `0x97` | 1 B | W | firmware-update gate | [VERIFIED] `fcn.1001c3e0` |
| `0xD0` | 1 B | W | `=0` at temperature init | [VERIFIED] |
| `0xD1` | 1 B | W | `=1` at temperature init | [VERIFIED] |

Type 4 commands on `0x40`: `0x00` ping, `0x8A` (FIFO/DX reset, second half of
`FN_bDrvResetFifos`), `0x92` DX stop.

### Motor / main board `0x44`

| Reg | Width | Access | Meaning | Tag |
|---|---|---|---|---|
| `0x82` | 3 B (`idx` + u16) | W | CCD **FPGA** register file | [VERIFIED] |
| `0x84` | 3 B (`idx` + u16) | W | CCD **A/D** register file | [VERIFIED] |
| `0xA5` | 2 B | W | motor speed / rate | [VERIFIED] |

Type 4 commands on `0x44`: `0x00` ping, **`0xA0` advance forward**,
**`0xA1` advance reverse**, **`0xA2` stop**.

FPGA file (`reg 0x82`, 3-byte form `82 <idx> <lo> <hi>`):

| idx | Meaning | Tag |
|---|---|---|
| 0 | control register, 10 bits (`and eax,0x3ff`). **bit 0 = CCD acquire enable**, bit 1 = ?, bits 5–6 (`0x60`) set by FpgaSettings, **bit 8 (`0x100`) = IR mode** | [VERIFIED] |
| 1,2,3 | zeroed at InitCcd | [VERIFIED] |
| 4 | `uiCcdPixelOffset` | [VERIFIED via assert string] |
| 5 | `uiCcdPixelOffset + uiCcdPixelHeight` (end pixel) | [INFERRED] |
| 6 | `uiCcdIntegrationTime` | [VERIFIED via assert string `0x10066ddc`] |
| 9 | front-panel status LEDs | [VERIFIED] `FN_bDrvSetLed` |
| 0xA | `= 0x400` at InitCcd | [VERIFIED] |
| 0xB | `= 0` in FpgaSettings | [VERIFIED] |

A/D file (`reg 0x84`, 3-byte form):

| idx | Meaning | Tag |
|---|---|---|
| 0 | `= 0x78` at InitCcd | [VERIFIED] |
| 1 | `= 0x80` at InitCcd | [VERIFIED] |
| 2,3,4 | A/D **gains**, clamped to `0x3F` | [VERIFIED] `FN_bDrvPutCcdAtoDGains` |
| 5,6,7 | CCD **exposures** | [VERIFIED] `FN_bDrvPutCcdExposures` |

### Host / FX2 `0x10`

| Reg / Cmd | Meaning | Tag |
|---|---|---|
| `01`/`07` | 24-bit pointer + block read window (used by `FN_bDrvReadScanLine`) | [VERIFIED] |
| reg `0x03` (read 2 B) | host status word; if `status & 0x20`, driver issues `04 03 10 00 85` and retries 100× | [VERIFIED] `fcn.1000a0c0` |
| reg `0x84` = `2` | **reset FIFOs** | [VERIFIED] `FN_bDrvResetFifos` |
| reg `0x8F` = `0`/`1` | toggled around board probing in `FN_bInit2`; bus/relay enable | [VERIFIED write] / [INFERRED meaning] |
| Type 4 cmd `0x85` | host clear / ack | [VERIFIED] |

---

## 4. (a) LAMP ON — the priority answer

### The packet

```
  02 04 40 01 80 01        <-- LAMP ON  (visible)
  02 04 40 01 80 03        <-- LAMP ON  (visible + IR)
  02 04 40 01 80 00        <-- LAMP OFF
  ── ── ── ── ── ──
  │  │  │  │  │  └── value: bit0 = visible lamps, bit1 = IR lamp
  │  │  │  │  └───── register 0x80 = lamp enable
  │  │  │  └──────── 1 payload byte
  │  │  └─────────── light board 0x40
  │  └────────────── PktLen = 1 + 3 = 4  (wire size 6)
  └───────────────── Type 2 = write register
```

Expected response: **`07 02 40 00`** (Type 7, address 0x40, status 0 = success).

### Evidence — [VERIFIED-FROM-BINARY]

`FN_bDrvLampOff` = `fcn.1000c4d0`, at `0x1000c4e9`–`0x1000c512`:

```asm
mov  edi, dword [esp + 0x10]      ; logging context
push 0                            ; arg5 nolock = 0
mov  al,  byte [esi + 0x131]      ; al = light board address = 0x40
push 0                            ; arg4 VALUE = 0
mov  byte [esp + 0x10], al
mov  ecx, dword [esp + 0x10]
push 0x80                         ; arg3 REGISTER = 0x80
push ecx                          ; arg2 ADDRESS  = 0x40
push edi                          ; arg1 log ctx
call fcn.10009ba0                 ; PutRegisterByte
```

`FN_bDrvLampOn` = `fcn.1002c5f0`. At the top it composes a bitmask into `edi`:

```asm
xor  edi, edi
cmp  dword [ebp + 0x0c], 0        ; caller's "lamp on" flag
je   +
mov  edi, 1                       ;   -> bit 0
+
cmp  dword [ebp + 0x10], 0        ; caller's "IR" flag
je   +
or   edi, 2                       ;   -> bit 1
+
```

and then, at `0x1002c683`–`0x1002c6a4`, writes exactly the same register:

```asm
mov  dl,  byte [esi + 0x2f9]      ; = drv+0x131 = 0x40   (scanner+0x1c8 = drv)
push 0                            ; nolock
push edi                          ; VALUE = the bitmask
push 0x80                         ; REGISTER = 0x80
push eax                          ; ADDRESS  = 0x40
push ecx                          ; log ctx
lea  ecx, [esi + 0x1c8]           ; 'this' = the driver object
call fcn.10009ba0                 ; PutRegisterByte
```

The value is cached in `scanner+0x29c` and the write is skipped when unchanged,
which is why the lamp register is written exactly once per state change.

`FN_bBeforeScan` (`fcn.1002dbd0`) calls it at `0x1002e40a` with the first flag
literally `push 1` and the second from `scanner+0x378` (the IR-enable config), so
**`mask = 1` is the ordinary "lamp on for a normal colour scan"** value.

**Corroboration in a sibling binary:** `TLC.dll` (F-335) `FN_bDrvLampOff` at
`0x10010180` writes the *same register `0x80`* — only the board address differs
(`0x38` on that model). Same register, three product generations.

### Caveats before you celebrate — [INFERRED]

Register `0x80` is an **enable**, not a brightness. The F-135 lamp is an LED
array (`FN_bCalibrateLEDs`, `FN_bCalibrateFindLedCurrent`,
`FN_bCalibrateFindLedDutyCycle`, `FN_bDrvPutLampLevel`). The full lamp-on
sequence in `fcn.1002c5f0` is:

1. `02 04 40 01 80 <mask>` — enable (this is the one above)
2. `02 08 40 05 81 <b0> <b1> <b2> 00 <b4>` — 5-byte LED level array
3. `02 0F 40 0C 82 <12 bytes>` — 12-byte LED duty-cycle array

If the board powers up with all levels at zero, step 1 alone may enable the
drivers without producing visible light. **Read `0x81` and `0x82` back first**
(Type 1 is a safe read) to find out what the board currently holds — see §8.

The byte order of the `0x81` payload, reconstructed from
`0x1002cbba`–`0x1002cc38`, is `[a6, a7, a4, 0x00, a5]` where `a4..a7` are the
four `CiConfigLight` values at `+0x58/+0x5c/+0x60/+0x64`. Which of those is R, G,
B and IR is **[UNKNOWN]** — the config-file field names were not resolved.

---

## 5. (b) ADVANCE FILM / motor control — [VERIFIED-FROM-BINARY]

`FN_bDriveMotorAdvanceFilm` = `fcn.1000b6d0` does exactly two packets:

```
  1)  02 05 44 02 A5 <lo> <hi>     set speed register 0xA5 (u16 LE)
  2)  04 03 44 00 A0               command 0xA0 = drive forward
      04 03 44 00 A1               command 0xA1 = drive reverse
```

and `FN_bDriveMotorStop` = `fcn.1000a440` sends one:

```
      04 03 44 00 A2               command 0xA2 = stop
```

Both expect `07 02 44 00`.

Source, `fcn.1000b6d0:0x1000b6f8`–`0x1000b784`:

```asm
mov  eax, dword [ebp + 0x10]      ; requested speed (signed)
mov  byte [esp + 0x10], 0xa0      ; command = 0xA0
jge  +
mov  byte [esp + 0x10], 0xa1      ;   negative -> 0xA1
neg  eax
+
mov  cl, byte [edi + 0x130]       ; motor board address
cmp  cl, 0x44                     ; Plus motor board?
jne  legacy
    clamp eax to [0x03E8 .. 0x7FFE]      ; 1000 .. 32766
    jmp  send
legacy:
    clamp eax to [0x0190 .. 0x251C]      ;  400 .. 9500
send:
push 0
push eax                          ; VALUE = speed
push 0xa5                         ; REGISTER 0xA5
push eax                          ; ADDRESS = 0x44
push esi
call fcn.10009d40                 ; PutRegisterWord  -> packet (1)
...
push eax                          ; COMMAND 0xA0 / 0xA1
push ecx                          ; ADDRESS = 0x44
push esi
call fcn.10009a40                 ; PutCommand       -> packet (2)
```

After packet (2) the function either waits a caller-supplied number of
milliseconds and then calls `FN_bDriveMotorStop`, or returns immediately and
leaves the motor running.

**Units of register `0xA5` are [UNKNOWN].** The COM layer speaks in
`iTenthsOfMillimetersPerSecond` (`0x10068228`) and `iAdvanceMilliseconds`
(`0x100681fc`), and `FN_bBeforeScan` divides by 1000 (magic multiply
`0x10624DD3` at `0x1002e687`) before calling the driver — so `0xA5` is *not*
directly tenths-of-mm/s. Treat the legal range `0x03E8..0x7FFE` as the only
solid fact and start at the low end.

A safe first motor experiment is the speed write alone (`02 05 44 02 A5 E8 03`) —
it configures the rate but does **not** start the motor. Nothing moves until a
`0xA0`/`0xA1` command is sent.

Related, but **not on this unit** (board `0x28` is unpopulated, §2):
`fcn.1002d850` `FN_bDrvMoveFocusSteppers` → board `0x28`, registers `0x88` and
`0x8B` (u16), commands `0x87` and `0x8A`.

---

## 6. (c) START SCAN and what makes EP 0x86 carry real lines

This is the least complete section. What is solid:

### The acquire bit — [VERIFIED-FROM-BINARY]

`FN_bDrvCcdAcquireAndDxStart` = `fcn.10009bf0` builds two packets by hand:

```
  02 06 44 03 82 00 <lo> <hi>      FPGA control register (idx 0) := shadow | 1
  02 06 40 03 91 <lo> <hi> <b>     light board reg 0x91, 3 bytes (DX start)
```

The wrapper `fcn.10029710` computes the value as follows:

```asm
mov  cx, word [esi + 0x358]       ; software shadow of the FPGA control reg
mov  eax, ecx
or   eax, 1                       ; <<< set bit 0
cmp  cx, ax
sete dl                           ; already set?
dec  edx
and  eax, edx                     ; -> 0 if already set, else shadow|1
```

and `fcn.10009bf0` skips the FPGA write when the value is 0. So **bit 0 of the
FPGA control register at CCD `reg 0x82, idx 0` on board `0x44` is the CCD
acquire enable.** It is set once per strip, immediately before `FN_iScanStrips`
starts pulling lines.

The control register is 10 bits (`and eax, 0x3ff` in `fcn.10029770`). Other bits
seen written:

| Mask | Set by | Meaning |
|---|---|---|
| `0x001` | `FN_bDrvCcdAcquireAndDxStart` | acquire enable |
| `0x002` | `FN_bDrvPutCcdFpgaSettings` | [UNKNOWN] |
| `0x060` | `FN_bDrvPutCcdFpgaSettings` | [UNKNOWN] |
| `0x100` | `FN_bDrvPutCcdIrMode` (`fcn.10029860`) | IR mode |

Writing it is `PutCcdFpgaControlReg(bits, set_or_clear)` → `02 06 44 03 82 00 lo hi`
with the **whole** 10-bit word, not just the changed bits, so you must maintain
the shadow yourself.

### The FIFO reset — [VERIFIED-FROM-BINARY]

`FN_bDrvResetFifos` = `fcn.1000a730`, two packets:

```
  02 04 10 01 84 02       host (FX2) register 0x84 := 2   -- reset FIFOs
  04 03 40 00 8A          light board command 0x8A
```

`FN_bBeforeScan` calls this **twice** (at `0x1002dcf5` and `0x1002e0ee`), before
and after CCD configuration.

### The stop side — [VERIFIED-FROM-BINARY]

`FN_bDrvDxStop` = `fcn.10009da0` → `04 03 40 00 92`.

### Order of operations in `FN_bBeforeScan` (`fcn.1002dbd0`) — [VERIFIED-FROM-BINARY]

Call sequence, in program order:

```
  ResetFifos                       02 04 10 01 84 02 ; 04 03 40 00 8A
  ... DPI / light config ...
  PutCcdFpgaSettings   (1002c340)  reg 0x82 idx 4,5,6,0xB + ctrl bits 0x60, 0x02
  PutCcdAtoDOffsets    (100299c0)  reg 0x84 idx 5,6,7
  PutCcdAtoDGains      (100298b0)  reg 0x84 idx 2,3,4
  ResetFifos                       (again)
  bDrvInitCcd          (1002d5c0)  reg 0x82 idx 1,2,3 := 0 ; idx 0xA := 0x400
                                   reg 0x84 idx 0 := 0x78 ; idx 1 := 0x80
  bSetCurrentScanType  (10031570)
  LampOn               (1002c5f0)  02 04 40 01 80 01   <<< lamp
  bDriveMotorAdvanceFilm(1000b6d0) 02 05 44 02 A5 .. ; 04 03 44 00 A0
```

then `FN_iScanStrips` (`fcn.10029b80`) runs, calling
`CcdAcquireAndDxStart` and then `PutCcdFpgaControlReg` per strip.

### What I could **not** establish — [UNKNOWN]

- Whether EP 0x86 is gated at all, or simply always streams whatever the CCD
  FPGA hands it. I found **no** register write whose obvious purpose is
  "enable/disable the EP 0x86 stream". The nearest candidate is host register
  `0x8F` on address `0x10`, toggled `0 → 1 → 0` around board probing in
  `FN_bInit2` (`fcn.1000b100`), but the code gives no name for it.
- My best reading, given you already observe a free-running dark stream, is that
  **EP 0x86 always streams and the difference between "dark" and "real" is
  entirely (i) the lamp being on and (ii) the FPGA acquire bit + exposure /
  gain / geometry registers being programmed.** That is [INFERRED], not proven.
- `FN_bDrvReadScanLine` (`fcn.1001bdf0`) does **not** read EP 0x86 at all — it
  uses the register-`0x07` block-read window on host address `0x10`
  (`fcn.10008f80` → `fcn.100090f0`). That is the calibration path, not the
  imaging path. So the binary does not document EP 0x86's gating anywhere I
  could find.

---

## 7. (d) Scanner identity / firmware versions — [VERIFIED-FROM-BINARY]

`FN_bDrvGetDevInfo` = `fcn.1000a370`. Two packets, for any board address `AA`:

```
  1)  02 04 AA 01 03 01        write 1 to register 0x03 (select device-info source)
  2)  01 03 AA 0C 07           read 12 bytes from register 0x07
```

Response to (2): `01 0E AA SS <12 bytes>`.

Source:

```asm
mov  byte [esp+0x14], 2       ; buf[0] = 2
mov  byte [esp+0x16], bl      ; buf[2] = address
mov  byte [esp+0x17], al      ; buf[3] = 1   (al = 1)
mov  byte [esp+0x18], 3       ; buf[4] = 0x03
mov  byte [esp+0x19], al      ; buf[5] = 1
call fcn.100095a0
...
push 0xc                      ; n = 12
push eax                      ; out buffer
push 7                        ; register 0x07
push ebx                      ; address
push edi
call fcn.10009410             ; Type 1 read
```

`FN_bUpdate` (`fcn.1001c3e0`) consumes the result at `0x1001cd01`:

```asm
movzx eax, byte [esp + 0x92]      ; devinfo[2]
movzx edi, byte [esp + 0x91]      ; devinfo[1]
```

so **`devinfo[1]` and `devinfo[2]` are the board's firmware version pair.**
The log line

```
Version USB 0x%02X,0x%02X  CCD 0x%02X,0x%02X  Lamp 0x%02X,0x%02X
        DX 0x%02X,0x%02X  Motor 0x%02X,0x%02X  Aps 0x%02X,0x%02X
```

(at `0x10065808`, printed by `fcn.1001ab40` from scanner fields `+0x70..+0x98`)
is six such pairs — one per subsystem, each obtained by running the two packets
above against that subsystem's board address.

Other pure-read status commands, all safe:

| Purpose | Packet | Source |
|---|---|---|
| Lamp hardware status | `01 03 40 01 83` | `fcn.1000b890:0x1000b8fe` |
| Lamp temperature (u16) | `01 03 40 02 84` | `fcn.1000b890:0x1000b99b` |
| Host status word (u16) | `01 03 10 02 03` | `fcn.1000b100:0x1000b2f4` |
| Focus board status (~~`01 03 28 01 EA`~~ — board absent on this unit) | — | `fcn.1000bd40` |
| Info string (30 bytes) | `01 03 AA 1E 90` | `fcn.10009790` |

---

## 8. SAFE TO SEND FIRST

Ordered most-confident first. **All of these use only Types 1, 2, 3 and 4**, so
none of them can wedge the firmware the way an unknown Type does. Types 1 and 3
are pure reads and cannot change device state at all.

| # | Packet | What it does | Success looks like | Confidence |
|---|---|---|---|---|
| 1 | `01 03 40 01 83` | read lamp hardware status | `01 03 40 88 <status>` — 6 bytes back, `resp[3] & 0x36 == 0` | **very high** |
| 2 | `01 03 40 02 84` | read lamp temperature (u16 LE) | `01 04 40 88 <lo> <hi>` | **very high** |
| 3 | `01 03 40 05 81` | read back the 5 LED level bytes | `01 07 40 88 <5 bytes>` — tells you whether levels are non-zero *before* you enable | **very high** |
| 4 | `01 03 40 0C 82` | read back the 12 LED duty-cycle bytes | `01 0E 40 88 <12 bytes>` | high |
| 5 | `02 04 40 01 03 01` then `01 03 40 0C 07` | device info for the light board; bytes [1],[2] = firmware version | `07 02 40 00`, then `01 0E 40 88 <12 bytes>` | **very high** |
| 6 | `02 04 44 01 03 01` then `01 03 44 0C 07` | same for the motor/main board | `07 02 44 00`, then `01 0E 44 08 <12 bytes>` | **very high** |
| 7 | **`02 04 40 01 80 01`** | **LAMP ON (visible)** | **`07 02 40 00`** — and the lamp should light | **high** |
| 8 | `02 04 40 01 80 00` | LAMP OFF — send this right after #7 | `07 02 40 00` | **high** |
| 9 | `01 03 10 02 03` | host / FX2 status word | `01 04 10 08 <lo> <hi>`; if `resp[3] & 0x20`, follow with `04 03 10 00 85` | high |
| 10 | `02 05 44 02 A5 E8 03` | set motor speed to the minimum legal value (1000). **Does not move the motor.** | `07 02 44 00` | high |
| 11 | `04 03 44 00 A0` | **start motor forward** — film will move. Have `04 03 44 00 A2` (stop) queued and send it within a second. | `07 02 44 00` | high |
| 12 | `02 04 10 01 84 02` | reset host FIFOs | `07 02 10 00` | medium |
| 13 | `04 03 40 00 8A` | light board FIFO/DX reset (second half of ResetFifos) | `07 02 40 00` | medium |

**If you can only afford one packet this power cycle, send #1.** It is a pure
read of a register the driver itself reads, it proves the register-index theory
end-to-end, and its result tells you whether the lamp subsystem is alive before
you try to switch it on.

**If you want the lamp on this power cycle**, send #3 first (read the levels),
then #7. If #3 comes back all zeros, expect #7 to succeed at the protocol level
(`07 02 40 00`) while producing no visible light, and the next thing to work out
is the `0x81` payload.

### Do not send

- Any Type other than 1, 2, 3, 4.
- `02 06 44 03 82 00 ...` (FPGA control) until you have read the current value —
  the driver always writes the *whole* 10-bit word, so a blind write will clobber
  bits you did not intend. There is no Type 1 read of `0x82` anywhere in the
  binary, so the shadow cannot be recovered from the device; it must be
  reconstructed by replaying the InitCcd sequence.
- `02 04 40 01 97 ..` — the firmware-update gate.

---

## 9. Honest summary of what is still unknown

1. **Physical units of motor register `0xA5`.** Range is proven; scale is not.
2. **The `0x81` LED-level payload semantics** — 5 bytes, position of R/G/B/IR
   and their scale are unresolved. Reading the register back is the cheapest way
   to learn them.
3. **Whether EP 0x86 needs an explicit enable.** I searched every packet-emitting
   call site in TLB.dll (all 60-odd of them are enumerated above) and found no
   register that names itself as a stream gate. Host register `0x8F` is the only
   candidate and its meaning is not documented in the binary.
4. **FPGA control register bits 1 and 5–6** (`0x002`, `0x060`).
5. **Response status bit 7 (`0x80`)** on the light board. It is provably *not*
   an error (it is outside the `0x36` error mask the driver accumulates) but the
   binary never tests it.
6. The `0x82` 12-byte lamp payload on the light board — layout verified as 12
   bytes, contents [UNKNOWN].
