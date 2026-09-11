/* Call the REAL vendor Shasta tone function on REAL parameters, under Wine.
 *
 * WHY THIS EXISTS
 * ---------------
 * docs/74 §127: the washed-out defect is 40-50% of the contrast, and it is in
 * tone x ICC -- the invert stage measures -957/-1017/-938 per decade against
 * the formula's -1000, so it is correct. `pakon_decode.py` forces
 * `shasta_stand_in = True` because AnsShastaCapabilityImpl::analyze is
 * unported, and the stand-in uses 3 of the vendor's 72 parameters.
 *
 * fcn.101bea50 is the tone shaping function: it reads exactly the
 * shadow/highlight roll-off parameters
 *
 *     +0xa8 extShadowButtons   +0xf0 shadowExpScale   +0x100 shadowMaxExpSlope
 *     +0xb0 shadowButtons      +0xf8 highlightExpScale +0x108 highlightMaxExpSlope
 *     +0xe0 highlightAggr      +0xe8 extHighlightAggr
 *
 * from `params` at `this+0xe0`, and evaluates three pow()s (f2xm1 + fscale +
 * frndint) with fdiv/fdivr around them. Hand-porting 771 bytes of x87 stack
 * juggling and hoping it matches is the wrong order of work: run the real
 * thing first, get its behaviour, THEN port against a known-good reference.
 *
 * WHAT IS FABRICATED HERE, AND WHY THE OUTPUT IS SUSPECT UNTIL CHECKED
 * -------------------------------------------------------------------
 * The `this` object is synthesised: a zeroed block with a pointer to a
 * ShastaParams built from shasta-rpd.dpi at +0xe0. Everything else in `this`
 * is zero, and the params struct's own `key` std::string (+0x1c) and
 * `pfdParams` sub-struct are zeroed too. The function's six stack arguments
 * are also unknown -- they are swept, not known.
 *
 * So this does NOT produce "the vendor's tone curve" on its own. It produces
 * the function's response surface over swept inputs, which is what tells us
 * whether it is even the right function before any porting effort is spent.
 * A run that returns a constant, or NaN, means the synthesis is wrong -- and
 * the host prints enough to see that rather than assume success.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define TONE_RVA 0x001bea50u          /* fcn.101bea50 */
#define PARAMS_AT_THIS 0xe0u

typedef double (__cdecl *tone_fn)(double, double, double, double, double, double);

/* File-scope, deliberately: these are referenced from inline asm AFTER %esp has
 * been adjusted. Statics are addressed absolutely, so they stay valid; stack
 * locals would not (that bug jumped the indirect call to 0). */
void *g_self;
void *g_fn;
unsigned g_argblk[8];
double g_slot[6];
double g_result;

int main(int argc, char **argv)
{
    setvbuf(stdout, NULL, _IONBF, 0);
    if (argc < 3) { printf("usage: shasta_host.exe <dll> <params.bin>\n"); return 2; }

    HMODULE h = LoadLibraryA(argv[1]);
    if (!h) { printf("LoadLibrary failed: %lu\n", (unsigned long)GetLastError()); return 1; }
    unsigned char *base = (unsigned char *)h;
    void *fn = base + TONE_RVA;
    printf("loaded %p   tone fn %p\n", (void *)h, fn);

    FILE *f = fopen(argv[2], "rb");
    if (!f) { printf("cannot open %s\n", argv[2]); return 1; }
    static unsigned char params[0x200];
    size_t n = fread(params, 1, sizeof params, f);
    fclose(f);
    printf("params: %zu bytes\n", n);

    /* Echo back a few fields so a mis-built struct is visible immediately
     * rather than silently producing plausible numbers. */
    printf("  metricGray=%d white=%d codeValuesPerButton=%.3f\n",
           *(int *)(params + 0x38), *(int *)(params + 0x40),
           *(double *)(params + 0x48));
    printf("  shadowButtons=%.3f highlightButtons=%.3f shadowExpScale=%.3f\n",
           *(double *)(params + 0xb0), *(double *)(params + 0xb8),
           *(double *)(params + 0xf0));

    /* Synthesised `this`: params pointer at +0xe0, everything else zero. */
    static unsigned char self[0x400];
    memset(self, 0, sizeof self);
    *(void **)(self + PARAMS_AT_THIS) = params;
    g_self = self;
    g_fn = fn;

    /* The six stack args are unknown. Sweep arg0 across a plausible code-value
     * range with the rest zero, and print the response. A flat or NaN response
     * means the call shape is wrong. */
    /* Signature, read from the body rather than guessed:
     *   every one of the six stack args is loaded as a DWORD
     *     mov eax,[arg_8h] / [arg_ch] / [arg_10h] / [arg_14h]
     *     mov ebx,[arg_18h]   mov edx,[arg_1ch]
     *   and args 4/5 are written through -- `fstp qword [ebx]`,
     *   `fstp qword [edx]` at 0x101beb18/0x101beb20 -- so they are double*
     *   OUT params. There is also `fcomp qword [ebp+0x20]`, a double in the
     *   7th slot. A first attempt passed six doubles and page-faulted writing
     *   to NULL at 0x101beb18, which is what proved the shape.
     *
     * So: six pointers to doubles, then a trailing double. */
    /* Drive it with a REAL 64x64 analysis image.
     *
     * The loop body settles the signature: this+0xc and this+0xe are the grid
     * dimensions, arg3 is an int16 mask (a nonzero entry skips the pixel), and
     * arg0/arg1/arg2 are int16 planes read with `movsx word [edx+eax]` where
     * edx = index*2. Values are converted to "buttons" by dividing by
     * extShadowButtons / shadowButtons -- so the planes are code values.
     *
     * analysisImageDim=64 and rowPortion=colPortion=0.875 in shasta-rpd.dpi,
     * so the vendor analyses a 64x64 sample of the central 87.5%. That is what
     * analysis64.bin is: our own frame 05 RPD, cropped and decimated the same
     * way. Feeding real data is the only way to get past the count==0 early
     * exit at 0x101beb4d. */
    static short planes[3][64 * 64];
    static short mask[64 * 64];
    FILE *af = fopen(argc > 3 ? argv[3] : "analysis64.bin", "rb");
    if (!af) { printf("cannot open analysis image\n"); return 1; }
    static short inter[64 * 64 * 3];
    size_t got = fread(inter, 2, 64 * 64 * 3, af);
    fclose(af);
    printf("analysis image: %zu int16 read\n", got);
    for (int i = 0; i < 64 * 64; i++) {
        planes[0][i] = inter[i * 3 + 0];
        planes[1][i] = inter[i * 3 + 1];
        planes[2][i] = inter[i * 3 + 2];
        mask[i] = 0;                      /* 0 = use this pixel */
    }
    printf("  plane means: %d %d %d\n", planes[0][2048], planes[1][2048], planes[2][2048]);

    *(short *)(self + 0x0c) = 64;         /* grid width  */
    *(short *)(self + 0x0e) = 64;         /* grid height */

    g_argblk[0] = (unsigned)(UINT_PTR)planes[0];
    g_argblk[1] = (unsigned)(UINT_PTR)planes[1];
    g_argblk[2] = (unsigned)(UINT_PTR)planes[2];
    g_argblk[3] = (unsigned)(UINT_PTR)mask;
    g_argblk[4] = (unsigned)(UINT_PTR)&g_slot[4];
    g_argblk[5] = (unsigned)(UINT_PTR)&g_slot[5];

    printf("\n  thresh      out4                out5\n");
    for (int i = 0; i <= 8; i++) {
        double thresh = (double)i * 512.0;
        memcpy(&g_argblk[6], &thresh, sizeof(double));
        g_slot[4] = g_slot[5] = -12345.0;   /* sentinel: untouched is visible */
        __asm__ volatile (
            "subl $32, %%esp\n\t"
            "movl $_g_argblk, %%esi\n\t"
            "movl %%esp, %%edi\n\t"
            "movl $8, %%ecx\n\t"
            "cld\n\t rep movsl\n\t"
            "movl _g_self, %%ecx\n\t"
            "call *_g_fn\n\t"
            "addl $32, %%esp\n\t"
            ::: "eax", "ecx", "edx", "esi", "edi", "memory");
        printf("  %8.1f  %18.8f  %18.8f\n", thresh, g_slot[4], g_slot[5]);
    }
    return 0;
}
