#define _POSIX_C_SOURCE 200809L
/* A simulated F-135 Plus for developer runs (--fake, debug builds only; the whole file is compiled out with NDEBUG). It is a RAW
 * transport: the CLI puts the real write guard (and the recorder) in front of it, so every fake run exercises the guard, the link, the
 * boards and the HW-1 commands exactly as a real run does. It answers just enough: the calibration chip (an 8 KB image with the
 * copies named by --fake-damage broken), board status reads, a latched register 0x02 with the 0x06 acknowledge, lamp temperatures
 * that warm up, a film strip that passes the sensors, and a cable that can be pulled (--fake-unplug N). It is not a model of
 * the scanner; it exists so the commands can be run and replayed without hardware. */
#ifndef NDEBUG
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include "cli.h"
#include "link/link.h"

typedef struct {
    pthread_mutex_t mu;
    uint8_t eeprom[0x2000];
    uint8_t a4;
    uint8_t resp[64];
    size_t resp_n;
    int lamp_en, motor_run, dx_active, film_in;
    unsigned reads02, reads_since_motor, reads_since_lamp, reads88, packets;
    int pending;                  /* register 0x02 value waiting for its acknowledge, 0 = none */
    int stable_sent, in_sent, out_sent, silent_sent;
    int unplug_after;
    /* the unloaded FX2 (pakon load --fake): mode 1 = boot ROM with the 8051 held or running Kodak's stage-1, 2 = firmware released and
     * waiting to re-enumerate, 0 = the loaded scanner above */
    int fx_mode, held, s1_run;
    unsigned a3_bytes;
    uint8_t m[0x10000];
    uint8_t wr[0x10000 / 8];
} fk;

static uint32_t crc32(const uint8_t *p, size_t n) {
    uint32_t c = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        c ^= p[i];
        for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return ~c;
}

static void put32(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); }

static void build_eeprom(fk *f, unsigned damage) {
    memset(f->eeprom, 0xFF, sizeof f->eeprom);
    uint32_t lcg = 0x1234567u;
    static const struct { unsigned off, len; int calwiz; } C[4] = { { 0x000, 0x40, 1 }, { 0x400, 0x40, 1 }, { 0x800, 0x24, 0 }, { 0xA00, 0x24, 0 } };
    for (int i = 0; i < 4; i++) {
        uint8_t *c = f->eeprom + C[i].off;
        lcg = 0x1234567u + (uint32_t)C[i].calwiz;      /* the two copies of a kind are identical */
        for (unsigned k = 8; k < C[i].len; k++) { lcg = lcg * 1664525u + 1013904223u; c[k] = (uint8_t)(lcg >> 24); }
        if (C[i].calwiz) { put32(c + 0x08, 8); put32(c + 0x0C, 0x547); put32(c + 0x10, 12345); }
        put32(c, C[i].len);
        put32(c + 4, crc32(c + 8, C[i].len - 8));
        if (damage & (1u << i)) c[C[i].len - 3] ^= 0x5A;   /* the checksum no longer matches */
    }
}

static void gone_check(fk *f, pk_status *st) { if (f->unplug_after && f->packets >= (unsigned)f->unplug_after) *st = PK_E_DISCONNECTED; }

static void answer_read(fk *f, uint8_t addr, uint8_t reg, uint8_t cnt) {
    uint8_t status = 0x88;
    uint8_t *r = f->resp;
    memset(r, 0, sizeof f->resp);
    switch (reg) {
    case 0x02:
        f->reads02++;
        if (f->motor_run) f->reads_since_motor++;
        if (f->lamp_en) f->reads_since_lamp++;
        if (!f->pending) {
            if (f->lamp_en && !f->stable_sent && f->reads_since_lamp >= 3) { f->pending = 0x02; f->stable_sent = 1; }
            else if (f->motor_run && f->dx_active && !f->in_sent && f->reads_since_motor >= 6) { f->pending = 0x04; f->in_sent = 1; f->film_in = 1; }
            else if (f->motor_run && f->dx_active && f->in_sent && !f->out_sent && f->reads_since_motor >= 40) { f->pending = 0x04; f->out_sent = 1; f->film_in = 0; }
        }
        if (f->pending) { r[4] = (uint8_t)f->pending; status = 0x88; }
        else if (f->reads02 == 4 && !f->silent_sent) { r[4] = 0x20; status = 0x08; f->silent_sent = 1; }   /* a non-zero value without the event flag */
        else status = 0x08;
        break;
    case 0x07: r[4] = 0; r[5] = 0; r[6] = 0x0A; break;                      /* devinfo[2] = 0x0A, the light firmware version byte */
    case 0x83: r[4] = f->lamp_en ? 0x0A : 0x18; break;                      /* temperature valid; lit: stable (bit 1); off: levels-zero (bit 4, S-R26 confirm) */
    case 0x84: r[4] = 0x80; r[5] = 0x02; break;                             /* setpoint 0x280 = 40.0 C */
    case 0x88: {
        f->reads88++;
        int lamp = f->lamp_en ? 0x280 - (f->reads88 < 5 ? (int)(20 - 4 * f->reads88) : 0) : 0x1E0;
        r[4] = (uint8_t)lamp; r[5] = (uint8_t)(lamp >> 8); r[6] = 0xC0; r[7] = 0x01;
        break;
    }
    case 0x90:
        r[6] = 1; r[7] = f->film_in ? 0x30 : 0x00;                           /* one record; buf[3] = sensor nibble */
        break;
    default: break;
    }
    r[0] = 1; r[1] = (uint8_t)(cnt + 2); r[2] = addr; r[3] = status;
    f->resp_n = (size_t)cnt + 4;
}

static pk_status fk_out(pk_transport *t, uint8_t ep, const uint8_t *d, size_t n, unsigned to) {
    (void)ep; (void)to;
    fk *f = (fk *)t->impl;
    pk_status st = PK_OK;
    pthread_mutex_lock(&f->mu);
    f->packets++;
    gone_check(f, &st);
    if (st == PK_OK && n >= 5) {
        uint8_t type = d[0], addr = d[2], reg = d[4];
        if (type == 1) answer_read(f, addr, reg, d[3]);
        else {
            if (type == 2 && reg == 0x06 && n >= 7 && d[5] == 0) { if (f->pending == d[6] || d[6] == 0xFF) f->pending = 0; }
            if (type == 2 && reg == 0x80) { int en = n >= 6 ? (d[5] & 1) : 0; if (en && !f->lamp_en) f->reads_since_lamp = 0; f->lamp_en = en; if (!en) f->stable_sent = 0; }
            if (type == 2 && reg == 0x91) { f->dx_active = 1; f->in_sent = f->out_sent = 0; f->film_in = 0; }
            if (type == 4 && reg == 0x92) f->dx_active = 0;
            if (type == 4 && (reg == 0xA0 || reg == 0xA1) && !f->motor_run) { f->motor_run = 1; f->reads_since_motor = 0; f->film_in = 0; }
            if (type == 4 && reg == 0xA2) f->motor_run = 0;
            f->resp[0] = 7; f->resp[1] = 2; f->resp[2] = addr; f->resp[3] = 0; f->resp_n = 4;
        }
    } else if (st == PK_OK && n >= 3 && d[0] == 3) {
        f->resp[0] = 3; f->resp[1] = 4; f->resp[2] = d[2]; f->resp[3] = 0; f->resp[4] = f->resp[5] = 0; f->resp_n = 6;
    }
    pthread_mutex_unlock(&f->mu);
    return st;
}

static pk_status fk_in(pk_transport *t, uint8_t ep, uint8_t *b, size_t cap, size_t *got, unsigned to) {
    (void)ep; (void)to;
    fk *f = (fk *)t->impl;
    pk_status st = PK_OK;
    pthread_mutex_lock(&f->mu);
    gone_check(f, &st);
    *got = 0;
    if (st == PK_OK) {
        if (f->resp_n == 0) st = PK_E_TIMEOUT;
        else { size_t n = f->resp_n < cap ? f->resp_n : cap; memcpy(b, f->resp, n); *got = n; f->resp_n = 0; }
    }
    pthread_mutex_unlock(&f->mu);
    return st;
}

/* The unloaded FX2: A0 writes internal RAM below 0x4000 (held only) and CPUCS; A3 acts on xdata only while Kodak's stage-1 runs, which the
 * fake decides the way the real chip would: the bytes written so far hash to the pinned stage-1 at the moment of the release. */
static pk_status fx2_ctl(fk *f, uint8_t rt, uint8_t req, uint16_t val, uint8_t *data, size_t len) {
    int in = (rt & 0x80) != 0;
    if (req == 0xA0) {
        if (val == 0xE600 && !in && len == 1) {
            if (data[0] & 1) { f->held = 1; f->s1_run = 0; return PK_OK; }
            if (!f->held) return PK_OK;
            f->held = 0;
            pk_image *img = (pk_image *)calloc(1, sizeof *img);
            if (!img) return PK_E_NOMEM;
            for (unsigned a = 0; a < 0x4000; a++)
                if (f->wr[a >> 3] >> (a & 7) & 1) { img->mem[a] = f->m[a]; img->used[a >> 3] = (uint8_t)(img->used[a >> 3] | (1u << (a & 7))); }
            char hex[65];
            pkl_image_canon_hex(img, hex);
            free(img);
            if (strcmp(hex, PKL_STAGE1_CANON_SHA256) == 0) f->s1_run = 1;
            else if (f->a3_bytes) f->fx_mode = 2;   /* the firmware starts: it will re-enumerate */
            return PK_OK;
        }
        if ((unsigned)val + len > 0x4000 || (!in && !f->held)) return PK_E_IO;
        if (in) memcpy(data, f->m + val, len);
        else for (size_t i = 0; i < len; i++) { f->m[val + i] = data[i]; f->wr[(val + i) >> 3] = (uint8_t)(f->wr[(val + i) >> 3] | (1u << ((val + i) & 7))); }
        return PK_OK;
    }
    if (req == 0xA3) {
        if (!f->s1_run) return PK_E_TIMEOUT;   /* nothing services it */
        if ((unsigned)val + len > 0xE000) return PK_E_IO;
        if (in) memcpy(data, f->m + val, len);
        else { memcpy(f->m + val, data, len); f->a3_bytes += (unsigned)len; }
        return PK_OK;
    }
    return PK_E_UNSUPPORTED;
}

static pk_status fk_ctl(pk_transport *t, uint8_t rt, uint8_t req, uint16_t val, uint16_t idx, uint8_t *data, size_t len, unsigned to) {
    (void)to;
    fk *f = (fk *)t->impl;
    pk_status st = PK_OK;
    pthread_mutex_lock(&f->mu);
    f->packets++;
    gone_check(f, &st);
    if (st == PK_OK && f->fx_mode) st = fx2_ctl(f, rt, req, val, data, len);
    else if (st == PK_OK) {
        (void)idx;
        if (rt == 0x40 && req == 0xA4) f->a4 = (uint8_t)val;
        else if (rt == 0xC0 && req == 0xA9 && f->a4 == 0xA5 && (size_t)val + len <= sizeof f->eeprom) memcpy(data, f->eeprom + val, len);
        else if (rt == 0xC0 && req == 0xA9 && f->a4 == 0xA3 && len == 8) { static const uint8_t p[8] = { 0xC0, 0x05, 0x0F, 0x35, 0xF2, 0x07, 0xAA, 0x04 }; memcpy(data, p, 8); }
        else st = PK_E_UNSUPPORTED;
    }
    pthread_mutex_unlock(&f->mu);
    return st;
}

static pk_status fk_stream(pk_transport *t, uint8_t *b, size_t cap, size_t *got, unsigned to) { (void)t; (void)b; (void)cap; (void)to; *got = 0; return PK_E_TIMEOUT; }
static pk_status fk_reopen(pk_transport *t, uint16_t v, uint16_t p, unsigned w) {
    (void)w;
    fk *f = (fk *)t->impl;
    if (f->fx_mode != 2 || v != 0x0F05 || p != 0xF135) return PK_E_TIMEOUT;   /* only a started firmware re-enumerates, as 0F05:F135 */
    f->fx_mode = 0;
    return PK_OK;
}
static void fk_close(pk_transport *t) { fk *f = (fk *)t->impl; if (f) { pthread_mutex_destroy(&f->mu); free(f); } t->impl = NULL; }
static const pk_transport_ops FK_OPS = { fk_out, fk_in, fk_ctl, fk_stream, fk_reopen, fk_close };

pk_status cli_fake_open(const cli_opts *o, pk_transport **raw) {
    fk *f = (fk *)calloc(1, sizeof *f);
    pk_transport *t = (pk_transport *)calloc(1, sizeof *t);
    if (!f || !t) { free(f); free(t); return PK_E_NOMEM; }
    pthread_mutex_init(&f->mu, NULL);
    build_eeprom(f, o->fake_damage);
    f->unplug_after = o->fake_unplug;
    f->fx_mode = o->fake_unloaded ? 1 : 0;
    t->ops = &FK_OPS;
    t->impl = f;
    *raw = t;
    return PK_OK;
}
#endif
