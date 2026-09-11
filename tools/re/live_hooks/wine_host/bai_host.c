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
/* 32, matching v34's STACK_DWORDS_LOGGED, rather than the 25 that `arg_68h`
 * implies. Passing more dwords than the callee reads is harmless under
 * caller-cleans, and it removes the need to trust a disassembly reading of
 * which argument is the highest -- the exact kind of assumption that cost
 * §124 a run. */
#define BAI_ARGC 32
typedef int (__cdecl *bai_fn)(unsigned, unsigned, unsigned, unsigned, unsigned,
                              unsigned, unsigned, unsigned, unsigned, unsigned,
                              unsigned, unsigned, unsigned, unsigned, unsigned,
                              unsigned, unsigned, unsigned, unsigned, unsigned,
                              unsigned, unsigned, unsigned, unsigned, unsigned,
                              unsigned, unsigned, unsigned, unsigned, unsigned,
                              unsigned, unsigned);

static unsigned rd32(const unsigned char *p) {
    return (unsigned)p[0] | ((unsigned)p[1] << 8) |
           ((unsigned)p[2] << 16) | ((unsigned)p[3] << 24);
}

/* Which captured ranges were actually laid down. Reserved-but-never-written
 * memory reads as zeroes and is indistinguishable from a real all-zero buffer,
 * so "is this address backed by a DUMP" has to be tracked explicitly rather
 * than inferred from its contents. */
#define MAX_RANGES 262144
static struct { unsigned lo, hi; } g_ranges[MAX_RANGES];
static unsigned g_nranges;

static void mark_loaded(unsigned addr, unsigned len)
{
    if (g_nranges < MAX_RANGES) {
        g_ranges[g_nranges].lo = addr;
        g_ranges[g_nranges].hi = addr + len;
        g_nranges++;
    }
}

static int loaded(unsigned addr, unsigned len)
{
    unsigned i;
    for (i = 0; i < g_nranges; i++)
        if (g_ranges[i].lo <= addr && addr + len <= g_ranges[i].hi) return 1;
    return 0;
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
        if (addr >= HEAP_LO && addr + blen <= HEAP_HI) {
            memcpy((void *)(UINT_PTR)addr, blob + off, blen);
            mark_loaded(addr, blen);
        }
        off += blen;
    }
    unsigned ncalls = rd32(blob + off); off += 4;
    printf("buffers: %u   calls: %u\n\n", nbufs, ncalls);

    /* Re-initialise replayed CRITICAL_SECTIONs, named on argv[3..].
     *
     * A lock is process-local state, not data. Copying one in from a capture
     * reproduces whatever LockCount/OwningThread it had in the vendor process,
     * and if that says "held", the function blocks forever waiting for an
     * owner thread that does not exist here -- which is exactly what happened:
     *   RtlpWaitForCriticalSection section 08DB401C blocked by 0000
     * at 0% CPU, with no fault. (docs/74 SS124 read an earlier instance of
     * this as exception-dispatcher recursion. That was wrong: the repeated
     * stack frames are Wine's wait/retry chain.)
     *
     * Re-initialising is not fabricating an input: it restores the only state
     * a lock can legitimately have in a fresh single-threaded process. The
     * pixel data the function computes from is untouched. */
    for (int ai = 3; ai < argc; ai++) {
        unsigned la = (unsigned)strtoul(argv[ai], NULL, 0);
        if (la < HEAP_LO || la + sizeof(CRITICAL_SECTION) > HEAP_HI) {
            printf("lock %#x outside the reserved window -- skipped\n", la);
            continue;
        }
        InitializeCriticalSection((CRITICAL_SECTION *)(UINT_PTR)la);
        printf("re-initialised CRITICAL_SECTION @ %#x\n", la);
    }
    if (argc > 3) printf("\n");

    for (unsigned c = 0; c < ncalls; c++) {
        unsigned cid = rd32(blob + off); off += 4;
        unsigned nargs = rd32(blob + off); off += 4;
        unsigned a[BAI_ARGC];
        memset(a, 0, sizeof a);
        for (unsigned i = 0; i < nargs && i < BAI_ARGC; i++) { a[i] = rd32(blob + off); off += 4; }
        if (nargs > BAI_ARGC) off += 4 * (nargs - BAI_ARGC);

        /* arg0 is the `this` pointer. v34 adds a bai_this row, so the real
         * object should already be laid down at its captured address by the
         * buffer loop above -- in which case a[0] is used AS CAPTURED and
         * nothing here is fabricated.
         *
         * If it is absent (pre-v34 capture, or the dump came back unreadable),
         * fall back to a zeroed object and SAY SO on the row. A silent
         * fallback would let fabricated input masquerade as a real result,
         * which is exactly how §124's run would have misled if it had produced
         * numbers instead of faulting. */
        int thisReal = (a[0] >= HEAP_LO && a[0] < HEAP_HI && loaded(a[0], 2));
        if (!thisReal) a[0] = (unsigned)(UINT_PTR)calloc(1, 0x400);

        /* The shift slot BEFORE the call. bai_arg3 dumps 0x200 bytes from
         * arg3 -- which includes +0x0a -- and dumps fire on entry, so the
         * captured buffer already holds the vendor's shift. Reading the slot
         * after the call and finding the expected value therefore proves
         * NOTHING unless it changed: an untouched slot returns what was
         * loaded. Both values are printed so a tautological "match" is
         * visible rather than reported as a result. */
        short *shp = (short *)((unsigned char *)(UINT_PTR)a[3] + 0x0a);
        short pre[3] = { shp[0], shp[1], shp[2] };

        /* Snapshot every captured arg buffer, so that if the shift slot is
         * untouched we can still see WHERE the function put its output.
         * §106.1 says the shift write is gated on a value derived from this
         * function, so the value we actually want may be written into any of
         * these rather than returned. */
        static unsigned char snap[4][0x400];
        unsigned sidx[4] = { a[0], a[1], a[3], a[6] };
        unsigned slen[4] = { 0x200, 0x400, 0x200, 0x400 };
        for (int s = 0; s < 4; s++)
            if (loaded(sidx[s], slen[s]))
                memcpy(snap[s], (void *)(UINT_PTR)sidx[s], slen[s]);

        printf("  call %u:%s ", cid, thisReal ? "" : " [SYNTHETIC this]");
        int rc = bai(a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8],
                     a[9], a[10], a[11], a[12], a[13], a[14], a[15], a[16],
                     a[17], a[18], a[19], a[20], a[21], a[22], a[23], a[24],
                     a[25], a[26], a[27], a[28], a[29], a[30], a[31]);

        /* balance_shift_4b6 reads arg3+0x0a (docs/74 §95.1). */
        short *sh = shp;
        int changed = (sh[0] != pre[0]) || (sh[1] != pre[1]) || (sh[2] != pre[2]);
        printf("rc=%#x  pre=(%d,%d,%d) post=(%d,%d,%d) %s\n",
               (unsigned)rc, pre[0], pre[1], pre[2], sh[0], sh[1], sh[2],
               changed ? "WROTE" : "UNCHANGED(no proof)");

        static const char *snm[4] = { "this", "arg1", "arg3", "arg6" };
        for (int s = 0; s < 4; s++) {
            if (!loaded(sidx[s], slen[s])) continue;
            const unsigned char *now = (const unsigned char *)(UINT_PTR)sidx[s];
            unsigned first = 0xffffffff, last = 0, n = 0;
            for (unsigned o = 0; o < slen[s]; o++)
                if (now[o] != snap[s][o]) {
                    if (first == 0xffffffff) first = o;
                    last = o; n++;
                }
            if (n) {
                printf("        %s: %u bytes changed, offsets %#x..%#x",
                       snm[s], n, first, last);
                /* A 4-byte change at a dword boundary is almost certainly a
                 * pointer or count -- print both values. §108.2 identified the
                 * gate as a smart pointer whose NULL/non-NULL state decides
                 * whether the shift is written, so this dword is the thing the
                 * whole `k` question turns on. */
                if (n <= 4 && (first % 4) == 0 && first + 4 <= slen[s]) {
                    unsigned ov, nv;
                    memcpy(&ov, snap[s] + first, 4);
                    memcpy(&nv, now + first, 4);
                    printf("   [%#010x -> %#010x]%s", ov, nv,
                           nv ? "" : "  (NULL)");
                    /* If the new value is a pointer the DLL allocated during
                     * the call, its target is real memory in THIS process and
                     * can simply be read. §106.1's gate object is exactly
                     * this, and whatever `k` is derived from should be in it. */
                    if (s == 0 && first == 0 && nv && !IsBadReadPtr((void *)(UINT_PTR)nv, 0x40)) {
                        const unsigned *q = (const unsigned *)(UINT_PTR)nv;
                        printf("\n          gate object @%#x:", nv);
                        for (int w = 0; w < 16; w++) printf(" %08x", q[w]);
                    }
                }
                printf("\n");
            }
        }
    }
    free(blob);
    return 0;
}
