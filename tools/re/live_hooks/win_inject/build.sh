#!/usr/bin/env bash
# Cross-compiles hookdll.dll and injector.exe (32-bit PE, matching the
# confirmed-32-bit PakonIMAu.dll/TLA.dll/TLB.dll and Windows XP target --
# docs/68-handover.md line 10, docs/70-digital-ice-groundwork.md line 105)
# from a Mac using Homebrew's mingw-w64. See ../README.md for the full
# picture, safety notes, and how to run the result on the real XP box.
#
# Usage:
#   brew install mingw-w64          # once
#   ./build.sh                      # from this directory, or anywhere
#   ./build.sh selftest             # also builds + runs the Wine self-test
#     (needs Wine: `brew install --cask wine-stable` or `brew install wine`)

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CC=i686-w64-mingw32-gcc
MH=../vendor/minhook
CFLAGS="-m32 -O2 -Wall -Wextra -I$MH/include -I$MH/src -static-libgcc"
MH_SRCS="$MH/src/buffer.c $MH/src/hook.c $MH/src/trampoline.c $MH/src/hde/hde32.c"

if ! command -v "$CC" >/dev/null 2>&1; then
    echo "error: $CC not found. Install with: brew install mingw-w64" >&2
    exit 1
fi

echo "== hookdll.dll =="
# shellcheck disable=SC2086
$CC $CFLAGS -shared -o hookdll.dll \
    hookdll.c hookcore.c hookcore_real_table.c hookstub.S $MH_SRCS \
    -Wl,--kill-at
file hookdll.dll

echo "== injector.exe =="
# shellcheck disable=SC2086
$CC $CFLAGS -o injector.exe injector.c
file injector.exe

if [ "${1:-}" = "selftest" ]; then
    echo "== selftest.exe (synthetic cdecl/stdcall/thiscall/fastcall targets) =="
    # shellcheck disable=SC2086
    $CC -m32 -O0 -g -Wall -Wextra -I"$MH/include" -I"$MH/src" -static-libgcc \
        -o selftest.exe selftest.c hookcore.c hookstub.S $MH_SRCS
    file selftest.exe

    if command -v wine >/dev/null 2>&1; then
        echo "== running selftest.exe under Wine =="
        WINEPREFIX="${WINEPREFIX:-$HOME/wineprefixes/hookcore_test}" \
            WINEDEBUG=-all wine selftest.exe
        rm -f live_hooks_*.jsonl   # test-run log, not a real capture
    else
        echo "wine not found -- built selftest.exe but did not run it." \
             "Install with: brew install --cask wine-stable"
    fi
fi

echo
echo "Done. Copy hookdll.dll + injector.exe (+ optionally hooks.cfg) to the" \
     "XP box -- see ../README.md \"Running it on the real XP box\"."
