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

// SelectSbaKey walks sba.map's rules in order and returns the first match,
// together with the rule that matched. Selector columns are: _AnselPath_
// scannerName sourceType productCode genCode _AnselImageSize_, then the key.
//
// The matched rule is returned rather than discarded because it is the only
// thing that distinguishes "this stock's own dpi was selected" from "the
// wildcard row answered because there was nothing to select on". Both are
// legitimate vendor outcomes; they are not the same claim about the frame.
func SelectSbaKey(mapPath, anselPath string, sourceType int, dx DX) (string, string, error) {
	f, err := os.Open(mapPath)
	if err != nil {
		return "", "", err
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
		return key, strings.Join(fs, " "), nil
	}
	return "", "", fmt.Errorf("%s: no rule matched", mapPath)
}

// SelectShastaKey walks shasta.map. Columns: _AnselPath_ _AnselToneStrategy_
// _AnselToneAggrSetting_ _AnselImageSize_, then the key.
func SelectShastaKey(mapPath, anselPath string) (string, string, error) {
	f, err := os.Open(mapPath)
	if err != nil {
		return "", "", err
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
		return fs[4], strings.Join(fs, " "), nil
	}
	return "", "", fmt.Errorf("%s: no rule matched", mapPath)
}

// fugcLutMapByMode is what AnsFugcMapping (PakonIMAu.dll @ 0x101fb140)
// selects on: the `mode` field of fugc/fugc-defaultParams.dpi.
//
// fugc-lutMap.map is NOT one of the options. It is the 08/28/2002 original
// both variants were split out of, and nothing in the DLL selects it. This
// pipeline opened it anyway until now, which was the single largest numeric
// divergence between the Go and Python engines: the shipped dpi says
// `mode = RGB`, the rgb map (10/24/2003) has every per-film rule commented
// out so every stock falls through to its `film = X X X 2.25` catch-all, and
// that resolves to NoShift_fugc-generic0225.lut — which differs from the
// fugc-generic0225.lut the 2002 map hands back in 705 rows, by up to 60
// codes, over indices 237…943. For ISO 100/200 and ~100 other DX codes the
// 2002 map also picks a different contrast class outright.
//
// Cite: tools/ansel/python-pipeline/pakon_ansel_maps.py:fugc_lut_map_path.
var fugcLutMapByMode = map[string]string{
	"RGB":     "fugc-rgb-lutMap.map",
	"NEUTRAL": "fugc-neutral-lutMap.map",
}

// FugcLutMapPath resolves (map file, mode) the way AnsFugcMapping does.
// There is no default: if the dpi carries no `mode`, there is nothing to
// select on and this refuses rather than falling back to the 2002 file.
func FugcLutMapPath(items string) (string, string, error) {
	dpi := filepath.Join(items, "fugc", "fugc-defaultParams.dpi")
	f, err := os.Open(dpi)
	if err != nil {
		return "", "", err
	}
	defer f.Close()

	mode := ""
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if strings.EqualFold(strings.TrimSpace(parts[0]), "mode") {
			mode = strings.ToUpper(strings.TrimSpace(parts[1]))
			break
		}
	}
	if err := sc.Err(); err != nil {
		return "", "", err
	}
	if mode == "" {
		return "", "", fmt.Errorf(
			"%s: no 'mode =' field. AnsFugcMapping (0x101fb140) selects the "+
				"FUGC lutMap on it; without it there is nothing to select on",
			dpi)
	}
	name, ok := fugcLutMapByMode[mode]
	if !ok {
		return "", "", fmt.Errorf("%s: mode = %q is not RGB or NEUTRAL", dpi, mode)
	}
	path := filepath.Join(items, "fugc", name)
	if st, statErr := os.Stat(path); statErr != nil || st.IsDir() {
		return "", "", fmt.Errorf("%s (selected by mode = %s): %v", path, mode, statErr)
	}
	return path, mode, nil
}

// LoadFugcATableDmin reads the `aTableDmin` header of a shipped fugc-*.lut.
// It is analyze's +0x60f8 word (Cap +0xe0). Every file in this install
// carries 500 500 500, which is why hardcoding it was survivable — but it is
// a per-file field and reading it is one line.
func LoadFugcATableDmin(path string) ([3]int, error) {
	dmin := [3]int{500, 500, 500}
	f, err := os.Open(path)
	if err != nil {
		return dmin, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if !strings.EqualFold(strings.TrimSpace(parts[0]), "aTableDmin") {
			continue
		}
		fs := strings.Fields(parts[1])
		if len(fs) < 3 {
			continue
		}
		var out [3]int
		for i := 0; i < 3; i++ {
			v, cerr := strconv.Atoi(fs[i])
			if cerr != nil {
				return dmin, fmt.Errorf("%s: aTableDmin %q: %w", path, fs[i], cerr)
			}
			out[i] = v
		}
		return out, nil
	}
	return dmin, sc.Err()
}

// LoadAfilmAimDmin reads `aFilmAimDmin` from fugc-defaultParams.dpi — Cap
// +0x12, the aim the 0x101fc3c4 policy branch falls back to. Cite the copy
// into Cap at 0x10118380.
func LoadAfilmAimDmin(items string) ([3]int, error) {
	aim := [3]int{500, 1000, 1000}
	dpi := filepath.Join(items, "fugc", "fugc-defaultParams.dpi")
	f, err := os.Open(dpi)
	if err != nil {
		return aim, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if !strings.EqualFold(strings.TrimSpace(parts[0]), "aFilmAimDmin") {
			continue
		}
		fs := strings.Fields(parts[1])
		if len(fs) < 3 {
			continue
		}
		var out [3]int
		for i := 0; i < 3; i++ {
			v, cerr := strconv.Atoi(fs[i])
			if cerr != nil {
				return aim, fmt.Errorf("%s: aFilmAimDmin %q: %w", dpi, fs[i], cerr)
			}
			out[i] = v
		}
		return out, nil
	}
	return aim, sc.Err()
}

// SelectFugcLut walks the selected fugc lutMap. Two tables: film (dx1, dx2, iso) →
// contrast, then contrast → LUT filename. Both first-match, and the ISO rules
// come first, so an ISO 400 stock takes contrast 2.25 whatever its DX is.
//
// It also returns the film row that matched. Every shipped lutMap ends with a
// `# Default` row of `film = X X X <contrast>`, so a request that carries no
// DX and no ISO is answered by the vendor's own catch-all rather than by
// anything this port invents — and on fugc-rgb-lutMap.map, which `mode = RGB`
// selects, that catch-all is the ONLY live row: every per-film rule in it is
// commented out. On that map the ISO cannot change the outcome for any stock.
func SelectFugcLut(mapPath string, dx DX) (float64, string, string, error) {
	f, err := os.Open(mapPath)
	if err != nil {
		return 0, "", "", err
	}
	defer f.Close()

	contrast := -1.0
	rule := ""
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
				rule = "film = " + strings.Join(fs, " ")
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
		return 0, "", "", fmt.Errorf("%s: no film rule matched", mapPath)
	}
	for _, k := range order {
		if c, err := strconv.ParseFloat(k, 64); err == nil && c == contrast {
			return contrast, lutByContrast[k], rule, nil
		}
	}
	return contrast, "", rule, fmt.Errorf("%s: contrast %.2f has no LUT", mapPath, contrast)
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
	DX          DX
	Sba         *SbaDpi
	Shasta      *ShastaDpi
	FugcLut     string
	Contrast    float64
	FugcMapFile string // which lutMap AnsFugcMapping selected
	FugcMode    string // the fugc-defaultParams.dpi `mode` it selected on
	FugcDmin    [3]int // aTableDmin, read from the selected .lut
	FugcAim     [3]int // aFilmAimDmin, read from fugc-defaultParams.dpi

	// Provenance. Every selection this made records the vendor rule that
	// answered it, so a defaulted stock can be told apart from a chosen one
	// at every layer above this — see Engine.Resolution.
	SbaRule    string // the sba.map row that matched
	ShastaRule string // the shasta.map row that matched
	FugcRule   string // the lutMap `film =` row that matched

	// DXDefaulted is true when no DX reached this selection and the vendor's
	// wildcard rows are therefore what chose the stock. ISODefaulted likewise
	// for the film speed. Neither is an error; both are claims the operator
	// is entitled to see, because "Kodak Gold 400" and "whatever the map says
	// when nobody told it" are different statements about their photograph.
	DXDefaulted  bool
	ISODefaulted bool
}

// DefaultNote is one line of prose for a selection that had no DX or no ISO to
// go on, or "" when the operator's own selection drove it. It names the file
// and the row, so the claim is checkable rather than reassuring.
func (s *FilmSelection) DefaultNote() string {
	if !s.DXDefaulted && !s.ISODefaulted {
		return ""
	}
	missing := "DX"
	if s.DXDefaulted && s.ISODefaulted {
		missing = "DX or film speed"
	} else if s.ISODefaulted {
		missing = "film speed"
	}
	return fmt.Sprintf(
		"no %s was supplied, so the vendor's own wildcard rows chose this "+
			"stock: sba.map %q -> %s, and %s %q -> %s (contrast %.2f). This "+
			"is the F-135's documented no-DX behaviour, not a measurement of "+
			"the film in the gate",
		missing, s.SbaRule, s.Sba.Key, s.FugcMapFile, s.FugcRule, s.FugcLut,
		s.Contrast)
}

// SelectFilm runs the vendor's three selections for a DX number.
//
// NO DX IS A LEGITIMATE INPUT, BECAUSE THE VENDOR TREATS IT AS ONE. This used
// to refuse outright, which broke every roll on a unit whose DX board has
// never returned a code — and being stricter than the F-135's own software is
// a deviation from "byte for byte the same as pakon's", not a safeguard. The
// shipped selection tables carry the no-DX rows themselves:
//
//	sba/SbaDPI/sba.map      any any 1 any any any  -> ansel-sba-CN-default
//	                        (sourceType 1 = ANS_NEGATIVE_35; productCode and
//	                        genCode are `any`, which is exactly "no DX")
//	shasta/shasta.map       any any any any        -> ansel-shasta-rpd
//	fugc/fugc-rgb-lutMap.map  # Default
//	                        film = X X X 2.25      -> NoShift_fugc-generic0225.lut
//
// So CN-default is not this port's guess. It is the row the vendor's own map
// selects when nothing is known about the stock, which is why the install
// ships sba-CN-default.dpi at all. On fugc-rgb-lutMap.map — the file
// `mode = RGB` selects — every per-film rule is commented out and that `X X X`
// row is the only live one, so a missing ISO cannot change the FUGC LUT for
// any stock whatsoever.
//
// The defect this refusal was added to fix was never the defaulting. It was
// that the defaulting was SILENT: the owner's film was rendered as a stock
// nobody chose and nothing said so. The fix for silent is visible. So this
// defaults exactly as the vendor does and marks the result DXDefaulted, and
// every layer above — Engine.Resolution, roll.dx_source, the sidecar and the
// Review rail — carries that through to the screen.
//
// What still refuses: a film path whose stage-2 branch is not ported
// (RenderRequest.CheckFilmClass, POSITIVE/filmClass 2), and a film base of
// zero (CheckFilmBase). Those cannot be defaulted from anything the vendor
// ships. Cite: tools/ansel/python-pipeline/pakon_ansel_maps.py:select_ansel_files,
// which makes the same selection with the same reasons recorded.
func SelectFilm(items, dxSpec string, iso int, anselPath string, sourceType int) (*FilmSelection, error) {
	dxDefaulted := strings.TrimSpace(dxSpec) == ""
	isoDefaulted := iso <= 0

	dx, err := ParseDX(dxSpec, iso)
	if err != nil {
		return nil, err
	}

	sbaDir := filepath.Join(items, "sba", "SbaDPI")
	sbaKey, sbaRule, err := SelectSbaKey(filepath.Join(sbaDir, "sba.map"), anselPath, sourceType, dx)
	if err != nil {
		return nil, err
	}
	sba, err := LoadSbaDpi(sbaDir, sbaKey)
	if err != nil {
		return nil, err
	}

	shastaDir := filepath.Join(items, "shasta")
	shastaKey, shastaRule, err := SelectShastaKey(filepath.Join(shastaDir, "shasta.map"), anselPath)
	if err != nil {
		return nil, err
	}
	shasta, err := LoadShastaDpi(shastaDir, shastaKey)
	if err != nil {
		return nil, err
	}

	fugcMap, fugcMode, err := FugcLutMapPath(items)
	if err != nil {
		return nil, err
	}
	contrast, fugcLut, fugcRule, err := SelectFugcLut(fugcMap, dx)
	if err != nil {
		return nil, err
	}
	fugcDmin, err := LoadFugcATableDmin(filepath.Join(items, "fugc", fugcLut))
	if err != nil {
		return nil, err
	}
	fugcAim, err := LoadAfilmAimDmin(items)
	if err != nil {
		return nil, err
	}

	return &FilmSelection{
		DX: dx, Sba: sba, Shasta: shasta, FugcLut: fugcLut, Contrast: contrast,
		FugcMapFile: filepath.Base(fugcMap), FugcMode: fugcMode,
		FugcDmin: fugcDmin, FugcAim: fugcAim,
		SbaRule: sbaRule, ShastaRule: shastaRule, FugcRule: fugcRule,
		DXDefaulted: dxDefaulted, ISODefaulted: isoDefaulted,
	}, nil
}

// DXLabel is the DX as prose. "none (defaulted)" rather than "-1--1": a
// sentinel printed as a number reads like a film code, which is the one thing
// this must not be mistaken for.
func (s *FilmSelection) DXLabel() string {
	if s.DX.Part1 < 0 {
		return "none (defaulted)"
	}
	if s.DX.Part2 < 0 {
		return strconv.Itoa(s.DX.Part1)
	}
	return fmt.Sprintf("%d-%d", s.DX.Part1, s.DX.Part2)
}

// ISOLabel is the film speed as prose, for the same reason.
func (s *FilmSelection) ISOLabel() string {
	if s.DX.Iso <= 0 {
		return "none (defaulted)"
	}
	return strconv.Itoa(s.DX.Iso)
}

func (s *FilmSelection) Print() {
	fmt.Fprintf(os.Stderr, "film: DX %s ISO %s\n", s.DXLabel(), s.ISOLabel())
	if note := s.DefaultNote(); note != "" {
		fmt.Fprintf(os.Stderr, "  DEFAULTED: %s\n", note)
	}
	fmt.Fprintf(os.Stderr, "  sba.map        -> %s (%s)  fpo=%v fpa=%v nbp=%d neuBtn=%d\n",
		s.Sba.Key, s.Sba.File, s.Sba.Fpo, s.Sba.Fpa,
		s.Sba.NeutralBalancePoint, s.Sba.NeutralButton)
	fmt.Fprintf(os.Stderr, "  shasta.map     -> %s (%s)  black=%.0f gray=%.0f white=%.0f\n",
		s.Shasta.Key, s.Shasta.File, s.Shasta.Black, s.Shasta.MetricGray, s.Shasta.White)
	fmt.Fprintf(os.Stderr, "  fugc mode=%s   -> %s -> contrast %.2f -> %s  "+
		"aTableDmin=%v aFilmAimDmin=%v\n",
		s.FugcMode, s.FugcMapFile, s.Contrast, s.FugcLut, s.FugcDmin, s.FugcAim)
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
