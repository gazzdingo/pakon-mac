// Command thdump produces the Go anstonehelper port's output — the parsed
// params and decision tree, both metric groups, the walk path and the published
// toneHelperValue — for tools/test_tonehelper_port.py to diff against
// pakon_toneHelper.py.
//
// Every metric is emitted, not just the one integer that crosses the shell
// boundary: toneHelperValue is a 1-or-2 decision, so a port that got most of
// the 29 metrics wrong would still agree with the reference roughly half the
// time by chance. Comparing the metrics is what makes a pass mean something.
//
// Wire format, stdin (all little-endian):
//
//	i32 n, i32 haveExposure, f64 exposure, i32 dataDirLen, dataDir bytes
//	i32 * n   lumHist
//	i32 * n   edgeHist
//	i16 * n   toneLut
//
// Wire format, stdout: the record stream cnadump/dradump emit.
// kind: 0 = int16, 1 = uint8, 2 = float64, 3 = int32, 4 = int64.
package main

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"os"

	"pakonpipeline/anstonehelper"
)

func die(format string, a ...any) {
	fmt.Fprintf(os.Stderr, "thdump: "+format+"\n", a...)
	os.Exit(1)
}

func writeRecord(w *bufio.Writer, name string, rows, cols int, kind uint8, payload any) {
	if err := w.WriteByte(uint8(len(name))); err != nil {
		die("write: %v", err)
	}
	if _, err := w.WriteString(name); err != nil {
		die("write: %v", err)
	}
	var elem uint8
	switch kind {
	case 0:
		elem = 2
	case 2, 4:
		elem = 8
	case 3:
		elem = 4
	default:
		die("unknown kind %d", kind)
	}
	binary.Write(w, binary.LittleEndian, int32(rows))
	binary.Write(w, binary.LittleEndian, int32(cols))
	w.WriteByte(elem)
	w.WriteByte(kind)
	if err := binary.Write(w, binary.LittleEndian, payload); err != nil {
		die("write payload %q: %v", name, err)
	}
}

func readI32(in io.Reader, n int) []int64 {
	raw := make([]int32, n)
	if err := binary.Read(in, binary.LittleEndian, raw); err != nil {
		die("reading i32 array: %v", err)
	}
	out := make([]int64, n)
	for i, v := range raw {
		out[i] = int64(v)
	}
	return out
}

func readI16(in io.Reader, n int) []int64 {
	raw := make([]int16, n)
	if err := binary.Read(in, binary.LittleEndian, raw); err != nil {
		die("reading i16 array: %v", err)
	}
	out := make([]int64, n)
	for i, v := range raw {
		out[i] = int64(v)
	}
	return out
}

func groupF64(g anstonehelper.MetricGroup) []float64 {
	return []float64{
		g.WorkLow, g.WorkMidLow, g.WorkSumLow, g.WorkMidHigh, g.WorkHigh,
		g.WorkSumHigh, g.WorkTotal, g.Distance, g.Intersection, g.Average,
		g.AvgDev, g.StdDev, g.Skew, g.Kurtosis,
	}
}

func main() {
	in := bufio.NewReaderSize(os.Stdin, 1<<20)
	out := bufio.NewWriterSize(os.Stdout, 1<<20)

	var n, haveExposure, dirLen int32
	var exposure float64
	if err := binary.Read(in, binary.LittleEndian, &n); err != nil {
		die("reading header: %v", err)
	}
	if err := binary.Read(in, binary.LittleEndian, &haveExposure); err != nil {
		die("reading header: %v", err)
	}
	if err := binary.Read(in, binary.LittleEndian, &exposure); err != nil {
		die("reading header: %v", err)
	}
	if err := binary.Read(in, binary.LittleEndian, &dirLen); err != nil {
		die("reading header: %v", err)
	}
	dirBuf := make([]byte, dirLen)
	if _, err := io.ReadFull(in, dirBuf); err != nil {
		die("reading data dir: %v", err)
	}
	lumHist := readI32(in, int(n))
	edgeHist := readI32(in, int(n))
	toneLut := readI16(in, int(n))

	p, err := anstonehelper.LoadParams(string(dirBuf), "")
	if err != nil {
		die("%v", err)
	}
	fmt.Fprintf(os.Stderr, "maxValue=%d tree=%s (%d nodes) bands=%v/%v/%v/%v",
		p.MaxValue, p.DecisionTree, len(p.Nodes), p.LowToneRange,
		p.MidLowToneRange, p.MidHighToneRange, p.HighToneRange)

	// The parsed params and tree, so the Go .dpi/tree parser is checked too.
	writeRecord(out, "params_i", 1, 10, 4, []int64{
		p.MaxValue, p.MinEdgeThreshold,
		p.LowToneRange[0], p.LowToneRange[1],
		p.MidLowToneRange[0], p.MidLowToneRange[1],
		p.MidHighToneRange[0], p.MidHighToneRange[1],
		p.HighToneRange[0], p.HighToneRange[1],
	})
	writeRecord(out, "params_f", 1, 5, 2, []float64{
		p.ThresholdMultiplier, p.ThresholdReductionFactor, p.MinEdgeRatio,
		p.SmoothingSizeFactor, p.SmoothingSigma,
	})
	nodesI := make([]int64, 0, len(p.Nodes)*4)
	nodesF := make([]float64, 0, len(p.Nodes))
	for _, nd := range p.Nodes {
		nodesI = append(nodesI, int64(nd.Metric), int64(nd.LessEqual),
			int64(nd.Greater), int64(nd.Class))
		nodesF = append(nodesF, nd.Threshold)
	}
	writeRecord(out, "tree_i", 1, len(nodesI), 4, nodesI)
	writeRecord(out, "tree_f", 1, len(nodesF), 2, nodesF)

	res, err := anstonehelper.AnalyzeWithHistograms(p, lumHist, edgeHist,
		toneLut, exposure, haveExposure != 0)
	if err != nil {
		die("%v", err)
	}

	writeRecord(out, "lum_group", 1, 14, 2, groupF64(res.Lum))
	writeRecord(out, "edge_group", 1, 14, 2, groupF64(res.Edge))
	writeRecord(out, "counts", 1, 2, 4, []int64{res.Lum.Count, res.Edge.Count})
	metrics := anstonehelper.MetricsByID(res.Lum, res.Edge, res.Exposure)
	byID := make([]float64, 0, 29)
	for id := 2; id <= 30; id++ {
		byID = append(byID, metrics[id])
	}
	writeRecord(out, "metrics", 1, len(byID), 2, byID)
	path := make([]int64, len(res.Path))
	for i, v := range res.Path {
		path[i] = int64(v)
	}
	writeRecord(out, "path", 1, len(path), 4, path)
	writeRecord(out, "published", 1, 4, 4, []int64{
		int64(res.TerminalNode), int64(res.ToneHelperValue),
		int64(res.SceneClass), res.NPixels,
	})

	out.WriteByte(0)
	if err := out.Flush(); err != nil {
		die("flush: %v", err)
	}
}
