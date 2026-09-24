"""The term-date columns sort as DATES, not as text.

⚠⚠ `contracts.start_date` / `end_date` are MM/DD/YYYY TEXT. Ordering the raw
column orders by MONTH first, so 01/31/2031 lands before 12/01/2019. The All
technology contracts table shipped that on both its Start Date and End Date
headers (reported 2026-09-23). `contractterm.sql_date` is the one owner of the
parse; every sort map that offers a date key must route it through that.
"""
import ast
import importlib.util
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
OCE = os.path.join(ROOT, 'routers', 'oce.py')


def _contractterm():
    # By path: conftest.py replaces the `modules` package with a MagicMock.
    spec = importlib.util.spec_from_file_location(
        '_real_contractterm', os.path.join(ROOT, 'modules', 'contractterm.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sql_date_parses_only_well_formed_values():
    sql = _contractterm().sql_date('c.end_date')
    assert "TO_DATE(c.end_date, 'MM/DD/YYYY')" in sql
    # The format test must gate the parse: TO_DATE raises on malformed values.
    m = re.search(r"CASE WHEN c\.end_date ~ '([^']+)' THEN TO_DATE", sql)
    assert m, sql
    pat = re.compile(m.group(1))
    assert pat.match('01/31/2031')
    assert not pat.match('1/31/2031')
    assert not pat.match('')
    assert not pat.match('2031-01-31')


def _sort_maps():
    tree = ast.parse(open(OCE).read())
    maps = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == 'sort_map'
                and isinstance(node.value, ast.Dict)):
            maps.append(node)
    return maps


def test_every_date_sort_key_orders_by_the_parsed_date():
    maps = _sort_maps()
    checked = 0
    for node in maps:
        entries = {k.value: v for k, v in zip(node.value.keys, node.value.values)
                   if isinstance(k, ast.Constant)}
        # Only the contract-term maps: they are the ones offering `end_date`. The
        # spending explorer's map sorts `issue_date`, already a TRY_CAST.
        if 'end_date' not in entries:
            continue
        checked += 1
        for key in ('date', 'end_date'):
            if key not in entries:
                continue
            v = entries[key]
            ok = (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                  and v.func.attr == 'sql_date'
                  and isinstance(v.func.value, ast.Name)
                  and v.func.value.id == 'contractterm')
            assert ok, (f"sort_map[{key!r}] at oce.py:{node.lineno} sorts a text "
                        f"date column raw: {ast.unparse(v)}")
    assert checked >= 2, 'expected the /all and legacy contract sort maps'
