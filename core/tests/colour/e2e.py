"""End-to-end corpus check (Task 21): libpakon's public API on whole real rolls == Kodak's engine, bit for bit.

usage: python3 -I core/tests/colour/e2e.py [--rolls r4,r2,..] [--no-adjust] [--keep-rolls] [--pixels] [--build DIR] [--threads N]

For every roll in e2e_hashes.json: the roll directory (pk_roll_input layout, CORPUS.md) is rebuilt from the owner's v1
capture by tools/v1_adapter/v1_adapter.py when it is not in the scratch tree, and must hash to the recorded inputs;
build/pakon_render renders every frame in PSI's default save geometry (the roll's save_rotation); the SHA-256 of each
frame's u8 sRGB and 12-bit pre-ICC buffer must equal
Kodak's (recorded by lab/e2e/run_corpus.py from PakonIMAu under Wine at x87 PC53, fed by TLB's own film-base finder,
LUT and polynomial on the same roll directory). The adjustment grid (lab/e2e/run_adjust.py) is checked the same way, and
so are the AnselOrientation = 0 renders of lab/e2e/run_ao0.py (pk_colour_render_saved, Task 22 item 6) and PSI's scaled
saves of lab/e2e/run_scaled.py (pk_colour_render_saved_scaled, RE 39: the bounding box, fit 1 / 2, don't-scale-up, picture
rotations and AnselOrientation 0 on frames of r4 and g400, up- and downscaled).
Prints one line per frame that differs and a summary line:
    e2e: <R> rolls, <F> frames, <N> differing (u8 hash, sb hash); adjust: <S> renders, <M> differing; AnselOrientation 0: ...;
    scaled save: <S> renders, <M> differing
With --pixels, a differing frame is re-run through Kodak's engine (Wine) to count its differing pixels.

Exit 0 = pass, 1 = a difference or an error, 77 = skipped: a roll directory is neither in the scratch tree with the
recorded hashes nor rebuildable (its capture or the scratch tree's v1 copy is absent; lab/restore_scratch.sh restores the
latter). Checking hashes needs no Wine and no RE archive; --pixels needs Wine.
Only lab tooling and the CLI are used; nothing here is part of libpakon.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
HASHES = os.path.join(HERE, 'e2e_hashes.json')
EXPERIMENT = os.environ.get('PAKON_V1_EXPERIMENT', '/private/tmp/pakon_re_v2/work/experiment/')
ROLLS = '/private/tmp/pakon_re_v2/work/e2e/rolls/'
CHUNK = 8


def skip(why):
    print(f'e2e: SKIP ({why})')
    sys.exit(77)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 22), b''):
            h.update(blk)
    return h.hexdigest()


def have_roll(name, roll):
    d = ROLLS + name
    if os.path.exists(d + '/roll.json'):
        meta = json.load(open(d + '/roll.json'))
        if meta['sha256'] == roll['roll_sha256'] and all(sha256(os.path.join(d, f)) == h for f, h in meta['sha256'].items()):
            return True
    return False


def rebuildable(roll):
    return os.path.exists(os.path.join(roll['captures_dir'], roll['capture'] + '.bin')) and os.path.isdir(EXPERIMENT + 'v1/tools')


def roll_dir(name, roll, keep):
    d = ROLLS + name
    if have_roll(name, roll): return d, False
    shutil.rmtree(d, ignore_errors=True)
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'tools', 'v1_adapter', 'v1_adapter.py'), roll['capture'], d,
                    '--captures', roll['captures_dir']], check=True, stdout=subprocess.DEVNULL)
    meta = json.load(open(d + '/roll.json'))
    if meta['sha256'] != roll['roll_sha256']:
        raise SystemExit(f'e2e: {name}: the rebuilt roll directory does not hash to the recorded inputs')
    return d, not keep


def pixels_differing(name, d, k, ext, mine, wine, rot):
    """re-run Kodak for frame k (Wine) and count the differing pixels; None without Wine"""
    if not wine: return None
    import numpy as np
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'lab', 'oracle', 'scripts', 'e2e_oracle.py'), d, name,
                    '--frames', str(k), '--geom', f'{rot},0'], check=True, stdout=subprocess.DEVNULL)
    ko = f'/private/tmp/pakon_re_v2/work/oracle/out/e2e_{name}/f{k}.{ext}'
    dt = np.uint8 if ext.endswith('u8') else '<u2'
    a = np.fromfile(ko, dt).reshape(3, -1); b = np.fromfile(mine, dt).reshape(3, -1)
    return int((a != b).any(0).sum())


def sets_file(H):
    p = os.path.join(tempfile.gettempdir(), 'pk_e2e_adjust_sets.json')
    json.dump(H['adjust']['sets'], open(p, 'w'))
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rolls'); ap.add_argument('--no-adjust', action='store_true')
    ap.add_argument('--keep-rolls', action='store_true', help='keep roll directories rebuilt by this run')
    ap.add_argument('--pixels', action='store_true', help="count a differing frame's pixels (re-runs Kodak's engine)")
    ap.add_argument('--bits16', action='store_true', help="also check '16-bit Kodak' (C10, docs/re/50): every frame, adjust set and scaled save, "
                    "rendered 16-bit and reduced with Kodak's 8-bit store, must equal the 8-bit render")
    ap.add_argument('--build', default=os.path.join(ROOT, 'build'))
    ap.add_argument('--threads', default='0', help="pakon_render --threads N (0 = automatic, 1 = calling thread only); the hashes must not change")
    A = ap.parse_args()
    wine = shutil.which('wine')
    if A.pixels and not wine: raise SystemExit('e2e: --pixels needs Wine')
    H = json.load(open(HASHES))
    want = set(A.rolls.split(',')) if A.rolls else None
    rolls = {k: v for k, v in H['rolls'].items() if not want or k in want}
    for name, r in rolls.items():
        if not have_roll(name, r) and not rebuildable(r):
            skip(f"roll {name}: no roll directory and capture {r['capture']} or the v1 copy {EXPERIMENT} absent")
    render = os.path.join(A.build, 'pakon_render')
    if not os.path.exists(render): raise SystemExit(f'e2e: {render} missing: build the core first')

    nf = bad = 0
    for name, roll in rolls.items():
        d, drop = roll_dir(name, roll, A.keep_rolls)
        frames = roll['frames']
        with tempfile.TemporaryDirectory(prefix='pk_e2e_') as out:
            for c0 in range(0, len(frames), CHUNK):
                chunk = frames[c0:c0 + CHUNK]
                r = subprocess.run([render, d, out, '--frames', ','.join(str(f['frame']) for f in chunk),
                                    '--rotate', str(roll['save_rotation']), '--threads', A.threads], capture_output=True, text=True)
                if r.returncode: print(r.stderr); raise SystemExit(f'e2e: pakon_render failed on {name}')
                for f in chunk:
                    k = f['frame']; nf += 1
                    for ext, key in (('srgb.u8', 'u8_sha256'), ('sb.u16', 'sb_sha256')):
                        p = os.path.join(out, f'f{k}.{ext}')
                        if sha256(p) != f[key]:
                            bad += 1
                            px = pixels_differing(name, d, k, ext, p, wine, roll['save_rotation']) if A.pixels else None
                            print(f'e2e: DIFFER {name} frame {k} {ext}' + (f': {px} differing pixels' if px is not None else ''))
                        os.remove(p)
        if drop: shutil.rmtree(d)
    line = f'e2e: {len(rolls)} rolls, {nf} frames, {bad} differing outputs (u8 + sb hashes)'

    adj_bad = adj_n = 0
    if not A.no_adjust and 'adjust' in H:
        G = H['adjust']
        sets = os.path.join(tempfile.gettempdir(), 'pk_e2e_adjust_sets.json')
        json.dump(G['sets'], open(sets, 'w'))
        for fr in G['frames']:
            name, k = fr['roll'], fr['frame']
            if want and name not in want: continue
            d, drop = roll_dir(name, H['rolls'][name], A.keep_rolls)
            with tempfile.TemporaryDirectory(prefix='pk_e2e_adj_') as out:
                r = subprocess.run([render, d, out, '--frames', str(k), '--no-sb', '--adjust', '@' + sets,
                                    '--rotate', str(fr['rotation']), '--threads', A.threads], capture_output=True, text=True)
                if r.returncode: print(r.stderr); raise SystemExit(f'e2e: pakon_render --adjust failed on {name}')
                for s in fr['sets']:
                    adj_n += 1
                    if sha256(os.path.join(out, f"f{k}.a{s['set']}.srgb.u8")) != s['u8_sha256']:
                        adj_bad += 1
                        print(f"e2e: DIFFER {name} frame {k} adjust set {s['set']} {G['sets'][s['set']]}")
            if drop: shutil.rmtree(d)
        line += f'; adjust: {adj_n} renders, {adj_bad} differing'
    ao_bad = ao_n = 0
    if 'ao0' in H:     # Task 22 item 6: PSI's save path with AnselOrientation = 0 (PIRotatePlanar 270 before the balance)
        for fr in H['ao0']:
            name, k = fr['roll'], fr['frame']
            if want and name not in want: continue
            d, drop = roll_dir(name, H['rolls'][name], A.keep_rolls)
            with tempfile.TemporaryDirectory(prefix='pk_e2e_ao0_') as out:
                r = subprocess.run([render, d, out, '--frames', str(k), '--ansel-orientation', '0', '--threads', A.threads], capture_output=True, text=True)
                if r.returncode: print(r.stderr); raise SystemExit(f'e2e: pakon_render --ansel-orientation failed on {name}')
                ao_n += 1
                if sha256(os.path.join(out, f'f{k}.srgb.u8')) != fr['u8_sha256']:
                    ao_bad += 1
                    print(f'e2e: DIFFER {name} frame {k} AnselOrientation 0')
            if drop: shutil.rmtree(d)
        line += f'; AnselOrientation 0: {ao_n} renders, {ao_bad} differing'
    sc_bad = sc_n = 0
    if 'scaled' in H:  # RE 39: PSI's scaled save (iSaveControl 0x01 / 0x02 / 0x800), pk_colour_render_saved_scaled
        for case in H['scaled']:
            name = case['roll']
            if want and name not in want: continue
            d, drop = roll_dir(name, H['rolls'][name], A.keep_rolls)
            fit, bw, bh, noup = case['save_size']
            with tempfile.TemporaryDirectory(prefix='pk_e2e_scaled_') as out:
                cmd = [render, d, out, '--frames', ','.join(str(f['frame']) for f in case['frames']), '--save-size', f'{fit},{bw},{bh},{noup}',
                       '--picture-rotation', str(case['picture_rotation']), '--ansel-orientation', str(case['ansel_orientation']),
                       '--threads', A.threads]
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode: print(r.stderr); raise SystemExit(f"e2e: pakon_render --save-size failed on {name} case {case['case']}")
                for f in case['frames']:
                    k = f['frame']; p = os.path.join(out, f'f{k}.srgb.u8'); sc_n += 1
                    if os.path.getsize(p) != 3 * f['size'][0] * f['size'][1] or sha256(p) != f['u8_sha256']:
                        sc_bad += 1
                        print(f"e2e: DIFFER {name} frame {k} scaled save case {case['case']} ({case['save_size']}, rotation {case['picture_rotation']}, "
                              f"AnselOrientation {case['ansel_orientation']}), Kodak {f['size'][0]}x{f['size'][1]}")
            if drop: shutil.rmtree(d)
        line += f'; scaled save: {sc_n} renders, {sc_bad} differing'
    b16 = [0, 0, 0]      # renders, differing pixels, samples carrying more than the 8-bit code
    def bits16_run(d, args):
        with tempfile.TemporaryDirectory(prefix='pk_e2e_b16_') as out:
            r = subprocess.run([render, d, out, '--bits16', '--ansel-orientation', args.pop(0), '--threads', A.threads] + args, capture_output=True, text=True)
            for ln in r.stdout.splitlines():
                if ln.startswith('bits16: ') and 'renders' in ln:
                    t = ln.split()
                    b16[0] += int(t[1]); b16[1] += int(t[3]); b16[2] += int(t[6])
                elif ln.startswith('bits16: '): print('e2e: ' + ln)
            if r.returncode and not b16[1]: print(r.stderr); raise SystemExit('e2e: pakon_render --bits16 failed')
    if A.bits16:
        for name, roll in rolls.items():
            d, drop = roll_dir(name, roll, A.keep_rolls)
            bits16_run(d, ['270', '--no-sb'])
            if 'adjust' in H:
                for fr in H['adjust']['frames']:
                    if fr['roll'] == name: bits16_run(d, ['270', '--no-sb', '--frames', str(fr['frame']), '--adjust', '@' + sets_file(H)])
            for case in H.get('scaled', []):
                if case['roll'] == name:
                    fit, bw, bh, noup = case['save_size']
                    bits16_run(d, [str(case['ansel_orientation']), '--no-sb', '--frames', ','.join(str(f['frame']) for f in case['frames']),
                                   '--save-size', f'{fit},{bw},{bh},{noup}', '--picture-rotation', str(case['picture_rotation'])])
            if drop: shutil.rmtree(d)
        line += f'; 16-bit Kodak: {b16[0]} renders, {b16[1]} differing pixels after reduction to 8 bit, {b16[2]} samples carry more than the 8-bit code'
    print(line)
    sys.exit(1 if bad or adj_bad or ao_bad or sc_bad or b16[1] else 0)


if __name__ == '__main__':
    main()
