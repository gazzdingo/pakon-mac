#!/bin/sh
# Cross-compiles hookload.exe + hookdll.dll for 32-bit Windows XP.
#
# This is the exact command line used to produce the prebuilt binaries
# checked in next to this script. Re-run it after editing hookdll.c /
# hookload.c / common.h / minicrt.h; it needs the mingw-w64 cross toolchain
# (`brew install mingw-w64` on macOS; `apt install mingw-w64` on Debian/
# Ubuntu -- either gives you i686-w64-mingw32-gcc).
#
# WHY -nostartfiles, AND NO -lmsvcrt/-lucrt/ANY libc AT ALL:
#   A first build of this project, even passing -mcrtdll=msvcrt explicitly
#   to request the classic runtime, still imported api-ms-win-crt-*.dll --
#   the Windows-10-era Universal CRT "API set" DLLs, confirmed by objdump,
#   not assumed. Those don't exist on Windows XP, this project's real
#   target (docs/68: "shipped with 32-bit Windows XP-only drivers"). Rather
#   than keep fighting this specific mingw-w64 build's default CRT
#   selection, hookdll.c/hookload.c were rewritten (see minicrt.h) to use
#   NO C runtime at all -- only kernel32.dll, present on every NT since
#   3.1. -nostartfiles drops even the CRT *startup* object (which itself
#   pulls in CRT init functions regardless of whether your own code calls
#   any libc function), replaced by a custom entry point per binary
#   (-Wl,-e,...) whose signature exactly matches what the OS loader itself
#   invokes, so no adapter/wrapper is needed:
#     hookdll.dll:  DllMain(HINSTANCE,DWORD,LPVOID) __stdcall, 3 args
#                   -> decorated symbol _DllMain@12 (confirmed via nm,
#                   not guessed)
#     hookload.exe: a plain (cdecl) void MyMain(void) that calls
#                   ExitProcess() itself at every exit path
#                   -> decorated symbol _MyMain
#   The verification step below checks, via objdump, that the result
#   imports NOTHING but KERNEL32.dll -- an unambiguous, re-checked-every-
#   build guarantee, not a flag trusted blindly.
#
# Other flag choices:
#   -D_WIN32_WINNT=0x0501 -DWINVER=0x0501   target the XP API level
#   --major/minor-subsystem-version 5.1      stamp the PE header so XP's
#                                             loader accepts it (a modern
#                                             default stamp can make XP
#                                             refuse to run an otherwise-
#                                             fine binary)
#   --major/minor-os-version 5.1             same idea, OS version field
#   -static-libgcc                           libgcc (stack-probe helpers
#                                             like __chkstk_ms, not the C
#                                             runtime) is baked into the
#                                             binary at compile time, no
#                                             runtime DLL needed -- doesn't
#                                             affect the import table
set -e
cd "$(dirname "$0")"

CC=i686-w64-mingw32-gcc
OBJDUMP=i686-w64-mingw32-objdump
# -fno-builtin: at -O2, GCC will silently rewrite a hand-written byte-copy
# loop (e.g. mc_strcpy_n) or a struct assignment into an implicit call to
# memcpy/memset/memmove/memcmp -- which, on this toolchain, resolves
# through api-ms-win-crt-string-l1-1-0.dll (confirmed: a first build
# without this flag imported exactly that, despite zero explicit libc
# calls anywhere in this project's own source). -fno-builtin stops GCC
# from ever substituting one of those in.
XPFLAGS="-D_WIN32_WINNT=0x0501 -DWINVER=0x0501 -Wall -O2 -fno-builtin -ffreestanding \
  -static-libgcc -nostartfiles \
  -Wl,--major-subsystem-version,5 -Wl,--minor-subsystem-version,1 \
  -Wl,--major-os-version,5 -Wl,--minor-os-version,1"

echo "== building hookdll.dll =="
$CC $XPFLAGS -shared -Wl,-e,_DllMain@12 -o hookdll.dll hookdll.c -lkernel32

echo "== building hookload.exe =="
$CC $XPFLAGS -Wl,-e,_MyMain -o hookload.exe hookload.c -lkernel32

echo "== verifying no CRT dependency at all (must show ONLY KERNEL32.dll) =="
$OBJDUMP -p hookdll.dll  | grep -i 'DLL Name'
$OBJDUMP -p hookload.exe | grep -i 'DLL Name'
BAD=$($OBJDUMP -p hookdll.dll hookload.exe | grep -i 'DLL Name' | grep -vi 'kernel32.dll' || true)
if [ -n "$BAD" ]; then
  echo "FAIL: unexpected import(s), not present on XP:" >&2
  echo "$BAD" >&2
  exit 1
fi
echo "OK: only KERNEL32.dll referenced -- no CRT, UCRT, or anything else."

echo "== subsystem/OS version stamp =="
$OBJDUMP -p hookdll.dll hookload.exe | grep -i 'subsystem\|os version'

echo "== file types =="
file hookdll.dll hookload.exe

echo "Done. Copy hookdll.dll + hookload.exe together onto the Windows XP box."
