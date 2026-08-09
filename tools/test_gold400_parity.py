#!/usr/bin/env python3
"""
Test parity and performance between Python/NumPy path and native C library path
on captures/gold400.bin (F-135 stage-2 colour polynomial).

Cite: TLB.dll @ 0x1000d880 (fcn.1000d880 polynomial).
"""

import os
import sys
import time
import numpy as np

# Ensure tools and tools/ansel are in path
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pakon_color

GOLD400_PATH = os.path.join(os.path.dirname(HERE), "captures", "gold400.bin")

def main():
    if not os.path.exists(GOLD400_PATH):
        print(f"Error: {GOLD400_PATH} not found", file=sys.stderr)
        return 1

    file_bytes = os.path.getsize(GOLD400_PATH)
    num_pixels = file_bytes // 6
    width = 3000
    height = num_pixels // width
    actual_pixels = width * height

    print(f"File: {GOLD400_PATH}")
    print(f"Size: {file_bytes} bytes (~{file_bytes / (1024*1024):.1f} MB)")
    print(f"Dimensions: {width}x{height} ({actual_pixels:,} RGB pixels)")

    # Read image slice (first 1000 lines = 3,000,000 pixels = ~18 MB for fast parity check)
    test_height = min(height, 1000)
    read_words = width * test_height * 3
    print(f"\nLoading test slice: {width}x{test_height} ({width * test_height:,} pixels)...")

    with open(GOLD400_PATH, "rb") as f:
        raw_bytes = f.read(read_words * 2)

    raw_u16 = np.frombuffer(raw_bytes, dtype=np.uint16).reshape((test_height, width, 3))
    coeffs = pakon_color.load_unit_matrix("auto")
    print(f"EEPROM/Registry coefficients loaded (diag: {coeffs[0]:.6f}, {coeffs[11]:.6f}, {coeffs[22]:.6f})")

    # 1. Native C Path Execution
    print("\n--- Running Native C Path (libpakon_color.dylib) ---")
    t0 = time.perf_counter()
    out_c = pakon_color.poly_hwc(raw_u16, coeffs, film_class=1)
    t_c = time.perf_counter() - t0
    print(f"Native C execution time: {t_c:.4f} seconds ({actual_pixels / t_c / 1e6:.2f} MPixels/sec)")

    # 2. Pure Python / NumPy Path Execution (temporarily disable _LIB_C)
    print("\n--- Running Pure Python / NumPy Path ---")
    saved_lib = pakon_color._LIB_C
    pakon_color._LIB_C = None
    t0 = time.perf_counter()
    out_py = pakon_color.poly_hwc(raw_u16, coeffs, film_class=1)
    t_py = time.perf_counter() - t0
    pakon_color._LIB_C = saved_lib
    print(f"Python/NumPy execution time: {t_py:.4f} seconds ({actual_pixels / t_py / 1e6:.2f} MPixels/sec)")

    # 3. Bit-Exact Parity Check
    print("\n--- Parity Check ---")
    equal = np.array_equal(out_c, out_py)
    diffs = np.count_nonzero(out_c != out_py)
    total_samples = out_c.size

    if equal:
        print(f"✅ PARITY MATCH: 100.0% Bit-Exact Match across all {total_samples:,} output channel samples!")
    else:
        print(f"❌ MISMATCH: {diffs:,} differences out of {total_samples:,} samples")
        max_diff = np.max(np.abs(out_c.astype(np.int64) - out_py.astype(np.int64)))
        print(f"Max difference magnitude: {max_diff}")
        return 1

    speedup = t_py / t_c if t_c > 0 else 1.0
    print(f"\n🚀 C Acceleration Speedup: {speedup:.2f}x faster than Python/NumPy!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
