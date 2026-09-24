"""Build `capital_projects` — ONE row per FMS project id, from every source.

⚠⚠ WHY THIS TABLE EXISTS. The capital section reads
`capitalprojectsdollarscomp`, the OMB Capital Project Detail Data series NYC
RETIRED on 2023-10-26 (`is_active=false`, no socrata_id, never ingested). Its
successors have been in the database and current the whole time. The spine makes
the CURRENT plan the universe and demotes the retired series to labelled
history — decision (A) and (B) in docs/CAPITAL-SECTION-PLAN.md.

    source                          rows/ids            state
    capitalprojectslist (CPDB)      12,905 projects     current, ccpversion fisa_2026
    capprojectsbudgetsandschedule    8,171 FMS ids      current, 10 periods -> 202605
    capitalprojectsdollarscomp       8,740 projects     RETIRED, 14 pubs -> 20231026

⚠⚠ THE UNIVERSE IS A UNION, NOT THE CURRENT PLAN ALONE, and the tail is far
bigger than a latest-snapshot count suggests. Measured 2026-09-05:

    in CPDB                                        12,905
    in the Dashboard but NOT in CPDB (all periods)  1,104   (52 in period 202605 alone)
    in the 2023 series but NOT in CPDB (all pubs)   2,433   (261 in pub 20231026 alone)
    ------------------------------------------------------
    spine rows                                     15,813

Every one of those tail ids has a live `/p/{id}` page today, because the current
handler resolves against any publication of the retired series. Restricting the
spine to the current plan would 404 thousands of indexed URLs. They are carried
with `in_current_plan = false` so a count, tile or map can exclude them while the
page still resolves.

⚠⚠ THE GRAIN IS (AGENCY, PROJECT ID), NOT THE PROJECT ID ALONE — and getting
this wrong MERGES TWO DIFFERENT AGENCIES' PROJECTS. Measured 2026-09-05:
`capitalprojectslist` holds 12,929 rows, **12,929 distinct `maprojid` but only
12,905 distinct `projectid`**. 24 project ids are used by two managing agencies
at once, with different money and different work:

    HWK1669B    DDC  $148,984,071   |  DOT     $202,595
    BROADBAND   DFTA   $1,257,000   |  OTI  $56,215,000
    HWHARPERG   DCAS     $336,000   |  DDC  $48,000,000

Keying on `projectid` alone silently picks one and discards the other — $0.77B
across 48 rows — and the survivor is arbitrary. The Dashboard carries the same
split (DDC and DOT each publish an `HWK1669B`), and the retired series has 9,081
(agency, project) pairs against 8,740 bare ids. So all three sources agree the
project id is not unique on its own.

The primary key is therefore **(agency_key, fms_id)**. `agency_key` is the
three-digit managing-agency code, which every source can produce:

    CPDB          `magency`, already a code
    Dashboard     `Managing Agency` acronym -> code (1:1 in CPDB: 0 acronyms map
                  to more than one code); 24 of its 25 acronyms resolve
    2023 series   `MANAGING_AGCY_CD`, already a code

⚠ The one Dashboard acronym CPDB does not know is **EDC**, which this repo
already documents as not being a City agency and holding no capital budget line
of its own. Rows like that keep the ACRONYM as their `agency_key` rather than
being dropped — losing a real project to a missing code lookup would be the
worse failure.

⚠ JOIN KEYS GO THROUGH `modules.fmsid` — never a bare column, and never a
"strip three leading digits" rule. 814 CPDB projectids and 361 Dashboard FMS IDs
legitimately begin with digits; stripping them invents ids that do not exist.
Measured: no source joins on the concatenated `maprojid` form at all (Dashboard
0/5,608, retired series 0/5,126 match it), so nothing has to be inferred.

⚠ MONEY IS DOLLARS AT SOURCE in CPDB and the Dashboard, and THOUSANDS in the
retired series (its own description says so). Every column here is `_usd` and the
retired figures are multiplied on the way in, once, so a later reader cannot
re-scale them. This is the 1000x defect the org-tab work already paid for.

Usage:
    python build_capital_projects.py            # dry run: measure, change nothing
    python build_capital_projects.py --apply    # stage, guard, swap
"""
import argparse
import asyncio
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from modules import dbcreds, fmsid
except ImportError:  # running from inside api/
    import dbcreds
    import fmsid

try:
    from config import Config
except ImportError:
    Config = None

TABLE = "capital_projects"
STAGING = f"_staging_{TABLE}"

DDL = f"""
CREATE TABLE {STAGING} (
    -- ⚠ COMPOSITE KEY. `fms_id` alone is NOT unique — 24 ids are shared by two
    -- agencies. See the grain note in the module docstring.
    agency_key          text NOT NULL,
    fms_id              text NOT NULL,
    maprojid            text,

    -- identity / ownership
    agency_code         text,
    agency_acro         text,
    agency_name         text,
    wegov_org_id        text,
    sponsor_agency      text,
    description         text,
    type_category       text,
    ccpversion          text,

    -- CPDB money funnel, DOLLARS
    planned_total_usd       numeric,
    adopt_total_usd         numeric,
    allocate_total_usd      numeric,
    commit_total_usd        numeric,
    spent_total_usd         numeric,
    spent_checkbook_usd     numeric,

    -- CPDB plan window. ⚠ NOT a schedule: 12,408 of 12,929 maxdate values fall
    -- on 06/01, i.e. fiscal-year plan boundaries. Named `plan_*` so no caller
    -- mistakes them for start/end dates.
    plan_min_date       text,
    plan_max_date       text,

    -- Dashboard schedule (latest reporting period)
    dash_period                 text,
    dash_pid                    text,
    current_phase               text,
    phase_is_standard           boolean,
    phase_start                 text,
    forecast_phase_end          text,
    forecast_completion         text,
    actual_design_start         text,
    actual_design_end           text,
    actual_procurement_start    text,
    actual_procurement_end      text,
    actual_construction_start   text,
    actual_construction_end     text,
    dash_total_budget_usd       numeric,
    dash_spend_to_date_usd      numeric,
    borough                     text,
    community_board             text,
    ten_year_category           text,

    -- retired 2023 series, newest publication only (labelled history)
    cpdd_pub_date       integer,
    cpdd_orig_budget_usd numeric,
    cpdd_curr_budget_usd numeric,
    cpdd_scope_text     text,
    cpdd_borough        text,

    -- ⚠⚠ THE BUDGET LINE IS THE TAXONOMY THE BUDGET PAGES JOIN ON, and it is
    -- MULTI-VALUED: a project draws on 1-34 lines (mean 1.45) and 1-10 project
    -- types (mean 1.08), so a scalar column would silently keep one and drop
    -- the rest. Arrays, unnested where a page needs to group by them.
    --
    -- ⚠ Sourced from `capitalprojectscommitments`, which keys on `maprojid` and
    -- therefore covers exactly the 12,929 projects in the current plan. A
    -- project outside the plan has NO budget line here, and that is the honest
    -- answer rather than a gap: the commitment plan is what assigns them.
    budget_lines        text[],
    project_types       text[],

    -- which sources carry it
    in_current_plan     boolean NOT NULL DEFAULT false,
    in_dashboard        boolean NOT NULL DEFAULT false,
    in_cpdd_2023        boolean NOT NULL DEFAULT false,

    built_at            timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (agency_key, fms_id)
);
"""

INDEXES = [
    # ⚠ fms_id is indexed but NOT unique: /p/{id} may legitimately resolve to
    # more than one project, and the handler must show that rather than pick.
    ("idx_capital_projects_fms", "fms_id"),
    ("idx_capital_projects_org", "wegov_org_id"),
    ("idx_capital_projects_in_plan", "in_current_plan"),
    ("idx_capital_projects_phase", "current_phase"),
    ("idx_capital_projects_agency", "agency_acro"),
]

# ⚠ GIN, not btree: these are arrays and the budget pages ask "which projects
# are on this line", which is a containment test.
ARRAY_INDEXES = [
    ("idx_capital_projects_budget_lines", "budget_lines"),
    ("idx_capital_projects_project_types", "project_types"),
]

# The Dashboard's five standard phases. Everything else it emits is a
# parenthesised NON-phase status — "(Pending)", "(Cancelled)", "(Lump Sum)",
# 31 distinct values measured in period 202605 — which means "no schedule is
# required", not "this is its phase". Kept verbatim in `current_phase` and
# flagged so a phase-mix chart can separate them instead of showing
# "(Pending)" as the second-largest phase.
STANDARD_PHASES = {
    "Design", "Construction Procurement", "Construction",
    "Close-out", "Pre-Design",
}

# ⚠ SQL, not Python, because the join is over ~85k rows across three tables and
# the whole build must stay inside one statement to be atomic and fast.
# `fmsid.norm` is mirrored here as `upper(btrim(...))` and NOTHING ELSE: every
# id in these three tables is already bare (measured — 0 of them carry the
# agency-concatenated form), so normalisation here is case+whitespace only.
# A guard asserts the SQL and the Python agree on every observed shape.
BUILD_SQL = f"""
INSERT INTO {STAGING} (
    agency_key, fms_id, maprojid, agency_code, agency_acro, agency_name, wegov_org_id,
    sponsor_agency, description, type_category, ccpversion,
    planned_total_usd, adopt_total_usd, allocate_total_usd, commit_total_usd,
    spent_total_usd, spent_checkbook_usd, plan_min_date, plan_max_date,
    dash_period, dash_pid, current_phase, phase_is_standard, phase_start,
    forecast_phase_end, forecast_completion,
    actual_design_start, actual_design_end,
    actual_procurement_start, actual_procurement_end,
    actual_construction_start, actual_construction_end,
    dash_total_budget_usd, dash_spend_to_date_usd,
    borough, community_board, ten_year_category,
    cpdd_pub_date, cpdd_orig_budget_usd, cpdd_curr_budget_usd,
    cpdd_scope_text, cpdd_borough,
    in_current_plan, in_dashboard, in_cpdd_2023
)
WITH
-- ── current plan ─────────────────────────────────────────────────────────
-- ⚠ NO DISTINCT ON: `maprojid` is unique (12,929 of 12,929), so the composite
-- key needs no tie-break here. Deduping on projectid is exactly the bug.
cpdb AS (
challenge_placeholder
),
-- acronym -> agency code, so the Dashboard can be keyed the same way.
-- ⚠ 1:1 in this direction (0 acronyms map to >1 code), measured.
agencymap AS (
    SELECT DISTINCT btrim(magencyacro) AS acro, lpad(btrim(magency),3,'0') AS code
    FROM capitalprojectslist WHERE btrim(coalesce(magencyacro,'')) <> ''
),
-- ── Dashboard, NEWEST period per project ─────────────────────────────────
-- ⚠ DISTINCT ON with an explicit ORDER BY, not max(): the row must stay
-- internally consistent. Taking max(period) and max(forecast_completion)
-- separately would emit a forecast from one period beside a phase from
-- another.
dash AS (
    SELECT DISTINCT ON (coalesce(m.code, btrim(b."Managing Agency")), upper(btrim(b."FMS ID")))
           -- ⚠ fall back to the ACRONYM when no code resolves (EDC). Dropping
           -- the row would lose a real project to a lookup miss.
           coalesce(m.code, btrim(b."Managing Agency"))  AS akey,
           upper(btrim(b."FMS ID"))                     AS id,
           btrim(b."Reporting Period")                    AS period,
           nullif(btrim(coalesce(b."PID", '')), '')       AS pid,
           nullif(btrim(coalesce(b."Current Phase", '')), '')     AS phase,
           nullif(btrim(coalesce(b."Current Phase Start", '')), '')       AS phase_start,
           nullif(btrim(coalesce(b."Forecast Current Phase End", '')), '') AS phase_end,
           nullif(btrim(coalesce(b."Forecast Completion", '')), '')       AS forecast_completion,
           nullif(btrim(coalesce(b."Actual Design Start", '')), '')       AS design_start,
           nullif(btrim(coalesce(b."Actual Design End", '')), '')         AS design_end,
           nullif(btrim(coalesce(b."Actual Construction Procurement Start", '')), '') AS proc_start,
           nullif(btrim(coalesce(b."Actual Construction Procurement End", '')), '')   AS proc_end,
           nullif(btrim(coalesce(b."Actual Construction Start", '')), '') AS constr_start,
           nullif(btrim(coalesce(b."Actual Construction End", '')), '')   AS constr_end,
           CASE WHEN btrim(coalesce(b."Total Budget",'')) ~ '^-?[0-9.]+$'
                THEN btrim(b."Total Budget")::numeric END              AS total_budget,
           CASE WHEN btrim(coalesce(b."Spend to Date",'')) ~ '^-?[0-9.]+$'
                THEN btrim(b."Spend to Date")::numeric END             AS spend_to_date,
           nullif(btrim(coalesce(b."Borough", '')), '')            AS borough,
           nullif(btrim(coalesce(b."Community Board", '')), '')    AS community_board,
           nullif(btrim(coalesce(b."Ten Year Plan Category", '')), '') AS ten_year,
           nullif(btrim(coalesce(b."Sponsor Agency", '')), '')     AS sponsor
    FROM capprojectsbudgetsandschedule b
    LEFT JOIN agencymap m ON m.acro = btrim(b."Managing Agency")
    WHERE btrim(coalesce(b."FMS ID", '')) <> ''
    ORDER BY coalesce(m.code, btrim(b."Managing Agency")), upper(btrim(b."FMS ID")),
             btrim(b."Reporting Period") DESC
),
-- ── retired series, NEWEST publication per project ────────────────────────
-- ⚠ `PUB_DATE` is numeric, so DESC is chronological. Without the dedup the
-- 14 publications would count as 14 projects.
cpdd AS (
    SELECT DISTINCT ON (lpad("MANAGING_AGCY_CD"::text,3,'0'), upper(btrim("PROJECT_ID")))
           lpad("MANAGING_AGCY_CD"::text,3,'0') AS akey,
           upper(btrim("PROJECT_ID"))       AS id,
           "PUB_DATE"                       AS pub_date,
           -- ⚠ THOUSANDS -> DOLLARS, once, here. BUDG_ORIG is numeric while
           -- BUDG_CURR is text holding '' and '-', so they cannot be guarded
           -- the same way.
           ("BUDG_ORIG" * 1000)::numeric    AS orig_usd,
           CASE WHEN btrim(coalesce("BUDG_CURR", '')) ~ '^-?[0-9.]+$'
                THEN btrim("BUDG_CURR")::numeric * 1000 END AS curr_usd,
           nullif(btrim(coalesce("SCOPE_TEXT", '')), '')  AS scope_text,
           nullif(btrim(coalesce("BORO", '')), '')        AS boro
    FROM capitalprojectsdollarscomp
    WHERE btrim(coalesce("PROJECT_ID", '')) <> ''
    ORDER BY lpad("MANAGING_AGCY_CD"::text,3,'0'), upper(btrim("PROJECT_ID")), "PUB_DATE" DESC
),
ids AS (
    SELECT akey, id FROM cpdb
    UNION SELECT akey, id FROM dash
    UNION SELECT akey, id FROM cpdd
)
SELECT
    i.akey,
    i.id,
    c.maprojid,
    c.magency,
    c.magencyacro,
    c.magencyname,
    c.org_id,
    d.sponsor,
    -- first non-blank: the current plan names it, else the agency's own name
    -- for it, else the FMS name, else the retired series.
    coalesce(c.description, d.pid_desc, o.descr),
    c.typecategory,
    c.ccpversion,
    c.planned_total, c.adopt_total, c.allocate_total,
    c.commit_total, c.spent_total, c.spent_checkbook,
    c.mindate, c.maxdate,
    d.period, d.pid, d.phase,
    -- ⚠⚠ CASE-INSENSITIVE, AND THE 6 ROWS THAT PROVE IT ARE MEASURABLE. An
    -- exact `= ANY(...)` flagged `Construction Procurement` (317 rows)
    -- standard and `Construction procurement` (6 rows) NOT standard — the same
    -- phase, in the same column, published in two casings, split into "this is
    -- its phase" and "no schedule is required". Nothing published moved,
    -- because `in_construction` additionally tests `= 'Construction'` and there
    -- is no lowercase spelling of that one; it was a defect waiting for the
    -- first phase-mix chart. The list endpoint folds case on this column for
    -- exactly the same reason.
    CASE WHEN d.phase IS NULL THEN NULL
         ELSE lower(btrim(d.phase)) = ANY($1::text[]) END,
    d.phase_start, d.phase_end, d.forecast_completion,
    d.design_start, d.design_end, d.proc_start, d.proc_end,
    d.constr_start, d.constr_end,
    d.total_budget, d.spend_to_date,
    coalesce(d.borough, o.boro), d.community_board, d.ten_year,
    o.pub_date, o.orig_usd, o.curr_usd, o.scope_text, o.boro,
    (c.id IS NOT NULL), (d.id IS NOT NULL), (o.id IS NOT NULL)
FROM ids i
LEFT JOIN cpdb c ON c.akey = i.akey AND c.id = i.id
LEFT JOIN dash d ON d.akey = i.akey AND d.id = i.id
LEFT JOIN cpdd o ON o.akey = i.akey AND o.id = i.id
"""

# The CPDB projection, kept separate only so the money columns' guards are
# readable. ⚠ Every money column is regex-guarded before ::numeric — these are
# TEXT columns in the source and one non-numeric value aborts the whole query.
_CPDB_SELECT = """
    SELECT lpad(btrim(magency),3,'0')                       AS akey,
           upper(btrim(projectid))                          AS id,
           btrim(maprojid)                                  AS maprojid,
           -- ⚠ `magency` is a numeric CODE, not a name: it is a bare number on
           -- all 12,929 rows while `magencyacro` is populated on every one.
           -- Reading the plausibly-named column renders "126" as an agency.
           nullif(btrim(coalesce(magency, '')), '')         AS magency,
           nullif(btrim(coalesce(magencyacro, '')), '')     AS magencyacro,
           nullif(btrim(coalesce(magencyname, '')), '')     AS magencyname,
           {org_id_expr}                                    AS org_id,
           nullif(btrim(coalesce(description, '')), '')     AS description,
           nullif(btrim(coalesce(typecategory, '')), '')    AS typecategory,
           nullif(btrim(coalesce(ccpversion, '')), '')      AS ccpversion,
           CASE WHEN btrim(coalesce(plannedcommit_total,'')) ~ '^-?[0-9.]+$'
                THEN btrim(plannedcommit_total)::numeric END  AS planned_total,
           CASE WHEN btrim(coalesce(adopt_total,'')) ~ '^-?[0-9.]+$'
                THEN btrim(adopt_total)::numeric END          AS adopt_total,
           CASE WHEN btrim(coalesce(allocate_total,'')) ~ '^-?[0-9.]+$'
                THEN btrim(allocate_total)::numeric END       AS allocate_total,
           CASE WHEN btrim(coalesce(commit_total,'')) ~ '^-?[0-9.]+$'
                THEN btrim(commit_total)::numeric END         AS commit_total,
           CASE WHEN btrim(coalesce(spent_total,'')) ~ '^-?[0-9.]+$'
                THEN btrim(spent_total)::numeric END          AS spent_total,
           CASE WHEN btrim(coalesce(spent_total_checkbooknyc,'')) ~ '^-?[0-9.]+$'
                THEN btrim(spent_total_checkbooknyc)::numeric END AS spent_checkbook,
           nullif(btrim(coalesce(mindate, '')), '')         AS mindate,
           nullif(btrim(coalesce(maxdate, '')), '')         AS maxdate
    FROM capitalprojectslist
    WHERE btrim(coalesce(projectid, '')) <> ''
"""


def _sql(has_org_id=True):
    """The build statement, with the CPDB projection spliced in.

    Kept as one statement so the whole spine is written atomically.

    ⚠⚠ `wegov-org-id` IS AN ENRICHMENT COLUMN AND MAY BE ABSENT. The normalizer
    stamps it during ingest (dataset 241), so it is present whenever
    `capitalprojectslist` arrives by that route — which is how production loads
    it. But the scheduler's DIRECT Socrata path replaces the table from the raw
    CSV, which has no such column, and then the post-ingest hook runs against a
    table that no longer has it.

    Measured 2026-09-05: that is not hypothetical — a real ingest in this
    session produced

        [hooks] ✗ rebuild_capital_projects_hook: column "wegov-org-id" does not exist

    while history and stats rebuilt fine beside it. Hard-requiring an enrichment
    column turns a routing change into a build failure, so the column is probed
    and its absence degrades to NULL. Everything else about the spine — the
    universe, the money, the schedule — is unaffected.
    """
    org_id_expr = ('nullif(btrim(coalesce("wegov-org-id", \'\')), \'\')'
                   if has_org_id else 'NULL::text')
    sql = BUILD_SQL.replace('challenge_placeholder',
                            _CPDB_SELECT.replace('{org_id_expr}', org_id_expr))
    # `d.pid_desc` and `o.descr` are named in the SELECT for readability but the
    # CTEs above expose them under different names; alias them here rather than
    # duplicating the CTEs.
    sql = sql.replace('d.pid_desc', 'NULL').replace('o.descr', 'NULL')
    return sql


async def _attach_budget_lines(conn):
    """Budget lines and project types, from the commitment plan.

    ⚠ A separate UPDATE rather than a join in the main INSERT. The commitments
    table holds 41,277 rows for 12,929 projects, so joining it into the spine's
    SELECT would multiply the spine — the amendment defect this repo has shipped
    twice, in a new table. Aggregating first cannot.

    ⚠ Empty strings are excluded, never stored as a member: an array containing
    '' reads as "this project has a budget line" to every consumer that checks
    length. Measured, `budgetline` is populated on all 41,277 rows today, so
    this guards a future change rather than a current one.
    """
    has_commitments = await conn.fetchval(
        "SELECT to_regclass('public.capitalprojectscommitments') IS NOT NULL")
    if not has_commitments:
        # ⚠ Degrade, do not fail. A fresh environment may not have ingested the
        # commitments yet, and an absent taxonomy must not stop the spine.
        print("[capital spine] ⚠ capitalprojectscommitments absent — "
              "budget_lines and project_types left NULL.")
        return

    await conn.execute(f"""
        WITH agg AS (
            SELECT maprojid,
                   array_agg(DISTINCT btrim(budgetline)) FILTER (
                       WHERE btrim(coalesce(budgetline, '')) <> '') AS lines,
                   array_agg(DISTINCT btrim(projecttype)) FILTER (
                       WHERE btrim(coalesce(projecttype, '')) <> '') AS types
            FROM capitalprojectscommitments
            WHERE btrim(coalesce(maprojid, '')) <> ''
            GROUP BY maprojid
        )
        UPDATE {STAGING} s
           SET budget_lines = agg.lines,
               project_types = agg.types
          FROM agg
         WHERE agg.maprojid = s.maprojid
    """)
    n = await conn.fetchval(
        f"SELECT count(*) FROM {STAGING} WHERE budget_lines IS NOT NULL")
    print(f"[capital spine] budget lines attached to {n} projects")


async def build(conn, apply):
    live = 0
    exists = await conn.fetchval(
        "SELECT to_regclass($1) IS NOT NULL", f"public.{TABLE}")
    if exists:
        live = await conn.fetchval(f"SELECT count(*) FROM {TABLE}")

    has_org_id = await conn.fetchval("""
        SELECT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name = 'capitalprojectslist'
                         AND column_name = 'wegov-org-id')
    """)
    if not has_org_id:
        print("[capital spine] ⚠ capitalprojectslist has no `wegov-org-id` — "
              "it was loaded without normalizer enrichment. Building without "
              "org links rather than failing.")

    await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
    await conn.execute(DDL)
    # ⚠ Lowercased HERE so the Python set stays the readable spelling while the
    # comparison is folded on both sides — normalising only one side is the
    # borough defect, and it would silently flag every phase non-standard.
    await conn.execute(_sql(has_org_id),
                       sorted(p.lower() for p in STANDARD_PHASES))
    await _attach_budget_lines(conn)

    total = await conn.fetchval(f"SELECT count(*) FROM {STAGING}")

    stats = await conn.fetchrow(f"""
        SELECT count(*) FILTER (WHERE in_current_plan)  AS in_plan,
               count(DISTINCT fms_id)                   AS distinct_fms_ids,
               count(*) FILTER (WHERE in_dashboard)     AS in_dash,
               count(*) FILTER (WHERE in_cpdd_2023)     AS in_cpdd,
               count(*) FILTER (WHERE NOT in_current_plan) AS tail,
               count(*) FILTER (WHERE in_current_plan AND in_dashboard) AS plan_and_dash,
               sum(planned_total_usd) AS planned_usd,
               sum(spent_checkbook_usd) AS checkbook_usd
        FROM {STAGING}
    """)

    if total == 0:
        await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
        return {"status": "fail", "error": "built 0 rows", "stats": dict(stats)}

    # Same data-safety guard as every other loader here: a source that suddenly
    # halves is far more likely to be a broken upstream than real news.
    if live > 0 and total < live * 0.5:
        await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
        return {"status": "fail", "stats": dict(stats),
                "error": f"refusing swap: {total} rows vs {live} live (>50% drop)"}

    if not apply:
        await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
        return {"status": "dry-run", "rows": total, "live": live,
                "stats": dict(stats)}

    async with conn.transaction():
        await conn.execute(f"DROP TABLE IF EXISTS {TABLE} CASCADE")
        await conn.execute(f"ALTER TABLE {STAGING} RENAME TO {TABLE}")
        for name, col in INDEXES:
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS {name} ON {TABLE}({col})")
        for name, col in ARRAY_INDEXES:
            await conn.execute(
                f"CREATE INDEX IF NOT EXISTS {name} ON {TABLE} USING gin({col})")
        await conn.execute(f"ANALYZE {TABLE}")

    return {"status": "ok", "rows": total, "live": live, "stats": dict(stats)}


async def rebuild_capital_projects_hook(conn):
    """Post-ingest hook: rebuild the spine whenever a source table lands."""
    res = await build(conn, apply=True)
    print(f"[capital spine] {res['status']}: {res.get('rows', 0)} projects "
          f"({res.get('stats', {}).get('in_plan', 0)} in the current plan)")
    if res["status"] == "fail":
        raise RuntimeError(f"capital spine build failed: {res.get('error')}")
    return res


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="stage, guard and swap (default is a dry run)")
    args = ap.parse_args()

    cfg = getattr(Config, "db", {}) if Config else {}
    conn = await asyncpg.connect(**dbcreds.settings(cfg))
    try:
        res = await build(conn, apply=args.apply)
    finally:
        await conn.close()

    s = res.get("stats", {})
    print(f"status            : {res['status']}")
    if res.get("error"):
        print(f"error             : {res['error']}")
    print(f"spine rows        : {res.get('rows', 0)}   (live before: {res.get('live', 0)})")
    print(f"  in current plan : {s.get('in_plan')}")
    print(f"  in dashboard    : {s.get('in_dash')}")
    print(f"  in 2023 series  : {s.get('in_cpdd')}")
    print(f"  tail (not in plan): {s.get('tail')}")
    print(f"  plan AND dashboard: {s.get('plan_and_dash')}")
    print(f"  distinct bare ids : {s.get('distinct_fms_ids')}  "
          f"(fewer than rows = ids shared by 2 agencies)")
    print(f"planned (CPDB)    : ${float(s.get('planned_usd') or 0)/1e9:,.1f}B")
    print(f"checkbook spend   : ${float(s.get('checkbook_usd') or 0)/1e9:,.1f}B")
    return 0 if res["status"] in ("ok", "dry-run") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
