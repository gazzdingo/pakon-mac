#ifndef PAKON_COLOUR_ANALYSIS_KINT_H
#define PAKON_COLOUR_ANALYSIS_KINT_H
/* Kodak's integer idioms, shared by the analysis ports (sba_measure.c, fos.c, sba_pref.c, flesh.c, exposure.c).
 * PakonIMAu.dll carries several identical copies of each; every copy a port mirrors is listed, so a fix here reaches
 * all of them. */
#include <stdint.h>

/* a 32-bit register: the low 32 bits, signed (two's complement wrap, no UB) */
static inline int32_t pkc_wrap32(int64_t v) { return (int32_t)(uint32_t)(uint64_t)v; }
/* a 16-bit word store read back with movsx */
static inline int16_t pkc_sx16(int64_t v) { return (int16_t)(uint16_t)(uint64_t)v; }

/* MSVC _ftol / _ftol2 (0x104ffe44): fistp qword with the round-toward-zero fixup, 64 bits; NaN, +-inf and |x| >= 2^63 give
 * the x87 integer indefinite 0x8000000000000000. Callers keep eax (pkc_wrap32) or ax (pkc_sx16). Copies: fos.c's
 * SbaFOSResults word stores, scplut.c's LUT fill, sba_pref.c's Preference / setShifts / dpi-block stores, flesh.c's
 * borders, axis indices, probability plane, weights and delta. */
static inline int64_t pkc_ftol64(double x) {
    if (!(x > -9223372036854775808.0 && x < 9223372036854775808.0)) return INT64_MIN;
    return (int64_t)x;                              /* C conversion truncates toward zero */
}

/* idiv of (num +- trunc(den / 2)) by den: the half (cdq; sub eax, edx; sar 1) is added when num and den have the same
 * sign, subtracted otherwise. Copies: FOS weight ramp / weighted means 0x1028f1f8 / 0x1028f456; FUN_1028ae00's U / V
 * means 0x1028b26e / 0x1028b4ef; fcn.102b7440's s2 0x102b7d40; Makesfs' fill 0x102ac4cd / 0x102ac573. den != 0 is the
 * caller's to guarantee (Kodak faults with #DE). */
static inline int32_t pkc_half_round_div(int32_t num, int32_t den) {
    int32_t half = den / 2;
    int64_t n = ((num < 0) == (den < 0)) ? (int64_t)num + half : (int64_t)num - half;
    return pkc_wrap32((int64_t)pkc_wrap32(n) / den);
}

/* (x +- bias) / div with a positive constant div: the bias's sign follows x (test; jge; lea +-bias, which wraps), then
 * MSVC's magic-number division by the constant -- an exact truncating division. Copies: sba_pref.c's dpi block
 * (0x10215084), the FOS-pointer dmin luma (0x102afaf9), the dmin chroma blend (0x1028b2ca..) and the setShifts axes
 * (0x10100a37..); exposure.c's exposure word (fcn.102ae9d0 0x102aebe9..0x102aec0a: bias 85000, div 170000).
 * The same bias + magic-multiply idiom also appears with its own constants as sba_measure.c's opening axes (biased_scale +
 * magic_div: 32-bit imul by 100000, then 0x306E8227 / 0x111F883D / 0x3B510A6F with sar 15/14/15, 0x1028b979..) and sba_vm.c's
 * round_div100 (0x51EB851F, sar 5, SbaDecodePcode 0x102884b0). They are listed here, not folded into pkc_bias_div: they
 * keep the multiply-high form of the DLL's sequence (and sba_vm.c's unrelated constants), each verified against Kodak. */
static inline int32_t pkc_bias_div(int32_t x, int32_t bias, int32_t div) {
    return pkc_wrap32((int64_t)pkc_wrap32(x >= 0 ? (int64_t)x + bias : (int64_t)x - bias) / div);
}

/* Kodak's integer square root for x >= 0: x itself below 2; else Newton from a power-of-two guess (0x60000000 mask
 * walked down by 2 bits, guess 0x8000 halved), s' = (x / s + s + 1) >> 1 until it repeats (terminates for every int32,
 * checked exhaustively). Copies: FOS 0x1028f362 (inline; a negative x falls into the "below 2" exit and is returned
 * as is) and fcn.102b7130 (Makesfs; a negative x returns -1 first) -- each caller keeps its own negative arm. */
static inline int32_t pkc_isqrt(int32_t x) {
    if (x < 2) return x;
    int32_t m = 0x60000000, s = 0x8000, prev;
    if (!(m & x)) {
        do { m >>= 2; s >>= 1; } while (!(x & m));
        if (!s) return 0;
    }
    do { int32_t q = x / s; prev = s; s = (int32_t)(((int64_t)q + s + 1) >> 1); } while (s != prev);
    return s;
}

/* The 120-step hue wheel of (s0, s1, s2): 1 for a neutral or unclassified triple, else six 20-step sectors
 * 0x01 / 0x15 / 0x29 / 0x3D / 0x51 / 0x65 + (den/2 + 20 * offset) / den, folded to 1 from 0x79 up. Every sum is a 32-bit
 * register (den > 0 in each sector). Copies: fcn.102aece0's mask 0x102b0e75 (bands within +-7100), Makesfs'
 * fcn.102b7180 (arguments up to ~1.4e7). */
static inline int pkc_hue120(int32_t s0, int32_t s1, int32_t s2) {
    int32_t den, off, base;
    if (s0 == s1 && s1 == s2) return 1;
    if (s0 >= s1 && s1 >= s2) { den = pkc_wrap32((int64_t)s0 - s2); off = pkc_wrap32((int64_t)s0 - s1); base = 0x01; }
    else if (s0 > s2 && s2 > s1) { den = pkc_wrap32((int64_t)s0 - s1); off = pkc_wrap32((int64_t)s2 - s1); base = 0x15; }
    else if (s2 >= s0 && s0 >= s1) { den = pkc_wrap32((int64_t)s2 - s1); off = pkc_wrap32((int64_t)s2 - s0); base = 0x29; }
    else if (s2 > s1 && s1 > s0) { den = pkc_wrap32((int64_t)s2 - s0); off = pkc_wrap32((int64_t)s1 - s0); base = 0x3D; }
    else if (s1 >= s2 && s2 >= s0) { den = pkc_wrap32((int64_t)s1 - s0); off = pkc_wrap32((int64_t)s1 - s2); base = 0x51; }
    else if (s1 > s0 && s0 > s2) { den = pkc_wrap32((int64_t)s1 - s2); off = pkc_wrap32((int64_t)s0 - s2); base = 0x65; }
    else return 1;
    int32_t h = pkc_wrap32((int64_t)pkc_wrap32((int64_t)(den / 2) + (int64_t)20 * off) / den + base);
    return h < 0x79 ? h : 1;
}
#endif
