#!/usr/bin/env python3
"""Live light meter on EP 0x86. READ ONLY -- nothing is written.

Prints the CCD mean once a second so you can change the illumination and watch
it react, instead of running two captures and comparing afterwards.

Cover the film slot with your hand, or shine a phone flashlight into it. If the
number moves, the sensor path responds to light -- which is the claim docs/06
made when it declared this the project blocker.

Flushes the free-running FIFO before every sample (docs/06:139), otherwise you
measure stale buffer contents rather than the present.
"""
import statistics, sys, time
import usb.core, usb.util

dev = usb.core.find(idVendor=0x0F05, idProduct=0xF135)
if dev is None:
    sys.exit("scanner not found -- run tools/pakon_load.py first")
try: dev.set_configuration()
except Exception: pass
usb.util.claim_interface(dev, 0)
try: dev.clear_halt(0x86)
except Exception: pass

SIZE = 0x8000
print("live CCD level -- cover the film slot / shine a light in. ctrl-C to stop.\n")
base = None
try:
    while True:
        for _ in range(6):                      # flush stale FIFO
            try: dev.read(0x86, SIZE, 2000)
            except Exception: pass
        try:
            b = bytes(dev.read(0x86, SIZE, 2000))
        except Exception:
            print("  no data"); time.sleep(1); continue
        v = [int.from_bytes(b[i:i+2], "little") for i in range(0, len(b)-1, 2)]
        ch = [v[k::3] for k in range(3)]
        m = statistics.mean(v)
        if base is None:
            base = m
        d = m - base
        bar = "#" * max(0, min(50, int(abs(d) / 4)))
        print(f"  mean {m:8.1f}   R {statistics.mean(ch[0]):7.1f}  "
              f"G {statistics.mean(ch[1]):7.1f}  B {statistics.mean(ch[2]):7.1f}   "
              f"delta {d:+8.1f} {bar}")
        time.sleep(1)
except KeyboardInterrupt:
    print("\nstopped.")
