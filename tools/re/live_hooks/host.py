#!/usr/bin/env python3
"""Frida host controller for `agent.js` -- live-hooks the real vendor F-135
pipeline (PakonIMAu.dll / TLA.dll / TLB.dll) inside a running PSI.exe on the
real Windows VM, during a real scan.

WHY THIS EXISTS
----------------
`docs/74-washed-out-tone-chain-architecture-and-dmin-methodology.md` traced
the ~206-sRGB-code "washed out" defect to the point where every INDIVIDUALLY
Unicorn-verified stage (SBA, FUGC, falloff, ICC) matches the real DLL
bit-exact, yet the composite render is still wrong -- and separately (§13,
§15) confirmed the real vendor app, on the real unit, produces genuine deep
blacks on the same film. What static Unicorn comparisons cannot see is
whether the pieces are wired together correctly at real scan time. This
script attaches Frida to a REAL running PSI.exe, loads `agent.js` (which
hooks each documented real function's entry/exit and dumps raw context +
buffer previews), and streams every event to a JSON-lines log file on disk,
tagged with a `call_id` (every hook invocation) and a `frame_id` (bumped
each time the per-scene driver, `AnsCnEnhancedPath` @ PakonIMAu.dll
`0x10069490`, is re-entered) so multiple calls across one scan session can
be told apart and grouped back into "everything that happened for frame N".

RUN THIS ON THE WINDOWS VM ITSELF
----------------------------------
This connects to Frida's LOCAL device (no frida-server needed) -- so it must
run on the same Windows machine as PSI.exe, in a Python that has `frida`
installed. See `README.md` for exact setup steps.

USAGE
-----
    # attach to an already-running PSI.exe
    python host.py --process PSI.exe --out session1.jsonl

    # or spawn it fresh under Frida (paused at entry, then resumed)
    python host.py --spawn "C:\\Program Files\\Pakon\\PSI\\PSI.exe" --out session1.jsonl

Then, while this script is running and printing `[hook_installed]` lines,
go trigger a real scan in PSI's own UI. Ctrl+C here (or press Enter, see
below) to detach cleanly -- the JSONL log and any captured buffer files
are flushed and left on disk either way.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    import frida
except ImportError:
    print(
        "The 'frida' Python package is not installed in this interpreter.\n"
        "On the Windows VM, run:\n"
        "    pip install frida frida-tools\n"
        "(frida-tools pulls in the frida package as a dependency; installing\n"
        "frida directly also works if you only need this script, not the\n"
        "frida/frida-trace/frida-ps CLI tools).",
        file=sys.stderr,
    )
    raise

HERE = Path(__file__).resolve().parent
AGENT_JS = HERE / "agent.js"


def make_on_message(log_fh, buffers_dir: Path, stats: dict):
    def on_message(message, data):
        if message.get("type") == "error":
            stats["errors"] += 1
            sys.stderr.write(
                "[agent error] "
                + message.get("description", str(message))
                + "\n"
            )
            if message.get("stack"):
                sys.stderr.write(message["stack"] + "\n")
            return
        payload = message.get("payload")
        if payload is None:
            return

        kind = payload.get("kind")
        if kind == "buffer" and data is not None:
            # Full-buffer capture from dumpFullBuffer() in agent.js (only
            # fires once wired up per the file's own header comment).
            buffers_dir.mkdir(parents=True, exist_ok=True)
            fname = "{call_id:08d}_{hook_id}_{tag}.bin".format(
                call_id=payload.get("call_id", 0),
                hook_id=payload.get("hook_id", "unknown"),
                tag=payload.get("tag", "buf"),
            )
            fpath = buffers_dir / fname
            fpath.write_bytes(data)
            payload = dict(payload)
            payload["saved_to"] = str(fpath)
            stats["buffers"] += 1

        log_fh.write(json.dumps(payload, sort_keys=True) + "\n")
        log_fh.flush()
        stats["events"] += 1

        # Lightweight live console feedback -- the full detail is in the
        # JSONL file, this is just enough to see it's alive.
        if kind == "status":
            print("[status] " + payload.get("message", ""))
        elif kind == "hook_installed":
            print(
                "[hook_installed] {hook_id} {module} {va} -> {rt}".format(
                    hook_id=payload.get("hook_id"),
                    module=payload.get("module"),
                    va=payload.get("va_documented"),
                    rt=payload.get("rt_address"),
                )
            )
        elif kind == "hook_failed":
            print(
                "[hook_failed] {hook_id} {module} {va}: {err}".format(
                    hook_id=payload.get("hook_id"),
                    module=payload.get("module"),
                    va=payload.get("va_documented"),
                    err=payload.get("error"),
                )
            )
        elif kind == "call" and payload.get("event") == "enter":
            print(
                "[call #{cid} frame {fid}] {hook_id} ENTER".format(
                    cid=payload.get("call_id"),
                    fid=payload.get("frame_id"),
                    hook_id=payload.get("hook_id"),
                )
            )

    return on_message


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--process", metavar="NAME_OR_PID",
        help="Attach to an already-running process, by name (e.g. PSI.exe) "
             "or numeric PID.",
    )
    target.add_argument(
        "--spawn", metavar="PATH",
        help="Spawn a fresh process under Frida (paused at entry), e.g. "
             "\"C:\\Program Files\\Pakon\\PSI\\PSI.exe\", then resume it.",
    )
    ap.add_argument(
        "--out", default=None,
        help="JSONL log path. Default: live_hooks_<timestamp>.jsonl next to "
             "this script.",
    )
    ap.add_argument(
        "--agent", default=str(AGENT_JS),
        help="Path to the Frida agent script (default: agent.js next to "
             "this file).",
    )
    args = ap.parse_args()

    if args.out:
        log_path = Path(args.out)
    else:
        log_path = HERE / time.strftime("live_hooks_%Y%m%d-%H%M%S.jsonl")
    buffers_dir = log_path.parent / (log_path.stem + "_buffers")

    device = frida.get_local_device()

    pid = None
    spawned = False
    if args.spawn:
        print(f"Spawning: {args.spawn}")
        pid = device.spawn([args.spawn])
        spawned = True
    else:
        ident = args.process
        try:
            pid = int(ident)
        except ValueError:
            procs = [p for p in device.enumerate_processes() if p.name == ident]
            if not procs:
                print(
                    f"No running process named '{ident}' found. "
                    f"Run 'frida-ps' (installed with frida-tools) to list "
                    f"processes, or pass --process <pid> directly.",
                    file=sys.stderr,
                )
                return 1
            if len(procs) > 1:
                print(
                    f"Multiple processes named '{ident}': "
                    f"{[p.pid for p in procs]} -- pass --process <pid> to "
                    f"disambiguate.",
                    file=sys.stderr,
                )
                return 1
            pid = procs[0].pid

    print(f"Attaching to pid {pid}")
    session = device.attach(pid)

    agent_src = Path(args.agent).read_text(encoding="utf-8")
    script = session.create_script(agent_src)

    stats = {"events": 0, "errors": 0, "buffers": 0}
    with open(log_path, "a", encoding="utf-8") as log_fh:
        script.on("message", make_on_message(log_fh, buffers_dir, stats))
        script.load()

        if spawned:
            print("Resuming spawned process...")
            device.resume(pid)

        print(f"\nLogging to: {log_path}")
        print(f"Buffer captures (if any get wired up) go under: {buffers_dir}")
        print(
            "\nHooks are installing (some may wait up to 60s for their DLL "
            "to load). Go trigger a real scan in PSI's UI now.\n"
            "Press Enter here to detach and stop logging.\n"
        )
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            pass

        try:
            session.detach()
        except frida.InvalidOperationError:
            pass

    print(
        f"\nDetached. {stats['events']} events / {stats['errors']} agent "
        f"errors / {stats['buffers']} buffer captures logged to {log_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
