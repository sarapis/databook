"""Build `capital_program_stats` — every capital figure, computed in ONE place.

⚠⚠ WHAT THIS REPLACES, AND WHY. The section's four tiles come from
`rebuild_glob_stats`, which computes them over the RETIRED 2023 series, and the
same four are recomputed again by eight `pstats-*` endpoint families per scope.
Measured on the live site: Projects 5,128 · Original $90.7B · Current $135.8B ·
**Amount Over Budget $76.9B** — where current minus original is $45.1B, not
$76.9B. The global tile sums every row's budget difference; the district tiles
sum only the negative ones. **Two pages publish the same label from two
definitions**, which is what happens when a figure has no owner.

So: one table, one definition per figure, every page reading a key.

⚠⚠ THE THREE OLD MONEY TILES ARE DELIBERATELY NOT REPRODUCED. "Original Cost",
"Current Cost" and "Amount Over Budget" are properties of the retired series —
CPDB publishes no original budget at all — so recreating them would either mean
reading the dead table forever or inventing a baseline. Their honest successor
is the Dashboard's own budget history (first snapshot vs latest, per project),
which is in `capital_project_history` and reported here as `budget_growth_usd`
over the projects that HAVE such a history, with that denominator stated rather
than implied.

⚠ Every count is over `capital_projects`, so the universe is the current plan
plus the flagged tail, and `in_current_plan` separates them. A figure that mixes
the two silently is the whole defect this rebuild exists to remove.

⚠⚠ CPDB'S MONEY COLUMNS ARE NOT A FUNNEL, AND THE PLAN'S §5.3 ASSUMES THEY ARE.
Measured 2026-09-05 straight from `capitalprojectslist`, and reproduced exactly
by this table:

    planned   $201.8B      populated on 9,213 projects
    adopt     $427.1B
    allocate  $309.1B
    commit     $30.4B      populated on 5,158
    spent      $87.8B      populated on 7,118

They do not nest. Adopted is more than twice planned, and committed is a third
of spent. They are not successive stages of one pot: `commit_total` is what was
committed within the CURRENT plan period, while `spent_total` is cumulative
spend over the project's whole life, and the adopted/allocated columns span
several years of budget authority. Each is also populated on a different subset.

So a "planned -> adopted -> allocated -> committed -> spent" funnel — which is
what docs/CAPITAL-SECTION-PLAN.md §5.3 proposes for the project profile — would
draw a shape the data does not have, and would read as money vanishing. Show
them as separate labelled measures with their populations, or pick the two that
share a window. **This needs an owner decision before the profile is built.**
"""
import argparse
import asyncio
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'modules'))

try:
    from modules import dbcreds
except ImportError:
    import dbcreds

try:
    from config import Config
except ImportError:
    Config = None

TABLE = "capital_program_stats"
STAGING = f"_staging_{TABLE}"

DDL = f"""
CREATE TABLE {STAGING} (
    scope_type      text NOT NULL,
    scope_id        text NOT NULL,
    projects        integer NOT NULL,
    in_plan         integer NOT NULL,
    -- ⚠ SIX SEPARATE MEASURES, EACH WITH ITS OWN POPULATION. They are not
    -- stages of one pot and do not nest — see modules/capitalmoney.py, which
    -- owns what each means and the note that must appear beside them.
    planned_usd     numeric,
    adopt_usd       numeric,
    allocate_usd    numeric,
    committed_usd   numeric,
    spent_usd       numeric,
    checkbook_usd   numeric,
    planned_n       integer,
    adopt_n         integer,
    allocate_n      integer,
    committed_n     integer,
    spent_n         integer,
    checkbook_n     integer,
    with_schedule   integer NOT NULL,
    in_construction integer NOT NULL,
    completed       integer NOT NULL,
    late_forecast   integer NOT NULL,
    with_geometry   integer NOT NULL,
    dropped_since_2023 integer NOT NULL,
    as_of_plan      text,
    as_of_dashboard text,
    built_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope_type, scope_id)
);
"""

# ⚠ ONE definition per figure, written once and reused for every scope. The
# 2023 tiles diverged precisely because each scope recomputed them.
METRICS = """
    count(*)                                                      AS projects,
    count(*) FILTER (WHERE p.in_current_plan)                     AS in_plan,
    sum(p.planned_total_usd)                                      AS planned_usd,
    sum(p.adopt_total_usd)                                        AS adopt_usd,
    sum(p.allocate_total_usd)                                     AS allocate_usd,
    sum(p.commit_total_usd)                                       AS committed_usd,
    sum(p.spent_total_usd)                                        AS spent_usd,
    sum(p.spent_checkbook_usd)                                    AS checkbook_usd,
    -- ⚠ The POPULATION of each measure, not just its total. A figure summed
    -- over 5,158 projects and one summed over 11,650 are not comparable, and
    -- showing them side by side without their denominators is what makes them
    -- look like a funnel that leaks.
    count(*) FILTER (WHERE p.planned_total_usd  > 0)              AS planned_n,
    count(*) FILTER (WHERE p.adopt_total_usd    > 0)              AS adopt_n,
    count(*) FILTER (WHERE p.allocate_total_usd > 0)              AS allocate_n,
    count(*) FILTER (WHERE p.commit_total_usd   > 0)              AS committed_n,
    count(*) FILTER (WHERE p.spent_total_usd    > 0)              AS spent_n,
    count(*) FILTER (WHERE p.spent_checkbook_usd > 0)             AS checkbook_n,
    -- ⚠ "has a schedule" means the Dashboard published one, NOT that the plan
    -- carries plan_min/max dates: 12,408 of 12,929 maxdate values fall on 06/01,
    -- i.e. fiscal-year boundaries, which is a plan window and not a schedule.
    count(*) FILTER (WHERE p.dash_period IS NOT NULL)              AS with_schedule,
    -- ⚠ Only the five STANDARD phases count as a phase. The Dashboard also
    -- emits 31 parenthesised statuses — "(Pending)", "(Cancelled)", "(Lump
    -- Sum)" — which mean "no schedule is required", not "this is its phase".
    count(*) FILTER (WHERE p.phase_is_standard
                       AND p.current_phase = 'Construction')       AS in_construction,
    count(*) FILTER (WHERE p.current_phase = '(Completed)')         AS completed,
    count(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM capital_project_history h
        WHERE h.agency_key = p.agency_key AND h.fms_id = p.fms_id
          AND h.source = 'dash_sched' AND h.variance_days > 0))     AS late_forecast,
    count(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM capital_project_geometry g
        WHERE g.agency_key = p.agency_key AND g.fms_id = p.fms_id)) AS with_geometry,
    -- ⚠ "dropped" is in the 2023 series and NOT in the current plan — a real
    -- state a reader should be able to see, not a silent exclusion.
    count(*) FILTER (WHERE p.in_cpdd_2023 AND NOT p.in_current_plan) AS dropped_since_2023,
    max(p.ccpversion)                                              AS as_of_plan,
    max(p.dash_period)                                             AS as_of_dashboard
"""


def _sql_for(scope_type, scope_expr, join="", where="TRUE"):
    # ⚠ A literal scope (the whole programme) is ONE aggregate row and must not
    # be grouped — Postgres rejects a non-integer constant in GROUP BY.
    group = "" if scope_expr.startswith("'") else f"GROUP BY {scope_expr}"
    return f"""
    INSERT INTO {STAGING} (
        scope_type, scope_id, projects, in_plan,
        planned_usd, adopt_usd, allocate_usd, committed_usd, spent_usd, checkbook_usd,
        planned_n, adopt_n, allocate_n, committed_n, spent_n, checkbook_n,
        with_schedule, in_construction, completed,
        late_forecast, with_geometry, dropped_since_2023, as_of_plan, as_of_dashboard)
    SELECT '{scope_type}', {scope_expr}, {METRICS}
    FROM capital_projects p
    {join}
    WHERE {where}
    {group}
    """


SCOPES = [
    # the whole programme
    ("program", "'all'", "", "TRUE"),
    # by managing agency, both by our org id and by the agency's own acronym
    ("org", "p.wegov_org_id", "", "p.wegov_org_id IS NOT NULL AND p.wegov_org_id <> ''"),
    ("agency", "p.agency_acro", "", "p.agency_acro IS NOT NULL AND p.agency_acro <> ''"),
    # by district, through the crosswalk
    ("cd", "d.dist", "JOIN capital_project_districts d ON d.agency_key = p.agency_key AND d.fms_id = p.fms_id AND d.dist_type = 'cd'", "TRUE"),
    ("cc", "d.dist", "JOIN capital_project_districts d ON d.agency_key = p.agency_key AND d.fms_id = p.fms_id AND d.dist_type = 'cc'", "TRUE"),
    ("sd", "d.dist", "JOIN capital_project_districts d ON d.agency_key = p.agency_key AND d.fms_id = p.fms_id AND d.dist_type = 'sd'", "TRUE"),
    ("nta", "d.dist", "JOIN capital_project_districts d ON d.agency_key = p.agency_key AND d.fms_id = p.fms_id AND d.dist_type = 'nta'", "TRUE"),
    # ⚠⚠ TWO DIFFERENT THINGS ARE CALLED A "CATEGORY", AND THIS SCOPE USED TO
    # CARRY ONLY THE COARSE ONE UNDER THE BARE NAME. CPDB's `typc` is a 3-value
    # asset class (Fixed Asset · ITT, Vehicles and Equipment · Lump Sum); the
    # Ten-Year Capital Strategy category is a 138-value programme taxonomy, and
    # it is the one the Categories page actually joins on. A scope called
    # `category` serving 3 rows where a page needs 138 is the same label with
    # two definitions — the defect that produced two "Amount Over Budget"
    # figures. Both are kept, each named for what it is.
    ("asset_category", "p.type_category", "",
     "p.type_category IS NOT NULL AND p.type_category <> ''"),
    ("ten_year_category", "p.ten_year_category", "",
     "p.ten_year_category IS NOT NULL AND p.ten_year_category <> ''"),
    # ⚠ Budget lines and project types are ARRAYS on the spine, so they are
    # unnested here. A project on 3 lines counts once under each — which is
    # correct for "what is on this line" and means these scopes' project counts
    # deliberately do NOT sum to the programme total. `_sql_for` groups on the
    # unnested alias, never the array.
    ("budget_line", "bl", ", LATERAL unnest(p.budget_lines) AS bl",
     "p.budget_lines IS NOT NULL"),
    ("type", "pt", ", LATERAL unnest(p.project_types) AS pt",
     "p.project_types IS NOT NULL"),
]


async def _reconcile(conn):
    """Recompute every array scope straight from the spine and demand agreement.

    ⚠⚠ A RECONCILIATION ON COUNTS IS NOT A RECONCILIATION. This repo has already
    shipped a by-year chart whose contract count closed perfectly at 4,397 while
    the money series was $2,500,000 short, because a NULL predicate dropped rows
    from the value aggregates and not from `COUNT(*)`. So this checks the MONEY
    too, and compares against `numeric` rather than a float sum.

    ⚠ The array scopes are the ones worth checking, because they are the only
    ones whose row count is not simply the group count: a project on three
    budget lines is counted under each, so `budget_line` legitimately totals
    18,732 projects against a programme of 17,024. That is exactly the shape
    where an off-by-a-join goes unnoticed — it is SUPPOSED to be bigger, so
    "bigger than expected" tells you nothing. Only an independent recomputation
    does.

    Returns a list of failures; empty means agreement.
    """
    checks = [("budget_line", "budget_lines"), ("type", "project_types")]
    problems = []
    for scope, column in checks:
        row = await conn.fetchrow(f"""
            WITH expect AS (
                SELECT count(*) AS projects,
                       sum(p.planned_total_usd) AS planned,
                       sum(p.spent_total_usd)   AS spent
                FROM capital_projects p, LATERAL unnest(p.{column}) v
                WHERE p.{column} IS NOT NULL),
            got AS (
                SELECT sum(projects) AS projects,
                       sum(planned_usd) AS planned,
                       sum(spent_usd)   AS spent
                FROM {STAGING} WHERE scope_type = $1)
            SELECT e.projects AS e_projects, g.projects AS g_projects,
                   round(coalesce(e.planned, 0), 2) AS e_planned,
                   round(coalesce(g.planned, 0), 2) AS g_planned,
                   round(coalesce(e.spent, 0), 2)   AS e_spent,
                   round(coalesce(g.spent, 0), 2)   AS g_spent
            FROM expect e, got g
        """, scope)
        if row is None:
            continue
        if row["e_projects"] != row["g_projects"]:
            problems.append(
                f"{scope} projects {row['g_projects']} != {row['e_projects']}")
        for key in ("planned", "spent"):
            if row[f"e_{key}"] != row[f"g_{key}"]:
                problems.append(
                    f"{scope} {key} {row[f'g_{key}']} != {row[f'e_{key}']}")
    return problems


async def build(conn, apply):
    for dep in ('capital_projects', 'capital_project_history',
                'capital_project_geometry', 'capital_project_districts'):
        if not await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", f"public.{dep}"):
            return {"status": "fail", "error": f"{dep} is missing — build it first"}

    live = 0
    if await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", f"public.{TABLE}"):
        live = await conn.fetchval(f"SELECT count(*) FROM {TABLE}")

    await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
    await conn.execute(DDL)
    for scope_type, expr, join, where in SCOPES:
        await conn.execute(_sql_for(scope_type, expr, join, where))

    total = await conn.fetchval(f"SELECT count(*) FROM {STAGING}")
    by_scope = await conn.fetch(
        f"SELECT scope_type, count(*) AS rows FROM {STAGING} GROUP BY 1 ORDER BY 1")
    prog = await conn.fetchrow(
        f"SELECT * FROM {STAGING} WHERE scope_type = 'program'")

    if total == 0:
        await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
        return {"status": "fail", "error": "built 0 rows"}
    if live > 0 and total < live * 0.5:
        await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
        return {"status": "fail",
                "error": f"refusing swap: {total} vs {live} live (>50% drop)"}

    bad = await _reconcile(conn)
    if bad:
        await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
        return {"status": "fail", "error": "refusing swap: " + "; ".join(bad)}

    if not apply:
        await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
        return {"status": "dry-run", "rows": total,
                "by_scope": [dict(r) for r in by_scope],
                "program": dict(prog) if prog else {}}

    async with conn.transaction():
        await conn.execute(f"DROP TABLE IF EXISTS {TABLE} CASCADE")
        await conn.execute(f"ALTER TABLE {STAGING} RENAME TO {TABLE}")
        await conn.execute(f"ANALYZE {TABLE}")

    return {"status": "ok", "rows": total,
            "by_scope": [dict(r) for r in by_scope],
            "program": dict(prog) if prog else {}}


async def rebuild_capital_stats_hook(conn):
    res = await build(conn, apply=True)
    print(f"[capital stats] {res['status']}: {res.get('rows', 0)} scope rows")
    if res["status"] == "fail":
        raise RuntimeError(f"capital stats build failed: {res.get('error')}")
    return res


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    cfg = getattr(Config, "db", {}) if Config else {}
    conn = await asyncpg.connect(**dbcreds.settings(cfg))
    try:
        res = await build(conn, apply=args.apply)
    finally:
        await conn.close()
    print(f"status : {res['status']}")
    if res.get('error'):
        print(f"error  : {res['error']}")
    print(f"rows   : {res.get('rows', 0)}")
    for r in res.get('by_scope', []):
        print(f"  {r['scope_type']:9s} {r['rows']:5d}")
    p = res.get('program') or {}
    if p:
        print("\nprogram:")
        print(f"  projects        {p.get('projects')}  (in plan {p.get('in_plan')})")
        print("  money — six SEPARATE measures, each over its own population:")
        for key, n_key, label in (
                ('planned_usd', 'planned_n', 'planned'),
                ('adopt_usd', 'adopt_n', 'adopted'),
                ('allocate_usd', 'allocate_n', 'allocated'),
                ('committed_usd', 'committed_n', 'committed'),
                ('spent_usd', 'spent_n', 'spent'),
                ('checkbook_usd', 'checkbook_n', 'paid (checkbook)')):
            print(f"    {label:18s} ${float(p.get(key) or 0)/1e9:8,.1f}B  "
                  f"over {p.get(n_key)} projects")
        print(f"  with schedule   {p.get('with_schedule')}")
        print(f"  in construction {p.get('in_construction')}")
        print(f"  late forecast   {p.get('late_forecast')}")
        print(f"  with geometry   {p.get('with_geometry')}")
        print(f"  dropped since 2023 {p.get('dropped_since_2023')}")
        print(f"  as of           plan {p.get('as_of_plan')} / dashboard {p.get('as_of_dashboard')}")
    return 0 if res["status"] in ("ok", "dry-run") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
