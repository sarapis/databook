"""The site footer's link columns must be reachable at phone width.

⚠⚠ MEASURED 2026-09-18 ON EVERY PAGE OF THE SITE: at 390 the footer's five grid
tracks totalled **719px inside a 366px box**, so `Sections`, `Contribute`,
`About` and `Social` — sixteen links — sat off the right edge. And the page does
not scroll sideways, so they were not merely off-screen, they were UNREACHABLE.
Present since the design-system migration (2026-06-16) and live on production.

The cause is a CSS default that reads as flexible and is not: **`1fr` is
`minmax(auto, 1fr)`**, so a track never shrinks below its own content, and the
first column holds a newsletter `<input>` whose min-content is about 300px.

⚠ This guard reads the STYLESHEET, which is the only thing a unit test can see.
Whether the columns actually fit is geometry, and this repo has measured a stat
tile that existed, sat in the right place, held the right text and was clipped —
so the real check is a browser at 320/390/576, recorded in the commit.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSS = os.path.join(ROOT, 'app/public/css/databook-components.css')


def _css():
    """⚠ CSS comments stripped first. The comment added with this rule names
    both `1fr` and `minmax(0`, so a naive scan passes on a file whose rule has
    been deleted — the own-prose firing this repo has now paid for fourteen
    times."""
    return re.sub(r'/\*.*?\*/', '', io.open(CSS, encoding='utf-8').read(), flags=re.S)


def _blocks(selector):
    """Every declaration block for one selector, in source order."""
    return re.findall(re.escape(selector) + r'\s*\{([^}]*)\}', _css())


def test_the_footer_columns_have_a_narrow_width_override():
    """Without one, four of the five tracks are off-screen below 768."""
    blocks = _blocks('.db-footer .db-footer-cols')
    assert len(blocks) >= 2, (
        'the footer grid has only its desktop declaration again, so its four '
        'link columns are unreachable at phone width')
    narrow = [b for b in blocks if 'minmax(0' in b]
    assert narrow, (
        'the narrow-width footer rule no longer uses minmax(0, …) — `1fr` alone '
        're-floors each track at its own content and the columns blow out again')


def test_the_narrow_override_is_inside_a_max_width_media_query():
    """⚠ A rule that is not in a media query is not an override, it is a
    replacement — it would stack the footer on a 1440 desktop too."""
    css = _css()
    i = css.index('minmax(0, 1fr))', css.index('.db-footer .db-footer-cols'))
    before = css[:i]
    # the nearest enclosing at-rule: the last '@media' with no closing brace
    # between it and here beyond its own block's
    j = before.rindex('@media')
    assert re.match(r'@media\s*\(max-width:\s*7\d\d(\.\d+)?px\)', before[j:j + 40]), (
        'the narrow footer rule is not inside a max-width media query: '
        + before[j:j + 60])


def test_the_first_column_spans_the_row_so_the_newsletter_is_not_squeezed():
    """The brand column carries the newsletter input; at 366px two tracks give
    it 175px, which is narrower than the input's own minimum. Spanning the row
    is what lets the other four sit two-up beneath it."""
    assert re.search(
        r'\.db-footer \.db-footer-cols > div:first-child\s*\{[^}]*grid-column:\s*1 / -1',
        _css()), (
        'the footer brand column no longer spans the row, so the newsletter '
        'input re-floors its track')
