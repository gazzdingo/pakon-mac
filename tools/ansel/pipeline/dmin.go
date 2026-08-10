package main

const TlaFindDminNBins = 0x4000 // 16384

func findDminThrNPixels(nPixels int) int {
	// FindDmin threshold (n * 0x10624dd3) >> 38 @ 0x10009362 == n/1000.
	return nPixels / 1000
}

// findDminCodeFromHist is the high-side histogram walk at
// 0x100093f0…0x1000941f. It walks code DOWN from nBins-1 and stops when the
// cumulative count exceeds thr, so it returns the code above which only 0.1 %
// of the frame's pixels lie — on a colour negative that is the clear film
// base, the maximum transmission. If the very first bin already exceeds thr
// the DLL stores 0 (sete / and special case).
//
// Cite: tools/ansel/pakon_scene_context.py:find_dmin_code_from_hist, which is
// Unicorn-golden against the DLL. This file used to walk upward from 0, which
// returned the darkest code instead of the film base.
func findDminCodeFromHist(counts []int, thr int, nBins int) int {
	if nBins <= 0 {
		return 0
	}
	code := nBins - 1
	cum := 0
	for {
		if code >= 0 && code < len(counts) {
			cum += counts[code]
		}
		if thr < cum {
			break
		}
		code--
		if code == 0 {
			break
		}
	}
	if code == nBins-1 {
		return 0
	}
	return code
}

func findDminCodeFromSamples(samples []int, nBins int) int {
	hist := make([]int, nBins)
	nPix := 0
	mask := nBins - 1
	for _, v := range samples {
		hist[v&mask]++
		nPix++
	}
	thr := findDminThrNPixels(nPix)
	return findDminCodeFromHist(hist, thr, nBins)
}

// frameDminRgbFromPlanes is FindDmin → frame +0x6cac/+0x6cb0/+0x6cb4.
func frameDminRgbFromPlanes(planeR, planeG, planeB []int, nBins int) [3]int {
	return [3]int{
		findDminCodeFromSamples(planeR, nBins),
		findDminCodeFromSamples(planeG, nBins),
		findDminCodeFromSamples(planeB, nBins),
	}
}
