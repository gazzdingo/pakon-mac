package ansdra

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// TtcMaxPoints is the 100-point float32[100] block the params object reserves
// per curve; TtcBlockStride is proven by the six *TTC parser offsets being
// exactly this far apart.
const (
	TtcMaxPoints   = 100
	TtcBlockStride = 0x4B4
)

// Ttc is one .ttc tone-transfer curve: whitespace `in out` pairs.
//
// Slope is NOT read from the file — it is the params block's third
// float32[100] array, computed by the .dpi parser's leaf 0x10227c60 alongside
// each point, and it is what KeepMidPtLut actually interpolates with. A port
// that only parsed x/y would be silently incomplete downstream.
type Ttc struct {
	Name  string
	X     []float64
	Y     []float64
	Slope []float64
}

// BuildTtcSlopes is 0x10227e93..0x10227eab — the per-segment finite-difference
// slope: slope[i] = f32((y[i+1] - y[i]) / (x[i+1] - x[i])). Float32 in, float32
// out, the division itself at register precision.
func BuildTtcSlopes(x, y []float64) []float64 {
	n := len(x)
	if n < 2 {
		return []float64{}
	}
	slopes := make([]float64, n-1)
	for i := 0; i < n-1; i++ {
		dy := f32(y[i+1]) - f32(y[i])
		dx := f32(x[i+1]) - f32(x[i])
		slopes[i] = f32(dy / dx)
	}
	return slopes
}

// ParseTtc parses a .ttc: `#` comments, then whitespace-separated `x y`. The
// shipped files end with a `10 10` sentinel far outside the [0,1] domain — an
// extrapolation guard, kept verbatim, not stripped.
func ParseTtc(path string) (Ttc, error) {
	curve := Ttc{Name: filepath.Base(path)}
	raw, err := os.ReadFile(path)
	if err != nil {
		return curve, err
	}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimRight(line, "\r")
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) < 2 {
			continue
		}
		xv, err := strconv.ParseFloat(parts[0], 64)
		if err != nil {
			return curve, fmt.Errorf("%s: %q is not a number", path, parts[0])
		}
		yv, err := strconv.ParseFloat(parts[1], 64)
		if err != nil {
			return curve, fmt.Errorf("%s: %q is not a number", path, parts[1])
		}
		curve.X = append(curve.X, f32(xv))
		curve.Y = append(curve.Y, f32(yv))
	}
	if len(curve.X) > TtcMaxPoints {
		return curve, fmt.Errorf("%s: %d points exceeds the %d-point block the "+
			"params object reserves", filepath.Base(path), len(curve.X),
			TtcMaxPoints)
	}
	curve.Slope = BuildTtcSlopes(curve.X, curve.Y)
	return curve, nil
}

// ---------------------------------------------------------------------------
// AnsDraParams
// ---------------------------------------------------------------------------

// Params is the parsed params object. Offsets in the comments are relative to
// generateLut's params pointer (impl+0x10), which is the parser's own base
// minus 0x2c.
type Params struct {
	MaxValue            int64   // +0x00 %hd
	LowFixedPoint       int64   // +0x02 %hd
	HighFixedPoint      int64   // +0x04 %hd
	PaperMin            int64   // +0x06 %hd
	PaperMax            int64   // +0x08 %hd
	MinSlope            float64 // +0x0c %f   (dead — see GenerateLut)
	MaxSlope            float64 // +0x10 %f   (dead — see GenerateLut)
	BinFactor           int64   // +0x14 %ld
	BDoAverage          bool    // +0x18 %c
	LumWeighting        float64 // +0x1c %f
	EdgeWeighting       float64 // +0x20 %f
	BIsBacklit          bool    // +0x24 %c
	BIsFlash            bool    // +0x25 %c
	FlashFraction       float64 // +0x28 %f
	BacklitFraction     float64 // +0x2c %f
	StartingMinCumPoint float64 // +0x30 %f
	CumPctBelowMin      float64 // +0x34 %f
	StartingMaxCumPoint float64 // +0x38 %f
	CumPctAboveMax      float64 // +0x3c %f

	// The six curve blocks, +0x40 / +0x4f4 / +0x9a8 / +0xe5c / +0x1310 /
	// +0x17c4, keyed by their .dpi key.
	Curves map[string]Ttc
}

// The six *TTC .dpi keys, in parser order.
const (
	KeyLowNormalTTC    = "lowNormalTTC"
	KeyHighNormalTTC   = "highNormalTTC"
	KeyLowBacklitTTC   = "lowBacklitTTC"
	KeyHighBacklitTTC  = "highBacklitTTC"
	KeyLowFrontlitTTC  = "lowFrontlitTTC"
	KeyHighFrontlitTTC = "highFrontlitTTC"
)

// LightingCurveKeys is keepMidPtLut's head, 0x102290d6..0x102291c8: `cmp dx,1`
// / `cmp dx,2` and EVERYTHING else — including the 0 a find("lighting") miss
// produces — falls through to the Normal pair.
func LightingCurveKeys(lighting int64) (string, string) {
	switch lighting {
	case LightingBacklit:
		return KeyLowBacklitTTC, KeyHighBacklitTTC
	case LightingFrontlit:
		return KeyLowFrontlitTTC, KeyHighFrontlitTTC
	default:
		return KeyLowNormalTTC, KeyHighNormalTTC
	}
}

// CurvePair is the (low, high) curve pair keepMidPtLut selects.
func (p Params) CurvePair(lighting int64) (Ttc, Ttc, error) {
	loKey, hiKey := LightingCurveKeys(lighting)
	lo, ok := p.Curves[loKey]
	if !ok {
		return Ttc{}, Ttc{}, fmt.Errorf("dra params have no %s curve", loKey)
	}
	hi, ok := p.Curves[hiKey]
	if !ok {
		return Ttc{}, Ttc{}, fmt.Errorf("dra params have no %s curve", hiKey)
	}
	return lo, hi, nil
}

// ---------------------------------------------------------------------------
// the .dpi parser — 0x102283a0
//
// The CRT's own sscanf does the tokenising and every numeric conversion (the
// `call ebx` at 0x1022841e and at each key's arm). The helpers below reproduce
// sscanf's semantics for exactly the five conversion specifiers this function
// uses, because the DIFFERENCE between them and a naive split is observable.
// ---------------------------------------------------------------------------

const cWhitespace = " \t\n\r\v\f"

func isCSpace(b byte) bool { return strings.IndexByte(cWhitespace, b) >= 0 }

// sscanfToken is one %s: skip leading whitespace, then take up to the next.
// An empty result means the conversion FAILED and sscanf stopped, which is what
// makes the surrounding `cmp eax,2` at 0x10228423 reject the line.
func sscanfToken(s string, i int) (string, int, bool) {
	for i < len(s) && isCSpace(s[i]) {
		i++
	}
	start := i
	for i < len(s) && !isCSpace(s[i]) {
		i++
	}
	if i == start {
		return "", i, false
	}
	return s[start:i], i, true
}

// SscanfKV is sscanf(line, "%s = %s", key, value), reporting ok only for
// exactly the 2 conversions 0x10228423 demands.
//
// The literal '=' in the format has to MATCH A REAL '=' in the input, and the
// two %s are whitespace-delimited, so a `key=value` line with no spaces is
// REJECTED OUTRIGHT by the real DLL: the first %s swallows "key=value" whole,
// the format then wants '=' and the input is exhausted, so sscanf returns 1.
// A naive split on "=" accepts it — a real divergence, Unicorn-confirmed.
func SscanfKV(line string) (string, string, bool) {
	key, i, ok := sscanfToken(line, 0)
	if !ok {
		return "", "", false
	}
	for i < len(line) && isCSpace(line[i]) {
		i++
	}
	if i >= len(line) || line[i] != '=' {
		return "", "", false
	}
	i++
	val, _, ok := sscanfToken(line, i)
	if !ok {
		return "", "", false
	}
	return key, val, true
}

// sscanfInt is %hd / %ld: an optional sign then a maximal digit run. Trailing
// junk is ignored ("4095abc" converts to 4095) and a token with no digits at
// all fails, leaving the destination field UNWRITTEN.
func sscanfInt(tok string, bits int) (int64, bool) {
	i := 0
	if i < len(tok) && (tok[i] == '+' || tok[i] == '-') {
		i++
	}
	d0 := i
	for i < len(tok) && tok[i] >= '0' && tok[i] <= '9' {
		i++
	}
	if i == d0 {
		return 0, false
	}
	v, err := strconv.ParseInt(tok[:i], 10, 64)
	if err != nil {
		return 0, false
	}
	if bits == 16 {
		return s16(v), true
	}
	return s32(v), true
}

// sscanfFloat is %f: sign, digits/point, optional exponent; narrowed to float32
// because the destination is a `float`, not a `double`.
func sscanfFloat(tok string) (float64, bool) {
	i := 0
	if i < len(tok) && (tok[i] == '+' || tok[i] == '-') {
		i++
	}
	d0 := i
	for i < len(tok) && ((tok[i] >= '0' && tok[i] <= '9') || tok[i] == '.') {
		i++
	}
	if i < len(tok) && (tok[i] == 'e' || tok[i] == 'E') {
		j := i + 1
		if j < len(tok) && (tok[j] == '+' || tok[j] == '-') {
			j++
		}
		k := j
		for k < len(tok) && tok[k] >= '0' && tok[k] <= '9' {
			k++
		}
		if k > j {
			i = k
		}
	}
	if i == d0 {
		return 0, false
	}
	v, err := strconv.ParseFloat(tok[:i], 64)
	if err != nil {
		return 0, false
	}
	return f32(v), true
}

// sscanfBool is the three bools, 0x102285b8..0x102285e0 and its two twins.
//
// NOT strcmp(value, "true"): the DLL does sscanf(value, "%c", &c) then
// `cmp byte, 0x74 ; sete` — a single lowercase 't' on the FIRST character. So
// "true", "t" and "tomato" are all TRUE while "True" and "TRUE" are FALSE.
func sscanfBool(tok string) (bool, bool) {
	if tok == "" {
		return false, false
	}
	return tok[0] == 't', true
}

// ParseDpiLine is 0x102283d5..0x10228965 — the parser's whole per-line body.
// A key whose conversion fails, or whose line is rejected, leaves the map
// untouched, exactly as the DLL leaves the params field unwritten.
//
// Step 1 (0x102283d5..0x102283fe) rejects the line outright if its FIRST
// character is '#', '*', CR, LF or NUL. Note this is a first-character test
// only: it is NOT "strip everything after a #". A leading-whitespace comment is
// therefore not caught here — it is caught one step later, by the 2-conversion
// requirement.
func ParseDpiLine(line string, values map[string]string) {
	if line == "" {
		return
	}
	switch line[0] {
	case '#', '*', '\r', '\n', 0:
		return
	}
	key, val, ok := SscanfKV(line)
	if !ok {
		return
	}
	if _, isScalar := dpiScalarKinds[key]; isScalar {
		values[key] = val
		return
	}
	// 0x102287e8..0x102287fd: anything unmatched is passed to
	// strstr(key, "TTC"); no match means the line is a silent no-op.
	if !strings.Contains(key, "TTC") {
		return
	}
	if isTtcKey(key) {
		values[key] = val
	}
}

var dpiScalarKinds = map[string]string{
	"maxValue": "i16", "lowFixedPoint": "i16", "highFixedPoint": "i16",
	"paperMin": "i16", "paperMax": "i16",
	"minSlope": "f32", "maxSlope": "f32",
	"binFactor": "i32", "bDoAverage": "bool",
	"lumWeighting": "f32", "edgeWeighting": "f32",
	"bIsBacklit": "bool", "bIsFlash": "bool",
	"flashFraction": "f32", "backlitFraction": "f32",
	"startingMinCumPoint": "f32", "cumPctBelowMin": "f32",
	"startingMaxCumPoint": "f32", "cumPctAboveMax": "f32",
}

func isTtcKey(k string) bool {
	switch k {
	case KeyLowNormalTTC, KeyHighNormalTTC, KeyLowBacklitTTC,
		KeyHighBacklitTTC, KeyLowFrontlitTTC, KeyHighFrontlitTTC:
		return true
	}
	return false
}

// DefaultDpiName is the shipped .dpi. Note this file carries no `key =` line,
// so the repo's key-indexed resolvers cannot find it — it is opened by path.
const DefaultDpiName = "ansel-dra-default-default.dpi"

// LoadParams parses draDir/dpiName and every .ttc it names, resolved against
// the .dpi's OWN directory (0x102288bf..0x1022894b).
//
// A key whose sscanf conversion fails leaves that field at its zero value here,
// where the DLL leaves the params object's own prior contents — the ctor
// defaults. That divergence is only reachable for a malformed .dpi; the shipped
// file sets every field, and ValidateParams would reject a zeroed maxValue
// loudly rather than silently.
func LoadParams(draDir, dpiName string) (Params, error) {
	var p Params
	p.Curves = map[string]Ttc{}
	if dpiName == "" {
		dpiName = DefaultDpiName
	}
	path := filepath.Join(draDir, dpiName)
	raw, err := os.ReadFile(path)
	if err != nil {
		return p, err
	}
	values := map[string]string{}
	// splitLines mirrors Python's str.splitlines() on the shipped files: the
	// parser is called once per line, in file order, so a repeated key wins
	// last — the DLL has no "already seen" guard.
	for _, line := range splitLines(string(raw)) {
		ParseDpiLine(line, values)
	}
	for key, tok := range values {
		if isTtcKey(key) {
			curve, err := ParseTtc(filepath.Join(draDir, tok))
			if err != nil {
				return p, err
			}
			p.Curves[key] = curve
			continue
		}
		switch dpiScalarKinds[key] {
		case "i16":
			if v, ok := sscanfInt(tok, 16); ok {
				p.setInt(key, v)
			}
		case "i32":
			if v, ok := sscanfInt(tok, 32); ok {
				p.setInt(key, v)
			}
		case "f32":
			if v, ok := sscanfFloat(tok); ok {
				p.setFloat(key, v)
			}
		case "bool":
			if v, ok := sscanfBool(tok); ok {
				p.setBool(key, v)
			}
		}
	}
	return p, nil
}

func splitLines(s string) []string {
	s = strings.ReplaceAll(s, "\r\n", "\n")
	s = strings.ReplaceAll(s, "\r", "\n")
	out := strings.Split(s, "\n")
	if n := len(out); n > 0 && out[n-1] == "" {
		out = out[:n-1]
	}
	return out
}

func (p *Params) setInt(key string, v int64) {
	switch key {
	case "maxValue":
		p.MaxValue = v
	case "lowFixedPoint":
		p.LowFixedPoint = v
	case "highFixedPoint":
		p.HighFixedPoint = v
	case "paperMin":
		p.PaperMin = v
	case "paperMax":
		p.PaperMax = v
	case "binFactor":
		p.BinFactor = v
	}
}

func (p *Params) setFloat(key string, v float64) {
	switch key {
	case "minSlope":
		p.MinSlope = v
	case "maxSlope":
		p.MaxSlope = v
	case "lumWeighting":
		p.LumWeighting = v
	case "edgeWeighting":
		p.EdgeWeighting = v
	case "flashFraction":
		p.FlashFraction = v
	case "backlitFraction":
		p.BacklitFraction = v
	case "startingMinCumPoint":
		p.StartingMinCumPoint = v
	case "cumPctBelowMin":
		p.CumPctBelowMin = v
	case "startingMaxCumPoint":
		p.StartingMaxCumPoint = v
	case "cumPctAboveMax":
		p.CumPctAboveMax = v
	}
}

func (p *Params) setBool(key string, v bool) {
	switch key {
	case "bDoAverage":
		p.BDoAverage = v
	case "bIsBacklit":
		p.BIsBacklit = v
	case "bIsFlash":
		p.BIsFlash = v
	}
}
