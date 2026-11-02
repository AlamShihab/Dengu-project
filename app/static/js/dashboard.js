/* Dashboard: KPIs, leaderboard per level, MAE-by-day chart, district coverage, quality, figures, downloads. */
(function () {
    'use strict';
    let data = null;
    let level = 'district';

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('#lb-level button').forEach((b) => b.addEventListener('click', () => {
            level = b.dataset.level;
            document.querySelectorAll('#lb-level button').forEach((x) => x.classList.toggle('active', x === b));
            renderLeaderboard();
        }));
        document.addEventListener('dfs:theme', () => { if (data) { drawMae(); drawCoverage(); } });
        load();
        loadFigures();
        loadDownloads();
    });

    async function load() {
        data = await dfs.api('/api/dashboard-data');
        if (data.status !== 'ok') { dfs.notice([data.message]); return; }
        dfs.notice(data.messages);
        const u = data.units || {};
        dfs.setText('total-units', (u.divisions || 0) + (u.districts || 0) + 1);
        dfs.setText('unit-detail', `Bangladesh, ${u.divisions || '--'} divisions, ${u.districts || '--'} district units`);
        dfs.setText('avg-mae', dfs.fmt(data.avg_mae_district, 2));
        const p = data.data_period || {};
        dfs.setText('data-latest', p.division_last || '--');
        dfs.setText('data-detail', `Divisions & Bangladesh to ${p.division_last || '--'}; district table (PDF) to ${p.pdf_last || '--'}; from ${p.first || '--'}`);
        dfs.setText('num-models', `${data.deployed_models || 0}`);
        const a = data.audit || {};
        dfs.setText('audit-label', a.pipeline_status ? `Audit: ${a.pipeline_status} (${a.passed}/${a.total}), ML models: ${data.ml_models}` : 'Audit: not run yet');
        if (data.test_period) dfs.setText('test-period', `(forecast origins ${data.test_period.start_origin} to ${data.test_period.end_origin})`);
        const q = data.data_quality || {};
        dfs.setText('q-reports', q.reports ? `${q.parsed_ok} of ${q.reports}` : '--');
        dfs.setText('q-missing', q.missing_report_days != null ? `${q.missing_report_days} days` : '--');
        const ag = q.pdf_vs_dashboard || {};
        dfs.setText('q-agree', ag.overlap_rows ? `${ag.overlap_rows - ag.mismatch_rows} of ${ag.overlap_rows} equal` : '--');
        dfs.setText('q-status', ({ PASS: 'Pass', PASS_WITH_WARNINGS: 'Pass (with warnings)', FAIL: 'Fail' })[q.validation_status] || '--');
        renderLeaderboard();
        drawCoverage();
    }

    function renderLeaderboard() {
        const rows = (data && data.leaderboards && data.leaderboards[level]) || [];
        const body = dfs.$('leaderboard-body');
        if (!rows.length) { body.innerHTML = '<tr><td colspan="8">No results yet - run the pipeline.</td></tr>'; dfs.emptyChart('mae-chart', 'No results yet.'); return; }
        body.innerHTML = rows.map((r) => `<tr>
            <td>Day ${r.horizon}</td><td>${dfs.esc(r.baseline_name || '--')}</td><td class="num">${dfs.fmt(r.baseline_mae, 2)}</td>
            <td>${dfs.esc(r.ml_model || '--')}</td><td class="num">${dfs.fmt(r.ml_mae, 2)}</td>
            <td class="num">${r.improvement_percent == null ? '--' : dfs.pct(r.improvement_percent)}</td>
            <td>${r.deployed_model ? `<span class="badge ${r.deployed_kind === 'ml' ? 'success' : 'warning'}">${dfs.esc(r.deployed_model)}${r.deployed_kind === 'ml' ? '' : ' (baseline)'}</span>` : '<span class="badge pending">pending</span>'}</td>
            <td class="num">${r.coverage == null ? '--' : dfs.pct(100 * r.coverage, 0)}</td></tr>`).join('');
        drawMae();
    }

    function drawMae() {
        const rows = (data.leaderboards || {})[level] || [];
        if (!rows.length) return;
        const t = dfs.theme();
        const x = rows.map((r) => `Day ${r.horizon}`);
        const traces = [
            { x, y: rows.map((r) => r.baseline_mae), name: 'Best baseline', type: 'scatter', mode: 'lines+markers',
              line: { color: t.s2, width: 2 }, marker: { size: 8 }, hovertemplate: '%{y:.2f}<extra>baseline</extra>' },
        ];
        if (rows.some((r) => r.deployed_mae != null)) {
            traces.push({ x, y: rows.map((r) => r.deployed_mae), name: 'Deployed model', type: 'scatter', mode: 'lines+markers',
                          line: { color: t.s1, width: 2 }, marker: { size: 8 }, hovertemplate: '%{y:.2f}<extra>deployed</extra>' });
        }
        dfs.plot('mae-chart', traces, dfs.layout({ yaxis: { title: { text: 'MAE (admissions per day)' }, rangemode: 'tozero' } }));
    }

    function drawCoverage() {
        const cov = (data && data.coverage) || [];
        if (!cov.length) { dfs.emptyChart('coverage-chart', 'Coverage is shown after the preparation stage.'); return; }
        const t = dfs.theme();
        const x = cov.map((r) => r.name);
        const bar = (key, name, color) => ({ x, y: cov.map((r) => r[key]), name, type: 'bar',
            marker: { color, line: { color: t.bg, width: 1 } }, hovertemplate: `%{y:.1f}%<extra>${name}</extra>` });
        dfs.plot('coverage-chart', [bar('observed_pct', 'Reported', t.s1), bar('missing_pct', 'Missing', t.neutral)],
            dfs.layout({ barmode: 'stack', bargap: 0.25, margin: { l: 56, r: 20, t: 20, b: 130 },
                         xaxis: { tickangle: -60, tickfont: { size: 10 } }, yaxis: { title: { text: '% of days' }, range: [0, 100] } }));
    }

    let files = [];
    let showAll = false;
    async function loadDownloads() {
        const res = await dfs.api('/api/downloads');
        files = res.status === 'ok' ? res.files : [];
        showAll = !files.some((f) => f.key);
        dfs.$('downloads-toggle').addEventListener('click', () => { showAll = !showAll; renderDownloads(); });
        renderDownloads();
    }
    function renderDownloads() {
        const tbody = dfs.$('downloads-body');
        if (!files.length) { tbody.innerHTML = '<tr><td colspan="5">No result files yet.</td></tr>'; dfs.show('downloads-toggle', false); return; }
        const rows = showAll ? files : files.filter((f) => f.key);
        tbody.innerHTML = rows.map((f) => `<tr><td>${dfs.esc(f.name)}</td><td class="muted-cell">${dfs.esc(f.description || '')}</td>
            <td class="num">${dfs.fmt(f.size_kb, 1)}</td><td>${dfs.esc(f.modified)}</td>
            <td><a class="btn btn-secondary btn-sm" href="/api/download/${encodeURIComponent(f.name)}">Download</a></td></tr>`).join('');
        const others = files.length - files.filter((f) => f.key).length;
        dfs.show('downloads-toggle', others > 0 && files.some((f) => f.key));
        dfs.$('downloads-toggle').textContent = showAll ? 'Show only the key reports' : `Show all ${files.length} result files (${others} more)`;
    }
    async function loadFigures() {
        const res = await dfs.api('/api/figures');
        if (res.status !== 'ok' || !res.figures.length) return;
        dfs.$('figure-grid').innerHTML = res.figures.map((f) => `<figure class="figure-card">
            <a href="${dfs.esc(f.url)}" target="_blank" rel="noopener"><img src="${dfs.esc(f.url)}" alt="${dfs.esc(f.title)}" loading="lazy"></a>
            <figcaption>${dfs.esc(f.title)}</figcaption></figure>`).join('');
        dfs.show('figures-section', true);
    }
})();
