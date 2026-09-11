package anstonehelper

import (
	"os"
	"path/filepath"
	"testing"
)

// The real verification of this package is tools/test_tonehelper_port.py.
// These tests pin the tree file's documented gotcha and the walker's boundary
// rule, both of which a plausible-looking rewrite gets wrong.

func vendorDir(t *testing.T) string {
	t.Helper()
	d := filepath.Join("..", "..", "..", "..", "vendor", "ansel",
		"anselinstalldir", "dataPathItems", "toneHelper")
	if _, err := os.Stat(filepath.Join(d, DefaultDpi)); err != nil {
		t.Skipf("vendor toneHelper data not present: %v", err)
	}
	return d
}

func TestShippedParamsAndTree(t *testing.T) {
	p, err := LoadParams(vendorDir(t), "")
	if err != nil {
		t.Fatal(err)
	}
	if err := CheckParams(p); err != nil {
		t.Fatalf("shipped .dpi fails 0x101da6b0: %v", err)
	}
	if p.MaxValue != 4095 {
		t.Errorf("maxValue = %d, want 4095", p.MaxValue)
	}
	if p.DecisionTree != DefaultTree {
		t.Errorf("decisionTree = %q, want %q", p.DecisionTree, DefaultTree)
	}
	if err := VerifyDecisionTree(p.Nodes); err != nil {
		t.Fatalf("shipped tree fails 0x101da3b0: %v", err)
	}
	// AllOnTree1 carries a COMMENTED-OUT node 0 (LUM_STDDEV 285.044 1 12 2)
	// directly above the live one. A parser that honoured it would produce a
	// root threshold of 285.044 instead of 1.000, and every frame would walk
	// the other way.
	root := p.Nodes[0]
	if MetricNames[root.Metric] != "LUM_STDDEV" || root.Threshold != 1.0 {
		t.Errorf("root node is %s %v, want LUM_STDDEV 1.0 — the commented-out "+
			"node 0 leaked in", MetricNames[root.Metric], root.Threshold)
	}
}

func TestWalkerSendsEqualityToGreater(t *testing.T) {
	// 0x101dbada's `fcom; fnstsw; test ah,5; jp` takes [edx+0xc] (greater)
	// exactly when metric >= threshold. The file's "lessEqual" column name is
	// off by the boundary case and the assembly wins.
	nodes := []DecisionNode{
		{Metric: MetricID["LUM_STDDEV"], Threshold: 1.0, LessEqual: 1, Greater: 2},
		{Metric: MetricTerminal, LessEqual: -1, Greater: -1, Class: 1},
		{Metric: MetricTerminal, LessEqual: -1, Greater: -1, Class: 2},
	}
	metrics := map[int]float64{MetricID["LUM_STDDEV"]: 1.0} // exactly equal
	w, err := WalkDecisionTree(nodes, metrics)
	if err != nil {
		t.Fatal(err)
	}
	if w.TerminalNode != 2 {
		t.Errorf("equality landed on node %d, want 2 (the `greater` child)",
			w.TerminalNode)
	}
}

func TestWalkerClampsClassThree(t *testing.T) {
	// 0x101dbaff: class >= 3 publishes (toneHelperValue, sceneClass) = (2, 3),
	// so a class-4 terminal reports 3, not 4.
	nodes := []DecisionNode{{Metric: MetricTerminal, LessEqual: -1,
		Greater: -1, Class: 4}}
	w, err := WalkDecisionTree(nodes, map[int]float64{})
	if err != nil {
		t.Fatal(err)
	}
	if w.ToneValue != 2 || w.SceneClass != 3 {
		t.Errorf("class 4 -> (%d,%d), want (2,3)", w.ToneValue, w.SceneClass)
	}
	nodes[0].Class = 2
	w, _ = WalkDecisionTree(nodes, map[int]float64{})
	if w.ToneValue != 1 || w.SceneClass != 2 {
		t.Errorf("class 2 -> (%d,%d), want (1,2)", w.ToneValue, w.SceneClass)
	}
}

func TestVerifyRejectsBackwardGotos(t *testing.T) {
	// The strict `> index` half is load-bearing: it makes the tree a
	// forward-only DAG, which is what guarantees the walker terminates.
	nodes := []DecisionNode{
		{Metric: 2, Threshold: 1.0, LessEqual: 0, Greater: 1},
		{Metric: MetricTerminal, LessEqual: -1, Greater: -1},
	}
	if err := VerifyDecisionTree(nodes); err == nil {
		t.Error("a self-referential lessEqualGoto should be rejected")
	}
	if err := VerifyDecisionTree(nil); err == nil {
		t.Error("a NULL tree should be rejected")
	}
}

func TestMetricImplLayoutGap(t *testing.T) {
	// ids 2..15 are the LUM group, 16..30 the EDGE group. The 8-byte step
	// between id 15 (impl+0xe8) and id 16 (impl+0xf0) is the EDGE group's own
	// count int; MetricsByID must not fold the two groups into one run.
	lum := MetricGroup{WorkLow: 1, Kurtosis: 2}
	edge := MetricGroup{WorkLow: 3, Kurtosis: 4}
	m := MetricsByID(lum, edge, 5)
	if m[2] != 1 || m[15] != 2 || m[16] != 3 || m[29] != 4 || m[30] != 5 {
		t.Errorf("metric ids mis-mapped: %v %v %v %v %v",
			m[2], m[15], m[16], m[29], m[30])
	}
}

func TestCalcStatsSmallCount(t *testing.T) {
	// 0x10278ac7: count < 2 returns the raw first moment as `average` and
	// leaves every other output at 0.0f.
	h := &Histogram{NBins: 8, Bins: []int64{0, 0, 1, 0, 0, 0, 0, 0},
		MinValue: 0, MaxValue: 7}
	s, err := h.CalcStats(0, 0)
	if err != nil {
		t.Fatal(err)
	}
	if s.Count != 1 || s.Average != 2.0 || s.StdDev != 0 || s.Kurtosis != 0 {
		t.Errorf("count<2 gave %+v", s)
	}
}
