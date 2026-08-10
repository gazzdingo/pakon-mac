package main

import (
	"fmt"
	"sort"
)

// ShastaAnalyzePorted records that AnsShastaCapabilityImpl::analyze is NOT
// ported — not here, and not in tools/ansel/pakon_shasta.py either, which
// carries the toneLut assembly but sets ANALYZE False. ShastaToneRpd below is
// a stand-in, not the vendor's curve. Same convention as the *_PORTED flags in
// the Python modules.
const ShastaAnalyzePorted = false

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
// not ported (see tools/ansel/README.md — Shasta ANALYZE is False).
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
	fmt.Printf("DEBUG: shasta anchors lo=%v median=%v -> black=%.0f metricGray=%.0f\n",
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

	fmt.Printf("DEBUG Shasta lo=%v hi=%v\n", lo, hi)

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
