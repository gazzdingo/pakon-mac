# 17 — Boot EEPROM repair: procedure and result

**Status: repaired.** All nine bytes verified against Kodak's own personality
file on three consecutive reads.

## Damage history

| stage | content | cause |
|-------|---------|-------|
| healthy | `c0 05 0f 35 f2 07 aa 04 02` | — |
| first damage | `5c 05 0f 35 f2 07 aa 04` | a sweep of ~384 blind writes across addresses assumed to be board registers but which were I2C device addresses |
| second damage | `5c b5 db 05 d9 47 d7 04` | a repair attempt using a write recipe derived from stack push order, which was wrong |
| **repaired** | **`c0 05 0f 35 f2 07 aa 04 02`** | this procedure |

Both stages of damage were self-inflicted, and the second happened while
trying to undo the first. The lesson is the obvious one: do not write to an
address whose meaning has not been established, and do not attempt a repair
from an unverified recipe.

Note the damage was worse than `docs/13-eeprom-repair.md` recorded. That
document claimed one byte had changed; in fact seven of eight had.

## Why it mattered

Byte 0 is the FX2 format signature. `0xC0` means "take VID/PID from this
EEPROM". `0x5C` is not a valid signature, so the FX2 ignored the EEPROM and
enumerated with its hardwired default `04B4:8613`. Consequences:

- `pakon_load.py` needed `--hex`, because the pre-load USB identity that
  selects the firmware image was gone
- the unit lit red status LEDs after loading

## The repair data is certain

Kodak ships the personalities in `FirmwareLoader/Personalities/`:

```
USB DDR.bin    c0 05 0f 35 f2 05 aa 04 02
USB F135.bin   c0 05 0f 35 f2 07 aa 04 02   <- this scanner
USB F335.bin   c0 05 0f 35 f2 08 aa 04 02
USB FIFO.bin   c0 05 0f 35 f2 05 aa 04 01
```

`USB F135.bin` matches the bytes captured from this unit before the damage.
The tool verifies its payload against that file and refuses to run if they
disagree, so the content is never reconstructed from memory.

## Procedure

Requires the scanner **power-cycled and not yet loaded** (`04b4:8613`).

```sh
./eeprom_repair.py --dry-run     # read and report, write nothing
./eeprom_repair.py               # repair
```

### The write is one byte per transfer

This is the part that is not obvious, and it cost a false start.

The stage-1 loader answers vendor request `0xA2` (write) with **`wValue` as
the byte address**, one byte of data per transfer. Passing the whole 9-byte
payload with `wValue = 0` writes only byte 0 and then times out — which is
exactly what happened on the first attempt, leaving the EEPROM in the
dangerous intermediate state `c0 b5 db …`: a *valid* signature with a garbage
VID/PID, which would make the FX2 try to enumerate with nonsense IDs rather
than fall back to its safe default.

**If a write is interrupted, finish it before power-cycling.**

Each successful write also leaves the loader unresponsive to further control
transfers, so the loader must be re-uploaded between bytes:

```
for addr in 0..8:
    upload stage-1 loader        # RAM only
    read  0xA9 wValue=0 wIndex=0 # verify current
    write 0xA2 wValue=addr       # one byte
    upload stage-1 loader again
    read back and confirm
```

Read is `0xA9`, write is `0xA2`, both with `wIndex = 0`. Note this differs
from the generic EEPROM path in `TLB.dll` (`fcn.100160a0`), which uses
`wValue = ((n | 0x50) << 1) | readBit` and `wIndex = 0x1234` to select among
several I2C EEPROMs. The stage-1 loader's personality pair addresses the boot
EEPROM directly.

## Reading the EEPROM — what does not work

Three methods produce convincing artifacts rather than content. All are
quarantined under `~/pakon-eeprom-backup/`:

| method | result |
|--------|--------|
| `0xA9` under application firmware (`Pakon7.hex`) | one fixed buffer, byte-identical for all eight addresses |
| `0xA9` on the bare FX2 ROM | timeout; the ROM implements `0xA0` only |
| `0xA9` under stage-1 with `wValue=((n\|0x50)<<1)`, `wIndex=0x1234` | eight *different* MD5s, but the same 17 bytes shifted two positions per index — the payload tracks `wValue` rather than selecting a device |

The third is the dangerous one: a distinct-hash check reports success. **Hashes
are not enough; inspect the content.** The only trustworthy read is the
stage-1 loader's personality request with `wValue = 0`, `wIndex = 0`, repeated
several times and compared for stability.

## Verification

```
read (9 bytes): c0 05 0f 35 f2 07 aa 04 02
read (9 bytes): c0 05 0f 35 f2 07 aa 04 02
read (9 bytes): c0 05 0f 35 f2 07 aa 04 02
target        : c0 05 0f 35 f2 07 aa 04 02
```

## What to check after a power cycle

1. the unit should enumerate as `0f05:f135` **without** `--hex`
2. the red status LEDs should clear, if they were caused by this

Neither is confirmed at the time of writing.

## Backups

`~/pakon-eeprom-backup/verified/` holds the damaged content as read before the
repair (`5c b5 db 05 d9 47 d7 04`), together with a README explaining it. The
other two directories hold quarantined artifacts that must not be restored.
