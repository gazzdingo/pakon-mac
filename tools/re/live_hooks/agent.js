/**
 * Live Frida instrumentation of the real vendor F-135 pipeline
 * (PakonIMAu.dll / TLA.dll / TLB.dll) inside a running PSI.exe, on the real
 * Windows VM with the real scanner attached.
 *
 * WHY THIS EXISTS
 * ----------------
 * `docs/74-washed-out-tone-chain-architecture-and-dmin-methodology.md` has,
 * by static Unicorn-CPU-emulation comparison against the real DLLs, already
 * confirmed bit-exact every individually-tested subsystem (SBA neutral
 * balance, FUGC, falloff, ICC transform) -- yet the composite rendered
 * output is still wrong (~206 sRGB codes too bright, no real blacks; §13/§15
 * confirm the real vendor app on the real unit produces genuine deep blacks
 * on the same film). Static per-function verification cannot see whether
 * the pieces are correctly *wired together* at real scan time. This script
 * hooks the same functions LIVE, during a REAL scan, entry and exit, and
 * logs raw context + best-effort decoded fields + buffer previews to
 * structured JSONL -- so a human can diff each real stage's actual
 * live input/output against this port's own Python pipeline
 * (`tools/ansel/python-pipeline/pakon_ansel.py` and friends) run on the
 * same frame.
 *
 * ADDRESS CONVENTION -- READ BEFORE EDITING
 * ------------------------------------------
 * Every VA below is quoted the way this project's own docs quote it: as if
 * the owning DLL were loaded at its own preferred image base, 0x10000000.
 * This is confirmed for PakonIMAu.dll directly (`tools/re/reachability.py`:
 * "It loads at bin.baddr=0x10000000, which is what makes every VA in docs/
 * line up"; docs/62 line ~1246: "PakonIMAu.dll is PE32 x86 based at
 * 0x10000000"). TLA.dll/TLB.dll VAs throughout docs/62, docs/65, docs/66,
 * docs/72 are all in the same 0x1000_0000-0x1010_0000-ish range for files
 * of a few hundred KB, consistent with the same convention, but this has
 * NOT been independently re-confirmed the way PakonIMAu.dll's base was --
 * flagged honestly, not assumed silently (see `ASSUMED_BASE_UNCONFIRMED`
 * below).
 *
 * A REAL running PSI.exe cannot actually have every one of these DLLs
 * loaded at 0x10000000 simultaneously -- Windows will rebase all but one of
 * them. So this script NEVER treats a documented VA as an absolute runtime
 * address. It always computes:
 *
 *     runtime_addr = Module.findBaseAddress(dllName) + (documented_VA - 0x10000000)
 *
 * i.e. it converts the documented VA to an RVA against the assumed base,
 * then re-bases it against wherever Windows actually put that DLL in this
 * process. If a hook's resolved address looks obviously wrong once you have
 * real output (e.g. it doesn't disassemble to a sane prologue), that is
 * good evidence the assumed base is wrong for that specific DLL -- open an
 * x64dbg/x32dbg view on the loaded module and compare its own preferred
 * ImageBase (in the PE header) against 0x10000000 to check directly.
 *
 * WHAT THIS DOES NOT DO
 * ----------------------
 * It does not know the exact calling convention (register vs. stack,
 * exact arg index) for any of these functions at the assembly level --
 * that was never re-derived from a live disassembly for this task, only
 * the architectural facts already in docs/62/65/66/67/72/74 (what a
 * function does, who calls it, what struct fields it reads). Rather than
 * invent a plausible-looking stack offset for "the pixel buffer argument"
 * of each function (which would be exactly the kind of guessing this task
 * was told not to do), every hook logs:
 *
 *   1. full raw register state (onEnter and onLeave),
 *   2. the first STACK_DWORDS_TO_LOG dwords above ESP,
 *   3. a short preview (bytes + as int16 array) of every register/stack
 *      value that resolves to a live, readable memory region, and
 *   4. a "known-constant" heuristic annotation on any 16/32-bit value that
 *      matches a constant docs/74's own struct-field list already
 *      documents (1550 = neutralBalancePoint/lowFixedPoint/highFixedPoint/
 *      setShifts pivot 0x60E; 1200 = paperMin; 2000 = paperMax; the shipped
 *      CN fpo default 879/1250/1386; the shipped CN setShifts_out default
 *      683/297/151 -- all cited in docs/74 §1/§9).
 *
 * This turns "which register/stack slot is fpo" from a guess into
 * something the human running this can read directly off a live capture
 * (grep the JSONL for `"known_constant"`), and is a legitimate, standard
 * live-RE technique -- much more honest than inventing an ABI.
 * `dumpFullBuffer()` is provided, implemented, and ready to wire to a
 * specific register/stack slot in one line once that slot is identified
 * this way from a real capture.
 *
 * USAGE
 * -----
 * See `tools/re/live_hooks/README.md`. In short:
 *
 *     python host.py --process PSI.exe --out session1.jsonl
 *
 * on the Windows VM, then trigger a real scan in PSI while it runs.
 */

'use strict';

// ---------------------------------------------------------------------
// Hook table -- every entry cites the doc/line this address comes from.
// ---------------------------------------------------------------------

const ASSUMED_BASE = 0x10000000;
const ASSUMED_BASE_UNCONFIRMED = ['TLA.dll', 'TLB.dll']; // see header comment

const HOOKS = [
  // ---- Frame / stage boundaries (no real args decoded, just markers) ----
  {
    dll: 'PakonIMAu.dll', va: 0x10069490, id: 'cn_enhanced_driver',
    role: 'frame_boundary',
    desc: 'AnsCnEnhancedPath per-scene analyze driver (fcn.10069490) -- ' +
          'the real call-order spine: analyzeFugc -> balanceAreaImage -> ' +
          'analyzeArea -> analyzeAttributes -> analyzeFalloff -> ' +
          'analyzeAutoTone -> analyzeSharpening -> ...',
    cite: 'docs/74 §11 (call order), docs/62 line ~201-202',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x100fb730, id: 'analyze_auto_tone',
    role: 'stage_boundary',
    desc: 'ColorNegativePath::analyzeAutoTone -- the real 6-subsystem tone ' +
          'chain (cna/dra/toneHelper/contrast/ast/citras). Every subsystem ' +
          'individually Unicorn-verified bit-exact per docs/66; this ' +
          'boundary hook is for correlating a live call with the port\'s ' +
          'own real_auto_tone() on the same frame.',
    cite: 'docs/63, docs/65, docs/66, docs/74 (address repeated throughout)',
  },

  // ---- SBA / balance ----
  {
    dll: 'PakonIMAu.dll', va: 0x10100260, id: 'sba_set_shifts',
    role: 'stage', pixelBuffer: false,
    desc: 'ColorNegativePath::setShifts -- reads via getShifts, writes the ' +
          '3x int16 OUT balance-shift buffer this whole tone chain anchors ' +
          'to (the "SBA neutral-balance output" the task asks for).',
    cite: 'tools/ansel/python-pipeline/pakon_sba_apply.py module docstring',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x10100a37, id: 'sba_set_shifts_12',
    role: 'stage', pixelBuffer: false,
    desc: 'setShifts real closed-form entry for the shipped CN control ' +
          'words (ntdChoice,ctdChoice)=(1,2) -- PATH_SET_SHIFTS_12.',
    cite: 'pakon_sba_apply.py: PATH_SET_SHIFTS_12 = 0x10100A37',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x10124000, id: 'sba_get_shifts',
    role: 'stage', pixelBuffer: false,
    desc: 'getShifts -- copies 3x int16 from *(AnsSbaCapability+0x10)+0x3a38.',
    cite: 'pakon_sba_apply.py module docstring',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x1028c780, id: 'sba_preference',
    role: 'stage', pixelBuffer: false,
    desc: 'Preference -- the ONLY confirmed writer of +0x3a38 (analyzePass2 ' +
          '@ 0x10216433 passes scene+0x3a30; fist-rounds 3x int16 into ' +
          'scene+0x3a38/+3a3a/+3a3c).',
    cite: 'pakon_sba_apply.py module docstring',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x1019a0c0, id: 'sba_apply_balance_shifts',
    role: 'stage', pixelBuffer: true,
    desc: 'AnsAreaCapabilityImpl::applyBalanceShifts -- the real PER-PIXEL ' +
          'LUT apply (builds three 4096-entry LUTs via 0x1006c4f0, applies ' +
          'clamp(i+shift,0,4095) to every pixel). This is the closest real ' +
          'analogue of pakon_sba_apply.apply_balance_shifts() -- the ' +
          'pixel-buffer stage to diff, not just the scalar shifts.',
    cite: 'pakon_sba_apply.py module docstring',
  },

  // ---- FUGC ----
  {
    dll: 'PakonIMAu.dll', va: 0x100fed00, id: 'fugc_analyze',
    role: 'stage', pixelBuffer: false,
    desc: 'analyzeFugc -- FUGC analyze entry point in the real per-scene driver.',
    cite: 'docs/62 line ~201',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x101f82c0, id: 'fugc_set_lut_info',
    role: 'stage', pixelBuffer: false,
    desc: 'setLutInfo -- builds the FUGC apply LUT from ebp14 (setShifts ' +
          'OUT @ +0x4b6) and ebp18 (SceneContext "dmin" bag). Confirmed ' +
          'real-DLL-verified including the near-identity offsets=(0,-1,1) ' +
          'case, docs/74 §10.',
    cite: 'docs/66 line ~1839; docs/74 §10',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x101fc518, id: 'fugc_mode_dispatch',
    role: 'stage', pixelBuffer: false,
    desc: 'FUGC analyze / mode dispatch: Cap+0x60e8 == 2 -> metrics path, ' +
          'else -> setLutInfo. Address has a trailing "..." in its own ' +
          'source citation (approximate, not independently re-confirmed ' +
          'this pass) -- verify the exact entry live before trusting it.',
    cite: 'pakon_ansel.py comment near fugc_mode field (~line 657-658)',
    approximate: true,
  },

  // ---- falloff / area / attributes (docs/74's #1 remaining suspect) ----
  {
    dll: 'PakonIMAu.dll', va: 0x100fe960, id: 'analyze_falloff',
    role: 'stage', pixelBuffer: true,
    desc: 'analyzeFalloff -- per-pixel radial lens/scanner vignetting ' +
          'correction. The "falloff output" hook the task asks for.',
    cite: 'docs/62 line ~201-202; docs/74 §11',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x1006c4f0, id: 'shift_lut_builder',
    role: 'stage', pixelBuffer: false,
    desc: 'The vendor shift-LUT builder, out[i] = master[i + shift]. Hooked ' +
          'for its ARGUMENTS: stack_dwords[4..6] are the three post-rewrite ' +
          'shifts (docs/74 SS168, SS175.4).',
    cite: 'docs/74 SS167.5, SS168, SS175.4; r2 af+pdf 2026-08-20',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x100fdc40, id: 'analyze_post_balance',
    role: 'stage', pixelBuffer: true,
    desc: 'ColorNegativePath::analyzePostBalance -- builds the per-frame ' +
          'shift LUTs via 0x1006c4f0 and applies them via ' +
          'area_image_apply_lut. Entry pinned via the DLL own error string; ' +
          'cdecl, not __thiscall (docs/74 SS167.3).',
    cite: 'docs/74 SS167.3, SS168; r2 af+pdf 2026-08-20',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x10102b20, id: 'balance_area_image',
    role: 'stage', pixelBuffer: true,
    desc: 'balanceAreaImage -- opens with find("area") idempotency guard ' +
          '(a HIT throws; a MISS falls through -- docs/74 §11 already ' +
          'ruled out the find("area") HIT path as a live data-consumption ' +
          'channel, but never read the miss-path body itself).',
    cite: 'docs/74 §11',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x100fd190, id: 'analyze_scp_lut_balance',
    role: 'stage', pixelBuffer: false,
    desc: 'ColorNegativePath::analyzeScpLutBalance -- the analyze-time ' +
          'path that casts to the same AnsSCPLutCapability type ' +
          'balanceAreaImage\'s miss-path composes with at apply time ' +
          '(docs/74 §37/§39). Added specifically to settle the one open ' +
          'question §39 flagged: whether the [cast_result+0xc] gate ' +
          'controlling that whole compose block is actually non-zero on ' +
          'a real scan -- if this hook never fires, the SCPLut compose ' +
          'is dead on the real render path regardless of its data being ' +
          'confirmed correct.',
    cite: 'docs/74 §37.4, §39.2-39.3',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x100e16d0, id: 'analyze_area',
    role: 'stage', pixelBuffer: true,
    desc: 'analyzeArea entry (732-function capability, 0% ported). docs/74 ' +
          '§11-12 calls the four unreplicated stages -- this one included -- ' +
          '"the sole remaining concrete software lead" after every other ' +
          'mechanism was checked against the real DLL and confirmed correct.',
    cite: 'docs/74 §11, §12, §"What this changes about the open item list" item 1',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x100fb3d0, id: 'analyze_attributes',
    role: 'stage', pixelBuffer: true,
    desc: 'analyzeAttributes -- one of the four unreplicated stages between ' +
          'FUGC and autoTone, real call order per docs/74 §11.',
    cite: 'docs/74 §11',
  },

  // ---- SCPLut analyze worker (v36) ----
  {
    dll: 'PakonIMAu.dll', va: 0x10287eb0, id: 'scp_lut_worker',
    role: 'stage', pixelBuffer: false,
    desc: 'AnsSCPLutCapabilityImpl analyze worker -- computes the per-channel ' +
          'slope/offset (and visualGamma) that AnsSCPLutResults carries. The ' +
          'last unported step between tone and ICC; see docs/74 §141.',
    cite: 'docs/74 §139-§141',
  },

  // ---- ICC transform ----
  {
    dll: 'PakonIMAu.dll', va: 0x102f8420, id: 'icc_xform_apply',
    role: 'stage', pixelBuffer: true,
    desc: 'ImaICCXForm::apply -- builds source/dest descriptors and calls ' +
          'SpEvaluate @ 0x102f884c (kodakcms.dll import thunk 0x10500338). ' +
          'The "ICC transform input/output" hook the task asks for.',
    cite: 'docs/62 §12.4.2',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x1016ede0, id: 'icc_effect_op',
    role: 'stage', pixelBuffer: false,
    desc: 'ImaICCEffectOp -- wraps apply, passes this+0x118 (source max) / ' +
          'this+0x120 (dest max) at 0x1016ee84-0x1016eef8. The scale ' +
          '(4095 vs 32767 vs Go\'s x65535/4095) is explicitly UNRESOLVED ' +
          'in docs/62 §12.4.2 -- a live capture of this+0x118/this+0x120 ' +
          'settles it directly.',
    cite: 'docs/62 §12.4.2',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x1016e680, id: 'icc_effect_op_ctor',
    role: 'stage', pixelBuffer: false,
    desc: 'ImaICCEffectOp ctor -- the only writer found (static analysis) ' +
          'for this+0x118, loading the hardcoded 32767.0 from 0x1058fac0. ' +
          'A live hit here with a DIFFERENT value would directly disprove ' +
          'the "no later setter" assumption docs/62 flags as unconfirmed.',
    cite: 'docs/62 §12.4.2',
  },

  // ---- F-235 / TLA / TLB dmin-remap chain (the task's own cited example) ----
  {
    dll: 'TLA.dll', va: 0x1003f7db, id: 'tla_baddscene',
    role: 'stage', pixelBuffer: true,
    desc: 'bAddScene -- the REAL writer of FUGC\'s "dmin" SceneContext bag: ' +
          'FindDmin on the raw PRE-balance frame words, then TLB\'s F-135 ' +
          'ColNeg poly remap, stored as "dmin" and read back via ' +
          'getCnContext. This port\'s own stand-in ' +
          '(pakon_ansel.py render_scene, `ebp18` / `raw_dmin` block) is ' +
          'flagged in its own comment as producing values OUTSIDE the ' +
          'accept band on every real frame tested -- a real, confirmed, ' +
          'currently-not-the-206-code-defect wiring bug worth diffing live.',
    cite: 'tools/ansel/python-pipeline/pakon_ansel.py comment ~line 900-932; ' +
          'docs/66 golden-fleet section corroborates the surrounding TLA ' +
          'AddScene ColNeg leaf shape (zeroing @ 0x1003f7eb, width=4 push ' +
          '@ 0x1003f85d)',
  },
  {
    dll: 'TLA.dll', va: 0x100064d0, id: 'tla_colneg_planar_scan',
    role: 'stage', pixelBuffer: true,
    desc: 'PIColorCorrectColNegPlanarScan -- F-235 stage-2 entry, shuffles ' +
          '5 args into the MMX kernel\'s 7 at 0x1001c470.',
    cite: 'docs/65 line ~93; docs/66 golden-fleet section',
  },
  {
    dll: 'TLA.dll', va: 0x1001c470, id: 'tla_colneg_mmx_kernel',
    role: 'stage', pixelBuffer: true,
    desc: 'The inner MMX kernel itself (pmulhw x3, independently-truncated ' +
          'products, THEN summed -- the exact bug docs/66\'s "golden ' +
          'fleet" section fixed on the port side, one code high).',
    cite: 'docs/66 "6.2 -- golden fleet, colneg_1px remap TLA"',
  },

  {
    dll: 'TLB.dll', va: 0x10022a60, id: 'tlb_lut_apply',
    role: 'stage', pixelBuffer: true,
    desc: 'The per-pixel transfer-LUT loop applied immediately before ' +
          'PolyPixel; out[i] = *(uint16 *)(table + in[i]*4). Candidate ' +
          'site of the F-135 inversion (docs/74 §162-§163).',
    cite: 'docs/74 §162, §163, §163.5; r2 af+pdf 2026-08-20',
  },
  {
    dll: 'TLB.dll', va: 0x10034b9b, id: 'tlb_f135_poly_remap',
    role: 'stage', pixelBuffer: true,
    desc: 'F-135 ColNeg polynomial remap used by bAddScene to turn the raw ' +
          'FindDmin walk into "dmin". NOTE: this port\'s own comment cites ' +
          'it as "TLB.dll fcn.1000d880 @ 0x10034b9b" -- an r2 auto-name/VA ' +
          'pair that looks inconsistent (fcn.<addr> normally names a ' +
          'function BY its own entry address) with docs/65\'s separate ' +
          'citation of "TLB.dll:fcn.1000d880" for the general stage-2 3x10 ' +
          'polynomial (PolyPixel). Both addresses are hooked below ' +
          '(this one and tlb_polypixel) precisely so a live capture can ' +
          'resolve which is which rather than guessing.',
    cite: 'pakon_ansel.py comment ~line 903-904',
    approximate: true,
  },
  {
    dll: 'TLB.dll', va: 0x1000d880, id: 'tlb_polypixel',
    role: 'stage', pixelBuffer: true,
    desc: 'PolyPixel -- general stage-2 3x10 quadratic polynomial (the ' +
          'entry address implied directly by its own r2 auto-name, ' +
          'fcn.1000d880). See tlb_f135_poly_remap\'s note above -- hooked ' +
          'alongside it to resolve the naming ambiguity live.',
    cite: 'docs/65 line ~86; docs/62 line ~950',
  },

  // ---- AFE (device-side register write, not a per-pixel software stage) ----
  {
    dll: 'TLB.dll', va: 0x100299c0, id: 'tlb_afe_offset_write',
    role: 'stage', pixelBuffer: false,
    desc: 'FN_bDrvPutCcdAtoDOffsets -- AD9826 offset register encoder ' +
          '(9-bit sign-magnitude; this port had a two\'s-complement bug ' +
          'here, fixed 2026-08-12, docs/72). This is the closest REAL, ' +
          'documented "AFE" hook available. NOTE: this is the OFFSET ' +
          'write, not GAIN -- no distinct address for a gain-register ' +
          'write function was found documented anywhere in docs/62-74. ' +
          'See README.md "AFE gain -- honestly unresolved" for the exact ' +
          'search strategy to find it live rather than guess it.',
    cite: 'docs/72 §1.3 ("FN_bDrvPutCcdAtoDOffsets at 0x100299c0, ' +
          '[VERIFIED-FROM-BINARY]")',
  },

  // ---- Area image per-pixel LUT apply (docs/74 §46) ----
  {
    dll: 'PakonIMAu.dll', va: 0x100d9340, id: 'area_image_apply_lut',
    role: 'stage', pixelBuffer: true,
    desc: 'AnsImageData::applyLut -- self-named by its own embedded ' +
          'strings ("AnsImageData::applyLut" @ 0x10584320 and three ' +
          'sibling error strings, path ' +
          '"\\Atc\\ansel\\src\\libStub.ansel\\AnsImageData.cpp" @ ' +
          '0x10584274). A real nested width/height-bounded loop (outer ' +
          'row loop 0x100d97f0-0x100d98be, inner column loop ' +
          '0x100d9822-0x100d986b) doing, per pixel, an indexed LUT ' +
          'lookup (`mov bx,word[lutBase+ebx*2]`) and indexed pixel write ' +
          '(`mov word[dst+idx],bx`) for each of R/G/B against three ' +
          'separate 4096-entry caller-supplied LUTs -- the genuine ' +
          'per-pixel write §27.4/§37.7/§45 had been missing, not another ' +
          'capability-object field write. Called 4x from ' +
          'balanceAreaImage (all on the AREA capability\'s own real ' +
          '"AREA analysis image" object, this+0x1a4 per §27.3), once ' +
          '(currently gated off) from sba_apply_balance_shifts, once ' +
          'from analyzePostBalance (0x100fdc40), and 3x from ' +
          'AnsDcPremiumPath\'s own CN-Premium vtable method -- 10 real ' +
          'static callers total, E8-scan confirmed. Independently ' +
          'corroborated by docs/62 §2.5, docs/64, and ' +
          'docs/reports/autotone-scope-2026-08-10/{fugc,filmLut}.md, ' +
          'none of which this investigation had cross-referenced before ' +
          'this pass. Still-open question this hook exists to help ' +
          'settle: whether the "AREA analysis image" aliases the shared ' +
          'scene buffer cna/dra actually reads, or is a private, ' +
          'analysis-only copy (docs/58 §16.5 as quoted in docs/62 §2.5).',
    cite: 'docs/74 §46; docs/62 §2.5; docs/64; docs/58 §16.5 (quoted in ' +
          'docs/62); docs/reports/autotone-scope-2026-08-10/' +
          '{fugc,filmLut}.md',
  },

  // ---- Lamp / AFE-gain / CCD-acquire-control (docs/74 §49) ----
  // Three new TLB.dll entries covering the real lamp warm-up + CCD
  // dark-offset-calibration bring-up sequence docs/55 and docs/59
  // captured on the wire, extending the existing tlb_afe_offset_write
  // hook (AFE OFFSET register only) to the other two real,
  // independently call-reachable driver functions in that sequence.
  // Re-derived fresh this pass against the hash-verified TLB.dll (md5
  // 193d9b2ce0a4b77ae9b78262bd06c0fc) via r2 af/axt/pdf -- appended here
  // AND in win_inject/hookcore_real_table.c's table[] in the same order,
  // per check_table_sync.py.
  {
    dll: 'TLB.dll', va: 0x1002c5f0, id: 'tlb_lamp_on',
    role: 'stage', pixelBuffer: false,
    desc: 'FN_bDrvLampOn -- the real lamp enable+duty-write function: ' +
          'writes light-board reg 0x80 (enable mask), 0x81 (5-byte LED ' +
          'levels [B,Ir,R,0,G]) and 0x82 (12-byte PWM on-count sextet + ' +
          'period N), matching docs/59\'s captured steps 16-18/80-82/100/' +
          '114 and docs/40 §3/§12\'s own static derivation of this exact ' +
          'address ("FN_bDrvLampOn = fcn.1002c5f0"). Re-confirmed fresh ' +
          'this pass: `axt` finds 8 genuine CALL-type xrefs from 6 ' +
          'distinct caller functions, zero CODE-type/internal-jump ' +
          'xrefs. Prologue: `push ebp; mov ebp,esp; and esp,0xfffffff8; ' +
          'sub esp,0x54` -- an entirely ordinary MSVC frame (stack ' +
          'realignment for FPU locals), no relative jump/call anywhere ' +
          'near the bytes MinHook needs to relocate.',
    cite: 'docs/40 §3 ("FN_bDrvLampOn = fcn.1002c5f0"), §12 (write-order ' +
          'correction); docs/59 (captured wire sequence); fresh r2 ' +
          'af/axt/pdf 2026-08-15 against TLB.dll md5 ' +
          '193d9b2ce0a4b77ae9b78262bd06c0fc',
  },
  {
    dll: 'TLB.dll', va: 0x100298b0, id: 'tlb_afe_gain_write',
    role: 'stage', pixelBuffer: false,
    desc: 'The AFE GAIN register write function -- the address ' +
          'README.md\'s "AFE gain -- honestly unresolved" section asked ' +
          'for. Self-naming string "FN_bDrvPutCcdAtoDGains" exists in ' +
          'this exact binary at 0x10063b4c, matching the vendor\'s own ' +
          'FN_bDrv... naming convention (referenced only from the shared ' +
          'name-lookup/logging dispatcher fcn.100170b0, not from inside ' +
          'this function\'s own body -- the name<->address link here is ' +
          'by structural match, same standard already used for ' +
          'tlb_afe_offset_write). Sits immediately before ' +
          'tlb_afe_offset_write (0x100299c0) in .text, same shape, and ' +
          'writes CCD reg 0x84 idx 2/3/4 -- exactly docs/55\'s captured ' +
          'steps 19-21 (gain R/G/B), vs. the offset function\'s idx 5/6/7. ' +
          '`axt` finds 8 genuine CALL-type xrefs. Prologue: `push ebx; ' +
          'mov ebx,[esp+8]` -- exactly 5 bytes, no relative jump/call.',
    cite: 'README.md "AFE gain -- honestly unresolved"; docs/55 steps ' +
          '19-21 (captured 0x44/0x84 idx2/3/4 gain writes); fresh r2 ' +
          'izz/af/axt/pdf 2026-08-15 against TLB.dll md5 ' +
          '193d9b2ce0a4b77ae9b78262bd06c0fc',
  },
  {
    dll: 'TLB.dll', va: 0x1002c340, id: 'tlb_ccd_acquire_control',
    role: 'stage', pixelBuffer: false,
    desc: 'The CCD acquire-on/off toggle function docs/40 §11 names ' +
          '"FN_bDrvCcdAcquireControl" ("sets bit 0 of CCD register ' +
          '0x82"), matching docs/55\'s captured steps 2/18/35/40/43 ' +
          '(board 0x44 reg 0x82 idx 0: mask 0x0060 vs acquire-on 0x0061). ' +
          'LOWER CONFIDENCE ON THE NAME specifically than the other two ' +
          'new entries: the self-naming string is, like the others, ' +
          'referenced only from the shared dispatcher fcn.100170b0, not ' +
          'from inside this function\'s own body -- identified by ' +
          'behavior and position instead: validates uiCcdPixelHeight/' +
          'uiCcdPixelOffset/uiCalibrationOffset/uiCcdIntegrationTime (4 ' +
          'embedded assert strings naming them), then calls a small ' +
          'shared reg-0x82-idx0 write primitive (fcn.10029770) TWICE. ' +
          'This function\'s own address range (0x1002c340-0x1002c5f0) ' +
          'ends EXACTLY where tlb_lamp_on/FN_bDrvLampOn begins -- ' +
          'adjacent in the same translation unit. `axt` finds 8 genuine ' +
          'CALL-type xrefs from 6 distinct callers, 3 of which also call ' +
          'tlb_lamp_on. Prologue: `push ecx; mov eax,[esp+0x1c]` -- ' +
          'exactly 5 bytes, no relative jump/call.',
    cite: 'docs/40 §11 ("FN_bDrvCcdAcquireControl sets bit 0 of CCD ' +
          'register 0x82"); docs/55 steps 2/18/35/40/43 (captured ' +
          '0x44/0x82 idx0 mask/acquire writes); fresh r2 izz/af/axt/pdf ' +
          '2026-08-15 against TLB.dll md5 193d9b2ce0a4b77ae9b78262bd06c0fc',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x101b76d0, id: 'color_adjust_shift',
    role: 'stage', pixelBuffer: false,
    desc: 'The analyzePostBalance shift leaf (fcn.101b76d0, 282 B) -- ' +
          'computes the three int16 post-balance shifts as out_c = ' +
          'round((in_c - mean(in)) * M_c + S1*S2 + dmin_c), Unicorn-verified ' +
          'bit-exact (pakon_postbalance_golden.py). __thiscall: ecx = ' +
          'AnsColorAdjustCapabilityImpl (the Impl at Cap+0x10); the Impl ' +
          'fields are M/S1/S2/dens/dmin at +0xc..+0x30 (M and S1 are ctor ' +
          'args defaulting 25/25/25/75; dens/S2/dmin are zeroed at ' +
          'construction -- their non-zero writer is the still-open question ' +
          'this hook exists to answer). Prologue `push ecx; push esi; mov ' +
          'esi,ecx` (5 B) is a clean MinHook target; reached via two real ' +
          'CALL sites (fcn.100f13a0 @ 0x100f13c1, fcn.101b7e90 @ ' +
          '0x101b80ad), so notCallReachable=0.',
    cite: 'docs/74 §57; tools/ansel/python-pipeline/pakon_postbalance_golden.py',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x1028b8d0, id: 'sba_order_fpo_calc',
    role: 'stage', pixelBuffer: false,
    desc: 'The function §66 named as the per-frame orderFpo (scene+0x38a2) ' +
          'writer -- 2958 B, 13 cdecl args (callers clean up add esp,0x34), ' +
          '8 helper subroutines, called 5x per frame. §72\'s full-body read ' +
          'found its own TOP-LEVEL code does NOT write the orderFpo Y/U/V ' +
          'triple (pref_data+0x0/+0x2/+0x4) on the case that provably fires ' +
          'live (switch selector arg 3 == 0 at both real call sites): it ' +
          'writes exactly ONE unrelated word at pref_data+0x3e, derived from ' +
          'two other already-present pref_data fields. Whether one of the 8 ' +
          'unread helpers is the real orderFpo writer -- with pref_data ' +
          'threaded in as a hidden argument -- is exactly what this hook ' +
          'exists to settle empirically. Safety (r2 af+axt 2026-08-17): FIVE ' +
          'real CALL-type xrefs (fcn.102159c0 @ 0x10215d6a/0x10215fae/' +
          '0x1021605b = AnsSbaCapabilityImpl::analyzePass2, fcn.10218110 @ ' +
          '0x1021937b/0x102196a9), ZERO CODE-type jmp/jcc entries, and `af` ' +
          'resolves to 0x1028b8d0 itself -- the return-address-swap ' +
          'precondition genuinely holds. Prologue `mov eax,[esp+0xc]` (4 B) ' +
          '+ `sub esp,0x2c0` (6 B) is position-independent, no rel32 in the ' +
          'first 5 bytes, so a clean MinHook relocation target. Entry-only: ' +
          'the before/after question §72.7 poses is answered by consecutive ' +
          'ENTRY dumps across the 5 calls plus the existing sba_preference ' +
          'pref_data dump (§72.5 proved all 5 precede Preference).',
    cite: 'docs/74 §66, §72 (esp. §72.2 arg table, §72.3 case-0 read, ' +
          '§72.7 capture spec); r2 af/axt safety audit 2026-08-17',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x1028ae00, id: 'sba_order_fpo_helper',
    role: 'stage', pixelBuffer: false,
    desc: 'fcn.1028ae00 (1897 B, 15 cdecl args) -- the helper 0x1028b8d0 ' +
          'calls at 0x1028c023 to compute the chroma residual behind the ' +
          'orderFpo U/V terms. §76 derived U/V in full and needs no ' +
          'emulation of them, but could not statically derive the Y term: ' +
          'an int32 read from a stack slot (L[-0x200]) that nothing in ' +
          "0x1028b8d0's own 912 instructions ever writes. §76 traced it to " +
          "this function's own arg 9. The engine already logs the first 16 " +
          'raw stack dwords per entry and all 15 args fall inside that ' +
          'window, so arg 9 is captured with no extra dump row, and the ' +
          "same line cross-checks §76's whole 15-arg reconstruction. " +
          'Safety (r2 af+axt 2026-08-17): exactly one real CALL xref ' +
          '(fcn.1028b8d0 @ 0x1028c023), zero CODE-type jmp/jcc entries, ' +
          '`af` resolves to its own entry, and the prologue ' +
          '`sub esp,0x5c` + `movsx eax, word [esp+0x70]` is ' +
          'position-independent with no rel32 in the first 5 bytes. ' +
          'Entry-only: the wanted value is an input argument.',
    cite: 'docs/74 §76; r2 af/axt safety audit 2026-08-17',
  },
  {
    dll: 'PakonIMAu.dll', va: 0x102aadf0, id: 'sba_vm_interp',
    role: 'stage', pixelBuffer: false,
    desc: 'fcn.102aadf0 (4423 B) -- the BYTECODE INTERPRETER §78.2 found ' +
          'standing between a captured Y term and a computable one. Program ' +
          'pointer at [arg2+4], 16-bit opcodes, 0xff halt, two-stage ' +
          'dispatch (254-byte index table at 0x102ac018, then the jump table ' +
          'at 0x102abf4c). Static scoping (§86): the 254 opcodes collapse to ' +
          '51 handler indices and index 50 alone covers 203 of them (the ' +
          'default case), so there are 50 real handlers, not 254. This ' +
          'capture dumps the PROGRAM rather than logging each dispatch: ' +
          'comparing the bytes across frames and scans settles ' +
          'static-vs-generated, and walking them against the index table ' +
          'gives the exact opcode set this path uses -- the number that ' +
          'decides whether porting the VM is bounded. Safety (r2 af+axt ' +
          '2026-08-17): exactly one real CALL xref (fcn.102ac140 @ ' +
          '0x102ac15a), zero CODE-type entries, `af` resolves to its own ' +
          'entry, and the prologue `sub esp,0x2c` + `push ebx` + `push ebp` ' +
          'is exactly 5 position-independent bytes with no rel32. ' +
          'Entry-only: the program and context are inputs.',
    cite: 'docs/74 §78.2, §86; r2 af/axt safety audit 2026-08-17',
  },

  // -------------------------------------------------------------------
  // v46 -- TLB.dll FRAMING cascade. ALL THREE RE-DERIVED, and now ON.
  //
  // They were first shipped OFF (approximate) on two stated premises, and
  // BOTH WERE FALSE. Recording that here because the correction is more
  // instructive than the result.
  //
  // (1) "TLB.dll is not on this machine." It is, at /tmp/pakon_re/TLB.dll --
  // the scratch dir CLAUDE.md designates for RE work, and the FIRST entry in
  // pakon_framing_golden.py's own DEFAULT_DLL_CANDIDATES. md5
  // 193d9b2ce0a4b77ae9b78262bd06c0fc, exactly the hash that harness expects.
  // The `find` behind the claim was scoped to the repo; `mdfind` does not
  // index /tmp. An absence of evidence needs verifying as carefully as a
  // presence -- "I could not find X" is a claim about the search, not X.
  //
  // (2) "The `or` sites span a range containing 0x100072c0, so the entry may
  // be interior to fcn.10006e70." Read it and it dissolves: fcn.10006e70 is
  // 0x10006e70-0x100072b5, fcn.100072c0 is 0x100072c0-0x100079b1 -- adjacent,
  // 11 bytes of padding, not nested. Three `or` sites (0x1000708b,
  // 0x10007193, 0x1000729f) are inside the driver; 0x10007d35 is in
  // fcn.100079c0, the outer caller. No repeat of sba_set_shifts_12 or v41's
  // 0x100fe4f0 here.
  //
  // Verified this pass with r2 `af`+`afi`+`axt` against that md5: every one
  // is a real function boundary, every prologue takes a 5-byte patch without
  // splitting an instruction, and nothing jumps into the patched bytes. The
  // entry is __thiscall (`mov esi,ecx`), and the highest this-relative offset
  // it touches is esi+0x6cbc -- last byte 0x6cbf -- so the 0x6CC0 dump size
  // is exact rather than assumed.
  //
  // tlb_framing_line_reduce alone stays off by default, on log volume: it is
  // per-LINE, and a ~9,000-line roll with a re-running threshold search adds
  // tens of MB even with dumps capped. One hooks.cfg line turns it on.
  {
    dll: 'TLB.dll', va: 0x100072c0, id: 'tlb_framing_entry',
    role: 'stage', pixelBuffer: false,
    desc: 'Framing entry point, per ROLL. Reported as the caller of the ' +
          'five-stage cascade (LookForNicePictures 0x10006930, ' +
          'FramingLookInBetweenEnds 0x100063d0, LookAtEnd 0x10006ae0, ' +
          'LookAtBeginning 0x10006ca0, FramingBlindlyPlacePictures ' +
          '0x10006720) and as the owner of the threshold search that ' +
          're-binarises and re-runs the run extractor, stepping +-2 ' +
          'between 25 and 256 until the bins settle -- a search this port ' +
          'reads but has never ported. CONFIRMED real entry: fcn.100072c0, ' +
          '1777 bytes, 0x100072c0-0x100079b1.',
    cite: 'framing pass 2026-08-21 (xref from TLB.dll log strings at file ' +
          'offsets 0x5b890/0x5b8b8/0x5b8d4/0x5b8ec/0x5b944); RE-DERIVED ' +
          '2026-08-21 vs md5 193d9b2ce0a4b77ae9b78262bd06c0fc, r2 af/afi/axt',
  },
  {
    dll: 'TLB.dll', va: 0x10006e70, id: 'tlb_framing_driver',
    role: 'stage', pixelBuffer: false,
    desc: 'Framing cascade driver, per ROLL. Sets the warning bits the ' +
          'cascade stages report through (or eax,0x100 @ 0x1000708b; ' +
          'or eax,0x200 @ 0x10007193; or [ebp+0x6ca8],0x400 @ 0x1000729f; ' +
          'or edi,0x800 @ 0x10007d35). The [ebp+0x6ca8] site is the one ' +
          'structural fact available about the framing object without the ' +
          'DLL in hand: it is at least 0x6cac bytes, and the per-line ' +
          'trace fcn.10006870 consumes starts at +0x6c -- so a 0x6CC0 dump ' +
          'from the object base covers the trace, the warning word, and ' +
          'the threshold-search state in one row. CONFIRMED: fcn.10006e70, ' +
          '0x10006e70-0x100072b5; 0x1000729f disassembles to exactly ' +
          '`or dword [ebp + 0x6ca8], 0x400`.',
    cite: 'framing pass 2026-08-21; RE-DERIVED 2026-08-21 vs md5 ' +
          '193d9b2ce0a4b77ae9b78262bd06c0fc',
  },
  {
    dll: 'TLB.dll', va: 0x10006870, id: 'tlb_framing_line_reduce',
    role: 'stage', pixelBuffer: false,
    desc: 'Per-LINE reduction: reads three bytes per line from this+0x6c ' +
          'and returns 255 - (r+g+b)/3 -- 8-bit and INVERTED. This is the ' +
          'domain gap that currently makes the ported framing cascade ' +
          'untestable: this port runs on float 14-bit non-inverted data, ' +
          'so the two cascades are not comparable until the vendor\'s own ' +
          'array is seen. Hooked as the CONSUMER, deliberately: the array ' +
          'is already filled when this runs, so an entry-side dump of it ' +
          'is the finished trace -- whereas the driver\'s entry dump is ' +
          'the array before it exists. PER-LINE, so its dump row is capped ' +
          'at 6 and exit-hooking is off. CONFIRMED: fcn.10006870, 181 bytes, ' +
          'called from fcn.100072c0 @ 0x100073b3 -- all three framing ' +
          'hooks are ONE call tree. Off by default on VOLUME alone.',
    cite: 'framing pass 2026-08-21; RE-DERIVED 2026-08-21 vs md5 ' +
          '193d9b2ce0a4b77ae9b78262bd06c0fc',
  },

  // v47 -- the SBA statistics ENGINE, hooked for PROVENANCE.
  //
  // docs/74 §192/§196. fcn.102aece0 produces every variable term of the
  // per-frame orderFpo triple: the 864-byte mask at obj+0xc20 feeds U and V,
  // and the 720-slot vector at obj+0x3c is the p-code VM's in[], which
  // reproduces L. Both the mask and the packer (fcn.102b7440) are now ported
  // bit-exact -- but tier 1 for EQUIVALENCE and tier 4 for PROVENANCE, because
  // no capture hooks either and their inputs are synthetic. B1 is a question
  // about real per-frame values; this row is what answers it.
  //
  // NOTE the already-hooked sba_order_fpo_calc (0x1028b8d0) is the CALLER, not
  // this. §192.1 corrected an earlier reading that named it the producer: it
  // is 2,958 B and this is 24,516 B.
  {
    dll: 'PakonIMAu.dll', va: 0x102aece0, id: 'sba_measure',
    role: 'stage', pixelBuffer: false,
    desc: 'The per-sample SBA statistics engine (24,516 B; ONE function, ' +
          'four rets sharing one 0xfac frame -- §192.1 corrected the ' +
          'earlier reading that its body ended at the first ret, which is ' +
          'an early calloc-failure return). Reads a 24x36x6 sample grid; ' +
          'writes the 864-byte selection mask at obj+0xc20, ten header ' +
          'words, and via its pure tail callee fcn.102b7440 the whole ' +
          '720-slot int32 vector at obj+0x3c. Hooked ENTRY+EXIT on the ' +
          'object: exit captures mask+vector+headers together (the callee ' +
          'writes the same object before this returns), and entry is NOT ' +
          'redundant because the cross-call read of [obj+0x7b8] at ' +
          '0x102b0da5 is live, so call N consumes what N-1 wrote.',
    cite: 'docs/74 §192 (mapped; three corrections to §76.6), §196 (run as ' +
          'one function under Unicorn: 74/74 cases to the success exit ' +
          '0x102b4c93, mask bit-exact 63,936/63,936 bytes, 17 mutations ' +
          'caught / 2 provably inert / 0 NOT CAUGHT). Address and prologue ' +
          're-derived 2026-08-21 vs PakonIMAu.dll md5 ' +
          'eea9dcf78ee21d4f7c515a6c2512242d: single 6-byte `sub esp,0xfac`, ' +
          'no jump target in the patched bytes',
  },

  // v53 -- the framing 14->8-bit derivation SOURCE, to close FRAMING_PORTED.
  //
  // docs/74 §194. The ported framing cascade consumes the object's 8-bit
  // per-line RGB summary at this+0x6c (captured as framing_lines), but this
  // port holds float 14-bit non-inverted data and the 14->8 quantisation is
  // unknown. The per-line value-writer is on an unhookable DMA path (prior
  // RE), so instead capture the 16-bit CCD source + 8-bit summary + geometry
  // of ONE real frame and derive the map offline. fcn.10004f00 is the framing
  // object's allocator/geometry site: __thiscall, ecx=object, count =
  // total_lines / line_scale, sets +0x60 (row-pointer table; table[0] is the
  // 16-bit CCD base, a DOUBLE deref), +0x64 (size), +0x6c (8-bit summary).
  // OFF by default (opt-in via hooks.cfg). TIER 3 (static mapping) until this
  // capture runs, NOT yet live-confirmed -- that is what it is for.
  {
    dll: 'TLB.dll', va: 0x10004f00, id: 'tlb_framing_setup',
    role: 'stage', pixelBuffer: false,
    desc: 'Framing object allocator + geometry (__thiscall, ecx=object). ' +
          'Computes count = total_lines / line_scale (e.g. 19096/8 = 2387) ' +
          'and stores the +0x6c 8-bit per-line RGB summary pointer, the ' +
          '+0x60 row-pointer table pointer (table[0] = contiguous 16-bit CCD ' +
          'image base, a DOUBLE deref) and the +0x64 size. Hooked ENTRY+EXIT ' +
          'on the object; paired with the +0x60 CCD-image and row-table dumps ' +
          'on tlb_framing_line_reduce, captures the 16-bit source + 8-bit ' +
          'summary + geometry of one real frame so the vendor 14->8 framing ' +
          'quantisation can be derived offline and FRAMING_PORTED closed ' +
          '(docs/74 §194). OFF by default (opt-in); not yet live-confirmed.',
    cite: 'RE 2026-08-22, /tmp/pakon_re/framewriter/ (prior static-RE agent), ' +
          'TLB.dll md5 193d9b2ce0a4b77ae9b78262bd06c0fc: fcn.10004f00 sets ' +
          '+0x60/+0x64/+0x6c, store to [esi+0x6c] @ 0x100051b2. Prologue first ' +
          'insn `mov eax, fs:[0]` is 6 bytes (>= 5), MinHook 5-byte patch safe ' +
          '(approximate=0). TIER 3 (static mapping), NOT yet live-confirmed.',
  },
];

// ---------------------------------------------------------------------
// Known-constant heuristic table (docs/74 §1/§9's own struct-field values)
// ---------------------------------------------------------------------

const KNOWN_CONSTANTS = {
  1550: 'neutralBalancePoint / lowFixedPoint / highFixedPoint / setShifts pivot (0x60E) -- docs/74 §1',
  1200: 'paperMin -- docs/74 §1',
  2000: 'paperMax -- docs/74 §1',
  4095: '12-bit domain max',
  879: 'fpo R, shipped CN default -- docs/74 §9',
  1250: 'fpo G, shipped CN default -- docs/74 §9',
  1386: 'fpo B, shipped CN default -- docs/74 §9',
  683: 'setShifts_out R, this roll (docs/74 §9 example -- confirm against your own frame, not universal)',
  297: 'setShifts_out G, this roll (docs/74 §9 example)',
  151: 'setShifts_out B, this roll (docs/74 §9 example)',
};

// ---------------------------------------------------------------------
// Session / correlation state
// ---------------------------------------------------------------------

const SESSION_ID = 'sess_' + Date.now().toString(36);
let callCounter = 0;
let frameCounter = 0;
const STACK_DWORDS_TO_LOG = 24;
const PTR_PREVIEW_BYTES = 64;

function log(obj) {
  send(Object.assign({ session_id: SESSION_ID, ts: Date.now() }, obj));
}

// ---------------------------------------------------------------------
// Safe memory helpers -- never let a bad pointer kill the hook
// ---------------------------------------------------------------------

function tryReadBytes(ptr, len) {
  try {
    if (ptr.isNull()) return null;
    const range = Process.findRangeByAddress(ptr);
    if (range === null) return null;
    if (range.protection.indexOf('r') === -1) return null;
    return Memory.readByteArray(ptr, Math.min(len, PTR_PREVIEW_BYTES));
  } catch (e) {
    return null;
  }
}

function bytesToHex(buf) {
  if (buf === null) return null;
  const view = new Uint8Array(buf);
  let out = '';
  for (let i = 0; i < view.length; i++) {
    out += ('0' + view[i].toString(16)).slice(-2);
  }
  return out;
}

function bytesToI16Array(buf) {
  if (buf === null) return null;
  const n = Math.floor(buf.byteLength / 2);
  const arr = new Array(n);
  const dv = new DataView(buf);
  for (let i = 0; i < n; i++) {
    arr[i] = dv.getInt16(i * 2, true); // little-endian
  }
  return arr;
}

function annotateKnownConstants(i16arr) {
  if (i16arr === null) return [];
  const hits = [];
  for (let i = 0; i < i16arr.length; i++) {
    const v = i16arr[i];
    if (Object.prototype.hasOwnProperty.call(KNOWN_CONSTANTS, v)) {
      hits.push({ index: i, value: v, meaning: KNOWN_CONSTANTS[v] });
    }
  }
  return hits;
}

function previewPointer(ptr) {
  const bytes = tryReadBytes(ptr, PTR_PREVIEW_BYTES);
  if (bytes === null) return null;
  const i16 = bytesToI16Array(bytes);
  return {
    ptr: ptr.toString(),
    hex: bytesToHex(bytes),
    i16: i16,
    known_constant_hits: annotateKnownConstants(i16),
  };
}

function regsToObj(context) {
  // ia32 CpuContext fields. If this ever runs against a 64-bit build,
  // extend with rax/rbx/.../r8-r15 -- these DLLs are documented 32-bit
  // PE (PE32) throughout docs/62, so ia32 is assumed.
  const out = {};
  const names = ['eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'ebp', 'esp', 'eip'];
  for (const n of names) {
    if (context[n] !== undefined) out[n] = context[n].toString();
  }
  return out;
}

function stackDwords(context, count) {
  const out = [];
  try {
    let p = context.esp;
    for (let i = 0; i < count; i++) {
      let val = null;
      try { val = p.readU32(); } catch (e) { val = null; }
      out.push({ offset: i * 4, addr: p.toString(), u32: val });
      p = p.add(4);
    }
  } catch (e) {
    // leave out whatever was collected
  }
  return out;
}

function pointerScan(context) {
  // Generic ABI-agnostic evidence gathering: preview every register and
  // the first STACK_DWORDS_TO_LOG stack slots that happen to resolve to
  // live, readable memory. This is what stands in for "decode the real
  // argument list" without inventing an unconfirmed calling convention --
  // see the file header comment.
  const found = {};
  const regNames = ['eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'ebp'];
  for (const n of regNames) {
    if (context[n] === undefined) continue;
    const prev = previewPointer(context[n]);
    if (prev !== null) found['reg_' + n] = prev;
  }
  try {
    let p = context.esp;
    for (let i = 0; i < STACK_DWORDS_TO_LOG; i++) {
      let val = null;
      try { val = p.readPointer(); } catch (e) { val = null; }
      if (val !== null) {
        const prev = previewPointer(val);
        if (prev !== null) found['stack_+0x' + (i * 4).toString(16)] = prev;
      }
      p = p.add(4);
    }
  } catch (e) {
    // best effort
  }
  return found;
}

// Ready-to-wire full-buffer capture. Not called by default (see file
// header) -- call this from a specific hook's onEnter/onLeave once you've
// identified which register/stack slot holds the real pixel buffer
// pointer from a live pointerScan() capture, e.g.:
//     dumpFullBuffer(this.hookId, this.callId, 'input_buf', context.esi, 4096);
function dumpFullBuffer(hookId, callId, tag, ptr, byteLen) {
  try {
    if (ptr.isNull()) return;
    const range = Process.findRangeByAddress(ptr);
    if (range === null || range.protection.indexOf('r') === -1) return;
    const data = Memory.readByteArray(ptr, byteLen);
    send({
      session_id: SESSION_ID, ts: Date.now(), kind: 'buffer',
      hook_id: hookId, call_id: callId, tag: tag,
      ptr: ptr.toString(), byte_len: byteLen,
    }, data);
  } catch (e) {
    log({ kind: 'error', hook_id: hookId, call_id: callId, tag: tag,
          error: 'dumpFullBuffer failed: ' + e.message });
  }
}

// ---------------------------------------------------------------------
// Module resolution with retry (DLLs may load after the script attaches)
// ---------------------------------------------------------------------

function findModuleBase(dllName) {
  try {
    if (typeof Process.findModuleByName === 'function') {
      const m = Process.findModuleByName(dllName);
      return m ? m.base : null;
    }
  } catch (e) { /* fall through to legacy API */ }
  try {
    return Module.findBaseAddress(dllName);
  } catch (e) {
    return null;
  }
}

function installHooks() {
  const pending = HOOKS.slice();
  const installed = [];

  function tryInstallAll() {
    for (let i = pending.length - 1; i >= 0; i--) {
      const h = pending[i];
      const base = findModuleBase(h.dll);
      if (base === null) continue; // module not loaded yet, retry later
      const rva = h.va - ASSUMED_BASE;
      const rt = base.add(rva);
      try {
        Interceptor.attach(rt, {
          onEnter(args) {
            this.hookId = h.id;
            this.callId = ++callCounter;
            this.frameId = frameCounter;
            if (h.role === 'frame_boundary') {
              frameCounter++;
              this.frameId = frameCounter;
            }
            const context = this.context;
            log({
              kind: 'call', event: 'enter',
              hook_id: h.id, call_id: this.callId, frame_id: this.frameId,
              tid: this.threadId,
              module: h.dll, va_documented: '0x' + h.va.toString(16),
              rt_address: rt.toString(),
              role: h.role, desc: h.desc, cite: h.cite,
              approximate_address: !!h.approximate,
              base_unconfirmed: ASSUMED_BASE_UNCONFIRMED.indexOf(h.dll) !== -1,
              regs: regsToObj(context),
              stack: stackDwords(context, STACK_DWORDS_TO_LOG),
              pointer_scan: pointerScan(context),
            });
          },
          onLeave(retval) {
            log({
              kind: 'call', event: 'leave',
              hook_id: h.id, call_id: this.callId, frame_id: this.frameId,
              tid: this.threadId,
              module: h.dll, va_documented: '0x' + h.va.toString(16),
              rt_address: rt.toString(),
              retval: retval.toString(),
              regs: regsToObj(this.context),
              pointer_scan_at_return: pointerScan(this.context),
            });
          },
        });
        installed.push(h.id);
        log({ kind: 'hook_installed', hook_id: h.id, module: h.dll,
              va_documented: '0x' + h.va.toString(16),
              rt_address: rt.toString() });
      } catch (e) {
        log({ kind: 'hook_failed', hook_id: h.id, module: h.dll,
              va_documented: '0x' + h.va.toString(16),
              rt_address: rt.toString(), error: e.message });
      }
      pending.splice(i, 1);
    }
  }

  tryInstallAll();
  if (pending.length > 0) {
    log({ kind: 'status',
          message: pending.length + ' hook(s) waiting on module load: ' +
                   pending.map(h => h.dll).join(', ') +
                   ' -- retrying every 500ms for 60s' });
    let attempts = 0;
    const timer = setInterval(function () {
      attempts++;
      tryInstallAll();
      if (pending.length === 0 || attempts > 120) {
        clearInterval(timer);
        if (pending.length > 0) {
          log({ kind: 'status',
                message: 'gave up waiting on: ' +
                         pending.map(h => h.dll + ':' + h.id).join(', ') +
                         ' -- these modules never loaded in this process. ' +
                         'Re-run once PSI has actually opened a scan/DLL ' +
                         'load has happened, or check the process name.' });
        } else {
          log({ kind: 'status', message: 'all hooks installed (' +
                    installed.length + '/' + HOOKS.length + ')' });
        }
      }
    }, 500);
  } else {
    log({ kind: 'status', message: 'all hooks installed (' +
              installed.length + '/' + HOOKS.length + ')' });
  }
}

log({ kind: 'status', message: 'agent.js loaded, session ' + SESSION_ID +
          ', ' + HOOKS.length + ' hooks defined' });
installHooks();

// Expose a manual re-scan trigger from the Python side (in case a DLL
// loads long after the 60s auto-retry window gives up, e.g. the human
// starts PSI and this script before opening any file).
rpc.exports = {
  rescan() {
    installHooks();
    return 'rescan triggered';
  },
  status() {
    return { session_id: SESSION_ID, call_counter: callCounter,
             frame_counter: frameCounter, hooks: HOOKS.length };
  },
};
