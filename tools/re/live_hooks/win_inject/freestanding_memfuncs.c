/*
 * freestanding_memfuncs.c -- real memcpy/memset, real external linkage,
 * used ONLY to satisfy vendored MinHook's own direct calls to those two
 * functions (confirmed via `nm -u` on buffer.o/hook.o/trampoline.o/
 * hde32.o: `_memcpy`/`_memset` are genuine undefined references, not
 * something GCC inlines away even with `-fno-builtin -ffreestanding`).
 *
 * WHY ITS OWN TRANSLATION UNIT, WITH NO windows.h ANYWHERE IN IT
 * ------------------------------------------------------------------
 * A first attempt macro-redirected MinHook's calls at the compiler
 * command line (`-Dmemcpy=mc_memcpy -Dmemset=mc_memset -include
 * mincrt.h`) so they'd resolve to hand-written freestanding
 * implementations instead of pulling in a CRT DLL. That failed to even
 * compile: mingw-w64's own `string.h` (pulled in transitively by
 * `windows.h`, which mincrt.h itself includes) ALSO declares (and, in
 * some configurations, defines inline) `memcpy`/`memset` with
 * `__restrict__`-qualified parameters -- since a `-D` command-line macro
 * substitutes that literal token EVERYWHERE in the translation unit,
 * including inside system headers, this produced a real "conflicting
 * types" compile error between mingw's own declaration (post-rename) and
 * this project's differently-qualified definition, not just a stylistic
 * clash.
 *
 * The clean fix: don't rename anything, and don't let this file's own
 * translation unit see mingw's memcpy/memset declaration at all. This
 * file includes ONLY `<stddef.h>` (a genuinely freestanding-safe header,
 * for `size_t` -- it does not declare memcpy/memset) and defines
 * `memcpy`/`memset` with their real, standard names and real external
 * linkage. MinHook's own `.c` files are compiled completely normally
 * (their own `windows.h`/`string.h` inclusions see the usual mingw
 * declarations, exactly as upstream intends -- vendor/minhook/VENDOR.md:
 * nothing in `vendor/minhook/` is modified). At LINK time, this file's
 * exported `_memcpy`/`_memset` symbols satisfy MinHook's undefined
 * references -- object-file symbol resolution doesn't care about
 * `restrict`/inline attributes that only matter at compile time, so
 * there's no conflict there. Standard C (`-ffreestanding`, C11 4p6)
 * explicitly allows a freestanding program to supply its own
 * implementations of function names like these instead of linking a
 * standard library at all -- this is exactly that, not a hack.
 */
#include <stddef.h>

void *memcpy(void *dst, const void *src, size_t n) {
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    while (n--) *d++ = *s++;
    return dst;
}

void *memset(void *dst, int v, size_t n) {
    unsigned char *d = (unsigned char *)dst;
    while (n--) *d++ = (unsigned char)v;
    return dst;
}
