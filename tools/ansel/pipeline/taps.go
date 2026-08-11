package main

// Per-stage taps, for the parity harness.
//
// A final-image-only comparison between two engines tells you they disagree
// and nothing about where. These write one raw array per stage so
// tools/pakon_parity.py can localise a divergence to the stage that caused
// it. Format is deliberately the dullest thing that works: little-endian
// float64, (h, w, 3) C-order, one file per tap, plus a manifest naming them
// in order. np.fromfile reads it with no dependencies.

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
)

type TapWriter struct {
	dir    string
	h, w   int
	order  []string
	meta   map[string]any
	failed error
}

func NewTapWriter(dir string, h, w int) (*TapWriter, error) {
	if dir == "" {
		return nil, nil
	}
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	return &TapWriter{dir: dir, h: h, w: w, meta: map[string]any{}}, nil
}

// Set records a scalar or small vector alongside the taps — film base, aim
// words, the bias, the selected files. These are what tell you *why* a tap
// diverged once you know that it did.
func (t *TapWriter) Set(key string, val any) {
	if t == nil {
		return
	}
	t.meta[key] = val
}

// Write dumps an (h, w, 3) float64 stage output.
func (t *TapWriter) Write(name string, img [][][3]float64) {
	if t == nil || t.failed != nil {
		return
	}
	f, err := os.Create(filepath.Join(t.dir, name+".f64"))
	if err != nil {
		t.failed = err
		return
	}
	defer f.Close()
	buf := make([]byte, 8*3*t.w)
	for y := 0; y < len(img); y++ {
		row := img[y]
		for x := 0; x < len(row); x++ {
			for c := 0; c < 3; c++ {
				binary.LittleEndian.PutUint64(buf[8*(3*x+c):], math.Float64bits(row[x][c]))
			}
		}
		if _, err := f.Write(buf[:8*3*len(row)]); err != nil {
			t.failed = err
			return
		}
	}
	t.order = append(t.order, name)
}

// WriteU8 dumps an (h, w, 3) uint8 stage output — the ICC tap.
func (t *TapWriter) WriteU8(name string, img [][][3]uint8) {
	if t == nil || t.failed != nil {
		return
	}
	f, err := os.Create(filepath.Join(t.dir, name+".u8"))
	if err != nil {
		t.failed = err
		return
	}
	defer f.Close()
	buf := make([]byte, 3*t.w)
	for y := 0; y < len(img); y++ {
		row := img[y]
		for x := 0; x < len(row); x++ {
			buf[3*x+0] = row[x][0]
			buf[3*x+1] = row[x][1]
			buf[3*x+2] = row[x][2]
		}
		if _, err := f.Write(buf[:3*len(row)]); err != nil {
			t.failed = err
			return
		}
	}
	t.order = append(t.order, name)
}

func (t *TapWriter) Close() error {
	if t == nil {
		return nil
	}
	if t.failed != nil {
		return t.failed
	}
	t.meta["taps"] = t.order
	t.meta["height"] = t.h
	t.meta["width"] = t.w
	t.meta["engine"] = "go"
	data, err := json.MarshalIndent(t.meta, "", " ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(t.dir, "manifest.json"), data, 0o644)
}

// ReadRawU16 reads an (h, w, 3) little-endian uint16 frame — the parity
// harness's input format, and the shape the phase-2 ABI will pass by pointer.
// It is the CALIBRATED 14-bit capture slice on the capture's own grid, before
// unsquash and before rot90; this pipeline must not resample it.
func ReadRawU16(path string, h, w int) ([][][3]uint16, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	want := h * w * 3 * 2
	if len(data) != want {
		return nil, fmt.Errorf("%s: %d bytes, want %d for %dx%dx3 u16",
			path, len(data), want, h, w)
	}
	out := make([][][3]uint16, h)
	for y := 0; y < h; y++ {
		row := make([][3]uint16, w)
		base := y * w * 3 * 2
		for x := 0; x < w; x++ {
			o := base + x*6
			row[x] = [3]uint16{
				binary.LittleEndian.Uint16(data[o:]),
				binary.LittleEndian.Uint16(data[o+2:]),
				binary.LittleEndian.Uint16(data[o+4:]),
			}
		}
		out[y] = row
	}
	return out, nil
}
