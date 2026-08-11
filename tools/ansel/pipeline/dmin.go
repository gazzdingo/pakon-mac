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

// --------------------------------------------------------------------------
// FindDmin's window — which pixels are film?
// --------------------------------------------------------------------------
//
// FindDmin is a 99.9th-percentile walk, so "the code above which 0.1 % of the
// pixels lie" is the clear film base ONLY IF the population it walks is film.
// Walking a whole capture instead is what makes it return its "no valid Dmin"
// sentinel on captures that are correctly exposed.
//
// WHAT IS THE VENDOR'S AND WHAT IS OURS — read this before citing any of it.
//
//	[VERIFIED, vendor] The walk itself: findDminCodeFromHist @
//	    0x100093f0…0x1000941f, thr = n/1000, and the 0 sentinel. Untouched.
//	[VERIFIED, vendor] The CCD window. docs/53 §3.4 marks it [VERIFIED]:
//	    DpiBase16_35 is programmed at pixel offset 62, and the same section
//	    says in as many words that "our port's 32 / 2000 corresponds to no
//	    vendor configuration". Both facts predate this code.
//	[INFERRED] That the vendor never has this problem because FindDmin is fed
//	    a detected scene's AREA IMAGE — the frame +0x6cac/+0x6cb0/+0x6cb4
//	    citation below — so leader and run-in are excluded by its framing and
//	    not by any test like the one here. That citation is this file's own
//	    and was NOT re-checked against the binary for this change: there is no
//	    TLA.dll/TLB.dll in the repo or on this machine, and only r2 is
//	    installed, no r2ghidra.
//	[OURS] Everything else here: the window as a named thing, the
//	    saturated-line test, its threshold, and the minimum-film guard. No
//	    vendor call site computes any of it — see FilmBaseWindowPorted.
//
// Measured over captures/:
//
//	strip_cal.bin      0.29 / 0.43 / 0.35 % of pixels at the 4095 ceiling, ALL
//	                   of it in CCD columns 0..45. The sensor never saturates
//	                   on this capture — 0.0000 % at raw 16383.
//	gold400.bin        6.72 / 6.75 / 6.76 %, ALL of it in lines 0..2105, which
//	                   are 95-100 % clipped: the clear leader, which DOES
//	                   saturate the sensor (4.9 / 6.3 / 6.4 % at raw 16383).
//	                   That is correct hardware behaviour, not over-exposure.
//	scan-…-181450.bin  0.000 / 0.027 / 0.013 %, i.e. under the 0.1 % threshold
//	                   only by margin, and its clipping is in the head too.
//
// Cite tools/pakon_decode.py:film_base_window, which this mirrors.

// FilmBaseWindowPorted: no DLL call site computes this window. The vendor does
// not need one — on the [INFERRED] reading above its framing decides where
// film is before FindDmin runs. Ours does not: find_frames splits gold400's
// fully saturated leader into (0,900), (900,1800), (1800,2771) and calls them
// frames. Same status as F135InvertPorted: the constants are the vendor's, the
// arrangement is ours.
const FilmBaseWindowPorted = false

const (
	// VendorCcdPixelOffset is the first CCD pixel TLB ever digitises at
	// DpiBase16_35. docs/53 §3.4 [VERIFIED]: FN_bBeforeScan (0x1002df4e) and
	// FN_bDrvInitCcd (0x1002d6f5) both program idx4 = 62, idx5 = 2062, and
	// the one registry key that tunes it is clamped to [6, 650].
	VendorCcdPixelOffset = 62

	// DefaultCcdPixelOffset is what this port programs
	// (tools/pakon_scan.py:ScanConfig.pixel_offset). docs/53 §3.4 flags it in
	// as many words: "our port's 32 / 2000 corresponds to no vendor
	// configuration". Capture column i is CCD pixel offset+i, so at 32 the
	// first 30 columns of every line are pixels the vendor never digitises.
	// They sit in the illumination roll-off, which is why the unit flat-field
	// has to amplify them 17-24x (gain[0] = 17.2 / 19.6 / 24.5 against 0.94
	// mid-line) and why ordinary film density lands on the ceiling there.
	DefaultCcdPixelOffset = 32

	// FilmBaseLineSaturation is OURS, not the vendor's — see
	// FilmBaseWindowPorted. A line saturated across this much of the aperture
	// is clear leader or empty gate, not film: film is never more transparent
	// than its own base. On gold400 the split is at least not a judgement
	// call — 29 076 lines have exactly zero clipped pixels, 2 095 are 95-100 %
	// clipped, and 32 lines are anywhere in between, so anything from 2 % to
	// 50 % puts the film base within 5 codes of the same answer.
	FilmBaseLineSaturation = 0.5

	// FilmBaseMinFilmFraction: nothing can tell a saturated line of film from
	// a saturated line of leader. What separates a capture with a leader from
	// one that is simply blown is how much of it goes. Below this much
	// surviving film the window has stopped being a window, so the
	// measurement is refused rather than taken from whatever survived.
	FilmBaseMinFilmFraction = 0.5
)

// CcdAxis says which axis of a frame grid indexes CCD pixels.
//
// It has to be stated, not guessed. A -raw-in blob is on the capture's own
// grid — y = scan line, x = CCD pixel — which is what tools/pakon_parity.py
// writes. A TIFF has already been through pakon_decode.to_frame_image, which
// resamples the transport axis and rot90s it, so there y = CCD pixel. Getting
// this wrong would trim 30 scan lines off a frame instead of 30 dead columns.
type CcdAxis int

const (
	CcdAxisUnknown CcdAxis = iota // no window: measure over everything
	CcdAxisX                      // x indexes CCD pixels (the capture's grid)
	CcdAxisY                      // y indexes CCD pixels (a decoded TIFF)
)

// DminWindow is the film area of one (H, W) grid.
type DminWindow struct {
	H, W int
	Axis CcdAxis
	// Col0 is the first CCD pixel inside the vendor's window — normally
	// VendorCcdPixelOffset minus the capture's own programmed pixel offset.
	Col0 int
}

// FilmBaseCol0 is the first capture column inside the vendor's CCD window.
// Derived, not hardcoded: 30 for every capture taken at this port's offset of
// 32, and 0 the day one is taken at the vendor's own 62.
func FilmBaseCol0(pixelOffset int) int {
	if pixelOffset <= 0 {
		pixelOffset = DefaultCcdPixelOffset
	}
	if d := VendorCcdPixelOffset - pixelOffset; d > 0 {
		return d
	}
	return 0
}

// filmAreaMask marks the plane indices FindDmin may look at: inside the
// vendor's CCD window, and not on a transport line saturated right across it.
// It returns the mask, the number of film lines, and the number of transport
// lines in total.
//
// An unknown axis or a geometry that does not match the planes means no
// window — the same answer as before, never a silently wrong one.
func filmAreaMask(planes [3][]int, win DminWindow, nBins int) ([]bool, int, int) {
	n := len(planes[0])
	mask := make([]bool, n)
	if win.Axis == CcdAxisUnknown || win.H <= 0 || win.W <= 0 || win.H*win.W != n {
		for i := range mask {
			mask[i] = true
		}
		return mask, 0, 0
	}
	ceil := nBins - 1
	// nLines counts along the transport axis; idx(line, ccd) is the flat
	// plane index of one pixel.
	nLines, nCcd := win.H, win.W
	idx := func(line, ccd int) int { return line*win.W + ccd }
	if win.Axis == CcdAxisY {
		nLines, nCcd = win.W, win.H
		idx = func(line, ccd int) int { return ccd*win.W + line }
	}
	col0 := win.Col0
	if col0 < 0 || col0 >= nCcd {
		col0 = 0 // degenerate window; never trim the frame away
	}
	aperture := nCcd - col0
	film := 0
	for line := 0; line < nLines; line++ {
		sat := 0
		for ccd := col0; ccd < nCcd; ccd++ {
			i := idx(line, ccd)
			if planes[0][i] >= ceil || planes[1][i] >= ceil || planes[2][i] >= ceil {
				sat++
			}
		}
		if float64(sat) >= FilmBaseLineSaturation*float64(aperture) {
			continue // clear leader / empty gate: no film base in this line
		}
		film++
		for ccd := col0; ccd < nCcd; ccd++ {
			mask[idx(line, ccd)] = true
		}
	}
	return mask, film, nLines
}

// FilmBaseFromPlanes is FindDmin over the film area — the same window
// tools/pakon_decode.py:film_base_codes measures over. It also reports the
// clipped percentage INSIDE that window, which is the number the refusal has
// to quote: clipping outside it is the leader and the gate edge, and neither
// is a statement about exposure.
//
// It returns FindDmin's own 0 sentinel when too little film survives, so the
// one refusal in CheckFilmBase covers that case too. It does NOT decide which
// frames to measure over: the film base is the ROLL's, and this narrows which
// pixels of what it is handed are film, never which frames.
func FilmBaseFromPlanes(planeR, planeG, planeB []int, nBins int,
	win DminWindow) (base [3]int, clip [3]float64, filmLines, totalLines int) {

	planes := [3][]int{planeR, planeG, planeB}
	mask, filmLines, totalLines := filmAreaMask(planes, win, nBins)
	hist := [3][]int{
		make([]int, nBins), make([]int, nBins), make([]int, nBins),
	}
	nPix := 0
	var ceilCount [3]int
	for i, keep := range mask {
		if !keep {
			continue
		}
		nPix++
		for c := 0; c < 3; c++ {
			hist[c][planes[c][i]&(nBins-1)]++
			if planes[c][i] >= nBins-1 {
				ceilCount[c]++
			}
		}
	}
	if nPix > 0 {
		for c := 0; c < 3; c++ {
			clip[c] = 100.0 * float64(ceilCount[c]) / float64(nPix)
		}
	}
	enough := nPix > 0 && (totalLines == 0 ||
		float64(filmLines) >= FilmBaseMinFilmFraction*float64(totalLines))
	if !enough {
		return [3]int{0, 0, 0}, clip, filmLines, totalLines
	}
	thr := findDminThrNPixels(nPix)
	for c := 0; c < 3; c++ {
		base[c] = findDminCodeFromHist(hist[c], thr, nBins)
	}
	return base, clip, filmLines, totalLines
}

// frameDminRgbFromPlanes is FindDmin → frame +0x6cac/+0x6cb0/+0x6cb4, over
// every pixel it is handed. Prefer FilmBaseFromPlanes: on this port's captures
// a bare walk measures the gate edge and the leader as if they were film.
func frameDminRgbFromPlanes(planeR, planeG, planeB []int, nBins int) [3]int {
	return [3]int{
		findDminCodeFromSamples(planeR, nBins),
		findDminCodeFromSamples(planeG, nBins),
		findDminCodeFromSamples(planeB, nBins),
	}
}
