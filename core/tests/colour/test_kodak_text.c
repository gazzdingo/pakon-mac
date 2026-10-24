#include "greatest.h"
#include "data/kodak_text.h"
#include <locale.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int tmp_write(char *path, const void *data, size_t n) {
    int fd = mkstemp(path);
    if (fd < 0) return -1;
    FILE *f = fdopen(fd, "wb");
    if (!f) return -1;
    fwrite(data, 1, n, f); fclose(f);
    return 0;
}
TEST falloff_dpi(void) {
    pkc_kt *k; char p[1024]; double v[2];
    ASSERT_EQ(PK_OK, pkc_vendor_path(VENDOR_ROOT, "anselinstalldir/dataPathItems/falloff/falloff-srcType-SUC-NEGATIVE_35-NO.dpi", p, sizeof p));
    ASSERT_EQ(PK_OK, pkc_kt_load(p, &k));
    ASSERT_EQ(1, pkc_kt_num(k, "scale", v, 2)); ASSERT_EQ(1250.0, v[0]);
    ASSERT_EQ(1, pkc_kt_num(k, "exposure_min", v, 2)); ASSERT_EQ(-0.5, v[0]);
    pkc_kt_free(k); PASS();
}
TEST noise_table(void) {
    pkc_kt *k; char p[1024]; static double v[4 * 4096];
    ASSERT_EQ(PK_OK, pkc_vendor_path(VENDOR_ROOT, "anselinstalldir/dataPathItems/noiseTable/negative35-0100.tbl", p, sizeof p));
    ASSERT_EQ(PK_OK, pkc_kt_load(p, &k));
    ASSERT_EQ(4 * 4096, pkc_kt_num(k, "NoiseTable", v, 4 * 4096));
    ASSERT_EQ(0.0, v[0]); ASSERT_IN_RANGE(17.041, v[1], 1e-9);
    pkc_kt_free(k); PASS();
}
/* Pins I-4: a host's comma-decimal locale must not change a Kodak number (strtod would give 2 for "2.25"). */
TEST locale_independent(void) {
    char *old = setlocale(LC_ALL, NULL); char saved[128] = "C";
    if (old) snprintf(saved, sizeof saved, "%s", old);
    if (!setlocale(LC_ALL, "de_DE.UTF-8")) SKIPm("de_DE.UTF-8 locale not installed");
    double d = 0, v[4 * 4096]; pkc_kt *k; char p[1024];
    int ok = pkc_kt_parse_number("2.25", &d);
    int ok2 = pkc_kt_parse_number("1e999", &d);
    ASSERT_EQ(PK_OK, pkc_vendor_path(VENDOR_ROOT, "anselinstalldir/dataPathItems/noiseTable/negative35-0100.tbl", p, sizeof p));
    int ld = pkc_kt_load(p, &k), n = ld == PK_OK ? pkc_kt_num(k, "NoiseTable", v, 4 * 4096) : 0;
    double v1 = n > 1 ? v[1] : -1;
    if (ld == PK_OK) pkc_kt_free(k);
    setlocale(LC_ALL, saved);
    ASSERT_EQ(1, ok); ASSERT_EQ(0, ok2);
    ASSERT_EQ(PK_OK, ld); ASSERT_EQ(4 * 4096, n); ASSERT_IN_RANGE(17.041, v1, 1e-9);
    PASS();
}
TEST fugc_map_rows(void) {
    pkc_kt *k; char p[1024]; char **t; int nc;
    ASSERT_EQ(PK_OK, pkc_vendor_path(VENDOR_ROOT, "anselinstalldir/dataPathItems/fugc/fugc-rgb-lutMap.map", p, sizeof p));
    ASSERT_EQ(PK_OK, pkc_kt_load(p, &k));
    int n = pkc_kt_rows(k, "contrast", &t, &nc);
    ASSERT_EQ(4, n); ASSERT_STR_EQ("NoShift_fugc-generic0225.lut", t[1 * nc + 1]);
    pkc_kt_free(k); PASS();
}
TEST missing_file_is_vendor_error(void) {
    pkc_kt *k;
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_kt_load("/nonexistent/x.dpi", &k)); PASS();
}
TEST short_table_returns_count(void) {
    /* Size enforcement belongs to consumers; the parser just reports the count. */
    char p[] = "/tmp/pk_shortXXXXXX";
    ASSERT_EQ(0, tmp_write(p, "NoiseTable =\n 0 1 2\n", 21));
    pkc_kt *k; ASSERT_EQ(PK_OK, pkc_kt_load(p, &k)); double v[16];
    ASSERT_EQ(3, pkc_kt_num(k, "NoiseTable", v, 16));
    pkc_kt_free(k); remove(p); PASS();
}

TEST directory_is_vendor_error(void) {
    pkc_kt *k; ASSERT_EQ(PK_E_VENDOR_DATA, pkc_kt_load("/tmp", &k)); PASS();
}
TEST empty_file_is_vendor_error(void) {
    char p[] = "/tmp/pk_emptyXXXXXX"; pkc_kt *k;
    ASSERT_EQ(0, tmp_write(p, "", 0));
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_kt_load(p, &k)); remove(p); PASS();
}
TEST garbage_file_is_vendor_error(void) {
    char p[] = "/tmp/pk_garbXXXXXX"; pkc_kt *k;
    const unsigned char g[] = {0x00, 0xff, 0xfe, 0x01, '\n', 0x80, 0x90, 0x7f, 0x02};
    ASSERT_EQ(0, tmp_write(p, g, sizeof g));
    ASSERT_EQ(PK_E_VENDOR_DATA, pkc_kt_load(p, &k)); remove(p); PASS();
}
TEST nonfinite_and_hex_not_numeric(void) {
    char p[] = "/tmp/pk_nanXXXXXX"; pkc_kt *k; double v[8];
    const char *txt = "T = 1 2\nnan inf 0x10\n3\nU = nan\nV = 1e2 -.5 +3.\n";
    ASSERT_EQ(0, tmp_write(p, txt, strlen(txt)));
    ASSERT_EQ(PK_OK, pkc_kt_load(p, &k)); remove(p);
    ASSERT_EQ(3, pkc_kt_num(k, "T", v, 8)); ASSERT_EQ(3.0, v[2]);
    ASSERT_EQ(0, pkc_kt_num(k, "U", v, 8));
    ASSERT_EQ(3, pkc_kt_num(k, "V", v, 8)); ASSERT_EQ(100.0, v[0]); ASSERT_EQ(-0.5, v[1]);
    pkc_kt_free(k); PASS();
}
TEST str_lookup(void) {
    pkc_kt *k; char p[1024];
    ASSERT_EQ(PK_OK, pkc_vendor_path(VENDOR_ROOT, "anselinstalldir/dataPathItems/noiseTable/negative35-0100.tbl", p, sizeof p));
    ASSERT_EQ(PK_OK, pkc_kt_load(p, &k));
    ASSERT_STR_EQ("negative35-0100.tbl", pkc_kt_str(k, "key"));
    ASSERT(pkc_kt_str(k, "no_such_key") == NULL);
    pkc_kt_free(k); PASS();
}

GREATEST_MAIN_DEFS();
int main(int argc, char **argv) {
    GREATEST_MAIN_BEGIN();
    RUN_TEST(falloff_dpi); RUN_TEST(noise_table); RUN_TEST(fugc_map_rows);
    RUN_TEST(missing_file_is_vendor_error); RUN_TEST(short_table_returns_count);
    RUN_TEST(directory_is_vendor_error); RUN_TEST(empty_file_is_vendor_error); RUN_TEST(garbage_file_is_vendor_error);
    RUN_TEST(nonfinite_and_hex_not_numeric); RUN_TEST(str_lookup); RUN_TEST(locale_independent);
    GREATEST_MAIN_END();
}
