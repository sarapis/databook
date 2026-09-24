# Capital Projects section — review against NYC Open Data (2026-09-03)

A fresh look at what the City publishes about capital projects, how Databook
uses it, and what would improve the section. Every figure below was measured on
2026-09-03 against Socrata, prod Postgres, or the rendered site; nothing is from
memory. This is a review, not a plan — nothing here has been built.

## 1. What NYC publishes today

There is no single source for the capital program. Five families, each with a
different grain, and the FMS project id is the only spine between them.

| family | datasets | grain | current? | what only it has |
|---|---|---|---|---|
| **DCP Capital Projects Database (CPDB)** | `fi59-268w` projects (12,929), `djxg-kcfi` commitments (41,277), `h2ic-zdws` points (2,776), `9jkp-n57r` polygons (1,784) | one FMS project, one planned-commitment line | yes — `ccpversion fisa_2026`, updated 2026-08-24, tri-annual | the whole Commitment Plan at project grain; planned → adopted → allocated → committed → spent per project, city vs non-city; `spent_total_checkbooknyc`; geometry for 35% of projects |
| **Mayor's Office of Operations Capital Projects Dashboard** (Local Law 37/2020) | `fb86-vt7u` budget+schedule, `gyhf-rsr3` spend by FY, `95tx-snak` schedule history, `qj5n-h5qp` budget history | reporting period × FMS id (× agency project id) | yes — 10 snapshots 202305→202605, updated 2026-07-15 | **current phase, actual design/procurement/construction dates, forecast completion, variance and reasons, budget history back to 2006** — for 5,608 FMS ids (43% of CPDB), 0% DOE/SCA, 0% OTI |
| **OMB budget documents** | `2cmn-uidm` commitment plan (May 2026), `46m8-77gv` capital budget (Adopted FY27, Jul 2026), `b37a-3faw` ten-year strategy (Apr 2025), `8u85-k342` commitment **actuals** (FY2002→FY2025), `4utb-pisg` funding sources, `4xfc-mzbg` monthly capital cashflow | budget line / agency / citywide | yes | actuals vs plan (the "commitment rate"), financing, monthly cash |
| **Agency trackers** | Parks tracker feed (2,244 projects, all geocoded, phase % complete, funding sources); SCA `2xh6-psuq` schedules + `8586-3zfm` sites (BBL/council district); DDC ArcGIS (164 live projects, geometry); DOT reconstruction `97nd-ff3i` | agency-specific | Parks feed yes (⚠ its Socrata mirror `4hcv-tc5r` held **0 rows** today); SCA yes; DDC Socrata `3ss8-m844` stale since 2023 but ArcGIS current | the only schedule data for DOE ($26.7B of CPDB); per-phase % complete; who funded what |
| **Cross-cutting** | `c99a-c5ux` Climate Budgeting (259K rows, every capital project rated for climate alignment, joins CPDB on 99.9% of ids); `t474-a92g` Council capital awards by member and district (FY19–26); `vck7-ujai` State of Good Repair needs; `vn4m-mk4t` CB budget requests | project / award / asset | yes | the only capital dataset with **council district** (Council awards); demand side; unfunded needs |
| **Retired** | `wa2y-rh4b` Capital Project Detail Data – Dollars and `s7yh-frbm` – Milestones | pub date × project (× task) | **frozen at 2023-10-26**; OMB: "replaced by the Capital Projects Dashboard" | the only milestone-level original-vs-current dates that ever existed; 2019–2023 history |

Id spellings differ everywhere: CPDB `maprojid` is agency code + id with no
separator (`850GKOH15-01`), the Dashboard and DDC use the bare id, Parks and
Climate Budgeting use agency code + space + id (`846 P-405VITO`). Budget lines
come in four punctuation styles. Any join needs one normaliser.

Measured joins: 99.1% of Dashboard FMS ids exist in CPDB; Parks feed → CPDB
1,409 of 1,867; DDC ArcGIS → CPDB 157 of 164; Climate Budgeting → CPDB
7,793 of 7,798.

## 2. How Databook uses it — findings

### 2.1 The section is built on the retired series, and says so in one place

`capitalprojectsdollarscomp` (the retired OMB Detail Data, last publication
**2023-10-26**, `is_active=false`, never ingested by the scheduler) is the
source for: the `/projects` list and map (5,145 rows, overlay text
"Loading 5,000+ capital projects"), the four tiles on `/projects`,
`/projects/capital` and `/procurement`, the home page project count, the
default table on every agency's Capital Projects tab, every district's
projects tab, all four MCP capital tools, the sitemap, and the home-page
briefing's capital feed. Only the org tab (#366, and Hub task `dbc5aeac`)
discloses that the series ended.

Meanwhile the live successor data is already in the database and current:

| table | source | rows | as of |
|---|---|---|---|
| `capitalprojectslist` | CPDB projects | 12,929 | fisa_2026, ingested 2026-08-25 |
| `capitalprojectscommitments` | CPDB commitments | 41,277 | same |
| `capprojectsbudgetsandschedule` (+3 siblings) | Dashboard | 5,608 FMS ids in 202605 | ingested 2026-08-03 |
| `capitalcommitmentplan` | OMB | 59,077 | 2026-05-12 |
| `capitalcommitmentactuals` | OMB | 864 | FY2025 |

The live data is used only on the project profile page (Dashboard forecasts
and history, CPDB commitments), the org tab's second table, and global search.

### 2.2 The headline tiles do not reconcile and cannot be reproduced from live data

`/pipeline/globstats` serves Projects 5,128 · Original $90.7B · Current
$135.8B · Amount Over Budget $76.9B — all from the 2023 snapshot. Current minus
original is $45.1B, not $76.9B; "over budget" is `-sum(BUDG_DIFF)` over all
rows on the global tile but `WHERE BUDG_DIFF < 0` on the district tiles, so
two pages define the same label two ways. CPDB carries no original budget, so
these tiles have no live successor as defined; the Dashboard's budget history
does (first snapshot vs latest, per FMS id, for 5,608 projects).

### 2.3 Things that are silently empty or broken

- District capital tabs for **council** and **school** districts are always
  empty: `capitalprojects_cc_idx` and `capitalprojects_sd_idx` hold 0 rows
  (`cd_idx` has 8,107). No script in the repo creates any of the three.
- `/capital/minor-projects` calls `/get/mcapitalprojects/all`, which does not
  exist; the controller swallows the 404 and renders an empty table.
- The hearing brief's capital query (`mcp_server.py:3450`,
  `data_pipeline.py:1552`) names columns `capitalprojectslist` does not have
  (`MAN_AGENCY_NAME`, `SHORT_DESCRIPTION`, `TOTAL_PLAN_COMMTMTS`); wrapped in
  try/except, so every brief's capital section is empty.
- The home-page briefing reads `capitalprojectsmilestones` ±7 days; that table
  ends in 2023, so the live feed has 0 capital items (61 items, 5 sections,
  none capital). The MOCK fallback in `root.blade.php` contains six invented
  capital headlines with invented dollar figures; it renders only when the API
  fails or returns empty, but it exists.
- `globStats` still computes four top-10 lists daily (`most_expensive_list` is
  ordered by a TEXT column, so "$9,997K" ranks first); nothing renders them.
- Three orphan views (`capitalA`, `projectsA`, `orgprojectA`, 1,923 lines) and
  two orphan endpoints; category and budget-line pages render an 8-tile grid
  with no data URLs.
- "Help us locate projects — NYC's government doesn't publish the locations
  of capital projects (!?)" appears on four pages. It is no longer true: CPDB
  publishes points and polygons, Parks publishes lat/lon for every project,
  SCA publishes BBL/BIN.
- The Public API v1 has no capital endpoints at all.

### 2.4 Structure

The nav is Projects · Types · Categories · Budget Lines · Commitments ·
Capital, framed around OMB's four budget-process phases. The Types, Categories,
Budget Lines and Commitments pages are budget-document tables (budget-line
grain, tri-annual publications), and the only bridge from them to projects is
the normalizer's `wegov-project-types` taxonomy, which exists only on the
retired table. The project profile is the strongest page — it already merges
CPDB, Dashboard and retired history — but 6,606 of 12,929 projects (the ones
with no 2023 row) get the reduced `pureproject` page. Column sets drift
between the list, org and district tables (Current Budget / Budget Change %
vs Planned Cost / Budget Increase). No page states an "as of" for the plan
version or Dashboard reporting period except the profile's history table.

## 3. Ideas, in priority order

### Tier 0 — stop presenting 2023 as current (cheap, and overdue)

1. **Make CPDB the universe.** Re-base the `/projects` list, map, search,
   sitemap and MCP tools on `capitalprojectslist` (12,929 projects, $201.6B
   planned), joined to the Dashboard for phase/schedule where it exists
   (5,608) and to the retired series **as labelled history** where it exists
   (8,740). Map straight from CPDB points/polygons (4,560 mapped) instead of
   enriching the dead table. This also completes Hub task `dbc5aeac`.
2. **Replace the four tiles** with figures the live data can produce and the
   Overview rule this repo already uses (every figure served by an endpoint,
   linked, with an "as of"): projects · planned commitments · committed to
   date · spent to date (CPDB funnel); projects with a published schedule ·
   in construction (Dashboard); commitment rate FY2025 (actuals ÷ plan, from
   `capitalcommitmentactuals`, already ingested, used nowhere).
3. **Stamp every capital page** with the CCP version and Dashboard reporting
   period, the way the licence pages carry `as_of`.
4. **Fix the silent empties**: build the cc/sd crosswalks (point-in-polygon
   over CPDB geometry against the district boundaries we already serve), fix
   or remove minor-projects, fix the hearing-brief column names, and point the
   briefing's capital feed at Dashboard schedule-history changes and new CPDB
   projects. Delete the MOCK capital items or label the whole MOCK as demo.

### Tier 1 — a "program status" lens (the thing nobody else publishes cleanly)

5. **Program Overview page** that computes nothing and links everything,
   mirroring the Digital Services reorg: commitment plan vs actuals by agency
   and year (the classic "agencies commit ~60% of plan" chart); phase mix;
   schedule slippage (`variance_day` distribution, reasons where given);
   budget growth from Dashboard history; and a **coverage panel** stating
   which agencies have no schedule data (DOE, OTI, most of HPD) — the
   Comptroller's *Flying Blind* finding, shown from the data rather than
   asserted. Disclosing what the City does not publish is on-brand.
6. **Project life-cycle funnel on every profile**: planned → adopted →
   allocated → committed → spent from CPDB, with `spent_total_checkbooknyc`
   beside our own Checkbook figure, and the Dashboard phase timeline above
   it. Most of the fields are already fetched.
7. **Longitudinal per-project budget/schedule charts** from the 10 Dashboard
   snapshots (and the 14 retired publications for pre-2024), replacing the
   single-snapshot "Budget Change %".

### Tier 2 — geography

8. **Council-district capital tab** from `t474-a92g` (member items by district
   and sponsor, FY19–26) plus the spatial join in idea 4. It is the only
   capital dataset that names council members — link them to People pages.
9. Adopt CPDB's geometry directly and show mapped share honestly ("4,560 of
   12,929 projects have a published location") instead of the volunteer-
   locating copy.

### Tier 3 — agency trackers as panels

10. **Parks**: ingest the Parks JSON feed (not the empty Socrata mirror) and
    render phase % complete, projected/adjusted/actual dates, funding sources
    and the plain-language update on the 1,409 matching profiles.
11. **SCA for DOE**: the $26.7B of DOE capital has no Dashboard schedule; we
    already ingest `scacapitalprojectschedules` and `scaactiveprojects`
    (geocoded, with council district). Surface them in the Projects section,
    not only on school pages.
12. **DDC ArcGIS** live geometry and phase for 164 projects (CPDB already folds
    it in; a direct feed would be fresher).

### Tier 4 — new datasets worth ingesting

13. **Climate Budgeting** (`c99a-c5ux`): every capital project rated for
    GHG mitigation, flood and heat resiliency, with vulnerability indexes.
    Joins CPDB on 99.9% of ids. Nobody surfaces this at project grain.
14. **State of Good Repair needs** (`vck7-ujai`): asset-level unfunded needs,
    the demand side the plan does not show.
15. **Monthly capital cashflow** (`4xfc-mzbg`): actual vs plan by department,
    the only monthly actuals series.

### Tier 5 — hygiene

16. One FMS-id normaliser (bare / agency-concatenated / agency-space) and one
    budget-line normaliser, in `modules/`, used by every join.
17. One column set for the project table across list, org and district pages.
18. Remove the orphan views, endpoints and the unrendered top-10 lists; fix
    the `capitalbudget` registry entry (inactive, one publication behind the
    Adopted FY27 budget on Socrata).
19. Public API v1 and MCP: expose CPDB + Dashboard, retire the dollarscomp
    readers.

## 4. Things to keep

- The project profile's merge of CPDB, Dashboard and retired history is the
  right shape; the rest of the section should converge on it.
- The org tab's union approach (#366) — "in 2026 plan / in 2023 series" as a
  visible column — is the correct way to carry the retired data forward.
- The Checkbook "Capital Contracts" spend-by-year chart on `/procurement` is
  sound and current.
- Budget-line and strategy pages are legitimate views of OMB's documents;
  they just should not be the primary way in.
