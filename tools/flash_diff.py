#!/usr/bin/env python3
"""Diff a flash read off U11 against the vendor image. READ ONLY -- pure analysis.

This is the payoff step of the ICSP session. Only four points in the whole
32 KB chip have ever been verified (0x400-0x47F, 0x800, 0x1000, 0x2000). The
other ~29 KB has never been read by anything. If corruption exists in it, this
finds it -- and that would be the fault, located, with nothing written.

WHAT IT CHECKS, in order of diagnostic value
--------------------------------------------
1. ERASED ROWS. PIC18 erases in 64-byte rows, so damage from a bad flash write
   appears as 64-byte-ALIGNED runs of 0xFF. That signature distinguishes "we
   erased this ourselves" from random corruption, and it is the single most
   likely self-inflicted failure -- flash_picm.py had a bug where command 4
   (ERASE a row) was believed to be "set address".

2. CRITICAL LOCATIONS. A handful of words decide whether the chip can answer
   on I2C at all. Each is checked and named explicitly rather than being lost
   in a byte count.

3. EVERYTHING ELSE, summarised by region.

A NOTE ON THE BOOTLOADER
------------------------
nm0506.HEX starts at 0x400. The bootloader at 0x0000-0x03FF is NOT in any
vendor file -- 348 HEX files were parsed and every one starts at 0x400 -- so
that region CANNOT be diffed. It can only be preserved. Anything read there is
reported for the record but never compared.

    ./flash_diff.py <read.hex>              # diff a real read
    ./flash_diff.py --self-test             # prove the tool works, no hardware
"""
from __future__ import annotations

import argparse
import sys

VENDOR_HEX = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/"
              "Pakon/F-X35 COM SERVER/Config/Firmware/nm0506.HEX")

CONFIG_LO, CONFIG_HI = 0x300000, 0x30000E
EEPROM_LO, EEPROM_HI = 0xF00000, 0xF00100
BOOTLOADER_END = 0x000400
FLASH_END = 0x008000
ROW = 64

# U11 internal EEPROM indices worth naming (docs/27 section 4).
EEPROM_MAP = {0: 'app-valid gate (expect 0xAA)',
              2: 'gates fault-code clear',
              4: 'suspected stray 0x0D',
              5: 'THE PERSISTED FAULT CODE',
              6: '-> RAM 0x027'}

# Words whose corruption would produce exactly the fault we are chasing.
CRITICAL = {
    0x000400: (0xEFE1, "GOTO 0x002BC2 -- the application reset vector. This is "
                       "the ONLY byte in 0x400-0x47F that differs between "
                       "firmware revisions (nm0406/nm0306 hold 0xDF -> "
                       "0x002BBE). One wrong byte sends the chip four bytes "
                       "early, skipping a setup instruction while still "
                       "looking alive enough to blink. WE WROTE THIS REGION."),
    0x000402: (0xF015, "second word of the reset GOTO."),
    0x002C62: (0x0E44, "MOVLW 0x44 -- the I2C slave address literal. This is "
                       "the value that reaches SSPADD. Corrupt it and U11 "
                       "answers at the wrong address, or nowhere."),
    0x002C64: (0x0101, "MOVLB 1 -- selects bank 1. Without it the MOVWF below "
                       "writes 0x34 in the WRONG BANK and every other check "
                       "still reads green."),
    0x002C66: (0x6F34, "MOVWF 0x134 -- stores that address into the argument "
                       "slot the MSSP init reads."),
    0x001A8C: (0x0E36, "MOVLW 0x36 -- the SSPCON1 value that ENABLES the I2C "
                       "slave. Corrupt it and the peripheral never turns on."),
    0x001A90: (0xC134, "MOVFF 0x134,SSPADD -- loads the slave address into the "
                       "peripheral."),
}

REGIONS = [(0x000400, 0x000480, "reset/interrupt vectors (repaired 2026-08)"),
           (0x000480, 0x001000, "early init"),
           (0x001000, 0x002000, "main body"),
           (0x002000, 0x002D80, "boot path, MSSP init, main loop"),
           (0x002D80, 0x008000, "tail")]


def load_hex(path):
    """Parse Intel HEX, VALIDATING record checksums.

    The first version silently skipped malformed lines, so a truncated or
    corrupted transfer degraded quietly into "partial data" and then into a
    confident verdict. Now bad records are counted, surfaced, AND (since the
    2026-08-05 review) fed into the trust gates: a read containing malformed
    records gets its verdict WITHHELD rather than merely warned about.

    Returns (mem, bad_record_count).
    """
    mem, ext, bad = {}, 0, 0
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith(":"):
                continue
            try:
                b = bytes.fromhex(line[1:])
            except ValueError:
                bad += 1
                continue
            if len(b) < 5 or (sum(b) & 0xFF) != 0:
                bad += 1
                continue
            n, a, t = b[0], (b[1] << 8) | b[2], b[3]
            if t == 0:
                for i, v in enumerate(b[4:4 + n]):
                    mem[ext + a + i] = v
            elif t == 2:
                ext = ((b[4] << 8) | b[5]) << 4
            elif t == 4:
                ext = ((b[4] << 8) | b[5]) << 16
            elif t == 1:
                break
    if bad:
        print(f"  *** WARNING: {bad} malformed/bad-checksum record(s) in "
              f"{path}. The read may be truncated or corrupted. ***")
    return mem, bad


def word(mem, a):
    return mem.get(a, 0xFF) | (mem.get(a + 1, 0xFF) << 8)


def erased_rows(chip, lo, hi):
    """64-byte ALIGNED runs of 0xFF -- the signature of a PIC18 row erase."""
    out = []
    for base in range(lo - (lo % ROW), hi, ROW):
        vals = [chip.get(base + i) for i in range(ROW)]
        if all(v == 0xFF for v in vals if v is not None) and any(
                v is not None for v in vals):
            out.append(base)
    # merge adjacent
    merged = []
    for b in out:
        if merged and merged[-1][1] == b:
            merged[-1][1] = b + ROW
        else:
            merged.append([b, b + ROW])
    return merged


def analyse(chip, vendor, bad_records=0):
    """Returns 0 = matches, 1 = does not match, 2 = verdict WITHHELD."""
    print(f"read image : {len(chip)} bytes, "
          f"{min(chip):#08x}-{max(chip):#08x}" if chip else "read image : EMPTY")
    print(f"vendor     : {len(vendor)} bytes, "
          f"{min(vendor):#08x}-{max(vendor):#08x}\n")

    boot = {a: v for a, v in chip.items() if a < BOOTLOADER_END}
    if boot:
        nonff = sum(1 for v in boot.values() if v != 0xFF)
        print(f"BOOTLOADER 0x000000-0x0003FF: {len(boot)} bytes read, "
              f"{nonff} non-blank")
        print("  Not comparable -- no vendor copy of this region exists "
              "anywhere.")
        print("  PRESERVE IT. This is what makes chip replacement possible.\n")
    else:
        print("BOOTLOADER 0x000000-0x0003FF: NOT PRESENT in this read.")
        print("  *** Read it before doing anything else. No copy exists. ***\n")

    print("=" * 70)
    print("1. ERASED ROWS (64-byte aligned 0xFF runs -- our own flasher's "
          "signature)")
    rows = erased_rows(chip, BOOTLOADER_END, FLASH_END)
    expected_blank = []
    if not rows:
        print("   none. No row-erase damage in the application region.")
    for lo, hi in rows:
        vend_blank = all(vendor.get(a, 0xFF) == 0xFF for a in range(lo, hi))
        tag = "also blank in vendor image (normal)" if vend_blank else \
              "*** ERASED -- vendor image has code here ***"
        if vend_blank:
            expected_blank.append((lo, hi))
        print(f"   {lo:#08x}-{hi:#08x}  ({(hi - lo) // ROW} rows)  {tag}")

    print("\n" + "=" * 70)
    print("2. CRITICAL WORDS")
    bad_critical = 0
    for addr, (expect, why) in sorted(CRITICAL.items()):
        got = word(chip, addr)
        present = addr in chip
        if not present:
            print(f"   {addr:#08x}  NOT READ")
            continue
        ok = got == expect
        if not ok:
            bad_critical += 1
        print(f"   {addr:#08x}  expect {expect:#06x}  got {got:#06x}  "
              f"{'OK' if ok else '*** MISMATCH ***'}")
        if not ok:
            print(f"              {why}")

    print("\n" + "=" * 70)
    print("3. FULL COMPARISON BY REGION")
    total_diff = 0
    for lo, hi, name in REGIONS:
        diffs = [a for a in range(lo, hi)
                 if a in chip and chip[a] != vendor.get(a, 0xFF)]
        total_diff += len(diffs)
        read_n = sum(1 for a in range(lo, hi) if a in chip)
        if read_n == 0:
            print(f"   {lo:#08x}-{hi:#08x}  {name:44} NOT READ")
        elif not diffs:
            print(f"   {lo:#08x}-{hi:#08x}  {name:44} identical "
                  f"({read_n} bytes)")
        else:
            print(f"   {lo:#08x}-{hi:#08x}  {name:44} "
                  f"*** {len(diffs)} DIFFS ***")
            for a in diffs[:8]:
                print(f"        {a:#08x}  chip {chip[a]:#04x}  "
                      f"vendor {vendor.get(a, 0xFF):#04x}")
            if len(diffs) > 8:
                print(f"        ... and {len(diffs) - 8} more")

    print("\n" + "=" * 70)
    print("4. TRUST GATES -- is this read believable at all?")
    trust_ok = True

    # (a) Config words. We know these from nm0506.HEX, so a mismatch means the
    #     READ is wrong, not the chip. docs/27 step 3 specified this gate; it
    #     was never actually implemented until now.
    cfg_chip = {a: chip[a] for a in range(CONFIG_LO, CONFIG_HI) if a in chip}
    cfg_vend = {a: vendor[a] for a in range(CONFIG_LO, CONFIG_HI) if a in vendor}
    if not cfg_chip:
        print("   config words : NOT READ -- cannot verify the read chain")
        trust_ok = False
    else:
        bad_cfg = [a for a in cfg_chip
                   if a in cfg_vend and cfg_chip[a] != cfg_vend[a]]
        if bad_cfg:
            print(f"   config words : *** {len(bad_cfg)} MISMATCH ***")
            for a in bad_cfg:
                print(f"        {a:#08x}  chip {cfg_chip[a]:#04x}  "
                      f"vendor {cfg_vend[a]:#04x}")
            trust_ok = False
        else:
            print(f"   config words : match ({len(cfg_chip)} bytes) -- "
                  f"read chain trustworthy")

    # (b) Dead read chain. All-0xFF or all-0x00 is miswiring or a stuck line,
    #     not a diagnosis. 1 KB of zeros looks exactly like a real backup.
    if boot:
        vals = set(boot.values())
        if len(vals) == 1:
            print(f"   bootloader   : *** ALL {vals.pop():#04x} -- DEAD READ "
                  f"CHAIN, this is not a backup ***")
            trust_ok = False
        else:
            print(f"   bootloader   : {len(vals)} distinct byte values "
                  f"(looks like real data)")

    # (c) Completeness. Every counter above only counts what was READ, so a
    #     truncated read would otherwise sail through as "matches" -- a chip
    #     swap decided on 128 bytes of evidence.
    unread = [n for lo, hi, n in REGIONS
              if not any(a in chip for a in range(lo, hi))]
    partial = [n for lo, hi, n in REGIONS
               if 0 < sum(1 for a in range(lo, hi) if a in chip) < hi - lo]
    missing_crit = [a for a in CRITICAL if a not in chip]
    if unread or partial or missing_crit:
        print("   completeness : *** INCOMPLETE READ ***")
        for n in unread:
            print(f"        not read at all      : {n}")
        for n in partial:
            print(f"        only partially read  : {n}")
        if missing_crit:
            print(f"        critical words unread: "
                  f"{', '.join(hex(a) for a in missing_crit)}")
        trust_ok = False
    else:
        print("   completeness : every region and critical word was read")

    # (d) The bootloader itself. "Read everything first" means a read with
    #     no bootloader at all gets no verdict -- a verdict here could invite
    #     a reflash while the one irreplaceable region was never captured.
    if not boot:
        print("   bootloader   : *** ABSENT FROM THIS READ -- the one "
              "region that can never be re-created was not captured ***")
        trust_ok = False

    # (e) The internal EEPROM. Same rule -- "all of the EEPROMs" -- and it
    #     carries the app-valid gate and the persisted fault code. A full
    #     device read (-GF) contains it; a read without it is not the backup
    #     this procedure requires.
    eeprom = {a - EEPROM_LO: v for a, v in chip.items()
              if EEPROM_LO <= a < EEPROM_HI}
    if not eeprom:
        print("   int. EEPROM  : *** ABSENT FROM THIS READ -- use the full-"
              "device read (-GF), or capture the EEPROM region explicitly ***")
        trust_ok = False
    else:
        named = "  ".join(f"[{i}]={eeprom.get(i, 0xFF):#04x}"
                          for i in sorted(EEPROM_MAP))
        print(f"   int. EEPROM  : {len(eeprom)} bytes read   {named}")
        print(f"                  ([5] is the persisted fault code)")

    # (f) Malformed HEX records in the transfer.
    if bad_records:
        print(f"   hex records  : *** {bad_records} malformed/bad-checksum "
              f"record(s) -- transfer not trustworthy ***")
        trust_ok = False

    print("\n" + "=" * 70)
    # tuple(r): rows holds LISTS, expected_blank holds TUPLES, and
    # [lo,hi] == (lo,hi) is always False in Python. That mismatch made every
    # vendor-blank region count as damage -- and since the chip is 32 KB while
    # the vendor image ends at 0x2D7B, the blank tail guaranteed a false
    # "does NOT match" on a perfectly healthy chip.
    real_erased = [r for r in rows if tuple(r) not in expected_blank]

    if not trust_ok:
        print("VERDICT: WITHHELD -- this read cannot be trusted.")
        print("  A trust gate failed above. Fix the connection, the wiring or")
        print("  the command and read again. Draw no conclusion from this and")
        print("  write nothing based on it.")
        return 2

    if total_diff == 0 and not real_erased and bad_critical == 0:
        print("VERDICT: flash matches the vendor image.")
        print("  Firmware is exonerated. The fault is electrical -- the pin")
        print("  stub, the I/O drivers, or the MSSP peripheral. Proceed to")
        print("  Test A (docs/27), and budget for a chip swap.")
        return 0
    print("VERDICT: the flash does NOT match.")
    if bad_critical:
        print(f"  {bad_critical} CRITICAL word(s) wrong -- this alone can")
        print("  explain a chip that never answers on I2C.")
    if real_erased:
        print(f"  {len(real_erased)} erased region(s) that should hold code.")
    print(f"  {total_diff} differing byte(s) overall.")
    print("\n  This is the good outcome: reflash and retest.")
    print("\n  *** BUT SEE THE MERGED-IMAGE RULE, docs/27 SECTION 7 ***")
    print("  Programming BULK-ERASES the whole chip, including the")
    print("  bootloader, which exists in no vendor file anywhere. Program a")
    print("  single merged image: bootloader backup + application + config")
    print("  + EEPROM. NEVER program nm0506.HEX on its own -- it starts at")
    print("  0x400 and would leave the bootloader erased and unrecoverable.")
    return 1


def self_test():
    """Prove the tool works, using synthetic damage. No hardware needed.

    Each case ASSERTS its verdict (0 matches / 1 does not match /
    2 withheld). A self-test that only prints can rot silently; this one
    fails loudly if any gate stops firing.
    """
    print("SELF-TEST -- synthetic data, no hardware\n")
    vendor, vbad = load_hex(VENDOR_HEX)
    if not vendor or vbad:
        sys.exit(f"cannot trust vendor image: {VENDOR_HEX} "
                 f"({vbad} bad records)")
    print(f"vendor image loaded: {len(vendor)} bytes\n")

    def realistic(mutate=None):
        """The shape tomorrow's read actually has: bootloader + full flash
        + config + internal EEPROM (a -GF full-device read)."""
        img = {a: vendor.get(a, 0xFF) for a in range(0x400, 0x8000)}
        img.update({a: vendor[a] for a in vendor if a >= 0x300000})
        for a in range(0, 0x400):
            img[a] = (a * 7 + 3) & 0xFF
        for i in range(256):
            img[EEPROM_LO + i] = 0xFF
        img[EEPROM_LO + 0] = 0xAA
        img[EEPROM_LO + 4] = 0x0D
        img[EEPROM_LO + 5] = 0x0B
        if mutate:
            mutate(img)
        return img

    results = []

    def case(n, title, chip, expect):
        print(f"\n\n--- case {n}: {title} ---")
        got = analyse(chip, vendor)
        verdict = {0: "MATCHES", 1: "DOES NOT MATCH", 2: "WITHHELD"}
        ok = got == expect
        results.append((n, title, ok, got, expect))
        print(f"\n[self-test] case {n}: expected {verdict[expect]}, "
              f"got {verdict[got]}  ->  {'PASS' if ok else '*** FAIL ***'}")

    case(1, "healthy chip (must report MATCHES)", realistic(), 0)

    def corrupt_literal(m):
        m[0x002C62] = 0x10        # MOVLW 0x44 -> MOVLW 0x10
    case(2, "the address literal corrupted (the hypothesis we most want "
            "to catch)", realistic(corrupt_literal), 1)

    def erase_row(m):
        for a in range(0x001800, 0x001840):
            m[a] = 0xFF
    case(3, "a 64-byte row erased (our flasher's bug signature)",
         realistic(erase_row), 1)

    case(4, "DEAD READ CHAIN, all 0x00 (must WITHHOLD)",
         {a: 0x00 for a in range(0, 0x8000)}, 2)

    case(5, "TRUNCATED read, 128 bytes only (must WITHHOLD)",
         {a: vendor.get(a, 0xFF) for a in range(0x400, 0x480)}, 2)

    def drop_eeprom(m):
        for a in range(EEPROM_LO, EEPROM_HI):
            m.pop(a, None)
    case(6, "internal EEPROM missing from an otherwise perfect read "
            "(must WITHHOLD -- all of the EEPROMs get read, no exceptions)",
         realistic(drop_eeprom), 2)

    def drop_boot(m):
        for a in range(0, 0x400):
            m.pop(a, None)
    case(7, "bootloader missing from an otherwise perfect read "
            "(must WITHHOLD -- read everything first)",
         realistic(drop_boot), 2)

    bad = [r for r in results if not r[2]]
    print("\n" + "=" * 70)
    for n, title, ok, got, expect in results:
        print(f"  case {n}: {'PASS' if ok else '*** FAIL ***'}")
    if bad:
        print("\nSELF-TEST FAILED -- a trust gate is not firing. Do not use")
        print("this tool's verdicts until it passes.")
        return 1
    print("\nSELF-TEST PASSED -- every verdict and every withhold-gate fired")
    print("exactly as designed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("read", nargs="?", help="Intel HEX read off the chip")
    ap.add_argument("--vendor", default=VENDOR_HEX)
    ap.add_argument("--self-test", action="store_true",
                    help="prove the tool works using synthetic damage")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.read:
        ap.error("give a HEX file to diff, or --self-test")

    chip, bad = load_hex(args.read)
    if not chip:
        sys.exit(f"no data parsed from {args.read} -- is it Intel HEX?")
    vendor, vbad = load_hex(args.vendor)
    if not vendor:
        sys.exit(f"cannot read vendor image: {args.vendor}")
    if vbad:
        sys.exit(f"vendor image has {vbad} malformed record(s): "
                 f"{args.vendor} -- fix that before diffing anything")
    return analyse(chip, vendor, bad_records=bad)


if __name__ == "__main__":
    sys.exit(main())
