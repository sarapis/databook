"""Guards on the capital index pages' charts, and on the string arithmetic that
broke two of them.

⚠⚠ THE DEFECT. Every money field in these payloads is a STRING — measured,
`'129000'` on all 749 rows of `/get/capitalbudget/bydate/recent` — so `0 + v`
CONCATENATES. On `/projects/budget-lines` that rendered a y-axis reading
**$7E141** and two pie legends reading **"undefined (NaN %)"** with no slices
drawn at all; on `/projects/commitments` the column headed "Total Commitment
Value" rendered **$634,158,196,199,885,056** for a budget line whose five years
total $22,266,000. Every row on that page was wrong.

⚠⚠ AND TWO SECOND DEFECTS THE FIRST ONE HID.
  * `/projects/budget-lines` plotted its four fiscal years BACKWARDS. `First
    Fiscal Year` is the first year of the window, so FY1 belongs to it and
    FY2-4 to the three AFTER; the view mapped FY4 to `First - 3`. Measured, the
    totals are FY1 $29.1B -> FY4 $15.9B — a declining forward forecast, drawn as
    a steep rise.
  * `/projects/commitments` summed FOUR of five years under a header saying
    "Total". 867 of 5,074 rows carry a fifth, worth **$34.4B**.

⭐ THE CHARTS ARE DERIVED FROM THE TABLE'S FILTERED ROWS, which is the property
these guards exist to keep. Each page serves several publication vintages in one
payload — 531 rows over 8 vintages on `/projects/types`, 1,617 over 8 on
`/projects/categories`, 5,074 over 3 on `/projects/commitments` — so charting
the payload would add every vintage together, and two of those vintages are the
ones this repo records as ingested wrong. Verified live: chart total == table
total to the dollar on four charts across two pages.
"""
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROOT = os.path.realpath(os.path.join(API, '..'))
VIEWS = os.path.join(ROOT, 'app', 'resources', 'views')
HELPER = os.path.join(ROOT, 'app', 'public', 'js', 'db-table-charts.js')

CHART_PAGES = ['prjTypesA.blade.php', 'categoriesA.blade.php',
               'prjCommitmentsA.blade.php']


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _no_comments(src):
    """Blade and JS comments gone — own-prose firings stand at 24 in this repo,
    and the comment beside each of these fixes quotes the strings scanned for."""
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$', '', src)


# ================================================== the string arithmetic

def test_no_view_adds_a_money_field_without_coercing_it_to_a_number():
    """⚠⚠ `+` ON TWO STRINGS CONCATENATES, AND EVERY AMOUNT HERE IS A STRING.

    The scan is for the PATTERN, not for the two sites that were broken — that
    is the lesson the pagination clamp already paid for, where a guard written
    for three known sites found three more.
    """
    offenders = []
    for name in CHART_PAGES + ['budgetLinesA.blade.php']:
        src = _no_comments(_read(os.path.join(VIEWS, name)))
        # `r['… Amount']` or `r['yr…']` used as an operand of `+` with nothing
        # coercing it. `num(...)`/`Number(...)` wrap it when correct.
        for m in re.finditer(r"[+]\s*(r\[[^\]]*(?:Amount|total|amt|cost)[^\]]*\])",
                             src, re.I):
            offenders.append('%s: + %s' % (name, m.group(1)))
        for m in re.finditer(r"(r\[[^\]]*(?:Amount|total|amt|cost)[^\]]*\])\s*[+]",
                             src, re.I):
            offenders.append('%s: %s +' % (name, m.group(1)))
    assert not offenders, (
        'these add a payload field straight, and every money field in these '
        'payloads is a STRING — `+` concatenates them: %r' % offenders)


def test_the_commitment_total_covers_every_fiscal_year_the_plan_presents():
    """⚠ A column headed "Total Commitment Value" that sums four of five years
    is not a total. `Number of Years Presented` is 4 or 5, and the fifth year is
    $34.4B across 867 of 5,074 rows.
    """
    src = _no_comments(_read(os.path.join(VIEWS, 'prjCommitmentsA.blade.php')))
    tot = [l for l in src.splitlines() if 'Total' in l or
           ("Fiscal Year 1 Amount" in l and "Fiscal Year 4 Amount" in l)]
    body = '\n'.join(tot)
    for i in range(1, 6):
        assert "Fiscal Year %d Amount" % i in body, (
            'the total omits fiscal year %d — a column calling itself the total '
            'must cover every year the plan presents' % i)
    # And the fifth year must be a COLUMN, so the total is checkable by adding
    # up the row rather than taken on trust.
    heads = re.findall(r'<th scope="col">([^<]+)</th>', src)
    assert 'Fiscal Year 5 Amount' in heads, (
        'the fifth year is inside the total but not shown, so the visible '
        'columns do not add up to it: %r' % heads)


def test_the_budget_line_years_run_forwards():
    """⚠⚠ `First Fiscal Year` IS THE FIRST YEAR OF THE WINDOW, so FY1 belongs to
    it and FY2-4 to the three AFTER it. Mapping FY4 to `First - 3` ran the
    window backwards and drew a declining forecast (FY1 $29.1B -> FY4 $15.9B) as
    a steep rise.
    """
    src = _no_comments(_read(os.path.join(VIEWS, 'budgetLinesA.blade.php')))
    assert not re.search(r"\['First Fiscal Year'\]\s*-\s*\d", src), (
        'a fiscal year is still being placed BEFORE the window\'s first year')
    assert re.search(r'y0\s*\+\s*3', src), (
        'the fourth fiscal year is no longer placed three years after the first')


# ================================================== the charts follow the table

def test_every_chart_is_bound_to_its_table_not_to_the_payload():
    """⚠⚠ THE PAYLOAD CARRIES EVERY PUBLICATION VINTAGE AT ONCE. `/projects/types`
    serves 531 rows over 8 vintages for 37 types; charting it whole adds eight
    publications of the same strategy together. Two of those vintages are the
    ones this repo records as ingested wrong, so the error is not even uniform.
    """
    for name in CHART_PAGES:
        src = _no_comments(_read(os.path.join(VIEWS, name)))
        m = re.search(r'DBTableCharts\.bind\(\s*([A-Za-z_$][\w$]*)', src)
        assert m, '%s: the charts are not bound through DBTableCharts' % name
        assert m.group(1) == 'table', (
            '%s: the charts are bound to %r, not to the DataTable — they no '
            'longer follow the page\'s own filters' % (name, m.group(1)))


def test_the_helper_reads_the_filtered_rows():
    src = _no_comments(_read(HELPER))
    assert "rows({search: 'applied'})" in src, (
        'the helper no longer reads the table\'s FILTERED rows, so a chart can '
        'disagree with the table beside it')
    assert re.search(r"\.on\('draw'", src), (
        'the charts no longer redraw when the table does, so changing a filter '
        'moves the table and leaves the charts behind')


def test_the_helper_coerces_every_value_to_a_number():
    """⚠ The helper is where the aggregation happens, so it is where the string
    defect would return."""
    src = _no_comments(_read(HELPER))
    assert re.search(r'function num\(v\)\s*\{[^}]*Number\(v\)', src), (
        'the helper no longer coerces, so a string payload concatenates again')
    assert re.search(r'acc\[k\]\s*=\s*\(acc\[k\]\s*\|\|\s*0\)\s*\+\s*num\(', src), (
        'the accumulator adds a raw value')


def test_a_capped_chart_accounts_for_what_it_capped():
    """⚠ This repo has shipped "top 25 of 88" presented as the whole set more
    than once. A capped chart folds the remainder into one labelled slice, which
    is why every chart's total equals its table's total exactly.
    """
    src = _no_comments(_read(HELPER))
    assert 'spec.top' in src and 'restLabel' in src, (
        'the cap no longer folds a remainder, so a top-10 chart silently drops '
        'everything below it')
    assert re.search(r'pairs\.slice\(spec\.top\)\.reduce', src), (
        'the remainder is not summed')


def test_a_truncated_label_cannot_collide_with_another():
    """⚠ Cutting at 23 characters rendered "Department of Environmental
    Protection" and "Department of Environmental Remediation" as ONE string, so
    the chart showed two bars with the same name. The END is what distinguishes
    them in every one of these vocabularies.
    """
    src = _no_comments(_read(HELPER))
    m = re.search(r'function shorten\(v\)\s*\{(.*?)\n  \}', src, re.S)
    assert m, 'the label shortener is gone'
    assert 's.slice(-' in m.group(1), (
        'the shortener drops the END of the label, which is the part that '
        'distinguishes these names from each other')


# ================================================== the two copy changes

def test_the_publication_date_note_is_behind_a_working_help_control():
    """⚠⚠ THE `?` ON `/projects/types` SHOWED NOTHING, so moving the note behind
    it was first a question of making it work. Measured before the change:
    `initPopovers()` is called from exactly ONE place in `script.js`, inside the
    MAP's click handler, so on a page with no map it never runs; the `<th>`
    carried no `data-toggle` and clicking produced **0** popovers.

    ⚠⚠ AND `initPopovers()` MUST NOT BE CALLED GLOBALLY TO FIX IT — it binds
    every `[data-content]`, and `data-content` is also the DataTables SORT KEY
    on every money cell in this section. Bootstrap 5's own `data-bs-content` is
    used instead, which cannot collide with that.

    ⭐ Safe behind a click because the load-bearing half survives outside it:
    all three affected columns render a visible `2023 series` label in their own
    headers, so a reader who changes the vintage and sees those three sit still
    is told why by the table itself.
    """
    src = _no_comments(_read(os.path.join(VIEWS, 'prjTypesA.blade.php')))
    assert 'data-bs-content=' in src, (
        'the publication-date note is no longer in a Bootstrap 5 popover')
    assert 'Capital Projects Dollars Comparison' in src, 'the note itself is gone'
    assert 'bootstrap.Popover' in src, (
        'nothing initialises the popover, so the help control shows nothing — '
        'which is the state this replaced')
    assert 'initPopovers()' not in src, (
        'initPopovers binds every [data-content], and that attribute is the '
        'DataTables sort key on this section\'s money cells')
    # The three columns must still carry their own visible series label, or the
    # note has become the only place the warning lives.
    # ⚠ COUNTED IN THE TABLE HEADERS ALONE. A whole-file count also sees the
    # popover's own copy, so removing ONE column label still left three matches
    # and the guard passed against it.
    heads = re.findall(r'<th[^>]*>(.*?)</th>', src, re.S)
    labelled = [h for h in heads if '2023 series' in h]
    assert len(labelled) >= 3, (
        'only %d table headers carry the 2023-series label — the caveat is now '
        'ONLY behind a click' % len(labelled))


def test_the_about_page_does_not_cite_a_map_it_does_not_have():
    """⚠ Removed on owner request, and it was fossil: `/projects/about` has no
    map at all — no `mapboxgl`, no `#map_container`, no `<canvas>`, measured on
    the rendered page. It cited two CPDB geometry datasets for a map that lives
    on other pages, which still cite them.
    """
    src = _no_comments(_read(os.path.join(VIEWS, 'capital.blade.php')))
    assert 'Our map uses data from' not in src, (
        'the page cites a map it does not have')
    assert 'mapboxgl' not in src and 'map_container' not in src, (
        'this page has a map now, so the citation it used to carry needs to '
        'come back rather than stay deleted')


# ================================ the budget-lines chart row (owner, 2026-09-11)

def test_the_funding_source_pie_is_gone_from_markup_and_from_js():
    """⚠⚠ REMOVING A CANVAS WITHOUT ITS `new Chart(...)` BREAKS THE WHOLE PAGE.
    `new Chart(null, …)` throws "can't acquire context from the given item", and
    that call sits inside this view's `$(document).ready`, so every function on
    the page would be undefined while the page still returned 200 — the exact
    failure this view has shipped before.

    ⚠ `stats['byfund']` is deliberately still COMPUTED: the line chart beside it
    plots the same four sources across four fiscal years, so nothing about
    funding is lost. The removed pie showed the first year's split, which is
    that chart's 2027 point.
    """
    src = _no_comments(_read(os.path.join(VIEWS, 'budgetLinesA.blade.php')))
    assert 'byFundSourceChart' not in src, (
        'the funding-source chart is back in some form: a leftover canvas or a '
        'leftover Chart call')
    assert 'chart2' not in src, 'a dangling chart2 reference remains'
    # ⚠ THE ACCUMULATION, NOT THE MENTION. `'byfund'` also appears in the
    # reducer's seed object and in the `stats = {…}` reshape, so a bare
    # containment check stayed GREEN against a mutation that deleted the line
    # actually summing into it.
    assert re.search(r"a\['byfund'\]\[t\]\s*=[^\n]*\+\s*n\(", src), (
        "nothing accumulates into stats['byfund'] any more — the line chart's "
        'four source series are built from it')


def test_the_project_type_legend_and_pie_are_a_flex_pair():
    """⚠⚠ THE LEGEND IS AN UNSIZED INLINE-BLOCK and its longest row is "WATER
    MAINS, SOURCES AND TREATMENT: $1.06B (3.6 %)". In the ~400px column it used
    to share with the funding-source pie, that did not fit beside a 285px
    canvas, so the pie wrapped BELOW its own legend — what the owner reported.

    ⚠ Widening the column alone is NOT what holds this: with the third chart
    gone, a bare `col` auto-fills the same width, so that mutation is inert. The
    flex row is the thing that makes it structural, and it is what the rendered
    check in `verify_bl_index.py` falsifies.
    ⚠ `flex-wrap` is the narrow-screen half: at 390px there is no room for both
    and they must wrap rather than force the page sideways.
    """
    src = _no_comments(_read(os.path.join(VIEWS, 'budgetLinesA.blade.php')))
    # ⚠ ANCHORED ON THE MARKUP, NOT THE FIRST MENTION. `byPrgTypeChart` appears
    # first in `getElementById("byPrgTypeChart")` up in the script block, so
    # `index()` found the JS and this guard failed on a correct file. Fourth
    # wrong-occurrence anchoring this repo has paid for.
    m = re.search(r'<div class="col-md-\d+ byPrgTypeChart">', src)
    assert m, 'the project-type chart column is gone'
    block = src[m.start():m.start() + 1400]
    assert 'display: flex' in block, (
        'the legend and the pie are no longer a flex row, so the pie can wrap '
        'below its own legend')
    assert 'flex-wrap: wrap' in block, (
        'the pair cannot wrap, so a narrow screen scrolls sideways instead')
    assert re.search(r'flex:\s*0\s+0\s+285px', block), (
        'the canvas no longer keeps its declared 285px, so it competes with the '
        'legend for width')
    assert 'position: absolute' not in block, (
        'absolute positioning is back in this row — with no positioned ancestor '
        'it resolves against the VIEWPORT, which is how both pies once landed '
        'in one box and the page scrolled 40px sideways')


# ================================================== the value axis's rotation

def _balanced(src, start):
    """The `{...}` beginning at `start`, brace-matched.

    ⚠ `\\{[^}]*\\}` would stop at the first inner `}`, so a branch that grows a
    callback function would read as truncated and the guard would silently
    measure half of it.
    """
    assert src[start] == '{', src[start:start + 40]
    depth = 0
    for i in range(start, len(src)):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError('unbalanced braces from %r' % src[start:start + 40])


def _x_ticks_branches(src):
    """The two branches of the x scale's `ticks:` ternary, (horizontal, vertical).

    ⚠ Anchored on the `x:` SCALE, not on the first `spec.horizontal` in the file
    — `indexAxis`, the tooltip callback and the y scale each test it too, and
    anchoring on any of those would read a different object.
    """
    m = re.search(r'\n\s*x:\s*\{', src)
    assert m, 'the x scale is gone from the helper'
    x_block = _balanced(src, m.end() - 1)
    t = re.search(r'ticks:\s*spec\.horizontal\s*\?\s*\{', x_block)
    assert t, "the x scale's ticks no longer branch on spec.horizontal"
    horiz = _balanced(x_block, t.end() - 1)
    rest = x_block[t.end() - 1 + len(horiz):]
    v = re.search(r':\s*\{', rest)
    assert v, 'the x ticks ternary has no else branch'
    vert = _balanced(rest, v.end() - 1)
    return horiz, vert


def test_both_x_tick_branches_cap_the_label_rotation():
    """⚠⚠ ON A HORIZONTAL BAR THE X AXIS IS THE VALUE AXIS, AND ITS BRANCH HAD
    NO `maxRotation`.

    Chart.js defaults to `maxRotation: 50` and rotates whenever the tick count
    it chooses does not fit the width, so at the ~408px three charts leave,
    `$0 $10.0B $20.0B $30.0B $40.0B $50.0B` rendered on a ~30 degree slant.

    ⚠ Measured, WHICH chart slants moves with the viewport — 1440 put `tyByTen`
    and `caByTen` at 29.8 degrees, 1024 put `tyByTen` and `caByYr1` at 27.3 while
    `caByTen` straightened — because it depends on the ticks Chart.js happens to
    pick. So this is not a property of one page and the fix is not on one page.

    ⚠⚠ THE GUARD READS THE HORIZONTAL BRANCH SPECIFICALLY. A scan for
    `maxRotation: 0` anywhere in the helper PASSES against the exact defect,
    because the vertical branch has carried it all along — the fixed-one-branch
    shape this repo already records for `_cached` in nycha.py and for
    `fapireq`'s error branch.
    """
    horiz, vert = _x_ticks_branches(_no_comments(_read(HELPER)))
    for name, branch in (('horizontal', horiz), ('vertical', vert)):
        m = re.search(r'maxRotation:\s*(\d+)', branch)
        assert m, (
            'the %s x-tick branch sets no maxRotation, so Chart.js falls back '
            'to 50 and slants the axis whenever its ticks do not fit: %s'
            % (name, branch[:120]))
        assert m.group(1) == '0', (
            'the %s x-tick branch allows %s degrees of rotation'
            % (name, m.group(1)))


def test_only_the_category_axis_refuses_to_skip_ticks():
    """⚠ `autoSkip: false` belongs on the CATEGORY axis and must not spread to
    the value axis.

    Skipping a category HIDES a bar's name; skipping a value tick only removes a
    number from a scale whose gridlines stay and whose exact figure is in the
    tooltip. That asymmetry is what lets the value axis cap rotation without
    colliding labels — with `autoSkip: false` AND `maxRotation: 0` it would
    overlap them instead, which is worse than a slant.
    """
    src = _no_comments(_read(HELPER))
    horiz, vert = _x_ticks_branches(src)
    assert 'autoSkip' not in horiz, (
        'the horizontal x axis is the VALUE axis; refusing to skip its ticks '
        'makes capped rotation overlap them instead of dropping one')
    assert re.search(r'autoSkip:\s*false', vert), (
        'the vertical x axis is the CATEGORY axis and skipping hides a bar')
    y = re.search(r'\n\s*y:\s*\{', src)
    assert y, 'the y scale is gone'
    y_block = _balanced(src, y.end() - 1)
    yt = re.search(r'ticks:\s*spec\.horizontal\s*\?\s*\{', y_block)
    assert yt, "the y scale's ticks no longer branch on spec.horizontal"
    assert re.search(r'autoSkip:\s*false', _balanced(y_block, yt.end() - 1)), (
        'on a horizontal bar the y axis is the CATEGORY axis and skipping '
        'would hide a project type')
