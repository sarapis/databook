"""The capital profile's climate and milestone panels are index-backed.

⚠⚠ Both filter on an EXPRESSION over the id columns, so they ran as sequential
scans of 259,491 and 497,727 rows — twice each per `/p/{id}` page view — until
2026-09-24 (~150ms per query on prod; the two panels were ~80% of the endpoint).
An expression index serves a query ONLY when the expression matches, and a
mismatch fails silently: the index builds, the hook prints ✓, and every lookup
still seq-scans. So the declaration and the query text are pinned together.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))


def _read(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


def _declared(table):
    src = _read('data_scheduler.py')
    i = src.index(f'"{table}": [')
    block = src[i:src.index(']', src.index('("idx_', i) + 1) + 400]
    return block


def test_climate_index_matches_the_panels_filter():
    cap = _read('routers/capital.py')
    m = re.search(r'^_QUALIFIED = "(.*)"$', cap, re.M)
    assert m, '_QUALIFIED is gone; re-check the climate index'
    expr = m.group(1).format(col='"Project Id"')
    assert expr == "upper(replace(btrim(\"Project Id\"), ' ', ''))"
    sched = _read('data_scheduler.py')
    assert "(\"idx_climatebudgeting_project\",\n                          'upper(replace(btrim(\"Project Id\"), \\' \\', \\'\\'))')" in sched, \
        'the climate index no longer matches _QUALIFIED'
    assert "_QUALIFIED.format(col='\"Project Id\"')" in cap, 'the panel no longer filters through _QUALIFIED'


def test_milestones_index_matches_the_panels_filter():
    cap = _read('routers/capital.py')
    i = cap.index('async def _milestones(')
    # The SQL sits in single-quoted Python literals, so its quotes are escaped
    # in the source text.
    fn = cap[i:cap.index('\nasync def ', i + 10)].replace("\\'", "'")
    for expr in ("lpad(m.\"MANAGING_AGCY_CD\"::text, 3, '0')", 'upper(btrim(m."PROJECT_ID"))'):
        assert expr in fn, f'the milestones filter changed: {expr!r} is gone'
    sched = _read('data_scheduler.py')
    assert "'lpad(\"MANAGING_AGCY_CD\"::text, 3, \\'0\\'), upper(btrim(\"PROJECT_ID\"))'" in sched, \
        'the milestones index no longer matches the panel filter'
