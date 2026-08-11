package main

import "testing"

// FindDmin must see film — not the leader, not the gate edge.
//
// Both halves of this were real, and both were measured. The whole of
// captures/strip_cal.bin's 0.29/0.43/0.35 % of ceiling pixels lived in CCD
// columns 0..45 — pixels below the vendor's own window start of 62 (docs/53
// §3.4), where the unit flat-field gain is 17-24x — and the whole of
// captures/gold400.bin's 6.7 % lived in lines 0..2105, the clear leader. The
// sensor never saturates on strip_cal at all. Neither is over-exposure, and
// neither may reach FindDmin. What must still reach it is film that has
// genuinely clipped.
//
// Mirrors tools/test_render_f135.py:test_film_base_window_is_the_film.

const testNBins = 4096

// buildStrip lays out a (h, w) capture grid, x = CCD pixel: film at code 2500,
// the gate edge at the ceiling, a clear leader at the head, and optionally
// blownCols of highlight clipping across every film line.
func buildStrip(h, w, col0, leaderLines, blownCols int) (r, g, b []int) {
	n := h * w
	r = make([]int, n)
	g = make([]int, n)
	b = make([]int, n)
	for y := 0; y < h; y++ {
		for x := 0; x < w; x++ {
			v := 2500
			switch {
			case x < col0: // gate edge, outside the vendor's CCD window
				v = testNBins - 1
			case y < leaderLines: // clear leader
				v = testNBins - 1
			case x < col0+blownCols: // over-exposed film highlights
				v = testNBins - 1
			}
			i := y*w + x
			r[i], g[i], b[i] = v, v, v
		}
	}
	return r, g, b
}

func TestFilmBaseCol0IsTheVendorWindow(t *testing.T) {
	if got := FilmBaseCol0(DefaultCcdPixelOffset); got != 30 {
		t.Fatalf("FilmBaseCol0(%d) = %d, want 30 (vendor %d - port %d)",
			DefaultCcdPixelOffset, got, VendorCcdPixelOffset, DefaultCcdPixelOffset)
	}
	if got := FilmBaseCol0(VendorCcdPixelOffset); got != 0 {
		t.Fatalf("FilmBaseCol0(%d) = %d, want 0: a capture taken at the "+
			"vendor's own offset has no dead columns to trim",
			VendorCcdPixelOffset, got)
	}
	if got := FilmBaseCol0(0); got != 30 {
		t.Fatalf("FilmBaseCol0(0) = %d, want 30 (unrecorded → this port's %d)",
			got, DefaultCcdPixelOffset)
	}
}

func TestFilmBaseWindowIsTheFilm(t *testing.T) {
	const h, w = 400, 2000
	col0 := FilmBaseCol0(DefaultCcdPixelOffset)
	win := DminWindow{H: h, W: w, Axis: CcdAxisX, Col0: col0}

	r, g, b := buildStrip(h, w, col0, 40, 0)
	base, clip, film, total := FilmBaseFromPlanes(r, g, b, testNBins, win)
	if film != 360 || total != h {
		t.Fatalf("film area = %d/%d lines, want 360/%d", film, total, h)
	}
	for c := 0; c < 3; c++ {
		if base[c] != 2500 {
			t.Fatalf("film base %v is not the film's own 2500 — the leader or "+
				"the gate edge is still in the histogram", base)
		}
		if clip[c] != 0 {
			t.Fatalf("clip[%d] = %g%%, want 0: nothing inside the film area "+
				"is at the ceiling", c, clip[c])
		}
	}
	if err := CheckFilmBase(base, &clip, true); err != nil {
		t.Fatalf("refused a measurable film base: %v", err)
	}

	// …and the refusal still has to fire when the FILM is what clipped.
	// 100 of 1970 aperture columns is 5 %, well over FindDmin's 0.1 %.
	r, g, b = buildStrip(h, w, col0, 40, 100)
	base, clip, _, _ = FilmBaseFromPlanes(r, g, b, testNBins, win)
	if err := CheckFilmBase(base, &clip, true); err == nil {
		t.Fatalf("film clipped over 5 %% of its own area was accepted "+
			"(base %v, clip %v); the refusal has been weakened", base, clip)
	}

	// A saturated line cannot be told from leader, so a capture that is
	// mostly saturated must refuse rather than measure off the remnant.
	r, g, b = buildStrip(h, w, col0, 300, 0)
	base, clip, film, _ = FilmBaseFromPlanes(r, g, b, testNBins, win)
	if err := CheckFilmBase(base, &clip, true); err == nil {
		t.Fatalf("a capture with %d of %d lines of film was accepted "+
			"(base %v); the line test can be used to discard an over-exposed "+
			"capture down to its remnant", film, h, base)
	}
}

// An undeclared CCD axis must fall back to measuring everything, never to
// trimming the wrong axis.
func TestFilmBaseWindowNeedsTheAxisDeclared(t *testing.T) {
	const h, w = 400, 2000
	col0 := FilmBaseCol0(DefaultCcdPixelOffset)
	r, g, b := buildStrip(h, w, col0, 40, 0)

	for _, win := range []DminWindow{
		{H: h, W: w, Axis: CcdAxisUnknown, Col0: col0},
		{H: 1, W: 1, Axis: CcdAxisX, Col0: col0}, // geometry does not match
	} {
		base, _, film, total := FilmBaseFromPlanes(r, g, b, testNBins, win)
		if film != 0 || total != 0 {
			t.Fatalf("%+v: reported a film area (%d/%d) it cannot know",
				win, film, total)
		}
		if base != ([3]int{0, 0, 0}) {
			t.Fatalf("%+v: base %v — an unwindowed walk over this strip has "+
				"the gate edge at the ceiling, so FindDmin's sentinel is the "+
				"only honest answer", win, base)
		}
	}
}

// The y-axis form is the same window, just transposed — a decoded TIFF.
func TestFilmBaseWindowOnTheTiffAxis(t *testing.T) {
	const lines, ccd = 400, 2000
	col0 := FilmBaseCol0(DefaultCcdPixelOffset)
	// (ccd, lines) grid: y = CCD pixel, x = scan line.
	n := ccd * lines
	r := make([]int, n)
	g := make([]int, n)
	b := make([]int, n)
	for y := 0; y < ccd; y++ {
		for x := 0; x < lines; x++ {
			v := 2500
			if y < col0 || x < 40 {
				v = testNBins - 1
			}
			i := y*lines + x
			r[i], g[i], b[i] = v, v, v
		}
	}
	win := DminWindow{H: ccd, W: lines, Axis: CcdAxisY, Col0: col0}
	base, clip, film, total := FilmBaseFromPlanes(r, g, b, testNBins, win)
	if film != 360 || total != lines {
		t.Fatalf("film area = %d/%d lines, want 360/%d", film, total, lines)
	}
	if base != ([3]int{2500, 2500, 2500}) {
		t.Fatalf("film base %v is not 2500 on the TIFF axis (clip %v)", base, clip)
	}
}
