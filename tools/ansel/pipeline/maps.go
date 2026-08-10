package main

// Ansel .map selection, copied from the vendor's own map files.
//
// Nothing about the film stock is hardcoded in the pipeline any more: the DX
// number picks the SBA dpi, the FUGC contrast LUT and the Shasta dpi exactly
// the way the shipped .map files say. All three are first-match — "Only the
// first '.map' file containing this key is read" (sba.map header), and within
// a file the rules are tried top to bottom.
//
// The Python port of this lives in tools/ansel/pakon_ansel_maps.py; this is
// the same selection, written out for the Go pipeline.

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// DX is a Pakon film product: part 1 is the I3A/PIMA combination code
// (0…127), part 2 the generation code (0…15). The composite 4-digit DX
// number is part1*16 + part2.
type DX struct {
	Part1 int
	Part2 int
	Iso   int
}

// SbaDpi is the subset of an sba-*.dpi the colour pipeline reads.
type SbaDpi struct {
	Key                    string
	File                   string
	Fpo                    [3]int
	Fpa                    [3]int
	Neu                    [3]int
	Neo                    [3]int
	MinDmin                [3]int
	Pcls                   int
	NeutralButton          int
	NeutralBalancePoint    int
	NeutralUnderConstraint float64
	NeutralOverConstraint  float64
}

// ShastaDpi is the subset of a shasta-*.dpi the tone stage reads.
type ShastaDpi struct {
	Key           string
	File          string
	Black         float64
	White         float64
	MetricGray    float64
	MinValue      float64
	MaxValue      float64
	ShadowPercent float64
}

func dpiFields(path string) (map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	out := map[string]string{}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if line == "" || !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		out[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
	}
	return out, sc.Err()
}

func fieldInts3(m map[string]string, key string, def [3]int) [3]int {
	v, ok := m[key]
	if !ok {
		return def
	}
	fs := strings.Fields(v)
	if len(fs) < 3 {
		return def
	}
	var out [3]int
	for i := 0; i < 3; i++ {
		n, err := strconv.Atoi(fs[i])
		if err != nil {
			return def
		}
		out[i] = n
	}
	return out
}

func fieldInt(m map[string]string, key string, def int) int {
	if v, ok := m[key]; ok {
		if n, err := strconv.Atoi(strings.Fields(v)[0]); err == nil {
			return n
		}
	}
	return def
}

func fieldFloat(m map[string]string, key string, def float64) float64 {
	if v, ok := m[key]; ok {
		if n, err := strconv.ParseFloat(strings.Fields(v)[0], 64); err == nil {
			return n
		}
	}
	return def
}

// findDpiByKey scans a directory for the .dpi whose "key =" field matches.
// The .map files name a key, not a filename; the vendor resolves it this way.
func findDpiByKey(dir, key string) (string, map[string]string, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return "", nil, err
	}
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(strings.ToLower(e.Name()), ".dpi") {
			continue
		}
		p := filepath.Join(dir, e.Name())
		m, err := dpiFields(p)
		if err != nil {
			continue
		}
		if m["key"] == key {
			return p, m, nil
		}
	}
	return "", nil, fmt.Errorf("no .dpi in %s has key = %s", dir, key)
}

// tokenMatches implements the selector cell grammar: "any"/"X" wildcard, a
// literal number, or a "(lo,hi)" range.
func tokenMatches(tok string, value int, haveValue bool) bool {
	tok = strings.TrimSpace(tok)
	if tok == "any" || tok == "X" || tok == "x" {
		return true
	}
	if strings.HasPrefix(tok, "(") {
		return true // image-size ranges: not modelled, treat as wildcard
	}
	n, err := strconv.Atoi(tok)
	if err != nil {
		return false
	}
	return haveValue && n == value
}

// SelectSbaKey walks sba.map's rules in order and returns the first match.
// Selector columns are: _AnselPath_ scannerName sourceType productCode
// genCode _AnselImageSize_, then the key.
func SelectSbaKey(mapPath, anselPath string, sourceType int, dx DX) (string, error) {
	f, err := os.Open(mapPath)
	if err != nil {
		return "", err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	inRules := false
	for sc.Scan() {
		line := sc.Text()
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "mapping") {
			inRules = true
			continue
		}
		if !inRules || strings.Contains(line, "=") || strings.HasPrefix(line, "_") {
			continue
		}
		fs := strings.Fields(line)
		if len(fs) != 7 {
			continue
		}
		pathTok, srcTok, prodTok, genTok, key := fs[0], fs[2], fs[3], fs[4], fs[6]
		if pathTok != "any" && pathTok != anselPath {
			continue
		}
		if !tokenMatches(srcTok, sourceType, true) {
			continue
		}
		if !tokenMatches(prodTok, dx.Part1, dx.Part1 >= 0) {
			continue
		}
		if !tokenMatches(genTok, dx.Part2, dx.Part2 >= 0) {
			continue
		}
		return key, nil
	}
	return "", fmt.Errorf("%s: no rule matched", mapPath)
}

// SelectShastaKey walks shasta.map. Columns: _AnselPath_ _AnselToneStrategy_
// _AnselToneAggrSetting_ _AnselImageSize_, then the key.
func SelectShastaKey(mapPath, anselPath string) (string, error) {
	f, err := os.Open(mapPath)
	if err != nil {
		return "", err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	inRules := false
	for sc.Scan() {
		line := sc.Text()
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "mapping") {
			inRules = true
			continue
		}
		if !inRules || strings.Contains(line, "=") || strings.HasPrefix(line, "_") {
			continue
		}
		fs := strings.Fields(line)
		if len(fs) != 5 {
			continue
		}
		if fs[0] != "any" && fs[0] != anselPath {
			continue
		}
		// tone strategy / aggressiveness: default settings, so "1" (low) rules
		// are skipped and the "any" rule below them wins, as on the vendor
		// default path.
		if fs[1] != "any" {
			continue
		}
		return fs[4], nil
	}
	return "", fmt.Errorf("%s: no rule matched", mapPath)
}

// SelectFugcLut walks fugc-lutMap.map. Two tables: film (dx1, dx2, iso) →
// contrast, then contrast → LUT filename. Both first-match, and the ISO rules
// come first, so an ISO 400 stock takes contrast 2.25 whatever its DX is.
func SelectFugcLut(mapPath string, dx DX) (float64, string, error) {
	f, err := os.Open(mapPath)
	if err != nil {
		return 0, "", err
	}
	defer f.Close()

	contrast := -1.0
	lutByContrast := map[string]string{}
	var order []string

	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if line == "" || !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		lhs := strings.TrimSpace(parts[0])
		fs := strings.Fields(parts[1])

		switch lhs {
		case "film":
			if contrast >= 0 || len(fs) != 4 {
				continue
			}
			if !tokenMatches(fs[0], dx.Part1, dx.Part1 >= 0) {
				continue
			}
			if !tokenMatches(fs[1], dx.Part2, dx.Part2 >= 0) {
				continue
			}
			if !tokenMatches(fs[2], dx.Iso, dx.Iso > 0) {
				continue
			}
			if c, err := strconv.ParseFloat(fs[3], 64); err == nil {
				contrast = c
			}
		case "contrast":
			if len(fs) != 2 {
				continue
			}
			lutByContrast[fs[0]] = fs[1]
			order = append(order, fs[0])
		}
	}
	if contrast < 0 {
		return 0, "", fmt.Errorf("%s: no film rule matched", mapPath)
	}
	for _, k := range order {
		if c, err := strconv.ParseFloat(k, 64); err == nil && c == contrast {
			return contrast, lutByContrast[k], nil
		}
	}
	return contrast, "", fmt.Errorf("%s: contrast %.2f has no LUT", mapPath, contrast)
}

// LoadSbaDpi resolves an sba key to its file and reads the preference fields.
func LoadSbaDpi(dir, key string) (*SbaDpi, error) {
	path, m, err := findDpiByKey(dir, key)
	if err != nil {
		return nil, err
	}
	return &SbaDpi{
		Key:                    key,
		File:                   filepath.Base(path),
		Fpo:                    fieldInts3(m, "fpo", [3]int{879, 1250, 1386}),
		Fpa:                    fieldInts3(m, "fpa", [3]int{-70, -55, -45}),
		Neu:                    fieldInts3(m, "neu", [3]int{975, 975, 975}),
		Neo:                    fieldInts3(m, "neo", [3]int{1010, 1010, 1010}),
		MinDmin:                fieldInts3(m, "minDmin", [3]int{180, 550, 700}),
		Pcls:                   fieldInt(m, "pcls", 0),
		NeutralButton:          fieldInt(m, "neutralButton", 130),
		NeutralBalancePoint:    fieldInt(m, "neutralBalancePoint", 1550),
		NeutralUnderConstraint: fieldFloat(m, "neutralUnderConstraint", -16.0),
		NeutralOverConstraint:  fieldFloat(m, "neutralOverConstraint", 16.0),
	}, nil
}

// LoadShastaDpi resolves a shasta key to its file and reads the tone aims.
func LoadShastaDpi(dir, key string) (*ShastaDpi, error) {
	path, m, err := findDpiByKey(dir, key)
	if err != nil {
		return nil, err
	}
	return &ShastaDpi{
		Key:           key,
		File:          filepath.Base(path),
		Black:         fieldFloat(m, "black", 0),
		White:         fieldFloat(m, "white", 3000),
		MetricGray:    fieldFloat(m, "metricGray", 1618),
		MinValue:      fieldFloat(m, "minValue", 0),
		MaxValue:      fieldFloat(m, "maxValue", 4095),
		ShadowPercent: fieldFloat(m, "shadowPercent", 1.0),
	}, nil
}

// ParseDX accepts "96-1" or "96". Part2 -1 means unspecified (wildcard).
func ParseDX(s string, iso int) (DX, error) {
	dx := DX{Part1: -1, Part2: -1, Iso: iso}
	s = strings.TrimSpace(s)
	if s == "" {
		return dx, nil
	}
	parts := strings.SplitN(s, "-", 2)
	p1, err := strconv.Atoi(strings.TrimSpace(parts[0]))
	if err != nil {
		return dx, fmt.Errorf("bad DX %q", s)
	}
	dx.Part1 = p1
	if len(parts) == 2 {
		p2, err := strconv.Atoi(strings.TrimSpace(parts[1]))
		if err != nil {
			return dx, fmt.Errorf("bad DX %q", s)
		}
		dx.Part2 = p2
	}
	return dx, nil
}

// FilmSelection is everything the .map files decide for one film stock.
type FilmSelection struct {
	DX       DX
	Sba      *SbaDpi
	Shasta   *ShastaDpi
	FugcLut  string
	Contrast float64
}

// SelectFilm runs the vendor's three selections for a DX number.
func SelectFilm(items, dxSpec string, iso int, anselPath string, sourceType int) (*FilmSelection, error) {
	dx, err := ParseDX(dxSpec, iso)
	if err != nil {
		return nil, err
	}

	sbaDir := filepath.Join(items, "sba", "SbaDPI")
	sbaKey, err := SelectSbaKey(filepath.Join(sbaDir, "sba.map"), anselPath, sourceType, dx)
	if err != nil {
		return nil, err
	}
	sba, err := LoadSbaDpi(sbaDir, sbaKey)
	if err != nil {
		return nil, err
	}

	shastaDir := filepath.Join(items, "shasta")
	shastaKey, err := SelectShastaKey(filepath.Join(shastaDir, "shasta.map"), anselPath)
	if err != nil {
		return nil, err
	}
	shasta, err := LoadShastaDpi(shastaDir, shastaKey)
	if err != nil {
		return nil, err
	}

	contrast, fugcLut, err := SelectFugcLut(filepath.Join(items, "fugc", "fugc-lutMap.map"), dx)
	if err != nil {
		return nil, err
	}

	return &FilmSelection{DX: dx, Sba: sba, Shasta: shasta, FugcLut: fugcLut, Contrast: contrast}, nil
}

func (s *FilmSelection) Print() {
	fmt.Printf("film: DX %d-%d ISO %d\n", s.DX.Part1, s.DX.Part2, s.DX.Iso)
	fmt.Printf("  sba.map        -> %s (%s)  fpo=%v fpa=%v nbp=%d neuBtn=%d\n",
		s.Sba.Key, s.Sba.File, s.Sba.Fpo, s.Sba.Fpa,
		s.Sba.NeutralBalancePoint, s.Sba.NeutralButton)
	fmt.Printf("  shasta.map     -> %s (%s)  black=%.0f gray=%.0f white=%.0f\n",
		s.Shasta.Key, s.Shasta.File, s.Shasta.Black, s.Shasta.MetricGray, s.Shasta.White)
	fmt.Printf("  fugc-lutMap    -> contrast %.2f -> %s\n", s.Contrast, s.FugcLut)
}

// ShastaParams adapts the selected dpi to the tone stage's view of it.
func (s *FilmSelection) ShastaParams() ShastaParams {
	return ShastaParams{
		Black:         s.Shasta.Black,
		MetricGray:    s.Shasta.MetricGray,
		White:         s.Shasta.White,
		ShadowPercent: s.Shasta.ShadowPercent,
		MinValue:      s.Shasta.MinValue,
		MaxValue:      s.Shasta.MaxValue,
	}
}
