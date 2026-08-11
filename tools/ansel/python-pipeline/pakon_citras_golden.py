#!/usr/bin/env python3
r"""Golden ``AnsCitrasCapabilityImpl::analyze`` vs PakonIMAu.dll.

Phase 2f.  Proves ``pakon_citras`` against the real ``0x10223a20`` executing
under Unicorn — the object state it leaves behind, the bytes it copies, the
allocations and frees it performs, and the exact ``(code, func, message, file,
line)`` of every status it builds.

WHAT RUNS FOR REAL
==================
All three vendor functions, start to finish, on every case:

    0x10223a20  AnsCitrasCapabilityImpl::analyze            627 B
    0x10223180  ...::validateParameters                     394 B
    0x10223810  ...::allocateMemory                         428 B

plus the AnsStatus refcount helpers they call (``0x100065e0`` addref,
``0x100012e0`` release, ``0x10001530``/``0x10001560``/``0x10001580`` smart-ptr
assign and destroy), the SEH prologues, and — the point of the whole thing —
the real ``rep movsd`` / ``rep movsb`` pair at ``0x10223c0c``/``0x10223c13``.
The copied bytes are read back out of emulated memory and compared to the
host's, so an off-by-one in the ``lea ecx, [edi+edi]`` byte count or a wrong
entry width could not pass.

Also emulated for real, as an independent check on the defaults table: the
straight-line block ``0x1022336f``..``0x102233c3`` of the impl constructor,
which is the *only* thing that installs ``AnsCitrasParams``.  It is run with
``edi`` pointed at a scratch object and the resulting 0x18 bytes are compared
against ``pakon_citras.default_params().pack()``.  Nothing in the port's default
table is asserted from a note; it is the vendor's own copy loop.

WHAT IS STUBBED (and why none of it is vendor arithmetic)
=========================================================
* ``operator new[]`` ``0x104ffd78`` (which is a bare ``jmp`` onto ``operator
  new`` ``0x104ffd53``) and ``operator delete[]`` ``0x104ffe3e`` — CRT.  The PE
  is loaded unbound and CRT init never runs, so there is no live heap in the
  image.  The stub is a bump allocator; it records every requested size and
  every freed pointer, which is how the harness observes the free at
  ``0x10223a70`` and the allocation at ``0x10223852`` at all.  It can also be
  told to return null, which is the only way to reach ``allocateMemory``'s
  ``0x1022385f`` failure branch.
* ``0x1001ed90`` — the AnsStatus builder.  Behind it is ``operator new(0x78)``
  plus ``0x1001f670``, an ``AnsStatus`` constructor that formats and stores the
  six arguments; running it would be testing MSVCP71 string machinery, not
  citras.  The stub records the six arguments verbatim — which is the entire
  observable — hands back a refcounted sentinel object, and returns ``arg0``
  exactly as the real one does (``0x1001edf5`` onward).  Sixteen of the thirty-seven
  cases below turn on those recorded arguments being byte-for-byte the image's
  own literals.

``[0x106b5bd4]``, the AnsStatus OK singleton, is **not** stubbed: it lives in
the tail of ``.data`` past ``SizeOfRawData`` (rva ``0x25bd4`` vs ``rsz
0x22000``), so it loads as 0, which is what makes ``OK == NULL`` and what
``pakon_citras.CITRAS_OK`` models.  Every ``cmp eax, [0x106b5bd4]`` in all three
functions therefore runs against the real global.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_citras_golden.py [dll]``

The DLL is not in the repo.  Extract it with
``python3 tools/re/reachability.py extract`` (default ``/tmp/pakon_re``).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import UcError, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EDI, UC_X86_REG_ESP

import pakon_autotone as at
import pakon_citras as ct
from pakon_autotone_shell_golden import DEFAULT_DLL, Emu

#: The block of the impl ctor (0x10223310) that installs AnsCitrasParams:
#: `fld qword [0x1058f458]` ... `mov cx, [0x1058f474]; mov [esi+0x14], cx`.
CTOR_DEFAULTS_BEGIN = 0x1022336F
CTOR_DEFAULTS_END = 0x102233C4          # `xor ebp, ebp`, the next statement

#: ``call operator delete[]`` at ``0x10223a70`` -- the only one in ``analyze``.
#: The free is observed here, at the call instruction with the argument already
#: pushed, rather than at ``0x104ffe3e``: ``Emu`` installs its own returning
#: stub there, and a second intercepting hook on the same address would run
#: after it and mistake the pushed argument for a return address.  A read-only
#: watch at the call site is order-independent.
DELETE_ARRAY_CALL_SITE = 0x10223A70

BIG_REFCOUNT = 0x01000000


class Run:
    """One emulated run of the real ``0x10223a20``."""

    def __init__(self, pe: bytes, *, params: ct.CitrasParams | None = None,
                 lut_size: int = 0x1000, tone: list[int] | None = None,
                 preexisting: list[int] | None = None,
                 fail_allocation: bool = False, holder: bool = False):
        self.emu = Emu(pe)
        e = self.emu
        self.fail_allocation = fail_allocation
        self.new_sizes: list[int] = []
        self.freed: list[int] = []
        self.statuses: list[dict] = []
        self.params = params if params is not None else ct.default_params()
        self.lut_size = lut_size
        self.tone = tone
        self.preexisting = preexisting

        # A vftable whose slot 0 is a `ret 4` thiscall destructor.  Nothing
        # should ever call it -- every refcount is seeded BIG_REFCOUNT so no
        # release reaches zero -- but a plain `ret` stub would silently unbalance
        # the stack if one ever did, and that must fail loudly instead.
        self.dtor = e.stub()
        e.uc.mem_write(self.dtor, b"\xC2\x04\x00")
        self.vftable = e.alloc(0x20)
        e.wu32(self.vftable, self.dtor)

        # AnsCitrasCapabilityImpl
        self.impl = e.alloc(ct.IMPL_SIZE + 0x20)
        e.wu32(self.impl, self.vftable)
        e.uc.mem_write(self.impl + ct.IMPL_PARAMS, bytes(self.params.pack()))
        if preexisting is not None:
            self.old_lut = e.alloc(max(len(preexisting) * 2, 4),
                                   struct.pack(f"<{len(preexisting)}H",
                                               *preexisting))
            e.wu32(self.impl + ct.IMPL_TONE_LUT, self.old_lut)
            e.wi32(self.impl + ct.IMPL_LUT_SIZE, len(preexisting))
        else:
            self.old_lut = 0

        # The tone LUT the shell threads in as ctx+0x64d0.
        if tone is None:
            self.tone_ptr = 0
        else:
            self.tone_ptr = e.alloc(max(len(tone) * 2, 4),
                                    struct.pack(f"<{len(tone)}H", *tone))

        # [ebp+0xc] -- analyze only ever releases this.  Optionally give it a
        # real refcounted object to prove it is never read.
        if holder:
            self.holder = e.alloc(0x20)
            e.wu32(self.holder, self.vftable)
            e.wu32(self.holder + 4, BIG_REFCOUNT)
        else:
            self.holder = 0

        self._hooks()

    # -- stubs -------------------------------------------------------------
    def _hooks(self) -> None:
        e = self.emu

        def op_new_array(emu: Emu, args: int):
            size = emu.r32(args)
            self.new_sizes.append(size)
            if self.fail_allocation or size >= 0x00400000:
                return 0, 0            # `push ecx; call` returned NULL
            return emu.alloc(max(size, 4), b"\xCD" * max(size, 4)), 0
        e.hook(ct.OP_NEW_ARRAY, op_new_array)

        def watch_delete(uc, address, size, _u):
            esp = uc.reg_read(UC_X86_REG_ESP)
            self.freed.append(struct.unpack("<I", uc.mem_read(esp, 4))[0])
        e.uc.hook_add(UC_HOOK_CODE, watch_delete,
                      begin=DELETE_ARRAY_CALL_SITE, end=DELETE_ARRAY_CALL_SITE)

        def make_status(emu: Emu, args: int):
            sret = emu.r32(args)
            rec = {
                "code": emu.r32(args + 4),
                "func": emu.cstr(emu.r32(args + 8)),
                "message": emu.cstr(emu.r32(args + 12)),
                "file": emu.cstr(emu.r32(args + 16)),
                "line": emu.r32(args + 20),
            }
            self.statuses.append(rec)
            obj = emu.alloc(0x80)
            emu.wu32(obj, self.vftable)
            emu.wu32(obj + 0x74, BIG_REFCOUNT)
            emu.wu32(sret, obj)
            return sret, 0             # cdecl; the real one returns arg0 too
        e.hook(ct.MAKE_STATUS, make_status)

    # -- run ---------------------------------------------------------------
    def run(self) -> dict:
        e = self.emu
        sret = e.alloc(0x10)
        e.call(ct.CITRAS_ANALYZE,
               [sret, self.holder, self.lut_size & 0xFFFFFFFF, self.tone_ptr],
               ecx=self.impl)
        lut_size = e.ri32(self.impl + ct.IMPL_LUT_SIZE)
        lut_ptr = e.r32(self.impl + ct.IMPL_TONE_LUT)
        raw = b""
        if lut_ptr and lut_size > 0:
            raw = bytes(e.uc.mem_read(lut_ptr, lut_size * 2))
        return {
            "status": self.statuses[-1] if e.r32(sret) else None,
            "lut_size": lut_size,
            "lut_null": lut_ptr == 0,
            "lut": raw,
            "new_sizes": list(self.new_sizes),
            "freed": list(self.freed),
        }


def host_run(r: Run) -> dict:
    """The same case through ``pakon_citras``."""
    state = ct.CitrasState(params=ct.CitrasParams(**vars(r.params)))
    if r.preexisting is not None:
        state.tone_lut = list(r.preexisting)
        state.lut_size = len(r.preexisting)
    state.fail_allocation = r.fail_allocation
    status = ct.citras_analyze(state, r.tone, r.lut_size)
    return {
        "status": None if status is None else {
            "code": status.code, "func": status.func,
            "message": status.message, "file": status.file,
            "line": status.line},
        "lut_size": state.lut_size,
        "lut_null": state.tone_lut is None,
        "lut": ct.tone_lut_bytes(state),
        "new_sizes": list(state.allocations),
        "freed": state.frees,
    }


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

def _ramp(n: int) -> list[int]:
    return [(i * 4093 + 0x1234) & 0xFFFF for i in range(n)]


P = ct.CitrasParams

CASES: list[tuple[str, dict]] = [
    # -- the two shapes analyzeAutoTone can actually produce ---------------
    ("shipped: default params, 0x1000-entry tone LUT",
     {"lut_size": 0x1000, "tone": _ramp(0x1000)}),
    ("tone == NULL (ctx+0x64d0 never got a LUT)",
     {"lut_size": 0x1000, "tone": None}),

    # -- the free at 0x10223a70 -------------------------------------------
    ("pre-existing LUT is delete[]d, then replaced",
     {"lut_size": 0x800, "tone": _ramp(0x800), "preexisting": _ramp(0x40)}),
    ("pre-existing LUT is delete[]d even when tone == NULL",
     {"lut_size": 0x800, "tone": None, "preexisting": _ramp(0x40)}),
    ("pre-existing LUT is delete[]d even when validation fails",
     {"lut_size": 0x800, "tone": _ramp(0x800), "preexisting": _ramp(0x40),
      "params": P(minValue=4095, maxValue=0)}),

    # -- the rep movsd / rep movsb split at 0x10223c0c --------------------
    ("lutSize 0 (new[0], zero-byte copy)", {"lut_size": 0, "tone": _ramp(4)}),
    ("lutSize 1 (odd -> 2-byte movsb tail)",
     {"lut_size": 1, "tone": _ramp(4)}),
    ("lutSize 2 (even -> one movsd, no tail)",
     {"lut_size": 2, "tone": _ramp(4)}),
    ("lutSize 3 (odd -> movsd + movsb tail)",
     {"lut_size": 3, "tone": _ramp(8)}),
    ("lutSize 0x101 (odd, large)",
     {"lut_size": 0x101, "tone": _ramp(0x101)}),
    ("copy takes lutSize entries, not len(tone)",
     {"lut_size": 0x10, "tone": _ramp(0x400)}),

    # -- holder is never read ---------------------------------------------
    ("live refcounted holder in [ebp+0xc] is not read",
     {"lut_size": 0x40, "tone": _ramp(0x40), "holder": True}),

    # -- allocateMemory failure -------------------------------------------
    ("operator new[] returns NULL -> \"Failed in 'new'.\"",
     {"lut_size": 0x1000, "tone": _ramp(0x1000), "fail_allocation": True}),
    ("allocation failure still leaves the object empty",
     {"lut_size": 0x40, "tone": _ramp(0x40), "preexisting": _ramp(0x40),
      "fail_allocation": True}),

    # -- the eight validateParameters checks, in order --------------------
    ("check 1: sigma == 0", {"params": P(sigma=0.0),
                             "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 1: sigma < 0", {"params": P(sigma=-2.5),
                            "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 1: sigma just above 0 passes",
     {"params": P(sigma=1e-300), "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 1: sigma == NaN is ACCEPTED (jp takes unordered)",
     {"params": P(sigma=float("nan")), "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 2: blockSize == 0", {"params": P(blockSize=0),
                                 "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 2: blockSize < 0", {"params": P(blockSize=-1),
                                "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 3: minAvoidance == 100 passes", {"params": P(minAvoidance=100),
                                             "lut_size": 0x40,
                                             "tone": _ramp(0x40)}),
    ("check 3: minAvoidance == 101", {"params": P(minAvoidance=101),
                                      "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 3: minAvoidance == 255 (unsigned compare)",
     {"params": P(minAvoidance=255), "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 4: maxGradient == -1", {"params": P(maxGradient=-1),
                                    "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 4: maxGradient == 0 passes", {"params": P(maxGradient=0),
                                          "lut_size": 0x40,
                                          "tone": _ramp(0x40)}),
    ("check 5: lowGradientThreshold == -2",
     {"params": P(lowGradientThreshold=-2), "lut_size": 0x40,
      "tone": _ramp(0x40)}),
    ("check 6: highGradientThreshold == -2",
     {"params": P(highGradientThreshold=-2), "lut_size": 0x40,
      "tone": _ramp(0x40)}),
    ("check 7: low=5 high=-1 -> low must be < high",
     {"params": P(lowGradientThreshold=5), "lut_size": 0x40,
      "tone": _ramp(0x40)}),
    ("check 7: low=5 high=5", {"params": P(lowGradientThreshold=5,
                                           highGradientThreshold=5),
                               "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 7: low=5 high=6 passes", {"params": P(lowGradientThreshold=5,
                                                  highGradientThreshold=6),
                                      "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 7: low=-1 is exempt from the ordering rule",
     {"params": P(lowGradientThreshold=-1, highGradientThreshold=-1),
      "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("check 8: minValue == maxValue", {"params": P(minValue=7, maxValue=7),
                                       "lut_size": 0x40,
                                       "tone": _ramp(0x40)}),
    ("check 8: minValue > maxValue", {"params": P(minValue=4095, maxValue=0),
                                      "lut_size": 0x40, "tone": _ramp(0x40)}),

    # -- ordering: the FIRST failing check is the one reported ------------
    ("order: sigma and minValue both bad -> sigma wins",
     {"params": P(sigma=0.0, minValue=4095, maxValue=0),
      "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("order: blockSize and minAvoidance both bad -> blockSize wins",
     {"params": P(blockSize=0, minAvoidance=200),
      "lut_size": 0x40, "tone": _ramp(0x40)}),
    ("order: validation runs BEFORE any allocation",
     {"params": P(blockSize=0), "lut_size": 0x40, "tone": _ramp(0x40),
      "fail_allocation": True}),
    ("tone == NULL short-circuits BEFORE validation",
     {"params": P(blockSize=0), "lut_size": 0x40, "tone": None}),
]


def check_defaults(pe: bytes) -> bool:
    """Run the ctor's own default-install block and diff it against the port."""
    emu = Emu(pe)
    obj = emu.alloc(0x60)
    emu.uc.reg_write(UC_X86_REG_EDI, obj)
    try:
        emu.uc.emu_start(CTOR_DEFAULTS_BEGIN, CTOR_DEFAULTS_END,
                         timeout=0, count=200)
    except UcError as exc:                       # pragma: no cover
        print(f"  ctor defaults block faulted: {exc}")
        return False
    got = bytes(emu.uc.mem_read(obj + ct.IMPL_PARAMS, ct.CITRAS_PARAMS_SIZE))
    want = bytes(ct.default_params().pack())
    # The two padding bytes at +0x0b and +0x16..0x17 are never written by the
    # ctor block, so compare field by field rather than blob to blob.
    ok = True
    for off, name, kind, _default in ct.CITRAS_PARAMS_LAYOUT:
        fmt = ct.CITRAS_PARAM_FORMATS[kind]
        g = struct.unpack_from(fmt, got, off)[0]
        w = struct.unpack_from(fmt, want, off)[0]
        good = g == w
        ok = ok and good
        print(f"  +{off:#04x} {name:<24} dll={g!r:<10} port={w!r:<10} "
              f"{'OK' if good else 'FAIL'}")
    return ok


def check_results_layout() -> bool:
    """``impl+0x28``/``+0x2c`` must be the ``AnsCitrasResults`` the shell knows."""
    ok = True
    for field_name, want in (("lutSize", ct.IMPL_LUT_SIZE - ct.IMPL_LUT_SIZE),
                             ("ToneLut", ct.IMPL_TONE_LUT - ct.IMPL_LUT_SIZE)):
        got = at.layout_offset("AnsCitrasResults", field_name)
        good = got == want
        ok = ok and good
        print(f"  AnsCitrasResults.{field_name:<8} shell +{got:#04x}  "
              f"impl+{ct.IMPL_LUT_SIZE + want:#04x}  {'OK' if good else 'FAIL'}")
    size = at.AUTOTONE_WORK_LAYOUT["AnsCitrasResults"]["size"]
    good = size == 8
    ok = ok and good
    print(f"  AnsCitrasResults size    {size:#04x}  {'OK' if good else 'FAIL'}")
    return ok


def main(argv: list[str]) -> int:
    dll = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll.exists():
        print(f"{dll} not found — run "
              f"'python3 tools/re/reachability.py extract' first")
        return 2
    pe = dll.read_bytes()
    bad = 0

    print("== AnsCitrasParams defaults: the ctor's own copy block "
          f"({CTOR_DEFAULTS_BEGIN:#x}..{CTOR_DEFAULTS_END:#x}) executed ==")
    bad += not check_defaults(pe)
    print()

    print("== AnsCitrasResults == impl+0x28, as pakon_autotone already "
          "records it ==")
    bad += not check_results_layout()
    print()

    print("== host pakon_citras vs DLL 0x10223a20 ==")
    for label, kw in CASES:
        r = Run(pe, **kw)
        try:
            d = r.run()
        except RuntimeError as exc:
            bad += 1
            print(f"  {label:<58} EMU FAIL {exc}")
            continue
        h = host_run(r)
        problems = []
        if d["status"] != h["status"]:
            problems.append(f"status dll={d['status']} host={h['status']}")
        if d["lut_size"] != h["lut_size"]:
            problems.append(
                f"lutSize dll={d['lut_size']} host={h['lut_size']}")
        if d["lut_null"] != h["lut_null"]:
            problems.append(
                f"ToneLut null dll={d['lut_null']} host={h['lut_null']}")
        if d["lut"] != h["lut"]:
            problems.append(f"LUT bytes differ ({len(d['lut'])} vs "
                            f"{len(h['lut'])})")
        # allocations: the DLL records every requested size including the one
        # that returned NULL; the host only records successful ones, so compare
        # the successful subset plus the failure count separately.
        dll_ok_new = [s for s in d["new_sizes"]
                      if not (r.fail_allocation or s >= 0x00400000)]
        if dll_ok_new != h["new_sizes"]:
            problems.append(f"new[] dll={dll_ok_new} host={h['new_sizes']}")
        want_freed = 1 if r.preexisting is not None else 0
        if len(d["freed"]) != want_freed or h["freed"] != want_freed:
            problems.append(f"delete[] dll={len(d['freed'])} "
                            f"host={h['freed']} want={want_freed}")
        if r.preexisting is not None and d["freed"] and \
                d["freed"][0] != r.old_lut:
            problems.append("delete[] freed the wrong pointer")
        ok = not problems
        bad += not ok
        st = "OK" if d["status"] is None else d["status"]["message"][:34]
        print(f"  {label:<58} lutSize={d['lut_size']:<6} {st:<36} "
              f"{'OK' if ok else 'FAIL ' + '; '.join(problems)}")
    print()

    # ---- the exact literals every failure status carries -----------------
    print("== status literals, straight out of the image ==")
    seen = {}
    for label, kw in CASES:
        r = Run(pe, **kw)
        d = r.run()
        if d["status"]:
            seen[d["status"]["message"]] = d["status"]
    for _pred, va, msg in ct.CITRAS_PARAM_CHECKS:
        rec = seen.get(msg)
        ok = (rec is not None
              and rec["code"] == ct.VALIDATE_ERROR_CODE
              and rec["func"] == ct.FUNC_ANALYZE
              and rec["file"] == ct.SRC_FILE
              and rec["line"] == ct.ANALYZE_VALIDATE_LINE)
        bad += not ok
        print(f"  {va:#010x} {msg:<68} {'OK' if ok else 'FAIL ' + str(rec)}")
    rec = seen.get("Failed in 'new'.")
    ok = (rec is not None and rec["code"] == ct.ALLOCATE_ERROR_CODE
          and rec["func"] == ct.FUNC_ALLOCATE_MEMORY
          and rec["file"] == ct.SRC_FILE
          and rec["line"] == ct.ALLOCATE_MEMORY_FAIL_LINE)
    bad += not ok
    print(f"  0x10576a24 {chr(34)}Failed in 'new'.{chr(34)}"
          f"{'':<52}{'OK' if ok else 'FAIL ' + str(rec)}")
    print()

    if bad:
        print(f"FAILED {bad} check(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
