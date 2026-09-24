"""`/projects/budget-lines/{code}` — the eight tiles that contradicted each other.

⚠⚠ MEASURED ON THE RENDERED PAGE, 2026-09-10, `/projects/budget-lines/EP-0007`:

    Projects 1          Original Cost   $502M
    Amount Over Budget $297M            Current Cost    $474M

$502M against $474M is **$28M UNDER** budget, beside a tile claiming $297M over,
in one grid. The tiles were summed in the browser from the retired series' rows
the table happened to be showing, times 1000, and `#over_budg_am` accumulated
`-BUDG_DIFF` — the publisher's own difference column, which does not reconcile
with the two costs shown next to it. That is why this section reproduces `Amount
Over Budget` nowhere.

⚠⚠ AND `Projects 1` WHERE THE SPINE HAS **60**. The table's endpoint is
`SELECT * FROM capitalprojectsdollarscomp WHERE "BUDGET_LINE" = …` — 34 rows for
9 distinct projects over 14 publication dates — so this is the "2 projects where
the spine has 268" defect the category page already fixed, on the page next door.

⚠⚠ AND THE SPINE'S `budget_line` FILTER HAD NO CONSUMER IN `app/`. It was built,
normalised on both sides through `modules/budgetline` and verified across twelve
list/map combinations — and the string `budget_line` appeared nowhere in the
frontend, so no page could ask for it. "Check a new module has a CONSUMER, not
just a test."

⚠⚠ AND THE SCOPE LOOKUP WOULD HAVE ANSWERED `found: false` FOR EVERY LINK FROM
THE INDEX. `capital_program_stats.scope_id` holds the hyphenated form while
`capitalbudget` — which the index links from — holds `EP 0007` with a space on
all 15,742 rows: `EP-0007` -> 60 projects, `EP 0007` -> **0**. A zero there reads
as "this budget line has no capital projects".
"""
import ast
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
ROUTER = os.path.join(ROOT, 'api', 'routers', 'capital.py')
CTRL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Projects.php')
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'budgetLineA.blade.php')
LIST_VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'projects.blade.php')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _code_only(text):
    """⚠ Blade, block and line comments stripped. Every guard below searches for
    a string this session's own comments quote — `Amount Over Budget`,
    `over_budg_am`, `budget_line`, `1000`. Own-prose firings in this repo stand
    at 23; each of these was run against the unmutated file first."""
    text = re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'^\s*//.*$', '', text, flags=re.M)


def _php_method(text, name):
    code = _code_only(text)
    i = code.index('function %s(' % name)
    return code[i:code.index('public function ', i + 10)]


def _load_budgetline():
    """⚠⚠ BY PATH, NEVER `from modules import budgetline`. `conftest.py` replaces
    the whole `modules` package with a MagicMock, so the import yields a mock
    whose `sql_norm(...)` is a MagicMock and every `in` test against it raises
    `TypeError: 'in <string>' requires string as left operand`. It bit on the
    first run of this guard. `modules/budgetline` imports only `re`, so it loads
    standalone.

    ⚠ And the load is ASSERTED, because a mock that satisfied the assertions
    silently would make this guard measure nothing.
    """
    import importlib.util
    path = os.path.join(ROOT, 'api', 'modules', 'budgetline.py')
    spec = importlib.util.spec_from_file_location('_budgetline_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert isinstance(mod.sql_norm('bl'), str), (
        'modules/budgetline did not load as the real module')
    return mod


def _py_function_code(path, name):
    """A Python function's statements with the docstring dropped — the shape
    own-prose firing 22 established, since `ast.unparse` includes it."""
    fn = next(n for n in ast.walk(ast.parse(_read(path)))
              if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
              and n.name == name)
    stmts = list(fn.body)
    if (stmts and isinstance(stmts[0], ast.Expr)
            and isinstance(stmts[0].value, ast.Constant)
            and isinstance(stmts[0].value.value, str)):
        stmts = stmts[1:]
    return '\n'.join(ast.unparse(st) for st in stmts)


def test_the_budget_line_scope_is_looked_up_through_the_normaliser():
    """⚠⚠ WITHOUT THIS THE TILES READ "no projects" ON EVERY LINK FROM THE INDEX.
    Verified against the running endpoint rather than reasoned about: `EP-0007`,
    `EP 0007`, `EP0007`, `ep-0007` all return 60, and `P -I001` / `PI001` both
    return 1,135 — the figure `modules/budgetline` was measured against.

    ⚠ The rule has ONE owner in both languages. A second spelling of the strip
    pattern here is the suffix-list defect: a check measuring a different system
    than the code it guards.
    """
    body = _py_function_code(ROUTER, 'capital_scope_stats')
    assert "scope_type == 'budget_line'" in body, (
        'the budget-line scope is no longer special-cased, so a space-spelled '
        'code — which is what capitalbudget publishes — misses every row')
    assert 'budgetline.sql_norm(' in body, (
        'the lookup no longer normalises the stored column through '
        'modules/budgetline')
    assert 'budgetline.norm(' in body, (
        'the lookup no longer normalises the CALLER\'s value; normalising one '
        'side only is the documented way to return a third fewer rows while '
        'looking careful')
    assert not re.search(r"regexp_replace\(\s*['\"]?scope_id", body), (
        'the strip pattern is re-typed here instead of coming from '
        'modules/budgetline')


def test_the_budget_line_tiles_are_server_rendered_from_the_spine():
    body = _php_method(_read(CTRL), 'budgetLine_a')
    assert '/get/capital/stats/budget_line/' in body, (
        'the budget-line page no longer fetches the spine scope, so its tiles '
        'have no server-rendered source')
    assert 'finStatSelectors' not in body, (
        'the browser-side tile summation is back — it summed the retired '
        "series' currently-filtered rows and read 1 project where the spine "
        'has 60')


def test_amount_over_budget_is_not_reproduced():
    """⚠⚠ INVARIANT 11, on the page where it was arithmetically self-refuting."""
    view = _code_only(_read(VIEW))
    for dead in ('Amount Over Budget', 'over_budg_am'):
        assert dead not in view, (
            'the budget-line page reproduces the two-definition label: %s' % dead)


def test_every_money_tile_carries_the_population_of_its_own_measure():
    """⚠ ⚑ F. On EP-0007 the planned total is over 46 projects and the spent
    total over 48. A population for the WRONG measure is worse than none, so
    each tile's `$bMoney[key]` is paired with the `$bPop(key)` in the SAME tile.
    """
    view = _code_only(_read(VIEW))
    i = view.index('id="stats_collapse"')
    grid = view[i:view.index('</div>\n\t\t\t\t{{', i)] if '</div>\n\t\t\t\t{{' in view[i:] \
        else view[i:i + 6000]
    tiles = re.findall(r'<div class="db-stat[^"]*">(.*?)</div>\s*(?=<div class="db-stat|</div>)',
                       grid, flags=re.S)
    money = [t for t in tiles if "$bMoney['" in t]
    assert len(money) >= 2, (
        'the budget-line grid renders no money tile — found %d' % len(money))
    for t in money:
        keys = set(re.findall(r"\$bMoney\['([a-z_]+)'\]", t))
        pops = set(re.findall(r"\$bPop\('([a-z_]+)'\)", t))
        assert keys == pops, (
            'a money tile states the population of a different measure (or '
            'none): value=%s population=%s' % (sorted(keys), sorted(pops)))


def test_no_budget_line_money_cell_multiplies_by_a_thousand():
    """⚠⚠ INVARIANT 2. The retired series publishes THOUSANDS and every tile
    here passed `, 1000`; the spine is USD, so carrying one over renders $3.0B
    as $3.0T."""
    view = _code_only(_read(VIEW))
    offenders = re.findall(r'to(?:Fin|FinShortK)\([^)]*,\s*1000\s*\)', view)
    assert not offenders, 'spine money must not be scaled: %s' % offenders


def test_the_tiles_and_the_table_are_one_view_and_the_page_no_longer_says_otherwise():
    """⚠⚠ RE-EXPRESSED 2026-09-10, WHEN THE TABLE WAS MIGRATED — and its previous
    form was passing FOR THE WRONG REASON, which is the more useful half.

    It read `assert '2023' in block`, standing for invariant 9: the tiles were
    the spine (60) and the table below was the 2023 series at one publication
    date (1 row), so the page had to SAY they were different views or the two
    read as a contradiction. That was right while it was true.

    The table is now the same spine at the same grain, so the disclosure
    describes a page that no longer exists — and a reader who is told to
    discount a table that agrees with the tiles exactly is worse off than one
    told nothing. So the assertion inverts: the claim must be GONE.

    ⚠⚠ AND THE OLD ASSERTION STILL PASSED AFTER THE SENTENCE WAS DELETED. It read
    the RAW file, and the Blade comment recording the removal quotes the removed
    sentence — *"the 2023 project detail series"* — so `'2023' in block` matched
    this session's own prose. Own-prose firing 24, and the first one in this repo
    to be found by a guard passing rather than failing. Every assertion here
    reads the comment-stripped copy.
    """
    view = _code_only(_read(VIEW))
    i = view.index('id="stats_collapse"')
    block = view[i:i + 6000]
    assert 'budget_line=' in block, (
        'the tiles no longer link to the spine\'s own list of this line\'s '
        'projects — the figure has no destination and the endpoint filter loses '
        'a consumer')
    assert '2023' not in block, (
        'the page still tells the reader the table below the tiles is the 2023 '
        'series. It is the spine now, on the same projects the tiles count, so '
        'that sentence is a stale disclosure')
    assert re.search(r'same\s+\{\{\s*\$bFmtN\(\$bTracked\)', block), (
        'the sentence no longer states, from the SERVED figure, that the table '
        'is on the same projects as the tiles — invariant 9 still applies, it '
        'is just satisfied by agreement now rather than by disclaiming a '
        'difference')


def test_the_budget_line_project_table_is_served_from_the_spine():
    """⚠⚠ THE PAGE PUBLISHED ONE PROJECT OF SIXTY. Measured on the rendered
    `/projects/budget-lines/EP 0007`, 2026-09-10:

        Showing 1 to 1 of 1 entries (filtered from 34 total entries)

    directly beneath a tile reading **60**. `capitalprojectsdollarscomp` holds 34
    rows for **9** distinct projects on that line — one per publication vintage,
    `UTIUTIL` alone 14 times — and the page's own publication-date control then
    selected the last of 15 dates and cut those 34 to 1.

    ⚠ The retired endpoint must be GONE, not merely unused: leaving the URL in
    the controller is how a second consumer appears later.
    """
    body = _php_method(_read(CTRL), 'budgetLine_a')
    assert '/get/capital/projects/by-budget-line/' in body, (
        'the budget-line table is no longer served from the spine')
    assert '/get/capitalprojects/by_budgetline/' not in body, (
        'the retired-series project endpoint is back on this page — 34 rows for '
        '9 projects where the spine has 60')
    assert "$ds->get('spine')" in body, (
        "the page no longer uses the `spine` dataset contract. `main` is written "
        'against the retired series and multiplies every money cell by 1000, so '
        'reusing it renders $3.0B as $3.0T (invariant 2)')
    assert "$ds->get('main')" not in body, (
        'the retired-series contract is back on this page')


def test_the_budget_line_list_normalises_the_code_on_both_sides():
    """⚠⚠ ONE SIDE ONLY RETURNS 0, AND 0 READS AS "no projects on this line".
    `capitalbudget` — which every link to this page comes from — publishes
    `EP 0007` with a SPACE on all 15,742 rows, and the spine's `budget_lines`
    array holds `EP-0007`. Verified against the running endpoint: `EP 0007`,
    `EP-0007`, `EP0007`, `ep-0007` and `ep 0007` all return **60**.

    ⚠ THE PATTERN IS PARSED OUT OF WHAT `sql_norm` EMITS AND APPLIED, never
    re-typed. A guard that reimplements the rule it guards measures a different
    system — the finding that made
    `test_the_sql_and_python_budget_line_rules_agree` rewrite itself.
    """
    budgetline = _load_budgetline()
    body = _py_function_code(ROUTER, 'capital_projects_by_budget_line')
    assert 'budgetline.norm(' in body, (
        "the CALLER's value is no longer normalised")
    assert 'budgetline.sql_norm(' in body, (
        'the stored column is no longer normalised')
    # ⚠⚠ THE QUERY MUST CALL THE OWNER, NOT CARRY A COPY OF ITS OUTPUT. The first
    # form of this assertion looked for the emitted SQL literally in the
    # function's source and failed on correct code, because the expression is
    # concatenated at runtime — `ast.unparse` shows the CALL. Asserting the call
    # is what stops a literal being pasted in later.
    assert "budgetline.sql_norm('bl')" in body or \
           'budgetline.sql_norm("bl")' in body, (
        'the query no longer builds its normalisation by calling '
        'modules/budgetline; a pasted copy of the pattern is the suffix-list '
        'defect — a check measuring a different system from the code')
    assert not re.search(r"regexp_replace\(\s*bl\b", body), (
        'the strip pattern is re-typed in this query instead of coming from '
        'modules/budgetline')

    # ⚠⚠ AND THE TWO LANGUAGES MUST AGREE, parsed out of what `sql_norm` emits
    # and applied — never re-typed. This is the shape
    # `test_the_sql_and_python_budget_line_rules_agree` had to be rewritten into
    # after its first version re-typed the strip pattern beside a `startswith`
    # check, so dropping whitespace from `sql_norm` — the whole defect, since
    # `AG 0001` and `F  D109` are space-spelled — changed nothing it could see.
    emitted = budgetline.sql_norm('bl')
    m = re.search(r"regexp_replace\(\s*bl\s*,\s*'([^']*)'\s*,\s*'([^']*)'",
                  emitted)
    assert m, ('sql_norm no longer emits a regexp_replace this guard can read: '
               '%r' % emitted)
    pattern, repl = m.group(1), m.group(2)
    folds_case = 'upper(' in emitted
    for spelling in ('EP 0007', 'EP-0007', 'EP0007', 'ep-0007', 'P -I001',
                     'C -0075', 'F  D109'):
        sql_side = re.sub(pattern, repl, spelling)
        if folds_case:
            sql_side = sql_side.upper()
        assert sql_side == budgetline.norm(spelling), (
            'the SQL rule and the Python rule disagree on %r: SQL gives %r, '
            'norm() gives %r — so the caller and the column are normalised to '
            'different keys and the join returns 0'
            % (spelling, sql_side, budgetline.norm(spelling)))
    assert 'unnest(p.budget_lines)' in body, (
        '`budget_lines` stores the RAW spelling, so a normalised match cannot '
        'use the GIN index and must unnest; `&&` on the raw array returns 0')


def test_the_map_and_the_table_answer_one_question():
    """⚠⚠ THE MAP DREW 7 FEATURES FOR 3 PROJECTS, AND THEN 0. It was built from
    `r['GEO_JSON']` on the retired series' rows — so one project was plotted once
    per publication vintage — and after the page's own date control it drew
    nothing. The spine carries no `GEO_JSON` column at all, so a table migration
    that left this reading the table would have drawn an empty map with a clean
    container, a loaded style and an empty console. `/projects/categories/{slug}`
    is measured to be in exactly that state.

    ⚠ ONE SCOPE, BUILT ONCE. `budget_line` is the page's only filter, so the map
    and the list cannot answer differently — the property `/projects` had to be
    given by construction after `?has_location=false` listed 12,464 projects
    while the map drew 4,560 the list had excluded.
    """
    body = _php_method(_read(CTRL), 'budgetLine_a')
    assert 'capGeojsonUrl' in body, (
        'the page no longer passes a served geojson URL, so its map has no '
        'source but the table it can no longer read')
    # ⚠⚠ SCOPED TO THE ARRAY ENTRY, NOT A WINDOW. The first form of this
    # assertion read 400 characters from `capGeojsonUrl` — which reaches
    # `"/get/capital/stats/budget_line/{$enc}"` four keys later, so `budget_line`
    # was present no matter what this key held. Verified by mutation: stripping
    # the scope off the map's URL left the guard GREEN. Third instance in this
    # repo of "scope a guard to the statement, not the word".
    decl = next(l for l in body.splitlines() if 'capGeojsonUrl' in l)
    assert '/get/capital/geojson' in decl, (
        "the map's URL is not the geojson endpoint: %s" % decl.strip())
    assert 'budget_line' in decl, (
        "the map's URL is not scoped to this budget line, so it answers a "
        'different question from the list beside it — the map would draw all '
        '4,560 located projects under a heading about one budget line: %s'
        % decl.strip())

    view = _code_only(_read(VIEW))
    assert '$capGeojsonUrl' in view, 'the view never fetches the served geojson'
    # ⚠⚠ COMMENT-STRIPPED, because the comments recording this fix quote
    # `GEO_JSON` five times. Own-prose firing 24 happened in this very file.
    assert 'GEO_JSON' not in view, (
        'live code on this page reads GEO_JSON again — a column the spine does '
        'not serve, which yields an empty map with no error: %s'
        % re.findall(r'.{0,60}GEO_JSON.{0,20}', view)[:2])


def test_the_publication_date_control_is_gated_on_the_contract():
    """⚠⚠ INVARIANT 10 — A CONTROL INDEXED ON A COLUMN POSITION. `columns([1])`
    meant `Publication Date` under the retired contract, which declares a details
    expander so `get()` prepends a column. The `spine` contract declares none, so
    column 1 is `Agency`: unchanged, this block would have built a dropdown of 60
    agency names, auto-selected the last and filtered the table to it. That
    shipped on the org capital tab, where the page read *"Showing 1 to 1 of 1
    (filtered from 2,798)"* with a correct payload, correct headers and correct
    rows — only the visible count wrong.

    ⚠ AND THE LABEL GOES WITH THE CONTROL. `Project Publication Date` and its ⓘ
    sit in the markup the `<select>` is appended to; ungated, the page renders a
    caption beside an EMPTY cell — invariant 7's fourth thing, which is what
    eight tiles on the org capital tab did for weeks.
    """
    view = _code_only(_read(VIEW))
    assert 'columns([1])' not in view, (
        'the publication-date control is hardcoded to column 1 again; on the '
        'spine contract that column is Agency')
    assert "pubdate_filter" in view, (
        'the control is no longer gated on the dataset contract, so its column '
        'index and its meaning can drift apart again')
    # The label must be behind the same gate as the control that fills it.
    i = view.index('id="pub_date_prj_filter"')
    before = view[:i]
    gate = before.rindex('@if')
    assert 'pubdate_filter' in before[gate:], (
        'the "Project Publication Date" label is not gated on the same key as '
        'the control appended into it, so it renders as a caption for a control '
        'that does not exist')
    # ⚠⚠ AND THIS GUARD'S LAST CLAUSE WAS RETIRED 2026-09-10, WHICH IS NOT THE
    # SAME AS WEAKENING IT. It read `assert "'pubdate_filter' => [1 =>" in
    # contracts` — the retired-series contracts `main` and `main-a` declared the
    # column, and they have been DELETED (nothing routed to them, and each
    # carried eleven `, 1000` multipliers). Left as it was, the guard would have
    # required a dead contract to exist in order to pass, i.e. forbidden exactly
    # the deletion this section wanted. The condition it checked has ended.
    #
    # What survives is the property that outlives any one contract: NO contract
    # may declare this key at a column other than 1, because 1 is where
    # `Publication Date` sits under a contract with a details expander, and the
    # `@if` above only checks that the key EXISTS — it never reads a position.
    # So a contract declaring `[2 =>` would gate the control on and then filter
    # the wrong column, which is invariant 10 with the numbers changed.
    contracts = _code_only(_read(os.path.join(ROOT, 'app', 'app', 'Custom',
                                              'ProjectsDatasets.php')))
    for m in re.finditer(r"'pubdate_filter'\s*=>\s*\[\s*(\d+)\s*=>", contracts):
        assert m.group(1) == '1', (
            'a dataset contract declares its publication-date column as %s; the '
            'view gates the control on the KEY and never reads the position, so '
            'the dropdown would filter a different column' % m.group(1))


def test_an_empty_commitments_series_is_not_drawn_and_cannot_throw():
    """⚠⚠ AN UNCAUGHT `TypeError` ON A LIVE PAGE, FOUND BY VERIFYING A DIFFERENT
    CHANGE. `capCommUpdate` initialised `labels` as an OBJECT and only ever
    assigned an array inside its loop, so a budget line with no matching
    commitment row left `{}`, and Chart.js's `buildTicks` threw `n.slice is not
    a function`. Measured on `/projects/budget-lines/P I001`, where
    `capitalcommitmentplan` holds **0 rows** for the line: HTTP 200, one uncaught
    TypeError, every other check green.

    ⚠ PRE-EXISTING — the block that fetches this data and triggers the call is
    untouched by the spine migration. Guarded because an uncaught error makes
    "did this page throw?" unanswerable, which is what the page's headless
    verifier now asserts.

    ⚠ And nothing to plot is not an empty chart: `P I001` is a real budget line
    with 1,135 projects and no commitment plan, and a blank canvas under
    "Commitments (OMB)" says the City committed nothing.
    """
    view = _code_only(_read(VIEW))
    i = view.index('function capCommUpdate(')
    body = view[i:view.index('\n\t\tfunction ', i + 10)] if '\n\t\tfunction ' in view[i + 10:] \
        else view[i:i + 3000]
    assert not re.search(r'var\s+labels\s*=\s*\{\s*\}', body), (
        'labels is an object again; Chart.js calls .slice on it and throws')
    assert re.search(r'var\s+labels\s*=\s*\[\s*\]', body), (
        'labels is no longer initialised as an array')
    assert re.search(r'if\s*\(!datasets\.length\)', body), (
        'the chart is drawn even with no series, so a budget line with no '
        'commitment plan renders an empty canvas that reads as "$0 committed"')


def test_the_projects_page_accepts_and_carries_the_budget_line_filter():
    """⚠⚠ TWO HALVES, AND EITHER ALONE IS USELESS. The controller must ACCEPT the
    parameter — otherwise the link from the budget-line page lands on an
    unfiltered list of 17,024 and reads as broken — and the filter FORM must
    carry it as a hidden field, because a GET form submits only its own fields,
    so touching any other filter would silently drop it. Same rule as
    "pagination links carry the current filters", one submit button over.
    """
    ctrl = _php_method(_read(CTRL), 'projects')
    # ⚠ Balanced brackets, not a `];` search — the array closes
    # `], function ($v) { … });`, so the naive delimiter is absent and the guard
    # raised ValueError on the unmutated file instead of asserting anything.
    i = ctrl.index('$capFilters = array_filter([')
    j = ctrl.index('[', i)
    depth, k = 0, j
    while k < len(ctrl):
        if ctrl[k] == '[':
            depth += 1
        elif ctrl[k] == ']':
            depth -= 1
            if depth == 0:
                break
        k += 1
    arr = ctrl[j:k + 1]
    assert "'budget_line'" in arr, (
        'the /projects controller no longer accepts budget_line, so the '
        'endpoint filter has no consumer again')
    view = _code_only(_read(LIST_VIEW))
    j = view.index('id="capFilterForm"')
    form = view[j:view.index('</form>', j)]
    assert re.search(r"name=\"budget_line\"", form), (
        'the filter form does not carry budget_line, so applying any other '
        'filter drops it silently')
    assert "$fv('budget_line')" in view, (
        'the page never states which budget line it is filtered to, so a reader '
        'sees a narrowed list with no reason for it and no way back')


def test_the_commitments_chart_resolves_its_budget_line_through_the_one_owner():
    """⚠⚠ A LIST OF GUESSED SPELLINGS SERVED A PARTIAL ANSWER FOR 87% OF ROWS.
    `/get/capitalcommitments/stats_by_budgetline/{blcode}` tried the raw code, a
    stripped form, and forms with a space or a hyphen inserted after the leading
    alpha run — and RETURNED THE FIRST that yielded any rows.
    `capitalcommitmentplan` genuinely spells one budget line several ways across
    vintages, so "the first spelling with rows" silently drops the others.

    Measured 2026-09-10 over every row of that table:

        1,817 of 2,724 distinct budget lines carry MORE THAN ONE spelling,
        covering 51,623 of 59,076 rows, and each of those lines loses exactly
        ONE publication vintage — 1,817 vintages missing from the chart's own
        date dropdown.

    `C 0075` holds 30 vintages (2016-04-26 → 2026-05-12) and `C -0075` holds one
    (2018-10-10); the endpoint served whichever it reached first. After: every
    spelling of that line returns **61 groups over 31 vintages**. `EP 0007`,
    which the budget-line page links with, went 30 → 31 for the same reason.

    ⚠ THE UNION IS ADDITIVE, MEASURED NOT ASSUMED: **0** group keys
    `(normalised line, Published Date, Funding Type)` span two spellings, so
    nothing merges and no figure double-counts. Without that check this would be
    an unsafe change to a published chart.

    ⚠ And the loop could not generate the padded single-letter form the sources
    use at all — `P -I001`, `C -0075` — which is the exact case
    `modules/budgetline` exists for.
    """
    budgetline = _load_budgetline()
    main = os.path.join(ROOT, 'api', 'main.py')
    body = _py_function_code(main, 'get_capital_commitments_stats_by_budgetline')
    assert 'budgetline.norm(' in body, (
        "the caller's budget line is no longer normalised through the one owner")
    assert "budgetline.sql_norm(" in body, (
        'the stored column is no longer normalised, so a space-spelled code — '
        'which is what capitalbudget publishes — misses every row')
    # ⚠⚠ THE VARIANT LOOP MUST BE GONE, not merely bypassed. Its shape is the
    # defect: any "try spellings until one returns rows" reintroduces the
    # partial answer, because the first hit wins and the rest are invisible.
    assert 'stripped' not in body and 'dashed' not in body, (
        'the hand-rolled spelling variants are back; a list of guessed '
        'spellings returns whichever one it reaches first and silently drops '
        'the rest: %s' % body[:200])
    assert not re.search(r'for\s+\w+\s+in\s+dict\.fromkeys\(', body), (
        'the try-each-spelling loop is back on this endpoint')
    # And the rule itself must still agree across the two languages.
    emitted = budgetline.sql_norm('"Budget Line"')
    m = re.search(r"regexp_replace\(\s*\S.*?,\s*'([^']*)'\s*,\s*'([^']*)'",
                  emitted)
    assert m, 'sql_norm no longer emits a readable regexp_replace: %r' % emitted
    for spelling in ('EP 0007', 'EP-0007', 'EP0007', 'C -0075', 'P -I001'):
        sql_side = re.sub(m.group(1), m.group(2), spelling)
        if 'upper(' in emitted:
            sql_side = sql_side.upper()
        assert sql_side == budgetline.norm(spelling), (
            'the SQL and Python rules disagree on %r (%r vs %r)'
            % (spelling, sql_side, budgetline.norm(spelling)))


def test_the_other_by_budget_line_endpoint_was_measured_not_skipped():
    """⚠ `/get/commitments/by_budgetline/{blcode}` STILL CARRIES THE VARIANT LOOP,
    and that is a measured decision rather than an oversight.

    It reads `capitalprojectscommitments`, and measured 2026-09-10 that table has
    **0** budget lines carrying more than one spelling across all 41,277 rows
    (1,913 distinct lines, hyphenated throughout). So there is no partial answer
    to fix there, and this repo's standing rule is that extending a fix to a
    second table needs its own measurement, not an assumption.

    This guard exists so the NEXT reader knows the difference between "checked
    and left alone" and "not looked at" — those two states are what a bare
    absence cannot distinguish, which is this section's oldest lesson. If that
    table ever gains a second spelling, the loop starts dropping rows there too
    and this docstring is the record of why it was safe until then.
    """
    main = _read(os.path.join(ROOT, 'api', 'main.py'))
    assert 'def get_commitments_by_budgetline(' in main, (
        'the endpoint this note is about has been renamed or removed; re-measure '
        'before assuming the note still applies')
