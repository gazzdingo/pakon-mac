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
import re
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO / "research" / "film-products.json"
DEFAULT_INI = Path(
    "/Users/guy/Downloads/Pakon Update 2/fx35install/"
    "program files/Pakon/F-X35 COM SERVER/Config/ColorCorrection/defaults.ini"
)

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


def parse_dx(spec: str) -> tuple[int, int | None]:
    """Parse '78-13', '78/13', '78', or composite '1261' (part1*16+part2)."""
    spec = spec.strip().lower().replace(" ", "")
    if "-" in spec or "/" in spec:
        a, b = re.split(r"[-/]", spec, maxsplit=1)
        return int(a), int(b)
    n = int(spec)
    if n <= 127:
        return n, None
    # composite DX number
    return n // 16, n % 16


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dx", help="DX spec: PART1, PART1-PART2, or composite")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()
    p1, p2 = parse_dx(args.dx)
    stock = lookup(p1, p2, args.db)
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
