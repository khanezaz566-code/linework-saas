with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\server\static\app.js', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. In onDone: store S.jobData = j and add joints stats
old_stats = '''      if (finFixed > 0 || finFound > 0) stats.push(['Finisher Engine', `${finFixed}/${finFound} sites fixed`]);'''

new_stats = '''      if (finFixed > 0 || finFound > 0) stats.push(['Finisher Engine', `${finFixed}/${finFound} sites fixed`]);
      const jTotal = (j.audit && j.audit.joints) || 0;
      const jRepaired = (j.audit && j.audit.joints_repaired) || 0;
      const jReview = (j.audit && j.audit.joints_review) || 0;
      if (jTotal > 0 || jRepaired > 0 || jReview > 0) {
        stats.push(['Join Engine', `${jTotal} joints / ${jRepaired} repaired / ${jReview} for review`]);
      }'''

text = text.replace(old_stats, new_stats)

# 2. In onDone beginning, store S.jobData = j;
old_ondone = '''  function onDone(j) {
    if (S.poll) { clearInterval(S.poll); S.poll = null; }'''

new_ondone = '''  function onDone(j) {
    S.jobData = j;
    if (S.poll) { clearInterval(S.poll); S.poll = null; }'''

text = text.replace(old_ondone, new_ondone)

# 3. In loadSvg call renderUnresolvedJointsOverlay
old_loadsvg = '''        vec.innerHTML = t;
        $$('#vec path').forEach(p => p.dataset.w = p.getAttribute('stroke-width'));
        applyStyle();'''

new_loadsvg = '''        vec.innerHTML = t;
        $$('#vec path').forEach(p => p.dataset.w = p.getAttribute('stroke-width'));
        applyStyle();
        if (S.jobData) renderUnresolvedJointsOverlay($('#vec svg'), S.jobData);'''

text = text.replace(old_loadsvg, new_loadsvg)

# 4. Add renderUnresolvedJointsOverlay function right before loadSvg
overlay_func = '''  function renderUnresolvedJointsOverlay(svgEl, job) {
    if (!svgEl || !job || !job.icons) return;
    const oldOverlay = svgEl.querySelector('#unresolvedJointsOverlay');
    if (oldOverlay) oldOverlay.remove();

    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    g.id = 'unresolvedJointsOverlay';
    g.setAttribute('class', 'unresolved-joints-layer');

    let count = 0;
    job.icons.forEach(ic => {
      const jn = ic.metrics && ic.metrics.joins;
      if (!jn || !jn.unresolved || !jn.unresolved.length) return;
      const offX = (ic.box && ic.box[0]) || 0;
      const offY = (ic.box && ic.box[1]) || 0;
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
    });

    if (count > 0) {
      svgEl.appendChild(g);
    }
  }

'''

text = text.replace('  // ---------------------------------------------------------------- vector layer + live styling\n  async function loadSvg() {',
                    overlay_func + '  // ---------------------------------------------------------------- vector layer + live styling\n  async function loadSvg() {')

with open(r'C:\Users\USER\.gemini\antigravity\scratch\linework\server\static\app.js', 'w', encoding='utf-8') as f:
    f.write(text)
print('Updated server/static/app.js successfully')
