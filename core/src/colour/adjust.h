#ifndef PAKON_COLOUR_ADJUST_H
#define PAKON_COLOUR_ADJUST_H
#include "internal.h"
#include "pakon/colour_types.h"

/* RE 06 §2.2: PIColorAdjustPlanar's contrast/RGB LUTs, including Kodak's clamp-loop bug
 * (a channel with zero sum keeps out-of-range entries after the first in-range one, e.g.
 * contrast 100, r 25 -> G[4095] = 4222). *active = 0 when Kodak skips the LUT stage; out is then
 * the identity. Fields are clamped to their pk_adjust ranges first. Cannot fail. */
void pkc_adjust_lut(const pk_adjust *a, pkc_lut3 *out, int *active);

/* RE 06 §2.3: 3x3 separable [1 2 1]/4 unsharp mask, in place, 0..4095 out; the 1-pixel border
 * is filtered with the image edge replicated (oracle-verified). sharpness 0 is a no-op.
 * PK_E_ARG on NULLs or sharpness outside 0..2000; PK_E_IMAGE_TOO_SMALL if sharpness != 0 and
 * w or h < 3 (Kodak's convolution rejects images smaller than the kernel); PK_E_NOMEM. */
pk_status pkc_adjust_usm(pkc_planes *img, int sharpness);

/* LUT stage then USM, in place on 12-bit planes (LUT index clamped to 0..4095). Output can exceed
 * 4095 when only the LUT runs (the bug); the ICC stage masks to 12 bits. The caller then runs
 * pkc_icc_select(film_class, a->saturation, a->bnw) + pkc_icc_eval.
 * PK_E_ARG on NULLs or any pk_adjust field out of range; otherwise as pkc_adjust_usm. */
pk_status pkc_adjust_apply(pkc_planes *img, const pk_adjust *a);
#endif
