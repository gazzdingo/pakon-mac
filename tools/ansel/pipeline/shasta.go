package main

import (
	"fmt"
	"os"
	"sort"
)

// ShastaAnalyzePorted records that AnsShastaCapabilityImpl::analyze
// (0x101e5250…0x101e5ca0) and its Cap wrap 0x101ed9b0 are NOT ported here.
// ShastaToneRpd below is a stand-in, not the vendor's curve.
//
// It stays false, and NOT merely because the port is unfinished. Since this
// was written, analyze's image stage (0x1027be10 — prep 0x1027b1c0, the
// percentile pass 0x1027b970 including the real Iem histogram fill 0x104ea940,
// the planar means 0x1027b3c0, 0x102935d0, and the builder 0x10293ee0) HAS
// been ported and is Unicorn-verified bit-exact end to end, whole toneLut
// included, in tools/ansel/python-pipeline/pakon_shasta_analyze_golden.py.
// It is deliberately not wired in here, because:
//
// SHASTA DOES NOT RUN FOR A COLOUR NEGATIVE. The processing path is chosen by
// name in CiColorCorrectionAnsel::bStartNewRoll (0x10001e70, reached from the
// export PIAnselStartNewRoll 0x100183a0) through the jump table at 0x10002270
// = [0x1000205f, 0x10001f93, 0x10001f93, 0x10001f24, 0x10001ff9], whose five
// handlers push exactly "DC-Premium", "CN-Enhanced", "CN-Enhanced",
// "CN-Lockbeam", "CP-Balance". No case yields CN-Premium; the string
// "CN-Premium" (0x1057a048) has ONE code reference in the whole DLL —
// 0x1004f6e7, inside its own path registration. AnsShastaCapabilityImpl::analyze
// has one caller (0x1010d941) and zero data/vtable references, and the chain
// above it bottoms out at analyzeWithShastaTriage 0x10116040, whose only two
// callers are 0x10057111 (CN-Premium.cpp) and 0x100739a3 (DC-Premium.cpp).
// AnsShastaCapability::acquire 0x1010dff0 likewise has only those two owners
// (0x100503fe / 0x1006df66).
//
// A negative's tone stage is ColorNegativePath::analyzeAutoTone 0x100fb730 —
// one caller, 0x10069a1d inside AnsCnEnhancedPath::CnEnhanced_analyzeSceneSpecific
// — which acquires cna, dra, toneHelper, contrast, ast, pfd and citras, and
// never shasta. That is also why AnsCnEnhancedPath::exportParameterPack
// carries no Shasta operand.
//
// So ShastaToneRpd is standing in for analyzeAutoTone, not for Shasta.
// Replacing it with a (correct) Shasta curve would put a stage on the render
// path that the scanner never runs for this film. 0x100fb730 plus the shipped
// ansel-toneHelper-default / ansel-contrast-CNEnhanced DPIs are the real
// target for the crushed-shadow / warm-shift symptom.
const ShastaAnalyzePorted = false

// ShastaOnCnRenderPath records the fork above: false for a colour negative
// (CN-Enhanced), true only for CN-Premium / DC-Premium, neither of which the
// F-135/F-235/F-335 host selects for negative film.
const ShastaOnCnRenderPath = false

// AutoTonePorted records whether ColorNegativePath::analyzeAutoTone
// (PakonIMAu.dll:0x100fb730, \Atc\ansel\src\libPaths.ansel\cnMethods.cpp) —
// the negative's real tone stage, which ShastaToneRpd below stands in for —
// has been ported. It has NOT. Nothing below is a guess; it is all read out of
// the binary, and it is recorded so the next attempt starts from here.
//
// WHAT analyzeAutoTone IS
//
// It is not one algorithm. It is an orchestrator that chains SIX separate
// capability subsystems, each with its own …CapabilityImpl::analyze, its own
// DPI parser and its own data files. It threads one tone object through them
// via the CN context (ctx+0x64d0, seeded 0 at 0x100fb787 and re-stored after
// every stage) plus a second scalar in ctx+0x4bc:
//
//	stage  capability   acquire      Impl::analyze   data file (via its .map)
//	  1    cna          0x10132dc0   0x1022ea50      cna/ansel-cna-default-default.dpi
//	  2    dra          0x10131100   0x1022af20      dra/ansel-dra-default-default.dpi + 6 *.ttc
//	  3    toneHelper   0x1010c6a0   0x101dcc50      toneHelper/toneHelper-default.dpi + AllOnTree1/deiTree1
//	  4    contrast     0x1010ad20   0x101d8240      contrast/contrast-CNEnhanced.dpi
//	  5    ast          0x1012f3f0   0x10227160      (no dataPathItems dir — built-in defaults)
//	  6    citras       —            0x10223860      (no dataPathItems dir — built-in defaults)
//
// A seventh, pfd, is acquired at 0x100fbc1c but ColorNegativePath::declareAutoTone
// (0x100f95f0) sets its enable byte +0xc/+0xd to 0 at 0x100f9da2/0x100f9dad
// while setting all six above to 1 (0x100f9723, 0x100f98ad, 0x100f9a37,
// 0x100f9b0e, 0x100f9be5, 0x100f9cd8). analyzeAutoTone tests that same +0xc
// byte before each stage, so pfd is dead and the other six all run.
//
// WHY IT IS NOT PORTED
//
// Reachability from 0x100fb730 following direct calls is 166 functions /
// 67,896 bytes of code with 615 indirect (vtable) call sites. For scale, the
// whole of AnsShastaCapabilityImpl::analyze — a single capability, and a full
// task's work, see pakon_shasta_analyze_golden.py — is 189 functions / 44,427
// bytes / 386 indirect. This is six of those, and it is not separable: a
// half-ported chain would put a worse transform on the render path than the
// stand-in does, so nothing is wired in until the whole chain is bit-exact.
//
// It is also not a pure function of the image. The chain runs 17th of the 30
// capabilities AnsCnEnhancedPath::declare (0x10064d70) registers — after
// filmLut, flesh, pan, fos, scpLut, afterSCPLutSba, area, orderOrientation,
// asea, noiseTable, pnr, nra, dei, dtt, falloff and fugc — and reads what they
// published through AnsSceneContext::find (0x10022a40, directly reachable).
// toneHelper's own DPI names decisionTreeDei = deiTree1, i.e. it consumes the
// dei stage. So porting analyzeAutoTone bit-exactly means porting its
// producers too; it cannot be verified end-to-end in isolation.
//
// (One lookup, AnsDraCapabilityImpl::analyze's guarded find("lighting") at
// 0x1022b2e5→0x1022b314, whose miss is fatal at 0x1022b35b, cannot be
// satisfied on this path at all — "lighting" is not in CN-Enhanced's declared
// capability list — so that branch must not be taken for a negative. Worth
// re-deriving before trusting any port of dra.)
//
// DATA — the toneHelper file the earlier note could not find
//
// toneHelper IS DPI-file-driven, and the file was simply never copied.
// vendor/ reproduces only the subdirectories the pipeline already read;
// toneHelper/ was not one of them. toneHelper.map keys on _AnselPath_ and maps
// "CN-Enhanced" → ansel-toneHelper-default, i.e. toneHelper-default.dpi (NOT
// toneHelper-CNPremium.dpi — CN-Premium and CN-Enhanced differ only in
// decisionTree, dTree1 vs AllOnTree1). That file, its map, its six decision
// trees, and the equally-missing cna/ and dra/ data have now been copied from
// the F-X35 COM SERVER install into vendor/ansel/anselinstalldir/dataPathItems/.
// Nothing reads them yet. ast and citras have no dataPathItems directory in a
// full install at all, so those two are not DPI-file-driven.
//
// WHAT THE STAND-IN IS DOING TO THE PICTURE, MEASURED
//
// On captures 08_raw14, the stand-in takes the pre-tone (fugc) RPD-12 means
// 1985.8/2179.8/2269.8 down to 1442.9/1362.3/1333.6 and clips: the toned tap
// spans the full 0…4095 and 8.65 % of its samples land under code 257 (= 16
// of 255). Bypassing the stage entirely renders 215.7/231.4/235.3 with 0.00 %
// of samples under 16 — far too light, so the stage is load-bearing and the
// crush is the stand-in's own hard two-anchor clip, not the ICC hop.
const AutoTonePorted = false

// ShastaParams are the fields of anselinstalldir/dataPathItems/shasta/
// shasta-rpd.dpi — the DPI shasta.map selects for the colour-negative
// ("CN-Premium") path.
type ShastaParams struct {
	Black          float64 // black = 0
	MetricGray     float64 // metricGray = 1618
	White          float64 // white = 3000
	ShadowPercent  float64 // shadowPercent = 1.0
	MinValue       float64 // minValue = 0
	MaxValue       float64 // maxValue = 4095
}

func ShastaRpdParams() ShastaParams {
	return ShastaParams{
		Black:         0.0,
		MetricGray:    1618.0,
		White:         3000.0,
		ShadowPercent: 1.0,
		MinValue:      0.0,
		MaxValue:      4095.0,
	}
}

// histPercentile returns the value at pct% of a 0…4095 code histogram.
func histPercentile(hist []int, nPix int, pct float64) float64 {
	target := int(pct / 100.0 * float64(nPix))
	cum := 0
	for code := 0; code < len(hist); code++ {
		cum += hist[code]
		if cum > target {
			return float64(code)
		}
	}
	return float64(len(hist) - 1)
}

// ShastaToneRpd is a stand-in for AnsShastaCapabilityImpl::analyze, which is
// not ported (see ShastaAnalyzePorted above for exactly what that means).
//
// The vendor builds a per-scene tone LUT from five measured statistics
// (extShadowPercent 0.1, shadowPercent 1.0, the scene grey, highlightPercent
// 99.0, extHighlightPercent 99.9) moved toward aims placed in "buttons" either
// side of metricGray (blackButtons 10.466, shadowButtons 6.67, highlightButtons
// 3.67, extHighlightButtons 7.68, codeValuesPerButton 75.0) by per-knot
// aggressiveness factors, with exponential slope limits and white-point
// compression. None of that is reproduced here.
//
// This reproduces only two anchors — shadowPercent → black, median →
// metricGray, straight line between them, clamped to [minValue, maxValue].
// Every constant comes from shasta-rpd.dpi, but the SHAPE is not the vendor's.
//
// It runs PER CHANNEL. That is not what a Shasta tone scale is — the vendor
// keeps a single toneLut (int16 vector at AnsShastaCapabilityImpl+0x3e0,
// docs/46) — and the note that used to sit here blamed it on the stage-2
// hand-off not having matched channel contrast. That reason is gone: the
// density inversion in main.go now reproduces the negative's own channel
// contrasts to about 2 %. Running one shared curve was tried and measured, and
// it does not rescue the frame, because the per-channel behaviour here is
// standing in for something else entirely — the roll/scene balance.
//
// What the vendor balances with, and why one curve is not enough yet:
//   * ColorNegativePath::analyzePostBalance (PakonIMAu.dll:0x100fdc40) builds
//     its three shift LUTs at 0x1006c4f0 as lut_c[i] = master[i + shift_c] —
//     ONE curve, three integer translations. Same shape as makeSRALUTS.
//   * The three integer shifts come from ColorNegativePath::setShifts
//     (0x10100260) fed by the roll analysis in analyzeBalanceOrder
//     (0x10101220, called twice per scene). That is Sba(), which is NOT ported
//     — docs/46 lists full Sba() / AnalyseRoll as open. Our shifts come from
//     the sba-*.dpi constants alone, so they carry the stock's nominal mask
//     but nothing measured off this frame.
// Until Sba() is ported, a per-channel stretch here is the stand-in for it.
// It is an honest grey-world normaliser, not a tone scale, and that is the
// next thing to replace.
func ShastaToneRpd(rpd12 [][][3]float64, p ShastaParams) [][][3]float64 {
	height := len(rpd12)
	if height == 0 {
		return rpd12
	}
	width := len(rpd12[0])

	var lo, mid [3]float64
	for c := 0; c < 3; c++ {
		hist := make([]int, 4096)
		n := 0
		for y := 0; y < height; y++ {
			for x := 0; x < width; x++ {
				v := int(rpd12[y][x][c])
				if v < 0 {
					v = 0
				}
				if v > 4095 {
					v = 4095
				}
				hist[v]++
				n++
			}
		}
		lo[c] = histPercentile(hist, n, p.ShadowPercent)
		mid[c] = histPercentile(hist, n, 50.0)
	}
	fmt.Fprintf(os.Stderr, "shasta anchors lo=%v median=%v -> black=%.0f metricGray=%.0f\n",
		lo, mid, p.Black, p.MetricGray)

	out := make([][][3]float64, height)
	for y := 0; y < height; y++ {
		out[y] = make([][3]float64, width)
		for x := 0; x < width; x++ {
			for c := 0; c < 3; c++ {
				span := mid[c] - lo[c]
				if span < 1.0 {
					span = 1.0
				}
				scale := (p.MetricGray - p.Black) / span
				v := (rpd12[y][x][c]-lo[c])*scale + p.Black
				if v < p.MinValue {
					v = p.MinValue
				}
				if v > p.MaxValue {
					v = p.MaxValue
				}
				out[y][x][c] = v
			}
		}
	}
	return out
}

func LinkedPercentileTone(rpd12 [][][3]float64, white float64, shadowPercent, highlightPercent float64, maxValue float64) [][][3]float64 {
	height := len(rpd12)
	if height == 0 {
		return rpd12
	}
	width := len(rpd12[0])

	// Collect per-channel samples
	var ch [3][]float64
	for i := 0; i < height; i++ {
		for j := 0; j < width; j++ {
			p := rpd12[i][j]
			for c := 0; c < 3; c++ {
				ch[c] = append(ch[c], p[c])
			}
		}
	}

	var lo, hi [3]float64
	for c := 0; c < 3; c++ {
		sort.Float64s(ch[c])
		n := len(ch[c])
		loIdx := int((shadowPercent / 100.0) * float64(n-1))
		hiIdx := int((highlightPercent / 100.0) * float64(n-1))
		lo[c] = ch[c][loIdx]
		hi[c] = ch[c][hiIdx]
		if hi[c] <= lo[c] {
			hi[c] = lo[c] + 1.0
		}
	}

	fmt.Fprintf(os.Stderr, "shasta linked lo=%v hi=%v\n", lo, hi)

	out := make([][][3]float64, height)
	for i := 0; i < height; i++ {
		out[i] = make([][3]float64, width)
		for j := 0; j < width; j++ {
			p := rpd12[i][j]
			for c := 0; c < 3; c++ {
				scale := white / (hi[c] - lo[c])
				v := (p[c] - lo[c]) * scale
				if v < 0 { v = 0 }
				if v > maxValue { v = maxValue }
				out[i][j][c] = v
			}
		}
	}
	return out
}
