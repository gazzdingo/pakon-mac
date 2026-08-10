import numpy as np
import sys

# Load a small slice of active_raw
raw = np.fromfile('captures/gold400.bin', dtype=np.uint16)
lines = raw[2124*6000 : 2124*6000 + 100*6000].reshape(100, 6000)
# Shift by 2 (Stage 0)
lines = (lines & 0xFFFE) >> 2

# The interleaved words are Word0, Word1, Word2
w0 = lines[:, 0::3].flatten()
w1 = lines[:, 1::3].flatten()
w2 = lines[:, 2::3].flatten()

# EEPROM coeffs
import struct
with open('backups/eeprom-i2c/eeprom_52.bin', 'rb') as f:
    f.seek(0x25)
    coeffs = np.frombuffer(f.read(30*4), dtype=np.float32)

def eval_poly(r, g, b):
    # Just do a rough mean of the polynomial output
    r_mean = r.mean(); g_mean = g.mean(); b_mean = b.mean()
    out = np.zeros(3)
    for k in range(3):
        c = coeffs[10*k : 10*(k+1)]
        val = (c[0]*r_mean + c[1]*g_mean + c[2]*b_mean + 
               c[3]*r_mean**2 + c[4]*g_mean**2 + c[5]*b_mean**2 +
               c[6]*r_mean*g_mean + c[7]*r_mean*b_mean + c[8]*g_mean*b_mean + c[9])
        out[k] = val
    return out

perms = [
    ('RGB', w0, w1, w2),
    ('RBG', w0, w2, w1),
    ('GRB', w1, w0, w2),
    ('GBR', w1, w2, w0),
    ('BRG', w2, w0, w1),
    ('BGR', w2, w1, w0)
]

for name, r, g, b in perms:
    out = eval_poly(r, g, b)
    rpd_r = out[0] + 741
    rpd_g = out[1] + 355
    rpd_b = out[2] + 209
    print(f'{name:3s} -> RPD pre-SBA: {out[0]:6.1f} {out[1]:6.1f} {out[2]:6.1f} | post-SBA: {rpd_r:6.1f} {rpd_g:6.1f} {rpd_b:6.1f}')
