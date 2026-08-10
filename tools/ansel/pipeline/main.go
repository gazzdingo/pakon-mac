package main

import (
	"bufio"
	"flag"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"log"
	"os"
	"strconv"
	"strings"

	"golang.org/x/image/tiff"
)

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

func processImage(inputPath, outputPath string, profile *ColorProfile, rpd2pcs, srgb *IccMft2, model string, coeffs []float32, band3 *ThreeBandLut) error {
	f, err := os.Open(inputPath)
	if err != nil {
		return err
	}
	defer f.Close()
	
	var img image.Image
	if strings.HasSuffix(strings.ToLower(inputPath), ".tiff") || strings.HasSuffix(strings.ToLower(inputPath), ".tif") {
		img, err = tiff.Decode(f)
	} else {
		img, _, err = image.Decode(f)
	}
	if err != nil {
		return err
	}
	
	bounds := img.Bounds()
	outImg := image.NewRGBA(bounds)
	bypassImg := image.NewRGBA(bounds)

	height := bounds.Max.Y - bounds.Min.Y
	width := bounds.Max.X - bounds.Min.X
	
	rpd12 := make([][][3]float64, height)
	var planeR, planeG, planeB []int

	clamp4k := func(v int) int {
		if v < 0 { return 0 }
		if v > 4095 { return 4095 }
		return v
	}

	// --- Single pass ---
	// F-135: PolyPixel (TLB.dll:fcn.1000d880, 3x10 quadratic, ROM12 out)
	//        -> SRA forward LUT (common-sraFwdLut-metric-rom12.lut, ROM12 -> RPD12).
	//        No NegLut / NegMat: those are the F-235 (TLA) stage-2 tables.
	for y := bounds.Min.Y; y < bounds.Max.Y; y++ {
		yy := y - bounds.Min.Y
		rpd12[yy] = make([][3]float64, width)
		for x := bounds.Min.X; x < bounds.Max.X; x++ {
			xx := x - bounds.Min.X
			r, g, b, _ := img.At(x, y).RGBA()

			var outR, outG, outB float32

			if model == "f135" {
				polyOut := PolyPixel([3]int{int(r), int(g), int(b)}, coeffs)

				outR = float32(profile.SraLut[clamp4k(polyOut[0])])
				outG = float32(profile.SraLut[clamp4k(polyOut[1])])
				outB = float32(profile.SraLut[clamp4k(polyOut[2])])

				if x == bounds.Min.X && y == bounds.Min.Y {
					fmt.Printf("DEBUG pixel[0,0] raw=%d,%d,%d polyOut=%v sra=%.0f,%.0f,%.0f\n",
						int(r), int(g), int(b), polyOut, outR, outG, outB)
				}

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
	
	frameDmin := frameDminRgbFromPlanes(planeR, planeG, planeB, 4096)
	
	// Kodak Gold 400 (DX code 96) SBA parameters from sba-CN-default-96-1.dpi
	fpo := [3]int{879, 1250, 1386} // Film Printing Offset (orange-mask aim density)
	fpa := [3]int{-75, -50, -25}   // Film Preference Adjustment (Kodak Gold 400 specific)
	nbp := 18
	nb  := 130 // neutralButton
	prefA := PreferenceShiftsFromDpiFields(fpo, fpa, nbp, nb, -16.0, 16.0, 0)
	
	setshiftsOut := SetShifts12(prefA, prefA, band3.Planar, band3.NumLut)
	
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
	
	// toned is balanced; Shasta runs after FUGC on final RPD12 values
	toned := balanced
	
	fugcDmin := [3]int{500, 500, 500}
	afilmAim := [3]int{500, 1000, 1000}
	var fugcApplyLut [][3]float32
	if model == "f135" {
		fugcApplyLut = BuildMode2ApplyLut(profile.Fugc[:], fugcDmin, setshiftsOut, afilmAim)
	} else {
		fugcApplyLut, _ = BuildSetLutInfoApplyLut(profile.Fugc[:], fugcDmin, setshiftsOut, frameDmin, afilmAim)
	}
	
	fmt.Printf("DEBUG: frameDmin=%v\n", frameDmin)
	fmt.Printf("DEBUG: prefA=%v\n", prefA)
	fmt.Printf("DEBUG: setshiftsOut=%v\n", setshiftsOut)
	
	minB, maxB := 9999.0, 0.0
	for y := 0; y < 100; y++ {
		for x := 0; x < 100; x++ {
			if balanced[y][x][0] < minB { minB = balanced[y][x][0] }
			if balanced[y][x][0] > maxB { maxB = balanced[y][x][0] }
		}
	}
	fmt.Printf("DEBUG: balanced R range (first 100x100) = %v to %v\n", minB, maxB)
	
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

	// Shasta tone LUT requires full scene analysis (aim codes from image stats)
	// and cannot be approximated with a simple percentile. Skip for now.
	// shasted := LinkedPercentileTone(fugcOut, 3000.0, 1.0, 99.0, 4095.0)
	shasted := fugcOut

	var sum [3]float64
	for y := 0; y < height; y++ {
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
			sum[0] += float64(srgbColor[0])
			sum[1] += float64(srgbColor[1])
			sum[2] += float64(srgbColor[2])
		}
	}
	n := float64(width * height)
	fmt.Printf("OUTPUT mean sRGB per channel: R=%.1f G=%.1f B=%.1f\n", sum[0]/n, sum[1]/n, sum[2]/n)

	outBypass, _ := os.Create(outputPath + "_bypass.png")
	png.Encode(outBypass, bypassImg)
	outBypass.Close()
	
	out, err := os.Create(outputPath)
	if err != nil {
		return err
	}
	defer out.Close()
	return png.Encode(out, outImg)
}

func main() {
	modelFlag := flag.String("model", "f135", "Pipeline model: f135 (polynomial) or f235 (matrix/LUT)")
	coeffsFlag := flag.String("coeffs", "/Users/guy/www/pakon-mac/research/windows-registry/pakon_registry_full.txt", "Path to the registry .txt or EEPROM file containing coefficients (for f135)")
	flag.Parse()

	args := flag.Args()
	if len(args) < 2 {
		log.Fatalf("Usage: %s [-model f135|f235] <input> <output>\n", os.Args[0])
	}
	inputPath := args[0]
	outputPath := args[1]

	lutPath := "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/Config/ColorCorrection/_ClientColNegLut.txt"
	matPath := "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/Config/ColorCorrection/_ClientColNegMat.txt"
	fugcPath := "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/anselinstalldir/dataPathItems/fugc/fugc-generic0225.lut"
	rpd2pcsPath := "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/anselinstalldir/dataPathItems/profile/Rpd2Pcs_HR200_QS_v5s10.pf"
	srgbPath := "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/anselinstalldir/dataPathItems/profile/Srgb_v2.pf"
	sraPath := "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/anselinstalldir/dataPathItems/common/common-sraFwdLut-metric-rom12.lut"
	band3Path := "/Users/guy/Downloads/Pakon Update 2/fx35install/program files/Pakon/F-X35 COM SERVER/anselinstalldir/dataPathItems/common/luts6_postROMM_equalRGBshort.lut"

	profile, err := LoadProfile(lutPath, matPath, fugcPath, sraPath)
	if err != nil {
		log.Fatalf("Error loading base profile: %v", err)
	}
	
	var coeffs []float32
	if *modelFlag == "f135" {
		coeffs, err = LoadMatrixRegistry(*coeffsFlag, 1) 
		if err != nil {
			log.Fatalf("Error loading f135 coefficients from %s: %v", *coeffsFlag, err)
		}
	}
	
	rpd2pcs, err := LoadICCProfile(rpd2pcsPath)
	if err != nil {
		log.Fatalf("Error loading Rpd2Pcs: %v", err)
	}
	
	srgb, err := LoadICCProfileB2A0(srgbPath)
	if err != nil {
		log.Fatalf("Error loading Srgb: %v", err)
	}
	
	band3, err := Load3BandLutAscii(band3Path)
	if err != nil {
		log.Fatalf("Error loading 3band lut: %v", err)
	}
	
	err = processImage(inputPath, outputPath, profile, rpd2pcs, srgb, *modelFlag, coeffs, band3)
	if err != nil {
		log.Fatalf("Failed to process image: %v", err)
	}
	fmt.Printf("Successfully saved %s\n", outputPath)
}

// importSort unused
func strictMinMax(vals []float64) (float64, float64) {
	min, max := vals[0], vals[0]
	for _, v := range vals {
		if v < min { min = v }
		if v > max { max = v }
	}
	return min, max
}



