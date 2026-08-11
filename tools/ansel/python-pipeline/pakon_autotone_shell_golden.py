#!/usr/bin/env python3
"""Golden ``ColorNegativePath::analyzeAutoTone`` **shell** vs PakonIMAu.dll.

This is the whole point of the Phase-1 task: prove, against the real binary,
that ``pakon_autotone.analyze_auto_tone`` has the control flow, the enable-byte
gating and — above all — the **struct offsets** right, *before* six Phase-2
subsystems get built on top of them.

WHAT RUNS FOR REAL
==================
The real ``0x100fb730`` executes, start to finish, on every case.  So do all
fourteen Cap-level wrappers it calls (``0x10132dc0`` … ``0x1012c490``) and,
critically, all five ``rep movsd`` getters:

    0x101320b0  cnaImpl+0x88    0x18 dwords -> AnsCnaResults
    0x10132070  cnaImpl+0x0c    0x1f dwords -> AnsCnaParams
    0x10130390  draImpl+0x1c88  0x0f dwords -> AnsDraResults
    0x10109d70  contrastImpl+0x18c 0x0b dwords -> AnsContrastAdjustResults
    0x1010bb40  toneHelperImpl+0x80 0x2f dwords -> AnsToneHelperResults

Those five are what make this a layout test rather than a control-flow test.
Each Impl's source window is filled with a **distinct dword per offset**
(``PATTERN_BASE | offset``), so the value the shell ends up threading into
``ctx+0x64d0`` / the citras ``lutSize`` argument / the contrast ``x`` argument
literally spells out which offset it came from.  If ``AUTOTONE_WORK_LAYOUT``
named the wrong offset, the probe would report the wrong one and the case
fails — it cannot pass by accident.

WHAT IS STUBBED (and why each is not vendor arithmetic)
======================================================
* ``operator new`` / ``delete`` / MSVCP71 ``basic_string`` ctor+dtor — CRT.
  The PE is loaded unbound and CRT init never runs.  The string stub stores the
  ``const char*`` verbatim, which is all the find thunk needs.
* ``0x10020a40`` — the capability-set find thunk.  Behind it, ``0x10028f70``
  walks a real ``std::map<std::string, AnsCapabilityPtr>`` red-black tree
  (``0x10209820`` -> ``0x101990c0``) plus an MSVCP71 string comparator import.
  Building a live ``_Tree`` in emulated memory would be testing MSVCP71, not
  the shell, so the map is Python-side.  Its **contract** — miss returns the
  null-capability singleton and the status is unconditionally OK
  (``0x10028fc7`` / ``0x10029034``) — is reproduced exactly, and the "not
  found" cases below exercise it.
* ``0x104ffdd6`` ``__RTDynamicCast`` — an *unbound IAT thunk* in the shipped
  file (it jumps to the raw import RVA ``0x68bc14``), so there is no vendor
  code in this image to run.  The stub is MSVC's documented algorithm walking
  the **DLL's own RTTI tables out of emulated memory**: ``*obj`` -> vftable,
  ``vftable[-4]`` -> CompleteObjectLocator, ``COL+0x10`` ->
  ClassHierarchyDescriptor, then a linear scan of its BaseClassArray for the
  target TypeDescriptor.  The cast decision is therefore data-driven off the
  real image, not hard-coded: the seven capability objects are given the seven
  real vftables (``0x1058ab04`` cna, ``0x1058a878`` dra, ``0x105871a8``
  toneHelper, ``0x10586f50`` contrast, ``0x1058a6d0`` ast, ``0x10589bb4`` pfd,
  ``0x10589d6c`` citras) and the not-found cases work by handing one object
  the *wrong* real vftable.
* The nine subsystem entry points — hooked at the **Impl** level, so the Cap
  wrappers still run::

      0x1022ea50 cna.acquire      0x1022b530 dra.acquire+hist
      0x1022af20 dra.acquire      0x101dd1b0 th.acquire+hist
      0x101dcc50 th.acquire       0x101d8880 contrast.acquire
      0x10227160 ast              0x10220650 pfd    0x10223a20 citras

  Each writes the OK status into the hidden ``AnsStatus&`` sret and returns;
  none of their bodies executes — that is Phase 2's job, and the point of this
  harness is to nail the boundary down before they exist.  Which of the nine
  was reached *is* checked, because that is how the dra and toneHelper branch
  decisions become observable.

  Arguments are recorded one level up, by a non-intercepting watch on each of
  the fourteen Cap entries, because that is the level ``pakon_autotone``
  models: every Cap wrapper rewrites the argument list on the way through.
  cna / dra / ast / pfd / citras insert the capability pointer; toneHelper
  substitutes it for the holder; contrast (``0x1010a568``) additionally reads a
  *third* capability flag byte at ``cap+0xe`` and passes it down.  None of that
  is the shell's behaviour, and none of it is modelled here.
* ``0x1001f540`` (the log sink) and ``0x1001ed90`` (the "<Name> capability not
  found." throw) — recorded, not executed.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_autotone_shell_golden.py [dll]``

The DLL is not in the repo.  Extract it with
``python3 tools/re/reachability.py extract`` (default ``/tmp/pakon_re``).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import (
    Uc,
    UcError,
    UC_ARCH_X86,
    UC_MODE_32,
    UC_HOOK_CODE,
    UC_HOOK_MEM_INVALID,
)
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_ECX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESP,
)

import pakon_autotone as at

IMAGE_BASE = 0x10000000
STACK = 0x0BF00000
STACK_SZ = 0x00800000
HEAP = 0x0D000000
HEAP_SZ = 0x02000000
SCRATCH = 0x00100000
RET_MAGIC = 0x00110000

VA_OP_NEW = 0x104FFD53
VA_OP_DELETE = 0x104FFDD0
VA_OP_DELETE_ARR = 0x104FFE3E
IAT_STRING_CTOR = 0x10573394   # basic_string::basic_string(const char*)
IAT_STRING_DTOR = 0x10573418   # basic_string::~basic_string()

VA_ANALYZE = at.ANALYZE_AUTO_TONE
VA_FIND_THUNK = at.CAP_FIND_THUNK
VA_RTDYNCAST = at.RT_DYNAMIC_CAST
VA_LOG_SINK = 0x1001F540
VA_THROW = at.THROW_NOT_FOUND

#: Real vftables for the seven capability classes, located by scanning the
#: image for the CompleteObjectLocator that names each TypeDescriptor and then
#: for the dword that points at that COL (vftable[-4]).  All seven COLs report
#: ``offset == 0``, i.e. AnsCapability is at offset 0 in every one.
CAP_VFTABLE = {
    "cna": 0x1058AB04,
    "dra": 0x1058A878,
    "toneHelper": 0x105871A8,
    "contrast": 0x10586F50,
    "ast": 0x1058A6D0,
    "pfd": 0x10589BB4,
    "citras": 0x10589D6C,
}

#: (Impl entry, callee-pop bytes) for every subsystem body we intercept.
SUBSYSTEM_IMPLS = {
    "cna.acquire":      (0x1022EA50, 0x10),
    "dra.acquireHist":  (0x1022B530, 0x18),
    "dra.acquire":      (0x1022AF20, 0x10),
    "th.acquireHist":   (0x101DD1B0, 0x18),
    "th.acquire":       (0x101DCC50, 0x14),
    "contrast.acquire": (0x101D8880, 0x18),
    "ast.analyze":      (0x10227160, 0x10),
    "pfd.analyze":      (0x10220650, 0x10),
    "citras.analyze":   (0x10223A20, 0x10),
}

#: Impl-relative window each real getter copies out (from AUTOTONE_WORK_LAYOUT).
GETTER_WINDOWS = {
    "cna": [("AnsCnaResults", 0x88), ("AnsCnaParams", 0x0C)],
    "dra": [("AnsDraResults", 0x1C88)],
    "toneHelper": [("AnsToneHelperResults", 0x80)],
    "contrast": [("AnsContrastAdjustResults", 0x18C)],
}

PATTERN_BASE = 0x5A5A0000   # PATTERN_BASE | off  -> a unique dword per offset

DEFAULT_DLL = Path("/tmp/pakon_re/PakonIMAu.dll")


def _align(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


class Emu:
    """Minimal PakonIMAu.dll emulator: bump heap, CRT stubs, flat SEH head."""

    def __init__(self, pe: bytes):
        self.pe = pe
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc = uc
        self._load()
        uc.mem_map(0, 0x1000)              # flat FS base -> fs:[0] SEH head
        uc.mem_map(STACK, STACK_SZ)
        uc.mem_map(HEAP, HEAP_SZ)
        uc.mem_map(SCRATCH, 0x10000)
        uc.mem_map(RET_MAGIC & ~0xFFF, 0x1000)
        uc.mem_write(RET_MAGIC, b"\xC3")
        uc.mem_write(0, struct.pack("<I", 0xFFFFFFFF))
        self.brk = HEAP + 0x1000
        self._stub_next = SCRATCH + 0x1000
        self.faults: list[str] = []
        uc.hook_add(UC_HOOK_MEM_INVALID, self._on_bad_mem)
        self.hook(VA_OP_NEW, lambda e, a: (e.alloc(max(e.r32(a), 4)), 0))
        self.hook(VA_OP_DELETE, lambda e, a: (None, 0))
        self.hook(VA_OP_DELETE_ARR, lambda e, a: (None, 0))

        # MSVCP71 std::string ctor/dtor: store the char* verbatim at this+0.
        ctor = self.stub()
        self.wu32(IAT_STRING_CTOR, ctor)
        self.hook(ctor, self._string_ctor)
        dtor = self.stub()
        self.wu32(IAT_STRING_DTOR, dtor)
        self.hook(dtor, lambda e, a: (None, 0))

    @staticmethod
    def _string_ctor(e: "Emu", args: int):
        this = e.uc.reg_read(UC_X86_REG_ECX)
        e.wu32(this, e.r32(args))
        return this, 4

    def _load(self) -> None:
        pe = self.pe
        e = struct.unpack_from("<I", pe, 0x3C)[0]
        ns = struct.unpack_from("<H", pe, e + 6)[0]
        osz = struct.unpack_from("<H", pe, e + 20)[0]
        opt = e + 24
        size_image = struct.unpack_from("<I", pe, opt + 56)[0]
        self.uc.mem_map(IMAGE_BASE, _align(size_image))
        self.uc.mem_write(IMAGE_BASE, pe[:0x1000])
        so = opt + osz
        for i in range(ns):
            o = so + i * 40
            vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
            if rsz == 0 or raddr == 0:
                continue
            d = pe[raddr:raddr + rsz]
            if len(d) < vsz:
                d += b"\x00" * (vsz - len(d))
            self.uc.mem_write(IMAGE_BASE + va, d[:max(vsz, rsz)])

    # -- memory ------------------------------------------------------------
    def alloc(self, size: int, fill: bytes | None = None) -> int:
        p = self.brk
        self.brk = (self.brk + size + 0x40) & ~0xF
        if self.brk >= HEAP + HEAP_SZ:
            raise RuntimeError("emu heap exhausted")
        self.uc.mem_write(p, b"\x00" * size)
        if fill:
            self.uc.mem_write(p, fill)
        return p

    def stub(self) -> int:
        p = self._stub_next
        self._stub_next += 0x10
        self.uc.mem_write(p, b"\xC3")
        return p

    def wu32(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<I", int(v) & 0xFFFFFFFF))

    def wi32(self, a: int, v: int) -> None:
        self.uc.mem_write(a, struct.pack("<i", int(v)))

    def wu8(self, a: int, v: int) -> None:
        self.uc.mem_write(a, bytes([int(v) & 0xFF]))

    def r32(self, a: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(a, 4))[0]

    def ri32(self, a: int) -> int:
        return struct.unpack("<i", self.uc.mem_read(a, 4))[0]

    def ru8(self, a: int) -> int:
        return self.uc.mem_read(a, 1)[0]

    def cstr(self, a: int, limit: int = 96) -> str:
        raw = bytes(self.uc.mem_read(a, limit))
        return raw.split(b"\x00", 1)[0].decode("latin-1")

    # -- hooks -------------------------------------------------------------
    def hook(self, va: int, fn) -> None:
        def cb(uc, address, size, _u):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            res = fn(self, esp + 4)
            eax, pop = res if isinstance(res, tuple) else (res, 0)
            if eax is not None:
                uc.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
            uc.reg_write(UC_X86_REG_EIP, ret)

        self.uc.hook_add(UC_HOOK_CODE, cb, begin=va, end=va)

    def _on_bad_mem(self, uc, access, address, size, value, _u):
        self.faults.append(
            f"bad mem access={access} addr={address:#x} eip="
            f"{uc.reg_read(UC_X86_REG_EIP):#x}")
        return False

    # -- calling -----------------------------------------------------------
    def call(self, va: int, args=(), ecx: int | None = None) -> int:
        uc = self.uc
        esp = STACK + STACK_SZ - 0x20000
        blob = b"".join(struct.pack("<I", a & 0xFFFFFFFF) for a in args)
        esp -= len(blob)
        if blob:
            uc.mem_write(esp, blob)
        esp -= 4
        uc.mem_write(esp, struct.pack("<I", RET_MAGIC))
        uc.reg_write(UC_X86_REG_ESP, esp)
        if ecx is not None:
            uc.reg_write(UC_X86_REG_ECX, ecx)
        self.faults = []
        try:
            uc.emu_start(va, RET_MAGIC, timeout=0, count=200_000_000)
        except UcError as ex:
            raise RuntimeError(
                f"emu {va:#x} eip={uc.reg_read(UC_X86_REG_EIP):#x}: {ex}"
                + ("; " + "; ".join(self.faults[:2]) if self.faults else "")
            ) from ex
        if self.faults:
            raise RuntimeError(f"emu {va:#x} faults: {self.faults[:2]}")
        return uc.reg_read(UC_X86_REG_EAX)


# ---------------------------------------------------------------------------
# __RTDynamicCast over the DLL's own RTTI tables
# ---------------------------------------------------------------------------


def rt_dynamic_cast(emu: Emu, obj: int, vfdelta: int, srctype: int,
                    dsttype: int) -> int:
    """MSVC's algorithm, reading the real RTTI structures from emulated memory.

    ``vftable[-4]`` is the RTTICompleteObjectLocator
    ``{signature, offset, cdOffset, pTypeDescriptor, pClassDescriptor}``;
    ``pClassDescriptor`` is an RTTIClassHierarchyDescriptor
    ``{signature, attributes, numBaseClasses, pBaseClassArray}``; each entry of
    that array is an RTTIBaseClassDescriptor whose first dword is the base's
    TypeDescriptor and whose ``+8`` is the PMD member displacement.
    """
    if obj == 0:
        return 0
    vft = emu.r32(obj)
    col = emu.r32(vft - 4)
    if emu.r32(col) != 0:                       # signature must be 0 (x86)
        return 0
    off = emu.r32(col + 4)
    chd = emu.r32(col + 0x10)
    nbase = emu.r32(chd + 8)
    pbca = emu.r32(chd + 0x0C)
    for i in range(nbase):
        bcd = emu.r32(pbca + 4 * i)
        if emu.r32(bcd) == dsttype:
            mdisp = emu.ri32(bcd + 8)
            return (obj - off + mdisp) & 0xFFFFFFFF
    return 0


# ---------------------------------------------------------------------------
# the scenario
# ---------------------------------------------------------------------------


class Scenario:
    """One emulated run of the real ``0x100fb730``."""

    def __init__(self, pe: bytes, *, enabled=None, wrong_vftable=None,
                 missing=None, scene_type: int = 0, arg2: int = 0xA2A2A2A2,
                 tone_from_cna: bool = True, edge_hist: bool = True,
                 elmo: bool = True):
        self.emu = Emu(pe)
        e = self.emu
        self.calls: list[tuple[str, tuple[int, ...]]] = []
        self.impls_reached: list[str] = []
        self.thrown: tuple[str, str, int] | None = None
        self.enabled = ({c.name for c in at.CAPABILITIES
                         if c.declare_enabled} if enabled is None
                        else set(enabled))
        self.missing = set(missing or ())
        self.wrong_vftable = wrong_vftable
        self.arg2 = arg2

        # ctx: the ColorNegativePath driver state.
        self.ctx = e.alloc(0x6600)
        e.wi32(self.ctx + at.CTX_SCENE_TYPE, scene_type)
        e.wu32(self.ctx + at.CTX_TONE_OBJECT, 0xDEADBEEF)  # must be zeroed

        # holder: [ebp+0xc], refcounted at +4, never released to zero.
        self.holder = e.alloc(0x40)
        e.wu32(self.holder + 4, 0x01000000)
        e.wu32(self.holder + 0xC, e.alloc(0x10))

        # Impl objects, each filled with PATTERN_BASE|off over the getter
        # window so every copied dword names its own offset.
        self.impls: dict[str, int] = {}
        for key, windows in GETTER_WINDOWS.items():
            impl = e.alloc(0x2100)
            for struct_name, base in windows:
                size = at.AUTOTONE_WORK_LAYOUT[struct_name]["size"]
                for off in range(0, size, 4):
                    e.wu32(impl + base + off, PATTERN_BASE | off)
            self.impls[key] = impl
        # the two branch-controlling fields
        self.cna_tone_off = at.layout_offset("AnsCnaResults", "ToneScaleLut")
        self.cna_edge_off = at.layout_offset("AnsCnaResults", "EdgeHist")
        if not tone_from_cna:
            e.wu32(self.impls["cna"] + 0x88 + self.cna_tone_off, 0)
        if not edge_hist:
            e.wu32(self.impls["cna"] + 0x88 + self.cna_edge_off, 0)
        self.cna_elmo_off = at.layout_offset("AnsCnaResults", "bElmoOccured")
        if not elmo:
            e.wu8(self.impls["cna"] + 0x88 + self.cna_elmo_off, 0)

        # the seven capability objects
        self.caps: dict[str, int] = {}
        for spec in at.CAPABILITIES:
            cap = e.alloc(0x40)
            vft = CAP_VFTABLE[spec.name]
            if wrong_vftable and wrong_vftable[0] == spec.name:
                vft = CAP_VFTABLE[wrong_vftable[1]]
            e.wu32(cap, vft)
            e.wu32(cap + 4, 0x01000000)
            e.wu8(cap + at.CAP_ENABLE_BYTE, 1 if spec.name in self.enabled else 0)
            e.wu8(cap + at.CAP_FLAG_BYTE_D, 1)
            impl_key = {"cna": "cna", "dra": "dra", "toneHelper": "toneHelper",
                        "contrast": "contrast"}.get(spec.name)
            e.wu32(cap + at.CAP_IMPL_PTR,
                   self.impls[impl_key] if impl_key else e.alloc(0x100))
            self.caps[spec.name] = cap

        self._install_hooks()

    # -- hooks -------------------------------------------------------------
    def watch_cap_call(self, call: at.CapCall) -> None:
        """Record a Cap-level call's arguments **without** intercepting it.

        This is the level ``pakon_autotone`` models.  Recording at the Impl
        entry instead would compare the Cap wrappers' own marshalling — they
        insert the capability pointer (cna/dra/ast/pfd/citras), or substitute
        it for the holder (toneHelper), before forwarding.
        """
        e = self.emu
        n = call.n_stack_args

        def cb(uc, address, size, _u):
            esp = uc.reg_read(UC_X86_REG_ESP)
            vals = tuple(
                struct.unpack("<I", uc.mem_read(esp + 4 + 4 * i, 4))[0]
                for i in range(n))
            args = () if call.key.split(".")[1].startswith("get") \
                else vals[1:]                        # drop the sret slot
            self.calls.append((call.key, args))

        e.uc.hook_add(UC_HOOK_CODE, cb, begin=call.cap_va, end=call.cap_va)

    def _install_hooks(self) -> None:
        e = self.emu

        # Observe every Cap-level call the shell makes, in order.
        for call in at.CAP_CALLS:
            self.watch_cap_call(call)

        def find(emu: Emu, args: int):
            sret, name_obj, out = (emu.r32(args), emu.r32(args + 4),
                                   emu.r32(args + 8))
            name = emu.cstr(emu.r32(name_obj))
            self.calls.append(("find:" + name, ()))
            cap = 0 if name in self.missing else self.caps.get(name, 0)
            emu.wu32(out, cap)
            emu.wu32(sret, 0)          # status is ALWAYS OK -- 0x10029034
            return sret, 0xC           # ret 0xc
        e.hook(VA_FIND_THUNK, find)

        def dyncast(emu: Emu, args: int):
            obj, vfd, src, dst = (emu.r32(args), emu.r32(args + 4),
                                  emu.r32(args + 8), emu.r32(args + 12))
            return rt_dynamic_cast(emu, obj, vfd, src, dst), 0   # cdecl
        e.hook(VA_RTDYNCAST, dyncast)

        for key, (va, pop) in SUBSYSTEM_IMPLS.items():
            e.hook(va, self._make_impl_hook(key, pop))

        e.hook(VA_LOG_SINK, lambda em, a: (None, 0x10))

        def throw(emu: Emu, args: int):
            sret = emu.r32(args)
            msg = emu.cstr(emu.r32(args + 12))
            line = emu.r32(args + 20)
            self.thrown = (msg, emu.cstr(emu.r32(args + 16)), line)
            emu.wu32(sret, 0)
            return sret, 0             # cdecl
        e.hook(VA_THROW, throw)

    def _make_impl_hook(self, key: str, pop: int):
        """Intercept a subsystem body: write the OK status, return, run nothing.

        ``*arg0`` is the hidden ``AnsStatus&`` sret every Impl fills; ``0`` is
        the OK sentinel (``[0x106b5bd4]`` is 0 in the shipped image), which is
        also what makes every downstream refcount guard take its null branch.
        """
        def h(emu: Emu, args: int):
            sret = emu.r32(args)
            self.impls_reached.append(key)
            emu.wu32(sret, 0)
            return sret, pop
        return h

    # -- run ---------------------------------------------------------------
    def run(self):
        e = self.emu
        sret = e.alloc(0x10)
        e.call(VA_ANALYZE, [sret, self.holder, self.arg2, self.ctx])
        return {
            "tone": e.r32(self.ctx + at.CTX_TONE_OBJECT),
            "scene_type": e.ri32(self.ctx + at.CTX_SCENE_TYPE),
            "calls": list(self.calls),
            "impls": list(self.impls_reached),
            "thrown": self.thrown,
            "cap_ok_byte": {n: e.ru8(c + at.CAP_STATUS_BYTE_F)
                            for n, c in self.caps.items()},
        }


# ---------------------------------------------------------------------------
# the same run, through pakon_autotone
# ---------------------------------------------------------------------------


class PatternSubsystems(at.AutoToneSubsystems):
    """Host side of the same scenario: the same pattern bytes, same records."""

    def __init__(self, sc: Scenario):
        self.sc = sc
        self.calls: list[tuple[str, tuple]] = []

    def _buf(self, struct_name: str, *, zero: tuple[int, ...] = ()) -> bytes:
        size = at.AUTOTONE_WORK_LAYOUT[struct_name]["size"]
        b = bytearray(size)
        for off in range(0, size, 4):
            struct.pack_into("<I", b, off, PATTERN_BASE | off)
        for off in zero:
            struct.pack_into("<I", b, off, 0)
        return bytes(b)

    # cna
    def cna_acquire(self, holder, arg2):
        self.calls.append(("cna.acquire", (holder, arg2)))

    def cna_get_results(self):
        self.calls.append(("cna.getResults", ()))
        zero = []
        if not self.sc._tone_from_cna:
            zero.append(self.sc.cna_tone_off)
        if not self.sc._edge_hist:
            zero.append(self.sc.cna_edge_off)
        b = bytearray(self._buf("AnsCnaResults", zero=tuple(zero)))
        if not self.sc._elmo:
            b[self.sc.cna_elmo_off] = 0
        return bytes(b)

    def cna_get_params(self):
        self.calls.append(("cna.getParams", ()))
        return self._buf("AnsCnaParams")

    # dra
    def dra_acquire_with_hist(self, holder, lum, edge, tone):
        self.calls.append(("dra.acquireHist", (holder, lum, edge, tone)))

    def dra_acquire(self, holder, arg2):
        self.calls.append(("dra.acquire", (holder, arg2)))

    def dra_get_results(self):
        self.calls.append(("dra.getResults", ()))
        return self._buf("AnsDraResults")

    # toneHelper
    def tone_helper_acquire_with_hist(self, holder, lum, edge, ctx, tone):
        self.calls.append(("th.acquireHist",
                           (holder, lum, edge, "&ctx+0x4bc", tone)))

    def tone_helper_acquire(self, holder, arg2, ctx, tone):
        self.calls.append(("th.acquire", (holder, arg2, "&ctx+0x4bc", tone)))

    def tone_helper_get_results(self):
        self.calls.append(("th.getResults", ()))
        return self._buf("AnsToneHelperResults")

    # contrast
    def contrast_acquire(self, holder, scene_type, x, tone):
        self.calls.append(("contrast.acquire", (holder, scene_type, x, tone)))

    def contrast_get_results(self):
        self.calls.append(("contrast.getResults", ()))
        return self._buf("AnsContrastAdjustResults")

    # singles
    def ast_analyze(self, holder, tone):
        self.calls.append(("ast.analyze", (holder, tone)))

    def pfd_analyze(self, holder, lut_size, tone):
        self.calls.append(("pfd.analyze", (holder, lut_size, tone)))

    def citras_analyze(self, holder, lut_size, tone):
        self.calls.append(("citras.analyze", (holder, lut_size, tone)))


def host_run(sc: Scenario):
    """Run ``pakon_autotone.analyze_auto_tone`` over the same scenario."""
    subs = PatternSubsystems(sc)
    subs.sc._tone_from_cna = sc._tone_from_cna
    subs.sc._edge_hist = sc._edge_hist
    subs.sc._elmo = sc._elmo
    ctx = at.AutoToneContext(scene_type=sc._scene_type)
    ctx.tone_object = 0xDEADBEEF
    cs = at.CapabilitySet()
    for spec in at.CAPABILITIES:
        if spec.name in sc.missing:
            continue
        rtti = spec.rtti_class
        if sc.wrong_vftable and sc.wrong_vftable[0] == spec.name:
            rtti = next(s.rtti_class for s in at.CAPABILITIES
                        if s.name == sc.wrong_vftable[1])
        cs.insert(at.Capability(name=spec.name, rtti_class=rtti,
                                enabled=spec.name in sc.enabled))
    thrown = None
    try:
        at.analyze_auto_tone(ctx, cs, holder=sc.holder, arg2=sc.arg2,
                             subsystems=subs)
    except at.AutoToneError as exc:
        thrown = str(exc)
    return {
        "tone": (ctx.tone_object or 0) & 0xFFFFFFFF,
        "scene_type": ctx.scene_type,
        "calls": subs.calls,
        "thrown": thrown,
    }


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------


def normalise_dll_calls(sc: Scenario, calls):
    """Drop the find records and rewrite ``ctx+0x4bc`` to a symbol."""
    out = []
    for name, args in calls:
        if name.startswith("find:"):
            continue
        a = tuple("&ctx+0x4bc" if v == sc.ctx + at.CTX_TONEHELPER_SCALAR else v
                  for v in args)
        out.append((name, a))
    return out


def lookup_order(calls) -> list[str]:
    return [n[5:] for n, _ in calls if n.startswith("find:")]


CASES: list[tuple[str, dict]] = [
    ("shipped (six on, pfd off)", {}),
    ("scene_type=1 (epilogue zeroes tone)", {"scene_type": 1}),
    ("scene_type=4", {"scene_type": 4}),
    ("scene_type=7", {"scene_type": 7}),
    ("cna off", {"enabled": {"dra", "toneHelper", "contrast", "ast", "citras"}}),
    ("dra off", {"enabled": {"cna", "toneHelper", "contrast", "ast", "citras"}}),
    ("toneHelper off",
     {"enabled": {"cna", "dra", "contrast", "ast", "citras"}}),
    ("contrast off", {"enabled": {"cna", "dra", "toneHelper", "ast", "citras"}}),
    ("ast off", {"enabled": {"cna", "dra", "toneHelper", "contrast", "citras"}}),
    ("citras off", {"enabled": {"cna", "dra", "toneHelper", "contrast", "ast"}}),
    ("pfd ON (the dead stage forced live)",
     {"enabled": {"cna", "dra", "toneHelper", "contrast", "ast", "pfd",
                  "citras"}}),
    ("all off", {"enabled": set()}),
    ("cna yields no tone -> dra takes 0x10131020",
     {"tone_from_cna": False}),
    ("cna yields no edge hist -> th takes 0x1010c0f0", {"edge_hist": False}),
    ("no tone and no edge hist",
     {"tone_from_cna": False, "edge_hist": False}),
    ("only cna", {"enabled": {"cna"}}),
    ("only citras", {"enabled": {"citras"}}),
    ("only toneHelper", {"enabled": {"toneHelper"}}),
    ("bElmoOccured=0 -> contrast x = toneHelper +0xb4", {"elmo": False}),
    ("bElmoOccured=0, scene_type=4 (no reset)",
     {"elmo": False, "scene_type": 4}),
    ("bElmoOccured=0, toneHelper off", {"elmo": False,
     "enabled": {"cna", "dra", "contrast", "ast", "citras"}}),
]

NOT_FOUND_CASES = [
    ("cna", "Cna capability not found.", 845),
    ("dra", "Dra capability not found.", 846),
    ("toneHelper", "ToneHelper capability not found.", 847),
    ("contrast", "ContrastAdjust capability not found.", 849),
    ("ast", "Ast capability not found.", 850),
    ("pfd", "Pfd capability not found.", 851),
    ("citras", "Citras capability not found.", 852),
]


def _mk(pe: bytes, **kw) -> Scenario:
    scene_type = kw.pop("scene_type", 0)
    tone_from_cna = kw.pop("tone_from_cna", True)
    edge_hist = kw.pop("edge_hist", True)
    elmo = kw.pop("elmo", True)
    sc = Scenario(pe, scene_type=scene_type, tone_from_cna=tone_from_cna,
                  edge_hist=edge_hist, elmo=elmo, **kw)
    sc._scene_type = scene_type
    sc._tone_from_cna = tone_from_cna
    sc._edge_hist = edge_hist
    sc._elmo = elmo
    return sc


def main(argv: list[str]) -> int:
    dll = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll.exists():
        print(f"{dll} not found — run "
              f"'python3 tools/re/reachability.py extract' first")
        return 2
    pe = dll.read_bytes()
    bad = 0

    # ---- 1. the layout probe -------------------------------------------
    print("== layout probe: which offset did each threaded value come from ==")
    sc = _mk(pe)
    d = sc.run()
    probe_ok = True

    def _probe(label, got, struct_name, field):
        nonlocal probe_ok
        want_off = at.layout_offset(struct_name, field)
        got_off = got & 0xFFFF
        ok = (got & 0xFFFF0000) == PATTERN_BASE and got_off == want_off
        probe_ok = probe_ok and ok
        print(f"  {label:<34} dll={got:#010x} -> {struct_name}+{got_off:#04x}"
              f"  expected {field}+{want_off:#04x}  "
              f"{'OK' if ok else 'FAIL'}")

    calls = dict(normalise_dll_calls(sc, d["calls"]))
    _probe("ctx+0x64d0 after contrast", d["tone"],
           "AnsContrastAdjustResults", "OutToneLut")
    _probe("citras lutSize arg", calls["citras.analyze"][1],
           "AnsContrastAdjustResults", "lutSize")
    _probe("dra lumHist arg", calls["dra.acquireHist"][1],
           "AnsCnaResults", "LuminanceHist")
    _probe("dra edgeHist arg", calls["dra.acquireHist"][2],
           "AnsCnaResults", "EdgeHist")
    _probe("th lumHist arg", calls["th.acquireHist"][1],
           "AnsCnaResults", "LuminanceHist")
    _probe("th edgeHist arg", calls["th.acquireHist"][2],
           "AnsCnaResults", "EdgeHist")
    _probe("dra tone arg (cna ToneScaleLut)", calls["dra.acquireHist"][3],
           "AnsCnaResults", "ToneScaleLut")
    # bElmoOccured is byte +0x5c of the pattern dword 0x5a5a005c -> low byte 0x5c
    _probe("contrast x arg (elmoAggressiveness)",
           calls["contrast.acquire"][2], "AnsCnaParams", "elmoAggressiveness")
    bad += not probe_ok
    print(f"  layout probe: {'ALL OK' if probe_ok else 'FAILED'}\n")

    # ---- 2. tone-object identity after every stage ----------------------
    print("== ctx+0x64d0 threading, stage by stage ==")
    for label, want_struct, want_field, kw in (
        ("cna only", "AnsCnaResults", "ToneScaleLut", {"enabled": {"cna"}}),
        ("cna+dra", "AnsDraResults", "DraLut", {"enabled": {"cna", "dra"}}),
        ("cna+dra+th (th must NOT write it)", "AnsDraResults", "DraLut",
         {"enabled": {"cna", "dra", "toneHelper"}}),
        ("+contrast", "AnsContrastAdjustResults", "OutToneLut",
         {"enabled": {"cna", "dra", "toneHelper", "contrast"}}),
    ):
        s = _mk(pe, **kw)
        r = s.run()
        want = PATTERN_BASE | at.layout_offset(want_struct, want_field)
        ok = r["tone"] == want
        bad += not ok
        print(f"  {label:<36} dll={r['tone']:#010x} "
              f"want {want_struct}.{want_field}={want:#010x} "
              f"{'OK' if ok else 'FAIL'}")
    print()

    # ---- 3. host vs DLL over the whole case matrix ----------------------
    print("== host pakon_autotone vs DLL ==")
    for label, kw in CASES:
        s = _mk(pe, **kw)
        d = s.run()
        h = host_run(s)
        dll_calls = normalise_dll_calls(s, d["calls"])
        order = lookup_order(d["calls"])
        problems = []
        if order != list(at.LOOKUP_ORDER):
            problems.append(f"lookup order {order}")
        if dll_calls != h["calls"]:
            problems.append("call sequence")
        if d["tone"] != h["tone"]:
            problems.append(f"tone dll={d['tone']:#x} host={h['tone']:#x}")
        if d["scene_type"] != h["scene_type"]:
            problems.append(
                f"scene_type dll={d['scene_type']} host={h['scene_type']}")
        # Every Cap-level acquire/analyze must have reached its own Impl, in
        # the same order -- this is what makes the dra / toneHelper branch
        # choice observable rather than inferred from the Cap entry alone.
        want_impls = [n for n, _ in dll_calls if n in SUBSYSTEM_IMPLS]
        if d["impls"] != want_impls:
            problems.append(
                f"impls reached {d['impls']} != {want_impls}")
        ok = not problems
        bad += not ok
        print(f"  {label:<44} {len(dll_calls):>2} calls  "
              f"tone={d['tone']:#010x} scene={d['scene_type']} "
              f"{'OK' if ok else 'FAIL ' + '; '.join(problems)}")
        if problems and "call sequence" in problems:
            for i in range(max(len(dll_calls), len(h["calls"]))):
                a = dll_calls[i] if i < len(dll_calls) else None
                b = h["calls"][i] if i < len(h["calls"]) else None
                if a != b:
                    print(f"      [{i}] dll={a}\n          host={b}")
    print()

    # ---- 4. the "<Name> capability not found." fallback -----------------
    print("== 0x1001ed90 not-found fallback (wrong RTTI type + absent) ==")
    for name, msg, line in NOT_FOUND_CASES:
        other = "citras" if name != "citras" else "cna"
        for kind, kw in (("wrong vftable", {"wrong_vftable": (name, other)}),
                         ("absent from set", {"missing": {name}})):
            s = _mk(pe, **kw)
            d = s.run()
            h = host_run(s)
            got = d["thrown"]
            ok = (got is not None and got[0] == msg and got[2] == line
                  and h["thrown"] is not None and msg in h["thrown"])
            # everything after the failing lookup must not run
            reached = [n for n, _ in d["calls"] if not n.startswith("find:")]
            ok = ok and not reached
            bad += not ok
            print(f"  {name:<11} {kind:<16} dll={got} "
                  f"post-calls={len(reached)} {'OK' if ok else 'FAIL'}")
    print()

    # ---- 5. cap+0xf, written by every Cap wrapper -----------------------
    s = _mk(pe)
    d = s.run()
    want_f = {n: (1 if n in s.enabled else 0) for n in s.caps}
    ok = d["cap_ok_byte"] == want_f
    bad += not ok
    print("== cap+0xf ('last call OK'), written by the real Cap wrappers ==")
    print(f"  {d['cap_ok_byte']}  {'OK' if ok else 'FAIL want ' + str(want_f)}")
    print()

    if bad:
        print(f"FAILED {bad} check(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
