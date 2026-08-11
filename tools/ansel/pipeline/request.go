package main

// The render request, and the refusals.
//
// Everything the colour chain needs that cannot be recovered from the pixels
// arrives here as an explicit value with an explicit "unknown" encoding.
// There is no fourth state and no silent default: a field is a value, is
// explicitly unknown (legal only where the vendor's own selector has a
// wildcard cell), or the render is refused.
//
// This is the Go half of docs/62 §4. The Python side has carried these
// refusals since tools/pakon_decode.py's check_film_base / check_film_class;
// this pipeline clamped and carried on, which is how a black frame ships.

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
)

// StageOrder is the order the two tone stages run in after the balance apply.
// docs/62 §2.5: these do not commute — FUGC is a clamped 1-D translation of a
// nonlinear seed curve, Shasta is a per-channel affine stretch with clamps at
// both ends, so L∘A ≠ A∘L wherever either clamps.
type StageOrder string

const (
	// OrderFugcShasta is balance → FUGC → … → Shasta. THIS IS THE VENDOR'S
	// ORDER and it is established from the bytes, not inferred:
	//
	//   AnsImaBuilder::getImaTransformGroup (PakonIMAu.dll @ 0x100346a0)
	//   walks the parameter pack by index and connects each operand to the
	//   previous one (loop tail 0x1003a9d5…0x1003aa64; "input" bind at
	//   0x1003a9e3, ImaTransform::connect 0x1033fa00 at 0x1003aa33, "output"
	//   bind at 0x1003aac3). The render chain is therefore strictly linear in
	//   pack order — there is no reordering stage.
	//
	//   AnsCnPremiumPath::exportParameterPack (0x10050e20) emits, in order:
	//   noise, BalanceMethods_export (0x101142a0 — filmLut, scpLut, shift),
	//   exportFugc (0x100ff770), area, falloff, flare, SHASTA, ColorAdjust,
	//   sharpening, defects.
	//
	// So balance and FUGC are operands 2 and 3 and Shasta is operand 7. This
	// also closes docs/58 §16.5: balanceAreaImage's composed
	// filmLut∘scpLut∘shift∘fugc LUT is not analysis-only, it is the first
	// four links of the render chain cascaded into one table.
	OrderFugcShasta StageOrder = "fugc-shasta"
	// OrderShastaFugc is balance → Shasta → FUGC → ColorAdjust, which is what
	// tools/ansel/python-pipeline/pakon_ansel.py:render_scene does. It is
	// kept so the parity harness can compare the two engines as they are and
	// price the difference; it is not the vendor's order.
	OrderShastaFugc StageOrder = "shasta-fugc"
)

// IccInputDepth is the precision the RPD codes reach the ICC transform at.
// docs/62 §2.9: the RPD-side profile's mft2 input table has 4096 entries, so
// U12 reaches every knot; U8 reaches 256 of them. Python quantises to U8 only
// because PIL has no 16-bit RGB mode and ImageCms.applyTransform needs a PIL
// image — a library limitation that became a colour decision.
//
// SETTLED from the binary: the vendor does NOT quantise to 8 bit before the
// CMS. profile-Rpd2Srgb.dpi's `dataType = U8` is the OUTPUT description, as
// the file's own comment says — AnsImaProfileAggregate's constructor
// (PakonIMAu.dll @ 0x100938c0) compares it against "U8" at 0x10093bd6 and
// feeds the result to the ImaDataType factory (0x10311600, case 0 = unsigned
// char, case 1 = short) for the OUTPUT plane; there is no input datatype
// field in the DPI reader's string table at all (0x1059128c…0x105912e0).
// ImaICCXForm::apply (0x102f8420) selects the KODAKCMS SpEvaluate datatype at
// 0x102f85f4…0x102f8692: u8 planes take Sp type 1, 16-bit planes take Sp type
// 4 with an explicit 0..4095 mode gated on the caller's max value being
// exactly 4096.0 (constant at 0x105a17e0), otherwise Sp type 5.
//
// So U12 is the right default. What is NOT established is the scale: the only
// writer found for ImaICCEffectOp's source-max field (this+0x118) is its
// constructor at 0x1016e680, loading 32767.0 from 0x1058fac0, which would
// select Sp type 5 (full 16-bit) rather than the 4096 mode. A later setter
// was not ruled out. See docs/62 §12.4.
type IccInputDepth string

const (
	IccU8  IccInputDepth = "u8"
	IccU12 IccInputDepth = "u12"
)

// CoeffSource is which of the two stage-2 coefficient stores to read.
// docs/62 §2.11: "auto" is not a legal answer — the two sources differ by
// 14–57 RPD codes at (4000,4000,4000) and they answer different questions
// ("replay the vendor byte-for-byte" vs "render the best image").
type CoeffSource string

const (
	CoeffEeprom   CoeffSource = "eeprom"
	CoeffRegistry CoeffSource = "registry"
)

// filmClassByPath mirrors tools/pakon_color.py:FILM_CLASS_BY_PATH.
// 1, 4 and 8 all read the NegMatrix at TLB this+0x50, so 1 is the same
// arithmetic for ColNeg / BnW / IMPORTED. POSITIVE is filmClass 2, which
// reads the PosMatrix at this+0xc8 — a different matrix, not a worse one.
var filmClassByPath = map[string]int{
	"ColNeg":   1,
	"BnW":      1,
	"IMPORTED": 1,
	"POSITIVE": 2,
}

// F135ReversalPorted mirrors tools/pakon_decode.py:F135_REVERSAL_PORTED.
// The colour-reversal branch of fcn.1000d880 (filmClass 2) has no host chain
// behind it: everything after stage 2 here is written for a negative — the
// log inversion, the CN sba/shasta dpis, the FUGC density LUTs — and on this
// unit the shipped PosMatrix is an uncalibrated 0.25 diagonal with zero
// pedestals, so it is not usable evidence either.
const F135ReversalPorted = false

// RenderRequest is one frame's worth of everything that is not pixels.
type RenderRequest struct {
	Model string // "f135" | "f235"

	// Film selection. DXPart1/DXPart2 -1 and ISO 0 mean "explicitly
	// unknown", which is legal only because sba.map and fugc-rgb-lutMap.map
	// genuinely carry X cells for them. FilmPath has no wildcard because
	// CheckFilmClass needs it.
	DXPart1, DXPart2 int
	ISO              int
	FilmPath         string
	AnselPath        string
	SourceType       int
	SbaKeyOverride   string

	CoeffSource CoeffSource
	CoeffPath   string

	// FilmBase is the ROLL's film base in linear 12-bit codes — FindDmin over
	// the whole strip, not this frame. docs/62 §2.6: it is a property of the
	// stock, not of one frame, and measuring it per frame makes the same
	// negative render differently depending on which frames you happened to
	// export. 0 is FindDmin's "no valid Dmin" sentinel and is refused.
	FilmBase [3]int
	// FilmBaseFromFrame is the explicit, logged opt-out for offline analysis
	// of a single frame with no roll context. It is never correct for the
	// app.
	FilmBaseFromFrame bool
	// CcdAxis is which axis of the input grid indexes CCD pixels. FindDmin's
	// window is stated in CCD pixels, so without this there is nothing to
	// trim against and the window is not applied — see dmin.go. A -raw-in
	// blob is on the capture's own grid (CcdAxisX); a TIFF has already been
	// through pakon_decode.to_frame_image, which rot90s it (CcdAxisY).
	CcdAxis CcdAxis
	// CcdPixelOffset is the CCD pixel the capture's scan window started at —
	// pakon_scan's pixel_offset, out of the capture's own .scan.json. The
	// vendor's own start for DpiBase16_35 is 62 (docs/53 §3.4), so this is
	// what says how many leading columns of each line the vendor would never
	// have digitised. 0 means "unrecorded", and dmin.go assumes this port's
	// own 32.
	CcdPixelOffset int

	StageOrder StageOrder
	IccInput   IccInputDepth
	FugcMode   int // Cap +0x60e8: 2 → metrics/plane path, else setLutInfo
	CcdDeskew  [3]int
	Rotate180  bool

	// UserOffsets is the operator's correction, in RPD-12 codes, applied to
	// the toned image immediately before the ICC hop — the same point and the
	// same arithmetic as tools/pakon_render.py:apply_correction
	// (clip(toned + steps*code_values_per_button, 0, SHASTA_MAX)).
	//
	// The parameter *model* stays in Python and must: DEFAULT_PARAMS,
	// UNAVAILABLE_CONTROLS, the button semantics and code_values_per_button
	// are the product's statement about what it will and will not invent, and
	// docs/62 §9 keeps them next to the UI. What crosses here is only the
	// three numbers Python has already decided on, because the point in the
	// chain they apply at is inside this pipeline and nowhere else. Zero is a
	// legitimate value, not "unset" (docs/62 §4.3).
	UserOffsets [3]float64

	Provenance  map[string]string // where each field came from, for the log
	TapDir      string            // "" = no taps
	WriteBypass bool
}

// FilmClass resolves the stage-2 matrix dispatch for this request's film path.
func (r *RenderRequest) FilmClass() int {
	if c, ok := filmClassByPath[r.FilmPath]; ok {
		return c
	}
	return 1
}

// CheckFilmClass refuses a film path whose stage-2 branch is not ported, by
// name. Cite tools/pakon_decode.py:check_film_class.
//
// Rendering slide film through the NegMatrix is not a worse render, it is a
// different transform followed by a negative→positive inversion the frame
// never needed. Silently doing that is the defect; this is the refusal.
func (r *RenderRequest) CheckFilmClass() error {
	if r.FilmPath == "" {
		return fmt.Errorf(
			"no film path: pass -film-path ColNeg|BnW|IMPORTED|POSITIVE. " +
				"It selects fcn.1000d880's matrix (filmClass) and it has no " +
				"wildcard cell in any vendor selector, so there is nothing to " +
				"fall back to")
	}
	if _, ok := filmClassByPath[r.FilmPath]; !ok {
		return fmt.Errorf("-film-path %q is not one of ColNeg, BnW, IMPORTED, POSITIVE",
			r.FilmPath)
	}
	if r.Model != "f135" || r.FilmClass() != 2 {
		return nil
	}
	if !F135ReversalPorted {
		return fmt.Errorf(
			"-film-path POSITIVE selects filmClass 2 (colour reversal, " +
				"PosMatrix at TLB this+0xc8), and the F-135 reversal path is " +
				"not ported: the rest of this chain — the negative→positive " +
				"log, the CN sba/shasta dpis, the FUGC density LUTs — is " +
				"written for a negative, and this unit's PosMatrix is an " +
				"uncalibrated 0.25 diagonal. Use -film-path ColNeg for " +
				"negative film; there is no correct answer for slide yet")
	}
	return nil
}

// CheckFilmBase refuses a film base of 0 — FindDmin's sentinel, not a
// measurement. Cite tools/pakon_decode.py:check_film_base.
//
// find_dmin_code_from_hist walks the histogram down from the top and returns
// 0 when the top bin alone is already over threshold (0x100093f0…'s sete/and
// case): the data is clipped, so there is no clear-film code to find. Feeding
// that 0 into the inversion is not a degraded render, it is a fabricated one
// — base − c9 clamps to 1, log10 of it is 0, and every pixel comes out at
// fpo − 1000·log10(…), i.e. a black frame with no warning anywhere.
//
// clipPct, when non-nil, is the per-channel percentage of pixels already at
// the 4095 ceiling, which is the cause and is worth saying out loud.
// windowed says whether clipPct was measured over the FILM (dmin.go's
// DminWindow) or over every pixel. It changes what this refusal can honestly
// claim. Over the film area, a 0 means the film itself is clipped and the
// gain really is too high. Over everything, it may only mean the capture has
// a clear leader in it, or CCD columns below the vendor's window start —
// neither of which is an exposure fault, and telling the operator to lower
// the gain for either is how a good capture gets thrown away.
func CheckFilmBase(base [3]int, clipPct *[3]float64, windowed bool) error {
	var bad []int
	for i := 0; i < 3; i++ {
		if base[i] <= 0 {
			bad = append(bad, i)
		}
	}
	if len(bad) == 0 {
		return nil
	}
	detail := " The base was supplied by the caller, over the whole roll — " +
		"so this frame's own histogram says nothing about it."
	remedy := "Re-scan at a lower gain."
	if clipPct != nil && windowed {
		detail = fmt.Sprintf(" Inside the film area %.3f%% / %.3f%% / %.3f%% "+
			"of pixels are at the 4095 ceiling (FindDmin's threshold is "+
			"0.1%%) — the leader and the CCD columns below the vendor's "+
			"window start are already excluded, so this is the film.",
			clipPct[0], clipPct[1], clipPct[2])
	} else if clipPct != nil {
		detail = fmt.Sprintf(" Clipped at the 4095 ceiling: %.2f%% / %.2f%% / "+
			"%.2f%% of pixels (FindDmin's threshold is 0.1%%) — measured over "+
			"every pixel, so it also counts any clear leader and the CCD "+
			"columns below the vendor's window start, neither of which is "+
			"over-exposure.",
			clipPct[0], clipPct[1], clipPct[2])
		remedy = "Declare the input's CCD axis (-ccd-axis) so the film area " +
			"can be measured, before concluding anything about gain."
	}
	return fmt.Errorf(
		"F-135 invert: FindDmin found no film base (channel(s) %v came back "+
			"0, the 'no valid Dmin' sentinel; base = %v).%s Rendering anyway "+
			"would emit a black frame. %s",
		bad, base, detail, remedy)
}

// Validate runs every refusal that does not need pixels.
func (r *RenderRequest) Validate() error {
	if r.Model != "f135" && r.Model != "f235" {
		return fmt.Errorf("-model %q is not f135 or f235", r.Model)
	}
	if err := r.CheckFilmClass(); err != nil {
		return err
	}
	if r.AnselPath == "" {
		return fmt.Errorf("no ansel path: pass -ansel-path (CN-Premium, " +
			"CN-Fps, DC-Premium). sba.map / shasta.map / profile.map key on " +
			"it and it has no wildcard cell")
	}
	switch r.CoeffSource {
	case CoeffEeprom, CoeffRegistry:
	default:
		return fmt.Errorf(
			"-coeff-source must be eeprom or registry, not %q. There is no "+
				"'auto': docs/62 §2.11 — the EEPROM is the higher-precision "+
				"calibration store, the registry is what TLB actually read at "+
				"runtime after its %%f round-trip, and they differ by 14–57 "+
				"RPD codes at (4000,4000,4000). Which one is right depends on "+
				"whether you are replaying the vendor or rendering the best "+
				"image, and this will not choose for you",
			r.CoeffSource)
	}
	switch r.StageOrder {
	case OrderShastaFugc, OrderFugcShasta:
	default:
		return fmt.Errorf("-stage-order must be %q or %q, not %q",
			OrderShastaFugc, OrderFugcShasta, r.StageOrder)
	}
	switch r.IccInput {
	case IccU8, IccU12:
	default:
		return fmt.Errorf("-icc-input must be u8 or u12, not %q", r.IccInput)
	}
	if r.Model == "f135" {
		if r.FilmBaseFromFrame {
			// Explicit opt-out; the caller has said they know.
		} else if err := CheckFilmBase(r.FilmBase, nil, false); err != nil {
			return err
		}
	}
	return nil
}

// ParseTriple parses "a,b,c" into three ints.
func ParseTriple(s string) ([3]int, error) {
	var out [3]int
	parts := strings.Split(s, ",")
	if len(parts) != 3 {
		return out, fmt.Errorf("want three comma-separated integers, got %q", s)
	}
	for i, p := range parts {
		v, err := strconv.Atoi(strings.TrimSpace(p))
		if err != nil {
			return out, fmt.Errorf("%q is not an integer", p)
		}
		out[i] = v
	}
	return out, nil
}

// --- the capture sidecar -------------------------------------------------

// Sidecar is the subset of <capture>.scan.json this pipeline reads. The file
// is written by tools/pakon_scan.py:write_capture_metadata and read by
// tools/pakon_decode.py:load_capture_sidecar; the point of consuming it here
// rather than taking flags is that phase 2 has the app driving this, and the
// app must not be able to pass a film selection that disagrees with what the
// operator recorded at scan time.
type Sidecar struct {
	Speed    *float64 `json:"speed"`
	LineRate *float64 `json:"line_rate_0x91"`
	DpiBase  *int     `json:"dpi_base"`
	Film     *struct {
		FilmPath *string `json:"film_path"`
		DX       *string `json:"dx"`
		DXSource *string `json:"dx_source"`
	} `json:"film"`
}

// LoadSidecar reads a .scan.json. It never guesses: a field that is absent
// stays absent, and the caller decides whether that is fatal.
func LoadSidecar(path string) (*Sidecar, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var s Sidecar
	if err := json.Unmarshal(data, &s); err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	return &s, nil
}

// ApplySidecar fills DX / ISO-independent film fields the sidecar records,
// without overriding anything the caller stated explicitly. It records the
// provenance of every field it touches.
//
// It deliberately does NOT supply ISO: a DX-less roll has none, and the film
// stock table is Python's (research/film-products.json). ISO stays an
// explicit input.
func (r *RenderRequest) ApplySidecar(s *Sidecar, explicitDX, explicitFilmPath bool) error {
	if r.Provenance == nil {
		r.Provenance = map[string]string{}
	}
	if s.Film == nil {
		return nil
	}
	if !explicitFilmPath && s.Film.FilmPath != nil && *s.Film.FilmPath != "" {
		r.FilmPath = *s.Film.FilmPath
		r.Provenance["filmPath"] = "scan.json film.film_path"
	}
	if !explicitDX && s.Film.DX != nil && *s.Film.DX != "" {
		p1, p2, err := parseDXString(*s.Film.DX)
		if err != nil {
			return fmt.Errorf("scan.json film.dx: %w", err)
		}
		r.DXPart1, r.DXPart2 = p1, p2
		src := "unknown"
		if s.Film.DXSource != nil {
			src = *s.Film.DXSource
		}
		r.Provenance["dx"] = "scan.json film.dx (" + src + ")"
	}
	return nil
}

func parseDXString(s string) (int, int, error) {
	s = strings.TrimSpace(s)
	parts := strings.SplitN(s, "-", 2)
	p1, err := strconv.Atoi(strings.TrimSpace(parts[0]))
	if err != nil {
		return 0, 0, fmt.Errorf("%q: part 1 is not an integer", s)
	}
	p2 := -1
	if len(parts) == 2 {
		p2, err = strconv.Atoi(strings.TrimSpace(parts[1]))
		if err != nil {
			return 0, 0, fmt.Errorf("%q: part 2 is not an integer", s)
		}
	}
	return p1, p2, nil
}
