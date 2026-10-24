/* core_frame_kodak: the frame detection pass (pkf_detect) and the full sequence (strip-end passes, aggressive flag, blind placement, framing warnings;
 * pk_frame_strip_profile, pkf_frame_strip with 3 and 4 planes) against Kodak's TLB.dll FUN_100079c0 / FUN_100072c0 run under Unicorn (RE 31,
 * lab/vectors/gen_frame.py -> frame.pkv). Frame count and every rectangle field equal UC's, for all strips. */
#include "greatest.h"
#include <stdio.h>
#include <stdlib.h>
#include "pkv.h"
#include <string.h>
#include "pakon/framing.h"
#include "framing/frame.h"
#include "boards/dx_internal.h"
static pkv_file *V, *V_ends;
static const char *S[] = { "r4","r2","r201900","r121838","r172139","g400","rollbin","stripcal","one_frame","frames36","blank","leader_only","short","half_gap_dx","half_gap_veto" };
#define K(sfx) (snprintf(k, sizeof k, "%s." sfx, name), k)
TEST strip_case(const char *name) {
    char k[96]; const pkv_array *P = pkv_get(V, K("profile")), *R = pkv_get(V, K("rects")), *D = pkv_get(V, K("dx_rows")), *PA = pkv_get(V, K("params")), *SW = pkv_get(V, K("scanw0"));
    ASSERT(P && R && PA && SW);                             /* dx_rows is absent when a strip has none */
    const int32_t *pa = PA->data; int rows = P->dims[0];
    pk_frame_params fp = { pa[1], pa[2], pa[0], pa[3] != 0, D ? D->data : NULL, pa[4] };
    pkf_film film = { 0, false, pa[5] != 0 };               /* half_gap_veto is the 24 mm path, where the veto runs */
    if (!strcmp(name, "half_gap_dx")) {                     /* TLB's line -> lo-res row conversion (C26): 0 rows in TLB's configuration */
        const pkv_array *X = pkv_get(V, K("dx_events")); ASSERT(X && X->dims[0] <= 64);
        pkb_dx_event ev[64]; int got[64]; memset(ev, 0, sizeof ev);
        for (int i = 0; i < X->dims[0]; i++) { const int32_t *x = (const int32_t *)X->data + 3 * i; ev[i].type = x[0]; ev[i].rollover = x[1]; ev[i].line = x[2]; }
        ASSERT_EQ(D ? (int)D->dims[0] : 0, pkf_dx_rows(ev, (size_t)X->dims[0], fp.ratio, got, 64));
        if (D) ASSERT_MEM_EQ(D->data, got, (size_t)D->dims[0] * 4);
    }
    pk_framing *f; ASSERT_EQ(PK_OK, pkf_detect_ex(P->data, rows, &fp, &film, &f));
    ASSERT_EQ(R->dims[0], f->n);
    ASSERT_EQ(((const int32_t *)SW->data)[0], (int)f->scanw);
    /* S-R19: exactly the strips whose first run search finds nothing (reviewer's split) are flagged */
    ASSERT_EQ(!strcmp(name, "blank") || !strcmp(name, "leader_only") || !strcmp(name, "r121838"), (int)f->not_kodak_exact);
    for (int i = 0; i < f->n; i++) {
        const int32_t *e = (const int32_t *)R->data + 6 * i; const pk_frame_rect *r = &f->rects[i];
        ASSERT_EQ(e[0], r->top); ASSERT_EQ(e[1], r->bottom); ASSERT_EQ(e[2], r->lo_top); ASSERT_EQ(e[3], r->lo_bottom);
        ASSERT_EQ(e[4], r->number); ASSERT_EQ(e[5], (int)r->type);
    }
    pk_framing_free(f); PASS();
}
static const char *ENDS[] = { "r4","r2","r201900","r121838","r172139","g400","rollbin","stripcal","one_frame","frames36","blank","leader_only","short","half_gap_dx",
                              "partial_both_ends","flush_ends","empty_blind","cheap_test_fails","half_gap_veto" };
#define KE(sfx) (snprintf(k, sizeof k, "%s." sfx, name), k)
TEST ends_case(const char *name) {
    char k[96];                                                          /* profile, params and expectations all come from frame_ends.pkv */
    const pkv_array *P = pkv_get(V_ends, KE("profile")), *D = pkv_get(V_ends, KE("dx_rows")), *PA = pkv_get(V_ends, KE("params")), *SW = pkv_get(V_ends, KE("scanw")),
                    *G = pkv_get(V_ends, KE("geom"));
    ASSERT(P && PA && SW && G);                                          /* dx_rows may be absent when a strip has none */
    const int32_t *pa = PA->data, *sw = SW->data;
    pk_frame_film film = { ((const int32_t *)G->data)[2] != 0, pa[5] != 0 };
    int rows = (int)P->dims[0];
    for (int ag = 0; ag < 2; ag++) {
        k[0] = 0; const pkv_array *R = pkv_get(V_ends, ag ? KE("rects_ag") : KE("rects_na")); ASSERT(R);
        pk_frame_params fp = { pa[1], pa[2], pa[0], ag != 0, D ? D->data : NULL, pa[4] }; pk_framing *f;
        ASSERT_EQ(PK_OK, pk_frame_strip_profile(P->data, rows, &fp, &film, &f));
        ASSERT_EQ(R->dims[0], f->n); ASSERT_EQ((unsigned)sw[ag], f->scanw);
        for (int i = 0; i < f->n; i++) { const int32_t *e = (const int32_t *)R->data + 6 * i;
            ASSERT_EQ(e[0], f->rects[i].top); ASSERT_EQ(e[1], f->rects[i].bottom); ASSERT_EQ(e[2], f->rects[i].lo_top);
            ASSERT_EQ(e[3], f->rects[i].lo_bottom); ASSERT_EQ(e[4], f->rects[i].number); ASSERT_EQ(e[5], (int)f->rects[i].type); }
        /* S-R19 survives the blind pass: the strips whose first run search finds nothing are flagged in both passes */
        ASSERT_EQ(!strcmp(name, "blank") || !strcmp(name, "leader_only") || !strcmp(name, "r121838"), (int)f->not_kodak_exact);
        pk_framing_free(f);
        /* pkf_frame_strip: the framing reads R = rows - (planes - 1) profile rows; UC's planes only enter through R (RE 31 sec 8), so a 3-plane and a
         * 4-plane IR strip declaring R + planes - 1 stored rows frame exactly as UC's R-row strip does */
        for (int planes = 3; planes <= 4; planes++) {
            uint8_t *buf = calloc((size_t)(rows + 4) * 3, 1); ASSERT(buf);
            memcpy(buf, P->data, (size_t)rows * 3); memset(buf + (size_t)rows * 3, 0xA5, 12);   /* extra stored rows the framing must ignore */
            pkd_strip st; memset(&st, 0, sizeof st); st.rows = rows + planes - 1; st.profile = buf;
            pk_framing *g; ASSERT_EQ(PK_OK, pkf_frame_strip(&st, planes, &fp, &film, &g));
            ASSERT_EQ(R->dims[0], g->n); ASSERT_EQ((unsigned)sw[ag], g->scanw);
            for (int i = 0; i < g->n; i++) { const int32_t *e = (const int32_t *)R->data + 6 * i;
                ASSERT_EQ(e[0], g->rects[i].top); ASSERT_EQ(e[1], g->rects[i].bottom); ASSERT_EQ(e[5], (int)g->rects[i].type); }
            pk_framing_free(g); free(buf);
        }
    }
    PASS();
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); V = pkv_open(PKV_DIR "/frame.pkv"); if (!V) { fprintf(stderr, "frame.pkv missing\n"); return 1; }
    for (size_t i = 0; i < sizeof S / sizeof S[0]; i++) RUN_TEST1(strip_case, S[i]);
    V_ends = pkv_open(PKV_DIR "/frame_ends.pkv"); if (!V_ends) { fprintf(stderr, "frame_ends.pkv missing\n"); return 1; }
    for (size_t i = 0; i < sizeof ENDS / sizeof ENDS[0]; i++) RUN_TEST1(ends_case, ENDS[i]);
    pkv_close(V_ends); pkv_close(V); GREATEST_MAIN_END();
}
