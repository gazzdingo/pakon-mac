#!/usr/bin/env python3
"""ONE read of both I2C EEPROMs, straight to disk. READ ONLY.

WHY ONE
-------
Established 2026-08-05 on hardware: these EEPROMs return good data on the
FIRST transaction after a power cycle and DEGRADE on every read after it.
The second read of a cycle already differed in 180 of 256 bytes on 0x52, and
0x51 read entirely 0xFF. The devices keep ACKing throughout -- status stays
"ok" -- so nothing in the status bytes reveals that the data is now junk.

A five-pass hash comparison is therefore actively WRONG here: it converges on
stable garbage, because passes 3-5 agree with each other and disagree with
reality. (That happened: 7/7 "STABLE" all-0xFF.)

The correct protocol is: power cycle, ONE read, save it, compare against
reads taken in OTHER power cycles. Agreement across cycles is the real proof.

    ./eeprom_oneshot.py                    # one read, saved
    ./eeprom_oneshot.py --compare <dir>    # also diff against a previous save
"""
import sys, time, os, hashlib, argparse
import usb.core
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pakon_load import Fx2, HexImage   # noqa: E402

VIN, A0 = 0xC0, 0xA0
FW = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                  "fx2", "eeprom_dump_all.ihx")
STAT = {0: "ok", 1: "no ACK dev addr", 2: "no ACK word addr",
        3: "no ACK read addr", 4: "bus error"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare", help="previous save dir to diff against")
    args = ap.parse_args()

    d = None
    for v, p in ((0x04B4, 0x8613), (0x0F05, 0xF235), (0x0547, 0x1002)):
        d = usb.core.find(idVendor=v, idProduct=p)
        if d is not None:
            break
    if d is None:
        sys.exit("scanner not found -- power it on, and do NOT run pakon_load first")
    print(f"device {d.idVendor:04x}:{d.idProduct:04x}")
    print("This must be the FIRST EEPROM access since power-on.\n")

    fx = Fx2(d)
    fx.reset_8051(True)
    fx.download(HexImage.load(FW), False)
    fx.reset_8051(False)
    time.sleep(2.5)
    fx.reset_8051(True)
    rd = lambda a, n: bytes(d.ctrl_transfer(VIN, A0, a, 0, n, 5000))
    st, b51, b52 = rd(0x0600, 8), rd(0x0400, 256), rd(0x0500, 256)

    outdir = os.path.expanduser("~/pakon-eeprom-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(outdir, exist_ok=True)
    print(f"status: 0x51={STAT.get(st[0], st[0])}  0x52={STAT.get(st[1], st[1])}  "
          f"marker={st[2:6].hex()}")
    ok = True
    for name, data in (("51", b51), ("52", b52)):
        fn = os.path.join(outdir, f"eeprom_{name}.bin")
        open(fn, "wb").write(data)
        nf = sum(1 for x in data if x != 0xFF)
        print(f"\ndevice 0x{name}: {nf}/256 non-0xFF")
        print(f"  sha256 {hashlib.sha256(data).hexdigest()}")
        print(f"  md5    {hashlib.md5(data).hexdigest()}")
        print(f"  saved  {fn}")
        if args.compare:
            prev_fn = os.path.join(os.path.expanduser(args.compare),
                                   f"eeprom_{name}.bin")
            if os.path.exists(prev_fn):
                prev = open(prev_fn, "rb").read()
                same = prev == data
                print(f"  vs {os.path.basename(args.compare)}: "
                      f"{'IDENTICAL' if same else 'DIFFERS'}")
                if not same:
                    dd = [i for i in range(min(len(prev), len(data)))
                          if prev[i] != data[i]]
                    print(f"     {len(dd)} bytes differ, first at {dd[0]:#04x}")
                    ok = False
    print(f"\n{outdir}")
    if args.compare:
        print("VERIFIED -- two separate power cycles agree." if ok
              else "*** MISMATCH -- one of these reads is degraded. ***")
    print("\nDo NOT read again without power-cycling first.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
