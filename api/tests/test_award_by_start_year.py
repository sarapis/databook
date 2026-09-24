"""Guards for the Overview's committed-money-by-start-year chart.

This chart replaced one that was wrong in three ways at once, and each of those
is a rule this codebase already paid for. The replacement can regress into any
of them, so each gets a guard:

1. ⚠⚠ IT BLENDED MASTER CEILINGS INTO "Awarded Amount". A master agreement's
   figure is headroom agencies buy against, drawn down under other contract ids
   — #261's rule, and #294 broke it once already on the renewal calendar
   ($3,802M against the queue's $3,637.6M for the same 690 contracts). Measured
   on this chart's own data 2026-08-22: 2023 carries $913.1M of ceiling and 2025
   $708.8M, so the tallest bars would be substantially money nobody has drawn.
2. ⚠ ITS WINDOW SILENTLY DROPPED ROWS. `2018 <= y <= 2030`, hardcoded, with no
   disclosure: 30 contracts / $162.0M were simply absent. A chart that quietly
   drops rows reads as the whole inventory.
3. ⚠ IT HAD NO ACTIVE/ENDED SPLIT, so it read as a live book while 3,655 of
   4,397 contracts had already ended.

And two structural traps:
4. the series stops closing to the tiles above it, silently (the 243-vs-242
   family — two independent computations of one number);
5. the controller stops passing the key, so the chart renders as nothing while
   every source-scanning guard still passes (the #247 seam).

⚠ Source scans here read AST STRING LITERALS, never the raw function text: this
file's own prose names the banned patterns, and eight guards in this repo have
fired on their own docstrings.
"""
import ast
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
OCE = os.path.join(ROOT, 'api/routers/oce.py')
OVERVIEW = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform.blade.php')
CTRL = os.path.join(ROOT, 'app/app/Http/Controllers/ProcurementController.php')
FN = '_award_by_start_year'


def _src(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _fn_node(name=FN):
    """The AST node for one nested function, found by walking the tree.

    ⚠ A text slice from `def name` to the next `def` would include whatever
    happens to follow; and this function is NESTED inside the endpoint, so a
    top-level-only search finds nothing.
    """
    tree = ast.parse(_src(OCE))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return node
    raise AssertionError(f"{name}() is gone — the guard cannot check what it "
                         f"cannot find")


def _code(node):
    """The function's CODE as text, with its docstring removed.

    ⚠⚠ THE TRAP THIS EXISTS FOR, hit while writing this file. `ast.unparse`
    includes the docstring, and this function's docstring cites the measured
    years ("2023 carries $913.1M", "2011-2019", "2026") — so a year-literal scan
    over the unparsed source fired on the PROSE explaining why hardcoded years
    are banned. That is the tenth own-prose guard failure in this repo, and the
    reason every scan here goes through this helper.
    """
    stripped = ast.parse(ast.unparse(node)).body[0]
    body = getattr(stripped, 'body', None) or []
    if body and isinstance(body[0], ast.Expr) \
            and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        stripped.body = body[1:]
    return ast.unparse(stripped)


def _assigned(node, name):
    """The unparsed right-hand side of a local `name = ...` assignment.

    The query interpolates predicates by VARIABLE (`{master}`), so the SQL text
    alone cannot show what they contain — reading the assignment is what makes
    the ceiling-split assertion real rather than a match on a variable name.
    """
    for n in ast.walk(node):
        if isinstance(n, ast.Assign) and any(
                getattr(t, 'id', '') == name for t in n.targets):
            return ast.unparse(n.value)
    return None


def _sql(node):
    """The SQL this function emits, with interpolations rendered INLINE as
    `{expr}` so the text can be parsed per aggregate.

    ⚠ The query is an f-string, so its text is split across JoinedStr parts. An
    earlier version joined the parts with newlines, which made
    `SUM({val}) FILTER (WHERE NOT ({master}))` unreadable as one expression —
    and that is precisely what let a mutation removing the master filter from
    `committed_active` pass every assertion below.
    """
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.JoinedStr):
            for part in n.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    out.append(part.value)
                elif isinstance(part, ast.FormattedValue):
                    out.append('{' + ast.unparse(part.value) + '}')
    return ''.join(out)


def _aggregate(sql, alias):
    """The text of the one aggregate expression ending `AS <alias>`.

    Anchors on the alias and walks BACK to the previous aggregate boundary, so
    each money column can be checked on its own terms rather than against the
    whole query — the difference between catching a dropped filter and not.
    """
    i = sql.find('AS ' + alias)
    assert i > 0, f"the {alias} aggregate is gone"
    head = sql[:i]
    start = max(head.rfind('COALESCE'), head.rfind('COUNT('))
    return sql[start:i]


def _view():
    """The Overview as it renders — includes expanded IN PLACE (bladeview.py).
    ⚠ The by-start-year chart lives in `contracts-book` / `contracts-book-js`,
    shared with the Contracts page, so the page's own file no longer holds it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'bladeview', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bladeview.py'))
    bv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bv)
    return bv.expand(OVERVIEW)


def _view_with_partials():
    """The Overview AND every partial it @includes, expanded IN PLACE.

    ⚠⚠ THE BLEND GUARD BELOW USED TO READ THE PAGE'S OWN FILE ALONE, AND THE PAGE
    REPRODUCED #294 FROM A PARTIAL (the storyboard's nine hand-typed bars all
    matched `committed + ceiling` to the dollar). So the page is read as it
    renders.
    ⚠ Since 2026-09-23 this is the same as `_view()`: the chart itself moved into
    `contracts-book`, which the Contracts page shares, and expanding IN PLACE
    (bladeview.py) keeps "is this statement before that one" meaningful — which
    is what an append-at-the-end concatenation could not.
    """
    return _view()


def _php_code(view):
    """Only the @php blocks and directives — where code lives, not prose."""
    return '\n'.join(re.findall(r'@php(.*?)@endphp', view, re.S))


# ------------------------------------------------------- 1. the ceiling split

def test_the_query_splits_committed_money_from_master_ceilings():
    """Regression 1. Committed money and ceilings must come back as SEPARATE
    aggregates, gated on contractkind's master test — never one SUM.

    ⚠ The predicate is interpolated by variable, so this reads the ASSIGNMENT
    (`master = contractkind.sql_is_master(...)`) rather than matching the
    variable's name in the SQL, which would pass against any expression.
    """
    node = _fn_node()
    master = _assigned(node, 'master')
    assert master and 'contractkind.sql_is_master' in master, \
        (f"the master test is not contractkind's own rule (got {master!r}), so "
         f"ceilings may be summed into committed money — #261/#294")
    sql = _sql(node)
    # ⚠⚠ PER AGGREGATE, not "somewhere in the query". Verified by reintroducing
    # the bug: dropping the master filter from `committed_active` alone left the
    # ceiling aggregate still using it, so a query-wide check PASSED while the
    # committed series silently included $3,337.4M of undrawn ceiling. That is
    # #294 exactly, and a whole-query assertion cannot see it.
    for alias in ('committed_active', 'committed_ended'):
        agg = _aggregate(sql, alias)
        assert re.search(r'NOT\s*\(\{master\}\)', agg), \
            (f"{alias} does not exclude master agreements, so ceilings are "
             f"being counted as committed money — #261/#294:\n  {agg.strip()}")
    ceiling = _aggregate(sql, 'ceiling')
    assert re.search(r'FILTER\s*\(WHERE\s*\{master\}\)', ceiling), \
        f"the ceiling aggregate no longer isolates masters:\n  {ceiling.strip()}"
    # And the ceiling must NOT also be filtered as committed — the mirror error.
    assert not re.search(r'NOT\s*\(\{master\}\)', ceiling), \
        "the ceiling aggregate excludes masters, so it can never be a ceiling"


def test_the_ceiling_is_never_added_to_committed_anywhere():
    """The key is named `ceiling` precisely so it resists being summed.

    ⚠ SCOPED TO THE ADDITION ITSELF, via the AST. My first draft regexed
    `committed.*\\+.*ceiling` over the whole function and fired on the
    reconciliation block, where a legitimate `committed_active + committed_ended`
    sum sits a few keys above an unrelated `'ceiling':` — the "scope a guard to
    the statement, not the word" lesson. Walking BinOp(Add) nodes cannot make
    that mistake.
    """
    node = _fn_node()
    offenders = []
    for n in ast.walk(node):
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
            sides = (ast.unparse(n.left), ast.unparse(n.right))
            joined = ' '.join(sides)
            if 'ceiling' in joined and 'committed' in joined:
                offenders.append(' + '.join(sides))
    assert not offenders, \
        ("a ceiling is added to committed money — #294's exact defect:\n  "
         + "\n  ".join(offenders))
    # The view must not do it either, in PHP or in the chart's JS.
    # ⚠ The test is "ceiling added to COMMITTED", not "ceiling ever added":
    # `$abyCeilTot += $y['ceiling']` is a legitimate ceiling-only total for the
    # disclosure sentence, and my first draft flagged it. Check per statement,
    # and only where BOTH words appear.
    # ⚠ ONE annotated escape hatch, capped — the `RAW-CONTRACTS-JOIN-OK` pattern.
    # Reconstructing the grand total to reconcile against `stats.total` (which
    # DOES count masters) is the single legitimate sum of the two; anything else
    # is #294. Capping the marker is what stops it becoming a habit.
    code = _php_code(_view_with_partials())
    marker = 'CEILING-PLUS-COMMITTED-OK'
    assert code.count(marker) <= 1, \
        (f"{code.count(marker)} uses of {marker} — it exists for the "
         f"reconciliation alone; a second use needs its own argument")
    # ⚠ The marker must sit WITHIN 6 LINES ABOVE the line it excuses — the same
    # proximity rule the raw-join hatch uses, because a marker floating at the top
    # of a file silences everything below it.
    lines = code.split('\n')
    for n, stmt in enumerate(lines):
        # ⚠ A `//` comment line is prose, not arithmetic: the storyboard's @php
        # block explains the #294 blend in words ("`committed + ceiling` TO THE
        # DOLLAR"), and reading every page as rendered put it in scope.
        if stmt.strip().startswith('//'):
            continue
        if '+' in stmt and 'ceiling' in stmt and 'committed' in stmt:
            excused = any(marker in l for l in lines[max(0, n - 6):n])
            assert excused, \
                (f"the view's PHP adds a ceiling to committed money (line {n}): "
                 f"{stmt.strip()}\nIf this is the reconciliation, annotate it "
                 f"with {marker} directly above.")
    view = _view_with_partials()
    assert not re.search(r'd\.ceiling\s*\+\s*d\.committed|'
                         r'd\.committed\w*\s*\+\s*d\.ceiling', view), \
        "the chart's JS adds a ceiling to committed money"


def test_the_chart_has_exactly_two_datasets_and_neither_is_the_ceiling():
    """⚠ The likeliest future regression is someone "completing" the chart by
    adding the ceiling as a third bar. The bar tracks committed only — #294's
    settled decision — so the dataset count is pinned."""
    view = _view()
    # Anchor from the `new Chart(...)` for THIS canvas to the next canvas's
    # Chart() call (or end of file) — the agency doughnut follows it, and a
    # brace-counting anchor is brittle against reformatting.
    start = view.find("new Chart(document.getElementById('digitalStartYearChart')")
    assert start > 0, "the chart's Chart() call is gone — re-anchor this guard"
    nxt = view.find("new Chart(", start + 10)
    body = view[start:nxt if nxt > 0 else len(view)]
    labels = re.findall(r"label:\s*'([^']+)'", body)
    assert len(labels) == 2, f"expected 2 datasets, found {len(labels)}: {labels}"
    for lb in labels:
        assert 'committed' in lb.lower(), \
            f"a dataset that is not committed money is being drawn: {lb!r}"
    # The ceiling may appear in the tooltip, never as chart data.
    data_lines = re.findall(r'data:\s*abyData\.map\(d => d\.(\w+)\)', body)
    assert set(data_lines) == {'committed_active', 'committed_ended'}, \
        f"the bars plot something other than committed money: {data_lines}"


def test_the_page_states_that_ceilings_are_excluded():
    """A reader cannot see the rule from the bars alone, so the page says it.
    #294's lesson was that two figures twenty inches apart disagreed silently."""
    view = _view()
    prose = re.sub(r'@php.*?@endphp', '', view, flags=re.S)
    assert re.search(r'ceilings? (are|is) not in the bars', prose, re.I) or \
        re.search(r'not included above', prose, re.I), \
        "the page never tells the reader that master ceilings are excluded"


# ------------------------------------------------- 2. no silent row dropping

def test_no_hardcoded_year_window():
    """Regression 2. The retired chart's `2018 <= y <= 2030` dropped 30
    contracts / $162.0M with no disclosure. Any reintroduced bound must be
    accompanied by a disclosure, so the simplest guard is: no year literals
    filtering the series at all."""
    node = _fn_node()
    src = _code(node)
    years = re.findall(r'\b(20[0-3]\d)\b', src)
    # A date FORMAT string ('MM/DD/YYYY') carries no year digits; a real bound does.
    assert not years, \
        (f"a hardcoded year bound is back in the series ({years}) — the retired "
         f"chart dropped 30 contracts this way, silently")


def test_rows_without_a_usable_start_date_are_counted_and_reported():
    """They must be MEASURED, not filtered away: 'nothing was dropped' and 'we
    never looked' are the same number otherwise. Currently 0 of 4,397 — and the
    payload says so, which is what makes the zero meaningful."""
    node = _fn_node()
    src = _code(node)
    assert 'unusable_start_date' in src, \
        "the payload no longer reports rows with no usable start date"
    sql = _sql(node)
    assert 'NOT {usable}' in sql or re.search(r'NOT\s+\{?usable', sql), \
        "nothing counts the rows the series excludes"
    view = _view()
    assert 'unusable_start_date' in view, "the view ignores the excluded rows"
    prose = re.sub(r'@php.*?@endphp', '', view, flags=re.S)
    assert re.search(r'no usable\s+start date', prose, re.I), \
        "the page never mentions rows excluded for want of a start date"
    # ⚠ And the zero case must SAY something, or a reader cannot tell a clean
    # dataset from an unreported one.
    assert re.search(r'nothing is omitted|every contract in scope', prose, re.I), \
        "when nothing is dropped the page should say so explicitly"


def test_the_year_in_progress_is_labelled_and_derived_from_the_clock():
    """Otherwise the newest bar reads as a collapse — or here, as a surge: 2026
    carries the largest committed figure of any year on only 61 contracts.
    ⚠ From the CLOCK, never max(year): a max()-based rule marks whatever the
    data ends on as complete."""
    node = _fn_node()
    src = _code(node)
    assert 'current_year' in src, "the payload no longer names the current year"
    assert 'datetime.now()' in src, \
        "the current year is not derived from the clock"
    assert not re.search(r'max\(\s*(y|year|years)', src), \
        "the current year looks derived from the data rather than the clock"
    view = _view()
    assert 'partial' in view.lower(), "the partial year is not labelled on the page"


# ---------------------------------------------- 3. the active/ended split

def test_the_series_carries_the_active_ended_split():
    """Regression 3, and the plan's explicit requirement. 3,655 of 4,397 have
    ended; every contract starting 2011-2019 has."""
    node = _fn_node()
    sql = _sql(node)
    assert 'n_active' in sql, "the series no longer counts active contracts"
    # ⚠ `ended` is interpolated by VARIABLE, so the rendered SQL shows only the
    # name — read the assignment, as the master-split guard does.
    ended = _assigned(node, 'ended')
    assert ended and 'end_date' in ended and 'CURRENT_DATE' in ended, \
        f"the ended test is gone from the series (got {ended!r})"
    view = _view()
    assert 'committed_active' in view and 'committed_ended' in view, \
        "the chart no longer renders the active/ended split"


def test_the_ended_test_matches_the_tiles_definition():
    """⚠ ONE definition of "ended" for the page. Two independent ones is how the
    licences page's two expiring figures came to disagree — so the series' test
    must be byte-identical to `_stats`'s."""
    tree = ast.parse(_src(OCE))
    def ended_literal(fn):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name == fn:
                for n in ast.walk(node):
                    if isinstance(n, ast.Assign) and any(
                            getattr(t, 'id', '') == 'ended' for t in n.targets):
                        return ast.unparse(n.value)
        return None
    a, b = ended_literal('_stats'), ended_literal(FN)
    assert a and b, f"could not find the ended predicate in both (_stats={a!r})"
    norm = lambda s: re.sub(r'\s+', ' ', s.replace("'", '"'))
    assert norm(a) == norm(b), \
        (f"the series defines 'ended' differently from the tiles:\n  "
         f"tiles:  {a}\n  series: {b}")


# ------------------------------------------------------- 4. it must close

def test_the_series_reconciles_instead_of_publishing_its_own_total():
    """⚠ The Overview computes nothing it can link to instead — this chart is the
    one exception, so it publishes a RECONCILIATION rather than a headline. Two
    independent computations of one number produced the 243-vs-242 defect."""
    node = _fn_node()
    src = _code(node)
    assert 'reconciles' in src, "the series no longer reports a reconciliation"
    view = _view()
    code = _php_code(view)
    assert 'reconciles' in code, "the view ignores the reconciliation"
    # And it must actually be COMPARED to the tiles, not merely displayed.
    assert re.search(r"stats\['count'\]", code), \
        ("the reconciliation is never compared against the tiles' own count, so "
         "a series that stops closing would render as if it were complete")
    # ⚠⚠ AND THE VALUE, not only the count. This is the defect that got through:
    # a NULL master test dropped 2 contracts / $2,500,000 out of every money
    # aggregate while COUNT(*) still counted them, so a count-only reconciliation
    # closed perfectly on a series that was $2.5M short. A tolerance is required
    # because the tile accumulates in float32 (~7e-7 off exact), but it must be
    # far tighter than the 2.4e-4 defect it exists to catch.
    assert re.search(r"stats\['total'\]", code), \
        ("the reconciliation never compares VALUE against the tile, which is the "
         "half that a dropped-row defect actually shows up in")
    tol = re.search(r'/\s*\$abyTot\s*<\s*([0-9.]+)', code)
    assert tol, "the value comparison has no tolerance — float32 makes == useless here"
    t = float(tol.group(1))
    assert 1e-6 < t < 2e-4, \
        (f"the value tolerance is {t}: it must exceed float32 noise (~7e-7) and "
         f"stay below the 2.4e-4 defect it exists to catch")
    # ⚠⚠ AND THE VALUE CHECK MUST BE CONSUMED, not merely computed. Verified by
    # reverting `$abyClose` to the count alone: every assertion above still
    # passed, because $abyCloseV was still being calculated — a value existing
    # says nothing about anything reading it (the org-chart-parent shape).
    decide = re.search(r'\$abyClose\s*=\s*([^;]+);', code)
    assert decide, "the close decision is gone"
    expr = decide.group(1)
    assert '$abyCloseN' in expr and '$abyCloseV' in expr, \
        (f"the close decision ignores one half: {expr.strip()!r} — a count-only "
         f"check is what let a $2.5M value loss render as complete")


def test_the_reconciliation_includes_the_excluded_rows():
    """A reconciliation that omits what the series dropped always closes, which
    makes it worthless. The contract count must add the unusable-start rows."""
    # ⚠ _code(), not ast.unparse(): the docstring mentions `reconciles` and a raw
    # find() landed inside the prose instead of the dict.
    src = _code(_fn_node())
    i = src.find('reconciles')
    assert i > 0, "the reconciliation is gone"
    tail = src[i:i + 400]
    assert 'contracts' in tail and ('u.get' in tail or 'unusable' in tail), \
        ("the contract reconciliation ignores rows excluded for want of a start "
         "date, so it closes by construction and proves nothing")


def test_the_retired_chart_key_is_a_marker_not_a_blended_number():
    """`charts.trend` summed ceilings into awarded value. It is retired to a
    marker (the `pipeline` precedent) so a consumer fails loudly rather than
    plotting a wrong figure — never left computing quietly."""
    src = _src(OCE)
    # ⚠⚠ EVERY site, not the first. This guard found a SECOND copy of the same
    # defective computation in the legacy /digital-reform/charts endpoint —
    # duplication is how it survived, since the live page reads /all and fixing
    # one copy left the other quietly serving blended ceilings.
    sites = [m.start() for m in re.finditer(r'\btrend = \{', src)]
    assert sites, "the trend key is gone entirely — was that deliberate?"
    for i in sites:
        assert 'moved_to' in src[i:i + 300], \
            (f"a trend series at offset {i} is being computed again instead of "
             f"pointing at its successor — check for a second copy")
    # No SQL may still build a by-year series outside the one owner.
    assert 'trend_query' not in src and 'trend_rows' not in src, \
        "a by-year trend query is still being executed somewhere"
    # And nothing may plot it any more.
    view = _view()
    assert 'chartData.trend' not in view, \
        "the Overview still plots the retired blended series"


# ------------------------------------------------------ 5. the failure state

def test_a_failed_query_degrades_the_section_and_raises_an_event():
    """⚠ Losing a whole section is ERROR (a Sentry event), not WARNING — #258.
    And the page must distinguish 'unavailable' from 'no contracts in scope':
    a silently missing chart looks like a broken feature."""
    node = _fn_node()
    src = _code(node)
    assert 'logger.error' in src, \
        "a failure here is logged below ERROR, so nothing alerts — #258"
    assert "'available': False" in src or '"available": False' in src, \
        "a failure does not mark the section unavailable"
    view = _view()
    prose = re.sub(r'@php.*?@endphp', '', view, flags=re.S)
    assert re.search(r'by-year view is unavailable', prose, re.I), \
        "the page has no distinct 'unavailable' state for this chart"
    assert re.search(r'nothing to chart|no technology contracts are in scope',
                     prose, re.I), \
        "the page cannot tell an empty universe from a failed query"


def test_the_php_block_is_assigned_before_the_script_reads_it():
    """⚠ THE $fragCount DEFECT: a variable read above its assignment renders as
    empty and looks like a measured zero.

    ⚠⚠ AND ITS PARTIAL-SCOPE TWIN (2026-09-23). The chart's markup and its JS now
    live in two partials (`contracts-book`, `contracts-book-js`) shared with the
    Contracts page, and an included view renders in ITS OWN SCOPE: a variable the
    markup partial assigns does not exist in the JS partial. Reading `$abyYears`
    there would render `[]` and draw no chart, silently. So the script must read
    the PAYLOAD KEY, which both partials receive from the page.
    """
    js_path = os.path.join(ROOT, 'app/resources/views/procurement/partials/contracts-book-js.blade.php')
    js = _src(js_path)
    assert "@json($awardByStartYear['years']" in js, \
        "the chart script no longer reads the served payload key"
    assert '@json($abyYears' not in js and '@json($abyCur' not in js, \
        ("the chart script reads a variable assigned in ANOTHER partial — it is "
         "out of scope there, so the chart renders empty")
    view = _view()
    assert view.find('$abyYears =') > 0, "the markup's @php block is gone"