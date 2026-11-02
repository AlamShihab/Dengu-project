/* Model performance page. */
(function () {
    'use strict';
    let last = null;

    document.addEventListener('DOMContentLoaded', async () => {
        const hs = dfs.$('horizon-select');
        [1, 2, 3, 4, 5, 6, 7].forEach((h) => hs.add(new Option(`Day ${h}`, h)));
        dfs.$('level-select').addEventListener('change', async () => { await loadUnits(); load(); });
        dfs.$('unit-select').addEventListener('change', load);
        hs.addEventListener('change', load);
        document.addEventListener('dfs:theme', () => { if (last) draw(last); });
        const q = new URLSearchParams(window.location.search);
        if (q.get('level')) dfs.$('level-select').value = q.get('level');
        await loadUnits();
        if (q.get('unit')) dfs.$('unit-select').value = q.get('unit');
        if (q.get('horizon')) hs.value = q.get('horizon');
        load();
    });

    async function loadUnits() {
        const level = dfs.$('level-select').value;
        const res = await dfs.api(`/api/units?level=${level}`);
        const sel = dfs.$('unit-select');
        const units = res.status === 'ok' ? res.units : [];
        dfs.fillSelect(sel, units.map((u) => u.unit_code), level === 'national' ? '' : 'All places of this level',
            (c) => units.find((u) => u.unit_code === c).name);
        if (level === 'national') sel.value = 'BD';
    }

    async function load() {
        const body = { level: dfs.$('level-select').value, unit: dfs.$('unit-select').value, horizon: Number(dfs.$('horizon-select').value) };
        const res = await dfs.api('/api/model-metrics', body);
        if (res.status !== 'ok') { dfs.notice([res.message]); return; }
        dfs.notice([]);
        last = res;
        const tp = res.test_period || {};
        dfs.setText('test-note', `Test period: forecast origins ${tp.start_origin || '--'} to ${tp.end_origin || '--'} (never used for training or model choice). MAE = mean absolute error in admissions per place and day.`);
        const unit = !!res.unit && res.level !== 'national';
        dfs.$('metrics-head').innerHTML = `<tr><th>Day</th><th>Deployed model</th>${unit ? '<th class="num">Place MAE</th><th class="num">Place baseline MAE</th><th class="num">Place RMSE</th><th class="num">Place 80% coverage</th><th class="num">Days</th>' : ''}
            <th class="num">All-places MAE</th><th class="num">Baseline MAE</th><th class="num">RMSE</th><th class="num">Bias</th><th class="num">R²</th><th class="num">80% coverage</th></tr>`;
        dfs.$('metrics-body').innerHTML = res.by_horizon.map((r) => `<tr><td>Day ${r.horizon}</td><td>${dfs.esc(r.model || '--')}</td>
            ${unit ? `<td class="num">${dfs.fmt(r.unit_MAE, 2)}</td><td class="num">${dfs.fmt(r.unit_baseline_MAE, 2)}</td><td class="num">${dfs.fmt(r.unit_RMSE, 2)}</td><td class="num">${r.unit_coverage == null ? '--' : dfs.pct(100 * r.unit_coverage, 0)}</td><td class="num">${dfs.int(r.unit_n)}</td>` : ''}
            <td class="num">${dfs.fmt(r.all_MAE, 2)}</td><td class="num">${dfs.fmt(r.baseline_MAE, 2)} <span class="muted">${dfs.esc(r.baseline || '')}</span></td>
            <td class="num">${dfs.fmt(r.all_RMSE, 2)}</td><td class="num">${dfs.fmt(r.all_Bias, 2)}</td><td class="num">${dfs.fmt(r.all_R2, 2)}</td>
            <td class="num">${r.coverage == null ? '--' : dfs.pct(100 * r.coverage, 0)}</td></tr>`).join('');
        const td = res.topdown || [];
        dfs.show('topdown-section', td.length > 0);
        dfs.$('topdown-body').innerHTML = td.map((r) => `<tr><td class="num">${r.staleness_days}</td><td class="num">${dfs.fmt(r.topdown_MAE, 2)}</td>
            <td class="num">${dfs.fmt(r.direct_MAE, 2)}</td><td class="num">${dfs.int(r.rows)}</td></tr>`).join('');
        const mi = res.model_info || {};
        const cand = mi.candidate || {};
        const iv = mi.intervals || {};
        const info = [
            ['Deployed', `${mi.deployed || '--'} (${mi.kind || '--'})`],
            ['Best ML candidate (CV)', cand.model ? `${cand.model} · ${cand.profile} · tuned CV MAE ${dfs.fmt(cand.tuned_cv_MAE, 3)}` : '--'],
            ['Tuned parameters', cand.params && Object.keys(cand.params).length ? JSON.stringify(cand.params) : 'defaults'],
            ['Best baseline (CV)', mi.best_baseline || '--'],
            ['Target', mi.target_mode === 'log_ratio' ? 'log ratio of admissions to the last 7-day mean' : (mi.target_mode || '--')],
            ['Features', mi.n_features || '--'],
            ['Trained on', mi.trained_on ? `${mi.trained_on.production} (accuracy from ${mi.trained_on.evaluation})` : '--'],
            ['80% range', iv.overall ? `log1p residual quantiles ${dfs.fmt(iv.overall[0], 2)} / ${dfs.fmt(iv.overall[1], 2)}, by forecast size` : '--'],
        ];
        dfs.$('model-info').innerHTML = info.map(([k, v]) => `<tr><td>${dfs.esc(k)}</td><td>${dfs.esc(v)}</td></tr>`).join('');
        draw(res);
    }

    function draw(res) {
        const t = dfs.theme();
        const x = res.by_horizon.map((r) => `Day ${r.horizon}`);
        const unit = !!res.unit && res.level !== 'national';
        const traces = [
            { x, y: res.by_horizon.map((r) => r.baseline_MAE), name: 'Best baseline (all places)', type: 'scatter', mode: 'lines+markers', line: { color: t.s2, width: 2 }, marker: { size: 8 } },
            { x, y: res.by_horizon.map((r) => r.all_MAE), name: 'Deployed (all places)', type: 'scatter', mode: 'lines+markers', line: { color: t.s1, width: 2 }, marker: { size: 8 } },
        ];
        if (unit) traces.push({ x, y: res.by_horizon.map((r) => r.unit_MAE), name: res.unit_name, type: 'scatter', mode: 'lines+markers', line: { color: t.s3, width: 2 }, marker: { size: 8 } });
        dfs.setText('mae-title', unit ? `MAE by forecast day - ${res.unit_name} vs all places` : 'MAE by forecast day');
        dfs.plot('mae-chart', traces, dfs.layout({ yaxis: { title: { text: 'MAE (admissions per day)' }, rangemode: 'tozero' } }));

        const s = res.series || [];
        dfs.setText('series-title', `Actual vs Day ${res.horizon} forecast on the test period - ${res.unit_name || (res.level === 'national' ? 'Bangladesh' : 'sum of all ' + res.level + 's')}`);
        if (s.length) {
            dfs.plot('series-chart', [
                { x: s.map((r) => r.date), y: s.map((r) => r.actual), name: 'Actual', type: 'scatter', mode: 'lines', line: { color: t.s1, width: 2 } },
                { x: s.map((r) => r.date), y: s.map((r) => r.predicted), name: `Day ${res.horizon} forecast`, type: 'scatter', mode: 'lines', line: { color: t.s2, width: 2 } },
            ], dfs.layout({ yaxis: { title: { text: 'admissions per day' }, rangemode: 'tozero' }, xaxis: { type: 'date' } }));
        } else dfs.emptyChart('series-chart', 'No test predictions yet.');

        const imp = [...(res.importance || [])].reverse();
        if (imp.length) {
            dfs.plot('importance-chart', [{ type: 'bar', orientation: 'h', x: imp.map((r) => r.importance), y: imp.map((r) => r.label),
                marker: { color: t.s1 }, error_x: { type: 'data', array: imp.map((r) => r.std), color: t.text2, thickness: 1 },
                hovertemplate: '%{x:.3f}<extra>%{y}</extra>' }],
                dfs.layout({ margin: { l: 280, r: 20, t: 10, b: 50 }, hovermode: 'closest', showlegend: false,
                             xaxis: { title: { text: 'increase in MAE when shuffled' } } }));
        } else dfs.emptyChart('importance-chart', 'Feature importance is available when an ML model is deployed for this level and day.');

        const r = res.residuals || [];
        if (r.length) {
            dfs.plot('residual-chart', [{ type: 'histogram', x: r, nbinsx: 60, marker: { color: t.s1, line: { color: t.bg, width: 1 } },
                hovertemplate: '%{x}: %{y}<extra></extra>' }],
                dfs.layout({ hovermode: 'closest', showlegend: false, xaxis: { title: { text: 'forecast − actual (admissions)' } },
                             yaxis: { title: { text: 'count' } } }));
        } else dfs.emptyChart('residual-chart', 'No test predictions yet.');
    }
})();
