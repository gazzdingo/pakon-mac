#include "greatest.h"
#include "pkv.h"
#include <stdio.h>
#include <string.h>
#include <stdint.h>

/* Write bytes to a temp file, return pkv_open result. */
static pkv_file *open_bytes(const unsigned char *b, size_t n) {
    char path[] = "/tmp/pkv_testXXXXXX";
    int fd = mkstemp(path);
    if (fd < 0) return NULL;
    FILE *fp = fdopen(fd, "wb");
    fwrite(b, 1, n, fp);
    fclose(fp);
    pkv_file *f = pkv_open(path);
    remove(path);
    return f;
}

/* Header: PKV1, count=1, name "a", dtype 2 (i16), ndim 1, dims d0..d3. */
static size_t mk(unsigned char *o, uint32_t count, uint32_t d0, uint32_t d1, int ndim, size_t payload) {
    size_t k = 0;
    memcpy(o, "PKV1", 4); k = 4;
    for (int i = 0; i < 4; i++) o[k++] = (unsigned char)(count >> (8 * i));
    o[k++] = 1; o[k++] = 'a'; o[k++] = 2; o[k++] = (unsigned char)ndim;
    uint32_t d[4] = {d0, d1, 0, 0};
    for (int j = 0; j < 4; j++) for (int i = 0; i < 4; i++) o[k++] = (unsigned char)(d[j] >> (8 * i));
    memset(o + k, 0, payload);
    return k + payload;
}

TEST rejects_missing_file(void) { ASSERT(pkv_open("/tmp/pkv_does_not_exist.pkv") == NULL); PASS(); }
TEST rejects_bad_magic(void) {
    unsigned char b[64]; size_t n = mk(b, 1, 2, 0, 1, 4); b[0] = 'X';
    ASSERT(open_bytes(b, n) == NULL); PASS();
}
TEST rejects_truncated_header(void) {
    unsigned char b[64]; size_t n = mk(b, 1, 2, 0, 1, 4);
    ASSERT(open_bytes(b, 6) == NULL);
    ASSERT(open_bytes(b, 20) == NULL);
    ASSERT(n > 20); PASS();
}
TEST rejects_short_payload(void) {
    unsigned char b[64]; size_t n = mk(b, 1, 8, 0, 1, 4); /* needs 16 bytes */
    ASSERT(open_bytes(b, n) == NULL); PASS();
}
TEST accepts_exact_payload(void) {
    unsigned char b[64]; size_t n = mk(b, 1, 2, 0, 1, 4);
    pkv_file *f = open_bytes(b, n); ASSERT(f != NULL); pkv_close(f); PASS();
}
TEST rejects_huge_count(void) {
    unsigned char b[64]; size_t n = mk(b, 0xFFFFFFFFu, 2, 0, 1, 4);
    ASSERT(open_bytes(b, n) == NULL); PASS();
}
TEST rejects_overflowing_dims(void) {
    unsigned char b[64];
    size_t n = mk(b, 1, 0x7FFFFFFFu, 0x7FFFFFFFu, 2, 4);
    ASSERT(open_bytes(b, n) == NULL);
    n = mk(b, 1, 0x80000000u, 0, 1, 4); /* dim above INT32_MAX */
    ASSERT(open_bytes(b, n) == NULL); PASS();
}
TEST reads_named_arrays(void) {
    pkv_file *f = pkv_open(PKV_DIR "/selftest.pkv");
    ASSERT(f != NULL);
    const pkv_array *a = pkv_get(f, "ramp");
    ASSERT(a && a->dtype == 2 && a->ndim == 1 && a->dims[0] == 4096);
    const int16_t *v = a->data;
    ASSERT_STR_EQ("ramp", a->name); ASSERT_EQ(4096, (int)a->n);
    ASSERT_EQ(0, v[0]); ASSERT_EQ(4095, v[4095]);
    ASSERT(pkv_get(f, "missing") == NULL);
    pkv_close(f); PASS();
}
/* id lists (pkv_list_count / pkv_list_index, Task 18 M4): an empty u8 list holds no id; a NULL id is never found */
TEST id_lists(void) {
    unsigned char b[64]; size_t n = mk(b, 1, 0, 0, 1, 0);
    b[10] = 1;                                   /* dtype u8, zero elements */
    pkv_file *f = open_bytes(b, n);
    ASSERT(f != NULL);
    ASSERT_EQ(0, pkv_list_count(f, "a"));
    ASSERT_EQ(-1, pkv_list_index(f, "a", ""));
    ASSERT_EQ(-1, pkv_list_index(f, "a", NULL));
    pkv_close(f);
    unsigned char c[64]; size_t m = mk(c, 1, 5, 0, 1, 5);
    c[10] = 1; memcpy(c + m - 5, "x,yz", 4); c[m - 1] = 'w';     /* "x,yzw" */
    f = open_bytes(c, m);
    ASSERT(f != NULL);
    ASSERT_EQ(2, pkv_list_count(f, "a"));
    ASSERT_EQ(1, pkv_list_index(f, "a", "yzw"));
    ASSERT_EQ(-1, pkv_list_index(f, "a", NULL));
    pkv_close(f);
    PASS();
}
GREATEST_MAIN_DEFS();
int main(int argc, char **argv) { GREATEST_MAIN_BEGIN(); RUN_TEST(reads_named_arrays); RUN_TEST(rejects_missing_file); RUN_TEST(rejects_bad_magic);
    RUN_TEST(rejects_truncated_header); RUN_TEST(rejects_short_payload); RUN_TEST(accepts_exact_payload);
    RUN_TEST(rejects_huge_count); RUN_TEST(rejects_overflowing_dims); RUN_TEST(id_lists); GREATEST_MAIN_END(); }
