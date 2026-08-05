#!/usr/bin/env python3
"""Write interlock for the Pakon tools.

Created 2026-08-05, the night before the PICkit 3 session on U11. The owner's
rule for that session: READ EVERYTHING FIRST. Until the reads exist, verify
(five matching reads), and are copied off this machine, nothing may write to,
erase, or mode-switch the scanner.

Two independent layers:

1. THE LOCK FILE. While tools/WRITES_LOCKED exists, every tool with a write,
   erase, program, or mode-switch path refuses to start -- before it opens
   USB, before it parses an image, before anything. Removing the lock is a
   deliberate act by a human who has read the file.

2. TYPED CONFIRMATION. Even with the lock removed, a tool about to touch
   NON-VOLATILE state (PIC flash, any EEPROM, a bootloader mode flag) must get
   the operator to type a phrase on a real TTY. A wrong command-line flag, a
   script, or a tool run in the wrong order can therefore never reach a write
   on its own.

This module is imported by the guarded tools; it is not run directly.
"""
from __future__ import annotations

import os
import sys

LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "WRITES_LOCKED")
PHRASE = "WRITE TO THE SCANNER"


def require_writes_unlocked(tool: str, does: str) -> None:
    """Refuse to run at all while the lock file exists."""
    if os.path.exists(LOCK):
        sys.exit(
            f"REFUSING TO RUN: {tool} {does}.\n"
            f"\n"
            f"  The write interlock is engaged:\n"
            f"      {LOCK}\n"
            f"\n"
            f"  Rule in force: READ EVERYTHING FIRST. Nothing may write to,\n"
            f"  erase, or mode-switch the scanner until the ICSP read-out of\n"
            f"  U11 is complete, verified (five byte-identical reads) and\n"
            f"  copied off this machine. See docs/27-icsp-procedure.md.\n"
            f"\n"
            f"  To re-enable write tools later, deliberately: open that file,\n"
            f"  satisfy its checklist, then delete it. Nothing was sent to the\n"
            f"  scanner by this refusal."
        )


def confirm_write(tool: str, does: str) -> None:
    """Typed, interactive confirmation immediately before a NV write."""
    if not sys.stdin.isatty():
        sys.exit(
            f"REFUSING: {tool} is about to {does}, but stdin is not a "
            f"terminal, so no operator can confirm it. Run interactively."
        )
    print(f"\n*** {tool} is about to {does}. ***")
    print(f"*** This changes non-volatile state on the scanner.          ***")
    print(f"Type exactly '{PHRASE}' to proceed; anything else aborts.")
    try:
        got = input("> ")
    except EOFError:
        got = ""
    if got.strip() != PHRASE:
        sys.exit("confirmation not given -- nothing was written.")
