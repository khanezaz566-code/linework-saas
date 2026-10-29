(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const S = { job: null, since: 0, version: -1, view: 'vector', sel: null, W: 0, H: 0, tf: { x: 0, y: 0, k: 1 }, timer: null, quality: 'standard', icons: [], done: false, logN: 0, editCount: 0 };

  // ---------------------------------------------------------------- helpers
  const toast = (msg, err) => { const t = $('#toast'); t.textContent = msg; t.className = 'toast show' + (err ? ' err' : ''); clearTimeout(toast.t); toast.t = setTimeout(() => t.className = 'toast', 3200); };
  const api = (p, o) => fetch(p, o).then(async r => { if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); } return r; });
  const fmt = n => (n * 100).toFixed(1) + '%';

  fetch('/api/health').then(r => r.json()).then(h => { const p = $('#health'); p.classList.add('ok'); p.lastElementChild.textContent = `engines online · ${h.renderer}`; })
    .catch(() => { const p = $('#health'); p.classList.add('bad'); p.lastElementChild.textContent = 'offline'; });

  // ---------------------------------------------------------------- options
  $('#quality').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; S.quality = b.dataset.v; $$('#quality button').forEach(x => x.classList.toggle('on', x === b)); });
  const hint = () => { const v = +$('#clean').value; $('#cleanHint').textContent = v < .2 ? 'Exact match' : v > .8 ? 'Cleanest paths' : 'Balanced'; };
  $('#clean').addEventListener('input', hint);

  // ---------------------------------------------------------------- upload
  const drop = $('#drop'), file = $('#file');
  drop.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); file.click(); } });
  file.addEventListener('change', () => file.files[0] && upload(file.files[0]));
  ['dragenter', 'dragover'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', e => { const f = e.dataTransfer.files[0]; if (f) upload(f); });
  window.addEventListener('paste', e => { const it = [...(e.clipboardData?.items || [])].find(i => i.type.startsWith('image/')); if (it && !S.job) upload(it.getAsFile()); });
  $$('[data-sample]').forEach(b => b.addEventListener('click', async () => {
    try { const r = await api(`/api/samples/${b.dataset.sample}?quality=${S.quality}`, { method: 'POST' }); begin((await r.json()).id, b.dataset.sample); } catch (e) { toast(e.message, 1); }
  }));

  async function upload(f) {
    const fd = new FormData();
    fd.append('file', f); fd.append('quality', S.quality); fd.append('clean', $('#clean').value);
    try { const r = await api('/api/jobs', { method: 'POST', body: fd }); begin((await r.json()).id, f.name || 'pasted image'); }
    catch (e) { toast(e.message, 1); }
    file.value = '';
  }

  // ---------------------------------------------------------------- workspace lifecycle
  function begin(id, name) {
    Object.assign(S, { job: id, since: 0, version: -1, done: false, sel: null, icons: [], logN: 0, editCount: 0 });
    $('#landing').hidden = true; $('#work').hidden = false;
    $('#jobName').textContent = name; $('#log').innerHTML = ''; $('#icons').innerHTML = ''; $('#summary').hidden = true;
    $('#prog').classList.remove('done'); $('#prog i').style.width = '3%';
    $$('.eng').forEach(e => { e.className = 'eng'; $('em', e).textContent = ''; });
    ['dlSvg', 'dlZip', 'copy'].forEach(i => $('#' + i).classList.add('disabled'));
    $('#vec').innerHTML = ''; $('#imgDiff').removeAttribute('src');
    const o = $('#imgOrig'); o.onload = () => { S.W = o.naturalWidth; S.H = o.naturalHeight; sizeCanvas(); fit(); }; o.src = `/api/jobs/${id}/original.png`;
    setView('vector'); clearTimeout(S.timer); poll();
  }
  $('#newJob').addEventListener('click', () => { clearTimeout(S.timer); S.job = null; $('#work').hidden = true; $('#landing').hidden = false; });

  async function poll() {
    if (!S.job) return;
    const id = S.job;
    try {
      const j = await (await api(`/api/jobs/${id}?since=${S.since}`)).json();
      if (id !== S.job) return;
      S.since = j.next; ingest(j);
      if (j.status === 'error') { toast(j.error || 'Job failed', 1); return; }
      if (j.status === 'done') { finish(j); return; }
    } catch (e) { /* transient */ }
    S.timer = setTimeout(poll, 650);
  }

  // ---------------------------------------------------------------- state -> UI
  const ENGINE = { trace: 'edit', split: 'edit', edit: 'edit', output: 'output', doctor: 'doctor' };
  function ingest(j) {
    S.icons = j.icons;
    const total = j.icons.length, done = j.icons.filter(i => i.status === 'done').length;
    $('#prog i').style.width = total ? Math.max(4, done / total * 100) + '%' : '4%';
    $('#iconCount').textContent = total ? `${done}/${total}` : '';
    if (j.width && !S.W) { S.W = j.width; S.H = j.height; }
    // engines + log
    const log = $('#log'); let last = null;
    for (const e of j.events) {
      last = e;
      const eng = ENGINE[e.engine] || 'edit';
      if (eng === 'edit' && e.engine === 'edit') S.editCount++;
      const el = $(`.eng[data-e=${eng}]`); if (el && e.iou != null && eng !== 'edit') $('em', el).textContent = fmt(e.iou);
      if (S.logN++ < 400) {
        const li = document.createElement('li');
        li.innerHTML = `<u>${e.icon ? e.icon.replace('icon', '#') : ''}</u><s class="${e.engine}">${e.engine}</s><span></span>`;
        li.lastChild.textContent = e.msg; log.appendChild(li);
      }
    }
    log.scrollTop = log.scrollHeight;
    $('.eng[data-e=edit] em').textContent = S.editCount ? `${S.editCount} steps` : '';
    if (last && j.status !== 'done') { $$('.eng').forEach(x => x.classList.remove('live')); const el = $(`.eng[data-e=${ENGINE[last.engine] || 'edit'}]`); el && el.classList.add('live'); }
    renderIcons(j);
    if (j.version !== S.version && j.version > 0) { S.version = j.version; loadSvg(); }
  }

  function renderIcons(j) {
    const box = $('#icons');
    j.icons.forEach(ic => {
      let el = box.children[ic.k];
      if (!el) { el = document.createElement('div'); el.className = 'ic'; el.dataset.k = ic.k; el.innerHTML = '<img alt=""><span class="pc"></span>'; el.addEventListener('click', () => selectIcon(ic.k)); box.appendChild(el); }
      const done = ic.status === 'done';
      el.classList.toggle('run', !done && ic.status !== 'error'); el.classList.toggle('err', ic.status === 'error');
      const pc = $('.pc', el);
      pc.textContent = done ? fmt(ic.iou) : (ic.live_iou ? fmt(ic.live_iou) : '…');
      const img = $('img', el);
      if (done && !img.dataset.ok) {
        img.dataset.ok = 1; let n = 0;
        const load = () => { img.src = `/api/jobs/${S.job}/icons/${ic.k}.svg?r=${n}`; };
        img.onerror = () => { if (n++ < 5) setTimeout(load, 500 * n); };
        load();
      }
    });
  }

  function finish(j) {
    S.done = true; $('#prog').classList.add('done'); $('#prog i').style.width = '100%';
    $$('.eng').forEach(x => { x.classList.remove('live'); x.classList.add('ok'); });
    const ms = j.icons.map(i => i.metrics).filter(Boolean);
    const paths = ms.reduce((a, m) => a + m.paths, 0), nodes = ms.reduce((a, m) => a + m.nodes, 0);
    const s = $('#summary'); s.hidden = false;
    s.innerHTML = [['Match', fmt(j.iou)], ['Icons', j.icons.length], ['Paths', paths], ['Nodes', nodes], ['Duplicate centerlines', (j.audit && j.audit.coincident) || 0], ['Open gaps', (j.audit && j.audit.gaps) || 0], ['Notches', (j.audit && j.audit.notches) || 0], ['Time', (j.seconds || 0).toFixed(0) + 's']]
      .map(([k, v]) => `<div><span class="k">${k}</span><b>${v}</b></div>`).join('');
    $('#imgDiff').src = `/api/jobs/${S.job}/diff.png?v=${S.version}`;
    updateLinks(); ['dlSvg', 'dlZip', 'copy'].forEach(i => $('#' + i).classList.remove('disabled'));
    loadSvg();
  }

  // ---------------------------------------------------------------- vector layer + live styling
  async function loadSvg() {
    const id = S.job;
    try {
      const t = await (await api(`/api/jobs/${id}/result.svg?bg=none&v=${S.version}`)).text();
      if (id !== S.job) return;
      $('#vec').innerHTML = t;
      $$('#vec path').forEach(p => p.dataset.w = p.getAttribute('stroke-width'));
      applyStyle();
    } catch (e) {}
  }
  function applyStyle() {
    const sc = +$('#scale').value, col = S.view === 'overlay' ? '#ef4444' : $('#stroke').value;
    $('#scaleV').textContent = Math.round(sc * 100) + '%';
    const g = $('#vec g'); if (g) g.setAttribute('stroke', col);
    $$('#vec path').forEach(p => p.setAttribute('stroke-width', (+p.dataset.w * sc).toFixed(2)));
    const bg = $('#bg').value, c = $('#canvas');
    c.classList.toggle('nobg', bg === 'none'); c.classList.toggle('dark', bg === '#0b0b0c');
    if (bg === '#0b0b0c' && $('#stroke').value === '#111111') { $('#stroke').value = '#f4f4f5'; if (g) g.setAttribute('stroke', S.view === 'overlay' ? '#ef4444' : '#f4f4f5'); }
    if (bg !== '#0b0b0c' && $('#stroke').value === '#f4f4f5') { $('#stroke').value = '#111111'; if (g) g.setAttribute('stroke', S.view === 'overlay' ? '#ef4444' : '#111111'); }
    updateLinks();
  }
  ['stroke', 'scale', 'bg'].forEach(i => $('#' + i).addEventListener('input', applyStyle));
  function qs(extra = '') { return `stroke=${encodeURIComponent($('#stroke').value)}&scale=${$('#scale').value}&bg=${encodeURIComponent($('#bg').value)}${extra}`; }
  function updateLinks() {
    if (!S.job) return;
    $('#dlSvg').href = `/api/jobs/${S.job}/result.svg?${qs('&download=1')}`;
    $('#dlZip').href = `/api/jobs/${S.job}/download.zip?stroke=${encodeURIComponent($('#stroke').value)}&scale=${$('#scale').value}`;
  }
  $('#copy').addEventListener('click', async () => {
    try { const t = await (await api(`/api/jobs/${S.job}/result.svg?${qs()}`)).text(); await navigator.clipboard.writeText(t); toast('SVG copied to clipboard'); }
    catch (e) { toast('Copy failed', 1); }
  });

  // ---------------------------------------------------------------- views
  function setView(v) {
    S.view = v; $$('#view button').forEach(b => b.classList.toggle('on', b.dataset.v === v));
    const o = $('#imgOrig'), d = $('#imgDiff'), vec = $('#vec');
    o.style.display = (v === 'original' || v === 'overlay') ? 'block' : 'none'; o.style.opacity = v === 'overlay' ? .5 : 1; o.style.filter = v === 'overlay' ? 'grayscale(1)' : 'none';
    vec.style.display = (v === 'vector' || v === 'overlay') ? 'block' : 'none';
    d.style.display = v === 'diff' ? 'block' : 'none'; $('#legend').hidden = v !== 'diff';
    applyStyle();
  }
  $('#view').addEventListener('click', e => { const b = e.target.closest('button'); if (b) setView(b.dataset.v); });

  // ---------------------------------------------------------------- pan / zoom
  const stage = $('#stage'), canvas = $('#canvas');
  function sizeCanvas() { canvas.style.width = S.W + 'px'; canvas.style.height = S.H + 'px'; }
  function paint() { canvas.style.transform = `translate(${S.tf.x}px,${S.tf.y}px) scale(${S.tf.k})`; }
  function fit(box) {
    const r = stage.getBoundingClientRect(); if (!S.W) return;
    const b = box || [0, 0, S.W, S.H], bw = b[2] - b[0], bh = b[3] - b[1], pad = box ? 0.78 : 0.96;
    const k = Math.min(r.width / bw, r.height / bh) * pad;
    S.tf = { k, x: (r.width - bw * k) / 2 - b[0] * k, y: (r.height - bh * k) / 2 - b[1] * k }; paint();
  }
  function zoomAt(f, cx, cy) { const k = Math.min(Math.max(S.tf.k * f, .05), 40); const r = k / S.tf.k; S.tf.x = cx - (cx - S.tf.x) * r; S.tf.y = cy - (cy - S.tf.y) * r; S.tf.k = k; paint(); }
  stage.addEventListener('wheel', e => { e.preventDefault(); const r = stage.getBoundingClientRect(); zoomAt(Math.exp(-e.deltaY * (e.ctrlKey ? .01 : .0016)), e.clientX - r.left, e.clientY - r.top); }, { passive: false });
  let drag = null;
  stage.addEventListener('pointerdown', e => { if (e.target.closest('.zoom')) return; drag = { x: e.clientX, y: e.clientY, tx: S.tf.x, ty: S.tf.y }; stage.classList.add('drag'); stage.setPointerCapture(e.pointerId); });
  stage.addEventListener('pointermove', e => { if (!drag) return; S.tf.x = drag.tx + e.clientX - drag.x; S.tf.y = drag.ty + e.clientY - drag.y; paint(); });
  stage.addEventListener('pointerup', () => { drag = null; stage.classList.remove('drag'); });
  stage.addEventListener('dblclick', () => { clearFocus(); fit(); });
  $('#zin').onclick = () => { const r = stage.getBoundingClientRect(); zoomAt(1.35, r.width / 2, r.height / 2); };
  $('#zout').onclick = () => { const r = stage.getBoundingClientRect(); zoomAt(1 / 1.35, r.width / 2, r.height / 2); };
  $('#zfit').onclick = () => { clearFocus(); fit(); };
  window.addEventListener('resize', () => S.job && fit());

  function selectIcon(k) {
    const ic = S.icons[k]; if (!ic) return;
    S.sel = k; $$('.ic').forEach(x => x.classList.toggle('sel', +x.dataset.k === k));
    const f = $('#focus'); const b = ic.box; f.hidden = false; Object.assign(f.style, { left: b[0] + 'px', top: b[1] + 'px', width: (b[2] - b[0]) + 'px', height: (b[3] - b[1]) + 'px' });
    fit(b);
  }
  function clearFocus() { S.sel = null; $('#focus').hidden = true; $$('.ic').forEach(x => x.classList.remove('sel')); }
  hint();
})();
