package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
)

const (
	PolyMax  = 4095.0
	PolyMin  = 0.0
	PolyHalf = 0.5
)

// f32 simulates rounding a float64 to float32
func f32(x float64) float64 {
	return float64(float32(x))
}

// ftol simulates MSVC _ftol (truncate toward zero)
func ftol(x float64) int {
	return int(x)
}

// Offsets of the two 3x10 float32 matrices inside the 0x52 calibration EEPROM.
// The 256-byte page is a float32 array based at byte offset 1; NegMatrix is
// elements 9..38 (byte 0x25) and PosMatrix elements 39..68 (byte 0x9d). This
// mirrors tools/pakon_color.py:eeprom_matrix_offsets exactly — see that
// docstring for the alignment evidence, and docs/58 s4.4.
const (
	eepromFloatBase = 1
	eepromNegIndex  = 9
	eepromPosIndex  = 39
)

// LoadMatrixCoeffs reads this unit's 30 stage-2 polynomial coefficients from
// either coefficient source, dispatching on the file's content.
//
// The calibration EEPROM .bin is preferred, and is what -coeffs defaults to.
// The Windows registry dump is the vendor's own runtime source, but TLB wrote
// those values out with "%f" — six decimal places — so every coefficient below
// 1e-6 is quantised to one significant figure and three of the thirty round to
// zero outright. The quadratic terms reach ~270 codes at full scale, so that
// rounding is worth up to ~116 codes of 4095.
// LoadMatrixCoeffsFrom is LoadMatrixCoeffs with the source stated rather than
// sniffed. docs/62 §2.11: "auto" is not a legal answer here. The EEPROM is the
// higher-precision calibration store; the registry is what TLB actually read
// into its runtime float32 matrix after writing the values out with "%f",
// which quantises the ~1e-6 quadratic terms and rounds three of the thirty to
// zero. They differ by 14-57 RPD codes at (4000,4000,4000), and which one is
// right depends on whether you are replaying the vendor byte-for-byte or
// rendering the best image. The caller has to say.
//
// The file is still dispatched on content, so a mislabelled path is caught
// rather than silently parsed as the other format.
func LoadMatrixCoeffsFrom(source CoeffSource, path string, filmClass int) ([]float32, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	isRegistry := bytes.Contains(data, []byte(`"NegMatrix`)) || bytes.Contains(data, []byte(`"PosMatrix`))
	switch source {
	case CoeffRegistry:
		if !isRegistry {
			return nil, fmt.Errorf(
				"-coeff-source registry but %s is not a registry hive export "+
					"(no \"NegMatrix / \"PosMatrix values in it)", path)
		}
		return loadMatrixRegistryText(path, filmClass)
	case CoeffEeprom:
		if isRegistry {
			return nil, fmt.Errorf(
				"-coeff-source eeprom but %s is a registry hive export. "+
					"Point -coeffs at the calibration EEPROM .bin, or pass "+
					"-coeff-source registry and mean it", path)
		}
		return loadMatrixEEPROM(path, data, filmClass)
	default:
		return nil, fmt.Errorf("coefficient source %q is not eeprom or registry", source)
	}
}

func LoadMatrixCoeffs(path string, filmClass int) ([]float32, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	// The registry dump is a text hive export; the EEPROM is a raw 256-byte
	// page. Dispatch on content, not extension, so either works under any name.
	if bytes.Contains(data, []byte(`"NegMatrix`)) || bytes.Contains(data, []byte(`"PosMatrix`)) {
		return loadMatrixRegistryText(path, filmClass)
	}
	return loadMatrixEEPROM(path, data, filmClass)
}

// loadMatrixEEPROM parses the raw calibration EEPROM page. Ported from
// tools/pakon_color.py:load_matrix_eeprom — little-endian float32, and any
// elements running past the end of the page are zero-filled (PosMatrix 24..29
// are genuinely absent from the 256-byte page we have).
func loadMatrixEEPROM(path string, data []byte, filmClass int) ([]float32, error) {
	off := eepromFloatBase + 4*eepromNegIndex // 0x25
	key := "NegMatrix"
	if filmClass == 2 {
		off = eepromFloatBase + 4*eepromPosIndex // 0x9d
		key = "PosMatrix"
	}

	avail := 0
	if len(data) > off {
		avail = (len(data) - off) / 4
	}
	if avail <= 0 {
		return nil, fmt.Errorf("%s: %d-byte file holds no %s at offset %#x",
			path, len(data), key, off)
	}
	n := avail
	if n > 30 {
		n = 30
	}

	out := make([]float32, 30)
	for i := 0; i < n; i++ {
		out[i] = math.Float32frombits(binary.LittleEndian.Uint32(data[off+4*i:]))
	}
	// n < 30 leaves the tail zero, matching the Python reader.
	return out, nil
}

func loadMatrixRegistryText(path string, filmClass int) ([]float32, error) {
	key := "NegMatrix"
	if filmClass == 2 {
		key = "PosMatrix"
	}

	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	vals := make(map[int]float32)
	scanner := bufio.NewScanner(file)

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if !strings.HasPrefix(line, `"`+key) {
			continue
		}

		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}

		name := strings.Trim(strings.TrimSpace(parts[0]), `"`)
		if !strings.HasPrefix(name, key) {
			continue
		}

		idxStr := name[len(key):]
		idx, err := strconv.Atoi(idxStr)
		if err != nil {
			continue
		}

		rest := parts[1]
		valParts := strings.SplitN(rest, ":", 2)
		if len(valParts) != 2 {
			continue
		}

		val, err := strconv.ParseFloat(strings.TrimSpace(valParts[1]), 32)
		if err != nil {
			continue
		}

		vals[idx] = float32(val)
	}

	if err := scanner.Err(); err != nil {
		return nil, err
	}

	if len(vals) < 30 {
		return nil, fmt.Errorf("%s: found only %d %s values", path, len(vals), key)
	}

	out := make([]float32, 30)
	for i := 0; i < 30; i++ {
		out[i] = vals[i]
	}
	return out, nil
}

// PolyPixel implements TLB.dll:fcn.1000d880
func PolyPixel(rgb [3]int, coeffs []float32) [3]int {
	r := float64(rgb[0] & 0xFFFF)
	g := float64(rgb[1] & 0xFFFF)
	b := float64(rgb[2] & 0xFFFF)

	rr := r * r
	gg := g * g
	bb := f32(b * b)
	rg := f32(r * g)
	rb := f32(r * b)
	gb := f32(g * b)

	var out [3]int
	for k := 0; k < 3; k++ {
		c := coeffs[10*k : 10*k+10]
		acc := float64(c[0])*r + float64(c[1])*g
		acc += float64(c[2]) * b
		acc += float64(c[3]) * rr
		acc += float64(c[4]) * gg
		acc += float64(c[5]) * bb
		acc += float64(c[6]) * rg
		acc += float64(c[7]) * rb
		acc += float64(c[8]) * gb
		acc += float64(c[9])

		acc = f32(acc + PolyHalf)
		if acc < PolyMin {
			acc = PolyMin
		} else if acc > PolyMax {
			acc = PolyMax
		}

		out[k] = ftol(acc)
	}
	return out
}
