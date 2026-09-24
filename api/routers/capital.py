"""Capital projects — served from the derived spine, never the retired series.

⚠⚠ WHAT THESE ENDPOINTS EXIST TO REPLACE. Every capital figure the site shows
today is computed over `capitalprojectsdollarscomp`, the OMB series NYC retired
on 2023-10-26. The four headline tiles come from `rebuild_glob_stats`, and eight
`pstats-*` families recompute them per scope — which is how the same label came
to carry two definitions ("Amount Over Budget" sums every row's difference
globally and only the negative ones per district).

These read `capital_program_stats` and `capital_projects`, so a figure has one
owner and every payload carries its vintage.

⚠ EVERY PAYLOAD CARRIES `sources`. A reader — human or another page — must be
able to see which plan version and which Dashboard reporting period a number
came from without going and looking. That is the whole failure this section is
being rebuilt to end.
"""
from __future__ import annotations

import logging
import re

import asyncpg

from fastapi import APIRouter, HTTPException

try:
    from modules import budgetline, capitalmoney, capitalslug, fmsid, wkt
except ImportError:  # pragma: no cover - path differs inside the container
    import budgetline
    import capitalslug
    import capitalmoney
    import fmsid
    import wkt

try:
    from postgrex.asyncmodel import PostgresModelAsync
except ImportError:  # pragma: no cover
    from modules.postgrex.asyncmodel import PostgresModelAsync

logger = logging.getLogger(__name__)

router = APIRouter()

_MONEY_COLUMNS = {
    "planned_usd": "planned_n",
    "adopt_usd": "adopt_n",
    "allocate_usd": "allocate_n",
    "committed_usd": "committed_n",
    "spent_usd": "spent_n",
    "checkbook_usd": "checkbook_n",
}


async def _select(sql, params=()):
    """Rows as a plain list.

    ⚠ `select_safe` returns a LIST, while `main.select` wraps the same thing as
    `{"rows": [...]}`. Assuming the wrapper here 500s on the first call — worth
    the comment because the two live one import apart.
    """
    res = await PostgresModelAsync.select_safe(sql, list(params))
    if isinstance(res, dict):
        return res.get("rows") or []
    return list(res or [])


async def _select_optional(sql, params=(), *, panel):
    """Rows for an OPTIONAL panel, or `[]` when its source table is absent.

    ⚠⚠ AN ABSENT OPTIONAL SOURCE TOOK DOWN EVERY PROJECT PAGE — measured on
    PROD, 2026-09-11, during the capital deploy. `parkscapitaltracker` has never
    existed there (NYC Parks IP-blocks the box: that feed answers **405** from
    prod and **200** from a laptop), so `_parks` raised `UndefinedTableError`
    and `/get/capital/project/{id}` 500'd for **all 17,024 projects** — the app
    turning each into a 503. One optional panel, the whole page type.

    ⭐ THE REST OF THE CODE ALREADY EXPECTS ABSENCE. The provenance block serves
    `"present": bool(parks)` for exactly this, and the profile renders a panel
    only when it has rows. `_parks` was the one place that treated a missing
    table as fatal rather than as "this publisher covers none of it".

    ⚠ THE CATCH IS NARROW ON PURPOSE, and this is the `routers/search.py::_rows`
    split one organ over. `UndefinedTableError` can only ever mean a source this
    deployment has not ingested — it is never transient and never data-dependent,
    so degrading is right. Anything else (a syntax error, a bad column, a dead
    connection) is a real fault and must keep raising, or this helper becomes the
    swallow-everything path that hides the next defect.
    """
    try:
        return await _select(sql, params)
    except asyncpg.exceptions.UndefinedTableError:
        # WARNING, not ERROR: on a fresh or partially-ingested environment this
        # is a legitimate state, and the panel simply does not render. The same
        # judgement `_rows` records for UndefinedTable/UndefinedColumn.
        logger.warning(
            "[capital] optional panel %r: its source table does not exist; "
            "serving no rows. Ingest the source to populate it.", panel)
        return []


def _money_block(row):
    """The six measures, each with its own population, plus the notes.

    ⚠⚠ POPULATIONS ARE SERVED, NEVER IMPLIED. A total summed over 5,158
    projects beside one summed over 11,650 looks like a funnel that leaks; with
    both denominators visible it reads as what it is — six different measures of
    different things. `modules/capitalmoney` owns the copy so this endpoint and
    the page cannot drift.
    """
    values = {k: (float(row[k]) if row.get(k) is not None else None)
              for k in _MONEY_COLUMNS}
    pops = {k: row.get(n) for k, n in _MONEY_COLUMNS.items()}
    return capitalmoney.payload(values, pops)


def _sources(row):
    """Which publication every figure in this payload came from."""
    return [
        {"source": "Capital Commitment Plan (CPDB)",
         "table": "capitalprojectslist",
         "version": row.get("as_of_plan")},
        {"source": "Capital Projects Dashboard",
         "table": "capprojectsbudgetsandschedule",
         "period": row.get("as_of_dashboard")},
    ]


def _coverage(row):
    """What the data does NOT cover, stated rather than left to be inferred.

    ⚠ An absent schedule is "NYC publishes none", not "this project has none",
    and the two are indistinguishable from a count alone. Measured citywide:
    8,483 of 17,024 projects carry a Dashboard schedule and 4,560 carry a
    published location.
    """
    projects = row.get("projects") or 0
    with_sched = row.get("with_schedule") or 0
    with_geo = row.get("with_geometry") or 0
    return {
        "projects": projects,
        "in_current_plan": row.get("in_plan"),
        "with_published_schedule": with_sched,
        "without_published_schedule": max(projects - with_sched, 0),
        "with_published_location": with_geo,
        "without_published_location": max(projects - with_geo, 0),
        "dropped_since_2023": row.get("dropped_since_2023"),
        "note": (
            "A project with no published schedule or location is one the City "
            "has not published those for — not one without them. Coverage "
            "differs by agency: several publish no schedule at all."
        ),
    }


@router.get("/get/capital/overview", tags=["Capital Projects"])
async def capital_overview():
    """Programme-level figures. Computes nothing that a scope row does not hold."""
    rows = await _select(
        "SELECT * FROM capital_program_stats WHERE scope_type = 'program' LIMIT 1")
    if not rows:
        # ⚠ Distinguish "not built yet" from "no capital projects". A bare empty
        # payload reads as the second.
        return {"available": False,
                "error": "capital_program_stats has no programme row — "
                         "run build_capital_stats.py"}
    row = dict(rows[0])
    return {
        "available": True,
        "projects": row.get("projects"),
        "in_current_plan": row.get("in_plan"),
        "schedule": {
            "with_published_schedule": row.get("with_schedule"),
            "in_construction": row.get("in_construction"),
            "completed": row.get("completed"),
            "late_forecast": row.get("late_forecast"),
        },
        "money": _money_block(row),
        "coverage": _coverage(row),
        "sources": _sources(row),
    }


# ⚠ A borough earns a link on a district page only above BOTH thresholds. One
# project or one percent is a label disagreeing with the geometry, not a fact
# about the district; 18 Rikers projects at 25% is. Stated in the payload so a
# reader can see the rule rather than infer it.
_BOROUGH_MIN_PROJECTS = 3
_BOROUGH_MIN_SHARE = 5.0


async def _cc_context(scope_id):
    """What a council district page shows BESIDE its own projects.

    ⚠⚠ THE DISTRICT TABLE STAYS THE FOCUS — owner decision, 2026-09-06 — and
    these are counts with links, never rows above it. That is measured, not
    stylistic: district 22's own capital work is **100 projects**, while the
    citywide and borough sets are 1,482 and 1,558. Rendering either as a table
    buries a council member's actual district work about 30 to 1.

    ⚠⚠ AND WE CANNOT PUT AN UNPLACED PROJECT IN THIS DISTRICT'S TABLE marked
    "no location". We do not know it is in this district, and printing it there
    asserts a location the City never published. The one path that might have
    rescued it does not work: community-board text already places 7,799 projects
    into COMMUNITY districts, but only 11 of 70 community districts even appear
    to sit inside a single council district — and that is a sample artefact, not
    geometry.

    The three groups are mutually exclusive and none overlaps the district's own
    table: every one requires the project to be attributed to NO council
    district. Without that, the 157 citywide projects that DO carry a district
    mapping would appear twice.
    """
    # The borough(s) this district's own projects sit in. Derived, never
    # assumed, and ONLY from projects that lie in exactly ONE council district.
    #
    # ⚠⚠ THE RESTRICTION IS THE WHOLE MEASUREMENT. A project's `borough` is a
    # single label, so a project spanning many districts says nothing about any
    # one of them: district 22 picked up BROOKLYN from the "East River Ferry
    # Route", which runs through **11** districts. Counting only
    # single-district projects, 45 of 51 districts resolve at >=90% and the
    # stragglers are genuine.
    #
    # ⭐ AND THE REMAINING DISAGREEMENT IS REAL, WHICH IS WHY NO DISTRICT IS
    # FORCED TO ONE BOROUGH. District 22 is Astoria, Queens, and 18 of its
    # projects are labelled BRONX — every one a Rikers Island jail facility
    # (GRVC, RMSC, AMKC, RNDC, OBCC). Rikers is geographically in the Bronx and
    # administratively part of Queens, and it sits in district 22. Both labels
    # are correct, and a rule that picked one would delete a real answer.
    boro_rows = await _select(
        "WITH one AS (SELECT agency_key, fms_id FROM capital_project_districts "
        "             WHERE dist_type = 'cc' GROUP BY 1, 2 HAVING count(*) = 1) "
        "SELECT " + _borough_sql() + " AS borough, count(*) AS n "
        "FROM capital_project_districts d "
        "JOIN one o ON o.agency_key = d.agency_key AND o.fms_id = d.fms_id "
        "JOIN capital_projects p "
        "  ON p.agency_key = d.agency_key AND p.fms_id = d.fms_id "
        "WHERE d.dist_type = 'cc' AND d.dist = $1 "
        "  AND " + _borough_sql() + " NOT IN ('', 'CITYWIDE') "
        "GROUP BY 1 ORDER BY 2 DESC", (str(scope_id),))
    boro_rows = [dict(r) for r in boro_rows]
    total_boro = sum((r["n"] or 0) for r in boro_rows) or 0
    # ⚠ Everything measured is SERVED; `primary` says which earn a link. A
    # borough is hidden from nobody — dropping the tail silently is how a page
    # comes to state a district's geography more confidently than the data does.
    boroughs = [{
        "borough": r["borough"],
        "projects_in_district": r["n"],
        "share_of_district": (round(100.0 * r["n"] / total_boro, 1)
                              if total_boro else None),
        "primary": bool(total_boro and (r["n"] or 0) >= _BOROUGH_MIN_PROJECTS
                        and 100.0 * r["n"] / total_boro >= _BOROUGH_MIN_SHARE),
    } for r in boro_rows]

    async def count(**filters):
        where, params = _list_filters(**filters)
        clause = (" WHERE " + " AND ".join(where)) if where else ""
        rows = await _select(
            f"SELECT count(*) AS n FROM capital_projects p{clause}", params)
        return (dict(rows[0]).get("n") if rows else 0) or 0

    # ⚠⚠ ONE `filters` DICT PER GROUP, COUNTED AND LINKED WITH THE SAME VALUE.
    # An earlier draft passed `in_cc=False` to the counting helper and repeated
    # the filters separately for the link — so the number and the list it links
    # to were two independent expressions of one intent, free to disagree. They
    # did not, but nothing stopped them, and my first guard could not see it:
    # it read the served dict while the count came from elsewhere, so deleting
    # the exclusion left the guard green and the count wrong. Derive the count
    # FROM the served filters and the two cannot diverge.
    specs = [{
        "key": "citywide",
        "label": "Citywide projects",
        "filters": {"in_cc": False, "borough": "Citywide"},
        # ⚠ Published as citywide is a FACT, not a missing value. These apply
        # to this district and every other one.
        "note": ("The City published these as citywide rather than at a "
                 "location, so they apply here and everywhere."),
    }]
    for b in [x for x in boroughs if x["primary"]]:
        specs.append({
            "key": "borough",
            "label": f"{b['borough'].title()} projects with no published location",
            "borough": b["borough"],
            "filters": {"in_cc": False, "borough": b["borough"]},
            "note": ("These may or may not be in this district — the City "
                     "publishes no location for them.")})
    specs.append({
        "key": "no_location",
        "label": "Projects with no published location at all",
        "filters": {"in_cc": False, "has_borough": False},
        "note": ("Neither a location nor a borough is published for these, so "
                 "they cannot be placed anywhere."),
    })

    groups = []
    for spec in specs:
        spec["count"] = await count(**spec["filters"])
        groups.append(spec)

    return {
        "boroughs": boroughs,
        "borough_rule": {
            "min_projects": _BOROUGH_MIN_PROJECTS,
            "min_share_pct": _BOROUGH_MIN_SHARE,
            "basis": ("boroughs of this district's own projects, counting only "
                      "projects that lie in exactly one council district"),
        },
        "groups": groups,
        "note": ("These are counted separately from this district's projects "
                 "and are never added to them. Each requires the project to be "
                 "attributed to no council district, so nothing is counted "
                 "twice."),
    }


@router.get("/get/capital/stats/{scope_type}/{scope_id}", tags=["Capital Projects"])
async def capital_scope_stats(scope_type: str, scope_id: str):
    """One scope's figures — org, agency, cd, cc, sd, nta or category.

    ⚠ The SAME definitions as the programme row, from the same table. The two
    diverged before precisely because each scope recomputed them.
    """
    # ⚠ `asset_category` and `ten_year_category` are BOTH here and are not
    # interchangeable — see the note in build_capital_stats.SCOPES. The bare
    # name `category` is deliberately absent so nobody can ask for it and get
    # whichever one happens to be wired.
    allowed = {"program", "org", "agency", "cd", "cc", "sd", "nta",
               "asset_category", "ten_year_category", "budget_line", "type"}
    if scope_type not in allowed:
        raise HTTPException(status_code=400,
                            detail=f"scope_type must be one of {sorted(allowed)}")
    # ⚠⚠ A BUDGET LINE IS PUNCTUATED FIVE WAYS AND THIS SCOPE STORES ONE OF
    # THEM. `capital_program_stats.scope_id` holds the HYPHENATED form
    # (`ED-K384`, `PW-I001`) because the spine does, while `capitalbudget` — the
    # table the budget-lines index builds its links from — holds `EP 0007` with a
    # SPACE on all 15,742 rows. So an exact match answered `found: false` for
    # every budget line reached from that index: measured 2026-09-10,
    # `EP-0007` -> 60 projects, `EP 0007` -> 0, `EP0007` -> 0. That is the
    # documented zero-that-reads-as-a-fact — "this budget line has no capital
    # projects" — and it would have shipped as a tile grid saying so.
    # ⚠ Normalised through `modules/budgetline`, which is the ONE owner of this
    # rule in both languages, rather than a second spelling of it here.
    if scope_type == 'budget_line':
        rows = await _select(
            "SELECT * FROM capital_program_stats WHERE scope_type = $1 "
            "AND " + budgetline.sql_norm('scope_id') + " = $2 LIMIT 1",
            (scope_type, budgetline.norm(scope_id)))
    else:
        rows = await _select(
            "SELECT * FROM capital_program_stats WHERE scope_type = $1 AND scope_id = $2 LIMIT 1",
            (scope_type, scope_id))
    if not rows:
        # ⚠ A scope with no row genuinely has no capital projects in the
        # crosswalk — which is different from the table being missing, and says
        # so rather than returning an ambiguous empty object.
        return {"available": True, "found": False,
                "scope_type": scope_type, "scope_id": scope_id,
                "projects": 0,
                "note": "No capital projects are linked to this scope. Where a "
                        "project has no published location it cannot be placed "
                        "in a district, so district coverage is bounded by what "
                        "the City maps."}
    row = dict(rows[0])
    return {
        "available": True, "found": True,
        "scope_type": scope_type, "scope_id": scope_id,
        "projects": row.get("projects"),
        "in_current_plan": row.get("in_plan"),
        "schedule": {
            "with_published_schedule": row.get("with_schedule"),
            "in_construction": row.get("in_construction"),
            "completed": row.get("completed"),
            "late_forecast": row.get("late_forecast"),
        },
        "money": _money_block(row),
        "coverage": _coverage(row),
        "sources": _sources(row),
        **({"not_in_this_district": await _cc_context(scope_id)}
           if scope_type == "cc" else {}),
    }


@router.get("/get/capital/money-measures", tags=["Capital Projects"])
async def capital_money_measures():
    """What each money measure means, and why they are not a funnel.

    Served on its own so a page can render the info notes without pulling a
    whole stats payload, and so the copy has exactly one origin.
    """
    return capitalmoney.payload()


# ── project profile ──────────────────────────────────────────────────────────

# ⚠⚠ THE SPINE'S MONEY COLUMNS ARE NOT THE STATS TABLE'S. Same six measures,
# different names, because the stats table aggregates. Mapping them here rather
# than renaming either keeps each builder's SQL readable; a guard pins that the
# keys on both sides are `capitalmoney`'s.
_SPINE_MONEY = {
    "planned_usd": "planned_total_usd",
    "adopt_usd": "adopt_total_usd",
    "allocate_usd": "allocate_total_usd",
    "committed_usd": "commit_total_usd",
    "spent_usd": "spent_total_usd",
    "checkbook_usd": "spent_checkbook_usd",
}


def _panel(rows, absent_reason):
    """A section that renders its "not published" line rather than nothing.

    ⚠ An empty panel and a missing panel are indistinguishable to a reader, and
    the empty one is the more common truth here — NYC publishes schedules for
    half these projects and locations for a quarter. Every panel therefore says
    which it is.

    ⚠ NOTHING IS CAPPED, and that is measured rather than assumed. Worst case
    per project, 2026-09-05: 48 commitment lines, 45 history snapshots, 215
    districts (a citywide project, correctly). All bounded and small, so a cap
    would buy nothing and cost the thing this repo has already paid for twice —
    a truncated list presented as the whole. If a future source makes one of
    these large, cap it AND serve the true total beside it.
    """
    if rows:
        return {"available": True, "count": len(rows), "rows": rows}
    return {"available": False, "count": 0, "rows": [], "reason": absent_reason}


async def _resolve_project(ident, agency=None):
    """Every spine row an identifier could mean, in candidate order.

    ⚠⚠ A BARE FMS ID DOES NOT IDENTIFY A PROJECT, and the plan's `/p/{fms_id}`
    assumed it did. Measured 2026-09-05 over the 17,024-row spine: **1,160 ids
    are carried by more than one agency, covering 2,371 rows** — 14% of the
    universe. Within the current plan alone it is only 24 ids / 48 rows, which
    is the figure §5.3 was written against and why the problem was invisible:
    the collisions live almost entirely in the Dashboard and 2023 tails that
    owner decision B pulled into scope.

    `maprojid` (`858DOIT5MYSM`) IS unique — 12,929 distinct over 12,929 non-null
    — but it exists only for current-plan rows, so it cannot be the key either.
    `(agency_key, fms_id)` is the only thing unique across all 17,024, which is
    what the table is keyed on.

    So this resolves and hands back EVERY match. The caller disambiguates or
    refuses; it never picks one, because picking silently would show a reader
    one agency's project under another agency's id.
    """
    cands = fmsid.candidates(ident)
    if not cands:
        return []

    # ⚠⚠ THE AGENCY-CONCATENATED FORM IS THE SOURCE-NATIVE IDENTITY, and matching
    # it is what makes this endpoint usable. Measured 2026-09-06 across every
    # publisher: CPDB's own published key is `maprojid`, which is byte-identical
    # to `agency_key || fms_id` on all 12,929 rows; the Parks tracker publishes
    # `NNN id` on 1,962 of 2,244; Climate Budgeting on 259,331 of 259,491. Only
    # the Dashboard's `FMS ID` and CPDB's internal `projectid` are bare — and the
    # legacy Databook URL was already `858DOIT5MYSM`. So the agency code is not
    # decoration a caller might omit; it is how the City names these projects.
    #
    # `agency_key || fms_id` is UNIQUE across all 17,024 rows, including the
    # 4,095 that have no `maprojid` because they are outside the current plan.
    # Matching it drops the number of rows unreachable by identifier alone from
    # **2,371 to 1** — `EDC`+`SOLAR2` concatenates to `EDCSOLAR2`, which is also
    # agency 856's bare id. That one still returns both choices, correctly.
    #
    # ⚠ This is a LOOKUP, not a parse: nothing has to decide where the agency
    # code ends, which is the judgement that would reintroduce the 814-project
    # truncation defect for ids that legitimately begin with digits.
    # ⚠ ONLY genuinely agency-qualified spellings go in here — the exact value
    # with any separator removed, and the explicit `NNN id` form recombined.
    # Putting the BARE candidate in this set was a bug: `856 110WLM` then
    # matched agency 856's row via the qualified form AND both agencies' rows
    # via the bare one, and a caller who had named the agency got "ambiguous".
    concat = {cands[0].replace(' ', '')}
    code = fmsid.agency_code(ident)
    if code:
        concat.add((code + fmsid.norm(ident)).upper())
    concat = sorted(concat)
    # ⚠⚠ THE PARENTHESES ARE LOAD-BEARING, and their absence was a live defect.
    # `WHERE A OR B AND C` parses as `A OR (B AND C)` — AND binds tighter than OR
    # — so an unparenthesised agency filter constrained only the fms_id branch
    # and left the maprojid branch wide open. Measured before the fix:
    # `826HED-545?agency=999` returned agency 826's project. That is exactly the
    # failure this resolver exists to prevent, arriving through SQL precedence
    # rather than through logic.
    # ⚠⚠ TIERS, NOT ONE `OR`, AND THE ORDER IS THE POINT. `fmsid.candidates`
    # returns spellings to try IN ORDER and leaves resolving to the caller;
    # ORing them all at once throws that ordering away. A form that names the
    # agency identifies a project, and a bare id may not — so a qualified match
    # WINS, and the bare fallback runs only when the qualified tier finds
    # nothing. Without this, `856 110WLM` matched agency 856 by its qualified
    # form and both agencies by the bare one, and reported itself ambiguous to a
    # caller who had already said which agency they meant.
    tail = ""
    extra = []
    if agency:
        tail = " AND upper(agency_key) = $3"
        extra = [str(agency).strip().upper()]
    order = " ORDER BY in_current_plan DESC, agency_key"

    qualified = await _select(
        "SELECT * FROM capital_projects "
        "WHERE (upper(coalesce(maprojid,'')) = $1 "
        "       OR upper(agency_key || fms_id) = ANY($2))"
        + tail + order, [cands[0], concat] + extra)
    if qualified:
        return [dict(r) for r in qualified]

    bare = await _select(
        "SELECT * FROM capital_projects WHERE upper(fms_id) = ANY($1)"
        + tail.replace("$3", "$2") + order, [cands] + extra)
    return [dict(r) for r in bare]


# ⚠⚠ TWO PERIOD SHAPES, AND THEY ARE NOT THE SAME KIND OF FACT. Measured over
# all 205,503 history rows on 2026-09-08: **0 rows** carry a period that is
# neither 6 nor 8 characters.
#
#     cpdd        YYYYMMDD   14 values, 20190425-20231026   a publication DATE
#     dashboard   YYYYMM     10 values, 202305-202605       a reporting PERIOD
#     dash_sched  YYYYMM     10 values, 202305-202605       a reporting PERIOD
#     dash_money  YYYYMM     64 values, 200609-202605       a reporting PERIOD
#
# ⚠ The Dashboard publishes a PERIOD, not a day — its months are exactly 01, 05
# and 09, three editions a year on the Commitment Plan cadence. Rendering
# `202405` as "1 May 2024" would invent a precision the City did not publish, so
# a YYYYMM value gets a month and a year and nothing finer.
_PERIOD_SHAPE = {
    "cpdd": "date",          # YYYYMMDD
    "dashboard": "month",    # YYYYMM
    "dash_sched": "month",
    "dash_money": "month",
}

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# ⚠ A STORED KEY IS NOT COPY. `cpdd` / `dash_money` are how the history table
# names its four sources; a reader has no way to know that `dash_money` means the
# Dashboard's budget history and `cpdd` a series retired in 2023. Served as a
# label beside the key, never instead of it.
_SOURCE_LABEL = {
    "cpdd": "Project detail (2023 series, retired)",
    "dashboard": "Capital Projects Dashboard",
    "dash_money": "Dashboard budget history",
    "dash_sched": "Dashboard schedule history",
}


def _period_label(source, period):
    """A period a reader can read, or the raw value if it is not a shape we know.

    ⚠ KEYED ON THE SOURCE, NOT ON THE STRING LENGTH. Length is a perfect proxy
    today (8 vs 6) and would silently mis-format the day a source changes
    cadence — the failure would be a plausible-looking wrong date, which is the
    worst kind. The expected shape is then CHECKED against the value, and a
    mismatch falls through to the raw string rather than guessing.

    ⚠ It never returns empty for a non-empty input. A blank cell where a period
    exists reads as "not published", which is a different claim.
    """
    raw = "" if period is None else str(period).strip()
    if not raw:
        return None
    want = _PERIOD_SHAPE.get(source)
    digits = raw.isdigit()
    try:
        if want == "date" and digits and len(raw) == 8:
            y, m, d = int(raw[:4]), int(raw[4:6]), int(raw[6:])
            if 1 <= m <= 12 and 1 <= d <= 31:
                return f"{d} {_MONTHS[m - 1]} {y}"
        elif want == "month" and digits and len(raw) == 6:
            y, m = int(raw[:4]), int(raw[4:])
            if 1 <= m <= 12:
                return f"{_MONTHS[m - 1]} {y}"
    except (ValueError, IndexError):  # pragma: no cover - guarded above
        pass
    return raw


async def _history(agency_key, fms_id):
    rows = await _select(
        "SELECT source, period, budget_usd, orig_budget_usd, spend_usd, phase, "
        "start_date, end_date, forecast_completion, variance_days, delay_reason "
        "FROM capital_project_history WHERE agency_key = $1 AND fms_id = $2 "
        "ORDER BY source, period", (agency_key, fms_id))
    out = []
    for r in rows:
        r = dict(r)
        # ⚠ Served BESIDE the raw value, never instead of it: `period` is the
        # key a consumer joins on, and `period_label` is for reading.
        r["period_label"] = _period_label(r.get("source"), r.get("period"))
        # ⚠ Falls back to the key rather than to blank: a source we have not
        # named is still the source of that row.
        r["source_label"] = _SOURCE_LABEL.get(r.get("source"), r.get("source"))
        # ⚠ One formatter (`_mdy_label`), beside the raw value, never instead.
        for col in ("start_date", "end_date", "forecast_completion"):
            r[col + "_label"] = _mdy_label(r.get(col))
        out.append(r)
    return out


# ⚠⚠ WHICH COLUMNS EACH SOURCE PUBLISHES IS MEASURED, NOT ASSUMED. Counted
# non-null per column per source over all 205,503 history rows, 2026-09-08:
#
#   source       rows   budget   orig   spend   phase   start     end  forecast  var  reason
#   cpdd       72,437   69,969 72,437       0       0  64,154  66,022         0    0  43,719
#   dash_money 53,218   53,218      0  49,057       0       0       0         0    0       0
#   dash_sched 24,678        0      0       0  24,457       0       0    19,911 16,587 2,581
#   dashboard  55,170   55,170      0  55,170  55,170  12,880   5,923    22,373    0       0
#
# A column null on 100% of a source's rows is not that source's column. The old
# single table UNIONed all four into ONE 14-column shape, so more than half of
# every cell was an em dash: `cpdd` showed empty Phase and Forecast columns on
# every one of its rows, `dash_sched` showed empty Budget and Spent on every one
# of its, and the page read as though the City had failed to publish things it
# never publishes in that table at all.
#
# ⭐ It also HID two columns. `cpdd` carries start_date on 64,154 rows and
# end_date on 66,022, and the old table had no column for either — the schedule
# the retired series actually published was fetched and thrown away.
# ⚠⚠ ONE FORMATTER REACHES EVERY DATE ON THE PAGE, NOT JUST THE SCHEDULE'S.
# The first pass at item K labelled the schedule, the history and the chart and
# left four panels printing `04/01/2026` — so the page still carried two date
# formats and the "one format" claim was true only of the sections that had been
# looked at. Measured on the rendered page after that pass: 7 raw `MM/DD/YYYY`
# strings survived, in commitments, climate, Parks and milestones.
#
# ⚠ The RAW value stays beside the label in every case. Consumers (MCP, the
# public API, anyone reading the payload) key on it, and this is additive.
_DATE_COLUMNS = {
    "plancommdate", "published", "construction_projected",
    "orig_start", "orig_end", "start_date", "end_date",
}


def _label_dates(rows):
    """Add `<col>_label` for every `_DATE_COLUMNS` key present on these rows."""
    for r in rows:
        for col in _DATE_COLUMNS:
            if col in r:
                r[col + "_label"] = _mdy_label(r[col])
    return rows


_HISTORY_COLUMNS = {
    "cpdd":       ["period_label", "budget_usd", "orig_budget_usd",
                   "start_date_label", "end_date_label", "delay_reason"],
    "dash_money": ["period_label", "budget_usd", "spend_usd"],
    "dash_sched": ["period_label", "phase", "forecast_completion_label",
                   "variance_days", "delay_reason"],
    "dashboard":  ["period_label", "budget_usd", "spend_usd", "phase",
                   "start_date_label", "end_date_label",
                   "forecast_completion_label"],
}

# The order they are shown in: current publications first, the retired series
# last, so a reader meets the live record before the historical one.
_HISTORY_ORDER = ["dashboard", "dash_sched", "dash_money", "cpdd"]

_HISTORY_HEADINGS = {
    "period_label": "Period", "budget_usd": "Budget",
    "orig_budget_usd": "Original budget", "spend_usd": "Spent",
    "phase": "Phase", "start_date_label": "Phase start",
    "end_date_label": "Phase end",
    "forecast_completion_label": "Forecast completion",
    "variance_days": "Change (days)", "delay_reason": "Reason given",
}


def _history_by_source(hist):
    """The same snapshots, grouped by publication, each with only its own columns.

    ⚠⚠ THIS IS THE PAGE'S LARGEST BLOCK AND MOSTLY REPETITION. Measured on
    `850GKOH15-01`: 45 rows x 14 columns, 2,505px — **26% of a 9,636px page**,
    and ~4,200px of a 17,349px phone page where the source label wrapped to five
    lines per row. Its 14 `cpdd` rows carry 0 phases, 0 forecasts, the identical
    reason string 14 times, and 4 budgets byte-identical to the row above.

    ⚠ `changed` COMPARES ONLY THE COLUMNS THIS SOURCE PUBLISHES, against the
    previous row OF THE SAME SOURCE. Comparing against the previous row of the
    merged list would mark every source-boundary row as changed, and comparing
    columns a source never publishes would mark every row unchanged on those.

    ⚠ NOTHING IS DROPPED. `changed` is a flag the page uses to choose a default
    view; every snapshot is still served, and the flat `history` key is
    untouched for consumers that already read it (MCP, the public API).

    ⚠⚠ AND THE FOUR SOURCES ARE NEVER MERGED OR DEDUPED. `dashboard` and
    `dash_sched` agree on 98% of shared (project, period) pairs and disagree on
    371 of 17,764 — measured. That disagreement is a fact about the City's two
    tables, and collapsing them would hide it while looking tidier.
    """
    groups = []
    for src in _HISTORY_ORDER:
        rows = [r for r in hist if r.get("source") == src]
        if not rows:
            continue
        cols = _HISTORY_COLUMNS.get(src)
        if cols is None:
            # ⚠ An unknown source is SHOWN, with every column it has a value
            # for, rather than skipped. A source we have not catalogued is still
            # the City publishing something about this project.
            cols = ["period_label"] + sorted(
                {k for r in rows for k, v in r.items()
                 if k not in ("source", "source_label", "period", "period_label")
                 and v not in (None, "")})

        prev, out = None, []
        for r in rows:
            sig = tuple(r.get(c) for c in cols if c != "period_label")
            row = {c: r.get(c) for c in cols}
            row["changed"] = prev is None or sig != prev
            prev = sig
            out.append(row)

        changed_n = sum(1 for r in out if r["changed"])
        groups.append({
            "source": src,
            "source_label": rows[0].get("source_label") or src,
            "retired": src == "cpdd",
            "columns": cols,
            "headings": [_HISTORY_HEADINGS.get(c, c) for c in cols],
            "rows": out,
            "count": len(out),
            "changed_count": changed_n,
            # ⚠ Phrased so a group with one snapshot does not read as a change.
            "summary": (f"{len(out)} snapshot{'s' if len(out) != 1 else ''}"
                        + (f", {changed_n} with a change"
                           if len(out) > 1 else "")),
        })
    return {
        "available": bool(groups),
        "groups": groups,
        "total": sum(g["count"] for g in groups),
        "note": ("Each publication is shown separately, with only the columns it "
                 "publishes. The Dashboard's main table and its schedule history "
                 "both publish a forecast and they do not always agree; neither "
                 "is merged into the other."),
        "reason": None if groups else
                  "No earlier budget or schedule snapshot is published for this "
                  "project.",
    }


async def _commitments(maprojid):
    """CPDB's planned-commitment lines — the detail behind `planned_usd`.

    ⚠ Keyed on `maprojid` because that is what the commitments table carries,
    and it is unique. A project outside the current plan has none, which is the
    absence being reported, not a lookup failure.
    """
    if not maprojid:
        return []
    rows = await _select_optional(
        'SELECT budgetline, projecttype, plancommdate, commitmentdescription, '
        'typcname, plannedcommit_total, plannedcommit_citycost, '
        'plannedcommit_noncitycost FROM capitalprojectscommitments '
        'WHERE maprojid = $1 ORDER BY plancommdate, budgetline', (maprojid,), panel='commitments')
    return _label_dates([dict(r) for r in rows])


# The four boundary sets `capital_project_districts` can place a project in,
# in the order the site's own boundary menu lists them. Declared here rather
# than derived from the rows, because a type with NOTHING for this project
# still has to render — an omitted row and an empty one are the same defect
# this file records everywhere else.
DISTRICT_TYPES = ("cd", "cc", "sd", "nta")

# Only `geometry` can place a project in a council, school or neighborhood
# district; the community-board text fallback fills `cd` and nothing else.
# Measured 2026-09-10 over the whole crosswalk: `cc`/`sd`/`nta` are 100%
# `geometry` (5,810 / 5,530 / 6,815 rows, 0 otherwise).
_GEOMETRY_ONLY_TYPES = ("cc", "sd", "nta")


async def _districts(agency_key, fms_id):
    """Every district this project is recorded in, ordered for display.

    ⚠⚠ THE SORT IS NUMERIC-AWARE, AND THAT IS A MEASURED FIX RATHER THAN
    TIDINESS. `dist` is TEXT, so a plain `ORDER BY dist` renders council
    districts `1, 10, 11, 12, 14, ... 2, 20, 21` — measured on the project
    carrying the most, which has **45** of them. `lpad` sorts the numeric ids
    as numbers and leaves NTA names alone, which are text and sort correctly
    as text; `cd` is unaffected either way because every code is three digits.
    """
    rows = await _select(
        "SELECT dist_type, dist, method FROM capital_project_districts "
        "WHERE agency_key = $1 AND fms_id = $2 "
        "ORDER BY dist_type, "
        "CASE WHEN dist ~ '^[0-9]+$' THEN lpad(dist, 12, '0') ELSE dist END",
        (agency_key, fms_id))
    return [dict(r) for r in rows]


def _district_groups(rows, has_geometry):
    """One entry per boundary set, ALWAYS all four, so nothing is omitted.

    ⚠⚠ A COUNT OF ZERO AND AN UNANSWERABLE COUNT ARE DIFFERENT CLAIMS, AND
    BOTH ARE REAL HERE — measured 2026-09-10 across all 9,880 placed projects:

        no published geometry   5,333 projects   cc/sd/nta are zero on ALL of
                                                 them, because geometry is the
                                                 only method that can place
                                                 those three at all
        published geometry      4,547 projects   cc 20, sd 19, nta 21, cd 1
                                                 are zero — a genuine spatial
                                                 miss, e.g. a project outside
                                                 every neighborhood polygon

    So `0` on a project with no location would assert the City placed it in no
    school district. It did not; it is in one, and we cannot say which. That
    is invariant 20 — a count that cannot be asked answers **null**, never 0 —
    arriving on the project profile. `cd` always answers a real number, because
    the community-board text fallback can place it without geometry.
    """
    by = {}
    for r in rows:
        by.setdefault(r.get("dist_type"), []).append(r)
    out = []
    for t in DISTRICT_TYPES:
        members = by.get(t, [])
        unknown = (not members and not has_geometry
                   and t in _GEOMETRY_ONLY_TYPES)
        out.append({
            "dist_type": t,
            "count": None if unknown else len(members),
            "dists": [m["dist"] for m in members],
            "methods": sorted({m["method"] for m in members if m.get("method")}),
        })
    return out


async def _geometry(agency_key, fms_id):
    rows = await _select(
        "SELECT geom_kind, centroid_lat, centroid_lng FROM capital_project_geometry "
        "WHERE agency_key = $1 AND fms_id = $2", (agency_key, fms_id))
    return [dict(r) for r in rows]


# ⚠⚠ HOW THE THREE OUTSIDE FEEDS JOIN, MEASURED 2026-09-06 — and every one of
# them publishes the AGENCY-QUALIFIED id, which is why `agency_key || fms_id` is
# the join key rather than the bare `fms_id` a reader types.
#
#     Parks tracker   `846 P-405VITO`   1,745 of 2,244 rows reach the spine
#     Climate         `035 L21FREEZE`   11,506 of 12,126 distinct ids
#     Milestones      agency + id       9,102 of 9,293 distinct pairs
#
# ⚠ Milestones is the odd one: `MANAGING_AGCY_CD` is numeric (`35`, no leading
# zero) and `PROJECT_ID` is `character(14)`, so it needs `lpad(...,3,'0')` and a
# trim. Joining it raw returns nothing at all.
_QUALIFIED = "upper(replace(btrim({col}), ' ', ''))"


async def _parks(agency_key, fms_id):
    """NYC Parks' own project tracker, where it covers this project.

    ⚠ ONE PROJECT CAN CARRY SEVERAL TRACKER ROWS — measured, 37 of 1,660 do, up
    to 13 — because Parks tracks sub-projects under one FMS id. They are
    returned as a LIST rather than aggregated: collapsing them would invent a
    single percent-complete for work Parks reports separately, and a
    `MAX(percent)` would report the furthest-along piece as the whole.
    """
    rows = await _select_optional(
        'SELECT "TrackerID" AS tracker_id, "Title" AS title, "Summary" AS summary, '
        '"CurrentPhase" AS current_phase, '
        '"DesignPercentComplete" AS design_pct, '
        '"ProcurementPercentComplete" AS procurement_pct, '
        '"ConstructionPercentComplete" AS construction_pct, '
        '"ConstructionProjectedCompletion" AS construction_projected, '
        '"TotalFunding" AS total_funding, "ProjectLiaison" AS liaison '
        'FROM parkscapitaltracker '
        'WHERE ' + _QUALIFIED.format(col='"FMSID"') + ' = $1 '
        'ORDER BY "TrackerID"', (agency_key.upper() + fms_id.upper(),), panel='parks')
    return _label_dates([dict(r) for r in rows])


async def _climate(agency_key, fms_id):
    """OMB's Climate Budgeting ratings for this project, latest vintage only.

    ⚠⚠ THE GRAIN IS (PROJECT, PUBLISHED DATE, BUDGET LINE), AND MEASURING THAT
    IS WHAT MAKES THIS PANEL SAFE. The feed holds 259,491 rows; a project
    averages **22** of them and one carries **453**. Joining it to the spine
    without aggregating is #262/#278 at scale.
      * Across vintages the rating genuinely moves — 3,182 of 12,126 projects
        carry more than one GHG rating — so this serves the LATEST published
        date and names it.
      * Within one vintage it varies only where a project spans several budget
        lines (5,965 of 27,420 project-vintage pairs). Per (project, vintage,
        budget line) it is constant: **0 of 37,245 triples disagree**.
    So: one row per budget line, at the latest vintage. That is the finest grain
    at which a single rating is a fact rather than a summary.
    """
    rows = await _select_optional(
        'SELECT DISTINCT "Published Date" AS published, "Budget Line" AS budget_line, '
        '"Budget Line Title" AS budget_line_title, "Asset Category" AS asset_category, '
        '"Greenhouse Gas (GHG) Mitigation" AS ghg_mitigation, '
        '"Flood Resiliency" AS flood_resiliency, "Heat Resiliency" AS heat_resiliency, '
        '"Heat Vulnerability Index" AS heat_vulnerability, '
        '"Flood Vulnerability Index" AS flood_vulnerability '
        'FROM climatebudgeting '
        'WHERE ' + _QUALIFIED.format(col='"Project Id"') + ' = $1 '
        '  AND to_date("Published Date", \'MM/DD/YYYY\') = ('
        '     SELECT max(to_date(c2."Published Date", \'MM/DD/YYYY\')) '
        '     FROM climatebudgeting c2 '
        '     WHERE ' + _QUALIFIED.format(col='c2."Project Id"') + ' = $1) '
        'ORDER BY 2', (agency_key.upper() + fms_id.upper(),), panel='climate')
    return _label_dates([dict(r) for r in rows])


async def _milestones(agency_key, fms_id):
    """The Oct-2023 milestone tasks, if the retired series carried any.

    ⚠ LATEST PUBLICATION ONLY. The table holds 14 vintages of the same tasks;
    returning all of them would show one task once per vintage and read as a
    schedule that changed 14 times. The vintage is served beside the rows,
    because this series was RETIRED — every date here is a 2023 statement.
    """
    rows = await _select_optional(
        'SELECT "PUB_DATE" AS pub_date, "SEQ_NUMBER" AS seq, '
        '"TASK_DESCRIPTION" AS task, "ORIG_START_DATE" AS orig_start, '
        '"ORIG_END_DATE" AS orig_end, "TASK_START_DATE" AS start_date, '
        '"TASK_END_DATE" AS end_date '
        'FROM capitalprojectsmilestones m '
        'WHERE lpad(m."MANAGING_AGCY_CD"::text, 3, \'0\') = $1 '
        '  AND upper(btrim(m."PROJECT_ID")) = $2 '
        '  AND m."PUB_DATE" = (SELECT max(m2."PUB_DATE") FROM capitalprojectsmilestones m2 '
        '     WHERE lpad(m2."MANAGING_AGCY_CD"::text, 3, \'0\') = $1 '
        '       AND upper(btrim(m2."PROJECT_ID")) = $2) '
        'ORDER BY "SEQ_NUMBER"', (agency_key, fms_id.upper()), panel='milestones')
    return _label_dates([dict(r) for r in rows])


# A related list is CAPPED, unlike `_panel`'s contents, because these are
# unbounded: the largest budget line carries hundreds of projects. So the true
# total travels beside every capped list — the `by_vendor` defect (25 of 88 rows
# under a heading implying all of them) is the one being avoided.
# ⚠ FIVE, not 25. Measured: the same-budget-line list rendered 25 of 234 rows
# as **1,650px** mid-page, and the Council awards another 25 — 2,400px of tables
# a reader scrolls past to reach the sources. Five is a sample with a link; 25
# is a table pretending to be complete. The true total is served beside it
# either way, which is the property that matters.
_RELATED_CAP = 5


async def _related_on_budget_lines(agency_key, fms_id, lines):
    """Other projects funded from the same budget line(s)."""
    if not lines:
        return {"available": False, "count": 0, "rows": [],
                "reason": "The City assigns budget lines through the Capital "
                          "Commitment Plan, and this project is not in it."}
    total = await _select(
        "SELECT count(*) AS n FROM capital_projects p "
        "WHERE p.budget_lines && $1::text[] "
        "  AND NOT (p.agency_key = $2 AND p.fms_id = $3)",
        (lines, agency_key, fms_id))
    n = (dict(total[0]).get("n") if total else 0) or 0
    rows = await _select(
        "SELECT p.agency_key, p.fms_id, p.maprojid, p.agency_acro, p.description, "
        "p.planned_total_usd, p.in_current_plan FROM capital_projects p "
        "WHERE p.budget_lines && $1::text[] "
        "  AND NOT (p.agency_key = $2 AND p.fms_id = $3) "
        "ORDER BY p.planned_total_usd DESC NULLS LAST, p.agency_key, p.fms_id "
        f"LIMIT {_RELATED_CAP}", (lines, agency_key, fms_id))
    out = [dict(r) for r in rows]
    for r in out:
        if r.get("planned_total_usd") is not None:
            r["planned_total_usd"] = float(r["planned_total_usd"])
    return {"available": bool(out), "count": n, "showing": len(out), "rows": out,
            # ⚠ THE LINK IS SERVED, NOT COMPOSED IN THE VIEW. The list is capped
            # at 5 of `count`, so "see all N" has to reach a page that answers
            # the SAME question — `/projects?budget_line=…` through the filter
            # added above, on the FIRST line, because the list itself is `&&`
            # over every line and no single query string reproduces that.
            # `lines_used` says which one, so the page can name it rather than
            # implying the link covers all of them.
            "filter": {"budget_line": lines[0]} if lines else None,
            "lines_used": lines,
            "reason": None if out else
                      "No other project is funded from this budget line."}


async def _council_awards(lines):
    """City Council capital awards naming this project's budget line(s).

    ⚠⚠ THE RAW JOIN RETURNS ZERO, AND ZERO IS INDISTINGUISHABLE FROM "THIS
    PROJECT RECEIVED NO COUNCIL AWARD". Measured 2026-09-06: the awards feed
    writes `PW DN984` and the spine writes `AG-D001`, so
    `c."Budget_Line" = ANY(p.budget_lines)` matches **0** of 11,503 award rows;
    through `budgetline.sql_norm` it matches **11,446**, over 3,725 projects.
    `modules/budgetline` is the one owner of that rule — this is its first
    consumer.

    ⚠ AN AWARD ON A BUDGET LINE IS NOT AN AWARD TO THIS PROJECT. The City states
    the line, not the project, so the payload says so and the page must repeat
    it. Reporting these as this project's funding would be an inference the
    source does not support.
    """
    if not lines:
        return {"available": False, "count": 0, "rows": [],
                "reason": "This project has no budget line to match awards on."}
    keys = sorted({budgetline.norm(x) for x in lines if budgetline.norm(x)})
    if not keys:
        return {"available": False, "count": 0, "rows": [], "reason":
                "This project has no budget line to match awards on."}
    norm_col = budgetline.sql_norm('c."Budget_Line"')
    total = await _select(
        f'SELECT count(*) AS n FROM councilcapitalbudget c WHERE {norm_col} = ANY($1)',
        (keys,))
    n = (dict(total[0]).get("n") if total else 0) or 0
    rows = await _select(
        'SELECT c."Fiscal_Year" AS fiscal_year, c."Sponsor" AS sponsor, '
        'c."Award" AS award, c."Budget_Line" AS budget_line, c."Title" AS title, '
        'c."Council_District" AS council_district, c."Borough" AS borough '
        f'FROM councilcapitalbudget c WHERE {norm_col} = ANY($1) '
        'ORDER BY c."Fiscal_Year" DESC NULLS LAST, c."Sponsor" '
        f'LIMIT {_RELATED_CAP}', (keys,))
    out = [dict(r) for r in rows]
    return {
        "available": bool(out), "count": n, "showing": len(out), "rows": out,
        "reason": None if out else
                  "No City Council capital award names this project's budget line.",
        "note": ("The City Council publishes an award against a BUDGET LINE, not "
                 "against a project. These awards fund the same line this "
                 "project is funded from; none of them is stated to be for this "
                 "project."),
    }


# ⚠⚠ THE FORECAST SERIES IS `dash_sched`, AND THE CHOICE IS MEASURED, NOT
# ARBITRARY. Two sources publish `forecast_completion`: `dashboard`
# (`capprojectsbudgetsandschedule`, 22,373 rows) and `dash_sched`
# (`capprojectsschedulehistory`, 19,911). They are NOT the same series — measured
# 2026-09-08, they **disagree on 371 of 17,764 shared (project, period) pairs**
# and 4,609 periods carry a forecast in `dashboard` alone.
#
# `dash_sched` wins because it is the schedule-history publication and it is the
# only one carrying `variance_days` and `delay_reason` — the two things that turn
# a moving line into an explanation. Drawing both would put two 98%-identical
# lines on one chart and invite a reader to read the 2% as a finding about the
# project rather than about the two tables.
#
# ⚠ The cost: 2,195 projects have a moving forecast in `dash_sched` against 2,319
# in the union, so 124 projects get no chart. The sources table already shows
# them that this publication has nothing for them.
_SLIP_SOURCE = "dash_sched"

# 30.44 days: the mean Gregorian month. Used ONLY to put a readable unit on the
# axis — the exact day count is served beside it and is what the tooltip shows,
# so nothing downstream has to trust this constant.
_DAYS_PER_MONTH = 30.44


def _mdy(value):
    """`MM/DD/YYYY` to a date, or None. Every published value is that shape —
    42,284 of 42,284 forecasts and 3,210 of 3,210 phase dates, measured — so an
    unparseable value means the source changed, and None is the honest answer."""
    import datetime
    raw = "" if value is None else str(value).strip()
    if len(raw) != 10 or raw[2] != "/" or raw[5] != "/":
        return None
    try:
        return datetime.date(int(raw[6:]), int(raw[:2]), int(raw[3:5]))
    except ValueError:
        return None


def _mdy_label(value):
    """`MM/DD/YYYY` as `23 Feb 2030`, or None.

    ⚠⚠ ONE FORMATTER, AT THE ENDPOINT. The page carried TWO date formats —
    `02/23/2030` in the schedule and the chart, `26 Oct 2023` in the history and
    the sources table — because the history's periods were formatted here and
    the phase dates were echoed raw. Two formatters for one kind of value is how
    that happened; adding a third in the view is how it would happen again.

    ⚠ Served BESIDE the raw value, never instead of it: `MM/DD/YYYY` is what the
    City published and what a consumer joins on.
    """
    d = _mdy(value)
    if d is None:
        # ⚠ Falls through to the raw string rather than to blank — a value in an
        # unfamiliar shape is still a date the City published, and an empty cell
        # reads as "not published", which is a different claim.
        raw = "" if value is None else str(value).strip()
        return raw or None
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _slippage(hist):
    """How the City's own completion forecast for this project has moved.

    ⭐ THIS IS THE ONE CHART THAT SAYS SOMETHING THE TABLES DO NOT. A phase gantt
    re-renders dates already in the Schedule table; a forecast that moves is a
    fact about the project that no single row shows.

    ⚠ NO EXTRA QUERY — it reads the history rows the endpoint already fetched.

    ⚠ IT NEEDS TWO DISTINCT FORECASTS, NOT TWO ROWS. A project republished
    unchanged across ten periods has a flat line and nothing to say; drawing it
    would imply a story where there is none. `available` is false then, with the
    reason stated rather than an empty canvas.
    """
    rows = [h for h in hist
            if h.get("source") == _SLIP_SOURCE
            and str(h.get("forecast_completion") or "").strip()]
    rows.sort(key=lambda h: str(h.get("period") or ""))

    points, base = [], None
    for h in rows:
        d = _mdy(h.get("forecast_completion"))
        if d is None:
            continue
        if base is None:
            base = d
        days = (d - base).days
        points.append({
            "period": h.get("period"),
            "period_label": _period_label(_SLIP_SOURCE, h.get("period")),
            "forecast_completion": h.get("forecast_completion"),
            "forecast_completion_label": _mdy_label(h.get("forecast_completion")),
            "days_later": days,
            "months_later": round(days / _DAYS_PER_MONTH, 1),
            # ⚠ The City's own per-period change and its own stated reason. A
            # blank reason means NYC published none — never "no delay".
            "variance_days": h.get("variance_days"),
            "delay_reason": h.get("delay_reason") or None,
        })

    distinct = {p["forecast_completion"] for p in points}
    if len(points) < 2 or len(distinct) < 2:
        return {
            "available": False, "points": [],
            "reason": ("The City has published only one completion forecast for "
                       "this project, so there is nothing to plot."
                       if points else
                       "The City publishes no completion forecast history for "
                       "this project."),
        }

    total = points[-1]["days_later"]
    return {
        "available": True,
        "points": points,
        "first": {"period_label": points[0]["period_label"],
                  "forecast_completion": points[0]["forecast_completion"],
                  "forecast_completion_label": points[0]["forecast_completion_label"]},
        "latest": {"period_label": points[-1]["period_label"],
                   "forecast_completion": points[-1]["forecast_completion"],
                   "forecast_completion_label": points[-1]["forecast_completion_label"]},
        "total_days": total,
        "total_months": round(total / _DAYS_PER_MONTH, 1),
        # ⚠ A forecast can move EARLIER, and 0 is a real answer meaning it
        # returned to where it started. The direction is named rather than left
        # to the sign of a number in a chart.
        "direction": "later" if total > 0 else ("earlier" if total < 0 else "unchanged"),
        "publications": len(points),
        "source": "capprojectsschedulehistory",
        "note": ("Each point is the completion date the City forecast in that "
                 "Capital Projects Dashboard reporting period. The baseline is "
                 "the first forecast published, not an original target — the "
                 "Dashboard's history begins in May 2023."),
        "other_series_note": ("The Dashboard's main table publishes a forecast "
                              "too. The two agree on 98% of reporting periods; "
                              "this chart reads the schedule-history "
                              "publication, which is the one carrying the City's "
                              "stated reason for each change."),
    }


# ⚠⚠ THE STRIP IS NOW EVERY MEASURE, AND IT IS DERIVED FROM `capitalmoney`
# RATHER THAN TYPED HERE. It used to be four — planned, committed, spent,
# Checkbook — with the other two reachable only in a Money section further down
# the page. The owner folded that section into the strip (2026-09-10), so the
# tiles ARE the ⚑ F set and there is no second place a measure could live.
#
# ⚠ DERIVED, NOT A HAND-TYPED SIX. A literal tuple would be a second list of the
# same measures, and the one that silently goes stale: add a seventh measure to
# `capitalmoney.MEASURES` and the page would keep showing six with nothing
# raising. Taking the keys from the module that owns them makes "the strip shows
# every measure" true by construction, in the publisher-canonical order the
# definitions below the tiles are listed in — so a tile and its definition can
# never fall out of step.
_STRIP_MONEY = tuple(m["key"] for m in capitalmoney.MEASURES)


def _key_facts(row, values, money, slip, coverage, geom):
    """What a reader asks in the first two seconds: how much, what phase, when,
    is it late, and which publications carry this project at all.

    ⚠⚠ MEASURED: THE PAGE ANSWERED NONE OF THAT ABOVE THE FOLD. On a 1440x900
    viewport the Money heading sat at **1,216px** and Schedule at **1,716px** —
    the first screen was the agency's navigation, a seven-row attribute table
    and a presence card. This block is what goes there.

    ⭐ IT RUNS NO QUERY AND COMPUTES NO FIGURE. Every value is one the endpoint
    already assembled — the money measures, the slippage total, the coverage
    counts, the geometry panel. So the strip CANNOT disagree with the sections
    it summarises: they are the same values, not a second reading of them.
    """
    labels = {m["key"]: m["label"] for m in money.get("measures", [])}
    return {
        "money": [{"key": k, "label": labels.get(k, k), "value": values.get(k)}
                  for k in _STRIP_MONEY],
        # ⚠ `None` means the City publishes no schedule for this project, which
        # the page renders as a sentence — never a blank, never a zero.
        "current_phase": row.get("current_phase"),
        "phase_is_standard": row.get("phase_is_standard"),
        "forecast_completion": row.get("forecast_completion"),
        "forecast_completion_label": _mdy_label(row.get("forecast_completion")),
        # ⚠ From the slippage block, so the headline figure and the chart cannot
        # disagree — and absent rather than 0 when the forecast never moved,
        # because "unchanged" and "no history published" are different facts.
        "slip_months": slip.get("total_months") if slip.get("available") else None,
        "slip_direction": slip.get("direction") if slip.get("available") else None,
        "has_location": bool(geom),
        "in_current_plan": row.get("in_current_plan"),
        "sources_present": coverage.get("sources_present"),
        "sources_read": coverage.get("sources_read"),
        # ⚠⚠ THIS REPLACES TWO THINGS FURTHER DOWN THE PAGE — the presence card
        # beside the header, and the "not shown for this project" line that sat
        # at **8,480px**, below every section it explained. A reader who wondered
        # at 1,700px why there was no Schedule had to scroll past everything to
        # find out. Same information, at the point the question is asked.
        "sources_absent": [r["label"] for r in coverage.get("rows", [])
                           if not r.get("present")],
    }


def _source_coverage(row, hist, commits, miles, geom, climate, parks, awards):
    """Every capital source Databook reads, and whether THIS project is in it.

    ⚠⚠ THE POINT IS THE ABSENCES. Listing only the sources that contributed
    leaves a reader unable to tell a publication that has nothing to say about
    this project from one Databook does not read at all. That distinction is the
    whole reason the empty sections above can be hidden — the absence does not
    disappear, it moves here.

    ⭐ THIS COSTS NO EXTRA QUERIES. Every value is already in hand: three flags
    on the spine row and five panels the endpoint has already fetched to render
    the page. So the table cannot disagree with the sections it summarises —
    they are the same values — and a project page does not pay ten EXISTS
    against 259k- and 497k-row tables to draw it.

    ⚠⚠ THE COUNCIL AWARDS ROW IS A DIFFERENT KIND OF CLAIM, AND `grain` SAYS SO.
    Every other row means "this project appears in that table". The Council
    publishes against a BUDGET LINE, so its row means "an award names a line this
    project is funded from" — not the same thing. A yes/no column that quietly
    mixed the two grains would be one label carrying two definitions, which is
    the defect that produced two different "Amount Over Budget" figures.

    ⚠ TABLES THAT ARE NOT PROJECT-KEYED ARE ABSENT FROM THIS LIST, NOT LISTED AS
    "no". `capitalstrategy` is keyed on project TYPE; `capitalbudget` and
    `capitalcommitmentplan` on budget line; `capitalcashflow`,
    `capitalcommitmentactuals` and `capitalfundingsource` carry no project or
    line key at all. Rendering "did not appear" against those would tell a reader
    the City left this project out of a table that has no notion of projects.

    ⚠ The three Parks tables are ONE row. Measured: `parkscapitaltracker`,
    `parkscapitalfunding` and `parkscapitallocations` cover the IDENTICAL 1,660
    projects, so listing them separately would imply three independent
    confirmations of one fact.
    """
    def hist_n(src):
        return sum(1 for h in hist if h.get("source") == src)

    rows = [
        {"key": "cpdb_plan",
         "label": "Capital Commitment Plan",
         "publisher": "NYC Department of City Planning (CPDB)",
         "tables": ["capitalprojectslist"],
         "grain": "project", "retired": False,
         "present": bool(row.get("in_current_plan")),
         "version": row.get("ccpversion"),
         "detail": None},
        {"key": "cpdb_commitments",
         "label": "Planned commitments",
         "publisher": "NYC Department of City Planning (CPDB)",
         "tables": ["capitalprojectscommitments"],
         "grain": "project", "retired": False,
         "present": bool(commits),
         "version": row.get("ccpversion"),
         "detail": f"{len(commits)} line(s)" if commits else None},
        {"key": "dashboard",
         "label": "Capital Projects Dashboard",
         "publisher": "NYC Mayor's Office of Operations",
         "tables": ["capprojectsbudgetsandschedule", "capprojectsbudgetandspend"],
         "grain": "project", "retired": False,
         "present": bool(row.get("in_dashboard")),
         # ⚠ A reporting PERIOD, so month and year — `202309` is not a day.
         "version": _period_label("dashboard", row.get("dash_period")),
         "detail": None},
        {"key": "dash_money",
         "label": "Dashboard budget history",
         "publisher": "NYC Mayor's Office of Operations",
         "tables": ["capprojectsbudgetspendhistory"],
         "grain": "project", "retired": False,
         "present": hist_n("dash_money") > 0,
         "version": None,
         "detail": (f"{hist_n('dash_money')} snapshot(s)"
                    if hist_n("dash_money") else None)},
        {"key": "dash_sched",
         "label": "Dashboard schedule history",
         "publisher": "NYC Mayor's Office of Operations",
         "tables": ["capprojectsschedulehistory"],
         "grain": "project", "retired": False,
         "present": hist_n("dash_sched") > 0,
         "version": None,
         "detail": (f"{hist_n('dash_sched')} snapshot(s)"
                    if hist_n("dash_sched") else None)},
        {"key": "geometry",
         "label": "Published location",
         "publisher": "NYC Department of City Planning (CPDB points and polygons)",
         "tables": ["capital_project_geometry"],
         "grain": "project", "retired": False,
         "present": bool(geom),
         "version": None,
         "detail": (geom[0].get("geom_kind") if geom else None)},
        {"key": "climate",
         "label": "Climate Budgeting",
         "publisher": "NYC Office of Management and Budget",
         "tables": ["climatebudgeting"],
         "grain": "project", "retired": False,
         "present": bool(climate),
         # ⚠ THE LABEL, not the raw value. This one cell was the last place on
         # the whole page still printing `05/12/2026` after item K — every other
         # `version` here is already prose (`fisa_2026`, `May 2026`,
         # `26 Oct 2023`), so the odd one out read as a different KIND of
         # value rather than the same fact in a second format.
         "version": (climate[0].get("published_label") if climate else None),
         "detail": (f"{len(climate)} budget line(s) rated" if climate else None)},
        {"key": "parks",
         "label": "NYC Parks project tracker",
         "publisher": "NYC Department of Parks and Recreation",
         "tables": ["parkscapitaltracker", "parkscapitalfunding",
                    "parkscapitallocations"],
         "grain": "project", "retired": False,
         "present": bool(parks),
         "version": None,
         "detail": (f"{len(parks)} tracked item(s)" if parks else None)},
        {"key": "cpdd_2023",
         "label": "Project detail (2023 series)",
         "publisher": "NYC Office of Management and Budget",
         "tables": ["capitalprojectsdollarscomp"],
         "grain": "project", "retired": True,
         "present": bool(row.get("in_cpdd_2023")),
         # ⚠ Formatted the same way the history periods are — `20231026` is a
         # publication date, and printing the raw integer is the stored-key
         # defect one column over.
         "version": _period_label("cpdd", row.get("cpdd_pub_date")),
         "detail": None},
        {"key": "milestones_2023",
         "label": "Project milestones (2023 series)",
         "publisher": "NYC Office of Management and Budget",
         "tables": ["capitalprojectsmilestones"],
         "grain": "project", "retired": True,
         "present": bool(miles),
         "version": (_period_label("cpdd", miles[0].get("pub_date"))
                     if miles else None),
         "detail": f"{len(miles)} task(s)" if miles else None},
        {"key": "council_awards",
         "label": "City Council capital awards",
         "publisher": "New York City Council",
         "tables": ["councilcapitalbudget"],
         "grain": "budget_line", "retired": False,
         "present": bool(awards.get("count")),
         "version": None,
         "detail": (f"{awards.get('count')} award(s) on this project's budget "
                    f"line(s)" if awards.get("count") else None)},
    ]

    present = sum(1 for r in rows if r["present"])
    return {
        "rows": rows,
        "sources_read": len(rows),
        "sources_present": present,
        "note": ("Every capital source Databook reads that can be keyed to a "
                 "project. A source marked absent has nothing published about "
                 "this project — it is not a gap in Databook's coverage of that "
                 "source."),
        "grain_note": ("The City Council publishes an award against a BUDGET "
                       "LINE rather than a project, so that row means an award "
                       "names a line this project is funded from — not that the "
                       "Council named this project."),
        "excluded_note": ("Capital tables that are not keyed to a project are "
                          "not listed: the Ten-Year Strategy is keyed on project "
                          "type, the Capital Budget and Commitment Plan on "
                          "budget line, and cash flow, commitment actuals and "
                          "funding sources carry neither."),
        "retired_note": ("The 2023 series were retired by NYC on 26 October "
                         "2023. Anything from them describes the project as it "
                         "was then."),
    }


@router.get("/get/capital/project/{ident}", tags=["Capital Projects"])
async def capital_project(ident: str, agency: str = None):
    """One project — spine row, money, schedule, history, commitments, place.

    ⚠ `ident` may be a bare FMS id, CPDB's concatenated `maprojid`, or the
    space-separated form the Parks and Climate feeds publish; `modules/fmsid`
    owns which of those to try and in what order. When an id is carried by more
    than one agency this returns the choices rather than guessing — pass
    `?agency=` to pick one.
    """
    rows = await _resolve_project(ident, agency)

    if not rows:
        # ⚠ "No project with this id" is a real answer and says so. Returning a
        # bare 404 would make an id that exists under another agency look absent.
        return {"available": True, "found": False, "ident": ident,
                "tried": fmsid.candidates(ident),
                "note": "No capital project carries this id. Ids from the "
                        "Parks and Climate feeds are published with a "
                        "three-digit agency prefix; both forms are tried."}

    if len(rows) > 1:
        # ⚠⚠ NEVER PICK. See `_resolve_project` — 1,160 ids are shared.
        return {
            "available": True, "found": False, "ambiguous": True,
            "ident": ident,
            "note": ("This project id is used by more than one agency, so it "
                     "does not identify a project on its own. Choose an agency."),
            "choices": [{
                "agency_key": r.get("agency_key"),
                "agency_name": r.get("agency_name") or r.get("agency_acro"),
                "fms_id": r.get("fms_id"),
                "maprojid": r.get("maprojid"),
                "description": r.get("description"),
                "in_current_plan": r.get("in_current_plan"),
            } for r in rows],
        }

    row = rows[0]
    ak, fid = row["agency_key"], row["fms_id"]

    hist = await _history(ak, fid)
    commits = await _commitments(row.get("maprojid"))
    dists = await _districts(ak, fid)
    geom = await _geometry(ak, fid)
    parks = await _parks(ak, fid)
    climate = await _climate(ak, fid)
    miles = await _milestones(ak, fid)
    lines = list(row.get("budget_lines") or [])
    slip = _slippage(hist)
    same_line = await _related_on_budget_lines(ak, fid, lines)
    awards = await _council_awards(lines)

    values = {k: (float(row[c]) if row.get(c) is not None else None)
              for k, c in _SPINE_MONEY.items()}

    # ⚠ Populations are a SCOPE concept. On one project the honest statement is
    # whether the City publishes each measure for it, which `value: None`
    # already carries — passing a count of 1 or 0 would invent a denominator.
    money = capitalmoney.payload(values, None, scope="project")
    coverage = _source_coverage(row, hist, commits, miles, geom, climate, parks,
                                awards)

    sched_hist = [h for h in hist if h["source"] == "dash_sched"]
    latest_sched = sched_hist[-1] if sched_hist else {}

    return {
        "available": True, "found": True,
        "id": {"agency_key": ak, "fms_id": fid, "maprojid": row.get("maprojid")},
        "header": {
            "description": row.get("description"),
            "agency_name": row.get("agency_name"),
            "agency_acro": row.get("agency_acro"),
            "agency_code": row.get("agency_code"),
            "sponsor_agency": row.get("sponsor_agency"),
            "wegov_org_id": row.get("wegov_org_id"),
            "type_category": row.get("type_category"),
            "ten_year_category": row.get("ten_year_category"),
            "borough": row.get("borough"),
            "community_board": row.get("community_board"),
            # ⚠ MULTI-VALUED BECAUSE THEY ARE — 1 to 34 budget lines per
            # project, mean 1.45. A project on three lines is on three lines;
            # picking one would make the Council-award match below look
            # arbitrary.
            "budget_lines": list(row.get("budget_lines") or []),
            "project_types": list(row.get("project_types") or []),
            # ⚠ The only scope prose the City publishes for these projects, and
            # it comes from the RETIRED 2023 series — so it is labelled with its
            # vintage rather than presented as current.
            "scope_2023": row.get("cpdd_scope_text"),
        },
        # ⚠ Which publications this project appears in, stated rather than
        # implied. A project absent from the current plan is one NYC has stopped
        # planning — a finding, not a gap in our data.
        "presence": {
            "in_current_plan": row.get("in_current_plan"),
            "in_dashboard": row.get("in_dashboard"),
            "in_2023_series": row.get("in_cpdd_2023"),
            "note": ("A project not in the current plan appeared in an earlier "
                     "publication and no longer appears in this one."),
        },
        "money": money,
        "key_facts": _key_facts(row, values, money, slip, coverage, geom),
        "schedule": {
            "available": bool(row.get("current_phase")),
            "reason": None if row.get("current_phase") else
                      "The City publishes no Capital Projects Dashboard "
                      "schedule for this project.",
            "current_phase": row.get("current_phase"),
            "phase_is_standard": row.get("phase_is_standard"),
            "phase_start": row.get("phase_start"),
            "phase_start_label": _mdy_label(row.get("phase_start")),
            "forecast_phase_end": row.get("forecast_phase_end"),
            "forecast_phase_end_label": _mdy_label(row.get("forecast_phase_end")),
            "forecast_completion": row.get("forecast_completion"),
            "forecast_completion_label": _mdy_label(row.get("forecast_completion")),
            # ⚠ Labels beside the raw values, ONE formatter for both — see
            # `_mdy_label`. The page prints the label; a consumer joins on the
            # `MM/DD/YYYY` the City published.
            "actual": {
                "design_start": row.get("actual_design_start"),
                "design_end": row.get("actual_design_end"),
                "procurement_start": row.get("actual_procurement_start"),
                "procurement_end": row.get("actual_procurement_end"),
                "construction_start": row.get("actual_construction_start"),
                "construction_end": row.get("actual_construction_end"),
            },
            "actual_labels": {
                "design_start": _mdy_label(row.get("actual_design_start")),
                "design_end": _mdy_label(row.get("actual_design_end")),
                "procurement_start": _mdy_label(row.get("actual_procurement_start")),
                "procurement_end": _mdy_label(row.get("actual_procurement_end")),
                "construction_start": _mdy_label(row.get("actual_construction_start")),
                "construction_end": _mdy_label(row.get("actual_construction_end")),
            },
            "variance_days": latest_sched.get("variance_days"),
            # ⚠ 296 of 372 delayed rows carry a reason. A blank one means NYC
            # published none, and must not read as "no delay".
            "delay_reason": latest_sched.get("delay_reason"),
        },
        "history": _panel(hist,
                          "No earlier budget or schedule snapshot is published "
                          "for this project."),
        "history_by_source": _history_by_source(hist),
        "commitments": _panel(commits,
                              "No planned commitment lines are published — a "
                              "project outside the current Capital Commitment "
                              "Plan has none."),
        "districts": dict(_panel(dists,
                            "This project has no published location, so it "
                            "cannot be placed in a district."),
                          # ⚠ Served beside `rows`, never instead of it: the map
                          # and the placement line both read the flat rows, and
                          # `groups` answers a different question — what the
                          # reader is told about EACH boundary set, including
                          # the ones with nothing.
                          groups=_district_groups(dists, bool(geom))),
        "geometry": _panel(geom,
                           "The City publishes no location for this project."),
        "parks_tracker": _panel(parks,
                                "NYC Parks' capital tracker does not cover this "
                                "project. It covers Parks projects only."),
        "climate": _panel(climate,
                          "OMB's Climate Budgeting publication does not rate "
                          "this project."),
        "milestones_2023": _panel(miles,
                                  "The retired 2023 milestone series published "
                                  "no tasks for this project."),
        "related": {"same_budget_line": same_line, "council_awards": awards},
        "slippage": slip,
        "source_coverage": coverage,
        "sources": _sources({"as_of_plan": row.get("ccpversion"),
                             "as_of_dashboard": row.get("dash_period")}),
    }


# ── list, map, and one project's footprint ───────────────────────────────────

# ⚠⚠ ORDERING IS A WHITELIST, and the map is what it maps to — never the raw
# parameter. A caller-supplied ORDER BY is an injection; a caller-supplied
# COLUMN NAME that merely looks safe is still a way to sort by something the
# page cannot explain.
_SORTS = {
    "planned": "planned_total_usd",
    "adopted": "adopt_total_usd",
    "committed": "commit_total_usd",
    "spent": "spent_total_usd",
    "agency": "agency_acro",
    "id": "fms_id",
}
_LIST_MAX_PER_PAGE = 200


def _page(value, default=1, minimum=1, maximum=None):
    """A page number that cannot go below 1, as an INT.

    ⚠⚠ BOTH HALVES ARE LOAD-BEARING, and this repo has already paid for it.
    #321: pagination markup emitted a live href on a disabled control, a crawler
    walked `page=0`, `-1`, `-2` downward with no floor, and the raw value reached
    a cache key — so `'1'`, `1` and `'01'` minted three entries for one page and
    a 1.2 GB cache. Floor AND cast, every time.
    """
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    if n < minimum:
        return minimum
    if maximum is not None and n > maximum:
        return maximum
    return n


# ⚠⚠ TWO NAMES FOR ONE BOROUGH, AND MIXED CASE. Measured 2026-09-06 on the
# spine: `Manhattan` 1,161 vs `MANHATTAN` 708 (two publication vintages), and
# **`RICHMOND` 194 is `STATEN ISLAND` 399** — the county name and the borough
# name for the same place. Counting them separately understates Staten Island by
# a third and invents a sixth borough. One owner for the spelling.
_BOROUGH_ALIASES = {"RICHMOND": "STATEN ISLAND"}


def _norm_borough(value):
    if value is None:
        return ""
    v = " ".join(str(value).strip().upper().split())
    return _BOROUGH_ALIASES.get(v, v)


def _borough_sql(col="p.borough"):
    """The stored column, normalised the SAME way `_norm_borough` normalises a
    caller's value.

    ⚠⚠ NORMALISING ONLY ONE SIDE IS WORSE THAN NORMALISING NEITHER. My first
    draft canonicalised the input to STATEN ISLAND and compared it against the
    raw column, which silently dropped the 194 rows stored as RICHMOND — a
    filter that looks careful and returns a third fewer projects than it should.
    Both sides go through the same mapping, and a guard pins that they agree.
    """
    expr = f"upper(trim(coalesce({col},'')))"
    for src, dst in sorted(_BOROUGH_ALIASES.items()):
        expr = f"CASE WHEN {expr} = '{src}' THEN '{dst}' ELSE {expr} END"
    return expr


def _norm_phase(value):
    """A phase spelling, normalised by CASE and whitespace and nothing else.

    ⚠ Deliberately not `_norm_borough`'s shape: there is no alias map here,
    because the only collisions measured on this column are case-only. Adding
    aliases would be where a taxonomy quietly gets invented.
    """
    if value is None:
        return ""
    return " ".join(str(value).strip().split()).lower()


def _phase_sql(col="p.current_phase"):
    """The stored column normalised the SAME way `_norm_phase` normalises input."""
    return f"lower(btrim(coalesce({col},'')))"


# ⚠⚠ THE AGENCY FILTER SPLIT 20 AGENCIES IN TWO, AND HALF OF EACH WAS LABELLED
# WITH A BARE NUMBER. Measured 2026-09-10: `agency_acro` is NULL on **4,095 of
# 17,024** spine rows, and that set is EXACTLY the 4,095 projects outside the
# current Capital Commitment Plan — 0 in-plan rows lack it. So the City names the
# agency only on the current plan, and the older work carries the FMS code alone.
#
# The option list built its value as `coalesce(agency_acro, agency_key)`, so the
# dropdown offered both halves as separate entries:
#
#     Department of Parks and Recreation  2,798   and   846   631
#     Department of Design and Construction 2,202  and   850   814
#     Department of Transportation          785    and   841   345
#
# `850` was the third-largest entry in the list and named nothing. Choosing the
# agency by name returned 82% of its projects.
#
# ⚠⚠ AND THE MERGE IS NOT UNCONDITIONAL, BECAUSE ONE KEY IS THREE ORGANISATIONS.
# `801` carries SBS (809 rows, org 170010801), Brooklyn Navy Yard (71, org
# 112137138) and the Trust for Governors Island (31, org 272683349) — three
# different `wegov_org_id`s. A `max(agency_acro)` merge would fuse them and
# attribute 121 unattributable rows to whichever name sorted last. So a key is
# resolved ONLY where it carries exactly one acronym; `801`'s three keep their
# own options and its 121 unnamed rows keep theirs.
#
# ⚠ Every acronym maps to exactly ONE key (measured: 0 acronyms span two), which
# is what makes resolving the CALLER's value a single uncorrelated subquery
# rather than a per-row lookup. The correlated form was measured at **1,165ms**
# over 657,480 buffers; this is **4.9ms**.
_AGENCY_RESOLVE_SQL = """(
    upper(coalesce(p.agency_acro, p.agency_key)) = $?
    OR (p.agency_acro IS NULL AND p.agency_key = (
          SELECT a.agency_key FROM capital_projects a
          WHERE upper(a.agency_acro) = $?
            AND (SELECT count(DISTINCT b.agency_acro) FROM capital_projects b
                 WHERE b.agency_key = a.agency_key) = 1
          LIMIT 1)))"""

# The same rule for the OPTION list, which needs it per row rather than per
# caller. ⚠ TWO SQL TEXTS FOR ONE RULE, so they are pinned by a BEHAVIOURAL
# guard rather than by looking alike: every option the list emits must be
# reproduced, to the row, by the filter for that option's value. That check runs
# against the real database in `scripts/headless/verify_agency_options.py`.
_AGENCY_VOCAB_CTE = """WITH voc AS (
    SELECT agency_key,
           CASE WHEN count(DISTINCT agency_acro) = 1 THEN max(agency_acro) END AS acro,
           CASE WHEN count(DISTINCT agency_name) = 1 THEN max(agency_name) END AS nm
    FROM capital_projects GROUP BY 1)"""
_AGENCY_VALUE_SQL = "upper(coalesce(p.agency_acro, v.acro, p.agency_key))"


def _list_filters(agency=None, category=None, phase=None, borough=None,
                  in_plan=None, has_schedule=None, has_location=None, q=None,
                  has_borough=None, in_cc=None, budget_line=None,
                  org=None, ten_year_category=None):
    """WHERE fragments and params for the project list.

    ⚠ `has_location` reads the geometry table rather than a column on the spine,
    because "has a published location" is a fact about what the City published,
    not an attribute of the project.

    ⚠⚠ EVERY COLUMN IS QUALIFIED `p.`, AND THAT IS NOT TIDINESS. These fragments
    are shared by the list (which selects from `capital_projects p` alone) and
    the map (which JOINs `capital_project_geometry g`), and both tables carry
    `agency_key` and `fms_id`. Unqualified, the map 500s with
    `AmbiguousColumnError` the moment any filter is applied — measured, on
    `?agency=DDC`, while the unfiltered map returned 4,560 features perfectly.
    A caller that only ever exercises the default would never see it.
    """
    where, params = [], []

    def add(sql, value):
        params.append(value)
        where.append(sql.replace("$?", f"${len(params)}"))

    if agency:
        # ⚠ TWO PARAMS, ONE VALUE — `add` substitutes one placeholder per call,
        # and this fragment names the caller's value twice.
        v = str(agency).strip().upper()
        params.append(v)
        first = len(params)
        params.append(v)
        where.append(_AGENCY_RESOLVE_SQL
                     .replace("$?", f"${first}", 1)
                     .replace("$?", f"${len(params)}", 1))
    if category:
        # ⚠⚠ THIS IS THE ASSET CLASS, NOT THE TEN-YEAR CATEGORY, and the bare name
        # is the ambiguity this repo already retired once. `p.type_category` is
        # CPDB's coarse 3-value asset class ("Fixed Asset", …);
        # `p.ten_year_category` is the 138-value Ten-Year Strategy taxonomy the
        # category PAGES are keyed on. Two things called `category` is what
        # produced two different "Amount Over Budget" figures, and it is why
        # `/get/capital/stats/category/...` now 400s and demands
        # `asset_category` or `ten_year_category`.
        # ⚠ The name is kept HERE because `/projects` already sends it and
        # renaming a live query parameter is a separate decision; the new scope
        # below is spelled out in full rather than overloading this one.
        add("p.type_category = $?", category)
    if ten_year_category:
        # ⚠ SLUGGED ON BOTH SIDES THROUGH THE ONE RULE (`_SLUG_SQL` / `_slug`).
        # 12 of 138 categories carry a comma, so `REPLACE(cat,' ','-')` never
        # matched Laravel's slug for those and the old endpoints fell through to
        # a loose `ILIKE '%…%'` — which is worse than missing, since `sewers`
        # also matches `COMBINED SEWERS AND WATER MAINS` and a category page
        # could list another category's projects.
        add(_SLUG_SQL.format(col="p.ten_year_category") + " = $?",
            str(ten_year_category).lower())
    if org:
        # ⚠ `::text`, matching `/get/capital/projects/by-org/{org_id}`. The
        # column is numeric and the caller's value arrives from a URL; comparing
        # them as text is what that endpoint already does, so the map and the
        # tab's list resolve an org identically.
        add("p.wegov_org_id::text = $?", str(org))
    if phase:
        # ⚠⚠ CASE-INSENSITIVE ON BOTH SIDES, FOR THE SAME REASON AS BOROUGH, and
        # it is measured: the spine carries `Construction Procurement` 317 AND
        # `Construction procurement` 6, `(On-Hold)` 26 AND `(On-hold)` 42. An
        # equality test on the raw value therefore offers the reader a phase and
        # then silently hides part of it — 6 projects and 26 projects
        # respectively. Both sides go through `lower(trim(...))`.
        #
        # ⚠ CASE ONLY. The parentheses are NOT collapsed: `(Construction)` 18 is
        # not `Construction` 825. The Dashboard emits five standard phases plain
        # and every other status parenthesised, meaning "no schedule is
        # required" rather than "this is its phase" — merging them would be a
        # judgement about what the publisher meant, not a normalisation.
        add(_phase_sql() + " = $?", _norm_phase(phase))
    if borough:
        # ⚠ Normalised on BOTH sides. The column is mixed-case across vintages
        # (1,161 "Manhattan" against 708 "MANHATTAN"), so an equality test on the
        # raw value silently returns the wrong half of a borough.
        add(_borough_sql() + " = $?", _norm_borough(borough))
    if q:
        add("p.description ILIKE $?", f"%{str(q).strip()}%")
    if budget_line:
        # ⚠⚠ NORMALISED ON BOTH SIDES, THROUGH `modules/budgetline`. The spine
        # stores `AG-D001`; a caller will send `AG D001` or `AGD001`, because
        # five sources punctuate the same line five ways. A raw comparison
        # matches 0 rows, and 0 reads exactly like "no projects on this line" —
        # the same defect as the RICHMOND borough case, on a new column.
        #
        # ⚠ `unnest`, not `&&`. The array holds the RAW spelling, so the GIN
        # index (`idx_capital_projects_budget_lines`) cannot serve a normalised
        # match and this plans as a seq scan. Measured 2026-09-08: **35ms** over
        # 17,024 rows, 1,372 buffers, all shared hits — acceptable at page
        # scale, which is why there is no normalised column. If this ever moves
        # to a hot path, add `budget_lines_norm text[]` in the builder and index
        # THAT; do not reach for `&&` on the raw array.
        add("EXISTS (SELECT 1 FROM unnest(p.budget_lines) bl WHERE "
            + budgetline.sql_norm("bl") + " = $?)", budgetline.norm(budget_line))

    if in_plan is not None:
        where.append("p.in_current_plan IS " + ("TRUE" if in_plan else "FALSE"))
    if has_schedule is not None:
        where.append("p.current_phase IS " + ("NOT NULL" if has_schedule else "NULL"))
    if has_borough is not None:
        where.append(
            "coalesce(trim(p.borough),'') " + ("<> ''" if has_borough else "= ''"))
    if in_cc is not None:
        # ⚠ "Attributed to a council district" is not the same as "has a
        # location": 33 projects carry published geometry that falls in NO
        # council district — DOT citywide work, DEP and Parks sites. Keyed on the
        # district crosswalk, which is what a district page actually asks.
        where.append(
            ("EXISTS" if in_cc else "NOT EXISTS") +
            " (SELECT 1 FROM capital_project_districts dx "
            "WHERE dx.agency_key = p.agency_key AND dx.fms_id = p.fms_id "
            "AND dx.dist_type = 'cc')")
    if has_location is not None:
        where.append(
            ("EXISTS" if has_location else "NOT EXISTS") +
            # ⚠ Aliased `gx`, not `g`: the map query already binds `g` to the
            # geometry table, and reusing it here would silently correlate the
            # subquery to the OUTER row instead of testing existence.
            " (SELECT 1 FROM capital_project_geometry gx "
            "WHERE gx.agency_key = p.agency_key AND gx.fms_id = p.fms_id)")
    return where, params


@router.get("/get/capital/projects/filters", tags=["Capital Projects"])
async def capital_project_filters():
    """The option lists the project index offers, WITH their counts.

    ⚠⚠ THE OPTIONS ARE GROUPED THE SAME WAY THE FILTER MATCHES, and that is the
    whole reason this is an endpoint rather than a hand-kept list in a template.
    Boroughs are folded through `_borough_sql`, so `RICHMOND` (229) and
    `Staten Island` (659) offer ONE option worth 888 — offering both is the
    defect `_norm_borough` exists to prevent, moved up one layer into the UI.
    Phases are folded through `_phase_sql` for the same reason
    (`Construction Procurement` 317 + `Construction procurement` 6).

    ⚠ Every option carries `n`. An option that would return nothing is not a
    filter, it is a dead end, and a reader cannot tell the two apart from the
    label alone.

    ⚠ `blank` is served for borough, category and phase as its own count rather
    than dropped: "the City published no borough for 5,152 projects" is a
    finding about the data, and a select that silently omits them implies the
    listed options cover everything.
    """
    agencies = await _select(
        _AGENCY_VOCAB_CTE +
        " SELECT " + _AGENCY_VALUE_SQL + " AS value, "
        "       max(coalesce(p.agency_name, v.nm, p.agency_acro, p.agency_key)) AS label, "
        "       count(*) AS n "
        "FROM capital_projects p JOIN voc v USING (agency_key) "
        "GROUP BY 1 ORDER BY 3 DESC, 1")

    categories = await _select(
        "SELECT coalesce(p.type_category,'') AS value, count(*) AS n "
        "FROM capital_projects p GROUP BY 1 ORDER BY 2 DESC")

    phases = await _select(
        # ⚠ `label` is a REPRESENTATIVE stored spelling (the most common one),
        # never a re-cased invention: showing "Construction procurement" when the
        # City writes "Construction Procurement" would be this page correcting a
        # publisher it is supposed to be quoting. `value` is the folded key the
        # filter matches on, so label and value can differ and that is fine.
        "SELECT " + _phase_sql() + " AS value, "
        "       (array_agg(p.current_phase ORDER BY p.current_phase))[1] AS label, "
        "       bool_or(p.phase_is_standard) AS is_standard, count(*) AS n "
        "FROM capital_projects p WHERE p.current_phase IS NOT NULL "
        "GROUP BY 1 ORDER BY 4 DESC")

    boroughs = await _select(
        "SELECT " + _borough_sql() + " AS value, count(*) AS n "
        "FROM capital_projects p GROUP BY 1 ORDER BY 2 DESC")

    flags = await _select(
        "SELECT count(*) FILTER (WHERE p.in_current_plan) AS in_plan, "
        "  count(*) FILTER (WHERE NOT p.in_current_plan) AS not_in_plan, "
        "  count(*) FILTER (WHERE p.current_phase IS NOT NULL) AS has_schedule, "
        "  count(*) FILTER (WHERE p.current_phase IS NULL) AS no_schedule, "
        "  count(*) FILTER (WHERE coalesce(trim(p.borough),'') <> '') AS has_borough, "
        "  count(*) FILTER (WHERE coalesce(trim(p.borough),'') = '') AS no_borough, "
        "  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM capital_project_geometry gx "
        "     WHERE gx.agency_key = p.agency_key AND gx.fms_id = p.fms_id)) AS has_location, "
        "  count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM capital_project_geometry gx "
        "     WHERE gx.agency_key = p.agency_key AND gx.fms_id = p.fms_id)) AS no_location, "
        "  count(*) AS projects "
        "FROM capital_projects p")

    def rows(res, blank_key="value"):
        out = []
        for r in res:
            r = dict(r)
            r["n"] = int(r.get("n") or 0)
            out.append(r)
        return out

    def agency_rows(res):
        """⚠ AN OPTION THAT NAMES NOTHING MUST SAY SO.

        After resolution the only entries still labelled with their own FMS code
        are the ones the spine cannot attribute: `801`, whose 121 rows belong to
        one of SBS, Brooklyn Navy Yard or the Trust for Governors Island and
        nothing says which. Leaving the label as `801` puts a bare number in a
        list of agency names; inventing one would attribute those rows to an
        organisation that may not own them. So it states what is true.

        ⚠ THE VALUE IS UNTOUCHED — only the label. The filter matches on the
        value, and a label that changed it would break the option.
        """
        out = []
        for r in rows(res):
            label = (r.get("label") or "").strip()
            if label == r.get("value") and label.isdigit():
                r["label"] = f"Not identified (agency code {label})"
                r["unidentified"] = True
            out.append(r)
        return out

    return {
        "available": True,
        "agencies": agency_rows(agencies),
        "categories": rows(categories),
        "phases": rows(phases),
        "boroughs": rows(boroughs),
        "flags": dict(flags[0]) if flags else {},
        "sorts": sorted(_SORTS),
        "note": ("Counts are over every project in the spine, unfiltered — an "
                 "option's `n` is what it would match on its own, not within "
                 "the filters already applied."),
    }


# ⚠⚠ THE TEN-YEAR CATEGORY PAGE LISTED PROJECTS FROM A SERIES NYC RETIRED ON
# 2023-10-26. `/get/capitalprojects/by_category/` is `SELECT * FROM
# capitalprojectsdollarscomp` — **8,740 distinct project ids against the spine's
# 17,024** (12,929 in the current plan). So the page understated its own
# category by roughly half, on a page whose whole job is to size one.
#
# ⚠ THE SLUG IS MATCHED THE WAY LARAVEL BUILDS IT, NOT BY A LOOSE ILIKE. The old
# endpoint fell back to `ILIKE '%…%'`, so `sewers` would also match
# `COMBINED SEWERS AND WATER MAINS`. Here the comparison is on the SLUG of the
# stored value, computed the same way on both sides, so it is exact or nothing.
# ⚠ `[^a-z0-9]+` collapsed and trimmed — Laravel's `Str::slug` lowercases,
# replaces every run of non-alphanumerics with one `-`, and strips the ends.
# ⚠⚠ THE SLUG RULE MOVED TO `modules/capitalslug` ON 2026-09-10, because it
# gained a SECOND consumer: `modules/capitalsources` counts a source table's
# records for one scope, and for a Ten-Year category it must slug both sides.
# These two names stay bound here so every caller and guard in this file reads
# the same values; what is gone is the second copy of the rule.
#
# ⚠ The alternative — resolve the slug to the spine's canonical NAME once and
# compare names, which needs no slug SQL in the module — was MEASURED and
# rejected: of the 138 spine category names, `capitalstrategy` spells only 5
# the same way and 124 match only after case-folding, so a name comparison
# would have returned 0 on that source for 124 of 138 category pages. Slug both
# sides, with one rule (invariant 3).
_SLUG_SQL = capitalslug.SLUG_SQL
_slug = capitalslug.slug



@router.get("/get/capital/families")
async def capital_families():
    """The budget-line family vocabulary, with each family's project count.

    ⚠⚠ SERVED SO A CALLER CAN GATE A LINK ON WHETHER THE PAGE EXISTS. The budget
    lines index groups by `capitalbudget."Project Type Name"` — **41 values** —
    and the spine's families are **39**; only **25 slugs match**. The other 16
    are the same programmes under different spellings (`PARKS` vs `Parks and
    Recreation`, `FIRE` vs `Fire Department`, `HEALTH` vs `Health and Mental
    Hygiene`). Linking every group header would 404 on 39% of them, and this
    section's standing rule is that a link landing on a 404 is worse than text.

    ⚠ The slug is computed HERE with the same rule the family endpoint matches
    on, so a caller never re-derives it — the defect that made
    `/projects/categories/{slug}` unable to match its own URLs.
    """
    rows = await _select(
        "SELECT t AS family, count(*) AS n FROM ("
        "  SELECT unnest(project_types) AS t FROM capital_projects) x "
        "GROUP BY 1 ORDER BY 2 DESC")
    out = [{"family": r["family"], "slug": _slug(r["family"]), "projects": r["n"]}
           for r in rows if (r["family"] or "").strip()]
    return {"rows": out, "count": len(out),
            "slugs": sorted({r["slug"] for r in out})}


@router.get("/get/capital/projects/by-family/{fslug}")
async def capital_projects_by_family(fslug: str):
    """Every spine project funded through one BUDGET-LINE FAMILY.

    ⚠⚠ THIS IS NOT THE SAME DIMENSION AS `/projects/types/{slug}`, AND THE WHOLE
    REASON THIS ENDPOINT EXISTS IS THAT THE TWO WERE CONFLATED. Measured
    2026-09-08:

      spine `project_types`                        **39** values
      capitalstrategy "Project Type Description"  **236** values
      shared names                                   **5**, every one a
                                                     coincidence (library
                                                     systems, Courts, FDNY,
                                                     NYCHA)

    This one is the deduplicated set of budget-line families a project is funded
    through — `{L-0101, L-D002, PU-0025}` → `{New York Research Library, EDP
    Equipment and Finance Costs}` (`P`→Parks and Recreation, `HW`→Highways,
    `PW`→Public Buildings). It is project-level: **12,929 projects carry it,
    exactly the current plan**, and 0 outside it, because the families come from
    the Capital Commitment Plan's budget lines.

    ⚠ `unnest`, not `= ANY`, because the match is on the SLUG of the stored
    value and both sides are slugged the same way — the rule the category
    endpoint already uses. A raw comparison would miss every family whose name
    carries punctuation (`Water Mains, Sources and Treatment`,
    `Dept. of Information Technology & Telecomm`), which is 4 of the 39.
    """
    rows = await _select(
        "SELECT p.agency_key, p.fms_id, p.maprojid, p.description, "
        "p.agency_name, p.agency_acro, p.wegov_org_id, p.type_category, "
        "p.ten_year_category, p.borough, p.current_phase, p.in_current_plan, "
        "p.planned_total_usd, p.spent_total_usd, p.forecast_completion, "
        "p.budget_lines, p.project_types "
        "FROM capital_projects p "
        "WHERE EXISTS (SELECT 1 FROM unnest(p.project_types) t "
        "              WHERE " + _SLUG_SQL.format(col="t") + " = $1) "
        "ORDER BY p.planned_total_usd DESC NULLS LAST, p.agency_key, p.fms_id",
        (fslug.lower(),))
    out, name, lines = [], None, {}   # line code -> how many of this family's projects it funds
    for r in rows:
        d = dict(r)
        d["id"] = (d.get("agency_key") or "") + (d.get("fms_id") or "")
        for k in ("planned_total_usd", "spent_total_usd"):
            if d.get(k) is not None:
                d[k] = float(d[k])
        for t in (d.get("project_types") or []):
            if _slug(t) == fslug.lower():
                name = name or t
        for bl in (d.get("budget_lines") or []):
            lines[bl] = lines.get(bl, 0) + 1
        out.append(d)

    # ⚠⚠ THE TITLES NEED `budgetline.sql_norm` ON BOTH SIDES, and the zero is
    # the argument. `capitalbudget` spells a line `AG 0001` (space) while the
    # spine writes `AG-0001` (hyphen), so the raw join returns NOTHING — which
    # reads as "the City publishes no title for this line" rather than as our
    # punctuation. Measured on this family: raw 0 of 103, normalised 103 of 103.
    # ⚠ `budgetline` owns the rule in both languages; this must not re-type it.
    titles = {}
    if lines:
        try:
            nb = budgetline.sql_norm('"Budget Line"')
            # ⚠ ONE parameter — the whole array. Passing the codes as 103
            # separate params is what `$1::text[]` cannot take, and asyncpg says
            # so plainly: "the server expects 1 argument, 103 were passed".
            # ⚠ ORDER BY matches the DISTINCT ON expression, or the row kept per
            # code is arbitrary; a line can appear under several project types.
            trows = await _select(
                'SELECT DISTINCT ON (%s) %s AS k, "Budget Line Title" AS title '
                'FROM capitalbudget WHERE %s = ANY($1::text[]) '
                'ORDER BY %s, "Budget Line Title"' % (nb, nb, nb, nb),
                [[budgetline.norm(c) for c in lines]])
            titles = {r["k"]: r["title"] for r in trows}
        except Exception as exc:      # noqa: BLE001
            # ⚠ A missing title must not take the page down — it is a display
            # label, and this repo has already had one 500 a facet page.
            logger.warning("[capital] budget-line titles unavailable: %s", exc)

    return {
        "rows": out,
        "count": len(out),
        "family": name,
        # ⚠ The lines are the family's MEMBERS, and the count travels beside the
        # list — a family spans 1 to hundreds of budget lines and this page is
        # the only place that relationship is visible.
        # ⚠ KEPT AS A LIST OF CODES. `budget_lines` has another consumer shape in
        # this codebase and changing it here would be a silent contract change;
        # the richer rows are ADDITIVE.
        "budget_lines": sorted(lines),
        "budget_line_count": len(lines),
        # ⭐ One row per line, so the page can render a TABLE rather than 103
        # undifferentiated tags: the code, the City's own title for it, and how
        # many of THIS family's projects that line funds. `projects` is counted
        # from the rows already fetched, so it costs nothing.
        "budget_line_rows": [
            {"code": c, "title": titles.get(budgetline.norm(c)), "projects": n}
            for c, n in sorted(lines.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "note": "A budget-line family is how the Capital Commitment Plan groups "
                "budget lines. A project appears here when any line funding it "
                "belongs to this family, so a project can appear under more than "
                "one.",
    }


@router.get("/get/capital/projects/by-district/{dist_type}/{dist_id}")
async def capital_projects_by_district(dist_type: str, dist_id: str):
    """One district's capital projects, from the spine.

    ⚠⚠ THE LAST SURFACE OFF THE RETIRED SERIES. The district tab joined
    `capitalprojectsdollarscomp` to a `capitalprojects_{type}_idx` table on
    `PROJECT_ID`; the spine's own crosswalk is `capital_project_districts`,
    keyed on `(agency_key, fms_id)` — the grain an FMS id alone does not have.

    ⚠⚠ ONLY PROJECTS ATTRIBUTED TO THIS DISTRICT. A project the City has not
    placed is NOT listed here marked "no location": we do not know it is in this
    district, and printing it would assert a location NYC never published. The
    citywide and borough-wide counts a district page shows beside its own table
    come from `/get/capital/stats/{scope}/{id}`'s `not_in_this_district`, as
    counts with links — the owner decision recorded for the district surface.

    ⚠ The four types `capital_project_districts` carries: cd (15,679 rows),
    nta (6,815), cc (5,810), sd (5,530). Anything else returns an empty list
    with `available` true — "this district type is not crosswalked" is a
    different answer from a failure.
    """
    if dist_type not in ("cd", "cc", "sd", "nta"):
        return {"available": True, "rows": [], "count": 0,
                "note": "Databook does not crosswalk capital projects to "
                        "districts of type '%s'." % dist_type}
    rows = await _select(
        "SELECT p.agency_key, p.fms_id, p.maprojid, p.description, "
        "p.agency_name, p.agency_acro, p.wegov_org_id, p.type_category, "
        "p.ten_year_category, p.borough, p.current_phase, p.in_current_plan, "
        "p.planned_total_usd, p.spent_total_usd, p.forecast_completion "
        "FROM capital_projects p "
        "JOIN capital_project_districts d "
        "  ON d.agency_key = p.agency_key AND d.fms_id = p.fms_id "
        "WHERE d.dist_type = $1 AND d.dist = $2 "
        "ORDER BY p.planned_total_usd DESC NULLS LAST, p.agency_key, p.fms_id",
        (dist_type, str(dist_id)))
    out = []
    for r in rows:
        d = dict(r)
        # ⚠ THE CANONICAL, AGENCY-CONCATENATED ID — 1,160 bare FMS ids are
        # carried by more than one agency, so a link built from one can land on
        # a different agency's project.
        d["id"] = (d.get("agency_key") or "") + (d.get("fms_id") or "")
        for k in ("planned_total_usd", "spent_total_usd"):
            if d.get(k) is not None:
                d[k] = float(d[k])
        out.append(d)
    return {
        "available": True,
        "rows": out,
        "count": len(out),
        "in_current_plan": sum(1 for d in out if d.get("in_current_plan")),
        "note": "Capital projects the City attributes to this district. A "
                "project NYC publishes no location for is not listed here — "
                "see the citywide and borough counts for those.",
    }


@router.get("/get/capital/projects/by-org/{org_id}")
async def capital_projects_by_org(org_id: str):
    """One organisation's capital projects, from the spine.

    ⚠⚠ THIS REPLACES `capitalprojectsdollarscomp` ON THE ORG PROFILE'S CAPITAL
    TAB — the last surface still reading the series NYC retired 2023-10-26. The
    tab used the GENERIC `/get/orgs/section/{id}/{tbl}` endpoint, which cannot
    serve the spine: it hardcodes the quoted `"wegov-org-id"` column and the
    spine's is `wegov_org_id`.

    ⚠ MEASURED COVERAGE, because it bounds what this page can claim. The spine
    resolves **27** distinct orgs against the retired series' **25**, so the
    repoint is a net gain of two — and exactly ONE org on the old series cannot
    be served: **Metropolitan Transportation Authority** (`170020045`, 14 rows).
    The MTA is a State authority, so its absence from a CITY capital spine is
    arguably correct rather than a gap; it is stated here rather than discovered.

    ⚠ 12,456 of 17,024 projects carry an org id (73%). The 27% without are
    mostly the Dashboard and 2023 tails where no org link was ever resolved.
    This endpoint is scoped to one org, so it never asks about them — but the
    EMPTY answer is the common case here, and `available` distinguishes "this
    agency has no capital projects in the spine" from a failure (invariant 7).
    """
    rows = await _select(
        "SELECT p.agency_key, p.fms_id, p.maprojid, p.description, "
        "p.agency_name, p.agency_acro, p.wegov_org_id, p.type_category, "
        "p.ten_year_category, p.borough, p.current_phase, p.in_current_plan, "
        "p.planned_total_usd, p.spent_total_usd, p.forecast_completion "
        "FROM capital_projects p WHERE p.wegov_org_id::text = $1 "
        "ORDER BY p.planned_total_usd DESC NULLS LAST, p.agency_key, p.fms_id",
        (str(org_id),))
    out = []
    for r in rows:
        d = dict(r)
        # ⚠ THE CANONICAL ID, agency-concatenated — a bare `fms_id` is carried by
        # more than one agency on 1,160 ids, so a link built from it can land on
        # the wrong project.
        d["id"] = (d.get("agency_key") or "") + (d.get("fms_id") or "")
        for k in ("planned_total_usd", "spent_total_usd"):
            if d.get(k) is not None:
                d[k] = float(d[k])
        out.append(d)
    in_plan = sum(1 for d in out if d.get("in_current_plan"))
    return {
        "available": True,
        "rows": out,
        "count": len(out),
        "in_current_plan": in_plan,
        # ⚠ SERVED, never implied: a reader comparing this tab to the citywide
        # page needs the denominator this org is a slice of.
        "coverage": {
            "spine_total": 17024,
            "with_org_id": 12456,
            "note": "Databook links 12,456 of 17,024 tracked capital projects to "
                    "an organisation. A project with no published organisation "
                    "does not appear on any agency's tab.",
        },
        "note": "Every project the City's capital plan attributes to this "
                "organisation, from Databook's capital project spine.",
    }


@router.get("/get/capital/projects/by-category/{cslug}")
async def capital_projects_by_category(cslug: str):
    """Every spine project in one Ten-Year Strategy category.

    ⚠ THIS IS THE PROJECT LIST, NOT THE PLAN. `capitalstrategy` publishes the
    ten-year AMOUNTS for a category and has **no project key at all** — its whole
    column list is (Published Date, Project Type, Project Type Description,
    Ten-Year Plan Category, Funding Type, FY1-10 Amount, Ten-Year Total), 267
    rows for a whole city. So the two are served separately and are never added:
    the strategy says what the City plans to spend on a category over ten years,
    this says which projects are in it.

    ⚠ MEASURED COVERAGE, because it bounds what this page can claim: **8,287 of
    17,024** spine rows carry a `ten_year_category` (6,555 of 12,929 in the
    current plan). A category page therefore lists what the City has categorised,
    and the endpoint says so rather than implying the category is complete.
    """
    rows = await _select(
        "SELECT p.agency_key, p.fms_id, p.maprojid, p.description, "
        "p.agency_name, p.agency_acro, p.wegov_org_id, p.type_category, "
        "p.ten_year_category, p.borough, p.current_phase, p.in_current_plan, "
        "p.planned_total_usd, p.spent_total_usd, p.forecast_completion "
        "FROM capital_projects p WHERE " + _SLUG_SQL.format(col="p.ten_year_category") + " = $1 "
        "ORDER BY p.planned_total_usd DESC NULLS LAST, p.agency_key, p.fms_id",
        (cslug.lower(),))
    out = []
    for r in rows:
        d = dict(r)
        # ⚠ THE CANONICAL ID, agency-concatenated. A bare `fms_id` is carried by
        # more than one agency on 1,160 ids / 2,371 rows, so a link built from it
        # can land on the wrong project — the defect `/p/110WLM` shipped.
        d["id"] = (d.get("agency_key") or "") + (d.get("fms_id") or "")
        for k in ("planned_total_usd", "spent_total_usd"):
            if d.get(k) is not None:
                d[k] = float(d[k])
        out.append(d)
    total = await _select("SELECT count(*) AS n FROM capital_projects")
    categorised = await _select(
        "SELECT count(*) AS n FROM capital_projects "
        "WHERE ten_year_category IS NOT NULL AND ten_year_category <> ''")
    return {
        "rows": out,
        "count": len(out),
        "category": (out[0]["ten_year_category"] if out else None),
        "coverage": {
            "spine_total": (dict(total[0]).get("n") if total else 0),
            "categorised": (dict(categorised[0]).get("n") if categorised else 0),
            # ⚠ SERVED, not implied. A reader comparing this page to a citywide
            # figure needs to know the denominator is the categorised subset.
            "note": "NYC publishes a Ten-Year Strategy category for some of its "
                    "capital projects, not all. This page lists the projects in "
                    "this category; projects the City has not categorised appear "
                    "on no category page.",
        },
    }


@router.get("/get/capital/projects/by-budget-line/{code}")
async def capital_projects_by_budget_line(code: str):
    """Every spine project funded through one budget line.

    ⚠⚠ THIS REPLACES `capitalprojectsdollarscomp` ON THE BUDGET-LINE PAGE, and
    what it replaced was not merely an undercount — it was ONE ROW. Measured on
    `EP 0007` (2026-09-10), the rendered page read *"Showing 1 to 1 of 1 entries
    (filtered from 34 total entries)"* while the spine tiles directly above it
    said **60 projects**. Three things stacked to produce that:

      * the retired series holds **34 rows for 9 distinct projects** on this
        line, one per publication vintage (`UTIUTIL` alone appears 14 times) —
        the #262/#278 restated-row defect on a third table;
      * a publication-date control indexed on COLUMN 1 auto-selected the last
        of 15 dates, cutting those 34 rows to **1** (invariant 10);
      * so 9 of the line's 60 projects could ever be listed, and 1 was.

    One row per project, from the spine, is what this serves.

    ⚠⚠ NORMALISED ON BOTH SIDES, THROUGH `modules/budgetline` — the caller sends
    the code as its own source spells it and the spine stores a third spelling.
    `capitalbudget` publishes `EP 0007` on all 15,742 rows; the spine's
    `budget_lines` array holds `EP-0007`. A raw comparison returns 0 rows, and 0
    reads exactly like "no capital projects on this budget line", which is the
    same failure as the RICHMOND borough case. Normalising only ONE side is the
    half-fix that still returns 0.

    ⚠ `unnest`, not `&&`. `budget_lines` stores the RAW spelling, so the GIN
    index (`idx_capital_projects_budget_lines`) cannot serve a normalised match
    and this plans as a seq scan — measured 35.6ms over 17,024 rows for the
    largest line (`P-I001`, 1,135 projects), which is why no normalised column
    was added. If this ever reaches a hot path, add `budget_lines_norm text[]`
    in the builder and index THAT; do not reach for `&&` on the raw array.

    ⚠ An unknown or unfunded line returns an EMPTY list with `available` true.
    "No project in Databook's spine is funded through this line" is a real
    answer about a real budget line, and it is not a failure (invariant 7).
    """
    norm = budgetline.norm(code)
    rows = await _select(
        "SELECT p.agency_key, p.fms_id, p.maprojid, p.description, "
        "p.agency_name, p.agency_acro, p.wegov_org_id, p.type_category, "
        "p.ten_year_category, p.borough, p.current_phase, p.in_current_plan, "
        "p.planned_total_usd, p.spent_total_usd, p.forecast_completion "
        "FROM capital_projects p "
        "WHERE EXISTS (SELECT 1 FROM unnest(p.budget_lines) bl "
        "              WHERE " + budgetline.sql_norm("bl") + " = $1) "
        "ORDER BY p.planned_total_usd DESC NULLS LAST, p.agency_key, p.fms_id",
        (norm,))
    out = []
    for r in rows:
        d = dict(r)
        # ⚠ THE CANONICAL, AGENCY-CONCATENATED ID. 1,160 bare FMS ids are carried
        # by more than one agency across 2,371 rows, so a link built from
        # `fms_id` alone can land on a different agency's project — the defect
        # `/p/110WLM` shipped. It is also the key the map's features are matched
        # on, so the two cannot drift.
        d["id"] = (d.get("agency_key") or "") + (d.get("fms_id") or "")
        for k in ("planned_total_usd", "spent_total_usd"):
            if d.get(k) is not None:
                d[k] = float(d[k])
        out.append(d)
    return {
        "available": True,
        "rows": out,
        "count": len(out),
        "in_current_plan": sum(1 for d in out if d.get("in_current_plan")),
        "budget_line_norm": norm,
        "note": "Every capital project in Databook's spine funded through this "
                "budget line, one row per project. A project may be funded "
                "through several budget lines, so it can appear on more than "
                "one of these pages.",
    }


@router.get("/get/capital/projects", tags=["Capital Projects"])
async def capital_projects(page: str = "1", per_page: str = "50",
                           sort: str = "planned", direction: str = "desc",
                           agency: str = None, category: str = None,
                           phase: str = None, borough: str = None,
                           q: str = None, in_plan: bool = None,
                           has_schedule: bool = None, has_location: bool = None,
                           has_borough: bool = None, in_cc: bool = None,
                           budget_line: str = None, org: str = None,
                           ten_year_category: str = None):
    """The project list behind the index, the map's table, and the org tab.

    ⚠ THE TRUE TOTAL IS SERVED BESIDE THE PAGE. A capped list presented as the
    whole inventory is the defect this repo has shipped more than once —
    `by_vendor` showed 25 of 88 under a heading implying all of them.
    """
    page_n = _page(page)
    per = _page(per_page, default=50, minimum=1, maximum=_LIST_MAX_PER_PAGE)
    col = _SORTS.get((sort or "").lower(), _SORTS["planned"])
    desc = str(direction or "desc").lower() != "asc"

    # ⚠⚠ EVERY PARAMETER IS FORWARDED AS ITSELF. The guard on this seam reads the
    # ARGUMENT EXPRESSIONS, not the two signatures, because `has_location` was
    # once declared here and then handed on as the literal `None` — which reads
    # perfectly and makes the filter vanish.
    where, params = _list_filters(agency, category, phase, borough, in_plan,
                                  has_schedule, has_location, q,
                                  has_borough, in_cc, budget_line,
                                  org, ten_year_category)
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    total_rows = await _select(
        f"SELECT count(*) AS n FROM capital_projects p{clause}", params)
    total = (dict(total_rows[0]).get("n") if total_rows else 0) or 0

    # ⚠ The page can be past the end; that returns an empty list and is bounded,
    # which the CEILING clamp cannot be (the count is only known after this
    # query). Below 1 was the unbounded direction, and `_page` closes it.
    offset = (page_n - 1) * per
    rows = await _select(
        "SELECT agency_key, fms_id, maprojid, agency_acro, agency_name, "
        "wegov_org_id, description, type_category, borough, current_phase, "
        "forecast_completion, in_current_plan, in_dashboard, in_cpdd_2023, "
        "planned_total_usd, adopt_total_usd, commit_total_usd, spent_total_usd, "
        "EXISTS (SELECT 1 FROM capital_project_geometry gx "
        "  WHERE gx.agency_key = p.agency_key AND gx.fms_id = p.fms_id) AS has_location "
        f"FROM capital_projects p{clause} "
        f"ORDER BY {col} {'DESC' if desc else 'ASC'} NULLS LAST, agency_key, fms_id "
        f"LIMIT {per} OFFSET {offset}", params)

    return {
        "available": True,
        "total": total,
        "page": page_n,
        "per_page": per,
        "pages": (total + per - 1) // per if per else 0,
        "sort": {"by": sort if sort in _SORTS else "planned",
                 "direction": "desc" if desc else "asc",
                 "options": sorted(_SORTS)},
        "showing": len(rows),
        "rows": [dict(r) for r in rows],
        # ⚠ Stated on every page of every filter, because "50 of 17,024" and
        # "50 of 50" are the same list and a very different claim.
        "note": ("`total` counts every project matching these filters; `rows` "
                 "is one page of them."),
    }


@router.get("/get/capital/geojson", tags=["Capital Projects"])
async def capital_geojson(agency: str = None, category: str = None,
                          phase: str = None, borough: str = None,
                          q: str = None, in_plan: bool = None,
                          has_schedule: bool = None, has_location: bool = None,
                          has_borough: bool = None, in_cc: bool = None,
                          budget_line: str = None, org: str = None,
                          ten_year_category: str = None):
    """Project CENTROIDS for the city-scale map, with coverage stated.

    ⚠⚠ CENTROIDS, NOT FOOTPRINTS, AND THAT IS MEASURED. The published geometry
    is 2,776 points (169 kB of WKT) plus 1,784 polygons (**20 MB**), and the
    largest single footprint is 618 kB. Serving footprints citywide would be a
    20 MB payload; centroids are ~534 kB for all 4,560. A project's real
    outline is served one at a time by `/get/capital/project/{ident}/geometry`.

    ⚠ `coverage` is not decoration. Only 4,560 of 17,024 projects have a
    published location, so a map without that sentence reads as the whole
    capital programme when it is a quarter of it — and the missing ones are not
    randomly distributed, since several agencies publish no location at all.
    """
    # ⚠⚠ THE MAP MUST TAKE THE SAME FILTERS AS THE LIST, and that is a property
    # of the PAGE, not a tidiness preference. `/projects` builds its map from
    # the table's currently-filtered rows, so filtering the table moves the map
    # — the single best thing about that page. Server-side paging breaks that
    # unless the map can be filtered identically, so every filter the list takes
    # and that can affect WHICH projects are shown is accepted here too.
    #
    # ⚠⚠ `has_location` AND `has_borough` WERE LEFT OUT OF THIS LIST, AND THE
    # REASONING FOR THE FIRST WAS EXACTLY BACKWARDS — measured 2026-09-06, not
    # argued. The original note said accepting `has_location` "would either
    # change nothing or empty the map" because the INNER JOIN already requires
    # geometry. What it actually did was make the map IGNORE the filter: with
    # `?has_location=false` the table listed 12,464 projects that have no
    # published location while the map drew **4,560 pins**, every one of them a
    # project the table had excluded. `has_borough=false` did the same — table
    # 5,152, map 4,560. And because `matching_filters` is the legend's
    # denominator, both read "of 17,024" against a table saying 4,560.
    #
    # A filter that changes WHICH projects are in view must reach the map, or
    # the map and the table are two answers to one question — the defect this
    # whole section is being rebuilt to end.
    #
    # ⚠⚠ AND `org` / `ten_year_category` WERE MISSING FOR THE SAME REASON, WITH
    # A WORSE SYMPTOM — added 2026-09-10. Three surfaces had their project TABLE
    # migrated to the spine while their map went on reading the retired series'
    # `GEO_JSON` column off that table, so with no way to ask this endpoint for
    # one org or one Ten-Year category they each drew **0 features**: the org
    # capital tab with 2,798 rows in its table, and two category pages with 447
    # and 1,036. Container, style load and console were clean on all three.
    where, params = _list_filters(agency, category, phase, borough, in_plan,
                                  has_schedule, has_location, q, has_borough,
                                  in_cc, budget_line, org, ten_year_category)
    where.append("g.centroid_lat IS NOT NULL AND g.centroid_lng IS NOT NULL")
    clause = " WHERE " + " AND ".join(where)

    rows = await _select(
        "SELECT p.agency_key, p.fms_id, p.maprojid, p.agency_acro, "
        "p.description, p.type_category, p.current_phase, p.in_current_plan, "
        "p.planned_total_usd, g.geom_kind, g.centroid_lat, g.centroid_lng "
        "FROM capital_projects p "
        "JOIN capital_project_geometry g "
        "  ON g.agency_key = p.agency_key AND g.fms_id = p.fms_id"
        f"{clause}", params)

    # The same filters without the location requirement — the denominator the
    # legend needs. Computed, never typed.
    tw, tp = _list_filters(agency, category, phase, borough, in_plan,
                           has_schedule, has_location, q, has_borough, in_cc,
                           budget_line, org, ten_year_category)
    tclause = (" WHERE " + " AND ".join(tw)) if tw else ""
    trows = await _select(
        f"SELECT count(*) AS n FROM capital_projects p{tclause}", tp)
    matching = (dict(trows[0]).get("n") if trows else 0) or 0

    features = []
    for r in rows:
        r = dict(r)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [r["centroid_lng"], r["centroid_lat"]]},
            "properties": {
                "agency_key": r["agency_key"], "fms_id": r["fms_id"],
                "maprojid": r["maprojid"], "agency": r["agency_acro"],
                "description": r["description"], "category": r["type_category"],
                "phase": r["current_phase"], "in_current_plan": r["in_current_plan"],
                "planned_usd": (float(r["planned_total_usd"])
                                if r["planned_total_usd"] is not None else None),
                # ⚠ A centroid of a polygon is not the project's address; say so
                # per feature, since the property travels with the pin.
                "geometry_kind": r["geom_kind"],
            },
        })

    # ⚠ Formatted HERE, at the one owner of the sentence. The page prints
    # `coverage.note` verbatim — that is what stops it typing a denominator that
    # goes stale under a filter — so making it readable is this endpoint's job,
    # not the template's.
    note = (f"{len(features):,} of {matching:,} matching projects have a "
            "published location. A project without one is not absent from the "
            "capital programme — the City publishes no location for it, and "
            "several agencies publish none at all. Pins are centroids; a "
            "polygon's centroid is not its address.")

    # ⚠⚠ AN EMPTY MAP THAT IS CORRECT MUST SAY SO, or it reads as broken.
    # Measured 2026-09-05: geometry exists for 4,560 of the 12,929 projects in
    # the current plan and for **0 of the 4,095 outside it** — DCP publishes its
    # geometry against the current plan version, so a dropped project has no
    # location by construction, not by omission. `?in_plan=false` therefore
    # returns an empty FeatureCollection every time, and without this sentence
    # that is indistinguishable from a failed query.
    if matching and not features:
        note += (" No project here has a published location. Projects outside "
                 "the current Capital Commitment Plan have none at all — the "
                 "City publishes capital geometry against the current plan "
                 "version — so this is an empty map, not a failed one.")

    return {
        "type": "FeatureCollection",
        "features": features,
        "coverage": {
            "mapped": len(features),
            "matching_filters": matching,
            "unmapped": max(matching - len(features), 0),
            "note": note,
        },
    }


@router.get("/get/capital/project/{ident}/geometry", tags=["Capital Projects"])
async def capital_project_geometry(ident: str, agency: str = None):
    """One project's real footprint, fetched separately.

    ⚠ Separate because it is heavy and rarely needed: the largest polygon is
    618 kB of WKT and the average is 11.7 kB, so inlining it in the profile
    would make every project page pay for the few that are large.
    """
    rows = await _resolve_project(ident, agency)
    if len(rows) != 1:
        return {"available": True, "found": False,
                "ambiguous": len(rows) > 1, "ident": ident}
    row = rows[0]
    geo = await _select(
        "SELECT geom_kind, wkt, centroid_lat, centroid_lng "
        "FROM capital_project_geometry WHERE agency_key = $1 AND fms_id = $2",
        (row["agency_key"], row["fms_id"]))
    if not geo:
        return {"available": True, "found": True, "has_geometry": False,
                "features": [], "type": "FeatureCollection",
                "reason": "The City publishes no location for this project."}
    g = dict(geo[0])

    # ⚠⚠ SERVED AS GeoJSON, NOT RAW WKT, BECAUSE NOTHING DOWNSTREAM READS WKT.
    # Mapbox does not, and there is no PostGIS on this database to convert it
    # (`pg_extension` holds plpgsql and pg_trgm only — checked, not assumed).
    # The `wkt` key stays for any consumer that wants the source value.
    #
    # ⚠ A parse failure DEGRADES rather than 500s: the profile page can render
    # every other section, and a project whose outline we cannot read is a
    # narrower failure than a project with no page. It says WHICH it is, because
    # "we could not read this" and "the City published nothing" are different
    # facts and this repo has paid for conflating them.
    feature, box, err = None, None, None
    try:
        geom = wkt.to_geojson(g["wkt"])
        box = wkt.bbox(geom)
        feature = {"type": "Feature", "bbox": box, "geometry": geom,
                   "properties": {"agency_key": row["agency_key"],
                                  "fms_id": row["fms_id"],
                                  "maprojid": row.get("maprojid"),
                                  "description": row.get("description"),
                                  "geometry_kind": g["geom_kind"]}}
    except wkt.WktError as exc:  # pragma: no cover - 0 of 4,560 rows today
        err = str(exc)
        logger.error("[capital] unreadable geometry for %s%s: %s",
                     row["agency_key"], row["fms_id"], err)

    # ⚠ THE SENTENCE FOLLOWS THE SHAPE. One line for both said "a polygon is the
    # site, not a street address" over a POINT — describing geometry the reader
    # is not looking at. The two shapes make different claims and 2,776 of the
    # 4,560 published locations are points, so it is the majority case.
    shape_note = ("The outline the City publishes for this project. A polygon "
                  "is the site, not a street address."
                  if g["geom_kind"] == "polygon" else
                  "The point the City publishes for this project. It locates "
                  "the site, not necessarily a building entrance.")
    note = shape_note if feature else (
           "The City publishes a location for this project, but Databook could "
           "not read the published geometry. That is a fault here, not a gap in "
           "the City's data.")

    return {"available": True, "found": True, "has_geometry": True,
            "type": "FeatureCollection",
            "features": [feature] if feature else [],
            "bbox": box, "note": note, "error": err,
            "geom_kind": g["geom_kind"], "wkt": g["wkt"],
            "centroid": {"lat": g["centroid_lat"], "lng": g["centroid_lng"]}}
