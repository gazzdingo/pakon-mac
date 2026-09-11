package citrasdriver

import (
	"math"
	"testing"
)

// The real comparison for this package is tools/test_citras_driver_ports.py,
// which diffs every stage against pakon_citras_driver.py on a real frame. It
// needs a real capture and a Python environment, so it cannot run under
// `go test`. What lives here is the subset that can be checked from constants
// alone — the values that come straight out of .rdata and the disassembly, and
// the two arithmetic choices most likely to be "cleaned up" by a later reader.

// The shipped CN-Enhanced sigma is 8.25, and 0x10168d90's kernel for it is 49
// taps summing to 1. Both numbers are load-bearing: the radius drives the
// mirror pad's margin and the valid-convolution output size.
func TestVendorKernelShape(t *testing.T) {
	if got := GaussianRadius(VendorKernelSigma); got != 24 {
		t.Errorf("GaussianRadius(%v) = %d, want 24", VendorKernelSigma, got)
	}
	k := GaussianKernel(VendorKernelSigma)
	if len(k) != 49 {
		t.Fatalf("kernel has %d taps, want 2*24+1 = 49", len(k))
	}
	var sum float64
	for _, v := range k {
		sum += v
	}
	if math.Abs(sum-1.0) > 1e-12 {
		t.Errorf("kernel sums to %.17g, want 1", sum)
	}
	// 0x10168d90 normalises by a single reciprocal, so the table is symmetric.
	for i := 0; i < len(k)/2; i++ {
		if k[i] != k[len(k)-1-i] {
			t.Errorf("kernel not symmetric at %d: %v vs %v", i, k[i], k[len(k)-1-i])
		}
	}
}

// Both thresholds default to -1 and are derived from sigma at 0x10168f9b and
// 0x10168fd4. The low one derives NEGATIVE (118*0.1273-18 = -2.97) and is then
// clamped to 0 — via truncation toward zero, not floor, which is why it is -2
// before the clamp and not -3. Getting that wrong shifts the whole cosine ramp.
func TestAvoidanceTableThresholds(t *testing.T) {
	p := DefaultParams()
	table, lo, hi := AvoidanceTable(p)
	if lo != 0 || hi != 118 {
		t.Errorf("thresholds = (%d, %d), want (0, 118)", lo, hi)
	}
	if len(table) != p.MaxGradient+1 {
		t.Fatalf("table has %d entries, want %d", len(table), p.MaxGradient+1)
	}
	if table[0] != 100 {
		t.Errorf("table[0] = %d, want 100 (flat up to lowThreshold)", table[0])
	}
	if table[len(table)-1] != uint8(p.MinAvoidance) {
		t.Errorf("table[max] = %d, want minAvoidance %d",
			table[len(table)-1], p.MinAvoidance)
	}
	// The ramp is monotone non-increasing between the thresholds.
	for i := 1; i <= hi && i < len(table); i++ {
		if table[i] > table[i-1] {
			t.Fatalf("ramp rises at %d: %d > %d", i, table[i], table[i-1])
		}
	}
}

// MIRROR is BORDER_REFLECT_101 — it does NOT repeat the edge sample. The other
// reflection (BORDER_REFLECT, numpy "symmetric") is the classic wrong pick and
// the harness's own negative control shows it moving 20 % of the padded plane.
func TestMirrorPadDoesNotRepeatTheEdge(t *testing.T) {
	src := PlaneI16{H: 1, W: 4, Px: []int16{10, 20, 30, 40}}
	got := MirrorPad(src, 2, 2, 0, 0)
	want := []int16{30, 20, 10, 20, 30, 40, 30, 20}
	if len(got.Px) != len(want) {
		t.Fatalf("padded width %d, want %d", len(got.Px), len(want))
	}
	for i := range want {
		if got.Px[i] != want[i] {
			t.Fatalf("mirror pad = %v, want %v (reflect_101, edge not repeated)",
				got.Px, want)
		}
	}
}

// Luminance is (R+G+B+1)/3 truncating toward zero. The +1 is a rounding bias
// the harness measures at 33 % of pixels on a real frame; a port that drops it
// is wrong on a third of the image.
func TestLuminanceRoundingBias(t *testing.T) {
	img := ImageI16{H: 1, W: 3, Px: []int16{
		0, 0, 0, // (0+0+0+1)/3 = 0
		1, 1, 0, // (1+1+0+1)/3 = 1
		2, 2, 2, // (2+2+2+1)/3 = 2
	}}
	got := Luminance(img)
	want := []int16{0, 1, 2}
	for i := range want {
		if got.Px[i] != want[i] {
			t.Errorf("Luminance = %v, want %v", got.Px, want)
		}
	}
}

// AvoidanceBlend returns a DELTA — table[idx] - idx — not a toned value. With a
// weight of 100 (a perfectly smooth region) the index is pulled all the way to
// the reference.
func TestAvoidanceBlendReturnsADelta(t *testing.T) {
	// identity curve: delta must be exactly zero everywhere
	table := make([]int64, 4096)
	for i := range table {
		table[i] = int64(i)
	}
	ref := PlaneI16{H: 1, W: 2, Px: []int16{100, 3000}}
	val := PlaneI16{H: 1, W: 2, Px: []int16{200, 2000}}
	w := PlaneU8{H: 1, W: 2, Px: []uint8{100, 100}}
	got := AvoidanceBlend(ref, w, val, table)
	for i, v := range got.Px {
		if v != 0 {
			t.Errorf("identity curve gave a non-zero delta at %d: %d", i, v)
		}
	}
	// A constant offset curve must give exactly that offset back as the delta.
	for i := range table {
		table[i] = int64(i) + 7
	}
	got = AvoidanceBlend(ref, w, val, table)
	for i, v := range got.Px {
		if v != 7 {
			t.Errorf("offset curve gave delta %d at %d, want 7", v, i)
		}
	}
}

// Apply must refuse rather than guess on the shapes the DLL itself validates.
func TestApplyRefusesBadOperands(t *testing.T) {
	lut := make([]int64, 4096)
	p := DefaultParams()
	if _, err := Apply(ImageI16{H: 2, W: 2, Px: make([]int16, 4)}, lut, p); err == nil {
		t.Error("a 2x2 image with 4 samples (not 3 bands) was accepted")
	}
	img := ImageI16{H: 8, W: 8, Px: make([]int16, 8*8*3)}
	if _, err := Apply(img, nil, p); err == nil {
		t.Error("an empty tone LUT was accepted")
	}
	bad := p
	bad.BlockSize = 0
	if _, err := Apply(img, lut, bad); err == nil {
		t.Error("blockSize 0 was accepted")
	}
}
