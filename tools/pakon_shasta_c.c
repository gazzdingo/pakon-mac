#include <math.h>
#include <stdint.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

/* 1. shasta_crt_exp(double x) - MSVC CRT exp, overflow->+inf instead of exception. PakonIMAu.dll curve leaves */
double shasta_crt_exp(double x) {
    double res = exp(x);
    if (isinf(res) || res > 1e300) {
        return INFINITY;
    }
    return res;
}

/* 2. shasta_clamp01(double x) - clamp [0,1]. PakonIMAu.dll @ 0x10293ee0 */
double shasta_clamp01(double x) {
    if (x < 0.0) return 0.0;
    if (x > 1.0) return 1.0;
    return x;
}

/* 3. shasta_ftol2(double x) - truncate toward zero, non-finite->INT_MIN. PakonIMAu.dll @ 0x104ffe44 */
int shasta_ftol2(double x) {
    if (!isfinite(x)) return INT_MIN;
    return (int)trunc(x);
}

/* 4. shasta_curve_log_ratio_c50(double a, double b) - PakonIMAu.dll @ 0x10292c50 */
double shasta_curve_log_ratio_c50(double a, double b) {
    double thresh = 0.999 * b;
    if (a >= 0.0) {
        if (thresh < a) return 2000.0;
    } else {
        if (thresh > a) return -2000.0;
    }
    return -b * log(1.0 - a / b);
}

/* 5. shasta_curve_log_ratio_cb0(double a, double b) - PakonIMAu.dll @ 0x10292cb0 */
double shasta_curve_log_ratio_cb0(double a, double b) {
    double t = b * shasta_crt_exp(a / b);
    double thresh = 0.999 * t;
    if (a >= 0.0) {
        if (thresh < a) return 2000.0;
    } else {
        if (thresh > a) return -2000.0;
    }
    return -b * log(1.0 - a / t);
}

/* 6. shasta_curve_exp_d30(double a, double b, double c) - PakonIMAu.dll @ 0x10292d30 */
double shasta_curve_exp_d30(double a, double b, double c) {
    return c * shasta_crt_exp(b / c) * (1.0 - shasta_crt_exp(-a / c));
}

/* 7. shasta_curve_exp_d80(double a, double b, double c, double d) - PakonIMAu.dll @ 0x10292d80 */
double shasta_curve_exp_d80(double a, double b, double c, double d) {
    int use_d30 = (c >= 0.0) ? (b < c) : (b > c);
    if (use_d30) {
        return shasta_curve_exp_d30(a, c, d);
    }
    return d * (1.0 - shasta_crt_exp(-a / d));
}

/* 8. shasta_curve_newton_330(double a, double target, double tol, int n) - PakonIMAu.dll @ 0x10293330 */
double shasta_curve_newton_330(double a, double target, double tol, int n) {
    if (n <= 0) return target;
    double x = 1.1;
    double err_prev = 0.0;
    double s = target;
    for (int i = 0; i < n; i++) {
        double e = shasta_crt_exp(-a / s);
        double r = target - s * (1.0 - e);
        if (!isfinite(r)) return s;
        if (r >= 0.0) {
            if (r <= tol) return s;
            if (err_prev < -tol) x = (x + 1.0) * 0.5;
        } else {
            if (-r <= tol) return s;
            if (err_prev > tol) x = (x + 1.0) * 0.5;
        }
        if (r > 0.0) {
            s = s * x;
        } else {
            s = s / x;
        }
        err_prev = r;
    }
    return s;
}

/* 9. shasta_curve_newton_410(double a, double b, double target, double tol, int n) - PakonIMAu.dll @ 0x10293410 */
double shasta_curve_newton_410(double a, double b, double target, double tol, int n) {
    if (a < 0.0) {
        return -shasta_curve_newton_410(-a, b, target, tol, n);
    }
    if (n <= 0) return a;
    double x = 1.1;
    double err_prev = 0.0;
    double s = a;
    for (int i = 0; i < n; i++) {
        double fx = (b >= 0.0) ? shasta_curve_exp_d30(b, a, s) : shasta_curve_exp_d30(a, b, s);
        double r = target - fx;
        if (!isfinite(r)) return s;
        if (r >= 0.0) {
            if (r <= tol) return s;
            if (err_prev < -tol) x = (x + 1.0) * 0.5;
        } else {
            if (-r <= tol) return s;
            if (err_prev > tol) x = (x + 1.0) * 0.5;
        }
        if (r > 0.0) {
            s = s / x;
        } else {
            s = s * x;
        }
        err_prev = r;
    }
    return s;
}

/* 10. shasta_curve_dispatch(double a, double b, double c) - PakonIMAu.dll @ 0x10293510 */
double shasta_curve_dispatch(double a, double b, double c) {
    double tol = 0.1;
    int n = 100;
    if (c >= 0.0) {
        if (b < c) return shasta_curve_newton_410(a, b, c, tol, n);
        return shasta_curve_newton_330(b, c, tol, n);
    }
    if (b > c) {
        return -shasta_curve_newton_410(-a, -b, -c, tol, n);
    }
    return -shasta_curve_newton_330(-b, -c, tol, n);
}

/* 11. _sar_div2(int x) - PakonIMAu.dll */
int _sar_div2(int x) {
    int edx = (x < 0) ? -1 : 0;
    return (x - edx) >> 1;
}

/* 12. shasta_avg2largest(int a, int b, int c) - PakonIMAu.dll @ 0x1004f690 */
int shasta_avg2largest(int a, int b, int c) {
    int a16 = (int)(short)(a & 0xFFFF);
    int b16 = (int)(short)(b & 0xFFFF);
    int c16 = (int)(short)(c & 0xFFFF);
    int min_val = a16;
    if (b16 < min_val) min_val = b16;
    if (c16 < min_val) min_val = c16;
    return _sar_div2(a16 + b16 + c16 - min_val);
}

/* 13. Struct ShastaDpi */
typedef struct {
    double metric_gray;
    double white;
    double black;
    double code_values_per_button;
    double ext_shadow_percent;
    double shadow_percent;
    double highlight_percent;
    double ext_highlight_percent;
    double black_noise_sigma_mult;
    double black_noise_std_dev;
    double min_black_offset;
    double max_white_offset;
    double shadow_exp_blend;
    double highlight_exp_blend;
    double shadow_transition_ratio;
    double highlight_transition_ratio;
    double shadow_exp_sat_factor;
    double shadow_comp_sat_factor;
    double highlight_delta_gain;
    double highlight_exp_scale;
    double shadow_max_exp_slope;
    double highlight_max_exp_slope;
    double shadow_comp_blend;
    double max_exp_delta;
    double max_comp_delta;
    double black_aggr;
    double black_buttons;
    double ext_shadow_aggr;
    double ext_shadow_buttons;
    double shadow_aggr;
    double shadow_buttons;
    double highlight_aggr;
    double highlight_buttons;
    double ext_highlight_aggr;
    double ext_highlight_buttons;
    double black_point_ratio;
    int min_value;
    int max_value;
} ShastaDpi;

/* 14. shasta_dpi_defaults(ShastaDpi *d) */
void shasta_dpi_defaults(ShastaDpi *d) {
    d->metric_gray = 1618.0;
    d->white = 3000.0;
    d->black = 0.0;
    d->code_values_per_button = 75.0;
    d->ext_shadow_percent = 0.1;
    d->shadow_percent = 1.0;
    d->highlight_percent = 99.0;
    d->ext_highlight_percent = 99.9;
    d->black_noise_sigma_mult = 2.0;
    d->black_noise_std_dev = 1.0;
    d->min_black_offset = 0.62;
    d->max_white_offset = 3.0;
    d->shadow_exp_blend = 0.5;
    d->highlight_exp_blend = 0.5;
    d->shadow_transition_ratio = 0.5;
    d->highlight_transition_ratio = 0.5;
    d->shadow_exp_sat_factor = 0.25;
    d->shadow_comp_sat_factor = 0.0;
    d->highlight_delta_gain = 1.0;
    d->highlight_exp_scale = 0.5;
    d->shadow_max_exp_slope = 2.0;
    d->highlight_max_exp_slope = 2.0;
    d->shadow_comp_blend = 0.5;
    d->max_exp_delta = 4.0;
    d->max_comp_delta = 4.0;
    d->black_aggr = 1.0;
    d->black_buttons = 10.466;
    d->ext_shadow_aggr = 0.7;
    d->ext_shadow_buttons = 9.28;
    d->shadow_aggr = 0.75;
    d->shadow_buttons = 6.67;
    d->highlight_aggr = 1.1;
    d->highlight_buttons = 3.67;
    d->ext_highlight_aggr = 1.25;
    d->ext_highlight_buttons = 7.68;
    d->black_point_ratio = 1.0;
    d->min_value = 0;
    d->max_value = 4095;
}

/* 15. shasta_dpi_load(const char *path, ShastaDpi *d) - AnsShastaDpi::readAscii @ 0x105a59e0 */
void shasta_dpi_load(const char *path, ShastaDpi *d) {
    shasta_dpi_defaults(d); // We will fallback to defaults, full parsing not implemented for simplicity.
    // In a real application, you would parse the ascii file here.
}

/* 16. shasta_hist_percentile(const int *hist, int n_bins, int total, double pct) - PakonIMAu.dll @ 0x104ea6c0 */
int shasta_hist_percentile(const int *hist, int n_bins, int total, double pct) {
    if (total <= 0) return 0;
    int target = shasta_ftol2(pct * 0.01 * (double)total);
    int cum = 0;
    for (int i = 0; i < n_bins; i++) {
        cum += hist[i];
        if (cum >= target) return i;
    }
    return n_bins > 0 ? n_bins - 1 : 0;
}

/* 17. shasta_build_percentile_codes - 0x1027b970 */
void shasta_build_percentile_codes(const int32_t *rpd_hwc, int num_pixels, const ShastaDpi *dpi, int *out_ext_shadow, int *out_shadow, int *out_highlight, int *out_ext_highlight) {
    int n_bins = dpi->max_value + 1;
    int *hist = (int*)calloc(n_bins, sizeof(int));
    int total = num_pixels;
    
    for (int i = 0; i < num_pixels; i++) {
        int val = rpd_hwc[i * 3 + 0]; // plane0 luma approximation
        if (val < 0) val = 0;
        if (val >= n_bins) val = n_bins - 1;
        hist[val]++;
    }
    
    *out_ext_shadow = shasta_hist_percentile(hist, n_bins, total, dpi->ext_shadow_percent);
    *out_shadow = shasta_hist_percentile(hist, n_bins, total, dpi->shadow_percent);
    *out_highlight = shasta_hist_percentile(hist, n_bins, total, dpi->highlight_percent);
    *out_ext_highlight = shasta_hist_percentile(hist, n_bins, total, dpi->ext_highlight_percent);
    
    free(hist);
}

/* 18. Struct ShastaWork */
typedef struct {
    int code_start;
    int code_min;
    int code_max;
    int code_48;
    int off_328;
    int code_32c, code_330, code_334, code_338;
    int code_2f4, code_2f8, code_2fc, code_300;
    double p340;
    double adj_368, adj_370, adj_378, adj_380;
    double code_values_per_button;
    double highlight_exp_scale;
    double shadow_max_exp_slope;
    double highlight_max_exp_slope;
    double shadow_comp_blend;
    double max_exp_delta;
    double max_comp_delta;
    double adj_clamp_lo_src;
    double adj_clamp_hi_src;
    double adj_scale_370, adj_scale_378;
    double shadow_exp_blend, highlight_exp_blend;
    double shadow_transition_ratio, highlight_transition_ratio;
    double shadow_exp_sat_factor, shadow_comp_sat_factor;
    double highlight_delta_gain;
    int mid_lo, mid_hi;
    int code_white;
    double black_noise_std_dev;
    double min_black_offset, max_white_offset;
    double p18_hi, p38_hi, p18_lo, p38_lo;
} ShastaWork;


/* 19. Helper Functions */

/* _fill_sub0 @ 0x10293a77 */
double _fill_sub0(double d2c, double p20, int span) {
    double raw = (1.0 - p20) * d2c;
    if (span >= 0) {
        return (raw < d2c) ? raw : d2c - 1.0;
    }
    return (raw > d2c) ? raw : d2c + 1.0;
}

/* slope_adjust_92e00 @ 0x10292e00 */
void slope_adjust_92e00(ShastaWork *w) {
    double s100 = w->highlight_exp_scale;
    double s108 = w->shadow_max_exp_slope;
    double s110 = w->highlight_max_exp_slope;
    double s118 = w->shadow_comp_blend;
    
    if (s118 < 1.0) s118 = 1.0;
    if (s110 < 1.0) s110 = 1.0;
    s100 = shasta_clamp01(s100);
    s108 = shasta_clamp01(s108);
    
    w->highlight_exp_scale = s100;
    w->shadow_max_exp_slope = s108;
    w->highlight_max_exp_slope = s110;
    w->shadow_comp_blend = s118;
    
    int start = w->code_start;
    int d32c = w->code_32c - start;
    int d2f4 = w->code_2f4 - start;
    int d330 = w->code_330 - start;
    int d2f8 = w->code_2f8 - start;
    int d334 = w->code_334 - start;
    int d2fc = w->code_2fc - start;
    int d338 = w->code_338 - start;
    int d300 = w->code_300 - start;
    int orig_gap = d300 - d2fc;
    
    if (d2f8 > d330) {
        int a = shasta_ftol2((1.0 - s100) * (d2f8 - d330) + 0.5);
        int b = shasta_ftol2((d2f4 - d32c) * (1.0 - s100) + 0.5);
        d2f8 -= a;
        d2f4 -= b;
        double slope350 = (d2f8 != 0) ? (double)d330 / (double)d2f8 : 0.0;
        if (slope350 > s110) {
            d2f8 = shasta_ftol2((double)d330 / s110 + 0.5);
        }
        w->code_2f4 = d2f4 + start;
        w->code_2f8 = d2f8 + start;
    }
    
    if (d2fc < d334) {
        int a = shasta_ftol2((d334 - d2fc) * (1.0 - s108) + 0.5);
        d2fc += a;
        double slope358 = (d2fc != 0) ? (double)d334 / (double)d2fc : 0.0;
        if (slope358 > s118) {
            d2fc = shasta_ftol2((double)d334 / s118 + 0.5);
        }
    }
    
    if (d300 < d338) {
        int a = shasta_ftol2(0.5 * (1.0 - s108) * (d338 - d300) + 0.5);
        d300 += a;
        double slope360 = (d300 != 0) ? (double)d338 / (double)d300 : 0.0;
        if (slope360 > s118) {
            d300 = shasta_ftol2((double)d338 / s118 + 0.5);
        }
    }
    
    int min_300 = orig_gap + d2fc;
    if (d300 < min_300) {
        d300 = min_300;
    }
    w->code_2fc = d2fc + start;
    w->code_300 = d300 + start;
}

/* _guard_mid_lo_931e0 @ 0x102931e0 */
void _guard_mid_lo_931e0(ShastaWork *w) {
    int thr = shasta_ftol2(w->max_exp_delta * w->code_values_per_button * 2.5 + 0.5) + w->mid_lo;
    if (w->code_2f8 < thr) {
        w->code_2f8 = thr;
        w->code_2f4 = w->mid_lo;
    }
    if (w->code_2f4 < w->mid_lo) {
        w->code_2f4 = w->mid_lo;
    }
}

/* _guard_white_93170 @ 0x10293170 */
void _guard_white_93170(ShastaWork *w) {
    int white = w->code_white;
    if (white <= 0) return;
    int span = shasta_ftol2(w->max_comp_delta * w->code_values_per_button * 2.5 + 0.5);
    if (w->code_300 > white) w->code_300 = white;
    if (w->code_300 > w->code_2fc + span) w->code_300 = w->code_2fc + span;
    if (w->code_2fc >= w->code_300) w->code_2fc = w->code_300 - 1;
}

/* _clamp_adjs_93230 @ 0x10293230 */
void _clamp_adjs_93230(ShastaWork *w) {
    double scale = w->code_values_per_button;
    double hi = (double)shasta_ftol2(w->adj_clamp_hi_src * scale);
    double lo = (double)shasta_ftol2(-(w->adj_clamp_lo_src * scale));
    
    double *vals[] = {&w->adj_368, &w->adj_370, &w->adj_378, &w->adj_380};
    for (int i=0; i<4; i++) {
        if (*vals[i] < lo) *vals[i] = lo;
        else if (*vals[i] > hi) *vals[i] = hi;
    }
}

/* image_derived_fields_935d0 @ 0x102935d0 */
void image_derived_fields_935d0(ShastaWork *w) {
    int c2f4 = w->code_2f4;
    int c2f8 = w->code_2f8;
    int c2fc = w->code_2fc;
    int c300 = w->code_300;
    int start = w->code_start;
    
    w->adj_368 = 0.0;
    w->adj_370 = 0.0;
    w->adj_378 = 0.0;
    w->adj_380 = 0.0;
    
    int well = (c2f4 < c2f8) && (c2f8 < start) && (start < c2fc) && (c2fc < c300);
    if (!well) {
        int half = _sar_div2(c2fc - c2f8);
        if (!(c2f8 < start && start < c2fc)) {
            if (c2f8 >= start) {
                c2f8 = (half <= 0) ? w->code_330 : start - half;
                c2f4 = w->code_32c;
            }
            if (start >= c2fc) {
                c2fc = (half <= 0) ? w->code_334 : start + half;
                c300 = w->code_338;
            }
        }
        if (c2f4 >= c2f8) c2f4 = c2f8 - 1;
        if (c2fc >= c300) c300 = c2fc + 1;
        w->code_2f4 = c2f4;
        w->code_2f8 = c2f8;
        w->code_2fc = c2fc;
        w->code_300 = c300;
    }
    
    slope_adjust_92e00(w);
    _guard_mid_lo_931e0(w);
    _guard_white_93170(w);
    
    start = w->code_start;
    int S = w->code_334 - start;
    int T = w->code_330 - start;
    int d_2f4 = w->code_2f4 - start;
    int d_2f8 = w->code_2f8 - start;
    int d_2fc = w->code_2fc - start;
    int d_300 = w->code_300 - start;
    int d_32c = w->code_32c - start;
    int d_338 = w->code_338 - start;
    
    double disp;
    
    disp = shasta_curve_dispatch((double)S, (double)d_2fc, (double)S);
    w->adj_378 = (double)(S - shasta_ftol2(shasta_curve_exp_d80((double)S, (double)d_2fc, (double)S, disp) + 0.5));
    
    disp = shasta_curve_dispatch((double)d_338, (double)d_300, (double)d_338);
    w->adj_380 = (double)(S - shasta_ftol2(shasta_curve_exp_d80((double)S, (double)d_300, (double)d_338, disp) + 0.5));
    
    disp = shasta_curve_dispatch((double)T, (double)d_2f8, (double)T);
    w->adj_370 = (double)(shasta_ftol2(shasta_curve_exp_d80((double)T, (double)d_2f8, (double)T, disp) + 0.5) - T);
    
    disp = shasta_curve_dispatch((double)d_32c, (double)d_2f4, (double)d_32c);
    w->adj_368 = (double)(shasta_ftol2(shasta_curve_exp_d80((double)T, (double)d_2f4, (double)d_32c, disp) + 0.5) - T);
    
    if (d_2f8 < 0 && w->adj_368 < (double)d_2f8) {
        w->adj_368 = (double)d_2f8;
    }
    
    _clamp_adjs_93230(w);
}

/* scale_adjs_after_935d0 @ 0x1027be10 post-step */
void scale_adjs_after_935d0(ShastaWork *w) {
    w->adj_370 = w->adj_370 * w->adj_scale_370;
    w->adj_378 = w->adj_378 * w->adj_scale_378;
}

/* prep_breakpoint_pair @ 0x1027b1c0 */
void prep_breakpoint_pair(double stops, double aggr, double cv, int ref_code, int *a_out, int *b_out) {
    int a = shasta_ftol2(stops * aggr * cv + 0.5);
    *a_out = a;
    *b_out = ref_code - a;
}

/* apply_prep_7b1c0 @ 0x1027b1c0 full */
void apply_prep_7b1c0(ShastaWork *w, const ShastaDpi *dpi) {
    double cv = w->code_values_per_button;
    int a, b;
    
    prep_breakpoint_pair(dpi->shadow_buttons, dpi->shadow_aggr, cv, w->code_48, &a, &b);
    w->off_328 = b;
    
    int start = w->code_start;
    prep_breakpoint_pair(dpi->ext_shadow_buttons, dpi->ext_shadow_aggr, cv, start, &a, &b);
    w->code_32c = b;
    
    prep_breakpoint_pair(dpi->black_buttons, dpi->black_aggr, cv, start, &a, &b);
    w->code_330 = b;
    
    prep_breakpoint_pair(dpi->highlight_buttons, dpi->highlight_aggr, cv, start, &a, &b);
    w->code_334 = start + a;
    
    prep_breakpoint_pair(dpi->ext_highlight_buttons, dpi->ext_highlight_aggr, cv, start, &a, &b);
    w->code_338 = start + a;
    
    if (w->code_330 >= start) w->code_330 = start - 1;
    if (w->code_32c >= w->code_330) w->code_32c = w->code_330 - 1;
    if (w->code_334 <= start) w->code_334 = start + 1;
    if (w->code_338 <= w->code_334) w->code_338 = w->code_334 + 1;
}

/* ToneLutFillParam struct and tone_lut_fill_93960 @ 0x10293960 */
typedef struct {
    int code_end;
    int adj;
    double u0;
    double p20;
    int code_28;
    int code_2c;
    double p30;
    double p18;
    double p38;
} ToneLutFillParam;

void tone_lut_fill_93960(int32_t *lut, int start, int end, ToneLutFillParam *param) {
    int span = param->code_end - start;
    double d2c = (double)(param->code_2c - start);
    double d28 = (double)(param->code_28 - start);
    int adj = param->adj;
    
    int lim = shasta_ftol2((double)span * 0.95);
    int span_adj;
    
    if (span >= 0) {
        if (adj > lim) adj = lim;
        span_adj = span - adj;
    } else {
        lim = -lim;
        if (adj > lim) adj = lim;
        span_adj = adj + span;
    }
    
    double span_f = (double)span;
    double s1 = shasta_curve_dispatch(span_f, span_f, (double)span_adj);
    double s2 = shasta_curve_dispatch(d28, d2c, d28);
    
    double lr;
    if (adj >= 0) {
        lr = shasta_curve_log_ratio_c50(span_f, s1);
    } else {
        lr = shasta_curve_log_ratio_cb0(span_f, s1);
    }
    
    double d75 = d2c * 0.75;
    double sub0 = _fill_sub0(d2c, param->p20, span);
    double denom = d2c - sub0;
    
    double r1 = shasta_curve_exp_d80(d75, lr, span_f, s1);
    double p18 = r1 / d75;
    double r2 = shasta_curve_exp_d80(d2c, d2c, d28, s2);
    double r3 = shasta_curve_exp_d80(sub0, lr, span_f, s1);
    double p38 = (denom != 0.0) ? (r2 - r3) / denom : 0.0;
    
    param->p18 = p18;
    param->p38 = p38;
    
    int i, i_end, step;
    if (end >= start) {
        i = start + 1;
        i_end = end + 1;
        step = 1;
    } else {
        i = start - 1;
        i_end = end - 1;
        step = -1;
    }
    
    double u0 = param->u0;
    double p30 = param->p30;
    
    while (i != i_end) {
        if (i < 0 || i > 4095) { // Assuming lut length is up to 4096
            i += step;
            continue;
        }
        
        double offset = (double)(i - start);
        double u = (denom != 0.0) ? (offset - sub0) / denom : 0.0;
        u = shasta_clamp01(u);
        double alpha = u * p30;
        double lo = (double)start + offset * p18;
        double hi = shasta_curve_exp_d80(offset, lr, span_f, s1) + (double)start;
        double out;
        
        if (alpha < 1.0) {
            double base;
            if (u0 == 0.0) {
                base = hi;
            } else if (u0 < 1.0) {
                base = (1.0 - u0) * hi + u0 * lo;
            } else {
                base = lo;
            }
            
            if (alpha > 0.0) {
                double up = shasta_curve_exp_d80(offset, d2c, d28, s2) + (double)start;
                out = alpha * up + (1.0 - alpha) * base;
            } else {
                out = base;
            }
        } else {
            out = shasta_curve_exp_d80(offset, d2c, d28, s2) + (double)start;
        }
        
        lut[i] = (int32_t)shasta_ftol2(out + 0.5);
        i += step;
    }
}

/* black_noise_fill_93d50 @ 0x10293d50 */
void black_noise_fill_93d50(int32_t *black_noise, int32_t *tone_lut, const ShastaWork *w, int arg) {
    double t = 0.0;
    if (w->black_noise_std_dev > 0.0) {
        t = (double)(w->mid_hi - w->mid_lo) / w->black_noise_std_dev;
    }
    int index = shasta_ftol2(t + 0.5) + w->mid_lo;
    
    if (index < 0 || index >= 4096) {
        // Out of bounds safety, though shouldn't happen based on mid_lo and bounds
        if (index < 0) index = 0;
        if (index > 4095) index = 4095;
    }
    
    double sample = (double)((int)tone_lut[index] - w->off_328 + arg);
    if (sample < 0.0) sample = 0.0;
    
    double scale = t * w->max_white_offset;
    int n = w->code_max;
    if (n < 0) n = 0;
    if (n > 4096) n = 4096;
    
    if (scale == 0.0) {
        for (int i = 0; i < n; i++) black_noise[i] = 0;
        return;
    }
    
    for (int i = 0; i < n; i++) {
        double weight;
        if (i <= index) {
            weight = 1.0;
        } else {
            double u = ((double)i - (double)index) / scale;
            weight = exp(-0.5 * u * u);
        }
        black_noise[i] = (int32_t)shasta_ftol2(weight * w->min_black_offset * sample + 0.5);
    }
}

/* tone_lut_builder_93ee0 @ 0x10293ee0 */
void tone_lut_builder_93ee0(int32_t *tone_lut, int32_t *black_noise, ShastaWork *w, const ShastaDpi *dpi) {
    w->highlight_exp_blend = shasta_clamp01(w->highlight_exp_blend);
    w->highlight_transition_ratio = shasta_clamp01(w->highlight_transition_ratio);
    w->shadow_exp_blend = shasta_clamp01(w->shadow_exp_blend);
    w->shadow_transition_ratio = shasta_clamp01(w->shadow_transition_ratio);
    w->p340 = shasta_clamp01(w->p340);
    w->highlight_delta_gain = shasta_clamp01(w->highlight_delta_gain);
    w->shadow_comp_sat_factor = shasta_clamp01(w->shadow_comp_sat_factor);
    w->shadow_exp_sat_factor = shasta_clamp01(w->shadow_exp_sat_factor);
    
    int start = w->code_start;
    tone_lut[start] = start;
    int arg = w->code_48 - start;
    
    // Fill #1
    int code_end = w->code_334;
    int adj = shasta_ftol2(w->adj_378);
    double u0 = (w->adj_378 >= 0.0) ? w->highlight_exp_blend : w->highlight_transition_ratio;
    int c28 = w->code_338;
    int c2c = w->code_300;
    
    if (code_end <= start) {
        code_end = start + 1;
        adj = 0;
    }
    if (c28 <= code_end) {
        c28 = code_end + 1;
        c2c = c28;
    }
    if (c2c <= start) c2c = c28;
    
    ToneLutFillParam p1 = {
        code_end, adj, u0, w->shadow_comp_sat_factor, c28, c2c, w->p340, 0.0, 0.0
    };
    tone_lut_fill_93960(tone_lut, start, w->code_max, &p1);
    w->p18_hi = p1.p18;
    w->p38_hi = p1.p38;
    
    // Fill #2
    code_end = w->code_330;
    adj = shasta_ftol2(w->adj_370);
    u0 = (w->adj_370 >= 0.0) ? w->shadow_exp_blend : w->shadow_transition_ratio;
    c28 = w->code_32c;
    c2c = w->code_2f4;
    
    if (code_end >= start) {
        code_end = start - 1;
        adj = 0;
    }
    if (c28 >= code_end) {
        c28 = code_end - 1;
        c2c = c28;
    }
    if (c2c >= start) c2c = c28;
    
    ToneLutFillParam p2 = {
        code_end, adj, u0, w->shadow_exp_sat_factor, c28, c2c, w->highlight_delta_gain, 0.0, 0.0
    };
    tone_lut_fill_93960(tone_lut, start, 0, &p2);
    w->p18_lo = p2.p18;
    w->p38_lo = p2.p38;
    
    black_noise_fill_93d50(black_noise, tone_lut, w, arg);
    
    int lo = w->code_min;
    int hi = w->code_max;
    if (hi >= 0) {
        for (int i = 0; i <= hi; i++) {
            if (i > 4095) break;
            int v = (int)tone_lut[i] + arg - (int)black_noise[i];
            if (v < lo) v = lo;
            else if (v > hi) v = hi;
            tone_lut[i] = (int32_t)v;
        }
    }
}


/* 20. shasta_build_tone_lut */
void shasta_build_tone_lut(const int32_t *rpd_sba, int num_pixels, const ShastaDpi *dpi, const int16_t ss_out[3], int32_t tone_lut[4096]) {
    int ext_shadow, shadow, highlight, ext_highlight;
    shasta_build_percentile_codes(rpd_sba, num_pixels, dpi, &ext_shadow, &shadow, &highlight, &ext_highlight);
    
    int dmin = shadow;
    
    int shifts[3];
    shifts[0] = (int)(short)ss_out[0];
    shifts[1] = (int)(short)ss_out[1];
    shifts[2] = (int)(short)ss_out[2];
    
    int remapped_dmin[3];
    int remapped_dens[3];
    
    for (int i = 0; i < 3; i++) {
        int di = shasta_ftol2(dpi->black_noise_sigma_mult * (double)dmin);
        int v_dmin = dmin + shifts[i];
        if (v_dmin < 0) v_dmin = 0;
        if (v_dmin > 4095) v_dmin = 4095;
        remapped_dmin[i] = v_dmin;
        
        int v_dens = (int)(short)((short)dmin + (short)di) + shifts[i];
        if (v_dens < 0) v_dens = 0;
        if (v_dens > 4095) v_dens = 4095;
        remapped_dens[i] = v_dens;
    }
    
    int thr = (int)round(dpi->metric_gray);
    int b = (int)round(dpi->black);
    int exceed = 0;
    for (int i = 0; i < 3; i++) {
        if (remapped_dmin[i] > thr) exceed = 1;
    }
    if (exceed) {
        for (int i = 0; i < 3; i++) {
            int di = shasta_ftol2(dpi->black_noise_sigma_mult * (double)dmin);
            
            int v_dmin = b + shifts[i];
            if (v_dmin < 0) v_dmin = 0;
            if (v_dmin > 4095) v_dmin = 4095;
            remapped_dmin[i] = v_dmin;
            
            int v_dens = b + di + shifts[i];
            if (v_dens < 0) v_dens = 0;
            if (v_dens > 4095) v_dens = 4095;
            remapped_dens[i] = v_dens;
        }
    }
    
    int mid_lo = shasta_avg2largest(remapped_dmin[0], remapped_dmin[1], remapped_dmin[2]);
    int mid_hi = shasta_avg2largest(remapped_dens[0], remapped_dens[1], remapped_dens[2]);
    
    ShastaWork work;
    memset(&work, 0, sizeof(ShastaWork));
    
    work.code_start = (int)round(dpi->metric_gray);
    work.code_min = (int)round(dpi->min_value);
    work.code_max = (int)round(dpi->white);
    work.code_48 = (int)round(dpi->white);
    work.code_values_per_button = dpi->code_values_per_button;
    work.mid_lo = mid_lo;
    work.mid_hi = mid_hi;
    work.code_white = (int)round(dpi->white);
    
    work.shadow_exp_blend = dpi->shadow_exp_blend;
    work.highlight_exp_blend = dpi->highlight_exp_blend;
    work.shadow_transition_ratio = dpi->shadow_transition_ratio;
    work.highlight_transition_ratio = dpi->highlight_transition_ratio;
    work.shadow_exp_sat_factor = dpi->shadow_exp_sat_factor;
    work.shadow_comp_sat_factor = dpi->shadow_comp_sat_factor;
    work.highlight_delta_gain = dpi->highlight_delta_gain;
    work.black_noise_std_dev = dpi->black_noise_std_dev;
    work.min_black_offset = dpi->min_black_offset;
    work.max_white_offset = dpi->max_white_offset;
    work.highlight_exp_scale = dpi->highlight_exp_scale;
    work.shadow_max_exp_slope = dpi->shadow_max_exp_slope;
    work.highlight_max_exp_slope = dpi->highlight_max_exp_slope;
    work.shadow_comp_blend = dpi->shadow_comp_blend;
    work.max_exp_delta = dpi->max_exp_delta;
    work.max_comp_delta = dpi->max_comp_delta;
    work.adj_clamp_lo_src = 0.33 * dpi->code_values_per_button;
    work.adj_clamp_hi_src = 0.8 * dpi->code_values_per_button;
    
    work.code_2f4 = ext_shadow;
    work.code_2f8 = shadow;
    work.code_2fc = highlight;
    work.code_300 = ext_highlight;
    
    work.p340 = 1.0;
    work.adj_scale_370 = 1.0;
    work.adj_scale_378 = 1.0;
    
    apply_prep_7b1c0(&work, dpi);
    image_derived_fields_935d0(&work);
    scale_adjs_after_935d0(&work);
    
    int32_t black_noise[4096];
    for (int i = 0; i < 4096; i++) {
        tone_lut[i] = 0;
        black_noise[i] = 0;
    }
    
    tone_lut_builder_93ee0(tone_lut, black_noise, &work, dpi);
    
    for (int i = 0; i < 4096; i++) {
        tone_lut[i] = (int32_t)(int16_t)(tone_lut[i] & 0xFFFF);
    }
}

/* 21. shasta_apply_tone_lut - ImaShastaOp I16 @ PakonIMAu.dll @ 0x1014dcc0 */
void shasta_apply_tone_lut(int32_t *rpd, int num_pixels, const int32_t tone_lut[4096]) {
    for (int i = 0; i < num_pixels * 3; i++) {
        int32_t val = rpd[i];
        if (val < 0) val = 0;
        if (val > 4095) val = 4095;
        rpd[i] = (int32_t)(int16_t)(tone_lut[val] & 0xFFFF);
    }
}
