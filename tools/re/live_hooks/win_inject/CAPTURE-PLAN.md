# The next hardware capture — everything we need, in two scans

Written 2026-08-21. Everything here is built, self-tested and validated on
the build machine; nothing in it has touched the scanner yet.

Read `../README.md` "Running it on the real XP box" for the injector
mechanics. This file is the *plan*: what to capture, in what order, and what
each scan is for.

---

## Why two scans and not one

Cost, not safety. Every address in both configs is a confirmed real function
entry. But `tlb_framing_line_reduce` is per-LINE and the reference trace is
already ~175 MB; there is no reason to pay both at once, and the framing scan
is cheap to repeat if something goes wrong.

Run **framing first**. It closes the last render-affecting gap, it is small,
and it shakes out the injector before the expensive one is committed to.

---

## Before you copy anything

```
cd tools/re/live_hooks/win_inject
bash build.sh                       # must end "OK: 40 hooks ... 40/48 slots"
bash build.sh selftest              # must end "ALL PASS (0 failure(s))"
python3 check_hooks_cfg.py hooks.cfg.framing
python3 check_hooks_cfg.py hooks.cfg.reference
md5 hookdll.dll injector.exe        # hash what you copy — see below
```

`check_hooks_cfg.py` prints exactly which hooks each config will record,
resolving the built-in defaults. **Read that list before the scan, not
after.** A misspelt hook id in `hooks.cfg` is silently ignored on the box;
this project has lost real hardware round trips to that class of thing
(v22/v24/v26 to a derived offset, v41 to a mid-instruction address, §178.1 to
a capture that was still uploading).

**PE headers carry a build timestamp, so these binaries are not reproducible
across rebuilds.** Hash the copies you actually take, not a hash from a
previous session. A stale `hookdll_v46.dll` sitting next to a fresh
`hookdll.dll` has already caused one near-miss here.

---

## Scan 1 — FRAMING  (`hooks.cfg.framing`)

**Records 3 hooks. Expect tens of MB.**

### What it closes

`FRAMING_PORTED` is the **only** flag in the ledger that can affect a render.
The vendor's cascade is already bit-exact — 15 functions, 1,429 checks, up to
and including the entry and its full threshold search (§194). The flag is
False for one reason no further RE can fix:

> the entry consumes the object's **8-bit per-line RGB summary** at
> `this+0x6c`; this port holds **float 14-bit non-inverted**. Guessing that
> quantisation would move every frame boundary *invisibly to the golden*,
> because the golden feeds both sides the same synthetic bytes.

`tlb_framing_line_reduce` is that array's consumer, and at its entry the array
is already filled. One capture settles it.

### Success looks like

* `framing_trace` dump rows present, 6 of them (the row's cap);
* `tlb_framing_entry` entry+exit pairs, with the exit side showing the
  `SCAN_WARNINGS` word set;
* the per-line values are **8-bit and inverted** — i.e. `255 - (r+g+b)/3`.
  If they are not, that is itself the finding, and it changes the port.

---

## Scan 2 — REFERENCE TRACE  (`hooks.cfg.reference`)

**Records 28 hooks. Expect ~175 MB, ~45 MB gzipped.**

### What it is for

**(a) The byte-for-byte reference.** Every colour stage captured at both its
input and its output. This was impossible before v46: `LogExtraDumps` fired on
ENTRY ONLY, and the vendor's chain is a series of *in-place* transforms, so no
stage's output could be seen at all (§189.2).

The centrepiece is the scene struct — **0x64DC (25,820) bytes**, confirmed
three independent ways. One 52 KB dump per side per frame subsumes every
narrow per-frame row, and diffing adjacent stage brackets attributes each
per-frame scalar change to the stage that made it: the measurement §168 could
not make.

**(b) Provenance for B1** — new in v47. `sba_measure` (`fcn.102aece0`) is the
per-sample statistics engine. Its 864-byte mask feeds U and V; its 720-slot
vector is the p-code VM's `in[]`, which reproduces L. Both the mask and the
packer are now ported **bit-exact** — but tier 1 for *equivalence* and tier 4
for *provenance*, because no capture has ever hooked either and their inputs
are synthetic (§196). B1 asks what the real per-frame values are. Only a
capture answers that.

### Success looks like

* `measure_obj_pre` / `measure_obj_post` pairs, 18 of each (3 calls/frame ×
  6 frames);
* in `measure_obj_post`, non-poison bytes at `+0x6..+0x1c`, `+0x3c..+0xb7c`
  and `+0xc20..+0xf80` — the three written extents measured under emulation;
* `scene_in` / `scene_out` at 0x64DC for each frame;
* `check_v46.py` accepting the capture.

### Verify the capture before drawing anything from it

```
python3 ../wine_host/check_v46.py <capture.jsonl>
```

Its strongest tests are cross-row identities that cannot pass by accident —
`lut_dst[i] ∈ lut_table`, `scene_in[0x4b6] == balance_shift_4b6`,
`slb_lut_* == clamp(i + stack_dwords[4..6], 0, 4095)`, same-address/
different-content on the polypixel pair, and no capped row over its cap.

**And check the transfer.** §178.1: a whole analysis was drawn from a capture
that was still uploading — 0.51 GB of 2.47 GB. Compare `Content-Length`
against the file on disk before reading a byte of it.

---

## What each scan cannot give us

Stated here so the trace is not read as complete:

* **A once-per-frame hook on the pre-invert raw plane.** `tlb_lut_apply` is
  per-*strip* — 52,877 calls / 39 frames ≈ 1,356 per frame. `maxDumps` bounds
  the *first* N calls, which all land in frames 0–1; it cannot manufacture
  one-per-frame.
* **The pre-ICC u8 buffer.** `icc_xform_apply` reaches pixels only through
  virtual band accessors, so no static `ExtraDumpSpec` can reach them.
* **The tone LUT as a standalone buffer** — built in callees into
  sub-objects; bracketed by the `tone_scene` entry/exit pair instead.
* **Post-FUGC RPD as a distinct plane** — no hooked function takes it as an
  argument.
* **The fourth `ret` of `sba_measure`** (`0x102b48f3`, the no-samples exit).
  Never reached under emulation across 74 cases; whether a real roll reaches
  it is open.

---

## Safety

Per `CLAUDE.md`: commands that expose or drive film require **explicit
confirmation of the film type physically loaded**. That is by design. Neither
config drives the motor or the lamp by itself — they only observe a scan you
start — but the scan itself does, and the confirmation belongs to the person
at the machine.
