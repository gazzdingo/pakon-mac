#!/usr/bin/env python3
"""Deprecated: use ``eeprom_backup.py``.

This tool used to reimplement the EEPROM read protocol on its own, in
parallel with ``eeprom_backup.py``. That is exactly how it went stale: when
``eeprom_backup.py`` was fixed for issue #50 (no ``0xA4`` chip select, no
stage-1 loader, no validation before saving -- see its docstring for the
history), this file kept the old, broken sequence, because nothing forced the
two copies to move together. A dump taken with the old code here reproduces
issue #50 exactly: no chip ever gets selected, so every read comes back
``0xFF`` and gets written to disk as if it were real.

Rather than maintain a second copy of the protocol, this now just calls
``eeprom_backup.main()``. If you have a workflow that invokes this filename,
it still works; the read path, validation, and safety behaviour are
``eeprom_backup.py``'s, not a separate implementation.
"""
from __future__ import annotations

import os
import sys

# This file lives in tools/ alongside eeprom_backup.py, so a direct run finds
# it via Python's own script-directory auto-insert -- but that only holds
# true for a direct run. The explicit insert makes it hold for an import too.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eeprom_backup import main   # noqa: E402

if __name__ == "__main__":
    print("eeprom_dump.py is deprecated -- running eeprom_backup.py "
          "(same tool, corrected protocol, validated output).",
          file=sys.stderr)
    sys.exit(main())
