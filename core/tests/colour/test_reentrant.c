/* The loaders keep no global state (colour.h): several threads loading the same Kodak data at once must all succeed
 * with identical results. Guards against strtok-style hidden state in the text parsers. */
#include <pthread.h>
#include <string.h>
#include "greatest.h"
#include "data/kodak_map.h"

#define NTHREADS 4
#define NLOADS 300

typedef struct { int failures, mismatches; const int16_t (*ref)[16]; } worker;

static void *iso_worker(void *arg) {
    worker *w = arg;
    static const char *root = VENDOR_ROOT;
    for (int i = 0; i < NLOADS; i++) {
        int16_t t[128][16];
        if (pkc_film_iso_load(root, t) != PK_OK) { w->failures++; continue; }
        if (memcmp(t, w->ref, sizeof t)) w->mismatches++;
    }
    return NULL;
}

TEST film_iso_load_concurrent(void) {
    static int16_t ref[128][16];
    ASSERT_EQ(PK_OK, pkc_film_iso_load(VENDOR_ROOT, ref));
    pthread_t th[NTHREADS]; worker w[NTHREADS];
    for (int i = 0; i < NTHREADS; i++) {
        memset(&w[i], 0, sizeof w[i]); w[i].ref = (const int16_t (*)[16])ref;
        ASSERT_EQ(0, pthread_create(&th[i], NULL, iso_worker, &w[i]));
    }
    for (int i = 0; i < NTHREADS; i++) pthread_join(th[i], NULL);
    for (int i = 0; i < NTHREADS; i++) { ASSERT_EQ(0, w[i].failures); ASSERT_EQ(0, w[i].mismatches); }
    PASS();
}

GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    RUN_TEST(film_iso_load_concurrent);
    GREATEST_MAIN_END();
}
