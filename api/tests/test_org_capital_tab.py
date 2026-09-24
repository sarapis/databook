"""The org profile's capital tab reads the spine, not the retired series.

⚠⚠ THIS WAS THE LAST SURFACE ON `capitalprojectsdollarscomp`, the series NYC
retired 2023-10-26. It could not simply be repointed: the tab hydrated from the
GENERIC `/get/orgs/section/{id}/{tbl}` endpoint, which hardcodes the quoted
`"wegov-org-id"` column — the spine's is `wegov_org_id` — so it needed an
org-scoped spine endpoint of its own.

⚠ MEASURED BEFORE AND AFTER, because a repoint that loses agencies is a
regression dressed as a migration: the spine resolves **27** distinct orgs
against the retired series' **25**, and exactly ONE org loses rows —
**Metropolitan Transportation Authority** (`170020045`, 14 rows). A State
authority absent from a CITY capital spine is arguably correct. NYCHA reads 0
on BOTH series, so its empty tab is not a regression either.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
CONTRACT = os.path.join(ROOT, 'app', 'app', 'Custom', 'OrgsDatasets.php')
CONTROLLER = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Organizations.php')
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'orgprojectsection.blade.php')
ROUTER = os.path.join(ROOT, 'api', 'routers', 'capital.py')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _php_code_only(text):
    """⚠ Strip comments. The contract's own comment EXPLAINS that it was
    repointed off `capitalprojectsdollarscomp` and that the old cells multiplied
    by 1000 — a raw scan fires on the prose documenting the fix. Own-prose
    firings in this repo now stand at 23.

    ⚠⚠ BLADE COMMENTS TOO, and that is not optional here. The view's own
    `{{-- --}}` block now explains that `Amount Over Budget` is deliberately
    NOT reproduced and that the tiles used to hydrate from `pstats-*`, so it
    contains every string the guards below search for. Verified by running each
    of them against the unmutated file, which is the check that catches an
    own-prose firing before it is mistaken for a real defect."""
    text = re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'^\s*//.*$', '', text, flags=re.M)


def _projects_contract(text):
    """The `projects` entry of the OrgsDatasets contract map."""
    code = _php_code_only(text)
    i = code.index("'projects' => [")
    # walk balanced brackets from the opening [
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


def test_the_org_capital_tab_reads_the_spine():
    body = _projects_contract(_read(CONTRACT))
    assert "'table' => 'capital_projects'" in body, (
        'the org capital tab is not reading the spine')
    assert 'capitalprojectsdollarscomp' not in body, (
        'the org capital tab still names the retired series')


def test_no_money_cell_multiplies_by_a_thousand():
    """⚠⚠ INVARIANT 2, AND THE REASON THIS IS A NEW CONTRACT RATHER THAN AN
    EDITED TABLE NAME. `capitalprojectsdollarscomp` is denominated in THOUSANDS
    and every money cell of the old contract passed `, 1000`. The spine is USD,
    so carrying one over renders $652.6M as $652.6B — plausible, and invisible
    to a row count or a status code."""
    body = _projects_contract(_read(CONTRACT))
    offenders = re.findall(r'to(?:Fin|FinShortK)\([^)]*,\s*1000\s*\)', body)
    assert not offenders, (
        'the spine is USD, not thousands — these cells would render $652.6M as '
        '$652.6B:\n  ' + '\n  '.join(offenders))


def test_the_controller_points_at_the_org_scoped_spine_endpoint():
    """⚠ The generic `/get/orgs/section/{id}/{tbl}` CANNOT serve the spine: it
    hardcodes the quoted `"wegov-org-id"` column and the spine's is
    `wegov_org_id`. Pointing back at it would return an error the DataTable
    renders as an empty table — a silent regression."""
    ctrl = _php_code_only(_read(CONTROLLER))
    i = ctrl.index('function orgProjectSection')
    body = ctrl[i:ctrl.index('public function ', i + 10)]
    assert '/get/capital/projects/by-org/' in body, (
        'orgProjectSection no longer fetches the org-scoped spine endpoint')
    assert '/get/orgs/section/' not in body, (
        'it is back on the generic org-section endpoint, which cannot serve '
        'the spine')


def test_the_endpoint_filters_on_the_spine_org_column():
    """⚠⚠ READS THE CODE, NOT THE DOCSTRING — OWN-PROSE FIRING 22, caught on the
    unmutated file. The endpoint's own docstring says it REPLACES
    `capitalprojectsdollarscomp`, so a raw scan of the function text fires on the
    sentence documenting the fix. `ast.unparse` includes the docstring, so it is
    dropped explicitly rather than assumed away."""
    import ast
    tree = ast.parse(_read(ROUTER))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef)
              and n.name == 'capital_projects_by_org')
    stmts = list(fn.body)
    if (stmts and isinstance(stmts[0], ast.Expr)
            and isinstance(stmts[0].value, ast.Constant)
            and isinstance(stmts[0].value.value, str)):
        stmts = stmts[1:]                      # drop the docstring
    body = '\n'.join(ast.unparse(st) for st in stmts)
    assert 'FROM capital_projects' in body
    assert 'wegov_org_id' in body, 'the endpoint does not scope to the org'
    assert 'capitalprojectsdollarscomp' not in body, (
        'the org-scoped endpoint reads the retired series')


def test_the_publication_date_filter_is_gated():
    """⚠⚠ THE DEFECT THIS PREVENTS, AND IT WAS LIVE FOR ONE BUILD. The pub-date
    control hardcodes `columns([1])` and then auto-selects that column's LAST
    option. Under the retired contract — 9 headers plus a details expander —
    column 1 was `Publication Date`. The spine has 8 headers and no expander, so
    column 1 is `Name`: it built a dropdown of 2,798 project names, picked the
    last, and the table read "Showing 1 to 1 of 1 (filtered from 2,798)".

    ⭐ The payload, the headers and the rows were all CORRECT. Only the visible
    count was wrong, which is why this needed the rendered table rather than the
    response — the same lesson this section keeps paying for.
    """
    view = _read(VIEW)
    # ⚠⚠ RE-EXPRESSED 2026-09-10 AND STRICTLY STRONGER, not relaxed. The gate was
    # keyed `pubDateFilter` while `orgSection` — the other consumer of
    # OrgsDatasets — reads `pubdate_filter`, and the column and the auto-selected
    # dropdown were HARDCODED inside the gate. So a contract could legitimately
    # turn the control on and still point it at the wrong column: the gate said
    # "there is a publication-date filter" without saying WHERE it is. Both now
    # come from the contract, one key, the same mechanism as every other view.
    #
    # ⚠ Behaviourally a no-op today — no OrgsDatasets contract declares the key
    # for this tab, so the control is off either way, which is the point: the
    # spine has no per-row publication date.
    assert 'columns([1])' not in _php_code_only(view), (
        'the pub-date control indexes column 1 unconditionally again; on the '
        'spine contract column 1 is Name, and it built a dropdown of 2,798 '
        'project names, picked the last, and the table read "Showing 1 to 1 of '
        '1 (filtered from 2,798)"')
    assert "$('#filter-1 option:last-child')" not in _php_code_only(view), (
        "the auto-select targets #filter-1 by hand again — which is also the id "
        'the GENERAL filter loop gives column 1, so it can pick a value out of '
        'an entirely different dropdown')
    for anchor in ("array_keys($details['pubdate_filter'])[0] }}]).every",
                   "array_values($details['pubdate_filter'])[0] }}')",
                   '<tr id="pub_date_row">'):
        i = view.index(anchor)
        preceding = view[:i]
        assert preceding.rindex("@if ($details['pubdate_filter'] ?? null)") > \
            (preceding.rindex('@endif') if '@endif' in preceding else -1), (
            f'`{anchor}` is not inside the pubdate_filter gate — on a contract '
            'with no publication-date column it silently filters the table')


def _js_function(text, name):
    """One JS function's body, by walking balanced braces from its `{`.

    ⚠ SCOPED, because the file holds several functions that touch the same
    element ids. A file-wide scan for `#spine-stats` cannot tell the union
    branch from the loop that was deleted, which is the "guard inspected a
    mention, not what the code did" failure this section records seven times.
    """
    code = _php_code_only(text)
    i = code.index('function %s(' % name)
    j = code.index('{', i)
    depth, k = 0, j
    while k < len(code):
        if code[k] == '{':
            depth += 1
        elif code[k] == '}':
            depth -= 1
            if depth == 0:
                return code[j:k + 1]
        k += 1
    raise AssertionError('unbalanced function %s' % name)


def test_the_capital_tiles_are_server_rendered_not_hydrated_from_the_retired_series():
    """⚠⚠ THE DEFECT: EIGHT BLANK TILES, WITH A CORRECT TABLE BESIDE THEM.

    The tab's tiles hydrated by AJAX from `/get/orgs/pstats-{measure}/{id}/
    {pubdate}` over `capitalprojectsdollarscomp`. The ONLY call to
    `loadFinStat()` sat inside the `@if ($details['pubDateFilter'])` block, and
    the spine contract turns that off — so after the tab was repointed at the
    spine nothing called it. Measured on the rendered page 2026-09-10: all eight
    tiles read `&nbsp;` and ZERO pstats requests were made, on every org that
    has spine projects. Table, headers and payload were right throughout.

    ⚠ `pstats-union` is the ONE survivor and is deliberately allowed: an org
    matched by plan TEXT holds no spine row, so that endpoint is the only figure
    it has, and the union block labels every cell `2023 series`.
    """
    ctrl = _php_code_only(_read(CONTROLLER))
    i = ctrl.index('function orgProjectSection')
    body = ctrl[i:ctrl.index('public function ', i + 10)]
    assert '/get/capital/stats/org/' in body, (
        'the capital tiles are no longer fed by the org-scoped spine stats — '
        'without them the eight tiles have no server-rendered source')
    hydration = [m for m in re.findall(r'pstats-[a-z_]+', body)
                 if m != 'pstats-union']
    assert not hydration, (
        'the retired-series tile hydration is back; these render blank on the '
        'spine contract because nothing calls loadFinStat(): %s' % hydration)
    assert 'finStatUrls' not in body, (
        'finStatUrls is back — the view no longer has a loop to consume it')


def test_amount_over_budget_is_not_reproduced():
    """⚠⚠ INVARIANT 11, ON THE ONE SURFACE THAT STILL RENDERED IT. `Amount Over
    Budget` is the label carrying TWO definitions — every row's budget
    difference globally, but only the NEGATIVE ones per district — so
    repointing it under new data preserves the defect. The Overview drops it,
    the district tab drops it, and the union block here serves the value and
    deliberately does not render it.
    """
    view = _php_code_only(_read(VIEW))
    for dead in ('Amount Over Budget', 'over_budg_am'):
        assert dead not in view, (
            'the org capital tab reproduces the two-definition label: %s' % dead)


def test_every_money_tile_carries_the_population_of_its_own_measure():
    """⚠⚠ ⚑ F, AND THE KEY HAS TO MATCH. The six measures are not a funnel and
    no two are over the same set of projects — this org's planned total is over
    1,635 projects and its spent total over 2,149 — so a total with no
    denominator reads as a funnel that leaks.

    ⚠ A population for the WRONG measure is worse than none: it is a confident,
    plausible, wrong denominator. So this pairs each tile's `$oMoney[key]` with
    the `$oPop(key)` in the same tile rather than merely counting that some
    population is present somewhere in the grid.
    """
    view = _php_code_only(_read(VIEW))
    i = view.index('id="spine-stats"')
    grid = view[i:view.index('id="union_stats"')]
    tiles = re.findall(r'<div class="db-stat[^"]*">(.*?)</div>\s*(?=<div class="db-stat|</div>)',
                       grid, flags=re.S)
    money = [t for t in tiles if "$oMoney['" in t]
    assert len(money) >= 2, (
        'the spine grid no longer renders any money tile — found %d' % len(money))
    for t in money:
        keys = set(re.findall(r"\$oMoney\['([a-z_]+)'\]", t))
        pops = set(re.findall(r"\$oPop\('([a-z_]+)'\)", t))
        assert keys == pops, (
            'a money tile states the population of a different measure (or '
            'none): value=%s population=%s' % (sorted(keys), sorted(pops)))


def test_the_union_block_hides_the_spine_grid():
    """⚠⚠ THE TWO BLOCKS CANNOT BOTH BE TRUE, AND BOTH RENDERING IS A VISIBLE
    CONTRADICTION. An org on the union path holds no spine row, so
    `/get/capital/stats/org/{id}` correctly answers `found: false` and the grid
    renders "no projects in Databook's capital spine under this organization" —
    true, and sitting directly above $681M of real figures. Every assertion
    about either block passes in that state; only looking sees it.
    """
    body = _js_function(_read(VIEW), 'loadUnionStats')
    assert "$('#spine-stats').hide()" in body, (
        "loadUnionStats no longer hides the spine grid — the tab renders "
        "'no projects in the capital spine' above the union's own figures")
    assert "$('#union_stats').show()" in body, (
        'loadUnionStats no longer shows its own block — its writes land on '
        'hidden tiles and the reader sees no figures at all')


def test_the_dead_retired_series_hydration_loop_is_gone_not_left_inert():
    """⚠ DELETE, NOT DISABLE — the call the district tab made for the same
    reason. `loadFinStat()` could never run once `pubDateFilter` was gated off,
    but it still NAMED `#over_budg_am`, `#orig_cost` and `#curr_cost` and still
    multiplied by 1000. Dead code that names the thing we removed is how a later
    reader concludes the tiles are still hydrated from the retired series.

    ⚠ The function itself SURVIVES because its caller relies on the popovers;
    what must not survive is its body.
    """
    body = _js_function(_read(VIEW), 'loadFinStat')
    for dead in ('finStatUrls', 'pstats', 'filter-1', 'toFinShortK'):
        assert dead not in body, (
            'loadFinStat still carries its retired-series body: %s' % dead)
    offenders = re.findall(r'to(?:Fin|FinShortK)\([^)]*,\s*1000\s*\)', body)
    assert not offenders, 'the 1000x multiplier is back: %s' % offenders
