// Command dradump produces the Go ansdra port's output — the published
// AnsDraResults, the parsed params, and every intermediate generateLut builds —
// for tools/test_dra_port.py to diff against pakon_dra.py.
//
// It exists for the same reason cmd/cnadump and cmd/citrasdump do. Nothing in
// the render path imports it.
//
// The params are loaded by the Go side from the vendor .dpi/.ttc on disk, and
// emitted as records, so the harness verifies the Go PARSER against the Python
// parser as well as the arithmetic — a params field that silently failed to
// parse would otherwise look like a correct port of a wrong number.
//
// Wire format, stdin (all little-endian):
//
//	i32 nSmall, i32 lighting, i32 haveLum, i32 haveEdge, i32 haveTone
//	i32 dpiDirLen, dpiDir bytes
//	i32 * nSmall   lumHist   (only when haveLum)
//	i32 * nSmall   edgeHist  (only when haveEdge)
//	i16 * nSmall   toneLut   (only when haveTone)
//
// Wire format, stdout: the same record stream cnadump emits —
//
//	u8 nameLen, name bytes, i32 rows, i32 cols, u8 elemBytes, u8 kind
//	rows*cols*elemBytes payload bytes
//
// kind: 0 = int16, 1 = uint8, 2 = float64, 3 = int32, 4 = int64.
// A zero-length name ends the stream.
package main

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"os"

	"pakonpipeline/ansdra"
)

func die(format string, a ...any) {
	fmt.Fprintf(os.Stderr, "dradump: "+format+"\n", a...)
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
	case 1:
		elem = 1
	case 2:
		elem = 8
	case 3:
		elem = 4
	case 4:
		elem = 8
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

func readI32Array(in io.Reader, n int) []int64 {
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

func readI16Array(in io.Reader, n int) []int64 {
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

func emitI64(w *bufio.Writer, name string, v []int64) {
	writeRecord(w, name, 1, len(v), 4, v)
}

func boolI64(b bool) int64 {
	if b {
		return 1
	}
	return 0
}

func main() {
	in := bufio.NewReaderSize(os.Stdin, 1<<20)
	out := bufio.NewWriterSize(os.Stdout, 1<<20)

	var nSmall, lighting, haveLum, haveEdge, haveTone, dirLen int32
	for _, p := range []*int32{&nSmall, &lighting, &haveLum, &haveEdge,
		&haveTone, &dirLen} {
		if err := binary.Read(in, binary.LittleEndian, p); err != nil {
			die("reading header: %v", err)
		}
	}
	dirBuf := make([]byte, dirLen)
	if _, err := io.ReadFull(in, dirBuf); err != nil {
		die("reading dpi dir: %v", err)
	}
	var lumHist, edgeHist, toneLut []int64
	if haveLum != 0 {
		lumHist = readI32Array(in, int(nSmall))
	}
	if haveEdge != 0 {
		edgeHist = readI32Array(in, int(nSmall))
	}
	if haveTone != 0 {
		toneLut = readI16Array(in, int(nSmall))
	}

	p, err := ansdra.LoadParams(string(dirBuf), "")
	if err != nil {
		die("%v", err)
	}
	fmt.Fprintf(os.Stderr, "maxValue=%d binFactor=%d paper=[%d,%d] fp=[%d,%d] "+
		"lighting=%d", p.MaxValue, p.BinFactor, p.PaperMin, p.PaperMax,
		p.LowFixedPoint, p.HighFixedPoint, lighting)

	// The parsed params, so the Go .dpi/.ttc parser is checked, not assumed.
	emitI64(out, "params_i", []int64{
		p.MaxValue, p.LowFixedPoint, p.HighFixedPoint, p.PaperMin, p.PaperMax,
		p.BinFactor, boolI64(p.BDoAverage), boolI64(p.BIsBacklit),
		boolI64(p.BIsFlash), int64(ansdra.ValidateParams(p)),
	})
	writeRecord(out, "params_f", 1, 10, 2, []float64{
		p.MinSlope, p.MaxSlope, p.LumWeighting, p.EdgeWeighting,
		p.FlashFraction, p.BacklitFraction, p.StartingMinCumPoint,
		p.CumPctBelowMin, p.StartingMaxCumPoint, p.CumPctAboveMax,
	})
	low, high, err := p.CurvePair(int64(lighting))
	if err != nil {
		die("%v", err)
	}
	writeRecord(out, "low_x", 1, len(low.X), 2, low.X)
	writeRecord(out, "low_y", 1, len(low.Y), 2, low.Y)
	writeRecord(out, "low_slope", 1, len(low.Slope), 2, low.Slope)
	writeRecord(out, "high_x", 1, len(high.X), 2, high.X)
	writeRecord(out, "high_y", 1, len(high.Y), 2, high.Y)
	writeRecord(out, "high_slope", 1, len(high.Slope), 2, high.Slope)

	// Run the two halves separately so the pre-compose curve is observable:
	// generateLut's own output and the composed one are different arrays, and a
	// port that composed twice (or not at all) would still produce something
	// plausible from the outside.
	if bad := ansdra.ValidateParams(p); bad != 0 {
		die("Parameter #%d is invalid.", bad)
	}
	if lumHist == nil && edgeHist == nil {
		die("No analysis data was provided!.")
	}
	res := ansdra.Alloc(int64(nSmall), lumHist != nil, edgeHist != nil,
		p.BinFactor)
	if lumHist != nil {
		res.LumHist = append([]int64(nil), lumHist...)
	}
	if edgeHist != nil {
		res.EdgeHist = append([]int64(nil), edgeHist...)
	}
	preCompose, err := ansdra.GenerateLut(res, p, int64(lighting), toneLut)
	if err != nil {
		die("%v", err)
	}
	emitI64(out, "lum_remapped", res.LumHist)
	emitI64(out, "lum_large", res.LumLargeHist)
	emitI64(out, "lum_cum", res.LumCumHist)
	emitI64(out, "edge_remapped", res.EdgeHist)
	emitI64(out, "edge_large", res.EdgeLargeHist)
	emitI64(out, "edge_cum", res.EdgeCumHist)
	emitI64(out, "bounds", []int64{
		res.NSmallBins, res.NLargeBins, res.NLumPixels, res.NEdgePixels,
		res.LumMin, res.LumMax, res.EdgeMin, res.EdgeMax,
		res.EffMin, res.EffMax,
	})
	emitI64(out, "lut_precompose", preCompose)

	final := preCompose
	if toneLut != nil {
		final, err = ansdra.ComposeTone(preCompose, toneLut, int(nSmall))
		if err != nil {
			die("%v", err)
		}
	}
	emitI64(out, "dra_lut", final)

	out.WriteByte(0)
	if err := out.Flush(); err != nil {
		die("flush: %v", err)
	}
}
