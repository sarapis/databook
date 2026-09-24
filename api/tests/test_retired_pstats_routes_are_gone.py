"""The 24 per-publication-date `pstats-*` routes are DELETED, and stay deleted.

⚠⚠ WHAT THEY WERE. Each served ONE number for ONE publication date of
`capitalprojectsdollarscomp` — the series NYC retired 2023-10-26 — in three
scopes: per organization (`/get/orgs/pstats-{measure}/{id}/{pubdate}`), citywide
(`/get/pstats-{measure}/{pubdate}`) and per administrative district
(`/get/districts/pstats-{measure}/{type}/{id}/{pubdate}`), over eight measures.

⚠⚠ WHY THIS GUARD EXISTS AT ALL, AND IT IS NOT ABOUT DEAD CODE. One of the eight
measures is **`over_budg_am` — `Amount Over Budget`**, the label this section
retired for carrying two definitions, and these routes held the last live
arithmetic for it: `-sum(cast("BUDG_DIFF" as decimal))`, the publisher's own
difference column, which does not reconcile with the two costs the same grid
showed. That is exactly the figure the budget-line page published as $297M over
budget beside $502M original and $474M current. An endpoint nobody calls is
harmless; an endpoint nobody calls that computes a retired label is a template,
and the next page written from it republishes the defect — which the org capital
tab did for weeks, with eight blank tiles one of which was labelled
`Amount Over Budget`.

⭐ THEY WERE PROVED UNUSED, NOT ASSUMED. A tree-wide scan for each route found it
in exactly two kinds of place: a COMMENT in `app/` recording that the URL was
removed, and a GUARD asserting it is absent. Neither is a consumer.

⚠ WHAT IS DELIBERATELY STILL HERE, so nobody "finishes the job" by deleting it:
`/get/orgs/pstats-union/{id}` is LIVE, is labelled on the page as the 2023
series, and answers the whole row in one query; `/get/pstats-records_no-by_*` is
a different family entirely (a dataset's record count for a scope) and is what
the provenance component reads; and `/get/pstats-categories*` /
`/get/capitalprojects/{dates,all,geojson,taxonomy,core,by_category}` all have
live consumers. The rule is not "no route may read the retired series" — this
repo already corrected that overreach once. It is that these 24 have no caller
and one of them computes a retired label.
"""
import ast
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROOT = os.path.realpath(os.path.join(API, '..'))
MAIN = os.path.join(API, 'main.py')

MEASURES = ('projects_no', 'orig_cost', 'curr_cost', 'over_budg_am',
            'long_no', 'over_budg_no', 'late_start_no', 'late_end_no')

DELETED = tuple(
    tmpl % m for m in MEASURES for tmpl in (
        '/get/orgs/pstats-%s/{id}/{pubdate}',
        '/get/pstats-%s/{pubdate}',
        '/get/districts/pstats-%s/{type}/{id}/{pubdate}',
    )
) + ('/get/capitalprojects/profile/{prjid}',
     '/get/capitalprojects/by_budgetline/{blcode}')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _routes():
    """Every route string `main.py` REGISTERS — read off the decorators.

    ⚠⚠ NOT a substring scan of the file. The module's own comments name each
    deleted route in order to explain why it went, so a text search fires on the
    prose that records the deletion: own-prose firing number twenty-seven,
    avoided by construction rather than by comment-stripping. A route exists if
    and only if a decorator declares it.
    """
    tree = ast.parse(_read(MAIN))
    out = []
    for n in ast.walk(tree):
        for d in getattr(n, 'decorator_list', []) or []:
            if (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                    and d.func.attr in ('get', 'post', 'put', 'delete')
                    and d.args and isinstance(d.args[0], ast.Constant)
                    and isinstance(d.args[0].value, str)):
                out.append(d.args[0].value)
    return out


def test_the_scan_can_see_routes_at_all():
    """⚠ A guard that finds nothing passes. This one asserts it LOOKED, and that
    it can see a route it is NOT trying to ban — otherwise a decorator rename
    makes every assertion below vacuous."""
    routes = _routes()
    # ⚠ The floor is deliberately far BELOW the real count (140 today), on the
    # `MIN_TOOLS = 35` precedent: it exists to catch an empty or truncated parse,
    # not to pin a number that a legitimate new endpoint would break.
    assert len(routes) > 100, (
        'only %d routes parsed out of main.py — the decorator shape has '
        'changed and every assertion in this file is now vacuous' % len(routes))
    assert '/get/orgs/pstats-union/{id}' in routes, (
        'the LIVE union endpoint is missing; either it was deleted with the '
        'dead ones or this scan is reading the wrong thing')


def test_none_of_the_twenty_six_retired_routes_is_registered():
    routes = set(_routes())
    back = sorted(r for r in DELETED if r in routes)
    assert not back, (
        'a retired per-publication-date route is registered again: %s. These '
        'have no caller, and `over_budg_am` computes the two-definition label '
        'this section reproduces nowhere.' % back)


def test_no_route_computes_amount_over_budget_from_the_publishers_difference():
    """⚠⚠ THE PROPERTY, NOT THE ROUTE NAMES. Re-adding the same arithmetic under
    a different path would satisfy the test above and reintroduce the defect. So
    this reads the SQL STRING LITERALS and bans the `-sum(... "BUDG_DIFF" ...)`
    shape wherever it appears.

    ⚠ It reads literals via `ast`, never the file text: the explanation directly
    above quotes the expression it bans.
    ⚠ And it must not ban `BUDG_DIFF` outright — `/get/orgs/pstats-union` and
    the type index legitimately COUNT rows where it is negative, which is a
    different claim from publishing its sum as a dollar figure.
    """
    tree = ast.parse(_read(MAIN))
    lits = [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    docs = set()
    for n in ast.walk(tree):
        b = getattr(n, 'body', None)
        if (isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                           ast.ClassDef)) and b and isinstance(b[0], ast.Expr)
                and isinstance(b[0].value, ast.Constant)
                and isinstance(b[0].value.value, str)):
            docs.add(b[0].value.value)
    sql = [s for s in lits if s not in docs]
    assert sql, 'no string literals read out of main.py'
    bad = [s for s in sql
           if re.search(r'-\s*sum\s*\([^)]*BUDG_DIFF', s, flags=re.I | re.S)]
    # ⚠⚠ EXACTLY TWO SURVIVORS, EACH NAMED WITH ITS REASON rather than admitted
    # by a looser pattern — so a THIRD has to be argued for instead of arriving
    # by omission. Both are LIVE endpoints whose page LABELS the figure as the
    # 2023 series, which is the standing exception this section allows.
    #
    #   `pstats-union`  — serves the org capital tab's whole retired row in one
    #                     query, `over_budg_am` among its columns.
    #   `stats-prj`     — the org profile's publication-date time series. ⚠ Its
    #                     `budg_diff` is SERVED AND DELIBERATELY NOT PLOTTED: the
    #                     `Amount Over Budget` dataset was removed from the chart
    #                     (`af69016`) and the view records that pushing into a
    #                     dataset that no longer exists throws on the first point
    #                     and blanks the whole canvas. Served-and-ignored, not
    #                     published.
    allowed = [
        lambda s: 'AS over_budg_am' in s and 'FROM ret' in s,
        lambda s: 'as budg_diff' in s and 'GROUP BY "PUB_DATE"' in s,
    ]
    rest = [s for s in bad if not any(f(s) for f in allowed)]
    assert not rest, (
        'a query publishes `Amount Over Budget` as -sum("BUDG_DIFF") again — '
        'the label carrying two definitions, which this section reproduces '
        'nowhere: %s' % [s[:90] for s in rest])
    # ⚠ And the allowances must still MATCH something, or a rename turns each of
    # them into a permanently-inert exemption that hides the next instance.
    for i, f in enumerate(allowed):
        assert any(f(s) for s in bad), (
            'named survivor %d no longer matches any query, so it is now an '
            'exemption for nothing — delete it rather than leave it' % i)


def test_the_orphaned_district_pstats_helper_is_gone():
    """⚠ `_pstats_select` existed only for the eight district routes. Leaving a
    helper whose every caller is deleted is how a later reader concludes the
    endpoints must still be somewhere — and it is a live invitation to re-add
    them, since the hard part looks already done."""
    tree = ast.parse(_read(MAIN))
    fns = {n.name for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert '_pstats_select' not in fns, (
        '_pstats_select is back; it has no caller unless the eight district '
        'per-publication-date routes came back with it')
    assert '_district_select' in fns, (
        '_district_select was deleted with it — that one still serves the live '
        'district tables and its loss would empty every district data tab')


def test_no_frontend_file_asks_for_a_deleted_route():
    """⚠⚠ THE HALF THAT MATTERS AT RUNTIME. Deleting an endpoint the frontend
    still builds a URL for turns a rendered tile into a 404 and — measured on
    this section — one throw in `loadTableStat` leaves EVERY remaining tile on
    the page blank. So the ban is enforced against `app/` too, on the
    STATIC PREFIX, which is what a PHP string concatenation would still contain.

    ⚠ Comments are stripped first: `app/` carries several comments naming these
    URLs precisely to record that they were removed.
    """
    roots = [os.path.join(ROOT, 'app', 'app'),
             os.path.join(ROOT, 'app', 'resources', 'views'),
             os.path.join(ROOT, 'app', 'public', 'js')]
    prefixes = sorted({r.split('{')[0].rstrip('/') for r in DELETED})
    scanned, bad = 0, []
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if not f.endswith(('.php', '.js')):
                    continue
                p = os.path.join(dirpath, f)
                src = _read(p)
                src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
                src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
                src = re.sub(r'^[ \t]*(?://|#).*$', '', src, flags=re.M)
                scanned += 1
                for pre in prefixes:
                    if pre in src:
                        bad.append('%s -> %s' % (os.path.relpath(p, ROOT), pre))
    # ⚠ 196 files today; the floor is below that for the same reason as the
    # route floor above — it catches a broken walk, not a deleted view.
    assert scanned > 150, (
        'this guard scanned only %d frontend files, so it is the zero-files '
        'scanner again' % scanned)
    assert not bad, (
        'a frontend file builds a URL for a deleted endpoint, which 404s and '
        'blanks every tile on the page: %s' % bad[:5])
