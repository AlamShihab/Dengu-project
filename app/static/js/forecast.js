/* Forecast page: level + Division -> District -> Upazila selection; 7-day outlook (default), single day,
   all places (table + map); history chart; downloads. Deep links:
   /forecast?unit=BD3029&outlook=1   /forecast?unit=BD3029&horizon=3   /forecast?level=district&all=1 */
(function () {
    'use strict';
    let horizons = [1, 2, 3, 4, 5, 6, 7];
    let level = 'district';
    let locations = null;
    let last = null, lastOutlook = null, lastAll = null, lastMap = null;
    const SECTIONS = ['results-section', 'outlook-section', 'all-section', 'error-section'];
    const LEVEL_HELP = {
        national: 'All of Bangladesh (sum of every division).',
        division: 'The 8 divisions. Dhaka division includes the Dhaka city hospitals.',
        district: 'Districts are the main forecast level. Dhaka city hospitals are forecast as their own unit (Dhaka Metropolitan).',
        upazila: 'DGHS publishes no upazila-level dengue data. Choosing an upazila shows the forecast of its district, clearly labelled.',
    };

    document.addEventListener('DOMContentLoaded', () => {
        setupSlider();
        document.querySelectorAll('#level-tabs button').forEach((b) =>
            b.addEventListener('click', () => setLevel(b.dataset.level)));
        dfs.$('division-select').addEventListener('change', fillDistricts);
        dfs.$('district-select').addEventListener('change', fillUpazilas);
        dfs.$('horizon-slider').addEventListener('input', updateHorizonLabel);
        dfs.$('outlook-btn').addEventListener('click', showOutlook);
        dfs.$('generate-btn').addEventListener('click', generateForecast);
        dfs.$('all-btn').addEventListener('click', () => forecastAll(null));
        dfs.$('download-json-btn').addEventListener('click', () => downloadSingle('json'));
        dfs.$('download-csv-btn').addEventListener('click', () => downloadSingle('csv'));
        dfs.$('outlook-json-btn').addEventListener('click', () => downloadOutlook('json'));
        dfs.$('outlook-csv-btn').addEventListener('click', () => downloadOutlook('csv'));
        dfs.$('all-csv-btn').addEventListener('click', downloadAll);
        document.addEventListener('dfs:theme', () => {
            if (last) drawChart('forecast-chart', last, [last.forecast]);
            if (lastOutlook) drawChart('outlook-chart', lastOutlook, lastOutlook.forecasts);
            if (lastMap) drawMap(lastMap);
        });
        loadLocations();
    });

    async function loadLocations() {
        const data = await dfs.api('/api/locations');
        if (data.status !== 'ok') {
            dfs.notice([data.message || 'Places could not be loaded.']);
            ['outlook-btn', 'generate-btn', 'all-btn'].forEach((id) => { dfs.$(id).disabled = true; });
            return;
        }
        locations = data;
        if (data.horizons && data.horizons.length) horizons = data.horizons;
        dfs.fillSelect(dfs.$('division-select'), data.divisions.map((d) => d.code), '-- Select a division --',
            (c) => data.divisions.find((d) => d.code === c).name);
        const q = new URLSearchParams(window.location.search);
        const unit = (q.get('unit') || '').trim();
        const h = Number(q.get('horizon'));
        if (q.get('level')) setLevel(q.get('level'));
        else setLevel('district');
        if (unit) selectUnit(unit);
        else {                                          // a sensible default: Dhaka division / Dhaka Metropolitan
            dfs.$('division-select').value = 'BD30';
            fillDistricts();
            dfs.$('district-select').value = 'DHAKA_METRO';
            fillUpazilas();
        }
        if (horizons.includes(h)) { dfs.$('horizon-slider').value = h; updateHorizonLabel(); }
        if (q.get('all')) forecastAll(horizons.includes(h) ? h : null);
        else if (unit && q.get('horizon') && !q.get('outlook')) generateForecast();
        else if (unit) showOutlook();
    }

    function selectUnit(code) {
        if (code === 'BD') return setLevel('national');
        for (const dv of locations.divisions) {
            if (dv.code === code) { setLevel('division'); dfs.$('division-select').value = code; return; }
            for (const ds of dv.districts) {
                const up = ds.upazilas.find((u) => u.code === code);
                if (ds.code === code || up) {
                    setLevel(up ? 'upazila' : 'district');
                    dfs.$('division-select').value = dv.code;
                    fillDistricts();
                    dfs.$('district-select').value = ds.code;
                    fillUpazilas();
                    if (up) dfs.$('upazila-select').value = code;
                    return;
                }
            }
        }
    }

    function setLevel(lv) {
        level = ['national', 'division', 'district', 'upazila'].includes(lv) ? lv : 'district';
        document.querySelectorAll('#level-tabs button').forEach((b) => b.classList.toggle('active', b.dataset.level === level));
        dfs.show('division-group', level !== 'national');
        dfs.show('district-group', level === 'district' || level === 'upazila');
        dfs.show('upazila-group', level === 'upazila');
        dfs.setText('level-help', LEVEL_HELP[level]);
        const allBtn = dfs.$('all-btn');
        allBtn.style.display = (level === 'district' || level === 'division') ? '' : 'none';
        allBtn.textContent = level === 'division' ? 'All divisions: 7-day table' : 'All districts: 7-day table + map';
    }

    function fillDistricts() {
        const dv = locations.divisions.find((d) => d.code === dfs.$('division-select').value);
        const sel = dfs.$('district-select');
        if (!dv) { dfs.fillSelect(sel, [], '-- Choose a division first --'); fillUpazilas(); return; }
        dfs.fillSelect(sel, dv.districts.map((d) => d.code), '-- Select a district --',
            (c) => dv.districts.find((d) => d.code === c).name);
        fillUpazilas();
    }

    function currentDistrict() {
        const dv = locations && locations.divisions.find((d) => d.code === dfs.$('division-select').value);
        return dv ? dv.districts.find((d) => d.code === dfs.$('district-select').value) : null;
    }

    function fillUpazilas() {
        const ds = currentDistrict();
        const sel = dfs.$('upazila-select');
        if (!ds) { dfs.fillSelect(sel, [], '-- Choose a district first --'); return; }
        dfs.fillSelect(sel, ds.upazilas.map((u) => u.code), ds.upazilas.length ? '-- Select an upazila --' : '-- no upazilas listed --',
            (c) => ds.upazilas.find((u) => u.code === c).name);
    }

    function selectedUnit() {
        if (level === 'national') return 'BD';
        if (level === 'division') return dfs.$('division-select').value;
        if (level === 'district') return dfs.$('district-select').value;
        return dfs.$('upazila-select').value;
    }

    function setupSlider() {
        const s = dfs.$('horizon-slider');
        s.min = 1; s.max = 7; s.value = 1;
        dfs.$('slider-ticks').innerHTML = horizons.map((h) => `<span>Day ${h}</span>`).join('');
        updateHorizonLabel();
    }
    const currentHorizon = () => Number(dfs.$('horizon-slider').value);
    function updateHorizonLabel() { dfs.setText('horizon-value', `Day ${currentHorizon()}`); }

    function showOnly(id) { SECTIONS.forEach((s) => dfs.show(s, s === id)); }
    function showError(msg) { dfs.setText('error-message', msg); showOnly('error-section'); }
    function busy(btn, text) {
        const old = btn.textContent;
        btn.disabled = true; btn.textContent = text;
        return () => { btn.disabled = false; btn.textContent = old; };
    }
    const needUnit = () => {
        const u = selectedUnit();
        if (!u) showError(level === 'upazila' ? 'Please select an upazila.' : level === 'division' ? 'Please select a division.' : 'Please select a district.');
        return u;
    };
    const placeName = (d) => d.requested_name ? `${d.requested_name} (upazila) → ${d.unit_name}` : d.unit_name;
    const modelLabel = (f) => f.method === 'top_down' ? f.model : (f.model_kind === 'baseline' ? `${f.model} (baseline)` : f.model);

    function warnings(id, list) {
        dfs.$(id).innerHTML = (list || []).map((w) => `<div class="warning-item">⚠️ ${dfs.esc(w)}</div>`).join('');
    }

    async function showOutlook() {
        const unit = needUnit();
        if (!unit) return;
        const done = busy(dfs.$('outlook-btn'), 'Forecasting...');
        const data = await dfs.api('/api/outlook', { unit });
        done();
        if (data.status !== 'success') return showError(data.message || 'The forecast could not be made.');
        lastOutlook = data;
        dfs.setText('outlook-place', placeName(data));
        dfs.$('outlook-method').innerHTML = dfs.methodBadge(data.method);
        dfs.setText('outlook-origin', dfs.niceDate(data.origin_date) + ` (${data.data_age_days} day${data.data_age_days === 1 ? '' : 's'} ago)`);
        dfs.setText('outlook-total', dfs.int(data.total_7_days));
        warnings('outlook-warnings', data.warnings);
        dfs.$('day-cards').innerHTML = data.forecasts.map((f) => `
            <div class="day-card">
                <div class="day-label">${f.day_label}</div>
                <div class="day-date">${dfs.niceDate(f.target_date)}</div>
                <div class="day-value">${dfs.int(f.predicted)}</div>
                <div class="day-range">80%: ${dfs.range(f.lower_80, f.upper_80)}</div>
            </div>`).join('');
        dfs.$('outlook-body').innerHTML = data.forecasts.map((f) => `
            <tr><td>${f.day_label}</td><td>${dfs.esc(f.target_date)}</td><td class="num">${dfs.int(f.predicted)}</td>
                <td class="num">${dfs.range(f.lower_80, f.upper_80)}</td><td>${dfs.esc(modelLabel(f))}</td>
                <td class="num">${dfs.fmt(f.test_MAE, 1)}</td><td class="num">${f.method === 'top_down' ? '<span class="muted" title="direct district model with fresh data">direct: ' + dfs.fmt(f.direct_MAE, 1) + '</span>' : dfs.fmt(f.baseline_MAE, 1)}</td></tr>`).join('');
        showOnly('outlook-section');
        drawChart('outlook-chart', data, data.forecasts);
    }

    async function generateForecast() {
        const unit = needUnit();
        if (!unit) return;
        const done = busy(dfs.$('generate-btn'), 'Forecasting...');
        const data = await dfs.api('/api/forecast', { unit, horizon: currentHorizon() });
        done();
        if (data.status !== 'success') return showError(data.message || 'The forecast could not be made.');
        last = data;
        const f = data.forecast;
        dfs.setText('result-place', placeName(data));
        dfs.setText('result-date', dfs.niceDate(f.target_date));
        dfs.setText('result-horizon', f.day_label);
        dfs.setText('result-model', modelLabel(f));
        dfs.setText('prediction-value', dfs.int(f.predicted));
        dfs.setText('confidence-range', dfs.range(f.lower_80, f.upper_80));
        dfs.setText('origin-date', data.origin_date);
        dfs.setText('result-method', f.method === 'top_down' ? 'top-down from the division forecast' : 'direct');
        dfs.setText('result-mae', dfs.fmt(f.test_MAE, 2));
        dfs.setText('result-baseline', f.baseline_MAE == null ? '--' : `${dfs.fmt(f.baseline_MAE, 2)}${f.baseline ? ' (' + f.baseline + ')' : ''}`);
        dfs.setText('result-improvement', f.test_MAE != null && f.baseline_MAE ? dfs.pct(100 * (f.baseline_MAE - f.test_MAE) / f.baseline_MAE) : '--');
        warnings('warnings', data.warnings);
        showOnly('results-section');
        drawChart('forecast-chart', data, [f]);
    }

    /* history (observed) + forecast with 80% band; one y-axis; legend because there are 2+ series */
    function drawChart(id, data, fcs) {
        const t = dfs.theme();
        const hist = data.history || [];
        const xs = hist.map((r) => r.date), ys = hist.map((r) => r.admissions);
        const fx = fcs.map((f) => f.target_date);
        const traces = [
            { x: xs, y: ys, type: 'scatter', mode: 'lines', name: 'Reported admissions', line: { color: t.s1, width: 2 },
              connectgaps: false, hovertemplate: '%{y:,.0f}<extra>reported</extra>' },
        ];
        if (fcs.some((f) => f.lower_80 != null)) {
            traces.push({ x: fx.concat([...fx].reverse()), y: fcs.map((f) => f.upper_80).concat(fcs.map((f) => f.lower_80).reverse()),
                          type: 'scatter', mode: 'lines', fill: 'toself', fillcolor: dfs.alpha(t.s2, 0.18), line: { width: 0 },
                          name: '80% range', hoverinfo: 'skip' });
        }
        traces.push({ x: fx, y: fcs.map((f) => f.predicted), type: 'scatter', mode: 'lines+markers', name: 'Forecast',
                      line: { color: t.s2, width: 2 }, marker: { size: 8, color: t.s2, line: { color: t.bg, width: 2 } },
                      customdata: fcs.map((f) => [f.day_label, f.lower_80, f.upper_80]),
                      hovertemplate: '%{customdata[0]}: %{y:,.0f} (80%: %{customdata[1]:,.0f}–%{customdata[2]:,.0f})<extra>forecast</extra>' });
        dfs.plot(id, traces, dfs.layout({ yaxis: { title: { text: 'admissions per day' }, rangemode: 'tozero' },
                                          xaxis: { type: 'date' } }));
    }

    async function forecastAll(horizon) {
        const lv = level === 'division' ? 'division' : 'district';
        const done = busy(dfs.$('all-btn'), `Forecasting every ${lv}...`);
        const data = await dfs.api('/api/forecast-all', horizon ? { level: lv, horizon } : { level: lv });
        if (data.status !== 'success') { done(); return showError(data.message || 'The forecasts could not be made.'); }
        lastAll = data;
        const days = data.units.length ? data.units[0].forecasts.map((f) => f.day_label) : [];
        dfs.setText('all-title', lv === 'division' ? 'All Divisions · 7-day forecast' : 'All Districts · 7-day forecast');
        const first = data.units.find((u) => u.forecasts.length);
        dfs.setText('all-note', first ? `Issued ${data.issue_date}. Each cell is the forecast number of admissions for that day `
            + `(hover for the 80% range). Method: direct = the place's own data; top-down = division forecast × district share `
            + `(district reports stopped after ${first.district_last_data || first.origin_date}).` : 'No forecasts.');
        dfs.$('all-head').innerHTML = `<tr><th>${lv === 'division' ? 'Division' : 'District'}</th><th>Data to</th><th>Method</th>`
            + days.map((d) => `<th class="num">${d}</th>`).join('') + '<th class="num">7-day total</th></tr>'
            + (first ? `<tr><th></th><th></th><th></th>${first.forecasts.map((f) => `<th class="num muted-cell">${dfs.niceDate(f.target_date)}</th>`).join('')}<th></th></tr>` : '');
        const rows = [...data.units].sort((a, b) => (b.total_7_days || 0) - (a.total_7_days || 0));
        dfs.$('all-body').innerHTML = rows.map((u) => `<tr>
            <td><a href="/forecast?unit=${encodeURIComponent(u.unit_code)}&outlook=1">${dfs.esc(u.unit_name)}</a></td>
            <td class="muted-cell">${dfs.esc(u.district_last_data || u.origin_date)}</td><td>${dfs.methodBadge(u.method)}</td>
            ${u.forecasts.map((f) => `<td class="num" title="80%: ${dfs.range(f.lower_80, f.upper_80)}">${dfs.int(f.predicted)}</td>`).join('')}
            <td class="num"><strong>${dfs.int(u.total_7_days)}</strong></td></tr>`).join('');
        warnings('all-warnings', (data.skipped || []).map((s) => `${s.name}: ${s.message}`));
        showOnly('all-section');
        dfs.show('map-container', lv === 'district');
        if (lv === 'district') {
            const h = horizon || currentHorizon();
            const m = await dfs.api('/api/map', { horizon: h });
            if (m.status === 'ok') { lastMap = m; drawMap(m); }
            else dfs.emptyChart('map-chart', m.message || 'The map could not be drawn.');
        }
        done();
    }

    /* sequential single-hue (blue) choropleth; log colour scale because counts are skewed */
    function drawMap(m) {
        const t = dfs.theme();
        const dark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const seq = dark ? [[0, '#184f95'], [0.5, '#3987e5'], [1, '#cde2fb']]
                         : [[0, '#cde2fb'], [0.35, '#6da7ec'], [0.7, '#256abf'], [1, '#0d366b']];
        const vals = m.values.filter((v) => v.unit_code !== 'DHAKA_METRO');
        const metro = m.values.find((v) => v.unit_code === 'DHAKA_METRO');
        const z = vals.map((v) => Math.log10(1 + v.predicted));
        const ticks = [0, 1, 5, 10, 50, 100, 500].filter((x) => Math.log10(1 + x) <= Math.max(...z, 1) + 0.2);
        dfs.setText('map-title', `District forecast for Day ${m.horizon} (${vals.length ? dfs.niceDate(vals[0].target_date) : ''})`
            + (metro ? ` · Dhaka Metropolitan (city hospitals, not shown on the map): ${dfs.int(metro.predicted)}` : ''));
        dfs.plot('map-chart', [{
            type: 'choropleth', geojson: m.geojson, featureidkey: 'properties.pcode',
            locations: vals.map((v) => v.unit_code), z, zmin: 0, colorscale: seq,
            marker: { line: { color: t.bg, width: 1 } },
            customdata: vals.map((v) => [v.name, v.predicted, v.lower, v.upper, v.method === 'top_down' ? 'top-down' : 'direct']),
            hovertemplate: '<b>%{customdata[0]}</b><br>%{customdata[1]:,.0f} admissions<br>80%: %{customdata[2]:,.0f}–%{customdata[3]:,.0f}<br>%{customdata[4]}<extra></extra>',
            colorbar: { title: { text: 'admissions', font: { color: t.text2, size: 12 } }, tickvals: ticks.map((x) => Math.log10(1 + x)),
                        ticktext: ticks.map(String), tickfont: { color: t.text2 }, thickness: 12, len: 0.6 },
        }], { paper_bgcolor: t.bg, plot_bgcolor: t.bg, margin: { l: 0, r: 0, t: 0, b: 0 },
              geo: { fitbounds: 'locations', visible: false, bgcolor: t.bg }, font: { color: t.text } });
    }

    // ---------------------------------------------------------------- downloads
    const CSV_HEAD = ['place', 'place_code', 'level', 'forecast_unit', 'issue_date', 'data_as_of', 'day', 'target_date',
                      'predicted_admissions', 'lower_80', 'upper_80', 'method', 'model', 'test_MAE', 'warnings'];
    const rowsOf = (d, list) => list.map((f) => [d.requested_name || d.unit_name, d.requested_code || d.unit_code,
        d.requested_level || d.level, d.unit_code, d.issue_date, d.origin_date, f.horizon, f.target_date,
        f.predicted, f.lower_80, f.upper_80, f.method, f.model, f.test_MAE, (d.warnings || []).join(' | ')]);
    const fname = (d, suffix, ext) => `dengue_forecast_${(d.requested_code || d.unit_code)}_${suffix}_${d.issue_date}.${ext}`;

    function downloadSingle(kind) {
        if (!last) return;
        if (kind === 'json') dfs.download(JSON.stringify(last, null, 2), fname(last, `day${last.forecast.horizon}`, 'json'), 'application/json');
        else dfs.download(dfs.toCsv(CSV_HEAD, rowsOf(last, [last.forecast])), fname(last, `day${last.forecast.horizon}`, 'csv'), 'text/csv');
    }
    function downloadOutlook(kind) {
        if (!lastOutlook) return;
        if (kind === 'json') dfs.download(JSON.stringify(lastOutlook, null, 2), fname(lastOutlook, '7day', 'json'), 'application/json');
        else dfs.download(dfs.toCsv(CSV_HEAD, rowsOf(lastOutlook, lastOutlook.forecasts)), fname(lastOutlook, '7day', 'csv'), 'text/csv');
    }
    function downloadAll() {
        if (!lastAll) return;
        const rows = lastAll.units.flatMap((u) => rowsOf(u, u.forecasts));
        dfs.download(dfs.toCsv(CSV_HEAD, rows), `dengue_forecast_all_${lastAll.level}s_${lastAll.issue_date}.csv`, 'text/csv');
    }
})();
