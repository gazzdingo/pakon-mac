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
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"

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
	// Decided ONCE, read by both pass 1 and pass 2. See inversionMode().
	invMode := inversionMode(model, vendorInvertEnabled)
	logf("INVERSION: %s\n", invMode)

	for y := 0; y < height; y++ {
		yy := y - 0
		rpd12[yy] = make([][3]float64, width)
		for x := 0; x < width; x++ {
			xx := x - 0
			r, g, b := ccdPixel(x, y)

			var outR, outG, outB float32

			if model == "f135" {
				if invMode == "vendor" {
					// The vendor's own position for the inversion: BEFORE the
					// polynomial, on the raw code. Pass 2 is skipped in this
					// mode by the same inversionMode() call, so the log
					// happens exactly once — pakon_render's vendor path guards
					// the same hazard with "do NOT invert again".
					r, g, b = applyVendorInvertRGB(r, g, b)
				}
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
	// Runs only in "legacy" mode. Under "vendor" the inversion already
	// happened in pass 1, and both branches read the SAME inversionMode()
	// result, so inverting twice is unrepresentable rather than merely
	// guarded — see inversionMode's comment for why that distinction earned
	// its own refactor.
	applyLegacyInversion(invMode, rpd12, fpo, baseLog, c9, logTerm, clamp4k)
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
	// never runs for CN-Enhanced. See AutoTonePorted in shasta.go for the full
	// call map and the enable bytes.
	//
	// The chain's APPLY half is now ported: if the caller supplied the real
	// OutToneLut, it is applied through the vendor's own driver
	// (ImaCitrasOpBase::virtual_40, citrasdriver) — a luminance-indexed,
	// gradient-avoiding delta broadcast, not a per-channel stretch. Without a
	// LUT the F-135 falls back to the two-anchor stand-in from shasta-rpd.dpi.
	// Both branches are named in the provenance banner below; neither is
	// silent.
	//
	// CORRECTION 2026-08-21: this comment used to read "the ANALYSIS half that
	// builds that curve is still Python-only". That is no longer true and had
	// gone stale — package ansautotone EXISTS in Go and its Analyze() returns
	// the OutToneLut directly, with cna/dra/toneHelper/contrast each verified
	// bit-exact against their Python references, which are themselves
	// Unicorn-verified against the DLL. The accurate statement is narrower:
	// the Go analysis chain is not WIRED here. That is Phase 6.2, and it is a
	// deliberate decision rather than a missing port — see autotone.go.
	//
	// Note before wiring it: docs/74 §182.3 shows Go and Python diverge
	// UPSTREAM of tone (Go inverts against the FRAME's dmin where Python uses
	// the ROLL's; FUGC provenance and index rounding differ). So computing the
	// curve in Go would replace a stand-in with the vendor's real chain — a
	// genuine correctness gain — but would NOT by itself make the two engines
	// agree, because they would be analysing different input.
	shasted := fugcOut
	toneVia := "none"
	if req.HasToneLut() {
		toned, err := applyVendorTone(fugcOut, req.OutToneLut)
		if err != nil {
			return fmt.Errorf("vendor tone apply: %w", err)
		}
		shasted = toned
		toneVia = "citrasdriver(analyzeAutoTone OutToneLut)"
	} else if goAutoTone && model == "f135" {
		// Phase 6.2, opt-in via PAKON_GO_AUTOTONE=1 — compute the curve here
		// with the ported analysis chain rather than falling back to the
		// stand-in. See computeGoToneLut for the evidence chain.
		lut, err := computeGoToneLut(fugcOut, eng.AnselRoot)
		if err != nil {
			return fmt.Errorf("go autotone: %w", err)
		}
		if lut == nil {
			// sceneType epilogue zeroed the tone object: no curve to apply.
			// Passing the frame through untoned is what having no tone object
			// means; it is NOT a silent fallback to the stand-in, and the
			// banner says so.
			toneVia = "ansautotone(Go): no tone curve (sceneType epilogue)"
		} else {
			toned, err := applyVendorTone(fugcOut, lut)
			if err != nil {
				return fmt.Errorf("vendor tone apply: %w", err)
			}
			shasted = toned
			toneVia = "ansautotone(Go analysis) + citrasdriver"
		}
	} else if model == "f135" {
		shasted = ShastaToneRpd(fugcOut, sel.ShastaParams())
		toneVia = "ShastaToneRpd stand-in"
	}
	logf("TONE: %s\n", toneVia)
	tw.Write("shasta", shasted)
	tw.Write("ansel", shasted) // the toned RPD-12 handed to the ICC hop

	// This loop is the ICC hop, run twice per pixel (device->PCS, PCS->sRGB),
	// each a trilinear CLUT interpolation plus two 1-D table lookups —
	// profiled at ~39% of a render's CPU time, the single largest stage in
	// processImage (PAKON_GO_CPUPROFILE, docs/68 handover). Every pixel is
	// independent — reads shasted[y][x], writes its own row of outImg/
	// bypassImg/iccU8 — so it is split across goroutines by row range rather
	// than run on one core. img.Set boxes its color.Color argument on every
	// call (escape analysis: main.go color.RGBA{} literals here used to
	// escape to heap); writing straight into Pix avoids that on top of the
	// parallelism.
	iccU8 := make([][][3]uint8, height)
	for y := 0; y < height; y++ {
		iccU8[y] = make([][3]uint8, width)
	}

	logf("ICC: %s\n", IccRenderBanner(rpd2pcs != nil && srgb != nil))

	workers := runtime.NumCPU()
	if workers > height {
		workers = height
	}
	if workers < 1 {
		workers = 1
	}
	rowsPerWorker := (height + workers - 1) / workers
	partialSums := make([][3]float64, workers)
	var wg sync.WaitGroup
	for w := 0; w < workers; w++ {
		y0 := w * rowsPerWorker
		y1 := y0 + rowsPerWorker
		if y1 > height {
			y1 = height
		}
		if y0 >= y1 {
			continue
		}
		wg.Add(1)
		go func(y0, y1, w int) {
			defer wg.Done()
			var sum [3]float64
			for y := y0; y < y1; y++ {
				outRow := outImg.Pix[y*outImg.Stride : y*outImg.Stride+width*4]
				bypassRow := bypassImg.Pix[y*bypassImg.Stride : y*bypassImg.Stride+width*4]
				for x := 0; x < width; x++ {
					p := shasted[y][x]

					finalR := int(p[0])
					finalG := int(p[1])
					finalB := int(p[2])

					// bypass: direct linear scale 0-4095 → 0-255 (for debug)
					dr := uint8(finalR * 255 / 4095)
					dg := uint8(finalG * 255 / 4095)
					db := uint8(finalB * 255 / 4095)
					o := x * 4
					bypassRow[o], bypassRow[o+1], bypassRow[o+2], bypassRow[o+3] = dr, dg, db, 255

					// IccRenderRpd12ToSrgb8 runs the port of the vendor's own
					// CLUT interpolator (kodakcms.dll fcn.10018160, tetrahedral
					// / 14-bit / SAR) by default; PAKON_ICC_TRILINEAR=1 selects
					// the old trilinear mft2 chain, which docs/74 §176 measured
					// as up to 3 sRGB codes away from the vendor. req.IccInput
					// only reaches the trilinear path — the vendor's combined
					// transform is u8-in by construction, see icc.go.
					srgbColor := IccRenderRpd12ToSrgb8(rpd2pcs, srgb,
						[3]int{finalR, finalG, finalB}, req.IccInput)
					outRow[o], outRow[o+1], outRow[o+2], outRow[o+3] =
						srgbColor[0], srgbColor[1], srgbColor[2], 255
					iccU8[y][x] = srgbColor
					sum[0] += float64(srgbColor[0])
					sum[1] += float64(srgbColor[1])
					sum[2] += float64(srgbColor[2])
				}
			}
			partialSums[w] = sum
		}(y0, y1, w)
	}
	wg.Wait()
	var sum [3]float64
	for _, s := range partialSums {
		sum[0] += s[0]
		sum[1] += s[1]
		sum[2] += s[2]
	}
	tw.WriteU8("icc", iccU8)
	tw.Set("film_base", frameDmin)
	tw.Set("fpo", fpo)

	n := float64(width * height)
	logf("OUTPUT mean sRGB per channel: R=%.1f G=%.1f B=%.1f\n", sum[0]/n, sum[1]/n, sum[2]/n)
	if model == "f135" {
		// Two separate facts, kept separate on purpose. AutoToneApplyPorted is
		// about the vendor's apply driver being ported and verified;
		// AutoToneAnalysisPorted is about the six-subsystem chain that builds
		// the curve, which is not. A render is only tone-correct when the
		// apply is ported AND a real curve arrived, so the banner reports the
		// curve's presence rather than letting the flag imply it.
		// Three branches now, and the banner must distinguish all three —
		// "which curve ran" is the single most load-bearing fact about a
		// render's colour, and docs/74 §182.1 is what happens when a claim
		// about which path ran goes stale.
		toneSource := "ShastaToneRpd stand-in (no OutToneLut supplied)"
		switch {
		case req.HasToneLut():
			toneSource = "vendor OutToneLut via citrasdriver"
		case goAutoTone && model == "f135":
			toneSource = "Go ansautotone chain + citrasdriver " +
				"(PAKON_GO_AUTOTONE=1)"
		}
		logf("PROVENANCE: F135InvertPorted=%v AutoToneApplyPorted=%v "+
			"AutoToneAnalysisPorted=%v ShastaAnalyzePorted=%v — tone: %s; "+
			"the inversion is still a stand-in, not a vendor call site\n",
			F135InvertPorted, AutoToneApplyPorted, AutoToneAnalysisPorted,
			ShastaAnalyzePorted, toneSource)
	}

	if err := tw.Close(); err != nil {
		return fmt.Errorf("tap writer close: %w", err)
	}

	return emit(outImg, nil)
}

// DefaultCoeffRelPath and defaultAnselRelPath are repo-relative, and are
// found by searching UPWARD from the working directory rather than being
// absolute.
//
// The absolute paths that used to be baked in here
// (/Users/guy/Downloads/Pakon Update 2/…) meant this binary only ran on one
// machine and only from one directory, and the relative
// "../../../backups/eeprom-i2c/eeprom_52.bin" only resolved when the process
// happened to be started from tools/ansel/pipeline. The harness builds this
// into a scratch dir and runs it from the repo root, so neither worked.
const (
	DefaultCoeffRelPath = "backups/eeprom-i2c/eeprom_52.bin"
	defaultAnselRelPath = "vendor/ansel/anselinstalldir/dataPathItems"
)

// findUpward walks up from the working directory looking for rel.
func findUpward(rel string) (string, bool) {
	dir, err := os.Getwd()
	if err != nil {
		return "", false
	}
	for {
		cand := filepath.Join(dir, rel)
		if _, err := os.Stat(cand); err == nil {
			return cand, true
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return "", false
		}
		dir = parent
	}
}

// ResolveCoeffPath returns the stage-2 coefficient store to read.
func ResolveCoeffPath(flagVal string) (string, error) {
	if flagVal != "" {
		if _, err := os.Stat(flagVal); err != nil {
			return "", fmt.Errorf("%s: %w", flagVal, err)
		}
		return flagVal, nil
	}
	if p, ok := findUpward(DefaultCoeffRelPath); ok {
		return p, nil
	}
	return "", fmt.Errorf(
		"no -coeffs given and %s is not above the working directory (%s). "+
			"The stage-2 polynomial is this unit's calibration; there is no "+
			"generic fallback to guess at", DefaultCoeffRelPath, mustGetwd())
}

// ResolveAnselRoot returns the vendor dataPathItems directory.
func ResolveAnselRoot(flagVal string) (string, error) {
	if flagVal != "" {
		if _, err := os.Stat(flagVal); err != nil {
			return "", fmt.Errorf("%s: %w", flagVal, err)
		}
		return filepath.Clean(flagVal), nil
	}
	if p, ok := findUpward(defaultAnselRelPath); ok {
		return p, nil
	}
	return "", fmt.Errorf(
		"no -ansel-root given and %s is not above the working directory (%s)",
		defaultAnselRelPath, mustGetwd())
}

func mustGetwd() string {
	d, err := os.Getwd()
	if err != nil {
		return "?"
	}
	return d
}

// readFrame reads the input pixels. A non-zero h/w means -raw-in: a
// headerless (h,w,3) little-endian u16 blob on the capture's own grid.
// Otherwise the input is a TIFF.
func readFrame(path string, rawH, rawW int) (*frame, error) {
	if rawH > 0 && rawW > 0 {
		px, err := ReadRawU16(path, rawH, rawW)
		if err != nil {
			return nil, fmt.Errorf("-raw-in: %w", err)
		}
		fr := &frame{h: rawH, w: rawW, px: make([][][3]int, rawH)}
		for y := 0; y < rawH; y++ {
			fr.px[y] = make([][3]int, rawW)
			for x := 0; x < rawW; x++ {
				fr.px[y][x] = [3]int{
					int(px[y][x][0]), int(px[y][x][1]), int(px[y][x][2])}
			}
		}
		return fr, nil
	}

	inFile, err := os.Open(path)
	if err != nil {
		return nil, fmt.Errorf("failed to open input file: %w", err)
	}
	defer inFile.Close()

	img, err := tiff.Decode(inFile)
	if err != nil {
		return nil, fmt.Errorf("failed to decode TIFF: %w", err)
	}
	b := img.Bounds()
	fr := &frame{h: b.Dy(), w: b.Dx(), px: make([][][3]int, b.Dy())}
	for y := 0; y < fr.h; y++ {
		fr.px[y] = make([][3]int, fr.w)
		for x := 0; x < fr.w; x++ {
			r, g, bl, _ := img.At(b.Min.X+x, b.Min.Y+y).RGBA()
			fr.px[y][x] = [3]int{int(r), int(g), int(bl)}
		}
	}
	return fr, nil
}

// parseHW parses the "h,w" of -raw-in.
func parseHW(s string) (int, int, error) {
	parts := strings.Split(s, ",")
	if len(parts) != 2 {
		return 0, 0, fmt.Errorf("want \"h,w\", got %q", s)
	}
	h, err := strconv.Atoi(strings.TrimSpace(parts[0]))
	if err != nil || h <= 0 {
		return 0, 0, fmt.Errorf("%q is not a positive height", parts[0])
	}
	w, err := strconv.Atoi(strings.TrimSpace(parts[1]))
	if err != nil || w <= 0 {
		return 0, 0, fmt.Errorf("%q is not a positive width", parts[1])
	}
	return h, w, nil
}

func main() {
	if len(os.Args) == 1 {
		// No args -> act as C-shared library, do nothing
		return
	}

	// The flag surface IS the request. Every field the colour chain needs
	// that cannot be recovered from the pixels has to arrive here explicitly
	// — request.go's whole premise — so anything RenderRequest carries and a
	// caller has to choose gets a flag. tools/pakon_parity.py drives all of
	// these; a rebuild of this file that leaves any of them out does not fail
	// loudly, it fails as "flag provided but not defined" and the harness
	// cannot run at all.
	modelFlag := flag.String("model", "f135", "scanner model (f135 or f235)")
	dxFlag := flag.String("dx", "96-1", "DX film code, \"PART1[-PART2]\". "+
		"Selects the film tables the way the vendor's own .map files do "+
		"(maps.go:SelectFilm). An absent part 2 is -1, \"explicitly unknown\", "+
		"which is legal only because sba.map / fugc-rgb-lutMap.map carry X "+
		"cells for it.")
	isoFlag := flag.Int("iso", 0, "film speed. 0 is \"explicitly unknown\", "+
		"legal for the same reason as an absent DX part 2.")
	filmPathFlag := flag.String("film-path", "ColNeg", "ColNeg | BnW | "+
		"IMPORTED | POSITIVE. Selects fcn.1000d880's matrix (filmClass); it "+
		"has no wildcard cell in any vendor selector, so there is nothing to "+
		"fall back to and POSITIVE is refused (F135ReversalPorted).")
	anselPathFlag := flag.String("ansel-path", "CN-Premium", "vendor path name "+
		"(CN-Premium, CN-Fps, DC-Premium…). sba.map / shasta.map / profile.map "+
		"key on it and it has no wildcard cell.")
	sourceTypeFlag := flag.Int("source-type", 1, "vendor source type, the "+
		"fourth key SelectFilm matches on.")
	coeffSourceFlag := flag.String("coeff-source", string(CoeffEeprom),
		"eeprom | registry — which stage-2 coefficient store to read. There is "+
			"no \"auto\": they differ by 14–57 RPD codes at (4000,4000,4000) "+
			"and they answer different questions. docs/62 §2.11.")
	coeffPathFlag := flag.String("coeffs", "", "path to the coefficient store. "+
		"Empty searches upward from the working directory for "+
		DefaultCoeffRelPath+".")
	filmBaseFlag := flag.String("film-base", "", "the ROLL's film base in "+
		"linear 12-bit codes, \"r,g,b\" — FindDmin over the whole strip, not "+
		"this frame. It is a property of the stock (docs/62 §2.6); measuring "+
		"it per frame makes the same negative render differently depending on "+
		"which frames you exported. 0 is FindDmin's \"no valid Dmin\" sentinel "+
		"and is refused. Empty requires -film-base-from-frame.")
	filmBaseFromFrameFlag := flag.Bool("film-base-from-frame", false,
		"measure the film base from this frame alone. The explicit, logged "+
			"opt-out for offline analysis with no roll context; never correct "+
			"for the app.")
	stageOrderFlag := flag.String("stage-order", string(OrderFugcShasta),
		"fugc-shasta (the VENDOR's order, established from "+
			"AnsCnPremiumPath::exportParameterPack) | shasta-fugc (what "+
			"pakon_ansel.py:render_scene does). They do not commute.")
	iccInputFlag := flag.String("icc-input", string(IccU12),
		"u8 | u12 — the precision the RPD codes reach the ICC transform at. "+
			"ONLY affects PAKON_ICC_TRILINEAR=1: the default evaluator is the "+
			"vendor's own combined transform (kodakcms.dll fcn.10018160), "+
			"whose input index table is 3x256 by construction, so it is u8-in "+
			"and this flag cannot change that. For the trilinear path, the "+
			"RPD-side profile's mft2 input table has 4096 entries, so u12 "+
			"reaches every knot. docs/62 §2.9, docs/74 §176.")
	fugcModeFlag := flag.Int("fugc-mode", 1, "FUGC mode (Cap +0x60e8). 2 takes "+
		"the metrics/plane path at 0x101fc7e6; anything else takes setLutInfo "+
		"at 0x101f82c0, which is what pakon_ansel.py defaults to and what "+
		"docs/58 §7 lists as ported. docs/62 §2.2.")
	anselRootFlag := flag.String("ansel-root", "", "the vendor's "+
		"anselinstalldir/dataPathItems. The F-X35 COM SERVER root it sits "+
		"under is derived from it (two levels up) and is where "+
		"Config/ColorCorrection is read from. Empty uses the in-repo copy "+
		"under vendor/ansel, found by searching upward from the working "+
		"directory.")
	rawInFlag := flag.String("raw-in", "", "read the input as a headerless "+
		"(h,w,3) little-endian u16 blob of the given \"h,w\" instead of "+
		"decoding a TIFF. This is the CALIBRATED 14-bit capture slice on the "+
		"capture's OWN grid — before unsquash, before rot90 — so the CCD axis "+
		"is x, which is what FindDmin's window is stated in.")
	tapFlag := flag.String("tap-dir", "", "write one raw array per pipeline "+
		"stage here (poly/inv/balance/fugc/shasta/ansel/icc) plus a "+
		"manifest.json, for tools/pakon_parity.py or for looking at a stage "+
		"directly. \"\" writes nothing.")
	flag.Parse()
	args := flag.Args()

	// An output PNG is optional when -tap-dir is given: the parity harness
	// wants the stages, not a picture, and making it name a PNG it will not
	// read would be a lie about what this run produces.
	minArgs := 2
	usageTail := "<input> <output.png>"
	if *tapFlag != "" {
		minArgs = 1
		usageTail = "<input> [output.png]"
	}
	if len(args) < minArgs {
		fmt.Fprintf(os.Stderr, "Usage: %s [flags] %s\n", os.Args[0], usageTail)
		flag.PrintDefaults()
		os.Exit(1)
	}
	inputPath := args[0]
	outputPath := ""
	if len(args) > 1 {
		outputPath = args[1]
	}

	dx1, dx2, err := parseDXString(*dxFlag)
	if err != nil {
		log.Fatalf("-dx: %v", err)
	}

	var filmBase [3]int
	if *filmBaseFlag != "" {
		if filmBase, err = ParseTriple(*filmBaseFlag); err != nil {
			log.Fatalf("-film-base: %v", err)
		}
	}

	// -raw-in decides both how the pixels are read and which axis of the grid
	// indexes CCD pixels, because those are the same fact. A raw blob is on
	// the capture's own grid (x); a TIFF has been through
	// pakon_decode.to_frame_image, which rot90s it (y). Getting this wrong
	// does not error, it silently drops FindDmin's window — see dmin.go.
	ccdAxis := CcdAxisY
	rawH, rawW := 0, 0
	if *rawInFlag != "" {
		if rawH, rawW, err = parseHW(*rawInFlag); err != nil {
			log.Fatalf("-raw-in: %v", err)
		}
		ccdAxis = CcdAxisX
	}

	coeffPath, err := ResolveCoeffPath(*coeffPathFlag)
	if err != nil {
		log.Fatalf("-coeffs: %v", err)
	}
	anselRoot, err := ResolveAnselRoot(*anselRootFlag)
	if err != nil {
		log.Fatalf("-ansel-root: %v", err)
	}
	// <root>/anselinstalldir/dataPathItems -> <root>, which is the F-X35 COM
	// SERVER directory Config/ColorCorrection hangs off.
	fx35Root := filepath.Dir(filepath.Dir(anselRoot))

	req := &RenderRequest{
		Model:             *modelFlag,
		FilmPath:          *filmPathFlag,
		DXPart1:           dx1,
		DXPart2:           dx2,
		ISO:               *isoFlag,
		AnselPath:         *anselPathFlag,
		SourceType:        *sourceTypeFlag,
		CoeffSource:       CoeffSource(*coeffSourceFlag),
		CoeffPath:         coeffPath,
		FilmBase:          filmBase,
		FilmBaseFromFrame: *filmBaseFromFrameFlag,
		CcdAxis:           ccdAxis,
		StageOrder:        StageOrder(*stageOrderFlag),
		IccInput:          IccInputDepth(*iccInputFlag),
		FugcMode:          *fugcModeFlag,
		TapDir:            *tapFlag,
	}

	// Validate BEFORE the pixels are read, not after. Every refusal in
	// request.go is a statement about the request, not about the image, so
	// there is no reason to decode a frame first — and reporting "-stage-order
	// banana" only after a TIFF decode has already failed on an unrelated
	// problem hides the flag error behind an irrelevant one.
	if err := req.Validate(); err != nil {
		log.Fatalf("%v", err)
	}

	fr, err := readFrame(inputPath, rawH, rawW)
	if err != nil {
		log.Fatalf("%v", err)
	}

	eng, err := OpenEngine(fx35Root, anselRoot, req)
	if err != nil {
		log.Fatalf("OpenEngine failed: %v", err)
	}

	// stderr, not stdout: docs/62 §3.4's ABI contract, so a caller reading
	// stdout as a payload never sees a log line mixed into it.
	logf := func(format string, a ...any) { fmt.Fprintf(os.Stderr, format, a...) }
	
	emit := func(out, bypass *image.RGBA) error {
		if outputPath == "" {
			// -tap-dir with no output PNG: the stages ARE the product.
			return nil
		}
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