// Package ansdra is the Go transcription of
// tools/ansel/python-pipeline/pakon_dra.py — AnsDraCapabilityImpl
// (PakonIMAu.dll 0x1022af20 / 0x1022b530), the SECOND of the six subsystems in
// ColorNegativePath::analyzeAutoTone's ANALYSIS half.
//
// WHAT THIS IS AND IS NOT
// =======================
// A line-for-line transcription of the Python module, which is itself
// Unicorn-verified against the real DLL (pakon_dra_golden.py). It is
// bit-exactness against the vendor BY TRANSITIVITY, and only to the extent
// tools/test_dra_port.py demonstrates Go == Python on real data. Nothing here
// re-derives any vendor arithmetic; every VA in a comment is carried over from
// the Python source.
//
// WHAT DRA ACTUALLY DOES TO PIXELS (from pakon_dra.py's generateLut docstring,
// asserted there against the real DLL, not reasoned out of the port): with the
// shipped ansel-dra-default-default.dpi and the shipped identity Normal .ttc
// pair, a frame whose [effMin, effMax] lies inside [paperMin, paperMax] gets an
// EXACTLY identity DraLut. Only a range that spills outside the paper range is
// touched, and then the offending side is compressed inward pivoting on the
// fixed point. There is no expansion branch: dra is a one-way clamp-and-
// compress, not an auto-level.
//
// TWO OVERLOADS, and the live one is the second:
//
//	0x1022af20  analyze(image)        computes its own luminance histogram,
//	                                  never composes. Reached only when cna
//	                                  produced no tone object.
//	0x1022b530  analyze(hists, tone)   receives cna's LuminanceHist/EdgeHist,
//	                                  remaps them through the incoming tone LUT
//	                                  inside generateLut, and composes the
//	                                  finished curve onto it afterward. This is
//	                                  the shipped colour-negative path.
//
// lighting is 0 (Normal) on every real negative: "lighting" is never in
// CN-Enhanced's declared capability list, and a find() miss is defined to
// yield 0 — Unicorn-verified in pakon_dra_golden.check_lighting.
//
// FLOATING POINT: as in package anscna, register values are float64 and f32()
// is applied only where the DLL does an fstp dword.
package ansdra

import (
	"fmt"
	"math"
)

// ---------------------------------------------------------------------------
// addresses (carried from pakon_dra.py; not re-derived here)
// ---------------------------------------------------------------------------

const (
	VAAnalyzeImage   = 0x1022AF20 // analyze(image)
	VAAnalyzeHist    = 0x1022B530 // analyze(hists, tone)
	VAGenerateLut    = 0x1022AB50
	VAKeepMidPtLut   = 0x102290B0
	VARebin          = 0x10228E00
	VACumBounds      = 0x10228BC0
	VAEffBounds      = 0x10228CD0
	VAAllocBuffers   = 0x1022A820
	VAValidateParams = 0x10228E40
	VAParseDpi       = 0x102283A0
	VATtcSlopeLeaf   = 0x10227C60
)

const (
	// f32Percent is 0x1059f5f0, the 1/100 in 0x10228bc0. It is the float32
	// nearest 0.01, not 0.01 — using the exact decimal moves the thresholds.
	f32Percent = 0.009999999776482582
	// f64Half is 0x10574f40, the round-to-nearest bias.
	f64Half = 0.5
)

// Lighting values. Everything that is not 1 or 2 — including the 0 a
// find("lighting") miss produces — falls through to the Normal pair.
const (
	LightingNormal   = 0
	LightingBacklit  = 1
	LightingFrontlit = 2
)

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

func f32(v float64) float64 { return float64(float32(v)) }

func s16(v int64) int64 { return int64(int16(uint16(uint64(v)))) }

func s32(v int64) int64 { return int64(int32(uint32(uint64(v)))) }

// idiv is x86 idiv — truncation toward zero, not Go's floor (Go's / already
// truncates toward zero for signed ints, but the name records the intent).
func idiv(a, b int64) int64 {
	q := absI(a) / absI(b)
	if (a < 0) != (b < 0) {
		return -q
	}
	return q
}

func absI(a int64) int64 {
	if a < 0 {
		return -a
	}
	return a
}

// ftolRound is `fadd 0.5` then 0x104ffe44 (__ftol) — truncate AFTER biasing.
// Not round(): the DLL adds the 0x10574f40 0.5 in double precision and then
// truncates toward zero, so negatives bias the other way.
//
// The Python reference is `int(x + 0.5)`, which is arbitrary-precision. Go has
// no such type; a magnitude that does not fit an int64 saturates instead, and
// every consumer in this file narrows to int16 immediately afterward, so the
// distinction is unreachable with real histogram-scale inputs.
func ftolRound(x float64) int64 {
	v := x + f64Half
	if math.IsNaN(v) {
		return math.MinInt64 // the masked-invalid "integer indefinite"
	}
	t := math.Trunc(v)
	if t >= 9223372036854775808.0 {
		return math.MaxInt64
	}
	if t <= -9223372036854775808.0 {
		return math.MinInt64
	}
	return int64(t)
}

// Error is what 0x1001ed90 raises from inside dra.
type Error struct{ Msg string }

func (e *Error) Error() string { return e.Msg }

// ---------------------------------------------------------------------------
// the ported leaves
// ---------------------------------------------------------------------------

// LumHistogram is variant A's own luminance histogram, 0x1022b191..0x1022b1d4.
//
// The bin is (R + G + B + 1) / 3 where the +1 is the literal `inc ecx` at
// 0x1022b1ae, the divide is the 0x55555556 magic-multiply (signed truncation
// toward zero, NOT floor), and the quotient is narrowed through `movsx edx, cx`
// at 0x1022b1c4 before indexing — a 16-bit wrap this port reproduces.
func LumHistogram(pixels []int16, nPixels, nBins int) ([]int64, error) {
	hist := make([]int64, nBins)
	for i := 0; i < nPixels; i++ {
		r := int64(pixels[3*i])
		g := int64(pixels[3*i+1])
		b := int64(pixels[3*i+2])
		idx := s16(idiv(r+g+b+1, 3))
		if idx < 0 || idx >= int64(nBins) {
			return nil, fmt.Errorf("%#x: luminance bin %d is outside [0,%d) "+
				"and the vendor's store is unchecked; there is no defined "+
				"value to model", VAAnalyzeImage, idx, nBins)
		}
		hist[idx]++
	}
	return hist, nil
}

// ComposeTone is variant B's compose block, 0x1022bb0f..0x1022bb50:
// memcpy(scratch, draLut, n*2) then draLut[i] = scratch[toneLut[i]], i.e.
// out = draCurve o toneLut. Variant A has no equivalent block — this is the
// single behavioural difference between the two overloads.
func ComposeTone(draLut, toneLut []int64, n int) ([]int64, error) {
	scratch := append([]int64(nil), draLut...)
	out := append([]int64(nil), draLut...)
	for i := 0; i < n; i++ {
		idx := s16(toneLut[i])
		if idx < 0 || idx >= int64(len(scratch)) {
			return nil, fmt.Errorf("%#x: compose index %d is outside the "+
				"%d-entry curve; the vendor's movsx-widened load is unchecked",
				VAAnalyzeHist, idx, len(scratch))
		}
		out[i] = scratch[idx]
	}
	return out, nil
}

// Rebin is 0x10228e00 — sum every binFactor small bins into a large bin.
// A binFactor of 1 or less short-circuits the inner loop (0x10228e15).
func Rebin(small []int64, nSmall, binFactor int) []int64 {
	nLarge := idiv(int64(nSmall), int64(binFactor))
	out := make([]int64, 0, maxInt(int(nLarge), 0))
	src := 0
	for i := int64(0); i < nLarge; i++ {
		acc := small[src]
		src++
		if binFactor > 1 {
			for k := 1; k < binFactor; k++ {
				acc = s32(acc + small[src])
				src++
			}
		}
		out = append(out, s32(acc))
	}
	return out
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

// CumBounds is 0x10228bc0 — cumulative-percentile min/max, in small-bin units.
//
// Four thresholds are formed as ftol(total * p * 0.01 + 0.5). The min scan
// walks the cumulative histogram up to the first bin at or above the 1st
// threshold, then walks BACK while any of the three trailing raw large-bin
// counts still exceeds the 2nd; the max scan is its mirror. Both indices are
// finally multiplied by binFactor to return to small-bin units.
func CumBounds(cumHist, largeHist []int64, nLarge int, total int64,
	p Params) (int64, int64) {
	t := float64(total)
	a := ftolRound(t * p.StartingMinCumPoint * f32Percent)
	b := ftolRound(t * p.CumPctBelowMin * f32Percent)
	c := ftolRound(t * p.StartingMaxCumPoint * f32Percent)
	d := ftolRound(t * p.CumPctAboveMax * f32Percent)
	binFactor := p.BinFactor

	// --- min side, 0x10228c27..0x10228c5d ---------------------------------
	ecx := 0
	if cumHist[0] < a {
		for {
			ecx++
			if cumHist[ecx] >= a {
				break
			}
		}
		for ecx > 2 {
			if largeHist[ecx] > b || largeHist[ecx-1] > b ||
				largeHist[ecx-2] > b {
				ecx--
			} else {
				break
			}
		}
	}
	lo := s16(binFactor * int64(ecx))

	// --- max side, 0x10228c70..0x10228cb2 ---------------------------------
	ecx = nLarge - 1
	if cumHist[nLarge-1] > c {
		for {
			ecx--
			if cumHist[ecx] <= c {
				break
			}
		}
	}
	limit := nLarge - 3
	for ecx < limit {
		if largeHist[ecx] > d || largeHist[ecx-1] > d ||
			largeHist[ecx-2] > d {
			ecx++
		} else {
			break
		}
	}
	hi := s16(binFactor * int64(ecx))
	return lo, hi
}

// EffBounds is 0x10228cd0 — the lum/edge bounds -> the effective bounds.
//
// NOTE the min/max asymmetry, confirmed by Unicorn (not assumed): for the MIN
// blend, whichever of (a, b) is SMALLER keeps its own weight and paperMin
// borrows the other weight (0x10228d59..0x10228d7f); for the MAX blend it is
// the LARGER of (a, b) that keeps its own weight (0x10228db9..0x10228ddf).
func EffBounds(lumMin, lumMax, edgeMin, edgeMax, paperMin, paperMax int64,
	lumWeighting, edgeWeighting float64, doAverage bool) (int64, int64) {
	lumMin, lumMax = s16(lumMin), s16(lumMax)
	edgeMin, edgeMax = s16(edgeMin), s16(edgeMax)
	paperMin, paperMax = s16(paperMin), s16(paperMax)

	if !doAverage {
		effMin := maxI(minI(lumMin, edgeMin), paperMin)
		effMax := minI(maxI(lumMax, edgeMax), paperMax)
		return s16(effMin), s16(effMax)
	}

	blend := func(a, b, p int64, largerKeepsOwn bool) int64 {
		var r float64
		switch {
		case (a-p)*(b-p) >= 0:
			r = float64(a)*lumWeighting + float64(b)*edgeWeighting
		case a < b:
			if largerKeepsOwn {
				r = float64(b)*edgeWeighting + float64(p)*lumWeighting
			} else {
				r = float64(a)*lumWeighting + float64(p)*edgeWeighting
			}
		default:
			if largerKeepsOwn {
				r = float64(a)*lumWeighting + float64(p)*edgeWeighting
			} else {
				r = float64(b)*edgeWeighting + float64(p)*lumWeighting
			}
		}
		return s16(ftolRound(r))
	}

	effMin := blend(lumMin, edgeMin, paperMin, false)
	effMax := blend(lumMax, edgeMax, paperMax, true)
	return effMin, effMax
}

func maxI(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}

func minI(a, b int64) int64 {
	if a < b {
		return a
	}
	return b
}

// KeepMidPtLut is 0x102290b0 — the curve-construction body of keepMidPtLut.
// Three regions: a high side above highFixedPoint, a low side below
// lowFixedPoint, and the [lowFixedPoint, highFixedPoint] midpoint band, which
// is filled with the IDENTITY unconditionally (0x1022938a/0x1022938e is a
// fallthrough, not an "else" of the high loop). That is what the function's
// name means: the midpoint is kept as-is.
func KeepMidPtLut(lighting int64, low, high Ttc, maxValue, lowFixedPoint,
	highFixedPoint, paperMin, paperMax int64, flashFraction float64,
	effMin, effMax int64) []int64 {
	maxValue = s16(maxValue)
	lowFP := s16(lowFixedPoint)
	highFP := s16(highFixedPoint)
	paperMin = s16(paperMin)
	paperMax = s16(paperMax)
	effMin = s16(effMin)
	effMax = s16(effMax)

	// +1 slack: the boundary write can land on esi == maxValue+1 in edge
	// cases; sliced back to maxValue+1 entries on return.
	out := make([]int64, maxValue+2)

	clamp0 := func(v int64) int64 {
		if v >= 0 {
			return v
		}
		return 0
	}

	// search is the linear scan + clamp/interpolate, 0x102292c4..0x1022933a
	// (and its low-side mirror 0x102293e6..0x1022945a).
	search := func(curve Ttc, t float64) float64 {
		n := len(curve.X)
		if n == 0 {
			return 0.0
		}
		if t < curve.X[0] {
			return curve.Y[0]
		}
		if t > curve.X[n-1] {
			return curve.Y[n-1]
		}
		if n <= 1 {
			return curve.Y[0]
		}
		for i := 1; i < n; i++ {
			if !(t < curve.X[i-1]) && t <= curve.X[i] {
				return curve.Y[i-1] + curve.Slope[i-1]*(t-curve.X[i-1])
			}
		}
		return curve.Y[n-1]
	}

	// ---- high side, 0x1022920a..0x10229384 --------------------------------
	hiGapBase := s32(effMax - highFP)
	effMaxAdj, paperMaxAdj := effMax, paperMax
	denom := float64(hiGapBase)
	// 0x10229232: when effMax <= paperMax (no clamp needed), S(0x40) — the
	// multiplier the final fmul uses — stays effMax-highFP, i.e. IDENTICAL to
	// the fraction's own denominator. Only in the clamp-needed branch does it
	// become paperMax(Adj)-highFP.
	hiGap := hiGapBase
	hiRebase := effMax
	if effMax > paperMax {
		adj := ftolRound(float64(hiGapBase) * flashFraction)
		if lighting == LightingFrontlit {
			effMaxAdj = s16(s32(effMax - adj))
			paperMaxAdj = s16(s32(paperMax - adj))
			denom = f32(float64(hiGapBase) - float64(adj))
		}
		hiGap = s32(paperMaxAdj - highFP)
		hiRebase = paperMaxAdj
	}
	hiBound := effMaxAdj

	// twoSidedClamp is 0x1022935a..0x10229384 (high) / 0x10229473..0x102294a5
	// (low): a plain two-sided clamp to [0, maxValue].
	twoSidedClamp := func(val int64) int64 {
		if val > maxValue {
			return maxValue
		}
		return clamp0(val)
	}

	// The loop runs esi from highFixedPoint+1 to maxValue INCLUSIVE. Inside
	// each iteration a SECOND check (0x102292b0) switches from curve
	// interpolation to a plain linear extrapolation once esi reaches hiBound —
	// a per-iteration branch, not a one-off boundary write.
	if idx0 := highFP + 1; idx0 <= maxValue {
		num := int64(1)
		for esi := idx0; esi <= maxValue; esi++ {
			var val int64
			if esi < hiBound {
				t := 0.0
				if denom != 0 {
					t = f32(float64(num) / denom)
				}
				y := search(high, t)
				val = ftolRound(y*float64(hiGap) + float64(highFP))
			} else {
				val = esi - effMaxAdj + hiRebase
			}
			out[esi] = s16(twoSidedClamp(s16(val)))
			num++
		}
	}

	if lowFP <= highFP {
		for v := lowFP; v <= highFP; v++ {
			out[v] = s16(v)
		}
	}

	// ---- low side, 0x102293ad..0x102294b7 ---------------------------------
	// loGap uses max(effMin, paperMin) for the FINAL rebase but the fraction's
	// own denominator/numerator use plain effMin, unclamped by paperMin — an
	// asymmetry with the high side's own adj-vs-unadjusted split, confirmed by
	// the raw esp offsets, not assumed.
	loGap := s32(lowFP - maxI(effMin, paperMin))
	denomLo := f32(float64(s32(lowFP - effMin)))
	for esi := lowFP - 1; esi >= 0; esi-- {
		var newv int64
		if esi >= effMin {
			num := s32(esi - effMin)
			t := 0.0
			if denomLo != 0 {
				t = f32(float64(num) / denomLo)
			}
			y := search(low, t)
			newv = s16(ftolRound(y*float64(loGap) + float64(maxI(effMin, paperMin))))
		} else {
			// 0x10229480 — below effMin: stop interpolating, ramp the
			// already-written neighbour above down by 1 per step (a fresh
			// re-read of outLut[esi+1], not a cached register).
			var neighbour int64
			if esi+1 <= maxValue {
				neighbour = out[esi+1]
			}
			newv = s16(neighbour - 1)
		}
		out[esi] = s16(twoSidedClamp(newv))
	}

	return out[:maxValue+1]
}

// ---------------------------------------------------------------------------
// validate_params — 0x10228e40
// ---------------------------------------------------------------------------

// Bad-parameter indices. Codes 5, 7, 9 and 11-13 are never produced — gaps in
// the DLL's own numbering, not a port omission.
const (
	BadMaxValue        = 1
	BadLowFP           = 2
	BadHighFP          = 3
	BadPaper           = 4
	BadSlope           = 6
	BadBinFactor       = 8
	BadWeights         = 10
	BadFlashFraction   = 14
	BadBacklitFraction = 15
	BadStartingMinCum  = 16
	BadCumBelowMin     = 17
	BadStartingMaxCum  = 18
	BadCumAboveMax     = 19
)

// ValidateParams is 0x10228e40 — 0 if valid, else the 1-based bad-parameter
// index. All bounds are inclusive on both ends (empirically confirmed against
// the DLL, not hand-decoded from the x87 comparison bytes).
func ValidateParams(p Params) int {
	maxValue := s16(p.MaxValue)
	if !(maxValue > 0) {
		return BadMaxValue
	}
	lowFP := s16(p.LowFixedPoint)
	if !(0 <= lowFP && lowFP <= maxValue) {
		return BadLowFP
	}
	highFP := s16(p.HighFixedPoint)
	if !(lowFP <= highFP && highFP <= maxValue) {
		return BadHighFP
	}
	paperMin, paperMax := s16(p.PaperMin), s16(p.PaperMax)
	if !(0 <= paperMin && paperMin <= paperMax && paperMax <= maxValue) {
		return BadPaper
	}
	if !(0.0 <= p.MinSlope && p.MinSlope <= p.MaxSlope) {
		return BadSlope
	}
	if p.BinFactor < 1 || (maxValue+1)%p.BinFactor != 0 {
		return BadBinFactor
	}
	if p.LumWeighting+p.EdgeWeighting != 1.0 {
		return BadWeights
	}
	if !(0.0 <= p.FlashFraction && p.FlashFraction <= 1.0) {
		return BadFlashFraction
	}
	if !(0.0 <= p.BacklitFraction && p.BacklitFraction <= 1.0) {
		return BadBacklitFraction
	}
	if !(0.0 <= p.StartingMinCumPoint && p.StartingMinCumPoint <= 50.0) {
		return BadStartingMinCum
	}
	if !(0.0 <= p.CumPctBelowMin && p.CumPctBelowMin <= 25.0) {
		return BadCumBelowMin
	}
	if !(50.0 <= p.StartingMaxCumPoint && p.StartingMaxCumPoint <= 100.0) {
		return BadStartingMaxCum
	}
	if !(0.0 <= p.CumPctAboveMax && p.CumPctAboveMax <= 25.0) {
		return BadCumAboveMax
	}
	return 0
}

// ---------------------------------------------------------------------------
// AnsDraResults + alloc — 0x1022a820
// ---------------------------------------------------------------------------

// ResultsSize is sizeof(AnsDraResults), the 0x3c-byte window 0x10130390
// rep-movsds out of impl+0x1c88.
const ResultsSize = 0x3C

// Results is the AnsDraResults struct at impl+0x1c88 plus the arrays its
// pointers stand for. A buffer is nil exactly when Alloc's corresponding gate
// was false; generateLut's null checks on the real pointers (0x1022ab9d,
// 0x1022acaa) become nil checks here.
type Results struct {
	NSmallBins    int64
	LumHist       []int64
	EdgeHist      []int64
	NLargeBins    int64
	NLumPixels    int64
	LumLargeHist  []int64
	LumCumHist    []int64
	NEdgePixels   int64
	EdgeLargeHist []int64
	EdgeCumHist   []int64
	Scratch       []int64
	LumMin        int64
	LumMax        int64
	EdgeMin       int64
	EdgeMax       int64
	EffMin        int64
	EffMax        int64
	DraLut        []int64

	hasLum  bool
	hasEdge bool
}

// Alloc is 0x1022a820 — AnsDraCapabilityImpl::allocateMemory. Scratch and
// DraLut are allocated unconditionally; the six lum/edge histogram buffers only
// per their gate, matching real operator-new calls 1:1.
func Alloc(nSmallBins int64, allocLum, allocEdge bool, binFactor int64) *Results {
	r := &Results{NSmallBins: nSmallBins, hasLum: allocLum, hasEdge: allocEdge}
	nLarge := idiv(nSmallBins, binFactor)
	r.NLargeBins = nLarge
	if allocLum {
		r.LumHist = make([]int64, maxInt(int(nSmallBins), 0))
		r.LumLargeHist = make([]int64, maxInt(int(nLarge), 0))
		r.LumCumHist = make([]int64, maxInt(int(nLarge), 0))
	}
	if allocEdge {
		r.EdgeHist = make([]int64, maxInt(int(nSmallBins), 0))
		r.EdgeLargeHist = make([]int64, maxInt(int(nLarge), 0))
		r.EdgeCumHist = make([]int64, maxInt(int(nLarge), 0))
	}
	r.Scratch = make([]int64, maxInt(int(nSmallBins), 0))
	r.DraLut = make([]int64, maxInt(int(nSmallBins), 0))
	return r
}

// ---------------------------------------------------------------------------
// generateLut — 0x1022ab50
// ---------------------------------------------------------------------------

// RemapHist is 0x1022abaf..0x1022ac19 / 0x1022acbe..0x1022ad26 — generateLut's
// own toneLut-gated small-bin histogram remap: scratch[toneLut[i]] += hist[i],
// then the small-bin histogram is replaced by scratch wholesale.
//
// This is the histogram-side counterpart to ComposeTone's curve-side remap. The
// two are easy to conflate but are different blocks at different times: this one
// runs INSIDE generateLut, BEFORE rebin; ComposeTone runs AFTER generateLut
// returns, on the finished LUT.
func RemapHist(hist, toneLut []int64, n int) ([]int64, error) {
	scratch := make([]int64, n)
	for i := 0; i < n; i++ {
		idx := s16(toneLut[i])
		if idx < 0 || idx >= int64(n) {
			return nil, fmt.Errorf("%#x: remap index %d is outside [0,%d); "+
				"the vendor's store is unchecked", VAGenerateLut, idx, n)
		}
		scratch[idx] = s32(scratch[idx] + hist[i])
	}
	return scratch, nil
}

// cumsum32 is 0x1022ac38..0x1022ac69 / 0x1022ad2c..0x1022ad7d — the running
// cumulative sum over the large-bin histogram, plus its final total.
func cumsum32(large []int64) ([]int64, int64) {
	cum := make([]int64, 0, len(large))
	total := int64(0)
	for _, v := range large {
		total = s32(total + v)
		cum = append(cum, total)
	}
	return cum, total
}

// GenerateLut is 0x1022ab50 — AnsDraCapabilityImpl::generateLut. Mutates
// results in place and returns the built LUT.
//
// minSlope and maxSlope (params +0x0c/+0x10) are DEAD here despite their names:
// 0x1022ab50 contains no x87 instructions at all, and sweeping both across
// their whole valid range leaves the real DLL's DraLut byte-identical. Their
// only consumer is ValidateParams' range check (bad-index 6).
func GenerateLut(results *Results, p Params, lighting int64,
	toneLut []int64) ([]int64, error) {
	nSmall := int(results.NSmallBins)
	binFactor := p.BinFactor
	nLarge := idiv(results.NSmallBins, binFactor)
	results.NLargeBins = nLarge

	if results.hasLum {
		lumSmall := results.LumHist
		if toneLut != nil && lumSmall != nil {
			var err error
			lumSmall, err = RemapHist(lumSmall, toneLut, nSmall)
			if err != nil {
				return nil, err
			}
			results.LumHist = lumSmall
		}
		large := Rebin(lumSmall, nSmall, int(binFactor))
		results.LumLargeHist = large
		cum, total := cumsum32(large)
		results.LumCumHist = cum
		results.NLumPixels = total
		results.LumMin, results.LumMax = CumBounds(cum, large, int(nLarge),
			total, p)
	} else {
		// 0x1022ac93 / 0x1022adab: the DLL's own -1 sentinel for an absent
		// side, not a call to cum_bounds.
		results.LumMin, results.LumMax = -1, -1
	}

	if results.hasEdge {
		edgeSmall := results.EdgeHist
		if toneLut != nil && edgeSmall != nil {
			var err error
			edgeSmall, err = RemapHist(edgeSmall, toneLut, nSmall)
			if err != nil {
				return nil, err
			}
			results.EdgeHist = edgeSmall
		}
		large := Rebin(edgeSmall, nSmall, int(binFactor))
		results.EdgeLargeHist = large
		cum, total := cumsum32(large)
		results.EdgeCumHist = cum
		results.NEdgePixels = total
		results.EdgeMin, results.EdgeMax = CumBounds(cum, large, int(nLarge),
			total, p)
	} else {
		results.EdgeMin, results.EdgeMax = -1, -1
	}

	// The three-way merge, 0x1022adc1..0x1022ae12: a -1 sentinel on either side
	// copies the other side's bounds; only when BOTH are real is EffBounds
	// actually called.
	switch {
	case results.EdgeMin < 0:
		results.EffMin, results.EffMax = results.LumMin, results.LumMax
	case results.LumMin < 0:
		results.EffMin, results.EffMax = results.EdgeMin, results.EdgeMax
	default:
		results.EffMin, results.EffMax = EffBounds(
			results.LumMin, results.LumMax, results.EdgeMin, results.EdgeMax,
			p.PaperMin, p.PaperMax, p.LumWeighting, p.EdgeWeighting,
			p.BDoAverage)
	}

	low, high, err := p.CurvePair(lighting)
	if err != nil {
		return nil, err
	}
	draLut := KeepMidPtLut(lighting, low, high, p.MaxValue, p.LowFixedPoint,
		p.HighFixedPoint, p.PaperMin, p.PaperMax, p.FlashFraction,
		results.EffMin, results.EffMax)
	results.DraLut = draLut
	return draLut, nil
}

// ---------------------------------------------------------------------------
// the two analyze overloads
// ---------------------------------------------------------------------------

// AnalyzeImage is 0x1022af20 — the no-incoming-tone-LUT overload. It builds its
// own luminance histogram from raw pixel data (no edge side, so GenerateLut
// always takes the "edge absent -> eff = lum" branch) and never composes.
func AnalyzeImage(p Params, pixels []int16, width, height int,
	lighting int64) (*Results, error) {
	if bad := ValidateParams(p); bad != 0 {
		return nil, &Error{Msg: fmt.Sprintf("Parameter #%d is invalid.", bad)}
	}
	nSmall := s16(p.MaxValue) + 1
	results := Alloc(nSmall, true, false, p.BinFactor)
	hist, err := LumHistogram(pixels, width*height, int(nSmall))
	if err != nil {
		return nil, err
	}
	results.LumHist = hist
	if _, err := GenerateLut(results, p, lighting, nil); err != nil {
		return nil, err
	}
	return results, nil
}

// AnalyzeHist is 0x1022b530 — the histograms-in / compose-out overload, the
// shipped colour-negative path.
//
// When toneLut is provided, GenerateLut remaps the incoming small-bin
// histograms through it (RemapHist, inside generateLut, BEFORE rebin) AND,
// separately, the finished curve is composed onto it afterward (ComposeTone,
// AFTER generateLut returns) — two different uses of the same array, both real.
func AnalyzeHist(p Params, lumHist, edgeHist, toneLut []int64,
	lighting int64) (*Results, error) {
	if bad := ValidateParams(p); bad != 0 {
		return nil, &Error{Msg: fmt.Sprintf("Parameter #%d is invalid.", bad)}
	}
	if lumHist == nil && edgeHist == nil {
		return nil, &Error{Msg: "No analysis data was provided!."}
	}
	nSmall := s16(p.MaxValue) + 1
	results := Alloc(nSmall, lumHist != nil, edgeHist != nil, p.BinFactor)
	if lumHist != nil {
		results.LumHist = append([]int64(nil), lumHist...)
	}
	if edgeHist != nil {
		results.EdgeHist = append([]int64(nil), edgeHist...)
	}
	if _, err := GenerateLut(results, p, lighting, toneLut); err != nil {
		return nil, err
	}
	if toneLut != nil {
		composed, err := ComposeTone(results.DraLut, toneLut, int(nSmall))
		if err != nil {
			return nil, err
		}
		results.DraLut = composed
	}
	return results, nil
}
