"""Guards on what a council district page shows beside its own projects.

⚑ Owner decision, 2026-09-06: **the district table stays the focus**, and the
projects that cannot be placed in it appear as COUNTS WITH LINKS — citywide,
borough-wide, and no location at all — never as rows above the district's own.

⚠⚠ THAT IS MEASURED, NOT STYLISTIC. District 22's own capital work is 100
projects; the citywide and borough sets are 1,482 and 1,558. Rendering either as
a table buries a council member's actual district work about 30 to 1.

⚠⚠ AND AN UNPLACED PROJECT CANNOT GO IN THE DISTRICT'S TABLE marked "no
location found", which is the thing the owner asked about. We do not know it is
in this district, and printing it there asserts a location the City never
published. The one path that might have rescued it does not work: community
board text already places 7,799 projects into COMMUNITY districts, but only 11
of 70 community districts even appear to sit inside one council district — and
that is a sample artefact, not geometry.
"""
import asyncio
import importlib.util
import inspect
import os
import re
import sys

API = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
MODULES = os.path.join(API, 'modules')
ROUTER = os.path.join(API, 'routers', 'capital.py')


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_real_money = _load(os.path.join(MODULES, 'capitalmoney.py'), 'capitalmoney')
_real_fmsid = _load(os.path.join(MODULES, 'fmsid.py'), 'fmsid')


class _StubPG:
    queue = []
    seen = []

    @classmethod
    async def select_safe(cls, sql, params):
        cls.seen.append((sql, list(params)))
        return cls.queue.pop(0) if cls.queue else []


def _load_router():
    keys = ('modules', 'capitalmoney', 'fmsid', 'postgrex.asyncmodel', 'postgrex')
    saved = {k: sys.modules.get(k) for k in keys}
    pkg_modules = type(sys)('modules')
    pkg_modules.capitalmoney = _real_money
    pkg_modules.fmsid = _real_fmsid
    sys.modules['modules'] = pkg_modules
    sys.modules['capitalmoney'] = _real_money
    sys.modules['fmsid'] = _real_fmsid
    pkg = type(sys)('postgrex')
    am = type(sys)('postgrex.asyncmodel')
    am.PostgresModelAsync = _StubPG
    pkg.asyncmodel = am
    sys.modules['postgrex'] = pkg
    sys.modules['postgrex.asyncmodel'] = am
    try:
        return _load(ROUTER, 'capital_router_districts_test')
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


cap = _load_router()


def test_the_real_modules_loaded():
    assert cap.capitalmoney is _real_money and cap.fmsid is _real_fmsid


def _run(coro):
    _StubPG.seen = []
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _boro_rows():
    return [{'borough': 'QUEENS', 'n': 41}, {'borough': 'BRONX', 'n': 18},
            {'borough': 'BROOKLYN', 'n': 1}]


def _ctx():
    _StubPG.queue = [_boro_rows()] + [[{'n': 100}] for _ in range(6)]
    return _run(cap._cc_context('22'))


# ── the groups must not overlap the district's own table ─────────────────────

def test_every_group_excludes_projects_attributed_to_a_council_district():
    """⚠⚠ WITHOUT THIS THE SAME PROJECT IS COUNTED TWICE. Measured: 157 of the
    1,639 projects published as CITYWIDE also carry a council-district mapping,
    so they are already in the district's own table."""
    ctx = _ctx()
    assert ctx['groups'], 'no groups produced'

    # ⚠⚠ CHECK THE EMITTED QUERY, NOT THE SERVED DICT. The first version of this
    # guard asserted `filters['in_cc'] is False` — and passed with the exclusion
    # deleted from the counting call, because the dict and the count were two
    # separate expressions of one intent. A guard that reads the input cannot
    # see what the query did; this reads the SQL the counts actually ran.
    counts = [sql for sql, _p in _StubPG.seen if sql.startswith('SELECT count(*)')]
    assert len(counts) == len(ctx['groups']), (
        f'{len(ctx["groups"])} groups but {len(counts)} count queries')
    for g, sql in zip(ctx['groups'], counts):
        assert "dist_type = 'cc'" in sql and 'NOT EXISTS' in sql, (
            f"{g['key']}'s count does not exclude projects already placed in a "
            f'council district: {sql}')
        assert g['filters'].get('in_cc') is False, (
            f"{g['key']} links without that exclusion: {g['filters']}")


def test_the_three_kinds_of_group_are_all_present():
    keys = [g['key'] for g in _ctx()['groups']]
    assert keys[0] == 'citywide', 'citywide is a published fact and leads'
    assert 'borough' in keys and keys[-1] == 'no_location'


def test_citywide_is_described_as_published_not_missing():
    """⚠ 'Citywide' is a value the City published, not an absent one. Describing
    it as missing data would discard a fact."""
    g = [x for x in _ctx()['groups'] if x['key'] == 'citywide'][0]
    assert 'publish' in g['note'].lower()
    assert 'no location' not in g['label'].lower()


def test_a_borough_group_says_it_may_not_be_this_district():
    g = [x for x in _ctx()['groups'] if x['key'] == 'borough'][0]
    assert 'may or may not' in g['note']


def test_every_link_uses_parameters_the_list_endpoint_accepts():
    """⚠⚠ A FILTER KEY THE ENDPOINT DOES NOT TAKE IS A DEAD LINK that renders
    a plausible count next to a list of everything. FastAPI ignores unknown
    query parameters, so this fails silently in the reassuring direction."""
    accepted = set(inspect.signature(cap.capital_projects).parameters)
    for g in _ctx()['groups']:
        unknown = set(g['filters']) - accepted
        assert not unknown, (
            f"{g['key']} links with parameter(s) the list endpoint ignores: "
            f"{sorted(unknown)}")


# ── borough derivation ───────────────────────────────────────────────────────

def test_the_borough_is_derived_only_from_single_district_projects():
    """⚠⚠ THE RESTRICTION IS THE MEASUREMENT. A project carries ONE borough
    label, so one spanning many districts says nothing about any of them:
    district 22 picked up BROOKLYN from the East River Ferry Route, which runs
    through 11 districts."""
    _ctx()
    sql = _StubPG.seen[0][0]
    assert 'HAVING count(*) = 1' in sql, (
        'the borough query must count only projects in exactly one council '
        f'district: {sql}')


def test_all_boroughs_are_served_and_only_some_are_linked():
    """⚠ Everything measured is disclosed; `primary` says which earn a link.
    Dropping the tail silently is how a page states a district's geography more
    confidently than the data does."""
    ctx = _ctx()
    assert [b['borough'] for b in ctx['boroughs']] == ['QUEENS', 'BRONX', 'BROOKLYN']
    primary = {b['borough'] for b in ctx['boroughs'] if b['primary']}
    assert primary == {'QUEENS', 'BRONX'}, (
        'one project at 1.7% is a label disagreeing with the geometry; 18 '
        'Rikers Island projects at 30% is a fact about the district')
    linked = {g.get('borough') for g in ctx['groups'] if g['key'] == 'borough'}
    assert linked == primary


def test_a_straddling_district_is_not_forced_to_one_borough():
    """⭐ District 22 is Astoria, Queens, and 18 of its projects are labelled
    BRONX — every one a Rikers Island jail facility. Rikers is geographically in
    the Bronx and administratively part of Queens. Both labels are correct, and
    a rule that picked one would delete a real answer."""
    ctx = _ctx()
    assert len([g for g in ctx['groups'] if g['key'] == 'borough']) == 2


def test_the_threshold_is_served_not_implied():
    rule = _ctx()['borough_rule']
    assert rule['min_projects'] == cap._BOROUGH_MIN_PROJECTS
    assert rule['min_share_pct'] == cap._BOROUGH_MIN_SHARE
    assert 'exactly one council district' in rule['basis']


# ── borough spelling ─────────────────────────────────────────────────────────

def test_richmond_and_staten_island_are_one_borough():
    """⚠⚠ MEASURED: `RICHMOND` 194 rows and `STATEN ISLAND` 399 are the same
    place under the county name and the borough name. Counting them separately
    understates Staten Island by a third and invents a sixth borough."""
    assert cap._norm_borough('Richmond') == 'STATEN ISLAND'
    assert cap._norm_borough('richmond') == cap._norm_borough('Staten Island')
    assert cap._norm_borough('  staten   island ') == 'STATEN ISLAND'


def test_both_sides_of_the_borough_comparison_are_normalised():
    """⚠⚠ NORMALISING ONLY ONE SIDE IS WORSE THAN NEITHER. Canonicalising the
    caller's value to STATEN ISLAND and comparing it against the raw column
    drops the 194 rows stored as RICHMOND — a filter that looks careful and
    returns a third fewer projects than it should."""
    sql = cap._borough_sql()
    for src, dst in cap._BOROUGH_ALIASES.items():
        assert f"'{src}'" in sql and f"'{dst}'" in sql, (
            f'the column expression does not map {src} -> {dst}: {sql}')
    where, params = cap._list_filters(borough='Richmond')
    assert params == ['STATEN ISLAND']
    assert 'RICHMOND' in where[0], 'the stored spelling must be mapped too'


def test_mixed_case_boroughs_cannot_split_a_count():
    """The column is mixed-case across publication vintages — 1,161 'Manhattan'
    against 708 'MANHATTAN'."""
    _where, params = cap._list_filters(borough='Manhattan')
    assert params == ['MANHATTAN']
    assert 'upper(' in cap._borough_sql()


# ── scope ────────────────────────────────────────────────────────────────────

def test_only_a_council_district_gets_this_block():
    """⚠ An agency or NTA page has no borough band to offer, and attaching one
    would imply a geography those scopes do not have."""
    import ast
    with open(ROUTER, encoding='utf-8') as fh:
        src = fh.read()

    # ⚠ Read the CODE, not the first mention. The key is named in this module's
    # prose too, and a line-scoped regex found the docstring and then failed on
    # a construct that spans two lines — the own-prose trap this repo has paid
    # for repeatedly, in its "matched the wrong occurrence" form.
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == 'capital_scope_stats')
    gated = False
    for node in ast.walk(fn):
        if isinstance(node, ast.IfExp):
            body = ast.unparse(node.body)
            test = ast.unparse(node.test)
            if 'not_in_this_district' in body:
                gated = 'scope_type' in test and "'cc'" in test.replace('"', "'")
    assert gated, (
        'the district block must be attached only for the cc scope — an agency '
        'or NTA page has no borough band to offer, and attaching one would '
        'imply a geography those scopes do not have')
