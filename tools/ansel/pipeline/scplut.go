package main

import (
	"bufio"
	"os"
	"strconv"
	"strings"
)

type ThreeBandLut struct {
	Name     string
	NumLut   int
	NumBands int
	Planar   []int
}

func Load3BandLutAscii(path string) (*ThreeBandLut, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	name := "luts6_postROMM_equalRGBshort.lut"
	numLut := 4096
	numBands := 3

	type row struct {
		r, g, b int
	}
	rows := make(map[int]row)

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := scanner.Text()
		idx := strings.Index(line, "#")
		if idx != -1 {
			line = line[:idx]
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}

		if strings.Contains(line, "=") {
			parts := strings.SplitN(line, "=", 2)
			key := strings.ToUpper(strings.TrimSpace(parts[0]))
			val := strings.TrimSpace(parts[1])

			switch key {
			case "LUT_NAME":
				name = strings.Fields(val)[0]
			case "NUM_LUT":
				numLut, _ = strconv.Atoi(strings.Fields(val)[0])
			case "NUM_BANDS":
				numBands, _ = strconv.Atoi(strings.Fields(val)[0])
			}
			continue
		}

		parts := strings.Fields(line)
		if len(parts) == 4 {
			i, _ := strconv.Atoi(parts[0])
			r, _ := strconv.Atoi(parts[1])
			g, _ := strconv.Atoi(parts[2])
			b, _ := strconv.Atoi(parts[3])
			rows[i] = row{r, g, b}
		}
	}

	planar := make([]int, numLut*numBands)
	for i, r := range rows {
		if i >= 0 && i < numLut {
			planar[i] = r.r
			planar[i+numLut] = r.g
			planar[i+2*numLut] = r.b
		}
	}

	return &ThreeBandLut{
		Name:     name,
		NumLut:   numLut,
		NumBands: numBands,
		Planar:   planar,
	}, nil
}
