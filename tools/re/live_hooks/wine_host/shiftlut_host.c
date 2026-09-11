/* shiftlut_host.exe -- run the REAL shift-LUT builder out of PakonIMAu.dll
 * (md5 eea9dcf78ee21d4f7c515a6c2512242d) under Wine, and dump both its output
 * and the master table it reads from.
 *
 * WHAT THIS IS FOR
 * ----------------
 * `area_image_apply_lut` (fcn.100d9340) is handed three 4096-entry int16
 * tables. docs/74 §159.2 measured every captured table as exactly
 * `clip(i + k, 0, 4095)` -- tier 2: it says WHAT is applied, not what builds
 * it. The builder is `fcn.1006c4f0`, called on the singleton at
 * `PakonIMAu+0x6b5f74`, and its whole body is
 *
 *     out[i] = master[i + shift]        (int16, i = 0 .. count-1)
 *
 * where `master` is `*(obj+8)`, the middle of a 0x20002-byte allocation, so
 * the index range is -0x8000..0x7fff. `master` lives in UNINITIALISED .data:
 * it does not exist in the file image and cannot be read statically, and no
 * capture dumps it. Wine's real loader running the DLL's own initialisers is
 * therefore the only way to see it -- Unicorn would have to be handed a
 * fabricated table, which is the exact thing this project does not accept.
 *
 * CALLING CONVENTION
 * ------------------
 * `fcn.1006c4f0` ends in `ret 0x1c` and takes `this` in ecx, i.e. __thiscall
 * with seven stack dwords:
 *
 *   short build(short **outR, short **outG, short **outB,
 *               int count, short shR, short shG, short shB)
 *
 * returning 0 on success, -1 if `[this+4]` is null, -2 on allocation failure.
 * GCC has no __thiscall for this shape, so the call goes through an inline-asm
 * thunk. Nothing is emulated or reimplemented: the bytes that run are the
 * vendor's.
 *
 * BUILD/RUN
 *   i686-w64-mingw32-gcc -O2 -o shiftlut_host.exe shiftlut_host.c
 *   WINEPREFIX=$HOME/wineprefixes/hookcore_test WINEDEBUG=-all \
 *     wine shiftlut_host.exe PakonIMAu.dll cases.bin out.bin
 *
 * cases.bin : int32 ncases, then ncases * 3 int32 (shR, shG, shB)
 * out.bin   : int32 count(=4096), int32 master_lo, int32 master_n,
 *             master_n int16 master[master_lo ...],
 *             then per case: int32 rc, 3 * count int16 (R, G, B)
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>

#define OBJ_RVA 0x006b5f74u
#define BLD_RVA 0x0006c4f0u
#define COUNT   4096
#define MASTER_LO (-0x8000)
#define MASTER_N  0x10000

static short call_build(void *thisp, void *fn, short **a, short **b, short **c,
                        int count, short sr, short sg, short sb)
{
    volatile unsigned st[7];
    short ret;
    st[0] = (unsigned)(UINT_PTR)a;
    st[1] = (unsigned)(UINT_PTR)b;
    st[2] = (unsigned)(UINT_PTR)c;
    st[3] = (unsigned)count;
    st[4] = (unsigned)(int)sr;
    st[5] = (unsigned)(int)sg;
    st[6] = (unsigned)(int)sb;
    __asm__ __volatile__(
        "pushl 24(%%esi)\n\t"
        "pushl 20(%%esi)\n\t"
        "pushl 16(%%esi)\n\t"
        "pushl 12(%%esi)\n\t"
        "pushl 8(%%esi)\n\t"
        "pushl 4(%%esi)\n\t"
        "pushl 0(%%esi)\n\t"
        "movl %%edi, %%ecx\n\t"
        "call *%%ebx\n\t"          /* callee cleans (ret 0x1c) */
        : "=a"(ret)
        : "S"(st), "D"(thisp), "b"(fn)
        : "ecx", "edx", "memory");
    return ret;
}

int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc < 4) { printf("usage: shiftlut_host.exe <dll> <cases.bin> <out.bin>\n"); return 2; }

    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) { printf("LoadLibrary failed: %lu\n", (unsigned long)GetLastError()); return 1; }
    unsigned char *base = (unsigned char *)h;
    unsigned *obj = (unsigned *)(base + OBJ_RVA);
    printf("module %p  obj@%p vtbl=%08x buf=%08x master=%08x\n",
           (void *)base, (void *)obj, obj[0], obj[1], obj[2]);
    if (!obj[1] || !obj[2]) {
        printf("master table is NULL -- the DLL's initialiser did not run\n");
        return 1;
    }
    if ((int)(obj[2] - obj[1]) != -2 * MASTER_LO) {
        printf("unexpected master offset %d bytes (expected %d)\n",
               (int)(obj[2] - obj[1]), -2 * MASTER_LO);
        return 1;
    }
    const short *master = (const short *)(UINT_PTR)obj[2];

    FILE *fi = fopen(argv[2], "rb");
    if (!fi) { printf("cannot read %s\n", argv[2]); return 1; }
    int ncases = 0;
    if (fread(&ncases, 4, 1, fi) != 1 || ncases < 0 || ncases > 100000) {
        printf("bad cases file\n"); return 1;
    }
    FILE *fo = fopen(argv[3], "wb");
    if (!fo) { printf("cannot write %s\n", argv[3]); return 1; }

    int cnt = COUNT, lo = MASTER_LO, mn = MASTER_N;
    fwrite(&cnt, 4, 1, fo);
    fwrite(&lo, 4, 1, fo);
    fwrite(&mn, 4, 1, fo);
    fwrite(master + MASTER_LO, 2, MASTER_N, fo);

    void *fn = base + BLD_RVA;
    for (int i = 0; i < ncases; i++) {
        int s[3];
        if (fread(s, 4, 3, fi) != 3) { printf("short cases file at %d\n", i); return 1; }
        short *lr = NULL, *lg = NULL, *lb = NULL;
        short rc = call_build(obj, fn, &lr, &lg, &lb, COUNT,
                              (short)s[0], (short)s[1], (short)s[2]);
        int rc32 = rc;
        fwrite(&rc32, 4, 1, fo);
        static short zero[COUNT];
        fwrite(rc == 0 && lr ? lr : zero, 2, COUNT, fo);
        fwrite(rc == 0 && lg ? lg : zero, 2, COUNT, fo);
        fwrite(rc == 0 && lb ? lb : zero, 2, COUNT, fo);
    }
    fclose(fi);
    fclose(fo);
    printf("wrote %s: master[%d..%d] + %d cases\n", argv[3], MASTER_LO,
           MASTER_LO + MASTER_N - 1, ncases);
    return 0;
}
