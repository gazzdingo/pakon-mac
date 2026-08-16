/*
 * hookstub.S -- the ONE hand-written x86 asm entry/exit engine shared by
 * every hook. Read hookcore.h's header comment FIRST -- it explains why
 * this exists (generic, calling-convention-agnostic entry+exit, because
 * none of the 23 real targets' true signatures are known) and the exact
 * design of the "return-address swap" exit technique before you read the
 * code below.
 *
 * Assembled by i686-w64-mingw32-gcc (passed through as a real .S file --
 * preprocessed then handed to GNU as). i686-w64-mingw32-gcc decorates
 * cdecl C symbols with a single leading underscore (verified directly:
 * `echo 'int foo(void){return 1;}' | i686-w64-mingw32-gcc -c -xc - -o -
 * | i686-w64-mingw32-nm -` prints `T _foo`) -- every C symbol referenced
 * or defined here uses that convention (`_HookEntryC`, `_LogExitC`,
 * `_OnReturnThunk`, `_Thunk_NN`).
 *
 * STACK LAYOUT AT SharedEntryHandler, after `pushfd; pushad; mov ebp,esp`
 * -----------------------------------------------------------------------
 *   [ebp+0]  saved EDI            [ebp+20] saved EDX
 *   [ebp+4]  saved ESI            [ebp+24] saved ECX
 *   [ebp+8]  saved EBP (real)     [ebp+28] saved EAX
 *   [ebp+12] saved ESP (pre-pushad, i.e. entry_esp - 4, from PUSHAD itself)
 *   [ebp+16] saved EBX            [ebp+32] saved EFLAGS (from PUSHFD)
 *   [ebp+36] hookIndex (pushed by the Thunk_NN that got us here)
 *   [ebp+40] retAddr    (return address to the REAL caller)
 *   [ebp+44..] the target function's real stack-passed args, untouched
 *
 * This exactly matches HookRegs in hookcore.h (HOOKREGS_OFFSET_HOOKINDEX
 * = 36, _RETADDR = 40, _ARGS = 44) -- hookcore.c has a compile-time
 * static_assert pinning those numbers, so if this file and that struct
 * ever drift apart, the build fails loudly instead of corrupting a live
 * scan silently.
 */

    .intel_syntax noprefix
    .text

/* ---------------------------------------------------------------------
 * SharedEntryHandler -- every Thunk_NN lands here after `push idx`.
 * Ends by tail-jumping (`jmp`, never `call`) into the trampoline MinHook
 * built for this hook, with every register restored to its exact
 * original value and the stack laid out exactly as the real caller left
 * it -- except the return-address slot may have been swapped to
 * _OnReturnThunk if HookEntryC (C side) decided to exit-hook this call.
 * --------------------------------------------------------------------- */
    .globl _SharedEntryHandler
_SharedEntryHandler:
    pushfd
    pushad
    mov     ebp, esp
    sub     esp, 4                  /* local: outSwapAddr slot, [ebp-4] */
    mov     dword ptr [ebp-4], 0

    /* cdecl args pushed right-to-left: outSwapAddr, argsPtr, realRetAddr,
     * regs, hookIndex (hookIndex pushed LAST so it lands as arg #1). */
    lea     eax, [ebp-4]
    push    eax                     /* outSwapAddr = &local            */
    lea     eax, [ebp+44]
    push    eax                     /* argsPtr                         */
    push    dword ptr [ebp+40]      /* realRetAddr                     */
    push    ebp                     /* regs (HookRegs* == ebp itself)  */
    push    dword ptr [ebp+36]      /* hookIndex                       */
    call    _HookEntryC
    add     esp, 20                 /* cdecl cleanup, 5 args * 4       */
    /* eax == trampoline pointer for this hook (NULL only on the
     * structurally-impossible bug path -- see .Lbug_no_trampoline) */

    mov     ecx, [ebp-4]            /* swap target, 0 or &_OnReturnThunk */
    test    ecx, ecx
    jz      .Lno_swap
    mov     [ebp+40], ecx           /* overwrite retaddr slot in place  */
.Lno_swap:
    mov     [ebp+36], eax           /* stash trampoline ptr where hookIndex was */

    mov     esp, ebp                /* undo our locals/call args        */
    popad                           /* restores real edi/esi/ebp/ebx/edx/ecx/eax */
    popfd                           /* restores real eflags             */
    pop     eax                     /* trampoline ptr; esp now -> retaddr (maybe swapped) */
    test    eax, eax
    jz      .Lbug_no_trampoline
    jmp     eax                     /* tail-jump into MinHook's trampoline */

.Lbug_no_trampoline:
    /* HookEntryC returned NULL. Per its own contract (hookcore.h) this
     * means hookIndex was out of range or not installed -- structurally
     * impossible in normal operation (a Thunk_NN only ever runs because
     * MinHook patched a target to jump to it, which only happens after
     * this same hookIndex was successfully installed). If this is ever
     * actually reached, something is badly wrong (e.g. a stale/mismatched
     * build) -- silently `ret`-ing here would skip the real function
     * entirely and hand the real caller garbage register state as a
     * "return value", i.e. silent data corruption during a live scan,
     * which is worse than a clean crash. `int 3` deliberately raises a
     * breakpoint exception; with no debugger attached, Windows terminates
     * the process visibly instead. See README "Safety" section. */
    int     3

/* ---------------------------------------------------------------------
 * OnReturnThunk -- lands here when a hooked function's own `ret`/`ret N`
 * pops the swapped return address instead of the real one. At this exact
 * point: EAX (and EDX, for 64-bit-wide returns) hold the function's real
 * return value, and ESP/EBP/EBX/ESI/EDI already equal exactly what the
 * REAL caller expects immediately after the call (any stdcall/thiscall
 * "ret N" stack cleanup already happened as part of that same ret) --
 * i.e. we are, for every register except EAX/EDX/ECX/EFLAGS (the
 * standard x86 volatile/caller-saved set on every Windows calling
 * convention), already indistinguishable from "just returned to the real
 * caller". So this only needs to preserve EAX/EDX across the C call,
 * then tail-jump to the real saved return address.
 * --------------------------------------------------------------------- */
    .globl _OnReturnThunk
_OnReturnThunk:
    /* pushfd MUST be the very first instruction here -- see the fix note
     * below. It captures the REAL EFLAGS the hooked function set immediately
     * before its own `ret`/`ret N` (the standard x86-on-Windows rule that,
     * like EAX/EDX, is convention-independent). */
    pushfd
    push    ebp
    mov     ebp, esp
    sub     esp, 12                 /* [ebp-4]=eax [ebp-8]=edx [ebp-12]=realRetAddr;
                                        real eflags sit at [ebp+4] (pushed
                                        before ebp, above it in this frame) */
    mov     [ebp-4], eax
    mov     [ebp-8], edx

    push    edx                     /* LogExitC(eaxRet, edxRet) -- cdecl, edxRet pushed first */
    push    eax
    call    _LogExitC
    add     esp, 8
    mov     [ebp-12], eax           /* real original return address */

    mov     eax, [ebp-4]            /* restore the function's real return value */
    mov     edx, [ebp-8]
    mov     ecx, [ebp-12]           /* jump target -- ECX is caller-clobberable
                                        on every relevant convention, safe scratch */
    mov     esp, ebp
    pop     ebp                     /* esp now -> the eflags dword pushed first */
    popfd                           /* restore the REAL eflags (see fix note above) */
    jmp     ecx
    /* FIX (2026-08-15): the original version here did `sub esp, 16` --
     * which sets EFLAGS via its own subtraction result -- BEFORE its own
     * `pushfd`, so it captured and later restored its OWN clobbered flags
     * instead of the hooked function's genuine return-time flags. In
     * practice this is unlikely to be the primary cause of any crash seen
     * so far (no mainstream x86 Windows calling convention or compiler
     * treats EFLAGS as preserved across a `call` boundary -- MSVC and GCC
     * both treat flags as fully clobbered by any call), but it is a real,
     * confirmed discrepancy from this file's own documented contract
     * ("preserve EAX/EDX/EFLAGS across the C call"), found by reading this
     * exact sequence very carefully while investigating the
     * icc_effect_op/icc_xform_apply "stops mid-loop" failures, and fixed
     * on the same pass since it costs nothing extra (same instruction
     * count, just reordered) and there's no reason to ship a known-wrong
     * flags value instead of a known-correct one. */

/* ---------------------------------------------------------------------
 * Thunk_00 .. Thunk_27 -- 28 fixed slots (HOOKCORE_MAX_HOOKS in
 * hookcore.h). Each is just `push <its own index>; jmp SharedEntryHandler`
 * -- deliberately identical in shape so a bug in one is a bug in all of
 * them (uniform, mechanically-checkable, not 28 independently-hand-
 * written variants that could each have their own typo).
 *
 * Thunk_25/26/27 (docs/74 §49, 2026-08-15): added alongside the three new
 * TLB.dll lamp/AFE-gain/CCD-acquire-control hooks appended at the END of
 * hookcore_real_table.c's table[] (tlb_lamp_on, tlb_afe_gain_write,
 * tlb_ccd_acquire_control). Added in the SAME commit as the
 * HOOKCORE_MAX_HOOKS 25->28 bump and the new thunks[25..27] entries in
 * hookcore_real_table.c, specifically to not repeat the Thunk_23 bug
 * described below (a table[] bump that landed without its matching thunk).
 *
 * Thunk_23 (added docs/74 §46, alongside Thunk_24): fixes a real, latent
 * bug this file did NOT introduce but that a prior commit (6d2e36a,
 * "add analyze_scp_lut_balance hook") did. That commit bumped
 * HOOKCORE_MAX_HOOKS 23->24 and inserted its new table[] entry in the
 * MIDDLE of hookcore_real_table.c's array (right after balance_area_image),
 * which shifted every later entry's array index up by one -- including
 * tlb_afe_offset_write, which moved from index 22 (Thunk_22, real) to
 * index 23 (no Thunk_23 existed). `HookCore_BuildRealTable`'s
 * `eng->defs[i].entryThunk = thunks[i]` is purely positional, and
 * `thunks[HOOKCORE_MAX_HOOKS]`'s C array initializer only named 23
 * thunks -- so `thunks[23]` silently zero-initialized to NULL, meaning
 * tlb_afe_offset_write's `entryThunk` was NULL the moment that commit
 * landed. This was never caught because (a) selftest.c uses its own
 * separate 4-hook synthetic table (`void *thunks[4]`), never exercising
 * `HookCore_BuildRealTable`'s real 24-entry array at all, and (b)
 * tlb_afe_offset_write's own MH_CreateHook call has independently failed
 * with MH_ERROR_NOT_EXECUTABLE on every real capture so far (docs/74
 * §40.1's own "every one of the 121 failures is tlb_afe_offset_write"),
 * which short-circuits before MinHook ever dereferences the NULL
 * pDetour -- so the bug has been silently latent, not silently wrong,
 * on every capture to date. Confirmed by direct inspection (`git show
 * 6d2e36a -- hookstub.S` shows zero changes to this file in that commit)
 * before writing this, not assumed. Fixed here by simply defining the
 * thunk that should have existed all along, at the position its
 * (unmoved) index already implies.
 * --------------------------------------------------------------------- */
    .macro DEFTHUNK idx, sfx
    .globl _Thunk_\sfx
_Thunk_\sfx:
    push    \idx
    jmp     _SharedEntryHandler
    .endm

    DEFTHUNK 0, 00
    DEFTHUNK 1, 01
    DEFTHUNK 2, 02
    DEFTHUNK 3, 03
    DEFTHUNK 4, 04
    DEFTHUNK 5, 05
    DEFTHUNK 6, 06
    DEFTHUNK 7, 07
    DEFTHUNK 8, 08
    DEFTHUNK 9, 09
    DEFTHUNK 10, 10
    DEFTHUNK 11, 11
    DEFTHUNK 12, 12
    DEFTHUNK 13, 13
    DEFTHUNK 14, 14
    DEFTHUNK 15, 15
    DEFTHUNK 16, 16
    DEFTHUNK 17, 17
    DEFTHUNK 18, 18
    DEFTHUNK 19, 19
    DEFTHUNK 20, 20
    DEFTHUNK 21, 21
    DEFTHUNK 22, 22
    DEFTHUNK 23, 23
    DEFTHUNK 24, 24
    DEFTHUNK 25, 25
    DEFTHUNK 26, 26
    DEFTHUNK 27, 27
