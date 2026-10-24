/* TLB's frame detector (docs/re/31-framing.md sec 7.1-7.5): FUN_100079c0, FUN_100072c0, FUN_10005d20 (threshold), FUN_10006140 (runs),
 * FUN_10006930 (LookForNicePictures), FUN_100063d0 (Between), FUN_10006310 (DX veto), FUN_10006e70 with the strip-end passes (FUN_10006ae0 LookAtEnd, FUN_10006ca0 LookAtBeginning, FUN_100064e0, FUN_10006630) and blind placement
 * (FUN_10006720), all docs/re/31-framing.md sec 7.1-7.7. */
#include <stdlib.h>
#include <string.h>
#include "framing/frame.h"

typedef struct { int start, width, src; } rc_t;
typedef struct { int start, len; } run_t;

typedef struct {
    int R, ratio, P, S, maxc, cap;      /* P = pitch rows, S = frame rows, cap = allocated rect slots */
    int first, last;
    const pk_frame_params *prm;
    uint8_t *B;                          /* R + 1 bits, zeroed tail */
    uint8_t *g;
    run_t *runs; int nruns;
    int good, lng, shrt;                 /* FUN_10006140's statistics, stale between calls (0 at the start, S-R19) */
    rc_t *RC; rc_t dummy;
    int count; unsigned scanw;
    int aps, inexact;
    int aggr, ends;                      /* FUN_100079c0's aggressive flag; 0 = detection only (Task 18's check), 1 = with the strip-end passes */
} fr_t;

/* Kodak writes RC[(2p)/P] without a bound (RE 31 sec 0 item 5); writes outside the allocation are dropped but still counted */
static rc_t *slot(fr_t *f, int p) {
    long long i = ((long long)p * 2) / f->P;
    if (p < 0 || i >= f->cap) { f->dummy.start = f->dummy.width = f->dummy.src = 0; return &f->dummy; }
    return &f->RC[i];
}

/* FUN_10006310 */
static int veto(const fr_t *f, rc_t *r) {
    const pk_frame_params *p = f->prm;
    if (!f->aps || p->n_dx_edges <= 0) return 1;     /* TLB: hole+0x64 stays 1 on 35 mm, the veto never runs */
    int s = r->start, w = r->width;
    for (int i = 0; i < p->n_dx_edges; i++) {
        int pp = p->dx_edge_rows[i];
        if (s <= pp && pp <= w + s && pp <= w / 4 + s) {
            int q = i + 1 < p->n_dx_edges ? p->dx_edge_rows[i + 1] : 0;
            if ((w * 3) / 4 + s <= q && q <= w + s) return 1;
        }
    }
    r->start = r->width = 0;
    return 0;
}

/* FUN_10005d20; B[first..last] = (T < g) */
static int threshold(fr_t *f, const int h[256], int mode) {
    int T;
    int cnt = f->last - f->first + 1, lim = cnt / 150;
    if (mode > 0) T = mode;
    else if (mode == 0) {
        int best = 0, bi = 0;
        for (int j = 0; j < 250; j++) {
            if (lim < best && h[j] < (best * 3) / 5) break;
            if (best < h[j]) { bi = j; best = h[j]; }
        }
        int lo = bi;
        while (lo != 0 && best / 20 <= h[lo]) lo--;
        int hl = bi + 0x32 < 0xFF ? bi + 0x32 : 0xFF, hi = bi;
        while (hi < hl && best / 10 <= h[hi]) hi++;
        if ((bi - lo) * 4 < hi - bi) {
            T = bi;
            while (T < 0xFF && (best >> 1) <= h[T]) T++;
        } else T = hi + (hi - bi) / 2;
    } else {
        long long tot = 0;
        for (int i = 0; i < 256; i++) tot += h[i];
        float tf = (float)((double)tot * (double)0.02f);   /* x87 at 53 bits, stored as a dword */
        double cum = 0.0;
        T = 250;
        for (int i = 0; i < 250; i++) {
            cum += (double)h[i];
            if ((double)tf < cum) { T = i; break; }
        }
    }
    for (int r = f->first; r <= f->last; r++) f->B[r] = T < f->g[r] ? 1 : 0;
    return T;
}

/* FUN_10006140 */
static int find_runs(fr_t *f) {
    int first = f->first, last = f->last;
    const uint8_t *B = f->B;
    int n = B[first];
    for (int i = first; i < last; i++) if (B[i] < B[i + 1]) n++;
    if (n == B[first]) { f->nruns = 0; return 0; }
    run_t *runs = f->runs;                 /* capacity R + 2 >= n + 1 */
    memset(runs, 0, (size_t)(n + 1) * sizeof *runs);
    int prev = B[first], e = 0, done = 0, L = 1;
    runs[0].start = first;
    for (int i = first; i <= last && n > 0; i++) {
        int cur = B[i];
        if (cur == prev) L++;              /* at i == first this counts the first row twice (Kodak) */
        else {
            if (cur == 0) { done++; runs[e].len = L; e++; }
            else runs[e].start = i;
            L = 1;
        }
        prev = cur;
    }
    if (prev == 1 && n > 0) runs[done].len = L;
    int lo = (f->S * 0x5F) / 100, hi = (f->S * 0x73) / 100;
    f->good = f->lng = f->shrt = 0;
    for (int i = 0; i < n; i++) {
        if (lo < runs[i].len) { if (runs[i].len < hi) f->good++; else f->lng++; }
        else f->shrt++;
    }
    f->nruns = n;
    return n;
}

/* FUN_10006930 placement */
static void place(fr_t *f, int p) {
    if (p <= f->first) p = f->first + 1;
    rc_t *e = slot(f, p);
    e->start = p;
    e->width = p + f->S < f->last ? f->S : (f->last - p) - 1;
    if (veto(f, e)) f->count++;
}
static void nice(fr_t *f) {
    int S = f->S, P = f->P, lo = (S * 0x5F) / 100, hi = (S * 0x73) / 100;
    for (int i = 0; i < f->nruns; i++) {
        int s = f->runs[i].start, L = f->runs[i].len;
        if (lo < L && L < hi) place(f, (L - S) / 3 + s);
        else if (lo + P < L && L < hi + P) { place(f, ((L - P) - S) / 3 + s); place(f, s + P); }
    }
}

/* FUN_100063d0 */
static void between(fr_t *f, int kfirst, int klast) {
    int P = f->P, prev = kfirst;
    for (int k = kfirst + 1; k <= klast; k++) {
        rc_t *cur = &f->RC[k];
        if (cur->start != 0 && cur->width != 0) {
            rc_t *pr = &f->RC[prev];
            int gap = ((cur->width / 2 - pr->width / 2) - pr->start) + cur->start;
            int miss = gap / P;
            if (gap - miss * P < (P >> 2)) miss--;
            int old = pr->start;
            prev = k;
            if (0 < miss) {
                int step = gap / (miss + 1), pos = old + step;
                while (miss) {
                    rc_t *e = slot(f, pos);
                    e->start = pos; e->width = f->S;
                    f->count++;
                    pos += step; miss--;
                }
            }
        }
    }
}

/* FUN_100064e0: the window of S rows, starting in start .. start+d-1, with the most set bits; ties go to the one nearest the centre. Rows past the
 * allocation are not read (Kodak reads the zeroed tail of its page, UNRESOLVED 4). */
static int best_window(const fr_t *f, int start, int d) {
    int S = f->S, half = d / 2, best = 0, bestw = half, bestpos = 0;
    long long lim = (long long)f->R + 8 + f->P;                  /* the zeroed B allocation */
    for (int j = 0; j < d; j++) {
        int W = 0;
        for (int k = 0; k < S; k++) { long long r = (long long)start + j + k; if (r >= 0 && r < lim) W += f->B[r]; }
        int w = j > half ? j - half : half - j;
        if (best <= W && (W != best || w < bestw)) { best = W; bestw = w; bestpos = start + j; }
    }
    return best != 0 ? bestpos : start + half;
}

/* FUN_10006630: is there a frame-sized run near the window a .. b? runs[] is the final run table */
static int cheap(const fr_t *f, int a, int b, int d) {
    const run_t *r = f->runs; int n = f->nruns;
    if (n <= 0) return 0;
    if (a < b) {
        int k = 0;
        while (k < n && !(a <= r[k].start + r[k].len)) k++;
        if (k == n) return b <= r[n - 1].start + r[n - 1].len;
        return r[k].start - a <= d * 20 || r[k].start + r[k].len < b - 10;
    }
    if (b < a) {
        int k = n - 1;
        while (k >= 0 && !(r[k].start + d * 2 <= a)) k--;
        return k != -1 && (a - r[k].len - r[k].start <= d * 20 || 10 < r[k].start);
    }
    return 0;
}

/* FUN_10006ae0 */
static void look_at_end(fr_t *f, int start, int last) {
    int P = f->P, S = f->S, d = P - S, h = d / 2, pos = h + start, lim = last - S / 2;
    if (pos >= lim) return;
    for (;;) {
        int e = pos + P < last ? pos + P : last;
        if (f->aggr == 0 && !cheap(f, pos, e, d)) return;
        if (last - pos < h + P) break;
        pos = best_window(f, pos, d);
        rc_t *r = slot(f, pos);
        r->start = pos; r->width = pos + S < last ? S : last - pos;
        if (!veto(f, r)) return;
        f->count++;
        pos = r->width + r->start + h;
        if (lim <= pos) return;
    }
    if (P / 2 + h <= last - pos) {
        pos += d;
        rc_t *r = slot(f, pos);
        r->start = pos; r->width = pos + S < last ? S : last - pos;
        if (veto(f, r)) f->count++;
    }
}

/* FUN_10006ca0 */
static void look_at_beginning(fr_t *f, int start, int first) {
    int P = f->P, S = f->S, d = P - S, h = d / 2, pos = start - h;
    if (pos <= first) return;
    for (;;) {
        int lo = pos - P, e = lo >= first ? lo : first;
        if (f->aggr == 0 && !cheap(f, pos, e, d)) return;
        if (pos - first < h + P) break;
        pos = best_window(f, lo, d);
        rc_t *r = slot(f, pos);
        r->start = pos; r->width = S;
        if (!veto(f, r)) return;
        f->count++;
        pos = r->start - h;
        if (pos <= first) return;
    }
    if (P / 2 + h <= pos - first) {
        int p = (pos - h) - S;
        rc_t *r;
        if (first < p) { r = slot(f, p); r->start = p; r->width = S; }
        else { p = first + 1; r = slot(f, p); r->start = p; r->width = p + S < pos - h ? S : (pos - p) - h; }
        if (veto(f, r)) f->count++;
    }
}

/* FUN_10006e70 */
static void e70(fr_t *f) {
    int maxc = f->maxc;
    f->count = 0;
    nice(f);
    int kf = maxc - 1, kl = 0, sf = f->first, el = f->last;
    for (int k = 0; k < maxc; k++) {
        rc_t *e = &f->RC[k];
        if (e->start != 0 && e->width != 0) {
            if (k <= kf) { kf = k; sf = e->start; }
            if (kl <= k) { kl = k; el = e->width + e->start; }
        }
    }
    if (kf <= kl) for (int k = kf; k <= kl; k++) if (f->RC[k].width > 0) f->RC[k].src = 1;
    int prior = f->count;
    if (prior > 1) between(f, kf, kl);
    if (kf <= kl) for (int k = kf; k <= kl; k++) if (f->RC[k].width > 0 && f->RC[k].src == 0) f->RC[k].src = 2;
    if (prior < f->count) { f->scanw |= 0x100; prior = f->count; }
    if (!f->ends || f->count < 1) return;
    look_at_end(f, el, f->last);
    for (int k = kl; k < maxc; k++) if (f->RC[k].width > 0 && f->RC[k].src == 0) f->RC[k].src = 4;
    if (prior < f->count) { f->scanw |= 0x200; prior = f->count; }
    look_at_beginning(f, sf, f->first);
    for (int k = 0; k < kf; k++) if (f->RC[k].width > 0 && f->RC[k].src == 0) f->RC[k].src = 3;
    if (prior < f->count) f->scanw |= 0x400;
}

/* FUN_10006720: blind placement, one frame per pitch */
static void blind_place(fr_t *f) {
    int P = f->P, S = f->S, half = (P - S) / 2, off = 0, n = 0, left = f->R - 1;
    f->count = 0;
    if (left > 0) {
        while (P + 4 < left) { f->RC[n].start = off + half; f->RC[n].width = S; left -= P; off += P; f->count++; n++; }
        if (S / 2 < left) { off += half; f->RC[n].start = off; f->RC[n].width = (f->R - 1 - off) - 4; f->count++; }
    }
    for (int k = 0; k < f->count; k++) if (f->RC[k].width > 0 && f->RC[k].src == 0) f->RC[k].src = 9;
}

/* FUN_100072c0 */
static pk_status detect(fr_t *f, const uint8_t *prof, int positive) {
    for (int r = 0; r < f->R; r++) {
        int m = (prof[3 * r] + prof[3 * r + 1] + prof[3 * r + 2]) / 3;
        f->g[r] = (uint8_t)(positive ? m : 255 - m);
    }
    int h[256]; memset(h, 0, sizeof h);
    for (int r = f->first; r <= f->last; r++) h[f->g[r]]++;
    int T0 = threshold(f, h, 0);
    int n = find_runs(f);
    if (n == 0) f->inexact = 1;              /* S-R19: the statistics below are Kodak's uninitialised stack ints (0 here) */
    int T1, Tcur, bestT, bestg, g430;
    if (n < 2) { T1 = threshold(f, h, -1); Tcur = bestT = T1; bestg = g430 = f->good; }
    else { n = find_runs(f); T1 = T0; Tcur = bestT = T0; bestg = g430 = f->good; }
    int s438, s430, sT;
    for (;;) {                                  /* loop A: walk the threshold up */
        s438 = bestg; s430 = g430; sT = bestT;
        if (!(1 <= Tcur && Tcur <= 249) || f->lng < 1) break;
        Tcur = threshold(f, h, Tcur + 2);
        n = find_runs(f);
        bestT = Tcur; bestg = g430 = f->good;
        if (s438 < f->good) continue;
        bestT = sT; bestg = s438; g430 = s430;
        if (s430 <= f->good) continue;
        break;
    }
    bestT = sT; bestg = s438;
    Tcur = threshold(f, h, T1);
    n = find_runs(f);
    g430 = f->good;
    for (;;) {                                  /* loop B: walk down */
        s438 = bestg; s430 = g430; sT = bestT;
        if (!(0x1A <= Tcur && Tcur <= 0xFF) || (f->shrt < 1 && 1 < n)) break;
        Tcur = threshold(f, h, Tcur - 2);
        n = find_runs(f);
        bestT = Tcur; bestg = g430 = f->good;
        if (s438 < f->good) continue;
        bestT = sT; bestg = s438; g430 = s430;
        if (s430 <= f->good) continue;
        break;
    }
    threshold(f, h, sT);
    find_runs(f);
    e70(f);
    return PK_OK;
}

static int pitch_window(int frame_lines) {
    switch (frame_lines) { case 1500: return 1603; case 2250: return 2405; case 3000: return 3206; default: return 0; }
}

/* mode 0: detection only; 1: detection plus the strip-end passes (FUN_100079c0(strip, aggr, 0, 0)); 2: blind placement (FUN_100079c0(strip, 1, 1, 0)),
 * continuing from the first pass's scanw and exactness flag (carry). */
enum { M_DETECT, M_FULL, M_BLIND };
static pk_status frame_pass(const uint8_t *profile, int rows, const pk_frame_params *p, const pkf_film *film, int mode, const pk_framing *carry, pk_framing **out) {
    if (!out) return PK_E_ARG;
    *out = NULL;
    if (!profile || !p || !film || (p->ratio != 4 && p->ratio != 6 && p->ratio != 8) || p->strip_lines <= 0 || rows > (1 << 24) || rows < 0 || p->ratio <= 0 || p->frame_pitch_lines <= 0 || p->n_dx_edges < 0 || (p->n_dx_edges && !p->dx_edge_rows)) return PK_E_ARG;
    int win = film->scan_window_lines ? film->scan_window_lines : pitch_window(p->frame_pitch_lines);
    if (win <= 0) return PK_E_ARG;
    pk_framing *o = calloc(1, sizeof *o);
    if (!o) return PK_E_NOMEM;
    int ratio = p->ratio, P = win / ratio, S = p->frame_pitch_lines / ratio;
    if (P <= 0 || S <= 0) { free(o); return PK_E_ARG; }
    int maxc = (int)(((long long)rows * 2) / P);
    if (maxc < 1) { *out = o; return PK_OK; }
    fr_t f; memset(&f, 0, sizeof f);
    f.R = rows; f.ratio = ratio; f.P = P; f.S = S; f.maxc = maxc; f.cap = maxc + 64; f.prm = p;
    f.first = 0; f.last = rows - 1; f.aps = film->aps;
    f.ends = mode != M_DETECT; f.aggr = mode == M_BLIND ? 1 : p->aggressive;
    if (carry) { f.scanw = carry->scanw; f.inexact = carry->not_kodak_exact; }
    if (film->aps && P * 10 < rows) { int skip = (250 * 0x6338) / 23700; f.first = skip; f.last = rows - skip - 1; }
    if (f.first > f.last) { free(o); return PK_E_ARG; }
    f.B = calloc((size_t)rows + 8 + (size_t)P, 1);
    f.g = calloc((size_t)rows + 1, 1);
    f.runs = calloc((size_t)rows + 3, sizeof *f.runs);
    f.RC = calloc((size_t)f.cap, sizeof *f.RC);
    pk_status st = PK_OK;
    if (!f.B || !f.g || !f.runs || !f.RC) st = PK_E_NOMEM;
    else if (mode == M_BLIND) { f.scanw |= 0x800; blind_place(&f); }
    else st = detect(&f, profile, film->positive);
    if (st == PK_OK) {
        pk_frame_rect *rc = calloc((size_t)maxc, sizeof *rc);
        if (!rc) st = PK_E_NOMEM;
        else {
            int n = 0, fl = p->frame_pitch_lines, nh = p->strip_lines;
            for (int k = 0; k < maxc; k++) {
                const rc_t *e = &f.RC[k];
                if (e->width == 0 || e->start == 0) continue;
                int top, bot;
                if (film->aps) {
                    top = ratio * e->start;
                    bot = top + (fl - 1);
                    if (top < 0) top = 0;
                    if (nh <= bot) bot = nh - 1;
                } else {
                    if (e->width < S && e->start < 5) { bot = ratio * (e->width + e->start); top = bot - fl; }
                    else { top = ratio * e->start; bot = top - 1 + fl; }
                    if (top < 0) top = 0;
                    if (nh <= bot) bot = nh - 1;
                    if (bot - top < ratio * 0x10) { if (e->start < 5) bot = ratio * 0x10 + top; else top = bot - ratio * 0x10; }
                }
                rc[n].top = top; rc[n].bottom = bot;
                /* Kodak divides unsigned here; identical while top >= 0 and bottom >= top - 1, which holds unless strip_lines is far below rows * ratio */
                rc[n].lo_top = top / ratio;                                       /* FUN_10027350 */
                rc[n].lo_bottom = ((bot - top + 1) / ratio - 1) + top / ratio;
                rc[n].number = n; rc[n].type = (char)e->src;
                n++;
            }
            o->n = n; o->rects = rc; o->scanw = f.scanw; o->not_kodak_exact = f.inexact != 0;
        }
    }
    free(f.B); free(f.g); free(f.runs); free(f.RC);
    if (st != PK_OK) { free(o->rects); free(o); return st; }
    *out = o;
    return PK_OK;
}

pk_status pkf_detect(const uint8_t *profile, int rows, const pk_frame_params *p, pk_framing **out) {
    static const pkf_film def = { 0, false, false };
    return frame_pass(profile, rows, p, &def, M_DETECT, NULL, out);
}
pk_status pkf_detect_ex(const uint8_t *profile, int rows, const pk_frame_params *p, const pkf_film *film, pk_framing **out) {
    return frame_pass(profile, rows, p, film, M_DETECT, NULL, out);
}

/* FN_bEndScan's sequence for one strip: FUN_100079c0(strip, aggressive, 0, 0), and when that finds no frame FUN_100079c0(strip, 1, 1, 0) */
pk_status pkf_frame_ex(const uint8_t *profile, int rows, const pk_frame_params *p, const pkf_film *film, pk_framing **out) {
    pk_framing *a;
    if (!out) return PK_E_ARG;
    pk_status st = frame_pass(profile, rows, p, film, M_FULL, NULL, &a);
    if (st != PK_OK) { *out = NULL; return st; }
    if (a->n > 0) { *out = a; return PK_OK; }
    pk_framing *b;
    st = frame_pass(profile, rows, p, film, M_BLIND, a, &b);
    pk_framing_free(a);
    *out = st == PK_OK ? b : NULL;
    return st;
}

pk_status pk_frame_strip_profile(const uint8_t *profile, int rows, const pk_frame_params *p, const pk_frame_film *film, pk_framing **out) {
    pkf_film f = { 0, film ? film->positive : false, film ? film->aps : false };
    return pkf_frame_ex(profile, rows, p, &f, out);
}

pk_status pkf_frame_strip(const pkd_strip *s, int planes, const pk_frame_params *p, const pk_frame_film *film, pk_framing **out) {
    if (!s || !out || (planes != 3 && planes != 4)) return PK_E_ARG;
    return pk_frame_strip_profile(s->profile, (int)pkd_strip_readable_rows((size_t)s->rows, planes), p, film, out);
}

void pk_framing_free(pk_framing *f) { if (f) { free(f->rects); free(f); } }

int pkf_dx_rows(const pkb_dx_event *ev, size_t n_ev, int ratio, int *rows_out, int cap) {
    (void)ev; (void)n_ev; (void)ratio; (void)rows_out; (void)cap;
    return 0;
}
