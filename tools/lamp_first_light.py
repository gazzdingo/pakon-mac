#!/usr/bin/env python3
"""First light: turn the lamp on at a permutation-proof current. VOLATILE ONLY.

Encoding from docs/40 (FN_bDrvLampOn = fcn.1002c5f0), recovered today and NEVER
YET TESTED on hardware. That is the whole reason for the safety design below.

  reg 0x81   5 B   [level_B, level_Ir, level_R, 0x00, level_G]
  reg 0x82  12 B   six LE u16: [on_B][on_Ir][on_R][0x0000][on_G][N]
  reg 0x80   1 B   enable mask: 1 visible, 2 IR, 3 both

WHY THIS IS SAFE EVEN IF THE ENCODING IS WRONG
----------------------------------------------
The clamps (fcn.100203c0) are ASYMMETRIC. With IR off: R<=4, G<=20, B<=20,
Ir<=0. So if our channel order is wrong, a value meant for G (up to 20) could
land in R (max 4) and overdrive it 5x.

Defence: every level byte here is capped at 4 -- the TIGHTEST clamp of any
channel. A permuted payload therefore cannot overdrive anything, because every
byte is legal in every position. That property is enforced below and is the
point of this tool.

Also:
  * IR is forced off (mask 0x01, level_Ir 0, on_Ir 0) -- IR is optional and
    its clamp is the tightest at 8;
  * duty ~0.5, well under the N-2 ceiling;
  * run time capped, and lamp-off is sent from a finally: block so it goes out
    on KeyboardInterrupt or any exception;
  * reg 0x8E is NEVER sent -- no per-unit LampTempWorking exists and the vendor
    never sent one; the board self-regulates (docs/40 sections 1, 2, 8);
  * temperature is read before and after from reg 0x88.

Nothing written here is non-volatile. A power cycle clears all of it.
"""
import argparse, statistics, struct, sys, time
import usb.core, usb.util

VID, PID = 0x0F05, 0xF135
EP_OUT, EP_IN = 0x01, 0x81
LIGHT = 0x40
MAX_LEVEL = 4          # tightest clamp of any channel -> permutation-proof
N_PERIOD = 599         # docs/40: exposure 2498 -> N = 599

def open_dev():
    d = usb.core.find(idVendor=VID, idProduct=PID)
    if d is None: sys.exit("scanner not found -- run tools/pakon_load.py first")
    try: d.set_configuration()
    except Exception: pass
    usb.util.claim_interface(d, 0)
    for ep in (EP_OUT, EP_IN):
        try: d.clear_halt(ep)
        except Exception: pass
    return d

def send(d, pkt, label):
    print(f"  -> {pkt.hex(' ')}   {label}")
    try:
        d.write(EP_OUT, pkt, 2000)
        r = bytes(d.read(EP_IN, 64, 2000))
    except Exception as e:
        print(f"     USB error: {e}"); return None
    ok = len(r) > 3 and r[0] == 7 and r[3] == 0
    print(f"     <- {r.hex(' ')}   {'ok' if ok else 'ERROR'}")
    return r if ok else None

def read_reg(d, reg, n):
    try:
        d.write(EP_OUT, bytes([0x01, 0x03, LIGHT, n, reg]), 2000)
        return bytes(d.read(EP_IN, 64, 2000))
    except Exception:
        return None

def temps(d):
    r = read_reg(d, 0x88, 4)
    if not r or len(r) < 8: return None
    lb, mb = struct.unpack("<HH", r[4:8])
    return lb / 16.0, mb / 16.0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=3, help=f"all channels, max {MAX_LEVEL}")
    ap.add_argument("--duty", type=float, default=0.5)
    ap.add_argument("--seconds", type=float, default=3.0)
    a = ap.parse_args()

    lvl = max(0, min(MAX_LEVEL, a.level))
    if lvl != a.level:
        print(f"level clamped {a.level} -> {lvl} (permutation-proof cap)")
    duty = max(0.0, min(0.9, a.duty))
    secs = max(0.5, min(10.0, a.seconds))
    on = int(N_PERIOD * duty)
    on = min(on, N_PERIOD - 2)

    d = open_dev()
    print(f"levels all={lvl} (cap {MAX_LEVEL}), IR OFF, duty={duty}, "
          f"on={on}, N={N_PERIOD}, {secs}s\n")

    t0 = temps(d)
    print(f"temps before: {t0}\n" if t0 else "temps before: unreadable\n")

    # The init block. THIS IS REQUIRED -- without it the lamp does not light,
    # confirmed on hardware: an identical sequence minus these six writes
    # produced no light, and 0x83 stayed 0x00. With them, 0x83 goes to 0x02 and
    # the lamp lights. 0x8E is deliberately absent (docs/40).
    for reg, payload in ((0x8F, bytes([0xE8, 0xFF, 0x18, 0x00])),
                         (0x8C, bytes([0xE0, 0xFF, 0x20, 0x00])),
                         (0x8B, bytes([0xF0, 0x00, 0x20, 0x03])),
                         (0x8D, bytes([0xA0, 0x00, 0x70, 0x03]))):
        send(d, bytes([0x02, len(payload) + 3, LIGHT, len(payload), reg]) + payload,
             f"init reg {reg:#04x}")
    send(d, bytes([0x02, 0x04, LIGHT, 0x01, 0xD0, 0x00]), "init reg 0xD0 = 00")
    send(d, bytes([0x02, 0x04, LIGHT, 0x01, 0xD1, 0x01]), "init reg 0xD1 = 01")

    send(d, bytes([0x02, 0x04, LIGHT, 0x01, 0x80, 0x00]), "lamp off, known state")

    # 0x82: [on_B][on_Ir=0][on_R][0x0000][on_G][N]  -- six LE u16
    pwm = struct.pack("<HHHHHH", on, 0, on, 0, on, N_PERIOD)
    send(d, bytes([0x02, 0x0F, LIGHT, 0x0C, 0x82]) + pwm, "PWM on-counts + N")

    # 0x81: [level_B, level_Ir=0, level_R, 0x00, level_G]
    send(d, bytes([0x02, 0x08, LIGHT, 0x05, 0x81, lvl, 0, lvl, 0, lvl]), "levels")

    try:
        send(d, bytes([0x02, 0x04, LIGHT, 0x01, 0x80, 0x01]), "ENABLE visible only")
        print(f"\n  *** LOOK AT THE SCANNER NOW -- {secs}s ***\n")
        time.sleep(secs)
        t1 = temps(d)
        print(f"temps during/after: {t1}")
        s = read_reg(d, 0x83, 1)
        if s: print(f"status 0x83: {s.hex(' ')}")
    finally:
        print()
        send(d, bytes([0x02, 0x04, LIGHT, 0x01, 0x80, 0x00]), "LAMP OFF")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
