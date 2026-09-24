"""The org profile's `Capital Projects` trend chart.

⚠⚠ THIS WAS THE FOURTH SURFACE STILL PLOTTING `Amount Over Budget`, AND THE ONE A
TEXT SCAN OF THE RENDERED PAGE CANNOT SEE. Chart.js draws its legend into the
canvas, so a sweep of every capital URL for the string "Amount Over Budget"
reported this page clean while `window.chart3.data.datasets[1].label` was exactly
that, over 14 publication dates from `-sum("BUDG_DIFF")` on
`capitalprojectsdollarscomp`. **Read the chart's DATA, not the page's text** — the
same rule this section already records for a map (read `getSource()._data`, not
pixels) and for a clipped tile (geometry proves an element is there; only looking
proves it is readable).

⚠ `Current Budget` stays: one measure, one column, and the caption says which
series it is and that NYC last published it 2023-10-26 — the line stops in 2023
while every other figure on the profile is live.

⚠ AND THE FIRST FIX SHOWED AN EMPTY CHART UNDER THAT CAPTION. `drawPrjstatChart`
shows the canvas whenever its callback fires, 0 rows included, so NYCHA — which
holds no row in that series — rendered a blank canvas captioned as if it did.
Caught by rendering NYCHA, not by re-reading the code; my own comment claiming
the caption could not appear without data was wrong.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'organization.blade.php')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _code_only(text):
    """⚠ Blade and JS comments stripped: the comments added with this fix quote
    `Amount Over Budget`, `datasets[1]` and `BUDG_DIFF`, which is every string
    the guards below search for."""
    text = re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'^\s*//.*$', '', text, flags=re.M)


def _chart_config(code):
    """`config3`, the capital chart's Chart.js config, by balanced braces."""
    i = code.index('var config3 = {')
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
    raise AssertionError('unbalanced config3')


def test_the_capital_chart_does_not_plot_amount_over_budget():
    """⚠⚠ INVARIANT 11, on the surface where the label is drawn into a canvas."""
    code = _code_only(_read(VIEW))
    cfg = _chart_config(code)
    assert 'Amount Over Budget' not in cfg, (
        'the capital trend chart plots the two-definition label again — and no '
        'scan of the page text can see it, because Chart.js renders the legend '
        'into the canvas')
    labels = re.findall(r"label:\s*'([^']+)'", cfg)
    assert labels == ['Current Budget'], (
        'the capital chart should carry exactly one series; found %s' % labels)


def test_the_chart_filler_pushes_only_the_series_that_exists():
    """⚠ Pushing into `datasets[1]` after removing that dataset throws on the
    first point and leaves the whole chart blank — the failure mode is a chart
    that silently never draws, which this section has already paid for once on
    `/projects`."""
    code = _code_only(_read(VIEW))
    i = code.index('function drawPrjstatChart(')
    body = code[i:code.index('\n\t\t}', i)]
    pushes = re.findall(r'datasets\[(\d+)\]\.data\.push', body)
    assert pushes == ['0'], (
        'the filler pushes into datasets %s but the config declares one series'
        % pushes)
    assert 'budg_diff' not in body, (
        'the chart is plotting the budget difference again')


def test_an_agency_with_no_rows_gets_neither_the_chart_nor_its_caption():
    """⚠ NOTHING TO PLOT IS NOT AN EMPTY CHART. NYCHA holds no row in the 2023
    series, and the first version of this fix showed it a blank canvas under a
    caption about that series. Verified rendered afterwards: Parks shows the
    chart and the note, NYCHA shows neither."""
    code = _code_only(_read(VIEW))
    i = code.index('function drawPrjstatChart(')
    body = code[i:code.index('\n\t\t}', i)]
    gate = re.search(r'if\s*\(\s*!data\s*\|\|\s*!data\.length\s*\)\s*\{\s*return', body)
    assert gate, (
        'drawPrjstatChart no longer returns early on an empty series, so an '
        'agency with no rows renders a blank chart under a caption claiming one')
    for shown in ("$('#chart_prj').show()", "$('#chart_prj_note').show()"):
        assert body.index(shown) > gate.end(), (
            '`%s` runs before the empty-series gate' % shown)


def test_the_chart_says_which_series_and_which_vintage_it_is():
    """⚠ It is the ONE figure on the profile that is not current. Unlabelled, a
    line ending in 2023 beside live headcount and spending reads as the agency's
    capital programme stopping."""
    view = _read(VIEW)
    i = view.index('id="chart_prj_note"')
    note = view[i:i + 900]
    for phrase in ('2023-10-26', 'capital spine'):
        assert phrase in note, (
            'the caption no longer says "%s", so a 2019-2023 line reads as '
            'current' % phrase)
    assert "route('orgSection'" in note, (
        'the caption no longer links to the spine-backed capital tab')
    assert "'orgslug' => '-'" not in note, (
        "the link builds its slug as a bare '-'; use this page's own "
        "Str::slug($org['name']) convention")
