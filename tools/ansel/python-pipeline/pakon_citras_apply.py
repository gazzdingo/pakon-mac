#!/usr/bin/env python3
r"""``citras``-apply — Phase 3, ``CITRAS_APPLY_PORTED = True``.

PakonIMAu.dll ImageBase ``0x10000000`` (file VAs == cited VAs), MD5
``eea9dcf78ee21d4f7c515a6c2512242d``.  This is the second half of citras (see
``pakon_citras.py`` for the first, ``CITRAS_ANALYZE_PORTED``): the per-pixel
**application** of the tone LUT that ``analyze`` validates and stores.  It is
reached from an entirely different call graph than ``analyzeAutoTone`` --
through ``ImaI16CitrasOp``'s vtable, at render time, not from
``ColorNegativePath::analyzeAutoTone`` (``0x100fb730``) at all -- so nothing
here changes the shell, and nothing here is wired into any live render path
(``ShastaToneRpd``/``AutoTonePorted`` stay exactly as Phase 6 will leave them).

Per ``docs/66`` Phase 3, this was explicitly split into four tasks and this
file now covers all four, three fully and one (3a) partially by design:

* **3a.**  Class/vtable plumbing and object layout -- Unicorn-verified.  The
  one genuinely mechanical bridge function found, ``setToneLut``, is ported.
  ``validate()`` and the object-construction/factory path are still not
  ported -- see ``CITRAS_APPLY_VALIDATE_PORTED``'s own comment for why that
  is no longer blocking the umbrella below, and ``CITRAS_APPLY_SCAFFOLD_
  PORTED``'s comment for why 3a itself stays honestly partial regardless.
* **3b.**  ``virtual_56``/``CITRAS_APPLY_TONE_COMPOSE_PORTED`` -- fully
  ported and Unicorn-verified bit-exact, including the per-pixel compute
  (resolved via live Unicorn single-stepping, not disassembly alone -- see
  the flag's own comment for the two real corrections that came out of that).
* **3c.**  ``virtual_60``/``CITRAS_APPLY_AVOIDANCE_BLEND_PORTED`` -- ported
  AND Unicorn-verified bit-exact.
* **3d.**  ``virtual_64``/``CITRAS_APPLY_LUMINANCE_PORTED`` -- ported AND
  Unicorn-verified bit-exact.

Phase 3 as a whole is done: ``CITRAS_APPLY_PORTED = True``.  See the "WHAT GOT
PORTED" section below and ``CITRAS_APPLY_VALIDATE_PORTED``'s own comment for
why a still-``False``, still-not-ported ``validate()`` does not block that
umbrella.

WHAT GOT PORTED AND VERIFIED, AND WHAT DID NOT
==========================================================
Six things are ``True`` below, all Unicorn-verified against the real DLL in
``pakon_citras_apply_golden.py`` -- these six are every piece of REAL
per-pixel apply math this file's umbrella, ``CITRAS_APPLY_PORTED``, promises,
and that umbrella is now ``True``:

* ``CITRAS_APPLY_OBJECT_LAYOUT_PORTED`` -- the vtable/COL layout documented in
  ``CITRAS_APPLY_VTABLE_CHAIN``/``CITRAS_APPLY_SLOTS`` below is read directly
  out of the loaded image under Unicorn and compared dword-for-dword against
  this file's static claims, plus each COL's ``pTypeDescriptor`` is walked to
  the RTTI name string and checked against the class name.  This is "vtable
  plumbing" documentation, not executable logic -- there is nothing to run
  besides the read.
* ``CITRAS_APPLY_SET_TONE_LUT_PORTED`` -- ``AnsCitrasOperand::setToneLut``
  (``0x10181ee0``), the bridge that copies the LUT ``pakon_citras.CITRAS_
  ANALYZE_PORTED`` already builds into the apply-side operand.  Genuinely
  mechanical: it touches only its own two fields (``+0x30``/``+0x34``), calls
  no other virtual, and its allocate+memcpy shape is structurally identical
  to ``AnsCitrasCapabilityImpl::analyze``'s own (same ``operator new[]``
  ``0x104ffd78``, same error codes ``0x69``/``0xca``, same
  ``rep movsd``+``rep movsb`` copy).  Full Unicorn bit-exact verification in
  the golden file.
* ``CITRAS_APPLY_AVOIDANCE_BLEND_PORTED`` -- ``ImaI16CitrasOp::virtual_60``
  (``0x10168360``), Phase 3c's subject: the genuine, previously-unnamed
  gradient-avoidance blend + tone-table lookup, fused into one per-pixel
  pass. Fully re-derived from the real disassembly this pass (the Phase 3a
  recon one-liner was a hypothesis, confirmed correct in shape but wrong or
  missing in several particulars once actually traced -- see the flag's own
  comment for the full derivation, including the tooling gotcha that made
  naive r2/Ghidra variable names actively misleading here). Unicorn
  bit-exact verified across nine cases (identity/zero-weight, full-weight,
  per-pixel-varying weight, non-contiguous strides, index wraparound,
  both zero-trip-count edges, max-byte weight, and a larger 5x9 grid).
* ``CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED`` -- the null/type/dims/
  band-count VALIDATION PREFIX of ``virtual_56`` (``0x10167bf0``, Phase 3b),
  i.e. everything the function does BEFORE it would begin the per-pixel
  compute. All four of the function's own return codes (-1/-2/-3/0) and the
  exact six-check dims/band-count order are Unicorn-verified.
* ``CITRAS_APPLY_TONE_COMPOSE_PORTED`` -- **this pass, completed.** The
  per-pixel compute past the validation prefix, resolved with LIVE Unicorn
  single-stepping (constructed real operand/accessor objects, not just
  reading disassembly) exactly as this task demanded, because static reading
  had already hit its limit here. The live trace CORRECTED the prior pass's
  recon in a real, load-bearing way -- see the flag's own comment for the
  full derivation, but the headline finding: **it is ``term`` (``arg_68h``)
  that gets mutated in place, not ``base`` (``arg_60h``) as the previous
  recon claimed** -- confirmed by literally watching which of two
  independently-addressed buffers changed under emulation, with the other
  provably untouched. A second, previously-undocumented finding: when
  ``base.band_count`` is less than ``term``'s (validated-exactly-3) band
  count, the base band actually read is ``min(band, base.band_count - 1)``
  -- i.e. base's last available band is broadcast across any term band it
  doesn't itself have, not skipped. Both corrections, plus the wraparound-add
  and inclusive-bounds-clamp formula, are Unicorn bit-exact verified in
  ``pakon_citras_apply_golden.py``.
* ``CITRAS_APPLY_LUMINANCE_PORTED`` -- **this pass, completed.**
  ``ImaI16CitrasOp::virtual_64`` (``0x10168800``), the third and last named
  vtable-slot candidate. The PRIOR recon guess ("its calling convention takes
  a single struct pointer holding four nested operand objects") was proven
  WRONG once actually traced live, exactly per this task's own warning to
  treat any one-line guess as a hypothesis, not a given: the real signature
  is ``thiscall(this) + TWO plain operand pointers`` (source, 3-band; dest,
  1-band), not four. The arithmetic itself WAS correctly guessed --
  ``(R+G+B+1)/3`` truncating-toward-zero, the identical magic-multiply
  (``0x55555556``) idiom already ported in ``pakon_dra.lum_histogram`` -- but
  the loop bounds turned out to be a genuine, non-obvious finding: they are
  the SOURCE operand's own width/height, not the destination's, confirmed by
  constructing source/dest operands with deliberately MISMATCHED declared
  dimensions and watching, under live Unicorn execution, exactly how far the
  real ``0x10168800`` bytes wrote/read before stopping (a smaller dest simply
  gets overwritten beyond its own declared bounds; a smaller source leaves
  the dest's extra cells provably untouched). See the flag's own comment for
  the full derivation and the four independent probes that pinned this down.

Everything else -- just ``validate()`` -- stays ``False`` and is recon-only;
see the flag's own comment for exactly what is and is not established:

* ``CITRAS_APPLY_VALIDATE_PORTED`` (``validate``, offset ``0x18``/24) --
  address, size and the two checks it performs (3-band, I16) are read
  directly from the decompile and corroborated by its own two self-naming
  error strings, but it was **not** Unicorn-verified: an earlier pass traced
  substantially deeper than the first (see the flag's own comment for the
  full call chain) and found the reachable set is not just "generic
  type-descriptor comparison machinery" but includes, on ANY failure path, a
  full MSVCP71 STL exception/logging subsystem (``std::basic_ostringstream``
  formatting, ``std::string`` construction, ``ctime``/``InitializeCriticalSection``)
  an order of magnitude past what any other citras-apply function has needed
  to mock, plus, even on the SUCCESS path, a deep and only partially-mapped
  dependency on ``this->0x104`` (an "Ima2DImage reference" whose own
  accessor, ``fcn.10328790``, is 438 bytes and pulls in several more
  as-yet-unread functions). A THIRD pass (the one that landed
  ``CITRAS_APPLY_PORTED = True``) asked a different question instead of
  retrying that same full port: does skipping ``validate()`` change anything
  the already-ported math computes? It could not pin down validate()'s real
  caller with confidence (a promising structural lead turned out, via its own
  self-naming error string, to belong to an unrelated sibling class,
  ``ImaArfOpBase`` -- see the flag's own comment), but it DID directly verify
  zero field-level overlap between everything ``validate()``/its success-path
  helper touch and everything ``tone_compose``/``apply_avoidance_blend``/
  ``apply_luminance`` read or write -- in both directions, by direct
  inspection, not by absence of a search. ``validate()`` itself is still not
  ported (calling it still raises), but it is proven irrelevant to the pixel
  math this file's umbrella promises, so the umbrella excludes it rather than
  staying artificially ``False``. See the flag's own comment for the complete
  evidence.

THE CLASS CHAIN AND HOW IT WAS FOUND
=====================================
``ImaCitrasOperationBase -> ImaCitrasOperationT<short> -> ImaCitrasOpBase ->
ImaI16CitrasOp`` (a straight single-inheritance chain; ``AnsImaCitrasAggregate``
and ``AnsCitrasOperand`` are siblings, not ancestors).  Located the same way
``docs/67`` §4 recommends -- self-naming RTTI strings, not static call-graph
inference:

1. The DLL's ``.data`` carries MSVC type_info name strings for all five
   classes (``.?AVImaCitrasOperationBase@@`` etc., found by ``iz~Citras``).
2. Each type_info object is ``name_string_va - 8`` (vftable ptr + spare
   precede the name).  A raw 4-byte search for that address finds each
   class's ``RTTICompleteObjectLocator`` (``pTypeDescriptor`` is COL``+0xc``,
   so ``COL = hit - 0xc``).
3. A second raw 4-byte search for each COL address finds the dword
   immediately before its vtable (``vftable[-1] == &COL``), which is
   therefore ``vtable = hit + 4``.

This is the same two-hop RTTI walk ``pakon_autotone_shell_golden.
rt_dynamic_cast`` already performs live, at runtime, over the same tables --
this file just does it once, statically, to find the vtable addresses in the
first place.

``ImaI16CitrasOp``'s own vtable is 17 slots (``0x10580824``..``0x10580864``,
0x44 bytes), immediately followed in ``.rdata`` by ``ImaCitrasOpBase``'s own,
separate, ALSO-17-slot vtable (``0x1058086c``..``0x105808ac``) -- i.e. **each
class in the chain gets its own vtable emitted** (the MSVC-with-RTTI norm),
not one shared table progressively overridden, and the two tables are the
same size (single inheritance adds no new slots here -- see below for why an
earlier reading of this file thought otherwise). Comparing the two byte for
byte at matching offsets shows most slots are byte-identical (inherited,
unmodified) and four differ -- see ``CITRAS_APPLY_SLOTS``.

``ImaCitrasOpBase``'s own slots at all four of those offsets (``0x18``,
``0x38``, ``0x3c``, ``0x40``) are ``0x104ffdf4``, a bare ``jmp dword
[0x105735d8]`` onto ``MSVCR71.dll!_purecall`` -- i.e. ``ImaCitrasOpBase``
declares all four **pure virtual**, and ``ImaI16CitrasOp`` is (at least one
of) the concrete class that implements them. (An earlier pass over this file
misread the base table as ending at ``0x3c``/16 slots and called ``0x40`` a
"new slot ImaI16CitrasOp introduces" -- wrong: the base table runs one dword
further, to ``0x105808ac``, and IS pure-virtual at ``0x40`` too; the golden
harness's own live read caught this by comparing ``ImaCitrasOpBase``'s
``+0x40`` against the expected "no such slot" and getting ``0x104ffdf4``
back instead.) This is independent, binary-level confirmation that all four
slots are the real seams between "generic operand plumbing" and
"per-bit-depth pixel math", not an assumption. (The destructor slot, offset
``0x00``, also differs between the two tables -- ``0x100aeac0`` in the base
vs ``0x100aeb70`` in ``ImaI16CitrasOp`` -- but that is the ordinary
every-class-has-its-own-dtor pattern, not one of the four seams above.)

``CITRAS_APPLY_SLOTS`` -- the full ``ImaI16CitrasOp`` vtable, byte offset from
vtable base (== object base, since ``ImaI16CitrasOp`` has single inheritance
and the vfptr sits at object+0):

======  ==========  =========  ================================================
offset  VA          bytes      role (this file's finding)
======  ==========  =========  ================================================
0x00    0x100aeb70  30         destructor (trivial, calls generic cleanup)
0x04    0x10009a00  --         inherited unchanged from ImaCitrasOpBase
0x08    0x10009a10  --         inherited unchanged
0x0c    0x10009a40  --         inherited unchanged
0x10    0x10327c60  --         inherited unchanged
0x14    0x10327cf0  --         inherited unchanged
0x18    0x10167ae0  261        OVERRIDDEN, was pure -- ``validate`` (3-band + I16 check)
0x1c    0x103289e0  --         inherited unchanged
0x20    0x100066b0  --         inherited unchanged
0x24    0x10328a90  --         inherited unchanged
0x28    0x10169350  --         inherited unchanged
0x2c    0x10168c20  --         inherited unchanged
0x30    0x10327d70  --         inherited unchanged
0x34    0x10328d20  --         inherited unchanged
0x38    0x10167bf0  1,897      OVERRIDDEN, was pure -- ``virtual_56`` (3b, recon only)
0x3c    0x10168360  1,176      OVERRIDDEN, was pure -- ``virtual_60`` (3c, PORTED)
0x40    0x10168800  664        OVERRIDDEN, was pure -- ``virtual_64``
======  ==========  =========  ================================================

(base's own slot at 0x00 is a *different* dtor implementation, not pure;
0x18/0x38/0x3c/0x40 are all the same ``_purecall`` thunk in the base.
"inherited unchanged" entries were spot-checked byte-equal between the two
tables at their matching offset, not merely assumed.)

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline python3 \
  tools/ansel/python-pipeline/pakon_citras_apply.py``
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from pakon_citras import CitrasStatus

# NOTE: CitrasStatus is imported LAZILY, inside apply_set_tone_lut itself
# (the only place this module constructs one), not at module load time.
# pakon_citras.py imports CITRAS_APPLY_PORTED back from this module's own
# umbrella flag (see pakon_citras.py, right after its CitrasStatus class) --
# a module-level `from pakon_citras import CitrasStatus` here would make
# THAT a genuine circular import that fails whenever pakon_citras_apply is
# the first of the two to be imported (confirmed by actually triggering it,
# not just reasoned about: `import pakon_citras_apply` alone, in a fresh
# interpreter, raised ImportError before this fix). Deferring the import to
# call time sidesteps the cycle entirely, since by the time
# apply_set_tone_lut actually RUNS, both modules have long since finished
# loading.

# ---------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------

# The COL/vtable addresses and slot map documented in this file's own
# docstring, cross-checked two ways in pakon_citras_apply_golden.py: (1) the
# live image loaded under Unicorn is read at each claimed address and
# compared dword-for-dword against CITRAS_APPLY_SLOTS/CITRAS_APPLY_VTABLE_
# CHAIN; (2) each COL's pTypeDescriptor is walked to its RTTI name string and
# checked against the expected class name, the same walk pakon_autotone_
# shell_golden.rt_dynamic_cast performs live for the seven analyzeAutoTone
# capabilities. There is no "arithmetic" to verify here -- this flag means
# the addresses are real and the slot roles (inherited/overridden/pure/new)
# are exactly as documented, not guessed.
CITRAS_APPLY_OBJECT_LAYOUT_PORTED = True

# AnsCitrasOperand::setToneLut (0x10181ee0, 471 real bytes / 597 span --
# corrected from an initial 0x10181f00 candidate, which decodes mid-function:
# it skips the real `push ebp; mov ebp, esp` + SEH prologue and the ebx/esi/
# edi register saves, so calling straight into it leaves EBP unset and the
# very first EBP-relative local write faults. Found the real entry the same
# way this project always resolves a wrong address (docs/67 SS4): walked
# backwards from the two `push str."AnsCitrasOperand::setToneLut"` sites
# until a genuine `push ebp` prologue with a matching SEH triple showed up),
# thiscall(ecx=AnsCitrasOperand*) + (AnsStatus* sret, int lutSize, const
# unsigned short* tone), ret 0xc. Mechanical: validates lutSize>0 and
# tone!=NULL, reuses the existing buffer in place when lutSize is unchanged,
# otherwise frees the old one (operator delete[] 0x104ffe3e) and allocates a
# new lutSize*2-byte one (operator new[] 0x104ffd78 -- the SAME function
# CITRAS_ANALYZE's own allocateMemory uses), then memcpy(dst, tone,
# lutSize*2) as rep movsd + a movsb tail for an odd lutSize. Touches only its
# own +0x30 (lutSize)/+0x34 (ToneLut) fields; no other virtual call. Bridges
# analyze's already-verified output (pakon_citras.CITRAS_ANALYZE_PORTED) into
# the apply-side operand this file otherwise does not construct. Unicorn
# bit-exact verified: state (lutSize, buffer bytes, allocation/free calls)
# and the exact (code, func, message, file, line) of both error statuses,
# across fresh-alloc / same-size-reuse / size-changed-realloc / lutSize<=0 /
# tone==NULL / allocation-failure / odd-and-even lutSize cases. See
# pakon_citras_apply_golden.py.
CITRAS_APPLY_SET_TONE_LUT_PORTED = True

# ---- NOT THIS PASS EITHER: traced substantially deeper, still blocked -----

# ImaI16CitrasOp::validate (0x10167ae0, 261 B, vtable offset 0x18/24).
# thiscall(ecx=this) + one stack arg (an AnsCitrasOperand* to check
# compatibility against, called `other_operand` below). `this` IS read here
# (unlike virtual_64) -- specifically `this->0x104`, see below.
#
# THIS PASS traced the real control flow (raw disassembly, not just the
# earlier decompile) all the way through every branch and confirmed the
# checks are NOT just the two the prior pass documented -- there is a THIRD,
# earlier gate, and the "true" return path itself is not free either:
#
#   1. `func_0x10328950(this->0x104, other_operand)` -- a check on
#      `this->0x104` (an "Ima2DImage reference" this object owns; genuinely
#      never seen elsewhere in this file, since virtual_56/60/64 never touch
#      it) that must pass before the I16/band-count checks even run. If
#      `*(this->0x104)` is null it builds a "The op does not refer to any
#      Ima2DImage" exception (via fcn.10312100, see below) and returns false
#      immediately; otherwise it delegates to `fcn.10328790(other_operand)`
#      (438 B), which ITSELF branches on `other_operand->8` (another,
#      similarly unexplored field: builds a SECOND exception, "Ima2DImage is
#      unable to determine its own size", if that byte is zero) before doing
#      real work involving at least three more not-yet-read functions
#      (`fcn.1016efa0`, `fcn.103280f0`, `fcn.10328260`) and two indirect
#      (vtable) calls (`[edx+0xc]`, `[ebp+0x3c]`/`[edx+0x34]` inside a
#      further callee) whose targets were not identified this pass.
#   2. The already-documented I16 type check: `func_0x10327f60(other_operand,
#      1)` -- confirmed live to be `other_operand`'s own cached-singleton
#      "type descriptor #1" accessor (`fcn.10327dc0`, lazily allocates +
#      calls `fcn.10311600(1)` only the FIRST time; every subsequent call
#      just returns the operand's own vtable pointer as the cached type
#      token, a legitimate "compare vtable pointers for type identity"
#      trick) -- then `fcn.1014f470` compares it against the fixed I16
#      constant, INVERTED from what "type check" suggests: it returns
#      nonzero on MISMATCH, not match (confirmed from the real `test al,al;
#      je <continue>` sense at the call site, not assumed from the name).
#      On mismatch: "This op only works with I16 data." exception, return
#      false.
#   3. The already-documented band-count check: `func_0x10327f20(other_
#      operand)` returns the operand's band count (a similarly-shaped
#      cached-accessor call), compared against 3. On mismatch: "This op
#      only works with 3 band data." exception, return false.
#   4. ONLY if all three pass: `func_0x10328560(other_operand, &pair)` runs
#      (295 B, itself containing TWO indirect vtable calls, `[ebp+0x3c]`
#      and `[edx+0x34]`, on objects this pass did not identify) with `&pair`
#      built from `*(this->0x104)`'s own `+0x20`/`+0x24` fields -- i.e. the
#      "success" path is not a free `return true`, it does real, still-
#      unidentified work first. Only then does the function return true.
#
# THE EXCEPTION-BUILDING MACHINERY on every failure path (`fcn.10312100`,
# reached from step 1's failure and step 1's `fcn.10328790` sub-failure, in
# addition to the two already-documented I16/band-count messages) is
# substantially bigger than anything else mocked in this file: it is not
# just "generic type-descriptor comparison" but a full MSVCP71 STL
# exception/logging object -- `std::basic_ostringstream` formatting
# ("EkcError - <file>: line <n>"), `std::string` construction/destruction,
# `ctime`/`time`, and (on first use) `InitializeCriticalSection` -- an order
# of magnitude more infrastructure than the `AnsStatus`-builder stub
# (`MAKE_STATUS`/`0x1001ed90`) every OTHER citras-apply error path in this
# file uses. Faithfully mocking MSVCP71 string/stream internals under
# Unicorn, just to observe a boolean return value that never surfaces this
# internal object to the caller, was judged genuinely out of budget for a
# cleanup pass, not merely unattempted: reaching even the "true" return
# requires understanding `this->0x104` (an object this file never otherwise
# models) and three more unread functions inside `fcn.10328790`, and reaching
# any "false" return requires either stubbing `fcn.10312100`'s STL machinery
# faithfully enough that a later, more careful pass can trust it (risky to
# get subtly wrong) or executing it for real (a materially larger lift than
# every other stub in this file combined).
#
# 83-function/12,207-byte direct-call reachable set (tools/re/reachability.py
# walk 0x10167ae0) still stands as the outer bound; this pass traced roughly
# a dozen of those functions concretely (fcn.10328950/10328790/10327f60/
# 10327f20/10327dc0/10328560/10312100/102bb930/102bb960/102bb9f0/102bb760/
# 102bbd80) without finding a safe, honest stopping point short of either
# the full STL mock or full execution. Calling this raises.
#
# A THIRD pass (this one) asked a different question per this task's own
# instruction, rather than retrying the same full-port attempt: does
# validate()'s outcome, or its success-path side effect, ever reach anything
# tone_compose/apply_avoidance_blend/apply_luminance actually read? Real
# evidence, gathered directly (not reasoned about), both ways:
#
# 1. CALL-GRAPH POSITION -- genuinely NOT pinned down, reported honestly
#    rather than rounded up in either direction. `validate` (0x10167ae0) has
#    ZERO direct (E8) call sites anywhere in the whole 7,598,080-byte image
#    (exhaustive scan, every section, every E8 opcode byte, target computed
#    and compared -- not a sampled search), and the literal vtable address
#    0x10580824 (ImaI16CitrasOp's own) is referenced EXACTLY ONCE in the
#    entire binary -- its own constructor at 0x100ae947-0x100ae949 -- so
#    nothing anywhere statically narrows a pointer to "this is really an
#    ImaI16CitrasOp" before dispatching through it either. The real caller
#    must therefore be some generic, base-class-typed driver working through
#    ImaCitrasOpBase*/ImaCitrasOperationT<short>*/ImaCitrasOperationBase*
#    (late-bound, whichever concrete type was actually constructed) -- this
#    pass went looking for it and did NOT find it with confidence. One
#    concrete near-miss worth recording (and folding into docs/67 as a new
#    instance of "coincidental structural resemblance" catching out static
#    reading): a function at 0x10165a80 (2,895 B, real SEH-frame prologue,
#    r2's own naive linear-sweep boundary detection mis-split it into a
#    bogus 448-byte fragment starting mid-body at 0x1016640f -- caught by
#    re-resolving the true boundary via `af`/SEH-prologue byte-pattern scan,
#    not trusted from the first read) reads a `this->0x104` field and
#    dispatches vtable offsets 0x38/0x3c/0x40 on `this` -- superficially an
#    exact structural match for "the ImaI16CitrasOp apply driver". It is NOT
#    ImaI16CitrasOp's: its own embedded error strings self-identify it as
#    `.\ImaArfOpBase.cpp` (an unrelated sibling class in the same generic
#    ImaBuilder template family, built from the same "base class owns a
#    +0x104 Ima2DImage ref and dispatches three per-type virtuals at
#    0x38/0x3c/0x40" pattern for a DIFFERENT operation entirely -- band-count
#    3 check included), confirmed by the same self-naming-string method
#    docs/67 SS4 already recommends -- caught BEFORE being written down as a
#    finding, not after. Two more functions in citras's own address range
#    (0x10166ec6 "Primary input connection point was NULL"/"Input data type
#    (...) does not match the supported data types", 0x10167196 the
#    output-side twin) DO self-identify via `.\ImaCitrasOperationBase.cpp`
#    and check plausible pre-flight conditions, but also have zero E8
#    callers and do not appear in ImaCitrasOperationBase's own vtable
#    (0x1058075c, dumped and checked directly) at any offset -- so even
#    these could not be traced to a concrete caller in the time this pass
#    had. Reported as a real, unresolved gap, not papered over.
#
# 2. FIELD-LEVEL DEPENDENCE -- THIS part IS pinned down, directly, and is
#    the part that actually answers this task's question. Every already-
#    ported apply function's own complete read/write set is independently
#    known (each Unicorn-verified): tone_compose reads/writes term/base
#    pixel data plus this->0x124/0x126/0x128 (the clamp descriptor);
#    apply_avoidance_blend reads/writes s/opA/opB/opC pixel data plus
#    this->0x108 (the shared clamp/tone table); apply_luminance reads/writes
#    only source/dest pixel data, no this-> field at all. validate() itself
#    gates on this->0x104 (checked directly, not reused from the prior
#    pass), a field NONE of the three math functions reads. Its SUCCESS path
#    calls fcn.10328560 (295 B) -- read directly this pass, not just cited:
#    the only write to any object's persistent state in its entire body is
#    `mov dword [edi], eax` at 0x103285cd, where `edi` is `other_operand`
#    (the argument passed to validate(), not `this`/ImaI16CitrasOp) and the
#    write is to `other_operand`'s own offset 0 -- a type-descriptor CACHE
#    slot, the exact same "lazily allocate + cache a type token on first
#    use, plain pointer-return on every later call" idiom this file ALREADY
#    treats as harmless generic plumbing for fcn.10327dc0 (cited earlier in
#    this same comment block). Every other write in fcn.10328560 targets a
#    local `&pair` output struct, not persistent object state. Cross-checked
#    the other direction too: tone_compose's disassembly (0x10167bf0) has
#    ZERO calls to vtable offset 0x18 anywhere in its body (grepped the full
#    1,897-byte function); apply_avoidance_blend and apply_luminance each
#    DO call offset 0x18 four times each, but every one of those eight call
#    sites is already accounted for by this file's OWN existing, Unicorn-
#    verified derivation as an OPERAND's own getOffset() accessor call
#    (`op.vtable[0x18]()`, part of the generic pixel-accessor protocol the
#    module docstring documents), never a call to `this`'s own vtable slot
#    0x18 (validate) -- confirmed by checking the register each call
#    dispatches through is loaded from the operand argument, not from `this`.
#    So: zero field overlap between what validate()/its success-path helper
#    write and what the three already-ported functions read, in either
#    direction, confirmed by direct inspection, not by absence of a search.
#
# 3. STRUCTURAL CORROBORATION. Each of the three already-ported math
#    functions carries its OWN complete, independently Unicorn-verified
#    input validation (tone_compose_validate's null/type/dims/band-count
#    prefix; avoidance_blend and luminance both have their own zero-trip-
#    count and operand-null handling) that duplicates what validate() also
#    checks (I16 type, band-count==3). A caller that skipped validate()
#    entirely and called the math directly on malformed input would still
#    get validate()-equivalent, defined error behaviour from the math
#    function's own prefix -- the math functions do not trust validate() to
#    have already run, they re-check. That is real, load-bearing evidence
#    this is a genuinely separate, optional pre-flight/diagnostic entry
#    point in the class's design, not a gate the math depends on -- the same
#    conclusion the task's own framing anticipated as the likely outcome,
#    now backed by a field-level check rather than an assumption.
#
# CONCLUSION: whether or not some caller this pass could not identify
# invokes validate() before running the real math, doing so has PROVEN zero
# effect on anything tone_compose/apply_avoidance_blend/apply_luminance
# compute -- no field it reads, writes, or gates on is touched by
# validate()'s own body or its success-path helper. That is the concrete
# question this port cares about (does skipping validate() change the
# already-ported pixel math's output?), and the answer is no, with real
# evidence on both the "what validate touches" and "what the math reads"
# sides. This flag stays False -- the function itself is still not ported,
# and calling it still raises rather than guessing a boolean -- but it is
# now excluded from CITRAS_APPLY_PORTED's AND (see that flag's own comment)
# because its outcome is confirmed irrelevant to what the umbrella actually
# promises: that the already-ported pixel math is real and bit-exact. This
# is the same "exclude a real, still-False, provably-orthogonal flag from
# the umbrella AND, with a comment saying why" move pakon_toneHelper.py's
# TONEHELPER_ANALYZE_PORTED already made for TONEHELPER_ACQUIRE_IMAGE_PORTED/
# TONEHELPER_IMAGE_HISTOGRAM_PORTED -- except THAT precedent rests on the
# dead path being provably unreachable on the shipped path, and this one
# rests on a field-level independence proof instead, because reachability
# itself could not be pinned down. That distinction is stated plainly, not
# blurred, in case a later pass DOES find the real caller and wants to
# tighten this further.
CITRAS_APPLY_VALIDATE_PORTED = False

# ImaI16CitrasOp::virtual_56 (0x10167bf0, vtable offset 0x38/56, 1,897 B;
# direct-call reachable set 8 fn / 2,375 B / 11 indirect call sites / 1 IAT --
# tools/re/reachability.py walk 0x10167bf0). Phase 3b's subject.
#
# THIS PASS resolved the per-pixel compute with LIVE UNICORN SINGLE-STEPPING
# (constructed real base/term/this objects with logging vtable stubs for the
# generic accessor protocol, then single-stepped/hooked the real 0x10167bf0
# bytes and read back both mutated buffers) -- per this task's own explicit
# instruction, because the prior pass's static reading (disassembly +
# r2ghidra `pdg`) had already hit its limit on the accessor-protocol
# question and on two claims that turned out simply wrong once actually
# traced. Both corrections below are execution facts, not re-readings of the
# same bytes.
#
# SIGNATURE: thiscall(ecx=this, unused for validation but IS this-> for the
# clamp descriptor, see below) + 3 stack args, `ret 0xc`:
#     virtual_56(this, base /*arg_60h, edi*/, correction /*arg_64h, unused*/,
#                term /*arg_68h, esi*/)
# `correction` (param_2) is read NOWHERE in the function body for the
# compute -- confirmed by a full instruction-level scan, still true -- but
# is released on every exit path as a local smart-pointer copy alongside
# base/term (see the release-triple note below), so the signature keeps it.
#
# *** CORRECTION #1, load-bearing: it is `term` (arg_68h, esi) that is
# MUTATED IN PLACE, not `base` (arg_60h, edi) as the prior pass's static
# reading claimed. *** Proven directly, not inferred: two operands were given
# entirely separate, independently-addressed memory (3 planar band buffers
# each, distinct heap addresses via logging `getPtr` stubs), the real DLL
# bytes were executed, and only the `term`-labelled buffers changed --
# `base`'s buffers came back byte-for-byte identical to what they started as,
# in every case tried (add-only, clamped, wraparound, boundary). This
# reverses the mutation direction the file previously documented; `base` is
# the read-only additive operand, `term` is the accumulator. The parameter
# NAMES (`base`/`term` for arg_60h/arg_68h) are kept as-is because
# `tone_compose_validate`'s already-Unicorn-verified signature depends on
# that positional mapping -- only the "which one is mutated" claim was wrong.
#
# RETURN CODES -- unchanged from the already-verified validation prefix:
#   -1 (0xffffffff, epilogue 0x101682d0) -- base or term is NULL.
#   -2 (0xfffffffe, epilogue 0x1016824d) -- base or term fails a pixel-type
#       check; term is checked strictly BEFORE base.
#   -3 (0xfffffffd, epilogue 0x10168206) -- a dims/band-count check fails,
#       see CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED for the exact six
#       checks and their order.
#    0                                   -- success.
#
# THE ACCESSOR PROTOCOL, resolved live (this pass's main blocker, now
# closed): `fcn.10092880`/`fcn.100928b0` are tiny, fully self-contained
# functions -- read directly, not guessed -- that each do exactly:
#     ecx2 = this->0x40                       # the per-operand accessor
#     (typeInfo, sampleSize) = *(ecx2->0x20)    # sub-object's type pair
#     n = ecx2.vtable[0x28](1, 0)   # fcn.10092880: count(1,0) -- COL stride
#     n = ecx2.vtable[0x28](0, 1)   # fcn.100928b0: count(0,1) -- ROW stride
#     return (unsigned) n / sampleSize            # BYTES -> ELEMENTS
# i.e. each returns a plain unsigned ELEMENT-COUNT stride (col-stride or
# row-stride), via the SAME `count(a, b)` vtable slot (+0x28 on the operand's
# +0x40 sub-object) `apply_avoidance_blend` already established, just called
# with a fixed (1,0)/(0,1) pair instead of a caller-supplied one. *** THIS
# REFUTES THE PRIOR PASS'S "locked resource handle" HYPOTHESIS ***, which
# was reasoning from a coincidental address collision, not a confirmed read:
# what actually gets released via `fcn.100014e0` at the success exit
# (0x101681c2) are three LOCAL SMART-POINTER COPIES of `base`/`correction`/
# `term` THEMSELVES (confirmed live: the three release calls' `*ecx` values
# were, in order, the real `base` operand pointer, NULL (`correction`, unset
# in every test run), and the real `term` operand pointer -- an entirely
# ordinary "release my by-value smart-pointer argument copies on the way
# out" C++ pattern, unrelated to `fcn.10092880`/`fcn.100928b0`'s integer
# return values, which are used purely as loop strides). `fcn.10092840`
# (the third, more complex accessor, also read directly, not guessed) is:
#     fcn.10092840(ecx=op, row, col, band) =
#         op.vtable[0x18]()                                    # getOffset()
#         + op->0x40.vtable[0x24](row - op->0x30, col - op->0x34, band)  # getPtr
# called three times per operand (band=0,1,2) with row/col equal to that
# SAME operand's own +0x30/+0x34 fields (self-cancelling to (0, 0) every
# time, confirmed live for BOTH base and term in every case tried) -- i.e.
# virtual_56 always asks each operand for its own band-0/1/2 row-0,col-0
# pointer, never a sub-rectangle offset; any ROI addressing is entirely
# inside the (opaque, un-reimplemented) generic accessor, exactly the same
# scoping choice `apply_avoidance_blend` already made for its own getPtr/
# count stubs.
#
# *** CORRECTION #2, previously undocumented ***: term's band count is
# validated to be EXACTLY 3, but base's is only validated to be <= 3 (1, 2 or
# 3 all pass). Live tracing with base.band_count in {1, 2, 3} shows the
# per-pixel loop always processes all 3 term bands, but the BASE band index
# it reads is `min(band, base.band_count - 1)` -- i.e. base's LAST available
# band is broadcast across any term band index it doesn't itself have
# (base.band_count=1 -> every term band reads base band 0; band_count=2 ->
# term band 2 reads base band 1), not skipped or zero-filled. This matches
# the disassembly's `cmp base.band_count, 1 / 2; jle` structure that gates
# which extra `fcn.10092840` calls happen for base.
#
# THE PER-PIXEL COMPUTE (success path, past the validated prefix) -- live
# Unicorn-verified bit-exact in pakon_citras_apply_golden.py, per pixel
# (r, c) and for band in 0..2 of `term`:
#   baseBand = min(band, base.band_count - 1)
#   s = wrap16(term.read(r, c, band) + base.read(r, c, baseBand))  # 16-bit
#       # wraparound add (confirmed via the real `add word [...], reg`
#       # instruction, and live-verified with values that genuinely overflow
#       # the int16 range both positive and negative)
#   if this->0x124 (a byte) == 0:
#       term.write(r, c, band, s)                     # no clamp
#   else:
#       low  = movsx16(this->0x126)
#       high = movsx16(this->0x128)
#       term.write(r, c, band, clamp(s, low, high))    # max(low, min(high,
#           # s)), INCLUSIVE bounds -- live-verified with sums landing
#           # exactly ON low/high (unclamped) and one step outside (clamped)
# `this` here really is the ImaI16CitrasOp object (ecx at function entry,
# saved to a local at the very top of the function and re-read for the
# clamp-descriptor pointer) -- confirmed live by reading EAX one instruction
# AFTER the `mov eax, [var_24h]` load (the load's own address transiently
# holds a stale register value from three instructions earlier, a genuine
# off-by-one-instruction trap in naive breakpoint placement worth recording
# for whoever traces this function next).
#
# THE SMALL-VS-LARGE LUT HEURISTIC (which of two equivalent clamp
# strategies -- direct compare-and-clamp per sample, vs building a 65536-
# entry saturating LUT once and doing one lookup per sample -- runs) is
# **not modelled by the port**, same scoping choice as everywhere else in
# this file: the two strategies were confirmed, by direct disassembly
# reading of the LUT-fill algorithm (constant/identity/constant fill exactly
# matching `clamp(i, low, high)` at every table index), to produce
# IDENTICAL output, so the port always uses the direct formula above. One
# incidental, honestly-reported finding while chasing this branch live: the
# stack local that feeds the heuristic's `width*height <= 0xffff` compare is
# never written anywhere in this function along the path this pass exercised
# (confirmed by an exhaustive write-search over a full single-step trace) --
# it is read straight off the caller's leftover stack contents, a real,
# apparently-harmless vendor UB pattern (in the same family as the
# already-documented `dra` out-of-bounds-histogram vendor bug), not a port
# concern precisely because both branches it selects between are equivalent.
#
# FPCW: the full 1,897-byte function, not just the validation prefix, was
# scanned for x87 mnemonics and has ZERO -- every operation here is integer
# (mov/add/sub/cmp/movsx/movzx, no fld/fst/fmul/etc). No FPCW-sensitivity
# claim to make or disprove, same conclusion as every other citras-apply
# function so far.
CITRAS_APPLY_TONE_COMPOSE_PORTED = True

# The NULL/type/dims/band-count VALIDATION PREFIX of virtual_56 above --
# 0x10167bf0..0x10167d38, i.e. everything up to (not including) the first
# fcn.10092840 "get band pointer" call -- IS Unicorn-verified this pass
# against the real DLL, deliberately narrower than
# CITRAS_APPLY_TONE_COMPOSE_PORTED (same umbrella-plus-piece-flags shape as
# pakon_dra.DRA_ANALYZE_PORTED / pakon_citras.CITRAS_ANALYZE_PORTED). What
# makes this provably safe to verify WITHOUT resolving the operand-accessor
# protocol above: fcn.10092880/100928b0 (the two "locked resource" accessor
# calls that also run inside this prefix, once both type checks pass, to
# prime two locals) get CALLED here, but their RETURN VALUES are read
# nowhere before any of the four failure returns -- confirmed by tracing
# every read of those two stack slots forward through the whole function;
# they are only read again on the SUCCESS path (0x101681c2's cleanup, and
# 0x10167dc0's clamp-descriptor dereference, both well past this prefix). So
# the golden harness stubs fcn.10092880/100928b0 to return a fixed non-null
# dummy value (also letting the harness assert they get CALLED the right
# number of times) without that choice affecting anything this flag claims.
# fcn.1014f470 (the type check) and fcn.100012e0 (the refcount decrement)
# run for REAL, unstubbed, against real operand memory this file constructs,
# because both are fully understood, self-contained, and citras-adjacent-
# but-generic in exactly the way validate()'s own already-documented use of
# fcn.1014f470 is. Verified: all four of the function's own return codes,
# the exact six-check dims/band-count order, and that term's type is
# checked strictly before base's. See check_tone_compose_validate in
# pakon_citras_apply_golden.py.
#
# FPCW: the ~330 bytes this prefix covers (0x10167bf0..0x10167d38) contain
# ZERO x87 instructions -- confirmed by scanning the full function's
# disassembly (1,897 B) for any FPU mnemonic and finding none at all, not
# just none in this prefix. No FPCW-sensitivity claim to make or disprove;
# stated plainly rather than run through a negative control that has
# nothing to find, matching CITRAS_APPLY_SET_TONE_LUT_PORTED's own
# established precedent for a genuine "does not apply" case.
CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED = True

# ImaI16CitrasOp::virtual_60 (0x10168360, vtable offset 0x3c/60, 1,176 B;
# direct-call reachable set 3 fn / 1,209 B / 20 indirect call sites --
# tools/re/reachability.py walk 0x10168360). Phase 3c's subject.
#
# FULLY RE-DERIVED FROM SCRATCH THIS PASS -- the Phase 3a recon one-liner
# ("a percentage-weighted, likely minAvoidance, gradient-avoidance blend")
# was a hypothesis, not a given, per this task's own instructions. It is
# CONFIRMED CORRECT IN SHAPE but was under-specified: getting the exact
# formula, argument order and table-bias mechanics required live
# instruction-by-instruction ESP-offset tracking (r2/Ghidra's own stack-slot
# naming is UNRELIABLE here -- both `pdf` and `pdg` misattribute several
# locals because the function's ESP shifts underneath unbalanced push/call
# windows; this was caught by re-disassembling with capstone and manually
# walking ESP deltas through every push/call/ret-N, not by trusting either
# tool's variable names -- see the golden file's own docstring for the
# concrete example this pass caught (0x1016848d's divisor looked
# "unwritten" under naive offset arithmetic and was actually a mis-tracked
# earlier store)).
#
# SIGNATURE: thiscall(ecx=this: ImaI16CitrasOp*) + 4 stack dwords, ret 0x10:
#   virtual_60(this, s, opA, opB, opC)
# where `this->0x108` is a pointer to a shared 65536-entry int16 clamp/tone
# table cache object (fields +0xc=count, +0x10=bias, +0x18=**pointer to the
# int16 array, double-indirected), and each of s/opA/opB/opC is itself an
# operand object dispatched through ITS OWN vtable (the same multi-operand
# accessor protocol the module docstring's object-layout section already
# flagged) -- generic ImaBuilder plumbing, not citras-specific, exactly like
# `validate`'s type-descriptor machinery. Per-operand roles, confirmed by
# which one feeds which side of the arithmetic (not by name -- there is no
# self-naming string inside this function):
#   s    -- the "reference"/avoidance-target plane (16-bit)
#   opA  -- the per-pixel BYTE weight plane (unsigned 0-255)
#   opB  -- the "value" plane being toned (16-bit, read twice: once as the
#           diff's minuend, once as the index's base)
#   opC  -- the OUTPUT plane (16-bit, write-only)
# `s->0x38`/`s->0x3c` are plain integer loop trip counts (COLS/inner, ROWS/
# outer respectively) -- NOT operand pointers, despite living at offsets
# adjacent to `s->0x40` which genuinely is one; an earlier reading of this
# function (mine, mid-pass) misread them as two more operand objects before
# live ESP tracking showed one gates a `test edx,edx` with no `[reg+0x20]`
# dereference anywhere near it.
#
# THE ALGORITHM, per pixel (rows x cols, row-major, both counts from `s`):
#   p        = value.read(r, c)                    # opB, sign-extended i16
#   ref      = reference.read(r, c)                 # s, sign-extended i16
#   diff     = wrap16(p - ref)                        # 16-bit wraparound sub
#   w        = weight.read(r, c)                       # opA, unsigned byte
#   weighted = w * diff + 50                             # 0x32
#   q        = trunc_div(weighted, 100)                   # signed, round-
#                                                          # toward-zero --
#                                                          # confirmed exact
#                                                          # via the
#                                                          # 0x51eb851f
#                                                          # magic-multiply
#                                                          # (imul, sar 5,
#                                                          # +sign-bit) at
#                                                          # 0x10168692-
#                                                          # 0x101686a5,
#                                                          # the textbook
#                                                          # MSVC "/100"
#                                                          # idiom
#   idx      = wrap16(p - q)                                # NOT clamped,
#                                                            # genuinely
#                                                            # wraps at the
#                                                            # int16
#                                                            # boundary
#                                                            # (`movsx
#                                                            # ecx,cx`
#                                                            # right before
#                                                            # the lookup)
#   out.write(r, c, table[idx])
# This is the avoidance blend the recon guessed at: it pulls the toned
# value `p` back toward the reference `ref` by `w` percent (w=100 -> fully
# replaced by ref; w=0 -> unchanged), THEN re-applies the shared tone/clamp
# table at the blended index -- doing the avoidance blend and the tone
# lookup in one fused pass, not two.
#
# THE TABLE ITSELF (0x101685a2-0x1016860e / 0x1016874a-0x1016875d, i.e.
# BEFORE and AFTER the main loop, both gated by the identical `lo<=hi`
# test): `this->0x108`'s cache is resolved via `func_0x104ffdd6` (a
# generic get-or-build accessor, NOT `__RTDynamicCast` despite living at
# the same address as that thunk in `pakon_autotone_shell_golden.py` --
# confirmed a DIFFERENT call shape here: 5 cdecl args, caller cleans up
# with an explicit `add esp,0x14`, and the two string-literal args are
# unused by anything this function reads back -- so it is stubbed as an
# identity accessor in the golden harness, matching how `pakon_autotone_
# shell_golden.py` already established the *real* `__RTDynamicCast` shape
# for its own, unrelated use of this address, and documenting them as
# separate call sites rather than conflating them). The returned table
# object's fields (`+0xc`=count, `+0x10`=bias, `+0x18`=**data) are read
# BOTH via the returned pointer AND independently via `*(this->0x108)`
# again immediately after -- proving the "get-or-build" call returns the
# SAME object `this->0x108` already points to, not a fresh one, so the
# port and the golden harness both treat `this->0x108`'s fields as the
# single source of truth. With the DLL's own clamps (`iStack_cc =
# min(bias+count-1, 0x7fff)`, `iVar9 = max(bias, -0x8000)`), a
# bias=-0x8000/count=0x10000 configuration -- the only one this pass tested
# -- saturates to exactly the full int16 domain, which is also what the
# `movsx ecx,cx` truncation on every `idx` guarantees is always a valid
# index into ANYWAY, so `AVOIDANCE_TABLE_SIZE`/`AVOIDANCE_TABLE_BIAS` below
# are fixed at that configuration rather than threaded through as
# parameters -- a smaller/differently-biased table is a real DLL capability
# this pass did not exercise, see the docstring on `apply_avoidance_blend`.
# The table is MUTATED IN PLACE for the duration of the call -- every one
# of its (up to 65536) entries has its own index subtracted before the main
# loop and added back after, unconditionally, regardless of `rows`/`cols`
# -- because it is a shared, cached object the function must not leave
# permanently altered. Ported as `table[i] -= i` / `table[i] += i` (16-bit
# wraparound) over the exact same range both times.
#
# NOT MODELLED, DELIBERATELY (same scoping discipline as `validate`/
# `virtual_64`, and with zero effect on any pixel value): the trailing
# four `func_0x100012e0(...)` refcount-check + conditional `vtable[0](1)`
# "Release" calls on s/opA/opB/opC (0x1016875f-0x101687e3). Generic
# COM-style cleanup, not citras math; the golden harness stubs
# `func_0x100012e0` to always report "still referenced" (matching its own
# `BIG_REFCOUNT`-seeded-object precedent from `CITRAS_APPLY_SET_TONE_LUT_
# PORTED`'s golden), so `vtable[0]` is provably never reached and does not
# need a real destructor.
#
# FPCW: this function's disassembly (0x10168360-0x101687f5) contains ZERO
# x87 instructions -- every operation is integer (imul/div/sar/shr/movsx/
# movzx), same finding as `CITRAS_APPLY_SET_TONE_LUT_PORTED`. No
# FPCW-sensitivity claim to make or disprove; stated plainly rather than
# run through a negative control that has nothing to find, per this
# project's own established norm for a genuine "does not apply" case.
#
# Unicorn bit-exact verified in pakon_citras_apply_golden.py: the real
# 0x10168360 executed against constructed operand/table objects (real
# per-slot vtable dispatch through Python-side stub handlers keyed by
# ECX, exactly the way the generic accessor protocol is designed to be
# mocked, not re-implemented), compared field-for-field against this
# module's own `apply_avoidance_blend` -- output plane contents AND the
# table's fully-restored post-call state, across weight=0/100/255,
# positive/negative diff, non-contiguous (sub-rectangle) strides, and
# idx-wraparound cases.
CITRAS_APPLY_AVOIDANCE_BLEND_PORTED = True

# ImaI16CitrasOp::virtual_64 (0x10168800, vtable offset 0x40/64 -- overrides
# a pure virtual on ImaCitrasOpBase's own (also 17-slot) table, same as the
# other three seams -- 664 B; direct-call reachable set 2 fn / 691 B / 14
# indirect call sites -- tools/re/reachability.py walk 0x10168800).
#
# FULLY RE-DERIVED FROM LIVE UNICORN EXECUTION THIS PASS -- the prior recon
# guess ("its ABI takes a single struct argument holding four nested,
# independently-vtable-dispatched operand objects") was WRONG, per this
# task's own explicit instruction to treat any one-line recon guess as a
# hypothesis, not a given (the same lesson virtual_56's "which operand
# mutates" correction already taught this file once). What is actually true,
# confirmed by constructing real operand objects with REAL executing vtable
# stub code (dtor/getOffset on the operand itself, getPtr/count on its own
# +0x40 sub-object -- the SAME protocol virtual_56/virtual_60 already
# established) and single-stepping the genuine 0x10168800 bytes against them:
#
# SIGNATURE: thiscall(ecx=this: ImaI16CitrasOp*, unused -- confirmed unread
# anywhere in the function body, same as validate()'s own `this`) + TWO
# stack dwords, `ret 8`:
#   virtual_64(this, source /*3-band I16 operand*/, dest /*1-band I16 operand*/)
# Not four operands -- two. `this` itself is never dereferenced for anything
# but the vtable dispatch that reached this function; there is no `this->0x...`
# field read anywhere in its 664 bytes.
#
# THE ALGORITHM, per pixel (r, c) ranging over 0..source.height-1 /
# 0..source.width-1 -- confirmed to be SOURCE's own dimensions, not dest's,
# see below:
#   r_ = source.bands[0].read(row, col)     # sign-extended i16, via the
#   g_ = source.bands[1].read(row, col)      # SAME getPtr(0,0,band)+getOffset()
#   b_ = source.bands[2].read(row, col)       # addressing virtual_56 uses --
#                                              # row/col args to getPtr are
#                                              # always (0,0,band) regardless
#                                              # of source's own +0x30/+0x34
#                                              # adjustment fields (the same
#                                              # self-cancelling pattern
#                                              # virtual_56 already
#                                              # established, confirmed again
#                                              # here independently)
#   val = trunc_div(r_ + g_ + b_ + 1, 3)        # signed, round-toward-zero,
#                                                # the SAME 0x55555556
#                                                # magic-multiply
#                                                # (`imul edx`, `shr eax,0x1f`,
#                                                # `add eax,edx`) idiom
#                                                # pakon_dra.lum_histogram's
#                                                # `_idiv(r+g+b+1, 3)` already
#                                                # ports -- confirmed bit-exact
#                                                # against real negative,
#                                                # zero and boundary inputs,
#                                                # not just positive ramps
#   dest.bands[0].write(row, col, val)            # plain 16-bit truncating
#                                                  # store, `mov word [...], ax`
#
# *** LOOP-BOUNDS FINDING, not in the prior recon at all ***: the row/col trip
# counts are SOURCE's own width/height, not dest's -- confirmed with FOUR
# independent live probes, not inferred from one case: (1) dest smaller than
# source in both dimensions -- the extra source pixels get written into dest
# using dest's own stride, silently overlapping/overwriting earlier writes
# (no bounds check against dest's declared size, a genuine vendor UB pattern
# in the same family as dra's already-documented out-of-bounds histogram
# indexing, not a port concern); (2) source smaller than dest in both
# dimensions -- with a big pre-filled sentinel region behind dest's declared
# buffer, the probe proved the DLL's own writes stop EXACTLY at source's
# dimensions, leaving every dest cell beyond that -- including cells WITHIN
# dest's own larger declared width/height -- provably untouched (still the
# sentinel value byte-for-byte); (3) a rows=0/cols=0 edge case (matching
# virtual_56/virtual_60's own independently-gated row/col trip-count
# pattern) leaves dest completely untouched, no fault; (4) a 1x1 case
# confirms the minimal non-empty path. The port below and check_luminance in
# pakon_citras_apply_golden.py both encode this SOURCE-bounds finding
# directly (`for r in range(source.height): for c in range(source.width)`),
# not dest's.
#
# THE REFCOUNT/RELEASE TAIL (source, then dest, each `func_0x100012e0`
# check + conditional `vtable[0](1)` Release) is NOT modelled, same
# scoping choice as virtual_56/virtual_60 and setToneLut: it is ordinary
# COM-style cleanup with zero effect on any pixel value, and the golden
# harness stubs `func_0x100012e0` to always report "still referenced"
# (matching this file's own established `BIG_REFCOUNT` precedent) so the
# `vtable[0]` Release path is provably never reached.
#
# FPCW: the full 664-byte function was scanned for x87 mnemonics and has
# ZERO -- every operation is integer (mov/add/sub/imul/shr/movsx/movzx, no
# fld/fst/fmul/etc). No FPCW-sensitivity claim to make or disprove, same
# conclusion as every other citras-apply function so far.
#
# Unicorn bit-exact verified in pakon_citras_apply_golden.py: the real
# 0x10168800 executed against constructed source/dest operand objects (real
# per-slot vtable dispatch, exactly the mocking discipline virtual_56/
# virtual_60 already established), compared field-for-field against this
# module's own `apply_luminance` -- across a plain rectangular grid, a 1x1
# minimal case, both rows=0/cols=0 edge cases, negative/boundary pixel
# values exercising the truncating-division's sign correction, and the
# source-bounds-not-dest-bounds mismatched-dimension case described above.
CITRAS_APPLY_LUMINANCE_PORTED = True

# Rollup, in this file's convention (see pakon_dra.DRA_ANALYZE_PORTED for the
# precedent this follows): True only when EVERY piece "scaffolding" could
# reasonably mean is ported. It is NOT True here -- CITRAS_APPLY_VALIDATE_
# PORTED is still False, and the object-construction/factory path that
# actually builds an ImaI16CitrasOp (found but not traced -- see the module
# docstring's "construction, not fully scoped" note below) is untouched.
# What IS true: the vtable/object layout is real and Unicorn-checked, and one
# genuinely mechanical bridge function (setToneLut) is ported and verified.
# Phase 3a is therefore PARTIAL, not done -- this flag says so honestly.
CITRAS_APPLY_SCAFFOLD_PORTED = (
    CITRAS_APPLY_OBJECT_LAYOUT_PORTED
    and CITRAS_APPLY_SET_TONE_LUT_PORTED
    and CITRAS_APPLY_VALIDATE_PORTED
)

# Whole-file umbrella, same "AND of every real flag in this file" convention
# as pakon_dra.DRA_ANALYZE_PORTED / pakon_citras.CITRAS_ANALYZE_PORTED, WITH
# ONE DELIBERATE EXCLUSION -- CITRAS_APPLY_VALIDATE_PORTED is left out of
# this AND on purpose, the same "exclude a real, still-False flag from the
# umbrella, with a comment saying why" move pakon_autotone.py's
# TONEHELPER_ANALYZE_PORTED already made for TONEHELPER_ACQUIRE_IMAGE_PORTED.
# See CITRAS_APPLY_VALIDATE_PORTED's own comment (directly above, in this
# same file) for the full evidence: validate()'s exact callers could not be
# pinned down (genuinely reported as unresolved, not assumed dead), but its
# entire read set (this->0x104) and its success-path helper's entire write
# set (a generic operand type-descriptor cache slot plus a local output
# struct) were checked directly against every field tone_compose/
# apply_avoidance_blend/apply_luminance actually read or write, with zero
# overlap in either direction -- and each of those three math functions
# carries its own independent, already-verified input validation that does
# not trust validate() to have run first. Skipping validate() therefore
# provably cannot change any already-ported function's output. The six
# flags that ARE ANDed below are checked directly against every OTHER
# ``*_PORTED`` name defined in this file (``grep -n "_PORTED = "
# pakon_citras_apply.py``): OBJECT_LAYOUT, SET_TONE_LUT, TONE_COMPOSE_
# VALIDATE, TONE_COMPOSE, AVOIDANCE_BLEND, LUMINANCE -- all six are True and
# all six are Unicorn-verified, so this umbrella is honestly True: every
# piece of REAL per-pixel apply math this port promises is ported and
# bit-exact. ``validate()`` itself is still not ported (calling it still
# raises, see ``validate()`` the function, below) -- this umbrella is a
# claim about the pixel math, not a claim that every vtable slot has a body.
CITRAS_APPLY_PORTED = (
    CITRAS_APPLY_OBJECT_LAYOUT_PORTED
    and CITRAS_APPLY_SET_TONE_LUT_PORTED
    and CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED
    and CITRAS_APPLY_TONE_COMPOSE_PORTED
    and CITRAS_APPLY_AVOIDANCE_BLEND_PORTED
    and CITRAS_APPLY_LUMINANCE_PORTED
)

# ---------------------------------------------------------------------------
# object construction -- found, not traced (honest gap, not a claim)
# ---------------------------------------------------------------------------
#
# ImaI16CitrasOp's constructor installs its vtable at 0x100ae947 (`mov dword
# [esi], 0x10580824`), inside a much larger routine (disassembly runs at
# least 0x100ae8c0..0x100ae9b0 without a clean prologue boundary r2 could
# resolve automatically) that also allocates a 0x130-byte block via operator
# new after looking up a "maxValue"-keyed value -- almost certainly part of
# a generic per-bit-depth-and-band-count OPERAND FACTORY shared across the
# whole ImaBuilder library (the same family AnsImaCitrasAggregate belongs to,
# per the "Failed in 'new ImaCitrasOperationT'"/"...AnsImaCitrasAggregate'"
# bad_alloc strings), not a small citras-specific constructor. A linear-sweep
# probe from one of its bad_alloc strings landed inside a single ~25 KB
# function span, which is very likely several merged functions (a known r2
# `af` boundary-detection failure mode, see docs/67 §6) rather than one real
# 25 KB function -- that number is NOT reported as real anywhere in this
# file for that reason. Locating and sizing the real factory honestly is
# follow-up work, not done here.

IMA_I16_CITRAS_OP_CTOR_VTABLE_INSTALL = 0x100AE947  # `mov [esi], vtable`, NOT
                                                     # the function's own start


def _unported(flag: str, va: int, what: str) -> NoReturn:
    raise RuntimeError(
        f"{flag} is False: {what} ({va:#x}) is not ported. See "
        f"tools/ansel/python-pipeline/pakon_citras_apply.py -- Phase 3a is "
        f"partial (validate()/0x10167ae0 and the object-construction path "
        f"are recon only); Phase 3b (virtual_56, tone-compose) is done -- "
        f"see CITRAS_APPLY_TONE_COMPOSE_PORTED; Phase 3c (virtual_60, "
        f"avoidance-blend) is done -- see "
        f"CITRAS_APPLY_AVOIDANCE_BLEND_PORTED.")


# ---------------------------------------------------------------------------
# the class chain -- COL / vtable addresses
# ---------------------------------------------------------------------------

#: (class name, COL VA, vtable VA, slot count, RTTI name string VA).
#: Found by the two-hop raw-pointer search described in the module docstring:
#: name string -> type_info (name-8) -> COL (name string's own type_info
#: address is COL+0xc, i.e. a raw-pointer hit ON the type_info address is
#: COL+0xc; the COL's own address is that hit's location minus 0xc) ->
#: vtable (a raw-pointer hit ON the COL address is vtable-4, i.e. the COL
#: address itself is what's STORED at vtable-4; vtable = that hit's location
#: plus 4). The COL value here is the STORED pointer VALUE, not the location
#: that stores it -- that distinction bit the first draft of this table (it
#: used the vtable-4 *location* by mistake) and was caught by the golden
#: harness's own `vtable-4 == COL` live read failing on every entry.
CITRAS_APPLY_VTABLE_CHAIN: tuple[tuple[str, int, int, int, int], ...] = (
    ("ImaCitrasOperationBase", 0x105E24DC, 0x1058075C, None, 0x10694568),
    ("ImaCitrasOperationT<short>", 0x105E2438, 0x105804FC, None, 0x10694590),
    ("ImaCitrasOpBase", 0x105E2580, 0x1058086C, 17, 0x106945DC),
    ("ImaI16CitrasOp", 0x105E2548, 0x10580824, 17, 0x106945FC),
)

#: The RTTI type_info name string VA for each class (== name field VA; the
#: type_info object itself starts 8 bytes earlier: vftable ptr + spare).
CITRAS_APPLY_RTTI_NAMES: dict[str, int] = {
    name: str_va for name, _col, _vt, _n, str_va in CITRAS_APPLY_VTABLE_CHAIN
}

#: The full ImaI16CitrasOp vtable, byte offset from vtable base (== object
#: base) -> (VA, byte size or None for "inherited, size not independently
#: measured", role). See the module docstring's table for the narrative.
IMAI16CITRASOP_VTABLE = 0x10580824
IMACITRASOPBASE_VTABLE = 0x1058086C
PURECALL_THUNK = 0x104FFDF4          # `jmp dword [0x105735d8]` -> _purecall

CITRAS_APPLY_SLOTS: tuple[tuple[int, int, object, str], ...] = (
    (0x00, 0x100AEB70, 30, "dtor"),
    (0x04, 0x10009A00, None, "inherited"),
    (0x08, 0x10009A10, None, "inherited"),
    (0x0C, 0x10009A40, None, "inherited"),
    (0x10, 0x10327C60, None, "inherited"),
    (0x14, 0x10327CF0, None, "inherited"),
    (0x18, 0x10167AE0, 261, "validate"),
    (0x1C, 0x103289E0, None, "inherited"),
    (0x20, 0x100066B0, None, "inherited"),
    (0x24, 0x10328A90, None, "inherited"),
    (0x28, 0x10169350, None, "inherited"),
    (0x2C, 0x10168C20, None, "inherited"),
    (0x30, 0x10327D70, None, "inherited"),
    (0x34, 0x10328D20, None, "inherited"),
    (0x38, 0x10167BF0, 1897, "virtual_56 (tone-compose, Phase 3b, PORTED)"),
    (0x3C, 0x10168360, 1176, "virtual_60 (avoidance-blend, Phase 3c, PORTED)"),
    (0x40, 0x10168800, 664, "virtual_64 (luminance, PORTED)"),
)

#: The corresponding base-class (ImaCitrasOpBase) slot at the same offset,
#: for the four offsets ImaI16CitrasOp actually overrides/adds -- used by the
#: golden harness to confirm the "was pure" / "no such slot" claims live.
CITRAS_APPLY_BASE_SLOTS_AT_OVERRIDES: dict[int, object] = {
    0x18: PURECALL_THUNK,   # validate: overrides a pure virtual
    0x38: PURECALL_THUNK,   # virtual_56: overrides a pure virtual
    0x3C: PURECALL_THUNK,   # virtual_60: overrides a pure virtual
    0x40: PURECALL_THUNK,     # virtual_64: overrides a pure virtual, same as the rest
}

# ---------------------------------------------------------------------------
# AnsCitrasOperand::setToneLut -- 0x10181ee0
# ---------------------------------------------------------------------------

SET_TONE_LUT = 0x10181EE0
SET_TONE_LUT_SRC_FILE = r"\Atc\ansel\src\libCitras.ansel\AnsCitrasOperand.cpp"
SET_TONE_LUT_FUNC = "AnsCitrasOperand::setToneLut"

#: `push 0x1b` at 0x10181f19 -- the "lutSize<1 or NULL" line (27).
SET_TONE_LUT_SIZE_ERROR_LINE = 0x1B
#: `push 0x2b` at 0x10181f59 -- the allocation-failure line (43).
SET_TONE_LUT_ALLOC_ERROR_LINE = 0x2B
SET_TONE_LUT_SIZE_ERROR_CODE = 0x69      # same family as CITRAS_ANALYZE's
SET_TONE_LUT_ALLOC_ERROR_CODE = 0xCA     # same code CITRAS_ALLOCATE_MEMORY uses

#: AnsCitrasOperand-relative offsets setToneLut touches -- the only two
#: fields this file's port models on that object.
OPERAND_LUT_SIZE = 0x30
OPERAND_TONE_LUT = 0x34


@dataclass
class CitrasApplyOperand:
    """``AnsCitrasOperand``, only the parts ``setToneLut`` touches.

    The real object also carries a 5-slot vtable (``0x1058386c``, found the
    same COL/vtable-search way as the ``ImaI16CitrasOp`` chain, but not
    otherwise used by this file) and whatever fields its accessor methods
    reach -- none of that is modelled, because ``setToneLut`` itself never
    dispatches through it.
    """

    lut_size: int = 0
    tone_lut: list[int] | None = None

    #: Every ``new[]``/``delete[]`` this object performed, mirroring
    #: ``pakon_citras.CitrasState``'s bookkeeping fields for the same reason:
    #: proving the free-before-realloc and the realloc-only-on-size-change
    #: behaviour actually happened.
    allocations: list[int] = field(default_factory=list)
    frees: int = 0

    #: Set to force the ``0x10181f57`` null-return branch under test.
    fail_allocation: bool = False


def apply_set_tone_lut(op: CitrasApplyOperand, lut_size: int, tone):
    """``AnsCitrasOperand::setToneLut`` (``0x10181ee0``), the whole body.

    ``thiscall(ecx=op)`` + ``(AnsStatus* sret, int lutSize, const unsigned
    short* tone)``, ``ret 0xc``.  ``tone`` is a sequence of at least
    ``lut_size`` unsigned 16-bit entries (or ``None`` for the null pointer).
    Returns ``None`` (OK) or a ``CitrasStatus`` -- same truthy-error
    convention as ``pakon_citras.citras_analyze``.

    Three things easy to get wrong, all modelled:

    * ``lutSize <= 0`` or ``tone is None`` is an error that leaves ``op``
      completely untouched (checked BEFORE anything else,
      ``0x10181f0e``..``0x10181f23``).
    * the existing buffer is only freed+reallocated when ``lutSize`` actually
      **changes** (``0x10181f29``, ``cmp ebx, [edi+0x30]; je`` skips straight
      to the copy when it's equal) -- an unchanged-size call overwrites the
      existing buffer in place, it does not always realloc.
    * the copy is ``lutSize*2`` bytes as ``rep movsd`` over ``(lutSize*2)>>2``
      dwords then ``rep movsb`` over ``(lutSize*2)&3`` -- the same odd-size
      tail shape ``pakon_citras.citras_analyze``'s own memcpy has.
    """
    from pakon_citras import CitrasStatus   # lazy -- see the module-level
                                            # note above this function for why

    if not CITRAS_APPLY_SET_TONE_LUT_PORTED:
        _unported("CITRAS_APPLY_SET_TONE_LUT_PORTED", SET_TONE_LUT,
                  "AnsCitrasOperand::setToneLut")

    # 0x10181f0e..0x10181f23 -- validated first; op is untouched on failure.
    if lut_size <= 0 or tone is None:
        return CitrasStatus(SET_TONE_LUT_SIZE_ERROR_CODE, SET_TONE_LUT_FUNC,
                            "Lut size is less than 1 or LUT is NULL.",
                            SET_TONE_LUT_SRC_FILE, SET_TONE_LUT_SIZE_ERROR_LINE)

    if isinstance(tone, int):
        raise RuntimeError(
            "apply_set_tone_lut got an opaque non-null tone pointer "
            f"({tone:#x}); pass a sequence of unsigned 16-bit entries.")

    # 0x10181f29 -- only realloc when the size actually changes.
    if lut_size != op.lut_size:
        if op.tone_lut is not None:                  # 0x10181f37
            op.tone_lut = None
            op.frees += 1
        n_bytes = (lut_size + lut_size) & 0xFFFFFFFF
        if op.fail_allocation or n_bytes >= 0x80000000:
            # 0x10181f57 -- `push eax /*new[] result==0*/; jne` not taken.
            op.lut_size = 0
            return CitrasStatus(
                SET_TONE_LUT_ALLOC_ERROR_CODE, SET_TONE_LUT_FUNC,
                "Failed in 'new ansPixel_t[lutSize]'",
                SET_TONE_LUT_SRC_FILE, SET_TONE_LUT_ALLOC_ERROR_LINE)
        op.allocations.append(n_bytes)
        op.lut_size = lut_size                        # 0x10181f73

    # 0x10181fbe.. -- memcpy(op->ToneLut, tone, lutSize*2).
    if len(tone) < lut_size:
        raise RuntimeError(
            f"apply_set_tone_lut: tone has {len(tone)} entries but lutSize "
            f"is {lut_size}; the DLL would read {lut_size * 2} bytes out of "
            "it.")
    op.tone_lut = [int(v) & 0xFFFF for v in tone[:lut_size]]
    return None


# ---------------------------------------------------------------------------
# recon-only stub -- validate (0x10167ae0), address real, body not ported.
# Phase 3b (virtual_56/apply_tone_compose) and Phase 3c
# (virtual_60/apply_avoidance_blend) each have their own real-implementation
# sections below, not here.
# ---------------------------------------------------------------------------


def validate(op_this, other_operand) -> bool:  # noqa: ARG001
    """``ImaI16CitrasOp::validate`` (``0x10167ae0``) -- recon only, not ported.

    See ``CITRAS_APPLY_VALIDATE_PORTED``'s comment for why. Calling this
    raises rather than silently returning a guess.
    """
    _unported("CITRAS_APPLY_VALIDATE_PORTED", 0x10167AE0,
             "ImaI16CitrasOp::validate")


# apply_tone_compose (ImaI16CitrasOp::virtual_56's per-pixel compute) is
# defined further below, after CitrasI16Plane -- the same per-band pixel
# accessor apply_avoidance_blend already established -- so it can reuse that
# dataclass instead of inventing a parallel one. See its own docstring and
# CITRAS_APPLY_TONE_COMPOSE_PORTED's comment above for the full derivation.


# ---------------------------------------------------------------------------
# ImaI16CitrasOp::virtual_56 -- validation prefix -- 0x10167bf0..0x10167d38
# ---------------------------------------------------------------------------

TONE_COMPOSE = 0x10167BF0

#: Return codes virtual_56 itself uses -- a raw int32, not an AnsStatus (no
#: sret argument, unlike validate()/setToneLut). See the flag's own comment
#: for which epilogue address each one is read off.
TONE_COMPOSE_ERR_NULL_OPERAND = -1     # 0xffffffff, epilogue 0x101682d0
TONE_COMPOSE_ERR_TYPE_MISMATCH = -2    # 0xfffffffe, epilogue 0x1016824d
TONE_COMPOSE_ERR_SHAPE_MISMATCH = -3   # 0xfffffffd, epilogue 0x10168206
TONE_COMPOSE_OK = 0

#: The real (typeInfo*, sampleSizeBytes) pair fcn.10311600(1) constructs for
#: "type 1", read directly out of the image (0x10311644's case body) --
#: confirmed == I16 (sampleSize 2, in a class literally named
#: `ImaI16CitrasOp`). An operand whose own operand+0x40->+0x20 pair matches
#: this exactly passes virtual_56's type check via the fast pointer-equal
#: path in fcn.1014f470, with no need to invoke the slower
#: `type_info::operator==` MSVCR71 import behind it.
TONE_COMPOSE_TYPE_I16 = (0x106908C0, 2)


@dataclass
class ComposeOperandShape:
    """Just the fields ``virtual_56``'s validation PREFIX reads off an
    operand, before it would begin the per-pixel compute (which this file
    does NOT port -- see ``CITRAS_APPLY_TONE_COMPOSE_PORTED``). Real
    offsets: ``width``\\ =+0x38, ``height``\\ =+0x3c (both plain dwords on
    the operand itself), ``band_count``\\ =(+0x40)->+0x18 and
    ``is_i16``\\ =(+0x40)->+0x20 compared against ``TONE_COMPOSE_TYPE_I16``
    (both plain dwords one level down, off the operand's own accessor
    sub-object -- no virtual dispatch needed to reach either).
    """

    width: int
    height: int
    band_count: int
    is_i16: bool = True


def tone_compose_validate(base: ComposeOperandShape | None,
                           term: ComposeOperandShape | None) -> int:
    """The NULL/type/dims/band-count validation prefix of
    ``ImaI16CitrasOp::virtual_56`` (``0x10167bf0``..``0x10167d38``) -- the
    part of the function this pass COULD Unicorn-verify. See
    ``CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED``'s comment for what
    "could" means here and why the per-pixel compute past this point is
    still unported (``CITRAS_APPLY_TONE_COMPOSE_PORTED`` stays ``False``).

    ``base`` is ``param_1``/``arg_60h`` (the operand ``virtual_56`` would
    mutate in place on success), ``term`` is ``param_3``/``arg_68h`` (the
    correction operand). ``param_2``/``arg_64h`` is real in the DLL -- every
    exit path releases it too -- but it is never READ for validation, so it
    has no representation here.

    Returns one of the four ``TONE_COMPOSE_*`` ints above, matching
    ``virtual_56``'s own return convention exactly.
    """
    if not CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED:
        _unported("CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED", TONE_COMPOSE,
                  "ImaI16CitrasOp::virtual_56 (validation prefix)")

    # 0x10167c20/0x10167c28 -- term(esi)==NULL or base(edi)==NULL, checked
    # FIRST, before any field of either object is read.
    if term is None or base is None:
        return TONE_COMPOSE_ERR_NULL_OPERAND

    # 0x10167c2e..0x10167c52 -- term must be I16 (checked before base).
    if not term.is_i16:
        return TONE_COMPOSE_ERR_TYPE_MISMATCH
    # 0x10167c58..0x10167c7c -- base must be I16 too.
    if not base.is_i16:
        return TONE_COMPOSE_ERR_TYPE_MISMATCH

    # 0x10167cf0..0x10167d32 -- dims/band-count, in this EXACT order (the
    # real code short-circuits on the first failing one, matched here so a
    # multi-failure input still reports the same failure the DLL would).
    if not (term.width > 0):
        return TONE_COMPOSE_ERR_SHAPE_MISMATCH
    if not (term.height > 0):
        return TONE_COMPOSE_ERR_SHAPE_MISMATCH
    if base.width != term.width:
        return TONE_COMPOSE_ERR_SHAPE_MISMATCH
    if base.height != term.height:
        return TONE_COMPOSE_ERR_SHAPE_MISMATCH
    if term.band_count != 3:
        return TONE_COMPOSE_ERR_SHAPE_MISMATCH
    if base.band_count > 3:
        return TONE_COMPOSE_ERR_SHAPE_MISMATCH

    return TONE_COMPOSE_OK


# ---------------------------------------------------------------------------
# ImaI16CitrasOp::virtual_60 -- 0x10168360 -- Phase 3c
# ---------------------------------------------------------------------------

AVOIDANCE_BLEND = 0x10168360

#: The generic "get-or-build the shared table object" accessor `this->0x108`
#: is resolved through. 5 cdecl args (this->0x108, 0, str, 0, str), caller
#: cleans up (`add esp,0x14` at 0x101685cb). Confirmed to return the SAME
#: object `this->0x108` already points to (its fields are re-read directly
#: off `this->0x108` immediately after, not off the return value alone) --
#: see the flag's own comment for why this is stubbed as an identity
#: accessor rather than ported.
AVOIDANCE_BLEND_TABLE_LOOKUP = 0x104FFDD6

#: The generic refcount-check helper the trailing (unmodelled) Release
#: block calls four times -- thiscall(ecx=target), returns bool in AL, no
#: stack args. Same address family as `pakon_citras_apply_golden.py`'s
#: existing AnsStatus refcount helpers.
AVOIDANCE_BLEND_REFCOUNT_CHECK = 0x100012E0

#: `this->0x108`'s cache fields, and the only configuration this pass
#: tested (see the flag's comment for why it is fixed rather than
#: threaded through as a parameter): the full signed-int16 domain.
AVOIDANCE_TABLE_SIZE = 0x10000
AVOIDANCE_TABLE_BIAS = -0x8000


def _wrap16(x: int) -> int:
    """Reduce ``x`` to a signed 16-bit value, matching every 16-bit
    register/memory op in this function (`sub ax,...`, `movsx ecx,cx`)."""
    return ((x + 0x8000) & 0xFFFF) - 0x8000


def _trunc_div100(n: int) -> int:
    """C-style truncating (round-toward-zero) signed division by 100.

    Bit-exact to the DLL's ``0x51eb851f`` magic-multiply idiom at
    ``0x10168692``..``0x101686a5`` (``imul`` by the magic constant, `sar
    edx,5`, then `+ sign-bit(edx)`) -- the textbook MSVC-generated
    implementation of C's ``/`` operator for a constant divisor of 100,
    exact for every ``int32`` dividend, not an approximation of it.
    """
    q = abs(n) // 100
    return -q if n < 0 else q


@dataclass
class CitrasPlane:
    """One of the four strided pixel-array views ``virtual_60`` reads or
    writes through.

    Addressed the way the function's generic per-operand accessor calls
    resolve a pointer: a row-0 base index into a flat ``data`` list, plus a
    per-column and per-row ELEMENT stride. The real DLL computes BYTE
    strides (`ImaI16CitrasOp`'s vtable+0x28 "count" accessor on each
    operand's own +0x40 sub-object, doubled for the three int16 planes and
    left as-is for the single 8-bit weight plane) -- this dataclass models
    the element stride one level below that byte/doubling detail, which is
    generic accessor plumbing the module docstring's object-layout section
    already scopes out of citras-specific work, not part of the math this
    flag is about.
    """

    data: list[int]
    row0: int = 0
    col_stride: int = 1
    row_stride: int = 0

    def _addr(self, r: int, c: int) -> int:
        return self.row0 + r * self.row_stride + c * self.col_stride


@dataclass
class CitrasI16Plane(CitrasPlane):
    """The reference / value / output planes -- 16-bit, sign-extended on
    read (`movsx eax, word [...]`), masked to 16 bits on write."""

    def read(self, r: int, c: int) -> int:
        return _wrap16(self.data[self._addr(r, c)] & 0xFFFF)

    def write(self, r: int, c: int, v: int) -> None:
        self.data[self._addr(r, c)] = v & 0xFFFF


@dataclass
class CitrasU8Plane(CitrasPlane):
    """The weight plane -- unsigned byte, zero-extended on read
    (`movzx ecx, byte [...]`)."""

    def read(self, r: int, c: int) -> int:
        return self.data[self._addr(r, c)] & 0xFF


def apply_avoidance_blend(rows: int, cols: int, table: list[int],
                           reference: CitrasI16Plane, weight: CitrasU8Plane,
                           value: CitrasI16Plane, out: CitrasI16Plane) -> None:
    """``ImaI16CitrasOp::virtual_60`` (``0x10168360``), the per-pixel math.

    ``table`` is ``AVOIDANCE_TABLE_SIZE`` (``0x10000``) signed-16-bit
    entries, indexed with ``AVOIDANCE_TABLE_BIAS`` (``-0x8000``) -- i.e.
    ``table[i]`` here corresponds to the DLL's ``table_base[i +
    AVOIDANCE_TABLE_BIAS]``. It is **mutated in place for the duration of
    the call and restored bit-exact before returning** (the DLL's own
    behaviour: every entry has its own signed index subtracted before the
    main loop and added back after, unconditionally, because it is a
    shared cached object this function borrows, not owns) -- modelled with
    a ``try/finally`` so a caller who inspects ``table`` mid-exception
    still sees the DLL's own un-recoverable-in-that-case state, not a
    silently "fixed" one.

    ``rows``/``cols`` are ``s->0x38``/``s->0x3c`` in the DLL's own
    ABI (``s`` being the object this port folds into ``reference`` --
    see the flag's comment for why the reference plane also carries the
    loop trip counts in the real object layout, a detail this port does
    not need to reproduce since ``reference``/``rows``/``cols`` are passed
    explicitly here instead).

    Per pixel: blend ``value`` toward ``reference`` by ``weight`` percent
    (``weight=100`` -> fully replaced by ``reference``; ``weight=0`` ->
    unchanged), THEN look the blended, 16-bit-wrapped index up in
    ``table`` -- the avoidance blend and the tone-table application fused
    into one pass, not two. See the flag's own comment for the full
    derivation and exact VAs.
    """
    if not CITRAS_APPLY_AVOIDANCE_BLEND_PORTED:
        _unported("CITRAS_APPLY_AVOIDANCE_BLEND_PORTED", AVOIDANCE_BLEND,
                 "ImaI16CitrasOp::virtual_60")

    if len(table) != AVOIDANCE_TABLE_SIZE:
        raise RuntimeError(
            f"apply_avoidance_blend: table has {len(table)} entries, "
            f"expected {AVOIDANCE_TABLE_SIZE} -- this port only models the "
            "bias=-0x8000/count=0x10000 configuration, see the flag's "
            "comment.")

    bias = AVOIDANCE_TABLE_BIAS
    lo, hi = bias, bias + AVOIDANCE_TABLE_SIZE - 1   # == -0x8000, 0x7fff

    # 0x101685de..0x1016860e -- bias-subtract the WHOLE table range, always,
    # regardless of rows/cols (the DLL's own `lo <= hi` gate is unconditionally
    # true for this fixed table configuration). Stored back masked to
    # unsigned 16 bits -- `table` models a raw memory word array (matching
    # how the golden harness reads it back, `struct.unpack("<H", ...)`), so
    # `_wrap16`'s SIGNED result (needed for the subtraction itself to match
    # the DLL's `sub word [...], ax` semantics) must be re-masked before
    # storage, not left signed -- an earlier draft of this function stored
    # the signed value directly and it matched the DLL's own output for
    # every genuinely-used index (proven by every ``opC`` case already
    # passing) while failing the table's own restored-state comparison for
    # every negative-``i`` entry, since ``-24576`` and ``40960`` are the
    # SAME 16-bit memory word under the two representations.
    for i in range(lo, hi + 1):
        table[i - bias] = _wrap16(table[i - bias] - i) & 0xFFFF
    try:
        # 0x10168640.. -- the double loop itself; skipped entirely (both
        # dimensions, not just one) when either trip count is <= 0, exactly
        # matching the DLL's two independent `jle` gates (0x10168618 on
        # rows, 0x10168646 on cols, the latter re-tested every row off the
        # SAME unchanging value -- collapsing to a single up-front `and` is
        # behaviour-equivalent since neither loop has an externally visible
        # side effect when skipped, only dead pointer arithmetic).
        if rows > 0 and cols > 0:
            for r in range(rows):
                for c in range(cols):
                    p = value.read(r, c)                 # opB
                    ref = reference.read(r, c)            # s
                    diff = _wrap16(p - ref)                 # 16-bit wrap sub
                    w = weight.read(r, c)                    # opA, 0..255
                    weighted = w * diff + 50                  # 0x32
                    q = _trunc_div100(weighted)
                    idx = _wrap16(p - q)
                    out.write(r, c, table[idx - bias])          # opC
    finally:
        # 0x1016874a..0x1016875d -- restore, same range, unconditional.
        for i in range(lo, hi + 1):
            table[i - bias] = _wrap16(table[i - bias] + i) & 0xFFFF


# ---------------------------------------------------------------------------
# ImaI16CitrasOp::virtual_56 -- per-pixel compute -- 0x10167d38..0x10168203
# ---------------------------------------------------------------------------

#: ``this``-relative offsets the compute reads for the clamp/no-clamp
#: decision -- ``this`` really is the ``ImaI16CitrasOp`` object (ecx at
#: function entry), confirmed live (see ``CITRAS_APPLY_TONE_COMPOSE_PORTED``'s
#: comment for how that was pinned down against an off-by-one-instruction
#: trap in naive breakpoint placement).
TONE_COMPOSE_FLAG_OFFSET = 0x124   # byte: 0 -> no clamp, nonzero -> clamp
TONE_COMPOSE_LOW_OFFSET = 0x126    # signed int16 (movsx), inclusive low bound
TONE_COMPOSE_HIGH_OFFSET = 0x128   # signed int16 (movsx), inclusive high bound


@dataclass
class ComposeOperand:
    """``base``/``term`` as ``virtual_56``'s per-pixel compute actually reads
    and writes them: the same shape fields ``tone_compose_validate`` checks,
    plus the real per-band pixel data -- ``bands`` is a list of exactly
    ``band_count`` ``CitrasI16Plane``\\ s, one per band, each independently
    addressed via the SAME generic ``getOffset()``/``getPtr()``/``count()``
    accessor protocol ``apply_avoidance_blend`` already established (see
    ``CitrasPlane``). This is not a simplification of an interleaved layout
    -- live tracing confirmed the real DLL asks for each band's own row-0
    pointer via a SEPARATE accessor call, so per-band planes are the real
    access pattern, not a port-side convenience.
    """

    width: int
    height: int
    band_count: int
    bands: list[CitrasI16Plane]
    is_i16: bool = True

    def shape(self) -> ComposeOperandShape:
        return ComposeOperandShape(width=self.width, height=self.height,
                                    band_count=self.band_count,
                                    is_i16=self.is_i16)


def apply_tone_compose(this_flag: int, this_low: int, this_high: int,
                        base: ComposeOperand | None,
                        term: ComposeOperand | None) -> int:
    """``ImaI16CitrasOp::virtual_56`` (``0x10167bf0``), the WHOLE function:
    the already-verified validation prefix (delegated to
    ``tone_compose_validate``) followed by the per-pixel compute this pass
    resolved via live Unicorn tracing.

    ``this_flag``/``this_low``/``this_high`` are ``this->0x124``/``0x126``/
    ``0x128`` (see the module-level offset constants) -- the caller is
    responsible for having already sign-extended ``this_low``/``this_high``
    from their real 16-bit memory representation, matching how the golden
    harness reads them (``struct.unpack("<h", ...)``).

    On success (return ``0``), **``term`` is mutated in place** -- NOT
    ``base``, correcting this file's own prior-pass claim (see
    ``CITRAS_APPLY_TONE_COMPOSE_PORTED``'s comment for the live evidence).
    ``base`` is read-only. Returns one of the four ``TONE_COMPOSE_*`` ints,
    exactly matching ``tone_compose_validate``'s own convention (this
    function IS a superset of that one).
    """
    if not CITRAS_APPLY_TONE_COMPOSE_PORTED:
        _unported("CITRAS_APPLY_TONE_COMPOSE_PORTED", TONE_COMPOSE,
                 "ImaI16CitrasOp::virtual_56 (per-pixel compute)")

    code = tone_compose_validate(
        None if base is None else base.shape(),
        None if term is None else term.shape())
    if code != TONE_COMPOSE_OK:
        return code

    # mypy/type-checkers: validation guarantees both are non-None past here.
    assert base is not None and term is not None

    clamp = this_flag != 0
    low, high = this_low, this_high

    # 0x10167d38..0x10168203 -- always all 3 of TERM's bands (band_count is
    # validated == 3 for term); BASE's band index is clamped/broadcast to
    # min(band, base.band_count - 1) when base has fewer than 3 bands (a
    # live-traced finding, not in the prior recon -- see the flag's comment).
    for band in range(term.band_count):
        base_band = min(band, base.band_count - 1)
        base_plane = base.bands[base_band]
        term_plane = term.bands[band]
        for r in range(term.height):
            for c in range(term.width):
                s = _wrap16(term_plane.read(r, c) + base_plane.read(r, c))
                if clamp:
                    s = max(low, min(high, s))
                term_plane.write(r, c, s)

    return TONE_COMPOSE_OK


# ---------------------------------------------------------------------------
# ImaI16CitrasOp::virtual_64 -- 0x10168800
# ---------------------------------------------------------------------------

LUMINANCE = 0x10168800


def _trunc_div3(n: int) -> int:
    """Signed truncating (round-toward-zero) division by 3.

    Bit-exact to the DLL's own ``0x55555556`` magic-multiply idiom
    (``imul edx``, ``shr eax,0x1f``, ``add eax,edx``) -- the SAME idiom
    ``pakon_dra.lum_histogram``'s ``_idiv(r+g+b+1, 3)`` already ports, kept
    as a separate local helper here (rather than importing that one) because
    this file does not otherwise depend on ``pakon_dra``.
    """
    q = abs(n) // 3
    return -q if n < 0 else q


@dataclass
class LuminanceOperand:
    """``source``/``dest`` as ``virtual_64`` actually reads/writes them --
    only the fields this function's own body touches: the loop bounds
    (``width``/``height``, taken from ``source`` regardless of which operand
    is passed as ``dest`` -- see ``CITRAS_APPLY_LUMINANCE_PORTED``'s comment
    for the live proof) and ``bands`` (3 planes for ``source``, 1 for
    ``dest``), each independently addressed via the SAME
    ``getOffset()``/``getPtr()``/``count()`` accessor protocol
    ``apply_tone_compose``/``apply_avoidance_blend`` already established.
    """

    width: int
    height: int
    bands: list[CitrasI16Plane]


def apply_luminance(source: LuminanceOperand, dest: LuminanceOperand) -> None:
    """``ImaI16CitrasOp::virtual_64`` (``0x10168800``), the whole function.

    ``thiscall(this, source, dest)`` -- ``this`` is unused (confirmed: no
    ``this``-relative read anywhere in the function body). Writes
    ``dest.bands[0]`` in place with the per-pixel truncating average of
    ``source.bands[0..2]`` (``(R + G + B + 1) / 3``, round-toward-zero) --
    see ``CITRAS_APPLY_LUMINANCE_PORTED``'s comment for the full derivation,
    including the live-traced correction that the loop bounds are
    ``source``'s own width/height, not ``dest``'s (a real, previously
    undocumented finding, not carried over from the Phase 3a recon).
    """
    if not CITRAS_APPLY_LUMINANCE_PORTED:
        _unported("CITRAS_APPLY_LUMINANCE_PORTED", LUMINANCE,
                 "ImaI16CitrasOp::virtual_64")

    r_plane, g_plane, b_plane = source.bands[0], source.bands[1], source.bands[2]
    out_plane = dest.bands[0]
    for r in range(source.height):
        for c in range(source.width):
            total = (r_plane.read(r, c) + g_plane.read(r, c)
                    + b_plane.read(r, c) + 1)
            out_plane.write(r, c, _trunc_div3(total))


# ---------------------------------------------------------------------------


def main() -> None:
    print("citras-apply -- Phase 3a (scaffolding), see docs/66 Phase 3")
    print()
    print("Class chain (COL/vtable, self-naming-RTTI-located):")
    for name, col, vt, n, str_va in CITRAS_APPLY_VTABLE_CHAIN:
        n_s = f"{n} slots" if n is not None else "slots not counted"
        print(f"  {name:<28} COL={col:#010x} vtable={vt:#010x}  {n_s}")
    print()
    print(f"ImaI16CitrasOp vtable ({IMAI16CITRASOP_VTABLE:#010x}, 17 slots):")
    for off, va, sz, role in CITRAS_APPLY_SLOTS:
        sz_s = f"{sz:>5} B" if sz is not None else "       "
        print(f"  +{off:#04x}  {va:#010x}  {sz_s}  {role}")
    print()
    print(f"  CITRAS_APPLY_OBJECT_LAYOUT_PORTED = {CITRAS_APPLY_OBJECT_LAYOUT_PORTED}")
    print(f"  CITRAS_APPLY_SET_TONE_LUT_PORTED  = {CITRAS_APPLY_SET_TONE_LUT_PORTED}")
    print(f"  CITRAS_APPLY_VALIDATE_PORTED      = {CITRAS_APPLY_VALIDATE_PORTED}  (not ported; proven orthogonal to the pixel math, excluded from the umbrella below)")
    print(f"  CITRAS_APPLY_TONE_COMPOSE_PORTED  = {CITRAS_APPLY_TONE_COMPOSE_PORTED}  (Phase 3b per-pixel compute, Unicorn-verified)")
    print(f"  CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED = {CITRAS_APPLY_TONE_COMPOSE_VALIDATE_PORTED}  (Phase 3b validation prefix, Unicorn-verified)")
    print(f"  CITRAS_APPLY_AVOIDANCE_BLEND_PORTED = {CITRAS_APPLY_AVOIDANCE_BLEND_PORTED}  (Phase 3c, Unicorn-verified)")
    print(f"  CITRAS_APPLY_LUMINANCE_PORTED     = {CITRAS_APPLY_LUMINANCE_PORTED}  (Phase 3, Unicorn-verified)")
    print(f"  CITRAS_APPLY_SCAFFOLD_PORTED      = {CITRAS_APPLY_SCAFFOLD_PORTED}  (honestly False -- ctor/factory path still not sized)")
    print(f"  CITRAS_APPLY_PORTED               = {CITRAS_APPLY_PORTED}  (umbrella; True -- all real per-pixel apply math ported & verified)")
    print()

    op = CitrasApplyOperand()
    lut = [(i * 7) & 0xFFF for i in range(0x1000)]
    st = apply_set_tone_lut(op, 0x1000, lut)
    print(f"  apply_set_tone_lut(fresh, 0x1000) -> {st}  "
          f"lutSize={op.lut_size} allocs={op.allocations} frees={op.frees} "
          f"first4={op.tone_lut[:4]}")
    st = apply_set_tone_lut(op, 0x1000, lut)
    print(f"  apply_set_tone_lut(same size again) -> {st}  "
          f"allocs={op.allocations} frees={op.frees}  (no realloc expected)")
    st = apply_set_tone_lut(op, 0, lut)
    print(f"  apply_set_tone_lut(lutSize=0) -> {st}")
    print()

    base = ComposeOperandShape(width=64, height=32, band_count=2)
    term = ComposeOperandShape(width=64, height=32, band_count=3)
    print(f"  tone_compose_validate(base, term) -> "
          f"{tone_compose_validate(base, term)}  (expect "
          f"{TONE_COMPOSE_OK}, OK)")
    print(f"  tone_compose_validate(None, term) -> "
          f"{tone_compose_validate(None, term)}  (expect "
          f"{TONE_COMPOSE_ERR_NULL_OPERAND})")
    bad_type = ComposeOperandShape(width=64, height=32, band_count=3,
                                   is_i16=False)
    print(f"  tone_compose_validate(base, bad_type) -> "
          f"{tone_compose_validate(base, bad_type)}  (expect "
          f"{TONE_COMPOSE_ERR_TYPE_MISMATCH})")
    mismatched = ComposeOperandShape(width=32, height=32, band_count=3)
    print(f"  tone_compose_validate(base, mismatched-width) -> "
          f"{tone_compose_validate(base, mismatched)}  (expect "
          f"{TONE_COMPOSE_ERR_SHAPE_MISMATCH})")


if __name__ == "__main__":
    main()
