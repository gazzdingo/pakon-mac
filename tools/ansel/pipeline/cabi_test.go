package main

// The wire contract, pinned.
//
// The request crosses the dylib boundary as JSON produced by
// tools/pakon_colour_go.py:ColourRequest, and is decoded here into
// RenderRequest by field name, case-insensitively. That works today and would
// keep working silently-wrongly if either side renamed a field: the JSON would
// still parse, the field would just arrive as its zero value, and a rendered
// image gives no sign of it. docs/62 §0 is about exactly this class of
// unverified assumption, so it gets a test.
//
// The literal below is the output of
//
//	python3 -c "import sys; sys.path.insert(0,'tools'); import pakon_colour_go as g; \
//	  print(g.ColourRequest(...).wire().decode())"
//
// with every field set to a value distinguishable from its zero. If a field is
// renamed on either side, one of the assertions below fails by name.

import (
	"encoding/json"
	"testing"
)

const pythonWireSample = `{
 "abi": 1,
 "fx35Root": "/repo/vendor/ansel",
 "anselRoot": "/repo/vendor/ansel/anselinstalldir/dataPathItems",
 "request": {
  "model": "f135",
  "dxPart1": 96,
  "dxPart2": 1,
  "iso": 400,
  "filmPath": "ColNeg",
  "anselPath": "CN-Premium",
  "sourceType": 1,
  "sbaKeyOverride": "k",
  "coeffSource": "eeprom",
  "coeffPath": "/tmp/e.bin",
  "filmBase": [3001, 3002, 3003],
  "filmBaseFromFrame": false,
  "stageOrder": "shasta-fugc",
  "iccInput": "u12",
  "fugcMode": 1,
  "ccdDeskew": [8, 0, -8],
  "rotate180": true,
  "userOffsets": [1.5, -2.5, 3.5],
  "provenance": {"dx": "flag"}
 }
}`

func TestPythonWireFillsEveryField(t *testing.T) {
	var ar abiRequest
	if err := json.Unmarshal([]byte(pythonWireSample), &ar); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if ar.Abi != AbiVersion {
		t.Fatalf("abi %d, want %d", ar.Abi, AbiVersion)
	}
	if ar.AnselRoot == "" || ar.Fx35Root == "" {
		t.Fatalf("roots did not arrive: %+v", ar)
	}
	r := ar.Request
	if r == nil {
		t.Fatal(`the "request" object did not arrive`)
	}
	check := func(name string, got, want any) {
		t.Helper()
		if got != want {
			t.Errorf("%s = %v, want %v — the field name in "+
				"tools/pakon_colour_go.py no longer matches RenderRequest",
				name, got, want)
		}
	}
	check("model", r.Model, "f135")
	check("dxPart1", r.DXPart1, 96)
	check("dxPart2", r.DXPart2, 1)
	check("iso", r.ISO, 400)
	check("filmPath", r.FilmPath, "ColNeg")
	check("anselPath", r.AnselPath, "CN-Premium")
	check("sourceType", r.SourceType, 1)
	check("sbaKeyOverride", r.SbaKeyOverride, "k")
	check("coeffSource", r.CoeffSource, CoeffEeprom)
	check("coeffPath", r.CoeffPath, "/tmp/e.bin")
	check("filmBase", r.FilmBase, [3]int{3001, 3002, 3003})
	check("filmBaseFromFrame", r.FilmBaseFromFrame, false)
	check("stageOrder", r.StageOrder, OrderShastaFugc)
	check("iccInput", r.IccInput, IccU12)
	check("fugcMode", r.FugcMode, 1)
	check("ccdDeskew", r.CcdDeskew, [3]int{8, 0, -8})
	check("rotate180", r.Rotate180, true)
	check("userOffsets", r.UserOffsets, [3]float64{1.5, -2.5, 3.5})
	if r.Provenance["dx"] != "flag" {
		t.Errorf("provenance did not arrive: %v", r.Provenance)
	}
}

// A request that says nothing must be refused, not defaulted. This is the
// product rule from docs/62 §4.2 as a test: there is no fourth state.
func TestEmptyRequestIsRefusedNotDefaulted(t *testing.T) {
	var r RenderRequest
	if err := r.Validate(); err == nil {
		t.Fatal("an empty RenderRequest validated; it must refuse")
	}
	r = RenderRequest{Model: "f135", FilmPath: "ColNeg", AnselPath: "CN-Premium"}
	if err := r.Validate(); err == nil {
		t.Fatal("coeffSource unset validated; docs/62 §2.11 has no 'auto'")
	}
	r.CoeffSource = CoeffEeprom
	r.StageOrder = OrderShastaFugc
	r.IccInput = IccU12
	if err := r.Validate(); err == nil {
		t.Fatal("film base of 0,0,0 validated; 0 is FindDmin's sentinel")
	}
	r.FilmBase = [3]int{3000, 3000, 3000}
	if err := r.Validate(); err != nil {
		t.Fatalf("a fully-specified request was refused: %v", err)
	}
}

// POSITIVE must refuse by name rather than render slide film through the
// NegMatrix and then invert it (docs/62 §2.7).
func TestPositiveFilmPathRefuses(t *testing.T) {
	r := RenderRequest{
		Model: "f135", FilmPath: "POSITIVE", AnselPath: "CN-Premium",
		CoeffSource: CoeffEeprom, StageOrder: OrderShastaFugc,
		IccInput: IccU12, FilmBase: [3]int{3000, 3000, 3000},
	}
	err := r.Validate()
	if err == nil {
		t.Fatal("POSITIVE validated")
	}
	if len(err.Error()) < 80 {
		t.Errorf("the refusal has to be readable prose, got %q", err)
	}
}
