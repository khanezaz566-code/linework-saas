(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const S = {
    job: null,
    since: 0,
    version: -1,
    view: 'vector',
    sel: null,
    W: 0,
    H: 0,
    tf: { x: 0, y: 0, k: 1 },
    timer: null,
    quality: 'standard',
    icons: [],
    done: false,
    logN: 0,
    editCount: 0,
    startTime: 0,
    stageTimes: { split: 0, trace: 0, edit: 0, output: 0 }
  };

  // ---------------------------------------------------------------- helpers
  const toast = (msg, err) => {
    const t = $('#toast');
    if (!t) return;
    t.textContent = msg;
    t.className = 'toast show' + (err ? ' err' : '');
    clearTimeout(toast.t);
    toast.t = setTimeout(() => t.className = 'toast', 3400);
  };

  const api = (p, o) => fetch(p, o).then(async r => {
    if (!r.ok) {
      let m = r.statusText;
      try { m = (await r.json()).detail || m; } catch {}
      throw new Error(m);
    }
    return r;
  });

  const fmt = n => (n != null ? (n * 100).toFixed(1) + '%' : '--');

  // Health check
  fetch('/api/health')
    .then(r => r.json())
    .then(h => {
      const p = $('#health');
      if (!p) return;
      p.className = 'status-pill ok';
      const txt = $('.status-text', p) || p.lastElementChild;
      if (txt) txt.textContent = `AI Engine Online · ${h.renderer}`;
    })
    .catch(() => {
      const p = $('#health');
      if (!p) return;
      p.className = 'status-pill bad';
      const txt = $('.status-text', p) || p.lastElementChild;
      if (txt) txt.textContent = 'Engine Offline';
    });

  // ---------------------------------------------------------------- options
  const qEl = $('#quality');
  if (qEl) {
    qEl.addEventListener('click', e => {
      const b = e.target.closest('button');
      if (!b) return;
      S.quality = b.dataset.v;
      $$('#quality button').forEach(x => x.classList.toggle('on', x === b));
    });
  }

  const hint = () => {
    const cleanEl = $('#clean');
    if (!cleanEl) return;
    const v = +cleanEl.value;
    const h = $('#cleanHint');
    if (h) h.textContent = v < 0.2 ? 'Exact match' : v > 0.8 ? 'Cleanest paths' : 'Balanced';
  };
  const cleanInput = $('#clean');
  if (cleanInput) cleanInput.addEventListener('input', hint);

  // ---------------------------------------------------------------- upload & samples
  const drop = $('#drop'), file = $('#file');
  if (drop && file) {
    drop.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        file.click();
      }
    });
    file.addEventListener('change', () => file.files[0] && upload(file.files[0]));
    ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => {
      e.preventDefault();
      drop.classList.add('over');
    }));
    ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => {
      e.preventDefault();
      drop.classList.remove('over');
    }));
    drop.addEventListener('drop', e => {
      const f = e.dataTransfer.files[0];
      if (f) upload(f);
    });
  }

  window.addEventListener('paste', e => {
    const it = [...(e.clipboardData?.items || [])].find(i => i.type.startsWith('image/'));
    if (it && !S.job) upload(it.getAsFile());
  });

  $$('[data-sample]').forEach(b => b.addEventListener('click', async () => {
    try {
      const isFresh = $('#freshRun') && $('#freshRun').checked ? '&fresh=true' : '';
      const r = await api(`/api/samples/${b.dataset.sample}?quality=${S.quality}${isFresh}`, { method: 'POST' });
      begin((await r.json()).id, b.dataset.sample);
    } catch (e) {
      toast(e.message, 1);
    }
  }));

  async function upload(f) {
    const fd = new FormData();
    fd.append('file', f);
    fd.append('quality', S.quality);
    const cVal = $('#clean') ? $('#clean').value : '0.5';
    fd.append('clean', cVal);
    const isFresh = $('#freshRun') ? $('#freshRun').checked : true;
    fd.append('fresh', isFresh ? 'true' : 'false');
    try {
      const r = await api('/api/jobs', { method: 'POST', body: fd });
      begin((await r.json()).id, f.name || 'Pasted Line Art');
    } catch (e) {
      toast(e.message, 1);
    }
    if (file) file.value = '';
  }

  // ---------------------------------------------------------------- workspace lifecycle
  function begin(id, name) {
    Object.assign(S, {
      job: id,
      since: 0,
      version: -1,
      done: false,
      sel: null,
      icons: [],
      logN: 0,
      editCount: 0,
      startTime: Date.now(),
      stageTimes: { split: 0, trace: 0, edit: 0, output: 0 }
    });

    $('#landing').hidden = true;
    $('#work').hidden = false;
    $('#jobName').textContent = name;
    const meta = $('#jobMeta');
    if (meta) meta.textContent = 'Analyzing image...';

    const log = $('#log'); if (log) log.innerHTML = '';
    const icons = $('#icons'); if (icons) icons.innerHTML = '';
    const summary = $('#summary'); if (summary) summary.hidden = true;

    // Reset progress and indicators
    $('#prog').classList.remove('done');
    $('#prog i').style.width = '3%';
    const pFill = $('#procBarFill'); if (pFill) pFill.style.width = '3%';
    const pPct = $('#procPercent'); if (pPct) pPct.textContent = '3%';
    const miniFill = $('#miniProgFill'); if (miniFill) miniFill.style.width = '3%';

    // Start live processing animation on canvas
    const stg = $('#stage');
    if (stg) stg.classList.add('processing');

    const pTitle = $('#procTitle'); if (pTitle) pTitle.textContent = 'Processing...';
    const pSub = $('#procSub'); if (pSub) pSub.textContent = 'AI is analyzing and redrawing your image into clean vector paths.';
    const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Analyzing raster image...';

    // Reset stages
    resetStages();

    // Reset metrics
    updateMetricsUI(0, '--', '--', 0);

    $$('.eng').forEach(e => {
      e.className = 'eng';
      const em = $('em', e); if (em) em.textContent = '';
    });
    ['dlSvg', 'dlZip', 'copy', 'dlEps', 'btnSendToTemplate'].forEach(i => {
      const el = $('#' + i);
      if (el) el.classList.add('disabled');
    });

    $('#vec').innerHTML = '';
    $('#imgDiff').removeAttribute('src');

    const o = $('#imgOrig');
    o.onload = () => {
      S.W = o.naturalWidth;
      S.H = o.naturalHeight;
      sizeCanvas();
      fit();
      const dims = $('#artboardDims');
      if (dims && S.W && S.H) dims.textContent = `${S.W} × ${S.H} px`;
      if (meta && S.icons.length) {
        meta.textContent = `${S.icons.length} icons · ${S.W} × ${S.H}`;
      } else if (meta) {
        meta.textContent = `${S.W} × ${S.H} px`;
      }
    };
    o.src = `/api/jobs/${id}/original.png`;

    setArtboardBg('#ffffff');
    setView('vector');
    clearTimeout(S.timer);
    poll();
  }

  function cancelCurrentJob() {
    clearTimeout(S.timer);
    if (S.job) {
      api('/api/jobs/' + S.job + '/cancel', { method: 'POST' }).catch(() => {});
      S.job = null;
    }
    $('#work').hidden = true;
    const tplSt = $('#templateStudio'); if (tplSt) tplSt.hidden = true;
    $('#landing').hidden = false;
    const stg = $('#stage');
    if (stg) stg.classList.remove('processing');
  }

  $('#newJob').addEventListener('click', cancelCurrentJob);

  const navHome = $('#navHome');
  if (navHome) {
    navHome.addEventListener('click', e => {
      e.preventDefault();
      cancelCurrentJob();
    });
  }

  async function poll() {
    if (!S.job) return;
    const id = S.job;
    try {
      const j = await (await api(`/api/jobs/${id}?since=${S.since}`)).json();
      if (id !== S.job) return;
      S.since = j.next;
      ingest(j);
      if (j.status === 'cancelled') {
        toast('Job was cancelled', 0);
        const stg = $('#stage'); if (stg) stg.classList.remove('processing');
        const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Cancelled';
        return;
      }
      if (j.status === 'error') {
        toast(j.error || 'Job failed', 1);
        const stg = $('#stage'); if (stg) stg.classList.remove('processing');
        const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Processing error';
        return;
      }
      if (j.status === 'done') {
        finish(j);
        return;
      }
    } catch (e) {
      /* transient network poll */
    }
    S.timer = setTimeout(poll, 650);
  }

  // ---------------------------------------------------------------- state -> UI
  const ENGINE = { trace: 'edit', split: 'edit', edit: 'edit', output: 'output', doctor: 'doctor' };

  function resetStages() {
    ['stageImageAnalysis', 'stagePathTracing', 'stageCurveOpt', 'stageOutputGen'].forEach(id => {
      const row = $('#' + id);
      if (row) row.className = 'stage-row';
    });
    setStageTime('timeAnalysis', '0.0s');
    setStageTime('timeTracing', '--');
    setStageTime('timeCurve', '--');
    setStageTime('timeOutput', '--');
  }

  function setStageTime(id, val) {
    const el = $('#' + id);
    if (el) el.textContent = val;
  }

  function ingest(j) {
    S.icons = j.icons || [];
    const total = S.icons.length, done = S.icons.filter(i => i.status === 'done').length;
    const pct = total ? Math.min(100, Math.max(4, Math.round((done / total) * 100))) : 4;

    // Progress updates
    const progI = $('#prog i'); if (progI) progI.style.width = pct + '%';
    const pFill = $('#procBarFill'); if (pFill) pFill.style.width = pct + '%';
    const pPct = $('#procPercent'); if (pPct) pPct.textContent = pct + '%';
    const miniFill = $('#miniProgFill'); if (miniFill) miniFill.style.width = pct + '%';

    const iconCount = $('#iconCount');
    if (iconCount) iconCount.textContent = total ? `${done}/${total} icons` : '';

    if (j.width && !S.W) {
      S.W = j.width;
      S.H = j.height;
    }
    const meta = $('#jobMeta');
    if (meta && total && S.W) {
      meta.textContent = `${total} icons · ${S.W} × ${S.H}`;
    }

    // Engine events & real stage mapping
    const log = $('#log');
    let last = null;
    for (const e of j.events || []) {
      last = e;
      const eng = ENGINE[e.engine] || 'edit';
      if (eng === 'edit' && e.engine === 'edit') S.editCount++;

      // Real stage tracking
      const nowS = (Date.now() - S.startTime) / 1000;
      if (e.engine === 'split') {
        setStageActive('stageImageAnalysis');
        setStageTime('timeAnalysis', (e.t || nowS).toFixed(1) + 's');
      } else if (e.engine === 'trace') {
        setStageDone('stageImageAnalysis');
        setStageActive('stagePathTracing');
        setStageTime('timeTracing', (e.t || nowS).toFixed(1) + 's');
      } else if (e.engine === 'edit') {
        setStageDone('stageImageAnalysis');
        setStageDone('stagePathTracing');
        setStageActive('stageCurveOpt');
        setStageTime('timeCurve', (e.t || nowS).toFixed(1) + 's');
      } else if (e.engine === 'output' || e.engine === 'doctor') {
        setStageDone('stageCurveOpt');
        setStageActive('stageOutputGen');
        setStageTime('timeOutput', (e.t || nowS).toFixed(1) + 's');
      }

      if (log && S.logN++ < 400) {
        const li = document.createElement('li');
        li.innerHTML = `<s>${e.engine}</s><span>${e.msg}</span>`;
        log.appendChild(li);
      }
    }

    if (log) log.scrollTop = log.scrollHeight;

    // Status message
    const cMsg = $('#canvasStatusMsg');
    if (cMsg && last) {
      if (last.engine === 'trace') cMsg.textContent = 'Tracing centerline paths...';
      else if (last.engine === 'edit') cMsg.textContent = 'Optimizing Bezier curves & smoothing...';
      else if (last.engine === 'output') cMsg.textContent = 'Rendering vector output...';
      else if (last.engine === 'doctor') cMsg.textContent = 'Verifying match with raster image...';
    }

    // Live intermediate metrics
    const ms = S.icons.map(i => i.metrics).filter(Boolean);
    const paths = ms.reduce((a, m) => a + (m.paths || 0), 0);
    const nodes = ms.reduce((a, m) => a + (m.nodes || 0), 0);
    const elapsed = (Date.now() - S.startTime) / 1000;
    updateMetricsUI(elapsed, paths || '--', nodes || '--', (j.audit && j.audit.coincident) || 0);

    renderIcons(j);

    if (j.version !== S.version && j.version > 0) {
      S.version = j.version;
      loadSvg();
    }
  }

  function setStageActive(id) {
    const el = $('#' + id);
    if (el && !el.classList.contains('done')) {
      el.className = 'stage-row active';
    }
  }

  function setStageDone(id) {
    const el = $('#' + id);
    if (el) el.className = 'stage-row done';
  }

  function updateMetricsUI(sec, paths, nodes, dupes) {
    const mTime = $('#metricTime'); if (mTime) mTime.textContent = (sec > 0 ? sec.toFixed(1) + 's' : '0.0s');
    const mPaths = $('#metricPaths'); if (mPaths) mPaths.textContent = paths;
    const mNodes = $('#metricNodes'); if (mNodes) mNodes.textContent = nodes;
    const mDupes = $('#metricDupes'); if (mDupes) mDupes.textContent = dupes;

    const cPaths = $('#countPathsVal'); if (cPaths) cPaths.textContent = paths;
    const cNodes = $('#countNodesVal'); if (cNodes) cNodes.textContent = nodes;
  }

  // ---------------------------------------------------------------- Icon-by-Icon Match Cards
  function renderIcons(j) {
    const box = $('#icons');
    if (!box) return;

    const total = j.icons.length;
    const subText = $('#matchSubText');
    if (subText && total) {
      const avg = j.iou != null ? fmt(j.iou) : '--';
      subText.textContent = `${total} icons · Average Match ${avg}`;
    }

    j.icons.forEach(ic => {
      let el = box.children[ic.k];
      const done = ic.status === 'done';
      const pctVal = done ? ic.iou : (ic.live_iou || 0);
      const pctStr = pctVal ? fmt(pctVal) : '…';
      
      // Circumference for r=18: 2 * PI * 18 = 113.097
      const circ = 113.1;
      const offset = pctVal ? (circ * (1 - Math.min(1, Math.max(0, pctVal)))).toFixed(1) : circ;

      if (!el) {
        el = document.createElement('div');
        el.className = 'ic';
        el.dataset.k = ic.k;
        el.innerHTML = `
          <div class="ic-thumb-wrap">
            <img alt="icon-${ic.k + 1}">
          </div>
          <div class="gauge-cluster">
            <svg class="gauge-svg" viewBox="0 0 44 44">
              <circle class="gauge-bg" cx="22" cy="22" r="18" />
              <circle class="gauge-bar" cx="22" cy="22" r="18" stroke-dasharray="${circ}" stroke-dashoffset="${offset}" />
            </svg>
            <span class="gauge-text">${pctStr}</span>
          </div>
          <span class="gauge-label">Match</span>
        `;
        el.addEventListener('click', () => selectIcon(ic.k));
        box.appendChild(el);
      } else {
        const bar = $('.gauge-bar', el);
        if (bar) bar.style.strokeDashoffset = offset;
        const txt = $('.gauge-text', el);
        if (txt) txt.textContent = pctStr;
      }

      el.classList.toggle('run', !done && ic.status !== 'error');
      el.classList.toggle('err', ic.status === 'error');
      if (S.sel === ic.k) el.classList.add('sel');
      const fin = ic.metrics && ic.metrics.finisher;
      const isMem = ic.metrics && ic.metrics.from_memory;
      if (isMem) {
        el.title = `Icon ${ic.k + 1}: ${pctStr} match · (⚡ Re-used from memory cache)`;
      } else if (fin && fin.found > 0) {
        el.title = `Icon ${ic.k + 1}: ${pctStr} match · Fresh run · Finisher polished ${fin.fixed}/${fin.found} sites`;
      } else {
        el.title = `Icon ${ic.k + 1}: ${pctStr} match · Fresh run`;
      }

      const img = $('img', el);
      if (done && img && !img.dataset.ok) {
        img.dataset.ok = 1;
        let n = 0;
        const load = () => { img.src = `/api/jobs/${S.job}/icons/${ic.k}.svg?r=${n}`; };
        img.onerror = () => { if (n++ < 5) setTimeout(load, 500 * n); };
        load();
      }
    });

    // Dynamic focus tracking during live processing:
    // Follow the icon that is CURRENTLY being worked on.
    if (!S.done && j.icons.length > 0) {
      const activeIcon = j.icons.find(i => i.status === 'running') ||
                         j.icons.find(i => i.status !== 'done') ||
                         j.icons[0];
      if (activeIcon && activeIcon.box) {
        trackActiveIcon(activeIcon.k);
      }
    } else if (S.done && S.sel !== null && j.icons[S.sel]) {
      updateComparison(S.sel);
    }
  }

  // ---------------------------------------------------------------- Dynamic Active Icon Tracking
  function trackActiveIcon(k) {
    const ic = S.icons[k];
    if (!ic || !ic.box) return;

    // Highlight card in bottom carousel
    $$('.ic').forEach(x => x.classList.toggle('sel', +x.dataset.k === k));

    // Smoothly glide the green focus box over the actively processed icon
    const f = $('#focus');
    if (f) {
      f.hidden = false;
      const b = ic.box;
      Object.assign(f.style, {
        left: b[0] + 'px',
        top: b[1] + 'px',
        width: (b[2] - b[0]) + 'px',
        height: (b[3] - b[1]) + 'px'
      });
    }

    updateComparison(k);
  }

  // ---------------------------------------------------------------- Manual Selection & Comparison View
  function selectIcon(k) {
    const ic = S.icons[k];
    if (!ic) return;

    // If user clicks the already selected card, toggle it off and show full clean artboard!
    if (S.sel === k) {
      clearFocus();
      fit();
      return;
    }

    S.sel = k;
    $$('.ic').forEach(x => x.classList.toggle('sel', +x.dataset.k === k));

    const f = $('#focus');
    const b = ic.box;
    if (f && b) {
      f.hidden = false;
      Object.assign(f.style, {
        left: b[0] + 'px',
        top: b[1] + 'px',
        width: (b[2] - b[0]) + 'px',
        height: (b[3] - b[1]) + 'px'
      });
    }

    updateComparison(k);
  }

  function updateComparison(k) {
    const ic = S.icons[k];
    if (!ic) return;

    // Vector SVG preview
    const vecImg = $('#compVecImg');
    if (vecImg) {
      vecImg.src = `/api/jobs/${S.job}/icons/${k}.svg?v=${S.version}`;
    }

    // Match badge
    const badge = $('#compMatchBadge');
    if (badge) {
      const p = ic.iou != null ? ic.iou : ic.live_iou;
      const fin = ic.metrics && ic.metrics.finisher;
      let txt = p != null ? `${fmt(p)} Match` : 'Processing...';
      if (fin && fin.found > 0) {
        txt += ` · ✨ Finisher: ${fin.fixed}/${fin.found} sites`;
      }
      badge.textContent = txt;
    }

    // Crop original icon image client-side onto in-memory canvas
    const origImg = $('#imgOrig');
    const compOrig = $('#compOrigImg');
    if (origImg && compOrig && ic.box && origImg.naturalWidth) {
      try {
        const [x0, y0, x1, y1] = ic.box;
        const bw = Math.max(1, x1 - x0);
        const bh = Math.max(1, y1 - y0);
        const c = document.createElement('canvas');
        c.width = bw;
        c.height = bh;
        const ctx = c.getContext('2d');
        ctx.drawImage(origImg, x0, y0, bw, bh, 0, 0, bw, bh);
        compOrig.src = c.toDataURL();
      } catch (e) {
        compOrig.src = `/api/jobs/${S.job}/original.png`;
      }
    }
  }

  function clearFocus() {
    S.sel = null;
    const f = $('#focus');
    if (f) f.hidden = true;
    $$('.ic').forEach(x => x.classList.remove('sel'));
  }

  // ---------------------------------------------------------------- Finish Completion
  function finish(j) {
    S.done = true;

    // Stop scanning beam
    const stg = $('#stage');
    if (stg) stg.classList.remove('processing');

    // 1. Immediately remove the focus box so the entire artboard is clean!
    clearFocus();

    // 2. Fit the entire artboard so all icons are crisp and in view!
    fit();

    // 3. Ensure the artboard is pure white with black vector lines!
    setArtboardBg('#ffffff');

    // 4. Update the bottom comparison preview card with the first icon, without putting any box on the artboard
    if (j.icons.length > 0) {
      updateComparison(0);
    }

    // Global progress & Processing Card
    $('#prog').classList.add('done');
    $('#prog i').style.width = '100%';
    const pFill = $('#procBarFill'); if (pFill) pFill.style.width = '100%';
    const pPct = $('#procPercent'); if (pPct) pPct.textContent = '100%';
    const miniFill = $('#miniProgFill'); if (miniFill) miniFill.style.width = '100%';

    const pTitle = $('#procTitle');
    if (pTitle) pTitle.textContent = `Completed (${fmt(j.iou)} Match)`;
    const pSub = $('#procSub');
    if (pSub) pSub.textContent = `All ${j.icons.length} icons optimized into clean single-centerline vector paths.`;
    const cMsg = $('#canvasStatusMsg');
    if (cMsg) cMsg.textContent = 'Vector redraw complete';

    // Mark all stages done
    ['stageImageAnalysis', 'stagePathTracing', 'stageCurveOpt', 'stageOutputGen'].forEach(setStageDone);

    // Compute metrics
    const ms = j.icons.map(i => i.metrics).filter(Boolean);
    const paths = ms.reduce((a, m) => a + (m.paths || 0), 0);
    const nodes = ms.reduce((a, m) => a + (m.nodes || 0), 0);
    const dupes = (j.audit && j.audit.coincident) || 0;
    const sec = j.seconds || ((Date.now() - S.startTime) / 1000);

    updateMetricsUI(sec, paths, nodes, dupes);

    // Summary container
    const s = $('#summary');
    if (s) {
      s.hidden = false;
      const gaps = (j.audit && j.audit.gaps) || 0;
      const notches = (j.audit && j.audit.notches) || 0;
      const restored = (j.audit && j.audit.restored) || 0;
      const stray = (j.audit && j.audit.stray) || 0;
      const finFixed = (j.audit && j.audit.finisher_fixed) || 0;
      const finFound = (j.audit && j.audit.finisher_found) || 0;
      const stats = [
        ['Average Match', fmt(j.iou)],
        ['Total Icons', j.icons.length],
        ['Total Paths', paths],
        ['Total Nodes', nodes],
        ['Duplicate Centerlines', dupes],
        ['Open gaps', gaps],
        ['Notches', notches]
      ];
      if (restored > 0) stats.push(['Restored Chunks', restored]);
      if (stray > 0) stats.push(['Stray Removed', stray]);
      if (finFixed > 0 || finFound > 0) stats.push(['Finisher Engine', `${finFixed}/${finFound} sites fixed`]);
      const jTotal = (j.audit && j.audit.joints) || 0;
      const jRepaired = (j.audit && j.audit.joints_repaired) || 0;
      const jReview = (j.audit && j.audit.joints_review) || 0;
      if (jTotal > 0 || jRepaired > 0 || jReview > 0) {
        stats.push(['Join Engine', `${jTotal} joints / ${jRepaired} repaired / ${jReview} for review`]);
      }
      const sFound = (j.audit && j.audit.structure_found) || 0;
      const sFixed = (j.audit && j.audit.structure_fixed) || 0;
      const sReview = (j.audit && j.audit.structure_review) || 0;
      if (sFound > 0 || sFixed > 0 || sReview > 0) {
        stats.push(['Structure Engine', `${sFixed}/${sFound} sites fixed / ${sReview} for review`]);
      }

      if (j.set_pass) {
        if (j.set_pass.widths_changed > 0) stats.push(['Set Widths Harmonized', `${j.set_pass.widths_changed} icons`]);
        if (j.set_pass.weak && j.set_pass.weak.length > 0) stats.push(['Set Second Pass', `${j.set_pass.weak.length} weak icon(s)`]);
      }
      stats.push(['Processing Time', sec.toFixed(1) + 's']);
      s.innerHTML = stats.map(([k, v]) => `<div><span class="k">${k}</span><b>${v}</b></div>`).join('');
    }

    const imgDiff = $('#imgDiff');
    if (imgDiff) imgDiff.src = `/api/jobs/${S.job}/diff.png?v=${S.version}`;

    updateLinks();
    ['dlSvg', 'dlZip', 'copy', 'dlEps', 'btnSendToTemplate'].forEach(i => {
      const el = $('#' + i);
      if (el) el.classList.remove('disabled');
    });

    loadSvg();
    if (S.sel !== null) updateComparison(S.sel);
  }

  function renderUnresolvedJointsOverlay(svgEl, job) {
    if (!svgEl || !job || !job.icons) return;
    const oldOverlay = svgEl.querySelector('#unresolvedJointsOverlay');
    if (oldOverlay) oldOverlay.remove();

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.id = 'unresolvedJointsOverlay';
    g.setAttribute('class', 'unresolved-joints-layer');

    let count = 0;
    job.icons.forEach(ic => {
      const offX = (ic.box && ic.box[0]) || 0;
      const offY = (ic.box && ic.box[1]) || 0;
      const jn = ic.metrics && ic.metrics.joins;
      if (jn && jn.unresolved && jn.unresolved.length) {
        jn.unresolved.forEach(u => {
          const cx = offX + u.x;
          const cy = offY + u.y;
          const r = Math.max(7, (u.w || 8) * 0.9);
          const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          circle.setAttribute('cx', cx.toFixed(2));
          circle.setAttribute('cy', cy.toFixed(2));
          circle.setAttribute('r', r.toFixed(2));
          circle.setAttribute('fill', 'rgba(255, 0, 85, 0.15)');
          circle.setAttribute('stroke', '#ff0055');
          circle.setAttribute('stroke-width', '2');
          circle.setAttribute('stroke-dasharray', '4,3');

          const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
          title.textContent = `Unresolved joint: ${(u.reasons || []).join(', ')} at (${cx.toFixed(1)}, ${cy.toFixed(1)})`;
          circle.appendChild(title);

          g.appendChild(circle);
          count++;
        });
      }
      const sx = ic.metrics && ic.metrics.structure;
      if (sx && sx.unresolved && sx.unresolved.length) {
        sx.unresolved.forEach(u => {
          const cx = offX + u.x;
          const cy = offY + u.y;
          const r = Math.max(9, 12);
          const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
          circle.setAttribute('cx', cx.toFixed(2));
          circle.setAttribute('cy', cy.toFixed(2));
          circle.setAttribute('r', r.toFixed(2));
          circle.setAttribute('fill', 'rgba(255, 120, 0, 0.15)');
          circle.setAttribute('stroke', '#ff7700');
          circle.setAttribute('stroke-width', '2');
          circle.setAttribute('stroke-dasharray', '3,3');

          const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
          title.textContent = `Unresolved structure: ${u.kind} (severity ${u.severity ? u.severity.toFixed(2) : '?'}) at (${cx.toFixed(1)}, ${cy.toFixed(1)})`;
          circle.appendChild(title);

          g.appendChild(circle);
          count++;
        });
      }
    });

    if (count > 0) {
      svgEl.appendChild(g);
    }
  }

  // ---------------------------------------------------------------- vector layer + live styling
  async function loadSvg() {
    const id = S.job;
    try {
      const t = await (await api(`/api/jobs/${id}/result.svg?bg=none&v=${S.version}`)).text();
      if (id !== S.job) return;
      const vec = $('#vec');
      if (vec) {
        vec.innerHTML = t;
        $$('#vec path').forEach(p => p.dataset.w = p.getAttribute('stroke-width'));
        applyStyle();
        if (S.jobData) renderUnresolvedJointsOverlay($('#vec svg'), S.jobData);
      }
    } catch (e) {}
  }

  // ---------------------------------------------------------------- Artboard background controller
  let currentArtboardBg = '#ffffff';

  function setArtboardBg(bg) {
    currentArtboardBg = bg;

    // Update active state in topbar buttons
    $$('#artboardSwitcher .ab-btn').forEach(b => {
      b.classList.toggle('on', b.dataset.bg === bg);
    });

    // Update select element in sidebar
    const bgSelect = $('#bg');
    if (bgSelect) {
      if (bg === '#ffffff') bgSelect.value = '#ffffff';
      else if (bg === 'grid' || bg === 'none') bgSelect.value = 'none';
      else if (bg === '#0c131d' || bg === '#0b0b0c') bgSelect.value = '#0b0b0c';
    }

    const c = $('#canvas');
    if (c) {
      c.classList.remove('ab-white', 'ab-grid', 'ab-dark', 'nobg', 'dark');
      if (bg === '#ffffff') {
        c.classList.add('ab-white');
      } else if (bg === 'grid' || bg === 'none') {
        c.classList.add('ab-grid');
      } else {
        c.classList.add('ab-dark');
      }
    }

    // Auto-contrast stroke color so lines are 100% visible!
    const strokeEl = $('#stroke');
    if (bg === '#0c131d' || bg === '#0b0b0c') {
      if (strokeEl && (strokeEl.value === '#111111' || strokeEl.value === '#000000')) {
        strokeEl.value = '#ffffff';
      }
    } else {
      if (strokeEl && strokeEl.value === '#ffffff') {
        strokeEl.value = '#111111';
      }
    }

    applyStyle();
  }

  const abSwitcher = $('#artboardSwitcher');
  if (abSwitcher) {
    abSwitcher.addEventListener('click', e => {
      const b = e.target.closest('.ab-btn');
      if (b && b.dataset.bg) {
        setArtboardBg(b.dataset.bg);
      }
    });
  }

  function applyStyle() {
    const sc = $('#scale') ? +$('#scale').value : 1;
    const isDark = currentArtboardBg === '#0c131d' || currentArtboardBg === '#0b0b0c';
    const defaultCol = isDark ? '#ffffff' : '#111111';
    const col = S.view === 'overlay' ? '#ef4444' : ($('#stroke') ? $('#stroke').value : defaultCol);
    const scaleV = $('#scaleV'); if (scaleV) scaleV.textContent = Math.round(sc * 100) + '%';

    const g = $('#vec g');
    if (g) g.setAttribute('stroke', col);
    $$('#vec path').forEach(p => {
      if (p.dataset.w) p.setAttribute('stroke-width', (+p.dataset.w * sc).toFixed(2));
    });

    const c = $('#canvas');
    if (c) {
      c.classList.remove('ab-white', 'ab-grid', 'ab-dark', 'nobg', 'dark');
      if (currentArtboardBg === '#ffffff') c.classList.add('ab-white');
      else if (currentArtboardBg === 'grid' || currentArtboardBg === 'none') c.classList.add('ab-grid');
      else c.classList.add('ab-dark');
    }

    updateLinks();
  }

  ['stroke', 'scale', 'bg'].forEach(i => {
    const el = $('#' + i);
    if (el) el.addEventListener('input', applyStyle);
  });

  function qs(extra = '') {
    const strk = $('#stroke') ? $('#stroke').value : '#111111';
    const sc = $('#scale') ? $('#scale').value : '1';
    let bg = 'none';
    if (currentArtboardBg === '#ffffff') bg = '#ffffff';
    else if (currentArtboardBg === '#0c131d' || currentArtboardBg === '#0b0b0c') bg = '#0b0b0c';
    return `stroke=${encodeURIComponent(strk)}&scale=${sc}&bg=${encodeURIComponent(bg)}${extra}`;
  }

  function updateLinks() {
    if (!S.job) return;
    const dlSvg = $('#dlSvg');
    if (dlSvg) dlSvg.href = `/api/jobs/${S.job}/result.svg?${qs('&download=1')}`;

    const dlEps = $('#dlEps');
    if (dlEps) dlEps.href = `/api/jobs/${S.job}/result.eps?${qs('&download=1')}`;

    const dlZip = $('#dlZip');
    const strk = $('#stroke') ? $('#stroke').value : '#111111';
    const sc = $('#scale') ? $('#scale').value : '1';
    if (dlZip) dlZip.href = `/api/jobs/${S.job}/download.zip?stroke=${encodeURIComponent(strk)}&scale=${sc}`;
  }

  const copyBtn = $('#copy');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      try {
        const t = await (await api(`/api/jobs/${S.job}/result.svg?${qs()}`)).text();
        await navigator.clipboard.writeText(t);
        toast('SVG copied to clipboard');
      } catch (e) {
        toast('Copy failed', 1);
      }
    });
  }

  // ---------------------------------------------------------------- views
  function setView(v) {
    S.view = v;
    $$('#view button').forEach(b => b.classList.toggle('on', b.dataset.v === v));
    const o = $('#imgOrig'), d = $('#imgDiff'), vec = $('#vec');
    if (o) {
      o.style.display = (v === 'original' || v === 'overlay') ? 'block' : 'none';
      o.style.opacity = v === 'overlay' ? '0.5' : '1';
      o.style.filter = v === 'overlay' ? 'grayscale(1)' : 'none';
    }
    if (vec) vec.style.display = (v === 'vector' || v === 'overlay') ? 'block' : 'none';
    if (d) d.style.display = v === 'diff' ? 'block' : 'none';
    const leg = $('#legend'); if (leg) leg.hidden = v !== 'diff';
    applyStyle();
  }

  const vBox = $('#view');
  if (vBox) {
    vBox.addEventListener('click', e => {
      const b = e.target.closest('button');
      if (b && b.dataset.v) setView(b.dataset.v);
    });
  }

  // ---------------------------------------------------------------- pan / zoom
  const stage = $('#stage'), canvas = $('#canvas');
  function sizeCanvas() {
    if (canvas && S.W && S.H) {
      canvas.style.width = S.W + 'px';
      canvas.style.height = S.H + 'px';
    }
  }

  function paint() {
    if (canvas) {
      canvas.style.transform = `translate(${S.tf.x}px,${S.tf.y}px) scale(${S.tf.k})`;
    }
  }

  function fit(box) {
    if (!stage || !S.W) return;
    const r = stage.getBoundingClientRect();
    const b = box || [0, 0, S.W, S.H];
    const bw = b[2] - b[0], bh = b[3] - b[1];
    const pad = box ? 0.76 : 0.94;
    const k = Math.min(r.width / bw, r.height / bh) * pad;
    S.tf = {
      k,
      x: (r.width - bw * k) / 2 - b[0] * k,
      y: (r.height - bh * k) / 2 - b[1] * k
    };
    paint();
  }

  function zoomAt(f, cx, cy) {
    const k = Math.min(Math.max(S.tf.k * f, 0.05), 40);
    const r = k / S.tf.k;
    S.tf.x = cx - (cx - S.tf.x) * r;
    S.tf.y = cy - (cy - S.tf.y) * r;
    S.tf.k = k;
    paint();
  }

  if (stage) {
    stage.addEventListener('wheel', e => {
      e.preventDefault();
      const r = stage.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0016)), e.clientX - r.left, e.clientY - r.top);
    }, { passive: false });

    let drag = null;
    stage.addEventListener('pointerdown', e => {
      if (e.target.closest('.zoom-cluster')) return;
      drag = { x: e.clientX, y: e.clientY, tx: S.tf.x, ty: S.tf.y };
      stage.classList.add('drag');
      stage.setPointerCapture(e.pointerId);
    });

    stage.addEventListener('pointermove', e => {
      if (!drag) return;
      S.tf.x = drag.tx + e.clientX - drag.x;
      S.tf.y = drag.ty + e.clientY - drag.y;
      paint();
    });

    stage.addEventListener('pointerup', () => {
      drag = null;
      stage.classList.remove('drag');
    });

    stage.addEventListener('dblclick', () => {
      clearFocus();
      fit();
    });
  }

  const zIn = $('#zin');
  if (zIn) zIn.onclick = () => {
    if (!stage) return;
    const r = stage.getBoundingClientRect();
    zoomAt(1.35, r.width / 2, r.height / 2);
  };

  const zOut = $('#zout');
  if (zOut) zOut.onclick = () => {
    if (!stage) return;
    const r = stage.getBoundingClientRect();
    zoomAt(1 / 1.35, r.width / 2, r.height / 2);
  };

  const zFit = $('#zfit');
  if (zFit) zFit.onclick = () => {
    clearFocus();
    fit();
  };

  window.addEventListener('resize', () => S.job && fit());

  if (window.ResizeObserver && stage) {
    let roTimer = null;
    const ro = new ResizeObserver(() => {
      if (S.job && S.W && !S.sel) {
        clearTimeout(roTimer);
        roTimer = setTimeout(() => fit(), 30);
      }
    });
    ro.observe(stage);
  }

  // Fresh Run checkbox listener
  const freshRun = $('#freshRun');
  const freshBadge = $('#freshBadge');
  if (freshRun && freshBadge) {
    freshRun.addEventListener('change', () => {
      freshBadge.textContent = freshRun.checked ? 'Fresh (No Cache)' : 'Memory Active';
      freshBadge.style.color = freshRun.checked ? 'var(--accent)' : 'var(--text-dim)';
    });
  }

  // AI Lessons Modal & Cache Clearing
  const btnLessons = $('#btnLessons');
  const lessonsModal = $('#lessonsModal');
  const closeLessonsModal = $('#closeLessonsModal');
  const lessonsContent = $('#lessonsContent');

  async function loadLessonsModal() {
    if (!lessonsContent) return;
    lessonsContent.innerHTML = '<div style="text-align:center; padding:30px; color:var(--text-dim);">Loading memory data...</div>';
    try {
      const res = await fetch('/api/lessons');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      
      let html = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
          <div><b>Memory Corpus:</b> ${data.icons} unique icons tracked</div>
          <div><b>Skipped Passes:</b> ${data.skipped && data.skipped.length ? data.skipped.map(s => `<span class="lessons-badge badge-skip">${s}</span>`).join(' ') : 'None'}</div>
        </div>
        <div style="font-weight:600; color:#fff; margin-bottom:6px;">Finisher Pass Performance (Found vs Fixed):</div>
        <table class="lessons-table">
          <thead>
            <tr>
              <th>Pass Name</th>
              <th>Found</th>
              <th>Fixed</th>
              <th>Success Rate</th>
            </tr>
          </thead>
          <tbody>
      `;
      const passes = data.passes || {};
      const sortedPasses = Object.entries(passes).sort((a, b) => b[1].found - a[1].found);
      for (const [name, counts] of sortedPasses) {
        const rate = counts.found > 0 ? ((counts.fixed / counts.found) * 100).toFixed(1) + '%' : '0%';
        const badgeClass = counts.fixed > 0 ? 'badge-ok' : (counts.found > 100 ? 'badge-skip' : 'badge-warn');
        html += `
          <tr>
            <td><b>${name}</b></td>
            <td>${counts.found}</td>
            <td>${counts.fixed}</td>
            <td><span class="lessons-badge ${badgeClass}">${rate}</span></td>
          </tr>
        `;
      }
      html += `
          </tbody>
        </table>
      `;
      if (data.remaining_issues) {
        html += `
          <div style="margin-top:20px; font-weight:600; color:#fff; margin-bottom:6px;">Remaining Defect Census across set runs:</div>
          <div style="display:flex; flex-wrap:wrap; gap:10px; font-family:var(--font-mono); font-size:12px;">
        `;
        for (const [k, v] of Object.entries(data.remaining_issues)) {
          if (v > 0) {
            html += `<div style="background:rgba(255,255,255,0.04); padding:6px 12px; border-radius:6px; border:1px solid var(--line-dim);"><span>${k}:</span> <b style="color:#fff;">${v}</b></div>`;
          }
        }
        html += `</div>`;
      }
      lessonsContent.innerHTML = html;
    } catch (err) {
      lessonsContent.innerHTML = `<div style="color:#ff4d4d; padding:20px;">Failed to load lessons: ${err.message}</div>`;
    }
  }

  async function clearCacheAction() {
    try {
      if (S.job) {
        clearTimeout(S.timer);
        api('/api/jobs/' + S.job + '/cancel', { method: 'POST' }).catch(() => {});
        S.job = null;
      }
      const r = await api('/api/cache/clear', { method: 'POST' });
      const res = await r.json();
      const count = res.cleared ? res.cleared.best_count : 0;
      toast(`Cache cleared & engine reset! All running jobs stopped.`, 0);
      const stg = $('#stage'); if (stg) stg.classList.remove('processing');
      const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Engine reset & ready';
      if (lessonsModal && lessonsModal.style.display !== 'none') {
        loadLessonsModal();
      }
    } catch (e) {
      toast('Failed to clear cache: ' + e.message, 1);
    }
  }

  
  const btnCancelJob = $('#btnCancelJob');
  if (btnCancelJob) {
    btnCancelJob.addEventListener('click', async () => {
      if (S.job) {
        clearTimeout(S.timer);
        try {
          await api('/api/jobs/' + S.job + '/cancel', { method: 'POST' });
        } catch {}
        S.job = null;
        toast('Processing cancelled by user', 0);
        const stg = $('#stage'); if (stg) stg.classList.remove('processing');
        const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Cancelled';
        $('#landing').hidden = false;
        $('#work').hidden = true;
      }
    });
  }

  const btnClearCacheDirect = $('#btnClearCacheDirect');
  if (btnClearCacheDirect) {
    btnClearCacheDirect.addEventListener('click', clearCacheAction);
  }
  const btnClearLessons = $('#btnClearLessons');
  if (btnClearLessons) {
    btnClearLessons.addEventListener('click', clearCacheAction);
  }

  if (btnLessons && lessonsModal) {
    btnLessons.onclick = async () => {
      lessonsModal.style.display = 'flex';
      loadLessonsModal();
    };

    if (closeLessonsModal) {
      closeLessonsModal.onclick = () => {
        lessonsModal.style.display = 'none';
      };
    }
    lessonsModal.onclick = e => {
      if (e.target === lessonsModal) lessonsModal.style.display = 'none';
    };
  }

  // ================================================================
  // Presentation Template Studio Logic
  // ================================================================
  const TEMPLATE_PRESETS = {
    obsidian: {
      name: 'Obsidian Dark',
      bg: '#090d14', panel_bg: '#121824', accent: '#00f5a0',
      title_color: '#ffffff', text_color: '#ffffff', icon_stroke: '#00f5a0'
    },
    minimal: {
      name: 'Minimalist Studio',
      bg: '#f8fafc', panel_bg: '#ffffff', accent: '#0284c7',
      title_color: '#0f172a', text_color: '#0f172a', icon_stroke: '#0f172a'
    },
    cyber: {
      name: 'Cyber Neon',
      bg: '#0a0a16', panel_bg: '#131326', accent: '#f43f5e',
      title_color: '#ffffff', text_color: '#ffffff', icon_stroke: '#38bdf8'
    },
    gold: {
      name: 'Luxury Gold',
      bg: '#121110', panel_bg: '#1c1a17', accent: '#d4af37',
      title_color: '#fef3c7', text_color: '#fef3c7', icon_stroke: '#d4af37'
    },
    cream: {
      name: 'Pastel Cream',
      bg: '#faf7f2', panel_bg: '#ffffff', accent: '#e11d48',
      title_color: '#292524', text_color: '#292524', icon_stroke: '#292524'
    },
    blueprint: {
      name: 'Blueprint Tech',
      bg: '#0a192f', panel_bg: '#112240', accent: '#38bdf8',
      title_color: '#f8fafc', text_color: '#f8fafc', icon_stroke: '#38bdf8'
    }
  };

  S.template = {
    preset: 'obsidian',
    layout: 'landscape',
    zoom: 1.0
  };

  function renderPresetCards() {
    const box = $('#presetList');
    if (!box) return;
    box.innerHTML = '';
    for (const [key, p] of Object.entries(TEMPLATE_PRESETS)) {
      const el = document.createElement('div');
      el.className = 'preset-card' + (S.template.preset === key ? ' active' : '');
      el.dataset.p = key;
      el.innerHTML = `
        <div class="preset-card-name">${p.name}</div>
        <div class="preset-swatches">
          <span class="swatch-dot" style="background:${p.bg}" title="Background"></span>
          <span class="swatch-dot" style="background:${p.panel_bg}" title="Card"></span>
          <span class="swatch-dot" style="background:${p.accent}" title="Accent"></span>
          <span class="swatch-dot" style="background:${p.icon_stroke}" title="Stroke"></span>
        </div>
      `;
      el.onclick = () => selectPreset(key);
      box.appendChild(el);
    }
  }

  function selectPreset(key) {
    const p = TEMPLATE_PRESETS[key];
    if (!p) return;
    S.template.preset = key;
    $$('#presetList .preset-card').forEach(c => c.classList.toggle('active', c.dataset.p === key));
    const hint = $('#customColorHint');
    if (hint) hint.textContent = p.name;

    if ($('#tplBgColor')) $('#tplBgColor').value = p.bg;
    if ($('#tplPanelBgColor')) $('#tplPanelBgColor').value = p.panel_bg;
    if ($('#tplAccentColor')) $('#tplAccentColor').value = p.accent;
    if ($('#tplTextColor')) $('#tplTextColor').value = p.title_color;
    if ($('#tplStrokeColor')) $('#tplStrokeColor').value = p.icon_stroke;

    scheduleTemplateUpdate();
  }

  let tplUpdateTimer = null;
  function scheduleTemplateUpdate() {
    clearTimeout(tplUpdateTimer);
    tplUpdateTimer = setTimeout(updateTemplatePreview, 80);
  }

  function formatTitle(rawName) {
    if (!rawName) return 'Minimal Vector Line Icons';
    let clean = rawName.replace(/\.[^/.]+$/, '').replace(/[-_]+/g, ' ');
    clean = clean.replace(/\b\w/g, c => c.toUpperCase());
    if (!clean.toLowerCase().includes('icon')) clean += ' Icons';
    return clean;
  }

  function openTemplateStudio() {
    if (!S.job) return;
    $('#work').hidden = true;
    $('#templateStudio').hidden = false;

    // Auto-populate title if empty or default
    const titleInput = $('#tplTitle');
    if (titleInput && (!titleInput.value || titleInput.value === 'Minimal Vector Line Icons')) {
      titleInput.value = formatTitle(S.name);
    }

    renderPresetCards();
    updateTemplatePreview();
  }

  function closeTemplateStudio() {
    $('#templateStudio').hidden = true;
    $('#work').hidden = false;
    fit();
  }

  async function updateTemplatePreview() {
    if (!S.job) return;
    const title = $('#tplTitle') ? $('#tplTitle').value : 'Minimal Vector Line Icons';
    const subtitle = $('#tplSubtitle') ? $('#tplSubtitle').value : 'Clean Centerline Vector Icon Collection';
    const grid = $('#tplGrid') ? $('#tplGrid').value : '64 × 64 px Grid';
    const author = $('#tplAuthor') ? $('#tplAuthor').value : 'Linework AI Precision Engine';
    const bg = $('#tplBgColor') ? $('#tplBgColor').value : '#090d14';
    const panelBg = $('#tplPanelBgColor') ? $('#tplPanelBgColor').value : '#121824';
    const accent = $('#tplAccentColor') ? $('#tplAccentColor').value : '#00f5a0';
    const stroke = $('#tplStrokeColor') ? $('#tplStrokeColor').value : '#00f5a0';
    const scale = $('#tplStrokeScale') ? $('#tplStrokeScale').value : '1.0';
    const layout = S.template.layout || 'landscape';

    const params = new URLSearchParams({
      preset: S.template.preset || 'obsidian',
      title: title,
      subtitle: subtitle,
      grid_size: grid,
      author: author,
      layout: layout,
      stroke: stroke,
      scale: scale,
      bg: bg,
      panel_bg: panelBg,
      accent: accent,
    });

    // Update download links
    const dlSvg = $('#btnDlTemplateSvg');
    if (dlSvg) dlSvg.href = `/api/jobs/${S.job}/template.svg?${params.toString()}&download=1`;

    const dlEps = $('#btnDlTemplateEps');
    if (dlEps) dlEps.href = `/api/jobs/${S.job}/template.eps?${params.toString()}&download=1`;

    const dlZip = $('#btnDlTemplateZip');
    if (dlZip) dlZip.href = `/api/jobs/${S.job}/download.zip?stroke=${encodeURIComponent(stroke)}&scale=${scale}`;

    // Update dims indicator
    const dimsBadge = $('#tplDimsBadge');
    if (dimsBadge) {
      dimsBadge.textContent = (layout === 'square' ? '1200 × 1200 px' : '1600 × 1000 px') + ' · SVG & EPS Merged';
    }

    try {
      const res = await api(`/api/jobs/${S.job}/template.svg?${params.toString()}`);
      if (res.ok) {
        const svgContent = await res.text();
        const container = $('#templateSvgContainer');
        if (container) {
          container.innerHTML = svgContent;
        }
      }
    } catch (e) {
      console.error('Failed to load template preview:', e);
    }
  }

  // Setup template listeners
  const btnSendToTemplate = $('#btnSendToTemplate');
  if (btnSendToTemplate) {
    btnSendToTemplate.addEventListener('click', () => {
      if (!S.job) {
        toast('Please load an icon sheet first', 1);
        return;
      }
      openTemplateStudio();
    });
  }

  const btnBackToWork = $('#btnBackToWork');
  if (btnBackToWork) {
    btnBackToWork.addEventListener('click', closeTemplateStudio);
  }

  // Text inputs live preview
  ['tplTitle', 'tplSubtitle', 'tplGrid', 'tplAuthor'].forEach(id => {
    const el = $('#' + id);
    if (el) el.addEventListener('input', scheduleTemplateUpdate);
  });

  // Color inputs live preview
  ['tplBgColor', 'tplPanelBgColor', 'tplAccentColor', 'tplTextColor', 'tplStrokeColor'].forEach(id => {
    const el = $('#' + id);
    if (el) {
      el.addEventListener('input', () => {
        $$('#presetList .preset-card').forEach(c => c.classList.remove('active'));
        const hint = $('#customColorHint');
        if (hint) hint.textContent = 'Custom Preset';
        scheduleTemplateUpdate();
      });
    }
  });

  // Stroke scale slider
  const tplScale = $('#tplStrokeScale');
  const tplScaleVal = $('#tplScaleVal');
  if (tplScale && tplScaleVal) {
    tplScale.addEventListener('input', () => {
      tplScaleVal.textContent = Math.round(tplScale.value * 100) + '%';
      scheduleTemplateUpdate();
    });
  }

  // Layout switcher
  $$('#tplLayoutSeg button').forEach(b => {
    b.addEventListener('click', () => {
      $$('#tplLayoutSeg button').forEach(x => x.classList.toggle('on', x === b));
      S.template.layout = b.dataset.v;
      scheduleTemplateUpdate();
    });
  });

  // Zoom controls for template studio
  let tplZoom = 1.0;
  function setTemplateZoom(z) {
    tplZoom = Math.min(Math.max(z, 0.4), 2.5);
    const container = $('#templateSvgContainer');
    if (container) {
      container.style.transform = `scale(${tplZoom})`;
    }
  }

  const tplZin = $('#tplZin');
  if (tplZin) tplZin.onclick = () => setTemplateZoom(tplZoom * 1.2);
  const tplZout = $('#tplZout');
  if (tplZout) tplZout.onclick = () => setTemplateZoom(tplZoom / 1.2);
  const tplZfit = $('#tplZfit');
  if (tplZfit) tplZfit.onclick = () => setTemplateZoom(1.0);

  hint();
})();
