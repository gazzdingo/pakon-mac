// Package anscna is the Go transcription of
// tools/ansel/python-pipeline/pakon_cna.py — AnsCnaCapabilityImpl
// (PakonIMAu.dll 0x1022ea50), the FIRST of the six subsystems in
// ColorNegativePath::analyzeAutoTone's ANALYSIS half.
//
// WHAT THIS IS AND IS NOT
// =======================
// This is a line-for-line transcription of the Python module, which is itself
// Unicorn-verified against the real DLL (pakon_cna_golden.py). It is therefore
// bit-exactness against the vendor BY TRANSITIVITY, and only to the extent
// tools/test_cna_port.py actually demonstrates Go == Python on real data.
// Nothing here re-derives any vendor arithmetic; every VA in a comment is
// carried over from the Python source, not independently rediscovered.
//
// cna measures the frame and produces the three things the rest of the chain
// threads: LuminanceHist, EdgeHist and ToneScaleLut (analyzeAutoTone's stage 1,
// 0x100fbdf8), plus bElmoOccured / elmoAggressiveness for the shell's fork at
// 0x100fc5cd.
//
// FLOATING POINT
// ==============
// The vendor computes on the x87 stack under FPCW 0x027f (53-bit precision
// control) and stores float32. The Python reference keeps register values in
// binary64 and calls f32() at exactly the points the DLL does a fst/fstp dword.
// This port does the same: every value is a float64, and f32() is the only
// narrowing. Using Go's float32 type for the register values would round in
// places the vendor does not, so it is deliberately NOT used.
//
// TWO STATED DIVERGENCES FROM THE PYTHON REFERENCE, both in branches no real
// frame has been observed to reach. They are recorded rather than hidden:
//
//   - histResample step 4 divides hist[i] by the histogram's own total with a
//     plain /, as the Python does. For total == 0 Python raises
//     ZeroDivisionError and this port produces the x87 infinity/NaN instead.
//     The vendor does the latter; the Python is the one that diverges, so
//     matching Python exactly here is impossible and matching the DLL is the
//     better failure. Same for analyzeImage's pct = below/nEdge.
//   - analyzeImageThreshold's luminance histogram store is unchecked in the
//     vendor (inc dword [edi + eax*4], 0x1022df80). Python would index a
//     Python list, i.e. wrap negatives to the tail and raise on overflow; this
//     port returns an error naming the offending value instead of emulating a
//     Python list artefact that is not vendor behaviour either.
package anscna

import (
	"fmt"
	"math"
)

// ---------------------------------------------------------------------------
// addresses (carried from pakon_cna.py; not re-derived here)
// ---------------------------------------------------------------------------

const (
	VAAnalyze       = 0x1022EA50 // AnsCnaCapabilityImpl::analyze
	VAAnalyzeImage  = 0x1022DDC0 // the whole tone analysis
	VALaplacian     = 0x1022C340
	VAGaussSmooth   = 0x1022C8F0
	VAPeakSearch    = 0x1022C3E0
	VAHistResample  = 0x1022CA80
	VAMapDown       = 0x1022C520
	VAMapUp         = 0x1022C630
	VAToneLUTBuild  = 0x1022C740
	VAValidateParam = 0x1022CEB0
)

// float/double literals the subsystem reads out of .rdata.
const (
	kHalf        = 0.5                 // qword 0x10574f40
	kMinusHalf   = -0.5                // qword 0x1057ae70
	kInvSqrt2Pi  = 0.3989423241103187  // qword 0x1059a858 -- NOT 1/sqrt(2*pi)
	kOneF32      = 1.0                 // dword 0x1058d4c0
	kHundredF32  = 100.0               // dword 0x1059bea8
	kLUTMax      = 0x0FFF              // the luminance / LUT clamp
	kToneMaxF32  = 4095.0              // dword 0x1059f880
	kBlendMin    = 0.10000000149011612 // dword 0x10598cac
	kBlendMax    = 9.0                 // dword 0x10598cb0
	kMinPosThr   = 4                   // word  0x10598cb4
	kSizeFactMin = 1.0                 // dword 0x10598cb8
	kSizeFactMax = 10.0                // dword 0x10598cbc
	kSigmaMin    = 1.0                 // dword 0x10598cc0
	kSigmaMax    = 50.0                // dword 0x10598cc4
	kOneF64      = 1.0                 // qword 0x10574f50
)

// ---------------------------------------------------------------------------
// float32 / x87 helpers
// ---------------------------------------------------------------------------

// f32 is one fst/fstp dword — round a register value to float32.
func f32(x float64) float64 { return float64(float32(x)) }

// x87Indefinite is x87's "real indefinite" QNaN, sign bit set — what a
// masked-exception 0.0/0.0 produces under FPCW 0x027f. Go's math.NaN() has the
// sign bit clear, so it is built explicitly; only the payload's SIGN is ever
// observable downstream (through copysign), never its bits.
var x87Indefinite = math.Float64frombits(0xFFF8000000000000)

// x87Div is fdiv/fdivr under FPCW 0x027f's masked exceptions: the DLL does not
// trap, it produces a correctly-signed infinity (0.0/0.0 instead yields the
// real indefinite QNaN). Python's / raises ZeroDivisionError on both, which is
// why pakon_cna.py has this same helper.
func x87Div(num, den float64) float64 {
	if den == 0.0 {
		if num == 0.0 {
			return x87Indefinite
		}
		return math.Copysign(math.Inf(1), num) * math.Copysign(1.0, den)
	}
	return num / den
}

// i16 is one 16-bit register write (mov word), two's complement.
func i16(x int64) int64 {
	v := uint16(uint64(x))
	return int64(int16(v))
}

// i32 is one 32-bit register write, two's complement.
func i32(x int64) int64 { return int64(int32(uint32(uint64(x)))) }

// idiv is x86 idiv — quotient truncated toward zero.
func idiv(a, b int64) int64 {
	q := abs64(a) / abs64(b)
	if (a < 0) != (b < 0) {
		return -q
	}
	return q
}

func abs64(a int64) int64 {
	if a < 0 {
		return -a
	}
	return a
}

// ftol2 is 0x104ffe44 — _ftol2, truncation toward zero, 64-bit result.
//
// The Python reference returns math.trunc(x), an arbitrary-precision int. Go
// has no such type here, and a float64 that does not fit in an int64 has no
// int64 answer, so the saturating values below are returned instead. That is
// observationally identical everywhere the result is CLAMPED before use (every
// index site in this file), and ftol2I32 exists for the one site that instead
// narrows it to 32 bits.
func ftol2(x float64) int64 {
	if math.IsNaN(x) || math.IsInf(x, 0) {
		return math.MinInt64 // the masked-invalid "integer indefinite"
	}
	t := math.Trunc(x)
	if t >= 9223372036854775808.0 {
		return math.MaxInt64
	}
	if t <= -9223372036854775808.0 {
		return math.MinInt64
	}
	return int64(t)
}

// ftol2I32 is i32(ftol2(x)) computed exactly, including for |x| >= 2**63 where
// trunc(x) has no int64 representation. math.Mod is exact for these magnitudes,
// so the low 32 bits are the true ones rather than a saturated stand-in.
//
// The reachable case this matters for is NaN: 0x1022ce98 stores only EAX of
// _ftol2's edx:eax, and the 64-bit integer-indefinite pattern
// 0x8000000000000000 has LOW 32 bits ZERO. A real scanned roll's dark-half
// histogram reaches it (pakon_cna.py's histResample comment, live-DLL
// confirmed), so this is production behaviour, not a corner.
func ftol2I32(x float64) int64 {
	if math.IsNaN(x) || math.IsInf(x, 0) {
		return 0 // low 32 bits of 0x8000000000000000
	}
	t := math.Trunc(x)
	if t >= -9223372036854775808.0 && t < 9223372036854775808.0 {
		return i32(int64(t))
	}
	m := math.Mod(t, 4294967296.0)
	if m < 0 {
		m += 4294967296.0
	}
	return int64(int32(uint32(m)))
}

// roundHalfUp is the vendor's ubiquitous `fadd 0.5; call _ftol2` — trunc(x+0.5),
// NOT round(): half away from zero for positives, toward zero for negatives,
// with the +0.5 taken at register precision before any float32 store.
func roundHalfUp(x float64) int64 { return ftol2(x + kHalf) }

func roundHalfUpI32(x float64) int64 { return ftol2I32(x + kHalf) }

// ---------------------------------------------------------------------------
// AnsCnaParams
// ---------------------------------------------------------------------------

// Params is AnsCnaParams (0x7c B). The float fields hold float32-exact values
// in a float64, matching how the Python reference carries them.
type Params struct {
	RedShift                    int64
	GreenShift                  int64
	BlueShift                   int64
	HistSize                    int64
	BucketSize                  int64
	LowClamp                    float64 // +0x10, unnamed by the vendor dumper
	HighClamp                   float64 // +0x14, unnamed
	Blend                       float64
	Pivot                       int64
	MinPivotPercentile          float64
	MaxPivotPercentile          float64
	ThresholdMultiplier         float64
	ThresholdReductionFactor    float64
	MinPosThreshold             int64
	MinLapPixelRatio            float64
	SmoothingSizeFactor         float64
	LaplacianHistSmoothingSigma float64
	CoarseHistSmoothingSigma    float64
	ToneScaleSmoothingSigma     float64
	DarkMaxContrastGain         float64
	LightMaxContrastGain        float64
	DarkScale                   float64 // +0x50, unnamed
	LightScale                  float64 // +0x54, unnamed
	Unk58                       float64
	Unk5c                       float64
	MinGaussSigma               float64
	MaxGaussSigma               float64
	ElmoNeutralLimit            int64
	ElmoRedLimit                int64
	ElmoGreenLimit              int64
	ElmoBlueLimit               int64
	ElmoSatThreshold            int64
	ElmoCriticalPercent         float64
	ElmoAggressiveness          int64
}

// DefaultParams is 0x100f8030's ctor defaults, i.e.
// ansel-cna-default-default.dpi. Kept in sync with pakon_cna.CnaParams's own
// dataclass defaults; the harness passes the real 0x7c-byte image over the wire
// rather than relying on these, so a drift here cannot silently pass.
func DefaultParams() Params {
	return Params{
		HistSize:                    5000,
		BucketSize:                  10,
		LowClamp:                    0.5,
		HighClamp:                   1.5,
		Blend:                       1.0,
		Pivot:                       1550,
		MinPivotPercentile:          f32(0.1),
		MaxPivotPercentile:          f32(0.9),
		ThresholdMultiplier:         1.5,
		ThresholdReductionFactor:    f32(0.949),
		MinPosThreshold:             4,
		MinLapPixelRatio:            f32(0.1),
		SmoothingSizeFactor:         4.0,
		LaplacianHistSmoothingSigma: 10.0,
		CoarseHistSmoothingSigma:    2.0,
		ToneScaleSmoothingSigma:     4.0,
		DarkMaxContrastGain:         f32(1.33333),
		LightMaxContrastGain:        f32(1.33333),
		DarkScale:                   f32(243.75),
		LightScale:                  f32(243.75),
		Unk58:                       260.0,
		Unk5c:                       84.5,
		MinGaussSigma:               1.0,
		MaxGaussSigma:               50.0,
		ElmoNeutralLimit:            1500,
		ElmoRedLimit:                1600,
		ElmoGreenLimit:              1600,
		ElmoBlueLimit:               1600,
		ElmoSatThreshold:            400,
		ElmoCriticalPercent:         5.0,
		ElmoAggressiveness:          1,
	}
}

// Image is what 0x1022ddc0 reads out of its second argument. Pixels is an
// interleaved R,G,B int16 buffer, three shorts per pixel, Width*Height pixels,
// row-major with no padding.
type Image struct {
	Width  int
	Height int
	Pixels []int16
}

// ---------------------------------------------------------------------------
// 0x1022c340 -- the laplacian
// ---------------------------------------------------------------------------

// Laplacian is 0x1022c340 — the 5-point laplacian over the interior, in int16.
// lap = left + right + up + down - 4*centre, with every intermediate wrapping
// modulo 2**16 because the vendor computes it in 16-bit registers. Output is
// dense, (height-2)*(width-2) entries, row-major.
func Laplacian(lum []int64, width, height int) []int64 {
	out := make([]int64, 0)
	if height <= 2 {
		return out
	}
	if width > 2 {
		out = make([]int64, 0, (height-2)*(width-2))
	}
	for r := 0; r < height-2; r++ {
		if width <= 2 {
			continue
		}
		base := (r + 1) * width
		for c := 1; c < width-1; c++ {
			centre := lum[base+c]
			v := i16(lum[base+c-1] - i16(centre*4))
			v = i16(v + lum[base-width+c])
			v = i16(v + lum[base+width+c])
			v = i16(v + lum[base+c+1])
			out = append(out, v)
		}
	}
	return out
}

// ---------------------------------------------------------------------------
// 0x1022c8f0 -- 1-D gaussian convolution
// ---------------------------------------------------------------------------

// GaussHalfWidth is d = trunc(sigma*smoothingSizeFactor + 0.5) (0x1022c8f4).
func GaussHalfWidth(sigma, smoothingSizeFactor float64) int64 {
	return roundHalfUp(f32(sigma) * f32(smoothingSizeFactor))
}

// GaussKernel is the 2d+1 tap kernel built at 0x1022c940..0x1022c96f.
// k[j] = exp(i*i * (-0.5/sigma**2)) * (0.3989423241103187/sigma), i = -d..d.
// The two scale factors are formed once, before the loop, at register
// precision; i*i is formed in integer registers (imul) so it is exact.
func GaussKernel(sigma, smoothingSizeFactor float64) []float64 {
	s := f32(sigma)
	d := GaussHalfWidth(s, smoothingSizeFactor)
	amp := kInvSqrt2Pi / s       // 0x1022c90e, register-wide
	expk := kMinusHalf / (s * s) // 0x1022c931, register-wide
	n := 2*d + 1
	out := make([]float64, 0, n)
	for j := int64(0); j < n; j++ {
		i := -d + j
		out = append(out, f32(math.Exp(f32(float64(i*i))*expk)*amp))
	}
	return out
}

// GaussSmooth is 0x1022c8f0 — convolve src[0:n] with GaussKernel. Edge handling
// is CLAMP, via a materialised n+2d scratch: d copies of src[0], src, then d
// copies of src[n-1]. Each output is a dot product accumulated at register
// precision and stored once as float32, in the vendor's own unroll-by-four
// association order.
func GaussSmooth(src []float64, n int, sigma, smoothingSizeFactor float64) []float64 {
	d := int(GaussHalfWidth(sigma, smoothingSizeFactor))
	kern := GaussKernel(sigma, smoothingSizeFactor)
	taps := 2*d + 1
	pad := make([]float64, 0, n+2*d)
	if n > 0 {
		for i := 0; i < d; i++ {
			pad = append(pad, f32(src[0]))
		}
		for i := 0; i < n; i++ {
			pad = append(pad, f32(src[i]))
		}
		for i := 0; i < d; i++ {
			pad = append(pad, f32(src[n-1]))
		}
	} else {
		pad = make([]float64, 2*d)
	}
	out := make([]float64, 0, n)
	for b := 0; b < n; b++ {
		acc := 0.0
		w := pad[b : b+taps]
		i := 0
		// 0x1022ca14: unrolled by four, in the vendor's association order.
		for taps-i >= 4 {
			acc = (kern[i+1] * w[i+1]) + ((kern[i] * w[i]) + acc)
			acc = acc + (kern[i+2] * w[i+2])
			acc = acc + (kern[i+3] * w[i+3])
			i += 4
		}
		for i < taps { // 0x1022ca47 tail
			acc = acc + (kern[i] * w[i])
			i++
		}
		out = append(out, f32(acc))
	}
	return out
}

// ---------------------------------------------------------------------------
// 0x1022c3e0 -- peak of the second difference
// ---------------------------------------------------------------------------

// PeakSecondDifference is 0x1022c3e0 — argmax over j in [start, limit] of
// f[j-2] + f[j+2] - 2*f[j]. The candidate is stored to a float32 stack slot
// before the compare, and a candidate replaces the incumbent only when it is
// STRICTLY greater, so ties keep the lower index.
func PeakSecondDifference(f []float64, start, limit int) int {
	d2 := func(j int) float64 {
		return f32((f32(f[j+2]) + f32(f[j-2])) - (f32(f[j]) + f32(f[j])))
	}
	bestIdx := start
	best := d2(start)
	for j := start + 1; j <= limit; j++ {
		cur := d2(j)
		if cur > best {
			best = cur
			bestIdx = j
		}
	}
	return bestIdx
}

// ---------------------------------------------------------------------------
// 0x1022ca80 -- histogram moments, smooth, resample
// ---------------------------------------------------------------------------

// HistResample is what 0x1022ca80 writes back through its two out-pointers.
type HistResample struct {
	InSigma  float64 // *A7 -- results.darkInSigma / .lightInSigma
	OutSigma float64 // *A8 -- results.darkOutSigma / .lightOutSigma
	Out      []int64 // A9, n ints
}

// DoHistResample is 0x1022ca80 — the shared dark/light half of the tone
// analysis. See pakon_cna.hist_resample for the step-by-step derivation; the
// spill points below (which accumulator is float32-rounded on which of the four
// unrolled lanes) are the vendor's and are observable in sigma's last bits.
func DoHistResample(p Params, hist []int64, n int, pivot int64,
	scale, maxContrastGain float64) (HistResample, error) {
	var res HistResample

	// -- 1. moments -------------------------------------------------------
	total := int64(0)
	accA := 0.0 // st0 at the loop head
	accB := 0.0 // the float32 slot [esp+0x14]
	i := 0
	for n-i >= 4 {
		x0, x1, x2, x3 := hist[i], hist[i+1], hist[i+2], hist[i+3]
		total = i32(total + x0 + x1 + x2 + x3)
		ii := int64(i)
		accA = accA + float64(i32(x0*ii))
		accB = accB + float64(i32(i32(x0*ii)*ii))
		accB = accB + float64(i32(i32(x1*(ii+1))*(ii+1)))
		accA = f32(float64(i32(x1*(ii+1))) + accA)
		accA = f32(float64(i32(x2*(ii+2))) + accA)
		accB = f32(float64(i32(i32(x2*(ii+2))*(ii+2))) + accB)
		accA = float64(i32(x3*(ii+3))) + accA
		accB = f32(float64(i32(i32(x3*(ii+3))*(ii+3))) + accB)
		i += 4
	}
	for i < n { // 0x1022cb80 tail
		x := hist[i]
		ii := int64(i)
		total = i32(total + x)
		accA = accA + float64(i32(x*ii))
		accB = f32(float64(i32(i32(x*ii)*ii)) + accB)
		i++
	}

	// -- 2. mean / sigma (0x1022cbb0) -------------------------------------
	// `fst dword [esp+0x18]` stores 1/sum as float32 but does not pop, so the
	// mean is formed with the REGISTER reciprocal and the second moment with
	// the FLOAT32 one.
	fsum := f32(float64(total))
	invReg := kOneF32 / fsum
	invF32 := f32(invReg)
	mean := accA * invReg
	m2 := invF32 * accB
	variance := m2 - mean*mean
	sigma := math.NaN()
	if variance >= 0.0 {
		sigma = math.Sqrt(variance)
	}
	res.InSigma = f32(sigma)

	// -- 3. outSigma (0x1022cbe6) -----------------------------------------
	// The low clamp compares the REGISTER value; the high clamp compares the
	// float32 spill. Both write the float32 slot.
	blended := sigma * p.Blend
	outSigma := f32(blended)
	if !(blended >= p.MinGaussSigma) {
		outSigma = p.MinGaussSigma
	} else if outSigma > p.MaxGaussSigma {
		outSigma = p.MaxGaussSigma
	}

	// -- 4. normalise into a ZERO-padded scratch, smooth, rescale ---------
	// 0x1022cc40 / 0x1022cc59 write ZEROS into the two pads — a different edge
	// policy from GaussSmooth's own internal clamp padding.
	d := int(GaussHalfWidth(outSigma, p.SmoothingSizeFactor))
	npad := n + 2*d
	padded := make([]float64, npad)
	for k := 0; k < n; k++ {
		padded[d+k] = f32(float64(hist[k]) / fsum)
	}
	padded = GaussSmooth(padded, npad, outSigma, p.SmoothingSizeFactor)
	for k := range padded {
		padded[k] = f32(padded[k] * fsum)
	}

	// -- 5. crossing index (0x1022cd6b) -----------------------------------
	below := int64(0)
	if pivot >= 0 {
		for k := int64(0); k <= pivot; k++ {
			below = i32(below + hist[k])
		}
	}
	frac := float64(below) / fsum
	acc := 0.0
	for _, v := range padded {
		acc = acc + v
	}
	target := frac * acc
	cross := -1
	for k, v := range padded {
		target = target - v
		if !(target > 0.0) {
			cross = k
			break
		}
	}
	if cross < 0 {
		// When the walk never crosses, [esp+0x2c] keeps the AnsCnaResults
		// pointer the slot held on entry and fild reads THAT as the index — a
		// genuine vendor quirk with no sane value. Refuse rather than invent.
		return res, fmt.Errorf("%#x: running sum never crossed %v*total; the "+
			"vendor would read the AnsCnaResults pointer out of [esp+0x2c] as "+
			"the index here", VAHistResample, frac)
	}

	// -- 6. resample (0x1022cdef) -----------------------------------------
	sig32 := res.InSigma // fld dword [ecx] -- reloaded
	ratio := x87Div((outSigma*outSigma)+(sig32*sig32), sig32*sig32)
	root := math.Sqrt(ratio)
	var outVal float64
	if sig32 < f32(scale)/f32(maxContrastGain) {
		outVal = sig32 * f32(maxContrastGain) // register precision
	} else {
		outVal = f32(scale)
	}
	res.OutSigma = f32(outVal)
	step := f32(x87Div(sig32, outVal) * root) // fstp dword [esp+0x30]
	cur := float64(cross) - float64(pivot+1)*step
	res.Out = make([]int64, 0, n)
	for k := 0; k < n; k++ {
		cur = cur + step
		j := roundHalfUp(cur)
		if j < 0 {
			j = 0
		} else if j >= int64(npad) {
			j = int64(npad) - 1
		}
		// 0x1022ce98 stores only EAX of _ftol2's edx:eax — see ftol2I32.
		res.Out = append(res.Out, roundHalfUpI32(step*padded[j]))
	}
	return res, nil
}

// ---------------------------------------------------------------------------
// 0x1022d970 -- allocateMemory (sizes only)
// ---------------------------------------------------------------------------

// BufferSizes is 0x1022d970 — the element counts of all 15 working buffers, in
// elements rather than the vendor's byte counts.
func BufferSizes(p Params, nPixels int64) map[string]int64 {
	nBins := p.HistSize
	nBuckets := idiv(nBins, p.BucketSize)
	hw1 := roundHalfUp(f32(p.MaxGaussSigma) * f32(p.SmoothingSizeFactor))
	m := math.Max(p.LaplacianHistSmoothingSigma, p.CoarseHistSmoothingSigma)
	if m < p.ToneScaleSmoothingSigma {
		m = p.ToneScaleSmoothingSigma
	}
	if m < p.MaxGaussSigma {
		m = p.MaxGaussSigma
	}
	hw2 := roundHalfUp(f32(m) * f32(p.SmoothingSizeFactor))
	padded := nBins + 2*hw1
	return map[string]int64{
		"lum_i16":         nPixels,
		"lum_hist_i32":    nBins,
		"lap_i16":         nPixels,
		"edge_hist_i32":   nBins,
		"gauss_pad_f32":   2*hw2 + padded,
		"gauss_kern_f32":  2*hw2 + 1,
		"resample_f32":    padded,
		"scratch_c4_i32":  nBins,
		"bucket_hist_i32": nBuckets,
		"scratch_cc_f32":  nBins,
		"scratch_d0_f32":  nBins,
		"scratch_d4_f32":  nBins,
		"scratch_d8_f32":  nBins,
		"tone_lut_i16":    nBins,
		"_hw1":            hw1,
		"_hw2":            hw2,
	}
}

// ---------------------------------------------------------------------------
// 0x1022ddc0 -- the first half of analyzeImage
// ---------------------------------------------------------------------------

// ThresholdStage is everything 0x1022ddc0 has decided by 0x1022e23e.
type ThresholdStage struct {
	NPixels   int64
	Lum       []int64
	LumHist   []int64
	Lap       []int64
	LapHist   []int64
	Half      int64
	PeakIndex int
	// Threshold is results.threshold (impl+0x98) — the threshold of the last
	// pass that actually ran, published at 0x1022e1e6 BEFORE the sufficiency
	// test, so on the bail-out path it keeps the last TRIED value.
	Threshold        int64
	ReducedThreshold int64
	HasReduced       bool
	MinLapPixels     int64
	EdgeHist         []int64
	NEdge            int64
	// GaveUp is true when the relaxation loop ran out of threshold and
	// 0x1022e21c wrote the identity LUT and returned OK.
	GaveUp  bool
	ToneLUT []int64
}

// LuminancePlane is 0x1022deb5/0x1022df0f — lum = (R+G+B+1+shifts)/3 with x86
// signed /3. The +1 is a literal `inc eax` on the red term, not a rounding of
// the mean. There are TWO copies of this loop and they are not equivalent: when
// the three shifts sum to zero the result is stored raw as int16, otherwise it
// is first clamped to [0, 0xfff].
func LuminancePlane(img Image, p Params) []int64 {
	shift := p.RedShift + p.GreenShift + p.BlueShift
	n := img.Width * img.Height
	out := make([]int64, n)
	if shift != 0 {
		for i := 0; i < n; i++ {
			s := int64(img.Pixels[3*i]) + 1 + int64(img.Pixels[3*i+1]) +
				int64(img.Pixels[3*i+2]) + shift
			v := idiv(s, 3)
			if v < 0 {
				v = 0
			} else if v > kLUTMax {
				v = kLUTMax
			}
			out[i] = i16(v)
		}
		return out
	}
	for i := 0; i < n; i++ {
		s := int64(img.Pixels[3*i]) + 1 + int64(img.Pixels[3*i+1]) +
			int64(img.Pixels[3*i+2])
		out[i] = i16(idiv(s, 3))
	}
	return out
}

// AnalyzeImageThreshold is 0x1022ddc0 from entry to 0x1022e23e — the threshold
// search. If the relaxation loop drives threshold below minPosThreshold the
// function writes an IDENTITY ToneScaleLut and returns OK, which is the
// subsystem's own "this frame has no usable edge structure" answer.
func AnalyzeImageThreshold(img Image, p Params) (*ThresholdStage, error) {
	st := &ThresholdStage{}
	w, h := img.Width, img.Height
	nBins := int(p.HistSize)
	st.NPixels = int64(w) * int64(h)

	st.Lum = LuminancePlane(img, p)

	st.LumHist = make([]int64, nBins)
	interior := func(fn func(idx int)) {
		if h <= 2 || w <= 2 {
			return
		}
		for r := 1; r < h-1; r++ {
			for c := 1; c < w-1; c++ {
				fn(r*w + c)
			}
		}
	}
	var histErr error
	interior(func(idx int) {
		j := st.Lum[idx]
		if j < 0 || j >= int64(nBins) {
			if histErr == nil {
				histErr = fmt.Errorf("%#x: luminance %d is outside [0,%d) and "+
					"the vendor's histogram store is unchecked "+
					"(inc dword [edi + eax*4], 0x1022df80); there is no "+
					"defined value to model", VAAnalyzeImage, j, nBins)
			}
			return
		}
		st.LumHist[j] = i32(st.LumHist[j] + 1)
	})
	if histErr != nil {
		return nil, histErr
	}

	st.Lap = Laplacian(st.Lum, w, h)
	nLap := len(st.Lap)

	half := idiv(int64(nBins), 2)
	st.Half = half
	st.LapHist = make([]int64, nBins)
	lo, hi := i16(-half), i16(int64(nBins)-half-1)
	for _, v := range st.Lap {
		if lo <= v && v <= hi {
			st.LapHist[half+v] = i32(st.LapHist[half+v] + 1)
		}
	}

	lapF := make([]float64, nBins)
	for i, v := range st.LapHist {
		lapF[i] = float64(v)
	}
	smoothed := GaussSmooth(lapF, nBins, p.LaplacianHistSmoothingSigma,
		p.SmoothingSizeFactor)
	st.PeakIndex = PeakSecondDifference(smoothed, int(half)+1, nBins-3)

	threshold := roundHalfUp(f32(float64(int64(st.PeakIndex)-half)) *
		f32(p.ThresholdMultiplier))
	st.MinLapPixels = roundHalfUp(f32(float64(nLap)) * f32(p.MinLapPixelRatio))

	for {
		st.EdgeHist = make([]int64, nBins)
		k := 0
		interior(func(idx int) {
			v := st.Lap[k]
			k++
			if v > threshold || v < -threshold {
				j := st.Lum[idx]
				st.EdgeHist[j] = i32(st.EdgeHist[j] + 1)
			}
		})
		nEdge := int64(0)
		for _, v := range st.EdgeHist {
			nEdge = i32(nEdge + v)
		}
		st.NEdge = nEdge
		st.Threshold = threshold
		if nEdge >= st.MinLapPixels {
			return st, nil
		}
		nxt := i16(roundHalfUp(f32(float64(threshold)) *
			f32(p.ThresholdReductionFactor)))
		if nxt < threshold {
			threshold = nxt
		} else {
			threshold = threshold - 1
		}
		st.ReducedThreshold = threshold
		st.HasReduced = true
		if threshold < p.MinPosThreshold {
			st.GaveUp = true
			st.ToneLUT = make([]int64, nBins)
			for i := 0; i < nBins; i++ {
				st.ToneLUT[i] = i16(int64(i))
			}
			return st, nil
		}
	}
}

// ---------------------------------------------------------------------------
// 0x1022e865 .. 0x1022e9b0 -- elmo detection
// ---------------------------------------------------------------------------

// ElmoResult is AnsCnaResults+0x58 / +0x5c — what the shell reads at 0x100fc084.
type ElmoResult struct {
	ElmoPercent  float64
	BElmoOccured bool
	Count        int64
	Ran          bool
}

// ElmoDetect is 0x1022e865..0x1022e9a9 — cna's half of the fork
// analyzeAutoTone takes at 0x100fc5cd. Two gates, both of which leave
// elmoPercent at its -1.0f seed when they decline.
func ElmoDetect(p Params, img Image, lightInSigma, lightOutSigma float64) ElmoResult {
	r := ElmoResult{ElmoPercent: -1.0}
	if !(lightInSigma > lightOutSigma) { // 0x1022e88a
		return r
	}
	if !(p.ElmoCriticalPercent < kHundredF32) { // 0x1022e8a1
		return r
	}
	r.Ran = true
	sat2 := i32(p.ElmoSatThreshold * p.ElmoSatThreshold)
	n := img.Width * img.Height
	count := int64(0)
	for i := 0; i < n; i++ {
		red := int64(img.Pixels[3*i])
		grn := int64(img.Pixels[3*i+1])
		blu := int64(img.Pixels[3*i+2])
		lum := idiv(red+grn+blu+1, 3)
		// 0x1022e91d / 0x1022e932 are the compiler's signed-division idioms,
		// truncating toward zero, not arithmetic shifts.
		u := idiv(2*grn+2-red-blu, 4)
		v := idiv(blu-red+1, 2)
		if !(i16(red) > p.ElmoRedLimit || i16(grn) > p.ElmoGreenLimit ||
			i16(blu) > p.ElmoBlueLimit) {
			continue
		}
		if i16(lum) >= p.ElmoNeutralLimit {
			continue
		}
		if i32(i16(u)*i16(u))+i32(i16(v)*i16(v)) > sat2 {
			count++
		}
	}
	r.Count = count
	r.ElmoPercent = f32(float64(count) * kHundredF32 / float64(n))
	r.BElmoOccured = r.ElmoPercent > p.ElmoCriticalPercent
	return r
}

// ---------------------------------------------------------------------------
// 0x1022c520 / 0x1022c630 -- the two halves of the contrast map
// ---------------------------------------------------------------------------

// contrastMap is 0x1022c630 (ascending) and 0x1022c520 (descending), in place.
//
// THE LOW-CLAMP TEST'S NaN BEHAVIOUR (docs/74 §30): the real compare is
// `fcom [lo]; fnstsw ax; test ah,5; jp`, which for an UNORDERED compare also
// jumps — so the DLL SKIPS the clamp for a NaN ratio and leaves it NaN. Go's
// `ratio < lo` is false for NaN, which is the same branch. (The Python
// reference had to be written as `if ratio < lo` for exactly this reason; a
// `not (ratio >= lo)` spelling launders NaN into lo and is wrong.)
func contrastMap(p Params, src, ratioDen, out []float64, pivot int64,
	idx int64, limit int, ascending bool) {
	out[pivot] = f32(float64(pivot))
	den := ratioDen[idx]
	ratio := f32(src[pivot]) / f32(den) // register precision
	acc := f32(float64(idx))
	delta := idx - pivot
	lo, hi := p.LowClamp, p.HighClamp

	step := func(i int) {
		if ratio < lo { // 0x1022c57b / 0x1022c68d
			ratio = lo
		} else if ratio > hi {
			ratio = hi
		}
		if ascending {
			acc = f32(acc + ratio)
		} else {
			acc = f32(acc - ratio)
		}
		k := roundHalfUp(acc)
		if k < 0 {
			k = 0
		} else if k >= int64(limit) {
			k = int64(limit) - 1
		}
		j := k - delta
		if j < 0 {
			j = 0
		} else if j >= int64(limit) {
			j = int64(limit) - 1
		}
		out[i] = f32(float64(j))
		den = ratioDen[k]
		if den == 0.0 {
			ratio = kOneF32
		} else {
			ratio = f32(src[i]) / f32(den)
		}
	}

	if ascending {
		for i := int(pivot) + 1; i < limit; i++ {
			step(i)
		}
	} else {
		for i := int(pivot) - 1; i >= 0; i-- {
			step(i)
		}
	}
}

// ---------------------------------------------------------------------------
// 0x1022c740 -- bucket curve -> int16 ToneScaleLut
// ---------------------------------------------------------------------------

// BuildToneLUT is 0x1022c740 — expand a per-bucket curve into a per-bin int16
// LUT. Within a bucket the accumulator starts at curve[j]*step and advances by
// curve[j+1]-curve[j] per bin — NOT by that difference scaled to bins, which is
// what a linear interpolation would do. That asymmetry is the vendor's.
func BuildToneLUT(curve []float64, nBuckets, nBins int) []int64 {
	lut := make([]int64, nBins)
	step := idiv(int64(nBins), int64(nBuckets))
	half := idiv(step, 2)
	pos := half
	for j := 0; j < nBuckets-1; j++ { // 0x1022c774 .. 0x1022c7da
		delta := f32(f32(curve[j+1]) - f32(curve[j]))
		acc := f32(curve[j]) * float64(step) // register precision
		lut[pos] = i16(roundHalfUp(acc))
		pos++
		if step > 1 {
			for k := int64(0); k < step-1; k++ { // 0x1022c7b0
				acc = acc + delta
				lut[pos] = i16(roundHalfUp(acc))
				pos++
			}
		}
	}

	// -- low tail (0x1022c7e2) --------------------------------------------
	i := half - 1
	slope := f32(float64(lut[i+2]) - float64(lut[i+1]))
	acc := float64(lut[i+1])
	for i >= 0 {
		acc = acc - slope
		if acc < 0.0 { // 0x1022c81c
			for i >= 0 { // 0x1022c880 zero-fill
				lut[i] = 0
				i--
			}
			break
		}
		lut[i] = i16(roundHalfUp(acc))
		i--
	}

	// -- high tail (0x1022c838) -------------------------------------------
	e := int64(nBins) - idiv(step+1, 2)
	slope = f32(float64(lut[e-1]) - float64(lut[e-2]))
	acc = float64(lut[e-1])
	for i = e; i < int64(nBins); i++ {
		acc = acc + slope
		if acc > kToneMaxF32 { // 0x1022c894
			for k := i; k < int64(nBins); k++ { // 0x1022c8d2 rep stosd 0xfff
				lut[k] = kLUTMax
			}
			break
		}
		lut[i] = i16(roundHalfUp(acc))
	}
	return lut
}

// ---------------------------------------------------------------------------
// 0x1022ddc0 -- the whole per-frame analysis
// ---------------------------------------------------------------------------

// Analysis is everything 0x1022ddc0 leaves in AnsCnaResults, plus its workings.
type Analysis struct {
	ThresholdStage *ThresholdStage
	Pivot          int64
	PivotBucket    int64
	NBuckets       int64
	Percentile     float64
	BucketHist     []int64
	Dark           *HistResample
	Light          *HistResample
	CrossDark      int64
	CrossLight     int64
	Curve          []float64
	Elmo           ElmoResult
	ToneLUT        []int64
	NPixels        int64
	NEdge          int64
	Threshold      int64
}

// AnalyzeImage is 0x1022ddc0 — AnsCnaCapabilityImpl's whole per-frame analysis.
func AnalyzeImage(img Image, p Params) (*Analysis, error) {
	a := &Analysis{Elmo: ElmoResult{ElmoPercent: -1.0}}
	st, err := AnalyzeImageThreshold(img, p)
	if err != nil {
		return nil, err
	}
	a.ThresholdStage = st
	a.NPixels = st.NPixels
	a.NEdge = st.NEdge
	a.Threshold = st.Threshold
	nBins := int(p.HistSize)
	if st.GaveUp {
		a.ToneLUT = append([]int64(nil), st.ToneLUT...)
		return a, nil
	}

	// -- 1. pivot percentile (0x1022e23e) ---------------------------------
	// The ORIGINAL params.pivot is kept in a separate slot (E-0x04) and is what
	// step 8 normalises against; the re-derived pivot is used only for the
	// bucketing.
	pivotOrig := p.Pivot
	pivot := pivotOrig
	below := int64(0)
	if pivotOrig >= 0 {
		for i := int64(0); i <= pivotOrig; i++ {
			below = i32(below + st.EdgeHist[i])
		}
	}
	nEdgeF := float64(st.NEdge)
	pct := f32(float64(below) / nEdgeF)
	if !(pct >= p.MinPivotPercentile) || !(pct <= p.MaxPivotPercentile) {
		if !(pct >= p.MinPivotPercentile) {
			pct = p.MinPivotPercentile
		} else {
			pct = p.MaxPivotPercentile
		}
		want := roundHalfUp(nEdgeF * pct)
		c := int64(0)
		for i := 0; i < nBins; i++ {
			want -= st.EdgeHist[i]
			if want <= 0 {
				pivot = c
				break
			}
			c++
		}
	}
	a.Pivot = pivot
	a.Percentile = pct

	// -- 2. bucketing (0x1022e2e8) ----------------------------------------
	nBuckets := int(idiv(int64(nBins), p.BucketSize))
	a.NBuckets = int64(nBuckets)
	bucket := make([]int64, nBuckets)
	k := 0
	for j := 0; j < nBuckets; j++ {
		s := int64(0)
		for c := int64(0); c < p.BucketSize; c++ {
			s = i32(s + st.EdgeHist[k])
			k++
		}
		bucket[j] = s
	}
	pivotBucket := idiv(pivot, p.BucketSize)
	a.PivotBucket = pivotBucket
	bucketF := make([]float64, nBuckets)
	for i, v := range bucket {
		bucketF[i] = float64(v)
	}
	sm := GaussSmooth(bucketF, nBuckets, p.CoarseHistSmoothingSigma,
		p.SmoothingSizeFactor)
	for i, v := range sm {
		bucket[i] = roundHalfUp(v)
	}
	a.BucketHist = append([]int64(nil), bucket...)

	curve := make([]float64, nBuckets)
	src := make([]float64, nBuckets)
	den := make([]float64, nBuckets)

	// half is one of the two symmetric halves (0x1022e402 / 0x1022e634). It
	// mutates the shared src/den scratch, exactly as the vendor's own two
	// buffers are reused between the halves.
	half := func(scaleNum, gain float64) (*HistResample, int64, error) {
		r, err := DoHistResample(p, bucket, nBuckets, pivotBucket,
			f32(f32(scaleNum)/float64(p.BucketSize)), gain)
		if err != nil {
			return nil, 0, err
		}
		tot := int64(0)
		for _, v := range r.Out {
			tot = i32(tot + v)
		}
		ftot := f32(float64(tot))
		want := roundHalfUp(float64(tot) * pct)
		cross := int64(-1)
		for i := 0; i < nBins; i++ {
			if i >= nBuckets {
				// 0x1022e473's real bound is params.histSize, so the vendor
				// genuinely walks past bucket nBuckets into memory this port
				// has no buffer for. Not expected on real data since
				// DoHistResample's int32 store fix — see pakon_cna.py's own
				// note — so this stays a loud failure, not an invented value.
				return nil, 0, fmt.Errorf("%#x: the crossing walk ran past "+
					"bucket %d into the uninitialised tail of the resample "+
					"scratch; the vendor reads it, but there is no defined "+
					"value to model", VAAnalyzeImage, nBuckets)
			}
			want -= r.Out[i]
			if want <= 0 {
				cross = int64(i)
				break
			}
		}
		if cross < 0 {
			cross = tot // the slot's prior value -- see 0x1022e442
		}
		sumBucket := int64(0)
		for _, v := range bucket {
			sumBucket = i32(sumBucket + v)
		}
		fsb := float64(sumBucket)
		for i := 0; i < nBuckets; i++ {
			src[i] = f32(x87Div(float64(bucket[i]), fsb))
			den[i] = f32(x87Div(float64(r.Out[i]), ftot))
		}
		return &r, cross, nil
	}

	// -- 3/4. dark half ---------------------------------------------------
	dark, crossDark, err := half(p.DarkScale, p.DarkMaxContrastGain)
	if err != nil {
		return nil, err
	}
	a.Dark, a.CrossDark = dark, crossDark
	contrastMap(p, src, den, curve, pivotBucket, crossDark, nBuckets, false)

	// -- 5. light half ----------------------------------------------------
	light, crossLight, err := half(p.LightScale, p.LightMaxContrastGain)
	if err != nil {
		return nil, err
	}
	a.Light, a.CrossLight = light, crossLight
	contrastMap(p, src, den, curve, pivotBucket, crossLight, nBuckets, true)
	a.Curve = append([]float64(nil), curve...)

	// -- 6. elmo ----------------------------------------------------------
	a.Elmo = ElmoDetect(p, img, a.Light.InSigma, a.Light.OutSigma)

	// -- 7. smooth and expand ---------------------------------------------
	smoothed := GaussSmooth(curve, nBuckets, p.ToneScaleSmoothingSigma,
		p.SmoothingSizeFactor)
	lut := BuildToneLUT(smoothed, nBuckets, nBins)

	// -- 8. normalise at the ORIGINAL pivot (0x1022e9e3) ------------------
	delta := pivotOrig - lut[pivotOrig]
	for i := 0; i < nBins; i++ {
		v := lut[i] + delta
		if v < 0 {
			v = 0
		} else if v > kLUTMax {
			v = kLUTMax
		}
		lut[i] = i16(v)
	}
	a.ToneLUT = lut
	return a, nil
}

// ---------------------------------------------------------------------------
// 0x1022ceb0 -- the AnsCnaParams validator
// ---------------------------------------------------------------------------

// ValidateParams is 0x1022ceb0 — returns the failing field index, or -1 if
// valid. The field numbers are DPI key positions, not the order of the checks,
// so a gap in this table is not a missing check.
func ValidateParams(p Params) int {
	if !(p.HistSize > kLUTMax) { // 0x1022ceb0
		return 4
	}
	if p.BucketSize < 1 { // 0x1022cec6
		return 5
	}
	if idiv(p.HistSize, p.BucketSize)*p.BucketSize != p.HistSize {
		return 5 // 0x1022cee2
	}
	if !(p.LowClamp > 0.0) { // 0x1022cef3
		return 6
	}
	if !(p.HighClamp > p.LowClamp) { // 0x1022cf0c
		return 7
	}
	if !(p.Blend >= kBlendMin) || p.Blend > kBlendMax { // 0x1022cf28
		return 8
	}
	if !(p.MinPivotPercentile >= 0.0) { // 0x1022cf50
		return 0xA
	}
	if !(p.MaxPivotPercentile > p.MinPivotPercentile) ||
		p.MaxPivotPercentile > kOneF64 { // 0x1022cf69
		return 0xB
	}
	if !(p.ThresholdMultiplier > 0.0) { // 0x1022cf91
		return 0xC
	}
	if !(p.ThresholdReductionFactor > 0.0) ||
		p.ThresholdReductionFactor >= kOneF64 { // 0x1022cfad
		return 0xD
	}
	if i16(p.MinPosThreshold) < kMinPosThr { // 0x1022cfce
		return 0xE
	}
	if !(p.MinLapPixelRatio >= 0.0) || p.MinLapPixelRatio > kOneF64 {
		return 0xF // 0x1022cfee
	}
	if !(p.SmoothingSizeFactor >= kSizeFactMin) ||
		p.SmoothingSizeFactor > kSizeFactMax { // 0x1022d016
		return 0x10
	}
	sigmas := []struct {
		idx int
		val float64
	}{
		{0x11, p.LaplacianHistSmoothingSigma}, // 0x1022d03e
		{0x12, p.CoarseHistSmoothingSigma},    // 0x1022d066
		{0x13, p.ToneScaleSmoothingSigma},     // 0x1022d08e
	}
	for _, s := range sigmas {
		if !(s.val >= kSigmaMin) || s.val > kSigmaMax {
			return s.idx
		}
	}
	limits := []struct {
		idx int
		val int64
	}{
		{0x1A, p.ElmoNeutralLimit}, // 0x1022d0ab
		{0x1B, p.ElmoRedLimit},
		{0x1C, p.ElmoGreenLimit},
		{0x1D, p.ElmoBlueLimit},
		{0x1E, p.ElmoSatThreshold},
	}
	for _, l := range limits {
		if i16(l.val) < 0 || i16(l.val) > kLUTMax {
			return l.idx
		}
	}
	if p.ElmoAggressiveness != 0 && p.ElmoAggressiveness != 1 { // 0x1022d0fd
		return 0x20
	}
	return -1
}

// ---------------------------------------------------------------------------
// 0x1022ea50 -- AnsCnaCapabilityImpl::analyze
// ---------------------------------------------------------------------------

// BadFieldError is what 0x1022eada throws.
type BadFieldError struct{ Field int }

func (e *BadFieldError) Error() string {
	return fmt.Sprintf("Bad field(#%d) in AnsCnaParams structure! "+
		`[AnsCnaCapabilityImpl::analyze, \Atc\ansel\src\libCna.ansel\`+
		"AnsCnaCapabilityImpl.cpp:1211] (code 105)", e.Field)
}

// Analyze is 0x1022ea50 — AnsCnaCapabilityImpl::analyze: validate the params,
// then run the analysis.
func Analyze(img Image, p Params) (*Analysis, error) {
	if bad := ValidateParams(p); bad >= 0 {
		return nil, &BadFieldError{Field: bad}
	}
	return AnalyzeImage(img, p)
}

// Results is a host-side AnsCnaResults plus the arrays its pointers stand for.
type Results struct {
	NPixels       int64
	Threshold     int64
	NEdge         int64
	DarkInSigma   float64
	LightInSigma  float64
	DarkOutSigma  float64
	LightOutSigma float64
	ElmoPercent   float64
	BElmoOccured  bool
	LuminanceHist []int64
	EdgeHist      []int64
	ToneScaleLut  []int64
	Analysis      *Analysis
}

// AnalyzeToResults is Analyze plus the 0x101320b0 getter, as the shell consumes
// them: ToneScaleLut is AnsCnaResults+0x54, which is what 0x100fbfc1 threads
// into ctx+0x64d0.
func AnalyzeToResults(img Image, p Params) (*Results, error) {
	a, err := Analyze(img, p)
	if err != nil {
		return nil, err
	}
	r := &Results{
		NPixels: a.NPixels, Threshold: a.Threshold, NEdge: a.NEdge,
		DarkInSigma: -1.0, LightInSigma: -1.0,
		DarkOutSigma: -1.0, LightOutSigma: -1.0,
		ElmoPercent:  a.Elmo.ElmoPercent,
		BElmoOccured: a.Elmo.BElmoOccured,
		Analysis:     a,
	}
	if a.Dark != nil {
		r.DarkInSigma, r.DarkOutSigma = a.Dark.InSigma, a.Dark.OutSigma
	}
	if a.Light != nil {
		r.LightInSigma, r.LightOutSigma = a.Light.InSigma, a.Light.OutSigma
	}
	r.LuminanceHist = append([]int64(nil), a.ThresholdStage.LumHist...)
	r.EdgeHist = append([]int64(nil), a.ThresholdStage.EdgeHist...)
	r.ToneScaleLut = append([]int64(nil), a.ToneLUT...)
	return r, nil
}
