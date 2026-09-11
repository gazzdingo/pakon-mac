package kcmsclut

import "testing"

// The exhaustive proof that this package is the vendor's arithmetic lives in
// tools/test_kcms_clut_ports.py, which needs Python, numpy and the reference
// module. These tests are what `go test ./...` alone can carry: a set of
// vectors taken from that reference covering all six tetrahedra, and the
// branch-distribution shape.

// vectors are pakon_kcms_clut.evaluate's own outputs — the module that is
// bit-exact against the real kodakcms.dll over the whole u8 domain (docs/74
// §176). Three per tetrahedron plus the corners, so a transcription error in
// any one branch of the six-way sort fails here and not only in the exhaustive
// harness.
var vectors = [][2][3]uint8{
	{{0, 0, 0}, {2, 0, 0}},             // tetra 5
	{{255, 255, 255}, {255, 255, 254}}, // tetra 5
	{{128, 128, 128}, {245, 244, 243}}, // tetra 5
	{{1, 254, 3}, {0, 121, 0}},         // tetra 3
	{{241, 160, 175}, {255, 255, 254}}, // tetra 0
	{{184, 94, 125}, {250, 93, 215}},   // tetra 0
	{{186, 129, 156}, {255, 244, 255}}, // tetra 0
	{{213, 57, 14}, {200, 0, 0}},       // tetra 1
	{{233, 1, 127}, {214, 0, 178}},     // tetra 1
	{{149, 141, 130}, {255, 253, 241}}, // tetra 1
	{{229, 148, 198}, {255, 254, 255}}, // tetra 2
	{{210, 33, 204}, {216, 0, 186}},    // tetra 2
	{{30, 119, 209}, {0, 149, 210}},    // tetra 2
	{{77, 87, 71}, {39, 63, 30}},       // tetra 3
	{{131, 248, 119}, {246, 254, 216}}, // tetra 3
	{{63, 254, 3}, {0, 132, 0}},        // tetra 3
	{{161, 112, 131}, {255, 197, 241}}, // tetra 4
	{{177, 225, 51}, {255, 197, 0}},    // tetra 4
	{{10, 189, 121}, {0, 159, 195}},    // tetra 4
	{{76, 72, 223}, {46, 0, 186}},      // tetra 5
	{{113, 122, 129}, {197, 228, 246}}, // tetra 5
	{{254, 206, 202}, {255, 255, 254}}, // tetra 5
}

func TestEvalU8AgainstReferenceVectors(t *testing.T) {
	if NpzMD5 != "28d5812832f1e5a0a4af4139732c722c" {
		t.Fatalf("tables.go was generated from npz %s, not the capture these "+
			"vectors came from — regenerate and re-run "+
			"tools/test_kcms_clut_ports.py", NpzMD5)
	}
	seen := map[int]bool{}
	for _, v := range vectors {
		got := EvalU8(v[0])
		if got != v[1] {
			t.Errorf("EvalU8(%v) = %v, reference says %v", v[0], got, v[1])
		}
		seen[TetraOf(v[0])] = true
	}
	if len(seen) != 6 {
		t.Errorf("vectors only cover %d of the 6 tetrahedra", len(seen))
	}
}

// TestTetraDistribution walks the whole u8 domain and checks every branch of
// the six-way weight sort is reachable, in the proportions
// pakon_kcms_clut_golden.py reports for the real DLL's own table. A
// transcription that gets a tie the wrong way round changes these.
func TestTetraDistribution(t *testing.T) {
	golden := [6]float64{13.5, 13.7, 19.0, 13.7, 19.0, 21.1}
	var hits [6]int64
	var in [3]uint8
	for r := 0; r < 256; r++ {
		in[0] = uint8(r)
		for g := 0; g < 256; g++ {
			in[1] = uint8(g)
			for b := 0; b < 256; b++ {
				in[2] = uint8(b)
				hits[TetraOf(in)]++
			}
		}
	}
	var total int64
	for i, h := range hits {
		total += h
		pct := 100 * float64(h) / (1 << 24)
		if h == 0 {
			t.Errorf("tetrahedron %d is never reached", i)
		} else if d := pct - golden[i]; d > 0.1 || d < -0.1 {
			t.Errorf("tetrahedron %d takes %.2f%% of the domain, golden says %.1f%%",
				i, pct, golden[i])
		}
	}
	if total != 1<<24 {
		t.Errorf("counted %d inputs, want %d", total, 1<<24)
	}
}

func TestRpd12ToU8(t *testing.T) {
	// clip(rint(code*255/4095), 0, 255), per pakon_ansel.rpd12_to_icc_u8.
	for _, c := range []struct {
		rpd  int
		want uint8
	}{
		{-1, 0}, {0, 0}, {8, 0}, {9, 1}, {741, 46}, {2048, 128},
		{4094, 255}, {4095, 255}, {9999, 255},
	} {
		if got := Rpd12ToU8(c.rpd); got != c.want {
			t.Errorf("Rpd12ToU8(%d) = %d, want %d", c.rpd, got, c.want)
		}
	}
	// monotone, and it must reach both ends
	prev := Rpd12ToU8(0)
	for v := 1; v <= 4095; v++ {
		cur := Rpd12ToU8(v)
		if cur < prev {
			t.Fatalf("Rpd12ToU8 is not monotone at %d: %d then %d", v, prev, cur)
		}
		prev = cur
	}
	if prev != 255 {
		t.Errorf("Rpd12ToU8(4095) = %d, want 255", prev)
	}
}
