#ifndef PAKON_COLOUR_ANALYSIS_SBA_MEASURE_H
#define PAKON_COLOUR_ANALYSIS_SBA_MEASURE_H
#include <stdint.h>
#include "internal.h"
#include "analysis/image.h"
#include "analysis/sba_vm.h"

/* The SBA scene-balance measuring pass: fcn.102aece0 (statistics + selection mask), its packer fcn.102b7440, the
 * fcn.1028b8d0 vector tail, and the p-code VM that turns the 733-slot vector into the L term
 * (lab/reference pakon_sba_measure.py, pakon_orderfpo_vecpack.py, pakon_vm.py). */
#define PKC_SBA_VEC_N 733              /* slots 0..719 fcn.102b7440, 720..732 fcn.1028b8d0's own stores */

typedef struct {
    uint8_t params[PKC_SBA_STRUCT_SIZE];   /* stage-1 struct of pcode-<dpi pcode>: tables (en) at 0/0x2c/0x84/0xb0, par at 0xdc */
    pkc_sba_prog prog;                     /* stage-2 record table */
    int16_t opening[3];                    /* dpi `fpo`: the roll opening RGB density (879 1250 1386) */
    int16_t pcwf, ix_pcwf, non_flash_adj;  /* dpi pcwf / ix_pcwf / nonFlashAdj (70 25 25): vector slots 720 / 726 / 727 are 10x these */
    int16_t fog, splice_pct;               /* dpi fog / splicePct (1000 55; sba+0x4d1e / +0x4d30): analyzePass1's splice crop */
    /* fcn.1028b8d0 inputs that are NOT in the .dpi or the pcode: the SBA object's flag bytes (arg3 = sba+0x388c) and
     * its flag word (arg5 = sba+0x38a0). R16 traced both: the ctor (0x10217d00) writes exactly FE FE FE FF FF FE 00 FE
     * and 0 unless the scene carries an "aid" context (fcn.101a33b0 -> 0x10217f4d returned 0 on all 4 rolls) /
     * "orientation" (analyzePass1 0x10218892 overwrites flags[1]; absent on all 4 rolls) / "strangeLight" / "lighting"
     * (flag word bits 0x2000 / 0x800 / 0x1000). Kodak-observed at PC53 on r1/r4/r12/r2 (lab/rollbal/truth/t12), asserted
     * by lab/vectors/gen_sba_truth.py. A scene with those contexts would need them passed in (not yet modelled). */
    uint8_t flags[8];
    uint16_t flagsword;
    /* derived from flags at load (fcn.1028b8d0 0x1028bc..); pass 1 overrides mode and the gate table, see pkc_sba_pass */
    int mode;                              /* 1, 2, 4 or 8: which par quad / table the pass uses; 1 for the CN default */
    int sel;                               /* arg3 of fcn.102aece0 = (int16)(int8)flags[1]; 0xFFFE selects the default arm */
    int en_off;                            /* offset of the 64-byte gate table inside params[] (0, 0x2c, 0x84 or 0xb0) */
    uint8_t en_static[64];                 /* DAT_1069d0f0: pass 1's gate table (zero-padded past its 0x2c bytes) */
    /* PakonIMAu.dll tables (vendor/derived/imau_tables) */
    uint8_t sel_byte[5][PKC_GRID_N];       /* 105a8e10 105a94d0 105a9170 105a9830 105a9b90 */
    uint32_t sel_dword[4][PKC_GRID_N];     /* 1069e5a0 106a00a0 1069f320 106a0e20 */
    uint32_t hue_wb_global;                /* 106bc820: 0 in the shipped build, which kills the white-balanced hue arm */
} pkc_sba_ctx;


/* The SBA dpi of the default path's sba.map row (`any any 1 any any any ansel-sba-CN-default`); the scene's own row is
 * picked by pkc_roll_select (docs/re/24 section 8). */
#define PKC_SBA_DPI_DEFAULT "anselinstalldir/dataPathItems/sba/SbaDPI/sba-CN-default.dpi"

/* Load sba/SbaDPI/sba-CN-default.dpi (-> fpo, pcode name), sba/Pcode/<pcode> and the six imau_tables bins.
 *   vendor_root  = ".../F-X35 COM SERVER" (contains anselinstalldir/);  derived_root = ".../vendor/derived".
 * PK_E_VENDOR_DATA: a file is missing/unreadable/malformed; PK_E_ARG on NULLs. On failure *out is freed. */
pk_status pkc_sba_ctx_load(const char *vendor_root, const char *derived_root, pkc_sba_ctx *out);
/* The same from a given SBA dpi file (a product row's: sba-CN-default-78-13.dpi, ...). */
pk_status pkc_sba_ctx_load_dpi(const char *vendor_root, const char *derived_root, const char *dpi, pkc_sba_ctx *out);
void pkc_sba_ctx_free(pkc_sba_ctx *ctx);

/* Replace the SBA object's flag bytes / flag word (a scene carrying the "aid" / "orientation" / "strangeLight" /
 * "lighting" contexts) and re-derive mode, sel and the gate table (fcn.1028b8d0 0x1028bc..). PK_E_ARG on NULLs and when
 * both 0x800 and 0x1000 are set in the flag word (Kodak 0x189c at 0x1028baf1); PK_E_VENDOR_DATA when the flags reach
 * the branch where Kodak reads an uninitialised local. On failure the ctx is unchanged. */
pk_status pkc_sba_ctx_set_flags(pkc_sba_ctx *ctx, const uint8_t flags[8], uint16_t flagsword);

typedef struct {
    int32_t Yband[PKC_GRID_N], C1band[PKC_GRID_N], C2band[PKC_GRID_N];   /* measure image bands 3-5 (Y, C1, C2) */
    uint8_t mask[PKC_GRID_N];              /* the selection mask (obj+0xc20): 0, 1, or 2 (hue window) */
    int32_t lvec[8];                       /* vector slots 0..7: [3] = Ythr, [4] = obj+0x4c, [5] = obj+0x50 */
    int32_t L;                             /* the p-code L term: orderFpo.Y = opening Y + L */
    int32_t ythr;                          /* == lvec[3], the mean of the Y band minus the opening Y */
} pkc_sba_measure;

/* Kodak's fcn.1028b8d0 arg4 (R17): which of the scene's passes this is. Each is modelled from the disassembly:
 *  PASS1  = 1 (call 0x102196a9, analyzePass1). fcn.102aece0 arg5 = 1: the gate table is the static DAT_1069d0f0 and
 *           the par quad / mode is 1 (0x1028bc..), mask stage 1 runs and stage 2 (hue window) is skipped, the
 *           packer takes its mode-1 arm (slots 476..505, 506..509, 544..577 and 612 only, no 616..719). The function
 *           returns right after the measure (0x1028bdbc..): NO p-code VM, no vector tail, out->L = 0, out->ythr =
 *           vec[3]. Its job is to leave the scene's mask and vector (slot 479) for the next pass.
 *  FOS2   = 2 (call 0x10215fae, analyzePass2 of a >= 4-frame roll). arg5 = 2: mask stage 1 is SKIPPED (0x102b09ed) and
 *           the scene's previous mask is kept; stage 2 reads the previous mask and slot 479 left by pass 1.
 *  SHORT2 = 0 (call 0x1021605b, analyzePass2 of a < 4-frame roll). arg5 = 0: both mask stages run.
 * Passes 2 use the pcode table / mode picked by the flag bytes (mode 1, gate table 0 for the CN default). */
typedef enum { PKC_SBA_SHORT2 = 0, PKC_SBA_PASS1 = 1, PKC_SBA_FOS2 = 2 } pkc_sba_pass;

/* The per-scene state Kodak's scene object (sba+0x290c) carries from one pass to the next: the vector at +0x3c
 * (slot 479 = +0x7b8 is what the mask's hue window reads) and the mask at +0xc20. Initialise with
 * pkc_sba_scene_init (Kodak: a zeroed object -- slot 479 and the mask are 0 on entry to pass 1, observed) and pass
 * the same struct to the scene's passes in Kodak's order (PASS1, then FOS2 or SHORT2).
 * known[i] = 1 where vec[i] is Kodak-exact. 0 where the port does not claim it: the packer copies A6 rows and scalars the
 * port never fills (row +0x48 of every bank, the bank scalars, the whole-frame banks other than the one the L term reads
 * plus the three single cells A6+0x834 / 0x8AC / 0x9CC it does fill, the A3/A4/A5 entries other than 7/2/1, banks whose
 * gate byte is 0 -- uninitialised stack in Kodak) and Kodak's object holds non-zero there (~80 of the 720 slots per
 * pass-2 object; Kodak-observed). vec[i] is 0 (or a stale value) for those. The L p-code VM receives known[] and
 * returns PK_E_UNSUPPORTED when an unknown slot's value reaches L, a branch condition (opcodes 54 / 55), a loop count
 * (27-30) or a divisor (R18 taint rule: reading an unknown slot is not an error by itself; a division whose divisor is
 * tainted is refused even when the port's value is non-zero, R40 M2). On the real scenes L reads 17 unknown slots (616, 624,
 * 636, 637, 639, 641, 643, 671, 672, 673, 691, 692, 694, 695, 696, 697, 709; the port holds 0 there) and none of them reaches L,
 * a branch, a loop count or a divisor, so L is Kodak-exact on every truth scene (40). Mask-2 (hue-window) samples are modelled in the
 * whole-frame sums that feed slots 614 and 719 (Kodak 0x102b11ba..), exact on the crafted truth rolls.
 * Slots 0..732 not written by a pass keep their previous value and flag. */
typedef struct {
    int32_t vec[PKC_SBA_VEC_N];
    uint8_t known[PKC_SBA_VEC_N];
    uint8_t mask[PKC_GRID_N];
} pkc_sba_scene;
void pkc_sba_scene_init(pkc_sba_scene *s);

/* Slots 720..732 (fcn.1028b8d0's own stores) for the given mode, all marked known. Exposed for the flag-row test, which checks
 * them on the rows where the L program refuses the scene (PK_E_UNSUPPORTED) and so never reaches *scene. */
void pkc_vec_tail(const pkc_sba_ctx *c, int mode, int32_t *vec, uint8_t *known);

/* One pass of one scene: the 24x36 RGB grid (Task 10) through fcn.102aece0 (+ the packer, and for passes 2 the VM).
 * aimg and dmin are the caller's analysis image and scene dmin; neither is read (bands 0-2 are the grid, the opening
 * is the dpi's fpo); both may be NULL. scene is read and, on PK_OK only, updated; out receives the pass's result
 * (bands, mask, lvec = scene->vec[0..7], L, ythr). Errors: PK_E_ARG on NULLs / a bad pass kind, on a division by
 * zero Kodak would fault on, and on a VM error exit (Kodak 0x18a9); PK_E_VENDOR_DATA if the white-balanced hue arm
 * would run (hue_wb_global != 0: dead in the shipped DLL). Not modelled: fcn.1028b8d0's range checks (0x18bd,
 * 0x189c) and the FOS-pointer arms of fcn.102aece0 (the dmin-luma count and its weight: sba_pref.c). */
pk_status pkc_sba_measure_scene(const pkc_planes *aimg, const int32_t grid[3][PKC_GRID_N], const uint16_t dmin[3],
                                const pkc_sba_ctx *ctx, int pass, pkc_sba_scene *scene, pkc_sba_measure *out);

/* SbaCalcFosResults opening / the 1/sqrt3, 1/sqrt6, 1/sqrt2 basis (fcn.1028f608; same arithmetic fcn.1028b8d0 uses at
 * its top): (r,g,b) read as int16 -> (Y, C1, C2). */
void pkc_sba_axes(int r, int g, int b, int32_t *y, int32_t *c1, int32_t *c2);
#endif
