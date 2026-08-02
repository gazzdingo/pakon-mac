#!/usr/bin/env python3
"""Dump the Pakon PSI mrd.mdb Access database (schema + all table data).

Finding (2026-08-02): mrd.mdb from "Pakon Update 2/program files/Pakon/PSI/" is a
Jet4 (Access 2000) file containing a single user table, `Production`, with columns
(Period Text(20), Product Text(50), Unit Text(20), Quantity Long) and ZERO rows.
It is a leftover stub, NOT the film-stock database. The film product identification
lives in the DX code pipeline instead — see docs/09-film-database.md.

Usage:
    python3 tools/dump_mrd.py [path/to/mrd.mdb] [-o outdir]

Prefers mdbtools (`brew install mdbtools`); falls back to raw string extraction so
the file's contents can at least be eyeballed without dependencies.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_MDB = (
    "/Users/guy/Downloads/Pakon Update 2/program files/Pakon/PSI/mrd.mdb"
)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def dump_with_mdbtools(mdb: Path, outdir: Path) -> None:
    print(f"# {run(['mdb-ver', str(mdb)]).strip()} database: {mdb}")
    tables = [t for t in run(["mdb-tables", "-1", str(mdb)]).splitlines() if t]
    schema = run(["mdb-schema", str(mdb)])
    (outdir / "schema.sql").write_text(schema)
    print(f"# tables: {tables or '(none)'}  -> schema.sql written")
    for t in tables:
        csv_text = run(["mdb-export", str(mdb), t])
        out = outdir / f"{t}.csv"
        out.write_text(csv_text)
        nrows = max(0, len(csv_text.splitlines()) - 1)
        print(f"#   {t}: {nrows} row(s) -> {out.name}")


def dump_strings_fallback(mdb: Path, outdir: Path) -> None:
    print("# mdbtools not found; falling back to string extraction", file=sys.stderr)
    data = mdb.read_bytes()
    out = outdir / "strings.txt"
    with out.open("w") as f:
        for m in re.finditer(rb"[\x20-\x7e]{4,}", data):
            f.write(f"A\t{m.start():#x}\t{m.group().decode('ascii')}\n")
        for m in re.finditer(rb"(?:[\x20-\x7e]\x00){4,}", data):
            f.write(f"U\t{m.start():#x}\t{m.group().decode('utf-16-le')}\n")
    print(f"# wrote {out}")
    print("# note: Jet4 pages XOR-mask some metadata; prefer mdbtools for structure")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("mdb", nargs="?", default=DEFAULT_MDB, type=Path)
    ap.add_argument("-o", "--outdir", default=Path("research/mrd-dump"), type=Path)
    args = ap.parse_args()

    if not args.mdb.is_file():
        sys.exit(f"error: {args.mdb} not found")
    args.outdir.mkdir(parents=True, exist_ok=True)

    if shutil.which("mdb-tables"):
        dump_with_mdbtools(args.mdb, args.outdir)
    else:
        dump_strings_fallback(args.mdb, args.outdir)


if __name__ == "__main__":
    main()
