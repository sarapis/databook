"""Guards on the budget-line / type / category taxonomy the budget pages join on.

⚠⚠ THIS CLOSES A GAP IN PHASE 1 THAT PHASE 4 DEPENDS ON. `docs/CAPITAL-SECTION-PLAN.md`
§5.6 says each budget-line page links to the spine's projects through
`capital_projects.budget_lines` and that the pages' tile grids are fed from
`capital_program_stats (budget_line|category|type)`. None of those existed: the
spine had no budget-line column at all, and the stats table's only category
scope carried CPDB's coarse 3-value asset class.

⚠⚠ AND TWO DIFFERENT THINGS ARE CALLED A "CATEGORY". CPDB's `typc` is a 3-value
asset class — Fixed Asset, ITT/Vehicles/Equipment, Lump Sum. The Ten-Year
Capital Strategy category is a 138-value programme taxonomy, and it is the one
the Categories page actually joins on. A scope named `category` serving 3 rows
where a page needs 138 is one label with two definitions, which is the defect
that produced two different "Amount Over Budget" figures on this same section.
Both are kept, each named for what it is, and the bare name is retired so
nobody can ask for it and get whichever happens to be wired.
"""
import ast
import os
import re

API = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
SPINE = os.path.join(API, 'build_capital_projects.py')
STATS = os.path.join(API, 'build_capital_stats.py')
ROUTER = os.path.join(API, 'routers', 'capital.py')


def _src(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _code(path):
    """Source with docstrings stripped.

    ⚠ Ten guards in this repo have fired on the prose explaining the very thing
    they scan for. These modules' docstrings quote `budget_lines`, `category`
    and the SQL keywords below, so every scan here reads code only.
    """
    tree = ast.parse(_src(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


# ── the spine carries the taxonomy ───────────────────────────────────────────

def test_the_spine_declares_both_taxonomy_columns_as_arrays():
    """⚠ MULTI-VALUED, measured: a project draws on 1-34 budget lines (mean
    1.45) and 1-10 project types. A scalar column would keep one and silently
    drop the rest."""
    ddl = _code(SPINE)
    assert re.search(r'budget_lines\s+text\[\]', ddl), 'budget_lines must be text[]'
    assert re.search(r'project_types\s+text\[\]', ddl), 'project_types must be text[]'


def test_the_taxonomy_is_aggregated_before_it_touches_the_spine():
    """⚠⚠ THE DEFECT THIS PREVENTS IS THIS REPO'S MOST-SHIPPED ONE. The
    commitments table holds 41,277 rows for 12,929 projects, so joining it into
    the spine's INSERT would multiply the spine — the amendment double-count of
    #262 and #278 in a new table. Aggregate first; a GROUP BY cannot multiply.
    """
    code = _code(SPINE)
    m = re.search(r'async def _attach_budget_lines.*?(?=\nasync def |\ndef |\Z)',
                  code, re.S)
    assert m, '_attach_budget_lines not found'
    body = m.group(0)
    assert 'GROUP BY maprojid' in body, (
        'the commitments must be aggregated to one row per project before '
        f'they reach the spine: {body[:200]}')
    assert 'UPDATE' in body, 'it must update the staged spine, not join into it'


def test_an_empty_string_never_becomes_a_budget_line():
    """⚠ An array holding '' reads as "this project has a budget line" to every
    consumer that checks length."""
    body = _code(SPINE)
    assert body.count('FILTER (') >= 2, (
        'both arrays must filter out blanks before aggregating')
    assert "btrim(coalesce(budgetline, '')) <> ''" in body


def test_the_arrays_are_gin_indexed():
    """⚠ btree cannot answer "which projects are on this line" over an array."""
    code = _code(SPINE)
    assert 'ARRAY_INDEXES' in code
    assert 'USING gin(' in code


def test_a_missing_commitments_table_degrades_rather_than_failing():
    """⚠ A fresh environment may not have ingested commitments yet, and an
    absent taxonomy must not stop the spine building."""
    body = re.search(r'async def _attach_budget_lines.*?(?=\nasync def |\ndef |\Z)',
                     _code(SPINE), re.S).group(0)
    assert 'to_regclass' in body and 'return' in body


# ── the stats scopes ─────────────────────────────────────────────────────────

def _scopes():
    tree = ast.parse(_src(STATS))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, 'id', '') == 'SCOPES' for t in node.targets):
            return [ast.literal_eval(e)[0] for e in node.value.elts]
    raise AssertionError('SCOPES not found')


def test_every_scope_the_budget_pages_need_exists():
    scopes = _scopes()
    for needed in ('budget_line', 'type', 'ten_year_category', 'asset_category'):
        assert needed in scopes, f'{needed} scope missing: {scopes}'


def test_the_ambiguous_bare_category_scope_is_retired():
    """⚠⚠ ONE LABEL, TWO DEFINITIONS. `category` meant CPDB's 3-value asset
    class while the Categories page needs the 138-value Ten-Year Strategy
    taxonomy. Naming both explicitly is what stops a page asking for `category`
    and getting whichever is wired."""
    assert 'category' not in _scopes(), (
        'use asset_category or ten_year_category — never the bare name')
    with open(ROUTER, encoding='utf-8') as fh:
        allowed = re.search(r'allowed = \{(.*?)\}', fh.read(), re.S).group(1)
    assert '"category"' not in allowed, (
        'the endpoint must not accept the ambiguous bare scope name')
    for needed in ('asset_category', 'ten_year_category', 'budget_line', 'type'):
        assert f'"{needed}"' in allowed, f'{needed} not accepted by the endpoint'


def test_the_array_scopes_group_on_the_unnested_value():
    """⚠ Grouping on the ARRAY would produce one row per distinct combination of
    lines — 'this set of 3 lines' — rather than one row per line, which is what
    a budget-line page asks for."""
    tree = ast.parse(_src(STATS))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, 'id', '') == 'SCOPES' for t in node.targets):
            for elt in node.value.elts:
                key, expr, join, _where = ast.literal_eval(elt)
                if key in ('budget_line', 'type'):
                    assert 'unnest' in join, f'{key} must unnest its array'
                    # ⚠ Tie the group expression to the join's OWN alias. My
                    # first version asserted the expression contained no '[',
                    # which `p.budget_lines` satisfies — the column name has no
                    # brackets, so grouping on the raw array passed the guard.
                    alias = re.search(r'\bAS\s+(\w+)\s*$', join.strip())
                    assert alias, f'{key} join names no alias: {join!r}'
                    assert expr.strip() == alias.group(1), (
                        f'{key} must group on the unnested alias '
                        f'{alias.group(1)!r}, not {expr!r} — grouping on the '
                        'array gives one row per distinct SET of lines')


def test_the_scope_endpoint_rejects_an_unknown_scope():
    """A scope name that is not served must 400, not return an empty object that
    reads as "no projects here"."""
    src = _src(ROUTER)
    m = re.search(r'if scope_type not in allowed:.*?\n(.*?)\n\n', src, re.S)
    assert m and 'HTTPException' in m.group(0) and '400' in m.group(0)


# ── the build-time reconciliation ────────────────────────────────────────────

def test_the_array_scopes_are_reconciled_before_the_swap():
    """⚠⚠ A CHECK THAT RUNS AFTER THE SWAP IS NOT A GUARD — it reports a table
    that is already live. This repo has the matching lesson from the other
    direction: a dry run that creates its own table is not dry.
    """
    code = _code(STATS)
    m = re.search(r'async def build\(.*?(?=\nasync def |\ndef |\Z)', code, re.S)
    assert m, 'build() not found'
    body = m.group(0)
    call = body.find('_reconcile(')
    swap = body.find('RENAME TO')
    assert call != -1, 'build() never calls _reconcile'
    assert swap != -1, 'build() has no swap to guard'
    assert call < swap, (
        'the reconciliation must run BEFORE the rename, or it validates a '
        'table that is already serving')
    assert 'refusing swap' in body, 'a failed reconciliation must block the swap'


def test_the_reconciliation_checks_money_and_not_only_counts():
    """⚠⚠ A RECONCILIATION ON COUNTS IS NOT A RECONCILIATION. This section has
    already shipped a by-year chart whose contract count closed exactly at 4,397
    while the money series was $2,500,000 short — a NULL predicate dropped rows
    from the value aggregates and not from COUNT(*). Verified by mutation: a
    money-only divergence of $807,000 with counts still matching is caught.
    """
    tree = ast.parse(_src(STATS))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == '_reconcile')

    # ⚠ READ THE LOOP THAT COMPARES, NOT THE WORDS. My first version asserted
    # 'planned' and 'spent' appeared in the function — which they do, inside the
    # SQL string — so emptying the comparison loop left the guard green while
    # nothing but counts was checked. That is the exact failure this test is
    # about, reproduced in the test itself.
    compared = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.For) and isinstance(node.iter, ast.Tuple):
            for elt in node.iter.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    compared.add(elt.value)
    assert {'planned', 'spent'} <= compared, (
        f'the money measures are not compared, only named: {sorted(compared)}')

    # and the count comparison, which is a separate statement
    body = ast.unparse(fn)
    assert "e_projects'] != row['g_projects'" in body.replace('"', "'"), (
        'the project counts must be compared too')
    # ⚠ `round(...)` on numeric, never a float comparison: award-style columns
    # accumulate float error and an equality test on them is useless.
    assert 'round(' in body


def test_the_reconciliation_recomputes_rather_than_re_reading():
    """⚠ Reading the same aggregate twice proves nothing. It must recompute
    from `capital_projects` independently of the staged table."""
    body = re.search(r'async def _reconcile\(.*?(?=\nasync def |\ndef |\Z)',
                     _code(STATS), re.S).group(0)
    assert 'FROM capital_projects p' in body and 'unnest' in body, (
        'the expected side must come from the spine, not from the staging table')
    assert 'STAGING' in body or '{STAGING}' in body, (
        'the actual side must come from the staged table')
