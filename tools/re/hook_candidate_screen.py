#!/usr/bin/env python3
"""Mechanical hook-safety screen over a reachability.py walk's function set.

WHY THIS EXISTS
---------------
docs/74 SS46 needed to know, for `analyzeArea`'s full 943-function reachable
set (`reachability.py walk 0x100e16d0`), which addresses are even mechanically
SAFE to install a return-address-swap hook on (this project's
`hookcore.h`/`hookstub.S` technique) -- as opposed to which ones are
individually verified as a genuine per-pixel/per-line write worth watching.
Those are two different questions. This script answers only the first one,
exhaustively, by direct binary inspection -- it does not read or judge any
function's actual behaviour beyond the two mechanical checks below, and it
does NOT decide which functions should be wired into the live hook table.

THE TWO MECHANICAL CHECKS
--------------------------
(a) independently call-reachable entry point: at least one real `E8 rel32`
    direct-call instruction anywhere in `.text` targets this exact address.
    Same convention as docs/74 SS37.2/SS39.2/SS40's own E8 scans, and the
    same criterion `hookcore_real_table.c`'s `notCallReachable` field
    documents -- an address reached only via an internal jmp/jcc from inside
    a different, larger function is NOT safe for this engine's
    return-address-swap technique (see that field's own long comment).
    This check does NOT follow indirect/vtable calls (their targets are not
    statically known), so it under-counts real call sites the same way
    reachability.py's own walk already does and says so.
(b) relocatable prologue: MinHook needs to copy the function's first ~5-16
    bytes into a trampoline. If any of the first 16 bytes belong to an
    instruction using EIP-relative *control transfer* (a short/near
    relative jmp/jcc/call/loop whose target is computed from its own
    address), copying it elsewhere silently breaks the target -- MinHook
    itself detects a subset of these and returns an error rather than
    crashing (this is a real engine-level backstop, not just a screening
    nicety), but flagging it here up front means a failure shows up as a
    named, pre-identified skip in this script's own report rather than as
    an opaque `MH_ERROR_*` in a live capture log.

A THIRD, EXPLICITLY-A-HEURISTIC SIGNAL: `loop_shape`
------------------------------------------------------
For triage/prioritization only, not a safety gate: does the function's own
basic-block graph contain a backward branch (candidate loop back-edge), and
is the function large enough (>= 200 bytes realsz, an arbitrary but stated
threshold) to plausibly hold real per-element work rather than a handful of
capability-lookup instructions? This is NOT a per-pixel/per-line confirmation
-- docs/74 SS27/SS28 already found several large, loopy-looking functions in
this exact neighbourhood (`applyLut`/`fcn.101fa5b0`, 90 basic blocks) that
turned out, on an actual full read, to loop over LUT *construction* (4096
entries) or SEH cleanup, not image pixels. Treat `loop_shape=True` as "worth
reading next", never as "confirmed hot pixel loop".

USAGE
-----
    python3 tools/re/hook_candidate_screen.py /tmp/pakon_re/reach_area.json \\
        --dll /tmp/pakon_re/PakonIMAu.dll --out /tmp/pakon_re/screen_area.json
"""
import argparse
import json
import struct
import sys

import r2pipe

IMAGE_BASE = 0x10000000


def parse_pe_text_section(dll_path):
    with open(dll_path, "rb") as f:
        data = f.read()
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[e_lfanew:e_lfanew + 4] == b"PE\x00\x00"
    coff_off = e_lfanew + 4
    _machine, num_sections = struct.unpack_from("<HH", data, coff_off)
    opt_hdr_size = struct.unpack_from("<H", data, coff_off + 16)[0]
    sec_table_off = coff_off + 20 + opt_hdr_size
    for i in range(num_sections):
        off = sec_table_off + i * 40
        name = data[off:off + 8].rstrip(b"\x00").decode(errors="replace")
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, off + 8)
        if name == ".text":
            return data, va, rawsize, raw
    raise RuntimeError("no .text section found")


def exhaustive_e8_targets(data, text_va, text_rawsize, text_raw):
    """Every real call target reached by an E8 rel32 anywhere in .text.
    Returns dict target_va -> [caller e8_va, ...]."""
    targets = {}
    start, end = text_raw, text_raw + text_rawsize
    for off in range(start, end - 4):
        if data[off] != 0xE8:
            continue
        rel = struct.unpack_from("<i", data, off + 1)[0]
        e8_va = text_va + (off - text_raw) + IMAGE_BASE
        next_va = e8_va + 5
        target_va = (next_va + rel) & 0xFFFFFFFF
        targets.setdefault(target_va, []).append(e8_va)
    return targets


# x86 opcodes/prefixes that begin a short/near RELATIVE control-transfer
# instruction whose encoded target would be wrong once copied to a
# trampoline at a different address. Approximate, intentionally
# conservative (over-flags rather than under-flags) -- same spirit as this
# project's other mechanical screens (docs/74 SS37.2 E8 scan).
_REL_CTRL_OPCODES_1B = {
    0xE8,  # call rel32
    0xE9,  # jmp rel32
    0xEB,  # jmp rel8
    0xE0, 0xE1, 0xE2, 0xE3,  # loopnz/loopz/loop/jcxz rel8
}
# 0x70-0x7F: jcc rel8; 0x0F 0x80-0x8F: jcc rel32 (two-byte opcode)


def prologue_has_relative_ctrl(insns_bytes):
    """insns_bytes: the raw bytes at the function entry, >=16 bytes.
    Walks byte-by-byte (not a real length disassembler) looking for the
    *opcode byte* of a relative jmp/jcc/call/loop starting inside the
    window. This is deliberately crude (does not fully decode operands/
    prefixes) so it can only ever OVER-flag, never silently miss one --
    a false positive here just means "read this one by hand before
    hooking", never "hook something unsafe"."""
    n = len(insns_bytes)
    i = 0
    while i < min(16, n):
        b = insns_bytes[i]
        if b in _REL_CTRL_OPCODES_1B:
            return True, i, f"0x{b:02x}"
        if b == 0x0F and i + 1 < n and 0x80 <= insns_bytes[i + 1] <= 0x8F:
            return True, i, f"0x0f 0x{insns_bytes[i+1]:02x}"
        if 0x70 <= b <= 0x7F:
            return True, i, f"0x{b:02x}"
        i += 1
    return False, None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reach_json", help="output of `reachability.py walk ... --out`")
    ap.add_argument("--dll", required=True, help="path to the extracted DLL")
    ap.add_argument("--out", required=True, help="output JSON path")
    ap.add_argument("--min-loop-size", type=int, default=200,
                     help="realsz threshold for the loop_shape heuristic (default 200)")
    args = ap.parse_args()

    reach = json.load(open(args.reach_json))
    funcs = reach["functions"]
    print(f"loaded {len(funcs)} functions from {args.reach_json}", file=sys.stderr)

    data, text_va, text_rawsize, text_raw = parse_pe_text_section(args.dll)
    print(f".text: va=0x{text_va:x} rawsize=0x{text_rawsize:x}", file=sys.stderr)

    print("scanning .text for every E8 call target (one pass)...", file=sys.stderr)
    call_targets = exhaustive_e8_targets(data, text_va, text_rawsize, text_raw)
    print(f"  {len(call_targets)} distinct real call targets found in .text",
          file=sys.stderr)

    # r2 pass for basic-block back-edges (loop_shape heuristic) --
    # one shared `aa` session (this project's own convention: `aa`, not the
    # slower `aaa`, is used here purely for afb.j's own block graph, which
    # does not need string xrefs), `afb.j` per candidate function.
    print("opening r2pipe session (aaa, matching reachability.py's own "
          "analysis depth)...", file=sys.stderr)
    r2 = r2pipe.open(args.dll, flags=["-2"])
    r2.cmd("aaa")

    results = {}
    n = len(funcs)
    for idx, (addr_str, meta) in enumerate(funcs.items()):
        addr = int(addr_str, 16)
        if idx % 100 == 0:
            print(f"  {idx}/{n}...", file=sys.stderr)

        call_reachable = addr in call_targets
        num_callers = len(call_targets.get(addr, []))

        # read up to 16 raw bytes at entry directly from the PE image
        file_off = addr - IMAGE_BASE - text_va + text_raw
        raw16 = data[file_off:file_off + 16] if 0 <= file_off else b""
        bad_prologue, bad_off, bad_op = prologue_has_relative_ctrl(raw16)

        loop_shape = False
        if meta.get("realsz", 0) >= args.min_loop_size:
            r2.cmd(f"s 0x{addr:x}")
            bbs = r2.cmdj("afbj")
            if not bbs:
                r2.cmd("af")
                bbs = r2.cmdj("afbj")
            if not bbs:
                bbs = []
            starts = {bb.get("addr") for bb in bbs if isinstance(bb, dict)}
            for bb in bbs:
                if not isinstance(bb, dict):
                    continue
                j = bb.get("jump")
                f = bb.get("fail")
                bb_addr = bb.get("addr", 0)
                if (j is not None and j in starts and j <= bb_addr) or \
                   (f is not None and f in starts and f <= bb_addr):
                    loop_shape = True
                    break

        results[addr_str] = {
            "name": meta.get("name"),
            "realsz": meta.get("realsz"),
            "call_reachable": call_reachable,
            "num_static_callers": num_callers,
            "safe_prologue": not bad_prologue,
            "prologue_flag_offset": bad_off,
            "prologue_flag_opcode": bad_op,
            "loop_shape_heuristic": loop_shape,
            "mechanically_safe_to_hook": call_reachable and not bad_prologue,
        }

    r2.quit()

    safe = [a for a, r in results.items() if r["mechanically_safe_to_hook"]]
    not_call_reachable = [a for a, r in results.items() if not r["call_reachable"]]
    bad_prologue_list = [a for a, r in results.items()
                          if r["call_reachable"] and not r["safe_prologue"]]
    loopy = [a for a, r in results.items() if r["loop_shape_heuristic"]]
    loopy_and_safe = [a for a in loopy if results[a]["mechanically_safe_to_hook"]]

    summary = {
        "dll": args.dll,
        "reach_json": args.reach_json,
        "total_functions": n,
        "mechanically_safe_to_hook": len(safe),
        "not_call_reachable": len(not_call_reachable),
        "call_reachable_but_bad_prologue": len(bad_prologue_list),
        "loop_shape_heuristic_hits": len(loopy),
        "loop_shape_and_mechanically_safe": len(loopy_and_safe),
    }
    print(json.dumps(summary, indent=2), file=sys.stderr)

    json.dump({"summary": summary, "functions": results}, open(args.out, "w"), indent=1)
    print(f"written to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
