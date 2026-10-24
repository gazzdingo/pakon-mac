#ifndef PAKON_DECODE_STRIP_H
#define PAKON_DECODE_STRIP_H
/* Decode part 2 (Task 17): TLB's lo-res strip (the accumulators at the tail of FUN_100246d0), the row profile, the stored-row count (FUN_10005660)
 * and the registered read-out (FUN_100013b0). Internal (prefix pkd_, ruling C31). Evidence: docs/re/30-tlb-scan-kernel.md sec 7-9, checked bit for
 * bit against Kodak's code under Unicorn by core_decode_kodak (lab/vectors/gen_lores.py -> lores.pkv). */
#include <stddef.h>
#include <stdint.h>
#include "decode/kernel.h"

typedef struct {
    int ratio;                  /* 4, 6, 8 */
    int width;                  /* lo-res pixels per row (250 for 1000/1500/2000 px at ratio 4/6/8) */
    int rows;                   /* stored (declared) rows: TLB strip field +0x14 (set by pkd_strip_new, redeclared by pkd_strip_finish) */
    uint16_t *plane[3];         /* un-registered: plane c of row r at plane[c] + r * width; rows + 2 rows are allocated, the 2 after `rows` stay 0 */
    uint8_t *profile;           /* 3 bytes per row, stored order plane2, plane1, plane0; same row index as the strip row */
    int film;                   /* TLB's param_5: non-zero (the default) advances the row and profile pointers at an emission */
    /* private */
    int alloc_rows;             /* rows allocated: hires_lines / ratio + 3 */
    int count, row;             /* TLB's block counter (ratio .. 1) and weight row (0 .. ratio-1) */
    size_t wr;                  /* the row index the next emission writes (advances only with film) */
    size_t film_lines;          /* lines fed with film != 0 (TLB's hand-off count strip+0xca0, INFERRED, RE 30 UNRESOLVED 2) */
    uint32_t *acc[3];           /* width * ratio / 2 pmaddwd accumulators per plane */
    uint32_t own_sums[3];       /* the profile sums when the caller shares none */
    uint32_t *prof_sum;         /* sum of the per-line mean4 over the block, planes 0, 1, 2: own_sums, or the caller's roll-lifetime sums */
} pkd_strip;

/* TLB FUN_10005660: stored rows = hires_lines / ratio + 1, and 0 for 0 lines (UC, RE 30 sec 8.2). */
size_t pkd_strip_rows_for(int ratio, size_t hires_lines);
/* TLB FUN_10005590 (strip vtable +0x20): the rows the framing reads, R = rows - (planes - 1), 0 below that. This is the profile length the framing
 * takes (ruling S-R19, RE 30 sec 8.2). */
size_t pkd_strip_readable_rows(size_t rows, int planes);

/* ratio 4 / 6 / 8, 0 < width <= 4096; hires_lines = the window the strip is allocated for (rows are allocated for hires_lines / ratio + 3). */
pk_status pkd_strip_new(int ratio, int width, size_t hires_lines, pkd_strip **out);
/* Ruling S-R41 (copy Kodak, RE 30 sec 7.4): Kodak's profile sums are globals that init does not clear, so a block left partial by one strip leaks into row 0 of the
 * next. Lifetimes: SESSION (Kodak's globals live as long as the process: the caller keeps one array for the whole scanner session, zeroes it once at session
 * start and must NOT re-zero it between strips or rolls) = a uint32_t sums[3] passed to pkd_strip_share_profile_sums;
 * PER STRIP = the pkd_strip, the pkd_kernel_state (pkd_kernel_init per strip) and the accumulators, which start at zero. The strip reads and writes the shared
 * array in place (call before the first feed, keep it alive as long as the strip). Without a call the sums are private to the strip and start at zero. */
void pkd_strip_share_profile_sums(pkd_strip *s, uint32_t sums[3]);
/* One raw USB line through the kernel (cfg->n_px must be width * ratio, cfg->ratio == ratio), the hi-res planar line to hires_planar_out
 * (cfg->channels * n_px words) and, from the three colour planes, the lo-res accumulation; every ratio-th line from the first call emits a row.
 * PK_E_ARG when an emission would pass the allocated rows. */
pk_status pkd_strip_feed(pkd_strip *s, const pkd_kernel_cfg *c, pkd_kernel_state *st, const uint16_t *raw_line, uint16_t *hires_planar_out);
/* TLB's param_5: lines fed from now on count as film (default 1). Rows emitted with film 0 are written at the unadvanced row and overwritten. */
void pkd_strip_set_film(pkd_strip *s, int film);
/* Declares the stored rows: rows_for(ratio, lines fed with film). PK_E_ARG, rows unchanged, when rows + 2 would pass the allocation (more film lines than the window). */
pk_status pkd_strip_finish(pkd_strip *s);
void pkd_strip_free(pkd_strip *s);

/* Registered read-out (FUN_100013b0): plane c (c = 0, 1, 2) of destination row r comes from stored row row0 + r + c * d; with 4 planes the IR plane
 * (stored plane 3, RE 45 sec 2.2) is the same stored row as plane 0 (row0 + r), not staggered. stored rows are `stride` words apart (a crop reads columns col .. col+width-1, col + width <= stride); out_planes[c] is rows * width words. Bounds rule
 * (C27): PK_E_ARG when rows == 0, rows < 2 d (Kodak overruns), or row0 + rows - 1 + 2 d >= stored_rows (a Kodak over-read of uninitialised memory;
 * inside the strip's 2 zero rows after `rows` it is Kodak's defined output, so pass stored_rows = rows + 2 for a strip). */
pk_status pkd_readout_planes(const uint16_t *const stored_planes[], int planes, size_t stored_rows, int stride, int col, int width, int d, size_t row0,
                             size_t rows, uint16_t *const out_planes[]);
pk_status pkd_readout(const uint16_t *const stored_planes[3], size_t stored_rows, int width, int d, size_t row0, size_t rows, uint16_t *const out_planes[3]);
/* The lo-res read (FUN_10005600, d = PKD_LORES_STAGGER) of a strip: stored_rows = s->rows + 2. */
pk_status pkd_strip_read_lores(const pkd_strip *s, size_t row0, size_t rows, uint16_t *const out_planes[3]);

/* Lo-res stagger d = 1 (strip row units). The hi-res read stagger is the ratio (4 / 6 / 8 by base; RE 30 sec 8.2, UC): no fixed constant. */
#define PKD_LORES_STAGGER 1
#endif
