/*
 * hookcore_real_table.c -- the REAL 23-address PSI.exe hook table.
 *
 * This is a byte-for-byte transcription of `HOOKS` in `../agent.js` (the
 * prior Frida version) -- same 23 addresses, same ids, same dll names,
 * same citations, in the same order (so `HookCore_BuildRealTable`'s
 * implicit index assignment 0..22 for entryThunk = Thunk_00..Thunk_22
 * lines up 1:1 with agent.js's own HOOKS array position). Per the task
 * this was built for: "reuse that exact address list and citations,
 * don't re-derive from scratch" -- nothing below was re-derived; every
 * `va`/`cite` field is copied from agent.js verbatim.
 *
 * `check_table_sync.py` in this same directory automatically parses both
 * this file and agent.js and diffs their (dll, va, id) triples, so this
 * claim is mechanically checked, not just asserted in a comment.
 *
 * exitDefault: 1 for every confirmed-address hook (entry+exit attempted
 * by default), except the two `approximate: true` entries below, which
 * are DISABLED entirely by default (see HookCore_LoadConfig) regardless
 * of exitDefault, until verified live -- exitDefault is still set
 * honestly for them (matching the others) so enabling them via hooks.cfg
 * gets sensible behavior without a second edit.
 *
 * One extra runtime note not in agent.js: `tla_colneg_mmx_kernel` (index
 * 19) is described in agent.js's own citation as "the inner MMX kernel
 * itself" -- if that runs per-scanline or per-pixel-block rather than
 * once per frame, entry+exit hooking it live could be high-frequency
 * (large log volume, measurable slowdown). It defaults to exit-enabled
 * here like everything else, but hooks.cfg lets you turn it off
 * (`tla_colneg_mmx_kernel.exit=off` or `tla_colneg_mmx_kernel=off`
 * entirely) without a rebuild if a first live run shows it's too hot --
 * see README.md.
 *
 * hotPathDisabled (added after docs/74 SS32's real disassembly of
 * `tlb_polypixel`/0x1000d880): a second, DISTINCT reason a confirmed-real
 * hook can default to off, separate from `approximate`. `approximate`
 * means "this address was never independently re-confirmed as a real
 * function entry" -- `hotPathDisabled` means the opposite (the address IS
 * confirmed real, by direct disassembly) but the hook is still off by
 * default because it's a demonstrated per-pixel/per-scanline hot path AND
 * its original live-capture purpose has since been fully resolved
 * statically, leaving nothing left for a live trace to answer. Currently
 * only `tlb_polypixel` sets this -- see its own citation below for the
 * full reasoning, and hookcore.h for the field's contract.
 *
 * notCallReachable (added 2026-08-15, root-causing the "stops mid-loop
 * under load, no shutdown message" failure that persisted across two real
 * XP-box captures -- `live_hooks_20260814-110254.jsonl` (clean shutdown)
 * and `live_hooks_20260814-112642.jsonl` (no shutdown message) -- even
 * AFTER the FlushFileBuffers-on-every-line fix): a THIRD, separate reason,
 * found by re-running `r2 -c 'aaa; af @ <va>; axt @ <va>'` against the
 * MD5/sha256-verified vendor DLLs fresh (PakonIMAu.dll sha256
 * 0ede8d9813af4ee95dddd85e5adc495a27f014a8fd4817cfbc3b3b1e107f511f per
 * reachability.py; TLA.dll md5 33f7a247d79286a31b192e83d3c37425 and TLB.dll
 * md5 193d9b2ce0a4b77ae9b78262bd06c0fc, both freshly extracted from the
 * SAME `research/sdk/PAKONF135.iso` this pass -- not independently cited
 * anywhere before this, but same verified ISO every other MD5 in this repo
 * traces back to). Five of the (non-approximate) addresses in this table
 * turned out to NOT be independently call-reachable function entries at
 * all: `af` analysis starting from the documented VA walked back to an
 * earlier, different, real function entry, and `axt` found only CODE-type
 * (jmp/jcc) cross-references from within that enclosing function, never a
 * CALL-type one. Hooking such an address with this engine's
 * calling-convention-agnostic return-address-swap technique (hookstub.S)
 * is unsafe for a reason distinct from both `approximate` (uncertain
 * citation) and `hotPathDisabled` (certain but too hot to be worth it):
 * the engine's one hard precondition -- "the DWORD at [esp] when a hooked
 * address is reached is always a real return address, because the only way
 * to reach it is via `call`" -- is simply false for these five. Reached via
 * an internal jmp/jcc instead, [esp] holds whatever real local variable or
 * spilled register the ACTUAL enclosing function happened to put there,
 * and this engine's entry stub corrupts it by overwriting it with
 * `OnReturnThunk`'s address. `sba_set_shifts_12` (see its own citation) has
 * DIRECT LIVE EVIDENCE of exactly this happening, 3 times across the two
 * new captures, every single time via the identical mechanism. Disabled by
 * default regardless of `approximate`/`hotPathDisabled` -- see
 * hookcore.h's own comment on this field for why re-enabling any of these
 * five specific VAs is never correct (unlike `approximate`, there is
 * nothing to "verify live" that would turn this back on; a genuinely new,
 * independently call-reachable address for the underlying subsystem would
 * need to be re-derived first). A SEPARATE, general engine-level guard
 * (`LooksLikeCodeAddress` in hookcore.c, checked before every
 * return-address swap) was added the same pass specifically so a hook NOT
 * yet known to have this problem -- including any of the 5 TLA.dll/PakonIMAu.dll
 * hooks below with zero resolvable r2 xrefs at all (`icc_effect_op`,
 * `tla_baddscene`'s siblings' own callers, etc. -- indirect/vtable calls
 * this static pass could not resolve either way) -- can't cause the same
 * corruption; per-address disabling below is the confirmed-bad list, not
 * the complete guarantee.
 */

#include "hookcore.h"

void HookCore_BuildRealTable(HookEngine *eng) {
    static void *thunks[HOOKCORE_MAX_HOOKS] = {
        (void *)&Thunk_00, (void *)&Thunk_01, (void *)&Thunk_02,
        (void *)&Thunk_03, (void *)&Thunk_04, (void *)&Thunk_05,
        (void *)&Thunk_06, (void *)&Thunk_07, (void *)&Thunk_08,
        (void *)&Thunk_09, (void *)&Thunk_10, (void *)&Thunk_11,
        (void *)&Thunk_12, (void *)&Thunk_13, (void *)&Thunk_14,
        (void *)&Thunk_15, (void *)&Thunk_16, (void *)&Thunk_17,
        (void *)&Thunk_18, (void *)&Thunk_19, (void *)&Thunk_20,
        (void *)&Thunk_21, (void *)&Thunk_22, (void *)&Thunk_23,
        (void *)&Thunk_24, (void *)&Thunk_25, (void *)&Thunk_26,
        (void *)&Thunk_27, (void *)&Thunk_28, (void *)&Thunk_29,
        (void *)&Thunk_30, (void *)&Thunk_31,
        /* v46: 32..39, alongside the HOOKCORE_MAX_HOOKS 32 -> 40 bump and
         * DEFTHUNK 32..39 in hookstub.S. See hookcore.h's comment on the
         * constant: 36 entries were being initialised into a 32-element
         * table[] and the last four hooks were silently dropped by the
         * compiler as "excess elements". table[] is unsized from this pass
         * on, with a compile-time assert against HOOKCORE_MAX_HOOKS, so that
         * class of silent truncation cannot recur. */
        (void *)&Thunk_32, (void *)&Thunk_33,
        (void *)&Thunk_34, (void *)&Thunk_35,
        (void *)&Thunk_36, (void *)&Thunk_37,
        (void *)&Thunk_38, (void *)&Thunk_39,
        (void *)&Thunk_40, (void *)&Thunk_41,
        (void *)&Thunk_42, (void *)&Thunk_43,
        (void *)&Thunk_44, (void *)&Thunk_45,
        (void *)&Thunk_46, (void *)&Thunk_47,
        /* Thunk_23 fixes a real, latent NULL-entryThunk bug left by the
         * prior commit (6d2e36a) that inserted analyze_scp_lut_balance
         * mid-array without adding a matching thunk -- see hookstub.S's
         * own comment on Thunk_23 for the full account. Thunk_24 is the
         * new slot for this pass's own addition, area_image_apply_lut,
         * appended at the END of table[] below specifically so no
         * existing entry's index (and therefore no existing entry's
         * thunk assignment) moves again.
         *
         * Thunk_25/26/27 (docs/74 §49, 2026-08-15): same append-only
         * discipline, for the three new TLB.dll lamp/AFE-gain/CCD-
         * acquire-control hooks (tlb_lamp_on, tlb_afe_gain_write,
         * tlb_ccd_acquire_control) added at the very end of table[]
         * below. HOOKCORE_MAX_HOOKS bumped 25->28 in hookcore.h and the
         * matching DEFTHUNK 25/26/27 added to hookstub.S in the SAME
         * commit -- double-checked specifically against the Thunk_23
         * mistake this file's own comment above documents.
         *
         * Thunk_29 (docs/74 §72.7, v21): same append-only discipline, for
         * the one new PakonIMAu.dll hook (sba_order_fpo_calc, 0x1028b8d0)
         * appended at the very end of table[] below. HOOKCORE_MAX_HOOKS
         * bumped 29->30 in hookcore.h, `extern void Thunk_29(void)` added
         * there too, and the matching DEFTHUNK 29 added to hookstub.S --
         * all in the SAME pass, re-checked against the same Thunk_23
         * mistake. */
    };

    /* UNSIZED, deliberately (v46). This was `table[HOOKCORE_MAX_HOOKS]`, and
     * when the v41-v45 work grew it to 36 entries against a constant of 32 the
     * compiler emitted four "excess elements in array initializer" WARNINGS
     * and dropped the last four hooks -- color_adjust_shift,
     * sba_order_fpo_calc, sba_order_fpo_helper, sba_vm_interp -- out of every
     * DLL built since. Sizing the array from its own initialiser makes the
     * table the source of truth; the static assert below turns "too many
     * hooks" into a build failure instead of a silent truncation, and
     * check_table_sync.py gained a matching count check in the same pass. */
    static const HookDef table[] = {
        /* ---- Frame / stage boundaries ---- */
        { "PakonIMAu.dll", 0x10069490, "cn_enhanced_driver",
          "AnsCnEnhancedPath per-scene analyze driver (fcn.10069490) -- "
          "the real call-order spine: analyzeFugc -> balanceAreaImage -> "
          "analyzeArea -> analyzeAttributes -> analyzeFalloff -> "
          "analyzeAutoTone -> analyzeSharpening -> ...",
          "docs/74 SS11 (call order), docs/62 line ~201-202", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x100fb730, "analyze_auto_tone",
          "ColorNegativePath::analyzeAutoTone -- the real 6-subsystem tone "
          "chain (cna/dra/toneHelper/contrast/ast/citras). Every subsystem "
          "individually Unicorn-verified bit-exact per docs/66; this "
          "boundary hook is for correlating a live call with the port's "
          "own real_auto_tone() on the same frame.",
          "docs/63, docs/65, docs/66, docs/74 (address repeated throughout)", 0, 1, 0, 0, 0 },

        /* ---- SBA / balance ---- */
        { "PakonIMAu.dll", 0x10100260, "sba_set_shifts",
          "ColorNegativePath::setShifts -- reads via getShifts, writes the "
          "3x int16 OUT balance-shift buffer this whole tone chain anchors "
          "to (the \"SBA neutral-balance output\" the task asks for). "
          "Re-confirmed 2026-08-15 as a genuine, independently call-reachable "
          "entry (r2 `axt` finds 3 real CALL xrefs, `af` resolves to its own "
          "address exactly) -- unlike sba_set_shifts_12 immediately below, "
          "which lives INSIDE this same function's body.",
          "tools/ansel/python-pipeline/pakon_sba_apply.py module docstring; "
          "r2 af/axt re-check 2026-08-15", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x10100a37, "sba_set_shifts_12",
          "setShifts real closed-form entry for the shipped CN control "
          "words (ntdChoice,ctdChoice)=(1,2) -- PATH_SET_SHIFTS_12. "
          "CONFIRMED 2026-08-15 NOT an independently call-reachable function: "
          "`r2 -c 'aaa; axt @ 0x10100a37' PakonIMAu.dll` finds exactly ONE "
          "xref in the whole binary -- `fcn.10100260 0x101008e1 [CODE:--x] "
          "jne 0x10100a37` -- a plain conditional jump FROM WITHIN "
          "sba_set_shifts's (0x10100260) own body, zero CALL-type xrefs "
          "anywhere. Live evidence this actually corrupts data: in BOTH new "
          "2026-08-14 captures, every single time this hook fires (3 times "
          "total, tid 3020/3452 in the clean run, tid 1556 in the crashed "
          "run), the PARENT sba_set_shifts call's own shadow-stack frame is "
          "permanently orphaned right afterward -- its \"leave\" event never "
          "gets logged, and (in 2 of 3 cases) that OS thread never logs "
          "another hook event again for the rest of the capture. This "
          "engine's return-address-swap technique assumes [esp] holds a real "
          "return address at every hooked VA; reached via an internal `jne` "
          "instead of `call`, [esp] instead holds whatever real local "
          "variable/spilled register setShifts's OWN code put there, which "
          "gets overwritten with OnReturnThunk's address -- live memory "
          "corruption inside setShifts's own stack frame. DISABLED BY "
          "DEFAULT (notCallReachable) -- there is no live verification that "
          "would make hooking THIS address safe; a genuinely separate, "
          "call-reachable entry for the (1,2) closed-form path (if one is "
          "ever needed) would have to be found some other way.",
          "pakon_sba_apply.py: PATH_SET_SHIFTS_12 = 0x10100A37; "
          "live_hooks_20260814-110254.jsonl call_id 21/51 (orphaned), "
          "live_hooks_20260814-112642.jsonl call_id 20 (orphaned); "
          "r2 af/axt 2026-08-15", 0, 1, 0, 1, 0 },
        { "PakonIMAu.dll", 0x10124000, "sba_get_shifts",
          "getShifts -- copies 3x int16 from *(AnsSbaCapability+0x10)+0x3a38.",
          "pakon_sba_apply.py module docstring", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x1028c780, "sba_preference",
          "Preference -- the ONLY confirmed writer of +0x3a38 (analyzePass2 "
          "@ 0x10216433 passes scene+0x3a30; fist-rounds 3x int16 into "
          "scene+0x3a38/+3a3a/+3a3c).",
          "pakon_sba_apply.py module docstring", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x1019a0c0, "sba_apply_balance_shifts",
          "AnsAreaCapabilityImpl::applyBalanceShifts -- the real PER-PIXEL "
          "LUT apply (builds three 4096-entry LUTs via 0x1006c4f0, applies "
          "clamp(i+shift,0,4095) to every pixel). This is the closest real "
          "analogue of pakon_sba_apply.apply_balance_shifts() -- the "
          "pixel-buffer stage to diff, not just the scalar shifts.",
          "pakon_sba_apply.py module docstring", 0, 1, 0, 0, 0 },

        /* ---- FUGC ---- */
        { "PakonIMAu.dll", 0x100fed00, "fugc_analyze",
          "analyzeFugc -- FUGC analyze entry point in the real per-scene driver.",
          "docs/62 line ~201", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x101f82c0, "fugc_set_lut_info",
          "setLutInfo -- builds the FUGC apply LUT from ebp14 (setShifts "
          "OUT @ +0x4b6) and ebp18 (SceneContext \"dmin\" bag). Confirmed "
          "real-DLL-verified including the near-identity offsets=(0,-1,1) "
          "case, docs/74 SS10.",
          "docs/66 line ~1839; docs/74 SS10", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x101fc518, "fugc_mode_dispatch",
          "FUGC analyze / mode dispatch: Cap+0x60e8 == 2 -> metrics path, "
          "else -> setLutInfo. Address has a trailing \"...\" in its own "
          "source citation (approximate, not independently re-confirmed "
          "this pass) -- verify the exact entry live before trusting it. "
          "r2 `axt` 2026-08-15 finds ZERO xrefs of any kind (neither CALL "
          "nor CODE) -- inconclusive (consistent with an indirect/vtable "
          "call this static pass can't resolve, but does NOT positively "
          "confirm this is a real entry either) -- stays approximate/off.",
          "pakon_ansel.py comment near fugc_mode field (~line 657-658); "
          "r2 axt 2026-08-15 (inconclusive)", 1, 1, 0, 0, 0 },

        /* ---- falloff / area / attributes ---- */
        { "PakonIMAu.dll", 0x100fe960, "analyze_falloff",
          "analyzeFalloff -- per-pixel radial lens/scanner vignetting "
          "correction. The \"falloff output\" hook the task asks for.",
          "docs/62 line ~201-202; docs/74 SS11", 0, 1, 0, 0, 0 },
                /* docs/74 §167.3/§168 -- ColorNegativePath::analyzePostBalance, the
         * REAL per-frame shift-LUT builder (balance_area_image only relays,
         * §167.3, and applied no LUT on any of the 39 frames).
         *
         * ENTRY PINNED THE HARD WAY. v41 hooked 0x100fe4f0, which decodes as
         * `add ch, bl` / `inc esp` -- mid-instruction. It produced zero dumps
         * and was unsafe (the trampoline would overwrite part of an
         * instruction). r2 resolves no function over that range even after
         * `aab`, so the entry was found by locating the DLL's own error
         * string 'ColorNegativePath::analyzePostBalance\n' at 0x10586b60 and
         * walking back from its earliest push site (0x100fdd7a) to the
         * enclosing SEH prologue:
         *
         *     fcn.100fdc40  size 3345, 142 bbs, spans 0x100FDC40..0x100FE951
         *
         * which contains BOTH known interior sites -- the builder call
         * 0x100fe807 (`call 0x1006c4f0`) and the apply 0x100fe875
         * (`call 0x100d9340`, retaddr 0x100fe87a).
         *
         * IT IS cdecl, NOT __thiscall: the prologue is `push -1; push
         * handler; mov eax, fs:[0]` then `sub esp, 0x1d8` and `xor edi, edi`
         * -- ecx is never stashed. So an EXTRA_DUMP_THIS_OFFSET row would
         * read a register that is not a scene pointer; that was a SECOND
         * independent defect in v41's row, beyond the wrong address.
         *
         * The function makes NO reference to +0x4b4..+0x4ba anywhere in its
         * body: the shift triple reaches it through a pointer
         * (`mov dx, word [eax]` at 0x100fe7e9, just before the builder call).
         * Since dumps fire at ENTRY only, that register cannot be read, so
         * both stack arguments are dumped instead and the triple is
         * identified offline by matching against the applied k -- which is
         * already known per frame from the r_lut/g_lut/b_lut rows. */
        /* docs/74 §175.4 -- Delta's source, via the one function that is
         * HANDED the post-rewrite shift as a plain stack argument.
         *
         * v44 dumped analyzePostBalance's two cdecl args: arg0 came back
         * constant and arg1, though it varies every call, does not contain the
         * applied k at any offset nor at any uniform difference from it. The
         * triple sits behind a pointer, and chasing that pointer through r2's
         * esp-relative slot naming is how the previous two rows went wrong
         * (0x100fe5b4's `lea ecx, [var_10h_3]` is a std::string, destructed at
         * 0x100fe5c4 -- r2 gives the same name to different slots).
         *
         * So hook the CONSUMER instead. At the builder call site:
         *
         *   0x100fe7d0  mov dx, word [eax + 4]     ; eax -> the triple
         *   0x100fe7d6  mov cx, word [eax + 2]
         *   0x100fe7e9  mov dx, word [eax]
         *   ... push edx / push ecx / push edx     ; the three shifts
         *   0x100fe7f6  push 0x1000                ; count
         *   ... push eax / push ecx / push edx     ; three out buffers
         *   0x100fe802  mov ecx, 0x106b5f74        ; master table (__thiscall)
         *   0x100fe807  call 0x1006c4f0
         *
         * giving at entry: stack_dwords[3] = 0x1000 (a self-check that the
         * convention is right) and stack_dwords[4..6] = the three POST-rewrite
         * shifts. No dump row is needed -- STACK_DWORDS_LOGGED already covers
         * them for every call.
         *
         * Paired against cn_shift_before (+0x4b6 at cn_enhanced_driver ENTRY),
         * this yields Delta per frame directly. This builder is already ported
         * bit-exact (pakon_sba_apply.shift_luts, SHIFT_LUTS_PORTED). */
        { "PakonIMAu.dll", 0x1006c4f0, "shift_lut_builder",
          "The vendor's shift-LUT builder, out[i] = master[i + shift] over "
          "the singleton at 0x106b5f74. Hooked for its ARGUMENTS: "
          "stack_dwords[4..6] are the three post-rewrite shifts, which is "
          "Delta's other half (docs/74 SS168, SS175.4).",
          "docs/74 SS167.5, SS168, SS175.4; r2 af+pdf 2026-08-20",
          0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x100fdc40, "analyze_post_balance",
          "ColorNegativePath::analyzePostBalance -- builds the per-frame "
          "shift LUTs via 0x1006c4f0 (bit-exact ported) and applies them "
          "via area_image_apply_lut. Entry pinned via the DLL's own error "
          "string; cdecl, not __thiscall (docs/74 SS167.3, SS168).",
          "docs/74 SS167.3, SS168; r2 af+pdf 2026-08-20", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x10102b20, "balance_area_image",
          "balanceAreaImage -- opens with find(\"area\") idempotency guard "
          "(a HIT throws; a MISS falls through -- docs/74 SS11 already "
          "ruled out the find(\"area\") HIT path as a live data-consumption "
          "channel, but never read the miss-path body itself).",
          "docs/74 SS11", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x100fd190, "analyze_scp_lut_balance",
          "ColorNegativePath::analyzeScpLutBalance -- the analyze-time "
          "path that casts to the same AnsSCPLutCapability type "
          "balanceAreaImage's miss-path composes with at apply time "
          "(docs/74 SS37/SS39). Added specifically to settle the one "
          "open question SS39 flagged: whether the [cast_result+0xc] "
          "gate controlling that whole compose block is actually "
          "non-zero on a real scan -- if this hook never fires, the "
          "SCPLut compose is dead on the real render path regardless "
          "of its data being confirmed correct.",
          "docs/74 SS37.4, SS39.2-39.3", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x100e16d0, "analyze_area",
          "analyzeArea entry (732-function capability, 0% ported). docs/74 "
          "SS11-12 calls the four unreplicated stages -- this one included -- "
          "\"the sole remaining concrete software lead\" after every other "
          "mechanism was checked against the real DLL and confirmed correct.",
          "docs/74 SS11, SS12, SS\"What this changes about the open item list\" item 1", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x100fb3d0, "analyze_attributes",
          "analyzeAttributes -- one of the four unreplicated stages between "
          "FUGC and autoTone, real call order per docs/74 SS11.",
          "docs/74 SS11", 0, 1, 0, 0, 0 },

        /* ---- ICC transform ---- */
        /* ---- SCPLut analyze worker (v36, docs/74 SS141) ---- */
        { "PakonIMAu.dll", 0x10287eb0, "scp_lut_worker",
          "AnsSCPLutCapabilityImpl analyze WORKER -- the last unported step between tone and ICC. docs/74 SS141: analyzeScpLutBalance 0x100fd190 -> Cap analyze 0x101226c0 -> Impl analyze 0x102128f0 -> 0x102127d0 -> THIS (1097 B, 292 instrs, 160 FP, cyclomatic 14). Its product is a per-channel out = slope*i - offset LUT (scp_lut_fill_channel, already ported), which is exactly the form PAKON_BLACK_WHITE applies by hand to move R's slope error 36.8%% -> 8.2%% (SS135.1). Its callees are both already ported (opponent 0x1028c4e0, ftol2 0x104ffe44) and there are no transcendental helpers, so it is a bounded port -- blocked only on real inputs: the Unicorn harness pakon_scp_worker_golden.py runs the real function but faults on null args, and no existing dump covers them.",
          "docs/74 SS139-SS141", 0, 1, 0, 0, 0 },

        { "PakonIMAu.dll", 0x102f8420, "icc_xform_apply",
          "ImaICCXForm::apply -- builds source/dest descriptors and calls "
          "SpEvaluate @ 0x102f884c (kodakcms.dll import thunk 0x10500338). "
          "The \"ICC transform input/output\" hook the task asks for. "
          "Re-confirmed 2026-08-15: r2 `axt` finds 2 real CALL xrefs "
          "(one from `method.ImaICCEffectOp.virtual_40`, matching "
          "icc_effect_op's own citation exactly) -- a genuine, "
          "independently call-reachable entry, not the source of the "
          "2026-08-14 icc_effect_op/icc_xform_apply capture stopping "
          "mid-loop (every logged enter/leave pair for this hook across "
          "both new captures is perfectly balanced, right up to the last "
          "line before each log goes silent).",
          "docs/62 SS12.4.2; r2 af/axt re-check 2026-08-15", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x1016ede0, "icc_effect_op",
          "ImaICCEffectOp -- wraps apply, passes this+0x118 (source max) / "
          "this+0x120 (dest max) at 0x1016ee84-0x1016eef8. The scale "
          "(4095 vs 32767 vs Go's x65535/4095) is explicitly UNRESOLVED "
          "in docs/62 SS12.4.2 -- a live capture of this+0x118/this+0x120 "
          "settles it directly. Re-confirmed 2026-08-15: real disassembly "
          "shows an ordinary SEH prologue then `mov esi, ecx` -- a genuine "
          "__thiscall entry (this-pointer in ECX, matching esi+0x118/+0x120 "
          "used throughout the rest of the function) -- r2's own direct-call "
          "analysis finds zero xrefs here, consistent with this being "
          "reached only via indirect/vtable dispatch (the C++ method-call "
          "shape this class's own name implies), which is a static-analysis "
          "coverage gap, NOT evidence of a notCallReachable problem the way "
          "sba_set_shifts_12/icc_effect_op_ctor showed -- live capture data "
          "backs this up directly: every icc_effect_op enter/leave pair "
          "logged across both new captures is cleanly balanced, no orphaned "
          "frames, unlike the confirmed-bad hooks below.",
          "docs/62 SS12.4.2; r2 af/pdf/axt re-check 2026-08-15", 0, 1, 0, 0, 0 },
        { "PakonIMAu.dll", 0x1016e680, "icc_effect_op_ctor",
          "ImaICCEffectOp ctor -- the only writer found (static analysis) "
          "for this+0x118, loading the hardcoded 32767.0 from 0x1058fac0. "
          "A live hit here with a DIFFERENT value would directly disprove "
          "the \"no later setter\" assumption docs/62 flags as unconfirmed. "
          "CONFIRMED 2026-08-15 NOT an independently call-reachable function: "
          "`af @ 0x1016e680` resolves to a containing function starting at "
          "0x1016e4d0 (spanning through 0x1016ea3d), and the ONLY xref to "
          "0x1016e680 anywhere is `fcn.1016e4d0 0x1016e677 [CODE:--x] je "
          "0x1016e680` -- a conditional jump that skips a vtable/destructor "
          "call (`call dword [edx+4]`) and lands directly at 0x1016e680, "
          "which is simply the next straight-line instruction "
          "(`fld qword [0x1058fac0]` -- literally the hardcoded 32767.0 this "
          "citation already names), not any function's entry. Never actually "
          "fired in either 2026-08-14 capture (0 calls logged), so this is a "
          "latent bug, not one with direct live-corruption evidence like "
          "sba_set_shifts_12 -- but the same corruption mechanism applies the "
          "first time this code path executes. DISABLED BY DEFAULT "
          "(notCallReachable).",
          "docs/62 SS12.4.2; r2 af/axt 2026-08-15", 0, 1, 0, 1, 0 },

        /* ---- F-235 / TLA / TLB dmin-remap chain ---- */
        { "TLA.dll", 0x1003f7db, "tla_baddscene",
          "bAddScene -- the REAL writer of FUGC's \"dmin\" SceneContext bag: "
          "FindDmin on the raw PRE-balance frame words, then TLB's F-135 "
          "ColNeg poly remap, stored as \"dmin\" and read back via "
          "getCnContext. This port's own stand-in "
          "(pakon_ansel.py render_scene, `ebp18` / `raw_dmin` block) is "
          "flagged in its own comment as producing values OUTSIDE the "
          "accept band on every real frame tested -- a real, confirmed, "
          "currently-not-the-206-code-defect wiring bug worth diffing live. "
          "SUSPECT as of 2026-08-15: `af @ 0x1003f7db` against a freshly "
          "extracted TLA.dll (md5 33f7a247d79286a31b192e83d3c37425, from the "
          "same research/sdk/PAKONF135.iso every other MD5 in this table "
          "traces to) resolves to a containing function starting at "
          "0x1003f720, not 0x1003f7db itself, and the real disassembly AT "
          "0x1003f7db (`mov dx, word [ebx+0x6cac]`) is not any recognizable "
          "function prologue (no push ebp/sub esp/SEH setup) -- it reads "
          "from `ebx` as if that register was already established by an "
          "earlier prologue, i.e. it looks like a mid-function continuation, "
          "matching the SAME pattern independently confirmed for "
          "sba_set_shifts_12 and icc_effect_op_ctor below. UNLIKE those two, "
          "this was never exercised in either 2026-08-14 capture (TLA.dll "
          "never finished loading in that window -- see README \"why only "
          "17/23 hooks installed\") so there is no live corruption evidence "
          "either way, and no CALL/CODE xref was found at all (TLA.dll's "
          "in-degree count for the containing function suggests at least one "
          "caller elsewhere, not yet traced down to confirm/refute this "
          "specific sub-address). Downgraded to notCallReachable out of "
          "caution rather than left enabled on inconclusive evidence -- "
          "this project's own rule is \"if unsure, say so honestly rather "
          "than guessing,\" and this address does not currently meet the bar "
          "this pass set for the other 12 confirmed-real PakonIMAu.dll "
          "entries above (an actual CALL xref, or `af` resolving to its own "
          "address).",
          "tools/ansel/python-pipeline/pakon_ansel.py comment ~line 900-932; "
          "docs/66 golden-fleet section corroborates the surrounding TLA "
          "AddScene ColNeg leaf shape (zeroing @ 0x1003f7eb, width=4 push "
          "@ 0x1003f85d); r2 af/pd re-check 2026-08-15 (suspect, not "
          "definitively confirmed either way -- TLA.dll never loaded live)", 0, 1, 0, 1, 0 },
        { "TLA.dll", 0x100064d0, "tla_colneg_planar_scan",
          "PIColorCorrectColNegPlanarScan -- F-235 stage-2 entry, shuffles "
          "5 args into the MMX kernel's 7 at 0x1001c470. "
          "CONFIRMED 2026-08-15 NOT an independently call-reachable "
          "function: `axt @ 0x100064d0` finds exactly one xref -- "
          "`CODE XREF from fcn.10006320 @ 0x10006486` -- a jmp/jcc from "
          "within a DIFFERENT, larger function, not a call. Never fired "
          "live (TLA.dll never finished loading in either 2026-08-14 "
          "capture). DISABLED BY DEFAULT (notCallReachable), same reasoning "
          "as sba_set_shifts_12/icc_effect_op_ctor above.",
          "docs/65 line ~93; docs/66 golden-fleet section; "
          "r2 af/axt 2026-08-15", 0, 1, 0, 1, 0 },
        { "TLA.dll", 0x1001c470, "tla_colneg_mmx_kernel",
          "The inner MMX kernel itself (pmulhw x3, independently-truncated "
          "products, THEN summed -- the exact bug docs/66's \"golden "
          "fleet\" section fixed on the port side, one code high). NOTE: "
          "if this fires per-scanline/per-pixel-block rather than once per "
          "frame, it may be high-frequency live -- see hooks.cfg to "
          "disable if a first run shows it's too hot. "
          "CONFIRMED 2026-08-15 NOT an independently call-reachable "
          "function: `af @ 0x1001c470` resolves to a containing function "
          "spanning 0x1001b160-0x1001dec6 (11622 bytes) -- 0x1001c470 is "
          "deep inside that function's body, not its own entry. Never "
          "fired live (TLA.dll never finished loading in either 2026-08-14 "
          "capture). DISABLED BY DEFAULT (notCallReachable) -- this also "
          "retires the earlier \"may be high-frequency, disable via "
          "hooks.cfg if needed\" concern moot: it's off by default now for "
          "a stronger reason than heat.",
          "docs/66 \"6.2 -- golden fleet, colneg_1px remap TLA\"; "
          "r2 af 2026-08-15", 0, 1, 0, 1, 0 },

        /* docs/74 §163 -- the per-pixel LUT applied to the plane IMMEDIATELY
         * before PolyPixel. fcn.10026c90's last call before
         * `call fcn.1000d880` is this, and its body (real af+pdf, 44 bytes,
         * 5 blocks) is a bare transfer loop:
         *     movzx edi, word [ecx]          ; uint16 source pixel
         *     mov   di,  word [esi + edi*4]  ; TABLE LOOKUP, stride 4
         *     mov   word [eax], di
         * i.e. out[i] = *(uint16 *)(table + in[i]*4), with the table arriving
         * as arg_14h -- which is why §163.1 found no such table anywhere in
         * either DLL's static data: it is built at runtime.
         *
         * §162/§164 established by measurement that the data reaching
         * PolyPixel is ALREADY POSITIVE (signed corr with the vendor's render
         * +0.92 on 38/38 frames vs -0.93 for the PSI export; skipping this
         * port's own invert takes the segment test 95.29 -> 33.33 MAE). So a
         * transform inverting the negative must run at or before this point,
         * and this is the only per-pixel transform there.
         *
         * §163.5 recovered its BEHAVIOUR from the captured output without the
         * table: attainable output values thin out at high values 2-7x beyond
         * the Poisson sampling expectation, so it is genuinely compressive --
         * but NOT a plain logarithm (exponential-gap fit R^2 0.48-0.58 pooled,
         * 0.087 per-frame), so its actual shape is unknown. This row captures
         * the table itself and settles it.
         *
         * arg_14h at entry = stack_dwords[5] (arg_4h is [0], so +0x14 is [5]).
         * 0x4000 = 4096 entries x 4-byte stride. */
        { "TLB.dll", 0x10022a60, "tlb_lut_apply",
          "The per-pixel transfer-LUT loop applied immediately before "
          "PolyPixel; out[i] = *(uint16 *)(table + in[i]*4). Candidate "
          "site of the F-135 inversion (docs/74 SS162-SS163).",
          "docs/74 SS162, SS163, SS163.5; r2 af+pdf 2026-08-20",
          0, 1, 0, 0, 0 },

        { "TLB.dll", 0x10034b9b, "tlb_f135_poly_remap",
          "F-135 ColNeg polynomial remap used by bAddScene to turn the raw "
          "FindDmin walk into \"dmin\". NOTE: this port's own comment cites "
          "it as \"TLB.dll fcn.1000d880 @ 0x10034b9b\" -- an r2 auto-name/VA "
          "pair that looks inconsistent (fcn.<addr> normally names a "
          "function BY its own entry address) with docs/65's separate "
          "citation of \"TLB.dll:fcn.1000d880\" for the general stage-2 3x10 "
          "polynomial (PolyPixel). Both addresses are hooked (this one and "
          "tlb_polypixel) precisely so a live capture can resolve which is "
          "which rather than guessing. RESOLVED 2026-08-15, statically, no "
          "live capture needed: 0x10034b9b is not a function at all -- it "
          "is the literal byte address of the `call fcn.1000d880` opcode "
          "(`e8 e0 8c fd ff`) inside a DIFFERENT function, fcn.10034a60 "
          "(`mov ecx, dword [0x10075554]; push edx; add ecx, 0x16f4; call "
          "fcn.1000d880` at exactly 0x10034b9b; `test eax,eax; jne "
          "0x10034bc4` immediately after). This fully resolves the naming "
          "ambiguity this hook existed to settle: `tlb_polypixel` "
          "(0x1000d880) is the one and only real PolyPixel function; "
          "0x10034b9b is simply a CALL SITE that invokes it. This is worse "
          "than the other notCallReachable entries in this table -- hooking "
          "it would plant a JMP over live CALL-instruction bytes inside "
          "fcn.10034a60, silently rewriting that function's own control "
          "flow the moment MinHook installs the hook, independent of "
          "whether the hook ever even fires. `approximate` is kept set "
          "(it really was never independently re-confirmed, and now we know "
          "definitively why it never should be) alongside the new "
          "notCallReachable=1 for a complete, honest record of both how "
          "this was originally flagged and what was actually found.",
          "pakon_ansel.py comment ~line 903-904; r2 af/pd/axt 2026-08-15 "
          "(definitively resolved: this VA is a call-instruction's own "
          "address, not a function)", 1, 1, 0, 1, 0 },
        { "TLB.dll", 0x1000d880, "tlb_polypixel",
          "PolyPixel -- general stage-2 3x10 quadratic polynomial. Address "
          "confirmed (not just implied) by a real af+pdf disassembly, "
          "docs/74 SS32.2: 845 bytes, switch-dispatched on filmClass "
          "(case 2 -> this+0xc8 PosMatrix, matching check_film_class's own "
          "citation exactly), a tight fild/fmul/faddp per-pixel loop over "
          "10 stored coefficients per channel, zero fyl2x/log-family FPU "
          "instructions anywhere in the function. That same pass also "
          "resolved the naming ambiguity this hook (and tlb_f135_poly_remap "
          "above) originally existed to settle live -- both addresses are "
          "PolyPixel-family, statically, with no live capture needed. "
          "RE-ENABLED 2026-08-16 (hotPathDisabled was 1) with a real "
          "live-data question restored: the v8 area_image_apply_lut "
          "capture now yields the vendor's actual RPD12, but there is no "
          "matching raw capture to fit ROM12 -> RPD12 against, so this "
          "hook's own g_extraDumps[] row (poly_input_r) captures the raw "
          "14-bit R plane PolyPixel reads (stack_dwords[1] = buffer base "
          "at call site fcn.10026c90 @ 0x100270a5; planar, in-place). "
          "Entry-only (wantExitDefault=0) because the per-pixel loop "
          "(iterates up to 512 word-pixels per call, 0x1000d8f2-0x1000dab0) "
          "makes exit-hooking this a demonstrated hot path; the entry "
          "buffer dump is what the analysis needs. If per-scanline call "
          "volume turns out too large for a full roll, reduce the "
          "poly_input_r numBytes in g_extraDumps[] (only the first call's "
          "entry dump is pure pre-poly raw anyway -- later calls are "
          "in-place-contaminated). The prologue itself was checked directly "
          "and is NOT the concern: `push -1; push <SEH handler>; mov "
          "eax,fs:[0]; push eax; mov fs:[0],esp; sub esp,0x48` is an "
          "entirely ordinary MSVC/SEH prologue, a standard, safe MinHook "
          "trampoline target. "
          "v46: wantExitDefault flipped 0 -> 1, on measurement rather than "
          "estimate. The paragraph above declined exit-hooking on a "
          "'demonstrated hot path' reading of the per-pixel loop -- but the "
          "loop is INTERNAL to the call, and the reference scan shows this "
          "function is entered only 77 times for the whole roll (~2 per "
          "frame), which is nothing. Exit-hooking it is what makes stage 2 "
          "testable at all: PolyPixel is IN-PLACE, so the entry dump and the "
          "exit dump of the SAME 0x84000 buffer are the polynomial's input "
          "and its output for the same pixels in the same layout. That also "
          "retires this entry's own caveat that 'only the first call's entry "
          "dump is pure pre-poly raw, later calls are in-place-contaminated' "
          "-- with the matched exit dump, a contaminated entry is no longer "
          "ambiguous, it is simply the input to whatever that call did.",
          "docs/74 SS32.2-32.3, SS32.7; call count from the v45-era reference "
          "scan", 0, 1, 0, 0, 0 },

        /* ---- AFE (device-side register write) ---- */
        { "TLB.dll", 0x100299c0, "tlb_afe_offset_write",
          "FN_bDrvPutCcdAtoDOffsets -- AD9826 offset register encoder "
          "(9-bit sign-magnitude; this port had a two's-complement bug "
          "here, fixed 2026-08-12, docs/72). This is the closest REAL, "
          "documented \"AFE\" hook available. NOTE: this is the OFFSET "
          "write, not GAIN -- no distinct address for a gain-register "
          "write function was found documented anywhere in docs/62-74. "
          "See README.md \"AFE gain -- honestly unresolved\". Re-confirmed "
          "2026-08-15: r2 `axt` finds 5 real CALL xrefs from 4 different "
          "functions -- a genuine, independently call-reachable entry, "
          "matching the clean/balanced enter+leave pairs this hook logged "
          "throughout both new 2026-08-14 captures.",
          "docs/72 SS1.3 (\"FN_bDrvPutCcdAtoDOffsets at 0x100299c0, "
          "[VERIFIED-FROM-BINARY]\"); r2 af/axt re-check 2026-08-15", 0, 1, 0, 0, 0 },

        /* ---- Area image per-pixel LUT apply (docs/74 SS46) ---- */
        { "PakonIMAu.dll", 0x100d9340, "area_image_apply_lut",
          "AnsImageData::applyLut -- self-named by 4 embedded strings in "
          "its own body (\"AnsImageData::applyLut\" @ 0x10584320, "
          "\"Images must have 3 bands.\" @ 0x10584338, \"Source and "
          "destination have different packing.\" @ 0x105842f0, \"Source "
          "and destination are different sizes.\" @ 0x105842c4; path "
          "\"\\Atc\\ansel\\src\\libStub.ansel\\AnsImageData.cpp\" @ "
          "0x10584274) -- THE genuine per-pixel write this doc's own "
          "priority list (docs/74 SS27.4/SS37.7/SS45) had been missing: "
          "a real nested width/height-bounded loop (outer row loop "
          "0x100d97f0-0x100d98be, inner column loop 0x100d9822-0x100d986b, "
          "both `dec reg; jne`-terminated against edi->+0xc/+0x10, the "
          "same width/height offsets pakon_fugc.FUGC_IMG_DESC_WIDTH_OFF/"
          "HEIGHT_OFF already document for this same AnsImageData-shaped "
          "descriptor layout) doing, per pixel per row: `movsx "
          "ebx,word[src+idx]; mov bx,word[lutBase+ebx*2]; mov "
          "word[dst+idx2],bx` for R, G, and B against three SEPARATE "
          "caller-supplied 4096-entry LUTs (0x100d9822/0x100d9837/"
          "0x100d9846) -- a genuine `[base+index*stride]`-shaped indexed "
          "LUT lookup AND indexed pixel write inside an image-bounded "
          "loop, not a struct-field or capability-object write (the "
          "shape every other function read in this neighbourhood turned "
          "out to have -- AnsFugcCapabilityImpl::applyLut/0x101fa5b0 in "
          "SS28 had zero indexed writes in 705 instructions; "
          "analyzeScpLutBalance/0x100fd190 in SS40 never wrote its own "
          "flag byte at all). Called (E8 exhaustive .text scan, this "
          "pass, 10 real static callers total) 4x from balanceAreaImage "
          "(0x10103561/0x1010386a/0x101038f7/0x10103965, ALL on the "
          "AREA capability's own real \"AREA analysis image\" object -- "
          "the exact this+0x1a4 field SS27.3 already read via "
          "fcn.100dc060, confirmed here to be var_34h at each of these "
          "4 call sites, with LUT triples from the shift+SCPLut-composed "
          "buffer SS37.4/SS38-40 already traced), once from "
          "sba_apply_balance_shifts/0x1019a274 (currently gated off per "
          "SS37.3, 0/12 real fires), once from analyzePostBalance "
          "(0x100fdc40, per docs/62 SS2.5's own citation of the scene "
          "order \"analyzePostBalance 0x100fdc40 -> analyzeFugc -> "
          "balanceAreaImage\"), and 3x from AnsDcPremiumPath's own "
          "vtable method_12 (0x1006fa90 range -- the CN-Premium path, "
          "not this doc's own CN-Enhanced negative path per docs/64). "
          "Independently corroborated by THREE pre-existing docs this "
          "investigation had not cross-referenced before this pass: "
          "docs/62 SS2.5 (\"balanceAreaImage composes filmLut_c . "
          "scpLut_c . shift_c . fugc_c and applies it through "
          "AnsImageData::applyLut 0x100d9340\"), docs/64 (\"They compose "
          "into the pixel buffer in balanceAreaImage\"), and "
          "docs/reports/autotone-scope-2026-08-10/{fugc,filmLut}.md "
          "(\"applied to image pixels via AnsImageData::applyLut "
          "0x100d9340 -- genuine per-channel density math\"). The "
          "STILL-open question those same earlier docs flag and this "
          "pass does not resolve (docs/58 SS16.5 as quoted in docs/62 "
          "SS2.5): whether this \"AREA analysis image\" aliases the "
          "shared scene buffer cna/dra actually read, or is a private "
          "analysis-only copy -- exactly what this live hook is for. "
          "approximate=0: afij (1,505 realsz/473 ninstrs/106 nbbs, "
          "single real exit ebbs=1, minaddr/maxaddr span matches the "
          "full af+pdf read exactly) plus this section's own E8 scan "
          "(10 real CALL xrefs, not a guess) both independently confirm "
          "a genuine, independently call-reachable function entry, the "
          "same standard SS37.2/SS39.2/SS40 already established. "
          "wantExitDefault=1, hotPathDisabled=0: called a small, bounded "
          "number of times PER FRAME externally (<=4 from "
          "balanceAreaImage, <=1 each from the other real call sites) "
          "-- its own internal per-pixel loop is opaque to the external "
          "call count, unlike tlb_polypixel (called roughly every 15-45 "
          "ticks, i.e. externally once per scanline-batch) -- so full "
          "entry+exit tracing at this call frequency is not the "
          "high-volume hot-path risk hotPathDisabled exists for.",
          "docs/74 SS46; docs/62 SS2.5; docs/64; docs/58 SS16.5 (quoted "
          "in docs/62); docs/reports/autotone-scope-2026-08-10/"
          "{fugc,filmLut}.md", 0, 1, 0, 0, 0 },

        /* ---- Lamp / AFE-gain / CCD-acquire-control (docs/74 SS49) ----
         * Three new TLB.dll entries covering the real lamp warm-up + CCD
         * dark-offset-calibration bring-up sequence docs/55 and docs/59
         * captured on the wire, extending the existing tlb_afe_offset_write
         * hook above (which only covers the AFE OFFSET register write) to
         * the other two real, independently call-reachable driver
         * functions in that same sequence. All three re-derived and
         * confirmed fresh this pass against the hash-verified TLB.dll
         * (md5 193d9b2ce0a4b77ae9b78262bd06c0fc, same file every other
         * TLB.dll citation in this table traces to, extracted from
         * research/sdk/PAKONF135.iso and independently re-hashed this
         * pass) via `r2 -e bin.baddr=0x10000000 -c 'aaa; af @ <va>; axt @
         * <va>; pdf @ <va>'` -- not carried over from agent.js (agent.js
         * gained the same three entries, appended, in this same pass). */
        { "TLB.dll", 0x1002c5f0, "tlb_lamp_on",
          "FN_bDrvLampOn -- the real lamp enable+duty-write function: one "
          "call writes light-board reg 0x80 (enable mask), 0x81 (5-byte "
          "LED levels [B,Ir,R,0,G]) and 0x82 (12-byte PWM on-count sextet "
          "+ period N), matching docs/59's captured steps 16-18/80-82/100/"
          "114 and docs/40 SS3/SS12's own static derivation of this exact "
          "address (`FN_bDrvLampOn = fcn.1002c5f0`). Re-confirmed fresh "
          "this pass, independent of docs/40's citation: `af @ 0x1002c5f0` "
          "resolves to itself (minaddr==maxaddr-2175==0x1002c5f0, "
          "num-instrs=656), `axt` finds 8 genuine CALL-type xrefs from 6 "
          "distinct caller functions (0x1001e7b0 x3, 0x1001ec90, "
          "0x10020dc0, 0x1002d5c0, 0x1002d7f0 -- FN_bBeforeScan per docs/59's "
          "own header note, 0x1002dbd0), zero CODE-type/internal-jump "
          "xrefs -- the same axt-based safety check that found the 5 "
          "notCallReachable entries above finds nothing wrong here. "
          "Prologue is an entirely ordinary MSVC frame: `push ebp; mov "
          "ebp,esp; and esp,0xfffffff8; sub esp,0x54` (stack realignment "
          "for the function's own FPU/double-precision locals, per the "
          "immediately-following `fld qword [0x10067008]` -- no relative "
          "jump/call anywhere near the bytes MinHook needs to relocate). "
          "This hook observes the SAME register writes docs/59's "
          "`tools/lamp_replay_vendor.py` sends deliberately from the host "
          "side -- it does not send anything itself, only logs entry/exit "
          "when PSI's own code calls this function during a real scan.",
          "docs/40 SS3 (\"FN_bDrvLampOn = fcn.1002c5f0\"), SS12 (write-order "
          "correction: 0x80 first, then 0x81, then 0x82); docs/59 (captured "
          "wire sequence this function produces); fresh r2 af/axt/pdf "
          "2026-08-15 against TLB.dll md5 193d9b2ce0a4b77ae9b78262bd06c0fc",
          0, 1, 0, 0, 0 },
        { "TLB.dll", 0x100298b0, "tlb_afe_gain_write",
          "The AFE GAIN register write function -- the address README.md's "
          "\"AFE gain -- honestly unresolved\" section asked for, found "
          "this pass. Self-naming string \"FN_bDrvPutCcdAtoDGains\" exists "
          "in this exact binary at 0x10063b4c (found via `izz~AtoD`, "
          "alongside \"FN_bDrvPutCcdAtoDOffsets\" at 0x10063b18 -- the "
          "already-hooked tlb_afe_offset_write's own name), confirming the "
          "vendor's own FN_bDrv... naming convention includes this "
          "function; the string itself is referenced only from the shared "
          "name-lookup/logging dispatcher (fcn.100170b0, a big "
          "switch-on-command-id table that also references "
          "\"FN_bDrvLampOn\"'s and \"FN_bDrvCcdAcquireControl\"'s own name "
          "strings the same indirect way), NOT from inside 0x100298b0's "
          "own body -- so the name<->address link here is by STRUCTURAL "
          "match, not a literal in-body self-reference, same standard "
          "already used to identify tlb_afe_offset_write in the first "
          "place. That structural match is exact: 0x100298b0 sits "
          "immediately before tlb_afe_offset_write (0x100299c0) in .text, "
          "same shape (in-degree 8, cyclomatic-complexity 13 vs the "
          "offset function's 19), and writes CCD board reg 0x84 with "
          "indices 2, 3, 4 (`push 2/push 0x84`, `push 3/push 0x84`, "
          "`push 4/push 0x84`, each followed by a call to the same "
          "cache-check helper fcn.1000a5d0 then the same PutRegisterWord "
          "primitive fcn.1001acd0 the offset function also calls) -- "
          "exactly docs/55's captured steps 19-21 (`0x44 0x84 idx 2/3/4 "
          "= gain R/G/B`, all value 0x000D=13), as opposed to the offset "
          "function's idx 5/6/7. `axt` finds 8 genuine CALL-type xrefs "
          "from 8 real call sites (0x1001e242, 0x1001ff3b, 0x1001ffaf, "
          "0x100208f9, 0x10020fd0, 0x1002120a, 0x100213a9, 0x1002df92), "
          "the same call-reachability bar tlb_afe_offset_write meets. "
          "Prologue: `push ebx; mov ebx,[esp+8]` -- exactly 5 bytes, no "
          "relative jump/call, a clean MinHook target.",
          "README.md \"AFE gain -- honestly unresolved\" (the search "
          "strategy this hook is the result of); docs/55 steps 19-21 "
          "(captured 0x44/0x84 idx2/3/4 gain writes this function "
          "produces); fresh r2 izz/af/axt/pdf 2026-08-15 against TLB.dll "
          "md5 193d9b2ce0a4b77ae9b78262bd06c0fc",
          0, 1, 0, 0, 0 },
        { "TLB.dll", 0x1002c340, "tlb_ccd_acquire_control",
          "The CCD acquire-on/off toggle function docs/40 SS11 names "
          "\"FN_bDrvCcdAcquireControl\" (\"sets bit 0 of CCD register "
          "0x82\"), matching docs/55's captured steps 2/18/35/40/43 (board "
          "0x44 reg 0x82 idx 0: mask 0x0060 vs acquire-on 0x0061). LOWER "
          "CONFIDENCE ON THE NAME SPECIFICALLY than the other two new "
          "entries above: the self-naming string \"FN_bDrvCcdAcquireControl\" "
          "(0x10064220, found via the same `izz~bDrv` scan) is, like the "
          "other FN_bDrv* strings, referenced only from the shared "
          "name-lookup dispatcher fcn.100170b0 -- never from inside "
          "0x1002c340's own body -- so this address is identified by "
          "BEHAVIOR AND POSITION, not a direct citation: it validates "
          "exactly the CCD acquisition-window parameters this role "
          "implies (four embedded assert-message strings at 0x10066f38, "
          "0x10066efc, 0x10066e58, 0x10066e08, 0x10066ddc name "
          "`uiCcdPixelHeight`, `uiCcdPixelOffset`, `uiCalibrationOffset`, "
          "`uiCcdIntegrationTime` by name), then calls "
          "fcn.10029770 -- a small (149-byte, in-degree 4, real CALL "
          "xrefs only) shared primitive that merges a caller-supplied "
          "value into a cached word at [this+0x358] and writes it to reg "
          "0x82 idx 0 via the same fcn.1001acd0 PutRegisterWord primitive "
          "the gain/offset functions use -- TWICE, at 0x1002c4c3 and "
          "0x1002c518, consistent with one call setting the mask "
          "(0x0060-shaped base) and a later one toggling the acquire bit "
          "(0x0061). This function's own address range (0x1002c340-"
          "0x1002c5f0) ends EXACTLY where tlb_lamp_on/FN_bDrvLampOn "
          "begins -- the two are adjacent in the same translation unit, "
          "consistent with docs/40's own description of these as "
          "sibling FN_bDrv... driver functions. `axt` finds 8 genuine "
          "CALL-type xrefs from 6 distinct callers (0x1001fe10 x3, "
          "0x10020590, 0x10020dc0 x2, 0x1002d5c0, 0x1002dbd0 -- three of "
          "which, 0x1001fe10/0x10020dc0/0x1002dbd0, are also callers of "
          "tlb_lamp_on, i.e. the real driver dispatch layer calls both "
          "from the same handful of higher-level functions), zero "
          "CODE-type xrefs. Prologue: `push ecx; mov eax,[esp+0x1c]` -- "
          "exactly 5 bytes, no relative jump/call, a clean MinHook "
          "target. This is a real, confirmed, independently "
          "call-reachable entry by every mechanical test this project's "
          "own axt-based safety check applies -- flagged as "
          "behavior-inferred rather than address-cited only so a future "
          "reader knows the difference from tlb_lamp_on's docs/40-cited "
          "address above.",
           "docs/40 SS11 (\"FN_bDrvCcdAcquireControl sets bit 0 of CCD "
           "register 0x82\"); docs/55 steps 2/18/35/40/43 (captured "
           "0x44/0x82 idx0 mask/acquire writes this function produces); "
           "fresh r2 izz/af/axt/pdf 2026-08-15 against TLB.dll md5 "
           "193d9b2ce0a4b77ae9b78262bd06c0fc",
           0, 1, 0, 0, 0 },

        /* ---- AnsColorAdjustCapability density-adjust shift (docs/74 SS57) ---- */
        { "PakonIMAu.dll", 0x101b76d0, "color_adjust_shift",
          "The analyzePostBalance shift leaf (fcn.101b76d0, 282 B) -- "
          "computes the three int16 post-balance shifts as "
          "out_c = round((in_c - mean(in)) * M_c + S1*S2 + dmin_c), "
          "Unicorn-verified bit-exact (pakon_postbalance_golden.py). "
          "thiscall: ecx = AnsColorAdjustCapabilityImpl (the Impl at "
          "Cap+0x10); the Impl fields are M/S1/S2/dens/dmin at +0xc..+0x30 "
          "(M and S1 are ctor args defaulting 25/25/25/75; dens/S2/dmin are "
          "zeroed at construction -- their non-zero writer is the still-open "
          "question this hook exists to answer). Prologue "
          "`push ecx; push esi; mov esi,ecx` (5 B, no rel jmp/call) is a "
          "clean MinHook target; reached via two real CALL sites "
          "(fcn.100f13a0 @ 0x100f13c1, and fcn.101b7e90 @ 0x101b80ad), "
          "so notCallReachable=0. Entry-only (wantExitDefault=0): the OUT "
          "shifts are already covered by the verified formula; the unknown "
          "is the Impl field VALUES, captured by the impl_fields extra dump.",
          "docs/74 SS57; tools/ansel/python-pipeline/"
          "pakon_postbalance_golden.py", 0, 0, 0, 0, 0 },

        /* ---- Per-frame orderFpo candidate (docs/74 SS66/SS72, v21) ---- */
        { "PakonIMAu.dll", 0x1028b8d0, "sba_order_fpo_calc",
          "The function SS66 named as the per-frame orderFpo (scene+0x38a2) "
          "writer -- 2958 B, 13 cdecl args (callers clean up add esp,0x34), "
          "8 helper subroutines, called 5x per frame. SS72's full-body read "
          "found its own TOP-LEVEL code does NOT write the orderFpo Y/U/V "
          "triple (pref_data+0x0/+0x2/+0x4) on the case that provably fires "
          "live (switch selector arg 3 == 0 at both real call sites): it "
          "writes exactly ONE unrelated word at pref_data+0x3e, derived from "
          "two other already-present pref_data fields. Whether one of the 8 "
          "unread helpers is the real orderFpo writer -- with pref_data "
          "threaded in as a hidden argument -- is exactly what this hook "
          "exists to settle empirically. "
          "SAFETY (audited 2026-08-17, the same af+axt pass this table's own "
          "header describes): `axt` finds FIVE real CALL-type xrefs "
          "(fcn.102159c0 @ 0x10215d6a/0x10215fae/0x1021605b = "
          "AnsSbaCapabilityImpl::analyzePass2, and fcn.10218110 @ "
          "0x1021937b/0x102196a9) and ZERO CODE-type jmp/jcc entries, and "
          "`af` resolves to 0x1028b8d0 itself (its own entry, not a "
          "containing function) -- so the engine's return-address-swap "
          "precondition genuinely holds here, unlike the notCallReachable "
          "entries above. Prologue `mov eax,[esp+0xc]` (4 B) + "
          "`sub esp,0x2c0` (6 B) is position-independent with no rel32 "
          "jmp/call in the first 5 bytes, so it is a clean MinHook "
          "relocation target. notCallReachable=0, entry-only "
          "(wantExitDefault=0): the before/after question SS72.7 poses is "
          "answered by consecutive ENTRY dumps (see g_extraDumps below), so "
          "no exit hook is needed and none is taken.",
          "docs/74 SS66, SS72 (esp. SS72.2 arg table, SS72.3 case-0 read, "
          "SS72.7 capture spec); r2 af/axt safety audit 2026-08-17", 0, 0, 0, 0, 0 },

        /* ---- orderFpo chroma helper (docs/74 SS76, v24) ---- */
        { "PakonIMAu.dll", 0x1028ae00, "sba_order_fpo_helper",
          "fcn.1028ae00 (1897 B, 15 cdecl args) -- the helper 0x1028b8d0 "
          "calls at 0x1028c023 to compute the chroma residual that becomes "
          "the orderFpo U/V terms. SS76 derived the U/V arithmetic in full "
          "(a weighted mean over 864 dens samples, 50x83 int8 weight table, "
          "round-half-away-from-zero divide) and needs no emulation of it -- "
          "but could NOT statically derive the Y term, an int32 read from a "
          "stack slot (L[-0x200]) that nothing in 0x1028b8d0's own 912 "
          "instructions ever writes. SS76 traced it to this function's own "
          "arg 9. Hooking here captures that dword directly: the engine "
          "already logs the first 16 raw stack dwords on every entry, and "
          "this function's 15 args all fall inside that window, so arg 9 is "
          "captured with NO extra dump row at all -- and the same line "
          "cross-checks SS76's whole 15-arg reconstruction for free. "
          "SAFETY (r2 af+axt 2026-08-17, this table's own standard): exactly "
          "ONE real CALL-type xref (fcn.1028b8d0 @ 0x1028c023) and zero "
          "CODE-type jmp/jcc entries; `af` resolves to 0x1028ae00 itself, "
          "its own entry, not a containing function. Prologue "
          "`sub esp,0x5c` (3 B) + `movsx eax, word [esp+0x70]` (5 B) is "
          "position-independent with no rel32 in the first 5 bytes -- a "
          "clean MinHook relocation target. Entry-only (wantExitDefault=0): "
          "the wanted value is an INPUT argument, so the return adds "
          "nothing.",
          "docs/74 SS76 (U/V derivation, and Y's L[-0x200] traced to this "
          "function's arg 9); r2 af/axt safety audit 2026-08-17", 0, 0, 0, 0, 0 },

        /* ---- the bytecode interpreter (docs/74 SS78.2/SS86, v26) ---- */
        { "PakonIMAu.dll", 0x102aadf0, "sba_vm_interp",
          "fcn.102aadf0 (4423 B) -- the BYTECODE INTERPRETER SS78.2 found "
          "standing between a captured Y term and a computable one. Program "
          "pointer at [arg2+4], 16-bit opcodes, 0xff halt, two-stage dispatch "
          "(movzx from the 254-byte index table at 0x102ac018, then jmp "
          "through the table at 0x102abf4c). Static scoping (SS86): 254 "
          "opcodes collapse to 51 handler indices, and index 50 alone covers "
          "203 opcodes (the default/invalid case) -- so there are 50 real "
          "handlers, not 254. "
          "WHY THIS CAPTURE: dumping the PROGRAM rather than logging each "
          "dispatch answers both open questions offline and costs one dump "
          "per call instead of thousands of log lines. Comparing the program "
          "bytes across frames and across scans settles static-vs-generated; "
          "walking those bytes against the index table gives the exact set of "
          "opcodes this path actually uses, which is the number that decides "
          "whether porting the VM is a bounded job. "
          "SAFETY (r2 af+axt 2026-08-17, this table's own standard): exactly "
          "ONE real CALL-type xref (fcn.102ac140 @ 0x102ac15a), zero "
          "CODE-type jmp/jcc entries, and `af` resolves to 0x102aadf0 itself. "
          "Prologue `sub esp,0x2c` (3 B) + `push ebx` (1 B) + `push ebp` "
          "(1 B) is exactly 5 position-independent bytes with no rel32 -- a "
          "clean MinHook relocation target. Entry-only (wantExitDefault=0): "
          "the program and its context are inputs, so the return adds "
          "nothing. "
          "v46: NOW hotPathDisabled=1, for two reasons that only became "
          "visible together. (1) VOLUME, MEASURED: this hook fires 185,329 "
          "times in one reference scan -- more than every other hook in this "
          "table combined -- and carries eight dump rows totalling 8,448 "
          "bytes per call, i.e. ~1.5 GB of dumps and ~90 MB of bare enter "
          "lines. Nothing else in a capture survives that. (2) ITS QUESTION "
          "IS ANSWERED: docs/74 SS88 ported the interpreter and located L "
          "(vars[133], record 156) from the v27 captures; the program bytes "
          "are the same on every call, so 185,329 copies of them buy nothing "
          "a handful would not. NOTE this hook was NOT actually running in "
          "any DLL built between the v41 and v45 passes -- it is one of the "
          "four entries the HOOKCORE_MAX_HOOKS=32 truncation silently "
          "discarded (see hookcore.h) -- so turning it back on by fixing that "
          "bug would have re-introduced the volume without anyone deciding "
          "to. Re-enable from hooks.cfg like any other hook; its rows carry "
          "maxDumps caps so doing so is now survivable.",
          "docs/74 SS78.2 (interpreter identified), SS86 (static scoping: 50 "
          "real handlers), SS88 (ported; question closed); r2 af/axt safety "
          "audit 2026-08-17; call count from the v45-era reference scan",
          0, 0, 1, 0, 0 },

        /* ---- v46: TLB.dll FRAMING cascade -- ALL THREE RE-DERIVED ----
         *
         * HISTORY, because the correction matters more than the result. The
         * pass that first wrote these three rows shipped them approximate=1
         * on two stated premises, and BOTH WERE FALSE:
         *
         * (1) "TLB.dll is not on this machine." It is, and always was, at
         * /tmp/pakon_re/TLB.dll -- which is precisely the scratch directory
         * CLAUDE.md designates for RE work, and the FIRST of the two paths
         * pakon_framing_golden.py's own DEFAULT_DLL_CANDIDATES already
         * searches. md5 193d9b2ce0a4b77ae9b78262bd06c0fc, matching the hash
         * that harness expects. The `find` behind the claim was scoped to
         * the repo, and `mdfind` does not index /tmp. The lesson is the one
         * docs/74 SS178.1 already drew about the truncated capture: an
         * absence of evidence has to be verified as carefully as a presence,
         * and "I could not find X" is a claim about the search, not about X.
         *
         * (2) "The `or` sites span a range containing 0x100072c0, so the
         * entry may be interior to fcn.10006e70." Resolved by reading it:
         * fcn.10006e70 is 0x10006e70-0x100072b5 and fcn.100072c0 is
         * 0x100072c0-0x100079b1. They are ADJACENT, with 11 bytes of
         * padding, not nested. Three of the four `or` sites (0x1000708b,
         * 0x10007193, 0x1000729f) are inside the driver; the fourth
         * (0x10007d35) is in fcn.100079c0, the outer caller. Nothing spans
         * anything. The feared repeat of `sba_set_shifts_12` / v41's
         * 0x100fe4f0 is not present here.
         *
         * All three are now approximate=0, each row citing its own `afi`
         * extents and its prologue's patch safety. The dump sizes were
         * checked rather than assumed: the highest this-relative offset the
         * entry touches is esi+0x6cbc, ending at 0x6cbf, so 0x6CC0 is exact.
         *
         * tlb_framing_line_reduce stays OFF by default via hotPathDisabled,
         * for its per-line log volume ALONE -- see its citation; that is a
         * cost decision, and the only one of the three that is. */
        { "TLB.dll", 0x100072c0, "tlb_framing_entry",
          "Framing entry point, per ROLL -- the caller of the five-stage "
          "cascade (LookForNicePictures 0x10006930, FramingLookInBetweenEnds "
          "0x100063d0, LookAtEnd 0x10006ae0, LookAtBeginning 0x10006ca0, "
          "FramingBlindlyPlacePictures 0x10006720) and the owner of the "
          "threshold search that re-binarises and re-runs the run extractor, "
          "stepping +-2 between 25 and 256 until the bins settle. That search "
          "is read but not ported. CONFIRMED real function entry.",
          "framing pass 2026-08-21 (xref from TLB.dll's own log strings at "
          "file offsets 0x5b890/0x5b8b8/0x5b8d4/0x5b8ec/0x5b944, warning "
          "codes confirmed against machine code). RE-DERIVED 2026-08-21 "
          "against TLB.dll md5 193d9b2ce0a4b77ae9b78262bd06c0fc (r2 `af`+"
          "`afi`): fcn.100072c0, 1777 bytes, 0x100072c0-0x100079b1 -- a real "
          "boundary, NOT interior to fcn.10006e70, which ends at 0x100072b5 "
          "(11 bytes of padding between them). Prologue is a single 6-byte "
          "`sub esp, 0x44c`, so MinHook's 5-byte patch cannot split an "
          "instruction, and `axt` finds no jump target at +1..+4. __thiscall "
          "(`mov esi, ecx` @ 0x100072d0), so EXTRA_DUMP_THIS_OFFSET is the "
          "right dump kind. Highest this-relative offset touched is "
          "esi+0x6cbc, whose last byte is 0x6cbf -- so the 0x6CC0 dump size "
          "is exactly right and not a guess",
          0, 1, 0, 0, 0 },
        { "TLB.dll", 0x10006e70, "tlb_framing_driver",
          "Framing cascade driver, per ROLL. Sets the cascade's warning bits "
          "(or eax,0x100 @ 0x1000708b; or eax,0x200 @ 0x10007193; "
          "or [ebp+0x6ca8],0x400 @ 0x1000729f; or edi,0x800 @ 0x10007d35). "
          "The [ebp+0x6ca8] site is the only structural fact available about "
          "the framing object without the DLL in hand -- it is at least "
          "0x6cac bytes, and the per-line trace starts at +0x6c, so one "
          "0x6CC0 dump from the base covers the trace array, the warning "
          "word and the threshold-search state without assuming where any of "
          "them begins. ENTRY+EXIT: at entry the trace does not exist yet, "
          "at exit it does and the warning bits are set. CONFIRMED.",
          "framing pass 2026-08-21. RE-DERIVED 2026-08-21 against TLB.dll "
          "md5 193d9b2ce0a4b77ae9b78262bd06c0fc: fcn.10006e70, 1093 bytes, "
          "0x10006e70-0x100072b5, a real boundary, called from fcn.100072c0 "
          "@ 0x100078d9. Prologue `sub esp,0x1c` + `mov eax,[0x1007554c]` = "
          "8 bytes before any branch, so the 5-byte patch is safe. Three of "
          "the four warning `or` sites are INSIDE this function "
          "(0x1000708b, 0x10007193, 0x1000729f); the fourth (0x10007d35) is "
          "in fcn.100079c0, the outer caller -- they do not 'span' "
          "0x100072c0 in any sense that implies nesting. 0x1000729f "
          "disassembles to exactly `or dword [ebp + 0x6ca8], 0x400`, "
          "confirming the offset the 0x6CC0 dump size was chosen to cover",
          0, 1, 0, 0, 0 },
        { "TLB.dll", 0x10006870, "tlb_framing_line_reduce",
          "Per-LINE reduction -- reads three bytes per line from this+0x6c "
          "and returns 255 - (r+g+b)/3, i.e. 8-bit and INVERTED. This is the "
          "domain gap that makes the ported framing cascade untestable "
          "today: this port's cascade runs on float 14-bit non-inverted "
          "data, so the two are not comparable until the vendor's own array "
          "is seen. Hooked as the CONSUMER on purpose -- extra dumps fire on "
          "entry, and at this function's entry the array is already filled, "
          "whereas at the driver's entry it does not exist yet. PER-LINE and "
          "therefore genuinely hot: entry-only (wantExitDefault=0) and its "
          "dump row is capped at 6, but note that even with no dumps at all "
          "each call still costs one enter line, so a roll with ~9,000 lines "
          "and a re-running threshold search will add tens of MB of plain "
          "log. Budget for that before enabling it. CONFIRMED address, but "
          "OFF BY DEFAULT ON COST alone (hotPathDisabled), not on doubt. "
          "*** MEASURED 2026-08-21: THE COST WARNING ABOVE IS WRONG. On a "
          "real 6-frame scan this fired exactly ONCE, not once per line -- "
          "the whole capture was 283 KB, not the 'tens of MB' predicted. It "
          "loops over the lines INTERNALLY rather than being called per line, "
          "so it is not a hot path at all and hotPathDisabled is no longer "
          "justified by cost. Left off by default only because flipping a "
          "shipped default is a separate decision; enable it in hooks.cfg "
          "without budgeting for volume. ***",
          "framing pass 2026-08-21. RE-DERIVED 2026-08-21 against TLB.dll "
          "md5 193d9b2ce0a4b77ae9b78262bd06c0fc: fcn.10006870, 181 bytes, "
          "0x10006870-0x10006925, a real boundary, called from fcn.100072c0 "
          "@ 0x100073b3 -- so all three framing hooks are one call tree "
          "rooted at the entry. Prologue is push ebx/ebp/esi, three "
          "single-byte pushes that relocate trivially. NOTE this row is the "
          "one case where hotPathDisabled is set for VOLUME rather than "
          "because static disassembly already answered the question: it has "
          "NOT -- capturing the vendor's own 8-bit inverted line array is "
          "exactly the measurement the framing domain gap still needs",
          0, 0, 1, 0, 0 },

        /* ---- v47: the SBA statistics ENGINE, for PROVENANCE ----
         *
         * docs/74 SS192/SS196. fcn.102aece0 is the per-sample statistics engine
         * that produces every variable term of the per-frame orderFpo triple:
         * the 864-byte selection mask at obj+0xc20 feeds U and V, and the
         * 720-slot vector at obj+0x3c is the p-code VM's in[], which
         * reproduces L. Its tail callee fcn.102b7440 writes the vector, and
         * both are now ported -- the mask bit-exact over 63,936 bytes, the
         * packer over 24,771 dwords.
         *
         * WHY THIS HOOK EXISTS: both of those ports are tier 1 for
         * EQUIVALENCE and tier 4 for PROVENANCE. No capture in the tree hooks
         * either function, so their inputs are synthetic. That settles "does
         * this arithmetic match" and does NOT settle "are these the values a
         * real frame produces" -- and B1 is precisely a question about real
         * per-frame values. This row is what converts it.
         *
         * The caller sba_order_fpo_calc (0x1028b8d0) is already hooked, but it
         * is the CALLER: docs/74 SS192.1 corrected an earlier reading that
         * named it the producer. It is 2,958 B; this is 24,516 B.
         *
         * ONE entry+exit pair on the object covers everything, because
         * fcn.102b7440 writes into the SAME object before this function
         * returns. Measured written extents are +0x6..+0x1c, +0x3c..+0xb7c
         * and +0xc20..+0xf80, so a 0x1000 dump from the base covers all three
         * with nothing assumed about where any of them starts. The ENTRY side
         * is not redundant: SS196 confirmed the cross-call read of [obj+0x7b8]
         * (vector slot 479) at 0x102b0da5 is LIVE, reached from the
         * 0x102b0e75 arm, so a later invocation consumes what an earlier one
         * wrote and only an entry dump shows what it read.
         *
         * Safety: prologue is a single 6-byte `sub esp, 0xfac`, so MinHook's
         * 5-byte patch cannot split an instruction, and `axt` finds no jump
         * target at +1..+4. Re-derived 2026-08-21 against PakonIMAu.dll md5
         * eea9dcf78ee21d4f7c515a6c2512242d.
         *
         * Called three times per frame from 0x1028b8d0, so caps are per-row
         * and modest -- 6 frames' worth. */
        { "PakonIMAu.dll", 0x102aece0, "sba_measure",
          "The per-sample SBA statistics engine (24,516 B, one function, four "
          "rets sharing one 0xfac frame). Reads a 24x36x6 sample grid; writes "
          "the 864-byte selection mask at obj+0xc20, ten header words, and -- "
          "via its pure tail callee fcn.102b7440 at 0x102b4c5e -- the whole "
          "720-slot int32 statistics vector at obj+0x3c. Hooked ENTRY+EXIT on "
          "the object: entry captures what the cross-call read at 0x102b0da5 "
          "sees, exit captures the mask, the vector and the headers together. "
          "This is the provenance B1's ports do not have.",
          "docs/74 SS192 (mapped, three corrections to SS76.6), SS196 (executed "
          "as one function under Unicorn, 74/74 cases to the success exit "
          "0x102b4c93, mask bit-exact 63,936/63,936 bytes). Address and "
          "prologue re-derived 2026-08-21 vs md5 "
          "eea9dcf78ee21d4f7c515a6c2512242d: fcn.102aece0, "
          "0x102aece0-0x102b4ca4, single 6-byte `sub esp,0xfac` prologue, no "
          "jump target in the patched bytes",
          0, 1, 0, 0, 0 },

        /* ---- v53: the framing 14->8-bit derivation SOURCE ----
         *
         * docs/74 SS194. FRAMING_PORTED is False for exactly one reason: the
         * ported cascade consumes the object's 8-bit per-line RGB summary at
         * this+0x6c (already captured as `framing_lines`), but this port holds
         * float 14-bit non-inverted data, and the 14->8 quantisation the vendor
         * applies is unknown. Deriving that map needs BOTH the 16-bit CCD source
         * AND the finished 8-bit summary from the SAME real frame; the per-line
         * value-writer itself is on an unhookable DMA path (prior RE), so the
         * plan is to capture (16-bit source image + 8-bit summary + geometry)
         * and derive the map offline.
         *
         * fcn.10004f00 is the framing object's allocator/geometry site
         * (__thiscall, ecx = the object). It computes count = total_lines /
         * line_scale (e.g. 19096/8 = 2387) and stores the three pointers this
         * capture turns on: +0x60 (a POINTER to a row-pointer table; the
         * contiguous 16-bit CCD base is table[0], a DOUBLE deref), +0x64 (size),
         * +0x6c (the 8-bit summary). One entry+exit pair here records the object
         * header after those stores; the two new +0x60 dump rows on
         * tlb_framing_line_reduce read the 16-bit image and the row table.
         *
         * OFF BY DEFAULT: hotPathDisabled is set to make this OPT-IN via
         * hooks.cfg (the framing capture is its own one-more-scan campaign),
         * NOT because it is a hot path -- it is an allocator, called at setup,
         * not per line. This is the same use of the flag as
         * tlb_framing_line_reduce (see its citation): an honest "off by default
         * on the enable-lever we have", not a claim about volume.
         *
         * EVIDENCE TIER: this address and the +0x60/+0x64/+0x6c layout are TIER
         * 3 (static disassembly / mapping) from the prior RE agent, NOT yet
         * confirmed against live hardware -- confirming it is precisely what
         * this hook exists to do. If ecx is not the framing object, or the
         * double-deref does not resolve, the rows come back readable=false,
         * which is itself the finding (same philosophy as the other framing
         * rows). Prologue safety: first instruction is `mov eax, fs:[0]`
         * (6 bytes >= 5), so MinHook's 5-byte patch cannot split it
         * (approximate=0). */
        { "TLB.dll", 0x10004f00, "tlb_framing_setup",
          "Framing object allocator + geometry (__thiscall, ecx = object). "
          "Computes count = total_lines / line_scale (e.g. 19096/8 = 2387) and "
          "stores the framing +0x6c 8-bit per-line RGB summary pointer, the "
          "+0x60 row-pointer table pointer (whose table[0] is the contiguous "
          "16-bit CCD image base -- a DOUBLE deref) and the +0x64 size. Hooked "
          "ENTRY+EXIT on the object so the exit dump records those pointer bases "
          "and the geometry after they are set; paired with the +0x60 CCD-image "
          "and row-table dumps on tlb_framing_line_reduce, this captures the "
          "16-bit source + 8-bit summary + geometry of ONE real frame so the "
          "vendor's 14->8 framing quantisation can be derived offline and "
          "FRAMING_PORTED closed (docs/74 SS194). OFF BY DEFAULT (opt-in via "
          "hooks.cfg); NOT confirmed against live hardware yet -- that is what "
          "this capture is for.",
          "RE 2026-08-22, /tmp/pakon_re/framewriter/ (prior static-RE agent), "
          "TLB.dll md5 193d9b2ce0a4b77ae9b78262bd06c0fc: fcn.10004f00 "
          "(__thiscall, ecx=object) sets +0x60/+0x64/+0x6c; store to [esi+0x6c] "
          "@ 0x100051b2. Prologue first insn `mov eax, fs:[0]` is 6 bytes "
          "(>= 5), so a MinHook 5-byte patch is safe (approximate=0). TIER 3 "
          "(static mapping), NOT yet live-confirmed -- this hook is the tool to "
          "confirm it. hotPathDisabled set to make it opt-in, NOT for volume "
          "(it is an allocator, not a per-line hot path).",
          0, 1, 1, 0, 0 },

        /* ---- v54: the frame->grid sampler INPUT (the last unported colour
         * piece) ----
         *
         * AnsImageData::blockAverage (fcn.100d9930, __thiscall, ecx = the
         * SOURCE AnsImageData). Block-averages a resized "analysis image" into
         * the 24x36x6 SBA grid -- that grid IS measure_samples, the input to
         * the already-bit-exact grid -> balance A path. The one remaining
         * unported colour stage is the frame -> grid sampler that produces the
         * grid; to port it we need its INPUT, the analysis image itself, on a
         * real frame. This hook captures that: the src AnsImageData header
         * (dims @+0xc/+0x10, layout @+0x4, pixptr @+0x20) and the analysis-image
         * pixels reached by a single deref of *(ecx+0x20) -- the same 1-deref
         * pattern framing_lines and area_image_apply_lut's pixel_data use. The
         * grid OUTPUT is not dumped here: the default stack_dwords logged on
         * entry already record the args, and the finished grid is matched
         * offline against the existing measure_samples dump.
         *
         * OFF BY DEFAULT (hotPathDisabled=1): block-average is per-image, not
         * per-pixel, but it can run on several images per scan, so it is opt-in
         * via hooks.cfg and the dump rows are capped at 40 to catch the SBA
         * invocation across a few frames without swamping the trace.
         *
         * Prologue safety: 6A FF 68 A1 D0 51 10 = `push -1` (2 B) +
         * `push 0x1051d0a1` (5 B) = 7 bytes / two whole instructions, both
         * push-immediate -- no relative jmp/call and no RIP-relative operand in
         * the patched bytes -- so MinHook's 5-byte patch relocates them verbatim
         * (approximate=0). VERIFIED with r2 af+pdf: real function boundary. */
        { "PakonIMAu.dll", 0x100d9930, "sba_block_average",
          "AnsImageData::blockAverage (__thiscall, ecx = SOURCE AnsImageData). "
          "Block-averages the resized analysis image into the 24x36x6 SBA grid "
          "(= measure_samples). This hook captures its INPUT -- the analysis "
          "image (dims @+0xc/+0x10, layout @+0x4, pixptr @+0x20) -- so the last "
          "unported colour stage, the frame->grid sampler, can be ported; grid "
          "output = measure_samples, and everything downstream (grid -> balance "
          "A) is already bit-exact, no DLL. OFF BY DEFAULT (opt-in via "
          "hooks.cfg): block-average is per-image not per-pixel, but may be "
          "called on several images per scan.",
          "RE 2026-08-24, /tmp/pakon_re/sampler/, PakonIMAu.dll md5 "
          "eea9dcf78ee21d4f7c515a6c2512242d: fcn.100d9930 = "
          "AnsImageData::blockAverage (embedded strings AnsImageData::"
          "blockAverage @0x10584430 and 'The source and destination images can "
          "not be the same.' @0x1058444c, source AnsImageData.cpp). r2 af+pdf "
          "confirms a real function boundary at 0x100d9930 (~1621 B). Prologue "
          "6A FF 68 A1 D0 51 10 = push -1 (2 B) + push 0x1051d0a1 (5 B) = 7 "
          "bytes / 2 whole instructions, both push-immediate (no relative "
          "jmp/call, no RIP-relative operand), MinHook 5-byte patch safe "
          "(approximate=0). Asserts integer scale @0x100d9d09 (line 501) / "
          "0x100d9d44 (line 509).",
          0, 0, 1, 0, 0 },

        /* ---- v55: the frame->grid sampler, RTTI-PINNED (supersedes v54) ----
         *
         * v54's sba_block_average (fcn.100d9930) fired ZERO times last scan --
         * that block-average belongs to pan-detect, not the SBA grid-fill,
         * while measure_samples (the grid) fired 18x, proving a DIFFERENT
         * function fills it. An RTTI walk pinned the real grid-fill op:
         * ImaBlockAverageOpTT<short,double>::process = fcn.10154ea0, the ONLY
         * concrete block-average op class in the DLL and the handler the
         * dynamically-dispatched "paxelize-BlockAveraged" ImaResampleOp
         * necessarily resolves to. Provenance (tier 3, RTTI): TD 0x10697fd8
         * (.?AV?$ImaBlockAverageOpTT@FN@@) -> COL 0x105e6360 -> vtable
         * 0x1058ddf4 slot 10 = 0x10154ea0. /tmp/pakon_re/sampler/.
         *
         * All three ON PakonIMAu.dll md5 eea9dcf78ee21d4f7c515a6c2512242d,
         * re-verified this pass with r2 af+pdf (real function boundary) and the
         * prologue read directly (MinHook 5-byte patch safe -- no relative
         * jmp/call, no RIP-relative operand in the patched bytes). All three
         * OFF BY DEFAULT (hotPathDisabled=1), opt-in via hooks.cfg.
         *
         * HOOK A -- paxelize_blockavg_op @ 0x10154ea0 (__thiscall, ecx=OP).
         * CONFIRMS the op fires and captures the block factor (op+0x108) and the
         * analysis DIMS; its src/dst pixels sit 3 pointer-levels deep, so no
         * pixel row here (that is HOOK B). Prologue 6A FF 68 13 93 52 10 =
         * push -1 (2 B) + push 0x10529313 (5 B) = 7 bytes / 2 whole
         * push-immediate instructions. ZERO E8 callers (vtable-dispatched, as a
         * name-registered op must be). ON_ENTRY -> wantExitDefault=0. */
        { "PakonIMAu.dll", 0x10154ea0, "paxelize_blockavg_op",
          "ImaBlockAverageOpTT<short,double>::process (__thiscall, ecx = the OP "
          "object) -- the RTTI-pinned handler the \"paxelize-BlockAveraged\" "
          "ImaResampleOp dispatches to, i.e. the SBA grid-fill. Reads the block "
          "factor at op+0x108 (dest holder op+0x104) and the resample CONTEXT at "
          "arg0 (dst rect @+0x30..0x3c, SOURCE analysis image @+0x40). This hook "
          "dumps the op fields, the context, and the src image header (dims "
          "@+0x34/+0x38, stride @+0x44) and, critically, CONFIRMS the op fires "
          "(v54 hooked the wrong block-average and missed). Src/dst pixels are 3 "
          "pointer-levels deep here, so they are captured on HOOK B "
          "(dsba_intlv_to_planar), not here. OFF BY DEFAULT (opt-in via "
          "hooks.cfg).",
          "RE 2026-08-24, /tmp/pakon_re/sampler/, PakonIMAu.dll md5 "
          "eea9dcf78ee21d4f7c515a6c2512242d. RTTI walk: TD 0x10697fd8 "
          "(.?AV?$ImaBlockAverageOpTT@FN@@) -> COL 0x105e6360 -> vtable "
          "0x1058ddf4 slot 10 = 0x10154ea0. r2 af+pdf confirms a real function "
          "boundary (988 B, 0x10154ea0-0x1015528e), ZERO E8/CALL xrefs "
          "(vtable-dispatched only). Prologue 6A FF 68 13 93 52 10 = push -1 "
          "(2 B) + push 0x10529313 (5 B) = 7 bytes / 2 whole push-immediate "
          "instructions (no relative jmp/call, no RIP-relative operand), MinHook "
          "5-byte patch safe (approximate=0). Asserts \"BlockAverage factor must "
          "be positive\"/ImaBlockAverageOp.h @0x10154f1a.",
          0, 0, 1, 0, 0 },

        /* HOOK B -- dsba_intlv_to_planar @ 0x101c0890 (cdecl,
         * AnsDSbaCapabilityImpl::convertInterleaveToPlanar). THE clean
         * analysis-image pixel capture: reads an AnsImageData SOURCE at arg1
         * ([ebp+0xc]) -- pixptr at +0x20, the same +0x20 the area image uses --
         * so DEREF_PTR(idx=1, off=0x20) dumps the analysis pixels exactly like
         * area pixel_data. Real entry 0x101c0890 (NOT 0x101c0893, which afi
         * resolves to the SAME fcn -> mid-prologue). Prologue 55 8B EC 6A FF 68
         * = push ebp + mov ebp,esp + push -1 = 5 bytes / 3 whole
         * position-independent instructions. ON_ENTRY -> wantExitDefault=0. */
        { "PakonIMAu.dll", 0x101c0890, "dsba_intlv_to_planar",
          "AnsDSbaCapabilityImpl::convertInterleaveToPlanar (cdecl) -- the CLEAN "
          "analysis-image pixel capture on the DSBA/SBA path, the piece that "
          "closes the frame->grid sampler port. Reads an AnsImageData SOURCE at "
          "arg1 ([ebp+0xc]): h @+0x10, w @+0xc, bands @+0x14, layout @+0x4, "
          "pixels at +0x20 (the SAME +0x20 AnsImageData pixptr the area image "
          "uses). This hook dumps src_desc (the 0x24 header) and src_pixels via "
          "a single deref of *(arg1+0x20) -- the same 1-deref pattern "
          "area_image_apply_lut's pixel_data uses. Block-average these pixels "
          "offline and compare to measure_samples[bands 0-2]. OFF BY DEFAULT "
          "(opt-in via hooks.cfg).",
          "RE 2026-08-24, /tmp/pakon_re/sampler/, PakonIMAu.dll md5 "
          "eea9dcf78ee21d4f7c515a6c2512242d: r2 af+pdf confirms a real function "
          "boundary (549 B, 0x101c0890-0x101c0ab5); afi @0x101c0893 resolves to "
          "the SAME fcn.101c0890, confirming 0x101c0893 is mid-prologue, not an "
          "entry (real entry is 0x101c0890). Prologue 55 8B EC 6A FF 68 = push "
          "ebp (1 B) + mov ebp,esp (2 B) + push -1 (2 B) = 5 bytes / 3 whole "
          "position-independent instructions (no relative jmp/call, no "
          "RIP-relative operand), MinHook 5-byte patch safe (approximate=0). "
          "Single caller fcn.101c1120 @0x101c126d.",
          0, 0, 1, 0, 0 },

        /* HOOK C -- resample_analysis_img @ 0x100d8030 (cdecl,
         * pathUtils::resampleAnslysisImage). FALLBACK for the analysis DIMS
         * only: resizes the frame into the proportionally-scaled analysis image
         * the block-average consumes. Hooked ON EXIT (arg0 is the out
         * ptr-to-descPtr, so DEREF_PTR(idx=0, off=0) does the one deref to the
         * finished descriptor). Pixels need a 3rd deref -> not capturable here.
         * Prologue 55 8B EC 6A FF 68 = 5 bytes / 3 whole position-independent
         * instructions. ON_EXIT -> wantExitDefault=1 (it must be exit-hooked to
         * fire the anal_desc row). */
        { "PakonIMAu.dll", 0x100d8030, "resample_analysis_img",
          "pathUtils::resampleAnslysisImage (cdecl) -- FALLBACK for the analysis "
          "DIMS only. Resizes the frame into the proportionally-scaled "
          "\"analysis image\" (dest = round(src*target/max(w,h))) the "
          "block-average later consumes. Hooked ON EXIT: arg0 is the out "
          "ptr-to-descPtr, so DEREF_PTR(idx=0, off=0) does the one deref to the "
          "finished analysis descriptor (dims @+0xc/+0x10, layout @+0x4, pixptr "
          "@+0x20). Its PIXELS need a 3rd deref (not capturable here); this row "
          "settles the dims so HOOK B's source can be identified as pre- or "
          "post-average. wantExitDefault=1 so the ON_EXIT row can fire. OFF BY "
          "DEFAULT (opt-in via hooks.cfg).",
          "docs/74 sampler UPDATE 3; RE 2026-08-24, /tmp/pakon_re/sampler/, "
          "PakonIMAu.dll md5 eea9dcf78ee21d4f7c515a6c2512242d: r2 af+pdf confirms "
          "a real function boundary (1047 B, 0x100d8030-0x100d8447). Prologue "
          "55 8B EC 6A FF 68 = push ebp + mov ebp,esp + push -1 = 5 bytes / 3 "
          "whole position-independent instructions (no relative jmp/call, no "
          "RIP-relative operand), MinHook 5-byte patch safe (approximate=0). "
          "Single caller fcn.100d85c0 (apuPutAnalysisImageInPortfolio).",
          0, 1, 1, 0, 0 },

        /* ---- v56: the frame->grid sampler DIAGNOSTIC (docs/74 sampler
         * UPDATE 8/9; RE 2026-08-24, /tmp/pakon_re/sampler/ + v56build/).
         * UPDATES 5/7 proved TWO misses: v54's sba_block_average and v55's
         * paxelize_blockavg_op / dsba_intlv_to_planar / resample_analysis_img
         * ALL fired ZERO times -- they are DSBA / ImaResample machinery the
         * REGULAR SBA path never invokes. UPDATE 8 re-grounded on RUNTIME
         * evidence: the regular capability's analyzePass1 DID run (12x), it only
         * READS the already-populated frame grid (frame+0x1a), so the grid
         * PRODUCER runs UPSTREAM and is unhooked. These two hooks are a
         * diagnostic that finds the producer in ONE scan, using functions with
         * proven/derived runtime firing on the regular path -- NOT another
         * DSBA guess.
         *
         * HOOK 1 (essential) -- sba_analyze_pass1 @ 0x10218110. PROVEN to fire.
         * The LATCH: dump the images the capability holds at analyze time. */
        { "PakonIMAu.dll", 0x10218110, "sba_analyze_pass1",
          "AnsSbaCapabilityImpl::analyzePass1 (__thiscall, ecx = "
          "AnsSbaCapabilityImpl). PROVEN to fire on the REGULAR SBA path "
          "(sba_order_fpo_calc returns into it 12x @ retaddr 0x102196ae, docs/74 "
          "sampler UPDATE 8 §1). The frame->grid (frame+0x1a) is already "
          "populated at entry -- this function only READS it -- so the grid "
          "PRODUCER runs upstream and is unhooked. LATCH hook: dumps the "
          "capability head (ecx+0), the arg0/arg1 AnsImageData headers and "
          "arg0's pixels (*(arg0+0x20)) to test whether arg0 reproduces "
          "measure_samples (=> the producer is arg0's source, portable offline "
          "from one scan). OFF BY DEFAULT (opt-in via hooks.cfg).",
          "docs/74 sampler UPDATE 8/9; RE 2026-08-24, /tmp/pakon_re/sampler/ + "
          "/tmp/pakon_re/v56build/, PakonIMAu.dll md5 "
          "eea9dcf78ee21d4f7c515a6c2512242d: r2 af+pdf real function boundary "
          "(6312 B, 0x10218110-0x102199b8), embedded string "
          "\"AnsSbaCapabilityImpl::analyzePass1()\" @0x1059e1b0. Prologue "
          "55 8B EC 6A FF 68 1F AD 53 10 = push ebp (1 B) + mov ebp,esp (2 B) + "
          "push -1 (2 B) = 5 bytes / 3 whole position-independent instructions "
          "(no relative jmp/call, no RIP-relative operand), MinHook 5-byte patch "
          "safe (approximate=0). Runtime firing proof: "
          "live_hooks_20260822-170343.jsonl (retaddr 0x102196ae x12).",
          0, 0, 1, 0, 0 },

        /* HOOK 3 (bracket) -- cn_balance_order @ 0x10101220 =
         * ColorNegativePath::analyzeBalanceOrder (\Atc\ansel\src\
         * libPaths.ansel\cnMethods.cpp). The CN scene balance-order driver that
         * acquires the "Sba"/"Fos" capabilities and calls the analyzePass1
         * dispatcher fcn.10123980 at 0x101013da. Its ENTRY (no dump rows -- base
         * enter/leave logging only) brackets the unhooked producer's call site
         * in the timeline relative to sba_analyze_pass1. NOTE the sampler note's
         * "~fcn.10101180" was wrong (that fcn is 153 B, ends 0x10101219); the
         * real container of the 0x101013da call site is this 0x10101220 entry.
         *
         * Prologue 6A FF 68 D2 15 52 10 = push -1 (2 B) + push 0x105215d2 (5 B)
         * = 7 bytes / 2 whole push-immediate instructions (no relative jmp/call,
         * no RIP-relative operand), MinHook 5-byte patch safe (approximate=0).
         * Real, independently call-reachable entry -> the exit return-address
         * swap is safe; wantExitDefault=1 for the full enter/leave bracket. OFF
         * BY DEFAULT (hotPathDisabled=1; per-scene, opt-in via hooks.cfg). No
         * g_extraDumps rows.
         *
         * HOOK 2 (paxelize-SubSampled) was investigated and DELIBERATELY SKIPPED
         * -- see /tmp/pakon_re/sampler/RESUME.md UPDATE 9: no RTTI op class for a
         * SubSample op exists (BlockAveraged had two), the op is registered by
         * name through a dynamic factory vtable (0x10071dee, call [eax+0x38]) so
         * the string does not statically yield a handler, and UPDATE 7 already
         * proved the whole paxelize/ImaResample chain is DSBA-only and does not
         * fire on the regular path. Hooking it would repeat the documented miss;
         * a guess was not added. Slot 47 left free. */
        { "PakonIMAu.dll", 0x10101220, "cn_balance_order",
          "ColorNegativePath::analyzeBalanceOrder (fcn.10101220, cnMethods.cpp) "
          "-- the CN scene balance-order driver that acquires the Sba/Fos "
          "capabilities and calls the analyzePass1 dispatcher (fcn.10123980) at "
          "0x101013da. Call-log BRACKET (no dump rows): its enter/leave frames "
          "the unhooked frame->grid producer's call site in the timeline "
          "relative to sba_analyze_pass1. OFF BY DEFAULT (opt-in via hooks.cfg).",
          "docs/74 sampler UPDATE 8/9; RE 2026-08-24, /tmp/pakon_re/v56build/, "
          "PakonIMAu.dll md5 eea9dcf78ee21d4f7c515a6c2512242d: r2 af+pdf real "
          "function boundary (5579 B, 0x10101220-0x101027eb) containing "
          "call 0x10123980 @0x101013da; embedded strings "
          "\"ColorNegativePath::analyzeBalanceOrder\" @0x10586d3c and \"Sba "
          "capability not found.\" @0x1057a46c. Prologue 6A FF 68 D2 15 52 10 = "
          "push -1 (2 B) + push 0x105215d2 (5 B) = 7 bytes / 2 whole "
          "push-immediate instructions (no relative jmp/call, no RIP-relative "
          "operand), MinHook 5-byte patch safe (approximate=0).",
          0, 1, 1, 0, 0 },
    };

    /* Build-time guard for exactly the bug described above: if table[] ever
     * outgrows the fixed-size HookEngine.defs[]/rt[]/thunks[] arrays, this
     * fails to COMPILE. Raise HOOKCORE_MAX_HOOKS, add the matching
     * `extern void Thunk_NN` in hookcore.h, the DEFTHUNK NN in hookstub.S,
     * and the thunks[] entry above -- all four, in the same pass. */
    typedef char table_fits_in_engine_arrays
        [(int)(sizeof(table) / sizeof(table[0])) <= HOOKCORE_MAX_HOOKS ? 1 : -1];

    int i;
    eng->count = (int)(sizeof(table) / sizeof(table[0]));
    for (i = 0; i < eng->count; i++) {
        eng->defs[i] = table[i];
        eng->defs[i].entryThunk = thunks[i];
    }
}

/* ---------------------------------------------------------------------
 * g_extraDumps[] -- docs/74 SS47's own re-derived calling convention for
 * area_image_apply_lut (0x100d9340), from a fresh af+pdf this pass (not
 * reused from SS46's transcription, which SS47.1 found had dropped a real
 * `push edi` instruction at the first balanceAreaImage call site). Stack
 * layout at entry, confirmed against BOTH the caller-side push order AND
 * the callee-side [esp+N] reads independently, and cross-checked live
 * (ecx == stack_dwords[4] on all 18 real captured calls, docs/74 SS47.2):
 *
 *   stack_dwords[0] = &status   (caller-owned out-param, NOT a buffer)
 *   stack_dwords[1] = R-band LUT pointer (4096 x int16 = 8192 bytes)
 *   stack_dwords[2] = G-band LUT pointer (= R + 0x2000 in every real
 *                      capture from balanceAreaImage's own compose chain,
 *                      but NOT assumed here -- read via its own pointer)
 *   stack_dwords[3] = B-band LUT pointer (= R + 0x4000, same caveat)
 *   stack_dwords[4] = dup-this: the SAME AnsImageData* as `this`/ecx
 *
 * Pixel-buffer dump: `this->0x20` is the AnsImageData pixel-data
 * base-pointer field. Originally SS47.1's own inference (traced via the
 * "if width/height/bands > 0: eax = [edi+0x20]; cache it for the loop"
 * block at 0x100d9650-0x100d9664); re-confirmed 2026-08-16 by a fresh
 * af+pdf of 0x100d9340 -- 0x100d9661 `mov eax,[edi+0x20]` is the real
 * per-pixel-loop source base, and the band-pointer arithmetic at
 * 0x100d967f-0x100d9708 shows the packing==0 layout is INTERLEAVED
 * 16-bit RGB (band 0 at base+0, band 1 at base+2, band 2 at base+4),
 * with width at this->0xc, height at this->0x10, bands at this->0x14,
 * packing at this->0x4, row stride at this->0x1c. Bumped from SS47's
 * 256-byte preview to the full 8192-byte row cap specifically so a
 * capture carries enough real RPD12 pixel values (4096 int16 = ~1365
 * interleaved RGB pixels) to fit the F-135 inversion curve
 * (ROM12 -> RPD12) against this port's own PolyPixel output on the same
 * frame -- the one unverified stage behind the washed-out defect
 * (docs/74 SS8/SS32/SS51/SS54). Still bounded at
 * HOOKCORE_EXTRA_DUMP_MAX_BYTES, and still IsBadReadPtr-guarded, so
 * this stays a per-CALL (not per-pixel) cost on the real box.
 */
/* ---------------------------------------------------------------------
 * tlb_polypixel (0x1000d880) extra dump -- captures the raw 14-bit R
 * plane the F-135 PolyPixel reads, so the inversion curve (ROM12 -> RPD12)
 * can be fit point-for-point against the area_image_apply_lut pixel_data
 * capture on the SAME frame.
 *
 * Calling convention (fresh af+pdf 2026-08-16, call site fcn.10026c90 @
 * 0x100270a5): `push eax; push esi; push edi; call fcn.1000d880`, i.e. at
 * entry stack_dwords[0]=edi, stack_dwords[1]=esi (= buffer base),
 * stack_dwords[2]=eax (filmClass). The buffer is PLANAR int16:
 * R at base, G at base + w*h*2, B at base + w*h*4, where w=stack_dwords[3]
 * and h=stack_dwords[4] (PolyPixel's own `imul eax,[esp+0x68],[esp+0x6c]`
 * then `lea ebx,[edx+eax*2]`/`lea ebp,[edx+eax*4]` at
 * 0x1000d8ce-0x1000d8e3). Confirmed live (v10, docs/74 SS59): the frame is
 * 245x367 (w=0xf5, h=0x16f), NOT 2000 px wide as this comment previously
 * guessed. PolyPixel is in-place, so at ENTRY the dump is the raw 14-bit
 * (pre-poly) plane; the port computes ROM12 = PolyPixel(raw) bit-exact.
 * First 8192 bytes of each plane = first 4096 pixels (~16.7 scanlines at
 * w=245). v12/v13 (docs/74 SS60) bumps poly_input_r to 0x84000 bytes
 * (540672 = the page-rounded committed frame size; 245x367x3 planes x2 =
 * 539490 = 0x83B62, R+G+B contiguous, since the planes are back-to-back at
 * w*h*2/4), so the whole frame is carried in ONE dump -- this is what
 * makes the raw<->RPD12 spatial relayout solvable by 2D cross-correlation
 * (the truncated tops of the two differently-laid-out buffers did not
 * overlap). poly_input_g/b are dropped (redundant with the full dump).
 * 0x90000 was tried first and came back IsBadReadPtr-failed on every row
 * (the inter-buffer stride is larger than the committed region), so 0x84000
 * is the read-safe ceiling. Bounded/IsBadReadPtr-guarded.
 *
 * area_image_apply_lut (0x100d9340) img_desc dump: 0x24 bytes of the
 * AnsImageData descriptor at this->0x0 -- packing@0x4, width@0xc,
 * height@0x10, bands@0x14, row stride@0x1c -- so the RPD12 pixel_data
 * layout (interleaved vs planar, stride) is read straight off the object
 * instead of guessed from the buffer stride.
 */
/*
 * color_adjust_shift (0x101b76d0) extra dump -- captures the raw
 * AnsColorAdjustCapabilityImpl field region so the still-open question
 * docs/74 SS57.5 flags (which code writes the non-zero dens/S2/dmin) can
 * be settled from live values instead of the noise-swamped static search.
 *
 * __thiscall: ecx = Impl. Field layout (verified, docs/74 SS57.2):
 *   +0x0c/+0x10/+0x14   M (3 x float)
 *   +0x18               S1 (float)
 *   +0x1c/+0x20/+0x24   dens a,b,c (3 x float)
 *   +0x28               S2 (float)
 *   +0x2c/+0x2e/+0x30   dmin (3 x int16)
 *
 * Dump 0x28 bytes from Impl+0x0c (M..dmin inclusive, 38 bytes + 2 pad) --
 * raw hex, so the floats/int16s parse offline against the already-ported
 * orderFpo/fosDmin. EXTRA_DUMP_THIS_OFFSET reads regs->ecx, so stackIndex
 * is ignored (0). 40 bytes per call, IsBadReadPtr-guarded like the rest.
 */
/*
 * sba_get_shifts (0x10124000) extra dump -- captures the 3 int16 that
 * getShifts copies out of *(AnsSbaCapability+0x10)+0x3a38 (the SBA Impl's
 * shift words) into its out buffer, so the per-frame +0x3a38 values the
 * balance actually reads can be read DIRECTLY instead of recovered by
 * inverting setshifts_12 (docs/74 SS62). __thiscall: ecx = AnsSbaCapability;
 * EXTRA_DUMP_THIS_DEREF_OFFSET reads *(ecx + 0x10) + 0x3a38 (6 bytes = 3
 * int16). This settles SS62.3's open contradiction -- whether +0x3a38 is
 * written per-frame by a second writer (it varies) or is constant (it
 * doesn't) -- and lets the per-frame values be correlated against the FOS
 * orderFpo/fosDmin the port already computes.
 */
/*
 * sba_preference (0x1028c780) extra dumps -- capture the Preference's own
 * INPUTS to find the source of the per-frame uniform luma offset Delta that
 * SS62.5 found is added to setshifts_12(+0x3a38) in the applied balance
 * shift. Calling convention (SS62): arg1 = scene+0x38a2 (preference data the
 * hi=0/hi=0x30 U/V-aim fields live in), arg2 = FOS (null live), arg3 =
 * scene+0x3a30 (shift out), arg4 = blob (the nested-fpo copy), arg5 = mode.
 * So pref_data dumps the per-frame preference words (orderFpo/fpo) and blob
 * dumps the nested-fpo struct -- enough to see whether the Delta tracks the
 * FOS orderFpo luma or the DPI constant.
 */
const ExtraDumpSpec g_extraDumps[] = {
    { "area_image_apply_lut", "r_lut", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 8192, EXTRA_DUMP_ON_ENTRY, 0 },
    { "area_image_apply_lut", "g_lut", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 8192, EXTRA_DUMP_ON_ENTRY, 0 },
    { "area_image_apply_lut", "b_lut", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 8192, EXTRA_DUMP_ON_ENTRY, 0 },
    { "area_image_apply_lut", "img_desc", EXTRA_DUMP_THIS_OFFSET, 0, 0x0, 0, 0x24, EXTRA_DUMP_ON_ENTRY, 0 },
    { "area_image_apply_lut", "pixel_data", EXTRA_DUMP_DEREF_PTR, 4, 0x20, 0, 0x80000, EXTRA_DUMP_ON_ENTRY, 20 },
    /* v46 -- the SAME buffer at exit. area_image_apply_lut rewrites
     * this->0x20 in place (the per-pixel loop's source base is
     * `mov eax,[edi+0x20]` at 0x100d9661), so entry+exit of one call is the
     * additive-shift stage's input and output, same pixels, same layout, no
     * pairing guesswork. Capped to the same 20 dumps as the entry row so the
     * pairs line up: 127 calls over 39 frames is ~3.3/frame, so 20 covers the
     * first ~6 frames -- the same six the whole SS157-SS181 comparison uses.
     * 0x80000 hex-encoded is ~1.05 MB per dump, which is why this is capped
     * and the per-frame SCALAR rows below are not. */
    { "area_image_apply_lut", "pixel_data_out", EXTRA_DUMP_DEREF_PTR, 4, 0x20, 0, 0x80000, EXTRA_DUMP_ON_EXIT, 20 },
    { "tlb_polypixel", "poly_input_r", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x84000, EXTRA_DUMP_ON_ENTRY, 12 },
    /* v46 -- STAGE 2's OUTPUT, the row this whole exit-dump mechanism was
     * built for. PolyPixel is in-place (docs/74 SS32.2), so this is byte-for-
     * byte the same 540,672-byte planar R/G/B region as poly_input_r above,
     * read after the polynomial has run. That gives a real (in, out) pair for
     * the one stage this port has never been able to test on vendor data:
     * SS60 could not solve the raw<->RPD12 relayout by cross-correlation
     * because the only two captures available were different buffers in
     * different layouts. This pair is the same buffer, so there is no
     * relayout to solve -- the mapping is index-for-index.
     * 12 dumps = 6 frames (77 calls / 39 frames ~= 2 per frame). */
    { "tlb_polypixel", "poly_output_r", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x84000, EXTRA_DUMP_ON_EXIT, 12 },
    { "sba_get_shifts", "shifts_3a38", EXTRA_DUMP_THIS_DEREF_OFFSET, 0x10, 0x3a38, 0, 6, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_get_shifts", "pref_out_3a30", EXTRA_DUMP_THIS_DEREF_OFFSET, 0x10, 0x3a30, 0, 6, EXTRA_DUMP_ON_ENTRY, 0 },
    /* docs/74 sec69: getShifts reads *(arg1+0x10)+0x3a38 (arg1 = sp[0]), NOT
     * *(this+0x10)+0x3a38 -- the two getShifts the setShifts body makes use
     * the same this/arg1, but the caller's third getShifts (0x10101ff6) has a
     * different arg1. Dump the real read to catch the per-frame Delta. */
    { "sba_get_shifts", "shifts_3a38_arg1", EXTRA_DUMP_STACK_DEREF2_OFFSET, 0, 0x10, 0x3a38, 6, EXTRA_DUMP_ON_ENTRY, 0 },
    /* docs/74 sec67: the Preference's OUT proves it runs hi=0x30/lo=3 (out+2
     * matches), yet arg5(mode)=0 is captured. Dump the scene mode word
     * scene+0x5074 directly at getShifts to settle whether the live mode is
     * 0x33 (arg5 capture artifact) or 0 (Preference reads mode elsewhere). */
    { "sba_get_shifts", "mode_5074", EXTRA_DUMP_THIS_DEREF_OFFSET, 0x10, 0x5074, 0, 2, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_preference", "pref_data", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x64, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_preference", "blob", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x48, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v29 (docs/74 SS95) -- the inputs that produce the per-frame balance
     * scalar `k`.
     *
     * SS93/SS94 established the vendor's shift is `A[c] + k[f]`: A is a
     * per-channel constant stable across two rolls (agrees to 5 codes on G),
     * k is a per-scene scalar. Every offline candidate for k has been tested
     * and ruled out -- Y, U and V from the SS79-golden orderFpo triple (best
     * residual rms 33.0 against a k spread of 118), L itself, and every
     * int16/int32 field in this 0x64 pref_data window (nothing above |0.95|).
     *
     * WHY THE SEARCH COULD NOT HAVE SUCCEEDED. The call trace puts the
     * producer exactly here:
     *
     *     3300 sba_order_fpo_helper   (computes L)
     *     3301 sba_preference         <- consumes the triple, produces the shift
     *     3302 sba_set_shifts         (the shift is now set)
     *     3306 area_image_apply_lut   (applied; balance_shift_4b6 confirms
     *                                  the same six triples independently)
     *
     * but the scene structs are contiguous with a stride of 25820 bytes
     * (cn_enhanced_driver arg1: 150139080, 150164900, 150190720, ...), and
     * pref_data dumps 0x64 of them -- 0.4 %. The inputs driving k are almost
     * certainly outside that window, so the negative results above bound
     * where k ISN'T, not what it is.
     *
     * arg0 here sits ~0x3888 into the same scene struct fpo_calc's arg0
     * addresses, and orderFpo writes its triple at scene+0x38a2 -- just past
     * it, in a region fpo_calc's own arg0_big (0x3000) does not reach. 0x800
     * covers the triple and the fields around it. Same pointer already being
     * dumped, only larger: no new hook, no thunk, no HOOKCORE_MAX_HOOKS
     * change, and if the buffer is shorter than asked the row comes back
     * readable=false while the 0x64 row above still carries its data. */
    { "sba_preference", "pref_scene_big", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x800, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v30 (docs/74 SS105) -- the ONE row that brackets where the luma is added.
     *
     * SS101 showed the vendor's shift differs from Preference's output on
     * frames 4-6 by a uniform per-channel amount (+92/+65/+39 -- pure luma),
     * and SS104.4 showed sba_set_shifts fires only SIX times, all per-scene,
     * so the correction is NOT delivered through set_shifts. SS100 killed the
     * pref_scene_big theory outright: those bytes are copied, never computed
     * with, and the shift is invariant to them under three different fills.
     *
     * The window is now four calls wide. From the v28 capture's own pointers:
     *
     *     set_shifts   3302   arg1=0x8ea25a0 arg3=0x8ea26b0
     *     get_shifts   3303   arg2=0x8ea25a0        (= set_shifts arg1)
     *     cn_driver    3305   arg1=0x8f2f0c8
     *     apply_lut    3306   arg4=0x8f2f0cc        (= cn arg1 + 4)
     *     balance      3309   arg3=0x8f2f574        (= cn arg1 + 0x4ac)
     *
     * and balance_shift_4b6 reads arg3+0x0a, i.e. **cn_driver arg1 + 0x4b6** --
     * which is where the row's own name came from. So the final shift is
     * readable from cn_enhanced_driver's arg 1, and apply_lut's LUTs (which
     * already carry the final value) are built one call later.
     *
     * Dumping arg 1 at cn_enhanced_driver's ENTRY therefore discriminates
     * exactly:
     *   - if +0x4b6 already holds the vendor's final shift, the luma was added
     *     BEFORE cn_driver, i.e. inside get_shifts or between it and here;
     *   - if it holds what our emulation of Preference produces, the luma is
     *     added INSIDE cn_driver or later.
     *
     * One row, one pointer already passed on the stack, and a yes/no answer
     * either way. 0x500 covers +0x4b6 with margin. */
    { "cn_enhanced_driver", "cn_shift_before", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x500, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v31 (docs/74 SS106.4) -- the three cheapest unexplored inputs to `k`.
     *
     * v30 established that the luma correction is applied inside
     * cn_enhanced_driver and is pure luma on 39/39 frames, but SS105.5 then
     * closed every candidate that could be tested from arg 1: not the incoming
     * shift, not a clamp, not any field in the 0x500 window (int16/uint16/
     * int32/float32 at every offset), and not cross-frame smoothing. The two
     * byte flags the gated block actually reads -- esi+0x29 and esi+0x4c --
     * are constant 1 across all 39 frames, so they do not discriminate either.
     *
     * arg 2 and arg 3 have NEVER been dumped (arg2=0x8ca9f88, arg3=0x8ca9f8c
     * in the v28 trace -- adjacent, so probably one small struct and a pointer
     * into it). They are the only inputs left that a row can reach.
     *
     * The third row is the gate itself. SS106.1: the block that writes the
     * shift is skipped unless a global at 0x106b5bd4 matches a value derived
     * from balance_area_image. That global is ZERO in the file image, so it is
     * written during initialisation and its run-time value has never been
     * observable -- no existing dump kind can reach a static. Hence
     * EXTRA_DUMP_MODULE_ABS, added in this same build: base + RVA 0x6b5bd4
     * (0x106b5bd4 at the preferred base 0x10000000), 0x40 bytes to catch its
     * neighbours too.
     *
     * If the global turns out to vary per frame it is the discriminator; if it
     * is constant, the gate's other operand is, and the answer is in
     * balance_area_image. Either outcome halves the search. */
    { "cn_enhanced_driver", "cn_arg2", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x200, EXTRA_DUMP_ON_ENTRY, 0 },
    { "cn_enhanced_driver", "cn_arg3", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x200, EXTRA_DUMP_ON_ENTRY, 0 },
    { "cn_enhanced_driver", "cn_gate_global", EXTRA_DUMP_MODULE_ABS, 0, 0x6b5bd4, 0, 0x40, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v29b (docs/74 SS98) -- arg 2, kept for its WRITE targets, not its reads.
     *
     * An earlier justification for this row claimed the function reads
     * arg2+0x54 as a missing input. That was WRONG and is corrected here: a
     * read/write-ordered trace shows arg2+0x54 is WRITTEN first
     * (0x1028c884: mov word [esi+0x54], cx) and only then read back as a loop
     * bound (0x1028c8eb/0x1028c8ff). It is an internal temporary, not an
     * input, and no capture is needed to supply it.
     *
     * The row is kept on different grounds: fcn.1028c780 WRITES the anchor at
     * arg2+0x02 and the balance shift at arg2+0x08 (SS97.1), so dumping arg2
     * on ENTRY gives the pre-call state and makes the capture self-checking --
     * the emulation's computed shift can be diffed against what the vendor
     * actually left there, per call, without relying on the LUT decode. 0x80
     * covers both slots with margin. */
    { "sba_preference", "pref_arg2", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x80, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v33 (docs/74 SS123) -- FUGC's own state, which SS122 left as the only
     * unverified input to R's transfer shape.
     *
     * SS121 traced R's SHAPE to FUGC: setShifts feeds a per-channel
     * setLutInfo offset (aim_offset = w60ec - w60f8 + w60f2, the fragment at
     * 0x101f82c0), so a wrong shift becomes a wrong per-channel CURVE, not
     * merely a wrong balance. SS122 then checked every other FUGC input
     * against the vendor's shipped files -- aFilmAimDmin (500,1000,1000) from
     * fugc-defaultParams.dpi, aTableDmin (500,500,500) from the seed LUT's own
     * header, and the NoShift_fugc-generic0225.lut selection via
     * AnsFugcMapping -- and all are correct.
     *
     * What has never been captured is what FUGC computes at RUN TIME. Both
     * fugc hooks fire 80x per scan and dump nothing.
     *
     * WHY THIS ROW AND NOT AN ARG INDEX. fcn.101f82c0 is __thiscall
     * (0x101f82ee: `lea eax, [ecx + 0xe6]`) and r2 resolves only two stack
     * args, so the port's own set_lut_info_channel(seed, offset, n) is a
     * FRAGMENT signature, not the ABI -- reading "arg3" as the offset gives 0
     * on all 40 calls, which is an artefact of the wrong index, not a
     * measurement. That mis-derivation has cost this project a hardware round
     * trip three times (v22, v24, v26), so this dumps what the function
     * demonstrably reads instead of a guessed argument: `this` + 0xe0, the Cap
     * slot the port already documents as aTableDmin's home and the base the
     * function's own first memory reference is taken from.
     *
     * 0x80 covers +0xe0 with margin and catches the neighbouring Cap fields
     * (+0x60ec/+0x60f2/+0x60f8 are elsewhere; this is the Cap header). */
    { "fugc_set_lut_info", "fugc_cap_e0", EXTRA_DUMP_THIS_OFFSET, 0, 0xe0, 0, 0x80, EXTRA_DUMP_ON_ENTRY, 0 },
    { "fugc_analyze", "fugc_analyze_arg1", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x200, EXTRA_DUMP_ON_ENTRY, 0 },
    { "fugc_analyze", "fugc_analyze_this", EXTRA_DUMP_THIS_OFFSET, 0, 0, 0, 0x100, EXTRA_DUMP_ON_ENTRY, 0 },
    /* docs/74 sec68: balanceAreaImage reads the three ramp-shift words from
     * arg4+0x0a (0x10102f85..fa3). Dump them directly to pin scene+0x4b6 --
     * the setShifts OUT plus the per-frame uniform luma offset Delta that is
     * still unlocated (added between setShifts and this read). */
    { "balance_area_image", "balance_shift_4b6", EXTRA_DUMP_STACK_PTR_OFFSET, 3, 0xa, 0, 6, EXTRA_DUMP_ON_ENTRY, 0 },
    /* docs/74 §168 -- Delta, the uniform per-frame scalar, at last capturable.
     *
     * §168.1: applied_k = (scene+0x4b6 at cn_enhanced_driver ENTRY) + Delta,
     * with Delta the SAME value on all three channels every frame -- 0 on 21
     * of 39, non-zero on 18, range -55..94. §168.2 eliminated every captured
     * source: nothing carries it verbatim, best predictor |corr| 0.26, best
     * image statistic 0.302 (best of 20 tried, i.e. chance), and it is not a
     * function of the entry triple (|corr| 0.02-0.05).
     *
     * analyzePostBalance sees the triple AFTER that rewrite. Which of its two
     * cdecl arguments carries the scene is NOT established, so both are
     * dumped generously rather than guessed; +0x4b6 will land inside whichever
     * one it is, and the triple is identified offline by matching the known
     * per-frame applied k. Deliberately not a narrow 6-byte row at a guessed
     * offset -- that is the mistake v41 made twice. */
    /* ---- v50: the row that pins δ ----
     *
     * docs/74 §201. The 2026-08-21 capture localised δ — §168's "uniform
     * per-frame scalar whose source is still uncaptured" — to the window
     * between cn_enhanced_driver's entry and fugc_analyze's entry, and
     * measured it: the triple at scene+0x4b6 changes by EXACTLY the same
     * amount on R, G and B, on 6 frames of 6 (-39, +30, +17, +37, -52, +10).
     *
     * Exactly three hooked calls run in that window:
     *     analyze_post_balance · shift_lut_builder · area_image_apply_lut
     *
     * None of the four bracketed stages (fugc / attributes / falloff /
     * autotone) touches the triple — 0 of 6 each. The reason δ was never
     * seen is simply that **analyze_post_balance has no scene bracket**: its
     * existing rows dump arg0/arg1/an image descriptor, and §189.3 already
     * found two of those were a caller status local and a smart-pointer
     * holder rather than the scene.
     *
     * This row is the scene itself, at both ends, 0x64DC as everywhere else.
     * If the triple changes across it, δ is analyze_post_balance's and the
     * search is over. If it does not, δ belongs to one of the other two and
     * that is equally decisive — which is the point of bracketing rather
     * than guessing.
     *
     * arg1 is the scene: §189.3 established analyze_post_balance's pushes as
     * [esi+0x2c] | esi+4 | esi+0x4ac | holder | &status, and the shift triple
     * is read at index 2 + 0x0a — i.e. stack_dwords[1] + 0x4b6 is the same
     * scene+0x4b6 every other bracket dumps. Index 1, NOT 2: see the v48
     * correction above, argN is at stack_dwords[N-1]. */
    { "analyze_post_balance", "apb_scene", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x64DC, EXTRA_DUMP_ON_BOTH, 6 },

    { "analyze_post_balance", "apb_arg0", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x600, EXTRA_DUMP_ON_ENTRY, 0 },
    { "analyze_post_balance", "apb_arg1", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x600, EXTRA_DUMP_ON_ENTRY, 0 },
    /* docs/74 §163 -- the transfer table applied per pixel immediately
     * before PolyPixel: out[i] = *(uint16 *)(table + in[i]*4). Capturing it
     * settles whether tlb_lut_apply is the F-135 inversion. A monotone,
     * log-shaped table means the inversion is found and portable bit-exact;
     * an identity table means this function is a no-op on the CN path and
     * §162's inversion lies elsewhere upstream. Either answer closes §163.
     *
     * v41 GOT THE INDEX WRONG -- do not copy that row. r2 labels the table
     * argument `arg_14h`, but that label is relative to the esp AFTER
     * `push esi`: the instruction is `8b742414` = `mov esi, [esp+0x14]` at
     * 0x10022a71, one push in, so it reads ORIGINAL esp+0x10 -- the FOURTH
     * argument.
     *
     * The index convention is fixed by an existing, known-good row:
     * poly_input_r uses index 1 and its own comment documents
     * `stack_dwords[0]=edi` for `push eax; push esi; push edi; call`, i.e.
     * stack_dwords[i] = [orig_esp + 4 + 4*i], so index 0 is the FIRST
     * argument:
     *     arg1 dst   = index 0
     *     arg2 src   = index 1
     *     arg3 count = index 2
     *     arg4 table = index 3
     *
     * v41 used 5 -- past the argument list, into the caller's frame -- and
     * got a readable but meaningless buffer: 68 non-zero entries of 4096,
     * [0]=46868, [1024]=0, [4095]=0. That is the signature of dumping the
     * wrong address, not of a sparse table. */
    /* v42 dumped 0x4000 = 4096 entries, but lut_src's real range is 404..11681
     * (docs/74 §173.1) -- the loop indexes table + in[i]*4 with a full 16-bit
     * in[i], so 4096 entries covered only the first quarter of the range
     * actually used. 0x10000 = 16384 entries covers 11681 with headroom. */
    /* v46: capped at 4. THIS ROW IS WHY maxDumps EXISTS. v45 hung ~96 KB of
     * dumps on this hook without knowing it fires **52,877 times** in one
     * scan; the log was truncated and the capture was lost. The table is a
     * single runtime-built object -- 4 copies prove it is stable and cost
     * 0.5 MB; 52,877 copies cost ~3.5 GB and prove the same thing. */
    { "tlb_lut_apply", "lut_table", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x10000, EXTRA_DUMP_ON_ENTRY, 4 },
    /* And its input plane, so the mapping can be fit point-for-point against
     * poly_input_r (this loop's output) on the SAME frame. arg2, index 1
     * (v41 used 2, which is the COUNT -- a small integer, not a pointer). */
    { "tlb_lut_apply", "lut_src", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x8000, EXTRA_DUMP_ON_ENTRY, 24 },
    /* v46 -- the inversion's OUTPUT. arg1 (index 0) is the destination:
     * `out[i] = *(uint16 *)(table + in[i]*4)` writes through it (docs/74
     * SS163.2, 0x10022a7d `mov word [eax], di`). With lut_src at entry and
     * this at exit, the F-135 inversion becomes directly testable pixel by
     * pixel against the captured table, with no need to infer the mapping
     * from attainable-value spacing the way SS163.5 had to.
     *
     * A WARNING FOR WHOEVER READS THE CAPTURE. This hook is per-STRIP, not
     * per-frame: 52,877 calls for 39 frames is ~1,356 calls per frame, and
     * `count` (arg3, stack_dwords[2]) says how many pixels each one covers.
     * The 24-dump cap therefore does NOT mean "24 frames" or even "24
     * strips spread over the roll" -- it means the first 24 calls, which all
     * belong to the FIRST frame or two. There is no once-per-frame hook on
     * this boundary (see the report accompanying this build), and a per-row
     * cap cannot manufacture one; it can only bound the first N. */
    { "tlb_lut_apply", "lut_dst", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x8000, EXTRA_DUMP_ON_EXIT, 24 },
    /* v32 (docs/74 SS108.3) -- balance_area_image's own inputs, which serve two
     * purposes at once.
     *
     * SS107 eliminated every input to cn_enhanced_driver as a predictor of `k`
     * (arg1, arg2, arg3, the gate global, the incoming shift, cross-frame
     * terms), leaving only data the function derives itself -- and SS106.1's
     * gate names the source: an object obtained around balance_area_image.
     * SS108.2 then corrected what that gate is: 0x106b5bd4 is a global NULL
     * SMART POINTER (assignment to out-params, AddRef at [eax+0x74]), so the
     * test is null / non-null, not a numeric threshold. Which of this
     * function's five return paths runs is therefore the discriminator.
     *
     * Only 6 bytes of this hook have ever been captured (balance_shift_4b6, at
     * arg3+0x0a), which is why SS108.1 could not emulate it: wine_host places
     * captured buffers at their real addresses and would fault on the first
     * dereference of arg 1.
     *
     * These three rows fix both problems together -- they capture the state
     * that decides the return path, AND they are exactly what the wine_host /
     * Unicorn harnesses need to execute the function on real inputs.
     *
     * Args from the v31 trace: (0x939fd38, 0x87e5278, 1, 0xf8404cc, 0,
     * 0x6d13d50, 0xf840020, 1). arg1 varies per frame (the scene/image), arg3
     * is the struct balance_shift_4b6 already reads 6 bytes of, arg6 varies
     * per frame and is adjacent to arg3's region. Sizes are deliberately
     * modest: an over-large row that comes back readable=false costs nothing,
     * but a fault-inducing one costs a scan.
     *
     * No new hook, no new dump kind, no thunk change -- fcn.10102b20 has been
     * hooked since v20. */
    { "balance_area_image", "bai_arg1", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x400, EXTRA_DUMP_ON_ENTRY, 0 },
    { "balance_area_image", "bai_arg3", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x200, EXTRA_DUMP_ON_ENTRY, 0 },
    { "balance_area_image", "bai_arg6", EXTRA_DUMP_STACK_PTR, 6, 0, 0, 0x400, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v34 (docs/74 SS124) -- the `this` object, the one pointer argument the
     * v32 rows above left uncaptured. wine_host loaded all 43,697 v32 buffers
     * and resolved args 1/3/5/6 on all 40 calls, then faulted on the first
     * call: unbounded recursion in ntdll's exception dispatcher, a fault
     * raised while handling a fault.
     *
     * SS123's trick does not rescue this one. `ecx` gives the ADDRESS for free
     * on every call (0x939fd38, identical across all 40), but no dump holds the
     * CONTENTS -- checked against all 89,040 dumps in the capture, not just the
     * ones labelled for this hook. The nearest is poly_input_r at 0x93a0020,
     * 0x2e8 bytes past it. Likewise args 16..24: no dump covers the stack
     * region on any of the 40 calls. Both gaps are real, which is why this row
     * and the STACK_DWORDS_LOGGED 16 -> 32 bump exist.
     *
     * THIS_OFFSET rather than STACK_PTR index 0: ecx and stack_dwords[0] hold
     * the same value here, but reading ecx does not assume the callee also
     * receives `this` on the stack.
     *
     * Corrects an earlier reading in SS124's own working notes: "the entire
     * disassembly contains exactly one this-relative access, [esi+0x74], so a
     * zeroed `this` is survivable". That came from grepping three registers for
     * positive hex offsets and cannot see arg_8h loaded into another register
     * and dereferenced. A grep over a register subset is not a reachability
     * argument -- run the walk, per CLAUDE.md.
     *
     * 0x200 is deliberately modest and stays inside the 0x2e8 gap to the next
     * known object. Not claimed: that this object has no pointer-valued fields
     * of its own needing further rows. That is unknown until a capture lands.
     *
     * No new hook and no new dump kind -- fcn.10102b20 has been hooked since
     * v20 and EXTRA_DUMP_THIS_OFFSET since v21. */
    { "balance_area_image", "bai_this", EXTRA_DUMP_THIS_OFFSET, 0, 0, 0, 0x200, EXTRA_DUMP_ON_ENTRY, 0 },
    { "color_adjust_shift", "impl_fields", EXTRA_DUMP_THIS_OFFSET, 0, 0x0c, 0, 0x28, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v35 (docs/74 SS135) -- the ICC source/dest max, the LAST unknown blocking
     * the algorithmic fix for the washed-out defect.
     *
     * SS134 traced the lifted black point to a domain disagreement: DRA targets
     * paperMin/paperMax = 1200/2000, while this port's pre-ICC encode
     * (rpd12_to_icc_u8, x255/4095) assumes a full 0..4095 domain in which black
     * must be ~924. That is a ~500 RPD lift, and it IS the washed-out look
     * (SS133.1: our sRGB p1 36/86/68 against the vendor's 10/11/10).
     *
     * Either reading can be made to fit, and ONE number decides which.
     * ImaICCEffectOp (0x1016ede0) loads its scales as doubles and pushes both
     * into the transform call --
     *
     *     0x1016ee84   fld qword [esi + 0x120]     ; dest max
     *     0x1016ee93   fld qword [esi + 0x118]     ; source max
     *
     * If source max is 4095, the x255/4095 encode is right and a pipeline stage
     * is MISSING between tone and ICC. If it is the paper range (or 32767), the
     * ENCODE is wrong and nothing is missing. This hook's own row above already
     * records the scale as "explicitly UNRESOLVED in docs/62 SS12.4.2 -- a live
     * capture of this+0x118/this+0x120 settles it directly".
     *
     * Not obtainable from what is already on disk (SS135.3): icc_effect_op logs
     * ecx on all 3,783 v34 calls and resolves to a SINGLE `this`, but that
     * object is covered by no dump -- checked against every buffer in the
     * capture, the way SS123 recovered FUGC's state successfully. The profile
     * DPIs carry only the OUTPUT description (dataType = U8, colorSpaceMin/Max
     * = 0/255); the source max is set at runtime.
     *
     * 0x20 bytes from +0x110 covers both doubles with margin. THIS_OFFSET reads
     * regs->ecx + derefOffset, and this hook is __thiscall -- its body is
     * `mov esi, ecx` after an ordinary SEH prologue. No new hook and no new
     * dump kind: hooked since v13, EXTRA_DUMP_THIS_OFFSET since v21. */
    { "icc_effect_op", "icc_scales", EXTRA_DUMP_THIS_OFFSET, 0, 0x110, 0, 0x20, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v36 -- the worker's inputs. It takes 13 stack dwords; several are
     * pointers it dereferences (the Unicorn harness faults on nulls), and the
     * int16 args are read with `movsx word [arg_ch]` / `[arg_14h]` etc. These
     * rows dump the four pointer-looking args so the harness can be driven on
     * real data and a port diffed bit-exact against it. Sizes are deliberately
     * modest: an over-large row that returns readable=false costs nothing, a
     * fault-inducing one costs a scan (docs/74 SS108.1's own rule). */
    /* v37 -- CORRECTED indices. v36 used 0/1/2 and every dump came back
     * readable=false: SS142.1 had already established that arg0 is the pixel
     * COUNT and arg1/arg2 are scalars, so the hook dereferenced an integer and
     * two scalars as pointers. The three planar RGB pointers are args 10/11/12
     * (base, base+n*2, base+n*4). scpw_this is dropped: the worker is reached
     * by a plain E8 from 0x102127d0 with everything pushed, so ECX is not a
     * `this` at its entry. arg8 is the in/out control block the worker reads
     * its mode word from (SS142.5), so it is dumped instead. */
    /* v46 -- widened 0x400 -> 0x8000 and turned into ENTRY+EXIT pairs.
     * v37 pinned these three as the planar R/G/B pointers (args 10/11/12,
     * base / base+n*2 / base+n*4) and dumped 0x400 = 512 samples each, which
     * is enough to show the pointers are right but not enough to fit a
     * transfer curve. 0x8000 = 16,384 samples per plane matches what
     * `lut_src` already uses for the same job on the TLB side.
     * BOTH: the worker transforms these planes in place, so the pair is its
     * input and its output. maxDumps 24 = 12 matched pairs out of 43 calls;
     * the ctrl/out control blocks are small and stay uncapped so every call's
     * mode word is recorded even after the plane dumps stop. */
    { "scp_lut_worker", "scpw_plane_r", EXTRA_DUMP_STACK_PTR, 10, 0, 0, 0x8000, EXTRA_DUMP_ON_BOTH, 24 },
    { "scp_lut_worker", "scpw_plane_g", EXTRA_DUMP_STACK_PTR, 11, 0, 0, 0x8000, EXTRA_DUMP_ON_BOTH, 24 },
    { "scp_lut_worker", "scpw_plane_b", EXTRA_DUMP_STACK_PTR, 12, 0, 0, 0x8000, EXTRA_DUMP_ON_BOTH, 24 },
    { "scp_lut_worker", "scpw_ctrl", EXTRA_DUMP_STACK_PTR, 8, 0, 0, 0x40, EXTRA_DUMP_ON_BOTH, 0 },
    { "scp_lut_worker", "scpw_out", EXTRA_DUMP_STACK_PTR, 9, 0, 0, 0x40, EXTRA_DUMP_ON_BOTH, 0 },
    /* v38 (docs/74 SS144) -- PolyPixel's coefficient object, arg0.
     *
     * The vendor calls tlb_polypixel in two phases: early (the inversion this
     * port already does at pakon_decode.py:459) and again on the full frame
     * immediately before every icc_effect_op -- the exact position SS136 says a
     * transform is missing. arg0 is the coefficient object and takes two
     * distinct values across the capture, 0x07173a74 and 0x07173b10, neither
     * covered by any v37 dump.
     *
     * A 3x10 poly for 3 channels is 30 doubles = 0xF0 bytes; 0x180 covers that
     * with room for a header without straying far. SS108.1's rule applies: an
     * over-large row that returns readable=false costs nothing, a
     * fault-inducing one costs a scan. */
    /* v40 (docs/74 SS144.6) -- PolyPixel's REAL coefficients, from `this`.
     *
     * fcn.1000d880 (TLB.dll) is __thiscall: `mov esi, ecx` at 0x1000d8a1, then
     * `lea ecx,[esi+0x50]` and `lea edx,[esi+0xc8]` -- the coefficient blocks
     * are INLINE in `this`, not behind a pointer, and not in arg0. v38/v39
     * dumped arg0 (per-image data) because that label was assumed rather than
     * read out of the disassembly; those rows are removed here.
     *
     * `this` is a single object (0x71756fc) across every call, so what these
     * rows answer is whether its coefficients are REWRITTEN between the early
     * inversion phase and the pre-ICC phase (SS144.1). If they are, the second
     * pass is a distinct transform this port does not perform. A 3x10 poly is
     * 30 doubles = 0xF0 B, so 0x100 from each block covers it. */
    { "tlb_polypixel", "poly_this50", EXTRA_DUMP_THIS_OFFSET, 0, 0x50, 0, 0x100, EXTRA_DUMP_ON_ENTRY, 0 },
    { "tlb_polypixel", "poly_thisc8", EXTRA_DUMP_THIS_OFFSET, 0, 0xc8, 0, 0x100, EXTRA_DUMP_ON_ENTRY, 0 },
    /* docs/74 SS72.7 (v21) -- sba_order_fpo_calc (0x1028b8d0) extra dumps.
     *
     * The question: SS72.3 proved this function's own top level writes only
     * pref_data+0x3e on the live-firing case, NOT the orderFpo Y/U/V triple
     * at pref_data+0x0/+0x2/+0x4. Either one of its 8 unread helpers writes
     * that triple (pref_data threaded in as a hidden arg), or something else
     * entirely does. This capture answers it empirically.
     *
     * WHY ENTRY-ONLY IS SUFFICIENT (a real deviation from SS72.7's own
     * proposed spec, made deliberately, not by oversight): LogExtraDumps is
     * called ONLY from HookEntryC (hookcore.c ~line 645), never from the
     * exit path -- extra dumps physically cannot fire on return with this
     * engine as built, and adding that would be a real engine change with
     * its own risk (at exit the args have been popped; sp no longer points
     * at a valid arg frame). It is not needed: this function is called 5x
     * per frame with the SAME pref_data pointer (arg 12, both call sites,
     * SS72.2), so consecutive ENTRY dumps give before/after across calls
     * 1->2, 2->3, 3->4, 4->5 directly, and the state AFTER the 5th call is
     * already captured by the existing `sba_preference`/`pref_data` row
     * above -- SS72.5 proved 0x1028b8d0's calls all precede Preference's own
     * single call in the same per-frame pass. Five entry dumps plus one
     * existing Preference dump = six observations of the same 0x64-byte blob
     * spanning all five calls, which is exactly the before/after series the
     * question needs.
     *
     * WHY NO 13 RAW-ARG ROWS (SS72.7 proposed 13x EXTRA_DUMP_STACK_PTR):
     * they would be redundant AND wrong-shaped. The engine already logs the
     * first STACK_DWORDS_LOGGED (=16, hookcore.c line 52) raw stack dwords on
     * every entry, and this function takes 13 args -- so all 13 raw arg
     * VALUES are captured for free in the existing "stack_dwords" field.
     * EXTRA_DUMP_STACK_PTR would instead DEREFERENCE each one, which is not
     * what SS72.7 wanted from those rows. Keeping them out also keeps this a
     * cheap addition on the real box.
     *
     * IMPORTANT -- this dump self-checks SS72.2's own arg table rather than
     * trusting it: SS72.2 rates its 13-arg mapping Tier 3 (static, cross-
     * checked two ways, NOT live-confirmed). If arg 12 is not really
     * scene+0x38a2, pref_data_before dumps something else and the mismatch is
     * itself the finding -- and the raw stack_dwords in the same JSONL line
     * give the ground truth to re-derive the real mapping from. Nothing here
     * assumes SS72.2 is right.
     *
     * arg 5 (the DPI-blob-copy-or-zero input SS72.4 traced) and arg 11
     * (fosDmin, scene+0x290c) are dumped too: SS72.4 found arg 5 has TWO
     * different provenances at the two call sites (a copy of the same
     * DPI-static blob Preference reads, vs explicitly zeroed), and which one
     * a real frame uses is one of the three unknowns SS72.6 named as
     * blocking a Unicorn harness. Dumping it settles that from real data. */
    { "sba_order_fpo_calc", "pref_data_before", EXTRA_DUMP_STACK_PTR, 12, 0, 0, 0x64, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg5_blob", EXTRA_DUMP_STACK_PTR, 5, 0, 0, 0x48, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "fos_dmin", EXTRA_DUMP_STACK_PTR, 11, 0, 0, 0x10, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v22 (docs/74 SS73/SS74) -- the remaining six POINTER arguments, so a
     * Unicorn harness can execute 0x1028b8d0 on real captured inputs and be
     * diffed bit-exact against the six known-good orderFpo triples SS73.2
     * already recorded. v21 dumped only args 5/11/12; args 0/1/2/6/7/10 are
     * pointers whose CONTENTS have never been captured, and a Unicorn run
     * cannot be built without them (SS72.6 refused to build one precisely
     * because inventing them is forbidden).
     *
     * Sizes are deliberately generous-but-bounded; every row is
     * IsBadReadPtr-guarded like the rest, so an over-large request degrades
     * to `"readable":false` rather than crashing. Total added ~1.5 KB per
     * call x 24 calls ~= 37 KB per capture -- negligible next to the
     * existing 0x84000-byte poly_input_r row.
     *
     * Arg->offset mapping below is LIVE-CONFIRMED from v21's own raw
     * stack_dwords (docs/74 SS73.4 and the scene-base arithmetic in SS75):
     * deriving the scene base from arg12 (= scene+0x38a2) and subtracting
     * shows args 0/1/2/7/11/12 land exactly on SS72.2's claimed offsets
     * (+0x1a, +0x3bc8, +0x388c, +0x3c34, +0x290c, +0x38a2). **arg 6 does
     * NOT** -- SS72.2 claimed scene+0x5978, but the real pointer sits
     * ~0xc65f0 BELOW the scene base, i.e. a separate allocation entirely.
     * It is dumped here as an unknown buffer rather than as a scene field,
     * and its size is a guess (0x100) for that reason -- if it comes back
     * truncated or unreadable, that is itself information.
     * args 5 and 10 are adjacent caller locals (arg10 == arg5 + 0x64). */
    { "sba_order_fpo_calc", "arg0_dens", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x40, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg1_cbank", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x400, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg2_388c", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x20, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg6_unknown", EXTRA_DUMP_STACK_PTR, 6, 0, 0, 0x100, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg7_3c34", EXTRA_DUMP_STACK_PTR, 7, 0, 0, 0x40, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg10_local2", EXTRA_DUMP_STACK_PTR, 10, 0, 0, 0x64, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v23 (docs/74 SS76) -- the v22 sizes were too small, proven by running
     * the real function under Unicorn on v22's own data: it early-exits with
     * return code 0x18bd at the bounds check at 0x1028b928/938/945/94e, which
     * reads `word [edx+0x104]` and `word [edx+0x106]` where edx == arg 6.
     * v22 dumped only 0x100 bytes of arg 6, so those two words fell outside
     * the capture and the harness read poison. That was the one size v22's
     * own comment flagged as a guess -- now measured, not guessed again.
     *
     * These rows are ADDITIVE alongside the v22 rows above, not replacements.
     * A larger request is IsBadReadPtr-guarded as a whole range, so if a
     * buffer turns out to be smaller than asked for, the big row comes back
     * `"readable":false` while the original small row still carries its data.
     * Belt and braces: cheap (~11.5 KB/call, ~276 KB per capture) against the
     * cost of another hardware round trip.
     *
     * Sizes derived from a mechanical scan of the function's own disassembly
     * for real memory operands (lea excluded -- it computes an address
     * without touching memory, and this function does use lea with very large
     * constants like +0x11436 as plain arithmetic, which would badly mislead
     * a naive grep): the deepest real accesses are [edx+0x106] (arg 6),
     * [edi+0x158], and a block of dword writes/reads spanning
     * [esi+0xb7c]..[esi+0xbac]. Which argument esi/edi hold at those points
     * is not yet pinned (both are reassigned several times), so arg 5 and
     * arg 7 are both sized past 0xbb0/0x158 respectively rather than
     * asserting a mapping this pass has not established. */
    /* v25: arg0 must reach 0x2880. docs/74 SS76.4's three dens arrays are at
     * arg0+0x1440, +0x1b00 and +0x21c0, each 864 x int16 = 0x6c0 bytes, so the
     * last one ends at 0x2880. v24's 0x1500 covered only the first ~96 of 864
     * densY samples -- confirmed exactly by the harness faulting at arg0+0x1440
     * and then arg0+0x1b00. 0x3000 leaves margin. */
    { "sba_order_fpo_calc", "arg0_big", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x3000, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg1_big", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x1000, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg2_big", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x200, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg5_big", EXTRA_DUMP_STACK_PTR, 5, 0, 0, 0xC00, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg6_big", EXTRA_DUMP_STACK_PTR, 6, 0, 0, 0x400, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg7_big", EXTRA_DUMP_STACK_PTR, 7, 0, 0, 0x1200, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg10_big", EXTRA_DUMP_STACK_PTR, 10, 0, 0, 0x200, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg11_big", EXTRA_DUMP_STACK_PTR, 11, 0, 0, 0x1200, EXTRA_DUMP_ON_ENTRY, 0 },
    { "sba_order_fpo_calc", "arg12_big", EXTRA_DUMP_STACK_PTR, 12, 0, 0, 0x200, EXTRA_DUMP_ON_ENTRY, 0 },
    /* v26 (docs/74 SS86) -- the interpreter's own context and PROGRAM.
     *
     * Calling convention (r2 af+pdf): args are sp[0..3]; `mov ebp,[arg_3ch]`
     * at 0x102aadf5 resolves by stack-delta (entry - 0x2c - 4 push, so
     * [esp+0x3c] == entry+0xc) to **arg index 2**, and `mov edi,[ebp+4]` at
     * 0x102aadfb is the program pointer. So:
     *   vm_ctx     = *sp[2]            -- the interpreter's context struct
     *   vm_program = *(*(sp[2] + 4))   -- the bytecode itself
     * EXTRA_DUMP_DEREF_PTR is exactly the second shape (deref the stack arg,
     * add the offset, deref again, dump from there).
     *
     * 0x1000 of program is a deliberate over-ask: the real length is unknown
     * (the halt opcode 0xff terminates it, so it is self-delimiting when
     * walked offline) and an over-read degrades to "readable":false rather
     * than truncating silently. If it comes back unreadable at 0x1000 the
     * smaller ctx dump still lands and the size can be stepped down. */
    /* v27 CORRECTION: v26 used stackIndex 2 and every dump came back
     * readable=false because sp[2] is 0. The prologue has TWO pushes before
     * the load, not one:
     *     0x102aadf3  push ebx
     *     0x102aadf4  push ebp        <- missed in the v26 derivation
     *     0x102aadf5  mov ebp,[esp+0x3c]
     * so esp = entry-0x2c-8 and [esp+0x3c] = entry+8 = ARG 1. The live
     * capture confirms it: sp[1] = 0x08e0e7c8 (a real pointer) while
     * sp[2] = 0x00000000.
     *
     * All four low indices are dumped rather than just the derived one.
     * This arg-index arithmetic has now been got wrong three times across
     * v22/v24/v26, each costing a hardware round trip; four small dumps cost
     * ~1 KB per call and remove the class of error entirely. Whichever index
     * is right lands, the rest come back readable=false and are ignored. */
    { "sba_vm_interp", "vm_ctx0", EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x40, EXTRA_DUMP_ON_ENTRY, 4 },
    { "sba_vm_interp", "vm_ctx1", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x40, EXTRA_DUMP_ON_ENTRY, 4 },
    { "sba_vm_interp", "vm_ctx2", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x40, EXTRA_DUMP_ON_ENTRY, 4 },
    { "sba_vm_interp", "vm_ctx3", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x40, EXTRA_DUMP_ON_ENTRY, 4 },
    { "sba_vm_interp", "vm_prog0", EXTRA_DUMP_DEREF_PTR, 0, 4, 0, 0x800, EXTRA_DUMP_ON_ENTRY, 4 },
    { "sba_vm_interp", "vm_prog1", EXTRA_DUMP_DEREF_PTR, 1, 4, 0, 0x800, EXTRA_DUMP_ON_ENTRY, 4 },
    { "sba_vm_interp", "vm_prog2", EXTRA_DUMP_DEREF_PTR, 2, 4, 0, 0x800, EXTRA_DUMP_ON_ENTRY, 4 },
    { "sba_vm_interp", "vm_prog3", EXTRA_DUMP_DEREF_PTR, 3, 4, 0, 0x800, EXTRA_DUMP_ON_ENTRY, 4 },
    /* v28 (docs/74 SS88) -- the ONE row that unblocks Y's `L` term.
     *
     * SS88 ported the interpreter and located `L` exactly: the 23rd record
     * with type == 1 is record 156, whose whole body is `PUSH v133 ; STORE
     * v156`, so L == vars[133]. Computing it needs the input vector `in[]`,
     * which lives at (fpo_calc's arg 11) + 0x3c, 736 x u32.
     *
     * WHY NO EXISTING CAPTURE CAN SUPPLY IT. Extra dumps fire on ENTRY only
     * (LogExtraDumps is called solely from HookEntryC), and `in[]` is filled
     * later inside the same 0x1028b8d0 call, before fcn.102ac310 runs. The
     * region IS already inside arg11_big above -- and measured across all 48
     * arg11_big dumps of both v27 rolls it is 736 u32 of ZERO, with the whole
     * 4608-byte buffer holding just 5 non-zero words (indices 992..996,
     * outside in[]). So this is a timing gap, not a coverage gap, and no
     * re-reading of captures in hand can close it.
     *
     * sba_order_fpo_helper (0x1028ae00) already runs AFTER the fill -- it is
     * called from 0x1028c023, downstream of it -- and is already hooked, so
     * this needs no new hook, no thunk, and no HOOKCORE_MAX_HOOKS change:
     * one dump row only.
     *
     * WHICH ARG: MEASURED, NOT DERIVED. This arg-index arithmetic has been
     * got wrong three times (v22, v24, v26), each costing a hardware round
     * trip, so it was not derived from the prologue a fourth time. Both
     * hooks already log their first 16 raw stack dwords, so the answer was
     * read straight out of the v27 captures: for every helper call, exactly
     * ONE stack index equals the enclosing fpo_calc call's arg 11 --
     * index 1, uniquely, 12/12 on roll A and 12/12 on roll B. (argsPtr =
     * ebp+44 with the return address at ebp+40, hookstub.S:58-60, so
     * stack_dwords[0] is the FIRST argument.)
     *
     * WHY THE WHOLE BUFFER AND NOT arg1+0x3c. A STACK_PTR_OFFSET row at
     * +0x3c would re-stake the result on the offset being exactly right --
     * the same shape of assumption that cost v22 four bytes and v24 an
     * offset-vs-total misreading. Dumping from the base at 0x1200 subsumes
     * in[] wherever it starts (0x3c + 0xb80 = 0xbbc < 0x1200) and is byte-
     * for-byte comparable with arg11_big above: same buffer, same span, one
     * snapshot before the fill and one after. The diff of those two IS the
     * evidence that the fill happened. ~4.6 KB x 12 helper calls = ~55 KB
     * per capture. */
    { "sba_order_fpo_helper", "arg1_big_filled", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x1200, EXTRA_DUMP_ON_ENTRY, 0 },
    /* =================================================================
     * v46 -- THE REFERENCE-TRACE ROWS (2026-08-21)
     * =================================================================
     *
     * Everything above this line captures ONE question at a time: a row was
     * added, a scan was run, a section of docs/74 was written, and the next
     * pass added another row. What has never existed is a capture that
     * records the vendor's own state at EVERY stage boundary ON THE SAME
     * FRAMES, which is what turns "this stage matches on synthetic input"
     * into "this stage matches the vendor, on the vendor's own data, at both
     * its input and its output". These rows are that trace.
     *
     * THE SCENE STRUCT -- derived this pass, af+pdf, cross-checked three ways
     * ---------------------------------------------------------------------
     * PakonIMAu.dll md5 eea9dcf78ee21d4f7c515a6c2512242d (the same copy every
     * docs/74 section cites), r2 `af`+`pdf` from the real function entries.
     *
     * fcn.10069490 (cn_enhanced_driver) is `push ebp; mov ebp,esp` and does
     * `mov esi, [ebp+0xc]` at 0x100694cc -- so ESI, the register every
     * per-frame stage's arguments are built from, is the SECOND argument,
     * i.e. **stack_dwords[1]**. Reading its call sites gives the arguments of
     * every stage below directly, which is worth far more than re-deriving
     * each callee's prologue (the arithmetic this project has got wrong in
     * v22, v24 and v26, once per hardware round trip):
     *
     *   0x100697d9  fugc_analyze         push esi | esi+4 | holder | &status
     *   0x10069837  balance_area_image   push esi+0x4ac | b[esi+0x29] | holder | &status
     *   0x1006988a  analyze_area         push &loc | [esi+0x30] | b[esi+0x4c] |
     *                                         b[esi+0x29] | esi+0x4b6 | 1 |
     *                                         holder | &status
     *   0x100698e4  analyze_attributes   push esi | esi+4 | holder | &status
     *   0x100699a3  analyze_falloff      push esi | edi | holder | &status
     *   0x100699eb  analyze_auto_tone    push esi | edi | holder | &status
     *   0x100694cf  analyze_post_balance push [esi+0x2c] | esi+4 | esi+0x4ac |
     *                                         holder | &status
     *
     * pushes are right-to-left, so the LAST push is stack_dwords[0]. The
     * `holder` slot is the small object fcn.10006880 constructs in place
     * (`mov ecx,esp` then `call 0x10006880`, which is `ret 4`).
     *
     * THREE INDEPENDENT CONFIRMATIONS that ESI is the scene and the scene is
     * 0x64DC bytes:
     *   1. docs/74 SS95 recorded cn_enhanced_driver's live pointer values --
     *      150139080, 150164900, 150190720 -- whose stride is exactly 25820
     *      = 0x64DC.
     *   2. fcn.100fb730 (analyze_auto_tone) does `mov eax,[ebp+0x14]` (arg 4)
     *      then `mov [eax+0x64d0], edi` at 0x100fb787 -- a write to the LAST
     *      dword of a 0x64DC struct, and arg 4 is ESI per the call site above.
     *      It is the only >=3-digit structure offset in that whole 5,695-byte
     *      function.
     *   3. The already-live, already-proven `balance_shift_4b6` row reads
     *      arg index 3 + 0x0a on balance_area_image; the call site shows
     *      index 3 == esi+0x4ac, so that row reads esi+0x4b6 -- which is what
     *      SS105 named it after. An independent derivation landing on an
     *      existing row's known-good address is the check that matters.
     *
     * So `stack_dwords[1]` at cn_enhanced_driver and `stack_dwords[3]` at
     * fugc/falloff/auto_tone/attributes are the SAME 0x64DC object, and a
     * 0x64DC dump captures exactly one scene without reading into the next
     * (they are contiguous). Every narrow per-frame row above -- +0x4b6,
     * +0x3a38, +0x3a30, +0x5074, +0x38a2, +0x290c, +0x64d0 -- lives inside
     * it, so these rows SUBSUME them and, on the same capture, must AGREE
     * with them. check_v46.py tests exactly that, and a disagreement means
     * this derivation is wrong rather than that the vendor changed.
     *
     * WHY WHOLE-SCENE AND NOT NARROW ROWS AT KNOWN OFFSETS. Because the
     * open question (SS168, SS180, SS185: what produces the per-frame delta)
     * is "which field changed during this stage", and a narrow row can only
     * answer it for fields already suspected. An entry/exit pair of the whole
     * struct answers it for every field at once, and it is CHEAP: 0x64DC is
     * 25,820 bytes, ~52 KB hex-encoded, so all 39 frames at both ends of the
     * driver cost ~4 MB. The expensive rows in this table are the pixel
     * planes, which are half a megabyte each; the scalars are free by
     * comparison, which is why none of the rows below are capped.
     * ================================================================= */
    { "cn_enhanced_driver", "scene_in",  EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x64DC, EXTRA_DUMP_ON_ENTRY, 0 },
    { "cn_enhanced_driver", "scene_out", EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x64DC, EXTRA_DUMP_ON_EXIT,  0 },
    /* Per-stage brackets INSIDE the driver, in the driver's own call order.
     * Each is the same scene struct, so consecutive rows chain: fugc_scene's
     * exit state is balance's entry state, and so on. Diffing adjacent dumps
     * attributes every per-frame scalar change to the exact stage that made
     * it -- which is the measurement SS168 could not make and SS185 had to
     * infer forward from pixels. */
    { "fugc_analyze",        "fugc_scene", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x64DC, EXTRA_DUMP_ON_BOTH, 0 },
    { "analyze_attributes",  "attr_scene", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x64DC, EXTRA_DUMP_ON_BOTH, 0 },
    { "analyze_falloff",     "fall_scene", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x64DC, EXTRA_DUMP_ON_BOTH, 0 },
    { "analyze_auto_tone",   "tone_scene", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x64DC, EXTRA_DUMP_ON_BOTH, 0 },
    /* analyze_area is the one stage that does NOT receive the scene base: its
     * call site passes esi+0x4b6 as argument 4 (index 3) -- the balance shift
     * triple itself -- plus three scene bytes as scalars. 6 bytes at index 3
     * is therefore the shift as analyze_area sees it, entry and exit. This is
     * a deliberate duplicate of what scene_in/+0x4b6 already carries: it is
     * the cheapest possible cross-check that index 3 means what this comment
     * says it means, and it costs 26 dumps of 6 bytes. */
    { "analyze_area", "area_shift_4b6", EXTRA_DUMP_STACK_PTR, 3, 0, 0, 6, EXTRA_DUMP_ON_BOTH, 0 },
    /* ---------------------------------------------------------------------
     * CORRECTION to the SS168 `apb_arg0`/`apb_arg1` rows above.
     *
     * Those two rows dump analyze_post_balance's arguments 1 and 2 at 0x600
     * bytes each, on the stated grounds that "which one carries the scene is
     * NOT established, so both are dumped and +0x4b6 will land inside
     * whichever one it is". Reading the CALLER settles it, and the answer is
     * NEITHER: at 0x100694cf..0x10069503 the pushes are
     *
     *     [esi+0x2c] | esi+4 | esi+0x4ac | holder | &status
     *
     * so index 0 is a caller-owned status local and index 1 is the in-place
     * holder object fcn.10006880 builds -- a smart pointer, not the scene.
     * Both rows are readable and both are non-constant across calls, so they
     * PASS check_v44.py's acceptance test while carrying nothing that can be
     * matched to a per-frame k. That is worth stating plainly: the v44 check
     * accepted those rows, and acceptance never meant they held the scene.
     *
     * The shift triple is at index 2 + 0x0a (esi+0x4ac + 0x0a = esi+0x4b6),
     * exactly as for balance_area_image. Index 3 is the AnsImageData at
     * esi+4. Both are dumped ENTRY+EXIT here; the old rows are left in place
     * rather than deleted so the same capture proves the correction. */
    { "analyze_post_balance", "apb_shift_4ac", EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x40, EXTRA_DUMP_ON_BOTH, 0 },
    { "analyze_post_balance", "apb_img_desc",  EXTRA_DUMP_STACK_PTR, 3, 0, 0, 0x40, EXTRA_DUMP_ON_BOTH, 0 },
    /* ---------------------------------------------------------------------
     * shift_lut_builder (fcn.1006c4f0) -- the three built LUTs, at exit.
     *
     * Call site 0x100fe7e6..0x100fe807 inside analyze_post_balance, pushes
     * right-to-left:
     *
     *     idx0 = &out_lut_a   idx1 = &out_lut_b   idx2 = &out_lut_c
     *     idx3 = 0x1000 (= 4096, the entry count)
     *     idx4/5/6 = word[p+0] / word[p+2] / word[p+4]  -- the shift triple
     *
     * idx4/5/6 are plain integers and are already captured for free in the
     * existing `stack_dwords` field of every enter line, which is what the
     * task brief means by "post-rewrite shift as plain stack args". idx0/1/2
     * are pointers to CALLER LOCALS that the callee writes the LUT pointers
     * into, so the LUTs themselves need a double deref -- EXTRA_DUMP_DEREF_PTR
     * with derefOffset 0 is exactly `*(sp[idx]) + 0`, and it can only be read
     * AFTER the call, which is what EXTRA_DUMP_ON_EXIT is for. 4096 entries x
     * int16 = 0x2000 bytes each.
     *
     * This closes the loop on the applied balance: the same capture now holds
     * the shift triple that went IN (stack_dwords), the LUTs that came OUT
     * (here), the LUTs as applied (r_lut/g_lut/b_lut on the very next call),
     * and the pixels before and after (pixel_data / pixel_data_out). The
     * builder is already bit-exact against the DLL (SS167.5), so these rows
     * are a regression check on a solved stage rather than an open question --
     * but a trace with a hole where a solved stage should be is not a trace.
     *
     * idx3 == 0x1000 is also the self-check: check_v44.py already reads
     * stack_dwords[3] == 0x1000 for this hook, so if this index convention
     * were wrong that assertion would already be failing. */
    { "shift_lut_builder", "slb_lut_a", EXTRA_DUMP_DEREF_PTR, 0, 0, 0, 0x2000, EXTRA_DUMP_ON_EXIT, 0 },
    { "shift_lut_builder", "slb_lut_b", EXTRA_DUMP_DEREF_PTR, 1, 0, 0, 0x2000, EXTRA_DUMP_ON_EXIT, 0 },
    { "shift_lut_builder", "slb_lut_c", EXTRA_DUMP_DEREF_PTR, 2, 0, 0, 0x2000, EXTRA_DUMP_ON_EXIT, 0 },
    /* ---------------------------------------------------------------------
     * v46 -- FRAMING rows. Inert unless the three tlb_framing_* hooks are
     * enabled in hooks.cfg; see their table entries for why they ship off.
     *
     * All three use EXTRA_DUMP_THIS_OFFSET with derefOffset 0 -- the whole
     * object from its base, not `+0x6c`. That is deliberate and is the
     * lesson of v22/v24/v26 (three hardware round trips lost to an offset or
     * index that was derived rather than measured): dumping from the base at
     * a size that SUBSUMES the field of interest cannot be wrong about where
     * the field starts, and the offset can be confirmed offline from the
     * bytes. 0x6CC0 = 27,840 bytes covers +0x6c (the per-line trace,
     * 3 bytes/line, so up to ~9,200 lines) and +0x6ca8 (the warning word)
     * with margin, and it is ~56 KB hex-encoded per dump.
     *
     * `this` is assumed to be ECX at each of these entries -- which is NOT
     * verified, for the same reason the addresses are not: no TLB.dll here.
     * If ECX is not the framing object, these rows come back readable=false
     * or obviously wrong, which is itself the finding, and nothing else in
     * the capture is affected. */
    { "tlb_framing_entry",       "framing_obj",      EXTRA_DUMP_THIS_OFFSET, 0, 0, 0, 0x6CC0, EXTRA_DUMP_ON_BOTH,  0 },
    { "tlb_framing_driver",      "framing_drv_obj",  EXTRA_DUMP_THIS_OFFSET, 0, 0, 0, 0x6CC0, EXTRA_DUMP_ON_BOTH,  0 },
    { "tlb_framing_line_reduce", "framing_trace",    EXTRA_DUMP_THIS_OFFSET, 0, 0, 0, 0x6CC0, EXTRA_DUMP_ON_ENTRY, 6 },

    /* ---- v48: THE ROW THE FRAMING CAPTURE ACTUALLY NEEDED ----
     *
     * The row above is correct as far as it goes and is kept -- it captured
     * the object header, and its non-zero data ended at exactly +0x6cbf, the
     * last byte of esi+0x6cbc, confirming 0x6CC0 was the right size. But it
     * does NOT contain the per-line array, and the 2026-08-21 framing capture
     * proved it: `+0x6c` holds a POINTER (measured: 0x07890714, a heap address
     * ~0x18000 above the object at 0x07878630), not inline data.
     *
     * The mistake was reading this hook's own description -- "reads three
     * bytes per line from this+0x6c" -- as "the array is AT +0x6c". It is the
     * POINTER to the array that is at +0x6c.
     *
     * This is the v22/v24/v26 lesson INVERTED, and worth stating plainly
     * because the earlier rule actively pointed the wrong way here: "dump from
     * the base at a size that subsumes the field, so you cannot be wrong about
     * where it starts" defends against a wrong OFFSET. It is no defence at all
     * when the field is a POINTER -- subsuming a pointer just captures the
     * pointer. A base dump and a deref dump answer different questions and the
     * capture needs both.
     *
     * Size: the reduce reads 3 bytes per line, and the same capture measured
     * ~2,384 lines (obj+0x14 = 0x950 = 2384; ebx at entry = 0x94d = 2381), so
     * the array is ~7,152 bytes. 0x8000 subsumes that with room for a longer
     * roll -- up to 10,922 lines -- without assuming the exact count.
     *
     * Cap 6 as before; see the hook's own citation for why 6 is now known to
     * be generous rather than tight. */
    { "tlb_framing_line_reduce", "framing_lines",    EXTRA_DUMP_THIS_DEREF_OFFSET, 0x6c, 0, 0, 0x8000, EXTRA_DUMP_ON_ENTRY, 6 },

    /* ---- v49: the vendor's own FRAME LIST ----
     *
     * The 2026-08-21 capture let the ported cascade run on the vendor's real
     * per-line array for the first time, and both placed SIX frames with the
     * same warning word. What it could not check is WHERE: the entry writes
     * its frame list into the CALLER's buffer (arg3, `slots`), not into the
     * object -- the same capture showed the object itself changed at only
     * four bytes, +0x6c..+0x6f, i.e. the array pointer and nothing else.
     *
     * arg3 is stack_dwords[2] (index N-1; see the v48 correction above, which
     * this row is deliberately written to be consistent with). EXIT, because
     * at entry the buffer holds whatever the caller left there.
     *
     * Size: n_slots was 11 on the captured roll and each slot is three
     * dwords, so 132 bytes. 0x100 subsumes that and covers up to 21 slots
     * without assuming the count -- and n_slots is itself logged as arg2, so
     * a reader can always tell how much of the dump is live. */
    { "tlb_framing_entry",       "framing_slots",    EXTRA_DUMP_STACK_PTR, 2, 0, 0, 0x100, EXTRA_DUMP_ON_EXIT, 6 },

    /* ---- v53: the framing 14->8-bit derivation SOURCE (docs/74 SS194) ----
     *
     * The rows above give the vendor's finished 8-bit per-line summary
     * (framing_lines) and the placed frame list (framing_slots). What closes
     * FRAMING_PORTED is the OTHER side of the 14->8 quantisation: the 16-bit
     * CCD source and the geometry that maps it to those 8-bit lines. Three
     * rows, all inert unless the framing hooks are enabled in hooks.cfg.
     *
     * framing_setup_obj -- tlb_framing_setup's object header at EXIT (after
     * the allocator has stored +0x60/+0x64/+0x6c and the count), from the base
     * so the exact offsets can be confirmed offline, same base-dump discipline
     * as framing_obj. Capped at 4 (setup runs a handful of times, not hot).
     *
     * framing_src16 -- the contiguous 16-bit CCD image base, reached by the
     * new EXTRA_DUMP_THIS_DEREF2_OFFSET: object +0x60 holds a POINTER to a
     * row-pointer table, and table[0] is the image base (a DOUBLE deref). Read
     * at line_reduce ENTRY, where the array is already filled. 0x8000 bytes is
     * a window into the top of the image, not the whole frame -- enough to
     * correlate the 16-bit source against the 8-bit summary offline; capped 6.
     *
     * framing_rowtable -- the row-pointer table itself (object +0x60, single
     * deref = the same EXTRA_DUMP_THIS_DEREF_OFFSET framing_lines uses), so the
     * per-row stride/layout of the 16-bit image can be resolved offline rather
     * than assumed. 0x1000 bytes = up to 1024 row pointers; capped 6.
     *
     * All three are TIER 3 (static mapping) until this capture runs; a wrong
     * offset or a non-object ecx comes back readable=false, which is the
     * finding, and nothing else in the capture is disturbed. */
    { "tlb_framing_setup",       "framing_setup_obj", EXTRA_DUMP_THIS_OFFSET,         0,    0, 0, 0x6CC0, EXTRA_DUMP_ON_EXIT,  4 },
    { "tlb_framing_line_reduce", "framing_src16",     EXTRA_DUMP_THIS_DEREF2_OFFSET,  0x60, 0, 0, 0x8000, EXTRA_DUMP_ON_ENTRY, 6 },
    { "tlb_framing_line_reduce", "framing_rowtable",  EXTRA_DUMP_THIS_DEREF_OFFSET,   0x60, 0, 0, 0x1000, EXTRA_DUMP_ON_ENTRY, 6 },

    /* ---------------------------------------------------------------------
     * v47 -- sba_measure (fcn.102aece0). PROVENANCE for B1.
     *
     * The ports of this function's mask and of its packer are tier 1 for
     * EQUIVALENCE and tier 4 for PROVENANCE: no capture hooks either, so
     * their inputs are synthetic (docs/74 SS196). These rows are what turn
     * "the arithmetic matches" into "these are the values a real frame
     * produces", which is the question B1 actually asks.
     *
     * The object rows follow v46's rule and dump from the OBJECT BASE at a
     * size that subsumes every field, rather than at a derived offset --
     * the lesson of v22/v24/v26. Measured written extents are +0x6..+0x1c,
     * +0x3c..+0xb7c and +0xc20..+0xf80, so 0x1000 from the base covers the
     * headers, the whole 720-slot vector and the whole 864-byte mask, and
     * cannot be wrong about where any of them begins.
     *
     * ENTRY is not redundant with EXIT: SS196 confirmed the cross-call read of
     * [obj+0x7b8] (vector slot 479) at 0x102b0da5 is LIVE, so invocation N
     * consumes what N-1 wrote. Only the entry side shows what was read.
     *
     * Caps: 18 = 3 calls/frame x 6 frames, matching the pixel-plane budget
     * the rest of the reference trace uses.
     *
     * arg1 is the sample image: six planes x 864 samples x int16 = 10,368 B,
     * stride 864, grid 24 rows x 36 cols (SS192.2, derived from the plane
     * bases and the `cmp eax,0x18` row bound, not assumed). arg2 is the six
     * int32 subtracted from every band sample -- 24 B, and the per-channel
     * shape of the defect makes it worth having.
     */
    /* v48 CORRECTION — these four were OFF BY ONE in v47.
     *
     * `stack_dwords[0]` is **arg1**, not the return address: hookcore.h's
     * HookRegs comment says argsPtr points at "stack-passed args, if any,
     * [which] immediately follow" retAddr, and HookEntryC sets
     * `sp = (DWORD *)argsPtr`. So argN is at index N-1. v47 used 10/1/2 for
     * arg10/arg1/arg2 and should have used 9/0/1.
     *
     * The 2026-08-21 reference capture proved it, and is worth reading as a
     * worked example of how a wrong index hides:
     *
     *   - `measure_bandsub` at idx 2 resolved to 0x0000fffe and was
     *     UNREADABLE on all 18 calls — the loud failure, and the clue.
     *   - `measure_obj` at idx 10 resolved to 0x08dc60b0, which WAS readable
     *     and did contain plausible mask-shaped and vector-shaped data. It
     *     was simply a different, nearby object. The tell was that
     *     measure_obj_pre and measure_obj_post were byte-identical on all 18
     *     calls while `scene_in`/`scene_out` differed on 6 of 6 — i.e. the
     *     exit mechanism worked fine and the thing being dumped genuinely
     *     never changed, because sba_measure does not write it.
     *   - the real object is `esi` (docs/74 SS192: arg10 == esi), and the
     *     capture shows esi == 0x08dc89bc == stack_dwords[**9**].
     *
     * The lesson is the same one as the framing +0x6c pointer, from the other
     * side: a readable dump full of plausible-looking bytes is not evidence
     * that the address was right. `unreadable` is a gift; silent plausibility
     * is the dangerous case, and only a cross-check — here, "did the buffer
     * this function is documented to write actually change?" — catches it. */
    { "sba_measure", "measure_obj_pre",  EXTRA_DUMP_STACK_PTR, 9, 0, 0, 0x1000, EXTRA_DUMP_ON_ENTRY, 18 },
    { "sba_measure", "measure_obj_post", EXTRA_DUMP_STACK_PTR, 9, 0, 0, 0x1000, EXTRA_DUMP_ON_EXIT,  18 },
    { "sba_measure", "measure_samples",  EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0x2880, EXTRA_DUMP_ON_ENTRY, 18 },
    { "sba_measure", "measure_bandsub",  EXTRA_DUMP_STACK_PTR, 1, 0, 0, 0x18,   EXTRA_DUMP_ON_ENTRY, 18 },
    /* v52 -- the LAST two uncaptured inputs to fcn.102aece0. arg7 (`en`, the
     * per-slot enable/gate array) and arg8 (`par`, the per-slot parameter
     * array) are POINTERS; v47-v51 logged their addresses in stack_dwords[6]
     * and [7] but never dereferenced them, so the 720-slot vector could only
     * be reconstructed to 506/720 (docs/74 -- synthetic `default_en`/`build_par`
     * in the closure emulation). A search of all 28 captures (10.3 GB, Aug17-v51)
     * confirmed NEITHER is on disk: the only 3 scans that hook sba_measure dump
     * the same 4 labels above, none of them arg7/arg8. These are per-frame
     * VARIABLE (mode_pack=0: both vary, laid out adjacently as par == en+0xdc;
     * mode_pack=1: en is the shared constant 0x0839d0f0 but par still varies),
     * so they must be CAPTURED, not reconstructed. `aim` (arg9, stack_dwords[8])
     * is genuinely NULL, not uncaptured, so with these two the input set is
     * complete. Sizes subsume the disassembly-derived read extents: `en` is
     * read to +0x24 (gate words 0..6/0x0E, hist bytes to 0x24 -- 0x102af2bf,
     * 0x102af35a); `par` to +0x56 (hue/chroma words + bias@0x56 -- 0x102af145,
     * 0x102af261). Both reads are inside fcn.102aece0, so ON_ENTRY precedes use.
     * These close 506/720 -> 720/720 = per-frame colour balance PROVENANCE. */
    { "sba_measure", "measure_en",       EXTRA_DUMP_STACK_PTR, 6, 0, 0, 0x40,   EXTRA_DUMP_ON_ENTRY, 18 },
    { "sba_measure", "measure_par",      EXTRA_DUMP_STACK_PTR, 7, 0, 0, 0x80,   EXTRA_DUMP_ON_ENTRY, 18 },

    /* v54 -- the frame->grid sampler INPUT (docs/74; RE 2026-08-24).
     * sba_measure's `measure_samples` (above) is the 24x36x6 SBA GRID -- the
     * OUTPUT of AnsImageData::blockAverage. The one remaining unported colour
     * stage is the sampler that produces that grid, and porting it needs its
     * INPUT: the resized analysis image blockAverage reads. These two rows
     * capture it on the SOURCE AnsImageData (ecx):
     *   blkavg_src_desc -- the src header (ecx+0), 0x24 bytes: layout @+0x4,
     *     dims @+0xc/+0x10, pixptr @+0x20.
     *   blkavg_src_px   -- the analysis-image pixels, *(ecx+0x20), a SINGLE
     *     deref (same pattern as framing_lines / area pixel_data). 0x84000 ==
     *     HOOKCORE_EXTRA_DUMP_MAX_BYTES, the read-safe ceiling.
     * Both ON_ENTRY (the grid input exists before the call); capped at 40 to
     * catch the SBA invocation across a few frames without swamping -- block-
     * average is per-image, not per-pixel. No dst/grid row here: the default
     * stack_dwords logged on entry already record the args, and the finished
     * grid is matched offline against the existing measure_samples dump.
     * Inert unless sba_block_average is enabled in hooks.cfg (OFF by default). */
    { "sba_block_average", "blkavg_src_desc", EXTRA_DUMP_THIS_OFFSET,       0,    0, 0, 0x24,    EXTRA_DUMP_ON_ENTRY, 40 },
    { "sba_block_average", "blkavg_src_px",   EXTRA_DUMP_THIS_DEREF_OFFSET, 0x20, 0, 0, 0x84000, EXTRA_DUMP_ON_ENTRY, 40 },

    /* v55 -- the RTTI-pinned frame->grid sampler (docs/74; RE 2026-08-24,
     * /tmp/pakon_re/sampler/). v54's fcn.100d9930 was pan-detect's block-average
     * and fired 0x; the real grid-fill op is ImaBlockAverageOpTT<short,double>::
     * process = fcn.10154ea0 (RTTI: TD 0x10697fd8 -> COL 0x105e6360 -> vtable
     * 0x1058ddf4 slot 10). Three hooks, all OFF by default (opt-in via
     * hooks.cfg): A confirms the op fires + captures the block factor and
     * analysis dims; B is the clean 1-deref analysis-image PIXEL capture that
     * closes the port; C is the resize-EXIT fallback for the dims.
     *
     * HOOK A -- paxelize_blockavg_op @ 0x10154ea0 (__thiscall, ecx = the OP).
     * Field order {hookId,label,kind,stackIndex,derefOffset,derefOffset2,
     * numBytes,when,maxDumps}. op_fields: THIS_OFFSET ecx+0, 0x110 bytes ->
     * dest holder @op+0x104, block factor @op+0x108. ctx: STACK_PTR sp[0]=arg0,
     * 0x50 bytes -> dst rect @+0x30..0x3c, SOURCE image @+0x40. src_img_hdr:
     * DEREF_PTR *(sp[0]+0x40) = the analysis ImaImage header, 0x48 bytes ->
     * w@+0x34, h@+0x38, stride@+0x44. Pixels are 3 derefs deep here -> none;
     * HOOK B captures them. All ON_ENTRY (the inputs exist before the call). */
    { "paxelize_blockavg_op", "op_fields",   EXTRA_DUMP_THIS_OFFSET, 0, 0x0,  0, 0x110,   EXTRA_DUMP_ON_ENTRY, 40 },
    { "paxelize_blockavg_op", "ctx",         EXTRA_DUMP_STACK_PTR,   0, 0,    0, 0x50,    EXTRA_DUMP_ON_ENTRY, 40 },
    { "paxelize_blockavg_op", "src_img_hdr", EXTRA_DUMP_DEREF_PTR,   0, 0x40, 0, 0x48,    EXTRA_DUMP_ON_ENTRY, 40 },

    /* HOOK B -- dsba_intlv_to_planar @ 0x101c0890 (cdecl,
     * AnsDSbaCapabilityImpl::convertInterleaveToPlanar). THE analysis-image
     * pixel capture. src_desc: STACK_PTR sp[1]=arg1 ([ebp+0xc]), 0x24 bytes ->
     * AnsImageData header (w@+0xc, h@+0x10, bands@+0x14, layout@+0x4,
     * pixptr@+0x20). src_pixels: DEREF_PTR *(sp[1]+0x20) = the analysis pixel
     * buffer (int16), capped at 0x84000 = HOOKCORE_EXTRA_DUMP_MAX_BYTES -- the
     * SAME 1-deref pattern as area pixel_data. Block-average these offline and
     * compare to measure_samples[bands 0-2]. Both ON_ENTRY. */
    { "dsba_intlv_to_planar", "src_desc",   EXTRA_DUMP_STACK_PTR, 1, 0,    0, 0x24,    EXTRA_DUMP_ON_ENTRY, 40 },
    { "dsba_intlv_to_planar", "src_pixels", EXTRA_DUMP_DEREF_PTR, 1, 0x20, 0, 0x84000, EXTRA_DUMP_ON_ENTRY, 40 },

    /* HOOK C -- resample_analysis_img @ 0x100d8030 (cdecl,
     * pathUtils::resampleAnslysisImage). FALLBACK, analysis DIMS only. anal_desc:
     * DEREF_PTR *(sp[0]+0) = *arg0 (the out param is a ptr-to-descPtr, so off0
     * does the one deref to the finished analysis descriptor: dims @+0xc/+0x10,
     * pixptr @+0x20). ON_EXIT (the resized image only exists after the call) --
     * so the HookDef sets wantExitDefault=1. Pixels need a 3rd deref -> not
     * capturable here. */
    { "resample_analysis_img", "anal_desc", EXTRA_DUMP_DEREF_PTR, 0, 0x0, 0, 0x24, EXTRA_DUMP_ON_EXIT, 8 },

    /* v56 -- sba_analyze_pass1 LATCH rows (docs/74 sampler UPDATE 8/9;
     * /tmp/pakon_re/v56build/). Field order {hookId,label,kind,stackIndex,
     * derefOffset,derefOffset2,numBytes,when,maxDumps}. __thiscall: ecx=this=
     * AnsSbaCapabilityImpl; sp[0]=first stack arg (arg0), sp[1]=second (arg1).
     * p1_cap_head: THIS_OFFSET ecx+0, 0x40 -- capability head (locate the frame
     * array / scene). p1_arg0_hdr: STACK_PTR sp[0], 0x24 -- arg0 AnsImageData
     * descriptor (layout@+4, w@+0xc, h@+0x10, bands@+0x14, pixptr@+0x20).
     * p1_arg0_pix: DEREF_PTR *(sp[0]+0x20), capped 0x84000 =
     * HOOKCORE_EXTRA_DUMP_MAX_BYTES -- arg0's pixels (int16), the SAME 1-deref
     * pattern area pixel_data uses. p1_arg1_hdr: STACK_PTR sp[1], 0x24 -- arg1
     * scene context. All ON_ENTRY (the images exist at analyze time), capped 20
     * (~12x/scan). If arg0's dims/pixels reproduce measure_samples, the producer
     * IS arg0's source and ports offline from one scan. Inert unless
     * sba_analyze_pass1 is enabled in hooks.cfg (OFF by default). */
    { "sba_analyze_pass1", "p1_cap_head", EXTRA_DUMP_THIS_OFFSET, 0, 0x0,  0, 0x40,    EXTRA_DUMP_ON_ENTRY, 20 },
    { "sba_analyze_pass1", "p1_arg0_hdr", EXTRA_DUMP_STACK_PTR,   0, 0,    0, 0x24,    EXTRA_DUMP_ON_ENTRY, 20 },
    { "sba_analyze_pass1", "p1_arg0_pix", EXTRA_DUMP_DEREF_PTR,   0, 0x20, 0, 0x84000, EXTRA_DUMP_ON_ENTRY, 20 },
    { "sba_analyze_pass1", "p1_arg1_hdr", EXTRA_DUMP_STACK_PTR,   1, 0,    0, 0x24,    EXTRA_DUMP_ON_ENTRY, 20 },

    { NULL, NULL, EXTRA_DUMP_STACK_PTR, 0, 0, 0, 0, EXTRA_DUMP_ON_ENTRY, 0 }, /* sentinel */
};
