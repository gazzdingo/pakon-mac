#ifndef PAKON_DECODE_KERNEL_H
#define PAKON_DECODE_KERNEL_H
/* Decode part 1 (Task 16): TLB's scan-line kernel FUN_100246d0 (dark, smear, gain, clamp, unpack) and line sync. Internal (prefix pkd_, ruling C31).
 * Evidence and every fixed-point rule: docs/re/30-tlb-scan-kernel.md sec 2 and 5; checked bit for bit against Kodak's own code under Unicorn by
 * core_decode_kodak (vectors lab/vectors/gen_kernel.py). Only the arithmetic of the call is here; TLB's lo-res accumulation and profile (Task 17)
 * are separate. */
#include <stddef.h>
#include <stdint.h>
#include "pakon/status.h"
#include "calib/calib.h"

typedef struct {
    uint16_t mean4[3];          /* previous corrected line: 4 x the per-channel mean, ch0 (R), ch1 (G), ch2 (B) (TLB DAT_1007d3a8 / 3a0 / 398) */
} pkd_kernel_state;

typedef struct {
    int n_px;                   /* pixels per line, a positive multiple of 4 */
    int channels;               /* 3, or 4 with the IR plane */
    int ratio;                  /* lo-res decimation 4 / 6 / 8 (base 4 / 8 / 16): the IR cross-talk tail differs at 6 (RE 30 sec 5.4) */
    const pk_cal_tables *t;     /* dark/gain for every channel; smearc (3 channels) or the per-pixel smear (4) */
    unsigned ir_crosstalk_factor;   /* 0 = off */
} pkd_kernel_cfg;

void pkd_kernel_init(pkd_kernel_state *s);   /* TLB's init call: the mean state is zero */
/* One raw USB line (pixel-interleaved R,G,B words, then n_px IR words with IR; channels * n_px words, unshifted and unmasked as the scanner
 * sends them) -> planar corrected line (channels * n_px u16: R plane, G plane, B plane, IR plane; R, G, B 0..0x3FFF). Updates the state.
 * IR can exceed 0x3FFF at ratio 4 and 8 when a cross-talk factor is set (TLB's clamp quirk, reproduced). PK_E_ARG on a bad configuration. */
pk_status pkd_kernel_line(const pkd_kernel_cfg *c, pkd_kernel_state *s, const uint16_t *raw, uint16_t *planar_out);

/* Line sync (v1 segment_lines, RE 30 sec 2.1): every word with bit 0 set starts a line; a gap of exactly words_per_line to the next start is a
 * clean line, any other gap is a glitch and is skipped (Kodak aborts instead). The last start counts when words_per_line words follow it. The
 * output is one malloc'd block of lines * words_per_line words, lines back to back (free it); *lines_out is NULL when there are no lines. */
typedef struct { size_t lines, partial_tail_words, resyncs, lead_words; } pkd_sync_report;
/* lines = clean lines; resyncs = an estimate of the lines lost to glitch gaps (each bad gap counts max(1, gap / words_per_line): a missing start bit counts 2, a stray bit 0 inside a line also 2 though 1 is lost); non-zero means a glitch; lead_words = words before the first start;
 * partial_tail_words = every word after the last line returned (an incomplete final line, or words beyond a complete one; 0 if none). A caller that needs the stream's line grid must treat resyncs != 0 as an error. */
pk_status pkd_sync_lines(const uint16_t *words, size_t n_words, unsigned words_per_line, uint16_t **lines_out, pkd_sync_report *rep);
#endif
