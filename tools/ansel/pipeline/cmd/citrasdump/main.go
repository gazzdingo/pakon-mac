// Command citrasdump produces the Go citras-driver port's output — the final
// image AND every intermediate plane — for tools/test_citras_driver_ports.py to
// diff against pakon_citras_driver.py.
//
// It exists for the same reason cmd/kcmsdump does: the comparison that matters
// crosses a language boundary, and streaming length-prefixed records out of a
// tiny program is the least ceremony that does it. Nothing in the render path
// imports this.
//
// Every stage is emitted, not just the result, because docs/74 §171.3 records
// that errors in this chain can have opposite signs — a stage checked only
// through the final image can be wrong in a direction the total hides.
//
// Wire format, stdin (all little-endian):
//
//	i32 H, i32 W, i32 lutLen, i32 paramCount
//	f64 sigma
//	i32 blockSize, minAvoidance, maxGradient, lowGradThr, highGradThr,
//	    doClipping, minValue, maxValue
//	i16 * H*W*3   the interleaved frame
//	i32 * lutLen  the tone LUT
//
// Wire format, stdout: a sequence of records, each
//
//	u8 nameLen, name bytes, i32 rows, i32 cols, u8 elemBytes, u8 kind
//	rows*cols*elemBytes payload bytes
//
// kind: 0 = int16, 1 = uint8, 2 = float64. A zero-length name ends the stream.
package main

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"os"

	"pakonpipeline/citrasdriver"
)

func die(format string, a ...any) {
	fmt.Fprintf(os.Stderr, "citrasdump: "+format+"\n", a...)
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
	}
	binary.Write(w, binary.LittleEndian, int32(rows))
	binary.Write(w, binary.LittleEndian, int32(cols))
	w.WriteByte(elem)
	w.WriteByte(kind)
	if err := binary.Write(w, binary.LittleEndian, payload); err != nil {
		die("write payload %q: %v", name, err)
	}
}

func main() {
	in := bufio.NewReaderSize(os.Stdin, 1<<20)
	out := bufio.NewWriterSize(os.Stdout, 1<<20)

	var h, w, lutLen, paramCount int32
	for _, p := range []*int32{&h, &w, &lutLen, &paramCount} {
		if err := binary.Read(in, binary.LittleEndian, p); err != nil {
			die("reading header: %v", err)
		}
	}
	if paramCount != 8 {
		die("header says %d int params; this build expects 8", paramCount)
	}
	var sigma float64
	if err := binary.Read(in, binary.LittleEndian, &sigma); err != nil {
		die("reading sigma: %v", err)
	}
	ints := make([]int32, 8)
	if err := binary.Read(in, binary.LittleEndian, ints); err != nil {
		die("reading params: %v", err)
	}
	p := citrasdriver.Params{
		Sigma:                 sigma,
		BlockSize:             int(ints[0]),
		MinAvoidance:          int(ints[1]),
		MaxGradient:           int(ints[2]),
		LowGradientThreshold:  int(ints[3]),
		HighGradientThreshold: int(ints[4]),
		DoClipping:            int(ints[5]),
		MinValue:              int(ints[6]),
		MaxValue:              int(ints[7]),
	}

	// The frame arrives as float64 when --float is given — the post-FUGC RPD-12
	// the render path actually holds — so that citrasdriver.QuantiseRPD12 is
	// VERIFIED against np.rint rather than merely asserted to match it. The
	// verification came back bit-exact and also came back showing the check is
	// weak: a real frame contains zero exact .5 values, so rint and
	// round-half-away cannot differ on it. Kept because it costs nothing and
	// covers the clip bounds as well as the rounding.
	asFloat := false
	for _, a := range os.Args[1:] {
		if a == "--float" {
			asFloat = true
		}
	}

	img := citrasdriver.ImageI16{H: int(h), W: int(w), Px: make([]int16, int(h)*int(w)*3)}
	if asFloat {
		raw64 := make([]float64, len(img.Px))
		if err := binary.Read(io.LimitReader(in, int64(len(raw64))*8), binary.LittleEndian, raw64); err != nil {
			die("reading %dx%d float frame: %v", w, h, err)
		}
		for i, v := range raw64 {
			img.Px[i] = citrasdriver.QuantiseRPD12(v)
		}
	} else if err := binary.Read(io.LimitReader(in, int64(len(img.Px))*2), binary.LittleEndian, img.Px); err != nil {
		die("reading %dx%d frame: %v", w, h, err)
	}
	raw := make([]int32, lutLen)
	if err := binary.Read(in, binary.LittleEndian, raw); err != nil {
		die("reading tone LUT: %v", err)
	}
	lut := make([]int64, lutLen)
	for i, v := range raw {
		lut[i] = int64(v)
	}

	toned, tr, err := citrasdriver.ApplyTraced(img, lut, p)
	if err != nil {
		die("%v", err)
	}

	// The avoidance table is a function of the params alone, so it is emitted
	// as a 1-row record rather than being recomputed by the harness.
	table, lo, hi := citrasdriver.AvoidanceTable(p)
	fmt.Fprintf(os.Stderr, "radius=%d blocks=%dx%d lowThr=%d highThr=%d\n",
		citrasdriver.GaussianRadius(p.Sigma), tr.Blk.H, tr.Blk.W, lo, hi)

	writeRecord(out, "clipped", img.H, img.W*3, 0, img.Px)
	writeRecord(out, "kernel", 1, len(tr.Kernel), 2, tr.Kernel)
	writeRecord(out, "avoidtab", 1, len(table), 1, table)
	writeRecord(out, "lum", tr.Lum.H, tr.Lum.W, 0, tr.Lum.Px)
	writeRecord(out, "padded", tr.Padded.H, tr.Padded.W, 0, tr.Padded.Px)
	writeRecord(out, "blk", tr.Blk.H, tr.Blk.W, 0, tr.Blk.Px)
	writeRecord(out, "ext", tr.Ext.H, tr.Ext.W, 0, tr.Ext.Px)
	writeRecord(out, "smooth", tr.Smooth.H, tr.Smooth.W, 0, tr.Smooth.Px)
	writeRecord(out, "weightlow", tr.WeightLow.H, tr.WeightLow.W, 1, tr.WeightLow.Px)
	writeRecord(out, "reference", tr.Reference.H, tr.Reference.W, 0, tr.Reference.Px)
	writeRecord(out, "weight", tr.Weight.H, tr.Weight.W, 1, tr.Weight.Px)
	writeRecord(out, "delta", tr.Delta.H, tr.Delta.W, 0, tr.Delta.Px)
	writeRecord(out, "toned", toned.H, toned.W*3, 0, toned.Px)
	out.WriteByte(0) // end of stream

	if err := out.Flush(); err != nil {
		die("flush: %v", err)
	}
}
