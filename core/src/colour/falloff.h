#ifndef PAKON_COLOUR_FALLOFF_H
#define PAKON_COLOUR_FALLOFF_H
#include "internal.h"

/* RE 11 (incl. both corrections). Lens-falloff parameters from
 * anselinstalldir/dataPathItems/falloff/falloff-srcType-SUC-NEGATIVE_35-NO.dpi
 * (scale 1250, max 4095, stops 0.7f, exposure_min -0.5, exposure_max 7.0). */
typedef struct {
    int scale;
    int max;
    float stops;        /* stored as float, as Kodak does */
    float exp_min;      /* true stops; floats at the falloff Impl +0x1c / +0x20, compared as floats (FUN_102038f0) */
    float exp_max;
} pkc_falloff_params;

/* PK_E_VENDOR_DATA if the file is unreadable or any key is missing. */
pk_status pkc_falloff_params_load(const char *vendor_root, pkc_falloff_params *p);

/* 1 if the op is exported for a scene whose SBA exposure is sba_exposure_stops (pkc_sba_exposure_stops, docs/re/23):
 * FUN_102038f0 with Kodak's types: scale > 0 (int), stops > 2^-23 ([0x1059b344], a float compare), then
 * exp_min <= e and e <= exp_max as floats (fcomp of the float exposure; NaN is off). e is the float Kodak stores at the
 * scene ctx +0x4bc, passed as a double (exact); it is compared as (float)e. Kodak-pinned at both exposure edges
 * (-0.5 / -1.0 and 7.0 / 7.5 stops) by test_exposure. */
int pkc_falloff_enabled(const pkc_falloff_params *p, double sba_exposure_stops);

/* PK_E_ARG on NULL args or w/h <= 0, PK_E_NOMEM if the correction table cannot be allocated, PK_OK otherwise
 * (including the identity case, which leaves the image unchanged).
 * In-place radial correction on all 3 planes (identity if scale <= 0 or !(stops > 0)).
 * Samples must be 0..4095; there is no lower clamp, as in Kodak. */
pk_status pkc_falloff_apply(pkc_planes *img, const pkc_falloff_params *p);
#endif
