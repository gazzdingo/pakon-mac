/* Digital ICE tables, computed at first use from the formulas of RE 44 sec. 2.2 and 2.4. No Kodak bytes are stored here.
 * Kodak's Begin builds the same tables with the x87; in IEEE double (log10 / pow) they come out bit for bit equal to the dump of the
 * Wine oracle (RE 44 sec. 2.2, OBSERVED). Whether a given libm reproduces that is checked, when the private vector is present, by
 * core_ice_kodak (it hashes the tables and compares every vector). pki_log is followed by the zero gap, so an IR word above 16383
 * reads 0 (docs/re/45 U2). */
#include "ice/ice_internal.h"
#include <math.h>
#include <pthread.h>

float pki_log[65536];
int64_t pki_ahi[256], pki_alo[256];
double pki_thr_high_slope, pki_thr_low_slope;

static pthread_once_t once = PTHREAD_ONCE_INIT;

static double f32(double x) { return (double)(float)x; }

/* RE 44 sec. 2.4: thr = f32((log10(f32(c) + 1) / log10(16384)) * 16383) */
static double thr_for(double c) { return f32((log10(f32(c) + 1.0) / log10(16384.0)) * 16383.0); }

static void build(void) {
    const double s = f32(16383.0 / log10(16384.0));
    for (int v = 0; v < 16384; v++) pki_log[v] = (float)(log10((double)(v + 1)) * s);
    for (int h = 0; h < 256; h++) pki_ahi[h] = h < 64 ? (int64_t)(pow(10.0, (double)(h * 256) / s) * 16.0 + 0.5) : 0;
    for (int l = 0; l < 256; l++) pki_alo[l] = (int64_t)(pow(10.0, (double)l / s) * 65536.0 + 0.5);
    pki_thr_high_slope = thr_for(0.1646);
    pki_thr_low_slope = thr_for(0.02);
}

void pki_tables_init(void) { pthread_once(&once, build); }
