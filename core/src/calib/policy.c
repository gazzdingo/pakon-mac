/* The automatic calibration policy (Task 15). Origin: TLB FN_bCalibrateFindCorrections FUN_10021590 (the 20 h full-search test, FUN_10010250) and FN_bBeforeScan
 * FUN_1002dbd0 (no tables / DarkPointCorrectIntervalMinutes), docs/re/43-calibration-sequence.md sec 1 and 6; the defaults are S-R39 a. v1 had no policy
 * (it calibrated once). Pure: no I/O, no clock. */
#include "calib/calib.h"

void pk_cal_policy_default(pk_cal_policy *out) {
    if (!out) return;
    out->dark_point_interval_min = 120;   /* the owner's PSI value (TLB's own default is 60, FUN_10011fd0); S-R39 a */
    out->full_search_after_h = 20;        /* 72000 s */
    out->auto_at_power_on = true;
}

pk_cal_due pk_calibration_due(const pk_cal_policy *p, const pk_cal_state *st, int64_t now_s) {
    pk_cal_due d = { false, false, "" };
    if (!p || !st) return d;
    /* the 20 h rule: TLB zeroes FullLightCorrections on a serial change, which makes "now - 0 > 72000" true at the next calibration */
    const bool never_full = st->last_full_s <= 0;
    const bool full_late = never_full || now_s - st->last_full_s > (int64_t)p->full_search_after_h * 3600;
    if (st->serial_changed) { d.due = d.full_search = true; d.reason = "the scanner serial changed"; return d; }
    if (st->last_run_s <= 0) {
        /* RAM-only tables: after TLB loads, the first scan always calibrates. Without auto_at_power_on only a missing full search is due (nothing to scan with). */
        if (p->auto_at_power_on) { d.due = true; d.full_search = full_late; d.reason = full_late ? "power-on, full light search" : "power-on"; return d; }
        if (never_full) { d.due = d.full_search = true; d.reason = "no light settings yet"; return d; }
        return d;
    }
    if (full_late) { d.due = d.full_search = true; d.reason = "full light search interval"; return d; }
    if (now_s - st->last_run_s > (int64_t)p->dark_point_interval_min * 60) { d.due = true; d.reason = "dark-point interval"; return d; }
    return d;
}
