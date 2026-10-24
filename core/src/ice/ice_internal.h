#ifndef PAKON_ICE_INTERNAL_H
#define PAKON_ICE_INTERNAL_H
/* Digital ICE internals (RE 44): the per-frame context the generated per-pixel routines read, and Kodak's table lookups. */
#include <float.h>
#include <stddef.h>
#include <stdint.h>
#include "colour/analysis/kint.h"      /* pkc_ftol64, pkc_wrap32: MSVC _ftol, low dword kept */

/* Float configuration (RE 44 sec. 7): plain IEEE double with Kodak's float32 stores, no fused multiply-add, no reassociation. The
 * build also sets -ffp-contract=off; these make a build with another driver (Xcode, SwiftPM) fail instead of drifting. */
#if defined(__FAST_MATH__) || FLT_EVAL_METHOD != 0
#error "Digital ICE needs strict IEEE double evaluation: no -ffast-math, FLT_EVAL_METHOD 0 (not x87)"
#endif
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

/* Kodak's tables (tables.c): computed once from the RE 44 sec. 2.2 / 2.4 formulas by pki_tables_init(), which pk_ice_apply calls first.
 * Read-only afterwards. */
extern float pki_log[65536];
extern int64_t pki_ahi[256], pki_alo[256];
extern double pki_thr_high_slope, pki_thr_low_slope;
void pki_tables_init(void);

/* the object's float area from +0x28c4 (RE 44 sec. 2.2): log table (16384 entries), the zero gap, gain table 1 at float index
 * 0x10000, gain table 2 at 0x20000. Gain lookups index it without bounds in Kodak; here an index outside it reads 0. */
#define PKI_OBJF 0x30000

typedef struct {
    double m, c0, A, B;                /* statistics and weight map (float32 values) */
    const float *L;                    /* pki_log: [0,16383] Kodak's, the rest the zero gap */
    const int64_t *ahi, *alo;          /* pki_ahi, pki_alo */
    int gain_cls;                      /* 0: gain table 1 (m < 0.035f), 1: gain table 2 */
} pki_ctx;

typedef void (*pki_fn)(const pki_ctx *, uint16_t *const[4], ptrdiff_t, int, int);
typedef struct { pki_fn a[3], b[3], mid[5]; } pki_variants;      /* main: row 0, row 1; worker: row h-2, row h-1; then mid rows */
extern const pki_variants pki_variant_table[4][2];

/* __ftol, callers take eax */
static inline int32_t pki_ftol32(double x) { return pkc_wrap32(pkc_ftol64(x)); }

/* G[i] of the gain table the routine picked: T1 = 1.3 on [0,16383) with 2.3 on [0,36); T2 = 0.8 on [0,16383); 0 elsewhere. */
static inline double pki_gain(const pki_ctx *s, int32_t i) {
    int64_t idx = (int64_t)i + (s->gain_cls ? 0x20000 : 0x10000);
    /* Outside the area Kodak reads whatever lies there (its Ahi table bytes, then the heap, up to an access violation). That needs
     * |DL| >= 0x10000: the statistics can give it only with IR >= 46341, where Kodak's 32-bit v*v wraps negative and the weights can
     * cancel (sv2 near 0, c0 huge). The scanner's cross-talk IR (docs/re/45 U2) stays far below that. The port stays memory safe
     * and reads 0 there, which diverges from Kodak. */
    if (idx < 0 || idx >= PKI_OBJF) return 0.0;
    if (idx < 16384) return (double)s->L[idx];
    if (idx >= 0x20000) return idx < 0x20000 + 16383 ? (double)0.8f : 0.0;
    if (idx >= 0x10000) {
        int64_t j = idx - 0x10000;
        return j < 36 ? (double)2.3f : (j < 16383 ? (double)1.3f : 0.0);
    }
    return 0.0;
}

/* 0x100014c0: x = a + 0.5 capped at 16383; i = ftol(x); ((Ahi[(i >> 8) & 255] * Blo[i & 255]) >> 20) - 1, 16-bit store */
static inline uint16_t pki_antilog(const pki_ctx *s, double a) {
    double x = a + 0.5;
    if (x > 16383.0) x = 16383.0;
    int32_t i = pki_ftol32(x);
    int64_t p = (s->ahi[((uint32_t)i >> 8) & 255] * s->alo[(uint32_t)i & 255]) >> 20;
    return (uint16_t)(uint64_t)(p - 1);
}
#endif
