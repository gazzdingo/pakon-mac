"""Correlate registry write times against the windows when the scanner was
physically attached over USB.

This is the step that establishes WHICH scanner each calibration key belongs to.
The guest clock runs behind host-local time, so the offset must be corrected
before the comparison means anything.

Inputs:
  pakon_registry_full.json   produced by extract_hive.py
  parallels.log              from the .pvm bundle (attach windows read out of it)

Run from the research/windows-registry directory.
"""
import json, datetime, os

HERE = os.path.dirname(os.path.abspath(__file__))
JSON = os.path.join(HERE, "..", "pakon_registry_full.json")

# Guest-clock offset, established from a key whose write we can pin to a known
# host-side event: HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion was written
# at 2025-07-22 02:57:19 guest, during the VM's first boot, which parallels.log
# timestamps 2025-07-22 10:55:11 host-local.
GUEST_REF = datetime.datetime(2025, 7, 22, 2, 57, 19)
HOST_REF = datetime.datetime(2025, 7, 22, 10, 55, 11)
OFFSET = HOST_REF - GUEST_REF          # 7:57:52

# Scanner attach windows, host-local, from parallels.log.
# Start  = "[USB] ConnectToBus: result: 0 ... (F135-USB Film Scanner)"
# End    = "DisconnectFromBus: result 0 ... <F135-USB Film Scanner>"
WINDOWS = [
    ("2025-07-23 12:04:22", "2025-07-23 12:44:15"),
    ("2025-07-23 13:12:24", "2025-07-23 14:15:40"),
    ("2025-07-27 20:22:57", "2025-07-27 20:42:44"),
    ("2025-07-28 10:23:24", "2025-07-28 11:09:42"),
]

def parse(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

W = [(parse(a), parse(b)) for a, b in WINDOWS]

print("guest clock runs behind host-local by:", OFFSET)
print()
print("scanner attached (host-local):")
for a, b in W:
    print("   %s -> %s   (%s)" % (a, b, b - a))
print()

data = json.load(open(JSON))
print("%-26s %-20s %-20s %s" % ("calibration key", "guest write", "= host local", "verdict"))
print("-" * 92)
for e in data:
    names = {v["name"]: v["value"] for v in e["values"]}
    if "Current_R" not in names:
        continue
    g = parse(e["last_written"][:19])
    h = g + OFFSET
    inside = any(a <= h <= b for a, b in W)
    short = e["path"].split("Scan\\")[1]
    if g.year >= 2025:
        verdict = "ATTACHED -> ours" if inside else "2025 but outside a window (!)"
    else:
        verdict = "pre-dates this VM -> serial 16275's"
    print("%-26s %-20s %-20s %s" % (short, g, h, verdict))
