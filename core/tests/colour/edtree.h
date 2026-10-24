#ifndef PK_TEST_EDTREE_H
#define PK_TEST_EDTREE_H
/* Test helper: a vendor tree of symlinks to the shipped one in which one file (rel, under anselinstalldir/dataPathItems)
 * is a copy with `from` replaced by `to` (from NULL: an unedited copy). Every directory on rel's path is real; its other
 * entries are symlinks. Needs VENDOR_ROOT and <dirent.h> <stdio.h> <stdlib.h> <string.h> <sys/stat.h> <unistd.h>. */
static int ed_mirror(const char *src, const char *dst, const char *rel, const char *from, const char *to) {
    if (mkdir(dst, 0700)) return -1;
    const char *slash = strchr(rel, '/');
    size_t l = slash ? (size_t)(slash - rel) : strlen(rel);
    DIR *D = opendir(src); struct dirent *e;
    if (!D) return -1;
    while ((e = readdir(D))) {
        if (e->d_name[0] == '.' || (strlen(e->d_name) == l && !strncmp(e->d_name, rel, l))) continue;
        char a[1200], b[1200];
        snprintf(a, sizeof a, "%s/%s", src, e->d_name); snprintf(b, sizeof b, "%s/%s", dst, e->d_name);
        if (symlink(a, b)) { closedir(D); return -1; }
    }
    closedir(D);
    char s2[1200], d2[1200];
    snprintf(s2, sizeof s2, "%s/%.*s", src, (int)l, rel); snprintf(d2, sizeof d2, "%s/%.*s", dst, (int)l, rel);
    if (slash) return ed_mirror(s2, d2, slash + 1, from, to);
    static char txt[65536];
    FILE *f = fopen(s2, "rb"); if (!f) return -1;
    size_t len = fread(txt, 1, sizeof txt - 1, f); fclose(f); txt[len] = 0;
    char *hit = from ? strstr(txt, from) : NULL;
    if (from && !hit) return -1;
    f = fopen(d2, "wb"); if (!f) return -1;
    if (hit) { fwrite(txt, 1, (size_t)(hit - txt), f); fputs(to, f); fputs(hit + strlen(from), f); }
    else fputs(txt, f);
    fclose(f);
    return 0;
}
/* root must hold 64 bytes; the tree is created under /tmp */
static int ed_tree(char *root, const char *rel, const char *from, const char *to) {
    char d[1200], src[1200], dst[1200];
    strcpy(root, "/tmp/pk_edt_XXXXXX");
    if (!mkdtemp(root)) return -1;
    snprintf(d, sizeof d, "%s/anselinstalldir", root); if (mkdir(d, 0700)) return -1;
    snprintf(src, sizeof src, "%s/Config", VENDOR_ROOT); snprintf(dst, sizeof dst, "%s/Config", root);
    if (symlink(src, dst)) return -1;
    snprintf(src, sizeof src, "%s/anselinstalldir/dataPathItems", VENDOR_ROOT);
    snprintf(d, sizeof d, "%s/anselinstalldir/dataPathItems", root);
    return ed_mirror(src, d, rel, from, to);
}
static void ed_rm(const char *root) {
    char cmd[1300]; snprintf(cmd, sizeof cmd, "rm -rf '%s'", root);
    if (system(cmd)) fprintf(stderr, "could not remove %s\n", root);
}
#endif
