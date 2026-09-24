"""Guards on resolving and serving ONE capital project.

⚠⚠ THE DEFECT THESE EXIST FOR. `docs/CAPITAL-SECTION-PLAN.md` §5.3 specified
`/p/{fms_id}`, on the understanding that an FMS id names a project. Measured
2026-09-05 over the 17,024-row spine, it does not: **1,160 ids are carried by
more than one agency, covering 2,371 rows** — 14% of the universe. Within the
current plan alone it is 24 ids / 48 rows, which is the figure the plan was
written against and exactly why the problem was invisible: owner decision B
pulled the Dashboard and 2023 tails into scope, and the collisions live there.

`maprojid` is unique (12,929 distinct over 12,929 non-null) but exists only for
current-plan rows. `(agency_key, fms_id)` is the only key unique across all
17,024, so the endpoint resolves to a SET and refuses to choose.

⚠ THE WORKED EXAMPLE FOR ⚑ F AT PROJECT GRAIN, found while building this and
served live: **826HED-545, the Croton Filtration Plant**, reads planned
commitments **$5.1M** against adopted **$3,255.9M** and spent **$2,848.7M**.
Planned is 0.16% of adopted. Drawn as a funnel, this one project shows $3.25
billion vanishing between two boxes — which is why the project payload carries
its own non-funnel note rather than the citywide one.

⚠ The other half is the id's spelling: four publishers write it three ways, and
`modules/fmsid` owns which to try. The property that must not regress is that
`02200901` — a real id that begins with three digits — resolves as ITSELF and
never as its own truncation. 814 project ids are that shape.
"""
import asyncio
import importlib.util
import os
import re
import sys

import pytest

API = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
MODULES = os.path.join(API, 'modules')
ROUTER = os.path.join(API, 'routers', 'capital.py')


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ⚠⚠ conftest replaces the whole `modules` package with a MagicMock, so a
# by-path load of the router would import MOCKS of capitalmoney and fmsid and
# every assertion below would pass against a mock that asserts nothing. The real
# modules are injected first, and `test_the_real_modules_loaded` proves it.
_real_money = _load(os.path.join(MODULES, 'capitalmoney.py'), 'capitalmoney')
_real_fmsid = _load(os.path.join(MODULES, 'fmsid.py'), 'fmsid')


class _StubPG:
    """Stands in for PostgresModelAsync; records SQL and returns queued rows."""
    queue = []
    seen = []

    @classmethod
    async def select_safe(cls, sql, params):
        cls.seen.append((sql, list(params)))
        return cls.queue.pop(0) if cls.queue else []


def _load_router():
    # ⚠⚠ The router's FIRST import is `from modules import capitalmoney, fmsid`,
    # and conftest's `modules` MagicMock SATISFIES it — so the ImportError
    # fallback never runs and injecting bare `capitalmoney`/`fmsid` into
    # sys.modules achieves nothing. The mocked package is swapped for a real one
    # carrying the real submodules, and restored afterwards.
    keys = ('modules', 'capitalmoney', 'fmsid', 'postgrex.asyncmodel', 'postgrex')
    saved = {k: sys.modules.get(k) for k in keys}
    real_modules_pkg = type(sys)('modules')
    real_modules_pkg.capitalmoney = _real_money
    real_modules_pkg.fmsid = _real_fmsid
    sys.modules['modules'] = real_modules_pkg
    sys.modules['capitalmoney'] = _real_money
    sys.modules['fmsid'] = _real_fmsid
    pkg = type(sys)('postgrex')
    asyncmodel = type(sys)('postgrex.asyncmodel')
    asyncmodel.PostgresModelAsync = _StubPG
    pkg.asyncmodel = asyncmodel
    sys.modules['postgrex'] = pkg
    sys.modules['postgrex.asyncmodel'] = asyncmodel
    try:
        return _load(ROUTER, 'capital_router_under_test')
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


cap = _load_router()


def test_the_real_modules_loaded():
    """⚠ Without this the whole file could be asserting against MagicMocks."""
    assert cap.capitalmoney is _real_money
    assert cap.fmsid is _real_fmsid
    assert _real_money.MEASURE_KEYS[0] == 'planned_usd'
    assert _real_fmsid.candidates('02200901') == ['02200901']


def _run(coro):
    _StubPG.seen = []
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _spine_row(**kw):
    row = {'agency_key': '826', 'fms_id': 'HED-545', 'maprojid': '826HED-545',
           'description': 'CROTON FILTRATION PLANT', 'agency_name': 'DEP',
           'in_current_plan': True, 'in_dashboard': True, 'in_cpdd_2023': True,
           'ccpversion': 'fisa_2026', 'dash_period': '202605',
           'current_phase': '(Completed)'}
    row.update(kw)
    return row


# ── resolution ───────────────────────────────────────────────────────────────

def test_a_shared_id_returns_the_choices_and_never_picks_one():
    """⚠⚠ THE HEADLINE PROPERTY. 1,160 ids are shared. Picking silently would
    show a reader one agency's project under another agency's id."""
    _StubPG.queue = [[_spine_row(agency_key='856', fms_id='110WLM'),
                      _spine_row(agency_key='068', fms_id='110WLM',
                                 in_current_plan=False)]]
    out = _run(cap.capital_project('110WLM'))
    assert out['found'] is False and out['ambiguous'] is True
    assert 'id' not in out, 'an ambiguous lookup must not resolve to one project'
    assert {c['agency_key'] for c in out['choices']} == {'856', '068'}
    for c in out['choices']:
        assert 'agency_key' in c and 'in_current_plan' in c, (
            'a reader choosing between two agencies needs enough to choose')


def test_an_agency_narrows_a_shared_id():
    _StubPG.queue = [[_spine_row(agency_key='068', fms_id='110WLM')]]
    out = _run(cap.capital_project('110WLM', agency='068'))
    assert out['found'] is True and out['id']['agency_key'] == '068'
    sql, params = _StubPG.seen[0]
    assert 'agency_key' in sql and '068' in params


def test_a_pinned_agency_constrains_every_branch_of_the_lookup():
    """⚠⚠ A LIVE DEFECT THIS CAUGHT, THROUGH SQL PRECEDENCE RATHER THAN LOGIC.

    The resolver ORs several id spellings and then appends the agency filter.
    Unparenthesised, `A OR B AND C` parses as `A OR (B AND C)` — AND binds
    tighter — so the agency constrained only the last branch. Measured against
    the live API before the fix, `826HED-545?agency=999` returned agency
    **826's** project: one agency's project served under another's filter, which
    is the single thing this resolver exists to prevent.

    ⚠ The first version of this guard asserted the SQL CONTAINED 'agency_key'
    and the parameter. It passed throughout, because a test that inspects a
    query's text cannot see its value. This one EVALUATES each emitted predicate
    over every combination of its atoms and demands the one property that
    matters: with the agency not matching, nothing matches.

    ⚠ It checks EVERY lookup query, not the first. The resolver runs a
    qualified tier and then a bare fallback; an agency filter correct in one and
    missing from the other is the obvious way to half-fix this.
    """
    import itertools
    _StubPG.queue = [[], []]          # force both tiers to run
    _run(cap._resolve_project('110WLM', agency='068'))
    lookups = [sql for sql, _p in _StubPG.seen if 'FROM capital_projects' in sql]
    assert len(lookups) >= 2, f'expected a qualified tier and a fallback, got {len(lookups)}'

    for sql in lookups:
        where = sql.split('WHERE', 1)[1].split('ORDER BY')[0]
        expr = where
        expr = re.sub(r"upper\(coalesce\(maprojid,\s*''\)\)\s*=\s*\$\d+", 'A', expr)
        expr = re.sub(r"upper\(agency_key \|\| fms_id\)\s*=\s*ANY\(\$\d+\)", 'B', expr)
        expr = re.sub(r"upper\(fms_id\)\s*=\s*ANY\(\$\d+\)", 'D', expr)
        expr = re.sub(r"upper\(agency_key\)\s*=\s*\$\d+", 'C', expr)

        # ⚠ Refuse to guess. If the SQL is rewritten into a shape this cannot
        # parse, fail loudly rather than evaluate a fragment and report it
        # clean — that is the zero-files scanner in a new place.
        leftover = re.sub(r"[ABCD()\s]", '', re.sub(r"\bAND\b|\bOR\b", '', expr))
        assert not leftover, (
            'the guard cannot read this predicate, so it cannot vouch for it: '
            f'{where.strip()!r} (unparsed: {leftover!r})')
        assert 'C' in expr, f'no agency filter in a lookup query: {where.strip()!r}'

        pyexpr = expr.replace(' AND ', ' and ').replace(' OR ', ' or ')
        # ⚠ Find the atoms AFTER the keywords are gone: `'D' in expr` is true
        # for any predicate containing the word AND, and `'A' in expr` likewise.
        # That is the same trap as stripping atoms before keywords, one line up,
        # and it made this guard read three atoms where the query has two.
        bare_atoms = re.sub(r"\bAND\b|\bOR\b", ' ', expr)
        atoms = [c for c in 'ABD' if re.search(rf'\b{c}\b', bare_atoms)]
        for combo in itertools.product([True, False], repeat=len(atoms)):
            env = dict(zip(atoms, combo))
            for c in (True, False):
                env['C'] = c
                got = eval(pyexpr, {'__builtins__': {}}, dict(env))
                if not c:
                    assert not got, (
                        'a row whose agency does not match the pinned agency is '
                        f'still selected ({env}): {where.strip()!r}')
                else:
                    assert got == any(combo), (
                        'pinning an agency must not change which ids match: '
                        f'{where.strip()!r}')


def test_an_agency_qualified_form_outranks_a_bare_one():
    """⚠⚠ THE TIERS ARE THE FIX FOR THE SHARED-ID PROBLEM, and their ORDER is
    the property. Measured 2026-09-06: `agency_key || fms_id` is unique across
    all 17,024 rows and is byte-identical to CPDB's own published `maprojid` on
    all 12,929 that have one — so a form naming the agency identifies a project
    where a bare id may not.

    `fmsid.candidates` returns spellings to try IN ORDER; ORing them into one
    query throws that away. It did: `856 110WLM` matched agency 856 by its
    qualified form and BOTH agencies by the bare one, and reported itself
    ambiguous to a caller who had already said which agency they meant.
    """
    # qualified tier hits -> the bare fallback must not run at all
    _StubPG.queue = [[_spine_row(agency_key='856', fms_id='110WLM')]]
    rows = _run(cap._resolve_project('856110WLM'))
    assert len(rows) == 1 and rows[0]['agency_key'] == '856'
    lookups = [sql for sql, _p in _StubPG.seen if 'FROM capital_projects' in sql]
    assert len(lookups) == 1, (
        'a qualified match must end the search — running the bare fallback '
        'anyway is what reintroduces the ambiguity it exists to remove')

    # qualified tier misses -> fall back, and surface a genuine ambiguity
    _StubPG.queue = [[], [_spine_row(agency_key='856', fms_id='110WLM'),
                          _spine_row(agency_key='068', fms_id='110WLM')]]
    rows = _run(cap._resolve_project('110WLM'))
    assert len(rows) == 2, 'a bare shared id must still return every candidate'


def test_the_qualified_set_holds_no_bare_spelling():
    """⚠ The bug this fixed: putting the bare candidate into the qualified set
    made `856 110WLM` match the agency-qualified row AND both bare rows in one
    query, so a caller who named the agency got "ambiguous"."""
    _StubPG.queue = [[], []]
    _run(cap._resolve_project('856 110WLM'))
    _sql, params = _StubPG.seen[0]
    qualified = params[1]
    assert '856110WLM' in qualified, 'the recombined agency form must be tried'
    assert '110WLM' not in qualified, (
        'the bare id is not an agency-qualified spelling and must not be in '
        f'this tier: {qualified}')


def test_a_missing_id_says_which_spellings_were_tried():
    """⚠ A bare 404 makes an id that exists under another agency look absent."""
    _StubPG.queue = [[]]
    out = _run(cap.capital_project('NOSUCHID9'))
    assert out['available'] is True and out['found'] is False
    assert out['tried'] == ['NOSUCHID9']
    assert out['note'].strip()


def test_an_all_numeric_id_is_never_truncated_by_the_endpoint():
    """⚠⚠ 814 project ids begin with three digits. Truncating `02200901` to
    `00901` would silently miss every one of them."""
    _StubPG.queue = [[_spine_row(agency_key='002', fms_id='02200901',
                                 maprojid=None)]]
    _run(cap.capital_project('02200901'))
    _sql, params = _StubPG.seen[0]
    tried = params[1]
    assert tried == ['02200901'], f'must not offer a truncation: {tried}'


def test_every_id_spelling_reaches_the_project():
    """The legacy URL form, the Parks/Climate feed form and the bare id must all
    land. ⚠ The exact value is always tried FIRST, or a real id that merely
    looks prefixed resolves as its own truncation — 814 ids begin with three
    digits."""
    for ident in ('846P-5PLG12A', '846 P-5PLG12A'):
        _StubPG.queue = [[_spine_row(agency_key='846', fms_id='P-5PLG12A')]]
        _run(cap._resolve_project(ident))
        sql, params = _StubPG.seen[0]
        assert '846P-5PLG12A' in params[1], f'{ident} must try the agency form'
        # ⚠ Binding the right parameter proves nothing if the query does not use
        # it against the right expression. Deleting the concatenation left this
        # guard green until it also checked what the parameter is compared TO.
        assert 'agency_key || fms_id' in sql, (
            'the qualified tier must compare against the agency-concatenated '
            f'form, which is CPDB\'s own published key: {sql}')

    # the bare spelling reaches the fallback tier
    _StubPG.queue = [[], [_spine_row(agency_key='846', fms_id='P-5PLG12A')]]
    _run(cap._resolve_project('P-5PLG12A'))
    bare_sql = [(sql, p) for sql, p in _StubPG.seen if 'upper(fms_id)' in sql]
    assert bare_sql, 'the bare id must still be tried when nothing qualified matches'
    assert 'P-5PLG12A' in bare_sql[0][1][0]


# ── the payload ──────────────────────────────────────────────────────────────

def _full():
    _StubPG.queue = [
        [_spine_row()],                       # spine
        [{'source': 'dash_sched', 'period': '202605', 'variance_days': 12,
          'delay_reason': 'Site conditions', 'budget_usd': None,
          'orig_budget_usd': None, 'spend_usd': None, 'phase': 'Construction',
          'start_date': None, 'end_date': None, 'forecast_completion': None}],
        [],                                   # commitments
        [],                                   # districts
        [],                                   # geometry
    ]
    return _run(cap.capital_project('826HED-545'))


def test_a_project_gets_the_project_note_not_the_citywide_one():
    """⚠⚠ The citywide note cites populations "shown beside" each measure. A
    project page has no populations, so that sentence would name a denominator
    that is not on the page."""
    out = _full()
    assert out['money']['note'] == _real_money.NOT_A_FUNNEL_NOTE_PROJECT
    assert out['money']['note'] != _real_money.NOT_A_FUNNEL_NOTE


def test_a_project_serves_no_population():
    """⚠ A population of 1 or 0 would invent a denominator. Whether the City
    publishes a measure for this project is carried by `value: None`."""
    out = _full()
    for m in out['money']['measures']:
        assert m['population'] is None
        assert m['definition'] and m['source']


def test_the_spine_money_map_covers_exactly_the_published_measures():
    """One vocabulary. A key here that capitalmoney does not know would serve a
    figure with no definition and no publisher."""
    assert sorted(cap._SPINE_MONEY) == sorted(_real_money.MEASURE_KEYS)


def test_every_empty_panel_states_why():
    """⚠ An empty panel and a missing panel look identical, and the empty one is
    the common truth: NYC publishes a location for a quarter of these projects."""
    out = _full()
    for key in ('history', 'commitments', 'districts', 'geometry'):
        panel = out[key]
        if not panel['available']:
            assert panel['reason'].strip(), f'{key} is empty and does not say why'
            assert panel['rows'] == [] and panel['count'] == 0


def test_presence_in_each_publication_is_stated():
    """⚠ A project absent from the current plan is one NYC stopped planning —
    a finding, not a hole in our data."""
    out = _full()
    p = out['presence']
    for k in ('in_current_plan', 'in_dashboard', 'in_2023_series'):
        assert k in p
    assert p['note'].strip()


def test_the_delay_reason_comes_from_the_schedule_history():
    out = _full()
    assert out['schedule']['variance_days'] == 12
    assert out['schedule']['delay_reason'] == 'Site conditions'


def test_a_project_with_no_schedule_says_the_city_publishes_none():
    _StubPG.queue = [[_spine_row(current_phase=None)], [], [], [], []]
    out = _run(cap.capital_project('826HED-545'))
    assert out['schedule']['available'] is False
    assert 'publishes no' in out['schedule']['reason']


def test_the_project_payload_carries_its_vintage():
    out = _full()
    versions = {s.get('version') or s.get('period') for s in out['sources']}
    assert 'fisa_2026' in versions and '202605' in versions


def test_the_router_does_not_inline_the_money_copy():
    with open(ROUTER, encoding='utf-8') as fh:
        src = fh.read()
    assert 'not stages of one pot' not in src
    assert re.search(r'capitalmoney\.payload\([^)]*scope="project"', src), (
        'the project endpoint must ask for the project-scoped note by name')


# ── list and map ─────────────────────────────────────────────────────────────

def test_a_page_number_can_never_go_below_one_and_is_an_int():
    """⚠⚠ #321 IN FULL. A disabled pagination control kept a live href, a
    crawler walked page 0, -1, -2 downward with no floor, and the raw value
    reached a cache key — so '1', 1 and '01' minted three entries for one page
    and a 1.2 GB cache. Floor AND cast."""
    for bad in ('0', '-1', '-42', 'abc', '', None, '1.5'):
        got = cap._page(bad)
        assert isinstance(got, int) and got >= 1, f'{bad!r} -> {got!r}'
    assert cap._page('01') == 1 and cap._page(1) == 1 and cap._page('1') == 1, (
        'three spellings of page one must be one value, or they are three '
        'cache keys')
    assert cap._page('7') == 7, 'a legitimate page must still work'
    assert cap._page('999', maximum=200) == 200


def test_every_filter_column_is_table_qualified():
    """⚠⚠ A LIVE 500 THIS CAUGHT. The fragments are shared by the list (one
    table) and the map (JOINed to geometry), and BOTH tables carry `agency_key`
    and `fms_id`. Unqualified, `/get/capital/geojson?agency=DDC` raised
    AmbiguousColumnError while the unfiltered map returned 4,560 features
    perfectly — a defect only a filtered call could reveal.
    """
    where, _params = cap._list_filters(
        agency='DDC', category='Education', phase='Construction',
        borough='BRONX', in_plan=True, has_schedule=True, q='park')
    assert where, 'the guard must have something to inspect'
    for frag in where:
        # Every bare column reference must carry an alias. `gx.` is the
        # existence subquery's own table.
        #
        # ⚠ THE TRAILING `\b` IS LOAD-BEARING. Without it `[a-z_]{3,}` is greedy
        # but backtracks: on `trim(` it tries `trim`, the lookahead rejects the
        # `(`, and it settles for `tri` — which passes the lookahead and is
        # reported as an unqualified column. That fired on correct SQL the
        # moment a CASE expression introduced `trim`, which is a guard crying
        # wolf on the code it exists to protect. With `\b`, a function name is
        # matched whole and excluded by the `(` that follows it.
        # ⚠⚠ A TABLE NAME IS NOT A COLUMN — second wolf-cry, and the same shape
        # as the `trim` one above. `FROM capital_projects a` in the agency
        # resolution's subquery matched as a bare column while every column in
        # that fragment carries an alias, and the map it exists to protect was
        # measured serving all 31 agencies correctly. A name introduced by
        # `FROM` is excluded the way a function name is excluded by its `(`.
        # ⚠⚠ THE ALTERNATION IS `\b`-ANCHORED, AND MY FIRST CORRECTION WAS NOT —
        # adding bare `a` and `b` as subquery aliases made `(?!…|a|b)` reject
        # every token STARTING with a or b, so `agency_acro` stopped being
        # scanned and two deliberate mutations passed. Single- and two-letter
        # aliases never need excluding anyway: `[a-z_]{3,}` cannot match them.
        scan = re.sub(r'\bFROM\s+[a-z_]+', 'FROM', frag)
        bare = re.findall(r'(?<![\w.])(?!(?:upper|coalesce|trim|count|SELECT|FROM'
                          r'|WHERE|EXISTS|NOT|AND|OR|IS|TRUE|FALSE|NULL|ILIKE'
                          r'|LIMIT|DISTINCT)\b)'
                          r'([a-z_]{3,})\b(?!\s*\()', scan)
        assert not bare, f'unqualified column(s) {bare} in: {frag!r}'


def test_the_location_subquery_does_not_reuse_the_maps_alias():
    """⚠ The map binds `g` to the geometry table. An EXISTS subquery reusing
    `g` would correlate to the outer row instead of testing existence."""
    where, _ = cap._list_filters(has_location=True)
    frag = ' '.join(where)
    assert 'capital_project_geometry gx' in frag
    assert re.search(r'\bg\.', frag) is None, (
        'the subquery must not reference the alias the map query binds')


def test_the_list_serves_the_true_total_beside_the_page():
    """⚠ A capped list presented as the whole inventory is a defect this repo
    has shipped more than once."""
    _StubPG.queue = [[{'n': 17024}], [{'agency_key': '826', 'fms_id': 'X'}]]
    out = _run(cap.capital_projects(per_page='1'))
    assert out['total'] == 17024 and out['showing'] == 1
    assert out['pages'] == 17024
    assert out['note'].strip()


def test_sort_is_a_whitelist():
    """A caller-supplied column name that merely looks safe is still a way to
    order by something the page cannot explain."""
    for bad in ('; DROP TABLE capital_projects', 'planned_total_usd', '', None):
        _StubPG.queue = [[{'n': 0}], []]
        _run(cap.capital_projects(sort=bad))
        sql = _StubPG.seen[1][0]
        assert 'ORDER BY planned_total_usd' in sql, (
            f'{bad!r} must fall back to the default sort, got: {sql}')
    _StubPG.queue = [[{'n': 0}], []]
    _run(cap.capital_projects(sort='spent', direction='asc'))
    assert 'ORDER BY spent_total_usd ASC' in _StubPG.seen[1][0]


def test_the_map_computes_its_denominator_rather_than_assuming_it():
    """⚠ The legend's "N of M" must count the SAME filters without the location
    requirement. A typed or reused M is the stale-disclosure defect."""
    _StubPG.queue = [
        [{'agency_key': '826', 'fms_id': 'X', 'maprojid': None,
          'agency_acro': 'DEP', 'description': 'd', 'type_category': None,
          'current_phase': None, 'in_current_plan': True,
          'planned_total_usd': None, 'geom_kind': 'point',
          'centroid_lat': 40.7, 'centroid_lng': -73.9}],
        [{'n': 2202}],
    ]
    out = _run(cap.capital_geojson(agency='DDC'))
    c = out['coverage']
    assert c['mapped'] == 1 and c['matching_filters'] == 2202
    assert c['unmapped'] == 2201
    # ⚠ The note is thousands-separated at its owner (the endpoint), because the
    # page prints it verbatim rather than retyping a denominator that goes stale
    # under a filter. Assert the SEPARATED form: a substring check on the raw
    # digits would pass on a note that had silently lost its formatting, and a
    # check that ignores formatting cannot see the sentence a reader gets.
    assert '1 of 2,202 matching projects' in c['note']


def test_a_correctly_empty_map_says_it_is_not_a_broken_one():
    """⚠⚠ Measured: geometry exists for 4,560 of the 12,929 current-plan
    projects and for 0 of the 4,095 outside it, because DCP publishes geometry
    against the current plan version. `?in_plan=false` is therefore always an
    empty FeatureCollection, which without this sentence looks like a failure."""
    _StubPG.queue = [[], [{'n': 4095}]]
    out = _run(cap.capital_geojson(in_plan=False))
    assert out['features'] == []
    note = out['coverage']['note']
    assert 'empty map, not a failed one' in note
    assert 'current Capital Commitment Plan' in note


def test_a_map_with_features_does_not_claim_to_be_empty():
    """The converse — the explanation must not appear when it is untrue."""
    _StubPG.queue = [
        [{'agency_key': '8', 'fms_id': 'X', 'maprojid': None, 'agency_acro': 'A',
          'description': None, 'type_category': None, 'current_phase': None,
          'in_current_plan': True, 'planned_total_usd': None,
          'geom_kind': 'point', 'centroid_lat': 1.0, 'centroid_lng': 2.0}],
        [{'n': 10}]]
    out = _run(cap.capital_geojson())
    assert 'empty map' not in out['coverage']['note']


def test_the_map_serves_centroids_not_footprints():
    """⚠⚠ MEASURED, NOT PREFERRED. The published geometry is 2,776 points
    (169 kB of WKT) plus 1,784 polygons (20 MB), largest single footprint
    618 kB. Citywide footprints would be a 20 MB payload; centroids are ~534 kB
    for all 4,560. The real outline is a separate, lazy fetch."""
    _StubPG.queue = [[], [{'n': 0}]]
    _run(cap.capital_geojson())
    sql = _StubPG.seen[0][0]
    assert 'centroid_lat' in sql and 'centroid_lng' in sql
    assert 'wkt' not in sql.lower(), (
        'the citywide map must not select footprints — 20 MB of them exist')


def test_the_map_accepts_every_list_filter_that_changes_which_projects_show():
    """⚠⚠ A PROPERTY OF THE PAGE, NOT A TIDINESS PREFERENCE — and I nearly
    broke it by reading the plan instead of the page. `/projects` builds its map
    from the DataTable's CURRENTLY FILTERED rows, so filtering the table moves
    the map. That is the single best thing about that page, and server-side
    paging destroys it unless the map can be filtered identically.

    Verified against the live data under seven filter combinations: the list's
    `total` and the map's `matching_filters` agree exactly every time.

    ⚠ `has_location` is excluded BY DESIGN: the map INNER JOINs the geometry, so
    the filter would either change nothing or empty the map, and `coverage`
    already reports the unmapped count. `page`, `per_page`, `sort` and
    `direction` are excluded because they change presentation, not membership.
    """
    import inspect
    list_params = set(inspect.signature(cap.capital_projects).parameters)
    map_params = set(inspect.signature(cap.capital_geojson).parameters)

    presentation = {'page', 'per_page', 'sort', 'direction'}
    by_design = {'has_location', 'has_borough'}
    membership = list_params - presentation - by_design

    missing = membership - map_params
    assert not missing, (
        'the map cannot be filtered the way the list can, so a filtered table '
        f'and its map would disagree: {sorted(missing)}')


def test_the_map_and_the_list_build_their_filters_from_one_owner():
    """⚠ Two spellings of one filter is how the two figures on a page come to
    disagree. Both must go through `_list_filters`."""
    import ast
    with open(ROUTER, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())

    # ⚠⚠ CHECK THE ASSIGNMENT, NOT THE MENTION. The first version asserted
    # `'_list_filters(' in` the function body — and `capital_geojson` contains a
    # SECOND call for the legend's denominator, so deleting the one that builds
    # the serving WHERE left the guard green. Sixth time in this session's work
    # that a guard read a mention rather than what the code does.
    for name in ('capital_projects', 'capital_geojson'):
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
        built_by = None
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Tuple):
                names = [getattr(e, 'id', '') for e in node.targets[0].elts]
                if names[:1] == ['where']:
                    built_by = node.value
                    break
        assert built_by is not None, f'{name} never assigns (where, params)'
        assert isinstance(built_by, ast.Call) and \
            getattr(built_by.func, 'id', '') == '_list_filters', (
                f'{name} builds its WHERE from '
                f'{ast.unparse(built_by)!r} instead of the shared owner — two '
                'spellings of one filter is how a page\'s two figures disagree')
