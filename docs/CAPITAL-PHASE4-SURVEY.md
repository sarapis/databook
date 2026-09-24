# Phase 4 surfaces: what they read today, and what is missing

Measured 2026-09-06 against the live local stack, before building any page.
The pass exists because the owner's one question about the Types/Categories
pages surfaced **two dependencies Phase 1 had silently not delivered**
(`capital_projects.budget_lines`, and stats scopes for the taxonomy). Asking the
same question of the other four surfaces is cheap and changes nothing.

Four surfaces, five findings, **one live defect fixed in the same change**.

---

## §5.4 Org profile → Capital Projects tab

Reads `capitalprojectsdollarscomp` — the series NYC retired 2023-10-26 —
through `/get/orgs/section/...` (`main.py:954-962`, count / `BUDG_ORIG` /
`BUDG_CURR`, all keyed `WHERE "wegov-org-id" = $1 AND "PUB_DATE" = $2`).

**The spine can serve it**: `wegov_org_id` is populated on **12,456 of 17,024**
projects (73%), and `capital_program_stats (org)` has 27 rows / `(agency)` 29.

⚠ The 27% without an org id are not a defect to fix before Phase 4 — they are
mostly the Dashboard and 2023 tails, where no org link was ever resolved. The
tab is scoped to one org, so it simply never asks about them. Worth stating on
the page rather than discovering later.

**No blocker.**

---

## §5.5 Districts → projects tab

### ✅ The Council awards dataset is ingested
`councilcapitalbudget` (`t474-a92g`) — **11,503 rows**, first ingested
2026-09-05 by Phase 1's registry work. Columns: `Reported, Fiscal_Year,
Borough, Award, Council_District, Sponsor, Title, Description, ID, Budget_Line`.

### ⚠⚠ GAP 1 — the third location method does not exist
§5.5 specifies a *how located* line reading "312 by geometry, 41 by community
board, **88 by Council award**". `capital_project_districts` carries only
**geometry** and **community_board_text**. There is no council-award method, so
that sentence cannot be rendered and those projects are not located at all.

### ⚠⚠ GAP 2 — the budget-line join is 0%, and the fix already exists unused
§5.5 wants each award linked to "projects on that line". Measured raw:

    award budget lines matching the spine:   0 of 492

The two publishers use different separators — awards write `HD D024`, `E  D001`
(note the double space); the spine writes `AG-D001`, `AG-DN025`. Normalising
both sides:

    award budget lines matching the spine: 444 of 480   (92.5%)

⭐ **`modules/budgetline.py` was built in Phase 1 to do exactly this and is
wired into nothing.** That is the same shape as the missing `budget_lines`
column: a Phase 1 deliverable that exists and has no consumer.

### ⚠⚠ GAP 3 — keying on `Council_District` silently drops a THIRD of the money

    usable (district 1-51)   10,364 rows   all 51 districts   $4,049.7M
    NOT usable                1,139 rows                      $2,050.5M

**33.6% of the award money has no valid council district.** 685 of those rows
carry an amount-shaped value in `Council_District` (e.g. `955000` beside an
`Award` of `1500000`), and they are overwhelmingly shared awards: **654 name
the Speaker, 192 a borough delegation, 680 have multiple sponsors** — against
13% Speaker among normal rows.

⚠ I first read this as a column shift from an unquoted multi-sponsor field.
**That was wrong**: `Award`, `Sponsor` and every other column are correctly
placed on those rows. What the value means is not determinable from the data,
so it is a question for the publisher, not a guess — the `docs/mocs-role-codes-inquiry.md`
precedent. Until then a district page must state the excluded total rather than
publish $4.05B as though it were the programme.

---

## §5.7 Home card

`root.blade.php:383` renders `projects_no` from `/pipeline/globstats`
(`cached_stats`, computed over the retired series):

    home card says            5,128
    spine, in current plan   12,929
    spine, all               17,024

**A one-line repoint**, and it more than doubles a public figure.

---

## §5.7 Daily briefing capital feed

Reads `capitalprojectsmilestones` (`TASK_DESCRIPTION`, `TASK_END_DATE`,
`PROJECT_ID`). Measured freshness:

    497,727 rows, PUB_DATE 20190425 .. 20231026

So the *daily* briefing surfaces capital milestones whose newest publication is
**2023-10-26** — nearly three years stale, presented beside genuinely daily
items. Replacing it is §5.7's stated intent (Dashboard schedule-history changes,
projects new to the plan, Parks updates).

---

## §5.7 Hearing brief — ⚠⚠ A LIVE SILENT FAILURE, FIXED IN THIS CHANGE

`routers/data_pipeline.py` queried `capitalprojectslist` with **four column
names that do not exist**:

    project_id           ->  projectid
    short_description    ->  description
    total_plan_commtmts  ->  plannedcommit_total
    man_agency_name      ->  magencyname

Proven against the live database rather than inferred:
`ERROR: column "project_id" does not exist`. The query sits inside
`except Exception` that only `print`s, so **every hearing brief ever generated
has had an empty capital section** and nothing surfaced it — the same family as
the search group that returned `[]` for eight weeks.

⚠ The plan said "its column names were wrong". They were, all four, and the
failure was total rather than partial.

Fixed and verified: the corrected query returns real rows (Parks, ordered by
planned commitments). A guard now pins every column the query names against
`capitalprojectslist`'s real schema, so a rename breaks the build rather than
the brief.
