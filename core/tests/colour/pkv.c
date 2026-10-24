#include "pkv.h"
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct pkv_file {
    int n;
    pkv_array *a;
};

static const size_t DT_SIZE[7] = {0, 1, 2, 2, 4, 4, 8};

static uint32_t rd32(const unsigned char *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

void pkv_close(pkv_file *f) {
    if (!f) return;
    for (int i = 0; i < f->n; i++) free(f->a[i].data);
    free(f->a);
    free(f);
}

static unsigned char *slurp(const char *path, size_t *len) {
    FILE *fp = fopen(path, "rb");
    if (!fp) return NULL;
    unsigned char *buf = NULL;
    size_t cap = 0, n = 0;
    for (;;) {
        if (n == cap) {
            size_t nc = cap ? cap * 2 : 65536;
            unsigned char *nb = realloc(buf, nc);
            if (!nb) { free(buf); fclose(fp); return NULL; }
            buf = nb; cap = nc;
        }
        size_t r = fread(buf + n, 1, cap - n, fp);
        if (r == 0) break;
        n += r;
    }
    int bad = ferror(fp);
    fclose(fp);
    if (bad) { free(buf); return NULL; }
    *len = n;
    return buf;
}

/* Array payloads are copied into their own allocations so they are suitably
   aligned for their dtype regardless of the preceding name length. */
pkv_file *pkv_open(const char *path) {
    size_t len = 0, o = 8;
    unsigned char *b = slurp(path, &len);
    if (!b) return NULL;
    pkv_file *f = NULL;
    if (len < 8 || memcmp(b, "PKV1", 4) != 0) goto fail;
    uint32_t n = rd32(b + 4);
    if (n > len) goto fail; /* cheap sanity bound only (an array takes at least 19 bytes: name length, dtype, ndim, 4 dims); the reads below check each array */
    f = calloc(1, sizeof *f);
    if (!f) goto fail;
    f->a = calloc(n ? n : 1, sizeof *f->a);
    if (!f->a) goto fail;
    for (uint32_t i = 0; i < n; i++) {
        if (o >= len) goto fail;
        size_t L = b[o++];
        if (L >= 64 || len - o < L + 2 + 16) goto fail;
        pkv_array *a = &f->a[i];
        memcpy(a->name, b + o, L); a->name[L] = 0; o += L;
        a->dtype = b[o]; a->ndim = b[o + 1]; o += 2;
        if (a->dtype < 1 || a->dtype > 6 || a->ndim > 4) goto fail;
        size_t cnt = 1;
        for (int d = 0; d < 4; d++) {
            uint32_t v = rd32(b + o + 4 * d);
            if (d < a->ndim) {
                if (v > INT32_MAX) goto fail;
                a->dims[d] = (int)v;
                if (v && cnt > SIZE_MAX / v) goto fail;
                cnt *= v;
            }
        }
        o += 16;
        size_t bytes = cnt * DT_SIZE[a->dtype];
        if (cnt && bytes / cnt != DT_SIZE[a->dtype]) goto fail;
        if (len - o < bytes) goto fail;
        a->n = cnt;
        a->data = malloc(bytes ? bytes : 1);
        if (!a->data) goto fail;
        memcpy(a->data, b + o, bytes);
        o += bytes;
        f->n = (int)i + 1;
    }
    free(b);
    return f;
fail:
    free(b);
    pkv_close(f);
    return NULL;
}

const pkv_array *pkv_get(const pkv_file *f, const char *name) {
    if (!f || !name) return NULL;
    for (int i = 0; i < f->n; i++)
        if (strcmp(f->a[i].name, name) == 0) return &f->a[i];
    return NULL;
}

int pkv_list_count(const pkv_file *f, const char *list) {
    const pkv_array *a = pkv_get(f, list);
    if (!a || a->dtype != 1 || a->n == 0) return 0;     /* an empty list holds no id */
    int n = 1;
    for (size_t i = 0; i < a->n; i++) n += ((const char *)a->data)[i] == ',';
    return n;
}

int pkv_list_index(const pkv_file *f, const char *list, const char *id) {
    const pkv_array *a = pkv_get(f, list);
    if (!a || a->dtype != 1 || !id || a->n == 0) return -1;
    const char *s = a->data;
    size_t len = a->n, idl = strlen(id);
    int k = 0;
    for (size_t i = 0; i <= len; k++) {
        size_t j = i;
        while (j < len && s[j] != ',') j++;
        if (j - i == idl && !memcmp(s + i, id, idl)) return k;
        i = j + 1;
    }
    return -1;
}

/* C9: a Kodak-match test needs files the public tree does not carry (Kodak truth vectors, the user's own PSI install, vendor/derived).
 * CMake lists them in PK_NEED_FILES ("a|b|c"); when one is missing the test says so and exits 77, which ctest reports as skipped. */
#ifdef PK_NEED_FILES
__attribute__((constructor)) static void pkv_skip_when_inputs_missing(void) {
    const char *p = PK_NEED_FILES;
    while (*p) {
        const char *e = strchr(p, '|');
        size_t n = e ? (size_t)(e - p) : strlen(p);
        char path[4096];
        if (n < sizeof path) {
            memcpy(path, p, n); path[n] = 0;
            if (access(path, F_OK) != 0) { fprintf(stderr, "SKIP: %s is missing (Kodak-match input, not in the public tree)\n", path); _exit(77); }
        }
        p += n + (e ? 1 : 0);
    }
}
#endif
