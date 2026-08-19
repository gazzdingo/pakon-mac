/* Call the REAL balance_area_image under Wine, to recover `k`.
 *
 * WHY
 * ---
 * docs/74 §121/§122: `setShifts` feeds FUGC's per-channel LUT offset, so a
 * wrong shift becomes a wrong per-channel transfer SHAPE — which is R's
 * symptom. Every other FUGC input is verified correct (§122.1, now including
 * `aTableDmin = (500,500,500)` read from the vendor's own runtime state), so
 * `setShifts = A + k` is the only remaining wrong input, and `k` is unknown.
 *
 * §106.1 showed the shift write is gated on a value derived from
 * `balance_area_image`, and §113 eliminated every capturable input as a
 * predictor of `k` — leaving `k` as something the function computes from the
 * pixels. Reproducing it therefore means running the function.
 *
 * WHAT MAKES THIS POSSIBLE NOW
 * ----------------------------
 * v32 finally dumped arg1/arg3/arg6 (§108.1 recorded that their absence was
 * the blocker). Of the two remaining pointers:
 *
 *   arg5  (0x6d13d50) — already covered by an unrelated `vm_prog1` dump, 808
 *                       bytes from that address onward. Captures routinely
 *                       contain more than the rows that asked for them.
 *   arg0  (== ecx, the `this`) — not dumped at all.
 *
 * `this` is nevertheless survivable: the whole 1505-line disassembly contains
 * exactly ONE `this`-relative access, `[esi + 0x74]`, the refcount slot. The
 * function works through its arguments. So a zeroed `this` is supplied and
 * the run is expected to reach real arithmetic rather than fault on entry.
 *
 * WHAT WOULD MAKE THIS DISHONEST
 * ------------------------------
 * A zeroed `this` is fabricated input. If the function reads it in a way that
 * changes the result, the answer is wrong and would look fine. The host
 * therefore reports the return value AND the shift slot for every call, so a
 * constant or obviously-degenerate result is visible rather than assumed. A
 * `k` recovered here is a HYPOTHESIS until it reproduces the per-frame values
 * §105 measured from the captures.
 *
 * BUILD/RUN: see README.md.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BAI_RVA 0x00102B20u        /* fcn.10102b20, hooked since v20 */

#define HEAP_LO 0x06000000u
#define HEAP_HI 0x10000000u

/* The epilogue is a bare `c3` (caller-cleans) => __cdecl, so a wider prototype
 * than the real one is safe to call through. The function references `arg_68h`
 * (ebp+0x68, arg #24), so it is ~25 dwords wide; v32 captured 16. Args 16..24
 * are passed as zero and are FABRICATED — see the note in main(). */
#define BAI_ARGC 25
typedef int (__cdecl *bai_fn)(unsigned, unsigned, unsigned, unsigned, unsigned,
                              unsigned, unsigned, unsigned, unsigned, unsigned,
                              unsigned, unsigned, unsigned, unsigned, unsigned,
                              unsigned, unsigned, unsigned, unsigned, unsigned,
                              unsigned, unsigned, unsigned, unsigned, unsigned);

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
    /* Unbuffered: a fault mid-run must not swallow the progress that located
     * it. Block-buffered stdout to a file hid exactly that on the first run. */
    setvbuf(stdout, NULL, _IONBF, 0);

    if (argc < 3) { printf("usage: bai_host.exe <dll> <bai.bin>\n"); return 2; }

    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) { printf("LoadLibrary failed: %lu\n", (unsigned long)GetLastError()); return 1; }
    bai_fn bai = (bai_fn)((unsigned char *)h + BAI_RVA);
    printf("loaded %p   balance_area_image %p\n", (void *)h, (void *)bai);

    /* One reservation covering every captured address (docs/74 §  wine_host
     * README: per-buffer reservations fragment and then collide). */
    if (!VirtualAlloc((LPVOID)(UINT_PTR)HEAP_LO, HEAP_HI - HEAP_LO,
                      MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE)) {
        printf("reserve %#x..%#x failed: %lu\n", HEAP_LO, HEAP_HI,
               (unsigned long)GetLastError());
        return 1;
    }

    long len = 0;
    unsigned char *blob = slurp(argv[2], &len);
    if (!blob) { printf("cannot read %s\n", argv[2]); return 1; }

    /* Memory first, once: the whole capture's buffers at their captured
     * addresses. arg5 is only reachable because a `vm_prog1` dump contains it,
     * so containment must be preserved rather than relocated. */
    printf("blob %ld bytes\n", len);
    unsigned off = 0, nbufs = rd32(blob + off); off += 4;
    for (unsigned b = 0; b < nbufs; b++) {
        unsigned addr = rd32(blob + off); off += 4;
        unsigned blen = rd32(blob + off); off += 4;
        if (addr >= HEAP_LO && addr + blen <= HEAP_HI)
            memcpy((void *)(UINT_PTR)addr, blob + off, blen);
        off += blen;
    }
    unsigned ncalls = rd32(blob + off); off += 4;
    printf("buffers: %u   calls: %u\n\n", nbufs, ncalls);

    for (unsigned c = 0; c < ncalls; c++) {
        unsigned cid = rd32(blob + off); off += 4;
        unsigned nargs = rd32(blob + off); off += 4;
        unsigned a[BAI_ARGC];
        memset(a, 0, sizeof a);
        for (unsigned i = 0; i < nargs && i < BAI_ARGC; i++) { a[i] = rd32(blob + off); off += 4; }
        if (nargs > BAI_ARGC) off += 4 * (nargs - BAI_ARGC);

        /* arg0 is the `this` pointer and is the ONE pointer arg no dump covers.
         * A zeroed object is supplied. Combined with the zeroed args 16..24,
         * this run has FABRICATED INPUTS and its numbers are not evidence of
         * anything until they reproduce §105's per-frame values. */
        a[0] = (unsigned)(UINT_PTR)calloc(1, 0x400);

        printf("  call %u: ", cid);
        int rc = bai(a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8],
                     a[9], a[10], a[11], a[12], a[13], a[14], a[15], a[16],
                     a[17], a[18], a[19], a[20], a[21], a[22], a[23], a[24]);

        /* balance_shift_4b6 reads arg3+0x0a (docs/74 §95.1). */
        short *sh = (short *)((unsigned char *)(UINT_PTR)a[3] + 0x0a);
        printf("rc=%d (%#x)   shift@arg3+0xa = (%d, %d, %d)\n",
               rc, (unsigned)rc, sh[0], sh[1], sh[2]);
    }
    free(blob);
    return 0;
}
