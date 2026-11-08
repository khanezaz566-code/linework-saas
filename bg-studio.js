/*
 * bg-studio.js  -  BG Studio UI module (needs bg-generator.js loaded first).
 *
 *   <script src="bg-generator.js"></script>
 *   <script src="bg-studio.js"></script>
 *   <script>
 *     var studio = BGStudio.mount(document.getElementById('bgstudio-root'), {
 *       theme: { accent: '#00f5a0' },        // optional, see THEME below
 *       title: 'BG Studio',                  // false hides the header
 *       matchReference: async function (info) { ... }   // optional AI hook, see below
 *     });
 *     // when the user leaves the page:
 *     studio.destroy();
 *   </script>
 *
 * The UI lives in a Shadow DOM, so the host app's CSS cannot restyle it and its CSS cannot
 * leak out. It adds no global CSS, no global variables except window.BGStudio, and the only
 * document-level listener is "paste", which destroy() removes.
 *
 * THEME (all optional). Defaults match a dark slate app with a mint accent:
 *   bg, panel, panel2, line, fg, soft, muted, accent, accentFg, font
 * You can also set the CSS variables --bgs-accent, --bgs-panel ... on the host element.
 *
 * AI HOOK (optional). Without it, a pasted reference only copies its colours.
 *   matchReference({ file, palette, prompt, catalog })  ->  Promise of
 *   { matches: [ { id, score, why, params, colors } ] }  (object or JSON string)
 *   "prompt" is ready to send to any vision model together with "file".
 */
(function (root) {
  'use strict';

  var CSS = [
    /* all:initial stops inherited host styles (letter-spacing, text-transform ...) leaking in; font-family still follows the app. */
    ':host{all:initial;display:block;font-family:var(--bgs-font,inherit);font-size:14px;line-height:1.45;color:var(--bgs-fg,#e2e8f0);}',
    '*{box-sizing:border-box;}',
    '[hidden]{display:none!important;}',
    '.root{--bg:var(--bgs-bg,transparent);--panel:var(--bgs-panel,#0a1219);--panel2:var(--bgs-panel2,#0e1a24);--line:var(--bgs-line,#1b2a38);',
    '--fg:var(--bgs-fg,#e2e8f0);--soft:var(--bgs-soft,#94a3b8);--muted:var(--bgs-muted,#64748b);--accent:var(--bgs-accent,#00f5a0);--accent-fg:var(--bgs-accent-fg,#03140e);',
    '--chk-a:#121d27;--chk-b:#0c151c;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--fg);background:var(--bg);}',
    'h1{font-size:24px;font-weight:700;margin:0;letter-spacing:-.01em;}',
    'h2{font-size:11px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);margin:0;}',
    '.head{display:flex;align-items:baseline;justify-content:space-between;gap:8px 24px;flex-wrap:wrap;margin-bottom:16px;}',
    '.sub{margin:0;color:var(--soft);max-width:64ch;font-size:13px;}',
    '.app{display:grid;grid-template-columns:minmax(0,1fr);gap:18px;}',
    '.wide .app{grid-template-columns:360px minmax(0,1fr);align-items:start;}',
    '.wide .panel{grid-column:1;grid-row:1;}.wide .stage{grid-column:2;grid-row:1;}',
    '.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;display:flex;flex-direction:column;min-width:0;overflow:hidden;}',
    '.sec{padding:14px;border-top:1px solid var(--line);display:flex;flex-direction:column;gap:10px;min-width:0;}',
    '.sec:first-child{border-top:0;}',
    '.pat-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-height:440px;overflow-y:auto;padding-right:2px;scrollbar-width:thin;scrollbar-color:var(--line) transparent;}',
    '.pat,.famb{appearance:none;border:1px solid var(--line);background:var(--panel2);border-radius:8px;padding:4px 4px 6px;cursor:pointer;color:var(--fg);font:inherit;font-size:11.5px;text-align:left;display:flex;flex-direction:column;gap:5px;min-width:0;}',
    '.pat img,.famb img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover;border-radius:5px;display:block;background:var(--chk-b);}',
    '.pat span,.famb span{padding:0 2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
    '.pat[aria-pressed="true"],.famb[aria-pressed="true"],.match[aria-pressed="true"]{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent);}',
    '.fam{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;}.famb{font-size:11px;}',
    '.chips{display:flex;flex-wrap:wrap;gap:6px;}',
    '.chip{appearance:none;font:inherit;font-size:12px;font-family:var(--mono);color:var(--soft);background:var(--panel2);border:1px solid var(--line);border-radius:999px;padding:4px 10px;cursor:pointer;}',
    '.chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--accent-fg);font-weight:600;}',
    '.ctl{display:flex;flex-direction:column;gap:4px;}.ctl-head{display:flex;justify-content:space-between;gap:8px;}',
    '.ctl label{font-size:12.5px;color:var(--soft);}',
    '.ctl output{font-family:var(--mono);font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;}',
    'input[type="range"]{width:100%;accent-color:var(--accent);margin:0;}',
    '.tog{display:flex;align-items:center;gap:8px;font-size:12.5px;cursor:pointer;color:var(--soft);}',
    '.tog input{accent-color:var(--accent);width:15px;height:15px;margin:0;}',
    '.colors{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px;}',
    '.col{display:flex;flex-direction:column;gap:4px;font-size:11.5px;color:var(--muted);min-width:0;}',
    '.col input[type="color"]{width:100%;height:30px;padding:0;border:1px solid var(--line);border-radius:6px;background:var(--panel2);cursor:pointer;}',
    '.col code{font-family:var(--mono);font-size:11px;color:var(--soft);}',
    '.pal{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;}',
    '.pal button{appearance:none;border:1px solid var(--line);border-radius:6px;padding:0;height:26px;display:flex;overflow:hidden;cursor:pointer;background:var(--panel2);}',
    '.pal button i{flex:1;display:block;}',
    '.btn{appearance:none;font:inherit;font-size:13px;font-weight:600;border:1px solid var(--line);background:var(--panel2);color:var(--fg);border-radius:8px;padding:8px 13px;cursor:pointer;}',
    '.btn:hover{border-color:var(--muted);}',
    '.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-fg);}',
    '.btn.primary:hover{filter:brightness(1.08);}',
    ':focus-visible{outline:2px solid var(--accent);outline-offset:2px;}',
    '.stage{display:flex;flex-direction:column;gap:12px;min-width:0;}',
    '.stage-head{display:flex;justify-content:space-between;align-items:center;gap:10px 16px;flex-wrap:wrap;}',
    '.meta{font-family:var(--mono);font-size:12px;color:var(--muted);display:flex;gap:6px 14px;flex-wrap:wrap;}',
    '.actions,.export{display:flex;gap:8px;flex-wrap:wrap;align-items:center;}',
    '.board{border:1px solid var(--line);border-radius:10px;overflow:hidden;line-height:0;background-color:var(--chk-a);',
    'background-image:conic-gradient(var(--chk-b) 25%,transparent 0 50%,var(--chk-b) 0 75%,transparent 0);background-size:20px 20px;}',
    '.board img{width:100%;height:auto;display:block;max-height:74vh;object-fit:contain;margin:0 auto;}',
    '.stats{font-family:var(--mono);font-size:12px;color:var(--muted);font-variant-numeric:tabular-nums;}',
    '.hint{margin:0;font-size:12.5px;color:var(--muted);max-width:80ch;}',
    '.toast{font-size:12.5px;color:var(--accent);min-height:1.2em;}',
    '#code{width:100%;height:150px;font-family:var(--mono);font-size:11.5px;background:var(--panel);color:var(--soft);border:1px solid var(--line);border-radius:8px;padding:8px;resize:vertical;}',
    '.vars-head{display:flex;justify-content:space-between;align-items:center;gap:8px 12px;flex-wrap:wrap;margin:6px 0 8px;}',
    '.var-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;}',
    '.var{appearance:none;padding:0;border:1px solid var(--line);border-radius:8px;overflow:hidden;cursor:pointer;background:var(--chk-b);line-height:0;}',
    '.var img{width:100%;height:auto;display:block;}.var:hover{border-color:var(--accent);}',
    '.libnav{display:flex;gap:6px;align-items:center;flex-wrap:wrap;}',
    '.libnav input{width:74px;font:inherit;font-family:var(--mono);font-size:13px;padding:7px 8px;border:1px solid var(--line);border-radius:8px;background:var(--panel2);color:var(--fg);}',
    '.libnav .of{font-family:var(--mono);font-size:12px;color:var(--muted);}',
    '.fine{font-size:12px;color:var(--muted);margin:0;}',
    '.drop{border:1px dashed var(--muted);border-radius:10px;padding:12px;display:flex;flex-direction:column;gap:8px;align-items:flex-start;background:var(--panel2);}',
    '.drop.over{border-color:var(--accent);}.drop p{margin:0;font-size:12.5px;color:var(--soft);}',
    '.drop kbd{font-family:var(--mono);font-size:11px;border:1px solid var(--line);border-radius:4px;padding:0 4px;background:var(--panel);color:var(--fg);}',
    '.ref-row{display:flex;gap:10px;align-items:flex-start;}',
    '.ref-row img{width:112px;height:72px;object-fit:cover;border:1px solid var(--line);border-radius:6px;background:var(--chk-b);flex:none;}',
    '.swatches{display:flex;gap:4px;flex-wrap:wrap;}.swatches i{width:22px;height:22px;border-radius:5px;border:1px solid var(--line);display:block;}',
    '.status{font-size:12.5px;color:var(--soft);min-height:1.3em;}',
    '.matches{display:flex;flex-direction:column;gap:6px;}',
    '.match{appearance:none;text-align:left;font:inherit;color:var(--fg);background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:5px;display:flex;gap:9px;cursor:pointer;align-items:center;}',
    '.match img{width:84px;height:47px;object-fit:cover;border-radius:4px;flex:none;background:var(--chk-b);}',
    '.match b{font-weight:600;font-size:12.5px;}.match small{display:block;font-size:11.5px;color:var(--muted);line-height:1.3;}',
    '.err{padding:14px;border:1px solid #7f1d1d;border-radius:10px;color:#fecaca;background:#2a0f12;font-size:13px;}',
    '.pack-btn{background:linear-gradient(135deg,rgba(0,245,160,0.18),rgba(0,255,213,0.06));border:1.5px solid var(--accent);color:var(--accent);display:inline-flex;align-items:center;font-weight:700;transition:all .18s ease;box-shadow:0 0 12px rgba(0,245,160,0.15);cursor:pointer;}',
    '.pack-btn:hover{background:var(--accent);color:#050b0d;box-shadow:0 0 20px rgba(0,245,160,0.4);transform:translateY(-1px);}',
    '.pack-dock{position:fixed;bottom:20px;right:28px;z-index:9999;background:#080e14;border:1px solid #162636;border-radius:12px;box-shadow:0 14px 40px rgba(0,0,0,0.7),0 0 0 1px rgba(0,245,160,0.15);display:flex;flex-direction:column;width:340px;max-width:calc(100vw - 40px);overflow:hidden;backdrop-filter:blur(16px);font-family:inherit;}',
    '.pack-dock-bar{display:flex;align-items:center;gap:10px;padding:9px 13px;cursor:pointer;background:#0d1822;user-select:none;transition:background .15s;}',
    '.pack-dock-bar:hover{background:#11202e;}',
    '.pack-dock-icon{font-size:16px;}',
    '.pack-dock-title{font-size:12.5px;font-weight:700;color:var(--fg);flex:1;}',
    '.pack-dock-badge{background:var(--accent);color:#050b0d;font-family:var(--mono);font-size:11px;font-weight:800;border-radius:999px;padding:2px 8px;min-width:18px;text-align:center;}',
    '.pack-dock-badge.bump{transform:scale(1.25);transition:transform .15s ease;}',
    '.pack-quick-dl{appearance:none;border:none;background:var(--accent);color:#050b0d;font:inherit;font-size:11.5px;font-weight:700;padding:5px 10px;border-radius:6px;cursor:pointer;}',
    '.pack-quick-dl:hover{filter:brightness(1.1);}',
    '.pack-dock-arrow{background:transparent;border:none;color:var(--muted);font-size:11px;cursor:pointer;padding:2px 4px;transition:transform .2s;}',
    '.pack-dock.open .pack-dock-arrow{transform:rotate(180deg);}',
    '.pack-drawer{padding:12px;display:flex;flex-direction:column;gap:10px;border-top:1px solid #162636;max-height:420px;}',
    '.pack-drawer-head{display:flex;justify-content:space-between;align-items:center;gap:8px;}',
    '.pack-drawer-title{font-size:12px;font-weight:700;color:var(--fg);}',
    '.pack-drawer-sub{font-size:11px;color:var(--muted);}',
        '.pack-fmt-switcher{display:inline-flex;background:#060d13;border:1px solid #182a3c;border-radius:6px;padding:2px;gap:2px;}',
    '.fmt-pill{appearance:none;background:transparent;border:none;color:var(--muted);font-family:var(--mono);font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:4px;cursor:pointer;transition:all .15s;}',
    '.fmt-pill:hover{color:var(--fg);}',
    '.fmt-pill.active{background:var(--accent);color:#050b0d;}',
    '.pack-fmt-box{display:flex;flex-direction:column;gap:6px;padding:8px 10px;background:#09121a;border:1px solid #142230;border-radius:8px;}',
    '.pack-fmt-title{font-family:var(--mono);font-size:10px;color:var(--muted);font-weight:700;letter-spacing:.05em;}',
    '.pack-fmt-options{display:grid;grid-template-columns:1fr 1fr;gap:6px;}',
    '.fmt-opt{display:flex;align-items:center;gap:6px;font-size:11.5px;color:var(--soft);cursor:pointer;padding:4px 6px;border-radius:6px;}',
    '.fmt-opt:hover{background:rgba(255,255,255,0.04);}',
    '.fmt-opt input{accent-color:var(--accent);margin:0;width:13px;height:13px;}',
    '.pack-fmt-label{font-family:var(--mono);font-size:10.5px;color:var(--muted);font-weight:700;}',
    '.pack-items{display:flex;flex-direction:column;gap:6px;max-height:200px;overflow-y:auto;padding-right:2px;}',
    '.pack-item{display:flex;align-items:center;gap:9px;padding:5px 8px;background:#0a131b;border:1px solid #152331;border-radius:6px;}',
    '.pack-thumb{width:44px;height:28px;object-fit:cover;border-radius:4px;border:1px solid #1a2a3a;background:#050a0f;flex:none;}',
    '.pack-meta{flex:1;min-width:0;display:flex;flex-direction:column;gap:1px;}',
    '.pack-name{font-size:11.5px;font-weight:600;color:var(--fg);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}',
    '.pack-dim{font-family:var(--mono);font-size:10px;color:var(--muted);}',
    '.pack-del{appearance:none;background:transparent;border:none;color:var(--muted);cursor:pointer;font-size:13px;padding:2px 5px;border-radius:4px;}',
    '.pack-del:hover{color:#ff6b6b;background:rgba(255,107,107,0.15);}',
    '.pack-empty{padding:14px;text-align:center;font-size:12px;color:var(--muted);}',
    '.pack-dl-all{appearance:none;font:inherit;width:100%;background:linear-gradient(135deg,var(--accent),#00e599);border:none;color:#050b0d;font-size:12.5px;font-weight:800;border-radius:8px;padding:9px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;box-shadow:0 0 16px rgba(0,245,160,0.25);}',
    '.pack-dl-all:hover{filter:brightness(1.08);transform:translateY(-1px);}'
  ].join('\n');

  var HTML = [
    '<div class="root" id="root">',
    '<header class="head" id="head"><h1 id="title"></h1><p class="sub" id="sub"></p></header>',
    '<div class="app">',
    '<section class="stage" aria-label="Artboard">',
    '<div class="stage-head"><div class="meta"><span id="m-design"></span><span id="m-size"></span><span id="m-fit"></span></div>',
    '<div class="actions"><button class="btn primary" id="btn-next" type="button">New variation</button><button class="btn" id="btn-shuffle" type="button">Shuffle everything</button></div></div>',
    '<div class="board"><img id="art" alt="Generated vector background"></div>',
    '<div class="export">',
    '<button class="btn primary" id="btn-svg" type="button">Download SVG</button>',
    '<button class="btn primary" id="btn-eps" type="button">Download EPS</button>',
    '<button class="btn" id="btn-png" type="button">Download PNG</button>',
    '<button class="btn" id="btn-copy" type="button">Copy SVG code</button>',
    '<button class="btn" id="btn-code" type="button">Show code</button>',
    '<button class="btn pack-btn" id="btn-add-pack" type="button" title="Add current design to ZIP bundle pack"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" style="vertical-align:middle;margin-right:4px;"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>+ Add to Pack</button>',
    '<span class="stats" id="stats"></span><span class="toast" id="toast" role="status"></span></div>',
    '<textarea id="code" hidden readonly spellcheck="false" aria-label="SVG source"></textarea>',
    '<p class="hint">SVG, EPS and PNG download straight to your computer. EPS has no transparency, so opacity becomes solid colour and gradients become fine bands. Everything stays editable vector shapes.</p>',
    '<div><div class="vars-head"><h2>Variations of this design</h2><div class="chips" id="strength"></div><button class="btn" id="btn-add-all-vars" type="button" title="Add all 8 variations to ZIP pack">+ Add 8 to Pack</button><button class="btn" id="btn-vars" type="button">Show 8 more</button></div>',
    '<div class="var-grid" id="vars"></div></div>',
    '</section>',
    '<aside class="panel" aria-label="Controls">',
    '<div class="sec"><h2>Artboard</h2><div class="chips" id="sizes"></div>',
    '<label class="tog"><input type="checkbox" id="transparent"><span>Transparent background</span></label>',
    '<div class="ctl"><div class="ctl-head"><label for="rot">Rotate pattern</label><output id="rot-o">0°</output></div><input type="range" id="rot" min="-90" max="90" step="5" value="0"></div></div>',
    '<div class="sec"><h2>Shape</h2><div id="params" style="display:flex;flex-direction:column;gap:10px"></div></div>',
    '<div class="sec"><h2>Colours</h2><div class="colors" id="colors"></div>',
    '<div class="ctl"><div class="ctl-head"><label for="hue">Hue shift</label><output id="hue-o">0°</output></div><input type="range" id="hue" min="-180" max="180" step="5" value="0"></div>',
    '<h2 style="margin-top:4px">Palettes</h2><div class="pal" id="pals"></div></div>',
    '<div class="sec"><h2>Pattern family</h2><div class="chips" id="cats"></div><div class="pat-grid" id="pats"></div></div>',
    '<div class="sec"><h2>Design library</h2>',
    '<div class="libnav"><button class="btn" id="lib-prev" type="button" aria-label="Previous design">←</button>',
    '<input id="lib-no" type="number" min="1" value="1" aria-label="Design number"><span class="of" id="lib-of"></span>',
    '<button class="btn" id="lib-next" type="button" aria-label="Next design">→</button><button class="btn" id="lib-rand" type="button">Random</button></div>',
    '<div class="fam" id="fam"></div><p class="fine" id="lib-note"></p></div>',
    '<div class="sec"><h2>Match a reference</h2>',
    '<div class="drop" id="drop"><p>Paste a screenshot with <kbd>Ctrl</kbd>+<kbd>V</kbd>, drop an image here, or choose a file. The closest templates are found and the colours are copied.</p>',
    '<button class="btn" id="btn-file" type="button">Choose image</button><input type="file" id="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden></div>',
    '<div class="ref-row" id="ref-row" hidden><img id="ref-img" alt="Your reference"><div style="min-width:0;display:flex;flex-direction:column;gap:6px"><div class="swatches" id="ref-sw"></div><div class="status" id="ref-status" role="status"></div></div></div>',
    '<div class="matches" id="matches"></div>',
    '<label class="tog" id="diverge-row" hidden><input type="checkbox" id="diverge" checked><span>Variations differ from the reference (new hue and layout)</span></label></div>',
        '<div class="pack-dock" id="pack-dock">',
    '<div class="pack-dock-bar" id="pack-toggle"><span class="pack-dock-icon">📦</span><span class="pack-dock-title">Collection Pack</span><span class="pack-dock-badge" id="pack-count">0</span><div class="pack-fmt-switcher" id="dock-fmt-switcher"><button class="fmt-pill active" data-fmt="svg" type="button" title="Download only SVG files">SVG</button><button class="fmt-pill" data-fmt="eps" type="button" title="Download only EPS files">EPS</button><button class="fmt-pill" data-fmt="both" type="button" title="Download both SVG and EPS">Both</button></div><button class="pack-quick-dl" id="btn-quick-dl" type="button" style="display:none;">Download SVG ZIP</button><button class="pack-dock-arrow" id="pack-expand" type="button" aria-label="Expand Pack">▲</button></div>',
    '<div class="pack-drawer" id="pack-drawer" hidden>',
    '<div class="pack-drawer-head"><div><span class="pack-drawer-title">Collected Backgrounds</span> <span class="pack-drawer-sub" id="pack-count-sub">(0)</span></div><button class="btn" id="btn-clear-pack" type="button" style="padding:3px 8px;font-size:11px;">Clear</button></div>',
    '<div class="pack-fmt-box"><div class="pack-fmt-title">SELECT FORMAT FOR ZIP:</div><div class="pack-fmt-options"><label class="fmt-opt"><input type="radio" name="pack-fmt" value="svg" checked> <span><strong>SVG Only</strong> (.svg vector)</span></label><label class="fmt-opt"><input type="radio" name="pack-fmt" value="eps"> <span><strong>EPS Only</strong> (.eps vector)</span></label><label class="fmt-opt"><input type="radio" name="pack-fmt" value="both"> <span><strong>Both</strong> (SVG + EPS)</span></label><label class="fmt-opt"><input type="radio" name="pack-fmt" value="png"> <span><strong>PNG Only</strong> (.png image)</span></label></div></div>',
    '<div class="pack-items" id="pack-items"><div class="pack-empty">Your pack is empty.<br>Click "+ Add to Pack" on any design!</div></div>',
    '<button class="pack-dl-all" id="btn-pack-dl-all" type="button" disabled>⬇ Download ZIP (0 SVGs)</button>',
    '</div></div>',
    '</aside></div></div>'
  ].join('');

  var THEME_VARS = { bg: '--bgs-bg', panel: '--bgs-panel', panel2: '--bgs-panel2', line: '--bgs-line', fg: '--bgs-fg', soft: '--bgs-soft', muted: '--bgs-muted', accent: '--bgs-accent', accentFg: '--bgs-accent-fg', font: '--bgs-font' };

  var SIZES = [
    { l: '16:9', w: 1920, h: 1080 }, { l: '4K', w: 3840, h: 2160 }, { l: '1:1', w: 2000, h: 2000 }, { l: '4:3', w: 2400, h: 1800 },
    { l: '3:2', w: 2400, h: 1600 }, { l: '9:16', w: 1080, h: 1920 }, { l: 'A4', w: 2480, h: 3508 }
  ];
  var STRENGTHS = [['subtle', 'Subtle'], ['medium', 'Medium'], ['wild', 'Wild']];

  function mount(target, options) {
    options = options || {};
    var host = typeof target === 'string' ? document.querySelector(target) : target;
    if (!host) throw new Error('BGStudio.mount: container not found');
    if (host.__bgstudio) host.__bgstudio.destroy();
    var G = root.BGGen;
    var sr = host.shadowRoot || host.attachShadow({ mode: 'open' });
    if (!G) {
      sr.innerHTML = '<style>' + CSS + '</style><div class="root"><div class="err">BG Studio could not start: load bg-generator.js before bg-studio.js.</div></div>';
      return { destroy: function () { sr.innerHTML = ''; } };
    }
    sr.innerHTML = '<style>' + CSS + '</style>' + HTML;
    var theme = options.theme || {};
    Object.keys(THEME_VARS).forEach(function (k) { if (theme[k]) host.style.setProperty(THEME_VARS[k], theme[k]); });

    var $ = function (s) { return sr.querySelector(s); };
    var $$ = function (s) { return sr.querySelectorAll(s); };
    var TOTAL = G.designCount(), VPD = G.VARIATIONS_PER_DESIGN;
    var CATS = ['All'];
    G.patterns.forEach(function (p) { if (CATS.indexOf(p.cat) < 0) CATS.push(p.cat); });
    var state = {
      id: 'burst', design: 1, seed: 20261103, size: 0, transparent: false, hue: 0, rotate: 0, cat: 'All',
      params: {}, colors: [], ref: null, refBase: false, base: null, vIdx: 0, vBase: 0, strength: 'medium', seen: new Set()
    };
    var current = null, urls = {}, raf = 0, famFor = '', famToken = 0, matchCtl = null, destroyed = false, toastT = 0;

    function blobUrl(key, svg) {
      if (urls[key]) { try { URL.revokeObjectURL(urls[key]); } catch (e) {} }
      urls[key] = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
      return urls[key];
    }
    function opts(extra) {
      var s = SIZES[state.size];
      return Object.assign({ width: s.w, height: s.h, seed: state.seed, params: state.params, colors: state.colors, transparent: state.transparent, hue: state.hue, rotate: state.rotate }, extra || {});
    }
    function fmt(n) { return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n); }
    function pad(n) { return String(n).padStart(3, '0'); }
    function normHex(h) {
      h = String(h || '').trim();
      if (/^#[0-9a-f]{3}$/i.test(h)) h = '#' + h[1] + h[1] + h[2] + h[2] + h[3] + h[3];
      return /^#[0-9a-f]{6}$/i.test(h) ? h.toLowerCase() : null;
    }
    function mapPalette(pal, n) { var o = []; for (var i = 0; i < n; i++) o.push(pal[i % pal.length]); return o; }
    function toast(t) { $('#toast').textContent = t; clearTimeout(toastT); toastT = setTimeout(function () { var el = $('#toast'); if (el) el.textContent = ''; }, 4500); }

    /* ---------- render ---------- */
    function label() { $('#m-design').textContent = (state.design ? 'Design #' + pad(state.design) + ' of ' + TOTAL : 'Custom design') + ' · variation ' + state.vIdx; }
    function render() {
      raf = 0; if (destroyed) return;
      var s = SIZES[state.size];
      current = G.build(state.id, opts());
      state.seen.add(G.hash(current.svg));
      $('#art').src = blobUrl('main', current.svg);
      $('#art').style.aspectRatio = s.w + ' / ' + s.h;
      $('#m-size').textContent = s.w + ' × ' + s.h + ' px';
      $('#m-fit').textContent = current.meta;
      $('#stats').textContent = fmt(current.shapes) + ' shapes · ' + Math.round(current.bytes / 1024) + ' KB';
      label();
      if (!$('#code').hidden) $('#code').value = G.toFile(current.svg);
    }
    function schedule() { if (!raf) raf = requestAnimationFrame(render); }

    function markBase() { state.base = { params: Object.assign({}, state.params), colors: state.colors.slice() }; state.vIdx = 0; state.vBase = 0; }
    function applyOptions(o) {
      state.seed = o.seed; state.params = Object.assign({}, o.params); state.colors = o.colors.slice();
      state.hue = o.hue || 0; state.rotate = o.rotate || 0;
      syncAll(); render();
    }
    function syncAll() {
      markPattern(); buildParams(); buildColors();
      $('#rot').value = state.rotate; $('#rot-o').textContent = state.rotate + '°';
      $('#lib-no').value = state.design || '';
      markFamily();
    }

    /* ---------- pattern families ---------- */
    function buildCats() {
      var box = $('#cats'); box.innerHTML = '';
      CATS.forEach(function (c) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'chip';
        b.textContent = c + ' ' + (c === 'All' ? G.patterns.length : G.patterns.filter(function (p) { return p.cat === c; }).length);
        b.setAttribute('aria-pressed', c === state.cat ? 'true' : 'false');
        b.onclick = function () { state.cat = c; buildCats(); filterPatterns(); };
        box.appendChild(b);
      });
    }
    function filterPatterns() { $$('.pat').forEach(function (b) { b.hidden = !(state.cat === 'All' || b.dataset.cat === state.cat); }); }
    function buildPatterns() {
      var box = $('#pats'); box.innerHTML = '';
      var q = [];
      G.patterns.forEach(function (p) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'pat'; b.dataset.id = p.id; b.dataset.cat = p.cat;
        b.innerHTML = '<img alt="" width="480" height="270"><span></span>';
        b.querySelector('span').textContent = p.name;
        b.onclick = function () { setPattern(p.id); };
        box.appendChild(b); q.push(p);
      });
      (function next() {
        if (destroyed) return;
        var p = q.shift(); if (!p) return;
        var img = sr.querySelector('.pat[data-id="' + p.id + '"] img');
        if (img) img.src = blobUrl('t-' + p.id, G.generate(p.id, { width: 480, height: 270, seed: 5 }));
        setTimeout(next, 0);
      })();
    }
    function markPattern() { $$('.pat').forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.id === state.id ? 'true' : 'false'); }); }

    /* ---------- design library ---------- */
    function buildFamily() {
      var box = $('#fam'); box.innerHTML = ''; famFor = state.id;
      var token = ++famToken, first = G.designNumber(state.id, 0), items = [];
      for (var m = 0; m < G.moods.length; m++) {
        (function (n) {
          var d = G.designAt(n);
          var b = document.createElement('button');
          b.type = 'button'; b.className = 'famb'; b.dataset.no = n;
          b.innerHTML = '<img alt="" width="360" height="203"><span></span>';
          b.querySelector('span').textContent = d.style + ' · ' + d.paletteName;
          b.onclick = function () { applyDesignNo(n); };
          box.appendChild(b); items.push({ n: n, d: d, b: b });
        })(first + m);
      }
      (function next() {
        if (destroyed || token !== famToken) return;
        var it = items.shift(); if (!it) return;
        var svg = G.generate(it.d.pattern, { width: 360, height: 203, params: it.d.params, colors: it.d.colors, seed: it.d.seed });
        it.b.querySelector('img').src = blobUrl('f-' + (it.n - first), svg);
        setTimeout(next, 0);
      })();
      markFamily();
    }
    function markFamily() {
      if (famFor !== state.id) { buildFamily(); return; }
      $$('.famb').forEach(function (b) { b.setAttribute('aria-pressed', state.design && +b.dataset.no === state.design ? 'true' : 'false'); });
    }
    function applyDesignNo(n) {
      n = Math.max(1, Math.min(TOTAL, Math.round(+n) || 1));
      var d = G.designAt(n);
      state.id = d.pattern; state.design = d.no; state.refBase = false;
      applyOptions({ seed: d.seed, params: d.params, colors: d.colors, hue: 0, rotate: 0 });
      markBase(); render(); buildVariations();
    }
    function setPattern(id) {
      applyDesignNo(G.designNumber(id, 0));
      if (state.ref) {
        state.colors = mapPalette(state.ref.palette, G.byId[id].colors.length); state.refBase = true;
        markBase(); buildColors(); render(); buildVariations();
      }
    }

    /* ---------- controls ---------- */
    function buildSizes() {
      var box = $('#sizes'); box.innerHTML = '';
      SIZES.forEach(function (s, i) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'chip'; b.textContent = s.l; b.title = s.w + ' × ' + s.h;
        b.setAttribute('aria-pressed', i === state.size ? 'true' : 'false');
        b.onclick = function () { state.size = i; buildSizes(); render(); buildVariations(); };
        box.appendChild(b);
      });
    }
    function buildStrength() {
      var box = $('#strength'); box.innerHTML = '';
      STRENGTHS.forEach(function (s) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'chip'; b.textContent = s[1];
        b.setAttribute('aria-pressed', s[0] === state.strength ? 'true' : 'false');
        b.onclick = function () { state.strength = s[0]; buildStrength(); buildVariations(); };
        box.appendChild(b);
      });
    }
    function edited() { state.design = null; label(); $$('.famb').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); }); }
    function committed() { markBase(); label(); buildVariations(); }
    function buildParams() {
      var pat = G.byId[state.id], box = $('#params'); box.innerHTML = '';
      pat.params.forEach(function (pr) {
        var row = document.createElement('div'); row.className = 'ctl';
        var id = 'p-' + pr.key;
        if (pr.type === 'toggle') {
          row.innerHTML = '<label class="tog"><input type="checkbox" id="' + id + '"><span></span></label>';
          row.querySelector('span').textContent = pr.label;
          var cb = row.querySelector('input'); cb.checked = !!state.params[pr.key];
          cb.onchange = function () { state.params[pr.key] = cb.checked ? 1 : 0; edited(); schedule(); committed(); };
        } else {
          var dec = pr.step < 1 ? 2 : 0;
          row.innerHTML = '<div class="ctl-head"><label for="' + id + '"></label><output for="' + id + '"></output></div>' +
            '<input type="range" id="' + id + '" min="' + pr.min + '" max="' + pr.max + '" step="' + pr.step + '">';
          row.querySelector('label').textContent = pr.label;
          var inp = row.querySelector('input'), out = row.querySelector('output');
          inp.value = state.params[pr.key]; out.textContent = (+inp.value).toFixed(dec);
          inp.oninput = function () { state.params[pr.key] = +inp.value; out.textContent = (+inp.value).toFixed(dec); edited(); schedule(); };
          inp.onchange = committed;
        }
        box.appendChild(row);
      });
    }
    var palSet = null;
    function buildColors() {
      if (G.palettesFor && palSet !== G.palettesFor(state.id)) buildPalettes();
      var pat = G.byId[state.id], box = $('#colors'); box.innerHTML = '';
      pat.colors.forEach(function (label, i) {
        var d = document.createElement('div'); d.className = 'col';
        d.innerHTML = '<span></span><input type="color" id="c-' + i + '"><code></code>';
        d.querySelector('span').textContent = label;
        var inp = d.querySelector('input'), code = d.querySelector('code');
        inp.setAttribute('aria-label', label);
        inp.value = state.colors[i]; code.textContent = state.colors[i];
        inp.oninput = function () { state.colors[i] = inp.value; code.textContent = inp.value; edited(); schedule(); };
        inp.onchange = function () { state.refBase = false; committed(); };
        box.appendChild(d);
      });
      $('#hue').value = state.hue; $('#hue-o').textContent = state.hue + '°';
    }
    function buildPalettes() {
      var box = $('#pals'); box.innerHTML = '';
      palSet = G.palettesFor ? G.palettesFor(state.id) : G.palettes;
      palSet.forEach(function (p) {
        var b = document.createElement('button');
        b.type = 'button'; b.title = p.name; b.setAttribute('aria-label', 'Palette ' + p.name);
        b.innerHTML = p.c.map(function (c) { return '<i style="background:' + c + '"></i>'; }).join('');
        b.onclick = function () {
          state.colors = p.c.slice(0, G.byId[state.id].colors.length); state.hue = 0; state.refBase = false;
          edited(); buildColors(); render(); committed();
        };
        box.appendChild(b);
      });
    }

    /* ---------- variations ---------- */
    function varOptions(idx) {
      var o;
      if (state.refBase && $('#diverge').checked === false) { o = G.variation(state.id, state.base, idx, 'subtle'); o.hue = 0; o.rotate = 0; }
      else o = G.variation(state.id, state.base, idx, state.strength);
      return o;
    }
    function nextVariation() {
      var idx = state.vIdx + 1, tries = 0, o;
      for (;;) {
        o = varOptions(idx);
        var svg = G.generate(state.id, opts({ params: o.params, colors: o.colors, seed: o.seed, hue: o.hue, rotate: o.rotate }));
        if (!state.seen.has(G.hash(svg)) || ++tries > 25) break;
        idx++;
      }
      state.vIdx = idx; applyOptions(o);
    }
    function buildVariations() {
      var box = $('#vars'); box.innerHTML = '';
      var s = SIZES[state.size], w = 420, h = Math.round(w * s.h / s.w);
      for (var i = 1; i <= 8; i++) {
        (function (idx) {
          var o = varOptions(idx);
          var svg = G.generate(state.id, { width: w, height: h, transparent: state.transparent, params: o.params, colors: o.colors, seed: o.seed, hue: o.hue, rotate: o.rotate });
          var b = document.createElement('button');
          b.type = 'button'; b.className = 'var'; b.setAttribute('aria-label', 'Use variation ' + idx);
          b.innerHTML = '<img alt="" src="' + blobUrl('v-' + (idx - state.vBase), svg) + '">';
          b.onclick = function () { state.vIdx = idx; applyOptions(o); };
          box.appendChild(b);
        })(state.vBase + i);
      }
    }

    /* ---------- reference: palette ---------- */
    function extractPalette(img) {
      var S = 72, cw = S, ch = Math.max(8, Math.round(S * img.naturalHeight / img.naturalWidth));
      if (ch > S) { ch = S; cw = Math.max(8, Math.round(S * img.naturalWidth / img.naturalHeight)); }
      var cv = document.createElement('canvas'); cv.width = cw; cv.height = ch;
      var cx = cv.getContext('2d', { willReadFrequently: true }); cx.drawImage(img, 0, 0, cw, ch);
      var d = cx.getImageData(0, 0, cw, ch).data, px = [], bins = {}, i;
      for (i = 0; i < d.length; i += 4) {
        if (d[i + 3] < 128) continue;
        px.push([d[i], d[i + 1], d[i + 2]]);
        var key = (d[i] >> 4) * 256 + (d[i + 1] >> 4) * 16 + (d[i + 2] >> 4);
        bins[key] = (bins[key] || 0) + 1;
      }
      if (!px.length) return null;
      var list = Object.keys(bins).map(function (k) { k = +k; return { c: [(k >> 8) * 16 + 8, ((k >> 4) & 15) * 16 + 8, (k & 15) * 16 + 8], n: bins[k] }; }).sort(function (a, b) { return b.n - a.n; });
      var dist = function (a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); };
      var centers = [];
      list.forEach(function (b) { if (centers.length < 5 && centers.every(function (c) { return dist(c, b.c) > 52; })) centers.push(b.c.slice()); });
      for (var it = 0; it < 6; it++) {
        var sums = centers.map(function () { return [0, 0, 0, 0]; });
        px.forEach(function (p) {
          var bi = 0, bd = 1e9;
          centers.forEach(function (c, ci) { var dd = dist(c, p); if (dd < bd) { bd = dd; bi = ci; } });
          sums[bi][0] += p[0]; sums[bi][1] += p[1]; sums[bi][2] += p[2]; sums[bi][3]++;
        });
        centers = centers.map(function (c, ci) { var s = sums[ci]; return s[3] ? [s[0] / s[3], s[1] / s[3], s[2] / s[3]] : c; });
        if (it === 5) centers = centers.map(function (c, ci) { return { c: c, n: sums[ci][3] }; });
      }
      centers = centers.filter(function (c) { return c.n > 0; }).sort(function (a, b) { return b.n - a.n; });
      var tot = centers.reduce(function (a, c) { return a + c.n; }, 0);
      var hex = function (c) { return '#' + c.map(function (v) { return Math.round(v).toString(16).padStart(2, '0'); }).join(''); };
      return centers.map(function (c) { return { hex: hex(c.c), share: c.n / tot }; });
    }

    /* ---------- reference: optional AI match ---------- */
    function catalogText() {
      return G.catalog().map(function (p) {
        return p.id + ' | ' + p.name + ' | ' + p.cat + ' | roles: ' + p.colors.join(', ') + ' | params: ' +
          p.params.map(function (r) { return r.key + '[' + r.min + '..' + r.max + ', default ' + r.def + ']'; }).join('; ');
      }).join('\n');
    }
    function buildPrompt(pal) {
      return 'You match a reference background image to a catalog of editable vector templates.\n\n' +
        'Catalog (id | name | category | colour roles in order | params as key[min..max, default]):\n' + catalogText() + '\n\n' +
        'Palette extracted from the reference, most common first:\n' + pal.map(function (p) { return p.hex + ' (' + Math.round(p.share * 100) + '%)'; }).join(', ') + '\n\n' +
        'Pick the 3 templates that best reproduce the reference STRUCTURE: shape type, symmetry, repetition, line versus filled areas, density. ' +
        'For each one set params to imitate what you see (counts, angles, density), staying inside min..max; toggles are 0 or 1. ' +
        'Set colors to one hex per colour role, in the role order, using hexes from the extracted palette (the most common one is usually the background role). ' +
        'The result must be an original look-alike in the same style, never a trace of the reference.\n\n' +
        'Reply with only JSON like {"matches":[{"id":"burst","score":85,"why":"short reason","params":{"rays":24},"colors":["#ffc425","#ff9f0a","#ffb52e"]}]}';
    }
    function cleanMatch(m, pal) {
      var pat = G.byId[m && m.id]; if (!pat) return null;
      var params = G.defaults(pat.id), given = (m.params && typeof m.params === 'object') ? m.params : {};
      pat.params.forEach(function (pr) {
        var v = Number(given[pr.key]); if (!isFinite(v) || given[pr.key] == null) return;
        if (pr.type === 'toggle') { params[pr.key] = v ? 1 : 0; return; }
        v = Math.max(pr.min, Math.min(pr.max, v));
        params[pr.key] = +(Math.round(v / pr.step) * pr.step).toFixed(3);
      });
      var cols = (Array.isArray(m.colors) ? m.colors : []).map(normHex).filter(Boolean);
      if (cols.length < pat.colors.length) cols = mapPalette(pal.map(function (p) { return p.hex; }), pat.colors.length);
      return { id: pat.id, score: Math.max(0, Math.min(100, Math.round(Number(m.score) || 0))), why: String(m.why || '').slice(0, 140), params: params, colors: cols.slice(0, pat.colors.length) };
    }
    function parseJson(x) {
      if (x && typeof x === 'object') return x;
      var t = String(x || ''), a = t.indexOf('{'), b = t.lastIndexOf('}');
      if (a < 0 || b < a) return null;
      try { return JSON.parse(t.slice(a, b + 1)); } catch (e) { return null; }
    }
    function setStatus(t) { $('#ref-status').textContent = t; }
    function applyMatch(m, idx) {
      state.id = m.id; state.design = null; state.refBase = true;
      applyOptions({ seed: Math.floor(Math.random() * 1e9), params: m.params, colors: m.colors, hue: 0, rotate: 0 });
      markBase(); label(); buildVariations();
      $$('.match').forEach(function (b, i) { b.setAttribute('aria-pressed', i === idx ? 'true' : 'false'); });
    }
    function showMatches(list) {
      var box = $('#matches'); box.innerHTML = '';
      var s = SIZES[state.size], h = Math.round(360 * s.h / s.w);
      list.forEach(function (m, i) {
        var b = document.createElement('button'); b.type = 'button'; b.className = 'match';
        var svg = G.generate(m.id, { width: 360, height: h, params: m.params, colors: m.colors, seed: 3 });
        b.innerHTML = '<img alt="" src="' + blobUrl('m-' + i, svg) + '"><span><b></b><small></small></span>';
        b.querySelector('b').textContent = G.byId[m.id].name + (m.score ? ' · ' + m.score + '%' : '');
        b.querySelector('small').textContent = m.why;
        b.onclick = function () { applyMatch(m, i); };
        box.appendChild(b);
      });
    }
    function paletteOnly(msg) {
      state.colors = mapPalette(state.ref.palette, G.byId[state.id].colors.length); state.hue = 0; state.refBase = true;
      edited(); buildColors(); render(); committed(); setStatus(msg);
    }
    function runMatch(file) {
      var pal = state.ref.full;
      if (typeof options.matchReference !== 'function') { paletteOnly('Colours copied. Pick a template from the list, or connect an AI endpoint to match the structure too.'); return; }
      setStatus('Comparing the structure…');
      if (matchCtl) matchCtl.cancelled = true;
      var ctl = matchCtl = { cancelled: false };
      Promise.resolve().then(function () { return options.matchReference({ file: file, palette: pal, prompt: buildPrompt(pal), catalog: G.catalog() }); })
        .then(function (res) {
          if (ctl.cancelled || destroyed) return;
          var obj = parseJson(res);
          var list = (obj && obj.matches ? obj.matches : []).map(function (m) { return cleanMatch(m, pal); }).filter(Boolean).slice(0, 3);
          if (!list.length) throw new Error('no matches');
          showMatches(list); applyMatch(list[0], 0);
          setStatus('Closest templates found. The first one is applied; edit anything on the left.');
        })
        .catch(function () { if (!ctl.cancelled && !destroyed) paletteOnly('The AI match did not work. Colours copied, pick a template yourself.'); });
    }
    function handleFile(file) {
      if (!file || !/^image\//.test(file.type)) { toast('Choose a PNG, JPG, WebP or GIF image.'); return; }
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () {
        var full = null; try { full = extractPalette(img); } catch (e) { full = null; }
        if (!full || !full.length) { setStatus('Could not read colours from this image.'); return; }
        state.ref = { palette: full.map(function (p) { return p.hex; }), full: full };
        $('#ref-row').hidden = false; $('#diverge-row').hidden = false; $('#matches').innerHTML = '';
        $('#ref-img').src = url;
        $('#ref-sw').innerHTML = full.map(function (p) { return '<i title="' + p.hex + ' ' + Math.round(p.share * 100) + '%" style="background:' + p.hex + '"></i>'; }).join('');
        runMatch(file);
      };
      img.onerror = function () { $('#ref-row').hidden = false; setStatus('This image could not be opened.'); };
      img.src = url;
    }

    /* ---------- downloads ---------- */

    /* ---------- Quota Check Hook ---------- */
    async function checkBgQuotaAndConsume() {
      if (!window.LineworkAuth || !window.LineworkAuth.user) {
        if (window.LineworkAuth) window.LineworkAuth.requireLogin();
        return false;
      }
      var u = window.LineworkAuth.user;
      var isUnlimited = (u.role === 'admin' || ['bundle_pro', 'bg_pro', 'pro'].indexOf(u.plan) !== -1);
      if (!isUnlimited && u.bg_used >= 10) {
        toast('Free trial limit reached (10 backgrounds used). Please upgrade to continue.', true);
        if (window.LineworkAuth) window.LineworkAuth.showPricing('bg_pro');
        return false;
      }
      try {
        var tok = sessionStorage.getItem('lw_token') || localStorage.getItem('lw_token') || '';
        var res = await fetch('/api/bgstudio/use', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + tok }
        });
        if (!res.ok) {
          var err = await res.json().catch(function(){return {};});
          toast(err.detail || 'Limit reached', true);
          if (window.LineworkAuth) window.LineworkAuth.showPricing('bg_pro');
          return false;
        }
        var data = await res.json();
        if (window.LineworkAuth && data.quota) {
          window.LineworkAuth.updateUserData(data.quota);
        }
        return true;
      } catch (e) {
        return true;
      }
    }

    function baseName() {
      var s = SIZES[state.size];
      return 'bg-' + state.id + (state.design ? '-d' + pad(state.design) : '-custom') + '-v' + state.vIdx + '-' + s.w + 'x' + s.h;
    }
    function saveBlob(name, blob) {
      var a = document.createElement('a'), u = URL.createObjectURL(blob);
      a.href = u; a.download = name; a.style.display = 'none';
      document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(u); a.remove(); }, 2000);
    }
    async function exportPNG() {
      if (!await checkBgQuotaAndConsume()) return;
      var s = SIZES[state.size], name = baseName();
      var u = URL.createObjectURL(new Blob([current.svg], { type: 'image/svg+xml' })), img = new Image();
      img.onload = function () {
        var cv = document.createElement('canvas'); cv.width = s.w; cv.height = s.h;
        cv.getContext('2d').drawImage(img, 0, 0, s.w, s.h);
        cv.toBlob(function (b) { URL.revokeObjectURL(u); if (b) { saveBlob(name + '.png', b); toast('Saved the PNG.'); } else toast('The PNG was too large for this browser. Pick a smaller artboard.'); }, 'image/png');
      };
      img.onerror = function () { URL.revokeObjectURL(u); toast('The PNG could not be made.'); };
      img.src = u;
    }

    
    /* ---------- ZIP Collection Pack Engine ---------- */
    var pack = [];

    function buildZipData(files) {
      var crcTable = new Uint32Array(256);
      for (var i = 0; i < 256; i++) {
        var c = i;
        for (var k = 0; k < 8; k++) c = ((c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1));
        crcTable[i] = c;
      }
      function crc32(buf) {
        var crc = -1;
        for (var i = 0; i < buf.length; i++) crc = (crc >>> 8) ^ crcTable[(crc ^ buf[i]) & 0xFF];
        return (crc ^ (-1)) >>> 0;
      }
      var te = new TextEncoder();
      var fileRecords = [];
      var offset = 0;
      var parts = [];

      for (var j = 0; j < files.length; j++) {
        var f = files[j];
        var nameBytes = te.encode(f.name);
        var dataBytes = typeof f.data === 'string' ? te.encode(f.data) : f.data;
        var crc = crc32(dataBytes);
        var size = dataBytes.length;

        var localHeader = new Uint8Array(30 + nameBytes.length);
        var lv = new DataView(localHeader.buffer);
        lv.setUint32(0, 0x04034b50, true);
        lv.setUint16(4, 20, true);
        lv.setUint16(6, 0, true);
        lv.setUint16(8, 0, true);
        lv.setUint16(10, 0, true);
        lv.setUint16(12, 0, true);
        lv.setUint32(14, crc, true);
        lv.setUint32(18, size, true);
        lv.setUint32(22, size, true);
        lv.setUint16(26, nameBytes.length, true);
        lv.setUint16(28, 0, true);
        localHeader.set(nameBytes, 30);

        parts.push(localHeader);
        parts.push(dataBytes);

        fileRecords.push({ nameBytes: nameBytes, crc: crc, size: size, offset: offset });
        offset += localHeader.length + dataBytes.length;
      }

      var centralDirStart = offset;
      for (var m = 0; m < fileRecords.length; m++) {
        var rec = fileRecords[m];
        var cd = new Uint8Array(46 + rec.nameBytes.length);
        var cv = new DataView(cd.buffer);
        cv.setUint32(0, 0x02014b50, true);
        cv.setUint16(4, 20, true);
        cv.setUint16(6, 20, true);
        cv.setUint16(8, 0, true);
        cv.setUint16(10, 0, true);
        cv.setUint16(12, 0, true);
        cv.setUint16(14, 0, true);
        cv.setUint32(16, rec.crc, true);
        cv.setUint32(20, rec.size, true);
        cv.setUint32(24, rec.size, true);
        cv.setUint16(28, rec.nameBytes.length, true);
        cv.setUint16(30, 0, true);
        cv.setUint16(32, 0, true);
        cv.setUint16(34, 0, true);
        cv.setUint16(36, 0, true);
        cv.setUint32(38, 0, true);
        cv.setUint32(42, rec.offset, true);
        cd.set(rec.nameBytes, 46);

        parts.push(cd);
        offset += cd.length;
      }

      var centralDirSize = offset - centralDirStart;
      var eocd = new Uint8Array(22);
      var ev = new DataView(eocd.buffer);
      ev.setUint32(0, 0x06054b50, true);
      ev.setUint16(4, 0, true);
      ev.setUint16(6, 0, true);
      ev.setUint16(8, fileRecords.length, true);
      ev.setUint16(10, fileRecords.length, true);
      ev.setUint32(12, centralDirSize, true);
      ev.setUint32(16, centralDirStart, true);
      ev.setUint16(20, 0, true);
      parts.push(eocd);

      var totalLen = 0;
      for (var k = 0; k < parts.length; k++) totalLen += parts[k].length;
      var out = new Uint8Array(totalLen);
      var pos = 0;
      for (var p = 0; p < parts.length; p++) {
        out.set(parts[p], pos);
        pos += parts[p].length;
      }
      return out;
    }

    var packFormat = 'svg';

    function setPackFormat(fmt) {
      packFormat = fmt;
      $$('.fmt-pill').forEach(function (b) {
        b.classList.toggle('active', b.dataset.fmt === fmt);
      });
      $$('input[name="pack-fmt"]').forEach(function (r) {
        r.checked = (r.value === fmt);
      });
      renderPack();
    }

    function renderPack() {
      var countEl = $('#pack-count');
      var countSubEl = $('#pack-count-sub');
      var btnDlAll = $('#btn-pack-dl-all');
      var quickDl = $('#btn-quick-dl');
      var itemsBox = $('#pack-items');
      var count = pack.length;

      if (countEl) countEl.textContent = count;
      if (countSubEl) countSubEl.textContent = '(' + count + ')';

      var label = 'SVGs';
      if (packFormat === 'eps') label = 'EPSs';
      else if (packFormat === 'both') label = 'Designs · SVG+EPS';
      else if (packFormat === 'png') label = 'PNGs';

      if (btnDlAll) {
        btnDlAll.textContent = '⬇ Download ZIP (' + count + ' ' + label + ')';
        btnDlAll.disabled = count === 0;
      }
      if (quickDl) {
        quickDl.style.display = count > 0 ? 'inline-block' : 'none';
        var qFmt = packFormat.toUpperCase();
        quickDl.textContent = packFormat === 'both' ? 'Download ZIP' : 'Download ' + qFmt + ' ZIP';
      }

      if (countEl) {
        countEl.classList.remove('bump');
        void countEl.offsetWidth;
        countEl.classList.add('bump');
      }

      if (!itemsBox) return;
      if (count === 0) {
        itemsBox.innerHTML = '<div class="pack-empty">Your pack is empty.<br>Click "+ Add to Pack" on any design!</div>';
        return;
      }

      itemsBox.innerHTML = '';
      pack.forEach(function (item, idx) {
        var row = document.createElement('div');
        row.className = 'pack-item';

        var img = document.createElement('img');
        img.className = 'pack-thumb';
        img.src = item.thumb;
        img.alt = item.name;

        var meta = document.createElement('div');
        meta.className = 'pack-meta';
        meta.innerHTML = '<span class="pack-name">' + (idx + 1) + '. ' + item.name + '</span>' +
                         '<span class="pack-dim">' + item.dim + ' · var ' + item.vIdx + '</span>';

        var del = document.createElement('button');
        del.type = 'button';
        del.className = 'pack-del';
        del.innerHTML = '✕';
        del.title = 'Remove from pack';
        del.onclick = function (e) {
          e.stopPropagation();
          pack.splice(idx, 1);
          renderPack();
          toast('Removed item from pack.');
        };

        row.appendChild(img);
        row.appendChild(meta);
        row.appendChild(del);
        itemsBox.appendChild(row);
      });
    }

    function addCurrentToPack() {
      var s = SIZES[state.size];
      var pat = G.byId[state.id];
      var pName = pat ? pat.name : state.id;
      var title = pName + (state.design ? ' #' + state.design : '');
      var base = baseName();

      var thumbUrl = URL.createObjectURL(new Blob([current.svg], { type: 'image/svg+xml' }));

      pack.push({
        id: state.id,
        name: title,
        baseName: base,
        vIdx: state.vIdx,
        dim: s.w + 'x' + s.h,
        svgText: G.toFile(current.svg),
        epsText: G.toEPS(current.svg, base),
        rawSvg: current.svg,
        width: s.w,
        height: s.h,
        thumb: thumbUrl
      });
      renderPack();
      toast('Added "' + title + '" to Pack! (' + pack.length + ' in ZIP)');
    }

    async function downloadPackZip() {
      if (pack.length === 0) return;
      if (!await checkBgQuotaAndConsume()) return;
      var btn = $('#btn-pack-dl-all');
      var quickBtn = $('#btn-quick-dl');
      var prevText = btn ? btn.textContent : '';
      if (btn) { btn.textContent = 'Generating ZIP...'; btn.disabled = true; }
      if (quickBtn) quickBtn.textContent = 'Zipping...';

      try {
        var incSvg = (packFormat === 'svg' || packFormat === 'both');
        var incEps = (packFormat === 'eps' || packFormat === 'both');
        var incPng = (packFormat === 'png');

        var files = [];
        var readme = [
          'Linework AI - BG Studio Vector Collection Pack',
          '==============================================',
          'Total Backgrounds: ' + pack.length,
          'Exported at: ' + new Date().toLocaleString(),
          '',
          'Included Designs:'
        ];

        for (var i = 0; i < pack.length; i++) {
          var it = pack[i];
          var num = String(i + 1).padStart(2, '0');
          var fileBase = num + '-' + it.baseName;

          readme.push((i + 1) + '. ' + it.name + ' (' + it.dim + ', variation ' + it.vIdx + ')');

          if (incSvg) {
            files.push({ name: fileBase + '.svg', data: it.svgText });
          }
          if (incEps) {
            files.push({ name: fileBase + '.eps', data: it.epsText });
          }
          if (incPng) {
            try {
              var pngData = await new Promise(function (res) {
                var u = URL.createObjectURL(new Blob([it.rawSvg], { type: 'image/svg+xml' }));
                var img = new Image();
                img.onload = function () {
                  var cv = document.createElement('canvas');
                  cv.width = it.width;
                  cv.height = it.height;
                  cv.getContext('2d').drawImage(img, 0, 0, it.width, it.height);
                  cv.toBlob(function (b) {
                    URL.revokeObjectURL(u);
                    if (b) {
                      b.arrayBuffer().then(function (ab) { res(new Uint8Array(ab)); }).catch(function () { res(null); });
                    } else res(null);
                  }, 'image/png');
                };
                img.onerror = function () { URL.revokeObjectURL(u); res(null); };
                img.src = u;
              });
              if (pngData) {
                files.push({ name: fileBase + '.png', data: pngData });
              }
            } catch (err) {
              console.warn('PNG render failed for item', i, err);
            }
          }
        }

        readme.push('');
        readme.push('All SVG and EPS shapes are 100% native editable vector curves.');
        readme.push('Generated with Linework AI BG Studio.');
        files.push({ name: 'manifest.txt', data: readme.join('\n') });

        var zipBytes = buildZipData(files);
        var zipName = 'bgstudio-pack-' + pack.length + '-' + packFormat + '.zip';
        saveBlob(zipName, new Blob([zipBytes], { type: 'application/zip' }));
        toast('Downloaded ZIP containing ' + pack.length + ' backgrounds (' + files.length + ' files)!');
      } catch (e) {
        console.error('Error generating zip:', e);
        toast('Failed to create ZIP: ' + (e.message || e));
      } finally {
        if (btn) { btn.textContent = prevText; btn.disabled = false; }
        if (quickBtn) quickBtn.textContent = 'Download ZIP';
      }
    }

    /* ---------- wiring ---------- */
    var onPaste = function (e) {
      if (destroyed || !host.isConnected || !host.getClientRects().length) return;
      var fl = e.clipboardData && e.clipboardData.files;
      if (fl && fl.length && /^image\//.test(fl[0].type)) { e.preventDefault(); handleFile(fl[0]); }
    };
    document.addEventListener('paste', onPaste);
    var drop = $('#drop');
    ['dragenter', 'dragover'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('over'); }); });
    ['dragleave', 'drop'].forEach(function (ev) { drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('over'); }); });
    drop.addEventListener('drop', function (e) { var fl = e.dataTransfer && e.dataTransfer.files; if (fl && fl.length) handleFile(fl[0]); });
    $('#btn-file').onclick = function () { $('#file').click(); };
    $('#file').onchange = function (e) { handleFile(e.target.files[0]); e.target.value = ''; };

    $('#btn-svg').onclick = async function () { if (!await checkBgQuotaAndConsume()) return; saveBlob(baseName() + '.svg', new Blob([G.toFile(current.svg)], { type: 'image/svg+xml' })); toast('Saved the SVG. Open it in Illustrator, Figma or Inkscape.'); };
    $('#btn-eps').onclick = async function () { if (!await checkBgQuotaAndConsume()) return;
      var name = baseName();
      saveBlob(name + '.eps', new Blob([G.toEPS(current.svg, name)], { type: 'application/postscript' })); toast('Saved the EPS.');
    };
    $('#btn-png').onclick = exportPNG;
    $('#btn-add-pack').onclick = addCurrentToPack;
    if ($('#btn-add-all-vars')) {
      $('#btn-add-all-vars').onclick = function () {
        var s = SIZES[state.size];
        var pat = G.byId[state.id];
        var pName = pat ? pat.name : state.id;
        for (var vi = 1; vi <= 8; vi++) {
          var vIndex = state.vBase + vi;
          var o = varOptions(vIndex);
          var svgRaw = G.generate(state.id, { width: s.w, height: s.h, transparent: state.transparent, params: o.params, colors: o.colors, seed: o.seed, hue: o.hue, rotate: o.rotate });
          var bName = state.id + '-v' + vIndex + '-' + s.w + 'x' + s.h;
          var thumbUrl = URL.createObjectURL(new Blob([svgRaw], { type: 'image/svg+xml' }));
          pack.push({
            id: state.id,
            name: pName + ' (Var ' + vIndex + ')',
            baseName: bName,
            vIdx: vIndex,
            dim: s.w + 'x' + s.h,
            svgText: G.toFile(svgRaw),
            epsText: G.toEPS(svgRaw, bName),
            rawSvg: svgRaw,
            width: s.w,
            height: s.h,
            thumb: thumbUrl
          });
        }
        renderPack();
        toast('Added 8 variations to Pack! (' + pack.length + ' in ZIP)');
      };
    }
    $('#pack-toggle').onclick = function () {
      var d = $('#pack-drawer');
      var isClosed = d.hidden;
      d.hidden = !isClosed;
      $('#pack-dock').classList.toggle('open', isClosed);
    };
    $('#btn-clear-pack').onclick = function (e) {
      e.stopPropagation();
      pack = [];
      renderPack();
      toast('Pack cleared.');
    };
    $('#btn-quick-dl').onclick = function (e) { e.stopPropagation(); downloadPackZip(); };
    $('#btn-pack-dl-all').onclick = downloadPackZip;
    $$('.fmt-pill').forEach(function (pill) {
      pill.onclick = function (e) {
        e.stopPropagation();
        setPackFormat(pill.dataset.fmt);
      };
    });
    $$('input[name="pack-fmt"]').forEach(function (radio) {
      radio.onchange = function () {
        setPackFormat(radio.value);
      };
    });
    $('#btn-next').onclick = nextVariation;
    $('#btn-shuffle').onclick = function () {
      var o = G.randomOptions(state.id, Math.floor(Math.random() * 1e9));
      state.design = null; state.refBase = false;
      applyOptions(Object.assign(o, { hue: 0, rotate: 0 }));
      markBase(); label(); buildVariations();
    };
    $('#btn-vars').onclick = function () { state.vBase += 8; buildVariations(); };
    $('#diverge').onchange = function () { buildVariations(); };
    $('#transparent').onchange = function (e) { state.transparent = e.target.checked; render(); buildVariations(); };
    $('#hue').oninput = function (e) { state.hue = +e.target.value; $('#hue-o').textContent = state.hue + '°'; schedule(); };
    $('#rot').oninput = function (e) { state.rotate = +e.target.value; $('#rot-o').textContent = state.rotate + '°'; schedule(); };
    $('#lib-prev').onclick = function () { applyDesignNo(((state.design || 1) + TOTAL - 2) % TOTAL + 1); };
    $('#lib-next').onclick = function () { applyDesignNo((state.design || 0) % TOTAL + 1); };
    $('#lib-rand').onclick = function () { applyDesignNo(1 + Math.floor(Math.random() * TOTAL)); };
    $('#lib-no').onchange = function (e) { applyDesignNo(e.target.value); };
    $('#lib-of').textContent = 'of ' + TOTAL; $('#lib-no').max = TOTAL;
    $('#lib-note').textContent = TOTAL + ' designs × ' + VPD.toLocaleString('en-US') + ' variations = ' + (TOTAL * VPD).toLocaleString('en-US') + ' unique files, and New variation keeps going past that. Each one is checked against what you have already seen.';
    $('#btn-code').onclick = function () {
      var c = $('#code'); c.hidden = !c.hidden;
      $('#btn-code').textContent = c.hidden ? 'Show code' : 'Hide code';
      if (!c.hidden) c.value = G.toFile(current.svg);
    };
    $('#btn-copy').onclick = function () {
      var text = G.toFile(current.svg);
      var fallback = function () { var c = $('#code'); c.hidden = false; c.value = text; $('#btn-code').textContent = 'Hide code'; c.focus(); c.select(); toast('Copy was blocked. The code is selected below, press Ctrl+C.'); };
      try { navigator.clipboard.writeText(text).then(function () { toast('Copied the SVG code.'); }, fallback); } catch (e) { fallback(); }
    };

    /* header + responsive layout */
    if (options.title === false) $('#head').hidden = true;
    else {
      $('#title').textContent = options.title || 'BG Studio';
      $('#sub').textContent = TOTAL.toLocaleString('en-US') + ' ready designs from ' + G.patterns.length + ' patterns, each with endless unique variations. Change shape and colour, then download SVG, EPS or PNG. Every shape stays editable vector art.';
    }
    var rootEl = $('#root'), ro = null;
    var fit = function () { rootEl.classList.toggle('wide', host.clientWidth >= 940); };
    fit();
    if (root.ResizeObserver) { ro = new ResizeObserver(fit); ro.observe(host); }

    buildCats(); buildPatterns(); buildSizes(); buildStrength(); buildPalettes(); applyDesignNo(1);

    var api = {
      destroy: function () {
        if (destroyed) return; destroyed = true;
        document.removeEventListener('paste', onPaste);
        if (ro) ro.disconnect();
        clearTimeout(toastT); cancelAnimationFrame(raf);
        Object.keys(urls).forEach(function (k) { try { URL.revokeObjectURL(urls[k]); } catch (e) {} });
        sr.innerHTML = '';
        Object.keys(THEME_VARS).forEach(function (k) { host.style.removeProperty(THEME_VARS[k]); });
        delete host.__bgstudio;
      },
      /* read-only helpers for the host app */
      getSVG: function () { return G.toFile(current.svg); },
      getEPS: function () { return G.toEPS(current.svg, baseName()); },
      getState: function () { return { pattern: state.id, design: state.design, variation: state.vIdx, size: SIZES[state.size] }; }
    };
    host.__bgstudio = api;
    return api;
  }

  root.BGStudio = { mount: mount, version: '1.7.0' };
})(window);
