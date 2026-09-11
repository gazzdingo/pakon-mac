#!/usr/bin/env python3
"""Acceptance check for a v34 capture, run BEFORE trusting anything from it.

v34 exists to clear the two gaps docs/74 §124 identified. This verifies it
actually did, rather than assuming a capture that arrived is a capture that
worked. Three things, each of which has a plausible failure mode:

  1. stack_dwords == 32, not 16.  Failure mode: the XP box ran the OLD DLL.
     A v34 run that silently used v33's binary looks completely normal.
  2. `bai_this` rows exist AND are readable.  Failure mode: 0x200 was too big
     and the dump straddles unmapped memory, giving readable=false.
     UNTESTED before this run -- the selftest uses a synthetic hook table, so
     the row has never fired.
  3. this == ecx, as it was on all 40 v32 calls.  Failure mode: the object
     moves, meaning it is not the stable per-call structure §124 assumed.

Usage:  python3 check_v34.py <capture.jsonl>
Exit 0 only if all three pass.
"""
import json
import sys
from collections import Counter

path = sys.argv[1] if len(sys.argv) > 1 else "capture.jsonl"

stack_lens = Counter()
bai_this = {"readable": 0, "unreadable": 0, "sizes": Counter()}
this_vs_ecx = {"match": 0, "differ": 0}
bai_calls = 0
bad_json = 0

for line in open(path):
    try:
        d = json.loads(line)
    except Exception:
        bad_json += 1
        continue

    if d.get("kind") == "call":
        sd = d.get("stack_dwords")
        if isinstance(sd, list):
            stack_lens[len(sd)] += 1
        if d.get("hook_id") == "balance_area_image":
            bai_calls += 1
            if isinstance(sd, list) and sd and d.get("ecx"):
                if int(sd[0], 16) == int(d["ecx"], 16):
                    this_vs_ecx["match"] += 1
                else:
                    this_vs_ecx["differ"] += 1

    elif d.get("kind") == "buffer_dump" and d.get("label") == "bai_this":
        if d.get("readable"):
            bai_this["readable"] += 1
            bai_this["sizes"][len(d.get("hex") or "") // 2] += 1
        else:
            bai_this["unreadable"] += 1

print(f"capture: {path}")
print(f"  unparseable lines      : {bad_json}")
print(f"  stack_dwords lengths   : {dict(stack_lens)}")
print(f"  balance_area_image calls: {bai_calls}")
print(f"  bai_this readable      : {bai_this['readable']}")
print(f"  bai_this unreadable    : {bai_this['unreadable']}")
print(f"  bai_this sizes         : {dict(bai_this['sizes'])}")
print(f"  this == ecx            : {this_vs_ecx}")

ok = True

if 32 not in stack_lens:
    print("\nFAIL 1: no call row has 32 stack dwords -- the XP box very likely "
          "ran a pre-v34 DLL. Check the injected binary's md5 against "
          "hookdll_v34.dll = 58ace56b491cf974f3467678ea4c6958.")
    ok = False
elif 16 in stack_lens:
    print(f"\nNOTE: {stack_lens[16]} rows still have 16 dwords alongside "
          f"{stack_lens[32]} with 32. Expected only if a frame ended near "
          "unreadable memory (the per-dword probe truncates rather than "
          "dropping the row) -- not necessarily a failure, but check which "
          "hooks they are before relying on them.")

if bai_this["readable"] == 0:
    print("\nFAIL 2: no readable bai_this dump. If unreadable > 0 the 0x200 "
          "size straddles unmapped memory -- shrink numBytes and re-run. If "
          "both are 0 the row never fired at all.")
    ok = False

if this_vs_ecx["differ"]:
    print(f"\nFAIL 3: this != ecx on {this_vs_ecx['differ']} call(s). §124 "
          "assumed these are the same object; EXTRA_DUMP_THIS_OFFSET dumps "
          "from ecx, so a mismatch means bai_this may not be arg0's object.")
    ok = False

print("\n" + ("ALL CHECKS PASS -- safe to feed bai_host_gen.py"
              if ok else "NOT SAFE TO USE -- see failures above"))
sys.exit(0 if ok else 1)
