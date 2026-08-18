/*
 * hookcore.h -- shared entry/exit hook engine used by both hookdll.c (the
 * real 23-address PSI.exe/PakonIMAu.dll/TLA.dll/TLB.dll harness) and
 * selftest.c (a synthetic self-test run under Wine on the dev machine,
 * see win_inject/README build notes).
 *
 * WHY A GENERIC, CALLING-CONVENTION-AGNOSTIC ENGINE
 * --------------------------------------------------
 * `agent.js`'s own header comment (the prior Frida version this ports)
 * says plainly: "It does not know the exact calling convention (register
 * vs. stack, exact arg index) for any of these functions at the assembly
 * level -- that was never re-derived from a live disassembly for this
 * task". That fact is still true here. MinHook's documented, normal usage
 * pattern is a typed C detour matching the target's real signature -- but
 * writing 23 typed detours would mean inventing 23 unconfirmed signatures,
 * exactly what this project's own rules forbid ("no invented addresses...
 * if unsure, say so honestly rather than guessing").
 *
 * So instead, every hook here uses ONE shared, hand-written x86 asm
 * entry stub (`hookstub.S`) that:
 *   1. Saves every general register + EFLAGS (a plain `pushfd; pushad`),
 *      so entry logging is a raw register/stack dump, identical in spirit
 *      to what agent.js's `regsToObj()`/`pointer_scan()` already did --
 *      never assuming which register/stack slot is "the" pixel buffer.
 *   2. Passes that raw state to `HookEntryC()` (below) for logging, then
 *      restores every register to its EXACT original value and tail-jumps
 *      (`jmp`, not `call`) into MinHook's trampoline for that hook -- so
 *      the original function executes with a byte-for-byte identical
 *      register/stack state to an un-hooked call. This works for cdecl,
 *      stdcall, thiscall, AND fastcall alike, because none of those
 *      Windows x86 conventions change where the return address lives (always
 *      the first thing on the stack at function entry) or what "restore
 *      every register + flags" means.
 *   3. For exit logging: rather than a `call` into the trampoline (which
 *      would push an extra return address and shift every stack-passed
 *      argument by 4 bytes relative to what the target's own prologue
 *      expects -- silently wrong for any function with stack args, on
 *      literally every convention except a zero-arg one), this uses the
 *      standard convention-agnostic "return address swap" technique: the
 *      real return address (to the ACTUAL caller) is saved on a per-thread
 *      shadow stack, and the stack slot is overwritten with the address of
 *      `OnReturnThunk`. When the hooked function eventually executes its
 *      own `ret`/`ret N` (which pops exactly one return address, however
 *      many bytes of arguments it additionally frees, on every one of
 *      these conventions), control lands in `OnReturnThunk` instead of the
 *      real caller, with the return value already sitting in EAX (and EDX
 *      for 64-bit returns) per the one universal x86-on-Windows rule that
 *      *is* convention-independent. `OnReturnThunk` logs, then tail-jumps
 *      to the real saved return address, so the real caller never knows
 *      any of this happened.
 *
 * WHAT THIS ASSUMES (the ONE real assumption, stated honestly, not hidden)
 * --------------------------------------------------------------------
 * The shared entry stub uses EAX as scratch for the final trampoline-jump
 * target immediately before entering the target's relocated prologue. On
 * every standard Windows x86 calling convention (cdecl, stdcall, thiscall,
 * fastcall), EAX never carries an incoming argument (fastcall's first two
 * args go in ECX/EDX; EAX is return-value-only) -- so this is safe for any
 * compiler-generated function using one of those four conventions, which
 * is true of essentially all MSVC-compiled C/C++ of this era (the vendor
 * DLLs; docs/62 already identifies several of these as C++ methods, e.g.
 * `ColorNegativePath::analyzeAutoTone`, `AnsAreaCapabilityImpl::
 * applyBalanceShifts`). It would NOT be safe for genuinely custom/
 * register-passing ABIs (unlikely for MSVC C++ output, but not something
 * that has been independently re-verified per-function from a live
 * disassembly -- flagged honestly here, not assumed silently).
 *
 * A SECOND, SEPARATE CAVEAT: if a hooked function's stack unwinds via a
 * C++ exception or SEH instead of a normal `ret` (e.g. the function or
 * something it calls throws), `OnReturnThunk` is never reached, and the
 * corresponding shadow-stack slot is never popped -- not a memory-safety
 * bug (nothing is ever jumped to based on a stale slot), but it does mean
 * that call's exit never gets logged, and in a worst case a later call at
 * the exact same thread+recursion-depth could pop a stale (wrong) slot.
 * Nothing here has any evidence of throwing in the normal per-frame image
 * path, but this is exactly the sort of thing to watch for in a live log
 * (an exit log entry whose `entry_hook_id` doesn't match what you'd
 * expect) rather than assume can't happen.
 *
 * WHY THIS IS SAFER THAN HAND-ROLLING THE TRAMPOLINE TOO
 * --------------------------------------------------------
 * The one part of this whole design that genuinely requires knowing x86
 * instruction lengths well enough to relocate a prologue -- i.e. finding
 * how many bytes of the target's real prologue can be safely copied out
 * before overwriting them with a jump, without splitting an instruction in
 * half -- is entirely MinHook's job (via its vendored HDE disassembler),
 * not this file's. That's the whole point of vendoring MinHook rather than
 * hand-rolling that specific, failure-prone part: it's a small, widely
 * used, actively-maintained engine, not a one-off implementation with 23
 * different real prologues to get right on the first try against
 * irreplaceable hardware.
 */

#ifndef HOOKCORE_H
#define HOOKCORE_H

#include <windows.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ---------------------------------------------------------------------
 * Fixed slot count. The asm side (hookstub.S) hand-defines exactly this
 * many Thunk_NN entry stubs (Thunk_00 .. Thunk_27). hookdll.c's real table
 * uses all 28 for the documented PSI.exe hooks; selftest.c reuses the same
 * fixed slots 0..N for its own small synthetic table. Never grow this
 * without adding matching Thunk_NN stubs in hookstub.S -- see hookstub.S's
 * own Thunk_23 comment (docs/74 §46) for what happens when this drifts:
 * a prior commit bumped this define and inserted a table[] entry
 * mid-array without adding a matching thunk, silently leaving one real
 * hook's entryThunk NULL. Bumped 25->28 (docs/74 §49, 2026-08-15): three
 * new TLB.dll lamp/AFE/CCD-acquire hooks
 * (tlb_lamp_on, tlb_afe_gain_write, tlb_ccd_acquire_control) appended at
 * the END of table[] in hookcore_real_table.c, same reasoning as
 * area_image_apply_lut's own append-only placement above -- so no
 * existing entry's index (and therefore no existing entry's thunk
 * assignment) moves again. Thunk_25/26/27 added to hookstub.S in the
 * same pass, matching thunks[25..27] in hookcore_real_table.c -- the
 * exact "forgot the matching thunk" mistake §46/§47 found and fixed is
 * the one thing this bump was double-checked against.
 * Bumped 28->29 (docs/74 §57, 2026-08-16): one new PakonIMAu.dll hook
 * (color_adjust_shift, 0x101b76d0) appended at the END of table[], same
 * append-only discipline. Thunk_28 added to hookstub.S in the same pass.
 * Bumped 30->31 (docs/74 §76, v24): one new PakonIMAu.dll hook
 * (sba_order_fpo_helper, 0x1028ae00) appended at the END of table[], same
 * append-only discipline. Thunk_30 added to hookstub.S and to
 * hookcore_real_table.c's thunks[] in the SAME pass. Its arg 9 is the one
 * value §76 could not derive statically (the Y term L[-0x200]); the engine
 * already logs 16 raw stack dwords per entry, so hooking it captures that
 * dword with no extra dump row at all.
 * Bumped 29->30 (docs/74 §72.7, v21): one new PakonIMAu.dll hook
 * (sba_order_fpo_calc, 0x1028b8d0) appended at the END of table[], same
 * append-only discipline. Thunk_29 added to hookstub.S and to
 * hookcore_real_table.c's own thunks[] array in the SAME pass -- the
 * §46.8/§47 "forgot the matching thunk" bug class this file's own comment
 * above documents was explicitly re-checked before committing.
 * --------------------------------------------------------------------- */
#define HOOKCORE_MAX_HOOKS 31

/* Must exactly match the PUSHAD+PUSHFD+index+retaddr stack layout that
 * hookstub.S's SharedEntryHandler builds -- see that file's header
 * comment for the derivation. hookdll.c has a compile-time static_assert
 * pinning these offsets so the two files can never silently drift apart.
 */
#pragma pack(push, 1)
typedef struct HookRegs {
    DWORD edi;
    DWORD esi;
    DWORD ebp_orig;
    DWORD esp_orig;   /* ESP as recorded by PUSHAD, i.e. entry_esp - 4 */
    DWORD ebx;
    DWORD edx;
    DWORD ecx;
    DWORD eax;
    DWORD eflags;
    DWORD hookIndex;
    DWORD retAddr;    /* return address to the REAL caller, at entry */
    /* stack-passed args, if any, immediately follow in the real stack
     * image; HookEntryC receives a pointer to this location separately
     * as argsPtr rather than as a flexible array member, to keep this
     * struct's size fixed and asm-offset math simple. */
} HookRegs;
#pragma pack(pop)

#define HOOKREGS_OFFSET_HOOKINDEX  36
#define HOOKREGS_OFFSET_RETADDR    40
#define HOOKREGS_OFFSET_ARGS       44

typedef struct HookDef {
    const char *dll;          /* module name, e.g. "PakonIMAu.dll" */
    DWORD       va;           /* documented VA, assumed base 0x10000000 */
    const char *id;           /* short id, matches agent.js's h.id */
    const char *desc;
    const char *cite;
    int         approximate;  /* 1 = agent.js flagged this address as
                                  not independently re-confirmed as a real
                                  function entry -- see agent.js/README.
                                  Disabled (not hooked) unless explicitly
                                  turned on in hooks.cfg. */
    int         wantExitDefault; /* 1 = attempt entry+exit by default,
                                     0 = entry-only by default (still
                                     overridable per-hook via hooks.cfg) */
    int         hotPathDisabled; /* 1 = the address IS a confirmed, real
                                     function entry (unlike `approximate`,
                                     this says nothing about the citation's
                                     confidence) but is disabled BY DEFAULT
                                     anyway, because it is a demonstrated
                                     per-pixel/per-scanline hot path AND its
                                     original diagnostic purpose has since
                                     been fully resolved by static
                                     disassembly, leaving no remaining
                                     live-capture value to justify tracing
                                     it at full volume by default -- see
                                     hookcore_real_table.c's citation for
                                     the specific hook this applies to.
                                     Still just an `enabled` default: turn
                                     it back on any time via hooks.cfg
                                     exactly like any other hook. */
    int         notCallReachable; /* 1 = a real, targeted r2 `af`+`axt`
                                     cross-reference pass against the
                                     MD5/sha256-verified vendor DLL (done
                                     2026-08-15, after two real XP-box
                                     captures kept showing the same
                                     "stops mid-loop, no shutdown message"
                                     failure the FlushFileBuffers fix did
                                     NOT resolve) found this documented VA
                                     is NOT the entry point of its own,
                                     independently call-reachable function
                                     -- it is either (a) an internal
                                     branch/fallthrough target reached only
                                     via a jmp/jcc from WITHIN a different,
                                     larger enclosing function (confirmed by
                                     `af` walking back to an earlier, real
                                     entry address when analysis starts from
                                     the documented VA, and by `axt` finding
                                     only CODE-type, not CALL-type, xrefs),
                                     or (b) in one case worse still, the
                                     literal address of a `call` opcode
                                     inside another function, not any kind
                                     of function boundary at all. THIS
                                     MATTERS SPECIFICALLY because of how
                                     hookstub.S's return-address-swap
                                     technique works (see this header's own
                                     top comment): it assumes the DWORD
                                     sitting at [esp] the instant a hooked
                                     address is reached is always a genuine
                                     return address pushed by a real `call`
                                     instruction, and unconditionally
                                     overwrites that stack slot with
                                     `OnReturnThunk`'s address if exit-
                                     hooking is enabled. When a hooked
                                     address is reached via anything other
                                     than `call` -- straight-line
                                     fallthrough or an internal jmp/jcc --
                                     that assumption is false: [esp] holds
                                     whatever real local variable or spilled
                                     register the ACTUAL enclosing function
                                     put there, and swapping it corrupts
                                     live data belonging to a function this
                                     harness never intended to touch at all.
                                     Live evidence for exactly this failure
                                     mode exists for at least one of these
                                     (`sba_set_shifts_12`, see its own
                                     citation) in both new 2026-08-14
                                     captures. Disabled BY DEFAULT regardless
                                     of `approximate`/`hotPathDisabled` --
                                     unlike those two fields, there is
                                     nothing to "verify live" here to turn
                                     this back on: the underlying subsystem
                                     this hook wanted to observe still has
                                     no independently call-reachable entry
                                     address documented anywhere, so
                                     re-enabling THIS specific VA is never
                                     correct; a genuinely new address would
                                     need to be re-derived first. See
                                     hookcore_real_table.c's own citation for
                                     the specific evidence per affected
                                     hook, and hookcore.c's `HookEntryC` for
                                     the separate, general runtime guard
                                     added at the same time (a `VirtualQuery`
                                     sanity check before ever committing to
                                     the swap) so a hook not yet known to
                                     have this problem can't cause the same
                                     corruption either. */
    void       *entryThunk;   /* Thunk_NN function pointer, assigned by
                                  the table-builder in hookcore.c */
} HookDef;

typedef struct HookRuntime {
    int      enabled;         /* resolved after hooks.cfg + approximate
                                  default, before install is attempted */
    int      exitEnabled;
    void    *target;          /* resolved runtime address */
    void    *trampoline;      /* MinHook original-call trampoline */
    int      installed;
} HookRuntime;

/* ---------------------------------------------------------------------
 * OPT-IN, PER-HOOK "ALSO DUMP FULL BUFFER CONTENTS" EXTENSION (docs/74
 * SS47) -- layered ON TOP of the existing generic stack_dwords dump, not
 * a replacement for it. Motivation: for area_image_apply_lut specifically
 * (docs/74 SS46/SS47), the 3 LUT-pointer stack_dwords (indices 1/2/3,
 * confirmed docs/74 SS47.1's own re-derivation of the calling convention)
 * point at real, small (4096 entries x int16 = 8192 bytes each) buffers
 * whose CONTENTS -- not just their addresses -- had never been captured.
 * Deliberately kept OUT of HookDef itself (not a new positional field
 * threaded through all 25 existing table-literal entries in
 * hookcore_real_table.c) precisely because it is hook_id-specific,
 * optional, and small -- same spirit as hooks.cfg being a separate
 * overlay rather than a HookDef field, so adding it cannot silently
 * shift any existing entry's fields the way the Thunk_23 bug (SS46.8)
 * already showed a positional-array insertion can. Bounded at
 * HOOKCORE_EXTRA_DUMP_MAX_BYTES per row specifically so this stays a
 * small, cheap addition on the real box (worst case for
 * area_image_apply_lut: 3 x 8192 + 1 x 256 bytes per CALL, not per
 * pixel -- nothing like the per-pixel volume hotPathDisabled guards
 * against). Every row is IsBadReadPtr-guarded exactly like the existing
 * stack_dwords dump; an unreadable pointer logs `"readable":false`
 * rather than skipping the row silently or crashing.
 * Bumped 8192 -> 0x84000 (540672 = 132 pages, docs/74 SS60, 2026-08-16):
 * the full 245x367 planar/interleaved frame is 539490 bytes (=0x83B62), so
 * the old cap only carried ~2-16 scanlines, which is not enough to solve
 * the raw<->RPD12 spatial relayout by 2D cross-correlation (the two
 * buffers are laid out differently and the truncated tops don't overlap).
 * 0x84000 is the page-rounded committed size of that buffer (539490 rounds
 * up to 132*4096); the first v12 build used 0x90000 (the observed inter-
 * buffer stride) and every full-frame dump came back IsBadReadPtr-failed,
 * so 0x84000 is the read-safe ceiling. LogExtraDumps' line buffer moved to
 * the heap at the same time because 0x84000*2 hex chars exceeds the
 * default 1 MB thread stack. */
#define HOOKCORE_MAX_EXTRA_DUMPS 8
#define HOOKCORE_EXTRA_DUMP_MAX_BYTES 0x84000

typedef enum ExtraDumpKind {
    EXTRA_DUMP_STACK_PTR = 0,  /* dump N bytes from   *stack_dwords[idx]        */
    EXTRA_DUMP_DEREF_PTR = 1,  /* dump N bytes from  **(stack_dwords[idx]+off)  */
    EXTRA_DUMP_THIS_OFFSET = 2,/* dump N bytes from   (regs->ecx + derefOffset) --
                                   for a __thiscall target, the Impl/`this`
                                   object's own fields (stackIndex ignored)     */
    EXTRA_DUMP_PLANAR_PLANE = 3, /* dump N bytes from  *(stack_dwords[idx]) +
                                   (stack_dwords[3] * stack_dwords[4]) *
                                   derefOffset -- PolyPixel's planar buffer,
                                   R/G/B at base + w*h*(0/2/4); w/h are
                                   hard-coded to stack_dwords[3]/[4] per the
                                   PolyPixel calling convention (docs/74 SS32)  */
    EXTRA_DUMP_THIS_DEREF_OFFSET = 4, /* dump N bytes from
                                    *(regs->ecx + stackIndex) + derefOffset --
                                    for a __thiscall target whose `this` points
                                    to a holder: deref this+stackIndex to get the
                                    Impl, then add derefOffset (e.g. getShifts
                                    reads *(SbaCap+0x10)+0x3a38)                */
    EXTRA_DUMP_STACK_PTR_OFFSET = 5, /* dump N bytes from
                                    (stack_dwords[idx] + derefOffset) -- a raw
                                    stack arg pointer PLUS an offset, for a
                                    field inside the arg's struct (e.g.
                                    balanceAreaImage reads the shift at
                                    arg4+0x0a)                                 */
    EXTRA_DUMP_STACK_DEREF2_OFFSET = 6 /* dump N bytes from
                                    *(stack_dwords[idx] + derefOffset) +
                                    derefOffset2 -- a double deref then offset
                                    (e.g. getShifts reads *(arg1+0x10)+0x3a38,
                                    arg1 = stack_dwords[0])                    */
} ExtraDumpKind;

typedef struct ExtraDumpSpec {
    const char    *hookId;      /* matches HookDef.id                       */
    const char    *label;       /* short JSON field name, e.g. "r_lut"      */
    ExtraDumpKind  kind;
    int            stackIndex;  /* index into the same stack_dwords[] array
                                     HookEntryC already logs on "enter"       */
    DWORD          derefOffset; /* only used for EXTRA_DUMP_DEREF_PTR       */
    DWORD          derefOffset2;/* only used for EXTRA_DUMP_STACK_DEREF2_OFFSET */
    DWORD          numBytes;    /* must be <= HOOKCORE_EXTRA_DUMP_MAX_BYTES,
                                     enforced defensively at the call site
                                     too, not just by convention here        */
} ExtraDumpSpec;

/* Defined in hookcore_real_table.c, terminated by a {NULL,...} sentinel
 * row (checked by hookId == NULL, not by array length). */
extern const ExtraDumpSpec g_extraDumps[];

/* One shared engine instance -- either hookdll.c's real table or
 * selftest.c's synthetic one, never both in the same process. */
typedef struct HookEngine {
    HookDef      defs[HOOKCORE_MAX_HOOKS];
    HookRuntime  rt[HOOKCORE_MAX_HOOKS];
    int          count;
    const char  *logPath;
    HANDLE       logFile;
    CRITICAL_SECTION logLock;
    volatile LONG callCounter;
    DWORD        tlsShadowStack; /* TLS slot index */
    int          unflushedLines; /* protected by logLock; see LogLine in
                                     hookcore.c for why the hot per-call
                                     path no longer flushes every line */
} HookEngine;

/* The single global engine instance -- one per process, defined in
 * hookcore.c. Both hookdll.c and selftest.c use this same symbol; only
 * one of those two object files is ever linked into a given binary. */
extern HookEngine g_engine;

/* Populate g_engine.defs[]/count with the REAL PSI.exe hook table (28
 * entries as of docs/74 SS49; originally a 23-hook, then 25-hook table)
 * (verbatim transcription of agent.js's HOOKS array -- see
 * hookcore_real_table.c and its own header for the address-by-address
 * citations, and tools/re/live_hooks/win_inject/check_table_sync.py for
 * the automated cross-check against agent.js). */
void HookCore_BuildRealTable(HookEngine *eng);

/* CALL ORDER CONTRACT: BuildRealTable/BuildSelftestTable (whichever
 * populates eng->defs[]/eng->count for this process) MUST run BEFORE
 * HookCore_Init -- Init's config loading walks defs[0..count) to apply
 * per-hook enable/exit defaults and hooks.cfg overrides, so the table
 * needs to exist first. Getting this backwards silently no-ops every
 * hook (count reads as 0) rather than crashing, so it's easy to miss --
 * both hookdll.c and selftest.c order it correctly; keep it that way if
 * you add a third caller.
 *
 * Read "<dir-of-module>\hooks.cfg" if present (one line per hook,
 * `<id>=on|off`, `#` comments, blank lines ignored) plus a top-level
 * `EXIT=on|off` global toggle, and apply it on top of each HookDef's
 * defaults (approximate => disabled, else enabled; wantExitDefault as
 * given). Never fatal if the file is missing -- defaults apply. */
void HookCore_LoadConfig(HookEngine *eng, const char *configDir);

/* Open the log file (path: <configDir>\live_hooks_<timestamp>.jsonl
 * unless HOOKDLL_LOG_PATH env var is set), init the critical section and
 * TLS slot. Call once before InstallAll. */
BOOL HookCore_Init(HookEngine *eng, const char *configDir);

/* Attempt MH_Initialize() + MH_CreateHook()+MH_EnableHook() for every
 * enabled-but-not-yet-installed hook whose DLL is currently loaded
 * (GetModuleHandleA). Safe to call repeatedly (e.g. from a retry-poll
 * loop) -- already-installed hooks are skipped. Returns count of hooks
 * newly installed this call. */
int HookCore_InstallPass(HookEngine *eng);

/* Best-effort teardown: MH_DisableHook(MH_ALL_HOOKS), MH_Uninitialize(),
 * flush + close the log file. */
void HookCore_Shutdown(HookEngine *eng);

/* Writes one {"kind":"status",...} JSONL line. Exposed for callers
 * (hookdll.c's worker thread) that want to log their own progress
 * messages through the same file/lock. */
void HookCore_LogStatus(HookEngine *eng, const char *msg);

/* ---------------------------------------------------------------------
 * Called from hookstub.S -- see that file for the exact calling
 * sequence. Not intended to be called from anywhere else.
 * --------------------------------------------------------------------- */

/* Logs entry, decides whether to install the return-address swap for
 * this specific call (based on rt.exitEnabled and shadow-stack depth),
 * pushes the shadow-stack frame if so, and ALWAYS returns the trampoline
 * pointer to jump to (never NULL for an installed hook -- hookIndex values
 * that somehow reach here uninstalled are a bug, logged loudly and the
 * call falls back to returning hookIndex's raw target address if even
 * that is unavailable, rather than jumping to garbage). *outSwapAddr is
 * set to the OnReturnThunk address if exit-hooking this call, else left
 * as NULL (caller must zero-init before the call; hookstub.S does). */
void *HookEntryC(DWORD hookIndex, HookRegs *regs, void *realRetAddr,
                  void *argsPtr, void **outSwapAddr);

/* Called from OnReturnThunk with the real EAX/EDX return value pair
 * preserved by the caller (asm) around this call -- logs exit, pops the
 * shadow-stack frame for the current thread, and returns the real
 * original return address to jump to. */
void *LogExitC(DWORD eaxRet, DWORD edxRet);

/* Defined in hookstub.S. HookEntryC uses its address (a plain function
 * pointer, not a call) as the return-address-swap target. */
extern void OnReturnThunk(void);

/* The 23 fixed entry-thunk slots, defined in hookstub.S. hookdll.c's real
 * table and selftest.c's synthetic table both assign these (in slot
 * order) into HookDef.entryThunk. */
extern void Thunk_00(void); extern void Thunk_01(void); extern void Thunk_02(void);
extern void Thunk_03(void); extern void Thunk_04(void); extern void Thunk_05(void);
extern void Thunk_06(void); extern void Thunk_07(void); extern void Thunk_08(void);
extern void Thunk_09(void); extern void Thunk_10(void); extern void Thunk_11(void);
extern void Thunk_12(void); extern void Thunk_13(void); extern void Thunk_14(void);
extern void Thunk_15(void); extern void Thunk_16(void); extern void Thunk_17(void);
extern void Thunk_18(void); extern void Thunk_19(void); extern void Thunk_20(void);
extern void Thunk_21(void); extern void Thunk_22(void);
extern void Thunk_23(void); extern void Thunk_24(void);
extern void Thunk_25(void); extern void Thunk_26(void); extern void Thunk_27(void);
extern void Thunk_28(void); extern void Thunk_29(void);
extern void Thunk_30(void);

#ifdef __cplusplus
}
#endif

#endif /* HOOKCORE_H */
