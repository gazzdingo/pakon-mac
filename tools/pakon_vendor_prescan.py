"""Vendor pre-scan bring-up `f`, ported exactly from TLB.dll — pure functions.

md5 of the source binary: TLB.dll `193d9b2ce0a4b77ae9b78262bd06c0fc`
(F-135, `/Users/guy/pakon-windows-repair/COM-SERVER/TLB.dll`). Every constant
here was read out of that binary; every arithmetic rule was recovered by
tier-3 static `af`+`pdf` disassembly and cross-checked against the tier-2 live
captures docs/55 (CCD/AFE) and docs/59 (light board).

WHAT THIS IS
------------
PSI runs two adaptive loops during every scan's bring-up: the AFE dark-offset
convergence (docs/55 steps 19-34) and the LED duty / white-balance search
(docs/59). Each is a DETERMINISTIC function of (current register state, sensor
read-back): `next_write = f(state, reading)`. This module is `f`, and only `f`
— the exact update rules, the exact rounding, the 9-bit sign-magnitude
encoding, the convergence windows, the iteration caps.

WHAT THIS IS *NOT*
------------------
* It is NOT wired into `pakon_scan.run_scan`. Importing this module changes
  nothing about the default scan path (which replays stored calibration).
* It drives NO hardware and reads NO hardware. The read-backs are inputs the
  caller supplies. A real integration would feed it EP-0x86 line data.
* Its adaptive loops are NOT bit-exact-validated. docs/55 + docs/59 captured
  only the vendor's *writes* (they hooked `DeviceIoControl`); the *read-backs*
  that drove each step flow over `ReadFile`/EP 0x86 and were never captured.
  The `--selftest` below reproduces docs/55's nine offset WORDS bit-exact
  (that part is proven), and demonstrates forward *consistency* against docs/55's
  offset trajectory — a consistency demo, explicitly NOT a validation, because
  a single trajectory does not pin `f` (round 2 lands the sensor on its floor;
  many rules fit the same three writes).

GATING
------
Nothing here executes on import. A caller that wants the ported bring-up must
opt in with the env flag, e.g.::

    import os
    if os.environ.get("PAKON_VENDOR_PRESCAN") == "1":
        from pakon_vendor_prescan import ...

so `PAKON_VENDOR_PRESCAN` defaults OFF and the flag name is discoverable.

TIER: tier-3 static (TLB.dll `af`+`pdf`) + tier-2 docs/55/59. NOT hardware.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


# ==========================================================================
# AFE dark-offset convergence  --  FN_bCalibrateFindDarkOffset  fcn.1001e1c0
# ==========================================================================
#
# Register write primitive: FN_bDrvPutCcdAtoDOffsets @ 0x100299c0
#   reg 0x84, idx (5,6,7) for (R,G,B).
# Update constants (raw .rdata doubles):
#   target black  0x10065c88 = 0x4072c00000000000 = 300.0
#   gain          0x10065c80 = 0xbf8b6db6db6db6db = -0.013392857142857142
#                 the code multiplies by 2*gain = -0.0267857... = -3/112
#   window ±32 -> [268, 332]   (FN 0x1001ce50, args black,300,32,32)
#   seed +10, iteration cap 8.

AFE_TARGET_BLACK = 300.0
AFE_UPDATE_GAIN = -0.013392857142857142          # 0x10065c80
AFE_WINDOW_LO = 268                              # 300 - 32
AFE_WINDOW_HI = 332                              # 300 + 32
AFE_SEED = (10, 10, 10)
AFE_MAX_ROUNDS = 8

ADC_OFFSET_MAX = 255
ADC_OFFSET_SIGN = 0x100                          # bit 8 = sign
AFE_OFFSET_IDX = (5, 6, 7)                       # reg 0x84 idx for R,G,B
AFE_REG = 0x84


def _round_ties_away(x: float) -> int:
    """fcn.10048e9c: round-to-nearest, ties away from zero (MSVC ftol-style)."""
    return int(math.floor(x + 0.5)) if x >= 0.0 else int(math.ceil(x - 0.5))


def afe_offset_word_vendor(v: int) -> int:
    """Encode a signed AFE offset EXACTLY as FN_bDrvPutCcdAtoDOffsets does.

    fcn.100299c0 @ 0x100299dc..0x100299fc:
        if v <= -255: v = -255      # CLAMP (jle -> mov edi,0xffffff01), NOT an error
        if v >=  255: v =  255      # CLAMP
        word = abs(v) | (0x100 if v < 0 else 0)   # 9-bit sign-magnitude

    NOTE this differs from `pakon_commands.afe_offset_word`, which RAISES at
    v <= -255. The vendor clamps. Both agree everywhere in (-255, 255), which
    is the only range real offsets occupy, so the live path is unaffected; this
    version is the faithful one for a byte-exact replay at the clamp edge.
    """
    v = int(v)
    if v <= -ADC_OFFSET_MAX:
        v = -ADC_OFFSET_MAX
    elif v >= ADC_OFFSET_MAX:
        v = ADC_OFFSET_MAX
    return abs(v) | (ADC_OFFSET_SIGN if v < 0 else 0)


def afe_offset_converged(black: float) -> bool:
    """fcn.1001ce50(black, 300, 32, 32): True iff 268 <= black <= 332."""
    return AFE_WINDOW_LO <= black <= AFE_WINDOW_HI


def afe_offset_next(offset: int, black: float) -> int:
    """The vendor proportional update: offset += round((black-300)*2*gain).

    `black` MUST be on the vendor's own scale — the windowed mean produced by
    fcn.1001d4c0 (round(sum(window)/(count*32)), samples unsigned), where the
    target is 300 — NOT a decoded 14-bit wire count. See afe_black_scalar().
    """
    delta = _round_ties_away((float(black) - AFE_TARGET_BLACK) * 2.0
                             * AFE_UPDATE_GAIN)
    return int(offset) + delta


def afe_black_scalar(samples, scale: int = 32) -> int:
    """fcn.1001d4c0: round(sum(samples)/(len(samples)*scale)), unsigned.

    `samples` is one channel's window of the (line-averaged) dark line. The
    vendor treats each 32-bit sample as unsigned; on a real EP-0x86 14-bit
    line the high bits are clear so this is a plain mean/scale. Provided so a
    caller reduces a captured line to the SAME scalar the vendor compares to
    300 — the piece that makes the update rule reproducible.
    """
    s = 0
    n = 0
    for v in samples:
        iv = int(v)
        if iv < 0:
            iv += 1 << 32
        s += iv
        n += 1
    if n == 0:
        return 0
    return _round_ties_away(s / (n * scale))


# ==========================================================================
# LED duty / white-balance search -- FN_bCalibrateFindLedDutyCycle fcn.1001ec90
# ==========================================================================
#
# VA 0x1001ec90. Writes duty via FN_bDrvLampOn (fcn.1002c5f0).
# Per channel, each of up to 32 iterations:
#   peak = max(line[channel] over window)
#   if window_lo <= peak <= window_hi:  converged
#   elif peak == last or peak == last2: converged   (stuck / oscillation guard)
#   else:
#       duty = duty*2                if peak == 0
#       duty = duty*TARGET/peak      otherwise
#       clamp duty <= 1.0
# Visible R/G/B: window [63936,64000], TARGET 63968 (centre)  0x10065d50
# Ir:            window [39936,40000], TARGET 39968 (centre)  0x10065d40
# clamp eps 0.001 (0x10065d48). Channel order on the wire is B,Ir,R,-,G (docs/59).

LED_TARGET_VIS = 63968.0                          # 0x10065d50, centre of window
LED_WINDOW_VIS = (63936, 64000)                   # 0xf9c0 .. 0xfa00
LED_TARGET_IR = 39968.0                           # 0x10065d40
LED_WINDOW_IR = (39936, 40000)                    # 0x9c00 .. 0x9c40
LED_MAX_ROUNDS = 32
LED_DUTY_MAX = 1.0


def _led_window(channel: str):
    return LED_WINDOW_IR if channel.lower() == "ir" else LED_WINDOW_VIS


def _led_target(channel: str) -> float:
    return LED_TARGET_IR if channel.lower() == "ir" else LED_TARGET_VIS


def led_duty_converged(peak: int, channel: str = "vis") -> bool:
    lo, hi = _led_window(channel)
    return lo <= peak <= hi


def led_duty_next(duty: float, peak: int, channel: str = "vis") -> float:
    """new_duty = clamp(old_duty * TARGET / peak, <= 1.0); peak==0 -> *2."""
    if peak == 0:
        nd = duty * 2.0
    else:
        nd = duty * _led_target(channel) / float(peak)
    return LED_DUTY_MAX if nd >= LED_DUTY_MAX else nd


@dataclass
class DutyChannelState:
    """Per-channel state for the ratiometric search, incl. the stuck guard."""
    channel: str = "vis"
    duty: float = 0.0
    converged: bool = False
    last_peak: int | None = None
    last2_peak: int | None = None

    def step(self, peak: int) -> float:
        """Consume a measured peak, return the next duty to write."""
        if self.converged:
            return self.duty
        if led_duty_converged(peak, self.channel):
            self.converged = True
        elif peak == self.last_peak or peak == self.last2_peak:
            self.converged = True            # oscillation / can't hit target
        else:
            self.duty = led_duty_next(self.duty, peak, self.channel)
        self.last2_peak = self.last_peak
        self.last_peak = peak
        return self.duty


# ==========================================================================
# Write-stream helper: turn a stream of readings into the packet stream PSI
# would emit, including write-on-change on the offset registers.
# ==========================================================================

@dataclass
class OffsetConvergence:
    """Reproduce FN_bCalibrateFindDarkOffset's emitted 0x84 idx5/6/7 stream.

    Feed it, per round, the three per-channel black scalars (already on the
    vendor scale, e.g. via `afe_black_scalar`). It yields the exact (idx, word)
    writes PSI would put on the wire, skipping unchanged channels
    (write-on-change) and stopping each channel at the 268..332 window.
    """
    offset: list = field(default_factory=lambda: list(AFE_SEED))
    stored: list = field(default_factory=lambda: [None, None, None])
    converged: list = field(default_factory=lambda: [False, False, False])
    round: int = 0

    def all_converged(self) -> bool:
        return all(self.converged)

    def emit(self):
        """Return the list of (idx, word) writes for the CURRENT offsets,
        applying write-on-change (matches fcn.100299c0's `cmp;je` skip)."""
        writes = []
        for c in range(3):
            v = self.offset[c]
            if self.stored[c] == v:
                continue
            # clamp exactly as the encoder does before compare-store
            cv = max(-ADC_OFFSET_MAX, min(ADC_OFFSET_MAX, v))
            writes.append((AFE_OFFSET_IDX[c], afe_offset_word_vendor(cv)))
            self.stored[c] = cv
        return writes

    def observe(self, blacks) -> None:
        """Consume this round's three black scalars, update offsets/flags."""
        self.round += 1
        for c in range(3):
            if self.converged[c]:
                continue
            b = blacks[c]
            if afe_offset_converged(b):
                self.converged[c] = True
            else:
                self.offset[c] = afe_offset_next(self.offset[c], b)


# ==========================================================================
# Self-test: bit-exact encoding vs docs/55, + forward consistency demo.
# ==========================================================================

def _selftest() -> int:
    ok = True

    # (1) Encoding: bit-exact vs docs/55's captured wire words. PROVEN.
    cases = [(10, 0x00A), (-29, 0x11D), (-38, 0x126), (-30, 0x11E),
             (-21, 0x115), (-22, 0x116), (-19, 0x113), (-25, 0x119),
             (-26, 0x11A)]
    print("[1] offset encoding vs docs/55 (bit-exact, PROVEN):")
    for v, w in cases:
        got = afe_offset_word_vendor(v)
        flag = "ok" if got == w else "MISMATCH"
        ok &= got == w
        print(f"    {v:>4} -> 0x{got:03X}  (docs55 0x{w:03X})  {flag}")

    # (2) Clamp, not raise, at the edge (differs from pc.afe_offset_word).
    print("[2] clamp at the edge (vendor clamps, does not raise):")
    for v, w in [(-255, 0x1FF), (-300, 0x1FF), (255, 0x0FF), (400, 0x0FF)]:
        got = afe_offset_word_vendor(v)
        ok &= got == w
        print(f"    {v:>5} -> 0x{got:03X}  (expect 0x{w:03X})  "
              f"{'ok' if got == w else 'MISMATCH'}")

    # (3) Convergence window.
    print("[3] convergence window 268..332:")
    for b, exp in [(267, False), (268, True), (300, True), (332, True),
                   (333, False)]:
        got = afe_offset_converged(b)
        ok &= got == exp
        print(f"    black {b}: converged={got}  {'ok' if got == exp else 'BAD'}")

    # (4) Forward consistency demo (NOT a validation). Feed the loop the black
    #     levels implied by docs/55's own trajectory and show it re-emits the
    #     captured writes. The readings are BACKED OUT of the writes, so this is
    #     circular by construction -- it demonstrates the rule is self-consistent
    #     with the trace, it does NOT prove the rule, because the real readings
    #     were never captured (they flow over EP 0x86, not DeviceIoControl).
    print("[4] forward consistency demo vs docs/55 trajectory "
          "(NOT a validation -- readings are reverse-engineered):")
    # Per-round, per-channel black scalars chosen inside each implied band so
    # afe_offset_next reproduces docs/55 R,G,B = 10 -> -29/-38/-30 -> -21/-30/-22
    # -> -19/-25/-19 -> (G only) -26.
    rounds_black = [
        (1756, 2092, 1793),   # round1: +10 -> -29/-38/-30
        (0, 0, 0),            # round2: -29/-38/-30 -> -21/-30/-22 (floored/overshoot)
        (225, 113, 188),      # round3: -21/-30/-22 -> -19/-25/-19
        (300, 337, 300),      # round4: only G (337>332) moves -25 -> -26; R,B in-window
    ]
    conv = OffsetConvergence()
    all_writes = []
    for rb in rounds_black:
        if conv.all_converged():
            break
        w = conv.emit()
        all_writes.append(w)
        conv.observe(rb)
    # final emit for any last change
    all_writes.append(conv.emit())
    for i, w in enumerate(all_writes, 1):
        pretty = ", ".join(f"idx{idx}=0x{word:03X}" for idx, word in w)
        print(f"    emit {i}: {pretty or '(nothing changed)'}")
    print(f"    final offsets R,G,B = {conv.offset}  (docs/55 converged "
          f"-19,-26,-19)")
    ok &= conv.offset == [-19, -26, -19]

    # (5) LED duty ratiometric rule sanity.
    print("[5] led_duty_next ratiometric (target 63968):")
    for duty, peak, exp_more in [(0.5, 32000, True), (0.5, 63968, False)]:
        nd = led_duty_next(duty, peak, "vis")
        print(f"    duty {duty} peak {peak} -> {nd:.5f}")
    ok &= led_duty_converged(63968, "vis")
    ok &= not led_duty_converged(60000, "vis")
    ok &= led_duty_converged(39968, "ir")

    print("\nSELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    print(__doc__)
    print("Run with --selftest to check the ported constants and encoding.")
