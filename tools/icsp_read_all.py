#!/usr/bin/env python3
"""Read U11 (PIC18F452) out through a PICkit 3 via ipecmd. READ ONLY.

This is the "read everything before writing anything" step. No copy of the
PICM bootloader (0x0000-0x03FF) exists anywhere -- 348 vendor HEX files were
parsed and every one starts at 0x400. If it is ever clobbered it is gone
permanently, so it comes off the chip first, before anything else happens.

THE OWNER'S RULES, implemented here verbatim:
  1. nothing is deleted -- there is no write path in this file at all;
  2. everything is read -- bootloader, full flash, config words, internal
     EEPROM, user IDs, in every read;
  3. the full device is read FIVE times and the reads are hashed and compared
     -- per region, not just whole-file -- and this tool REFUSES (exit 1,
     explicit "do not write" message) unless all five agree everywhere.

SAFETY DESIGN
-------------
* DRY RUN BY DEFAULT. Nothing runs until --execute is passed. Without it this
  prints the exact commands it would issue so they can be read first.
* No write path exists in this file. The programming (-F), erase (-E) and
  program-device (-M) flags are never emitted, and guard() refuses to run any
  command containing them (or -U/-S/-Z, the other programming-family flags).
* Matching hashes alone are NOT trusted: a dead read chain returns the same
  garbage five times. The config words must also match the values known from
  nm0506.HEX, and the bootloader region must look like real code, before the
  reads are called good.
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
3. Bootloader     -- to screen, eyeballed before any file is trusted.
4. FIVE full-device reads -- 32 KB flash + config + EEPROM + IDs, five times.
5. Automatic verification -- parse all five files, hash per region, compare,
   check config against known values, check bootloader entropy, and REFUSE
   on any disagreement.

Then diff the flash against nm0506.HEX with flash_diff.py. Only four points in
the whole chip have ever been verified (0x400-0x47F, 0x800, 0x1000, 0x2000).
If corruption exists anywhere in the rest, that diff finds it -- and that
would be the fault, found, with nothing written.

    ./icsp_read_all.py                # dry run: print the plan, touch nothing
    ./icsp_read_all.py --execute      # actually read (5x) and verify
    ./icsp_read_all.py --verify DIR   # re-verify previously saved reads
    ./icsp_read_all.py --self-test    # prove the comparison logic, no hardware
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
import tempfile
from datetime import datetime

DEVICE = "18F452"
TOOL = "PK3"                      # PICkit 3
READS = 5                         # owner requirement: five reads, compared
LETTERS = "ABCDE"
VENDOR_HEX = ("/Users/guy/Downloads/Pakon Update 2/fx35install/program files/"
              "Pakon/F-X35 COM SERVER/Config/Firmware/nm0506.HEX")

# From nm0506.HEX (re-verified by parsing the file 2026-08-05):
#   0x300006 CONFIG4L = 0x81, 0x300008 CONFIG5L = 0x0F,
#   0x300009 CONFIG5H = 0xC0, 0x30000B CONFIG6H = 0xE0.
# A read that matches these proves the chain is good. These four are the
# documented trust gate (docs/27 section 3); the remaining config bytes are
# printed for the record but not gated, because unimplemented bits can read
# differently from the file image.
EXPECTED_CONFIG = {0x300006: ("CONFIG4L", 0x81), 0x300008: ("CONFIG5L", 0x0F),
                   0x300009: ("CONFIG5H", 0xC0), 0x30000B: ("CONFIG6H", 0xE0)}

CONFIG_LO, CONFIG_HI = 0x300000, 0x30000E
EEPROM_LO, EEPROM_HI = 0xF00000, 0xF00100
BOOT_LO, BOOT_HI = 0x000000, 0x000400

# (name, lo, hi, required) -- required regions must be present in the read
# files or verification fails. User IDs are optional (ipecmd may omit them).
REGIONS = [
    ("bootloader 0x0000-0x03FF", BOOT_LO, BOOT_HI, True),
    ("application flash 0x0400-0x7FFF", 0x000400, 0x008000, True),
    ("user IDs 0x200000-0x200007", 0x200000, 0x200008, False),
    ("config words 0x300000-0x30000D", CONFIG_LO, CONFIG_HI, True),
    ("internal EEPROM (256 B)", EEPROM_LO, EEPROM_HI, True),
]

# U11 internal EEPROM index map, recovered from the boot-path disassembly
# (docs/27 section 4). Printed with the verification so index 5 -- the
# persisted fault code that has never been readable -- is surfaced instantly.
EEPROM_MAP = {0: 'bootloader "application valid" gate -- expect 0xAA',
              2: "gates the fault-code clear on the warm path",
              4: "-> RAM 0x135/0x138 (suspected stray 0x0D; 13 = default gain)",
              5: "*** THE PERSISTED FAULT CODE -- compare to the LED nibble ***",
              6: "-> RAM 0x027"}

# Flags that would modify the chip. Never emitted; refused if ever present.
# -W is NOT here: it means "power target from tool"; omitting it selects
#    "externally power target", which we require (see module docstring).
# -M is "Program Device"; reads use -G, so blocking -M blocks no read.
# -F selects the hex file to program; -E erases; -U programs OSCCAL-type
#    memory on parts that have it; -S is SQTP serialisation (programming
#    only); -Z is a programming-range modifier. None is ever needed to read.
FORBIDDEN = ("-F", "-E", "-M", "-U", "-S", "-Z")


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


def native_lib_dir(ipecmd):
    """mplab_platform/bin -- where libUSBAccessLink lives.

    VERIFIED 2026-08-05: without -Djava.library.path pointing here, ipecmd
    reports "Programmer not found" even though the PICkit 3 is enumerated and
    the IPE GUI can see it by serial number. The GUI launches via nbexec with
    paths already set up; `java -jar` does not, so it loads far enough to read
    the device family pack and then cannot enumerate tools at all. Setting this
    changes the failure from "Programmer not found" to "Connection Failed",
    i.e. programmer found, target absent -- which is correct with nothing wired.
    """
    for d in glob.glob("/Applications/microchip/mplabx/*/mplab_platform/bin"):
        if glob.glob(os.path.join(d, "libUSBAccessLink*")):
            return d
    return None


def base_cmd(ipecmd):
    if not ipecmd.endswith(".jar"):
        return [ipecmd]
    jre = bundled_jre(ipecmd)
    libdir = native_lib_dir(ipecmd)
    if jre:
        cmd = [jre]
        if libdir:
            cmd.append("-Djava.library.path=" + libdir)
        return cmd + ["-jar", ipecmd]
    # Fall back to forcing x86_64 so Rosetta picks an Intel JVM.
    return ["arch", "-x86_64", "java", "-jar", ipecmd]


def guard(cmd):
    """Refuse anything that could modify the chip.

    Case-insensitive, prefix-based: no legitimate READ flag begins with any
    FORBIDDEN prefix (reads are -G*, device/tool selection is -P/-TP), and
    the old isalnum() test let "-F/path/x.hex" through because "/" is not
    alphanumeric.
    """
    for a in cmd:
        up = a.upper()
        for bad in FORBIDDEN:
            if up.startswith(bad):
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


def file_hashes(path):
    """(md5, sha256) of the raw file. The owner asked for 'the md5 or
    something'; both are printed, and the real comparison is per-region on
    the PARSED contents, which also survives cosmetic HEX re-formatting."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return None, None
    return hashlib.md5(data).hexdigest(), hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------- verification

def load_hex(path):
    """Parse Intel HEX, VALIDATING record checksums.

    Returns (mem dict, bad_record_count). Bad records are counted, not
    silently skipped -- a truncated or corrupted transfer must fail loudly.
    """
    mem, ext, bad = {}, 0, 0
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or not line.startswith(":"):
                continue
            try:
                b = bytes.fromhex(line[1:])
            except ValueError:
                bad += 1
                continue
            if len(b) < 5 or (sum(b) & 0xFF) != 0 or len(b) != b[0] + 5:
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
    return mem, bad


def region_digest(mem, lo, hi):
    """sha256 over the region, absent addresses filled with 0xFF.

    Safe ONLY because verify_reads first proves all files cover identical
    address sets; the fill can therefore never mask a file that omitted data
    another file contains."""
    return hashlib.sha256(
        bytes(mem.get(a, 0xFF) for a in range(lo, hi))).hexdigest()


def verify_reads(paths, quiet=False):
    """The five-read comparison. Returns (ok, failures).

    failures is a list of (check, detail) tuples, so the self-test can prove
    -- not assume -- that the right check fires for the right corruption.
    """
    say = (lambda *a, **k: None) if quiet else print
    failures = []
    say("\n" + "=" * 68)
    say(f"VERIFYING {len(paths)} READS -- all must agree, per region")

    say("\nwhole-file hashes (for the record; the real comparison is below):")
    images = {}
    for path, letter in zip(paths, LETTERS):
        md5, s256 = file_hashes(path)
        if md5 is None:
            failures.append(("missing-file", letter))
            say(f"  read {letter}: {os.path.basename(path)}  MISSING")
            continue
        say(f"  read {letter}: md5 {md5}  sha256 {s256[:16]}...")
        mem, bad = load_hex(path)
        if bad:
            failures.append(("malformed-records", letter))
            say(f"          *** {bad} malformed/bad-checksum record(s) ***")
        if not mem:
            failures.append(("empty-file", letter))
            say(f"          *** no data parsed ***")
            continue
        images[letter] = mem
    if len(images) < len(paths):
        say("\n*** Not every read produced a parseable file. ***")
        return False, failures

    # 1. Identical address coverage. If one read omits addresses another
    #    contains, they are NOT the same read, whatever the hashes say.
    sets = {letter: frozenset(mem) for letter, mem in images.items()}
    baseline = sets[LETTERS[0]]
    for letter, s in sets.items():
        if s != baseline:
            failures.append(("address-coverage", letter))
    if any(f[0] == "address-coverage" for f in failures):
        say("\n*** ADDRESS COVERAGE DIFFERS BETWEEN READS ***")
        for letter, s in sorted(sets.items()):
            say(f"  read {letter}: {len(s)} addressed bytes")
        say("  A read that omits regions another read contains is not the")
        say("  same read. Do not trust any of them; read again.")

    # 2. Required regions present (checked on read A; coverage equality
    #    extends the result to all).
    a_img = images[LETTERS[0]]
    say("\nregion presence (read A):")
    for name, lo, hi, required in REGIONS:
        n = sum(1 for a in a_img if lo <= a < hi)
        tag = f"{n}/{hi - lo} bytes"
        if n == 0 and required:
            failures.append(("region-missing", name))
            tag += "  *** REQUIRED REGION ABSENT ***"
        elif n == 0:
            tag += "  (absent -- optional)"
        say(f"  {name:38} {tag}")
    if any(f[0] == "region-missing" and "EEPROM" in f[1] for f in failures):
        say("\n  The internal EEPROM did not appear in the -GF output. Either")
        say("  this ipecmd's -GF omits EEPROM, or the EEPROM read failed.")
        say("  Do NOT proceed on guesswork: check --help-ipecmd for the")
        say("  EEPROM region read (-GE style) and capture it explicitly.")

    # 3. Per-region hashes across all reads -- the owner's requirement 3.
    say(f"\nper-region sha256 across the {len(paths)} reads:")
    for name, lo, hi, required in REGIONS:
        if not any(lo <= a < hi for a in a_img):
            continue                      # absence already handled above
        digests = {letter: region_digest(mem, lo, hi)
                   for letter, mem in sorted(images.items())}
        groups = {}
        for letter, dg in digests.items():
            groups.setdefault(dg, []).append(letter)
        if len(groups) == 1:
            say(f"  {name:38} IDENTICAL in all "
                f"{len(digests)}  {next(iter(groups))[:16]}...")
        else:
            majority = max(groups.values(), key=len)
            outliers = sorted(set(digests) - set(majority))
            failures.append(("region-mismatch",
                             f"{name}: reads {','.join(outliers)} differ"))
            say(f"  {name:38} *** {len(groups)} DISTINCT CONTENTS ***")
            for dg, letters in sorted(groups.items(), key=lambda kv: -len(kv[1])):
                say(f"      reads {','.join(letters)}: {dg[:16]}...")
            say(f"      -> reads {','.join(outliers)} disagree with the "
                f"majority ({','.join(majority)})")

    # 4. Config words against the values known from nm0506.HEX. Five
    #    identical reads of a BROKEN chain would still match each other;
    #    this is the independent anchor that says the chain reads truth.
    say("\nconfig-word trust gate (known values from nm0506.HEX):")
    for addr, (cname, want) in sorted(EXPECTED_CONFIG.items()):
        got = a_img.get(addr)
        if got is None:
            failures.append(("config-unread", cname))
            say(f"  {cname} @ {addr:#08x}: NOT READ")
        elif got != want:
            failures.append(("config-mismatch", f"{cname}={got:#04x}"))
            say(f"  {cname} @ {addr:#08x}: expect {want:#04x}  got {got:#04x}"
                f"  *** MISMATCH -- read chain not trustworthy ***")
        else:
            say(f"  {cname} @ {addr:#08x}: {got:#04x}  OK")
    other_cfg = {a: v for a, v in a_img.items()
                 if CONFIG_LO <= a < CONFIG_HI and a not in EXPECTED_CONFIG}
    if other_cfg:
        say("  (for the record: " + "  ".join(
            f"{a:#08x}={v:#04x}" for a, v in sorted(other_cfg.items())) + ")")

    # 5. Bootloader entropy. Identical garbage is still garbage: 1 KB of a
    #    stuck bus pattern hashes identically five times.
    boot_vals = {a_img[a] for a in a_img if BOOT_LO <= a < BOOT_HI}
    if boot_vals:
        if len(boot_vals) <= 1:
            failures.append(("bootloader-dead-chain", None))
            say(f"\nbootloader: *** ALL bytes read "
                f"{next(iter(boot_vals)):#04x} -- DEAD READ CHAIN. Five "
                f"matching reads of a stuck line still match. ***")
        elif len(boot_vals) < 16:
            failures.append(("bootloader-low-entropy", len(boot_vals)))
            say(f"\nbootloader: *** only {len(boot_vals)} distinct byte "
                f"values in 1 KB -- implausible for real code ***")
        else:
            say(f"\nbootloader: {len(boot_vals)} distinct byte values "
                f"(looks like real code)")

    # 6. The EEPROM bytes we came for, printed while everyone is looking.
    if any(EEPROM_LO <= a < EEPROM_HI for a in a_img):
        say("\ninternal EEPROM, decoded indices:")
        for idx, meaning in EEPROM_MAP.items():
            v = a_img.get(EEPROM_LO + idx)
            vs = f"{v:#04x}" if v is not None else "absent"
            say(f"  [{idx}] = {vs:6}  {meaning}")

    ok = not failures
    say("\n" + "=" * 68)
    if ok:
        say(f"ALL {len(paths)} READS AGREE, in every region, the config words")
        say("match the known values, and the bootloader looks like real code.")
        say("The read is STABLE and the bootloader backup can be trusted.")
    else:
        say("*** VERIFICATION FAILED ***")
        for check, detail in failures:
            say(f"  - {check}" + (f": {detail}" if detail else ""))
        say("\n  DO NOT TRUST THIS BACKUP AND DO NOT WRITE ANYTHING -- not a")
        say("  test program, not a reflash, nothing -- until five consecutive")
        say("  reads agree. Bad connection, marginal VDD, or a failing chip:")
        say("  find out which first. Nothing has been lost by stopping here.")
    return ok, failures


# ---------------------------------------------------------------- self-test

def write_hex(mem, path):
    """Emit Intel HEX (type 4 + type 0 + EOF) for the self-test."""
    def rec(rtype, addr, data):
        body = bytes([len(data), (addr >> 8) & 0xFF, addr & 0xFF, rtype]) + data
        ck = (-sum(body)) & 0xFF
        return ":" + (body + bytes([ck])).hex().upper()
    lines, ext = [], None
    addrs = sorted(mem)
    i = 0
    while i < len(addrs):
        a = addrs[i]
        hi = a >> 16
        if hi != ext:
            lines.append(rec(4, 0, bytes([hi >> 8, hi & 0xFF])))
            ext = hi
        chunk = [a]
        while (len(chunk) < 16 and i + len(chunk) < len(addrs)
               and addrs[i + len(chunk)] == a + len(chunk)
               and (addrs[i + len(chunk)] >> 16) == hi):
            chunk.append(addrs[i + len(chunk)])
        lines.append(rec(0, a & 0xFFFF, bytes(mem[x] for x in chunk)))
        i += len(chunk)
    lines.append(":00000001FF")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def synth_image():
    """A synthetic but realistic full-device read."""
    img = {}
    # bootloader: deterministic pseudo-code, plenty of distinct values
    for a in range(BOOT_LO, BOOT_HI):
        img[a] = (a * 7 + 3) & 0xFF
    # application: the real vendor image if present, else pseudo-data
    vendor = {}
    if os.path.exists(VENDOR_HEX):
        vendor, _ = load_hex(VENDOR_HEX)
    for a in range(0x400, 0x8000):
        img[a] = vendor.get(a, 0xFF) if vendor else (a * 13 + 5) & 0xFF
    # config: the known values
    cfg = {0x300000: 0x00, 0x300001: 0x26, 0x300002: 0x06, 0x300003: 0x0D,
           0x300004: 0x00, 0x300005: 0x01, 0x300006: 0x81, 0x300007: 0x00,
           0x300008: 0x0F, 0x300009: 0xC0, 0x30000A: 0x0F, 0x30000B: 0xE0,
           0x30000C: 0x0F, 0x30000D: 0x40}
    img.update(cfg)
    # EEPROM: app-valid gate, the suspected 0x0D, a fault code
    for i in range(256):
        img[EEPROM_LO + i] = 0xFF
    img[EEPROM_LO + 0] = 0xAA
    img[EEPROM_LO + 4] = 0x0D
    img[EEPROM_LO + 5] = 0x0B
    return img


def self_test():
    """Prove the 5-read comparison catches what it must. No hardware."""
    print("SELF-TEST -- synthetic reads, no hardware, nothing touched\n")
    base = synth_image()
    results = []

    def case(name, mutators, expect_ok, expect_check=None):
        """mutators: list of READS callables (or None) applied per read."""
        with tempfile.TemporaryDirectory() as td:
            paths = []
            for i in range(READS):
                img = dict(base)
                if mutators and mutators[i]:
                    mutators[i](img)
                p = os.path.join(td, f"read-{LETTERS[i]}.hex")
                write_hex(img, p)
                paths.append(p)
            ok, failures = verify_reads(paths, quiet=True)
        checks = [c for c, _ in failures]
        passed = (ok == expect_ok and
                  (expect_check is None or expect_check in checks))
        results.append((name, passed, ok, checks))
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
        print(f"        expected ok={expect_ok}"
              + (f", check '{expect_check}'" if expect_check else "")
              + f"  ->  got ok={ok}, checks={sorted(set(checks)) or '[]'}")

    def corrupt_app(img):
        img[0x2C62] ^= 0x54            # the I2C address literal

    def drop_eeprom(img):
        for a in range(EEPROM_LO, EEPROM_HI):
            img.pop(a, None)

    def flip_config(img):
        img[0x300006] = 0x83           # CONFIG4L wrong -> LVP bit suspect

    def dead_boot(img):
        for a in range(BOOT_LO, BOOT_HI):
            img[a] = 0x00

    def corrupt_eeprom_byte(img):
        img[EEPROM_LO + 5] = 0x0C      # a different fault code in one read

    case("1. five identical reads -> accepted",
         None, True)
    case("2. read D corrupted in application flash -> refused, D named",
         [None, None, None, corrupt_app, None], False, "region-mismatch")
    case("3. read B missing the EEPROM region -> refused",
         [None, drop_eeprom, None, None, None], False, "address-coverage")
    case("4. EEPROM byte differs in read C -> refused (EEPROM compared too)",
         [None, None, corrupt_eeprom_byte, None, None], False,
         "region-mismatch")
    case("5. all five identical but bootloader is all-0x00 -> refused\n"
         "        (proof that matching hashes alone are NOT trusted)",
         [dead_boot] * READS, False, "bootloader-dead-chain")
    case("6. all five identical but CONFIG4L wrong -> refused",
         [flip_config] * READS, False, "config-mismatch")
    case("7. EEPROM absent from ALL five reads -> refused",
         [drop_eeprom] * READS, False, "region-missing")

    bad = [r for r in results if not r[1]]
    print(f"\n{'ALL ' + str(len(results)) + ' CASES PASS' if not bad else str(len(bad)) + ' CASE(S) FAILED'}"
          f" -- the comparison logic is {'proven' if not bad else 'BROKEN; do not use --execute'}.")
    return 0 if not bad else 1


# --------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--execute", action="store_true",
                    help="actually run (default is a dry run)")
    ap.add_argument("--help-ipecmd", action="store_true",
                    help="dump ipecmd's own usage, to verify flag syntax")
    ap.add_argument("--verify", nargs="+", metavar="PATH",
                    help="verify previously saved reads (files, or one "
                         "directory containing *full-device-read*.hex)")
    ap.add_argument("--self-test", action="store_true",
                    help="prove the 5-read comparison logic, no hardware")
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.verify:
        paths = args.verify
        if len(paths) == 1 and os.path.isdir(paths[0]):
            paths = sorted(glob.glob(os.path.join(paths[0],
                                                  "*full-device-read*.hex")))
        if not paths:
            sys.exit("nothing to verify")
        print(f"verifying {len(paths)} file(s):")
        for p in paths:
            print(f"  {p}")
        ok, _ = verify_reads(paths)
        return 0 if ok else 1

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
    print(f"device: {DEVICE}   tool: {TOOL} (PICkit 3)   reads: {READS}")
    print("\nThe board must be powered from its OWN supply. -W is deliberately")
    print("NOT passed: per the installed ipecmd's help, -W means 'power target")
    print("from tool' and omitting it gives externally-powered, the default.")
    print("Nothing may talk to the scanner over USB while ICSP is active.")

    # No -W: omitting it means the target is externally powered (verified
    # against the installed ipecmd help). The board runs from its own supply.
    # -OD = "VDD First" (default is VPP First). Establishes and senses the
    # target supply BEFORE energising the ~12V VPP, which is the safer ordering
    # on a header whose pinout we have not fully verified. Found in the
    # installed ipecmd's own help, 2026-08-05.
    dev = ["-P" + DEVICE, "-TP" + TOOL, "-OD"]
    # NOTE: -GF<file> reads the ENTIRE device to file; it does not select a
    # region (regions are -GP/-GE/-GI/-GC). So these are FIVE independent
    # full-device reads. Five is the owner's requirement: comparing their
    # per-region hashes is the only self-contained proof the read is stable
    # and the bootloader backup is genuine.
    reads = [os.path.join(outdir, f"{i + 4:02d}-full-device-read-{L}.hex")
             for i, L in enumerate(LETTERS[:READS])]

    # Syntax below VERIFIED against the installed ipecmd's own help, 2026-08-04:
    #   -GF<path>  read whole device into a hex file (range not used)
    #   -GI        print device ID to screen
    #   -GC        print configuration words to screen
    #   -GP<x-y>   print program memory range to screen
    # 1. Device ID -- confirms ICSP works, touches nothing.
    run(bc + dev + ["-GI"], args.execute,
        "1. Device ID (-GI) -- confirms ICSP works, touches nothing")

    # 2. Config words -- the trust gate, eyeballed live; also re-checked
    #    automatically from the read files below.
    run(bc + dev + ["-GC"], args.execute,
        "2. Config words (-GC) -- THE TRUST GATE, compare to expected values")

    # 3. The bootloader region, to screen, so it is eyeballed before we rely
    #    on any file. 1 KB of identical bytes means a dead read chain.
    run(bc + dev + ["-GP0-3ff"], args.execute,
        "3. Bootloader 0x0-0x3FF to screen -- sanity-check it is not all "
        "one byte value")

    # 4..8. FIVE full-device reads.
    for i, path in enumerate(reads):
        note = {0: "  *** includes the IRREPLACEABLE bootloader ***",
                READS - 1: "  (last of five)"}.get(i, "")
        run(bc + dev + ["-GF" + path], args.execute,
            f"{i + 4}. Full device read {LETTERS[i]} of {READS}{note}")

    print("\n" + "=" * 68)
    if not args.execute:
        print("DRY RUN. Nothing was executed and nothing was read.")
        print("After --execute, the five reads are parsed and compared")
        print("automatically (per region: bootloader / flash / config /")
        print("EEPROM / IDs) and this tool exits non-zero, telling you NOT")
        print("to proceed, unless all five agree everywhere, the config")
        print("words match nm0506.HEX, and the bootloader looks like code.")
        print("Verify the flag syntax against the installed MPLAB X version:")
        print("    ./icsp_read_all.py --help-ipecmd")
        print("then re-run with --execute.")
        return 0

    ok, _ = verify_reads(reads)
    if not ok:
        print("\n*** Reads missing, incomplete, or unstable. Do NOT proceed")
        print("to any write step. Fix the reads first. ***")
        return 1

    print(f"\nNEXT: diff the flash against the vendor image:")
    print(f"  ./flash_diff.py {reads[0]}")
    print(f"  vendor: {VENDOR_HEX}")
    print("  Only 0x400-0x47F, 0x800, 0x1000 and 0x2000 have ever been")
    print("  verified. If corruption exists in the other ~29 KB, that diff")
    print("  finds it -- the fault, located, with nothing written.")
    print(f"\nCopy {outdir} somewhere off this machine (twice) before going")
    print("further. The bootloader bytes in these files exist nowhere else")
    print("on Earth.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
