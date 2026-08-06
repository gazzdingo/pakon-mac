#!/usr/bin/env python3
"""Build the repair image for U34 (PICM) -- the chip is ALIVE, its flash has a hole.

THE FAULT
  One 64-byte row erased at 0x000D00-0x000D3F. Everything else on the chip is
  correct. 0xFFFF executes as NOP, so initialisation at 0x0D00 never happens.

STRATEGY
  Restore the chip to exactly what it was, except with that row filled in.
  MPLAB BULK-ERASES before programming, so the image must contain everything:
  bootloader, application, config and EEPROM in one file.

SOURCES -- everything comes off THIS chip except the application
  bootloader  U34's own, 0x0000-0x03FF        <- the real PICM bootloader
  application nm0506.HEX, 0x0400+            <- the vendor file, which has 0x0D00
  config      U34's own                      <- NOT the file's. The chip reads
                                                CONFIG2H=0x09 where nm0506 says
                                                0x0D; U11 reads 0x09 too, so
                                                Kodak programs 0x09 regardless
  EEPROM      U34's own                      <- preserves index 0 = 0xAA and
                                                whatever else the app stored

Aborts if the chip's application differs from the vendor image anywhere OTHER
than the known erased row -- that would mean a second fault we have not seen.

OUTPUTS (adversarial review 2026-08-06)
  u34-repair.hex         exact restore + the row filled. EEPROM[0]=0xAA, so the
                         application runs at the first cold boot after
                         programming. Use only as the FALLBACK full-ICSP image,
                         and prefer the staged variant even then.
  u34-repair-staged.hex  identical except EEPROM[0]=0x00: the chip parks in its
                         own bootloader (pins held safe, I2C at 0x46) until the
                         host verifies the flash over I2C and starts the app
                         with command 8; the app then sets 0xAA itself via
                         `02 05 44 02 0a 00 aa`, the vendor update flow.
  u34-stage-eeprom.hex   EEPROM region ONLY -- all 256 bytes are the chip's own
                         values with index 0 = 0x00. For the recommended
                         minimal-ICSP path: program EEPROM only (ipecmd -ME
                         with -OH so nothing is bulk-erased), then do the whole
                         flash repair through the chip's own bootloader over
                         I2C, never erasing anything. Contains ALL 256 bytes
                         deliberately, so a tool that pads the region cannot
                         invent 0xFF over indices 1..255 (index 5 = 0x00 is the
                         persisted-fault code; 0xFF there would read as fault
                         0xF).
"""
import sys, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHIP = os.path.join(REPO, "backups/u34-picm/u34-full-A.hex")
APP  = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/"
        "Pakon/F-X35 COM SERVER/Config/Firmware/nm0506.HEX")
ERASED = (0x000D00, 0x000D40)      # the known hole, [lo, hi)
APP_BASE, FLASH_END = 0x0400, 0x8000
CFG_LO, CFG_HI = 0x300000, 0x30000E
EE_LO = 0xF00000


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
    """Intel HEX, splitting at gaps so no byte is ever invented."""
    out, ext, addrs = [], None, sorted(mem)
    i = 0
    while i < len(addrs):
        base = addrs[i] - (addrs[i] % 16)
        run = [a for a in range(base, base + 16) if a in mem]
        hi = base >> 16
        if hi != ext:
            ext = hi
            r = bytes([2, 0, 0, 4, (hi >> 8) & 0xFF, hi & 0xFF])
            out.append(":" + (r + bytes([(-sum(r)) & 0xFF])).hex().upper())
        # contiguous sub-runs only -- never pad across a gap
        start = run[0]
        while start <= run[-1]:
            seg = []
            a = start
            while a in mem and a < base + 16:
                seg.append(mem[a]); a += 1
            if seg:
                lo = start & 0xFFFF
                r = bytes([len(seg), (lo >> 8) & 0xFF, lo & 0xFF, 0]) + bytes(seg)
                out.append(":" + (r + bytes([(-sum(r)) & 0xFF])).hex().upper())
            start = a + 1 if a < base + 16 else base + 16
        while i < len(addrs) and addrs[i] < base + 16:
            i += 1
    out.append(":00000001FF")
    open(path, "w").write("\n".join(out) + "\n")


def main():
    chip, app_src = load(CHIP), load(APP)
    print(f"chip read   : {os.path.basename(CHIP)}")
    print(f"application : {os.path.basename(APP)}\n")

    # --- verify the fault is exactly what we think, and nothing else ---
    vend_app = {a: v for a, v in app_src.items() if APP_BASE <= a < FLASH_END}
    diff = [a for a in vend_app if chip.get(a, 0xFF) != vend_app[a]]
    unexpected = [a for a in diff if not (ERASED[0] <= a < ERASED[1])]
    print(f"application differences chip vs vendor: {len(diff)} bytes")
    if unexpected:
        print(f"  *** {len(unexpected)} OUTSIDE the known erased row:")
        for a in unexpected[:10]:
            print(f"      {a:#08x}  chip {chip.get(a,0xFF):02x}  vendor {vend_app[a]:02x}")
        sys.exit("ABORT: a second fault exists. Investigate before programming.")
    blank = all(chip.get(a, 0xFF) == 0xFF for a in range(*ERASED))
    print(f"  all {len(diff)} are inside {ERASED[0]:#08x}-{ERASED[1]-1:#08x}")
    print(f"  that row reads entirely 0xFF on the chip: {blank}")
    if not blank:
        sys.exit("ABORT: the row is not cleanly erased -- unexpected state.")

    # --- assemble ---
    boot = {a: v for a, v in chip.items() if a < APP_BASE}
    cfg  = {a: v for a, v in chip.items() if CFG_LO <= a < CFG_HI}
    ee   = {a: v for a, v in chip.items() if a >= EE_LO}
    print(f"\nbootloader  0x0000-0x03FF : {sum(1 for v in boot.values() if v!=0xFF)} non-0xFF "
          f"(U34's OWN -- the real PICM bootloader)")
    print(f"application 0x0400-{max(vend_app):#06x} : {len(vend_app)} bytes from nm0506")
    print(f"config                    : " + " ".join(f"{cfg[a]:02x}" for a in sorted(cfg)))
    print(f"                            (chip's own; nm0506 says CONFIG2H=0x0d, chip says "
          f"{cfg.get(0x300003,0xFF):#04x})")
    print(f"EEPROM                    : {len(ee)} bytes, index 0 = "
          f"{ee.get(EE_LO,0xFF):#04x}, index 5 = {ee.get(EE_LO+5,0xFF):#04x}")

    if not (boot and vend_app and cfg and ee):
        sys.exit("ABORT: a source region is empty")
    if set(boot) & set(vend_app):
        sys.exit("ABORT: bootloader and application overlap")

    here = os.path.dirname(os.path.abspath(__file__))
    if ee.get(EE_LO) != 0xAA:
        sys.exit("ABORT: chip EEPROM[0] is not 0xAA -- staging logic assumes it")

    ee_staged = dict(ee)
    ee_staged[EE_LO] = 0x00            # != 0xAA -> park in the bootloader

    images = [
        ("u34-repair.hex",        {**boot, **vend_app, **cfg, **ee}),
        ("u34-repair-staged.hex", {**boot, **vend_app, **cfg, **ee_staged}),
        ("u34-stage-eeprom.hex",  dict(ee_staged)),
    ]

    for name, img in images:
        out = os.path.join(here, name)
        emit(img, out)

        # --- verify bidirectionally ---
        back = load(out)
        missing = [a for a in img if back.get(a) != img[a]]
        extra   = [a for a in back if a not in img]
        print(f"\n  {out}")
        print(f"  round-trip: {len(missing)} missing/wrong, {len(extra)} invented")
        if missing or extra:
            sys.exit("ABORT: round-trip failed")
        if len(img) > 256:
            fixed = all(back.get(a) == vend_app[a] for a in range(*ERASED))
            print(f"  the erased row is filled from the vendor image: {fixed}")
            if not fixed:
                sys.exit("ABORT: the repair row is not present in the output")
        print(f"  EEPROM[0] = {back.get(EE_LO):#04x}"
              + ("  (staged: boots into the bootloader)"
                 if back.get(EE_LO) != 0xAA else "  (app runs at power-up)"))
        print(f"  total {len(img)} bytes")

    print("\n  OK -- u34-repair.hex restores the chip to exactly its previous")
    print("  state with the erased row at 0x0D00 filled in. The staged")
    print("  variants differ from it in exactly one byte, EEPROM[0].")
    return 0


if __name__ == "__main__":
    sys.exit(main())
