"""The district profile's capital tab reads the spine, not the retired series.

⚠⚠ THE LAST SURFACE OFF `capitalprojectsdollarscomp`. Like the org tab it could
not be repointed by changing a table name: it fetched
`/get/districts/{type}/{id}/capitalprojects`, which joins the retired series to
a `capitalprojects_{type}_idx` on `PROJECT_ID`. The spine's crosswalk is
`capital_project_districts`, keyed on `(agency_key, fms_id)` — the grain a bare
FMS id does not have.

Cross-checked rather than asserted: `/get/capital/projects/by-district/cc/38`
returns **103** rows, `/get/capital/stats/cc/38` reports **103** projects, and
the rendered table reads "Showing 1 to 10 of 103 entries".
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
CONTRACT = os.path.join(ROOT, 'app', 'app', 'Custom', 'DistDatasets.php')
CONTROLLER = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Districts.php')
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'distprojectsection.blade.php')
ROUTER = os.path.join(ROOT, 'api', 'routers', 'capital.py')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _code_only(text):
    """⚠ Strip comments — the contract and the view both EXPLAIN that they were
    repointed off the retired series and that the old cells multiplied by 1000.
    A raw scan fires on the prose documenting the fix (own-prose firings in this
    repo stand at 22)."""
    text = re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'^\s*//.*$', '', text, flags=re.M)


def _projects_contract(text):
    code = _code_only(text)
    i = code.index("'projects' => [")
    j = code.index('[', i)
    depth, k = 0, j
    while k < len(code):
        if code[k] == '[':
            depth += 1
        elif code[k] == ']':
            depth -= 1
            if depth == 0:
                return code[j:k + 1]
        k += 1
    raise AssertionError('unbalanced projects contract')


def test_the_district_capital_tab_reads_the_spine():
    body = _projects_contract(_read(CONTRACT))
    assert "'table' => 'capital_projects'" in body
    assert 'capitalprojectsdollarscomp' not in body


def test_no_money_cell_multiplies_by_a_thousand():
    """⚠⚠ INVARIANT 2. The retired series is denominated in THOUSANDS and the
    spine in USD; carrying a `, 1000` over renders $145M as $145B."""
    body = _projects_contract(_read(CONTRACT))
    offenders = re.findall(r'to(?:Fin|FinShortK)\([^)]*,\s*1000\s*\)', body)
    assert not offenders, 'spine money must not be scaled: %s' % offenders


def test_amount_over_budget_is_not_reproduced():
    """⚠⚠ THE ONE LABEL THAT MUST NOT BE REPOINTED. `Amount Over Budget` carries
    TWO definitions — every row's budget difference globally, but only the
    NEGATIVE ones per district — so repointing it preserves the defect under new
    data. The rebuild drops it."""
    view = _code_only(_read(VIEW))
    for dead in ('Amount Over Budget', 'over_budg_am', 'pstats-orig_cost'):
        assert dead not in view, (
            'the district capital tab still renders a retired-series tile: %s' % dead)


def test_the_controller_points_at_the_district_scoped_spine_endpoint():
    ctrl = _code_only(_read(CONTROLLER))
    assert '/get/capital/projects/by-district/' in ctrl, (
        'the district tab no longer fetches the spine endpoint')
    assert '/capitalprojects"' not in ctrl, (
        'it is back on the retired-series district endpoint')


def test_the_endpoint_joins_the_spine_crosswalk():
    """⚠ Reads the AST with the docstring dropped — the endpoint's own prose
    names the retired series, which is own-prose firing 22's exact shape."""
    import ast
    fn = next(n for n in ast.walk(ast.parse(_read(ROUTER)))
              if isinstance(n, ast.AsyncFunctionDef)
              and n.name == 'capital_projects_by_district')
    stmts = list(fn.body)
    if (stmts and isinstance(stmts[0], ast.Expr)
            and isinstance(stmts[0].value, ast.Constant)
            and isinstance(stmts[0].value.value, str)):
        stmts = stmts[1:]
    body = '\n'.join(ast.unparse(st) for st in stmts)
    assert 'capital_project_districts' in body, 'not joined to the spine crosswalk'
    assert 'agency_key' in body and 'fms_id' in body, (
        'the join must be on (agency_key, fms_id) — an FMS id alone is carried '
        'by more than one agency on 1,160 ids')
    assert 'capitalprojectsdollarscomp' not in body


def test_the_publication_date_filter_is_gated():
    """⚠⚠ Column 1 was `Publication Date` under the retired contract and is
    `Agency` on the spine. Ungated, the control builds a dropdown of agency
    names, selects the last, and silently filters the table — exactly what read
    "Showing 1 to 1 of 1 (filtered from 2,798)" on the ORG tab."""
    view = _read(VIEW)
    for anchor in ('columns([1]).every', "$('#filter-1 option:last-child')"):
        i = view.index(anchor)
        preceding = view[:i]
        assert preceding.rindex("@if ($details['pubDateFilter'] ?? false)") > \
            (preceding.rindex('@endif') if '@endif' in preceding else -1), (
            '`%s` is not inside the pubDateFilter gate' % anchor)


# ── the district URL shape ──────────────────────────────────────────────────

ROUTES = os.path.join(ROOT, 'app', 'routes', 'web.php')


def test_the_district_id_and_slug_are_separated_by_an_underscore():
    """⚠⚠ THE DEFECT THIS PREVENTS, AND IT SILENTLY TRUNCATED 40% OF NTA NAMES.

    `{id}` compiles to a LAZY match, so on `/d/nta-Tribeca-Civic Center-district`
    the controller received **`Tribeca`** — measured off the page's own permalink,
    which rendered `/d/nta-Tribeca-dslug/projects`. **103 of the 255 NTA names
    carry a hyphen** (Tribeca-Civic Center, Downtown Brooklyn-DUMBO-Boerum Hill),
    so those districts resolved to a name that does not exist and rendered empty.

    ⚠ An underscore cannot appear in an NTA name or a slug, so the split is
    unambiguous BY CONSTRUCTION rather than by luck about the data. It is the
    same fix `/p/{prjId}_{prjslug}` already uses, for the same reason — project
    ids contain hyphens too.
    """
    routes = re.sub(r'^\s*//.*$', '', _read(ROUTES), flags=re.M)
    m = re.search(r"Route::get\('/d/\{type\}-\{id\}(.)\{dslug\}/\{section\}'", routes)
    assert m, 'the canonical district section route is gone'
    assert m.group(1) == '_', (
        "the district id/slug separator is %r — with '-' a hyphenated NTA name "
        "is truncated at its first hyphen" % m.group(1))


def test_the_legacy_hyphen_route_is_numeric_only():
    """⚠ The legacy shape is kept so old links resolve, but constrained to
    NUMERIC ids. cd/cc/sd are numbers and were never ambiguous; leaving `nta` on
    that pattern would keep silently truncating the names this fixes."""
    routes = re.sub(r'^\s*//.*$', '', _read(ROUTES), flags=re.M)
    i = routes.index("Route::get('/d/{type}-{id}-{dslug}/{section}'")
    tail = routes[i:i + 400]
    assert "'id' => '[0-9]+'" in tail, (
        'the legacy hyphen route is not constrained to numeric ids, so it will '
        'still swallow hyphenated NTA names')


def test_the_district_id_is_url_encoded_into_the_api_calls():
    """⚠⚠ CAUGHT BY MEASURING, NOT BY READING. An NTA id is a NAME with spaces,
    and `"/get/capital/stats/{$type}/{$id}"` built a malformed URL — the tab
    rendered an em dash while the endpoint itself returned 90 projects for
    `nta/Prospect Park`. Numeric districts hid it completely."""
    ctrl = _code_only(_read(CONTROLLER))
    for call in ('/get/capital/projects/by-district/', '/get/capital/stats/'):
        i = ctrl.index(call)
        line = ctrl[i:ctrl.index('\n', i)]
        assert 'rawurlencode($id)' in line, (
            'district id is interpolated raw into %s — a name with a space '
            'builds a malformed URL: %s' % (call, line.strip()))


def test_the_sources_panel_names_every_publication_the_spine_is_built_from():
    """⚠⚠ IT NAMED ONE OF FOUR, AND THE ONE IT NAMED WAS THE RETIRED ONE.

    The district capital tab reads `capital_projects`, which
    `build_capital_projects.py` builds from FOUR publications —
    `capitalprojectslist` (CPDB), `capprojectsbudgetsandschedule` (the
    Dashboard), `capitalprojectscommitments` and `capitalprojectsdollarscomp`
    (the 2023 series, for scope text, borough and the 2023 budgets). The panel
    listed only the last of those, whose row is BLANK — "not tracked", no
    description, no date — because it is never ingested. Measured on the
    rendered page 2026-09-10: "normalized data from 5 datasets containing
    227,395 records", with the capital row contributing nothing. So the sources
    panel for a tab whose every figure comes from the spine named a single 2023
    publication and no other.

    ⚠ THE RETIRED SERIES STAYS. The spine really does read it, so naming it is
    accurate; naming it ALONE is what was wrong. After: 7 datasets / 337,568
    records, verified on `cc`, `cd` and `nta`.

    ⚠ `/projects` already got this right (6 datasets / 475,136 records), which
    is how the district panel's omission was visible at all — the same figure
    computed two ways on two pages, which is this section's oldest tell.
    """
    ctrl = _code_only(_read(CONTROLLER))
    contract = _code_only(_read(CONTRACT))
    spine_sources = ('capitalprojectslist', 'capprojectsbudgetsandschedule',
                     'capitalprojectscommitments')
    # Both district handlers build their own dataset list; a fix applied to one
    # and not the other is exactly how the scope note shipped on one page only.
    lists = re.findall(r"\[\s*'nyccouncildiscretionaryfunding'.*?\]", ctrl, flags=re.S)
    assert len(lists) == 2, (
        'expected both district handlers to name their dataset list, found %d'
        % len(lists))
    for i, lst in enumerate(lists):
        for src in spine_sources:
            assert src in lst, (
                "district dataset list %d does not name `%s`, one of the four "
                'publications the spine is built from — the panel then credits '
                'the tab\'s figures to the 2023 series alone' % (i + 1, src))
    # And the accordion can only render a row for a table its map knows.
    for src in spine_sources:
        assert "'%s' => [" % src in contract, (
            '`%s` has no entry in DistDatasets, so naming it in the list '
            'renders a fallback row with no name or section' % src)
