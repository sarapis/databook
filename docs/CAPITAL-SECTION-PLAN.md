# Capital Projects section — rebuild plan

**v0.2 · 2026-09-04 · nothing built.** Companion to
`docs/CAPITAL-SECTION-REVIEW.md` (the measured review this plan answers) and
Hub task `dbc5aeac`. Items marked **⚑** were owner decisions; **A–D were
decided 2026-09-04 exactly as assumed below**, so the plan reads as written.
E remains an assumption.

Every figure here was measured on 2026-09-03/04 against Socrata, prod Postgres,
or the codebase. Where a join rate is stated, it was computed, not estimated.

---

## 0. Decisions

| ⚑ | decision | status | resolved as |
|---|---|---|---|
| A | What happens to the retired 2023 series | **decided 2026-09-04** | kept as **labelled history**, never a default, never a tile source |
| B | The project universe | **decided 2026-09-04** | **the current Capital Commitment Plan (CPDB, 12,905 distinct ids)**, plus a flagged tail of ids seen only in older sources |
| C | Non-Socrata feeds (Parks JSON, DDC ArcGIS) | **decided 2026-09-04** | **in scope**, both as extractors |
| D | Section navigation | **decided 2026-09-04** | **keep the six URLs**; `/projects/capital` becomes the Overview and moves first in the nav |
| E | Council member attribution on capital awards | assumed | **yes** — public data, links to People pages (§4.2, §5.5) |
| F | How to present CPDB's six money columns | **decided 2026-09-05** | **separate measures, each with its own population and an info note, plus one note saying why they are not a funnel** |

> ⚠⚠ **⚑ F — THE MONEY COLUMNS ARE NOT A FUNNEL. Earlier drafts of §5.3 drew one
> and would have shown money vanishing.** Measured 2026-09-05 straight from
> `capitalprojectslist` and reproduced exactly by `capital_program_stats`:
>
> | measure | total | projects with a value (of 12,929) |
> |---|---:|---:|
> | Planned commitments | $201.6B | 9,213 |
> | Adopted | $427.1B | 11,650 |
> | Allocated | $309.0B | 10,767 |
> | Committed | $30.4B | 5,158 |
> | Spent | $87.8B | 7,118 |
> | Paid (Checkbook NYC) | $70.7B | 6,507 |
>
> They do not nest — adopted is more than twice planned, committed a third of
> spent — because they cover different windows (committed is within the current
> plan period; spent is cumulative over the project's life) and each is
> published for a different subset.
>
> **Resolved:** show all six as separate measures, each rendered with its own
> population and an **info icon carrying the publisher's own definition**, plus
> one note explaining why they neither sum nor nest. `modules/capitalmoney.py`
> owns that copy so the endpoint and the page cannot drift, and it quotes DCP
> and the Comptroller rather than paraphrasing them — the only claim in our own
> voice is the arithmetic, marked `basis`.
> ⚠ It also carries DCP's own caveat verbatim: *"The Capital Projects Database is
> not a project or financial management system. Budgetary information may be
> incomplete since all monies committed to or spent on a project may not be
> captured."*

---

## 1. Goal and principles

Rebuild the section on the data the City publishes **now**, keep everything
current through the Pipeline (`dataset_registry` → scheduler → normalizer →
post-ingest hooks), and stop presenting a series NYC retired in October 2023 as
the present.

Principles — each is a rule this repo has already paid for elsewhere:

1. **One universe, one key.** Every page reads the same derived project table
   keyed on a normalised FMS id. No page re-derives the universe.
2. **The Overview computes nothing.** Every figure it shows is a key another
   endpoint serves, linked (the Digital Services rule).
3. **Every payload carries its vintage.** `sources: [{table, as_of, version}]`
   on every capital endpoint; every page renders it. The plan version
   (`ccpversion`) and Dashboard `reporting_period` are the two that matter.
4. **Empty means "not published", and says so.** A project with no schedule
   renders "no published schedule", never a blank. The org tab already does this
   (`section-coverage`); it becomes the norm.
5. **Freshness is the Pipeline's job.** Nothing in the section is loaded by
   hand. A source that cannot go through the registry gets an extractor and a
   hook, the way `vendors`' enrichments do.
6. **History is a source, not a default.** Old snapshots (2023 series,
   Dashboard periods) live in one history table with a `source` column; the
   current row is always from the current plan.

---

## 2. The 2023 series (⚑ A): keep or drop

`capitalprojectsdollarscomp` + `capitalprojectsmilestones` — OMB Capital
Project Detail Data, 14 publications 2019-04 → 2023-10-26, retired. Measured:
72,437 dollar rows / 497,727 milestone rows; final publication 5,126 projects.

### Keep — arguments

- **It is the only milestone-grain record that exists.** ~7 checkpoints per
  project (`DEVELOP SCOPE` → `PUNCHLIST COMPLETE`), each with original vs
  current start/end. The Dashboard replaced it with 4 phases. Nothing
  published since can answer "did design finish on time?" for the pre-2024
  book.
- **Original budget on 100% of rows.** CPDB has no original; the Dashboard's
  nearest thing is "earliest snapshot" (from 2023-05, or 2006 for some budget
  lines). For projects that predate 2023 the series is the only baseline.
- **Coded delay reasons on 73% of projects** (3,759; 12-code vocabulary).
  The Dashboard records 296 citywide.
- **Scope text (98%), site description, community board** — narrative fields
  CPDB lacks.
- **261 projects exist in no live source.** They were in the plan in 2023 and
  have since dropped out. Their `/p/` pages are indexed.
- **14 vintages** make a 2019-2023 trend possible per project.
- **Zero ingest cost.** It is frozen; nothing has to be scheduled.
- **The union pattern is already built** (#366, org tab): "in 2026 plan / in
  2023 series" as a visible column.

### Drop — arguments

- **It is the cause of the present problem.** Everything that reads it looks
  current and is not. Keeping it available is how it keeps being read.
- **Two schemas forever.** `PROJECT_ID` is blank-padded `character`;
  `BUDG_CURR`, `BUDG_DIFF`, `*_DIFF` are text holding `''` and `'-'`;
  `wegov-org-id` is numeric here and text in CPDB. Every query needs the
  guards `main.py` already carries (see the `capital-projects-via` docstring).
- **It disagrees with CPDB on who runs 525 projects**, and CPDB is measured to
  be right. Any join has to pick a side.
- **142 MB, mostly TOAST `GEO_JSON`** that belongs on a geometry table, not
  here. The map's 6-hour in-memory cache exists only because of this column.
- **~40 endpoints, 4 MCP tools, the sitemap and the briefing read it directly.**
  Each is a place the wrong vintage can re-emerge.
- **Its "Amount Over Budget" cannot be reproduced from anything live** and does
  not reconcile with its own columns (§ review 2.2). Keeping the table tempts
  someone to keep the tile.
- **It will never grow.** Every year the share of the program it describes
  shrinks; it already covers 40%.

### Recommendation

**Keep it — as history, and only as history.**

- Its rows move into `capital_project_history` (§3.4) with
  `source = 'cpdd'`, one row per (project, publication), beside the Dashboard's
  snapshots (`source = 'dashboard'`). The current-state table never reads it.
- `GEO_JSON`/`LAT`/`LNG` are dropped from it once geometry has its own table
  (§3.5). That alone removes the map cache.
- The **261 projects seen only there** keep their pages, badged *"Last seen in
  the October 2023 plan; not in the current Commitment Plan"*, and are
  excluded from every count, tile and map unless a "show dropped projects"
  toggle is on. They stay in the sitemap (their URLs are indexed) but with a
  `noindex` meta, so the pages resolve without being promoted.
- Every direct reader of `capitalprojectsdollarscomp` is retired or re-pointed
  (§7). A guard bans new readers outside the history builder.
- The registry row stays `is_active = false` and gets an honest
  `display_name`: *"Capital Project Detail Data (retired Oct 2023)"*.

If ⚑ A goes the other way — drop — the history table simply starts at
Dashboard period 202305, and the 261 pages become 410s with a note. Nothing
else in this plan changes.

---

## 3. Data model

### 3.1 The spine: `capital_projects`

> ⚠⚠ **CORRECTED 2026-09-05 while building it — the key is NOT the project id.**
> `capitalprojectslist` has 12,929 rows, 12,929 distinct `maprojid` but only
> **12,905 distinct `projectid`**: 24 ids are used by two managing agencies at
> once, for different work (`HWK1669B` is DDC $149.0M *and* DOT $202,595;
> `BROADBAND` is DFTA $1.26M *and* OTI $56.2M). A spine keyed on the project id
> discards one of each pair, arbitrarily. **The primary key is
> `(agency_key, fms_id)`**, `agency_key` being the 3-digit managing-agency code,
> which every source can produce (the Dashboard's acronym maps 1:1 to it; its
> one unknown acronym is EDC, which holds no capital budget line).
> ⭐ The count looked plausible either way — only the MONEY showed the loss:
> $201.2B keyed on the id against **$201.6B**, the source total, keyed on the
> pair.
>
> ⚠ **The spine is 17,024 rows, not ~13,200.** §0's "261 + 52" tail was measured
> on the latest snapshots only; across all 14 publications and 10 periods the
> tail is 4,095. Distinct bare ids: 15,813.

One row per (managing agency, FMS project id), built by `api/build_capital_projects.py` (a
`build_*.py` in the pattern of `build_contract_timeline.py`), rebuilt by
post-ingest hook whenever any source table lands.

| column | from | notes |
|---|---|---|
| `agency_key` + `fms_id` (**composite PK**) | CPDB `magency` + `projectid` | see the correction above; `fms_id` is indexed but NOT unique |
| `maprojid` | CPDB | agency-prefixed form, kept for links |
| `agency_code`, `agency_acro`, `agency_name`, `wegov_org_id` | CPDB `magency`/`magencyacro`/`magencyname`/`wegov-org-id` | ⚠ `magency` is a numeric CODE; the normalizer stamps `wegov-org-id` |
| `sponsor_agency` | Dashboard `sponsor_agency` (blank on 60%) | |
| `description` | CPDB `description` → Dashboard `agency_project_name` → `fms_project_name` | first non-blank |
| `type_category` | CPDB `typecategory` | Fixed Asset / Lump Sum / ITT… |
| `ccpversion` | CPDB | the plan vintage |
| `planned_total_usd`, `adopt_total_usd`, `allocate_total_usd`, `commit_total_usd`, `spent_total_usd`, `spent_checkbook_usd` | CPDB money blocks | the funnel; **dollars at source** (the 2023 series was thousands — never mix) |
| `plan_min_date`, `plan_max_date` | CPDB `mindate`/`maxdate` | plan-year boundaries, NOT a schedule — label accordingly |
| `dash_period` | Dashboard latest `reporting_period` | NULL = no published schedule |
| `dash_pid` | Dashboard `pid` | agency project id, 61% |
| `current_phase`, `phase_start`, `forecast_phase_end`, `forecast_completion` | Dashboard | `current_phase` raw + `phase_class` (standard / parenthesised-status) |
| `actual_design_start/end`, `actual_procurement_start/end`, `actual_construction_start/end` | Dashboard | |
| `dash_total_budget_usd`, `dash_spend_to_date_usd` | Dashboard | |
| `borough`, `community_boards[]` | Dashboard → geometry spatial join → 2023 series | first available, `borough_source` recorded |
| `budget_lines[]` | CPDB commitments (distinct `budgetline`, normalised) | |
| `ten_year_category` | Dashboard `ten_year_plan_category` → CPDB commitments `typcname` | |
| `has_geometry`, `geom_kind` | §3.5 | point / polygon / none |
| `in_current_plan`, `in_dashboard`, `in_cpdd_2023`, `in_parks_tracker`, `in_climate` | derived | the "which sources carry it" flags the org tab already renders |
| `first_seen`, `last_seen` | history | |
| `climate_*` | §4.2 Climate Budgeting | mitigation / flood / heat ratings + indexes |
| `sources` (jsonb) | builder | `[{table, as_of, version}]` — emitted on every payload |

Rows exist for every `fms_id` in CPDB (12,905 distinct) **plus** ids seen only
in the Dashboard (52 in 202605) or only in the 2023 series (261), flagged
`in_current_plan = false` (⚑ B).

### 3.2 Source inventory and Pipeline route

**Already ingested — keep, wire into the build.**

| table | source | grain | route | cadence (source) | change needed |
|---|---|---|---|---|---|
| `capitalprojectslist` | CPDB `fi59-268w` | project | normalizer ds 241 (stamps `wegov-org-id`) | tri-annual | hook → rebuild spine |
| `capitalprojectscommitments` | CPDB `djxg-kcfi` | commitment line | normalizer ds 240 | tri-annual | hook → rebuild spine; `TABLE_INDEXES` on `projectid`, `budgetline` |
| `capprojectsbudgetsandschedule` | Dashboard `fb86-vt7u` | period × FMS id | normalizer ds 244 | tri-annual | hook → rebuild spine + history |
| `capprojectsbudgetandspend` | `gyhf-rsr3` | period × FMS × FY | ds 325 | tri-annual | profile funding table (as today) |
| `capprojectsschedulehistory` | `95tx-snak` | period × agency project | ds 327 | tri-annual | history; Overview slippage chart |
| `capprojectsbudgetspendhistory` | `qj5n-h5qp` | year-month × FMS | ds 326 | tri-annual | history; per-project budget chart |
| `capitalcommitmentplan` | OMB `2cmn-uidm` | pub × budget line | socrata direct | tri-annual | unchanged; Budget Lines / Commitments pages |
| `capitalbudget` | OMB `46m8-77gv` | pub × budget line | socrata direct | annual + | ⚠ **in `DATED_DATASETS` and `is_active=false`** — that is why it stopped at 2026-05-12 while Socrata has the Adopted FY27 (2026-07-13). Remove from `DATED_DATASETS`, reactivate. |
| `capitalstrategy` | OMB `b37a-3faw` | pub × type × category | socrata direct | biennial | unchanged |
| `capitalcommitmentactuals` | OMB `8u85-k342` | agency × FY | socrata direct | annual | **used nowhere today** → Overview "commitment rate" chart |
| `scacapitalprojectschedules`, `scaactiveprojects` | SCA `2xh6-psuq`, `8586-3zfm` | building × phase / site | socrata direct | quarterly | surface in the section as the DOE lens (§5.6); no FMS join exists — keyed on DOE building id |

**Retired — keep as history, stop reading directly (⚑ A).**

| table | change |
|---|---|
| `capitalprojectsdollarscomp` | source rows for `capital_project_history` (`source='cpdd'`); drop `GEO_JSON`,`LAT`,`LNG` after §3.5; rename display; keep inactive |
| `capitalprojectsmilestones` | keep; `capital_project_milestones_2023` view for the profile's history panel; the only consumer |
| `capitalprojectsdollars` | duplicate of the above minus enrichment; **drop** |
| `cpdb_projects`, `cpdb_commitments` | inactive duplicates already in `DUPLICATE_DATASETS`; **drop the tables** (nothing reads them; measured) |

**Add — Socrata, registry rows only.**

| table (new) | source | rows | grain | join | cadence | normalizer? |
|---|---|---|---|---|---|---|
| `cpdb_geometry_points` | `h2ic-zdws` | 2,776 | project | `projectid` | tri-annual | no |
| `cpdb_geometry_polygons` | `9jkp-n57r` | 1,784 | project | `projectid` | tri-annual | no |
| `climatebudgeting` | `c99a-c5ux` | 259,491 (3 pubs) | pub × project × budget line × FY | `project_id` = `"035 L21FREEZE"` → strip agency prefix → **9,119 of 9,134 match CPDB** (corrected) | annual (Exec budget) | no |
| `councilcapitalbudget` | `t474-a92g` | 11,503 | award | `budget_line` (`HD D024`, normalised) → CPDB commitments `budgetline`; `council_district`; `sponsor` → People | annual | **yes** — `sponsor` → `wegov-person-id` if the normalizer has a people core; else exact-name to `people` at build time |
| `capitalcashflow` | `4xfc-mzbg` | 2,356 | month × dept × FY | `dept` → org | monthly | yes — `dept` → `wegov-org-id` |
| `sogrneeds` | `vck7-ujai` | 43,063 | asset × component × plan year | `agency_name` → org; `capisid_bc` → FMS id (**untested**; measure before relying) | annual | yes — `agency_name` |
| `capitalfundingsource` | `4utb-pisg` | 188 | pub × source × FY | citywide | tri-annual | no |

⚠ **Geometry via Socrata:** the CSV export of `h2ic-zdws` carries `the_geom`
as WKT text; the `.geojson` endpoint (what `enrich_geo_json.py` already uses)
is cleaner. The registry's Socrata path downloads `rows.csv`. Two options:
(a) ingest the CSV and parse WKT in the builder with DuckDB spatial
(`ST_GeomFromText`) — no new code path; (b) a small `source_type='extractor'`
row whose script fetches `.geojson`. **(a)** unless the WKT export proves lossy.

**Add — extractors (⚑ C).**

| table (new) | source | rows | grain | join | cadence | note |
|---|---|---|---|---|---|---|
| `parkscapitaltracker` | `nycgovparks.org/bigapps/DPR_CapitalProjectTracker_001.json` | 2,244 | project (+ nested locations, funding sources) | `FMSID` `"846 P-405VITO"` → strip → **1,409 of 1,867 match CPDB** | daily at source; ingest daily | ⚠ the Socrata mirror `4hcv-tc5r` held **0 rows** on 2026-09-03 — the extractor reads the Parks feed and records which it used. `ingestion_mode='replace'`, `>50%` drop guard. |
| `ddcactiveprojects` | ArcGIS `DDC_ACTIVEPROJECTS_PUBLIC` FeatureServer (2 layers) | 164 projects / 4,891 features | project (+ geometry) | `ProjectID` → **157 of 164 match CPDB** | ~monthly | optional; CPDB already folds DDC geometry in. Lowest priority. |

Extractor shape: `api/extractors/parks_capital_tracker.py`, invoked by
`process_extractor_dataset` (daily, once-daily guard — ⚠ the guard is a 24h
delta, task `2e414da8`; a deploy can defer it a day). It writes a flat CSV to
`/data/pre-processed/` and the scheduler imports from `source_url`, exactly as
`passport_mocs.py` does. Nested `Locations[]` and `FundingSources[]` become
two child tables.

### 3.3 Id normalisation: `modules/fmsid.py` and `modules/budgetline.py`

The FMS id is spelled three ways across sources and budget lines four ways.
One owner each, used by every join:

```
fmsid.norm("850GKOH15-01") == fmsid.norm("GKOH15-01") == fmsid.norm("850 GKOH15-01") == "GKOH15-01"
fmsid.agency_code("850GKOH15-01") == "850"
budgetline.norm("HD D024") == budgetline.norm("HD-D024") == budgetline.norm("HDD024") == "HDD024"
```

Rules (measured shapes): strip a leading 3-digit agency code when followed by
a space or an alpha character; `btrim`; upper-case. ⚠ Not every id begins with
letters after the code (`P-405VITO`, `BED-774`), and a hyphen is legal inside
an id — so the rule is "leading `\d{3}` + separator", never "leading digits".
Guard: a table of every observed shape from all 7 sources must round-trip.

### 3.4 History: `capital_project_history`

One row per (fms_id, source, period). Columns: `budget_usd`,
`orig_budget_usd`, `spend_usd`, `start`, `end`, `forecast_completion`,
`phase`, `delay_reason`, plus `source ∈ {cpdd, dashboard}` and `period`
(`PUB_DATE` or `reporting_period`). Built from the 2023 series (14
publications) and the Dashboard (10 periods, growing). Feeds the per-project
budget/schedule chart and the Overview trend. ⚠ Money from `cpdd` is
`× 1000` at load; the column is suffixed `_usd` so it cannot be re-scaled
(the rule `capital-projects-via` already follows).

Milestones stay in `capitalprojectsmilestones` (2023 only, 497K rows) and
render on the profile as *"Milestones — last published October 2023"*.

### 3.5 Geometry and district crosswalks

`capital_project_geometry` — one row per fms_id: `geom_kind`, `geojson`,
`bbox`, `centroid_lat/lng`, `source ∈ {cpdb_points, cpdb_polygons, parks,
ddc}`, `as_of`. Built from the two CPDB geometry tables (4,560 projects,
35.3%), Parks locations (every Parks project has lat/lng; adds ~450 active
projects CPDB may not map), DDC optional.

`capitalprojects_{cd,cc,sd,nta}_idx` — rebuilt in the same hook by DuckDB
spatial (`ST_Intersects`) against `https://map.databook.nyc/data/{cd,cc,sd,nta}.geojson`,
**the exact mechanism `enrich_fire_data.py` uses for FDNY battalions**. Today
`cc_idx` and `sd_idx` hold 0 rows and nothing creates any of the three; this
gives them an owner. Coverage is bounded by geometry (35%); the crosswalk
carries `method ∈ {geometry, community_board_text, council_award}` so a
district page can say how many of its projects were located and how.

Council districts additionally get every project on a budget line that a
Council award (`t474-a92g`) funds in that district — a second, non-spatial
edge, labelled as such.

### 3.6 Program statistics: `capital_program_stats`

Replaces the four capital keys in `rebuild_glob_stats` and the 8 `pstats-*`
endpoint families. One row per (scope_type, scope_id, as_of) — scope
`program`, `org`, `cd`, `cc`, `sd`, `nta`, `budget_line`, `category`, `type`:

`projects`, `planned_usd`, `committed_usd`, `spent_usd`, `with_schedule`,
`in_construction`, `completed_recent`, `late_forecast` (Dashboard
`variance_day > 0`), `with_geometry`, `dropped_since_2023`, and for `program`
only `commitment_rate_fy` (actuals ÷ plan from `capitalcommitmentactuals`
+ `capitalcommitmentplan`).

**Retired tiles**: Original Cost / Current Cost / Amount Over Budget. CPDB has
no original budget; the three did not reconcile (§ review 2.2). Their honest
successor per project is the Dashboard budget history (first vs latest
snapshot), exposed on the profile and as a program-level *"budget growth
across snapshots, projects with a schedule only"* figure with its denominator
stated.

---

## 4. Pipeline changes, concretely

### 4.1 Registry (`api/setup_data_pipeline.py`)

- Add rows (§3.2) to `UNTRACKED_TABLES` + `METADATA_CORRECTIONS`; entity
  columns for the normalizer-routed ones in the entity-match config.
- Remove `capitalbudget` from `DATED_DATASETS`; reactivate.
- `capitalprojectsdollarscomp` display name → retired wording; stays inactive.
- Drop `capitalprojectsdollars`, `cpdb_projects`, `cpdb_commitments` (a
  one-off `scripts/` migration with a row-count print, after the history table
  is verified).
- `test_registry_seed.py` already fails a duplicate `socrata_id`; extend so a
  capital table cannot be re-added under a second name.

### 4.2 Hooks (`data_scheduler.POST_INGEST_HOOKS`)

```
capitalprojectslist            → [rebuild_capital_projects, rebuild_geometry_and_crosswalks, rebuild_capital_stats]
capitalprojectscommitments     → [rebuild_capital_projects, rebuild_capital_stats]
capprojectsbudgetsandschedule  → [rebuild_capital_projects, rebuild_history, rebuild_capital_stats]
capprojectsschedulehistory     → [rebuild_history]
capprojectsbudgetspendhistory  → [rebuild_history]
cpdb_geometry_points/polygons  → [rebuild_geometry_and_crosswalks]
parkscapitaltracker            → [rebuild_capital_projects, rebuild_geometry_and_crosswalks]
climatebudgeting               → [rebuild_capital_projects]
capitalcommitmentactuals       → [rebuild_capital_stats]
councilcapitalbudget           → [rebuild_crosswalks(cc), rebuild_capital_stats]
```

- The builders are idempotent and stage-then-swap (`_staging_*` → RENAME), the
  pattern `enrich_vendor.py` uses, with the >50% row-drop refusal.
- ⚠ **Hooks fire only for scheduler-ingested tables.** All of these are
  scheduler tables (normalizer-routed ones return through `/import-csv`, which
  does update the registry and… does it run hooks? **Verify** — `crol` did not
  until #265. Read the log for `[hooks] Running N post-ingest hook(s) for
  capitalprojectslist` after the first real ingest; that line is the proof.)
- Because six sources feed one builder, a guard asserts every source table in
  §3.2 has the spine rebuild registered — a source added later without a hook
  is the "declared but never runs" class.

### 4.3 Extractors

`api/extractors/parks_capital_tracker.py` (⚑ C). Registry row
`source_type='extractor'`, `source_url` = its output CSV path. Records
`feed_used` (`parks_json` / `socrata`) and `feed_as_of` (max `LastUpdated`).
Fails loudly on 0 records (the Socrata mirror precedent). Raises a Sentry event
on failure, as `oce-refresh.sh` learned to.

### 4.4 Indexes (`TABLE_INDEXES`)

`capitalprojectslist(projectid)`, `capitalprojectscommitments(projectid)`,
`(budgetline)`, `capprojectsbudgetsandschedule("FMS ID")`,
`("Reporting Period")`, `capprojectsbudgetspendhistory("FMS ID")`,
`capital_projects(fms_id)` PK, `(wegov_org_id)`, `(dash_period)`,
`capital_project_history(fms_id, source, period)`, and trigram on
`capital_projects(description)` (moving `idx_capproj_desc_*` off the raw table
into `modules/searchindexes.py`).

### 4.5 Stats

`rebuild_glob_stats`'s capital block reads `capital_program_stats WHERE
scope_type='program'` and stops computing anything itself. The four unrendered
top-10 lists are deleted. `most_expensive_list` was ordering a text column.

### 4.6 Staleness

`dataset-staleness.sh` already checks behind-source (>5 days) and
empty-at-source via LL251 `row_count`. Additions: the Parks feed is not in
LL251, so the extractor's own zero-record refusal is its empty check; the
retired tables need no ACK (inactive rows are not checked).

### 4.7 Cadence reality

Every core capital source moves **three times a year** (Prelim ~Jan, Exec
~May, Adopted ~Jul/Sep) with the Dashboard ~6 weeks behind each plan. The
Socrata path polls `rowsUpdatedAt` daily, so a new plan lands within a day of
publication and the spine rebuilds that night. The section should say *"Plan:
Executive FY2027 (May 2026) · Schedules: reporting period 2026-05"* rather
than a bare date, because the vintage is what a reader needs.

---

## 5. Pages and endpoints

URLs are kept (⚑ D). Every page reads the spine or a stats row; none reads a
source table directly except the budget-document pages, which are views of
those documents.

### 5.1 `/projects/capital` → **Overview**

Computes nothing; links everything. Tiles from `capital_program_stats
(program)`: projects in plan · planned commitments · committed · spent · with a
published schedule (n, %) · in construction · FY2025 commitment rate. Charts:
plan vs actual commitments by FY (actuals table, finally used); phase mix;
projects by agency (top 10 + all); budget growth across Dashboard snapshots
with denominator; a **coverage panel** naming agencies with 0 schedule
coverage (DOE $26.7B, OTI, HPD 0.3%) computed from the spine's flags. Vintage
strip. Endpoint `/get/capital/overview` returning only stats-row keys.

### 5.2 `/projects` → **Projects** (list + map)

Reads `/get/capital/projects` (spine, paginated server-side; the 13.7 MB
in-memory payload goes away). Columns: id, name, agency, category, phase,
planned, committed, spent, schedule?, location?. Filters: agency, category,
phase class, has schedule, has location, borough, in-plan / dropped (⚑ B).
Map from `capital_project_geometry` (`/get/capital/geojson`, cached at the
edge like `/oce/*`), with the honest legend *"4,560 of 12,905 projects have a
published location"*. Delete the volunteer-locating copy on all four pages.

> ⭐ **BUILT 2026-09-06.** Deviations from the text above, each measured:
>
> - **The legend is not typed at all.** It is the endpoint's own `coverage.note`,
>   printed verbatim, because the denominator depends on the filters applied —
>   the sentence quoted above ("of 12,905") is already wrong for the default view,
>   which matches 17,024. A guard bans a typed figure in this page's copy.
> - **One filter state, in the query string**, not a client-side table filter.
>   The controller builds `$capFilters` once and uses it for BOTH the list request
>   and the map URL, so the map follows the list by construction. A GET-form
>   reload rather than server-side DataTables ajax — it matches the idiom the
>   NYCHA record explorers already use, and it makes a filtered view shareable.
> - **`phase class` became the published phase values with counts**, plus the
>   `phase_is_standard` split expressed in the map's colouring (five standard
>   phases coloured, every parenthesised status one neutral colour). Inventing a
>   phase *class* would have been a second taxonomy; the spine already carries
>   the flag.
> - **A new endpoint was needed**: `/get/capital/projects/filters`, serving the
>   option lists WITH counts and folded the same way the filters match — or the
>   page would offer `RICHMOND` and `Staten Island` as two boroughs, which is the
>   defect `_norm_borough` exists to prevent, moved one layer up into the UI.
> - ⚠⚠ **`has_location` and `has_borough` did not reach the map** and had to be
>   added to `/get/capital/geojson` first. See the CLAUDE.md entry; the short
>   version is that `?has_location=false` listed 12,464 projects while the map
>   drew 4,560 pins for projects the list had excluded.
> - **The four `globStats` tiles are gone rather than repointed** (5,128 against
>   17,024), `Amount Over Budget` among them — the label this plan already refuses
>   to carry forward.

### 5.3 `/p/{fms_id}` → **Project profile**

Spine row + history + commitments + Dashboard funding + milestones (2023) +
Parks/SCA/climate panels when present. Sections, in order: header (agency,
sponsor, category, budget lines, vintage badges "in plan / schedule published
/ location"); **money** — see the ⚑ F box below, NOT a funnel; **schedule** (Dashboard phases with actual
dates; forecast completion; variance and reason from schedule history);
**budget over time** (history table, both sources, labelled); **commitments**
(CPDB lines); **milestones (Oct 2023)** if any; **Parks tracker** panel
(percent complete, funding sources, update) if `in_parks_tracker`; **climate**
ratings if `in_climate`; **map** if geometry; **related**: same budget line,
same agency, Council awards on its budget lines. Every empty section renders
its "not published" line, not nothing.

One template. `pureproject.blade.php` and `CapProjectsBuilder2024` go;
`/p/{id}` resolves through `fmsid.candidates` so `858DOIT5MYSM`, `DOIT5MYSM`
and `858 DOIT5MYSM` all land — verified against the live spine on 2026-09-05.

> ⚠⚠ **CORRECTION, 2026-09-05: AN FMS ID DOES NOT IDENTIFY A PROJECT, so the
> heading's `/p/{fms_id}` cannot be the whole route.** Measured over the
> 17,024-row spine, **1,160 ids are carried by more than one agency, covering
> 2,371 rows — 14% of the universe.** Within the current plan alone it is
> **24 ids / 48 rows**, which is the figure this section was written against
> and exactly why the problem was invisible: ⚑ B pulled the Dashboard and 2023
> tails into scope, and that is where the collisions live (308 ids / 620 rows
> in the Dashboard set alone).
>
> `maprojid` (`858DOIT5MYSM`) **is** unique — 12,929 distinct over 12,929
> non-null — but it exists only for current-plan rows, so it cannot be the key
> either. **`(agency_key, fms_id)` is the only thing unique across all 17,024**,
> which is what the spine is keyed on.
>
> So `/get/capital/project/{ident}` accepts any of the three spellings, and
> when the identifier is shared it returns the **choices** — agency, id,
> description, in-plan — and **never picks one**. Picking silently would show a
> reader one agency's project under another agency's id.
>
> ⭐ **RESOLVED 2026-09-06 — THE CANONICAL URL ID IS THE AGENCY-CONCATENATED
> FORM, and that is what the publishers themselves use.** Measured across every
> source: CPDB's published key `maprojid` carries the agency on **12,929 of
> 12,929** rows and is byte-identical to `agency_key || fms_id`; Climate
> Budgeting publishes `NNN id` on 259,331 of 259,491; the Parks tracker on
> 1,962 of 2,244. Only the Dashboard's `FMS ID` and CPDB's own internal
> `projectid` are bare — and Databook's LEGACY url was already `858DOIT5MYSM`.
> `agency_key || fms_id` is **unique across all 17,024 rows**, including the
> 4,095 with no `maprojid` because they sit outside the current plan.
>
> Matching it takes the rows unreachable by identifier alone from **2,371 to
> 1**: `EDC`+`SOLAR2` concatenates to `EDCSOLAR2`, which is also agency 856's
> bare id. The qualified reading wins there and 856's project stays reachable as
> `856EDCSOLAR2`. Verified end to end on a random sample: **250 of 250** resolve
> to exactly the right project.
>
> ⚠ It is a LOOKUP, not a parse — nothing decides where the agency code ends,
> which is the judgement that would reintroduce the 814-project truncation
> defect. And the spellings are tried in TIERS, not ORed: a form naming the
> agency outranks a bare one, or `856 110WLM` matches agency 856 by its
> qualified form and both agencies by the bare one and reports itself ambiguous
> to a caller who already said which agency they meant.
>
> **So `/p/{agency}{id}` is the canonical route.** A bare id still resolves when
> it is unique and returns choices when it is not.

> ⭐ **BUILT 2026-09-06** as `capitalproject.blade.php` (one template) plus
> `capitalprojectchoices.blade.php` (the ambiguous-id state). `pureproject.blade.php`,
> `orgproject.blade.php` and `CapProjectsBuilder2024` are no longer reached by
> `/p/…` and can be deleted once nothing else calls them. Deviations, each
> measured:
>
> - **The org shell is CONDITIONAL, and that is a bug fix rather than a style
>   choice.** 4,568 of 17,024 spine rows carry no `wegov_org_id`, and the old
>   action required `fetchOrg()` to succeed — `/p/111PO111-17`, a project in the
>   current plan, returned **404**. A project whose agency we cannot resolve now
>   gets a standalone page.
> - **`/get/capital/project/{ident}/geometry` now serves GeoJSON**, not the raw
>   WKT it served before. Nothing downstream reads WKT and there is no PostGIS
>   here; `modules/wkt.py` converts it and refuses any shape outside the two
>   measured across all 4,560 rows.
> - **Three panels §5.3 asked for needed their join measured first**: Parks
>   tracker (1,660 projects, 37 with several tracker rows — a list, never a
>   summary), Climate Budgeting (11,506 projects, latest vintage, one row per
>   budget line) and the retired 2023 milestones (9,102 projects, latest
>   publication only, labelled with its vintage).
> - **`related` is two blocks, not three.** Same budget line and Council awards
>   are built; "same agency" is not, because the agency link in the header already
>   goes to the agency's full project list and a second capped list of the same
>   thing would be the `by_vendor` defect for no gain.
> - **The Council-award block is `modules/budgetline`'s first consumer** — raw
>   join 0 rows, normalised 11,446 — and it states that an award names a budget
>   line rather than a project.
> - ⚠ **"Community board" was the wrong label** for 5,263 of the 8,373 populated
>   values, which name only a borough. Renamed and qualified.

### 5.4 Org profile → Capital Projects tab

Default table = spine `WHERE wegov_org_id = ?` (current plan). The 2023 table
becomes a collapsed *"Earlier plan (Oct 2023)"* block from history. The union
/ text-match path for non-agencies (#366) stays and reads the spine. Tiles
from `capital_program_stats (org)`. `section-coverage` note stays.

### 5.5 Districts → projects tab (the home for the Council-district view)

**Owner decision 2026-09-04: the Council-district view of capital projects
lives in the existing Districts section** — `/districts/cc` as the index and
`/d/cc-{id}-{slug}/projects` per district — not on a new route or a Council
page. Same for `cd`, `sd`, `nta`.

Spine joined through the rebuilt `{type}_idx` with a *how located* line
("312 projects by geometry, 41 by community board, 88 by Council award").
On `cc` districts the tab additionally carries a **Council capital awards**
table from `t474-a92g` (FY, sponsor → People page under ⚑ E, amount, budget
line, linked projects on that line). Tiles from `capital_program_stats
(cd|cc|sd|nta)`. The `/districts/cc` index gains a per-district capital
column (projects located, planned $) from the same stats rows so the index
itself is a citywide comparison, not just a list of links.

### 5.6 Budget documents: Types · Categories · Budget Lines · Commitments

Keep as views of OMB's documents (`capitalstrategy`, `capitalbudget`,
`capitalcommitmentplan`), with `capitalbudget` current again. Each budget line
page links to the spine's projects on that line via
`capital_projects.budget_lines`, replacing the taxonomy that lived only on the
dead table. Their stray 8-tile grids (no data URLs today) are removed or fed
from `capital_program_stats (budget_line|asset_category|ten_year_category|type)`.

> ⭐ **THE PHASE 1 GAP THIS DEPENDED ON IS CLOSED, 2026-09-06.** Neither
> dependency existed when Phase 1 shipped: the spine had **no budget-line
> column at all**, and the stats table's only category scope carried CPDB's
> coarse 3-value asset class. Both are now built.
>
> - `capital_projects.budget_lines` and `.project_types` are `text[]`, from
>   `capitalprojectscommitments`: **1,913 distinct budget lines** and **39
>   project types** over the 12,929 projects in the current plan, GIN-indexed.
>   Multi-valued because they are — 1-34 lines per project (mean 1.45).
>   ⚠ Attached by an aggregate-then-UPDATE, never a join into the spine's
>   INSERT: 41,277 commitment rows for 12,929 projects would have multiplied
>   the spine, which is #262/#278 in a new table. Verified 17,024 rows before
>   and after, twice.
>   ⚠ A project outside the current plan has none, and that is the honest
>   answer rather than a gap — the commitment plan is what assigns them.
> - Four stats scopes: `budget_line` (1,913) · `ten_year_category` (138) ·
>   `type` (39) · `asset_category` (3).
>
> ⚠⚠ **AND THE BARE SCOPE NAME `category` IS RETIRED, because two different
> things were called one.** CPDB's `typc` is a 3-value ASSET class (Fixed Asset
> · ITT, Vehicles and Equipment · Lump Sum). The Ten-Year Capital Strategy
> category is a **138-value** programme taxonomy, and it is the one the
> Categories page joins on. A scope named `category` serving 3 rows where a page
> needs 138 is one label with two definitions — the defect that already produced
> two different "Amount Over Budget" figures in this section.
> `/get/capital/stats/category/...` now **400s**; ask for the one you mean.
>
> ⚠ **The Categories page cannot be a straight repoint, and the numbers say
> why.** It is a HYBRID today: strategy figures from the live `capitalstrategy`,
> project counts joined from the RETIRED series at its last publication. Of the
> **185** categories the strategy publishes, the spine can serve **128**; 57
> have no project in the current plan, and 10 spine categories are absent from
> the strategy. The retired series matched 140 because it spans a longer
> history. So the page keeps all 185 strategy rows, shows counts on the 128, and
> STATES the coverage — the same denominator discipline as the rest of the
> section. Silently dropping 57 categories, or showing them as zero, would both
> be wrong.

**SCA / DOE** appears as a panel on the Overview coverage section and on the
DOE org tab ("DOE's capital program has no published FMS-level schedule; the
School Construction Authority publishes phase schedules by building —
N projects, $X"), linking to the existing school pages. No FMS join is
claimed.

### 5.7 Home, briefing, hearing brief

Home card reads `capital_program_stats.projects`. Briefing's capital feed
reads Dashboard schedule-history changes in the latest period + projects new
to the current plan + Parks updates, not 2023 milestones. Hearing brief's
capital query is rewritten against the spine (its column names were wrong).
The MOCK fallback's fabricated capital items are deleted.

---

## 6. MCP and public API

- MCP `search_capital_projects`, `get_project_details`, `get_agency_projects`
  read the spine; `get_project_milestones` becomes `get_project_schedule`
  (Dashboard phases + history) and keeps 2023 milestones as a sub-key.
  `docs/mcp_setup.md` "8,000+ projects" → served count. Audit (40 tools)
  re-pinned.
- Public API v1 gains `/api/v1/capital/projects`, `/projects/{fms_id}`,
  `/capital/stats`, all with `sources[]`.

---

## 7. Cutover order (each step verifiable alone)

1. **Pipeline first, read nothing new yet**: registry rows, `capitalbudget`
   reactivation, extractors, hooks, `fmsid`/`budgetline` modules, builders.
   Verify: every new table has rows, `[hooks] Running …` lines appear for each
   capital source, `capital_projects` count = 12,905 + tail, join rates match
   the measured ones (Dashboard 5,556, Parks 1,409, Climate 7,793).
2. **Endpoints**: `/get/capital/*` beside the old ones. Verify payload shapes
   and `sources[]` on every one; count reconciliation (spine count = list
   count = stats count; money reconciles to `sum(::numeric)` within 1e-4).
3. **Pages**: Overview, Projects, profile, org tab, districts, budget pages,
   home/briefing/brief. One PR per page family, each verified on the
   **rendered** page (the rule every defect in this section's history
   demanded).
4. **Retire**: the ~40 direct readers of `dollarscomp`, the map cache, the
   `pstats-*` families, orphan views (`capitalA`, `projectsA`, `orgprojectA`),
   `pureproject`, both `CapProjectsBuilder*`, minor-projects route, the
   unrendered top-10 lists. Redirects: `/capital/minor-projects/*` → `/p/`.
5. **Drop columns/tables**: `GEO_JSON`/`LAT`/`LNG` from `dollarscomp`;
   `capitalprojectsdollars`, `cpdb_*`. Sitemap regenerated from the spine.

Owner reviews the deltas at each step (before/after counts, rendered pages),
per the working convention.

---

## 8. Guards

- No file outside `build_capital_history.py` may read
  `capitalprojectsdollarscomp` (AST-literal scan, asserts it scanned >40
  files).
- Every source table in §3.2 has the spine rebuild in `POST_INGEST_HOOKS`.
- `fmsid.norm` round-trips every observed id shape (fixture of ~30 real ids
  across 7 sources); `budgetline.norm` likewise.
- Money columns in the spine and history end in `_usd`; no `× 1000` outside
  the history loader.
- Spine count == list count == stats `projects`; stats money reconciles to an
  exact `sum(::numeric)` within 1e-4 (the #294 lesson: counts alone pass while
  money is wrong).
- Every `/get/capital/*` payload carries a non-empty `sources[]`.
- The Overview template reads only keys the stats endpoint serves (the
  controller-seam guard from the Digital Services rebuild).
- Extractor refuses 0 records and a >50% drop.
- Positive test on each district crosswalk (`cc` and `sd` must have >0 rows
  for a known district) — an empty crosswalk was the silent defect.

---

## 9. Phasing and rough size

| phase | scope | size |
|---|---|---|
| 1 Pipeline | registry, reactivation, `fmsid`/`budgetline`, geometry tables, spine + history + stats builders, hooks, indexes, Parks extractor | the largest; ~2 PRs on the api |
| 2 Endpoints | `/get/capital/*`, MCP re-point, API v1 | 1 PR |
| 3 Pages A | Overview + Projects list/map + profile | 2 PRs |
| 4 Pages B | org tab, districts (+ Council awards), budget pages, home/briefing/brief | 2 PRs |
| 5 Retire | readers, views, columns, tables, sitemap, redirects | 1 PR |
| 6 Optional | DDC ArcGIS extractor, SOGR needs, capital cashflow, climate detail page | as wanted |

Climate Budgeting and Council awards are in Phase 1 as registry rows because
they cost nothing to ingest; their **pages** are Phase 4/6.

---

## 10. Open questions (⚑) — restated

- **A** 2023 series: history-only (assumed), or also visible in default tables,
  or dropped.
- **B** Universe: current plan only, or include the 261 + 52 dropped/orphan
  ids as a flagged tail (assumed).
- **C** Non-Socrata feeds: Parks JSON and DDC ArcGIS in scope via extractors
  (assumed), or Socrata-only.
- **D** Navigation: keep six URLs with an Overview swapped in (assumed), or
  regroup (Overview · Projects · Agencies · Districts · Budget).
- **E** Council member attribution on awards, linked to People (assumed yes).
- Not asked, decided here unless told otherwise: DuckDB spatial at build time
  (no PostGIS in the databook Postgres; the FDNY precedent works); dollars at
  source in every new column; tri-annual sources polled daily; Parks extractor
  daily.
