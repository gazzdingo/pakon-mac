// Package kcmsclut is the Go port of the Kodak CMM's 3-D CLUT interpolator,
// kodakcms.dll fcn.10018160 (md5 e4c8064a9dd3c3a5541d74b00a730e53).
//
// # WHY THIS EXISTS
//
// icc.go's trilinearClut is a trilinear, float64, round-to-nearest ICC mft2
// evaluator. docs/74 §176 drove the real vendor CMM under Wine and established
// that the vendor is none of those three: it is tetrahedral, at 14-bit integer
// precision, with an arithmetic shift (truncation toward -inf) rather than
// rounding. §176's negative controls priced each wrong choice on a 32³ lattice
// of the input domain:
//
//	trilinear instead of tetrahedral   2037 / 98304 samples differ, max |d| 3
//	round-to-nearest instead of SAR    1200 / 98304 samples differ, max |d| 1
//
// # THE REFERENCE
//
// tools/ansel/python-pipeline/pakon_kcms_clut.py is bit-exact against the real
// DLL over the entire u8 RGB input domain — all 16,777,216 triples,
// 50,331,648 channel samples, zero differences (pakon_kcms_clut_golden.py).
// This package is a transcription of it, and tools/test_kcms_clut_ports.py
// re-proves the transcription over the same 16,777,216 triples.
//
// THE ROUTINE, per pixel
//
//	offR, wR = idx[0][r]     (records of {i32 byte offset, i32 weight})
//	offG, wG = idx[1][g]
//	offB, wB = idx[2][b]
//	base = offR + offG + offB
//
//	sort {wR, wG, wB} descending -> (w0, w1, w2); which of the six orderings
//	holds selects one of six tetrahedra and with it two intermediate corner
//	byte offsets (pa, pb)
//
//	for ch in 0, 1, 2:
//	    c = base + 2*ch
//	    A = clut[c];  C = clut[c+pa];  B = clut[c+pb];  D = clut[c+offRGB]
//	    t = (D-B)*w2 + (C-A)*w0 + (B-C)*w1        (signed 32-bit)
//	    out[ch] = otab[ch][4*A + (t >> 14)]       (SAR, i.e. floor)
//
// The grid index and the fraction are not computed per pixel: they come out of
// the precomputed 3×256 table at grid+0x8c, which also absorbs the input curve.
// The 14-bit result is mapped to u8 through a per-channel 16384-entry byte
// table (grid+0x154), so the output transfer curve is exact, not interpolated.
//
// Ranges, measured over the whole u8 domain rather than assumed:
//
//	CLUT word index   0 .. 89372   (table is 89373 words)  — always in range
//	t                 -10,513,533 .. 41,730,541            — never overflows i32
//	otab index        1024 .. 16152 (table is 16384)       — never negative
//
// so nothing here clamps; a clamp would be a deviation from the vendor rather
// than safety. Go's >> on a signed value is defined as an arithmetic shift, so
// t>>14 is the vendor's SAR directly.
package kcmsclut

import "math"

// EvalU8 is fcn.10018160 on one interleaved RGB u8 triple.
//
// The six-way branch is the disassembly's own three signed compares in its own
// order: 0x100182a4 cmp wR,wG / 0x100182ac cmp wG,wB / 0x100182c9 cmp wR,wB.
// Ties go where the vendor's jg/jle pairs send them — note the asymmetry
// (wR > wG but wB >= wR). That is load-bearing, and it is what the exhaustive
// test checks.
func EvalU8(in [3]uint8) [3]uint8 {
	offRi, wR := idxOff[0][in[0]], idxWeight[0][in[0]]
	offGi, wG := idxOff[1][in[1]], idxWeight[1][in[1]]
	offBi, wB := idxOff[2][in[2]], idxWeight[2][in[2]]
	base := offRi + offGi + offBi

	var w0, w1, w2, pa, pb int32
	if wR > wG {
		switch {
		case wG > wB: // wR > wG > wB
			w0, w1, w2, pa, pb = wR, wG, wB, offR, offRG
		case wR > wB: // wR > wB >= wG
			w0, w1, w2, pa, pb = wR, wB, wG, offR, offRB
		default: // wB >= wR > wG
			w0, w1, w2, pa, pb = wB, wR, wG, offB, offRB
		}
	} else {
		switch {
		case wG > wB && wR > wB: // wG >= wR > wB
			w0, w1, w2, pa, pb = wG, wR, wB, offG, offRG
		case wG > wB: // wG > wB >= wR
			w0, w1, w2, pa, pb = wG, wB, wR, offG, offGB
		default: // wB >= wG >= wR
			w0, w1, w2, pa, pb = wB, wG, wR, offB, offGB
		}
	}

	var out [3]uint8
	for ch := int32(0); ch < 3; ch++ {
		c := base + 2*ch
		a := int32(clut[c>>1])
		cc := int32(clut[(c+pa)>>1])
		b := int32(clut[(c+pb)>>1])
		d := int32(clut[(c+offRGB)>>1])
		t := (d-b)*w2 + (cc-a)*w0 + (b-cc)*w1
		out[ch] = otab[ch][4*a+(t>>14)]
	}
	return out
}

// Rpd12ToU8 is the encode the vendor's own profile-Rpd2Srgb.dpi implies
// (dataType U8, colorSpaceMax 255) and that the Python path performs in
// pakon_ansel.rpd12_to_icc_u8:
//
//	u8 = clip(rint(code * 255 / 4095), 0, 255)
//
// np.rint is round-half-to-even and so is math.RoundToEven, on the identical
// float64 expression code * (255.0/4095.0). This is NOT int(x + 0.5), which is
// what icc.go's rpd12ToU16 and IccRpd12ToSrgb8Depth do. For integer codes
// 0..4095 no exact half-way value actually arises, so the tie rule is not
// load-bearing here; it is written this way to match the reference expression
// rather than to approximate it.
func Rpd12ToU8(rpd12 int) uint8 {
	if rpd12 <= 0 {
		return 0
	}
	if rpd12 >= 4095 {
		return 255
	}
	v := math.RoundToEven(float64(rpd12) * (255.0 / 4095.0))
	if v <= 0 {
		return 0
	}
	if v >= 255 {
		return 255
	}
	return uint8(v)
}

// Rpd12ToSrgb8 is the whole ICC hop as the vendor performs it: 12-bit RPD in,
// 8-bit sRGB out. It needs no .pf files — SpCombineXforms already folded both
// profiles into the tables in tables.go.
func Rpd12ToSrgb8(rpd [3]int) [3]uint8 {
	return EvalU8([3]uint8{
		Rpd12ToU8(rpd[0]), Rpd12ToU8(rpd[1]), Rpd12ToU8(rpd[2]),
	})
}

// TetraOf reports which of the six weight orderings an input lands in, using
// the same branch as EvalU8. Exported for the test that shows every
// tetrahedron is actually visited over the domain rather than assumed.
func TetraOf(in [3]uint8) int {
	wR, wG, wB := idxWeight[0][in[0]], idxWeight[1][in[1]], idxWeight[2][in[2]]
	if wR > wG {
		if wG > wB {
			return 0
		}
		if wR > wB {
			return 1
		}
		return 2
	}
	if wG > wB {
		if wR > wB {
			return 4
		}
		return 3
	}
	return 5
}
