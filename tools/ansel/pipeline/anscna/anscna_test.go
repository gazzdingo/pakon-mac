package anscna

import (
	"math"
	"testing"
)

// The real verification of this package is tools/test_cna_port.py, which
// streams a real frame through both this port and pakon_cna.py and diffs every
// stage. These tests pin the arithmetic primitives instead — the pieces whose
// behaviour is a transcribed fact with a cited VA, and which a refactor could
// quietly "simplify" into something that still compiles.

func TestI16Wraps(t *testing.T) {
	// 0x1022c374's laplacian computes in 16-bit registers, so `centre*4` wraps.
	for _, c := range []struct{ in, want int64 }{
		{0x7FFF, 0x7FFF}, {0x8000, -0x8000}, {0xFFFF, -1},
		{0x10000, 0}, {-1, -1}, {40000, 40000 - 65536},
	} {
		if got := i16(c.in); got != c.want {
			t.Errorf("i16(%d) = %d, want %d", c.in, got, c.want)
		}
	}
}

func TestIdivTruncatesTowardZero(t *testing.T) {
	// x86 idiv, not Python/Go floor division. -7/3 is -2, not -3.
	for _, c := range []struct{ a, b, want int64 }{
		{7, 3, 2}, {-7, 3, -2}, {7, -3, -2}, {-7, -3, 2}, {5000, 2, 2500},
	} {
		if got := idiv(c.a, c.b); got != c.want {
			t.Errorf("idiv(%d,%d) = %d, want %d", c.a, c.b, got, c.want)
		}
	}
}

func TestFtol2I32OnNaNIsZero(t *testing.T) {
	// 0x1022ce98 stores only EAX of _ftol2's edx:eax, and the masked-invalid
	// "integer indefinite" 0x8000000000000000 has LOW 32 bits ZERO. A real
	// scanned roll's dark-half histogram reaches this (see DoHistResample).
	if got := ftol2I32(math.NaN()); got != 0 {
		t.Errorf("ftol2I32(NaN) = %d, want 0", got)
	}
	if got := ftol2I32(math.Inf(1)); got != 0 {
		t.Errorf("ftol2I32(+Inf) = %d, want 0", got)
	}
	// ftol2 itself still reports the full 64-bit indefinite.
	if got := ftol2(math.NaN()); got != math.MinInt64 {
		t.Errorf("ftol2(NaN) = %d, want MinInt64", got)
	}
}

func TestRoundHalfUpIsTruncNotRound(t *testing.T) {
	// trunc(x + 0.5): half away from zero for positives, TOWARD zero for
	// negatives. round() would give -3 for -2.5.
	for _, c := range []struct {
		in   float64
		want int64
	}{{2.5, 3}, {2.4, 2}, {-2.5, -2}, {-2.6, -2}, {-2.51, -2}, {0.5, 1}} {
		if got := roundHalfUp(c.in); got != c.want {
			t.Errorf("roundHalfUp(%v) = %d, want %d", c.in, got, c.want)
		}
	}
}

func TestX87DivDoesNotTrap(t *testing.T) {
	// Python's / raises; the DLL masks the exception and produces a signed
	// infinity, or the real indefinite for 0/0.
	if got := x87Div(1.0, 0.0); !math.IsInf(got, 1) {
		t.Errorf("x87Div(1,0) = %v, want +Inf", got)
	}
	if got := x87Div(-1.0, 0.0); !math.IsInf(got, -1) {
		t.Errorf("x87Div(-1,0) = %v, want -Inf", got)
	}
	if got := x87Div(0.0, 0.0); !math.IsNaN(got) {
		t.Errorf("x87Div(0,0) = %v, want NaN", got)
	}
}

func TestDefaultParamsValidate(t *testing.T) {
	// 0x100f8030's ctor defaults are ansel-cna-default-default.dpi's values,
	// and every one of 0x1022ceb0's 22 checks passes on them.
	if bad := ValidateParams(DefaultParams()); bad >= 0 {
		t.Fatalf("ValidateParams(defaults) = field %d, want valid", bad)
	}
	p := DefaultParams()
	p.ThresholdReductionFactor = 1.0 // 0x1022cfad rejects >= 1.0, not > 1.0
	if bad := ValidateParams(p); bad != 0xD {
		t.Errorf("thresholdReductionFactor 1.0 -> field %d, want 0xD", bad)
	}
}

func TestBufferSizes(t *testing.T) {
	p := DefaultParams()
	s := BufferSizes(p, 1000*1500)
	if s["lum_hist_i32"] != 5000 || s["bucket_hist_i32"] != 500 {
		t.Errorf("histogram sizes wrong: %v", s)
	}
	// hw1 = trunc(maxGaussSigma * smoothingSizeFactor + 0.5) = 50*4 = 200.
	if s["_hw1"] != 200 {
		t.Errorf("hw1 = %d, want 200", s["_hw1"])
	}
}

func TestGaussKernelIsSymmetricAndFloat32(t *testing.T) {
	k := GaussKernel(2.0, 4.0)
	if len(k) != 2*8+1 {
		t.Fatalf("kernel has %d taps, want 17", len(k))
	}
	for i := range k {
		if k[i] != k[len(k)-1-i] {
			t.Errorf("tap %d is not mirrored: %v vs %v", i, k[i], k[len(k)-1-i])
		}
		if k[i] != f32(k[i]) {
			t.Errorf("tap %d is not float32-exact: %v", i, k[i])
		}
	}
}

func TestParamsFromBytesRoundTrip(t *testing.T) {
	// A 0x7c-byte image with only histSize set: everything else decodes to 0,
	// which is what an unwritten field would be. The point is the OFFSETS.
	buf := make([]byte, ParamsSize)
	buf[0x08] = 0x88
	buf[0x09] = 0x13 // 5000
	p, err := ParamsFromBytes(buf)
	if err != nil {
		t.Fatal(err)
	}
	if p.HistSize != 5000 {
		t.Errorf("histSize = %d, want 5000", p.HistSize)
	}
	if _, err := ParamsFromBytes(buf[:10]); err == nil {
		t.Error("a short buffer should be refused, not padded")
	}
}
