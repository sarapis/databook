"""Route actions are the array form, never the `'Controller@method'` string.

⚠⚠ THE STRING FORM DEPENDS ON A PREFIX LARAVEL REMOVED. It is resolved against
`RouteServiceProvider::$namespace`, which Laravel 8 dropped from the default
skeleton. Every string action is therefore an item in the framework migration
(#382), and the procurement section those routes serve is under active
development — so each one written in the old form is rework booked in advance.
28 of them were converted 2026-09-14; this stops the count growing back.

⚠ It is NOT a forward-compatibility bet. Laravel 7.30.7's `RouteAction::parse`
already handles arrays, and the file had mixed both forms for months — 69
array-form registrations ran beside the 28 string ones. The conversion changed
no caller anywhere: all 28 were `->name()`d and nothing in the tree resolves a
route by action string (`action()` / `URL::action`).

⭐ THE PROOF THE CONVERSION WAS PURE was not a count. `php artisan route:list`
before and after is BYTE-IDENTICAL — same 140 routes, same names, same resolved
actions — because Laravel resolves both forms to the same `Controller@method`
action string. A count can agree while a route moves; the resolved table cannot.

⚠ A wrong class reference here fails LOUDLY: class-not-found at registration, and
every page 500s. There is no silent-breakage mode, which is why the frontend
page-family sweep catches it across the board rather than subtly.
"""
import os
import re

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
ROUTES_DIR = os.path.join(ROOT, 'app', 'routes')

# A quoted `Controller@method` action literal.
STRING_ACTION = re.compile(r"'([A-Za-z_]\w*Controller)@(\w+)'")
# The array form, in either spelling — a bare imported name or a fully-qualified
# `\App\Http\Controllers\X::class`. ⚠ Both are live in this file: 19 routes use
# the fully-qualified spelling, and a bare-name-only pattern silently misses
# them. That is what made three different sessions report the array count as 48,
# 49 and 50 for one unchanged file.
ARRAY_ACTION = re.compile(r"\[\s*\\?(?:[A-Za-z_]\w*\\)*[A-Za-z_]\w*::class\s*,\s*'\w+'\s*\]")
REGISTRATION = re.compile(r"Route::(?:get|post|put|patch|delete|options|any|match|resource)\s*\(")


def _strip_php_comments(src):
    """Remove `/* */`, `//` and `#` comments WITHOUT touching string literals.

    ⚠ A naive `(?m)//.*$` eats from `http://` to end of line, which this repo has
    already paid for once (a dataset description carrying
    `http://labs.council.nyc/...`). No route file contains `://` today — checked
    — but a redirect to an external URL would introduce one, and a guard that
    only works on today's content is a guard with an expiry date.
    """
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in "'\"":
            # copy the whole literal verbatim, honouring backslash escapes
            quote, out_start = c, i
            i += 1
            while i < n:
                if src[i] == '\\':
                    i += 2
                    continue
                if src[i] == quote:
                    i += 1
                    break
                i += 1
            out.append(src[out_start:i])
            continue
        if src.startswith('/*', i):
            end = src.find('*/', i + 2)
            i = n if end == -1 else end + 2
            out.append(' ')
            continue
        if src.startswith('//', i) or c == '#':
            end = src.find('\n', i)
            i = n if end == -1 else end
            out.append(' ')
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def _route_files():
    return sorted(
        os.path.join(ROUTES_DIR, f)
        for f in os.listdir(ROUTES_DIR)
        if f.endswith('.php')
    )


def test_no_route_uses_the_string_controller_action_form():
    """The property. ⚠ Comments are stripped first, or this fires on the prose
    above explaining the banned form — this repo has had twenty guards fire on
    their own explanation."""
    offenders = []
    scanned = 0
    registrations = 0
    for path in _route_files():
        with open(path, encoding='utf-8') as fh:
            code = _strip_php_comments(fh.read())
        scanned += 1
        registrations += len(REGISTRATION.findall(code))
        for m in STRING_ACTION.finditer(code):
            line = code[:m.start()].count('\n') + 1
            offenders.append(f"{os.path.basename(path)}:{line}  '{m.group(1)}@{m.group(2)}'")

    # ⚠⚠ NON-VACUITY, BOTH HALVES. A broken extractor finds nothing and passes,
    # which is indistinguishable from a clean tree — this repo has shipped a
    # guard that scanned ZERO files and passed unconditionally. Floors are set
    # well under the real figures (4 files, 140 registrations) so ordinary
    # additions never trip them, but a scanner reading the wrong directory or a
    # comment-stripper that blanks the file does.
    assert scanned >= 4, f"only scanned {scanned} route files — the path is wrong"
    assert registrations >= 100, (
        f"found only {registrations} Route:: registrations across {scanned} files — "
        "the scanner is broken, not the tree"
    )

    assert not offenders, (
        "route actions must be the array form `[Controller::class, 'method']`, not "
        "the `'Controller@method'` string — the string form resolves against "
        "RouteServiceProvider::$namespace, which Laravel 8 removed (see #382):\n  "
        + "\n  ".join(offenders)
    )


def test_the_array_form_is_actually_in_use():
    """⭐ The other direction, and it is not decoration.

    A file where every route is a closure would satisfy the ban above while
    proving nothing. This pins that the array form is the form in use, so the
    ban cannot pass by the routes having quietly become something else.
    """
    total = 0
    for path in _route_files():
        with open(path, encoding='utf-8') as fh:
            total += len(ARRAY_ACTION.findall(_strip_php_comments(fh.read())))
    assert total >= 90, (
        f"only {total} array-form route actions found; there were 97 after the "
        "2026-09-14 conversion. A sharp drop means routes were removed or the "
        "pattern no longer matches how they are written"
    )


def test_the_comment_stripper_does_not_eat_a_url():
    """⚠ The stripper is the part most likely to be wrong in the quiet direction.

    `(?m)//.*$` would truncate `'http://example.test/x'` at the `//`, silently
    shrinking what the ban above scans. Pinned directly rather than trusted.
    """
    src = "Route::redirect('/a', 'http://example.test/b');  // a real comment\n"
    out = _strip_php_comments(src)
    assert 'http://example.test/b' in out, "the stripper ate a URL inside a string"
    assert 'a real comment' not in out, "the stripper did not remove a real comment"
    # …and a banned action hiding in a comment must NOT be reported.
    assert not STRING_ACTION.search(_strip_php_comments("// 'FooController@bar'\n")), \
        "a commented-out action is reported as live code"
    # …while the same text in real code must be.
    assert STRING_ACTION.search(_strip_php_comments("Route::get('/x', 'FooController@bar');")), \
        "a live string action is not detected"


@pytest.mark.parametrize('name', ['web.php', 'api.php', 'channels.php', 'console.php'])
def test_every_expected_route_file_is_present(name):
    """⚠ The floor above counts files; this names them. A rename that left the
    count intact would otherwise pass while the file carrying all 140 routes
    stopped being scanned."""
    assert os.path.exists(os.path.join(ROUTES_DIR, name)), \
        f"app/routes/{name} is gone — update this list deliberately, not by deleting the assertion"


# ---------------------------------------------------------------------------
# 2026-09-18 — the controller-namespace prefix, removed once #404 made it dead.
# ---------------------------------------------------------------------------

PROVIDER = os.path.join(ROOT, 'app/app/Providers/RouteServiceProvider.php')


def _provider_code():
    """⚠ Comments stripped. The block that replaced `$namespace` explains what it
    was for and quotes `namespace` repeatedly, so a raw scan fires on its own
    epitaph — the most common guard defect in this repo."""
    src = open(PROVIDER, encoding='utf-8').read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return "\n".join(l for l in src.split("\n") if not l.strip().startswith('//'))


def test_the_route_service_provider_declares_no_controller_namespace():
    """⚠⚠ THIS PROPERTY IS A BLOCKER, NOT A TIDY-UP. `$namespace` turned
    `'Titles@main'` into `App\\Http\\Controllers\\Titles@main`; Laravel 8
    deprecated it and Laravel 9 REMOVES it, so while it is declared the
    framework move (#382) cannot proceed and string actions can quietly return.

    ⭐ Removing it was proved inert the way #404 proved its own change:
    `php artisan route:list` byte-identical before and after — 144
    registrations, same names, same resolved actions. A count can agree while a
    route moves; the resolved table cannot."""
    code = _provider_code()
    assert not re.search(r'\$namespace\s*=', code), (
        'RouteServiceProvider declares a controller namespace again — that '
        're-enables string-form route actions and re-blocks the Laravel 9 move')
    assert '->namespace(' not in code, (
        'a route group applies a controller namespace again: ' + code[:200])
