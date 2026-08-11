#!/usr/bin/env python3
"""DX / film-product lookup for the Pakon colour path.

Film product ID = DX Part 1 (0–127). Specifier = DX Part 2 / generation (0–15).
Composite DX number = part1*16 + part2 (see research/film-products.json).

This selects the *path* (colour-neg / B&W / positive) and names the stock.
Per-stock slider values in shipped defaults.ini are empty; stock-specific
Ansel overrides live under anselinstalldir (sba-*.dpi) and are applied later.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO / "research" / "film-products.json"
# vendor/ansel mirrors an F-X35 COM SERVER install (see vendor/README.md);
# PAKON_FX35_ROOT overrides it with a real one.
FX35_ROOT = Path(os.environ.get("PAKON_FX35_ROOT") or REPO / "vendor" / "ansel")
DEFAULT_INI = FX35_ROOT / "Config" / "ColorCorrection" / "defaults.ini"

# Pseudo-products from defaults.ini
PATH_COLNEG = "ColNeg"
PATH_BNW = "BnW"
PATH_POSITIVE = "POSITIVE"
PATH_IMPORTED = "IMPORTED"


@dataclass
class FilmStock:
    dx_part1: int
    dx_part2: int | None
    name: str
    manufacturer: str
    path: str                          # ColNeg / BnW / POSITIVE / IMPORTED
    iso: int | None = None
    in_defaults_ini: bool = False
    sba_override: str | None = None    # e.g. "78-13" if Ansel has a stock dpi

    @property
    def dx_number(self) -> int | None:
        if self.dx_part2 is None:
            return None
        return self.dx_part1 * 16 + self.dx_part2


def load_db(path: Path = DEFAULT_DB) -> dict:
    return json.loads(path.read_text())


def _bnw_ids(db: dict) -> set[int]:
    """IDs listed under Ilford + known chromogenic B&W overrides."""
    ids = set()
    ilford = db.get("ilford", {})
    for i in ilford.get("defaults_ini_ids", []):
        ids.add(int(i))
    # Chromogenic B&W from sba overrides
    for key in db.get("pakon_per_stock_corrections", {}).get("sba_overrides", {}):
        # "78-13", "79-15", "96-*", "43-*"
        m = re.match(r"(\d+)", key)
        if m and "bw" in json.dumps(
            db["pakon_per_stock_corrections"]["sba_overrides"][key]
        ).lower():
            ids.add(int(m.group(1)))
    # Kodak chromogenic B&W products called out in meta
    ids.update({78, 79})  # Gold B&W / Portra 400BW gens — path still ColNeg+SBA
    return ids


def lookup(dx_part1: int, dx_part2: int | None = None,
           db_path: Path = DEFAULT_DB) -> FilmStock:
    db = load_db(db_path)
    entries = db["dx_part1_entries"]
    entry = next((e for e in entries if e["dx_part1"] == dx_part1), None)
    if entry is None:
        raise KeyError(f"DX part1={dx_part1} not in film-products.json")

    name = entry.get("pakon_brand_comment") or entry.get("manufacturer_pakon")
    iso = None
    product_name = None
    if dx_part2 is not None:
        for p in entry.get("products", []):
            if p.get("dx_part2") == dx_part2:
                product_name = p.get("name")
                iso = p.get("pakon_iso")
                break
        gens = entry.get("pakon_iso_by_gen")
        if iso is None and gens and 0 <= dx_part2 < len(gens):
            iso = gens[dx_part2] or None

    # Path selection
    special = {k.upper() for k in db.get("pakon_pseudo_products", {})}
    path = PATH_COLNEG
    maker = (entry.get("manufacturer_pakon") or "").lower()
    pname = (product_name or name or "").lower()
    if "ilford" in maker or "harman" in maker:
        path = PATH_BNW
    elif any(k in pname for k in ("pan f", "hp5", "fp4", "delta", "xp2", "tri-x",
                                   "t-max", "neopan", "apx")):
        path = PATH_BNW
    elif "chrome" in pname or "velvia" in pname or "provia" in pname:
        path = PATH_POSITIVE

    sba = None
    overrides = db.get("pakon_per_stock_corrections", {}).get("sba_overrides", {})
    if dx_part2 is not None:
        key = f"{dx_part1}-{dx_part2}"
        if key in overrides:
            sba = key
        elif f"{dx_part1}-*" in overrides:
            sba = f"{dx_part1}-*"

    return FilmStock(
        dx_part1=dx_part1,
        dx_part2=dx_part2,
        name=product_name or name or f"DX {dx_part1}",
        manufacturer=entry.get("manufacturer_pakon") or "Unknown",
        path=path,
        iso=iso,
        in_defaults_ini=bool(entry.get("in_pakon_defaults_ini")),
        sba_override=sba,
    )


#: The whole key space. The DX film-edge barcode carries 21 bits, of which
#: exactly 7 identify the product and 4 the specifier -- fcn.10013cd0
#: 0x10013d0b-0x10013d2c, docs/53 s1.4. So Part 1 is 0-127, Part 2 is 0-15 and
#: the composite is 0-2047. Nothing outside that can have come off a roll of
#: film, and a number that does not fit is not a DX number at all.
DX_PART1_MAX = 127
DX_PART2_MAX = 15
DX_COMPOSITE_MAX = DX_PART1_MAX * 16 + DX_PART2_MAX      # 2047


def parse_dx(spec: str) -> tuple[int, int | None]:
    """Parse '78-13', '78/13', '78', or composite '1261' (part1*16+part2).

    Out-of-range input raises. It used to be accepted: ``parse_dx('91-5373')``
    returned ``(91, 5373)``, ``lookup`` found no product with specifier 5373,
    fell back to the Part 1 brand name, and reported *KODAK ADVANTIX* for a
    roll of Kodak Gold 400. Splitting a number that is not a DX number until
    some piece of it lands on a row is not a lookup, and a confidently wrong
    film stock feeds wrong colour into everything downstream. See docs/53 s7.
    """
    spec = spec.strip().lower().replace(" ", "")
    if "-" in spec or "/" in spec:
        a, b = re.split(r"[-/]", spec, maxsplit=1)
        p1, p2 = int(a), int(b)
        if not 0 <= p1 <= DX_PART1_MAX:
            raise ValueError(
                f"DX Part 1 = {p1} is outside 0-{DX_PART1_MAX}. Part 1 is a "
                f"7-bit field in the barcode, so {p1} cannot have been read "
                f"off film.")
        if not 0 <= p2 <= DX_PART2_MAX:
            raise ValueError(
                f"DX Part 2 = {p2} is outside 0-{DX_PART2_MAX}. Part 2 is a "
                f"4-bit field. '{spec}' is not a DX Part1-Part2 pair; if it "
                f"is a number printed on the cartridge it is some other "
                f"identifier, and there is no table here that maps one.")
        return p1, p2
    n = int(spec)
    if n <= DX_PART1_MAX:
        return n, None
    if n > DX_COMPOSITE_MAX:
        raise ValueError(
            f"{n} is larger than the largest DX number there is "
            f"({DX_COMPOSITE_MAX} = 127*16+15). The barcode carries 11 bits of "
            f"film identity and nothing else, so no six-digit number can be "
            f"one. See docs/53 s7.")
    # composite DX number
    return n // 16, n % 16


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dx", help="DX spec: PART1, PART1-PART2, or composite")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()
    try:
        p1, p2 = parse_dx(args.dx)
        stock = lookup(p1, p2, args.db)
    except (ValueError, KeyError) as e:
        import sys
        print(f"no such film stock: {e.args[0] if e.args else e}",
              file=sys.stderr)
        return 2
    print(f"DX {stock.dx_part1}"
          + (f"-{stock.dx_part2}" if stock.dx_part2 is not None else ""))
    print(f"  name:     {stock.name}")
    print(f"  maker:    {stock.manufacturer}")
    print(f"  path:     {stock.path}")
    print(f"  ISO:      {stock.iso}")
    print(f"  defaults: {stock.in_defaults_ini}")
    print(f"  SBA:      {stock.sba_override}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
