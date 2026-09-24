"""Build `capital_project_history` — every published snapshot of a project.

⚠⚠ THIS IS WHERE THE RETIRED SERIES LIVES NOW, and the only place it may be
read. Decision (A) in docs/CAPITAL-SECTION-PLAN.md keeps the OMB Capital Project
Detail Data as **labelled history** rather than dropping it: it is the only
milestone-grain, original-budget, coded-delay record that will ever exist for
the pre-2024 book, and 2,433 of its projects appear in no current source but
still have live `/p/` pages. What it must never again be is a DEFAULT — every
row here carries `source` and `period`, so a caller cannot read a 2023 snapshot
as the present without saying so.

Four sources, 98 snapshots between them (measured 2026-09-05):

    cpdd        capitalprojectsdollarscomp        14 publications  72,437 rows
    dashboard   capprojectsbudgetsandschedule     10 periods       56,525 rows
    dash_money  capprojectsbudgetspendhistory     64 year-months   53,495 rows
    dash_sched  capprojectsschedulehistory        10 periods       22,464 rows

⚠⚠ MONEY UNITS DIFFER BY SOURCE AND ARE NORMALISED HERE, ONCE. The retired
series publishes THOUSANDS (its own description says so); the Dashboard
publishes dollars. Every column ends `_usd` and the retired figures are
multiplied on the way in, so a later reader cannot re-scale them. That is the
1000x defect this repo has already paid for.

⚠ `capprojectsbudgetspendhistory` is the ONLY source of a pre-2023 budget
baseline that is still maintained: it reaches back to year-month 200609 for some
lines, where the Dashboard's own snapshots start at 202305. It is keyed on FMS
ID with no agency, so it is joined through the spine rather than keyed directly.

Usage:
    python build_capital_history.py            # dry run
    python build_capital_history.py --apply
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

TABLE = "capital_project_history"
STAGING = f"_staging_{TABLE}"

DDL = f"""
CREATE TABLE {STAGING} (
    agency_key      text NOT NULL,
    fms_id          text NOT NULL,
    source          text NOT NULL,
    period          text NOT NULL,
    budget_usd      numeric,
    orig_budget_usd numeric,
    spend_usd       numeric,
    phase           text,
    start_date      text,
    end_date        text,
    forecast_completion text,
    variance_days   numeric,
    delay_reason    text,
    PRIMARY KEY (agency_key, fms_id, source, period)
);
"""

INDEXES = [
    ("idx_capital_history_project", "(agency_key, fms_id)"),
    ("idx_capital_history_source", "(source, period)"),
]

BUILD_SQL = f"""
INSERT INTO {STAGING} (
    agency_key, fms_id, source, period,
    budget_usd, orig_budget_usd, spend_usd,
    phase, start_date, end_date, forecast_completion,
    variance_days, delay_reason
)
-- ── the retired series: one row per (project, publication) ────────────────
-- ⚠ x1000: this source publishes THOUSANDS. Done here, once.
SELECT DISTINCT ON (lpad("MANAGING_AGCY_CD"::text,3,'0'), upper(btrim("PROJECT_ID")), "PUB_DATE")
       lpad("MANAGING_AGCY_CD"::text,3,'0'),
       upper(btrim("PROJECT_ID")),
       'cpdd',
       "PUB_DATE"::text,
       CASE WHEN btrim(coalesce("BUDG_CURR",'')) ~ '^-?[0-9.]+$'
            THEN btrim("BUDG_CURR")::numeric * 1000 END,
       ("BUDG_ORIG" * 1000)::numeric,
       NULL::numeric,
       NULL::text,
       -- ⚠ 1899/1900 is a spreadsheet-epoch SENTINEL, not a date: 703 rows in
       -- one spike. Suppressed here so there is ONE owner for the rule.
       -- ⚠ Deliberately NOT a wider cutoff — the 1930s cluster and the isolated
       -- 1980s dates may well be real and nothing evidences otherwise.
       CASE WHEN btrim(coalesce("START_CURR",'')) NOT IN ('','-')
             AND right(btrim("START_CURR"),4) >= '1901'
            THEN btrim("START_CURR") END,
       CASE WHEN btrim(coalesce("END_CURR",'')) NOT IN ('','-')
             AND right(btrim("END_CURR"),4) >= '1901'
            THEN btrim("END_CURR") END,
       NULL::text, NULL::numeric, nullif(btrim(coalesce("DELAY_DESC",'')), '')
FROM capitalprojectsdollarscomp
WHERE btrim(coalesce("PROJECT_ID",'')) <> ''

UNION ALL

-- ── Dashboard budget + schedule, one row per (project, reporting period) ──
SELECT DISTINCT ON (coalesce(m.code, btrim(b."Managing Agency")), upper(btrim(b."FMS ID")), btrim(b."Reporting Period"))
       coalesce(m.code, btrim(b."Managing Agency")),
       upper(btrim(b."FMS ID")),
       'dashboard',
       btrim(b."Reporting Period"),
       CASE WHEN btrim(coalesce(b."Total Budget",'')) ~ '^-?[0-9.]+$'
            THEN btrim(b."Total Budget")::numeric END,
       NULL::numeric,
       CASE WHEN btrim(coalesce(b."Spend to Date",'')) ~ '^-?[0-9.]+$'
            THEN btrim(b."Spend to Date")::numeric END,
       nullif(btrim(coalesce(b."Current Phase",'')), ''),
       nullif(btrim(coalesce(b."Actual Construction Start",'')), ''),
       nullif(btrim(coalesce(b."Actual Construction End",'')), ''),
       nullif(btrim(coalesce(b."Forecast Completion",'')), ''),
       NULL::numeric, NULL::text
FROM capprojectsbudgetsandschedule b
LEFT JOIN agencymap m ON m.acro = btrim(b."Managing Agency")
WHERE btrim(coalesce(b."FMS ID",'')) <> ''

UNION ALL

-- ── Dashboard budget history, the long money series ───────────────────────
-- ⚠⚠ KEYED ON ITS OWN `Managing Agency`, NOT BY JOINING THE SPINE ON THE BARE
-- ID. The first draft joined `capital_projects` on `fms_id` alone and turned
-- 53,495 source rows into 61,724 — every project id shared by two agencies
-- duplicated its whole budget history onto BOTH, attaching one agency's money
-- to the other's project. This table carries the agency itself, so there is
-- nothing to infer.
SELECT DISTINCT ON (coalesce(mh.code, btrim(h."Managing Agency")), upper(btrim(h."FMS ID")), btrim(h."Year-Month Reported"))
       coalesce(mh.code, btrim(h."Managing Agency")),
       upper(btrim(h."FMS ID")),
       'dash_money',
       btrim(h."Year-Month Reported"),
       CASE WHEN btrim(coalesce(h."Total Budget",'')) ~ '^-?[0-9.]+$'
            THEN btrim(h."Total Budget")::numeric END,
       NULL::numeric,
       CASE WHEN btrim(coalesce(h."Spend to Date",'')) ~ '^-?[0-9.]+$'
            THEN btrim(h."Spend to Date")::numeric END,
       NULL::text, NULL::text, NULL::text, NULL::text, NULL::numeric, NULL::text
FROM capprojectsbudgetspendhistory h
LEFT JOIN agencymap mh ON mh.acro = btrim(h."Managing Agency")
WHERE btrim(coalesce(h."FMS ID",'')) <> ''

UNION ALL

-- ── Dashboard schedule history: variance and the stated reason ────────────
-- ⚠ Keyed on the AGENCY PROJECT id (`PID`), which is NOT the FMS id, so it must
-- be resolved through the spine's `dash_pid`. 3,445 of 5,801 projects carry a
-- PID, so this arm is deliberately PARTIAL rather than wrong.
-- ⚠ The spine row is matched on (agency, pid), not pid alone, for the same
-- reason the money arm keys on its own agency.
-- ⚠⚠ AND THIS ARM LEGITIMATELY EMITS MORE ROWS THAN ITS SOURCE — 24,678 from
-- 22,464 — because a PID is many-to-one over FMS ids: 283 (agency, pid) pairs
-- cover several budget lines, one of them 17. DDC's pid 4752 spans five. One
-- agency project's schedule genuinely describes work carried on all of them, so
-- attaching it to each is right; what it means is that a `dash_sched` ROW COUNT
-- is not a project count. Measured, not assumed.
SELECT DISTINCT ON (p.agency_key, p.fms_id, btrim(s."Reporting Period"))
       p.agency_key,
       p.fms_id,
       'dash_sched',
       btrim(s."Reporting Period"),
       NULL::numeric, NULL::numeric, NULL::numeric,
       nullif(btrim(coalesce(s."Current Phase",'')), ''),
       NULL::text, NULL::text,
       nullif(btrim(coalesce(s."Completion Date",'')), ''),
       CASE WHEN btrim(coalesce(s."Variance (day)",'')) ~ '^-?[0-9.]+$'
            THEN btrim(s."Variance (day)")::numeric END,
       nullif(btrim(coalesce(s."Reason for Forecast Completion Change",'')), '')
FROM capprojectsschedulehistory s
LEFT JOIN agencymap ms ON ms.acro = btrim(s."Managing Agency")
JOIN capital_projects p
  ON p.dash_pid = btrim(s."PID")
 AND p.agency_key = coalesce(ms.code, btrim(s."Managing Agency"))
WHERE btrim(coalesce(s."PID",'')) <> ''
"""

AGENCYMAP = """
CREATE TEMP TABLE agencymap AS
SELECT DISTINCT btrim(magencyacro) AS acro, lpad(btrim(magency),3,'0') AS code
FROM capitalprojectslist WHERE btrim(coalesce(magencyacro,'')) <> ''
"""


async def build(conn, apply):
    live = 0
    if await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", f"public.{TABLE}"):
        live = await conn.fetchval(f"SELECT count(*) FROM {TABLE}")

    if not await conn.fetchval("SELECT to_regclass('public.capital_projects') IS NOT NULL"):
        return {"status": "fail",
                "error": "capital_projects is missing — build the spine first"}

    await conn.execute("DROP TABLE IF EXISTS agencymap")
    await conn.execute(AGENCYMAP)
    await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
    await conn.execute(DDL)
    await conn.execute(BUILD_SQL)

    total = await conn.fetchval(f"SELECT count(*) FROM {STAGING}")
    stats = await conn.fetchrow(f"""
        SELECT source, count(*) AS rows, count(DISTINCT period) AS periods,
               count(DISTINCT (agency_key, fms_id)) AS projects
        FROM {STAGING} GROUP BY source ORDER BY source LIMIT 1
    """)
    by_source = await conn.fetch(f"""
        SELECT source, count(*) AS rows, count(DISTINCT period) AS periods,
               count(DISTINCT (agency_key, fms_id)) AS projects
        FROM {STAGING} GROUP BY source ORDER BY source
    """)

    if total == 0:
        await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
        return {"status": "fail", "error": "built 0 rows"}
    if live > 0 and total < live * 0.5:
        await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
        return {"status": "fail",
                "error": f"refusing swap: {total} vs {live} live (>50% drop)"}

    if not apply:
        await conn.execute(f"DROP TABLE IF EXISTS {STAGING}")
        return {"status": "dry-run", "rows": total, "live": live,
                "by_source": [dict(r) for r in by_source]}

    async with conn.transaction():
        await conn.execute(f"DROP TABLE IF EXISTS {TABLE} CASCADE")
        await conn.execute(f"ALTER TABLE {STAGING} RENAME TO {TABLE}")
        for name, cols in INDEXES:
            await conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {TABLE}{cols}")
        await conn.execute(f"ANALYZE {TABLE}")

    return {"status": "ok", "rows": total, "live": live,
            "by_source": [dict(r) for r in by_source]}


async def rebuild_capital_history_hook(conn):
    res = await build(conn, apply=True)
    print(f"[capital history] {res['status']}: {res.get('rows', 0)} snapshots")
    if res["status"] == "fail":
        raise RuntimeError(f"capital history build failed: {res.get('error')}")
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
    print(f"rows   : {res.get('rows', 0)}  (live before: {res.get('live', 0)})")
    for r in res.get('by_source', []):
        print(f"  {r['source']:11s} {r['rows']:7d} rows  "
              f"{r['periods']:3d} periods  {r['projects']:6d} projects")
    return 0 if res["status"] in ("ok", "dry-run") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
