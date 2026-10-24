#include "util/util.h"
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define PKU_MAX_FILE ((long long)1 << 30)

pk_status pku_read_file(const char *path, uint8_t **data, size_t *n) {
    if (data) *data = NULL;
    if (n) *n = 0;
    if (!path || !data || !n) return PK_E_ARG;
    FILE *f = fopen(path, "rb");
    if (!f) return errno == ENOENT || errno == ENOTDIR ? PK_E_NOT_FOUND : PK_E_IO;
    pk_status st = PK_E_IO;
    uint8_t *buf = NULL;
    if (fseek(f, 0, SEEK_END)) goto done;
    long long sz = ftell(f);
    if (sz < 0 || fseek(f, 0, SEEK_SET)) goto done;
    if (sz > PKU_MAX_FILE) { st = PK_E_CORRUPT; goto done; }
    buf = (uint8_t *)malloc(sz ? (size_t)sz : 1);
    if (!buf) { st = PK_E_NOMEM; goto done; }
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) goto done;
    *data = buf; *n = (size_t)sz; buf = NULL; st = PK_OK;
done:
    free(buf);
    fclose(f);
    return st;
}

pk_status pku_write_file_atomic(const char *path, const void *data, size_t n) {
    if (!path || (n && !data)) return PK_E_ARG;
    char tmp[1100];
    if (snprintf(tmp, sizeof tmp, "%s.tmp.%ld", path, (long)getpid()) >= (int)sizeof tmp) return PK_E_FORMAT;
    int fd = open(tmp, O_WRONLY | O_CREAT | O_EXCL, 0644);
    if (fd < 0) return PK_E_IO;
    const uint8_t *p = (const uint8_t *)data;
    size_t left = n;
    while (left) {
        ssize_t w = write(fd, p, left);
        if (w < 0 && errno == EINTR) continue;
        if (w <= 0) goto fail;
        p += w; left -= (size_t)w;
    }
    if (fsync(fd)) goto fail;
    if (close(fd)) { fd = -1; goto fail; }
    fd = -1;
    if (rename(tmp, path)) goto fail;
    return PK_OK;
fail:
    if (fd >= 0) close(fd);
    unlink(tmp);
    return PK_E_IO;
}

pk_status pku_mkdirs(const char *path) {
    if (!path || !*path) return PK_E_ARG;
    size_t len = strlen(path);
    if (len >= 1100) return PK_E_FORMAT;
    char b[1100];
    memcpy(b, path, len + 1);
    for (size_t i = 1; i <= len; i++) {
        if (b[i] != '/' && b[i] != 0) continue;
        char c = b[i];
        b[i] = 0;
        if (mkdir(b, 0777) && errno != EEXIST) return PK_E_IO;
        b[i] = c;
    }
    struct stat st;
    return stat(path, &st) == 0 && S_ISDIR(st.st_mode) ? PK_OK : PK_E_IO;
}

int pku_path_is_safe(const char *rel) {
    if (!rel || !*rel || rel[0] == '/') return 0;
    for (const char *p = rel; *p;) {
        const char *q = p;
        while (*q && *q != '/') { if (*q == '\\') return 0; q++; }
        if (q - p == 2 && p[0] == '.' && p[1] == '.') return 0;
        p = *q ? q + 1 : q;
    }
    return 1;
}
