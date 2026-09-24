"""Guards for the frontend page-family sweep (scripts/frontend-smoke.sh).

The sweep exists to make the Laravel 13 / PHP 8.4 migration in issue #382
verifiable: a route that stops resolving, a view that stops compiling or a
class that stops loading all move a page's status, and the sweep fails on any
movement against a committed baseline.

⚠ It is a DIFF, not a list of expected 200s, and that is not a shortcut. CI
boots against an EMPTY Postgres, where a page that 500s from missing data is
byte-identical to one broken by a code change — the failure this repo keeps
paying for, one layer up. Asserting "nothing moved" is the strongest thing that
is actually true without a seed fixture.

These guards pin the properties that were verified by hand when it was written,
because each of them is a way the sweep could keep passing while covering
nothing.
"""

import io
import os
import re
import subprocess

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SCRIPT = os.path.join(ROOT, 'scripts', 'frontend-smoke.sh')
ROUTES = os.path.join(ROOT, 'app', 'routes', 'web.php')
CI = os.path.join(ROOT, '.github', 'workflows', 'ci.yml')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _urls():
    """The sweep's OWN url list, by running it — never a reimplementation.

    A harness that rebuilds the thing it checks measures a different system and
    reports its result as the real one.
    """
    out = subprocess.run(['bash', SCRIPT, '--urls'], capture_output=True, text=True)
    assert out.returncode == 0, 'frontend-smoke.sh --urls failed: %s' % out.stderr
    return [l for l in out.stdout.splitlines() if l.strip()]


def test_the_sweep_covers_the_page_families_and_says_so_when_it_cannot():
    """It must find the routes, and refuse loudly when it finds none."""
    urls = _urls()
    assert len(urls) >= 40, (
        'the sweep extracted only %d urls from web.php — a sweep that covers '
        'nothing passes silently, which is the whole defect it guards against'
        % len(urls))
    for expected in ('/', '/procurement', '/research/digital-reform', '/districts'):
        assert expected in urls, 'the sweep does not cover %r' % expected

    # And the floor must actually fire, not merely be written down.
    empty = _read(SCRIPT).replace('ROUTES="$ROOT/app/routes/web.php"',
                                  'ROUTES="/dev/null"', 1)
    tmp = os.path.join('/tmp', 'fe_smoke_empty_guard.sh')
    with io.open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(empty)
    out = subprocess.run(['bash', tmp, '--urls'], capture_output=True, text=True)
    os.unlink(tmp)
    assert out.returncode == 2, (
        'with no routes to find, the sweep exited %d instead of refusing — it '
        'would report success having checked nothing' % out.returncode)


def test_a_commented_out_route_is_never_swept():
    """`#Route::get('/sitemap.xml', ...)` is commented out in web.php.

    The first draft of the extractor matched it, because a grep over raw text
    cannot tell a route from a route someone deleted. Asserting on a URL that is
    not routed at all would bake a 404 into the baseline and call it correct.
    """
    routes = _read(ROUTES)
    commented = re.findall(r"(?m)^\s*(?://|#)\s*Route::get\(\s*'(/[^']*)'", routes)
    assert commented, (
        'no commented-out Route::get in web.php any more — this guard has lost '
        'its subject; re-check the extractor still strips comments before '
        'deleting it')
    urls = _urls()
    for u in commented:
        assert u not in urls, (
            '%r is commented out in web.php but the sweep picked it up — the '
            'extractor stopped stripping comments' % u)


def test_every_exclusion_is_justified_in_the_script():
    """A route may leave the sweep only with its reason written beside it.

    Excluding a route because it is inconvenient is how a sweep quietly stops
    covering the thing that breaks.
    """
    body = _read(SCRIPT)
    block = body[body.index('is_excluded()'):body.index('urls()')]
    patterns = re.findall(r"(?m)^\s*(/[^)]*?)\)\s*return 0", block)
    assert patterns, 'no exclusions parsed out of is_excluded() — scanner is wrong'
    for pat in patterns:
        first = pat.split('|')[0].strip()
        assert re.search(r'#[^\n]*\n(\s*#[^\n]*\n)*\s*' + re.escape(pat), block), (
            'exclusion %r has no comment above it explaining why the sweep '
            'cannot assert on it' % first)
    # The two known ones, each for a different reason — pinned so a later
    # cleanup cannot quietly drop the reasoning with the entry.
    assert 'next.sarapis.org' in block, (
        'the /blog exclusion no longer names the external service that makes it '
        'unassertable')
    assert 'test_review_ui' in block, (
        'the gated-route exclusion no longer names what covers those routes '
        'instead')


def test_ci_runs_the_sweep_and_does_not_swallow_its_result():
    """The step must call the script directly, under `set -e`.

    A step that pipes the sweep into something else reports that thing's exit
    status, not the sweep's — the mistake that made a prod-smoke run read as
    passing when it had failed.
    """
    ci = _read(CI)
    assert './scripts/frontend-smoke.sh' in ci, 'CI never runs the frontend sweep'
    step = ci[ci.index('Frontend page families'):]
    step = step[:step.index('- name:', 10)]
    assert 'set -e' in step, 'the sweep step does not run under set -e'
    line = [l.strip() for l in step.splitlines()
            if './scripts/frontend-smoke.sh' in l][0]
    assert line == './scripts/frontend-smoke.sh', (
        'the sweep is invoked as %r — anything appended takes over the exit '
        'status and the failure would be swallowed' % line)


def test_ci_stubs_the_app_env_or_every_page_500s():
    """CI must create app/.env before the build, with a usable APP_KEY.

    `docker-compose.yml` bind-mounts `./app/.env`, which is gitignored — so
    without this Docker creates a DIRECTORY at /var/www/.env and Laravel cannot
    read its config. Measured 2026-09-09: all 68 page families returned 500 in
    CI, including /about and /styleguide, which need no data. The frontend had
    never rendered there, and the pre-existing smoke printed its status without
    asserting it.

    ⚠ And copying the template is not enough on its own: .env.example ships
    APP_KEY blank (spaces and a comment), which 500s Laravel by itself with
    "No application encryption key has been specified".
    """
    ci = _read(CI)
    assert 'cp app/.env.example app/.env' in ci, (
        'CI no longer stubs app/.env — the bind mount becomes a directory and '
        'every page 500s')
    assert 'app/.env.default' not in ci, (
        'CI must not use app/.env.default: sync-public.sh excludes it because '
        'it carried a live APP_KEY and Carto key')
    stub = ci[ci.index('cp app/.env.example app/.env'):]
    stub = stub[:stub.index('- name:')]
    assert re.search(r'APP_KEY=base64:', stub), (
        'CI stubs app/.env without setting an APP_KEY — .env.example ships it '
        'blank, and Laravel 500s on every page without one')
