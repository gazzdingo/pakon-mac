package vendorinvert

import (
	"math"
	"testing"
)

// TestTableShape pins the table's basic contract.
func TestTableShape(t *testing.T) {
	if Entries != 16384 {
		t.Fatalf("Entries = %d, want 16384", Entries)
	}
	if len(Table) != Entries {
		t.Fatalf("len(Table) = %d, want %d", len(Table), Entries)
	}
	if Max != 16383 {
		t.Fatalf("Max = %d, want 16383", Max)
	}
	for i, v := range Table {
		if int(v) > Max {
			t.Fatalf("Table[%d] = %d exceeds Max %d", i, v, Max)
		}
	}
}

// TestClosedFormIsTheFallbackNotTheSource re-measures the claim docs/74 §173.2
// had to withdraw once already. The closed form was described as "exact to
// rounding"; it is not. It is 87.5 % exact with a maximum error of 1.
//
// This test asserts the SHAPE of that relationship — near, but not equal —
// so that if someone ever replaces the captured table with the formula, the
// substitution is caught rather than inherited silently.
func TestClosedFormIsTheFallbackNotTheSource(t *testing.T) {
	closed := func(i int) int {
		if i <= 0 {
			return Max // log10(0) is -Inf; the table's own entry 0 is 16383
		}
		v := 14750.0 - 3500.0*math.Log10(float64(i))
		r := int(math.Round(v))
		if r < 0 {
			r = 0
		}
		if r > Max {
			r = Max
		}
		return r
	}

	exact, maxErr := 0, 0
	for i := 0; i < Entries; i++ {
		d := int(Table[i]) - closed(i)
		if d < 0 {
			d = -d
		}
		if d == 0 {
			exact++
		}
		if d > maxErr {
			maxErr = d
		}
	}
	pct := 100.0 * float64(exact) / float64(Entries)

	if maxErr > 1 {
		t.Errorf("closed form differs from the captured table by %d; "+
			"docs/74 §173.2 measured a maximum of 1", maxErr)
	}
	if pct < 80.0 || pct > 95.0 {
		t.Errorf("closed form is exact on %.1f %% of entries; §173.2 measured "+
			"~87.5 %%. A large change means the table or the formula moved", pct)
	}
	if exact == Entries {
		t.Error("closed form is exact everywhere — that would mean the " +
			"captured table was replaced by the formula, which is exactly " +
			"the substitution §173.2 warns about")
	}
	t.Logf("closed form: %d/%d exact (%.2f %%), max |err| %d",
		exact, Entries, pct, maxErr)
}

// TestKnownEntries pins values read directly out of the .npy, so a
// regenerate-from-a-different-source is caught.
func TestKnownEntries(t *testing.T) {
	want := map[int]uint16{
		0: 16383, 1: 14750, 2: 13696, 3: 13080, 4: 12643, 5: 12303,
		16383: 0, 16382: 0, 16381: 0, 16380: 0,
	}
	for i, w := range want {
		if Table[i] != w {
			t.Errorf("Table[%d] = %d, want %d", i, Table[i], w)
		}
	}
}

// TestMonotoneNonIncreasing — an inversion of a log curve must never rise.
// docs/74 §F3 records that the curve flattens (many-to-one), which is why the
// table cannot be inverted to recover sensor values; it must still be
// non-increasing.
func TestMonotoneNonIncreasing(t *testing.T) {
	for i := 1; i < Entries; i++ {
		if Table[i] > Table[i-1] {
			t.Fatalf("Table rises at %d: %d -> %d", i, Table[i-1], Table[i])
		}
	}
}
