/**
 * Vector BG Studio - Parametric Vector Background Generator Controller
 * Linework AI SaaS Integration
 * Pure client-side SVG generation with zero dependencies, 510 designs & infinite variations.
 */
(() => {
  'use strict';

  // Wait for DOM and BGGen
  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(() => {
    const G = window.BGGen;
    if (!G) {
      console.warn('BGGen library not detected. Vector BG Studio will wait.');
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
      params: {},
      colors: [],
      paletteName: 'Original',
      hue: 0,
      rotate: 0,
      transparent: false,
      width: 1920,
      height: 1080,
      zoom: 1.0,
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
      home: $('#navHome'),
      redraw: $('#navRedraw'),
      bgStudio: $('#navBgStudio'),
      projects: $('#navProjects'),
      templates: $('#navTemplates'),
      settings: $('#navSettings')
    };

    const els = {
      badge: $('#bgDesignBadge'),
      prevDesign: $('#bgPrevDesign'),
      nextDesign: $('#bgNextDesign'),
      designNum: $('#bgDesignNum'),
      btnNewVariation: $('#btnBgNewVariation'),
      btnShuffle: $('#btnBgShuffle'),
      btnExportSvg: $('#btnBgExportSvg'),
      btnBack: $('#btnBackFromBgStudio'),
      designName: $('#bgCurrentDesignName'),
      catTabs: $('#bgCatTabs'),
      patternSelect: $('#bgPatternSelect'),
      moodSelect: $('#bgMoodSelect'),
      strengthSeg: $('#bgStrengthSeg'),
      varPrev: $('#bgVarPrev'),
      varNext: $('#bgVarNext'),
      varVal: $('#bgVarIndexVal'),
      paramsPanel: $('#bgParamsPanel'),
      paramsList: $('#bgParamsList'),
      btnResetParams: $('#btnResetParams'),
      paletteSelect: $('#bgPaletteSelect'),
      colorsList: $('#bgColorsList'),
      hueShift: $('#bgHueShift'),
      hueVal: $('#bgHueVal'),
      transparent: $('#bgTransparent'),
      sizeSelect: $('#bgSizeSelect'),
      rotate: $('#bgRotate'),
      rotateVal: $('#bgRotateVal'),
      metaDesc: $('#bgLiveMetaDesc'),
      zOut: $('#bgZout'),
      zFit: $('#bgZfit'),
      zIn: $('#bgZin'),
      stage: $('#bgStage'),
      svgContainer: $('#bgSvgContainer'),
      btnCopySvg: $('#btnBgCopySvg'),
      btnShowCode: $('#btnBgShowCode'),
      btnDownloadPng: $('#btnBgDownloadPng'),
      btnSendToTemplate: $('#btnBgSendToTemplate'),
      shapesCount: $('#bgShapesCount'),
      byteSize: $('#bgByteSize'),
      hashTag: $('#bgHashTag'),
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

      // Update Nav active classes
      $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
      if (navs.bgStudio) navs.bgStudio.classList.add('active');

      if (!state.initialized) {
        initStudio();
      } else {
        render();
      }
    }

    function returnToRedraw() {
      if (views.bgStudio) views.bgStudio.hidden = true;
      if (views.templateStudio) views.templateStudio.hidden = true;

      // Update Nav active classes
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

    // Attach navigation clicks
    if (navs.bgStudio) {
      navs.bgStudio.addEventListener('click', e => {
        e.preventDefault();
        openBgStudio();
      });
    }

    if (navs.redraw) {
      navs.redraw.addEventListener('click', e => {
        // Redraw nav click
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

      // Populate Moods
      if (els.moodSelect && G.moods) {
        els.moodSelect.innerHTML = G.moods.map((m, idx) => `<option value="${idx}">${m}</option>`).join('');
        els.moodSelect.addEventListener('change', e => {
          state.moodIdx = parseInt(e.target.value, 10) || 0;
          state.variationIdx = 0;
          syncDesignFromPatternAndMood();
          render();
        });
      }

      // Populate Palettes
      if (els.paletteSelect && G.libraryPalettes) {
        let palHtml = '<option value="__current__">Original Palette</option>';
        G.libraryPalettes.forEach((p, idx) => {
          palHtml += `<option value="${idx}">${p.name} (${p.c.length} colors)</option>`;
        });
        els.paletteSelect.innerHTML = palHtml;
        els.paletteSelect.addEventListener('change', e => {
          const val = e.target.value;
          if (val !== '__current__') {
            const pal = G.libraryPalettes[parseInt(val, 10)];
            if (pal && pal.c) {
              state.colors = pal.c.slice();
              buildColorPickers();
              render();
            }
          }
        });
      }

      // Populate Patterns with category filtering
      updatePatternDropdown();

      // Category tab clicks
      if (els.catTabs) {
        els.catTabs.addEventListener('click', e => {
          const tab = e.target.closest('.bg-cat-tab');
          if (!tab) return;
          $$('.bg-cat-tab', els.catTabs).forEach(b => b.classList.remove('active'));
          tab.classList.add('active');
          state.activeCat = tab.dataset.cat || 'all';
          updatePatternDropdown();
        });
      }

      // Steppers & Number Input
      if (els.prevDesign) {
        els.prevDesign.addEventListener('click', () => {
          loadDesignNumber(Math.max(1, state.designNo - 1));
        });
      }
      if (els.nextDesign) {
        els.nextDesign.addEventListener('click', () => {
          loadDesignNumber(Math.min(G.designCount(), state.designNo + 1));
        });
      }
      if (els.designNum) {
        els.designNum.addEventListener('change', e => {
          const val = parseInt(e.target.value, 10);
          if (!isNaN(val)) {
            loadDesignNumber(Math.max(1, Math.min(G.designCount(), val)));
          }
        });
      }

      // New Variation & Shuffle
      if (els.btnNewVariation) {
        els.btnNewVariation.addEventListener('click', () => {
          state.variationIdx++;
          updateVariationUI();
          render();
        });
      }

      if (els.btnShuffle) {
        els.btnShuffle.addEventListener('click', () => {
          const rndDesign = Math.floor(Math.random() * G.designCount()) + 1;
          loadDesignNumber(rndDesign);
          toast(`Shuffled to Design #${rndDesign}: ${state.designName ? state.designName.textContent : ''}`);
        });
      }

      // Variation Stepper
      if (els.varPrev) {
        els.varPrev.addEventListener('click', () => {
          if (state.variationIdx > 0) {
            state.variationIdx--;
            updateVariationUI();
            render();
          }
        });
      }
      if (els.varNext) {
        els.varNext.addEventListener('click', () => {
          state.variationIdx++;
          updateVariationUI();
          render();
        });
      }

      // Strength Segment
      if (els.strengthSeg) {
        els.strengthSeg.addEventListener('click', e => {
          const btn = e.target.closest('.bg-seg-btn');
          if (!btn) return;
          $$('.bg-seg-btn', els.strengthSeg).forEach(b => b.classList.remove('on'));
          btn.classList.add('on');
          state.strength = btn.dataset.v || 'medium';
          if (state.variationIdx > 0) {
            render();
          }
        });
      }

      // Reset Params
      if (els.btnResetParams) {
        els.btnResetParams.addEventListener('click', () => {
          const pat = G.byId[state.patternId];
          if (pat) {
            state.params = Object.assign({}, G.defaults(state.patternId));
            buildParamSliders();
            render();
            toast('Parameters reset to default');
          }
        });
      }

      // Hue Shift
      if (els.hueShift) {
        els.hueShift.addEventListener('input', e => {
          state.hue = parseInt(e.target.value, 10) || 0;
          if (els.hueVal) els.hueVal.textContent = state.hue + '°';
          scheduleDebouncedRender();
        });
      }

      // Transparent Background
      if (els.transparent) {
        els.transparent.addEventListener('change', e => {
          state.transparent = !!e.target.checked;
          render();
        });
      }

      // Canvas Size Select
      if (els.sizeSelect) {
        els.sizeSelect.addEventListener('change', e => {
          const [w, h] = e.target.value.split('x').map(Number);
          if (w && h) {
            state.width = w;
            state.height = h;
            render();
          }
        });
      }

      // Pattern Rotation
      if (els.rotate) {
        els.rotate.addEventListener('input', e => {
          state.rotate = parseInt(e.target.value, 10) || 0;
          if (els.rotateVal) els.rotateVal.textContent = state.rotate + '°';
          scheduleDebouncedRender();
        });
      }

      // Zoom Controls
      if (els.zIn) els.zIn.addEventListener('click', () => setZoom(state.zoom * 1.25));
      if (els.zOut) els.zOut.addEventListener('click', () => setZoom(state.zoom / 1.25));
      if (els.zFit) els.zFit.addEventListener('click', () => setZoom(1.0));

      // Action Buttons
      if (els.btnCopySvg) {
        els.btnCopySvg.addEventListener('click', copySvgToClipboard);
      }
      if (els.btnShowCode) {
        els.btnShowCode.addEventListener('click', openCodeModal);
      }
      if (els.btnExportSvg) {
        els.btnExportSvg.addEventListener('click', exportSvgFile);
      }
      if (els.btnDownloadPng) {
        els.btnDownloadPng.addEventListener('click', exportPngFile);
      }
      if (els.btnSendToTemplate) {
        els.btnSendToTemplate.addEventListener('click', sendColorsToTemplateStudio);
      }

      // Modal Controls
      if (els.btnModalCopyCode) {
        els.btnModalCopyCode.addEventListener('click', () => {
          if (els.codeTextarea) {
            navigator.clipboard.writeText(els.codeTextarea.value).then(() => {
              toast('SVG markup copied to clipboard!');
            }).catch(() => {
              els.codeTextarea.select();
              document.execCommand('copy');
              toast('SVG markup copied to clipboard!');
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
          if (e.target === els.codeModal) {
            els.codeModal.style.display = 'none';
          }
        });
      }

      // Load initial design #1
      loadDesignNumber(1);
    }

    function updatePatternDropdown() {
      if (!els.patternSelect || !G.patterns) return;
      const cat = state.activeCat;
      const filtered = G.patterns.filter(p => cat === 'all' || p.cat === cat);
      
      els.patternSelect.innerHTML = filtered.map(p => 
        `<option value="${p.id}" ${p.id === state.patternId ? 'selected' : ''}>${p.name} (${p.cat})</option>`
      ).join('');

      els.patternSelect.onchange = e => {
        state.patternId = e.target.value;
        state.variationIdx = 0;
        syncDesignFromPatternAndMood();
        render();
      };
    }

    function syncDesignFromPatternAndMood() {
      // Find matching design number
      const dNo = G.designNumber(state.patternId, state.moodIdx);
      if (dNo >= 1 && dNo <= G.designCount()) {
        state.designNo = dNo;
        const d = G.designAt(dNo);
        state.params = Object.assign({}, d.params);
        state.colors = d.colors.slice();
        state.paletteName = d.paletteName;
      } else {
        state.params = Object.assign({}, G.defaults(state.patternId));
        state.colors = G.defaultColors(state.patternId).slice();
      }
      updateDesignUI();
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
      state.hue = 0;
      state.rotate = 0;

      // Sync active category if needed
      const pat = G.byId[d.pattern];
      if (pat && state.activeCat !== 'all' && pat.cat !== state.activeCat) {
        state.activeCat = 'all';
        $$('.bg-cat-tab', els.catTabs).forEach(b => b.classList.toggle('active', b.dataset.cat === 'all'));
        updatePatternDropdown();
      }

      updateDesignUI();
      render();
    }

    function updateDesignUI() {
      if (els.designNum) els.designNum.value = state.designNo;
      if (els.badge) els.badge.textContent = `Design #${state.designNo} of ${G.designCount()}`;
      
      const d = G.designAt(state.designNo);
      if (els.designName) els.designName.textContent = d ? d.name : state.patternId;
      
      if (els.patternSelect) els.patternSelect.value = state.patternId;
      if (els.moodSelect) els.moodSelect.value = state.moodIdx;
      if (els.hueShift) els.hueShift.value = state.hue;
      if (els.hueVal) els.hueVal.textContent = state.hue + '°';
      if (els.rotate) els.rotate.value = state.rotate;
      if (els.rotateVal) els.rotateVal.textContent = state.rotate + '°';
      if (els.paletteSelect) els.paletteSelect.value = '__current__';

      updateVariationUI();
      buildParamSliders();
      buildColorPickers();
    }

    function updateVariationUI() {
      if (els.varVal) {
        els.varVal.textContent = state.variationIdx === 0 ? 'Var #0 (Original)' : `Var #${state.variationIdx}`;
      }
    }

    function buildParamSliders() {
      if (!els.paramsList) return;
      const pat = G.byId[state.patternId];
      if (!pat || !pat.params || !pat.params.length) {
        els.paramsList.innerHTML = '<div style="color:var(--text-muted); font-size:12px; padding:10px 0;">No tunable parameters for this pattern.</div>';
        return;
      }

      els.paramsList.innerHTML = pat.params.map(p => {
        const val = state.params[p.key] !== undefined ? state.params[p.key] : p.def;
        return `
          <div class="form-row" style="margin-bottom:8px;">
            <div class="flex-between">
              <label for="bgParam_${p.key}">${p.label}</label>
              <span class="opt-val" id="bgParamVal_${p.key}">${val}</span>
            </div>
            <input type="range" class="range-slider" id="bgParam_${p.key}"
              data-key="${p.key}" min="${p.min}" max="${p.max}" step="${p.step}" value="${val}">
          </div>
        `;
      }).join('');

      // Wire live input events
      $$('input[type="range"]', els.paramsList).forEach(slider => {
        slider.addEventListener('input', e => {
          const k = e.target.dataset.key;
          const v = parseFloat(e.target.value);
          state.params[k] = v;
          const valEl = $(`#bgParamVal_${k}`);
          if (valEl) valEl.textContent = v;
          scheduleDebouncedRender();
        });
      });
    }

    function buildColorPickers() {
      if (!els.colorsList) return;
      const pat = G.byId[state.patternId];
      const colLabels = (pat && pat.colors) || ['Background', 'Shape 1', 'Shape 2'];

      els.colorsList.innerHTML = colLabels.map((lbl, idx) => {
        const c = state.colors[idx] || (G.defaultColors(state.patternId)[idx] || '#00f5a0');
        return `
          <div class="bg-color-swatch-item">
            <div class="color-picker-wrap" style="position:relative; width:28px; height:28px; border-radius:6px; overflow:hidden; border:1px solid rgba(255,255,255,0.2);">
              <input type="color" data-idx="${idx}" value="${c}" style="position:absolute; top:-6px; left:-6px; width:40px; height:40px; border:none; cursor:pointer;">
            </div>
            <div style="display:flex; flex-direction:column; gap:1px; flex:1;">
              <span style="font-size:11px; color:var(--text-muted); font-weight:500;">${lbl}</span>
              <span class="bg-hex-label" id="bgHex_${idx}" style="font-family:monospace; font-size:11px; color:var(--text-bright);">${c}</span>
            </div>
          </div>
        `;
      }).join('');

      $$('input[type="color"]', els.colorsList).forEach(picker => {
        picker.addEventListener('input', e => {
          const idx = parseInt(e.target.dataset.idx, 10);
          state.colors[idx] = e.target.value;
          const hexEl = $(`#bgHex_${idx}`);
          if (hexEl) hexEl.textContent = e.target.value;
          scheduleDebouncedRender();
        });
      });
    }

    let renderTimer = null;
    function scheduleDebouncedRender() {
      clearTimeout(renderTimer);
      renderTimer = setTimeout(render, 30);
    }

    function render() {
      if (!views.bgStudio || views.bgStudio.hidden) return;

      const patId = state.patternId;
      const d = G.designAt(state.designNo);

      let paramsToUse = Object.assign({}, state.params);
      let colorsToUse = state.colors.slice();
      let hueToUse = state.hue;
      let rotateToUse = state.rotate;
      let seedToUse = (d && d.seed) || 1000;

      // Apply variation if variationIdx > 0
      if (state.variationIdx > 0) {
        const v = G.variation(patId, { params: paramsToUse, colors: colorsToUse }, state.variationIdx, state.strength);
        paramsToUse = v.params;
        colorsToUse = v.colors;
        hueToUse = (state.hue + v.hue) % 360;
        rotateToUse = (state.rotate + v.rotate);
        seedToUse = v.seed;
      }

      try {
        const out = G.build(patId, {
          width: state.width,
          height: state.height,
          transparent: state.transparent,
          params: paramsToUse,
          colors: colorsToUse,
          hue: hueToUse,
          rotate: rotateToUse,
          seed: seedToUse
        });

        state.currentSvg = out.svg;

        // Render into container
        if (els.svgContainer) {
          els.svgContainer.innerHTML = out.svg;
          // Apply aspect ratio & dimensions
          const svgEl = els.svgContainer.querySelector('svg');
          if (svgEl) {
            svgEl.style.width = '100%';
            svgEl.style.height = '100%';
            svgEl.style.display = 'block';
          }
        }

        // Update meta & statistics
        const hash = G.hash(out.svg);
        if (els.metaDesc) {
          els.metaDesc.textContent = `${out.meta || 'Parametric Vector Pattern'} · ${state.width} × ${state.height} px`;
        }
        if (els.shapesCount) els.shapesCount.textContent = `${out.shapes} shapes`;
        if (els.byteSize) els.byteSize.textContent = `${(out.bytes / 1024).toFixed(1)} KB`;
        if (els.hashTag) els.hashTag.textContent = `#${hash}`;

      } catch (err) {
        console.error('Render error in Vector BG Studio:', err);
      }
    }

    function setZoom(z) {
      state.zoom = Math.min(Math.max(z, 0.25), 3.0);
      if (els.svgContainer) {
        els.svgContainer.style.transform = `scale(${state.zoom})`;
        els.svgContainer.style.transformOrigin = 'center center';
      }
    }

    function copySvgToClipboard() {
      if (!state.currentSvg) return;
      const cleanSvg = G.toFile(state.currentSvg);
      navigator.clipboard.writeText(cleanSvg).then(() => {
        toast('Vector SVG code copied to clipboard!');
      }).catch(() => {
        toast('Failed to copy. Please click Show Code.', true);
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
        const canvas = document.createElement('canvas');
        canvas.width = W;
        canvas.height = H;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, W, H);
        URL.revokeObjectURL(url);

        canvas.toBlob(blob => {
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

    function sendColorsToTemplateStudio() {
      const tplBgColor = $('#tplBgColor');
      const tplAccentColor = $('#tplAccentColor');
      const tplStrokeColor = $('#tplStrokeColor');

      if (state.colors && state.colors.length) {
        if (tplBgColor && state.colors[0]) tplBgColor.value = state.colors[0];
        if (tplAccentColor && state.colors[1]) tplAccentColor.value = state.colors[1];
        if (tplStrokeColor && state.colors[1]) tplStrokeColor.value = state.colors[1];
      }

      if (window.LineworkApp && window.LineworkApp.job) {
        window.LineworkApp.openTemplate();
      } else {
        toast('Please load an icon sheet in Redraw first to build templates', 1);
      }
    }

    // Expose controller globally if needed
    window.VectorBGStudio = {
      open: openBgStudio,
      close: returnToRedraw,
      loadDesign: loadDesignNumber,
      render: render,
      state: state
    };
  });
})();
