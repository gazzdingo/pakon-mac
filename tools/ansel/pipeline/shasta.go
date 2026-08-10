package main

import (
	"fmt"
	"sort"
)

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
