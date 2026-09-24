# Capital section — open issues, triaged

Raised by the owner while reviewing the local build on 2026-09-08. Every figure
here was measured against the running stack or a query on that date; where I did
not verify something, it says so. **Nothing below is built.** This is a triage
list, not a plan — it records what was observed, what the cause actually is, how
wide it reaches, and what I would do.

State when this was written: branch `feat/capital-spine`, three commits
(`ec569c8`, `1485127`, `c7583c6`), pushed, PR #376 open and unmerged. Nothing
deployed anywhere.

---

## 1. The datasets accordion is empty — and it deletes its own rows  ✅ FIXED

**Observed:** on `/projects`, *"We're using normalized data from ___ datasets
containing ___ records"* has both counters blank.

**It is worse than blank.** The page renders six real dataset rows server-side;
JavaScript then deletes every one of them. Measured on the live page: `var
datasets` arrives populated, and after load `datasets.length === 0` and the
table reads *"No data available in table"*.

**Cause.** `loadTableStat()` calls `/get/pstats-records_no/{table}` per dataset.
**That route has never existed** — `git log -S` over the whole repo history finds
no commit that added or removed it, and it returns 404 for every table, including
`contracts` and `crol`. On a non-200 `fapireq` hands back `[]`, and the `else`
branch runs `datasets.splice(i,1)` + `dsstats_table.row(i).remove()`. Six 404s,
six rows deleted.

**Not a regression from the rewrite.** The identical URL is in the controller at
`ed9e393`, before any of this work, and the caller dates to the 2026-02-11
initial commit.

**Blast radius:** six controller call sites use the broken plain form —
`/projects`, `/projects/capital`, `projectsA`, the org projects section — plus
`/get/pstats-records_no-byprj/...` on the project page, which also 404s.

⚠ **Why it survived:** the three `-by_*` variants DO work (200), so
`/projects/types/{slug}`, `/projects/categories/{slug}` and
`/projects/budget-lines/{code}` have working accordions, and the feature looks
alive on the pages most likely to be spot-checked.

⚠⚠ **CORRECTION, 2026-09-08 — I said "only the un-suffixed form is missing" and
that was wrong.** Measured while fixing it: **three** variants 404, not one.

    /get/pstats-records_no/{tbl}                      404   6 call sites
    /get/pstats-records_no-byprj/{tbl}/{prjId}        404   1 (the project page)
    /get/districts/pstats-records_no/{type}/{id}/{t}  404   2 (district pages)

Only `-by_prjtype`, `-by_category` and `-by_budgetline` answer. **This fix covers
the plain form only** — the district and byprj variants are filtered counts that
would each need a real endpoint, and they are still broken.

**Proposed fix — no new endpoint needed.** `/pipeline/registry` already serves
`estimated_rows` per table for 75 tables, and it matches `count(*)` **exactly**
on all six capital tables (12,929 / 41,277 / 56,525 / 288,446 / 53,495 /
22,464). Render the counts server-side with the rest of the page: one call
instead of six, no route to keep alive, no blank-then-populate flicker.

⚠ **And stop deleting rows on failure regardless.** A failed request is not an
empty dataset — the `fapireq` lesson already recorded in this repo. Current
behaviour turns one missing route into *"we use no datasets at all"*, which is
the most misleading possible outcome on a page whose whole claim is that it
measures.

---

## 2. Put the map top-right on the project profile  ✅ FIXED

**Asked for:** the map in the top right, closer to the previous design.

**Confirmed against the old template.** `orgproject.blade.php` — the page most
projects used before the rewrite — is `col-md-8` content + `col-md-4` map on the
right (lines 100 and 269), with the map container carrying an inline
`style="float:none;"`.

⚠ That inline override is the same `#map_container { float: right; }` rule
(`style.css:1509`) that made the rebuilt map **0px wide** in `c7583c6`. Whatever
shape the map ends up in, it needs a declared width, and the guard
`test_the_map_container_declares_a_width_against_the_float_rule` currently pins
the `.row` + `col-12` form. **That guard has to move with the markup** — it is
pinning a specific wrapper, so a two-column layout will fail it until it is
updated. That is the guard working, not an obstacle.

**Open question for the owner:** at `col-md-4` the map is ~450px wide on a
1400px viewport. The polygons are real footprints — the Gravesend Bay sewer
network spans ~2.5km — so a narrow column zooms them small. Full width is more
legible for polygons; top-right is more consistent with the old design and puts
the money table beside it. I would go **top-right at `col-md-5`, full width
below `md`**, but this is a design call, not a measurement.

---

## 3. Hide the sections that have no data  ✅ FIXED

**Asked for:** don't render sections like "NYC Parks project tracker" when the
project has none.

⚠⚠ **THIS REVERSES A RECORDED DECISION, AND THE REVERSAL IS FINE — but it must
be written down, or a later reader will "fix" it back.** `docs/CAPITAL-SECTION-PLAN.md`
§5.3 says *"Every empty section renders its 'not published' line, not nothing."*
The reason was real: an absent section and an empty one are indistinguishable to
a reader, and here the absence is often the finding (NYC publishes a schedule for
half these projects and a location for a quarter).

**What makes hiding them safe is issue 4** — the absence stops being invisible
because it moves into one table that accounts for every source. Hiding sections
WITHOUT that table would re-introduce exactly the defect §5.3 was guarding
against. **The two ship together or not at all.**

**Scale of the problem being solved**, measured over the spine: a project outside
the current plan renders **nine** consecutive "not published" paragraphs. Even a
well-covered project usually has 2–4.

---

## 4. Make "Where these figures come from" account for every source  ✅ FIXED

**Asked for:** list all the data tables in the capital section, with a column
saying whether this project appeared in each.

This is the right shape, and it is what makes issue 3 safe. Today that table
lists only the two or three sources that *did* contribute — so a reader cannot
tell a source that has nothing to say about this project from one Databook does
not read at all.

**Measured coverage across all 17,024 spine projects**, 2026-09-08 — these are
the candidate rows:

| source | table(s) | projects |
|---|---|---:|
| Capital Commitment Plan (CPDB) | `capitalprojectslist` | 12,929 |
| CPDB planned commitments | `capitalprojectscommitments` | 12,929 |
| Climate Budgeting | `climatebudgeting` | 11,506 |
| Milestones (2023, retired) | `capitalprojectsmilestones` | 9,102 |
| Project detail (2023, retired) | `capitalprojectsdollarscomp` | 9,081 |
| Capital Projects Dashboard | `capprojectsbudgetsandschedule`, `capprojectsbudgetandspend` | 8,483 |
| Dashboard budget history | `capprojectsbudgetspendhistory` | 5,947 |
| Published location | `capital_project_geometry` (CPDB points/polygons) | 4,560 |
| Dashboard schedule history | `capprojectsschedulehistory` | 4,018 |
| Council capital awards *(via budget line)* | `councilcapitalbudget` | 3,725 |
| NYC Parks project tracker | `parkscapitaltracker`, `parkscapitalfunding`, `parkscapitallocations` | 1,660 |

⚠ **The three Parks tables are ONE row, not three** — measured, they cover the
identical 1,660 projects, so listing them separately would imply three
independent confirmations of the same fact.

⚠⚠ **THE COUNCIL AWARDS ROW IS A DIFFERENT KIND OF CLAIM AND MUST SAY SO.**
Every other row means *this project appears in that table*. The Council publishes
against a BUDGET LINE, so its row means *an award names a line this project is
funded from* — which is not the same thing and is already stated on the section
itself. A yes/no column that quietly mixes the two grains would be a second
"Amount Over Budget": one label, two definitions.

⚠ **Tables that are NOT project-keyed must be excluded, not shown as "no".**
`capitalstrategy` is keyed on project TYPE; `capitalbudget` and
`capitalcommitmentplan` on budget line; `capitalcashflow`,
`capitalcommitmentactuals` and `capitalfundingsource` carry no project or line
key at all. Rendering "did not appear" against those would tell a reader the
City omitted this project from a table that has no notion of projects.

⚠ **One correction to my own first measurement, recorded because the shape of the
error matters more than the number.** I first read
`capprojectsbudgetspendhistory` as covering **0** projects and nearly wrote it up
as a source that ingests nothing. The probe queried `source='dash_budget'`; the
builder writes `dash_money`. The real figure is **5,947**. A join on a key that
does not exist returns zero, and zero reads exactly like a finding.

⭐ **CORRECTION, 2026-09-08 — the cost concern was unfounded, and the reason is
worth keeping.** I wrote that this needs ten `EXISTS` per page against 259k- and
497k-row tables, and floated precomputing a `sources` column in the builder.
**Not one extra query is needed.** Every value is already in hand when the page
is assembled: three flags on the spine row (`in_current_plan`, `in_dashboard`,
`in_cpdd_2023`) and five panels the endpoint already fetches to render the
sections. So the table is a restatement of what the page already knows — which
also means it **cannot disagree with the sections it summarises**, because they
are the same values. A guard bans `_select` inside it.

---

## 5. "Period" in *Budget and schedule over time* should read as a date or a month  ✅ FIXED

**Asked for:** turn `20231026` / `202405` into a date or month/year as
appropriate.

**It is exactly two shapes, with no exceptions** — measured over all 205,503
history rows: **0 rows** have a period that is neither 6 nor 8 characters.

| source | shape | distinct | range | reads as |
|---|---|---:|---|---|
| `cpdd` (2023 series) | `YYYYMMDD` | 14 | 20190425 – 20231026 | a publication **date** → *25 Apr 2019* |
| `dashboard` | `YYYYMM` | 10 | 202305 – 202605 | a reporting **period** → *May 2023* |
| `dash_sched` | `YYYYMM` | 10 | 202305 – 202605 | same |
| `dash_money` | `YYYYMM` | 64 | 200609 – 202605 | same |

All 14 `cpdd` values match `^\d{8}$`.

⚠⚠ **"AS APPROPRIATE" IS THE WHOLE POINT, AND THE TWO ARE NOT INTERCHANGEABLE.**
The 2023 series publishes on a specific day; the Dashboard publishes a
**reporting period**, and its months are exactly **01, 05 and 09** — three
editions a year, the Commitment Plan cadence. Rendering `202405` as *1 May 2024*
would invent a precision the City did not publish. So: full date for `cpdd`,
month + year for the three Dashboard sources.

⚠ Format from the **source**, not from the string length. Length happens to be a
perfect proxy today (8 vs 6) and would silently mis-format the day a source
changes its cadence. Keying on `source` — which the payload already carries —
says what is meant. A guard should assert the two agree on every observed value,
since the proxy failing silently is the whole risk.

⚠ The row also needs the source column to stay legible: *"Jan 2024"* under a
column headed **Period** next to *"26 Oct 2023"* is only coherent because the
Source column says which publication each came from. Do not drop it.

---

## 6. Gantt / timeline visuals — B (slippage) ✅ BUILT; A and C still open

**Honest answer: no, I have not explored this.** The rebuild has been about
getting the right numbers onto the page; nothing on any capital page is drawn as
a chart today. Here is what the data would actually support, measured
2026-09-08 — this is a feasibility note, not a design.

**The dates are plottable.** Every Dashboard phase date is `MM/DD/YYYY` with
**0 exceptions** (3,210 populated `actual_design_start`), and so is every
`forecast_completion`.

| candidate | data behind it | projects |
|---|---|---:|
| **A. Phase gantt** — design / procurement / construction bars from the Dashboard's actual dates | `actual_*_start` / `actual_*_end` | **2,493** have ≥2 phase starts; 3,288 have any phase date |
| **B. Slippage line** — how the forecast completion moved across reporting periods | `capital_project_history.forecast_completion` | **2,319** have more than one distinct forecast |
| **C. Task gantt** — the 2023 milestone tasks, original vs as-published | `capitalprojectsmilestones` | 9,102, avg **6.6** tasks, max 30 |

⭐ **B is the one that says something the tables cannot.** A phase gantt restates
dates already in the Schedule table in a prettier form; a slippage line shows the
City's own completion forecast moving — for 2,319 projects it moved more than
once, and `variance_days` + `delay_reason` are already served beside it. That is
a finding, not a re-render.

⚠ **C is retired data** (the series NYC stopped publishing 2023-10-26). Drawing
it as a gantt beside a live schedule is exactly the "reads as current" risk
issue 3 is about — it would need the same vintage labelling the table already
carries, and arguably more, because a chart reads as *now* far more strongly than
a dated table does.

⚠ **Coverage has to be on the chart, not in a caption.** A phase gantt covers
3,288 of 17,024 projects. On the 13,736 without one the honest output is the
absent-section treatment from issue 3, never an empty axis.

⚠ **Never draw a bar from one endpoint.** A phase with a start and no end is
common here; guessing "to today" would render an in-progress claim the City did
not make. Show it as an open-ended marker or not at all.

⚠ **Repo convention:** charts are Chart.js via `app/public/js/db-charts.js`
(`DBChart.apply`, navy/accent palette, Public Sans). **Any
`maintainAspectRatio:false` canvas MUST sit in a fixed-height `.db-chart-body`
wrapper or it grows unboundedly** — #61, already paid for once.

**My recommendation:** B first, on the project profile, where it is cheap and
uses data already in the payload. A second, if the phase table proves hard to
read. C only if someone wants the 2023 material foregrounded, which I would not
do by default.

> ⭐ **B IS BUILT, 2026-09-08 — and measuring the series first was load-bearing.**
> **Two sources publish `forecast_completion` and they are NOT the same series:**
> `dashboard` (22,373 rows) and `dash_sched` (19,911) **disagree on 371 of 17,764
> shared (project, period) pairs**, and 4,609 periods carry a forecast in
> `dashboard` alone. Drawing both would put two 98%-identical lines on one chart
> and invite a reader to read the 2% as a finding about the project rather than
> about the two tables.
>
> The chart reads **`dash_sched`** — the schedule-history publication, and the
> only one carrying `variance_days` and `delay_reason`, which is what turns a
> moving line into an explanation. Cost: 2,195 projects instead of the union's
> 2,319, so 124 get no chart; the sources table already tells them why.
>
> - **The axis is months later than the first published forecast**, not a date
>   axis — Chart.js needs a date adapter for that, and the actual date belongs in
>   the tooltip beside the City's own stated reason, where it reads better.
> - ⚠ The baseline is **the first forecast published, not an original target** —
>   the Dashboard's history begins May 2023. The note says so, because "33 months
>   late" against an unstated baseline is a different and larger claim.
> - ⚠ **Two distinct forecasts are required, not two rows.** A project
>   republished unchanged across ten periods has a flat line and nothing to say.
> - ⚠ A forecast can move **earlier**, and `direction` names it rather than
>   leaving a reader to infer it from a negative number under a heading.
> - It costs no extra query — it reads history rows the endpoint already fetched.
>
> Worked example (`850GKOH15-01`): **33.4 months later** over 10 periods, and the
> line visibly comes *back* about seven months in late 2025 before jumping again
> — movement no row of the table shows.

---

## Status, 2026-09-08

**1, 2, 3, 4, 5 and 6B are done** — see the ✅ headings above. What remains from
6 is the phase gantt (A) and the 2023 task gantt (C), both of which I would leave
until someone wants them; the slippage chart is the one that says something the
tables do not.

⚠ **Item 2's `col-md-5` was my call, not the owner's** — the alternative was
`col-md-4`, matching the old layout exactly, which zooms a 2.5km polygon to
illegibility. Easy to change; the guard now accepts any `col-*` class rather than
pinning one width.

⚠ **Item 3 is the reversal of §5.3, and the compromise is worth knowing:** the
hidden sections are NAMED in one sentence above the sources table, rather than
silently dropped. A project outside the current plan went from nine consecutive
"not published" paragraphs to three sections plus that line.

⚠ While fixing 5 I found the same defect one column over: the history table
printed the raw `source` key (`cpdd`, `dash_money`) as copy. A reader cannot know
`cpdd` is a series NYC retired in 2023. Now served as `source_label` beside the
key, on the same rule as the placement methods.

## Suggested order

1, 4, 5 are independent of each other. **3 must not ship without 4.** 2 is
cosmetic and touches a guard. 6 is a proposal, not a defect — it needs a design
decision before any of it is worth building.

Nothing here blocks the throwaway preview on the box — that can go up on the
current state, and these become the second pass.
