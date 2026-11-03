/*
 * batch.js: write thousands of unique, fully editable SVG backgrounds.
 *
 * The library has 510 designs (34 patterns x 15 styles). Every design can make
 * as many variations as you ask for. Variation 0 is the design itself.
 *
 *   node batch.js                                  510 designs x 5 variations -> ./out
 *   node batch.js --variations 1000                510 x 1000 = 510,000 files
 *   node batch.js --designs 1-30 --variations 200  only designs 1 to 30
 *   node batch.js --pattern burst --variations 500 one pattern only
 *   node batch.js --size 3840x2160 --strength wild --out D:/stock
 *
 * Options
 *   --designs  A-B       design range, 1 to 510 (default 1-510)
 *   --pattern  id        only designs of this pattern
 *   --variations N       files per design, including the design itself (default 5)
 *   --strength S         subtle | medium | wild (default medium)
 *   --size WxH           artboard in px (default 1920x1080)
 *   --transparent        no background rectangle
 *   --out DIR            output folder (default ./out)
 *
 * Speed: about 3 ms per file. To use several CPU cores, start several terminals
 * with different --designs ranges (for example 1-130, 131-260, 261-390, 391-510).
 *
 * Layout:  out/<pattern>/d<design>/v<variation>.svg   and   out/manifest-<A>-<B>.csv
 * Every file is hashed. A file whose hash was already written is skipped and the
 * next variation index is used, so no two files in one run are identical.
 */
const fs = require('fs');
const path = require('path');
const G = require('./server/static/bg-generator.js');

const args = {};
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (!a.startsWith('--')) continue;
  const key = a.slice(2), next = process.argv[i + 1];
  if (next === undefined || next.startsWith('--')) args[key] = true; else { args[key] = next; i++; }
}

const total = G.designCount();
const [from, to] = String(args.designs || `1-${total}`).split('-').map(Number);
const perDesign = Number(args.variations || 5);
const strength = args.strength || 'medium';
const [W, H] = String(args.size || '1920x1080').split('x').map(Number);
const outDir = args.out || 'out';
const only = args.pattern || null;

fs.mkdirSync(outDir, { recursive: true });
const manifest = [['file', 'design', 'pattern', 'style', 'palette', 'variation', 'hash'].join(',')];
const seen = new Set();
let written = 0, skipped = 0;
const t0 = Date.now();

for (let n = from; n <= Math.min(to, total); n++) {
  const d = G.designAt(n);
  if (only && d.pattern !== only) continue;
  const dir = path.join(outDir, d.pattern, 'd' + String(n).padStart(3, '0'));
  fs.mkdirSync(dir, { recursive: true });
  let made = 0, idx = 0;
  while (made < perDesign && idx < perDesign * 4) {
    const v = G.variation(d.pattern, { params: d.params, colors: d.colors }, idx, strength);
    const svg = G.generate(d.pattern, {
      width: W, height: H, transparent: !!args.transparent,
      params: v.params, colors: v.colors, hue: v.hue, rotate: v.rotate,
      seed: idx === 0 ? d.seed : v.seed
    });
    const hash = G.hash(svg);
    if (seen.has(hash)) { skipped++; idx++; continue; }
    seen.add(hash);
    const file = path.join(dir, 'v' + String(idx).padStart(4, '0') + '.svg');
    fs.writeFileSync(file, G.toFile(svg));
    manifest.push([path.relative(outDir, file), n, d.pattern, d.style, d.paletteName, idx, hash].join(','));
    made++; written++; idx++;
  }
  if (n % 10 === 0) console.log(`design ${n}/${Math.min(to, total)}  files ${written}  ${(written / ((Date.now() - t0) / 1000)).toFixed(0)}/s`);
}

fs.writeFileSync(path.join(outDir, `manifest-${from}-${Math.min(to, total)}.csv`), manifest.join('\n'));
console.log(`Done. ${written} unique SVG files in ${((Date.now() - t0) / 1000).toFixed(1)}s (${skipped} duplicates skipped). Manifest saved.`);
