/*
 * bg-generator.js
 * Parametric vector background generator. Pure functions, no dependencies.
 * Works in the browser (window.BGGen) and in Node (require).
 *
 *   const G = require('./bg-generator.js');
 *   const svg = G.generate('burst', { width: 1920, height: 1080, seed: 7 });
 *   const opts = G.randomOptions('scales', 12345);      // random params + palette
 *   const file = G.toFile(G.generate('scales', opts));  // ready to save as .svg
 *
 * Every shape in the output is a native <path>, <polygon>, <circle>, <rect>
 * or <line>. No raster, no filters, no masks. Opens in Illustrator, Figma,
 * Affinity, Inkscape as fully editable vector art.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.BGGen = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var TAU = Math.PI * 2;
  var f = function (n) { return String(+(+n).toFixed(2)); };

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  /* ---------- colour helpers ---------- */
  function hex2rgb(h) {
    h = String(h).replace('#', '');
    if (h.length === 3) h = h.split('').map(function (c) { return c + c; }).join('');
    var n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function rgb2hex(r, g, b) {
    return '#' + [r, g, b].map(function (v) {
      return Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0');
    }).join('');
  }
  function mix(a, b, t) {
    var A = hex2rgb(a), B = hex2rgb(b);
    return rgb2hex(A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t);
  }

  function hueShift(hex, deg) {
    var c = hex2rgb(hex), r = c[0] / 255, g = c[1] / 255, b = c[2] / 255;
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b), h = 0, sat = 0, l = (mx + mn) / 2, d = mx - mn;
    if (d) {
      sat = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
      h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
      h /= 6;
    }
    if (!sat) return hex;
    h = (((h + deg / 360) % 1) + 1) % 1;
    /* Keep the perceived brightness of the original, so a hue turn never produces neon colours. */
    var target = (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255;
    var build = function (L) {
      var sa = sat * 0.88;
      var q = L < 0.5 ? L * (1 + sa) : L + sa - L * sa, p2 = 2 * L - q;
      var k = function (t) {
        t = (t + 1) % 1;
        if (t < 1 / 6) return p2 + (q - p2) * 6 * t;
        if (t < 1 / 2) return q;
        if (t < 2 / 3) return p2 + (q - p2) * (2 / 3 - t) * 6;
        return p2;
      };
      return [k(h + 1 / 3) * 255, k(h) * 255, k(h - 1 / 3) * 255];
    };
    var lo = 0.03, hi = 0.97, it;
    for (it = 0; it < 14; it++) {
      var mid = (lo + hi) / 2, rgb = build(mid);
      if ((0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255 < target) lo = mid; else hi = mid;
    }
    var out = build((lo + hi) / 2);
    return rgb2hex(out[0], out[1], out[2]);
  }
  function lighten(c, t) { return mix(c, '#ffffff', t); }
  function darken(c, t) { return mix(c, '#000000', t); }

  /* ---------- geometry helpers ---------- */
  function polyPath(pts, close) {
    return 'M' + pts.map(function (p) { return f(p[0]) + ' ' + f(p[1]); }).join('L') + (close ? 'Z' : '');
  }
  function smoothPath(pts, closed) {
    var n = pts.length, i;
    if (n < 3) return polyPath(pts, closed);
    var mid = function (a, b) { return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; };
    var d, m;
    if (closed) {
      m = mid(pts[n - 1], pts[0]);
      d = 'M' + f(m[0]) + ' ' + f(m[1]);
      for (i = 0; i < n; i++) {
        var p = pts[i], q = pts[(i + 1) % n], m2 = mid(p, q);
        d += 'Q' + f(p[0]) + ' ' + f(p[1]) + ' ' + f(m2[0]) + ' ' + f(m2[1]);
      }
      return d + 'Z';
    }
    d = 'M' + f(pts[0][0]) + ' ' + f(pts[0][1]);
    for (i = 1; i < n - 1; i++) {
      var mm = mid(pts[i], pts[i + 1]);
      d += 'Q' + f(pts[i][0]) + ' ' + f(pts[i][1]) + ' ' + f(mm[0]) + ' ' + f(mm[1]);
    }
    return d + 'L' + f(pts[n - 1][0]) + ' ' + f(pts[n - 1][1]);
  }
  function hexPts(x, y, r) {
    var out = [];
    for (var k = 0; k < 6; k++) {
      var a = (-90 + 60 * k) * Math.PI / 180;
      out.push([x + r * Math.cos(a), y + r * Math.sin(a)]);
    }
    return out;
  }
  function hexGrid(W, H, cols) {
    var hw = W / cols, r = hw / Math.sqrt(3), dy = 1.5 * r;
    var rows = Math.ceil(H / dy) + 2, cells = [];
    for (var row = -1; row < rows; row++) {
      for (var i = -1; i <= cols; i++) {
        cells.push({ x: i * hw + ((row & 1) ? hw / 2 : 0), y: row * dy });
      }
    }
    return { cells: cells, r: r, rows: rows };
  }

  /* ---------- marching squares (for contour lines) ---------- */
  function contours(field, gw, gh, level, cell) {
    var pts = new Map(), adj = new Map();
    var v = function (i, j) { return field[j * (gw + 1) + i]; };
    function edge(type, i, j) {
      var key = type + i + ',' + j;
      if (!pts.has(key)) {
        var a, b, t;
        if (type === 'h') {
          a = v(i, j); b = v(i + 1, j); t = (level - a) / (b - a);
          pts.set(key, [(i + t) * cell, j * cell]);
        } else {
          a = v(i, j); b = v(i, j + 1); t = (level - a) / (b - a);
          pts.set(key, [i * cell, (j + t) * cell]);
        }
      }
      return key;
    }
    function link(a, b) {
      if (!adj.has(a)) adj.set(a, []);
      if (!adj.has(b)) adj.set(b, []);
      adj.get(a).push(b); adj.get(b).push(a);
    }
    for (var j = 0; j < gh; j++) {
      for (var i = 0; i < gw; i++) {
        var idx = (v(i, j) > level ? 8 : 0) | (v(i + 1, j) > level ? 4 : 0) |
                  (v(i + 1, j + 1) > level ? 2 : 0) | (v(i, j + 1) > level ? 1 : 0);
        if (idx === 0 || idx === 15) continue;
        var T = function () { return edge('h', i, j); };
        var B = function () { return edge('h', i, j + 1); };
        var L = function () { return edge('v', i, j); };
        var R = function () { return edge('v', i + 1, j); };
        switch (idx) {
          case 1: case 14: link(L(), B()); break;
          case 2: case 13: link(B(), R()); break;
          case 3: case 12: link(L(), R()); break;
          case 4: case 11: link(T(), R()); break;
          case 5: link(T(), L()); link(B(), R()); break;
          case 6: case 9: link(T(), B()); break;
          case 7: case 8: link(T(), L()); break;
          case 10: link(T(), R()); link(L(), B()); break;
        }
      }
    }
    var used = new Set(), lines = [];
    function walk(start) {
      var line = [start], cur = start;
      used.add(start);
      for (;;) {
        var nxt = adj.get(cur).find(function (k) { return !used.has(k); });
        if (!nxt) break;
        used.add(nxt); line.push(nxt); cur = nxt;
      }
      var closed = line.length > 2 && adj.get(cur).indexOf(start) !== -1;
      lines.push({ pts: line.map(function (k) { return pts.get(k); }), closed: closed });
    }
    adj.forEach(function (n, k) { if (n.length === 1 && !used.has(k)) walk(k); });
    adj.forEach(function (n, k) { if (!used.has(k)) walk(k); });
    return lines;
  }

  /* ---------- palettes: [background, c1, c2, c3, c4] ---------- */
  var PALETTES = [
    { name: 'Sunny',   c: ['#ffc425', '#ff9f0a', '#ffb52e', '#e68600', '#fff1b8'] },
    { name: 'Sky',     c: ['#ffffff', '#00a8f0', '#7fd4f8', '#0a6fb0', '#e6f6fd'] },
    { name: 'Rose',    c: ['#ffffff', '#ff6f91', '#ffc2d1', '#c9184a', '#ffe5ec'] },
    { name: 'Cherry',  c: ['#8f0d18', '#e0202c', '#ff6a5e', '#5a060d', '#ffd1cc'] },
    { name: 'Graphite',c: ['#ffffff', '#9a9a9a', '#cfcfcf', '#555555', '#ededed'] },
    { name: 'Mint',    c: ['#f4fffb', '#17c3a0', '#7fe6cf', '#0c7a64', '#d8f7ef'] },
    { name: 'Violet',  c: ['#fbf8ff', '#8e44d6', '#c9a4ee', '#5b1fa6', '#efe4fb'] },
    { name: 'Navy Gold',c:['#0e1b3d', '#f5b700', '#3d5bd9', '#e8ecff', '#7a8cc9'] },
    { name: 'Lime',    c: ['#f7ffe0', '#8bd100', '#cdf26b', '#3f7d00', '#eaffb8'] },
    { name: 'Sunset',  c: ['#2b1055', '#ff5e62', '#ff9966', '#ffd36b', '#7a4fd6'] },
    { name: 'Ocean',   c: ['#04293a', '#1ea7c5', '#64e6d9', '#0b6e8c', '#bff3ee'] },
    { name: 'Peach',   c: ['#fff5ee', '#ff9a76', '#ffd1b8', '#e0603a', '#ffe8dc'] }
  ];

  /* ---------- patterns ---------- */
  var PATTERNS = [
    {
      id: 'burst', name: 'Twist Burst', pal: 0,
      colors: ['Ray A', 'Ray B', 'Dots'],
      params: [
        { key: 'rays', label: 'Rays', min: 6, max: 60, step: 1, def: 24 },
        { key: 'twist', label: 'Twist', min: -4, max: 4, step: 0.1, def: 1.8 },
        { key: 'cx', label: 'Center X', min: 0, max: 1, step: 0.01, def: 0.5 },
        { key: 'cy', label: 'Center Y', min: 0, max: 1, step: 0.01, def: 0.5 },
        { key: 'dots', label: 'Halftone dots', min: 0, max: 1, step: 0.05, def: 0.6 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col;
        var cx = p.cx * W, cy = p.cy * H;
        var R = Math.hypot(Math.max(cx, W - cx), Math.max(cy, H - cy)) * 1.08;
        var n = Math.round(p.rays), S = 36, step = TAU / n, rays = [];
        for (var i = 0; i < n; i++) {
          var a0 = i * step, a1 = a0 + step / 2, pts = [], s, t, a;
          for (s = 0; s <= S; s++) { t = s / S; a = a0 + p.twist * t; pts.push([cx + R * t * Math.cos(a), cy + R * t * Math.sin(a)]); }
          for (s = S; s >= 0; s--) { t = s / S; a = a1 + p.twist * t; pts.push([cx + R * t * Math.cos(a), cy + R * t * Math.sin(a)]); }
          rays.push('<path d="' + polyPath(pts, true) + '"/>');
        }
        var body = '<g id="Rays" fill="' + col[1] + '">' + rays.join('') + '</g>';
        var defs = '';
        if (p.dots > 0) {
          var g = W / 60, r = g * 0.24 * p.dots + 0.01;
          defs = '<pattern id="dots" width="' + f(g) + '" height="' + f(g) + '" patternUnits="userSpaceOnUse"><circle cx="' + f(g / 2) + '" cy="' + f(g / 2) + '" r="' + f(r) + '" fill="' + col[2] + '"/></pattern>';
          body += '<rect id="Halftone" width="' + W + '" height="' + H + '" fill="url(#dots)" opacity="0.55"/>';
        }
        return { body: body, defs: defs, meta: n + ' rays from one center' };
      }
    },
    {
      id: 'scales', name: 'Fish Scales', pal: 6,
      colors: ['Background', 'Ring color'],
      params: [
        { key: 'cols', label: 'Columns across', min: 4, max: 30, step: 1, def: 12 },
        { key: 'rings', label: 'Rings per scale', min: 3, max: 22, step: 1, def: 10 },
        { key: 'sw', label: 'Line weight', min: 0.4, max: 4, step: 0.1, def: 1.3 },
        { key: 'solid', label: 'Solid overlap', type: 'toggle', def: 1 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col;
        var cols = Math.round(p.cols), dx = W / cols, R = dx * 0.8, dy = dx * 0.38;
        var rows = Math.ceil(H / dy) + 3, out = [], rings = Math.round(p.rings);
        for (var row = -1; row < rows; row++) {
          var y = row * dy;
          for (var i = -1; i <= cols; i++) {
            var x = i * dx + ((row & 1) ? dx / 2 : 0), g = '';
            if (p.solid) g += '<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(R) + '" fill="' + col[0] + '" stroke="none"/>';
            for (var k = 1; k <= rings; k++) g += '<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(R * k / rings) + '"/>';
            out.push('<g>' + g + '</g>');
          }
        }
        return {
          body: '<g id="Scales" fill="none" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '">' + out.join('') + '</g>',
          defs: '', meta: cols + ' columns × ' + rows + ' rows, fitted to the artboard width'
        };
      }
    },
    {
      id: 'hex', name: 'Hex Tiles', pal: 4,
      colors: ['Background', 'Tile A', 'Tile B'],
      params: [
        { key: 'cols', label: 'Columns across', min: 4, max: 36, step: 1, def: 12 },
        { key: 'gap', label: 'Gap', min: 0, max: 14, step: 0.5, def: 3 },
        { key: 'var', label: 'Tone variation', min: 0, max: 1, step: 0.05, def: 0.7 }
      ],
      render: function (c) {
        var u = c.u, p = c.p, col = c.col, rnd = c.rnd;
        var cols = Math.round(p.cols), g = hexGrid(c.W, c.H, cols), r = g.r - p.gap * u * 0.5, out = [];
        g.cells.forEach(function (h) {
          var fill = mix(col[1], col[2], rnd() * p.var);
          out.push('<polygon points="' + hexPts(h.x, h.y, r).map(function (q) { return f(q[0]) + ',' + f(q[1]); }).join(' ') + '" fill="' + fill + '"/>');
        });
        return { body: '<g id="Tiles">' + out.join('') + '</g>', defs: '', meta: cols + ' columns × ' + g.rows + ' rows, fitted to the artboard width' };
      }
    },
    {
      id: 'cubes', name: 'Iso Cubes', pal: 3,
      colors: ['Gap color', 'Cube color'],
      params: [
        { key: 'cols', label: 'Columns across', min: 4, max: 36, step: 1, def: 14 },
        { key: 'gap', label: 'Gap', min: 0, max: 14, step: 0.5, def: 1.5 },
        { key: 'contrast', label: 'Face contrast', min: 0.05, max: 0.7, step: 0.01, def: 0.3 },
        { key: 'jitter', label: 'Per-cube jitter', min: 0, max: 0.4, step: 0.01, def: 0.08 }
      ],
      render: function (c) {
        var u = c.u, p = c.p, col = c.col, rnd = c.rnd;
        var cols = Math.round(p.cols), g = hexGrid(c.W, c.H, cols), r = g.r - p.gap * u * 0.5, out = [];
        var P = function (a) { return a.map(function (q) { return f(q[0]) + ',' + f(q[1]); }).join(' '); };
        g.cells.forEach(function (h) {
          var v = hexPts(h.x, h.y, r), ctr = [h.x, h.y];
          var s = (rnd() - 0.5) * 2 * p.jitter;
          var base = s > 0 ? lighten(col[1], s) : darken(col[1], -s);
          out.push('<g><polygon points="' + P([v[0], v[1], ctr, v[5]]) + '" fill="' + lighten(base, p.contrast) + '"/>' +
                   '<polygon points="' + P([v[5], ctr, v[3], v[4]]) + '" fill="' + base + '"/>' +
                   '<polygon points="' + P([v[1], v[2], v[3], ctr]) + '" fill="' + darken(base, p.contrast) + '"/></g>');
        });
        return { body: '<g id="Cubes">' + out.join('') + '</g>', defs: '', meta: cols + ' columns × ' + g.rows + ' rows, 3 faces per cube' };
      }
    },
    {
      id: 'contour', name: 'Contour Lines', pal: 4,
      colors: ['Background', 'Line color'],
      params: [
        { key: 'lines', label: 'Contour lines', min: 6, max: 60, step: 1, def: 28 },
        { key: 'blobs', label: 'Hills', min: 1, max: 10, step: 1, def: 5 },
        { key: 'wobble', label: 'Wobble', min: 0, max: 1, step: 0.05, def: 0.6 },
        { key: 'sw', label: 'Line weight', min: 0.3, max: 3, step: 0.1, def: 1 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, i, j;
        var cell = Math.max(W, H) / 190, gw = Math.ceil(W / cell), gh = Math.ceil(H / cell);
        var blobs = [], waves = [];
        for (i = 0; i < Math.round(p.blobs); i++) blobs.push({ x: rnd() * W, y: rnd() * H, s: (0.12 + rnd() * 0.2) * Math.min(W, H), a: 0.6 + rnd() * 0.4 });
        for (i = 0; i < 3; i++) waves.push({ fx: 1.5 + rnd() * 5, fy: 1.5 + rnd() * 5, ph: rnd() * TAU });
        var field = new Float32Array((gw + 1) * (gh + 1)), mn = Infinity, mx = -Infinity;
        for (j = 0; j <= gh; j++) {
          for (i = 0; i <= gw; i++) {
            var x = i * cell, y = j * cell, v = 0;
            blobs.forEach(function (b) { var dx = x - b.x, dy = y - b.y; v += b.a * Math.exp(-(dx * dx + dy * dy) / (2 * b.s * b.s)); });
            waves.forEach(function (w) { v += p.wobble * 0.12 * Math.sin(TAU * (w.fx * x / W + w.fy * y / H) + w.ph); });
            field[j * (gw + 1) + i] = v; if (v < mn) mn = v; if (v > mx) mx = v;
          }
        }
        var n = Math.round(p.lines), out = [];
        for (var k = 0; k < n; k++) {
          var level = mn + (mx - mn) * (k + 0.5) / n;
          var ls = contours(field, gw, gh, level, cell);
          var d = ls.map(function (l) { return smoothPath(l.pts, l.closed); }).join('');
          if (d) out.push('<path d="' + d + '"/>');
        }
        return { body: '<g id="Contours" fill="none" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '" stroke-linejoin="round">' + out.join('') + '</g>', defs: '', meta: n + ' levels, one compound path per level' };
      }
    },
    {
      id: 'plaid', name: 'Plaid Lines', pal: 1,
      colors: ['Background', 'Line 1', 'Line 2', 'Line 3', 'Line 4'],
      params: [
        { key: 'bundles', label: 'Bundles per direction', min: 2, max: 16, step: 1, def: 8 },
        { key: 'lines', label: 'Lines per bundle', min: 2, max: 16, step: 1, def: 8 },
        { key: 'angle', label: 'Angle', min: 0, max: 90, step: 1, def: 45 },
        { key: 'sw', label: 'Line weight', min: 0.3, max: 3, step: 0.1, def: 1 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, out = [], count = 0;
        var D = Math.hypot(W, H), a = p.angle * Math.PI / 180;
        for (var pass = 0; pass < 2; pass++) {
          var ang = a + pass * Math.PI / 2, dx = Math.cos(ang), dy = Math.sin(ang), nx = -dy, ny = dx;
          for (var b = 0; b < Math.round(p.bundles); b++) {
            var off = (rnd() - 0.5) * D, spread = (10 + rnd() * 70) * u;
            var color = col[1 + Math.floor(rnd() * (col.length - 1))];
            var ln = Math.round(p.lines), g = '';
            for (var l = 0; l < ln; l++) {
              var o = off + ((ln > 1 ? l / (ln - 1) : 0.5) - 0.5) * spread + (rnd() - 0.5) * spread * 0.15;
              var mx = W / 2 + nx * o, my = H / 2 + ny * o;
              g += '<line x1="' + f(mx - dx * D) + '" y1="' + f(my - dy * D) + '" x2="' + f(mx + dx * D) + '" y2="' + f(my + dy * D) + '" stroke-width="' + f((0.5 + rnd() * 1.2) * p.sw * u) + '"/>';
              count++;
            }
            out.push('<g stroke="' + color + '" stroke-opacity="0.85">' + g + '</g>');
          }
        }
        return { body: '<g id="Lines" fill="none">' + out.join('') + '</g>', defs: '', meta: count + ' separate line objects' };
      }
    },
    {
      id: 'bars', name: 'Soft Bars', pal: 4,
      colors: ['Background', 'Bar color', 'Bar color 2'],
      params: [
        { key: 'count', label: 'Bars', min: 4, max: 60, step: 1, def: 18 },
        { key: 'angle', label: 'Angle', min: -90, max: 90, step: 1, def: 35 },
        { key: 'spread', label: 'Angle spread', min: 0, max: 45, step: 1, def: 0 },
        { key: 'round', label: 'Roundness', min: 0, max: 1, step: 0.05, def: 0.7 },
        { key: 'opacity', label: 'Opacity range', min: 0.1, max: 0.9, step: 0.05, def: 0.45 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, out = [];
        for (var i = 0; i < Math.round(p.count); i++) {
          var w = (36 + rnd() * 120) * u, l = (320 + rnd() * 1100) * u;
          var x = rnd() * W, y = rnd() * H, ang = p.angle + (rnd() - 0.5) * 2 * p.spread;
          out.push('<rect x="' + f(-l / 2) + '" y="' + f(-w / 2) + '" width="' + f(l) + '" height="' + f(w) + '" rx="' + f(w * p.round / 2) +
            '" fill="' + mix(col[1], col[2], rnd()) + '" fill-opacity="' + f(0.12 + rnd() * p.opacity) +
            '" transform="translate(' + f(x) + ' ' + f(y) + ') rotate(' + f(ang) + ')"/>');
        }
        return { body: '<g id="Bars">' + out.join('') + '</g>', defs: '', meta: Math.round(p.count) + ' rounded rectangles' };
      }
    },
    {
      id: 'pinwheel', name: 'Pinwheel Tiles', pal: 0, defCols: ['#ff9a1f', '#ffffff', '#fff3c9'],
      colors: ['Background', 'Line color', 'Center square'],
      params: [
        { key: 'cols', label: 'Columns across', min: 3, max: 24, step: 1, def: 10 },
        { key: 'steps', label: 'Nested squares', min: 3, max: 16, step: 1, def: 9 },
        { key: 'ratio', label: 'Twist ratio', min: 0.04, max: 0.35, step: 0.01, def: 0.16 },
        { key: 'sw', label: 'Line weight', min: 0.3, max: 3, step: 0.1, def: 1 },
        { key: 'mirror', label: 'Mirror alternate tiles', type: 'toggle', def: 1 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col;
        var cols = Math.round(p.cols), cell = W / cols, rows = Math.ceil(H / cell), steps = Math.round(p.steps), out = [];
        for (var r = 0; r < rows; r++) {
          for (var cc = 0; cc < cols; cc++) {
            var mir = p.mirror && ((r + cc) & 1);
            var pts = [[0, 0], [cell, 0], [cell, cell], [0, cell]], polys = [];
            for (var s = 0; s < steps; s++) {
              polys.push({ pts: pts, last: s === steps - 1 });
              pts = pts.map(function (q, i) {
                var nx = pts[(i + 1) % 4];
                return [q[0] + (nx[0] - q[0]) * p.ratio, q[1] + (nx[1] - q[1]) * p.ratio];
              });
            }
            var g = polys.map(function (pl) {
              var s2 = pl.pts.map(function (q) { return f(q[0]) + ',' + f(q[1]); }).join(' ');
              return '<polygon points="' + s2 + '"' + (pl.last ? ' fill="' + col[2] + '"' : '') + '/>';
            }).join('');
            var tr = 'translate(' + f(cc * cell + (mir ? cell : 0)) + ' ' + f(r * cell) + ')' + (mir ? ' scale(-1 1)' : '');
            out.push('<g transform="' + tr + '">' + g + '</g>');
          }
        }
        return {
          body: '<g id="Tiles" fill="none" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '" stroke-linejoin="round">' + out.join('') + '</g>',
          defs: '', meta: cols + ' × ' + rows + ' tiles, fitted to the artboard width'
        };
      }
    },
    {
      id: 'ribbon', name: 'Wave Ribbon', pal: 2,
      colors: ['Background', 'Line start', 'Line end'],
      params: [
        { key: 'lines', label: 'Lines', min: 10, max: 100, step: 1, def: 46 },
        { key: 'amp', label: 'Wave height', min: 0.04, max: 0.4, step: 0.01, def: 0.2 },
        { key: 'waves', label: 'Waves', min: 0.5, max: 3, step: 0.1, def: 1.2 },
        { key: 'spread', label: 'Ribbon width', min: 0.1, max: 0.8, step: 0.01, def: 0.4 },
        { key: 'sw', label: 'Line weight', min: 0.3, max: 2.5, step: 0.1, def: 0.9 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, out = [];
        var ph = rnd() * TAU, ph2 = rnd() * TAU, n = Math.round(p.lines), S = 90;
        for (var k = 0; k < n; k++) {
          var t = k / (n - 1), pts = [];
          for (var s = 0; s <= S; s++) {
            var x = -0.05 * W + 1.1 * W * s / S, q = x / W;
            var base = H / 2 + p.amp * H * Math.sin(TAU * p.waves * q + ph);
            var tw = Math.cos(TAU * p.waves * q * 0.9 + ph2);
            pts.push([x, base + (t - 0.5) * p.spread * H * tw]);
          }
          out.push('<path d="' + smoothPath(pts, false) + '" stroke="' + mix(col[1], col[2], t) + '"/>');
        }
        return { body: '<g id="Ribbon" fill="none" stroke-width="' + f(p.sw * u) + '" stroke-opacity="0.9">' + out.join('') + '</g>', defs: '', meta: n + ' curved lines, blended start to end' };
      }
    },
    {
      id: 'dots', name: 'Polka Dots', pal: 2,
      colors: ['Background', 'Dot A', 'Dot B'],
      params: [
        { key: 'cols', label: 'Columns across', min: 3, max: 40, step: 1, def: 14 },
        { key: 'size', label: 'Dot size', min: 0.15, max: 1, step: 0.01, def: 0.6 },
        { key: 'vary', label: 'Size variation', min: 0, max: 0.8, step: 0.05, def: 0.2 },
        { key: 'stagger', label: 'Staggered rows', type: 'toggle', def: 1 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, cols = Math.round(p.cols), cell = W / cols;
        var dy = p.stagger ? cell * 0.866 : cell, rows = Math.ceil(H / dy) + 2, out = [];
        for (var r = -1; r < rows; r++) for (var i = -1; i <= cols; i++) {
          var x = i * cell + cell / 2 + ((p.stagger && (r & 1)) ? cell / 2 : 0), y = r * dy + cell / 2;
          out.push('<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(cell / 2 * p.size * (1 - rnd() * p.vary)) + '" fill="' + (((r + i) & 1) ? col[1] : col[2]) + '"/>');
        }
        return { body: '<g id="Dots">' + out.join('') + '</g>', defs: '', meta: cols + ' columns × ' + rows + ' rows' };
      }
    },
    {
      id: 'lowpoly', name: 'Low Poly', pal: 1,
      colors: ['Background', 'Color start', 'Color end'],
      params: [
        { key: 'cols', label: 'Columns across', min: 4, max: 30, step: 1, def: 12 },
        { key: 'jitter', label: 'Point jitter', min: 0, max: 0.45, step: 0.01, def: 0.3 },
        { key: 'tone', label: 'Tone noise', min: 0, max: 0.6, step: 0.01, def: 0.25 },
        { key: 'angle', label: 'Gradient angle', min: 0, max: 360, step: 1, def: 45 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, cols = Math.round(p.cols), cell = W / cols;
        var rows = Math.ceil(H / cell), P = [], out = [], a = p.angle * Math.PI / 180, D = Math.hypot(W, H);
        for (var j = 0; j <= rows; j++) { P[j] = []; for (var i = 0; i <= cols; i++) {
          var jx = (i === 0 || i === cols) ? 0 : (rnd() - 0.5) * 2 * p.jitter * cell;
          var jy = (j === 0 || j === rows) ? 0 : (rnd() - 0.5) * 2 * p.jitter * cell;
          P[j][i] = [i * cell + jx, j * cell + jy];
        } }
        function tri(A, B, C) {
          var cx = (A[0] + B[0] + C[0]) / 3, cy = (A[1] + B[1] + C[1]) / 3;
          var t = ((cx - W / 2) * Math.cos(a) + (cy - H / 2) * Math.sin(a)) / D + 0.5 + (rnd() - 0.5) * p.tone;
          t = Math.max(0, Math.min(1, t));
          var fl = mix(col[1], col[2], t);
          out.push('<polygon points="' + [A, B, C].map(function (q) { return f(q[0]) + ',' + f(q[1]); }).join(' ') + '" fill="' + fl + '" stroke="' + fl + '" stroke-width="0.6"/>');
        }
        for (j = 0; j < rows; j++) for (i = 0; i < cols; i++) {
          var A = P[j][i], B = P[j][i + 1], C = P[j + 1][i + 1], Dd = P[j + 1][i];
          if ((i + j) & 1) { tri(A, B, Dd); tri(B, C, Dd); } else { tri(A, B, C); tri(A, C, Dd); }
        }
        return { body: '<g id="Triangles">' + out.join('') + '</g>', defs: '', meta: out.length + ' triangles, fitted to the artboard' };
      }
    },
    {
      id: 'argyle', name: 'Argyle Diamonds', pal: 7,
      colors: ['Gap color', 'Diamond A', 'Diamond B', 'Line'],
      params: [
        { key: 'cols', label: 'Columns across', min: 2, max: 24, step: 1, def: 8 },
        { key: 'tall', label: 'Diamond height', min: 0.8, max: 2.4, step: 0.05, def: 1.5 },
        { key: 'gap', label: 'Gap', min: 0, max: 10, step: 0.5, def: 0 },
        { key: 'sw', label: 'Line weight', min: 0, max: 3, step: 0.1, def: 1 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, cols = Math.round(p.cols), w = W / cols, h = w * p.tall;
        var rows = Math.ceil(H / h) + 2, out = [], hw = w / 2 - p.gap * u, hh = h / 2 - p.gap * u * p.tall;
        function dia(x, y, fill) {
          out.push('<polygon points="' + f(x) + ',' + f(y - hh) + ' ' + f(x + hw) + ',' + f(y) + ' ' + f(x) + ',' + f(y + hh) + ' ' + f(x - hw) + ',' + f(y) + '" fill="' + fill + '"/>');
        }
        for (var j = -1; j < rows; j++) for (var i = -1; i <= cols; i++) { dia(i * w, j * h, col[1]); dia(i * w + w / 2, j * h + h / 2, col[2]); }
        return { body: '<g id="Diamonds" stroke="' + col[3] + '" stroke-width="' + f(p.sw * u) + '" stroke-linejoin="round">' + out.join('') + '</g>', defs: '', meta: cols + ' diamonds across, fitted to the artboard width' };
      }
    },
    {
      id: 'chevron', name: 'Chevron Stripes', pal: 3,
      colors: ['Background', 'Stripe A', 'Stripe B'],
      params: [
        { key: 'zigs', label: 'Zigzags across', min: 2, max: 30, step: 1, def: 10 },
        { key: 'bands', label: 'Stripes down', min: 3, max: 30, step: 1, def: 12 },
        { key: 'amp', label: 'Zigzag depth', min: 0, max: 2, step: 0.05, def: 0.8 },
        { key: 'thick', label: 'Stripe thickness', min: 0.2, max: 1, step: 0.05, def: 0.5 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, zigs = Math.round(p.zigs), bands = Math.round(p.bands);
        var bh = H / bands, zw = W / zigs, amp = p.amp * bh, out = [];
        for (var b = -2; b < bands + 2; b++) {
          var top = [], bot = [];
          for (var k = 0; k <= zigs * 2; k++) {
            var x = k * zw / 2, y = b * bh + ((k & 1) ? amp : 0);
            top.push([x, y]); bot.push([x, y + bh * p.thick]);
          }
          out.push('<path d="' + polyPath(top.concat(bot.reverse()), true) + '" fill="' + ((b & 1) ? col[1] : col[2]) + '"/>');
        }
        return { body: '<g id="Chevrons">' + out.join('') + '</g>', defs: '', meta: bands + ' stripes, ' + zigs + ' zigzags' };
      }
    },
    {
      id: 'rings', name: 'Concentric Rings', pal: 1,
      colors: ['Background', 'Ring A', 'Ring B'],
      params: [
        { key: 'rings', label: 'Rings', min: 4, max: 60, step: 1, def: 22 },
        { key: 'cx', label: 'Center X', min: 0, max: 1, step: 0.01, def: 0.5 },
        { key: 'cy', label: 'Center Y', min: 0, max: 1, step: 0.01, def: 0.5 },
        { key: 'squash', label: 'Squash', min: 0.4, max: 1.6, step: 0.05, def: 1 },
        { key: 'sw', label: 'Line weight', min: 0.3, max: 8, step: 0.1, def: 2 },
        { key: 'filled', label: 'Filled bands', type: 'toggle', def: 1 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, cx = p.cx * W, cy = p.cy * H, n = Math.round(p.rings), out = [];
        var R = Math.hypot(Math.max(cx, W - cx), Math.max(cy, H - cy)) * 1.05 / Math.min(1, p.squash);
        for (var k = n; k >= 1; k--) {
          var r = R * k / n, fl = p.filled ? ((k & 1) ? col[1] : col[2]) : 'none';
          out.push('<ellipse cx="' + f(cx) + '" cy="' + f(cy) + '" rx="' + f(r) + '" ry="' + f(r * p.squash) + '" fill="' + fl + '"/>');
        }
        return { body: '<g id="Rings" stroke="' + (p.filled ? 'none' : col[1]) + '" stroke-width="' + f(p.sw * u) + '">' + out.join('') + '</g>', defs: '', meta: n + ' rings from one center' };
      }
    },
    {
      id: 'spiral', name: 'Spiral Stripes', pal: 9,
      colors: ['Background', 'Arm A', 'Arm B'],
      params: [
        { key: 'arms', label: 'Arms', min: 1, max: 16, step: 1, def: 6 },
        { key: 'coils', label: 'Coils to edge', min: 2, max: 16, step: 1, def: 6 },
        { key: 'thick', label: 'Arm thickness', min: 0.2, max: 1, step: 0.05, def: 0.7 },
        { key: 'cx', label: 'Center X', min: 0, max: 1, step: 0.01, def: 0.5 },
        { key: 'cy', label: 'Center Y', min: 0, max: 1, step: 0.01, def: 0.5 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, cx = p.cx * W, cy = p.cy * H, arms = Math.round(p.arms), coils = p.coils, out = [];
        var R = Math.hypot(Math.max(cx, W - cx), Math.max(cy, H - cy)) * 1.08, pitch = R / coils, gap = pitch / arms;
        var steps = Math.ceil(coils * 48);
        for (var k = 0; k < arms; k++) {
          var A = [], B = [];
          for (var s = 0; s <= steps; s++) {
            var th = coils * TAU * s / steps, r1 = pitch * th / TAU + k * gap, r2 = r1 + gap * p.thick;
            A.push([cx + r1 * Math.cos(th), cy + r1 * Math.sin(th)]); B.push([cx + r2 * Math.cos(th), cy + r2 * Math.sin(th)]);
          }
          out.push('<path d="' + polyPath(A.concat(B.reverse()), true) + '" fill="' + ((k & 1) ? col[2] : col[1]) + '"/>');
        }
        return { body: '<g id="Spiral">' + out.join('') + '</g>', defs: '', meta: arms + ' spiral arms' };
      }
    },
    {
      id: 'layers', name: 'Layered Waves', pal: 5,
      colors: ['Sky', 'Layer start', 'Layer end'],
      params: [
        { key: 'layers', label: 'Layers', min: 3, max: 16, step: 1, def: 8 },
        { key: 'amp', label: 'Wave height', min: 0.01, max: 0.15, step: 0.005, def: 0.06 },
        { key: 'freq', label: 'Waves', min: 0.5, max: 4, step: 0.1, def: 1.6 },
        { key: 'drift', label: 'Layer drift', min: 0, max: 3, step: 0.1, def: 0.8 },
        { key: 'top', label: 'Start height', min: 0, max: 0.6, step: 0.01, def: 0.2 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, n = Math.round(p.layers), ph = rnd() * TAU, out = [];
        for (var k = 0; k < n; k++) {
          var t = n > 1 ? k / (n - 1) : 0, base = H * (p.top + (1 - p.top) * k / n), pts = [];
          for (var s = 0; s <= 60; s++) { var x = W * s / 60; pts.push([x, base + p.amp * H * Math.sin(TAU * p.freq * x / W + p.drift * k + ph)]); }
          out.push('<path d="' + smoothPath(pts, false) + 'L' + f(W) + ' ' + f(H + 10) + 'L0 ' + f(H + 10) + 'Z" fill="' + mix(col[1], col[2], t) + '"/>');
        }
        return { body: '<g id="Layers">' + out.join('') + '</g>', defs: '', meta: n + ' stacked wave layers' };
      }
    },
    {
      id: 'truchet', name: 'Truchet Arcs', pal: 10,
      colors: ['Background', 'Arc A', 'Arc B'],
      params: [
        { key: 'cols', label: 'Columns across', min: 4, max: 30, step: 1, def: 14 },
        { key: 'sw', label: 'Arc thickness', min: 0.05, max: 0.45, step: 0.01, def: 0.2 },
        { key: 'duo', label: 'Two-tone checker', type: 'toggle', def: 1 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, cols = Math.round(p.cols), cell = W / cols, rows = Math.ceil(H / cell), out = [];
        for (var j = 0; j < rows; j++) for (var i = 0; i < cols; i++) {
          var x = i * cell, y = j * cell, h = cell / 2, d;
          if (rnd() > 0.5) d = 'M' + f(x + h) + ' ' + f(y) + 'A' + f(h) + ' ' + f(h) + ' 0 0 1 ' + f(x) + ' ' + f(y + h) + 'M' + f(x + h) + ' ' + f(y + cell) + 'A' + f(h) + ' ' + f(h) + ' 0 0 1 ' + f(x + cell) + ' ' + f(y + h);
          else d = 'M' + f(x + cell) + ' ' + f(y + h) + 'A' + f(h) + ' ' + f(h) + ' 0 0 1 ' + f(x + h) + ' ' + f(y) + 'M' + f(x) + ' ' + f(y + h) + 'A' + f(h) + ' ' + f(h) + ' 0 0 1 ' + f(x + h) + ' ' + f(y + cell);
          out.push('<path d="' + d + '" stroke="' + ((p.duo && ((i + j) & 1)) ? col[2] : col[1]) + '"/>');
        }
        return { body: '<g id="Arcs" fill="none" stroke-width="' + f(cell * p.sw) + '">' + out.join('') + '</g>', defs: '', meta: cols + ' × ' + rows + ' tiles with random orientation' };
      }
    },
    {
      id: 'confetti', name: 'Memphis Confetti', pal: 9,
      colors: ['Background', 'Shape 1', 'Shape 2', 'Shape 3', 'Shape 4'],
      params: [
        { key: 'count', label: 'Shapes', min: 20, max: 300, step: 1, def: 90 },
        { key: 'size', label: 'Size', min: 0.5, max: 2, step: 0.05, def: 1 },
        { key: 'sw', label: 'Line weight', min: 1, max: 8, step: 0.5, def: 3.5 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, placed = [], out = [];
        for (var n = 0; n < Math.round(p.count); n++) {
          var s = (16 + rnd() * 30) * u * p.size, x, y, ok = false, tries = 0;
          while (!ok && tries++ < 14) { x = rnd() * W; y = rnd() * H; ok = placed.every(function (q) { return Math.hypot(q[0] - x, q[1] - y) > (q[2] + s) * 0.9; }); }
          if (!ok) continue; placed.push([x, y, s]);
          var color = col[1 + Math.floor(rnd() * (col.length - 1))], t = Math.floor(rnd() * 6), rot = f(rnd() * 360);
          var tr = ' transform="translate(' + f(x) + ' ' + f(y) + ') rotate(' + rot + ')"', sh;
          if (t === 0) sh = '<circle r="' + f(s / 2) + '" fill="' + color + '" transform="translate(' + f(x) + ' ' + f(y) + ')"/>';
          else if (t === 1) sh = '<circle r="' + f(s / 2) + '" fill="none" stroke="' + color + '" stroke-width="' + f(p.sw * u) + '" transform="translate(' + f(x) + ' ' + f(y) + ')"/>';
          else if (t === 2) sh = '<rect x="' + f(-s / 2) + '" y="' + f(-s / 2) + '" width="' + f(s) + '" height="' + f(s) + '" fill="' + color + '"' + tr + '/>';
          else if (t === 3) sh = '<polygon points="0,' + f(-s / 2) + ' ' + f(s / 2) + ',' + f(s / 2) + ' ' + f(-s / 2) + ',' + f(s / 2) + '" fill="' + color + '"' + tr + '/>';
          else if (t === 4) sh = '<path d="M' + f(-s / 2) + ' 0H' + f(s / 2) + 'M0 ' + f(-s / 2) + 'V' + f(s / 2) + '" fill="none" stroke="' + color + '" stroke-width="' + f(p.sw * u) + '"' + tr + '/>';
          else { var a = s * 0.25; sh = '<path d="M' + f(-s) + ' 0q' + f(a) + ' ' + f(-a) + ' ' + f(2 * a) + ' 0t' + f(2 * a) + ' 0t' + f(2 * a) + ' 0t' + f(2 * a) + ' 0" fill="none" stroke="' + color + '" stroke-width="' + f(p.sw * u) + '" stroke-linecap="round"' + tr + '/>'; }
          out.push(sh);
        }
        return { body: '<g id="Confetti">' + out.join('') + '</g>', defs: '', meta: out.length + ' separate shapes, no overlaps' };
      }
    },
    {
      id: 'halftone', name: 'Halftone Gradient', pal: 6,
      colors: ['Background', 'Dot color'],
      params: [
        { key: 'cols', label: 'Columns across', min: 10, max: 70, step: 1, def: 40 },
        { key: 'angle', label: 'Direction', min: 0, max: 360, step: 1, def: 35 },
        { key: 'min', label: 'Smallest dot', min: 0, max: 0.5, step: 0.01, def: 0.08 },
        { key: 'max', label: 'Largest dot', min: 0.4, max: 1.1, step: 0.01, def: 0.95 },
        { key: 'stagger', label: 'Staggered rows', type: 'toggle', def: 1 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, cols = Math.round(p.cols), cell = W / cols, a = p.angle * Math.PI / 180, D = Math.hypot(W, H) / 2;
        var dy = p.stagger ? cell * 0.866 : cell, rows = Math.ceil(H / dy) + 1, out = [];
        for (var r = 0; r < rows; r++) for (var i = 0; i <= cols; i++) {
          var x = i * cell + ((p.stagger && (r & 1)) ? cell / 2 : 0), y = r * dy + cell / 2;
          var t = Math.max(0, Math.min(1, ((x - W / 2) * Math.cos(a) + (y - H / 2) * Math.sin(a)) / D * 0.5 + 0.5));
          var rad = cell / 2 * (p.min + (p.max - p.min) * t);
          if (rad > 0.2) out.push('<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(rad) + '"/>');
        }
        return { body: '<g id="Dots" fill="' + col[1] + '">' + out.join('') + '</g>', defs: '', meta: out.length + ' dots sized along a gradient' };
      }
    },
    {
      id: 'blobs', name: 'Soft Blobs', pal: 2,
      colors: ['Background', 'Blob 1', 'Blob 2', 'Blob 3'],
      params: [
        { key: 'count', label: 'Blobs', min: 3, max: 18, step: 1, def: 8 },
        { key: 'size', label: 'Size', min: 0.1, max: 0.5, step: 0.01, def: 0.25 },
        { key: 'wobble', label: 'Wobble', min: 0.05, max: 0.5, step: 0.01, def: 0.25 },
        { key: 'opacity', label: 'Opacity', min: 0.2, max: 1, step: 0.05, def: 0.7 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, out = [], m = Math.min(W, H);
        for (var n = 0; n < Math.round(p.count); n++) {
          var cx = rnd() * W, cy = rnd() * H, r = p.size * m * (0.5 + rnd()), pts = [], ph = rnd() * TAU;
          for (var k = 0; k < 8; k++) { var rr = r * (1 + (rnd() - 0.5) * 2 * p.wobble), a = ph + k * TAU / 8; pts.push([cx + rr * Math.cos(a), cy + rr * Math.sin(a)]); }
          out.push('<path d="' + smoothPath(pts, true) + '" fill="' + col[1 + Math.floor(rnd() * 3)] + '" fill-opacity="' + f(p.opacity) + '"/>');
        }
        return { body: '<g id="Blobs">' + out.join('') + '</g>', defs: '', meta: out.length + ' smooth closed paths' };
      }
    },
    {
      id: 'stripes', name: 'Candy Stripes', pal: 0,
      colors: ['Background', 'Stripe A', 'Stripe B'],
      params: [
        { key: 'count', label: 'Stripes', min: 4, max: 60, step: 1, def: 18 },
        { key: 'angle', label: 'Angle', min: 0, max: 180, step: 1, def: 45 },
        { key: 'thick', label: 'A / B ratio', min: 0.15, max: 0.85, step: 0.01, def: 0.5 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, n = Math.round(p.count), D = Math.hypot(W, H), w = D / n, out = [];
        for (var k = 0; k < n; k++) {
          var x = -D / 2 + k * w;
          out.push('<rect x="' + f(x) + '" y="' + f(-D) + '" width="' + f(w * p.thick + 0.5) + '" height="' + f(2 * D) + '" fill="' + col[1] + '"/>');
          out.push('<rect x="' + f(x + w * p.thick) + '" y="' + f(-D) + '" width="' + f(w * (1 - p.thick) + 0.5) + '" height="' + f(2 * D) + '" fill="' + col[2] + '"/>');
        }
        return { body: '<g id="Stripes" transform="translate(' + f(W / 2) + ' ' + f(H / 2) + ') rotate(' + f(p.angle) + ')">' + out.join('') + '</g>', defs: '', meta: n + ' stripe pairs' };
      }
    },
    {
      id: 'stars', name: 'Star Grid', pal: 7,
      colors: ['Background', 'Star A', 'Star B'],
      params: [
        { key: 'cols', label: 'Columns across', min: 3, max: 20, step: 1, def: 8 },
        { key: 'points', label: 'Points', min: 4, max: 12, step: 1, def: 5 },
        { key: 'inner', label: 'Inner radius', min: 0.2, max: 0.8, step: 0.01, def: 0.45 },
        { key: 'size', label: 'Size', min: 0.4, max: 1.2, step: 0.01, def: 0.85 },
        { key: 'spin', label: 'Random rotation', min: 0, max: 1, step: 0.05, def: 0 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, cols = Math.round(p.cols), cell = W / cols, dy = cell * 0.866, rows = Math.ceil(H / dy) + 2, n = Math.round(p.points), out = [];
        for (var r = -1; r < rows; r++) for (var i = -1; i <= cols; i++) {
          var x = i * cell + cell / 2 + ((r & 1) ? cell / 2 : 0), y = r * dy + cell / 2, R = cell / 2 * p.size, rot = -Math.PI / 2 + rnd() * p.spin * TAU / n, pts = [];
          for (var k = 0; k < n * 2; k++) { var rr = (k & 1) ? R * p.inner : R, a = rot + k * Math.PI / n; pts.push(f(x + rr * Math.cos(a)) + ',' + f(y + rr * Math.sin(a))); }
          out.push('<polygon points="' + pts.join(' ') + '" fill="' + (((r + i) & 1) ? col[1] : col[2]) + '"/>');
        }
        return { body: '<g id="Stars">' + out.join('') + '</g>', defs: '', meta: cols + ' columns × ' + rows + ' rows' };
      }
    },
    {
      id: 'mosaic', name: 'Pixel Mosaic', pal: 10,
      colors: ['Background', 'Tone 1', 'Tone 2', 'Tone 3'],
      params: [
        { key: 'cols', label: 'Columns across', min: 6, max: 60, step: 1, def: 24 },
        { key: 'gap', label: 'Gap', min: 0, max: 8, step: 0.5, def: 1 },
        { key: 'round', label: 'Roundness', min: 0, max: 0.5, step: 0.01, def: 0 },
        { key: 'chaos', label: 'Randomness', min: 0, max: 1, step: 0.05, def: 0.35 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, cols = Math.round(p.cols), cell = W / cols, rows = Math.ceil(H / cell), out = [], ph = rnd() * TAU, g = p.gap * u;
        for (var j = 0; j < rows; j++) for (var i = 0; i < cols; i++) {
          var x = i * cell, y = j * cell;
          var t = 0.5 + 0.5 * Math.sin(TAU * (x / W * 1.3 + y / H * 0.8) + ph) + (rnd() - 0.5) * p.chaos;
          t = Math.max(0, Math.min(1, t));
          var fl = t < 0.5 ? mix(col[1], col[2], t * 2) : mix(col[2], col[3], (t - 0.5) * 2);
          out.push('<rect x="' + f(x + g / 2) + '" y="' + f(y + g / 2) + '" width="' + f(cell - g) + '" height="' + f(cell - g) + '" rx="' + f(cell * p.round) + '" fill="' + fl + '"/>');
        }
        return { body: '<g id="Mosaic">' + out.join('') + '</g>', defs: '', meta: cols + ' × ' + rows + ' squares, fitted to the artboard width' };
      }
    },
    {
      id: 'bricks', name: 'Brick Rows', pal: 11,
      colors: ['Gap color', 'Brick A', 'Brick B'],
      params: [
        { key: 'cols', label: 'Bricks across', min: 3, max: 24, step: 1, def: 8 },
        { key: 'ratio', label: 'Brick height', min: 0.15, max: 0.6, step: 0.01, def: 0.35 },
        { key: 'gap', label: 'Gap', min: 0, max: 10, step: 0.5, def: 3 },
        { key: 'round', label: 'Roundness', min: 0, max: 0.5, step: 0.01, def: 0.15 },
        { key: 'vary', label: 'Tone variation', min: 0, max: 1, step: 0.05, def: 0.6 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, cols = Math.round(p.cols), w = W / cols, h = w * p.ratio, rows = Math.ceil(H / h) + 1, out = [], g = p.gap * u;
        for (var r = 0; r < rows; r++) for (var i = -1; i <= cols; i++) {
          var x = i * w + ((r & 1) ? w / 2 : 0), y = r * h;
          out.push('<rect x="' + f(x + g / 2) + '" y="' + f(y + g / 2) + '" width="' + f(w - g) + '" height="' + f(h - g) + '" rx="' + f(h * p.round) + '" fill="' + mix(col[1], col[2], rnd() * p.vary) + '"/>');
        }
        return { body: '<g id="Bricks">' + out.join('') + '</g>', defs: '', meta: cols + ' bricks across, ' + rows + ' rows' };
      }
    },
    {
      id: 'rosette', name: 'Rosette Tiles', pal: 6,
      colors: ['Background', 'Petal A', 'Petal B', 'Petal C'],
      params: [
        { key: 'cols', label: 'Columns across', min: 2, max: 12, step: 1, def: 5 },
        { key: 'petals', label: 'Petals', min: 4, max: 18, step: 1, def: 10 },
        { key: 'layers', label: 'Layers', min: 1, max: 5, step: 1, def: 3 },
        { key: 'size', label: 'Size', min: 0.5, max: 1.1, step: 0.01, def: 0.9 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, cols = Math.round(p.cols), cell = W / cols, rows = Math.ceil(H / cell), n = Math.round(p.petals), L = Math.round(p.layers), out = [];
        for (var r = 0; r < rows; r++) for (var i = 0; i < cols; i++) {
          var R = cell / 2 * p.size, g = '';
          for (var l = 0; l < L; l++) {
            var s = 1 - l * (0.7 / L), rot0 = l * 180 / n;
            for (var k = 0; k < n; k++) g += '<ellipse cx="0" cy="' + f(-R * 0.5 * s) + '" rx="' + f(R * 0.2 * s) + '" ry="' + f(R * 0.5 * s) + '" fill="' + col[1 + (l % 3)] + '" transform="rotate(' + f(rot0 + k * 360 / n) + ')"/>';
          }
          out.push('<g transform="translate(' + f(i * cell + cell / 2) + ' ' + f(r * cell + cell / 2) + ')" fill-opacity="0.85">' + g + '</g>');
        }
        return { body: '<g id="Rosettes">' + out.join('') + '</g>', defs: '', meta: cols + ' × ' + rows + ' rosette tiles' };
      }
    },
    {
      id: 'orbs', name: 'Gradient Orbs', pal: 9,
      colors: ['Background', 'Orb 1', 'Orb 2', 'Orb 3', 'Orb 4'],
      params: [
        { key: 'count', label: 'Orbs', min: 3, max: 16, step: 1, def: 7 },
        { key: 'size', label: 'Size', min: 0.15, max: 0.6, step: 0.01, def: 0.35 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, n = Math.round(p.count), defs = '', out = [], m = Math.min(W, H);
        for (var k = 0; k < n; k++) {
          var color = col[1 + Math.floor(rnd() * 4)], r = p.size * m * (0.5 + rnd() * 0.8);
          defs += '<radialGradient id="orb' + k + '"><stop offset="0" stop-color="' + color + '" stop-opacity="0.95"/><stop offset="1" stop-color="' + color + '" stop-opacity="0"/></radialGradient>';
          out.push('<circle cx="' + f(rnd() * W) + '" cy="' + f(rnd() * H) + '" r="' + f(r) + '" fill="url(#orb' + k + ')"/>');
        }
        return { body: '<g id="Orbs">' + out.join('') + '</g>', defs: defs, meta: n + ' radial gradient circles' };
      }
    },
    {
      id: 'grid', name: 'Graph Grid', pal: 1,
      colors: ['Background', 'Minor lines', 'Major lines'],
      params: [
        { key: 'cols', label: 'Columns across', min: 4, max: 60, step: 1, def: 24 },
        { key: 'major', label: 'Major line every', min: 2, max: 10, step: 1, def: 4 },
        { key: 'sw', label: 'Line weight', min: 0.3, max: 3, step: 0.1, def: 0.8 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, cols = Math.round(p.cols), cell = W / cols, rows = Math.ceil(H / cell), mj = Math.round(p.major), a = '', b = '';
        for (var i = 0; i <= cols; i++) { var l = '<line x1="' + f(i * cell) + '" y1="0" x2="' + f(i * cell) + '" y2="' + f(H) + '"/>'; if (i % mj === 0) b += l; else a += l; }
        for (var j = 0; j <= rows; j++) { var m = '<line x1="0" y1="' + f(j * cell) + '" x2="' + f(W) + '" y2="' + f(j * cell) + '"/>'; if (j % mj === 0) b += m; else a += m; }
        return { body: '<g id="Minor" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '">' + a + '</g><g id="Major" stroke="' + col[2] + '" stroke-width="' + f(p.sw * u * 1.8) + '">' + b + '</g>', defs: '', meta: cols + ' × ' + rows + ' cells' };
      }
    },
    {
      id: 'wavylines', name: 'Wavy Lines', pal: 10,
      colors: ['Background', 'Line start', 'Line end'],
      params: [
        { key: 'lines', label: 'Lines', min: 4, max: 60, step: 1, def: 24 },
        { key: 'amp', label: 'Wave height', min: 0.005, max: 0.1, step: 0.005, def: 0.03 },
        { key: 'freq', label: 'Waves', min: 0.5, max: 8, step: 0.1, def: 3 },
        { key: 'shift', label: 'Line shift', min: 0, max: 3, step: 0.1, def: 0.4 },
        { key: 'sw', label: 'Line weight', min: 0.5, max: 6, step: 0.1, def: 2 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, n = Math.round(p.lines), ph = rnd() * TAU, out = [];
        for (var k = 0; k < n; k++) {
          var t = n > 1 ? k / (n - 1) : 0, y0 = H * (k + 0.5) / n, pts = [];
          for (var s = 0; s <= 70; s++) { var x = -0.05 * W + 1.1 * W * s / 70; pts.push([x, y0 + p.amp * H * Math.sin(TAU * p.freq * x / W + ph + p.shift * k)]); }
          out.push('<path d="' + smoothPath(pts, false) + '" stroke="' + mix(col[1], col[2], t) + '"/>');
        }
        return { body: '<g id="Lines" fill="none" stroke-linecap="round" stroke-width="' + f(p.sw * u) + '">' + out.join('') + '</g>', defs: '', meta: n + ' parallel wavy lines' };
      }
    },
    {
      id: 'bubbles', name: 'Soft Bubbles', cat: 'Shapes', pal: 5,
      colors: ['Background', 'Bubble 1', 'Bubble 2', 'Bubble 3'],
      params: [
        { key: 'count', label: 'Bubbles', min: 5, max: 90, step: 1, def: 26 },
        { key: 'size', label: 'Largest size', min: 0.04, max: 0.4, step: 0.01, def: 0.18 },
        { key: 'opacity', label: 'Opacity range', min: 0.1, max: 0.9, step: 0.05, def: 0.5 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, out = [], m = Math.min(W, H), n = Math.round(p.count);
        for (var i = 0; i < n; i++) {
          var r = m * p.size * (0.25 + 0.75 * rnd());
          out.push('<circle cx="' + f(rnd() * W) + '" cy="' + f(rnd() * H) + '" r="' + f(r) + '" fill="' + col[1 + (i % 3)] + '" fill-opacity="' + f(0.15 + rnd() * p.opacity) + '"/>');
        }
        return { body: '<g id="Bubbles">' + out.join('') + '</g>', defs: '', meta: n + ' translucent circles' };
      }
    },
    {
      id: 'guilloche', name: 'Spiro Rosette', cat: 'Radial', pal: 6,
      colors: ['Background', 'Line start', 'Line end'],
      params: [
        { key: 'count', label: 'Ellipses', min: 10, max: 160, step: 1, def: 60 },
        { key: 'ratio', label: 'Ellipse ratio', min: 0.05, max: 1, step: 0.01, def: 0.35 },
        { key: 'span', label: 'Rotation span', min: 30, max: 360, step: 5, def: 180 },
        { key: 'size', label: 'Size', min: 0.3, max: 1.3, step: 0.02, def: 0.8 },
        { key: 'sw', label: 'Line weight', min: 0.3, max: 2.5, step: 0.1, def: 0.8 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, out = [], n = Math.round(p.count);
        var rx = Math.hypot(W, H) * 0.28 * p.size, ry = rx * p.ratio, cx = W / 2, cy = H / 2;
        for (var k = 0; k < n; k++) {
          var t = n > 1 ? k / (n - 1) : 0;
          out.push('<ellipse cx="' + f(cx) + '" cy="' + f(cy) + '" rx="' + f(rx) + '" ry="' + f(ry) + '" stroke="' + mix(col[1], col[2], t) + '" transform="rotate(' + f(t * p.span) + ' ' + f(cx) + ' ' + f(cy) + ')"/>');
        }
        return { body: '<g id="Rosette" fill="none" stroke-width="' + f(p.sw * u) + '">' + out.join('') + '</g>', defs: '', meta: n + ' rotated ellipses' };
      }
    },
    {
      id: 'honeycomb', name: 'Honeycomb Lines', cat: 'Tiles', pal: 10,
      colors: ['Background', 'Line color', 'Fill color'],
      params: [
        { key: 'cols', label: 'Columns across', min: 4, max: 30, step: 1, def: 12 },
        { key: 'sw', label: 'Line weight', min: 0.4, max: 6, step: 0.1, def: 1.6 },
        { key: 'fill', label: 'Filled cells', min: 0, max: 1, step: 0.05, def: 0.25 }
      ],
      render: function (c) {
        var u = c.u, p = c.p, col = c.col, rnd = c.rnd, out = [], cols = Math.round(p.cols), g = hexGrid(c.W, c.H, cols);
        g.cells.forEach(function (h) {
          var fl = rnd() < p.fill ? ' fill="' + col[2] + '" fill-opacity="' + f(0.25 + rnd() * 0.5) + '"' : '';
          out.push('<polygon points="' + hexPts(h.x, h.y, g.r).map(function (q) { return f(q[0]) + ',' + f(q[1]); }).join(' ') + '"' + fl + '/>');
        });
        return { body: '<g id="Honeycomb" fill="none" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '" stroke-linejoin="round">' + out.join('') + '</g>', defs: '', meta: cols + ' columns × ' + g.rows + ' rows' };
      }
    },
    {
      id: 'kaleido', name: 'Kaleidoscope', cat: 'Radial', pal: 9,
      colors: ['Background', 'Color 1', 'Color 2', 'Color 3', 'Color 4'],
      params: [
        { key: 'sectors', label: 'Sectors', min: 4, max: 32, step: 2, def: 12 },
        { key: 'rings', label: 'Rings', min: 3, max: 20, step: 1, def: 8 },
        { key: 'turn', label: 'Rotation', min: 0, max: 360, step: 5, def: 0 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, out = [];
        var n = Math.round(p.sectors / 2) * 2, m = Math.round(p.rings), cx = W / 2, cy = H / 2, R = Math.hypot(cx, cy) * 1.05;
        var table = [], j, i;
        for (j = 0; j < m; j++) { table[j] = []; for (i = 0; i < n / 2; i++) table[j][i] = 1 + Math.floor(rnd() * (col.length - 1)); }
        var off = p.turn * Math.PI / 180, step = TAU / n;
        var P = function (r, a) { return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
        for (j = 0; j < m; j++) {
          var r0 = R * j / m, r1 = R * (j + 1) / m;
          for (i = 0; i < n; i++) {
            var h = i < n / 2 ? i : n - 1 - i, a0 = off + i * step, a1 = a0 + step;
            var p1 = P(r1, a0), p2 = P(r1, a1), p3 = P(r0, a1), p0 = P(r0, a0);
            var d = j === 0
              ? 'M' + f(cx) + ' ' + f(cy) + 'L' + f(p1[0]) + ' ' + f(p1[1]) + 'A' + f(r1) + ' ' + f(r1) + ' 0 0 1 ' + f(p2[0]) + ' ' + f(p2[1]) + 'Z'
              : 'M' + f(p0[0]) + ' ' + f(p0[1]) + 'L' + f(p1[0]) + ' ' + f(p1[1]) + 'A' + f(r1) + ' ' + f(r1) + ' 0 0 1 ' + f(p2[0]) + ' ' + f(p2[1]) + 'L' + f(p3[0]) + ' ' + f(p3[1]) + 'A' + f(r0) + ' ' + f(r0) + ' 0 0 0 ' + f(p0[0]) + ' ' + f(p0[1]) + 'Z';
            out.push('<path d="' + d + '" fill="' + col[table[j][h]] + '" stroke="' + col[table[j][h]] + '" stroke-width="0.5"/>');
          }
        }
        return { body: '<g id="Kaleidoscope">' + out.join('') + '</g>', defs: '', meta: n + ' mirrored sectors × ' + m + ' rings' };
      }
    },
    {
      id: 'plus', name: 'Plus Grid', cat: 'Shapes', pal: 5,
      colors: ['Background', 'Plus A', 'Plus B'],
      params: [
        { key: 'cols', label: 'Columns across', min: 4, max: 40, step: 1, def: 14 },
        { key: 'size', label: 'Size', min: 0.2, max: 0.5, step: 0.01, def: 0.34 },
        { key: 'thick', label: 'Arm thickness', min: 0.1, max: 0.6, step: 0.02, def: 0.28 },
        { key: 'tilt', label: 'Tilt', min: 0, max: 45, step: 1, def: 0 },
        { key: 'stagger', label: 'Offset rows', type: 'toggle', def: 1 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, out = [];
        var cols = Math.round(p.cols), d = W / cols, rows = Math.ceil(H / d) + 2, h = p.size * d, t = h * p.thick;
        var pts = [[-t, -h], [t, -h], [t, -t], [h, -t], [h, t], [t, t], [t, h], [-t, h], [-t, t], [-h, t], [-h, -t], [-t, -t]].map(function (z) { return f(z[0]) + ',' + f(z[1]); }).join(' ');
        for (var j = -1; j < rows; j++) for (var i = -1; i <= cols; i++) {
          var x = i * d + d / 2 + ((p.stagger && (j & 1)) ? d / 2 : 0), y = j * d + d / 2;
          out.push('<polygon points="' + pts + '" fill="' + col[1 + (Math.abs(i + j) & 1)] + '" transform="translate(' + f(x) + ' ' + f(y) + ') rotate(' + f(p.tilt) + ')"/>');
        }
        return { body: '<g id="Plus">' + out.join('') + '</g>', defs: '', meta: cols + ' columns of crosses' };
      }
    },
    {
      id: 'bauhaus', name: 'Bauhaus Tiles', cat: 'Tiles', pal: 7,
      colors: ['Background', 'Color 1', 'Color 2', 'Color 3', 'Color 4'],
      params: [
        { key: 'cols', label: 'Columns across', min: 3, max: 20, step: 1, def: 8 }
      ],
      render: function (c) {
        var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, out = [];
        var cols = Math.round(p.cols), cell = W / cols, rows = Math.ceil(H / cell), h = cell / 2, nc = col.length - 1;
        function sector(cx, cy, r, a0, span) {
          var s = a0 * Math.PI / 180, e = (a0 + span) * Math.PI / 180;
          return 'M' + f(cx) + ' ' + f(cy) + 'L' + f(cx + r * Math.cos(s)) + ' ' + f(cy + r * Math.sin(s)) +
            'A' + f(r) + ' ' + f(r) + ' 0 0 1 ' + f(cx + r * Math.cos(e)) + ' ' + f(cy + r * Math.sin(e)) + 'Z';
        }
        for (var r = 0; r < rows; r++) for (var i = 0; i < cols; i++) {
          var x = i * cell, y = r * cell, k1 = Math.floor(rnd() * nc), k2 = (k1 + 1 + Math.floor(rnd() * (nc - 1))) % nc;
          var shape = Math.floor(rnd() * 4), q = Math.floor(rnd() * 4), fill = col[1 + k2], el;
          if (shape === 0) el = '<circle cx="' + f(x + h) + '" cy="' + f(y + h) + '" r="' + f(h) + '" fill="' + fill + '"/>';
          else if (shape === 1) {
            var corners = [[x, y, 0], [x + cell, y, 90], [x + cell, y + cell, 180], [x, y + cell, 270]][q];
            el = '<path d="' + sector(corners[0], corners[1], cell, corners[2], 90) + '" fill="' + fill + '"/>';
          } else if (shape === 2) {
            var sides = [[x + h, y, 0], [x + cell, y + h, 90], [x + h, y + cell, 180], [x, y + h, 270]][q];
            el = '<path d="' + sector(sides[0], sides[1], h, sides[2], 180) + '" fill="' + fill + '"/>';
          } else {
            var tp = [[[x, y], [x + cell, y], [x, y + cell]], [[x, y], [x + cell, y], [x + cell, y + cell]], [[x + cell, y], [x + cell, y + cell], [x, y + cell]], [[x, y], [x + cell, y + cell], [x, y + cell]]][q];
            el = '<polygon points="' + tp.map(function (z) { return f(z[0]) + ',' + f(z[1]); }).join(' ') + '" fill="' + fill + '"/>';
          }
          out.push('<g><rect x="' + f(x) + '" y="' + f(y) + '" width="' + f(cell) + '" height="' + f(cell) + '" fill="' + col[1 + k1] + '"/>' + el + '</g>');
        }
        return { body: '<g id="Tiles">' + out.join('') + '</g>', defs: '', meta: cols + ' × ' + rows + ' tiles, 4 shape types' };
      }
    }
  ];


  /* ======================== EXTRA FAMILIES (part 1: helpers + shape grids) ======================== */
  function circleD(cx, cy, r) {
    return 'M' + f(cx - r) + ' ' + f(cy) + 'a' + f(r) + ' ' + f(r) + ' 0 1 0 ' + f(2 * r) + ' 0a' + f(r) + ' ' + f(r) + ' 0 1 0 ' + f(-2 * r) + ' 0Z';
  }
  function polarPts(n, r, rot, inner) {
    var pts = [], k = inner ? n * 2 : n;
    for (var i = 0; i < k; i++) {
      var a = rot + i * TAU / k, rr = (inner && (i & 1)) ? r * inner : r;
      pts.push([rr * Math.cos(a), rr * Math.sin(a)]);
    }
    return pts;
  }
  function makeNoise(seed) {
    var rnd = mulberry32(seed), N = 256, perm = [], vals = [], i, j, t;
    for (i = 0; i < N; i++) { vals.push(rnd()); perm.push(i); }
    for (i = N - 1; i > 0; i--) { j = Math.floor(rnd() * (i + 1)); t = perm[i]; perm[i] = perm[j]; perm[j] = t; }
    var h = function (x, y) { return vals[perm[(perm[x & 255] + y) & 255]]; };
    var sm = function (q) { return q * q * (3 - 2 * q); };
    return function (x, y) {
      var xi = Math.floor(x), yi = Math.floor(y), xf = sm(x - xi), yf = sm(y - yi);
      var a = h(xi, yi), b = h(xi + 1, yi), c = h(xi, yi + 1), d = h(xi + 1, yi + 1);
      var top = a + (b - a) * xf, bot = c + (d - c) * xf;
      return top + (bot - top) * yf;
    };
  }
  function f1(n) { return String(+(+n).toFixed(1)); }
  function clamp01(t) { return Math.max(0, Math.min(1, t)); }
  var PSETS = {};
  function pr(key, label, min, max, step, def) { return { key: key, label: label, min: min, max: max, step: step, def: def }; }
  function tg(key, label, def) { return { key: key, label: label, type: 'toggle', def: def }; }
  function def(id, name, cat, pal, colors, params, render, defCols, dark) {
    var o = { id: id, name: name, cat: cat, pal: pal, colors: colors, params: params, render: render };
    if (defCols) o.defCols = defCols;
    if (dark) o.dark = dark;
    EXTRA.push(o);
  }
  function clipLine(x1, y1, x2, y2, xmin, ymin, xmax, ymax) {
    var dx = x2 - x1, dy = y2 - y1, t0 = 0, t1 = 1, pp = [-dx, dx, -dy, dy], qq = [x1 - xmin, xmax - x1, y1 - ymin, ymax - y1];
    for (var i = 0; i < 4; i++) {
      if (pp[i] === 0) { if (qq[i] < 0) return null; }
      else {
        var t = qq[i] / pp[i];
        if (pp[i] < 0) { if (t > t1) return null; if (t > t0) t0 = t; }
        else { if (t < t0) return null; if (t < t1) t1 = t; }
      }
    }
    return [x1 + t0 * dx, y1 + t0 * dy, x1 + t1 * dx, y1 + t1 * dy];
  }
  function clipHalf(poly, mx, my, nx, ny) {
    var out = [], n = poly.length, a, b, da, db, t;
    for (var q = 0; q < n; q++) {
      a = poly[q]; b = poly[(q + 1) % n];
      da = (a[0] - mx) * nx + (a[1] - my) * ny; db = (b[0] - mx) * nx + (b[1] - my) * ny;
      if (da <= 0) out.push(a);
      if ((da < 0 && db > 0) || (da > 0 && db < 0)) { t = da / (da - db); out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]); }
    }
    return out;
  }
  function voronoi(W, H, cols, jit, rnd) {
    var cw = W / cols, rows = Math.ceil(H / cw), S = {}, cells = [], i, j, k, l;
    for (j = -1; j <= rows; j++) for (i = -1; i <= cols; i++) S[j + ',' + i] = [(i + 0.5 + (rnd() - 0.5) * jit) * cw, (j + 0.5 + (rnd() - 0.5) * jit) * cw];
    for (j = -1; j <= rows; j++) for (i = -1; i <= cols; i++) {
      var s = S[j + ',' + i], R = 2.5 * cw;
      var poly = [[s[0] - R, s[1] - R], [s[0] + R, s[1] - R], [s[0] + R, s[1] + R], [s[0] - R, s[1] + R]];
      for (l = -2; l <= 2 && poly.length; l++) for (k = -2; k <= 2 && poly.length; k++) {
        if (!k && !l) continue;
        var n = S[(j + l) + ',' + (i + k)]; if (!n) continue;
        poly = clipHalf(poly, (s[0] + n[0]) / 2, (s[1] + n[1]) / 2, n[0] - s[0], n[1] - s[1]);
      }
      if (poly.length > 2) cells.push({ s: s, poly: poly });
    }
    return { cells: cells, rows: rows };
  }

  var EXTRA = [];
  var PT = function (pts) { return polyPath(pts, true); };

  /* ---------- motif shapes (centered on 0,0, radius r). part = {d, s: stroke factor, sh: shade} ---------- */
  var MOT = {
    ring: function (r) { return [{ d: circleD(0, 0, r * 0.76), s: 0.26 }]; },
    square: function (r) { var q = r * 0.78; return [{ d: PT([[-q, -q], [q, -q], [q, q], [-q, q]]) }]; },
    diamond: function (r) { return [{ d: PT([[0, -r], [r * 0.72, 0], [0, r], [-r * 0.72, 0]]) }]; },
    tri: function (r) { return [{ d: PT(polarPts(3, r, -Math.PI / 2)) }]; },
    star5: function (r) { return [{ d: PT(polarPts(5, r, -Math.PI / 2, 0.45)) }]; },
    sparkle: function (r) { return [{ d: PT(polarPts(4, r, -Math.PI / 2, 0.2)) }]; },
    hexstar: function (r) { return [{ d: PT(polarPts(6, r, -Math.PI / 2, 0.58)) }]; },
    heart: function (r) {
      var pts = [], s = r / 17.5, i, t;
      for (i = 0; i < 56; i++) {
        t = i / 56 * TAU;
        pts.push([16 * Math.pow(Math.sin(t), 3) * s, -(13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t)) * s]);
      }
      return [{ d: PT(pts) }];
    },
    leaf: function (r) {
      return [{ d: 'M0 ' + f(r) + 'Q' + f(r * 1.25) + ' ' + f(r * 0.1) + ' ' + f(r * 0.15) + ' ' + f(-r) + 'Q' + f(-r * 0.7) + ' ' + f(-r * 0.1) + ' 0 ' + f(r) + 'Z' },
        { d: 'M0 ' + f(r * 0.9) + 'L' + f(r * 0.1) + ' ' + f(-r * 0.55), s: 0.07, sh: -0.28 }];
    },
    drop: function (r) {
      var a = r * 0.8, b = r * 0.35;
      return [{ d: 'M0 ' + f(-r) + 'C' + f(r * 0.2) + ' ' + f(-r * 0.4) + ' ' + f(a) + ' 0 ' + f(a) + ' ' + f(b) + 'A' + f(a) + ' ' + f(a) + ' 0 0 1 ' + f(-a) + ' ' + f(b) + 'C' + f(-a) + ' 0 ' + f(-r * 0.2) + ' ' + f(-r * 0.4) + ' 0 ' + f(-r) + 'Z' }];
    },
    moon: function (r) {
      var o = r * 0.4;
      return [{ d: 'M' + f(o) + ' ' + f(-r) + 'A' + f(r) + ' ' + f(r) + ' 0 0 0 ' + f(o) + ' ' + f(r) + 'A' + f(r * 1.35) + ' ' + f(r * 1.35) + ' 0 0 1 ' + f(o) + ' ' + f(-r) + 'Z' }];
    },
    petals4: function (r) {
      var d = '', i; for (i = 0; i < 4; i++) { var a = i * Math.PI / 2; d += circleD(r * 0.52 * Math.cos(a), r * 0.52 * Math.sin(a), r * 0.4); }
      return [{ d: d }, { d: circleD(0, 0, r * 0.2), sh: 0.55 }];
    },
    petals6: function (r) {
      var d = '', i; for (i = 0; i < 6; i++) { var a = i * Math.PI / 3 - Math.PI / 2; d += circleD(r * 0.62 * Math.cos(a), r * 0.62 * Math.sin(a), r * 0.32); }
      return [{ d: d }, { d: circleD(0, 0, r * 0.22), sh: 0.55 }];
    },
    trefoil: function (r) {
      var d = '', i; for (i = 0; i < 3; i++) { var a = i * TAU / 3 - Math.PI / 2; d += circleD(r * 0.44 * Math.cos(a), r * 0.44 * Math.sin(a), r * 0.42); }
      return [{ d: d }];
    },
    hexagon: function (r) { return [{ d: PT(polarPts(6, r * 0.95, 0)) }]; },
    octagon: function (r) { return [{ d: PT(polarPts(8, r * 0.95, Math.PI / 8)) }]; },
    pentagon: function (r) { return [{ d: PT(polarPts(5, r, -Math.PI / 2)) }]; },
    semi: function (r) { return [{ d: 'M' + f(-r) + ' ' + f(r * 0.5) + 'A' + f(r) + ' ' + f(r) + ' 0 0 1 ' + f(r) + ' ' + f(r * 0.5) + 'Z' }]; },
    quarter: function (r) {
      var q = r * 0.8;
      return [{ d: 'M' + f(-q) + ' ' + f(q) + 'L' + f(-q) + ' ' + f(-q) + 'A' + f(2 * q) + ' ' + f(2 * q) + ' 0 0 1 ' + f(q) + ' ' + f(q) + 'Z' }];
    },
    arrow: function (r) { return [{ d: PT([[-r, -r * 0.8], [0, r * 0.2], [r, -r * 0.8], [r, -r * 0.3], [0, r * 0.7], [-r, -r * 0.3]]) }]; },
    bolt: function (r) { return [{ d: PT([[r * 0.2, -r], [-r * 0.5, r * 0.1], [-r * 0.05, r * 0.1], [-r * 0.2, r], [r * 0.5, -r * 0.2], [r * 0.05, -r * 0.2]]) }]; },
    cloud: function (r) {
      return [{ d: circleD(-r * 0.42, r * 0.18, r * 0.38) + circleD(r * 0.02, -r * 0.12, r * 0.5) + circleD(r * 0.45, r * 0.2, r * 0.36) +
        'M' + f(-r * 0.42) + ' ' + f(r * 0.56) + 'H' + f(r * 0.45) + 'V' + f(r * 0.2) + 'H' + f(-r * 0.42) + 'Z' }];
    },
    squiggle: function (r) { return [{ d: 'M' + f(-r) + ' 0q' + f(r * 0.5) + ' ' + f(-r * 0.9) + ' ' + f(r) + ' 0t' + f(r) + ' 0', s: 0.22 }]; },
    spiral: function (r) {
      var d = 'M0 0', i; for (i = 1; i <= 40; i++) { var a = i * 0.55, rr = r * 0.95 * i / 40; d += 'L' + f(rr * Math.cos(a)) + ' ' + f(rr * Math.sin(a)); }
      return [{ d: d, s: 0.13 }];
    },
    asterisk: function (r) { return [{ d: 'M0 ' + f(-r) + 'L0 ' + f(r) + 'M' + f(-r * 0.87) + ' ' + f(-r * 0.5) + 'L' + f(r * 0.87) + ' ' + f(r * 0.5) + 'M' + f(-r * 0.87) + ' ' + f(r * 0.5) + 'L' + f(r * 0.87) + ' ' + f(-r * 0.5), s: 0.2 }]; },
    bowtie: function (r) { return [{ d: 'M' + f(-r) + ' ' + f(-r * 0.7) + 'L0 0L' + f(-r) + ' ' + f(r * 0.7) + 'ZM' + f(r) + ' ' + f(-r * 0.7) + 'L0 0L' + f(r) + ' ' + f(r * 0.7) + 'Z' }]; },
    lens: function (r) { var R = r * 1.15; return [{ d: 'M' + f(-r) + ' 0A' + f(R) + ' ' + f(R) + ' 0 0 1 ' + f(r) + ' 0A' + f(R) + ' ' + f(R) + ' 0 0 1 ' + f(-r) + ' 0Z' }]; },
    pill: function (r) {
      var a = r * 0.55, b = r * 0.35;
      return [{ d: 'M' + f(-a) + ' ' + f(-b) + 'H' + f(a) + 'A' + f(b) + ' ' + f(b) + ' 0 0 1 ' + f(a) + ' ' + f(b) + 'H' + f(-a) + 'A' + f(b) + ' ' + f(b) + ' 0 0 1 ' + f(-a) + ' ' + f(-b) + 'Z' }];
    },
    cross: function (r) {
      return [{ d: circleD(0, 0, r * 0.55), s: 0.12 }, { d: 'M0 ' + f(-r) + 'L0 ' + f(r) + 'M' + f(-r) + ' 0L' + f(r) + ' 0', s: 0.12 }];
    },
    dash: function (r) { return [{ d: 'M' + f(-r * 0.85) + ' 0L' + f(r * 0.85) + ' 0', s: 0.34 }]; },
    trio: function (r) { return [{ d: circleD(0, -r * 0.45, r * 0.3) + circleD(-r * 0.5, r * 0.35, r * 0.3) + circleD(r * 0.5, r * 0.35, r * 0.3) }]; },
    sun: function (r) {
      var d = '', i; for (i = 0; i < 8; i++) { var a = i * Math.PI / 4; d += 'M' + f(r * 0.64 * Math.cos(a)) + ' ' + f(r * 0.64 * Math.sin(a)) + 'L' + f(r * Math.cos(a)) + ' ' + f(r * Math.sin(a)); }
      return [{ d: circleD(0, 0, r * 0.42) }, { d: d, s: 0.15 }];
    },
    gem: function (r) {
      return [{ d: PT([[-r * 0.5, -r * 0.55], [r * 0.5, -r * 0.55], [r * 0.9, -r * 0.1], [-r * 0.9, -r * 0.1]]), sh: 0.3 },
        { d: PT([[-r * 0.9, -r * 0.1], [0, -r * 0.1], [0, r * 0.95]]) },
        { d: PT([[0, -r * 0.1], [r * 0.9, -r * 0.1], [0, r * 0.95]]), sh: -0.2 }];
    }
  };
  function shade(c, s) { return !s ? c : (s > 0 ? lighten(c, s) : darken(c, -s)); }
  function motifPattern(id, name, pal, fn, o) {
    o = o || {};
    def(id, name, 'Shapes', pal, ['Background', 'Shape A', 'Shape B'], [
      pr('cols', 'Columns across', 3, 40, 1, o.cols || 12),
      pr('size', 'Shape size', 0.2, 1.1, 0.02, o.size || 0.62),
      pr('rot', 'Rotation', -180, 180, 5, o.rot || 0),
      pr('spin', 'Random rotation', 0, 1, 0.05, o.spin || 0),
      pr('sizevar', 'Size variation', 0, 0.7, 0.02, o.sizevar || 0),
      tg('stagger', 'Offset rows', o.stagger == null ? 1 : o.stagger),
      tg('alt', 'Alternate colours', o.alt == null ? 1 : o.alt)
    ], function (c) {
      var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, out = [], n = 0;
      var cols = Math.round(p.cols), d = W / cols, dy = p.stagger ? d * 0.866 : d, rows = Math.ceil(H / dy) + 2;
      for (var j = -1; j < rows; j++) for (var i = -1; i <= cols; i++) {
        var x = i * d + ((p.stagger && (j & 1)) ? d / 2 : 0) + d / 2, y = j * dy + d / 2;
        var color = col[1 + (p.alt ? (Math.abs(i + j) & 1) : 0)];
        var r = d * 0.5 * p.size * (1 - p.sizevar * rnd());
        var ang = p.rot + (rnd() - 0.5) * 360 * p.spin;
        var tr = ' transform="translate(' + f(x) + ' ' + f(y) + ')' + (ang ? ' rotate(' + f(ang) + ')' : '') + '"';
        fn(r).forEach(function (pt) {
          var cc = shade(color, pt.sh);
          if (pt.s) out.push('<path d="' + pt.d + '" fill="none" stroke="' + cc + '" stroke-width="' + f(r * pt.s) + '" stroke-linecap="round" stroke-linejoin="round"' + tr + '/>');
          else out.push('<path d="' + pt.d + '" fill="' + cc + '"' + tr + '/>');
        });
        n++;
      }
      return { body: '<g id="Shapes">' + out.join('') + '</g>', defs: '', meta: n + ' shapes on a ' + cols + ' column grid' };
    });
  }
  [
    ['ringgrid', 'Ring Grid', 2, 'ring', { size: 0.8 }],
    ['squaregrid', 'Square Grid', 7, 'square', { rot: 45, size: 0.7 }],
    ['diamondgrid', 'Diamond Grid', 9, 'diamond', {}],
    ['trigrid', 'Triangle Grid', 5, 'tri', { cols: 14 }],
    ['star5grid', 'Five Point Stars', 7, 'star5', { size: 0.8 }],
    ['sparklegrid', 'Sparkle Grid', 10, 'sparkle', { size: 0.8, cols: 14 }],
    ['hexstargrid', 'Hexagram Grid', 6, 'hexstar', { size: 0.82 }],
    ['heartgrid', 'Heart Grid', 2, 'heart', { size: 0.7 }],
    ['leafgrid', 'Leaf Grid', 8, 'leaf', { size: 0.8, rot: 30 }],
    ['dropgrid', 'Drop Grid', 1, 'drop', { size: 0.8 }],
    ['moongrid', 'Crescent Grid', 7, 'moon', { size: 0.8, rot: -20 }],
    ['petal4grid', 'Four Petal Flowers', 11, 'petals4', { size: 0.9, cols: 9 }],
    ['petal6grid', 'Six Petal Flowers', 6, 'petals6', { size: 0.95, cols: 9 }],
    ['trefoilgrid', 'Trefoil Grid', 5, 'trefoil', { size: 0.85, cols: 10 }],
    ['hexgrid', 'Hexagon Grid', 10, 'hexagon', { size: 0.9, cols: 14 }],
    ['octgrid', 'Octagon Grid', 0, 'octagon', { size: 0.9, stagger: 0, cols: 10 }],
    ['pentgrid', 'Pentagon Grid', 9, 'pentagon', { size: 0.85, cols: 11 }],
    ['semigrid', 'Half Circle Grid', 3, 'semi', { size: 0.9, stagger: 0, cols: 12 }],
    ['quartergrid', 'Quarter Circle Grid', 1, 'quarter', { size: 0.9, stagger: 0, spin: 1, cols: 10 }],
    ['arrowgrid', 'Chevron Arrow Grid', 3, 'arrow', { size: 0.8, cols: 12 }],
    ['boltgrid', 'Bolt Grid', 7, 'bolt', { size: 0.8, cols: 12, rot: 15 }],
    ['cloudgrid', 'Cloud Grid', 1, 'cloud', { size: 0.85, cols: 8 }],
    ['squigglegrid', 'Squiggle Grid', 2, 'squiggle', { size: 0.8, cols: 11 }],
    ['spiralgrid', 'Spiral Grid', 6, 'spiral', { size: 0.85, cols: 9 }],
    ['asteriskgrid', 'Asterisk Grid', 8, 'asterisk', { size: 0.7, cols: 14 }],
    ['bowtiegrid', 'Bow Tie Grid', 11, 'bowtie', { size: 0.85, cols: 11, rot: 90 }],
    ['lensgrid', 'Lens Grid', 10, 'lens', { size: 0.85, cols: 10, rot: 45 }],
    ['pillgrid', 'Pill Grid', 9, 'pill', { size: 0.95, cols: 9, rot: -30 }],
    ['crossgrid', 'Crosshair Grid', 4, 'cross', { size: 0.65, cols: 14, stagger: 0 }],
    ['dashgrid', 'Dash Grid', 3, 'dash', { size: 0.8, cols: 14, rot: 45 }],
    ['triogrid', 'Dot Trio Grid', 5, 'trio', { size: 0.9, cols: 11 }],
    ['sungrid', 'Sun Grid', 0, 'sun', { size: 0.85, cols: 9 }],
    ['gemgrid', 'Gem Grid', 6, 'gem', { size: 0.85, cols: 10 }]
  ].forEach(function (m) { motifPattern(m[0], m[1], m[2], MOT[m[3]], m[4]); });

  /* ======================== EXTRA FAMILIES (part 2: geometric, lines, radial, organic, retro) ======================== */
  var RND_ANG = function (rnd, n) { return Math.floor(rnd() * n); };

  /* ---------- Geometric ---------- */
  def('checker', 'Checkerboard', 'Geometric', 4, ['Background', 'Square A', 'Square B'], [
    pr('cols', 'Columns across', 2, 60, 1, 14), pr('var', 'Tone variation', 0, 1, 0.05, 0.15), pr('gap', 'Gap', 0, 10, 0.5, 0)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, out = [];
    var cols = Math.round(p.cols), d = W / cols, rows = Math.ceil(H / d), g = p.gap * u;
    for (var j = 0; j < rows; j++) for (var i = 0; i < cols; i++) {
      var k = (i + j) & 1, fill = mix(col[1 + k], col[2 - k], rnd() * p.var * 0.5);
      out.push('<rect x="' + f(i * d + g / 2) + '" y="' + f(j * d + g / 2) + '" width="' + f(d - g) + '" height="' + f(d - g) + '" fill="' + fill + '"/>');
    }
    return { body: '<g id="Squares">' + out.join('') + '</g>', defs: '', meta: cols + ' × ' + rows + ' squares' };
  }, ['#ffffff', '#1d2733', '#ffffff']);

  def('gingham', 'Gingham', 'Geometric', 2, ['Background', 'Check color'], [
    pr('cols', 'Columns across', 3, 40, 1, 10), pr('soft', 'Stripe strength', 0.15, 0.85, 0.01, 0.5)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = [];
    var cols = Math.round(p.cols), d = W / cols, rows = Math.ceil(H / d), mid = mix(col[0], col[1], p.soft), i, j;
    for (j = 0; j < rows; j += 2) out.push('<rect x="0" y="' + f(j * d) + '" width="' + W + '" height="' + f(d) + '" fill="' + mid + '"/>');
    for (i = 0; i < cols; i += 2) out.push('<rect x="' + f(i * d) + '" y="0" width="' + f(d) + '" height="' + H + '" fill="' + mid + '"/>');
    for (j = 0; j < rows; j += 2) for (i = 0; i < cols; i += 2) out.push('<rect x="' + f(i * d) + '" y="' + f(j * d) + '" width="' + f(d) + '" height="' + f(d) + '" fill="' + col[1] + '"/>');
    return { body: '<g id="Gingham">' + out.join('') + '</g>', defs: '', meta: cols + ' columns of gingham checks' };
  }, ['#ffffff', '#e2486a']);

  def('weave', 'Basket Weave', 'Geometric', 11, ['Background', 'Horizontal strips', 'Vertical strips'], [
    pr('cols', 'Columns across', 3, 30, 1, 8), pr('gap', 'Gap', 0, 0.3, 0.01, 0.08), pr('round', 'Roundness', 0, 1, 0.05, 0.4)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = [];
    var cols = Math.round(p.cols), d = W / cols, rows = Math.ceil(H / d), s = d / 3, g = s * p.gap, rx = (s - g) / 2 * p.round;
    for (var j = 0; j < rows; j++) for (var i = 0; i < cols; i++) {
      var hor = ((i + j) & 1) === 0;
      for (var k = 0; k < 3; k++) {
        var x = i * d + (hor ? g / 2 : k * s + g / 2), y = j * d + (hor ? k * s + g / 2 : g / 2);
        var w = hor ? d - g : s - g, h = hor ? s - g : d - g;
        out.push('<rect x="' + f(x) + '" y="' + f(y) + '" width="' + f(w) + '" height="' + f(h) + '" rx="' + f(rx) + '" fill="' + col[hor ? 1 : 2] + '"/>');
      }
    }
    return { body: '<g id="Strips">' + out.join('') + '</g>', defs: '', meta: cols + ' × ' + rows + ' woven blocks' };
  });

  def('lattice', 'Diamond Lattice', 'Geometric', 7, ['Background', 'Line color', 'Node color'], [
    pr('cols', 'Columns across', 3, 30, 1, 10), pr('aspect', 'Diamond height', 0.5, 2, 0.05, 1), pr('sw', 'Line weight', 0.4, 5, 0.1, 1.6), pr('dot', 'Node size', 0, 4, 0.1, 2.2)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, cols = Math.round(p.cols), dx = W / cols, dy = dx * p.aspect;
    var rows = Math.ceil(H / dy) + 2, d = '', dots = '', k, j, i, yA = -dy, yB = H + dy, n = 0;
    for (k = -rows - 2; k <= cols + rows + 2; k++) {
      if (k & 1) continue;
      d += 'M' + f(k * dx + yA / dy * dx) + ' ' + f(yA) + 'L' + f(k * dx + yB / dy * dx) + ' ' + f(yB);
      d += 'M' + f(k * dx - yA / dy * dx) + ' ' + f(yA) + 'L' + f(k * dx - yB / dy * dx) + ' ' + f(yB);
    }
    if (p.dot > 0) for (j = 0; j <= rows; j++) for (i = 0; i <= cols; i++) {
      if ((i + j) & 1) continue;
      dots += '<circle cx="' + f(i * dx) + '" cy="' + f(j * dy) + '" r="' + f(p.dot * u * 2) + '"/>'; n++;
    }
    return { body: '<path id="Lines" d="' + d + '" fill="none" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '"/><g id="Nodes" fill="' + col[2] + '">' + dots + '</g>', defs: '', meta: 'crossing lines and ' + n + ' nodes' };
  });

  def('circlelattice', 'Circle Lattice', 'Geometric', 10, ['Background', 'Line color'], [
    pr('cols', 'Columns across', 3, 24, 1, 9), pr('sw', 'Line weight', 0.4, 5, 0.1, 1.5), tg('double', 'Inner circles', 0)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, cols = Math.round(p.cols), R = W / cols, h = R * 0.866, rows = Math.ceil(H / h) + 2, d = '';
    for (var j = -1; j < rows; j++) for (var i = -1; i <= cols; i++) {
      var x = i * R + ((j & 1) ? R / 2 : 0), y = j * h;
      d += circleD(x, y, R); if (p.double) d += circleD(x, y, R / 2);
    }
    return { body: '<path id="Circles" d="' + d + '" fill="none" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '"/>', defs: '', meta: 'overlapping circles on a hex lattice' };
  });

  def('trimosaic', 'Triangle Mosaic', 'Geometric', 1, ['Background', 'Start tone', 'End tone'], [
    pr('cols', 'Columns across', 3, 40, 1, 14), pr('var', 'Tone variation', 0, 0.6, 0.02, 0.22), pr('angle', 'Gradient angle', 0, 360, 5, 30)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, out = [], cols = Math.round(p.cols), d = W / cols, h = d * 0.866, rows = Math.ceil(H / h);
    var a = p.angle * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a), E = (Math.abs(W * ca) + Math.abs(rows * h * sa)) / 2 || 1, HH = rows * h;
    var tri = function (A, B, C) {
      var cx = (A[0] + B[0] + C[0]) / 3, cy = (A[1] + B[1] + C[1]) / 3;
      var t = clamp01(((cx - W / 2) * ca + (cy - HH / 2) * sa) / E * 0.5 + 0.5 + (rnd() - 0.5) * p.var * 2), fill = mix(col[1], col[2], t);
      out.push('<polygon points="' + [A, B, C].map(function (q) { return f(q[0]) + ',' + f(q[1]); }).join(' ') + '" fill="' + fill + '" stroke="' + fill + '" stroke-width="0.6"/>');
    };
    for (var j = 0; j < rows; j++) for (var i = -1; i <= cols; i++) {
      var x = i * d, y = j * h;
      tri([x, y + h], [x + d, y + h], [x + d / 2, y]);
      tri([x + d / 2, y], [x + d * 1.5, y], [x + d, y + h]);
    }
    return { body: '<g id="Triangles" stroke-linejoin="round">' + out.join('') + '</g>', defs: '', meta: out.length + ' triangles' };
  });

  function tunnel(id, name, pal, sides, twist, ex) {
    def(id, name, 'Geometric', pal, ['Background', 'Ring A', 'Ring B'], [
      pr('rings', 'Rings', 4, 40, 1, ex && ex.rings || 16), pr('sides', 'Sides', 3, 12, 1, sides), pr('twist', 'Twist per ring', -30, 30, 0.5, twist),
      pr('cx', 'Center X', 0, 1, 0.01, 0.5), pr('cy', 'Center Y', 0, 1, 0.01, 0.5), pr('curve', 'Spacing curve', 0.5, 1.8, 0.05, 1)
    ], function (c) {
      var W = c.W, H = c.H, p = c.p, col = c.col, out = [], n = Math.round(p.rings), cx = p.cx * W, cy = p.cy * H, sd = Math.round(p.sides);
      var R0 = Math.hypot(Math.max(cx, W - cx), Math.max(cy, H - cy)) * 1.12 / Math.cos(Math.PI / sd);
      for (var k = 0; k < n; k++) {
        var r = R0 * Math.pow((n - k) / n, p.curve), rot = -Math.PI / 2 + k * p.twist * Math.PI / 180;
        out.push('<polygon points="' + polarPts(sd, r, rot).map(function (q) { return f(cx + q[0]) + ',' + f(cy + q[1]); }).join(' ') + '" fill="' + col[1 + (k & 1)] + '"/>');
      }
      return { body: '<g id="Rings">' + out.join('') + '</g>', defs: '', meta: n + ' nested ' + sd + '-sided shapes' };
    });
  }
  tunnel('tunnelsq', 'Square Tunnel', 3, 4, 0, { rings: 18 });
  tunnel('twistsq', 'Twisted Squares', 9, 4, 6);
  tunnel('tunnelhex', 'Hex Tunnel', 10, 6, 0);
  tunnel('tunneltri', 'Triangle Tunnel', 2, 3, 4);

  def('warpcheck', 'Warped Checker', 'Geometric', 4, ['Background', 'Square A', 'Square B'], [
    pr('cols', 'Columns across', 6, 40, 1, 20), pr('amp', 'Warp strength', 0, 0.9, 0.02, 0.4), pr('freq', 'Warp waves', 0.3, 4, 0.1, 1.4), pr('phase', 'Phase', 0, 6.28, 0.1, 0)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = [], cols = Math.round(p.cols), d = W / cols, rows = Math.ceil(H / d) + 1, A = p.amp * d * 2.2, i, j;
    var P = function (x, y) { return [x + A * Math.sin(TAU * p.freq * y / H + p.phase), y + A * Math.sin(TAU * p.freq * x / W + p.phase * 1.3)]; };
    for (j = -2; j < rows + 2; j++) for (i = -2; i < cols + 2; i++) {
      var q = [P(i * d, j * d), P((i + 1) * d, j * d), P((i + 1) * d, (j + 1) * d), P(i * d, (j + 1) * d)];
      out.push('<polygon points="' + q.map(function (z) { return f(z[0]) + ',' + f(z[1]); }).join(' ') + '" fill="' + col[1 + ((i + j) & 1)] + '"/>');
    }
    return { body: '<g id="Cells">' + out.join('') + '</g>', defs: '', meta: out.length + ' warped cells' };
  }, ['#ffffff', '#111111', '#ffffff']);

  def('colorblocks', 'Color Blocks', 'Geometric', 7, ['Gap color', 'Block 1', 'Block 2', 'Block 3', 'Block 4'], [
    pr('depth', 'Splits', 2, 9, 1, 6), pr('gap', 'Gap', 0, 18, 0.5, 6), pr('round', 'Corner radius', 0, 30, 1, 0)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, leaves = [], out = [];
    var split = function (x, y, w, h, depth) {
      if (depth <= 0 || (depth < 4 && rnd() < 0.2) || (w < W / 14 && h < W / 14)) { leaves.push([x, y, w, h]); return; }
      var vert = w > h * 1.15 ? true : (h > w * 1.15 ? false : rnd() > 0.5), t = 0.3 + rnd() * 0.4;
      if (vert) { split(x, y, w * t, h, depth - 1); split(x + w * t, y, w * (1 - t), h, depth - 1); }
      else { split(x, y, w, h * t, depth - 1); split(x, y + h * t, w, h * (1 - t), depth - 1); }
    };
    split(0, 0, W, H, Math.round(p.depth));
    var g = p.gap * u, rr = p.round * u;
    leaves.forEach(function (l) {
      out.push('<rect x="' + f(l[0] + g / 2) + '" y="' + f(l[1] + g / 2) + '" width="' + f(Math.max(1, l[2] - g)) + '" height="' + f(Math.max(1, l[3] - g)) + '" rx="' + f(rr) + '" fill="' + col[1 + RND_ANG(rnd, 4)] + '"/>');
    });
    return { body: '<g id="Blocks">' + out.join('') + '</g>', defs: '', meta: leaves.length + ' blocks' };
  });

  /* ---------- Lines ---------- */
  def('moirelines', 'Moire Lines', 'Lines', 4, ['Background', 'Lines A', 'Lines B'], [
    pr('count', 'Lines per set', 20, 160, 1, 80), pr('delta', 'Angle between sets', 0.5, 25, 0.5, 6), pr('angle', 'Angle', 0, 180, 5, 20), pr('sw', 'Line weight', 0.3, 3, 0.1, 1)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, n = Math.round(p.count), D = Math.hypot(W, H), out = '';
    [0, 1].forEach(function (s) {
      var a = (p.angle + s * p.delta) * Math.PI / 180, dx = Math.cos(a), dy = Math.sin(a), nx = -dy, ny = dx, d = '';
      for (var k = 0; k < n; k++) {
        var o = (k / (n - 1) - 0.5) * D, mx = W / 2 + nx * o, my = H / 2 + ny * o;
        d += 'M' + f(mx - dx * D) + ' ' + f(my - dy * D) + 'L' + f(mx + dx * D) + ' ' + f(my + dy * D);
      }
      out += '<path id="Set ' + (s + 1) + '" d="' + d + '" stroke="' + col[1 + s] + '"/>';
    });
    return { body: '<g fill="none" stroke-width="' + f(p.sw * u) + '">' + out + '</g>', defs: '', meta: (2 * n) + ' lines in two sets' };
  }, ['#ffffff', '#111111', '#e0202c']);

  def('equalizer', 'Equalizer Bars', 'Lines', 9, ['Background', 'Bar start', 'Bar end'], [
    pr('count', 'Bars', 10, 80, 1, 36), pr('width', 'Bar width', 0.3, 0.95, 0.01, 0.62), pr('height', 'Height', 0.1, 1, 0.02, 0.7), pr('round', 'Roundness', 0, 1, 0.05, 1), tg('mirror', 'Mirror around center', 1)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, out = [], n = Math.round(p.count), d = W / n, bw = d * p.width, ph = [rnd() * TAU, rnd() * TAU, rnd() * TAU];
    for (var i = 0; i < n; i++) {
      var q = i / (n - 1), v = 0.5 + 0.22 * Math.sin(q * TAU * 1.5 + ph[0]) + 0.16 * Math.sin(q * TAU * 3.7 + ph[1]) + 0.12 * Math.sin(q * TAU * 7.9 + ph[2]);
      var h = H * p.height * clamp01(v * (0.6 + 0.4 * rnd())) + bw * 0.4, x = i * d + (d - bw) / 2, y = p.mirror ? H / 2 - h / 2 : H - h;
      out.push('<rect x="' + f(x) + '" y="' + f(y) + '" width="' + f(bw) + '" height="' + f(h) + '" rx="' + f(bw / 2 * p.round) + '" fill="' + mix(col[1], col[2], q) + '"/>');
    }
    return { body: '<g id="Bars">' + out.join('') + '</g>', defs: '', meta: n + ' bars' };
  });

  def('dashrain', 'Dash Rain', 'Lines', 1, ['Background', 'Dash 1', 'Dash 2', 'Dash 3'], [
    pr('count', 'Dashes', 40, 900, 5, 320), pr('angle', 'Angle', -90, 90, 1, 62), pr('len', 'Length', 10, 260, 2, 70), pr('sw', 'Line weight', 0.5, 8, 0.1, 2.4), pr('var', 'Length variation', 0, 1, 0.05, 0.6)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, n = Math.round(p.count), a = p.angle * Math.PI / 180, dx = Math.cos(a), dy = Math.sin(a), g = ['', '', ''];
    for (var i = 0; i < n; i++) {
      var x = rnd() * W, y = rnd() * H, L = p.len * u * (1 - p.var * rnd() * 0.85) / 2, k = RND_ANG(rnd, 3);
      g[k] += 'M' + f(x - dx * L) + ' ' + f(y - dy * L) + 'L' + f(x + dx * L) + ' ' + f(y + dy * L);
    }
    return { body: '<g fill="none" stroke-linecap="round" stroke-width="' + f(p.sw * u) + '">' + g.map(function (d, i) { return d ? '<path d="' + d + '" stroke="' + col[1 + i] + '"/>' : ''; }).join('') + '</g>', defs: '', meta: n + ' dashes' };
  });

  def('hatch', 'Cross Hatch', 'Lines', 4, ['Background', 'Hatch A', 'Hatch B'], [
    pr('cols', 'Columns across', 3, 24, 1, 10), pr('lines', 'Lines per tile', 3, 18, 1, 9), pr('sw', 'Line weight', 0.4, 4, 0.1, 1.2), pr('gap', 'Tile gap', 0, 14, 0.5, 4)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, cols = Math.round(p.cols), d = W / cols, rows = Math.ceil(H / d), n = Math.round(p.lines), g = p.gap * u / 2, A = '', B = '';
    for (var j = 0; j < rows; j++) for (var i = 0; i < cols; i++) {
      var x0 = i * d + g, y0 = j * d + g, x1 = (i + 1) * d - g, y1 = (j + 1) * d - g, o = RND_ANG(rnd, 4), s = '', k, seg;
      for (k = 0; k < n; k++) {
        var t = (k + 0.5) / n;
        if (o === 0) seg = [x0, y0 + t * (y1 - y0), x1, y0 + t * (y1 - y0)];
        else if (o === 1) seg = [x0 + t * (x1 - x0), y0, x0 + t * (x1 - x0), y1];
        else if (o === 2) seg = clipLine(x0 + (t * 2 - 1) * d, y0, x0 + (t * 2 - 1) * d + d * 1.4, y0 + d * 1.4, x0, y0, x1, y1);
        else seg = clipLine(x0 + (t * 2 - 1) * d + d * 1.4, y0, x0 + (t * 2 - 1) * d, y0 + d * 1.4, x0, y0, x1, y1);
        if (seg) s += 'M' + f(seg[0]) + ' ' + f(seg[1]) + 'L' + f(seg[2]) + ' ' + f(seg[3]);
      }
      if (o & 1) B += s; else A += s;
    }
    return { body: '<g fill="none" stroke-linecap="round" stroke-width="' + f(p.sw * u) + '"><path id="Hatch A" d="' + A + '" stroke="' + col[1] + '"/><path id="Hatch B" d="' + B + '" stroke="' + col[2] + '"/></g>', defs: '', meta: cols * rows + ' hatched tiles' };
  });

  def('warpgrid', 'Warped Grid', 'Lines', 10, ['Background', 'Line color'], [
    pr('lines', 'Lines each way', 6, 50, 1, 22), pr('amp', 'Warp strength', 0, 0.2, 0.005, 0.05), pr('freq', 'Warp waves', 0.3, 5, 0.1, 1.6), pr('sw', 'Line weight', 0.3, 4, 0.1, 1.2)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, n = Math.round(p.lines), S = 70, A = p.amp * Math.min(W, H), d = '', k, s, x, y, pts;
    var P = function (x, y) { return [x + A * Math.sin(TAU * p.freq * y / H + 1), y + A * Math.sin(TAU * p.freq * x / W + 2)]; };
    for (k = 0; k <= n; k++) {
      pts = []; for (s = -2; s <= S + 2; s++) pts.push(P(k * W / n, s * H / S)); d += smoothPath(pts, false);
      pts = []; for (s = -2; s <= S + 2; s++) pts.push(P(s * W / S, k * H / n)); d += smoothPath(pts, false);
    }
    return { body: '<path id="Grid" d="' + d + '" fill="none" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '"/>', defs: '', meta: (2 * n + 2) + ' bending lines' };
  });

  def('halftonelines', 'Halftone Lines', 'Lines', 6, ['Background', 'Line color'], [
    pr('rows', 'Lines', 8, 80, 1, 34), pr('thick', 'Max thickness', 0.2, 1.1, 0.02, 0.85), pr('freq', 'Waves', 0.3, 6, 0.1, 1.6), pr('tilt', 'Vertical drift', 0, 1.5, 0.05, 0.5), tg('fade', 'Fade across instead', 0)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = '', n = Math.round(p.rows), sp = H / n, S = 110, k, s;
    for (k = 0; k < n; k++) {
      var top = [], bot = [], y = (k + 0.5) * sp;
      for (s = 0; s <= S; s++) {
        var x = W * s / S, t = p.fade ? x / W : 0.5 + 0.5 * Math.sin(TAU * p.freq * x / W + p.tilt * TAU * k / n), h = Math.max(0.4, sp * p.thick * t) / 2;
        top.push([x, y - h]); bot.push([x, y + h]);
      }
      out += polyPath(top.concat(bot.reverse()), true);
    }
    return { body: '<path id="Lines" d="' + out + '" fill="' + col[1] + '"/>', defs: '', meta: n + ' lines with changing thickness' };
  });

  def('zigzaglines', 'Zigzag Lines', 'Lines', 2, ['Background', 'Line start', 'Line end'], [
    pr('rows', 'Lines', 6, 60, 1, 20), pr('teeth', 'Zigzags across', 6, 80, 1, 30), pr('amp', 'Depth', 0.1, 1.2, 0.02, 0.5), pr('sw', 'Line weight', 0.5, 6, 0.1, 2), tg('shift', 'Shift each line', 1)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, out = [], n = Math.round(p.rows), t2 = Math.round(p.teeth), sp = H / n, tw = W / t2;
    for (var k = 0; k <= n; k++) {
      var pts = [], y = k * sp, off = p.shift ? (k & 1) : 0;
      for (var t = -1; t <= t2 + 1; t++) pts.push([(t + off * 0.5) * tw, y + ((t & 1) ? p.amp * sp / 2 : -p.amp * sp / 2)]);
      out.push('<path d="' + polyPath(pts, false) + '" stroke="' + mix(col[1], col[2], k / n) + '"/>');
    }
    return { body: '<g fill="none" stroke-linejoin="round" stroke-linecap="round" stroke-width="' + f(p.sw * u) + '">' + out.join('') + '</g>', defs: '', meta: (n + 1) + ' zigzag lines' };
  });

  def('isogrid', 'Isometric Grid', 'Lines', 5, ['Background', 'Line color', 'Node color'], [
    pr('cols', 'Columns across', 3, 40, 1, 14), pr('sw', 'Line weight', 0.3, 4, 0.1, 1), pr('dot', 'Node size', 0, 4, 0.1, 0), tg('iso', 'Isometric direction', 1)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, a = W / Math.round(p.cols), h = a * 0.866, T = 0.57735, d = '', dots = '', k, j, i;
    var M = function (x, y) { return p.iso ? [y, x] : [x, y]; };
    var seg = function (x1, y1, x2, y2) { var A = M(x1, y1), B = M(x2, y2); d += 'M' + f(A[0]) + ' ' + f(A[1]) + 'L' + f(B[0]) + ' ' + f(B[1]); };
    var Lx = p.iso ? H : W, Ly = p.iso ? W : H;
    for (j = 0; j * h <= Ly + h; j++) seg(0, j * h, Lx, j * h);
    for (k = -Math.ceil(Ly * T / a) - 1; k <= Lx / a + 1; k++) { seg(k * a, 0, k * a + Ly * T, Ly); seg(k * a, 0, k * a - Ly * T, Ly); }
    if (p.dot > 0) for (j = 0; j * h <= Ly + h; j++) for (i = -1; i * a <= Lx + a; i++) {
      var q = M(i * a + ((j & 1) ? a / 2 : 0), j * h); dots += '<circle cx="' + f(q[0]) + '" cy="' + f(q[1]) + '" r="' + f(p.dot * u * 2) + '"/>';
    }
    return { body: '<path id="Lines" d="' + d + '" fill="none" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '"/><g id="Nodes" fill="' + col[2] + '">' + dots + '</g>', defs: '', meta: 'triangular grid, three line directions' };
  });

  def('pinstripes', 'Pinstripes', 'Lines', 7, ['Background', 'Stripe', 'Accent stripe'], [
    pr('count', 'Stripes', 8, 120, 1, 40), pr('angle', 'Angle', -90, 90, 1, 0), pr('sw', 'Line weight', 0.3, 8, 0.1, 1.4), pr('accent', 'Accent every', 0, 10, 1, 5), tg('double', 'Double lines', 0)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, n = Math.round(p.count), D = Math.hypot(W, H), a = (p.angle + 90) * Math.PI / 180, out = [], ac = Math.round(p.accent);
    var dx = Math.cos(a), dy = Math.sin(a), nx = -dy, ny = dx;
    for (var k = 0; k <= n; k++) {
      var o = (k / n - 0.5) * D, mx = W / 2 + nx * o, my = H / 2 + ny * o, isA = ac && k % ac === 0, d = '';
      d += 'M' + f(mx - dx * D) + ' ' + f(my - dy * D) + 'L' + f(mx + dx * D) + ' ' + f(my + dy * D);
      if (p.double) { var q = p.sw * u * 3; d += 'M' + f(mx + nx * q - dx * D) + ' ' + f(my + ny * q - dy * D) + 'L' + f(mx + nx * q + dx * D) + ' ' + f(my + ny * q + dy * D); }
      out.push('<path d="' + d + '" stroke="' + (isA ? col[2] : col[1]) + '"/>');
    }
    return { body: '<g fill="none" stroke-width="' + f(p.sw * u) + '">' + out.join('') + '</g>', defs: '', meta: (n + 1) + ' stripes' };
  });

  def('noiseflow', 'Noise Flow', 'Organic', 10, ['Background', 'Line start', 'Line end'], [
    pr('lines', 'Lines', 80, 1200, 10, 420), pr('steps', 'Line length', 10, 90, 1, 42), pr('scale', 'Noise scale', 0.5, 6, 0.1, 2), pr('twist', 'Twist', 0.5, 8, 0.1, 3.2), pr('sw', 'Line weight', 0.3, 4, 0.1, 1.2)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, nz = makeNoise(Math.floor(rnd() * 1e9)), n = Math.round(p.lines), S = Math.round(p.steps), out = [], step = 7 * u;
    for (var i = 0; i < n; i++) {
      var x = rnd() * W, y = rnd() * H, d = 'M' + f1(x) + ' ' + f1(y);
      for (var s = 0; s < S; s++) {
        var a = nz(x / W * p.scale * 3, y / W * p.scale * 3) * TAU * p.twist;
        x += Math.cos(a) * step; y += Math.sin(a) * step; d += 'L' + f1(x) + ' ' + f1(y);
      }
      out.push('<path d="' + d + '" stroke="' + mix(col[1], col[2], rnd()) + '"/>');
    }
    return { body: '<g fill="none" stroke-linecap="round" stroke-linejoin="round" stroke-width="' + f(p.sw * u) + '">' + out.join('') + '</g>', defs: '', meta: n + ' flowing lines' };
  });

  /* ---------- Radial ---------- */
  def('polardots', 'Polar Dots', 'Radial', 5, ['Background', 'Dot A', 'Dot B'], [
    pr('rings', 'Rings', 4, 34, 1, 16), pr('size', 'Dot size', 0.15, 0.95, 0.01, 0.55), pr('cx', 'Center X', 0, 1, 0.01, 0.5), pr('cy', 'Center Y', 0, 1, 0.01, 0.5), tg('grow', 'Dots grow outward', 1)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = [], n = Math.round(p.rings), cx = p.cx * W, cy = p.cy * H;
    var R0 = Math.hypot(Math.max(cx, W - cx), Math.max(cy, H - cy)) * 1.05, gap = R0 / n;
    out.push('<circle cx="' + f(cx) + '" cy="' + f(cy) + '" r="' + f(gap * 0.3 * p.size) + '" fill="' + col[1] + '"/>');
    for (var k = 1; k <= n; k++) {
      var r = k * gap, m = Math.max(6, Math.round(TAU * r / gap)), rad = gap * 0.5 * p.size * (p.grow ? 0.35 + 0.65 * k / n : 1);
      for (var i = 0; i < m; i++) {
        var a = i * TAU / m + (k & 1) * Math.PI / m;
        out.push('<circle cx="' + f(cx + r * Math.cos(a)) + '" cy="' + f(cy + r * Math.sin(a)) + '" r="' + f(rad) + '" fill="' + col[1 + (k & 1)] + '"/>');
      }
    }
    return { body: '<g id="Dots">' + out.join('') + '</g>', defs: '', meta: out.length + ' dots on ' + n + ' rings' };
  });

  def('sunfan', 'Sun Fan', 'Retro', 0, ['Background', 'Ray color', 'Sun color', 'Ground color'], [
    pr('rays', 'Rays', 6, 60, 2, 28), pr('hy', 'Horizon height', 0.3, 1.3, 0.01, 0.78), pr('sun', 'Sun size', 0, 0.5, 0.01, 0.2), tg('full', 'Rays all around', 0), tg('ground', 'Ground', 1)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = [], n = Math.round(p.rays), cx = W / 2, cy = p.hy * H, R = Math.hypot(W, H) * 1.6, span = p.full ? TAU : Math.PI, a0 = p.full ? 0 : Math.PI;
    for (var i = 0; i < n; i += 2) {
      var A = a0 + i * span / n, B = a0 + (i + 1) * span / n;
      out.push('<polygon points="' + f(cx) + ',' + f(cy) + ' ' + f(cx + R * Math.cos(A)) + ',' + f(cy + R * Math.sin(A)) + ' ' + f(cx + R * Math.cos(B)) + ',' + f(cy + R * Math.sin(B)) + '" fill="' + col[1] + '"/>');
    }
    var body = '<g id="Rays">' + out.join('') + '</g>';
    if (p.sun > 0) body += '<circle id="Sun" cx="' + f(cx) + '" cy="' + f(cy) + '" r="' + f(p.sun * H) + '" fill="' + col[2] + '"/>';
    if (!p.full && p.ground && cy < H) body += '<rect id="Ground" x="0" y="' + f(cy) + '" width="' + W + '" height="' + f(H - cy + 1) + '" fill="' + col[3] + '"/>';
    return { body: body, defs: '', meta: n / 2 + ' rays and a sun' };
  });

  def('roses', 'Rose Curves', 'Radial', 6, ['Background', 'Line start', 'Line end'], [
    pr('curves', 'Curves', 3, 40, 1, 16), pr('petals', 'Petals', 2, 12, 1, 5), pr('turn', 'Turn per curve', 0, 20, 0.5, 4), pr('size', 'Size', 0.3, 1.3, 0.02, 0.85), pr('sw', 'Line weight', 0.3, 3, 0.1, 1)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, out = [], n = Math.round(p.curves), k = p.petals, R = Math.min(W, H) / 2 * p.size;
    for (var m = 1; m <= n; m++) {
      var s = m / n, rot = m * p.turn * Math.PI / 180, pts = [];
      for (var i = 0; i <= 240; i++) {
        var t = i / 240 * TAU, r = R * s * Math.cos(k * t);
        pts.push([W / 2 + r * Math.cos(t + rot), H / 2 + r * Math.sin(t + rot)]);
      }
      out.push('<path d="' + polyPath(pts, true) + '" stroke="' + mix(col[1], col[2], s) + '"/>');
    }
    return { body: '<g fill="none" stroke-linejoin="round" stroke-width="' + f(p.sw * u) + '">' + out.join('') + '</g>', defs: '', meta: n + ' nested rose curves' };
  });

  def('wavyrings', 'Wavy Rings', 'Radial', 10, ['Background', 'Ring A', 'Ring B'], [
    pr('rings', 'Rings', 6, 50, 1, 22), pr('lobes', 'Lobes', 3, 16, 1, 7), pr('amp', 'Wobble', 0, 0.35, 0.01, 0.1), pr('phase', 'Twist per ring', 0, 1.5, 0.05, 0.4), tg('filled', 'Filled rings', 1), pr('sw', 'Line weight', 0.4, 5, 0.1, 1.5)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, out = [], n = Math.round(p.rings), L = Math.round(p.lobes), R0 = Math.hypot(W, H) * 0.56;
    for (var k = 0; k < n; k++) {
      var base = R0 * (1 - k / n), pts = [], A = p.amp * base * 0.5;
      for (var i = 0; i < 120; i++) { var t = i / 120 * TAU, r = base + A * Math.sin(L * t + k * p.phase); pts.push([W / 2 + r * Math.cos(t), H / 2 + r * Math.sin(t)]); }
      out.push(p.filled ? '<path d="' + polyPath(pts, true) + '" fill="' + col[1 + (k & 1)] + '"/>' : '<path d="' + polyPath(pts, true) + '" fill="none" stroke="' + col[1 + (k & 1)] + '" stroke-width="' + f(p.sw * u) + '"/>');
    }
    return { body: '<g id="Rings">' + out.join('') + '</g>', defs: '', meta: n + ' wavy rings' };
  });

  def('moirerings', 'Moire Rings', 'Radial', 4, ['Background', 'Rings A', 'Rings B'], [
    pr('count', 'Rings per set', 20, 120, 1, 56), pr('offset', 'Center offset', 0.02, 0.5, 0.01, 0.12), pr('angle', 'Offset angle', 0, 180, 5, 0), pr('sw', 'Line weight', 0.3, 3, 0.1, 1)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, n = Math.round(p.count), R = Math.hypot(W, H) * 0.72, a = p.angle * Math.PI / 180, o = p.offset * W / 2, out = '';
    [-1, 1].forEach(function (sg, s) {
      var cx = W / 2 + sg * o * Math.cos(a), cy = H / 2 + sg * o * Math.sin(a), g = '';
      for (var k = 1; k <= n; k++) g += '<circle cx="' + f(cx) + '" cy="' + f(cy) + '" r="' + f(R * k / n) + '"/>';
      out += '<g id="Set ' + (s + 1) + '" stroke="' + col[1 + s] + '">' + g + '</g>';
    });
    return { body: '<g fill="none" stroke-width="' + f(p.sw * u) + '">' + out + '</g>', defs: '', meta: (2 * n) + ' circles in two sets' };
  }, ['#ffffff', '#111111', '#e0202c']);

  def('ripples', 'Ripples', 'Radial', 1, ['Background', 'Ring 1', 'Ring 2', 'Ring 3'], [
    pr('drops', 'Drops', 2, 12, 1, 5), pr('rings', 'Rings per drop', 3, 22, 1, 10), pr('space', 'Ring spacing', 0.01, 0.08, 0.002, 0.035), pr('sw', 'Line weight', 0.4, 5, 0.1, 1.8), pr('fade', 'Fade out', 0, 1, 0.05, 0.7)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, out = [], m = Math.round(p.rings), sp = p.space * Math.min(W, H);
    for (var d = 0; d < Math.round(p.drops); d++) {
      var cx = rnd() * W, cy = rnd() * H, color = col[1 + (d % 3)];
      for (var j = 1; j <= m; j++) {
        var t = j / m;
        out.push('<circle cx="' + f(cx) + '" cy="' + f(cy) + '" r="' + f(j * sp * (0.8 + 0.4 * (d % 3) / 2)) + '" stroke="' + mix(color, col[0], t * p.fade) + '" stroke-width="' + f(p.sw * u * (1 - t * 0.5)) + '"/>');
      }
    }
    return { body: '<g fill="none">' + out.join('') + '</g>', defs: '', meta: out.length + ' ripple rings' };
  });

  def('sunflower', 'Sunflower Dots', 'Radial', 8, ['Background', 'Dot start', 'Dot end'], [
    pr('count', 'Dots', 200, 2600, 50, 1100), pr('angle', 'Angle step', 136.5, 138.5, 0.02, 137.51), pr('size', 'Dot size', 0.2, 1.2, 0.02, 0.62), pr('grow', 'Dots grow outward', 0, 1.5, 0.05, 0.7), pr('cx', 'Center X', 0, 1, 0.01, 0.5)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = [], n = Math.round(p.count), cx = p.cx * W, cy = H / 2, R = Math.max(W, H) * 0.62, k = R / Math.sqrt(n), ga = p.angle * Math.PI / 180;
    for (var i = 1; i <= n; i++) {
      var r = k * Math.sqrt(i), a = i * ga, x = cx + r * Math.cos(a), y = cy + r * Math.sin(a), q = i / n, rd = k * 0.5 * p.size * (0.35 + p.grow * q);
      if (x < -rd || x > W + rd || y < -rd || y > H + rd) continue;
      out.push('<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(rd) + '" fill="' + mix(col[1], col[2], q) + '"/>');
    }
    return { body: '<g id="Dots">' + out.join('') + '</g>', defs: '', meta: out.length + ' dots on a golden spiral' };
  });

  /* ======================== EXTRA FAMILIES (part 3: organic, retro, soft, scatter) ======================== */
  def('voronoi', 'Voronoi Cells', 'Organic', 5, ['Background', 'Start tone', 'End tone', 'Gap color'], [
    pr('cols', 'Cells across', 4, 30, 1, 12), pr('jit', 'Irregularity', 0, 1, 0.02, 0.85), pr('gap', 'Gap', 0, 8, 0.25, 1.5), pr('var', 'Tone variation', 0, 0.6, 0.02, 0.2), pr('angle', 'Gradient angle', 0, 360, 5, 40)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, out = [], v = voronoi(W, H, Math.round(p.cols), p.jit, rnd);
    var a = p.angle * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a), E = (Math.abs(W * ca) + Math.abs(H * sa)) / 2 || 1;
    v.cells.forEach(function (cell) {
      var t = clamp01(((cell.s[0] - W / 2) * ca + (cell.s[1] - H / 2) * sa) / E * 0.5 + 0.5 + (rnd() - 0.5) * p.var * 2);
      out.push('<polygon points="' + cell.poly.map(function (q) { return f(q[0]) + ',' + f(q[1]); }).join(' ') + '" fill="' + mix(col[1], col[2], t) + '"/>');
    });
    return { body: '<g id="Cells" stroke="' + col[3] + '" stroke-width="' + f(p.gap * u) + '" stroke-linejoin="round">' + out.join('') + '</g>', defs: '', meta: out.length + ' cells' };
  });

  def('celllines', 'Cell Lines', 'Organic', 10, ['Background', 'Line color', 'Dot color'], [
    pr('cols', 'Cells across', 4, 30, 1, 11), pr('jit', 'Irregularity', 0, 1, 0.02, 0.9), pr('sw', 'Line weight', 0.4, 5, 0.1, 1.4), pr('dot', 'Dot size', 0, 6, 0.2, 2.4)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, d = '', dots = '', v = voronoi(W, H, Math.round(p.cols), p.jit, rnd);
    v.cells.forEach(function (cell) {
      d += polyPath(cell.poly, true);
      if (p.dot > 0) dots += '<circle cx="' + f(cell.s[0]) + '" cy="' + f(cell.s[1]) + '" r="' + f(p.dot * u * 2) + '"/>';
    });
    return { body: '<path id="Lines" d="' + d + '" fill="none" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '" stroke-linejoin="round"/><g id="Dots" fill="' + col[2] + '">' + dots + '</g>', defs: '', meta: v.cells.length + ' cells' };
  });

  def('mountains', 'Mountain Layers', 'Organic', 9, ['Sky', 'Far layer', 'Near layer', 'Sun'], [
    pr('layers', 'Layers', 3, 10, 1, 5), pr('peaks', 'Peaks per layer', 2, 16, 1, 6), pr('rough', 'Height variation', 0.1, 1, 0.02, 0.6), tg('smooth', 'Rolling hills', 0), tg('sun', 'Sun', 1)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, out = [], n = Math.round(p.layers), pk = Math.round(p.peaks), body = '';
    if (p.sun) body += '<circle id="Sun" cx="' + f(W * (0.2 + rnd() * 0.6)) + '" cy="' + f(H * 0.3) + '" r="' + f(H * 0.12) + '" fill="' + col[3] + '"/>';
    for (var k = 0; k < n; k++) {
      var t = n > 1 ? k / (n - 1) : 0, base = H * (0.4 + 0.5 * t), hgt = H * 0.34 * (1 - 0.45 * t) * p.rough, pts = [], m = pk * 2 + 1;
      for (var i = 0; i < m; i++) pts.push([W * i / (m - 1), base - ((i & 1) ? hgt * (0.55 + rnd() * 0.45) : hgt * rnd() * 0.3)]);
      var top = p.smooth ? smoothPath(pts, false) : polyPath(pts, false);
      out.push('<path d="' + top + 'L' + f(W) + ' ' + f(H + 5) + 'L0 ' + f(H + 5) + 'Z" fill="' + mix(col[1], col[2], t) + '"/>');
    }
    return { body: body + '<g id="Layers">' + out.join('') + '</g>', defs: '', meta: n + ' mountain layers' };
  });

  def('noisedots', 'Noise Dots', 'Organic', 6, ['Background', 'Dot A', 'Dot B'], [
    pr('cols', 'Dots across', 12, 80, 1, 40), pr('scale', 'Noise scale', 0.5, 8, 0.1, 2.5), pr('size', 'Max size', 0.3, 1.3, 0.02, 0.9), pr('contrast', 'Contrast', 0.5, 3, 0.1, 1.6), tg('stagger', 'Offset rows', 1)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, nz = makeNoise(Math.floor(rnd() * 1e9)), out = [], cols = Math.round(p.cols), d = W / cols, dy = p.stagger ? d * 0.866 : d, rows = Math.ceil(H / dy) + 1;
    for (var j = 0; j < rows; j++) for (var i = 0; i <= cols; i++) {
      var x = i * d + ((p.stagger && (j & 1)) ? d / 2 : 0), y = j * dy, v = nz(x / W * p.scale * 2, y / W * p.scale * 2);
      var t = clamp01((v - 0.5) * p.contrast + 0.5), r = d / 2 * p.size * t;
      if (r > 0.4) out.push('<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(r) + '" fill="' + (t > 0.72 ? col[2] : col[1]) + '"/>');
    }
    return { body: '<g id="Dots">' + out.join('') + '</g>', defs: '', meta: out.length + ' dots sized by noise' };
  });

  def('camo', 'Camouflage', 'Organic', 8, ['Background', 'Patch 1', 'Patch 2', 'Patch 3', 'Patch 4'], [
    pr('count', 'Patches', 10, 120, 1, 56), pr('size', 'Patch size', 0.05, 0.3, 0.01, 0.14), pr('wobble', 'Wobble', 0.1, 0.9, 0.02, 0.5)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, out = [], n = Math.round(p.count), m = Math.min(W, H);
    for (var b = 0; b < n; b++) {
      var cx = rnd() * W, cy = rnd() * H, R = m * p.size * (0.5 + rnd()), K = 9, pts = [], off = rnd() * TAU;
      for (var i = 0; i < K; i++) { var a = off + i / K * TAU, r = R * (1 + p.wobble * (rnd() - 0.5) * 1.6); pts.push([cx + r * Math.cos(a) * 1.35, cy + r * Math.sin(a) * 0.8]); }
      out.push('<path d="' + smoothPath(pts, true) + '" fill="' + col[1 + (b % 4)] + '"/>');
    }
    return { body: '<g id="Patches">' + out.join('') + '</g>', defs: '', meta: n + ' soft patches' };
  });

  def('starfield', 'Starfield', 'Soft', 9, ['Night sky', 'Star color', 'Accent star'], [
    pr('count', 'Stars', 60, 1400, 10, 420), pr('size', 'Star size', 0.4, 3, 0.1, 1.2), pr('sparkle', 'Sparkles', 0, 0.3, 0.01, 0.05), pr('dim', 'Dim variation', 0, 0.9, 0.02, 0.5)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, n = Math.round(p.count), dots = '', sp = '', cnt = 0;
    for (var i = 0; i < n; i++) {
      var x = rnd() * W, y = rnd() * H, r = u * p.size * (0.5 + 3 * Math.pow(rnd(), 3)), color = mix(col[1], col[0], rnd() * p.dim);
      if (rnd() < p.sparkle) {
        var pts = polarPts(4, r * 4, -Math.PI / 2, 0.18).map(function (q) { return f(x + q[0]) + ',' + f(y + q[1]); });
        sp += '<polygon points="' + pts.join(' ') + '" fill="' + col[2] + '"/>';
      } else dots += '<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(r) + '" fill="' + color + '"/>';
      cnt++;
    }
    return { body: '<g id="Stars">' + dots + '</g><g id="Sparkles">' + sp + '</g>', defs: '', meta: cnt + ' stars' };
  });

  function scatter(id, name, kind, pal, o) {
    def(id, name, 'Shapes', pal, ['Background', 'Color 1', 'Color 2', 'Color 3', 'Color 4'], [
      pr('count', 'Pieces', 10, 360, 2, o.count), pr('size', 'Piece size', 10, 400, 2, o.size), pr('var', 'Size variation', 0, 0.9, 0.02, o.vary),
      tg('overlap', 'Allow overlap', o.overlap), tg('spin', 'Random rotation', o.spin), pr('round', 'Corner radius', 0, 1, 0.05, kind === 'square' ? 0.2 : 0)
    ], function (c) {
      var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, rnd = c.rnd, out = [], placed = [], n = Math.round(p.count), tries = 0;
      while (placed.length < n && tries < n * 18) {
        tries++;
        var s = p.size * u * (1 - p.var * rnd()), x = rnd() * W, y = rnd() * H, ok = true;
        if (!p.overlap) for (var q = 0; q < placed.length; q++) { var z = placed[q]; if (Math.hypot(z.x - x, z.y - y) < (z.s + s) * 0.6) { ok = false; break; } }
        if (!ok) continue;
        placed.push({ x: x, y: y, s: s });
        var color = col[1 + RND_ANG(rnd, 4)], rot = p.spin ? rnd() * 360 : 0, h = s / 2;
        var tr = ' transform="translate(' + f(x) + ' ' + f(y) + ')' + (rot ? ' rotate(' + f(rot) + ')' : '') + '"';
        if (kind === 'square') out.push('<rect x="' + f(-h) + '" y="' + f(-h) + '" width="' + f(s) + '" height="' + f(s) + '" rx="' + f(h * p.round) + '" fill="' + color + '"' + tr + '/>');
        else if (kind === 'triangle') out.push('<polygon points="' + polarPts(3, h * 1.15, -Math.PI / 2).map(function (t) { return f(t[0]) + ',' + f(t[1]); }).join(' ') + '" fill="' + color + '"' + tr + '/>');
        else out.push('<circle r="' + f(h) + '" fill="' + color + '"' + tr + '/>');
      }
      return { body: '<g id="Pieces">' + out.join('') + '</g>', defs: '', meta: placed.length + ' pieces' };
    });
  }
  scatter('squarescatter', 'Square Scatter', 'square', 2, { count: 90, size: 60, vary: 0.5, overlap: 0, spin: 1 });
  scatter('triscatter', 'Triangle Scatter', 'triangle', 9, { count: 110, size: 54, vary: 0.5, overlap: 0, spin: 1 });
  scatter('circlelayers', 'Circle Layers', 'circle', 10, { count: 44, size: 260, vary: 0.8, overlap: 1, spin: 0 });

  def('wavedots', 'Wave Dots', 'Shapes', 6, ['Background', 'Dot start', 'Dot end'], [
    pr('rows', 'Rows', 6, 40, 1, 18), pr('per', 'Dots per row', 20, 100, 1, 52), pr('amp', 'Wave height', 0, 0.1, 0.005, 0.035), pr('waves', 'Waves', 0.5, 6, 0.1, 2), pr('size', 'Dot size', 0.3, 1.2, 0.02, 0.8)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = [], n = Math.round(p.rows), m = Math.round(p.per), rs = H / n, cs = W / m;
    for (var j = 0; j < n; j++) for (var i = 0; i <= m; i++) {
      var x = i * cs, q = x / W, s = 0.5 + 0.5 * Math.sin(TAU * p.waves * q + j * 0.5), y = (j + 0.5) * rs + p.amp * H * Math.sin(TAU * p.waves * q + j * 0.5);
      out.push('<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(Math.min(rs, cs) / 2 * p.size * (0.2 + 0.8 * s)) + '" fill="' + mix(col[1], col[2], j / (n - 1)) + '"/>');
    }
    return { body: '<g id="Dots">' + out.join('') + '</g>', defs: '', meta: out.length + ' dots on wave rows' };
  });

  /* ---------- Retro ---------- */
  def('rainbowscales', 'Rainbow Scales', 'Retro', 3, ['Background', 'Band 1', 'Band 2', 'Band 3', 'Band 4'], [
    pr('cols', 'Columns across', 3, 20, 1, 8), pr('bands', 'Bands per scale', 2, 6, 1, 4)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = [], cols = Math.round(p.cols), b = Math.round(p.bands), dx = W / cols, R = dx * 0.75, dy = dx * 0.36, rows = Math.ceil(H / dy) + 3;
    for (var j = -1; j < rows; j++) for (var i = -1; i <= cols; i++) {
      var x = i * dx + ((j & 1) ? dx / 2 : 0), y = j * dy;
      for (var k = b; k >= 1; k--) out.push('<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(R * k / b) + '" fill="' + col[1 + ((b - k) % 4)] + '"/>');
    }
    return { body: '<g id="Scales">' + out.join('') + '</g>', defs: '', meta: cols + ' columns of layered scales' };
  });

  def('gradstripes', 'Gradient Stripes', 'Retro', 9, ['Background', 'Start color', 'End color'], [
    pr('count', 'Stripes', 6, 80, 1, 24), pr('angle', 'Angle', -90, 90, 1, 25), pr('lift', 'Alternate lightness', 0, 0.4, 0.01, 0.1), pr('mid', 'Color midpoint', 0.15, 0.85, 0.01, 0.5)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = [], n = Math.round(p.count), D = Math.hypot(W, H), w = 2 * D / n;
    for (var k = 0; k < n; k++) {
      var t = n > 1 ? k / (n - 1) : 0, tt = t < p.mid ? 0.5 * t / p.mid : 0.5 + 0.5 * (t - p.mid) / (1 - p.mid), color = mix(col[1], col[2], tt);
      out.push('<rect x="' + f(-D + k * w) + '" y="' + f(-D) + '" width="' + f(w + 0.6) + '" height="' + f(2 * D) + '" fill="' + ((k & 1) ? lighten(color, p.lift) : color) + '"/>');
    }
    return { body: '<g id="Stripes" transform="translate(' + f(W / 2) + ' ' + f(H / 2) + ') rotate(' + f(p.angle) + ')">' + out.join('') + '</g>', defs: '', meta: n + ' stripes blending two colours' };
  });

  def('waveBands', 'Wave Bands', 'Retro', 0, ['Background', 'Band 1', 'Band 2', 'Band 3', 'Band 4'], [
    pr('bands', 'Bands', 3, 22, 1, 9), pr('amp', 'Wave height', 0.01, 0.25, 0.005, 0.08), pr('freq', 'Waves', 0.5, 4, 0.1, 1.3), pr('drift', 'Drift per band', 0, 1.5, 0.05, 0.35)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, out = [], n = Math.round(p.bands), S = 60, curves = [], k, s;
    for (k = 0; k <= n; k++) {
      var pts = [], base = (k / n) * H * 1.3 - H * 0.15;
      for (s = -2; s <= S + 2; s++) { var x = W * s / S; pts.push([x, base + p.amp * H * Math.sin(TAU * p.freq * x / W + k * p.drift)]); }
      curves.push(pts);
    }
    for (k = 0; k < n; k++) {
      var top = curves[k], bot = curves[k + 1].slice().reverse();
      out.push('<path d="' + smoothPath(top, false) + 'L' + bot.map(function (q) { return f(q[0]) + ' ' + f(q[1]); }).join('L') + 'Z" fill="' + col[1 + (k % 4)] + '"/>');
    }
    return { body: '<g id="Bands">' + out.join('') + '</g>', defs: '', meta: n + ' flowing bands' };
  });

  def('perspective', 'Perspective Grid', 'Retro', 9, ['Floor', 'Grid line', 'Sky', 'Sun'], [
    pr('hy', 'Horizon height', 0.25, 0.75, 0.01, 0.46), pr('vlines', 'Depth lines', 6, 50, 1, 22), pr('hlines', 'Cross lines', 6, 40, 1, 14), pr('power', 'Perspective', 1, 3.2, 0.1, 2.2), pr('sun', 'Sun size', 0, 0.3, 0.01, 0.17), pr('sw', 'Line weight', 0.4, 4, 0.1, 1.6)
  ], function (c) {
    var W = c.W, H = c.H, u = c.u, p = c.p, col = c.col, hy = p.hy * H, n = Math.round(p.vlines), m = Math.round(p.hlines), d = '';
    var body = '<rect id="Sky" width="' + W + '" height="' + f(hy) + '" fill="' + col[2] + '"/>';
    if (p.sun > 0) body += '<circle id="Sun" cx="' + f(W / 2) + '" cy="' + f(hy) + '" r="' + f(p.sun * Math.min(W, H)) + '" fill="' + col[3] + '"/>';
    body += '<rect id="Floor" y="' + f(hy) + '" width="' + W + '" height="' + f(H - hy + 1) + '" fill="' + col[0] + '"/>';
    for (var k = 0; k <= n; k++) d += 'M' + f(W / 2) + ' ' + f(hy) + 'L' + f(W / 2 + (k / n - 0.5) * W * 4) + ' ' + f(H);
    for (var j = 1; j <= m; j++) { var y = hy + (H - hy) * Math.pow(j / m, p.power); d += 'M0 ' + f(y) + 'L' + W + ' ' + f(y); }
    body += '<path id="Grid" d="' + d + '" fill="none" stroke="' + col[1] + '" stroke-width="' + f(p.sw * u) + '"/>';
    return { body: body, defs: '', meta: 'receding grid with a horizon' };
  });

  /* ---------- Soft: real SVG gradients ---------- */
  def('lineargrad', 'Linear Gradient', 'Soft', 1, ['Background', 'Start', 'End', 'Middle'], [
    pr('angle', 'Angle', 0, 360, 5, 45), pr('mid', 'Middle position', 0.1, 0.9, 0.01, 0.5)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, a = p.angle * Math.PI / 180, dx = Math.cos(a), dy = Math.sin(a), L = (Math.abs(W * dx) + Math.abs(H * dy)) / 2;
    var defs = '<linearGradient id="grad" gradientUnits="userSpaceOnUse" x1="' + f(W / 2 - dx * L) + '" y1="' + f(H / 2 - dy * L) + '" x2="' + f(W / 2 + dx * L) + '" y2="' + f(H / 2 + dy * L) + '">' +
      '<stop offset="0" stop-color="' + col[1] + '"/><stop offset="' + f(p.mid) + '" stop-color="' + col[3] + '"/><stop offset="1" stop-color="' + col[2] + '"/></linearGradient>';
    return { body: '<rect id="Gradient" width="' + W + '" height="' + H + '" fill="url(#grad)"/>', defs: defs, meta: 'one linear gradient with 3 stops' };
  }, ['#ffffff', '#6a5af9', '#ff7eb3', '#b86df0']);

  def('radialgrad', 'Radial Gradient', 'Soft', 9, ['Background', 'Center', 'Edge', 'Middle'], [
    pr('cx', 'Center X', 0, 1, 0.01, 0.5), pr('cy', 'Center Y', 0, 1, 0.01, 0.45), pr('radius', 'Radius', 0.2, 1.6, 0.02, 0.85), pr('mid', 'Middle position', 0.1, 0.9, 0.01, 0.5)
  ], function (c) {
    var W = c.W, H = c.H, p = c.p, col = c.col;
    var defs = '<radialGradient id="grad" gradientUnits="userSpaceOnUse" cx="' + f(p.cx * W) + '" cy="' + f(p.cy * H) + '" r="' + f(p.radius * Math.max(W, H)) + '">' +
      '<stop offset="0" stop-color="' + col[1] + '"/><stop offset="' + f(p.mid) + '" stop-color="' + col[3] + '"/><stop offset="1" stop-color="' + col[2] + '"/></radialGradient>';
    return { body: '<rect id="Gradient" width="' + W + '" height="' + H + '" fill="url(#grad)"/>', defs: defs, meta: 'one radial gradient with 3 stops' };
  }, ['#ffffff', '#ffd36b', '#2b1055', '#ff5e62']);


  /* ---------- Glow family: vertical glass bars over glowing waves, and smooth light ribbons ---------- */
  function sstep(a, b, x) { var t = clamp01((x - a) / (b - a)); return t * t * (3 - 2 * t); }
  function mixc(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
  function hx(c) { return rgb2hex(c[0], c[1], c[2]); }
  function glassParams(d, skip) {
    var L = [pr('bars', 'Bars', 30, 280, 1, d.bars), pr('duty', 'Bar width', 0.2, 0.95, 0.01, d.duty),
      pr('waves', 'Glow waves', 1, 4, 1, d.waves), pr('amp', 'Wave height', 0.03, 0.4, 0.01, d.amp),
      pr('freq', 'Wave count', 0.4, 3, 0.05, d.freq), pr('glow', 'Glow size', 0.05, 0.5, 0.01, d.glow),
      pr('spread', 'Colour drift', 0, 1, 0.02, d.spread), pr('core', 'Bright core', 0, 1, 0.02, d.core),
      pr('fade', 'Edge fade', 0, 1, 0.02, d.fade), pr('flicker', 'Bar flicker', 0, 0.5, 0.01, d.flicker)];
    return skip ? L.filter(function (q) { return q.key !== skip; }) : L;
  }
  /* Each bar is one rect with its own vertical gradient. The gradient colours come from a glow field,
     so the bars light up where a wave passes. Bars the glow never reaches are left out. */
  function glassBars(c, mode) { return ribbedEngine(c, { mode: mode === 'waves' ? 'gwaves' : mode === 'spectrum' ? 'gspectrum' : 'grise' }); }
  /* Smooth ribbons of light: stacked opaque strokes, wide and dim at the bottom of the stack, narrow and bright on top.
     Colours are mixed with the background up front, so the look survives EPS (which has no transparency). */
  function glassRibbon(c) {
    var W = c.W, H = c.H, p = c.p, col = c.col, rnd = c.rnd, r, k, s;
    var nR = Math.round(p.ribbons), L = Math.round(p.layers), N = 56, items = [], seq = 0;
    var bg = hex2rgb(col[0]), pal = [1, 2, 3, 4].map(function (q) { return hex2rgb(col[q] || col[1]); });
    for (r = 0; r < nR; r++) {
      var c0 = 0.5 + (rnd() - 0.5) * 0.4, sl = (rnd() - 0.5) * 0.6, a = p.amp * (0.7 + 0.6 * rnd()), fr = p.freq * (0.75 + 0.5 * rnd()), ph = rnd() * TAU, ph2 = rnd() * TAU, pts = [];
      for (s = 0; s <= N; s++) {
        var xn = -0.06 + 1.12 * s / N;
        pts.push([xn * W, H * (c0 + sl * (xn - 0.5) + a * Math.sin(TAU * fr * xn + ph) + 0.35 * a * Math.sin(TAU * fr * 2.1 * xn + ph2))]);
      }
      var d = smoothPath(pts, false), color = pal[r % 4];
      for (k = L; k >= 1; k--) items.push({ t: k / L, d: d, color: color, i: seq++ });
    }
    items.sort(function (A, B) { return B.t - A.t || A.i - B.i; });
    var out = items.map(function (it) {
      var t = it.t, g = Math.exp(-Math.pow(t * 2.2, 2)), wh = p.core * Math.exp(-Math.pow(t * 5, 2)) * 0.9;
      var fin = mixc(mixc(bg, it.color, g), [255, 255, 255], wh);
      return '<path d="' + it.d + '" stroke="' + hx(fin) + '" stroke-width="' + f(p.width * H * t) + '"/>';
    });
    var body = '<g id="Ribbons" fill="none" stroke-linecap="round" stroke-linejoin="round">' + out.join('') + '</g>';
    if (p.gap > 0.01) {
      var bn = Math.round(p.bars), pitch = W / bn, gw = pitch * p.gap, dd = '';
      for (var b = 0; b <= bn; b++) dd += 'M' + f(b * pitch - gw / 2) + ' 0h' + f(gw) + 'v' + H + 'h' + f(-gw) + 'Z';
      body += '<path id="Gaps" fill="' + col[0] + '" d="' + dd + '"/>';
    }
    return { body: body, defs: '', meta: nR + ' glowing ribbons, ' + L + ' layers each' + (p.gap > 0.01 ? ', cut into bars' : '') };
  }
  function ribbonParams(gap) {
    return [pr('ribbons', 'Ribbons', 1, 4, 1, 2), pr('layers', 'Glow layers', 14, 60, 1, 34), pr('width', 'Ribbon width', 0.05, 0.5, 0.01, 0.24),
      pr('amp', 'Wave height', 0.03, 0.4, 0.01, 0.17), pr('freq', 'Wave count', 0.4, 3, 0.05, 0.9), pr('core', 'Bright core', 0, 1, 0.02, 0.55),
      pr('bars', 'Bars', 30, 280, 1, 150), pr('gap', 'Bar gap', 0, 0.9, 0.02, gap)];
  }
  var GLOW_ROLES = ['Background', 'Glow 1', 'Glow 2', 'Glow 3', 'Glow 4'];
  def('glasswaves', 'Glass Waves', 'Glow', 1, GLOW_ROLES, glassParams({ bars: 150, duty: 0.55, waves: 2, amp: 0.17, freq: 1, glow: 0.17, spread: 0.6, core: 0.45, fade: 0.35, flicker: 0.12 }),
    function (c) { return glassBars(c, 'waves'); }, ['#05070f', '#2f6bff', '#ff4d6d', '#9b5cff', '#22e6d0'], true);
  def('glassspectrum', 'Spectrum Bars', 'Glow', 1, GLOW_ROLES, glassParams({ bars: 130, duty: 0.6, waves: 1, amp: 0.2, freq: 1.2, glow: 0.3, spread: 0.55, core: 0.3, fade: 0.2, flicker: 0.1 }),
    function (c) { return glassBars(c, 'spectrum'); }, ['#04060b', '#00e0b8', '#3a5bff', '#a23dff', '#ff8a1f'], true);
  def('glassrise', 'Rising Glow Bars', 'Glow', 1, GLOW_ROLES, glassParams({ bars: 120, duty: 0.5, waves: 1, amp: 0.12, freq: 0.9, glow: 0.22, spread: 0.7, core: 0.2, fade: 0.25, flicker: 0.15 }, 'waves'),
    function (c) { return glassBars(c, 'rise'); }, ['#07040f', '#8a3dff', '#4a6bff', '#ff3dd0', '#00d0ff'], true);
  def('glassribbon', 'Glow Ribbon', 'Glow', 1, GLOW_ROLES, ribbonParams(0), glassRibbon, ['#04060d', '#2b6bff', '#ff4d5e', '#ffb03d', '#22e6d0'], true);
  def('glassribbonbars', 'Ribbon Bars', 'Glow', 1, GLOW_ROLES, ribbonParams(0.4), glassRibbon, ['#05060c', '#ff5a1f', '#3a6bff', '#d1203a', '#7a5cff'], true);


  /* ---------- Fluted-glass family: soft colour blobs seen through reeded (ribbed) glass ---------- */
  function flutedParams(d) {
    return [pr('bars', 'Glass ribs', 40, 300, 1, d.bars), pr('duty', 'Rib width', 0.25, 0.95, 0.01, d.duty),
      pr('blobs', 'Colour blobs', 1, 8, 1, d.blobs), pr('blobsz', 'Blob size', 0.08, 0.7, 0.01, d.size),
      pr('stretch', 'Blob height', 0.5, 3, 0.05, d.stretch), pr('tilt', 'Blob tilt', -70, 70, 1, d.tilt),
      pr('scatter', 'Scatter', 0, 1, 0.02, d.scatter), pr('refr', 'Glass bend', 0, 1, 0.02, d.refr),
      pr('punch', 'Colour strength', 0.4, 3, 0.05, d.punch), pr('core', 'Bright core', 0, 1, 0.02, d.core),
      pr('flicker', 'Rib flicker', 0, 0.5, 0.01, d.flicker)];
  }
  function flutedGlass(c) { return ribbedEngine(c, { mode: 'blobs' }); }
  def('flutedtrio', 'Fluted Trio', 'Fluted', 1, GLOW_ROLES, flutedParams({ bars: 150, duty: 0.55, blobs: 3, size: 0.2, stretch: 1.5, tilt: 25, scatter: 0.1, refr: 0.5, punch: 1.2, core: 0.25, flicker: 0.12 }),
    flutedGlass, ['#020203', '#f0a020', '#2a7bd8', '#e8284a', '#9b5cff'], true);
  def('flutedfire', 'Fluted Fire', 'Fluted', 1, GLOW_ROLES, flutedParams({ bars: 170, duty: 0.6, blobs: 5, size: 0.2, stretch: 1.5, tilt: -20, scatter: 0.8, refr: 0.7, punch: 1.3, core: 0.35, flicker: 0.15 }),
    flutedGlass, ['#0a0304', '#ff6a1f', '#ffb52e', '#d1182e', '#ff4d7a'], true);
  def('flutedaura', 'Fluted Aurora', 'Fluted', 1, GLOW_ROLES, flutedParams({ bars: 140, duty: 0.55, blobs: 4, size: 0.16, stretch: 0.5, tilt: 0, scatter: 0.2, refr: 0.4, punch: 1.4, core: 0.4, flicker: 0.1 }),
    flutedGlass, ['#030208', '#8a3dff', '#d63dff', '#3d5bff', '#ff3dbb'], true);
  def('flutedlight', 'Fluted Light', 'Fluted', 1, GLOW_ROLES, flutedParams({ bars: 160, duty: 0.55, blobs: 5, size: 0.21, stretch: 1.3, tilt: 15, scatter: 0.7, refr: 0.7, punch: 1.3, core: 0, flicker: 0.15 }),
    flutedGlass, ['#c4c4c6', '#ff5a1f', '#ffb347', '#e8203a', '#2a2020'], 'light');
  def('flutedsoft', 'Fluted Pastel', 'Fluted', 1, GLOW_ROLES, flutedParams({ bars: 130, duty: 0.6, blobs: 4, size: 0.34, stretch: 1.0, tilt: 0, scatter: 0.6, refr: 0.5, punch: 1.1, core: 0, flicker: 0.08 }),
    flutedGlass, ['#e9eef6', '#7ab0ff', '#ffa6c9', '#a98bff', '#7fe3d0'], 'light');


  /* ---------- Splash family: flat-colour paint splatters, big splats, brush strokes and splash panels ---------- */
  var SPLASH_ROLES = ['Background', 'Splash 1', 'Splash 2', 'Splash 3', 'Splash 4', 'Splash 5'];
  function splBlob(cx, cy, r, rnd, rough, spiky) {
    var splat = rnd() < spiky, n = splat ? 26 + Math.floor(rnd() * 18) : 9 + Math.floor(rnd() * 7), pts = [], k, a0 = rnd() * TAU, sq = 0.75 + 0.5 * rnd();
    for (k = 0; k < n; k++) {
      var a = a0 + TAU * (k + (rnd() - 0.5) * 0.6) / n, rr;
      if (splat) { rr = (k % 2 ? 0.42 + 0.3 * rnd() : 0.8 + 0.5 * rnd()); if (rnd() < 0.2) rr *= 1.6 + 1.7 * rnd(); }
      else rr = 1 + (rnd() - 0.5) * 2 * rough * 0.5;
      pts.push([cx + Math.cos(a) * r * rr, cy + Math.sin(a) * r * rr * sq]);
    }
    return splat ? polyPath(pts, true) : smoothPath(pts, true);
  }
  function splStreak(x, y, ang, L, w) {
    var ex = x + Math.cos(ang) * L, ey = y + Math.sin(ang) * L, nx = -Math.sin(ang) * w, ny = Math.cos(ang) * w, mx = (x + ex) / 2, my = (y + ey) / 2;
    return 'M' + f(x) + ' ' + f(y) + 'Q' + f(mx + nx) + ' ' + f(my + ny) + ' ' + f(ex) + ' ' + f(ey) + 'Q' + f(mx - nx) + ' ' + f(my - ny) + ' ' + f(x) + ' ' + f(y) + 'Z';
  }
  function splPick(col, rnd, avoid, last) {
    var k, g = 0;
    do { k = 1 + Math.floor(rnd() * (col.length - 1)); g++; } while (g < 12 && (col[k] === avoid || k === last));
    return k;
  }
  function splFill(b, n, o, col, rnd, avoid) {
    var out = [], items = [], k, last = 0, w = b.x1 - b.x0, h = b.y1 - b.y0, base = Math.min(w, h) * o.size;
    for (k = 0; k < n; k++) items.push(base * (0.22 + 1.7 * Math.pow(rnd(), o.mix)));
    items.sort(function (a, c) { return c - a; });
    items.forEach(function (r) {
      var ci = splPick(col, rnd, avoid, last); last = ci;
      out.push('<path fill="' + col[ci] + '" d="' + splBlob(b.x0 + rnd() * w * 1.1 - w * 0.05, b.y0 + rnd() * h * 1.1 - h * 0.05, r, rnd, o.rough, o.spiky) + '"/>');
    });
    for (k = 0; k < o.streaks; k++) {
      var ci2 = splPick(col, rnd, avoid, -1);
      out.push('<path fill="' + col[ci2] + '" d="' + splStreak(b.x0 + rnd() * w, b.y0 + rnd() * h, rnd() * TAU, base * (0.8 + 2.2 * rnd()), base * (0.05 + 0.12 * rnd())) + '"/>');
    }
    for (k = 0; k < o.drops; k++) {
      var ci3 = splPick(col, rnd, avoid, -1);
      out.push('<circle fill="' + col[ci3] + '" cx="' + f(b.x0 + rnd() * w) + '" cy="' + f(b.y0 + rnd() * h) + '" r="' + f(base * (0.03 + 0.1 * Math.pow(rnd(), 2))) + '"/>');
    }
    return out;
  }
  var SPL_COMMON = function (d) {
    return [pr('size', 'Splash size', 0.05, 0.45, 0.01, d.size), pr('mix', 'Size mix', 0.4, 3, 0.05, d.mix), pr('spiky', 'Spiky edges', 0, 1, 0.02, d.spiky),
      pr('rough', 'Blob roughness', 0, 1, 0.02, d.rough), pr('streaks', 'Streaks', 0, 50, 1, d.streaks), pr('drops', 'Drops', 0, 140, 1, d.drops)];
  };
  def('splashpaint', 'Paint Splash', 'Splash', 3, SPLASH_ROLES, [pr('shapes', 'Splashes', 6, 120, 1, 64)].concat(SPL_COMMON({ size: 0.2, mix: 1.6, spiky: 0.45, rough: 0.6, streaks: 10, drops: 40 })),
    function (c) {
      var o = { size: c.p.size, mix: c.p.mix, spiky: c.p.spiky, rough: c.p.rough, streaks: Math.round(c.p.streaks), drops: Math.round(c.p.drops) };
      var parts = splFill({ x0: 0, y0: 0, x1: c.W, y1: c.H }, Math.round(c.p.shapes), o, c.col, c.rnd, c.col[0]);
      return { body: '<g id="Splash">' + parts.join('') + '</g>', defs: '', meta: parts.length + ' flat splash shapes' };
    }, ['#ffffff', '#e8143c', '#0a3dff', '#ffd800', '#00c8e8', '#18b04a'], 'vivid');
  def('splashpanels', 'Splash Panels', 'Splash', 3, SPLASH_ROLES, [pr('panels', 'Panels', 1, 6, 1, 3), pr('gap', 'Gap between', 0, 0.08, 0.002, 0.03), pr('shapes', 'Splashes per panel', 4, 70, 1, 28)].concat(SPL_COMMON({ size: 0.2, mix: 1.5, spiky: 0.5, rough: 0.6, streaks: 6, drops: 22 })),
    function (c) {
      var W = c.W, H = c.H, p = c.p, rnd = c.rnd, np = Math.round(p.panels), gw = W * p.gap, pw = (W - gw * (np - 1)) / np, defs = '', out = [], k, last = 0;
      var o = { size: p.size, mix: p.mix, spiky: p.spiky, rough: p.rough, streaks: Math.round(p.streaks), drops: Math.round(p.drops) };
      for (k = 0; k < np; k++) {
        var x0 = k * (pw + gw), ci = splPick(c.col, rnd, c.col[0], last); last = ci;
        var inner = splFill({ x0: x0, y0: 0, x1: x0 + pw, y1: H }, Math.round(p.shapes), o, c.col, rnd, c.col[ci]);
        defs += '<clipPath id="spp' + k + '"><rect x="' + f(x0) + '" y="0" width="' + f(pw) + '" height="' + H + '"/></clipPath>';
        out.push('<g clip-path="url(#spp' + k + ')"><rect fill="' + c.col[ci] + '" x="' + f(x0) + '" y="0" width="' + f(pw) + '" height="' + H + '"/>' + inner.join('') + '</g>');
      }
      return { body: '<g id="Panels">' + out.join('') + '</g>', defs: defs, meta: np + ' splash panels' };
    }, ['#ffffff', '#e8143c', '#0a3dff', '#ffd800', '#00c8e8', '#18b04a'], 'vivid');
  def('splashsplatter', 'Big Splats', 'Splash', 3, SPLASH_ROLES, [pr('splats', 'Splats', 1, 6, 1, 3), pr('size', 'Splat size', 0.12, 0.55, 0.01, 0.27), pr('layers', 'Colour layers', 1, 5, 1, 3),
    pr('tendrils', 'Tendrils', 0, 50, 1, 22), pr('drops', 'Drops', 0, 160, 1, 60), pr('spiky', 'Spiky edges', 0, 1, 0.02, 0.85)],
    function (c) {
      var W = c.W, H = c.H, p = c.p, rnd = c.rnd, col = c.col, out = [], s, l, k, ns = Math.round(p.splats), last = 0;
      for (s = 0; s < ns; s++) {
        var cx = W * (0.12 + 0.76 * (s + rnd() * 0.7) / ns), cy = H * (0.25 + 0.5 * rnd()), R = H * p.size * (0.75 + 0.5 * rnd());
        var ci = splPick(col, rnd, col[0], last); last = ci;
        for (k = 0; k < Math.round(p.tendrils); k++) {
          var a = rnd() * TAU, d0 = R * 0.5;
          out.push('<path fill="' + col[ci] + '" d="' + splStreak(cx + Math.cos(a) * d0, cy + Math.sin(a) * d0, a, R * (0.8 + 1.9 * rnd()), R * (0.03 + 0.07 * rnd())) + '"/>');
        }
        for (l = 0; l < Math.round(p.layers); l++) {
          if (l) ci = splPick(col, rnd, col[0], ci);
          out.push('<path fill="' + col[ci] + '" d="' + splBlob(cx + (rnd() - 0.5) * R * 0.2, cy + (rnd() - 0.5) * R * 0.2, R * (1 - 0.23 * l), rnd, 0.6, p.spiky) + '"/>');
        }
        for (k = 0; k < Math.round(p.drops) / ns; k++) {
          var a2 = rnd() * TAU, dd = R * (1.25 + 2.2 * Math.pow(rnd(), 1.3));
          out.push('<circle fill="' + col[splPick(col, rnd, col[0], -1)] + '" cx="' + f(cx + Math.cos(a2) * dd) + '" cy="' + f(cy + Math.sin(a2) * dd) + '" r="' + f(R * (0.02 + 0.07 * Math.pow(rnd(), 2))) + '"/>');
        }
      }
      return { body: '<g id="Splats">' + out.join('') + '</g>', defs: '', meta: ns + ' big splats with tendrils and drops' };
    }, ['#101018', '#ff2d55', '#00e5ff', '#ffe600', '#7a3dff', '#43e06a'], 'vivid');
  def('splashbrush', 'Paint Strokes', 'Splash', 3, SPLASH_ROLES, [pr('strokes', 'Strokes', 4, 40, 1, 16), pr('length', 'Stroke length', 0.15, 1.3, 0.01, 0.5), pr('width', 'Stroke width', 0.04, 0.35, 0.01, 0.13),
    pr('curl', 'Curl', 0, 1, 0.02, 0.5), pr('rough', 'Rough edge', 0, 1, 0.02, 0.45), pr('drops', 'Flecks', 0, 120, 1, 24)],
    function (c) {
      var W = c.W, H = c.H, p = c.p, rnd = c.rnd, col = c.col, out = [], s, k, N = 20, last = 0;
      for (s = 0; s < Math.round(p.strokes); s++) {
        var x = rnd() * W, y = rnd() * H, a = rnd() * TAU, turn = (rnd() - 0.5) * p.curl * 0.5, L = [], R = [], L0 = W * p.length * (0.5 + rnd()) / N, wd = H * p.width * (0.6 + 0.8 * rnd());
        for (k = 0; k <= N; k++) {
          var t = k / N, w = wd * (0.18 + 0.82 * Math.pow(Math.sin(Math.PI * Math.min(0.98, t + 0.02)), 0.7)) * (1 + p.rough * (rnd() - 0.5) * 0.7);
          L.push([x - Math.sin(a) * w / 2, y + Math.cos(a) * w / 2]); R.push([x + Math.sin(a) * w / 2, y - Math.cos(a) * w / 2]);
          turn += (rnd() - 0.5) * p.curl * 0.12; a += turn * 0.5; x += Math.cos(a) * L0; y += Math.sin(a) * L0;
        }
        var ci = splPick(col, rnd, col[0], last); last = ci;
        out.push('<path fill="' + col[ci] + '" d="' + smoothPath(L.concat(R.reverse()), true) + '"/>');
      }
      for (k = 0; k < Math.round(p.drops); k++) out.push('<circle fill="' + col[splPick(col, rnd, col[0], -1)] + '" cx="' + f(rnd() * W) + '" cy="' + f(rnd() * H) + '" r="' + f(H * (0.004 + 0.02 * Math.pow(rnd(), 2))) + '"/>');
      return { body: '<g id="Strokes">' + out.join('') + '</g>', defs: '', meta: Math.round(p.strokes) + ' paint strokes' };
    }, ['#fff4fa', '#ff3d9a', '#7a5cff', '#00d0ff', '#ffd23d', '#3dff9a'], 'vivid');


  /* ---------- Gallery families: Waves, Poster, Swirl, Wash, Crystal, Halftone, Smoke (6 patterns each) ---------- */
  function regSet(name, arr, shifts) {
    var lib = [];
    shifts.forEach(function (sh, si) {
      arr.forEach(function (p) {
        lib.push({ name: p.name + (si ? ' ' + 'I'.repeat(Math.min(si + 1, 4)) : ''), c: sh ? p.c.map(function (x, q) { return q === 0 ? x : hueShift(x, sh); }) : p.c.slice() });
      });
    });
    PSETS[name] = { base: arr, lib: lib };
  }
  var SH6 = [0, 60, 120, 180, 240, 300];
  regSet('earth', [
    { name: 'Terracotta', c: ['#fff7e6', '#e05a5a', '#ffa530', '#ffb84d', '#34496e', '#4d6a91'] },
    { name: 'Sage Clay', c: ['#cfded3', '#d9683a', '#f0a58a', '#5f8f8a', '#3f566b', '#f4d6c8'] },
    { name: 'Blush', c: ['#fbe3dc', '#d4663a', '#ee9f88', '#c57b6b', '#f6c9bd', '#a6452c'] },
    { name: 'Teal Sun', c: ['#e8f3f0', '#2f6f73', '#f0b35a', '#d9613c', '#1f3e4f', '#f7d9a8'] },
    { name: 'Rose Dusk', c: ['#f9ece7', '#b5465a', '#e8909a', '#6a3d5c', '#f1c0a8', '#d97b4d'] },
    { name: 'Olive', c: ['#f2efe0', '#7a8c4a', '#d9a441', '#b5523b', '#3d4f3a', '#e6c88b'] },
    { name: 'Ocean Sand', c: ['#fbf4e4', '#2d6a8f', '#6db5c9', '#f0c27a', '#e07a4f', '#1b3a57'] },
    { name: 'Plum', c: ['#f6ecf2', '#6b2d5c', '#c45b8a', '#f2a07b', '#3b1f4d', '#f7cfc0'] }
  ], SH6);
  regSet('flow', [
    { name: 'Reef', c: ['#f4f6e4', '#f6f8ea', '#a8dbe3', '#4f9db5', '#ff6b8a', '#ffc45e'] },
    { name: 'Dawn', c: ['#fff4e6', '#fdf0d5', '#f6c7a8', '#f08a8a', '#b05c9a', '#5a4a8a'] },
    { name: 'Lagoon', c: ['#eaf7f4', '#e2f4ee', '#9fdccf', '#3fa7b0', '#3a6fa8', '#2b3f7a'] },
    { name: 'Citrus', c: ['#fffbe6', '#fff3b0', '#ffd35a', '#ff9a3d', '#ff5a4a', '#c92a5a'] },
    { name: 'Lilac', c: ['#f4effc', '#ede6fb', '#cdb9f5', '#9a86e8', '#e07ab8', '#ff9a8a'] },
    { name: 'Moss', c: ['#f3f4e6', '#e6ead0', '#b9d09a', '#6fa86f', '#2f7a6a', '#1f4a5a'] }
  ], SH6);
  regSet('swirl', [
    { name: 'Canyon', c: ['#1a1a2e', '#2a4fd0', '#5cc8f0', '#ffe55a', '#ff7a1f', '#c42a1a'] },
    { name: 'Sky Sand', c: ['#fff3e0', '#8fd0ee', '#c9b8f0', '#ffb347', '#ff7a2f', '#7a2a1a'] },
    { name: 'Lava Ocean', c: ['#14101a', '#0a3dff', '#00c2ff', '#ffd400', '#ff5a00', '#a0101a'] },
    { name: 'Candy Silk', c: ['#fff0f6', '#ff6fae', '#a98bff', '#4fc3ff', '#ffe27a', '#ff8a5a'] },
    { name: 'Forest', c: ['#0c1a14', '#12604a', '#4fbf8a', '#e8e06a', '#f0903a', '#8a3a1a'] },
    { name: 'Mono Blue', c: ['#08142a', '#123f8a', '#2f7be0', '#7fc4ff', '#d0ecff', '#ffffff'] },
    { name: 'Rose Gold', c: ['#201016', '#6a1f3a', '#d4527a', '#f4a08a', '#ffd8a8', '#fff2dc'] },
    { name: 'Aurora', c: ['#07101c', '#1fd0a0', '#2f8bff', '#8a5cff', '#ff5cc0', '#ffe27a'] }
  ], SH6);
  regSet('wash', [
    { name: 'Sunburst', c: ['#fff6df', '#ffe27a', '#ffa13d', '#ff5a3d', '#d6247a', '#2f7be0'] },
    { name: 'Ocean', c: ['#eaf6ff', '#bfe8ff', '#4fb0ff', '#1f6be0', '#1fc9b0', '#6a3de0'] },
    { name: 'Berry', c: ['#fff0f4', '#ffc0d0', '#ff6a9a', '#c42a7a', '#7a2ab0', '#2f4fe0'] },
    { name: 'Pastel', c: ['#fdf7f0', '#ffd9c0', '#ffb0c8', '#c8b0ff', '#a0d8ff', '#a8f0d0'] },
    { name: 'Galaxy', c: ['#0a0816', '#2f3be0', '#8a2ae0', '#e02a9a', '#ff7a4a', '#ffd86a'] },
    { name: 'Jungle', c: ['#f2f8e8', '#e8f060', '#7ad060', '#1fa080', '#1f6ac0', '#6a2ab0'] },
    { name: 'Flame', c: ['#fff3e0', '#ffd45a', '#ff8a2a', '#e8402a', '#a0204a', '#401a60'] }
  ], SH6);
  regSet('candy', [
    { name: 'Candy Gem', c: ['#efeff1', '#2fb5c8', '#ff3d8a', '#ffa23d', '#5a7be0', '#9a4fd0'] },
    { name: 'Pop Gem', c: ['#f4f4f6', '#00b8d4', '#ff4d94', '#ff9a3d', '#b04fe0', '#ffd23d'] },
    { name: 'Ice Gem', c: ['#eef3f8', '#4fc3e8', '#2f7be0', '#a8e8f8', '#7a5cff', '#ffffff'] },
    { name: 'Fire Gem', c: ['#f6f2ee', '#ff5a2f', '#ffb03d', '#e0204a', '#ff7a9a', '#ffe27a'] },
    { name: 'Mint Gem', c: ['#eef6f2', '#1fc9a0', '#4fa8f0', '#a8f0d0', '#ffd86a', '#ff7a9a'] },
    { name: 'Violet Gem', c: ['#f2eefa', '#7a3de0', '#e04fb8', '#4f9bf0', '#ffa0d8', '#b8a0ff'] },
    { name: 'Neon Dark', c: ['#0b0b14', '#00e5ff', '#ff2d95', '#ffe600', '#7a3dff', '#43e06a'] }
  ], SH6);
  regSet('halftone', [
    { name: 'Sunrise', c: ['#bdbdc2', '#ff2d8a', '#ff5a5a', '#ff8a3d', '#ffc23d', '#ffe66a'] },
    { name: 'Violet Sea', c: ['#bdbdc2', '#c43de0', '#7a4fe8', '#3f8be8', '#2fc8e8', '#2ff0d8'] },
    { name: 'Peach Fuzz', c: ['#c8c8cc', '#ff8a6a', '#ffb04a', '#ffd04a', '#ff6aa0', '#ffe08a'] },
    { name: 'Aqua Pop', c: ['#c0c4c8', '#2f7be0', '#2fc8e8', '#6affe0', '#8af0ff', '#d0fff8'] },
    { name: 'Grape Soda', c: ['#c4c0c8', '#e02a8a', '#a03de0', '#5a4fe8', '#2f8bf0', '#4fd0ff'] },
    { name: 'Lime Fire', c: ['#c4c4c0', '#ff4a2a', '#ff9a2a', '#ffe02a', '#b8e82a', '#4fe86a'] }
  ], SH6);
  regSet('smoke', [
    { name: 'Flame Smoke', c: ['#020204', '#3a6bff', '#8a3dff', '#e0309a', '#ff5a2a', '#ffc04a'] },
    { name: 'Ice Smoke', c: ['#02040a', '#1f3bff', '#2f8bff', '#4fd0ff', '#a0f0ff', '#ffffff'] },
    { name: 'Toxic', c: ['#020402', '#0a6a2a', '#2fd060', '#a0ff3d', '#e8ff6a', '#ffffff'] },
    { name: 'Violet Smoke', c: ['#050208', '#3a1a8a', '#7a3de0', '#c04fe8', '#ff7ac8', '#ffd0f0'] },
    { name: 'Ember', c: ['#050202', '#6a1010', '#c42a1a', '#ff5a1f', '#ffa030', '#ffe27a'] },
    { name: 'Cyan Magenta', c: ['#020208', '#00c8ff', '#4f7bff', '#9a4fff', '#ff3da8', '#ff8a6a'] }
  ], SH6);

  var FAM_ROLES = ['Background', 'Colour 1', 'Colour 2', 'Colour 3', 'Colour 4', 'Colour 5'];
  function rampN(pal, t) { var n = pal.length - 1, q = clamp01(t) * n, k = Math.min(n - 1, Math.floor(q)); return mixc(pal[k], pal[k + 1], q - k); }
  function palRGB(col) { var o = []; for (var k = 1; k < col.length; k++) if (col[k]) o.push(hex2rgb(col[k])); return o.length ? o : [[128, 128, 128]]; }
  function fshade(c, k) { return k >= 0 ? mixc(c, [255, 255, 255], k) : mixc(c, [0, 0, 0], -k); }
  function ff1(v) { return String(Math.round(v * 10) / 10); }
  function mkFam(cat, pset, tpl, render, presets) {
    presets.forEach(function (P) {
      var ps = tpl.map(function (a) {
        var dv = P.p && P.p[a[0]] !== undefined ? P.p[a[0]] : a[a.length - 1];
        return a.length === 3 ? tg(a[0], a[1], dv) : pr(a[0], a[1], a[2], a[3], a[4], dv);
      });
      var ps2 = P.set || pset;
      def(P.id, P.name, cat, 1, FAM_ROLES, ps, function (c) { return render(c, P.m || {}); }, PSETS[ps2].base[P.pi || 0].c.slice(), ps2);
    });
  }

  /* --- Waves: layered paper-cut flowing sheets, optionally rotated, in groups --- */
  function wavesGroup(c, o, rnd, pal) {
    var W = c.W, H = c.H, Lc = Math.hypot(W, H), out = '', g, k, i, M = 34;
    for (g = 0; g < o.groups; g++) {
      var a = (o.angle + 180 * g + (g > 1 ? 90 : 0)) * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a);
      var hv = (W * Math.abs(sa) + H * Math.abs(ca)) / 2, ph1 = rnd() * TAU, ph2 = rnd() * TAU, drift = 0.25 + 0.5 * rnd(), tilt = (rnd() - 0.5) * 0.35 * Lc;
      var A = o.amp * hv * 1.6, off = Math.floor(rnd() * pal.length);
      var tx = function (u, v) { return [W / 2 + u * ca - v * sa, H / 2 + u * sa + v * ca]; };
      for (k = 0; k < o.sheets; k++) {
        var d = o.cover * (1 - o.spread * k / o.sheets), base = hv - 2 * hv * d + (rnd() - 0.5) * 0.04 * hv;
        var col = o.ramp ? rampN(pal, o.sheets > 1 ? k / (o.sheets - 1) : 0) : pal[(k + off) % pal.length];
        var mkPath = function (bo) {
          var pts = [], s;
          for (i = 0; i <= M; i++) {
            var u = -Lc / 2 + Lc * i / M; s = u / Lc;
            var v = base + bo + tilt * s + A * (Math.sin(TAU * o.freq * s + ph1 + k * drift) + 0.4 * Math.sin(TAU * o.freq * 2.3 * s + ph2 - k * drift * 0.7));
            pts.push(tx(u, v));
          }
          var e1 = tx(Lc / 2, hv + Lc * 0.3), e0 = tx(-Lc / 2, hv + Lc * 0.3);
          return smoothPath(pts, false) + 'L' + f(e1[0]) + ' ' + f(e1[1]) + 'L' + f(e0[0]) + ' ' + f(e0[1]) + 'Z';
        };
        if (o.tone > 0.01) out += '<path fill="' + hx(fshade(col, -0.2)) + '" d="' + mkPath(-o.tone * 0.14 * hv) + '"/>';
        out += '<path fill="' + hx(col) + '" d="' + mkPath(0) + '"/>';
      }
    }
    return out;
  }
  var WV_T = [['groups', 'Wave groups', 1, 3, 1, 1], ['sheets', 'Layers', 2, 14, 1, 5], ['angle', 'Angle', -180, 180, 1, 30], ['amp', 'Wave height', 0.01, 0.3, 0.005, 0.1],
    ['freq', 'Wave count', 0.3, 3.5, 0.05, 0.9], ['cover', 'Coverage', 0.15, 1.1, 0.01, 0.5], ['spread', 'Layer spread', 0.2, 1, 0.01, 0.8], ['tone', 'Edge shadow', 0, 0.8, 0.02, 0.3], ['ramp', 'Smooth colour ramp', 0]];
  mkFam('Waves', 'earth', WV_T, function (c) {
    var o = { groups: Math.round(c.p.groups), sheets: Math.round(c.p.sheets), angle: c.p.angle, amp: c.p.amp, freq: c.p.freq, cover: c.p.cover, spread: c.p.spread, tone: c.p.tone, ramp: c.p.ramp };
    return { body: '<g id="Waves">' + wavesGroup(c, o, c.rnd, palRGB(c.col)) + '</g>', defs: '', meta: o.groups + ' wave group(s), ' + o.sheets + ' layers each' };
  }, [
    { id: 'wvcorner', name: 'Corner Flow', pi: 0, p: { groups: 2, sheets: 4, angle: 35, amp: 0.12, freq: 0.8, cover: 0.4, spread: 0.75, tone: 0.35 } },
    { id: 'wvdiag', name: 'Diagonal Flow', set: 'flow', pi: 0, p: { groups: 1, sheets: 8, angle: 28, amp: 0.06, freq: 1.1, cover: 1.05, spread: 1, tone: 0.2, ramp: 1 }, m: {} },
    { id: 'wvdunes', name: 'Layered Dunes', pi: 6, p: { groups: 1, sheets: 6, angle: 0, amp: 0.08, freq: 1.2, cover: 0.75, spread: 0.85, tone: 0.3 } },
    { id: 'wvtwin', name: 'Twin Ribbons', pi: 3, p: { groups: 2, sheets: 3, angle: 0, amp: 0.1, freq: 0.7, cover: 0.34, spread: 0.7, tone: 0.3 } },
    { id: 'wvsunset', name: 'Sunset Ripples', set: 'flow', pi: 3, p: { groups: 1, sheets: 11, angle: 0, amp: 0.03, freq: 2.2, cover: 1.05, spread: 1, tone: 0.15, ramp: 1 } },
    { id: 'wvside', name: 'Side Sweep', pi: 1, p: { groups: 1, sheets: 5, angle: 90, amp: 0.14, freq: 0.8, cover: 0.5, spread: 0.8, tone: 0.3 } }
  ]);

  /* --- Poster: muted organic compositions (waves, circles, dot clusters, thin lines) --- */
  var PO_T = [['groups', 'Wave groups', 0, 3, 1, 1], ['sheets', 'Layers', 1, 6, 1, 3], ['angle', 'Angle', -180, 180, 1, 20], ['amp', 'Wave height', 0.01, 0.3, 0.005, 0.08],
    ['freq', 'Wave count', 0.3, 3, 0.05, 0.8], ['cover', 'Coverage', 0.15, 1, 0.01, 0.32], ['circles', 'Circles', 0, 10, 1, 3], ['half', 'Big circles', 0, 4, 1, 1], ['dots', 'Dot cluster', 1], ['line', 'Thin line', 1]];
  mkFam('Poster', 'earth', PO_T, function (c) {
    var W = c.W, H = c.H, p = c.p, rnd = c.rnd, pal = palRGB(c.col), bg = hex2rgb(c.col[0]), out = '', k, i, j;
    var pk = function () { return pal[Math.floor(rnd() * pal.length)]; };
    if (p.groups > 0) out += wavesGroup(c, { groups: Math.round(p.groups), sheets: Math.round(p.sheets), angle: p.angle, amp: p.amp, freq: p.freq, cover: p.cover, spread: 0.75, tone: 0.25, ramp: 0 }, rnd, pal);
    for (k = 0; k < Math.round(p.half); k++) {
      var r = H * (0.18 + 0.22 * rnd()), cx = rnd() < 0.5 ? W * 0.02 * rnd() : W * (1 - 0.02 * rnd()), cy = H * rnd();
      out += '<circle cx="' + f(cx) + '" cy="' + f(cy) + '" r="' + f(r) + '" fill="' + hx(pk()) + '"/>';
    }
    for (k = 0; k < Math.round(p.circles); k++) {
      var rr = H * (0.04 + 0.12 * rnd()), cc = mixc(pk(), bg, 0.12 * rnd());
      out += '<circle cx="' + f(W * rnd()) + '" cy="' + f(H * rnd()) + '" r="' + f(rr) + '" fill="' + hx(cc) + '"/>';
    }
    if (p.dots) {
      var sp = H * 0.026, nx = 7, ny = 6, x0 = rnd() < 0.5 ? W * 0.03 : W * 0.97 - nx * sp, y0 = rnd() < 0.5 ? H * 0.04 : H * 0.96 - ny * sp, dd = '', rd = sp * 0.17;
      for (i = 0; i < nx; i++) for (j = 0; j < ny; j++) { var dx = x0 + i * sp + (j % 2) * sp / 2, dy = y0 + j * sp; dd += 'M' + f(dx - rd) + ' ' + f(dy) + 'a' + f(rd) + ' ' + f(rd) + ' 0 1 0 ' + f(2 * rd) + ' 0a' + f(rd) + ' ' + f(rd) + ' 0 1 0 ' + f(-2 * rd) + ' 0Z'; }
      out += '<path fill="' + hx(fshade(pk(), 0.55)) + '" d="' + dd + '"/>';
    }
    if (p.line) {
      var lp = []; for (i = 0; i < 6; i++) lp.push([W * (i / 5), H * (0.2 + 0.6 * rnd())]);
      out += '<path fill="none" stroke="' + hx(fshade(pk(), 0.6)) + '" stroke-width="' + f(Math.max(1.2, H * 0.0028)) + '" d="' + smoothPath(lp, false) + '"/>';
    }
    return { body: '<g id="Poster">' + out + '</g>', defs: '', meta: 'organic poster: ' + Math.round(p.groups) + ' wave group(s), ' + Math.round(p.circles) + ' circles' };
  }, [
    { id: 'poquiet', name: 'Quiet Waves', pi: 1, p: { groups: 1, sheets: 3, angle: 12, amp: 0.07, circles: 2, half: 1 } },
    { id: 'pogarden', name: 'Circle Garden', pi: 2, p: { groups: 0, sheets: 2, circles: 8, half: 3, dots: 1, line: 1 } },
    { id: 'podunes', name: 'Dotted Dunes', pi: 3, p: { groups: 2, sheets: 3, angle: 0, amp: 0.1, cover: 0.3, circles: 2, half: 0, dots: 1 } },
    { id: 'poarch', name: 'Arch Layers', pi: 0, p: { groups: 1, sheets: 5, angle: 90, amp: 0.12, cover: 0.4, circles: 1, half: 2, line: 0 } },
    { id: 'pobold', name: 'Bold Blobs', pi: 4, p: { groups: 2, sheets: 2, angle: 40, amp: 0.15, cover: 0.45, circles: 3, half: 2, dots: 0 } },
    { id: 'poline', name: 'Line Flow', pi: 5, p: { groups: 1, sheets: 4, angle: -20, amp: 0.1, cover: 0.38, circles: 4, half: 1, dots: 1, line: 1 } }
  ]);

  /* --- Swirl: streamlines of a smooth flow field, coloured by the field value (oil / silk look) --- */
  var SW_T = [['waves', 'Flow waves', 2, 7, 1, 4], ['scale', 'Scale', 0.3, 2.5, 0.05, 1], ['curves', 'Lines', 150, 1200, 10, 520], ['steps', 'Line length', 10, 40, 1, 20],
    ['width', 'Line width', 0.5, 3, 0.1, 1.3], ['contrast', 'Shade variety', 0, 1, 0.02, 0.5], ['jitter', 'Colour mixing', 0, 0.3, 0.01, 0.05]];
  mkFam('Swirl', 'swirl', SW_T, function (c) {
    var W = c.W, H = c.H, p = c.p, rnd = c.rnd, asp = W / H, pal = palRGB(c.col), K = Math.round(p.waves), T = [], k, i, s;
    for (k = 0; k < K; k++) {
      var ang = rnd() * TAU, mag = p.scale * (0.5 + 1.0 * rnd());
      T.push({ kx: Math.cos(ang) * mag * TAU, ky: Math.sin(ang) * mag * TAU, a: 1 / (mag * TAU), ph: rnd() * TAU });
    }
    var psi = function (x, y) { var v = 0; for (var q = 0; q < K; q++) v += T[q].a * Math.sin(T[q].kx * x + T[q].ky * y + T[q].ph); return v; };
    var grad = function (x, y) { var gx = 0, gy = 0; for (var q = 0; q < K; q++) { var cs = T[q].a * Math.cos(T[q].kx * x + T[q].ky * y + T[q].ph); gx += cs * T[q].kx; gy += cs * T[q].ky; } return [gx, gy]; };
    var lo = 1e9, hi = -1e9;
    for (i = 0; i < 400; i++) { var v0 = psi(rnd() * asp, rnd()); if (v0 < lo) lo = v0; if (v0 > hi) hi = v0; }
    var span = Math.max(1e-6, hi - lo), lw = H / 1080, out1 = [], out2 = [], h = 0.012 * (1 + 0.4 * (1 / Math.max(0.5, p.scale)));
    var trace = function (x, y, dir, N, pts) {
      for (var n = 0; n < N; n++) {
        var g = grad(x, y), m = Math.hypot(g[0], g[1]);
        if (m < 1e-5) break;
        var vx = g[1] / m, vy = -g[0] / m, mx = x + dir * vx * h * 0.5, my = y + dir * vy * h * 0.5, g2 = grad(mx, my), m2 = Math.hypot(g2[0], g2[1]) || 1;
        x += dir * g2[1] / m2 * h; y += dir * -g2[0] / m2 * h;
        if (x < -0.12 || x > asp + 0.12 || y < -0.12 || y > 1.12) break;
        pts.push([x / asp * W, y * H]);
      }
    };
    var nU = Math.round(p.curves * 0.45), nT = Math.round(p.curves);
    var one = function (thick) {
      var x = -0.05 + (asp + 0.1) * rnd(), y = -0.05 + 1.1 * rnd(), t = (psi(x, y) - lo) / span + (rnd() - 0.5) * p.jitter * 2;
      var col = rampN(pal, t), pts = [], back = [];
      col = fshade(col, (rnd() - 0.5) * 0.2 * p.contrast * 2 - (thick ? 0.1 : 0));
      trace(x, y, 1, Math.round(p.steps), pts); trace(x, y, -1, Math.round(p.steps), back);
      var all = back.reverse().concat([[x / asp * W, y * H]], pts);
      if (all.length < 3) return null;
      return '<path d="M' + all.map(function (q) { return ff1(q[0]) + ' ' + ff1(q[1]); }).join('L') + '" stroke="' + hx(col) + '" stroke-width="' + f(p.width * lw * (thick ? 7 : 1)) + '"/>';
    };
    for (s = 0; s < nU; s++) { var u = one(true); if (u) out1.push(u); }
    for (s = 0; s < nT; s++) { var t2 = one(false); if (t2) out2.push(t2); }
    return { body: '<g id="Swirl" fill="none" stroke-linecap="round" stroke-linejoin="round">' + out1.join('') + out2.join('') + '</g>', defs: '', meta: (out1.length + out2.length) + ' flow lines' };
  }, [
    { id: 'swsilk', name: 'Silk Swirl', pi: 1, p: { waves: 4, scale: 1 } },
    { id: 'swcanyon', name: 'Canyon Swirl', pi: 0, p: { waves: 5, scale: 0.9, curves: 600, contrast: 0.7 } },
    { id: 'swocean', name: 'Ocean Swirl', pi: 2, p: { waves: 4, scale: 1.2, jitter: 0.03 } },
    { id: 'swwhirl', name: 'Tight Whirl', pi: 7, p: { waves: 6, scale: 2, curves: 800, width: 1, steps: 16 } },
    { id: 'swdrift', name: 'Slow Drift', pi: 3, p: { waves: 3, scale: 0.55, curves: 420, width: 1.8, steps: 28 } },
    { id: 'swmarble', name: 'Marble Flow', pi: 5, p: { waves: 5, scale: 1.4, curves: 900, width: 0.8, contrast: 0.3 } }
  ]);

  /* --- Wash: watercolour washes built from nested soft blobs (EPS-safe, no transparency), droplets and brush streaks --- */
  var WS_T = [['washes', 'Colour washes', 2, 10, 1, 7], ['size', 'Wash size', 0.1, 0.7, 0.01, 0.42], ['layers', 'Soft layers', 8, 40, 1, 30], ['bleed', 'Rough edge', 0, 1, 0.02, 0.3],
    ['drops', 'Droplets', 0, 260, 1, 110], ['dropsize', 'Droplet size', 0.2, 3, 0.05, 1], ['rings', 'Ring droplets', 0, 0.6, 0.02, 0.15], ['streaks', 'Brush streaks', 0, 14, 1, 4]];
  mkFam('Wash', 'wash', WS_T, function (c, m) {
    var W = c.W, H = c.H, p = c.p, rnd = c.rnd, pal = palRGB(c.col), bg = hex2rgb(c.col[0]), nW = Math.round(p.washes), L = Math.round(p.layers), out = [], wsh = [], k, l, i;
    var order = []; for (k = 0; k < nW; k++) order.push(k / Math.max(1, nW - 1));
    if (m.shuffle) order.sort(function () { return rnd() - 0.5; });
    for (k = 0; k < nW; k++) {
      var t = order[k], cx = W * (0.08 + 0.84 * (m.diag ? t : rnd())) , cy = H * (m.diag ? 0.15 + 0.7 * (1 - t) + (rnd() - 0.5) * 0.3 : 0.1 + 0.8 * rnd());
      var R = H * p.size * (0.7 + 0.7 * rnd()), colr = rampN(pal, t + (rnd() - 0.5) * 0.15), bgl = mixc(bg, rampN(pal, clamp01((cx / W + 1 - cy / H) / 2)), 0.42);
      wsh.push({ cx: cx, cy: cy, R: R, col: colr });
      var nb = 15, ph = [];
      for (i = 0; i < nb; i++) ph.push(rnd());
      for (l = 0; l < L; l++) {
        var fr = 0.25 + 0.85 * (1 - l / (L - 1)), cum = 1 - Math.pow(1 - 0.07, l + 1), pts = [];
        for (i = 0; i < nb; i++) { var an = i / nb * TAU, rr = R * fr * (1 + p.bleed * (ph[i] - 0.5) * 1.1 + p.bleed * 0.12 * (rnd() - 0.5)); pts.push([cx + Math.cos(an) * rr * 1.15, cy + Math.sin(an) * rr * 0.9]); }
        out.push('<path fill="' + hx(mixc(bgl, colr, Math.min(0.96, cum))) + '" d="' + smoothPath(pts, true) + '"/>');
      }
    }
    for (k = 0; k < Math.round(p.drops); k++) {
      var w = wsh[Math.floor(rnd() * wsh.length)], an2 = rnd() * TAU, dist = w.R * (0.5 + 1.1 * Math.sqrt(rnd())), r2 = Math.max(1, (1.2 + Math.pow(rnd(), 2.5) * H * 0.014) * p.dropsize * H / 1080);
      var dc = hx(mixc(bg, fshade(w.col, -0.1 + 0.25 * rnd()), 0.55 + 0.4 * rnd())), x = w.cx + Math.cos(an2) * dist, y = w.cy + Math.sin(an2) * dist * 0.9;
      if (rnd() < 0.3) { x = W * rnd(); y = H * rnd(); }
      out.push(rnd() < p.rings ? '<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(r2 * 1.8) + '" fill="none" stroke="' + dc + '" stroke-width="' + f(Math.max(1, r2 * 0.35)) + '"/>' : '<circle cx="' + f(x) + '" cy="' + f(y) + '" r="' + f(r2) + '" fill="' + dc + '"/>');
    }
    for (k = 0; k < Math.round(p.streaks); k++) {
      var sx = W * rnd(), sy = H * (0.6 + 0.4 * rnd()), sp = [], ang = -0.4 + rnd() * 0.8, sl = W * (0.15 + 0.25 * rnd());
      for (i = 0; i < 5; i++) sp.push([sx + Math.cos(ang) * sl * i / 4 + (rnd() - 0.5) * 20, sy + Math.sin(ang) * sl * i / 4 + (rnd() - 0.5) * 30]);
      var sc = mixc(bg, rampN(pal, rnd()), 0.55);
      out.push('<path fill="none" stroke="' + hx(sc) + '" stroke-linecap="round" stroke-width="' + f(H * (0.008 + 0.02 * rnd())) + '" d="' + smoothPath(sp, false) + '"/>');
    }
    var stops = '';
    for (k = 0; k < 5; k++) stops += '<stop offset="' + (k / 4) + '" stop-color="' + hx(mixc(bg, rampN(pal, k / 4), 0.42)) + '"/>';
    return { body: '<rect width="' + W + '" height="' + H + '" fill="url(#wsbg)"/><g id="Wash">' + out.join('') + '</g>', defs: '<linearGradient id="wsbg" x1="0" y1="1" x2="1" y2="0">' + stops + '</linearGradient>', meta: nW + ' colour washes with droplets' };
  }, [
    { id: 'wssun', name: 'Sunburst Wash', pi: 0, m: { diag: 1 }, p: { washes: 8, size: 0.42 } },
    { id: 'wsocean', name: 'Ocean Wash', pi: 1, m: { diag: 1 }, p: { washes: 7, size: 0.44, drops: 80, streaks: 8 } },
    { id: 'wsberry', name: 'Berry Wash', pi: 2, m: { shuffle: 1 }, p: { washes: 6, size: 0.46, bleed: 0.5, drops: 150 } },
    { id: 'wspastel', name: 'Pastel Wash', pi: 3, m: { diag: 1 }, p: { washes: 9, size: 0.4, drops: 40, rings: 0.3, streaks: 2 } },
    { id: 'wsgalaxy', name: 'Galaxy Wash', pi: 4, m: { shuffle: 1 }, p: { washes: 7, size: 0.4, drops: 200, dropsize: 0.8, rings: 0.1 } },
    { id: 'wsflame', name: 'Flame Wash', pi: 6, m: { diag: 1 }, p: { washes: 9, size: 0.38, bleed: 0.5, drops: 130 } }
  ]);

  /* --- Crystal: low-poly gem clusters, floating gems and a thin dot-and-line network --- */
  var CR_T = [['clusters', 'Crystal clusters', 1, 6, 1, 3], ['size', 'Cluster size', 0.08, 0.4, 0.01, 0.2], ['facets', 'Facets', 4, 12, 1, 7], ['gems', 'Floating gems', 0, 30, 1, 8],
    ['network', 'Network', 0, 1, 0.02, 0.6], ['light', 'Shading', 0, 1, 0.02, 0.6], ['clear', 'Keep centre clear', 1]];
  mkFam('Crystal', 'candy', CR_T, function (c) {
    var W = c.W, H = c.H, p = c.p, rnd = c.rnd, pal = palRGB(c.col), bg = hex2rgb(c.col[0]), out = [], k, j, i, nF = Math.round(p.facets);
    var dark = (bg[0] + bg[1] + bg[2]) / 3 < 110;
    var inCentre = function (x, y) { return p.clear && Math.pow((x - W / 2) / (W * 0.27), 2) + Math.pow((y - H / 2) / (H * 0.3), 2) < 1; };
    var gem = function (cx, cy, R, base) {
      var B = [], P0 = [cx + (rnd() - 0.5) * R * 0.3, cy + (rnd() - 0.5) * R * 0.3], a0 = rnd() * TAU, n = Math.max(4, nF);
      for (i = 0; i < n; i++) { var an = a0 + i / n * TAU + (rnd() - 0.5) * 0.4, rr = R * (0.7 + 0.5 * rnd()); B.push([cx + Math.cos(an) * rr, cy + Math.sin(an) * rr]); }
      for (i = 0; i < n; i++) {
        var A = B[i], Bn = B[(i + 1) % n], mid = Math.atan2((A[1] + Bn[1]) / 2 - cy, (A[0] + Bn[0]) / 2 - cx);
        var sh = (rnd() - 0.5) * 0.7 * p.light + 0.35 * p.light * Math.cos(mid + 0.8) * (dark ? 0.6 : 1);
        var cc = hx(fshade(base, sh * 0.6));
        out.push('<path fill="' + cc + '" stroke="' + cc + '" stroke-width="0.6" d="M' + f(P0[0]) + ' ' + f(P0[1]) + 'L' + f(A[0]) + ' ' + f(A[1]) + 'L' + f(Bn[0]) + ' ' + f(Bn[1]) + 'Z"/>');
      }
    };
    var nodes = [];
    for (k = 0; k < Math.round(p.network * 70); k++) {
      var nx = W * rnd(), ny = H * rnd(); if (inCentre(nx, ny) && rnd() < 0.85) continue; nodes.push([nx, ny]);
    }
    var lc = hx(mixc(bg, dark ? [200, 200, 220] : [90, 90, 105], 0.45)), ld = '';
    for (i = 0; i < nodes.length; i++) { var cnt = 0; for (j = i + 1; j < nodes.length && cnt < 3; j++) { if (Math.hypot(nodes[i][0] - nodes[j][0], nodes[i][1] - nodes[j][1]) < W * 0.14) { ld += 'M' + f(nodes[i][0]) + ' ' + f(nodes[i][1]) + 'L' + f(nodes[j][0]) + ' ' + f(nodes[j][1]); cnt++; } } }
    if (ld) out.push('<path fill="none" stroke="' + lc + '" stroke-width="' + f(Math.max(0.8, H * 0.0011)) + '" d="' + ld + '"/>');
    nodes.forEach(function (n) { out.push('<circle cx="' + f(n[0]) + '" cy="' + f(n[1]) + '" r="' + f(H * (0.002 + 0.006 * rnd())) + '" fill="' + hx(mixc(bg, dark ? [210, 210, 230] : [110, 110, 125], 0.5 + 0.3 * rnd())) + '"/>'); });
    for (k = 0; k < Math.round(p.clusters); k++) {
      var side = k % 2, cx = rnd() < 0.8 ? (side ? W * (0.97 - 0.12 * rnd()) : W * (0.03 + 0.12 * rnd())) : W * rnd(), cy = H * (0.15 + 0.7 * rnd()), R = p.size * H, np = 3 + Math.floor(rnd() * 4);
      for (j = 0; j < np; j++) gem(cx + (rnd() - 0.5) * R * 1.6, cy + (rnd() - 0.5) * R * 1.8, R * (0.45 + 0.55 * rnd()), pal[(j + k) % pal.length]);
    }
    for (k = 0; k < Math.round(p.gems); k++) {
      var gx = W * rnd(), gy = H * rnd(), tries = 0;
      while (inCentre(gx, gy) && tries++ < 8) { gx = W * rnd(); gy = H * rnd(); }
      gem(gx, gy, H * (0.025 + 0.05 * rnd()), pal[Math.floor(rnd() * pal.length)]);
    }
    var inner = mixc(bg, dark ? [40, 40, 70] : [255, 255, 255], dark ? 0.25 : 0.75);
    return { body: '<rect width="' + W + '" height="' + H + '" fill="url(#cgl)"/><g id="Crystal">' + out.join('') + '</g>', defs: '<radialGradient id="cgl" cx="0.5" cy="0.5" r="0.7"><stop offset="0" stop-color="' + hx(inner) + '"/><stop offset="1" stop-color="' + hx(bg) + '"/></radialGradient>', meta: 'crystal clusters and ' + nodes.length + ' network nodes' };
  }, [
    { id: 'crcorner', name: 'Crystal Corners', pi: 0, p: { clusters: 4, size: 0.2, gems: 8 } },
    { id: 'crscatter', name: 'Gem Scatter', pi: 1, p: { clusters: 1, size: 0.1, gems: 26, network: 0.4 } },
    { id: 'crcloud', name: 'Shard Cloud', pi: 3, p: { clusters: 5, size: 0.26, facets: 5, gems: 4, network: 0.3, light: 0.8 } },
    { id: 'crnet', name: 'Network Gems', pi: 5, p: { clusters: 2, size: 0.16, gems: 14, network: 1 } },
    { id: 'crice', name: 'Ice Crystals', pi: 2, p: { clusters: 3, size: 0.22, facets: 9, gems: 10, light: 0.9 } },
    { id: 'crneon', name: 'Neon Crystals', pi: 6, p: { clusters: 3, size: 0.2, facets: 7, gems: 12, network: 0.7, light: 0.7 } }
  ]);

  /* --- Halftone: gradient-coloured geometric tiles with halftone dot or scan-line patterns --- */
  function convexScan(poly, y) {
    var lo = 1e9, hi = -1e9, n = poly.length, i;
    for (i = 0; i < n; i++) { var a = poly[i], b = poly[(i + 1) % n]; if ((a[1] <= y && b[1] > y) || (b[1] <= y && a[1] > y)) { var x = a[0] + (y - a[1]) / (b[1] - a[1]) * (b[0] - a[0]); if (x < lo) lo = x; if (x > hi) hi = x; } }
    return hi > lo ? [lo, hi] : null;
  }
  function inConvex(poly, x, y, m) {
    var n = poly.length, s = 0, i;
    for (i = 0; i < n; i++) { var a = poly[i], b = poly[(i + 1) % n], cr = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]), len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1; cr /= len; if (Math.abs(cr) < m) return false; if (s === 0) s = cr > 0 ? 1 : -1; else if ((cr > 0 ? 1 : -1) !== s) return false; }
    return true;
  }
  var HT_T = [['tiles', 'Tiles across', 4, 26, 1, 10], ['kind', 'Shape (1 tri, 2 hex, 3 square, 4 diamond)', 1, 4, 1, 1], ['angle', 'Colour angle', 0, 360, 5, 35], ['range', 'Colour range', 0.4, 1.4, 0.02, 1],
    ['jitter', 'Tile variation', 0, 0.3, 0.01, 0.06], ['dots', 'Dot tiles', 0, 1, 0.02, 0.6], ['lines', 'Line tiles', 0, 1, 0.02, 0], ['dens', 'Dot density', 3, 14, 1, 7]];
  mkFam('Halftone', 'halftone', HT_T, function (c) {
    var W = c.W, H = c.H, p = c.p, rnd = c.rnd, pal = palRGB(c.col), n = Math.round(p.tiles), kind = Math.round(p.kind), s = W / n, tiles = [], r, q, i;
    var Lc = Math.hypot(W, H), a = p.angle * Math.PI / 180, ca = Math.cos(a), sa = Math.sin(a), cb = Math.cos(a + Math.PI / 2), sb = Math.sin(a + Math.PI / 2);
    if (kind === 1) { var h = s * 0.866, rows = Math.ceil(H / h) + 1; for (r = 0; r < rows; r++) for (q = -1; q <= n; q++) { var xo = (r % 2) * s / 2 + q * s, y0 = r * h; tiles.push([[xo, y0 + h], [xo + s, y0 + h], [xo + s / 2, y0]]); tiles.push([[xo + s / 2, y0], [xo + s * 1.5, y0], [xo + s, y0 + h]]); } }
    else if (kind === 2) { var R = s / 1.732, rs = Math.ceil(H / (1.5 * R)) + 2; for (r = -1; r < rs; r++) for (q = -1; q <= n; q++) { var cx = q * s + (r % 2) * s / 2, cy = r * 1.5 * R, hp = []; for (i = 0; i < 6; i++) { var an = Math.PI / 2 + i * Math.PI / 3; hp.push([cx + R * 1.01 * Math.cos(an), cy + R * 1.01 * Math.sin(an)]); } tiles.push(hp); } }
    else if (kind === 3) { for (r = 0; r < Math.ceil(H / s) + 1; r++) for (q = 0; q < n + 1; q++) tiles.push([[q * s, r * s], [q * s + s, r * s], [q * s + s, r * s + s], [q * s, r * s + s]]); }
    else { var hh = s / 2; for (r = -1; r < Math.ceil(H / hh) + 2; r++) for (q = -1; q <= n; q++) { var dx = q * s + (r % 2) * hh, dy = r * hh; tiles.push([[dx - hh, dy], [dx, dy - hh], [dx + hh, dy], [dx, dy + hh]]); } }
    var ds = s / p.dens, est = tiles.length * p.dots * (s * s * 0.4) / (ds * ds);
    if (est > 7000) ds *= Math.sqrt(est / 7000);
    var out = [], nd = 0;
    tiles.forEach(function (T) {
      var mx = 0, my = 0; T.forEach(function (v) { mx += v[0] / T.length; my += v[1] / T.length; });
      if (mx < -s || mx > W + s || my < -s || my > H + s) return;
      var t = ((mx - W / 2) * ca + (my - H / 2) * sa) / Lc + 0.5, tcol = rampN(pal, 0.5 + (t - 0.5) * p.range + (rnd() - 0.5) * p.jitter * 2), hc = hx(tcol);
      var d = 'M' + T.map(function (v) { return f(v[0]) + ' ' + f(v[1]); }).join('L') + 'Z';
      out.push('<path fill="' + hc + '" stroke="' + hc + '" stroke-width="0.8" stroke-linejoin="round" d="' + d + '"/>');
      var pick = rnd(), lc = hx(fshade(tcol, 0.5));
      if (pick < p.dots) {
        var xs = T.map(function (v) { return v[0]; }), ys = T.map(function (v) { return v[1]; }), x0 = Math.min.apply(0, xs), x1 = Math.max.apply(0, xs), y0 = Math.min.apply(0, ys), y1 = Math.max.apply(0, ys), dd = '', gy, gx;
        for (gy = Math.floor(y0 / ds); gy * ds <= y1; gy++) for (gx = Math.floor(x0 / ds); gx * ds <= x1; gx++) {
          var px = gx * ds + (gy % 2) * ds / 2, py = gy * ds;
          if (px < x0 || px > x1 || py < y0 || py > y1 || !inConvex(T, px, py, ds * 0.22)) continue;
          var g = clamp01(0.5 + ((px - W / 2) * cb + (py - H / 2) * sb) / Lc * 1.3), rd = ds * 0.5 * (0.2 + 0.75 * g);
          dd += 'M' + f(px - rd) + ' ' + f(py) + 'a' + f(rd) + ' ' + f(rd) + ' 0 1 0 ' + f(2 * rd) + ' 0a' + f(rd) + ' ' + f(rd) + ' 0 1 0 ' + f(-2 * rd) + ' 0Z'; nd++;
        }
        if (dd) out.push('<path fill="' + lc + '" d="' + dd + '"/>');
      } else if (pick < p.dots + p.lines) {
        var ys2 = T.map(function (v) { return v[1]; }), ly0 = Math.min.apply(0, ys2), ly1 = Math.max.apply(0, ys2), ld = '', yy, ls = Math.max(3, ds * 0.9);
        for (yy = ly0 + ls * 0.5; yy < ly1; yy += ls) { var sg = convexScan(T, yy); if (sg && sg[1] - sg[0] > ls * 0.5) ld += 'M' + f(sg[0] + 1) + ' ' + f(yy) + 'L' + f(sg[1] - 1) + ' ' + f(yy); }
        if (ld) out.push('<path fill="none" stroke="' + lc + '" stroke-width="' + f(Math.max(0.8, ls * 0.3)) + '" d="' + ld + '"/>');
      }
    });
    return { body: '<g id="Halftone">' + out.join('') + '</g>', defs: '', meta: tiles.length + ' tiles, ' + nd + ' halftone dots' };
  }, [
    { id: 'httri', name: 'Triangle Halftone', pi: 0, p: { kind: 1, tiles: 9, dots: 0.6 } },
    { id: 'hthex', name: 'Hex Halftone', pi: 1, p: { kind: 2, tiles: 7, angle: 90, dots: 0.55, dens: 8 } },
    { id: 'htsquare', name: 'Square Dots', pi: 2, p: { kind: 3, tiles: 8, angle: 135, dots: 0.7, dens: 6 } },
    { id: 'htdiamond', name: 'Diamond Halftone', pi: 3, p: { kind: 4, tiles: 8, angle: 0, dots: 0.5, lines: 0.3 } },
    { id: 'htlines', name: 'Scanline Tiles', pi: 4, p: { kind: 1, tiles: 8, angle: 60, dots: 0.15, lines: 0.6 } },
    { id: 'htbig', name: 'Big Dot Gradient', pi: 5, p: { kind: 3, tiles: 5, angle: 200, dots: 1, dens: 10, jitter: 0.1 } }
  ]);

  /* --- Smoke: thin glowing wisps (flame / smoke / aurora threads) on a dark ground. Glow is pre-blended, so EPS stays exact --- */
  var SM_T = [['wisps', 'Wisps', 20, 240, 1, 130], ['length', 'Length', 0.15, 1.2, 0.01, 0.7], ['curl', 'Curl', 0, 1.2, 0.02, 0.9], ['width', 'Line width', 0.4, 4, 0.1, 2.2],
    ['core', 'Bright core', 0, 1, 0.02, 0.6], ['base', 'Ground glow', 0, 1, 0.02, 0.4]];
  mkFam('Smoke', 'smoke', SM_T, function (c, m) {
    var W = c.W, H = c.H, p = c.p, rnd = c.rnd, pal = palRGB(c.col), bg = hex2rgb(c.col[0]), n = Math.round(p.wisps), glow = [], mid = [], core = [], w, i, sgm, lw = H / 1080;
    for (w = 0; w < n; w++) {
      var src = m.source === 'both' ? (rnd() < 0.5 ? 'bottom' : 'sides') : m.source || 'bottom', x0, y0, hd;
      if (src === 'bottom') { x0 = W * rnd(); y0 = H * (0.92 + 0.1 * rnd()); hd = -Math.PI / 2 + (rnd() - 0.5) * 0.6; }
      else if (src === 'sides') { var sd = rnd() < 0.5 ? 0 : 1; x0 = sd ? W * (1 - 0.08 * rnd()) : W * 0.08 * rnd(); y0 = H * (0.5 + 0.55 * rnd()); hd = -Math.PI / 2 + (sd ? -1 : 1) * 0.3 * rnd(); }
      else { x0 = W * (0.5 + (rnd() - 0.5) * 0.3); y0 = H * (0.4 + 0.2 * rnd()); hd = rnd() * TAU; }
      var tt = m.tmode === 'y' ? 1 - y0 / H : 1 - Math.abs(2 * x0 / W - 1), col = rampN(pal, clamp01(tt * 0.95 + (rnd() - 0.5) * 0.2));
      var N = 40, len = p.length * H * (0.35 + 0.65 * rnd()), step = len / N, cph = rnd() * TAU, cf = 3 + rnd() * 5, x = x0, y = y0, pts = [[x, y]];
      for (i = 1; i <= N; i++) { var ang = hd + p.curl * (1.5 * Math.sin(cph + i * cf / N) + 0.7 * Math.sin(cph * 2 + i * cf * 2.1 / N)); x += Math.cos(ang) * step; y += Math.sin(ang) * step; pts.push([x, y]); }
      var inten = [1, 0.85, 0.62, 0.38], S = 4, seg = N / S, base = 0.6 + 0.4 * rnd();
      for (sgm = 0; sgm < S; sgm++) {
        var chunk = pts.slice(Math.floor(sgm * seg), Math.floor((sgm + 1) * seg) + 2); if (chunk.length < 3) continue;
        var I = inten[sgm] * base, d = smoothPath(chunk, false);
        glow.push('<path stroke="' + hx(mixc(bg, col, I * 0.22)) + '" stroke-width="' + f(p.width * lw * 8) + '" d="' + d + '"/>');
        mid.push('<path stroke="' + hx(mixc(bg, col, I * 0.55)) + '" stroke-width="' + f(p.width * lw * 3.2) + '" d="' + d + '"/>');
        core.push('<path stroke="' + hx(mixc(mixc(bg, col, I * 0.9), [255, 255, 255], p.core * 0.6 * I)) + '" stroke-width="' + f(p.width * lw) + '" d="' + d + '"/>');
      }
    }
    var defs = '', pre = '';
    if (p.base > 0.02) {
      var wc = rampN(pal, 0.9), gh = H * 0.22;
      defs = '<linearGradient id="smb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + hx(bg) + '"/><stop offset="1" stop-color="' + hx(mixc(bg, wc, p.base * 0.55)) + '"/></linearGradient>';
      pre = '<rect x="0" y="' + f(H - gh) + '" width="' + W + '" height="' + f(gh) + '" fill="url(#smb)"/>';
    }
    return { body: pre + '<g id="Smoke" fill="none" stroke-linecap="round" stroke-linejoin="round">' + glow.join('') + mid.join('') + core.join('') + '</g>', defs: defs, meta: n + ' glowing wisps' };
  }, [
    { id: 'smflame', name: 'Flame Wisps', pi: 0, m: { source: 'bottom', tmode: 'x' }, p: { wisps: 150, length: 0.6, width: 2.2, base: 0.5 } },
    { id: 'smtwin', name: 'Twin Smoke', pi: 3, m: { source: 'sides', tmode: 'x' }, p: { wisps: 130, length: 0.85, curl: 1, width: 2, base: 0.2 } },
    { id: 'smaurora', name: 'Aurora Threads', pi: 5, m: { source: 'bottom', tmode: 'x' }, p: { wisps: 110, length: 1.1, curl: 0.4, width: 1.8, base: 0.3 } },
    { id: 'smink', name: 'Ink In Water', pi: 1, m: { source: 'center', tmode: 'y' }, p: { wisps: 170, length: 0.5, curl: 1.1, width: 2.4, base: 0 } },
    { id: 'smtoxic', name: 'Toxic Smoke', pi: 2, m: { source: 'both', tmode: 'x' }, p: { wisps: 140, length: 0.7, curl: 0.9, width: 2, base: 0.35 } },
    { id: 'smember', name: 'Ember Strands', pi: 4, m: { source: 'bottom', tmode: 'y' }, p: { wisps: 180, length: 0.5, curl: 0.7, width: 2, base: 0.6 } }
  ]);


  /* ---------- Ribbed-glass engine: bent, shaded glass ribs over a soft light field (replaces the flat-rib look) ---------- */
  function ribbedEngine(c, m) {
    var W = c.W, H = c.H, rnd = c.rnd, asp = W / H, q = c.p, pal = palRGB(c.col), bgc = hex2rgb(c.col[0]), i, j, k, w, mode = m.mode;
    var dv = function (v, d) { return v === undefined || v === null || isNaN(v) ? d : v; };
    var P = { bars: dv(q.bars, 150), duty: dv(q.duty, 0.55), blobs: dv(q.blobs, 4), size: dv(q.size, dv(q.blobsz, 0.2)), stretch: dv(q.stretch, 1.2), tilt: dv(q.tilt, 15), scatter: dv(q.scatter, 0.6),
      cy: dv(q.cy, 0.5), cyspread: dv(q.cyspread, 0.12 + 0.7 * dv(q.scatter, 0.6)), warp: dv(q.warp, 0.8), shear: dv(q.shear, dv(q.refr, 0.6) * 0.5), shade: dv(q.shade, 0.7), punch: dv(q.punch, 1.2),
      flicker: dv(q.flicker, 0.1), fx: dv(q.fx, 3), fy: dv(q.fy, 1.2), gamma: dv(q.gamma, 1), height: dv(q.height, 0.5), varw: dv(q.varw, 0.12) };
    var light = (bgc[0] + bgc[1] + bgc[2]) / 3 > 140, wph = [rnd() * TAU, rnd() * TAU, rnd() * TAU, rnd() * TAU], curJit = 1, field;
    var tone = function (acc, gain) { return [0, 1, 2].map(function (ch) { return bgc[ch] + (255 - bgc[ch]) * (1 - Math.exp(-gain * acc[ch] * curJit / 255)); }); };
    if (mode === 'blobs') {
      var nb = Math.round(P.blobs), blobs = [];
      for (k = 0; k < nb; k++) {
        var sz = P.size * (0.7 + 0.6 * rnd());
        blobs.push({ cx: asp * ((k + 0.3 + 0.4 * rnd()) / nb * (1 - P.scatter) + (0.08 + 0.84 * rnd()) * P.scatter), cy: P.cy + (rnd() - 0.5) * P.cyspread, sx: sz, sy: sz * P.stretch,
          cs: 0, sn: 0, a: 0.8 + 0.6 * rnd(), c: pal[(k + Math.floor(rnd() * 2)) % pal.length] });
        var th = (P.tilt + (rnd() - 0.5) * 30) * Math.PI / 180; blobs[k].cs = Math.cos(th); blobs[k].sn = Math.sin(th);
      }
      field = function (xn, yn) {
        var wx = xn * asp + P.warp * 0.05 * Math.sin(TAU * 1.7 * yn + wph[0]) + P.warp * 0.025 * Math.sin(TAU * 3.3 * yn + wph[1]), wy = yn + P.warp * 0.05 * Math.sin(TAU * 1.3 * xn * asp + wph[2]) + P.warp * 0.02 * Math.sin(TAU * 4.1 * xn * asp + wph[0]);
        var acc = [0, 0, 0], tot = 0, b, I, dx, dy, u, v;
        for (var z = 0; z < blobs.length; z++) {
          b = blobs[z]; dx = wx - b.cx; dy = wy - b.cy; u = (dx * b.cs + dy * b.sn) / b.sx; v = (-dx * b.sn + dy * b.cs) / b.sy; I = b.a * Math.exp(-(u * u + v * v));
          acc[0] += I * b.c[0]; acc[1] += I * b.c[1]; acc[2] += I * b.c[2]; tot += I;
        }
        if (light) { var A = clamp01((1 - Math.exp(-P.punch * 1.6 * tot)) * curJit), cl = tot > 1e-4 ? [acc[0] / tot, acc[1] / tot, acc[2] / tot] : pal[0]; return mixc(bgc, cl, A); }
        return tone(acc, P.punch * 1.8);
      };
    } else if (mode === 'wave') {
      field = function (xn, yn) {
        var u = P.fx * xn * asp, B = 0.55 * (0.5 + 0.5 * Math.sin(TAU * (u + 0.35 * Math.sin(TAU * P.fy * yn + wph[0])) + wph[1])) + 0.45 * (0.5 + 0.5 * Math.sin(TAU * 1.9 * u + wph[2] + yn * 2.4));
        B = Math.pow(clamp01(B), P.gamma) * (0.62 + 0.38 * Math.sin(Math.PI * yn)) * curJit; return rampN(pal, B);
      };
    } else if (mode === 'rise') {
      field = function (xn, yn) {
        var b = 0.5 + 0.5 * Math.sin(TAU * P.fx * 0.5 * xn * asp + wph[0]) * (0.6 + 0.4 * Math.sin(TAU * xn * 3.1 + wph[1])), t = Math.pow(yn, 1.3 * P.gamma) * (0.4 + 0.75 * b) * curJit;
        return rampN(pal, clamp01(t));
      };
    } else if (mode === 'eq') {
      field = function (xn, yn) {
        var env = 0.5 + 0.5 * Math.sin(TAU * P.fx * 0.5 * xn + wph[0]); env = 0.25 + 0.75 * env * (0.8 + 0.2 * Math.sin(xn * 83 + wph[1] * 7));
        var h = P.height * env * 0.6 + 0.04, d = (yn - 0.5) / h; return rampN(pal, clamp01(Math.exp(-d * d * 1.4) * curJit));
      };
    } else {
      /* glow-wave modes used by the Glow family: additive sine-wave light ribbons seen through ribs */
      var nW = mode === 'grise' ? 1 : Math.round(dv(q.waves, 2)), waves = [], amp = dv(q.amp, 0.17), freq = dv(q.freq, 1), glw = dv(q.glow, 0.17), spread = dv(q.spread, 0.6), fade = dv(q.fade, 0.3), core = dv(q.core, 0.4);
      for (w = 0; w < nW; w++) waves.push({ c0: 0.5 + (rnd() - 0.5) * 0.34, sl: (rnd() - 0.5) * 0.5, a: amp * (0.7 + 0.6 * rnd()), f: freq * (0.75 + 0.5 * rnd()), ph: rnd() * TAU, ph2: rnd() * TAU, ca: pal[w % pal.length], cb: pal[(w + 1 + Math.floor(rnd() * 3)) % pal.length] });
      var curve = function (ww, xn) { return ww.c0 + ww.sl * (xn - 0.5) + ww.a * Math.sin(TAU * ww.f * xn + ww.ph) + 0.35 * ww.a * Math.sin(TAU * ww.f * 2.1 * xn + ww.ph2); };
      field = function (xn, yn) {
        var acc = [0, 0, 0], tot = 0, vig = 1 - fade * Math.pow(Math.abs(2 * xn - 1), 2.2), ww, cen, sg, dd, I, cw;
        if (mode === 'grise') {
          ww = waves[0]; var edge = curve(ww, xn) + 0.12, t = sstep(edge - glw, edge + glw * 0.6, yn), cr = mixc(mixc(pal[0], pal[1 % pal.length], sstep(0, 1, (xn - 0.5) * spread * 2 + 0.5)), pal[2 % pal.length], 0.55 * yn * yn);
          return tone([cr[0] * t * vig * 1.6, cr[1] * t * vig * 1.6, cr[2] * t * vig * 1.6], 1.8);
        }
        for (w = 0; w < waves.length; w++) {
          ww = waves[w]; cen = curve(ww, xn); sg = glw * (0.7 + 0.5 * (0.5 + 0.5 * Math.sin(TAU * 0.7 * ww.f * xn + ww.ph2))); dd = (yn - cen) / sg; I = Math.exp(-dd * dd);
          cw = mode === 'gspectrum' ? rampN(pal, sstep(0, 1, (xn - 0.5) * (0.6 + spread * 1.6) + 0.5)) : mixc(ww.ca, ww.cb, sstep(0, 1, (xn - 0.5) * spread * 2 + 0.5));
          acc[0] += I * cw[0]; acc[1] += I * cw[1]; acc[2] += I * cw[2]; tot += I;
        }
        return tone([acc[0] * vig, acc[1] * vig, acc[2] * vig], 1.7 + core * 0.8);
      };
    }
    var n = Math.round(P.bars), pitch = W / n, S = 18, M = 6, ns = P.shade > 0.04 ? 3 : 1, cum = ns === 3 ? [0, 0.3, 0.7, 1] : [0, 1];
    var bmul = ns === 3 ? [1 + 0.5 * P.shade, 1, Math.max(0.25, 1 - 0.55 * P.shade)] : [1], defs = '', out = [], kept = 0;
    for (i = 0; i < n; i++) {
      var xc = (i + 0.5) * pitch, bw = Math.max(0.8, pitch * P.duty * (1 + P.varw * (rnd() - 0.5) * 2)), lean = P.shear * pitch * 1.1 * Math.sin(i * 0.23 + wph[3]);
      var amp2 = P.shear * pitch * 1.0 * (0.4 + 0.6 * Math.abs(Math.sin(i * 0.07 + wph[0])));
      var offs = function (y) { var t = y / H; return lean * (t - 0.5) * 2 + amp2 * Math.sin(TAU * 1.4 * t + i * 0.11 + wph[1]); };
      curJit = 1 + (rnd() - 0.5) * 2 * P.flicker;
      var gstops = [], maxd = 0;
      for (j = 0; j < ns; j++) {
        var st = '';
        for (var sIdx = 0; sIdx < S; sIdx++) {
          var yn = sIdx / (S - 1), xs = (xc - bw / 2 + bw * (cum[j] + cum[j + 1]) / 2 + offs(yn * H)) / W, rgb = field(xs, yn);
          rgb = [0, 1, 2].map(function (ch) { return Math.max(0, Math.min(255, rgb[ch] * bmul[j])); });
          maxd = Math.max(maxd, Math.abs(rgb[0] - bgc[0]) + Math.abs(rgb[1] - bgc[1]) + Math.abs(rgb[2] - bgc[2]));
          st += '<stop offset="' + f(yn) + '" stop-color="' + hx(rgb) + '"/>';
        }
        gstops.push(st);
      }
      if (maxd < 12) continue;
      for (j = 0; j < ns; j++) {
        var xs0 = xc - bw / 2 + bw * cum[j], xs1 = xc - bw / 2 + bw * cum[j + 1] + (j < ns - 1 ? 0.6 : 0), L = [], R = [], t2;
        for (t2 = 0; t2 <= M; t2++) { var yy = H * t2 / M, o = offs(yy); L.push(f(xs0 + o) + ' ' + f(yy)); R.push(f(xs1 + o) + ' ' + f(yy)); }
        var gid = 'rb' + i + '_' + j;
        defs += '<linearGradient id="' + gid + '" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="' + H + '">' + gstops[j] + '</linearGradient>';
        out.push('<path fill="url(#' + gid + ')" d="M' + L.join('L') + 'L' + R.reverse().join('L') + 'Z"/>');
      }
      kept++;
    }
    return { body: '<g id="RibbedGlass">' + out.join('') + '</g>', defs: defs, meta: kept + ' bent glass ribs' + (ns === 3 ? ', 3 shaded strips each' : '') };
  }

  /* --- Saw flames: slanted blades along a diagonal --- */
  function ribbedSaw(c) {
    var W = c.W, H = c.H, p = c.p, rnd = c.rnd, pal = palRGB(c.col), n = Math.round(p.bars), out = [], defs = '', i, ph = rnd() * TAU, ph2 = rnd() * TAU, lw = W / 1920;
    for (i = 0; i < n; i++) {
      var xn = (i + 0.5) / n, x = xn * W * 0.86 + W * 0.07, env = 0.5 + 0.5 * Math.sin(TAU * p.fx * xn + ph), cyc = H * (0.28 + 0.44 * xn + 0.05 * Math.sin(TAU * 1.6 * xn + ph2));
      var hh = H * p.height * (0.3 + 0.7 * env) * 0.5, yt = cyc - hh, yb = cyc + hh, bw = (W / n) * p.duty * 1.5, base = rampN(pal, clamp01(xn * 0.9 + 0.05));
      var gid = 'sw' + i, lean = bw * p.slant;
      defs += '<linearGradient id="' + gid + '" gradientUnits="userSpaceOnUse" x1="0" y1="' + f(yt) + '" x2="0" y2="' + f(yb) + '"><stop offset="0" stop-color="' + hx(mixc(c.col[0] ? hex2rgb(c.col[0]) : [0, 0, 0], base, 0.25)) + '"/><stop offset="0.45" stop-color="' + hx(fshade(base, -0.1)) + '"/><stop offset="1" stop-color="' + hx(fshade(base, 0.12)) + '"/></linearGradient>';
      out.push('<path fill="url(#' + gid + ')" d="M' + f(x) + ' ' + f(yb) + 'L' + f(x + bw) + ' ' + f(yb) + 'L' + f(x + lean) + ' ' + f(yt) + 'Z"/>');
      out.push('<path fill="' + hx(fshade(base, 0.3)) + '" d="M' + f(x + bw * 0.08) + ' ' + f(yb - hh * 0.1) + 'L' + f(x + bw * 0.3) + ' ' + f(yb - hh * 0.1) + 'L' + f(x + lean + bw * 0.04) + ' ' + f(yt + hh * 0.5) + 'Z"/>');
    }
    return { body: '<g id="SawFlames">' + out.join('') + '</g>', defs: defs, meta: n + ' flame blades' };
  }

  /* --- Ripple rings: shaded concentric circles --- */
  function rippleRings(c, m) {
    var W = c.W, H = c.H, p = c.p, rnd = c.rnd, pal = palRGB(c.col), n = Math.round(p.rings), out = [], defs = '', k;
    var cx = W * (m.x + (rnd() - 0.5) * 0.12), cy = H * (m.y + (rnd() - 0.5) * 0.12), maxR = Math.max(Math.hypot(cx, cy), Math.hypot(W - cx, cy), Math.hypot(cx, H - cy), Math.hypot(W - cx, H - cy)) * 1.02, R = [];
    for (k = 0; k <= n; k++) R.push(maxR * Math.pow(1 - k / (n + 0.6), p.curve));
    for (k = 0; k < n; k++) {
      var col = rampN(pal, n > 1 ? k / (n - 1) : 0), r = R[k], rin = R[k + 1] / r, gid = 'rr' + k;
      defs += '<radialGradient id="' + gid + '" gradientUnits="userSpaceOnUse" cx="' + f(cx) + '" cy="' + f(cy) + '" r="' + f(r) + '"><stop offset="0" stop-color="' + hx(fshade(col, -p.depth)) + '"/><stop offset="' + f(Math.max(0, Math.min(0.98, rin))) + '" stop-color="' + hx(fshade(col, -p.depth)) + '"/><stop offset="1" stop-color="' + hx(fshade(col, p.depth * 0.9)) + '"/></radialGradient>';
      out.push('<circle cx="' + f(cx) + '" cy="' + f(cy) + '" r="' + f(r) + '" fill="url(#' + gid + ')"/>');
    }
    return { body: '<g id="Ripple">' + out.join('') + '</g>', defs: defs, meta: n + ' shaded rings' };
  }

  regSet('rib', [
    { name: 'Northern', c: ['#010605', '#12e08c', '#2f8bff', '#8a5cff', '#e8ff6a', '#ff5cc0'] },
    { name: 'Ember', c: ['#050203', '#ff3d1f', '#ff9a1f', '#ffd23d', '#d11a3a', '#7a1fff'] },
    { name: 'Prism', c: ['#020204', '#00d0ff', '#ff2d95', '#ffb02e', '#7a3dff', '#3dff8a'] },
    { name: 'Orchid', c: ['#040208', '#c03dff', '#ff3d9a', '#3d6bff', '#ff9a5a', '#3dd0ff'] },
    { name: 'Aurora', c: ['#020208', '#2f8bff', '#8a3dff', '#ff3da8', '#ff8a3d', '#3dffb0'] },
    { name: 'Sunset Fire', c: ['#050202', '#ff5a1f', '#ffa02e', '#e0204a', '#ffd86a', '#7a1f8a'] },
    { name: 'Cobalt', c: ['#020410', '#1f4dff', '#4f9bff', '#7a5cff', '#00c8ff', '#ff4d9a'] },
    { name: 'Crimson', c: ['#050102', '#e0141f', '#ff4d3d', '#ff8a5a', '#8a0a1a', '#ff2d6f'] }
  ], SH6);
  regSet('ribramp', [
    { name: 'Velvet Red', c: ['#050102', '#3a0408', '#8a0a12', '#d01a1a', '#ff4a3a', '#ff8a6a'] },
    { name: 'Royal Blue', c: ['#020410', '#0a1260', '#1428c8', '#2f5bff', '#6a9bff', '#b8d4ff'] },
    { name: 'Emerald', c: ['#010604', '#04301c', '#0a7a46', '#12c274', '#5affb0', '#c8ffe0'] },
    { name: 'Violet', c: ['#050208', '#240a50', '#5a1fb0', '#9a4fff', '#d08aff', '#f0d0ff'] },
    { name: 'Amber', c: ['#060301', '#401a04', '#a04a08', '#e07a10', '#ffb02e', '#ffe08a'] },
    { name: 'Magenta', c: ['#06010a', '#4a0a3a', '#a0147a', '#e0309a', '#ff6ac0', '#ffc0e8'] }
  ], SH6);
  regSet('ripple', [
    { name: 'Cyan Ripple', c: ['#052a5a', '#e0fcff', '#6aeaf8', '#14c2e0', '#0a8ac8', '#065aa0'] },
    { name: 'Violet Ripple', c: ['#1a0a60', '#fbe8ff', '#e0a0ff', '#b04fff', '#7a2fe0', '#3a14b0'] },
    { name: 'Fire Ripple', c: ['#300808', '#fff0c0', '#ffc04a', '#ff7a1f', '#e0301a', '#8a0a14'] },
    { name: 'Mint Ripple', c: ['#06302a', '#eafff6', '#8af0c8', '#2fc89a', '#14907a', '#0a5a5a'] },
    { name: 'Rose Ripple', c: ['#3a0a28', '#fff0f6', '#ffb0d0', '#ff6aa0', '#d02a78', '#7a1050'] }
  ], SH6);

  regSet('flame', [
    { name: 'Red Flame', c: ['#030203', '#c4140c', '#e8340a', '#ff6a10', '#ff9a1a', '#ffc03a'] },
    { name: 'Blue Flame', c: ['#020308', '#1f3bff', '#4f7bff', '#8a5cff', '#d04fff', '#ff3da8'] },
    { name: 'Gold Flame', c: ['#050301', '#a03a08', '#d86a10', '#ffa020', '#ffd04a', '#fff0a0'] },
    { name: 'Magenta Flame', c: ['#060106', '#8a0a4a', '#d01a78', '#ff4aa0', '#ff8ac0', '#ffd0e8'] }
  ], SH6);
  var RB_BLOB = [['bars', 'Ribs', 40, 300, 1, 150], ['duty', 'Rib width', 0.3, 0.95, 0.01, 0.55], ['blobs', 'Colour blobs', 1, 9, 1, 4], ['size', 'Blob size', 0.06, 0.5, 0.01, 0.2], ['stretch', 'Blob height', 0.4, 3.5, 0.05, 1.2],
    ['tilt', 'Blob tilt', -80, 80, 1, 15], ['scatter', 'Scatter', 0, 1, 0.02, 0.6], ['cy', 'Height position', 0.1, 0.95, 0.01, 0.5], ['warp', 'Organic warp', 0, 1.5, 0.02, 0.8], ['shear', 'Glass bend', 0, 1.5, 0.02, 0.6],
    ['shade', 'Rib shading', 0, 1, 0.02, 0.7], ['punch', 'Colour strength', 0.4, 3, 0.05, 1.2], ['flicker', 'Rib variation', 0, 0.5, 0.01, 0.1]];
  var RB_WAVE = [['bars', 'Ribs', 20, 200, 1, 60], ['duty', 'Rib width', 0.4, 0.98, 0.01, 0.9], ['fx', 'Fold count', 0.5, 8, 0.1, 3], ['fy', 'Wave count', 0.3, 4, 0.05, 1.2], ['gamma', 'Contrast', 0.5, 2, 0.05, 1.1],
    ['shear', 'Glass bend', 0, 1.5, 0.02, 0.15], ['shade', 'Rib shading', 0, 1, 0.02, 0.85], ['flicker', 'Rib variation', 0, 0.5, 0.01, 0.08]];
  var RB_RISE = [['bars', 'Ribs', 12, 160, 1, 40], ['duty', 'Rib width', 0.3, 0.95, 0.01, 0.6], ['fx', 'Brightness waves', 0.5, 8, 0.1, 2.5], ['gamma', 'Glow height', 0.4, 2, 0.05, 1],
    ['shear', 'Glass bend', 0, 1.5, 0.02, 0], ['shade', 'Rib shading', 0, 1, 0.02, 0.9], ['flicker', 'Rib variation', 0, 0.5, 0.01, 0.12]];
  var RB_EQ = [['bars', 'Bars', 20, 160, 1, 60], ['duty', 'Bar width', 0.2, 0.9, 0.01, 0.5], ['fx', 'Wave count', 0.5, 8, 0.1, 3], ['height', 'Glow height', 0.15, 1, 0.01, 0.55],
    ['shear', 'Glass bend', 0, 1.5, 0.02, 0], ['shade', 'Rib shading', 0, 1, 0.02, 0.3], ['flicker', 'Bar variation', 0, 0.5, 0.01, 0.1]];
  var RB_SAW = [['bars', 'Blades', 8, 60, 1, 26], ['duty', 'Blade width', 0.4, 1.4, 0.02, 0.9], ['height', 'Blade height', 0.2, 1, 0.01, 0.5], ['slant', 'Slant', 0, 1, 0.02, 0.15], ['fx', 'Height waves', 0.3, 4, 0.05, 1.3]];
  mkFam('Ribbed', 'rib', RB_BLOB, function (c) { return ribbedEngine(c, { mode: 'blobs' }); }, [
    { id: 'rbaurora', name: 'Ribbed Aurora', pi: 0, p: { blobs: 5, size: 0.17, stretch: 0.6, tilt: 0, scatter: 0.9, cy: 0.45, warp: 1.1, shear: 0.7, punch: 1.3 } },
    { id: 'rbamber', name: 'Amber Blobs', pi: 5, p: { blobs: 4, size: 0.2, stretch: 1.3, tilt: 20, scatter: 0.6, bars: 150, duty: 0.5 } },
    { id: 'rbhill', name: 'Rainbow Hill', pi: 2, p: { blobs: 3, size: 0.28, stretch: 2, tilt: 0, scatter: 0.8, cy: 0.88, warp: 0.6, punch: 1.2 } },
    { id: 'rbdiag', name: 'Diagonal Smoke', pi: 1, p: { blobs: 6, size: 0.11, stretch: 3, tilt: 55, scatter: 0.3, warp: 1, shear: 0.5, bars: 170, duty: 0.5 } },
    { id: 'rbpetal', name: 'Petal Glass', pi: 3, p: { blobs: 7, size: 0.15, stretch: 1.4, tilt: -30, scatter: 0.9, warp: 1.2, shear: 0.9, punch: 1.5 } },
    { id: 'rbduo', name: 'Cobalt Fire', pi: 6, p: { blobs: 2, size: 0.3, stretch: 1.1, tilt: 10, scatter: 0.7, warp: 0.9, shade: 0.8, punch: 1.4 } }
  ]);
  mkFam('Ribbed', 'ribramp', RB_WAVE, function (c) { return ribbedEngine(c, { mode: 'wave' }); }, [
    { id: 'rbcurtain', name: 'Velvet Curtain', pi: 0, p: {} },
    { id: 'rbroyal', name: 'Royal Drape', pi: 1, p: { bars: 50, fx: 2.2, fy: 0.8 } },
    { id: 'rbemerald', name: 'Emerald Folds', pi: 2, p: { bars: 80, duty: 0.8, fx: 4, shade: 0.7 } }
  ]);
  mkFam('Ribbed', 'ribramp', RB_RISE, function (c) { return ribbedEngine(c, { mode: 'rise' }); }, [
    { id: 'rbpillars', name: 'Blue Pillars', pi: 1, p: {} },
    { id: 'rbamberpil', name: 'Amber Pillars', pi: 4, p: { bars: 60, duty: 0.45, fx: 3.5 } }
  ]);
  mkFam('Ribbed', 'ribramp', RB_EQ, function (c) { return ribbedEngine(c, { mode: 'eq' }); }, [
    { id: 'rbeq', name: 'Glow Equalizer', pi: 5, p: {} },
    { id: 'rbeqviolet', name: 'Violet Equalizer', pi: 3, p: { bars: 80, duty: 0.4, fx: 5, height: 0.7 } }
  ]);
  mkFam('Ribbed', 'flame', RB_SAW, ribbedSaw, [
    { id: 'rbsaw', name: 'Saw Flames', pi: 0, p: { bars: 38, duty: 1, height: 0.8, slant: 0.12, fx: 1.2 } },
    { id: 'rbsawblue', name: 'Blue Blades', pi: 1, p: { bars: 30, duty: 1.1, height: 0.6, slant: 0.3, fx: 2 } }
  ]);
  var RP_T = [['rings', 'Rings', 6, 44, 1, 20], ['curve', 'Spacing curve', 0.5, 2, 0.02, 1.1], ['depth', 'Ring shading', 0.05, 0.5, 0.01, 0.22]];
  mkFam('Ripple', 'ripple', RP_T, rippleRings, [
    { id: 'rpcyan', name: 'Cyan Ripples', pi: 0, m: { x: 0.92, y: 1.08 }, p: {} },
    { id: 'rpviolet', name: 'Violet Ripples', pi: 1, m: { x: 0.85, y: 1.1 }, p: { rings: 26, curve: 1.25 } },
    { id: 'rpfire', name: 'Fire Ripples', pi: 2, m: { x: 0.18, y: 0.5 }, p: { rings: 16, depth: 0.28 } },
    { id: 'rptunnel', name: 'Mint Tunnel', pi: 3, m: { x: 0.5, y: 0.5 }, p: { rings: 30, curve: 0.8 } },
    { id: 'rprose', name: 'Rose Ripples', pi: 4, m: { x: 0.05, y: -0.1 }, p: { rings: 24, curve: 1.3 } }
  ]);
  EXTRA.forEach(function (p) { PATTERNS.push(p); });


  var CATS = {
    burst: 'Radial', rings: 'Radial', spiral: 'Radial', rosette: 'Radial', guilloche: 'Radial', kaleido: 'Radial',
    scales: 'Tiles', hex: 'Tiles', cubes: 'Tiles', pinwheel: 'Tiles', dots: 'Tiles', lowpoly: 'Tiles', argyle: 'Tiles',
    truchet: 'Tiles', stars: 'Tiles', mosaic: 'Tiles', bricks: 'Tiles', honeycomb: 'Tiles', bauhaus: 'Tiles', plus: 'Tiles',
    contour: 'Lines', plaid: 'Lines', ribbon: 'Lines', chevron: 'Lines', stripes: 'Lines', grid: 'Lines', wavylines: 'Lines',
    bars: 'Soft', layers: 'Soft', confetti: 'Soft', halftone: 'Soft', blobs: 'Soft', orbs: 'Soft', bubbles: 'Soft'
  };
  PATTERNS.forEach(function (p) { p.cat = CATS[p.id] || p.cat || 'Soft'; });

  var byId = {};
  PATTERNS.forEach(function (p) { byId[p.id] = p; });

  function defaults(id) {
    var o = {};
    byId[id].params.forEach(function (pr) { o[pr.key] = pr.def; });
    return o;
  }
  function defaultColors(id) {
    var pat = byId[id];
    return (pat.defCols || PALETTES[pat.pal].c).slice(0, pat.colors.length);
  }

  function build(id, o) {
    var pat = byId[id];
    if (!pat) throw new Error('Unknown pattern: ' + id);
    o = o || {};
    var W = o.width || 1920, H = o.height || 1080;
    var p = Object.assign(defaults(id), o.params || {});
    var col = (o.colors && o.colors.length ? o.colors : defaultColors(id)).slice();
    while (col.length < pat.colors.length) col.push(col[col.length - 1]);
    if (o.hue) col = col.map(function (x) { return hueShift(x, o.hue); });
    var seed = o.seed == null ? 1 : o.seed;
    var u = Math.sqrt(W * H) / 1440;
    var r = pat.render({ W: W, H: H, u: u, p: p, col: col, rnd: mulberry32(seed) });
    var rot = o.rotate || 0;
    if (rot) {
      var ra = Math.abs(rot % 180) * Math.PI / 180, ca = Math.abs(Math.cos(ra)), sa = Math.abs(Math.sin(ra));
      var sc = Math.max((ca * W + sa * H) / W, (sa * W + ca * H) / H) * 1.02;
      r.body = '<g id="Pattern" transform="translate(' + f(W / 2) + ' ' + f(H / 2) + ') rotate(' + f(rot) + ') scale(' + f(sc) + ') translate(' + f(-W / 2) + ' ' + f(-H / 2) + ')">' + r.body + '</g>';
    }
    var bg = o.transparent ? '' : '<rect id="Background" width="' + W + '" height="' + H + '" fill="' + col[0] + '"/>';
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '">' +
      '<defs><clipPath id="artboard"><rect width="' + W + '" height="' + H + '"/></clipPath>' + r.defs + '</defs>' +
      '<g id="Artboard" clip-path="url(#artboard)">' + bg + r.body + '</g></svg>';
    return { svg: svg, meta: r.meta, shapes: (svg.match(/<(path|circle|rect|polygon|line)\b/g) || []).length, bytes: svg.length };
  }

  function generate(id, o) { return build(id, o).svg; }
  function toFile(svg) { return '<?xml version="1.0" encoding="UTF-8"?>\n' + svg; }

  function randomOptions(id, seed) {
    var rnd = mulberry32(seed * 2654435761 >>> 0), pat = byId[id], params = {};
    pat.params.forEach(function (pr) {
      if (pr.type === 'toggle') { params[pr.key] = rnd() > 0.5 ? 1 : 0; return; }
      var span = pr.max - pr.min;
      var v = pr.def + (rnd() - 0.5) * span * 0.8;
      v = Math.max(pr.min, Math.min(pr.max, v));
      params[pr.key] = +(Math.round(v / pr.step) * pr.step).toFixed(3);
    });
    var PS = palsOf(pat);
    var pal = PS[Math.floor(rnd() * PS.length)].c.slice();
    if (!pat.dark && rnd() > 0.7) { var t = pal[1]; pal[1] = pal[2]; pal[2] = t; }
    return { seed: seed, params: params, colors: pal.slice(0, pat.colors.length) };
  }


  /* ---------- design library: 34 patterns x 15 styles = 510 designs ---------- */
  function cyrb53(str, seed) {
    var h1 = 0xdeadbeef ^ (seed || 0), h2 = 0x41c6ce57 ^ (seed || 0);
    for (var i = 0, ch; i < str.length; i++) {
      ch = str.charCodeAt(i);
      h1 = Math.imul(h1 ^ ch, 2654435761); h2 = Math.imul(h2 ^ ch, 1597334677);
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36);
  }
  function strSeed(str) {
    var h = 2166136261;
    for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }


  var DARK_PALETTES = [
    { name: 'Aurora', c: ['#05070f', '#2f6bff', '#ff4d6d', '#9b5cff', '#22e6d0'] },
    { name: 'Ember', c: ['#080609', '#ff5a1f', '#ffb000', '#d1203a', '#7a2cff'] },
    { name: 'Lagoon', c: ['#041018', '#00b4ff', '#00e5c8', '#2b50ff', '#8ef0ff'] },
    { name: 'Orchid', c: ['#07040f', '#8a3dff', '#ff3dd0', '#3d7bff', '#d2b0ff'] },
    { name: 'Dusk', c: ['#0b0610', '#ff3d6e', '#ff9a3d', '#7a3dff', '#ffd23d'] },
    { name: 'Jade', c: ['#030a08', '#12e08c', '#9bff3d', '#0aa5d5', '#e0ff9a'] },
    { name: 'Frost', c: ['#050912', '#7ad0ff', '#b8e6ff', '#4a7bff', '#e8f4ff'] },
    { name: 'Neon', c: ['#050509', '#ff2bd6', '#2bffe0', '#fff23d', '#3d5bff'] },
    { name: 'Crimson', c: ['#0a0305', '#ff1f3d', '#ff6a3d', '#8a1fff', '#ffb03d'] },
    { name: 'Silver', c: ['#060606', '#e6edf5', '#9aa7b5', '#6a7886', '#ffffff'] },
    { name: 'Cobalt', c: ['#030617', '#1f4dff', '#00c2ff', '#7a5cff', '#ff5cb8'] },
    { name: 'Gold', c: ['#0a0703', '#ffb81f', '#ff7a1f', '#ffe27a', '#c2431f'] }
  ];
  var DARK_LIB = [];
  [0, 120, 240].forEach(function (shift, si) {
    DARK_PALETTES.forEach(function (p) {
      if (shift && p.name === 'Silver') return;
      DARK_LIB.push({ name: p.name + (si === 1 ? ' II' : si === 2 ? ' III' : ''), c: shift ? p.c.map(function (x) { return hueShift(x, shift); }) : p.c.slice() });
    });
  });
  function palettesFor(id) { return byId[id] && byId[id].dark ? DARK_PALETTES : PALETTES; }

  var GLOWLIGHT = [
    { name: 'Steel Fire', c: ['#c4c4c6', '#ff5a1f', '#ffb347', '#e8203a', '#2a2020'] },
    { name: 'Pastel', c: ['#e9eef6', '#7ab0ff', '#ffa6c9', '#a98bff', '#7fe3d0'] },
    { name: 'Mist Blue', c: ['#d6e0ee', '#2a6bff', '#7ad0ff', '#1b2a6b', '#ffffff'] },
    { name: 'Cream Sun', c: ['#f3ead8', '#ff8a1f', '#ffd23d', '#e8403a', '#7a2a1f'] },
    { name: 'Lilac', c: ['#e6e0f0', '#8a5cff', '#ff7ad0', '#3d5bff', '#2a1a4a'] },
    { name: 'Mint', c: ['#dcebe6', '#12c08c', '#9bff3d', '#0a7ad5', '#1a3a30'] },
    { name: 'Rose', c: ['#f1dfe3', '#ff3d6e', '#ffa07a', '#a02a5a', '#3a1a2a'] },
    { name: 'Stone', c: ['#cfcfd2', '#4a5568', '#e0a030', '#2a6bff', '#111111'] }
  ];
  var GLOWLIGHT_LIB = [];
  [0, 90, 180, 270].forEach(function (shift, si) {
    GLOWLIGHT.forEach(function (p) {
      GLOWLIGHT_LIB.push({ name: p.name + (si ? ' ' + 'I'.repeat(si + 1) : ''), c: shift ? p.c.map(function (x, q) { return q === 0 ? x : hueShift(x, shift); }) : p.c.slice() });
    });
  });

  var VIVID = [
    { name: 'Carnival', c: ['#ffffff', '#e8143c', '#0a3dff', '#ffd800', '#00c8e8', '#18b04a'] },
    { name: 'Riot', c: ['#101018', '#ff2d55', '#00e5ff', '#ffe600', '#7a3dff', '#43e06a'] },
    { name: 'Primary', c: ['#ffffff', '#d11a1a', '#1337d6', '#ffe100', '#17a34a', '#ff7a00'] },
    { name: 'Candy', c: ['#fff4fa', '#ff3d9a', '#7a5cff', '#00d0ff', '#ffd23d', '#3dff9a'] },
    { name: 'Tropic', c: ['#fffbe8', '#ff5a1f', '#ffc400', '#00b3a4', '#1a56ff', '#ff2d6f'] },
    { name: 'Sea Pop', c: ['#eefaff', '#0057ff', '#00c2ff', '#00d9a0', '#7a3dff', '#ff4d6d'] },
    { name: 'Night Paint', c: ['#0b0b14', '#ff3d6e', '#ffb02e', '#2fd0ff', '#9b5cff', '#36e08a'] },
    { name: 'Earth Pop', c: ['#f6efe0', '#d2402a', '#e8a317', '#2a7a6a', '#26436b', '#8a9a2a'] },
    { name: 'Acid', c: ['#0a0a0a', '#c6ff00', '#ff00c8', '#00f0ff', '#ffffff', '#ff6a00'] },
    { name: 'Grape', c: ['#f4eefc', '#6a1fff', '#ff2fa0', '#00bfff', '#ffcf1f', '#1fd08a'] }
  ];
  var VIVID_LIB = [];
  [0, 60, 120, 180, 240, 300].forEach(function (shift, si) {
    VIVID.forEach(function (p) {
      VIVID_LIB.push({ name: p.name + (si ? ' ' + 'I'.repeat(Math.min(si + 1, 4)) + (si > 3 ? 'I' : '') : ''), c: shift ? p.c.map(function (x, q) { return q === 0 ? x : hueShift(x, shift); }) : p.c.slice() });
    });
  });
  function palsOf(pat) { return pat.dark && PSETS[pat.dark] ? PSETS[pat.dark].base : pat.dark === 'vivid' ? VIVID : pat.dark === 'light' ? GLOWLIGHT : pat.dark ? DARK_PALETTES : PALETTES; }
  function palsFor(id) { return byId[id] ? palsOf(byId[id]) : PALETTES; }
  var LIB_PALETTES = [];
  [0, 120, 240].forEach(function (shift, si) {
    PALETTES.forEach(function (p) {
      if (shift && p.name === 'Graphite') return;
      LIB_PALETTES.push({
        name: p.name + (si === 1 ? ' II' : si === 2 ? ' III' : ''),
        c: shift ? p.c.map(function (x) { return hueShift(x, shift); }) : p.c.slice()
      });
    });
  });
  function lum(h) { var c = hex2rgb(h); return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255; }
  function contrastOk(cols, min) { return cols.length < 2 || Math.abs(lum(cols[0]) - lum(cols[1])) >= min; }
  var MOODS = ['Classic', 'Dense', 'Airy', 'Bold', 'Fine', 'Wide', 'Tight', 'Soft', 'Crisp', 'Wild', 'Calm', 'Rich', 'Light', 'Deep', 'Vivid'];
  var ALPHA = [0.7071, 0.7321, 0.2361, 0.6458, 0.3166, 0.6055, 0.1623, 0.3589, 0.4142, 0.5774];
  var VARIATIONS_PER_DESIGN = 1000;

  function designOptions(patIdx, m) {
    var pat = PATTERNS[patIdx], params = {}, colors, palName;
    if (m === 0) {
      params = defaults(pat.id); colors = defaultColors(pat.id); palName = 'Original';
    } else {
      pat.params.forEach(function (pr, k) {
        var t = (0.37 + (m + 1) * ALPHA[k % ALPHA.length] + patIdx * 0.131) % 1;
        t = 0.15 + 0.6 * t;
        if (pr.type === 'toggle') { params[pr.key] = t > 0.5 ? 1 : 0; return; }
        var v = Math.round((pr.min + t * (pr.max - pr.min)) / pr.step) * pr.step;
        params[pr.key] = +Math.max(pr.min, Math.min(pr.max, v)).toFixed(3);
      });
      var pal, tries = 0;
      var src = pat.dark && PSETS[pat.dark] ? PSETS[pat.dark].lib : pat.dark === 'vivid' ? VIVID_LIB : pat.dark === 'light' ? GLOWLIGHT_LIB : pat.dark ? DARK_LIB : LIB_PALETTES;
      do { pal = src[(m * 5 + patIdx * 7 + tries) % src.length]; tries++; }
      while (tries < src.length && !contrastOk(pal.c, 0.22));
      colors = pal.c.slice(0, pat.colors.length); palName = pal.name;
    }
    return { pattern: pat.id, mood: m, name: pat.name + ' ' + MOODS[m], style: MOODS[m], paletteName: palName, params: params, colors: colors, seed: 1000 + patIdx * 100 + m };
  }
  function designCount() { return PATTERNS.length * MOODS.length; }
  function designAt(n) {
    n = Math.max(1, Math.min(designCount(), Math.round(n)));
    var o = designOptions(Math.floor((n - 1) / MOODS.length), (n - 1) % MOODS.length);
    o.no = n; return o;
  }
  function designNumber(patternId, mood) {
    for (var i = 0; i < PATTERNS.length; i++) if (PATTERNS[i].id === patternId) return i * MOODS.length + (mood || 0) + 1;
    return 1;
  }

  /* Deterministic variation: same (pattern, base, index, strength) always gives the same result.
     index 0 is the base design itself. Colour hue follows the golden angle so neighbours stay far apart. */
  function variation(id, base, index, strength) {
    strength = strength || 'medium';
    var pat = byId[id], S = { subtle: 0.25, medium: 0.55, wild: 1 }[strength] || 0.55;
    var hueMax = { subtle: 30, medium: 100, wild: 180 }[strength] || 100;
    if (!index) return { seed: 1, params: Object.assign({}, base.params), colors: base.colors.slice(), hue: 0, rotate: 0 };
    var rnd = mulberry32(strSeed(id + ':' + index + ':' + strength + ':' + (base.colors || []).join('')));
    var params = {};
    pat.params.forEach(function (pr) {
      var cur = base.params[pr.key] != null ? base.params[pr.key] : pr.def;
      if (pr.type === 'toggle') { params[pr.key] = rnd() < S * 0.25 ? (cur ? 0 : 1) : cur; return; }
      var v = cur + (rnd() - 0.5) * (pr.max - pr.min) * S;
      v = Math.max(pr.min, Math.min(pr.max, v));
      params[pr.key] = +(Math.round(v / pr.step) * pr.step).toFixed(3);
    });
    var colors = base.colors.slice(), n = colors.length, i, j, t;
    if (n >= 3 && rnd() < 0.1 + 0.35 * S) {
      for (i = n - 1; i > 1; i--) { j = 1 + Math.floor(rnd() * i); t = colors[i]; colors[i] = colors[j]; colors[j] = t; }
    }
    if (n >= 2 && rnd() < 0.12 * S) { t = colors[0]; colors[0] = colors[1]; colors[1] = t; }
    if (!contrastOk(colors, 0.15) && contrastOk(base.colors, 0.15)) colors = base.colors.slice();
    var g = (index * 0.6180339887) % 1;
    var hue = Math.round(((g - 0.5) * 2 * hueMax) / 5) * 5;
    var rotate = 0;
    if (S > 0.3 && rnd() < 0.1 + 0.45 * S) rotate = [-60, -45, -30, -15, 15, 30, 45, 60, 90][Math.floor(rnd() * 9)];
    return { seed: 1 + Math.floor(rnd() * 1e9), params: params, colors: colors, hue: hue, rotate: rotate };
  }


  /* ======================== SVG -> EPS (PostScript level 2) ========================
   * Converts the SVG this engine writes into a plain-vector EPS: paths, fills, strokes, clips.
   * EPS has no transparency, so opacity is blended against the background colour, and
   * gradients are flattened into thin bands. Everything stays vector. */
  function toEPS(svg, title) {
    var wh = /<svg[^>]*?\swidth="([\d.]+)"[^>]*?\sheight="([\d.]+)"/.exec(svg);
    var W = wh ? +wh[1] : 1920, H = wh ? +wh[2] : 1080;
    var bgm = /<rect id="Background"[^>]*?fill="(#[0-9a-fA-F]{3,6})"/.exec(svg);
    var BG = bgm ? hex2rgb(bgm[1]) : [255, 255, 255];
    var ps = [], defsPat = {}, defsGrad = {};
    var N = function (n) { return String(+(+n).toFixed(2)); };
    var num = function (v, d) { return v == null || v === '' ? (d || 0) : +v; };

    var mmul = function (A, B) {
      return [A[0] * B[0] + A[2] * B[1], A[1] * B[0] + A[3] * B[1], A[0] * B[2] + A[2] * B[3], A[1] * B[2] + A[3] * B[3],
        A[0] * B[4] + A[2] * B[5] + A[4], A[1] * B[4] + A[3] * B[5] + A[5]];
    };
    var parseTransform = function (str) {
      var M = [1, 0, 0, 1, 0, 0];
      if (!str) return M;
      var re = /(\w+)\(([^)]*)\)/g, m;
      while ((m = re.exec(str))) {
        var v = m[2].trim().split(/[\s,]+/).map(Number), T = null, k;
        if (m[1] === 'translate') T = [1, 0, 0, 1, v[0], v[1] || 0];
        else if (m[1] === 'scale') T = [v[0], 0, 0, v.length > 1 ? v[1] : v[0], 0, 0];
        else if (m[1] === 'rotate') {
          var r = v[0] * Math.PI / 180, co = Math.cos(r), si = Math.sin(r);
          T = [co, si, -si, co, 0, 0];
          if (v.length >= 3) T = mmul(mmul([1, 0, 0, 1, v[1], v[2]], T), [1, 0, 0, 1, -v[1], -v[2]]);
        } else if (m[1] === 'matrix') T = v;
        if (T) M = mmul(M, T);
        k = 0;
      }
      return M;
    };
    var attrsOf = function (s) { var o = {}, m, re = /([\w:-]+)="([^"]*)"/g; while ((m = re.exec(s))) o[m[1]] = m[2]; return o; };
    var parseColor = function (v) {
      if (!v || v === 'none') return null;
      if (v.charAt(0) === '#') return hex2rgb(v);
      if (v === 'white') return [255, 255, 255];
      if (v === 'black') return [0, 0, 0];
      return null;
    };
    var flat = function (c, a) {
      if (a >= 0.999) return c;
      a = Math.max(0, a);
      return [BG[0] + (c[0] - BG[0]) * a, BG[1] + (c[1] - BG[1]) * a, BG[2] + (c[2] - BG[2]) * a];
    };
    var rgbk = function (c) { return [c[0], c[1], c[2]].map(function (x) { return String(+(x / 255).toFixed(3)); }).join(' ') + ' k'; };
    var TP = function (M, x, y) { return [M[0] * x + M[2] * y + M[4], M[1] * x + M[3] * y + M[5]]; };

    var ellipseCmds = function (cx, cy, rx, ry) {
      var k = 0.5522847498;
      return [['M', cx + rx, cy], ['C', cx + rx, cy + k * ry, cx + k * rx, cy + ry, cx, cy + ry], ['C', cx - k * rx, cy + ry, cx - rx, cy + k * ry, cx - rx, cy],
        ['C', cx - rx, cy - k * ry, cx - k * rx, cy - ry, cx, cy - ry], ['C', cx + k * rx, cy - ry, cx + rx, cy - k * ry, cx + rx, cy], ['Z']];
    };
    var rectCmds = function (x, y, w, h, rx) {
      rx = Math.min(rx, w / 2, h / 2);
      if (rx <= 0.01) return [['M', x, y], ['L', x + w, y], ['L', x + w, y + h], ['L', x, y + h], ['Z']];
      var k = 0.5522847498 * rx;
      return [['M', x + rx, y], ['L', x + w - rx, y], ['C', x + w - rx + k, y, x + w, y + rx - k, x + w, y + rx], ['L', x + w, y + h - rx],
        ['C', x + w, y + h - rx + k, x + w - rx + k, y + h, x + w - rx, y + h], ['L', x + rx, y + h], ['C', x + rx - k, y + h, x, y + h - rx + k, x, y + h - rx],
        ['L', x, y + rx], ['C', x, y + rx - k, x + rx - k, y, x + rx, y], ['Z']];
    };
    var pointsCmds = function (str, close) {
      var v = (str.match(/-?\d*\.?\d+(?:e[-+]?\d+)?/g) || []).map(Number), out = [];
      for (var i = 0; i + 1 < v.length; i += 2) out.push([i ? 'L' : 'M', v[i], v[i + 1]]);
      if (close && out.length) out.push(['Z']);
      return out;
    };
    var arcToC = function (x1, y1, rx, ry, phi, fa, fs, x2, y2) {
      if (!rx || !ry) return [['L', x2, y2]];
      rx = Math.abs(rx); ry = Math.abs(ry);
      var ph = phi * Math.PI / 180, cp = Math.cos(ph), sp = Math.sin(ph), dx = (x1 - x2) / 2, dy = (y1 - y2) / 2;
      var x1p = cp * dx + sp * dy, y1p = -sp * dx + cp * dy, lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry);
      if (lam > 1) { var sc = Math.sqrt(lam); rx *= sc; ry *= sc; }
      var sign = (fa ? 1 : 0) === (fs ? 1 : 0) ? -1 : 1;
      var nu = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p, de = rx * rx * y1p * y1p + ry * ry * x1p * x1p;
      var co = sign * Math.sqrt(Math.max(0, nu / de)); if (!isFinite(co)) co = 0;
      var cxp = co * rx * y1p / ry, cyp = -co * ry * x1p / rx;
      var cx = cp * cxp - sp * cyp + (x1 + x2) / 2, cy = sp * cxp + cp * cyp + (y1 + y2) / 2;
      var ang = function (ux, uy, vx, vy) { return Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy); };
      var ux = (x1p - cxp) / rx, uy = (y1p - cyp) / ry, vx = (-x1p - cxp) / rx, vy = (-y1p - cyp) / ry;
      var th1 = ang(1, 0, ux, uy), dth = ang(ux, uy, vx, vy);
      if (!fs && dth > 0) dth -= TAU; else if (fs && dth < 0) dth += TAU;
      var segs = Math.max(1, Math.ceil(Math.abs(dth) / (Math.PI / 2 + 0.001))), d = dth / segs, t = 4 / 3 * Math.tan(d / 4), out = [];
      var tf = function (p) { var X = p[0] * rx, Y = p[1] * ry; return [cp * X - sp * Y + cx, sp * X + cp * Y + cy]; };
      for (var i = 0; i < segs; i++) {
        var a1 = th1 + i * d, a2 = a1 + d, c1 = Math.cos(a1), s1 = Math.sin(a1), c2 = Math.cos(a2), s2 = Math.sin(a2);
        var q1 = tf([c1 - t * s1, s1 + t * c1]), q2 = tf([c2 + t * s2, s2 - t * c2]), q3 = tf([c2, s2]);
        out.push(['C', q1[0], q1[1], q2[0], q2[1], q3[0], q3[1]]);
      }
      return out;
    };
    var parsePath = function (d) {
      var tk = d.match(/[a-zA-Z]|-?\d*\.?\d+(?:e[-+]?\d+)?/g) || [], i = 0, out = [], cx = 0, cy = 0, sx = 0, sy = 0, cmd = 'M', lq = null;
      var nx = function () { return +tk[i++]; };
      while (i < tk.length) {
        if (/[a-zA-Z]/.test(tk[i])) cmd = tk[i++];
        var rel = cmd === cmd.toLowerCase(), C = cmd.toUpperCase(), x, y, x1, y1, x2, y2, keepQ = false;
        if (C === 'Z') { out.push(['Z']); cx = sx; cy = sy; lq = null; continue; }
        if (C === 'M') { x = nx(); y = nx(); if (rel) { x += cx; y += cy; } out.push(['M', x, y]); cx = sx = x; cy = sy = y; cmd = rel ? 'l' : 'L'; }
        else if (C === 'L') { x = nx(); y = nx(); if (rel) { x += cx; y += cy; } out.push(['L', x, y]); cx = x; cy = y; }
        else if (C === 'H') { x = nx(); if (rel) x += cx; out.push(['L', x, cy]); cx = x; }
        else if (C === 'V') { y = nx(); if (rel) y += cy; out.push(['L', cx, y]); cy = y; }
        else if (C === 'C') {
          x1 = nx(); y1 = nx(); x2 = nx(); y2 = nx(); x = nx(); y = nx();
          if (rel) { x1 += cx; y1 += cy; x2 += cx; y2 += cy; x += cx; y += cy; }
          out.push(['C', x1, y1, x2, y2, x, y]); cx = x; cy = y;
        } else if (C === 'Q' || C === 'T') {
          if (C === 'Q') { x1 = nx(); y1 = nx(); if (rel) { x1 += cx; y1 += cy; } }
          else { x1 = lq ? 2 * cx - lq[0] : cx; y1 = lq ? 2 * cy - lq[1] : cy; }
          x = nx(); y = nx(); if (rel) { x += cx; y += cy; }
          out.push(['C', cx + 2 / 3 * (x1 - cx), cy + 2 / 3 * (y1 - cy), x + 2 / 3 * (x1 - x), y + 2 / 3 * (y1 - y), x, y]);
          lq = [x1, y1]; keepQ = true; cx = x; cy = y;
        } else if (C === 'A') {
          var rx = nx(), ry = nx(), rot = nx(), fa = nx(), fs = nx(); x = nx(); y = nx();
          if (rel) { x += cx; y += cy; }
          arcToC(cx, cy, rx, ry, rot, fa, fs, x, y).forEach(function (s) { out.push(s); });
          cx = x; cy = y;
        } else { i++; }
        if (!keepQ) lq = null;
      }
      return out;
    };
    var pathStr = function (cmds, M) {
      var parts = ['n'], line = 'n', i, s, p, q, r;
      var add = function (t) { if (line.length + t.length > 180) { parts.push('\n'); line = ''; } parts.push(t); line += t + ' '; };
      for (i = 0; i < cmds.length; i++) {
        s = cmds[i];
        if (s[0] === 'M' || s[0] === 'L') { p = TP(M, s[1], s[2]); add(N(p[0]) + ' ' + N(p[1]) + ' ' + (s[0] === 'M' ? 'm' : 'l')); }
        else if (s[0] === 'C') { p = TP(M, s[1], s[2]); q = TP(M, s[3], s[4]); r = TP(M, s[5], s[6]); add(N(p[0]) + ' ' + N(p[1]) + ' ' + N(q[0]) + ' ' + N(q[1]) + ' ' + N(r[0]) + ' ' + N(r[1]) + ' c'); }
        else add('h');
      }
      return parts.join(' ').replace(/ \n /g, '\n');
    };
    var bbox = function (cmds) {
      var x0 = 1e18, y0 = 1e18, x1 = -1e18, y1 = -1e18;
      cmds.forEach(function (s) { for (var i = 1; i + 1 < s.length; i += 2) { x0 = Math.min(x0, s[i]); x1 = Math.max(x1, s[i]); y0 = Math.min(y0, s[i + 1]); y1 = Math.max(y1, s[i + 1]); } });
      return { x: x0, y: y0, w: Math.max(1e-6, x1 - x0), h: Math.max(1e-6, y1 - y0) };
    };
    var stopAt = function (stops, t) {
      var a = stops[0], b = stops[stops.length - 1], i;
      if (t <= a.o) return { c: a.c, a: a.a };
      if (t >= b.o) return { c: b.c, a: b.a };
      for (i = 0; i < stops.length - 1; i++) {
        if (t >= stops[i].o && t <= stops[i + 1].o) {
          var u = (t - stops[i].o) / Math.max(1e-9, stops[i + 1].o - stops[i].o), p = stops[i], q = stops[i + 1];
          return { c: [p.c[0] + (q.c[0] - p.c[0]) * u, p.c[1] + (q.c[1] - p.c[1]) * u, p.c[2] + (q.c[2] - p.c[2]) * u], a: p.a + (q.a - p.a) * u };
        }
      }
      return { c: b.c, a: b.a };
    };

    var inherit = function (P, a) {
      var s = {};
      for (var k in P) s[k] = P[k];
      if (a.fill != null) s.fill = a.fill;
      if (a.stroke != null) s.stroke = a.stroke;
      if (a['stroke-width'] != null) s.sw = +a['stroke-width'];
      if (a['fill-opacity'] != null) s.fo = +a['fill-opacity'];
      if (a['stroke-opacity'] != null) s.so = +a['stroke-opacity'];
      if (a.opacity != null) s.op = P.op * +a.opacity;
      if (a['stroke-linecap']) s.cap = a['stroke-linecap'];
      if (a['stroke-linejoin']) s.join = a['stroke-linejoin'];
      if (a['fill-rule']) s.fr = a['fill-rule'];
      if (a.transform) s.M = mmul(P.M, parseTransform(a.transform));
      return s;
    };

    var draw;
    var fillShape = function (cmds, s) {
      var url = /^url\(#([^)]+)\)$/.exec(s.fill || '');
      if (url) {
        var g = defsGrad[url[1]], pt = defsPat[url[1]], bb = bbox(cmds), i, j;
        if (pt) {
          for (i = Math.floor(bb.x / pt.w); i * pt.w < bb.x + bb.w; i++) for (j = Math.floor(bb.y / pt.h); j * pt.h < bb.y + bb.h; j++) {
            var base = { M: mmul(s.M, [1, 0, 0, 1, i * pt.w, j * pt.h]), fill: 'black', stroke: 'none', sw: 1, fo: 1, so: 1, op: s.op, cap: 'butt', join: 'miter', fr: 'nonzero' };
            pt.ch.forEach(function (ch) { draw(ch.tag, ch.a, inherit(base, ch.a)); });
          }
        } else if (g && g.stops.length) {
          var A = g.a, uso = A.gradientUnits === 'userSpaceOnUse', k, K;
          ps.push('gsave\n' + pathStr(cmds, s.M) + ' clip');
          if (g.type === 'linearGradient') {
            var gx1 = num(A.x1, 0), gy1 = num(A.y1, 0), gx2 = num(A.x2, 1), gy2 = num(A.y2, 0);
            if (!uso) { gx1 = bb.x + gx1 * bb.w; gx2 = bb.x + gx2 * bb.w; gy1 = bb.y + gy1 * bb.h; gy2 = bb.y + gy2 * bb.h; }
            var L = Math.hypot(gx2 - gx1, gy2 - gy1) || 1, ux = (gx2 - gx1) / L, uy = (gy2 - gy1) / L, nx = -uy, ny = ux, E = bb.w + bb.h + L;
            K = Math.min(140, Math.max(64, (g.stops.length - 1) * 6));
            for (k = 0; k < K; k++) {
              var t0 = k / K, t1 = Math.min(1, (k + 1) / K + 0.004), sc = stopAt(g.stops, (k + 0.5) / K);
              var Pq = [[gx1 + ux * L * t0 + nx * E, gy1 + uy * L * t0 + ny * E], [gx1 + ux * L * t1 + nx * E, gy1 + uy * L * t1 + ny * E], [gx1 + ux * L * t1 - nx * E, gy1 + uy * L * t1 - ny * E], [gx1 + ux * L * t0 - nx * E, gy1 + uy * L * t0 - ny * E]];
              if (k === 0) { Pq[0] = [Pq[0][0] - ux * E, Pq[0][1] - uy * E]; Pq[3] = [Pq[3][0] - ux * E, Pq[3][1] - uy * E]; }
              if (k === K - 1) { Pq[1] = [Pq[1][0] + ux * E, Pq[1][1] + uy * E]; Pq[2] = [Pq[2][0] + ux * E, Pq[2][1] + uy * E]; }
              ps.push(rgbk(flat(sc.c, sc.a * s.fo * s.op)) + ' ' + pathStr([['M', Pq[0][0], Pq[0][1]], ['L', Pq[1][0], Pq[1][1]], ['L', Pq[2][0], Pq[2][1]], ['L', Pq[3][0], Pq[3][1]], ['Z']], s.M) + ' f');
            }
          } else {
            var gcx = num(A.cx, 0.5), gcy = num(A.cy, 0.5), gr = num(A.r, 0.5);
            if (!uso) { gcx = bb.x + gcx * bb.w; gcy = bb.y + gcy * bb.h; gr = gr * Math.max(bb.w, bb.h); }
            K = 36;
            for (k = 0; k < K; k++) {
              var fr = 1 - k / K, sr = stopAt(g.stops, fr - 0.5 / K), al = sr.a * s.fo * s.op;
              if (al < 0.035) continue;
              ps.push(rgbk(flat(sr.c, al)) + ' ' + pathStr(ellipseCmds(gcx, gcy, gr * fr, gr * fr), s.M) + ' f');
            }
          }
          ps.push('grestore');
        }
        return;
      }
      var fc = parseColor(s.fill);
      if (fc) ps.push(rgbk(flat(fc, s.fo * s.op)) + ' ' + pathStr(cmds, s.M) + (s.fr === 'evenodd' ? ' e' : ' f'));
    };
    draw = function (tag, a, s) {
      var cmds = null;
      if (tag === 'rect') { var rx = num(a.rx, 0); cmds = rectCmds(num(a.x), num(a.y), num(a.width), num(a.height), rx); }
      else if (tag === 'circle') cmds = ellipseCmds(num(a.cx), num(a.cy), num(a.r), num(a.r));
      else if (tag === 'ellipse') cmds = ellipseCmds(num(a.cx), num(a.cy), num(a.rx), num(a.ry));
      else if (tag === 'line') cmds = [['M', num(a.x1), num(a.y1)], ['L', num(a.x2), num(a.y2)]];
      else if (tag === 'polygon') cmds = pointsCmds(a.points || '', true);
      else if (tag === 'polyline') cmds = pointsCmds(a.points || '', false);
      else if (tag === 'path') cmds = parsePath(a.d || '');
      if (!cmds || !cmds.length) return;
      if (tag !== 'line' && tag !== 'polyline') fillShape(cmds, s);
      else if (s.fill && s.fill !== 'none' && tag === 'polyline') fillShape(cmds, s);
      var sc = parseColor(s.stroke);
      if (sc && s.sw > 0) {
        var M = s.M, sw = s.sw * Math.sqrt(Math.abs(M[0] * M[3] - M[1] * M[2]));
        ps.push(rgbk(flat(sc, s.so * s.op)) + ' ' + N(sw) + ' w ' + (s.cap === 'round' ? 1 : s.cap === 'square' ? 2 : 0) + ' setlinecap ' + (s.join === 'round' ? 1 : s.join === 'bevel' ? 2 : 0) + ' setlinejoin\n' + pathStr(cmds, M) + ' s');
      }
    };

    var base0 = { M: [1, 0, 0, -1, 0, H], fill: 'black', stroke: 'none', sw: 1, fo: 1, so: 1, op: 1, cap: 'butt', join: 'miter', fr: 'nonzero' };
    var re = /<(\/?)([a-zA-Z]+)((?:\s+[\w:-]+="[^"]*")*)\s*(\/?)>/g, m, stack = [], st = base0, inDefs = false, curPat = null, curGrad = null, curClip = null, defsClip = {}, clipStack = [];
    while ((m = re.exec(svg))) {
      var close = m[1] === '/', tag = m[2], a = close ? {} : attrsOf(m[3]), selfc = m[4] === '/';
      if (tag === 'defs') { inDefs = !close; continue; }
      if (inDefs) {
        if (tag === 'clipPath') { if (!close) { curClip = defsClip[a.id] = []; if (selfc) curClip = null; } else curClip = null; continue; }
        if (curClip && !close) { var cc = tag === 'rect' ? rectCmds(num(a.x), num(a.y), num(a.width), num(a.height), num(a.rx, 0)) : tag === 'path' ? parsePath(a.d || '') : tag === 'circle' ? ellipseCmds(num(a.cx), num(a.cy), num(a.r), num(a.r)) : null; if (cc) curClip.push.apply(curClip, cc); continue; }
        if (tag === 'pattern') { if (!close) { curPat = { w: num(a.width, 1), h: num(a.height, 1), ch: [] }; defsPat[a.id] = curPat; if (selfc) curPat = null; } else curPat = null; }
        else if (tag === 'radialGradient' || tag === 'linearGradient') { if (!close) { curGrad = { type: tag, a: a, stops: [] }; defsGrad[a.id] = curGrad; if (selfc) curGrad = null; } else curGrad = null; }
        else if (tag === 'stop' && curGrad) {
          var off = String(a.offset || '0'), o = off.indexOf('%') >= 0 ? parseFloat(off) / 100 : parseFloat(off);
          curGrad.stops.push({ o: o, c: parseColor(a['stop-color']) || [0, 0, 0], a: a['stop-opacity'] != null ? +a['stop-opacity'] : 1 });
        } else if (curPat && !close) curPat.ch.push({ tag: tag, a: a });
        continue;
      }
      if (tag === 'svg') continue;
      if (tag === 'g') {
        if (close) { st = stack.pop() || base0; if (clipStack.pop()) ps.push('grestore'); }
        else {
          stack.push(st); st = inherit(st, a);
          var cu = a['clip-path'] ? /url\(#([^)]+)\)/.exec(a['clip-path']) : null, cl = cu && defsClip[cu[1]] && defsClip[cu[1]].length ? defsClip[cu[1]] : null;
          if (cl) ps.push('gsave\n' + pathStr(cl, st.M) + ' clip n');
          if (selfc) { st = stack.pop(); if (cl) ps.push('grestore'); } else clipStack.push(!!cl);
        }
        continue;
      }
      if (close) continue;
      draw(tag, a, inherit(st, a));
    }
    var head = '%!PS-Adobe-3.0 EPSF-3.0\n%%Creator: Vector BG Studio\n%%Title: ' + String(title || 'background').replace(/[^\w .-]/g, '') + '\n' +
      '%%BoundingBox: 0 0 ' + Math.ceil(W) + ' ' + Math.ceil(H) + '\n%%HiResBoundingBox: 0 0 ' + N(W) + ' ' + N(H) + '\n%%LanguageLevel: 2\n%%EndComments\n' +
      '%%BeginProlog\n/n{newpath}bind def /m{moveto}bind def /l{lineto}bind def /c{curveto}bind def /h{closepath}bind def\n' +
      '/k{setrgbcolor}bind def /f{fill}bind def /e{eofill}bind def /s{stroke}bind def /w{setlinewidth}bind def\n%%EndProlog\n%%Page: 1 1\ngsave\n' +
      'n 0 0 m ' + N(W) + ' 0 l ' + N(W) + ' ' + N(H) + ' l 0 ' + N(H) + ' l h clip n\n';
    return head + ps.join('\n') + '\ngrestore\nshowpage\n%%EOF\n';
  }

  /* per-pattern default tuning: stronger colours and line weights so every pattern reads well at first sight */
  var TUNE = {
    moirelines: { def: { sw: 1.5 } },
    hatch: { cols: ['#ffffff', '#1f2a36', '#e0202c'], def: { sw: 1.8 } },
    zigzaglines: { cols: ['#fff7f2', '#e0202c', '#ff9a1f'], def: { sw: 3 } },
    roses: { cols: ['#fbf8ff', '#5b1fa6', '#ff4fa3'], def: { sw: 1.6, size: 1.05, turn: 6, curves: 22 } },
    moirerings: { def: { sw: 1.4 } },
    ripples: { cols: ['#ffffff', '#0a6fb0', '#00a8f0', '#7a5af8'], def: { sw: 2.6 } },
    sunflower: { cols: ['#0e1b3d', '#f5b700', '#ff5e62'], def: { size: 0.95 } },
    celllines: { cols: ['#04293a', '#64e6d9', '#ff9966'], def: { sw: 2.4 } },
    lattice: { def: { sw: 2.6, cols: 12 } },
    starfield: { def: { size: 1.9, count: 560 } },
    dashrain: { cols: ['#ffffff', '#0a6fb0', '#00a8f0', '#7fd4f8'], def: { sw: 3.2 } },
    crossgrid: { cols: ['#ffffff', '#111111', '#e0202c'] },
    isogrid: { cols: ['#f4fffb', '#0c7a64', '#17c3a0'], def: { sw: 1.6 } },
    gradstripes: { def: { lift: 0.14 } },
    warpgrid: { def: { sw: 1.8 } },
    pinstripes: { def: { sw: 2 } }
  };
  PATTERNS.forEach(function (p) {
    var t = TUNE[p.id]; if (!t) return;
    if (t.cols) p.defCols = t.cols;
    if (t.def) p.params.forEach(function (r) { if (t.def[r.key] != null) r.def = t.def[r.key]; });
  });

  function catalog() {
    return PATTERNS.map(function (p) {
      return {
        id: p.id, name: p.name, cat: p.cat, colors: p.colors,
        params: p.params.map(function (r) {
          var t = r.type === 'toggle';
          return { key: r.key, min: t ? 0 : r.min, max: t ? 1 : r.max, step: t ? 1 : r.step, def: r.def };
        })
      };
    });
  }

  return {
    catalog: catalog, hueShift: hueShift, toEPS: toEPS,
    designAt: designAt, designCount: designCount, designNumber: designNumber, variation: variation, hash: cyrb53,
    moods: MOODS, libraryPalettes: LIB_PALETTES, VARIATIONS_PER_DESIGN: VARIATIONS_PER_DESIGN,
    version: '1.5.0', palettesFor: palsFor, darkPalettes: DARK_PALETTES,
    patterns: PATTERNS, byId: byId, palettes: PALETTES,
    defaults: defaults, defaultColors: defaultColors,
    build: build, generate: generate, toFile: toFile, randomOptions: randomOptions
  };
});
