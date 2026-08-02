# 13 — Boot EEPROM: damage and repair

## What happened

While sweeping writes across unidentified "board addresses" hunting for the
lamp, those addresses turned out to be **I2C addresses**. `0xa2`/`0xa3` and
`0xa4`/`0xa5` are 8-bit write/read pairs for I2C devices `0x51` and `0x52` —
serial EEPROMs. The sweep wrote into the FX2 boot EEPROM.

Evidence that the addresses are I2C, not registers:

- `0x40`/`0x41` and `0x44`/`0x45` are write/read pairs (`0x40>>1 = 0x20`,
  low bit = read) — the I2C 8-bit addressing convention
- status `1` = "not acknowledged" is an I2C NAK; status `9` is a bus error
- a Type 4 ping sweep of all 256 addresses returns exactly nine responders,
  consistent with a small I2C bus, not a register file

## Actual damage — one byte

| | |
|---|---|
| before | `c0 05 0f 35 f2 07 aa 04` |
| after | `5c 05 0f 35 f2 07 aa 04` |

Only the **format signature** changed, `0xC0` → `0x5C`. VID, PID, revision and
config byte are intact. The FX2 does not recognise the signature, ignores the
EEPROM, and enumerates with its hardwired default `04B4:8613`.

> An intermediate report that the EEPROM was "erased" (`ff ff ff ff ff ff ff`)
> was **wrong**. That reading came from a hand-written I2C routine in
> `tools/i2c_eeprom.c` which does not work correctly; all-`0xFF` is the
> signature of a failed read, not blank memory. The vendor's own reader (the
> stage-1 loader's `0xA9`) consistently returns bytes 1..7 correct. Trust the
> vendor path.

## Consequences — the scanner still works

- Firmware loads normally and the unit enumerates as a full
  `0f05:f135 "F135-USB Film Scanner"`.
- The command protocol, board communication and the 30 MB/s EP 0x86 stream all
  function.
- Two costs: `pakon_load.py` needs `--hex` because the pre-load USB identity is
  gone, and the unit lights a **red status LED** after loading.
- The red LED may be inhibiting the lamp. It is worth eliminating this variable
  before any further lamp work.

## The repair image is known exactly — [VERIFIED]

The vendor ships the EEPROM images. `FirmwareLoader/Personalities/`:

| File | Bytes | Decoded |
|---|---|---|
| `USB DDR.bin` | `c0 05 0f 35 f2 05 aa 04 02` | rev `aa05` |
| **`USB F135.bin`** | **`c0 05 0f 35 f2 07 aa 04 02`** | **rev `aa07` — this scanner** |
| `USB F335.bin` | `c0 05 0f 35 f2 08 aa 04 02` | rev `aa08` |
| `USB FIFO.bin` | `c0 05 0f 35 f2 05 aa 04 01` | rev `aa05`, cfg `01` |

`USB F135.bin` matches the bytes captured from this unit before the damage,
byte for byte, and adds a 9th byte (`02`) that the 8-byte personality read does
not expose. **The repair data is certain, not reconstructed.**

Structure (`DEVICE_PERSONALITY`, `F135Loader.h`, 8 bytes + 1):

```
  c0        format signature (0xC0 = supplies VID/PID; 0xC2 = full firmware)
  05 0f     idVendor  0x0F05
  35 f2     idProduct 0xF235
  07 aa     bcdDevice 0xAA07
  04        config
  02        trailing byte, personality index / board variant
```

## How the vendor writes it

`FirmwareLoaderCom.dll` (a .NET assembly using `DeviceIoControl`) exposes:

```
FN_bWritePersonality   FN_SetPersonality      FN_bVerifyPersonality
FN_bEEPromWrite        FN_bEEPromSendVendReq  FN_EraseEEPROM
FN_bReadEEPromBasics   FN_bReadEEPromBasicsCheckSum
FN_bReadPicEEPromByte  FN_LoadPersonalityAndFirmware
```

It reads its images from `\\?\%s\Personalities\%s` and reaches the device with
**`IOCTL_EZUSB_VENDOR_OR_CLASS_REQUEST` (`0x222059`)** — a generic vendor
request passthrough carrying `VENDOR_OR_CLASS_REQUEST_CONTROL`
(direction, requestType, recipient, reserved, request, value, index).

On macOS that IOCTL layer does not exist: it is a plain libusb control
transfer. So the repair reduces to **one unknown — the vendor request code and
its wValue/wIndex convention for an EEPROM write.**

## Recommended repair procedure

1. Decode the request code from `FirmwareLoaderCom.dll`. It is .NET, so
   decompiling the IL (monodis / ikdasm / ILSpy) will show the literal passed
   into the `VENDOR_OR_CLASS_REQUEST_CONTROL.request` field inside
   `FN_bEEPromSendVendReq`. This is the correct next step and needs no hardware.
2. Load the vendor stage-1 loader (it owns personality operations).
3. Issue the write with the 9 bytes of `USB F135.bin`.
4. Read back with `0xA9` and compare.
5. Power cycle; success is the unit enumerating as `0f05:f235 rev aa07`
   without `--hex`, and ideally the red LED clearing.

## Do not

- **Do not use `tools/i2c_eeprom.c` to write.** Its read path is unreliable and
  its write path fails with "no ACK on device address". It is retained only as
  a record of the approach and its failure. Bit-banging I2C by hand against a
  working scanner is not worth the risk when the vendor path exists.
- **Do not touch I2C device `0xa4`.** It still holds data
  (`01 00 00 0c 37 59 f1`) and is not the boot EEPROM.
- **Do not sweep writes across addresses whose meaning is unknown.** That is
  what caused this.

## The vendor's EEPROM access protocol — [VERIFIED-FROM-BINARY]

`FirmwareLoaderCom.dll` is a **native** COM DLL (the `mscoree` string is a red
herring — its CLR data directory is empty and it has an `.orpc` section), so it
disassembles directly.

`fcn.10005730` is the generic vendor-request wrapper. It builds a 10-byte
`VENDOR_OR_CLASS_REQUEST_CONTROL` from its arguments and issues
`DeviceIoControl(0x222059)` at `0x10005822` with `nInBufferSize = 10`.

Its only callers are `fcn.10005a40` and `fcn.10005bc0` — the EEPROM read and
write paths. Each calls the wrapper **twice**: once with direction `0`, once
with direction `1`, i.e. write-then-verify.

The constants they pass:

```
    mov byte [var_8h], 0xA2        ; bRequest, one branch
    mov byte [var_8h], 0xA9        ; bRequest, other branch
    ...
    push 0x1234                    ; wIndex   <-- MAGIC UNLOCK VALUE
    push 0xA4                      ; wValue
    push 2                         ; recipient
    push 0   /   push 1            ; direction: 0 = OUT (write), 1 = IN (read)
    call fcn.10005730
```

### `wIndex = 0x1234` is a safety interlock — [VERIFIED]

**EEPROM access is gated behind a magic constant.** This is the single most
important finding for the repair, and it explains every previous failure:

- hand-rolled I2C bit-banging (`tools/i2c_eeprom.c`) bypasses the firmware's
  own EEPROM routines entirely and does not work;
- sweeping vendor requests with `wIndex = 0` is silently ignored, because the
  unlock value is absent.

It also means the boot EEPROM **cannot** have been damaged through vendor
requests. The corruption came from the packet-protocol writes to I2C address
`0xa2`, which reach the bus directly and are not gated.

### Repair recipe

On macOS this is a plain libusb control transfer — the `DeviceIoControl` layer
does not exist:

```python
    # write (direction 0)
    dev.ctrl_transfer(0x40,        # host->device, vendor, device
                      0xA2,        # bRequest  (try 0xA9 if 0xA2 is refused)
                      0x00A4,      # wValue
                      0x1234,      # wIndex -- REQUIRED unlock value
                      data)        # bytes of USB F135.bin

    # verify (direction 1)
    back = dev.ctrl_transfer(0xC0, 0xA2, 0x00A4, 0x1234, len(data))
```

with `data = c0 05 0f 35 f2 07 aa 04 02` from `USB F135.bin`.

Sequence: load the vendor stage-1 loader first (it owns personality
operations), then issue the write, then the verify read, then power-cycle and
confirm the unit enumerates as `0f05:f235 rev aa07` without `--hex`.

Remaining uncertainty: which of `0xA2` / `0xA9` is the write and which is the
read, and whether `wValue` is fixed at `0xA4` or is an address. Both callers
show the same constants, so trying `0xA2` first and falling back to `0xA9` is
low risk — a wrong request code is refused, not destructive, and the data being
written is the vendor's own official image for this exact model.
