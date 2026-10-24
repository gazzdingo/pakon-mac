#define _POSIX_C_SOURCE 200809L
/* pakon decode <roll.raw> -o <dir> [--colour] [--film P/G] [--home DIR]
 *
 * Decodes a saved roll (roll.raw + roll.json + the calibration store under --home) through the library's roll hand-off (pakon/roll.h) and writes, per frame, the
 * linear 16-bit TIFF of pk_colour_export_linear16 (C41: this file writes the TIFF itself) and a frames.json. With --colour it also writes the finished picture:
 * PSI's default render (AnselOrientation 270, picture rotation 0, no user adjustments) through the same colour library calls tools/pakon_render.c uses, as an 8-bit
 * TIFF. There is no second colour pipeline here. */
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "cli.h"
#include "pakon/colour.h"
#include "pakon/roll.h"
#include "pakon/vendor.h"
#include "util/util.h"

#ifndef VENDOR_ROOT
#define VENDOR_ROOT ""
#endif
#ifndef DERIVED_ROOT
#define DERIVED_ROOT ""
#endif

static void put16(unsigned char *p, unsigned v) { p[0] = (unsigned char)v; p[1] = (unsigned char)(v >> 8); }
static void put32(unsigned char *p, unsigned long v) { put16(p, (unsigned)(v & 0xffff)); put16(p + 2, (unsigned)(v >> 16)); }

/* An uncompressed, interleaved RGB TIFF, little-endian, one strip. bits = 8 or 16. */
static int write_tiff(const char *path, int w, int h, int bits, const void *pix) {
    const size_t nsamp = (size_t)w * (size_t)h * 3, bytes = nsamp * (size_t)(bits / 8);
    enum { NTAGS = 11 };
    const unsigned long ifd = 8, bps_off = ifd + 2 + NTAGS * 12 + 4, data = bps_off + 6;
    if (bytes > 0x7fffffffUL - data) return 0;
    unsigned char hdr[8 + 2 + NTAGS * 12 + 4 + 6];
    memset(hdr, 0, sizeof hdr);
    hdr[0] = 'I'; hdr[1] = 'I'; put16(hdr + 2, 42); put32(hdr + 4, ifd);
    put16(hdr + ifd, NTAGS);
    unsigned char *e = hdr + ifd + 2;
    const struct { unsigned tag, type; unsigned long count, value; } t[NTAGS] = {
        { 256, 4, 1, (unsigned long)w }, { 257, 4, 1, (unsigned long)h }, { 258, 3, 3, bps_off }, { 259, 3, 1, 1 }, { 262, 3, 1, 2 },
        { 273, 4, 1, data }, { 277, 3, 1, 3 }, { 278, 4, 1, (unsigned long)h }, { 279, 4, 1, (unsigned long)bytes }, { 284, 3, 1, 1 }, { 339, 3, 1, 1 } };
    for (int i = 0; i < NTAGS; i++, e += 12) {
        put16(e, t[i].tag); put16(e + 2, t[i].type); put32(e + 4, t[i].count);
        if (t[i].type == 3 && t[i].count == 1) put16(e + 8, (unsigned)t[i].value); else put32(e + 8, t[i].value);
    }
    for (int i = 0; i < 3; i++) put16(hdr + bps_off + 2 * i, (unsigned)bits);
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    int ok = fwrite(hdr, 1, sizeof hdr, f) == sizeof hdr;
    if (bits == 8) ok = ok && fwrite(pix, 1, bytes, f) == bytes;
    else {
        const uint16_t *s = (const uint16_t *)pix;
        unsigned char buf[8192];
        for (size_t i = 0; ok && i < nsamp; i += 4096) {
            const size_t m = nsamp - i < 4096 ? nsamp - i : 4096;
            for (size_t j = 0; j < m; j++) put16(buf + 2 * j, s[i + j]);
            ok = fwrite(buf, 2, m, f) == m;
        }
    }
    return fclose(f) == 0 && ok;
}

static int dir_exists(const char *p) { return p && *p && access(p, R_OK) == 0; }

int cli_cmd_decode(cli_opts *o, int npos, const char **pos) {
    if (npos != 2 || !o->out) {
        fputs("usage: pakon decode <roll.raw> -o <folder> [--colour [--ice]] [--film PRODUCT/SPECIFIER] [--home DIR]\n"
              "  Writes one linear 16-bit TIFF per frame and frames.json. With --colour also a finished colour picture per frame.\n"
              "  --home is the folder that holds the calibration store the roll was scanned with.\n", stderr);
        return 2;
    }
    int film_p = -2, film_g = -2;
    if (o->film && sscanf(o->film, "%d/%d", &film_p, &film_g) != 2) { fputs("pakon: --film needs PRODUCT/SPECIFIER, for example 4/4\n", stderr); return 2; }
    const char *raw = pos[1], *out = o->out;
    char home[1024];
    if (cli_home(o, home, sizeof home)) { cli_say("Cannot find your home folder; use --home."); return 1; }

    pk_status st = pku_mkdirs(out);
    if (st != PK_OK) { cli_report_status("The output folder could not be made", st, NULL); return 1; }

    pk_roll *r = NULL;
    (void)pk_lores_weights_load(NULL, DERIVED_ROOT);
    if ((st = pk_roll_open(raw, home, &r)) != PK_OK) {
        cli_report_status("The roll could not be opened", st, NULL);
        cli_say("A roll needs its .json file next to the .raw file, and the calibration it was scanned with under %s (use --home to point elsewhere).", home);
        return 1;
    }

    pk_colour *c = NULL;
    if (o->colour) {
        char vendor[1200], derived[1200];
        const char *ev = getenv("PAKON_VENDOR_ROOT"), *ed = getenv("PAKON_DERIVED_ROOT");
        snprintf(vendor, sizeof vendor, "%s/vendor/3.0.4.27/F-X35 COM SERVER", home);
        if (ev && *ev) snprintf(vendor, sizeof vendor, "%s", ev);
        else if (!dir_exists(vendor)) snprintf(vendor, sizeof vendor, "%s", VENDOR_ROOT);
        snprintf(derived, sizeof derived, "%s", DERIVED_ROOT);
        if (ed && *ed) snprintf(derived, sizeof derived, "%s", ed);
        else if (!dir_exists(derived)) snprintf(derived, sizeof derived, "%s/vendor/derived", home);
        pk_load_error le;
        memset(&le, 0, sizeof le);
        pk_colour_options co = { sizeof co, 0 };
        if ((st = pk_colour_open_opts(vendor, derived, &co, &le, &c)) != PK_OK) {
            cli_report_status("The colour data could not be loaded", st, NULL);
            cli_detail("vendor %s, derived %s, file %s (%s)", vendor, derived, le.path, le.reason);
            cli_say("Run  pakon vendor import <folder with the Kodak install files>  first, or leave --colour off to get the linear TIFFs only.");
            pk_roll_close(r);
            return 1;
        }
    }

    char path[4400];
    snprintf(path, sizeof path, "%s/frames.json", out);
    FILE *fj = fopen(path, "w");
    if (!fj) { cli_say("Cannot write %s: %s", path, strerror(errno)); pk_colour_close(c); pk_roll_close(r); return 1; }
    fprintf(fj, "{\n \"roll\": \"%s\", \"dpi_base\": %d, \"complete\": %s, \"colour\": %s,\n \"frames\": [", raw, pk_roll_dpi_base(r), pk_roll_complete(r) ? "true" : "false", o->colour ? "true" : "false");

    int rc = 0, frame_no = 0, first = 1, nwritten = 0;
    const int nstrips = pk_roll_strip_count(r);
    for (int s = 0; s < nstrips && !g_cli_intr; s++) {
        if (film_p != -2 && (st = pk_roll_set_manual_film(r, s, film_p, film_g)) != PK_OK) {
            cli_report_status("That film code is not accepted", st, NULL); rc = 1; break; }
        pk_roll_input in;
        pk_roll_input_storage *keep = NULL;
        if ((st = pk_roll_colour_input(r, s, &in, &keep)) != PK_OK) {
            cli_report_status("The strip could not be decoded", st, NULL);
            if (st == PK_E_NOT_FOUND) cli_say("The calibration or the scanner's saved calibration chip is missing from %s (use --home).", home);
            rc = 1; continue;
        }
        if (in.n_frames < 1) { cli_say("Strip %d: no frames found.", s + 1); pk_roll_input_storage_free(keep); continue; }
        pk_dx_strip dx;
        pk_roll_framing_info fi;
        memset(&dx, 0, sizeof dx);
        memset(&fi, 0, sizeof fi);
        pk_roll_dx(r, s, &dx);
        pk_roll_framing_info_get(r, s, &fi);
        if (o->colour && !strcmp(dx.dx_source, "none"))
            cli_say("Strip %d: no film code was read, so the colour library's default film is used.", s + 1);
        else if (!strcmp(dx.dx_source, "manual")) cli_say("Strip %d: using the film set by hand (%d/%d).", s + 1, in.product_code, in.gen_code);

        pk_roll_result *res = NULL;
        if (c && (st = pk_colour_analyse_roll(c, &in, &res)) != PK_OK) {
            cli_report_status("The colour analysis failed; writing the linear TIFFs only", st, NULL);
            res = NULL; rc = 1;
        }
        for (int k = 0; k < in.n_frames && !g_cli_intr; k++) {
            frame_no++;
            char lin[64], col[64], lp[4400], cp[4400];
            snprintf(lin, sizeof lin, "frame_%02d_linear16.tif", frame_no);
            snprintf(col, sizeof col, "frame_%02d.tif", frame_no);
            snprintf(lp, sizeof lp, "%s/%s", out, lin);
            snprintf(cp, sizeof cp, "%s/%s", out, col);
            int exact = -1, skipped = -1, wrote_lin = 0, wrote_col = 0;
            pk_status fs = PK_OK;
            if ((st = pk_roll_colour_frame(r, s, k, &in, keep)) != PK_OK) {
                cli_report_status("A frame could not be read from the roll", st, NULL); rc = 1; fs = st; goto record;
            }
            {
                const size_t n = (size_t)in.frames[k].width * (size_t)in.frames[k].height;
                uint16_t *buf = malloc(n * 3 * sizeof *buf);
                pk_image_u16 im = { 0, 0, buf };
                if (buf && (fs = pk_colour_export_linear16(&in, k, &im)) == PK_OK && write_tiff(lp, im.width, im.height, 16, buf)) wrote_lin = 1;
                else { if (fs == PK_OK) fs = buf ? PK_E_IO : PK_E_NOMEM; cli_report_status("The linear picture could not be written", fs, NULL); rc = 1; }
                free(buf);
            }
            if (res) {
                pk_roll_result_exact(res, k, &exact);
                pk_roll_result_skipped(res, k, &skipped);
                fs = pk_roll_result_status(res, k);
                if (fs == PK_OK) {
                    const size_t n = (size_t)in.frames[k].width * (size_t)in.frames[k].height;
                    uint8_t *rgb = malloc(n * 3);
                    pk_image_u8 im = { 0, 0, rgb };
                    pk_status rs = rgb ? pk_colour_render_saved(c, &in, res, k, NULL, PK_ANSEL_ORIENTATION_PSI, 0, &im) : PK_E_NOMEM;
                    if (rs == PK_OK && write_tiff(cp, im.width, im.height, 8, rgb)) wrote_col = 1;
                    else { if (rs == PK_OK) rs = PK_E_IO; cli_report_status("The colour picture could not be made", rs, NULL); fs = rs; rc = 1; }
                    if (o->ice && rs == PK_OK && in.frames[k].linear14[PK_PLANE_IR]) {          /* the same frame again with TLB's save bit 0x80 (RE 45 sec 4) */
                        char ip[4400];
                        snprintf(ip, sizeof ip, "%s/frame_%02d_ice.tif", out, frame_no);
                        in.ice = 1;
                        pk_status is = pk_colour_render_saved(c, &in, res, k, NULL, PK_ANSEL_ORIENTATION_PSI, 0, &im);
                        in.ice = 0;
                        if (is == PK_OK && write_tiff(ip, im.width, im.height, 8, rgb)) { nwritten++; cli_say("Frame %d: Digital ICE picture written.", frame_no); }
                        else { cli_report_status("The Digital ICE picture could not be made", is == PK_OK ? PK_E_IO : is, NULL); rc = 1; }
                    } else if (o->ice && rs == PK_OK) cli_say("Frame %d: no infrared plane (not an IR scan), so no Digital ICE picture.", frame_no);
                    free(rgb);
                } else { cli_report_status("This frame could not be colour-processed", fs, NULL); rc = 1; }
            }
            nwritten += wrote_lin + wrote_col;
            if (o->colour && wrote_col) {
                cli_say("Frame %d: %d x %d, %s%s%s", frame_no, in.frames[k].width, in.frames[k].height, exact == 1 ? "exact" : "not exact",
                        skipped == 1 ? ", skipped (rendered unbalanced)" : "", fi.not_kodak_exact ? ", framing_not_kodak_exact: framing may differ from PSI" : "");
            } else cli_say("Frame %d: %d x %d, linear picture %s", frame_no, in.frames[k].width, in.frames[k].height, wrote_lin ? "written" : "NOT written");
            if (o->colour && !fi.not_kodak_exact && exact == 0) cli_say("  Frame %d is not Kodak-exact: framing may differ from PSI.", frame_no);
        record:
            fprintf(fj, "%s\n  {\"frame\": %d, \"strip\": %d, \"width\": %d, \"height\": %d, \"linear16\": %s%s%s, \"colour\": %s%s%s, "
                        "\"exact\": %s, \"skipped\": %s, \"framing_not_kodak_exact\": %s, \"product\": %d, \"specifier\": %d, \"dx_source\": \"%s\", \"status\": \"%s\"}",
                    first ? "" : ",", frame_no, s + 1, in.frames[k].width, in.frames[k].height,
                    wrote_lin ? "\"" : "null", wrote_lin ? lin : "", wrote_lin ? "\"" : "", wrote_col ? "\"" : "null", wrote_col ? col : "", wrote_col ? "\"" : "",
                    exact < 0 ? "null" : exact ? "true" : "false", skipped < 0 ? "null" : skipped ? "true" : "false", fi.not_kodak_exact ? "true" : "false",
                    in.product_code, in.gen_code, dx.dx_source, pk_status_str(fs));
            first = 0;
            pk_roll_colour_frame_release(&in, keep, k);
        }
        pk_roll_result_free(res);
        pk_roll_input_storage_free(keep);
    }
    fputs("\n ]\n}\n", fj);
    fclose(fj);
    if (g_cli_intr) { cli_say("Stopped."); rc = 130; }
    else if (nwritten == 0 && rc == 0) { cli_say("No frames were found in this roll."); rc = 1; }
    else cli_say("Done: %d picture%s in %s (frames.json lists them).", nwritten, nwritten == 1 ? "" : "s", out);
    pk_colour_close(c);
    pk_roll_close(r);
    return rc;
}
