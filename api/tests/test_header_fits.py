"""The site header must fit the viewport at every width.

⚠⚠ MEASURED 2026-09-18: it did not, on EVERY page of the site, across the whole
band **992 to 1227**. The drawer breakpoint was Bootstrap's `lg` (991.98) while
the desktop header's own content needs **1228px** — brand 163 + nav 825 +
search 180 + gaps — so above 992 the hamburger vanished, the full nav appeared,
and the page scrolled sideways by up to 236px. Half the tested matrix: **30 of
60** page/width combinations, including 1024 (iPad landscape) and 1200.

⚠ It was invisible below 992 only because the drawer block's own
`overflow-x: clip` was containing it — the clip is there for the off-canvas
drawer, and it happened to hide this too.

The two breakpoints are SWEPT, not chosen: with the search box hidden the header
fits from **1024**; as shipped it fits from **1228**. So the drawer runs to
1023.98 and the search box is hidden to 1227.98.

⚠ This reads the stylesheet, which is all a unit test can see. Whether the
header fits is geometry — 0 of 66 combinations scroll sideways with this
change, against 30 of 60 before — and that measurement is in the commit.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSS = os.path.join(ROOT, 'app/public/css/databook-components.css')


def _css():
    """⚠ CSS comments stripped first: the comments added with these rules quote
    every number and selector the scans below look for, and an own-prose firing
    is the single most common guard defect in this repo."""
    return re.sub(r'/\*.*?\*/', '', io.open(CSS, encoding='utf-8').read(), flags=re.S)


def _media_blocks():
    """(condition, body) for every top-level @media, by brace matching — a regex
    for `@media ... { ... }` stops at the FIRST inner `}` and would report every
    block as holding one rule."""
    css, out, i = _css(), [], 0
    while True:
        i = css.find('@media', i)
        if i < 0:
            return out
        j = css.index('{', i)
        cond = css[i + 6:j].strip()
        depth, k = 0, j
        while k < len(css):
            if css[k] == '{':
                depth += 1
            elif css[k] == '}':
                depth -= 1
                if depth == 0:
                    break
            k += 1
        out.append((cond, css[j + 1:k]))
        i = k


def test_the_nav_drawer_runs_to_the_width_at_which_the_bare_nav_fits():
    """Swept: with the search box hidden the header fits from 1024 up, so below
    that the drawer is the only layout that works."""
    drawers = [c for c, b in _media_blocks() if '.db-nav-toggle' in b and 'inline-flex' in b]
    assert drawers, 'no media query turns the nav drawer on any more'
    assert any(re.search(r'max-width:\s*1023\.98px', c) for c in drawers), (
        'the nav drawer breakpoint is no longer 1023.98 — at 992-1023 even the '
        'bare nav does not fit and the page scrolls sideways: ' + repr(drawers))


def test_the_header_search_is_hidden_until_the_full_header_fits():
    """Swept: as shipped the header needs 1228, and the search box is the only
    piece that does not fit below it."""
    hits = [c for c, b in _media_blocks()
            if re.search(r'\.db-header-search\s*\{[^}]*display:\s*none', b)]
    assert hits, 'nothing hides the header search box at narrow widths any more'
    assert any(re.search(r'max-width:\s*1227\.98px', c) for c in hits), (
        'the search box is no longer hidden up to 1227.98, so the header needs '
        '1228px on a viewport that may be 1024: ' + repr(hits))


def test_the_header_row_may_not_wrap():
    """⚠ Wrapping is the OTHER way to make the header fit, and it is the wrong
    one: it changes the rendered header height, and `--db-header-h` is what the
    sticky chrome, `.db-toc`, `.db-facets` and every in-page anchor offset
    themselves by. Measured across all 66 combinations, the header stays 56px."""
    css = _css()
    i = css.index('.db-header .db-header-inner')
    block = css[i:css.index('}', i)]
    assert 'flex-wrap' not in block, (
        'the header row may now wrap, which changes --db-header-h and moves '
        'every sticky offset and anchor on the site: ' + block)


def test_the_drawer_block_still_clips_horizontal_overflow():
    """`overflow-x: clip`, not `hidden` — hidden makes the element a scroll
    container and breaks `position: sticky` on the chrome above it. It is in the
    drawer block because that is where the off-canvas nav lives."""
    for cond, body in _media_blocks():
        if '.db-nav-toggle' in body and 'inline-flex' in body:
            assert 'overflow-x: clip' in body, (
                'the drawer block no longer clips horizontal overflow, so the '
                'off-canvas nav will scroll the page sideways')
            assert 'overflow-x: hidden' not in body, (
                '`hidden` here makes this a scroll container and breaks the '
                'sticky chrome — the comment beside it says so')
            return
    raise AssertionError('no drawer block found')
