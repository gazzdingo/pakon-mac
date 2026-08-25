"""The v28 test: does the ported VM reproduce L from the real input vector?

Target L values (docs/74 sec88, both prior rolls):
  A: 125, 30, -102, -296, 223, 64
  B: -186, -44, -2, -8, 38, 125
This capture is a third roll, so the L values are its own -- the check is
whether pakon_vm's L matches the L this capture's own orderFpo carries.
"""
import json
import struct
import sys

sys.path.insert(0, "/Users/guy/www/pakon-mac/.claude/worktrees/"
                   "tender-gliding-abelson/tools/ansel/python-pipeline")
import pakon_vm as V

CAP = ("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/"
       "live_hooks_20260818-080318.jsonl")
OFF, NB = 0x3C, 0xB80

vecs, ycalc = [], []
for line in open(CAP):
    d = json.loads(line)
    if (d.get("kind") == "buffer_dump"
            and d.get("hook_id") == "sba_order_fpo_helper"
            and d.get("label") == "arg1_big_filled" and d.get("readable")):
        b = bytes.fromhex(d["hex"])[OFF:OFF + NB]
        vecs.append(list(struct.unpack("<%di" % (len(b) // 4), b)))
    # the orderFpo triple the calc hook records, for cross-reference
    if d.get("kind") == "call" and d.get("hook_id") == "sba_order_fpo_calc":
        sd = d.get("stack_dwords")
        if sd:
            ycalc.append([int(x, 16) for x in sd[:4]])

print("input vectors recovered: %d" % len(vecs))
recs = V.load_pcode()
print("records loaded: %d" % len(recs))

seen = []
for i, vec in enumerate(vecs):
    try:
        L = V.l_term(recs, vec)
        seen.append(L)
        print("  vector %2d -> L = %d" % (i, L))
    except Exception as e:
        print("  vector %2d -> ERROR %s: %s" % (i, type(e).__name__, e))

print("\ndistinct L values: %s" % sorted(set(seen)))
print("known targets  A: [125, 30, -102, -296, 223, 64]")
print("               B: [-186, -44, -2, -8, 38, 125]")
