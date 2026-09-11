package anscontrast

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// THE VENDOR'S OWN TYPO, REPLICATED ON PURPOSE.
//
// csUpperIndex's parse key is spelled "csumpperixedindex" in the binary's
// string table. The literal sits at 0x1058a500 and 0x1012e576 matches it with
// `mov edi, 0x1058a500 / mov ecx, 0x12 / repe cmpsb` — 0x12 == 18 == the 17
// characters plus the NUL, so the comparison is the full misspelled token.
//
// Consequence: NO .dpi CAN EVER SET csUpperIndex. A file writing the correct
// `csUpperIndex = ...` falls through every key and is rejected; the field keeps
// its constructor default of 3999 forever. The shipped contrast-CNEnhanced.dpi
// does not try, so behaviour is unaffected — but a port that "fixed" the
// spelling would silently diverge from the real scanner on any hypothetical
// file that did. DO NOT CORRECT THIS.
const (
	DpiKeyCsUpperIndex          = "csumpperixedindex"
	DpiKeyCsUpperIndexStrVA     = 0x1058A500
	DpiKeyCsUpperIndexMatchVA   = 0x1012E576
	DpiKeyCsUpperIndexParamsOff = 0x17C
)

// modeNames are the five literals 0x1012dfbb onward matches against.
var modeNames = map[string]int{
	"NO_USER_INPUT":       ModeNoUserInput,
	"COMBINE_WITH_SLOPE":  ModeCombineWithSlope,
	"COMBINE_WITH_POINT":  ModeCombineWithPoint,
	"OVERRIDE_WITH_SLOPE": ModeOverrideWithSlope,
	"OVERRIDE_WITH_POINT": ModeOverrideWithPoint,
}

// The four slope arrays all converge on one shared 7-float sscanf
// (0x1058a5a8), which is why NSlopeBands is 7 and entries 7..15 keep whatever
// the constructor put there.
var dpiSlopeKeys = map[string]string{
	"alowerminslope": "aLowerMinSlope",
	"alowermaxslope": "aLowerMaxSlope",
	"aupperminslope": "aUpperMinSlope",
	"auppermaxslope": "aUpperMaxSlope",
}

// ParseDpi is AnsContrastAdjustParameterReader over one .dpi file's text.
//
// Runs at library INITIALISATION, not during analyzeAutoTone. It is here so the
// shipped vendor/ansel/anselinstalldir/dataPathItems/contrast/*.dpi files
// resolve to exactly the params the real reader would have produced, and so the
// csumpperixedindex typo is exercised rather than described.
func ParseDpi(text string, base *Params) (Params, error) {
	var p Params
	if base != nil {
		p = base.Copy()
	} else {
		p = DefaultParams()
	}
	basePoints := p.Points
	p.Points = nil
	seenPoints := false

	for _, raw := range strings.Split(text, "\n") {
		line := strings.TrimRight(raw, "\r")
		if i := strings.Index(line, "#"); i >= 0 {
			line = line[:i]
		}
		line = strings.TrimSpace(line)
		if !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		key := strings.ToLower(strings.TrimSpace(parts[0]))
		value := strings.TrimSpace(parts[1])

		switch {
		case key == "userinputmode":
			if m, ok := modeNames[value]; ok {
				p.UserInputMode = m
			} else { // 0x1012e0aa: sscanf("%d") fallback
				v, err := strconv.Atoi(value)
				if err != nil {
					return p, errf("userInputMode %q is neither a name nor an "+
						"integer", value)
				}
				p.UserInputMode = v
			}
		case key == "bconstrainslope":
			switch value {
			case "true": // 0x1012e2be
				p.BConstrainSlope = true
			case "false": // 0x1012e317
				p.BConstrainSlope = false
			default: // 0x1012e2e3: sscanf("%d")
				v, err := strconv.Atoi(value)
				if err != nil {
					return p, errf("bConstrainSlope %q is neither true/false "+
						"nor an integer", value)
				}
				p.BConstrainSlope = v != 0
			}
		case key == "midpoint":
			toks := strings.Fields(value)
			if len(toks) < 2 {
				return p, errf("midpoint needs two values, got %q", value)
			}
			a, err1 := strconv.ParseInt(toks[0], 10, 64)
			b, err2 := strconv.ParseInt(toks[1], 10, 64)
			if err1 != nil || err2 != nil {
				return p, errf("midpoint %q is not two integers", value)
			}
			p.MidpointIn, p.MidpointOut = i16(a), i16(b)
		case key == "points":
			seenPoints = true
			toks := strings.Fields(value)
			if len(toks) < 2 {
				return p, errf("points needs two values, got %q", value)
			}
			a, err1 := strconv.ParseInt(toks[0], 10, 64)
			b, err2 := strconv.ParseInt(toks[1], 10, 64)
			if err1 != nil || err2 != nil {
				return p, errf("points %q is not two integers", value)
			}
			p.Points = append(p.Points, Point{In: i16(a), Out: i16(b)})
		case dpiSlopeKeys[key] != "":
			toks := strings.Fields(value)
			if len(toks) > NSlopeBands {
				toks = toks[:NSlopeBands]
			}
			arr := p.slopeArrayRef(dpiSlopeKeys[key])
			for i, t := range toks {
				v, err := strconv.ParseFloat(t, 64)
				if err != nil {
					return p, errf("%s: %q is not a number", key, t)
				}
				arr[i] = f32(v)
			}
		default:
			if err := p.setScalar(key, value); err != nil {
				return p, err
			}
			// Anything unmatched — including a correctly spelled
			// "csupperindex" — falls through every key and is rejected. That is
			// the typo's whole practical effect; do not add a fallback here.
		}
	}
	if !seenPoints {
		p.Points = append([]Point(nil), basePoints...)
	}
	return p, nil
}

func (p *Params) slopeArrayRef(name string) *[SlopeArrayLen]float64 {
	switch name {
	case "aLowerMinSlope":
		return &p.ALowerMinSlope
	case "aLowerMaxSlope":
		return &p.ALowerMaxSlope
	case "aUpperMinSlope":
		return &p.AUpperMinSlope
	default:
		return &p.AUpperMaxSlope
	}
}

// setScalar handles the plain %hd / %d / %f keys, in the order scanOneLine
// tests them. Every key is compared lowercased.
func (p *Params) setScalar(key, value string) error {
	i16key := map[string]*int64{
		DpiKeyCsUpperIndex: &p.CsUpperIndex,
		"csfixedindex":     &p.CsFixedIndex,
		"cslowerindex":     &p.CsLowerIndex,
		"maxvalue":         &p.MaxValue,
	}
	i32key := map[string]*int64{
		"csnsamples":    &p.CsNSamples,
		"csgranularity": &p.CsGranularity,
		"lutsize":       &p.LutSize,
	}
	f32key := map[string]*float64{
		"allincr":          &p.AllIncr,
		"highincr":         &p.HighIncr,
		"lowincr":          &p.LowIncr,
		"highinitialslope": &p.HighInitialSlope,
		"lowinitialslope":  &p.LowInitialSlope,
	}
	if dst, ok := i16key[key]; ok {
		v, err := strconv.ParseInt(value, 10, 64)
		if err != nil {
			return errf("%s: %q is not an integer", key, value)
		}
		*dst = i16(v)
		return nil
	}
	if dst, ok := i32key[key]; ok {
		v, err := strconv.ParseInt(value, 10, 64)
		if err != nil {
			return errf("%s: %q is not an integer", key, value)
		}
		*dst = v
		return nil
	}
	if dst, ok := f32key[key]; ok {
		v, err := strconv.ParseFloat(value, 64)
		if err != nil {
			return errf("%s: %q is not a number", key, value)
		}
		*dst = f32(v)
		return nil
	}
	return nil
}

// DefaultDpiName is the .dpi CN-Enhanced selects.
const DefaultDpiName = "contrast-CNEnhanced.dpi"

// LoadParams reads contrastDir/dpiName and parses it over the ctor defaults.
func LoadParams(contrastDir, dpiName string) (Params, error) {
	if dpiName == "" {
		dpiName = DefaultDpiName
	}
	raw, err := os.ReadFile(filepath.Join(contrastDir, dpiName))
	if err != nil {
		return Params{}, err
	}
	return ParseDpi(string(raw), nil)
}
