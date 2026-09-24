"""`/notices` must not put a Bootstrap `.row` inside an `.organization_data` column.

⚠⚠ MEASURED 2026-09-18 ON LIVE PROD: `/notices` was the ONE page of thirteen
that scrolled sideways at a 1024px viewport, by 12px. The cause is a collision
between two rules that never meet anywhere else:

  * `responsive.css`'s `@media (max-width: 1024px)` sets
    `.organization_data { padding: 20px 0px 20px }` — no HORIZONTAL padding;
  * a nested `.row` carries `margin: 0 -12px`, whose whole job is to cancel a
    column's 12px padding.

With the padding gone the gutters cancel nothing, so the row overhangs its
column by 12px each side. On the RIGHT-hand column there is no page padding
left to absorb it. Below 1024 the nav drawer's `overflow-x: clip` hid it; at
exactly 1024 that clip is off (its query is `max-width: 1023.98px`), so the
overhang became a scrollbar. **The defect lived in a one-pixel gap between two
media queries.**

⚠ The fix is local markup, not CSS: a `.row` + `.col-md-12.text-center` around a
single centred button does nothing that `text-center` alone does not, and
measured before/after the buttons do not move by one pixel at 390, 768, 1100 or
1440. A CSS fix scoped to `.organization_data` would have reached **22 views**
to correct 12px on one, which is the kind of blast radius this repo asks you not
to take on trust.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VIEW = os.path.join(ROOT, 'app/resources/views/notices.blade.php')


def _markup():
    """⚠ Blade comments stripped FIRST. The comment added with this fix quotes
    `row justify-content-center` verbatim to explain what it replaced, so a scan
    of the raw text fires on its own explanation — the most common guard defect
    in this repo, now at fourteen firings."""
    return re.sub(r'\{\{--.*?--\}\}', '', io.open(VIEW, encoding='utf-8').read(), flags=re.S)


_DIV = re.compile(r'<div\b[^>]*>|</div>', re.I)


def _rows_inside_organization_data(markup):
    """Every `.row` that is a DESCENDANT of an `.organization_data` element.

    ⚠ Depth-counted, not a substring search: `organization_data` and `row` both
    appear all over this view, and 'a row somewhere after an organization_data'
    is not the property — the property is NESTING."""
    hits, stack = [], []
    for m in _DIV.finditer(markup):
        tag = m.group(0)
        if tag.startswith('</'):
            if stack:
                stack.pop()
            continue
        cls = re.search(r'class\s*=\s*"([^"]*)"', tag)
        classes = (cls.group(1) if cls else '').split()
        inside = any(stack)
        if inside and 'row' in classes:
            hits.append(markup[max(0, m.start() - 0):m.start() + 90].strip())
        stack.append('organization_data' in classes or inside)
    return hits


def test_no_bootstrap_row_is_nested_inside_an_organization_data_column():
    hits = _rows_inside_organization_data(_markup())
    assert not hits, (
        "a `.row` is nested inside `.organization_data` again — below 1024 that "
        "column has no horizontal padding for the row's -12px gutters to cancel, "
        "so it overhangs by 12px and /notices scrolls sideways at exactly 1024:\n"
        + "\n".join(hits[:3]))


def test_the_guard_can_actually_see_a_nested_row():
    """⚠ NON-VACUITY. A depth counter with an off-by-one reports zero on every
    input, which is indistinguishable from a clean file — this repo's oldest
    defect. Feed it the exact markup that was removed and require a hit."""
    sample = ('<div class="row justify-content-center">'
              '<div class="col-md-6 organization_data">'
              '<div class="row justify-content-center">'
              '<div class="col-md-12 text-center">x</div></div></div></div>')
    assert _rows_inside_organization_data(sample), (
        'the guard cannot see a row nested inside organization_data, so its '
        'clean verdict on the real view means nothing')


def test_the_guard_does_not_fire_on_a_row_that_merely_follows_one():
    """The outer rows on this page — the ones that CONTAIN the
    `.organization_data` columns — are correct and must stay."""
    sample = ('<div class="row justify-content-center">'
              '<div class="col-md-6 organization_data">ok</div></div>'
              '<div class="row justify-content-center">'
              '<div class="col-12">also ok</div></div>')
    assert not _rows_inside_organization_data(sample)
