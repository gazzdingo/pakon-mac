package main

import (
	"bufio"
	"flag"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"log"
	"math"
	"os"
	"strconv"
	"strings"

	"golang.org/x/image/tiff"
)

// F135InvertPorted records that the F-135 negative->positive step in
// processImage has no DLL call site behind it. docs/58 s3.5 is [VERIFIED] that
// no density LUT is applied between fcn.1000d880 and Ansel, and s16 records
// what has since been ruled out: AnsSraCapabilityImpl::makeSRALUTS is a
// balance, not a mask removal, and the SRA forward LUT is never applied on its
// own. Treat the rendered colour as provisional.

type frame struct {
	h, w int
	px   [][][3]int
}

const F135InvertPorted = false

// ccdLineOffsets is the trilinear CCD row spacing, R/G/B, in PIXELS of the
// input image along the transport axis. Measured, not from a vendor table —
// see the deskew block in processImage.
//
// Pixels, not scan lines: the decoder resamples the transport axis by the
// transport scale before it writes the TIFF, so the two are equal only at
// scale 1.0. captures/out_test was decoded at 1.0, which is why its measured
// 8 scan lines and the 8 that nulls the lag here are the same number. On
// strip_cal (scale 2.1801) the decoder measures 4 scan lines and it takes 8
// pixels here — 4 x 2.1801 = 8.7, and 8 is what actually nulls it.
//
// Default off, because the raw14 TIFFs this tool is fed have already been
// deskewed by tools/pakon_decode.py: correcting twice is worse than not at
// all. Pass -ccd-deskew 8,0,-8 for a TIFF decoded with --ccd-deskew off.
var ccdLineOffsets = [3]int{0, 0, 0}

// rotate180 turns the input through 180° before anything else looks at it.
//
// The scanner's lens inverts the image it projects onto the CCD, so a capture
// is upside-down and back-to-front relative to the scene — a rotation, not a
// mirror. docs/46 §5 listed orientation as open ("six variants tried, all
// judged wrong"); it is settled now from legible text, see
// tools/pakon_decode.py's ROTATE_180_FOR_LENS. That decoder applies the
// rotation when it writes the raw14 TIFF, so by default there is nothing left
// to do here. Set this for a TIFF written before that fix (captures/out_test/
// and anything else decoded with the old rot90(k=1)).
var rotate180 bool

// rotated180 presents an image turned through 180°, without copying it.
// It touches no pixel value, so nothing downstream — deskew, poly, ICC —
// measures anything different; only the axis directions change.
type rotated180 struct{ src image.Image }

func (r rotated180) ColorModel() color.Model { return r.src.ColorModel() }
func (r rotated180) Bounds() image.Rectangle { return r.src.Bounds() }
func (r rotated180) At(x, y int) color.Color {
	b := r.src.Bounds()
	return r.src.At(b.Min.X+b.Max.X-1-x, b.Min.Y+b.Max.Y-1-y)
}

type ColorProfile struct {
	NegLut [16384]float32
	Matrix [3][3]float32
	Offset [3]float32
	Fugc   [3201][3]float32
	SraLut [4096]int
}

func parseSraFwdLut(filename string) ([4096]int, error) {
	var lut [4096]int
	file, err := os.Open(filename)
	if err != nil {
		return lut, err
	}
	defer file.Close()
	
	var rows []int
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if idx := strings.Index(line, "#"); idx >= 0 {
			line = strings.TrimSpace(line[:idx])
		}
		if line == "" { continue }
		
		up := strings.ToUpper(line)
		if strings.HasPrefix(up, "SRA_NUM_FORWARDLUT") { continue }
		if strings.HasPrefix(up, "SRA_FORWARDLUT") {
			parts := strings.Split(line, "=")
			if len(parts) > 1 {
				rhs := strings.TrimSpace(parts[1])
				if rhs != "" {
					if val, err := strconv.Atoi(rhs); err == nil {
						rows = append(rows, val)
					}
				}
			}
			continue
		}
		
		if val, err := strconv.Atoi(line); err == nil {
			rows = append(rows, val)
		}
	}
	
	n := len(rows)
	if n > 4096 { n = 4096 }
	for i := 0; i < n; i++ {
		lut[i] = rows[i]
	}
	for i := n; i < 4096; i++ {
		if n > 0 {
			lut[i] = rows[n-1]
		}
	}
	return lut, scanner.Err()
}

func parseLut(filename string) ([16384]float32, error) {
	var lut [16384]float32
	file, err := os.Open(filename)
	if err != nil {
		return lut, err
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" { continue }
		parts := strings.Fields(line)
		if len(parts) == 2 {
			idx, _ := strconv.ParseFloat(parts[0], 32)
			val, _ := strconv.ParseFloat(parts[1], 32)
			if int(idx) >= 0 && int(idx) < 16384 {
				lut[int(idx)] = float32(val)
			}
		}
	}
	return lut, scanner.Err()
}

func parseMatrix(filename string) ([3][3]float32, [3]float32, error) {
	var mat [3][3]float32
	var off [3]float32
	file, err := os.Open(filename)
	if err != nil {
		return mat, off, err
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, ";") { continue }
		parts := strings.Split(line, ":")
		if len(parts) != 2 { continue }
		key := strings.TrimSpace(parts[0])
		val, _ := strconv.ParseFloat(strings.TrimSpace(parts[1]), 32)
		var row, col int
		if _, err := fmt.Sscanf(key, "coeff_%d_%d", &row, &col); err == nil {
			if col < 3 {
				mat[row][col] = float32(val)
			} else if col == 3 {
				off[row] = float32(val)
			}
		}
	}
	return mat, off, scanner.Err()
}

func parseFugcLut(filename string) ([3201][3]float32, error) {
	var lut [3201][3]float32
	file, err := os.Open(filename)
	if err != nil {
		return lut, err
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") || strings.Contains(line, "=") { continue }
		parts := strings.Fields(line)
		if len(parts) >= 4 {
			idx, _ := strconv.Atoi(parts[0])
			r, _ := strconv.ParseFloat(parts[1], 32)
			g, _ := strconv.ParseFloat(parts[2], 32)
			b, _ := strconv.ParseFloat(parts[3], 32)
			if idx >= 0 && idx <= 3200 {
				lut[idx][0] = float32(r)
				lut[idx][1] = float32(g)
				lut[idx][2] = float32(b)
			}
		}
	}
	return lut, scanner.Err()
}

func LoadProfile(lutPath, matPath, fugcPath, sraPath string) (*ColorProfile, error) {
	lut, err := parseLut(lutPath)
	if err != nil { return nil, err }
	mat, off, err := parseMatrix(matPath)
	if err != nil { return nil, err }
	fugc, err := parseFugcLut(fugcPath)
	if err != nil { return nil, err }
	sra, err := parseSraFwdLut(sraPath)
	if err != nil { return nil, err }
	return &ColorProfile{NegLut: lut, Matrix: mat, Offset: off, Fugc: fugc, SraLut: sra}, nil
}

func (p *ColorProfile) ApplyMath(r, g, b float32) (float32, float32, float32) {
	clamp := func(v float32) int {
		i := int(v)
		if i < 0 { return 0 }
		if i > 16383 { return 16383 }
		return i
	}
	lutR := p.NegLut[clamp(r)]
	lutG := p.NegLut[clamp(g)]
	lutB := p.NegLut[clamp(b)]
	outR := lutR * p.Matrix[0][0] + lutG * p.Matrix[0][1] + lutB * p.Matrix[0][2] + p.Offset[0]
	outG := lutR * p.Matrix[1][0] + lutG * p.Matrix[1][1] + lutB * p.Matrix[1][2] + p.Offset[1]
	outB := lutR * p.Matrix[2][0] + lutG * p.Matrix[2][1] + lutB * p.Matrix[2][2] + p.Offset[2]
	
	// Apply FUGC LUT
	clampFugc := func(v float32) int {
		i := int(v)
		if i < 0 { return 0 }
		if i > 3200 { return 3200 }
		return i
	}
	
	finalR := p.Fugc[clampFugc(outR)][0]
	finalG := p.Fugc[clampFugc(outG)][1]
	finalB := p.Fugc[clampFugc(outB)][2]
	// Output is in 12-bit RPD space (0-4095)
	return finalR, finalG, finalB
}

func processImage(fr *frame, req *RenderRequest, eng *Engine, logf func(string, ...any), emit func(out, bypass *image.RGBA) error) error {
	profile := eng.Profile
	rpd2pcs := eng.Rpd2Pcs
	srgb := eng.Srgb
	model := req.Model
	coeffs := eng.Coeffs
	band3 := eng.Band3
	sel := eng.Sel

	height := fr.h
	width := fr.w

	outImg := image.NewRGBA(image.Rect(0, 0, width, height))
	bypassImg := image.NewRGBA(image.Rect(0, 0, width, height))

	// Stage taps, for "show me each stage" — additive, no effect on the
	// render when req.TapDir is "". NewTapWriter and every method on it are
	// nil-safe, so tw is used unconditionally below with no branch on it.
	tw, twErr := NewTapWriter(req.TapDir, height, width)
	if twErr != nil {
		return fmt.Errorf("tap writer: %w", twErr)
	}

	
	// --- Trilinear CCD deskew -------------------------------------------
	// The sensor (#123528) senses R, G and B on three physically separate
	// pixel rows, so each channel crosses a given point on the film at a
	// different time and the three records land on different scan lines.
	// docs/30 §"Sensor" has this [VERIFIED trilinear — F-135 Service Manual
	// p.7] but records the row spacing as UNKNOWN; docs/46 asks whether a
	// +3 line shift is real. Measured by cross-correlating the log planes of
	// captures/out_test/frames/*_raw14.tiff, it is +8 / 0 / -8: R leads G by
	// eight scan lines and B trails it by eight. Frame 02 peaks at 0.998 (R)
	// and 0.996 (B), and 02…08 all agree; 00/01 are blank leader.
	//
	// The transport axis here is x (the long axis of the strip), so the
	// correction is a shift along x. It is in *scan lines*, so it is only
	// valid for the transport speed and line rate this capture was made at.
	//
	// SIGN. The offsets keep the sense tools/pakon_decode.py's
	// measure_ccd_line_offsets reports — R leads G, B trails it — and that
	// decoder corrects with np.roll(+off) on the capture's own (lines, ccd)
	// axes, before it rotates. By the time an image reaches this tool the lens
	// 180° has been applied, by the decoder or by -rotate180 above, so x runs
	// *against* increasing scan-line number and the same correction is x+off
	// here where it is x-off there.
	//
	// Measured, not argued: on an undeskewed frame 03 of strip_cal the R/B lag
	// against G along x is -8/+8 px. -ccd-deskew 8,0,-8 takes it to 0/0;
	// -8,0,8 takes it to -12/+12. Get the sign backwards and every vertical
	// edge picks up half again the rainbow fringing instead of none, which
	// reads as a colour bug rather than an ordering one.
	sample := func(x, y, c int) int {
		if x < 0 {
			x = 0
		}
		if x >= width {
			x = width - 1
		}
		return fr.px[y][x][c]
	}
	ccdPixel := func(x, y int) (int, int, int) {
		return sample(x+ccdLineOffsets[0], y, 0),
			sample(x+ccdLineOffsets[1], y, 1),
			sample(x+ccdLineOffsets[2], y, 2)
	}
	// Diagnostics go to stderr, never stdout: an app driving this over a pipe
	// (docs/62 §3.4) cannot tell a log line from the payload otherwise, and
	// the parity harness fails the run outright if stdout is not clean.
	if ccdLineOffsets == [3]int{0, 0, 0} {
		fmt.Fprintf(os.Stderr, "CCD deskew: off here — the input is already deskewed\n")
	} else {
		fmt.Fprintf(os.Stderr, "CCD deskew: R %+d / G %+d / B %+d transport px "+
			"(sampled at x%+d/x%+d/x%+d — x runs against scan-line order "+
			"after the lens 180°)\n",
			ccdLineOffsets[0], ccdLineOffsets[1], ccdLineOffsets[2],
			ccdLineOffsets[0], ccdLineOffsets[1], ccdLineOffsets[2])
	}

	rpd12 := make([][][3]float64, height)
	var planeR, planeG, planeB []int

	clamp4k := func(v int) int {
		if v < 0 { return 0 }
		if v > 4095 { return 4095 }
		return v
	}

	// --- Pass 1: PolyPixel only ---
	// F-135: PolyPixel (TLB.dll:fcn.1000d880, 3x10 quadratic) -> linear 12-bit.
	//        No NegLut / NegMat: those are the F-235 (TLA) stage-2 tables.
	//
	// The SRA forward LUT is NOT applied here on its own — that produces a
	// fully black image (a metric-preserving round trip fwd-then-bwd, applied
	// half of it) and is not an operation the vendor performs anywhere. See
	// the inversion block below for the call sites and the c9 formula that
	// replaces it. rpd12 holds the RAW poly output here, in the 0..4095 domain
	// PolyPixel produces; pass 2 overwrites it with the inverted value once
	// frameDmin (which itself needs the raw poly planes) is known.
	for y := 0; y < height; y++ {
		yy := y - 0
		rpd12[yy] = make([][3]float64, width)
		for x := 0; x < width; x++ {
			xx := x - 0
			r, g, b := ccdPixel(x, y)

			var outR, outG, outB float32

			if model == "f135" {
				polyOut := PolyPixel([3]int{r, g, b}, coeffs)

				outR = float32(polyOut[0])
				outG = float32(polyOut[1])
				outB = float32(polyOut[2])

				planeR = append(planeR, int(outR))
				planeG = append(planeG, int(outG))
				planeB = append(planeB, int(outB))
			} else {
				rawR := float32(r) / 4.0
				rawG := float32(g) / 4.0
				rawB := float32(b) / 4.0
				outR, outG, outB = profile.ApplyMath(rawR, rawG, rawB)
				
				planeR = append(planeR, int(outR))
				planeG = append(planeG, int(outG))
				planeB = append(planeB, int(outB))
			}
			
			rpd12[yy][xx] = [3]float64{float64(outR), float64(outG), float64(outB)}
		}
	}
	tw.Write("poly", rpd12) // raw PolyPixel output, pre-inversion

	// SBA preference fields come from the dpi that sba.map selected for this
	// DX — nothing film-specific is hardcoded here.
	//
	// nbp is neutralBalancePoint, not a button count. It was 18 here, which
	// flipped the sign of every preference shift: lim46 = round(nbp*sqrt3)
	// came out 31 instead of 2685, so sPrime = lim46 - Y went negative.
	// tools/ansel/pakon_sba_preference.py (PREFERENCE_SHIFTS_PORTED, docs/49)
	// passes the dpi's neutralBalancePoint and yields prefA (746, 350, 189).
	fpo := sel.Sba.Fpo
	fpa := sel.Sba.Fpa
	nbp := sel.Sba.NeutralBalancePoint
	nb := sel.Sba.NeutralButton

	// --- F-135 negative -> positive -------------------------------------
	// PROVENANCE: F135InvertPorted is still false. No call site in TLB.dll or
	// PakonIMAu.dll has been shown to compute this step; docs/58 s3.5 is
	// [VERIFIED] that no log-density LUT is applied between the polynomial and
	// Ansel, and where the F-135 inverts is still open. What follows is a
	// stand-in. Two things about it are now settled from the bytes, though, and
	// they are why it no longer looks like the previous one:
	//
	//  1. The SRA forward LUT is never used on its own by the vendor.
	//     AnsSraCapabilityImpl::analyze (PakonIMAu.dll:0x101a7080) finishes by
	//     calling 0x101a3ce0 three times (0x101a751b / 0x101a7540 / 0x101a7566)
	//     with the DPI's forward table (dpi+0x68) AND its backward table
	//     (dpi+0x64):
	//         sraLut_ch[i] = clamp( bwd[ aCh[ fwd[i] ] ], 0, 4095 )
	//     fwd and bwd round-trip to within 2-3 codes over the whole domain, so
	//     the finished SRA operator is metric-PRESERVING: it goes out to the
	//     RPD working space, tone-scales, and comes straight back. Applying
	//     common-sraFwdLut-metric-rom12.lut alone, as this code used to, is not
	//     an operation the vendor performs anywhere.
	//
	//  2. AnsSraCapabilityImpl::makeSRALUTS (0x101a6be0 — the 0x10594b78 in
	//     docs/46 is the *string*, not the function) is not the missing
	//     orange-mask removal. It builds ONE shared neutral curve `aCh` and
	//     three per-channel ADDITIVE INTEGER offsets (0x101a3d40):
	//         offR = -trunc(-(2/3)d2 - d3)
	//         offG = -trunc( (4/3)d2 )
	//         offB = -trunc(-(2/3)d2 + d3)
	//     from two opponent-chroma scalars. An additive offset cannot change a
	//     channel's contrast, so makeSRALUTS can only balance. See docs/58 s16.
	//
	// So the tone step has to be a density conversion, and it is the logarithm
	// that inverts — exactly as on the F-235 path, where the -7000*log10 dens
	// LUT is what turns the negative the right way up (docs/58 s3.5, s5).
	//
	//     rpd12 = fpo + 1000 * ( log10(filmBase - c9) - log10(poly - c9) )
	//
	// c9 is the polynomial's own per-channel constant term (159.59 / 444.75 /
	// 635.54 on this unit, docs/58 s4.4a): a pedestal in the LINEAR domain,
	// which has to come off before any log or the channel contrasts come out
	// wrong. Measured on 08_raw14.tiff (1...99.9 %):
	//     -log10(poly/4095)       spans 791 / 404 / 236  = 1.00 : 0.51 : 0.30
	//     -log10(poly - c9)       spans 1035 / 1180 / 1160 = 1.00 : 1.14 : 1.12
	//     the negative's own D    spans 1052 / 1182 / 1201 = 1.00 : 1.12 : 1.14
	// i.e. taking the pedestal off reproduces the film's own channel contrasts
	// to 2 %. That is what lets the tone scale below be ONE curve, the way a
	// vendor tone scale is.
	//
	// 1000 codes per decade is the metric the rest of the chain is written in:
	// the FUGC tone LUTs are 3201 rows of "1000 x density" (docs/58 s6 row 15).
	//
	// filmBase is the frame's clear-film code — what the vendor's FindDmin
	// returns, since it walks the histogram DOWN from the top (dmin.go). It is
	// placed on the DPI's own Film Printing Offset `fpo`, the orange-mask aim,
	// because the SBA balance below is sized to take it from there to neutral:
	// fpo (879/1250/1386) + setShifts (688/292/130) = 1567/1542/1516, i.e. the
	// same dpi's neutralBalancePoint 1550 to within 3 %% in every channel. That
	// is what the mask removal is on this path — a per-channel OFFSET, which is
	// all makeSRALUTS and setShifts can express, and it only works once the
	// channel contrasts already match.
	prefA := PreferenceShiftsFromDpiFields(fpo, fpa, nbp, nb,
		sel.Sba.NeutralUnderConstraint, sel.Sba.NeutralOverConstraint, sel.Sba.Pcls)
	setshiftsOut := SetShifts12(prefA, prefA, band3.Planar, band3.NumLut)

	frameDmin := frameDminRgbFromPlanes(planeR, planeG, planeB, 4096)

	// --- Pass 2: the inversion itself ---
	//     rpd12 = fpo + 1000 * ( log10(filmBase - c9) - log10(poly - c9) )
	// c9 is coeffs[10*ch+9], PolyPixel's own per-channel constant term (see
	// poly.go) — the pedestal that has to come off before the log, or the
	// channel contrasts come out wrong (measured 1.00:0.51:0.30 with it left
	// in, 1.00:1.14:1.12 with it removed, against the negative's own
	// 1.00:1.12:1.14). rpd12[y][x] currently holds pass 1's raw poly output;
	// this overwrites it in place.
	logTerm := func(v, c9 float64) float64 {
		d := v - c9
		if d < 1 {
			d = 1
		}
		return math.Log10(d)
	}
	c9 := [3]float64{float64(coeffs[9]), float64(coeffs[19]), float64(coeffs[29])}
	baseLog := [3]float64{
		logTerm(float64(frameDmin[0]), c9[0]),
		logTerm(float64(frameDmin[1]), c9[1]),
		logTerm(float64(frameDmin[2]), c9[2]),
	}
	if model == "f135" {
		for y := 0; y < height; y++ {
			for x := 0; x < width; x++ {
				p := rpd12[y][x]
				for ch := 0; ch < 3; ch++ {
					v := float64(fpo[ch]) + 1000*(baseLog[ch]-logTerm(p[ch], c9[ch]))
					p[ch] = float64(clamp4k(int(v)))
				}
				rpd12[y][x] = p
			}
		}
	}
	tw.Write("inv", rpd12) // after the c9 negative->positive log

	balanced := make([][][3]float64, height)
	for y := 0; y < height; y++ {
		balanced[y] = make([][3]float64, width)
		for x := 0; x < width; x++ {
			p := rpd12[y][x]
			pi := []int{int(p[0]), int(p[1]), int(p[2])}
			po := ApplyBalanceShifts(pi, setshiftsOut)
			balanced[y][x] = [3]float64{float64(po[0]), float64(po[1]), float64(po[2])}
		}
	}
	tw.Write("balance", balanced)

	// toned is balanced; Shasta runs after FUGC on final RPD12 values
	toned := balanced
	
	// FUGC aim words. docs/62 §2.4: these were hardcoded here. They are read
	// from the vendor files now — aTableDmin from the selected fugc .lut and
	// aFilmAimDmin from fugc/fugc-defaultParams.dpi, both resolved by
	// maps.go's PakonColorOpen. On this install the shipped values are
	// {500,500,500} and {500,1000,1000}, i.e. exactly what the hardcode said,
	// so this changes no pixel here; it stops being a coincidence on any
	// other install.
	fugcDmin := sel.FugcDmin
	afilmAim := sel.FugcAim

	// docs/62 §2.2: this branched on `model == "f135"`, which sent every F-135
	// frame down the mode-2 plane path — the branch docs/58 §7 lists as NOT
	// ported. The FUGC mode is a runtime capability field (Cap +0x60e8,
	// CAP_MODE_SELECT = 0xC), not a property of the scanner model, and
	// pakon_ansel.py defaults fugc_mode to 1 with nothing in the tree setting
	// it to 2. Branch on the mode the request actually carries.
	var fugcApplyLut [][3]float32
	if req.FugcMode == 2 {
		fugcApplyLut, _, _ = BuildMode2ApplyLut(profile.Fugc[:], fugcDmin, prefA, frameDmin, afilmAim)
	} else {
		fugcApplyLut, _, _, _ = BuildSetLutInfoApplyLut(profile.Fugc[:], fugcDmin, prefA, frameDmin, afilmAim)
	}
	
	clampFugc := func(v float64) int {
		i := int(v)
		if i < 0 { return 0 }
		if i > 4095 { return 4095 }
		return i
	}
	
	fugcOut := make([][][3]float64, height)
	for y := 0; y < height; y++ {
		fugcOut[y] = make([][3]float64, width)
		for x := 0; x < width; x++ {
			p := toned[y][x]
			fugcOut[y][x] = [3]float64{
				float64(fugcApplyLut[clampFugc(p[0])][0]),
				float64(fugcApplyLut[clampFugc(p[1])][1]),
				float64(fugcApplyLut[clampFugc(p[2])][2]),
			}
		}
	}
	tw.Write("fugc", fugcOut)

	// Auto-tone. The real stage for a negative is
	// ColorNegativePath::analyzeAutoTone (0x100fb730) — a six-capability chain
	// (cna → dra → toneHelper → contrast → ast → citras), NOT Shasta, which
	// never runs for CN-Enhanced. It is not ported; see AutoTonePorted in
	// shasta.go for the full call map, the enable bytes, the toneHelper DPI
	// resolution and why the chain cannot be ported piecewise. Until then
	// F-135 keeps the two-anchor stand-in built from shasta-rpd.dpi.
	shasted := fugcOut
	if model == "f135" {
		shasted = ShastaToneRpd(fugcOut, sel.ShastaParams())
	}
	tw.Write("shasta", shasted)
	tw.Write("ansel", shasted) // the toned RPD-12 handed to the ICC hop

	var sum [3]float64
	iccU8 := make([][][3]uint8, height)
	for y := 0; y < height; y++ {
		iccU8[y] = make([][3]uint8, width)
		for x := 0; x < width; x++ {
			p := shasted[y][x]

			finalR := int(p[0])
			finalG := int(p[1])
			finalB := int(p[2])

			// bypass: direct linear scale 0-4095 → 0-255 (for debug)
			dr := uint8(finalR * 255 / 4095)
			dg := uint8(finalG * 255 / 4095)
			db := uint8(finalB * 255 / 4095)
			bypassImg.Set(x, y, color.RGBA{dr, dg, db, 255})

			srgbColor := IccRpd12ToSrgb8(rpd2pcs, srgb, []int{finalR, finalG, finalB})
			outImg.Set(x, y, color.RGBA{srgbColor[0], srgbColor[1], srgbColor[2], 255})
			iccU8[y][x] = [3]uint8{srgbColor[0], srgbColor[1], srgbColor[2]}
			sum[0] += float64(srgbColor[0])
			sum[1] += float64(srgbColor[1])
			sum[2] += float64(srgbColor[2])
		}
	}
	tw.WriteU8("icc", iccU8)
	tw.Set("film_base", frameDmin)
	tw.Set("fpo", fpo)

	n := float64(width * height)
	logf("OUTPUT mean sRGB per channel: R=%.1f G=%.1f B=%.1f\n", sum[0]/n, sum[1]/n, sum[2]/n)
	if model == "f135" {
		logf("PROVENANCE: F135InvertPorted=%v AutoTonePorted=%v "+
			"ShastaAnalyzePorted=%v — the inversion and the tone scale are "+
			"stand-ins, not vendor call sites\n",
			F135InvertPorted, AutoTonePorted, ShastaAnalyzePorted)
	}

	if err := tw.Close(); err != nil {
		return fmt.Errorf("tap writer close: %w", err)
	}

	return emit(outImg, nil)
}

func main() {
	if len(os.Args) == 1 {
		// No args -> act as C-shared library, do nothing
		return
	}

	modelFlag := flag.String("model", "f135", "scanner model (f135 or f235)")
	fugcModeFlag := flag.Int("fugc-mode", 1, "FUGC mode (Cap +0x60e8). 2 takes "+
		"the metrics/plane path at 0x101fc7e6; anything else takes setLutInfo "+
		"at 0x101f82c0, which is what pakon_ansel.py defaults to and what "+
		"docs/58 §7 lists as ported. docs/62 §2.2.")
	tapFlag := flag.String("tap-dir", "", "write one raw array per pipeline "+
		"stage here (poly/inv/balance/fugc/shasta/ansel/icc) plus a "+
		"manifest.json, for tools/pakon_parity.py or for looking at a stage "+
		"directly. \"\" writes nothing.")
	flag.Parse()
	args := flag.Args()

	if len(args) < 2 {
		fmt.Fprintf(os.Stderr, "Usage: %s [-model f135|f235] <input.tiff> <output.png>\n", os.Args[0])
		os.Exit(1)
	}

	inputPath := args[0]
	outputPath := args[1]

	inFile, err := os.Open(inputPath)
	if err != nil {
		log.Fatalf("failed to open input file: %v", err)
	}
	defer inFile.Close()

	img, err := tiff.Decode(inFile)
	if err != nil {
		log.Fatalf("failed to decode TIFF: %v", err)
	}
	bounds := img.Bounds()
	width := bounds.Dx()
	height := bounds.Dy()

	fr := &frame{
		h:  height,
		w:  width,
		px: make([][][3]int, height),
	}

	for y := 0; y < height; y++ {
		fr.px[y] = make([][3]int, width)
		for x := 0; x < width; x++ {
			r, g, b, _ := img.At(bounds.Min.X+x, bounds.Min.Y+y).RGBA()
			fr.px[y][x] = [3]int{int(r), int(g), int(b)}
		}
	}

	req := &RenderRequest{
		Model:       *modelFlag,
		FilmPath:    "ColNeg",
		DXPart1:     96,
		DXPart2:     -1,
		AnselPath:   "CN-Premium",
		CoeffSource: CoeffEeprom,
		CoeffPath:   "../../../backups/eeprom-i2c/eeprom_52.bin",
		StageOrder:  OrderFugcShasta,
		IccInput:    IccU12,
		FugcMode:    *fugcModeFlag,
		TapDir:      *tapFlag,
	}

	anselRoot := "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/anselinstalldir/dataPathItems"
	fx35Root := "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER"

	eng, err := OpenEngine(fx35Root, anselRoot, req)
	if err != nil {
		log.Fatalf("OpenEngine failed: %v", err)
	}

	// stderr, not stdout: docs/62 §3.4's ABI contract, so a caller reading
	// stdout as a payload never sees a log line mixed into it.
	logf := func(format string, a ...any) { fmt.Fprintf(os.Stderr, format, a...) }
	
	emit := func(out, bypass *image.RGBA) error {
		outF, err := os.Create(outputPath)
		if err != nil {
			return err
		}
		defer outF.Close()
		return png.Encode(outF, out)
	}

	if err := processImage(fr, req, eng, logf, emit); err != nil {
		log.Fatalf("processImage failed: %v", err)
	}
}