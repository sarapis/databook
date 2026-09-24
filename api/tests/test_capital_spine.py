"""Guards on the grain of `capital_projects`.

⚠⚠ THE DEFECT THESE EXIST TO PREVENT. The obvious key for a capital project is
its project id, and it is WRONG. Measured 2026-09-05 on the live plan:
`capitalprojectslist` has 12,929 rows, **12,929 distinct `maprojid` but only
12,905 distinct `projectid`** — 24 ids are used by two managing agencies at once,
for different work with different money:

    HWK1669B    DDC  $148,984,071   |  DOT     $202,595
    BROADBAND   DFTA   $1,257,000   |  OTI  $56,215,000
    HWHARPERG   DCAS     $336,000   |  DDC  $48,000,000

A spine keyed on `projectid` silently keeps one and discards the other. It is not
merely lossy — the survivor is arbitrary, so DOT's $202,595 project can hide
DDC's $149.0M one under the same URL.

⚠ THE RECONCILIATION IS WHAT PROVED IT, and a count alone would not have.
Keyed on projectid the build produced 12,905 in-plan rows and **$201.2B** planned;
keyed on (agency, id) it produces 12,929 and **$201.6B**, which matches the
source total exactly. The count looked plausible either way; only the money
showed the loss. This is the same lesson as the by-year chart's $2.5M.

These are SHAPE guards on the SQL the builder emits, not behavioural tests —
CI's database is empty, so a behavioural test here would pass vacuously.
"""
import importlib.util
import os
import re

API = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))


def _load_builder():
    """Load the builder by path, without importing the `modules` package.

    ⚠ `conftest.py` replaces `modules` with a MagicMock, and the builder imports
    `dbcreds`/`fmsid` from it. Loading by path with a stubbed import keeps the
    real SQL while avoiding the mock satisfying assertions for us.
    """
    spec = importlib.util.spec_from_file_location(
        'build_capital_projects', os.path.join(API, 'build_capital_projects.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


builder = _load_builder()


def test_the_primary_key_is_agency_plus_project_id():
    """The 24-collision defect. A single-column PK on fms_id reintroduces it."""
    ddl = builder.DDL
    assert re.search(r'PRIMARY\s+KEY\s*\(\s*agency_key\s*,\s*fms_id\s*\)', ddl), (
        'capital_projects must be keyed on (agency_key, fms_id). 24 project ids '
        'are shared by two managing agencies; a single-column key discards one '
        'of each pair, arbitrarily.')
    assert not re.search(r'fms_id\s+text\s+PRIMARY\s+KEY', ddl), (
        'fms_id must NOT be a primary key on its own')


def test_fms_id_is_indexed_but_not_unique():
    """/p/{id} may legitimately resolve to more than one project."""
    names = [n for n, _ in builder.INDEXES]
    cols = [c for _, c in builder.INDEXES]
    assert 'fms_id' in cols, 'fms_id must be indexed for URL lookups'
    for name, col in builder.INDEXES:
        assert 'unique' not in name.lower(), (
            f'{name} must not be unique — {col} is shared across agencies')


def test_no_cte_dedupes_on_the_project_id_alone():
    """Each source CTE must carry the agency into its DISTINCT ON.

    ⚠ Reads the SQL the builder actually EMITS, so splicing cannot hide a
    single-column dedup.
    """
    sql = builder._sql()
    distincts = re.findall(r'DISTINCT ON \(([^)]*)\)', sql)
    assert distincts, 'expected DISTINCT ON clauses in the build SQL'
    for d in distincts:
        assert ('akey' in d) or ('Managing Agency' in d) or ('MANAGING_AGCY_CD' in d), (
            'this DISTINCT ON dedupes without the agency, which merges two '
            f'agencies\' projects: DISTINCT ON ({d.strip()})')


def test_every_source_contributes_its_agency_to_the_union():
    """The id universe is (agency, id) pairs, never bare ids."""
    sql = builder._sql()
    m = re.search(r'ids AS \((.*?)\n\)', sql, re.S)
    assert m, 'the `ids` CTE is missing'
    body = m.group(1)
    selects = re.findall(r'SELECT\s+([^\n]+?)\s+FROM', body)
    assert len(selects) >= 3, f'expected 3 source arms in the union, got {selects}'
    for sel in selects:
        assert 'akey' in sel, (
            f'every arm of the id union must carry the agency key; got "{sel}"')


def test_retired_money_is_converted_to_dollars_exactly_once():
    """⚠ The 2023 series publishes THOUSANDS; CPDB and the Dashboard publish
    dollars. The conversion belongs in the builder, once, and the column names
    end in `_usd` so a later reader cannot re-scale them."""
    sql = builder._sql()
    m = re.search(r'cpdd AS \((.*?)\n\),', sql, re.S)
    assert m, 'the `cpdd` CTE is missing'
    body = m.group(1)
    assert body.count('* 1000') == 2, (
        'both retired money columns (BUDG_ORIG, BUDG_CURR) must be scaled to '
        f'dollars exactly once each; found {body.count("* 1000")} scalings')
    # And no other CTE may scale — CPDB/Dashboard are already dollars.
    for name in ('cpdb AS (', 'dash AS ('):
        i = sql.find(name)
        j = sql.find('\n),', i)
        assert '* 1000' not in sql[i:j], (
            f'{name.strip(" AS (")} publishes DOLLARS; scaling it by 1000 is the '
            '1000x defect this repo has already paid for')


def test_money_columns_are_regex_guarded_before_cast():
    """These are TEXT columns at source; one non-numeric value aborts the query."""
    sql = builder._sql()
    casts = re.findall(r'btrim\((?:coalesce\()?([A-Za-z_"][^,)]*)[^)]*\)?\)::numeric', sql)
    assert casts, 'expected numeric casts in the build SQL'
    guarded = sql.count("~ '^-?[0-9.]+$'")
    assert guarded >= 8, (
        f'expected every text money column to be regex-guarded before ::numeric; '
        f'found {guarded} guards')


def test_the_builder_refuses_an_empty_or_halved_build():
    """The data-safety guard every loader here carries."""
    src = open(os.path.join(API, 'build_capital_projects.py'), encoding='utf-8').read()
    assert 'built 0 rows' in src, 'the builder must refuse a 0-row build'
    assert 'live * 0.5' in src, 'the builder must refuse a >50% row drop'


# ── history, stats and the hook chain ────────────────────────────────────────

SCHEDULER = os.path.join(API, 'data_scheduler.py')


def _scheduler_src():
    with open(SCHEDULER, encoding='utf-8') as fh:
        return fh.read()


def _hooks_for(table):
    src = _scheduler_src()
    m = re.search(r'POST_INGEST_HOOKS = \{(.*?)\n\}', src, re.S)
    assert m, 'POST_INGEST_HOOKS not found'
    e = re.search(r'"' + re.escape(table) + r'":\s*\[(.*?)\]', m.group(1), re.S)
    return [h.strip() for h in e.group(1).split(',') if h.strip()] if e else []


def test_the_spine_rebuilds_on_every_source_that_feeds_it():
    """A source landing without a rebuild leaves the spine describing a plan
    that no longer exists — the exact staleness this section is being rebuilt
    to remove."""
    for table in ('capitalprojectslist', 'capitalprojectscommitments',
                  'capprojectsbudgetsandschedule'):
        assert 'rebuild_capital_projects_hook' in _hooks_for(table), (
            f'{table} feeds the spine and must rebuild it')


def test_stats_runs_after_the_spine_and_after_history():
    """⚠⚠ ORDER IS LOAD-BEARING and there is no dependency graph to enforce it.

    History and stats both read `capital_projects`, and stats additionally reads
    `capital_project_history`. `run_post_ingest_hooks` runs a table's hooks in
    LIST ORDER, which is the only thing making this correct.
    """
    for table in ('capitalprojectslist', 'capprojectsbudgetsandschedule'):
        hooks = _hooks_for(table)
        assert 'rebuild_capital_stats_hook' in hooks, f'{table} must refresh stats'
        i_stats = hooks.index('rebuild_capital_stats_hook')
        for earlier in ('rebuild_capital_projects_hook', 'rebuild_capital_history_hook'):
            if earlier in hooks:
                assert hooks.index(earlier) < i_stats, (
                    f'{earlier} must run before stats on {table}; stats reads what it writes')


def test_the_history_sources_refresh_history():
    for table in ('capprojectsbudgetspendhistory', 'capprojectsschedulehistory'):
        assert 'rebuild_capital_history_hook' in _hooks_for(table), (
            f'{table} is a history source and must refresh it')


def test_the_spine_degrades_when_the_enrichment_column_is_absent():
    """⚠⚠ `wegov-org-id` is stamped by the NORMALIZER, not published by NYC.

    Production loads `capitalprojectslist` through the normalizer so the column
    is there — but the scheduler's DIRECT Socrata path replaces the table from
    the raw CSV, which has no such column, and the hook then runs against it.
    Measured 2026-09-05: a real ingest produced
    `[hooks] ✗ rebuild_capital_projects_hook: column "wegov-org-id" does not
    exist`. Hard-requiring an enrichment column turns a routing change into a
    build failure.
    """
    src = open(os.path.join(API, 'build_capital_projects.py'), encoding='utf-8').read()
    assert 'information_schema.columns' in src and 'wegov-org-id' in src, (
        'the builder must PROBE for the enrichment column rather than assuming it')
    assert 'NULL::text' in src, (
        'a missing enrichment column must degrade to NULL, not raise')
