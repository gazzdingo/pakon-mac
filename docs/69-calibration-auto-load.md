# 69 — Loading a scanner's own calibration automatically

**Status:** serial-keyed lookup and auto-load implemented and tested; pipeline
wiring specified but deliberately not applied; multi-page EEPROM addressing
investigated (§5).

**Scope note.** Nothing in this work touched hardware. No EEPROM was read, no
USB device was opened, and `calibration/` was not modified. Every result below
comes from the already-stored read `2026-08-08T15-27-44Z` and from static
analysis.

---

## 1. The goal, and the shape the vendor gave it

From the F-135 Service Manual, quoted in `backups/eeprom-i2c/README.md`:

> "The motherboard has an EEPROM chip built into it to store calibration
> information. The Calibration Wizard program writes all calibration data to
> this EEPROM chip. When the scanner interface software is launched, this
> calibration data in the EEPROM is written to the Windows registry."

So the vendor's architecture is: **EEPROM is the source of truth, the registry
is a cache, and the cache is refilled at every launch.** Confirmed in the
binary: `FN_bReadEEPromToRegistry` is called exactly once, from the
scanner-initialise path at `0x1000b2ae`, and writes
`HKLM\SOFTWARE\Pakon\TLB\Scan\DpiBase*_35\*`.

*(§5.0 corrects the identification recorded elsewhere in this project. It is
`fcn.10016a90`, **not** `fcn.100160a0`, and `0xA4` is a `bRequest`, **not** a
`wValue`. `backups/eeprom-i2c/README.md`, `docs/35` and `calib_verify.py` all
carry the older, wrong version.)*

We keep the same architecture with exactly one difference, forced on us by the
hardware: **our cache is filled once in a scanner's lifetime, not at every
launch.** These EEPROMs return good data on the first transaction after a power
cycle and degrade on every read after it while still reporting status `ok` —
measured on this unit, the second read of a cycle differed in 180 of 256 bytes
and the third read was entirely `0xFF`. So "refresh the cache at launch" is, on
this hardware, "destroy the calibration at launch".

Everything below follows from that one substitution.

---

## 2. What was built

| File | Status | What it does |
|---|---|---|
| `tools/calib_store.py` | extended | Serial index over the append-only store; per-unit overlays; the "which scanner is connected" pointer |
| `tools/calib_resolve.py` | **new** | The resolution state machine. Decides *which* scanner's calibration is in force. Cannot touch a device |
| `tools/calib_profile.py` | **new** | Decides *what numbers* follow from that. Decodes the matrices, merges the exposure overlay, labels every source. Cannot touch a device |
| `tools/calib_read.py` | edited | Connect report is now serial-aware and stops over-claiming identity |
| `tools/test_calib.py` | extended | 38 new checks; 141/141 pass |

### 2.1 `calib_store.py` — the serial index

The store was indexed by timestamp only. That is the right index while one
scanner is involved and the wrong one the moment a second has ever been read on
the same machine, because the newest read may belong to the other unit.

Added (all additive; no existing behaviour changed, nothing deletes):

- `ReadRecord.serial` — the unit this read came from, **trusted only from a
  read that passed the structural checks**. The serial lives at `0x0F` of the
  same page that degrades; on a degraded read those four bytes are corruption,
  and a corrupt `u32` makes a convincing-looking serial number. Believing one
  would invent scanners that do not exist and — far worse — could attribute a
  good read to the wrong unit.
- `ReadRecord.claimed_serial` — what the bytes say regardless. Display only, so
  a person can see *why* a read went unattributed.
- `units()`, `unit_index()`, `records_for_serial()`, `best_for_serial()`,
  `has_calibration_for()`.
- `select_unit()` / `active_unit()` — a pointer naming a serial, never
  calibration. Losing it costs a click.
- `save_overlay()` / `overlay()` / `overlays()` — per-unit values that are *not*
  on the page we can read (§4). Append-only, same as the reads, for the same
  reason: the value of an old record is that it is still there when the new one
  turns out to be wrong.

`best_for_serial()` returns the newest **good** read, not the newest read.
Within one unit the store may hold a later degraded read taken in a power cycle
that had already been used up; that read is evidence of what happened, not a
calibration to render with.

### 2.2 `calib_resolve.py` — which scanner

```
python3 tools/calib_resolve.py            what would be loaded, and why
python3 tools/calib_resolve.py units      the serial index
python3 tools/calib_resolve.py use 16275  say which scanner is connected
python3 tools/calib_resolve.py auto       go back to deciding automatically
```

---

## 3. The identity problem, stated honestly

The brief asks for lookup "given a connected scanner… by serial number". That
cannot be completed by asking the scanner, and the reason is worth writing down
because it constrains every design in this area:

**There is no per-unit identifier readable from this hardware before its EEPROM
has been read.**

- Every F-135 reports `iSerialNumber` **`010-203-04`**. The string is baked into
  the firmware descriptor and is byte-identical across `PknInit.hex`,
  `Pakon5.hex`, `Pakon7.hex` and `Pakon8.hex`
  (`docs/01-usb-layer.md`). It identifies the *model*, not the machine.
- The vendor's own `piScannerSerialNumber` (`docs/04-api-surface.md`) is fed
  from the registry, which was fed from the EEPROM. **The vendor has no
  pre-read identity either** — it simply re-reads, which is the one thing we
  cannot do.
- The serial itself lives at offset `0x0F` of the very page we are avoiding
  re-reading.

So the honest design is not "detect the serial and look it up". It is: **make
the question decidable from the store in every case where it has one answer,
and refuse to guess in the one case where it does not.**

### 3.1 The state machine

| Store contains | State | Action offered | Device touched |
|---|---|---|---|
| nothing | `no-calibration` | `prompt-read` | no |
| reads, none good | `unusable` | `attention` | no |
| exactly one unit | `ready` | `none` — **auto-load** | no |
| several units, no choice made | `ambiguous` | `choose-unit` | no |
| several units, choice made | `ready` (+ warning) | `none` | no |
| a serial hint we have never read | `unknown-unit` | `prompt-read` | no |

**Known scanner** (one unit stored — the overwhelmingly common case: one
person, one scanner): resolves straight to that unit's stored page, with zero
device traffic, on every launch forever. This is the whole point. Verified
against the live store:

```
$ python3 tools/calib_resolve.py
state    ready    action  none
Using scanner 16275's own calibration (2026-08-08T15-27-44Z). No read is needed.
Chosen because it is the only scanner this store has ever read.
```

**Unknown scanner**: `no-calibration` or `unknown-unit`, both of which produce
an explicit *prompt* and apply **nothing**. In particular an unknown serial is
never quietly given another unit's read — there is a test named exactly that
(`CRUCIALLY: an unknown scanner is not given another unit's read`).

**Ambiguity is never resolved by guessing.** With two units in the store the
resolver returns `ambiguous`, applies nothing, and asks. Guessing would mean
rendering someone's film through another scanner's colour matrix and lamp
calibration — which produces a plausible-looking, wrong picture. Choosing costs
one click; being wrong costs every scan until someone notices. When a choice
*has* been made the report still says so: *"Serial 20001 is in use because it
was chosen, not because it was detected."*

### 3.2 What would make true auto-detection possible

Listed so a future reader does not have to rediscover the dead ends:

- **Not** the USB serial descriptor — constant across all units (above).
- **Not** `piScannerSerialNumber` — EEPROM-derived, so circular.
- A per-unit value in a PICL/PICM register readable over the normal command
  protocol would do it. None is known; `tools/pakon_commands.py` documents no
  identity register on `AD_LIGHT`/`AD_MOTOR`. **UNRESOLVED** — settling it needs
  a survey of the read-only registers on both boards, which is device traffic
  and therefore out of scope here, though it is *ordinary* traffic and carries
  none of the EEPROM's read-once danger.

---

## 4. Making the stored calibration drive the pipeline

### 4.1 What is actually on the page, and what is not

Verified against the stored page (`calib_verify.py`, and re-derived
independently by `calib_profile.matrices_from_page`):

| Offset | Field |
|---|---|
| `0x0F` | scanner serial, `u32` LE (16275) |
| `0x25`–`0x9C` | `NegMatrix0..29`, 3×10 `float32` LE, row stride 40 |
| `0x9D`–`0xFF` | `PosMatrix0..23` — **truncated at 24 of 30 elements** by the page boundary |

That is the whole of it. The colour matrix genuinely comes from the device;
everything else the vendor stores per unit is on pages nothing here has read
(§5). The registry — being the vendor's own copy of the EEPROM — names them:
`MotorAdjust`, `MotorAdjustDrag(_Ir)`, `MotorSpeedPlus(_Ir)` and `Offset` per
DPI base, `StepperLens`, `StepperCCD`, and the per-mode lamp calibration
`Current_*`, `DutyCycle_*`, `DutyCycleOpenGate_*` for every DPI base × film
mode.

### 4.2 Two halves with different standing

`UnitProfile` therefore has two halves, deliberately kept apart:

- **`matrix_source`** — `device` when the coefficients came off this scanner's
  own page.
- **`config_source`** — `unit-overlay` (attached to this serial on purpose),
  `repo-reference` (`calibration/README.json`, *same* unit),
  `borrowed` (`calibration/README.json`, a **different** unit), or `missing`.

The failure this exists to prevent is the quiet one: handing a second owner's
scanner the first owner's lamp currents and calling the result "calibrated". A
borrowed exposure is a legitimate way to get a picture out of a new machine; it
is not that machine's calibration; and the difference must survive all the way
to the screen.

`calibration/README.json` is attributed to serial 16275 — its own prose records
that its lamp values were transcribed from that unit's vendor registry key
written 2022-11-10. The file carries no machine-readable serial, so
`calib_profile.REFERENCE_SERIAL` supplies the attribution (from
`calib_verify.OWNER_SERIAL`), and an explicit top-level `"unit_serial"` wins if
the file ever grows one. **No regex over the prose** — a regex over an English
sentence is not attribution.

Borrowing is offered rather than withheld: refusing outright would leave a new
owner unable to scan at all, and the values are inside the hardware's own
clamps, so the cost of borrowing is a mis-exposed frame, not a damaged lamp.
But it is labelled `borrowed` in the returned dict, in the CLI, and in a
warning written for a person to read.

### 4.3 Verified parity for the current unit

The new path produces **byte-identical** coefficients to the existing one, so
adopting it is a no-op for this unit and a correction for anyone else:

```
profile().matrix(1) == pakon_color.load_matrix_eeprom(film_class=1) → True
profile().matrix(2) == pakon_color.load_matrix_eeprom(film_class=2) → True
stored page sha256 == repo backups/eeprom-i2c/eeprom_52.bin sha256 → True
  675cf1cff78a2e0f4b7f115a08197d0318cd8594dd2e643e287efbf2020cb436
negative diagonal 0.289202 0.275831 0.278237  ← matches the render's own log
pedestals 159.594 444.750 635.535             ← matches calib_verify.OWNER_PEDESTALS
```

### 4.4 Adopting the current unit's exposure into the store

```
python3 tools/calib_profile.py adopt
```

copies the `config` block **out of** `calibration/README.json` into
`<store>/units/16275/overlay/<stamp>.json`, with provenance recorded. From then
on the exposure half is per-serial exactly as the colour half already is, and
the checkout stops being load-bearing. It never writes to `calibration/`.

**This has not been run against the live store** — it is a state change the
owner should make deliberately, and `calibration/README.json` was hand-edited
on 2026-08-12 (the `on_counts_R_G_B` duty fix), so the moment to snapshot it is
the owner's call, not mine. The fallback chain means the current unit works
identically either way.

---

## 5. EEPROM addressing beyond byte 255 — **RESOLVED**

Static analysis of `research/native/TLB.text.asm` (private, 124,205 lines). No
hardware was touched. Every VA below was spot-checked verbatim in that file;
every arithmetic claim was re-derived locally from
`backups/eeprom-i2c/eeprom_52.bin` and `research/windows-registry/pakon_registry_full.txt`.

### 5.0 Two corrections to previously recorded facts

`backups/eeprom-i2c/README.md`, `docs/35` and `calib_verify.py` all state that
`FN_bReadEEPromToRegistry` is `fcn.100160a0` and "pushes `wValue 0xA4`". **Both
halves are wrong**, and the error is what made the addressing look unsolvable.

TLB.dll's error reporter `fcn.1001acd0` is called as `(…, push <FN_id>, …)`,
and `research/sdk/TLB.tbl.dis.txt` gives the id → name table:

```
0x10016bad   680e010000   push 0x10e      ; 270   (inside fcn.10016a90)
0x10018798   68f0230610   push str.FN_bReadEEPromToRegistry     ; case 270
0x10017e64   689c380610   push str.FN_bEEPromRead               ; case 140
```

| Was believed | Actually |
|---|---|
| `FN_bReadEEPromToRegistry` = `fcn.100160a0` | **`fcn.10016a90`** |
| `fcn.100160a0` | **`FN_bEEPromRead`** (id 140) |
| `0xA4` is a `wValue` | **`0xA4` is a `bRequest`** (`0x10016175: push 0xa4`) |

The `0xA4 ≈ 0x52 << 1` coincidence is real but incidental: the 8-bit I2C
address does appear, as the *`wValue`* of the `0xA4` request, and it is `0xA5`
(read direction), not `0xA4`.

### 5.1 The mechanism: a flat 16-bit byte offset in `wValue`

`fcn.100160a0` (`FN_bEEPromRead`, `__thiscall`, 6 args, `ret 0x18`):

```
0x100160bc      3d00200000     cmp eax, 0x2000    ; offset      <  8192, else EC 0x7d
0x100160e6      3d00200000     cmp eax, 0x2000    ; offset+len <= 8192, else EC 0x7c
0x10016112      83f807         cmp eax, 7         ; device index <= 7,   else EC 0x7a
0x10016138      83c850         or eax, 0x50       ; 7-bit addr = 0x50 | index
0x1001613b      d1e0           shl eax, 1         ; 8-bit addr
```

then a two-request loop in 32-byte chunks:

```
; request 1 -- "select device", vendor/OUT, re-issued before EVERY chunk
0x1001616c      6a00           push 0        ; wLength = 0
0x1001616f      6834120000     push 0x1234   ; wIndex  = 0x1234  (constant)
0x10016174      50             push eax      ; wValue  = 8-bit I2C address (0xA5)
0x10016175      68a4000000     push 0xa4     ; bRequest = 0xA4

; request 2 -- the data phase, vendor/IN
0x100161a0      56             push esi      ; wLength = chunk (<= 32)
0x100161a2      6834120000     push 0x1234   ; wIndex  = 0x1234
0x100161a7      51             push ecx      ; wValue  = EEPROM BYTE OFFSET
0x100161a8      52             push edx      ; bRequest = 0xA9
0x100161af      6a01           push 1        ; direction = IN
```

So:

- **`wIndex` is not the offset.** It is the literal `0x1234` at all four call
  sites (`0x1001616f`, `0x100161a2`, `0x100162ff`, `0x10016332`) — a magic
  guard value.
- **`wValue` of the `0xA9` request carries a flat 16-bit byte offset.** There
  is no host-side page select, no `shr … 8`, no `and 0xff`. The host hands the
  firmware a linear address and the FX2 does whatever I2C word addressing the
  part needs.
- The host's own bound is **`0x2000` = 8192 bytes**, and the 32-byte chunking
  matches the 32-byte write page of a 24C32/24C64 (a 24C16 has 16-byte pages).

### 5.2 Where the data actually lives

`fcn.10016a90` = `FN_bReadEEPromToRegistry`, called once from the
scanner-initialise path (`0x1000b2ae`). Its stack locals are the whole answer:

```
0x10016aa7  mov dword [esp+0x18], eax    ; 0x400  maxlen A
0x10016add  mov dword [esp+0x28], eax    ; 0x200  maxlen B
0x10016ac5  mov dword [esp+0x30], 0      ; offset A primary = 0x000
0x10016aa3  mov dword [esp+0x2c], eax    ; offset A backup  = 0x400
0x10016acd  mov dword [esp+0x38], 0x800  ; offset B primary = 0x800
0x10016ad5  mov dword [esp+0x3c], 0xa00  ; offset B backup  = 0xa00
0x10016abe  push 0x18e                   ; 398
0x10016d4a  cmp ecx, 0x24                ; 36
```

| Section | Bytes | Primary offset | Backup offset |
|---|---|---|---|
| A | 398 (`0x18E`) | `0x000` | `0x400` |
| B | 36 (`0x24`) | `0x800` | `0xA00` |

Highest byte touched = `0xA00 + 36` = **`0xA24` = 2596**.

**This settles it.** 2596 > 2048, so the calibration part cannot be a 24C16
with device-select paging, and it is certainly not a 256-byte device. It is a
single device at 7-bit `0x52` of **at least 4 Kbit (24C32), addressed with a
2-byte word address**, and the vendor keeps **two copies of everything** —
section A at `0x000` with a backup at `0x400`, section B at `0x800` with a
backup at `0xA00`.

**The "further pages appear as 0x53, 0x54…" hypothesis is refuted.**
`docs/35 §2`, `calib_verify.cross_page_checks()` and `read.json`'s
`cross_page` note all assume device-select paging. There is none. The bytes
past 255 are at ordinary offsets behind the *same* address `0x52`. That is also
why `0x53` does not ACK on this unit and why that is *not* evidence of a
truncated device.

### 5.3 Section format and CRC

`fcn.100163c0` = `FN_bEEPromReadSection` reads an 8-byte header at `offset`,
then `length-8` payload bytes at `offset+8`:

```
0x100163e0      6a02           push 2       ; device index 2 -> 0x52 (hardcoded)
0x100163e2      6a08           push 8       ; 8-byte header
0x100163f8      mov ecx, [esp+0x10]         ; header dword0 = stored length
0x10016453      mov edx, [esp+0x14]         ; header dword1 = stored CRC32
0x1001645b      add ecx, 0xfffffff8         ; payload len = length - 8
0x10016465      add ebp, 8                  ; offset += 8
0x1001643d      or ecx, 1                   ; flags bit0 = BLANK
0x100164d8      or dword [eax], 2           ; flags bit1 = CRC BAD
```

Header = `{u32 length; u32 crc32;}`. **The CRC covers the payload only** —
bytes `[offset+8 … offset+length-1]`, excluding the header.

`fcn.10015d30` is the CRC: table of 256 entries built at runtime from the
forward polynomial `0x04C11DB7` (`0x1001604d: and esi, 0x4c11db7`;
`0x1001608a: cmp eax, 0x100`), init `0xFFFFFFFF`, final `NOT` — i.e. **the
standard reflected zlib/PKZIP CRC-32** (`0xEDB88320` equivalent; the literal
never appears). Ranges: section A → `0x008..0x18D` (390 bytes); section B →
`0x808..0x823` (28 bytes).

`calib_verify.crc_status()`'s note that a 7-variant search found nothing was
correct and is now explained: we hold 255 of the 390 section-A payload bytes,
and we hold them **off by one** (§5.5).

### 5.4 Registry field → EEPROM offset map

Unpackers: `fcn.10016860` (splits sections into per-DpiBase structs),
`fcn.10016610` (per-base scalars), `fcn.1000e890` (30-float matrices). Value
names from `fcn.10010430` / `fcn.1000cf80`. Root key
`HKLM\SOFTWARE\Pakon\TLB\Scan\DpiBase{4,8,16}_35\`.

Offsets are **absolute EEPROM byte addresses** (see §5.5 for the file-offset
conversion).

| EEPROM | Type | Registry value |
|---|---|---|
| `0x000` | u32 | section-A length (398) |
| `0x004` | u32 | section-A CRC32 → `0xF159370C` on this unit |
| `0x008` | u32 | → object `+0x70` — **name unresolved**, value 400 |
| `0x00C` | u32 | → object `+0x6c` — **name unresolved**, value 1351 |
| `0x010` | u32 | **scanner serial number** (16275) |
| `0x014/016/018` | 3×u16 | `DpiBase4_35\` **Offset / MotorSpeedPlus / MotorSpeedPlus_Ir** |
| `0x01A/01C/01E` | 3×u16 | `DpiBase8_35\` same three |
| `0x020/022/024` | 3×u16 | `DpiBase16_35\` same three |
| `0x026..0x09D` | 30×f32 | **NegMatrix0 … NegMatrix29** |
| `0x09E..0x115` | 30×f32 | **PosMatrix0 … PosMatrix29** |
| `0x116..0x18D` | 120 B | **UNMAPPED** — inside section A and inside its CRC, but `FN_bReadEEPromToRegistry` never reads it. 120 bytes is exactly the size of a third 30-float matrix |
| `0x800` | u32 | section-B length (36) |
| `0x804` | u32 | section-B CRC32 |
| `0x808/80A/80C/80E` | 4×u16 | `DpiBase4_35\` **MotorAdjust / MotorAdjustDrag / MotorAdjust_Ir / MotorAdjustDrag_Ir**, clamped 900–1100 |
| `0x810/812/814/816` | 4×u16 | `DpiBase8_35\` same four |
| `0x818/81A/81C/81E` | 4×u16 | `DpiBase16_35\` same four |
| `0x820` | u32 | → object `+0x68` — **name unresolved** |

**Not on the EEPROM at all:** `StepperLens`, `StepperCCD`, and *everything*
lamp-related — `Current_*`, `DutyCycle_*`, `DutyCycleOpenGate_*`, `Gain_*`,
`Offset_*` per DPI base × film mode. `fcn.10010430` reads `StepperLens`/
`StepperCCD` from object offsets `+0x4c`/`+0x50`, which no EEPROM unpacker
writes.

> **This is the single most important consequence for §8.** The per-mode lamp
> calibration — the thing a second owner most needs and the thing
> `calibration/README.json` is mostly made of — is **not recoverable from the
> EEPROM at any offset**. It is written to the registry by the Calibration
> Wizard and lives only there. A full multi-page read would recover the motor
> constants, the serial and the matrices; it would **not** recover the lamp
> values.

### 5.5 The stored dump is off by one — **verified locally**

`eeprom_52.bin[k] = EEPROM[k + 1]`. Four independent confirmations, all
re-derived here from the bytes rather than taken on trust:

| Anchor | File | EEPROM | Check |
|---|---|---|---|
| section-A length | `[0x00..0x02]` = `01 00 00` | `[0x01..0x03]` | prefix the unseen `0x8E` → `0x0000018E` = **398** ✓ |
| serial | `[0x0F]` u32 = **16275** | `[0x10]` | `0x10016868: mov eax, [edi+0x10]` reads exactly there ✓ |
| motor triples | `0x13 / 0x19 / 0x1F` | `0x14 / 0x1A / 0x20` | `fcn.10016860` puts them at `0x14/0x1A/0x20` ✓ |
| NegMatrix0 / PosMatrix0 | `0x25` / `0x9D` | `0x26` / `0x9E` | `0x10016d91: lea eax,[ebx+0x18ea]` = secA+0x26; `0x10016da7: add ebx,0x1962` = secA+0x9E ✓ |

The motor check is decisive because it is nine independent numbers matching the
registry hive exactly:

```
file 0x13 (EEPROM 0x14)  DpiBase4_35   Offset=27  MotorSpeedPlus=25802  _Ir=19335
file 0x19 (EEPROM 0x1a)  DpiBase8_35   Offset=54  MotorSpeedPlus=11467  _Ir=7580
file 0x1f (EEPROM 0x20)  DpiBase16_35  Offset=55  MotorSpeedPlus=5917   _Ir=4850
```

— identical to `pakon_registry_full.txt` for all three keys.

**The cause, strongly indicated:** `fx2/eeprom_dump_bus.c`'s `dump()` does

```c
(void)I2DAT;                     /* starts the first byte */
for (i = 0; i < 256; i++) { s = wd(); out[i] = I2DAT; }
```

On this FX2 the first data byte is already shifting in when `DONE` rises after
the read-direction address ACK, so the "priming" dummy read **consumes
`EEPROM[0]`** and starts byte 1. One dummy read too many. Confirming the
mechanism (as opposed to the shift, which is proven) needs a bus capture, so
it is recorded as indicated, not proven.

> ### ⚠ Landmine for whoever fixes this
> `calib_verify.SERIAL_OFF = 0x0F`, `NEG_MATRIX_OFF = 0x25`,
> `POS_MATRIX_OFF = 0x9D` and `pakon_color.EEPROM_FLOAT_BASE = 1` are all
> **correct for images produced by the current firmware** and become **wrong by
> one byte** the moment the dummy read is removed. They were left unchanged —
> changing them now would break the only good read that exists. Any firmware fix
> must land together with a version marker on the stored image so both
> alignments can be decoded.

Two further consequences:

- **This unit is definitively serial 16275.** `docs/37`'s open action ("read
  the serial off the physical scanner… if it happens to be 16275, the
  2022-11-10 registry values are this scanner's") is now answered from data
  already on disk, with a far stronger proof than the serial field alone: nine
  motor/offset values agree byte-for-byte between this unit's EEPROM and the
  hive. `calibration/README.json`'s reasoning was right.
- **The last six PosMatrix coefficients are not on another device.** They are
  at EEPROM `0x0FE..0x115`, just past the 256-byte window, behind the same
  address `0x52`.

### 5.6 Procedure for a future full read — FOR HUMAN REVIEW, DO NOT RUN

Not implemented, deliberately. It requires a new FX2 firmware and therefore a
new pinned hash, and it spends the one good read of a power cycle.

1. **Fix the off-by-one first**, or the whole image is misaligned. Decide
   whether to remove the priming read or to read 257 bytes and drop the last;
   verify against a *stored* image, never against the hardware.
2. **Write a 2-byte-word-address read.** The current `dump()` sends a single
   `I2DAT = 0x00`. A 24C32/64 needs two address bytes, high then low, with no
   STOP before the repeated START. All three write-impossibility properties of
   the current firmware must be preserved: exactly N address stores and **no
   data byte store**, no STOP between address and repeated start, and the
   address must be a compile-time constant with no host mailbox.
3. **Read `0x000..0xA24` (2596 bytes) from `0x52` in ONE pass**, sequential —
   one START, one address phase, 2596 sequential reads, one STOP. Degradation
   is per-transaction, and the existing evidence for that is `eeprom_dump_all.c`
   having read `0x51` then `0x52` in a single pass with both files reproducing
   byte-identically from a separate power cycle. **Do not** read the four
   sections as four separate transactions.
4. Keep reading `0x50..0x57` at 256 bytes each as today, for the boot
   personality and for other owners' units. Read `0x52` *last*, at full length,
   so a failure in the cheap part does not cost the expensive one.
5. **Verify by CRC, not by re-reading.** This is now possible and it is the
   real prize: zlib CRC-32 over `[0x008..0x18D]` must equal the u32 at `0x004`,
   and over `[0x808..0x823]` must equal the u32 at `0x804`. A validating CRC is
   a far stronger verdict than the six structural checks, and it costs nothing.
   If the primary fails, the backups at `0x400` and `0xA00` are a second chance
   **already in the same image** — no second read.
6. Everything else — the power-cycle guard, the lock, the save-before-interpret
   ordering, the append-only store — is unchanged and must stay.

### 5.7 Still unresolved

1. **Wire-level I2C word-address width.** TLB.dll hands the firmware a flat
   16-bit offset; the split into I2C bytes happens inside the FX2. Arithmetic
   forces 2-byte (offsets reach `0xA24`), but the wire form is not proven.
   *Needs:* the 8051 firmware implementing vendor requests `0xA4`/`0xA9`, or a
   USB capture of the vendor software.
2. **`wIndex = 0x1234`.** Constant at all four sites; a guard or magic value.
   Only the firmware can confirm.
3. **Three unnamed scalars** — section A `+0x008` (=400) and `+0x00C` (=1351),
   section B `+0x820`. *Needs:* the accessor pair for the class at `ebx+0x458`
   offsets `0x68/0x6c/0x70`.
4. **The 120-byte block at `0x116..0x18D`** — inside section A and inside its
   CRC, never consumed by `FN_bReadEEPromToRegistry`. Same size as a third
   30-float matrix. *Needs:* whichever function reads `ebx+0x18c4 + 0x116`.
5. **`bRequest 0xA2`** (the `a3 == 0` branch at `0x10016147`) is dead in
   TLB.dll — no call site passes `a3 == 0`.
6. **The mechanism of the off-by-one** (§5.5) — proven as an effect, indicated
   as a cause.

### 5.8 The bus, address by address

Ground truth for this unit is `fx2/eeprom_dump_bus.c`'s own header — *"On the
owner's unit the bus scan ACKed at 0x51 and 0x52 only"* — and
`backups/eeprom-i2c/README.md`: *"Two chips on the scanner's I2C bus, both on
the motherboard."*

> **Caveat on the stored read.** `read.json`'s status word
> `0100000101010101…` is the **simulator's**, not the hardware's — the record's
> `source` is `calib_read --simulate` (§6.1), and the simulator was given only
> two devices. It is *consistent with* the hardware scan but is not independent
> evidence of it. The hardware evidence is the two sources quoted above.

| addr7 | This unit | TLB.dll | Size / addressing | Replaceable? |
|---|---|---|---|---|
| `0x50` | absent | **never addressed** | no evidence | — |
| `0x51` | present, **erased** (239/256 = `0xFF`) | **never addressed** — the FX2 silicon reads it at power-up, not the host driver | 9-byte C0 load; 1-byte word address (24LC00/24C01/24C02 class). Not confirmed — TLB never touches it | **Yes.** Correct contents documented: `c0 05 0f 35 f2 07 aa 04 02` |
| `0x52` | present, **good** | the **only** device it reads or writes — `push 2` hardcoded at `0x100163e0`, `0x10016457`, `0x10016535`, `0x10016548` | ≥4 Kbit (24C32), **2-byte word address**, 32-byte pages; host bound 8192 B, highest offset used `0xA24` | **NO. Irreplaceable.** Serial, three DpiBase optical offsets + motor speeds, twelve clamped motor-adjust words, 60 float32 matrix coefficients. `F135_SM.txt` p.10: the Calibration Wizard is the only writer |
| `0x53`–`0x57` | absent | **never addressed** | no evidence | — |

The device index is fully parameterised in the code (`cmp eax, 7` then
`or eax, 0x50`), so TLB.dll *can* address `0x50`–`0x57` — but every one of the
four call sites passes index 2. **The vendor never addresses anything but
`0x52`.** For another owner's scanner that means `0x50` and `0x53`–`0x57`
carry no vendor meaning; `0x51` may well be *intact* rather than erased, and
capturing it is genuinely valuable, which is why `calib_read.py` reads the
whole range and should keep doing so.

Mitigation note for `0x52`: everything `FN_bReadEEPromToRegistry` actually
consumes is also present, verified identical, in
`research/windows-registry/pakon_registry_full.txt` — **except** the two
unnamed section-A dwords, the section-B dword, and the unmapped 120-byte block.

---

## 6. How no automatic device read can happen

Four independent barriers, in increasing order of how hard they are to remove.

**1. The lookup path has no device in reach — structurally, not by discipline.**
`calib_resolve.py` and `calib_profile.py` import only the standard library,
`calib_store` and `calib_verify`. They do not import `usb`. They do not import
`calib_device`. They take no transport argument. There is no object in either
module through which a control transfer could be issued. This is the same
property `calib_verify.py` has, and it is now enforced by a test that parses
both files' ASTs (not their text — these files *discuss* `calib_device` at
length in their docstrings, and a grep-based test would either fail or be
silenced by deleting the explanation).

**2. A stronger runtime proof.** `test_lookup_cannot_reach_a_device` launches a
clean interpreter, imports `calib_profile`, resolves a profile, and asserts that
neither `usb` nor `calib_device` is in `sys.modules` afterwards. A module that
was never imported cannot have issued a transfer.

**3. No code path decides to read.** `resolve()` returns an `action`, and the
strongest value it can ever return is `prompt-read` — a suggestion for a button.
Every returned dict carries `may_auto_read: False` and
`device_read_performed: False`, asserted on every branch by the tests. The only
function in the subsystem that reads is `calib_read.do_read`, it is only ever
called from an explicit `read` subcommand, and none of the new code calls it.

**4. The existing guards are untouched and still hold.** `do_read`'s ordering,
its refusal when a calibration is stored, `PowerCycleGuard.check()`'s fail-safe
rule, `--force` being *stricter* (demanding a witnessed power cycle) rather than
weaker, `ReadLock`, the pinned-firmware hash, the `assert_safe_installation()`
quarantine check, and the append-only store were **not modified**. All 103
pre-existing checks still pass alongside the 38 new ones.

One correctness note about the existing guard, deliberately *not* changed:
`do_read` refuses when `store.has_calibration()` is true — i.e. when *any*
scanner has been read — not when *this* scanner has. For a second owner on a
machine that already holds unit A's calibration that is a false refusal. It is
the right default (it fails safe), the refusal text already names the remedy
("a different scanner… pass `--force`"), and `--force` still requires a
witnessed power cycle. Weakening it to `has_calibration_for(serial)` is
impossible anyway, because knowing the serial requires the read. Left alone on
purpose.

### 6.1 An honest note about the stored record's provenance

The store's good record `2026-08-08T15-27-44Z` has `"source": "calib_read
--simulate"`. It is a **rehearsal** record — the 2026-08-08 bug that
`calib_read.open_store()`'s docstring describes, now fixed and regression-tested,
but the record it produced is still the one in force.

Its *bytes* are genuine: the rehearsal transport is fed
`backups/eeprom-i2c/eeprom_52.bin`, which is itself two byte-identical first
reads from separate power cycles, and the stored page's SHA-256 matches that
backup exactly (§4.3). So the values are real and the serial is right. But the
record is not itself evidence that this scanner was read.

`calib_resolve` now surfaces this as a warning on every `status` and every
resolve, rather than leaving it to whoever next opens `read.json`. **No action
is recommended** — re-reading to "get a proper record" would be exactly the
instinct this subsystem exists to suppress, and would risk the only copy that
exists to improve a metadata string.

---

## 7. Backend / UI wiring — specification, not implementation

`tools/pakon_app.py` and `app/src/` are being edited concurrently, so this is a
spec. The endpoints already exist — `GET calibration`, `POST calibration/read`,
`POST calibration/select` — so these are **extensions to existing functions**,
not new routes. Every guard to reuse is named.

### 7.1 `calibration_store_state()` — add the resolution and the profile

This is the disk-only function, and its existing contract ("Disk only. Safe to
call as often as the UI likes") is exactly the contract `calib_resolve` and
`calib_profile` were built to satisfy. Add inside the existing `try`, after
`sel = store.selection()`:

```python
import calib_profile as cprof          # add to the defensive import block
import calib_resolve as cres           # alongside calib_read/calib_store

        rep = cres.resolve(store)       # no transport: none exists in here
        prof = cprof.profile(store)
        return {"available": True, "store": str(store.root),
                "have_calibration": store.has_calibration(),
                "selection": sel,
                "resolution": rep,                    # NEW
                "profile": prof.to_json(),            # NEW
                "units": store.unit_index()}          # NEW
```

Both new calls are pure disk reads, so the "must never cause USB traffic"
property of this function is preserved — and now enforced by
`test_lookup_cannot_reach_a_device`, which proves the modules cannot import a
transport at all. Add them to the defensive import block so a failure degrades
to `available: False` exactly as today.

**Invariant for the endpoint:** `resolution.device_read_performed` and
`resolution.may_auto_read` are `False` in every response. If either is ever
true, something has been wired wrongly.

### 7.2 `calibration_state()` — one branch to add

The existing early-out is:

```python
    if out.get("have_calibration") or out["scan_running"]:
        out["action"] = "none" if out.get("have_calibration") else "busy"
        return out
```

`have_calibration` is true when *any* scanner has been read, so with two units
stored this returns `action: "none"` and the UI silently uses whichever the
selection points at. Add the ambiguity check before it:

```python
    if out["resolution"]["state"] == cres.AMBIGUOUS and not out["scan_running"]:
        out["action"] = "choose-unit"      # still no USB touched
        return out
```

Everything else stays. `connect_report()` — which is what runs when nothing is
stored — is already updated and now returns `action: "choose-unit"` in the same
situation, so the two paths agree.

### 7.3 `calibration_select()` — accept a serial as well as a stamp

Extend the existing handler rather than adding a route:

```python
    if "serial" in body:
        s = body.get("serial")
        if s is not None and not store.has_calibration_for(int(s)):
            return {"error": f"no good stored calibration for scanner {s}"}
        store.select_unit(None if s is None else int(s))
        return calibration_store_state()
    # ... existing stamp handling unchanged
```

Never create a unit by naming it: an unknown serial is an error, not an
instruction. `select_unit` writes a pointer file and deletes nothing, matching
`select()`'s existing guarantee.

### 7.4 `calibration_read()` — leave it exactly as it is

It is already correct and must not be touched. It reuses, in this order:

1. `SCAN.running()` — refuses while a scan owns the interface.
2. `calib_device.assert_safe_installation()` (inside `do_read`) — refuses if
   `tools/i2c_eeprom.hex` (write-capable) has been un-quarantined.
3. `calib_device.firmware_ok()` — pinned SHA-256 of `fx2/eeprom_dump_bus.ihx`.
4. `calib_read.do_read(...)` — which takes `calib_device.ReadLock`, consults
   `PowerCycleGuard.check()`, stamps the read-once marker *before* the 8051 is
   released, writes bytes to disk before interpreting them, and salvages from
   FX2 RAM rather than re-reading.

**Do not** add a retry, a timeout-retry, a "verify by reading again", or any
call to `calibration_read` from a polling loop, a health check, a reconnect
handler, a bootstrap or a startup path. It is reached only from
`POST calibration/read`. `force` must come from an explicit user gesture and
must never be defaulted true.

### 7.5 UI states

Drive purely off `action`:

| `action` | UI |
|---|---|
| `none` | Show `serial`, `stamp`, and the two `this_units_own` badges. No control. |
| `prompt-read` | An explicit button. Copy comes from `headline`/`reason`. Must state that the read happens once and requires a power cycle first. |
| `choose-unit` | A picker over `serials`. **No default selection** — a pre-selected radio is a guess wearing a choice's clothes. Posts to §7.2. |
| `attention` | Show `reason`. **Must not** offer "read again" as the remedy. |

`warnings[]` must be rendered wherever the calibration is shown, not hidden
behind a details pane. The two that matter most —
`profile.config.source == "borrowed"` and the rehearsal-provenance note — are
the ones a person needs to see before they trust a render.

### 7.5 Pipeline wiring — `pakon_scan.py` and `pakon_color.py`

Not applied: `pakon_scan.py` carries large uncommitted work and was out of my
edit scope. Both changes are small and additive.

**`pakon_scan.py` — `ScanConfig`.** Split the existing method so the file read
and the interpretation are separable, then add a store-backed entry point:

```python
@classmethod
def from_calibration(cls, cal_dir=None, *, config=None, source=None, **kw):
    if config is None:
        p = (Path(cal_dir) if cal_dir else _ROOT / "calibration") / "README.json"
        if not p.is_file():
            raise ScanRefused(...)                    # unchanged text
        config, source = (json.loads(p.read_text()).get("config") or {}), str(p)
    # ... the rest of the body unchanged, reading `config` instead of `c`
    #     and `source=source` instead of `source=str(p)`

@classmethod
def from_store(cls, serial_hint=None, **kw):
    """This scanner's own exposure if the store has it; the repo reference
    otherwise, clearly labelled."""
    import calib_profile as cprof
    prof = cprof.profile(serial_hint=serial_hint)
    if prof.config_source == cprof.FROM_NOTHING:
        return cls.from_calibration(**kw)             # unchanged fallback
    cfg = cls.from_calibration(config=prof.config,
                               source=prof.config_origin, **kw)
    cfg.warnings.extend(prof.warnings)
    return cfg
```

`from_calibration()` with no keywords behaves exactly as today, so every
existing caller and test is unaffected.

**`pakon_color.py` — `load_unit_matrix`.** Add a `'store'` source and change
only the case that is currently wrong:

```python
def load_unit_matrix(source="auto", film_class=1):
    if source in ("auto", "store"):
        import calib_profile as cprof
        prof = cprof.profile()
        # 'auto' keeps preferring the committed registry values for THIS unit,
        # because a byte-accurate replay must use what TLB actually loaded at
        # runtime (docs/58 §4.4) -- the %f-rounded REG_SZ strings, not the
        # higher-precision EEPROM floats. That reasoning only applies to the
        # unit the registry came from. For any other scanner the registry is
        # someone else's machine and the store is the only correct source.
        if prof.matrix_source == cprof.FROM_DEVICE and (
                source == "store" or prof.serial != cprof.REFERENCE_SERIAL):
            return prof.matrix(film_class)
    # ... existing registry / eeprom chain unchanged
```

This preserves every existing golden-parity result byte-for-byte for serial
16275 (verified identical in §4.3) while fixing the second-owner case, where
`REGISTRY_PATH` does not exist at all and `EEPROM_PATH` is the *first* owner's
page.

**`pakon_gate.py` — not wired, and cannot be.** `Gate.from_calibration()` loads
`dark_2000x3.npy` and `gain_2000x3.npy`. Those are *measured* flat-field tables,
not EEPROM contents — see §8.

---

## 8. What remains before another owner's scanner works end to end

Ordered by how much stands between here and a correct scan on a second unit.

1. **The flat-field tables are per-unit and are not on the EEPROM.**
   `calibration/dark_2000x3.npy` and `gain_2000x3.npy` were *measured* on this
   unit's CCD, lamp and optics. `Gate.from_calibration()` requires them and
   raises without them. No amount of EEPROM reading produces them: a second
   owner needs a dark/bright capture run of their own, stored per serial
   alongside the overlay. **This is the largest remaining gap** and it is a
   capture-and-storage problem, not a reverse-engineering one.
2. **The lamp calibration is on NO EEPROM page — this is worse than it looked.**
   §5.4 establishes that `Current_*`, `DutyCycle_*`, `DutyCycleOpenGate_*`,
   `Gain_*` and `Offset_*` per DPI base × film mode are **never written to the
   EEPROM by any code path in TLB.dll**. They are Calibration Wizard output
   that lives only in the Windows registry. A full multi-page read will recover
   the serial, the motor constants and the matrices; it will **not** recover
   these. So a second owner's routes are exactly two:
   *(a)* their own registry export, if the unit ever ran the vendor software —
   `calib_profile.py adopt --from <file>`; or *(b)* measuring their own, which
   is the same job as item 1. The `borrowed` label is therefore not a temporary
   state pending a better read; for lamp values it is the permanent honest
   answer until someone measures.
3. **The motor constants and the serial ARE recoverable** — at EEPROM
   `0x014..0x024` and `0x808..0x81E`, behind address `0x52` with 2-byte
   addressing (§5.2). Worth doing: they are per-unit, irreplaceable, and
   currently unread. Procedure in §5.6, not implemented.
4. **Reversal film is short six coefficients.** `PosMatrix24..29` are at EEPROM
   `0x0FE..0x115` — just past the 256-byte window, behind the *same* address
   `0x52`, **not** on a device at `0x53` as previously assumed. They come back
   with the read in §5.6. Colour negative is complete and unaffected.
5. **`calib_read.py`'s reference to `docs/60-calibration-safety.md`** — that
   file exists on neither remote, yet is cited **8 times across 5 files**
   (`calib_verify.py`, `calib_store.py`, `calib_read.py`, `calib_resolve.py`,
   `pakon_app.py`). The reasoning it is cited for is fully reproduced in those
   modules' own docstrings and in `backups/eeprom-i2c/README.md`, so nothing is
   lost — but a new reader following the citation finds nothing. Either write
   it or repoint the citations.
6. **A second owner's first read is the dangerous moment.** All the machinery
   is in place and tested against the simulator, but it has been exercised for
   real exactly once. The prompt copy must make the power-cycle requirement
   unmissable *before* the button, not in an error afterwards.
7. **Optional: true auto-detection** (§3.2) — a survey of read-only PICL/PICM
   registers for anything per-unit. Would remove the `ambiguous` state
   entirely. Ordinary command traffic; none of the EEPROM's danger.
