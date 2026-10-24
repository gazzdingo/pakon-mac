#include "util/util.h"
#include <stdlib.h>
#include <string.h>

#define ZIP_LOCAL_SIG 0x04034b50u
#define ZIP_CENTRAL_SIG 0x02014b50u
#define ZIP_EOCD_SIG 0x06054b50u
#define ZIP_NAME_MAX 255u

uint32_t pku_crc32(uint32_t crc, const void *data, size_t n) {
    static const uint32_t T[16] = { 0x00000000u, 0x1db71064u, 0x3b6e20c8u, 0x26d930acu, 0x76dc4190u, 0x6b6b51f4u, 0x4db26158u, 0x5005713cu,
                                    0xedb88320u, 0xf00f9344u, 0xd6d6a3e8u, 0xcb61b38cu, 0x9b64c2b0u, 0x86d3d2d4u, 0xa00ae278u, 0xbdbdf21cu };
    const uint8_t *p = (const uint8_t *)data;
    crc = ~crc;
    for (size_t i = 0; i < n; i++) {
        crc ^= p[i];
        crc = (crc >> 4) ^ T[crc & 15];
        crc = (crc >> 4) ^ T[crc & 15];
    }
    return ~crc;
}

static unsigned rd16(const uint8_t *p) { return (unsigned)p[0] | (unsigned)p[1] << 8; }
static uint32_t rd32(const uint8_t *p) { return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24; }
static void wr16(uint8_t *p, unsigned v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static void wr32(uint8_t *p, uint32_t v) { for (int i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (8 * i)); }

struct pku_zip { pku_zip_entry *e; size_t n; };

void pku_zip_close(pku_zip *z) {
    if (!z) return;
    free(z->e);
    free(z);
}
size_t pku_zip_count(const pku_zip *z) { return z ? z->n : 0; }
const pku_zip_entry *pku_zip_at(const pku_zip *z, size_t i) { return z && i < z->n ? &z->e[i] : NULL; }
const pku_zip_entry *pku_zip_find(const pku_zip *z, const char *name) {
    if (!z || !name) return NULL;
    for (size_t i = 0; i < z->n; i++) if (strcmp(z->e[i].name, name) == 0) return &z->e[i];
    return NULL;
}

pk_status pku_zip_open(const uint8_t *buf, size_t n, size_t max_entries, size_t max_entry_size, size_t max_total, pku_zip **out) {
    if (out) *out = NULL;
    if (!buf || !out) return PK_E_ARG;
    if (n < 22) return PK_E_CORRUPT;
    /* the end-of-central-directory record: the last position whose comment length reaches exactly the end of the file */
    size_t eocd = 0;
    int found = 0;
    size_t lo = n - 22 > 65535 ? n - 22 - 65535 : 0;
    for (size_t p = n - 22 + 1; p-- > lo;) {
        if (rd32(buf + p) == ZIP_EOCD_SIG && p + 22 + rd16(buf + p + 20) == n) { eocd = p; found = 1; break; }
    }
    if (!found) return PK_E_CORRUPT;
    const uint8_t *e = buf + eocd;
    if (rd16(e + 4) != 0 || rd16(e + 6) != 0) return PK_E_CORRUPT;                    /* one disk only */
    size_t count = rd16(e + 10);
    if (rd16(e + 8) != count || count == 0xFFFFu) return PK_E_CORRUPT;                  /* 0xFFFF is the zip64 marker */
    uint32_t cd_size = rd32(e + 12), cd_off = rd32(e + 16);
    if (cd_size == 0xFFFFFFFFu || cd_off == 0xFFFFFFFFu) return PK_E_CORRUPT;
    if ((uint64_t)cd_off + cd_size > eocd) return PK_E_CORRUPT;
    if (count > max_entries) return PK_E_CORRUPT;
    pku_zip *z = (pku_zip *)calloc(1, sizeof *z);
    if (!z) return PK_E_NOMEM;
    z->e = (pku_zip_entry *)calloc(count ? count : 1, sizeof *z->e);
    if (!z->e) { free(z); return PK_E_NOMEM; }
    pk_status st = PK_E_CORRUPT;
    size_t pos = cd_off, end = (size_t)cd_off + cd_size;
    uint64_t total = 0;
    uint32_t *lo_off = (uint32_t *)calloc(count ? count : 1, sizeof *lo_off), *hi_off = (uint32_t *)calloc(count ? count : 1, sizeof *hi_off);   /* each entry's [local header, data end) */
    if (!lo_off || !hi_off) { free(lo_off); free(hi_off); pku_zip_close(z); return PK_E_NOMEM; }
    for (size_t i = 0; i < count; i++) {
        if (end - pos < 46 || rd32(buf + pos) != ZIP_CENTRAL_SIG) goto fail;
        const uint8_t *c = buf + pos;
        unsigned flags = rd16(c + 8), method = rd16(c + 10);
        uint32_t crc = rd32(c + 16), csize = rd32(c + 20), usize = rd32(c + 24);
        size_t nlen = rd16(c + 28), elen = rd16(c + 30), clen = rd16(c + 32);
        unsigned disk = rd16(c + 34);
        uint32_t lho = rd32(c + 42);
        if (flags & (0x0001u | 0x0040u | 0x2000u)) goto fail;                          /* encrypted */
        if (method != 0 || csize != usize || usize == 0xFFFFFFFFu || lho == 0xFFFFFFFFu || disk != 0) goto fail;
        if (usize > max_entry_size) goto fail;
        total += usize;
        if (total > max_total) goto fail;
        if (nlen == 0 || nlen > ZIP_NAME_MAX) goto fail;
        if (end - pos - 46 < nlen + elen + clen) goto fail;
        const uint8_t *nm = c + 46;
        if (memchr(nm, 0, nlen) || nm[nlen - 1] == '/') goto fail;
        memcpy(z->e[i].name, nm, nlen);
        z->e[i].name[nlen] = 0;
        if (!pku_path_is_safe(z->e[i].name)) goto fail;
        for (size_t k = 0; k < i; k++) if (strcmp(z->e[k].name, z->e[i].name) == 0) goto fail;
        /* the local header must agree, and entry data must lie before the central directory */
        if ((uint64_t)lho + 30 > cd_off) goto fail;
        const uint8_t *l = buf + lho;
        if (rd32(l) != ZIP_LOCAL_SIG || rd16(l + 8) != 0) goto fail;
        if (rd16(l + 6) != flags) goto fail;                                           /* the local header must say what the central one says */
        if (!(flags & 0x0008u) && (rd32(l + 14) != crc || rd32(l + 18) != csize || rd32(l + 22) != usize)) goto fail;   /* no data descriptor: sizes and CRC repeat */
        size_t lnlen = rd16(l + 26), lelen = rd16(l + 28);
        if (lnlen != nlen || (uint64_t)lho + 30 + lnlen + lelen + usize > cd_off) goto fail;
        if (memcmp(l + 30, nm, nlen) != 0) goto fail;
        lo_off[i] = lho;
        hi_off[i] = (uint32_t)(lho + 30 + lnlen + lelen + usize);
        for (size_t k = 0; k < i; k++) if (lo_off[i] < hi_off[k] && lo_off[k] < hi_off[i]) goto fail;   /* overlapping entries */
        z->e[i].data = buf + lho + 30 + lnlen + lelen;
        z->e[i].size = usize;
        if (pku_crc32(0, z->e[i].data, usize) != crc) goto fail;
        pos += 46 + nlen + elen + clen;
        z->n = i + 1;
    }
    if (pos != end) goto fail;                                                          /* bytes after the last entry */
    free(lo_off); free(hi_off);
    *out = z;
    return PK_OK;
fail:
    free(lo_off); free(hi_off);
    pku_zip_close(z);
    return st;
}

typedef struct { char name[ZIP_NAME_MAX + 1]; uint32_t crc, size, off; } zw_ent;
struct pku_zipw { uint8_t *buf; size_t len, cap; zw_ent *e; size_t n, ecap; };

pku_zipw *pku_zipw_new(void) { return (pku_zipw *)calloc(1, sizeof(pku_zipw)); }
void pku_zipw_free(pku_zipw *w) {
    if (!w) return;
    free(w->buf);
    free(w->e);
    free(w);
}

static pk_status zw_put(pku_zipw *w, const void *d, size_t n) {
    if (n > (size_t)0xFFFFFFFFu || w->len + n > (size_t)0xFFFFFFFFu) return PK_E_FORMAT;   /* no zip64 */
    if (w->len + n > w->cap) {
        size_t nc = w->cap ? w->cap : 4096;
        while (nc < w->len + n) nc *= 2;
        uint8_t *nb = (uint8_t *)realloc(w->buf, nc);
        if (!nb) return PK_E_NOMEM;
        w->buf = nb; w->cap = nc;
    }
    if (n) memcpy(w->buf + w->len, d, n);
    w->len += n;
    return PK_OK;
}

pk_status pku_zipw_add(pku_zipw *w, const char *name, const void *data, size_t n) {
    if (!w || !name || (n && !data)) return PK_E_ARG;
    size_t nlen = strlen(name);
    if (nlen == 0 || nlen > ZIP_NAME_MAX || n > (size_t)0xFFFFFFFFu || w->n >= 0xFFFEu) return PK_E_ARG;
    if (w->n == w->ecap) {
        size_t nc = w->ecap ? w->ecap * 2 : 16;
        zw_ent *ne = (zw_ent *)realloc(w->e, nc * sizeof *ne);
        if (!ne) return PK_E_NOMEM;
        w->e = ne; w->ecap = nc;
    }
    zw_ent *z = &w->e[w->n];
    memcpy(z->name, name, nlen + 1);
    z->crc = pku_crc32(0, data, n);
    z->size = (uint32_t)n;
    z->off = (uint32_t)w->len;
    uint8_t h[30] = { 0 };
    wr32(h, ZIP_LOCAL_SIG); wr16(h + 4, 10);
    wr16(h + 12, 0x0021);                                  /* DOS date 1980-01-01, time 00:00 */
    wr32(h + 14, z->crc); wr32(h + 18, z->size); wr32(h + 22, z->size); wr16(h + 26, (unsigned)nlen);
    pk_status st = zw_put(w, h, sizeof h);
    if (st == PK_OK) st = zw_put(w, name, nlen);
    if (st == PK_OK) st = zw_put(w, data, n);
    if (st == PK_OK) w->n++;
    else w->len = z->off;                                  /* drop the partial entry */
    return st;
}

pk_status pku_zipw_finish(pku_zipw *w, uint8_t **out, size_t *outn) {
    if (out) *out = NULL;
    if (outn) *outn = 0;
    if (!w || !out || !outn) return PK_E_ARG;
    size_t cd = w->len;
    for (size_t i = 0; i < w->n; i++) {
        const zw_ent *z = &w->e[i];
        size_t nlen = strlen(z->name);
        uint8_t h[46] = { 0 };
        wr32(h, ZIP_CENTRAL_SIG); wr16(h + 4, 20); wr16(h + 6, 10);
        wr16(h + 14, 0x0021);
        wr32(h + 16, z->crc); wr32(h + 20, z->size); wr32(h + 24, z->size); wr16(h + 28, (unsigned)nlen);
        wr32(h + 38, 0); wr32(h + 42, z->off);
        pk_status st = zw_put(w, h, sizeof h);
        if (st == PK_OK) st = zw_put(w, z->name, nlen);
        if (st != PK_OK) return st;
    }
    uint8_t t[22] = { 0 };
    wr32(t, ZIP_EOCD_SIG); wr16(t + 8, (unsigned)w->n); wr16(t + 10, (unsigned)w->n);
    wr32(t + 12, (uint32_t)(w->len - cd)); wr32(t + 16, (uint32_t)cd);
    pk_status st = zw_put(w, t, sizeof t);
    if (st != PK_OK) return st;
    *out = w->buf; *outn = w->len;
    w->buf = NULL; w->len = w->cap = 0;
    return PK_OK;
}
