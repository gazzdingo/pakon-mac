package main

import "fmt"

func aimOffset(word60ec, word60f8Dmin, word60f2Aim int) int {
	v := int16(word60ec) - int16(word60f8Dmin) + int16(word60f2Aim)
	return int(v)
}

func fugcEbp18PolicyPass(arg, params [3]int) bool {
	frac := 0.2
	for i := 0; i < 3; i++ {
		a := float64(arg[i])
		p := float64(params[i])
		lo := frac * p
		hi := p + p
		if a < lo || a > hi {
			return false
		}
	}
	return true
}

func fillSetLutInfoAimWords(aTableDmin, argEbp14, argEbp18, capParamsAim [3]int) ([3]int, [3]int, [3]int) {
	useArgEbp18 := fugcEbp18PolicyPass(argEbp18, capParamsAim)
	w60f8 := aTableDmin
	w60f2 := argEbp14
	var w60ec [3]int
	if useArgEbp18 {
		w60ec = argEbp18
	} else {
		w60ec = capParamsAim
	}
	return w60ec, w60f2, w60f8
}

// setLutInfoChannel is one channel of setLutInfo @ 0x101f82c0.
//
// A NEGATIVE offset is refused rather than approximated. The verified
// fragment covers offset >= 0 only; the previous code fell through its
// bounds check and wrote n-1 (white) for every index, which is a silently
// blown-out channel rather than an error. Cite:
// pakon_fugc.py:set_lut_info_channel, which raises on the same condition.
func setLutInfoChannel(seed []int, offset int, n int) ([]int, error) {
	out := make([]int, n)
	if offset > n-1 {
		for i := 0; i < n; i++ {
			out[i] = i
		}
		return out, nil
	}
	if offset < 0 {
		return nil, fmt.Errorf(
			"setLutInfo offset %d < 0 is not covered by the verified "+
				"0x101f82c0 fragment; refusing rather than inventing a curve",
			offset)
	}
	for i := 0; i < offset; i++ {
		out[i] = offset
	}
	for i := offset; i < n; i++ {
		val := seed[i-offset] + offset
		if val < 0 {
			val = 0
		}
		if val > n-1 {
			val = n - 1
		}
		out[i] = val
	}
	return out, nil
}

func setLutInfo(seedRgb [][3]float32, offsets [3]int, n int) ([][3]float32, error) {
	out := make([][3]float32, n)
	for c := 0; c < 3; c++ {
		seedChan := make([]int, n)
		for i := 0; i < n; i++ {
			if i < len(seedRgb) {
				seedChan[i] = int(seedRgb[i][c])
			} else {
				seedChan[i] = i // identity fallback (pakon_fugc's np.arange seed)
			}
		}
		outChan, err := setLutInfoChannel(seedChan, offsets[c], n)
		if err != nil {
			return nil, fmt.Errorf("channel %d: %w", c, err)
		}
		for i := 0; i < n; i++ {
			out[i][c] = float32(outChan[i])
		}
	}
	return out, nil
}

// BuildSetLutInfoApplyLut is the FUGC mode≠2 path — the one docs/58 §7 lists
// as ported. Returns (applyLut, offsets, aimWords{60ec,60f2,60f8}).
func BuildSetLutInfoApplyLut(seedRgb [][3]float32, aTableDmin, argEbp14, argEbp18, capParamsAim [3]int) ([][3]float32, [3]int, [3][3]int, error) {
	w60ec, w60f2, w60f8 := fillSetLutInfoAimWords(aTableDmin, argEbp14, argEbp18, capParamsAim)
	var offs [3]int
	for c := 0; c < 3; c++ {
		offs[c] = aimOffset(w60ec[c], w60f8[c], w60f2[c])
	}
	applyLut, err := setLutInfo(seedRgb, offs, 4096)
	if err != nil {
		return nil, offs, [3][3]int{w60ec, w60f2, w60f8}, err
	}
	return applyLut, offs, [3][3]int{w60ec, w60f2, w60f8}, nil
}

// signedDiv3 is the DLL's signed division by three: the
// `imul 0x55555556` magic-multiply at PakonIMAu.dll 0x101f7a08, with the
// sign-correction add at 0x101f7a1f. A plain Go `/3` rounds toward zero on
// the same operand and differs from this by one whenever the numerator is
// negative and not a multiple of three, which is exactly the region the
// bias lands in when the aim words are below the Dmin words.
//
// Cite: tools/ansel/python-pipeline/pakon_fugc.py:signed_div3.
func signedDiv3(n int) int {
	a := int32(n)                               // @ 0x101f7a0d
	prod := int64(a) * int64(int32(0x55555556)) // @ 0x101f7a08 / 0x101f7a0d
	hi := int32(prod >> 32)                     // EDX after imul
	if hi < 0 {
		hi++ // @ 0x101f7a1f…
	}
	return int(hi)
}

// FugcWorkBias is 0x101f79b0 → Cap +0x14174 (int16).
//
//	bias = avg3( max(0, int16(60ec_i + arg_i)) ) − avg3( int16(60f8_i) )
//
// This used to be a three-term expression on the GREEN channel alone —
//
//	int16(capParamsAim[1]) - int16(aTableDmin[1]) + int16(argEbp14[1])
//
// — which is not the vendor's. It dropped R and B entirely, dropped the
// per-channel max(0, …) floor at 0x101f79c0 / 0x101f79d2 / 0x101f79e4, and
// dropped the +1 rounding bias inside each division. Measured against the
// correct form it is 350–500 codes out of 4096 on this install's tables.
//
// Note it takes the *resolved* aim word 60ec — the output of
// fillSetLutInfoAimWords, i.e. either the frame's own Dmin (argEbp18) or the
// ParamsDpi aim, whichever the 0x101fc3c4 policy branch selected — not
// capParamsAim unconditionally.
//
// Cite: tools/ansel/python-pipeline/pakon_fugc.py:fugc_work_bias.
func FugcWorkBias(word60ec, word60f8Dmin, argEbp14 [3]int) int {
	sum := 0
	for i := 0; i < 3; i++ {
		v := int(int16(word60ec[i] + argEbp14[i])) // @ 0x101f79b1…
		if v < 0 {                                 // @ 0x101f79c0 / d2 / e4
			v = 0
		}
		sum += v
	}
	avgAim := signedDiv3(sum + 1) // @ 0x101f7a04…0x101f7a24
	d0 := int(int16(word60f8Dmin[0]))
	d1 := int(int16(word60f8Dmin[1]))
	d2 := int(int16(word60f8Dmin[2]))
	avgDmin := signedDiv3(d2 + d1 + d0 + 1) // @ 0x101f7a34…0x101f7a4b
	return int(int16(avgAim - avgDmin))     // @ 0x101f7a4d → +0x14174
}

// mode2ApplyLutPlane is the mode==2 one-plane LUT fill @ 0x101fc7e6…0x101fc8c6
// (Cap +0x6140). Cite: pakon_fugc.py:mode2_apply_lut_plane.
func mode2ApplyLutPlane(seed []int, bias int, n int) []int {
	out := make([]int, n)
	ax := int(int16(bias))             // @ 0x101fc7eb
	seed0 := int(int16(seed[0])) + ax  // @ 0x101fc7fa…801
	last := int(int16(seed[n-1])) + ax // @ 0x101fc812…81a
	if ax >= 0 {                       // @ 0x101fc81d / 0x101fc823
		for i := 0; i < ax && i < n; i++ { // @ 0x101fc827…837
			out[i] = seed0
		}
		for i := ax; i < n; i++ { // @ 0x101fc840…85e
			out[i] = int(int16(seed[i-ax])) + ax
		}
	} else {
		end := ax + n - 1 // @ 0x101fc860…863
		for i := 0; i < end; i++ {
			out[i] = int(int16(seed[i-ax])) + ax
		}
		for i := end; i < n; i++ { // @ 0x101fc890…89c
			if i < 0 {
				continue
			}
			out[i] = last
		}
	}
	for i := 0; i < n; i++ { // @ 0x101fc8a1…8c4 clamp
		if out[i] < 0 {
			out[i] = 0
		} else if out[i] > n-1 {
			out[i] = n - 1
		}
	}
	return out
}

// BuildMode2ApplyLut is the FUGC mode==2 path: aims → bias @ 0x101f79b0 →
// plane LUT @ 0x101fc7e6, with the single plane stacked across RGB for the
// apply. It now runs the same aim-word resolution as the mode≠2 path, so the
// frame Dmin (argEbp18) reaches the bias through the 0x101fc3c4 policy branch
// instead of being discarded.
//
// Returns (applyLut, bias, aimWords) where aimWords is {60ec, 60f2, 60f8}.
func BuildMode2ApplyLut(fugcLut [][3]float32, aTableDmin, argEbp14, argEbp18, capParamsAim [3]int) ([][3]float32, int, [3][3]int) {
	const n = 4096
	w60ec, w60f2, w60f8 := fillSetLutInfoAimWords(aTableDmin, argEbp14, argEbp18, capParamsAim)
	bias := FugcWorkBias(w60ec, w60f8, argEbp14)

	// Python takes seed_rgb[:, 0] — the RED column of the shipped curve —
	// and the shipped fugc-*.lut files are R = G = B, so the choice is not
	// observable on this install. Kept as red to match the port.
	seed := make([]int, n)
	for i := 0; i < n; i++ {
		if i < len(fugcLut) {
			seed[i] = int(fugcLut[i][0])
		} else {
			seed[i] = i // identity tail, as pakon_fugc's np.arange seed
		}
	}

	plane := mode2ApplyLutPlane(seed, bias, n)
	out := make([][3]float32, n)
	for i := 0; i < n; i++ {
		v := float32(plane[i])
		out[i] = [3]float32{v, v, v}
	}
	return out, bias, [3][3]int{w60ec, w60f2, w60f8}
}
