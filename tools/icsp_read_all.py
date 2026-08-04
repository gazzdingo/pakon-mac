#!/usr/bin/env python3
"""Read U11 (PIC18F452) out through a PICkit 3 via ipecmd. READ ONLY.

This is the "read everything before writing anything" step. No copy of the
PICM bootloader (0x0000-0x03FF) exists anywhere -- 348 vendor HEX files were
parsed and every one starts at 0x400. If it is ever clobbered it is gone
permanently, so it comes off the chip first, before anything else happens.

SAFETY DESIGN
-------------
* DRY RUN BY DEFAULT. Nothing runs until --execute is passed. Without it this
  prints the exact commands it would issue so they can be read first.
* No write path exists in this file. The programming (-F), erase (-E) and
  program-device (-M) flags are never emitted, and guard() refuses to run any
  command containing them.
* -W IS NOT PASSED, and that is deliberate. VERIFIED against the installed
  ipecmd's own help on 2026-08-04, which prints a three-column table of
  flag | what it does | default:

      K   Display Hex File Checksum  |  Do Not Display
      M   Program Device             |  Do Not Program
      W   Power target from tool     |  Externally power target

  So -W means "power the target FROM THE TOOL", and "externally powered" is
  the DEFAULT you get by omitting it. A review claimed the opposite; the
  installed binary settles it. Passing -W would ask the PICkit 3 to source a
  board drawing far more than its ~30 mA, risking a brown-out mid-read and a
  corrupt "backup" we would then trust with the scanner's life.

ORDER OF OPERATIONS
-------------------
1. Device ID      -- confirms ICSP works at all, touches nothing.
2. Config words   -- we already know these from nm0506.HEX, so a match proves
                     the whole read chain is trustworthy before we depend on it.
3. Bootloader     -- the irreplaceable 1 KB.
4. Full flash     -- 32 KB. ~29 KB of this has NEVER been read by anything.
5. EEPROM         -- 256 B. Expect 0x0D at address 4 (see below).

Then diff the flash against nm0506.HEX. Only four points in the whole chip have
ever been verified (0x400-0x47F, 0x800, 0x1000, 0x2000). If corruption exists
anywhere in the rest, this diff finds it -- and that would be the fault, found,
with nothing written.

    ./icsp_read_all.py                # dry run: print the plan, touch nothing
    ./icsp_read_all.py --execute      # actually read
    ./icsp_read_all.py --help-ipecmd  # dump ipecmd's own usage

NOTE ON FLAG SYNTAX: ipecmd's options vary between MPLAB X versions. The flags
here follow the common form, but verify them against the installed version with
--help-ipecmd before trusting a long run. Dry run exists for exactly this.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import os
import subprocess
import sys
from datetime import datetime

DEVICE = "18F452"
TOOL = "PK3"                      # PICkit 3
VENDOR_HEX = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/"
              "Pakon/F-X35 COM SERVER/Config/Firmware/nm0506.HEX")

# From nm0506.HEX. A read that matches these proves the chain is good.
EXPECTED_CONFIG = {"CONFIG4L": 0x81, "CONFIG5L": 0x0F,
                   "CONFIG5H": 0xC0, "CONFIG6H": 0xE0}

# Flags that would modify the chip. Never emitted; refused if ever present.
# -W is NOT here: it means "externally power target", which we require.
# -M is "Program Device"; reads use -G, so blocking -M blocks no read.
FORBIDDEN = ("-F", "-E", "-M")


def find_ipecmd():
    """Locate ipecmd inside any MPLAB X install."""
    # ipecmd.sh FIRST: it launches the bundled Intel JRE under Rosetta. Running
    # the .jar with the system `java` on an arm64 Mac gives an arm64 JVM that
    # cannot load ipecmd's Intel-only native USB libraries -- it starts, then
    # dies at the USB layer.
    pats = ["/Applications/microchip/mplabx/*/mplab_platform/mplab_ipe/ipecmd.sh",
            "/Applications/microchip/mplabx/*/mplab_ipe/ipecmd.sh",
            "/opt/microchip/mplabx/*/mplab_platform/mplab_ipe/ipecmd.sh",
            "/Applications/microchip/mplabx/*/mplab_platform/mplab_ipe/ipecmd.jar",
            "/Applications/microchip/mplabx/*/mplab_ipe/ipecmd.jar"]
    hits = []
    for p in pats:
        hits.extend(glob.glob(p))
    if not hits:
        return None
    # Prefer v5.x: v6.x dropped PICkit 3 support entirely, so picking the
    # highest version (the old sorted()[-1]) was a landmine if both exist.
    v5 = [h for h in hits if "/v5." in h]
    return sorted(v5)[-1] if v5 else sorted(hits)[0]


def bundled_jre(ipecmd):
    """MPLAB's own x86_64 JRE.

    VERIFIED 2026-08-04: ipecmd's USB layer is libUSBAccessLink_3_36.dylib,
    which is x86_64 ONLY. The system java on this machine is an arm64-capable
    OpenJDK 25, and an arm64 JVM cannot load that library -- the jar starts
    fine and then dies at the USB layer, which is a miserable thing to debug
    with a programmer in your hand. MPLAB ships a matching x64 Java 8 JRE;
    use it, and Rosetta does the rest.
    """
    for root in glob.glob("/Applications/microchip/mplabx/*/sys/java/*x64*/"
                          "zulu-8.jre/Contents/Home/bin/java"):
        if os.access(root, os.X_OK):
            return root
    return None


def base_cmd(ipecmd):
    if not ipecmd.endswith(".jar"):
        return [ipecmd]
    jre = bundled_jre(ipecmd)
    if jre:
        return [jre, "-jar", ipecmd]
    # Fall back to forcing x86_64 so Rosetta picks an Intel JVM.
    return ["arch", "-x86_64", "java", "-jar", ipecmd]


def guard(cmd):
    """Refuse anything that could modify the chip."""
    for a in cmd:
        for bad in FORBIDDEN:
            # plain startswith: no legitimate READ flag begins with -F/-E/-M,
            # and the old isalnum() test let "-F/path/x.hex" through because
            # "/" is not alphanumeric.
            if a.startswith(bad):
                raise SystemExit(f"REFUSING: '{a}' can modify the device. "
                                 f"This tool is read-only.")


def run(cmd, execute, label):
    guard(cmd)
    printable = " ".join(f'"{a}"' if " " in a else a for a in cmd)
    print(f"\n=== {label}")
    print(f"    {printable}")
    if not execute:
        print("    [dry run -- not executed]")
        return None
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"    FAILED: {e}")
        return None
    out = (p.stdout or "") + (p.stderr or "")
    for line in out.splitlines():
        print(f"    | {line}")
    return out


def sha(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--execute", action="store_true",
                    help="actually run (default is a dry run)")
    ap.add_argument("--help-ipecmd", action="store_true",
                    help="dump ipecmd's own usage, to verify flag syntax")
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    ipecmd = find_ipecmd()
    if not ipecmd:
        print("ipecmd NOT FOUND.\n")
        print("  Install an older MPLAB X IPE (PICkit 3 support was dropped")
        print("  from recent versions). Expected somewhere like:")
        print("    /Applications/microchip/mplabx/v5.50/mplab_platform/"
              "mplab_ipe/ipecmd.jar")
        print("\n  Machine is arm64 macOS with Rosetta 2 present, so the Intel")
        print("  build should run. See docs/27-icsp-procedure.md.")
        return 1
    print(f"ipecmd: {ipecmd}")
    bc = base_cmd(ipecmd)

    if args.help_ipecmd:
        subprocess.run(bc + ["-?"])
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = args.outdir or os.path.expanduser(f"~/pakon-icsp-backup-{stamp}")
    if args.execute:
        os.makedirs(outdir, exist_ok=True)
    print(f"output: {outdir}")
    print(f"device: {DEVICE}   tool: {TOOL} (PICkit 3)")
    print("\nThe board must be powered from its OWN supply. -W is deliberately")
    print("NOT passed: per the installed ipecmd's help, -W means 'power target")
    print("from tool' and omitting it gives externally-powered, the default.")
    print("Nothing may talk to the scanner over USB while ICSP is active.")

    # No -W: omitting it means the target is externally powered (verified
    # against the installed ipecmd help). The board runs from its own supply.
    dev = ["-P" + DEVICE, "-TP" + TOOL]
    # NOTE: -GF<file> reads the ENTIRE device to file; it does not select a
    # region (regions are -GP/-GE/-GI/-GC). So these are three independent
    # full-device reads, named for that. Three reads is deliberate: comparing
    # their hashes is the only self-contained proof the read is stable and the
    # bootloader backup is genuine.
    boot = os.path.join(outdir, "01-full-device-read-A.hex")
    flash = os.path.join(outdir, "02-full-device-read-B.hex")
    eeprom = os.path.join(outdir, "03-full-device-read-C.hex")

    # Syntax below VERIFIED against the installed ipecmd's own help, 2026-08-04:
    #   -GF<path>  read whole device into a hex file (range not used)
    #   -GI        print device ID to screen
    #   -GC        print configuration words to screen
    #   -GP<x-y>   print program memory range to screen
    # 1. Device ID -- confirms ICSP works, touches nothing.
    run(bc + dev + ["-GI"], args.execute,
        "1. Device ID (-GI) -- confirms ICSP works, touches nothing")

    # 2. Config words -- the trust gate. Compare against EXPECTED_CONFIG below.
    run(bc + dev + ["-GC"], args.execute,
        "2. Config words (-GC) -- THE TRUST GATE, compare to expected values")

    # 3. The bootloader region, to screen, so it is eyeballed before we rely
    #    on any file. 1 KB of identical bytes means a dead read chain.
    run(bc + dev + ["-GP0-3ff"], args.execute,
        "3. Bootloader 0x0-0x3FF to screen -- sanity-check it is not all "
        "one byte value")

    # 2/3/4/5. Reads. -GF is 'get to file'.
    run(bc + dev + ["-GF" + boot], args.execute,
        "4. Full device read A  *** includes the IRREPLACEABLE bootloader ***")
    run(bc + dev + ["-GF" + flash], args.execute,
        "5. Full device read B  (hash must match A -- proves read stability)")
    run(bc + dev + ["-GF" + eeprom], args.execute,
        "6. Full device read C  (third sample; EEPROM lives at 0xF00004)")

    print("\n" + "=" * 68)
    if not args.execute:
        print("DRY RUN. Nothing was executed and nothing was read.")
        print("Verify the flag syntax against the installed MPLAB X version:")
        print("    ./icsp_read_all.py --help-ipecmd")
        print("then re-run with --execute.")
        return 0

    print("Saved:")
    ok = True
    for p in (boot, flash, eeprom):
        h, sz = sha(p), (os.path.getsize(p) if os.path.exists(p) else 0)
        state = f"sha256:{h}  {sz} bytes" if h and sz else "MISSING OR EMPTY"
        if not h or not sz:
            ok = False
        print(f"  {os.path.basename(p):34} {state}")

    print(f"\nExpected config (from nm0506.HEX) -- check these in the output above:")
    for k, v in EXPECTED_CONFIG.items():
        print(f"    {k} = {v:#04x}")
    print("  A match proves the read chain is trustworthy. A mismatch means")
    print("  believe nothing above and debug the connection first.")

    hashes = {sha(p) for p in (boot, flash, eeprom) if sha(p)}
    if len(hashes) == 1:
        print("\n  All three reads are byte-identical. The read is STABLE and")
        print("  the bootloader backup can be trusted.")
    else:
        print(f"\n  *** The three reads DIFFER ({len(hashes)} distinct hashes).")
        print("  The read chain is unstable -- bad connection, marginal VDD, or")
        print("  a failing chip. DO NOT trust this backup and DO NOT write")
        print("  anything until reads are repeatable. ***")
        ok = False

    if not ok:
        print("\n  *** Reads missing, empty, or unstable. Do NOT proceed to any")
        print("  write step. Fix the reads first. ***")
        return 1

    print(f"\nNEXT: diff the flash against the vendor image.")
    print(f"  vendor: {VENDOR_HEX}")
    print("  Only 0x400-0x47F, 0x800, 0x1000 and 0x2000 have ever been")
    print("  verified. If corruption exists in the other ~29 KB, that diff")
    print("  finds it -- the fault, located, with nothing written.")
    print(f"\nCopy {outdir} somewhere off this machine before going further.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
