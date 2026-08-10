package main

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

func setLutInfoChannel(seed []int, offset int, n int) []int {
	out := make([]int, n)
	if offset > n-1 {
		for i := 0; i < n; i++ {
			out[i] = i
		}
		return out
	}
	
	for i := 0; i < n; i++ {
		if i < offset {
			out[i] = offset
		} else {
			srcIdx := i - offset
			if srcIdx >= 0 && srcIdx < len(seed) {
				val := seed[srcIdx] + offset
				if val < 0 { val = 0 }
				if val > n-1 { val = n - 1 }
				out[i] = val
			} else {
				out[i] = n - 1
			}
		}
	}
	return out
}

func setLutInfo(seedRgb [][3]float32, offsets [3]int, n int) [][3]float32 {
	out := make([][3]float32, n)
	for c := 0; c < 3; c++ {
		seedChan := make([]int, n)
		for i := 0; i < n; i++ {
			if i < len(seedRgb) {
				seedChan[i] = int(seedRgb[i][c])
			} else {
				seedChan[i] = i // identity fallback
			}
		}
		outChan := setLutInfoChannel(seedChan, offsets[c], n)
		for i := 0; i < n; i++ {
			out[i][c] = float32(outChan[i])
		}
	}
	return out
}

func BuildSetLutInfoApplyLut(seedRgb [][3]float32, aTableDmin, argEbp14, argEbp18, capParamsAim [3]int) ([][3]float32, [3]int) {
	w60ec, w60f2, w60f8 := fillSetLutInfoAimWords(aTableDmin, argEbp14, argEbp18, capParamsAim)
	var offs [3]int
	for c := 0; c < 3; c++ {
		offs[c] = aimOffset(w60ec[c], w60f8[c], w60f2[c])
	}
	applyLut := setLutInfo(seedRgb, offs, 4096)
	return applyLut, offs
}

func BuildMode2ApplyLut(fugcLut [][3]float32, aTableDmin [3]int, argEbp14 [3]int, capParamsAim [3]int) [][3]float32 {
	bias := int(int16(capParamsAim[1]) - int16(aTableDmin[1]) + int16(argEbp14[1]))
	
	seedG := make([]int, 4096)
	for i := 0; i < 4096; i++ {
		if i < len(fugcLut) {
			seedG[i] = int(fugcLut[i][0]) // Plane LUT uses red channel of generic curve for Mode 2? Python says seed_rgb[:, 0]
		} else {
			seedG[i] = i
		}
	}
	
	outPlane := make([]int, 4096)
	seed0 := int(int16(seedG[0])) + bias
	
	if bias >= 0 {
		for i := 0; i < bias; i++ {
			outPlane[i] = seed0
		}
		for i := bias; i < 4096; i++ {
			outPlane[i] = int(int16(seedG[i-bias])) + bias
		}
	} else {
		for i := 0; i < 4096+bias; i++ {
			outPlane[i] = int(int16(seedG[i-bias])) + bias
		}
		for i := 4096 + bias; i < 4096; i++ {
			outPlane[i] = int(int16(seedG[4095])) + bias
		}
	}
	
	for i := 0; i < 4096; i++ {
		if outPlane[i] < 0 { outPlane[i] = 0 }
		if outPlane[i] > 4095 { outPlane[i] = 4095 }
	}
	
	out := make([][3]float32, 4096)
	for i := 0; i < 4096; i++ {
		out[i] = [3]float32{float32(outPlane[i]), float32(outPlane[i]), float32(outPlane[i])}
	}
	return out
}
