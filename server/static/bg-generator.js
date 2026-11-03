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
    var q = l < 0.5 ? l * (1 + sat) : l + sat - l * sat, p2 = 2 * l - q;
    var k = function (t) {
      t = (t + 1) % 1;
      if (t < 1 / 6) return p2 + (q - p2) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p2 + (q - p2) * (2 / 3 - t) * 6;
      return p2;
    };
    return rgb2hex(k(h + 1 / 3) * 255, k(h) * 255, k(h - 1 / 3) * 255);
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

  var CATS = {
    burst: 'Radial', rings: 'Radial', spiral: 'Radial', rosette: 'Radial', guilloche: 'Radial', kaleido: 'Radial',
    scales: 'Tiles', hex: 'Tiles', cubes: 'Tiles', pinwheel: 'Tiles', dots: 'Tiles', lowpoly: 'Tiles', argyle: 'Tiles',
    truchet: 'Tiles', stars: 'Tiles', mosaic: 'Tiles', bricks: 'Tiles', honeycomb: 'Tiles', bauhaus: 'Tiles', plus: 'Tiles',
    contour: 'Lines', plaid: 'Lines', ribbon: 'Lines', chevron: 'Lines', stripes: 'Lines', grid: 'Lines', wavylines: 'Lines',
    bars: 'Soft', layers: 'Soft', confetti: 'Soft', halftone: 'Soft', blobs: 'Soft', orbs: 'Soft', bubbles: 'Soft'
  };
  PATTERNS.forEach(function (p) { p.cat = CATS[p.id] || 'Soft'; });

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
    var pal = PALETTES[Math.floor(rnd() * PALETTES.length)].c.slice();
    if (rnd() > 0.7) { var t = pal[1]; pal[1] = pal[2]; pal[2] = t; }
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
      do { pal = LIB_PALETTES[(m * 5 + patIdx * 7 + tries) % LIB_PALETTES.length]; tries++; }
      while (tries < LIB_PALETTES.length && !contrastOk(pal.c, 0.22));
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
    catalog: catalog, hueShift: hueShift,
    designAt: designAt, designCount: designCount, designNumber: designNumber, variation: variation, hash: cyrb53,
    moods: MOODS, libraryPalettes: LIB_PALETTES, VARIATIONS_PER_DESIGN: VARIATIONS_PER_DESIGN,
    patterns: PATTERNS, byId: byId, palettes: PALETTES,
    defaults: defaults, defaultColors: defaultColors,
    build: build, generate: generate, toFile: toFile, randomOptions: randomOptions
  };
});
