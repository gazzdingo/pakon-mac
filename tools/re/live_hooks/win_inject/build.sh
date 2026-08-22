#!/usr/bin/env bash
# Cross-compiles hookdll.dll and injector.exe -- both 32-bit PE, both
# importing NOTHING but KERNEL32.dll, both stamped for the Windows XP
# subsystem/OS version -- from a Mac using Homebrew's mingw-w64.
#
# WHY -nostartfiles AND NO CRT AT ALL (msvcrt OR ucrt)
# -----------------------------------------------------
# A first build of this project, using ordinary printf/wsprintfA calls and
# the default CRT startup, imported `api-ms-win-crt-*.dll` -- the Windows-
# 10-era Universal CRT "API set" DLLs, confirmed with `objdump -p`, not
# assumed -- EVEN when `-mcrtdll=msvcrt` was passed explicitly, and even
# when linking `-lmsvcrt` explicitly (this Homebrew mingw-w64 build's own
# libmsvcrt.a itself resolves through the same UCRT API-set DLLs; there is
# no flag on this toolchain that reaches genuine legacy msvcrt.dll linking).
# None of the `api-ms-win-crt-*.dll` files exist on Windows XP, this
# project's real, confirmed target (docs/68-handover.md line 10). A binary
# built the "normal" way here looked fine under Wine ONLY because Wine
# stubs those API-set DLLs for compatibility -- masking exactly the
# problem this build avoids. hookdll.c/hookcore.c/hookcore_real_table.c/
# injector.c were written against mincrt.h (kernel32-only helpers) instead,
# and are linked with `-nostartfiles` plus a custom entry point per binary
# so the CRT *startup* object -- which pulls in CRT init/onexit machinery
# regardless of whether application code calls any libc function -- never
# gets linked in either:
#   hookdll.dll:   DllMain(HINSTANCE,DWORD,LPVOID) __stdcall, 3 args
#                  -> decorated symbol _DllMain@12
#   injector.exe:  a plain (cdecl) void MyMain(void) that calls
#                  ExitProcess() itself at every exit path
#                  -> decorated symbol _MyMain
# The verification step below checks, via objdump, that both binaries
# import NOTHING but KERNEL32.dll -- re-checked every build, not trusted
# blindly. (The independently-built ../native/ harness -- a different,
# earlier, NOT-chosen approach -- hit this identical toolchain wall and
# solved it the identical way; see mincrt.h's own header comment.)
#
# MinHook's own vendored source calls memcpy/memset directly (confirmed
# via `nm -u` -- not just compiler-synthesized calls -fno-builtin would
# suppress). Those are satisfied by freestanding_memfuncs.c, which
# provides real memcpy/memset with real external linkage from its own
# translation unit (see that file's header for why a macro-redirect
# approach failed to even compile). MinHook's .c files themselves are
# compiled completely normally -- upstream source is never modified
# (vendor/minhook/VENDOR.md).
#
# Other flag choices, same reasoning as ../native/build.sh:
#   -D_WIN32_WINNT=0x0501 -DWINVER=0x0501    target the XP API level
#   --major/minor-subsystem-version 5.1       stamp the PE header so XP's
#                                              loader accepts it
#   --major/minor-os-version 5.1              same idea, OS version field
#   -fno-builtin -ffreestanding                stop GCC from silently
#                                              rewriting a struct copy/loop
#                                              into an implicit memcpy/
#                                              memset call that would
#                                              re-resolve through CRT
#   -static-libgcc                            libgcc (stack-probe helpers
#                                              like __chkstk_ms) baked in
#                                              at compile time, no runtime
#                                              DLL needed -- doesn't affect
#                                              the import table
#
# Usage:
#   brew install mingw-w64          # once
#   ./build.sh                      # builds hookdll.dll + injector.exe
#   ./build.sh selftest             # ALSO builds + runs selftest.exe under
#     Wine (brew install wine) -- selftest.exe is dev-only, never copied to
#     the XP box, and is built with the ordinary (non-freestanding) recipe
#     for developer convenience since it only ever runs here, under Wine.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CC=i686-w64-mingw32-gcc
OBJDUMP=i686-w64-mingw32-objdump
MH=../vendor/minhook

if ! command -v "$CC" >/dev/null 2>&1; then
    echo "error: $CC not found. Install with: brew install mingw-w64" >&2
    exit 1
fi

XPFLAGS="-D_WIN32_WINNT=0x0501 -DWINVER=0x0501 -Wall -Wextra -O2 -fno-builtin -ffreestanding \
  -static-libgcc -nostartfiles \
  -Wl,--major-subsystem-version,5 -Wl,--minor-subsystem-version,1 \
  -Wl,--major-os-version,5 -Wl,--minor-os-version,1"
MHFLAGS="-D_WIN32_WINNT=0x0501 -DWINVER=0x0501 -O2 -fno-builtin -ffreestanding -static-libgcc \
  -I$MH/include -I$MH/src"

echo "== hookdll.dll =="
echo "-- compiling vendored MinHook (unmodified) + freestanding_memfuncs.c --"
BUILD_TMP=$(mktemp -d)
trap 'rm -rf "$BUILD_TMP"' EXIT
# shellcheck disable=SC2086
$CC $MHFLAGS -c "$MH/src/buffer.c" -o "$BUILD_TMP/mh_buffer.o"
# shellcheck disable=SC2086
$CC $MHFLAGS -c "$MH/src/hook.c" -o "$BUILD_TMP/mh_hook.o"
# shellcheck disable=SC2086
$CC $MHFLAGS -c "$MH/src/trampoline.c" -o "$BUILD_TMP/mh_trampoline.o"
# shellcheck disable=SC2086
$CC $MHFLAGS -c "$MH/src/hde/hde32.c" -o "$BUILD_TMP/mh_hde32.o"
$CC -O2 -fno-builtin -ffreestanding -static-libgcc -c freestanding_memfuncs.c -o "$BUILD_TMP/memfuncs.o"
# shellcheck disable=SC2086
$CC $XPFLAGS -shared -Wl,-e,_DllMain@12 -o hookdll.dll \
    hookdll.c hookcore.c hookcore_real_table.c hookstub.S \
    "$BUILD_TMP/mh_buffer.o" "$BUILD_TMP/mh_hook.o" "$BUILD_TMP/mh_trampoline.o" "$BUILD_TMP/mh_hde32.o" "$BUILD_TMP/memfuncs.o" \
    -I"$MH/include" -I"$MH/src" -Wl,--kill-at -lkernel32

echo "== injector.exe =="
# shellcheck disable=SC2086
$CC $XPFLAGS -Wl,-e,_MyMain -o injector.exe injector.c -lkernel32

echo "== verifying no CRT dependency at all (must show ONLY KERNEL32.dll) =="
$OBJDUMP -p hookdll.dll   | grep -i 'DLL Name'
$OBJDUMP -p injector.exe  | grep -i 'DLL Name'
BAD=$($OBJDUMP -p hookdll.dll injector.exe | grep -i 'DLL Name' | grep -vi 'kernel32.dll' || true)
if [ -n "$BAD" ]; then
    echo "FAIL: unexpected import(s), not present on XP:" >&2
    echo "$BAD" >&2
    exit 1
fi
echo "OK: only KERNEL32.dll referenced -- no CRT, UCRT, or anything else."

echo "== subsystem/OS version stamp (must be 5.1 for XP) =="
$OBJDUMP -p hookdll.dll injector.exe | grep -i 'subsystem\|os version'

echo "== file types =="
file hookdll.dll injector.exe

echo
echo "python3 check_table_sync.py to re-verify the hook table against agent.js:"
python3 check_table_sync.py || true

if [ "${1:-}" = "selftest" ]; then
    echo
    echo "== selftest.exe (synthetic cdecl/stdcall/thiscall/fastcall targets, dev-only, NOT copied to XP) =="
    # shellcheck disable=SC2086
    $CC -m32 -O0 -g -Wall -Wextra -I"$MH/include" -I"$MH/src" -static-libgcc \
        -o selftest.exe selftest.c hookcore.c hookstub.S \
        "$MH/src/buffer.c" "$MH/src/hook.c" "$MH/src/trampoline.c" "$MH/src/hde/hde32.c"
    file selftest.exe

    if command -v wine >/dev/null 2>&1; then
        echo "== running selftest.exe under Wine =="
        WINEPREFIX="${WINEPREFIX:-$HOME/wineprefixes/hookcore_test}" \
            WINEDEBUG=-all wine selftest.exe
        # test-run logs, not real captures. selftest_v46.jsonl is the pinned
        # path the v46 extra-dump assertions read back (HOOKDLL_LOG_PATH).
        rm -f live_hooks_*.jsonl selftest_v46.jsonl
    else
        echo "wine not found -- built selftest.exe but did not run it." \
             "Install with: brew install --cask wine-stable"
    fi
fi

echo
echo "Done. Copy hookdll.dll + injector.exe (+ optionally hooks.cfg) to the" \
     "XP box -- see ../README.md \"Running it on the real XP box\"."
