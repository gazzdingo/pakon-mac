#ifndef PAKON_COLOUR_RENDER_H
#define PAKON_COLOUR_RENDER_H
#include "internal.h"
#include "falloff.h"

/* RE 15/11/18: out = clamp(LUT_s[NRA(in)]) then lens falloff when fo != 0.
 * rpd12: 12-bit planes (0..4095), w,h >= 11. lut_s: per-scene LUT. thr: pkc_nra_prepare thresholds.
 * out must not alias rpd12 and has the same w/h. Errors are those of pkc_nra_apply; PK_E_ARG on NULLs. */
pk_status pkc_render_scene(const pkc_planes *rpd12, const pkc_lut3 *lut_s, int falloff_on,
                           const pkc_lut3 *nra_thr, const pkc_falloff_params *fp, pkc_planes *out);
/* Same with the NRA worker-thread count of pkc_nra_apply_t. */
pk_status pkc_render_scene_t(const pkc_planes *rpd12, const pkc_lut3 *lut_s, int falloff_on,
                             const pkc_lut3 *nra_thr, const pkc_falloff_params *fp, pkc_planes *out, int threads);

/* PIScaleAndRotatePlanar's resampler (RE 39): Kodak's bicubic ImaResampleOp on 12-bit planes (interpolation 2, the only one PSI's
 * save uses). Replaces *img by the ow x oh resample (a fresh block; the old one is freed); a no-op when the size is unchanged.
 * Catmull-Rom weights in double arithmetic, vertical pass then horizontal pass, edge samples replicated, result
 * trunc(x + 0.5) clamped to 0..4095. PK_E_ARG for a size < 1 or one whose index arithmetic would overflow Kodak's 32-bit ints
 * (src * 2 * dst > INT32_MAX on an axis); PK_E_NOMEM. */
pk_status pkc_resample_bicubic(pkc_planes *img, int ow, int oh);
#endif
