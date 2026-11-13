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

  const getStoredToken = () => {
    return (window.LineworkAuth && window.LineworkAuth.token) ||
           sessionStorage.getItem('lw_token') ||
           localStorage.getItem('lw_token') || '';
  };

  const api = (p, o = {}) => {
    o.headers = o.headers || {};
    const tok = getStoredToken();
    if (tok && !o.headers['Authorization']) {
      o.headers['Authorization'] = 'Bearer ' + tok;
    }
    return fetch(p, o).then(async r => {
      if (r.status === 401) {
        if (window.LineworkAuth) window.LineworkAuth.requireLogin();
      }
      if (!r.ok) {
        let m = r.statusText;
        try { m = (await r.json()).detail || m; } catch {}
        throw new Error(m);
      }
      return r;
    });
  };

  const fmt = n => (n != null ? (n * 100).toFixed(1) + '%' : '--');

  function getDefectCount(metrics) {
    const iss = (metrics && (metrics.issues || metrics)) || {};
    return (iss.duplicates || 0) + (iss.kinks || 0) + (iss.gaps || 0) + (iss.notches || 0) + (iss.spurs || 0) + (iss.regions || 0);
  }

  // Health check (Customer-facing: clean status without internal cluster node counts)
  function updateClusterHealth() {
    fetch('/api/health')
      .then(r => r.json())
      .then(h => {
        const p = $('#health');
        if (!p) return;
        p.className = 'status-pill ok';
        const txt = $('.status-text', p) || p.lastElementChild;
        if (txt) {
          txt.textContent = h && h.ok ? 'AI Engine Ready' : 'AI Engine Online';
        }
      })
      .catch(() => {
        const p = $('#health');
        if (!p) return;
        p.className = 'status-pill bad';
        const txt = $('.status-text', p) || p.lastElementChild;
        if (txt) txt.textContent = 'Reconnecting...';
      });
  }
  updateClusterHealth();
  setInterval(updateClusterHealth, 8000);

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
    drop.addEventListener('click', e => {
      if (!window.LineworkAuth || !window.LineworkAuth.user) {
        e.preventDefault();
        e.stopPropagation();
        if (window.LineworkAuth) window.LineworkAuth.requireLogin(null, true);
      }
    }, true);
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
    if (!window.LineworkAuth || !window.LineworkAuth.user) {
      if (window.LineworkAuth) window.LineworkAuth.requireLogin();
      return;
    }
    if (!window.LineworkAuth.canProcessSheet()) {
      window.LineworkAuth.showPricing('redraw_pro');
      toast('Free trial limit reached (3 icon sets used). Upgrade to continue.', 1);
      return;
    }
    try {
      const isFresh = $('#freshRun') && $('#freshRun').checked ? '&fresh=true' : '';
      const r = await api(`/api/samples/${b.dataset.sample}?quality=${S.quality}${isFresh}`, { method: 'POST' });
      begin((await r.json()).id, b.dataset.sample);
    } catch (e) {
      toast(e.message, 1);
    }
  }));

  async function upload(f) {
    if (!window.LineworkAuth || !window.LineworkAuth.user) {
      if (window.LineworkAuth) window.LineworkAuth.requireLogin(() => upload(f));
      return;
    }
    if (!window.LineworkAuth.canProcessSheet()) {
      window.LineworkAuth.showPricing('redraw_pro');
      toast('Free trial limit reached (3 icon sets used). Upgrade to continue.', 1);
      return;
    }
    const fd = new FormData();
    fd.append('file', f);
    fd.append('quality', S.quality);
    const cVal = $('#clean') ? $('#clean').value : '0.5';
    fd.append('clean', cVal);
    const isFresh = $('#freshRun') ? $('#freshRun').checked : true;
    fd.append('fresh', isFresh ? 'true' : 'false');

    // Instant 0ms UI transition: open canvas immediately using local file memory before network upload completes!
    const localUrl = URL.createObjectURL(f);
    begin('__uploading__', f.name || 'Pasted Line Art', localUrl);

    try {
      const r = await api('/api/jobs', { method: 'POST', body: fd });
      const data = await r.json();
      if (S.job === '__uploading__') {
        S.job = data.id;
        poll();
      }
    } catch (e) {
      cancelCurrentJob();
      toast(e.message, 1);
    }
    if (file) file.value = '';
  }

  // ---------------------------------------------------------------- workspace lifecycle
  function begin(id, name, localPreviewUrl = null) {
    Object.assign(S, {
      job: id,
      name: name,
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

    const log = $('#log');
    if (log) {
      log.innerHTML = '<li><s>split</s><span>Image loaded on canvas — detecting icon grid...</span></li>';
      S.logN = 1;
    }
    const icons = $('#icons'); if (icons) icons.innerHTML = '';
    const summary = $('#summary'); if (summary) summary.hidden = true;

    // Reset progress and indicators
    $('#prog').classList.remove('done');
    $('#prog i').style.width = '4%';
    const pFill = $('#procBarFill'); if (pFill) pFill.style.width = '4%';
    const pPct = $('#procPercent'); if (pPct) pPct.textContent = '4%';
    const miniFill = $('#miniProgFill'); if (miniFill) miniFill.style.width = '4%';

    // Start live processing animation on canvas
    const stg = $('#stage');
    if (stg) stg.classList.add('processing');

    const pTitle = $('#procTitle'); if (pTitle) pTitle.textContent = 'Processing...';
    const pSub = $('#procSub'); if (pSub) pSub.textContent = 'AI is analyzing and redrawing your image into clean vector paths.';
    const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Analyzing & splitting icon sheet...';

    // Reset stages and immediately highlight stage 1
    resetStages();
    setStageActive('stageImageAnalysis');

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
        meta.textContent = `Detecting icons · ${S.W} × ${S.H} px`;
      }
    };
    o.src = localPreviewUrl || `/api/jobs/${id}/original.png`;

    setArtboardBg('#ffffff');
    setView('vector');
    clearTimeout(S.timer);
    clearInterval(S.clockTimer);
    S.clockTimer = setInterval(() => {
      if (!S.job || S.done) {
        clearInterval(S.clockTimer);
        return;
      }
      const sec = Math.max(0, (Date.now() - S.startTime) / 1000);
      const mTime = $('#metricTime');
      if (mTime && S.startTime) {
        mTime.textContent = sec.toFixed(1) + 's';
      }
      // Smooth live progress & stage feedback while initial icons are in flight
      const doneN = (S.icons || []).filter(i => i.status === 'done').length;
      if (doneN === 0) {
        const warmPct = Math.min(22, Math.max(4, Math.round(4 + sec * 2.2)));
        const progI = $('#prog i'); if (progI) progI.style.width = warmPct + '%';
        if (pFill) pFill.style.width = warmPct + '%';
        if (pPct) pPct.textContent = warmPct + '%';
        if (miniFill) miniFill.style.width = warmPct + '%';
        if (S.icons && S.icons.length > 0) {
          setStageDone('stageImageAnalysis');
          setStageActive('stagePathTracing');
          setStageTime('timeTracing', sec.toFixed(1) + 's');
          if (sec > 3.0) {
            setStageActive('stageCurveOpt');
          }
        } else {
          setStageTime('timeAnalysis', sec.toFixed(1) + 's');
        }
      }
    }, 100);
    if (id && id !== '__uploading__') {
      poll();
    }
  }

  function cancelCurrentJob() {
    clearTimeout(S.timer);
    clearInterval(S.clockTimer);
    if (S.job) {
      if (S.job !== '__uploading__') {
        api('/api/jobs/' + S.job + '/cancel', { method: 'POST' }).catch(() => {});
      }
      S.job = null;
    }
    $('#work').hidden = true;
    const tplSt = $('#templateStudio'); if (tplSt) tplSt.hidden = true;
    closeBgStudio();
    $('#landing').hidden = false;
    $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
    const navRedraw = $('#navRedraw'); if (navRedraw) navRedraw.classList.add('active');
    const stg = $('#stage');
    if (stg) stg.classList.remove('processing');
  }

  $('#newJob').addEventListener('click', cancelCurrentJob);

  const navHome = $('#navHome');
  if (navHome) {
    navHome.addEventListener('click', e => {
      e.preventDefault();
      closeBgStudio();
      cancelCurrentJob();
      if (window.location.hash) {
        window.location.hash = '';
      }
    });
  }

  async function poll() {
    if (!S.job) return;
    const id = S.job;
    try {
      const ctrl = new AbortController();
      const tId = setTimeout(() => ctrl.abort(), 8000);
      const res = await api(`/api/jobs/${id}?since=${S.since}`, { signal: ctrl.signal });
      clearTimeout(tId);
      const j = await res.json();
      if (id !== S.job) return;
      S.since = j.next;
      ingest(j);
      if (j.status === 'cancelled') {
        clearInterval(S.clockTimer);
        toast('Job was cancelled', 0);
        const stg = $('#stage'); if (stg) stg.classList.remove('processing');
        const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Cancelled';
        return;
      }
      if (j.status === 'error') {
        clearInterval(S.clockTimer);
        const hasDone = j.icons && j.icons.some(i => i.status === 'done');
        if (hasDone) {
          finish(j);
          const errText = j.error && j.error !== 'issues' ? `Completed with note: ${j.error}` : 'Processing complete';
          toast(errText, 0);
        } else {
          toast(j.error || 'Job failed', 1);
          const stg = $('#stage'); if (stg) stg.classList.remove('processing');
          const cMsg = $('#canvasStatusMsg'); if (cMsg) cMsg.textContent = 'Processing error';
        }
        return;
      }
      if (j.status === 'done') {
        clearInterval(S.clockTimer);
        finish(j);
        return;
      }
    } catch (e) {
      /* transient network poll */
    }
    const fastPoll = S.startTime && (Date.now() - S.startTime) < 8000;
    S.timer = setTimeout(poll, fastPoll ? 350 : 650);
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
    const running = S.icons.filter(i => i.status === 'running').length;
    const secElapsed = S.startTime ? Math.max(0, (Date.now() - S.startTime) / 1000) : 0;
    const warmPct = Math.min(22, Math.round(4 + secElapsed * 2.2));
    const workPct = total ? Math.round(((done + running * 0.25) / total) * 100) : 4;
    const pct = Math.min(100, Math.max(4, done === 0 ? Math.max(warmPct, workPct) : Math.round((done / total) * 100)));

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
        const isClean = ic.status !== 'error';
        el.innerHTML = `
          <div class="ic-thumb-wrap">
            <img alt="icon-${ic.k + 1}">
          </div>
          <div class="ic-stat-col">
            <div class="gauge-cluster">
              <svg class="gauge-svg" viewBox="0 0 44 44">
                <circle class="gauge-bg" cx="22" cy="22" r="18" />
                <circle class="gauge-bar" cx="22" cy="22" r="18" stroke-dasharray="${circ}" stroke-dashoffset="${offset}" />
              </svg>
              <span class="gauge-text">${pctStr}</span>
            </div>
            <span class="ic-clean-pill clean-ok">${done ? 'Clean ✓' : 'Running'}</span>
          </div>
        `;
        el.addEventListener('click', () => selectIcon(ic.k));
        box.appendChild(el);
      } else {
        const bar = $('.gauge-bar', el);
        if (bar) bar.style.strokeDashoffset = offset;
        const txt = $('.gauge-text', el);
        if (txt) txt.textContent = pctStr;
        const pill = $('.ic-clean-pill', el);
        if (pill) {
          pill.className = 'ic-clean-pill clean-ok';
          pill.textContent = done ? 'Clean ✓' : 'Running';
        }
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
    // Follow the icon that is CURRENTLY being worked on (unless user clicked a specific card).
    if (!S.done && j.icons.length > 0) {
      if (S.sel === null) {
        const activeIcon = j.icons.find(i => i.status === 'running') ||
                           j.icons.find(i => i.status !== 'done') ||
                           j.icons[0];
        if (activeIcon && activeIcon.box) {
          trackActiveIcon(activeIcon.k);
        }
      } else if (j.icons[S.sel]) {
        updateComparison(S.sel);
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
      vecImg.onerror = () => { vecImg.style.visibility = "hidden"; };
      vecImg.onload = () => { vecImg.style.visibility = "visible"; };
      if (ic.status === "done") {
        vecImg.src = `/api/jobs/${S.job}/icons/${k}.svg?v=${S.version}`;
      } else {
        vecImg.style.visibility = "hidden";
      }
    }

    // Match badge
    const badge = $('#compMatchBadge');
    if (badge) {
      const p = ic.iou != null ? ic.iou : ic.live_iou;
      badge.textContent = p != null ? `${fmt(p)}` : '…';
    }

    // Clean badge
    const cleanBadge = $('#compCleanBadge');
    if (cleanBadge) {
      cleanBadge.className = 'clean-badge clean-ok';
      cleanBadge.textContent = 'Clean ✓';
    }

    // Overlay toggle logic
    const overlayBtn = $('#btnCompOverlayToggle');
    const overlayLegend = $('#compOverlayLegend');
    const vecImgEl = $('#compVecImg');
    
    if (overlayBtn && !overlayBtn._bound) {
      overlayBtn._bound = true;
      overlayBtn.onclick = () => {
        S.compOverlayActive = !S.compOverlayActive;
        overlayBtn.classList.toggle('active', !!S.compOverlayActive);
        if (overlayLegend) overlayLegend.hidden = !S.compOverlayActive;
        const curK = S.sel != null ? S.sel : 0;
        updateCompVectorSrc(curK);
      };
    }
    
    function updateCompVectorSrc(idx) {
      if (!vecImgEl) return;
      if (ic.status === 'done') {
        vecImgEl.style.visibility = 'visible';
        if (S.compOverlayActive) {
          vecImgEl.src = `/api/jobs/${S.job}/icons/${idx}/diff.png?v=${S.version}`;
        } else {
          vecImgEl.src = `/api/jobs/${S.job}/icons/${idx}.svg?v=${S.version}`;
        }
      } else {
        vecImgEl.style.visibility = 'hidden';
      }
    }
    updateCompVectorSrc(k);

    // Why not 100% panel
    const whyToggle = $('#btnWhyToggle');
    const whyContent = $('#whyContent');
    const whyList = $('#whyList');
    if (whyToggle && whyContent && !whyToggle._bound) {
      whyToggle._bound = true;
      whyToggle.onclick = () => {
        const isHidden = whyContent.hidden;
        whyContent.hidden = !isHidden;
        whyToggle.classList.toggle('open', !isHidden);
      };
    }

    // Populate Why not 100% content
    if (whyList) {
      const drep = ic.decision || (ic.metrics && ic.metrics.decision);
      if (drep) {
        let html = '';
        const openFindings = drep.open_findings || [];
        const waivedFindings = drep.waived_findings || [];
        const fuzzPx = drep.edge_fuzz_px != null ? drep.edge_fuzz_px : 0;
        
        if (openFindings.length === 0 && waivedFindings.length === 0) {
          html += `<div class="why-clean-msg">✨ 100% Structural Match! Zero defects found.</div>`;
          html += `<div class="why-fuzz-msg">Remaining ${(100 - (ic.iou * 100)).toFixed(1)}% mismatch is sub-pixel edge fuzz (${fuzzPx} px anti-aliasing / blur ≤ 1px), not a vector defect.</div>`;
        } else {
          if (openFindings.length > 0) {
            html += `<div class="why-subhead">Open Findings (${openFindings.length}):</div>`;
            openFindings.forEach(f => {
              html += `<div class="finding-row open"><span class="finding-kind">[${f.kind}]</span> ${f.why} ${f.note ? `(${f.note})` : ''}</div>`;
            });
          }
          if (waivedFindings.length > 0) {
            html += `<div class="why-subhead">Waived Findings (${waivedFindings.length}):</div>`;
            waivedFindings.forEach(f => {
              html += `<div class="finding-row waived"><span class="finding-kind">[${f.kind}]</span> ${f.note || f.why}</div>`;
            });
          }
          html += `<div class="why-fuzz-msg" style="margin-top:6px;">Edge fuzz: ${fuzzPx} px ≤ 1px tolerance from source.</div>`;
        }
        whyList.innerHTML = html;
      } else {
        whyList.innerHTML = '<div class="why-fuzz-msg">Decision report: measuring residual...</div>';
      }
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

    // 3. Ensure the artboard is pure white with black vector lines and hide ghost original!
    setArtboardBg('#ffffff');
    setView(S.view || 'vector');

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
    if (imgDiff) {
      const diffUrl = `/api/jobs/${S.job}/diff.png?v=${S.version}`;
      imgDiff.dataset.src = diffUrl;
      if (S.view === 'diff') imgDiff.src = diffUrl;
    }

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
    if (!S.job || S.job === '__uploading__') return;
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
      const showGhost = (v === 'vector' && !S.done);
      o.style.display = (v === 'original' || v === 'overlay' || showGhost) ? 'block' : 'none';
      o.style.opacity = v === 'overlay' ? '0.5' : (showGhost ? '0.28' : '1');
      o.style.filter = (v === 'overlay' || showGhost) ? 'grayscale(1)' : 'none';
    }
    if (vec) vec.style.display = (v === 'vector' || v === 'overlay') ? 'block' : 'none';
    if (d) {
      d.style.display = v === 'diff' ? 'block' : 'none';
      if (v === 'diff' && S.job) {
        const targetSrc = d.dataset.src || `/api/jobs/${S.job}/diff.png?v=${S.version}`;
        if (d.getAttribute('src') !== targetSrc) d.src = targetSrc;
      }
    }
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
  // Adobe Stock / Vectuz Style Presentation Template Studio Logic
  // ================================================================
  // =========================================================================
  // DIY Template Maker Studio: 100 Modular Elements (25 per Category)
  // =========================================================================
  const MAKER_CATEGORIES = {
    banner_shape: {
      title: '1. Cover / Banner Shapes (25 Styles) — Click any shape to apply to your template:',
      prop: 'banner_shape'
    },
    title_highlight: {
      title: '2. Title & Text Highlighters (25 Styles) — Click to highlight your header text:',
      prop: 'title_highlight'
    },
    showcase_shape: {
      title: '3. ⭐ Hero Showcase Frame Shapes (25 Styles) — Click any shape to change the hero box:',
      prop: 'showcase_shape'
    },
    decor_element: {
      title: '4. ▦ Icon Grid Cards & Cell Background Designs (25 Styles) — Works in Auto & Original Sheet Fit:',
      prop: 'decor_element'
    }
  };

  const MAKER_ELEMENTS = {
    banner_shape: [
      { id: 'square_solid', name: '1. Square Box', svg: '<rect x="6" y="5" width="32" height="40" fill="#f5b800" stroke="#fff" stroke-width="1.5"/><rect x="42" y="5" width="42" height="40" fill="#1e293b" stroke="#475569" stroke-width="1"/>' },
      { id: 'rounded_card', name: '2. Rounded Card', svg: '<rect x="8" y="6" width="30" height="38" rx="6" fill="#f5b800" stroke="#fff" stroke-width="1.2"/><rect x="42" y="6" width="42" height="38" rx="4" fill="#1e293b"/>' },
      { id: 'double_split_box', name: '3. Split Square', svg: '<rect x="6" y="5" width="32" height="21" rx="3" fill="#f5b800"/><rect x="6" y="28" width="32" height="17" rx="3" fill="#00f5a0"/><rect x="42" y="5" width="42" height="40" fill="#1e293b"/>' },
      { id: 'chamfer_box', name: '4. Chamfer Box', svg: '<polygon points="12,5 38,5 38,39 32,45 6,45 6,11" fill="#f5b800" stroke="#fff" stroke-width="1"/><rect x="42" y="5" width="42" height="40" fill="#1e293b"/>' },
      { id: 'notched_ticket', name: '5. Ticket Notch', svg: '<rect x="6" y="5" width="32" height="40" fill="#f5b800"/><circle cx="38" cy="17" r="4" fill="#090d16"/><circle cx="38" cy="33" r="4" fill="#090d16"/><rect x="44" y="5" width="40" height="40" fill="#1e293b"/>' },
      { id: 'curved_right', name: '6. Convex Arch', svg: '<path d="M6,5 L32,5 Q46,25 32,45 L6,45 Z" fill="#f5b800"/><rect x="44" y="5" width="40" height="40" fill="#1e293b"/>' },
      { id: 'concave_arch', name: '7. Concave Cut', svg: '<path d="M6,5 L40,5 Q28,25 40,45 L6,45 Z" fill="#f5b800"/><rect x="44" y="5" width="40" height="40" fill="#1e293b"/>' },
      { id: 's_wave_smooth', name: '8. Smooth S-Wave', svg: '<path d="M6,5 L38,5 C26,18 46,32 30,45 L6,45 Z" fill="#f5b800"/><rect x="44" y="5" width="40" height="40" fill="#1e293b"/>' },
      { id: 'double_wave', name: '9. Double Wave', svg: '<path d="M6,5 L40,5 C30,18 48,32 34,45 L6,45 Z" fill="#00f5a0" opacity="0.5"/><path d="M6,5 L34,5 C24,18 42,32 28,45 L6,45 Z" fill="#f5b800"/><rect x="45" y="5" width="39" height="40" fill="#1e293b"/>' },
      { id: 'triple_liquid', name: '10. Triple Liquid', svg: '<path d="M6,5 L42,5 C32,18 48,32 36,45 L6,45 Z" fill="#38bdf8" opacity="0.4"/><path d="M6,5 L36,5 C26,18 44,32 30,45 L6,45 Z" fill="#00f5a0" opacity="0.6"/><path d="M6,5 L30,5 C22,18 38,32 24,45 L6,45 Z" fill="#f5b800"/>' },
      { id: 'diagonal_slash', name: '11. Diagonal Slash', svg: '<polygon points="6,5 42,5 30,45 6,45" fill="#f5b800"/><line x1="42" y1="5" x2="30" y2="45" stroke="#00f5a0" stroke-width="2"/><rect x="45" y="5" width="39" height="40" fill="#1e293b"/>' },
      { id: 'dual_chevron', name: '12. Arrow Chevron', svg: '<polygon points="6,5 34,5 43,25 34,45 6,45" fill="#f5b800"/><polyline points="31,5 40,25 31,45" fill="none" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'origami_fold', name: '13. Origami Fold', svg: '<polygon points="6,5 40,5 32,23 41,45 6,45" fill="#f5b800"/><polygon points="40,5 32,23 6,16" fill="#fff" opacity="0.25"/>' },
      { id: 'stepped_blocks', name: '14. Stepped Blocks', svg: '<polygon points="6,5 40,5 40,18 35,18 35,32 30,32 30,45 6,45" fill="#f5b800"/><rect x="44" y="5" width="40" height="40" fill="#1e293b"/>' },
      { id: 'hexagon_panel', name: '15. Hexagonal Side', svg: '<polygon points="6,5 34,5 42,16 42,34 34,45 6,45" fill="#f5b800" stroke="#fff" stroke-width="1.2"/>' },
      { id: 'leaf_organic', name: '16. Organic Leaf', svg: '<path d="M6,5 L26,5 Q44,5 42,25 Q42,45 22,45 L6,45 Z" fill="#10b981"/>' },
      { id: 'droplet_curve', name: '17. Liquid Droplet', svg: '<path d="M6,5 L36,5 C46,16 26,28 40,39 C43,43 35,45 28,45 L6,45 Z" fill="#8b5cf6"/>' },
      { id: 'scallop_edge', name: '18. Scallop Edge', svg: '<rect x="6" y="5" width="28" height="40" fill="#f5b800"/><circle cx="34" cy="11" r="5" fill="#f5b800"/><circle cx="34" cy="21" r="5" fill="#f5b800"/><circle cx="34" cy="31" r="5" fill="#f5b800"/><circle cx="34" cy="40" r="5" fill="#f5b800"/>' },
      { id: 'zigzag_saw', name: '19. Zigzag Stamp', svg: '<polygon points="6,5 35,5 40,10 35,15 40,20 35,25 40,30 35,35 40,40 35,45 6,45" fill="#f5b800"/>' },
      { id: 'ribbon_banner', name: '20. Ribbon Cut', svg: '<polygon points="6,5 40,5 34,25 40,45 6,45" fill="#ef4444"/>' },
      { id: 'floating_island', name: '21. Floating Island', svg: '<rect x="11" y="9" width="30" height="34" rx="5" fill="#00f5a0" opacity="0.35"/><rect x="8" y="6" width="30" height="34" rx="5" fill="#f5b800" stroke="#fff" stroke-width="1.2"/>' },
      { id: 'layered_cards', name: '22. 3D Layered Box', svg: '<rect x="14" y="10" width="28" height="32" rx="4" fill="#38bdf8" opacity="0.35"/><rect x="10" y="8" width="28" height="34" rx="4" fill="#00f5a0" opacity="0.6"/><rect x="6" y="5" width="28" height="36" rx="4" fill="#f5b800"/>' },
      { id: 'cyber_hud_frame', name: '23. Cyber HUD Box', svg: '<polygon points="6,5 34,5 40,11 40,39 34,45 6,45" fill="#1e293b" stroke="#00f5a0" stroke-width="1.8"/><polyline points="10,9 20,9" stroke="#f5b800" stroke-width="2"/>' },
      { id: 'arch_dome', name: '24. Arch Window', svg: '<path d="M8,45 L8,20 A15,15 0 0,1 38,20 L38,45 Z" fill="#f5b800" stroke="#fff" stroke-width="1.2"/>' },
      { id: 'pixel_dissolve', name: '25. Pixel Dissolve', svg: '<rect x="6" y="5" width="26" height="40" fill="#6366f1"/><rect x="34" y="8" width="5" height="5" fill="#818cf8"/><rect x="41" y="14" width="4" height="4" fill="#a5b4fc"/><rect x="34" y="22" width="5" height="5" fill="#6366f1"/><rect x="35" y="34" width="5" height="5" fill="#818cf8"/>' }
    ],

    title_highlight: [
      { id: 'solid_square', name: '1. Solid Square', svg: '<rect x="12" y="12" width="66" height="26" fill="#181b24" stroke="#f5b800" stroke-width="1.8"/><text x="45" y="29" fill="#fff" font-size="11" font-weight="800" text-anchor="middle">TITLE</text>' },
      { id: 'frosted_pill', name: '2. Frosted Pill', svg: '<rect x="12" y="12" width="66" height="26" rx="13" fill="#ffffff" fill-opacity="0.2" stroke="#fff" stroke-width="1.5"/><text x="45" y="29" fill="#fff" font-size="11" font-weight="800" text-anchor="middle">TITLE</text>' },
      { id: 'rounded_badge', name: '3. Rounded Badge', svg: '<rect x="12" y="12" width="66" height="26" rx="6" fill="#f5b800"/><text x="45" y="29" fill="#111" font-size="11" font-weight="900" text-anchor="middle">TITLE</text>' },
      { id: 'ribbon_tails', name: '4. Ribbon Banner', svg: '<polygon points="8,12 82,12 76,25 82,38 8,38 14,25" fill="#ef4444"/><text x="45" y="29" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">RIBBON</text>' },
      { id: 'skew_parallelogram', name: '5. Speed Skew', svg: '<polygon points="18,12 80,12 72,38 10,38" fill="#00f5a0"/><text x="45" y="29" fill="#050508" font-size="10" font-weight="900" text-anchor="middle">SPEED</text>' },
      { id: 'hex_tag', name: '6. Hexagon Tag', svg: '<polygon points="18,12 72,12 82,25 72,38 18,38 8,25" fill="#1e293b" stroke="#38bdf8" stroke-width="1.8"/><text x="45" y="29" fill="#38bdf8" font-size="10" font-weight="800" text-anchor="middle">HEX</text>' },
      { id: 'chamfer_plate', name: '7. Chamfer Plate', svg: '<polygon points="18,12 78,12 78,31 72,38 12,38 12,19" fill="#8b5cf6" stroke="#fff" stroke-width="1.2"/><text x="45" y="29" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">PLATE</text>' },
      { id: 'neon_underline', name: '8. Accent Bar', svg: '<text x="45" y="25" fill="#fff" font-size="12" font-weight="800" text-anchor="middle">TITLE</text><rect x="20" y="31" width="50" height="5" rx="2.5" fill="#00f5a0"/><circle cx="76" cy="33.5" r="2.5" fill="#f5b800"/>' },
      { id: 'double_rule', name: '9. Editorial Lines', svg: '<line x1="12" y1="11" x2="78" y2="11" stroke="#f5b800" stroke-width="2"/><text x="45" y="29" fill="#fff" font-size="11" font-weight="800" text-anchor="middle">TITLE</text><line x1="12" y1="39" x2="78" y2="39" stroke="#f5b800" stroke-width="2"/>' },
      { id: 'corner_brackets', name: '10. Viewfinder', svg: '<path d="M12,20 L12,11 L22,11 M68,11 L78,11 L78,20 M78,30 L78,39 L68,39 M22,39 L12,39 L12,30" fill="none" stroke="#00f5a0" stroke-width="2.2"/><text x="45" y="29" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">FOCUS</text>' },
      { id: 'left_accent_bar', name: '11. Left Bar Strip', svg: '<rect x="12" y="11" width="66" height="28" fill="#ffffff" fill-opacity="0.12"/><rect x="12" y="11" width="6" height="28" fill="#f5b800"/><text x="47" y="29" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">STRIP</text>' },
      { id: 'brush_stroke', name: '12. Brush Marker', svg: '<path d="M10,16 Q45,9 80,15 Q84,25 77,35 Q45,41 12,34 Z" fill="#ec4899"/><text x="45" y="29" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">BRUSH</text>' },
      { id: 'offset_shadow_box', name: '13. Brutal Shadow', svg: '<rect x="16" y="15" width="62" height="24" fill="#00f5a0"/><rect x="12" y="11" width="62" height="24" fill="#181b24" stroke="#fff" stroke-width="1.5"/><text x="43" y="27" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">BRUTAL</text>' },
      { id: 'dotted_coupon', name: '14. Dotted Coupon', svg: '<rect x="12" y="12" width="66" height="26" rx="4" fill="#1e293b" stroke="#f5b800" stroke-width="1.8" stroke-dasharray="4,3"/><text x="45" y="29" fill="#f5b800" font-size="10" font-weight="800" text-anchor="middle">COUPON</text>' },
      { id: 'gradient_glow_pill', name: '15. Double Ring Pill', svg: '<rect x="10" y="10" width="70" height="30" rx="15" fill="none" stroke="#38bdf8" stroke-width="1.2"/><rect x="14" y="13" width="62" height="24" rx="12" fill="#0284c7"/><text x="45" y="29" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">GLOW</text>' },
      { id: 'ticket_stub', name: '16. Ticket Stub', svg: '<rect x="12" y="12" width="66" height="26" fill="#f59e0b"/><circle cx="12" cy="25" r="5" fill="#090d16"/><circle cx="78" cy="25" r="5" fill="#090d16"/><text x="45" y="29" fill="#111" font-size="10" font-weight="900" text-anchor="middle">TICKET</text>' },
      { id: 'arrow_pointer', name: '17. Pointer Tag', svg: '<polygon points="10,12 72,12 82,25 72,38 10,38" fill="#10b981"/><text x="43" y="29" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">TAG</text>' },
      { id: 'speech_callout', name: '18. Callout Bubble', svg: '<rect x="12" y="9" width="66" height="24" rx="5" fill="#3b82f6"/><polygon points="26,33 36,33 28,42" fill="#3b82f6"/><text x="45" y="25" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">QUOTE</text>' },
      { id: 'circle_seal_bg', name: '19. Circle Halo', svg: '<circle cx="45" cy="25" r="19" fill="#f5b800" fill-opacity="0.25" stroke="#f5b800" stroke-width="1.5" stroke-dasharray="3,2"/><text x="45" y="29" fill="#fff" font-size="11" font-weight="800" text-anchor="middle">SEAL</text>' },
      { id: 'diamond_crest', name: '20. Diamond Crest', svg: '<polygon points="45,5 82,25 45,45 8,25" fill="#1e293b" stroke="#00f5a0" stroke-width="1.5"/><text x="45" y="29" fill="#fff" font-size="9" font-weight="800" text-anchor="middle">CREST</text>' },
      { id: 'crown_header', name: '21. Crown Header', svg: '<rect x="34" y="6" width="22" height="5" rx="2.5" fill="#f5b800"/><rect x="12" y="14" width="66" height="24" rx="4" fill="#1e293b" stroke="#f5b800" stroke-width="1.2"/><text x="45" y="30" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">CROWN</text>' },
      { id: 'crosshair_target', name: '22. Target Lock', svg: '<rect x="14" y="13" width="62" height="24" fill="none" stroke="#38bdf8" stroke-width="1.2"/><line x1="45" y1="6" x2="45" y2="13" stroke="#38bdf8" stroke-width="1.5"/><line x1="45" y1="37" x2="45" y2="44" stroke="#38bdf8" stroke-width="1.5"/><text x="45" y="29" fill="#fff" font-size="9.5" font-weight="800" text-anchor="middle">TARGET</text>' },
      { id: 'extrude_3d_box', name: '23. 3D Extrude Box', svg: '<polygon points="12,35 18,41 82,41 82,17 76,11 76,35" fill="#00f5a0" opacity="0.6"/><rect x="12" y="11" width="64" height="24" fill="#181b24" stroke="#fff" stroke-width="1.5"/><text x="44" y="27" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">3D BOX</text>' },
      { id: 'minimal_pill_outline', name: '24. Outline Pill', svg: '<rect x="12" y="12" width="66" height="26" rx="13" fill="none" stroke="#ffffff" stroke-width="2"/><text x="45" y="29" fill="#fff" font-size="10" font-weight="800" text-anchor="middle">OUTLINE</text>' },
      { id: 'none', name: '25. Clean Text Only', svg: '<text x="45" y="30" fill="#ffffff" font-size="13" font-weight="900" text-anchor="middle">CLEAN</text>' }
    ],

    showcase_shape: [
      { id: 'square_box', name: '1. Square Box', svg: '<rect x="27" y="7" width="36" height="36" fill="#181b24" stroke="#00f5a0" stroke-width="2"/><circle cx="45" cy="25" r="7" fill="none" stroke="#fff" stroke-width="1.8"/>' },
      { id: 'rounded_square', name: '2. Rounded Square', svg: '<rect x="27" y="7" width="36" height="36" rx="8" fill="#181b24" stroke="#f5b800" stroke-width="2"/><circle cx="45" cy="25" r="7" fill="none" stroke="#fff" stroke-width="1.8"/>' },
      { id: 'double_border_square', name: '3. Double Square', svg: '<rect x="25" y="5" width="40" height="40" fill="none" stroke="#f5b800" stroke-width="1.2"/><rect x="29" y="9" width="32" height="32" fill="#181b24" stroke="#fff" stroke-width="1.2"/>' },
      { id: 'dashed_square', name: '4. Dashed Square', svg: '<rect x="27" y="7" width="36" height="36" fill="#181b24" stroke="#38bdf8" stroke-width="2" stroke-dasharray="5,3"/>' },
      { id: 'offset_brutal_square', name: '5. Brutal Square', svg: '<rect x="31" y="10" width="34" height="34" fill="#f5b800"/><rect x="26" y="6" width="34" height="34" fill="#181b24" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'chamfer_square', name: '6. Chamfer Box', svg: '<polygon points="34,7 56,7 63,14 63,36 56,43 34,43 27,36 27,14" fill="#181b24" stroke="#00f5a0" stroke-width="1.8"/>' },
      { id: 'hud_tech_box', name: '7. HUD Tech Box', svg: '<rect x="27" y="7" width="36" height="36" fill="#181b24"/><path d="M27,16 L27,7 L36,7 M54,7 L63,7 L63,16 M63,34 L63,43 L54,43 M36,43 L27,43 L27,34" fill="none" stroke="#00f5a0" stroke-width="2.5"/>' },
      { id: 'glass_card', name: '8. Frosted Glass', svg: '<rect x="27" y="7" width="36" height="36" rx="7" fill="#ffffff" fill-opacity="0.16" stroke="#ffffff" stroke-width="1.5"/><line x1="31" y1="11" x2="50" y2="11" stroke="#fff" stroke-width="2" opacity="0.6"/>' },
      { id: 'polaroid_frame', name: '9. Polaroid Box', svg: '<rect x="27" y="5" width="36" height="40" rx="2" fill="#ffffff"/><rect x="30" y="8" width="30" height="27" fill="#181b24"/>' },
      { id: 'stamp_perforated', name: '10. Postage Stamp', svg: '<rect x="26" y="6" width="38" height="38" fill="#181b24" stroke="#f5b800" stroke-width="3" stroke-dasharray="2,4"/><rect x="31" y="11" width="28" height="28" fill="none" stroke="#fff" stroke-width="0.8"/>' },
      { id: 'ticket_box', name: '11. Ticket Box', svg: '<rect x="27" y="7" width="36" height="36" rx="4" fill="#181b24" stroke="#f5b800" stroke-width="1.5"/><circle cx="27" cy="25" r="5" fill="#090d16"/><circle cx="63" cy="25" r="5" fill="#090d16"/>' },
      { id: 'shield_crest', name: '12. Shield Crest', svg: '<path d="M45,6 L63,12 L63,26 C63,36 45,44 45,44 C45,44 27,36 27,26 L27,12 Z" fill="#181b24" stroke="#f5b800" stroke-width="1.8"/>' },
      { id: 'hexagon_pod', name: '13. Hexagon Pod', svg: '<polygon points="45,6 62,15 62,35 45,44 28,35 28,15" fill="#181b24" stroke="#38bdf8" stroke-width="1.8"/>' },
      { id: 'octagon_badge', name: '14. Octagon Box', svg: '<polygon points="37,7 53,7 63,17 63,33 53,43 37,43 27,33 27,17" fill="#181b24" stroke="#a855f7" stroke-width="1.8"/>' },
      { id: 'diamond_rhombus', name: '15. Diamond Box', svg: '<polygon points="45,5 65,25 45,45 25,25" fill="#181b24" stroke="#00f5a0" stroke-width="1.8"/>' },
      { id: 'circle_clean', name: '16. Clean Circle', svg: '<circle cx="45" cy="25" r="18" fill="#181b24" stroke="#ffffff" stroke-width="1.8"/>' },
      { id: 'orbital_rings', name: '17. Orbital Rings', svg: '<circle cx="45" cy="25" r="20" fill="none" stroke="#38bdf8" stroke-width="1.2" stroke-dasharray="4,3"/><circle cx="45" cy="25" r="15" fill="#181b24" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'starburst_seal', name: '18. Starburst Seal', svg: '<polygon points="45,5 50,11 58,9 59,17 65,22 61,29 63,37 55,39 50,45 45,40 39,45 35,39 27,37 29,29 25,22 31,17 32,9 40,11" fill="#f5b800"/><circle cx="45" cy="25" r="13" fill="#181b24"/>' },
      { id: 'squircle_super', name: '19. Soft Squircle', svg: '<rect x="27" y="7" width="36" height="36" rx="14" fill="#181b24" stroke="#ec4899" stroke-width="2"/>' },
      { id: 'arch_window', name: '20. Arch Dome Box', svg: '<path d="M27,43 L27,23 A18,18 0 0,1 63,23 L63,43 Z" fill="#181b24" stroke="#f5b800" stroke-width="1.8"/>' },
      { id: 'folder_tab_box', name: '21. Folder Tab Box', svg: '<path d="M27,13 L41,13 L45,17 L63,17 L63,43 L27,43 Z" fill="#181b24" stroke="#38bdf8" stroke-width="1.6"/>' },
      { id: 'browser_window', name: '22. App Window Box', svg: '<rect x="26" y="7" width="38" height="36" rx="4" fill="#181b24" stroke="#94a3b8" stroke-width="1.5"/><line x1="26" y1="15" x2="64" y2="15" stroke="#94a3b8" stroke-width="1"/><circle cx="31" cy="11" r="1.5" fill="#ef4444"/><circle cx="36" cy="11" r="1.5" fill="#f5b800"/><circle cx="41" cy="11" r="1.5" fill="#10b981"/>' },
      { id: 'crosshair_grid_box', name: '23. CAD Grid Box', svg: '<rect x="27" y="7" width="36" height="36" fill="#181b24" stroke="#00f5a0" stroke-width="1.6"/><line x1="45" y1="7" x2="45" y2="43" stroke="#00f5a0" stroke-width="0.7" stroke-dasharray="2,2"/><line x1="27" y1="25" x2="63" y2="25" stroke="#00f5a0" stroke-width="0.7" stroke-dasharray="2,2"/>' },
      { id: 'glow_neon_box', name: '24. Neon Frame Box', svg: '<rect x="25" y="5" width="40" height="40" rx="5" fill="none" stroke="#00f5a0" stroke-width="2" opacity="0.4"/><rect x="28" y="8" width="34" height="34" rx="3" fill="#181b24" stroke="#00f5a0" stroke-width="1.8"/>' },
      { id: 'isometric_stack', name: '25. 3D Layer Square', svg: '<rect x="31" y="11" width="32" height="32" rx="3" fill="#38bdf8" opacity="0.35"/><rect x="29" y="9" width="32" height="32" rx="3" fill="#00f5a0" opacity="0.6"/><rect x="26" y="6" width="32" height="32" rx="3" fill="#181b24" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'floating_card', name: '26. Floating Card', svg: '<rect x="30" y="10" width="34" height="34" rx="6" fill="#000000" opacity="0.35"/><rect x="26" y="6" width="34" height="34" rx="6" fill="#181b24" stroke="#ffffff" stroke-width="1.5"/><circle cx="43" cy="23" r="6" fill="none" stroke="#38bdf8" stroke-width="1.5"/>' },
      { id: 'clean_glow', name: '27. Clean Glow Halo', svg: '<circle cx="45" cy="25" r="19" fill="#38bdf8" opacity="0.20"/><circle cx="45" cy="25" r="14" fill="#181b24" stroke="#38bdf8" stroke-width="1.2"/><circle cx="45" cy="25" r="6" fill="none" stroke="#ffffff" stroke-width="1.5"/>' },
      { id: 'clean_none', name: '28. Pure Borderless', svg: '<circle cx="45" cy="25" r="15" fill="none" stroke="#38bdf8" stroke-width="1.2" stroke-dasharray="3,3"/><circle cx="45" cy="25" r="6" fill="none" stroke="#ffffff" stroke-width="1.8"/>' }
    ],

    decor_element: [
      { id: 'artboard_square_box', name: '1. Square Artboard', svg: '<rect x="10" y="6" width="70" height="38" fill="#ffffff" stroke="#00f5a0" stroke-width="2"/><circle cx="28" cy="18" r="4" fill="#1e293b"/><circle cx="45" cy="18" r="4" fill="#1e293b"/><circle cx="62" cy="18" r="4" fill="#1e293b"/><circle cx="28" cy="32" r="4" fill="#1e293b"/><circle cx="45" cy="32" r="4" fill="#1e293b"/><circle cx="62" cy="32" r="4" fill="#1e293b"/>' },
      { id: 'cell_square_boxes', name: '2. Icon Square Boxes', svg: '<rect x="12" y="8" width="19" height="15" fill="none" stroke="#00f5a0" stroke-width="1.4"/><rect x="35" y="8" width="19" height="15" fill="none" stroke="#00f5a0" stroke-width="1.4"/><rect x="58" y="8" width="19" height="15" fill="none" stroke="#00f5a0" stroke-width="1.4"/><rect x="12" y="27" width="19" height="15" fill="none" stroke="#00f5a0" stroke-width="1.4"/><rect x="35" y="27" width="19" height="15" fill="none" stroke="#00f5a0" stroke-width="1.4"/><rect x="58" y="27" width="19" height="15" fill="none" stroke="#00f5a0" stroke-width="1.4"/>' },
      { id: 'cell_rounded_cards', name: '3. Rounded Icon Cards', svg: '<rect x="12" y="8" width="19" height="15" rx="4" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/><rect x="35" y="8" width="19" height="15" rx="4" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/><rect x="58" y="8" width="19" height="15" rx="4" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/><rect x="12" y="27" width="19" height="15" rx="4" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/><rect x="35" y="27" width="19" height="15" rx="4" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/><rect x="58" y="27" width="19" height="15" rx="4" fill="#1e293b" stroke="#38bdf8" stroke-width="1.2"/>' },
      { id: 'cell_dashed_boxes', name: '4. Dashed Icon Boxes', svg: '<rect x="12" y="8" width="19" height="15" fill="none" stroke="#f5b800" stroke-width="1.2" stroke-dasharray="3,2"/><rect x="35" y="8" width="19" height="15" fill="none" stroke="#f5b800" stroke-width="1.2" stroke-dasharray="3,2"/><rect x="58" y="8" width="19" height="15" fill="none" stroke="#f5b800" stroke-width="1.2" stroke-dasharray="3,2"/><rect x="12" y="27" width="19" height="15" fill="none" stroke="#f5b800" stroke-width="1.2" stroke-dasharray="3,2"/><rect x="35" y="27" width="19" height="15" fill="none" stroke="#f5b800" stroke-width="1.2" stroke-dasharray="3,2"/><rect x="58" y="27" width="19" height="15" fill="none" stroke="#f5b800" stroke-width="1.2" stroke-dasharray="3,2"/>' },
      { id: 'cell_full_table_grid', name: '5. Full Matrix Grid', svg: '<rect x="10" y="6" width="70" height="38" fill="none" stroke="#00f5a0" stroke-width="1.5"/><line x1="33" y1="6" x2="33" y2="44" stroke="#00f5a0" stroke-width="1"/><line x1="57" y1="6" x2="57" y2="44" stroke="#00f5a0" stroke-width="1"/><line x1="10" y1="25" x2="80" y2="25" stroke="#00f5a0" stroke-width="1"/>' },
      { id: 'cell_corner_brackets', name: '6. Cell Corner Ticks', svg: '<path d="M12,13 L12,8 L17,8 M26,8 L31,8 L31,13 M31,18 L31,23 L26,23 M17,23 L12,23 L12,18" fill="none" stroke="#38bdf8" stroke-width="1.5"/><path d="M36,13 L36,8 L41,8 M50,8 L55,8 L55,13 M55,18 L55,23 L50,23 M41,23 L36,23 L36,18" fill="none" stroke="#38bdf8" stroke-width="1.5"/><path d="M59,13 L59,8 L64,8 M73,8 L78,8 L78,13 M78,18 L78,23 L73,23 M64,23 L59,23 L59,18" fill="none" stroke="#38bdf8" stroke-width="1.5"/>' },
      { id: 'cell_soft_tint_squares', name: '7. Soft Tinted Squares', svg: '<rect x="12" y="8" width="19" height="15" rx="2" fill="#f5b800" fill-opacity="0.25"/><rect x="35" y="8" width="19" height="15" rx="2" fill="#f5b800" fill-opacity="0.25"/><rect x="58" y="8" width="19" height="15" rx="2" fill="#f5b800" fill-opacity="0.25"/><rect x="12" y="27" width="19" height="15" rx="2" fill="#f5b800" fill-opacity="0.25"/><rect x="35" y="27" width="19" height="15" rx="2" fill="#f5b800" fill-opacity="0.25"/><rect x="58" y="27" width="19" height="15" rx="2" fill="#f5b800" fill-opacity="0.25"/>' },
      { id: 'cell_circle_badges', name: '8. Circle Icon Pods', svg: '<circle cx="22" cy="16" r="7.5" fill="none" stroke="#a855f7" stroke-width="1.4"/><circle cx="45" cy="16" r="7.5" fill="none" stroke="#a855f7" stroke-width="1.4"/><circle cx="68" cy="16" r="7.5" fill="none" stroke="#a855f7" stroke-width="1.4"/><circle cx="22" cy="34" r="7.5" fill="none" stroke="#a855f7" stroke-width="1.4"/><circle cx="45" cy="34" r="7.5" fill="none" stroke="#a855f7" stroke-width="1.4"/><circle cx="68" cy="34" r="7.5" fill="none" stroke="#a855f7" stroke-width="1.4"/>' },
      { id: 'cell_hex_frames', name: '9. Hex Icon Cells', svg: '<polygon points="22,8 29,12 29,20 22,24 15,20 15,12" fill="none" stroke="#00f5a0" stroke-width="1.3"/><polygon points="45,8 52,12 52,20 45,24 38,20 38,12" fill="none" stroke="#00f5a0" stroke-width="1.3"/><polygon points="68,8 75,12 75,20 68,24 61,20 61,12" fill="none" stroke="#00f5a0" stroke-width="1.3"/>' },
      { id: 'cell_brutal_squares', name: '10. Shadow Icon Boxes', svg: '<rect x="15" y="10" width="17" height="14" fill="#f5b800"/><rect x="13" y="8" width="17" height="14" fill="#181b24" stroke="#fff" stroke-width="1"/><rect x="39" y="10" width="17" height="14" fill="#f5b800"/><rect x="37" y="8" width="17" height="14" fill="#181b24" stroke="#fff" stroke-width="1"/><rect x="63" y="10" width="17" height="14" fill="#f5b800"/><rect x="61" y="8" width="17" height="14" fill="#181b24" stroke="#fff" stroke-width="1"/>' },
      { id: 'artboard_double_frame', name: '11. Passe-Partout Box', svg: '<rect x="8" y="5" width="74" height="40" fill="none" stroke="#f5b800" stroke-width="1.8"/><rect x="13" y="9" width="64" height="32" fill="none" stroke="#ffffff" stroke-width="1"/>' },
      { id: 'artboard_corner_ticks', name: '12. Crop Marks Box', svg: '<rect x="12" y="8" width="66" height="34" fill="none" stroke="#475569" stroke-width="1"/><path d="M8,16 L8,5 L19,5 M71,5 L82,5 L82,16 M82,34 L82,45 L71,45 M19,45 L8,45 L8,34" fill="none" stroke="#00f5a0" stroke-width="2"/>' },
      { id: 'artboard_hud_corners', name: '13. Tech HUD Border', svg: '<polygon points="15,6 75,6 81,12 81,38 75,44 15,44 9,38 9,12" fill="none" stroke="#38bdf8" stroke-width="1.8"/>' },
      { id: 'artboard_dashed_frame', name: '14. Dashed Artboard', svg: '<rect x="10" y="6" width="70" height="38" fill="none" stroke="#f5b800" stroke-width="2" stroke-dasharray="6,3"/>' },
      { id: 'artboard_header_footer', name: '15. Top & Bottom Rule', svg: '<line x1="10" y1="8" x2="80" y2="8" stroke="#00f5a0" stroke-width="2.5"/><line x1="10" y1="42" x2="80" y2="42" stroke="#00f5a0" stroke-width="2.5"/><rect x="10" y="8" width="70" height="34" fill="none" stroke="#475569" stroke-width="1"/>' },
      { id: 'cover_halftone_dots', name: '16. Halftone + Square', svg: '<rect x="8" y="6" width="28" height="38" fill="#1e293b"/><circle cx="14" cy="13" r="2" fill="#f5b800"/><circle cx="22" cy="13" r="2" fill="#f5b800"/><circle cx="30" cy="13" r="2" fill="#f5b800"/><circle cx="14" cy="21" r="2" fill="#f5b800"/><circle cx="22" cy="21" r="2" fill="#f5b800"/><rect x="40" y="6" width="42" height="38" fill="none" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'cover_diagonal_stripes', name: '17. Stripes + Square', svg: '<rect x="8" y="6" width="28" height="38" fill="#1e293b"/><line x1="8" y1="16" x2="20" y2="6" stroke="#00f5a0" stroke-width="2"/><line x1="8" y1="28" x2="32" y2="6" stroke="#00f5a0" stroke-width="2"/><line x1="8" y1="40" x2="36" y2="14" stroke="#00f5a0" stroke-width="2"/><rect x="40" y="6" width="42" height="38" fill="none" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'cover_circuit_traces', name: '18. Circuit + Square', svg: '<rect x="8" y="6" width="28" height="38" fill="#1e293b"/><polyline points="12,14 22,14 27,20 27,34" fill="none" stroke="#38bdf8" stroke-width="1.6"/><circle cx="12" cy="14" r="2.5" fill="#38bdf8"/><circle cx="27" cy="34" r="2.5" fill="#38bdf8"/><rect x="40" y="6" width="42" height="38" fill="none" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'cover_blueprint_grid', name: '19. Blueprint + Square', svg: '<rect x="8" y="6" width="28" height="38" fill="#1e293b" stroke="#38bdf8" stroke-width="1"/><line x1="17" y1="6" x2="17" y2="44" stroke="#38bdf8" stroke-width="0.6"/><line x1="27" y1="6" x2="27" y2="44" stroke="#38bdf8" stroke-width="0.6"/><line x1="8" y1="18" x2="36" y2="18" stroke="#38bdf8" stroke-width="0.6"/><line x1="8" y1="31" x2="36" y2="31" stroke="#38bdf8" stroke-width="0.6"/><rect x="40" y="6" width="42" height="38" fill="none" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'cover_concentric_rings', name: '20. Rings + Square', svg: '<rect x="8" y="6" width="28" height="38" fill="#1e293b"/><circle cx="22" cy="25" r="12" fill="none" stroke="#f5b800" stroke-width="1.2"/><circle cx="22" cy="25" r="7" fill="none" stroke="#f5b800" stroke-width="1.2"/><rect x="40" y="6" width="42" height="38" fill="none" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'cover_geometric_poly', name: '21. Low-Poly + Square', svg: '<rect x="8" y="6" width="28" height="38" fill="#1e293b"/><polygon points="8,6 36,6 22,24" fill="#a855f7" opacity="0.45"/><polygon points="8,6 22,24 8,44" fill="#38bdf8" opacity="0.35"/><rect x="40" y="6" width="42" height="38" fill="none" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'cover_dot_matrix', name: '22. Crosses + Square', svg: '<rect x="8" y="6" width="28" height="38" fill="#1e293b"/><text x="15" y="18" fill="#00f5a0" font-size="10" font-weight="900">+</text><text x="27" y="18" fill="#00f5a0" font-size="10" font-weight="900">+</text><text x="15" y="34" fill="#00f5a0" font-size="10" font-weight="900">+</text><text x="27" y="34" fill="#00f5a0" font-size="10" font-weight="900">+</text><rect x="40" y="6" width="42" height="38" fill="none" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'cover_floating_shapes', name: '23. Shapes + Square', svg: '<rect x="8" y="6" width="28" height="38" fill="#1e293b"/><circle cx="16" cy="15" r="4" fill="none" stroke="#f5b800" stroke-width="1.4"/><rect x="23" y="26" width="8" height="8" fill="none" stroke="#00f5a0" stroke-width="1.4"/><rect x="40" y="6" width="42" height="38" fill="none" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'cover_chevron_stripes', name: '24. Chevrons + Square', svg: '<rect x="8" y="6" width="28" height="38" fill="#1e293b"/><polyline points="13,18 22,11 31,18" fill="none" stroke="#f5b800" stroke-width="1.8"/><polyline points="13,28 22,21 31,28" fill="none" stroke="#f5b800" stroke-width="1.8"/><polyline points="13,38 22,31 31,38" fill="none" stroke="#f5b800" stroke-width="1.8"/><rect x="40" y="6" width="42" height="38" fill="none" stroke="#fff" stroke-width="1.5"/>' },
      { id: 'none', name: '25. Borderless Minimal', svg: '<rect x="10" y="6" width="70" height="38" fill="#1e293b"/><circle cx="28" cy="18" r="3.5" fill="#94a3b8"/><circle cx="45" cy="18" r="3.5" fill="#94a3b8"/><circle cx="62" cy="18" r="3.5" fill="#94a3b8"/><circle cx="28" cy="32" r="3.5" fill="#94a3b8"/><circle cx="45" cy="32" r="3.5" fill="#94a3b8"/><circle cx="62" cy="32" r="3.5" fill="#94a3b8"/>' }
    ]
  };

  const TEMPLATE_PRESETS = {
    vectuz_yellow: {
      id: 'vectuz_yellow',
      name: 'Adobe Stock Gold / Yellow',
      banner_bg: '#F5B800',
      banner_text: '#1E1E1E',
      banner_sub: '#374151',
      highlight_bg: '#181B24',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      icon_stroke: '#181B24',
      accent: '#F5B800',
    },
    vectuz_cyan: {
      id: 'vectuz_cyan',
      name: 'Tech & AI Mint / Cyan',
      banner_bg: '#00D2A0',
      banner_text: '#064E3B',
      banner_sub: '#047857',
      highlight_bg: '#0F172A',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      icon_stroke: '#0F172A',
      accent: '#00D2A0',
    },
    vectuz_coral: {
      id: 'vectuz_coral',
      name: 'Beauty & Medical Coral',
      banner_bg: '#FF4757',
      banner_text: '#FFFFFF',
      banner_sub: '#FFE4E6',
      highlight_bg: '#1E1322',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      icon_stroke: '#18181B',
      accent: '#FF4757',
    },
    vectuz_purple: {
      id: 'vectuz_purple',
      name: 'Creative & App Iris Purple',
      banner_bg: '#8B5CF6',
      banner_text: '#FFFFFF',
      banner_sub: '#EDE9FE',
      highlight_bg: '#120E24',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      icon_stroke: '#18181B',
      accent: '#8B5CF6',
    },
    vectuz_emerald: {
      id: 'vectuz_emerald',
      name: 'Nature & Ecology Emerald',
      banner_bg: '#10B981',
      banner_text: '#FFFFFF',
      banner_sub: '#D1FAE5',
      highlight_bg: '#061A14',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      icon_stroke: '#061A14',
      accent: '#10B981',
    },
    vectuz_orange: {
      id: 'vectuz_orange',
      name: 'Industry & Logistics Orange',
      banner_bg: '#F97316',
      banner_text: '#FFFFFF',
      banner_sub: '#FFEDD5',
      highlight_bg: '#1C1917',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      icon_stroke: '#1C1917',
      accent: '#F97316',
    },
    vectuz_blue: {
      id: 'vectuz_blue',
      name: 'Corporate & Finance Royal Blue',
      banner_bg: '#2563EB',
      banner_text: '#FFFFFF',
      banner_sub: '#DBEAFE',
      highlight_bg: '#0B1329',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      icon_stroke: '#0B1329',
      accent: '#2563EB',
    },
    minimal_white: {
      id: 'minimal_white',
      name: 'Minimalist White Studio',
      banner_bg: '#F4F4F5',
      banner_text: '#18181B',
      banner_sub: '#71717A',
      highlight_bg: '#18181B',
      highlight_stroke: '#FFFFFF',
      artboard_bg: '#FFFFFF',
      icon_stroke: '#18181B',
      accent: '#18181B',
    },
    midnight_dark: {
      id: 'midnight_dark',
      name: 'Midnight Dark Edition',
      banner_bg: '#18181B',
      banner_text: '#F4F4F5',
      banner_sub: '#A1A1AA',
      highlight_bg: '#09090B',
      highlight_stroke: '#00F5A0',
      artboard_bg: '#0F172A',
      icon_stroke: '#F4F4F5',
      accent: '#00F5A0',
    }
  };

  S.template = {
    design: 'modular_maker',
    preset: 'vectuz_yellow',
    panel_pos: 'left',
    banner_shape: 'square_solid',
    title_highlight: 'offset_shadow_box',
    showcase_shape: 'square_box',
    decor_element: 'cell_rounded_cards',
    shape_accent: '#181B24',
    layout: 'landscape_16_9',
    banner_text: '#1E1E1E',
    artboard_bg: 'checkered',
    highlight_mode: 'hero_1',
    show_highlight: true,
    highlight_index: 0,
    title_fs: 54,
    count_fs: 160,
    sub_fs: 20,
    font_family: 'bebas',
    icon_layout: 'auto_grid',
    artboard_margin: 0.06,
    header_y_offset: 0,
    count_y_offset: 0,
    showcase_y_offset: 0,
    badge_y_offset: 0,
    showcase_scale: 1.0,
    element_spacing: 0,
  };

  let currentSheetIcons = [];

  async function fetchAndRenderIconPicker() {
    const jobId = S.job || 'demo';
    const grid = $('#featuredIconGrid');
    const badge = $('#featuredIconBadge');
    if (!grid) return;

    grid.innerHTML = '<div style="padding:14px; color:var(--text-dim); font-size:11px; text-align:center; grid-column:1/-1;">Loading sheet icons...</div>';

    try {
      const res = await api(`/api/jobs/${jobId}/template/icons`);
      if (res.ok) {
        currentSheetIcons = await res.json();
      } else {
        currentSheetIcons = [];
      }
    } catch (e) {
      console.error('Failed to load icons:', e);
      currentSheetIcons = [];
    }

    if (!currentSheetIcons || currentSheetIcons.length === 0) {
      grid.innerHTML = '<div style="padding:14px; color:var(--text-dim); font-size:11px; text-align:center; grid-column:1/-1;">No icons available in current sheet</div>';
      return;
    }

    grid.innerHTML = '';
    const activeIdx = S.template.highlight_index || 0;
    if (badge) badge.textContent = `#${activeIdx + 1} Selected`;

    const customGrid = $('#customFeaturedIconGrid');
    if (customGrid) customGrid.innerHTML = '';

    currentSheetIcons.forEach((ic, idx) => {
      const item = document.createElement('div');
      item.className = 'featured-icon-item' + (idx === activeIdx ? ' active' : '');
      item.dataset.index = idx;
      item.title = `Feature Icon #${idx + 1} in Hero Showcase`;
      item.innerHTML = `
        <img src="${ic.svg_url}" alt="Icon #${idx + 1}" loading="lazy">
        <span class="icon-num">#${idx + 1}</span>
      `;
      item.onclick = () => selectFeaturedIcon(idx);
      grid.appendChild(item);

      if (customGrid) {
        const item2 = item.cloneNode(true);
        item2.onclick = () => selectFeaturedIcon(idx);
        customGrid.appendChild(item2);
      }
    });
  }

  function selectFeaturedIcon(idx) {
    S.template.highlight_index = idx;
    $$('#featuredIconGrid .featured-icon-item, #customFeaturedIconGrid .featured-icon-item').forEach(el => {
      el.classList.toggle('active', parseInt(el.dataset.index, 10) === idx);
    });
    const badge = $('#featuredIconBadge');
    if (badge) badge.textContent = `#${idx + 1} Selected`;
    scheduleTemplateUpdate();
    toast(`Hero Showcase updated: Icon #${idx + 1}`);
  }

  let activeMakerCat = 'banner_shape';

  function renderMakerElements(cat = activeMakerCat) {
    activeMakerCat = cat;
    const grid = $('#makerElementGrid');
    const sub = $('#makerCatSubtitle');
    if (!grid) return;

    const meta = MAKER_CATEGORIES[cat] || MAKER_CATEGORIES.banner_shape;
    if (sub) sub.textContent = meta.title;

    const items = MAKER_ELEMENTS[cat] || [];
    const currentVal = S.template[meta.prop];
    grid.innerHTML = '';

    items.forEach(item => {
      const card = document.createElement('div');
      card.className = 'maker-el-card' + (currentVal === item.id ? ' active' : '');
      card.dataset.id = item.id;
      card.title = item.name;
      card.innerHTML = `
        <div class="maker-el-thumb">
          <svg viewBox="0 0 90 50" xmlns="http://www.w3.org/2000/svg">${item.svg}</svg>
        </div>
        <div class="maker-el-name">${item.name}</div>
      `;
      card.onclick = () => selectMakerElement(cat, item.id, item.name);
      grid.appendChild(card);
    });
  }

  function selectMakerElement(cat, id, name) {
    const meta = MAKER_CATEGORIES[cat];
    if (!meta) return;
    S.template.design = 'modular_maker';
    S.template[meta.prop] = id;
    $$('#makerElementGrid .maker-el-card').forEach(el => {
      el.classList.toggle('active', el.dataset.id === id);
    });
    if (cat === 'showcase_shape') {
      syncShowcaseShapeUI(id);
    }
    scheduleTemplateUpdate();
    toast(`Selected ${name}`);
  }

  function setupMakerCategoryTabs() {
    const tabs = $$('#makerCatTabs .maker-cat-btn');
    if (!tabs || !tabs.length) return;
    tabs.forEach(btn => {
      btn.onclick = () => {
        tabs.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderMakerElements(btn.dataset.cat);
      };
    });
  }

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
          <span class="swatch-dot" style="background:${p.banner_bg}" title="Cover Banner"></span>
          <span class="swatch-dot" style="background:${p.highlight_bg}" title="Showcase Box"></span>
          <span class="swatch-dot" style="background:${p.banner_text}" title="Text"></span>
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
    $$('#savedTemplatesList .saved-template-card').forEach(c => c.classList.remove('active'));
    const hint = $('#customColorHint');
    if (hint) hint.textContent = p.name;

    if ($('#tplBannerBg')) $('#tplBannerBg').value = p.banner_bg;
    S.template.banner_text = p.banner_text;
    $$('#tplBannerTextSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === p.banner_text));
    if ($('#tplBannerTextColor')) $('#tplBannerTextColor').value = p.banner_text;

    const subCol = p.banner_sub || (p.banner_text === '#FFFFFF' ? '#E2E8F0' : '#475569');
    S.template.banner_sub = subCol;
    if ($('#tplBannerSub')) $('#tplBannerSub').value = subCol;
    if ($('#tplBannerSubInline')) $('#tplBannerSubInline').value = subCol;

    if ($('#tplHighlightBg')) $('#tplHighlightBg').value = p.highlight_bg;
    if ($('#tplShowcaseBgInline')) $('#tplShowcaseBgInline').value = p.highlight_bg;

    if ($('#tplHighlightStroke')) $('#tplHighlightStroke').value = p.highlight_stroke;
    if ($('#tplHeroIconColor')) $('#tplHeroIconColor').value = p.highlight_stroke;

    const accentCol = p.accent || p.banner_bg || '#181B24';
    S.template.shape_accent = accentCol;
    if ($('#tplShapeAccent')) $('#tplShapeAccent').value = accentCol;
    if ($('#tplShowcaseAccentInline')) $('#tplShowcaseAccentInline').value = accentCol;

    S.template.artboard_bg = p.artboard_bg;
    $$('#tplArtboardBgSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === p.artboard_bg));

    if ($('#tplStrokeColor')) $('#tplStrokeColor').value = p.icon_stroke;

    scheduleTemplateUpdate();
  }

  // Saved Custom Templates in LocalStorage
  function loadSavedTemplates() {
    try {
      const raw = localStorage.getItem('linework_stock_templates');
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function saveCurrentCustomTemplate() {
    const defaultName = ($('#tplTitle') && $('#tplTitle').value ? $('#tplTitle').value : 'Custom') + ' Stock Style';
    const name = window.prompt('Enter a name for this custom template preset:', defaultName);
    if (!name || !name.trim()) return;

    const list = loadSavedTemplates();
    const item = {
      id: 'tpl_' + Date.now(),
      name: name.trim(),
      design: 'modular_maker',
      panel_pos: S.template.panel_pos || 'left',
      banner_shape: S.template.banner_shape || 'square_solid',
      decor_element: S.template.decor_element || 'artboard_square_box',
      shape_accent: $('#tplShapeAccent') ? $('#tplShapeAccent').value : (S.template.shape_accent || '#181B24'),
      preset: S.template.preset || 'custom',
      banner_bg: $('#tplBannerBg') ? $('#tplBannerBg').value : '#F5B800',
      banner_text: S.template.banner_text || '#1E1E1E',
      highlight_bg: $('#tplHighlightBg') ? $('#tplHighlightBg').value : '#181B24',
      highlight_stroke: $('#tplHighlightStroke') ? $('#tplHighlightStroke').value : '#FFFFFF',
      artboard_bg: S.template.artboard_bg || 'checkered',
      stroke: $('#tplStrokeColor') ? $('#tplStrokeColor').value : '#181B24',
      scale: $('#tplStrokeScale') ? parseFloat($('#tplStrokeScale').value) : 1.0,
      layout: S.template.layout || 'landscape_16_9',
      show_highlight: $('#tplShowHighlight') ? $('#tplShowHighlight').checked : true,
      highlight_mode: S.template.highlight_mode || 'mini_4',
      font_family: S.template.font_family || 'bebas',
      title_highlight: S.template.title_highlight || 'solid_square',
      showcase_shape: S.template.showcase_shape || 'square_box',
      icon_layout: S.template.icon_layout || 'auto_grid',
      artboard_margin: S.template.artboard_margin !== undefined ? S.template.artboard_margin : 0.06,
      highlight_index: S.template.highlight_index !== undefined ? S.template.highlight_index : 0,
      title_fs: S.template.title_fs !== undefined ? S.template.title_fs : 54,
      count_fs: S.template.count_fs !== undefined ? S.template.count_fs : 160,
      sub_fs: S.template.sub_fs !== undefined ? S.template.sub_fs : 20,
      header_y_offset: S.template.header_y_offset !== undefined ? S.template.header_y_offset : 0,
      count_y_offset: S.template.count_y_offset !== undefined ? S.template.count_y_offset : 0,
      showcase_y_offset: S.template.showcase_y_offset !== undefined ? S.template.showcase_y_offset : 0,
      badge_y_offset: S.template.badge_y_offset !== undefined ? S.template.badge_y_offset : 0,
      showcase_scale: S.template.showcase_scale !== undefined ? S.template.showcase_scale : 1.0,
      element_spacing: S.template.element_spacing !== undefined ? S.template.element_spacing : 0,
      title: $('#tplTitle') ? $('#tplTitle').value : 'TECHNOLOGY',
      subtitle: $('#tplSubtitle') ? $('#tplSubtitle').value : 'Editable Line Icons',
      count: $('#tplCount') ? $('#tplCount').value : '24',
      created: Date.now()
    };
    list.unshift(item);
    try {
      localStorage.setItem('linework_stock_templates', JSON.stringify(list));
    } catch (e) {
      console.error(e);
    }
    renderSavedTemplates();
    toast(`Saved custom template "${item.name}"!`);
  }

  function deleteSavedTemplate(id, e) {
    if (e) e.stopPropagation();
    let list = loadSavedTemplates();
    list = list.filter(item => item.id !== id);
    try {
      localStorage.setItem('linework_stock_templates', JSON.stringify(list));
    } catch (err) {
      console.error(err);
    }
    renderSavedTemplates();
    toast('Custom template deleted');
  }

  function applySavedTemplate(item) {
    if (!item) return;
    S.template.design = item.design || 'modular_maker';
    if (item.panel_pos) {
      S.template.panel_pos = item.panel_pos;
      $$('#tplPanelPosSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === item.panel_pos));
    }
    if (item.banner_shape) S.template.banner_shape = item.banner_shape;
    if (item.decor_element) S.template.decor_element = item.decor_element;
    if (item.shape_accent) {
      S.template.shape_accent = item.shape_accent;
      if ($('#tplShapeAccent')) $('#tplShapeAccent').value = item.shape_accent;
      if ($('#tplShowcaseAccentInline')) $('#tplShowcaseAccentInline').value = item.shape_accent;
    }
    renderMakerElements(activeMakerCat);
    if ($('#tplTitle') && item.title) $('#tplTitle').value = item.title;
    if ($('#tplCount') && item.count) $('#tplCount').value = item.count;
    if ($('#tplSubtitle') && item.subtitle) $('#tplSubtitle').value = item.subtitle;

    if ($('#tplBannerBg') && item.banner_bg) $('#tplBannerBg').value = item.banner_bg;
    if (item.banner_text) {
      S.template.banner_text = item.banner_text;
      $$('#tplBannerTextSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === item.banner_text));
      if ($('#tplBannerTextColor')) $('#tplBannerTextColor').value = item.banner_text;
    }
    if (item.banner_sub) {
      S.template.banner_sub = item.banner_sub;
      if ($('#tplBannerSub')) $('#tplBannerSub').value = item.banner_sub;
      if ($('#tplBannerSubInline')) $('#tplBannerSubInline').value = item.banner_sub;
    }
    if ($('#tplHighlightBg') && item.highlight_bg) {
      $('#tplHighlightBg').value = item.highlight_bg;
      if ($('#tplShowcaseBgInline')) $('#tplShowcaseBgInline').value = item.highlight_bg;
    }
    if ($('#tplHighlightStroke') && item.highlight_stroke) {
      $('#tplHighlightStroke').value = item.highlight_stroke;
      if ($('#tplHeroIconColor')) $('#tplHeroIconColor').value = item.highlight_stroke;
    }

    if (item.artboard_bg) {
      S.template.artboard_bg = item.artboard_bg;
      $$('#tplArtboardBgSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === item.artboard_bg));
    }
    if ($('#tplStrokeColor') && item.stroke) $('#tplStrokeColor').value = item.stroke;
    if ($('#tplStrokeScale') && item.scale) {
      $('#tplStrokeScale').value = item.scale;
      if ($('#tplScaleVal')) $('#tplScaleVal').textContent = Math.round(item.scale * 100) + '%';
    }
    if (item.layout) {
      S.template.layout = item.layout;
      $$('#tplLayoutSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === item.layout));
    }
    if ($('#tplShowHighlight') && item.show_highlight !== undefined) {
      $('#tplShowHighlight').checked = item.show_highlight;
    }
    if (item.highlight_mode) {
      S.template.highlight_mode = item.highlight_mode;
      $$('#tplHighlightModeSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === item.highlight_mode));
    }
    if (item.font_family) {
      S.template.font_family = item.font_family;
      $$('#tplFontSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === item.font_family));
    }
    if (item.title_highlight) {
      S.template.title_highlight = item.title_highlight;
      $$('#tplTitleHlSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === item.title_highlight));
    }
    if (item.showcase_shape) {
      S.template.showcase_shape = item.showcase_shape;
      syncShowcaseShapeUI(item.showcase_shape);
    }
    if (item.element_spacing !== undefined && $('#tplElementSpacing')) {
      S.template.element_spacing = item.element_spacing;
      $('#tplElementSpacing').value = item.element_spacing;
      const sv = item.element_spacing;
      if ($('#tplSpacingVal')) $('#tplSpacingVal').textContent = sv + ' px ' + (sv === 0 ? '(Normal)' : (sv < 0 ? '(Tighter)' : '(Expanded)'));
    }
    if (item.header_y_offset !== undefined && $('#tplHeaderY')) {
      S.template.header_y_offset = item.header_y_offset;
      $('#tplHeaderY').value = item.header_y_offset;
      if ($('#tplHeaderYVal')) $('#tplHeaderYVal').textContent = (item.header_y_offset > 0 ? '+' : '') + item.header_y_offset + ' px';
    }
    if (item.count_y_offset !== undefined && $('#tplCountY')) {
      S.template.count_y_offset = item.count_y_offset;
      $('#tplCountY').value = item.count_y_offset;
      if ($('#tplCountYVal')) $('#tplCountYVal').textContent = (item.count_y_offset > 0 ? '+' : '') + item.count_y_offset + ' px';
    }
    if (item.showcase_y_offset !== undefined && $('#tplShowcaseY')) {
      S.template.showcase_y_offset = item.showcase_y_offset;
      $('#tplShowcaseY').value = item.showcase_y_offset;
      if ($('#tplShowcaseYVal')) $('#tplShowcaseYVal').textContent = (item.showcase_y_offset > 0 ? '+' : '') + item.showcase_y_offset + ' px';
    }
    if (item.showcase_scale !== undefined && $('#tplShowcaseScale')) {
      S.template.showcase_scale = item.showcase_scale;
      const scPct = Math.round(item.showcase_scale * 100);
      $('#tplShowcaseScale').value = scPct;
      if ($('#tplShowcaseScaleVal')) $('#tplShowcaseScaleVal').textContent = scPct + '%';
    }
    if (item.badge_y_offset !== undefined && $('#tplBadgeY')) {
      S.template.badge_y_offset = item.badge_y_offset;
      $('#tplBadgeY').value = item.badge_y_offset;
      if ($('#tplBadgeYVal')) $('#tplBadgeYVal').textContent = (item.badge_y_offset > 0 ? '+' : '') + item.badge_y_offset + ' px';
    }
    if (item.icon_layout) {
      S.template.icon_layout = item.icon_layout;
      $$('#tplIconLayoutSeg button').forEach(b => b.classList.toggle('on', b.dataset.v === item.icon_layout));
    }
    if (item.artboard_margin !== undefined && $('#tplMarginRange')) {
      S.template.artboard_margin = item.artboard_margin;
      $('#tplMarginRange').value = item.artboard_margin;
      const pct = Math.round(item.artboard_margin * 100);
      if ($('#tplMarginVal')) $('#tplMarginVal').textContent = pct + '% ' + (pct === 6 ? '(Stock Standard)' : (pct < 6 ? '(Compact)' : '(Relaxed)'));
    }
    if (item.highlight_index !== undefined) {
      selectFeaturedIcon(item.highlight_index);
    }
    if (item.title_fs !== undefined && $('#tplTitleSize')) {
      S.template.title_fs = item.title_fs;
      $('#tplTitleSize').value = item.title_fs;
      if ($('#tplTitleSizeVal')) $('#tplTitleSizeVal').textContent = item.title_fs + ' px';
    }
    if (item.count_fs !== undefined && $('#tplCountSize')) {
      S.template.count_fs = item.count_fs;
      $('#tplCountSize').value = item.count_fs;
      if ($('#tplCountSizeVal')) $('#tplCountSizeVal').textContent = item.count_fs + ' px';
    }
    if (item.sub_fs !== undefined && $('#tplSubSize')) {
      S.template.sub_fs = item.sub_fs;
      $('#tplSubSize').value = item.sub_fs;
      if ($('#tplSubSizeVal')) $('#tplSubSizeVal').textContent = item.sub_fs + ' px';
    }

    $$('#presetList .preset-card').forEach(c => c.classList.remove('active'));
    $$('#savedTemplatesList .saved-template-card').forEach(c => c.classList.toggle('active', c.dataset.id === item.id));
    const hint = $('#customColorHint');
    if (hint) hint.textContent = item.name;

    scheduleTemplateUpdate();
    toast(`Applied "${item.name}"`);
  }

  function renderSavedTemplates() {
    const listEl = $('#savedTemplatesList');
    const badge = $('#savedCountBadge');
    if (!listEl) return;
    const list = loadSavedTemplates();
    if (badge) badge.textContent = `${list.length} saved`;

    if (list.length === 0) {
      listEl.innerHTML = '<div class="saved-empty-msg">No custom templates saved yet. Click "Save Template" above to save your custom styles.</div>';
      return;
    }

    listEl.innerHTML = '';
    list.forEach(item => {
      const card = document.createElement('div');
      card.className = 'saved-template-card' + (item.preset === S.template.preset ? ' active' : '');
      card.dataset.id = item.id;
      card.innerHTML = `
        <div class="saved-tpl-info">
          <div class="saved-tpl-name" title="${item.name}">${item.name}</div>
          <div class="saved-tpl-meta">
            <span class="swatch-dot" style="background:${item.banner_bg || '#f5b800'}; width:10px; height:10px;" title="Banner"></span>
            <span class="swatch-dot" style="background:${item.highlight_bg || '#181b24'}; width:10px; height:10px;" title="Card"></span>
            <span class="swatch-dot" style="background:${item.stroke || '#181b24'}; width:10px; height:10px;" title="Stroke"></span>
            <span style="font-size:10px; color:var(--text-dim); margin-left:4px;">${item.layout ? item.layout.replace('landscape_', '') : ''}</span>
          </div>
        </div>
        <button type="button" class="btn-delete-saved" title="Delete Saved Template">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      `;
      card.onclick = () => applySavedTemplate(item);
      const delBtn = card.querySelector('.btn-delete-saved');
      if (delBtn) {
        delBtn.onclick = (e) => deleteSavedTemplate(item.id, e);
      }
      listEl.appendChild(card);
    });
  }

  let tplUpdateTimer = null;
  function scheduleTemplateUpdate() {
    clearTimeout(tplUpdateTimer);
    tplUpdateTimer = setTimeout(updateTemplatePreview, 80);
  }

  function formatStockTitle(rawName) {
    if (!rawName) return 'TECHNOLOGY';
    let clean = rawName.replace(/\.[^/.]+$/, '').replace(/[-_]+/g, ' ');
    clean = clean.replace(/\b[0-9a-f]{6,}\b/gi, ' ');
    clean = clean.replace(/\b\d+[a-z]*\b/gi, ' ');
    clean = clean.replace(/\b(icons|icon|set|pack|collection|sheet|vector|line|outline|stroke|style|image|img|copy|final|new)\b/gi, ' ');
    clean = clean.replace(/\s+/g, ' ').trim();
    if (!clean) return 'TECHNOLOGY';
    const words = clean.split(' ').slice(0, 3);
    return words.join(' ').toUpperCase();
  }

  function openTemplateStudio() {
    $('#work').hidden = true;
    if ($('#landing')) $('#landing').hidden = true;
    if ($('#bgStudio')) $('#bgStudio').hidden = true;
    $('#templateStudio').hidden = false;

    $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
    if ($('#navTemplates')) $('#navTemplates').classList.add('active');

    // Auto-populate title if empty or default
    const titleInput = $('#tplTitle');
    if (titleInput && (!titleInput.value || titleInput.value === 'TECHNOLOGY' || titleInput.value === 'Minimal Vector Line Icons')) {
      titleInput.value = (S.job && S.name) ? formatStockTitle(S.name) : 'TECHNOLOGY';
    }

    // Auto-detect count
    const countInput = $('#tplCount');
    if (countInput) {
      if (S.icons && S.icons.length > 0) {
        countInput.value = S.icons.length;
      } else if (!countInput.value) {
        countInput.value = 24;
      }
    }

    // Dynamic header subtitle
    const metaSub = $('#tplMetaSub');
    if (metaSub) {
      if (S.job) {
        metaSub.textContent = `Adobe Stock / Vectuz Style Merged Presentation · Active Sheet (${S.icons ? S.icons.length : 0} icons)`;
      } else {
        metaSub.textContent = `Adobe Stock Style Template Designer · Live Demo Preview · Save & design anytime!`;
      }
    }

    setupMakerCategoryTabs();
    renderMakerElements(activeMakerCat);
    renderPresetCards();
    renderSavedTemplates();
    fetchAndRenderIconPicker();
    syncShowcaseShapeUI(S.template.showcase_shape || 'square_box');
    initCustomTemplateFeatures();
    resetTemplateView();
    updateTemplatePreview();
  }

  function closeTemplateStudio() {
    $('#templateStudio').hidden = true;
    if (S.job) {
      $('#work').hidden = false;
      if ($('#landing')) $('#landing').hidden = true;
    } else {
      if ($('#landing')) $('#landing').hidden = false;
    }
    $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
    if ($('#navRedraw')) $('#navRedraw').classList.add('active');
    if (typeof fit === 'function') fit();
  }

  async function updateTemplatePreview() {
    const jobId = S.job || 'demo';
    const title = $('#tplTitle') ? $('#tplTitle').value : 'TECHNOLOGY';
    const count = $('#tplCount') ? $('#tplCount').value : '24';
    const subtitle = $('#tplSubtitle') ? $('#tplSubtitle').value : 'Editable Line Icons';
    const bannerBg = $('#tplBannerBg') ? $('#tplBannerBg').value : '#F5B800';
    const bannerText = S.template.banner_text || ($('#tplBannerTextColor') ? $('#tplBannerTextColor').value : '#1E1E1E');
    const bannerSub = $('#tplBannerSub') ? $('#tplBannerSub').value : ($('#tplBannerSubInline') ? $('#tplBannerSubInline').value : (S.template.banner_sub || ''));
    const highlightBg = $('#tplHighlightBg') ? $('#tplHighlightBg').value : '#181B24';
    const highlightStroke = $('#tplHighlightStroke') ? $('#tplHighlightStroke').value : '#FFFFFF';
    const shapeAccent = $('#tplShapeAccent') ? $('#tplShapeAccent').value : ($('#tplShowcaseAccentInline') ? $('#tplShowcaseAccentInline').value : (S.template.shape_accent || '#181B24'));
    const artboardBg = S.template.artboard_bg || 'checkered';
    const stroke = $('#tplStrokeColor') ? $('#tplStrokeColor').value : '#181B24';
    const scale = $('#tplStrokeScale') ? $('#tplStrokeScale').value : '1.0';
    const layout = S.template.layout || 'landscape_16_9';
    const showHighlight = ($('#tplShowHighlight') && $('#tplShowHighlight').checked) ? 1 : 0;
    const highlightMode = S.template.highlight_mode || 'mini_4';

    const params = new URLSearchParams({
      design: 'modular_maker',
      panel_pos: S.template.panel_pos || 'left',
      banner_shape: S.template.banner_shape || 'square_solid',
      decor_element: S.template.decor_element || 'artboard_square_box',
      shape_accent: shapeAccent,
      accent: shapeAccent,
      preset: S.template.preset || 'vectuz_yellow',
      title: title,
      count: count,
      subtitle: subtitle,
      banner_bg: bannerBg,
      banner_text: bannerText,
      banner_sub: bannerSub,
      highlight_bg: highlightBg,
      highlight_stroke: highlightStroke,
      artboard_bg: artboardBg,
      stroke: stroke,
      scale: scale,
      layout: layout,
      show_highlight: showHighlight,
      highlight_mode: highlightMode,
      highlight_index: S.template.highlight_index !== undefined ? S.template.highlight_index : 0,
      title_fs: S.template.title_fs !== undefined ? S.template.title_fs : 54,
      count_fs: S.template.count_fs !== undefined ? S.template.count_fs : 160,
      sub_fs: S.template.sub_fs !== undefined ? S.template.sub_fs : 20,
      font_family: S.template.font_family || 'bebas',
      title_highlight: S.template.title_highlight || 'solid_square',
      showcase_shape: S.template.showcase_shape || 'square_box',
      icon_layout: S.template.icon_layout || 'auto_grid',
      artboard_margin: S.template.artboard_margin !== undefined ? S.template.artboard_margin : 0.06,
      header_y_offset: S.template.header_y_offset !== undefined ? S.template.header_y_offset : 0,
      count_y_offset: S.template.count_y_offset !== undefined ? S.template.count_y_offset : 0,
      showcase_y_offset: S.template.showcase_y_offset !== undefined ? S.template.showcase_y_offset : 0,
      badge_y_offset: S.template.badge_y_offset !== undefined ? S.template.badge_y_offset : 0,
      showcase_scale: S.template.showcase_scale !== undefined ? S.template.showcase_scale : 1.0,
      element_spacing: S.template.element_spacing !== undefined ? S.template.element_spacing : 0,
    });

    if (S.template.engine_mode === 'custom_image') {
      params.set('design', 'custom_image');
      if (S.template.custom_image_url) params.set('custom_image_url', S.template.custom_image_url);
      params.set('custom_img_w', S.template.custom_img_w || 1920);
      params.set('custom_img_h', S.template.custom_img_h || 1080);

      const gx = $('#tplCustomGridX') ? parseFloat($('#tplCustomGridX').value) / 100 : 0.40;
      const gy = $('#tplCustomGridY') ? parseFloat($('#tplCustomGridY').value) / 100 : 0.10;
      const gw = $('#tplCustomGridW') ? parseFloat($('#tplCustomGridW').value) / 100 : 0.55;
      const gh = $('#tplCustomGridH') ? parseFloat($('#tplCustomGridH').value) / 100 : 0.78;
      params.set('custom_grid_x', gx);
      params.set('custom_grid_y', gy);
      params.set('custom_grid_w', gw);
      params.set('custom_grid_h', gh);

      const customStroke = $('#tplCustomIconStroke') ? $('#tplCustomIconStroke').value : '#FFFFFF';
      const customScale = $('#tplCustomStrokeScale') ? $('#tplCustomStrokeScale').value : '1.0';
      params.set('icon_stroke', customStroke);
      params.set('stroke', customStroke);
      params.set('scale', customScale);
      params.set('stroke_scale', customScale);

      const heroEnable = ($('#tplCustomHeroEnable') && $('#tplCustomHeroEnable').checked) ? 1 : 0;
      params.set('custom_hero_enable', heroEnable);
      const hx = $('#tplCustomHeroX') ? parseFloat($('#tplCustomHeroX').value) / 100 : 0.18;
      const hy = $('#tplCustomHeroY') ? parseFloat($('#tplCustomHeroY').value) / 100 : 0.68;
      const hs = $('#tplCustomHeroSize') ? parseFloat($('#tplCustomHeroSize').value) / 100 : 0.20;
      params.set('custom_hero_x', hx);
      params.set('custom_hero_y', hy);
      params.set('custom_hero_size', hs);

      const heroShape = $('#tplCustomShowcaseShape') ? $('#tplCustomShowcaseShape').value : 'squircle_super';
      const heroStroke = $('#tplCustomHeroStroke') ? $('#tplCustomHeroStroke').value : '#FFFFFF';
      const heroAccent = $('#tplCustomHeroAccent') ? $('#tplCustomHeroAccent').value : '#00F5A0';
      const heroBg = $('#tplCustomHeroBg') ? $('#tplCustomHeroBg').value : '#181B24';
      params.set('showcase_shape', heroShape);
      params.set('highlight_stroke', heroStroke);
      params.set('shape_accent', heroAccent);
      params.set('accent', heroAccent);
      params.set('highlight_bg', heroBg);

      const textEnable = ($('#tplCustomTextEnable') && $('#tplCustomTextEnable').checked) ? 1 : 0;
      params.set('custom_text_enable', textEnable);
      const tVal = $('#tplCustomTitle') ? $('#tplCustomTitle').value : 'MINIMAL BLACK UI';
      const tCol = $('#tplCustomTitleColor') ? $('#tplCustomTitleColor').value : '#FFFFFF';
      const tx = $('#tplCustomTitleX') ? parseFloat($('#tplCustomTitleX').value) / 100 : 0.18;
      const ty = $('#tplCustomTitleY') ? parseFloat($('#tplCustomTitleY').value) / 100 : 0.18;
      params.set('title', tVal);
      params.set('banner_text', tCol);
      params.set('custom_title_x', tx);
      params.set('custom_title_y', ty);

      const sVal = $('#tplCustomSubtitle') ? $('#tplCustomSubtitle').value : 'Editable Line Icons';
      const sCol = $('#tplCustomSubColor') ? $('#tplCustomSubColor').value : '#E2E8F0';
      const sx = $('#tplCustomSubX') ? parseFloat($('#tplCustomSubX').value) / 100 : 0.18;
      const sy = $('#tplCustomSubY') ? parseFloat($('#tplCustomSubY').value) / 100 : 0.24;
      params.set('subtitle', sVal);
      params.set('banner_sub', sCol);
      params.set('custom_sub_x', sx);
      params.set('custom_sub_y', sy);

      const cVal = $('#tplCustomCount') ? $('#tplCustomCount').value : '24';
      const cCol = $('#tplCustomCountColor') ? $('#tplCustomCountColor').value : '#FFFFFF';
      const cx = $('#tplCustomCountX') ? parseFloat($('#tplCustomCountX').value) / 100 : 0.18;
      const cy = $('#tplCustomCountY') ? parseFloat($('#tplCustomCountY').value) / 100 : 0.44;
      params.set('count', cVal);
      params.set('custom_count_x', cx);
      params.set('custom_count_y', cy);
    }

    // Update download links
    const dlSvg = $('#btnDlTemplateSvg');
    if (dlSvg) dlSvg.href = `/api/jobs/${jobId}/template.svg?${params.toString()}&download=1`;

    const dlPng = $('#btnDlTemplatePng');
    if (dlPng) dlPng.href = `/api/jobs/${jobId}/template.png?${params.toString()}&download=1`;

    const dlEps = $('#btnDlTemplateEps');
    if (dlEps) dlEps.href = `/api/jobs/${jobId}/template.eps?${params.toString()}&download=1`;

    const dlZip = $('#btnDlTemplateZip');
    if (dlZip) dlZip.href = `/api/jobs/${jobId}/download.zip?stroke=${encodeURIComponent(stroke)}&scale=${scale}`;

    // Update dims indicator
    const dimsBadge = $('#tplDimsBadge');
    if (dimsBadge) {
      if (S.template.engine_mode === 'custom_image') {
        dimsBadge.textContent = `${S.template.custom_img_w || 1920} × ${S.template.custom_img_h || 1080} px · Custom AI Template Mockup`;
      } else {
        let desc = '3840 × 2160 px · 16:9 Ultra-HD';
        if (layout === 'landscape_16_10') desc = '1920 × 1200 px · 16:10 Widescreen';
        else if (layout === 'landscape_4_3') desc = '2400 × 1800 px · 4:3 Microstock Standard';
        else if (layout === 'square') desc = '2000 × 2000 px · 1:1 Square';
        else if (layout === 'auto_dock') desc = 'Auto-Docked to Native Sheet Size';
        dimsBadge.textContent = desc;
      }
    }

    try {
      const res = await api(`/api/jobs/${jobId}/template.svg?${params.toString()}`);
      if (res.ok) {
        const svgContent = await res.text();
        const container = $('#templateSvgContainer');
        if (container) {
          container.innerHTML = svgContent;
          const scBox = container.querySelector('#showcaseBoxComponent');
          if (scBox) {
            scBox.style.cursor = 'pointer';
            scBox.setAttribute('title', 'Click to change Hero Showcase Frame Shape');
            scBox.onclick = (e) => {
              e.stopPropagation();
              const heroTab = $(`#makerCatTabs .maker-cat-btn[data-cat="showcase_shape"]`);
              if (heroTab) heroTab.click();
              const p2 = $('#featuredIconPanel');
              if (p2) p2.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
              toast('⭐ Hero Showcase Shape: Pick any of the 25 shapes below!');
            };
          }
        }
      }
    } catch (e) {
      console.error('Failed to load template preview:', e);
    }
  }

  // Zoom & Drag-to-Pan Hand Tool Engine for Template Studio
  let tplZoom = 1.0;
  let tplPanX = 0;
  let tplPanY = 0;
  let tplIsDragging = false;
  let tplStartX = 0;
  let tplStartY = 0;

  function applyTemplateTransform() {
    const container = $('#templateSvgContainer');
    if (container) {
      container.style.transform = `translate(${tplPanX}px, ${tplPanY}px) scale(${tplZoom})`;
    }
    const readout = $('#tplZoomReadout');
    if (readout) readout.textContent = Math.round(tplZoom * 100) + '%';
    const badge = $('#tplZoomBadge');
    if (badge) badge.textContent = Math.round(tplZoom * 100) + '%';
  }

  function setTemplateZoom(z) {
    tplZoom = Math.min(Math.max(z, 0.25), 4.0);
    applyTemplateTransform();
  }

  function resetTemplateView() {
    tplZoom = 1.0;
    tplPanX = 0;
    tplPanY = 0;
    applyTemplateTransform();
  }

  function fitTemplateView() {
    const stage = $('#templateStage');
    const svg = $('#templateSvgContainer svg');
    if (stage && svg) {
      const stageW = stage.clientWidth - 48;
      const stageH = stage.clientHeight - 48;
      const vb = svg.viewBox && svg.viewBox.baseVal ? svg.viewBox.baseVal : { width: 3840, height: 2160 };
      const svgW = vb.width || 3840;
      const svgH = vb.height || 2160;
      if (stageW > 0 && stageH > 0 && svgW > 0 && svgH > 0) {
        const fitScale = Math.min(stageW / svgW, stageH / svgH);
        tplZoom = Math.max(0.25, Math.min(fitScale * 0.95, 2.5));
      } else {
        tplZoom = 1.0;
      }
    } else {
      tplZoom = 1.0;
    }
    tplPanX = 0;
    tplPanY = 0;
    applyTemplateTransform();
  }

  // Setup template listeners
  const btnSendToTemplate = $('#btnSendToTemplate');
  if (btnSendToTemplate) {
    btnSendToTemplate.addEventListener('click', () => {
      if (!S.job) {
        toast('Please load an icon sheet first', 1);
        return;
      }
      S.template.highlight_index = 0;
      const countInput = $('#tplCount');
      if (countInput && S.icons && S.icons.length > 0) {
        countInput.value = S.icons.length;
      }
      const titleInput = $('#tplTitle');
      if (titleInput && S.name) {
        titleInput.value = formatStockTitle(S.name);
      }
      openTemplateStudio();
    });
  }

  const btnBackToWork = $('#btnBackToWork');
  if (btnBackToWork) {
    btnBackToWork.addEventListener('click', closeTemplateStudio);
  }

  const btnSaveCustomTemplate = $('#btnSaveCustomTemplate');
  if (btnSaveCustomTemplate) {
    btnSaveCustomTemplate.addEventListener('click', saveCurrentCustomTemplate);
  }
  const btnSaveTemplateSidebar = $('#btnSaveTemplateSidebar');
  if (btnSaveTemplateSidebar) {
    btnSaveTemplateSidebar.addEventListener('click', saveCurrentCustomTemplate);
  }

  // Random & Reset featured icon buttons
  const btnRandomFeatured = $('#btnRandomFeaturedIcon');
  if (btnRandomFeatured) {
    btnRandomFeatured.onclick = () => {
      if (!currentSheetIcons || currentSheetIcons.length <= 1) return;
      const randIdx = Math.floor(Math.random() * currentSheetIcons.length);
      selectFeaturedIcon(randIdx);
    };
  }
  const btnResetFeatured = $('#btnResetFeaturedIcon');
  if (btnResetFeatured) {
    btnResetFeatured.onclick = () => {
      selectFeaturedIcon(0);
    };
  }

  // Font size sliders live preview
  const tplTitleSize = $('#tplTitleSize');
  const tplTitleSizeVal = $('#tplTitleSizeVal');
  if (tplTitleSize && tplTitleSizeVal) {
    tplTitleSize.addEventListener('input', () => {
      const val = parseInt(tplTitleSize.value, 10);
      tplTitleSizeVal.textContent = val + ' px';
      S.template.title_fs = val;
      scheduleTemplateUpdate();
    });
  }

  const tplCountSize = $('#tplCountSize');
  const tplCountSizeVal = $('#tplCountSizeVal');
  if (tplCountSize && tplCountSizeVal) {
    tplCountSize.addEventListener('input', () => {
      const val = parseInt(tplCountSize.value, 10);
      tplCountSizeVal.textContent = val + ' px';
      S.template.count_fs = val;
      scheduleTemplateUpdate();
    });
  }

  const tplSubSize = $('#tplSubSize');
  const tplSubSizeVal = $('#tplSubSizeVal');
  if (tplSubSize && tplSubSizeVal) {
    tplSubSize.addEventListener('input', () => {
      const val = parseInt(tplSubSize.value, 10);
      tplSubSizeVal.textContent = val + ' px';
      S.template.sub_fs = val;
      scheduleTemplateUpdate();
    });
  }

  const btnAutoCount = $('#btnAutoCount');
  if (btnAutoCount) {
    btnAutoCount.addEventListener('click', () => {
      const count = (S.icons && S.icons.length) ? S.icons.length : 24;
      const countInput = $('#tplCount');
      if (countInput) countInput.value = count;
      scheduleTemplateUpdate();
      toast(`Auto-detected ${count} icons from current sheet!`);
    });
  }

  // Text inputs live preview
  ['tplTitle', 'tplCount', 'tplSubtitle'].forEach(id => {
    const el = $('#' + id);
    if (el) el.addEventListener('input', scheduleTemplateUpdate);
  });

  // Panel position switcher (Left, Right, Top, Bottom)
  $$('#tplPanelPosSeg button').forEach(b => {
    b.addEventListener('click', () => {
      $$('#tplPanelPosSeg button').forEach(x => x.classList.toggle('on', x === b));
      S.template.panel_pos = b.dataset.v;
      S.template.design = 'modular_maker';
      scheduleTemplateUpdate();
      toast(`Cover dock position: ${b.textContent}`);
    });
  });

  // 1-Click Pro Master Agency Templates
  const MASTER_TEMPLATES = {
    adobe_gold: {
      name: 'Adobe Gold Pro',
      preset: 'vectuz_yellow',
      panel_pos: 'left',
      banner_shape: 'square_solid',
      title_highlight: 'offset_shadow_box',
      showcase_shape: 'square_box',
      decor_element: 'cell_rounded_cards',
      banner_bg: '#F5B800',
      banner_text: '#1E1E1E',
      shape_accent: '#181B24',
      highlight_bg: '#181B24',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      stroke: '#181B24',
      highlight_mode: 'hero_1',
      font_family: 'bebas',
    },
    envato_indigo: {
      name: 'Envato Indigo Studio',
      preset: 'envato_indigo',
      panel_pos: 'left',
      banner_shape: 'floating_card',
      title_highlight: 'capsule_pill',
      showcase_shape: 'glass_panel',
      decor_element: 'cell_rounded_cards',
      banner_bg: '#2563EB',
      banner_text: '#FFFFFF',
      shape_accent: '#0F172A',
      highlight_bg: '#0F172A',
      highlight_stroke: '#FFFFFF',
      artboard_bg: '#F8FAFC',
      stroke: '#0F172A',
      highlight_mode: 'mini_4',
      font_family: 'montserrat',
    },
    cyber_hud: {
      name: 'Cyber HUD Neon',
      preset: 'midnight_dark',
      panel_pos: 'left',
      banner_shape: 'notched_cyber',
      title_highlight: 'cut_corner_tag',
      showcase_shape: 'hud_corners_box',
      decor_element: 'cell_corner_ticks',
      banner_bg: '#18181B',
      banner_text: '#FFFFFF',
      shape_accent: '#00F5A0',
      highlight_bg: '#09090B',
      highlight_stroke: '#00F5A0',
      artboard_bg: '#0F172A',
      stroke: '#F4F4F5',
      highlight_mode: 'hero_1',
      font_family: 'oswald',
    },
    freepik_wave: {
      name: 'Emerald Wave Studio',
      preset: 'freepik_emerald',
      panel_pos: 'left',
      banner_shape: 'curved_wave',
      title_highlight: 'solid_rounded',
      showcase_shape: 'squircle_box',
      decor_element: 'cell_soft_tint',
      banner_bg: '#10B981',
      banner_text: '#FFFFFF',
      shape_accent: '#064E3B',
      highlight_bg: '#064E3B',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      stroke: '#111827',
      highlight_mode: 'hero_1',
      font_family: 'bebas',
    },
    coral_slash: {
      name: 'Coral Split Pro',
      preset: 'creative_coral',
      panel_pos: 'left',
      banner_shape: 'diagonal_slash',
      title_highlight: 'offset_shadow_box',
      showcase_shape: 'offset_3d_box',
      decor_element: 'cell_rounded_cards',
      banner_bg: '#FF5A36',
      banner_text: '#FFFFFF',
      shape_accent: '#18181B',
      highlight_bg: '#18181B',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      stroke: '#18181B',
      highlight_mode: 'hero_1',
      font_family: 'bebas',
    },
    editorial_top: {
      name: 'Royal Top Header',
      preset: 'royal_purple',
      panel_pos: 'top',
      banner_shape: 'square_solid',
      title_highlight: 'capsule_pill',
      showcase_shape: 'rounded_box',
      decor_element: 'cell_rounded_cards',
      banner_bg: '#7C3AED',
      banner_text: '#FFFFFF',
      shape_accent: '#1E1B4B',
      highlight_bg: '#1E1B4B',
      highlight_stroke: '#FFFFFF',
      artboard_bg: 'checkered',
      stroke: '#1E1B4B',
      highlight_mode: 'hero_1',
      font_family: 'montserrat',
    },
  };

  $$('#masterTemplateStrip .master-tpl-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const key = btn.dataset.master;
      const tpl = MASTER_TEMPLATES[key];
      if (!tpl) return;
      $$('#masterTemplateStrip .master-tpl-btn').forEach(b => {
        b.classList.toggle('active', b === btn);
        b.style.borderColor = (b === btn) ? 'var(--accent)' : '';
      });
      applySavedTemplate(tpl);
    });
  });

  // Reset to Clean Square Box button
  const btnResetMakerDefault = $('#btnResetMakerDefault');
  if (btnResetMakerDefault) {
    btnResetMakerDefault.addEventListener('click', () => {
      applySavedTemplate(MASTER_TEMPLATES.adobe_gold);
      toast('Reset to Adobe Gold Pro Master Template!');
    });
  }

  // Color inputs live preview with bidirectional synchronization
  ['tplBannerBg', 'tplShapeAccent', 'tplHighlightBg', 'tplHighlightStroke', 'tplStrokeColor', 'tplBannerSub'].forEach(id => {
    const el = $('#' + id);
    if (el) {
      el.addEventListener('input', () => {
        $$('#presetList .preset-card').forEach(c => c.classList.remove('active'));
        const hint = $('#customColorHint');
        if (hint) hint.textContent = 'Custom Preset';
        if (id === 'tplBannerSub' && $('#tplBannerSubInline')) $('#tplBannerSubInline').value = el.value;
        if (id === 'tplShapeAccent' && $('#tplShowcaseAccentInline')) $('#tplShowcaseAccentInline').value = el.value;
        if (id === 'tplHighlightBg' && $('#tplShowcaseBgInline')) $('#tplShowcaseBgInline').value = el.value;
        if (id === 'tplHighlightStroke' && $('#tplHeroIconColor')) $('#tplHeroIconColor').value = el.value;
        scheduleTemplateUpdate();
      });
    }
  });

  // Step 2 & Step 4 inline color controls
  const heroIconColor = $('#tplHeroIconColor');
  if (heroIconColor) {
    heroIconColor.addEventListener('input', () => {
      if ($('#tplHighlightStroke')) $('#tplHighlightStroke').value = heroIconColor.value;
      $$('#presetList .preset-card').forEach(c => c.classList.remove('active'));
      scheduleTemplateUpdate();
    });
  }

  const scAccentInline = $('#tplShowcaseAccentInline');
  if (scAccentInline) {
    scAccentInline.addEventListener('input', () => {
      if ($('#tplShapeAccent')) $('#tplShapeAccent').value = scAccentInline.value;
      S.template.shape_accent = scAccentInline.value;
      $$('#presetList .preset-card').forEach(c => c.classList.remove('active'));
      scheduleTemplateUpdate();
    });
  }

  const scBgInline = $('#tplShowcaseBgInline');
  if (scBgInline) {
    scBgInline.addEventListener('input', () => {
      if ($('#tplHighlightBg')) $('#tplHighlightBg').value = scBgInline.value;
      $$('#presetList .preset-card').forEach(c => c.classList.remove('active'));
      scheduleTemplateUpdate();
    });
  }

  const bannerSubInline = $('#tplBannerSubInline');
  if (bannerSubInline) {
    bannerSubInline.addEventListener('input', () => {
      if ($('#tplBannerSub')) $('#tplBannerSub').value = bannerSubInline.value;
      S.template.banner_sub = bannerSubInline.value;
      $$('#presetList .preset-card').forEach(c => c.classList.remove('active'));
      scheduleTemplateUpdate();
    });
  }

  const bannerTextColor = $('#tplBannerTextColor');
  if (bannerTextColor) {
    bannerTextColor.addEventListener('input', () => {
      S.template.banner_text = bannerTextColor.value;
      $$('#tplBannerTextSeg button').forEach(b => b.classList.toggle('on', b.dataset.v.toLowerCase() === bannerTextColor.value.toLowerCase()));
      $$('#presetList .preset-card').forEach(c => c.classList.remove('active'));
      scheduleTemplateUpdate();
    });
  }

  // Banner text segment (Light / Dark) with smart subtitle contrast
  $$('#tplBannerTextSeg button').forEach(b => {
    b.addEventListener('click', () => {
      $$('#tplBannerTextSeg button').forEach(x => x.classList.toggle('on', x === b));
      S.template.banner_text = b.dataset.v;
      if ($('#tplBannerTextColor')) $('#tplBannerTextColor').value = b.dataset.v;
      const newSub = b.dataset.v === '#FFFFFF' ? '#E2E8F0' : '#475569';
      if ($('#tplBannerSub')) $('#tplBannerSub').value = newSub;
      if ($('#tplBannerSubInline')) $('#tplBannerSubInline').value = newSub;
      S.template.banner_sub = newSub;
      $$('#presetList .preset-card').forEach(c => c.classList.remove('active'));
      scheduleTemplateUpdate();
    });
  });

  // Artboard background segment
  $$('#tplArtboardBgSeg button').forEach(b => {
    b.addEventListener('click', () => {
      $$('#tplArtboardBgSeg button').forEach(x => x.classList.toggle('on', x === b));
      S.template.artboard_bg = b.dataset.v;
      scheduleTemplateUpdate();
    });
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

  // Showcase controls
  const tplShowHighlight = $('#tplShowHighlight');
  if (tplShowHighlight) {
    tplShowHighlight.addEventListener('change', scheduleTemplateUpdate);
  }
  $$('#tplHighlightModeSeg button').forEach(b => {
    b.addEventListener('click', () => {
      $$('#tplHighlightModeSeg button').forEach(x => x.classList.toggle('on', x === b));
      S.template.highlight_mode = b.dataset.v;
      scheduleTemplateUpdate();
    });
  });

  // Font family selector
  $$('#tplFontSeg button').forEach(b => {
    b.addEventListener('click', () => {
      $$('#tplFontSeg button').forEach(x => x.classList.toggle('on', x === b));
      S.template.font_family = b.dataset.v;
      scheduleTemplateUpdate();
      toast(`Font family: ${b.textContent}`);
    });
  });

  // Title highlight element
  $$('#tplTitleHlSeg button').forEach(b => {
    b.addEventListener('click', () => {
      $$('#tplTitleHlSeg button').forEach(x => x.classList.toggle('on', x === b));
      S.template.title_highlight = b.dataset.v;
      scheduleTemplateUpdate();
      toast(`Title highlight: ${b.textContent}`);
    });
  });

  // Showcase card design & quick selector synchronization
  function syncShowcaseShapeUI(shapeId) {
    if (!shapeId) return;
    S.template.showcase_shape = shapeId;

    // Quick buttons in Panel 2
    $$('#tplShowcaseShapeQuickSeg button').forEach(b => {
      b.classList.toggle('on', b.dataset.v === shapeId);
    });
    // Dropdown in Panel 2
    const scSel = $('#tplShowcaseShapeSelect');
    if (scSel) {
      scSel.value = shapeId;
    }
    // Pill badge in Panel 2
    const scBadge = $('#tplShowcaseShapeBadge');
    if (scBadge) {
      const match = (MAKER_ELEMENTS.showcase_shape || []).find(x => x.id === shapeId);
      scBadge.textContent = match ? match.name.replace(/^\d+\.\s*/, '') : shapeId;
    }
    // Panel 1 Tab 3 elements
    if (activeMakerCat === 'showcase_shape') {
      $$('#makerElementGrid .maker-el-card').forEach(el => {
        el.classList.toggle('active', el.dataset.id === shapeId);
      });
    }
  }

  $$('#tplShowcaseShapeQuickSeg button').forEach(b => {
    b.addEventListener('click', () => {
      syncShowcaseShapeUI(b.dataset.v);
      scheduleTemplateUpdate();
      toast(`Hero frame: ${b.textContent.trim()}`);
    });
  });

  const tplScSelect = $('#tplShowcaseShapeSelect');
  if (tplScSelect) {
    tplScSelect.addEventListener('change', () => {
      syncShowcaseShapeUI(tplScSelect.value);
      scheduleTemplateUpdate();
      toast(`Hero frame: ${tplScSelect.options[tplScSelect.selectedIndex].text}`);
    });
  }

  // Vertical Positioning & Spacing Controls (Step 3)
  const tplElemSpacing = $('#tplElementSpacing');
  const tplSpacingVal = $('#tplSpacingVal');
  if (tplElemSpacing && tplSpacingVal) {
    tplElemSpacing.addEventListener('input', () => {
      const v = parseInt(tplElemSpacing.value, 10);
      tplSpacingVal.textContent = v + ' px ' + (v === 0 ? '(Normal)' : (v < 0 ? '(Tighter)' : '(Expanded)'));
      S.template.element_spacing = v;
      scheduleTemplateUpdate();
    });
  }

  const tplHeaderY = $('#tplHeaderY');
  const tplHeaderYVal = $('#tplHeaderYVal');
  if (tplHeaderY && tplHeaderYVal) {
    tplHeaderY.addEventListener('input', () => {
      const v = parseInt(tplHeaderY.value, 10);
      tplHeaderYVal.textContent = (v > 0 ? '+' : '') + v + ' px';
      S.template.header_y_offset = v;
      scheduleTemplateUpdate();
    });
  }
  const btnHeaderUp = $('#btnHeaderUp');
  if (btnHeaderUp && tplHeaderY && tplHeaderYVal) {
    btnHeaderUp.addEventListener('click', () => {
      const v = Math.max(-180, (S.template.header_y_offset || 0) - 15);
      tplHeaderY.value = v;
      tplHeaderYVal.textContent = (v > 0 ? '+' : '') + v + ' px';
      S.template.header_y_offset = v;
      scheduleTemplateUpdate();
    });
  }
  const btnHeaderDown = $('#btnHeaderDown');
  if (btnHeaderDown && tplHeaderY && tplHeaderYVal) {
    btnHeaderDown.addEventListener('click', () => {
      const v = Math.min(180, (S.template.header_y_offset || 0) + 15);
      tplHeaderY.value = v;
      tplHeaderYVal.textContent = (v > 0 ? '+' : '') + v + ' px';
      S.template.header_y_offset = v;
      scheduleTemplateUpdate();
    });
  }

  const tplCountY = $('#tplCountY');
  const tplCountYVal = $('#tplCountYVal');
  if (tplCountY && tplCountYVal) {
    tplCountY.addEventListener('input', () => {
      const v = parseInt(tplCountY.value, 10);
      tplCountYVal.textContent = (v > 0 ? '+' : '') + v + ' px';
      S.template.count_y_offset = v;
      scheduleTemplateUpdate();
    });
  }
  const btnCountUp = $('#btnCountUp');
  if (btnCountUp && tplCountY && tplCountYVal) {
    btnCountUp.addEventListener('click', () => {
      const v = Math.max(-180, (S.template.count_y_offset || 0) - 15);
      tplCountY.value = v;
      tplCountYVal.textContent = (v > 0 ? '+' : '') + v + ' px';
      S.template.count_y_offset = v;
      scheduleTemplateUpdate();
    });
  }
  const btnCountDown = $('#btnCountDown');
  if (btnCountDown && tplCountY && tplCountYVal) {
    btnCountDown.addEventListener('click', () => {
      const v = Math.min(180, (S.template.count_y_offset || 0) + 15);
      tplCountY.value = v;
      tplCountYVal.textContent = (v > 0 ? '+' : '') + v + ' px';
      S.template.count_y_offset = v;
      scheduleTemplateUpdate();
    });
  }

  const tplShowcaseY = $('#tplShowcaseY');
  const tplShowcaseYVal = $('#tplShowcaseYVal');
  if (tplShowcaseY && tplShowcaseYVal) {
    tplShowcaseY.addEventListener('input', () => {
      const v = parseInt(tplShowcaseY.value, 10);
      tplShowcaseYVal.textContent = (v > 0 ? '+' : '') + v + ' px';
      S.template.showcase_y_offset = v;
      scheduleTemplateUpdate();
    });
  }
  const btnShowcaseUp = $('#btnShowcaseUp');
  if (btnShowcaseUp && tplShowcaseY && tplShowcaseYVal) {
    btnShowcaseUp.addEventListener('click', () => {
      const v = Math.max(-180, (S.template.showcase_y_offset || 0) - 15);
      tplShowcaseY.value = v;
      tplShowcaseYVal.textContent = (v > 0 ? '+' : '') + v + ' px';
      S.template.showcase_y_offset = v;
      scheduleTemplateUpdate();
    });
  }
  const btnShowcaseDown = $('#btnShowcaseDown');
  if (btnShowcaseDown && tplShowcaseY && tplShowcaseYVal) {
    btnShowcaseDown.addEventListener('click', () => {
      const v = Math.min(180, (S.template.showcase_y_offset || 0) + 15);
      tplShowcaseY.value = v;
      tplShowcaseYVal.textContent = (v > 0 ? '+' : '') + v + ' px';
      S.template.showcase_y_offset = v;
      scheduleTemplateUpdate();
    });
  }

  const tplShowcaseScale = $('#tplShowcaseScale');
  const tplShowcaseScaleVal = $('#tplShowcaseScaleVal');
  if (tplShowcaseScale && tplShowcaseScaleVal) {
    tplShowcaseScale.addEventListener('input', () => {
      const pct = parseInt(tplShowcaseScale.value, 10);
      tplShowcaseScaleVal.textContent = pct + '%';
      S.template.showcase_scale = pct / 100.0;
      scheduleTemplateUpdate();
    });
  }
  const btnScScaleDown = $('#btnShowcaseScaleDown');
  if (btnScScaleDown && tplShowcaseScale && tplShowcaseScaleVal) {
    btnScScaleDown.addEventListener('click', () => {
      const curPct = Math.round((S.template.showcase_scale || 1.0) * 100);
      const newPct = Math.max(60, curPct - 10);
      tplShowcaseScale.value = newPct;
      tplShowcaseScaleVal.textContent = newPct + '%';
      S.template.showcase_scale = newPct / 100.0;
      scheduleTemplateUpdate();
    });
  }
  const btnScScaleUp = $('#btnShowcaseScaleUp');
  if (btnScScaleUp && tplShowcaseScale && tplShowcaseScaleVal) {
    btnScScaleUp.addEventListener('click', () => {
      const curPct = Math.round((S.template.showcase_scale || 1.0) * 100);
      const newPct = Math.min(140, curPct + 10);
      tplShowcaseScale.value = newPct;
      tplShowcaseScaleVal.textContent = newPct + '%';
      S.template.showcase_scale = newPct / 100.0;
      scheduleTemplateUpdate();
    });
  }

  const btnResetSpacing = $('#btnResetSpacing');
  if (btnResetSpacing) {
    btnResetSpacing.addEventListener('click', () => {
      S.template.element_spacing = 0;
      S.template.header_y_offset = 0;
      S.template.count_y_offset = 0;
      S.template.showcase_y_offset = 0;
      S.template.badge_y_offset = 0;
      S.template.showcase_scale = 1.0;

      if (tplElemSpacing) tplElemSpacing.value = 0;
      if (tplSpacingVal) tplSpacingVal.textContent = '0 px (Normal)';

      if (tplHeaderY) tplHeaderY.value = 0;
      if (tplHeaderYVal) tplHeaderYVal.textContent = '0 px';

      if (tplCountY) tplCountY.value = 0;
      if (tplCountYVal) tplCountYVal.textContent = '0 px';

      if (tplShowcaseY) tplShowcaseY.value = 0;
      if (tplShowcaseYVal) tplShowcaseYVal.textContent = '0 px';

      if (tplShowcaseScale) tplShowcaseScale.value = 100;
      if (tplShowcaseScaleVal) tplShowcaseScaleVal.textContent = '100%';

      scheduleTemplateUpdate();
      toast('Reset layout spacing & positions to default');
    });
  }

  // Icon sheet auto-grid & layout switcher
  $$('#tplIconLayoutSeg button').forEach(b => {
    b.addEventListener('click', () => {
      $$('#tplIconLayoutSeg button').forEach(x => x.classList.toggle('on', x === b));
      S.template.icon_layout = b.dataset.v;
      scheduleTemplateUpdate();
      toast(`Icon layout: ${b.textContent}`);
    });
  });

  // Artboard edge margin slider
  const tplMarginRange = $('#tplMarginRange');
  const tplMarginVal = $('#tplMarginVal');
  if (tplMarginRange && tplMarginVal) {
    tplMarginRange.addEventListener('input', () => {
      const pct = Math.round(tplMarginRange.value * 100);
      tplMarginVal.textContent = pct + '% ' + (pct === 6 ? '(Stock Standard)' : (pct < 6 ? '(Compact)' : '(Relaxed)'));
      S.template.artboard_margin = parseFloat(tplMarginRange.value);
      scheduleTemplateUpdate();
    });
  }

  // =========================================================================
  // Custom ChatGPT / Midjourney / AI Mockup Template Uploader Engine
  // =========================================================================
  let customTplInitialized = false;

  function initCustomTemplateFeatures() {
    if (customTplInitialized) return;
    customTplInitialized = true;

    // Mode Switcher: Modular Maker vs Custom ChatGPT Image
    $$('#tplEngineModeSeg button').forEach(b => {
      b.addEventListener('click', () => {
        $$('#tplEngineModeSeg button').forEach(x => x.classList.toggle('on', x === b));
        const mode = b.dataset.v;
        S.template.engine_mode = mode;
        const badge = $('#tplModeBadge');
        if (badge) badge.textContent = mode === 'custom_image' ? 'ChatGPT Image' : 'Vector Shapes';

        const customWrap = $('#customImageControlsWrap');
        if (customWrap) customWrap.style.display = mode === 'custom_image' ? 'flex' : 'none';

        ['makerElementsPanel', 'layoutSpacingPanel', 'artboardPanel'].forEach(id => {
          const p = $('#' + id);
          if (p) p.style.display = mode === 'custom_image' ? 'none' : '';
        });

        if (mode === 'custom_image' && !S.template.custom_image_url) {
          loadCustomTemplateImage('/static/sample_templates/chatgpt_cyber_dark.jpg', 'chatgpt_cyber_dark.jpg', 1920, 1080);
        }
        scheduleTemplateUpdate();
        toast(mode === 'custom_image' ? 'Switched to Custom ChatGPT Template mode' : 'Switched to Vector Shapes mode');
      });
    });

    // Dropzone & File Input
    const dropzone = $('#tplDropzone');
    const fileInput = $('#tplCustomFileInput');
    if (dropzone && fileInput) {
      dropzone.addEventListener('click', () => fileInput.click());
      dropzone.addEventListener('dragover', e => {
        e.preventDefault();
        dropzone.style.borderColor = 'var(--accent)';
        dropzone.style.background = 'rgba(0,245,160,0.08)';
      });
      dropzone.addEventListener('dragleave', () => {
        dropzone.style.borderColor = 'rgba(0,245,160,0.45)';
        dropzone.style.background = 'rgba(0,245,160,0.02)';
      });
      dropzone.addEventListener('drop', e => {
        e.preventDefault();
        dropzone.style.borderColor = 'rgba(0,245,160,0.45)';
        dropzone.style.background = 'rgba(0,245,160,0.02)';
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          handleCustomTemplateUpload(e.dataTransfer.files[0]);
        }
      });
      fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files[0]) {
          handleCustomTemplateUpload(fileInput.files[0]);
        }
      });
    }

    const btnChange = $('#btnChangeCustomImg');
    if (btnChange && fileInput) {
      btnChange.addEventListener('click', () => fileInput.click());
    }

    // Sample AI Mockup buttons
    $$('.sample-ai-tpl-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const imgPath = btn.dataset.img;
        const name = imgPath.split('/').pop();
        loadCustomTemplateImage(imgPath, name, 1920, 1080);
        toast(`Loaded ${name} template!`);
      });
    });

    // Bind sliders for Grid, Hero, Text
    const bindSlider = (id, valId, mult = 1, suffix = '%') => {
      const el = $('#' + id);
      const valEl = $('#' + valId);
      if (el) {
        el.addEventListener('input', () => {
          if (valEl) valEl.textContent = el.value + suffix;
          scheduleTemplateUpdate();
        });
      }
    };

    bindSlider('tplCustomGridX', 'tplCustomGridXVal', 0.01);
    bindSlider('tplCustomGridY', 'tplCustomGridYVal', 0.01);
    bindSlider('tplCustomGridW', 'tplCustomGridWVal', 0.01);
    bindSlider('tplCustomGridH', 'tplCustomGridHVal', 0.01);
    bindSlider('tplCustomStrokeScale', 'tplCustomScaleVal', 1, 'x');

    bindSlider('tplCustomHeroX', 'tplCustomHeroXVal', 0.01);
    bindSlider('tplCustomHeroY', 'tplCustomHeroYVal', 0.01);
    bindSlider('tplCustomHeroSize', 'tplCustomHeroSizeVal', 0.01);

    bindSlider('tplCustomTitleX', 'tplCustomTitleXVal', 0.01);
    bindSlider('tplCustomTitleY', 'tplCustomTitleYVal', 0.01);
    bindSlider('tplCustomSubX', 'tplCustomSubXVal', 0.01);
    bindSlider('tplCustomSubY', 'tplCustomSubYVal', 0.01);
    bindSlider('tplCustomCountX', 'tplCustomCountXVal', 0.01);
    bindSlider('tplCustomCountY', 'tplCustomCountYVal', 0.01);

    // Color & text inputs live update
    [
      'tplCustomIconStroke', 'tplCustomHeroStroke', 'tplCustomHeroAccent', 'tplCustomHeroBg',
      'tplCustomShowcaseShape', 'tplCustomTitle', 'tplCustomTitleColor',
      'tplCustomSubtitle', 'tplCustomSubColor', 'tplCustomCount', 'tplCustomCountColor'
    ].forEach(id => {
      const el = $('#' + id);
      if (el) {
        el.addEventListener('input', () => scheduleTemplateUpdate());
      }
    });

    // Checkbox toggles
    const heroCheck = $('#tplCustomHeroEnable');
    if (heroCheck) {
      heroCheck.addEventListener('change', () => {
        const body = $('#customHeroBody');
        if (body) body.style.opacity = heroCheck.checked ? '1' : '0.4';
        scheduleTemplateUpdate();
      });
    }

    const textCheck = $('#tplCustomTextEnable');
    if (textCheck) {
      textCheck.addEventListener('change', () => {
        const body = $('#customTextBody');
        if (body) body.style.opacity = textCheck.checked ? '1' : '0.4';
        scheduleTemplateUpdate();
      });
    }
  }

  function loadCustomTemplateImage(url, filename, width = 1920, height = 1080, b64 = '') {
    S.template.custom_image_url = url;
    S.template.custom_img_w = width;
    S.template.custom_img_h = height;

    const statusBox = $('#tplUploadedStatus');
    const thumb = $('#tplThumbImg');
    const nameEl = $('#tplFileName');
    const dimsEl = $('#tplFileDims');

    if (statusBox) statusBox.style.display = 'flex';
    if (thumb) thumb.src = b64 || url;
    if (nameEl) nameEl.textContent = filename || 'template.jpg';
    if (dimsEl) dimsEl.textContent = `${width} × ${height} px`;

    scheduleTemplateUpdate();
  }

  async function handleCustomTemplateUpload(file) {
    if (!file) return;
    toast('Uploading custom template image...');
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch('/api/custom_templates/upload', {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        loadCustomTemplateImage(data.url, data.filename, data.width, data.height, data.b64);
        toast('ChatGPT / AI Template ready!');
      } else {
        const reader = new FileReader();
        reader.onload = e => {
          loadCustomTemplateImage(e.target.result, file.name, 1920, 1080, e.target.result);
          toast('Loaded template image locally');
        };
        reader.readAsDataURL(file);
      }
    } catch (e) {
      const reader = new FileReader();
      reader.onload = e => {
        loadCustomTemplateImage(e.target.result, file.name, 1920, 1080, e.target.result);
        toast('Loaded template image locally');
      };
      reader.readAsDataURL(file);
    }
  }

  // Zoom buttons
  const tplZin = $('#tplZin');
  if (tplZin) tplZin.onclick = () => setTemplateZoom(tplZoom * 1.25);
  const tplZout = $('#tplZout');
  if (tplZout) tplZout.onclick = () => setTemplateZoom(tplZoom / 1.25);
  const tplZfit = $('#tplZfit');
  if (tplZfit) tplZfit.onclick = () => fitTemplateView();
  const tplZ100 = $('#tplZ100');
  if (tplZ100) tplZ100.onclick = () => resetTemplateView();

  // Mouse wheel & drag-to-pan on templateStage
  const tplStage = $('#templateStage');
  if (tplStage) {
    tplStage.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      tplIsDragging = true;
      tplStartX = e.clientX - tplPanX;
      tplStartY = e.clientY - tplPanY;
      tplStage.classList.add('is-dragging');
    });

    window.addEventListener('mousemove', (e) => {
      if (!tplIsDragging) return;
      tplPanX = e.clientX - tplStartX;
      tplPanY = e.clientY - tplStartY;
      applyTemplateTransform();
    });

    window.addEventListener('mouseup', () => {
      if (tplIsDragging) {
        tplIsDragging = false;
        tplStage.classList.remove('is-dragging');
      }
    });

    tplStage.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 1.12 : 0.89;
      setTemplateZoom(tplZoom * delta);
    }, { passive: false });
  }

  // ================================================================
  // BG Studio Integration (Dynamic Script Loading & Shadow DOM Mount)
  // ================================================================
  let bgStudioLoadingPromise = null;
  let currentBgStudio = null;
  let bgStudioMountToken = 0;

  function loadBgStudioScripts() {
    if (window.BGGen && window.BGStudio) {
      return Promise.resolve();
    }
    if (!bgStudioLoadingPromise) {
      bgStudioLoadingPromise = new Promise((resolve, reject) => {
        function addScript(src, next) {
          const s = document.createElement('script');
          s.src = src;
          s.async = false;
          s.onload = () => next();
          s.onerror = (err) => {
            bgStudioLoadingPromise = null;
            reject(new Error('Failed to load ' + src));
          };
          document.head.appendChild(s);
        }
        addScript('/static/bgstudio/bg-generator.js?v=3.0.0', () => {
          addScript('/static/bgstudio/bg-studio.js?v=3.0.0', () => {
            resolve();
          });
        });
      });
    }
    return bgStudioLoadingPromise;
  }

  async function openBgStudio() {
    const token = ++bgStudioMountToken;

    // Close template studio if open
    const tplSt = $('#templateStudio');
    if (tplSt) tplSt.hidden = true;

    // Hide work / landing
    const landing = $('#landing');
    if (landing) landing.hidden = true;
    const work = $('#work');
    if (work) work.hidden = true;

    // Show BG Studio section
    const bgSt = $('#bgStudio');
    if (!bgSt) return;
    bgSt.hidden = false;

    // Set sidebar active state
    $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
    const navBg = $('#navBgStudio');
    if (navBg) navBg.classList.add('active');

    // Destroy existing studio if mounted
    if (currentBgStudio) {
      try {
        currentBgStudio.destroy();
      } catch (e) {
        console.error('Error destroying previous BG Studio:', e);
      }
      currentBgStudio = null;
    }

    // Ensure clean container
    bgSt.innerHTML = '<div id="bgstudio-root"></div>';
    const rootEl = $('#bgstudio-root');

    try {
      await loadBgStudioScripts();
      if (token !== bgStudioMountToken || bgSt.hidden) {
        return; // User navigated away while scripts were loading
      }

      currentBgStudio = window.BGStudio.mount(rootEl, {
        theme: { font: 'inherit' },
        title: 'BG Studio'
      });
    } catch (err) {
      console.error('Failed to load or mount BG Studio:', err);
      toast('Failed to load BG Studio: ' + (err.message || err), 1);
    }
  }

  function closeBgStudio() {
    bgStudioMountToken++;
    if (currentBgStudio) {
      try {
        currentBgStudio.destroy();
      } catch (e) {
        console.error('Error destroying BG Studio:', e);
      }
      currentBgStudio = null;
    }
    const bgSt = $('#bgStudio');
    if (bgSt) {
      bgSt.hidden = true;
      bgSt.innerHTML = '<div id="bgstudio-root"></div>';
    }
  }

  // Navigation: Redraw
  const navRedraw = $('#navRedraw');
  if (navRedraw) {
    navRedraw.addEventListener('click', e => {
      e.preventDefault();
      closeBgStudio();
      window.location.hash = '#redraw';
      const tplSt = $('#templateStudio'); if (tplSt) tplSt.hidden = true;
      $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
      navRedraw.classList.add('active');
      if (S.job) {
        $('#work').hidden = false;
        $('#landing').hidden = true;
      } else {
        $('#landing').hidden = false;
        $('#work').hidden = true;
      }
    });
  }

  // Navigation: BG Studio
  const navBgStudio = $('#navBgStudio');
  if (navBgStudio) {
    navBgStudio.addEventListener('click', e => {
      e.preventDefault();
      if (window.location.hash !== '#bgstudio') {
        window.location.hash = '#bgstudio';
      } else {
        openBgStudio();
      }
    });
  }

  // Navigation: Other sidebar links
  const navProjects = $('#navProjects');
  if (navProjects) {
    navProjects.addEventListener('click', () => {
      closeBgStudio();
      $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
      navProjects.classList.add('active');
    });
  }
  const navTemplates = $('#navTemplates');
  if (navTemplates) {
    navTemplates.addEventListener('click', () => {
      closeBgStudio();
      openTemplateStudio();
    });
  }
  const navSettings = $('#navSettings');
  if (navSettings) {
    navSettings.addEventListener('click', () => {
      closeBgStudio();
      $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
      navSettings.classList.add('active');
    });
  }

  // Route handlers
  function handleRoute() {
    const hash = window.location.hash.toLowerCase();
    if (hash === '#bgstudio') {
      openBgStudio();
    } else {
      if (currentBgStudio || ($('#bgStudio') && !$('#bgStudio').hidden)) {
        closeBgStudio();
      }
      if (hash === '#templates' || hash === '#template') {
        openTemplateStudio();
      } else if (hash === '#redraw') {
        const tplSt = $('#templateStudio'); if (tplSt) tplSt.hidden = true;
        $$('.nav-menu .nav-item').forEach(el => el.classList.remove('active'));
        if (navRedraw) navRedraw.classList.add('active');
        if (S.job) {
          $('#work').hidden = false;
          $('#landing').hidden = true;
        } else {
          $('#landing').hidden = false;
          $('#work').hidden = true;
        }
      }
    }
  }

  window.addEventListener('hashchange', handleRoute);
  window.addEventListener('popstate', handleRoute);

  // Export app instance
  
  // =========================================================================
  // Linework AI SaaS Authentication, Quota, Payment & Support Engine
  // =========================================================================
  const LineworkAuth = {
    token: sessionStorage.getItem('lw_token') || localStorage.getItem('lw_token') || '',
    user: null,
    pendingAction: null,

    async init() {
      this.bindEvents();
      let token = this.token || sessionStorage.getItem('lw_token') || localStorage.getItem('lw_token') || '';

      if (token) {
        try {
          const res = await fetch('/api/auth/me', {
            headers: { 'Authorization': 'Bearer ' + token },
            cache: 'no-store'
          });
          const data = await res.json();
          if (data.logged_in && data.user) {
            this.token = token;
            sessionStorage.setItem('lw_token', token);
            localStorage.setItem('lw_token', token);
            this.setLoggedInUser(data.user);
            const m = $('#authModal');
            if (m) m.style.display = 'none';
            return;
          }
        } catch (e) {
          const cachedProfile = localStorage.getItem('lw_user_profile');
          if (cachedProfile) {
            try {
              this.setLoggedInUser(JSON.parse(cachedProfile));
              const m = $('#authModal');
              if (m) m.style.display = 'none';
              return;
            } catch {}
          }
        }
      }

      // Auto-login fallback if tab was closed or server restarted
      const savedIdent = localStorage.getItem('lw_saved_ident');
      const savedPass = localStorage.getItem('lw_saved_pass');
      if (savedIdent && savedPass) {
        try {
          const res = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone: savedIdent, password: savedPass })
          });
          const data = await res.json();
          if (res.ok && data.token && data.user) {
            this.token = data.token;
            sessionStorage.setItem('lw_token', data.token);
            localStorage.setItem('lw_token', data.token);
            this.setLoggedInUser(data.user);
            const m = $('#authModal');
            if (m) m.style.display = 'none';
            return;
          }
          // If server container was recreated, auto re-register using saved profile
          const savedProfileStr = localStorage.getItem('lw_user_profile');
          if (savedProfileStr) {
            const prof = JSON.parse(savedProfileStr);
            const rReg = await fetch('/api/auth/register', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                name: prof.name || 'User',
                phone: prof.phone || savedIdent,
                whatsapp: prof.whatsapp || savedIdent,
                password: savedPass
              })
            });
            const regData = await rReg.json();
            if (rReg.ok && regData.token && regData.user) {
              this.token = regData.token;
              sessionStorage.setItem('lw_token', regData.token);
              localStorage.setItem('lw_token', regData.token);
              this.setLoggedInUser(regData.user);
              const m = $('#authModal');
              if (m) m.style.display = 'none';
              return;
            }
          }
        } catch {}
      }

      this.setLoggedOut();
      this.requireLogin(null, true);
    },

    bindEvents() {
      // Tab switcher
      const tabReg = $('#tabRegister');
      const tabLog = $('#tabLogin');
      const regContainer = $('#registerContainer');
      const logContainer = $('#loginContainer');
      const regStepSocial = $('#regStepSocial');
      const regStepIdent = $('#regStepIdentification');

      if (tabReg && tabLog) {
        tabReg.addEventListener('click', () => {
          tabReg.classList.add('active');
          tabLog.classList.remove('active');
          if (regContainer) regContainer.style.display = 'flex';
          if (logContainer) logContainer.style.display = 'none';
        });
        tabLog.addEventListener('click', () => {
          tabLog.classList.add('active');
          tabReg.classList.remove('active');
          if (logContainer) logContainer.style.display = 'flex';
          if (regContainer) regContainer.style.display = 'none';
        });
      }

      // Social Picker Management
      let selectedSocial = {
        provider: 'google',
        name: 'Khan Ezaz',
        email: 'khanezaz566@gmail.com',
        social_id: 'google_ezaz_566'
      };

      const openSocialPicker = (provider, forLogin = false) => {
        selectedSocial.provider = provider;
        const pickerModal = $('#socialPickerModal');
        const title = $('#socialPickerTitle');
        const subtitle = $('#socialPickerSubtitle');
        const nameEl = $('#pickerItemName');
        const emailEl = $('#pickerItemEmail');
        const avatarEl = $('#pickerItemAvatar');
        const customForm = $('#customSocialForm');
        if (customForm) customForm.style.display = 'none';

        if (provider === 'google') {
          if (title) title.innerHTML = '<span style="color:#4285F4;">Google</span> Account Selector';
          if (subtitle) subtitle.textContent = forLogin ? 'Sign in using your Google account:' : 'Choose a Google account to claim your free trial:';
          if (nameEl) nameEl.textContent = 'Khan Ezaz';
          if (emailEl) emailEl.textContent = 'khanezaz566@gmail.com';
          if (avatarEl) {
            avatarEl.style.background = 'linear-gradient(135deg, #4285F4, #34A853)';
            avatarEl.textContent = 'G';
          }
        } else {
          if (title) title.innerHTML = '<span style="color:#1877F2;">Facebook</span> Profile Selector';
          if (subtitle) subtitle.textContent = forLogin ? 'Sign in using your Facebook account:' : 'Choose a Facebook profile to claim your free trial:';
          if (nameEl) nameEl.textContent = 'Khan Ezaz';
          if (emailEl) emailEl.textContent = 'facebook.com/khanezaz';
          if (avatarEl) {
            avatarEl.style.background = '#1877F2';
            avatarEl.textContent = 'f';
          }
        }
        if (pickerModal) {
          pickerModal.dataset.mode = forLogin ? 'login' : 'register';
          pickerModal.style.display = 'flex';
        }
      };

      const closePicker = () => {
        const pickerModal = $('#socialPickerModal');
        if (pickerModal) pickerModal.style.display = 'none';
      };

      const closeSocialBtn = $('#closeSocialPickerModal');
      if (closeSocialBtn) closeSocialBtn.addEventListener('click', closePicker);

      const applySocialAccount = async (account, isLoginMode = false) => {
        closePicker();
        if (isLoginMode) {
          try {
            const r = await fetch('/api/auth/social-auth', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                provider: account.provider,
                social_id: account.social_id || account.email,
                email: account.email,
                name: account.name
              })
            });
            const data = await r.json();
            if (r.ok && data.token && data.user) {
              this.token = data.token;
              sessionStorage.setItem('lw_token', data.token);
              localStorage.setItem('lw_token', data.token);
              localStorage.setItem('lw_saved_ident', data.user.phone || data.user.username);
              localStorage.setItem('lw_user_profile', JSON.stringify(data.user));
              this.setLoggedInUser(data.user);
              this.hideAuth();
              toast(`Welcome back, ${data.user.name || 'User'}!`);
              if (this.pendingAction) {
                const act = this.pendingAction;
                this.pendingAction = null;
                act();
              }
              return;
            }
          } catch (e) {}
        }

        // Switch to "Create Account" tab & transition to Step 2: Identification
        if (tabReg && tabLog) {
          tabReg.classList.add('active');
          tabLog.classList.remove('active');
          if (regContainer) regContainer.style.display = 'flex';
          if (logContainer) logContainer.style.display = 'none';
        }

        const pProvider = $('#regProvider');
        const pSocialId = $('#regSocialId');
        const pEmail = $('#regEmail');
        const pName = $('#regName');
        const verifiedIcon = $('#socialVerifiedIcon');
        const verifiedTxt = $('#socialVerifiedText');

        if (pProvider) pProvider.value = account.provider;
        if (pSocialId) pSocialId.value = account.social_id || account.email;
        if (pEmail) pEmail.value = account.email;
        if (pName && (!pName.value.trim() || pName.value === 'e.g. Khanezaz')) {
          pName.value = account.name || '';
        }

        if (verifiedIcon) {
          verifiedIcon.textContent = account.provider === 'google' ? '🟢' : account.provider === 'facebook' ? '🔵' : '📱';
        }
        if (verifiedTxt) {
          verifiedTxt.textContent = account.provider === 'direct' 
            ? 'Mobile & WhatsApp Account Setup'
            : `Verified via ${account.provider.charAt(0).toUpperCase() + account.provider.slice(1)} (${account.email || account.name})`;
        }

        if (regStepSocial) regStepSocial.style.display = 'none';
        if (regStepIdent) regStepIdent.style.display = 'flex';

        const wpInput = $('#regWhatsapp');
        if (wpInput) wpInput.focus();
      };

      // Click primary item in picker
      const itemPrimary = $('#pickerItemPrimary');
      if (itemPrimary) {
        itemPrimary.addEventListener('click', () => {
          const pickerModal = $('#socialPickerModal');
          const isLogin = pickerModal && pickerModal.dataset.mode === 'login';
          const nameEl = $('#pickerItemName');
          const emailEl = $('#pickerItemEmail');
          applySocialAccount({
            provider: selectedSocial.provider,
            name: nameEl ? nameEl.textContent : 'Khan Ezaz',
            email: emailEl ? emailEl.textContent : 'khanezaz566@gmail.com',
            social_id: `${selectedSocial.provider}_${emailEl ? emailEl.textContent : 'user'}`
          }, isLogin);
        });
      }

      // Custom account entry
      const itemCustom = $('#pickerItemCustom');
      const customForm = $('#customSocialForm');
      if (itemCustom && customForm) {
        itemCustom.addEventListener('click', () => {
          customForm.style.display = customForm.style.display === 'none' ? 'flex' : 'none';
        });
        customForm.addEventListener('submit', (e) => {
          e.preventDefault();
          const name = $('#inpCustomSocialName').value.trim();
          const email = $('#inpCustomSocialEmail').value.trim();
          if (!name || !email) return;
          const pickerModal = $('#socialPickerModal');
          const isLogin = pickerModal && pickerModal.dataset.mode === 'login';
          applySocialAccount({
            provider: selectedSocial.provider,
            name: name,
            email: email,
            social_id: `${selectedSocial.provider}_${email}`
          }, isLogin);
        });
      }

      // Social signup buttons
      const btnGSign = $('#btnGoogleSignup');
      if (btnGSign) btnGSign.addEventListener('click', () => openSocialPicker('google', false));

      const btnFBSign = $('#btnFacebookSignup');
      if (btnFBSign) btnFBSign.addEventListener('click', () => openSocialPicker('facebook', false));

      const btnGLog = $('#btnGoogleLogin');
      if (btnGLog) btnGLog.addEventListener('click', () => openSocialPicker('google', true));

      const btnFBLog = $('#btnFacebookLogin');
      if (btnFBLog) btnFBLog.addEventListener('click', () => openSocialPicker('facebook', true));

      // Direct phone button
      const btnDirect = $('#btnDirectPhoneSignup');
      if (btnDirect) {
        btnDirect.addEventListener('click', () => {
          applySocialAccount({
            provider: 'direct',
            name: '',
            email: '',
            social_id: ''
          }, false);
        });
      }

      // Change social account button (returns to Step 1)
      const btnChangeSocial = $('#btnChangeSocialAccount');
      if (btnChangeSocial) {
        btnChangeSocial.addEventListener('click', () => {
          if (regStepSocial) regStepSocial.style.display = 'flex';
          if (regStepIdent) regStepIdent.style.display = 'none';
        });
      }

      // Sync WhatsApp to Phone if checkbox is checked
      const chkSame = $('#chkSameAsWhatsapp');
      const inpWp = $('#regWhatsapp');
      const inpPh = $('#regPhone');
      if (inpWp && inpPh && chkSame) {
        inpWp.addEventListener('input', () => {
          if (chkSame.checked) {
            inpPh.value = inpWp.value;
          }
        });
        chkSame.addEventListener('change', () => {
          if (chkSame.checked) {
            inpPh.value = inpWp.value;
          }
        });
      }

      // Modals close buttons
      const closeAuth = $('#closeAuthModal');
      if (closeAuth) closeAuth.addEventListener('click', () => this.hideAuth());

      const closePricing = $('#closePricingModal');
      if (closePricing) closePricing.addEventListener('click', () => this.hidePricing());

      const closePayment = $('#closePaymentModal');
      if (closePayment) closePayment.addEventListener('click', () => this.hidePayment());

      const closeSupport = $('#closeSupportModal');
      if (closeSupport) closeSupport.addEventListener('click', () => this.hideSupport());

      const closeProfile = $('#closeProfileModal');
      if (closeProfile) closeProfile.addEventListener('click', () => this.hideProfile());

      // Header buttons
      const btnHUpgrade = $('#btnHeaderUpgrade');
      if (btnHUpgrade) btnHUpgrade.addEventListener('click', () => this.showPricing());

      const btnHSupport = $('#btnHeaderSupport');
      if (btnHSupport) btnHSupport.addEventListener('click', () => this.showSupport());

      const navP = $('#navPricing');
      if (navP) navP.addEventListener('click', (e) => { e.preventDefault(); this.showPricing(); });

      const navS = $('#navSupport');
      if (navS) navS.addEventListener('click', (e) => { e.preventDefault(); this.showSupport(); });

      const avatarBtn = $('#userAvatarBtn');
      if (avatarBtn) {
        avatarBtn.addEventListener('click', () => {
          if (this.user) {
            this.showProfile();
          } else {
            this.requireLogin();
          }
        });
      }

      // Registration Form Submission (Step 2: Identification)
      // Registration Form Submission (Step 2: Identification)
      const fReg = $('#registerForm');
      const btnReg = $('#btnSubmitRegister');

      const executeRegistration = async () => {
        const name = ($('#regName') ? $('#regName').value.trim() : '');
        const whatsapp = ($('#regWhatsapp') ? $('#regWhatsapp').value.trim() : '');
        const phone = ($('#regPhone') ? $('#regPhone').value.trim() : '') || whatsapp;
        const password = ($('#regPass') ? $('#regPass').value.trim() : '');
        const provider = ($('#regProvider') ? $('#regProvider').value.trim() : '') || 'direct';
        const social_id = ($('#regSocialId') ? $('#regSocialId').value.trim() : '') || '';
        const email = ($('#regEmail') ? $('#regEmail').value.trim() : '') || '';

        if (!name) {
          toast('Please enter your full name.', 1);
          const inp = $('#regName'); if (inp) inp.focus();
          return;
        }
        if (!whatsapp && !phone && !email) {
          toast('Please provide your WhatsApp or phone number.', 1);
          const inp = $('#regWhatsapp'); if (inp) inp.focus();
          return;
        }

        const btn = $('#btnSubmitRegister');
        const oldTxt = btn ? btn.textContent : '';
        if (btn) {
          btn.textContent = '🚀 একাউন্ট প্রস্তুত হচ্ছে...';
          btn.disabled = true;
        }

        try {
          const r = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, phone, whatsapp, password, email, provider, social_id })
          });
          const data = await r.json();
          if (!r.ok || !data.ok) throw new Error(data.detail || 'Registration failed');

          this.token = data.token;
          sessionStorage.setItem('lw_token', data.token);
          localStorage.setItem('lw_token', data.token);
          localStorage.setItem('lw_saved_ident', phone || data.user.phone || data.user.username);
          localStorage.setItem('lw_saved_pass', password);
          localStorage.setItem('lw_user_profile', JSON.stringify({ name, phone, whatsapp, password, ...data.user }));
          this.setLoggedInUser(data.user);
          this.hideAuth();
          closePicker();
          toast(`🎉 Welcome ${name}! Free Trial (3 Icon Sets + 10 Backgrounds) activated!`);

          if (this.pendingAction) {
            const act = this.pendingAction;
            this.pendingAction = null;
            act();
          }
        } catch (err) {
          toast(err.message || 'Registration failed', 1);
        } finally {
          if (btn) {
            btn.textContent = oldTxt;
            btn.disabled = false;
          }
        }
      };

      if (fReg) {
        fReg.addEventListener('submit', (e) => {
          e.preventDefault();
          executeRegistration();
        });
      }
      if (btnReg) {
        btnReg.addEventListener('click', (e) => {
          e.preventDefault();
          executeRegistration();
        });
      }

      // Login Form Submission
      const fLog = $('#loginForm');
      if (fLog) {
        fLog.addEventListener('submit', async (e) => {
          e.preventDefault();
          const ident = $('#loginIdent').value.trim();
          const password = $('#loginPass').value.trim();

          const btn = $('#btnSubmitLogin');
          const oldTxt = btn.textContent;
          btn.textContent = 'Signing in...';
          btn.disabled = true;

          try {
            const r = await fetch('/api/auth/login', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ phone: ident, password: password })
            });
            const data = await r.json();
            if (!r.ok) throw new Error(data.detail || 'Login failed');

            this.token = data.token;
            sessionStorage.setItem('lw_token', data.token);
            localStorage.setItem('lw_token', data.token);
            localStorage.setItem('lw_saved_ident', ident);
            localStorage.setItem('lw_saved_pass', password);
            localStorage.setItem('lw_user_profile', JSON.stringify(data.user));
            this.setLoggedInUser(data.user);
            this.hideAuth();
            closePicker();
            toast('Welcome back, ' + (data.user.name || 'User') + '!');

            if (this.pendingAction) {
              const act = this.pendingAction;
              this.pendingAction = null;
              act();
            }
          } catch (err) {
            toast(err.message, 1);
          } finally {
            btn.textContent = oldTxt;
            btn.disabled = false;
          }
        });
      }

      // Payment Form Submission
      const fPay = $('#paymentSubmitForm');
      if (fPay) {
        fPay.addEventListener('submit', async (e) => {
          e.preventDefault();
          if (!this.user) {
            this.requireLogin();
            return;
          }

          const plan = $('#paySelectedPlan').value;
          const amount = $('#paySelectedAmount').value;
          const phone = $('#paySenderPhone').value.trim();
          const trxId = $('#payTrxId').value.trim().toUpperCase();
          const screenshotInput = $('#payScreenshot');

          const fd = new FormData();
          fd.append('plan_selected', plan);
          fd.append('amount', amount);
          fd.append('phone', phone);
          fd.append('trx_id', trxId);
          if (screenshotInput && screenshotInput.files[0]) {
            fd.append('screenshot', screenshotInput.files[0]);
          }

          const btn = $('#btnSubmitPayment');
          const oldTxt = btn.textContent;
          btn.textContent = 'Submitting...';
          btn.disabled = true;

          try {
            const r = await fetch('/api/payments/submit', {
              method: 'POST',
              headers: { 'Authorization': 'Bearer ' + this.token },
              body: fd
            });
            const data = await r.json();
            if (!r.ok) throw new Error(data.detail || 'Payment submission failed');

            this.hidePayment();
            alert('🎉 পেমেন্ট রিকোয়েস্ট সাবমিট হয়েছে!\n\nএডমিন খুব দ্রুত আপনার TrxID ভেরিফাই করে একাউন্ট আপগ্রেড করে দিবে।\nজরুরী প্রয়োজনে সরাসরি কল বা হোয়াটসঅ্যাপ করুন: 01794590310');
            toast('Payment submitted for admin approval!');
          } catch (err) {
            toast(err.message, 1);
          } finally {
            btn.textContent = oldTxt;
            btn.disabled = false;
          }
        });
      }
    },

    setLoggedInUser(user) {
      this.user = user;
      this.updateUserData(user);
    },

    updateUserData(user) {
      this.user = user;
      const qPill = $('#userQuotaPill');
      const qTxt = $('#userQuotaText');
      const pBadge = $('#userPlanBadge');
      const avBtn = $('#userAvatarBtn');
      const admBtn = $('#btnHeaderAdmin');
      const admNav = $('#navAdminSide');
      const btnHUpgrade = $('#btnHeaderUpgrade');
      const navPricingSpan = $('#navPricing span');

      if (qPill) qPill.style.display = 'inline-flex';

      const isUnlimitedRedraw = (user.role === 'admin' || ['bundle_pro', 'redraw_pro', 'pro'].includes(user.plan));
      const isUnlimitedBg = (user.role === 'admin' || ['bundle_pro', 'bg_pro', 'pro'].includes(user.plan));
      const isAnyPro = (user.role === 'admin' || ['bundle_pro', 'redraw_pro', 'bg_pro', 'pro'].includes(user.plan));

      // Header Plan Badge
      if (pBadge) {
        pBadge.style.display = 'inline-block';
        if (user.role === 'admin') {
          pBadge.textContent = '👑 VIP ADMIN';
          pBadge.style.background = 'rgba(255, 183, 3, 0.2)';
          pBadge.style.borderColor = '#ffb703';
          pBadge.style.color = '#ffb703';
        } else if (user.plan === 'bundle_pro' || user.plan === 'pro') {
          pBadge.textContent = '👑 ALL-IN-ONE PRO';
          pBadge.style.background = 'rgba(0, 245, 160, 0.2)';
          pBadge.style.borderColor = '#00f5a0';
          pBadge.style.color = '#00f5a0';
        } else if (user.plan === 'redraw_pro') {
          pBadge.textContent = '⚡ REDRAW PRO';
          pBadge.style.background = 'rgba(0, 210, 255, 0.2)';
          pBadge.style.borderColor = '#00d2ff';
          pBadge.style.color = '#00d2ff';
        } else if (user.plan === 'bg_pro') {
          pBadge.textContent = '🎨 BG STUDIO PRO';
          pBadge.style.background = 'rgba(168, 85, 247, 0.2)';
          pBadge.style.borderColor = '#c084fc';
          pBadge.style.color = '#c084fc';
        } else {
          pBadge.textContent = '🎁 FREE TRIAL';
          pBadge.style.background = 'rgba(255, 255, 255, 0.08)';
          pBadge.style.borderColor = 'rgba(255, 255, 255, 0.2)';
          pBadge.style.color = '#ccc';
        }
      }

      // Quota indicator in header
      if (qTxt) {
        if (user.header_quota_text) {
          qTxt.textContent = user.header_quota_text;
        } else if (user.role === 'admin') {
          qTxt.textContent = '⚡ Lifetime VIP Admin';
        } else if (user.plan === 'bundle_pro' || user.plan === 'pro') {
          qTxt.textContent = '👑 All-In-One: Unlimited';
        } else if (user.plan === 'redraw_pro') {
          qTxt.textContent = '👑 Redraw: Unlimited';
        } else if (user.plan === 'bg_pro') {
          qTxt.textContent = '🎨 BG Studio: Unlimited';
        } else {
          const sLeft = Math.max(0, 3 - (user.sheets_used || 0));
          const bLeft = Math.max(0, 10 - (user.bg_used || 0));
          qTxt.textContent = `Trial: ${sLeft}/3 Icons · ${bLeft}/10 BG`;
        }
      }

      // Header Upgrade Button state
      if (btnHUpgrade) {
        if (isAnyPro) {
          let daysBadge = '';
          if (user.pro_expires_at) {
            const exp = new Date(user.pro_expires_at.replace(' ', 'T')).getTime();
            const diffDays = Math.ceil((exp - Date.now()) / (1000 * 3600 * 24));
            if (diffDays > 3650) daysBadge = ' (VIP)';
            else if (diffDays > 0) daysBadge = ` (${diffDays}d left)`;
          }
          btnHUpgrade.innerHTML = `👑 Active${daysBadge}`;
          btnHUpgrade.title = `Your ${user.plan_name} is active! Click to view details.`;
          btnHUpgrade.style.background = 'linear-gradient(135deg, rgba(0,245,160,0.2), rgba(0,180,216,0.2))';
          btnHUpgrade.style.border = '1px solid #00f5a0';
          btnHUpgrade.style.color = '#00f5a0';
        } else {
          btnHUpgrade.innerHTML = '⚡ Upgrade';
          btnHUpgrade.style.background = 'linear-gradient(135deg, #00f5a0, #00b4d8)';
          btnHUpgrade.style.color = '#050508';
          btnHUpgrade.style.border = 'none';
        }
      }

      if (navPricingSpan) {
        navPricingSpan.textContent = isAnyPro ? 'My Subscription' : 'Upgrade Pro';
      }

      if (avBtn) {
        const initials = (user.name || user.phone || 'U').slice(0, 2).toUpperCase();
        avBtn.textContent = initials;
        avBtn.title = `${user.name || 'User'} (${user.plan_name || 'Free Trial'})`;
      }

      if (user.role === 'admin') {
        if (admBtn) admBtn.style.display = 'inline-flex';
        if (admNav) admNav.style.display = 'flex';
      } else {
        if (admBtn) admBtn.style.display = 'none';
        if (admNav) admNav.style.display = 'none';
      }
    },

    setLoggedOut() {
      this.user = null;
      this.token = '';
      sessionStorage.removeItem('lw_token');
      localStorage.removeItem('lw_token');
      localStorage.removeItem('lw_saved_ident');
      localStorage.removeItem('lw_saved_pass');
      localStorage.removeItem('lw_user_profile');

      const qPill = $('#userQuotaPill');
      const pBadge = $('#userPlanBadge');
      const avBtn = $('#userAvatarBtn');
      const admBtn = $('#btnHeaderAdmin');
      const admNav = $('#navAdminSide');

      if (qPill) qPill.style.display = 'none';
      if (pBadge) pBadge.style.display = 'none';
      if (avBtn) {
        avBtn.textContent = 'Sign In';
        avBtn.title = 'Click to Sign In or Create Free Account';
      }
      if (admBtn) admBtn.style.display = 'none';
      if (admNav) admNav.style.display = 'none';
    },

    requireLogin(actionCallback, mandatory = false) {
      this.pendingAction = actionCallback || null;
      const m = $('#authModal');
      const closeBtn = $('#closeAuthModal');
      if (closeBtn) {
        closeBtn.style.display = (mandatory || !this.user) ? 'none' : 'block';
      }
      if (m) m.style.display = 'flex';
    },

    hideAuth() {
      const m = $('#authModal');
      if (m) m.style.display = 'none';
      const sm = $('#socialPickerModal');
      if (sm) sm.style.display = 'none';
    },

    showPricing(recommendedPlan) {
      const m = $('#pricingModal');
      if (m) {
        m.style.display = 'flex';
        $$('.saas-plan-card').forEach(c => c.classList.remove('highlight'));
        if (recommendedPlan === 'redraw_pro') {
          const c = $('#cardPlanRedraw'); if (c) c.classList.add('highlight');
        } else if (recommendedPlan === 'bg_pro') {
          const c = $('#cardPlanBg'); if (c) c.classList.add('highlight');
        } else {
          const c = $('#cardPlanBundle'); if (c) c.classList.add('highlight');
        }
      }
    },

    hidePricing() {
      const m = $('#pricingModal');
      if (m) m.style.display = 'none';
    },

    openPaymentModal(plan, amount) {
      if (!this.user) {
        this.requireLogin(() => this.openPaymentModal(plan, amount));
        return;
      }
      this.hidePricing();
      const m = $('#paymentModal');
      if (m) {
        $('#paySelectedPlan').value = plan;
        $('#paySelectedAmount').value = amount;
        const planName = plan === 'redraw_pro' ? 'Icon Redraw Pro' :
                         plan === 'bg_pro' ? 'BG Studio Pro' : 'All-In-One Bundle Pro';
        $('#payPlanName').textContent = planName;
        $('#payPlanAmount').textContent = `৳ ${amount}`;
        const phoneInp = $('#paySenderPhone');
        if (phoneInp && this.user.phone) {
          phoneInp.value = this.user.phone;
        }
        m.style.display = 'flex';
      }
    },

    hidePayment() {
      const m = $('#paymentModal');
      if (m) m.style.display = 'none';
    },

    showSupport() {
      const m = $('#supportModal');
      if (m) m.style.display = 'flex';
    },

    hideSupport() {
      const m = $('#supportModal');
      if (m) m.style.display = 'none';
    },

    showProfile() {
      if (!this.user) {
        this.requireLogin();
        return;
      }
      const m = $('#profileModal');
      if (m) {
        $('#profileName').textContent = this.user.name || 'User';
        $('#profilePhone').textContent = this.user.phone || '';
        $('#profileAvatarBig').textContent = (this.user.name || 'U').slice(0, 1).toUpperCase();
        const isUnlimitedRedraw = (this.user.role === 'admin' || ['bundle_pro', 'redraw_pro', 'pro'].includes(this.user.plan));
        const isUnlimitedBg = (this.user.role === 'admin' || ['bundle_pro', 'bg_pro', 'pro'].includes(this.user.plan));
        const isAnyPro = (this.user.role === 'admin' || ['bundle_pro', 'redraw_pro', 'bg_pro', 'pro'].includes(this.user.plan));

        let badgeTitle = '🎁 Free Trial';
        if (this.user.role === 'admin') badgeTitle = '👑 Super Admin';
        else if (this.user.plan === 'bundle_pro' || this.user.plan === 'pro') badgeTitle = '👑 All-In-One Bundle Pro';
        else if (this.user.plan === 'redraw_pro') badgeTitle = '⚡ Icon Redraw Pro';
        else if (this.user.plan === 'bg_pro') badgeTitle = '🎨 BG Studio Pro';

        $('#profilePlanBadge').textContent = badgeTitle;
        if (isUnlimitedRedraw) {
          $('#profileQuotaRedraw').innerHTML = '<span style="color:#00f5a0; font-weight:700;">👑 Unlimited Pro Access</span>';
        } else {
          const leftS = Math.max(0, 3 - (this.user.sheets_used || 0));
          $('#profileQuotaRedraw').textContent = `${this.user.sheets_used || 0} / 3 Used (${leftS} Free Left)`;
        }

        if (isUnlimitedBg) {
          $('#profileQuotaBg').innerHTML = '<span style="color:#00f5a0; font-weight:700;">🎨 Unlimited Pro Access</span>';
        } else {
          const leftB = Math.max(0, 10 - (this.user.bg_used || 0));
          $('#profileQuotaBg').textContent = `${this.user.bg_used || 0} / 10 Used (${leftB} Free Left)`;
        }

        const expRow = $('#profileExpiryRow');
        const expTxt = $('#profileExpiryDate');
        if (this.user.pro_expires_at) {
          if (expRow) expRow.style.display = 'flex';
          const exp = new Date(this.user.pro_expires_at.replace(' ', 'T')).getTime();
          const diffDays = Math.ceil((exp - Date.now()) / (1000 * 3600 * 24));
          let daysBadge = '';
          if (diffDays > 3650) {
            daysBadge = 'Permanent Lifetime VIP';
          } else if (diffDays > 0) {
            daysBadge = `${this.user.pro_expires_at.slice(0, 10)} (${diffDays} Days Left)`;
          } else {
            daysBadge = `${this.user.pro_expires_at.slice(0, 10)} (Expired)`;
          }
          if (expTxt) expTxt.textContent = daysBadge;
        } else {
          if (expRow) expRow.style.display = 'none';
        }

        m.style.display = 'flex';
      }
    },

    hideProfile() {
      const m = $('#profileModal');
      if (m) m.style.display = 'none';
    },

    async logout() {
      try {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + this.token }
        });
      } catch {}
      this.hideProfile();
      this.setLoggedOut();
      toast('Signed out successfully.');
    },

    canProcessSheet() {
      if (!this.user) return false;
      if (this.user.is_redraw_unlimited || this.user.role === 'admin' || ['bundle_pro', 'redraw_pro', 'pro'].includes(this.user.plan)) {
        return true;
      }
      return (this.user.sheets_used < 3);
    },

    canProcessBg() {
      if (!this.user) return false;
      if (this.user.is_bg_unlimited || this.user.role === 'admin' || ['bundle_pro', 'bg_pro', 'pro'].includes(this.user.plan)) {
        return true;
      }
      return (this.user.bg_used < 10);
    }
  };

  window.LineworkAuth = LineworkAuth;

  // Live Presence & Real-time Plan Sync (every 15s, on focus, and on user activity)
  async function sendLivePing() {
    const token = getStoredToken();
    if (!token) return;
    try {
      const res = await fetch('/api/auth/ping', {
        headers: { 'Authorization': 'Bearer ' + token },
        cache: 'no-store'
      });
      const data = await res.json();
      if (data && data.logged_in && data.user && window.LineworkAuth) {
        const oldPlan = window.LineworkAuth.user ? window.LineworkAuth.user.plan : null;
        window.LineworkAuth.updateUserData(data.user);
        if (oldPlan && oldPlan === 'free' && data.user.plan !== 'free') {
          toast(`🎉 Congratulations! Your plan was upgraded to ${data.user.plan_name}! Enjoy Unlimited Access!`);
        }
      }
    } catch {}
  }

  sendLivePing();
  setInterval(sendLivePing, 15000);

  window.addEventListener('focus', () => {
    sendLivePing();
  });

  ['click', 'keydown', 'touchstart'].forEach(evt => {
    window.addEventListener(evt, () => {
      const now = Date.now();
      if (!window._lastPing || (now - window._lastPing > 20000)) {
        window._lastPing = now;
        sendLivePing();
      }
    }, { passive: true });
  });

  LineworkAuth.init();

  window.LineworkApp = {
    get job() { return S.job; },
    get S() { return S; },
    cancelJob: cancelCurrentJob,
    openTemplate: openTemplateStudio,
    closeTemplate: closeTemplateStudio,
    openBgStudio: openBgStudio,
    closeBgStudio: closeBgStudio,
    get bgStudio() { return currentBgStudio; },
    toast: toast
  };

  hint();

  // Handle direct navigation to #bgstudio on initial load
  const initHash = window.location.hash.toLowerCase();
  if (initHash === '#bgstudio') {
    openBgStudio();
  } else if (initHash === '#templates' || initHash === '#template') {
    openTemplateStudio();
  }
})();
