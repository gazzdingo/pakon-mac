package anstonehelper

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// DefaultDpi and DefaultTree are what toneHelper.map selects for CN-Enhanced.
const (
	DefaultDpi  = "toneHelper-default.dpi"
	DefaultTree = "AllOnTree1"
)

// ParamsBase and ParamsSize: AnsToneHelperParams lives at impl+0x0c and ends
// exactly where AnsToneHelperResults begins.
const (
	ParamsBase = 0x0C
	ParamsSize = 0x74
)

// Params is AnsToneHelperParams — the fields this port actually consumes.
type Params struct {
	MaxValue                 int64
	ThresholdMultiplier      float64
	ThresholdReductionFactor float64
	MinEdgeThreshold         int64
	MinEdgeRatio             float64
	SmoothingSizeFactor      float64
	SmoothingSigma           float64
	LowToneRange             [2]int64
	MidLowToneRange          [2]int64
	MidHighToneRange         [2]int64
	HighToneRange            [2]int64
	// DecisionTree is the tree the ported entry point walks.
	DecisionTree string
	// DecisionTreeDei is loaded by the DPI and walked by a DIFFERENT caller
	// (ColorNegativePath::CalcDei). Recorded so the parser is faithful to the
	// file; NEVER read by anything in this package. Do not wire it in.
	DecisionTreeDei string
	// Nodes is the parsed DecisionTree, i.e. params+0x70/+0x78.
	Nodes []DecisionNode
}

// DefaultParams mirrors pakon_toneHelper.ToneHelperParams' own dataclass
// defaults. The harness loads the real .dpi on both sides rather than relying
// on these.
func DefaultParams() Params {
	return Params{
		MaxValue: 4095, ThresholdMultiplier: 1.5,
		ThresholdReductionFactor: f32(0.949), MinEdgeThreshold: 4,
		MinEdgeRatio: f32(0.1), SmoothingSizeFactor: 4.0, SmoothingSigma: 10.0,
		LowToneRange: [2]int64{600, 1149}, MidLowToneRange: [2]int64{1150, 1549},
		MidHighToneRange: [2]int64{1550, 1849},
		HighToneRange:    [2]int64{1850, 2449},
		DecisionTree:     DefaultTree, DecisionTreeDei: "deiTree1",
	}
}

// ParseDpiRaw is AnsToneHelperDpi::readAscii's tokenising: `key = value` lines,
// `#` comments.
func ParseDpiRaw(text string) map[string]string {
	out := map[string]string{}
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimRight(line, "\r")
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
	return out
}

// ParseDpi turns a toneHelper-*.dpi's text into Params. The key/version header
// lines are metadata and are not consumed here.
func ParseDpi(text string) (Params, error) {
	raw := ParseDpiRaw(text)
	p := DefaultParams()
	geti := func(key string, n int) ([]int64, bool, error) {
		v, ok := raw[key]
		if !ok {
			return nil, false, nil
		}
		toks := strings.Fields(v)
		if len(toks) < n {
			return nil, false, errf("toneHelper .dpi key %q needs %d values, "+
				"got %d", key, n, len(toks))
		}
		out := make([]int64, n)
		for i := 0; i < n; i++ {
			iv, err := strconv.ParseInt(toks[i], 10, 64)
			if err != nil {
				return nil, false, errf("toneHelper .dpi key %q: %q is not an "+
					"integer", key, toks[i])
			}
			out[i] = iv
		}
		return out, true, nil
	}
	getf := func(key string) (float64, bool, error) {
		v, ok := raw[key]
		if !ok {
			return 0, false, nil
		}
		toks := strings.Fields(v)
		if len(toks) == 0 {
			return 0, false, errf("toneHelper .dpi key %q is empty", key)
		}
		fv, err := strconv.ParseFloat(toks[0], 64)
		if err != nil {
			return 0, false, errf("toneHelper .dpi key %q: %q is not a number",
				key, toks[0])
		}
		return f32(fv), true, nil
	}

	for _, kv := range []struct {
		key string
		dst *int64
	}{{"maxValue", &p.MaxValue}, {"minEdgeThreshold", &p.MinEdgeThreshold}} {
		v, ok, err := geti(kv.key, 1)
		if err != nil {
			return p, err
		}
		if ok {
			*kv.dst = v[0]
		}
	}
	for _, kv := range []struct {
		key string
		dst *float64
	}{
		{"thresholdMultiplier", &p.ThresholdMultiplier},
		{"thresholdReductionFactor", &p.ThresholdReductionFactor},
		{"minEdgeRatio", &p.MinEdgeRatio},
		{"smoothingSizeFactor", &p.SmoothingSizeFactor},
		{"smoothingSigma", &p.SmoothingSigma},
	} {
		v, ok, err := getf(kv.key)
		if err != nil {
			return p, err
		}
		if ok {
			*kv.dst = v
		}
	}
	for _, kv := range []struct {
		key string
		dst *[2]int64
	}{
		{"lowToneRange", &p.LowToneRange},
		{"midLowToneRange", &p.MidLowToneRange},
		{"midHighToneRange", &p.MidHighToneRange},
		{"highToneRange", &p.HighToneRange},
	} {
		v, ok, err := geti(kv.key, 2)
		if err != nil {
			return p, err
		}
		if ok {
			*kv.dst = [2]int64{v[0], v[1]}
		}
	}
	for _, kv := range []struct {
		key string
		dst *string
	}{
		{"decisionTree", &p.DecisionTree},
		{"decisionTreeDei", &p.DecisionTreeDei},
	} {
		if v, ok := raw[kv.key]; ok {
			if toks := strings.Fields(v); len(toks) > 0 {
				*kv.dst = toks[0]
			}
		}
	}
	return p, nil
}

// ParseDecisionTree is AnsToneHelperDpi::readDecisionTree on
// AllOnTree1/dTree1.
//
// The first non-comment line is the node count; each subsequent line is
// `index metric threshold lessEqual greater class`. Note AllOnTree1 carries a
// COMMENTED-OUT node 0 (LUM_STDDEV 285.044 1 12 2) directly above the live one,
// which is why the live root threshold is 1.000 and not 285.044.
//
// The leading index column is positional only — the walker indexes the array,
// so a file whose indices are not 0..n-1 in order would be mis-walked. Both
// shipped trees are in order and this parser asserts it.
func ParseDecisionTree(text string) ([]DecisionNode, error) {
	var rows [][]string
	for _, line := range strings.Split(text, "\n") {
		s := strings.TrimSpace(strings.TrimRight(line, "\r"))
		if s == "" || strings.HasPrefix(s, "#") {
			continue
		}
		rows = append(rows, strings.Fields(s))
	}
	if len(rows) == 0 {
		return nil, errf("decision tree file has no data lines")
	}
	n, err := strconv.Atoi(rows[0][0])
	if err != nil {
		return nil, errf("decision tree node count %q is not an integer",
			rows[0][0])
	}
	if len(rows)-1 != n {
		return nil, errf("decision tree claims %d nodes, file has %d", n,
			len(rows)-1)
	}
	nodes := make([]DecisionNode, 0, n)
	for i, row := range rows[1:] {
		if len(row) < 6 {
			return nil, errf("decision tree node %d has %d columns, needs 6",
				i, len(row))
		}
		idx, err := strconv.Atoi(row[0])
		if err != nil || idx != i {
			return nil, errf("node index column %q != position %d; the walker "+
				"indexes the array, so out-of-order files would be mis-walked",
				row[0], i)
		}
		mid, ok := MetricID[row[1]]
		if !ok {
			return nil, errf("unknown metric name %q", row[1])
		}
		thr, err := strconv.ParseFloat(row[2], 64)
		if err != nil {
			return nil, errf("node %d threshold %q is not a number", i, row[2])
		}
		le, err1 := strconv.Atoi(row[3])
		gt, err2 := strconv.Atoi(row[4])
		cls, err3 := strconv.Atoi(row[5])
		if err1 != nil || err2 != nil || err3 != nil {
			return nil, errf("node %d has a non-integer goto or class", i)
		}
		nodes = append(nodes, DecisionNode{Metric: mid, Threshold: f32(thr),
			LessEqual: le, Greater: gt, Class: cls})
	}
	return nodes, nil
}

// LoadParams parses a vendored toneHelper-*.dpi from dataDir and attaches its
// decision tree, resolved against the same directory.
func LoadParams(dataDir, dpiName string) (Params, error) {
	if dpiName == "" {
		dpiName = DefaultDpi
	}
	raw, err := os.ReadFile(filepath.Join(dataDir, dpiName))
	if err != nil {
		return Params{}, err
	}
	p, err := ParseDpi(string(raw))
	if err != nil {
		return p, err
	}
	treeRaw, err := os.ReadFile(filepath.Join(dataDir, p.DecisionTree))
	if err != nil {
		return p, err
	}
	nodes, err := ParseDecisionTree(string(treeRaw))
	if err != nil {
		return p, err
	}
	p.Nodes = nodes
	return p, nil
}
