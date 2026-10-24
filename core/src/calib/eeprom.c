/* Calibration-EEPROM copy header rules and identity fields. Checked against TLB by core_eeprom_header_kodak. */
#define _POSIX_C_SOURCE 200809L
#include "calib/eeprom.h"
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "boards/boards.h"
#include "device/eeprom_store.h"
#include "pakon/calib.h"
#include "util/util.h"

static const uint32_t OFF[PKCAL_NCOPIES] = { 0x000, 0x400, 0x800, 0xA00 };
static const uint32_t BOUND[PKCAL_NCOPIES] = { 0x400, 0x400, 0x200, 0x200 };

/* CRC-32, reflected, polynomial 0x04C11DB7 (0xEDB88320 reflected), init 0xFFFFFFFF, final complement: TLB FUN_10015FD0's
 * table and FUN_100163C0's loop. Computed bitwise: no table, no state. */
static uint32_t crc32(const uint8_t *p, size_t n) {
    uint32_t c = 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) {
        c ^= p[i];
        for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
    }
    return ~c;
}

static uint32_t le32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static int copy_valid(const uint8_t *img, int i) {
    const uint8_t *c = img + OFF[i];
    uint32_t len = le32(c);
    if (len < 8 || len > BOUND[i] || OFF[i] + len > PKCAL_EEPROM_SIZE) return 0;
    return crc32(c + 8, len - 8) == le32(c + 4);
}

pk_status pkcal_eeprom_validate(const uint8_t image[PKCAL_EEPROM_SIZE], int copy_ok[PKCAL_NCOPIES]) {
    if (!image || !copy_ok) return PK_E_ARG;
    for (int i = 0; i < PKCAL_NCOPIES; i++) copy_ok[i] = copy_valid(image, i);
    return PK_OK;
}

size_t pkcal_eeprom_copy(const uint8_t image[PKCAL_EEPROM_SIZE], int copy, uint8_t *out, size_t cap) {
    if (!image || !out || copy < 0 || copy >= PKCAL_NCOPIES || !copy_valid(image, copy)) return 0;
    size_t len = le32(image + OFF[copy]), st = copy < 2 ? PKCAL_CALWIZ_STRUCT : PKCAL_ADJUST_STRUCT;
    size_t n = len < st ? len : st;
    if (n > cap) return 0;
    memcpy(out, image + OFF[copy], n);
    return n;
}

pk_status pkcal_eeprom_identity(const uint8_t image[PKCAL_EEPROM_SIZE], const int copy_ok[PKCAL_NCOPIES],
                                uint32_t *scanner_type, uint32_t *hw_version, uint32_t *serial) {
    if (!image || !copy_ok) return PK_E_ARG;
    for (int i = 0; i < 2; i++) {
        if (!copy_ok[i] || !copy_valid(image, i)) continue;   /* the caller's flag is not trusted on its own */
        const uint8_t *c = image + OFF[i];
        if (le32(c) < 0x14) continue;   /* too short to hold the identity fields: try the other copy */
        if (hw_version) *hw_version = le32(c + 0x08);
        if (scanner_type) *scanner_type = le32(c + 0x0C);
        if (serial) *serial = le32(c + 0x10);
        return PK_OK;
    }
    return PK_E_CORRUPT;
}

/* ------------------------------------------------------------------ the read (Task 15), TLB FN_bEEPromRead FUN_100160a0 / FN_bReadEEPromToRegistry FUN_10016a90 (RE 30 sec 13.3, 13.4) */
#define EE_CHUNK 0x20u

static float le_f32(const uint8_t *p) { uint32_t u = le32(p); float f; memcpy(&f, &u, 4); return f; }

/* Fields of the first valid CalWiz copy (A, then B: FUN_10016A90 tries B only when A fails). Offsets are from the start of the copy, header included. */
static pk_status parse_image(const uint8_t *img, pk_eeprom *o) {
    int ok[PKCAL_NCOPIES];
    pk_status st = pkcal_eeprom_validate(img, ok);
    if (st != PK_OK) return st;
    for (int i = 0; i < PKCAL_NCOPIES; i++) o->copy_ok[i] = ok[i] != 0;
    uint32_t type = 0, hwv = 0, serial = 0;
    if (pkcal_eeprom_identity(img, ok, &type, &hwv, &serial) != PK_OK) return PK_E_CORRUPT;
    if (type != 0x546 && type != 0x547) return PK_E_CORRUPT;
    uint8_t cw[PKCAL_CALWIZ_STRUCT];
    size_t n = 0;
    for (int i = 0; i < 2 && n == 0; i++) if (ok[i] && (n = pkcal_eeprom_copy(img, i, cw, sizeof cw)) < 0x9E) n = 0;
    if (n == 0) return PK_E_CORRUPT;
    o->scanner_type = type;
    o->hw_version = hwv;
    o->serial = serial;
    for (int k = 0; k < 3; k++) o->px_offset[k] = (unsigned)(cw[0x14 + 6 * k] | cw[0x15 + 6 * k] << 8);   /* base 4, 8, 16: Offset (then the two motor speeds) */
    for (int r = 0; r < 3; r++)
        for (int k = 0; k < 10; k++) {
            float f = le_f32(cw + 0x26 + 4 * (r * 10 + k));
            if (!isfinite(f) || fabsf(f) > 1e7f) return PK_E_CORRUPT;
            o->poly_neg[r][k] = f;
        }
    memcpy(o->raw, img, PKCAL_EEPROM_SIZE);
    o->len = PKCAL_EEPROM_SIZE;
    pku_sha256_hex(img, PKCAL_EEPROM_SIZE, o->sha256);
    return PK_OK;
}

/* Task 20: the same parse for a saved image (the roll hand-off reads poly_neg from the unit's stored image). */
pk_status pkcal_eeprom_parse(const uint8_t image[PKCAL_EEPROM_SIZE], pk_eeprom *out) {
    if (!image || !out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    return parse_image(image, out);
}

static void unit_for(unsigned type, unsigned serial, char out[80]) {
    snprintf(out, 80, "%s-%u", type == 0x547 ? "F-135_Plus" : "F-135", serial);
}

/* units/<name>/eeprom/eeprom.log under root: the count of all of them, and of those whose name starts with `prefix` (first one kept). FAIL CLOSED (S-R38, S-R40 I-1): only a
 * clean "nothing there" (ENOENT / ENOTDIR on units/ or on a unit's eeprom.log) counts as absent; a failure to open or read units/, an unreadable or odd entry (permission, I/O, a
 * log that is not a regular file) or a path too long is an error, and the caller makes no transfer. */
static pk_status scan_units(const char *root, const char *prefix, int *n_all, int *n_prefix, char first[80]) {
    *n_all = *n_prefix = 0;
    first[0] = 0;
    char dir[1100];
    if (snprintf(dir, sizeof dir, "%s/units", root) >= (int)sizeof dir) return PK_E_IO;
    DIR *d = opendir(dir);
    if (!d) return errno == ENOENT ? PK_OK : PK_E_IO;       /* only a missing units/ is "absent": a regular file there (ENOTDIR) or any other error is not (R1-I1) */
    pk_status st = PK_OK;
    struct dirent *e;
    errno = 0;
    while ((e = readdir(d)) != NULL) {
        if (e->d_name[0] == '.') { errno = 0; continue; }
        char p[1500];
        struct stat sb;
        if (snprintf(p, sizeof p, "%s/%s/eeprom/eeprom.log", dir, e->d_name) >= (int)sizeof p) { st = PK_E_IO; break; }
        if (lstat(p, &sb) != 0) {
            if (errno == ENOENT || errno == ENOTDIR) { errno = 0; continue; }
            st = PK_E_IO;
            break;
        }
        if (!S_ISREG(sb.st_mode)) { st = PK_E_IO; break; }
        (*n_all)++;
        if (strncmp(e->d_name, prefix, strlen(prefix)) == 0) { if (*n_prefix == 0) snprintf(first, 80, "%s", e->d_name); (*n_prefix)++; }
        errno = 0;
    }
    if (st == PK_OK && errno != 0) st = PK_E_IO;       /* readdir failed part-way */
    closedir(d);
    return st;
}

/* R1-I1: before the first transfer, prove the image can be saved: create the directory the image goes to and write, fsync and unlink a probe file there. A chip that is read but
 * cannot be stored would be read again on every attempt, against the once-per-scanner rule. Without a known unit the probe is units/ itself. */
static pk_status prove_writable(const char *root, const char *unit) {
    char dir[1200], probe[1300];
    if (unit && *unit) { if (snprintf(dir, sizeof dir, "%s/units/%s/eeprom", root, unit) >= (int)sizeof dir) return PK_E_IO; }
    else if (snprintf(dir, sizeof dir, "%s/units", root) >= (int)sizeof dir) return PK_E_IO;
    if (pku_mkdirs(dir) != PK_OK) return PK_E_IO;
    if (snprintf(probe, sizeof probe, "%s/.probe.%ld", dir, (long)getpid()) >= (int)sizeof probe) return PK_E_IO;
    int fd = open(probe, O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (fd < 0) return PK_E_IO;
    pk_status st = (write(fd, "x", 1) == 1 && fsync(fd) == 0) ? PK_OK : PK_E_IO;
    if (close(fd) != 0) st = PK_E_IO;
    if (unlink(probe) != 0) st = PK_E_IO;
    return st;
}

static pk_status eeprom_read_impl(const pk_model *m, pk_transport *t, const char *unit_in, const char *root, bool reread, pk_eeprom *out) {
    if (!out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    if (!m || !t || !root || !*root) return PK_E_ARG;
    char prefix[40], unit[80] = "", first[80];
    int n_all, n_pre;
    snprintf(prefix, sizeof prefix, "%s-", m->id == PK_MODEL_F135_PLUS ? "F-135_Plus" : "F-135");
    pk_status ls = scan_units(root, prefix, &n_all, &n_pre, first);
    if (ls != PK_OK) return ls;                                    /* fail closed: the store cannot be listed, so "no image yet" is not known: no transfer */
    if (unit_in && *unit_in) snprintf(unit, sizeof unit, "%s", unit_in);
    else if (n_all > 1) return PK_E_BUSY;                          /* more than one saved unit: say which (pk_eeprom_identify picks it from the chip serial) */
    else if (n_pre == 1) snprintf(unit, sizeof unit, "%s", first);
    uint8_t *cur = (uint8_t *)malloc(PKCAL_EEPROM_SIZE), *img = (uint8_t *)malloc(PKCAL_EEPROM_SIZE);
    if (!cur || !img) { free(cur); free(img); return PK_E_NOMEM; }
    pk_status st = PK_OK;
    bool have_current = false;
    if (unit[0]) {
        st = pk_eeprom_store_current(unit, root, cur);
        if (st == PK_OK) have_current = true;
        else if (st != PK_E_NOT_FOUND) goto done;                 /* a damaged saved image: never answer by reading the chip again */
        st = PK_OK;
    }
    if (have_current && !reread) {                                 /* the normal path: no transfer */
        st = parse_image(cur, out);
        out->from_cache = true;
        goto done;
    }
    if (reread && !have_current) { st = PK_E_NOT_FOUND; goto done; }
    if (!have_current && n_all > 0) { st = PK_E_BUSY; goto done; }  /* the chip has been read before (an eeprom.log exists): it is only ever read once*/
    {   /* the live read: TLB's shape, chunks of 0x20 bytes */
        if ((st = prove_writable(root, unit)) != PK_OK) goto done;       /* no transfer if the image could not be saved */
        for (unsigned off = 0; off < PKCAL_EEPROM_SIZE && st == PK_OK; off += EE_CHUNK) {
            st = pk_t_control(t, 0x40, 0xA4, PK_EEPROM_SELECT_WVALUE, 0x1234, NULL, 0, 2000);
            if (st == PK_OK) st = pk_t_control(t, 0xC0, 0xA9, (uint16_t)off, 0x1234, img + off, EE_CHUNK, 2000);
        }
        if (st != PK_OK) goto done;
        pk_eeprom e;
        memset(&e, 0, sizeof e);
        st = parse_image(img, &e);
        if (st != PK_OK) goto done;                                 /* not stored: nothing about this image is trusted */
        char want[80];
        unit_for(e.scanner_type, e.serial, want);
        if (!unit[0]) snprintf(unit, sizeof unit, "%s", want);
        else if (strcmp(unit, want) != 0) { st = PK_E_ARG; goto done; }   /* an explicit unit must be this chip's (review m8): nothing is stored under another key */
        int ok[PKCAL_NCOPIES];
        for (int i = 0; i < PKCAL_NCOPIES; i++) ok[i] = e.copy_ok[i];
        unsigned flags = 0;
        st = pk_eeprom_store_put(unit, root, img, ok, have_current ? 1 : 0, &flags);
        if (st != PK_OK) goto done;
        if (have_current && !(flags & PK_EEPROM_PUT_CURRENT)) { st = PK_E_CORRUPT; goto done; }   /* a re-read that differs from the saved image */
        *out = e;
    }
done:
    free(cur);
    free(img);
    return st;
}

pk_status pk_eeprom_read(pk_boards *b, const char *unit_in, const char *root, bool reread, pk_eeprom *out) {
    if (!out) return PK_E_ARG;
    if (!b) { memset(out, 0, sizeof *out); return PK_E_ARG; }
    return eeprom_read_impl(pk_boards_model(b), pk_boards_transport(b), unit_in, root, reread, out);
}

/* The app's automatic first read for a brand-new scanner (owner ruling 2026-10-23): the same read as pk_eeprom_read(NULL unit, reread = false), but from a bare transport and the
 * USB-level model, so it needs no boards and sends nothing but the chip-select and read transfers. Same fail-closed store rules: only a clean empty store reads the chip. */
pk_status pk_eeprom_first_read(pk_transport *t, const pk_model *usb_model, const char *store_root, pk_eeprom *out) {
    return eeprom_read_impl(usb_model, t, NULL, store_root, false, out);
}

/* ------------------------------------------------------------------ the per-session serial read (owner decision 2026-10-22, closes S-R40 I-2) */
static pk_status read_serial(pk_transport *t, uint16_t off, uint32_t *v) {
    uint8_t sb[4];
    pk_status st = pk_t_control(t, 0x40, 0xA4, PK_EEPROM_SELECT_WVALUE, 0x1234, NULL, 0, 2000);   /* TLB's read shape, 4 bytes: nothing is ever written to the chip */
    if (st == PK_OK) st = pk_t_control(t, 0xC0, 0xA9, off, 0x1234, sb, 4, 2000);
    if (st == PK_OK) *v = le32(sb);
    return st;
}

pk_status pk_eeprom_identify(pk_boards *b, const char *root, pk_eeprom *out, unsigned *seen_serial) {
    if (seen_serial) *seen_serial = 0;
    if (!out) return PK_E_ARG;
    memset(out, 0, sizeof *out);
    if (!b || !root || !*root) return PK_E_ARG;
    const pk_model *m = pk_boards_model(b);
    char prefix[40], first[80];
    int n_all, n_pre;
    snprintf(prefix, sizeof prefix, "%s-", m->id == PK_MODEL_F135_PLUS ? "F-135_Plus" : "F-135");
    pk_status st = scan_units(root, prefix, &n_all, &n_pre, first);
    if (st != PK_OK) return st;
    if (n_all == 0) return PK_E_NOT_FOUND;       /* nothing saved: the first full read is only ever an explicit command, never a session open */
    pk_transport *t = pk_boards_transport(b);
    if (!t) return PK_E_ARG;
    uint8_t *cur = (uint8_t *)malloc(PKCAL_EEPROM_SIZE);
    if (!cur) return PK_E_NOMEM;
    static const uint16_t OFFS[2] = { 0x010, 0x410 };   /* CalWiz serial in copy A and in copy B: a match on either counts */
    for (int pass = 0; pass < 2; pass++) {
        uint32_t ser[2];
        char name[2][80];
        int hit = -1;
        for (int i = 0; i < 2; i++) {
            if ((st = read_serial(t, OFFS[i], &ser[i])) != PK_OK) goto done;
            unit_for(m->id == PK_MODEL_F135_PLUS ? 0x547 : 0x546, ser[i], name[i]);
            pk_status c = pk_eeprom_store_current(name[i], root, cur);
            if (c == PK_OK) {
                if (hit >= 0 && strcmp(name[hit], name[i]) != 0) { st = PK_E_CORRUPT; goto done; }   /* the two copies name two different saved units: trust neither */
                if (hit < 0) hit = i;
            } else if (c != PK_E_NOT_FOUND) { st = c; goto done; }
        }
        if (hit >= 0 && pass == 1) { st = PK_E_CORRUPT; goto done; }   /* the first pair of reads found no saved unit and the second does: the chip is not answering consistently */
        if (hit >= 0) {                                   /* the same scanner as a saved unit: adopt its image, no further transfer */
            if ((st = pk_eeprom_store_current(name[hit], root, cur)) != PK_OK) goto done;
            st = parse_image(cur, out);
            out->from_cache = true;
            if (seen_serial) *seen_serial = ser[hit];
            goto done;
        }
        if (seen_serial) *seen_serial = ser[1];
        if (pass == 1) break;                             /* second pair of reads agreed: foreign */
    }
    st = PK_E_CAL_FOREIGN;                                /* a serial no saved unit has, read twice with the same outcome: a different scanner. Never read automatically */
done:
    free(cur);
    return st;
}
