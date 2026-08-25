#!/usr/bin/env python3
"""Pack captured `balance_area_image` calls for bai_host.exe.

Differs from pref_host_gen.py in one deliberate way: it does NOT relocate
buffers and rewrite the args to match. It preserves the CAPTURED addresses and
has the host reserve that range, because `balance_area_image`'s arg5
(0x6d13d50) lies *inside* a buffer dumped for an unrelated hook (`vm_prog1` at
0x6d13830) rather than being dumped in its own right. Relocating would break
that containment; preserving the addresses keeps every inter-buffer
relationship the vendor's own heap had.

Any captured buffer overlapping the reserved window is laid down, whoever
dumped it. See docs/74 §123.
"""
import json
import struct
import sys

HEAP_LO, HEAP_HI = 0x06000000, 0x10000000
CAP = sys.argv[1] if len(sys.argv) > 1 else "live_hooks_20260818-191932.jsonl"
OUT = sys.argv[2] if len(sys.argv) > 2 else "bai_args.bin"

calls, bufs = [], {}
for line in open(CAP):
    d = json.loads(line)
    if d.get("kind") == "buffer_dump" and d.get("readable") and d.get("addr"):
        bufs[int(d["addr"], 16)] = bytes.fromhex(d["hex"])
    elif d.get("kind") == "call" and d.get("hook_id") == "balance_area_image":
        sd = d.get("stack_dwords")
        if sd:
            # ALL captured dwords, not the first 8. radare2 shows the function
            # referencing `arg_68h` (ebp+0x68, arg #24) more often than any
            # other argument, so its signature is ~25 dwords wide, not 8.
            calls.append((d["call_id"], [int(x, 16) for x in sd]))

# Every buffer inside the window, regardless of which hook dumped it.
usable = sorted((a, b) for a, b in bufs.items() if HEAP_LO <= a and a + len(b) <= HEAP_HI)
print(f"{len(calls)} balance_area_image calls; {len(usable)} buffers in window")

# Buffers are laid down ONCE, not per call. Captured addresses are preserved,
# and no two dumps share an address, so the whole capture's memory can coexist
# in the reserved window -- which is also what makes arg5's containment work.
out = struct.pack("<I", len(usable))
for a, b in usable:
    out += struct.pack("<II", a, len(b)) + b

out += struct.pack("<I", len(calls))
for cid, args in calls:
    out += struct.pack("<II", cid, len(args))
    out += b"".join(struct.pack("<I", a) for a in args)
    covered = [i for i, a in enumerate(args)
               if a >= HEAP_LO and any(x <= a < x + len(y) for x, y in usable)]
    print(f"  call {cid}: args covered = {covered}")

open(OUT, "wb").write(out)
print(f"wrote {OUT} ({len(out)} bytes)")
