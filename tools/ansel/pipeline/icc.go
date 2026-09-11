// icc.go is an ICC v2 mft1/mft2 parser plus a TRILINEAR evaluator.
//
// !! NOT THE VENDOR'S ARITHMETIC — see IccRenderRpd12ToSrgb8 at the bottom.
//
// docs/74 §176 drove the real Kodak CMM (kodakcms.dll, md5
// e4c8064a9dd3c3a5541d74b00a730e53) under Wine and established that its CLUT
// interpolator is tetrahedral, 14-bit integer, and arithmetic-shift (floor).
// trilinearClut below is trilinear, float64 and round-to-nearest — all three
// wrong. §176's negative controls priced each on a 32³ lattice of the domain:
//
//	trilinear instead of tetrahedral   2037 / 98304 samples differ, max |d| 3
//	round-to-nearest instead of SAR    1200 / 98304 samples differ, max |d| 1
//
// The vendor's own arithmetic is in package kcmsclut. This file keeps the
// profile parser (engine.go still loads both profiles, and their grid sizes are
// reported) and the trilinear path as the PAKON_ICC_TRILINEAR=1 escape hatch,
// which exists so the two can be diffed — not because it is a defensible
// fallback.
package main

import (
	"encoding/binary"
	"fmt"
	"os"

	"pakonpipeline/kcmsclut"
)

const (
	ICCMft2Tag = 0x6D667432
	ICCMft1Tag = 0x6D667431
	ICCA2B0Tag = 0x41324230
	ICCB2A0Tag = 0x42324130
)

type IccMft2 struct {
	NIn        int
	NOut       int
	Grid       int
	NTableIn   int
	NTableOut  int
	TableIn    []uint16
	Clut       []uint16
	TableOut   []uint16
}

func iccFindTag(data []byte, sigWant uint32) []byte {
	if len(data) < 132 {
		return nil
	}
	tagCount := binary.BigEndian.Uint32(data[128:])
	dir := 132
	for i := uint32(0); i < tagCount && dir+12 <= len(data); i++ {
		sig := binary.BigEndian.Uint32(data[dir:])
		offset := binary.BigEndian.Uint32(data[dir+4:])
		tagLen := binary.BigEndian.Uint32(data[dir+8:])
		if sig == sigWant && int(offset+tagLen) <= len(data) {
			return data[offset : offset+tagLen]
		}
		dir += 12
	}
	return nil
}

func iccMft2Parse(body []byte) (*IccMft2, error) {
	if len(body) < 48 {
		return nil, fmt.Errorf("body too short")
	}
	typeSig := binary.BigEndian.Uint32(body)
	isMft1 := typeSig == ICCMft1Tag
	isMft2 := typeSig == ICCMft2Tag
	if !isMft1 && !isMft2 {
		return nil, fmt.Errorf("not mft1 or mft2 tag")
	}

	out := &IccMft2{
		NIn:  int(body[8]),
		NOut: int(body[9]),
		Grid: int(body[10]),
	}

	if isMft2 {
		if len(body) < 52 {
			return nil, fmt.Errorf("mft2 body too short")
		}
		out.NTableIn = int(binary.BigEndian.Uint16(body[48:]))
		out.NTableOut = int(binary.BigEndian.Uint16(body[50:]))
	} else {
		out.NTableIn = 256
		out.NTableOut = 256
	}

	clutNodes := 1
	for i := 0; i < out.NIn; i++ {
		clutNodes *= out.Grid
	}

	tinWords := out.NIn * out.NTableIn
	clutWords := clutNodes * out.NOut
	toutWords := out.NOut * out.NTableOut

	out.TableIn = make([]uint16, tinWords)
	out.Clut = make([]uint16, clutWords)
	out.TableOut = make([]uint16, toutWords)

	if isMft2 {
		p := 52
		for i := 0; i < tinWords; i++ {
			out.TableIn[i] = binary.BigEndian.Uint16(body[p:])
			p += 2
		}
		for i := 0; i < clutWords; i++ {
			out.Clut[i] = binary.BigEndian.Uint16(body[p:])
			p += 2
		}
		for i := 0; i < toutWords; i++ {
			out.TableOut[i] = binary.BigEndian.Uint16(body[p:])
			p += 2
		}
	} else {
		p := 48
		for i := 0; i < tinWords; i++ {
			out.TableIn[i] = uint16(body[p]) * 257
			p++
		}
		for i := 0; i < clutWords; i++ {
			out.Clut[i] = uint16(body[p]) * 257
			p++
		}
		for i := 0; i < toutWords; i++ {
			out.TableOut[i] = uint16(body[p]) * 257
			p++
		}
	}

	return out, nil
}

func linterp1D(table []uint16, n int, vNorm float64) float64 {
	p := vNorm * float64(n-1)
	lo := int(p)
	if lo >= n-1 {
		return float64(table[n-1])
	}
	if lo < 0 {
		return float64(table[0])
	}
	frac := p - float64(lo)
	return float64(table[lo])*(1.0-frac) + float64(table[lo+1])*frac
}

// clutNode is a plain function rather than a closure captured over m: this
// runs 8x per output channel for every pixel in the frame (icc.go's own
// call site is main.go's per-pixel loop), and a closure stored in a local
// var escapes to the heap on every trilinearClut call. Passing clut/g/no
// explicitly keeps this on the stack.
func clutNode(clut []uint16, g, no, c0, c1, c2, k int) float64 {
	return float64(clut[(((c0*g+c1)*g+c2)*no)+k])
}

// inNorm is always 3 values (RGB in) — an array, not a slice, so callers on
// the per-pixel path do not allocate to build it.
func trilinearClut(m *IccMft2, inNorm [3]float64, out []float64) {
	g := m.Grid
	no := m.NOut

	var q, frac [3]float64
	var lo, hi [3]int

	for c := 0; c < 3; c++ {
		q[c] = inNorm[c] * float64(g-1)
		lo[c] = int(q[c])
		if lo[c] >= g-1 {
			lo[c] = g - 2
		}
		if lo[c] < 0 {
			lo[c] = 0
		}
		hi[c] = lo[c] + 1
		frac[c] = q[c] - float64(lo[c])
	}

	clut := m.Clut
	for k := 0; k < no; k++ {
		v := clutNode(clut, g, no, lo[0], lo[1], lo[2], k)*(1.0-frac[0])*(1.0-frac[1])*(1.0-frac[2]) +
			clutNode(clut, g, no, lo[0], lo[1], hi[2], k)*(1.0-frac[0])*(1.0-frac[1])*frac[2] +
			clutNode(clut, g, no, lo[0], hi[1], lo[2], k)*(1.0-frac[0])*frac[1]*(1.0-frac[2]) +
			clutNode(clut, g, no, lo[0], hi[1], hi[2], k)*(1.0-frac[0])*frac[1]*frac[2] +
			clutNode(clut, g, no, hi[0], lo[1], lo[2], k)*frac[0]*(1.0-frac[1])*(1.0-frac[2]) +
			clutNode(clut, g, no, hi[0], lo[1], hi[2], k)*frac[0]*(1.0-frac[1])*frac[2] +
			clutNode(clut, g, no, hi[0], hi[1], lo[2], k)*frac[0]*frac[1]*(1.0-frac[2]) +
			clutNode(clut, g, no, hi[0], hi[1], hi[2], k)*frac[0]*frac[1]*frac[2]
		out[k] = v
	}
}

// maxIccOutStack bounds the stack-allocated scratch iccMft2Eval uses for
// clutOut. Both profiles this pipeline loads (Rpd2Pcs_HR200_QS_v5s10.pf,
// Srgb_v2.pf) are 3-channel, so this is headroom, not a tight fit — anything
// larger falls back to a heap allocation rather than mis-sizing.
const maxIccOutStack = 8

func iccMft2Eval(m *IccMft2, inVals []uint16, outVals []uint16) {
	var inNorm [3]float64
	for c := 0; c < 3; c++ {
		rawNorm := float64(inVals[c]) / 65535.0
		afterTin := linterp1D(m.TableIn[c*m.NTableIn:], m.NTableIn, rawNorm)
		inNorm[c] = afterTin / 65535.0
	}

	no := m.NOut
	var clutOutArr [maxIccOutStack]float64
	clutOut := clutOutArr[:0]
	if no <= maxIccOutStack {
		clutOut = clutOutArr[:no]
	} else {
		clutOut = make([]float64, no)
	}
	trilinearClut(m, inNorm, clutOut)

	for k := 0; k < no; k++ {
		norm := clutOut[k] / 65535.0
		v := linterp1D(m.TableOut[k*m.NTableOut:], m.NTableOut, norm)
		vi := uint32(v + 0.5)
		if vi > 65535 {
			vi = 65535
		}
		outVals[k] = uint16(vi)
	}
}

func loadProfileTag(path string, preferredTag uint32) (*IccMft2, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	// No substitution. A2B0 is device->PCS and B2A0 is PCS->device: they are
	// each other's INVERSE, so running one where the other was asked for does
	// not degrade the colour, it reverses the transform — and the result is a
	// perfectly ordinary-looking image that is wrong end to end. There is no
	// reading of "the profile is missing the tag I need" that the substitution
	// answers correctly, so it is an error.
	tag := iccFindTag(data, preferredTag)
	if tag == nil {
		want, other := "A2B0", "B2A0"
		if preferredTag == ICCB2A0Tag {
			want, other = "B2A0", "A2B0"
		}
		have := ""
		if iccFindTag(data, ICCA2B0Tag) != nil {
			have = " (it has A2B0)"
		} else if iccFindTag(data, ICCB2A0Tag) != nil {
			have = " (it has B2A0)"
		}
		return nil, fmt.Errorf(
			"%s: no %s tag%s. %s is the inverse transform, not a fallback",
			path, want, have, other)
	}

	return iccMft2Parse(tag)
}

func LoadICCProfile(path string) (*IccMft2, error) {
	return loadProfileTag(path, ICCA2B0Tag)
}

func LoadICCProfileB2A0(path string) (*IccMft2, error) {
	return loadProfileTag(path, ICCB2A0Tag)
}

func rpd12ToU16(rpd12 int) uint16 {
	if rpd12 <= 0 {
		return 0
	}
	if rpd12 >= 4095 {
		return 65535
	}
	v := int(float64(rpd12)*65535.0/4095.0 + 0.5)
	if v > 65535 {
		v = 65535
	}
	return uint16(v)
}

// IccRpd12ToSrgb8Depth is IccRpd12ToSrgb8 with the input precision made an
// explicit choice rather than an accident of whichever library was to hand.
//
// U12 hands the 12-bit RPD code straight to the mft2 evaluator, widened to
// 16 bits. Rpd2Pcs_HR200_QS_v5s10.pf's A2B0 has a 4096-entry input table —
// it was built to be indexed by a 12-bit code — so every knot is reachable.
//
// U8 reproduces what tools/ansel/python-pipeline/pakon_ansel.py does:
// rpd12_to_icc_u8 quantises to 8 bits (rint(code·255/4095)) and lcms then
// widens back to 16 bits internally (v·257) before evaluating. That reaches
// 256 of the 4096 knots. Python does it not as a colour decision but because
// ImageCms.applyTransform needs a PIL image and PIL has no 16-bit RGB mode.
//
// Kept here so the parity harness can put the two engines on the same footing
// at this tap and show the ICC hop's own contribution.
// rpd and the return are fixed 3-element arrays, not slices: this runs once
// per pixel (main.go's processImage loop), and a slice literal built at the
// call site plus a slice returned from here were two more heap allocations
// on top of the ones iccMft2Eval used to make — profiled at ~39% of a
// render's CPU time before this and the iccMft2Eval/trilinearClut changes
// above, almost all of it runtime.mallocgc / madvise, not colour maths.
func IccRpd12ToSrgb8Depth(rpd2pcs *IccMft2, srgb *IccMft2, rpd [3]int, depth IccInputDepth) [3]uint8 {
	if depth != IccU8 {
		return IccRpd12ToSrgb8(rpd2pcs, srgb, rpd)
	}
	var in1 [3]uint16
	for c := 0; c < 3; c++ {
		v := rpd[c]
		if v < 0 {
			v = 0
		}
		if v > 4095 {
			v = 4095
		}
		// rint(code * 255 / 4095), then lcms's 8->16 widening v*257.
		u8 := int(float64(v)*(255.0/4095.0) + 0.5)
		if u8 > 255 {
			u8 = 255
		}
		in1[c] = uint16(u8 * 257)
	}
	var pcs [3]uint16
	iccMft2Eval(rpd2pcs, in1[:], pcs[:])
	var srgb16 [3]uint16
	iccMft2Eval(srgb, pcs[:], srgb16[:])
	var out [3]uint8
	for c := 0; c < 3; c++ {
		v := uint32(srgb16[c]) * 255 / 65535
		if v > 255 {
			v = 255
		}
		out[c] = uint8(v)
	}
	return out
}

// IccRpd12ToSrgb8 evaluates the full two-stage ICC render from 12-bit RPD to 8-bit sRGB.
func IccRpd12ToSrgb8(rpd2pcs *IccMft2, srgb *IccMft2, rpd [3]int) [3]uint8 {
	var in1, pcs [3]uint16
	for c := 0; c < 3; c++ {
		v := rpd[c]
		if v < 0 {
			v = 0
		}
		if v > 4095 {
			v = 4095
		}
		in1[c] = rpd12ToU16(v)
	}
	iccMft2Eval(rpd2pcs, in1[:], pcs[:])

	var srgb16 [3]uint16
	iccMft2Eval(srgb, pcs[:], srgb16[:])

	var srgbOut [3]uint8
	for c := 0; c < 3; c++ {
		v := uint32(srgb16[c]) * 255 / 65535
		if v > 255 {
			srgbOut[c] = 255
		} else {
			srgbOut[c] = uint8(v)
		}
	}
	return srgbOut
}

// -------------------------------------------------------------------------
// THE ICC HOP THE PIPELINE SHOULD CALL
//
// Default: package kcmsclut — the port of kodakcms.dll fcn.10018160, the
// interpolator the vendor's own CMM runs for this profile pair. It needs no
// .pf files: SpCombineXforms already folded both profiles into its tables, and
// pakon_kcms_clut_golden.py case 2 checks those shipped tables byte-for-byte
// against the ones the live DLL builds. This mirrors the Python path, where
// AnselEngine.to_srgb defaults to the same port (PAKON_ICC_LCMS=1 falls back to
// lcms there), and the C path, where icc_render_rpd12_to_srgb8 does the same.
//
// PAKON_ICC_TRILINEAR=1 runs IccRpd12ToSrgb8Depth instead. Provided so the two
// can be diffed on real frames; it is the algorithm docs/74 §176 disproved.
//
// Note that -icc-input has no meaning on the vendor path: fcn.10018160 sits on
// the CMM dispatcher's in=3/out=3 *u8* leaf, and the combined transform's input
// index table is 3x256 by construction. u8 there is not a quantisation this
// port chose, it is the shape of the transform the vendor itself built.
// -------------------------------------------------------------------------

// iccTrilinear caches the PAKON_ICC_TRILINEAR lookup — this is on the
// per-pixel path.
var iccTrilinear = os.Getenv("PAKON_ICC_TRILINEAR") == "1"

// IccRenderRpd12ToSrgb8 evaluates the ICC hop with whichever evaluator is
// selected. rpd2pcs/srgb may be nil on the default path.
func IccRenderRpd12ToSrgb8(rpd2pcs *IccMft2, srgb *IccMft2, rpd [3]int,
	depth IccInputDepth) [3]uint8 {
	if iccTrilinear && rpd2pcs != nil && srgb != nil {
		return IccRpd12ToSrgb8Depth(rpd2pcs, srgb, rpd, depth)
	}
	return kcmsclut.Rpd12ToSrgb8(rpd)
}

// IccRenderBanner names the live evaluator, so a render log can never leave it
// ambiguous.
func IccRenderBanner(profilesLoaded bool) string {
	if iccTrilinear && profilesLoaded {
		return "PAKON_ICC_TRILINEAR=1 — legacy trilinear mft2 chain " +
			"(docs/74 §176: NOT the vendor's arithmetic)"
	}
	if iccTrilinear {
		return "PAKON_ICC_TRILINEAR=1 requested but profiles are not loaded — " +
			"using the vendor CLUT port"
	}
	return "kodakcms.dll fcn.10018160 port — vendor CLUT, tetrahedral / " +
		"14-bit / SAR, bit-exact over all 16,777,216 u8 triples"
}
