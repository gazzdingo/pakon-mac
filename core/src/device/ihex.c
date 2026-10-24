/* Strict Intel-HEX parser (record types 00, 01, 02, 04) into a 64 KiB image with a used-byte map. */
#include "pakon/device.h"
#include <stdlib.h>
#include <string.h>

static int hexv(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int is_ws(uint8_t c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }

void pk_image_free(pk_image *img) { free(img); }

/* recs/nrecs may both be NULL. With them, the data records come back in FILE ORDER, a record longer than 16 bytes split into
 * 16-byte pieces (Kodak's MAX_INTEL_HEX_RECORD_LENGTH; the vendor files hold none longer), addresses folded as in the image. */
static pk_status parse_impl(const uint8_t *text, size_t n, pk_image **out, pk_ihex_rec **recs, size_t *nrecs) {
    if (out) *out = NULL;
    if (recs) *recs = NULL;
    if (nrecs) *nrecs = 0;
    if (!out || (n && !text) || (!recs != !nrecs)) return PK_E_ARG;
    pk_image *img = (pk_image *)calloc(1, sizeof *img);
    if (!img) return PK_E_NOMEM;
    pk_ihex_rec *rl = NULL;
    size_t rn = 0, rcap = 0;
    uint32_t base = 0, lo = 0xFFFFFFFFu, hi = 0;
    int eof = 0;
    size_t i = 0;
    while (i < n) {
        if (is_ws(text[i])) { i++; continue; }   /* blank space and line ends between records */
        if (text[i] != ':' || eof) goto bad;     /* anything but a record, or anything after the end record */
        i++;
        size_t j = i;
        while (j < n && text[j] != '\r' && text[j] != '\n') j++;
        size_t len = j - i;
        while (len && (text[i + len - 1] == ' ' || text[i + len - 1] == '\t')) len--;   /* trailing blanks */
        if (len < 10 || (len & 1)) goto bad;     /* LL AAAA TT CC at least; whole bytes only */
        uint8_t rec[2 + 1 + 255 + 1 + 4];
        size_t nb = len / 2;
        if (nb > sizeof rec) goto bad;
        unsigned sum = 0;
        for (size_t k = 0; k < nb; k++) {
            int h = hexv(text[i + 2 * k]), l = hexv(text[i + 2 * k + 1]);
            if (h < 0 || l < 0) goto bad;
            rec[k] = (uint8_t)(h << 4 | l);
            sum += rec[k];
        }
        if ((sum & 0xFF) != 0) goto bad;         /* the checksum makes the record sum to zero */
        unsigned cnt = rec[0], addr = (unsigned)rec[1] << 8 | rec[2], type = rec[3];
        if (nb != cnt + 5) goto bad;
        switch (type) {
        case 0:
            if (recs) {
                for (unsigned k = 0; k < cnt; k += 16) {
                    if (rn == rcap) {
                        size_t nc = rcap ? rcap * 2 : 64;
                        pk_ihex_rec *nl = (pk_ihex_rec *)realloc(rl, nc * sizeof *nl);
                        if (!nl) { free(rl); free(img); return PK_E_NOMEM; }
                        rl = nl; rcap = nc;
                    }
                    unsigned take = cnt - k < 16 ? cnt - k : 16;
                    if (base + addr + k + take > 0x10000u) goto bad;
                    memset(&rl[rn], 0, sizeof rl[rn]);
                    rl[rn].addr = (uint16_t)(base + addr + k);
                    rl[rn].len = (uint8_t)take;
                    memcpy(rl[rn].data, rec + 4 + k, take);
                    rn++;
                }
            }
            for (unsigned k = 0; k < cnt; k++) {
                uint32_t a = base + addr + k;
                if (a >= 0x10000u) goto bad;     /* does not fold into a 64 KiB image */
                if (PK_IMAGE_USED(img, a)) goto bad;   /* a byte set twice */
                img->mem[a] = rec[4 + k];
                img->used[a >> 3] = (uint8_t)(img->used[a >> 3] | (1u << (a & 7)));
                img->nbytes++;
                if (a < lo) lo = a;
                if (a > hi) hi = a;
            }
            break;
        case 1:
            if (cnt != 0) goto bad;
            eof = 1;
            break;
        case 2:
            if (cnt != 2 || addr != 0) goto bad;
            base = ((uint32_t)rec[4] << 8 | rec[5]) << 4;
            break;
        case 4:
            if (cnt != 2 || addr != 0) goto bad;
            base = ((uint32_t)rec[4] << 8 | rec[5]) << 16;
            break;
        default: goto bad;                       /* 03 and 05 (start address) and anything else */
        }
        i = j;
    }
    if (!eof || img->nbytes == 0) goto bad;
    img->min_addr = lo;
    img->max_addr = hi;
    *out = img;
    if (recs) { *recs = rl; *nrecs = rn; }
    return PK_OK;
bad:
    free(rl);
    free(img);
    return PK_E_FORMAT;
}

pk_status pk_ihex_parse(const uint8_t *text, size_t n, pk_image **out) { return parse_impl(text, n, out, NULL, NULL); }

pk_status pk_ihex_parse_records(const uint8_t *text, size_t n, pk_image **out, pk_ihex_rec **recs, size_t *nrecs) {
    if (!recs || !nrecs) { if (out) *out = NULL; return PK_E_ARG; }
    return parse_impl(text, n, out, recs, nrecs);
}
