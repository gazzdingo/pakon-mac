# 31 — The recovered Kodak PIC18 bootloader

Written 2026-08-06, from `backups/u11-picl/u11-full-A.hex` (U11 = PICL, read
three times over ICSP, byte-identical). Nothing in `backups/` was modified.

**Verdict up front: adapting it is straightforward.** Six instructions change,
ten bytes in total, and one of them is the I²C address literal. Everything else
is device-generic. The bootloader contains no PICL-specific hardware setup, no
CALLs out of its own region, and no dependence on the application beyond a
single hand-off `GOTO`. See §7 for the change list and §8 for the verdict in
full.

---

## 1. Correction: the bootloader is `0x0000`–`0x033F`, not `0x0000`–`0x03FF`

This changes how the whole thing should be read, so it goes first.

Every PICL application image Kodak ships (`nl*`, `pl*`, and in fact `AP*`,
`ce*`, `md*`, `lq*`, `mc09/0A*`) starts at **`0x000340`**, not `0x400`:

```
nl050A.HEX     lo=0x000340  hi=0x006b59   26646 bytes
nm0506.HEX     lo=0x000400  hi=0x002d7b   10616 bytes
```

The U11 dump matches `nl050A.HEX` over **`0x340`–`0x6B59`, all 26646 bytes,
zero mismatches** — including the config words at `0x300000`. So the true split
on U11 is:

| Range | Owner | Bytes |
|---|---|---|
| `0x0000`–`0x0281` | **bootloader code** (last instruction `SLEEP` at `0x0280`) | 613 non-`0xFF` |
| `0x0282`–`0x033F` | blank (`0xFF`) — bootloader slack | — |
| `0x0340`–`0x6B59` | `nl050A.HEX`, byte-exact | 26646 |
| `0x6B5A`–`0x7FFF` | blank | — |

The 800 non-`0xFF` bytes counted earlier in `0x0000`–`0x03FF` were 613 bytes of
bootloader **plus 187 bytes of application** that happen to live below `0x400`.

**The application base address is per-board, and it is the only structural
difference between the PICL and PICM layouts:**

* PICL app base = `0x340` → bootloader occupies `0x0000`–`0x033F`
* PICM app base = `0x400` → bootloader occupies `0x0000`–`0x03FF`

The convention at the app base is fixed across every image in the tree
[VERIFIED — 56 vendor HEX files parsed]:

* `app_base + 0x00` = `GOTO <app entry>` (e.g. `nl050A` → `0x6518`,
  `nm0506` → `0x2BC2`)
* `app_base + 0x08` = the CCS interrupt dispatcher, beginning
  `6E05 CFD8 F006 …` (`MOVWF 0x05 / MOVFF STATUS,0x06 / …`)

Two of the 56 — `ce0004.HEX` and `pm0101.HEX` — put `0xFFFF` at `+0x08` and the
dispatcher at `+0x0A`, so the convention is not quite universal. **`nm0506.HEX`,
the image we care about, has it at `+0x08`** (`0x408: 6E05 CFD8 F006 50E9 …`),
which is what the `0x0008` patch in §7 targets. Check this byte pattern again if
a different `nm*` build is ever used.

That is what the bootloader's `0x0008` vector forwards to. It is a convention,
not a per-build address, which is exactly what makes the adaptation cheap.

---

## 2. `0x0018 GOTO 0x3D00` explained — it is dead code

This was the one thing that looked alarming. It is not.

`0x3D00` is **ordinary application code that differs in every version**:

| Image | first words at `0x3D00` |
|---|---|
| `nl0206` | `0101 2d84 d005 bf60` |
| `nl0307` | `6aef 2b2a d7e2 0100` |
| `nl0309` | `f261 c260 ffea c001` |
| `nl050A` | `6f7b c25b f27c 0100` |
| `nm0506` | `ffff ffff ffff ffff` (blank — beyond the image) |

It is not a stable ISR entry point, and it is not reachable:

* The bootloader clears `RCON.IPEN` twice — `0x001E` and `0x0048`
  (`9ED0 bcf RCON,IPEN`).
* `nl050A` clears it again at `0x651A`, its second instruction.
* `nm0506` clears it again at `0x2BC4`, its second instruction.
* **Neither application ever sets it.** A full scan of both images for any
  access-bank write to `RCON` (`0xFD0`) finds only `9ED0` (the clear) and
  `82D0`/`80D0` at `0x6668`/`0x666A` and `0x2C70`/`0x2C72`, which set bits 1
  and 0 — the `POR`/`BOR` reset flags, not `IPEN`.

With `IPEN = 0` the PIC18 has no interrupt priority and **every** interrupt
vectors to `0x0008`. Vector `0x0018` is never taken by any code path. The
`GOTO 0x3D00` is a build artefact, most likely whatever the CCS linker had for
that symbol at the time the boot block was assembled. Any value works; §7
replaces it with the safe one.

---

## 3. Annotated disassembly

Full listing regenerated with `gpdasm -p p18f452 -n -c`. RAM references are
access-bank; the bootloader uses `0x00`–`0x15` for state and `0x20`–`0x2F` as
the packet buffer.

### 3.1 Reset and the app-valid gate — `0x0000`, `0x001C`

```
000000: ef0e f000   GOTO 0x001C
000008: efa4 f001   GOTO 0x0348          ; app_base + 8  -> app's ISR dispatcher
000018: ef80 f01e   GOTO 0x3D00          ; DEAD (IPEN always 0) -- see §2

00001c: 6af8        CLRF  TBLPTRU
00001e: 9ed0        BCF   RCON,IPEN      ; no interrupt priorities, ever
000020: 6aea 6ae9   CLRF  FSR0H / FSR0L
000024: 80c1 82c1 84c1 96c1              ; ADCON1 PCFG = 0b0111 -> all pins digital
00002c: cff2 f016   MOVFF INTCON,0x16    ; CCS read_eeprom() prologue: save GIE
000030: 9ef2        BCF   INTCON,GIE
000032: 6aa9        CLRF  EEADR          ; index 0
000034: 9ca6        BCF   EECON1,CFGS
000036: 9ea6        BCF   EECON1,EEPGD   ; -> data EEPROM, not flash
000038: 80a6        BSF   EECON1,RD
00003a: 50a8        MOVF  EEDATA,W
00003c: be16 8ef2   BTFSC 0x16,7 / BSF INTCON,GIE     ; restore GIE
000040: 08aa        SUBLW 0xAA
000042: e102        BNZ   0x0048         ; not 0xAA -> stay in the bootloader
000044: efa0 f001   GOTO  0x0340         ; == 0xAA -> RUN THE APPLICATION
```

The gate is exactly as documented: **internal EEPROM index 0 == `0xAA` → jump
to the application base.** Nothing else is checked. Note the consequences:

* If `EEPROM[0] == 0xAA` and the application flash is blank, the bootloader
  still jumps — the CPU then slides through blank flash and wraps. **The
  bootloader is not a safety net against a blank app.** It is a safety net
  against an *interrupted update*, which is a different thing.
* The bootloader **never writes** internal EEPROM (its only EEPROM access is
  this read; both `EECON1` unlock sequences elsewhere have `EEPGD = 1`, i.e.
  flash). The `0xAA` flag is written by the *application*, via the application
  command `02 05 44 02 0a 00 aa` (board `0x44` = PICM app, cmd `0x0A` =
  write internal EEPROM, index `0x00`, value `0xAA`). That closes the vendor
  update loop: flash → command 8 → app runs → host sets the flag → next reset
  boots straight to the app.

### 3.2 MSSP init — the I²C address literal — `0x0048`–`0x0078`

```
000048: 9ed0        BCF   RCON,IPEN
00004a: 6af2        CLRF  INTCON
00004c: 0e1f 16f0   MOVLW 0x1F / ANDWF INTCON3,F      ; CCS disable_interrupts(GLOBAL)
000050: 6a9d 6aa0   CLRF  PIE1 / PIE2                 ; polled, never interrupt-driven
000054: 8694 8894   BSF   TRISC,3 / TRISC,4           ; SCL, SDA -> inputs
000058: 8682 8882   BSF   PORTC,3 / PORTC,4           ; latch bits (pins are tri-stated)
00005c: 0e42        MOVLW 0x42            ; <<<<<< THE I2C SLAVE ADDRESS
00005e: 6ec8        MOVWF SSPADD
000060: 8ec7 8cc7   BSF   SSPSTAT,SMP / SSPSTAT,CKE
000064: 9cc6 9ec6   BCF   SSPCON1,SSPOV / WCOL
000068: 0e36 6ec6   MOVLW 0x36 / MOVWF SSPCON1        ; SSPEN=1, CKP=1, SSPM=0110 (I2C slave, 7-bit)
00006c: 9006 9206   BCF   0x06,0 / 0x06,1             ; clear state flags
000070: 6a07        CLRF  0x07                        ; clear the status byte
000072: 6a15 6a14 6a13 6a12                           ; clear the 24-bit address latch (+1 spare)
```

**The address is a single literal byte at flash address `0x005C`.** It is not
computed, not read from EEPROM, not derived from a pin. It is `MOVLW 0x42`
followed immediately by `MOVWF SSPADD`, and `0x42` occurs **exactly once** in
the whole of `0x0000`–`0x033F`. `SSPADD` is written from exactly one place
(`0x005E`); `SSPCON1` from two (`0x006A` arm, `0x0264` disarm).

`SSPADD = 0x42` is the 8-bit form; in 7-bit slave mode the address sits in bits
7:1, so this is 7-bit `0x21`. The application uses `0x40` → 7-bit `0x20`.
PICM needs `0x46` → 7-bit `0x23` (its app uses `0x44` → 7-bit `0x22`).

Note `SSPCON1 = 0x36` here is **byte-identical to the value the PICM
application writes at `0x1A8C`**. Same module, same mode, same constant.

### 3.3 The I²C slave state machine — `0x007A`–`0x00B0`

Purely polled; interrupts are off.

```
label_005:
00007a: 0004        CLRWDT                       ; the WDT is enabled in hardware
00007c: b69e        BTFSC PIR1,SSPIF
00007e: d001        BRA   +
000080: d7fc        BRA   label_005              ; spin
+
000082: 969e        BCF   PIR1,SSPIF
000084: cfc7 f008   MOVFF SSPSTAT,0x08
000088: ba08        BTFSC 0x08,5                 ; D/A: 1 = data byte
00008a: d012        BRA   0x00B0
; --- address byte ---
00008c: 6a0a 6a0b   CLRF  0x0A (checksum) / 0x0B (byte index)
000090: 9206        BCF   0x06,1
000092: b408 8206   BTFSC 0x08,2 / BSF 0x06,1    ; R/W bit -> 0x06.1 = "master is reading"
000096: a206        BTFSS 0x06,1
000098: d007        BRA   0x00A8                 ; write transaction
; master is reading: emit the latched status byte immediately
00009a: c007 f009   MOVFF 0x07,0x09
00009e: c007 ffc9   MOVFF 0x07,SSPBUF
0000a2: 6a07        CLRF  0x07                   ; status is read-and-clear
0000a4: 8006        BSF   0x06,0                 ; "act at end of this byte"
0000a6: d003        BRA   0x00AE
0000a8: cfc9 f009   MOVFF SSPBUF,0x09            ; write: keep the address byte...
0000ac: 9cc6        BCF   SSPCON1,SSPOV
0000ae: d068        BRA   0x0180                 ; ...and fold it into the checksum
```

### 3.4 Packet parser — `0x00E2`–`0x0150`

The on-wire packet the slave sees (after the hardware consumes the I²C address
byte) is:

```
  [0] dataLen | 0x80 if the master will read back  (low 6 bits = length)
  [1] command byte
  [2] address bits  7..0     -> RAM 0x12  -> TBLPTRL
  [3] address bits 15..8     -> RAM 0x13  -> TBLPTRH
  [4] address bits 23..16    -> RAM 0x14  -> TBLPTRU
  [5..] payload              -> RAM 0x20+
  [n] checksum = ~(sum of the I2C address byte and all data bytes)
```

```
0000e2: cfc9 f009   MOVFF SSPBUF,0x09
0000e8: 520b e10f   MOVF 0x0B,F / BNZ 0x010A     ; index 0 -> the length byte
0000ec: 6a0c        CLRF  0x0C                   ; reply length := 0
0000ee: c009 f00f   MOVFF 0x09,0x0F
0000f2: 0e3f 160f   MOVLW 0x3F / ANDWF 0x0F,F
0000f6: ae09        BTFSS 0x09,7
0000f8: d005        BRA   0x0104
0000fa: c00f f00c   MOVFF 0x0F,0x0C              ; bit7 set: 0x0C = bytes to return
0000fe: 0e02 6e0f   MOVLW 2 / MOVWF 0x0F         ;           packet is 2 bytes + cksum
000102: d002        BRA   0x0108
000104: 0e02 260f   MOVLW 2 / ADDWF 0x0F,F       ; bit7 clear: expect dataLen+2 bytes

label_016 (index != 0):
00010a: 500f 5c0b   MOVF 0x0F,W / SUBWF 0x0B,W
00010e: e221        BC    0x0152                 ; index reached the length -> checksum byte
000110: 0e01 5c0b 6e10                          ; 0x10 = index - 1
000116: 5210 e103   MOVF 0x10,F / BNZ 0x0120
00011a: c009 f011   MOVFF 0x09,0x11              ; byte 1 -> the command register
000120: 5010 0803 e30b                          ; 0x10 in 1..3 ?
000126: ...         FSR0 = 0x12 + (0x10 - 1)     ; bytes 2..4 -> address latch
00013c: ...         FSR0 = 0x20 + (0x10 - 4)     ; bytes 5.. -> payload buffer
```

### 3.5 Checksum, and the length/command interlock — `0x0152`–`0x0184`

```
000152: 500a 0aff 5c09                          ; W = ~sum ; compare with received byte
000158: e002        BZ    0x015E
00015a: 8407        BSF   0x07,2                 ; CHECKSUM ERROR -> status bit 2
00015c: d010        BRA   0x017E

00015e: a211 d003   BTFSS 0x11,1 / BRA +         ; cmd bit1 (=2, write)?
000162: 500b 0815 e00a  MOVF 0x0B,W / SUBLW 0x15 / BZ accept   ; requires exactly 21 bytes
000168: a411 d003   BTFSS 0x11,2 / BRA +         ; cmd bit2 (=4, erase)?
00016c: 500b 0805 e005  MOVF 0x0B,W / SUBLW 0x05 / BZ accept   ; requires exactly 5 bytes
000172: a611 d004   BTFSS 0x11,3 / BRA +         ; cmd bit3 (=8, finalise)?
000176: 500b 0802 e101  MOVF 0x0B,W / SUBLW 0x02 / BNZ reject  ; requires exactly 2 bytes
00017c: 8006        BSF   0x06,0                 ; accept: run the action
```

This is a real interlock, and it is worth stating plainly: **a command is only
executed if its byte count is exactly right.** A truncated or over-long packet
is silently ignored (no status bit is set for it either).

Command `1` (read) has no bit tested here — reading needs no action on the
write transaction. The write packet's only job is to latch the address into
`0x12`/`0x13`/`0x14`, which the parser does unconditionally. That is why the
`02 06 <board> 03 01 <addr24>` "read setup" packet works: `dataLen=3, cmd=1`
gives 5 data bytes, no command bit matches, no action fires, but the address
sticks.

### 3.6 Command 1 — read 16 bytes — `0x018E`

Reached from the *read* transaction (`0x06.1` set), not from a write packet:

```
00018e: c014 fff8 / c013 fff7 / c012 fff6       ; TBLPTR <- latched 24-bit address
00019a: 0e20 6ee1 6ae2                          ; FSR1 = 0x0020
0001a0: 0e10 6e0d   MOVLW 16 / MOVWF 0x0D
0001a4: (loop)      TBLRD*+ ; MOVF TABLAT,W ; MOVWF POSTINC1
0001b8: cff8 f014 / cff7 f013 / cff6 f012       ; TBLPTR saved back -> AUTO-INCREMENT
```

The address auto-increments across successive reads, exactly as
`tools/picm_read_flash.py` assumes. **Reads are not address-guarded** — the
bootloader will happily read itself out, which is how a healthy PICM could have
been dumped over I²C had it been alive. `EECON1.CFGS` is left at 0 throughout,
so config words at `0x300000` are *not* reachable this way; only ICSP reads
those.

### 3.7 The self-protection guard — `0x01C6`–`0x01DE`

```
0001c6: 5215 e10b   MOVF 0x15,F / BNZ ok
0001ca: 5214 e109   MOVF 0x14,F / BNZ ok         ; TBLPTRU != 0 -> allowed
0001ce: 5013 0803   MOVF 0x13,W / SUBLW 0x03
0001d2: e306        BNC  ok                      ; TBLPTRH > 3 -> allowed
0001d4: e103        BNZ  reject                  ; TBLPTRH < 3 -> rejected
0001d6: 5012 083e   MOVF 0x12,W / SUBLW 0x3E
0001da: e302        BNC  ok                      ; TBLPTRL > 0x3E -> allowed
0001dc: 8207        BSF  0x07,1                  ; REJECT -> status bit 1
```

Reject if `address <= 0x00033E`. That is the bootloader refusing to erase or
overwrite itself, and the boundary is set one byte below the PICL application
base of `0x340`. It applies to erase and write only, never to read.

### 3.8 Command 4 — erase a 64-byte row — `0x01E0`

```
0001e4: TBLPTR <- 0x14/0x13/0x12
0001f0: 8ea6  BSF EECON1,EEPGD      ; flash, not EEPROM
0001f2: 9ca6  BCF EECON1,CFGS
0001f4: 84a6  BSF EECON1,WREN
0001f6: 88a6  BSF EECON1,FREE       ; row erase
0001f8: 0e55 6ea7 / 0eaa 6ea7       ; the 0x55 / 0xAA unlock
000200: 82a6  BSF EECON1,WR
000202: 94a6 9ea6  BCF WREN / BCF EEPGD
000206: 9411  BCF 0x11,2            ; consume the command bit
```

### 3.9 Command 2 — write 16 bytes — `0x020A`

```
00020e: TBLPTRU/H <- 0x14/0x13 ; TBLPTRL <- 0x12 - 1     (pre-decrement)
00021c: FSR1 = 0x0020 ; 0x0E = 2                          (two 8-byte blocks)
000226: outer loop x2:
00022e:   inner loop x8:  INCF TBLPTRL ; MOVF POSTINC1,W ; MOVWF TABLAT ; TBLWT*
000244:   BSF EEPGD / BCF CFGS / BSF WREN / 0x55 / 0xAA / BSF WR / BCF WREN / BCF EEPGD
00025c: 9211  BCF 0x11,1
```

Two 8-byte programming operations — the PIC18F452 write block is 8 bytes, the
erase row is 64. **There is no implicit erase**, which is why the host has to
erase-then-write, exactly as `tools/flash_picm.py` already does.

### 3.10 Command 8 — finalise — `0x0260`

```
000260: a611 d003   BTFSS 0x11,3 / BRA done
000264: 6ac6        CLRF  SSPCON1               ; disarm the MSSP, release SDA/SCL
000266: efa0 f001   GOTO  0x0340                ; run the application
```

Note it does **not** consult `EEPROM[0]`. Command 8 runs the app unconditionally.

### 3.11 Clock-stretch release — `0x026A`–`0x027E`

```
00026a: a206 d008   BTFSS 0x06,1 / BRA loop     ; only on read transactions
00026e: 0ea6 6e00   MOVLW 0xA6 / MOVWF 0x00     ; ~166-iteration settling delay
000272: (spin)
000278: 88c6        BSF   SSPCON1,CKP           ; release SCL
00027a: b0c7 d7fe   BTFSC SSPSTAT,BF / BRA self ; wait for the byte to go out
00027e: d6fd        BRA   label_005
000280: 0003        SLEEP                       ; unreachable; end of the bootloader
```

The `BF` wait at `0x027A` has **no `CLRWDT`**. If a master abandons a read
mid-byte the watchdog resets the chip. That is recovery behaviour, not a bug,
but it explains any observed "the PIC rebooted when I ctrl-C'd mid-transfer".

---

## 4. Protocol verification — confirms our model, with two refinements

| Claim | Status |
|---|---|
| cmd 1 = read 16 bytes at a 24-bit LE address | **Confirmed** (§3.6). Address is latched by any packet; the read itself happens on the I²C read transaction and auto-increments. |
| cmd 2 = write 16 bytes | **Confirmed** (§3.9). 2 × 8-byte program cycles. No implicit erase. |
| cmd 4 = erase a 64-byte row | **Confirmed** (§3.8). `EECON1.FREE` row erase. |
| cmd 8 = finalise / run the application | **Confirmed** (§3.10). Disarms the MSSP first. |
| `EEPROM[0] == 0xAA` gates the application | **Confirmed** (§3.1). Read at reset, before the MSSP is armed. |
| wire form `02 06 <b> 03 01 <addr24>` | **Confirmed**: on-wire `03 01 a0 a1 a2 <cksum>`, 5 data bytes, no command bit matches, address latched as a side effect. |
| wire form `04 03 <b> 00 08` | **Confirmed**: on-wire `00 08 <cksum>`, 2 data bytes, cmd bit3, length check `== 2` passes. |
| wire form `01 03 <b> <len> 07` | **Confirmed with a refinement** — see below. |
| status byte is `resp[3]` | **Confirmed** — see below. |

**Refinement 1 — the FX2 sets bit 7 of `dataLen` on type-1 (read) packets.**
The bootloader only loads its reply length (`RAM 0x0C`) when bit 7 of the first
received byte is set. `tools/picm_read_flash.py` sends `01 03 <board> 0x10 07`,
so the byte that must reach the slave is `0x90`, not `0x10`. The FX2 therefore
ORs `0x80` in when it transmits a type-1 packet. The trailing `07` is a
deliberate no-op command: bit 3 is clear, so the length/command interlock
(§3.5) rejects it and no action fires — the packet exists purely to set the
reply length.

**That `07` is load-bearing and one bit from dangerous.** Bit 3 is what makes a
2-byte packet *acceptable*; the dispatch (§3.7–§3.10) then acts on bit 2 first,
bit 1 second, bit 3 last, and only one action fires per packet. So on a 2-byte
packet:

| cmd | outcome |
|---|---|
| `0x07` | rejected by the length interlock — no action (this is the fetch) |
| `0x08` | exit the bootloader, run the app (the documented finalise) |
| `0x0B` | accepted, and **writes 16 bytes** of whatever is in RAM `0x20`+ to the latched address |
| `0x0F` | accepted, and **erases the 64-byte row** at the latched address |

A single flipped bit in that constant turns a read into a flash write. Worth a
comment in `picm_read_flash.py`.

**Refinement 2 — the PIC's own status byte is a bitfield, and only two bits
exist in the bootloader.** `RAM 0x07`, emitted as the first byte of every read
transaction and cleared on emission:

| Bit | Mask | Set at | Meaning |
|---|---|---|---|
| 1 | `0x02` | `0x01DC` | address `<= 0x33E` — write/erase refused |
| 2 | `0x04` | `0x015A` | checksum mismatch |

Nothing else ever writes it. The enum documented in `12-command-protocol.md`
(`0 ok / 1 no-ack / 2 invalid / 3 checksum`) is the **FX2's** type-7 mapping of
that bitfield, not the PIC's byte, and both descriptions are correct at their
own layer. The type-1/3 bitfield table in that doc describes the *application's*
richer status byte; the bootloader never sets bit 0 (busy) or bit 3 (ready).

**Checksum rule, now exact.** `checksum = ~(sum of bytes)` (one's complement,
8-bit). On a **write** the sum includes the I²C address byte itself
(`0x46`); on a **read** it does not — the address byte's value is overwritten
by the status byte before the accumulator is touched (§3.3). For
`04 03 46 00 08` the on-wire sum is `0x46 + 0x00 + 0x08 = 0x4E`, so the
trailing byte is `0xB1`.

**Response framing, now exact.** An I²C read returns
`[status] [buf[0] … buf[N-1]] [~checksum]` where `N` = the reply length latched
by the preceding type-1 packet. The FX2 prepends its 3-byte header, which is
why status lands at `resp[3]` and payload at `resp[4]`.

---

## 5. Hardware dependencies — there are essentially none

Every peripheral the bootloader touches:

| What | Value | PICL-specific? |
|---|---|---|
| `ADCON1` | `PCFG = 0b0111` → all pins digital | No |
| `INTCON`, `INTCON3`, `PIE1`, `PIE2` | cleared / masked | No |
| `TRISC` bits 3, 4 | inputs (SCL, SDA) | No — same pins on both PICs |
| `PORTC` bits 3, 4 | latch bits set (pins are tri-stated anyway) | No |
| `SSPSTAT` | `SMP=1`, `CKE=1` | No |
| `SSPCON1` | `0x36` | No — identical to the PICM app's value |
| `SSPADD` | `0x42` | **YES — the only board-specific value** |
| `EEADR`/`EECON1` | index 0 read; flash erase/write | No |
| WDT | `CLRWDT` in the poll loop | No |

**No other TRIS register is written**, so every other pin stays at its reset
default of input/high-Z. While the chip sits in the bootloader, nothing on the
motor board is driven — which is exactly the state the PICM was observed in
during the work recorded in `20-picm-in-bootloader.md`, and it was harmless
then. No LED, no lamp, no light-board-specific port setup, no timers, no CCP,
no A/D. There is nothing here that a motor board would need done differently.

**Config words are not the bootloader's business.** `EECON1.CFGS` is never set,
so the bootloader can neither read nor write `0x300000`. Fuses come from the
ICSP programming pass only. Note that U11's actual fuses
(`00 26 06 09 …`) do **not** match `nl050A.HEX`'s (`00 26 07 0b …`) — the chip
keeps whatever it was factory-programmed with, and no field update has ever
changed them. For a replacement PICM, take the fuses from `nm0506.HEX`:

```
0x300000: 00 26 06 0d 00 01 81 00 0f c0 0f e0 0f 40
```

(`CONFIG2H = 0x0D` → WDT enabled, ~1.15 s; `CONFIG4L = 0x81` → LVP **off**,
which is why ICSP needs proper Vpp; `CONFIG6H = 0xE0` → boot block **not**
write-protected, so the only thing protecting the bootloader is its own address
guard in §3.7.)

---

## 6. Self-containment

Every control transfer leaving `0x0000`–`0x033F`, exhaustively:

| At | Instruction | Purpose |
|---|---|---|
| `0x0000` | `GOTO 0x001C` | internal |
| `0x0008` | `GOTO 0x0348` | high-priority ISR → `app_base + 8` |
| `0x0018` | `GOTO 0x3D00` | **dead** (§2) |
| `0x0044` | `GOTO 0x0340` | app-valid → `app_base` |
| `0x0266` | `GOTO 0x0340` | command 8 → `app_base` |

**There are no `CALL`s and no `RCALL`s anywhere in the bootloader** — it is a
single flat loop, so it uses no hardware stack levels and cannot corrupt the
application's. It calls nothing in application space. Apart from the two
deliberate hand-offs and one dead vector, it is fully self-contained.

---

## 7. The change list

Six instructions. Ten bytes. Applied to the 613 bytes of `0x0000`–`0x033F`
extracted from `u11-full-A.hex`.

| Flash addr | From | To | Instruction | Why |
|---|---|---|---|---|
| `0x0008` | `A4 EF 01 F0` | `04 EF 02 F0` | `GOTO 0x0348` → `GOTO 0x0408` | **Required.** app_base + 8. Without it the app's ISR is never reached and the first interrupt slides through blank flash into the app's reset path with a return address on the stack. |
| `0x0018` | `80 EF 1E F0` | `04 EF 02 F0` | `GOTO 0x3D00` → `GOTO 0x0408` | Cosmetic — provably unreachable (§2). Pointing it at the same dispatcher is the safest possible value if `IPEN` were ever set. |
| `0x0044` | `A0 EF 01 F0` | `00 EF 02 F0` | `GOTO 0x0340` → `GOTO 0x0400` | **Required.** The app-valid hand-off. |
| `0x005C` | `42` | `46` | `MOVLW 0x42` → `MOVLW 0x46` | **Required.** The I²C slave address. One byte. |
| `0x0266` | `A0 EF 01 F0` | `00 EF 02 F0` | `GOTO 0x0340` → `GOTO 0x0400` | **Required.** Command 8 hand-off. |
| `0x01D8` | `3E` | `FE` | `SUBLW 0x3E` → `SUBLW 0xFE` | Optional. Moves the write/erase floor from `0x33E` to `0x3FE` so the guard matches the PICM boot block. Harmless either way — `0x282`–`0x3FF` is blank in both cases — but leaving it means a host could erase `0x340`–`0x3FF` on a PICM. |

**Yes — the I²C address is a single literal byte at `0x005C`.** That is the
whole of question 2.

Verified by rebuilding and re-disassembling: `diff` of the original vs patched
`gpdasm` listings shows those six instructions and nothing else.

```
000008:  ef04  goto 0x000408          (was efa4 -> 0x000348)
000018:  ef04  goto 0x000408          (was ef80 -> 0x003d00)
000044:  ef00  goto 0x000400          (was efa0 -> 0x000340)
00005c:  0e46  movlw 0x46             (was 0e42)
0001d8:  08fe  sublw 0xfe             (was 083e)
000266:  ef00  goto 0x000400          (was efa0 -> 0x000340)
```

### Building the replacement image

```
0x000000 – 0x00033F   patched bootloader (613 non-FF bytes)
0x000340 – 0x0003FF   0xFF  <-- MUST be blank: this is app space on a PICL,
                                boot space on a PICM, and nm0506 starts at 0x400
0x000400 – 0x002D7B   nm0506.HEX verbatim
0x002D7C – 0x007FFF   0xFF
0x300000 – 0x30000D   00 26 06 0d 00 01 81 00 0f c0 0f e0 0f 40   (from nm0506.HEX)
0xF00000 – 0xF000FF   internal EEPROM -- see below
```

### What to put in the replacement's EEPROM

The dead PICM's own EEPROM is unrecoverable, so this is a choice, not a
restoration. **Recommended staging:**

1. Program `EEPROM[0]` to something **other than** `0xAA` (e.g. `0x00`). The
   chip then comes up in the bootloader, and the first thing you can do is
   confirm it answers at `0x46` and read its own flash back over I²C — a full
   verification pass with nothing at risk.
2. Set `EEPROM[5] = 0x00` — the persisted fault code (`27-icsp-procedure.md`
   §4). Leaving it `0xFF` would present as fault nibble `0xF` on the diagnostic
   LED.
3. Then send `04 03 46 00 08` to run the application, and let the application
   set `EEPROM[0] = 0xAA` itself via `02 05 44 02 0a 00 aa`, the way Kodak's
   updater does.

U11's EEPROM, for reference (it is **PICL** state — index 0 is the only entry
whose meaning is known to be shared):

```
00: aa ff f8 80 07 00 20 48 61 c0 03 03 03 1f ff ff
10: ff 01 01 10 04 92 08 53 31 24 20 37 53 31 24 20
20: 37 37 00 01 0b bc 37 00 01 0b bc 90 ff ff ff ff
30: ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff
40: 80 ff ff ff ff ff ff ff ff ff ff ff ff ff ff ff
50..ff: all 0xFF, except index 0xFE = 0x01
```

`EEPROM[0] = 0xAA` ✓ and `EEPROM[5] = 0x00` — a healthy board with no persisted
fault, which is consistent with U11 being the good chip.

---

## 8. Verdict

**Straightforward.** Not fiddly, and nowhere near unwise.

The reasons this is a much better outcome than the 12-byte vector stub:

* The address is one literal byte. Nothing computes it, nothing reads it from
  hardware, and it appears exactly once in the image.
* The bootloader has zero PICL-specific hardware setup. It configures the MSSP,
  the two I²C pins, and nothing else. Every other pin stays high-Z.
* It has no `CALL`s out of its own region and consumes no stack.
* The only application coupling is `app_base` and `app_base + 8`, and that
  convention holds across all 56 vendor images in the tree.
* The result is *genuine Kodak code* implementing the real protocol, so the
  replacement PICM can be field-updated with `nm*.HEX` by Kodak's own tooling
  forever after — which the stub could never have done.

**The residual risks, honestly stated:**

1. **We are synthesising a PICM bootloader, not recovering one.** Kodak's real
   PICM boot block is still unseen. It is very probably this same source
   recompiled with a different address and app base, but it could differ in
   ways we cannot detect — a different guard constant, an extra command, a
   board-ID byte somewhere in the slack. Nothing in the observed PICM behaviour
   contradicts our version, but "we never saw it" remains true.
2. **`0x282`–`0x33F` and `0x340`–`0x3FF` are blank in our image.** If the real
   PICM bootloader used that space for anything, we lose it silently.
3. **The `0x0018` vector value is a guess** (though a provably-inert one).

None of these can brick anything: the replacement is a new chip, and if the
synthesised bootloader misbehaves it can simply be re-programmed over ICSP.
That is the difference between this and every write attempted on the original.

---

## 9. Correction: there is no PIC16 Kodak bootloader in the vendor tree either

`analysis/pic16dis.py`'s header, and `27-icsp-procedure.md` §8 row 6, state that
the `mc*`/`dx*`/`lp*`/`cd*` images "include their `0x0000`–`0x03FF` bootloader"
and are therefore a behavioural specification for the PIC18 one. **They do
not.** Those images are simply *older, pre-bootloader standalone builds.*

Evidence:

| Image | reset vector target | contains a boot block? |
|---|---|---|
| `CD010F.hex` | word `0x647` | no |
| `DX020E.HEX` | word `0xE05` | no |
| `LP0110.HEX` | word `0x6D2` | no |
| `LP0210.HEX` | word `0xA47` | no |
| `dx0211.HEX` | word `0x1800` | no |
| `mc061a/071a/081B` | word `0x1800` | no |

In every one, the reset vector jumps straight into ordinary application code,
and words `0x000`–`0x19F` hold the CCS interrupt dispatcher plus a standard
`SSPSTAT & 0x2D` Microchip I²C-slave state machine — application code the
linker placed low, not a bootloader. `mc061a`'s `0x1800` region is its `main()`
(it sets `ADCON1`, then calls into `0x04EF`, `0x056F`, … in normal app space).

The generational split is visible in the file list: within each family, the
early images start at `0x0000` (full standalone, factory ICSP) and the later
ones start at `0x340` (update-only, bootloader present) —
`mc061a/071a/081B` → `0x0000` but `mc0919/mc0A19` → `0x340`;
`LP01/LP02` → `0x0000` but `pl*` → `0x340`. Kodak added the bootloader partway
through the product's life and switched to shipping app-only updates.

**So `u11-full-A.hex` is the only copy of a Kodak bootloader, of any core, that
exists anywhere we have looked.** It should be treated accordingly.

Consequence for `27-icsp-procedure.md` §8 row 6: the claim that the light-board
PIC's firmware "is restorable from files, unlike U11's" is **wrong** — `lp*`
images are pre-bootloader full builds for an older light board, and if that PIC
has a bootloader it is as unrecoverable as U11's was. This does not change the
"do not ICSP a working board" rule; it strengthens it.

---

## 10. Open questions, and what would settle each

| Question | Status | What would settle it |
|---|---|---|
| Does Kodak's real PICM boot block differ from our synthesis beyond the six patches? | **Unknown, unknowable from here** | A dump of any surviving F-135/F-235 PICM over ICSP. One healthy donor board ends this permanently — and would be worth doing regardless, as an archive. |
| Does the FX2 really OR `0x80` into `dataLen` for type-1 packets? | **Inferred, not observed** | Disassemble the type-1 transmit path in the FX2 firmware (`fx2/`), or scope SDA during one `picm_read_flash.py` fetch. The bootloader logic leaves no other possibility, but it has not been seen on the wire. |
| Meaning of internal EEPROM indices 2, 3, 4, 6 | **Named, not decoded** | Both apps reach EEPROM through generic helpers taking the index in a RAM slot, so most call sites pass a computed value; pinning them needs a CFG with constant propagation, not a grep. In `nm0506` the writer is `0x0F70` — a *write-if-different* routine that reads `EEPROM[arg0]`, compares against `arg1`, and skips the program cycle when they already match. It has two callers, `0x1D14` and `0x1D24`, and only `0x1D24` passes literals: `(index 2, value 0)`. |
| U11's fuses are `CONFIG2H=0x09`, `nl050A.HEX` ships `0x0B` | **Explained, not a fault** | Already settled: the bootloader cannot write config (`CFGS` never set), so the chip keeps its factory fuses forever. Nothing to fix. |
| Is the `0x0018` value in a real PICM boot block something meaningful? | **Cannot matter** | `IPEN` is provably never set by bootloader or app (§2), so the vector is unreachable regardless of its value. |

---

## Appendix — reproducing this

Nothing here needs hardware. Working files were kept in `/tmp/blwork`; nothing
in `backups/` was touched and nothing was committed.

```
# extract the bootloader region as an Intel HEX and disassemble it
python3 - <<'EOF'
mem, ext = {}, 0
for l in open('backups/u11-picl/u11-full-A.hex'):
    l = l.strip()
    if not l.startswith(':'): continue
    b = bytes.fromhex(l[1:]); n, a, t = b[0], (b[1] << 8) | b[2], b[3]
    if   t == 0: mem.update({ext + a + i: v for i, v in enumerate(b[4:4+n])})
    elif t == 4: ext = ((b[4] << 8) | b[5]) << 16
    elif t == 1: break
out = []
for a in range(0, 0x340, 16):
    rec = [16, (a >> 8) & 0xff, a & 0xff, 0] + [mem.get(a+i, 0xff) for i in range(16)]
    out.append(':' + ''.join(f'{x:02X}' for x in rec + [(-sum(rec)) & 0xff]))
open('/tmp/bl.hex', 'w').write('\n'.join(out + [':00000001FF']) + '\n')
EOF

gpdasm -p p18f452 -n -c /tmp/bl.hex
```

`gputils 1.5.2` (`/opt/homebrew/bin/gpdasm`) decodes the PIC18 core cleanly,
including `MOVFF`, `TBLRD*+`, `TBLWT*` and the SFR names — the local
`analysis/pic16dis.py` was not needed and would not have handled this core.
