#!/usr/bin/env python3
"""Film product IDs, parsed from the vendor's Config/ColorCorrection/defaults.ini.

The scanner selects colour rendering by numeric film product ID. defaults.ini
is the vendor's own grouping of those IDs by manufacturer, plus three special
categories:

    [BnW]        black and white, both C41 process and conventional
    [POSITIVE]   colour reversal film and Kodachrome
    [IMPORTED]   images brought in from file rather than scanned

What this file does NOT contain, and what is not present anywhere in the
vendor tree: the mapping from an individual ID to a named stock. defaults.ini
gives "Ilford Imaging -> 105..110" but never says which of those is HP5, which
is FP4 and which is Delta 3200. PSI.chm has no film product table either. So
per-stock identification would need either a scan from a calibrated Windows
install or the DX code read off the film itself.

That matters less than it sounds for the Ilford request. HP5, FP4 and Delta
3200 are conventional black and white negatives: no orange mask, and no
per-stock colour matrix. They render through the [BnW] path, where the density
LUT does the inversion and the matrix degenerates to a neutral transform with
a measured film-base offset. The vendor ships the B&W toning profiles for
exactly this: cold_bw.pf, warm_bw_ld0_1_4-5.pf and sepia_ld0_9_22.pf.

    ./film_ids.py                    # the whole map
    ./film_ids.py --maker Ilford     # one manufacturer
    ./film_ids.py --id 105           # look up a single ID
"""
from __future__ import annotations

import argparse
import os
import re
import sys

# vendor/ansel mirrors an F-X35 COM SERVER install (see vendor/README.md);
# PAKON_FX35_ROOT overrides it with a real one.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX35_ROOT = os.environ.get("PAKON_FX35_ROOT") or os.path.join(_REPO, "vendor", "ansel")
DEFAULT_DIR = os.path.join(FX35_ROOT, "Config", "ColorCorrection")

SPECIAL = {
    "BnW": "black and white (C41 and conventional) -- includes Ilford HP5, "
           "FP4 and Delta 3200",
    "POSITIVE": "colour reversal film and Kodachrome",
    "IMPORTED": "imported images, e.g. from file",
}


def parse(path: str) -> tuple[dict[str, list[str]], list[str]]:
    """Return {manufacturer: [ids]} and the ordered list of manufacturers.

    defaults.ini is a comment-delimited INI: a `;Name` comment introduces a
    manufacturer, and the bare `[nn]` sections that follow belong to it until
    the next comment.
    """
    groups: dict[str, list[str]] = {}
    order: list[str] = []
    maker = "Unknown"
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith(";"):
                name = line.lstrip(";").strip()
                # Skip the worked example at the top of the file.
                if name and not name[0].isdigit() and "=" not in name \
                        and not name.lower().startswith(("example", "this ", "red ",
                                                         "green ", "blue ",
                                                         "brightness ", "contrast ",
                                                         "sharpness ", "clicked",
                                                         "applies", "user")):
                    maker = name
                    groups.setdefault(maker, [])
                    if maker not in order:
                        order.append(maker)
                continue
            m = re.fullmatch(r"\[([^\]]+)\]", line)
            if m:
                groups.setdefault(maker, []).append(m.group(1))
    return groups, order


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=DEFAULT_DIR)
    ap.add_argument("--maker", help="show only this manufacturer (substring match)")
    ap.add_argument("--id", help="look up a single film product ID")
    args = ap.parse_args()

    path = os.path.join(args.data_dir, "defaults.ini")
    if not os.path.exists(path):
        sys.exit(f"not found: {path}")
    groups, order = parse(path)

    if args.id:
        for maker in order:
            if args.id in groups.get(maker, []):
                print(f"  film product {args.id}: {maker}")
                if args.id in SPECIAL:
                    print(f"    {SPECIAL[args.id]}")
                return 0
        print(f"  film product {args.id}: not listed in defaults.ini")
        return 1

    total = 0
    for maker in order:
        ids = groups.get(maker, [])
        if not ids:
            continue
        if args.maker and args.maker.lower() not in maker.lower():
            continue
        numeric = [i for i in ids if i.isdigit()]
        special = [i for i in ids if not i.isdigit()]
        total += len(ids)
        print(f"\n{maker}  ({len(ids)})")
        if numeric:
            nums = sorted(int(i) for i in numeric)
            print("  ids: " + ", ".join(str(n) for n in nums))
        for s in special:
            print(f"  [{s}]  {SPECIAL.get(s, '')}")

    if not args.maker:
        print(f"\n{total} film product entries total")
        print("\nNote: defaults.ini groups IDs by manufacturer only. No file in")
        print("the vendor tree maps an individual ID to a named stock, so which")
        print("of Ilford's 105-110 is HP5 vs FP4 vs Delta 3200 is not knowable")
        print("from these files alone. All three are conventional B&W negatives")
        print("and render through the [BnW] path regardless.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
