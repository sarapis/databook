"""Pagination params are clamped, and disabled links carry no href.

⚠⚠ THE SITE WAS GENERATING ITS OWN CRAWLER TRAP. The pagination markup put
`disabled` on the <li> while leaving a real href on the <a> INSIDE it — a class
never stopped a crawler — so "Previous" from page 1 linked to page 0, from 0 to
-1, and downward without a floor. Meanwhile the controller took the value raw and
fed it into `$cacheKey = 'digital_reform_' . md5($qs)` with a 24h TTL.

Measured on prod 2026-08-29 over ONE 10-minute window:
    955    requests to /research/digital-reform/contracts
    265    distinct client IPs
    453    carrying a NEGATIVE page number (contract_page=-42, -34, -1 ...)
    1.2 GB Laravel file cache across 10,851 entries

⚠ I first characterised this as external "parameter fuzzing". It was not — the
crawler was faithfully following links WE emitted. Worth remembering before
blaming a client for a URL space you generate.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
CTRL = os.path.join(ROOT, 'app/app/Http/Controllers/ProcurementController.php')
VIEWS = os.path.join(ROOT, 'app/resources/views')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def test_every_pagination_param_is_clamped():
    """⚠ A raw `$request->input('*_page')` reaches the forwarded query string,
    the API and the cache key. One unclamped param reopens the whole space."""
    src = _read(CTRL)
    raw = re.findall(r"\$\w*[Pp]age\s*=\s*\$request->input\(", src)
    assert not raw, (
        f'{len(raw)} pagination param(s) still read raw from the request — '
        'they must go through _page(), which floors at 1')
    assert 'private function _page(' in src, 'the clamp helper is gone'
    assert re.search(r'return max\(1,\s*\(int\)\s*\$request->input\(', src), \
        'the helper no longer floors at 1 and casts to int'


def test_the_helper_returns_an_int_not_a_string():
    """⚠ The value reaches the CACHE KEY, so '1', 1 and '01' would otherwise mint
    three entries for one page — the same explosion in a smaller register."""
    src = _read(CTRL)
    assert re.search(r'private function _page\([^)]*\):\s*int', src), \
        'the clamp helper no longer declares an int return type'


def test_no_disabled_pagination_link_carries_an_href():
    """⚠⚠ THE TRAP ITSELF. `disabled` is a CSS class on the <li>; the crawler
    follows the href on the <a> inside it regardless. Every such block must emit
    a <span> when disabled, so no link to page 0 or below is ever rendered."""
    offenders = []
    for d, _dirs, files in os.walk(VIEWS):
        for f in files:
            if not f.endswith('.blade.php'):
                continue
            p = os.path.join(d, f)
            lines = _read(p).splitlines()
            for i, ln in enumerate(lines):
                if re.search(r"page-item \{\{ .* \? 'disabled' : '' \}\}", ln):
                    nxt = lines[i + 1] if i + 1 < len(lines) else ''
                    if '@if(' not in nxt:
                        offenders.append(f'{os.path.relpath(p, ROOT)}:{i+1}')
    assert not offenders, (
        'these pagination blocks still render an href on a disabled link, which '
        f'is an unbounded URL space a crawler will walk: {offenders}')


def test_the_scanner_actually_looked():
    """⚠ A guard that walks the tree must assert it walked it — this repo has
    shipped a scanner that matched zero files and passed unconditionally."""
    n = sum(1 for d, _x, files in os.walk(VIEWS)
            for f in files if f.endswith('.blade.php'))
    assert n > 50, f'only scanned {n} blade templates — the walk is broken'
