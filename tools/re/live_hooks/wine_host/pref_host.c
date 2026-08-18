/* Call the REAL sba_preference in the REAL PakonIMAu.dll, under Wine.
 *
 * WHY
 * ---
 * docs/74 SS97 emulated fcn.1028c780 under Unicorn and got 3 of 6 frames
 * within +-1. SS98 found why: Emu.place() maps whole 4 KB pages and poison-
 * fills them, so reads past a 100-byte dump but inside its page are silent --
 * and Preference reads to arg0+0x1e4 while the capture holds 0x64. 384 bytes
 * of every call have been supplied as 0xCD.
 *
 * Unicorn cannot fix that; only a bigger capture can. But Unicorn brings its
 * own risks that this host removes entirely:
 *
 *   - 471 bound imports stubbed by hand (MSVCR71/MSVCP71). Here the real CRT
 *     is loaded by the real loader.
 *   - a hand-rolled FPU control word. Here it is whatever the DLL sets.
 *   - poison semantics that hide short dumps at read time (SS98.1).
 *
 * So this is the cross-check: same inputs, same function, two independent
 * execution engines. Agreement means the Unicorn port is sound and the only
 * remaining deficit is captured data. Disagreement means the emulator is
 * wrong, which is worth knowing before any more is built on it.
 *
 * BUILD (see build.sh):
 *   i686-w64-mingw32-gcc -O2 -o pref_host.exe pref_host.c
 * RUN:
 *   wine pref_host.exe <PakonIMAu.dll> <args.bin>
 *
 * args.bin layout, little-endian, written by pref_host_gen.py:
 *   u32 n_calls
 *   per call:  u32 n_args, u32 args[n_args],
 *              u32 n_bufs, per buf: u32 arg_index, u32 len, u8 data[len]
 *
 * Nothing is written back to any capture; the host prints and exits.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

/* fcn.1028c780 at the DLL's preferred base 0x10000000. Resolved as an RVA
 * against the ACTUAL load address, so a relocated load is still correct. */
#define PREFERENCE_RVA 0x0028C780u
#define PREFERRED_BASE 0x10000000u

typedef int (__cdecl *pref_fn)(void *, void *, void *, void *, int, void *,
                               void *, void *, void *, void *, void *, void *);

static unsigned char *slurp(const char *path, long *out_len)
{
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    unsigned char *b = malloc((size_t)n);
    if (b && fread(b, 1, (size_t)n, f) != (size_t)n) { free(b); b = NULL; }
    fclose(f);
    if (out_len) *out_len = n;
    return b;
}

static unsigned rd32(const unsigned char *p) {
    return (unsigned)p[0] | ((unsigned)p[1] << 8) |
           ((unsigned)p[2] << 16) | ((unsigned)p[3] << 24);
}

int main(int argc, char **argv)
{
    if (argc < 3) {
        printf("usage: pref_host.exe <PakonIMAu.dll> <args.bin>\n");
        return 2;
    }

    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) {
        printf("LoadLibrary failed: %lu\n", (unsigned long)GetLastError());
        return 1;
    }
    printf("loaded at %p (preferred %#x)\n", (void *)h, PREFERRED_BASE);

    pref_fn preference = (pref_fn)((unsigned char *)h + PREFERENCE_RVA);
    printf("sba_preference at %p\n", (void *)preference);

    long len = 0;
    unsigned char *blob = slurp(argv[2], &len);
    if (!blob) { printf("cannot read %s\n", argv[2]); return 1; }

    unsigned off = 0;
    unsigned ncalls = rd32(blob + off); off += 4;
    printf("calls: %u\n", ncalls);

    for (unsigned c = 0; c < ncalls; c++) {
        unsigned nargs = rd32(blob + off); off += 4;
        unsigned args[32];
        for (unsigned i = 0; i < nargs && i < 32; i++) {
            args[i] = rd32(blob + off); off += 4;
        }
        unsigned nbufs = rd32(blob + off); off += 4;

        /* Allocate each buffer at a fresh address and REWRITE the arg to
         * point at it -- the captured pointers are another process's, so
         * they cannot be honoured here. Relative offsets within a buffer
         * are preserved, which is what the function actually uses. */
        void *bufptr[32];
        unsigned buflen[32];
        int scratch[32];
        for (unsigned i = 0; i < 32; i++) {
            bufptr[i] = NULL; buflen[i] = 0; scratch[i] = 0;
        }

        for (unsigned b = 0; b < nbufs; b++) {
            unsigned ai  = rd32(blob + off); off += 4;
            unsigned blen = rd32(blob + off); off += 4;
            /* Over-allocate and zero: Preference reads past the dumped
             * bytes (docs/74 SS98) and this host must not pretend otherwise.
             * Zero, not poison -- a Windows heap read of uninitialised
             * memory would fault or vary; zero is at least deterministic,
             * and the DIFFERENCE from the Unicorn run is the signal. */
            unsigned alloc = blen < 0x1000 ? 0x1000 : blen + 0x1000;
            unsigned char *p = calloc(1, alloc);
            memcpy(p, blob + off, blen);
            off += blen;
            if (ai < 32) { bufptr[ai] = p; buflen[ai] = blen; }
        }

        /* Any arg that looks like a captured heap pointer but has no dump
         * still needs VALID memory: the function writes through several of
         * them (e.g. the anchor/shift at arg2+0x02/+0x08). Give those a
         * zeroed scratch page. A captured pointer left as-is would fault --
         * as it did before this was added -- and, worse, a *wild* one could
         * silently corrupt. Range check keeps scalars (0, small ints) alone. */
        for (unsigned i = 0; i < nargs && i < 32; i++) {
            if (!bufptr[i] && args[i] >= 0x08000000u && args[i] < 0x0A000000u) {
                bufptr[i] = calloc(1, 0x2000);
                scratch[i] = 1;
            }
        }

        void *a[12];
        for (unsigned i = 0; i < 12; i++)
            a[i] = (i < nargs) ? (bufptr[i] ? bufptr[i] : (void *)(UINT_PTR)args[i])
                               : NULL;

        int rc = preference(a[0], a[1], a[2], a[3], (int)(UINT_PTR)a[4],
                            a[5], a[6], a[7], a[8], a[9], a[10], a[11]);

        /* The shift is written at arg2+0x08, the anchor at arg2+0x02
         * (docs/74 SS97.1). */
        if (bufptr[2]) {
            short *w = (short *)((unsigned char *)bufptr[2]);
            printf("  call %u: rc=%d  anchor=(%d, %d, %d)  shift=(%d, %d, %d)\n",
                   c, rc, w[1], w[2], w[3], w[4], w[5], w[6]);
        } else {
            printf("  call %u: rc=%d  (arg2 not supplied)\n", c, rc);
        }
    }

    free(blob);
    return 0;
}
