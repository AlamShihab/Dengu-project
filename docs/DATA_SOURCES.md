# Data sources — evidence (probed 2026-10-12 from Shihab's PC)

## 1. DGHS Daily Dengue Press Release PDFs (primary source for districts)

- Index page (lists every PDF link):
  `https://dghs.gov.bd/pages/static-pages/dengue-press-release-gxrgtg-6a9eb4cc7a024513d1b8c896`
  (866 KB HTML, 1,878 PDF links; saved list: `source_samples/dghs_pdf_urls_2026-10-12.txt`).
- URL pattern: `https://dashboard.dghs.gov.bd/osource/images/docs/vpr/YYYYMMDD_dengue_all.pdf`
  (2019 used `.../docs/Notice/2019/dengue/*.pdf`, a different format, 158 files).
- Count by year (`vpr`): 2021: 19 (from 2021-12-13) · 2022: 365 · 2023: 365 · 2024: 360 · 2025: 365 · 2026: 246
  (2026-01-01 → **2026-09-03**). HEAD checks on 2026-09-04, 09-20, 10-01, 10-10, 10-11 all return **404**.
- Plain `curl` gets 403 from dashboard.dghs.gov.bd; a browser User-Agent gets 200.
- Samples downloaded (SHA-256 in `source_samples/sample_pdf_sha256.txt`): 2022-08-15 (6 pages), 2024-08-15 (10 pages),
  2026-09-03 (10 pages).

### What is inside (2024/2026 layout)
| Pages | Content |
|---|---|
| 1–4 (English, A3 portrait) | national 24 h admissions and deaths, division & city-corporation bar charts (last 24 h and since 1 Jan), age/sex tables, discharged, monthly chart |
| 5–6 | Dhaka metropolitan hospitals, hospital by hospital (government and private): 24 h admitted, total admitted, deaths, discharged, currently admitted |
| 7–9 (8–10 in 2026) | **"Dengue cases and deaths reported from Dhaka metropolitan and divisions" table**. Columns: division · serial · **district** · institution name · *24 h new admissions: government / private / total* · *since 01-01: admitted / deaths / discharged* · *currently admitted*. One row per district, with extra rows for medical-college hospitals and a district subtotal row ("… জেলার মোট"), then a division total row ("বিভাগের সর্বমোট"). Example images: `source_samples/2026-09-03_district_table_p8.png`, `_p9.png` |
| last | monthly cases/deaths chart (English digits) |

2022 has the same district table on pages 4–5, plus Dhaka hospital tables with dengue-type columns (DF/DHF/DSS).

### Text extraction
- PyMuPDF `page.get_text()` returns Unicode Bangla. **Digits are clean Bangla digits** (০–৯). Fonts: Nikosh,
  SutonnyMJ, SolaimanLipi. No OCR needed.
- Some Bangla words lose glyphs (e.g. `চট্টগ্রা` for চট্টগ্রাম, `কক্সোজাি` for কক্সবাজার, `কুর ল্লা` for কুমিল্লা).
  They are consistent, so an alias table works. `pdftotext -layout` (available in Git Bash `/mingw64/bin`) gives the
  same text without coordinates.
- The parser must use word **coordinates** (column x-ranges) because the text order mixes columns.
- The Dhaka district row is "ঢাকা (ঢাকা মহানগর ব্যতীত)" = Dhaka excluding metropolitan; metropolitan hospitals are separate.

## 2. DGHS live dashboard `https://dashboard.dghs.gov.bd/pages/heoc_dengue_v1.php`
- Reachable (browser UA). Chart ids: `division_case`, `division_death`, `div_city_cor_case_in_year`,
  `affected_in_division_by_week`, … **No district data.** National + 8 divisions + DNCC/DSCC only.
- Already scraped by `../bd-health-signals/pipeline/fetchers/dghs_dengue.py` (10 reporting units).
- Possible use: keep **division-level** forecasts current after 2026-09-03 (needs a reconciliation check that the
  dashboard division numbers equal the PDF division totals).

## 3. New DGHS press-release list `https://dghs.gov.bd/pages/press-releases`
- 191 entries, mostly measles (হাম) since 2026-04. One dengue item "ডেঙ্গু-প্রেস-রিলিজ-১৭০৯২০২৬" (17 Sep 2026); its
  attachment link is broken (`.../o/undefined`). There is no regular daily dengue district release here.

## 4. Other local data (reference only, read-only)
- `../bd-health-signals/data/reference/`: `gazetteer.csv` (8 divisions, 64 districts, 544 "upazila" rows with BBS
  pcodes, Bangla names, Census 2022 population, lat/lon), `names_bn.csv`, `reporting_units.csv`,
  `boundaries_district.geojson`, `boundaries_division.geojson`. Use for codes, names, population and the map.
- `../bd-health-signals/data/official_counts.csv`: national daily 2026-01-01 → 2026-10-10 (dashboard).
- Codex's `bd-dengue-monitor` (`C:\Users\USER\Documents\Codex\2026-10-11\you\outputs\bd-dengue-monitor`): national
  12 Sep → 11 Oct 2026 and one day of division data. Its plan is copied into `codex_planning/`.
- Literature: Nabed et al., BMC Public Health 2026 (doi 10.1186/s12889-026-28806-y) used daily district DGHS admissions
  2022–2025, which is consistent with this PDF archive.

## 5. Upazila
No public daily (or weekly) upazila dengue data was found. DGHS PDFs stop at district level plus named hospitals.
Upazila data would need DGHS DHIS2 / IEDCR access.

## 6. Verification results (2026-10-12, after the full download and parse)

- **Download**: 1,690 PDFs (2021-12-13 → 2026-09-03), 0 download errors; 75 dates return 404 (36 historic gaps,
  including 2024-07-18..23 during the internet shutdown, and every date after 2026-09-03). Some 404 dates are linked
  from the DGHS index page but missing on the server (broken links on the DGHS side).
- **Parsing**: 1,680 of 1,690 PDFs parsed (1,643 ok, 37 with warnings); 10 PDFs use a different font encoding and
  fail (their dates are missing for districts; divisions/national come from the dashboard where available).
  On **every** parsed date the sum of the 65 district units equals the PDF's own printed nationwide total.
  The 37 warnings are mostly a Rajshahi division subtotal row in DGHS's table that does not add up (the unit rows
  still reconcile with the national total) and a few PDFs whose printed date is a template typo.
- **Layouts handled**: 2022 (blank cells for zero deaths), 2023 (new medical-college rows, wrapped names),
  2024-2026; glyph mappings changed several times (151 distinct printed district labels → 64 districts, all reviewed).
- **PDF vs dashboard** on 32 overlapping dates (Aug 2024 – Sep 2026): divisions equal on 251 of 256 rows, national
  on 30 of 32 (differences of at most 1 nationally, or a reassignment between divisions with the same national total,
  i.e. DGHS revisions). Dhaka Metropolitan (PDF city-hospital row) vs DNCC+DSCC (dashboard): equal on 21 of 32 days
  (median difference 0; up to 5% lower on the dashboard in late 2024). Since 2026-09-04 the Dhaka Metro unit comes
  from the dashboard; on recent dates the two definitions mostly agree.
- **Hand checks**: 2026-09-03 district subtotals (Faridpur, Gazipur, Kishoreganj, Mymensingh) and all divisions vs the
  dashboard; 2023-06-15 Mymensingh block (includes a printed "-1" discharged cell and blank deaths) vs the page image.
  These are encoded as tests in `pipeline/tests/test_pdf_parser.py`.
