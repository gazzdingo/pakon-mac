# U34 (PICM) full device read — 2026-08-06

**U34 IS NOT DEAD.** Every earlier ICSP failure was the physical connection.
With a better connection it reads first time: `PIC18F452 found, Revision ID 7`.

Six reads taken; **five agree** (A,C,D,E,F, sha256 `c786015bd268e542…`).
Pass B differed in 32354 bytes across the whole range — a mid-read connection
loss — and is excluded. Majority content is what is stored here.

## THE FAULT, FOUND

```
Application vs nm0506.HEX: 10616 bytes compared, 64 MISMATCH
Range 0x000D00 - 0x000D3F   chip reads 0xFF, vendor has code
```

**Exactly one 64-byte row, erased.** That is the signature of a PIC18 row erase
— 64-byte aligned, exactly 64 bytes, blank where code should be.

`0xFFFF` executes as a NOP on PIC18, so the chip runs through 64 bytes of NOPs
and whatever initialisation lived at `0x0D00` never happens.

**Every critical word is INTACT:**

| Address | Expected | Read | Meaning |
|---|---|---|---|
| `0x000400` | `EFE1` | `EFE1` | reset vector |
| `0x001A8C` | `0E36` | `0E36` | `MOVLW 0x36` → SSPCON1, SSPEN=1 |
| `0x001A90` | `C134` | `C134` | `MOVFF 0x134,SSPADD` |
| `0x002C62` | `0E44` | `0E44` | the I²C slave address |
| `0x002C64` | `0101` | `0101` | `MOVLB 1` |
| `0x002C66` | `6F34` | `6F34` | `MOVWF 0x134` |

So the MSSP arming code was never damaged. **This is repairable by reflashing.**

## Also recovered

**PICM's OWN bootloader**, 705 non-0xFF bytes in `0x0000`–`0x03FF`:
```
0x0000  GOTO 0x00003c
0x0008  GOTO 0x000408     app_base + 8   (PICM app base is 0x400)
0x0018  GOTO 0x003d00
```
This supersedes the adapted PICL bootloader in `build/` — we now have the real
thing rather than a patched copy.

## Config and EEPROM

```
chip  : 00 26 06 09 00 01 81 00 0f c0 0f e0 0f 40
nm0506: 00 26 06 0d 00 01 81 00 0f c0 0f e0 0f 40
                  ^^ CONFIG2H differs: chip 0x09, vendor 0x0D (WDT postscale)
```
U11 also reads `0x09`. **Kodak evidently programs `0x09` regardless of what the
HEX specifies — use the chip's own value, not the file's.**

Internal EEPROM: `aa ff 00 00 00 00 00 ff ...`
* index 0 = `0xAA` — application valid
* index 5 = `0x00` — **no persisted fault code**

## Provenance

PICkit 3 serial `BUR195068601`, firmware suite 01.56.09, MPLAB X v5.50,
`ipecmd -P18F452 -TPPK3 -OD -GF`. Read through JM11.
