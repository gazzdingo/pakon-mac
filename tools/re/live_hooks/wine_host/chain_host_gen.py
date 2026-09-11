#!/usr/bin/env python3
"""Pack matched orderFpo + preference calls for ``chain_host.exe``.

The two hook sites are matched by **scene identity**, not by ordering:
``fpo_calc``'s arg 12 is ``scene + 0x38a2`` (docs/74 §73.4/§74.2) and
``sba_preference``'s arg 0 is ``scene + 0x3888`` on this capture, so both
resolve to the same ``scene_base`` and the pairing has zero degrees of freedom.

Buffer addresses are emitted verbatim; ``chain_host.c`` decides which fall
inside the scene (and are placed at their real offset in one shared
allocation) and which need their own.

Layout, little-endian:
    u32 n_scenes
    per scene:
      u32 scene_base
      u32 n_fpo_args,  u32 fpo_args[]
      u32 n_pref_args, u32 pref_args[]
      u32 n_bufs, per buf: u32 arg_index, u32 addr, u32 len, u8 data[len]
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

DEFAULT_CAP = ("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/"
               "live_hooks_20260818-080318.jsonl")

TRIPLE_OFF = 0x38A2
PREF_ARG0_OFF = 0x38A2

FPO_LABEL_ARG = {
    "arg0_dens": 0, "arg1_cbank": 1, "arg2_388c": 2, "arg5_blob": 5,
    "arg6_unknown": 6, "arg7_3c34": 7, "arg10_local2": 10, "fos_dmin": 11,
    "pref_data_before": 12,
    "arg0_big": 0, "arg1_big": 1, "arg2_big": 2, "arg5_big": 5,
    "arg6_big": 6, "arg7_big": 7, "arg10_big": 10, "arg11_big": 11,
    "arg12_big": 12,
}
PREF_LABEL_ARG = {"pref_data": 0, "blob": 3, "pref_scene_big": 0,
                  "pref_arg2": 2}


def collect(cap: Path, hook: str):
    out = {}
    for line in open(cap):
        d = json.loads(line)
        if d.get("hook_id") != hook:
            continue
        cid = d.get("call_id")
        if cid is None:
            continue
        e = out.setdefault(cid, {"args": None, "bufs": {}})
        if d.get("kind") == "call" and d.get("stack_dwords"):
            e["args"] = [int(x, 16) for x in d["stack_dwords"]]
        elif d.get("kind") == "buffer_dump" and d.get("readable"):
            e["bufs"][d["label"]] = (int(d["addr"], 16),
                                     bytes.fromhex(d["hex"]))
    return {c: v for c, v in sorted(out.items()) if v["args"]}


def main(argv):
    cap = Path(argv[1]) if len(argv) > 1 else Path(DEFAULT_CAP)
    out = Path(argv[2]) if len(argv) > 2 else Path("chain_args.bin")

    fpo = collect(cap, "sba_order_fpo_calc")
    pref = collect(cap, "sba_preference")

    # scene identity -> call, for each side
    fpo_by_scene, pref_by_scene = {}, {}
    for c, e in fpo.items():
        # Only arg3 == 0 calls compute the triple; the other half of the real
        # calls run a different mode and write nothing (the golden harness
        # filters identically -- pakon_orderfpo_golden.load_capture).
        if len(e["args"]) > 12 and e["args"][12] and e["args"][3] == 0:
            fpo_by_scene.setdefault(e["args"][12] - TRIPLE_OFF, (c, e))
    for c, e in pref.items():
        if e["args"] and e["args"][0]:
            pref_by_scene.setdefault(e["args"][0] - PREF_ARG0_OFF, (c, e))

    shared = sorted(set(fpo_by_scene) & set(pref_by_scene))
    print(f"orderFpo scenes: {len(fpo_by_scene)}   "
          f"preference scenes: {len(pref_by_scene)}   matched: {len(shared)}")
    if not shared:
        sys.exit("no scene matched both hooks -- check TRIPLE_OFF/PREF_ARG0_OFF")

    blob = bytearray(struct.pack("<I", len(shared)))
    for base in shared:
        _cf, ef = fpo_by_scene[base]
        _cp, ep = pref_by_scene[base]
        fa, pa = ef["args"][:16], ep["args"][:12]
        blob += struct.pack("<I", base)
        blob += struct.pack("<I", len(fa)) + b"".join(
            struct.pack("<I", a & 0xFFFFFFFF) for a in fa)
        blob += struct.pack("<I", len(pa)) + b"".join(
            struct.pack("<I", a & 0xFFFFFFFF) for a in pa)

        bufs = []
        for lab, (addr, data) in ef["bufs"].items():
            if lab in FPO_LABEL_ARG:
                bufs.append((FPO_LABEL_ARG[lab], addr, data))
        for lab, (addr, data) in ep["bufs"].items():
            if lab in PREF_LABEL_ARG:
                bufs.append((PREF_LABEL_ARG[lab], addr, data))
        # small rows first so big rows land over the top (docs/74 §77.6)
        bufs.sort(key=lambda t: len(t[2]))
        blob += struct.pack("<I", len(bufs))
        for ai, addr, data in bufs:
            blob += struct.pack("<III", ai, addr, len(data)) + data

    out.write_bytes(blob)
    print(f"{out}: {len(shared)} scenes, {len(blob)} bytes")


if __name__ == "__main__":
    main(sys.argv)
