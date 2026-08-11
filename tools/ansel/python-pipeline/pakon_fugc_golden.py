#!/usr/bin/env python3
"""Golden FUGC mode==2 metrics leaves vs PakonIMAu.dll (Unicorn).

Leaves
------
* ``0x101f79b0`` work bias → Cap ``+0x14174``
* ``0x101fa269…0x101fa341`` threshold fill+clamp → ``+0x14178…+0x1418c``
* ``0x10279952…0x1027996d`` hist pixel accumulate
* host ``fugc_work_percent`` vs ``0x1059bea8`` scale

Usage
-----
``PYTHONPATH=tools/ansel/python-pipeline /Users/guy/.pyenv/versions/3.10.13/bin/python3 \\
    tools/ansel/python-pipeline/pakon_fugc_golden.py [dll]``
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (
    UC_X86_REG_EAX,
    UC_X86_REG_EBP,
    UC_X86_REG_EBX,
    UC_X86_REG_ECX,
    UC_X86_REG_EDI,
    UC_X86_REG_EDX,
    UC_X86_REG_EIP,
    UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

import pakon_fugc as fugc

IMAGE_BASE = 0x10000000
STACK_ADDR = 0x0BF00000
STACK_SIZE = 0x100000
HEAP_ADDR = 0x0C000000
HEAP_SIZE = 0x200000

DEFAULT_DLL = Path(
    "/Users/guy/Downloads/Pakon Update 3/fx35install/program files/"
    "Pakon/F-X35 COM SERVER/PakonIMAu.dll"
)

BIAS_ENTRY = fugc.IMPL_WORK_BIAS
BIAS_RET = 0x101F7A58  # ret 4 after store +0x14174
THRESH_ENTRY = 0x101FA269
THRESH_STOP = 0x101FA341
HIST_LEAF = fugc.IMPL_HIST_ACCUM_LEAF
HIST_LEAF_END = 0x10279973


def _align_up(n: int, a: int = 0x1000) -> int:
    return (n + a - 1) & ~(a - 1)


def load_pe_into_uc(uc: Uc, pe: bytes) -> None:
    e_lfanew = struct.unpack_from("<I", pe, 0x3C)[0]
    num_sec = struct.unpack_from("<H", pe, e_lfanew + 6)[0]
    opt_size = struct.unpack_from("<H", pe, e_lfanew + 20)[0]
    opt = e_lfanew + 24
    size_image = struct.unpack_from("<I", pe, opt + 56)[0]
    uc.mem_map(IMAGE_BASE, _align_up(size_image))
    uc.mem_write(IMAGE_BASE, pe[:0x1000])
    sec_off = opt + opt_size
    for i in range(num_sec):
        o = sec_off + i * 40
        vsz, va, rsz, raddr = struct.unpack_from("<IIII", pe, o + 8)
        if rsz == 0 or raddr == 0:
            continue
        data = pe[raddr : raddr + rsz]
        if len(data) < vsz:
            data = data + b"\x00" * (vsz - len(data))
        uc.mem_write(IMAGE_BASE + va, data[: max(vsz, rsz)])


def _uc() -> Uc:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(STACK_ADDR, STACK_SIZE)
    uc.mem_map(HEAP_ADDR, HEAP_SIZE)
    return uc


def run_work_bias(
    uc: Uc,
    *,
    word_60ec: tuple[int, int, int],
    word_60f8: tuple[int, int, int],
    arg: tuple[int, int, int],
    cap: int = HEAP_ADDR,
    arg_addr: int = HEAP_ADDR + 0x20000,
) -> int:
    """Unicorn ``0x101f79b0`` → int16 at Cap ``+0x14174``."""
    blob = bytearray(0x14200)
    struct.pack_into("<hhh", blob, fugc.CAP_AIM_60EC, *word_60ec)
    struct.pack_into("<hhh", blob, fugc.CAP_AIM_60F8, *word_60f8)
    uc.mem_write(cap, bytes(blob))
    uc.mem_write(arg_addr, struct.pack("<hhh", *arg))
    ret_stub = HEAP_ADDR + 0x30000
    uc.mem_write(ret_stub, b"\xcc")
    esp = STACK_ADDR + STACK_SIZE - 0x40
    uc.mem_write(esp, struct.pack("<II", ret_stub, arg_addr))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ECX, cap)
    stop = {"hit": False}

    def _hook(uc_: Uc, address: int, size: int, _user: object) -> None:
        if address == ret_stub:
            stop["hit"] = True
            uc_.emu_stop()

    hh = uc.hook_add(UC_HOOK_CODE, _hook, begin=ret_stub, end=ret_stub + 1)
    try:
        uc.emu_start(BIAS_ENTRY, ret_stub + 1, timeout=2_000_000, count=50_000)
    except UcError as e:
        raise RuntimeError(f"unicorn bias: {e}") from e
    finally:
        uc.hook_del(hh)
    if not stop["hit"]:
        raise RuntimeError(f"bias did not return eip={uc.reg_read(UC_X86_REG_EIP):#x}")
    raw = uc.mem_read(cap + fugc.CAP_WORK_BIAS, 2)
    return int(np.int16(struct.unpack_from("<h", raw)[0]))


def run_thresholds(
    uc: Uc,
    *,
    bias: int,
    hist_min: int,
    hist_max: int,
    high: tuple[int, int],
    mid: tuple[int, int],
    low: tuple[int, int],
    cap: int = HEAP_ADDR + 0x40000,
) -> tuple[int, int, int, int, int, int]:
    """Enter ``calcFugcMetrics`` at ``0x101fa269``; stop @ ``0x101fa341``."""
    blob = bytearray(0x14200)
    struct.pack_into("<i", blob, fugc.CAP_HIST_MIN, hist_min)
    struct.pack_into("<i", blob, fugc.CAP_HIST_MAX, hist_max)
    struct.pack_into("<i", blob, fugc.CAP_HIGH_WORK_LO, high[0])
    struct.pack_into("<i", blob, fugc.CAP_HIGH_WORK_HI, high[1])
    struct.pack_into("<i", blob, fugc.CAP_MID_WORK_LO, mid[0])
    struct.pack_into("<i", blob, fugc.CAP_MID_WORK_HI, mid[1])
    struct.pack_into("<i", blob, fugc.CAP_LOW_WORK_LO, low[0])
    struct.pack_into("<i", blob, fugc.CAP_LOW_WORK_HI, low[1])
    struct.pack_into("<h", blob, fugc.CAP_WORK_BIAS, int(np.int16(bias)))
    uc.mem_write(cap, bytes(blob))
    # Reconstruct regs as at 0x101fa269 after movsx bias into eax and loads.
    # Fragment consumes esi=Cap; we jump mid-function so set esi + emulate.
    esp = STACK_ADDR + STACK_SIZE - 0x80
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_ESI, cap)
    uc.reg_write(UC_X86_REG_EBP, 0)
    stop = {"hit": False}

    def _hook(uc_: Uc, address: int, size: int, _user: object) -> None:
        if address == THRESH_STOP:
            stop["hit"] = True
            uc_.emu_stop()

    hh = uc.hook_add(UC_HOOK_CODE, _hook, begin=THRESH_STOP, end=THRESH_STOP + 1)
    try:
        uc.emu_start(THRESH_ENTRY, THRESH_STOP + 1, timeout=2_000_000, count=50_000)
    except UcError as e:
        raise RuntimeError(f"unicorn thresholds: {e}") from e
    finally:
        uc.hook_del(hh)
    if not stop["hit"]:
        raise RuntimeError(
            f"thresholds did not reach stop eip={uc.reg_read(UC_X86_REG_EIP):#x}"
        )
    out = uc.mem_read(cap + fugc.CAP_WORK_FROM_HIGH, 24)
    return struct.unpack_from("<iiiiii", out)


def run_hist_leaf(
    uc: Uc,
    *,
    values: list[int],
    hist_min: int = 0,
    hist_max: int = 4095,
) -> tuple[list[int], int]:
    """Unicorn one-pixel leaf iterations for each sample value."""
    hist_addr = HEAP_ADDR + 0x50000
    obj = HEAP_ADDR + 0x60000
    # AnsHistogram: +0x4 total, +0x8 min, +0xc max, +0x18 dens base
    uc.mem_write(hist_addr, b"\x00" * ((hist_max + 1) * 4))
    uc.mem_write(obj + 0x4, struct.pack("<i", 0))
    uc.mem_write(obj + 0x8, struct.pack("<i", hist_min))
    uc.mem_write(obj + 0xC, struct.pack("<i", hist_max))
    uc.mem_write(obj + 0x18, struct.pack("<I", hist_addr))
    total = 0
    for v in values:
        # Patch: emulate body with edx=pixel ptr, ecx=0, esi=obj
        pix = HEAP_ADDR + 0x70000
        uc.mem_write(pix, struct.pack("<h", int(np.int16(v))))
        # Build tiny stub that sets regs then jumps to leaf… easier: set regs
        # and run leaf through end, with esp+0x28 step=1 unused after one pix.
        esp = STACK_ADDR + STACK_SIZE - 0x80
        # leaf uses [esp+0x28] only after pixel; provide width=1 path by
        # running from leaf and stopping before add ecx.
        uc.mem_write(esp + 0x24, struct.pack("<I", pix))
        uc.mem_write(esp + 0x28, struct.pack("<i", 1))
        uc.reg_write(UC_X86_REG_ESP, esp)
        uc.reg_write(UC_X86_REG_ESI, obj)
        uc.reg_write(UC_X86_REG_EDX, pix)
        uc.reg_write(UC_X86_REG_ECX, 0)
        uc.reg_write(UC_X86_REG_EBX, 1)  # width countdown
        stop = {"hit": False}

        def _hook(uc_: Uc, address: int, size: int, _user: object) -> None:
            if address == HIST_LEAF_END:
                stop["hit"] = True
                uc_.emu_stop()

        hh = uc.hook_add(UC_HOOK_CODE, _hook, begin=HIST_LEAF_END, end=HIST_LEAF_END + 1)
        try:
            uc.emu_start(HIST_LEAF, HIST_LEAF_END + 1, timeout=1_000_000, count=20_000)
        except UcError as e:
            raise RuntimeError(f"unicorn hist leaf: {e}") from e
        finally:
            uc.hook_del(hh)
        if not stop["hit"]:
            raise RuntimeError(f"hist leaf stuck eip={uc.reg_read(UC_X86_REG_EIP):#x}")
        total = struct.unpack_from("<i", uc.mem_read(obj + 0x4, 4))[0]
    counts = [
        struct.unpack_from("<i", uc.mem_read(hist_addr + i * 4, 4))[0]
        for i in range(hist_max + 1)
    ]
    return counts, total


def main() -> None:
    dll_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DLL
    pe = dll_path.read_bytes()
    uc = _uc()
    load_pe_into_uc(uc, pe)

    failed = 0
    bias_cases = [
        ((500, 1000, 1000), (500, 500, 500), (100, 200, 300)),
        ((500, 1000, 1000), (500, 1000, 1000), (0, 0, 0)),
        ((100, 100, 100), (500, 500, 500), (-50, -50, -50)),
        ((725, 849, 600), (400, 599, 500), (10, -20, 30)),
    ]
    for w60ec, w60f8, arg in bias_cases:
        host = fugc.fugc_work_bias(w60ec, w60f8, arg)
        ref = run_work_bias(uc, word_60ec=w60ec, word_60f8=w60f8, arg=arg)
        mark = "OK" if host == ref else "FAIL"
        if host != ref:
            failed += 1
        print(f"  {mark} bias 60ec={w60ec} dmin={w60f8} arg={arg} → host={host} dll={ref}")

    thr_cases = [
        (0, 0, 4095, (725, 849), (600, 724), (400, 599)),
        (50, 0, 4095, (725, 849), (600, 724), (400, 599)),
        (-100, 0, 4095, (50, 80), (20, 40), (0, 10)),
        (4000, 0, 4095, (725, 849), (600, 724), (400, 599)),
    ]
    for bias, hmin, hmax, hi, mid, lo in thr_cases:
        host = fugc.fugc_work_thresholds(
            bias=bias, hist_min=hmin, hist_max=hmax, high=hi, mid=mid, low=lo
        )
        ref = run_thresholds(
            uc, bias=bias, hist_min=hmin, hist_max=hmax, high=hi, mid=mid, low=lo
        )
        mark = "OK" if host == ref else "FAIL"
        if host != ref:
            failed += 1
        print(f"  {mark} thr bias={bias} → host={host} dll={ref}")

    samples = [0, 100, 500, 600, 725, 849, 4095, -1, 5000]
    host_hist = np.zeros(4096, dtype=np.int32)
    host_total = fugc.fugc_hist_accum_i16(
        np.array(samples, dtype=np.int16), host_hist, hist_min=0, hist_max=4095
    )
    dll_counts, dll_total = run_hist_leaf(uc, values=samples)
    host_counts = [int(host_hist[i]) for i in range(4096)]
    mark = "OK" if host_counts == dll_counts and host_total == dll_total else "FAIL"
    if mark != "OK":
        failed += 1
    print(f"  {mark} hist leaf total host={host_total} dll={dll_total}")

    for band, total in ((10, 40), (0, 0), (7, 7)):
        host = fugc.fugc_work_percent(band, total)
        # bit-identical float32 path
        ref = (
            0.0
            if total == 0
            else float(np.float32(100.0 * (float(band) / float(total))))
        )
        mark = "OK" if host == ref else "FAIL"
        if host != ref:
            failed += 1
        print(f"  {mark} pct {band}/{total} → {host}")

    # COM/ROI control leaves (cite 0x101f8bc0 / 0x10278140 / applyLut gate)
    assert fugc.FUGC_HIST_COM_ROI_PORTED
    assert fugc.FUGC_APPLY_LUT_GATE_PORTED
    if fugc.fugc_hist_roi_inset(100, 80) != (98, 78):
        print("  FAIL roi inset")
        failed += 1
    else:
        print("  OK hist ROI inset −2")
    if fugc.fugc_hist_setup_ok(0, 0) or not fugc.fugc_hist_setup_ok(0, 4095):
        print("  FAIL hist setup gate")
        failed += 1
    else:
        print("  OK hist setup max>min")
    if fugc.fugc_hist_setup_base_adjust(0x1000, 10) != 0x1000 - 40:
        print("  FAIL hist base adjust")
        failed += 1
    else:
        print("  OK hist base −4·min")
    plane = np.arange(5 * 5, dtype=np.int16).reshape(5, 5)
    hist = np.zeros(4096, dtype=np.int32)
    total_roi = fugc.fugc_generate_histogram_roi(plane, hist, hist_min=0, hist_max=4095)
    # crop 3×3 interior (inset 2 from 5×5)
    expect_hist = np.zeros(4096, dtype=np.int32)
    expect_total = fugc.fugc_hist_accum_i16(plane[1:4, 1:4], expect_hist)
    if total_roi != expect_total or not np.array_equal(hist, expect_hist):
        print(f"  FAIL roi hist {total_roi} vs {expect_total}")
        failed += 1
    else:
        print("  OK generateHistogram ROI → pixel leaf")
    if not (
        fugc.fugc_apply_lut_type_accepted(0)
        and fugc.fugc_apply_lut_type_accepted(2)
        and not fugc.fugc_apply_lut_type_accepted(1)
    ):
        print("  FAIL applyLut type gate")
        failed += 1
    else:
        print("  OK applyLut type ∈ {0,2}")

    print(
        f"  FLAGS METRICS={fugc.FUGC_METRICS_PORTED} "
        f"HIST={fugc.FUGC_GENERATE_HISTOGRAM_PORTED} "
        f"HIST_ROI={fugc.FUGC_HIST_COM_ROI_PORTED} "
        f"APPLY_GATE={fugc.FUGC_APPLY_LUT_GATE_PORTED} "
        f"BIAS={fugc.FUGC_WORK_BIAS_PORTED}"
    )
    if failed:
        raise SystemExit(1)
    print("  all FUGC mode==2 golden OK")


if __name__ == "__main__":
    main()
