#!/usr/bin/env python3
"""Roll-level Ansel analyze — call-graph catalog + verified fragments.

Pakon-only: cite ``PakonIMAu.dll`` / ``TLA.dll``. Do **not** invent roll
balance, FPO, or Preference maths. ``ANALYSE_ROLL_PORTED = False``.

VERIFIED call graph (image base ``0x10000000``)
==============================================

TLA jump table (loader ``TLA.dll`` ~``0x100179be``)
--------------------------------------------------
``GetProcAddress`` stores (this = loader object ``esi``):

* ``PIAnselEndRoll`` → ``esi+0x58``
* ``PIAnselAnalyzeRoll`` → ``esi+0x5c``
* ``PIAnselAnalyzeScene`` → ``esi+0x60``
* ``PIAnselColorSceneBalancePlanar`` → ``esi+0x64``

Host roll sequence (docs/11): StartNewRoll → AddScene* → EndRoll →
**AnalyzeRoll** → per-scene **ColorSceneBalancePlanar**.

``CiColorCorrectionAnsel::AnalyzeRoll`` @ ``0x10002843``
-------------------------------------------------------
* String ``0x10573acc``; find order ``0x10006090``.
* On success: ``call 0x10020100`` with order object (``ebx+0xc``).

``0x10020100`` → ``AnsOrder::analyzeOrder`` @ ``0x1001fc30``
-------------------------------------------------------------
* Thin wrapper: ``analyzeOrder(order, 0, 0)``.
* Sole ``E8`` site into ``0x1001fc30`` is ``0x10020113``.
* ``AnsOrder::analyzeOrder`` requires ``endOfOrder`` (error string
  ``0x10576740``); success path ``call dword [edx+8]`` (path virtual)
  then further order glue — dispatches into CN-Premium.

``AnsCnPremiumPath::CnPremium_analyzeOrderWide`` @ ``0x10059d90``
----------------------------------------------------------------
* String ``0x1057a5e0``; source ``CN-Premium.cpp``.
* Direct ``E8`` callers include ``0x1005a7ab``, ``0x1005b05c``.
* Order-stage ``E8`` sequence inside OrderWide (partial, cited):

  1. ``0x100fad90`` — ``ColorNegativePath::analyzeAneOrder`` (also
     hosts ``analyzeAsea`` string in same span)
  2. ``0x100d46a0`` — ``pathUtils.cpp`` helper
  3. ``0x100da770`` — (no name string in first 0x300 B)
  4. ``0x100f8620`` — ``ColorNegativePath::getCnContext``
  5. ``0x100fcd70`` — ``analyzeBalance`` / ``analyzePreBalance``
  6. ``0x10059d00`` — (no name string in first 0x300 B)
  7. ``0x100d8d40`` — ``AnsImageData`` metric dump helpers
  8. ``0x10101220`` — ``analyzeBalanceOrder`` (first)
  9. ``0x100fd190`` — ``analyzeScpLutBalance``
  10. ``0x10101220`` — ``analyzeBalanceOrder`` (second)

``ColorNegativePath::analyzeBalanceOrder`` @ ``0x10101220``
----------------------------------------------------------
* String ``0x10586d3c``; ends before ``balanceAreaImage`` (~``0x10102b20``).
* Stack flag selects names ``"sba"``/``"fos"`` vs ``afterSCPLutSba``/
  ``afterSCPLutFos``.
* Scene list from arg object ``[+4,+8)``; walks with stride ``0x64dc``;
  cursor uses field ``+0x4ba`` (same cluster as FUGC aim words).
* Cap lookup ``0x10020a40`` (path map ``+0x6028``).

Per-scene sequence (VERIFIED call order):

1. ``analyzePass1`` @ ``0x10123980`` (SBA)
2. ``AnsFosCapability::analyze`` @ ``0x1013cb30`` → Impl
   ``0x1023ff80`` → ``SbaCalcFosResults`` @ ``0x1028f570``
   (OUT ``Impl+0x18``; see ``pakon_fos.py`` / ``docs/47``)
3. ``analyzePass2`` @ ``0x10123cc0`` (SBA; runs Preference →
   ``scene+0x3a38`` — **blocked** on nested ``+0x4d0e`` writer;
   FOS does not fill that RGB)
4. ``ColorNegativePath::setShifts`` @ ``0x10100260`` — **consumes**
   shifts via ``getShifts``; writes **OUT** triple (not ``+0x3a38``)
5. ``getShifts`` @ ``0x10124000`` again; **adds** 3×int16 into an
   order-side accumulation buffer at ``[ptr-4]/[ptr-2]/[ptr]``
6. ``0x10199680`` (``minArea4BaseWidth/Height`` strings)

Also: ``AnsSceneContext::find`` @ ``0x10022a40``. Maths of pass1/FOS/
pass2 / accumulation: **UNKNOWN**.

``ColorNegativePath::setShifts`` @ ``0x10100260`` (VERIFIED I/O)
---------------------------------------------------------------
* Call @ ``0x10101f89``; arg4 QI → **``AnsSCPLutCapability``**.
* ``0x10122a70``: ``*(SCPLutCap+0x10)+0x18`` → ``0x10122190`` copy.
* Control words = SCPLut DPI ``ntdChoice``/``ctdChoice`` at ``+0x38``/
  ``+0x3a`` (dump ``0x101d0050``). Shipped CN dpi → **``(1, 2)``**.
* ``(0,0)`` passthrough A; ``(2,2)`` passthrough B; ``(1,2)`` DLL-golden
  (``docs/52`` / ``SETSHIFTS_12_PORTED``). A≡B (same Sba Cap);
  OUT → ``scene+0x4b6``.
* **Does not** store ``scene+0x3a38``. Preference still produces
  ``+0x3a38``; ``PREFERENCE_SHIFTS_PORTED=True`` (hi=``0x10``; ``hi≠0x10`` open).

Other ``E8`` into balanceOrder: ``0x1005f491``, ``0x10063c5b``,
``0x10069139``, ``0x10069921``.

``ColorNegativePath::analyzeAneOrder`` @ ``0x100fad90`` (OrderWide)
------------------------------------------------------------------
* Sole Cap call ``0x100faf90`` → ``AnsAneOrderCapability::analyze`` @
  ``0x10110540`` → Impl ``0x101ed3a0``. See ``pakon_ane_order.py``.
* ``getResults`` consumed by ``NoiseMethods::getNoiseTable``
  (``0x10112980`` @ ``0x10112aab`` → CnPremium mid-aim) and
  ``exportNoise``. **Not** balanceOrder / PreBalance / ScpLut →
  SBA/FOS/``+0x3a38``. Layout ported; dens fill
  ``ANE_ORDER_PORTED=False`` (see ``pakon_ane_order.py``).
* ``OrderOrientation`` Cap ``0x101218c0`` is **not** in this function —
  called from ``analyzeAttributes`` (``0x100fb576``).

Per-scene path (SceneSpecific — not OrderWide)
----------------------------------------------
``CnPremium_analyzeSceneSpecific`` @ ``0x10054800``. Includes
``analyzeFugc``, Shasta, falloff, area, attributes, sharpening, …
(``analyzeArea`` ``&+0x4b6`` out-arg @ ``0x10055fd8`` is **after**
``analyzeFugc`` on that path).

FUGC aim fields — static writer WALL
------------------------------------
Pointers (VERIFIED): ``analyzeFugc`` → Cap ``[ebp+0x14]=&obj+0x4b6``,
``[ebp+0x18]=&obj+0x3c``.

Stores to ``+0x4b6/+0x4b8/+0x4ba``: only ScpLutBalance **zero** @
``0x100fd8be`` (see ``pakon_scp_lut.py``). No ``mov word [r+0x3c]`` in
cnMethods ``0x100f8000…0x10110000``. Non-zero aim fillers: **UNKNOWN** —
needs dynamic RE / deeper through-pointer chase.

Order-wide state → apply
------------------------
* Balance shifts live at ``scene+0x3a38`` (Preference) → ``getShifts``
  → path ``setShifts`` OUT / apply LUTs (``pakon_sba_apply.py``).
* FPO / order scales: FOS dump strings only; storage **UNKNOWN**.
* Apply: ``bColorSceneBalancePlanar`` ``~0x10002c50`` / TLA ``JT+0x64``
  on prior analyze state.

Host stub: mean-of-medians — **not** ``PIAnselAnalyzeRoll``.

UNKNOWN / blockers
------------------
* Preference / ``+0x4d0e`` → no alternate ``+0x3a38`` writer.
* pass1 / FOS / pass2 bodies; FPO/scale memory layout.
* Non-zero writers of FUGC ``+0x4b6`` / ``+0x3c`` (static wall).
* ``AnsOrder`` ``[edx+8]`` → OrderWide vtable slot.
"""
from __future__ import annotations

ANALYSE_ROLL_PORTED = False

# --- COM / Ci ---
CI_ANALYZE_ROLL = 0x10002843
CI_ANALYZE_ROLL_FIND_ORDER = 0x10006090
CI_ANALYZE_ROLL_TO_ANS_ORDER = 0x10020100
CI_COLOR_SCENE_BALANCE_PLANAR = 0x10002C50  # ~ entry (SEH body)

# --- AnsOrder ---
ANS_ORDER_ANALYZE_ORDER = 0x1001FC30

# --- CN-Premium ---
CN_PREMIUM_ANALYZE_ORDER_WIDE = 0x10059D90
CN_PREMIUM_ANALYZE_SCENE_SPECIFIC = 0x10054800
ORDER_WIDE_CALL_SITES = (0x1005A7AB, 0x1005B05C)

# --- Path analyze / balance ---
PATH_ANALYZE_BALANCE_ORDER = 0x10101220
PATH_ANALYZE_ANE_ORDER = 0x100FAD90
ANE_ORDER_CAP_ANALYZE = 0x10110540
ORDER_ORIENTATION_CAP_ANALYZE = 0x101218C0
PATH_ANALYZE_PRE_BALANCE = 0x100FCD70
PATH_ANALYZE_SCP_LUT_BALANCE = 0x100FD190
PATH_ANALYZE_SCP_LUT_BALANCE_ALT = 0x100FD700  # zeroes path+0x4b6
PATH_GET_CN_CONTEXT = 0x100F8620
PATH_SET_SHIFTS = 0x10100260
PATH_SET_SHIFTS_CALL = 0x10101F89  # analyzeBalanceOrder E8
PATH_SET_SHIFTS_OUT_STORE = 0x101004BB  # mov word [out],…+2,+4 (0,0 path)
# Control words from SCPLut Cap+0x10+0x18 (docs/52)
SETSHIFTS_CTRL_VIA_CAP = 0x10122A70
SETSHIFTS_CTRL_COPY = 0x10122190
SETSHIFTS_SHIPPED_CN_CTRL = (1, 2)  # ntd=1, ctd=2
SCENE_STRIDE = 0x64DC
PATH_ANALYZE_FUGC = 0x100FED00
PATH_ANALYZE_FALLOFF = 0x100FE960
PATH_ANALYZE_ATTRIBUTES = 0x100FB3D0
PATH_ANALYZE_POST_BALANCE = 0x100FDC40
PATH_BALANCE_AREA_IMAGE = 0x10102B20
PATH_ANALYZE_SHARPENING = 0x10106780
PATH_ANALYZE_AREA = 0x100E16D0

# --- Capability analyzes invoked from balanceOrder ---
SBA_ANALYZE_PASS1 = 0x10123980
SBA_ANALYZE_PASS2 = 0x10123CC0
SBA_GET_SHIFTS = 0x10124000
SBA_GET_SHIFTS_COPY = 0x1012413A  # add ecx, 0x3a38; copy 6 bytes
FOS_ANALYZE = 0x1013CB30
CAP_FIND_BY_NAME = 0x10020A40  # path +0x6028 map
SCENE_CONTEXT_FIND = 0x10022A40

# --- Path/scene object fields used as FUGC Cap analyze args ---
OBJ_FUGC_AIM_EBP14 = 0x4B6  # 3×int16 → Cap +0x60f2
OBJ_FUGC_AIM_EBP18 = 0x3C  # 3×int16 → Cap +0x60ec (policy pass)
PATH_FUGC_AIM_EBP14 = OBJ_FUGC_AIM_EBP14
PATH_FUGC_AIM_EBP18 = OBJ_FUGC_AIM_EBP18

# Name / error strings
STR_CI_ANALYZE_ROLL = 0x10573ACC
STR_CI_ANALYZE_ROLL_ERR = 0x10573AF0
STR_PATH_BALANCE_ORDER = 0x10586D3C
STR_ANS_ORDER_ANALYZE = 0x10576728
STR_ORDER_WIDE = 0x1057A5E0
STR_SCENE_SPECIFIC = 0x1057A41C
STR_PI_ANALYZE_ROLL = 0x1068FA13

# Documented TLA jump-table offsets (docs/11 + TLA loader)
JT_START_NEW_ROLL = 0x50
JT_ADD_SCENE = 0x54
JT_END_ROLL = 0x58
JT_ANALYZE_ROLL = 0x5C
JT_ANALYZE_SCENE = 0x60
JT_COLOR_SCENE_BALANCE = 0x64

# Known E8 call sites into analyzeBalanceOrder
BALANCE_ORDER_CALL_SITES = (
    0x1005A348,
    0x1005A42F,
    0x1005F491,
    0x10063C5B,
    0x10069139,
    0x10069921,
)

# OrderWide → path-stage E8 sequence (sites inside 0x10059d90…)
ORDER_WIDE_STAGE_CALLS = (
    (0x10059E02, PATH_ANALYZE_ANE_ORDER, "analyzeAneOrder"),
    (0x10059F44, 0x100D46A0, "pathUtils"),
    (0x1005A0BB, 0x100DA770, "unknown"),
    (0x1005A1FD, PATH_GET_CN_CONTEXT, "getCnContext"),
    (0x1005A24B, PATH_ANALYZE_PRE_BALANCE, "analyzePreBalance/Balance"),
    (0x1005A281, 0x10059D00, "unknown"),
    (0x1005A2D4, 0x100D8D40, "AnsImageData metrics"),
    (0x1005A348, PATH_ANALYZE_BALANCE_ORDER, "analyzeBalanceOrder"),
    (0x1005A3E0, PATH_ANALYZE_SCP_LUT_BALANCE, "analyzeScpLutBalance"),
    (0x1005A42F, PATH_ANALYZE_BALANCE_ORDER, "analyzeBalanceOrder"),
)


def main() -> None:
    print("AnalyseRoll / analyzeBalanceOrder (base 0x10000000)")
    print(f"  Ci::AnalyzeRoll              {CI_ANALYZE_ROLL:#010x}")
    print(f"  → 0x10020100 → AnsOrder::analyzeOrder {ANS_ORDER_ANALYZE_ORDER:#010x}")
    print(f"  CnPremium_analyzeOrderWide   {CN_PREMIUM_ANALYZE_ORDER_WIDE:#010x}")
    print(f"  analyzeBalanceOrder          {PATH_ANALYZE_BALANCE_ORDER:#010x}")
    print(f"  SceneSpecific                {CN_PREMIUM_ANALYZE_SCENE_SPECIFIC:#010x}")
    print(f"  ColorSceneBalancePlanar ~    {CI_COLOR_SCENE_BALANCE_PLANAR:#010x}")
    print(f"  FUGC Cap args: path+{PATH_FUGC_AIM_EBP14:#x} / +{PATH_FUGC_AIM_EBP18:#x}")
    print(f"  ANALYSE_ROLL_PORTED={ANALYSE_ROLL_PORTED}")
    print("  OrderWide stages:")
    for site, dest, name in ORDER_WIDE_STAGE_CALLS:
        print(f"    {site:#010x} → {dest:#010x}  {name}")


if __name__ == "__main__":
    main()
