/*
 * mincrt.h -- the smallest possible string/formatting/allocation helpers,
 * built entirely on kernel32.dll, no CRT of any kind.
 *
 * WHY THIS EXISTS: an early build of hookdll.dll/injector.exe against this
 * project's Homebrew mingw-w64 toolchain, using ordinary stdio/wsprintfA/
 * lstrXxxA calls plus the default CRT startup, imported api-ms-win-crt-*.dll
 * (the Windows-10-era Universal CRT "API set" DLLs -- confirmed with
 * `objdump -p`, not assumed) EVEN with `-mcrtdll=msvcrt` explicitly passed
 * and even when explicitly linking `-lmsvcrt` -- this specific toolchain's
 * libmsvcrt.a itself resolves through the same UCRT API-set DLLs, so there
 * is no command-line flag on this toolchain that gets back to genuine
 * legacy `msvcrt.dll`. None of the `api-ms-win-crt-*.dll` files exist on
 * Windows XP, this project's real, confirmed target
 * (`docs/68-handover.md`: "shipped with 32-bit Windows XP-only drivers").
 * A binary built the "normal" way here would silently fail to even start
 * on the real XP box -- it looked fine under Wine only because Wine
 * happens to stub those API-set DLLs for compatibility, masking the exact
 * problem this file exists to avoid.
 *
 * The independently-built `../native/` harness (a different, hand-rolled
 * INT3-breakpoint approach explored earlier and NOT the one chosen -- see
 * README.md) hit this identical wall and solved it the identical way
 * (`../native/minicrt.h`); the technique here is the same one, written
 * fresh for this file's own (JSON-shaped) formatting needs rather than
 * sharing that file directly, so `win_inject/` stays self-contained.
 *
 * hookdll.c and injector.c are built with `-nostartfiles` plus a custom
 * entry point (see build.sh) specifically so even the CRT *startup*
 * object -- which pulls in CRT init/onexit machinery regardless of
 * whether application code calls any libc function -- never gets linked
 * in either. build.sh verifies with objdump, on every build, that the
 * result imports NOTHING but KERNEL32.dll.
 *
 * Deliberately boring: every function here does the obvious byte-at-a-time
 * thing. Nothing clever, nothing that needs a second reader to trust it.
 */
#ifndef WININJECT_MINCRT_H
#define WININJECT_MINCRT_H

#include <windows.h>

static int mc_strlen(const char *s) {
    int n = 0;
    while (s[n]) n++;
    return n;
}

static void mc_strcpy_n(char *dst, const char *src, int dstCap) {
    int i = 0;
    if (dstCap <= 0) return;
    for (; i < dstCap - 1 && src[i]; i++) dst[i] = src[i];
    dst[i] = 0;
}

static int mc_streq_ci(const char *a, const char *b) {
    for (;;) {
        char ca = *a, cb = *b;
        if (ca >= 'A' && ca <= 'Z') ca = (char)(ca - 'A' + 'a');
        if (cb >= 'A' && cb <= 'Z') cb = (char)(cb - 'A' + 'a');
        if (ca != cb) return 0;
        if (ca == 0) return 1;
        a++; b++;
    }
}

static char *mc_strchr(const char *s, char c) {
    for (; *s; s++) if (*s == c) return (char *)s;
    return NULL;
}

static int mc_isdigit(char c) { return c >= '0' && c <= '9'; }

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

/* Freestanding memcpy/memset -- MinHook's own vendored source (buffer.c,
 * hook.c, trampoline.c, hde32.c) calls both by name. build.sh compiles
 * those files with `-Dmemcpy=mc_memcpy -Dmemset=mc_memset` for the
 * freestanding (hookdll.dll) build only -- upstream MinHook source is
 * never modified (see vendor/minhook/VENDOR.md), only macro-redirected at
 * the call site via the compiler command line. */
static void *mc_memcpy(void *dst, const void *src, unsigned long n) {
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    while (n--) *d++ = *s++;
    return dst;
}

static void *mc_memset(void *dst, int v, unsigned long n) {
    unsigned char *d = (unsigned char *)dst;
    while (n--) *d++ = (unsigned char)v;
    return dst;
}

static void *mc_alloc(SIZE_T n) {
    return HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, n);
}

static void mc_free(void *p) {
    if (p) HeapFree(GetProcessHeap(), 0, p);
}

/* ------------------------------------------------------------------ */
/* Growable-but-bounded string buffer, used for both JSONL log lines   */
/* and injector.exe's console output.                                  */
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

static void sb_put_u32_dec(StrBuf *sb, unsigned long v) {
    char tmp[12];
    int n = 0;
    if (v == 0) { sb_putc(sb, '0'); return; }
    while (v > 0) { tmp[n++] = (char)('0' + (v % 10)); v /= 10; }
    while (n > 0) sb_putc(sb, tmp[--n]);
}

/* Zero-padded to exactly `width` digits (e.g. width=2 -> "07"; width=4 ->
 * "0026"). Assumes v fits in `width` digits -- fine for the calendar
 * fields this is used for (month/day/hour/minute/second all < 100). */
static void sb_put_u32_dec_padded(StrBuf *sb, unsigned long v, int width) {
    char tmp[12];
    int n = 0;
    while (v > 0) { tmp[n++] = (char)('0' + (v % 10)); v /= 10; }
    while (n < width) tmp[n++] = '0';
    while (n > 0) sb_putc(sb, tmp[--n]);
}

static void sb_put_i32_dec(StrBuf *sb, long v) {
    if (v < 0) { sb_putc(sb, '-'); sb_put_u32_dec(sb, (unsigned long)(-v)); }
    else sb_put_u32_dec(sb, (unsigned long)v);
}

static void sb_put_hex8(StrBuf *sb, unsigned long v) {
    static const char *hexd = "0123456789abcdef";
    char tmp[8];
    int i;
    for (i = 7; i >= 0; i--) { tmp[i] = hexd[v & 0xF]; v >>= 4; }
    for (i = 0; i < 8; i++) sb_putc(sb, tmp[i]);
}

/* `"0xXXXXXXXX"` -- quoted, matches the convention used for every
 * address/pointer field in the JSONL schema (see hookcore.c). */
static void sb_put_hex8_quoted(StrBuf *sb, unsigned long v) {
    sb_putc(sb, '"'); sb_puts(sb, "0x"); sb_put_hex8(sb, v); sb_putc(sb, '"');
}

/* Writes a JSON string literal, with escaping, from a plain C string. */
static void sb_put_json_str(StrBuf *sb, const char *s) {
    sb_putc(sb, '"');
    if (s) {
        for (; *s; s++) {
            unsigned char c = (unsigned char)*s;
            if (c == '"' || c == '\\') { sb_putc(sb, '\\'); sb_putc(sb, (char)c); }
            else if (c == '\n') sb_puts(sb, "\\n");
            else sb_putc(sb, (char)c);
        }
    }
    sb_putc(sb, '"');
}

/* ------------------------------------------------------------------ */
/* File I/O + console output helpers.                                  */
/* ------------------------------------------------------------------ */

static void mc_console_write(const char *s) {
    HANDLE h = GetStdHandle(STD_OUTPUT_HANDLE);
    DWORD written;
    if (h != NULL && h != INVALID_HANDLE_VALUE) {
        WriteFile(h, s, (DWORD)mc_strlen(s), &written, NULL);
    }
}

/* GetCommandLineA gives the raw command line including argv[0]. These
 * pull out the Nth space-or-quote-delimited token after argv[0] (1-based)
 * -- enough for injector.exe's two required arguments (a PID/process
 * name, and a DLL path), neither of which is expected to contain spaces
 * in the common case; quoting is honoured if one does. */
static const char *mc_skip_token(const char *p) {
    while (*p == ' ') p++;
    if (*p == '"') {
        p++;
        while (*p && *p != '"') p++;
        if (*p == '"') p++;
    } else {
        while (*p && *p != ' ') p++;
    }
    return p;
}

static int mc_get_argn(int n, char *out, int outCap) {
    const char *p = GetCommandLineA();
    int i;
    p = mc_skip_token(p); /* skip argv[0] */
    for (i = 1; i < n; i++) {
        while (*p == ' ') p++;
        if (!*p) return 0;
        p = mc_skip_token(p);
    }
    while (*p == ' ') p++;
    if (!*p) return 0;
    {
        int quoted = (*p == '"');
        int j = 0;
        if (quoted) p++;
        while (*p && j < outCap - 1 && (quoted ? (*p != '"') : (*p != ' '))) {
            out[j++] = *p++;
        }
        out[j] = 0;
        return j > 0;
    }
}

#endif /* WININJECT_MINCRT_H */
