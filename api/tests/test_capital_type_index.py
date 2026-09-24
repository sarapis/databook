"""`/projects/types` — the Project Types index, and the three columns it takes
from the series NYC retired.

⚠⚠ THE DEFECT: A MIXED ROW, WITH NOTHING SAYING SO. Seven columns come from the
Ten-Year Capital Strategy at the vintage the Publication Date control selects
(2025-05-01 by default). Three — `Projects`, `Original Budget`, `Current Budget`
— come from `capitalprojectsdollarscomp`, which NYC last published **2023-10-26**
and has since retired, and they do NOT move with that control. Measured on the
live page 2026-09-10.

⚠⚠ AND FIVE OF THE THIRTY-SEVEN ROWS PUBLISHED "0 projects / $0 / $0", among them
**Department of Education** and **Department of Transportation - Equipment**. The
endpoint LEFT JOINs and `COALESCE(..., 0)`s, and a matched group counts DISTINCT
project ids so it can never be 0 — so `0` means "the join found no row", and a
rendered `$0` is a claim the City did not make. Verified across all 531 rows:
`pnum == 0` and money `== 0` agree on every one, **0 disagreeing**.

⚠ THEY CANNOT BE REPOINTED AT THE SPINE, which is why the treatment is a label
and not a migration. `capitalstrategy` has **no project key at all**, and the
spine's own `project_types` is a different 39-value dimension (deduplicated
budget-line families) whose overlap with the strategy's work types is **5, every
one a coincidence**. `/get/pstats-categories_by_type` records the same three
columns being DROPPED from the per-TYPE page; there the join was on
(publication date, CATEGORY), so it attributed a whole category's projects to
one type and two thirds of its rows read zero. Here the join is on the type name
and 32 of 37 rows carry a real figure, so the honest treatment is the one the
org capital tab's union tiles and its alt-union table already use: label the
series the figures come from.

⚠ The alternative — dropping the three columns, as the type page did — is a
live option and would need no new code. It is not taken here because it removes
information from a published page, which is the owner's call; labelling is the
smaller, reversible change that stops the page implying one vintage.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'prjTypesA.blade.php')
MAIN = os.path.join(ROOT, 'api', 'main.py')

RETIRED_COLUMNS = ('pnum', 'budg_cost', 'curr_cost')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _code_only(text):
    """⚠ Blade, block and line comments all stripped. This view's own comments
    now explain that `0` means no match, that the columns come from the retired
    series and that `Difference` was deleted — so they contain every string the
    guards below search for. Own-prose firings in this repo stand at 23; running
    each of these against the unmutated file is what keeps this from being 24.
    """
    text = re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'^\s*//.*$', '', text, flags=re.M)


def _js_function(text, name):
    """One JS function's body, by balanced braces — scoped, so a guard cannot be
    satisfied by a mention somewhere else in a 180-line script block."""
    code = _code_only(text)
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


def _headers(text):
    """The `<th>` cells of the index table, in order."""
    i = text.index('<table id="prjsTypes"')
    thead = text[i:text.index('</thead>', i)]
    return re.findall(r'<th[^>]*>(.*?)</th>', thead, flags=re.S)


def test_each_retired_series_column_is_labelled_with_its_series():
    """⚠⚠ THE READER FORMS A ROW FROM ADJACENCY (invariant 9). Seven columns move
    with the Publication Date control and three do not; without the label the row
    reads as one vintage. The label is in the HEADER, not a footnote alone,
    because a caveat a column does not carry is a caveat read after the number.
    """
    heads = _headers(_read(VIEW))
    wanted = ('Projects', 'Original Budget', 'Current Budget')
    for w in wanted:
        cell = next((h for h in heads
                     if re.sub(r'<[^>]+>', ' ', h).split()[:len(w.split())]
                     == w.split()), None)
        assert cell is not None, 'the %s column is gone from the index' % w
        assert '2023 series' in cell, (
            'the %s column no longer says which series it comes from — it does '
            'not move with the Publication Date control beside it' % w)


def test_amount_over_budget_is_not_reproduced():
    """⚠⚠ INVARIANT 11. The index carried a `Difference` column rendering
    `budg_cost - curr_cost`, which IS `Amount Over Budget` — the label this
    section documents as carrying two definitions and reproduces nowhere. It was
    `visible: false` and the page renders no colVis button, so it was unreachable
    dead config; the answer for that here is delete, not leave it inert."""
    view = _code_only(_read(VIEW))
    assert 'Difference' not in view, (
        'the Difference column is back on the type index — it is Amount Over '
        'Budget under another name')
    assert not re.search(r'budg_cost.*?-.*?curr_cost', view), (
        'the index computes the budget difference again')


def test_a_missing_retired_row_renders_an_em_dash_and_never_a_zero():
    """⚠⚠ INVARIANT 7 — a number, `0` and `—` are three different claims. Five of
    the 37 rows on the default vintage have no row in the retired series, and
    they published "0 projects / $0 / $0" for real programmes including the
    Department of Education.

    ⚠ ONE OWNER for all three cells, so the rule cannot hold for two columns and
    not the third.
    """
    view = _read(VIEW)
    body = _js_function(view, 'retired')
    assert 'n === 0' in body or 'n == 0' in body, (
        'retired() no longer treats 0 as "the join found no row", so a type with '
        'no retired-series match publishes 0 projects and $0 again')
    assert '\\u2014' in body or '—' in body or '&mdash;' in body, (
        'retired() no longer renders an em dash for an unknown value')
    code = _code_only(view)
    for col in RETIRED_COLUMNS:
        assert re.search(r"data:\s*'%s'.*?retired\(" % col, code, flags=re.S), (
            'the %s column does not go through retired(), so its unknowns are '
            'not em dashes' % col)


def test_the_retired_series_columns_carry_a_numeric_sort_key():
    """⚠⚠ A CELL WHOSE VISIBLE TEXT IS NOT MONOTONIC IN ITS VALUE NEEDS A SORT
    KEY. `type: 'html'` strips the tags and compares STRINGS, so
    `$1,351,983,000` sorted above `$296,902,000` — already true of the two money
    columns before the em dash existed, and wrapping the count in markup would
    have taken `Projects` from a correct numeric sort to the same string compare.

    ⭐ Verified by CLICKING each header on the rendered page rather than reading
    the config: descending gives $17.0B, $16.5B, $15.5B and 1,467 / 452 / 374.
    """
    code = _code_only(_read(VIEW))
    i = code.index('columns: [')
    cols = code[i:code.index('],', i)]
    for col in RETIRED_COLUMNS:
        m = re.search(r"\{data:\s*'%s'.*?\}\}" % col, cols, flags=re.S)
        assert m, 'the %s column definition changed shape' % col
        d = m.group(0)
        assert "type: 'html'" not in d, (
            "the %s column is back on type:'html', which compares its display "
            'text as a string' % col)
        assert 'parseFloat' in d and "=== 'display'" in d, (
            'the %s column no longer returns a raw number for non-display '
            'requests, so it sorts on its rendered text' % col)


def test_the_footnote_names_the_series_and_what_an_em_dash_means():
    """⚠ IT USED TO READ "* The most recent publications might not offer project
    data." — true, vague, and silent about WHICH columns and WHICH publication.
    It read as a caveat about freshness when the point is that three columns come
    from a different publication that NYC stopped issuing.
    """
    view = _read(VIEW)
    # ⚠ RE-EXPRESSED 2026-09-11, not relaxed. The note used to sit in a `<td>`
    # UNDER the control, so the guard read the 1,600 characters after
    # `id="pub_date_filter"`. The owner asked for it behind the control's help
    # icon, so it is now that icon's popover content — which sits BEFORE the
    # filter cell, not after it. The property is unchanged: the same three
    # things must still be said where the control is.
    m = re.search(r'data-bs-content="([^"]*)"', view)
    assert m, 'the publication-date help control has no content'
    note = m.group(1)
    for phrase in ('2023 series', '2023-10-26', 'em dash'):
        assert phrase in note, (
            'the publication-date note no longer says "%s", so the reader '
            'cannot tell which columns the control moves' % phrase)
    # ⚠ And it must be REACHABLE. A popover nothing initialises shows nothing —
    # which is exactly the state this page was in before, and moving the note
    # into a dead control would have deleted it.
    # ⚠ THE CONSTRUCTION, NOT THE NAME. `window.bootstrap.Popover` also appears
    # in the `if` that guards the call, so asserting the name stayed green
    # against a mutation that deleted the call itself.
    assert re.search(r'new\s+window\.bootstrap\.Popover\s*\(', view), (
        'nothing initialises the popover, so the note reaches no reader')


def test_the_endpoint_still_coalesces_the_join_to_zero():
    """⚠ THE VIEW'S RULE DEPENDS ON THIS. `retired()` reads `0` as "no match",
    which is only sound because the endpoint LEFT JOINs and COALESCEs to 0 and a
    matched group counts DISTINCT ids (so it is never 0). If the endpoint ever
    served NULL instead, `parseFloat(null)` is NaN and the em dash still renders
    — but if it ever served a genuine zero for a matched type, the view would
    call it unknown. Pinned so that change cannot pass unnoticed.
    """
    src = _read(MAIN)
    i = src.index("async def get_capital_projects_taxonomy_all")
    body = src[i:src.index('@app.get', i + 10)]
    assert 'COALESCE(MAX(p.prjnum), 0) as pnum' in body, (
        'the projects count no longer coalesces a missing join to 0')
    assert 'COUNT(DISTINCT "PROJECT_ID") AS prjnum' in body, (
        'the count is no longer over DISTINCT project ids, so a matched group '
        'could legitimately be 0 and the view would call it unknown')
