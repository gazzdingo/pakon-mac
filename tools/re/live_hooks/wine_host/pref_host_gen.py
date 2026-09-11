#!/usr/bin/env python3
"""Pack captured ``sba_preference`` calls for ``pref_host.exe``.

Reads the same live-hook JSONL the Unicorn harness uses and emits the flat
binary ``pref_host.c`` parses, so both engines are driven from *identical*
inputs and any disagreement is the engines, not the data.

Layout (little-endian):
    u32 n_calls
    per call:  u32 n_args, u32 args[n_args]
               u32 n_bufs, per buf: u32 arg_index, u32 len, u8 data[len]
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

DEFAULT_CAP = ("/Users/guy/.claude-account-1/jobs/5e3f6f65/tmp/"
               "live_hooks_20260818-080318.jsonl")

#: label -> the arg index it was dumped from (must match the hook table).
LABEL_ARG = {"pref_data": 0, "blob": 3, "pref_scene_big": 0, "pref_arg2": 2}


def load(cap: Path):
    calls = {}
    for line in open(cap):
        d = json.loads(line)
        if d.get("hook_id") != "sba_preference":
            continue
        cid = d.get("call_id")
        if cid is None:
            continue
        e = calls.setdefault(cid, {"args": None, "bufs": {}})
        if d.get("kind") == "call" and d.get("stack_dwords"):
            e["args"] = [int(x, 16) for x in d["stack_dwords"]]
        elif d.get("kind") == "buffer_dump" and d.get("readable"):
            e["bufs"][d["label"]] = bytes.fromhex(d["hex"])
    return [v for _c, v in sorted(calls.items()) if v["args"]]


def main(argv):
    cap = Path(argv[1]) if len(argv) > 1 else Path(DEFAULT_CAP)
    out = Path(argv[2]) if len(argv) > 2 else Path("pref_args.bin")
    calls = load(cap)
    if not calls:
        sys.exit(f"no sba_preference calls with args in {cap}")

    blob = bytearray(struct.pack("<I", len(calls)))
    for e in calls:
        args = e["args"][:12]
        blob += struct.pack("<I", len(args))
        for a in args:
            blob += struct.pack("<I", a & 0xFFFFFFFF)
        bufs = [(LABEL_ARG[k], v) for k, v in sorted(e["bufs"].items())
                if k in LABEL_ARG]
        blob += struct.pack("<I", len(bufs))
        for ai, data in bufs:
            blob += struct.pack("<II", ai, len(data)) + data

    out.write_bytes(blob)
    print(f"{out}: {len(calls)} calls, {len(blob)} bytes")
    print("buffers per call: " +
          ", ".join(sorted({k for e in calls for k in e["bufs"]
                            if k in LABEL_ARG})))


if __name__ == "__main__":
    main(sys.argv)
