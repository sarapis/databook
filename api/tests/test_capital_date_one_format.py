"""One date format across the capital section, and the PHP half agrees with it.

⚠⚠ THE SECTION PUBLISHED TWO FORMATS AGAIN, ON ONE PAGE. The profile's redesign
settled `23 Feb 2030` and implemented it at the endpoint; the facet pages were
never covered. Measured 2026-09-10 on the rendered pages, scoped to
`.inner_container`:

    /projects                        6 raw MM/DD/YYYY  (sources table)
    /projects/types                  3                 (sources table)
    /projects/categories             1                 (inline note)
    /projects/budget-lines           1                 (inline note)
    /projects/budget-lines/EP 0007  15                 (10 commitments + 5 sources)
    /p/826HED-545                    0                 (already fixed)

After: **0 on all seven.**

⚠ SCOPE WAS DECIDED BY MEASURING, and the first answer was wrong. 23 views
render a `Last Updated` column, which reads as site-wide and out of bounds — but
`ProjectsDatasets::stats_data_sources` is called **only from `Projects.php`**;
`DistDatasets` and `SchoolDatasets` carry their own copies. So the capital
sources table could be fixed without moving a single district or school date,
and it HAD to be: formatting the commitments table while leaving the sources
table raw would have put both formats on one page — the exact defect being
removed.

⚠ `plancommdate` was ALREADY in `routers/capital._DATE_COLUMNS`, but the
labelling runs in that router and `/get/commitments/by_budgetline` never called
it, so the value existed and no page could use it. `main.py` now imports the
SAME `_mdy_label` rather than growing a second implementation — which is what
its own docstring warns against.
"""
import importlib.util
import os
import re
import subprocess

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROOT = os.path.realpath(os.path.join(API, '..'))
PHP_FILE = os.path.join(ROOT, 'app', 'app', 'Custom', 'CapitalDate.php')
CAPITAL = os.path.join(API, 'routers', 'capital.py')
MAIN = os.path.join(API, 'main.py')

# The shapes measured in the live data, plus the edges either side of them.
SHAPES = ('09/05/2026 22:10', '03/10/2026', '06/01/2026', '12/31/1999',
          '', 'not a date', '13/45/2026', '2026-09-05')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _py_label():
    """`_mdy_label` loaded BY PATH.

    ⚠ `conftest.py` replaces the whole `modules` package with a MagicMock, and
    `routers/capital` imports from it — so a plain import yields a mock whose
    output would satisfy any assertion. This repo has paid for that twice.
    """
    src = _read(CAPITAL)
    ns = {}
    # take just the two functions, so nothing else in the router has to import
    m = re.search(r'\n_MONTHS = \([^)]*\)\n', src)
    assert m, '_MONTHS is gone from routers/capital.py'
    exec(m.group(0), ns)
    for name in ('_mdy', '_mdy_label'):
        fm = re.search(r'\ndef %s\(value\):.*?(?=\n\ndef |\n\n@|\n\n_)' % name,
                       src, flags=re.S)
        assert fm, '%s is gone from routers/capital.py' % name
        exec(fm.group(0), ns)
    assert ns['_mdy_label']('02/23/2030') == '23 Feb 2030', (
        'the python formatter did not load as itself')
    return ns['_mdy_label']


def test_the_php_formatter_agrees_with_the_python_owner():
    """⚠⚠ A FOURTH LANGUAGE FOR ONE RULE IS A COST, and this is what pays for it:
    the PHP half is RUN and its output compared against the Python owner's on
    every shape measured in the data. A guard that merely inspected the PHP
    source would be the "reimplements the thing it guards" defect."""
    py = _py_label()
    script = (
        'require %r;'
        'foreach (%s as $v) { echo App\\Custom\\CapitalDate::label($v), "\\n"; }'
        % (PHP_FILE, 'json_decode(\'%s\')' % __import__('json').dumps(list(SHAPES))))
    out = subprocess.run(['php', '-r', script], capture_output=True, text=True)
    if out.returncode != 0:
        import pytest
        pytest.skip('php unavailable: %s' % (out.stderr or '')[:60])
    got = out.stdout.split('\n')[:len(SHAPES)]
    for shape, php_out in zip(SHAPES, got):
        want = py(shape)
        want = '' if want is None else want
        # ⚠ The PHP half also accepts a trailing clock, which the python one
        # never sees — the endpoint's dates carry no time. Compare on the DATE.
        if shape and len(shape) > 10 and shape[2] == '/' and shape[5] == '/':
            want = py(shape[:10]) or ''
        assert php_out == want, (
            'the PHP and Python date formatters disagree on %r: PHP %r, '
            'Python %r' % (shape, php_out, want))


# ⚠⚠ A `test_the_php_formatter_falls_through_rather_than_blanking` STOOD HERE AND
# WAS DELETED, not patched. It scanned the PHP source for `return $raw;` — and
# there are TWO such returns (the separator check and the `checkdate` check), so
# a mutation that blanked one left the string present and the guard green: a
# property enforced twice, falsified by neither. The fall-through IS pinned, and
# behaviourally: `SHAPES` above carries `'not a date'` and `'13/45/2026'`, and
# replacing BOTH returns with `''` makes the agreement test fail with
# "PHP '', Python 'not a date'" — verified, not assumed. This repo's rule is
# that a guard needing its own failure mode to express a WEAKER version of an
# existing assertion is not worth keeping.


def test_main_imports_the_one_formatter_rather_than_defining_another():
    src = _read(MAIN)
    assert 'from routers.capital import _mdy_label' in src, (
        'main.py no longer imports the section\'s one date formatter')
    tree = __import__('ast').parse(src)
    ast = __import__('ast')
    defined = {n.name for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for banned in ('_mdy_label', '_mdy'):
        assert banned not in defined, (
            'main.py defines its own %s — a second spelling of a date format is '
            'exactly how this section came to publish two' % banned)


def test_the_capital_sources_table_formats_its_last_updated_cell():
    """⚠ Capital-only: `DistDatasets` and `SchoolDatasets` have their own copies
    and are deliberately untouched, so this asserts the CAPITAL one."""
    src = _read(os.path.join(ROOT, 'app', 'app', 'Custom', 'ProjectsDatasets.php'))
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'^[ \t]*//.*$', '', src, flags=re.M)
    m = re.search(r"\$dash\(([^)]*Last Updated[^)]*)\)", src)
    assert m, 'the sources table no longer renders a Last Updated cell'
    assert 'CapitalDate::label(' in m.group(1), (
        'the capital sources table publishes a raw MM/DD/YYYY again, beside a '
        'commitments table and a profile that both say `1 Jun 2026`')


def test_the_commitments_table_reads_the_label_and_falls_back():
    view = _read(os.path.join(ROOT, 'app', 'resources', 'views',
                              'budgetLineA.blade.php'))
    view = re.sub(r'^[ \t]*//.*$', '', view, flags=re.M)
    m = re.search(r"\{data: function \(r\) \{ return r\['plancommdate_label'\][^}]*\}", view)
    assert m, 'the commitments table no longer reads the served date label'
    assert "r['plancommdate']" in m.group(0), (
        'the commitments column does not fall back to the raw value, so a row '
        'the formatter cannot read would render blank — "not published", which '
        'is a different claim')


# =============================== the PATTERN, not the sites

CONTROLLER = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Projects.php')
VIEWS_DIR = os.path.join(ROOT, 'app', 'resources', 'views')


def _blade_no_comments(src):
    """⚠ Own-prose firings stand at 24 here, and the comment beside this fix
    quotes `explode(' ', $dataset['Last Updated']` verbatim."""
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$', '', src)


def _capital_views():
    """The capital section's views, READ OUT OF ITS CONTROLLER.

    ⭐ Derived, never typed — so a view added to `Projects.php` tomorrow is
    covered before it exists. The same reason `errfmt`'s guard globs
    `extractors/*.py` rather than listing them.

    ⚠ This is also what keeps the scope honest. `CapitalDate`'s own docstring
    records that 23 views render a `Last Updated` and that districts and schools
    are deliberately NOT capital's to move; anchoring on the controller says
    exactly which ones are, instead of a hand-kept list that drifts.
    """
    src = _read(CONTROLLER)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'(?m)^\s*//.*$', '', src)
    names = sorted(set(re.findall(r"view\('([A-Za-z0-9_/.]+)'", src)))
    out = []
    for n in names:
        p = os.path.join(VIEWS_DIR, n.replace('.', '/') + '.blade.php')
        if os.path.exists(p):
            out.append((n, p))
    assert len(out) >= 10, (
        'only %d capital views resolved from Projects.php — the scan would be '
        'nearly vacuous' % len(out))
    return out


def test_no_capital_view_publishes_a_raw_last_updated():
    """⚠⚠ THE FIX WAS APPLIED SITE BY SITE AND SO WAS THE GUARD, SO A SITE WAS
    MISSED.

    `test_the_capital_sources_table_formats_its_last_updated_cell` names
    `ProjectsDatasets.php` and `test_the_commitments_table_reads_the_label...`
    names `budgetLineA.blade.php`. Neither could see `prjCommitmentsA`, which
    went on rendering `explode(' ', $dataset['Last Updated'])[0]` — measured
    2026-09-11 on the rendered page as **`Last updated 05/16/2026`**, the single
    raw date left in the whole section, beside a commitments table already
    saying `1 Jun 2026`.

    ⭐ So this scans for the PATTERN. The same scan then found the identical line
    in `mProject` and `mProjects`, which render no date TODAY only because their
    `$dataset` lookup returns nothing locally — a value being absent is not the
    same as a format being right, and those two would have published MM/DD/YYYY
    the moment it resolved. Precedent: the pagination clamp, where scanning for
    the banned pattern found three sites the author had not.
    """
    offenders = []
    for name, path in _capital_views():
        src = _blade_no_comments(_read(path))
        for m in re.finditer(r'\{\{(?![-])(.*?)\}\}', src, re.S):
            expr = m.group(1)
            if 'Last Updated' not in expr:
                continue
            if 'CapitalDate::label' not in expr:
                offenders.append('%s: %s' % (name, ' '.join(expr.split())[:90]))
    assert not offenders, (
        'a capital view echoes a Last Updated value without the one owner, so '
        'the section publishes two date formats again:\n  ' +
        '\n  '.join(offenders))


def test_the_capital_date_scan_actually_looked():
    """⚠ A guard that scans zero files passes. This repo has shipped exactly
    that once, and the rule since is that any tree-walking guard asserts it
    looked — here, that the views resolve AND that the scan reaches the echo it
    was written for."""
    views = dict(_capital_views())
    assert 'prjCommitmentsA' in views, (
        'the commitments view is no longer reached from Projects.php, so the '
        'scan that caught its raw date would be silently narrower')
    hits = 0
    for name, path in _capital_views():
        src = _blade_no_comments(_read(path))
        hits += len(re.findall(r"\{\{[^}]*Last Updated[^}]*\}\}", src))
    assert hits >= 4, (
        'only %d Last Updated echoes found across the capital views; the scan '
        'has stopped seeing the thing it guards' % hits)
