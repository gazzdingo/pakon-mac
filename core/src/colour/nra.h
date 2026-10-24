#ifndef PAKON_COLOUR_NRA_H
#define PAKON_COLOUR_NRA_H
#include "internal.h"

/* RE 15. Reads <vendor_root>/anselinstalldir/dataPathItems/noiseTable/negative35-0100.tbl and
 * .../nra/nra-srcType-speed-negative35-default.dpi, applies the noise-falloff edit and builds the
 * per-band threshold LUT (nearbyint). PK_E_VENDOR_DATA if a file is unreadable, the table is not
 * exactly 4096 rows x (code + 3 bands), or NoiseScale/WindowSize is missing (WindowSize must be 11). */
pk_status pkc_nra_prepare(const char *vendor_root, pkc_lut3 *thresholds);
/* The same for a film ISO (pkc_film_iso; 0 = unknown): the noise table noiseTable.map selects for a 35 mm negative of that
 * ISO (negative35-0100 / -0200 / -0400 / -0800.tbl; ranges inclusive) and the nra dpi of that ISO if one is shipped.
 * Kodak-pinned on the balanced hi-res images of truth t19 runs_codes (ISO 0, 25, 50, 100, 125, 160, 200, 400, 800, 1000,
 * 1600, 3200). pkc_nra_prepare is ISO 0. Errors of pkc_map_select and pkc_nra_prepare_files. */
pk_status pkc_nra_prepare_film(const char *vendor_root, int film_iso, pkc_lut3 *thresholds);

/* Same, from explicit file paths (used by pkc_nra_prepare and by tests). */
pk_status pkc_nra_prepare_files(const char *tbl_path, const char *dpi_path, pkc_lut3 *thresholds);

/* 11x11 "star" noise filter on 12-bit planes (values must be 0..4095). in->w/h == out->w/h;
 * out must not alias in. PK_E_IMAGE_TOO_SMALL if w < 11 or h < 11. */
pk_status pkc_nra_apply(const pkc_planes *in, pkc_planes *out, const pkc_lut3 *thr);
/* Same with a worker-thread count: 0 = automatic (cores, at most 8), 1 = the calling thread only, N = up to N (at most 8);
 * < 0 is PK_E_ARG. The output does not depend on it. */
pk_status pkc_nra_apply_t(const pkc_planes *in, pkc_planes *out, const pkc_lut3 *thr, int threads);
#endif
