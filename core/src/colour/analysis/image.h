#ifndef PAKON_COLOUR_ANALYSIS_IMAGE_H
#define PAKON_COLOUR_ANALYSIS_IMAGE_H
#include <stdint.h>
#include "internal.h"

#define PKC_AIMG_SIZE 376          /* _AnselAnalysisImageSize_ (0x178) */
#define PKC_GRID_ROWS 24
#define PKC_GRID_COLS 36
#define PKC_GRID_N (PKC_GRID_ROWS * PKC_GRID_COLS)

/* RE 19: analysis-image size. If max(w,h) > 376 the frame is resampled so its larger side is 376:
 * s = 1/(max/376), out = (int)(dim*s + 0.5) (pathUtils::resampleAnslysisImage 0x100d8030); otherwise w,h unchanged. */
void pkc_analysis_dims(int w, int h, int *ow, int *oh);

/* RE 19: the SBA analysis image of a planar lo-res frame (w x h, 3 planes).
 * max(w,h) <= 376: a copy. Otherwise Kodak's ImaResampleOp bilinear (0x100d5e40) to pkc_analysis_dims; source
 * samples are read as int16 (movswl). out->p[] is allocated here (one block); free it with pkc_analysis_image_free.
 * PK_E_ARG on NULLs or w,h < 1; PK_E_IMAGE_TOO_SMALL if a resampled side would be 0; PK_E_NOMEM. */
pk_status pkc_analysis_image(const uint16_t *lores[3], int w, int h, pkc_planes *out);
void pkc_analysis_image_free(pkc_planes *img);

/* createAlgData (0x1028ceb0) bands 0-2: the 24x36 block-mean grid (lab/reference pakon_sba_measure
 * build_grid_from_source), row-major, samples read as uint16.
 * Kodak then adds a per-channel offset clamp(table[c] - ref[c], -50, 50) (0x1028d165..0x1028d1ac), clamps to
 * 0..0xfff (0x1028d2bb..0x1028d306) and subtracts sba+0x14[c]. On the AddScene/analyzePass1 path the offset and the
 * subtrahend are 0 (RE 19: grids match Kodak's in every cell), so this port applies only the clamp.
 * Each block is si rows x so cols read flat (row * w + col), so a block reaching past a row's end continues on the next
 * row, as Kodak's sampler does (fcn.1028cd10).
 * Errors: PK_E_UNSUPPORTED for an aspect whose last block would read past the image's last sample (Kodak averages
 * whatever follows its buffer: t14w2's 356 x 123 frame); PK_E_ARG on NULLs and when any block mean > 0x7d00
 * (Kodak fails with -0x9b; ruling R14 maps it to PK_E_ARG -- not 12-bit data); PK_E_IMAGE_TOO_SMALL if w < 36 or
 * h < 24 (Kodak returns -0xa0 there). On error grid[] is unspecified. */
pk_status pkc_grid24x36(const pkc_planes *img, int32_t grid[3][PKC_GRID_N]);

/* pkc_grid24x36 for a block that reads past the image: those reads are clamped to the image's last row instead of refused.
 * NON-KODAK (owner's choice R41; Kodak reads heap memory there). *clamped (may be NULL) = 1 when any read was clamped. Other
 * errors as pkc_grid24x36 (without the PK_E_UNSUPPORTED). */
pk_status pkc_grid24x36_clamped(const pkc_planes *img, int32_t grid[3][PKC_GRID_N], int *clamped);

/* analyzePass1's splice crop (AnsSbaCapabilityImpl, 0x102183cb..0x10218617; Task 21, docs/re/19 section "Splice crop"):
 * before the grid, each SBA instance's pass 1 counts the "splice" columns of the scene's current image -- columns where
 * at least need = _ftol(h * 0.9 + 0.5) samples of band 0 exceed thr (signed compare; 0x102136c0) -- and remembers the
 * first such column. With ratio = (double)count / w in (0, splice_pct * 0.01] and w - count >= 36, the image the grid
 * and the pass-1 measure see is a copy without count columns: [0, w - count) when the first splice column lies right of
 * w * 0.5, else [count, w) (Kodak keeps a block of the right width; it does not look where the columns were).
 * thr = dpi fpo[0] + fog + 100 (the words at sba+0x4d0e / +0x4d1e), splice_pct = dpi splicePct (sba+0x4d30).
 * info (may be NULL) receives count, the first column (-1: none), ratio and whether it cropped (Kodak's numSplicesCols /
 * spliceStartCol / splicePctDetected / sba+0x5060). When it crops, out->p[] is allocated (free with
 * pkc_analysis_image_free); otherwise out is zeroed and the caller keeps img. PK_E_ARG on NULLs or a size < 1; PK_E_NOMEM. */
typedef struct { int count, start, cropped; double ratio; } pkc_splice;
pk_status pkc_splice_crop(const pkc_planes *img, int thr, int splice_pct, pkc_planes *out, pkc_splice *info);
#endif
