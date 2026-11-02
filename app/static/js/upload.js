/* Upload page: automatic DGHS update, file check (PDF / CSV / XLSX), apply + run, progress, versions. */
(function () {
    'use strict';
    let file = null, checked = null, modes = [], poll = null;

    document.addEventListener('DOMContentLoaded', () => {
        const area = dfs.$('drag-drop-area');
        const input = dfs.$('file-input');
        area.addEventListener('click', () => input.click());
        area.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') input.click(); });
        area.addEventListener('dragover', (e) => { e.preventDefault(); area.classList.add('dragover'); });
        area.addEventListener('dragleave', () => area.classList.remove('dragover'));
        area.addEventListener('drop', (e) => { e.preventDefault(); area.classList.remove('dragover'); if (e.dataTransfer.files[0]) pick(e.dataTransfer.files[0]); });
        input.addEventListener('change', () => { if (input.files[0]) pick(input.files[0]); });
        dfs.$('validate-btn').addEventListener('click', check);
        dfs.$('apply-btn').addEventListener('click', apply);
        dfs.$('update-btn').addEventListener('click', () => startRun('update'));
        dfs.$('run-cancel-btn').addEventListener('click', async () => { await dfs.api('/api/pipeline-run/cancel', {}); refreshRun(); });
        document.querySelectorAll('.rerun').forEach((b) => b.addEventListener('click', () => startRun(b.dataset.mode)));
        loadStatus();
    });

    function pick(f) {
        file = f;
        dfs.setText('file-name', f.name);
        dfs.setText('file-size', `${(f.size / 1024).toFixed(1)} KB`);
        dfs.show('file-info', true);
        dfs.$('validate-btn').disabled = false;
        dfs.show('validation-section', false);
    }

    async function check() {
        if (!file) return;
        const btn = dfs.$('validate-btn');
        btn.disabled = true; btn.textContent = 'Checking...';
        const fd = new FormData();
        fd.append('file', file);
        const res = await dfs.api('/api/upload', fd);
        btn.disabled = false; btn.textContent = 'Check File';
        checked = res;
        dfs.show('validation-section', true);
        const ok = res.status === 'success';
        dfs.show('success-card', ok);
        dfs.show('error-card', !ok);
        dfs.show('merge-card', false);
        if (!ok) {
            dfs.$('error-list').innerHTML = (res.errors && res.errors.length ? res.errors : [res.message]).map((e) => `<li>${dfs.esc(e)}</li>`).join('');
            return;
        }
        dfs.setText('success-message', res.message);
        const rows = res.kind === 'pdf'
            ? [['Report date', res.report_date], ['Date printed in the PDF', res.printed_date || '--'], ['District units read', res.units],
               ['National admissions (last 24 h)', dfs.int(res.national_24h)], ['Units add up to the national total', res.national_matches ? 'yes' : 'no'],
               ['Already in the data', res.already_present ? 'yes - nothing will be added' : 'no - new']]
            : [['Rows', res.rows], ['New rows', res.merge.new_rows], ['District rows', res.merge.district_rows],
               ['Division / national / Dhaka-metro rows', res.merge.other_rows], ['Already covered by DGHS PDFs', res.merge.already_in_pdf_data],
               ['Dates', `${res.merge.first_date} to ${res.merge.last_date}`]];
        dfs.$('summary-table').innerHTML = rows.map(([k, v]) => `<tr><td><strong>${dfs.esc(k)}</strong></td><td>${dfs.esc(v)}</td></tr>`).join('');
        dfs.show('warning-block', (res.warnings || []).length > 0);
        dfs.$('warning-list').innerHTML = (res.warnings || []).map((w) => `<li>${dfs.esc(w)}</li>`).join('');
        const prev = res.preview || [];
        dfs.$('preview-head').innerHTML = res.kind === 'pdf'
            ? '<tr><th>District unit</th><th class="num">Admissions (24 h)</th><th class="num">Since 1 January</th></tr>'
            : '<tr><th>Date</th><th>Place</th><th class="num">Admissions (24 h)</th></tr>';
        dfs.$('preview-body').innerHTML = prev.map((r) => res.kind === 'pdf'
            ? `<tr><td>${dfs.esc(r.name)}</td><td class="num">${dfs.int(r.admitted_24h)}</td><td class="num">${dfs.int(r.cum_admitted)}</td></tr>`
            : `<tr><td>${dfs.esc(r.report_date)}</td><td>${dfs.esc(r.name)}</td><td class="num">${dfs.int(r.admitted_24h)}</td></tr>`).join('');
        const canAdd = res.kind === 'pdf' ? !res.already_present : res.merge.new_rows > 0;
        dfs.show('merge-card', canAdd);
        dfs.setText('merge-summary', res.kind === 'pdf'
            ? `Adds the DGHS report for ${res.report_date} (all district units).`
            : `Adds ${res.merge.new_rows} new rows.`);
        renderModes();
    }

    function renderModes() {
        const opts = modes.filter((m) => m.key !== 'update');
        dfs.$('mode-choices').innerHTML = opts.map((m, i) => `<label style="display:block; margin-bottom:8px;">
            <input type="radio" name="mode" value="${m.key}" ${i === 0 ? 'checked' : ''}> <strong>${dfs.esc(m.label)}</strong>
            <span class="muted"> - ${dfs.esc(m.description)}</span></label>`).join('');
    }

    async function apply() {
        if (!checked || !checked.saved_as) return;
        const mode = (document.querySelector('input[name="mode"]:checked') || {}).value || 'data';
        const btn = dfs.$('apply-btn');
        btn.disabled = true;
        const res = await dfs.api('/api/apply-data', { file: checked.saved_as, mode });
        btn.disabled = false;
        if (res.status !== 'success') { dfs.notice([res.message].concat(res.errors || [])); return; }
        dfs.notice([]);
        dfs.show('merge-card', false);
        watchRun();
        loadStatus();
    }

    async function startRun(mode) {
        const res = await dfs.api('/api/pipeline-run/start', { mode });
        if (res.status !== 'success') { dfs.notice([res.message]); return; }
        dfs.notice([]);
        watchRun();
    }

    function watchRun() {
        dfs.show('run-section', true);
        refreshRun();
        if (poll) clearInterval(poll);
        poll = setInterval(refreshRun, 2000);
    }

    async function refreshRun() {
        const res = await dfs.api('/api/pipeline-run');
        const run = res.run;
        if (!run) return;
        dfs.show('run-section', true);
        dfs.setText('run-title', `${run.mode_label} · ${run.status}${run.note ? ' · ' + run.note : ''}`);
        dfs.setText('run-message', run.message || '');
        dfs.$('run-stage-body').innerHTML = run.stages.map((s) => `<tr><td>${dfs.esc(s.title)}</td>
            <td><span class="badge ${s.status === 'completed' ? 'success' : s.status === 'failed' ? 'error' : s.status === 'running' ? 'warning' : 'pending'}">${dfs.esc(s.status)}</span></td>
            <td class="num">${s.seconds == null ? '' : dfs.fmt(s.seconds, 1)}</td></tr>`).join('');
        const active = run.stages.find((s) => s.status === 'running') || [...run.stages].reverse().find((s) => (s.log || []).length);
        dfs.setText('run-log', active && active.log && active.log.length ? active.log.join('\n') : '--');
        dfs.show('run-cancel-btn', run.status === 'running');
        if (run.status !== 'running' && poll) { clearInterval(poll); poll = null; loadStatus(); }
    }

    async function loadStatus() {
        const res = await dfs.api('/api/data-status');
        if (res.status !== 'success') { dfs.notice([res.message]); return; }
        modes = res.modes || [];
        const d = res.data;
        dfs.setText('data-pdfs', d.pdfs.pdfs ? `${d.pdfs.pdfs} reports, ${d.pdfs.first} to ${d.pdfs.last} (${d.pdfs.missing} dates not published)` : 'none yet - use "Update from DGHS now"');
        dfs.setText('data-dash', d.dashboard.last ? `${d.dashboard.dates} days stored, up to ${d.dashboard.last}` : 'none yet');
        dfs.setText('data-uploads', `${d.uploaded_pdfs} PDFs · ${d.manual_rows} table rows`);
        const vs = d.versions || [];
        dfs.$('versions-body').innerHTML = vs.length ? vs.map((v) => `<tr><td>${dfs.esc(v.id)}</td><td>${dfs.esc(v.created)}</td>
            <td>${dfs.esc(v.note)}</td><td><button class="btn btn-outline btn-sm" data-restore="${dfs.esc(v.id)}">Restore</button></td></tr>`).join('')
            : '<tr><td colspan="4">No uploads yet - the data comes from the DGHS downloads.</td></tr>';
        document.querySelectorAll('[data-restore]').forEach((b) => b.addEventListener('click', async () => {
            if (!confirm(`Restore data version ${b.dataset.restore}? Data added after it is moved aside (not deleted).`)) return;
            const r = await dfs.api('/api/data-versions/restore', { id: b.dataset.restore, rerun: true });
            dfs.notice([r.message]);
            watchRun();
        }));
        if (res.run && res.run.status === 'running') watchRun();
    }
})();
