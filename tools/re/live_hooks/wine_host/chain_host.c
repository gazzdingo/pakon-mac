/* Chain the REAL vendor calls under Wine: orderFpo -> preference.
 *
 * WHY
 * ---
 * docs/74 SS98: sba_preference reads to arg0+0x1e4 but the capture holds only
 * 0x64, so 384 bytes of every call have been fed as garbage. SS99 confirmed
 * both execution engines are correct, so the deficit is DATA, not code.
 *
 * The fix does not have to be a new capture. fcn.1028b8d0 (orderFpo) WRITES
 * into exactly that region -- a write trace shows it filling
 * scene+0x3888..+0x3a2c, which is where preference's arg0 window lives. So if
 * both calls share ONE scene allocation, orderFpo manufactures the bytes
 * preference needs and the gap closes with no hardware at all.
 *
 * THE ONE THING THAT MAKES THIS WORK
 * ----------------------------------
 * A single contiguous allocation for the whole 25 820-byte scene struct, with
 * every captured buffer written at its REAL offset within it. The captured
 * pointers are another process's, so absolute addresses are useless -- but the
 * OFFSETS between them are exactly what the code uses, and those survive:
 *
 *     scene_base   = fpo_calc arg12 - 0x38a2      (docs/74 SS73.4/SS74.2)
 *     pref arg0    = scene_base + 0x3888          (measured, this capture)
 *
 * Args that point inside the scene are rebased into our allocation; args that
 * point elsewhere get their own buffer.
 *
 * WHAT WOULD MAKE THIS DISHONEST, AND IS THEREFORE CHECKED
 * -------------------------------------------------------
 * If orderFpo does not write the whole 0x1e4 window, the untouched remainder
 * is still fabricated -- zeroed heap rather than real data. So the host
 * reports how many of those 484 bytes orderFpo actually wrote. A result that
 * matches the vendor while half the window was never written is not a result;
 * it is a coincidence, and the count is printed so that can be seen rather
 * than assumed.
 *
 * BUILD/RUN: see README.md.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ORDERFPO_RVA   0x0028B8D0u
#define PREFERENCE_RVA 0x0028C780u

#define SCENE_SIZE     25820u        /* cn_enhanced_driver arg1 stride */
#define TRIPLE_OFF     0x38A2u       /* orderFpo writes its triple here    */
#define PREF_ARG0_OFF  0x38A2u       /* == fpo arg12: preference.arg0 IS the triple */
#define PREF_READ_LEN  0x1E4u        /* how far preference reads (SS98)    */

typedef int (__cdecl *fpo_fn)(void *, void *, void *, int, int, void *, void *,
                              void *, void *, void *, void *, void *, void *);
typedef int (__cdecl *pref_fn)(void *, void *, void *, void *, int, void *,
                               void *, void *, void *, void *, void *, void *);

static unsigned rd32(const unsigned char *p) {
    return (unsigned)p[0] | ((unsigned)p[1] << 8) |
           ((unsigned)p[2] << 16) | ((unsigned)p[3] << 24);
}

static unsigned char *slurp(const char *path, long *n)
{
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END); *n = ftell(f); fseek(f, 0, SEEK_SET);
    unsigned char *b = malloc((size_t)*n);
    if (b && fread(b, 1, (size_t)*n, f) != (size_t)*n) { free(b); b = NULL; }
    fclose(f);
    return b;
}

int main(int argc, char **argv)
{
    if (argc < 3) { printf("usage: chain_host.exe <dll> <chain.bin>\n"); return 2; }

    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) { printf("LoadLibrary failed: %lu\n", (unsigned long)GetLastError()); return 1; }
    fpo_fn  orderfpo  = (fpo_fn )((unsigned char *)h + ORDERFPO_RVA);
    pref_fn preference = (pref_fn)((unsigned char *)h + PREFERENCE_RVA);
    printf("loaded %p  orderFpo %p  preference %p\n",
           (void *)h, (void *)orderfpo, (void *)preference);

    /* Reserve the whole captured-heap range ONCE. Per-buffer reservations
     * fragment and then collide (observed: a later buffer spilling past an
     * earlier, smaller reservation faults inside memcpy). One span covering
     * every address the capture can contain removes the class of error. */
    #define HEAP_LO 0x08000000u
    #define HEAP_HI 0x0A000000u
    if (!VirtualAlloc((LPVOID)(UINT_PTR)HEAP_LO, HEAP_HI - HEAP_LO,
                      MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)) {
        printf("cannot reserve %#x..%#x: %lu\n", HEAP_LO, HEAP_HI,
               (unsigned long)GetLastError());
        return 1;
    }
    printf("reserved %#x..%#x for captured buffers\n", HEAP_LO, HEAP_HI);

    long len = 0;
    unsigned char *blob = slurp(argv[2], &len);
    if (!blob) { printf("cannot read %s\n", argv[2]); return 1; }

    unsigned off = 0;
    unsigned ncalls = rd32(blob + off); off += 4;
    printf("scenes: %u\n\n", ncalls);

    for (unsigned c = 0; c < ncalls; c++) {
        unsigned scene_lo = rd32(blob + off); off += 4;   /* captured scene base */
        unsigned nargs_f  = rd32(blob + off); off += 4;
        unsigned fa[24];
        for (unsigned i = 0; i < nargs_f && i < 24; i++) { fa[i] = rd32(blob + off); off += 4; }
        unsigned nargs_p  = rd32(blob + off); off += 4;
        unsigned pa[24];
        for (unsigned i = 0; i < nargs_p && i < 24; i++) { pa[i] = rd32(blob + off); off += 4; }

        /* Map every captured buffer AT ITS ORIGINAL ADDRESS.
         *
         * Rebasing into a local allocation looks tidier and is wrong: any
         * pointer stored INSIDE a captured buffer still refers to the
         * original address space, so a rebased struct hands the DLL stale
         * pointers. (Observed: orderFpo early-exits rc=6300 having written
         * nothing.) Unicorn sidesteps this by mapping at real addresses;
         * VirtualAlloc with an explicit base does the same under Wine, and
         * keeps every internal pointer valid for free. */
        unsigned nbufs = rd32(blob + off); off += 4;
        unsigned char *scene = NULL;

        for (unsigned b = 0; b < nbufs; b++) {
            unsigned ai   = rd32(blob + off); off += 4;
            unsigned addr = rd32(blob + off); off += 4;
            unsigned blen = rd32(blob + off); off += 4;
            const unsigned char *data = blob + off; off += blen;
            (void)ai;
            if (addr < HEAP_LO || addr + blen > HEAP_HI) {
                printf("  scene %u: buffer %#x+%#x outside the reserved "
                       "range -- skipped\n", c, addr, blen);
                continue;
            }
            memcpy((void *)(UINT_PTR)addr, data, blen);
        }

        scene = (unsigned char *)(UINT_PTR)scene_lo;   /* inside the reservation */

        /* Snapshot the window preference will read, so we can count what
         * orderFpo actually writes into it. */
        unsigned char before[PREF_READ_LEN];
        memcpy(before, scene + PREF_ARG0_OFF, PREF_READ_LEN);

        /* Resolve an fpo/pref arg to a real address in this process. */
        /* Every pointer is valid at its own captured value now. */
        void *fx[16];
        for (unsigned i = 0; i < 16; i++)
            fx[i] = (i < nargs_f) ? (void *)(UINT_PTR)fa[i] : NULL;

        int rcf = orderfpo(fx[0], fx[1], fx[2], (int)(UINT_PTR)fx[3],
                           (int)(UINT_PTR)fx[4], fx[5], fx[6], fx[7], fx[8],
                           fx[9], fx[10], fx[11], fx[12]);

        unsigned written = 0;
        for (unsigned i = 0; i < PREF_READ_LEN; i++)
            if (before[i] != scene[PREF_ARG0_OFF + i]) written++;

        short *tri = (short *)(scene + TRIPLE_OFF);

        void *px[12];
        for (unsigned i = 0; i < 12; i++)
            px[i] = (i < nargs_p) ? (void *)(UINT_PTR)pa[i] : NULL;
        if (!px[2]) px[2] = calloc(1, 0x2000);

        int rcp = preference(px[0], px[1], px[2], px[3], (int)(UINT_PTR)px[4],
                             px[5], px[6], px[7], px[8], px[9], px[10], px[11]);

        short *w = (short *)px[2];
        printf("  scene %u: fpo rc=%d triple=(%d,%d,%d)  pref rc=%d "
               "shift=(%d,%d,%d)  [orderFpo wrote %u/%u of pref's window]\n",
               c, rcf, tri[0], tri[1], tri[2], rcp, w[4], w[5], w[6],
               written, PREF_READ_LEN);
    }

    free(blob);
    return 0;
}
