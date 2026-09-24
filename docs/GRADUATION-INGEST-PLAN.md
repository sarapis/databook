# Graduation outcomes ingest — plan

> Ingest NYC DOE **Graduation Results, Cohorts 2012–2019** (`mjm3-8dw8`) as
> `graduationoutcomes` and surface a Graduation section on the school profile.
> This is the **first outcomes data in Databook** — before it, prod held no
> graduation, regents or expenditure table at all.

## STATUS — planned 2026-09-21, building now

Origin: an assessment of `districtfacts.com`, which publishes NY school-district
finance from ST-3 and switches to NYC Open Data sources for New York City.
⚠⚠ **Their district-finance engine does not transfer**: NYC is ONE district in
ST-3, so it yields a single row for the whole city and cannot describe our 32
community districts, let alone ~1,600 schools. What transfers is their NYC half,
and of that we already hold the Demographic Snapshot (`c7ru-d68s`). **Graduation
Results is the one genuinely new, directly ingestible source.**

⚠ Per-school FINANCE — the larger gap — is deliberately **out of scope** and is
not merely unbuilt: it is unavailable in bulk. SchoolBAG is a stateful ASPX app
that ignores a `?dbn=` parameter (measured: byte-identical 11,506-byte responses
with and without), the School Based Expenditure Report is on Socrata only for
2016-17, and Fair Student Funding / SAM are 2015–2017 snapshots. That absence is
why DistrictFacts covers 47 curated NYC schools rather than all of them.

## 1. The dataset, as measured (2026-09-20, not recalled)

**321,002 rows.** Grain is
`(report_category, geographic_subdivision, category, cohort_year, cohort)`.

| `report_category` | rows |
|---|---:|
| School | 291,506 |
| District | 21,895 |
| Borough | 3,434 |
| Charter School | 2,198 |
| Citywide | 1,130 |
| Transfer School | 839 |

- `cohort_year` **2012–2019** — classes of 2016–2023.
- `cohort`: `4 year June` (64,841) · `4 year August` (64,841) · `5 year June` /
  `5 year August` (56,663 each) · `6 year June` (48,498). **`4 year June` is the
  headline** — on-time graduation as of June.
- `category`: 20 values. `All Students` (17,093) plus ELL / SWD / race / gender /
  economic-disadvantage breakdowns.
- **497 distinct school DBNs**, i.e. high schools only — about 23% of our 2,131
  schools. The rest correctly have no graduating cohort.
- Headline slice (`School` + `All Students` + `4 year June`) covers 468–480
  schools per cohort year.
- **Per-school payload: avg 587 rows, max 686.**

## 2. ⚠⚠ Three findings that shape the build

### 2a. There is no DBN column
For `report_category='School'` the DBN lives in **`geographic_subdivision`**
(`02M422`). It matches `schoollocations.system_code` (`01M015`) exactly, so the
join is clean — but **`report_category = 'School'` is load-bearing**. Without it,
Borough and Citywide rollups join onto individual schools and every figure is
silently wrong in the overstating direction.

### 2b. ⚠⚠ `schoollocations.system_code` IS NOT UNIQUE — a naive join inflates
Measured on prod: the 497 grad DBNs join to **513 rows**. Cause: **59 byte-exact
duplicate rows** in `schoollocations` — `to_jsonb(t)` is identical and no column
differs; 2,190 rows carry 2,131 distinct `system_code`s, and even
`location_code` repeats (`02M255` twice, both `M255`).

This is the same family as the `contracts` amendment double-count (#262/#278):
**a join that looks like a lookup and is actually a multiplier.** Any join to
`schoollocations` here must dedupe.

⚠ It is also a **pre-existing defect in our own table**, independent of this
work, and silently inflates any other join to it. Worth its own task.

⚠ 1 of 497 DBNs does not match — `19K953`. Expected: `schoollocations` is the
2019-20 vintage and schools close.

### 2c. ⚠⚠ `UNTRACKED_TABLES` ALONE REGISTERS NOTHING ON PROD
`register_untracked_tables()` is reachable only from
`populate_from_datasets_json`, which returns early unless a `datasets.json`
exists at a dev path that is not on the box. `main()` calls
`apply_registry_deactivations` and `register_capital_datasets` **ungated**, and
the latter exists precisely because this bit the capital rebuild — *"the seed
reported success and created none of the seven."*

⭐ So the live precedent is a NAMED, ungated registration function reading the
same `UNTRACKED_TABLES` / `METADATA_CORRECTIONS` declarations. No guard pins
`register_capital_datasets` by name, so generalising it is safe.
⚠ `test_registry_seed.py` DOES assert `register_untracked_tables` is never
called from `main()`. That assertion stays.

## 3. Change set

| file | change |
|---|---|
| `api/setup_data_pipeline.py` | `UNTRACKED_TABLES` + `METADATA_CORRECTIONS` entries; `GRADUATION_DATASETS`; generalise `register_capital_datasets` → `register_explicit_datasets` over `CAPITAL_DATASETS + GRADUATION_DATASETS`; update `main()` |
| `api/data_scheduler.py` | `TABLE_INDEXES["graduationoutcomes"]` — **mandatory**, see §4 |
| `api/main.py` | one `col_map` entry in `get_school_section` |
| `app/app/Custom/SchoolDatasets.php` | the `graduation` section, `DBNkey => system_code` |
| `api/tests/test_graduation_ingest.py` | the guards in §5 |

**Routing is direct Socrata, not the normalizer.** The precedent is `attendance`
— Schools category, DBN-keyed, no `wegov-org-id`. `demographics` IS normalized;
this is not.

⚠⚠ **Column names come from the CSV header, not the JSON API.** `/import-csv`
creates the table from the header row, so the columns are the display names —
`"# Total Cohort"`, `"# Grads"`, `"% Grads"`, `"# Advanced Regents"`,
`"Geographic Subdivision"`. The CSV also carries **`School Name`**, which the
JSON API does not expose. Same convention as `attendance` (`"# Total Days"`,
`"% Attendance"`).

## 4. ⚠ The index is mandatory, not a nicety

The section endpoint runs
`SELECT * FROM graduationoutcomes WHERE "Geographic Subdivision" = $1` on every
profile view, against **321,002 rows**. Unindexed that is a sequential scan per
page view.

```python
"graduationoutcomes": [
    ("idx_grad_dbn",   '"Geographic Subdivision"'),
    ("idx_grad_slice", '"Report Category", "Category", "Cohort"'),
],
```

⚠⚠ **Declared in `TABLE_INDEXES`, never created by hand.** The ingest DROPs the
table and recreates it, so a hand-made index dies at the next ingest and nothing
raises — the documented rule that cost this repo six missing indexes.

## 5. Guards

1. The section query carries `Report Category = 'School'` (§2a).
2. Any join to `schoollocations` is deduped: 497 DBNs must yield **497** rows,
   not 513 (§2b). Mutation-verify by removing the dedupe.
3. `graduationoutcomes` is registered by the ungated path, and
   `register_untracked_tables` is still not called from `main()` (§2c).
4. The declared index columns exist in the ingested table — the
   `_CONTRACTS_COLS` precedent, because `recreate_table_indexes` **swallows** a
   failed `CREATE INDEX` and prints ✗ without raising.

## 6. Deploy

Registry → ingest → verify indexes → app. In that order.

1. `docker compose exec -T api python setup_data_pipeline.py`
2. Let the scheduler ingest, or force it. ⚠ The "daily" extractor ingest runs
   **~16 days in 21** (task `2e414da8`), so do not wait on it.
3. **Verify against `pg_indexes`, not the script's exit code** — an idempotent
   `CREATE INDEX IF NOT EXISTS` re-runs cleanly whether or not anything persisted.
4. Rebuild `app` (Blade views are bind-mounted, but `app/app/Custom/` is not),
   then `view:clear` + `config:clear`.

⚠ Do not start inside the 04:00 `docker compose restart api` window — it kills a
`docker compose exec` with no traceback.

## 7. Verification

- `pg_indexes` shows both indexes after a real ingest.
- A high school renders the section with plausible figures.
- ⭐ **A non-high-school renders NO section rather than an empty table.** An
  absent panel must read as *"this school has no graduating cohort"*, never as
  *"data missing"* — the honest-degradation rule.
- The rendered page states which cohort it is showing (§8).

## 8. Owner decisions

- ⚑ **A — vintage disclosure.** The latest cohort is **2019 = class of 2023**,
  and `mjm3-8dw8` is the newest graduation dataset NYC publishes on Socrata
  (checked: the only others are `9vpe-8zuf`, cohorts 2001–2011, and a 2009-10
  Regents file). Shipping it is right; the page must say which cohort it shows
  rather than implying currency. **Taken: state the cohort.**
- ⚑ **B — district pages. TAKEN 2026-09-21**, off the same table with no new
  ingest. All **32** community school districts are present and the key is a
  BARE NUMBER (1-32) — the same shape as `schoollocations.Geographical_District_code`,
  verified rather than assumed. 674-688 rows per district.
  - ⚠ Unlike the School half there is **no grain collision**: measured, a bare
    district number appears under no other `Report Category`, so the filter
    changes no row today. It is applied anyway (`_DISTRICT_FIXED_FILTERS`) so
    the grain is a guarantee rather than a coincidence a later publication could
    remove — and because the School half DOES collide on 54 of 497 DBNs.
  - ⚠ The panel is reachable only from `sd`: `DistDatasets::get()` returns null
    when a section has no `map` entry for the type, so `/d/cd-…/graduation`
    404s. Verified in both directions.
  - ⚠⚠ **AND IT FOUND A LANDMINE IN THE PRESELECT MECHANISM.** `#417` derived
    filter preselects from a non-null value in `filters`, which was inert for
    schools (all 15 other sections declare null) and would NOT have been for
    districts: `requests` carries a dormant `0 => '2020-07-01'`, a Publication
    Date, so the live Requests page would have been pinned to a single day by a
    line nobody wrote for that purpose. Both registries now read an explicit
    `fltPreselect`; the dormant declaration is left exactly as found.
