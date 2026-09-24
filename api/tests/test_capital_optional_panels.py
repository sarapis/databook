"""An absent optional source must not take the project profile down.

⚠⚠ THIS IS A MEASURED PRODUCTION OUTAGE, NOT A HYPOTHETICAL. On 2026-09-11,
during the capital deploy, `/get/capital/project/{id}` returned **500 for all
17,024 projects** — the app turning each into a 503 — because
`parkscapitaltracker` does not exist on prod and `_parks` let
`UndefinedTableError` escape. One optional panel, the entire page type.

⭐ THE SOURCE IS UNOBTAINABLE THERE, WHICH IS WHY DEGRADING IS THE ONLY ANSWER.
NYC Parks IP-blocks the server: the feed answers **HTTP 405** from prod and
**200** from a laptop — the same class as the documented `www.nyc.gov` 403 and
the CheckbookNYC WAF block. So "just ingest it" is not available, and a page
type cannot depend on a publisher choosing to answer us.

⭐ AND THE REST OF THE CODE ALREADY EXPECTED ABSENCE: the provenance block
serves `"present": bool(parks)` for exactly this case, and each panel renders
only when it has rows. `_parks` was the single place treating a missing table as
fatal.

⚠ THE CATCH MUST STAY NARROW. `UndefinedTableError` can only mean a source this
deployment has not ingested — never transient, never data-dependent. Everything
else is a real fault and must keep raising, or the helper becomes the
swallow-everything path that hides the next defect. Same split as
`routers/search.py::_rows`, which this repo already paid for.
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROUTER = os.path.join(API, 'routers', 'capital.py')

# Panels whose source is optional: a deployment can legitimately lack the table.
OPTIONAL = {'_parks', '_climate', '_milestones', '_commitments'}


def _src():
    with open(ROUTER, encoding='utf-8') as fh:
        return fh.read()


def _tree():
    return ast.parse(_src())


def _func(name):
    for n in ast.walk(_tree()):
        if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef)) and n.name == name:
            return n
    raise AssertionError('%s is gone from routers/capital.py' % name)


def test_every_optional_panel_degrades_on_a_missing_table():
    """⚠ The assertion is on the CALL each panel makes, not on a word in its
    body — a docstring mentioning `_select_optional` would satisfy a text scan
    while the code still used the fatal helper. This repo has 24 own-prose guard
    firings; reading the AST is the fix that holds."""
    offenders = []
    for name in sorted(OPTIONAL):
        fn = _func(name)
        calls = [n for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        names = {c.func.id for c in calls}
        if '_select' in names:
            offenders.append(
                '%s calls the fatal _select; an absent table 500s the whole '
                'project profile' % name)
        if '_select_optional' not in names:
            offenders.append('%s no longer routes through _select_optional' % name)
    assert not offenders, '\n  '.join(offenders)


def test_the_helper_catches_only_a_missing_table():
    """⚠⚠ A BROAD `except Exception` HERE WOULD BE WORSE THAN THE BUG IT FIXES.
    It would swallow a syntax error, a renamed column and a dead connection into
    a silently empty panel — the shape this repo records for the search group
    that returned `[]` for eight weeks and read as "nobody is called that"."""
    fn = _func('_select_optional')
    handlers = [n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)]
    assert handlers, '_select_optional no longer catches anything'
    assert len(handlers) == 1, 'more than one except: the catch has widened'
    caught = ast.unparse(handlers[0].type) if handlers[0].type else '<bare except>'
    assert caught.endswith('UndefinedTableError'), (
        'the optional-panel helper catches %r; only UndefinedTableError may be '
        'treated as "this deployment has not ingested the source"' % caught)


def test_every_optional_call_names_its_panel():
    """⚠ `panel` is keyword-only and REQUIRED, so a call missing it raises
    TypeError at request time — worse than the defect being fixed. I shipped
    exactly that for one edit: a regex converted four call sites and attached
    the keyword to only one. Checked by AST, never by eye."""
    bad = [n.lineno for n in ast.walk(_tree())
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == '_select_optional'
           and not any(k.arg == 'panel' for k in n.keywords)]
    assert not bad, (
        '_select_optional called without panel= at line(s) %s — that is a '
        'TypeError on every request that reaches it' % bad)


def test_the_degradation_is_logged_as_a_warning_not_an_error():
    """⚠ A fresh or partially-ingested environment legitimately lacks these
    tables, so this must not page anyone. WARNING is a breadcrumb here; ERROR
    would raise a Sentry event on every request of a correct deployment — the
    muted-alert failure this repo documents."""
    fn = _func('_select_optional')
    logs = [ast.unparse(n.func) for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and getattr(n.func.value, 'id', '') == 'logger']
    assert logs, 'the degradation is silent — an absent panel would be invisible'
    assert all(l.endswith('.warning') for l in logs), (
        'the optional-panel degradation logs %s; a legitimate fresh-environment '
        'state must not be an ERROR' % logs)
