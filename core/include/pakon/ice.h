#ifndef PAKON_ICE_H
#define PAKON_ICE_H
/* Digital ICE dust and scratch removal, ported bit for bit from Kodak's DMLDICELib.dll (DMLDICEProcess as TLB and PSI call it).
 * docs/re/44-ice-algorithm.md is the transcription (every constant, the order of every sum, every float32 store); docs/re/45
 * says where TLB applies it. Kodak truth: the Wine oracle's 42 vectors (lab/vectors/gen_ice_golden.py); the kept check is
 * core_ice_kodak, which compares every output plane and m / c0 / A / B byte for byte.
 *
 * The call is frame level and frontend agnostic: one frame's crop, four linear 14-bit planes R, G, B, IR (docs/re/45 sec. 2.4),
 * corrected in place. R, G and B are repaired where the infra-red plane shows dust or a scratch, and the IR plane is rewritten
 * with the value a clean film would show. All of the work is single threaded and deterministic. Kodak splits the rows over two
 * threads whose windows cross the seam; the port reproduces the outcome of the order in which the worker finishes first (RE 44
 * sec. 6.1): the rows [ceil(h/2), h) are done before [0, ceil(h/2)), each in raster order.
 *
 * Precision: IEEE double arithmetic with a float32 store wherever Kodak stores one (x87 at PC53, RE 44 sec. 7). The library is
 * built with -ffp-contract=off; a build on a target that evaluates double expressions in extended precision is not supported. */
#include <stddef.h>
#include <stdint.h>
#include "pakon/status.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The tags TLB passes (docs/re/45 sec. 3.1 step 7: {0x30, planes, w, h, 300, filmtype != 2, 0, 0,0,w-1,h-1}). Zero-initialise,
 * then set what you need: a zeroed pk_ice_opts is exactly TLB's call. */
typedef struct {
    int bits;            /* tag s3: sample bits. 14 (or 0 = 14) only; 12 returns PK_E_UNSUPPORTED (RE 44 UNRESOLVED 6) */
    int dpi;             /* tag d4 (TLB passes 300). Kodak never reads it; accepted and ignored */
    int neg;             /* tag d5 (filmtype != 2). Kodak never reads it (RE 44 sec. 2.1); accepted and ignored */
    int roi;             /* tag d6: nonzero selects Kodak's custom-ROI routines with the rectangle below. TLB never sets it */
    int x0, y0, x1, y1;  /* tag d7..d10: inclusive pixel rectangle, used when roi != 0. Pixels outside are neither read nor written
                          * by the correction; the statistics use the rectangle only */
} pk_ice_opts;

/* What Kodak keeps in its object after Process (obj +0x28ac..+0x28b8) plus two derived numbers. */
typedef struct {
    float m, c0;         /* slope of log IR against log R, and the clean-film log IR level. c0 is the x87 NaN 0xffc00000 when no
                          * statistics patch was valid; then nothing is corrected */
    float A, B;          /* weight map: t = clamp(A * (c0 - d) + B) */
    float thr;           /* defect threshold on c0 - D */
    int64_t ndefect;     /* pixels the defect test selected (and the correction rewrote) */
} pk_ice_stats;

/* 1 when this build has Digital ICE, 0 when it was built without it (CMake PK_WITH_ICE=OFF, the public source tree: the 88 per-pixel
 * routines are generated from Kodak's code and are not published). With 0, pk_ice_apply returns PK_E_UNSUPPORTED and a frontend must not
 * offer ICE. */
int pk_ice_available(void);

/* Corrects one frame in place.
 *   r, g, b, ir  four planes of uint16, w x h samples, row stride `stride` samples (>= w), 14-bit linear values. The IR plane
 *                is written too (Kodak recomputes it from the repaired R), so it is not const.
 *   opts         NULL = TLB's tags (full frame, 14 bit).
 *   out_stats    optional.
 * PK_E_ARG: a null plane, w < 1, h < 1, stride < w, an ROI outside the frame, and the sizes Kodak's code crashes on (RE 44 sec.
 * 4.1): the (ROI) height < 8, or < 32 when the image has >= 1,000,000 pixels (the statistics step is then 4), and the (ROI)
 * width <= 3. Frames of width 4..7 (or with too few valid IR samples) run and change nothing, as in Kodak. Nothing is written
 * on an error. PK_E_NOMEM if the scratch tables cannot be allocated.
 *
 * IR samples above 16383 (docs/re/45 U2): Kodak indexes its 16384-entry log table with the raw word; the words behind the table
 * are the object's never-written gap. The port reads 0 there (RE 44 sec. 2.2: zero-filled, INFERRED on Windows; observed zero under
 * Wine). It is memory safe and does not clamp. TODO(R27): confirm on the Intel/XP box. */
pk_status pk_ice_apply(uint16_t *r, uint16_t *g, uint16_t *b, uint16_t *ir, int w, int h, size_t stride,
                       const pk_ice_opts *opts, pk_ice_stats *out_stats);

#ifdef __cplusplus
}
#endif
#endif
