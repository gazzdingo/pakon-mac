# 18 — Main board: diagnosis and the recovery route

## Symptom

Board 0x44 does not communicate. It returns status 1 to a Type 4 command and
no data to any register read, across the low and high register ranges, after a
clean power cycle, with the physical connections confirmed intact and the boot
EEPROM repaired.

Everything else works:

| subsystem | state |
|-----------|-------|
| USB / FX2 | enumerates as `0f05:f235 rev aa07`, loads firmware unaided |
| light board 0x40 | every command status 0; lamp lights bright blue |
| I2C bus | EEPROM addresses ACK; two devices answer, one does not |
| main board 0x44 | **silent** |

The main board hosts the motor, the CCD A/D registers (0x84) and the FPGA
registers (0x82), so no scan is possible while it is silent.

## This is not a porting gap

`FN_bDrvFindPicController` (TLB.dll enum 92) discovers boards by sending
`04 03 <addr> 00 00` — byte for byte the probe used here. Board 0x44 fails it,
so the real Windows driver would report `EC_PicM_NotFound` (enum 236) against
this unit as it stands.

## The most promising hypothesis: the PIC is in its bootloader

`FirmwareLoaderCom.dll` distinguishes two states when it enumerates PICs:

```
iPIC_VERSION_BOOT_FOUND        a PIC present but running only its bootloader
iPIC_VERSION_BOOT_16_FOUND
iPIC_VERSION_PROGRAM_FOUND     a PIC running its application
iPIC_MOTOR / iPIC_CCD / iPIC_APS / iPIC_COUNT_F135
```

plus `FN_bPicToBootLoaderState`, `FN_bLoadPic`, `FN_bLoadPicLarge`,
`FN_bVerifyPicLarge`, `FN_bFindPicControllerStatus` and `EC_NoBootLoader`.

A motor PIC that has lost its application flash would sit in its bootloader:
present on the bus, acknowledging nothing at the application level, and unable
to run the motor or program the FPGA. That matches every observation.

If that is the failure, it is **recoverable in software** — but only through
the PIC bootloader protocol, which is a separate protocol from the packet
interface this project has decoded.

## Recommended route: run Kodak's own loader

Everything needed ships in the vendor download and is present locally:

```
Config/Firmware/FirmwareLoader.exe          61,440 bytes
FirmwareLoader/FirmwareLoaderCom.dll       212,992 bytes
FirmwareLoader/Personalities/*.bin         the EEPROM images
Config/Firmware/nm0506.HEX                  29,977 bytes  <- PICM, F-135 Plus
```

Per `ReadmeF135.txt`, the F-135 Plus uses the **NL** (light) and **NM**
(motor) images, where `NMxxyy` is `xx` = hardware revision, `yy` = firmware
revision:

| image | hardware |
|-------|----------|
| `nm0306.HEX` | PCB #125430A |
| `nm0406.HEX` | PCB #125430B |
| **`nm0506.HEX`** | **PCB #125430C** |

`yy = 06` is "Add F135 Plus/Hybrid support".

**Check the PCB number printed on the board before choosing an image.** The
readme is explicit that the 03/04/05 images must not be used on PCB #125039A.

Running `FirmwareLoader.exe` on a Windows machine (or a VM with USB
passthrough) will report which PICs it finds and in which state. That alone is
diagnostic:

- reports the motor PIC in **boot** state → reload `nm0506.HEX` and the board
  should come back
- does not see the motor PIC at all → the fault is electrical, not firmware

## If it is electrical

TLB.dll's self-test suite checks exactly what would produce this signature:

```
EC_BistPicmVinFail   EC_BistPicm13VFail  EC_BistPicm12VFail
EC_BistPicm6VFail    EC_BistPicm5VFail   EC_BistPicm3VFail
EC_BistPicmMotorFail
```

A failed supply rail explains all of it: fault LEDs lit, board off the bus,
motor dead, light board unaffected on its own supply. Measuring those rails is
the next step and needs a meter, not code.

## Porting the bootloader protocol

If Windows is not an option, the protocol is recoverable from
`FirmwareLoaderCom.dll` by the same technique used on TLB.dll: the enum→name
table is at `fcn.10006270`, and the logger takes
`(handle, functionEnum, errorCode)`. Relevant enums:

| enum | name |
|-----:|------|
| 8 | `FN_bDrvFindPicController` |
| 20 | `FN_bFindPicControllerStatus` |
| 38 | `FN_bLoadPic` |
| 39 | `FN_bLoadPicLarge` |
| 44 | `FN_bPicToBootLoaderState` |
| 51 | `FN_bReadPicEEPromByte` |
| 57 | `FN_bVerifyPicLarge` |
| 60 | `FN_bWritePersonality` |
| 114 | `EC_NoBootLoader` |

`FN_bPicToBootLoaderState` is `fcn.1000e2e0`. This has not been ported here;
writing PIC flash from an incompletely understood protocol is exactly the
class of action that damaged this unit's boot EEPROM, and it should not be
attempted from a partial reading.

## The address evidence points at the bootloader hypothesis

The addresses that ACK, expressed as 7-bit I2C devices:

| 8-bit pair | 7-bit | interpretation |
|------------|-------|----------------|
| `0x40`/`0x41` | `0x20` | light board — responds fully, stable reads |
| `0x44`/`0x45` | `0x22` | motor board application — **no ACK at all** |
| `0x46`/`0x47` | `0x23` | **ACKs, but no application behaviour** |
| `0xa2`/`0xa3` | `0x51` | EEPROM |
| `0xa4`/`0xa5` | `0x52` | EEPROM |

`0x22` and `0x23` are adjacent. PIC bootloaders conventionally answer on a
different I2C address from the application, and a bootloader implements
neither the register file nor the motor commands. That accounts for every
otherwise-odd observation about `0x46`:

- it ACKs writes (status 0) — a device is there
- register reads from it are unstable — no register file behind them
- motor commands are accepted and do nothing — no application to run them
- the application address `0x22` does not ACK — no application present

So the working hypothesis is that **the motor PIC is alive and sitting in its
bootloader at 7-bit 0x23, having lost its application flash**. If so the board
is not damaged and is recoverable by reloading `nm0506.HEX`.

This is a hypothesis, not a conclusion. What would confirm it is the vendor
loader reporting `iPIC_VERSION_BOOT_FOUND` for the motor PIC.

Note that `status = 0` on a write means only that a device ACKed the I2C
transaction; the known-good light board accepts nonsense registers just as
readily. Do not read an ACK as evidence that a command was understood.

## Retraction: 0x46 is not a PIC in bootloader mode

The bootloader-at-0x23 hypothesis above does not survive a proper look at the
data. Reading registers 0x00-0x1f and 0x80-0xaf on each address:

| board | readable regs | distinct payloads | status bytes | verdict |
|-------|--------------:|------------------:|--------------|---------|
| `0x40` light | 16 | 1 | 88, a8 | real device, discriminates |
| `0x44` motor | 0 | — | — | silent |
| `0x41` | 80 | 1 | 9c | echoes one value for every register |
| `0x46` | 80 | 49 | 00, 02 | varies -- noise |
| `0x47` | 80 | 56 | 04 | varies -- noise |

A real board answers a limited set of registers with stable values. The light
board answers 16. `0x46` and `0x47` answer *all eighty* probed registers with
values that differ between reads of the same register, which is the signature
of a floating bus, not a device.

The ACK at 0x46 and its occasional clean-looking response were over-read. The
motor board is not present at any address, in application or bootloader state.

That removes the software recovery route: there is nothing on the bus to send
a bootloader command to. Reloading `nm0506.HEX` requires a PIC that answers,
and none does.

The remaining explanation is electrical, which is where the vendor's own PICM
self-tests point:

```
EC_BistPicmVinFail   EC_BistPicm13VFail  EC_BistPicm12VFail
EC_BistPicm6VFail    EC_BistPicm5VFail   EC_BistPicm3VFail
EC_BistPicmMotorFail
```

## Why FirmwareLoader.exe cannot be run on this machine

```
FirmwareLoader.exe : PE32, Intel 80386, MS Windows GUI
this machine       : arm64 (Apple Silicon), no Wine or CrossOver
```

Wine would not help even if installed. The application reaches the scanner
through the `ezusb.sys` **kernel driver** via `DeviceIoControl`; Wine
implements Win32, not a Windows kernel driver stack, so there is no path from
it to the USB device. This is the same constraint that motivated this port.

Porting the loader's logic is feasible -- it speaks the same packet protocol
decoded here -- but pointless while no PIC answers on the bus.
