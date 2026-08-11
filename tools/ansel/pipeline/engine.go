package main

// The warm state, and the selection that produced it.
//
// Everything this pipeline loads from disk — the client LUT and matrix, the
// selected FUGC LUT, both ICC profiles, the 3-band LUT, the sba/shasta dpis
// and the stage-2 coefficients — is a function of the *selection* fields of a
// RenderRequest, not of the pixels. Loading them costs 10-30 ms; a slider drag
// is dozens of renders. So they are loaded once, keyed by the selection, and
// reused until the selection changes.
//
// This exists because the CLI's main() used to do the loading inline and then
// render exactly one frame. Phase 2 has the app calling this package through a
// c-shared dylib (see cabi.go) many times per second, so the loading had to
// come out of main(). The CLI now goes through the same Engine, which is the
// point: one arrangement of the stages, not two.
//
// docs/62 §3.3 and §4.3 — PakonColorOpen "returns the resolved selection ...
// so the app can show it". Resolution() is that.

import (
	"fmt"
	"path/filepath"
	"strconv"
	"strings"
)

// selectionKey is every request field that changes what gets loaded. Two
// requests with the same key can share one Engine; any difference and the
// tables must be re-read. It deliberately does NOT include FilmBase,
// StageOrder, IccInput, FugcMode, CcdDeskew or Rotate180 — those change the
// render, not the tables, so a slider bound to one of them does not evict.
type selectionKey struct {
	fx35, items      string
	model            string
	dxPart1, dxPart2 int
	iso              int
	filmPath         string
	anselPath        string
	sourceType       int
	coeffSource      CoeffSource
	coeffPath        string
}

func keyOf(fx35, items string, req *RenderRequest) selectionKey {
	return selectionKey{
		fx35: fx35, items: items,
		model:    req.Model,
		dxPart1:  req.DXPart1,
		dxPart2:  req.DXPart2,
		iso:      req.ISO,
		filmPath: req.FilmPath,

		anselPath:   req.AnselPath,
		sourceType:  req.SourceType,
		coeffSource: req.CoeffSource,
		coeffPath:   req.CoeffPath,
	}
}

// Engine holds the loaded vendor data for one film selection.
type Engine struct {
	Fx35Root  string
	AnselRoot string

	Sel     *FilmSelection
	Profile *ColorProfile
	Rpd2Pcs *IccMft2
	Srgb    *IccMft2
	Coeffs  []float32
	Band3   *ThreeBandLut

	// Paths, kept so Resolution() can say where every number came from
	// rather than making the operator guess.
	lutPath, matPath, fugcPath, sraPath string
	rpd2pcsPath, srgbPath, band3Path    string

	key selectionKey
}

// dxSpecOf renders the request's DX back into the "PART1[-PART2]" form
// SelectFilm parses. An unspecified part 1 stays empty, which SelectFilm
// resolves through the vendor's own wildcard map rows and MARKS as defaulted
// rather than refusing — see maps.go:SelectFilm for why the refusal that used
// to live there was the wrong half of the fix.
func dxSpecOf(req *RenderRequest) string {
	if req.DXPart1 < 0 {
		return ""
	}
	s := strconv.Itoa(req.DXPart1)
	if req.DXPart2 >= 0 {
		s += "-" + strconv.Itoa(req.DXPart2)
	}
	return s
}

// OpenEngine runs the vendor's selections and loads everything they name.
//
// It returns errors rather than exiting: the CLI turns them into a fatal, the
// dylib turns them into a structured refusal the UI can print. Nothing in here
// may write to stdout — see cabi.go.
func OpenEngine(fx35, items string, req *RenderRequest) (*Engine, error) {
	colorCorrection := filepath.Join(fx35, "Config", "ColorCorrection")
	e := &Engine{
		Fx35Root:    fx35,
		AnselRoot:   items,
		lutPath:     filepath.Join(colorCorrection, "_ClientColNegLut.txt"),
		matPath:     filepath.Join(colorCorrection, "_ClientColNegMat.txt"),
		sraPath:     filepath.Join(items, "common", "common-sraFwdLut-metric-rom12.lut"),
		rpd2pcsPath: filepath.Join(items, "profile", "Rpd2Pcs_HR200_QS_v5s10.pf"),
		srgbPath:    filepath.Join(items, "profile", "Srgb_v2.pf"),
		band3Path:   filepath.Join(items, "common", "luts6_postROMM_equalRGBshort.lut"),
		key:         keyOf(fx35, items, req),
	}

	sel, err := SelectFilm(items, dxSpecOf(req), req.ISO, req.AnselPath, req.SourceType)
	if err != nil {
		return nil, fmt.Errorf("film selection: %w", err)
	}
	e.Sel = sel
	e.fugcPath = filepath.Join(items, "fugc", sel.FugcLut)

	if e.Profile, err = LoadProfile(e.lutPath, e.matPath, e.fugcPath, e.sraPath); err != nil {
		return nil, fmt.Errorf("base profile: %w", err)
	}
	if req.Model == "f135" {
		if e.Coeffs, err = LoadMatrixCoeffsFrom(req.CoeffSource, req.CoeffPath, req.FilmClass()); err != nil {
			return nil, fmt.Errorf("f135 coefficients: %w", err)
		}
	}
	if e.Rpd2Pcs, err = LoadICCProfile(e.rpd2pcsPath); err != nil {
		return nil, fmt.Errorf("Rpd2Pcs profile: %w", err)
	}
	if e.Srgb, err = LoadICCProfileB2A0(e.srgbPath); err != nil {
		return nil, fmt.Errorf("sRGB profile: %w", err)
	}
	if e.Band3, err = Load3BandLutAscii(e.band3Path); err != nil {
		return nil, fmt.Errorf("3-band LUT: %w", err)
	}
	return e, nil
}

// Matches reports whether this Engine's tables are the ones req asks for.
func (e *Engine) Matches(fx35, items string, req *RenderRequest) bool {
	return e.key == keyOf(fx35, items, req)
}

// Resolution is what the selections resolved to, as flat strings, so the app
// can show the operator which stock's tables their frame went through instead
// of asking them to trust it. docs/62 §4.3.
func (e *Engine) Resolution() map[string]string {
	r := map[string]string{
		"anselRoot":    e.AnselRoot,
		"fx35Root":     e.Fx35Root,
		"clientLut":    e.lutPath,
		"clientMatrix": e.matPath,
		"sraFwdLut":    e.sraPath,
		"iccRpd2Pcs":   e.rpd2pcsPath,
		"iccSrgb":      e.srgbPath,
		"band3Lut":     e.band3Path,
	}
	if e.Sel != nil {
		s := e.Sel
		r["dx"] = s.DXLabel()
		r["iso"] = s.ISOLabel()
		r["sbaKey"] = s.Sba.Key
		r["sbaFile"] = s.Sba.File
		r["shastaKey"] = s.Shasta.Key
		r["shastaFile"] = s.Shasta.File
		r["fugcMode"] = s.FugcMode
		r["fugcMapFile"] = s.FugcMapFile
		r["fugcLut"] = s.FugcLut
		r["fugcContrast"] = fmt.Sprintf("%.2f", s.Contrast)
		r["fugcATableDmin"] = fmt.Sprintf("%v", s.FugcDmin)
		r["fugcAFilmAimDmin"] = fmt.Sprintf("%v", s.FugcAim)
		// Which vendor rule chose each file, and whether anything was known
		// about the stock when it did. Without these the app can say WHICH
		// tables a frame went through but not whether the operator picked
		// them — and those are exactly the two facts that were confused when
		// a defaulted stock last reached a photograph unannounced.
		r["sbaRule"] = s.SbaRule
		r["shastaRule"] = s.ShastaRule
		r["fugcRule"] = s.FugcRule
		r["dxDefaulted"] = strconv.FormatBool(s.DXDefaulted)
		r["isoDefaulted"] = strconv.FormatBool(s.ISODefaulted)
		if note := s.DefaultNote(); note != "" {
			r["filmDefaultNote"] = note
		}
	}
	r["coeffSource"] = string(e.key.coeffSource)
	r["coeffPath"] = e.key.coeffPath
	return r
}

// ResolutionLines is Resolution() as the same prose FilmSelection.Print writes
// to stderr, for a log line rather than a UI.
func (e *Engine) ResolutionLines() string {
	var b strings.Builder
	for _, k := range []string{"dx", "iso", "dxDefaulted", "sbaKey", "shastaKey",
		"fugcMapFile", "fugcLut", "fugcContrast", "coeffSource"} {
		if v, ok := e.Resolution()[k]; ok {
			fmt.Fprintf(&b, "%s=%s ", k, v)
		}
	}
	return strings.TrimSpace(b.String())
}
