#!/usr/bin/env python3
"""Scan-session helpers for the Pakon app — detect, capture, status.

Read-only by default. Does not invent new USB protocols: detection uses the
same VID/PID map as ``pakon_load.py``; strip capture is a bulk read of EP 0x86
(the established image endpoint). CCD arming / lamp / motor still go through
the existing guarded tools (``pakon_load``, ``init_ccd``, ``start_acquire``,
``lamp_on``, ``spin_motor``).

    python3 tools/pakon_session.py status
    python3 tools/pakon_session.py capture captures/live.bin --seconds 2

Writes to the scanner are never issued from this module. Capture only drains
EP 0x86; if acquire is not already running the file will be dark/idle data.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

LOCK = Path(__file__).resolve().parent / "WRITES_LOCKED"

# Same identity map as tools/pakon_load.py
UNLOADED = {
    (0x04B4, 0x8613): "Cypress FX2 (unloaded)",
    (0x0F05, 0xF235): "Pakon pre-load (F235)",
    (0x0547, 0x1002): "Anchor / EZ-USB (unloaded)",
}
LOADED = {
    (0x0F05, 0xF135): "F-135 / F-135 Plus",
    (0x0F05, 0x35F2): "F-235",
    (0x0F05, 0xF335): "F-235 / F-335",
}
EP_IMAGE = 0x86
CHUNK = 256 * 1024


def writes_locked() -> bool:
    return LOCK.is_file()


def _usb_devices():
    try:
        import usb.core  # type: ignore
    except ImportError:
        return None, "pyusb not installed (pip install pyusb)"
    found = []
    try:
        for d in usb.core.find(find_all=True) or []:
            found.append(d)
    except Exception as e:  # noqa: BLE001 — surface backend errors to UI
        return None, f"USB probe failed: {e}"
    return found, None


def probe_status() -> dict:
    """Return scanner presence without claiming interfaces or writing."""
    devices, err = _usb_devices()
    out = {
        "writes_locked": writes_locked(),
        "lock_path": str(LOCK),
        "pyusb": err is None and devices is not None,
        "usb_error": err,
        "scanner": None,
        "mode": "offline",
        "hint": "",
    }
    if devices is None:
        out["hint"] = err or "USB unavailable"
        return out

    for d in devices:
        key = (int(d.idVendor), int(d.idProduct))
        if key in LOADED:
            out["scanner"] = {
                "vid": key[0], "pid": key[1],
                "name": LOADED[key], "state": "loaded",
            }
            out["mode"] = "live"
            out["hint"] = (
                "Scanner loaded. Capture reads EP 0x86; arm CCD with "
                "tools/init_ccd.py first (requires writes unlocked)."
            )
            return out
        if key in UNLOADED:
            out["scanner"] = {
                "vid": key[0], "pid": key[1],
                "name": UNLOADED[key], "state": "unloaded",
            }
            out["mode"] = "needs_load"
            out["hint"] = (
                "Scanner present but firmware not loaded. Run "
                "tools/pakon_load.py (writes must be unlocked)."
            )
            return out

    out["hint"] = (
        "No Pakon / Cypress FX2 on USB — offline / demo mode. "
        "Load an existing captures/*.bin and decode through Ansel."
    )
    return out


def open_loaded_scanner():
    """Claim the loaded F-135 interface for EP 0x86 reads. No register writes."""
    import usb.core
    import usb.util

    dev = usb.core.find(idVendor=0x0F05, idProduct=0xF135)
    if dev is None:
        raise RuntimeError("loaded scanner not found (0x0F05:0xF135)")
    try:
        dev.set_configuration()
    except usb.core.USBError:
        pass
    usb.util.claim_interface(dev, 0)
    try:
        dev.clear_halt(EP_IMAGE)
    except usb.core.USBError:
        pass
    return dev


def capture_ep86(path: str | Path, seconds: float = 2.0,
                 chunk: int = CHUNK, progress=None) -> dict:
    """Drain EP 0x86 into ``path`` for ``seconds``. Read-only on the wire.

    Does not arm acquire, lamp, or motor — those are separate tools. Returns
    byte/transfer stats for the session UI.
    """
    import usb.core

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    seconds = max(0.2, min(120.0, float(seconds)))
    dev = open_loaded_scanner()
    total = 0
    transfers = 0
    errors = 0
    t0 = time.time()
    deadline = t0 + seconds
    with path.open("wb") as fh:
        while time.time() < deadline:
            try:
                buf = bytes(dev.read(EP_IMAGE, chunk, timeout=2000))
            except usb.core.USBError:
                errors += 1
                if progress:
                    progress({"bytes": total, "transfers": transfers,
                              "errors": errors, "phase": "capture"})
                continue
            if not buf:
                errors += 1
                continue
            fh.write(buf)
            total += len(buf)
            transfers += 1
            if progress and transfers % 8 == 0:
                progress({"bytes": total, "transfers": transfers,
                          "errors": errors, "phase": "capture"})
    elapsed = max(1e-6, time.time() - t0)
    stats = {
        "path": str(path),
        "bytes": total,
        "transfers": transfers,
        "errors": errors,
        "seconds": round(elapsed, 3),
        "mib_s": round((total / (1024 * 1024)) / elapsed, 2),
    }
    if progress:
        progress({**stats, "phase": "done"})
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="probe USB for Pakon / FX2")

    c = sub.add_parser("capture", help="read EP 0x86 into a .bin (no arming)")
    c.add_argument("output")
    c.add_argument("--seconds", type=float, default=2.0)
    c.add_argument("--chunk", type=int, default=CHUNK)

    args = ap.parse_args()
    if args.cmd == "status":
        import json
        print(json.dumps(probe_status(), indent=2))
        return 0
    if args.cmd == "capture":
        st = probe_status()
        if st["mode"] != "live":
            print(st["hint"], file=sys.stderr)
            return 1

        def prog(p):
            if p.get("phase") == "capture":
                print(f"\r  {p['bytes']/(1024*1024):.1f} MiB  "
                      f"xfer={p['transfers']}  err={p['errors']}",
                      end="", file=sys.stderr, flush=True)

        stats = capture_ep86(args.output, seconds=args.seconds,
                             chunk=args.chunk, progress=prog)
        print(file=sys.stderr)
        print(f"wrote {stats['path']}: {stats['bytes']} bytes "
              f"({stats['mib_s']} MiB/s, {stats['errors']} errors)")
        return 0 if stats["bytes"] else 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
