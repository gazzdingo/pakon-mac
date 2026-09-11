// Command cnadump produces the Go anscna port's output — the published
// AnsCnaResults AND every intermediate the analysis builds — for
// tools/test_cna_port.py to diff against pakon_cna.py.
//
// It exists for the same reason cmd/citrasdump and cmd/kcmsdump do: the
// comparison that matters crosses a language boundary, and streaming
// length-prefixed records out of a tiny program is the least ceremony that does
// it. Nothing in the render path imports this.
//
// Every stage is emitted, not just the ToneScaleLut, because docs/74 §171.3
// records that errors in this chain can have opposite signs — a stage checked
// only through the final curve can be wrong in a direction the total hides.
//
// Wire format, stdin (all little-endian):
//
//	i32 H, i32 W, i32 paramsLen
//	paramsLen bytes  the raw AnsCnaParams image (0x7c)
//	i16 * H*W*3      the interleaved frame
//
// Wire format, stdout: a sequence of records, each
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

	"pakonpipeline/anscna"
)

func die(format string, a ...any) {
	fmt.Fprintf(os.Stderr, "cnadump: "+format+"\n", a...)
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

func i64sAsI32(v []int64) []int32 {
	out := make([]int32, len(v))
	for i, x := range v {
		out[i] = int32(x)
	}
	return out
}

func i64sAsI64(v []int64) []int64 { return v }

func main() {
	in := bufio.NewReaderSize(os.Stdin, 1<<20)
	out := bufio.NewWriterSize(os.Stdout, 1<<20)

	var h, w, paramsLen int32
	for _, p := range []*int32{&h, &w, &paramsLen} {
		if err := binary.Read(in, binary.LittleEndian, p); err != nil {
			die("reading header: %v", err)
		}
	}
	raw := make([]byte, paramsLen)
	if _, err := io.ReadFull(in, raw); err != nil {
		die("reading params: %v", err)
	}
	params, err := anscna.ParamsFromBytes(raw)
	if err != nil {
		die("%v", err)
	}
	px := make([]int16, int(h)*int(w)*3)
	if err := binary.Read(in, binary.LittleEndian, px); err != nil {
		die("reading frame: %v", err)
	}
	img := anscna.Image{Width: int(w), Height: int(h), Pixels: px}
	fmt.Fprintf(os.Stderr, "%dx%d, histSize=%d bucketSize=%d pivot=%d",
		w, h, params.HistSize, params.BucketSize, params.Pivot)

	res, err := anscna.AnalyzeToResults(img, params)
	if err != nil {
		die("%v", err)
	}
	a := res.Analysis
	st := a.ThresholdStage

	// The threshold stage, in the order 0x1022ddc0 builds it.
	writeRecord(out, "lum", 1, len(st.Lum), 0, func() []int16 {
		v := make([]int16, len(st.Lum))
		for i, x := range st.Lum {
			v[i] = int16(x)
		}
		return v
	}())
	writeRecord(out, "lum_hist", 1, len(st.LumHist), 3, i64sAsI32(st.LumHist))
	writeRecord(out, "lap", 1, len(st.Lap), 0, func() []int16 {
		v := make([]int16, len(st.Lap))
		for i, x := range st.Lap {
			v[i] = int16(x)
		}
		return v
	}())
	writeRecord(out, "lap_hist", 1, len(st.LapHist), 3, i64sAsI32(st.LapHist))
	writeRecord(out, "edge_hist", 1, len(st.EdgeHist), 3, i64sAsI32(st.EdgeHist))
	writeRecord(out, "scalars", 1, 9, 4, i64sAsI64([]int64{
		st.NPixels, st.Half, int64(st.PeakIndex), st.Threshold,
		st.MinLapPixels, st.NEdge, boolI64(st.GaveUp),
		a.Pivot, a.PivotBucket,
	}))

	// The analysis proper.
	writeRecord(out, "bucket_hist", 1, len(a.BucketHist), 4, i64sAsI64(a.BucketHist))
	if a.Dark != nil {
		writeRecord(out, "dark_out", 1, len(a.Dark.Out), 4, i64sAsI64(a.Dark.Out))
	}
	if a.Light != nil {
		writeRecord(out, "light_out", 1, len(a.Light.Out), 4, i64sAsI64(a.Light.Out))
	}
	writeRecord(out, "curve", 1, len(a.Curve), 2, a.Curve)
	writeRecord(out, "tone_lut", 1, len(res.ToneScaleLut), 0, func() []int16 {
		v := make([]int16, len(res.ToneScaleLut))
		for i, x := range res.ToneScaleLut {
			v[i] = int16(x)
		}
		return v
	}())
	// The four sigmas plus elmoPercent, as the float32 bit patterns the real
	// AnsCnaResults holds — comparing the doubles would hide a narrowing bug.
	writeRecord(out, "sigmas", 1, 5, 2, []float64{
		res.DarkInSigma, res.LightInSigma, res.DarkOutSigma, res.LightOutSigma,
		res.ElmoPercent,
	})
	writeRecord(out, "elmo", 1, 3, 4, []int64{
		boolI64(res.BElmoOccured), a.Elmo.Count, boolI64(a.Elmo.Ran),
	})
	writeRecord(out, "crosses", 1, 2, 4, []int64{a.CrossDark, a.CrossLight})
	writeRecord(out, "percentile", 1, 1, 2, []float64{a.Percentile})

	out.WriteByte(0)
	if err := out.Flush(); err != nil {
		die("flush: %v", err)
	}
}

func boolI64(b bool) int64 {
	if b {
		return 1
	}
	return 0
}
