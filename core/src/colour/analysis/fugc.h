#ifndef PAKON_COLOUR_ANALYSIS_FUGC_H
#define PAKON_COLOUR_ANALYSIS_FUGC_H
#include <stdint.h>
#include "internal.h"
#include "analysis/fos.h"
#include "analysis/scplut.h"

/* FUGC, the per-scene tone LUT: AnsFugcCapabilityImpl::analyze (0x101fc370) and its LUT build setLutInfo (0x101f82c0),
 * called by ColorNegativePath::analyzeFugc (0x100fed00) with the scene's shift triple (scene+0x4b6, the total shift =
 * pre-flesh + flesh delta) and its dmin copy (scene+0x3c, refreshed from the scene context's "dmin" entry). docs/re/22.
 * Kodak's Impl runs the LUT build (mode 1) on every observed hit: Impl+0xc = 1, the dpi's "mode" key is skipped by
 * AnsFugcParamsDpi::readAscii (0x101fd8f0), and the histogram mode 2 (0x101fc7e6..) is not ported. */

#define PKC_FUGC_N 4096   /* the LUT size, the global [0x10589834] (4096 on every hit) */

/* The seed table and aTableDmin, as Kodak selects and reads them. Kodak's constructor (0x101fb340) looks the film up in
 * fugc-rgb-lutMap.map (the RGB map, 0x101fb1bf; mode 2 would take the neutral map, a missing RGB map fugc-lutMap.map)
 * by (productCode, genCode), (productCode, X), the ISO map, then (X, X), each an exact key lookup (0x101fbf03..
 * 0x101fc2d8); the shipped map has one active film row, `X X X 2.25`, and every DX/ISO row is commented out, so any
 * film resolves to it. This port, which has no DX/ISO, takes the first all-wildcard film row; the first
 * `contrast = <c> <lut key>` row with that contrast (compared as float) names the .lut.
 * Kodak resolves the .lut through its Ansel cache by the `key` inside each file; this port opens the file named by
 * the map's lut column and requires its `key` to equal that name (true of every shipped fugc file).
 * AnsFugcLutDpi::readAscii (0x101f7180..0x101f75fc):
 *   - lines starting with '#', '*', CR, LF or NUL are skipped; before the first table row, `key`, `version` and
 *     `aTableDmin = a b c` (%hd, all three required) are header entries;
 *   - a table row is 4 numbers (index R G B) or 2 (index V: R = G = B = V); each is trunc(x + 0.5) kept as an int16 word,
 *     and the index must equal the row count;
 *   - after the last row each channel continues by +1 per entry (0x101f754b: the shipped table has rows 0..3200 with
 *     3199 last, so seed[i] = i - 1 above 3200 -- the reference loader's identity there was RE 18's one-code residue);
 *   - every entry is then clamped to 0..4095 (0x101f758a..).
 * Equal to Kodak's Impl+0xe6 / +0xe0 on every truth hit (lab/rollbal/truth/t17, including an edited .lut).
 * PK_E_ARG on NULLs; PK_E_NOMEM; PK_E_VENDOR_DATA if a file, the wildcard film row or the contrast row is missing, the
 * .lut's key differs from its file name, there is no row or more than 4096 rows (Kodak writes past its table), or a
 * header or row breaks the rules above. This port is stricter than Kodak's reader in these cases, which Kodak reads
 * on (none occurs in the shipped files):
 *   - a line longer than 255 characters: Kodak's getline(buf, 0x100) sets failbit, readAscii clears it and goes on, so
 *     the first 255 characters are dropped and the rest is read as the next line; rejected here;
 *   - a row with 5 or more numbers or trailing junk ("%lf %lf %lf %lf" returns 4: a 4-value row), or with junk after
 *     two numbers ("0 1 abc": a 2-value row); rejected here, as is any token kodak_text's grammar refuses (hex, inf,
 *     "12abc");
 *   - aTableDmin values outside int16 (%hd truncates 40000) or not integers; rejected here. */
pk_status pkc_fugc_seed(const char *vendor_root, int16_t seed[3][PKC_FUGC_N], int16_t aTableDmin[3]);
/* The same for a film: the map's film rows are looked up in the constructor's order -- (productCode, genCode, X),
 * (productCode, X, X), (X, X, filmIso), (X, X, X), exact token matches, the first that exists wins (RE 22 section 4).
 * The shipped map has only the (X, X, X) row, so every film lands on it (Kodak-run: truth t19 runs_codes). A hit on any
 * other row (an edited map) is PK_E_UNSUPPORTED: those key forms come from the disassembly, never from a Kodak run.
 * pkc_fugc_seed is this with codes 0 / 0 and ISO 0. */
pk_status pkc_fugc_seed_film(const char *vendor_root, int product_code, int gen_code, int film_iso,
                             int16_t seed[3][PKC_FUGC_N], int16_t aTableDmin[3]);

/* aFilmAimDmin from fugc/fugc-defaultParams.dpi (AnsFugcParamsDpi::readAscii 0x101fd993, %hd x 3; Impl+0x12; shipped
 * 500 1000 1000). Kodak picks the params dpi by key, `fugc-<productCode>-<genCode>.dpi` and else
 * `fugc-default-default.dpi` (the key of fugc-defaultParams.dpi; no product dpi is shipped); this port opens the
 * file by name and does not check its key. Stricter than Kodak like pkc_fugc_seed's aTableDmin. PK_E_ARG on NULLs, PK_E_NOMEM, PK_E_VENDOR_DATA if the file or key is missing or a value is not an
 * integer in int16 range. */
pk_status pkc_fugc_aim_load(const char *vendor_root, int16_t aim[3]);
/* The same for a film: a params dpi whose key is fugc-<productCode>-<genCode>.dpi would be Kodak's choice; none is shipped,
 * and one in an edited tree is PK_E_UNSUPPORTED (not Kodak-run). */
pk_status pkc_fugc_aim_load_film(const char *vendor_root, int product_code, int gen_code, int16_t aim[3]);

/* The scene context's "dmin" entry, which FUGC reads, through the analysis (docs/re/22 section 2). Each SBA instance
 * (sba, then afterSCPLutSba) reads it in pass 1 and writes it back in passes 1 and 2; the scpLut balance remaps it in
 * between. Kodak runs the roll phase by phase, and the caller must keep that order (each phase over every scene
 * before the next; the entry is per scene):
 *   1. sba pass 1, every scene: scene = pkc_scene_dmin(ctx, grid); pkc_ctx_dmin_pass1(ctx, scene)  (ctx starts as the
 *      AddScene dmin)
 *   2. FOS#1 over the roll (pkc_fos_roll; reads every scene's pass-1 dmin)
 *   3. sba pass 2, every scene: pkc_ctx_dmin_pass2(ctx, scene, &fos1)
 *   4. scpLut balance (the roll scpLut from FOS#1, pkc_scplut_build), every scene: pkc_ctx_dmin_remap(ctx, &params,
 *      &scplut), and the scpLut applied to the scene's image
 *   5. afterSCPLut pass 1, every scene, on the scpLut image's grid: scene2 = pkc_scene_dmin(ctx, grid2);
 *      pkc_ctx_dmin_pass1(ctx, scene2)
 *   6. FOS#2 over the roll, then afterSCPLut pass 2, every scene: pkc_ctx_dmin_pass2(ctx, scene2, &fos2)
 *   7. per scene, after its shifts and flesh: pkc_fugc_dmin_prime(ctx, aim, dp); pkc_fugc_lut(seed, dp, aTableDmin,
 *      total shift, &lut).
 * With fewer than mff scenes there is no FOS (pass 2 changes nothing) and the scpLut is the identity. Words are Kodak's int16 (held here as uint16_t like pkc_scene_dmin's, compared as int16 where Kodak does).
 *
 * After pass 1 (analyzePass1 0x1021904b..0x102190d8): ctx = the entry the pass read (for the sba instance the AddScene
 * dmin), scene = pkc_scene_dmin(ctx, grid). Kodak writes scene back only if some channel took the grid minimum, i.e.
 * scene_c < d_c with d_c = 4095 if (int16)ctx_c <= limit_c else ctx_c; replacing a channel by 4095 alone is not a
 * change, so a channel <= its limit with no grid cell above it keeps the context value (crafted rolls t17a..e). */
pk_status pkc_ctx_dmin_pass1(uint16_t ctx[3], const uint16_t scene[3]);

/* After pass 2 (0x10215e9b..0x10215f5e), only when the pass has FOS results (fos != NULL and fos->valid; otherwise
 * nothing changes, 0x10215ffa): for each channel with (int16)fos->dmin_c <= (int16)scene_c the scene dmin (sba+0x3bc8,
 * scene[] here, updated in place) takes the FOS dmin; if any channel did, the whole scene triple is written to ctx. */
pk_status pkc_ctx_dmin_pass2(uint16_t ctx[3], uint16_t scene[3], const pkc_fos_result *fos);

/* The scpLut balance's remap (analyzeScpLutBalance 0x100fd984..0x100fd9b3, then the entry write 0x100fda7e), only when
 * the SCPLut dpi's modifyDmin is set: ctx_c = scp->t[c][(int16)ctx_c]. Kodak indexes with the movsx word unchecked;
 * the index is clamped to 0..4095 here (never out of range for 12-bit dmins). PK_E_ARG on NULLs. */
pk_status pkc_ctx_dmin_remap(uint16_t ctx[3], const pkc_scplut_params *p, const pkc_lut3 *scp);

/* FUGC's dmin' (Impl+0x60ec, 0x101fc3c4..0x101fc4bf): ctx = the context dmin when FUGC runs (after the afterSCPLut
 * instance's pass 2), aim = aFilmAimDmin. If every channel has 0.2 * aim_c <= ctx_c <= 2 * aim_c (x87 at PC53: the
 * product is rounded to double, so 100 is inside for aim 500), out = ctx, else out = aim for all three channels
 * (R is checked first; any failure falls back). PK_E_ARG on NULLs. */
pk_status pkc_fugc_dmin_prime(const uint16_t ctx[3], const int16_t aim[3], int16_t out[3]);

/* The FUGC LUT (setLutInfo 0x101f82c0, Impl+0x6140), per channel with O = int16(dmin'_c - aTableDmin_c + shift_c)
 * (16-bit word arithmetic, so the sum wraps):
 *   O > 4095:   L[i] = i;
 *   otherwise:  L[i] = O for i < O (O > 0 only); L[i] = clamp(int16(seed[i - O] + O), 0, 4095) for max(O, 0) <= i <
 *               min(O + 4096, 4096); L[i] = i above that (O < 0: the top -O entries; O <= -4096: the whole channel).
 * PK_E_ARG on NULLs. */
pk_status pkc_fugc_lut(const int16_t seed[3][PKC_FUGC_N], const int16_t dmin_prime[3], const int16_t aTableDmin[3],
                       const int16_t shift[3], pkc_lut3 *out);
#endif
