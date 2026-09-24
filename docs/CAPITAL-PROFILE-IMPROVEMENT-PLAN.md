# Improvement plan — the capital project profile (`/p/{agency}{id}`)

Companion to `docs/CAPITAL-PROFILE-DESIGN-REVIEW.md`, which measured the
problems. This says **how to fix each one**: what changes in which layer, what to
measure before and after, which guard pins it, and how to prove the guard. Every
class and key named here **existed on 2026-09-08** unless marked NEW.

⚠⚠ **THIS SENTENCE USED TO READ "Nothing below is built." IT IS ALL BUILT** —
A-Q shipped 2026-09-08, and the record of what the building found is in the
sections from *"FOUR PLACES THIS PLAN WAS WRONG"* onward. **And two items have
since been SUPERSEDED by owner decisions on 2026-09-10 — read the last section
of this file before implementing D or Q**, or you will rebuild a Money section
and a second table of contents that were deliberately removed.

Conventions this plan assumes, because the repo has paid for each:

- **The page computes nothing it can be served.** Where a number or a sentence
  is needed, add it to `/get/capital/project/{ident}`; the Blade prints it.
- **Every change is verified on the rendered page, headless**, reading geometry
  and DOM — never a screenshot alone, never the source file. The map and chart
  verifiers (`verify_profile.py`) are the pattern; extend them.
- **Every guard is verified by reintroducing its bug**, with the mutation
  asserted to have reached the **served HTML** first (`restart app`, then
  `curl`), because opcache holds the compiled Blade and `view:clear` alone does
  not reach it.
- **Controller and `Custom/` classes are baked into the app image** —
  `up -d --build app`, not `restart`. Views are mounted; the api is baked too
  (`up -d --build api`).

The items are grouped by the layer they touch. Sequencing is at the end.

---

## A. Key-facts strip above the fold  🔴 · the single most valuable change

**Problem.** Money begins at 1,216px, Schedule at 1,716px; the first screen is
chrome. A reader's four questions — how much, what phase, when, is it late — are
unanswered until the second screen.

**Endpoint** — add one block, assembled from values the endpoint already has:

```python
"key_facts": {
    "planned_usd": …, "committed_usd": …, "spent_usd": …, "checkbook_usd": …,
    "current_phase": row["current_phase"],           # None when not published
    "forecast_completion": row["forecast_completion"],
    "forecast_label": _mdy_label(row["forecast_completion"]),   # see K
    "slip_months": slip["total_months"] if slip["available"] else None,
    "slip_direction": slip["direction"] if slip["available"] else None,
    "sources_present": coverage["sources_present"],
    "sources_read": coverage["sources_read"],
    "sources_absent": [r["label"] for r in coverage["rows"] if not r["present"]],
}
```

No new query. `money`, `slip` and `coverage` are computed already; this
restates them at the grain the strip needs. ⚠ Keep the six money measures as
**six tiles, never fewer** — ⚑ F, they are not a funnel and cannot be combined.

**View** — directly under the badges, before the attribute table:

```blade
<x-db.stat-grid>
  <x-db.stat label="Planned" :value="$fmtM($kf['planned_usd'])" />
  <x-db.stat label="Committed" :value="$fmtM($kf['committed_usd'])" />
  <x-db.stat label="Spent" :value="$fmtM($kf['spent_usd'])" />
  <x-db.stat label="Paid (Checkbook)" :value="$fmtM($kf['checkbook_usd'])" />
  <x-db.stat label="Phase" :value="$kf['current_phase'] ?? 'No schedule published'" />
  <x-db.stat label="Forecast completion" :value="$kf['forecast_label'] ?? '—'"
             :sub="$slipLine" />        {{-- "33.4 months later than first forecast" --}}
</x-db.stat-grid>
<p class="small">In {{ $kf['sources_present'] }} of {{ $kf['sources_read'] }} sources
   @if($kf['sources_absent']) · not published: {{ implode(', ', $kf['sources_absent']) }} @endif</p>
```

That last line **absorbs item F** (the hidden-sections notice) and **item M**
(the presence card): both say "which publications carry this project", and
saying it once at the top is the answer to both.

⚠ `$fmtM(null)` must render **"Not published"**, not `$0` — a measure the City
does not publish for this project is not zero (existing rule; the helper already
does this, keep it).

**Measure.** Before: first `<h3>` at 1,216px. After: every one of the six
figures and the phase must sit **above 900px** at 1440×900. Read
`getBoundingClientRect().top` of each `.db-stat-value`, not a screenshot.

**Guard** (`test_capital_project_page.py`):
- `key_facts` is a returned key of `capital_project` (AST dict keys), and its
  money values are **the same variables** as `money.measures` — read the AST,
  assert `key_facts["planned_usd"]` is built from `values[...]`, not a second
  query.
- The view echoes all six `{{ … }}` (assert the echo, not a mention — the
  review's guard rule).
- The strip renders **before** the attribute table (`view.index('db-stat-grid')
  < view.index('Managing agency')`).

**Mutations to fire:** delete `key_facts` from the return; swap one tile's
value for a literal; move the grid below the table.

---

## B. Rebuild the history table  🔴 · 26% of the page, mostly repetition

**Problem.** 45 × 14, 2,505px. Four sources with different columns forced into
one UNION, so half the cells are `—`; 14 `cpdd` rows carry 0 phases, 0
forecasts, one reason string 14 times, and 4 unchanged budgets. On mobile the
per-row source label wraps to five lines and the table is 837px in a 390px
viewport.

**Endpoint** — serve the history **grouped by source**, each group carrying
only the columns that source publishes, and each row flagged for whether it
changed anything:

```python
"history_by_source": [
  {"source": "cpdd", "source_label": "Project detail (2023 series, retired)",
   "retired": True,
   "columns": ["period_label", "budget_usd", "orig_budget_usd", "delay_reason"],
   "rows": [ {..., "changed": True}, ... ],          # changed vs previous row
   "count": 14, "changed_count": 9,
   "note": "Retired series: every snapshot is a 2023-or-earlier statement."},
  {"source": "dash_money",  "columns": ["period_label","budget_usd","spend_usd"], ...},
  {"source": "dash_sched",  "columns": ["period_label","phase","forecast_completion",
                                        "variance_days","delay_reason"], ...},
  {"source": "dashboard",   ...},
]
```

`changed` = any served column differs from the previous row **of the same
source**. Keep the flat `history` key for existing consumers (MCP, the API) —
this is additive.

⚠ **Which columns each source publishes is measured, not assumed.** Before
writing the `columns` lists, count non-null per column per source over the whole
`capital_project_history` table and record it in the docstring. A column that is
null on 100% of a source's rows is not that source's column.

⚠ **Do not dedupe across sources.** `dashboard` and `dash_sched` agree on 98% of
periods and disagree on 2% (measured, 371 of 17,764) — that disagreement is real
and must stay visible when both are expanded.

**View** — one collapsible block per source, `collapse` (already on 18 views):

```
Budget history                                   [show all 45 snapshots]
▸ Project detail (2023 series, retired) — 14 snapshots, budget changed 9 times   [expand]
▸ Dashboard budget history — 11 snapshots, changed 9 times                       [expand]
▸ Dashboard schedule history — 10 snapshots, forecast moved 10 times             [expand]
```

Default state: **collapsed**, showing the one-line summary per source. Expanded:
only rows with `changed = true`, with a "show unchanged too" toggle. The source
label is the **group heading**, never a cell — that alone removes the five-line
wrap on mobile.

⚠ The **chart stays above this**. It is the schedule history's story; the table
is the receipt.

**Measure.** Before: 2,505px / 45 rows / 14 columns. After (collapsed):
≤ 250px. After (all expanded, changes only): count rows ≈ 9 + 9 + 10 + 10 = 38 →
should render **under 1,400px**. Mobile: widest table ≤ viewport (no inner
horizontal scroll) — assert `table.scrollWidth <= parent.clientWidth`.

**Guard.**
- `history_by_source[*].columns` ⊆ the non-null columns of that source
  (behavioural: build a fixture with one source, assert an all-null column is
  absent).
- Per-source `count` equals the flat `history` count for that source (the two
  keys cannot disagree).
- View: the source label appears in a heading element, not inside `<td>`.

**Mutations:** put `phase` into `cpdd`'s columns; make `changed` always `True`;
move the label into a cell.

---

## C. Reading order, one `<h1>`, demote the org shell  🟡

**Problem.** Section order is source-first. Two `<h1>`s. The agency's tab bar
(About · Notices · Work · …) is 380px of navigation for a different entity.

**View only.** New order:

1. breadcrumb (as today)
2. **Context line** replacing `@include('sub.orgheader')`:
   `A <a>Department of Design and Construction</a> project · reports to <a>Deputy Mayor for Operations</a>`
   — `org` is already fetched; `dispName()` and the parent are already
   available to the header include, so lift the two values, not the shell.
3. `<h1>` project title (item H), lead line, badges
4. **Key facts** (A) + map right column
5. About this project (attribute table, scope prose)
6. Money (D)
7. Schedule + the chart directly beneath it
8. Budget history (B)
9. Where it is (districts)
10. Also funded here (commitments · same-line · Council awards) (E)
11. Where these figures come from (unchanged)

Every section heading becomes `<h2>` (item I) — there is one `h1`, so sections
are `h2`.

⚠ **The org shell's `orgheader` include carries the NYCHA dropdown override and
the "Also known as" line.** Neither applies to a project page, but check the
include for anything ELSE it sets (e.g. `$section` used by breadcrumbs) before
removing it. `Breadcrumbs::orgPrj(...)` is what actually provides the org
context on this page today.

⚠ For the **4,568 projects with no `wegov_org_id`**, the context line is
`A DDC project` with no link, exactly as the standalone shell renders today.
Test both.

**Measure.** `document.querySelectorAll('h1').length === 1` on all five
representative pages. Section headings all `h2`. Height of everything above the
first `.db-stat-value` **< 600px** (was ~1,200).

**Guard.** One `<h1>` in the rendered copy; `sub.orgheader` not included; the
order of the eleven section anchors pinned by index.

**Mutation:** re-add the include; swap Money above the attribute table.

---

## D. Money as tiles, caveat beneath, definitions expandable  🟡

**Problem.** A 130-word caveat precedes any number; 4 of 6 definitions differ by
one word and each repeats the publisher.

**View only** (the payload already carries everything):

```blade
<h2>Money</h2>
<x-db.stat-grid>  @foreach($money['measures'] as $m)
  <x-db.stat :label="$m['label']" :value="$fmtM($m['value'])" />
@endforeach </x-db.stat-grid>
<p class="small">{{ $money['note'] }}</p>          {{-- ⚑ F, kept, one line beneath --}}
<details><summary class="small">What each measure counts, in the publisher's words</summary>
  <dl> @foreach … <dt>{{ $m['label'] }}</dt><dd>{{ $m['definition'] }} <em>— {{ $m['source'] }}</em></dd> @endforeach </dl>
  <p class="small">{{ $money['publisher_caveat'] }} <em>— {{ $money['publisher_caveat_source'] }}</em></p>
</details>
```

⚠ **The existing guard `test_the_page_echoes_the_publishers_own_definitions_and_the_not_a_funnel_note`
must keep passing and must not be weakened.** It asserts the note and every
definition are ECHOED. Inside `<details>` they still are — that is the point of
`<details>` over hiding: the text is in the DOM and in the accessibility tree.

⚠ If A ships, Money's six tiles duplicate the strip's four money tiles. Resolve
by making the strip show **four** (planned · committed · spent · paid) and
Money the full six with definitions — the strip is a summary, Money is the
section. Say so in a comment or the next reviewer will "dedupe" one away.

**Measure.** Money section height before ≈ 500px; after ≈ 220px collapsed.

**Guard:** the six `{{ $fmtM($m['value']) }}` echoes exist; `$money['note']`
echoed **outside** the `<details>` (it must be visible without a click).

---

## E. Cap the related lists at 5, link out  🟡 · needs one endpoint filter

**Problem.** 25 of 234 same-line projects (1,650px) and 25 Council awards,
both full tables mid-page.

**Endpoint, part 1 (NEW filter)** — `/get/capital/projects?budget_line=AG-0001`:

```python
# _list_filters
if budget_line:
    # ⚠ Through budgetline.norm on BOTH sides. The spine stores 'AG-D001'; a
    # caller may send 'AG D001' or 'AGD001'. Normalising only the input is the
    # RICHMOND defect on a new column.
    add("EXISTS (SELECT 1 FROM unnest(p.budget_lines) bl "
        "WHERE " + budgetline.sql_norm("bl") + " = $?)", budgetline.norm(budget_line))
```

`budget_lines` is `text[]` with a GIN index (`idx_capital_projects_budget_lines`);
`&&` against an array literal would use it directly, but the array holds the
**raw** spelling, so a normalised match has to `unnest`. Measure the cost on the
largest line (over 1,000 projects) before shipping; if it is slow, add a
normalised `budget_lines_norm text[]` column in the builder and index that.

⚠ The filter must reach the **map too** (`capital_geojson`) — the guard
`test_the_map_is_actually_handed_every_membership_filter_the_list_takes` will
fail until it does, which is correct.

**Endpoint, part 2** — `_RELATED_CAP` 25 → **5**, and serve a `more_url`
fragment: `"filter": {"budget_line": lines}` so the page can build the link
without composing a query string of its own.

**View** — 5 rows + `234 more on this budget line →` linking to
`/projects?budget_line=…` (one link per line when a project has several; most
have one, max 34).

**Measure.** Related sections before: ~2,400px; after: ~500px.

**Guard:** `count`/`showing` still served (existing test); the link's href is
built from the served `filter`, not a re-derived string.

---

## F. The "not shown" line  🟢 — absorbed by A
Move the sentence into the key-facts strip (`sources_absent`). Delete the
bottom copy. Guard `test_an_empty_section_is_hidden_and_then_named` needs its
location assertion updated to the strip; its property (hidden sections are
NAMED) is unchanged.

## G. Community-district cell  🟢
View only. `Brooklyn <span class="small text-muted">(borough only)</span>` with
`title="The City publishes no community district for this project — only the
borough"`. Keep `$cbHasDistrict` and its guard as-is; only the string changes.

## H. Title size  🟢
`.db-profile-title` on the project `<h1>` at `var(--db-text-2xl)` (28px) rather
than the 36px default. Do **not** transform case — `CSO`, `OH-015`, `GI` are the
City's tokens.

## I. Heading levels  🟢
With one `h1`, every section is `h2`, sub-blocks (`Dates the City reports as
actual`) `h3`. Guard: no `h4`–`h6` in `main` outside the footer.

## J. One badge vocabulary  🟡
| meaning | variant (exists) |
|---|---|
| presence (`In the current plan`, `Schedule published`) | `db-badge-neutral` |
| vintage warning (`retired 2023`) | `db-badge-warning` |
| grain caveat (`by budget line`) | `db-badge-info` |
| district ids | **links**, `db-badge-navy` — they should go to the district page |

Guard: `retired 2023` never renders inside `db-badge-neutral`; the grain badge is
`db-badge-info`.

## K. One date format  🟡
The schedule and chart print `MM/DD/YYYY`; history prints `26 Oct 2023`. Add
`_mdy_label()` beside `_mdy()` in the router (`23 Feb 2030`), and serve
`*_label` **beside** every phase/forecast date (`forecast_completion_label`,
`actual.design_start_label`, …) — the raw stays for consumers. The view prints
the label. The slippage chart's tooltip prints the label too.

⚠ Do not reformat in the view: two formatters for one kind of value is how
the two formats arrived.

Guard: no `\d{2}/\d{2}/\d{4}` in rendered copy (strip scripts and comments) —
verified against a served page fixture, since the pattern only appears once the
payload is echoed.

## L. Muted text on the token  🟢
`.db-muted { color: var(--db-text-muted); }` in `databook-components.css`;
replace `text-muted` in this view. Contrast: `#757575` on white = **4.6:1** —
passes AA for normal text, **fails AAA**, and Bootstrap's current
`rgba(33,37,41,.75)` is ≈7:1. **So this is a trade**: consistency with the token
vs. a darker grey. Recommend: adopt the token AND raise the token's
`--db-gray-600` to `#616161` (**≈6.9:1**) site-wide, which is a tokens-file
change with the parity check to satisfy (`test_design_token_parity.py` will
fail until `wegovnyc-design-tokens` moves too — that is the documented
process, not an obstacle). Or leave Bootstrap's and record it. Pick one.

## N. Load-bearing caveats are the smallest text  🟡
The non-funnel note, the Council grain caveat and the retired-series notice are
`small text-muted`. Style these as **`.db-alert-note`** (NEW, or reuse
`<x-db.alert type="info">` at small size): full body colour, a left rule, not
grey. Rule: **a sentence that stops a reader misusing a number is not
decoration.** Guard: those three specific served keys (`money.note`,
`council_awards.note`, `source_coverage.retired_note`) are not echoed inside an
element carrying `text-muted`/`db-muted`.

## O. Touch targets  🟢
Budget-line links and district badges: `padding: 6px 8px; display: inline-block`
on mobile via the existing `responsive.css`. Assert each is ≥ 32px tall at 390px
in the headless run.

## P. `<th scope>` on data tables  🟢
Add `scope="col"` to every `<thead><th>` in the view. Guard: every `<th>` in the
template carries a `scope` attribute.

## Q. Optional — a sticky table of contents
`.db-toc` exists in the design system and nothing on this page uses it. Once the
page is ~5 screens instead of 11, a right-rail TOC of the eleven sections would
make the remaining length navigable. Not a fix for the length; a companion to the
fixes above. Decide after A–E land.

---

## Sequencing

| step | items | layer | why this order |
|---|---|---|---|
| 1 | **K** (date labels), **A** (key facts), **B** (history by source), **E part 1** (budget_line filter) | **api** | Everything the view needs, in one api build. B's per-source columns and A's `forecast_label` both depend on K. |
| 2 | **C** (order, one h1) + **A** + **D** + **B** views + **F**, **M** | view | One restructure of the template, not five. Verify all five representative pages headless after this step — this is the risky one. |
| 3 | **E part 2** (cap + link), **G**, **H**, **I**, **J**, **P** | view | Small, independent, each with its own mutation. |
| 4 | **L**, **N**, **O** | css + view | Token decision first (L is a site-wide choice); N and O follow. |
| 5 | **Q** | view | Only if the page is still long enough to need it. |

**Guard first, then change.** For each step, write the guard, run it and watch
it **pass on the current page where the property already holds or fail where it
does not**, make the change, then mutate. Three guards in this section were
silent on first writing because they inspected a mention rather than the code's
effect; the mutation harness (`mutate*.py` in the scratchpad pattern) is the
check on the check.

**Verification of the whole, after step 2:**

| measure | today | target |
|---|---|---|
| rich page height, 1440px | 9,636px | **≤ 5,000px** |
| rich page height, 390px | 17,349px | **≤ 9,000px** |
| first `.db-stat-value` top | — (none) | **< 600px** |
| `h1` count | 2 | **1** |
| widest table vs viewport at 390px | 837 / 390 | **≤ 390** |
| sections with `h3`–`h6` headings | 14 mixed | **0 (all `h2`)** |
| `db-badge-neutral` meanings | 4 | **1** |
| date formats in rendered copy | 2 | **1** |
| suite | 1,076 | **1,076 + new guards, 0 red** |

Every "today" figure above was measured on `fead617`; re-measure before
starting, since the page may have moved.

---

## What NOT to do, because each looks like an improvement

- **Title-case the project names.** Breaks the City's own tokens (`CSO`,
  `OH-015`, `GI`). Reduce size, keep case.
- **Hide the caveats to save space.** Move them (D, N); never remove. ⚑ F and
  the Council grain caveat are the two sentences that stop a published number
  from being misread.
- **Collapse the six money measures into fewer tiles.** They are six separate
  measures on six populations (⚑ F). Four in the strip is a *summary*; six in
  Money is the *section*; neither is a merge.
- **Dedupe `dashboard` against `dash_sched` in the history.** They disagree on
  2% of periods, measured, and the disagreement is a fact about the City's two
  tables.
- **Filter `budget_line` on the raw array with `&&`.** Fast and wrong — the
  stored spelling is `AG-D001`, a caller will send `AG D001`, and 0 rows read
  exactly like "no projects on this line". Normalise both sides (E).
- **Drop the sources table because the key-facts strip summarises it.** The
  strip says *how many*; the table says *which*, with versions. Both.

---

# OUTCOME — all 17 items shipped 2026-09-08

Every item A–Q is implemented, verified headless on three representative pages
at two widths, and guarded by a mutation-verified test. Suite **1,076 → 1,088,
0 red**. What follows is the measured result, then the four places where doing
the work **contradicted this plan** — those are the part worth reading.

## Measured, before → after

| measure | plan target | before (`fead617`) | after | |
|---|---|---:|---:|:--|
| page height, 1440px (rich) | ≤ 5,000 | 9,636px | **5,350px** | ⚠ 7% over — see below |
| page height, 390px (rich) | ≤ 9,000 | 17,349px | **9,538px** | ⚠ 6% over |
| first `.db-stat-value` top, 1440 | < 600 | none existed | **382px** | ✅ |
| first `.db-stat-value` top, 390 | < 600 | none existed | **581px** | ✅ |
| `<h1>` count | 1 | 2 | **1** | ✅ |
| `h4`–`h6` headings | 0 | 14 mixed | **0** | ✅ |
| page scrolls horizontally at 390 | never | — | **never** | ✅ |
| `<th>` without `scope` | 0 | many | **0** | ✅ |
| date formats in rendered copy | 1 | 2 | **1** | ✅ |
| `db-badge-neutral` meanings | 1 | 4 | **1** | ✅ |
| history section height | — | 2,505px | **322px** | ✅ |
| `.db-tap` min height at 390 | ≥ 32 | ~19px | **32px** | ✅ |
| suite | 0 red | 1,076 | **1,089** | ✅ |

Sparse and no-org pages: ~2,400px / ~2,900px at 1440.

⚠ Clipped elements: **0** at both widths on all three pages (see below — this is
what the last ~110px of desktop height and ~410px of mobile height bought).

**The two heights that missed, and why they are not closable without cost.**
Section-by-section at 1440 after the work, nothing dominates: sources 959px,
commitments 735px, header+map 712px, climate 438px, same-line 438px, about
425px, schedule 326px, history 322px, money 262px. Every one is real data at its
natural grain — 15 commitment lines, 5 climate ratings per budget line, 11
sources. The only remaining levers are hiding content, which §"What NOT to do"
forbids for the sources table specifically. **Item Q cost 255px on its own** (a
`col-md-9` content column makes every table taller); it was kept because
navigation over 13 sections is worth 5% of height, but that is the trade and it
is recorded rather than buried.

## ⚠⚠ FOUR PLACES THIS PLAN WAS WRONG, FOUND BY MEASURING RATHER THAN READING

1. **Item L's contrast figures were wrong and its recommendation was
   backwards.** The plan proposed adopting `--db-text-muted` (`#757575`) and
   raising `--db-gray-600` to `#616161`, citing "≈6.9:1". Recomputed:
   `#757575` = **4.61:1**, `#616161` = **6.19:1**, and the Bootstrap
   `.text-muted` both were replacing composites to `#585c5e` = **6.76:1**. So
   the plan's own recommendation was a contrast **regression** dressed as a
   consistency win. Shipped instead: `--db-text-muted: #595959` = **7.00:1**,
   AAA for normal text and better than what it replaces.
   ⭐ And it is on the **semantic** token, never `--db-gray-600` — that grey is
   in the shared package's reference tier, so moving it fails
   `test_design_token_parity` and is not Databook's call to make alone.
   `--db-text-muted` is Databook-only, which is exactly what a semantic tier is
   for. **No parity failure, no package coordination, better contrast.**

2. **Item J's "district ids should be links" is only true for three of the four
   types.** Fetched with real values out of `capital_project_districts`:
   `cc`, `cd` and `nta` each serve a district page and its projects section
   (`/districtXHR/{type}/{id}/projects` → 200, ~23 kB). **`sd` returns 404 at
   both the page and the XHR**, for every school district tried. School
   districts therefore stay unlinked badges — a badge that looks like a link and
   lands on a 404 is worse than a badge. **This is a pre-existing defect on the
   district surface (Phase 4), not something the profile introduced**, and it is
   worth a task.

3. **Item A's view snippet does not work.** It writes
   `<x-db.stat label="…" :value="…" />`; `stat.blade.php` takes the value as its
   **SLOT**, so `:value` would have been merged onto the wrapper `<div>` as an
   attribute and every tile would have rendered **empty**. Nothing about the
   payload was wrong — the component contract was. *Read the component before
   writing against it.*

4. **Item K was incomplete as specified, and the incompleteness was invisible
   from the plan.** It named the schedule, the history and the chart. Four other
   panels — commitments, climate, Parks, milestones — still printed
   `MM/DD/YYYY`, so after implementing item K exactly as written the page still
   carried two date formats and **7 raw dates survived on the rendered page**.
   Fixed with `_DATE_COLUMNS` + `_label_dates()` at the endpoint, and the guard
   reads that set out of the router rather than re-typing it, so a new date
   column is covered the moment the endpoint labels it.

## ⚠ Other things the work found

- **A guard fired on its own prose for the thirteenth time in this repo**, in a
  new organ: `test_databook_does_not_import_the_package` scans
  `databook-tokens.css` for the package name, and the `/* … */` comment
  EXPLAINING why a shared reference value must not be edited there contains it.
  Fixed by stripping CSS and Blade comments in the guard — an import is code, a
  mention is prose. It now fails where something is wrong instead of where
  something is explained.
- **A CSS rule in `responsive.css` cannot override `databook-components.css`.**
  The mobile title size was put there first and the measurement did not move by
  a single pixel — `responsive.css` loads FIRST (checked in the rendered
  `<head>`, not assumed), and a media query is not more specific than the rule
  it means to override. Moved beside the class it overrides.
- **A sidebar that is `d-none` on mobile still costs mobile height.** The TOC's
  `col-md-9` gutter narrowed every table and paragraph by 24px at 390px, adding
  **312px** for a component that does not render there. `px-0 px-md-3` gives it
  back.
- **The first verifier asserted the wrong thing about tables.** It counted a
  table wider than its `.table-responsive` box as a failure and reported four
  correctly-scrolling tables as defects. A 7-column table cannot fit 390px; what
  must never happen is the PAGE scrolling sideways, which is what a reader
  experiences. Assert `document.documentElement.scrollWidth <= innerWidth`.
- **Six existing guards fired on this work and every one was right to.** Three
  in `test_capital_project_page.py` and three in `test_capital_triage_fixes.py`
  anchored on the old markup shape while guarding properties that still hold
  (the org shell, the climate vintage echo, `$cbHasDistrict`'s consumption, the
  history period label, the map's column, the `$show()` gate). Each was
  **re-expressed against what the code now does and then mutation-verified** —
  not relaxed. A guard that fails when you change the thing it guards is doing
  its job.
- **`_slippage` grew a dependency and a by-name test loader NameError'd.** That
  is the loader working: it compiles named defs out of the real router, so a
  function that starts calling something new fails loudly rather than testing a
  stale copy.

## The budget-line filter, measured before shipping

`EXPLAIN ANALYZE` on the largest line (`P-I001`, **1,135 projects** of 17,024):
seq scan, **35.6ms**, 1,372 buffers, all shared hits. Through the endpoint on a
warm cache: **43–58ms**. Acceptable at page scale, **so no normalised
`budget_lines_norm` column was added** — that decision and its measurement are
in the code comment, so the next reader does not re-derive it.

Verified in the direction that matters: `P-I001`, `P I001`, `PI001` and
`p-i001` all return **1,135**. Normalising only the input would have returned 0,
and 0 reads exactly like "no projects on this line".

⭐ **List and map agree on twelve filter combinations**, including both borough
spellings, both new-filter spellings and `budget_line` combined with
`has_location` — 0 mismatches.

## Guards added, all mutation-verified

23 mutations across 17 new/re-expressed guards; every one asserted to have
LANDED before asserting the guard FIRED. Covering: `budget_line` reaching both
`_list_filters` calls in the map endpoint (arguments, not signatures);
normalisation on both sides through `modules/budgetline`; `unnest` not `&&`; one
`<h1>`; the strip rendering before the attribute table; four measures in the
strip and six in Money with neither merged (⚑ F); a caveat never behind a
`<details>` nor styled muted; the history source label as a heading not a cell;
unchanged snapshots hidden but never dropped; the "see all" link built from the
served `filter`; every `<th>` carrying `scope`; one meaning per badge variant;
and no date reaching the page in the publisher's raw format.

## ⚠⚠ AND THEN LOOKING AT THE RENDER FOUND TWO DEFECTS EVERY CHECK HAD PASSED

The suite was green, six headless verifiers were green, and the page had a
**clipped tile** and a **doubled sentence** on it. Both were found by opening
the screenshot. This is the single most useful thing in this document.

1. **`Construction Procurement` rendered as "Constructio / Procuremer".**
   `.db-stat` is `overflow: hidden` and `.db-stat-value` is 30px bold, so a
   150px grid column simply CUT the value. Two more were cut once that was
   looked for: `Not published` by 8px and **`$105.7M` by 4px** — a clipped
   number is a wrong number.
   ⭐ **Nothing could see it.** The element existed, was the right size, was in
   the right place, and contained the right text; DOM assertions, bounding-box
   assertions and text extraction all pass on a clipped element. Overflow is
   invisible to every check this section had.
   Fixed at the shared component (`overflow-wrap: anywhere`, `minmax(165px)`)
   plus an `is-text` modifier for tiles whose value is prose. **The fix costs
   ~110px of desktop height and ~410px of mobile** — every wrapped value is a
   value that used to be silently cut — which is why both height targets moved
   further out and why that is the right trade.
   ⚠ It is a SHARED component, so the other consumers were checked rather than
   assumed: 8 pages × 2 widths, **0 clipped, 0 new horizontal scroll**. The
   `/organizations` pages do scroll sideways at 1440 — **measured
   byte-identical (1512px) with the change stashed, so pre-existing**, and worth
   its own task.
   New guards: `test_a_clipping_box_never_holds_an_unwrappable_value` (CSS,
   mutation-verified in both directions) and a headless `verify_overflow`
   comparing scroll extent against client extent on every clipping ancestor.

2. **The key-facts strip printed the same two names twice in one sentence**:
   *"Not published in: NYC Parks project tracker, City Council capital awards.
   Nothing published for: NYC Parks project tracker, City Council capital
   awards."* `sources_absent` names PUBLICATIONS and `$hidden` names SECTIONS,
   and where a section is fed by exactly one publication they are the same
   words. **Both halves were correct and the sentence was still wrong** — which
   is why no guard on either list could see it.
   Fixed by SUBTRACTING (`$hiddenOnly = array_diff($hidden, sources_absent)`),
   never by dropping a list: the publication list is the stronger statement and
   wins, and the remainder carries the sections with no one-to-one publication,
   which would otherwise go unnamed — §5.3 returning in a tidier sentence. The
   guard now requires BOTH halves to render, and both mutations fire.

**The generalisable rule: geometry checks prove an element is THERE; only
looking proves it is READABLE.** Add the overflow check to any page that puts
variable-length content in a fixed box — but run the screenshot too.

## Owner review, 2026-09-08 — layout revised

Three changes on review of the render, all view-only:
- **The key-facts strip is full width.** In a `col-md-7` column its six tiles
  wrapped to two rows on an ordinary desktop; across the container they sit on
  one (measured: 6 tiles, 1 row at 1440).
- **About → Scope → Money sit LEFT of the map; "Where it is" sits UNDER it.**
  The map and the districts are one facet (location) and were ~3,000px apart.
  Money is now a compact label/amount list rather than a second grid of tiles —
  four of the six were already tiles in the strip and repeating them at tile
  size read as duplication. **All six are still there** (⚑ F), with definitions
  one click away.
- **The TOC row starts at Schedule**, so its first entries (About, Money, Where
  it is) scroll back UP — which is what was asked for.

Rich page: **5,027px** at 1440 (from 5,350), **9,264px** at 390.

⚠⚠ A guard re-expressed for this FAILED ON THE UNMUTATED FILE and every
mutation read as "fired". Its row regex stopped at the About table's `</div>`;
then its replacement end-marker sat inside a Blade comment the helper strips.
**Check the baseline is green before reading a mutation result** — a guard that
fails on everything fires on everything. And one mutation was then silent
because `index()` found the FIRST grid, not the smuggled second one; asserted
`not in row` instead. Both recorded in the guard.


---

## ⚠⚠ Owner review, 2026-09-10 — D and Q are SUPERSEDED

Two rounds of owner changes, both landed and verified on the rendered page
(`30c93fb`, `153fdcd`). **Item D no longer describes the page and item Q's
"decide after A-E land" is decided.** Implementing either as written would undo
this.

**D is gone: there is no Money section.** All six measures are tiles in the
key-facts strip — the strip shows **six**, not the four D proposed — and the
`<h2 id="money">` section, its TOC entry and its anchor were deleted.
- ⭐ **The strip's measure set is DERIVED, not typed**:
  `_STRIP_MONEY = tuple(m["key"] for m in capitalmoney.MEASURES)` in
  `api/routers/capital.py`, so "the strip shows every measure" is true by
  construction and ⚑ F cannot be broken by a hand-edited 4-tuple. A guard
  AST-reads that expression and asserts it references `capitalmoney.MEASURES`.
- **Phase and Forecast completion left the strip for the header**
  (`.db-profile-meta`), with the slip line beside the forecast.
- **All the money help is in one `<details>` under the tiles** — the note, the
  six definitions and the publisher's caveat. ⚠⚠ **That contradicts D's own
  closing guard** (*"`$money['note']` echoed OUTSIDE the `<details>`"*), and it
  is an owner decision taken with that rule on the table, not an oversight. What
  makes it safe is that the `<summary>` carries the warning itself: *"How to
  read these six figures — they are not stages of one pot."* The guard was
  narrowed to require exactly that, and still protects `awards.note` and
  `coverage.retired_note` in full.

**Q is decided and inverted: there is exactly ONE table of contents, BELOW the
About row.** It used to render as a `col-md-3` beside About when there was **no**
map — squeezing About to `col-md-9` on precisely the pages with nothing in the
right column — and lower down when there was one. About is now `col-12` with no
map (measured 1,400px, was ~1,000) and `col-md-7` beside the map (817px), with a
single unconditional `@include('partials.capital_toc')` under the row.

**Also in this round, and not in the plan at all:**
- **Scope is a FIELD, not a section.** It was an `<h3>` plus a vintage line
  below the table it belongs in — the only free-text attribute the City
  publishes, formatted unlike every other attribute. It is a row in the About
  table now, and it left `$sections` with it: a field is not a section, so an
  absent scope is an em dash in its own row rather than "Scope" being named in
  the *"Nothing published for:"* sentence on every project the 2023 series never
  carried. ⚠⚠ **The vintage did not go, it MOVED to the ⓘ** (`title` +
  `aria-label`, the pattern the community-district row already uses; this page
  loads no popover JS). Turning a section into a table row is exactly how such a
  label gets lost — a guard asserts the citation exists, says "2023" and
  "retired", and reaches a screen reader rather than a mouse only.
- **The sources sentence moved to "Where these figures come from."** Same
  sentence, same two subtracted lists, now under the heading that asks its
  question. ⚠ It was at the top for a real reason (§5.3: that text sitting
  9,000px down a 9,636px page) and the reason weakened — the page is ~3,200px
  and the TOC links straight to the heading. Hence a move, not a revert.
