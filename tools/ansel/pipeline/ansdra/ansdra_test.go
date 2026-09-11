package ansdra

import (
	"os"
	"path/filepath"
	"testing"
)

// The real verification of this package is tools/test_dra_port.py. These tests
// pin the parser's documented quirks and the arithmetic primitives.

func vendorDir(t *testing.T) string {
	t.Helper()
	d := filepath.Join("..", "..", "..", "..", "vendor", "ansel",
		"anselinstalldir", "dataPathItems", "dra")
	if _, err := os.Stat(filepath.Join(d, DefaultDpiName)); err != nil {
		t.Skipf("vendor dra data not present: %v", err)
	}
	return d
}

func TestShippedParams(t *testing.T) {
	p, err := LoadParams(vendorDir(t), "")
	if err != nil {
		t.Fatal(err)
	}
	if bad := ValidateParams(p); bad != 0 {
		t.Fatalf("shipped .dpi fails validation at field %d", bad)
	}
	for _, c := range []struct {
		name string
		got  int64
		want int64
	}{
		{"maxValue", p.MaxValue, 4095},
		{"lowFixedPoint", p.LowFixedPoint, 1550},
		{"highFixedPoint", p.HighFixedPoint, 1550},
		{"paperMin", p.PaperMin, 1200},
		{"paperMax", p.PaperMax, 2000},
		{"binFactor", p.BinFactor, 4},
	} {
		if c.got != c.want {
			t.Errorf("%s = %d, want %d", c.name, c.got, c.want)
		}
	}
	if !p.BDoAverage {
		t.Error("bDoAverage should be true — the weighted-blend branch is live")
	}
	if p.LumWeighting+p.EdgeWeighting != 1.0 {
		t.Errorf("weights sum to %v, want exactly 1.0 (validator field 10)",
			p.LumWeighting+p.EdgeWeighting)
	}
	lo, hi, err := p.CurvePair(LightingNormal)
	if err != nil {
		t.Fatal(err)
	}
	// The .ttc slope array is DERIVED by the parser's leaf 0x10227c60, not read
	// from the file. A port that only parsed x/y leaves it empty.
	if len(lo.Slope) != len(lo.X)-1 || len(hi.Slope) != len(hi.X)-1 {
		t.Fatalf("slopes not built: low %d/%d, high %d/%d", len(lo.Slope),
			len(lo.X), len(hi.Slope), len(hi.X))
	}
}

func TestSscanfKVRejectsUnspacedEquals(t *testing.T) {
	// The literal '=' in "%s = %s" has to match a REAL '=' in the input, and
	// the two %s are whitespace-delimited — so "key=value" is rejected
	// outright. A naive split accepts it; the real DLL does not.
	if _, _, ok := SscanfKV("maxValue=4095"); ok {
		t.Error(`"maxValue=4095" should be REJECTED (sscanf returns 1)`)
	}
	k, v, ok := SscanfKV("  maxValue = 4095  ")
	if !ok || k != "maxValue" || v != "4095" {
		t.Errorf("SscanfKV spaced form gave (%q,%q,%v)", k, v, ok)
	}
}

func TestSscanfBoolIsFirstCharT(t *testing.T) {
	// NOT strcmp(value, "true"): sscanf("%c") then `cmp byte, 0x74`.
	for _, c := range []struct {
		in   string
		want bool
	}{{"true", true}, {"t", true}, {"tomato", true},
		{"True", false}, {"TRUE", false}, {"false", false}} {
		got, ok := sscanfBool(c.in)
		if !ok || got != c.want {
			t.Errorf("sscanfBool(%q) = %v, want %v", c.in, got, c.want)
		}
	}
}

func TestSscanfIntIgnoresTrailingJunk(t *testing.T) {
	if v, ok := sscanfInt("4095abc", 16); !ok || v != 4095 {
		t.Errorf(`sscanfInt("4095abc") = %d,%v`, v, ok)
	}
	if _, ok := sscanfInt("abc", 16); ok {
		t.Error("a token with no digits should fail, leaving the field unwritten")
	}
}

func TestLightingDispatchFallsThroughToNormal(t *testing.T) {
	// `cmp dx,1` / `cmp dx,2` and EVERYTHING else — including the 0 a
	// find("lighting") miss produces — takes the Normal pair.
	for _, v := range []int64{0, 3, -1, 99} {
		lo, hi := LightingCurveKeys(v)
		if lo != KeyLowNormalTTC || hi != KeyHighNormalTTC {
			t.Errorf("lighting %d -> (%s,%s), want the Normal pair", v, lo, hi)
		}
	}
}

func TestFtolRoundTruncatesAfterBias(t *testing.T) {
	for _, c := range []struct {
		in   float64
		want int64
	}{{2.5, 3}, {-2.5, -2}, {-2.6, -2}, {0.49, 0}} {
		if got := ftolRound(c.in); got != c.want {
			t.Errorf("ftolRound(%v) = %d, want %d", c.in, got, c.want)
		}
	}
}

func TestRebinShortCircuitsBinFactorOne(t *testing.T) {
	small := []int64{1, 2, 3, 4, 5, 6}
	if got := Rebin(small, 6, 1); len(got) != 6 || got[3] != 4 {
		t.Errorf("Rebin(bf=1) = %v, want a copy", got)
	}
	if got := Rebin(small, 6, 3); len(got) != 2 || got[0] != 6 || got[1] != 15 {
		t.Errorf("Rebin(bf=3) = %v, want [6 15]", got)
	}
}
