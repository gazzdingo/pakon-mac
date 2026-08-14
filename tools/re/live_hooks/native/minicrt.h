/*
 * minicrt.h -- the smallest possible string/formatting/allocation helpers,
 * built entirely on kernel32.dll, no CRT of any kind.
 *
 * WHY THIS EXISTS: a first build of hookdll.dll/hookload.exe against this
 * project's mingw-w64 toolchain, even with -mcrtdll=msvcrt explicitly
 * requested, still imported api-ms-win-crt-*.dll (the Windows-10-era
 * Universal CRT "API set" DLLs -- confirmed by objdump, not assumed).
 * Those don't exist on Windows XP, which is this project's real target
 * (docs/68: "shipped with 32-bit Windows XP-only drivers"). Rather than
 * keep fighting one specific mingw-w64 build's default CRT selection,
 * every libc-shaped thing this harness needs (string length/copy/compare,
 * decimal/hex formatting, heap alloc, file I/O) is hand-rolled here on top
 * of kernel32.dll ONLY -- present on every NT since 3.1, definitely on XP.
 * Both hookload.c and hookdll.c are linked with `-nostartfiles` and a
 * custom entry point (see build.sh) specifically so the C runtime startup
 * object itself never gets pulled in either. `build.sh` verifies via
 * objdump, on every build, that the result imports nothing but
 * KERNEL32.dll -- not trusted blindly.
 *
 * Deliberately tiny and boring: every function here does the obvious
 * byte-at-a-time thing. Nothing clever, nothing that needs a second
 * reader to trust it.
 */
#ifndef PAKON_MINICRT_H
#define PAKON_MINICRT_H

#include <windows.h>

static int mc_strlen(const char *s) {
    int n = 0;
    while (s[n]) n++;
    return n;
}

/* Always NUL-terminates within [dst, dst+dstCap), even if src is longer. */
static void mc_strcpy_n(char *dst, const char *src, int dstCap) {
    int i = 0;
    if (dstCap <= 0) return;
    for (; i < dstCap - 1 && src[i]; i++) dst[i] = src[i];
    dst[i] = 0;
}

static void mc_strcat_n(char *dst, const char *src, int dstCap) {
    int dl = mc_strlen(dst);
    if (dl >= dstCap - 1) return;
    mc_strcpy_n(dst + dl, src, dstCap - dl);
}

static char *mc_strrchr(const char *s, char c) {
    const char *last = NULL;
    for (; *s; s++) if (*s == c) last = s;
    return (char *)last;
}

static char mc_tolower(char c) {
    if (c >= 'A' && c <= 'Z') return (char)(c - 'A' + 'a');
    return c;
}

static int mc_isdigit(char c) { return c >= '0' && c <= '9'; }

/* Case-insensitive "does hay contain needle" -- both must be shorter than
   512 bytes (true of everything this tool ever calls it on: process
   names and single CLI tokens). */
static int mc_contains_ci(const char *hay, const char *needle) {
    char h[512], n[512];
    int i;
    for (i = 0; hay[i] && i < 511; i++) h[i] = mc_tolower(hay[i]);
    h[i] = 0;
    for (i = 0; needle[i] && i < 511; i++) n[i] = mc_tolower(needle[i]);
    n[i] = 0;
    int hl = mc_strlen(h), nl = mc_strlen(n);
    if (nl == 0) return 1;
    for (i = 0; i + nl <= hl; i++) {
        int j = 0;
        for (; j < nl; j++) if (h[i + j] != n[j]) break;
        if (j == nl) return 1;
    }
    return 0;
}

static unsigned long mc_atoul(const char *s) {
    unsigned long v = 0;
    while (*s && mc_isdigit(*s)) { v = v * 10 + (unsigned long)(*s - '0'); s++; }
    return v;
}

static int mc_is_all_digits(const char *s) {
    if (!*s) return 0;
    for (; *s; s++) if (!mc_isdigit(*s)) return 0;
    return 1;
}

/* Appends decimal digits of v, returns count written. */
static int mc_u32_to_dec(unsigned long v, char *out) {
    char tmp[12];
    int n = 0;
    if (v == 0) { out[0] = '0'; return 1; }
    while (v > 0) { tmp[n++] = (char)('0' + (v % 10)); v /= 10; }
    for (int i = 0; i < n; i++) out[i] = tmp[n - 1 - i];
    return n;
}

/* Writes exactly 8 lowercase hex digits (no prefix). */
static void mc_u32_to_hex8(unsigned long v, char *out) {
    static const char *hexd = "0123456789abcdef";
    for (int i = 7; i >= 0; i--) { out[i] = hexd[v & 0xF]; v >>= 4; }
}

static void mc_u8_to_hex2(unsigned char v, char *out) {
    static const char *hexd = "0123456789abcdef";
    out[0] = hexd[(v >> 4) & 0xF];
    out[1] = hexd[v & 0xF];
}

static void *mc_alloc(SIZE_T n) {
    return HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, n);
}

static void mc_free(void *p) {
    if (p) HeapFree(GetProcessHeap(), 0, p);
}

/* ------------------------------------------------------------------ */
/* Growable-but-bounded string buffer for building log lines / output. */
/* ------------------------------------------------------------------ */

typedef struct {
    char *buf;
    int cap;
    int len;
} StrBuf;

static void sb_init(StrBuf *sb, char *buf, int cap) {
    sb->buf = buf; sb->cap = cap; sb->len = 0;
    if (cap > 0) buf[0] = 0;
}

static void sb_putc(StrBuf *sb, char c) {
    if (sb->len < sb->cap - 1) { sb->buf[sb->len++] = c; sb->buf[sb->len] = 0; }
}

static void sb_puts(StrBuf *sb, const char *s) {
    for (; *s; s++) sb_putc(sb, *s);
}

static void sb_put_u32(StrBuf *sb, unsigned long v) {
    char tmp[12];
    int n = mc_u32_to_dec(v, tmp);
    for (int i = 0; i < n; i++) sb_putc(sb, tmp[i]);
}

static void sb_put_i32(StrBuf *sb, long v) {
    if (v < 0) { sb_putc(sb, '-'); sb_put_u32(sb, (unsigned long)(-v)); }
    else sb_put_u32(sb, (unsigned long)v);
}

static void sb_put_hex8(StrBuf *sb, unsigned long v) {
    char tmp[8];
    mc_u32_to_hex8(v, tmp);
    for (int i = 0; i < 8; i++) sb_putc(sb, tmp[i]);
}

/* Writes a JSON string literal, with escaping, from a plain C string. */
static void sb_put_json_str(StrBuf *sb, const char *s) {
    sb_putc(sb, '"');
    if (s) {
        for (; *s; s++) {
            unsigned char c = (unsigned char)*s;
            if (c == '"' || c == '\\') { sb_putc(sb, '\\'); sb_putc(sb, (char)c); }
            else if (c == '\n') { sb_puts(sb, "\\n"); }
            else if (c == '\r') { sb_puts(sb, "\\r"); }
            else if (c == '\t') { sb_puts(sb, "\\t"); }
            else if (c < 0x20) {
                char h[2]; mc_u8_to_hex2(c, h);
                sb_puts(sb, "\\u00"); sb_putc(sb, h[0]); sb_putc(sb, h[1]);
            } else sb_putc(sb, (char)c);
        }
    }
    sb_putc(sb, '"');
}

/* ------------------------------------------------------------------ */
/* Minimal file append helper.                                         */
/* ------------------------------------------------------------------ */

static HANDLE mc_open_append(const char *path) {
    HANDLE h = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
                            NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    return h;
}

static void mc_write(HANDLE h, const char *data, int len) {
    DWORD written;
    WriteFile(h, data, (DWORD)len, &written, NULL);
}

/* GetCommandLineA gives the raw command line including argv[0]; this
   pulls out argv[1] (the first token after the program name) if present,
   handling a simple "quoted or not" split -- enough for this tool's one
   optional argument (a PID or a process-name substring, neither of which
   is expected to contain spaces in practice; quoting is still honoured if
   someone does pass one). Returns 1 and fills out (up to outCap-1 chars)
   if an argument was found, else returns 0. */
static int mc_get_arg1(char *out, int outCap) {
    const char *cl = GetCommandLineA();
    const char *p = cl;
    /* skip argv[0] -- quoted or not */
    if (*p == '"') {
        p++;
        while (*p && *p != '"') p++;
        if (*p == '"') p++;
    } else {
        while (*p && *p != ' ') p++;
    }
    while (*p == ' ') p++;
    if (!*p) return 0;
    int quoted = (*p == '"');
    if (quoted) p++;
    int i = 0;
    while (*p && i < outCap - 1 && (quoted ? (*p != '"') : (*p != ' '))) {
        out[i++] = *p++;
    }
    out[i] = 0;
    return i > 0;
}

#endif /* PAKON_MINICRT_H */
