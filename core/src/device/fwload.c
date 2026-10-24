#define _POSIX_C_SOURCE 200809L
/* Firmware load by Kodak's own sequence (ruling S-R25; hw1-load-debug.md sec 2 and 6; RE 29 sec 7.5).
 *
 * The FX2 boot ROM's 0xA0 request writes only internal RAM below 0x4000, and Kodak's own driver (F235Ldr.sys, FX35Loader.c
 * Ezusb_DownloadIntelHex) loads Pakon firmware like this, which is the only loader proven on the owner's F-135 Plus:
 *   1. hold the 8051;  2. send Kodak's stage-1 records by 0xA0;  3. release;  4. wait 500 ms (v1's catch_bootloader.py);
 *   5. send every firmware record ABOVE 0x1B3F by 0xA3 (the running stage-1 MOVXes EP0BUF to xdata[wValue+i]), 16 bytes at most
 *      per transfer, in file order;  6. hold;  7. send the records at or below 0x1B3F by 0xA0, in file order.
 * Deliberate additions to Kodak's sequence, all READ-ONLY: before the hold of step 6 every A3-written byte is read back by A3 IN
 * (the stage-1 is still running), and while held every byte below 0x4000 is read back by A0 IN. On any mismatch the 8051 stays
 * held and an error is returned. Deliberate omissions: Kodak's 0x7F92 CPUCS write and its A4 0xA1 / A9 under the stage-1 (the
 * personality is read on the loaded device, as before).
 *
 * The stage-1 is Kodak's: it is cut out of the owner's hash-verified F235Ldr.sys at load time (file offset 0x1700, 360 records
 * of 22 bytes, then the EOF record) and checked against a pinned canonical SHA-256. No Kodak byte is committed to this repository.
 *
 * The guard (link/guard.c) vets every A0 and A3 byte against the library-owned images; this loader follows its phases exactly.
 * The previous stage-1 copier path (firmware/stage1) is gone from the load: nothing here reaches it. */
#include "pakon/device.h"
#include "device/fwload.h"
#include "device/models.h"
#include "link/link.h"
#include "util/util.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define XFER_MS 5000        /* per control transfer (v1) */

static void sleep_ms(unsigned ms) {
    if (!ms) return;
    struct timespec ts = { (time_t)(ms / 1000u), (long)(ms % 1000u) * 1000000L };
    while (nanosleep(&ts, &ts) != 0) {}
}

static pk_status fail_t(pk_error *e, pk_transport *t, pk_status s, const char *what) {
    pk_error_set(e, s, "fwload", "%s: %s%s%s", what, pk_status_str(s), t && t->diag[0] ? ": " : "", t && t->diag[0] ? t->diag : "");
    return s;
}

static pk_status a0_write(pk_transport *t, unsigned addr, const uint8_t *d, size_t n, pk_error *e, const char *what) {
    uint8_t buf[PKFW_REC_MAX];
    if (n > sizeof buf) return PK_E_ARG;
    memcpy(buf, d, n);
    pk_status s = pk_t_control(t, 0x40, 0xA0, (uint16_t)addr, 0, buf, n, XFER_MS);
    return s == PK_OK ? PK_OK : fail_t(e, t, s, what);
}

static pk_status cpucs(pk_transport *t, int hold, pk_error *e) {
    uint8_t v = hold ? 0x01 : 0x00;
    return a0_write(t, PKFW_CPUCS, &v, 1, e, hold ? "hold the 8051 (CPUCS 0x01)" : "release the 8051 (CPUCS 0x00)");
}

static int has_used(const pk_image *img, unsigned lo, unsigned hi) {
    for (unsigned a = lo; a < hi; a++) if (PK_IMAGE_USED(img, a)) return 1;
    return 0;
}

pk_status pk_device_personality(pk_transport *t, uint16_t *vid_out, uint16_t *pid_out, uint16_t *did_out) {
    if (!t || !vid_out || !pid_out) return PK_E_ARG;
    uint8_t b[8];
    pk_status s = pk_t_control(t, 0x40, 0xA4, PK_PERSONALITY_SELECT_WVALUE, 0, NULL, 0, 2000);
    if (s != PK_OK) return s;
    s = pk_t_control(t, 0xC0, 0xA9, 0, 0, b, sizeof b, 2000);
    if (s != PK_OK) return s;
    *vid_out = (uint16_t)(b[1] | b[2] << 8);   /* [0] is the EEPROM-type byte: never used */
    *pid_out = (uint16_t)(b[3] | b[4] << 8);
    if (did_out) *did_out = (uint16_t)(b[5] | b[6] << 8);
    return PK_OK;
}

/* Kodak's stage-1 out of F235Ldr.sys: records of 22 bytes at 0x1700 (len, pad, addr LE, type, 16 data bytes, pad), 360 data records
 * then the EOF record (len 0, type 1) at 0x35F0, ending at 0x3606. The caller pins the result by canonical hash. */
pk_status pkfw_stage1_from_ldr(const uint8_t *sys, size_t n, pk_image **img_out, pk_ihex_rec **recs_out, size_t *nrecs_out) {
    if (img_out) *img_out = NULL;
    if (recs_out) *recs_out = NULL;
    if (nrecs_out) *nrecs_out = 0;
    if (!sys || !img_out || !recs_out || !nrecs_out) return PK_E_ARG;
    if (n < PKFW_LDR_OFF + (PKFW_LDR_NREC + 1) * PKFW_LDR_STRIDE) return PK_E_CORRUPT;
    pk_image *img = (pk_image *)calloc(1, sizeof *img);
    pk_ihex_rec *recs = (pk_ihex_rec *)calloc(PKFW_LDR_NREC, sizeof *recs);
    if (!img || !recs) { free(img); free(recs); return PK_E_NOMEM; }
    uint32_t lo = 0xFFFFFFFFu, hi = 0;
    for (unsigned i = 0; i < PKFW_LDR_NREC; i++) {
        const uint8_t *r = sys + PKFW_LDR_OFF + (size_t)i * PKFW_LDR_STRIDE;
        unsigned len = r[0], addr = (unsigned)r[2] | (unsigned)r[3] << 8;
        if (len < 1 || len > 16 || r[4] != 0 || addr + len > 0x10000u) goto bad;
        recs[i].addr = (uint16_t)addr;
        recs[i].len = (uint8_t)len;
        memcpy(recs[i].data, r + 5, len);
        for (unsigned k = 0; k < len; k++) {
            unsigned a = addr + k;
            if (PK_IMAGE_USED(img, a)) goto bad;   /* a byte set twice */
            img->mem[a] = r[5 + k];
            img->used[a >> 3] = (uint8_t)(img->used[a >> 3] | (1u << (a & 7)));
            img->nbytes++;
            if (a < lo) lo = a;
            if (a > hi) hi = a;
        }
    }
    const uint8_t *eof = sys + PKFW_LDR_OFF + (size_t)PKFW_LDR_NREC * PKFW_LDR_STRIDE;
    if (eof[0] != 0 || eof[4] != 1) goto bad;
    img->min_addr = lo;
    img->max_addr = hi;
    *img_out = img; *recs_out = recs; *nrecs_out = PKFW_LDR_NREC;
    return PK_OK;
bad:
    free(img); free(recs);
    return PK_E_CORRUPT;
}

typedef struct {
    pk_image *s1, *fw;
    pk_ihex_rec *s1r, *fwr;
    size_t ns1, nfw;
} fw_set;

static void fw_set_free(fw_set *f) { pk_image_free(f->s1); pk_image_free(f->fw); free(f->s1r); free(f->fwr); memset(f, 0, sizeof *f); }

/* Reads A3 IN / A0 IN back and compares. Counts every differing byte; stops only on a transfer error. */
typedef struct { size_t bad; unsigned first_addr; uint8_t first_got, first_want; } rb_result;
static pk_status read_back(pk_transport *t, const pk_ihex_rec *r, size_t n, int ext, rb_result *res, pk_error *e) {
    memset(res, 0, sizeof *res);
    for (size_t i = 0; i < n; i++) {
        unsigned a = r[i].addr, len = r[i].len;
        if (ext ? a <= PKFW_A3_MIN_EXCL : a >= PKFW_EXT_START) continue;
        if (!ext && a + len > PKFW_EXT_START) len = PKFW_EXT_START - a;   /* A0 reads internal RAM only */
        /* The FX2 boot ROM answers an A0 IN at an odd address with the bytes from the even address below (HW-1 2026-10-19:
         * every odd-address read was shifted by one, every even one exact), so A0 reads start on an even address. */
        unsigned lead = (!ext && (a & 1u)) ? 1u : 0u;
        uint8_t raw[17];
        pk_status s = pk_t_control(t, 0xC0, ext ? 0xA3 : 0xA0, (uint16_t)(a - lead), 0, raw, len + lead, XFER_MS);
        if (s != PK_OK) return fail_t(e, t, s, ext ? "read back external RAM (A3 IN)" : "read back internal RAM (A0 IN)");
        const uint8_t *got = raw + lead;
        for (unsigned k = 0; k < len; k++)
            if (got[k] != r[i].data[k]) {
                if (!res->bad) { res->first_addr = a + k; res->first_got = got[k]; res->first_want = r[i].data[k]; }
                res->bad++;
            }
    }
    return PK_OK;
}

static pk_status load_in_window(pk_transport *t, const fw_set *f, const pk_fw_opts *o, pk_error *e) {
    pk_status s;
    rb_result rb;
    /* 1-3: hold, Kodak's stage-1 records by A0, release; 4: wait */
    if ((s = cpucs(t, 1, e)) != PK_OK) return s;
    sleep_ms(o->reset_hold_ms);
    for (size_t i = 0; i < f->ns1; i++)
        if ((s = a0_write(t, f->s1r[i].addr, f->s1r[i].data, f->s1r[i].len, e, "write Kodak's stage-1 loader (A0)")) != PK_OK) return s;
    if ((s = cpucs(t, 0, e)) != PK_OK) return s;
    sleep_ms(o->s1_wait_ms);
    /* 5: every record above 0x1B3F by A3, in file order, the stage-1 running */
    for (size_t i = 0; i < f->nfw; i++) {
        const pk_ihex_rec *r = &f->fwr[i];
        if (r->addr <= PKFW_A3_MIN_EXCL) continue;
        uint8_t buf[16];
        memcpy(buf, r->data, r->len);
        s = pk_t_control(t, 0x40, 0xA3, r->addr, 0, buf, r->len, XFER_MS);
        if (s != PK_OK) {
            s = fail_t(e, t, s, "write firmware by the stage-1 (A3)");
            (void)cpucs(t, 1, NULL);   /* best effort: do not leave Kodak's stage-1 (and its EEPROM handlers) running (S-R25 review M1) */
            return s;
        }
    }
    /* 8: read back all of it, still under the stage-1 */
    s = read_back(t, f->fwr, f->nfw, 1, &rb, e);
    if (s != PK_OK) { (void)cpucs(t, 1, NULL); return s; }   /* best effort hold, as above */
    /* 6: hold (also what "stay held" means after a bad read-back) */
    pk_status h = cpucs(t, 1, e);
    if (h != PK_OK) return h;
    sleep_ms(o->reset_hold_ms);
    if (rb.bad) {
        pk_error_set(e, PK_E_DEVICE, "fwload", "A3 read-back differs in %zu byte(s), first at 0x%04X: read 0x%02X, wanted 0x%02X; the 8051 is held and not released",
                     rb.bad, rb.first_addr, rb.first_got, rb.first_want);
        return PK_E_DEVICE;
    }
    /* 7: the records at or below 0x1B3F by A0, in file order */
    for (size_t i = 0; i < f->nfw; i++) {
        const pk_ihex_rec *r = &f->fwr[i];
        if (r->addr > PKFW_A3_MIN_EXCL) continue;
        if ((s = a0_write(t, r->addr, r->data, r->len, e, "write firmware (A0, internal RAM)")) != PK_OK) return s;
    }
    /* 9: read back every internal byte while held; 10: a mismatch stays held */
    if ((s = read_back(t, f->fwr, f->nfw, 0, &rb, e)) != PK_OK) return s;
    if (rb.bad) {
        pk_error_set(e, PK_E_DEVICE, "fwload", "A0 read-back differs in %zu byte(s), first at 0x%04X: read 0x%02X, wanted 0x%02X; the 8051 is held and not released",
                     rb.bad, rb.first_addr, rb.first_got, rb.first_want);
        return PK_E_DEVICE;
    }
    /* 11: the final hold and release */
    if ((s = cpucs(t, 1, e)) != PK_OK) return s;
    sleep_ms(o->reset_hold_ms);
    return cpucs(t, 0, e);
}

typedef struct { pk_vendor_item item; uint16_t rev; const char *canon; } fw_pin;   /* rev: the unloaded REV the image belongs to */
static const fw_pin FW_PINS[] = {
    { PKV_PAKON7_HEX_2006, 0xAA07, "d2d69b61b6d7637d5f6ef69376f026bd13a3065d68f7ba8eb5515942eb2283d8" },   /* F-135 / Plus, 10355 bytes, max 0x47AC (PSI 3.0.4.27) */
    { PKV_PAKON7_HEX_2004, 0xAA07, "9e512f77108b810cd8242aaa71920a1ddff292057ae7e58277c2677b54cc6691" },   /* F-135 / Plus, 10326 bytes, max 0x478F: the diagnostic override only */
    { PKV_PAKON5_HEX, 0xAA05, "73c27e0b6b7ebf99cbcc831a05e050c27702d7d5f0d6a024c6fbd5bcb1bfd656" },       /* F-235, 10345 bytes */
    { PKV_PAKON8_HEX, 0xAA08, "c0db8736ce44ab2a0fbfa2a2f9137cec9513fcb6f8772ae7cc8c9982be9e679a" },       /* F-335, 10251 bytes */
};

/* The library-owned images for one load: Kodak's stage-1 from the store's F235Ldr.sys and the model's firmware, each parsed from
 * hash-verified store bytes and pinned by canonical hash before any transfer. */
static pk_status own_images(const pk_model *m, pk_vendor *vendor, const pk_fw_opts *o, fw_set *f, pk_error *err) {
    char hex[65];
    pk_vendor_item item = m->firmware;
    if (o->image_2004) {
        if (item != PKV_PAKON7_HEX_2006) { pk_error_set(err, PK_E_UNSUPPORTED, "fwload", "the 2004 image is a diagnostic for the F-135 / Plus only"); return PK_E_UNSUPPORTED; }
        item = PKV_PAKON7_HEX_2004;
    }
    const char *pin = NULL;
    for (size_t i = 0; i < sizeof FW_PINS / sizeof FW_PINS[0]; i++)
        if (FW_PINS[i].item == item && FW_PINS[i].rev == pkm_boot_rev(m)) pin = FW_PINS[i].canon;   /* a wrong table row finds no pin */
    if (!pin) { pk_error_set(err, PK_E_UNSUPPORTED, "fwload", "no pinned firmware image for %s", m->name); return PK_E_UNSUPPORTED; }
    /* Kodak's stage-1 */
    pk_vendor_item ldr = pk_vendor_has(vendor, PKV_F235_F235LDR_SYS) ? PKV_F235_F235LDR_SYS : PKV_F335_F235LDR_SYS;   /* same file, same SHA-256 */
    pk_bytes b = { NULL, 0 };
    pk_status s = pk_vendor_file(vendor, ldr, &b);   /* re-reads and re-verifies the manifest SHA-256 (785bd29f...) */
    if (s != PK_OK) { pk_error_set(err, s, "fwload", "Kodak's F235Ldr.sys (the stage-1 loader) from the vendor store: %s", pk_status_str(s)); return s; }
    s = pkfw_stage1_from_ldr(b.data, b.len, &f->s1, &f->s1r, &f->ns1);
    free(b.data);
    if (s == PK_OK) { pkl_image_canon_hex(f->s1, hex); if (strcmp(hex, PKL_STAGE1_CANON_SHA256) != 0) s = PK_E_CORRUPT; }
    if (s != PK_OK) { pk_error_set(err, PK_E_CORRUPT, "fwload", "the stage-1 loader in F235Ldr.sys is not the pinned image"); fw_set_free(f); return PK_E_CORRUPT; }
    /* the firmware */
    b.data = NULL; b.len = 0;
    s = pk_vendor_file(vendor, item, &b);
    if (s != PK_OK) { pk_error_set(err, s, "fwload", "firmware for %s from the vendor store: %s", m->name, pk_status_str(s)); fw_set_free(f); return s; }
    s = pk_ihex_parse_records(b.data, b.len, &f->fw, &f->fwr, &f->nfw);
    free(b.data);
    if (s == PK_OK) { pkl_image_canon_hex(f->fw, hex); if (strcmp(hex, pin) != 0) s = PK_E_CORRUPT; }
    if (s != PK_OK) {
        pk_error_set(err, PK_E_CORRUPT, "fwload", "firmware for %s is not the pinned image", m->name);
        fw_set_free(f);
        return PK_E_CORRUPT;
    }
    return PK_OK;
}

pk_status pk_device_load_firmware(pk_transport *t, const pk_model *usb_model, pk_vendor *vendor, const pk_fw_opts *opts,
                                  pk_error *err) {
    pk_fw_opts o = { 100, 10000, 500, 0 };
    if (opts) { o = *opts; if (o.s1_wait_ms == 0) o.s1_wait_ms = 500; }   /* the 500 ms after the stage-1 release is never skipped */
    if (!t || !usb_model || !vendor) return PK_E_ARG;
    uint16_t lvid, lpid;
    pk_status s = pkm_loaded_identity(usb_model, &lvid, &lpid);
    if (s != PK_OK) return s;
    fw_set f;
    memset(&f, 0, sizeof f);
    s = own_images(usb_model, vendor, &o, &f, err);   /* before any transfer */
    if (s != PK_OK) return s;
    /* shape checks the guard would otherwise only meet mid-sequence: no firmware byte at or above 0xE000, internal bytes exist (the
     * reset vector), and no record straddles 0x1B3F (Kodak decides A0 or A3 by a record's address alone) */
    int shape = !has_used(f.fw, PKFW_EXT_END, 0x10000) && has_used(f.fw, 0, PKFW_A3_MIN_EXCL + 1u);
    for (size_t i = 0; shape && i < f.nfw; i++)
        if (f.fwr[i].addr <= PKFW_A3_MIN_EXCL && f.fwr[i].addr + f.fwr[i].len - 1u > PKFW_A3_MIN_EXCL) shape = 0;
    if (!shape) {
        pk_error_set(err, PK_E_FORMAT, "fwload", "image shape: firmware must have internal bytes, none at 0xE000 or above, and no record across 0x1B3F");
        s = PK_E_FORMAT;
        goto done;
    }
    s = pkl_guard_load_begin(t, f.s1, f.fw);   /* every A0 and A3 below is vetted against these library-owned images */
    if (s != PK_OK) { s = fail_t(err, t, s, "open the guard's load window"); goto done; }
    s = load_in_window(t, &f, &o, err);
    pkl_guard_load_end(t);                  /* on every exit path */
    if (s != PK_OK) goto done;
    /* 5. the loaded device re-enumerates: wait for it (bounded) */
    s = pk_t_reopen(t, lvid, lpid, o.reenum_wait_ms);
    if (s != PK_OK) { s = fail_t(err, t, s, "reopen under the loaded identity"); goto done; }
    /* 6. only Pakon's DR_VendorCmnd services A4/A9, so the boot-EEPROM personality is read on the loaded device. Bytes 1..6
     * (VID, PID, device ID) must equal the unloaded identity; the USB identity decides and a disagreement is refused. */
    uint16_t pv = 0, pp = 0, pd = 0;
    s = pk_device_personality(t, &pv, &pp, &pd);
    if (s != PK_OK) {
        pk_error_set(err, PK_E_LOADED_UNVERIFIED, "fwload", "firmware loaded and device re-enumerated, but the personality read failed (%s)", pk_status_str(s));
        s = PK_E_LOADED_UNVERIFIED;
    } else if (pv != PKFW_BOOT_VID || pp != PKFW_BOOT_PID || pd != pkm_boot_rev(usb_model)) {
        pk_error_set(err, PK_E_FIRMWARE_MISMATCH, "fwload", "boot EEPROM says %04X:%04X rev %04X, the unloaded device enumerated as %04X:%04X rev %04X", pv, pp, pd,
                     PKFW_BOOT_VID, PKFW_BOOT_PID, pkm_boot_rev(usb_model));
        s = PK_E_FIRMWARE_MISMATCH;
    }
done:
    fw_set_free(&f);
    return s;
}
