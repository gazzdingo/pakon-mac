/* The SBA exposure: fcn.102ae9d0's half-stop word (scene+0x38fc) and getSbaExposure's float (docs/re/23). */
#include "analysis/exposure.h"
#include "analysis/kint.h"

int16_t pkc_sba_exposure_halfstops(int16_t yword, int32_t yo) {
    int32_t x = pkc_wrap32((int64_t)yword - yo);          /* 0x102aebd0 movsx eax, word [esi]; 0x102aebe0 sub eax, [edi+0xc] */
    int32_t p = pkc_wrap32((int64_t)x * 1190);            /* 0x102aebe3 imul eax, eax, 1190 */
    return pkc_sx16(pkc_bias_div(p, 85000, 170000));      /* 0x102aebe9..0x102aec0a; 0x102aec13 mov word [esi+0x5a], ax */
}

pk_status pkc_sba_exposure_stops(const pkc_sba_triple_out *t, const pkc_sba_ctx *ctx, double *stops) {
    if (!t || !ctx || !stops || t->triple[0] != pkc_sx16(t->triple[0])) return PK_E_ARG;
    int32_t yo, c1, c2;
    pkc_sba_axes(ctx->opening[0], ctx->opening[1], ctx->opening[2], &yo, &c1, &c2);   /* fcn.1028b8d0's [esp+0x28] */
    int16_t hs = pkc_sba_exposure_halfstops((int16_t)t->triple[0], yo);
    *stops = (float)hs * 0.5f;                            /* 0x1012428a fild; fmul dword 0.5f; fstp dword: exact */
    return PK_OK;
}
