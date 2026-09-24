# Design review — the capital project profile (`/p/{agency}{id}`)

Reviewed 2026-09-08 against the **rendered local build** at `fead617`, not the
template: five representative projects at 1440px plus one at 390px, full-page
captures, and DOM measurements (heights, heading levels, table shapes, computed
colours). Every figure below is measured. Stage: **refinement** — the data
layer is right; the question is whether a reader can use it.

Pages measured: `850GKOH15-01` (rich: map, chart, 9 of 11 sources),
`846P-407LBSF` (Parks, point geometry), `037LN18ALELE` (out of plan, 1 of 11
sources), `111PO111-17` (no known agency, standalone shell), `110WLM`
(disambiguation).

---

## Overall impression

The page is **honest and complete** — every number is served, every source is
accounted for, and it cannot disagree with itself. That is rare and worth
protecting. But it reads as a **data dump, not a profile**: the rich page is
**9,636px tall** (≈11 screens), the first thing after the header is a 130-word
caveat, and the single largest block — 26% of the page — is a 45-row log whose
one piece of news is already drawn as a chart above it. **The page tells the
reader everything and prioritises nothing.** The biggest opportunity is
ordering, not content.

---

## Usability

| Finding | Severity | Recommendation |
|---|---|---|
| **No answer above the fold.** A reader arrives asking *how much, what phase, when, is it late*. Money starts at **1,216px**, Schedule at **1,716px**; the first 1,200px is agency chrome, a 7-row attribute table and a presence card. | 🔴 | A **key-facts strip** directly under the title: Planned · Committed · Spent · Current phase · Forecast completion · slip since first forecast. Every value is already in the payload; **zero new data**. |
| **"Budget and schedule over time" is a 45 × 14 log and the largest thing on the page** — 2,505px, **26% of the height**. Its 14 `cpdd` rows have **0 phases, 0 forecasts, and the identical reason string 14 times**; 4 carry a budget byte-identical to the row above. It is a UNION of four sources with different columns, so half the cells are `—` or "Not published". Its only story (the forecast moving) is the chart immediately above it. | 🔴 | **Split by source, show changes only, collapse by default.** `cpdd` has money and no schedule; `dash_sched` has schedule and no money — one table each, with only the columns that source publishes. Default view: rows where something *changed* (9 of 14 budgets, 10 of 10 forecasts), with "show all 45 snapshots". |
| **On mobile the same table is 837px wide in a 390px viewport**; the SOURCE column wraps to **5 lines per row**, so 45 rows cost ~4,200 of the page's **17,349px**, and the SPENT column is cut off behind an inner scroll. | 🔴 | Same fix as above solves most of it. Additionally: never put the long label (`Project detail (2023 series, retired)`) in a per-row column — it is the same on 14 consecutive rows. Group heading, not cell. |
| **Two `<h1>`s** — the agency (30px) then the project (36px) — and the org shell's tab bar (About · Notices · Work · …) is **380px of navigation for a different entity**. Inherited from `orgproject`/`pureproject`, but it is the wrong frame for this page. | 🟡 | Demote the org shell to a compact context line ("A **DDC** project · Deputy Mayor for Operations") with one link; the project is the h1. Keep the breadcrumb — it already does the job the tab bar is doing. |
| **The Money table leads with a caveat and repeats itself.** A 130-word paragraph precedes any number; then 4 of 6 definitions differ by one word ("Sum of the total *adopted/allocated/committed/spent* funding associated with the project within the City's budget"), each followed by the same publisher name. | 🟡 | Six **stat tiles** (`.db-stat`) with the number large and the label small; the one-line "these do not sum or nest" note beneath; publisher definitions as a single expandable "What each measure counts". The caveat's *content* is right and must stay — its *position* is what buries the page. |
| **"Other projects on the same budget line" shows 25 of 234 rows (1,650px) and Council awards 25 more**, both before the sources table. A 25-row table is cheap as a link and expensive as a section. | 🟡 | Top **5** each, "234 more →". ⚠ The natural target `/projects?budget_line=…` **does not exist** — the list endpoint filters on agency/category/phase/borough/q and four flags, not budget line. That is a small endpoint addition (the column is `text[]`, GIN-indexed) and it is worth doing, because it also gives the budget-line pages a live target. |
| **The "Not shown for this project…" line sits at 8,480px**, above the sources table. A reader who wonders "where is the schedule?" at 1,700px never sees it. | 🟢 | Move it to the key-facts strip as "Published: plan · commitments · Dashboard · location · … — not published: Parks tracker, Council awards", or repeat it at the top. |
| The community-district cell reads *"Brooklyn — the City publishes no community district for this project, only this much"* — 15 words in a table cell, on 5,263 of 8,373 projects. | 🟢 | "Brooklyn *(borough only)*" with the sentence as a `title`/tooltip. Same fact, one-fifth the ink. |

## Visual hierarchy

- **What draws the eye first:** the agency's name at the top, then the project title in **36px source-case capitals** — `GI - GREEN INFRASTRUCTURE IN OH-015 GRAVESEND BAY CSO PH 1`. The capitals are the City's, and title-casing would break `GI`, `CSO`, `OH-015`, so do **not** transform. But at 36px they shout over everything below; 28px with the same weight keeps the hierarchy without the volume.
- **Reading flow is source-ordered, not question-ordered.** The sequence is CPDB → Dashboard → chart → history → commitments → Parks → Climate → 2023 → districts → related → sources: *where the data came from*, not *what a reader asks*. The natural order is **what is it → how much → when → where → who else → where these figures come from**.
- **Heading levels are inconsistent:** `Scope` is an `h4`, `Where this project appears` and `Dates the City reports as actual` are `h6`, every other section is `h3`. Screen readers and skim-readers both use this.
- **Whitespace is uniform, so nothing is emphasised.** Every section gets the same `mt-4` and the same table treatment; the Money block and the "Districts" badge row have equal visual weight.
- **The chart is the best thing on the page and it is in the middle.** It should follow the key facts, not the Schedule table.

## Consistency

| Element | Issue | Recommendation |
|---|---|---|
| Muted text | Computed `.text-muted` is Bootstrap's `rgba(33,37,41,.75)`, not the design token `--db-text-muted` (`#757575`). Two greys for one meaning, and the tokens file thinks it owns this. | Use `color: var(--db-text-muted)` via a `.db-muted` class, or accept Bootstrap's and record it. Either — not both. |
| Badges | **31 `.db-badge.db-badge-neutral` on one page for four different meanings**: presence flags (`In the current plan`), a vintage warning (`retired 2023`), a grain caveat (`by budget line`), and district ids (`CC 38`, `NTA Kensington`). Same visual, different semantics. | One variant per meaning: presence = neutral, retired = warning-tinted, grain = outlined, districts = plain links (they *are* links, or should be). |
| Dates | `02/23/2030` (source `MM/DD/YYYY`) in Schedule, chart and sources; `26 Oct 2023` in history and the sources' version column. **Two formats on one page.** | Format phase/forecast dates the way periods are now formatted, at the endpoint. |
| Tables | `db-table table table-sm` for a 7-row key/value list, a 6-row measures table and a 45 × 14 log. Same class, three different shapes. | Key/value lists → definition list or `.db-stat`; logs → the split-by-source treatment above. |
| The presence card | Says the same thing as three of the eleven sources-table rows, in a card, 8,000px away from the table. | Fold into the key-facts strip and drop the card. |

## Accessibility

- **Colour contrast:** body `#171717` on white **15.9:1**; muted `rgba(33,37,41,.75)` ≈ **7:1**. Both pass AA and AAA for text. ✅
- **But the load-bearing caveats are the smallest, greyest text on the page** — the non-funnel note, the Council "award names a line, not a project" caveat, the retired-series notice — all `14px text-muted`. The sentences that stop a reader misusing a number are styled as the ones to skip.
- **Touch targets:** budget-line links (`EP-0007, HW-0001K, …`) are 16px inline text; the district badges are 12px. Marginal on mobile.
- **Tables:** the header key/value tables use `<th scope="row">` ✅; the data tables' `<th>` carry no `scope` — minor.
- **Chart:** the sentence above it ("moved 33.4 months later across 10 reporting periods…") is a real text alternative. ✅ Better than an `alt`.
- **Mobile:** no document-level horizontal scroll ✅; five tables scroll internally, and the widest (history) hides a column.

## What works well

- **Every figure is served, so the page cannot disagree with itself.** The Overview, the list and this page read one spine.
- **The sources table with its absences** is something almost no civic site does — a reader can tell "the City published nothing" from "Databook does not read that".
- **The slippage chart** says something no table on the page can: the forecast came back seven months and then jumped again.
- **The map is top-right and it draws** — a real footprint, not a pin, with an honest caption.
- **Hidden sections are named**, not silently dropped, and the disambiguation page for shared ids is clear and terminates.
- **The publisher's own definitions** on every money measure, verbatim, attributed.

---

## Priority recommendations

1. **Put the answer above the fold — a key-facts strip under the title.** Planned · Committed · Spent · phase · forecast · slip · which sources publish this project. All served today, no endpoint change, and it turns the first screen from chrome into content. *This is the single change that makes the page a profile.*
2. **Rebuild the history table as per-source, changes-only, collapsed.** It is 26% of the page and mostly repetition; on mobile it is a third of 17,000px. Split into "Budget snapshots (2023 series, 14)" and "Dashboard budget / schedule history", each with only its own columns, showing changes by default. The chart already carries the story.
3. **Reorder by question, not by source, and demote the org shell.** What → money → schedule + chart → where → who else → sources. One `<h1>`, one heading level for sections, breadcrumb instead of the agency tab bar.
4. **One vocabulary:** badges by meaning, one date format, muted text on the token. Cheap, and it removes the sense that four pages were stapled together.
5. **Cap the related lists at 5 with a live link** — which needs `budget_line` added to `/get/capital/projects` filters. Small, and it gives the budget-line pages a target too.

Not recommended: title-casing the City's project names (breaks `CSO`, `OH-015`); hiding the caveats to save space (move them, never remove them); merging the six money measures into fewer tiles (⚑ F — they are not a funnel).

---

## Proposed order (wireframe, not a mock)

```
breadcrumb: Capital › Projects › DDC › 850GKOH15-01
[Capital Project]  PROJECT TITLE (28px)
850GKOH15-01 · A DDC project (link) · Fixed Asset · Brooklyn
[in the current plan] [schedule published] [location published]

┌─ KEY FACTS ─────────────────────────────┬─ MAP ────────────┐
│ Planned $94.9M  Committed $60.3M        │                  │
│ Spent $11.4M    Paid (Checkbook) $9.6M  │   (top-right,    │
│ Phase: Construction Procurement         │    as today)     │
│ Forecast: 01/10/2030 · 33.4 mo later    │                  │
│ In 9 of 11 sources · not: Parks, Council│                  │
└─────────────────────────────────────────┴──────────────────┘
About this project        (attributes table, scope prose)
Money                     (6 tiles · one-line note · definitions expandable)
Schedule                  (current + actual dates · CHART directly beneath)
Budget history            (per source, changes only, collapsed)
Where it is               (districts, placed-by)
Also funded here          (commitments · 5 same-line projects → 234 more ·
                           5 Council awards → all, with the grain caveat)
Where these figures come from   (as today — this section is right)
```
