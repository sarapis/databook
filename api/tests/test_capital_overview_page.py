"""Guards on the Overview page's controller seam and its published copy.

⚠⚠ THE DEFECT THIS SEAM HAS ALREADY PRODUCED, ON THIS SITE. `ProcurementController`
NAMES each view-data key, so a payload the API serves and the Blade reads still
arrives as `null` unless the controller lists it — and `?? []` degrades
politely. The Digital Services Overview shipped with no composition bar and no
pipeline block that way, while every unit guard passed. Only fetching the page
found it (#247).

So this pins the seam itself: every key the view reads off `$capital` must be
served by `/get/capital/overview`, and the controller must pass `capital`.
"""
import ast
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'capital.blade.php')
CONTROLLER = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Projects.php')
ROUTER = os.path.realpath(
    os.path.join(os.path.dirname(__file__), '..', 'routers', 'capital.py'))


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def test_the_controller_passes_the_capital_payload():
    """Without this the view's `$capital` is undefined and every figure blanks
    — the #247 failure, silently."""
    src = _read(CONTROLLER)
    m = re.search(r"'capital'\s*=>\s*DatabookAPI::reqOCE\('(/get/capital/[^']+)'\)", src)
    assert m, "Projects::main() must pass a 'capital' key from the overview endpoint"
    assert m.group(1) == '/get/capital/overview'


def test_every_key_the_view_reads_is_one_the_endpoint_serves():
    """⚠ Reads the ENDPOINT's own returned literal, not a list retyped here —
    a guard comparing the view against a hand-kept list measures a different
    system than the one that ships."""
    view = _read(VIEW)
    read_keys = set(re.findall(r"\$cap\['([a-z_]+)'\]", view))
    assert read_keys, 'the view reads nothing off $cap — has it been rewritten?'

    router = ast.parse(_read(ROUTER))
    fn = next(n for n in ast.walk(router)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == 'capital_overview')
    served = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    served.add(k.value)
    missing = read_keys - served
    assert not missing, (
        f'the Overview reads key(s) the endpoint does not serve: {sorted(missing)}')


def test_the_page_states_the_measures_are_not_a_funnel():
    """⚑ F. Six measures without that sentence invite a reader to subtract two
    of them and report a shortfall that is an artefact of the columns."""
    view = _read(VIEW)

    # ⚠⚠ ASSERT IT IS ECHOED, NOT MENTIONED. The first version of this guard
    # checked that the string appeared in the file — which the surrounding
    # `@if (!empty($capMoney['note']))` satisfies all by itself, so deleting the
    # `{{ }}` that actually prints the note left the guard green. That is the
    # fourth time in this session's work that a guard inspected a mention
    # rather than the thing the code does.
    def echoed(expr):
        return re.search(r'\{\{\s*' + re.escape(expr) + r'\s*(\?\?[^}]*)?\}\}', view)

    assert echoed("$capMoney['note']"), (
        'the non-funnel note must be ECHOED, not merely referenced in a condition')
    assert echoed("$capMoney['publisher_caveat']"), (
        "the publisher's own caveat must be echoed")


def test_each_measure_shows_its_population_and_whose_definition_it_is():
    """⚠ A total over 5,158 projects beside one over 11,650 reads as a leaking
    funnel; with both denominators visible it reads as six different measures.
    And the definitions are the PUBLISHER'S — the page must say so."""
    view = _read(VIEW)
    for key in ("'population'", "'definition'", "'source'"):
        assert f"$m[{key}]" in view, f'each measure must render {key}'


def test_the_page_states_what_is_not_covered():
    view = _read(VIEW)
    for key in ('without_published_schedule', 'without_published_location'):
        assert key in view, f'the coverage panel must state {key}'


def test_the_page_carries_its_vintage():
    """⚠ A capital figure without its plan version and reporting period is the
    failure this whole section is being rebuilt to end."""
    assert '$capSources' in _read(VIEW)


def test_no_retired_series_tile_survives():
    """⚠⚠ The four old tiles came from `capitalprojectsdollarscomp`, retired by
    NYC in October 2023. `Amount Over Budget` is the one that carried two
    different definitions — summing every row's difference globally, and only
    the negative ones per district."""
    view = _read(VIEW)
    for dead in ('id="projects_no"', 'id="orig_cost"', 'id="curr_cost"',
                 'id="over_budg_am"', 'Amount Over Budget'):
        assert dead not in view, f'a retired-series tile is still rendered: {dead}'


def test_an_unavailable_payload_says_so_rather_than_rendering_nothing():
    """⚠ A silently missing block reads as "the City has no capital
    programme"."""
    view = _read(VIEW)
    assert '$capOk' in view and 'not available right now' in view


# ── /procurement's capital tiles must not drift from the Overview ────────────

PROC_VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'procurement', 'index.blade.php')
PROC_CTRL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'ProcurementController.php')
# ⚠ The capital tiles MOVED from /procurement to /projects (owner request,
# 2026-09-09). The guards below follow the property to its new home rather than
# being deleted — the tiles still mix four denominators wherever they live.
LIST_VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'projects.blade.php')
LIST_CTRL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Projects.php')


def test_the_capital_tiles_are_gone_from_procurement():
    """⚠ RETIRING A GUARD WHEN ITS CONDITION ENDS IS NOT WEAKENING IT — but the
    condition here inverted rather than ended, so the guard did too.

    This used to assert `ProcurementController` reads `/get/capital/overview`,
    because its capital tiles once hydrated from the RETIRED series and showed
    5,128 against the rebuilt Overview's 12,929. The tiles have now moved to
    /projects entirely, so the correct assertion is the opposite one: a
    procurement page must not grow a capital block again, in either place.
    """
    view = _blade_code_only(_read(PROC_VIEW))
    ctrl = _blade_code_only(_read(PROC_CTRL))
    assert 'db-stat-value' not in view or 'in_current_plan' not in view, (
        '/procurement is rendering capital programme figures again — they live '
        'on /projects, and two homes for one number is what this section has '
        'already paid for twice')
    assert '/get/capital/overview' not in ctrl, (
        'ProcurementController still fetches the capital overview for a block '
        'it no longer renders — a view-data key kept past its consumer')


def test_procurement_shows_no_retired_series_capital_tile():
    """⚠ `Amount Over Budget` is deliberately NOT reproduced anywhere: it is the
    label documented here as carrying two definitions, and the rebuilt Overview
    drops it rather than repointing it."""
    # ⚠⚠ SCAN THE RENDERED COPY, NOT THE SOURCE. The first version of this
    # guard fired on the comment in the view EXPLAINING that `Amount Over
    # Budget` is deliberately not reproduced — the own-prose failure this repo
    # documents ten times over, and the seventh in this session's work. Blade
    # comments and PHP line comments are stripped before scanning.
    view = _read(PROC_VIEW)
    view = re.sub(r'\{\{--.*?--\}\}', '', view, flags=re.S)   # Blade comments
    view = re.sub(r'^\s*//.*$', '', view, flags=re.M)            # PHP line comments

    for dead in ('id="projects_no"', 'id="orig_cost"', 'id="curr_cost"',
                 'id="over_budg_am"', 'Amount Over Budget'):
        assert dead not in view, (
            f'/procurement still renders a retired-series capital tile: {dead}')


def test_the_list_page_does_not_show_two_money_measures_without_the_caveat():
    """⚠ It shows planned and spent — two of SIX measures that do not sum or
    nest. Without saying so, a reader subtracts them and reports a shortfall
    that is an artefact of the columns."""
    view = _read(LIST_VIEW)
    assert 'do not sum or nest' in view
    assert re.search(r"route\('capital'\)", view), (
        'it must link to the Overview, which carries all six with populations')


def _blade_code_only(text):
    """Strip Blade and PHP comments before scanning.

    ⚠ Own-prose firings stand at 18 in this repo. The comment explaining the
    mixed-denominator defect below quotes every figure and label this guard
    looks for, so a raw-text scan would pass against the prose while the tiles
    themselves had lost their denominators.
    """
    text = re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)   # Blade comments
    text = re.sub(r'^\s*//.*$', '', text, flags=re.M)         # PHP line comments
    return text


def _capital_tiles(view):
    """The four <a class="db-stat"> tiles of /procurement's capital grid."""
    code = _blade_code_only(view)
    start = code.find('Projects in the current plan')
    assert start > 0, 'the capital tile grid is gone from /procurement'
    grid_start = code.rfind('db-stat-grid', 0, start)
    # ⚠ The grid ends at the `@else` of its own `@if ($pCapOk)`. An earlier
    # draft ended it at the first `</div>` after the last label — which closes
    # that label's VALUE, not the tile, so the fourth tile was cut in half and
    # the guard failed on the unmutated file. Checking the baseline is green
    # before reading a mutation is what caught it.
    grid_end = code.find('@else', grid_start)
    assert grid_end > grid_start, 'the capital grid is no longer inside an @if/@else'
    grid = code[grid_start:grid_end]
    tiles = re.findall(r'<a\b[^>]*class="db-stat[^"]*"[^>]*>(.*?)</a>', grid, flags=re.S)
    return tiles


def test_every_capital_tile_states_what_it_is_over():
    """⚠⚠ THE DEFECT THIS PREVENTS, MEASURED ON THE RENDERED PAGE 2026-09-09.

    These four tiles mix two scopes. Tile 1 counts the 12,929 projects in the
    current plan; "with a published schedule" is 8,483 of ALL 17,024 tracked,
    of which only 6,561 are in the plan. Side by side with no denominators they
    say 66% of the plan is scheduled. The real figure is 51%, and 1,922 of the
    8,483 are not in the current plan at all.

    The money tiles are over different sets again (9,213 planned, 7,118 spent),
    so no two of the four share a denominator. The Overview's own answer to
    this is `population` per measure; this is the same answer at tile size.

    ⚠ Structural on purpose: it asserts each tile CARRIES a rendered
    denominator, not that some string appears somewhere in the grid.
    """
    tiles = _capital_tiles(_read(LIST_VIEW))
    assert len(tiles) == 4, f'expected 4 capital tiles, found {len(tiles)}'
    for tile in tiles:
        label = re.search(r'db-stat-label">([^<]*)<', tile)
        name = label.group(1).strip() if label else '(unlabelled)'
        assert 'db-stat-sub' in tile, (
            f'capital tile "{name}" states a figure with no denominator — '
            'beside a tile scoped to a different set, that invites a ratio '
            'that is wrong by 15 points')


def test_the_schedule_denominator_is_the_tracked_total_not_the_plan():
    """⚠ The whole point is that 8,483 is over 17,024, NOT over 12,929.
    Pointing this denominator at `in_current_plan` would restate the defect
    while looking like a fix — the tile would read "8,483 / of 12,929", which
    is the false 66% written out.

    Reads the ASSIGNED EXPRESSION, not a mention of the key.
    """
    code = _blade_code_only(_read(LIST_VIEW))
    m = re.search(r'\$pTracked\s*=\s*\$pCap\[([^\]]+)\]', code)
    assert m, '$pTracked must be assigned from the payload'
    assert "'projects'" in m.group(1), (
        f"the tracked total must come from $pCap['projects'], got {m.group(1)} — "
        "scoping it to the current plan reproduces the mixed-denominator defect")


# ── the HOME page's capital card (Phase 4) ──────────────────────────────────

ROOT_VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'root.blade.php')
ROOT_CTRL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Organizations.php')


def test_the_home_controller_passes_the_capital_payload():
    """⚠ #247's seam again, on the most-visited page. `Organizations::root()`
    NAMES each view-data key, so the card renders em dashes — not an error —
    if the key is not passed."""
    ctrl = _read(ROOT_CTRL)
    assert re.search(r"'capital'\s*=>\s*DatabookAPI::reqOCE\('/get/capital/overview'\)", ctrl), (
        'root() must pass the capital payload from the same endpoint '
        '/procurement and the Overview read, or the front page can drift from them')


def test_the_home_capital_card_is_off_the_retired_series():
    """⚠⚠ THE FIGURE THIS REPLACED WAS 5,128, AND IT WAS ON THE FRONT PAGE.
    `projects_no`/`orig_cost`/`curr_cost` hydrated from `cached_stats` over
    `capitalprojectsdollarscomp`, retired by NYC 2023-10-26, while /procurement
    and /projects/capital published 12,929 for the same subject.

    ⚠ `data-multiplier` is checked because the retired series is denominated in
    THOUSANDS and the spine in USD: keeping the multiplier while repointing the
    source renders $201.6B as $201.6T, which still looks like money.

    ⚠ Comments are stripped first — the comment in the view EXPLAINING this
    quotes every one of these strings, which is own-prose firing 19.
    """
    view = _blade_code_only(_read(ROOT_VIEW))
    for dead in ('id="projects_no"', 'id="orig_cost"', 'id="curr_cost"',
                 'data-multiplier'):
        assert dead not in view, (
            f'the home capital card still carries a retired-series artefact: {dead}')


def test_the_home_page_hydrates_no_id_it_does_not_render():
    """⚠⚠ RE-EXPRESSED, NOT RELAXED — and it FAILED on the change that made it
    necessary, which is it doing its job.

    It used to require `root()` to DEFINE `finStatUrls` and then checked three
    named ids were absent from it. `root()` now passes no `finStatUrls` at all:
    the three capital tiles are server-rendered from `/get/capital/overview`,
    and the five remaining entries (`#over_budg_am`, `#long_no`,
    `#over_budg_no`, `#late_start_no`, `#late_end_no`) named ids the home page
    has never rendered. Measured on the rendered page before removing them —
    **0 pstats requests, 24 of 24 tiles hydrated, 0 uncaught JS** — because the
    loop consuming them sits inside a `/* */` block, so it was inert rather than
    broken. It went anyway: this is the section that keeps having to
    re-establish which surfaces read the retired series, and dead config naming
    `#over_budg_am` on the front page is the most expensive place to leave that
    question open.

    The PROPERTY is unchanged and is now asserted against the VIEW instead of
    against three remembered names: every selector-shaped key `root()` passes
    must be an id `root.blade.php` renders. That holds whether the array is
    absent, empty, or repopulated, so it cannot be satisfied by deletion and
    cannot go stale when a tile is renamed.
    """
    ctrl = _blade_code_only(_read(ROOT_CTRL))
    # ⚠ SCOPE TO root(). `Organizations.php` defines finStatUrls THREE times —
    # root(), orgAbout() and orgProjectSection(). An unscoped search happens to
    # find root()'s because it is first in the file, which is luck, not a
    # property: reordering the class would silently point this guard at another
    # action's array. That is the wrong-occurrence trap this repo has paid for.
    start = ctrl.find('public function root()')
    assert start > 0, 'root() is gone from Organizations.php'
    nxt = ctrl.find('public function ', start + 10)
    body = ctrl[start:nxt if nxt > 0 else len(ctrl)]
    m = re.search(r"'finStatUrls'\s*=>\s*\[(.*?)\]", body, flags=re.S)
    keys = re.findall(r"'#([A-Za-z0-9_]+)'\s*=>", m.group(1)) if m else []
    view = _read(os.path.join(ROOT, 'app', 'resources', 'views', 'root.blade.php'))
    rendered = set(re.findall(r'id="([A-Za-z0-9_]+)"', view))
    dead = sorted(k for k in keys if k not in rendered)
    assert not dead, (
        'root() hydrates ids the home page does not render: %s. A finStatUrls '
        'entry for a dropped tile is how loadTableStat throws, and one throw '
        'leaves every remaining prj_stat tile blank.' % dead)
    for dropped in ('projects_no', 'orig_cost', 'curr_cost'):
        assert dropped not in keys, (
            '%s is hydrated again although its tile is server-rendered from '
            'the spine' % dropped)
