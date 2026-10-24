/* core_dx_kodak (Task 8): the DX parser, votes, frame numbers and strip hand-off against TLB.dll's own code
 * (lab/vectors/gen_dx.py runs FUN_10009790 with its type handlers, FUN_10015520 / FUN_100150e0, FUN_10005820 and FUN_100057f0 under
 * Unicorn). Why it is kept: the roll code (Task 20) and the framing veto (Task 18) read these numbers back from the recorded packets,
 * and a wrong line rollover, parity rule, vote tie or frame extrapolation changes which film stock and which frame numbers a roll
 * carries without any visible failure. The recorded v1 packets of both capture directories and the crafted files all go through.
 * Our own rules where TLB would over-read (N > 5, a response not exactly 30 bytes) are not asserted here: they are not Kodak's. */
#include "greatest.h"
#include <string.h>
#include "pkv.h"
#include "pakon/dx.h"
#include "boards/dx_internal.h"      /* pkb_dx_event, pkb_dx_events(), pkb_dx_votes() */
static pkv_file *V;
TEST every_recorded_packet_matches_uc(void) {
    const pkv_array *P = pkv_get(V, "packets"), *F = pkv_get(V, "file_of_packet"), *E = pkv_get(V, "events"),
                    *VT = pkv_get(V, "final_votes"), *W = pkv_get(V, "winner"), *FIN = pkv_get(V, "finish"), *FF = pkv_get(V, "frame_files"),
                    *FN = pkv_get(V, "frame_numbers"), *FT = pkv_get(V, "frame_numbers_tailfirst"), *FR = pkv_get(V, "frame_read"),
                    *SW = pkv_get(V, "scanw"), *GC = pkv_get(V, "good_count"), *TB = pkv_get(V, "frame_table"),
                    *SS = pkv_get(V, "speed_slot"),
                    *GE = pkv_get(V, "geometry"), *CA = pkv_get(V, "calib"), *SX = pkv_get(V, "status_words"), *AB = pkv_get(V, "abort"),
                    *TF = pkv_get(V, "tail_first"), *AI = pkv_get(V, "aps_ids");
    ASSERT(P && F && E && VT && W && FIN && FF && FN && FT && FR && SW && GC && TB && SS && GE && CA && SX && AB && TF && AI);
    size_t n = (size_t)P->dims[0], nfiles = (size_t)W->n, ei = 0;
    for (size_t k = 0; k < nfiles; k++) {
        const int32_t *ge = (const int32_t *)GE->data + 5 * k, *ca = (const int32_t *)CA->data + 3 * k;
        pk_dx_geometry g; ASSERT_EQ(PK_OK, pk_dx_geometry_for(ge[0], ge[1] != 0, &g));
        g.aps24 = ge[2] != 0; g.single_strip = ge[3] != 0; g.film_context = (unsigned)ge[4];
        pk_dx *dx; ASSERT_EQ(PK_OK, pk_dx_new_geometry(&g, &dx));
        pk_dx_calibration cal = { ca[0] != 0, ca[1] != 0, ca[2] != 0 }; ASSERT_EQ(PK_OK, pk_dx_set_calibration(dx, &cal));
        pk_dx_speed_history sh;            /* the speed history this strip starts from (TLB scanner+0x398); all zero = none */
        for (int j = 0; j < 5; j++) sh.slot[j] = (uint32_t)((const int32_t *)SS->data)[5 * k + j];
        ASSERT_EQ(PK_OK, pk_dx_attach_speed_history(dx, &sh));
        int in_file = 0;     /* pk_dx numbers the packets it was fed; the vector file numbers them over all files */
        for (size_t i = 0; i < n; i++) {
            if (((const int32_t *)F->data)[i] != (int32_t)k) continue;
            ASSERT_EQ(PK_OK, pk_dx_feed_packet(dx, (const uint8_t *)P->data + 30 * i, 30));
            ASSERT_EQ(((const int32_t *)SX->data)[i], (int32_t)pk_dx_status_word(dx));      /* TLB's status word, incl. the calibration abort */
            const pkb_dx_event *ev; size_t nev; pkb_dx_events(dx, &ev, &nev);       /* events produced by this packet */
            for (size_t j = 0; j < nev; j++, ei++) {
                const int32_t *e = (const int32_t *)E->data + 6 * ei;
                ASSERT_EQ(e[0], (int32_t)i); ASSERT_EQ(in_file, ev[j].pkt);
                ASSERT_EQ(e[1], ev[j].type); ASSERT_EQ(e[2], ev[j].rollover);
                ASSERT_EQ(e[3], ev[j].line); ASSERT_EQ(e[4], ev[j].w0); ASSERT_EQ(e[5], ev[j].w1);
            }
            in_file++;
        }
        int votes[4][3]; int win; pkb_dx_votes(dx, votes, &win);
        ASSERT_MEM_EQ(((const int32_t *)VT->data + 12 * k), votes, sizeof votes);     /* parenthesised: the macro casts its argument to unsigned char * */
        ASSERT_EQ(((const int32_t *)W->data)[k], win);
        if (k == (size_t)((const int32_t *)FF->data)[0] || k == (size_t)((const int32_t *)FF->data)[1]) {      /* frame numbers, with and without tail-first */
            bool tf = k == (size_t)((const int32_t *)FF->data)[1]; const int32_t *wn = (const int32_t *)(tf ? FT : FN)->data;
            for (int f = 0; f < 10; f++) { bool rd = false; ASSERT_EQ(wn[f], pk_dx_frame_half_frames(dx, f, &rd)); if (!tf) ASSERT_EQ(((const int32_t *)FR->data)[f], (int)rd); }
        }
        for (int f = 0; f < 100; f++) {                                           /* the whole frame table of every file, not only entries 0..9 */
            bool rd = false; int hf = pk_dx_frame_half_frames(dx, f, &rd);
            ASSERT_EQ(((const int32_t *)TB->data)[200 * k + 2 * f], hf); ASSERT_EQ(((const int32_t *)TB->data)[200 * k + 2 * f + 1], (int)rd);
        }
        ASSERT_EQ(((const int32_t *)AB->data)[k], (int32_t)pk_dx_calibration_abort(dx));
        ASSERT_EQ(((const int32_t *)TF->data)[k], (int32_t)pk_dx_tail_first(dx));
        pkb_dx_state stt; pkb_dx_state_get(dx, &stt);                             /* the APS type 1 / type 2 results (hole+0xbc4, 0xbc8, 0xbbc, 0xbc0) */
        const uint32_t *ai = (const uint32_t *)AI->data + 4 * k;
        ASSERT_EQ(ai[0], stt.hole[0xbc4 >> 2]); ASSERT_EQ(ai[1], stt.hole[0xbc8 >> 2]);
        ASSERT_EQ(ai[2], stt.hole[0xbbc >> 2]); ASSERT_EQ(ai[3], stt.hole[0xbc0 >> 2]);
        pk_dx_strip ds; ASSERT_EQ(PK_OK, pk_dx_finish_strip(dx, true, &ds));      /* FUN_10005820 hand-off */
        ASSERT_STR_EQ(((const int32_t *)FIN->data)[2 * k] != PK_DX_NONE_CODE ? "dx" : "none", ds.dx_source);
        ASSERT_EQ(((const int32_t *)TF->data)[k], (int32_t)ds.tail_first);
        ASSERT_EQ(((const int32_t *)FIN->data)[2 * k], ds.product); ASSERT_EQ(((const int32_t *)FIN->data)[2 * k + 1], ds.specifier);
        ASSERT_EQ(((const int32_t *)SW->data)[k], (int32_t)ds.scanw); ASSERT_EQ(((const int32_t *)GC->data)[k], ds.good_count);
        pk_dx_strip dz; ASSERT_EQ(PK_OK, pk_dx_finish_strip(dx, false, &dz));    /* the publish that never ran: the constructor's 0/0 */
        ASSERT_EQ(0, dz.product); ASSERT_EQ(0, dz.specifier); ASSERT_STR_EQ("none", dz.dx_source);
        pk_dx_free(dx);
    }
    ASSERT_EQ((size_t)E->dims[0], ei);        /* no event missing and none extra */
    PASS();
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN(); V = pkv_open(PKV_DIR "/dx.pkv"); if (!V) { fprintf(stderr, "dx.pkv missing\n"); return 1; }
    RUN_TEST(every_recorded_packet_matches_uc);
    pkv_close(V); GREATEST_MAIN_END();
}
