#!/usr/bin/env python3
r"""Golden ``citras``-apply scaffolding (Phase 3a) vs PakonIMAu.dll.

Two independent things are checked here, both against the real DLL under
Unicorn, matching ``pakon_citras_apply.py``'s two ``True`` flags:

1. ``check_vtable_layout`` -- reads the class chain's COL/vtable dwords
   straight out of the loaded image (no execution needed -- it is data, not
   code) and confirms every address ``CITRAS_APPLY_VTABLE_CHAIN``/
   ``CITRAS_APPLY_SLOTS`` claims is real: each vtable slot's dword, and each
   COL's ``pTypeDescriptor -> name string`` walk resolving to the expected
   mangled class name. Also confirms the ``_purecall`` claim for all FOUR
   slots ``ImaI16CitrasOp`` overrides that ``ImaCitrasOpBase`` leaves pure
   (``0x18``/``0x38``/``0x3c``/``0x40`` -- an early draft of this check
   wrongly expected ``0x40`` to fall past the base table's end; the base
   table is 17 slots, same as the derived one, and this check is what caught
   that mistake against the real image).

2. ``check_set_tone_lut`` -- executes the real ``0x10181ee0`` bytes under
   Unicorn against ``pakon_citras_apply.apply_set_tone_lut``, case for case:
   the object's ``lutSize``/``ToneLut`` state, the copied bytes, which
   allocations/frees actually happened (proving the "no realloc when lutSize
   is unchanged" claim, not just asserting it), and the exact
   ``(code, func, message, file, line)`` of both error statuses.

FPCW
====
``setToneLut``'s disassembly (0x10181ee0..0x10182135) contains no x87
instruction at all -- every operation is integer/pointer (compare, add,
``rep movsd``/``movsb``, calls). There is therefore no FPCW-sensitivity claim
to make or disprove for this function, unlike every arithmetic subsystem
ported so far on this project. Stated plainly rather than run through a
negative control that has nothing to find, per this project's own precedent
of documenting a "does not apply" case honestly instead of performing a
pro-forma check (see ``pakon_dra``'s ``keep_midpt_lut`` note for the same
norm applied to a case that DID have FPU code but no measurable divergence).

WHAT IS STUBBED (and why none of it is vendor arithmetic)
===========================================================
Identical to ``pakon_citras_golden.py``'s own stub list, because
``setToneLut`` calls the exact same shared helpers:

* ``operator new[]`` (``0x104ffd78``, a bare ``jmp`` onto ``operator new``,
  NOT hooked by the shared ``Emu`` base class) -- a bump allocator that
  records every requested size and can be told to return NULL.
* ``operator delete[]`` (``0x104ffe3e``) -- ``Emu.__init__`` already installs
  a returning stub at this exact address (it is a bare ``jmp dword
  [IAT slot]`` onto an unbound import). A SECOND intercepting hook at the
  same address is not additive -- both callbacks would fire in sequence and
  the second one double-pops the stack, exactly the "duplicate CRT hook"
  gotcha ``docs/67`` warns about (caught here for real: an earlier draft of
  this file added its own hook at ``0x104ffe3e`` and it read the freed
  buffer's own address back as a return address, jumping into heap data as
  code). The fix, matching ``pakon_citras_golden.py``'s own
  ``DELETE_ARRAY_CALL_SITE`` pattern: a read-only, non-intercepting watch at
  the **call site** (``0x10181f3a``, before the ``call`` pushes a return
  address) observes the freed pointer, and the base class's single existing
  hook does the actual redirect back to the caller.
* ``0x1001ed90`` -- the ``AnsStatus`` builder; the stub records the six
  arguments verbatim (the entire observable) and returns a refcounted
  sentinel, exactly as ``pakon_citras_golden.py``'s own stub does.
* The ``AnsStatus`` refcount helpers (``0x100065e0``/``0x100012e0``/
  ``0x10001530``/``0x10001580``) are NOT stubbed -- they run for real, the
  same choice ``pakon_citras_golden.py`` makes, because they are plain
  memory operations on a refcounted object seeded with a huge count so no
  release ever reaches zero.

PHASE 3B -- ImaI16CitrasOp::virtual_56 (0x10167bf0)
====================================================
Two checks cover this function, split by how much of it each exercises:

``check_tone_compose_validate`` runs the real ``0x10167bf0`` under Unicorn
against ``pakon_citras_apply.tone_compose_validate``, exercising ONLY the
null/type/dims/band-count VALIDATION PREFIX (0x10167bf0..0x10167d38) --
every case here returns before the function would begin its per-pixel
compute. What gets stubbed here, and why it was provably safe for this
NARROWER scope even before the per-pixel compute was resolved:

* ``fcn.10092880``/``fcn.100928b0`` (``0x10092880``/``0x100928b0``) -- two
  accessor calls the validation prefix itself makes (once both type checks
  pass, to prime two locals used ONLY by the per-pixel compute past this
  prefix) -- are hooked to return a fixed non-null dummy value, with a
  counter so the harness can assert they get called exactly twice each
  (once for `term`, once for `base`) whenever both type checks pass, and
  zero times otherwise. Their return values are read nowhere before any of
  the four return codes this prefix produces -- confirmed by tracing every
  read of those two stack slots forward through the whole function -- so
  stubbing them here cannot affect anything THIS check verifies. (What they
  actually return is now fully resolved -- see ``check_tone_compose_full``
  below and ``CITRAS_APPLY_TONE_COMPOSE_PORTED``'s comment in
  ``pakon_citras_apply.py``: plain unsigned element-stride integers via the
  operand's own ``count()`` accessor, not "locked resource handles" as an
  earlier pass speculated.)
* Nothing else is stubbed. ``fcn.1014f470`` (the type-descriptor check) and
  ``fcn.100012e0`` (the refcount decrement every exit path uses to release
  all three operand pointers) run for REAL, unstubbed, against real operand
  memory this file constructs -- both are fully understood, self-contained,
  and citras-adjacent-but-generic in the same way ``validate()``'s own
  already-documented use of ``fcn.1014f470`` is.

Operand mock (this check only): a minimal object exposing only the fields
this prefix reads (``+0x38`` width, ``+0x3c`` height, ``+0x40`` -> a small
accessor sub-object with ``+0x18`` band count and ``+0x20``/``+0x24`` the
(typeInfo*, sampleSize) type-descriptor pair) plus the refcount-release
plumbing every exit path needs. Every case here stops BEFORE the per-pixel
compute would begin -- none of the six checks are ALL made to pass
simultaneously, since a full pass-through is exactly what
``check_tone_compose_full`` below covers instead, with a complete operand
mock.

``check_tone_compose_full`` (THIS PASS) runs the real ``0x10167bf0`` under
Unicorn against ``pakon_citras_apply.apply_tone_compose``, all the way
through the per-pixel compute on the SUCCESS path. Resolved via LIVE
Unicorn tracing (constructed real operand objects with REAL, executing
vtable stub code for ``getOffset``/``getPtr``/``count`` -- i.e.
``fcn.10092880``/``fcn.100928b0``/``fcn.10092840`` run for real, unstubbed,
against these objects; only the generic LEAF accessor calls they make are
stubbed, same scoping as ``AvoidanceRun`` already uses for ``virtual_60``'s
identical protocol), because static reading alone could not resolve the
accessor protocol or two claims that turned out wrong once traced -- see
``CITRAS_APPLY_TONE_COMPOSE_PORTED``'s comment in ``pakon_citras_apply.py``
for the full derivation, headlined by: it is `term` that gets mutated in
place, not `base` (reversed from the prior recon), and `base`'s band index
is `min(band, base.band_count - 1)` when `base` has fewer than 3 bands
(broadcast, not skip). Both are Unicorn-verified here across seven cases:
plain add with genuine int16 wraparound (both signs), inclusive clamp
boundaries, negative clamp bounds, `base.band_count` in {1, 2, 3}, and a
larger 6x5 grid. `base`'s own buffers are asserted UNCHANGED in every case,
not just `term`'s asserted-correct -- proving the read-only/mutated
direction, not just the arithmetic.

The small-vs-large 65536-entry-LUT clamp strategy the real DLL sometimes
takes internally is NOT separately exercised here (nor modelled by the
port) -- both strategies were confirmed, by direct disassembly reading of
the LUT-fill algorithm, to compute the identical saturating clamp, so the
port always uses the direct formula and this harness's cases exercise
exactly that.

PHASE 3C -- ImaI16CitrasOp::virtual_60 (0x10168360)
====================================================
``check_avoidance_blend`` runs the real ``0x10168360`` under Unicorn against
``pakon_citras_apply.apply_avoidance_blend``. Unlike ``setToneLut``, this
function's own body IS the vendor arithmetic under test -- what gets stubbed
here is exclusively the GENERIC multi-operand accessor protocol underneath
it (four independently-vtable-dispatched operand objects, per the module
docstring's object-layout section), not the math:

* Each operand's own vtable slot ``+0x18`` ("get row-0 pointer offset
  term") is stubbed to always return 0, and its ``+0x40`` sub-object's
  ``+0x24`` ("get row-0 pointer") is stubbed to return the address of a
  Python-constructed buffer this test also holds a live Python-side handle
  to -- so "rowbase = getPtr() + getOffset()" always resolves to exactly
  that buffer's own address, with no real generic-accessor code executed.
* Each sub-object's ``+0x28`` ("count") is stubbed to return a configured
  per-test COLUMN or ROW element stride depending on which two literal
  args (``(1,0)`` vs ``(0,1)``) the real DLL code passes -- confirmed by
  live ESP-corrected disassembly to be the ONLY two argument pairs this
  function ever uses, see ``pakon_citras_apply.py``'s
  ``CITRAS_APPLY_AVOIDANCE_BLEND_PORTED`` comment. Each sub-object's own
  ``extent.h`` field is fixed at 1 so the DLL's own ``div`` (unsigned,
  by the extent height) is a no-op, letting this test's stub directly
  control the resulting stride without needing genuine extent semantics.
* ``AVOIDANCE_BLEND_TABLE_LOOKUP`` (``0x104ffdd6``) is stubbed as an
  identity accessor (returns its own first argument, ``this->0x108``) --
  confirmed correct because the real function re-reads the SAME
  ``this->0x108`` fields directly afterward, not through the returned
  pointer alone (see the flag's own comment). This is a DIFFERENT call
  shape at the SAME address as ``pakon_autotone_shell_golden.py``'s own
  ``__RTDynamicCast`` stub (5 cdecl args here, vs that file's own use);
  the two are unrelated call sites documented separately, not conflated.
* ``AVOIDANCE_BLEND_REFCOUNT_CHECK`` (``0x100012e0``) is stubbed to always
  report "still referenced" (returns 0), so the trailing conditional
  ``vtable[0]`` Release calls are provably never reached -- matching this
  same file's own ``BIG_REFCOUNT`` precedent for ``setToneLut``, and
  correct here for the same reason: this is COM-style cleanup with zero
  effect on any pixel value, not part of the arithmetic being verified.

Everything else -- the loop bounds, the per-pixel diff/weight/magic-multiply
math, the table bias-subtract-then-restore, the actual memory reads and
writes -- is the REAL ``0x10168360`` bytes executing, not a mock.

FPCW
====
``virtual_60``'s disassembly (``0x10168360``..``0x101687f5``) contains no
x87 instruction at all -- every operation is integer (``imul``/``div``/
``sar``/``shr``/``movsx``/``movzx``). Same finding, and same "genuinely does
not apply" conclusion, as ``setToneLut`` above.

PHASE 3 -- ImaI16CitrasOp::virtual_64 (0x10168800, luminance)
===============================================================
``check_luminance`` runs the real ``0x10168800`` under Unicorn against
``pakon_citras_apply.apply_luminance``. Same accessor-mocking discipline as
``check_avoidance_blend``/``check_tone_compose_full``: each of the two real
operands (`source`, 3-band; `dest`, 1-band -- NOT four nested operands, the
prior recon's guess, corrected this pass) gets a REAL own-vtable (dtor +
getOffset) and REAL ``+0x40`` sub-object vtable (getPtr/count), so the
function's own generic accessor dispatch runs for real, unstubbed; only the
leaf stub callbacks are Python. ``func_0x100012e0`` (the trailing refcount
check on both operands) is stubbed to always report "still referenced",
matching every other citras-apply harness's own precedent.

The case list deliberately includes MISMATCHED source/dest declared
dimensions (dest smaller than source, and dest larger than source) because
that is exactly what proved, under live execution, that the loop bound is
`source`'s own width/height and not `dest`'s -- a real finding this pass
made, not something carried over from the Phase 3a recon (which guessed a
four-operand ABI that turned out wrong). See
``CITRAS_APPLY_LUMINANCE_PORTED``'s comment in ``pakon_citras_apply.py`` for
the full derivation.

FPCW
====
``virtual_64``'s disassembly (``0x10168800``..``0x10168a95``) contains no
x87 instruction at all -- every operation is integer (``mov``/``add``/
``sub``/``imul``/``shr``/``movsx``/``movzx``). Same "genuinely does not
apply" conclusion as every other citras-apply function so far.

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_citras_apply_golden.py [dll]``

The DLL is not in the repo.  Extract it with
``python3 tools/re/reachability.py extract`` (default ``/tmp/pakon_re``).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP

import pakon_citras as ct
import pakon_citras_apply as ca
from pakon_autotone_shell_golden import DEFAULT_DLL, Emu

BIG_REFCOUNT = 0x01000000

#: `push eax /*old buffer*/; call 0x104ffe3e` -- the ONE delete[] call site
#: inside setToneLut. Watched at the call instruction itself (before the
#: `call` pushes a return address), not at the callee's entry: see the
#: module docstring's "duplicate CRT hook" note for why.
SET_TONE_LUT_DELETE_CALL_SITE = 0x10181F3A

# ---------------------------------------------------------------------------
# 1. vtable/COL layout -- data only, no execution needed besides loading
# ---------------------------------------------------------------------------


def _read_cstr_mem(emu: Emu, va: int, limit: int = 64) -> str:
    raw = bytes(emu.uc.mem_read(va, limit))
    return raw.split(b"\x00", 1)[0].decode("latin-1", errors="replace")


def check_vtable_layout(pe: bytes) -> int:
    print("=== class chain COL/vtable layout (data, read from the loaded "
          "image under Unicorn) ===")
    bad = 0
    emu = Emu(pe)

    # -- 1a. each class's COL -> pTypeDescriptor -> name string round-trips
    for name, col, vt, _n, str_va in ca.CITRAS_APPLY_VTABLE_CHAIN:
        # vftable[-4] (i.e. dword at vt-4) must equal the COL address.
        got_col_ptr = emu.r32(vt - 4)
        ok1 = got_col_ptr == col
        bad += not ok1
        print(f"  {name:<28} vtable-4 == COL?  dll={got_col_ptr:#010x} "
              f"want={col:#010x}  {'OK' if ok1 else 'FAIL'}")

        # COL+0xc is pTypeDescriptor; type_info's name field is +8 into it.
        type_desc = emu.r32(col + 0xC)
        name_va = type_desc + 8
        ok2 = name_va == str_va
        bad += not ok2
        rtti = _read_cstr_mem(emu, name_va)
        name_ok = name.split("<")[0] in rtti   # strip the <short> for the T<F> case
        bad += not name_ok
        print(f"    COL+0xc -> typeDesc -> name @ {name_va:#010x} = "
              f"{rtti!r}  contains {name.split('<')[0]!r}: "
              f"{'OK' if name_ok else 'FAIL'} (name VA {'OK' if ok2 else 'FAIL'})")

    # -- 1b. every documented ImaI16CitrasOp slot dword matches the image
    print("  -- ImaI16CitrasOp's own 17 slots --")
    for off, va, _sz, role in ca.CITRAS_APPLY_SLOTS:
        got = emu.r32(ca.IMAI16CITRASOP_VTABLE + off)
        ok = got == va
        bad += not ok
        print(f"    +{off:#04x} dll={got:#010x} want={va:#010x} "
              f"({role:<12}) {'OK' if ok else 'FAIL'}")

    # -- 1c. the four overridden offsets: confirm ImaCitrasOpBase's OWN slot
    #        at each is the documented _purecall thunk (all four are -- an
    #        earlier draft of pakon_citras_apply.py thought 0x40 fell past
    #        the base table's end and was "no such slot"; it doesn't, the
    #        base table is 17 slots too, and this check catching that wrong
    #        claim is why it exists).
    print("  -- ImaCitrasOpBase's slots at the four overridden offsets --")
    for off, want in ca.CITRAS_APPLY_BASE_SLOTS_AT_OVERRIDES.items():
        got = emu.r32(ca.IMACITRASOPBASE_VTABLE + off)
        ok = got == want == ca.PURECALL_THUNK
        bad += not ok
        print(f"    +{off:#04x} dll={got:#010x} want={want:#010x} "
              f"(PURECALL) {'OK' if ok else 'FAIL'}")

    return bad


# ---------------------------------------------------------------------------
# 2. AnsCitrasOperand::setToneLut -- 0x10181ee0
# ---------------------------------------------------------------------------


class Run:
    """One emulated run of the real ``0x10181ee0``."""

    def __init__(self, pe: bytes, *, lut_size: int = 0x1000,
                 tone: list[int] | None = None,
                 preexisting: list[int] | None = None,
                 fail_allocation: bool = False):
        self.emu = Emu(pe)
        e = self.emu
        self.fail_allocation = fail_allocation
        self.new_sizes: list[int] = []
        self.freed: list[int] = []
        self.statuses: list[dict] = []
        self.lut_size = lut_size
        self.tone = tone
        self.preexisting = preexisting

        # AnsCitrasOperand -- setToneLut only ever touches +0x30/+0x34, no
        # vtable dispatch through `this` at all, so no vftable is needed here
        # (unlike CITRAS_ANALYZE's impl object).
        self.op = e.alloc(0x40)
        if preexisting is not None:
            self.old_lut = e.alloc(max(len(preexisting) * 2, 4),
                                   struct.pack(f"<{len(preexisting)}H",
                                               *preexisting))
            e.wu32(self.op + ca.OPERAND_TONE_LUT, self.old_lut)
            e.wi32(self.op + ca.OPERAND_LUT_SIZE, len(preexisting))
        else:
            self.old_lut = 0

        if tone is None:
            self.tone_ptr = 0
        else:
            self.tone_ptr = e.alloc(max(len(tone) * 2, 4),
                                    struct.pack(f"<{len(tone)}H", *tone))

        # A vftable whose slot 0 is a `ret 4` thiscall destructor, for the
        # AnsStatus sentinel objects the stub hands back -- same shape
        # pakon_citras_golden.Run uses, for the same reason (every refcount
        # is seeded BIG_REFCOUNT so no release reaches zero, but a bare `ret`
        # stub would silently unbalance the stack if one somehow did).
        self.dtor = e.stub()
        e.uc.mem_write(self.dtor, b"\xC2\x04\x00")
        self.vftable = e.alloc(0x20)
        e.wu32(self.vftable, self.dtor)

        self._hooks()

    def _hooks(self) -> None:
        e = self.emu

        def op_new_array(emu: Emu, args: int):
            size = emu.r32(args)
            self.new_sizes.append(size)
            if self.fail_allocation or size >= 0x00400000:
                return 0, 0
            return emu.alloc(max(size, 4), b"\xCD" * max(size, 4)), 0
        e.hook(ct.OP_NEW_ARRAY, op_new_array)

        # NOT e.hook(ct.OP_DELETE_ARRAY, ...) -- Emu.__init__ already hooks
        # that exact address; see the module docstring's "duplicate CRT
        # hook" note. A passive watch at the call site instead.
        def watch_delete(uc, address, size, _u):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ptr = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            if ptr:
                self.freed.append(ptr)
        e.uc.hook_add(UC_HOOK_CODE, watch_delete,
                      begin=SET_TONE_LUT_DELETE_CALL_SITE,
                      end=SET_TONE_LUT_DELETE_CALL_SITE)

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
            return sret, 0
        e.hook(ct.MAKE_STATUS, make_status)

    def run(self) -> dict:
        e = self.emu
        sret = e.alloc(0x10)
        e.call(ca.SET_TONE_LUT, [sret, self.lut_size & 0xFFFFFFFF,
                                  self.tone_ptr], ecx=self.op)
        lut_size = e.ri32(self.op + ca.OPERAND_LUT_SIZE)
        lut_ptr = e.r32(self.op + ca.OPERAND_TONE_LUT)
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
    op = ca.CitrasApplyOperand()
    if r.preexisting is not None:
        op.tone_lut = list(r.preexisting)
        op.lut_size = len(r.preexisting)
    op.fail_allocation = r.fail_allocation
    status = ca.apply_set_tone_lut(op, r.lut_size, r.tone)
    return {
        "status": None if status is None else {
            "code": status.code, "func": status.func,
            "message": status.message, "file": status.file,
            "line": status.line},
        "lut_size": op.lut_size,
        "lut_null": op.tone_lut is None,
        "lut": b"" if op.tone_lut is None else
               struct.pack(f"<{len(op.tone_lut)}H", *op.tone_lut),
        "new_sizes": list(op.allocations),
        "freed": op.frees,
    }


def _ramp(n: int) -> list[int]:
    return [(i * 4093 + 0x1234) & 0xFFFF for i in range(n)]


CASES: list[tuple[str, dict]] = [
    ("fresh: 0x1000-entry LUT, no pre-existing buffer",
     {"lut_size": 0x1000, "tone": _ramp(0x1000)}),
    ("lutSize <= 0 leaves the object untouched",
     {"lut_size": 0, "tone": _ramp(4)}),
    ("lutSize negative leaves the object untouched",
     {"lut_size": -5, "tone": _ramp(4)}),
    ("tone == NULL leaves the object untouched",
     {"lut_size": 0x40, "tone": None}),

    # -- realloc only when lutSize actually changes ------------------------
    ("same-size call reuses the buffer -- NO realloc, NO free",
     {"lut_size": 0x40, "tone": _ramp(0x40), "preexisting": _ramp(0x40)}),
    ("different-size call frees the old buffer and reallocates",
     {"lut_size": 0x80, "tone": _ramp(0x80), "preexisting": _ramp(0x40)}),
    ("shrinking also frees+reallocates (size compare is exact, not <=)",
     {"lut_size": 0x10, "tone": _ramp(0x10), "preexisting": _ramp(0x40)}),

    # -- rep movsd / movsb split --------------------------------------------
    ("lutSize 1 (odd -> 2-byte movsb tail)", {"lut_size": 1, "tone": _ramp(4)}),
    ("lutSize 2 (even -> one movsd, no tail)",
     {"lut_size": 2, "tone": _ramp(4)}),
    ("lutSize 3 (odd -> movsd + movsb tail)", {"lut_size": 3, "tone": _ramp(8)}),
    ("lutSize 0x101 (odd, large)", {"lut_size": 0x101, "tone": _ramp(0x101)}),
    ("copy takes lutSize entries, not len(tone)",
     {"lut_size": 0x10, "tone": _ramp(0x400)}),

    # -- allocation failure --------------------------------------------------
    ("operator new[] returns NULL -> \"Failed in 'new ansPixel_t[lutSize]'\"",
     {"lut_size": 0x1000, "tone": _ramp(0x1000), "fail_allocation": True}),
    ("allocation failure still frees the OLD buffer first",
     {"lut_size": 0x80, "tone": _ramp(0x80), "preexisting": _ramp(0x40),
      "fail_allocation": True}),
]


def check_set_tone_lut(pe: bytes) -> int:
    print()
    print("=== host pakon_citras_apply.apply_set_tone_lut vs "
          f"DLL {ca.SET_TONE_LUT:#010x} ===")
    bad = 0
    for label, kw in CASES:
        r = Run(pe, **kw)
        try:
            d = r.run()
        except RuntimeError as exc:
            bad += 1
            print(f"  {label:<62} EMU FAIL {exc}")
            continue
        h = host_run(r)
        problems = []
        if d["status"] != h["status"]:
            problems.append(f"status dll={d['status']} host={h['status']}")
        if d["lut_size"] != h["lut_size"]:
            problems.append(f"lutSize dll={d['lut_size']} host={h['lut_size']}")
        if d["lut_null"] != h["lut_null"]:
            problems.append(f"null dll={d['lut_null']} host={h['lut_null']}")
        if d["lut"] != h["lut"]:
            problems.append(f"LUT bytes differ ({len(d['lut'])} vs "
                            f"{len(h['lut'])})")
        dll_ok_new = [s for s in d["new_sizes"]
                      if not (r.fail_allocation or s >= 0x00400000)]
        if dll_ok_new != h["new_sizes"]:
            problems.append(f"new[] dll={dll_ok_new} host={h['new_sizes']}")
        want_freed = 1 if (r.preexisting is not None
                          and r.lut_size != len(r.preexisting)
                          and (r.lut_size > 0 and r.tone is not None)) else 0
        if len(d["freed"]) != want_freed or h["freed"] != want_freed:
            problems.append(f"delete[] dll={len(d['freed'])} "
                            f"host={h['freed']} want={want_freed}")
        if want_freed and d["freed"] and d["freed"][0] != r.old_lut:
            problems.append("delete[] freed the wrong pointer")
        ok = not problems
        bad += not ok
        st = "OK" if d["status"] is None else d["status"]["message"][:40]
        print(f"  {label:<62} lutSize={d['lut_size']:<6} {st:<42} "
              f"{'OK' if ok else 'FAIL ' + '; '.join(problems)}")
    return bad


# ---------------------------------------------------------------------------
# 2b. ImaI16CitrasOp::virtual_56 -- validation prefix only (Phase 3b)
# ---------------------------------------------------------------------------

#: The adjustment offset this harness chooses for the refcount-release
#: plumbing every virtual_56 exit path needs (see the module docstring):
#: refcountPtr = operand + 4 + *(*(operand+4) + 4), so placing the
#: adjustment value at 0x50 lands the refcount dword at operand+0x54,
#: clear of every other field this harness's mock operand uses (0x00-0x44).
_REFCOUNT_ADJUST = 0x50


def _mk_tone_compose_operand(e: Emu, *, width: int, height: int,
                             band_count: int, type_pair: tuple[int, int],
                             refcount: int = BIG_REFCOUNT) -> int:
    """A minimal operand satisfying only what virtual_56's validation
    PREFIX reads -- see the module docstring's own description of exactly
    which fields those are and why nothing else (in particular, no working
    function table behind +0x40) is needed for this scope."""
    op = e.alloc(0x60)

    q = e.alloc(8)
    e.wu32(q + 4, _REFCOUNT_ADJUST)
    e.wu32(op + 4, q)
    e.wi32(op + 4 + _REFCOUNT_ADJUST, refcount)

    dtor = e.stub()
    e.uc.mem_write(dtor, b"\xC2\x04\x00")   # ret 4 -- (ecx=op, arg1=1)
    vtable = e.alloc(4)
    e.wu32(vtable, dtor)
    e.wu32(op, vtable)

    e.wi32(op + 0x38, width)
    e.wi32(op + 0x3C, height)

    # operand+0x40 -> acc; acc+0x20 is itself a POINTER to the {typeInfo*,
    # sampleSize} pair (0x10167c2e..0x10167c36: `mov eax,[esi+0x40]; mov
    # eax,[eax+0x20]; mov ecx,[eax]; mov edx,[eax+4]` -- a further
    # indirection an earlier draft of this harness missed, caught live: it
    # crashed reading the wrong-type test's sentinel VALUE as if it were a
    # pointer, and every same-type case's type check spuriously failed too).
    acc = e.alloc(0x28)
    e.wi32(acc + 0x18, band_count)
    type_desc = e.alloc(8)
    e.wu32(type_desc, type_pair[0])
    e.wu32(type_desc + 4, type_pair[1])
    e.wu32(acc + 0x20, type_desc)
    e.wu32(op + 0x40, acc)
    return op


#: A wrong-on-both-fields type pair -- guarantees fcn.1014f470 takes its
#: fast "not equal" exit (differing SECOND field) without ever reaching the
#: `type_info::operator==` MSVCR71 import behind the slow path, which this
#: harness does not stub. See the module docstring for why a pair differing
#: in only the second field would NOT be a safe choice here (the first
#: field alone matching would take the fast "equal" exit instead).
_WRONG_TYPE = (0xDEAD0000, 999)


class ToneComposeValidateRun:
    """One emulated run of the real ``0x10167bf0``, validation prefix only."""

    def __init__(self, pe: bytes, *, base: dict | None, term: dict | None):
        self.emu = Emu(pe)
        e = self.emu
        self.calls_10092880 = 0
        self.calls_100928b0 = 0
        self.refcount_checks = 0
        dummy = e.alloc(4)

        def stub_10092880(emu: Emu, _args: int):
            self.calls_10092880 += 1
            return dummy, 0
        def stub_100928b0(emu: Emu, _args: int):
            self.calls_100928b0 += 1
            return dummy, 0
        e.hook(0x10092880, stub_10092880)
        e.hook(0x100928B0, stub_100928b0)

        def watch_refcount(uc, address, size, _u):
            self.refcount_checks += 1
        e.uc.hook_add(UC_HOOK_CODE, watch_refcount,
                      begin=0x100012E0, end=0x100012E0)

        self.base = (_mk_tone_compose_operand(e, **base)
                    if base is not None else 0)
        self.term = (_mk_tone_compose_operand(e, **term)
                    if term is not None else 0)

    def run(self) -> int:
        e = self.emu
        this = e.alloc(4)   # ecx -- confirmed unread by the function body
        ret = e.call(ca.TONE_COMPOSE, [self.base, 0, self.term], ecx=this)
        return ret - 0x100000000 if ret >= 0x80000000 else ret


TONE_COMPOSE_CASES: list[tuple[str, dict, int, int, int]] = [
    # (label, kwargs, want_return, want_10092880_calls, want_100928b0_calls)
    ("term NULL",
     dict(base=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16),
         term=None),
     ca.TONE_COMPOSE_ERR_NULL_OPERAND, 0, 0),
    ("base NULL",
     dict(base=None,
         term=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16)),
     ca.TONE_COMPOSE_ERR_NULL_OPERAND, 0, 0),
    ("both NULL",
     dict(base=None, term=None),
     ca.TONE_COMPOSE_ERR_NULL_OPERAND, 0, 0),

    ("term wrong type -- checked before base, base never even inspected",
     dict(base=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16),
         term=dict(width=64, height=32, band_count=3,
                    type_pair=_WRONG_TYPE)),
     ca.TONE_COMPOSE_ERR_TYPE_MISMATCH, 0, 0),
    ("base wrong type -- term's own check passes first",
     dict(base=dict(width=64, height=32, band_count=3,
                    type_pair=_WRONG_TYPE),
         term=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16)),
     ca.TONE_COMPOSE_ERR_TYPE_MISMATCH, 0, 0),

    ("term width <= 0",
     dict(base=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16),
         term=dict(width=0, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16)),
     ca.TONE_COMPOSE_ERR_SHAPE_MISMATCH, 2, 2),
    ("term height <= 0",
     dict(base=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16),
         term=dict(width=64, height=-1, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16)),
     ca.TONE_COMPOSE_ERR_SHAPE_MISMATCH, 2, 2),
    ("width mismatch",
     dict(base=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16),
         term=dict(width=48, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16)),
     ca.TONE_COMPOSE_ERR_SHAPE_MISMATCH, 2, 2),
    ("height mismatch",
     dict(base=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16),
         term=dict(width=64, height=16, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16)),
     ca.TONE_COMPOSE_ERR_SHAPE_MISMATCH, 2, 2),
    ("term band count != 3 (2 bands)",
     dict(base=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16),
         term=dict(width=64, height=32, band_count=2,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16)),
     ca.TONE_COMPOSE_ERR_SHAPE_MISMATCH, 2, 2),
    ("term band count != 3 (4 bands)",
     dict(base=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16),
         term=dict(width=64, height=32, band_count=4,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16)),
     ca.TONE_COMPOSE_ERR_SHAPE_MISMATCH, 2, 2),
    ("base band count > 3 (base's upper-bound check, distinct from term's "
     "exact-3 check)",
     dict(base=dict(width=64, height=32, band_count=4,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16),
         term=dict(width=64, height=32, band_count=3,
                    type_pair=ca.TONE_COMPOSE_TYPE_I16)),
     ca.TONE_COMPOSE_ERR_SHAPE_MISMATCH, 2, 2),
    # NOTE: deliberately no "base band_count==1/2/3, everything else valid"
    # case here -- that combination passes ALL SIX checks, which would walk
    # the real DLL past this prefix into fcn.10092840's function-table
    # dispatch (operand+0x40->+0 is intentionally left NULL in this mock,
    # since it is irrelevant to every case that IS tested) and crash. That
    # "all six pass" combination IS exercised, host-side only, in
    # pakon_citras_apply.main() -- see the module docstring's last
    # paragraph for why there is no honest way to also run it under
    # Unicorn without the accessor protocol this pass left unresolved. An
    # earlier draft of this list included it and it faulted exactly as
    # predicted (UC_ERR_FETCH_UNMAPPED at a NULL-derived address), which is
    # itself confirmation -- not a bug to fix -- that the boundary this
    # flag draws is the real one.
]


def check_tone_compose_validate(pe: bytes) -> int:
    print()
    print("=== host pakon_citras_apply.tone_compose_validate vs "
          f"DLL {ca.TONE_COMPOSE:#010x} (validation prefix only) ===")
    bad = 0
    for label, kw, want_ret, want_10092880, want_100928b0 in TONE_COMPOSE_CASES:
        r = ToneComposeValidateRun(pe, **kw)
        try:
            dll_ret = r.run()
        except RuntimeError as exc:
            bad += 1
            print(f"  {label:<62} EMU FAIL {exc}")
            continue

        def shape(d):
            return None if d is None else ca.ComposeOperandShape(
                width=d["width"], height=d["height"],
                band_count=d["band_count"],
                is_i16=(d["type_pair"] == ca.TONE_COMPOSE_TYPE_I16))
        host_ret = ca.tone_compose_validate(shape(kw["base"]), shape(kw["term"]))

        problems = []
        if dll_ret != want_ret:
            problems.append(f"dll returned {dll_ret}, expected {want_ret}")
        if host_ret != want_ret:
            problems.append(f"host returned {host_ret}, expected {want_ret}")
        if r.calls_10092880 != want_10092880:
            problems.append(f"fcn.10092880 called {r.calls_10092880}x, "
                            f"expected {want_10092880}x")
        if r.calls_100928b0 != want_100928b0:
            problems.append(f"fcn.100928b0 called {r.calls_100928b0}x, "
                            f"expected {want_100928b0}x")
        ok = not problems
        bad += not ok
        print(f"  {label:<70} dll={dll_ret:<3} host={host_ret:<3} "
              f"{'OK' if ok else 'FAIL ' + '; '.join(problems)}")
    return bad


# ---------------------------------------------------------------------------
# 2c. ImaI16CitrasOp::virtual_56 -- FULL per-pixel compute (Phase 3b, THIS
#     PASS). check_tone_compose_validate above only exercises the validation
#     prefix; this exercises the real 0x10167bf0 bytes all the way through
#     the per-pixel compute, on the SUCCESS path.
# ---------------------------------------------------------------------------
#
# This is what resolved the accessor protocol live (per the task's own
# instruction to use Unicorn execution, not more static reading): each
# operand gets a REAL own-vtable (dtor + getOffset, both real stub code that
# executes) and a REAL +0x40 sub-object vtable (getPtr/count, also real stub
# code that executes) -- so fcn.10092880/fcn.100928b0/fcn.10092840 all run
# for real, unstubbed, against these objects; only the GENERIC leaf accessor
# calls they make (getOffset/getPtr/count) are stubbed, exactly the same
# scoping AvoidanceRun already uses for virtual_60's identical protocol.

#: op's own vtable slots.
PX_OP_VT_DTOR = 0x00
PX_OP_VT_GET_OFFSET = 0x18
#: op's +0x40 sub-object's own vtable slots.
PX_SUB_VT_GET_PTR = 0x24
PX_SUB_VT_COUNT = 0x28


class ToneComposeRun:
    """One emulated run of the real ``0x10167bf0``, exercising the FULL
    function (validation prefix + per-pixel compute) on inputs that pass
    validation.

    ``term_bands``/``base_bands`` are each a list of flat ``list[int]``
    buffers, one per band (planar, per the live-traced finding -- see
    ``CITRAS_APPLY_TONE_COMPOSE_PORTED``'s comment) -- ``len(term_bands)``
    must be 3 (validated), ``len(base_bands)`` may be 1, 2 or 3.
    """

    def __init__(self, pe: bytes, *, width: int, height: int,
                 term_bands: list[list[int]], base_bands: list[list[int]],
                 flag: int, low: int, high: int):
        self.emu = Emu(pe)
        e = self.emu
        self.width, self.height = width, height
        self.get_ptr_calls: list[tuple] = []
        self.count_calls: list[tuple] = []

        def mk_op(bands: list[list[int]], band_count: int) -> tuple[int, list[int]]:
            band_addrs = []
            for data in bands:
                blob = struct.pack(f"<{len(data)}H", *[v & 0xFFFF for v in data])
                band_addrs.append(e.alloc(max(len(blob), 4), blob))

            sub = e.alloc(0x28)

            def get_ptr(emu: Emu, args: int, band_addrs=band_addrs):
                row, col, band = emu.ri32(args), emu.ri32(args + 4), emu.ri32(args + 8)
                self.get_ptr_calls.append((row, col, band))
                return band_addrs[band], 0xC
            def count(emu: Emu, args: int):
                a, b = emu.ri32(args), emu.ri32(args + 4)
                self.count_calls.append((a, b))
                if (a, b) == (1, 0):
                    return 2, 8              # col stride, bytes (1 element)
                if (a, b) == (0, 1):
                    return width * 2, 8      # row stride, bytes
                raise RuntimeError(f"virtual_56 sub.count() unexpected args "
                                  f"({a}, {b})")
            sub_dtor = e.stub(); e.hook(sub_dtor, lambda emu, a: (0, 4))
            get_ptr_stub = e.stub(); e.hook(get_ptr_stub, get_ptr)
            count_stub = e.stub(); e.hook(count_stub, count)
            sub_vt = e.alloc(0x2C)
            e.wu32(sub_vt, sub_dtor)
            e.wu32(sub_vt + PX_SUB_VT_GET_PTR, get_ptr_stub)
            e.wu32(sub_vt + PX_SUB_VT_COUNT, count_stub)
            e.wu32(sub, sub_vt)
            e.wi32(sub + 0x18, band_count)
            type_desc = e.alloc(8)
            e.wu32(type_desc, ca.TONE_COMPOSE_TYPE_I16[0])
            e.wu32(type_desc + 4, ca.TONE_COMPOSE_TYPE_I16[1])
            e.wu32(sub + 0x20, type_desc)

            op = e.alloc(0x44)
            q = e.alloc(8)
            e.wu32(q + 4, _REFCOUNT_ADJUST)
            e.wu32(op + 4, q)
            e.wi32(op + 4 + _REFCOUNT_ADJUST, BIG_REFCOUNT)
            op_dtor = e.stub(); e.hook(op_dtor, lambda emu, a: (0, 4))
            get_offset_stub = e.stub(); e.hook(get_offset_stub, lambda emu, a: (0, 0))
            op_vt = e.alloc(0x1C)
            e.wu32(op_vt, op_dtor)
            e.wu32(op_vt + PX_OP_VT_GET_OFFSET, get_offset_stub)
            e.wu32(op, op_vt)
            e.wi32(op + 0x30, 0)
            e.wi32(op + 0x34, 0)
            e.wi32(op + 0x38, width)
            e.wi32(op + 0x3C, height)
            e.wu32(op + 0x40, sub)
            return op, band_addrs

        self.term_op, self.term_band_addrs = mk_op(term_bands, 3)
        self.base_op, self.base_band_addrs = mk_op(base_bands, len(base_bands))

        self.this_obj = e.alloc(0x200)
        e.wu8(self.this_obj + ca.TONE_COMPOSE_FLAG_OFFSET, flag)
        e.uc.mem_write(self.this_obj + ca.TONE_COMPOSE_LOW_OFFSET,
                       struct.pack("<h", low))
        e.uc.mem_write(self.this_obj + ca.TONE_COMPOSE_HIGH_OFFSET,
                       struct.pack("<h", high))

    def run(self) -> dict:
        e = self.emu
        ret = e.call(ca.TONE_COMPOSE, [self.base_op, 0, self.term_op],
                    ecx=self.this_obj)
        ret_s = ret - 0x100000000 if ret >= 0x80000000 else ret
        n = self.width * self.height
        term_out = [list(struct.unpack(f"<{n}H", e.uc.mem_read(a, n * 2)))
                   for a in self.term_band_addrs]
        base_out = [list(struct.unpack(f"<{n}H", e.uc.mem_read(a, n * 2)))
                   for a in self.base_band_addrs]
        return {"ret": ret_s, "term": term_out, "base": base_out}


def _plane(data: list[int], width: int) -> ca.CitrasI16Plane:
    return ca.CitrasI16Plane(data=list(data), row0=0, col_stride=1,
                             row_stride=width)


def tone_compose_host_run(width: int, height: int, term_bands: list[list[int]],
                          base_bands: list[list[int]], flag: int, low: int,
                          high: int) -> dict:
    term = ca.ComposeOperand(
        width=width, height=height, band_count=len(term_bands),
        bands=[_plane(b, width) for b in term_bands])
    base = ca.ComposeOperand(
        width=width, height=height, band_count=len(base_bands),
        bands=[_plane(b, width) for b in base_bands])
    ret = ca.apply_tone_compose(flag, low, high, base, term)
    return {"ret": ret,
           "term": [p.data for p in term.bands],
           "base": [p.data for p in base.bands]}


def _ramp16b(n: int, start: int = 0, step: int = 37) -> list[int]:
    return [((start + i * step) & 0xFFFF) for i in range(n)]


TONE_COMPOSE_CASES_FULL: list[tuple[str, dict]] = [
    ("no-clamp add, 4x3, all 3 bands present on both sides",
     dict(width=4, height=3, flag=0, low=0, high=0,
          term_bands=[_ramp16b(12, 0, 1), _ramp16b(12, 100, 1), _ramp16b(12, 200, 1)],
          base_bands=[_ramp16b(12, 190, 1), _ramp16b(12, 290, 1), _ramp16b(12, 390, 1)])),

    ("no-clamp add with genuine int16 wraparound, positive and negative",
     dict(width=4, height=1, flag=0, low=0, high=0,
          term_bands=[[30000, (-30000 & 0xFFFF), 100, 0xFFFF],
                     [0] * 4, [0] * 4],
          base_bands=[[30000, (-30000 & 0xFFFF), (-50 & 0xFFFF), 1],
                     [0] * 4, [0] * 4])),

    ("clamp, inclusive boundary -- sums landing exactly on low/high stay "
     "unclamped, one step outside gets clamped",
     dict(width=5, height=1, flag=1, low=50, high=149,
          term_bands=[[100] * 5, [0] * 5, [0] * 5],
          base_bands=[[(-50 & 0xFFFF), (-49 & 0xFFFF), 0, 49, 50],
                     [0] * 5, [0] * 5])),

    ("clamp with negative low bound and negative wraparound sum",
     dict(width=1, height=1, flag=1, low=-30000, high=100,
          term_bands=[[(-20000 & 0xFFFF)], [0], [0]],
          base_bands=[[(-20000 & 0xFFFF)], [0], [0]])),

    ("base.band_count=2 -- term band2 must read base band1 (broadcast last "
     "base band), not skip or zero",
     dict(width=4, height=3, flag=0, low=0, high=0,
          term_bands=[_ramp16b(12, 0, 1), _ramp16b(12, 100, 1), _ramp16b(12, 200, 1)],
          base_bands=[_ramp16b(12, 190, 1), _ramp16b(12, 290, 1)])),

    ("base.band_count=1 -- every term band must read base band0",
     dict(width=4, height=3, flag=0, low=0, high=0,
          term_bands=[_ramp16b(12, 0, 1), _ramp16b(12, 100, 1), _ramp16b(12, 200, 1)],
          base_bands=[_ramp16b(12, 190, 1)])),

    ("larger 6x5 grid, clamped, to exercise the row/col loop nesting beyond "
     "a small hand-picked grid",
     dict(width=6, height=5, flag=1, low=-1000, high=1000,
          term_bands=[_ramp16b(30, -800, 71), _ramp16b(30, 200, -53),
                     _ramp16b(30, -300, 29)],
          base_bands=[_ramp16b(30, 600, -41), _ramp16b(30, -900, 17),
                     _ramp16b(30, 50, 63)])),
]


def check_tone_compose_full(pe: bytes) -> int:
    print()
    print("=== host pakon_citras_apply.apply_tone_compose vs "
          f"DLL {ca.TONE_COMPOSE:#010x} (full function, success path) ===")
    bad = 0
    for label, kw in TONE_COMPOSE_CASES_FULL:
        r = ToneComposeRun(pe, **kw)
        try:
            d = r.run()
        except RuntimeError as exc:
            bad += 1
            print(f"  {label:<70} EMU FAIL {exc}")
            continue
        h = tone_compose_host_run(**kw)
        problems = []
        if d["ret"] != 0 or h["ret"] != 0 or d["ret"] != h["ret"]:
            problems.append(f"ret dll={d['ret']} host={h['ret']} "
                            f"(every TONE_COMPOSE_CASES_FULL case must "
                            f"validate and return 0)")
        if d["term"] != h["term"]:
            problems.append(f"term (mutated operand) differs: "
                            f"dll={d['term']} host={h['term']}")
        if d["base"] != h["base"]:
            problems.append(f"base (should stay READ-ONLY) differs: "
                            f"dll={d['base']} host={h['base']}")
        # Extra invariant check, not just the pixel output: every getPtr()
        # call the real DLL made should have been (row=0, col=0, band) --
        # confirming the "no ROI sub-offset happens inside virtual_56 itself"
        # finding, not just assuming it holds for every case.
        bad_rowcol = [c for c in r.get_ptr_calls if c[0] != 0 or c[1] != 0]
        if bad_rowcol:
            problems.append(f"getPtr() called with nonzero row/col: "
                            f"{bad_rowcol[:4]}")
        bad_count_args = [c for c in r.count_calls if c not in ((1, 0), (0, 1))]
        if bad_count_args:
            problems.append(f"count() called with unexpected args: "
                            f"{bad_count_args[:4]}")
        ok = not problems
        bad += not ok
        print(f"  {label:<70} {'OK' if ok else 'FAIL ' + '; '.join(problems)}")
    return bad


# ---------------------------------------------------------------------------
# 3. ImaI16CitrasOp::virtual_60 -- 0x10168360 (Phase 3c)
# ---------------------------------------------------------------------------

#: own-vtable slot offsets, on s/opA/opB/opC themselves.
OP_VT_DTOR = 0x00
OP_VT_GET_OFFSET = 0x18
#: sub-object (op->0x40) vtable slot offsets.
SUB_VT_GET_PTR = 0x24
SUB_VT_COUNT = 0x28

OP_FIELD_SUB = 0x40      # -> the extent/accessor sub-object
OP_FIELD_COLS = 0x38     # only meaningful on `s` -- inner trip count
OP_FIELD_ROWS = 0x3C     # only meaningful on `s` -- outer trip count
SUB_FIELD_EXTENT = 0x20  # -> {w (unused, dead per the flag's comment), h}


class _Plane:
    """A flat buffer plus (row0, col_stride, row_stride), shared 1:1 between
    the DLL run (as real emulated memory) and the host comparison (as a
    plain Python list) -- exactly the same tuple
    ``pakon_citras_apply.CitrasPlane`` models, so there is nothing to
    translate between the two sides beyond byte packing.
    """

    def __init__(self, e: Emu, data: list[int], row0: int, col_stride: int,
                 row_stride: int, elemsize: int):
        self.data = list(data)
        self.row0 = row0
        self.col_stride = col_stride
        self.row_stride = row_stride
        self.elemsize = elemsize
        if elemsize == 2:
            blob = struct.pack(f"<{len(self.data)}H",
                               *[v & 0xFFFF for v in self.data])
        else:
            blob = bytes(v & 0xFF for v in self.data)
        self.addr = e.alloc(max(len(blob), 4), blob)

    def row0_addr(self) -> int:
        return self.addr + self.row0 * self.elemsize

    def read_back(self, e: Emu) -> list[int]:
        raw = bytes(e.uc.mem_read(self.addr, len(self.data) * self.elemsize))
        if self.elemsize == 2:
            return list(struct.unpack(f"<{len(self.data)}H", raw))
        return list(raw)


class AvoidanceRun:
    """One emulated run of the real ``0x10168360``.

    ``s``/``op_a``/``op_b``/``op_c`` are each ``(data, row0, col_stride,
    row_stride)`` 4-tuples -- ``op_a`` is the byte weight plane (elemsize 1),
    the other three are int16 planes (elemsize 2). ``table`` is the
    ``0x10000``-entry signed-16-bit clamp/tone table (``pakon_citras_apply.
    AVOIDANCE_TABLE_BIAS``-indexed, i.e. entry ``j`` here IS ``table[j]`` in
    both this class and the host port -- no translation needed, see the
    module docstring).
    """

    def __init__(self, pe: bytes, *, rows: int, cols: int, table: list[int],
                 s: tuple, op_a: tuple, op_b: tuple, op_c: tuple):
        self.emu = Emu(pe)
        e = self.emu
        self.rows, self.cols = rows, cols

        # -- the shared table-cache object, this->0x108 -----------------
        assert len(table) == 0x10000
        self.table_data_addr = e.alloc(
            0x10000 * 2, struct.pack("<65536H", *[v & 0xFFFF for v in table]))
        ptr_cell = e.alloc(4)
        e.wu32(ptr_cell, self.table_data_addr)
        table_cache = e.alloc(0x20)
        e.wi32(table_cache + 0xC, 0x10000)          # count
        e.wi32(table_cache + 0x10, -0x8000)          # bias
        e.wu32(table_cache + 0x18, ptr_cell)           # **data
        self.this = e.alloc(0x120)
        e.wu32(self.this + 0x108, table_cache)

        # -- the four operand planes + their fake object/vtable graph ---
        self.planes: dict[str, _Plane] = {}
        self.sub_info: dict[int, dict] = {}   # sub-object addr -> stride info
        self._op_addr: dict[str, int] = {}

        def make_op(name: str, spec: tuple, elemsize: int) -> int:
            data, row0, col_stride, row_stride = spec
            plane = _Plane(e, data, row0, col_stride, row_stride, elemsize)
            self.planes[name] = plane

            sub = e.alloc(0x24)
            e.wu32(sub, self.sub_vtable)
            extent = e.alloc(8)
            e.wi32(extent, 0)          # w -- dead, see the flag's comment
            e.wi32(extent + 4, 1)       # h -- fixed at 1, see module docstring
            e.wu32(sub + SUB_FIELD_EXTENT, extent)
            self.sub_info[sub] = {
                "row0_addr": plane.row0_addr(),
                "col_stride": col_stride,
                "row_stride": row_stride,
            }

            op = e.alloc(0x44)
            e.wu32(op, self.op_vtable)
            e.wu32(op + 4, e.alloc(8))     # dummy, only its address matters
            e.wu32(op + OP_FIELD_SUB, sub)
            self._op_addr[name] = op
            return op

        self._install_vtables()
        self.s_addr = make_op("s", s, 2)
        e.wi32(self.s_addr + OP_FIELD_COLS, cols)
        e.wi32(self.s_addr + OP_FIELD_ROWS, rows)
        self.a_addr = make_op("opA", op_a, 1)
        self.b_addr = make_op("opB", op_b, 2)
        self.c_addr = make_op("opC", op_c, 2)

    def _install_vtables(self) -> None:
        e = self.emu

        def get_offset(emu: Emu, _args: int):
            return 0, 0
        dtor = e.stub()
        e.hook(dtor, lambda emu, args: (0, 4))
        get_offset_stub = e.stub()
        e.hook(get_offset_stub, get_offset)
        self.op_vtable = e.alloc(0x1C)
        e.wu32(self.op_vtable + OP_VT_DTOR, dtor)
        e.wu32(self.op_vtable + OP_VT_GET_OFFSET, get_offset_stub)

        def get_ptr(emu: Emu, _args: int):
            ecx = emu.uc.reg_read(UC_X86_REG_ECX)
            return self.sub_info[ecx]["row0_addr"], 0xC
        def count(emu: Emu, args: int):
            ecx = emu.uc.reg_read(UC_X86_REG_ECX)
            a, b = emu.r32(args), emu.r32(args + 4)
            info = self.sub_info[ecx]
            if (a, b) == (1, 0):
                return info["col_stride"], 8
            if (a, b) == (0, 1):
                return info["row_stride"], 8
            raise RuntimeError(f"virtual_60 count() called with unexpected "
                              f"args ({a}, {b}) -- recon assumed only "
                              "(1,0)/(0,1) occur; see the flag's comment.")
        get_ptr_stub = e.stub()
        e.hook(get_ptr_stub, get_ptr)
        count_stub = e.stub()
        e.hook(count_stub, count)
        self.sub_vtable = e.alloc(0x2C)
        e.wu32(self.sub_vtable + SUB_VT_GET_PTR, get_ptr_stub)
        e.wu32(self.sub_vtable + SUB_VT_COUNT, count_stub)

        e.hook(ca.AVOIDANCE_BLEND_TABLE_LOOKUP,
              lambda emu, args: (emu.r32(args), 0))
        e.hook(ca.AVOIDANCE_BLEND_REFCOUNT_CHECK, lambda emu, args: (0, 0))

    def run(self) -> dict:
        e = self.emu
        e.call(ca.AVOIDANCE_BLEND,
              [self.s_addr, self.a_addr, self.b_addr, self.c_addr],
              ecx=self.this)
        return {
            "table": list(struct.unpack(
                "<65536H", bytes(e.uc.mem_read(self.table_data_addr,
                                              0x10000 * 2)))),
            "opC": self.planes["opC"].read_back(e),
        }


def avoidance_host_run(rows: int, cols: int, table: list[int], s: tuple,
                      op_a: tuple, op_b: tuple, op_c: tuple) -> dict:
    table = list(table)

    def plane(spec, cls):
        data, row0, col_stride, row_stride = spec
        return cls(list(data), row0, col_stride, row_stride)

    ref = plane(s, ca.CitrasI16Plane)
    weight = plane(op_a, ca.CitrasU8Plane)
    value = plane(op_b, ca.CitrasI16Plane)
    out = plane(op_c, ca.CitrasI16Plane)
    ca.apply_avoidance_blend(rows, cols, table, ref, weight, value, out)
    return {"table": table, "opC": out.data}


def _ramp16(n: int, start: int = 0, step: int = 37) -> list[int]:
    return [((start + i * step) & 0xFFFF) for i in range(n)]


def _tone_curve() -> list[int]:
    """A non-trivial (non-identity) 65536-entry table -- a soft-clip curve,
    so a passing comparison can't be an accident of table[i] == i."""
    out = [0] * 0x10000
    for j in range(0x10000):
        i = j - 0x8000            # signed index
        if i < -0x4000:
            v = -0x6000
        elif i > 0x4000:
            v = 0x6000
        else:
            v = (i * 3) // 2       # a gentle boost in the mid-range
        out[j] = v & 0xFFFF
    return out


AVOIDANCE_CASES: list[tuple[str, dict]] = [
    ("weight=0 everywhere -- output should equal table[value] exactly",
     dict(rows=2, cols=3,
          s=(_ramp16(6, 1000), 0, 1, 3), op_a=([0] * 6, 0, 1, 3),
          op_b=(_ramp16(6, -500, 53), 0, 1, 3),
          op_c=([0] * 6, 0, 1, 3))),

    ("weight=100, positive and negative diffs, mixed",
     dict(rows=3, cols=4,
          s=(_ramp16(12, -2000, 111), 0, 1, 4),
          op_a=([100] * 12, 0, 1, 4),
          op_b=(_ramp16(12, 500, -73), 0, 1, 4),
          op_c=([0] * 12, 0, 1, 4))),

    ("weight varies per pixel (0, 37, 100, 255)",
     dict(rows=2, cols=4,
          s=([100, 100, 100, 100, -5000, -5000, -5000, -5000], 0, 1, 4),
          op_a=([0, 37, 100, 255, 0, 37, 100, 255], 0, 1, 4),
          op_b=([200, 200, 200, 200, 5000, 5000, 5000, 5000], 0, 1, 4),
          op_c=([0] * 8, 0, 1, 4))),

    ("non-contiguous strides -- a 3x3 sub-rectangle inside a 5-wide canvas, "
     "each plane at a different row0/stride to prove the addressing (not "
     "just the arithmetic) is faithful",
     dict(rows=3, cols=3,
          s=(_ramp16(20, 10, 17), 6, 1, 5),
          op_a=(list(range(0, 40, 2))[:20], 3, 1, 6),
          op_b=(_ramp16(24, -300, 41), 2, 2, 7),
          op_c=([0] * 25, 1, 1, 5))),

    ("idx wraparound -- large weight * large diff overflows int16",
     dict(rows=1, cols=3,
          s=([0x7ff0, -0x7ff0, 0], 0, 1, 3),
          op_a=([255, 255, 255], 0, 1, 3),
          op_b=([-0x7ff0, 0x7ff0, 0x7fff], 0, 1, 3),
          op_c=([0, 0, 0], 0, 1, 3))),

    ("rows=0 -- main loop skipped entirely, table still bias/restored, "
     "output plane untouched",
     dict(rows=0, cols=4,
          s=(_ramp16(4), 0, 1, 4), op_a=([50] * 4, 0, 1, 4),
          op_b=(_ramp16(4, 9), 0, 1, 4), op_c=([0xDEAD] * 4, 0, 1, 4))),

    ("cols=0 -- same, gated on the other dimension",
     dict(rows=4, cols=0,
          s=(_ramp16(4), 0, 1, 1), op_a=([50] * 4, 0, 1, 1),
          op_b=(_ramp16(4, 9), 0, 1, 1), op_c=([0xBEEF] * 4, 0, 1, 1))),

    ("weight=255 (max byte, not just minAvoidance's <=100 domain) with a "
     "large negative diff -- stresses the magic-multiply divide's negative "
     "branch at its largest magnitude",
     dict(rows=1, cols=2,
          s=([0x7000, -0x7000], 0, 1, 2), op_a=([255, 255], 0, 1, 2),
          op_b=([-0x7000, 0x7000], 0, 1, 2), op_c=([0, 0], 0, 1, 2))),

    ("larger grid (5x9), pseudo-random-looking weight/value/reference to "
     "exercise the row/col loop nesting beyond a small hand-picked grid",
     dict(rows=5, cols=9,
          s=(_ramp16(45, -1500, 271), 0, 1, 9),
          op_a=([(i * 53 + 7) & 0xFF for i in range(45)], 0, 1, 9),
          op_b=(_ramp16(45, 2200, -199), 0, 1, 9),
          op_c=([0] * 45, 0, 1, 9))),
]


def check_avoidance_blend(pe: bytes) -> int:
    print()
    print("=== host pakon_citras_apply.apply_avoidance_blend vs "
          f"DLL {ca.AVOIDANCE_BLEND:#010x} ===")
    bad = 0
    table_src = _tone_curve()
    for label, kw in AVOIDANCE_CASES:
        r = AvoidanceRun(pe, table=list(table_src), **kw)
        try:
            d = r.run()
        except RuntimeError as exc:
            bad += 1
            print(f"  {label:<70} EMU FAIL {exc}")
            continue
        h = avoidance_host_run(table=list(table_src), **kw)
        problems = []
        if d["opC"] != h["opC"]:
            n_diff = sum(1 for x, y in zip(d["opC"], h["opC"]) if x != y)
            problems.append(f"opC differs in {n_diff}/{len(d['opC'])} entries "
                            f"(dll[:8]={d['opC'][:8]} host[:8]={h['opC'][:8]})")
        if d["table"] != h["table"]:
            n_diff = sum(1 for x, y in zip(d["table"], h["table"]) if x != y)
            problems.append(f"table not bit-exact restored: {n_diff} "
                            "entries differ from the host's post-call state")
        ok = not problems
        bad += not ok
        print(f"  {label:<70} {'OK' if ok else 'FAIL ' + '; '.join(problems)}")
    return bad


# ---------------------------------------------------------------------------
# 4. ImaI16CitrasOp::virtual_64 -- 0x10168800 (Phase 3, luminance)
# ---------------------------------------------------------------------------
#
# ``check_luminance`` runs the real ``0x10168800`` under Unicorn against
# ``pakon_citras_apply.apply_luminance``. Same mocking discipline as
# ``check_avoidance_blend``/``check_tone_compose_full``: each operand gets a
# REAL own-vtable (dtor + getOffset) and a REAL ``+0x40`` sub-object vtable
# (getPtr/count), so the function's own generic accessor calls run for real,
# unstubbed, against these objects -- only the LEAF stub callbacks
# (getOffset/getPtr/count themselves) are Python. `func_0x100012e0` (the
# trailing refcount check on both operands) is stubbed to always report
# "still referenced", matching every other citras-apply harness's own
# precedent, so the conditional `vtable[0]` Release call is provably never
# reached.

LUM_OP_VT_DTOR = 0x00
LUM_OP_VT_GET_OFFSET = 0x18
LUM_SUB_VT_GET_PTR = 0x24
LUM_SUB_VT_COUNT = 0x28


class LuminanceRun:
    """One emulated run of the real ``0x10168800``.

    ``source_bands`` is a list of exactly 3 flat ``list[int]`` buffers (R,
    G, B, planar); ``dest_band`` is a single flat buffer (the output). Both
    operands may declare DIFFERENT width/height than what actually gets
    looped -- this class deliberately allows that mismatch, because proving
    the loop bound is `source`'s own dims (not `dest`'s) is exactly what
    this pass's live tracing established; see
    ``CITRAS_APPLY_LUMINANCE_PORTED``'s comment in ``pakon_citras_apply.py``.
    """

    def __init__(self, pe: bytes, *, source_width: int, source_height: int,
                 source_bands: list[list[int]], dest_width: int,
                 dest_height: int, dest_band: list[int]):
        self.emu = Emu(pe)
        e = self.emu
        self.get_ptr_calls: list[tuple] = []
        self.count_calls: list[tuple] = []

        def mk_op(bands: list[list[int]], width: int, height: int) -> tuple[int, list[int]]:
            band_addrs = []
            for data in bands:
                blob = struct.pack(f"<{len(data)}H", *[v & 0xFFFF for v in data])
                band_addrs.append(e.alloc(max(len(blob), 4), blob))

            sub = e.alloc(0x28)

            def get_ptr(emu: Emu, args: int, band_addrs=band_addrs):
                row, col, band = emu.ri32(args), emu.ri32(args + 4), emu.ri32(args + 8)
                self.get_ptr_calls.append((row, col, band))
                return band_addrs[band], 0xC
            def count(emu: Emu, args: int, width=width):
                a, b = emu.ri32(args), emu.ri32(args + 4)
                self.count_calls.append((a, b))
                if (a, b) == (1, 0):
                    return 2, 8
                if (a, b) == (0, 1):
                    return width * 2, 8
                raise RuntimeError(f"virtual_64 sub.count() unexpected args "
                                  f"({a}, {b})")
            sub_dtor = e.stub(); e.hook(sub_dtor, lambda emu, a: (0, 4))
            get_ptr_stub = e.stub(); e.hook(get_ptr_stub, get_ptr)
            count_stub = e.stub(); e.hook(count_stub, count)
            sub_vt = e.alloc(0x2C)
            e.wu32(sub_vt, sub_dtor)
            e.wu32(sub_vt + LUM_SUB_VT_GET_PTR, get_ptr_stub)
            e.wu32(sub_vt + LUM_SUB_VT_COUNT, count_stub)
            e.wu32(sub, sub_vt)
            e.wi32(sub + 0x18, len(bands))
            type_desc = e.alloc(8)
            e.wu32(type_desc, ca.TONE_COMPOSE_TYPE_I16[0])
            e.wu32(type_desc + 4, ca.TONE_COMPOSE_TYPE_I16[1])
            e.wu32(sub + 0x20, type_desc)

            op = e.alloc(0x44)
            q = e.alloc(8)
            e.wu32(q + 4, _REFCOUNT_ADJUST)
            e.wu32(op + 4, q)
            e.wi32(op + 4 + _REFCOUNT_ADJUST, BIG_REFCOUNT)
            op_dtor = e.stub(); e.hook(op_dtor, lambda emu, a: (0, 4))
            get_offset_stub = e.stub(); e.hook(get_offset_stub, lambda emu, a: (0, 0))
            op_vt = e.alloc(0x1C)
            e.wu32(op_vt, op_dtor)
            e.wu32(op_vt + LUM_OP_VT_GET_OFFSET, get_offset_stub)
            e.wu32(op, op_vt)
            e.wi32(op + 0x30, 0)
            e.wi32(op + 0x34, 0)
            e.wi32(op + 0x38, width)
            e.wi32(op + 0x3C, height)
            e.wu32(op + 0x40, sub)
            return op, band_addrs

        self.src_op, self.src_band_addrs = mk_op(source_bands, source_width,
                                                  source_height)
        self.dst_op, self.dst_band_addrs = mk_op([dest_band], dest_width,
                                                  dest_height)
        self.dst_len = len(dest_band)

        self.this_obj = e.alloc(0x20)
        this_dtor = e.stub(); e.hook(this_dtor, lambda emu, a: (0, 4))
        this_vt = e.alloc(4)
        e.wu32(this_vt, this_dtor)
        e.wu32(self.this_obj, this_vt)

        e.hook(0x100012E0, lambda emu, a: (0, 0))

    def run(self) -> dict:
        e = self.emu
        e.call(ca.LUMINANCE, [self.src_op, self.dst_op], ecx=self.this_obj)
        dst = list(struct.unpack(f"<{self.dst_len}H",
                                 e.uc.mem_read(self.dst_band_addrs[0],
                                              self.dst_len * 2)))
        return {"dst": dst}


def _plane16(data: list[int], width: int) -> ca.CitrasI16Plane:
    return ca.CitrasI16Plane(data=list(data), row0=0, col_stride=1,
                             row_stride=width)


def luminance_host_run(*, source_width: int, source_height: int,
                       source_bands: list[list[int]], dest_width: int,
                       dest_height: int, dest_band: list[int]) -> dict:
    source = ca.LuminanceOperand(
        width=source_width, height=source_height,
        bands=[_plane16(b, source_width) for b in source_bands])
    dest_plane = _plane16(dest_band, dest_width)
    dest = ca.LuminanceOperand(width=dest_width, height=dest_height,
                               bands=[dest_plane])
    ca.apply_luminance(source, dest)
    return {"dst": dest_plane.data}


def _lum_ramp(n: int, start: int = 0, step: int = 37) -> list[int]:
    return [((start + i * step) & 0xFFFF) for i in range(n)]


LUMINANCE_CASES: list[tuple[str, dict]] = [
    ("plain 4x3 grid, source and dest same declared dims",
     dict(source_width=4, source_height=3,
          source_bands=[_lum_ramp(12, 1000, 1), _lum_ramp(12, 2000, 1),
                       _lum_ramp(12, 3000, 1)],
          dest_width=4, dest_height=3, dest_band=[0xDEAD] * 12)),

    ("1x1 minimal case",
     dict(source_width=1, source_height=1,
          source_bands=[[1000], [2000], [3000]],
          dest_width=1, dest_height=1, dest_band=[0xDEAD])),

    ("negative and boundary pixel values -- exercises the truncating "
     "division's sign correction, not just positive ramps",
     dict(source_width=6, source_height=1,
          source_bands=[[(-30000) & 0xFFFF, (-1) & 0xFFFF, 0, 32000,
                        (-32768) & 0xFFFF, 100],
                       [(-30000) & 0xFFFF, (-1) & 0xFFFF, 0, 32000, 32767,
                        (-100) & 0xFFFF],
                       [(-30000) & 0xFFFF, 2, 0, 32000, 0, 0]],
          dest_width=6, dest_height=1, dest_band=[0xDEAD] * 6)),

    ("source rows=0 -- untouched dest, no fault",
     dict(source_width=4, source_height=0,
          source_bands=[[], [], []],
          dest_width=4, dest_height=1, dest_band=[0xDEAD] * 4)),

    ("source cols=0 -- untouched dest, no fault",
     dict(source_width=0, source_height=4,
          source_bands=[[], [], []],
          dest_width=1, dest_height=4, dest_band=[0xDEAD] * 4)),

    ("dest declared SMALLER than source -- the DLL has no bounds check "
     "against dest's own declared size; extra source pixels overwrite dest "
     "using dest's own stride, proving the loop is source-bounded not "
     "dest-bounded (a real vendor UB pattern, not a port concern, same "
     "family as dra's already-documented out-of-bounds histogram bug) -- "
     "the backing buffer is padded past dest's own declared 2x2=4 so both "
     "the DLL and the host model have somewhere real to write the overlap "
     "into, instead of it landing on unrelated adjacent heap data",
     dict(source_width=4, source_height=3,
          source_bands=[_lum_ramp(12, 1000, 1), _lum_ramp(12, 2000, 1),
                       _lum_ramp(12, 3000, 1)],
          dest_width=2, dest_height=2, dest_band=[0xBEEF] * 8)),

    ("dest declared LARGER than source -- proves the loop stops at "
     "source's dims even though dest's own declared width/height would "
     "allow more: cells beyond source's shape stay the pristine sentinel",
     dict(source_width=2, source_height=2,
          source_bands=[[1000, 1001, 1004, 1005], [2000, 2001, 2004, 2005],
                       [3000, 3001, 3004, 3005]],
          dest_width=4, dest_height=3, dest_band=[0xBEEF] * 12)),
]


def check_luminance(pe: bytes) -> int:
    print()
    print("=== host pakon_citras_apply.apply_luminance vs "
          f"DLL {ca.LUMINANCE:#010x} ===")
    bad = 0
    for label, kw in LUMINANCE_CASES:
        r = LuminanceRun(pe, **kw)
        try:
            d = r.run()
        except RuntimeError as exc:
            bad += 1
            print(f"  {label:<70} EMU FAIL {exc}")
            continue
        h = luminance_host_run(**kw)
        problems = []
        if d["dst"] != h["dst"]:
            n_diff = sum(1 for x, y in zip(d["dst"], h["dst"]) if x != y)
            problems.append(f"dst differs in {n_diff}/{len(d['dst'])} "
                            f"entries (dll={d['dst']} host={h['dst']})")
        bad_rowcol = [c for c in r.get_ptr_calls if c[0] != 0 or c[1] != 0]
        if bad_rowcol:
            problems.append(f"getPtr() called with nonzero row/col: "
                            f"{bad_rowcol[:4]}")
        bad_count_args = [c for c in r.count_calls if c not in ((1, 0), (0, 1))]
        if bad_count_args:
            problems.append(f"count() called with unexpected args: "
                            f"{bad_count_args[:4]}")
        ok = not problems
        bad += not ok
        print(f"  {label:<70} {'OK' if ok else 'FAIL ' + '; '.join(problems)}")
    return bad


# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    dll = Path(argv[1]) if len(argv) > 1 else DEFAULT_DLL
    if not dll.exists():
        print(f"{dll} not found — run "
              f"'python3 tools/re/reachability.py extract' first")
        return 2
    pe = dll.read_bytes()
    bad = 0

    bad += check_vtable_layout(pe)
    bad += check_set_tone_lut(pe)
    bad += check_tone_compose_validate(pe)
    bad += check_tone_compose_full(pe)
    bad += check_avoidance_blend(pe)
    bad += check_luminance(pe)
    print()

    if bad:
        print(f"FAILED {bad} check(s)")
        return 1
    print("ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
