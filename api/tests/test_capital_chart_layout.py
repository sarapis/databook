"""Two pie charts were drawn in the SAME BOX, under the SAME heading.

⚠⚠ MEASURED 2026-09-10 ON THE RENDERED PAGE, at 1440 AND 390:

    byPrgTypeChart     x=1195 y=365 w=285 h=200
    byFundSourceChart  x=1195 y=365 w=285 h=200
    overlap 285 x 200 = **100% of both**

So one of the two charts on `/projects/budget-lines` was completely hidden
behind the other, at every width, and the page scrolled sideways by exactly
40px.

⭐ THE MECHANISM IS WORTH KNOWING: the wrapper carried
`position: absolute; right: -40px` and **no ancestor was positioned**, so it
resolved against the INITIAL CONTAINING BLOCK — `right: -40px` meant 40px past
the VIEWPORT rather than 40px past its column, and both wrappers therefore
landed in the identical place. The 40px of sideways scroll and the total overlap
are the same bug, which is why the scroll was the only symptom anyone could see.

⚠⚠ AND THE HIDDEN CHART IS WHY A WRONG LABEL SURVIVED. `byFundSourceChart` is
fed `stats['byfund']`, which buckets `Funding Type` through
`{C,E -> City, F -> Federal, S -> State, P -> Private}` — its rendered labels are
`Private, Federal, State, City` — and it carried the project-type chart's
heading **verbatim**. The page showed two charts of different dimensions under
one label; nobody noticed because only one was ever visible.
"""
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(HERE, '..', '..'))
VIEWS = os.path.join(ROOT, 'app', 'resources', 'views')
VIEW = os.path.join(VIEWS, 'budgetLinesA.blade.php')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _blade_code(src):
    """⚠ Comments stripped: the fix's own comments quote `position: absolute`,
    `right: -40px` and the wrong heading, so every guard below would fire on the
    prose explaining them."""
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'^[ \t]*//.*$', '', src, flags=re.M)


def test_no_capital_view_positions_a_chart_against_the_viewport():
    """⚠ Scoped to an inline `position: absolute` paired with a NEGATIVE offset,
    which is the shape that silently resolves against the viewport. A plain
    `position: absolute` inside a positioned parent is ordinary and stays legal.
    """
    scanned, bad = 0, []
    for name in sorted(os.listdir(VIEWS)):
        if not name.endswith('.blade.php'):
            continue
        src = _blade_code(_read(os.path.join(VIEWS, name)))
        scanned += 1
        for m in re.finditer(r'style="[^"]*"', src):
            style = m.group(0)
            if 'position:' not in style or 'absolute' not in style:
                continue
            if re.search(r'\b(right|left|top|bottom)\s*:\s*-\d', style):
                bad.append('%s: %s' % (name, style[:90]))
    assert scanned > 40, (
        'this guard scanned only %d views, so it is the zero-files scanner '
        'again' % scanned)
    assert not bad, (
        'an inline absolute position with a negative offset is back. With no '
        'positioned ancestor that resolves against the VIEWPORT, which stacked '
        'two charts in one box and scrolled the page sideways: %s' % bad[:4])


def test_the_project_type_chart_says_what_it_plots_and_is_fed_it():
    """⚠⚠ RE-EXPRESSED, NOT DELETED — its condition ended. This was TWO guards
    over a PAIR of pie charts: one asserted they did not share a heading (the
    funding-source chart had carried the project-type heading verbatim), the
    other that `chart2` was fed `byfund` so the rename stayed honest. The owner
    removed the funding-source pie on 2026-09-11, so there is no pair and no
    `chart2`, and keeping either would forbid the removal it was asked for.

    ⭐ WHAT SURVIVES IS THE PROPERTY THAT WAS ALWAYS THE POINT: a chart says
    what it plots, and is fed what it says. That half applies to the one pie
    left, and `test_the_funding_source_pie_is_gone_from_markup_and_from_js` in
    `test_capital_index_charts.py` pins the other direction — that the series
    behind the removed chart is still COMPUTED, because the line chart beside it
    plots the same four sources.
    """
    view = _blade_code(_read(VIEW))
    m = re.search(r'class="col-md-\d+ byPrgTypeChart"', view)
    assert m, 'the project-type chart column is gone'
    h = re.search(r'<h4[^>]*>(.*?)</h4>', view[m.start():], flags=re.S)
    assert h, 'the project-type column lost its heading'
    head = re.sub(r'<[^>]+>', '', h.group(1)).strip()
    assert 'Project Type' in head, (
        'the project-type chart no longer says what it plots: %r' % head)
    m1 = re.search(r"pieChartUpd\(\s*window\.chart1\s*,\s*'\.byPrgTypeChart'\s*,\s*stats\['([a-z0-9_]+)'\]", view)
    assert m1, 'chart1 is no longer wired to the project-type column'
    assert m1.group(1) == 'byprj', (
        "the project-type chart is fed stats['%s'], not the project-type series"
        % m1.group(1))
