/**
 * Vector BG Studio - Parametric Vector Background Generator
 * Full Claude-style Complete Suite Controller for Linework AI
 */
(() => {
  'use strict';

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(() => {
    const G = window.BGGen;
    if (!G) {
      console.warn('BGGen library not found.');
      return;
    }

    const $ = (s, r = document) => r.querySelector(s);
    const $$ = (s, r = document) => [...r.querySelectorAll(s)];

    const toast = (msg, isErr) => {
      const t = $('#toast');
      if (!t) return;
      t.textContent = msg;
      t.className = 'toast show' + (isErr ? ' err' : '');
      clearTimeout(toast._tm);
      toast._tm = setTimeout(() => { t.className = 'toast'; }, 3200);
    };

    // State
    const state = {
      initialized: false,
      designNo: 1, // 1 to 510
      patternId: 'burst',
      moodIdx: 0,
      variationIdx: 0,
      strength: 'medium', // subtle | medium | wild
      varOffset: 0,
      params: {},
      colors: [],
      paletteName: 'Original',
      hue: 0,
      rotate: 0,
      transparent: false,
      width: 1920,
      height: 1080,
      aspectRatio: '16:9',
      currentSvg: '',
      activeCat: 'all'
    };

    // DOM Elements
    const views = {
      landing: $('#landing'),
      work: $('#work'),
      templateStudio: $('#templateStudio'),
      bgStudio: $('#bgStudio')
    };

    const navs = {
      redraw: $('#navRedraw'),
      bgStudio: $('#navBgStudio'),
      home: $('#navHome')
    };

    const els = {
      btnBack: $('#btnBackFromBgStudio'),
      metaText: $('#vbgMetaText'),
      btnNewVar: $('#btnVbgNewVar'),
      btnShuffle: $('#btnVbgShuffle'),
      heroStage: $('#vbgHeroStage'),
      btnCopySvg: $('#btnVbgCopySvg'),
      btnShowCode: $('#btnVbgShowCode'),
      btnExportSvg: $('#btnVbgExportSvg'),
      btnDownloadPng: $('#btnVbgDownloadPng'),
      heroStats: $('#vbgHeroStats'),
      strengthSeg: $('#vbgStrengthSeg'),
      btnMoreVars: $('#btnVbgMoreVars'),
      variationsGrid: $('#vbgVariationsGrid'),
      dropZone: $('#vbgDropZone'),
      refFileInput: $('#vbgRefFileInput'),
      btnChooseImg: $('#btnVbgChooseImg'),
      familyTabs: $('#vbgFamilyTabs'),
      patternsGrid: $('#vbgPatternsGrid'),
      btnPrevDesign: $('#btnVbgPrevDesign'),
      designInput: $('#vbgDesignInput'),
      btnNextDesign: $('#btnVbgNextDesign'),
      btnRandomDesign: $('#btnVbgRandomDesign'),
      designsGallery: $('#vbgDesignsGallery'),
      ratioSeg: $('#vbgRatioSeg'),
      transparentCheck: $('#vbgTransparentCheck'),
      rotateSlider: $('#vbgRotateSlider'),
      rotateVal: $('#vbgRotateVal'),
      shapeSliders: $('#vbgShapeSliders'),
      colorsSwatches: $('#vbgColorsSwatches'),
      hueSlider: $('#vbgHueSlider'),
      hueVal: $('#vbgHueVal'),
      palettesGrid: $('#vbgPalettesGrid'),
      codeModal: $('#bgCodeModal'),
      codeTextarea: $('#bgCodeTextarea'),
      btnModalCopyCode: $('#btnModalCopyCode'),
      closeCodeModal: $('#closeBgCodeModal')
    };

    // Navigation Switchers
    function openBgStudio() {
      if (views.landing) views.landing.hidden = true;
      if (views.work) views.work.hidden = true;
      if (views.templateStudio) views.templateStudio.hidden = true;
      if (views.bgStudio) views.bgStudio.hidden = false;

      $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
      if (navs.bgStudio) navs.bgStudio.classList.add('active');

      if (!state.initialized) {
        initStudio();
      } else {
        renderHero();
      }
    }

    function returnToRedraw() {
      if (views.bgStudio) views.bgStudio.hidden = true;
      if (views.templateStudio) views.templateStudio.hidden = true;

      $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
      if (navs.redraw) navs.redraw.classList.add('active');

      if (window.LineworkApp && window.LineworkApp.job) {
        if (views.work) views.work.hidden = false;
        if (views.landing) views.landing.hidden = true;
      } else {
        if (views.landing) views.landing.hidden = false;
        if (views.work) views.work.hidden = true;
      }
    }

    if (navs.bgStudio) {
      navs.bgStudio.addEventListener('click', e => {
        e.preventDefault();
        openBgStudio();
      });
    }

    if (navs.redraw) {
      navs.redraw.addEventListener('click', e => {
        if (views.bgStudio && !views.bgStudio.hidden) {
          e.preventDefault();
          returnToRedraw();
        }
      });
    }

    if (els.btnBack) {
      els.btnBack.addEventListener('click', e => {
        e.preventDefault();
        returnToRedraw();
      });
    }

    // Initialize Studio Controls
    function initStudio() {
      state.initialized = true;

      // 1. Top Buttons
      if (els.btnNewVar) {
        els.btnNewVar.addEventListener('click', () => {
          state.variationIdx++;
          renderHero();
          renderVariationsGrid();
        });
      }

      if (els.btnShuffle) {
        els.btnShuffle.addEventListener('click', () => {
          const rndDesign = Math.floor(Math.random() * G.designCount()) + 1;
          loadDesignNumber(rndDesign);
          toast(`Shuffled to Design #${rndDesign}`);
        });
      }

      // 2. Action Strip
      if (els.btnCopySvg) els.btnCopySvg.addEventListener('click', copySvgToClipboard);
      if (els.btnShowCode) els.btnShowCode.addEventListener('click', openCodeModal);
      if (els.btnExportSvg) els.btnExportSvg.addEventListener('click', exportSvgFile);
      if (els.btnDownloadPng) els.btnDownloadPng.addEventListener('click', exportPngFile);

      // 3. Variations Section Controls
      if (els.strengthSeg) {
        els.strengthSeg.addEventListener('click', e => {
          const btn = e.target.closest('.vbg-seg-btn');
          if (!btn) return;
          $$('.vbg-seg-btn', els.strengthSeg).forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          state.strength = btn.dataset.v || 'medium';
          renderVariationsGrid();
          if (state.variationIdx > 0) renderHero();
        });
      }

      if (els.btnMoreVars) {
        els.btnMoreVars.addEventListener('click', () => {
          state.varOffset += 8;
          renderVariationsGrid();
        });
      }

      // 4. Match a Reference
      setupMatchReference();

      // 5. Pattern Family Tabs
      if (els.familyTabs) {
        els.familyTabs.addEventListener('click', e => {
          const tab = e.target.closest('.vbg-tab-pill');
          if (!tab) return;
          $$('.vbg-tab-pill', els.familyTabs).forEach(b => b.classList.remove('active'));
          tab.classList.add('active');
          state.activeCat = tab.dataset.cat || 'all';
          renderPatternsGrid();
        });
      }

      // 6. Design Library Steppers
      if (els.btnPrevDesign) {
        els.btnPrevDesign.addEventListener('click', () => {
          loadDesignNumber(Math.max(1, state.designNo - 1));
        });
      }
      if (els.btnNextDesign) {
        els.btnNextDesign.addEventListener('click', () => {
          loadDesignNumber(Math.min(G.designCount(), state.designNo + 1));
        });
      }
      if (els.designInput) {
        els.designInput.addEventListener('change', e => {
          const n = parseInt(e.target.value, 10);
          if (!isNaN(n)) loadDesignNumber(Math.max(1, Math.min(G.designCount(), n)));
        });
      }
      if (els.btnRandomDesign) {
        els.btnRandomDesign.addEventListener('click', () => {
          const r = Math.floor(Math.random() * G.designCount()) + 1;
          loadDesignNumber(r);
        });
      }

      // 7. Artboard Settings
      if (els.ratioSeg) {
        els.ratioSeg.addEventListener('click', e => {
          const btn = e.target.closest('.vbg-seg-btn');
          if (!btn) return;
          $$('.vbg-seg-btn', els.ratioSeg).forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          state.aspectRatio = btn.dataset.ratio;
          state.width = parseInt(btn.dataset.w, 10) || 1920;
          state.height = parseInt(btn.dataset.h, 10) || 1080;
          renderHero();
          renderVariationsGrid();
        });
      }

      if (els.transparentCheck) {
        els.transparentCheck.addEventListener('change', e => {
          state.transparent = !!e.target.checked;
          renderHero();
          renderVariationsGrid();
        });
      }

      if (els.rotateSlider) {
        els.rotateSlider.addEventListener('input', e => {
          state.rotate = parseInt(e.target.value, 10) || 0;
          if (els.rotateVal) els.rotateVal.textContent = state.rotate + '°';
          scheduleDebouncedHeroRender();
        });
      }

      // 8. Hue Shift Slider
      if (els.hueSlider) {
        els.hueSlider.addEventListener('input', e => {
          state.hue = parseInt(e.target.value, 10) || 0;
          if (els.hueVal) els.hueVal.textContent = state.hue + '°';
          scheduleDebouncedHeroRender();
        });
      }

      // 9. Palettes Grid
      renderPalettesGrid();

      // 10. Code Modal Handlers
      if (els.btnModalCopyCode) {
        els.btnModalCopyCode.addEventListener('click', () => {
          if (els.codeTextarea) {
            navigator.clipboard.writeText(els.codeTextarea.value).then(() => {
              toast('SVG markup copied!');
            });
          }
        });
      }
      if (els.closeCodeModal) {
        els.closeCodeModal.addEventListener('click', () => {
          if (els.codeModal) els.codeModal.style.display = 'none';
        });
      }
      if (els.codeModal) {
        els.codeModal.addEventListener('click', e => {
          if (e.target === els.codeModal) els.codeModal.style.display = 'none';
        });
      }

      // Load initial design #1
      loadDesignNumber(1);
      renderPatternsGrid();
    }

    function loadDesignNumber(num) {
      state.designNo = Math.max(1, Math.min(G.designCount(), num));
      const d = G.designAt(state.designNo);
      state.patternId = d.pattern;
      state.moodIdx = d.mood;
      state.params = Object.assign({}, d.params);
      state.colors = d.colors.slice();
      state.paletteName = d.paletteName;
      state.variationIdx = 0;
      state.varOffset = 0;
      state.rotate = 0;
      state.hue = 0;

      if (els.designInput) els.designInput.value = state.designNo;
      if (els.rotateSlider) els.rotateSlider.value = 0;
      if (els.rotateVal) els.rotateVal.textContent = '0°';
      if (els.hueSlider) els.hueSlider.value = 0;
      if (els.hueVal) els.hueVal.textContent = '0°';

      buildShapeSliders();
      buildColorSwatches();
      renderHero();
      renderVariationsGrid();
      renderDesignsGallery();
      updatePatternActiveState();
    }

    // --- Hero Rendering ---
    let heroTimer = null;
    function scheduleDebouncedHeroRender() {
      clearTimeout(heroTimer);
      heroTimer = setTimeout(renderHero, 25);
    }

    function renderHero() {
      if (!views.bgStudio || views.bgStudio.hidden) return;

      const patId = state.patternId;
      const d = G.designAt(state.designNo);

      let p = Object.assign({}, state.params);
      let c = state.colors.slice();
      let h = state.hue;
      let r = state.rotate;
      let seed = (d && d.seed) || 1000;

      if (state.variationIdx > 0) {
        const v = G.variation(patId, { params: p, colors: c }, state.variationIdx, state.strength);
        p = v.params;
        c = v.colors;
        h = (state.hue + v.hue) % 360;
        r = (state.rotate + v.rotate);
        seed = v.seed;
      }

      try {
        const out = G.build(patId, {
          width: state.width,
          height: state.height,
          transparent: state.transparent,
          params: p,
          colors: c,
          hue: h,
          rotate: r,
          seed: seed
        });

        state.currentSvg = out.svg;

        if (els.heroStage) {
          els.heroStage.innerHTML = out.svg;
          const svgEl = els.heroStage.querySelector('svg');
          if (svgEl) {
            svgEl.style.width = '100%';
            svgEl.style.height = '100%';
            svgEl.style.display = 'block';
          }
        }

        const patName = (G.byId[patId] && G.byId[patId].name) || patId;
        const metaStr = out.meta || 'Parametric Vector Shapes';
        if (els.metaText) {
          els.metaText.textContent = `${patName} · variation ${state.variationIdx} · ${state.width} × ${state.height} px · ${out.shapes} separate shapes, no overlaps`;
        }
        if (els.heroStats) {
          els.heroStats.textContent = `${out.shapes} shapes · ${(out.bytes / 1024).toFixed(0)} KB`;
        }

      } catch (err) {
        console.error('Vector BG Studio Hero render error:', err);
      }
    }

    // --- Variations Section (8 live miniature cards) ---
    function renderVariationsGrid() {
      if (!els.variationsGrid) return;
      els.variationsGrid.innerHTML = '';

      const patId = state.patternId;
      const baseParams = Object.assign({}, state.params);
      const baseColors = state.colors.slice();

      for (let i = 1; i <= 8; i++) {
        const vIdx = state.varOffset + i;
        const v = G.variation(patId, { params: baseParams, colors: baseColors }, vIdx, state.strength);

        const card = document.createElement('div');
        card.className = 'vbg-var-card' + (state.variationIdx === vIdx ? ' active' : '');
        card.title = `Variation #${vIdx} (${state.strength})`;

        // Build thumbnail SVG
        const thumbOut = G.build(patId, {
          width: 320,
          height: 180,
          transparent: state.transparent,
          params: v.params,
          colors: v.colors,
          hue: (state.hue + v.hue) % 360,
          rotate: (state.rotate + v.rotate),
          seed: v.seed
        });

        card.innerHTML = thumbOut.svg;

        card.addEventListener('click', () => {
          state.variationIdx = vIdx;
          $$('.vbg-var-card', els.variationsGrid).forEach(c => c.classList.remove('active'));
          card.classList.add('active');
          renderHero();
        });

        els.variationsGrid.appendChild(card);
      }
    }

    // --- Pattern Family (3-column cards with SVG previews) ---
    function renderPatternsGrid() {
      if (!els.patternsGrid || !G.patterns) return;
      els.patternsGrid.innerHTML = '';

      const cat = state.activeCat;
      const list = G.patterns.filter(p => cat === 'all' || p.cat === cat);

      list.forEach(pat => {
        const card = document.createElement('div');
        card.className = 'vbg-pattern-card' + (pat.id === state.patternId ? ' active' : '');
        card.dataset.id = pat.id;

        const thumbBox = document.createElement('div');
        thumbBox.className = 'vbg-pat-thumb';

        // Render sample preview
        const sampleOut = G.build(pat.id, {
          width: 320,
          height: 180,
          params: G.defaults(pat.id),
          colors: G.defaultColors(pat.id)
        });
        thumbBox.innerHTML = sampleOut.svg;

        const nameBox = document.createElement('div');
        nameBox.className = 'vbg-pat-name';
        nameBox.textContent = pat.name;

        card.appendChild(thumbBox);
        card.appendChild(nameBox);

        card.addEventListener('click', () => {
          state.patternId = pat.id;
          state.params = Object.assign({}, G.defaults(pat.id));
          state.colors = G.defaultColors(pat.id).slice();
          state.variationIdx = 0;
          state.varOffset = 0;

          // Find design number if matching
          const dNo = G.designNumber(pat.id, state.moodIdx);
          if (dNo >= 1 && dNo <= G.designCount()) state.designNo = dNo;
          if (els.designInput) els.designInput.value = state.designNo;

          updatePatternActiveState();
          buildShapeSliders();
          buildColorSwatches();
          renderHero();
          renderVariationsGrid();
          renderDesignsGallery();
        });

        els.patternsGrid.appendChild(card);
      });
    }

    function updatePatternActiveState() {
      if (!els.patternsGrid) return;
      $$('.vbg-pattern-card', els.patternsGrid).forEach(c => {
        c.classList.toggle('active', c.dataset.id === state.patternId);
      });
    }

    // --- Design Library Nearby Cards ---
    function renderDesignsGallery() {
      if (!els.designsGallery) return;
      els.designsGallery.innerHTML = '';

      const cur = state.designNo;
      const total = G.designCount();
      const indices = [
        cur > 1 ? cur - 1 : total,
        cur,
        cur < total ? cur + 1 : 1
      ];

      indices.forEach(idx => {
        const d = G.designAt(idx);
        const card = document.createElement('div');
        card.className = 'vbg-pattern-card' + (idx === cur ? ' active' : '');

        const thumb = document.createElement('div');
        thumb.className = 'vbg-pat-thumb';
        const out = G.build(d.pattern, {
          width: 320,
          height: 180,
          params: d.params,
          colors: d.colors,
          seed: d.seed
        });
        thumb.innerHTML = out.svg;

        const label = document.createElement('div');
        label.className = 'vbg-pat-name';
        label.textContent = `#${idx} · ${d.name}`;

        card.appendChild(thumb);
        card.appendChild(label);

        card.addEventListener('click', () => {
          loadDesignNumber(idx);
        });

        els.designsGallery.appendChild(card);
      });
    }

    // --- Dynamic Shape Parameters Sliders ---
    function buildShapeSliders() {
      if (!els.shapeSliders) return;
      const pat = G.byId[state.patternId];
      if (!pat || !pat.params || !pat.params.length) {
        els.shapeSliders.innerHTML = '<div style="color:#7f8c9b; font-size:12px;">No tunable shape sliders for this pattern.</div>';
        return;
      }

      els.shapeSliders.innerHTML = pat.params.map(p => {
        const curVal = state.params[p.key] !== undefined ? state.params[p.key] : p.def;
        return `
          <div class="vbg-slider-row">
            <div class="vbg-slider-meta">
              <label for="vbgParam_${p.key}">${p.label}</label>
              <span class="vbg-val-label" id="vbgParamVal_${p.key}">${curVal}</span>
            </div>
            <input type="range" class="vbg-range" id="vbgParam_${p.key}"
              data-key="${p.key}" min="${p.min}" max="${p.max}" step="${p.step}" value="${curVal}">
          </div>
        `;
      }).join('');

      $$('input[type="range"]', els.shapeSliders).forEach(slider => {
        slider.addEventListener('input', e => {
          const k = e.target.dataset.key;
          const val = parseFloat(e.target.value);
          state.params[k] = val;
          const valSpan = $(`#vbgParamVal_${k}`);
          if (valSpan) valSpan.textContent = val;
          scheduleDebouncedHeroRender();
          renderVariationsGrid();
        });
      });
    }

    // --- Colours Swatches ---
    function buildColorSwatches() {
      if (!els.colorsSwatches) return;
      const pat = G.byId[state.patternId];
      const labels = (pat && pat.colors) || ['Background', 'Shape 1', 'Shape 2'];

      els.colorsSwatches.innerHTML = labels.map((lbl, idx) => {
        const c = state.colors[idx] || (G.defaultColors(state.patternId)[idx] || '#00f5b7');
        return `
          <div class="vbg-swatch-item">
            <span class="vbg-swatch-label">${lbl}</span>
            <div class="vbg-swatch-box" style="background:${c};">
              <input type="color" data-idx="${idx}" value="${c}">
            </div>
            <span class="vbg-swatch-hex" id="vbgHex_${idx}">${c}</span>
          </div>
        `;
      }).join('');

      $$('input[type="color"]', els.colorsSwatches).forEach(picker => {
        picker.addEventListener('input', e => {
          const idx = parseInt(e.target.dataset.idx, 10);
          state.colors[idx] = e.target.value;
          const hexEl = $(`#vbgHex_${idx}`);
          if (hexEl) hexEl.textContent = e.target.value;
          e.target.closest('.vbg-swatch-box').style.background = e.target.value;
          scheduleDebouncedHeroRender();
          renderVariationsGrid();
        });
      });
    }

    // --- Palettes Grid (5-color bar strips) ---
    function renderPalettesGrid() {
      if (!els.palettesGrid || !G.libraryPalettes) return;
      els.palettesGrid.innerHTML = '';

      // Take first 12 distinct library palettes
      const pals = G.libraryPalettes.slice(0, 12);

      pals.forEach(p => {
        const bar = document.createElement('div');
        bar.className = 'vbg-palette-bar';
        bar.title = p.name;

        p.c.slice(0, 5).forEach(color => {
          const stripe = document.createElement('div');
          stripe.className = 'vbg-palette-stripe';
          stripe.style.background = color;
          bar.appendChild(stripe);
        });

        bar.addEventListener('click', () => {
          state.colors = p.c.slice();
          buildColorSwatches();
          renderHero();
          renderVariationsGrid();
          toast(`Applied "${p.name}" color palette!`);
        });

        els.palettesGrid.appendChild(bar);
      });
    }

    // --- Match a Reference (Image Color Extraction) ---
    function setupMatchReference() {
      if (els.btnChooseImg && els.refFileInput) {
        els.btnChooseImg.addEventListener('click', () => {
          els.refFileInput.click();
        });

        els.refFileInput.addEventListener('change', e => {
          if (e.target.files && e.target.files[0]) {
            processReferenceImageFile(e.target.files[0]);
          }
        });
      }

      if (els.dropZone) {
        ['dragenter', 'dragover'].forEach(name => {
          els.dropZone.addEventListener(name, e => {
            e.preventDefault();
            els.dropZone.classList.add('dragover');
          });
        });
        ['dragleave', 'drop'].forEach(name => {
          els.dropZone.addEventListener(name, e => {
            e.preventDefault();
            els.dropZone.classList.remove('dragover');
          });
        });
        els.dropZone.addEventListener('drop', e => {
          if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
            processReferenceImageFile(e.dataTransfer.files[0]);
          }
        });
      }

      // Global paste listener when on bgStudio
      window.addEventListener('paste', e => {
        if (!views.bgStudio || views.bgStudio.hidden) return;
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        for (let item of items) {
          if (item.kind === 'file' && item.type.startsWith('image/')) {
            const blob = item.getAsFile();
            processReferenceImageFile(blob);
            break;
          }
        }
      });
    }

    function processReferenceImageFile(file) {
      const reader = new FileReader();
      reader.onload = ev => {
        const img = new Image();
        img.onload = () => {
          const colors = extractDominantColors(img, 5);
          if (colors && colors.length) {
            state.colors = colors;
            buildColorSwatches();
            renderHero();
            renderVariationsGrid();
            toast('Extracted colors from reference image and applied to design!');
          }
        };
        img.src = ev.target.result;
      };
      reader.readAsDataURL(file);
    }

    function extractDominantColors(img, count = 5) {
      const cvs = document.createElement('canvas');
      const s = 64;
      cvs.width = s; cvs.height = s;
      const ctx = cvs.getContext('2d');
      ctx.drawImage(img, 0, 0, s, s);
      const data = ctx.getImageData(0, 0, s, s).data;

      const pixels = [];
      for (let i = 0; i < data.length; i += 16) {
        const r = data[i], g = data[i+1], b = data[i+2], a = data[i+3];
        if (a > 120) {
          pixels.push([r, g, b]);
        }
      }
      if (!pixels.length) return ['#0b0f17', '#00f5b7', '#d93d5b', '#ffe8ec', '#c97a8c'];

      // Sort by perceived luminance
      pixels.sort((a, b) => (a[0]*0.299 + a[1]*0.587 + a[2]*0.114) - (b[0]*0.299 + b[1]*0.587 + b[2]*0.114));

      const res = [];
      res.push(pixels[0]); // Darkest / background
      const step = Math.floor(pixels.length / (count - 1));
      for (let k = 1; k < count; k++) {
        const idx = Math.min(pixels.length - 1, k * step);
        res.push(pixels[idx]);
      }

      return res.map(c => '#' + c.map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join(''));
    }

    // --- Export & Code Actions ---
    function copySvgToClipboard() {
      if (!state.currentSvg) return;
      const cleanSvg = G.toFile(state.currentSvg);
      navigator.clipboard.writeText(cleanSvg).then(() => {
        toast('Vector SVG code copied to clipboard!');
      }).catch(() => {
        toast('Failed to copy. Please use Show code.', true);
      });
    }

    function openCodeModal() {
      if (!els.codeModal || !els.codeTextarea) return;
      els.codeTextarea.value = G.toFile(state.currentSvg);
      els.codeModal.style.display = 'flex';
    }

    function exportSvgFile() {
      if (!state.currentSvg) return;
      const content = G.toFile(state.currentSvg);
      const blob = new Blob([content], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `vector-bg-${state.patternId}-d${state.designNo}-v${state.variationIdx}.svg`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast('SVG background file exported!');
    }

    function exportPngFile() {
      if (!state.currentSvg) return;
      const W = state.width;
      const H = state.height;

      const img = new Image();
      const svgBlob = new Blob([G.toFile(state.currentSvg)], { type: 'image/svg+xml;charset=utf-8' });
      const url = URL.createObjectURL(svgBlob);

      img.onload = () => {
        const cvs = document.createElement('canvas');
        cvs.width = W;
        cvs.height = H;
        const ctx = cvs.getContext('2d');
        ctx.drawImage(img, 0, 0, W, H);
        URL.revokeObjectURL(url);

        cvs.toBlob(blob => {
          if (!blob) {
            toast('Failed to generate PNG', true);
            return;
          }
          const pngUrl = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = pngUrl;
          a.download = `vector-bg-${state.patternId}-d${state.designNo}-v${state.variationIdx}.png`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(pngUrl);
          toast(`PNG rendered & downloaded (${W} × ${H} px)!`);
        }, 'image/png');
      };

      img.onerror = () => {
        URL.revokeObjectURL(url);
        toast('Failed to rasterize SVG for PNG', true);
      };

      img.src = url;
    }

    // Expose controller globally
    window.VectorBGStudio = {
      open: openBgStudio,
      close: returnToRedraw,
      loadDesign: loadDesignNumber,
      state: state
    };
  });
})();
