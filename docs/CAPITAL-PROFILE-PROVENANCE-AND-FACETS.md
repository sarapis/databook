# Two open questions on the capital project profile

Owner, 2026-09-08: *"Where is the original table showing the datasets being
displayed on the page? Looks like 'Where these figures come from' has replaced
it? I want a good plan to unify the design because the old one is a pattern
throughout the site."* and *"Where and how are project-types and categories
represented on this profile? I currently don't see them."*

Everything below is measured on the local stack, 2026-09-08. Nothing is built.

---

# Part 1 — the datasets accordion and the sources table

## What is actually true

**The sources table did not replace the accordion. The rewrite dropped it.**
Measured: `/p/850GKOH15-01` contains **0** occurrences of `dsStatsTable` or the
accordion copy. `/projects` still has it, server-rendered — *"We're using
normalized data from 6 datasets containing 475,136 records."*

The accordion is a real site-wide pattern: **15 views** carry it —
`projects`, `projectsA`, `capital`, `capitalA`, `categoryA`, `prjTypeA`,
`prjTypesA`, `budgetLineA`, `mProjects`, `orgproject`, `orgprojectA`,
`distsection`, `distprojectsection`, `schools`, `schoolSection`. 13 of the 15
hydrate the counts by JS (`loadTableStat`); only `/projects` renders them
server-side, which was this phase's fix.

## ⚠ They answer DIFFERENT questions, and that is why one did not replace the other

| | datasets accordion | Where these figures come from |
|---|---|---|
| scope | **the page type** — identical on every project profile | **this project** — different on every one |
| question | what data feeds this kind of page | which publications carry THIS project |
| columns | Name · Section · Description · Last Updated · Dataset Records | Publication · Publisher · In this source? · Version · Table |
| absences | not represented — a dataset with no rows for this project still lists its full record count | **the point** — 9 of 11 here, and the 2 absent are named |
| vintage | Last Updated (when we ingested) | Version (**which plan edition the figure came from**) |
| links out | dataset profile pages | none today |

The old `/p/` page's accordion listed **4** datasets
(`capitalprojectsdollarscomp`, `capitalprojectsmilestones`,
`capitalprojectslist`, `capitalprojectscommitments`). The sources table lists
**11**. So the overlap is 4 of 11 — real, but neither is a superset.

⚠⚠ **The two must not be merged into one table.** A dataset's total record
count and this project's presence in it are different claims, and a single row
carrying both invites "475,136 records" to be read as being about this project.
That is the same defect class as the four `globStats` tiles this section already
removed for publishing 5,128 against the spine's 17,024.

## The plan: one component, two modes, one endpoint

**A. Extract the pattern into a Blade component** — `<x-db.data-provenance>`.
It renders the accordion shell (the `social_btn` button, the collapse, the
table) from a served array. 15 views currently hand-roll it; 13 also hand-roll
`loadTableStat`, which is why the six `/get/pstats-records_no/*` 404s on every
page carrying it went unnoticed for so long.

**B. Two modes, because there are two questions:**

- `mode="page"` — today's accordion. *"We're using normalized data from N
  datasets containing M records."* Unchanged copy, unchanged columns, so the
  other 14 pages are a drop-in swap.
- `mode="record"` — the profile's table, as a THIRD and FOURTH column on the
  same rows: `In this record?` and `Version`. Same shell, same accordion, same
  place on the page. The button copy becomes *"We're using normalized data from
  11 datasets. This project appears in 9 of them. Click here to learn more."*

⭐ **That is the unification: one shell, one place on the page, one visual
language — with the record-scoped columns appearing only where a record exists
to scope them to.** A reader who has learned the accordion on `/projects` finds
the same thing on `/p/{id}`, and the extra two columns read as more detail, not
as a different component.

**C. One endpoint owns the row list.** `_source_coverage` in
`routers/capital.py` already builds the 11-row list with publisher, tables,
grain, retired flag, version and presence. The page-scoped mode needs
`description` and `last_updated` and `record_count`, which `/get/datasets/all`
and `/pipeline/registry` already serve (`ProjectsDatasets::rowCounts()`, built
this phase, reads the registry). Join them at the endpoint, never in Blade —
two Blade files composing the same list is how the 15 hand-rolled copies
happened.

⚠ **Keep `Table` and `Publisher`.** They are the two columns the accordion
lacks and the reason the profile's version is trustworthy: a reader who wants
to check a figure needs to know which table to query and whose publication it
came from.

⚠ **The record-mode row must keep saying "Not published" rather than 0.** A
dataset with 205,503 rows and none for this project is not an empty dataset.

**D. Order of work.** Component first, `/projects` migrated to it (already
server-rendered, so it is the safe pilot), then the profile, then the other 13.
The 13 are the risky ones — each hand-rolls `loadTableStat` slightly
differently, and one of them (`orgproject`) is a page this section is retiring
anyway.

**Guards.** No view may declare `id="dsStatsTable"` outside the component; the
component's page mode must not render presence columns (a page-scoped table
claiming a record is present is the merge this plan forbids); the record mode
must render a row for every source, present or not, and the existing
`test_the_source_table_accounts_for_every_project_keyed_source` must keep
passing against the component's output.

---

# Part 2 — project types and categories

## They ARE on the page — measured

All three are in the `About this project` table today, as **plain text**:

| row | value on `850GKOH15-01` | has a page? |
|---|---|---|
| Asset category | `Fixed Asset` | ❌ `/projects/categories/fixed-asset` → **404** |
| Ten-Year Strategy category | `UTILITY RELOCATION FOR SE AND WM PROJECTS` | ✅ **200**, 55 kB |
| Project type | `Environmental Protection-Equipment, Highways, Sewers, Water Pollution Control` | ❌ all four → **404** |
| Budget line | `EP-0007, HW-0001K, SE-0944, WP-0169, WP-0170` | ⚠ linked, and **all five 500** |

So the answer to *"where are they"* is: they are there, and they are the only
multi-valued facets on the page that are **not** navigable — while the one that
is linked goes to an error.

## ⚠⚠ TWO DIFFERENT THINGS ARE CALLED "PROJECT TYPE", AND LINKING THEM WOULD BE WRONG

This is the `category` defect this section already documents, on a second
column. Measured:

| | vocabulary | size | examples |
|---|---|---:|---|
| spine `capital_projects.project_types` — **what the profile shows** | CPDB budget-line family | **39** | Parks and Recreation (2,968), Highways (855), Sewers (444), Aging (95), MTA Bus Company (3) |
| `capitalstrategy."Project Type Description"` — **what `/projects/types/{slug}` keys on** | Ten-Year Strategy work type | **236** | Access for the Handicapped, Acquisition of Real Property, Animal Care, Automotive Equipment |

**Overlap: 5 of 39** — `Brooklyn Public Library`, `Courts`, `Fire Department`,
`Housing Authority`, `New York Public Library`. Every one is a naming
coincidence between an agency-shaped spine value and a work-type-shaped
strategy value.

⭐ So linking the profile's "Project type" row to `/projects/types/{slug}` would
**404 on 34 of 39 values and, on the other 5, land a reader on a page about a
different thing that happens to share a name.** The second half is worse than
the first: a 404 tells you something is missing, a plausible wrong page does
not. **Do not link this row until the vocabularies are reconciled.**

⚠ And the spine's own label is misleading: 39 values that are mostly agency and
asset-family names ("Parks and Recreation", "Highway Bridges", "Water Mains,
Sources and Treatment") are not what a reader understands by "project type".
CPDB calls the column that; we do not have to.

## What to do, in order of cost

1. **Fix the budget-line 500 first, or unlink it.** Five links on every project
   profile with a budget line lead to
   `Undefined index: wegov-prjtype-name (View: budgetLineA.blade.php)`. It is
   documented as pre-existing and a Phase 4 surface — but the profile now
   *sends readers there*, which it did not before. Either fix `budgetLineA` or
   drop the anchor until it is fixed. **A link to a 500 is worse than text**,
   the same call already made for `sd` district badges.

2. **Link the Ten-Year Strategy category.** It is the one facet that works
   today: `route('prjStratCategory', ['cslug' => Str::slug($v)])` → 200. One
   line, immediate value, and it is the 138-value taxonomy this section already
   established as the useful one.

3. **Rename the "Project type" row to what it is** — `Programme` or
   `Budget-line family`, with the 39-value vocabulary stated — and leave it
   unlinked, with a comment recording the 39-vs-236 measurement so the next
   reader does not "fix" it by adding the link.

4. **Asset category stays plain text.** Three values, no page, and CLAUDE.md
   already retires the bare name `category` for exactly this ambiguity.

5. **Then decide whether the spine should carry the strategy's work type at
   all.** `capitalstrategy` joins to the spine on budget line; if a project's
   236-value work type is derivable, that is the row that *should* be labelled
   "Project type" and linked — and the current 39-value column becomes
   `programme`. That is a builder change and a separate piece of work.

**Guards.** No profile row may link to a route whose vocabulary differs from
the value it renders — expressed concretely: a test that the "Project type"
cell contains no `route(` call, with the 39-vs-236 measurement in its docstring,
so removing it is a deliberate act.

---

# Part 3 — the facet pages, decided (owner: "we should have profile pages for
# ten-year categories and project types, as we currently do on the site")

Agreed on both, and on the data-source component. Measuring what backs those
pages today changed **which** page gets which vocabulary, so this section
replaces Part 2's items 2–5.

## ⚠⚠ BOTH FACET PAGES PUBLISH A PROJECT LIST FROM THE RETIRED SERIES

`/get/capitalprojects/by_category/{cslug}` — the project list on a category
page — is `SELECT * FROM capitalprojectsdollarscomp`. `/get/pstats-categories_by_type/{tslug}`
LEFT JOINs the same table for `prjnum`, `plannedcost` and `currcost`.

    capitalprojectsdollarscomp (retired 2023-10-26)   8,740 project ids
    capital_projects (the spine)                     17,024
    capital_projects, in the current plan            12,929

So both pages understate the programme by roughly half, and the type page is a
**mixed** page: live Ten-Year Strategy figures beside retired-series counts and
money, with nothing saying so. This is the same defect the Overview and
`/procurement` were rebuilt for.

⚠ `capitalstrategy` itself is **NOT retired** — latest published date
**2025-05-01**, 267 rows. It is the live Ten-Year Capital Strategy. Only its
join partner is dead.

## ⚠⚠ AND `capitalstrategy` HAS NO PROJECT KEY — which decides the whole design

Its full column list is *(Published Date, Project Type, Project Type
Description, Ten-Year Plan Category, Funding Type, Fiscal Year 1–10 Amount,
Ten-Year Total)*. **No project id, no budget line, no agency.** It is a
programme-level plan table — 267 rows for a whole city — not a project table.

Two consequences, and they point in opposite directions:

- A project's **236-value strategy work type is not derivable**. There is no key
  to join on. So Part 2's idea of showing the strategy's work type on the
  profile is closed — not deferred, closed.
- The type page's project list can therefore only ever be **faked**, which is
  what the coarse `(pub_date, category)` join to the retired series is doing.

## The two dimensions, named precisely

| | spine `project_types` | `capitalstrategy."Project Type Description"` |
|---|---|---|
| values | **39** | **236** |
| what it is | the distinct **budget-line families** a project is funded through — measured: `{L-0101, L-0103, L-D002, PU-0025}` → `{New York Research Library, EDP Equipment and Finance Costs}`, i.e. the deduplicated prefix set (`P`→Parks and Recreation, `HW`→Highways, `PW`→Public Buildings) | the Ten-Year Strategy's **work type** (Access for the Handicapped, Acquisition of Real Property, Animal Care) |
| project-level? | **yes** — 12,929 projects (100% of the current plan, 0% outside it) | **no key exists** |
| overlap | **5 of 39**, every one a naming coincidence (library systems, Courts, FDNY, NYCHA) | |

⭐ **Ten-Year category is the one dimension that exists on both sides**: spine
`ten_year_category` has **138** values over **8,287** projects (6,555 in-plan),
the strategy has **186**, and **128 are shared**. That is why the category page
is the one that can be made whole.

## What to build

**1. Ten-Year category pages — repoint the list, keep the plan figures.**
`/projects/categories/{slug}` already resolves (200). Change
`/get/capitalprojects/by_category/` to read the spine, so the page lists the
real projects in that category with spine money, and keep `capitalstrategy` for
the ten-year plan totals it alone publishes — **labelled by series**, never
added to the spine's figures. Two sources, each answering the question it owns.

**2. Project type pages — split them, because they are two dimensions.**
- `/projects/types/{slug}` **keeps the 236-value strategy vocabulary** and drops
  its retired-series join entirely. It becomes an honest *plan* page: ten-year
  amounts by category and funding type, with **no project list**, because the
  source has no project key and a fabricated list is worse than none.
- The spine's 39-value dimension gets its own page family under a name that says
  what it is — **budget-line family** — carrying a real project list and real
  spine money. ⚠ This is close to `/projects/budget-lines/{code}`, which is one
  level finer (1,913 lines vs 39 families); the family page is the parent of
  those, so build it as `/projects/budget-lines` grouped, not as a third route,
  unless measurement says otherwise.

**3. The profile links to the dimension that is about the project.**
The `Project type` row becomes **`Budget-line family`** and links to (2b). The
`Ten-Year Strategy category` row links to (1). `Asset category` stays plain
text — 3 values, no page, and the bare name `category` is already retired for
this exact ambiguity.

**4. Fix or unlink the budget-line 500 first.** Unchanged from Part 2 and still
the most urgent item: five links on every project profile lead to
`Undefined index: wegov-prjtype-name`.

## Order

    4  unlink or fix the budget-line 500        (live defect, smallest change)
    1  category list onto the spine            (8,740 -> 17,024; one endpoint)
    3a link the Ten-Year category row           (one line, works today)
    2a strip the retired join off type pages    (removes a mixed page)
    2b budget-line family pages                 (new surface)
    3b rename + link the profile row            (depends on 2b)

**Guards.** No capital endpoint serving a project LIST may read
`capitalprojectsdollarscomp`; a page showing both spine and strategy figures
must label each with its series and must never sum across them; and the profile
row's link target vocabulary must equal the vocabulary of the value it renders
— the 39-vs-236 measurement in the docstring, so removing the check is
deliberate.

---

# Part 4 — shipped 2026-09-08 (items 4, 1 and 3a)

## Item 4 — the budget-line 500 is fixed

Root cause: the controller's fallback read `Project Type Description`
(`capitalstrategy`'s column) while `/get/capitalbudget/{code}` serves
**`Project Type Name`**. It never fired, so `budgetLineA` died on
`Undefined index: wegov-prjtype-name`. `capitalbudget` carries that column on
**16,491 of 16,491 rows, 0 blank**.

- All five links on a real project profile now **200**. Over 60 random budget
  lines: **56 render, 4 return 404** (the line exists on the spine but in
  neither `capitalbudget` nor the `capitalcommitmentplan` fallback) — an honest
  answer where the 500 was not.
- The view gains `?? '—'`. **A display label must never take a page down.**
- That cell no longer links to `/projects/types`: `capitalbudget`'s
  `Project Type Name` is **41 values, 24 shared with the spine's families and 5
  with the strategy's 236**, so it linked into the wrong dimension.

⭐ **Verified end to end**: `verify_profile_links.py` follows **every** anchor
the profile emits on three representative projects — **73 distinct links, 0
broken**.

## Item 1 — the category page lists the spine

`/get/capital/projects/by-category/{slug}` is new, on the spine. Measured:

| category | retired series | spine |
|---|---:|---:|
| `UTILITY RELOCATION FOR SE AND WM PROJECTS` | **2** | **268** |
| `NEIGHBORHOOD PARKS, PLAYGROUNDS AND BALLFIELDS` | **0** | **1,036** |
| `ROUTINE RECONSTRUCTION` | 369 | 447 |

⚠⚠ **THE SLUG RULE COULD NOT MATCH ITS OWN URLS.** Both endpoints compared
`REPLACE(category,' ','-')` against Laravel's `Str::slug`, and **12 of 138
categories carry a comma** — `large,-major-and-…` against `large-major-and-…`.
Those fell through to a loose `ILIKE '%…%'`, which is worse than missing:
`sewers` also matches `COMBINED SEWERS AND WATER MAINS`, so a category page
could list another category's plan. Both sides are slugged identically now, and
the ILIKE is **deleted**.

⚠⚠ **A CATEGORY CAN HAVE PROJECTS AND NO PLAN.** `capitalstrategy` has no
project key, so the parks category has **0 strategy rows and 1,036 spine
projects** — and the page `abort(404)`'d on the strategy alone. It now 404s only
when **both** are empty, and hides the plan chart with a sentence rather than
throwing `n.slice is not a function` out of Chart.js.

⚠⚠ **THE EIGHT TILES WERE COMPUTED FROM THE RETIRED SERIES' COLUMN NAMES**
(`BUDG_ORIG`, `BUDG_CURR`, `BUDG_DIFF`, `DURATION_DIFF`, `START_DIFF`,
`END_DIFF`), so repointing the table made every one throw. Replaced with five
spine tiles. **`Amount Over Budget` is DELETED, not repointed** — the label this
section retired for carrying two definitions — and the three lateness tiles with
it, because they needed an "original" date the spine holds as a history rather
than as one value.

⚠⚠ **THE UNIT TRAP.** `main`'s money fields multiply by **1000** because the
retired series publishes thousands; the spine publishes **USD**. Reusing that
contract would render a $385M category as **$385B** — entirely plausible, and
invisible to any row-count or status-code check. Hence a separate `spine` entry
in `ProjectsDatasets`, never a repoint of `main` (which `budgetLineA` still
uses).

⚠ And every cell returns a **string**: 4,095 spine rows carry no description or
agency name, 5,152 no borough, 5,193 no asset category, and a bare null threw
`n.slice is not a function` in DataTables' sort. ⭐ **The rows still rendered
while the sort was broken** — a row count passed and the console was throwing.

## Item 3a — the profile links the facet that is about the project

Ten-Year Strategy category is now a link. The `Project type` row is renamed
**`Budget-line family`** and stays plain text, with the 39-vs-236 measurement in
the comment so the next reader does not "fix" it by adding a link.

## ⚠⚠ THREE OWN-PROSE GUARD FIRINGS IN ONE SITTING — 14th, 15th and 16th

Every one of the three new scanners fired on the comment explaining the thing it
banned: the retired-series scan on the router's own docstring saying it never
reads the retired series; the `Amount Over Budget` scan on the note saying the
tile is gone; the `ILIKE` scan on the note saying the fallback was removed.
`_php_code()` and `_py_code()` now strip comments and **docstrings** before any
of them look.

⚠ And the retired-series guard was then **too broad**: the source-coverage
payload legitimately NAMES `capitalprojectsdollarscomp`, because the sources
table's "Table" column tells a reader where the retired series lives. It tests
for the table in a **SQL position** now, not for the string.

## Still open, in order


---

# Part 5 — item 2a, and a shifted ingest it uncovered

## The type page is no longer a mixed page

`/get/pstats-categories_by_type/` LEFT JOINed `capitalprojectsdollarscomp`
(retired 2023-10-26) for `prjnum` / `plannedcost` / `currcost` and served them
beside LIVE strategy amounts. Measured over 25 sampled types / 362 rows: the
join contributed a figure on **127 rows and zeros on the other 235**, so two
thirds of the table read "0 projects, $0 planned" for real programmes. The join
and the three columns are gone.

⚠⚠ **AND THEY MAY NOT BE REBUILT ON THE SPINE EITHER.** The join key was
(publication date, **category**), so it attributed a whole CATEGORY's projects
to one TYPE — and a category spans many types. `capitalstrategy` has no project
key at all, so no join makes a project count on this page correct. It belongs on
the category page, which has one. The category cell links there now: same
vocabulary, and that page lists the spine.

## ⚠⚠ TWO OF THE EIGHT `capitalstrategy` VINTAGES ARE INGESTED WRONG

Found because the type page rendered `City` as a Ten-Year Plan Category and
linked it to `/projects/categories/city`. Measured 2026-09-08:

| vintage | rows | defect |
|---|---:|---|
| `20250116` | **258 of 258** | `Ten-Year Plan Category` **duplicates** `Funding Type`. Amounts are correctly aligned; the category is simply absent. |
| `20230112` | **275 of 275** | A **left shift by one**. Funding Type → Category, First Fiscal Year → Funding Type, every amount one column left, `Ten-Year Total` NULL on all 275 — the money sits against the **wrong fiscal years**. |

**533 of 2,255 rows, 23.6%.** Separation from the six clean vintages is exact:
**0 of 1,722 clean rows flagged, 533 of 533 bad ones.**

⚠⚠ **TWO DEFECTS NEED TWO TREATMENTS, and treating them alike emptied 162 of
236 type pages.** The first attempt excluded every row whose category was a
funding type — which is both vintages — and most types appear only in those. So:

- **`_STRATEGY_MONEY_OK`** drops the 275 shifted rows (tell: `Ten-Year Total`
  IS NULL). **228 of 236 types survive; 8 correctly 404** rather than publish
  money on the wrong fiscal years.
- **`_STRATEGY_CATEGORY_OK`** withholds only the LABEL on the other 258, whose
  amounts are fine. The type page renders those as "Not published" and does not
  link them; the category endpoint applies both, so `/projects/categories/city`
  **404s**.

⚠ **Both test the DATA, never a hardcoded date list** — a list goes stale the
moment a ninth vintage lands wrong, and a guard pins that.
⚠ **Neither repairs anything.** Un-shifting `20230112` means asserting which
fiscal year each amount belongs to — a claim this data cannot support. **The fix
belongs in the ingest**, and this is worth a task.

## ⚠ The 17th and 18th own-prose guard firings, and a third shape

Both new guards fired on their own explanation: one on an endpoint DOCSTRING
saying it no longer joins the retired series, one on a comment recording the bad
vintages by date while the guard bans hardcoded dates. `_py_prose_free()` blanks
docstrings **by line range** — not by removing every triple-quoted string, since
the queries are triple-quoted too and that would make every SQL assertion
vacuous.

⭐ And a **third** comment shape then survived both: a `--` SQL comment *inside*
a query string. Stripped as well; `--` is unambiguously a comment in SQL, so
removing those lines cannot eat a query.

---

# Part 6 — items 2b and 3b: the budget-line family pages

`/projects/budget-lines/families/{fslug}` is new, and it is the 39-value
dimension's own page: its budget lines, its projects from the spine, its money.

    Sewers                              444 projects · 103 lines · $13.23B planned · $5.27B spent
    Water Mains, Sources and Treatment  503 projects ·  97 lines · $12.96B · $8.35B
    EDP Equipment and Finance Costs     630 projects · 144 lines ·  $9.80B · $4.21B

Cross-checked against the spine directly: `444 / 13.23 / 5.27` — exact.

⚠ The route is declared **before** `/projects/budget-lines/{blcode}` or
`families` arrives as a budget-line code. Guarded, on the precedent the
digital-services section already set for `function/{cap}` before `{slug}`.

⚠ One slug rule, two languages: `_slug()` (Python) and `_SLUG_SQL` (Postgres).
A guard runs the Python one over the real vocabulary and parses the character
class **out of** the SQL rather than re-typing it — 4 of the 39 families carry
punctuation (`Water Mains, Sources and Treatment`,
`Dept. of Information Technology & Telecomm`) and a raw comparison misses every
one. This is the same defect that made `/projects/categories/{slug}` unable to
match its own URLs.

## ⚠⚠ AND THE BUDGET-LINES INDEX'S FAMILY GROUPING WAS DEAD

Found while adding the links. `rowGroup.dataSrc` named `wegov-prjtype-name` —
a key `/get/capitalbudget/bydate/recent` has never served; the column is
`Project Type Name` — so **all 749 rows rendered under a single "No group"
header**. The same renamed key that 500'd every budget-line detail page, in a
third place.

⚠⚠ **AND THE GROUP NAMES ARE NOT THE FAMILY VOCABULARY.** `capitalbudget` has
**41** values against the spine's **39**, and only **25 slugs match** — `PARKS`
here is `Parks and Recreation` there, `FIRE` is `Fire Department`, `HEALTH` is
`Health and Mental Hygiene`. Linking every header would 404 on 39% of them.

⭐ So the link is **gated on a served slug set** (`/get/capital/families`), not
on a guess: 25 headers link, 16 render as plain text, and a guard asserts the
gate matches the vocabulary in both directions — a family with a page must be
linked, and one without must not be. That is the third form this section's
standing rule has taken (`sd` districts, the type row, and now this): **a link
that lands on a 404 is worse than text.**

## Item 3b — the profile's family row links now

It was plain text while no page existed, which was right then. The guard that
enforced *"must not link"* is **retired**, exactly as its own docstring said it
should be once the pages existed, and replaced by one asserting the stronger
property: it links, and to `budgetLineFamily` rather than `prjType`.

⚠ Retiring a guard when its condition ends is not weakening it — leaving that
one would have forbidden the thing it was waiting for.

Profile links followed end to end: **78 distinct links across three profiles, 0
broken** (73 before these two items).

---

# Part 7 — the `<x-db.data-provenance>` component (Part 1, shipped)

One shell, two modes, migrated on three pages.

    page    "what data feeds this KIND of page"   — /projects, the family pages
    record  "which publications carry THIS record" — the project profile

Rendered and verified: the profile's block reads *"We're using normalized data
from 11 datasets. This record appears in 9 of them"* over **11 rows, 9 Yes / 2
Not published**, with its retired and grain badges intact; `/projects` reads
*"6 datasets containing 475,136 records"*.

⚠⚠ **THE MODES MUST NOT MERGE**, and a guard asserts it **per branch** — the
record mode may not render a dataset's total record count, the page mode may not
render a presence column. A whole-file check passes while one branch is wrong,
which is the lesson the by-start-year chart paid for. A dataset's total and this
record's presence in it are different claims; one row carrying both invites
"475,136 records" to be read as being about this project.

⚠ The shell **fetches nothing**. `/projects`'s DataTable init went with the
markup: thirteen views hand-rolled `loadTableStat()`, which called a route that
has never existed and, on the 404, ran `datasets.splice(i,1)` — rendering rows
and then deleting them.

## ⚠⚠ AND A GUARD CAUGHT THE MOVE HIDING A CAVEAT

Folding the profile's sources table into the accordion took the **retired-series
note** inside the collapse with it — one of the three sentences this section
calls load-bearing, now behind a click.
`test_a_caveat_is_never_behind_a_click_or_the_faintest_text_on_the_page` fired.

It renders **outside** the collapse now; the other three notes stay inside
because they DESCRIBE the table and are unreadable without the rows. Verified on
the rendered page: **3 visible `.db-note` elements before any click.**

⚠ The guard's own collapse-detection then had to be fixed twice: a lazy
`.*?</div>` spanned far past the real block and reported the Council-awards note
— which sits elsewhere entirely — as behind a click. It **balances `<div>`**
now. *A guard that flags the innocent is as useless as one that misses the
guilty.*

⚠ And the first mutation of it was **inert**: disabling the note with
`@if(false && …)` leaves the echo in the source, which is what the guard reads,
so nothing fired. The real mutation MOVES the echo inside the collapse — and
that one fired.

## The rest — migrated 2026-09-09, see Part 8.

---

# Part 8 — the remaining views, and what surveying them found

**Ten live views migrated.** Not twelve: surveying first changed both the count
and the design.

## ⚠⚠ THE COUNTS ARE NOT ALL DEAD — three families are SCOPED and WORK

The premise of Part 1 was that every one of these pages fetched a route that
does not exist. Measured, that is true of **seven**, and false of **three**:

| endpoint | status | used by |
|---|---|---|
| `/get/pstats-records_no/{table}` | **404** | capital, mProjects, prjTypesA |
| `/get/districts/pstats-records_no/{type}/{id}/{table}` | **404** | distsection, distprojectsection, schools, schoolSection |
| `/get/pstats-records_no-by_prjtype/{table}/{slug}` | **200** | prjTypeA |
| `/get/pstats-records_no-by_category/{table}/{slug}` | **200** | categoryA |
| `/get/pstats-records_no-by_budgetline/{table}/{code}` | **200** | budgetLineA |

Those three return a count **scoped to that type / category / budget line** —
strictly more informative than the registry's global row count. Replacing them
with a global figure under the same heading would have been the `globStats`
defect again: a different number under an unchanged label.

⭐ So the component gained a **third mode**. `page` renders server-side totals;
`scoped` keeps each page's own endpoint and fills the cells from it.

## ⚠⚠ THE OLD CALLBACK DELETED ROWS, AND ZERO WAS THE SAME BRANCH AS FAILURE

`loadTableStat`'s callback was `if (res) { fill } else { splice }`. A scoped
count of **0** — a fact, meaning that dataset holds nothing for this type —
removed the row; so did a failed request. Measured on
`/projects/types/animal-care`: **3 datasets requested, 1 row rendered.** After:
**3 rows, counts `2 / 0 / 0`.**

The scoped mode now distinguishes three outcomes and removes nothing:

    a number   the scoped count
    0          this dataset holds nothing for this scope — a finding
    —          the request failed; we do not know, and must not imply 0

## What was excluded, and why

| view | reason |
|---|---|
| `capitalA`, `orgprojectA`, `projectsA` | **unrouted** — `main_a`, `project_a`, `projects_a` appear **zero times** in `routes/web.php` |
| `orgproject` | no controller renders it; the `/p/{id}` rewrite replaced it |
| `organization` | **a different pattern that WORKS** — per-SECTION counts from `/get/orgs/stats-*`; measured **42 requests, 42 × 200**. Folding it into a component built for `stats_data_sources` rows would be a rewrite of a working feature. |

## ⚠ THREE CLASSES RENDERED THE SAME CELL, AND TWO OF THEM WERE EMPTY

`DistDatasets` and `SchoolDatasets` each emitted a bare
`<span id="stats_{tbl}"></span>` for a fetch that never came, so their pages
showed blank counters permanently. `ProjectsDatasets::countCell` is now `public
static` and all three delegate — one owner, three states (a number, "not
tracked", an empty span for a caller that fills it).

⚠⚠ **THEIR SIGNATURES ALL DIFFER**, and a blind positional edit across both
controllers nearly landed the counts in `$dslist`. `$counts` is LAST and
optional on each, and every call site's arity was re-checked **per class** —
the first check assumed one class for the whole file and reported three false
mismatches while missing a real one.

## ⚠⚠ THE MIGRATION SCRIPT HAD THE OWN-PROSE BUG, AND THEN A BALANCING BUG

1. **The remover ate its own comment.** It inserted the component tag (whose
   comment named `loadTableStat`) and then stripped every line containing
   `loadTableStat` — taking the `--}}` closer with it and **500ing eight pages**
   with "unexpected end of file". Strip first, then insert.
2. **It balanced from the wrong bracket.** Removing
   `… $('#dsStatsTable').DataTable({ … })` from the statement start met the `(`
   of `$(` first, so it cut after `$('#dsStatsTable')` and left
   `.DataTable({ … });` orphaned — `Unexpected token ':'` on eight pages.
   Balance from the `{` of `.DataTable({`.

Both were caught by loading the pages, not by reading the diff.

## ⚠ And a guard that banned the old vocabulary rather than the property

`test_a_scoped_count_of_zero_never_removes_its_row` first banned `splice` and
`.row(` — the two spellings the old code used. A mutation deleting the row with
`$(cell).closest('tr').remove()` **sailed straight through**. It now bans every
removal form, and all three mutations (jQuery `.remove()`, `removeChild`,
`hidden = true`) fire.

## Verified

Ten pages, rows and count cells read off the rendered table: **0 empty tables,
0 blank count cells, 0 new JS errors.** `/schools` carries three PRE-EXISTING
errors (`schools_no`, `Bloodhound`, and the documented `setData` map race),
confirmed on three loads both before and after and **named** in the verifier so
a new one still fails. Suite **1,105 → 1,107**.

