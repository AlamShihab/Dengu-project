/* Project log page: renders docs/PROGRESS_LOG.md (small markdown subset) and the run history. */
(function () {
    'use strict';
    document.addEventListener('DOMContentLoaded', load);

    function inline(s) {
        return dfs.esc(s)
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1');
    }

    function render(md) {
        const out = [];
        let list = false, pre = false, para = [];
        const flush = () => { if (para.length) { out.push(`<p>${inline(para.join(' '))}</p>`); para = []; } };
        const closeList = () => { if (list) { out.push('</ul>'); list = false; } };
        for (const raw of md.split(/\r?\n/)) {
            const line = raw.replace(/\s+$/, '');
            if (line.startsWith('```')) { flush(); closeList(); out.push(pre ? '</pre>' : '<pre>'); pre = !pre; continue; }
            if (pre) { out.push(dfs.esc(line)); continue; }
            if (line.startsWith('<!--')) { flush(); closeList(); pre = false; continue; }
            const h = /^(#{1,3})\s+(.*)$/.exec(line);
            if (h) { flush(); closeList(); out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`); continue; }
            const li = /^\s*[-*]\s+(.*)$/.exec(line);
            if (li) { flush(); if (!list) { out.push('<ul>'); list = true; } out.push(`<li>${inline(li[1])}</li>`); continue; }
            if (/^---+$/.test(line)) { flush(); closeList(); out.push('<hr>'); continue; }
            if (!line.trim()) { flush(); closeList(); continue; }
            if (list && /^\s{2,}/.test(raw)) { out[out.length - 1] = out[out.length - 1].replace('</li>', ' ' + inline(line.trim()) + '</li>'); continue; }
            para.push(line.trim());
        }
        flush(); closeList();
        return out.join('\n');
    }

    async function load() {
        const res = await dfs.api('/api/project-log');
        if (res.status !== 'ok') { dfs.notice([res.message]); return; }
        dfs.$('log-md').innerHTML = render(res.markdown || '');
        dfs.setText('log-audit', res.audit || 'not run');
        const p = (res.pipeline_runs || [])[0];
        dfs.setText('log-last-run', p ? p.status : '--');
        dfs.setText('log-last-run-time', p ? `${p.run_id} · ${p.started || ''}` : '--');
        const w = (res.web_runs || [])[0];
        dfs.setText('log-last-web', w ? w.status : '--');
        dfs.setText('log-last-web-time', w ? `${w.mode_label} · ${w.started}` : 'none');
        dfs.$('runs-body').innerHTML = (res.pipeline_runs || []).map((r) => `<tr><td>${dfs.esc(r.run_id)}</td><td>${dfs.esc(r.status)}</td>
            <td>${dfs.esc(r.started || '')}</td><td class="muted-cell">${dfs.esc((r.stages || []).join(', '))}</td></tr>`).join('') || '<tr><td colspan="4">No runs yet.</td></tr>';
        dfs.$('web-body').innerHTML = (res.web_runs || []).map((r) => `<tr><td>${dfs.esc(r.run_id)}</td><td>${dfs.esc(r.mode_label)}</td>
            <td>${dfs.esc(r.status)}</td><td>${dfs.esc(r.started)}</td><td class="muted-cell">${dfs.esc(r.message || '')}</td></tr>`).join('') || '<tr><td colspan="5">No web-app runs yet.</td></tr>';
    }
})();
