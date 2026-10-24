/* The lo-res decimation weights, loaded from the user's own TLB.dll (see lores_weights.h). The only compiled-in facts are sizes, file offsets
 * and SHA-256 values: no Kodak bytes. */
#include "decode/lores_weights.h"
#include "util/util.h"
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TLB_SIZE 536576u
#define TLB_SHA "5866ec56776644e23c2c7e3755b4fc097761395db5731bf242998794a6f01647"
#define BLOB_SHA "8867d8122334f8165d2b9e69f5e6c0e477fafa01ea4f13ea2d853c6fdf2cb08d"
/* file offsets in TLB.dll 3.0.4.27 of the tables at VA 0x10066120 (4x4), 0x10066260 (6x6), 0x10066160 (8x8) */
static const struct { size_t off, n; } PART[3] = { { 418080, 64 }, { 418400, 144 }, { 418144, 256 } };

static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static uint16_t W4[4][4], W6[6][6], W8[8][8];
static int ready;

int pkd_lores_ready(void) { return __atomic_load_n(&ready, __ATOMIC_ACQUIRE); }

const uint16_t *pkd_lores_row(int ratio, int l) {
    if (!pkd_lores_ready() || l < 0 || l >= ratio) return NULL;
    return ratio == 4 ? W4[l] : ratio == 6 ? W6[l] : ratio == 8 ? W8[l] : NULL;
}

pk_status pkd_lores_install(const uint8_t *blob, size_t n) {
    if (!blob || n != PKD_LORES_BLOB) return PK_E_ARG;
    char hex[65];
    pku_sha256_hex(blob, n, hex);
    if (strcmp(hex, BLOB_SHA) != 0) return PK_E_CORRUPT;
    pthread_mutex_lock(&mu);
    if (!ready) {
        const uint8_t *p = blob;
        for (int i = 0; i < 16; i++, p += 4) W4[i / 4][i % 4] = (uint16_t)(p[0] | p[1] << 8);
        for (int i = 0; i < 36; i++, p += 4) W6[i / 6][i % 6] = (uint16_t)(p[0] | p[1] << 8);
        for (int i = 0; i < 64; i++, p += 4) W8[i / 8][i % 8] = (uint16_t)(p[0] | p[1] << 8);
        __atomic_store_n(&ready, 1, __ATOMIC_RELEASE);
    }
    pthread_mutex_unlock(&mu);
    return PK_OK;
}

pk_status pkd_lores_from_tlb(const uint8_t *tlb, size_t n, uint8_t blob[PKD_LORES_BLOB]) {
    if (!tlb || !blob || n != TLB_SIZE) return PK_E_ARG;
    char hex[65];
    pku_sha256_hex(tlb, n, hex);
    if (strcmp(hex, TLB_SHA) != 0) return PK_E_CORRUPT;
    size_t at = 0;
    for (int i = 0; i < 3; i++) { memcpy(blob + at, tlb + PART[i].off, PART[i].n); at += PART[i].n; }
    return PK_OK;
}

pk_status pkd_lores_load_blob_file(const char *path) {
    uint8_t *d = NULL;
    size_t n = 0;
    pk_status st = pku_read_file(path, &d, &n);
    if (st) return st == PK_E_NOT_FOUND ? PK_E_VENDOR_MISSING : st;
    st = pkd_lores_install(d, n);
    free(d);
    return st;
}

pk_status pkd_lores_load_derived(const char *derived_root) {
    static const char *const F[3] = { "tlb_lores_w4x4_10066120.bin", "tlb_lores_w6x6_10066260.bin", "tlb_lores_w8x8_10066160.bin" };
    if (!derived_root) return PK_E_ARG;
    uint8_t blob[PKD_LORES_BLOB];
    size_t at = 0;
    for (int i = 0; i < 3; i++) {
        char path[2048];
        if (snprintf(path, sizeof path, "%s/imau_tables/%s", derived_root, F[i]) >= (int)sizeof path) return PK_E_ARG;
        uint8_t *d = NULL;
        size_t n = 0;
        pk_status st = pku_read_file(path, &d, &n);
        if (st) return st == PK_E_NOT_FOUND ? PK_E_VENDOR_MISSING : st;
        if (n != PART[i].n) { free(d); return PK_E_CORRUPT; }
        memcpy(blob + at, d, n);
        at += n;
        free(d);
    }
    return pkd_lores_install(blob, sizeof blob);
}
