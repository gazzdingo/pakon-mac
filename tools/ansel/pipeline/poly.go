package main

import (
	"bufio"
	"fmt"
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

func LoadMatrixRegistry(path string, filmClass int) ([]float32, error) {
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
