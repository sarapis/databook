"""Every view that renders the provenance component must be PASSED its datasets.

⚠⚠ THE DEFECT THIS EXISTS TO STOP, AND IT SHIPPED ON THE CAPITAL BRANCH.
`Projects::mProjects()` never passed a `datasets` key, and `main` got away with
it for as long as it did because the view's ONLY consumer was dead code — its
`@foreach($datasets ...)` sat inside a Blade comment, so the variable was never
evaluated and `/capital/minor-projects` returned a contented 200.

Migrating the page to `<x-db.data-provenance :datasets="$datasets">` gave it a
LIVE consumer, and the page began returning **500 —
`Undefined variable: datasets`**. Nothing in the suite saw it; it was caught by
#383's page-family sweep, on that sweep's first real use.

⭐ THE GENERAL SHAPE IS #247's CONTROLLER SEAM: a Laravel controller NAMES each
view-data key, so a template can read something the controller never sends. The
Overview has a guard for exactly this. This is the same guard for the
provenance component, which is now on a dozen views.

⚠ A missing key is not always a 500 — `$x ?? []` degrades politely, which is how
the Digital Services Overview once shipped with two whole blocks missing while
every unit test passed. So this asserts the key is SENT, never that the page
renders.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
VIEWS = os.path.join(ROOT, 'app', 'resources', 'views')
CONTROLLERS = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _blade_code_only(text):
    """⚠ Strip Blade comments. `main`'s dead `@foreach($datasets ...)` lived
    inside one — counting it as a live read is precisely the mistake that made
    this bug invisible, so the stripper is the guard's core, not hygiene."""
    return re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)


def _views_that_read_datasets_live():
    """View basenames whose LIVE code (comments stripped) reads `$datasets`."""
    out = []
    for name in sorted(os.listdir(VIEWS)):
        if not name.endswith('.blade.php'):
            continue
        code = _blade_code_only(_read(os.path.join(VIEWS, name)))
        if re.search(r'\$datasets\b', code):
            out.append(name[:-len('.blade.php')])
    return out


def _view_calls_in_controllers():
    """{view name: [the argument array of each `view('name', [...])` call]}."""
    calls = {}
    for root, _dirs, files in os.walk(CONTROLLERS):
        for f in files:
            if not f.endswith('.php'):
                continue
            src = _read(os.path.join(root, f))
            src = re.sub(r'^\s*//.*$', '', src, flags=re.M)
            for m in re.finditer(r"view\(\s*'([A-Za-z0-9_.\-/]+)'\s*,", src):
                name = m.group(1)
                # Walk balanced brackets from the opening [ of the array.
                i = src.find('[', m.end() - 1)
                if i < 0:
                    continue
                depth, j = 0, i
                while j < len(src):
                    if src[j] == '[':
                        depth += 1
                    elif src[j] == ']':
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1
                calls.setdefault(name, []).append(src[i:j + 1])
    return calls


def test_the_scan_found_views_and_controller_calls():
    """⚠ ANTI-VACUUM — a guard that resolves to nothing passes unconditionally."""
    views = _views_that_read_datasets_live()
    calls = _view_calls_in_controllers()
    assert len(views) >= 5, f'only {len(views)} views read $datasets: {views}'
    assert len(calls) >= 20, f'only {len(calls)} view() calls found in controllers'


def test_every_view_reading_datasets_is_passed_it():
    views = _views_that_read_datasets_live()
    calls = _view_calls_in_controllers()
    offenders = []
    for view in views:
        arrays = calls.get(view)
        if not arrays:
            # Rendered only via @include/@extends, so it inherits its parent's
            # data. Not a seam this guard can check, and not one that broke.
            continue
        for arr in arrays:
            if "'datasets'" not in arr:
                offenders.append(f"{view}.blade.php reads $datasets but a "
                                 f"view('{view}', [...]) call does not pass it")
    assert not offenders, (
        'the controller must NAME every key the view reads — a missing one is '
        'either a 500 or, worse, a politely empty section:\n  '
        + '\n  '.join(sorted(set(offenders))))
