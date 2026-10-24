#include "util/util.h"

static const char A[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

size_t pku_b64_encode(const uint8_t *in, size_t n, char *out, size_t cap) {
    size_t need = (n / 3 + (n % 3 != 0)) * 4;
    if (!out || cap < need + 1) return 0;
    size_t o = 0;
    for (size_t i = 0; i < n; i += 3) {
        uint32_t v = (uint32_t)in[i] << 16;
        if (i + 1 < n) v |= (uint32_t)in[i + 1] << 8;
        if (i + 2 < n) v |= in[i + 2];
        out[o++] = A[v >> 18];
        out[o++] = A[(v >> 12) & 63];
        out[o++] = i + 1 < n ? A[(v >> 6) & 63] : '=';
        out[o++] = i + 2 < n ? A[v & 63] : '=';
    }
    out[o] = 0;
    return o;
}

static int val(char c) {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    if (c == '/') return 63;
    return -1;
}

pk_status pku_b64_decode(const char *in, size_t len, uint8_t *out, size_t cap, size_t *got) {
    if (got) *got = 0;
    if (!in || (len && !out) || len % 4) return PK_E_CORRUPT;
    size_t o = 0;
    for (size_t i = 0; i < len; i += 4) {
        int pad = 0, v[4];
        for (int k = 0; k < 4; k++) {
            char c = in[i + k];
            if (c == '=') {
                if (i + 4 != len || k < 2) return PK_E_CORRUPT;   /* padding only in the last two positions */
                pad++; v[k] = 0;
            } else {
                if (pad) return PK_E_CORRUPT;                      /* data after padding */
                if ((v[k] = val(c)) < 0) return PK_E_CORRUPT;
            }
        }
        uint32_t x = (uint32_t)v[0] << 18 | (uint32_t)v[1] << 12 | (uint32_t)v[2] << 6 | (uint32_t)v[3];
        size_t cnt = 3 - (size_t)pad;
        if (cap - o < cnt || o > cap) return PK_E_CORRUPT;
        out[o++] = (uint8_t)(x >> 16);
        if (cnt > 1) out[o++] = (uint8_t)(x >> 8);
        if (cnt > 2) out[o++] = (uint8_t)x;
    }
    if (got) *got = o;
    return PK_OK;
}
