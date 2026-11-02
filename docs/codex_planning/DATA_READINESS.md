# Forecast data readiness

Planning assessment, 12 October 2026. This establishes gaps; it does not certify a model dataset.

| Source | Verified locally / through research | Readiness |
|---|---|---|
| Active `data/store.json` | 30 national dates, 12 Sep–11 Oct 2026; 10 division/city units only on 11 Oct | Insufficient for district, upazila or seasonal division training |
| Separate Desktop `bd-health-signals/data/official_counts.csv` | 608 metric rows; national new_cases and deaths each cover 283 dates, 1 Jan–10 Oct 2026; other rows are snapshots | Potential national backfill after source/metric reconciliation; no district history |
| Desktop geographic reference files | Division/district boundaries, reporting-unit and hospital crosswalk candidates; 8/64/544 lookup rows labelled division/district/upazila | Candidate reference only; administrative type, date validity, codes, parents, provenance and licences need review |
| DGHS live dengue dashboard | National and division/city reporting observed in existing V1; daily HTTP collector previously tested | Current collector extracts national totals only; new historic district ingestion required |
| Published district study | Reports daily 64-district DGHS admissions for 2022–2025; acknowledges hospital-location basis and imputed missing dates | Strong acquisition lead; its underlying raw district series has not been obtained or verified here |
| Upazila daily dengue history | None acquired or verified | Unavailable for forecasting until a suitable source is obtained |

Study source: [Nabed et al., BMC Public Health, 2026](https://link.springer.com/article/10.1186/s12889-026-28806-y). The study reports interpolation in its analytical dataset. Any acquired study export must retain missingness/original-observation flags; interpolated values cannot become forecast evaluation truth.

Official entry points: [DGHS dashboard](https://dashboard.dghs.gov.bd/pages/heoc_dengue_v1.php) and [daily press-release archive](https://old.dghs.gov.bd/index.php/bd/home/5200-daily-dengue-status-report). The archive timed out in the web reader during this turn. A separate paper endpoint was blocked by a browser-check page; no contents were inferred from that page. This does not prove the primary data is unavailable.

## Acquisition gate

1. Locate actual daily district tables/API/downloads, then inspect representative records from multiple years and source layouts before bulk collection. Start with DGHS originals; study data is a secondary acquisition route with provenance checks.
2. Record report date, publication/availability time where known, daily metric, geographic basis, coverage, revisions, source URL, raw hash and extraction method. Keep releases immutable.
3. Establish whether Dhaka-city hospital categories are already included in district totals. Do not add city and district figures twice. Division-outside-city figures are not districts.
4. Seek at least two full seasonal cycles, preferably 2022 onward if obtainable. Profile every unit separately; annual/monthly totals cannot be expanded into fabricated daily observations.
5. Normalize official codes and parent relationships. Investigate the 544 purported upazila records before use; the file may mix administrative types or include outdated geography.
6. Distinguish zero reports from absent records. Resolve cumulative resets and retrospective corrections. A cumulative difference is not automatically a valid daily admission count.
7. Validate a stratified sample manually and reconcile same-basis daily district sums to divisions/national totals where the source permits. Explain partial coverage and unmatched records.
8. Produce an eligibility file with explicit reasons: eligible, baseline_only, insufficient_history, stale_data, unresolved_geography, source_gap, or not_validated. Do not fill unsupported districts/upazilas with invented forecasts.

## Interpretation contract

The initial target is **daily reported dengue hospital admissions attributed to reporting-facility geography** when that is what the source records. It does not estimate all infections or the number of infected residents. A residence-based series, if acquired, must remain a separate target and dataset. The UI must display this basis next to the forecast.

## Local inspection reproduction

Run `scripts/inspect_forecast_readiness.py` from the dengue root using Python. Its JSON output records counts, all legacy series, reference configuration and input-file hashes. It only reads the other projects. Counts and mapping candidates still need source-level validation in F01–F02.
