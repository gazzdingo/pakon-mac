package anscontrast

import (
	"os"
	"path/filepath"
	"testing"
)

// The real verification of this package is tools/test_contrast_port.py. These
// tests pin the vendor's own .dpi-parser typo (which a well-meaning cleanup
// would "fix", silently diverging from the real scanner) and the pieces of
// build_ramp / slope_band whose shape is a transcribed fact.

func vendorDir(t *testing.T) string {
	t.Helper()
	d := filepath.Join("..", "..", "..", "..", "vendor", "ansel",
		"anselinstalldir", "dataPathItems", "contrast")
	if _, err := os.Stat(filepath.Join(d, DefaultDpiName)); err != nil {
		t.Skipf("vendor contrast data not present: %v", err)
	}
	return d
}

func TestShippedParams(t *testing.T) {
	p, err := LoadParams(vendorDir(t), "")
	if err != nil {
		t.Fatal(err)
	}
	if msg := ValidateParams(p); msg != "" {
		t.Fatalf("shipped .dpi fails 0x101d3860: %s", msg)
	}
	if p.UserInputMode != ModeCombineWithSlope {
		t.Errorf("userInputMode = %d, want COMBINE_WITH_SLOPE", p.UserInputMode)
	}
	if !p.BConstrainSlope {
		t.Error("bConstrainSlope should be true in contrast-CNEnhanced.dpi")
	}
	if p.LutSize != 4096 || p.MaxValue != 4095 {
		t.Errorf("lutSize/maxValue = %d/%d", p.LutSize, p.MaxValue)
	}
	if p.MidpointIn != 1550 || p.MidpointOut != 1550 {
		t.Errorf("midpoint = %d/%d, want 1550/1550", p.MidpointIn, p.MidpointOut)
	}
	if len(p.Points) != 2 {
		t.Errorf("points = %v, want the two the .dpi lists", p.Points)
	}
	// aUpperMinSlope's shipped row, and the ctor padding past band 7.
	if p.AUpperMinSlope[1] != f32(0.45) {
		t.Errorf("aUpperMinSlope[1] = %v, want 0.45f", p.AUpperMinSlope[1])
	}
	if p.AUpperMinSlope[NSlopeBands] != 0.0 ||
		p.AUpperMaxSlope[NSlopeBands] != 100.0 {
		t.Errorf("ctor padding wrong: min %v, max %v",
			p.AUpperMinSlope[NSlopeBands], p.AUpperMaxSlope[NSlopeBands])
	}
}

func TestCsUpperIndexIsUnsettable(t *testing.T) {
	// THE VENDOR'S OWN TYPO. csUpperIndex's parse key is "csumpperixedindex";
	// a .dpi spelling it correctly falls through every key and is rejected, so
	// the field keeps its ctor default of 3999 forever. Do not "fix" this.
	dir := vendorDir(t)
	raw, err := os.ReadFile(filepath.Join(dir, DefaultDpiName))
	if err != nil {
		t.Fatal(err)
	}
	correct, err := ParseDpi(string(raw)+"\ncsUpperIndex = 2000\n", nil)
	if err != nil {
		t.Fatal(err)
	}
	if correct.CsUpperIndex != 3999 {
		t.Errorf("a correctly spelled csUpperIndex was accepted (%d); the real "+
			"scanner rejects it", correct.CsUpperIndex)
	}
	typo, err := ParseDpi(string(raw)+"\n"+DpiKeyCsUpperIndex+" = 2000\n", nil)
	if err != nil {
		t.Fatal(err)
	}
	if typo.CsUpperIndex != 2000 {
		t.Errorf("the vendor's misspelled key was NOT honoured (%d)",
			typo.CsUpperIndex)
	}
}

func TestSlopeBandDispatch(t *testing.T) {
	// 0x101d33f4's jump table: only slots 1 and 2 rewrite eax; 3..6 select
	// themselves. Outside [1,6] the default picks band 1 iff x == 2.
	for _, c := range []struct {
		scene, x int64
		want     int
	}{
		{1, 0, 0}, {2, 0, 2}, {3, 0, 3}, {6, 0, 6},
		{0, 2, 1}, {0, 1, 0}, {7, 2, 1}, {-1, 0, 0},
	} {
		if got := SlopeBand(c.scene, c.x); got != c.want {
			t.Errorf("SlopeBand(%d,%d) = %d, want %d", c.scene, c.x, got, c.want)
		}
	}
}

func TestBuildRampZeroSlopeFillsFlat(t *testing.T) {
	// 0x101d2bba: a zero slope fills the whole span with midOut, with no
	// rounding at all.
	buf := make([]int64, 16)
	BuildRamp(buf, 4095, 8, 100, 15, 0.0)
	for i := 8; i <= 15; i++ {
		if buf[i] != 100 {
			t.Fatalf("buf[%d] = %d, want 100", i, buf[i])
		}
	}
}

func TestBuildRampUnitSlopeIsIdentity(t *testing.T) {
	// The descending seed is (endIndex - midIn - 1)*slope + midOut, not
	// midOut - slope; with slope 1 and midpoint (n, n) that reproduces the
	// identity all the way down to 0.
	buf := make([]int64, 32)
	BuildRamp(buf, 4095, 16, 16, 0, 1.0)
	for i := 0; i <= 16; i++ {
		if buf[i] != int64(i) {
			t.Fatalf("descending ramp buf[%d] = %d, want %d", i, buf[i], i)
		}
	}
	BuildRamp(buf, 4095, 16, 16, 31, 1.0)
	for i := 16; i <= 31; i++ {
		if buf[i] != int64(i) {
			t.Fatalf("ascending ramp buf[%d] = %d, want %d", i, buf[i], i)
		}
	}
}

func TestBuildSegmentFlatIsAStore(t *testing.T) {
	// 0x101d2cb2: a flat segment is a rep stos with no float arithmetic.
	buf := make([]int64, 16)
	BuildSegment(buf, 4095, 2, 77, 10, 77)
	for i := 2; i <= 10; i++ {
		if buf[i] != 77 {
			t.Fatalf("buf[%d] = %d, want 77", i, buf[i])
		}
	}
}

func TestFtol16NarrowsToAx(t *testing.T) {
	// Every call site consumes only ax. NaN and out-of-int64 give the
	// indefinite, whose low word 0x104ffe63 leaves as 0 — not 0x8000.
	if got := ftol16(70000); got != 70000-65536 {
		t.Errorf("ftol16(70000) = %d, want %d", got, 70000-65536)
	}
	if got := ftol16(2.5); got != 2 {
		t.Errorf("ftol16(2.5) = %d, want 2 (truncation, the +0.5 is the "+
			"caller's)", got)
	}
}

func TestSetParamsRollsBackOnFailure(t *testing.T) {
	// 0x101d7ff5: a failing validate assigns the params straight back from the
	// backup, so a bad .dpi silently reverts rather than erroring the analysis.
	im := NewImpl()
	good := im.Params
	bad := DefaultParams()
	bad.MidpointIn = -1
	if msg := im.SetParams(bad); msg == "" {
		t.Fatal("a negative midpoint should fail validation")
	}
	if im.Params.MidpointIn != good.MidpointIn {
		t.Errorf("params were not rolled back: midpointIn = %d",
			im.Params.MidpointIn)
	}
}
