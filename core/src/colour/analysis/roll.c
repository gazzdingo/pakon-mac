/* Kodak's roll orchestration on the default colour-negative path: roll.h, docs/re/24-roll-orchestration.md. */
#include <stdlib.h>
#include <string.h>
#include "analysis/roll.h"
#include "analysis/image.h"
#include "analysis/dmin.h"
#include "analysis/exposure.h"
#include "nra.h"
#include "data/kodak_map.h"
#include "data/kodak_text.h"

pk_status pkc_roll_cfg_load(const char *vendor_root, const char *derived_root, int product_code, int gen_code, pkc_roll_cfg *cfg) {
    if (!vendor_root || !derived_root || !cfg) return PK_E_ARG;
    memset(cfg, 0, sizeof *cfg);
    /* -1 / -1: no DX read (TLB's DX vote slots start at -1; AddScene then sets neither context key: RE 24 section 8) */
    const int none = product_code == PKC_DX_NONE && gen_code == PKC_DX_NONE;
    if (!none && (product_code < 0 || product_code > 32767)) return PK_E_ARG;
    if (!none && (gen_code < 0 || gen_code > 15)) return PK_E_UNSUPPORTED;
    cfg->product_code = product_code; cfg->gen_code = gen_code; cfg->dx_none = none;
    char map[1100], dir[1100], dpi[1200];
    int16_t (*iso)[16] = malloc(128 * sizeof *iso);
    if (!iso) return PK_E_NOMEM;
    pk_status st = pkc_film_iso_load(vendor_root, iso);
    if (!st && !none) cfg->film_iso = pkc_film_iso((const int16_t (*)[16])iso, product_code, gen_code);
    free(iso);
    if (st) return st;
    /* sba.map: scannerName and _AnselImageSize_ are `any` on every sourceType-1 row */
    const pkc_map_key keys[4] = { { "_AnselPath_", PKC_MAP_STR, "CN-Enhanced", 0 }, { "sourceType", PKC_MAP_INT, NULL, 1 },
                                  { "productCode", none ? PKC_MAP_ABSENT : PKC_MAP_INT, NULL, product_code },
                                  { "genCode", none ? PKC_MAP_ABSENT : PKC_MAP_INT, NULL, gen_code } };
    if ((st = pkc_vendor_path(vendor_root, "anselinstalldir/dataPathItems/sba/SbaDPI/sba.map", map, sizeof map)) ||
        (st = pkc_map_select(map, keys, 4, cfg->sba_key, sizeof cfg->sba_key)) ||
        (st = pkc_vendor_path(vendor_root, "anselinstalldir/dataPathItems/sba/SbaDPI", dir, sizeof dir)) ||
        (st = pkc_dpi_by_key(dir, cfg->sba_key, dpi, sizeof dpi)))
        return st;
    if ((st = pkc_sba_ctx_load_dpi(vendor_root, derived_root, dpi, &cfg->sba))) return st;
    if (!(st = pkc_fos_params_read(dpi, &cfg->fos)) &&
        !(st = pkc_scplut_params_load(vendor_root, &cfg->scp)) &&
        !(st = pkc_sba_pref_read(vendor_root, derived_root, dpi, &cfg->pref)) &&
        !(st = pkc_flesh_params_load(vendor_root, &cfg->flesh)) &&
        !(st = pkc_fugc_seed_film(vendor_root, product_code, gen_code, cfg->film_iso, cfg->seed, cfg->tdmin)) &&
        !(st = pkc_fugc_aim_load_film(vendor_root, product_code, gen_code, cfg->aim)) &&
        !(st = pkc_falloff_params_load(vendor_root, &cfg->falloff)) &&
        !(st = pkc_nra_prepare_film(vendor_root, cfg->film_iso, &cfg->nra))) {
        /* setShifts is ported for (ntdChoice, ctdChoice) = (1, 2) only, and pass B needs runSCPAfterLut */
        if (cfg->scp.ntd_choice != 1 || cfg->scp.ctd_choice != 2 || !cfg->scp.run_after_lut) st = PK_E_UNSUPPORTED;
    }
    if (st) pkc_roll_cfg_free(cfg);
    return st;
}

void pkc_roll_cfg_free(pkc_roll_cfg *cfg) {
    if (!cfg) return;
    pkc_sba_ctx_free(&cfg->sba);
    memset(cfg, 0, sizeof *cfg);
}

pk_status pkc_roll_scene_lut(const pkc_lut3 *scp, const int16_t total[3], const pkc_lut3 *fugc, pkc_lut3 *out) {
    if (!scp || !total || !fugc || !out) return PK_E_ARG;
    for (int c = 0; c < 3; c++)
        for (int i = 0; i < 4096; i++) {
            int j = scp->t[c][i] + total[c];
            out->t[c][i] = fugc->t[c][j < 0 ? 0 : j > 4095 ? 4095 : j];
        }
    return PK_OK;
}

/* the per-roll working state, one block per array */
typedef struct {
    pkc_planes *img;               /* analysis images (scpLut applied in place at step 4) */
    int32_t (*grid)[3][PKC_GRID_N];
    uint16_t (*sdmin)[3];          /* the instance's scene dmin (sba+0x3bc8) */
    uint16_t (*ctx)[3];            /* the scene context's "dmin" entry */
    pkc_sba_scene *st;             /* the instance's scene objects */
    pkc_sba_measure *m;
    uint8_t *oob;                  /* 1: the scene's grid read past the image (clamped, R41) */
    int clamp;                     /* 0: such a grid is PK_E_UNSUPPORTED; 1: clamp it */
    uint8_t *skip;                 /* 1: analysis image under 107 x 107 -- Kodak runs no SBA pass and no balance for it (RE 27) */
} work;

static void work_free(work *w, int n) {
    if (w->img) for (int k = 0; k < n; k++) pkc_analysis_image_free(&w->img[k]);
    free(w->img); free(w->grid); free(w->sdmin); free(w->ctx); free(w->st); free(w->m); free(w->skip); free(w->oob);
}

/* pass 1 of one SBA instance over every scene: grid of the scene's current image, scene dmin, context write-back, measure */
static pk_status pass1(const pkc_roll_cfg *cfg, int n, work *w) {
    for (int k = 0; k < n; k++) {
        if (w->skip[k]) {
            /* a scene below 107 x 107 never reaches createAlgData / the measure: its grid, scene dmin and sba object stay
             * zero (what FOS#1 is handed for it: observed, RE 27) */
            memset(w->grid[k], 0, sizeof w->grid[k]); memset(w->sdmin[k], 0, sizeof w->sdmin[k]);
            pkc_sba_scene_init(&w->st[k]);
            continue;
        }
        /* analyzePass1 first drops the image's splice columns (docs/re/19); the grid and the pass-1 measure see the
         * cropped copy, later passes the scene's own image (Kodak's crop is a local of analyzePass1) */
        pkc_planes crop;
        pkc_splice sp;
        pk_status st = pkc_splice_crop(&w->img[k], cfg->sba.opening[0] + cfg->sba.fog + 100, cfg->sba.splice_pct, &crop, &sp);
        if (st) return st;
        const pkc_planes *im = sp.cropped ? &crop : &w->img[k];
        int cl = 0;
        if (!(st = w->clamp ? pkc_grid24x36_clamped(im, w->grid[k], &cl) : pkc_grid24x36(im, w->grid[k]))) {
            if (cl) w->oob[k] = 1;
            pkc_scene_dmin(w->ctx[k], (const int32_t (*)[PKC_GRID_N])w->grid[k], w->sdmin[k]);
            if (!(st = pkc_ctx_dmin_pass1(w->ctx[k], w->sdmin[k]))) {
                pkc_sba_scene_init(&w->st[k]);
                st = pkc_sba_measure_scene(im, (const int32_t (*)[PKC_GRID_N])w->grid[k], w->sdmin[k], &cfg->sba,
                                           cfg->fos.fos_on ? PKC_SBA_PASS1 : PKC_SBA_SHORT2, &w->st[k], w->m);
            }
        }
        pkc_analysis_image_free(&crop);
        if (st) return st;
    }
    return PK_OK;
}

/* FOS over the instance's pass-1 state */
static pk_status fos(const pkc_roll_cfg *cfg, int n, work *w, int *n_fos, pkc_fos_result *f) {
    /* AnsFosCapabilityImpl::analyze reads sourceType, productCode and genCode from the scene context and returns before
     * the calculation when one is missing ("Can't find 'AnsContextProductCode'...", 0x102404ab / 0x1024057b): a roll
     * without a DX read has no FOS in either instance (truth t21 codes_m1: no SbaCalcFosResults call, Preference gets
     * no FOS results) */
    if (cfg->dx_none) { memset(f, 0, sizeof *f); *n_fos = 0; return PK_OK; }
    int m = n < cfg->fos.max_frames ? n : cfg->fos.max_frames;
    *n_fos = cfg->fos.fos_on && m >= cfg->fos.min_frames ? m : 0;   /* 0: FOS did not run (fewer than mff scenes, or fosOn 0) */
    return pkc_fos_roll(&cfg->sba, &cfg->fos, n, (const int32_t (*)[3][PKC_GRID_N])w->grid, (const uint16_t (*)[3])w->sdmin,
                        w->st, f);
}

/* pass 2 of one SBA instance, scene k: measure, context min with the FOS dmin, triple, Preference shift */
static pk_status pass2(const pkc_roll_cfg *cfg, work *w, int k, const pkc_fos_result *f, pkc_sba_triple_out *t,
                       int16_t shift[3]) {
    int kind = f->valid ? PKC_SBA_FOS2 : PKC_SBA_SHORT2;
    pk_status st = pkc_sba_measure_scene(&w->img[k], (const int32_t (*)[PKC_GRID_N])w->grid[k], w->sdmin[k], &cfg->sba,
                                         kind, &w->st[k], w->m);
    if (st) return st;
    if ((st = pkc_ctx_dmin_pass2(w->ctx[k], w->sdmin[k], f))) return st;
    if ((st = pkc_sba_triple(w->m, &w->st[k], &cfg->sba, &cfg->pref, kind, f->valid ? f : NULL, t))) return st;
    return pkc_preference_shift(t->triple, &cfg->pref, 0, shift, NULL);   /* mode word 0 on the default path */
}

static void fail_roll(const pkc_roll_cfg *cfg, int n, const uint8_t *skip, pkc_roll_scene *out) {
    for (int k = 0; k < n; k++) {
        memset(&out[k], 0, sizeof out[k]);
        if (skip[k]) {                                  /* no transform: identity whatever the roll did (RE 27) */
            out[k].skipped = 1;
            for (int c = 0; c < 3; c++) for (int i = 0; i < 4096; i++) out[k].lut_s.t[c][i] = (int16_t)i;
            continue;
        }
        out[k].failed = 1;
        out[k].exposure = 0.0;
        out[k].falloff = pkc_falloff_enabled(&cfg->falloff, 0.0);
    }
}

static pk_status analyse(const pkc_roll_cfg *cfg, int n, const pkc_roll_frame *frames, const uint16_t (*addscene_dmin)[3],
                         pkc_roll_scene *out, pkc_roll_info *info, int clamp) {
    if (!cfg || !frames || !addscene_dmin || !out || n < 1 || n > PKC_ROLL_MAX) return PK_E_ARG;
    for (int k = 0; k < n; k++) {
        const pkc_roll_frame *f = &frames[k];
        if (!f->p[0] || !f->p[1] || !f->p[2] || f->w < 1 || f->h < 1) return PK_E_ARG;
        size_t np = (size_t)f->w * f->h;
        for (int c = 0; c < 3; c++)
            for (size_t i = 0; i < np; i++)
                if (f->p[c][i] > 4095) return PK_E_ARG;
    }
    pkc_roll_info local, *I = info ? info : &local;
    memset(I, 0, sizeof *I);
    work w; memset(&w, 0, sizeof w);
    pkc_sba_triple_out *ta = malloc((size_t)n * sizeof *ta), *tb = malloc((size_t)n * sizeof *tb);
    pkc_lut3 *fl = malloc(sizeof *fl);
    w.img = calloc((size_t)n, sizeof *w.img); w.grid = malloc((size_t)n * sizeof *w.grid);
    w.sdmin = malloc((size_t)n * sizeof *w.sdmin); w.ctx = malloc((size_t)n * sizeof *w.ctx);
    w.st = malloc((size_t)n * sizeof *w.st); w.m = malloc(sizeof *w.m); w.skip = calloc((size_t)n, 1); w.oob = calloc((size_t)n, 1); w.clamp = clamp;
    pk_status st = PK_E_NOMEM;
    if (!ta || !tb || !fl || !w.img || !w.grid || !w.sdmin || !w.ctx || !w.st || !w.m || !w.skip || !w.oob) goto done;

    /* AddScene: the analysis image (RE 19) and the context dmin entry */
    for (int k = 0; k < n; k++) {
        const uint16_t *pl[3] = { frames[k].p[0], frames[k].p[1], frames[k].p[2] };
        if ((st = pkc_analysis_image(pl, frames[k].w, frames[k].h, &w.img[k]))) goto done;
        w.skip[k] = w.img[k].w < PKC_ROLL_MIN_AIMG || w.img[k].h < PKC_ROLL_MIN_AIMG;
        memcpy(w.ctx[k], addscene_dmin[k], sizeof w.ctx[k]);
    }
    /* 1-3: the sba instance */
    if ((st = pass1(cfg, n, &w))) goto done;
    if (cfg->inject_fail == 1) { I->failed = 1; fail_roll(cfg, n, w.skip, out); st = PK_OK; goto done; }
    if ((st = fos(cfg, n, &w, &I->n_fos, &I->fos1))) goto done;
    if (cfg->inject_fail == 2) I->fos1.calc_err = 0x18a5;      /* the poked n = 0 of truth err_fos1 */
    if (I->fos1.calc_err) { I->failed = 1; fail_roll(cfg, n, w.skip, out); st = PK_OK; goto done; }
    for (int k = 0; k < n; k++) {
        memset(&out[k], 0, sizeof out[k]);
        if (w.skip[k]) continue;
        if ((st = pass2(cfg, &w, k, &I->fos1, &ta[k], out[k].shift_a))) goto done;
        if (cfg->inject_fail == 3 && k == 0) { I->failed = 1; fail_roll(cfg, n, w.skip, out); st = PK_OK; goto done; }
        /* only the sba instance's pass-2 triple feeds the exposure (getSbaExposure, RE 23) */
        if ((st = pkc_sba_exposure_stops(&ta[k], &cfg->sba, &out[k].exposure))) goto done;
        for (int c = 0; c < 3; c++) out[k].triple_a[c] = ta[k].triple[c];
    }
    /* 4: the scpLut balance */
    if ((st = pkc_scplut_build(&cfg->scp, &I->fos1, &I->scplut, NULL))) goto done;
    for (int k = 0; k < n; k++) {
        if (w.skip[k]) continue;
        if ((st = pkc_ctx_dmin_remap(w.ctx[k], &cfg->scp, &I->scplut))) goto done;
        if ((st = pkc_scplut_apply(&I->scplut, &w.img[k], &w.img[k]))) goto done;
    }
    /* 5-7: the afterSCPLut instance on the scpLut images */
    if ((st = pass1(cfg, n, &w))) goto done;
    if (cfg->inject_fail == 4) { I->failed = 1; fail_roll(cfg, n, w.skip, out); st = PK_OK; goto done; }
    int n2;
    if ((st = fos(cfg, n, &w, &n2, &I->fos2))) goto done;
    if (cfg->inject_fail == 5) I->fos2.calc_err = 0x18a5;      /* the poked n = 0 of truth err_fos2 */
    if (I->fos2.calc_err) { I->failed = 1; fail_roll(cfg, n, w.skip, out); st = PK_OK; goto done; }
    for (int k = 0; k < n; k++) {
        if (w.skip[k]) continue;
        if ((st = pass2(cfg, &w, k, &I->fos2, &tb[k], out[k].shift_b))) goto done;
        if (cfg->inject_fail == 6 && k == 0) { I->failed = 1; fail_roll(cfg, n, w.skip, out); st = PK_OK; goto done; }
        for (int c = 0; c < 3; c++) out[k].triple_b[c] = tb[k].triple[c];
    }
    /* 8-9: per scene */
    for (int k = 0; k < n; k++) {
        pkc_roll_scene *s = &out[k];
        if (w.skip[k]) {                                   /* no transform at all: identity, no falloff (observed, RE 27) */
            s->skipped = 1;
            for (int c = 0; c < 3; c++) for (int i = 0; i < 4096; i++) s->lut_s.t[c][i] = (int16_t)i;
            continue;
        }
        if ((st = pkc_setshifts_12(s->shift_a, s->shift_b, &I->scplut, s->preflesh))) goto done;
        if ((st = pkc_flesh_delta(&cfg->flesh, &w.img[k], s->preflesh, (float)s->exposure, s->total, NULL))) goto done;
        if ((st = pkc_fugc_dmin_prime(w.ctx[k], cfg->aim, s->dmin_prime))) goto done;
        if ((st = pkc_fugc_lut((const int16_t (*)[PKC_FUGC_N])cfg->seed, s->dmin_prime, cfg->tdmin, s->total, fl))) goto done;
        if ((st = pkc_roll_scene_lut(&I->scplut, s->total, fl, &s->lut_s))) goto done;
        s->falloff = pkc_falloff_enabled(&cfg->falloff, s->exposure);
    }
    st = PK_OK;
done:
    if (st == PK_OK) for (int k = 0; k < n; k++) out[k].oob = w.oob[k];
    work_free(&w, n);
    free(ta); free(tb); free(fl);
    return st;
}

pk_status pkc_roll_analyse(const pkc_roll_cfg *cfg, int n, const pkc_roll_frame *frames, const uint16_t (*addscene_dmin)[3],
                           pkc_roll_scene *out, pkc_roll_info *info) {
    return analyse(cfg, n, frames, addscene_dmin, out, info, 0);
}

pk_status pkc_roll_batches(const pkc_roll_cfg *cfg, int n, const pkc_roll_frame *frames, const uint16_t addscene_dmin[3],
                           pkc_roll_scene *out) {
    if (!cfg || !frames || !addscene_dmin || !out || n < 1) return PK_E_ARG;
    uint16_t d[PKC_ROLL_BATCH][3];
    for (int k = 0; k < PKC_ROLL_BATCH; k++) memcpy(d[k], addscene_dmin, sizeof d[k]);
    for (int b = 0; b < n; b += PKC_ROLL_BATCH) {
        int m = n - b < PKC_ROLL_BATCH ? n - b : PKC_ROLL_BATCH;
        pkc_roll_info info;
        pk_status st = analyse(cfg, m, frames + b, (const uint16_t (*)[3])d, out + b, &info, 1);
        if (st == PK_E_NOMEM) return st;
        if (!st) {
            /* R41: a scene whose grid read past its image is refused; its batch's statistics used the clamped grid, so
             * every other scene of the batch is rendered but not Kodak-exact. Two scenes stay exact (R42): a skipped scene
             * (its output is the identity whatever the batch holds), and, when no cross-frame statistic exists, every
             * scene. Cross-frame coupling is FOS only (roll.c fos() -> fos.c pkc_fos_roll, the only reader of more than
             * one scene's grid; everything else in analyse() is per scene: pass1/pass2/scplut_apply/dmin_remap use
             * w.grid[k], w.sdmin[k], w.ctx[k] of scene k alone, w.m is a per-call scratch) plus a roll failure, which
             * fails every scene. So with n_fos == 0 (no DX codes, fosOn 0, or fewer than mff scenes: fos.c:98-102, roll.c
             * fos()) and no failure, the odd scene's clamped grid reaches no other scene. */
            const int coupled = info.n_fos > 0 || info.failed;
            int any = 0;
            for (int j = 0; j < m; j++) any |= out[b + j].oob;
            for (int j = 0; j < m && any; j++) {
                const int odd = out[b + j].oob;
                if (odd) memset(&out[b + j], 0, sizeof out[b + j]);
                out[b + j].inexact = !out[b + j].skipped && coupled;
                if (odd) out[b + j].status = PK_E_UNSUPPORTED;
            }
        }
        if (st) {                                  /* the port refuses this batch: its frames carry the status (RE 27) */
            for (int j = 0; j < m; j++) { memset(&out[b + j], 0, sizeof out[b + j]); out[b + j].status = st; }
        }
    }
    return PK_OK;
}

