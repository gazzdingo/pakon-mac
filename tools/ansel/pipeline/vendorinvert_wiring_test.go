package main

import (
	"math"
	"os"
	"testing"

	"pakonpipeline/vendorinvert"
)

// TestVendorInvertIndexesTheFullCode is the regression guard that matters most
// on this path.
//
// docs/74 §173.1 / §174: an earlier version of the PYTHON vendor path shifted
// the index (`code >> 2`), inferred from a dump having 4096 entries — "so the
// index must be 12-bit". That was wrong. The vendor's loop indexes with the
// full 16-bit value, `lut_src`'s real range is 404..11681, and the 4096 was
// the DUMP's size rather than the table's. The shift made it impossible for
// the index to exceed 4095 however large the table, which is what made §172's
// clipping caveat look intrinsic when it was an artefact of that one line.
//
// So: assert we index with the full code, by checking values where the two
// readings visibly disagree.
func TestVendorInvertIndexesTheFullCode(t *testing.T) {
	for _, code := range []int{404, 1000, 4095, 4096, 8000, 11681, 16383} {
		got := vendorInvertRaw(code)
		want := int(vendorinvert.Table[code])
		if got != want {
			t.Errorf("vendorInvertRaw(%d) = %d, want Table[%d] = %d",
				code, got, code, want)
		}
		shifted := int(vendorinvert.Table[code>>2])
		if code >= 4 && got == shifted && want != shifted {
			t.Errorf("vendorInvertRaw(%d) matches the >>2 reading (%d) — "+
				"the §174 index bug is back", code, shifted)
		}
	}
	// The distinguishing property: with >>2 the index could never exceed
	// 4095, so every code above 16380 would collapse onto the same few
	// entries. Assert the full-index reading actually reaches the top.
	if vendorInvertRaw(16383) != int(vendorinvert.Table[16383]) {
		t.Error("the top of the table is unreachable — index is being shifted")
	}
}

// TestVendorInvertClamps pins out-of-range behaviour. The raw CCD code can
// exceed the table on a saturated line; clamping is what the Python path's
// np.clip does, and silently wrapping or panicking here would be a crash or a
// wrong pixel on exactly the frames that are hardest to notice.
func TestVendorInvertClamps(t *testing.T) {
	if got, want := vendorInvertRaw(-1), int(vendorinvert.Table[0]); got != want {
		t.Errorf("vendorInvertRaw(-1) = %d, want %d (clamp low)", got, want)
	}
	if got, want := vendorInvertRaw(-100000), int(vendorinvert.Table[0]); got != want {
		t.Errorf("vendorInvertRaw(-100000) = %d, want %d", got, want)
	}
	top := int(vendorinvert.Table[vendorinvert.Entries-1])
	if got := vendorInvertRaw(vendorinvert.Entries); got != top {
		t.Errorf("vendorInvertRaw(Entries) = %d, want %d (clamp high)", got, top)
	}
	if got := vendorInvertRaw(1 << 20); got != top {
		t.Errorf("vendorInvertRaw(2^20) = %d, want %d", got, top)
	}
}

// TestVendorInvertIsMonotone — inverting a log curve must never rise.
func TestVendorInvertIsMonotone(t *testing.T) {
	prev := vendorInvertRaw(0)
	for i := 1; i < vendorinvert.Entries; i++ {
		v := vendorInvertRaw(i)
		if v > prev {
			t.Fatalf("vendorInvertRaw rises at %d: %d -> %d", i, prev, v)
		}
		prev = v
	}
}

// TestVendorInvertDefaultsOff — this re-architects the front of the chain and
// rests on one roll and one capture (docs/74 §170.4). A stray edit making it
// default-on would silently change every F-135 render.
func TestVendorInvertDefaultsOff(t *testing.T) {
	if os.Getenv("PAKON_VENDOR_INVERT") == "1" {
		t.Skip("PAKON_VENDOR_INVERT=1 is set in this environment")
	}
	if vendorInvertEnabled {
		t.Fatal("vendorInvertEnabled is true without PAKON_VENDOR_INVERT=1 — " +
			"this must stay opt-in")
	}
}

// TestInversionModeIsExclusive is the guard against a DOUBLE INVERSION.
//
// A mutation test proved this was needed: with pass 1 and pass 2 reading two
// independent conditions, deleting pass 2's `!vendorInvertEnabled` was NOT
// CAUGHT by any test here — and a doubly-inverted frame is a plausible picture
// that raises nothing. Both passes now read inversionMode(), so exactly one
// can fire; this pins that property.
func TestInversionModeIsExclusive(t *testing.T) {
	for _, model := range []string{"f135", "f235", "f335", ""} {
		for _, vi := range []bool{false, true} {
			m := inversionMode(model, vi)
			vendor := m == "vendor"
			legacy := m == "legacy"
			if vendor && legacy {
				t.Fatalf("model=%q vendorInvert=%v: both passes would run",
					model, vi)
			}
			if model == "f135" && !vendor && !legacy {
				t.Errorf("model=f135 vendorInvert=%v: NEITHER pass would run "+
					"— the frame would never be inverted", vi)
			}
			if model != "f135" && m != "none" {
				t.Errorf("model=%q gave %q, want none", model, m)
			}
		}
	}
	if got := inversionMode("f135", true); got != "vendor" {
		t.Errorf("f135 + flag = %q, want vendor", got)
	}
	if got := inversionMode("f135", false); got != "legacy" {
		t.Errorf("f135 no flag = %q, want legacy", got)
	}
}

// TestApplyVendorInvertRGBKeepsChannelsDistinct catches a transposition —
// inverting G with R's value, say. Also proven necessary by mutation: it was
// NOT CAUGHT before this function existed, because nothing tested the wiring's
// per-channel mapping, only the scalar helper.
//
// The three inputs are chosen to have three DIFFERENT table values, so any
// permutation shows up. A test using equal or table-tail values would be inert
// — the failure docs/74 §193.4 records.
func TestApplyVendorInvertRGBKeepsChannelsDistinct(t *testing.T) {
	const cr, cg, cb = 500, 2500, 9000
	wr := int(vendorinvert.Table[cr])
	wg := int(vendorinvert.Table[cg])
	wb := int(vendorinvert.Table[cb])
	if wr == wg || wg == wb || wr == wb {
		t.Fatalf("test inputs are not discriminating: %d %d %d", wr, wg, wb)
	}
	gr, gg, gb := applyVendorInvertRGB(cr, cg, cb)
	if gr != wr || gg != wg || gb != wb {
		t.Fatalf("applyVendorInvertRGB(%d,%d,%d) = (%d,%d,%d), want (%d,%d,%d)",
			cr, cg, cb, gr, gg, gb, wr, wg, wb)
	}
}

// TestLegacyInversionRunsOnlyInLegacyMode is the DOUBLE-INVERSION guard, and
// it exists because a mutation proved the earlier arrangement untestable: with
// the mode check at the call site in processImage, letting pass 2 run
// alongside the vendor inversion was NOT CAUGHT by anything. A doubly-inverted
// frame is a plausible picture that raises no error.
func TestLegacyInversionRunsOnlyInLegacyMode(t *testing.T) {
	fpo := [3]int{100, 100, 100}
	baseLog := [3]float64{3.0, 3.0, 3.0}
	c9 := [3]float64{0, 0, 0}
	logTerm := func(v, c float64) float64 {
		d := v - c
		if d < 1 {
			d = 1
		}
		return math.Log10(d)
	}
	clamp := func(v int) int {
		if v < 0 {
			return 0
		}
		if v > 4095 {
			return 4095
		}
		return v
	}
	frame := func() [][][3]float64 {
		return [][][3]float64{{{500, 1200, 2400}, {800, 60, 4000}}}
	}

	// "vendor": pass 1 already inverted, so this must be a no-op.
	f := frame()
	before := [][3]float64{f[0][0], f[0][1]}
	applyLegacyInversion("vendor", f, fpo, baseLog, c9, logTerm, clamp)
	if f[0][0] != before[0] || f[0][1] != before[1] {
		t.Fatalf("legacy inversion ran in vendor mode — the frame is inverted "+
			"TWICE: %v %v -> %v %v", before[0], before[1], f[0][0], f[0][1])
	}

	// "none": also a no-op.
	f = frame()
	applyLegacyInversion("none", f, fpo, baseLog, c9, logTerm, clamp)
	if f[0][0] != before[0] || f[0][1] != before[1] {
		t.Fatalf("legacy inversion ran in none mode")
	}

	// "legacy": it must actually do something, or the guard above would pass
	// for the trivial reason that the function never works.
	f = frame()
	applyLegacyInversion("legacy", f, fpo, baseLog, c9, logTerm, clamp)
	if f[0][0] == before[0] && f[0][1] == before[1] {
		t.Fatal("legacy inversion did nothing in legacy mode — the no-op " +
			"assertions above prove nothing")
	}
}

// TestVendorInvertMatchesTheGeneratedTable checks every entry, so a
// regenerate-from-a-different-source cannot slip through the wiring.
func TestVendorInvertMatchesTheGeneratedTable(t *testing.T) {
	for i := 0; i < vendorinvert.Entries; i++ {
		if got, want := vendorInvertRaw(i), int(vendorinvert.Table[i]); got != want {
			t.Fatalf("vendorInvertRaw(%d) = %d, want %d", i, got, want)
		}
	}
}
