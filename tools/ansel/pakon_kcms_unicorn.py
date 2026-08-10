#!/usr/bin/env python3
"""Bare Unicorn harness for kodakcms.dll — SpInitialize → SpCombine.

Installs a bump-heap + CriticalSection / GetVersion / GetModuleHandle IAT
face, calls the identity-handle buffer-ops installer ``@ 0x10028df0``, then
drives ``SpInitialize`` → ``SpProfileLoadFromBuffer(unity.pf)`` →
``SpXformGet`` → ``SpCombineXforms``.

``SpProfileLoadFromBuffer`` (``kodakcms.dll @ 0x100306f0``; IMAu
``@ 0x102f6fa2``; ``SpProfileLoadProfileW @ 0x1004b799``) is:

    (SpInitialize 'call' handle, ICC buffer ptr, SpProfile* out)

Arg0 must ``lockBuffer`` to tag ``'call'`` (``0x63616c6c``) —
``SpInitializeEx @ 0x10033e12`` stamps that; it is *not* a raw ``.pf``.

``SpXformGet @ 0x1002fa40`` (stdcall 4 args, IMAu ``@ 0x102f7610``):

    (profile, which, renderIntent, SpXform* out)

``unity.pf`` succeeds with ``which=0``, ``renderIntent=1``.

Live ``SpCombineXforms(unity,unity)→0`` is the harness gate.
``COLOR_ADJUST_PORTED=True``; ``COLOR_ADJUST_PT_MERGE_BODY_PORTED=True``
(sample combiner ``@ 0x100127e0`` remains call-through).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESP,
)

import pakon_color_adjust as ca

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x200000
HEAP_ADDR = 0x30000000
HEAP_SIZE = 0x2000000
STUB_PAGE = 0x00100000
IAT_DISPATCH = 0x00101000
PROFILE_BUF = 0x32000000

DEFAULT_CMS = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/System32/kodakcms.dll"
)
DEFAULT_UNITY = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/Config/ColorCorrection/unity.pf"
)

# kodakcms.dll @ 0x10028df0 — install identity buffer ops + CS
BUF_OPS_INSTALL = 0x10028DF0
SP_INITIALIZE = 0x10033D00
SP_PROFILE_LOAD_FROM_BUFFER = 0x100306F0
SP_XFORM_GET = 0x1002FA40
SP_PROFILE_FREE = 0x100312C0
SP_XFORM_FREE = 0x10030220

# IAT slot VAs (kodakcms)
IAT = {
    "RegOpenKeyA": 0x1004D000,
    "RegCreateKeyA": 0x1004D004,
    "RegOpenKeyExA": 0x1004D008,
    "RegSetValueExA": 0x1004D00C,
    "RegSetValueA": 0x1004D010,
    "RegQueryValueExA": 0x1004D014,
    "RegQueryValueA": 0x1004D018,
    "RegDeleteKeyA": 0x1004D01C,
    "RegEnumKeyA": 0x1004D020,
    "RegCloseKey": 0x1004D024,
    "GetUserNameA": 0x1004D028,
    "RegCreateKeyExA": 0x1004D02C,
    "GetWindowsDirectoryA": 0x1004D034,
    "CreateFileA": 0x1004D038,
    "CreateFileW": 0x1004D03C,
    "MapViewOfFile": 0x1004D040,
    "CreateFileMappingA": 0x1004D044,
    "CloseHandle": 0x1004D048,
    "UnmapViewOfFile": 0x1004D04C,
    "LoadResource": 0x1004D050,
    "FindResourceA": 0x1004D054,
    "LoadLibraryW": 0x1004D058,
    "GetSystemDirectoryW": 0x1004D05C,
    "GetSystemDirectoryA": 0x1004D060,
    "WideCharToMultiByte": 0x1004D064,
    "MultiByteToWideChar": 0x1004D068,
    "GetModuleFileNameA": 0x1004D06C,
    "InitializeCriticalSection": 0x1004D070,
    "DeleteCriticalSection": 0x1004D074,
    "GlobalAlloc": 0x1004D078,
    "EnterCriticalSection": 0x1004D07C,
    "LeaveCriticalSection": 0x1004D080,
    "SetLastError": 0x1004D084,
    "GetLastError": 0x1004D088,
    "LoadLibraryA": 0x1004D08C,
    "FreeLibrary": 0x1004D090,
    "FreeResource": 0x1004D094,
    "GetProcAddress": 0x1004D098,
    "GetVersionExA": 0x1004D09C,
    "GetSystemInfo": 0x1004D0A0,
    "GetModuleHandleA": 0x1004D0A4,
    "CreateThread": 0x1004D0A8,
    "Sleep": 0x1004D0AC,
    "WaitForMultipleObjects": 0x1004D0B0,
    "GlobalLock": 0x1004D0B4,
    "GlobalFree": 0x1004D0B8,
    "GlobalHandle": 0x1004D0BC,
    "GetVersion": 0x1004D0C0,
    "HeapAlloc": 0x1004D0C4,
    "HeapCreate": 0x1004D0C8,
    "HeapFree": 0x1004D0CC,
    "HeapSize": 0x1004D0D0,
    "GetPrivateProfileIntA": 0x1004D0D4,
    "GetPrivateProfileStringA": 0x1004D0D8,
    "CreateDirectoryA": 0x1004D0DC,
    "GetCurrentThreadId": 0x1004D0E0,
    "GetCurrentProcessId": 0x1004D0E4,
    "InterlockedExchange": 0x1004D0E8,
    "CreateSemaphoreA": 0x1004D0EC,
    "ReleaseSemaphore": 0x1004D0F0,
    "GetLocalTime": 0x1004D0F4,
    "GetSystemTime": 0x1004D0F8,
    "ReadFile": 0x1004D0FC,
    "WriteFile": 0x1004D100,
    "MoveFileA": 0x1004D104,
    "FindClose": 0x1004D108,
    "FindNextFileA": 0x1004D10C,
    "FindFirstFileA": 0x1004D110,
    "FindNextFileW": 0x1004D114,
    "FindFirstFileW": 0x1004D118,
    "lstrcatW": 0x1004D11C,
    "lstrlenW": 0x1004D120,
    "lstrcpyW": 0x1004D124,
    "SetFilePointer": 0x1004D128,
    "DeleteFileA": 0x1004D12C,
    "DeleteFileW": 0x1004D130,
    "GetFileSize": 0x1004D134,
    "GetFileAttributesA": 0x1004D138,
    "GetFileAttributesW": 0x1004D13C,
    "malloc": 0x1004D148,
    "free": 0x1004D150,
    "_adjust_fdiv": 0x1004D144,
    "_initterm": 0x1004D14C,
    "_ultoa": 0x1004D154,
    "gmtime": 0x1004D158,
    "time": 0x1004D15C,
    "localtime": 0x1004D160,
    "strrchr": 0x1004D164,
    "sprintf": 0x1004D168,
    "_CIpow": 0x1004D16C,
    "_ltow": 0x1004D170,
    "wcsrchr": 0x1004D174,
    "wcscat": 0x1004D178,
    "wcscmp": 0x1004D17C,
    "wcscpy": 0x1004D180,
    "strncpy": 0x1004D184,
    "_ftol": 0x1004D188,
    "VerQueryValueA": 0x1004D1A0,
    "GetFileVersionInfoA": 0x1004D1A4,
    "GetFileVersionInfoSizeA": 0x1004D1A8,
    "LoadStringW": 0x1004D190,
    "wsprintfA": 0x1004D194,
    "LoadStringA": 0x1004D198,
}


def _align_up(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


def load_pe(uc: Uc, pe: bytes) -> None:
    e_lfanew = struct.unpack_from("<I", pe, 0x3C)[0]
    num_sec = struct.unpack_from("<H", pe, e_lfanew + 6)[0]
    opt_size = struct.unpack_from("<H", pe, e_lfanew + 20)[0]
    size_image = struct.unpack_from("<I", pe, e_lfanew + 24 + 56)[0]
    uc.mem_map(IMAGE_BASE, _align_up(size_image))
    uc.mem_write(IMAGE_BASE, pe[:0x1000])
    sec = e_lfanew + 24 + opt_size
    for i in range(num_sec):
        o = sec + i * 40
        vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
        if rsz == 0 or raddr == 0:
            continue
        data = pe[raddr : raddr + rsz]
        if len(data) < vsz:
            data = data + b"\x00" * (vsz - len(data))
        uc.mem_write(IMAGE_BASE + va, data[: max(vsz, rsz)])


class KcmsHost:
    """IAT bump-heap host for kodakcms under Unicorn."""

    def __init__(self, uc: Uc) -> None:
        self.uc = uc
        self.bump = HEAP_ADDR + 0x1000
        self.last_error = 0
        self.heap_handles = {0x50000001: True}
        self.globals: dict[int, bytes] = {}
        self.slot_by_addr = {va: name for name, va in IAT.items()}
        self.call_log: list[str] = []

    def alloc(self, n: int) -> int:
        n = max(int(n), 1)
        a = (self.bump + 15) & ~15
        self.bump = a + n + 32
        if self.bump >= HEAP_ADDR + HEAP_SIZE:
            raise MemoryError("Unicorn KCMS heap exhausted")
        self.uc.mem_write(a, b"\x00" * n)
        return a

    def stdcall_ret(self, nbytes: int, eax: int) -> None:
        esp = self.uc.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", self.uc.mem_read(esp, 4))[0]
        self.uc.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)
        self.uc.reg_write(UC_X86_REG_ESP, esp + 4 + nbytes)
        self.uc.reg_write(UC_X86_REG_EIP, ret)

    def cdecl_ret(self, eax: int) -> None:
        esp = self.uc.reg_read(UC_X86_REG_ESP)
        ret = struct.unpack("<I", self.uc.mem_read(esp, 4))[0]
        self.uc.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)
        self.uc.reg_write(UC_X86_REG_ESP, esp + 4)
        self.uc.reg_write(UC_X86_REG_EIP, ret)

    def arg(self, i: int) -> int:
        esp = self.uc.reg_read(UC_X86_REG_ESP)
        return struct.unpack("<I", self.uc.mem_read(esp + 4 + 4 * i, 4))[0]

    def dispatch(self, name: str) -> None:
        self.call_log.append(name)
        if name in ("InitializeCriticalSection", "DeleteCriticalSection",
                    "EnterCriticalSection", "LeaveCriticalSection"):
            self.stdcall_ret(4, 0)
            return
        if name == "InterlockedExchange":
            target, value = self.arg(0), self.arg(1)
            old = struct.unpack("<I", self.uc.mem_read(target, 4))[0]
            self.uc.mem_write(target, struct.pack("<I", value))
            self.stdcall_ret(8, old)
            return
        if name == "GetVersion":
            self.stdcall_ret(0, 0x0A280105)  # Win10-ish; al != 4
            return
        if name == "GetVersionExA":
            p = self.arg(0)
            # OSVERSIONINFOA: dwOSVersionInfoSize, major, minor, build, platform
            self.uc.mem_write(p + 4, struct.pack("<IIII", 5, 1, 2600, 2))
            self.stdcall_ret(4, 1)
            return
        if name == "GetSystemInfo":
            p = self.arg(0)
            # SYSTEM_INFO — dwNumberOfProcessors @ +0x14 = 1; dwPageSize @ +4
            blob = bytearray(36)
            struct.pack_into("<I", blob, 4, 0x1000)
            struct.pack_into("<I", blob, 0x14, 1)
            self.uc.mem_write(p, bytes(blob))
            self.stdcall_ret(4, 0)
            return
        if name == "GetModuleHandleA":
            # non-NULL → kodakcms base (string may be "KodakCMS.dll")
            self.stdcall_ret(4, IMAGE_BASE)
            return
        if name in ("GetCurrentThreadId", "GetCurrentProcessId"):
            self.stdcall_ret(0, 0x42)
            return
        if name == "Sleep":
            self.stdcall_ret(4, 0)
            return
        if name == "SetLastError":
            self.last_error = self.arg(0)
            self.stdcall_ret(4, 0)
            return
        if name == "GetLastError":
            self.stdcall_ret(0, self.last_error)
            return
        if name == "HeapCreate":
            h = 0x50000001
            self.heap_handles[h] = True
            self.stdcall_ret(12, h)
            return
        if name == "HeapAlloc":
            _heap, _flags, nbytes = self.arg(0), self.arg(1), self.arg(2)
            self.stdcall_ret(12, self.alloc(nbytes))
            return
        if name == "HeapFree":
            self.stdcall_ret(12, 1)
            return
        if name == "HeapSize":
            self.stdcall_ret(8, 0x1000)
            return
        if name == "malloc":
            self.cdecl_ret(self.alloc(self.arg(0)))
            return
        if name == "free":
            self.cdecl_ret(0)
            return
        if name == "_initterm":
            self.cdecl_ret(0)
            return
        if name == "_adjust_fdiv":
            self.cdecl_ret(0)
            return
        if name == "strrchr":
            # cdecl: strrchr(s, c) → last occurrence pointer or NULL
            s, c = self.arg(0), self.arg(1) & 0xFF
            raw = bytes(self.uc.mem_read(s, 4096))
            end = raw.find(b"\x00")
            if end < 0:
                end = len(raw)
            last = -1
            for i in range(end + 1):  # include NUL if c==0
                if i <= end and (raw[i] if i < len(raw) else 0) == c:
                    last = i
            self.cdecl_ret(0 if last < 0 else s + last)
            return
        if name == "wcsrchr":
            s, c = self.arg(0), self.arg(1) & 0xFFFF
            last = -1
            i = 0
            while i < 4096:
                w = struct.unpack("<H", self.uc.mem_read(s + 2 * i, 2))[0]
                if w == c:
                    last = i
                if w == 0:
                    break
                i += 1
            self.cdecl_ret(0 if last < 0 else s + 2 * last)
            return
        if name == "strncpy":
            dst, src, n = self.arg(0), self.arg(1), self.arg(2)
            raw = bytes(self.uc.mem_read(src, min(n, 4096)))
            if b"\x00" in raw:
                raw = raw[: raw.find(b"\x00") + 1]
            raw = raw[:n].ljust(n, b"\x00")
            self.uc.mem_write(dst, raw)
            self.cdecl_ret(dst)
            return
        if name == "wcscpy":
            dst, src = self.arg(0), self.arg(1)
            i = 0
            while True:
                w = self.uc.mem_read(src + 2 * i, 2)
                self.uc.mem_write(dst + 2 * i, w)
                if w == b"\x00\x00":
                    break
                i += 1
                if i > 4096:
                    break
            self.cdecl_ret(dst)
            return
        if name == "wcscat":
            dst, src = self.arg(0), self.arg(1)
            # find end of dst
            i = 0
            while struct.unpack("<H", self.uc.mem_read(dst + 2 * i, 2))[0]:
                i += 1
                if i > 4096:
                    break
            j = 0
            while True:
                w = self.uc.mem_read(src + 2 * j, 2)
                self.uc.mem_write(dst + 2 * (i + j), w)
                if w == b"\x00\x00":
                    break
                j += 1
                if j > 4096:
                    break
            self.cdecl_ret(dst)
            return
        if name == "wcscmp":
            a, b = self.arg(0), self.arg(1)
            i = 0
            while True:
                wa = struct.unpack("<H", self.uc.mem_read(a + 2 * i, 2))[0]
                wb = struct.unpack("<H", self.uc.mem_read(b + 2 * i, 2))[0]
                if wa != wb or wa == 0:
                    self.cdecl_ret((wa - wb) & 0xFFFFFFFF)
                    return
                i += 1
                if i > 4096:
                    self.cdecl_ret(0)
                    return
        if name == "sprintf":
            # minimal: sprintf(buf, fmt, ...) — copy fmt if no %, else empty
            buf, fmt = self.arg(0), self.arg(1)
            f = bytes(self.uc.mem_read(fmt, 512)).split(b"\x00", 1)[0]
            if b"%" not in f:
                self.uc.mem_write(buf, f + b"\x00")
                self.cdecl_ret(len(f))
            else:
                # best-effort: write empty (caller may not need exact)
                self.uc.mem_write(buf, b"\x00")
                self.cdecl_ret(0)
            return
        if name == "time":
            t = 1_700_000_000
            p = self.arg(0)
            if p:
                self.uc.mem_write(p, struct.pack("<I", t))
            self.cdecl_ret(t)
            return
        if name in ("gmtime", "localtime"):
            # return static tm blob
            tm = self.alloc(36)
            self.cdecl_ret(tm)
            return
        if name == "_ultoa":
            val, buf, base = self.arg(0), self.arg(1), self.arg(2) or 10
            s = format(val & 0xFFFFFFFF, "d" if base == 10 else "x").encode() + b"\x00"
            self.uc.mem_write(buf, s)
            self.cdecl_ret(buf)
            return
        if name == "_ltow":
            val, buf, base = self.arg(0), self.arg(1), self.arg(2) or 10
            s = format(val & 0xFFFFFFFF, "d" if base == 10 else "x")
            self.uc.mem_write(buf, s.encode("utf-16le") + b"\x00\x00")
            self.cdecl_ret(buf)
            return
        if name == "_ftol":
            # float→long via ST0 — Unicorn FPU often empty; return 0
            self.cdecl_ret(0)
            return
        if name == "_CIpow":
            self.cdecl_ret(0)
            return
        if name.startswith("GetFileVersionInfo") or name == "VerQueryValueA":
            self.stdcall_ret(12 if name != "VerQueryValueA" else 16, 0)
            return
        if name == "GlobalAlloc":
            flags, nbytes = self.arg(0), self.arg(1)
            ptr = self.alloc(nbytes)
            self.globals[ptr] = b"\x00" * nbytes
            # GMEM_FIXED → return pointer
            self.stdcall_ret(8, ptr)
            return
        if name == "GlobalLock":
            self.stdcall_ret(4, self.arg(0))
            return
        if name == "GlobalFree":
            self.stdcall_ret(4, 0)
            return
        if name == "GlobalHandle":
            self.stdcall_ret(4, self.arg(0))
            return
        if name == "CloseHandle":
            self.stdcall_ret(4, 1)
            return
        if name in ("LoadLibraryA", "LoadLibraryW", "FreeLibrary"):
            self.stdcall_ret(4 if name != "FreeLibrary" else 4,
                             IMAGE_BASE if name.startswith("Load") else 1)
            return
        if name == "GetProcAddress":
            self.stdcall_ret(8, 0)  # force fail soft
            return
        if name in ("GetWindowsDirectoryA", "GetSystemDirectoryA"):
            buf, n = self.arg(0), self.arg(1)
            s = b"C:\\WINDOWS\x00" if "Windows" in name else b"C:\\WINDOWS\\SYSTEM32\x00"
            self.uc.mem_write(buf, s[:n])
            self.stdcall_ret(8, len(s) - 1)
            return
        if name == "GetSystemDirectoryW":
            buf, n = self.arg(0), self.arg(1)
            s = "C:\\WINDOWS\\SYSTEM32".encode("utf-16le") + b"\x00\x00"
            self.uc.mem_write(buf, s[: n * 2])
            self.stdcall_ret(8, len(s) // 2 - 1)
            return
        if name == "GetModuleFileNameA":
            _h, buf, n = self.arg(0), self.arg(1), self.arg(2)
            s = b"C:\\WINDOWS\\SYSTEM32\\kodakcms.dll\x00"
            self.uc.mem_write(buf, s[:n])
            self.stdcall_ret(12, len(s) - 1)
            return
        if name.startswith("Reg"):
            # ERROR_SUCCESS=0, ERROR_FILE_NOT_FOUND=2
            if name == "RegOpenKeyA" or name == "RegCreateKeyA":
                # (hKey, subKey, phkResult) — 3 args
                self.uc.mem_write(self.arg(2), struct.pack("<I", 0x80000001))
                self.stdcall_ret(12, 0)
                return
            if name == "RegOpenKeyExA":
                # (hKey, subKey, options, samDesired, phkResult) — 5 args
                self.uc.mem_write(self.arg(4), struct.pack("<I", 0x80000001))
                self.stdcall_ret(20, 0)
                return
            if name == "RegCreateKeyExA":
                # 9 args → phkResult is arg 7
                self.uc.mem_write(self.arg(7), struct.pack("<I", 0x80000001))
                self.stdcall_ret(36, 0)
                return
            if name == "RegQueryValueExA":
                # (hKey, value, reserved, type, data, cbData) — 6 args / 24 bytes
                self.stdcall_ret(24, 2)  # not found
                return
            if name == "RegQueryValueA":
                # (hKey, subKey, data, cbData) — 4 args
                self.stdcall_ret(16, 2)
                return
            if name == "RegSetValueExA":
                self.stdcall_ret(24, 0)
                return
            if name == "RegSetValueA":
                self.stdcall_ret(16, 0)
                return
            if name == "RegCloseKey":
                self.stdcall_ret(4, 0)
                return
            if name == "RegDeleteKeyA" or name == "RegEnumKeyA":
                self.stdcall_ret(8, 2)
                return
            self.stdcall_ret(4, 0)
            return
        if name == "GetPrivateProfileIntA":
            # (app, key, default, file) — 4 args
            self.stdcall_ret(16, self.arg(2))
            return
        if name == "GetPrivateProfileStringA":
            # (app, key, default, out, nSize, file) — 6 args / 24 bytes
            default, out, nsize = self.arg(2), self.arg(3), self.arg(4)
            if out and nsize:
                if default:
                    raw = bytes(self.uc.mem_read(default, min(nsize, 512)))
                    if b"\x00" in raw:
                        raw = raw[: raw.find(b"\x00") + 1]
                    else:
                        raw = raw + b"\x00"
                    raw = raw[:nsize]
                    if raw[-1:] != b"\x00":
                        raw = raw[:-1] + b"\x00"
                    self.uc.mem_write(out, raw)
                    self.stdcall_ret(24, max(len(raw) - 1, 0))
                else:
                    self.uc.mem_write(out, b"\x00")
                    self.stdcall_ret(24, 0)
            else:
                self.stdcall_ret(24, 0)
            return
        if name in ("GetFileAttributesA", "GetFileAttributesW"):
            self.stdcall_ret(4, 0xFFFFFFFF)  # not found
            return
        if name in ("CreateFileA", "CreateFileW"):
            self.stdcall_ret(28 if name.endswith("A") else 28, 0xFFFFFFFF)
            return
        if name == "lstrlenW":
            p = self.arg(0)
            n = 0
            while True:
                w = struct.unpack("<H", self.uc.mem_read(p + 2 * n, 2))[0]
                if w == 0:
                    break
                n += 1
                if n > 4096:
                    break
            self.stdcall_ret(4, n)
            return
        if name == "lstrcpyW":
            dst, src = self.arg(0), self.arg(1)
            raw = b""
            i = 0
            while True:
                w = self.uc.mem_read(src + 2 * i, 2)
                raw += w
                if w == b"\x00\x00":
                    break
                i += 1
                if i > 4096:
                    break
            self.uc.mem_write(dst, raw)
            self.stdcall_ret(8, dst)
            return
        if name == "lstrcatW":
            self.stdcall_ret(8, self.arg(0))
            return
        if name == "MultiByteToWideChar":
            # codepage, flags, mbstr, cb, wstr, cch
            mb, cb, wb, cch = self.arg(2), self.arg(3), self.arg(4), self.arg(5)
            if cb == 0xFFFFFFFF:
                s = bytes(self.uc.mem_read(mb, 512)).split(b"\x00", 1)[0]
            else:
                s = bytes(self.uc.mem_read(mb, max(cb, 0)))
            ws = s.decode("latin-1", errors="replace").encode("utf-16le") + b"\x00\x00"
            need = len(ws) // 2
            if cch == 0:
                self.stdcall_ret(24, need)
                return
            self.uc.mem_write(wb, ws[: cch * 2])
            self.stdcall_ret(24, min(need, cch))
            return
        if name == "WideCharToMultiByte":
            self.stdcall_ret(32, 1)
            return
        if name == "GetUserNameA":
            buf, pcc = self.arg(0), self.arg(1)
            s = b"pakon\x00"
            self.uc.mem_write(buf, s)
            self.uc.mem_write(pcc, struct.pack("<I", len(s)))
            self.stdcall_ret(8, 1)
            return
        if name in ("GetLocalTime", "GetSystemTime"):
            self.uc.mem_write(self.arg(0), b"\x00" * 16)
            self.stdcall_ret(4, 0)
            return
        if name == "wsprintfA":
            # insufficient; return 0
            self.cdecl_ret(0)
            return
        # default: succeed / null
        self.stdcall_ret(0, 0)


def install_iat(uc: Uc, host: KcmsHost) -> None:
    uc.mem_map(STUB_PAGE, 0x10000)
    # One page of unique entry stubs: each 8 bytes = mov eax,imm32; jmp dispatch
    # Simpler: all IAT slots point to same trampoline that looks up caller via
    # ret… better: each stub encodes slot index in a register, or use
    # dedicated addresses.
    # Map each IAT → unique address STUB_PAGE+0x100+8*i with code that pushes
    # name-id then jumps to dispatcher.
    names = list(IAT.keys())
    disp = IAT_DISPATCH
    # dispatcher: pop id; call into python via hook on this address
    uc.mem_write(disp, b"\x90\x90\xcc")  # hooked
    for i, name in enumerate(names):
        stub = STUB_PAGE + 0x200 + i * 16
        # mov eax, i; jmp disp  → B8 ii ii ii ii ; E9 rel32
        rel = disp - (stub + 10)
        code = struct.pack("<BI", 0xB8, i) + b"\xE9" + struct.pack("<i", rel)
        uc.mem_write(stub, code)
        uc.mem_write(IAT[name], struct.pack("<I", stub))

    def on_disp(u: Uc, address: int, size: int, _user: object) -> None:
        if address != disp:
            return
        idx = u.reg_read(UC_X86_REG_EAX)
        if 0 <= idx < len(names):
            host.dispatch(names[idx])
        else:
            host.stdcall_ret(0, 0)

    uc.hook_add(UC_HOOK_CODE, on_disp, begin=disp, end=disp + 1)


def call_stdcall(uc: Uc, entry: int, *args: int, stop: int = STUB_PAGE) -> int:
    uc.mem_write(stop, b"\xc3")
    esp = STACK_ADDR + 0x100000
    payload = struct.pack("<I", stop) + struct.pack(f"<{len(args)}I", *args)
    esp -= len(payload)
    uc.mem_write(esp, payload)
    uc.reg_write(UC_X86_REG_ESP, esp)
    try:
        uc.emu_start(entry, stop, count=50_000_000, timeout=30_000_000)
    except UcError as e:
        eip = uc.reg_read(UC_X86_REG_EIP)
        raise RuntimeError(
            f"UcError {e} eip={eip:#x} eax={uc.reg_read(UC_X86_REG_EAX):#x}"
        ) from e
    return uc.reg_read(UC_X86_REG_EAX) & 0xFFFFFFFF


def patch_spinitialize_out_write(uc: Uc, out_ptr: int) -> None:
    """Identity getHandle is cdecl; SpInitializeEx treats it as stdcall → stack skew.

    Hook ``kodakcms.dll @ 0x10033e21`` (``mov [ecx], eax``): perform the store
    into the SpInitialize third-arg out pointer and skip the insn.
    """

    def on_write(u: Uc, address: int, size: int, _user: object) -> None:
        if address != 0x10033E21:
            return
        from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP

        eax = u.reg_read(UC_X86_REG_EAX) & 0xFFFFFFFF
        u.mem_write(out_ptr, struct.pack("<I", eax))
        # later ``mov ecx, [ecx]`` @ 0x10033e41 must load the handle
        u.reg_write(UC_X86_REG_ECX, out_ptr)
        u.reg_write(UC_X86_REG_EIP, 0x10033E23)  # skip ``mov [ecx], eax``

    uc.hook_add(UC_HOOK_CODE, on_write, begin=0x10033E21, end=0x10033E22)


def main(argv: list[str]) -> int:
    cms_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_CMS
    unity_path = Path(argv[2]) if len(argv) > 2 else DEFAULT_UNITY
    pe = cms_path.read_bytes()
    unity = unity_path.read_bytes()

    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    load_pe(uc, pe)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    uc.mem_map(PROFILE_BUF, _align_up(len(unity) + 0x1000))
    uc.mem_write(PROFILE_BUF, unity)

    host = KcmsHost(uc)
    install_iat(uc, host)

    print("1. buffer-ops install @ 0x10028df0 …", end=" ", flush=True)
    try:
        call_stdcall(uc, BUF_OPS_INSTALL)
        print("OK")
    except Exception as e:
        print(f"FAIL {e}")
        return 1

    # Confirm ops table
    ops = struct.unpack("<I", uc.mem_read(0x10054A40, 4))[0]
    print(f"   allocBufferHandle → {ops:#x}")

    out_init = host.alloc(4)
    uc.mem_write(out_init, b"\x00\x00\x00\x00")
    patch_spinitialize_out_write(uc, out_init)
    print("2. SpInitialize(cb=0, data=0, out) …", end=" ", flush=True)
    try:
        # SpInitialize(progressProc, appData, out*) —
        # third arg written @ 0x10033e21 (patched for identity-handle cdecl skew).
        st = call_stdcall(uc, SP_INITIALIZE, 0, 0, out_init)
        print(
            f"status={st:#x} out={struct.unpack('<I', uc.mem_read(out_init, 4))[0]:#x} "
            f"log={host.call_log[-6:]}"
        )
    except Exception as e:
        print(f"FAIL {e}")
        print("  last IAT:", host.call_log[-20:])
        return 1
    if st != 0:
        print("   SpInitialize non-zero — continue probing load anyway")

    call_h = struct.unpack("<I", uc.mem_read(out_init, 4))[0]
    if call_h == 0:
        print("   SpInitialize out handle is 0 — cannot LoadFromBuffer")
        return 1

    out_prof = host.alloc(4)
    uc.mem_write(out_prof, b"\x00\x00\x00\x00")
    print(
        f"3. SpProfileLoadFromBuffer(call={call_h:#x}, unity) …",
        end=" ",
        flush=True,
    )
    try:
        # stdcall 3 args @ kodakcms.dll SpProfileLoadFromBuffer @ 0x100306f0 /
        # SpProfileLoadProfileW @ 0x1004b799 / IMAu @ 0x102f6fa2:
        #   (SpInitialize 'call' handle, ICC buffer ptr, SpProfile* out)
        # NOT (buffer, size, out) — arg0 must lock to tag 'call' (0x63616c6c)
        # via SpTagSet+0xd0 @ 0x10033c70; SpInitializeEx stamps that @ 0x10033e12.
        st = call_stdcall(
            uc, SP_PROFILE_LOAD_FROM_BUFFER, call_h, PROFILE_BUF, out_prof
        )
        prof = struct.unpack("<I", uc.mem_read(out_prof, 4))[0]
        print(f"status={st:#x} profile={prof:#x}")
    except Exception as e:
        print(f"FAIL {e}")
        print("  last IAT:", host.call_log[-30:])
        return 1
    if st != 0 or prof == 0:
        print("   load failed — cannot SpCombine yet")
        print(
            "COLOR_ADJUST_PT_MERGE_BODY already True — "
            f"load failed status={st:#x} (harness issue)"
        )
        return 1

    out_xf = host.alloc(4)
    uc.mem_write(out_xf, b"\x00\x00\x00\x00")
    print("4. SpXformGet(prof, which=0, intent=1) …", end=" ", flush=True)
    try:
        # SpXformGet @ 0x1002fa40 — stdcall 4 args (ret 0x10); IMAu @ 0x102f7610
        #   push out; push [obj+0x2c]; push [obj+0x28]; push profile
        # unity.pf: which=0, renderIntent=1 → status 0 (intent=0 hits Generate 0x206).
        st = call_stdcall(uc, SP_XFORM_GET, prof, 0, 1, out_xf)
        xf = struct.unpack("<I", uc.mem_read(out_xf, 4))[0]
        print(f"status={st:#x} xform={xf:#x}")
    except Exception as e:
        print(f"FAIL {e}")
        print("  last IAT:", host.call_log[-30:])
        return 1

    if st != 0 or xf == 0:
        print("   SpXformGet failed — SpCombine golden still open")
        return 1

    # Two identical unity xforms → combine
    arr = host.alloc(8)
    uc.mem_write(arr, struct.pack("<II", xf, xf))
    a2 = host.alloc(4)
    a3 = host.alloc(4)
    uc.mem_write(a2, b"\x00\x00\x00\x00")
    uc.mem_write(a3, b"\xff\xff\xff\xff")
    print("5. SpCombineXforms(n=2, unity×2) …", end=" ", flush=True)
    try:
        st = call_stdcall(
            uc,
            ca.KODAKCMS_SP_COMBINE_XFORMS,
            2,
            arr,
            a2,
            a3,
            0,
            0,
        )
        print(
            f"status={st:#x} *a2={struct.unpack('<I', uc.mem_read(a2,4))[0]:#x} "
            f"*a3={struct.unpack('<I', uc.mem_read(a3,4))[0]:#x}"
        )
    except Exception as e:
        print(f"FAIL {e}")
        print("  last IAT:", host.call_log[-40:])
        return 1

    if st == 0:
        print(
            "SpCombine live KCMS path: OK "
            "(COLOR_ADJUST_KODAKCMS_LIVE_SPCOMBINE; PT_MERGE_BODY=True)"
        )
        return 0
    print(f"SpCombine returned {st:#x} — unexpected vs live unity golden")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
