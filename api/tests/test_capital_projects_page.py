"""Guards on the `/projects` index — the list, the map, and the seam between them.

⚠⚠ WHAT THIS FILE IS ANSWERING. `/projects` shows the same question twice: a
paginated table and a map. Measured on 2026-09-06, before this page was written,
the two endpoints behind it already disagreed — `?has_location=false` listed
12,464 projects with no published location while `/get/capital/geojson` drew
**4,560 pins**, every one a project the list had excluded, under a legend
reading "of 17,024". Two of the list's membership-affecting filters simply never
reached the map.

⚠⚠ AND THE GUARD DISCIPLINE THIS FILE IS WRITTEN UNDER. Six guards in the
previous session on this section passed against a real, reintroduced bug,
because each inspected a MENTION or an INPUT rather than what the code did: the
served `filters` dict while the count came from a separate call; a bound
parameter rather than the expression it was compared to; a WORD in a function
body (`'planned' in body` is satisfied by the SQL string); a string inside an
`@if` rather than the `{{ }}` that echoes it. Every guard below was verified by
reintroducing its bug and watching it fail — and the mutation was asserted to
have LANDED first, because three mutations in that session were themselves inert
and read as useless guards.
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROOT = os.path.realpath(os.path.join(API, '..'))

ROUTER = os.path.join(API, 'routers', 'capital.py')
BUILDER = os.path.join(API, 'build_capital_projects.py')
CONTROLLER = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Projects.php')
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'projects.blade.php')
# ⚠ `projectsA.blade.php` LEFT THIS LIST BECAUSE IT WAS DELETED (2026-09-10),
# not because the claim stopped mattering: it was one of three unrouted `*A`
# orphans, reachable by no route, still carrying `Amount Over Budget` tiles and
# nine `pstats-*` hydration URLs. A guard below asserts the file is genuinely
# gone, so an entry cannot be dropped from here to dodge a failure.
COPY_VIEWS = [
    os.path.join(ROOT, 'app', 'resources', 'views', v) for v in
    ('orgprojectsection.blade.php',
     'categoryA.blade.php', 'budgetLineA.blade.php')
]
DELETED_ORPHAN_VIEWS = ('capitalA.blade.php', 'projectsA.blade.php',
                        'orgprojectA.blade.php')

# Paging and ordering change WHICH SLICE you see, never WHICH PROJECTS match, so
# the map has no use for them. Everything else the list accepts does affect
# membership and must reach the map.
_SLICE_ONLY = {'page', 'per_page', 'sort', 'direction'}


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()

def _php_method(php, name):
    """One PHP method's body, bounded by the NEXT declaration.

    ⚠⚠ THIS REPLACES `php.index('public function projects_a()')` AS AN END
    BOUND, used at five sites across three test files. Naming a SIBLING as the
    boundary means deleting or renaming that sibling breaks guards about a
    different method — which is exactly what happened when the unrouted `*A`
    orphans were removed (2026-09-10): five guards about
    `Projects::projects()` failed with `ValueError: substring not found`,
    none of them about anything that had changed.

    ⚠ Anchored on declaration LINES, not on character arithmetic: an earlier
    attempt at this cut used `rindex('public function', 0, i + 5)`, whose window
    is too small for Python to return the intended match, so it silently found
    the PREVIOUS method 40 lines earlier.
    """
    import re as _re
    lines = php.splitlines(keepends=True)
    decl = _re.compile(r'^\s*(?:public|protected|private)?\s*function\s+(\w+)\s*\(')
    hits = [(n, m.group(1)) for n, l in enumerate(lines) for m in [decl.match(l)] if m]
    idx = [n for n, nm in hits if nm == name]
    assert len(idx) == 1, '%s is declared %d times' % (name, len(idx))
    start = idx[0]
    after = [n for n, _ in hits if n > start]
    end = after[0] if after else len(lines)
    return ''.join(lines[start:end])


def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef)) and n.name == name:
            return n
    raise AssertionError(f'{name} not found — has it been renamed?')


def _params(fn):
    a = fn.args
    return [p.arg for p in (a.posonlyargs + a.args + a.kwonlyargs)]


def _rendered_copy(src):
    """Blade source with every COMMENT removed — Blade's and PHP's.

    ⚠⚠ THIS REPO HAS NOW PAID ELEVEN TIMES FOR A GUARD FIRING ON ITS OWN PROSE,
    and both of the newest two are in this change. The comment that replaced the
    volunteer copy QUOTES the sentence it removed, so a raw scan for that
    sentence finds it in the very edit that deleted it. And the typed-figure
    guard below fired on a `//` comment INSIDE an `@php` block that cites the
    measurement justifying the rule — a new organ, since `{{-- --}}` stripping
    alone does not reach it.

    ⚠ PHP COMMENTS ONLY, NOT THE WHOLE `@php` BLOCK. Blade assigns rendered copy
    in `@php` (this page builds its "N projects match" sentence there), so
    discarding the block would blind the copy guard to the one place copy is
    actually composed — a scanner blind to the region the defect lives in is the
    zero-files scanner wearing a different hat.
    """
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)          # {{-- Blade --}}
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)                  # /* PHP or CSS */
    src = re.sub(r'^[ \t]*//.*$', '', src, flags=re.M)               # // PHP line comment
    return src


# ---------------------------------------------------------------- the map seam

def test_the_map_is_actually_handed_every_membership_filter_the_list_takes():
    """⚠⚠ THE SIGNATURE IS NOT THE BEHAVIOUR, and that distinction is the whole
    point of this guard.

    A parameter can be declared on `capital_geojson` and then dropped on the
    floor — which is exactly what happened: `has_location` and `has_borough`
    were passed to `_list_filters` as the literal `None` while the endpoint's
    own docstring explained why that was fine. A guard comparing the two
    signatures would have gone green on the broken version the day it shipped.

    So this resolves `_list_filters`'s parameter ORDER from its own def, walks
    every call to it inside `capital_geojson`, and asserts the argument in each
    filter position is the FORWARDED NAME — never a constant.
    """
    tree = ast.parse(_read(ROUTER))
    lst = _fn(tree, 'capital_projects')
    geo = _fn(tree, 'capital_geojson')
    filt_params = _params(_fn(tree, '_list_filters'))

    membership = [p for p in _params(lst) if p not in _SLICE_ONLY]
    missing = [p for p in membership if p not in _params(geo)]
    assert not missing, (
        f'the list filters on {missing} and the map cannot — so filtering the '
        f'table would move the table and not the map')

    calls = [n for n in ast.walk(geo)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == '_list_filters']
    assert len(calls) >= 2, (
        'the map builds two filter sets — the features and the coverage '
        'denominator — and both must be filtered the same way')

    for call in calls:
        bound = {}
        for i, arg in enumerate(call.args):
            if i < len(filt_params):
                bound[filt_params[i]] = arg
        for kw in call.keywords:
            if kw.arg:
                bound[kw.arg] = kw.value
        for name in membership:
            if name not in filt_params:
                continue
            passed = bound.get(name)
            assert passed is not None, (
                f'`{name}` is never passed to _list_filters on the map path')
            assert isinstance(passed, ast.Name) and passed.id == name, (
                f'the map declares `{name}` and then passes '
                f'`{ast.unparse(passed)}` to _list_filters — a filter that is '
                f'accepted and discarded is worse than one that is refused, '
                f'because the map silently answers a different question')


def test_the_coverage_denominator_uses_the_same_filters_as_the_features():
    """The legend's "N of M" is the map's own claim about how complete it is. If
    M is computed with a different filter set than N, the sentence is arithmetic
    over two populations — which is how "of 17,024" came to sit under a table
    reading 4,560."""
    tree = ast.parse(_read(ROUTER))
    geo = _fn(tree, 'capital_geojson')
    filt_params = _params(_fn(tree, '_list_filters'))
    calls = [n for n in ast.walk(geo)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == '_list_filters']

    def sig(call):
        bound = {}
        for i, a in enumerate(call.args):
            if i < len(filt_params):
                bound[filt_params[i]] = ast.unparse(a)
        for kw in call.keywords:
            if kw.arg:
                bound[kw.arg] = ast.unparse(kw.value)
        return bound

    first = sig(calls[0])
    for other in calls[1:]:
        assert sig(other) == first, (
            'the features and the coverage denominator are filtered '
            'differently, so the legend describes a population the map is not '
            'drawing')


# ------------------------------------------------------------ controller seam

def test_the_controller_passes_every_view_data_key_the_page_reads():
    """⚠⚠ #247, THE SAME SEAM. `ProcurementController` NAMES each view-data key,
    so a payload the API serves and the Blade reads still arrives as `null`
    unless the controller lists it — and `?? []` degrades politely. The Digital
    Services Overview shipped with no composition bar and no pipeline block that
    way, while every unit guard passed."""
    php = _read(CONTROLLER)
    action = _php_method(php, 'projects')

    passed = set(re.findall(r"'([A-Za-z_]+)'\s*=>", action))
    view = _read(VIEW)
    # Every `$var` the view reads that is not assigned inside the view itself.
    read = set(re.findall(r'\$([a-zA-Z][a-zA-Z0-9_]*)', view))
    assigned = set(re.findall(r'\$([a-zA-Z][a-zA-Z0-9_]*)\s*=', view))
    php_builtins = {'r', 'a', 'b', 'c', 'p', 'k', 'lbl', 'ds', 'tbl', 'v', 'this'}
    needs = {v for v in read - assigned - php_builtins if v.startswith('cap')}
    assert needs, 'the view reads no cap* view data — has it been rewritten?'

    missing = needs - passed
    assert not missing, (
        f'the page reads {sorted(missing)} and the controller never passes '
        f'them — they arrive as null and every figure blanks, silently')


def test_the_map_url_is_built_from_the_same_array_as_the_list_request():
    """⚠⚠ ONE FILTER STATE, BUILT ONCE. If the map URL is assembled from a second
    read of the request, the two can drift apart by a typo and nothing fails —
    which is precisely how the map and the table came to disagree in the first
    place. This asserts the geojson URL is built from `$capFilters`, and that
    `$capFilters` is what the list request was built from."""
    php = _read(CONTROLLER)
    action = _php_method(php, 'projects')

    m = re.search(r"'capGeojsonUrl'\s*=>\s*DatabookAPI::url\((.*?)\),\n", action, re.S)
    assert m, 'the page must be given a geojson URL'
    expr = m.group(1)
    assert 'http_build_query($capFilters)' in expr, (
        f'the map URL is built from `{expr.strip()}` rather than from '
        f'$capFilters — a second read of the request is a second filter state')

    lm = re.search(r'\$listQuery\s*=\s*array_merge\(\s*\$capFilters\b', action)
    assert lm, (
        'the list request must be built from $capFilters too, or "the same '
        'array" is only true of one of them')


def test_the_php_sort_whitelist_is_the_routers_sort_vocabulary():
    """`CAPITAL_SORTS` is a second copy — it has to be, since the whitelist runs
    before any API call. An unknown sort silently becomes the default at the
    endpoint, so a drifted copy offers the reader an option that does nothing and
    looks like it worked."""
    php = _read(CONTROLLER)
    m = re.search(r'const CAPITAL_SORTS\s*=\s*\[(.*?)\];', php, re.S)
    assert m, 'CAPITAL_SORTS must exist'
    php_sorts = set(re.findall(r"'([a-z_]+)'", m.group(1)))

    tree = ast.parse(_read(ROUTER))
    router_sorts = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == '_SORTS'
                and isinstance(node.value, ast.Dict)):
            router_sorts = {k.value for k in node.value.keys
                            if isinstance(k, ast.Constant)}
    assert router_sorts, '_SORTS not found in the router'
    assert php_sorts == router_sorts, (
        f'the page offers {sorted(php_sorts)} and the endpoint understands '
        f'{sorted(router_sorts)}')


def test_the_page_number_is_floored_and_cast():
    """⚠⚠ BOTH HALVES (#321). A crawler followed a live href on a disabled
    control down through page=0, -1, -2 with no floor — 453 requests carrying a
    negative page in one 10-minute window — and the raw value reached a cache
    key, so '1', 1 and '01' minted three entries for one page and a 1.2 GB
    cache."""
    php = _read(CONTROLLER)
    action = _php_method(php, 'projects')
    m = re.search(r"\$page\s*=\s*([^;]+);", action)
    assert m, 'the action must resolve $page'
    expr = ' '.join(m.group(1).split())
    assert 'max(1,' in expr.replace(' ', '').replace('max(1,', 'max(1,') or 'max(1' in expr, (
        f'$page is not floored at 1: {expr}')
    assert '(int)' in expr, (
        f'$page is not cast to int, so the raw string reaches the query: {expr}')


def test_a_disabled_pagination_control_is_never_a_link():
    """#321 again, at the markup end. The old pagination put `disabled` on the
    `<li>` and left a real href on the `<a>` inside it — a CSS class never
    stopped a crawler."""
    view = _rendered_copy(_read(VIEW))
    for m in re.finditer(r'<li class="page-item disabled">(.*?)</li>', view, re.S):
        inner = m.group(1)
        assert '<a' not in inner, (
            'a disabled pagination control still renders an anchor; it must be '
            'a <span>, because `disabled` on the <li> is decoration')
    assert 'page-item disabled' in view, (
        'no disabled pagination state at all — has the pager been removed?')


# ------------------------------------------------------------- published copy

def test_the_legend_is_the_served_sentence_and_carries_no_typed_denominator():
    """⚠⚠ ASSERT IT IS ECHOED, NOT MENTIONED — the failure mode that produced
    four of the previous session's dead guards. And a typed denominator is the
    defect this repo shipped as "the largest 20 families — 88.0% of value"
    against a computed 87.7%; here it would also go stale the moment any filter
    is applied, since the denominator depends on them."""
    view = _read(VIEW)
    assert re.search(r'\$\(\s*[\'"]#mapCoverageNote[\'"]\s*\)\s*\.text\(\s*cov'
                     r'\s*&&\s*cov\.note', view), (
        'the coverage note must be WRITTEN from the served `cov.note`, not '
        'merely referenced')

    copy = _rendered_copy(view)
    # Strip the <script> blocks: a phase colour like '#f2c45a' is code, and the
    # numbers that matter are the ones a reader sees.
    prose = re.sub(r'<script\b.*?</script>', '', copy, flags=re.S)
    for bad in re.finditer(r'\b(4,?560|17,?024|12,?929|12,?464)\b', prose):
        raise AssertionError(
            f'the page types the figure {bad.group(0)} into its copy; every '
            f'count here depends on the filters applied and must come from the '
            f'payload')


def test_no_page_still_claims_the_city_does_not_publish_project_locations():
    """The copy read "NYC's government doesn't publish the locations of capital
    projects (!?), so volunteers are using the information they do publish to
    determine where the projects are actually located". The City DOES publish
    them — Databook holds published geometry for 4,560 projects, from DCP's CPDB
    points and polygons — so the sentence told a reader the opposite of what the
    map beside it was drawing."""
    for path in COPY_VIEWS:
        copy = _rendered_copy(_read(path))
        assert 'volunteers are using' not in copy, (
            f'{os.path.basename(path)} still publishes the volunteer-locating '
            f'claim')
        assert 'Volunteer-d751814ef6374dd9b9d10c989bcfa141' not in copy, (
            f'{os.path.basename(path)} still links the volunteer sign-up')
        assert 'location_coverage' in copy, (
            f'{os.path.basename(path)} lost its location-coverage note '
            f'entirely; the honest version of that block has to replace it, not '
            f'just delete it')


def test_the_projects_index_no_longer_reads_the_retired_series():
    """The four tiles — Number of Projects / Original Cost / Current Cost /
    Amount Over Budget — were computed by `rebuild_glob_stats` over
    `capitalprojectsdollarscomp`, the OMB series NYC retired on 2023-10-26. The
    count it published was 5,128 against the spine's 17,024.

    ⚠ `Amount Over Budget` is deliberately NOT repointed anywhere: it is the
    label this section documents as carrying two definitions."""
    # ⚠⚠ STRIP COMMENTS FIRST — OWN-PROSE FIRING 21. The capital tiles moved
    # here from /procurement carrying the comment that EXPLAINS they used to
    # read `globStats` over the retired series. The code does not; the prose
    # does, and a raw scan cannot tell the difference. This repo has now paid
    # for that twenty-one times.
    import re as _re
    view = _read(VIEW)
    view = _re.sub(r'\{\{--.*?--\}\}', '', view, flags=_re.S)   # Blade comments
    view = _re.sub(r'^\s*//.*$', '', view, flags=_re.M)            # PHP line comments
    for banned in ('prj_stat', 'globStatView', 'globStats', 'GEO_JSON',
                   'Amount Over Budget'):
        assert banned not in view, (
            f'the project index still references `{banned}` — that is the '
            f'retired series')

    php = _read(CONTROLLER)
    action = _php_method(php, 'projects')
    assert "'globStats'" not in action, (
        'the controller still fetches /pipeline/globstats for this page')
    assert '/get/capitalprojects/projectsnew' not in action, (
        'the controller still requests the 13.7 MB whole-universe payload')


# ------------------------------------------------------ phase, on both sides

def test_a_phase_is_matched_case_insensitively_on_both_sides():
    """⚠⚠ MEASURED, NOT ARGUED. The spine carries `Construction Procurement`
    (317 rows) AND `Construction procurement` (6), `(On-Hold)` (26) AND
    `(On-hold)` (42). An equality test on the raw value offers a reader a phase
    and then hides part of it — the RICHMOND/STATEN ISLAND defect on a different
    column.

    ⚠ NORMALISING ONLY ONE SIDE IS WORSE THAN NORMALISING NEITHER: it drops
    every row stored in the other casing while looking careful."""
    # ⚠ The router imports asyncpg-backed modules that are absent under test,
    # so the two pure helpers are compiled OUT of the real file's AST and run —
    # never reimplemented here. A guard that reimplements the thing it guards
    # measures a different system than the one that ships.
    tree = ast.parse(_read(ROUTER))
    ns = {}
    for name in ('_norm_phase', '_phase_sql'):
        node = _fn(tree, name)
        exec(compile(ast.Module(body=[node], type_ignores=[]), ROUTER, 'exec'), ns)

    assert (ns['_norm_phase']('Construction Procurement')
            == ns['_norm_phase']('Construction procurement')), (
        'the two published casings of one phase must normalise to one value')
    assert ns['_norm_phase']('  (On-Hold) ') == ns['_norm_phase']('(On-hold)')
    # ⚠ CASE ONLY. The parentheses mark a NON-phase status ("no schedule is
    # required"), so `(Construction)` 18 is not `Construction` 825; collapsing
    # them would be a judgement about what the publisher meant.
    assert ns['_norm_phase']('(Construction)') != ns['_norm_phase']('Construction'), (
        'parenthesised statuses must stay distinct from the standard phases')

    sql = ns['_phase_sql']('p.current_phase')
    assert 'lower(' in sql and 'btrim(' in sql, (
        f'the stored column is not folded the way the input is: {sql}')

    # And the filter must actually USE it — a helper nothing calls is the
    # "declared but never runs" defect this repo keeps paying for.
    body = ast.unparse(_fn(tree, '_list_filters'))
    assert '_phase_sql()' in body, (
        'the phase filter does not go through _phase_sql, so the column is '
        'compared raw')
    assert '_norm_phase(phase)' in body, (
        'the caller\'s phase value is not normalised, so only one side is')


def test_the_builder_folds_case_when_flagging_a_standard_phase():
    """`phase_is_standard` was an exact `= ANY(...)`, so `Construction
    Procurement` (317) was flagged a phase and `Construction procurement` (6) was
    flagged "no schedule required" — the same phase, split by casing. Nothing
    published moved, because `in_construction` additionally tests
    `= 'Construction'` and there is no lowercase spelling of that one; it was a
    defect waiting for the first phase-mix chart."""
    src = _read(BUILDER)
    m = re.search(r'ELSE\s+([^\n]*?)\s*=\s*ANY\(\$1::text\[\]\)\s*END', src)
    assert m, 'the phase_is_standard expression is gone or unrecognisable'
    lhs = m.group(1)
    assert 'lower(' in lhs, (
        f'the stored phase is compared without folding case: {lhs}')

    call = re.search(r'await conn\.execute\(_sql\(has_org_id\),(.*?)\)\n', src, re.S)
    assert call, 'the builder no longer binds STANDARD_PHASES'
    assert '.lower()' in call.group(1), (
        'the Python side of the comparison is not lowercased, so folding only '
        'one side would flag every phase non-standard')


def test_a_page_past_the_end_says_so_instead_of_computing_a_range():
    """⚠⚠ ARITHMETIC ALONE PRODUCED A LIE, and only rendering the page found it.
    `?page=99999` printed **"Showing 4,999,901–17,024"** — a first row past the
    last row, over a list of 341 pages — because `(page-1)*per_page+1` is only
    meaningful where rows exist. Every unit assertion about paging was green.

    The ceiling genuinely cannot be clamped before the request (the page count is
    only known from the response), and clamping it afterwards would answer a
    different URL than the one asked for. So the page states the condition.
    """
    view = _rendered_copy(_read(VIEW))
    assert '$pastEnd' in view, 'the past-the-end condition is gone'
    # ⚠ ASSERT THE RANGE IS GATED ON IT, not merely that the variable exists —
    # a computed range beside an unused flag is the original defect with a new
    # variable in the file.
    m = re.search(r'\$firstRow\s*=\s*([^;]+);', view)
    assert m and '$hasRows' in m.group(1), (
        f'the row range is computed unconditionally: {m.group(1) if m else "?"}')
    assert re.search(r'if\s*\(\s*\$pastEnd\s*\)\s*\n?\s*\$showingPhrase\s*=', view), (
        'nothing tells the reader the page is past the end')


def test_the_unrouted_orphan_views_stay_deleted():
    """⚠⚠ THREE VIEWS WERE REACHABLE BY NO ROUTE AND STILL CARRIED THE DEFECTS
    THIS SECTION SPENT WEEKS REMOVING. Deleted 2026-09-10 with their controller
    actions (`Projects::main_a`, `Projects::projects_a`,
    `Organizations::project_a`), measured before removal:

        capitalA      297 lines, `Amount Over Budget` x1, `over_budg_am` x3
        projectsA     654 lines, `Amount Over Budget` x1, `over_budg_am` x3,
                      four `, 1000` money multipliers
        orgprojectA   983 lines
        main_a / projects_a: nine `pstats-*` hydration URLs each

    ⚠ THE POINT IS NOT TIDINESS. `Amount Over Budget` is the label this section
    documents as carrying two definitions, and `, 1000` is the multiplier that
    renders a spine figure a thousand times too large. Routing any of these
    pages would have republished both. Dead code that cannot be reached is
    harmless; dead code carrying a retired defect is not.

    ⚠ The recorded reason for LEAVING them was "a partial edit to dead code is a
    worse state than deletion or nothing" — which makes deletion the
    resolution, not a preference.
    """
    import re as _re
    views = os.path.join(ROOT, 'app', 'resources', 'views')
    for fn in DELETED_ORPHAN_VIEWS:
        assert not os.path.exists(os.path.join(views, fn)), (
            '%s is back. It is reachable by no route and carries retired-series '
            'markup, so routing it would republish defects this section '
            'removed.' % fn)
    # ⚠ And their actions must not come back either — a view can be recreated
    # from a controller as easily as the other way round.
    ctrl = _read(CONTROLLER)
    orgs = _read(os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers',
                              'Organizations.php'))
    for src, name in ((ctrl, 'main_a'), (ctrl, 'projects_a'),
                      (orgs, 'project_a')):
        assert not _re.search(r'function\s+%s\s*\(' % name, src), (
            'the orphan action `%s` is back' % name)
    # ⚠ ANTI-VACUUM: the live siblings share the `_a` suffix, so a guard matching
    # too loosely would pass by finding nothing at all.
    assert _re.search(r'function\s+budgetLine_a\s*\(', ctrl), (
        'the live `_a` siblings are gone too — this guard is matching the wrong '
        'thing')
