#!/usr/bin/env python3
r"""Golden ``toneHelper`` **decision-tree walker** vs PakonIMAu.dll.

The walker (``0x101db890``, 751 B) is split out of
``pakon_toneHelper_core_golden.py`` because it is verifiable to a completely
different standard: it does no arithmetic beyond one ``fcom``, so every one of
its 30 switch arms and both of its branch directions can be forced
deliberately and checked exhaustively.  The rest of the subsystem is
floating-point and can only be checked on representative input.

WHAT RUNS FOR REAL
==================
``0x101db890`` executes start to finish on every case, and so does the whole
verifier chain it gates on:

    0x101db8cf  -> 0x101da3b0  AnsToneHelperParams::verifyDecisionTree
                  -> 0x101d9db0  ::checkDecisionNode  (recursive, both children)

Nothing about the walk is intercepted.  A ``UC_HOOK_CODE`` on ``0x101db970``
(the top of the node loop) records ``EAX`` — the node index — on every
iteration, so the **path** through the tree is observable, not just the
result.  That is what makes "exercises the branching" checkable rather than
asserted: the DLL's own visited-node sequence is compared against the port's.

THE THREE LAYOUT PROBES
=======================
Each of the 29 metric ids 2..30 is given a **distinct** float32 value, and a
29-deep chain is built where node *k* tests metric *k+2*:

* ``probe lessEqual`` — threshold = value(k+2) + 1.0.  Every node must fall
  to ``lessEqual``, so the walk must visit 0,1,…,28 then the class-2 terminal.
  If any switch arm read the wrong ``impl`` offset it would see a different
  metric's value, the compare would flip, and the walk would divert to the
  class-4 escape terminal on that exact node.
* ``probe greater`` — threshold = value(k+2) - 1.0.  Mirror image.
* ``probe equal`` — threshold = value(k+2) exactly.  ``fcom`` sets C0 = 0 on
  equality and ``test ah,5 ; jp`` therefore takes ``[edx+0xc]``, so **every**
  node must go *greater*.  This is the one boundary the tree files' own
  "lessEqual" column name gets wrong, and it is checked here rather than
  assumed.

Then the shipped ``AllOnTree1`` is walked with hand-chosen metric vectors that
between them reach 11 different terminal nodes, both terminal classes on the
``< 3`` side, and the ``>= 3`` clamp.

WHAT IS STUBBED (and why none of it is vendor arithmetic)
=========================================================
* ``operator new``/``delete`` and the MSVCP71 ``basic_string`` ctor/dtor/
  ``operator+=`` imports — the PE is loaded unbound and CRT init never runs.
  ``0x101d9db0`` builds an ``"In node number"`` string unconditionally at its
  top (``0x101d9dd1``) and destroys it at ``0x101da389``, so the stubs are on
  the success path; they carry no numeric meaning.
* ``0x1001ed90`` / ``0x10020ad0`` — the two exception raisers.  Recorded, not
  executed.  The invalid-tree cases below check that they are *reached*, with
  the right source line.
* The ``AnsStatus`` smart-pointer helpers ``0x10001530``/``0x10001560``/
  ``0x10001580``/``0x100065e0``/``0x100012e0`` run for real; with the OK
  sentinel ``[0x106b5bd4]`` being 0 in the shipped image every refcount guard
  takes its null branch anyway.

dei
===
Nothing here touches dei.  The tree walked is the one at ``impl+0x78``, which
``toneHelper-default.dpi`` fills from ``decisionTree = AllOnTree1``.
``deiTree1`` belongs to ``ColorNegativePath::CalcDei``'s separate call into the
same shared code — see ``pakon_toneHelper.py``'s header.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_toneHelper_tree_golden.py [dll]``

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
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, \
    UC_X86_REG_ESP

import pakon_toneHelper as th

IMAGE_BASE = 0x10000000
STACK = 0x0BF00000
STACK_SZ = 0x00800000
HEAP = 0x0D000000
HEAP_SZ = 0x01000000
SCRATCH = 0x00100000
RET_MAGIC = 0x00110000

VA_OP_NEW = 0x104FFD53
VA_OP_DELETE = 0x104FFDD0
VA_OP_DELETE_ARR = 0x104FFE3E
IAT_STRING_CTOR = 0x10573394       # basic_string(const char*)
IAT_STRING_DTOR = 0x10573418       # ~basic_string()
IAT_STRING_APPEND_C = 0x10573204   # operator+=(char)
IAT_STRING_APPEND_S = 0x105731D4   # operator+=(const char*)
IAT_STRING_ASSIGN = 0x1057327C     # operator=(const char*)
IAT_ITOA = 0x105735A0

VA_WALK = th.WALK_TREE             # 0x101db890
VA_NODE_LOOP = 0x101DB970          # top of the walk loop; EAX == node index
VA_THROW1 = 0x1001ED90
VA_THROW2 = 0x10020AD0

DEFAULT_DLL = Path("/tmp/pakon_re/PakonIMAu.dll")


def _align(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


class Emu:
    """Minimal PakonIMAu.dll emulator: bump heap, CRT stubs, flat SEH head."""

    def __init__(self, pe: bytes):
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        self.uc = uc
        self.pe = pe
        self._load()
        uc.mem_map(0, 0x1000)
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
        # MSVCP71 std::string: a 0x20-byte scratch object we never inspect.
        for iat, pop in ((IAT_STRING_CTOR, 4), (IAT_STRING_APPEND_C, 4),
                         (IAT_STRING_APPEND_S, 4), (IAT_STRING_ASSIGN, 4)):
            s = self.stub()
            self.wu32(iat, s)
            self.hook(s, self._string_this)
            self._pop[s] = pop
        s = self.stub()
        self.wu32(IAT_STRING_DTOR, s)
        self.hook(s, lambda e, a: (None, 0))
        # _itoa(value, buf, radix) -> buf; the digits are never read back.
        s = self.stub()
        self.wu32(IAT_ITOA, s)
        self.hook(s, lambda e, a: (e.r32(a + 4), 0))

    _pop: dict[int, int] = {}

    @staticmethod
    def _string_this(e: "Emu", args: int):
        this = e.uc.reg_read(UC_X86_REG_ECX)
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

    def wf32(self, a: int, v: float) -> None:
        self.uc.mem_write(a, struct.pack("<f", float(v)))

    def r32(self, a: int) -> int:
        return struct.unpack("<I", self.uc.mem_read(a, 4))[0]

    def ri32(self, a: int) -> int:
        return struct.unpack("<i", self.uc.mem_read(a, 4))[0]

    def rf32(self, a: int) -> float:
        return struct.unpack("<f", self.uc.mem_read(a, 4))[0]

    def cstr(self, a: int, limit: int = 120) -> str:
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

    def watch(self, va: int, fn) -> None:
        """Observe without intercepting — used for the node-loop probe."""
        self.uc.hook_add(UC_HOOK_CODE,
                         lambda uc, a, s, u: fn(self), begin=va, end=va)

    def _on_bad_mem(self, uc, access, address, size, value, _u):
        self.faults.append(
            f"bad mem access={access} addr={address:#x} "
            f"eip={uc.reg_read(UC_X86_REG_EIP):#x}")
        return False

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
            uc.emu_start(va, RET_MAGIC, timeout=0, count=100_000_000)
        except UcError as ex:
            raise RuntimeError(
                f"emu {va:#x} eip={uc.reg_read(UC_X86_REG_EIP):#x}: {ex}"
                + ("; " + "; ".join(self.faults[:2]) if self.faults else "")
            ) from ex
        if self.faults:
            raise RuntimeError(f"emu {va:#x} faults: {self.faults[:2]}")
        return uc.reg_read(UC_X86_REG_EAX)


# ---------------------------------------------------------------------------
# one emulated walk
# ---------------------------------------------------------------------------

#: The Impl fields the walker touches.  Everything else in the 0x140-byte
#: object is left zero, which is exactly what allocateMemory leaves behind.
IMPL_SIZE = 0x200
OFF_NODE_COUNT = 0x70       # 0x101db8ba  mov eax, dword [esi + 0x70]
OFF_NODE_ARRAY = 0x78       # 0x101db8b7  mov ebp, dword [esi + 0x78]
OFF_TERMINAL = 0x12C        # 0x101dbaf4  mov dword [esi + 0x12c], eax
OFF_TONE_VALUE = 0x134      # 0x101dbb08 / 0x101dbb1a
OFF_SCENE_CLASS = 0x138     # 0x101dbb12 / 0x101dbb27


def make_error_status(e: Emu) -> int:
    """A non-OK ``AnsStatus`` object the DLL's own smart pointers can hold.

    ``0x100065e0``/``0x100012e0`` are a ``lock inc``/``lock dec`` on
    ``obj+0x74`` and ``0x10001530``/``0x10001580`` call ``(**obj)(1)`` — the
    virtual destructor — when that count hits zero.  Seeding the count high
    keeps the destructor unreached; slot 0 of the vftable is a ``ret 4`` stub
    in case it ever is.
    """
    dtor = e.stub()
    e.uc.mem_write(dtor, b"\xC2\x04\x00")          # ret 4
    vft = e.alloc(0x40)
    e.wu32(vft, dtor)
    obj = e.alloc(0x100)
    e.wu32(obj, vft)
    e.wu32(obj + 0x74, 0x01000000)
    return obj


def run_dll(pe: bytes, nodes, metrics: dict[int, float]):
    """Run the real ``0x101db890`` and return what it wrote plus the path."""
    e = Emu(pe)
    thrown: list[tuple[str, int]] = []
    err = make_error_status(e)

    def throw1(emu: Emu, a: int):
        # 0x1001ed90(&sret, kind, func, msg, file, line) -- cdecl
        thrown.append((emu.cstr(emu.r32(a + 12)), emu.r32(a + 20)))
        emu.wu32(emu.r32(a), err)
        return emu.r32(a), 0

    def throw2(emu: Emu, a: int):
        # 0x10020ad0(&sret, kind, func, &str, file, line) -- cdecl
        thrown.append((emu.cstr(emu.r32(a + 8)), emu.r32(a + 20)))
        emu.wu32(emu.r32(a), err)
        return emu.r32(a), 0

    e.hook(VA_THROW1, throw1)
    e.hook(VA_THROW2, throw2)

    path: list[int] = []
    e.watch(VA_NODE_LOOP, lambda em: path.append(em.uc.reg_read(UC_X86_REG_EAX)))

    impl = e.alloc(IMPL_SIZE)
    blob = b"".join(n.pack() for n in nodes)
    arr = e.alloc(max(len(blob), 4), blob)
    e.wi32(impl + OFF_NODE_COUNT, len(nodes))
    e.wu32(impl + OFF_NODE_ARRAY, arr)
    for mid, val in metrics.items():
        e.wf32(impl + th.metric_impl_offset(mid), val)

    sret = e.alloc(0x10)
    e.call(VA_WALK, [sret], ecx=impl)
    return {
        "terminal": e.ri32(impl + OFF_TERMINAL),
        "tone": e.ri32(impl + OFF_TONE_VALUE),
        "cls": e.ri32(impl + OFF_SCENE_CLASS),
        "path": tuple(path),
        "status": e.r32(sret),
        "thrown": thrown,
    }


def run_host(nodes, metrics: dict[int, float]):
    r = th.walk_decision_tree(nodes, metrics)
    return {"terminal": r.terminal_node, "tone": r.tone_value,
            "cls": r.scene_class, "path": r.path}


# ---------------------------------------------------------------------------
# probes
# ---------------------------------------------------------------------------

#: A distinct, exactly-representable float32 per metric id 2..30.
PROBE_METRICS = {mid: float(mid) * 8.0 + 0.25 for mid in range(2, 31)}

N = th.DecisionNode


def probe_tree(kind: str):
    """29 chained nodes, one per metric id, plus two terminals.

    ``lessEqual`` -> every node must fall through to the next; ``greater`` and
    ``equal`` -> every node must jump to node ``k+1`` via the *greater* edge.
    Either way a wrong switch arm sends the walk to the escape terminal, and
    the escape terminal is a different node index and a different class, so it
    is visible in all three observables.
    """
    n_metrics = 29                       # ids 2..30
    escape = n_metrics + 1               # node 30
    nodes = []
    for k in range(n_metrics):
        mid = k + 2
        v = PROBE_METRICS[mid]
        if kind == "lessEqual":
            thr, le, gt = v + 1.0, k + 1, escape
        elif kind == "greater":
            thr, le, gt = v - 1.0, escape, k + 1
        else:                            # equal -> C0 == 0 -> greater
            thr, le, gt = v, escape, k + 1
        nodes.append(N(mid, th.f32(thr), le, gt, 0))
    nodes.append(N(th.METRIC_TERMINAL, 0.0, -1, -1, 2))   # 29: the good end
    nodes.append(N(th.METRIC_TERMINAL, 0.0, -1, -1, 4))   # 30: the escape
    return tuple(nodes)


#: Metric vectors for the shipped ``AllOnTree1``.
#:
#: A real finding about this file, worth writing down: its live root is
#: ``0  LUM_STDDEV  1.000  1  24  4`` and the ``285.044`` root directly above
#: it is **commented out**.  A 1.000 threshold on a standard deviation is
#: effectively always exceeded, so on this tree the *greater* edge goes
#: straight to node 24 (terminal, class 4 -> clamped to (2, 3)) and nodes
#: 12..23 are unreachable.  Only nodes 0..11 and 24 can ever be visited.
#: The 12..23 subtree is exercised below through ``dTree1``, which has the
#: same shape with the 285.044 root live.
ALLON_VECTORS: tuple[tuple[str, dict[str, float]], ...] = (
    ("root goes greater (STDDEV >= 1.0) -> 24, class 4 CLAMPED",
     {"LUM_STDDEV": 300.0}),
    ("root exactly 1.0 -> greater (equality goes GREATER)",
     {"LUM_STDDEV": 1.0}),
    ("root just below 1.0 -> lessEqual",
     {"LUM_STDDEV": 0.99999994}),
    ("node1 lessEqual -> terminal 2",
     {"LUM_STDDEV": 0.5, "EDGE_WORK_TOTAL": 10.0}),
    ("node1 exactly 57.672 -> greater -> node3",
     {"LUM_STDDEV": 0.5, "EDGE_WORK_TOTAL": 57.672, "LUM_WORK_TOTAL": 300.0}),
    ("LUM_WORK_TOTAL high -> node5 terminal 2",
     {"LUM_STDDEV": 0.5, "EDGE_WORK_TOTAL": 100.0, "LUM_WORK_TOTAL": 300.0}),
    ("EDGE_WORK_LOW high -> node7 (class 3)",
     {"LUM_STDDEV": 0.5, "EDGE_WORK_TOTAL": 100.0, "LUM_WORK_TOTAL": 100.0,
      "EDGE_WORK_LOW": 100.0}),
    ("LUM_SKEW low -> node8 (class 2), 6 nodes deep",
     {"LUM_STDDEV": 0.5, "EDGE_WORK_TOTAL": 100.0, "LUM_WORK_TOTAL": 100.0,
      "EDGE_WORK_LOW": 10.0, "LUM_SKEW": 0.0}),
    ("LUM_SKEW high -> node9 -> node10 (class 2), 7 deep",
     {"LUM_STDDEV": 0.5, "EDGE_WORK_TOTAL": 100.0, "LUM_WORK_TOTAL": 100.0,
      "EDGE_WORK_LOW": 10.0, "LUM_SKEW": 5.0, "LUM_WORK_HIGH": 10.0}),
    ("... LUM_WORK_HIGH high -> node11 (class 3)",
     {"LUM_STDDEV": 0.5, "EDGE_WORK_TOTAL": 100.0, "LUM_WORK_TOTAL": 100.0,
      "EDGE_WORK_LOW": 10.0, "LUM_SKEW": 5.0, "LUM_WORK_HIGH": 100.0}),
)

#: ``dTree1`` — ``toneHelper-CNPremium.dpi``'s tree, same 25 nodes but with the
#: ``285.044`` root live and every class-2 terminal rewritten to class 0.  It
#: is the only shipped file that reaches nodes 12..24, so it is what exercises
#: the walker's deep right-hand subtree and the class-0 / class-4 terminals.
DTREE_VECTORS: tuple[tuple[str, dict[str, float]], ...] = (
    ("left subtree still works -> node2 (class 0)",
     {"LUM_STDDEV": 10.0, "EDGE_WORK_TOTAL": 10.0}),
    ("node12 -> 13 -> 14 -> 16 (class 0)",
     {"LUM_STDDEV": 300.0, "EDGE_WORK_TOTAL": 100.0, "LUM_SKEW": 0.0,
      "EDGE_WORK_SUMLOW": 10.0}),
    ("... EDGE_WORK_SUMLOW high -> node17 (class 3)",
     {"LUM_STDDEV": 300.0, "EDGE_WORK_TOTAL": 100.0, "LUM_SKEW": 0.0,
      "EDGE_WORK_SUMLOW": 100.0}),
    ("... LUM_SKEW high -> node15 -> node18 (class 0)",
     {"LUM_STDDEV": 300.0, "EDGE_WORK_TOTAL": 100.0, "LUM_SKEW": 1.0,
      "EDGE_WORK_HIGH": 1.0}),
    ("... EDGE_WORK_HIGH high -> node19 (class 3)",
     {"LUM_STDDEV": 300.0, "EDGE_WORK_TOTAL": 100.0, "LUM_SKEW": 1.0,
      "EDGE_WORK_HIGH": 100.0}),
    ("node12 greater -> node20 -> node21 (class 3)",
     {"LUM_STDDEV": 300.0, "EDGE_WORK_TOTAL": 200.0}),
    ("node20 greater -> node22 -> node24 (class 4, CLAMPED)",
     {"LUM_STDDEV": 500.0, "EDGE_WORK_TOTAL": 200.0, "LUM_SKEW": 0.0}),
    ("node22 LUM_SKEW low -> node23 (class 3)",
     {"LUM_STDDEV": 500.0, "EDGE_WORK_TOTAL": 200.0, "LUM_SKEW": -1.0}),
    ("node22 LUM_SKEW exactly -0.062 -> greater -> node24",
     {"LUM_STDDEV": 500.0, "EDGE_WORK_TOTAL": 200.0, "LUM_SKEW": -0.062}),
)


def vector_to_ids(named: dict[str, float]) -> dict[int, float]:
    """Fill all 29 metric slots; named ones set, the rest deliberately hostile.

    The filler is a large negative value: if a switch arm read the wrong slot
    the compare would flip on almost every node in ``AllOnTree1``, so a
    mis-mapped offset cannot pass by luck.
    """
    ids = {mid: -1.0e9 for mid in range(2, 31)}
    for name, val in named.items():
        ids[th.METRIC_ID[name]] = th.f32(val)
    return ids


# ---------------------------------------------------------------------------
# invalid trees -- verifyDecisionTree / checkDecisionNode must reject
# ---------------------------------------------------------------------------

INVALID_TREES: tuple[tuple[str, tuple, int], ...] = (
    ("TERMINAL with non -1 gotos",
     (N(th.METRIC_TERMINAL, 0.0, 1, -1, 2), N(th.METRIC_TERMINAL, 0.0, -1, -1, 2)),
     343),
    ("metric id 0 (NONE) is rejected",
     (N(0, 1.0, 1, 2, 0), N(th.METRIC_TERMINAL, 0.0, -1, -1, 2),
      N(th.METRIC_TERMINAL, 0.0, -1, -1, 3)),
     357),
    ("metric id 31 is rejected",
     (N(31, 1.0, 1, 2, 0), N(th.METRIC_TERMINAL, 0.0, -1, -1, 2),
      N(th.METRIC_TERMINAL, 0.0, -1, -1, 3)),
     357),
    ("backward lessEqualGoto is rejected",
     (N(2, 1.0, 1, 2, 0), N(2, 1.0, 0, 2, 0),
      N(th.METRIC_TERMINAL, 0.0, -1, -1, 2)),
     372),
    ("lessEqualGoto == nNodes is rejected",
     (N(2, 1.0, 3, 2, 0), N(th.METRIC_TERMINAL, 0.0, -1, -1, 2),
      N(th.METRIC_TERMINAL, 0.0, -1, -1, 3)),
     372),
    ("greaterGoto out of range is rejected (line 385, not 372)",
     (N(2, 1.0, 1, 9, 0), N(th.METRIC_TERMINAL, 0.0, -1, -1, 2),
      N(th.METRIC_TERMINAL, 0.0, -1, -1, 3)),
     385),
)


def main(argv: list[str]) -> int:
    dll = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll.exists():
        alt = dll.parent / "bin" / dll.name
        if alt.exists():
            dll = alt
        else:
            print(f"{dll} not found — run "
                  f"'python3 tools/re/reachability.py extract' first")
            return 2
    pe = dll.read_bytes()
    bad = 0

    def compare(label: str, nodes, metrics) -> bool:
        nonlocal bad
        d = run_dll(pe, nodes, metrics)
        h = run_host(nodes, metrics)
        keys = ("terminal", "tone", "cls", "path")
        ok = all(d[k] == h[k] for k in keys) and d["status"] == 0
        bad += not ok
        head = (f"  {label:<48} node={d['terminal']:>3} "
                f"value={d['tone']} class={d['cls']} depth={len(d['path'])}")
        print(f"{head} {'OK' if ok else 'FAIL'}")
        if not ok:
            for k in keys:
                if d[k] != h[k]:
                    print(f"      {k}: dll={d[k]} host={h[k]}")
            if d["status"]:
                print(f"      status={d['status']:#x} thrown={d['thrown']}")
        return ok

    # ---- 1. per-switch-arm layout probes --------------------------------
    print("== layout probe: all 29 metric switch arms, both branch "
          "directions ==")
    for kind in ("lessEqual", "greater", "equal"):
        nodes = probe_tree(kind)
        want_depth = 30                      # 29 test nodes + the terminal
        d = run_dll(pe, nodes, PROBE_METRICS)
        h = run_host(nodes, PROBE_METRICS)
        expect_path = tuple(range(30))
        ok = (d["path"] == expect_path and h["path"] == expect_path
              and d["terminal"] == h["terminal"] == 29
              and d["tone"] == h["tone"] == 1
              and d["cls"] == h["cls"] == 2)
        bad += not ok
        print(f"  probe {kind:<10} visited {len(d['path'])}/{want_depth} nodes"
              f"  terminal={d['terminal']} class={d['cls']}  "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            div = next((i for i, (a, b) in
                        enumerate(zip(d["path"], expect_path)) if a != b), None)
            print(f"      dll path  = {d['path']}")
            print(f"      host path = {h['path']}")
            print(f"      first divergence at step {div} -> metric id "
                  f"{div + 2 if div is not None else '?'} "
                  f"({th.METRIC_NAMES[div + 2] if div is not None else ''})")
    print()

    # ---- 2. the shipped AllOnTree1 --------------------------------------
    print("== shipped AllOnTree1 (toneHelper-default.dpi decisionTree) ==")
    tree = th.load_tree("AllOnTree1")
    print(f"  {len(tree)} nodes; root tests "
          f"{th.METRIC_NAMES[tree[0].metric]} @ {tree[0].threshold}")
    visited: set[int] = set()
    terminals: set[int] = set()
    for label, named in ALLON_VECTORS:
        ids = vector_to_ids(named)
        if compare(label, tree, ids):
            h = run_host(tree, ids)
            terminals.add(h["terminal"])
            visited.update(h["path"])
    print(f"  terminals reached {sorted(terminals)}; "
          f"nodes visited {sorted(visited)}")
    # nodes 12..23 are unreachable through the live root -- see ALLON_VECTORS.
    ok = visited == set(range(12)) | {24}
    bad += not ok
    print(f"  every reachable node of AllOnTree1 was visited: "
          f"{'OK' if ok else 'FAIL ' + str(sorted(set(range(12)) | {24}))}")
    print()

    # ---- 3. dTree1 — the same walker over the deep right-hand subtree ----
    print("== dTree1 (toneHelper-CNPremium.dpi's tree; reaches nodes 12..24) ==")
    d1 = th.load_tree("dTree1")
    visited = set()
    terminals = set()
    for label, named in DTREE_VECTORS:
        ids = vector_to_ids(named)
        if compare(label, d1, ids):
            h = run_host(d1, ids)
            terminals.add(h["terminal"])
            visited.update(h["path"])
    print(f"  terminals reached {sorted(terminals)}; "
          f"nodes visited {sorted(visited)}")
    ok = visited >= {12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}
    bad += not ok
    print(f"  deep subtree 12..24 exercised: {'OK' if ok else 'FAIL'}")
    print()

    # ---- 4. verifyDecisionTree / checkDecisionNode rejections -----------
    print("== 0x101da3b0 -> 0x101d9db0 must reject a malformed tree ==")
    for label, nodes, line in INVALID_TREES:
        d = run_dll(pe, nodes, PROBE_METRICS)
        host_raised = None
        try:
            th.walk_decision_tree(nodes, PROBE_METRICS)
        except th.ToneHelperError as exc:
            host_raised = str(exc)
        dll_lines = [ln for _m, ln in d["thrown"]]
        ok = (line in dll_lines and host_raised is not None
              and str(line) in host_raised and not d["path"])
        bad += not ok
        print(f"  {label:<42} dll lines={dll_lines} walked={len(d['path'])} "
              f"{'OK' if ok else 'FAIL'}")
        if not ok:
            print(f"      host={host_raised!r}")
    print()

    # ---- 5. an empty / NULL tree ----------------------------------------
    print("== 0x101da410 'A NULL decision tree is invalid.' (line 316) ==")
    e = Emu(pe)
    thrown: list[tuple[str, int]] = []
    e.hook(VA_THROW1, lambda em, a: (thrown.append(
        (em.cstr(em.r32(a + 12)), em.r32(a + 20))), em.wu32(em.r32(a), 0),
        (em.r32(a), 0))[-1])
    impl = e.alloc(IMPL_SIZE)          # node count and array both left 0
    sret = e.alloc(0x10)
    e.call(VA_WALK, [sret], ecx=impl)
    host_raised = None
    try:
        th.walk_decision_tree((), PROBE_METRICS)
    except th.ToneHelperError as exc:
        host_raised = str(exc)
    ok = (thrown and thrown[0][1] == 316 and host_raised
          and "316" in host_raised)
    bad += not ok
    print(f"  dll={thrown}  host={host_raised!r}  {'OK' if ok else 'FAIL'}")
    print()

    if bad:
        print(f"FAILED {bad} check(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
