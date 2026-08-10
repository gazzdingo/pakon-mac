/**
 * Frida dump of PIAnselAddScene planar pixels under Wine / Windows.
 *
 * Settles docs/58 §3.5 residual: does AddScene see TLB poly output
 * (host `poly_hwc`) or a dens-LUT remapped buffer?
 *
 * PakonIMAu.dll export PIAnselAddScene @ VA 0x100183c0 (reloc base may
 * differ under Wine — we resolve by export name).
 *
 * Call shape (docs/58 §7 / TLB 0x10034eb5, cdecl 3 args):
 *   AddScene(imageObj, unusedOrCtx, desc*)
 * Desc is 0x68 bytes; +0x48 = case, +0x54/+0x58/+0x5c = dmin RGB words
 * (pakon_scene_context). Image planar layout after stage 2: R, G, B
 * planes of W*H uint16 (TLB poly in-place; R at +0, G at +2n, B at +4n
 * bytes — docs/58 §4.1). Under Wine the *object* may wrap that buffer;
 * this script dumps:
 *   1) desc RGB dmin words (always)
 *   2) first N RGB triplets if --scan finds a plausible planar pointer
 *      in the first few dwords of arg0 / desc
 *
 * Usage (Wine, after wine-stable is installed):
 *   frida -f wine -- "C:\\path\\to\\TLXClientDemo.exe" -l tools/addscene_wine_dump.js
 *   # or attach:
 *   frida -n TLXClientDemo.exe -l tools/addscene_wine_dump.js
 *
 * On Parallels Win10 the same script works with native frida-server.
 *
 * Writes JSON lines to OUT (default /tmp/addscene_dump.jsonl).
 */

'use strict';

const OUT = Process.getenv('ADDSCENE_DUMP') || '/tmp/addscene_dump.jsonl';
const MAX_TRIPLETS = parseInt(Process.getenv('ADDSCENE_N') || '64', 10);
const MAX_CALLS = parseInt(Process.getenv('ADDSCENE_MAX') || '32', 10);

let nCalls = 0;

function u16(p) {
  try { return p.readU16(); } catch (e) { return null; }
}
function u32(p) {
  try { return p.readU32(); } catch (e) { return null; }
}

function dumpDesc(desc) {
  if (desc.isNull()) return null;
  return {
    case: u32(desc.add(0x48)),
    dmin_r: u32(desc.add(0x54)),
    dmin_g: u32(desc.add(0x58)),
    dmin_b: u32(desc.add(0x5c)),
    dword0: u32(desc),
    dword2: u32(desc.add(8)),
    dword3: u32(desc.add(0xc)),
  };
}

/**
 * Heuristic: treat `base` as planar R|G|B of `n` uint16 samples
 * (n = w*h). Read first MAX_TRIPLETS of each plane.
 */
function dumpPlanar(base, n) {
  if (base.isNull() || n < 1 || n > 50_000_000) return null;
  const rgb = [];
  const take = Math.min(MAX_TRIPLETS, n);
  try {
    for (let i = 0; i < take; i++) {
      const r = u16(base.add(2 * i));
      const g = u16(base.add(2 * (n + i)));
      const b = u16(base.add(2 * (2 * n + i)));
      if (r === null || g === null || b === null) return null;
      rgb.push([r, g, b]);
    }
  } catch (e) {
    return null;
  }
  return { n: n, samples: rgb };
}

function tryPlanarFromPtr(p) {
  if (p.isNull()) return null;
  // Common object layouts: +0 vtable, +0x2c/+0x30 size, +0x58 plane base
  // (matches TLB image object fields used around poly call in fcn.10026c90).
  const candidates = [
    p,
    ptr(u32(p) || 0),
  ];
  for (const off of [0x58, 0x2c, 0x30, 0x14, 0x18, 0x1c]) {
    try { candidates.push(p.add(off).readPointer()); } catch (e) {}
  }
  // Prefer sizes that look like scan dimensions near 2000×N.
  const sizes = [];
  for (const off of [0x2c, 0x30, 0x34, 0x38, 0xc, 0x10]) {
    try {
      const v = u32(p.add(off));
      if (v && v > 16 && v < 20_000_000) sizes.push(v);
    } catch (e) {}
  }
  for (const base of candidates) {
    if (!base || base.isNull()) continue;
    for (const n of sizes.concat([2000, 64, MAX_TRIPLETS])) {
      const d = dumpPlanar(base, n);
      if (!d) continue;
      // Reject all-zero and all-identical noise.
      const flat = d.samples.flat();
      const mx = Math.max.apply(null, flat);
      const mn = Math.min.apply(null, flat);
      if (mx === 0) continue;
      if (mx > 4095 && mx <= 16383) {
        // Still looks like pre-poly 14-bit — record anyway.
        return { base: base.toString(), hint: 'maybe_14bit', ...d };
      }
      if (mx <= 4095 && (mx - mn) > 0) {
        return { base: base.toString(), hint: 'maybe_12bit_rpd', ...d };
      }
    }
  }
  return null;
}

function append(rec) {
  const line = JSON.stringify(rec) + '\n';
  const f = new File(OUT, 'a');
  f.write(line);
  f.close();
  console.log('[addscene] #' + rec.i + ' wrote ' + OUT);
}

function hookAddScene(addr) {
  console.log('[addscene] hooking PIAnselAddScene @ ' + addr);
  Interceptor.attach(addr, {
    onEnter(args) {
      if (nCalls >= MAX_CALLS) return;
      const image = args[0];
      const arg1 = args[1];
      const desc = args[2];
      const rec = {
        i: nCalls,
        ts: Date.now(),
        image: image.toString(),
        arg1: arg1.toString(),
        desc: dumpDesc(desc),
        planar: tryPlanarFromPtr(image) || tryPlanarFromPtr(desc),
      };
      nCalls += 1;
      append(rec);
    },
  });
}

function findExport() {
  const names = ['PakonIMAu.dll', 'pakonimau.dll', 'PAKONIMAU.DLL'];
  for (const name of names) {
    const m = Process.findModuleByName(name);
    if (!m) continue;
    const exp = m.findExportByName('PIAnselAddScene');
    if (exp) return exp;
  }
  // Fallback: scan modules for the export string.
  for (const m of Process.enumerateModules()) {
    if (m.name.toLowerCase().indexOf('imau') < 0) continue;
    const exp = m.findExportByName('PIAnselAddScene');
    if (exp) return exp;
  }
  return null;
}

function main() {
  console.log('[addscene] OUT=' + OUT + ' N=' + MAX_TRIPLETS);
  let addr = findExport();
  if (addr) {
    hookAddScene(addr);
    return;
  }
  console.log('[addscene] PakonIMAu not loaded yet — waiting…');
  const iv = setInterval(() => {
    addr = findExport();
    if (!addr) return;
    clearInterval(iv);
    hookAddScene(addr);
  }, 500);
}

main();
