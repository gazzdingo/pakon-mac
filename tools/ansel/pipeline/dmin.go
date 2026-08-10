package main

const TlaFindDminNBins = 0x4000 // 16384

func findDminThrNPixels(nPixels int) int {
	return nPixels / 1000
}

func findDminCodeFromHist(counts []int, thr int, nBins int) int {
	if nBins <= 0 {
		return 0
	}
	code := 0
	cum := 0
	for {
		if code >= 0 && code < len(counts) {
			cum += counts[code]
		}
		if thr < cum {
			break
		}
		code++
		if code == nBins-1 {
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

// findFilmBaseCodeFromSamples is FindDmin walked from the top of the histogram
// instead of the bottom: it returns the code below which only 0.1 % of the
// frame's pixels lie above. On a colour negative that is the clear film base
// (maximum transmission), which is the Dmin the printing density is measured
// against.
func findFilmBaseCodeFromSamples(samples []int, nBins int) int {
	hist := make([]int, nBins)
	nPix := 0
	mask := nBins - 1
	for _, v := range samples {
		hist[v&mask]++
		nPix++
	}
	thr := findDminThrNPixels(nPix)
	cum := 0
	for code := nBins - 1; code > 0; code-- {
		cum += hist[code]
		if thr < cum {
			return code
		}
	}
	return nBins - 1
}

func frameFilmBaseRgbFromPlanes(planeR, planeG, planeB []int, nBins int) [3]int {
	return [3]int{
		findFilmBaseCodeFromSamples(planeR, nBins),
		findFilmBaseCodeFromSamples(planeG, nBins),
		findFilmBaseCodeFromSamples(planeB, nBins),
	}
}

func frameDminRgbFromPlanes(planeR, planeG, planeB []int, nBins int) [3]int {
	return [3]int{
		findDminCodeFromSamples(planeR, nBins),
		findDminCodeFromSamples(planeG, nBins),
		findDminCodeFromSamples(planeB, nBins),
	}
}
