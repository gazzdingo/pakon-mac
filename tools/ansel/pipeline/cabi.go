package main

// The phase-2 boundary: this package as a c-shared dylib, called from Python
// by ctypes.
//
// Why a dylib and not a process
// -----------------------------
// docs/62 §3.2 measured all three options on this machine. A ctypes call into
// Go costs 2.8 µs. A process spawn costs 6.6 ms, and a framed request/response
// over pipes costs a further 16 ms at display size and 54 ms at full — per
// render, every render, on every slider nudge. The repo already loads two
// Go/C shared libraries this way (tools/libpakon_color.dylib from
// tools/pakon_color.py, tools/ansel/python-pipeline/libpakon_ansel.dylib from
// pakon_sba_apply.py), so the numpy-buffer ABI and the path resolution are
// solved problems here and a process boundary would be a new architecture.
//
// The owner's product rule — one image per frame, no intermediates — rules out
// the current hand-off anyway: main.go used to take <input.tiff> and write two
// PNGs, and tools/pakon_decode.py:write_tiff16 unsquashes and rotates before
// writing, so the TIFF path had Go's colour maths running on resampled pixels
// while Python's ran on the raw grid (docs/62 §3.1). Here the 14-bit frame
// crosses in memory, on the capture's own grid, and nothing is written.
//
// Why JSON and not a C struct
// ---------------------------
// docs/62 §3.4 sketched a versioned C struct. A struct has to be declared
// twice — once in Go, once in ctypes — and the two drift silently, which is
// the exact failure mode this whole document is about. RenderRequest already
// has twenty fields including a provenance map. So the request crosses as
// UTF-8 JSON with an explicit "abi" word, parsed by encoding/json on this side
// and dataclasses.asdict on the other. Measured cost of the marshal + parse is
// under 50 µs against a 100 ms+ render; the field-drift it removes is worth
// more than that. Everything else in §3.4 stands: one entry point, no hidden
// state, no defaults, errors as data.
//
// Errors are data
// ---------------
// Every entry point returns a negative code and writes a JSON object into the
// caller's msg buffer. Nothing is scraped from stderr and nothing is inferred
// from an exit status. Go now refuses rather than guesses — no film base, no
// film class, no stock — and those refusals have to reach the operator as
// readable prose, so the object carries {code, kind, message} and the Python
// side raises it as a typed exception the frame endpoint turns into JSON for
// api.frameError.
//
// Crash domain
// ------------
// docs/62 §3.3 states the cost plainly: in-process, a Go panic takes the
// backend down, where a subprocess would have contained it. Every exported
// function below therefore recovers, and returns ErrInternal with the panic
// text and stack in msg. A panic must never cross the FFI line — the compiler
// will not enforce that, so it is enforced here, in one place, by construction:
// no exported function has a body other than a deferred recover plus a call
// into an unexported one.

/*
#include <stdint.h>
*/
import "C"

import (
	"encoding/json"
	"fmt"
	"image"
	"os"
	"runtime/debug"
	"runtime/pprof"
	"strconv"
	"strings"
	"sync"
	"unsafe"
)

// AbiVersion is bumped whenever the JSON request shape or the buffer contract
// changes in a way an old caller would get wrong. The Python side sends it and
// this side refuses a mismatch rather than reading a field that has moved.
const AbiVersion = 1

// Return codes. Negative on failure, and the caller must treat any negative as
// "no image was produced" — the out buffer is never partially written.
const (
	rcOK       = 0
	rcRequest  = -1 // malformed JSON, or an ABI version this build does not speak
	rcRefused  = -2 // a refusal: no film base, no film class, no stock. Operator-fixable
	rcLoad     = -3 // vendor data missing or unparseable
	rcBuffer   = -4 // null pointer or a size the buffers cannot hold
	rcInternal = -5 // a recovered panic
)

// abiRequest is the whole wire form. The request itself is RenderRequest, so
// there is exactly one definition of the fields on this side.
type abiRequest struct {
	Abi       int            `json:"abi"`
	Fx35Root  string         `json:"fx35Root"`
	AnselRoot string         `json:"anselRoot"`
	Request   *RenderRequest `json:"request"`
}

// abiError is what lands in the caller's msg buffer on every non-zero return,
// and on success carries the log and the resolved selection.
type abiError struct {
	Code    int               `json:"code"`
	Kind    string            `json:"kind"`
	Message string            `json:"message"`
	Log     string            `json:"log,omitempty"`
	Stack   string            `json:"stack,omitempty"`
	Resolve map[string]string `json:"resolved,omitempty"`
}

var (
	mu     sync.Mutex
	cached *Engine
)

func init() {
	// docs/62 §3.3: Go's runtime now lives inside the Python process and
	// shares a heap with a ThreadingHTTPServer. Left alone, GOGC=100 lets the
	// render's float64 intermediates double the RSS of the whole backend
	// before a collection. These are overridable rather than fixed because
	// the right number depends on the machine, but there is a stated default
	// instead of an accident.
	if v := os.Getenv("PAKON_GO_GC_PERCENT"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			debug.SetGCPercent(n)
		}
	} else {
		debug.SetGCPercent(40)
	}
	if v := os.Getenv("PAKON_GO_MEMLIMIT"); v != "" {
		if n, err := strconv.ParseInt(v, 10, 64); err == nil {
			debug.SetMemoryLimit(n)
		}
	}
	// A slider drag is dozens of renders, so where the milliseconds go is a
	// standing question rather than a one-off investigation. PAKON_GO_CPUPROFILE
	// names a file; PakonColorClose stops the profile. Off unless asked.
	if v := os.Getenv("PAKON_GO_CPUPROFILE"); v != "" {
		if f, err := os.Create(v); err == nil {
			profileFile = f
			_ = pprof.StartCPUProfile(f)
		}
	}
}

var profileFile *os.File

// writeMsg copies s into the caller's NUL-terminated buffer, truncating rather
// than overrunning. A truncated explanation is a bug report; an overrun is a
// crash in someone else's process.
func writeMsg(msg *C.char, msgLen C.int32_t, s string) {
	if msg == nil || msgLen <= 1 {
		return
	}
	buf := unsafe.Slice((*byte)(unsafe.Pointer(msg)), int(msgLen))
	n := copy(buf[:len(buf)-1], s)
	buf[n] = 0
}

func writeErr(msg *C.char, msgLen C.int32_t, code int, kind, format string, a ...any) C.int32_t {
	e := abiError{Code: code, Kind: kind, Message: fmt.Sprintf(format, a...)}
	b, err := json.Marshal(&e)
	if err != nil {
		writeMsg(msg, msgLen, `{"code":-5,"kind":"internal","message":"error marshal failed"}`)
		return C.int32_t(rcInternal)
	}
	writeMsg(msg, msgLen, string(b))
	return C.int32_t(code)
}

func writeOK(msg *C.char, msgLen C.int32_t, log string, resolved map[string]string) C.int32_t {
	e := abiError{Code: rcOK, Kind: "ok", Message: "", Log: log, Resolve: resolved}
	if b, err := json.Marshal(&e); err == nil {
		writeMsg(msg, msgLen, string(b))
	}
	return rcOK
}

// parseRequest is the shared front door: decode, check the ABI word, run every
// refusal that does not need pixels.
func parseRequest(reqJSON *C.char) (*abiRequest, int, string) {
	if reqJSON == nil {
		return nil, rcRequest, "no request: reqJSON was NULL"
	}
	raw := C.GoString(reqJSON)
	var ar abiRequest
	if err := json.Unmarshal([]byte(raw), &ar); err != nil {
		return nil, rcRequest, fmt.Sprintf("request JSON: %v", err)
	}
	if ar.Abi != AbiVersion {
		return nil, rcRequest, fmt.Sprintf(
			"ABI %d, but this build speaks %d. The dylib and tools/pakon_colour_go.py "+
				"are out of step — rebuild with tools/build-native.sh.", ar.Abi, AbiVersion)
	}
	if ar.Request == nil {
		return nil, rcRequest, "request JSON has no \"request\" object"
	}
	if ar.AnselRoot == "" {
		return nil, rcRequest, "no anselRoot: the caller must name the " +
			"anselinstalldir/dataPathItems directory. This will not guess one."
	}
	if err := ar.Request.Validate(); err != nil {
		return nil, rcRefused, err.Error()
	}
	return &ar, rcOK, ""
}

// engineFor returns the warm Engine for this selection, loading it if the
// selection changed. Holding one is what makes a slider drag cheap: the tables
// cost 10-30 ms to read and none of the interactive parameters (film base,
// stage order, ICC depth, FUGC mode, deskew) are in the key.
func engineFor(ar *abiRequest) (*Engine, error) {
	if cached != nil && cached.Matches(ar.Fx35Root, ar.AnselRoot, ar.Request) {
		return cached, nil
	}
	eng, err := OpenEngine(ar.Fx35Root, ar.AnselRoot, ar.Request)
	if err != nil {
		return nil, err
	}
	cached = eng
	return eng, nil
}

//export PakonColorAbiVersion
func PakonColorAbiVersion() C.int32_t { return C.int32_t(AbiVersion) }

//export PakonColorOpen
func PakonColorOpen(reqJSON *C.char, msg *C.char, msgLen C.int32_t) (rc C.int32_t) {
	defer func() {
		if r := recover(); r != nil {
			rc = writeErr(msg, msgLen, rcInternal, "internal",
				"panic in PakonColorOpen: %v\n%s", r, debug.Stack())
		}
	}()
	mu.Lock()
	defer mu.Unlock()
	return pakonColorOpen(reqJSON, msg, msgLen)
}

func pakonColorOpen(reqJSON *C.char, msg *C.char, msgLen C.int32_t) C.int32_t {
	ar, code, why := parseRequest(reqJSON)
	if code != rcOK {
		return writeErr(msg, msgLen, code, kindOf(code), "%s", why)
	}
	eng, err := engineFor(ar)
	if err != nil {
		return writeErr(msg, msgLen, rcLoad, "load", "%v", err)
	}
	return writeOK(msg, msgLen, eng.ResolutionLines(), eng.Resolution())
}

//export PakonColorRender
func PakonColorRender(reqJSON *C.char, in *C.uint16_t, h, w C.int32_t,
	out *C.uint8_t, msg *C.char, msgLen C.int32_t) (rc C.int32_t) {
	defer func() {
		if r := recover(); r != nil {
			rc = writeErr(msg, msgLen, rcInternal, "internal",
				"panic in PakonColorRender: %v\n%s", r, debug.Stack())
		}
	}()
	mu.Lock()
	defer mu.Unlock()
	return pakonColorRender(reqJSON, in, h, w, out, msg, msgLen)
}

func pakonColorRender(reqJSON *C.char, in *C.uint16_t, h, w C.int32_t,
	out *C.uint8_t, msg *C.char, msgLen C.int32_t) C.int32_t {

	if in == nil || out == nil {
		return writeErr(msg, msgLen, rcBuffer, "buffer",
			"null buffer: in=%v out=%v", in != nil, out != nil)
	}
	if h <= 0 || w <= 0 {
		return writeErr(msg, msgLen, rcBuffer, "buffer",
			"frame is %dx%d; both dimensions must be positive", int(w), int(h))
	}
	ar, code, why := parseRequest(reqJSON)
	if code != rcOK {
		return writeErr(msg, msgLen, code, kindOf(code), "%s", why)
	}
	eng, err := engineFor(ar)
	if err != nil {
		return writeErr(msg, msgLen, rcLoad, "load", "%v", err)
	}

	height, width := int(h), int(w)
	n := height * width * 3
	src := unsafe.Slice((*uint16)(unsafe.Pointer(in)), n)

	// The 14-bit calibrated frame, on the capture's own grid, before
	// unsquash_transport and before rot90. Nothing here resamples it — the
	// boundary is structurally unable to (docs/62 §9): there is no scale
	// field on this call and the output is the same h×w as the input.
	fr := &frame{h: height, w: width, px: make([][][3]int, height)}
	for y := 0; y < height; y++ {
		row := make([][3]int, width)
		base := y * width * 3
		for x := 0; x < width; x++ {
			i := base + x*3
			row[x] = [3]int{int(src[i]), int(src[i+1]), int(src[i+2])}
		}
		fr.px[y] = row
	}

	var log strings.Builder
	logf := func(format string, a ...any) { fmt.Fprintf(&log, format, a...) }

	// A dylib writes no files. WriteBypass is the CLI's debug affordance and
	// asking for it here is a caller bug, not a silently-ignored flag.
	if ar.Request.WriteBypass {
		return writeErr(msg, msgLen, rcRequest, "request",
			"writeBypass is not available across the dylib boundary: one image "+
				"per frame, no intermediates. Use the pakonpipeline CLI for a "+
				"bypass PNG.")
	}

	dst := unsafe.Slice((*uint8)(unsafe.Pointer(out)), n)
	emit := func(img, bypass *image.RGBA) error {
		if bypass != nil {
			return fmt.Errorf("internal: bypass image produced across the dylib boundary")
		}
		b := img.Bounds()
		if b.Dx() != width || b.Dy() != height {
			return fmt.Errorf("internal: rendered %dx%d for a %dx%d frame",
				b.Dx(), b.Dy(), width, height)
		}
		for y := 0; y < height; y++ {
			for x := 0; x < width; x++ {
				o := img.PixOffset(x, y)
				i := (y*width + x) * 3
				dst[i] = img.Pix[o]
				dst[i+1] = img.Pix[o+1]
				dst[i+2] = img.Pix[o+2]
			}
		}
		return nil
	}

	if err := processImage(fr, ar.Request, eng, logf, emit); err != nil {
		return writeErr(msg, msgLen, rcRefused, "render", "%v", err)
	}
	return writeOK(msg, msgLen, log.String(), eng.Resolution())
}

//export PakonColorClose
func PakonColorClose() {
	defer func() { _ = recover() }()
	mu.Lock()
	defer mu.Unlock()
	cached = nil
	if profileFile != nil {
		pprof.StopCPUProfile()
		_ = profileFile.Close()
		profileFile = nil
	}
}

func kindOf(code int) string {
	switch code {
	case rcRequest:
		return "request"
	case rcRefused:
		return "refused"
	case rcLoad:
		return "load"
	case rcBuffer:
		return "buffer"
	case rcInternal:
		return "internal"
	}
	return "ok"
}
