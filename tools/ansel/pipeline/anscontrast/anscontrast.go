// Package anscontrast is the Go transcription of
// tools/ansel/python-pipeline/pakon_contrast.py —
// AnsContrastAdjustCapabilityImpl (PakonIMAu.dll 0x101d8240 / 0x101d8880), the
// FOURTH of the six subsystems in ColorNegativePath::analyzeAutoTone's ANALYSIS
// half, and THE ONE THAT PRODUCES THE OUTPUT.
//
// contrast's OutToneLut is the chain's final tone object: ast and
// citras-analyze read it afterward but neither writes it back, so this is the
// 4096-entry curve the render actually applies through the citras driver
// (pakon_ansel.real_auto_tone's own note, and pakon_autotone's stage-5/stage-7
// notes).
//
// WHAT THIS IS AND IS NOT
// =======================
// A line-for-line transcription of the Python module, which is itself
// Unicorn-verified against the real DLL (pakon_contrast_lut_golden.py and
// pakon_contrast_slope_golden.py). Bit-exactness against the vendor BY
// TRANSITIVITY, and only to the extent tools/test_contrast_port.py demonstrates
// Go == Python on real data.
//
// PURE LUT DOMAIN: lutSize shorts in, lutSize shorts out, no pixels anywhere.
//
// NOT PORTED: selectParams / selectDpi (0x101d5d20). The real chain pulls a DPI
// name out of the scene context and looks it up in a std::map built at library
// INITIALISATION — only the lookup happens during analyzeAutoTone, not the
// parse. The Python models the lookup's contract over a host-side registry and
// so does this; ParseDpi is provided so the shipped .dpi resolves to exactly
// the params the real reader would have produced.
//
// FLOATING POINT: as in packages anscna, ansdra and anstonehelper, register
// values are float64 and f32() is applied only where the DLL does an fstp
// dword. build_ramp and build_segment ACCUMULATE their running value by
// repeated `fadd slope` rather than recomputing mid + i*slope, so the float
// error accumulates and is reproduced step for step.
package anscontrast

import (
	"fmt"
	"math"
)

// ---------------------------------------------------------------------------
// addresses (carried from pakon_contrast.py; not re-derived here)
// ---------------------------------------------------------------------------

const (
	VAAnalyze        = 0x101D8240 // the LUT builder
	VAAcquire        = 0x101D8880 // the params-resolving front end
	VABuildRamp      = 0x101D2AD0
	VABuildSegment   = 0x101D2C80
	VAConstrainSlope = 0x101D2EB0
	VAValidateParams = 0x101D3860
	VASetParams      = 0x101D7E70
	VAScanOneLine    = 0x1012DF00
	VASelectParams   = 0x101D5D20
)

const srcFile = `\Atc\ansel\src\libContrastAdjust.ansel\AnsContrastAdjustCapabilityImpl.cpp`

// Source line numbers the DLL pushes at its own log sites.
const (
	LineHolderFailed       = 176
	LineSelectParamsFailed = 185
)

const (
	// slopeMin is 0.1 as a float32 widened back out — the literal the
	// validator compares against, not the decimal.
	slopeMin  = 0.10000000149011612
	slopeMax  = 10.0
	roundHalf = 0.5
	fzero     = 0.0
)

// userInputMode. The numbers are the immediates 0x1012dfbb onward stores to
// params+0x40.
const (
	ModeNoUserInput       = 0 // 0x1012dff4
	ModeCombineWithSlope  = 1 // 0x1012e01a
	ModeCombineWithPoint  = 2 // 0x1012e044
	ModeOverrideWithSlope = 3 // 0x1012e06e
	ModeOverrideWithPoint = 4 // 0x1012e098
)

func modeWithSlope(m int) bool {
	return m == ModeCombineWithSlope || m == ModeOverrideWithSlope
}

func modeWithPoint(m int) bool {
	return m == ModeCombineWithPoint || m == ModeOverrideWithPoint
}

func modeCombine(m int) bool {
	return m == ModeCombineWithSlope || m == ModeCombineWithPoint
}

// modeOverride marks the modes that REPLACE the incoming tone LUT with the
// adjustment curve. They never read `tone` at all — which is why 0x101d82d5
// lets them run with a NULL tone argument and every other mode bails out.
func modeOverride(m int) bool {
	return m == ModeOverrideWithSlope || m == ModeOverrideWithPoint
}

// ---------------------------------------------------------------------------
// float / integer primitives
// ---------------------------------------------------------------------------

func f32(x float64) float64 { return float64(float32(x)) }

// i16 sign-extends the low 16 bits, as every `movsx r32, r/m16` does.
func i16(v int64) int64 { return int64(int16(uint16(uint64(v)))) }

// int64Limit is 2**63 — where fistp qword gives up and stores the "integer
// indefinite".
const int64Limit = 9223372036854775808.0

// ftol16 is `call 0x104ffe44` followed by a use of ax.
//
// __ftol is the standard MSVC helper: fistp qword then an explicit correction
// back toward zero, i.e. C (long long) semantics. Every call site in this
// subsystem consumes only ax, so the 64-bit result is narrowed to signed 16.
//
// NaN and anything outside int64 make fistp store the indefinite
// 0x8000000000000000; 0x104ffe63's `test eax, eax` then sees a zero LOW dword
// and skips the correction, so ax comes out 0, NOT 0x8000.
func ftol16(x float64) int64 {
	var v int64
	if math.IsNaN(x) || x >= int64Limit || x < -int64Limit {
		v = math.MinInt64
	} else {
		v = int64(math.Trunc(x))
	}
	return i16(v)
}

// fdiv is fdivp with every exception masked, which is how the CRT leaves x87.
// A zero divisor is not an error on the FPU. Both a QNaN and a signed infinity
// are reachable — a regression window with a single distinct sample abscissa
// (csGranularity == csNSamples == 1) makes the denominator exactly 0 — and both
// then flow through the limit comparisons as UNORDERED, which the vendor's
// `test ah, 5` / `test ah, 0x41` pairs resolve to "neither too shallow nor too
// steep", i.e. no flag. Go's `<` and `>` against NaN are false, which is the
// same outcome.
func fdiv(num, den float64) float64 {
	if den == 0.0 {
		if num == 0.0 || math.IsNaN(num) {
			return math.NaN()
		}
		if num > 0.0 {
			return math.Inf(1)
		}
		return math.Inf(-1)
	}
	return num / den
}

// cdiv is C idiv — truncation toward zero, not floor.
func cdiv(a, b int64) int64 {
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

// Error is what 0x1001ed90 raises out of this subsystem.
type Error struct{ Msg string }

func (e *Error) Error() string { return e.Msg }

func errf(format string, a ...any) *Error {
	return &Error{Msg: fmt.Sprintf(format, a...)}
}

// ---------------------------------------------------------------------------
// AnsContrastAdjustParams — 0x180 bytes, embedded at Impl+0xc
// ---------------------------------------------------------------------------

// NSlopeBands and SlopeArrayLen: the four per-band slope-limit arrays are 16
// entries wide in the struct but the ctor only seeds 7, and the .dpi reader's
// shared "%f %f %f %f %f %f %f" also writes 7.
const (
	NSlopeBands   = 7
	SlopeArrayLen = 16
)

// Point is one entry of the params' std::vector<(i16,i16)> polyline.
type Point struct{ In, Out int64 }

// Params is AnsContrastAdjustParams. Defaults are 0x1005dab0's literals.
type Params struct {
	MaxValue         int64 // +0x3a i16
	LutSize          int64 // +0x3c i32
	UserInputMode    int   // +0x40 i32
	LowInitialSlope  float64
	HighInitialSlope float64
	MidpointIn       int64 // +0x4c i16
	MidpointOut      int64 // +0x4e i16
	LowIncr          float64
	HighIncr         float64
	AllIncr          float64
	Points           []Point
	BConstrainSlope  bool
	ALowerMinSlope   [SlopeArrayLen]float64
	ALowerMaxSlope   [SlopeArrayLen]float64
	AUpperMinSlope   [SlopeArrayLen]float64
	AUpperMaxSlope   [SlopeArrayLen]float64
	CsGranularity    int64 // +0x170 i32
	CsNSamples       int64 // +0x174 i32
	CsLowerIndex     int64 // +0x178 i16
	CsFixedIndex     int64 // +0x17a i16
	CsUpperIndex     int64 // +0x17c i16
}

// 0x1005dab0's literal seeds, at the .rdata addresses in the comments.
var (
	defLowerMin = [NSlopeBands]float64{0.8, 0.3, 0.8, 0.5, 0.4, 0.2, 0.0}  // 0x10589f18
	defLowerMax = [NSlopeBands]float64{1.5, 6.0, 1.5, 2.5, 4.0, 6.0, 10.0} // 0x10589f58
	defUpperMin = [NSlopeBands]float64{0.8, 0.5, 0.8, 0.7, 0.6, 0.4, 0.0}  // 0x10589f98
	defUpperMax = [NSlopeBands]float64{1.5, 6.0, 1.5, 2.5, 4.0, 6.0, 10.0} // 0x10589fd8
)

// slopeArray is the ctor's fill: NSlopeBands real values, then padding.
// 0x1005dbdd: entries [n, 16) get min = 0 and max = 0x42c80000 == 100.0f.
func slopeArray(seed [NSlopeBands]float64, isMin bool) [SlopeArrayLen]float64 {
	var out [SlopeArrayLen]float64
	for i, v := range seed {
		out[i] = f32(v)
	}
	pad := 100.0
	if isMin {
		pad = 0.0
	}
	for i := NSlopeBands; i < SlopeArrayLen; i++ {
		out[i] = pad
	}
	return out
}

// DefaultParams is 0x1005dab0's constructor defaults.
func DefaultParams() Params {
	return Params{
		MaxValue: 4095, LutSize: 4096, UserInputMode: ModeCombineWithSlope,
		LowInitialSlope: 1.0, HighInitialSlope: 1.0,
		MidpointIn: 1550, MidpointOut: 1550,
		LowIncr: f32(0.1), HighIncr: f32(0.1), AllIncr: f32(0.1),
		ALowerMinSlope: slopeArray(defLowerMin, true),
		ALowerMaxSlope: slopeArray(defLowerMax, false),
		AUpperMinSlope: slopeArray(defUpperMin, true),
		AUpperMaxSlope: slopeArray(defUpperMax, false),
		CsGranularity:  20, CsNSamples: 5,
		CsLowerIndex: 51, CsFixedIndex: 1550, CsUpperIndex: 3999,
	}
}

// Copy is AnsContrastAdjustParams::operator= (0x1010b450) — a deep copy of the
// points vector (the four arrays are values here, so they copy already).
func (p Params) Copy() Params {
	q := p
	q.Points = append([]Point(nil), p.Points...)
	return q
}

// ---------------------------------------------------------------------------
// AnsContrastAdjustResults — 0x2c bytes at Impl+0x18c
// ---------------------------------------------------------------------------

// Results is AnsContrastAdjustResults. Defaults are 0x101d5e60's seeds.
type Results struct {
	LutSize                  int64
	LowSlope                 float64 // 0xbf800000 == -1.0f on a fresh Impl
	HighSlope                float64
	LowerMinSlopeLimit       float64
	LowerMaxSlopeLimit       float64
	UpperMinSlopeLimit       float64
	UpperMaxSlopeLimit       float64
	BWasLowerMinLimitReached bool
	BWasLowerMaxLimitReached bool
	BWasUpperMinLimitReached bool
	BWasUpperMaxLimitReached bool
	CAdjLut                  []int64
	InToneLut                []int64
	OutToneLut               []int64
}

// DefaultResults is the ctor's seeds.
func DefaultResults() Results {
	return Results{LowSlope: -1.0, HighSlope: -1.0,
		LowerMaxSlopeLimit: 100.0, UpperMaxSlopeLimit: 100.0}
}

// ---------------------------------------------------------------------------
// validateParams — 0x101d3860
// ---------------------------------------------------------------------------

// ValidateParams is 0x101d3860. Returns "" on success or an error summary.
//
// IT NEVER MUTATES THE PARAMS. Every `mov [esi], eax` inside it writes the
// hidden AnsStatus& sret, not `this`. That matters because 0x101d8240 DISCARDS
// the status setParams returns, so the only way a validation failure can change
// the LUT is through setParams' own rollback.
func ValidateParams(p Params) string {
	if modeWithPoint(p.UserInputMode) {
		// 0x101d3c06: at least two points, monotone non-decreasing in `in`,
		// every `in` in [0, lutSize), every `out` in [0, maxValue].
		if len(p.Points) < 2 {
			return "points: fewer than two"
		}
		prevIn := int64(math.MinInt64)
		for i, pt := range p.Points {
			if pt.In < 0 || pt.In >= p.LutSize {
				return fmt.Sprintf("points[%d].in out of range", i)
			}
			if pt.Out < 0 || pt.Out > p.MaxValue {
				return fmt.Sprintf("points[%d].out out of range", i)
			}
			if i > 0 && pt.In < prevIn {
				return fmt.Sprintf("points[%d].in decreases", i)
			}
			prevIn = pt.In
		}
		return ""
	}
	// 0x101d38bd: midpoint in range, then both initial slopes in [0.1, 10.0].
	if p.MidpointIn < 0 || p.MidpointIn >= p.LutSize {
		return "midpoint.in out of range"
	}
	if p.MidpointOut < 0 || p.MidpointOut > p.MaxValue {
		return "midpoint.out out of range"
	}
	for _, s := range []struct {
		name string
		v    float64
	}{{"lowInitialSlope", p.LowInitialSlope},
		{"highInitialSlope", p.HighInitialSlope}} {
		if s.v < slopeMin {
			return s.name + " < 0.1"
		}
		if s.v > slopeMax {
			return s.name + " > 10.0"
		}
	}
	return ""
}

// ---------------------------------------------------------------------------
// 0x101d2ad0 — ramp from `midpoint` out to `end_index` at a fixed slope
// ---------------------------------------------------------------------------

// BuildRamp is 0x101d2ad0(midpointPacked, endIndex, slope, buf).
//
// The three slope-sign branches are asymmetric ON PURPOSE:
//
//   - slope < 0  — per-sample clamp UP to maxValue; once the value reaches <= 0
//     the remaining entries are filled with 0 in one go (0x101d2b82).
//   - slope == 0 — the whole span is filled with midOut (0x101d2bba); no
//     rounding at all.
//   - slope > 0  — per-sample clamp DOWN to 0; once the value reaches
//     >= maxValue the rest is filled with maxValue (0x101d2c3e).
func BuildRamp(buf []int64, maxValue, midIn, midOut, endIndex int64,
	slope float64) {
	slope = f32(slope)
	buf[midIn] = midOut
	if i16(midIn) == i16(endIndex) { // 0x101d2af1
		return
	}
	var i, last int64
	var val float64
	if i16(midIn) < i16(endIndex) { // ascending: 0x101d2afa
		i, last = midIn, endIndex
		val = float64(midOut) - slope
	} else { // descending: 0x101d2b0d
		i, last = endIndex, midIn
		val = float64(i16(endIndex)-midIn-1)*slope + float64(midOut)
	}
	if i16(i) > i16(last) {
		return
	}
	if slope < fzero {
		for {
			val = val + slope
			if val <= fzero { // 0x101d2b53 -> 0x101d2b82
				for k := i; k <= last; k++ {
					buf[k] = 0
				}
				return
			}
			r := ftol16(roundHalf + val)
			if r > maxValue { // 0x101d2b62
				r = maxValue
			}
			buf[i] = r
			i++
			if i16(i) > i16(last) {
				return
			}
		}
	}
	if slope == fzero { // 0x101d2bba
		for k := i; k <= last; k++ {
			buf[k] = midOut
		}
		return
	}
	maxF := f32(float64(maxValue)) // 0x101d2bf6: fild / fstp dword
	for {
		val = val + slope
		if val >= maxF { // 0x101d2c0a -> 0x101d2c3e
			for k := i; k <= last; k++ {
				buf[k] = maxValue
			}
			return
		}
		r := ftol16(roundHalf + val)
		if r < 0 { // 0x101d2c1c
			r = 0
		}
		buf[i] = r
		i++
		if i16(i) > i16(last) {
			return
		}
	}
}

// ---------------------------------------------------------------------------
// 0x101d2c80 — one piecewise-linear segment between two `points` entries
// ---------------------------------------------------------------------------

// BuildSegment is 0x101d2c80(ptA, ptB, buf). Same accumulate-by-fadd shape as
// BuildRamp, with two differences that are real, not cosmetic: a flat segment
// (aOut == bOut) is a straight rep stos with no float arithmetic at all, and
// the sloped loops do NO per-sample clamping — only the terminal fills clamp.
func BuildSegment(buf []int64, maxValue, aIn, aOut, bIn, bOut int64) {
	buf[aIn] = aOut
	if i16(aIn) == i16(bIn) { // 0x101d2ca7
		return
	}
	if uint16(aOut) == uint16(bOut) { // 0x101d2cb2 -- flat
		lo, hi := aIn, bIn
		if i16(aIn) >= i16(bIn) {
			lo, hi = bIn, aIn
		}
		start := lo + 1
		if i16(start) > i16(hi) {
			return
		}
		for k := start; k <= hi; k++ {
			buf[k] = aOut
		}
		return
	}
	buf[bIn] = bOut // 0x101d2cff
	var i, last int64
	var slope, val float64
	if i16(aIn) < i16(bIn) { // ascending: 0x101d2d08
		i, last = aIn, bIn
		slope = f32((float64(bOut) - float64(aOut)) / float64(bIn-aIn))
		val = float64(aOut)
	} else { // descending: 0x101d2d2b
		i, last = bIn, aIn
		slope = f32((float64(aOut) - float64(bOut)) / float64(aIn-bIn))
		val = float64(bOut)
	}
	i++
	if i16(i) > i16(last) {
		return
	}
	if slope < fzero { // 0x101d2d64
		for {
			val = val + slope
			if val <= fzero { // -> 0x101d2da9
				for k := i; k <= last; k++ {
					buf[k] = 0
				}
				return
			}
			buf[i] = ftol16(roundHalf + val)
			i++
			if i16(i) > i16(last) {
				return
			}
		}
	}
	maxF := f32(float64(maxValue)) // 0x101d2de3
	for {
		val = val + slope
		if val >= maxF { // -> 0x101d2e27
			for k := i; k <= last; k++ {
				buf[k] = maxValue
			}
			return
		}
		buf[i] = ftol16(roundHalf + val)
		i++
		if i16(i) > i16(last) {
			return
		}
	}
}

// ---------------------------------------------------------------------------
// 0x101d2eb0 — constrainSlope
// ---------------------------------------------------------------------------

// SlopeBand is which of the seven per-band slope-limit rows constrainSlope
// uses. 0x101d33f4's 6-entry jump table on sceneType-1: slots 3..6 all land on
// the shared body with eax still holding sceneType itself, so they select bands
// 3..6; only slots 1 and 2 rewrite it. Anything outside [1,6] takes the default
// at 0x101d2f4d, which picks band 1 when x is exactly 2 and band 0 otherwise.
func SlopeBand(sceneType, x int64) int {
	switch sceneType {
	case 1:
		return 0
	case 2:
		return 2
	case 3, 4, 5, 6:
		return int(sceneType)
	}
	if x == 2 { // 0x101d2f4d
		return 1
	}
	return 0
}

// regress is the least-squares slope of 0x101d3020 / 0x101d3184:
// (Sxy - Sy*Sx/n) / (Sxx - Sx*Sx/n), with n the NOMINAL sample count csNSamples
// — not the number of samples the window actually visited. The four sums are
// accumulated from int operands, so x*y and x*x are 32-bit integer products.
func regress(inLut []int64, first, last, step int64, n float64) float64 {
	var sxy, sx, sy, sxx float64
	for i := first; i <= last; i += step {
		y := i16(inLut[i])
		sxy += float64(i * y)
		sx += float64(i)
		sy += float64(y)
		sxx += float64(i * i)
	}
	num := sxy - (sy*sx)/n // 0x101d3060..0x101d3066
	den := sxx - (sx*sx)/n // 0x101d3068..0x101d306e
	return fdiv(num, den)  // 0x101d3070 fdivp
}

// ConstrainSlopeSampleBounds is the lowest and highest inLut indices
// constrainSlope samples.
//
// Worth having explicitly, because THE VENDOR DOES NOT BOUNDS-CHECK THIS. The
// upward pass keeps starting windows while windowStart <= csUpperIndex and then
// samples up to windowStart + (csNSamples-1)*step + leftover/2, so with
// csUpperIndex close to lutSize it reads off the end of the LUT — a real
// out-of-bounds read in 0x101d3024, not a porting artefact.
//
// It cannot happen on the shipped configuration (csUpperIndex 3999, overhang
// 18, lutSize 4096 -> top sample 4017), and csUpperIndex is in fact UNSETTABLE
// from a .dpi at all — see the csumpperixedindex note in params.go.
func ConstrainSlopeSampleBounds(p Params) (int64, int64) {
	step := cdiv(p.CsGranularity, p.CsNSamples)
	span := (p.CsNSamples - 1) * step
	half := cdiv(i16(p.CsGranularity-span), 2)
	lastOff := span + half
	fixed, upper, lower := i16(p.CsFixedIndex), i16(p.CsUpperIndex),
		i16(p.CsLowerIndex)
	hi := fixed
	if fixed <= upper {
		nUp := (upper - fixed) / p.CsGranularity
		hi = fixed + nUp*p.CsGranularity + lastOff
	}
	lo := fixed
	ws := fixed - p.CsGranularity
	if ws >= lower {
		nDn := (ws - lower) / p.CsGranularity
		lo = ws - nDn*p.CsGranularity + half
	}
	// The Python spells this `min(lo, 0 if fixed == 0 else lo)`, i.e. lo is
	// pulled down to 0 only when csFixedIndex is 0 (the downward walk then
	// starts below the array).
	if fixed == 0 && lo > 0 {
		lo = 0
	}
	return lo, hi
}

// ConstrainSlope is 0x101d2eb0(&status, sceneType, x, inLut, outLut).
//
// Three phases, and the middle one reads oddly until you see it: OUT_LUT
// DOUBLES AS THE FLAG ARRAY. The two regression passes write -1 / +1 / 0 per
// LUT index straight into outLut, and the re-integration phase then reads those
// flags back out of outLut while overwriting it with the final curve. There is
// no separate flag buffer.
func ConstrainSlope(p Params, r *Results, inLut, outLut []int64,
	sceneType, x int64) error {
	lutSize := p.LutSize
	lo, hi := ConstrainSlopeSampleBounds(p)
	if hi >= lutSize || lo < 0 {
		return errf("constrainSlope would sample in_lut[%d..%d] outside "+
			"[0, %d) — the vendor reads out of bounds here (0x101d3024); see "+
			"ConstrainSlopeSampleBounds", lo, hi, lutSize)
	}
	maxValue := p.MaxValue
	for i := int64(0); i < lutSize; i++ { // 0x101d2edf: memset(outLut, 0)
		outLut[i] = 0
	}

	gran := p.CsGranularity
	nSamp := p.CsNSamples
	step := cdiv(gran, nSamp) // 0x101d2f03 idiv
	span := (nSamp - 1) * step
	half := cdiv(i16(gran-span), 2) // 0x101d2f19..0x101d2f25
	lastOff := span + half          // 0x101d2f29
	n := float64(nSamp)             // 0x101d2fc4 fild [esp+0x2c]

	b := SlopeBand(sceneType, x)
	lowerMin := f32(p.ALowerMinSlope[b]) // 0x101d2f59  impl+0x7c
	lowerMax := f32(p.ALowerMaxSlope[b]) // 0x101d2f61  impl+0xbc
	upperMin := f32(p.AUpperMinSlope[b]) // 0x101d2f6c  impl+0xfc
	upperMax := f32(p.AUpperMaxSlope[b]) // 0x101d2f77  impl+0x13c

	fixed := i16(p.CsFixedIndex)
	upper := i16(p.CsUpperIndex)
	lower := i16(p.CsLowerIndex)

	// -- phase 1: upward ----------------------------------------------------
	r.UpperMinSlopeLimit = upperMin // 0x101d2f86  impl+0x1a0
	r.UpperMaxSlopeLimit = upperMax // 0x101d2f97  impl+0x1a4
	r.BWasUpperMinLimitReached = false
	r.BWasUpperMaxLimitReached = false
	if ws := fixed; ws <= upper { // 0x101d2fbe
		sFirst := ws + half
		sLast := ws + lastOff
		for {
			we := ws + gran
			slope := regress(inLut, sFirst, sLast, step, n)
			flag := int64(0)
			if slope < upperMin { // 0x101d3078
				r.BWasUpperMinLimitReached = true
				flag = -1
			} else if slope > upperMax { // 0x101d3097
				r.BWasUpperMaxLimitReached = true
				flag = 1
			}
			if flag != 0 && ws < we {
				for k := ws; k < we; k++ {
					outLut[k] = flag & 0xFFFF
				}
			}
			ws += gran // 0x101d30c5
			sFirst += gran
			sLast += gran
			if ws > upper {
				break
			}
		}
	}

	// -- phase 2: downward --------------------------------------------------
	r.LowerMinSlopeLimit = lowerMin // 0x101d3105  impl+0x198
	r.LowerMaxSlopeLimit = lowerMax // 0x101d310b  impl+0x19c
	r.BWasLowerMinLimitReached = false
	r.BWasLowerMaxLimitReached = false
	if ws := fixed - gran; ws >= lower { // 0x101d312e
		sFirst := ws + half
		sLast := ws + lastOff
		for {
			we := ws + gran
			slope := regress(inLut, sFirst, sLast, step, n)
			flag := int64(0)
			if slope < lowerMin { // 0x101d31dd
				r.BWasLowerMinLimitReached = true
				flag = -1
			} else if slope > lowerMax { // 0x101d31fa
				r.BWasLowerMaxLimitReached = true
				flag = 1
			}
			if flag != 0 && ws < we {
				for k := ws; k < we; k++ {
					outLut[k] = flag & 0xFFFF
				}
			}
			ws -= gran // 0x101d322a
			sFirst -= gran
			sLast -= gran
			if ws < lower {
				break
			}
		}
	}

	// -- phase 3: re-integration -------------------------------------------
	clamp := func(v float64) int64 {
		rr := ftol16(roundHalf + v)
		if rr < 0 {
			return 0
		}
		if rr > maxValue {
			return maxValue
		}
		return rr
	}

	outLut[fixed] = inLut[fixed]           // 0x101d3272
	d := float64(i16(inLut[fixed]))        // 0x101d327a fild
	offset := 0.0                          // 0x101d3283
	for i := fixed + 1; i < lutSize; i++ { // 0x101d32a0
		switch f := i16(outLut[i]); {
		case f < 0:
			d = d + upperMin // 0x101d32ac
			offset = f32(d - float64(i16(inLut[i])))
		case f > 0:
			d = d + upperMax // 0x101d32c6
			offset = f32(d - float64(i16(inLut[i])))
		default:
			d = float64(i16(inLut[i])) + offset // 0x101d32e4
		}
		outLut[i] = clamp(d)
	}

	d = float64(i16(outLut[fixed])) // 0x101d332d
	offset = 0.0
	for i := fixed - 1; i >= 0; i-- { // 0x101d3352
		switch f := i16(outLut[i]); {
		case f < 0:
			d = d - lowerMin // 0x101d335e
			offset = f32(d - float64(i16(inLut[i])))
		case f > 0:
			d = d - lowerMax // 0x101d3378
			offset = f32(d - float64(i16(inLut[i])))
		default:
			d = float64(i16(inLut[i])) + offset // 0x101d3396
		}
		outLut[i] = clamp(d)
	}
	return nil
}

// ---------------------------------------------------------------------------
// the Impl object
// ---------------------------------------------------------------------------

// KeepIntermediatesDefault is AnsContrastAdjustCapability's ctor default for
// cap+0xe (0x10109fc0).
const KeepIntermediatesDefault = false

// Impl is AnsContrastAdjustCapabilityImpl — 0x1b8 bytes, ctor 0x101d5e60.
type Impl struct {
	Params  Params
	Results Results
}

// NewImpl is the ctor.
func NewImpl() *Impl {
	return &Impl{Params: DefaultParams(), Results: DefaultResults()}
}

// FreeBuffers is 0x101d2e50 — delete[] all three scratch LUTs and NULL them.
func (im *Impl) FreeBuffers() {
	im.Results.CAdjLut = nil
	im.Results.InToneLut = nil
	im.Results.OutToneLut = nil
}

// SetParams is 0x101d7e70. Copy in, validate, roll back on failure.
//
// On a validation failure the params are assigned straight back from the backup
// (0x101d7ff5), so a bad .dpi silently reverts to whatever the object already
// had rather than erroring the analysis out. On success the results' slopes are
// reseeded from the NEW initial slopes, but only if lowSlope < 0 (a freshly
// constructed Impl) or both results still equal the OLD params' initial slopes
// — the clause that stops a params reload from throwing away a slope the user
// moved with changeContrast(). analyzeAutoTone never calls that, so on this
// path the reseed always happens.
func (im *Impl) SetParams(p Params) string {
	old := im.Params.Copy()
	im.Params = p.Copy()
	if err := ValidateParams(im.Params); err != "" {
		im.Params = old // 0x101d7ff5 rollback
		return err
	}
	r := &im.Results
	if r.LowSlope < fzero ||
		(r.LowSlope == f32(old.LowInitialSlope) &&
			r.HighSlope == f32(old.HighInitialSlope)) {
		r.LowSlope = f32(im.Params.LowInitialSlope) // 0x101d8054
		r.HighSlope = f32(im.Params.HighInitialSlope)
	}
	return ""
}

// Analyze is 0x101d8240(&status, holder, capFlagE, params, sceneType, x, tone).
//
// setParams' status is deliberately DISCARDED when a params object is supplied,
// exactly as 0x101d82a2 does.
func (im *Impl) Analyze(params *Params, sceneType, x int64, toneLut []int64,
	keepIntermediates bool) (*Results, error) {
	if params != nil {
		im.SetParams(*params) // status deliberately dropped
	}

	p := im.Params
	r := &im.Results
	lutSize := p.LutSize
	mode := p.UserInputMode

	// 0x101d82c5: a NULL tone LUT is only survivable in the two OVERRIDE
	// modes, which never read it. Every other mode cleans up and returns OK
	// having built nothing at all.
	if toneLut == nil && !modeOverride(mode) {
		im.FreeBuffers()
		return r, nil
	}

	im.FreeBuffers() // 0x101d82e3
	outLut := make([]int64, lutSize)
	var adjLut []int64
	if mode != ModeNoUserInput {
		adjLut = make([]int64, lutSize)
	}
	var inLut []int64
	if !modeOverride(mode) { // 0x101d8445
		inLut = make([]int64, lutSize)
		copy(inLut, toneLut)
		if p.BConstrainSlope { // 0x101d84cb
			if err := ConstrainSlope(p, r, inLut, outLut, sceneType, x); err != nil {
				return nil, err
			}
		}
	}

	r.LutSize = lutSize // 0x101d855b impl+0x18c

	// -- the adjustment curve, into adjLut ---------------------------------
	switch {
	case modeWithSlope(mode): // 0x101d85b9
		BuildRamp(adjLut, p.MaxValue, p.MidpointIn, p.MidpointOut, 0,
			r.LowSlope)
		BuildRamp(adjLut, p.MaxValue, p.MidpointIn, p.MidpointOut, lutSize-1,
			r.HighSlope)
	case modeWithPoint(mode): // 0x101d8578
		for i := range adjLut {
			adjLut[i] = 0
		}
		for i := 0; i+1 < len(p.Points); i++ {
			a, bpt := p.Points[i], p.Points[i+1]
			BuildSegment(adjLut, p.MaxValue, a.In, a.Out, bpt.In, bpt.Out)
		}
	}

	// -- compose ------------------------------------------------------------
	// 0x101d85ef: the source for COMBINE is the CONSTRAINED curve when
	// bConstrainSlope ran, otherwise the raw copy of the incoming LUT.
	src := inLut
	if p.BConstrainSlope {
		src = outLut
	}
	switch {
	case modeCombine(mode): // 0x101d8697
		for i := int64(0); i < lutSize; i++ {
			idx := i16(src[i])
			if idx < 0 || idx >= int64(len(adjLut)) {
				return nil, errf("%#x: compose index %d is outside [0,%d); "+
					"the vendor's movsx-widened load is unchecked", VAAnalyze,
					idx, len(adjLut))
			}
			outLut[i] = adjLut[idx]
		}
	case modeOverride(mode): // 0x101d8681
		copy(outLut, adjLut)
	default: // 0x101d8617, NO_USER_INPUT
		if !p.BConstrainSlope {
			copy(outLut, src)
		}
	}

	r.OutToneLut = outLut
	r.CAdjLut = adjLut
	r.InToneLut = inLut
	if !keepIntermediates { // 0x101d8633, cap+0xe == 0
		r.CAdjLut = nil
		r.InToneLut = nil
	}
	return r, nil
}

// Acquire is 0x101d8880(&status, holder, capFlagE, sceneType, x, tone). The
// scene-context/selectParams resolution is modelled by the caller supplying the
// already-parsed params, exactly as pakon_contrast.acquire does — only the
// LOOKUP happens during analyzeAutoTone, and the parse does not.
func Acquire(im *Impl, params *Params, capFlagE bool, sceneType, x int64,
	toneLut []int64) (*Results, error) {
	return im.Analyze(params, sceneType, x, toneLut, capFlagE)
}

// Subsystem is the adapter for analyzeAutoTone's stage-4 pair: the shell calls
// contrast_acquire(holder, sceneType, x, tone) then contrast_get_results() and
// reads OutToneLut out of the returned 0x2c-byte blob (0x100fc6fb ->
// 0x10109d70, a bare rep movsd).
type Subsystem struct {
	Impl              *Impl
	KeepIntermediates bool
	Results           *Results
}

// NewSubsystem constructs the Impl and pushes the params through SetParams, as
// pakon_contrast.ContrastSubsystem does.
func NewSubsystem(p Params, keepIntermediates bool) *Subsystem {
	im := NewImpl()
	im.SetParams(p)
	return &Subsystem{Impl: im, KeepIntermediates: keepIntermediates}
}

// Acquire runs stage 4.
func (s *Subsystem) Acquire(sceneType, x int64, toneLut []int64) error {
	r, err := s.Impl.Analyze(nil, sceneType, x, toneLut, s.KeepIntermediates)
	if err != nil {
		return err
	}
	s.Results = r
	return nil
}
