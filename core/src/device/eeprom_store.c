#define _POSIX_C_SOURCE 200809L
/* The calibration-EEPROM image store; format in eeprom_store.h. No global or static mutable state. */
#include "device/eeprom_store.h"
#include "util/util.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define LOG_MAGIC "pkeeprom1"

static int unit_ok(const char *u) {
    size_t n = u ? strlen(u) : 0;
    if (n == 0 || n > 64 || u[0] == '.') return 0;
    for (size_t i = 0; i < n; i++) {
        char c = u[i];
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '.' || c == '_' || c == '-')) return 0;
    }
    return 1;
}

static pk_status dir_path(const char *unit, const char *root, char *out, size_t cap) {
    if (!unit_ok(unit) || !root || !*root) return PK_E_ARG;
    return snprintf(out, cap, "%s/units/%s/eeprom", root, unit) < (int)cap ? PK_OK : PK_E_ARG;
}

static int is_hex64(const char *s) {
    for (int i = 0; i < 64; i++) if (!((s[i] >= '0' && s[i] <= '9') || (s[i] >= 'a' && s[i] <= 'f'))) return 0;
    return s[64] == ' ';
}

/* The sha256 named by the last well-formed "current" line; PK_E_NOT_FOUND if there is none (or no log). */
static pk_status log_current(const char *dir, char sha[65]) {
    char path[1200];
    if (snprintf(path, sizeof path, "%s/eeprom.log", dir) >= (int)sizeof path) return PK_E_ARG;
    uint8_t *buf = NULL;
    size_t n = 0;
    pk_status s = pku_read_file(path, &buf, &n);
    if (s != PK_OK) return s;
    sha[0] = 0;
    size_t i = 0;
    while (i < n) {
        size_t j = i;
        while (j < n && buf[j] != '\n') j++;
        if (j < n) {   /* a line without its newline is a torn write: skipped */
            const char *l = (const char *)buf + i;
            size_t len = j - i;
            /* "pkeeprom1 " + 64 hex + " " + 4 mask + " " + tag + " " + seconds */
            if (len >= 10 + 64 + 1 + 4 + 1 + 6 + 1 + 1 && memcmp(l, LOG_MAGIC " ", 10) == 0 && is_hex64(l + 10)) {
                const char *m = l + 10 + 65;
                int mask_ok = m[4] == ' ';
                for (int k = 0; k < 4; k++) if (m[k] != '0' && m[k] != '1') mask_ok = 0;
                const char *tag = m + 5;
                int tail_ok = len > (size_t)(tag - l) + 8;   /* the seconds field: digits up to the newline, at least one */
                for (size_t k = (size_t)(tag - l) + 8; k < len; k++) if (l[k] < '0' || l[k] > '9') tail_ok = 0;
                if (mask_ok && tail_ok && memcmp(tag, "current ", 8) == 0) {
                    memcpy(sha, l + 10, 64);
                    sha[64] = 0;
                }
            }
        }
        i = j + 1;
    }
    free(buf);
    return sha[0] ? PK_OK : PK_E_NOT_FOUND;
}

static pk_status read_image(const char *dir, const char *sha, uint8_t out[PKCAL_EEPROM_SIZE]) {
    char path[1200];
    if (snprintf(path, sizeof path, "%s/%s.bin", dir, sha) >= (int)sizeof path) return PK_E_ARG;
    struct stat lst;
    if (lstat(path, &lst) == 0 && !S_ISREG(lst.st_mode)) return PK_E_CORRUPT;   /* a symlink or other non-file is never followed */
    uint8_t *buf = NULL;
    size_t n = 0;
    pk_status s = pku_read_file(path, &buf, &n);
    if (s == PK_E_NOT_FOUND) return PK_E_CORRUPT;   /* the log names an image the store does not hold */
    if (s != PK_OK) return s;
    char h[65];
    if (n != PKCAL_EEPROM_SIZE) s = PK_E_CORRUPT;
    else {
        pku_sha256_hex(buf, n, h);
        if (strcmp(h, sha) != 0) s = PK_E_CORRUPT;
        else memcpy(out, buf, n);
    }
    free(buf);
    return s;
}

pk_status pk_eeprom_store_current(const char *unit, const char *root, uint8_t image_out[PKCAL_EEPROM_SIZE]) {
    char dir[1100], sha[65];
    if (!image_out) return PK_E_ARG;
    pk_status s = dir_path(unit, root, dir, sizeof dir);
    if (s != PK_OK) return s;
    s = log_current(dir, sha);
    if (s != PK_OK) return s;
    return read_image(dir, sha, image_out);
}

pk_status pk_eeprom_store_put(const char *unit, const char *root, const uint8_t image[PKCAL_EEPROM_SIZE],
                              const int copy_ok[PKCAL_NCOPIES], int require_equal, unsigned *flags_out) {
    if (flags_out) *flags_out = 0;
    char dir[1100];
    if (!image || !copy_ok) return PK_E_ARG;
    pk_status s = dir_path(unit, root, dir, sizeof dir);
    if (s != PK_OK) return s;
    int chk[PKCAL_NCOPIES];
    if (pkcal_eeprom_validate(image, chk) != PK_OK) return PK_E_ARG;
    for (int i = 0; i < PKCAL_NCOPIES; i++) if ((chk[i] != 0) != (copy_ok[i] != 0)) return PK_E_ARG;   /* the flags must describe this image */

    unsigned fl = 0;
    char sha[65];
    pku_sha256_hex(image, PKCAL_EEPROM_SIZE, sha);
    if (pku_mkdirs(dir) != PK_OK) return PK_E_IO;
    char path[1200];
    if (snprintf(path, sizeof path, "%s/%s.bin", dir, sha) >= (int)sizeof path) return PK_E_ARG;
    struct stat st;
    if (lstat(path, &st) == 0) {
        uint8_t old[PKCAL_EEPROM_SIZE];
        s = read_image(dir, sha, old);   /* an existing file must really be this image */
        if (s != PK_OK) return s;
    } else {
        s = pku_write_file_atomic(path, image, PKCAL_EEPROM_SIZE);
        if (s != PK_OK) return s;
        fl |= PK_EEPROM_PUT_NEW;
    }

    int has_calwiz = copy_ok[PKCAL_CALWIZ_A] || copy_ok[PKCAL_CALWIZ_B];
    if (!has_calwiz) fl |= PK_EEPROM_PUT_NO_CALWIZ;
    int make_current = has_calwiz;
    {   /* whenever a current image exists, every put is a re-read: it becomes current only if byte-identical (S-R13) */
        char cur[65];
        pk_status cs = log_current(dir, cur);
        if (cs == PK_E_NOT_FOUND) { if (require_equal) { fl |= PK_EEPROM_PUT_NO_CURRENT; make_current = 0; } }   /* the first read */
        else if (cs != PK_OK) { if (flags_out) *flags_out = fl; return cs; }
        else if (strcmp(cur, sha) != 0) { fl |= PK_EEPROM_PUT_DIFFERS; make_current = 0; }
    }
    if (flags_out) *flags_out = fl;   /* the image is stored from here on, whatever happens to the log */
    {   /* the directory entries must be durable before a log line names the image */
        int dfd = open(dir, O_RDONLY);
        if (dfd >= 0) { (void)fsync(dfd); close(dfd); }
    }
    if (make_current) fl |= PK_EEPROM_PUT_CURRENT;

    char logp[1200], line[160];
    if (snprintf(logp, sizeof logp, "%s/eeprom.log", dir) >= (int)sizeof logp) return PK_E_ARG;
    int n = snprintf(line, sizeof line, LOG_MAGIC " %s %d%d%d%d %s %lld\n", sha, copy_ok[0] != 0, copy_ok[1] != 0,
                     copy_ok[2] != 0, copy_ok[3] != 0, make_current ? "current" : "stored", (long long)time(NULL));
    if (n <= 0 || n >= (int)sizeof line) return PK_E_IO;
    int fd = open(logp, O_RDWR | O_APPEND | O_CREAT, 0644);   /* append-only: never truncated or rewritten */
    if (fd < 0) return PK_E_IO;
    char lead[1] = { '\n' };
    off_t end = lseek(fd, 0, SEEK_END);
    char last = '\n';
    if (end > 0 && pread(fd, &last, 1, end - 1) != 1) { close(fd); return PK_E_IO; }
    int ok = 1;
    if (last != '\n') ok = write(fd, lead, 1) == 1;   /* a torn previous line: end it so this line stands alone */
    ok = ok && write(fd, line, (size_t)n) == n && fsync(fd) == 0;
    if (close(fd) != 0) ok = 0;
    if (!ok) return PK_E_IO;
    if (flags_out) *flags_out = fl;
    return PK_OK;
}
