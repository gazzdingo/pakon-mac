// Package citrasdriver is the Go port of ImaCitrasOpBase::virtual_40 —
// PakonIMAu.dll VA 0x10169350..0x10169d0a, the per-pixel driver that APPLIES
// analyzeAutoTone's composed tone curve to a frame.
//
// # WHAT THIS IS, AND WHAT IT IS NOT
//
// ColorNegativePath::analyzeAutoTone (0x100fb730) has two halves. The ANALYSIS
// half — cna → dra → toneHelper → contrast → ast → citras-analyze — measures
// the frame and builds a single shared 4096-entry OutToneLut. The APPLY half is
// this file: it takes that LUT and the frame and produces the toned frame.
//
// Only the APPLY half is ported here. The analysis half is ~3,800 lines of
// Python across six subsystems (pakon_cna, pakon_dra, pakon_toneHelper,
// pakon_contrast, pakon_ast, pakon_citras) and is NOT ported to Go; see
// AutoToneAnalysisPorted in shasta.go. The LUT therefore has to be supplied by
// the caller — RenderRequest.OutToneLut, filled in by the Python side, which
// runs pakon_ansel.real_auto_tone. A Go caller with no LUT gets the old
// ShastaToneRpd stand-in and the banner says so.
//
// # THE REFERENCE
//
// tools/ansel/python-pipeline/pakon_citras_driver.py. That module's numpy forms
// are proven element-for-element against pakon_citras_apply.py's scalar,
// Unicorn-verified originals by pakon_citras_driver_golden.py; the operand
// wiring (CITRAS_DRIVER_WIRING_PORTED) was recovered by full capstone
// disassembly with manual ESP tracking and cross-checked four ways against each
// callee's own `ret N`. This package is a transcription of that module, and
// tools/test_citras_driver_ports.py re-proves the transcription on real frames.
//
// # THE MECHANISM, in one line
//
//	out_rgb = clamp(rgb + (toneLut[idx] - idx), minValue, maxValue)
//	idx     = lum - trunc((weight*(lum - reference) + 50) / 100)
//
// The tone curve is looked up not at the pixel's own luminance but at an index
// pulled toward a heavily smoothed (block-averaged, Gaussian-blurred,
// upsampled) luminance reference by a per-pixel, gradient-driven weight — full
// pull in smooth regions, minimal pull near edges — and the resulting 1-band
// delta is added to R/G/B. Process in luma, restore chroma.
//
// # THE ONE STAGE THAT IS NOT BIT-EXACT AGAINST THE DLL
//
// gaussBlur. The DLL accumulates on the x87 stack in 80-bit extended precision;
// both numpy and this port accumulate in float64. The tap ORDER is identical,
// so the only difference is intermediate rounding (~1e-13 absolute at these
// magnitudes), which can only change an output that lands within that distance
// of a .5 write-back boundary. pakon_citras_driver.py states this plainly and
// so does this file: this port inherits that limitation exactly, neither more
// nor less. What IS verified here is Go == Python, bit for bit.
//
// # FLOATING-POINT FUSION
//
// Go's spec permits fusing a multiply and an add into one FMA, "possibly across
// statements", and the compiler does exactly that on arm64 — which is the
// machine this repo is developed on. An FMA keeps more intermediate precision
// than numpy's separate multiply-then-add, so it would make gaussBlur disagree
// with the reference on precisely the boundary cases described above. Every
// accumulation below therefore rounds its product through an explicit float64
// conversion, which the spec defines as a rounding barrier. Do not "simplify"
// those conversions away — they are load-bearing, and the harness will catch it.
package citrasdriver

import (
	"fmt"
	"math"
)

// errf is the package's single error constructor. Every refusal below is a
// caller bug or an input the DLL itself could not have been handed, and each
// says which VA establishes that, so the message is the finding.
func errf(format string, a ...any) error { return fmt.Errorf(format, a...) }

// VAs, for grep-ability against the disassembly.
const (
	CitrasDriverVA       = 0x10169350 // ImaCitrasOpBase::virtual_40
	GaussianKernelVA     = 0x10168D90 // builds the normalised 1-D kernel
	GradientWeightVA     = 0x10168F30 // builds the avoidance table + weights
	BlockAverageVA       = 0x10154EA0 // ImaBlockAverageOp, vtable slot 0x28
	UpsampleI16VA        = 0x10155290
	UpsampleU8VA         = 0x101556A0
	PadOpComputeVA       = 0x10016D60 // ImaPadOpT<short>, pad mode 2 == MIRROR
	ConvolutionComputeVA = 0x100A4220 // ImaConvolutionSeparableOpT<short>
)

// Constants read out of .rdata, cited by the address they were read from.
const (
	sigmaToRadiusConst = -3.0         // qword [0x10578478]
	highThresholdConst = 8057.2168125 // qword [0x1058de98]
	lowThresholdScale  = 0.1273       // qword [0x1057fbb0]
	lowThresholdBias   = 18.0         // qword [0x1057fba8]
)

// Params is this->0x110..0x128, in ImaI16CitrasOp's ctor's own field order and
// offsets. The defaults are the literal block at 0x1058f4e8, plus DoClipping,
// which the ctor hard-codes to 1 at 0x100aea5d rather than reading from the
// block — that field is not part of AnsCitrasParams and has no .dpi source, so
// the clamp in toneCompose is unconditionally on for this op.
type Params struct {
	Sigma                 float64 // f64 @ 0x110
	BlockSize             int     // i32 @ 0x118
	MinAvoidance          int     // u8  @ 0x11c
	MaxGradient           int     // i16 @ 0x11e
	LowGradientThreshold  int     // i16 @ 0x120
	HighGradientThreshold int     // i16 @ 0x122
	DoClipping            int     // u8  @ 0x124
	MinValue              int     // i16 @ 0x126
	MaxValue              int     // i16 @ 0x128
}

// DefaultParams is the shipped CN-Enhanced block at 0x1058f4e8.
func DefaultParams() Params {
	return Params{
		Sigma:                 8.25,
		BlockSize:             8,
		MinAvoidance:          70,
		MaxGradient:           4095,
		LowGradientThreshold:  -1,
		HighGradientThreshold: -1,
		DoClipping:            1,
		MinValue:              0,
		MaxValue:              4095,
	}
}

// QuantiseRPD12 is pakon_ansel.real_auto_tone's own entry quantisation:
//
//	clipped = np.clip(np.rint(x), -32768, 32767).astype(np.int16)
//
// It lives here, next to the driver it feeds, so the render path and the
// verification harness cannot use two different roundings.
//
// np.rint is round-half-to-EVEN, so this uses math.RoundToEven and NOT
// math.Round, which is half-away-from-zero. The two disagree on every exact .5.
//
// HOW MUCH THAT MATTERS, MEASURED RATHER THAN ASSUMED: on a real 3000x2000
// frame, exact .5 values number ZERO of 18,000,000 — the post-FUGC array comes
// straight out of a 4096-entry apply LUT whose entries are integers, so the
// halves an earlier draft of this comment predicted do not occur. The harness's
// own negative control for this (math.Round in place of rint) therefore moves
// nothing, and is recorded there as a non-distinction rather than as a passing
// check. RoundToEven is still what is written, because it is what the reference
// does and matching the reference is not conditional on being able to observe
// the difference — but no one should believe this line is load-bearing on
// today's data, and a future caller feeding this non-integer input is the case
// that would make it so.
func QuantiseRPD12(v float64) int16 {
	r := math.RoundToEven(v)
	if r < -32768 {
		r = -32768
	}
	if r > 32767 {
		r = 32767
	}
	return int16(r)
}

// PlaneI16 is a single-band int16 image, row-major, no padding.
type PlaneI16 struct {
	H, W int
	Px   []int16
}

// PlaneU8 is a single-band uint8 image, row-major, no padding.
type PlaneU8 struct {
	H, W int
	Px   []uint8
}

// ImageI16 is a 3-band interleaved int16 image — the operand shape the driver
// validates at 0x101693eb / 0x101693f4 and refuses anything else.
type ImageI16 struct {
	H, W int
	Px   []int16 // len == H*W*3, R,G,B interleaved
}

func newPlaneI16(h, w int) PlaneI16 { return PlaneI16{H: h, W: w, Px: make([]int16, h*w)} }
func newPlaneU8(h, w int) PlaneU8   { return PlaneU8{H: h, W: w, Px: make([]uint8, h*w)} }

// ---------------------------------------------------------------------------
// small integer helpers, matching the DLL's own idioms
// ---------------------------------------------------------------------------

// wrap16 is signed 16-bit wraparound. Go's int64->int16 conversion truncates to
// the low 16 bits and reinterprets as signed, which is exactly the DLL's
// `mov word ptr [...], ax`.
func wrap16(v int64) int16 { return int16(v) }

// wrap32 is what an x86 imul/add on 32-bit registers actually produces, where a
// widening int64 would not.
func wrap32(v int64) int64 { return int64(int32(v)) }

// truncDiv is C's `/` for signed integers — round toward zero. Go's own integer
// division already truncates toward zero (unlike Python's floor //, which is
// why the reference needs an explicit helper and this does not); the named
// wrapper is kept so the call sites read the same in both languages.
func truncDiv(n int64, d int64) int64 { return n / d }

// floorDiv rounds toward -inf, matching numpy's `//` in _upsample_axis.
func floorDiv(n, d int64) int64 {
	q := n / d
	if n%d != 0 && (n < 0) != (d < 0) {
		q--
	}
	return q
}

// ftol is _ftol2 (0x104ffe44) — truncate toward zero.
func ftol(x float64) int { return int(math.Trunc(x)) }

func clampInt(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func clampInt64(v, lo, hi int64) int64 {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

// ---------------------------------------------------------------------------
// 0x10168d90 — the normalised 1-D Gaussian kernel
// ---------------------------------------------------------------------------

// GaussianRadius is r at 0x1016958f..0x101695a6 and 0x10168dbc..0x10168dc8.
//
// The DLL computes n = _ftol2(sigma * -3.0), then length = 1 - 2n, then
// r = length/2 truncating. For sigma > 0 that is exactly trunc(3*sigma), but the
// arithmetic below is the DLL's sign-for-sign so a negative or zero sigma
// degrades the same way it does in the DLL rather than differently.
func GaussianRadius(sigma float64) int {
	n := ftol(sigma * sigmaToRadiusConst)
	length := 1 - 2*n
	if length >= 0 {
		return ftol(float64(length) / 2)
	}
	return -ftol(float64(-length) / 2)
}

// VendorKernelSigma is the one sigma the shipped CN-Enhanced op uses. It is a
// built-in constant with no .dpi source.
const VendorKernelSigma = 8.25

// vendorKernelSigma825 is the exact 49 doubles 0x10168d90 produces for sigma
// 8.25, captured from real DLL execution under Unicorn. Embedded rather than
// recomputed because the DLL's x87 80-bit exp differs from libm's by up to
// 1 ULP (measured: 4 of 49 entries differ at this sigma).
var vendorKernelSigma825 = [...]float64{
	0.0007048053080374048, 0.0009954476112820658, 0.0013854371616296047,
	0.001900091160190667, 0.0025679184261579602, 0.0034198510490572953,
	0.004487994740426867, 0.005803856538684475, 0.00739605581007829,
	0.009287586499807213, 0.011492770773865691, 0.014014118934936405,
	0.016839377555815722, 0.019939095385275895, 0.023265053133203924,
	0.026749879355115636, 0.030308105319509792, 0.033838798084257764,
	0.0372297612728758, 0.04036312240920416, 0.04312195477420756,
	0.04539743397508645, 0.047095927339090515, 0.04814537580690002,
	0.048500363150605685, 0.04814537580690002, 0.047095927339090515,
	0.04539743397508645, 0.04312195477420756, 0.04036312240920416,
	0.0372297612728758, 0.033838798084257764, 0.030308105319509792,
	0.026749879355115636, 0.023265053133203924, 0.019939095385275895,
	0.016839377555815722, 0.014014118934936405, 0.011492770773865691,
	0.009287586499807213, 0.00739605581007829, 0.005803856538684475,
	0.004487994740426867, 0.0034198510490572953, 0.0025679184261579602,
	0.001900091160190667, 0.0013854371616296047, 0.0009954476112820658,
	0.0007048053080374048,
}

// GaussianKernel is 0x10168d90's output: a 2r+1-entry kernel summing to 1,
// kernel[i] = exp(-(i-r)^2 / (2*sigma^2)) divided by the sum. For sigma == 8.25
// the verbatim DLL doubles are returned instead of recomputed ones.
//
// THE FALLBACK BRANCH IS NOT CLAIMED BIT-EXACT AGAINST THE PYTHON REFERENCE.
// For any sigma other than 8.25 this recomputes, and two things differ from
// numpy: Go's math.Exp and numpy's exp can disagree by 1 ULP, and numpy's sum
// is pairwise where the loop below is sequential. Production never takes this
// branch — the shipped CN-Enhanced op's sigma is the built-in 8.25 — and
// tools/test_citras_driver_ports.py verifies only the branch production uses.
// A caller that needs another sigma must extend the verification first.
func GaussianKernel(sigma float64) []float64 {
	if sigma == VendorKernelSigma {
		out := make([]float64, len(vendorKernelSigma825))
		copy(out, vendorKernelSigma825[:])
		return out
	}
	r := GaussianRadius(sigma)
	k := -1.0 / (2.0 * sigma * sigma)
	n := 2*r + 1
	vals := make([]float64, n)
	var sum float64
	for i := 0; i < n; i++ {
		x := float64(i - r)
		vals[i] = math.Exp(float64(k * x * x))
		sum += vals[i]
	}
	for i := range vals {
		vals[i] /= sum
	}
	return vals
}

// ---------------------------------------------------------------------------
// 0x10168f30 — the gradient-driven avoidance weight plane
// ---------------------------------------------------------------------------

// AvoidanceTable is 0x10168f30's own MaxGradient+1-entry byte table, built at
// 0x10168f4e..0x101690c2: flat 100 up to lowThreshold, a cosine ease down to
// MinAvoidance between the two thresholds, flat MinAvoidance above
// highThreshold. Both thresholds have sigma-derived defaults when negative.
// Returns the table and the two resolved thresholds.
func AvoidanceTable(p Params) (table []uint8, lo, hi int) {
	hi = p.HighGradientThreshold
	if hi < 0 { // 0x10168f91 test bp,bp / jge
		hi = ftol(highThresholdConst / (p.Sigma * p.Sigma)) // 0x10168f9b
	}
	if hi < 1 { // 0x10168fb4 cmp bp,1
		hi = 1
	} else if hi > p.MaxGradient { // 0x10168fc1 cmp bp,di
		hi = p.MaxGradient
	}
	lo = p.LowGradientThreshold
	if lo < 0 { // 0x10168fc8 test bx,bx / jge
		lo = ftol(float64(hi)*lowThresholdScale - lowThresholdBias) // 0x10168fd4
		if lo < 0 {                                                 // 0x10168feb
			lo = 0
		}
	}

	table = make([]uint8, p.MaxGradient+1)
	i := 0
	if lo >= 0 { // 0x10168ff7 test edx,edx / jl
		for j := 0; j <= lo && j < len(table); j++ { // 0x10169007 rep stosd 0x64646464
			table[j] = 100
		}
		i = lo + 1
	}
	if lo != hi { // 0x10169018 cmp bx,bp / je
		amp := float64(100-p.MinAvoidance) * 0.5 // fmul qword [0x10574f40] == 0.5
		step := 3.14159265 / float64(hi-lo)      // fdivr qword [0x1057fba0]
		for j := i; j < hi && j < len(table); j++ {
			// 0x10169060..0x1016907d, in the DLL's own operation order:
			//   trunc((cos((j-lo)*step) + 1.0) * amp + minAvoidance + 0.5)
			v := float64(math.Cos(float64(j-lo)*step)+1.0) * amp
			v = v + float64(p.MinAvoidance) + 0.5
			table[j] = uint8(int64(math.Trunc(v)))
		}
		i = hi
	}
	if i <= p.MaxGradient { // 0x10169094 cmp esi,ecx / jg
		for j := i; j < len(table); j++ { // 0x101690bb rep stosd
			table[j] = uint8(p.MinAvoidance)
		}
	}
	return table, lo, hi
}

// GradientWeight is 0x10168f30's per-pixel half. Per pixel, from
// 0x10169220..0x10169289:
//
//	m = (cur - src[r][c+1])^2 + (cur - src[r+1][c])^2   // 32-bit signed
//	if m > maxGradient: m = maxGradient
//	out[r][c] = table[m]
//
// The final column of every row and the whole final row get MinAvoidance
// instead (0x1016928f and 0x101692d0) — there is no forward neighbour there,
// and the DLL does not wrap or replicate.
func GradientWeight(src PlaneI16, p Params) PlaneU8 {
	table, _, _ := AvoidanceTable(p)
	out := newPlaneU8(src.H, src.W)
	for i := range out.Px {
		out.Px[i] = uint8(p.MinAvoidance)
	}
	if src.H < 2 || src.W < 2 {
		return out
	}
	maxG := int64(p.MaxGradient)
	for r := 0; r < src.H-1; r++ {
		row := r * src.W
		next := (r + 1) * src.W
		for c := 0; c < src.W-1; c++ {
			cur := int64(src.Px[row+c])
			dx := cur - int64(src.Px[row+c+1])
			dy := cur - int64(src.Px[next+c])
			// The DLL squares and sums in 32-bit registers (imul eax,eax /
			// imul ebp,ecx / add eax,ebp at 0x1016923e..0x10169248), so model
			// the 32-bit signed wraparound rather than widening.
			m := wrap32(wrap32(dx*dx) + wrap32(dy*dy))
			if m > maxG { // 0x1016924a cmp eax,ecx / jle
				m = maxG
			}
			// DELIBERATE DIVERGENCE FROM VENDOR UB: the cmp/jle above is a
			// SIGNED compare with no lower bound, so a wrapped-negative m sends
			// the DLL's `mov al, byte ptr [ecx+eax]` (0x10169254) reading below
			// the table. Clamping at 0 is the only defensible reproducible
			// choice; it cannot change any result on data the driver actually
			// produces, because the plane feeding this is the Gauss-blurred
			// reference, already inside [minValue, maxValue].
			if m < 0 {
				m = 0
			}
			out.Px[row+c] = table[m]
		}
	}
	return out
}

// ---------------------------------------------------------------------------
// 0x10154ea0 — ImaBlockAverageOp's per-block compute
// ---------------------------------------------------------------------------

// BlockAverage is a non-overlapping factor x factor box downsample, correctly
// rounded. src must be exactly (BH*factor, BW*factor).
//
// Rounding, from the factor == 2 integer fast path (0x101550ac..0x101550c0) and
// the general x87 path (0x1015519d..0x101551b4), which agree: the bias is
// floor(factor^2 / 2), added BEFORE the division with the sign of the sum, and
// the division truncates toward zero. The store is `mov word ptr [...], ax` in
// both paths — low 16 bits, no clamp, no saturation.
func BlockAverage(src PlaneI16, factor int) (PlaneI16, error) {
	if factor <= 0 {
		return PlaneI16{}, errf("BlockAverage: factor=%d must be positive", factor)
	}
	if src.H%factor != 0 || src.W%factor != 0 {
		return PlaneI16{}, errf(
			"BlockAverage: %dx%d is not a multiple of factor=%d; the driver "+
				"always pads to one first (0x10169561..0x1016958b) — a caller "+
				"that does not is a bug", src.H, src.W, factor)
	}
	bh, bw := src.H/factor, src.W/factor
	out := newPlaneI16(bh, bw)
	half := int64((factor * factor) / 2)
	den := int64(factor * factor)
	for by := 0; by < bh; by++ {
		for bx := 0; bx < bw; bx++ {
			var s int64
			for dy := 0; dy < factor; dy++ {
				row := (by*factor + dy) * src.W
				for dx := 0; dx < factor; dx++ {
					s += int64(src.Px[row+bx*factor+dx])
				}
			}
			n := s
			if s >= 0 {
				n += half
			} else {
				n -= half
			}
			out.Px[by*bw+bx] = wrap16(truncDiv(n, den))
		}
	}
	return out, nil
}

// ---------------------------------------------------------------------------
// the driver's own arithmetic
// ---------------------------------------------------------------------------

// Luminance is virtual_64 (0x10168800): (R + G + B + 1) / 3, truncating toward
// zero, stored as int16.
func Luminance(img ImageI16) PlaneI16 {
	out := newPlaneI16(img.H, img.W)
	for i := 0; i < img.H*img.W; i++ {
		total := int64(img.Px[i*3]) + int64(img.Px[i*3+1]) + int64(img.Px[i*3+2]) + 1
		out.Px[i] = wrap16(truncDiv(total, 3))
	}
	return out
}

// AvoidanceBlend is virtual_60 (0x10168360), returning the DELTA plane.
//
// table is the Tsc1DLutT contents — lutSize signed-16-bit entries, bias 0. The
// DLL bias-subtracts the table in place for the duration of the call, so what
// it stores is wrap16(table[idx] - idx); that subtraction is folded in here
// rather than modelled as a mutate/restore pair, which is equivalent because
// idx is the same value on both sides.
func AvoidanceBlend(reference PlaneI16, weight PlaneU8, value PlaneI16, table []int64) PlaneI16 {
	out := newPlaneI16(value.H, value.W)
	hi := int64(len(table) - 1)
	for i := range out.Px {
		p := int64(value.Px[i])
		ref := int64(reference.Px[i])
		diff := int64(wrap16(p - ref))
		weighted := int64(weight.Px[i])*diff + 50
		q := truncDiv(weighted, 100)
		idx := int64(wrap16(p - q))
		// Deliberate divergence from vendor UB: the DLL indexes table with the
		// raw wrapped idx and reads adjacent heap outside [0, lutSize-1]. This
		// clamps, for both the lookup and the `- idx` bias term so the pair
		// stays consistent — which is what every other *Lut in this chain does.
		idx = clampInt64(idx, 0, hi)
		out.Px[i] = wrap16(table[idx] - idx)
	}
	return out
}

// ToneCompose is virtual_56 (0x10167bf0). base is 1-band and broadcasts across
// all three of img's bands.
func ToneCompose(img ImageI16, base PlaneI16, p Params) ImageI16 {
	out := ImageI16{H: img.H, W: img.W, Px: make([]int16, len(img.Px))}
	lo, hi := int64(p.MinValue), int64(p.MaxValue)
	for i := 0; i < img.H*img.W; i++ {
		b := int64(base.Px[i])
		for c := 0; c < 3; c++ {
			s := int64(wrap16(int64(img.Px[i*3+c]) + b))
			if p.DoClipping != 0 {
				s = clampInt64(s, lo, hi)
			}
			out.Px[i*3+c] = int16(s)
		}
	}
	return out
}

// ---------------------------------------------------------------------------
// 0x10155290 (i16) / 0x101556a0 (u8) — the separable upsample
// ---------------------------------------------------------------------------

// upsampleAxisI64 is one pass of 0x10155290/0x101556a0 along the last axis.
// src is (lines, n) as a flat int64 slice; the result is (lines, n*r).
//
// The kernels run a backwards integer DDA, but every variant computes the same
// closed form, for destination index j:
//
//	i   = clamp(floor((2j + 1 - r) / (2r)), 0, n-2)
//	ACC = 2r*s[i] + (2j + 1 - r - 2r*i) * (s[i+1] - s[i]) + r
//	out[j] = trunc_toward_zero(ACC / (2r))
//
// i.e. linear interpolation on half-pixel centres, rounded by the +r and then
// truncated — NOT symmetric rounding: for a negative quotient the +r biases
// upward. Outside [0, n-1] the source INDEX is clamped but the VALUE is not, so
// the two end intervals' slopes are extrapolated and edge outputs can go below
// the source's own minimum (and, for a u8 plane, wrap modulo 256 — the store is
// a plain `mov byte ptr`, no saturation).
func upsampleAxisI64(src []int64, lines, n, r int) ([]int64, error) {
	if n < 2 {
		return nil, errf(
			"upsampleAxis: n=%d; the DLL's kernels unconditionally read s[n-2] "+
				"and would dereference one element before the plane. The driver "+
				"never produces n<2 — a caller that does is a bug, not a case to "+
				"emulate", n)
	}
	d := int64(2 * r)
	outW := n * r
	out := make([]int64, lines*outW)
	// The index map depends only on j, so hoist it out of the line loop.
	idx := make([]int, outW)
	frac := make([]int64, outW)
	for j := 0; j < outW; j++ {
		t := int64(2*j + 1 - r)
		i := clampInt(int(floorDiv(t, d)), 0, n-2)
		idx[j] = i
		frac[j] = t - d*int64(i)
	}
	for l := 0; l < lines; l++ {
		si := l * n
		oi := l * outW
		for j := 0; j < outW; j++ {
			lo := src[si+idx[j]]
			hi := src[si+idx[j]+1]
			acc := d*lo + frac[j]*(hi-lo) + int64(r)
			out[oi+j] = truncDiv(acc, d)
		}
	}
	return out, nil
}

func transposeI64(src []int64, h, w int) []int64 {
	out := make([]int64, len(src))
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			out[x*h+y] = src[y*w+x]
		}
	}
	return out
}

// upsampleGeneric expands by integer ratios in two passes. Pass 1 expands X on
// src's own rows (0x101554e7/0x10155512); pass 2 then expands Y IN PLACE ON THE
// DESTINATION (0x1015553b/0x10155542, with the destination's row/column strides
// swapped so the kernel walks columns). Doing pass 2 on the already-widened
// rows — not on the original — is what makes the two passes separable rather
// than independent.
//
// bits selects the store width's wraparound (16 for the i16 kernel, 8 for u8),
// matching the two kernels' stores.
func upsampleGeneric(src []int64, h, w, rx, ry, bits int) ([]int64, int, int, error) {
	if rx < 1 || ry < 1 {
		return nil, 0, 0, errf(
			"upsample: ratios must be >= 1, got %dx%d (the DLL's own "+
				"idiv-exactness gate, 0x10155421)", rx, ry)
	}
	wide, err := upsampleAxisI64(src, h, w, rx)
	if err != nil {
		return nil, 0, 0, err
	}
	wideW := w * rx
	narrow(wide, bits)

	tall, err := upsampleAxisI64(transposeI64(wide, h, wideW), wideW, h, ry)
	if err != nil {
		return nil, 0, 0, err
	}
	tallH := h * ry
	narrow(tall, bits)
	return transposeI64(tall, wideW, tallH), tallH, wideW, nil
}

// narrow applies the destination store's wraparound in place.
func narrow(a []int64, bits int) {
	if bits == 16 {
		for i, v := range a {
			a[i] = int64(int16(v))
		}
		return
	}
	for i, v := range a {
		a[i] = v & 0xFF
	}
}

// ---------------------------------------------------------------------------
// 0x1014f7d0 / 0x10016d60 — ImaPadOpT<short>, pad mode 2 == MIRROR
// ---------------------------------------------------------------------------

// reflectIndex is the index arithmetic at 0x1001754a..0x100175a9:
//
//	srcY = abs(abs((y + H - 1) % (2H - 2)) - (H - 1))
//
// period 2N-2, i.e. reflection that does NOT repeat the edge sample (numpy's
// mode="reflect"; OpenCV's BORDER_REFLECT_101). Written here with an explicit
// modulo fold so it also handles a margin larger than the plane, which is what
// numpy does by repeated reflection and what the radius pad can ask for on a
// small block grid.
func reflectIndex(k, n int) int {
	if n <= 1 {
		return 0
	}
	period := 2*n - 2
	k %= period
	if k < 0 {
		k += period
	}
	if k >= n {
		k = period - k
	}
	return k
}

// MirrorPad is ImaPadOpT<short> in MIRROR mode. The driver constructs this
// operator twice, both times with the literal 2 as its padMode argument
// (0x10169754 and 0x101698eb); 2 is MIRROR per the mode-name table at
// 0x106a3924 = {CONSTANT, EXTEND, MIRROR, WRAP, JUNK, COPY, SHRINK}, and the
// compute body's jump table at 0x10017c10 sends index 2 to 0x100173dd. The
// sample itself is copied verbatim — no arithmetic.
//
// The four margins are in the ctor's own argument order: left, right, top,
// bottom.
func MirrorPad(src PlaneI16, left, right, top, bottom int) PlaneI16 {
	if left == 0 && right == 0 && top == 0 && bottom == 0 {
		return src
	}
	h, w := src.H+top+bottom, src.W+left+right
	out := newPlaneI16(h, w)
	rows := make([]int, h)
	for y := 0; y < h; y++ {
		rows[y] = reflectIndex(y-top, src.H)
	}
	cols := make([]int, w)
	for x := 0; x < w; x++ {
		cols[x] = reflectIndex(x-left, src.W)
	}
	for y := 0; y < h; y++ {
		sr := rows[y] * src.W
		dr := y * w
		for x := 0; x < w; x++ {
			out.Px[dr+x] = src.Px[sr+cols[x]]
		}
	}
	return out
}

// ---------------------------------------------------------------------------
// 0x100a4010 / 0x100a4220 — ImaConvolutionSeparableOpT<short>
// ---------------------------------------------------------------------------

// GaussBlur is ImaConvolutionSeparableOpT<short>'s compute (0x100a4220): a
// "valid" separable convolution, output srcH-kh+1 by srcW-kw+1, with NO border
// rule of its own — it consumes the r-pixel mirror pad the ImaPadOpT above
// already produced.
//
// Pass order is VERTICAL first (0x100a43d0, taps = kernel height, tap step = the
// row stride, run across the full source width into a double line buffer) then
// HORIZONTAL out of that buffer (0x100a4430). 0x10168d90 hands the SAME array in
// as both the row and the column kernel (0x10168eb8), so one 1-D Gaussian serves
// both axes.
//
// Write-back (0x100a447b..0x100a449b): acc + 0.5 if acc >= 0 else acc - 0.5,
// then _ftol2 truncation toward zero — round-half-AWAY-from-zero — and
// `mov word ptr [edi], ax`, low 16 bits, no saturation.
//
// NO CLAMP HAPPENS HERE, despite minValue/maxValue being passed in. The clip
// flag is this->0x13, set from the ctor's sixth argument, and the driver pushes
// esi for it at 0x10169968 where esi is still 0 from the xor esi,esi at
// 0x1016989f. So the branch at 0x100a4457 always skips the clamp and the two
// bounds are stored but never applied.
//
// See the package comment on precision and on why the explicit float64
// conversions below must not be removed.
func GaussBlur(src PlaneI16, kernel []float64) (PlaneI16, error) {
	kh := len(kernel)
	kw := kh
	outH, outW := src.H-kh+1, src.W-kw+1
	if outH <= 0 || outW <= 0 {
		return PlaneI16{}, errf(
			"GaussBlur: %dx%d source with a %d-tap kernel leaves a %dx%d valid "+
				"region; the driver always pads by the kernel radius first "+
				"(0x10169922)", src.H, src.W, kh, outH, outW)
	}
	// Pass 1: vertical, into a float64 buffer of (outH, src.W). Tap k is added
	// for every pixel before tap k+1, matching the DLL's own inner loop and
	// numpy's per-k array add.
	tmp := make([]float64, outH*src.W)
	for k := 0; k < kh; k++ {
		kv := kernel[k]
		for y := 0; y < outH; y++ {
			srow := (y + k) * src.W
			trow := y * src.W
			for x := 0; x < src.W; x++ {
				// The explicit float64 conversion is a rounding barrier that
				// stops the compiler fusing this into an FMA. Load-bearing.
				tmp[trow+x] += float64(kv * float64(src.Px[srow+x]))
			}
		}
	}
	// Pass 2: horizontal, out of that buffer.
	acc := make([]float64, outH*outW)
	for k := 0; k < kw; k++ {
		kv := kernel[k]
		for y := 0; y < outH; y++ {
			trow := y * src.W
			arow := y * outW
			for x := 0; x < outW; x++ {
				acc[arow+x] += float64(kv * tmp[trow+x+k])
			}
		}
	}
	out := newPlaneI16(outH, outW)
	for i, a := range acc {
		if a >= 0.0 {
			a += 0.5
		} else {
			a -= 0.5
		}
		out.Px[i] = wrap16(int64(math.Trunc(a)))
	}
	return out, nil
}

// ---------------------------------------------------------------------------
// the whole driver
// ---------------------------------------------------------------------------

// Apply is ImaCitrasOpBase::virtual_40 (0x10169350), end to end.
//
// img is the 3-band I16 operand the DLL pre-fills from this->0x104 and then
// mutates in place; this returns a new image instead. toneLut is
// analyzeAutoTone's composed curve — exactly the array AnsCitrasOperand::
// setToneLut copies and AnsImaCitrasAggregate's ctor wraps in the Tsc1DLutT that
// becomes this->0x108. For CN-Enhanced that is 4096 entries with bias 0.
func Apply(img ImageI16, toneLut []int64, p Params) (ImageI16, error) {
	out, _, err := ApplyTraced(img, toneLut, p)
	return out, err
}

// Trace carries every intermediate plane Apply builds, in the driver's own
// order. It exists for tools/test_citras_driver_ports.py, which diffs each
// stage against the Python reference separately rather than only comparing the
// final image — docs/74 §171.3: at least two errors in this chain have opposite
// sign, so a stage checked only through an end-to-end number can be wrong in a
// direction the total hides. Nothing in the render path reads this.
type Trace struct {
	Lum       PlaneI16 // 0x101696c6
	Padded    PlaneI16 // 0x1016977c
	Blk       PlaneI16 // 0x10169861
	Ext       PlaneI16 // 0x10169922
	Kernel    []float64
	Smooth    PlaneI16 // 0x101699d7
	WeightLow PlaneU8  // 0x10169a9f
	Reference PlaneI16 // 0x10169af7
	Weight    PlaneU8  // 0x10169b7d
	Delta     PlaneI16 // 0x10169bf3
}

// ApplyTraced is Apply, additionally returning every intermediate.
func ApplyTraced(img ImageI16, toneLut []int64, p Params) (ImageI16, Trace, error) {
	out, tr, err := applyTraced(img, toneLut, p)
	return out, tr, err
}

func applyTraced(img ImageI16, toneLut []int64, p Params) (ImageI16, Trace, error) {
	var tr Trace
	if img.H <= 0 || img.W <= 0 || len(img.Px) != img.H*img.W*3 {
		return ImageI16{}, tr, errf(
			"Apply: expected an (H, W, 3) image with %d samples, got %d for "+
				"%dx%d. The driver validates 3 bands on both operands at "+
				"0x101693eb and 0x101693f4 and refuses anything else",
			img.H*img.W*3, len(img.Px), img.H, img.W)
	}
	if len(toneLut) == 0 {
		return ImageI16{}, tr, errf("Apply: toneLut is empty; there is no curve to apply")
	}
	bs := p.BlockSize
	if bs <= 0 {
		return ImageI16{}, tr, errf("Apply: blockSize=%d must be positive", bs)
	}
	radius := GaussianRadius(p.Sigma)
	if radius < 0 {
		return ImageI16{}, tr, errf("Apply: sigma=%v yields a negative radius %d", p.Sigma, radius)
	}
	bw := (img.W + bs - 1) / bs
	bh := (img.H + bs - 1) / bs
	padW, padH := bw*bs, bh*bs

	tr.Lum = Luminance(img)                                     // 0x101696c6
	tr.Padded = MirrorPad(tr.Lum, 0, padW-img.W, 0, padH-img.H) // 0x1016977c
	blk, err := BlockAverage(tr.Padded, bs)                     // 0x10169861
	if err != nil {
		return ImageI16{}, tr, err
	}
	tr.Blk = blk
	tr.Ext = MirrorPad(tr.Blk, radius, radius, radius, radius) // 0x10169922
	tr.Kernel = GaussianKernel(p.Sigma)                        // 0x1016994a
	smooth, err := GaussBlur(tr.Ext, tr.Kernel)                // 0x101699d7
	if err != nil {
		return ImageI16{}, tr, err
	}
	tr.Smooth = smooth
	tr.WeightLow = GradientWeight(tr.Smooth, p) // 0x10169a9f

	reference, err := upsamplePlaneI16(tr.Smooth, bs, bs, img.H, img.W) // 0x10169af7
	if err != nil {
		return ImageI16{}, tr, err
	}
	tr.Reference = reference
	weight, err := upsamplePlaneU8(tr.WeightLow, bs, bs, img.H, img.W) // 0x10169b7d
	if err != nil {
		return ImageI16{}, tr, err
	}
	tr.Weight = weight

	tr.Delta = AvoidanceBlend(tr.Reference, tr.Weight, tr.Lum, toneLut) // 0x10169bf3
	return ToneCompose(img, tr.Delta, p), tr, nil                       // 0x10169c30
}

// upsamplePlaneI16 upsamples then crops to the frame, matching the driver's
// obj2.roi = {0,0,W,H} at 0x10169ba6.
func upsamplePlaneI16(src PlaneI16, rx, ry, cropH, cropW int) (PlaneI16, error) {
	in := make([]int64, len(src.Px))
	for i, v := range src.Px {
		in[i] = int64(v)
	}
	up, h, w, err := upsampleGeneric(in, src.H, src.W, rx, ry, 16)
	if err != nil {
		return PlaneI16{}, err
	}
	if h < cropH || w < cropW {
		return PlaneI16{}, errf("upsample produced %dx%d, smaller than the %dx%d frame",
			h, w, cropH, cropW)
	}
	out := newPlaneI16(cropH, cropW)
	for y := 0; y < cropH; y++ {
		for x := 0; x < cropW; x++ {
			out.Px[y*cropW+x] = int16(up[y*w+x])
		}
	}
	return out, nil
}

func upsamplePlaneU8(src PlaneU8, rx, ry, cropH, cropW int) (PlaneU8, error) {
	in := make([]int64, len(src.Px))
	for i, v := range src.Px {
		in[i] = int64(v)
	}
	up, h, w, err := upsampleGeneric(in, src.H, src.W, rx, ry, 8)
	if err != nil {
		return PlaneU8{}, err
	}
	if h < cropH || w < cropW {
		return PlaneU8{}, errf("upsample produced %dx%d, smaller than the %dx%d frame",
			h, w, cropH, cropW)
	}
	out := newPlaneU8(cropH, cropW)
	for y := 0; y < cropH; y++ {
		for x := 0; x < cropW; x++ {
			out.Px[y*cropW+x] = uint8(up[y*w+x])
		}
	}
	return out, nil
}
