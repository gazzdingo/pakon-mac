// Command kcmsdump produces the Go vendor-CLUT port's output for
// tools/test_kcms_clut_ports.py to diff against the Python reference.
//
// It exists because the comparison that matters — Go against
// pakon_kcms_clut.py, which is itself bit-exact against the real
// kodakcms.dll — has to cross a language boundary, and streaming bytes out of
// a tiny program is the least ceremony that does it. Nothing in the render
// path imports this.
//
//	kcmsdump --exhaustive   all 16,777,216 u8 RGB triples' outputs on stdout,
//	                        r slowest / b fastest (the golden harness's order)
//	kcmsdump --stream       int32 count then count*3 u8 on stdin, count*3 u8 out
//	kcmsdump --tetra        per-tetrahedron hit counts over the domain, stderr
package main

import (
	"bufio"
	"encoding/binary"
	"fmt"
	"io"
	"os"

	"pakonpipeline/kcmsclut"
)

func exhaustive(w *bufio.Writer) {
	var in [3]uint8
	for r := 0; r < 256; r++ {
		in[0] = uint8(r)
		for g := 0; g < 256; g++ {
			in[1] = uint8(g)
			for b := 0; b < 256; b++ {
				in[2] = uint8(b)
				out := kcmsclut.EvalU8(in)
				w.Write(out[:])
			}
		}
	}
}

func stream(w *bufio.Writer) error {
	r := bufio.NewReaderSize(os.Stdin, 1<<20)
	var count int32
	if err := binary.Read(r, binary.LittleEndian, &count); err != nil {
		return err
	}
	if count < 0 {
		return fmt.Errorf("negative count %d", count)
	}
	buf := make([]byte, int(count)*3)
	if _, err := io.ReadFull(r, buf); err != nil {
		return err
	}
	for i := 0; i < int(count); i++ {
		out := kcmsclut.EvalU8([3]uint8{buf[i*3], buf[i*3+1], buf[i*3+2]})
		w.Write(out[:])
	}
	return nil
}

func tetra() {
	names := [6]string{
		"wR>wG>wB", "wR>wB>=wG", "wB>=wR>wG",
		"wG>wB>=wR", "wG>=wR>wB", "wB>=wG>=wR",
	}
	var hits [6]int64
	var in [3]uint8
	for r := 0; r < 256; r++ {
		in[0] = uint8(r)
		for g := 0; g < 256; g++ {
			in[1] = uint8(g)
			for b := 0; b < 256; b++ {
				in[2] = uint8(b)
				hits[kcmsclut.TetraOf(in)]++
			}
		}
	}
	for i, n := range names {
		fmt.Fprintf(os.Stderr, "tetra %d %-10s %12d  %6.2f %%\n",
			i, n, hits[i], 100.0*float64(hits[i])/16777216.0)
	}
}

func main() {
	mode := "--exhaustive"
	if len(os.Args) > 1 {
		mode = os.Args[1]
	}
	w := bufio.NewWriterSize(os.Stdout, 1<<20)
	defer w.Flush()
	switch mode {
	case "--exhaustive":
		exhaustive(w)
	case "--stream":
		if err := stream(w); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
	case "--tetra":
		tetra()
	default:
		fmt.Fprintf(os.Stderr, "unknown mode %s\n", mode)
		os.Exit(2)
	}
}
