#ifndef PAKON_COLOUR_ICC_H
#define PAKON_COLOUR_ICC_H
#include <stddef.h>
#include <stdint.h>
#include "data/kct.h"

/* RE 09: kodakcms.dll ETI evaluator, 12-bit in (0..4095, planar) -> 8-bit out, bit-exact. */
void pkc_icc_eval(const pkc_kct *k, const int16_t *in[3], uint8_t *out[3], size_t n);

/* kodakcms.dll's small-call evaluator 0x100168d0 (docs/re/09 "Small-call path", Task 21): the composed transform's fut
 * tables evaluated per pixel -- 12-bit in (each sample masked with 0xfff), 8-bit out. SpEvaluate takes it for a call of
 * w * h * 3 <= 1499 samples (under 500 pixels) instead of the ETI evaluator above. */
void pkc_icc_eval_small(const pkc_kfut *f, const int16_t *in[3], uint8_t *out[3], size_t n);

/* PIColorAdjustPlanar's ICC stage on a w x h planar frame as Kodak calls it (Task 21): one SpEvaluate per Ima tile, each
 * tile through the ETI evaluator or, under 500 pixels, the small-call one. Tiles (OBSERVED with an SpEvaluate hook,
 * lab/oracle/host/oracle_adjust.c EVAL_LOG; docs/re/09 "Ima tiles"): 256 x 256 from the frame's origin; with sharpening
 * (usm != 0) each axis of d samples is cut at b0 = min(129, d / 2 + 1), then every 256 after it, and not at all when
 * d < 128. PK_E_ARG on NULLs or a size < 1; PK_E_VENDOR_DATA when a small tile occurs and k carries no fut tables. */
/* The SpEvaluate tile sizes PIColorAdjustPlanar uses along one axis of d samples (with sharpening: usm != 0), in call order; at
 * most cap are written, the count is returned (0 for d < 1). Test seam for the measured tile rule. */
int pkc_icc_tile_sizes(int d, int usm, int *sizes, int cap);
pk_status pkc_icc_eval_frame(const pkc_kct *k, const int16_t *in[3], uint8_t *out[3], int w, int h, int usm);

/* The 16-bit Kodak output (docs/re/50): the same tiles and evaluators as pkc_icc_eval_frame, each carrying its result at 16 bits per
 * channel instead of 8. Reducing a value with Kodak's own 8-bit store, (v * 32640 + 2^22 - 1) >> 23, gives exactly the byte
 * pkc_icc_eval_frame writes (the ETI evaluator's value is held inside its own 8-bit code's interval; the small-call evaluator's
 * value is the one its store is made from). k must carry the fut tables (pkc_icc_select loads them); out is planar like the 8-bit one. */
void pkc_icc_eval16(const pkc_kct *k, const int16_t *in[3], uint16_t *out[3], size_t n);
void pkc_icc_eval_small16(const pkc_kfut *f, const int16_t *in[3], uint16_t *out[3], size_t n);
pk_status pkc_icc_eval_frame16(const pkc_kct *k, const int16_t *in[3], uint16_t *out[3], int w, int h, int usm);

/* Pick and load the derived table for (film_class, saturation -5..5, bnw 0..3), RE 06.
 * Reads <derived_root>/kcms/<p0>__<sat>__<bnw>.kct and its fut tables <derived_root>/kcms/fut/<p0>__<sat>__<bnw>.kfut
 * (k->fut; only for the rpd tables of the colour-negative path -- a romm table has k->fut NULL, so a frame of it with a
 * small tile is PK_E_VENDOR_DATA in pkc_icc_eval_frame). Out of range -> PK_E_ARG; a file missing -> PK_E_VENDOR_DATA. */
pk_status pkc_icc_select(const char *derived_root, int film_class, int saturation, int bnw, pkc_kct **out);
#endif
