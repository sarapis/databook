"""Every spine-backed capital map draws from a SERVED, SCOPED geojson.

⚠⚠ FOUR SURFACES DREW ZERO FEATURES AND NOT ONE LOOKED BROKEN. `budgetLineA`,
`categoryA` and `orgprojectsection` each held a byte-identical `drawProjects`
that built its features from `r['GEO_JSON']` on its own DataTable. Every one of
those tables was migrated onto the capital spine, and the spine carries no
`GEO_JSON` column at all — so each map wrote an empty `route` source. Measured
on the rendered pages 2026-09-10 from `map.getSource('route')._data`:

    /o/{id}/projects  (org capital tab)          table 2,798   map 0
    /projects/categories/neighborhood-parks-...  table 1,036   map 0
    /projects/categories/routine-reconstruction  table   447   map 0
    /projects/budget-lines/EP 0007               table    60   map 0

Container sized, style loaded, console empty, table correct. This is the
five-surfaces finding of 2026-09-09 in a fourth organ: a tab is not migrated
when its TABLE is repointed.

⚠ THE OWNER IS `capMap` IN `script.js`. Three copies of a race-sensitive block
is what this repo keeps paying for — and the race is real: the `route` source is
added inside mapbox's `load` handler while the fetch fires independently, so
when the data wins `getSource('route')` is undefined and `setData` throws inside
the AJAX success handler. The old pages papered over it with
`setTimeout(..., 3000)`, which is a guess about the style load rather than a
synchronisation with it.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
VIEWS = os.path.join(ROOT, 'app', 'resources', 'views')
SCRIPT = os.path.join(ROOT, 'app', 'public', 'js', 'script.js')
PROJECTS_CTRL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers',
                             'Projects.php')
ORGS_CTRL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers',
                         'Organizations.php')

# The views whose project table is the capital spine AND which render a map.
SPINE_MAP_VIEWS = ['budgetLineA.blade.php', 'categoryA.blade.php',
                   'orgprojectsection.blade.php']


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _code_only(text):
    """⚠ Blade, block and line comments stripped. Every assertion below searches
    for a string the comments recording this fix quote — `GEO_JSON`,
    `columns([1])`, `setTimeout`, `capital/geojson`. Own-prose firings in this
    repo stand at 26, three of them in the session that wrote this file, and one
    of those was found only by mutation."""
    text = re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'^\s*//.*$', '', text, flags=re.M)


def _php_method(text, name):
    code = _code_only(text)
    i = code.index('function %s(' % name)
    return code[i:code.index('public function ', i + 10)]


def test_there_is_exactly_one_owner_of_the_capital_maps_features():
    """⚠ The helper must exist, and no view may reimplement it."""
    js = _read(SCRIPT)
    assert 'var capMap = (function ()' in js, (
        'the shared capital-map owner is gone from script.js; the three views '
        'that use it will each fall back to their own copy')
    for fn in ('init', 'ready', 'draw', 'markLocated', 'isLocated', 'zoomTo'):
        assert re.search(r'\b%s:\s*%s\b' % (fn, fn), js), (
            'capMap no longer exposes %s(), which at least one view calls' % fn)


def test_no_spine_backed_map_builds_its_features_from_the_table():
    """⚠⚠ THE DEFECT ITSELF. A view reading `GEO_JSON` while its table is the
    spine draws an empty map with no error of any kind."""
    for name in SPINE_MAP_VIEWS:
        view = _code_only(_read(os.path.join(VIEWS, name)))
        assert 'GEO_JSON' not in view, (
            '%s reads GEO_JSON in live code again — the spine does not serve '
            'that column, so the map draws nothing and says nothing: %s'
            % (name, re.findall(r'.{0,50}GEO_JSON.{0,20}', view)[:2]))
        assert 'projectsMapDrawFeatures(' not in view, (
            '%s draws features itself instead of going through capMap, so the '
            'race and the coverage note have a second implementation' % name)
        assert 'capMap.draw(' in view, (
            '%s no longer draws its map through the one owner' % name)


def test_every_spine_backed_map_is_handed_its_scope_by_the_controller():
    """⚠⚠ THE MAP AND THE TABLE MUST BE ONE QUESTION. `capMap.init('')` is the
    silent failure mode — the helper takes `url || null` and then never fetches,
    so a controller that forgets the key produces the SAME empty map the defect
    produced. That happened while writing this: the org tab shipped
    `capMap.init('')` for one build because a script aborted before its
    controller edit, and the page still returned 200 with a clean console.
    """
    for name in SPINE_MAP_VIEWS:
        view = _code_only(_read(os.path.join(VIEWS, name)))
        assert 'capMap.init(' in view, (
            '%s never hands capMap a scope, so its map fetches nothing' % name)
        call = next(l for l in view.splitlines() if 'capMap.init(' in l)
        assert '$capGeojsonUrl' in call, (
            '%s builds its own map URL instead of taking the one the controller '
            'built from the same scope as the list: %s' % (name, call.strip()))

    # ⚠ And the controllers must actually pass it, scoped. This is the #247
    # seam: the view reading a key proves nothing about the controller sending
    # one, and `?? ''` degrades politely into exactly the original defect.
    for path, method, scope in (
            (PROJECTS_CTRL, 'budgetLine_a', 'budget_line'),
            (PROJECTS_CTRL, 'category_a', 'ten_year_category'),
            (ORGS_CTRL, 'orgProjectSection', 'org')):
        body = _php_method(_read(path), method)
        # ⚠⚠ THE EXACT ARRAY KEY, NOT A SUBSTRING. `'capGeojsonUrl' in body`
        # matched a mutation that renamed the key to `capGeojsonUrlX` — the view
        # would have received nothing and called `capMap.init('')`, which fetches
        # nothing and reproduces the original empty map. "A prefix match on a
        # name is not a match on the name", third time in this repo.
        assert re.search(r"'capGeojsonUrl'\s*=>", body), (
            '%s no longer passes a `capGeojsonUrl` key, so its map has no '
            'source — and `capMap.init(\'\')` fails SILENTLY' % method)
        line = next(l for l in body.splitlines()
                    if re.search(r"'capGeojsonUrl'\s*=>", l))
        assert '/get/capital/geojson' in line, (
            '%s does not point its map at the geojson endpoint: %s'
            % (method, line.strip()))
        # ⚠ Scoped to the LINE, not a window: reading a few hundred characters
        # from the key reaches other URLs in the same array, and a window-based
        # form of this assertion was measured to stay GREEN when the scope was
        # stripped off the budget-line page's map URL.
        assert scope in line, (
            '%s does not scope its map to %s, so the map answers a different '
            'question from the table beside it: %s'
            % (method, scope, line.strip()))


def test_no_spine_backed_view_indexes_a_control_on_column_one():
    """⚠⚠ INVARIANT 10, AND IT WAS LIVE ON THE CATEGORY PAGES. `columns([1])`
    with an `option:last-child` auto-select meant `Publication Date` under the
    retired contract, whose contract declares a details expander so `get()`
    prepends a column. On the `spine` contract column 1 is `Agency` — so the
    control built a dropdown of agency names and picked one.

    Measured on the rendered pages 2026-09-10:

        Neighborhood Parks, Playgrounds and Ballfields
            "Showing 1 to 3 of 3 (filtered from 1,036)"   — DOT
        Large, Major and Regional Park Reconstruction
            "Showing 1 to 1 of 1 (filtered from 367)"     — NYPD
        Routine Reconstruction
            "Showing 1 to 10 of 409 (filtered from 447)"  — H+H

    A PARKS category page showing one project, and that project the Police
    Department's. Payload, headers and rows all correct.

    ⚠ THE AUTO-SELECT IS HALF THE DEFECT AND MUST BE GATED WITH THE CONTROL.
    `#filter-1` is also the id the general filter loop gives column 1, so gating
    the date block alone leaves the agency dropdown being auto-picked.
    """
    for name in SPINE_MAP_VIEWS:
        view = _code_only(_read(os.path.join(VIEWS, name)))
        assert 'columns([1])' not in view, (
            '%s indexes a control on column 1 unconditionally; on the spine '
            'contract that column is not a publication date' % name)
        stray = re.findall(r"\$\('#filter-1 option:last-child'\)", view)
        assert not stray, (
            '%s auto-selects the last option of #filter-1 — which the general '
            'filter loop gives to column 1 — so the table is filtered to one '
            'arbitrary value of whatever that column happens to be' % name)


def test_the_asset_category_and_the_ten_year_category_stay_two_filters():
    """⚠⚠ TWO THINGS CALLED "CATEGORY" IS THE AMBIGUITY THIS REPO RETIRED ONCE.
    `p.type_category` is CPDB's coarse 3-value asset class; `p.ten_year_category`
    is the 138-value Ten-Year Strategy taxonomy the category PAGES are keyed on.
    Overlap between the two vocabularies is 5, every one a coincidence, and
    conflating them is what produced two different "Amount Over Budget" figures
    — which is why `/get/capital/stats/category/...` now 400s and demands
    `asset_category` or `ten_year_category` by name.
    """
    import ast
    src = _read(os.path.join(ROOT, 'api', 'routers', 'capital.py'))
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
              and n.name == '_list_filters')
    params = [a.arg for a in fn.args.args] + [a.arg for a in fn.args.kwonlyargs]
    assert 'category' in params and 'ten_year_category' in params, (
        'the two category dimensions are no longer separate parameters on the '
        'one filter owner: %s' % params)
    # ⚠⚠ READ THE BRANCH THAT USES THE PARAMETER, NOT THE WORD. A first form of
    # this assertion searched the unparsed body for `p.ten_year_category`, and a
    # mutation to `if False and ten_year_category:` left that string present
    # inside the now-dead branch — the guard passed while the filter was
    # switched off. This repo's third instance of "a WORD in a function body,
    # not the loop that uses it".
    def _branch_for(param):
        for node in ast.walk(fn):
            if (isinstance(node, ast.If) and isinstance(node.test, ast.Name)
                    and node.test.id == param):
                return '\n'.join(ast.unparse(st) for st in node.body)
        return None

    cat = _branch_for('category')
    tyc = _branch_for('ten_year_category')
    assert cat is not None, (
        '`category` no longer gates its own filter on a bare truth test, so '
        'this guard cannot tell whether it still filters anything')
    assert tyc is not None, (
        '`ten_year_category` no longer gates its own filter on a bare truth '
        'test — it may be present in the source and never applied')
    assert 'p.type_category = $?' in cat, (
        '`category` no longer filters the asset class: %s' % cat)
    assert 'p.ten_year_category' in tyc, (
        '`ten_year_category` no longer filters the Ten-Year taxonomy: %s' % tyc)
    assert 'p.ten_year_category' not in cat, (
        'the asset-class filter now reads the Ten-Year column — the two '
        'dimensions have been conflated, which is what produced two different '
        '"Amount Over Budget" figures')
    # ⚠ And the Ten-Year side must go through the ONE slug rule. 12 of 138
    # categories carry a comma, so `REPLACE(cat,' ','-')` never matched
    # Laravel's slug for those and the old endpoints fell through to a loose
    # `ILIKE '%…%'` — worse than missing, since `sewers` also matches
    # `COMBINED SEWERS AND WATER MAINS`.
    assert '_SLUG_SQL.format(col=' in tyc, (
        'the ten-year category is no longer slugged through the one rule, so '
        'a category whose name carries a comma cannot match its own URL: %s'
        % tyc)


def test_the_category_tiles_have_a_caller_outside_every_gate():
    """⚠⚠ I BROKE THIS IN THE SAME CHANGE THAT FIXED THE FILTER, AND IT IS THE
    ORG TAB'S DEFECT EXACTLY. `categoryA`'s five spine tiles are hydrated by
    `loadFinStat()`, and its ONLY caller lived inside the publication-date
    block. Gating that block — correct on its own terms — left all five tiles
    rendering `&nbsp;` with zero requests and zero JS errors, which is precisely
    what the org capital tab did for weeks with eight tiles.

    "When a contract changes, ask what CALLED the code the old contract fed, not
    just what read it."

    ⚠ Caught by `scripts/headless/verify_retired_sweep.py`, which counts blank
    `prj_stat` cells — 5 of 5 blank on
    `/projects/categories/routine-reconstruction`. Nothing else saw it: the
    table was right, the map was right, the payload was right.

    ⚠ AND THE FILTER IT REPLACED WAS PUBLISHING FIGURES, NOT JUST HIDING ROWS.
    `loadFinStat()` sums the rows matching the table's CURRENT SEARCH, so with
    an arbitrary agency auto-selected the tiles were that agency's totals under
    a category heading. Measured on the rendered pages 2026-09-10 by
    reproducing the old control exactly (tags stripped, deduped, sorted, last):

        Neighborhood Parks, Playgrounds and Ballfields
            published  3 projects · $1.53M planned · $0 spent   (DOT)
            actual     1,036      · $3.88B        · $1.29B
        Large, Major and Regional Park Reconstruction
            published  1 project  · $110K         · $0          (NYPD)
            actual     367        · $1.07B        · $1.44B
        Routine Reconstruction
            published  409        · $2.71B        · $1.18B      (H+H)
            actual     447        · $2.83B        · $1.28B

    A PARKS category page published $110K of planned commitments where the City
    plans $1.07B, and attributed it to the Police Department.
    """
    view = _code_only(_read(os.path.join(VIEWS, 'categoryA.blade.php')))
    assert 'function loadFinStat(' in view, (
        'categoryA no longer hydrates its tiles at all')
    calls = [i for i in range(len(view))
             if view.startswith('loadFinStat()', i)]
    # Drop the definition itself from consideration.
    calls = [i for i in calls if not view[:i].rstrip().endswith('function')]
    assert calls, 'nothing calls loadFinStat(), so the five tiles stay blank'
    # ⚠ At least one caller must sit OUTSIDE every Blade conditional. A caller
    # that only runs when a contract declares a publication-date column is the
    # defect, not the fix.
    ungated = []
    for i in calls:
        before = view[:i]
        opens = before.count('@if')
        closes = before.count('@endif')
        if opens == closes:
            ungated.append(i)
    assert ungated, (
        'every caller of loadFinStat() sits inside a Blade conditional, so on a '
        'contract that turns those off the five tiles render blank — a blank is '
        'not a zero and not an error, it is a fourth thing that says nothing')
