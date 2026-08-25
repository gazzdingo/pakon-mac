// Package anstonehelper is the Go transcription of
// tools/ansel/python-pipeline/pakon_toneHelper.py —
// AnsToneHelperCapabilityImpl::analyze (PakonIMAu.dll 0x101dd1b0, the
// histograms-in overload), the THIRD of the six subsystems in
// ColorNegativePath::analyzeAutoTone's ANALYSIS half.
//
// WHAT THIS IS AND IS NOT
// =======================
// A line-for-line transcription of the Python module, which is itself
// Unicorn-verified against the real DLL (pakon_toneHelper_core_golden.py and
// pakon_toneHelper_tree_golden.py). Bit-exactness against the vendor BY
// TRANSITIVITY, and only to the extent tools/test_tonehelper_port.py
// demonstrates Go == Python on real data.
//
// WHAT CROSSES THE SHELL BOUNDARY IS ONE INTEGER. toneHelper computes 29
// metrics over cna's two histograms mapped through dra's DraLut, walks a
// decision tree with them, and publishes AnsToneHelperResults+0xb4 —
// toneHelperValue, which is 1 or 2. analyzeAutoTone reads that at 0x100fc5c4
// and hands it to contrast as its `x` argument (unless cna raised
// bElmoOccured, in which case elmoAggressiveness is used instead). Nothing
// else this subsystem computes reaches the tone curve.
//
// NOT PORTED HERE: the image-side overload 0x101dcc50 and its histogram/edge
// builder 0x101dbc00. The Python does not port them either — the shell only
// calls that variant when cna produced no edge histogram (0x100fc334), and cna
// always does. AnalyzeFromImage returns an error saying so rather than shipping
// a plausible-looking edge detector nobody has checked against the DLL.
//
// FLOATING POINT: as in packages anscna and ansdra, register values are float64
// and f32() is applied only where the DLL does an fst/fstp dword. calcStats'
// four-slot unrolled moment loop spills DIFFERENT accumulators in each of its
// four positions, and that asymmetry is observable in the last bits of skew and
// kurtosis, so it is transcribed slot by slot rather than summed in one pass.
package anstonehelper

import (
	"fmt"
	"math"
)

// ---------------------------------------------------------------------------
// addresses (carried from pakon_toneHelper.py; not re-derived here)
// ---------------------------------------------------------------------------

const (
	VAImplAnalyzeHist  = 0x101DD1B0 // analyze(hists, tone, exposure) — LIVE
	VAImplAnalyzeImage = 0x101DCC50 // analyze(image, …) — not ported
	VABuildHistograms  = 0x101DBC00 // the image-side histogram/edge builder
	VAComputeMetrics   = 0x101DB020
	VAWalkTree         = 0x101DB890
	VAParamCheck       = 0x101DA6B0
	VAHistCalcWork     = 0x10278DF0
	VAHistCalcDistance = 0x102781D0
	VAHistCalcStats    = 0x10278730
)

const (
	srcFileImpl   = `\Atc\ansel\src\libToneHelper.ansel\AnsToneHelperCapabilityImpl.cpp`
	srcFileParams = `\Atc\ansel\src\libToneHelper.ansel\AnsToneHelperParams.cpp`
	srcFileHist   = `\Atc\ansel\src\libAnsCore\AnsHistogram.cpp`
)

// ResultsSize is sizeof(AnsToneHelperResults), the 0x2f dwords 0x1010bb40
// rep-movsds out of impl+0x80. ResultsToneValueOffset is the ONE field
// analyzeAutoTone reads.
const (
	ResultsSize            = 0xBC
	ResultsImplOffset      = 0x80
	ResultsToneValueOffset = 0xB4
)

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

func f32(v float64) float64 { return float64(float32(v)) }

func i32(v int64) int64 { return int64(int32(uint32(uint64(v)))) }

func i16(v int64) int64 { return int64(int16(uint16(uint64(v)))) }

// x87Indefinite is x87's "real indefinite" QNaN, sign bit set.
var x87Indefinite = math.Float64frombits(0xFFF8000000000000)

// x87Div is fdivr/fdiv under FPCW 0x027f's masked exceptions. Both divisors
// this file uses — the sum of four calcWork counts, and calcStats' own count —
// are 0 on a genuine, real-DLL-producible input: an entirely edgeless
// (perfectly flat) image legitimately makes edge_hist all zero. The real DLL
// silently produces a correctly-signed infinity and keeps executing.
func x87Div(num, den float64) float64 {
	if den == 0.0 {
		if num == 0.0 {
			return x87Indefinite
		}
		return math.Copysign(math.Inf(1), num) * math.Copysign(1.0, den)
	}
	return num / den
}

// ftol is the CRT's __ftol — truncation toward zero.
func ftol(x float64) int64 {
	if math.IsNaN(x) || math.IsInf(x, 0) {
		return math.MinInt64
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

// Error is what the subsystem throws.
type Error struct{ Msg string }

func (e *Error) Error() string { return e.Msg }

func errf(format string, a ...any) *Error {
	return &Error{Msg: fmt.Sprintf(format, a...)}
}

// ---------------------------------------------------------------------------
// the metric enum — the 31-entry char* table at 0x106993a0
// ---------------------------------------------------------------------------

// MetricNames is read straight out of .data; the decisionTree files name
// metrics by exactly these strings. The walker's jump table (0x101dbb80, 30
// entries) is indexed by metricId-1, so NONE (0) has no case.
var MetricNames = [...]string{
	"NONE", "TERMINAL",
	"LUM_WORK_LOW", "LUM_WORK_MIDLOW", "LUM_WORK_SUMLOW", "LUM_WORK_MIDHIGH",
	"LUM_WORK_HIGH", "LUM_WORK_SUMHIGH", "LUM_WORK_TOTAL", "LUM_DISTANCE",
	"LUM_INTERSECTION", "LUM_AVERAGE", "LUM_AVGDEV", "LUM_STDDEV", "LUM_SKEW",
	"LUM_KURTOSIS",
	"EDGE_WORK_LOW", "EDGE_WORK_MIDLOW", "EDGE_WORK_SUMLOW",
	"EDGE_WORK_MIDHIGH", "EDGE_WORK_HIGH", "EDGE_WORK_SUMHIGH",
	"EDGE_WORK_TOTAL", "EDGE_DISTANCE", "EDGE_INTERSECTION", "EDGE_AVERAGE",
	"EDGE_AVGDEV", "EDGE_STDDEV", "EDGE_SKEW", "EDGE_KURTOSIS",
	"EXPOSURE",
}

// MetricID maps a decisionTree file's metric name to its id.
var MetricID = func() map[string]int {
	m := make(map[string]int, len(MetricNames))
	for i, n := range MetricNames {
		m[n] = i
	}
	return m
}()

const (
	MetricNone     = 0
	MetricTerminal = 1
)

// ---------------------------------------------------------------------------
// AnsHistogram — 0x10278140's object
// ---------------------------------------------------------------------------

// Histogram is {nBins, _, min, max, uninit, data, base}. The ctor only
// initialises when data != 0 and minValue < maxValue; otherwise every method
// throws "Histogram was not initialized.". base (+0x18) is data - 4*minValue,
// i.e. the value-indexed view — reproduced here by indexing Bins with the raw
// value and keeping MinValue around.
type Histogram struct {
	NBins    int
	Bins     []int64
	MinValue int
	MaxValue int
}

func (h *Histogram) initialised() bool {
	return len(h.Bins) > 0 && h.MinValue < h.MaxValue
}

// rng is the shared `from >= to -> use [m_minValue, m_maxValue]` rule.
func (h *Histogram) rng(frm, to int) (int, int, error) {
	if frm < to {
		if frm < h.MinValue {
			return 0, 0, errf("The parameter 'from' is less than m_minValue. "+
				"[%s]", srcFileHist)
		}
		if to > h.MaxValue {
			return 0, 0, errf("The parameter 'to' is greater than m_maxValue. "+
				"[%s]", srcFileHist)
		}
		return frm, to, nil
	}
	return h.MinValue, h.MaxValue, nil
}

// CalcWork is AnsHistogram::calcWork (0x10278df0) -> (count, work), where
// work = sum(bins[v] * abs(lut[v] - v)) and count = sum(bins[v]).
//
// The absolute value is not an fabs: the loop forms the signed int32 product
// bins[v] * (lut[v] - v) and then picks fisub (0x10278fab) or fiadd
// (0x1027907f) on the sign of lut[v] - v. lut is read with `movsx ... word`,
// i.e. as SIGNED int16. Every addend is an int32 pushed through fiadd/fisub and
// the accumulator never leaves ST(0), so there is exactly one rounding, at the
// end.
func (h *Histogram) CalcWork(lut []int64, frm, to int) (int64, float64, error) {
	if !h.initialised() {
		return 0, 0, errf("Histogram was not initialized. [%s:458]", srcFileHist)
	}
	lo, hi, err := h.rng(frm, to)
	if err != nil {
		return 0, 0, err
	}
	count := int64(0)
	work := 0.0
	for v := lo; v <= hi; v++ {
		b := h.Bins[v]
		d := i16(lut[v]) - int64(v)
		count += b
		if d >= 0 {
			work += float64(i32(b * d))
		} else {
			work += float64(-i32(b * d))
		}
	}
	return i32(count), f32(work), nil
}

// CalcDistance is AnsHistogram::calcDistance (0x102781d0) -> (distance,
// intersection). It maps this histogram through lut into out and measures how
// far it moved. The second accumulator is fed only on the non-negative side —
// that asymmetry is what makes it an INTERSECTION (mass gained) rather than a
// signed total, which is always 0.
func (h *Histogram) CalcDistance(lut []int64, out *Histogram, frm, to int) (
	float64, float64, error) {
	if !h.initialised() {
		return 0, 0, errf("The input histogram was not initialized. [%s:199]",
			srcFileHist)
	}
	if !out.initialised() {
		return 0, 0, errf("The output histogram was not initialized. [%s:207]",
			srcFileHist)
	}
	if h.MinValue != out.MinValue || h.MaxValue != out.MaxValue {
		return 0, 0, errf("The input and output histograms have different "+
			"ranges. [%s:232]", srcFileHist)
	}
	lo, hi, err := h.rng(frm, to)
	if err != nil {
		return 0, 0, err
	}
	for v := lo; v <= hi; v++ {
		out.Bins[v] = 0
	}
	for v := lo; v <= hi; v++ {
		idx := i16(lut[v])
		if idx < 0 || idx >= int64(len(out.Bins)) {
			return 0, 0, errf("%#x: calcDistance target bin %d is outside "+
				"[0,%d); the vendor's store is unchecked", VAHistCalcDistance,
				idx, len(out.Bins))
		}
		out.Bins[idx] = i32(out.Bins[idx] + h.Bins[v])
	}
	dist, inter := 0.0, 0.0
	for v := lo; v <= hi; v++ {
		d := i32(out.Bins[v] - h.Bins[v])
		if d < 0 {
			dist -= float64(d)
		} else {
			dist += float64(d)
			inter += float64(d)
		}
	}
	return f32(dist), f32(inter), nil
}

// Stats is calcStats' six out-parameters, in the order 0x101db020 passes them.
type Stats struct {
	Count    int64
	Average  float64
	AvgDev   float64
	StdDev   float64
	Skew     float64
	Kurtosis float64
}

// CalcStats is AnsHistogram::calcStats (0x10278730).
//
// THE MOMENT LOOP IS NOT UNIFORM AND THE ASYMMETRY IS REAL. It is 4x unrolled
// and the compiler spilled different quantities to different-width slots in
// each of the four positions; the per-slot rounding table is in
// pakon_toneHelper.calc_stats' docstring and is transcribed literally below.
// m4 needs TWO variables because `fst dword [esp+0x18]` writes the rounded copy
// but leaves the unrounded value in ST(0), and the two remainder loops keep
// accumulating into the UNROUNDED one. Collapsing them costs exactly one
// float32 ulp of kurtosis on a broad histogram.
func (h *Histogram) CalcStats(frm, to int) (Stats, error) {
	var s Stats
	if !h.initialised() {
		return s, errf("Histogram was not initialized. [%s:310]", srcFileHist)
	}
	lo, hi, err := h.rng(frm, to)
	if err != nil {
		return s, err
	}

	count := int64(0)
	sum1 := 0.0
	for v := lo; v <= hi; v++ {
		b := h.Bins[v]
		count += b
		sum1 += float64(i32(b * int64(v)))
	}
	count = i32(count)
	sum1 = f32(sum1) // 0x10278958  fst dword [esp+0x1c]

	if count < 2 { // 0x10278ac7  cmp edi, 1 ; jle
		return Stats{Count: count, Average: sum1}, nil
	}

	nf := f32(float64(count)) // 0x10278af8/afc
	invN := 1.0 / nf          // ST(0), 0x10278b00/06
	invNF32 := f32(invN)      // 0x10278b0a  fst dword [esp+0x38]
	mean := f32(invN * sum1)  // 0x10278b0e/12
	mi := ftol(mean)          // 0x10278b16  _ftol (truncate)
	if float64(mi) > mean {   // 0x10278b25..b31
		mi--
	}

	a := 0.0     // [esp+0x54], always via memory
	m2 := 0.0    // [esp+0x50], always via memory
	m3 := 0.0    // ST(1) across the unrolled loop, [esp+0x20] within it
	m4reg := 0.0 // ST(0)
	m4mem := 0.0 // [esp+0x18]

	v := int64(lo)
	// ---- 0x10278b5a: 4x unrolled, only over [from .. mi] -----------------
	if mi-int64(lo)+1 >= 4 {
		for v <= mi-3 {
			// slot 0 -- d float32; m4 re-read from memory, m3 from ST(1)
			d := f32(float64(v) - mean)
			c := float64(h.Bins[v])
			a = f32(a - c*d)
			m2 = f32(m2 + c*d*d)
			t := f32(c * d * d * d) // fst dword [esp+0x1c]
			m3 = m3 + c*d*d*d       // faddp st(1) -- unrounded
			m4reg = m4mem + t*d     // fadd dword [esp+0x18]
			// slot 1 -- d stays in ST(0); m3 spills to float32
			d = float64(v+1) - mean
			c = float64(h.Bins[v+1])
			a = f32(a - c*d)
			m2 = f32(m2 + c*d*d)
			m3 = f32(m3 + c*d*d*d) // fstp dword [esp+0x20]
			m4reg = m4reg + c*d*d*d*d
			// slot 2 -- both m3 and m4 spill; m4's register copy is popped
			d = float64(v+2) - mean
			c = float64(h.Bins[v+2])
			a = f32(a - c*d)
			m2 = f32(m2 + c*d*d)
			m3 = f32(m3 + c*d*d*d)
			m4mem = f32(m4reg + c*d*d*d*d) // fstp -> memory only
			m4reg = m4mem
			// slot 3 -- d float32 again; m3 back into ST(0) unrounded,
			// m4 written to memory but kept unrounded in ST(0)
			d = f32(float64(v+3) - mean)
			c = float64(h.Bins[v+3])
			a = f32(a - c*d)
			m2 = f32(m2 + c*d*d)
			t = f32(c * d * d * d)
			m3 = m3 + c*d*d*d   // fadd dword [esp+0x20]
			m4reg = m4mem + t*d // fadd dword [esp+0x18]
			m4mem = f32(m4reg)  // fst  dword [esp+0x18]
			v += 4
		}
	}
	// ---- 0x10278c84: A and M2 come back from their float32 slots ---------
	a = f32(a)
	m2 = f32(m2)
	m4 := m4reg
	// ---- 0x10278c93: the rest of [from .. mi], nothing rounded ----------
	if v <= mi {
		for v <= mi {
			d := float64(v) - mean
			c := float64(h.Bins[v])
			a = a - c*d
			m2 = m2 + c*d*d
			m3 = m3 + c*d*d*d
			m4 = m4 + c*d*d*d*d
			v++
		}
		m4mem = f32(m4) // 0x10278cc4  fst dword [esp+0x18]
	}
	// ---- 0x10278cd1: (mi .. to], A now ADDS ------------------------------
	if v <= int64(hi) {
		for v <= int64(hi) {
			d := float64(v) - mean
			c := float64(h.Bins[v])
			a = a + c*d
			m2 = m2 + c*d*d
			m3 = m3 + c*d*d*d
			m4 = m4 + c*d*d*d*d
			v++
		}
		m4mem = f32(m4) // 0x10278d00  fst dword [esp+0x18]
	}

	// ---- 0x10278d06 ------------------------------------------------------
	avgDev := f32(invNF32 * a)
	variance := m2 / float64(count-1)
	if variance == 0.0 { // 0x10278d2b  fucompp ; jnp
		// The degenerate-histogram path: the raw third moment is left in ST(0)
		// as "skew" and whatever the loop last spilled to [esp+0x18] as
		// "kurtosis". Modelled rather than zeroed — guessing here is exactly
		// how a port silently diverges.
		return Stats{Count: count, Average: mean, AvgDev: avgDev,
			StdDev: 0.0, Skew: f32(m3), Kurtosis: m4mem}, nil
	}
	std := f32(math.Sqrt(variance))
	skew := f32(m3 / ((nf * std) * variance))
	kurt := f32(m4/((nf*variance)*variance) - f32(3.0))
	return Stats{Count: count, Average: mean, AvgDev: avgDev, StdDev: std,
		Skew: skew, Kurtosis: kurt}, nil
}

// ---------------------------------------------------------------------------
// 0x101db020 — the metric producer
// ---------------------------------------------------------------------------

// MetricGroup is one of the two 0x3c-byte AnsHistogram metric groups
// (impl+0xb0 for luminance, impl+0xec for edge). Field names come from the
// vendor's own ostream printer literals.
type MetricGroup struct {
	Count        int64   // +0x00 calcStats out #1
	WorkLow      float64 // +0x04 calcWork lowToneRange
	WorkMidLow   float64 // +0x08 calcWork midLowToneRange
	WorkSumLow   float64 // +0x0c low + midLow
	WorkMidHigh  float64 // +0x10 calcWork midHighToneRange
	WorkHigh     float64 // +0x14 calcWork highToneRange
	WorkSumHigh  float64 // +0x18 midHigh + high
	WorkTotal    float64 // +0x1c sumHigh + sumLow
	Distance     float64 // +0x20 calcDistance out #1
	Intersection float64 // +0x24 calcDistance out #2
	Average      float64 // +0x28 calcStats out #2
	AvgDev       float64 // +0x2c calcStats out #3
	StdDev       float64 // +0x30 calcStats out #4
	Skew         float64 // +0x34 calcStats out #5
	Kurtosis     float64 // +0x38 calcStats out #6
}

// ComputeMetrics is 0x101db020 -> (lumGroup, edgeGroup).
//
// Per pass: calcStats(0, 0) — the two zeros make it use the histogram's own
// full range — then four calcWork calls over the four tone ranges, then
// calcDistance. The two normalisation blocks are deliberately ASYMMETRIC and
// are transcribed literally: workSumLow adds the UNROUNDED products still on
// the FPU stack, whereas workSumHigh reloads the two float32 spills the code
// made at 0x101db4f5/0x101db500 and therefore adds the ROUNDED values.
func ComputeMetrics(p Params, lumHist, edgeHist, toneLut []int64) (
	MetricGroup, MetricGroup, error) {
	nBins := int(p.MaxValue) + 1
	scratch := &Histogram{NBins: nBins, Bins: make([]int64, nBins),
		MinValue: 0, MaxValue: int(p.MaxValue)}
	var groups [2]MetricGroup

	for pass, bins := range [2][]int64{lumHist, edgeHist} {
		h := &Histogram{NBins: nBins, Bins: append([]int64(nil), bins...),
			MinValue: 0, MaxValue: int(p.MaxValue)}
		var g MetricGroup

		st, err := h.CalcStats(0, 0)
		if err != nil {
			return groups[0], groups[1], err
		}
		g.Count = st.Count
		g.Average, g.AvgDev, g.StdDev = st.Average, st.AvgDev, st.StdDev
		g.Skew, g.Kurtosis = st.Skew, st.Kurtosis

		cLow, wLow, err := h.CalcWork(toneLut, int(p.LowToneRange[0]), int(p.LowToneRange[1]))
		if err != nil {
			return groups[0], groups[1], err
		}
		cMlo, wMlo, err := h.CalcWork(toneLut, int(p.MidLowToneRange[0]), int(p.MidLowToneRange[1]))
		if err != nil {
			return groups[0], groups[1], err
		}
		cMhi, wMhi, err := h.CalcWork(toneLut, int(p.MidHighToneRange[0]), int(p.MidHighToneRange[1]))
		if err != nil {
			return groups[0], groups[1], err
		}
		cHi, wHi, err := h.CalcWork(toneLut, int(p.HighToneRange[0]), int(p.HighToneRange[1]))
		if err != nil {
			return groups[0], groups[1], err
		}
		total := i32(cLow + cMlo + cMhi + cHi) // ebp, 0x101db4be

		// ---- 0x101db4c6 .. 0x101db530 -----------------------------------
		scale := x87Div(f32(1.0), float64(total))
		eLow := scale * wLow
		eMlo := scale * wMlo
		eMhi := scale * wMhi
		eHi := scale * wHi
		g.WorkLow = f32(eLow)
		g.WorkMidLow = f32(eMlo)
		g.WorkMidHigh = f32(eMhi)
		g.WorkHigh = f32(eHi)
		sumLow := eLow + eMlo // faddp st(1) -- unrounded
		g.WorkSumLow = f32(sumLow)
		sumHigh := g.WorkMidHigh + g.WorkHigh // the ROUNDED spills
		g.WorkSumHigh = f32(sumHigh)
		g.WorkTotal = f32(sumHigh + sumLow) // both still-unrounded sums

		// ---- calcDistance, 0x101db532 -----------------------------------
		dist, inter, err := h.CalcDistance(toneLut, scratch, 0, 0)
		if err != nil {
			return groups[0], groups[1], err
		}

		// ---- 0x101db596 .. 0x101db5b6 -----------------------------------
		// scale2 uses calcStats' own count, NOT the calcWork total.
		scale2 := x87Div(f32(1.0), float64(g.Count))
		g.Distance = f32(scale2 * dist)
		g.Intersection = f32(scale2 * inter)

		groups[pass] = g
	}
	return groups[0], groups[1], nil
}

// MetricsByID lays the two groups out the way the walker's switch arms read
// them: ids 2..15 are the LUM group, 16..29 the EDGE group, 30 the exposure.
func MetricsByID(lum, edge MetricGroup, exposure float64) map[int]float64 {
	pick := func(g MetricGroup, i int) float64 {
		switch i {
		case 0:
			return g.WorkLow
		case 1:
			return g.WorkMidLow
		case 2:
			return g.WorkSumLow
		case 3:
			return g.WorkMidHigh
		case 4:
			return g.WorkHigh
		case 5:
			return g.WorkSumHigh
		case 6:
			return g.WorkTotal
		case 7:
			return g.Distance
		case 8:
			return g.Intersection
		case 9:
			return g.Average
		case 10:
			return g.AvgDev
		case 11:
			return g.StdDev
		case 12:
			return g.Skew
		default:
			return g.Kurtosis
		}
	}
	ids := make(map[int]float64, 29)
	for id := 2; id <= 15; id++ {
		ids[id] = f32(pick(lum, id-2))
	}
	for id := 16; id <= 29; id++ {
		ids[id] = f32(pick(edge, id-16))
	}
	ids[30] = f32(exposure)
	return ids
}

// ---------------------------------------------------------------------------
// the decision tree
// ---------------------------------------------------------------------------

// DecisionNode is one 20-byte node of a decisionTree file.
type DecisionNode struct {
	Metric    int     // +0x00 index into MetricNames
	Threshold float64 // +0x04 stored and compared as float32
	LessEqual int     // +0x08 node index taken when metric <  threshold
	Greater   int     // +0x0c node index taken when metric >= threshold
	Class     int     // +0x10 only read on TERMINAL
}

// VerifyDecisionTree is AnsToneHelperParams::verifyDecisionTree (0x101da3b0).
// 0x101db890 calls it before walking a single node and bails on a non-OK
// status.
//
// The strict `> index` half of the goto range check is load-bearing: it makes
// the tree a forward-only DAG, which is the guarantee that the walker's
// unbounded while loop terminates.
func VerifyDecisionTree(nodes []DecisionNode) error {
	n := len(nodes)
	if n == 0 {
		return errf("A NULL decision tree is invalid. "+
			"[AnsToneHelperParams::verifyDecisionTree, %s:316]", srcFileParams)
	}
	var check func(i int) error
	check = func(i int) error {
		nd := nodes[i]
		if nd.Metric == MetricTerminal {
			if nd.LessEqual != -1 || nd.Greater != -1 {
				return errf("In node number %d, the TERMINAL node gotos are "+
					"not -1. [AnsToneHelperParams::checkDecisionNode, %s:343]",
					i, srcFileParams)
			}
			return nil
		}
		if nd.Metric < 1 || nd.Metric > 30 {
			return errf("In node number %d, metric %d is not supported. "+
				"[AnsToneHelperParams::checkDecisionNode, %s:357]",
				i, nd.Metric, srcFileParams)
		}
		for _, c := range []struct {
			label string
			tgt   int
			line  int
		}{{"lessEqualGoto", nd.LessEqual, 372}, {"greaterGoto", nd.Greater, 385}} {
			if !(i < c.tgt && c.tgt < n) {
				return errf("In node number %d, the %s value (%d) is out of "+
					"range. [AnsToneHelperParams::checkDecisionNode, %s:%d]",
					i, c.label, c.tgt, srcFileParams, c.line)
			}
		}
		if err := check(nd.LessEqual); err != nil {
			return err
		}
		return check(nd.Greater)
	}
	return check(0)
}

// WalkResult is what 0x101db890 writes back into the Impl.
type WalkResult struct {
	TerminalNode int   // impl+0x12c (results+0xac)
	ToneValue    int   // impl+0x134 (results+0xb4) -- 1 or 2
	SceneClass   int   // impl+0x138 (results+0xb8) -- 2, 3 or clamped 3
	Path         []int // visited node indices, harness aid only
}

// WalkDecisionTree is 0x101db890 — the 30-way walker.
//
// Two things the assembly settles that the file format does not:
//
//   - 0x101dbada's `fcom; fnstsw; test ah,5; jp` takes [edx+0xc] (greater)
//     exactly when metric >= threshold, so EQUALITY GOES TO GREATER. The file's
//     column name "lessEqual" is off by the boundary case and the assembly wins.
//   - ST(0) starts at 0.0f and metric ids outside 2..30 (including 0/NONE)
//     leave it UNCHANGED, i.e. re-use the previous node's metric value.
//     Modelled, not smoothed over — though VerifyDecisionTree rejects metric 0,
//     so it is unreachable for any tree that got past the check.
func WalkDecisionTree(nodes []DecisionNode, metrics map[int]float64) (
	WalkResult, error) {
	if err := VerifyDecisionTree(nodes); err != nil {
		return WalkResult{}, err
	}
	st0 := 0.0 // 0x101db964  fld dword [0x10575674]
	i := 0
	var path []int
	seen := 0
	for {
		path = append(path, i)
		seen++
		if seen > 4*len(nodes)+8 {
			return WalkResult{}, errf("decision tree walk does not terminate")
		}
		nd := nodes[i]
		if nd.Metric == MetricTerminal {
			if nd.Class >= 3 { // 0x101dbb04  cmp ecx, 3
				return WalkResult{TerminalNode: i, ToneValue: 2, SceneClass: 3,
					Path: path}, nil
			}
			return WalkResult{TerminalNode: i, ToneValue: 1,
				SceneClass: nd.Class, Path: path}, nil
		}
		if nd.Metric >= 2 && nd.Metric <= 30 {
			st0 = metrics[nd.Metric]
		}
		if st0 >= nd.Threshold {
			i = nd.Greater
		} else {
			i = nd.LessEqual
		}
	}
}

// ---------------------------------------------------------------------------
// 0x101da6b0 — the parameter check
// ---------------------------------------------------------------------------

// flt0999 is the float32 nearest 0.999. It is built from the exact bit pattern
// at 0x1059a310 because 0.999 as a float64 is a DIFFERENT number and the
// comparison is an inclusive fcomp against the float32.
var flt0999 = float64(math.Float32frombits(0x3F7FBE77))

// CheckParams is 0x101da6b0 — returns nil, or an error naming the bad field.
// The bounds are the immediates at 0x1059a2f8..0x1059a33c; every shipped
// toneHelper-*.dpi passes.
func CheckParams(p Params) error {
	type chk struct {
		name   string
		lo, hi float64
		hasHi  bool
		idx    int
	}
	checks := []chk{
		{"maxValue", 0, 0, false, 1},
		{"thresholdMultiplier", 1.0, 2.0, true, 2},
		{"thresholdReductionFactor", 0.5, flt0999, true, 3},
		{"minEdgeThreshold", 0, 0, false, 4},
		{"minEdgeRatio", 0.0, 1.0, true, 5},
		{"smoothingSizeFactor", 1.0, 10.0, true, 6},
		{"smoothingSigma", 1.0, 50.0, true, 7},
	}
	value := func(name string) float64 {
		switch name {
		case "maxValue":
			return float64(p.MaxValue)
		case "thresholdMultiplier":
			return p.ThresholdMultiplier
		case "thresholdReductionFactor":
			return p.ThresholdReductionFactor
		case "minEdgeThreshold":
			return float64(p.MinEdgeThreshold)
		case "minEdgeRatio":
			return p.MinEdgeRatio
		case "smoothingSizeFactor":
			return p.SmoothingSizeFactor
		default:
			return p.SmoothingSigma
		}
	}
	for _, c := range checks {
		v := value(c.name)
		var bad bool
		if !c.hasHi {
			bad = v < c.lo
		} else {
			bad = !(f32(c.lo) <= f32(v) && f32(v) <= f32(c.hi))
		}
		if bad {
			return errf("Bad field(#%d) in AnsToneHelperParams structure! "+
				"[AnsToneHelperCapabilityImpl::analyze, %s:105]", c.idx,
				srcFileImpl)
		}
	}
	return nil
}

// AllocateMemory is AnsToneHelperCapabilityImpl::allocateMemory (0x101dabe0),
// sizes only. The width < 1 || height < 1 branch — which is exactly what the
// histogram-fed entry point takes, since 0x101dd254 passes (-1, -1) —
// allocates only the four value-indexed buffers and skips every image-sized
// one. It also zeroes the whole AnsToneHelperResults window, which is why
// nPixels and threshold are 0 on the histogram-fed path.
func AllocateMemory(p Params, width, height int) map[string]int64 {
	n := p.MaxValue + 1
	sizes := map[string]int64{
		"_lumHist":  n * 4, // impl+0x88
		"_edgeHist": n * 4, // impl+0x98
		"_distHist": n * 4, // impl+0xa4
		"_toneLut":  n * 2, // impl+0xac
	}
	if width >= 1 && height >= 1 {
		sizes["_imageBuf"] = int64(width) * int64(height) * 2
		sizes["_lapBuf"] = int64(width) * int64(height) * 2
	}
	return sizes
}

// ---------------------------------------------------------------------------
// the entry points
// ---------------------------------------------------------------------------

// Results is the 0xbc bytes 0x1010bb40 rep-movsds into the shell's buffer.
type Results struct {
	NPixels         int64
	Threshold       int64
	Lum             MetricGroup
	Edge            MetricGroup
	Exposure        float64
	TerminalNode    int
	ToneHelperValue int // <-- the ONE field that crosses the shell boundary
	SceneClass      int
	BufferSizes     map[string]int64
	Path            []int
}

// AnalyzeWithHistograms is AnsToneHelperCapabilityImpl::analyze (0x101dd1b0),
// reached through Cap 0x1010c3b0 from analyzeAutoTone's th.acquireHist call
// site (0x100fc36a). This is the variant that runs on the shipped CN-Enhanced
// path.
//
// hasExposure models whether the shell's &ctx[0x4bc] pointer was non-NULL; a
// NULL pointer becomes 0.
func AnalyzeWithHistograms(p Params, lumHist, edgeHist, toneLut []int64,
	exposure float64, hasExposure bool) (*Results, error) {
	if err := CheckParams(p); err != nil {
		return nil, err
	}
	n := int(p.MaxValue) + 1
	res := &Results{SceneClass: 2}
	res.BufferSizes = AllocateMemory(p, -1, -1)
	if hasExposure {
		res.Exposure = f32(exposure)
	}

	fit := func(src []int64) []int64 {
		out := make([]int64, n)
		copy(out, src)
		return out
	}
	lum, edge, lut := fit(lumHist), fit(edgeHist), fit(toneLut)

	if len(p.Nodes) == 0 {
		return nil, errf("no decision tree loaded; toneHelper cannot walk")
	}

	lumG, edgeG, err := ComputeMetrics(p, lum, edge, lut)
	if err != nil {
		return nil, err
	}
	res.Lum, res.Edge = lumG, edgeG
	metrics := MetricsByID(lumG, edgeG, res.Exposure)
	walk, err := WalkDecisionTree(p.Nodes, metrics)
	if err != nil {
		return nil, err
	}
	res.TerminalNode = walk.TerminalNode
	res.ToneHelperValue = walk.ToneValue
	res.SceneClass = walk.SceneClass
	res.Path = walk.Path
	return res, nil
}

// AnalyzeFromImage is AnsToneHelperCapabilityImpl::analyze (0x101dcc50) — NOT
// ported, exactly as the Python is not. It needs 0x101dbc00, the image-side
// histogram/edge-threshold builder, and the shell only calls this variant when
// cna produced no edge histogram (0x100fc334), which never happens on the
// shipped colour-negative path.
func AnalyzeFromImage() error {
	return errf("the image-side histogram/edge builder (%#x) is not ported; "+
		"see pakon_toneHelper.analyze_from_image for the orchestration and why "+
		"shipping an unchecked edge detector was refused", VABuildHistograms)
}
