with open('server/static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

s_insert = '''      const sFound = (j.audit && j.audit.structure_found) || 0;
      const sFixed = (j.audit && j.audit.structure_fixed) || 0;
      const sReview = (j.audit && j.audit.structure_review) || 0;
      if (sFound > 0 || sFixed > 0 || sReview > 0) {
        stats.push(['Structure Engine', `${sFixed}/${sFound} sites fixed / ${sReview} for review`]);
      }
'''

needle1 = "stats.push(['Join Engine', `${jTotal} joints / ${jRepaired} repaired / ${jReview} for review`]);\n      }"
assert needle1 in content, 'needle1 not in content'

content = content.replace(needle1, needle1 + '\n' + s_insert, 1)

overlay_code = '''    let count = 0;
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
    });'''

needle2_start = '    let count = 0;\n    job.icons.forEach(ic => {'
needle2_end = '    });\n\n    if (count > 0) {'

idx_start = content.find(needle2_start)
idx_end = content.find(needle2_end, idx_start)
assert idx_start != -1 and idx_end != -1, 'needle2 not found'

content = content[:idx_start] + overlay_code + content[idx_end + len('    });'):]

with open('server/static/app.js', 'w', encoding='utf-8') as f:
    f.write(content)
print('Successfully patched server/static/app.js!')
