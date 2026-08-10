package main

import (
	"math"
)

const (
	InvSqrt3 = 0.5773502717125849
	InvSqrt6 = 0.40824829759439285
	InvSqrt2 = 0.7071067623730956
	Sqrt2Over3 = 0.8164965951887857
	Sqrt3    = 1.7320508
	Scale001 = 0.0010000000474974513
	OneThird = 1.0 / 3.0
	
	RgbScale = 0x186A0
	MagicY   = 0x306E8227
	MagicC1  = 0x111F883D
	MagicC2  = 0x3B510A6F
	BiasY    = 0x1524A
	BiasC1   = 0x1DE6A
	BiasC2   = 0x11436
)

type OpponentYUV struct {
	Y float64
	U float64
	V float64
}

func ftol2(x float64) int {
	return int(math.Trunc(x))
}

func clamp(val, min, max float64) float64 {
	if val < min { return min }
	if val > max { return max }
	return val
}

func i16(x int) int {
	x &= 0xFFFF
	if x >= 0x8000 { return x - 0x10000 }
	return x
}

func i32(x int64) int64 {
	x &= 0xFFFFFFFF
	if x >= 0x80000000 { return x - 0x100000000 }
	return x
}

func msvcMagicDiv(value, magic int64, sar uint) int64 {
	a := i32(value)
	b := i32(magic)
	prod := a * b
	edx := prod >> 32
	edx >>= sar
	sign := int64(0)
	if edx < 0 { sign = 1 }
	return edx + sign
}

func biasedScale(rgbTerm, bias int64) int64 {
	t := rgbTerm * RgbScale
	if t >= 0 {
		return t + bias
	}
	return t - bias
}

func fosOpeningAxes(r, g, b int) (int, int, int) {
	r, g, b = i16(r), i16(g), i16(b)
	y := int(msvcMagicDiv(biasedScale(int64(r+g+b), BiasY), MagicY, 15))
	c1 := int(msvcMagicDiv(biasedScale(int64(2*g-b-r), BiasC1), MagicC1, 14))
	c2 := int(msvcMagicDiv(biasedScale(int64(b-r), BiasC2), MagicC2, 15))
	return y, c1, c2
}

func axisToCode(axis int, bias, magic int64, sar uint, scale int64) int {
	t := int64(axis) * scale
	term := t - bias
	if t >= 0 { term = t + bias }
	return int(msvcMagicDiv(term, magic, sar))
}

func fosOpeningAxesInverse(y, c1, c2 int) (int, int, int) {
	yc := axisToCode(y, BiasY, MagicY, 15, RgbScale)
	c1c := axisToCode(c1, BiasC1, MagicC1, 14, RgbScale)
	c2c := axisToCode(c2, BiasC2, MagicC2, 15, RgbScale)
	c1x2 := axisToCode(c1, BiasC1, MagicC1, 14, 0x30D40)
	r := yc - c1c - c2c
	g := yc + c1x2
	b := yc - c1c + c2c
	return r, g, b
}

func pivot(rgb [3]int) [3]int {
	p := 1550 // SETSHIFTS_PIVOT_0x60E
	return [3]int{i16(p - rgb[0]), i16(p - rgb[1]), i16(p - rgb[2])}
}

func lookup3BandPlanar(idxRgb [3]int, planar []int, numLut int) [3]int {
	rI, gI, bI := i16(idxRgb[0]), i16(idxRgb[1]), i16(idxRgb[2])
	return [3]int{
		i16(planar[rI]),
		i16(planar[gI+numLut]),
		i16(planar[bI+2*numLut]),
	}
}

func SetShifts12(shiftsA, shiftsB [3]int, planarLut []int, numLut int) [3]int {
	aP := pivot(shiftsA)
	lutRgb := lookup3BandPlanar(aP, planarLut, numLut)
	y, _, _ := fosOpeningAxes(lutRgb[0], lutRgb[1], lutRgb[2])
	bP := pivot(shiftsB)
	_, c1, c2 := fosOpeningAxes(bP[0], bP[1], bP[2])
	r, g, b := fosOpeningAxesInverse(y, c1, c2)
	return pivot([3]int{r, g, b})
}

func ApplyBalanceShifts(rpd12 []int, shifts [3]int) []int {
	out := make([]int, 3)
	for c := 0; c < 3; c++ {
		val := rpd12[c] + shifts[c]
		if val < 0 { val = 0 }
		if val > 4095 { val = 4095 }
		out[c] = val
	}
	return out
}

func preferenceRgbToOpponent(r, g, b int) OpponentYUV {
	rd, gd, bd := float64(r), float64(g), float64(b)
	return OpponentYUV{
		Y: (rd + gd + bd) * InvSqrt3,
		U: (2.0*gd - rd - bd) * InvSqrt6,
		V: (bd - rd) * InvSqrt2,
	}
}

func preferenceOpponentToRgb(y, u, v float64) (float64, float64, float64) {
	ys := y * InvSqrt3
	us := u * InvSqrt6
	vs := v * InvSqrt2
	r := ys - us - vs
	g := ys + u*Sqrt2Over3
	b := ys - us + vs
	return r, g, b
}

func helper1028c540(r, g, b int) (float64, float64, float64) {
	m := float64(r+g+b) * Scale001 * OneThird
	out1 := (float64(g)*Scale001 - m) * InvSqrt2
	out2 := (float64(b)*Scale001 - float64(r)*Scale001) * InvSqrt6
	return m, out1, out2
}

func preferenceCombineYuv(opening, fpaOpp OpponentYUV, dy, du, dv float64, helper [3]float64, scale float64) OpponentYUV {
	m, o1, o2 := helper[0], helper[1], helper[2]
	idy := float64(ftol2(dy))
	idu := float64(ftol2(du))
	idv := float64(ftol2(dv))
	return OpponentYUV{
		Y: opening.Y + fpaOpp.Y + m*idy,
		U: opening.U + fpaOpp.U + scale*idu + o1*idy,
		V: opening.V + fpaOpp.V + scale*idv + o2*idy,
	}
}

func clampPreferenceSPrime(t, lim46, lo42, hi44 float64) float64 {
	s := lim46 - t
	if s < lo42 { return lo42 }
	if s > hi44 { return hi44 }
	return s
}

func preferenceShiftsFromCombined(combined OpponentYUV, w1e, lim46, lo42, hi44 float64) [3]int {
	t := combined.Y - w1e
	sPrime := clampPreferenceSPrime(t, lim46, lo42, hi44)
	r, g, b := preferenceOpponentToRgb(sPrime, -combined.U, -combined.V)
	return [3]int{ftol2(r), ftol2(g), ftol2(b)}
}

func PreferenceShiftsMode0x11(fpo, fpa [3]int, lim46, lo42, hi44 float64, pcls int) [3]int {
	neu := [3]int{975, 975, 975}
	neo := [3]int{1010, 1010, 1010}
	nonFlashAdj := 0
	
	opening := preferenceRgbToOpponent(fpo[0], fpo[1], fpo[2])
	fpaOpp := preferenceRgbToOpponent(fpa[0], fpa[1], fpa[2])
	
	aimY := opening.Y
	w1e := float64(pcls)
	dy := w1e + aimY - opening.Y
	
	helperRgb := neu
	if dy > 0.0 { helperRgb = neo }
	m, o1, o2 := helper1028c540(helperRgb[0], helperRgb[1], helperRgb[2])
	
	scale := float64(nonFlashAdj) * Scale001
	combined := preferenceCombineYuv(opening, fpaOpp, dy, 0.0, 0.0, [3]float64{m, o1, o2}, scale)
	
	return preferenceShiftsFromCombined(combined, w1e, lim46, lo42, hi44)
}

func lim46FromNbp(nbp int) float64 {
	return float64(int(math.Round(float64(nbp) * math.Sqrt(3.0))))
}

func clampLimitsFromNeutralButton(nb int, under, over float64) (float64, float64) {
	return float64(math.Round(float64(nb) * under)), float64(math.Round(float64(nb) * over))
}

func PreferenceShiftsFromDpiFields(fpo, fpa [3]int, nbp, nb int, under, over float64, pcls int) [3]int {
	lim46 := lim46FromNbp(nbp)
	lo42, hi44 := clampLimitsFromNeutralButton(nb, under, over)
	return PreferenceShiftsMode0x11(fpo, fpa, lim46, lo42, hi44, pcls)
}
