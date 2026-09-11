// Package ansautotone assembles the four ported subsystems into
// ColorNegativePath::analyzeAutoTone's ANALYSIS half (PakonIMAu.dll
// 0x100fb730), producing the 4096-entry OutToneLut the citras apply driver
// consumes.
//
// It is the Go counterpart of pakon_ansel.real_auto_tone's own wiring, and it
// makes the same claim that function's docstring makes and no larger one:
// every subsystem it calls is separately verified against its Python reference
// (which is itself Unicorn-verified against the real DLL), and this file's only
// job is to hand each one's real output to the next exactly as the shell
// (pakon_autotone.analyze_auto_tone, itself Unicorn-verified) says to. It is
// NOT a claim that the ASSEMBLED chain has been proven bit-exact against the
// real DLL end to end. That is a separate, still-open verification on BOTH
// sides — see pakon_autotone_assembled_golden.py.
//
// THE THREADING, from the shell's own stages
// ==========================================
//
//	stage 1  cna       0x100fbdf8  -> LuminanceHist, EdgeHist, ToneScaleLut,
//	                                 bElmoOccured, elmoAggressiveness
//	stage 2  dra       0x100fc098  acquireWithHist(lumHist, edgeHist,
//	                                 tone=ToneScaleLut) -> DraLut, nSmallBins
//	stage 3  toneHelper 0x100fc312 acquireWithHist(lumHist, edgeHist, ctx,
//	                                 tone=DraLut) -> toneHelperValue
//	between  0x100fc5cd            x = bElmoOccured ? elmoAggressiveness
//	                                                : toneHelperValue, and
//	                               3 <= sceneType <= 6 resets sceneType to 0
//	stage 4  contrast  0x100fc5f3  acquire(sceneType, x, tone=DraLut)
//	                                 -> OutToneLut  <-- the chain's output
//	stage 5  ast       0x100fc79e  reads OutToneLut, never writes it back
//	stage 6  pfd       0x100fc901  enable byte forced 0 at 0x100f9da2
//	stage 7  citras    0x100fc9c3  reads OutToneLut, never writes it back
//	epilogue 0x100fcb29            sceneType == 1 zeroes the tone object
//
// WHAT IS DELIBERATELY ABSENT
// ===========================
// ast (stage 5) and citras-analyze (stage 7) are NOT ported to Go. Both READ
// the finished OutToneLut and neither writes it back — pakon_autotone.py's
// stage-5 note ("ast writes its float LUT into its own Impl... and nothing in
// analyzeAutoTone reads it back") and its stage-7 note (citras.analyze's result
// is likewise never assigned to ctx.tone_object). So their absence cannot
// change the curve this function returns. It DOES mean this is not the whole
// of analyzeAutoTone, and AutoToneAnalysisPorted stays false because of it:
// see tools/ansel/pipeline/autotone.go.
//
// pfd (stage 6) is off in the shipped capability set and is absent for that
// reason instead.
package ansautotone

import (
	"fmt"

	"pakonpipeline/anscna"
	"pakonpipeline/anscontrast"
	"pakonpipeline/ansdra"
	"pakonpipeline/anstonehelper"
)

// VAAnalyzeAutoTone is ColorNegativePath::analyzeAutoTone.
const VAAnalyzeAutoTone = 0x100FB730

// LightingNormal is the value every real colour negative takes:
// find("lighting") always MISSES for CN-Enhanced and a miss is DEFINED to yield
// 0 — Unicorn-verified in pakon_dra_golden.check_lighting.
const LightingNormal = ansdra.LightingNormal

// Params bundles the four subsystems' parameter blocks.
type Params struct {
	Cna        anscna.Params
	Dra        ansdra.Params
	ToneHelper anstonehelper.Params
	Contrast   anscontrast.Params
}

// LoadParams reads all four from the vendored dataPathItems tree. anselRoot is
// the directory holding cna/, dra/, toneHelper/ and contrast/.
//
// cna's params are the ctor defaults (0x100f8030), which Phase 1 proved match
// ansel-cna-default-default.dpi key for key; there is no cna .dpi parser here
// for the same reason pakon_cna.py has none.
func LoadParams(anselRoot string) (Params, error) {
	var p Params
	p.Cna = anscna.DefaultParams()
	var err error
	if p.Dra, err = ansdra.LoadParams(anselRoot+"/dra", ""); err != nil {
		return p, fmt.Errorf("dra params: %w", err)
	}
	if p.ToneHelper, err = anstonehelper.LoadParams(
		anselRoot+"/toneHelper", ""); err != nil {
		return p, fmt.Errorf("toneHelper params: %w", err)
	}
	if p.Contrast, err = anscontrast.LoadParams(
		anselRoot+"/contrast", ""); err != nil {
		return p, fmt.Errorf("contrast params: %w", err)
	}
	return p, nil
}

// Trace is every value that crosses a stage boundary, for a harness to diff.
// Nothing in the render path reads it.
type Trace struct {
	LumHist         []int64
	EdgeHist        []int64
	ToneScaleLut    []int64
	ElmoOccured     bool
	Elmo            anscna.ElmoResult
	DraLut          []int64
	LutSize         int64
	ToneHelperValue int
	SceneClass      int
	X               int64
	SceneType       int64
	OutToneLut      []int64
	Cna             *anscna.Analysis
	Dra             *ansdra.Results
	Contrast        *anscontrast.Results
}

// Analyze runs stages 1..4 of analyzeAutoTone over an interleaved int16 frame
// and returns the OutToneLut plus a trace.
//
// sceneType is ctx+0x44. 0 is AutoToneContext's own default and what
// pakon_ansel.real_auto_tone passes; a real per-frame scene classification is a
// separate, unported capability (docs/64), so nothing here invents one.
//
// exposure is &ctx[0x4bc] at the shell's th.acquireHist site; 0.0 with a
// non-NULL pointer is the shell's own default, for the same reason.
//
// A nil OutToneLut with a nil error means the epilogue zeroed the tone object
// (sceneType == 1, 0x100fcb29) — the caller decides what to do with a frame
// that has no tone curve, exactly as real_auto_tone does.
func Analyze(img anscna.Image, p Params, sceneType int64, exposure float64) (
	[]int64, *Trace, error) {
	tr := &Trace{SceneType: sceneType}

	// -- stage 1: cna, 0x100fbdf8 -----------------------------------------
	cnaRes, err := anscna.AnalyzeToResults(img, p.Cna)
	if err != nil {
		return nil, tr, fmt.Errorf("cna: %w", err)
	}
	tr.Cna = cnaRes.Analysis
	tr.LumHist = cnaRes.LuminanceHist
	tr.EdgeHist = cnaRes.EdgeHist
	tr.ToneScaleLut = cnaRes.ToneScaleLut
	tr.Elmo = cnaRes.Analysis.Elmo
	tr.ElmoOccured = cnaRes.BElmoOccured

	// -- stage 2: dra, 0x100fc098 -----------------------------------------
	// The shell threads the arrays by POINTER and dra reads only the first
	// maxValue+1 entries of each — cna's histSize (5000) and dra's
	// maxValue+1 (4096) are different numbers. Truncating is what the real
	// 0x1022b873 rep movsd does, not a convenience.
	nSmall := int(int16(p.Dra.MaxValue)) + 1
	fit := func(src []int64) []int64 {
		out := make([]int64, nSmall)
		copy(out, src)
		return out
	}
	draRes, err := ansdra.AnalyzeHist(p.Dra, fit(tr.LumHist), fit(tr.EdgeHist),
		fit(tr.ToneScaleLut), LightingNormal)
	if err != nil {
		return nil, tr, fmt.Errorf("dra: %w", err)
	}
	tr.Dra = draRes
	tr.DraLut = draRes.DraLut
	tr.LutSize = draRes.NSmallBins

	// -- stage 3: toneHelper, 0x100fc312 ----------------------------------
	nTh := int(p.ToneHelper.MaxValue) + 1
	fitTh := func(src []int64) []int64 {
		out := make([]int64, nTh)
		copy(out, src)
		return out
	}
	thRes, err := anstonehelper.AnalyzeWithHistograms(p.ToneHelper,
		fitTh(tr.LumHist), fitTh(tr.EdgeHist), fitTh(tr.DraLut), exposure, true)
	if err != nil {
		return nil, tr, fmt.Errorf("toneHelper: %w", err)
	}
	tr.ToneHelperValue = thRes.ToneHelperValue
	tr.SceneClass = thRes.SceneClass

	// -- between 3 and 4: 0x100fc5cd --------------------------------------
	if tr.ElmoOccured {
		tr.X = p.Cna.ElmoAggressiveness // 0x100fc5dd
		if sceneType >= 3 && sceneType <= 6 {
			sceneType = 0 // 0x100fc5e7
		}
	} else {
		tr.X = int64(tr.ToneHelperValue) // 0x100fc5f0
	}
	tr.SceneType = sceneType

	// -- stage 4: contrast, 0x100fc5f3 ------------------------------------
	nCx := int(p.Contrast.LutSize)
	fitCx := func(src []int64) []int64 {
		out := make([]int64, nCx)
		copy(out, src)
		return out
	}
	sub := anscontrast.NewSubsystem(p.Contrast,
		anscontrast.KeepIntermediatesDefault)
	if err := sub.Acquire(sceneType, tr.X, fitCx(tr.DraLut)); err != nil {
		return nil, tr, fmt.Errorf("contrast: %w", err)
	}
	tr.Contrast = sub.Results
	tr.LutSize = sub.Results.LutSize
	tr.OutToneLut = sub.Results.OutToneLut

	// -- stages 5..7 are absent by design; see the package comment. --------

	// -- epilogue, 0x100fcb29 ---------------------------------------------
	if sceneType == 1 {
		tr.OutToneLut = nil
		return nil, tr, nil
	}
	if len(tr.OutToneLut) == 0 {
		return nil, tr, fmt.Errorf("%#x: the tone object is non-null but "+
			"contrast produced no OutToneLut — the shell and contrast "+
			"disagree about whether a tone LUT was produced", VAAnalyzeAutoTone)
	}
	return tr.OutToneLut, tr, nil
}
