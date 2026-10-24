/* SBA p-code: stage-1 decode (SbaDecodePcode 0x102884b0), stage-2 section parse (FUN_102a8f40), stack VM
 * (fcn.102aadf0). Port of lab/reference pakon_sba_pcode.py + pakon_vm.py. All integer (the _CItanh opcode is a table taken from Kodak's own
 * msvcr71, see TANH_THR) except the sqrt of HYPOT. */
#include "data/diag.h"
#include "analysis/sba_vm.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ------------------------------------------------------------------ stage 1 */

/* MSVC /100 with +-50 bias: imul 0x51EB851F, sar edx,5, add sign bit (pakon_sba_pcode._round_div100) */
static int32_t round_div100(int32_t n) {
    int32_t x = n >= 0 ? n + 50 : n - 50;
    int64_t prod = (int64_t)x * (int64_t)0x51EB851F;
    int32_t edx = (int32_t)(prod >> 32);
    edx >>= 5;
    return edx + (edx < 0 ? 1 : 0);
}
static int16_t s16(uint32_t v) { return (int16_t)(uint16_t)v; }
static void put16(uint8_t *buf, int off, uint32_t v) { buf[off] = (uint8_t)v; buf[off + 1] = (uint8_t)(v >> 8); }

/* opcode -> struct offset of the plain scalar stores (DLL cases 17..32, 34..44, 46..58) */
static int scalar_off(int op) {
    if (op >= 17 && op <= 32) return 0xE4 + 2 * (op - 17);
    if (op >= 34 && op <= 44) return 0x104 + 2 * (op - 34);
    if (op >= 46 && op <= 58) return 0x11A + 2 * (op - 46);
    return -1;
}

static pk_status pkc_decode_pcode(const uint16_t *w, size_t n, uint8_t params[PKC_SBA_STRUCT_SIZE], size_t *prog_at) {
    static const int table_base[5] = { 0x00, 0x2C, 0x58, 0x84, 0xB0 };
    memset(params, 0, PKC_SBA_STRUCT_SIZE);
    size_t esi = 0;
    while (esi < n) {
        int op = w[esi];
        int key = (int)s16(op) - 11;
        if (key < 0 || key > 48 || op == 45) {
            int32_t skip = esi + 1 < n ? s16(w[esi + 1]) : 0;
            int64_t nx = (int64_t)esi + 1 + skip + 1;
            if (nx <= (int64_t)esi) return PK_E_VENDOR_DATA;     /* the reference would loop forever */
            esi = (size_t)nx;
        } else if (op >= 11 && op <= 15) {
            int base = table_base[op - 11];
            esi += 2;
            for (int i = 0; i < 22; i++) {
                if (esi >= n) break;
                put16(params, base + 2 * i, w[esi]);
                esi++;
            }
        } else if (op == 16 || op == 33) {
            int32_t b = esi + 2 < n ? s16(w[esi + 2]) : 0;
            int o1 = op == 16 ? 0xDC : 0xE0, o2 = op == 16 ? 0xDE : 0xE2;
            esi += 2;
            put16(params, o1, (uint32_t)round_div100(b * 0x360));
            int32_t a = esi < n ? s16(w[esi]) : 0;
            int32_t probe = (100 - a) * 0x360;
            int32_t basec = probe >= 0 ? 0x151B2 : 0x1514E;
            int32_t val = round_div100(basec - a * 0x360);
            if (val == 0) val = 1;
            put16(params, o2, (uint32_t)val);
            esi += 1;
        } else if (op == 59) {
            put16(params, 0x134, esi + 2 < n ? w[esi + 2] : 0);
            esi += 3;
        } else if (scalar_off(op) >= 0) {
            put16(params, scalar_off(op), esi + 2 < n ? w[esi + 2] : 0);
            esi += 3;
        } else {
            return PK_E_VENDOR_DATA;
        }
        if (esi >= n) break;
        if ((w[esi] & 0xFF) == 0xFA) break;
    }
    if (esi >= n || w[esi] != 0xFA) return PK_E_VENDOR_DATA;   /* 0x18A8 */
    *prog_at = esi + 2;
    return PK_OK;
}

/* ------------------------------------------------------------------ stage 2 */

/* FUN_102a8f40: 0xFD 9, then sections until 0xFF. Section 0 (5 words) is the grid dims (not used by the VM);
 * section 7 is the record table; sections 0x10..0x12 skip one operand word. */
static pk_status pkc_parse_stage2(const uint16_t *w, size_t n, pkc_sba_prog *prog) {
    size_t i = 0;
    int have7 = 0;
    for (;;) {
        if (i >= n) return PK_E_VENDOR_DATA;
        int op = s16(w[i]);
        if (op > 0xFD) {
            if (op == 0xFF && have7) return PK_OK;
            return PK_E_VENDOR_DATA;
        }
        if (op == 0xFD) {
            if (i + 1 >= n || s16(w[i + 1]) != 9) return PK_E_VENDOR_DATA;     /* -10 */
            i += 2;
        } else if (op == 0) {
            i += 5;
        } else if (op >= 0x10 && op <= 0x12) {
            i += 2;
        } else if (op == 7) {
            if (have7 || i + 1 >= n) return PK_E_VENDOR_DATA;
            int cnt = s16(w[i + 1]);
            if (cnt < 1) return PK_E_VENDOR_DATA;
            pkc_sba_rec *rec = calloc((size_t)cnt, sizeof *rec);
            if (!rec) return PK_E_NOMEM;
            prog->rec = rec; prog->nrec = cnt; have7 = 1;
            i += 2;
            for (int k = 0; k < cnt; k++) {
                if (i + 3 > n) return PK_E_VENDOR_DATA;
                int idx = s16(w[i]), tag = s16(w[i + 1]), len = s16(w[i + 2]);
                if (idx < 0 || idx >= cnt || len < 1 || rec[idx].words || i + 3 + (size_t)len > n) return PK_E_VENDOR_DATA;
                rec[idx].words = malloc((size_t)len * sizeof(uint16_t));
                if (!rec[idx].words) return PK_E_NOMEM;
                memcpy(rec[idx].words, w + i + 3, (size_t)len * sizeof(uint16_t));
                rec[idx].tag = tag; rec[idx].nwords = len;
                i += 3 + (size_t)len;
            }
        } else {
            return PK_E_VENDOR_DATA;           /* sections 1..6 / unknown: not in pcode-dls_1.7 */
        }
    }
}

void pkc_sba_prog_free(pkc_sba_prog *prog) {
    if (!prog) return;
    for (int k = 0; k < prog->nrec; k++) free(prog->rec[k].words);
    free(prog->rec);
    prog->rec = NULL; prog->nrec = 0;
}

pk_status pkc_sba_pcode_load(const char *path, uint8_t params[PKC_SBA_STRUCT_SIZE], pkc_sba_prog *prog) {
    if (!path || !params || !prog) return PK_E_ARG;
    prog->rec = NULL; prog->nrec = 0;
    FILE *f = pkc_fopen(path, "rb");
    if (!f) return PK_E_VENDOR_DATA;
    uint8_t *raw = NULL; size_t cap = 0, len = 0;
    for (;;) {
        if (len == cap) {
            cap = cap ? cap * 2 : 16384;
            uint8_t *nr = realloc(raw, cap);
            if (!nr) { free(raw); fclose(f); return PK_E_NOMEM; }
            raw = nr;
        }
        size_t got = fread(raw + len, 1, cap - len, f);
        len += got;
        if (got == 0) break;
    }
    int err = ferror(f);
    fclose(f);
    if (err) { free(raw); return PK_E_IO; }
    size_t n = len / 2;
    uint16_t *w = n ? malloc(n * sizeof *w) : NULL;
    if (!w) { free(raw); return n ? PK_E_NOMEM : PK_E_VENDOR_DATA; }
    for (size_t i = 0; i < n; i++) w[i] = (uint16_t)(raw[2 * i] | (raw[2 * i + 1] << 8));    /* LE words */
    free(raw);
    if (w[0] != 0x00FB) {                                  /* the DLL's byte-swap path */
        for (size_t i = 0; i < n; i++) w[i] = (uint16_t)((w[i] << 8) | (w[i] >> 8));
        if (w[0] != 0x00FB) { free(w); return PK_E_VENDOR_DATA; }
    }
    size_t at = 0;
    pk_status st = pkc_decode_pcode(w, n, params, &at);
    if (st == PK_OK) st = pkc_parse_stage2(w + at, n - at, prog);
    free(w);
    if (st != PK_OK) pkc_sba_prog_free(prog);
    return st;
}

/* ------------------------------------------------------------------ the VM */

#define HALT 0xFF
#define NOP_WORD 0xFE
#define LABEL_WORD 0x23E7
#define ENDLABEL_WORD 0x244C

typedef struct {
    int32_t st[PKC_SBA_VM_STACK];
    uint8_t tt[PKC_SBA_VM_STACK];       /* R18 taint: 1 = the value derives from an input slot the port does not fill */
    int sp;
    int fail;
    uint8_t ot;                         /* OR of the taints popped since the last reset (an op's result taint) */
    uint8_t *vt;                        /* taint of the variable file */
} vm_t;

static int32_t wrap32(int64_t v) { return (int32_t)(uint32_t)(uint64_t)v; }   /* two's-complement wrap */
static void push(vm_t *m, int32_t v) { if (m->sp >= PKC_SBA_VM_STACK) m->fail = 1; else { m->tt[m->sp] = m->ot; m->st[m->sp++] = v; } }
static int32_t pop(vm_t *m) { if (m->sp <= 0) { m->fail = 1; return 0; } m->ot |= m->tt[m->sp - 1]; return m->st[--m->sp]; }
/* pop with the value's own taint reported separately (SWAP / SEL / stores keep per-value taint) */
static int32_t popt(vm_t *m, uint8_t *t) {
    uint8_t keep = m->ot;
    m->ot = 0;
    int32_t v = pop(m);
    *t = m->ot;
    m->ot = (uint8_t)(keep | *t);
    return v;
}
#define UNK_FAIL (-2)                   /* an unported slot decides control flow or an error exit */
/* x86 idiv truncation. The caller refuses b == 0 (-> error exit) and INT_MIN / -1 (R42: the CPU faults there, which the port does
 * not model, so it is refused like a tainted dividend: UNK_FAIL); every other b == -1 is just -a. Unreachable from the shipped records. */
static int32_t idiv32(int32_t a, int32_t b) { return b == -1 ? wrap32(-(int64_t)a) : a / b; }

/* the shared marker scan of opcodes 54/55 (pakon_vm._pkc_scan_labels); returns -1 when it runs off the record */
static long pkc_scan_labels(const uint16_t *w, long nw, long i, int nskip, int stop_on_end) {
    long c = -1;
    for (;;) {
        if (i >= nw) return -1;
        int cw = w[i];
        int nb = i > 0 && w[i - 1] == NOP_WORD && i + 1 < nw && w[i + 1] == NOP_WORD;
        if (stop_on_end && cw == ENDLABEL_WORD && nb) return i;
        if (cw == LABEL_WORD && nb) c++;
        i++;
        if (c >= nskip) return i;
    }
}

/* Opcode 16: (int)(_CItanh((double)a * 0.001f) * 1000.0f) with Kodak's msvcr71 _CItanh (x87 at PC64 inside the call, the
 * product and the truncation at PC53; RE 27 section 4). Not libm's tanh: macOS libm differs from Kodak for |a| 19050..19061
 * (1000 vs 999) and the saturation edge cannot be left to a platform function. The result is a monotone odd step function
 * of a, so it is stored as TANH_THR[k - 1] = the smallest |a| whose result is >= k, k = 1..1000, taken from the native
 * msvcr71 _CItanh run over every a in -20000..20000 and beyond (lab/tanh/sweep.c, under Wine/Rosetta x87) and reproduced
 * by an exact model of the msvcr71 code (lab/tanh/model.py: 40001 of 40001 equal; f2xm1 +-2 ulp64 changes no result in
 * -19100..19100, lab/tanh/sens.py). Above the saturation point (|x| >= 19.0615..., tanh = +-1: the code returns 1 without
 * computing) every |a| >= 19050 gives +-1000, as does any int32 beyond (swept to +-2^31). */
static const uint16_t TANH_THR[1000] = {
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13,
    14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25,
    26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37,
    38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49,
    50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61,
    62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73,
    74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85,
    86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97,
    98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
    110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121,
    122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133,
    134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 146,
    147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158,
    159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170,
    171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182,
    184, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 195,
    196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207,
    208, 209, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220,
    221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 232, 233,
    234, 235, 236, 237, 238, 239, 240, 241, 242, 243, 244, 245,
    246, 247, 248, 250, 251, 252, 253, 254, 255, 256, 257, 258,
    259, 260, 261, 262, 263, 264, 266, 267, 268, 269, 270, 271,
    272, 273, 274, 275, 276, 277, 278, 280, 281, 282, 283, 284,
    285, 286, 287, 288, 289, 290, 291, 293, 294, 295, 296, 297,
    298, 299, 300, 301, 302, 303, 305, 306, 307, 308, 309, 310,
    311, 312, 313, 314, 316, 317, 318, 319, 320, 321, 322, 323,
    324, 325, 327, 328, 329, 330, 331, 332, 333, 334, 335, 337,
    338, 339, 340, 341, 342, 343, 344, 346, 347, 348, 349, 350,
    351, 352, 353, 355, 356, 357, 358, 359, 360, 361, 363, 364,
    365, 366, 367, 368, 369, 371, 372, 373, 374, 375, 376, 377,
    379, 380, 381, 382, 383, 384, 385, 387, 388, 389, 390, 391,
    392, 394, 395, 396, 397, 398, 399, 401, 402, 403, 404, 405,
    406, 408, 409, 410, 411, 412, 413, 415, 416, 417, 418, 419,
    421, 422, 423, 424, 425, 427, 428, 429, 430, 431, 433, 434,
    435, 436, 437, 439, 440, 441, 442, 443, 445, 446, 447, 448,
    449, 451, 452, 453, 454, 455, 457, 458, 459, 460, 462, 463,
    464, 465, 467, 468, 469, 470, 471, 473, 474, 475, 476, 478,
    479, 480, 481, 483, 484, 485, 486, 488, 489, 490, 491, 493,
    494, 495, 497, 498, 499, 500, 502, 503, 504, 505, 507, 508,
    509, 511, 512, 513, 514, 516, 517, 518, 520, 521, 522, 523,
    525, 526, 527, 529, 530, 531, 533, 534, 535, 537, 538, 539,
    541, 542, 543, 544, 546, 547, 548, 550, 551, 552, 554, 555,
    556, 558, 559, 561, 562, 563, 565, 566, 567, 569, 570, 571,
    573, 574, 575, 577, 578, 580, 581, 582, 584, 585, 586, 588,
    589, 591, 592, 593, 595, 596, 598, 599, 600, 602, 603, 605,
    606, 607, 609, 610, 612, 613, 615, 616, 617, 619, 620, 622,
    623, 625, 626, 628, 629, 630, 632, 633, 635, 636, 638, 639,
    641, 642, 644, 645, 647, 648, 650, 651, 652, 654, 655, 657,
    658, 660, 661, 663, 664, 666, 667, 669, 671, 672, 674, 675,
    677, 678, 680, 681, 683, 684, 686, 687, 689, 691, 692, 694,
    695, 697, 698, 700, 701, 703, 705, 706, 708, 709, 711, 713,
    714, 716, 717, 719, 721, 722, 724, 726, 727, 729, 730, 732,
    734, 735, 737, 739, 740, 742, 744, 745, 747, 749, 750, 752,
    754, 755, 757, 759, 760, 762, 764, 765, 767, 769, 771, 772,
    774, 776, 778, 779, 781, 783, 785, 786, 788, 790, 792, 793,
    795, 797, 799, 800, 802, 804, 806, 808, 809, 811, 813, 815,
    817, 819, 820, 822, 824, 826, 828, 830, 831, 833, 835, 837,
    839, 841, 843, 845, 847, 848, 850, 852, 854, 856, 858, 860,
    862, 864, 866, 868, 870, 872, 874, 876, 878, 880, 882, 884,
    886, 888, 890, 892, 894, 896, 898, 900, 902, 904, 906, 908,
    910, 912, 914, 917, 919, 921, 923, 925, 927, 929, 931, 934,
    936, 938, 940, 942, 944, 947, 949, 951, 953, 955, 958, 960,
    962, 964, 967, 969, 971, 973, 976, 978, 980, 983, 985, 987,
    990, 992, 994, 997, 999, 1001, 1004, 1006, 1009, 1011, 1013, 1016,
    1018, 1021, 1023, 1026, 1028, 1031, 1033, 1036, 1038, 1041, 1043, 1046,
    1048, 1051, 1054, 1056, 1059, 1061, 1064, 1067, 1069, 1072, 1075, 1077,
    1080, 1083, 1085, 1088, 1091, 1094, 1096, 1099, 1102, 1105, 1108, 1110,
    1113, 1116, 1119, 1122, 1125, 1128, 1130, 1133, 1136, 1139, 1142, 1145,
    1148, 1151, 1154, 1157, 1160, 1163, 1167, 1170, 1173, 1176, 1179, 1182,
    1185, 1189, 1192, 1195, 1198, 1202, 1205, 1208, 1212, 1215, 1218, 1222,
    1225, 1229, 1232, 1235, 1239, 1242, 1246, 1249, 1253, 1257, 1260, 1264,
    1268, 1271, 1275, 1279, 1282, 1286, 1290, 1294, 1298, 1302, 1305, 1309,
    1313, 1317, 1321, 1325, 1329, 1334, 1338, 1342, 1346, 1350, 1355, 1359,
    1363, 1367, 1372, 1376, 1381, 1385, 1390, 1394, 1399, 1404, 1408, 1413,
    1418, 1422, 1427, 1432, 1437, 1442, 1447, 1452, 1457, 1462, 1467, 1473,
    1478, 1483, 1489, 1494, 1500, 1505, 1511, 1517, 1522, 1528, 1534, 1540,
    1546, 1552, 1558, 1564, 1570, 1577, 1583, 1590, 1596, 1603, 1609, 1616,
    1623, 1630, 1637, 1644, 1652, 1659, 1666, 1674, 1682, 1689, 1697, 1705,
    1713, 1722, 1730, 1739, 1747, 1756, 1765, 1774, 1783, 1793, 1802, 1812,
    1822, 1832, 1843, 1853, 1864, 1875, 1886, 1898, 1909, 1922, 1934, 1946,
    1959, 1973, 1986, 2000, 2014, 2029, 2044, 2060, 2076, 2093, 2110, 2128,
    2146, 2165, 2185, 2206, 2227, 2250, 2273, 2298, 2324, 2351, 2380, 2411,
    2443, 2478, 2515, 2555, 2599, 2647, 2700, 2759, 2826, 2904, 2995, 3107,
    3251, 3454, 3801, 19050,
};
static int32_t pkc_sba_tanh1000(int32_t a) {
    int64_t v = a < 0 ? -(int64_t)a : (int64_t)a;
    int lo = 0, hi = 1000;                              /* count of thresholds <= v */
    while (lo < hi) { int mid = (lo + hi) / 2; if (TANH_THR[mid] <= v) lo = mid + 1; else hi = mid; }
    return a < 0 ? -lo : lo;
}

/* one record; 0 = ok */
static int pkc_run_record(const pkc_sba_rec *rec, vm_t *m, int32_t *vars, int nvars, const int32_t *in, const uint8_t *known, int nin) {
    const uint16_t *w = rec->words;
    long nw = rec->nwords, i = 0;
    m->sp = 0; m->fail = 0;                    /* the stack is empty between records (every record halts balanced) */
    for (long steps = 0; steps < 1000000; steps++) {
        if (i >= nw) return -1;
        int op = w[i];
        m->ot = 0;
        if (op == HALT) return 0;
        if (op == 1) {
            if (i + 1 >= nw) return -1;
            int t = w[i + 1];
            if (t == 4) {
                if (i + 3 >= nw) return -1;
                push(m, (int32_t)(((uint32_t)w[i + 2] << 16) | w[i + 3]));
                i += 4;
            } else if (t == 3 || t == 6) {
                if (i + 2 >= nw) return -1;
                int idx = s16(w[i + 2]);
                if (t == 3) { if (idx < 0 || idx >= nvars) return -1; m->ot = m->vt[idx]; push(m, vars[idx]); }
                else {
                    if (idx < 0 || idx >= nin) return -1;
                    m->ot = known && !known[idx];       /* R18: tainted; only fatal if it reaches L or a decision */
                    push(m, in[idx]);
                }
                i += 3;
            } else return -1;                   /* source types 0,1,2,5: used by no shipped record */
        } else if (op == 2) {
            if (i + 1 >= nw) return -1;
            int idx = s16(w[i + 1]);
            if (idx < 0 || idx >= nvars) return -1;
            { uint8_t t; vars[idx] = popt(m, &t); m->vt[idx] = t; }
            i += 2;
        } else if (op == 54 || op == 55) {
            uint8_t ct;
            int32_t c = popt(m, &ct);
            if (ct) return UNK_FAIL;           /* the branch itself depends on an unported slot */
            int nskip = op == 54 ? c : (c == 0 ? 1 : 0);
            i++;
            if (nskip > -1) {
                i = pkc_scan_labels(w, nw, i, nskip, op == 54);
                if (i < 0) return -1;
            }
        } else {
            int32_t a, b, c, d;
            switch (op) {
            case 3: b = pop(m); a = pop(m); push(m, wrap32((int64_t)a + b)); break;
            case 4: b = pop(m); a = pop(m); push(m, wrap32((int64_t)a - b)); break;
            case 5: b = pop(m); a = pop(m); push(m, (int32_t)(uint32_t)((uint64_t)(uint32_t)a * (uint64_t)(uint32_t)b)); break;
            case 6: {
                uint8_t bt, at;                 /* R40 M2: a tainted divisor is refused whatever the port holds (Kodak's may be 0); so is a
                                                 * tainted dividend over -1 (Kodak's may be INT_MIN: the CPU would fault) */
                b = popt(m, &bt); a = popt(m, &at);
                if (bt || (at && b == -1)) return UNK_FAIL;
                if (b == 0) return -1;
                if (b == -1 && a == INT32_MIN) return UNK_FAIL;       /* R42: Kodak's idiv faults here; refuse, do not wrap */
                push(m, idiv32(a, b));
                break; }
            case 7: a = pop(m); push(m, wrap32(-(int64_t)a)); break;
            case 16: a = pop(m); push(m, pkc_sba_tanh1000(a)); break;      /* fild; fmul 0.001f; _CItanh; fmul 1000.0f; _ftol */
            case 27: case 28: {
                uint8_t nt;
                int32_t n = popt(m, &nt);
                if (nt) return UNK_FAIL;
                if (n < 1) return -1;
                int32_t s = 0;
                for (int32_t k = 0; k < n && !m->fail; k++) s = wrap32((int64_t)s + pop(m));
                push(m, op == 27 ? s : idiv32(s, n));
                break; }
            case 29: case 30: {
                uint8_t nt;
                int32_t n = popt(m, &nt);
                if (nt) return UNK_FAIL;
                if (n < 1) return -1;
                int32_t acc = pop(m);
                for (int32_t k = 0; k < n - 1 && !m->fail; k++) {
                    int32_t x = pop(m);
                    if (op == 29 ? x > acc : x < acc) acc = x;
                }
                push(m, acc);
                break; }
            case 31: case 32: case 33: case 34: case 35: case 36: {
                uint8_t ta, tb, tc, td;
                d = popt(m, &td); c = popt(m, &tc); b = popt(m, &tb); a = popt(m, &ta);      /* pushed A,B,C,D */
                int cond = op == 31 ? a > b : op == 32 ? a < b : op == 33 ? a == b : op == 34 ? a >= b : op == 35 ? a <= b : a != b;
                m->ot = (uint8_t)(ta | tb | (cond ? tc : td));      /* only the chosen branch's taint flows */
                push(m, cond ? c : d);
                break; }
            case 47: {                           /* sqrt(s32(a*a + b*b)) through _ftol; fsqrt(neg) = indefinite */
                b = pop(m); a = pop(m);
                int32_t s = wrap32((int64_t)((uint32_t)a * (uint32_t)a + (uint32_t)b * (uint32_t)b));
                push(m, s < 0 ? INT32_MIN : (int32_t)sqrt((double)s));
                break; }
            case 48: a = pop(m); push(m, a >= 0 ? wrap32(-(int64_t)a) : a); break;     /* -|x| */
            case 49: a = pop(m); push(m, a); push(m, a); break;
            case 50: { uint8_t ta, tb; a = popt(m, &ta); b = popt(m, &tb); m->ot = ta; push(m, a); m->ot = tb; push(m, b); break; }
            case 56: b = pop(m); a = pop(m); push(m, a > b); break;
            case 57: b = pop(m); a = pop(m); push(m, a < b); break;
            case 58: b = pop(m); a = pop(m); push(m, a == b); break;
            case 59: b = pop(m); a = pop(m); push(m, a >= b); break;
            case 60: b = pop(m); a = pop(m); push(m, a <= b); break;
            case 61: b = pop(m); a = pop(m); push(m, a != b); break;
            case 62: b = pop(m); a = pop(m); push(m, a && b); break;
            case 63: b = pop(m); a = pop(m); push(m, a || b); break;
            case 64: a = pop(m); push(m, !a); break;
            case 68: b = pop(m); a = pop(m); push(m, a & b); break;
            case 69: b = pop(m); a = pop(m); push(m, a | b); break;
            case 253: case 254: break;
            default: return -1;                  /* handler 50: -110 */
            }
            i++;
        }
        if (m->fail) return -1;
    }
    return -1;
}

/* fcn.102ac140: every record in file order; vars[] receives the variable file */
static pk_status pkc_run_all(const pkc_sba_prog *prog, const int32_t *in, const uint8_t *known, int nin, int32_t *vars, uint8_t *vt, int nvars) {
    vm_t *m = calloc(1, sizeof *m);
    if (!m) return PK_E_NOMEM;
    m->vt = vt;
    pk_status st = PK_OK;
    for (int k = 0; k < prog->nrec && st == PK_OK; k++)
    {
        int r = prog->rec[k].words ? pkc_run_record(&prog->rec[k], m, vars, nvars, in, known, nin) : -1;
        if (r == UNK_FAIL) st = PK_E_UNSUPPORTED;
        else if (r != 0) st = PK_E_ARG;
    }
    free(m);
    return st;
}

pk_status pkc_sba_vm_l(const pkc_sba_prog *prog, const int32_t *in, const uint8_t *known, int nin, int32_t *L, int32_t *vars_out) {
    if (!prog || !prog->rec || !in || nin < 0 || !L) return PK_E_ARG;
    int nvars = prog->nrec > 264 ? prog->nrec : 264;
    int32_t *vars = calloc((size_t)nvars, sizeof *vars);
    uint8_t *vt = calloc((size_t)nvars, 1);
    if (!vars || !vt) { free(vars); free(vt); return PK_E_NOMEM; }
    pk_status st = pkc_run_all(prog, in, known, nin, vars, vt, nvars);
    if (st == PK_OK) {
        int seen = 0, lvar = -1;
        for (int k = 0; k < prog->nrec && lvar < 0; k++)
            if (prog->rec[k].tag == 1 && seen++ == PKC_SBA_L_EXTRACT) lvar = k;
        if (lvar < 0) st = PK_E_VENDOR_DATA;
        else if (vt[lvar]) st = PK_E_UNSUPPORTED;      /* R18: L itself derives from an unported vector slot */
        else *L = vars[lvar];
    }
    if (st == PK_OK && vars_out) memcpy(vars_out, vars, (size_t)prog->nrec * sizeof *vars);
    free(vars); free(vt);
    return st;
}
