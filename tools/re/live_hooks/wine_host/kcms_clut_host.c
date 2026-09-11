/* kcms_clut_host.exe -- drive the REAL Kodak CMM (kodakcms.dll, md5
 * e4c8064a9dd3c3a5541d74b00a730e53) under Wine, and additionally reach
 * INSIDE it to the one function that actually interpolates the 3-D CLUT.
 *
 * Background
 * ----------
 * docs/74 §171 established that this port's PIL/littleCMS ICC step is not
 * bit-exact against the vendor's own CMM, and that the residual is a 3-D
 * CLUT interpolation difference rather than a per-channel remap.
 *
 * SpEvaluate (0x1002ecf0) -> PTEvalDT (0x10041070) -> fcn.100410a0 ->
 * fcn.10026d20 -> fcn.10012b30 -> fcn.10012bc0.  fcn.10012bc0 is a pure
 * dispatcher: it returns ONE function pointer out of 35 candidates, which
 * the tile loop fcn.10027410 then calls as `call dword [ebx + 4]`.
 *
 * WHICH candidate is live was settled dynamically, not by reading names:
 * POKE_RVA below overwrites a candidate's first byte with 0xC3 (`ret`;
 * the ABI is cdecl so a bare ret is safe) and the caller re-runs the whole
 * transform.  Exactly one of the 35 changes SpEvaluate's output:
 *
 *     0x10018160
 *
 * Its signature, from the two call sites at 0x10027499 and 0x100275f9
 * (`call dword [ebx+4]` followed by `add esp, 0x20`, i.e. cdecl/8 args):
 *
 *   int __cdecl eval(void **inPlanes,  void *inSteps,  int inColorSpace,
 *                    void **outPlanes, void *outSteps, int outColorSpace,
 *                    int nPixels,      void *grid);
 *
 * `grid` is the per-stage data block.  The evaluator reads exactly four
 * things out of it, all pointers into heap the DLL built at combine time:
 *
 *   grid+0x8c   3 x 256 x {int32 byteOffset, int32 weight}  input index table
 *   grid+0xf0   the CLUT itself, u16, output-channel-interleaved
 *   grid+0x154  3 x 16384 u8                                output tables
 *   grid+0x188..0x1a0  the seven cube-corner byte offsets
 *                      (B, G, GB, R, RB, RG, RGB)
 *
 * MODES
 * -----
 *   probe <p.pf>
 *       enumerate SpXformGet(intent, class) for one profile.
 *
 *   run <p1.pf> <p2.pf> <in.bin> <out.bin> <iA> <cA> <iB> <cB>
 *       combine the two xforms and SpEvaluate an interleaved RGB u8 buffer.
 *       in.bin  : int32 n, then n*3 uint8
 *       out.bin : int32 rc, int32 n, then n*3 uint8
 *
 * ENV
 * ---
 *   KCMS_DLL   dll to load (default kodakcms.dll from the cwd)
 *   DUMP_DIR   install the detour on 0x10018160 and write the four tables
 *              (grid_struct.bin, idxtab.bin, clut.bin, otab.bin,
 *              grid_meta.txt) into this directory on the first call
 *   POKE_RVA   write 0xC3 at this VA before running (dispatch sweep)
 *   SHAPE_H    describe the same buffer as nLines=H instead of 1
 *   EVAL_MODE=two   chain the two xforms explicitly instead of combining
 *
 * The detour is transparent: it restores the original bytes before
 * delegating, so the vendor output with DUMP_DIR set is byte-identical to
 * the vendor output without it (the golden harness asserts this).
 *
 * BUILD: i686-w64-mingw32-gcc -O1 -o kcms_clut_host.exe kcms_clut_host.c
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define EVAL_VA 0x10018160UL

typedef int (__stdcall *SpInit_t)(void*, void*, void*);
typedef int (__stdcall *SpInitThread_t)(void*, void*, void*);
typedef int (__stdcall *SpLoad_t)(void*, const char*, int, void**);
typedef int (__stdcall *SpXformGet_t)(void*, int, int, void**);
typedef int (__stdcall *SpCombine_t)(int, void**, void*, void*, void*, void*);
typedef int (__stdcall *SpEval_t)(void*, void*, void*, void*, void*);
typedef int (__stdcall *SpChans_t)(void*, int*, int*);
typedef int (__stdcall *SpErrTxt_t)(int, int, char*);

static HMODULE H;
static SpInit_t        pInit;
static SpInitThread_t  pInitThread;
static SpLoad_t        pLoad;
static SpXformGet_t    pXformGet;
static SpCombine_t     pCombine;
static SpEval_t        pEval;
static SpChans_t       pChans;
static SpErrTxt_t      pErrTxt;

typedef struct {
    int dataType, w, h, pixStep, lineStep, nChan;
    void *chan[8];
} SpImg;

static void *load_sym(const char *n) {
    void *p = (void*)GetProcAddress(H, n);
    if (!p) { printf("MISSING %s\n", n); exit(2); }
    return p;
}

/* SpInitialize's arg1 is &outHandle: SpInitializeEx writes
 * getHandleFromPtr(...) through it at 0x10033e21. That handle is what
 * SpProfileLoadProfile takes as its own arg1. */
static void *g_cms;

static int init_cms(void) {
    static void *h[8];
    int rc = pInit(h, NULL, NULL);
    printf("SpInitialize(&h,0,0) = %d  handle=%p\n", rc, h[0]);
    g_cms = h[0];
    printf("SpInitThread(h,0,0)  = %d\n", pInitThread(g_cms, NULL, NULL));
    return rc;
}

/* ------------------------------------------------------------------ */
/* detour on the live evaluator                                        */
/* ------------------------------------------------------------------ */
typedef int (__cdecl *ev_t)(void**, void*, int, void**, void*, int, int, void*);
static unsigned char *g_ev;
static unsigned char  g_save[6];
static int  g_dumped = 0;
static const char *g_dumpdir = NULL;

static void wrmem(void *dst, const void *src, size_t n) {
    DWORD o;
    VirtualProtect(dst, n, PAGE_EXECUTE_READWRITE, &o);
    memcpy(dst, src, n);
}

static void put(const char *name, const void *p, size_t n) {
    char path[512];
    FILE *f;
    sprintf(path, "%s/%s", g_dumpdir, name);
    f = fopen(path, "wb");
    if (!f) { printf("  ! cannot write %s\n", path); return; }
    fwrite(p, 1, n, f);
    fclose(f);
    printf("  wrote %s (%u bytes)\n", name, (unsigned)n);
}

static void dump_grid(void *grid, void **in, void **out, int n) {
    unsigned char *g = (unsigned char *)grid;
    int *gi = (int *)grid;
    int i, gridN, clutBytes;
    int offB   = gi[0x188/4], offG  = gi[0x18c/4], offGB = gi[0x190/4];
    int offR   = gi[0x194/4], offRB = gi[0x198/4], offRG = gi[0x19c/4];
    int offRGB = gi[0x1a0/4];
    void *idxtab = (void*)gi[0x8c/4];
    void *clut   = (void*)gi[0xf0/4];
    void *otab   = (void*)gi[0x154/4];
    char path[512];
    FILE *f;

    printf("=== evaluator 0x%08lx grid dump (n=%d) ===\n", EVAL_VA, n);
    printf("  grid=%p idxtab=%p clut=%p otab=%p\n", grid, idxtab, clut, otab);
    printf("  corner offsets: B=%d G=%d GB=%d R=%d RB=%d RG=%d RGB=%d\n",
           offB, offG, offGB, offR, offRB, offRG, offRGB);
    for (i = 0; i < 8; i++)
        printf("  inPlane[%d]=%p  outPlane[%d]=%p\n", i, in[i], i, out[i]);

    gridN     = offG / offB;                 /* offB = nOutChan * 2 bytes */
    clutBytes = gridN * gridN * gridN * offB;
    printf("  gridN=%d clutBytes=%d\n", gridN, clutBytes);

    put("grid_struct.bin", g, 0x200);
    put("idxtab.bin", idxtab, 3 * 256 * 8);
    put("clut.bin", clut, (size_t)clutBytes);
    put("otab.bin", otab, 3 * 0x4000);

    sprintf(path, "%s/grid_meta.txt", g_dumpdir);
    f = fopen(path, "w");
    fprintf(f, "evalVA %lu\n", EVAL_VA);
    fprintf(f, "offB %d\noffG %d\noffGB %d\noffR %d\noffRB %d\noffRG %d\n"
               "offRGB %d\n", offB, offG, offGB, offR, offRB, offRG, offRGB);
    fprintf(f, "gridN %d\nclutBytes %d\nnPixelsFirstCall %d\n",
            gridN, clutBytes, n);
    for (i = 0; i < 8; i++)
        fprintf(f, "outPlaneNonNull %d %d\n", i, out[i] != NULL);
    fclose(f);
    printf("  wrote grid_meta.txt\n");
}

static int __cdecl my_ev(void **in, void *a2, int a3, void **out,
                         void *a5, int a6, int n, void *grid) {
    wrmem(g_ev, g_save, 6);                 /* restore, permanently */
    if (!g_dumped) { g_dumped = 1; dump_grid(grid, in, out, n); }
    return ((ev_t)g_ev)(in, a2, a3, out, a5, a6, n, grid);
}

static void install_detour(void) {
    unsigned char p[6];
    g_ev = (unsigned char *)H + (EVAL_VA - 0x10000000UL);
    memcpy(g_save, g_ev, 6);
    p[0] = 0x68;                            /* push imm32 */
    *(void**)(p + 1) = (void*)my_ev;
    p[5] = 0xC3;                            /* ret        */
    wrmem(g_ev, p, 6);
    printf("detour on %p (VA %08lx) -> %p\n", g_ev, EVAL_VA, (void*)my_ev);
}

/* ------------------------------------------------------------------ */

int main(int argc, char **argv)
{
    const char *dll = getenv("KCMS_DLL");
    if (!dll) dll = "kodakcms.dll";
    setvbuf(stdout, NULL, _IONBF, 0);
    H = LoadLibraryA(dll);
    if (!H) { printf("LoadLibrary(%s) failed %lu\n", dll, GetLastError()); return 1; }
    pInit       = load_sym("SpInitialize");
    pInitThread = load_sym("SpInitThread");
    pLoad       = load_sym("SpProfileLoadProfile");
    pXformGet   = load_sym("SpXformGet");
    pCombine    = load_sym("SpCombineXforms");
    pEval       = load_sym("SpEvaluate");
    pChans      = load_sym("SpXformGetChannels");
    pErrTxt     = load_sym("SpGetErrorText");
    init_cms();

    {
        const char *poke = getenv("POKE_RVA");
        if (poke && *poke) {
            unsigned long va = strtoul(poke, NULL, 0);
            unsigned char *p = (unsigned char *)H + (va - 0x10000000UL);
            DWORD o;
            if (VirtualProtect(p, 16, PAGE_EXECUTE_READWRITE, &o)) {
                printf("POKE %p (VA %08lx) %02x -> C3\n", p, va, p[0]);
                p[0] = 0xC3;
            } else printf("POKE VirtualProtect failed\n");
        }
    }
    {
        const char *dd = getenv("DUMP_DIR");
        if (dd && *dd) { g_dumpdir = dd; install_detour(); }
    }

    if (argc < 2) { printf("usage: probe|run\n"); return 1; }

    if (!strcmp(argv[1], "probe")) {
        const char *p = argv[2];
        void *prof = NULL;
        int rc = pLoad(g_cms, p, 0, &prof);
        printf("SpProfileLoadProfile(cms,\"%s\",0,&p) = %d  prof=%p\n", p, rc, prof);
        if (rc == 0 && prof) {
            int i, c;
            for (i = 0; i <= 4; i++)
                for (c = 0; c <= 4; c++) {
                    void *xf = NULL;
                    int ic = -1, oc = -1;
                    int r2 = pXformGet(prof, i, c, &xf);
                    if (r2 == 0 && xf) pChans(xf, &ic, &oc);
                    printf("  SpXformGet(prof,%d,%d) rc=%d xf=%p in=%d out=%d\n",
                           i, c, r2, xf, ic, oc);
                }
        }
        return 0;
    }

    if (!strcmp(argv[1], "run")) {
        const char *p1, *p2, *fin, *fout;
        int iA, cA, iB, cB, n = 0, hh, rc;
        void *prof1 = NULL, *prof2 = NULL, *xf[2] = {NULL, NULL};
        void *outA = NULL, *outB = NULL, *comb = NULL;
        unsigned char *src, *dst;
        SpImg si, di;
        FILE *f, *g;
        const char *mode;

        if (argc < 10) { printf("bad args\n"); return 1; }
        p1 = argv[2]; p2 = argv[3]; fin = argv[4]; fout = argv[5];
        iA = atoi(argv[6]); cA = atoi(argv[7]);
        iB = atoi(argv[8]); cB = atoi(argv[9]);

        rc = pLoad(g_cms, p1, 0, &prof1);
        printf("load p1 rc=%d prof=%p\n", rc, prof1);
        if (rc) return 3;
        rc = pLoad(g_cms, p2, 0, &prof2);
        printf("load p2 rc=%d prof=%p\n", rc, prof2);
        if (rc) return 3;

        rc = pXformGet(prof1, iA, cA, &xf[0]);
        printf("xformget p1 (%d,%d) rc=%d xf=%p\n", iA, cA, rc, xf[0]);
        if (rc) return 4;
        rc = pXformGet(prof2, iB, cB, &xf[1]);
        printf("xformget p2 (%d,%d) rc=%d xf=%p\n", iB, cB, rc, xf[1]);
        if (rc) return 4;

        rc = pCombine(2, xf, &outA, &outB, NULL, NULL);
        printf("SpCombineXforms rc=%d outA=%p outB=%p\n", rc, outA, outB);
        if (rc == 0) comb = outA ? outA : outB;
        if (!comb) { printf("no combined xform\n"); return 5; }

        f = fopen(fin, "rb");
        if (!f) { printf("open %s failed\n", fin); return 6; }
        fread(&n, 4, 1, f);
        src = malloc((size_t)n * 3);
        dst = calloc((size_t)n * 3, 1);
        fread(src, 1, (size_t)n * 3, f);
        fclose(f);

        memset(&si, 0, sizeof si); memset(&di, 0, sizeof di);
        hh = getenv("SHAPE_H") ? atoi(getenv("SHAPE_H")) : 1;
        si.dataType = 1; si.w = n / hh; si.h = hh;
        si.pixStep = 3; si.lineStep = 3 * (n / hh); si.nChan = 3;
        si.chan[0] = src; si.chan[1] = src + 1; si.chan[2] = src + 2;
        di = si;
        di.chan[0] = dst; di.chan[1] = dst + 1; di.chan[2] = dst + 2;
        printf("shape w=%d h=%d lineStep=%d\n", si.w, si.h, si.lineStep);

        mode = getenv("EVAL_MODE");
        if (mode && !strcmp(mode, "two")) {
            unsigned char *mid = calloc((size_t)n * 3, 1);
            SpImg mi = si;
            int r1, r2;
            mi.chan[0] = mid; mi.chan[1] = mid + 1; mi.chan[2] = mid + 2;
            r1 = pEval(xf[0], &si, &mi, NULL, NULL);
            r2 = pEval(xf[1], &mi, &di, NULL, NULL);
            printf("two-step rc1=%d rc2=%d\n", r1, r2);
            rc = r1 ? r1 : r2;
        } else {
            rc = pEval(comb, &si, &di, NULL, NULL);
        }
        printf("SpEvaluate rc=%d\n", rc);
        if (rc) { char buf[512]; buf[0] = 0; pErrTxt(rc, 256, buf); printf("  err: %s\n", buf); }
        printf("  first: in %3d %3d %3d -> out %3d %3d %3d\n",
               src[0], src[1], src[2], dst[0], dst[1], dst[2]);
        printf("  last : in %3d %3d %3d -> out %3d %3d %3d\n",
               src[3*n-3], src[3*n-2], src[3*n-1],
               dst[3*n-3], dst[3*n-2], dst[3*n-1]);

        g = fopen(fout, "wb");
        fwrite(&rc, 4, 1, g); fwrite(&n, 4, 1, g);
        fwrite(dst, 1, (size_t)n * 3, g);
        fclose(g);
        return 0;
    }
    return 1;
}
