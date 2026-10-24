#ifndef PAKON_CALIB_INTERNAL_H
#define PAKON_CALIB_INTERNAL_H
/* Internal calibration functions (prefix pkcal_, ruling C31). Task 15 (A) adds the table derivation only; Task 15 (B) adds the
 * capture, AFE convergence, tests and policy. Evidence: docs/re/30-tlb-scan-kernel.md sec 13, docs/re/43-calibration-sequence.md. */
#include <stdbool.h>
#include <stdint.h>
#include "pakon/calib.h"
#include "pakon/calstore.h"
#include "pakon/status.h"
#include "pakon/transport.h"

/* The per-pixel tables in TLB's calibration-object layout (RE 30 sec 3.1: table+0x20.. Dark, +0x30.. Gain, +0x40.. SmearC,
 * +0x4c.. per-pixel Smear in IR mode). Channel order R, G, B, IR. dark[3], gain[3] and smear[] stay NULL for a 3-channel build. */
typedef struct {
    uint16_t *dark[4];
    uint32_t *gain[4];
    uint16_t smearc[3];
    uint16_t *smear[3];
    int n_px;
} pk_cal_tables;

#define PKCAL_TABLE_LINES 128   /* both FixedPattern passes acquire 0x80 lines (TLB 0x1001f65c, FUN_1001e4a0) */

/* TLB's table builder, bit for bit (FN_bCalibrateFixedPatternDark FUN_1001e4a0 + FN_bCalibrateFixedPatternBright FUN_1001f550,
 * checked under Unicorn by core_calib_tables). Pure arithmetic, no I/O.
 * dark_sum, bright_sum: per channel, ob_px + n_px dwords of 128-line sums (LEDs off; lamp on, empty gate). Columns [0, ob_px) are
 * the optical-black pixels (CCD 6..11 at TLB's calibration window start 6), columns [ob_px, ob_px + n_px) the active pixels
 * (CCD Offset..Offset+n_px-1). TLB acquires Offset-6-ob_px gap columns in between and never reads them; drop them before the call.
 * Per channel c (all integer arithmetic as TLB's, RE 30 sec 13):
 *   Dark_i  = (u16)(D_i / 128)                                   (truncating; TLB's pass-1 average)
 *   m(x, range) = trunc(sum over range / count)                  (FUN_1001d4c0; exact in double)
 *   Dob, Dact, Bob, Bact = m over [0, ob_px) and over the active columns
 *   SmearC  = Bact > Dact ? q = trunc((Bob - Dob) * 65536 / (Bact - Dact)), kept only if 1 <= q <= 699, else 0
 *   den_i   = (u32)(B_i - D_i - Bob + Dob)                       (mod 2^32; the OB rise is subtracted even when SmearC is 0)
 *   Gain_i  = den_i == 0 ? 0 : min(0x3FFFF, low32(0x7D00000000 / den_i))   (= 64000 * 65536 * 128 / den; only the low dword
 *             of the 64-bit quotient is compared and stored, so den 1..125 gives a wrapped value)
 * channels is 3, or 4 with IR (UNCHECKED: no Kodak vector, and TLB's FixedPatternIrLag pass, FUN_1001fb80, is not ported); n_lines
 * must be 128 (TLB has no other count; the constant 0x7D00000000 folds it in). PK_E_ARG on a bad argument, PK_E_NOMEM.
 * On success the tables are malloc'd; release them with pkcal_tables_free. TLB's dark table comes from a separate 128-line pass
 * from the dark sums used for the means and the gain (RE 43 row C5); this function takes one dark sum for both. */
pk_status pkcal_derive_tables(const uint32_t *dark_sum, const uint32_t *bright_sum, int n_lines, int n_px, int channels, int ob_px,
                              pk_cal_tables *out);
void pkcal_tables_free(pk_cal_tables *t);
/* The two-pass form TLB runs on hardware (RE 43 row C5): the Dark table from pass 1 (a 128-line sum, divided by 128 and truncated), the means and the gain from pass 2. channels may be
 * 4 (IR; UNCHECKED, see derive.c). pkcal_derive_tables is this with dark1_sum == dark_sum. */
pk_status pkcal_derive_tables2(const uint32_t *dark1_sum, const uint32_t *dark_sum, const uint32_t *bright_sum, int n_lines, int n_px, int channels, int ob_px,
                               pk_cal_tables *out);
/* TLB FN_bCalibrateFixedPatternIrLag FUN_1001fb80 (RE 43 row C11), the R/G/B Dark tables of an IR build: from a 128-line acquisition with only the IR LED lit, per colour channel
 * avg_i = trunc(sum_i / 128) and Dark_c[i] = (u16)(avg_i - min_c + 300), min_c = the minimum of avg over the active pixels (from 0xFFFF; FUN_1001ce20). lag_sum is channel-major
 * (ob_px + n_px) per channel, at least 3 channels; replaces t->dark[0..2] (which must exist). */
pk_status pkcal_irlag_dark(const uint32_t *lag_sum, int n_lines, int n_px, int ob_px, pk_cal_tables *t);

/* ---------------------------------------------------------------- the calibration procedure (Task 15 B; docs/re/43-calibration-sequence.md sec 2) */
/* What a calibration needs from its caller. tick is called from every wait loop (the session passes pks_keepalive and pks_cancelled): a non-OK return (PK_E_CANCELLED, a lamp fault,
 * a lost cable) ends the run at once. progress is optional. */
typedef struct pkcal_ctx {
    pk_boards *b;
    pk_transport *t;                 /* the guarded transport the stream reads (the session's) */
    const pk_model *model;
    pk_status (*tick)(void *user);
    void (*progress)(void *user, int percent, const char *msg);
    void *user;
    char *diag;                      /* optional: a one-line reason is written here when a step fails (PK_E_CAL_LIGHT names the channel) */
    size_t diag_cap;
} pkcal_ctx;
pk_status pkcal_tick(const pkcal_ctx *c);                       /* PK_OK when c->tick is NULL */
void pkcal_progress(const pkcal_ctx *c, int percent, const char *fmt, ...) __attribute__((format(printf, 3, 4)));

/* capture.c: line acquisition. One stream (EP 0x86, no file) runs for the whole measurement; each acquisition re-arms the sync search, discards the first
 * PKCAL_SETTLE_LINES lines and then sums n_lines complete lines word by word (TLB FUN_1001d590 / FUN_1001d170: the raw words, the line-sync bit of word 0 included). */
#define PKCAL_SETTLE_LINES 2u        /* OURS, not Kodak's: lines already in the FPGA FIFO when a setting changed are not summed */
#define PKCAL_LINE_TIMEOUT_MS 3000u  /* ScanPacketReadyTimeOut (RE 41 row 22): no line within this long is PK_E_TIMEOUT */
typedef struct pkcal_cap pkcal_cap;
pk_status pkcal_cap_open(const pkcal_ctx *c, unsigned words_per_line, pkcal_cap **out);
pk_status pkcal_cap_lines(pkcal_cap *cap, unsigned n_lines, uint32_t *sum /* words_per_line dwords */);
void pkcal_cap_close(pkcal_cap *cap);                            /* stops the stream; idempotent on NULL */

/* One calibration run's state (afe.c, measure.c). Channel order R, G, B, IR. An acquisition is held in TLB's layout (FUN_1001d590 / FUN_1001d170): channel-major, n_acq dwords per
 * channel, R at [0, n_acq), G at [n_acq, 2 n_acq), B, then IR at [3 n_acq, 4 n_acq). On the wire an IR line is NOT pixel-major: it is the n_acq R G B triplets, then n_acq IR words
 * (TLB 0x1001d300 / 0x1001d352; HW 2026-10-22, corpus/traces/hw2e-calibrate-ir.ptrace). */
typedef struct pkcal_run {
    const pkcal_ctx *c;
    pk_boards *b;
    pkcal_cap *cap;
    int dpi_base;
    bool ir;
    int nch;                         /* 3, or 4 with IR */
    int lnch;                        /* channels of the line the window gives NOW: 3 until an IR run sets FPGA bit 0x100 (RE 43 row C4), then 4 */
    int ob_px, gap_px, n_acq, n_px;  /* optical-black pixels (6; 3 binned), the gap before the active pixels, acquired pixels per line, active pixels (TLB PB+0x68) */
    unsigned wire_px;                /* FPGA index 5 - index 4 */
    pk_ccd_cfg ccd;                  /* the calibration window and the AFE as last written */
    pk_cal_light light;              /* the working light settings */
    unsigned period;                 /* PWM period N for light.integration */
    uint32_t *acc;                   /* nch * n_acq scratch (channel-major) */
    uint32_t *raw;                   /* 4 * n_acq: the summed line words in wire order, before pkcal_acquire reorders them */
    /* the light as FUN_1002c5f0 last sent it this run (TLB S+0x2a0.. currents, S+0x2b8.. duties, S+0x2d8.. on-counts): the settle wait and the duty search's history use it */
    unsigned sent_cur[4], sent_on[4];
    double sent_d[4];
    bool sent_valid;
    unsigned max_ir;                 /* LC+0x68: the IR maximum of the last duty round (FUN_1001ec90 0x1001f458); kept for the record only */
} pkcal_run;
pk_status pkcal_acquire(pkcal_run *r, unsigned n_lines, uint32_t *sum);   /* the stream's lines, summed, in TLB's channel-major layout: lnch * n_acq dwords */
/* afe.c: TLB FindDarkOffset (FUN_1001e1c0). LEDs off, gain 13, offsets from +10, at most max_rounds 32-line rounds; writes r->light.afe_offset / afe_gain and the AFE. Always on a
 * 3-channel line: TLB runs it before an IR run sets the IR bit (FUN_10020dc0), so an IR calibration has black-level offsets of its own (ColNegIr Offset_R/G/B). */
pk_status pkcal_afe_converge(pkcal_run *r, unsigned max_rounds);

typedef struct { int dpi_base; bool ir; bool full; } pkcal_job;      /* full: the LED-current search from the seeds (otherwise start from `start`) */
typedef struct {
    pk_cal_light light;              /* the converged light settings */
    pk_cal_tables tables;
    uint32_t *dark1_sum, *dark_sum, *bright_sum; /* channel-major, (ob_px + n_px) dwords per channel: the 128-line dark pass 1 (the Dark table), dark pass 2 (the means) and bright sums */
    uint32_t *irlag_sum;             /* IR runs only (else NULL): the 128-line sums of FixedPatternIrLag (C11, IR LED alone), same layout; the R/G/B Dark tables come from it */
    int nch, ob_px, n_px;
    bool full;                       /* a full search ran */
    unsigned max_active[4];          /* each channel's maximum over the active pixels in the 128-line bright pass (average) */
    unsigned max_ir;                 /* IR runs: LC+0x68, the IR maximum of the last duty round (FUN_1001ec90 0x1001f458) */
    bool parent_ir_lineage;          /* set by the caller before pkcal_build_record: the parent record (a non-full run's start) has "ir_lineage" (pkcal_record_ir_lineage) */
} pkcal_result;
/* TLB FN_bCalibrateLEDs (FUN_10020dc0) for one config, with the stream, the lamp and the CCD window; leaves the lamp ON and acquisition OFF (the caller turns the lamp off). `start` carries
 * the integration, px_offset (the unit's CCD window start from the EEPROM) and, for a non-full run, the stored currents / open-gate duties / gains. PK_E_CAL_LIGHT when a channel cannot
 * be lit (EC_InsufficientLight 0xDA). The lamp must be warm. */
pk_status pkcal_measure(const pkcal_ctx *c, const pkcal_job *job, const pk_cal_light *start, pkcal_result *out);
void pkcal_result_free(pkcal_result *r);
/* The record of a measurement for pk_calstore_put (Task 14's builder): light.json, dark.u16, gain.u32, smear.json (+ smear_ir.u16), raw sums (+ raw/irlag_sum.u32 for IR) and ob.json. last_full_s is the unix time of the
 * last full search that this light derives from (now_s for a full run). */
pk_status pkcal_build_record(const pkcal_result *r, const char *unit, const char *kind, const char *parent, int64_t now_s, int64_t last_full_s, pk_calibration **out);
/* Re-derives the tables of a stored calibration from its raw sums (raw/dark1_sum.u32, raw/dark_sum.u32, raw/bright_sum.u32 + raw/ob.json) with pkcal_derive_tables2: the result equals
 * the stored dark.u16 / gain.u32 / smearc exactly. A record without raw/dark1_sum.u32 (none is written without it) uses pass 2 for both. PK_E_CORRUPT when the blobs disagree. */
pk_status pkcal_rederive(const pk_calibration *c, pk_cal_tables *out);
/* The unix time of the last full search recorded in a stored calibration (raw/ob.json "full_utc"); 0 if absent. */
int64_t pkcal_record_last_full(const pk_calibration *c);
/* An IR record's light derives from a full search made with the IR plane read where TLB reads it (raw/ob.json "ir_lineage": a full IR run, or a non-full one whose parent has it).
 * IR records written before that (HW 2026-10-22: the R G B IR words read as interleaved) lack it; their currents and duties are not TLB's and must not seed a non-full run
 * (RE 43 sec 4). 1 = has it, 0 = not. */
int pkcal_record_ir_lineage(const pk_calibration *c);

/* tests.c: the read-only Track test (RE 43 sec 8.1). Never sends 0x94 / 0x95 / 0x96 / 0x97 / 0x0B. */
pk_status pkcal_track_test(const pkcal_ctx *c, pk_film_format fmt, pk_track_result *out);

#endif
