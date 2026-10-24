#ifndef PAKON_COLOUR_ANALYSIS_SBA_PREF_H
#define PAKON_COLOUR_ANALYSIS_SBA_PREF_H
#include <stdint.h>
#include "internal.h"
#include "analysis/sba_measure.h"
#include "analysis/fos.h"

/* The scene balance after the measure: the orderFpo triple of a pass-2 scene (FUN_1028ae00 called by fcn.1028b8d0,
 * with the FOS-pointer arms of fcn.102aece0 / fcn.102b7440 it reads: docs/re/17), the Preference shift words
 * (fcn.1028c780, mode 0) and setShifts' (ntd, ctd) = (1, 2) combine of the two instances' shifts through the roll
 * scpLut (0x10100a37). Ported from the disassembly and pinned against Kodak at x87 PC53 (lab/rollbal/truth/t13). */

#define PKC_SFS_NX 50                  /* the 50x83 weight table: a (C1) cells ... */
#define PKC_SFS_NY 83                  /* ... by b (C2) cells, index b_cell + a_cell * 83 */
#define PKC_SFS_N (PKC_SFS_NX * PKC_SFS_NY)

/* Roll-static inputs, from the dpi (anselinstalldir/dataPathItems/sba/SbaDPI/sba-CN-default.dpi) and its SFS row file. */
typedef struct {
    /* Makesfs (fcn.102ac820, called by AnsSfsTableDPI's ctor 0x1028982c) applied to the six rows of
     * sba/Sfs/<dpi sfsTable>: the 50x83 signed-byte weight table fcn.1028b8d0 hands FUN_1028ae00 (sba+0x3c08 +0x2c). */
    int8_t sfs[PKC_SFS_N];
    /* Preference's dpi block (arg 3), as fcn.10214f20 fills it, by 16-bit word: 0-2 fpo, 3-5 fpa, 6-8 neu, 9-11 neo,
     * 12-14 dmd, 15 pcls, 16 pcwf, 17 ix_pcwf, 18 nonFlashAdj, 19 fmt, 20/21 = 50/83, 22/23 a pointer (0 here), 24 cmm,
     * 25 fog, 26 fxr, 27 blk, 28 bxr, 29 ll1, 30 ll2, 31 = 140, 32 mff, 33 = ftol(neutralButton * neutralUnderConstraint),
     * 34 = ftol(neutralButton * neutralOverConstraint), 35 = neutralBalancePoint * sqrt3 rounded half away (0x10215084).
     * Kodak-observed equal to this on every call of every truth roll (bar the pointer). Preference reads 0-11, 15, 24
     * and 33-35. */
    int16_t blob[36];
} pkc_sba_pref;

/* Load the dpi keys above and build the SFS table. derived_root holds imau_tables/sfs_sin_105a8830.bin (Makesfs' sine
 * table). PK_E_ARG on NULLs; PK_E_NOMEM if the dpi parser runs out of memory; PK_E_VENDOR_DATA if a file or key is
 * missing, a value is not what Kodak's readers take (integers within int16; the constraints finite), or the SFS file is
 * one Kodak rejects (pkc_sfs_table). */
pk_status pkc_sba_pref_load(const char *vendor_root, const char *derived_root, pkc_sba_pref *out);
/* The same from a given SBA dpi (a product row's: sba-CN-default-78-13.dpi, ...; every key above is required, as for the
 * default dpi -- every shipped CN dpi has them). */
pk_status pkc_sba_pref_read(const char *vendor_root, const char *derived_root, const char *dpi, pkc_sba_pref *out);

/* Makesfs on an SFS row file. The file is read as operator>>(istream&, AnsSfsTableDef&) does (0x102ac8c0): six rows of
 * four whitespace-separated shorts (hue start 1..120, radius 1..2000, hue end 1..120, floor weight 0..100; an all-zero
 * row ends the list), a stream error or end of file inside the 24 numbers fails ("Error reading file"). Then the row
 * check fcn.102b7280 (any non-zero code fails Kodak's dpi ctor: 0x10289836), the 120-entry hue table fcn.102ac590
 * (rows copied over their hue span, gaps blended with the sine table) and the 50x83 fill fcn.102ac430.
 * PK_E_ARG on NULLs; PK_E_VENDOR_DATA if a file is missing / unreadable / malformed, the rows fail Kodak's check, or a
 * cell would read a hue entry the rows never wrote (uninitialised stack in Kodak) or divide by a zero radius (#DE). */
pk_status pkc_sfs_table(const char *sfs_path, const char *derived_root, int8_t out[PKC_SFS_N]);
/* The same from rows already read (rows[k] = hue start, radius, hue end, floor) and the sine table. */
pk_status pkc_sfs_build(const int16_t rows[6][4], const int16_t sin_tab[31], int8_t out[PKC_SFS_N]);

/* What FUN_1028ae00 and its caller produce for one pass-2 scene. Every value is Kodak's (int16 words sign-extended). */
typedef struct {
    int32_t triple[3];     /* orderFpo Y / C1 / C2 = scene+0x38a2 words 0..2: (Yo + L, C1o + out4, C2o + out8) as words */
    int32_t out4, out8;    /* the U / V terms (FUN_1028ae00 out +4 / +8) */
    int32_t flag;          /* scene+0x38a2 word 0x2f: 0 (FOS lines) / 100 (slope-limit fallback) in mode 2, 200 mode 0,
                            * 0xcb without a weight table */
    int32_t count;         /* scene+0x16: samples with Y - Yo below the FOS dmin luma + par[19] - Yo (mode 2; 0 in mode 0) */
    int32_t s2;            /* scene+0x18: its weight 0..1000 (fcn.102b7440 tail) */
    int32_t nsel;          /* samples FUN_1028ae00 selected for the U / V means */
    int32_t u, v;          /* the weighted means (with the FOS line's offset l5c / l58 in mode 2) */
    int32_t p15[3];        /* arg14: (par[13] + L, C1o + l5c, C2o + l58) in mode 2, the opening axes in mode 0 */
} pkc_sba_triple_out;

/* The triple of a scene's pass 2. m / scene = the pass's pkc_sba_measure_scene output and the scene state it left
 * (bands, L; vector slots 3 = Ythr, 4 / 5 = the whole-frame C1 / C2 means; the mask). pass = PKC_SBA_FOS2 (Kodak mode 2:
 * fos = that instance's FOS results, valid) or PKC_SBA_SHORT2 (mode 0: fos unused, may be NULL). Kodak's measure image
 * holds the bands as int16 words: every band of m must fit int16 -- it does for grids in 0..4095 (|band| <= 7100); a
 * grid near R14's 0x7d00 limit would make Kodak wrap the word, which is not modelled.
 * Errors: PK_E_ARG on NULLs, a bad pass, mode 2 without valid FOS results, a band outside int16, and where Kodak would
 * divide by zero (a zero par[3] with a count above par[2]; no sample under par[9] = 0); PK_E_VENDOR_DATA if a vector slot
 * read (3, 4, 5) is not known[] (ruling R18) or the flag bytes select the alternative weight tables DAT_1069b080 /
 * DAT_1069c0b8 (mode 2 with flags[3] in 1..3 and flags[2] = 0, or = 1 with flags[4] = 1: not extracted, R12). A flag word
 * with 0x2000 set (no weight table, fcn.1028b8d0 0x1028bfcb) is modelled from the disassembly (no Kodak run sets it):
 * out4 / out8 = slots 4 / 5, flag 0xcb. Kodak-exact (lab/rollbal/truth/t13) on every call of the truth rolls; the
 * flag bytes / flag word are ctx constants on the default PSI path (R18). The caller must treat a FOS calc error as a
 * failed roll before getting here (Kodak never runs pass 2 then: observed, roll t15d). */
pk_status pkc_sba_triple(const pkc_sba_measure *m, const pkc_sba_scene *scene, const pkc_sba_ctx *ctx, const pkc_sba_pref *pref,
                         int pass, const pkc_fos_result *fos, pkc_sba_triple_out *out);

/* Preference (fcn.1028c780) on the triple's int16 words: shift = scene+0x3a38 (what getShifts returns), anchor =
 * scene+0x3a32 (may be NULL). mode = Kodak's Preference mode word, scene+0x5074, which analyzePass2 (fcn.102159c0,
 * 0x10215e8f..0x10216413) assembles per scene from the scene's "userColorBalance" / "userNeutralBalance" attributes
 * (strings 0x1059db4c / 0x1059db60: high nibble |0x10..0x40 at 0x102161a8..0x10216209 / 0x10216356, low nibble from
 * analyzePass2's byte argument and the neutral-balance attribute at 0x10216114 / 0x1021640e). On the default PSI path no
 * scene carries either attribute and the word is 0 on every Kodak call observed (every truth roll). Only mode 0 is
 * ported (the aim = the triple itself, 0x1028c983 / 0x1028ca2f); x87 at PC53 = C doubles in Kodak's operation order,
 * every store _ftol (truncation) to a word.
 * PK_E_ARG on NULL triple / pref / shift; PK_E_UNSUPPORTED when mode & 0xff != 0 (Kodak reads only the two low
 * nibbles; bits above are ignored as at Kodak). The other modes' aim arms (low nibble 1..4 and
 * high nibble 0x10..0x40 at 0x1028c92f..0x1028ca43, and the 0x18a4 guard are not ported). shift / anchor are not
 * written on error. */
pk_status pkc_preference_shift(const int32_t triple[3], const pkc_sba_pref *pref, int mode, int16_t shift[3], int16_t anchor[3]);

/* ColorNegativePath::setShifts with (ntdChoice, ctdChoice) = (1, 2) (the shipped SCPLut dpi; the caller checks
 * pkc_scplut_params): Y from the scpLut applied to 1550 - A (A = the sba instance's shift words), C1 / C2 from 1550 - B
 * (B = the afterSCPLut instance's), back to RGB and out = 1550 - RGB. Integer only.
 * Kodak indexes the scpLut as one flat table, base[ar], base[4096 + ag], base[8192 + ab], with the int16 words ar = 1550 - A
 * and no bounds check. An index off its band (A_c > 1550 or A_c < -2545: a Preference shift beyond the clamp-limited luma
 * with a strong chroma; no corpus roll reaches it) reads the neighbouring band, exactly as here (Kodak-pinned by pokes,
 * docs/re/26 section 4). A flat index outside the 3 x 4096 table reads Kodak's heap: PK_E_UNSUPPORTED (out not written).
 * PK_E_ARG on NULLs (out not written). */
pk_status pkc_setshifts_12(const int16_t A[3], const int16_t B[3], const pkc_lut3 *scplut, int16_t out[3]);
#endif
