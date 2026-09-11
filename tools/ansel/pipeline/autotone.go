package main

import (
	"fmt"
	"os"

	"pakonpipeline/anscna"
	"pakonpipeline/ansautotone"
	"pakonpipeline/citrasdriver"
	"pakonpipeline/vendorinvert"
)

// vendorInvertEnabled mirrors the Python engine's PAKON_VENDOR_INVERT=1.
//
// docs/74 §170-§175: the F-135 inverts BEFORE stage 2, with a fixed 16,384-
// entry table — no film base, no Dmin, no pedestal (c9), no fpo. This engine's
// own inversion has all four and runs AFTER the polynomial. Using the vendor's
// table in the vendor's position takes the six-frame comparison from
// 59.14 MAE / +58.90 bias to 23.59 / -3.18.
//
// Off by default on both engines: it re-architects the front of the chain, and
// §170.4 states plainly that it rests on one roll and one capture.
var vendorInvertEnabled = os.Getenv("PAKON_VENDOR_INVERT") == "1"

// vendorInvertRaw maps a raw CCD code through the vendor's inversion table.
//
// The index is the FULL raw code clamped to the table, NOT `code >> 2`.
// docs/74 §173.1/§174: the >>2 was inferred from a dump having 4096 entries —
// "so the index must be 12-bit" — and is wrong. lut_src's real range is
// 404..11681, the loop indexes with the full 16-bit value, and the 4096 was
// the dump's size rather than the table's. With the shift in place the index
// could never exceed 4095 however large the table, which is what made §172's
// clipping caveat look intrinsic when it was an artefact of that one line.
func vendorInvertRaw(code int) int {
	if code < 0 {
		code = 0
	}
	if code >= vendorinvert.Entries {
		code = vendorinvert.Entries - 1
	}
	return int(vendorinvert.Table[code])
}

// applyVendorInvertRGB inverts a whole pixel. It exists so the per-channel
// mapping has ONE call site that a test can reach: a transposition here
// (inverting G with R's value, say) produces a plausible image and no error,
// and a mutation test proved the wiring was not covered until this existed.
func applyVendorInvertRGB(r, g, b int) (int, int, int) {
	return vendorInvertRaw(r), vendorInvertRaw(g), vendorInvertRaw(b)
}

// inversionMode is the SINGLE source of truth for which inversion a render
// runs. Pass 1 acts on "vendor", pass 2 acts on "legacy", and because both
// read this one function they cannot both fire — inverting twice is
// unrepresentable rather than merely tested for.
//
// That distinction is not academic: a double inversion yields a plausible
// picture and raises nothing, and a deliberate-mutation test showed the
// earlier two-independent-conditions form did not catch it. Same fix as
// quantiseFrameRPD12 above.
//
//	"vendor" — PAKON_VENDOR_INVERT=1: the vendor's table, before the
//	           polynomial, no film base / Dmin / c9 / fpo (docs/74 §170-§175)
//	"legacy" — this port's own fpo + 1000*(baseLog - log(p - c9)), after the
//	           polynomial, against the FRAME's dmin (§182.3)
//	"none"   — not an F-135 render
func inversionMode(model string, vendorInvert bool) string {
	if model != "f135" {
		return "none"
	}
	if vendorInvert {
		return "vendor"
	}
	return "legacy"
}

// applyLegacyInversion runs this port's own negative->positive step, IN PLACE,
// and only when invMode says to.
//
// The mode check lives INSIDE the function on purpose. With it at the call
// site in processImage, a deliberate mutation that let pass 2 run alongside the
// vendor inversion — doubly inverting every frame, producing a plausible image
// and raising nothing — was NOT CAUGHT by any test, because no test could
// reach that call site. Moving the decision here makes it reachable:
// applyLegacyInversion("vendor", ...) must leave the frame untouched, and that
// is now asserted.
//
// docs/74 §182.3: this is also where Go and Python diverge upstream of tone —
// this uses the FRAME's dmin (via baseLog) where Python uses the ROLL's. That
// divergence is unrelated to the vendor path and survives it.
func applyLegacyInversion(
	invMode string,
	rpd12 [][][3]float64,
	fpo [3]int,
	baseLog [3]float64,
	c9 [3]float64,
	logTerm func(v, c9 float64) float64,
	clamp4k func(v int) int,
) {
	if invMode != "legacy" {
		return
	}
	for y := range rpd12 {
		for x := range rpd12[y] {
			p := rpd12[y][x]
			for ch := 0; ch < 3; ch++ {
				v := float64(fpo[ch]) + 1000*(baseLog[ch]-logTerm(p[ch], c9[ch]))
				p[ch] = float64(clamp4k(int(v)))
			}
			rpd12[y][x] = p
		}
	}
}

// quantiseFrameRPD12 turns a post-FUGC RPD-12 frame into the interleaved
// int16 buffer both halves of the tone stage consume.
//
// THERE IS EXACTLY ONE OF THESE ON PURPOSE. The analysis half
// (computeGoToneLut, via anscna.Image) and the apply half (applyVendorTone,
// via citrasdriver.ImageI16) must see a byte-identical image; if they ever
// diverged, the chain would measure one image and transform another, and the
// result would be a plausible picture with no error raised — the worst
// failure mode this pipeline has.
//
// A test asserting the two agree cannot establish that, because a test can
// only compare whatever the two call sites do today. Sharing one function
// makes the divergence unrepresentable instead. The quantiser itself is
// citrasdriver.QuantiseRPD12 — real_auto_tone's own np.rint, round-half-to-
// even, which is load-bearing rather than pedantic (see that function).
func quantiseFrameRPD12(rpd12 [][][3]float64) []int16 {
	height := len(rpd12)
	if height == 0 {
		return nil
	}
	width := len(rpd12[0])
	px := make([]int16, width*height*3)
	for y := 0; y < height; y++ {
		row := rpd12[y]
		for x := 0; x < width; x++ {
			base := (y*width + x) * 3
			for c := 0; c < 3; c++ {
				px[base+c] = citrasdriver.QuantiseRPD12(row[x][c])
			}
		}
	}
	return px
}

// goAutoTone is Phase 6.2's opt-in switch: compute the OutToneLut in Go, with
// the ported analysis chain, instead of falling back to the ShastaToneRpd
// stand-in when no caller supplies one.
//
// OFF by default, deliberately, following PAKON_VENDOR_INVERT's precedent —
// this changes what the product render path computes, and that is the owner's
// call to make, not a side effect of the port becoming available.
var goAutoTone = os.Getenv("PAKON_GO_AUTOTONE") == "1"

// computeGoToneLut runs the ported analysis chain over the post-FUGC RPD-12
// frame and returns analyzeAutoTone's composed OutToneLut.
//
// EVIDENCE THIS IS SOUND (docs/74 §191, §192):
//
//   - Go chain == Python chain, bit for bit over 27,294 samples on a real
//     frame, OutToneLut included (tools/test_autotone_chain.py).
//   - Python assembled chain == the real DLL, all seven scenarios, calling
//     0x100fb730 once with NO subsystem entry points hooked
//     (pakon_autotone_assembled_golden.py).
//
// Those compose: Go chain == real DLL by transitivity. Neither leg is a
// per-subsystem claim standing in for an end-to-end one.
//
// ast (0x100fc79e) and citras-analyze (0x100fc9c3) are absent from the Go
// chain. Both only READ the finished OutToneLut and neither writes it back
// (pakon_autotone's stage-5 and stage-7 notes), so the curve is unaffected.
//
// THE INPUT is the same post-FUGC RPD-12 frame applyVendorTone consumes,
// quantised by the same citrasdriver.QuantiseRPD12 — which is real_auto_tone's
// own np.rint, round-half-to-even. Using a different rounding here would put
// the analysis and the apply on different images.
//
// sceneType 0 and exposure 0.0 are the shell's OWN documented defaults, the
// same ones pakon_ansel.real_auto_tone uses: a real per-frame scene-type
// classification is a separate unported capability (docs/64), so 0 is not a
// value invented here.
//
// A nil LUT with a nil error is not an error: sceneType 1's epilogue
// (0x100fcb29) legitimately zeroes the tone object, and the caller decides
// what a frame with no curve means — exactly as real_auto_tone does.
func computeGoToneLut(rpd12 [][][3]float64, anselRoot string) ([]int32, error) {
	height := len(rpd12)
	if height == 0 {
		return nil, nil
	}
	width := len(rpd12[0])

	img := anscna.Image{
		Width: width, Height: height,
		Pixels: quantiseFrameRPD12(rpd12),
	}

	params, err := ansautotone.LoadParams(anselRoot)
	if err != nil {
		return nil, fmt.Errorf("autotone params: %w", err)
	}

	lut64, _, err := ansautotone.Analyze(img, params, 0, 0.0)
	if err != nil {
		return nil, fmt.Errorf("autotone analyze: %w", err)
	}
	if lut64 == nil {
		return nil, nil // sceneType epilogue zeroed the tone object
	}
	if len(lut64) != ToneLutSize {
		return nil, fmt.Errorf(
			"autotone returned %d entries, want %d", len(lut64), ToneLutSize)
	}

	lut := make([]int32, len(lut64))
	for i, v := range lut64 {
		lut[i] = int32(v)
	}
	return lut, nil
}

// AutoToneApplyPorted records that the APPLY half of
// ColorNegativePath::analyzeAutoTone — ImaCitrasOpBase::virtual_40
// (PakonIMAu.dll 0x10169350) — is ported, in package citrasdriver, and is
// verified bit-exact against tools/ansel/python-pipeline/pakon_citras_driver.py
// on a real frame by tools/test_citras_driver_ports.py: all twelve intermediate
// stages plus the final image, zero differing samples, with four deliberate
// transcription mutations each caught.
//
// That Python module's leaf routines are themselves Unicorn-verified against
// the real DLL (pakon_citras_driver_golden.py), so this is bit-exactness
// against the vendor by transitivity — with ONE stated exception, gauss_blur,
// where the DLL accumulates in 80-bit x87 and both ports use float64. See the
// citrasdriver package comment. This flag is about the APPLY half only.
const AutoToneApplyPorted = true

// AutoToneAnalysisPorted records that the ANALYSIS half is NOT ported: cna →
// dra → toneHelper → contrast → ast → citras-analyze, the six subsystems that
// measure the frame and build the 4096-entry OutToneLut the driver applies.
//
// FOUR OF THE SIX ARE NOW IN GO, and the four that are include the one that
// produces the output:
//
//	anscna         AnsCnaCapabilityImpl::analyze          0x1022ea50
//	ansdra         AnsDraCapabilityImpl::analyze (hist)   0x1022b530
//	anstonehelper  AnsToneHelperCapabilityImpl (hist)     0x101dd1b0
//	anscontrast    AnsContrastAdjustCapabilityImpl        0x101d8240
//	ansautotone    the shell's own threading of the four  0x100fb730
//
// Each is verified bit-exact against its Python reference on a real frame by
// tools/test_cna_port.py, test_dra_port.py, test_tonehelper_port.py and
// test_contrast_port.py, and the assembled chain by test_autotone_chain.py —
// whose OutToneLut is diffed both against the harness's own wiring AND against
// the LUT the production pakon_ansel.real_auto_tone actually hands the citras
// driver. Those Python modules are each separately Unicorn-verified against the
// real DLL, so that is bit-exactness against the vendor by transitivity,
// subsystem by subsystem.
//
// THIS FLAG STAYS FALSE, but for ONE reason now, not two. Reason 2 below was
// true when written and is no longer true; it is kept, struck through, because
// a flag that stays False for a stale reason is exactly the drift docs/74 §188
// exists to catch, and this file was one of its instances.
//
//  1. ast (0x100fc79e) and citras-analyze (0x100fc9c3) are not ported. Both
//     READ the finished OutToneLut and neither writes it back — pakon_autotone's
//     stage-5 and stage-7 notes — so their absence cannot change the curve. But
//     they are two of the six, and this flag names six.
//
//  2. WITHDRAWN 2026-08-21. The claim was: "the ASSEMBLED chain has never been
//     diffed against the real DLL end to end, on EITHER side ...
//     pakon_autotone_assembled_golden.py is where that verification lives and
//     it is still open." That verification is CLOSED on the Python side.
//     pakon_autotone_assembled_golden.py runs today and passes all seven
//     scenarios — flat, gradient, high-contrast bands, two pseudo-random
//     images at realistic pixel counts, and two scene_type variants — calling
//     the real 0x100fb730 ONCE with NO subsystem entry points hooked, the real
//     Cap wrappers falling through into the real cna/dra/toneHelper/contrast/
//     ast/citras Impl bodies, every AUTOTONE_WORK_LAYOUT scalar and every
//     subsystem result object and LUT/histogram compared dword for dword.
//     pakon_autotone.py's own Phase 6.1 block records it, including the
//     integration-class bug it caught that no leaf test could: a flat image
//     makes cna's real EdgeHist all-zero, and toneHelper then divides by that
//     histogram's total — the DLL does not trap (FPCW 0x027f masks the x87
//     zero-divide) and the port did.
//
//     The Python-side subsystems raise rather than substitute (see
//     pakon_autotone.py's AutoToneSubsystems: "Every method is gated on its
//     *_PORTED flag and raises"), so that pass is proof the real chain ran,
//     not proof a stub was quiet.
//
// What genuinely remains is Phase 6.2 — swapping the render path — which
// pakon_autotone.py calls "a later, separate, more consequential step". See
// the note at applyVendorTone's call site in main.go.
//
// Nothing silently substitutes for the chain. A render either receives a real
// OutToneLut from the caller (RenderRequest.OutToneLut, which the Python side
// fills from pakon_ansel.real_auto_tone) and applies it through the vendor's
// own driver, or it does not and runs the openly-labelled ShastaToneRpd
// stand-in. The provenance banner names which of the two ran. Package
// ansautotone is NOT wired into the render path; calling it from there is a
// separate, deliberate decision.
const AutoToneAnalysisPorted = false

// applyVendorTone runs the vendor's real apply driver over the post-FUGC
// RPD-12 frame. The entry quantisation is citrasdriver.QuantiseRPD12, which is
// real_auto_tone's own np.rint (round-half-to-even) — see that function for why
// the distinction is load-bearing rather than pedantic.
func applyVendorTone(rpd12 [][][3]float64, lut []int32) ([][][3]float64, error) {
	height := len(rpd12)
	if height == 0 {
		return rpd12, nil
	}
	width := len(rpd12[0])

	// Same buffer builder the analysis half uses — see quantiseFrameRPD12 for
	// why this is one shared function rather than two matching loops.
	img := citrasdriver.ImageI16{H: height, W: width, Px: quantiseFrameRPD12(rpd12)}

	tone := make([]int64, len(lut))
	for i, v := range lut {
		tone[i] = int64(v)
	}

	toned, err := citrasdriver.Apply(img, tone, citrasdriver.DefaultParams())
	if err != nil {
		return nil, err
	}

	out := make([][][3]float64, height)
	for y := 0; y < height; y++ {
		row := make([][3]float64, width)
		for x := 0; x < width; x++ {
			base := (y*width + x) * 3
			row[x] = [3]float64{
				float64(toned.Px[base]),
				float64(toned.Px[base+1]),
				float64(toned.Px[base+2]),
			}
		}
		out[y] = row
	}
	return out, nil
}
