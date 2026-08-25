// Command autotonedump runs the Go ANALYSIS chain — cna -> dra -> toneHelper
// -> contrast, package ansautotone — over a real interleaved int16 frame and
// emits every value that crosses a stage boundary, for
// tools/test_autotone_chain.py to diff against pakon_ansel.real_auto_tone's own
// wiring of the Python subsystems.
//
// The per-stage records are what makes a pass mean something: OutToneLut is a
// single array at the end of four subsystems, and a chain wired up wrongly
// between two of them can still produce a plausible curve.
//
// Wire format, stdin (all little-endian):
//
//	i32 H, i32 W, i32 sceneType, f64 exposure, i32 rootLen, root bytes
//	i16 * H*W*3   the interleaved frame
//
// `root` is the dataPathItems directory holding dra/, toneHelper/ and
// contrast/.
//
// Wire format, stdout: the record stream the other dump commands emit.
// kind: 0 = int16, 1 = uint8, 2 = float64, 3 = int32, 4 = int64.
package main

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"os"

	"pakonpipeline/ansautotone"
	"pakonpipeline/anscna"
)

func die(format string, a ...any) {
	fmt.Fprintf(os.Stderr, "autotonedump: "+format+"\n", a...)
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

func boolI64(b bool) int64 {
	if b {
		return 1
	}
	return 0
}

func main() {
	in := bufio.NewReaderSize(os.Stdin, 1<<20)
	out := bufio.NewWriterSize(os.Stdout, 1<<20)

	var h, w, sceneType, rootLen int32
	var exposure float64
	if err := binary.Read(in, binary.LittleEndian, &h); err != nil {
		die("reading header: %v", err)
	}
	if err := binary.Read(in, binary.LittleEndian, &w); err != nil {
		die("reading header: %v", err)
	}
	if err := binary.Read(in, binary.LittleEndian, &sceneType); err != nil {
		die("reading header: %v", err)
	}
	if err := binary.Read(in, binary.LittleEndian, &exposure); err != nil {
		die("reading header: %v", err)
	}
	if err := binary.Read(in, binary.LittleEndian, &rootLen); err != nil {
		die("reading header: %v", err)
	}
	rootBuf := make([]byte, rootLen)
	if _, err := io.ReadFull(in, rootBuf); err != nil {
		die("reading root: %v", err)
	}
	px := make([]int16, int(h)*int(w)*3)
	if err := binary.Read(in, binary.LittleEndian, px); err != nil {
		die("reading frame: %v", err)
	}

	params, err := ansautotone.LoadParams(string(rootBuf))
	if err != nil {
		die("%v", err)
	}
	img := anscna.Image{Width: int(w), Height: int(h), Pixels: px}
	fmt.Fprintf(os.Stderr, "%dx%d sceneType=%d", w, h, sceneType)

	lut, tr, err := ansautotone.Analyze(img, params, int64(sceneType), exposure)
	if err != nil {
		die("%v", err)
	}

	writeRecord(out, "lum_hist", 1, len(tr.LumHist), 3, toI32(tr.LumHist))
	writeRecord(out, "edge_hist", 1, len(tr.EdgeHist), 3, toI32(tr.EdgeHist))
	writeRecord(out, "tone_scale_lut", 1, len(tr.ToneScaleLut), 4,
		tr.ToneScaleLut)
	writeRecord(out, "dra_lut", 1, len(tr.DraLut), 4, tr.DraLut)
	writeRecord(out, "scalars", 1, 6, 4, []int64{
		boolI64(tr.ElmoOccured), int64(tr.ToneHelperValue),
		int64(tr.SceneClass), tr.X, tr.SceneType, tr.LutSize,
	})
	if lut == nil {
		writeRecord(out, "out_tone_lut", 1, 0, 4, []int64{})
	} else {
		writeRecord(out, "out_tone_lut", 1, len(lut), 4, lut)
	}

	out.WriteByte(0)
	if err := out.Flush(); err != nil {
		die("flush: %v", err)
	}
}

func toI32(v []int64) []int32 {
	out := make([]int32, len(v))
	for i, x := range v {
		out[i] = int32(x)
	}
	return out
}
