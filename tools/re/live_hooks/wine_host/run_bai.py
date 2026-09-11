#!/usr/bin/env python3
"""Drive bai_host.exe, harvesting blocked CRITICAL_SECTION addresses.

Replayed locks come back in whatever state the vendor process left them, so a
held one blocks forever (docs/74 §126). Their addresses are not knowable in
advance -- they belong to per-call objects -- but Wine names each one as it
blocks:

    err:sync:RtlpWaitForCriticalSection section 08DFA1EC ... blocked by 0000

So: run, harvest the address, add it to the re-init list, run again. Repeat
until every call completes or no new lock appears (which would mean the block
is something other than a lock, and the loop must not spin on it).

Re-initialising a lock is not fabricating an input -- it restores the only
state a lock can have in a fresh single-threaded process, and touches no pixel
data. Everything the function computes from is as captured.
"""
import re
import subprocess
import sys
import os

HOST = "bai_host.exe"
DLL = "PakonIMAu.dll"
BLOB = sys.argv[1] if len(sys.argv) > 1 else "bai_args_v34.bin"
MAX_ROUNDS = int(sys.argv[2]) if len(sys.argv) > 2 else 60
TIMEOUT = 180

env = dict(os.environ, WINEPREFIX=os.path.expanduser("~/wineprefixes/hookcore_test"))
locks, results, seen_round = [], {}, {}

for rnd in range(MAX_ROUNDS):
    cmd = ["wine", HOST, DLL, BLOB] + [hex(l) for l in locks]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=TIMEOUT, env=env)
        out = p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode(errors="replace") + \
              (e.stderr or b"").decode(errors="replace")

    for m in re.finditer(r"^  call (\d+): .*?shift@arg3\+0xa = \(([-\d]+), ([-\d]+), ([-\d]+)\)",
                         out, re.M):
        results[int(m.group(1))] = tuple(int(m.group(i)) for i in (2, 3, 4))

    blocked = re.findall(r"section ([0-9A-Fa-f]{6,})", out)
    new = [int(b, 16) for b in blocked if int(b, 16) not in locks]

    print(f"round {rnd}: {len(results)} calls done, {len(locks)} locks known"
          f"{', +' + hex(new[0]) if new else ''}", flush=True)

    if len(results) >= 39:
        print("all calls completed")
        break
    if not new:
        # No new lock => whatever is blocking is not a lock we can clear.
        # Stop rather than spin; the caller needs to see this honestly.
        print("no new lock appeared -- stopping. Remaining blocker is not a "
              "replayed CRITICAL_SECTION.")
        break
    locks.extend(new)

print(f"\n{len(results)} / 39 calls produced a shift")
for cid in sorted(results):
    r, g, b = results[cid]
    print(f"  call {cid}: shift = ({r}, {g}, {b})")

with open("bai_shifts.txt", "w") as f:
    for cid in sorted(results):
        f.write(f"{cid} {results[cid][0]} {results[cid][1]} {results[cid][2]}\n")
print(f"\nwrote bai_shifts.txt; locks re-initialised: {[hex(l) for l in locks]}")
