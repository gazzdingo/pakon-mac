#!/usr/bin/env python3
"""Build a programmable image for a replacement PICM (U34, PIC18F452).

SOURCES
  bootloader : backups/u11-picl/u11-full-A.hex   0x0000-0x033F
               (U11 = PICL, read 3x over ICSP, byte-identical.
                The ONLY copy of a Kodak bootloader we have found anywhere.)
  application: nm0506.HEX  0x0400+   PICM PLUS, hardware 05 = PCB #125430C
  config     : nm0506.HEX  0x300000-0x30000D   -- NOT U11's; they differ, and
               the bootloader never sets CFGS so config comes only from ICSP.

PATCHES (docs/31-bootloader-recovered.md section 7)
  The PICL boot block hands off to app_base 0x340. PICM's app_base is 0x400.
  That, plus the I2C slave address, is the entire difference.

Every 'from' value is verified before patching. Any mismatch aborts.

OUTPUT
  picm-staged.hex  bootloader + app + config, NO EEPROM.
                   A fresh chip reads 0xFF at EEPROM[0], which != 0xAA, so it
                   STAYS IN THE BOOTLOADER and answers at I2C 0x46. Nothing
                   moves. Verify over I2C before letting the app run.
  picm-run.hex     same + EEPROM[0] = 0xAA, so the application starts.
"""
import sys, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOT_SRC = os.path.join(REPO, "backups/u11-picl/u11-full-A.hex")
APP_SRC = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/"
           "Pakon/F-X35 COM SERVER/Config/Firmware/nm0506.HEX")
BOOT_END = 0x0340          # PICL boot block; PICM app starts at 0x400
APP_BASE = 0x0400

# addr: (from_bytes, to_bytes, why)
PATCHES = {
    0x0008: (b"\xA4\xEF\x01\xF0", b"\x04\xEF\x02\xF0",
             "GOTO 0x0348 -> 0x0408   high-priority ISR, app_base+8"),
    0x0018: (b"\x80\xEF\x1E\xF0", b"\x04\xEF\x02\xF0",
             "GOTO 0x3D00 -> 0x0408   dead vector, made inert"),
    0x0044: (b"\xA0\xEF\x01\xF0", b"\x00\xEF\x02\xF0",
             "GOTO 0x0340 -> 0x0400   app-valid hand-off"),
    0x005C: (b"\x42",             b"\x46",
             "MOVLW 0x42 -> 0x46      THE I2C SLAVE ADDRESS"),
    0x0266: (b"\xA0\xEF\x01\xF0", b"\x00\xEF\x02\xF0",
             "GOTO 0x0340 -> 0x0400   command-8 hand-off"),
    0x01D8: (b"\x3E",             b"\xFE",
             "SUBLW 0x3E -> 0xFE      write guard floor 0x33E -> 0x3FE"),
}


def load(path):
    mem, ext = {}, 0
    with open(path, errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith(":"):
                continue
            b = bytes.fromhex(line[1:])
            if len(b) < 5 or (sum(b) & 0xFF) != 0:
                sys.exit(f"{path}: bad Intel HEX record")
            n, a, t = b[0], (b[1] << 8) | b[2], b[3]
            if t == 0:
                for i, v in enumerate(b[4:4 + n]):
                    mem[ext + a + i] = v
            elif t == 4:
                ext = ((b[4] << 8) | b[5]) << 16
            elif t == 1:
                break
    return mem


def emit(mem, path):
    """Write Intel HEX, 16 bytes per record, with extended-address records."""
    out, ext = [], None
    for base in range(0, max(mem) + 1, 16):
        chunk = [(base + i, mem[base + i]) for i in range(16) if base + i in mem]
        if not chunk:
            continue
        hi = base >> 16
        if hi != ext:
            ext = hi
            rec = bytes([2, 0, 0, 4, (hi >> 8) & 0xFF, hi & 0xFF])
            out.append(":" + (rec + bytes([(-sum(rec)) & 0xFF])).hex().upper())
        data = bytes(mem.get(base + i, 0xFF) for i in range(16))
        lo = base & 0xFFFF
        rec = bytes([16, (lo >> 8) & 0xFF, lo & 0xFF, 0]) + data
        out.append(":" + (rec + bytes([(-sum(rec)) & 0xFF])).hex().upper())
    out.append(":00000001FF")
    open(path, "w").write("\n".join(out) + "\n")


def main():
    boot_src, app_src = load(BOOT_SRC), load(APP_SRC)
    print(f"bootloader source : {BOOT_SRC}")
    print(f"application source: {os.path.basename(APP_SRC)}\n")

    boot = {a: v for a, v in boot_src.items() if a < BOOT_END}
    print(f"boot block 0x0000-{BOOT_END-1:#06x}: "
          f"{sum(1 for v in boot.values() if v != 0xFF)} non-0xFF bytes")

    print("\napplying patches (verifying every 'from' value first):")
    for addr in sorted(PATCHES):
        frm, to, why = PATCHES[addr]
        have = bytes(boot.get(addr + i, 0xFF) for i in range(len(frm)))
        if have != frm:
            sys.exit(f"  ABORT {addr:#06x}: expected {frm.hex(' ')}, "
                     f"found {have.hex(' ')}")
        for i, v in enumerate(to):
            boot[addr + i] = v
        print(f"  {addr:#06x}  {frm.hex(' '):<12} -> {to.hex(' '):<12}  {why}")

    app = {a: v for a, v in app_src.items() if APP_BASE <= a < 0x8000}
    cfg = {a: v for a, v in app_src.items() if a >= 0x300000}
    if not app or not cfg:
        sys.exit("ABORT: application or config missing from nm0506")
    print(f"\napplication 0x0400-{max(app):#06x}: {len(app)} bytes")
    print(f"config {min(cfg):#08x}-{max(cfg):#08x}: "
          + " ".join(f"{cfg[a]:02x}" for a in sorted(cfg)))

    overlap = set(boot) & set(app)
    if overlap:
        sys.exit(f"ABORT: boot and app overlap at {min(overlap):#06x}")

    base = {**boot, **app, **cfg}
    outdir = os.path.dirname(os.path.abspath(__file__))

    staged = os.path.join(outdir, "picm-staged.hex")
    emit(dict(base), staged)
    run = os.path.join(outdir, "picm-run.hex")
    emit({**base, 0xF00000: 0xAA}, run)

    print(f"\n  {staged}")
    print(f"     no EEPROM -> fresh chip reads 0xFF at index 0, stays in the")
    print(f"     bootloader, answers I2C 0x46. NOTHING MOVES. Program this first.")
    print(f"  {run}")
    print(f"     EEPROM[0]=0xAA -> application runs, answers I2C 0x44.")

    # read back and verify
    print("\nverifying written files:")
    for f in (staged, run):
        m = load(f)
        bad = [a for a in base if m.get(a) != base[a]]
        print(f"  {os.path.basename(f)}: {len(m)} bytes, "
              f"{'round-trips exactly' if not bad else f'*** {len(bad)} MISMATCH ***'}")
        for addr in sorted(PATCHES):
            to = PATCHES[addr][1]
            got = bytes(m.get(addr + i, 0xFF) for i in range(len(to)))
            if got != to:
                print(f"    *** patch {addr:#06x} not present: {got.hex(' ')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
