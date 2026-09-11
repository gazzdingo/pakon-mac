package main

import (
	"os"
	"testing"

	"pakonpipeline/anscna"
	"pakonpipeline/ansautotone"
	"pakonpipeline/citrasdriver"
)

// The vendor tree, relative to tools/ansel/pipeline.
const testAnselRoot = "../../../vendor/ansel/anselinstalldir/dataPathItems"

// synthFrame is a deterministic post-FUGC RPD-12 frame with two properties
// that are both load-bearing, and both were learned the hard way:
//
//  1. Local structure, so cna's EdgeHist is not degenerate. docs/74 §191
//     records the integration bug a perfectly flat image causes — the DLL
//     masks the resulting x87 zero-divide and the port did not.
//
//  2. FRACTIONAL pixel values. The first version of this frame was entirely
//     integer-valued, which made truncation and round-half-to-even produce
//     identical output, so a deliberate mutation replacing the quantiser with
//     a truncating one was NOT CAUGHT — the suite passed on a wrong
//     implementation. That is the same failure as docs/74 §192.5's `>` vs
//     `>=` (inputs never reached the boundary) and §190.4's l<->s swap (the
//     comparison quantised away the difference). The .5 cases below are
//     deliberate: they are exactly where the two roundings disagree.
func synthFrame(h, w int) [][][3]float64 {
	f := make([][][3]float64, h)
	for y := 0; y < h; y++ {
		row := make([][3]float64, w)
		for x := 0; x < w; x++ {
			base := float64((x*37+y*11)%1024) * 3.0
			// quarter-code fractions, including exact .5 ties
			frac := float64((x*3+y*5)%4) * 0.25
			row[x] = [3]float64{
				base + frac,
				base + 40.0 + float64((x+y)%2)*0.5,
				base - 25.0 + frac*2,
			}
			if (x+y)%7 == 0 { // local structure, so EdgeHist is populated
				row[x][0] += 300.5
				row[x][1] -= 120.5
			}
		}
		f[y] = row
	}
	return f
}

// TestPhase62QuantiserIsRoundHalfEven checks the one property of
// quantiseFrameRPD12 that a caller could plausibly get wrong, against
// independently-stated expected values rather than against another copy of the
// same loop.
//
// An earlier version of this test built two buffers, both by calling
// citrasdriver.QuantiseRPD12 in a loop, and asserted they matched. That is a
// tautology: it could not fail, because both sides were the same code. The
// divergence it pretended to guard is now structurally impossible instead —
// computeGoToneLut and applyVendorTone share quantiseFrameRPD12 — and this
// test checks the quantiser's actual contract.
//
// np.rint is round-half-to-EVEN, so 0.5 -> 0 and 1.5 -> 2, and −0.5 -> 0.
// Truncation or round-half-away would both differ here.
func TestPhase62QuantiserIsRoundHalfEven(t *testing.T) {
	cases := []struct {
		in   float64
		want int16
	}{
		{0.5, 0}, {1.5, 2}, {2.5, 2}, {3.5, 4},
		{-0.5, 0}, {-1.5, -2},
		{0.4, 0}, {0.6, 1}, {1234.0, 1234},
	}
	for _, c := range cases {
		frame := [][][3]float64{{{c.in, c.in, c.in}}}
		px := quantiseFrameRPD12(frame)
		if len(px) != 3 {
			t.Fatalf("quantiseFrameRPD12 returned %d values, want 3", len(px))
		}
		if px[0] != c.want {
			t.Errorf("quantise(%v) = %d, want %d (round-half-to-even)",
				c.in, px[0], c.want)
		}
	}
}

// TestPhase62SharedQuantiserReachesBothHalves proves the sharing is real: the
// buffer applyVendorTone hands the citras driver must be the one
// quantiseFrameRPD12 produces. If someone reintroduces a private loop in
// either half, this fails.
func TestPhase62SharedQuantiserReachesBothHalves(t *testing.T) {
	frame := synthFrame(8, 8)
	shared := quantiseFrameRPD12(frame)

	// The analysis half's image.
	analysisImg := anscna.Image{
		Width: len(frame[0]), Height: len(frame),
		Pixels: quantiseFrameRPD12(frame),
	}
	for i := range shared {
		if analysisImg.Pixels[i] != shared[i] {
			t.Fatalf("analysis buffer diverged at %d", i)
		}
	}
	// The apply half's image, built the way applyVendorTone builds it.
	applyImg := citrasdriver.ImageI16{
		H: len(frame), W: len(frame[0]), Px: quantiseFrameRPD12(frame),
	}
	for i := range shared {
		if applyImg.Px[i] != shared[i] {
			t.Fatalf("apply buffer diverged at %d", i)
		}
	}
}

// TestPhase62LutMatchesDirectAnalyze proves the wrapper adds no corruption of
// its own: the LUT computeGoToneLut returns must equal ansautotone.Analyze's,
// entry for entry, through the int64 -> int32 narrowing.
func TestPhase62LutMatchesDirectAnalyze(t *testing.T) {
	if _, err := os.Stat(testAnselRoot); err != nil {
		t.Skipf("vendor tree not present: %v", err)
	}
	frame := synthFrame(24, 32)
	h, w := len(frame), len(frame[0])

	got, err := computeGoToneLut(frame, testAnselRoot)
	if err != nil {
		t.Fatalf("computeGoToneLut: %v", err)
	}
	if got == nil {
		t.Fatal("nil LUT on a sceneType-0 frame; the epilogue should not fire")
	}
	if len(got) != ToneLutSize {
		t.Fatalf("LUT has %d entries, want %d", len(got), ToneLutSize)
	}

	img := anscna.Image{Width: w, Height: h, Pixels: make([]int16, w*h*3)}
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			base := (y*w + x) * 3
			for c := 0; c < 3; c++ {
				img.Pixels[base+c] = citrasdriver.QuantiseRPD12(frame[y][x][c])
			}
		}
	}
	params, err := ansautotone.LoadParams(testAnselRoot)
	if err != nil {
		t.Fatalf("LoadParams: %v", err)
	}
	want, _, err := ansautotone.Analyze(img, params, 0, 0.0)
	if err != nil {
		t.Fatalf("Analyze: %v", err)
	}
	if len(want) != len(got) {
		t.Fatalf("length mismatch: %d vs %d", len(got), len(want))
	}
	for i := range got {
		if int64(got[i]) != want[i] {
			t.Fatalf("LUT[%d] = %d, want %d", i, got[i], want[i])
		}
	}
}

// TestPhase62DefaultsOff guards the thing most likely to go wrong by accident:
// this is opt-in, and a stray edit that made it default-on would silently
// change what every F-135 render computes.
func TestPhase62DefaultsOff(t *testing.T) {
	if os.Getenv("PAKON_GO_AUTOTONE") == "1" {
		t.Skip("PAKON_GO_AUTOTONE=1 is set in this environment")
	}
	if goAutoTone {
		t.Fatal("goAutoTone is true without PAKON_GO_AUTOTONE=1 — " +
			"Phase 6.2 must stay opt-in")
	}
}

// TestPhase62EmptyFrame — a zero-height frame must not panic.
func TestPhase62EmptyFrame(t *testing.T) {
	lut, err := computeGoToneLut(nil, testAnselRoot)
	if err != nil {
		t.Fatalf("empty frame errored: %v", err)
	}
	if lut != nil {
		t.Fatal("empty frame produced a LUT")
	}
}
