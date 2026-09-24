"""Guards on the three triaged fixes: dataset counts, source coverage, periods.

Each is verified by reintroducing its bug, with the mutation asserted to have
landed first — the discipline the rest of this section is written under, because
seven guards here have passed against a real bug by inspecting a mention or an
input rather than what the code did.
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROOT = os.path.realpath(os.path.join(API, '..'))

ROUTER = os.path.join(API, 'routers', 'capital.py')
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'capitalproject.blade.php')
PROJECTS_VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'projects.blade.php')
PROJECTS_CTRL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Projects.php')
DATASETS = os.path.join(ROOT, 'app', 'app', 'Custom', 'ProjectsDatasets.php')
# ⚠ The datasets accordion and the source-coverage table now live in ONE shell,
# `<x-db.data-provenance>`, in two modes. Fifteen views hand-rolled the first and
# this page had a bespoke second; the guards below follow the markup to its new
# home rather than being relaxed — the properties are unchanged.
PROVENANCE = os.path.join(ROOT, 'app', 'resources', 'views', 'components', 'db',
                          'data-provenance.blade.php')


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


def _rendered_copy(src):
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'^[ \t]*//.*$', '', src, flags=re.M)
    return src


def _fn(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef)) and n.name == name:
            return n
    raise AssertionError(f'{name} not found')


def _code(fn):
    """A function's source without its docstring — `ast.unparse` includes it, and
    this repo has fired guards on their own prose twelve times."""
    node = ast.parse(ast.unparse(fn)).body[0]
    if (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)):
        node.body = node.body[1:]
    return ast.unparse(node)


def _load(names):
    """Run named top-level defs/assigns out of the REAL router file.

    The router imports asyncpg-backed modules absent under test, so the pieces
    under guard are compiled out of its AST — never reimplemented here, which
    would measure a different system than the one that ships.
    """
    tree = ast.parse(_read(ROUTER))
    ns = {}
    for node in tree.body:
        keep = False
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            keep = node.name in names
        elif isinstance(node, ast.Assign):
            keep = any(getattr(t, 'id', None) in names for t in node.targets)
        if keep:
            exec(compile(ast.Module(body=[node], type_ignores=[]), ROUTER, 'exec'), ns)
    return ns


# ------------------------------------------------------------------ periods

def test_a_period_is_formatted_by_its_source_not_by_its_length():
    """⚠⚠ MEASURED OVER ALL 205,503 HISTORY ROWS: **0** carry a period that is
    neither 6 nor 8 characters. `cpdd` publishes `YYYYMMDD`, a real publication
    date; the three Dashboard sources publish `YYYYMM`, a reporting PERIOD whose
    months are exactly 01, 05 and 09 — three editions a year.

    ⚠ Rendering `202405` as "1 May 2024" would invent a precision the City did
    not publish, which is why the shape is not guessed from the string.
    """
    ns = _load({'_period_label', '_PERIOD_SHAPE', '_MONTHS'})
    f = ns['_period_label']

    assert f('cpdd', '20231026') == '26 Oct 2023'
    assert f('cpdd', '20190425') == '25 Apr 2019'
    for src in ('dashboard', 'dash_sched', 'dash_money'):
        assert f(src, '202405') == 'May 2024', src
    assert f('dash_money', '200609') == 'Sep 2006'

    # ⚠⚠ KEYED ON THE SOURCE. If the rule read the string's LENGTH, an 8-digit
    # value under a month source would format as a date and vice versa — a
    # plausible-looking wrong date, the worst failure available here. A
    # mismatched shape falls through to the raw value instead.
    assert f('dashboard', '20231026') == '20231026', (
        'a Dashboard source with a date-shaped value must NOT be read as a date')
    assert f('cpdd', '202405') == '202405', (
        'a cpdd source with a month-shaped value must NOT be read as a date')

    # ⚠ Never blank for a non-empty input: an empty cell reads as "not
    # published", which is a different claim from "an unfamiliar shape".
    assert f('weird', '999') == '999'
    assert f('cpdd', None) is None and f('cpdd', '') is None

    # And the source map must cover every source the history builder writes.
    assert set(ns['_PERIOD_SHAPE']) == {'cpdd', 'dashboard', 'dash_sched',
                                        'dash_money'}


def test_the_history_rows_carry_a_label_and_the_page_echoes_it():
    """⚠ A stored key is not copy: `cpdd` and `dash_money` tell a reader nothing,
    and the first is a series retired in 2023."""
    tree = ast.parse(_read(ROUTER))
    code = _code(_fn(tree, '_history'))
    assert 'period_label' in code and '_period_label(' in code, (
        'the history rows no longer carry a formatted period')
    assert 'source_label' in code, 'the history rows no longer carry a source label'
    # ⚠ BESIDE the raw value, never instead of it — `period` is the join key.
    assert "r['period_label']" in code and 'r.get(\'period\')' in code

    view = _read(VIEW)
    # ⚠⚠ THIS USED TO ANCHOR ON `{{ $h['period_label'] ?? … }}` AND `{{
    # $h['source_label'] ?? … }}`, AND IT FIRED WHEN THE HISTORY WAS REGROUPED —
    # correctly. The 45 × 14 unioned table became one block per source, so the
    # source label is now the block HEADING (not a cell repeated on every row)
    # and the period is rendered through the SERVED per-source column list. Both
    # properties are unchanged; only the shape moved.
    #
    # `period_label` must be a served column for every source, so the page cannot
    # print a raw `202405` no matter which block it is in:
    cols = _load({'_HISTORY_COLUMNS'})['_HISTORY_COLUMNS']
    assert cols, '_HISTORY_COLUMNS is gone'
    for src, names in cols.items():
        assert 'period_label' in names, f'{src} does not publish period_label'
        assert 'period' not in names, (
            f'{src} publishes the RAW period, so the page prints 202405')
    # …and the view renders whatever that list says, rather than a hardcoded set.
    assert re.search(r"@foreach\(\$g\['columns'\] as \$col\)", view), (
        'the page no longer renders the served per-source columns')
    assert re.search(r"\{\{ \$g\['source_label'\] \}\}", view), (
        'the page still prints the raw source key')

    ns = _load({'_SOURCE_LABEL'})
    assert set(ns['_SOURCE_LABEL']) == {'cpdd', 'dashboard', 'dash_sched',
                                        'dash_money'}


# ---------------------------------------------------------- source coverage

def test_the_source_table_accounts_for_every_project_keyed_source():
    """⚠⚠ THE POINT IS THE ABSENCES. Listing only the sources that contributed
    leaves a reader unable to tell a publication that omits this project from one
    Databook does not read at all."""
    tree = ast.parse(_read(ROUTER))
    fn = _fn(tree, '_source_coverage')
    code = _code(fn)

    keys = set(re.findall(r"'key':\s*'([a-z0-9_]+)'", code))
    expected = {'cpdb_plan', 'cpdb_commitments', 'dashboard', 'dash_money',
                'dash_sched', 'geometry', 'climate', 'parks', 'cpdd_2023',
                'milestones_2023', 'council_awards'}
    assert keys == expected, f'source list drifted: {sorted(keys ^ expected)}'

    # ⚠ Tables that are NOT project-keyed must be ABSENT, not listed as "no" —
    # "did not appear" against a table with no notion of projects is a claim
    # about the City, not about the project.
    for banned in ('capitalstrategy', 'capitalcashflow', 'capitalcommitmentactuals',
                   'capitalfundingsource'):
        assert banned not in code, (
            f'{banned} is not keyed to a project and must not be listed')

    # ⚠ The three Parks tables are ONE row — measured, they cover the identical
    # 1,660 projects, so three rows would imply three independent confirmations.
    parks = re.search(r"'key':\s*'parks'.*?'tables':\s*\[(.*?)\]", code, re.S)
    assert parks and parks.group(1).count('parkscapital') == 3, (
        'the three Parks tables must share one row')


def test_the_council_award_row_declares_its_different_grain():
    """⚠⚠ Every other row means "this project appears in that table". The Council
    publishes against a BUDGET LINE. A yes/no column mixing the two grains is one
    label carrying two definitions — the defect that produced two different
    "Amount Over Budget" figures."""
    tree = ast.parse(_read(ROUTER))
    code = _code(_fn(tree, '_source_coverage'))
    m = re.search(r"'key':\s*'council_awards'.*?'grain':\s*'([a-z_]+)'", code, re.S)
    assert m and m.group(1) == 'budget_line', (
        'the Council awards row does not declare its grain')
    for other in ('cpdb_plan', 'dashboard', 'parks'):
        mm = re.search(r"'key':\s*'" + other + r"'.*?'grain':\s*'([a-z_]+)'",
                       code, re.S)
        assert mm and mm.group(1) == 'project', other

    # ⚠ AND THE PAGE MUST SHOW IT — the grain is served and then rendered as a
    # badge. This assertion followed the markup into the shared component; it is
    # the same property, one file over.
    comp = _rendered_copy(_read(PROVENANCE))
    assert "$c['grain'] ?? 'project') !== 'project'" in comp, (
        'the page renders every row identically, so the reader cannot see that '
        'the Council row is a different kind of claim')


def test_the_source_table_costs_no_extra_queries():
    """⭐ Every value is already in hand — three flags on the spine row and five
    panels the endpoint fetched to render the page. So the table cannot disagree
    with the sections it summarises, and a project page does not pay ten EXISTS
    against 259k- and 497k-row tables to draw it."""
    tree = ast.parse(_read(ROUTER))
    fn = _fn(tree, '_source_coverage')
    code = _code(fn)
    for banned in ('_select', 'await ', 'SELECT '):
        assert banned not in code, (
            f'_source_coverage runs its own query ({banned!r}) — it must read '
            f'only what the endpoint already fetched, or the table can disagree '
            f'with the sections above it')
    # It must be a plain def, not async — an async one would invite a query.
    assert isinstance(fn, ast.FunctionDef), '_source_coverage must not be async'


def test_the_page_renders_absent_sources_too():
    """A table that silently drops the "no" rows is the old behaviour with more
    steps."""
    # ⚠ The table moved into `<x-db.data-provenance mode="record">`; the property
    # is unchanged and this follows it there.
    comp = _rendered_copy(_read(PROVENANCE))
    assert re.search(r"@foreach\(\$rows as \$c\)", comp), (
        'the coverage table is gone')
    # ⚠ The sort must not FILTER. `usort` reorders; an `array_filter` on
    # `present` would drop exactly the rows this table exists to show.
    block = comp[comp.index('usort($rows'):comp.index('usort($rows') + 400]
    assert 'array_filter' not in block, (
        'the coverage rows are filtered before rendering, which drops the '
        'absences the table exists to show')
    assert re.search(r"\$c\['present'\]\s*\?\s*'Yes'\s*:\s*'Not published'", comp), (
        'an absent source does not render as absent')
    # ⚠⚠ AND THE PROFILE MUST STILL PASS ITS COVERAGE IN. A component rendered
    # with no data is an empty table, which is the defect with extra steps.
    view = _rendered_copy(_read(VIEW))
    assert re.search(r'<x-db\.data-provenance mode="record" :coverage="\$cov"', view), (
        'the profile no longer hands its source coverage to the component')


# ------------------------------------------------------- dataset row counts

def test_the_datasets_accordion_counts_server_side_and_fetches_nothing():
    """⚠⚠ `/get/pstats-records_no/{table}` HAS NEVER EXISTED — `git log -S` over
    the whole repo history finds no commit adding or removing it, and it 404s for
    every table. On a non-200 the caller ran `datasets.splice(i,1)`, so the page
    rendered six real dataset rows and then DELETED them."""
    php = _read(PROJECTS_CTRL)
    action = _php_method(php, 'projects')

    assert 'ProjectsDatasets::rowCounts()' in action, (
        'the action does not pass registry row counts, so the cells stay empty')
    assert '/get/pstats-records_no/tblname' not in action, (
        'the action still passes the URL of a route that does not exist')

    view = _rendered_copy(_read(PROJECTS_VIEW))
    assert 'loadTableStat' not in view, (
        'the page still calls the AJAX that deleted its own rows')
    assert 'datasets.splice' not in view, (
        'the page can still delete a dataset row when a request fails')
    # ⚠ And the sentence must be COMPUTED, not left to JS that no longer runs.
    # ⚠⚠ IT MOVED INTO `<x-db.data-provenance>` — the accordion is one shell now,
    # after fifteen views hand-rolled it. So the page must PASS the count in, and
    # the component must render it with `number_format`; asserting only the first
    # would pass against a component that ignored the value.
    assert re.search(r'<x-db\.data-provenance[^>]*:count="\$dsCount"', view), (
        'the page no longer hands its dataset count to the provenance component')
    assert re.search(r'<x-db\.data-provenance[^>]*:records="\$dsRecords"', view), (
        'the page no longer hands its record total to the provenance component')
    comp = _rendered_copy(_read(PROVENANCE))
    assert re.search(r'\{\{\s*number_format\(\$count \?\? 0\)\s*\}\}', comp), (
        'the dataset count is not rendered server-side')
    assert re.search(r'\{\{\s*number_format\(\$records \?\? 0\)\s*\}\}', comp), (
        'the record total is not rendered server-side')
    # ⚠ And nothing in the shell may fetch — that is the whole point of the move.
    assert 'loadTableStat' not in comp and 'fapireq' not in comp, (
        'the provenance component fetches, so a 404 can empty it again')
    # ⚠ (The `$dsRecords` echo moved into the component with the sentence; it is
    # asserted above, on both halves — the page passing it AND the component
    # rendering it.)


def test_a_missing_count_is_distinguishable_from_a_zero():
    """⚠ Three different facts — a known count, a table the registry does not
    track, and "we could not ask". The old markup had one state (an empty span),
    so all three read as zero."""
    php = _read(DATASETS)
    # ⚠ `public static` now, not `protected`: three classes render this cell —
    # `ProjectsDatasets`, `DistDatasets` and `SchoolDatasets` — and all three used
    # to emit a bare empty span. One owner, so the same defect cannot need three
    # fixes. The visibility is matched loosely on purpose; the PROPERTY asserted
    # below is the three states, not the keyword.
    m = re.search(r'(?:public static|protected) function countCell\(\$tbl, \$counts\)\s*\{(.*?)\n\t\}',
                  php, re.S)
    assert m, 'countCell is gone'
    body = m.group(1)
    assert '$counts === null' in body, (
        'an unreachable registry is not distinguished from a tracked table')
    assert 'array_key_exists' in body, (
        'a table the registry does not track is not distinguished from one it '
        'counts as zero')
    assert 'not tracked' in body

    # ⚠⚠ AND THE OTHER TWO CLASSES MUST DELEGATE, not re-emit an empty span. That
    # is what they did — `<span id="stats_{tbl}"></span>` waiting for an AJAX call
    # whose route does not exist — so their pages showed blank counters forever.
    for cls in ('DistDatasets', 'SchoolDatasets'):
        src = _read(os.path.join(ROOT, 'app', 'app', 'Custom', cls + '.php'))
        assert 'ProjectsDatasets::countCell' in src, (
            f'{cls} renders its own count cell again')
        assert not re.search(r"<span id=\"stats_'\s*\.[^,]*\.\s*'\"></span>", src), (
            f'{cls} still emits an empty count span for a fetch that never comes')

    # ⚠ `rowCounts` must degrade to [] rather than raising or returning null on
    # an unreachable registry — a failed request is not an empty dataset, and the
    # page has to keep rendering.
    r = re.search(r'public static function rowCounts\(\)\s*\{(.*?)\n\t\}', php, re.S)
    assert r, 'rowCounts is gone'
    assert 'reqOCE' in r.group(1) and '/pipeline/registry' in r.group(1)
    assert 'is_array' in r.group(1), (
        'rowCounts does not guard against a non-array response')


# ---------------------------------------------- layout, hiding, and the chart

def test_the_map_sits_in_the_right_hand_column():
    """Triage item 2. The previous project page put the map in a right-hand
    column (`orgproject.blade.php`: col-md-8 content + col-md-4 map, line 269);
    the rebuild had it full-width below the fold."""
    view = _rendered_copy(_read(VIEW))
    # The header row's right column must contain the map, and it must come
    # BEFORE the "where this project appears" card — top-right, not bottom-right.
    # ⚠⚠ THIS USED TO ANCHOR ON `<div class="card">` — the "Where this project
    # appears" card that sat under the map — and it fired when that card was
    # removed. The card said the same thing as the key-facts strip's source line
    # and the sources table, in a third place, so it went; the map staying
    # top-right did not change. The anchor is now the ROW ITSELF, so the guard
    # measures the map's position rather than its former neighbour.
    # ⚠ Owner review 2026-09-08: the strip is FULL WIDTH above this row (in a
    # 7/12 column its six tiles wrapped to two rows), and the map's row now pairs
    # it with About + Money on the left and puts "Where it is" BENEATH it —
    # one location facet in one place. This guard fired on that move, correctly,
    # and asserts the new row rather than the old neighbour.
    # ⚠⚠ THE ROW ENDS AT THE TOC, NOT AT THE FIRST `</div>` AT SOME INDENT. The
    # first draft's `(.*?)\n\t\t\t</div>` stopped at the About table's closer,
    # so the guard FAILED ON THE UNMUTATED FILE — and every mutation then read
    # as "fired". A guard that fails on the baseline fires on everything, which
    # is the inert-mutation trap wearing the other hat: three mutations reported
    # OK and none of them had been tested. Check the baseline is green FIRST.
    # ⚠ THE END ANCHOR MOVED, AND SO DID THE COLUMN WIDTHS. The TOC is now a
    # partial (it renders in one of two places depending on whether the project
    # HAS a map), so `<nav class="db-toc">` is no longer in this file at all —
    # the old anchor raised ValueError. `id="schedule"` is the first section
    # after the row and does not move.
    # ⚠ And the left column is now a ternary — `col-md-7` when there is a map,
    # `col-md-9` when there is not, because a map-less project rendered 848px of
    # About beside 848px of empty right column. The map's POSITION when one
    # exists is unchanged, which is what this guard is about.
    start = view.index('<div class="row mb-4 mt-3">')
    end = view.index('id="schedule"', start)
    row = view[start:end]
    assert 'id="map_container"' in row, (
        'the map is not in the about/map row — it is below the fold again')
    assert "$hasMap ? 'col-md-7'" in row, (
        'the left column no longer widens when there is no map')
    # ⚠ MATCH THE CLASS ATTRIBUTE, NOT A SUBSTRING. A mutation renaming the map
    # column to `col-md-5-moved` left this guard GREEN, because `col-md-5` is a
    # substring of it — the guard would have passed while the map sat in a
    # column no stylesheet defines.
    left, right = row.index("'col-md-7'"), row.index('class="col-md-5"')
    assert left < right < row.index('id="map_container"'), (
        'the map is not in the RIGHT-hand column of that row')
    # ⚠⚠ THIS ASSERTED `id="money"` TOO, AND FIRED WHEN THE MONEY SECTION WENT.
    # Correctly: the section is gone (owner, 2026-09-10) — its six figures are
    # the key-facts tiles above this row and its note and definitions are one
    # help block under them, so there is no `#money` heading left to be beside
    # the map. The property this guard is about is the map's COLUMN, and About
    # being the left one; naming a second neighbour was incidental to that, and
    # keeping it would forbid the change rather than protect anything.
    assert 'Managing agency' in row[left:right], (
        'About is not in the left column beside the map')
    assert 'id="where"' in row[right:], (
        '"Where it is" is not beneath the map — the two halves of the location '
        'facet are apart again')
    # And the strip is ABOVE the row, full width — not inside either column.
    # ⚠ `not in row`, NOT `index() < start`: the latter finds the FIRST grid,
    # which is the real one above the row, so a second grid smuggled into the
    # column was invisible to it — measured, that mutation did not fire.
    assert view.index('<x-db.stat-grid') < start, (
        'the key-facts strip is inside a column again, so its tiles wrap')
    assert '<x-db.stat-grid' not in row, (
        'a stat grid is inside the about/map row — in a 7/12 column its tiles '
        'wrap to two rows, which is what the full-width strip fixed')
    # And there is exactly ONE map container — a second would give mapbox two
    # elements with the same id and it would bind to the wrong one.
    assert view.count('id="map_container"') == 1, (
        'more than one #map_container on the page')


def test_an_empty_section_is_hidden_and_then_named():
    """⚠⚠ THIS REVERSES §5.3 ("every empty section renders its 'not published'
    line, not nothing"), and the reversal is only safe because the source table
    accounts for every source. The hidden sections are NAMED rather than silently
    dropped — a project outside the current plan otherwise rendered nine
    consecutive "not published" paragraphs, and the answer to that is one
    sentence, not silence.
    """
    view = _rendered_copy(_read(VIEW))
    # Every optional section goes through the same gate, so none can be hidden
    # without being recorded.
    # ⚠⚠ THIS USED TO READ `@if($show('Name'` AND IT FIRED WHEN THE CLOSURE WENT —
    # correctly, and the replacement is the point. `$show()` appended to
    # `$hidden` AS EACH SECTION RENDERED, so the "not shown for this project"
    # line could only be printed AFTER the last section: 9,000px below the fold,
    # where a reader who needs to know what is missing has already stopped
    # reading. It is a PRECOMPUTED MAP now, so the same list can be stated at the
    # top. The property — a hidden section is NAMED, never silently dropped — is
    # unchanged, which is what this still asserts.
    gated = re.findall(r"^\s*'([^']+)' => !empty\(", view, re.M)
    # ⚠⚠ `Scope` LEFT THIS SET ON 2026-09-10 AND THIS GUARD FIRED — correctly.
    # It became a FIELD in the About table at the owner's request, and a field
    # is not a section: an absent one renders an em dash in its own row like
    # every other attribute. Leaving it here would have named "Scope" in the
    # "Nothing published for:" sentence on every project the 2023 series never
    # carried — advertising a missing SECTION that no longer exists.
    # ⚠ Its VINTAGE did not go with it; see
    # `test_the_scope_field_keeps_the_citation_the_section_carried`.
    expected = {'Schedule', 'How the completion forecast has moved',
                'Budget and schedule over time', 'Planned commitments',
                'NYC Parks project tracker', 'Climate Budgeting ratings',
                'Milestones (2023)', 'Districts',
                'Other projects on the same budget line',
                'City Council capital awards'}
    assert set(gated) == expected, f'gate list drifted: {sorted(set(gated) ^ expected)}'

    # ⚠ `$show` must RECORD, not just return — a gate that only returns a bool
    # hides the section and loses the name, which is the §5.3 defect with extra
    # steps.
    # ⚠ `$hidden` must be DERIVED from that same map, not maintained separately —
    # two lists of the same thing is how a section comes to be hidden without
    # being named.
    m = re.search(r'\$hidden = ([^;]+);', view)
    assert m, '$hidden is no longer computed'
    assert '$sections' in m.group(1), (
        f'$hidden is not derived from the section map: {m.group(1).strip()}')

    # ⚠⚠ AND IT IS NAMED ABOVE THE FOLD NOW, NOT AT THE FOOT. Item F of the
    # design plan: the sentence moved into the key-facts strip, so the assertion
    # about WHERE it renders moved with it. Its property did not change.
    # ⚠⚠ THE NAMING IS SPLIT ACROSS TWO LISTS NOW, AND THIS GUARD FIRED WHEN IT
    # WAS — correctly. Rendering both unsubtracted printed the same two names
    # TWICE in one sentence ("Not published in: NYC Parks project tracker, City
    # Council capital awards. Nothing published for: NYC Parks project tracker,
    # City Council capital awards."), because `sources_absent` names
    # PUBLICATIONS and `$hidden` names SECTIONS and a section fed by exactly one
    # publication is the same words. So `$hiddenOnly` is the difference.
    # ⚠ THE PROPERTY IS THAT NOTHING HIDDEN GOES UNNAMED, and it now takes BOTH
    # halves to hold: subtracting without also printing `sources_absent` would
    # silently drop every section that has a one-to-one publication — which is
    # most of them, and precisely the §5.3 defect wearing a tidier sentence.
    assert re.search(r"\$hiddenOnly = array_values\(array_diff\(\$hidden,", view), (
        'the two name lists are not de-duplicated against each other')
    assert re.search(r'@if\(count\(\$hiddenOnly\)\)', view), (
        'the hidden sections are never named')
    assert "implode(', ', $hiddenOnly)" in view, (
        'the hidden section names are not printed')
    assert "implode(', ', $kf['sources_absent'])" in view, (
        'the absent PUBLICATIONS are not printed, so every section subtracted '
        'from $hiddenOnly is now named nowhere at all')
    # ⚠⚠ THE SENTENCE MOVED TO THE SOURCES SECTION (owner, 2026-09-10) AND THIS
    # ASSERTION MOVED WITH IT. It used to require the naming ABOVE the attribute
    # table, because the §5.3 defect was this text sitting 9,000px down a
    # 9,636px page with nothing else accounting for the absences. The page is
    # ~3,200px now, the TOC links straight to `Where these figures come from`,
    # and the coverage table it now sits beside names every source with its
    # version. So the property is no longer "as high as possible" — it is that
    # the naming sits WITH the accounting it belongs to, rather than orphaned
    # somewhere on the page.
    named = view.index("implode(', ', $hiddenOnly)")
    sources = view.index('id="sources"')
    provenance = view.index('<x-db.data-provenance mode="record"')
    assert sources < named < provenance, (
        f'the hidden sections are named at {named}, outside the sources '
        f'section ({sources}..{provenance}) — the one place on this page that '
        'accounts for what each publication does and does not carry')

    # ⚠ And the accounting must still be there — hiding without it is exactly
    # what §5.3 was guarding against.
    assert '$covRows' in view, (
        'sections are hidden and the source coverage table is gone — that is the '
        'defect §5.3 existed to prevent')


def test_the_slippage_series_is_one_named_publication():
    """⚠⚠ TWO SOURCES PUBLISH `forecast_completion` AND THEY ARE NOT THE SAME
    SERIES. Measured 2026-09-08: `dashboard` and `dash_sched` disagree on **371
    of 17,764** shared (project, period) pairs, and 4,609 periods carry a forecast
    in `dashboard` alone. Drawing both would put two 98%-identical lines on one
    chart and invite a reader to read the 2% as a finding about the project.

    `dash_sched` is chosen because it is the schedule-history publication and the
    only one carrying `variance_days` and `delay_reason`."""
    ns = _load({'_SLIP_SOURCE'})
    assert ns['_SLIP_SOURCE'] == 'dash_sched'

    tree = ast.parse(_read(ROUTER))
    code = _code(_fn(tree, '_slippage'))
    assert '_SLIP_SOURCE' in code, 'the series is no longer pinned to one source'
    assert 'h.get(\'source\') == _SLIP_SOURCE' in code, (
        'the slippage series does not filter to a single publication')
    # ⚠ No query — it reads the history rows the endpoint already fetched.
    for banned in ('_select', 'await ', 'SELECT '):
        assert banned not in code, f'_slippage runs its own query ({banned!r})'


def test_a_flat_forecast_is_not_drawn_as_a_story():
    """⚠ TWO DISTINCT FORECASTS, NOT TWO ROWS. A project republished unchanged
    across ten periods has a flat line and nothing to say; drawing it implies a
    story where there is none."""
    # ⚠ `_mdy_label` is in this set because `_slippage` CALLS it — the point
    # formatter moved to the endpoint so the page carries one date format. A
    # by-name loader silently NameErrors when the function under test grows a
    # dependency, which is what happened here; that is the loader working.
    ns = _load({'_slippage', '_period_label', '_PERIOD_SHAPE', '_MONTHS',
                '_SLIP_SOURCE', '_DAYS_PER_MONTH', '_mdy', '_mdy_label'})
    f = ns['_slippage']

    def h(period, fc, **kw):
        d = {'source': 'dash_sched', 'period': period, 'forecast_completion': fc}
        d.update(kw)
        return d

    flat = f([h('202305', '01/01/2030'), h('202309', '01/01/2030')])
    assert flat['available'] is False, 'an unmoved forecast must not be plotted'
    assert 'only one completion forecast' in flat['reason']

    none = f([{'source': 'dashboard', 'period': '202305',
               'forecast_completion': '01/01/2030'}])
    assert none['available'] is False, (
        'a forecast from the OTHER publication must not be drawn as this series')

    moved = f([h('202305', '01/01/2030'), h('202309', '07/01/2030', variance_days=181)])
    assert moved['available'] is True
    assert moved['points'][0]['months_later'] == 0.0
    assert moved['points'][1]['days_later'] == 181
    assert moved['direction'] == 'later'

    # ⚠ A forecast can move EARLIER, and the direction is NAMED rather than left
    # to the sign of a number under a heading that says "later".
    earlier = f([h('202305', '07/01/2030'), h('202309', '01/01/2030')])
    assert earlier['direction'] == 'earlier' and earlier['total_days'] < 0


def test_the_chart_sits_in_the_fixed_height_wrapper():
    """⚠⚠ #61, ALREADY PAID FOR ONCE. A `maintainAspectRatio:false` canvas
    outside `.db-chart-body` grows without bound and takes the page with it."""
    view = _rendered_copy(_read(VIEW))
    m = re.search(r'<div class="db-chart-body"><canvas id="slipChart">', view)
    assert m, 'the slippage canvas is not inside a fixed-height wrapper'
    assert 'maintainAspectRatio: false' in view, (
        'the chart no longer fills its wrapper — if this was removed on purpose, '
        'the wrapper requirement changes too')

    # ⚠ The page must DRAW the served points, never recompute them.
    assert re.search(r'var SLIP = \{!! json_encode\(\$slip\[.points.\]\) !!\}', view), (
        'the chart does not read the served points')
    assert 'p.forecast_completion' in view and 'p.delay_reason' in view, (
        "the tooltip drops the actual date or the City's stated reason, which is "
        "what makes the derived axis honest")


# ------------------------------------------------- the budget-line filter

def _call_args(fn_src, callee):
    """Every call to `callee` in `fn_src`, as the list of ARGUMENT EXPRESSIONS.

    ⚠⚠ THE ARGUMENTS, NEVER THE SIGNATURE. This repo has a filter that was
    declared as a parameter and then handed on as the literal `None` — the map
    ignored `has_location` for weeks while both signatures read correctly. A
    guard reading signatures cannot see that; a guard reading the expressions
    passed at the call site can.
    """
    out = []
    for n in ast.walk(ast.parse(fn_src)):
        if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == callee:
            out.append([ast.unparse(a) for a in n.args])
    return out


def test_the_map_and_the_list_are_both_handed_the_budget_line_filter():
    """⚠⚠ A FILTER THE LIST TAKES AND THE MAP DOES NOT MAKES THE MAP LIE.
    Measured on `has_location` before this section was rebuilt: the list showed
    12,464 projects with no published location while the map drew 4,560 pins,
    every one a project the list had excluded. `budget_line` is a membership
    filter of exactly that kind, so it has to reach `capital_geojson` too —
    including the endpoint's SECOND `_list_filters` call, which computes the
    total the legend renders.
    """
    tree = ast.parse(_read(ROUTER))
    seen = {}
    for name in ('capital_projects', 'capital_geojson'):
        calls = _call_args(_code(_fn(tree, name)), '_list_filters')
        assert calls, f'{name} makes no _list_filters call'
        seen[name] = calls

    # capital_geojson calls it TWICE — once for the mapped rows and once for the
    # unrestricted total. A filter reaching only the first understates the
    # legend's denominator, which reads as a smaller programme, not as a bug.
    assert len(seen['capital_geojson']) == 2, (
        'capital_geojson should build filters twice (features + total); got '
        f"{len(seen['capital_geojson'])}")

    for name, calls in seen.items():
        for i, args in enumerate(calls):
            assert 'budget_line' in args, (
                f'{name} call {i} does not forward budget_line: {args}')


def test_the_budget_line_filter_normalises_both_sides():
    """⚠⚠ NORMALISING ONLY THE CALLER'S VALUE IS THE RICHMOND DEFECT ON A NEW
    COLUMN — it looks careful and returns nothing. The spine stores `AG-D001`
    while a caller sends `AG D001`; the raw comparison matches 0 rows, and 0 is
    indistinguishable from "no projects on this line".

    The rule has ONE owner in `modules/budgetline`, so this reads the emitted
    SQL for the column side and the bound parameter's expression for the input
    side, rather than re-typing either — a guard that reimplements the thing it
    guards measures a different system.
    """
    tree = ast.parse(_read(ROUTER))
    code = _code(_fn(tree, '_list_filters'))

    add = [n for n in ast.walk(ast.parse(code))
           if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == 'add'
           and 'budget_lines' in ast.unparse(n)]
    assert len(add) == 1, f'expected one budget_lines clause, got {len(add)}'
    sql, param = ast.unparse(add[0].args[0]), ast.unparse(add[0].args[1])

    # COLUMN side: the SQL fragment must come from budgetline.sql_norm.
    assert 'budgetline.sql_norm' in sql, (
        f'the column side is compared raw, not through sql_norm: {sql}')
    # INPUT side: the bound value must come from budgetline.norm.
    assert 'budgetline.norm(' in param, (
        f'the input side is bound raw, not through budgetline.norm: {param}')
    # And it must be the CALLER'S value, not something else normalised.
    assert 'budget_line' in param, param

    # ⚠ `unnest`, not `&&`: the array holds the RAW spelling, so a set-overlap
    # test against a normalised value cannot match. `&&` here would read as an
    # index-friendly improvement and silently return nothing.
    assert 'unnest' in sql and '&&' not in sql, (
        f'the clause must unnest the raw array, not overlap it: {sql}')
