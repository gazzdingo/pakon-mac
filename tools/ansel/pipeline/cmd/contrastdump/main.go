// Command contrastdump produces the Go anscontrast port's output — the parsed
// params, the constrainSlope flag/curve pass, the adjustment curve and the
// final OutToneLut — for tools/test_contrast_port.py to diff against
// pakon_contrast.py.
//
// OutToneLut is the ANALYSIS half's actual output: the 4096-entry curve the
// render applies through the citras driver. Every intermediate is emitted
// anyway, because docs/74 §171.3 records that errors in this chain can have
// opposite signs and a stage checked only through the final curve can be wrong
// in a direction the total hides.
//
// Wire format, stdin (all little-endian):
//
//	i32 lutSize, i32 sceneType, i32 x, i32 keepIntermediates, i32 haveTone
//	i32 dpiDirLen, dpiDir bytes, i32 dpiNameLen, dpiName bytes
//	i16 * lutSize   toneLut (only when haveTone)
//
// Wire format, stdout: the record stream cnadump/dradump/thdump emit.
// kind: 0 = int16, 1 = uint8, 2 = float64, 3 = int32, 4 = int64.
package main

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"os"

	"pakonpipeline/anscontrast"
)

func die(format string, a ...any) {
	fmt.Fprintf(os.Stderr, "contrastdump: "+format+"\n", a...)
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

func readStr(in io.Reader) string {
	var n int32
	if err := binary.Read(in, binary.LittleEndian, &n); err != nil {
		die("reading string length: %v", err)
	}
	b := make([]byte, n)
	if _, err := io.ReadFull(in, b); err != nil {
		die("reading string: %v", err)
	}
	return string(b)
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

	var lutSize, sceneType, x, keep, haveTone int32
	for _, p := range []*int32{&lutSize, &sceneType, &x, &keep, &haveTone} {
		if err := binary.Read(in, binary.LittleEndian, p); err != nil {
			die("reading header: %v", err)
		}
	}
	dpiDir := readStr(in)
	dpiName := readStr(in)
	var toneLut []int64
	if haveTone != 0 {
		raw := make([]int16, lutSize)
		if err := binary.Read(in, binary.LittleEndian, raw); err != nil {
			die("reading tone LUT: %v", err)
		}
		toneLut = make([]int64, lutSize)
		for i, v := range raw {
			toneLut[i] = int64(v)
		}
	}

	p, err := anscontrast.LoadParams(dpiDir, dpiName)
	if err != nil {
		die("%v", err)
	}
	fmt.Fprintf(os.Stderr, "mode=%d lutSize=%d maxValue=%d midpoint=%d/%d "+
		"constrain=%v csFixed=%d sceneType=%d x=%d", p.UserInputMode, p.LutSize,
		p.MaxValue, p.MidpointIn, p.MidpointOut, p.BConstrainSlope,
		p.CsFixedIndex, sceneType, x)

	writeRecord(out, "params_i", 1, 12, 4, []int64{
		p.MaxValue, p.LutSize, int64(p.UserInputMode), p.MidpointIn,
		p.MidpointOut, boolI64(p.BConstrainSlope), p.CsGranularity,
		p.CsNSamples, p.CsLowerIndex, p.CsFixedIndex, p.CsUpperIndex,
		int64(len(p.Points)),
	})
	writeRecord(out, "params_f", 1, 5, 2, []float64{
		p.LowInitialSlope, p.HighInitialSlope, p.LowIncr, p.HighIncr, p.AllIncr,
	})
	slopes := make([]float64, 0, 4*anscontrast.SlopeArrayLen)
	slopes = append(slopes, p.ALowerMinSlope[:]...)
	slopes = append(slopes, p.ALowerMaxSlope[:]...)
	slopes = append(slopes, p.AUpperMinSlope[:]...)
	slopes = append(slopes, p.AUpperMaxSlope[:]...)
	writeRecord(out, "slopes", 1, len(slopes), 2, slopes)
	pts := make([]int64, 0, 2*len(p.Points))
	for _, pt := range p.Points {
		pts = append(pts, pt.In, pt.Out)
	}
	writeRecord(out, "points", 1, len(pts), 4, pts)
	writeRecord(out, "band", 1, 1, 4,
		[]int64{int64(anscontrast.SlopeBand(int64(sceneType), int64(x)))})

	// constrainSlope on its own, before the Impl runs it, so its flag/curve
	// output is observable independently of the compose that follows.
	if p.BConstrainSlope && toneLut != nil {
		inLut := make([]int64, p.LutSize)
		copy(inLut, toneLut)
		csOut := make([]int64, p.LutSize)
		r := anscontrast.DefaultResults()
		if err := anscontrast.ConstrainSlope(p, &r, inLut, csOut,
			int64(sceneType), int64(x)); err != nil {
			die("%v", err)
		}
		writeRecord(out, "cs_lut", 1, len(csOut), 4, csOut)
		writeRecord(out, "cs_limits", 1, 4, 2, []float64{
			r.LowerMinSlopeLimit, r.LowerMaxSlopeLimit,
			r.UpperMinSlopeLimit, r.UpperMaxSlopeLimit,
		})
		writeRecord(out, "cs_flags", 1, 4, 4, []int64{
			boolI64(r.BWasLowerMinLimitReached),
			boolI64(r.BWasLowerMaxLimitReached),
			boolI64(r.BWasUpperMinLimitReached),
			boolI64(r.BWasUpperMaxLimitReached),
		})
	}

	// The subsystem as analyzeAutoTone drives it. keepIntermediates is forced
	// on here so CAdjLut and InToneLut can be compared; the real cap+0xe is 0
	// and the shipped path frees them, which the "kept" record records.
	sub := anscontrast.NewSubsystem(p, keep != 0)
	if err := sub.Acquire(int64(sceneType), int64(x), toneLut); err != nil {
		die("%v", err)
	}
	r := sub.Results
	writeRecord(out, "results_f", 1, 6, 2, []float64{
		r.LowSlope, r.HighSlope, r.LowerMinSlopeLimit, r.LowerMaxSlopeLimit,
		r.UpperMinSlopeLimit, r.UpperMaxSlopeLimit,
	})
	writeRecord(out, "results_i", 1, 8, 4, []int64{
		r.LutSize,
		boolI64(r.BWasLowerMinLimitReached), boolI64(r.BWasLowerMaxLimitReached),
		boolI64(r.BWasUpperMinLimitReached), boolI64(r.BWasUpperMaxLimitReached),
		boolI64(r.CAdjLut != nil), boolI64(r.InToneLut != nil),
		boolI64(r.OutToneLut != nil),
	})
	if r.CAdjLut != nil {
		writeRecord(out, "adj_lut", 1, len(r.CAdjLut), 4, r.CAdjLut)
	}
	if r.InToneLut != nil {
		writeRecord(out, "in_lut", 1, len(r.InToneLut), 4, r.InToneLut)
	}
	if r.OutToneLut != nil {
		writeRecord(out, "out_tone_lut", 1, len(r.OutToneLut), 4, r.OutToneLut)
	}

	out.WriteByte(0)
	if err := out.Flush(); err != nil {
		die("flush: %v", err)
	}
}
