#ifndef PAKON_COLOUR_ANALYSIS_EXPOSURE_H
#define PAKON_COLOUR_ANALYSIS_EXPOSURE_H
#include <stdint.h>
#include "internal.h"
#include "analysis/sba_measure.h"
#include "analysis/sba_pref.h"

/* The SBA exposure (docs/re/23-sba-exposure.md): the per-scene value the falloff export gate (pkc_falloff_enabled, RE 11)
 * and the flesh calculator (pkc_flesh_delta's exposure, RE 16 section 8) read.
 *
 * Kodak computes it inside the pass-2 triple, fcn.1028b8d0, which calls fcn.102ae9d0 (0x1028c369) with the scene's out
 * struct (scene+0x38a2, word 0 = the triple's Y word, int16(L + Yo)) and the opening block (R, G, B, Y, C1, C2 of the
 * dpi fpo; Yo = its Y). The writer stores, at 0x102aebd0..0x102aec13, one int16 word at scene+0x38fc:
 *     x = Y word - Yo;  p = x * 1190;  hs = (p + (p >= 0 ? 85000 : -85000)) / 170000  (C truncation)
 * every step a 32-bit register (sub, imul, lea wrap; the idiv by 170000 is an exact imul-magic / sar 17 sequence), i.e.
 * x * 7 / 1000 half-stops rounded half away from zero. getSbaExposure (0x101241a0, 0x10124277..0x10124294) hands on
 * fild dword; fmul dword 0.5f; fstp dword -> scene ctx +0x4bc: stops = (float)hs * 0.5f, exact. Integer only, plus that
 * exact float product: no x87 transcendental (R27) and no precision-control dependence.
 * Both pass-2 kinds (FOS2, SHORT2) and both SBA instances write it; getSbaExposure reads the "sba" instance's (the one
 * whose triple runs before the scpLut), so Task 19 calls this on that instance's pkc_sba_triple output.
 * Kodak-exact on every writer call of lab/rollbal/truth/t18 (54 runs: the four rolls on both film bases, every crafted
 * roll of Tasks 12-18, RE 11's falloff-gate variants, and stores at the writer's operands: ties, the gate edges, wraps). */

/* fcn.102ae9d0's word from the Y word it reads (movsx) and the opening Y dword. Total: every input has a result. */
int16_t pkc_sba_exposure_halfstops(int16_t yword, int32_t yo);

/* The exposure in stops of a scene whose pass-2 triple (the sba instance's) is t: Yo = the Y axis of ctx->opening
 * (pkc_sba_axes, as fcn.1028b8d0 0x1028b967..), *stops = the float Kodak stores at ctx+0x4bc, as a double (exact).
 * PK_E_ARG on NULLs or a triple Y word outside int16 (pkc_sba_triple stores words); *stops is not written on error. */
pk_status pkc_sba_exposure_stops(const pkc_sba_triple_out *t, const pkc_sba_ctx *ctx, double *stops);
#endif
