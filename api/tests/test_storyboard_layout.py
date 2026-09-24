"""The Digital Services storyboard's layout rules (2026-09-18).

⚠⚠ THE STORYBOARD HAD ZERO RESPONSIVE RULES IN 928 LINES, and the reason is
structural rather than an oversight: every layout in it is an inline `style=`
attribute transcribed from the design handoff, and no media query can reach an
inline style. So the narrow-width behaviour lives in ONE `<style>` block in the
partial, and these guards pin the two properties that were measured broken.

⚠ What only a browser can answer — is the rail actually painting over a data
card at this scroll position — is `scripts/headless/verify_overview_bands.py`.
This repo has measured a stat tile that existed, sat in the right place, held
the right text and was CLIPPED; geometry is not a source question.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SB = os.path.join(ROOT,
                  'app/resources/views/procurement/partials/digital-services-storyboard.blade.php')
JS = os.path.join(ROOT, 'app/public/js/digital-services-storyboard.js')


def _read(p):
    return io.open(p, encoding='utf-8').read()


def _markup():
    """⚠ Blade comments stripped FIRST. The comments added with these rules
    quote the very selectors and properties the scans below look for, which is
    the single most common guard defect in this repo (fourteen firings and
    counting)."""
    return re.sub(r'\{\{--.*?--\}\}', '', _read(SB), flags=re.S)


def _style_block():
    """The partial's one <style> block, with CSS comments removed for the same
    reason — the comment explaining the bar-row fix names `flex: 1`."""
    m = re.search(r'<style>(.*?)</style>', _markup(), re.S)
    assert m, 'the storyboard has no <style> block — the narrow-width rules are gone'
    return re.sub(r'/\*.*?\*/', '', m.group(1), flags=re.S)


def _js_function(name):
    """The body of one JS function, by brace matching. ⚠ Scoped to the function
    rather than the file, because a file-wide scan is satisfied by any sibling.
    ⚠⚠ AND THE NAME NEEDS ITS PAREN: `function set` matched `setInitial` on the
    first run of this file and the guard failed on correct code, which is the
    same defect one level down — a locator answered by a longer name."""
    src = _read(JS)
    i = src.index('function ' + name + '(')
    j = src.index('{', i)
    depth, k = 0, j
    while k < len(src):
        if src[k] == '{':
            depth += 1
        elif src[k] == '}':
            depth -= 1
            if depth == 0:
                return src[j:k + 1]
        k += 1
    raise AssertionError('unbalanced braces reading ' + name)


def _rail_nav_tag():
    """The opening tag of the <nav> that holds the rail dots — located from the
    dots themselves, so renaming the element cannot make this pass by accident."""
    mk = _markup()
    i = mk.index('data-rail-dot')
    j = mk.rindex('<nav', 0, i)
    return mk[j:mk.index('>', j) + 1]


def test_the_rail_starts_hidden_so_a_js_failure_cannot_leave_it_over_the_data():
    """⚠⚠ MEASURED 2026-09-18: this `position: fixed` rail was painting over the
    Overview's own data cards at EVERY width below 1600 — the card's left edge
    is 24px and the rail's right edge is 35px — and it was visible at 1440, the
    width every verification in this repo uses. Nothing in the document flow can
    push a fixed element aside, so the only thing that keeps it off the data is
    the JS that places it. That makes the markup default load-bearing: with no
    JS, or a JS error, the failing state must be "no rail", never "a rail over
    the data"."""
    tag = _rail_nav_tag()
    assert 'display: none' in tag, (
        'the rail nav no longer starts hidden, so a JS failure paints it over '
        'the data bands: ' + tag)


def test_the_rail_is_placed_by_both_the_storyboards_rect_and_a_width_floor():
    """Two conditions, and they answer different questions: is the rail still
    indicating progress through something on screen, and is there a gutter for
    it to sit in. Measured — the story's own body copy clears the rail only from
    768 up; at 620 the gap is 2px."""
    body = _js_function('place')
    assert 'getBoundingClientRect' in body, (
        'place() no longer asks where the storyboard is, so the rail follows '
        'the reader down into the data bands')
    assert 'innerWidth' in body, (
        'place() no longer asks whether there is room, so the rail paints over '
        'the story text on a phone')
    assert 'style.display' in body, 'place() no longer shows or hides anything'
    # ⚠ The floor is a measurement, not a preference. Pinned so that lowering it
    # is a deliberate edit with this sentence in front of the editor.
    assert re.search(r'RAIL_MIN_WIDTH\s*=\s*768\b', _read(JS)), (
        'the rail width floor moved off the measured crossover of 768')


def test_the_ways_in_panels_are_one_column_and_their_tables_are_reachable():
    """⚠⚠ MEASURED AT 390: 27 elements of the four illustrative tables sat past
    the right edge with NO scrollable ancestor — "Ceiling", "Paid under this
    id", "Contracts", "Sells" and every value under them. The panels laid out
    two desktop columns with a 76px indent on a 342px screen."""
    css = _style_block()
    panel = re.search(r'\[data-x7-panel\]\s*>\s*div\s*\{([^}]*)\}', css)
    assert panel, 'the Ways-in panel no longer collapses to one column'
    assert '1fr' in panel.group(1) and 'padding-left' in panel.group(1)
    assert 'overflow-x: auto' in css, (
        "the mini-tables' own `overflow: hidden` is what makes their far "
        'columns unreachable rather than merely off-screen')


def test_the_bar_row_scrolls_rather_than_squeezing_its_money_labels():
    """⚠⚠ THE BAR ROW OVERFLOWED BY ITS LABELS, NOT ITS BARS. Nine columns at
    `flex: 1` cannot shrink below their own min-content width, and that is the
    money label — `$1.20B` is 47px at 13px mono, so nine of them plus eight gaps
    need 415px against a 336px row and the last two years sat off-screen.
    Shrinking the type to fit would need about 8px; hiding the labels would
    delete the figures."""
    css = _style_block()
    assert re.search(r'\[data-sb-bars\]\s*\{[^}]*overflow-x:\s*auto', css), (
        'the bar row no longer scrolls, so its last years are unreachable at '
        'phone width')
    assert re.search(r'\[data-sb-bar\]\s*\{[^}]*flex:\s*0 0 auto', css), (
        'the bars shrink again, which squeezes the money labels rather than '
        'scrolling them')


def test_every_narrow_width_selector_has_something_to_match():
    """⚠ A RULE WITH NO TARGET IS INERT AND READS AS A FIX. This repo has
    measured exactly that twice — `.db-page-lead { max-width: none }` in a
    `@section('head')`, and the `.tt-suggestion` rules that looked dead. Each
    attribute these rules key on is asserted present in the markup, so renaming
    a hook cannot quietly switch the whole block off."""
    mk = _markup()
    body = re.sub(r'<style>.*?</style>', '', mk, flags=re.S)
    for hook in ('data-x7-panel', 'data-sb-bars', 'data-sb-bar'):
        assert hook in body, (
            'the narrow-width block styles [%s] and nothing in the markup '
            'carries it' % hook)
    # The substring selectors are the fragile ones: they match on an inline
    # style's own text, so a restyle silently un-targets them.
    assert 'border-radius: 8px' in body, (
        'the mini-table selector matches on an inline `border-radius: 8px` and '
        'no element carries it any more')
    assert 'border-radius: 999px' in body, (
        'the pill selector matches on an inline `border-radius: 999px` and no '
        'element carries it any more')


def test_the_subtitle_measures_itself_instead_of_assuming_two_lines():
    """⚠ `sub.style.maxHeight = '80px'` is two lines at desktop type. At 390 the
    same sentence wraps to four or five, so the last line was sliced through the
    middle of its glyphs — "plus the searchable ind" with the rest cut off. A
    clipped line is a wrong line, and this repo has already paid for a clipped
    stat value ("$105.7M" losing 4px)."""
    body = _js_function('set')
    assert 'scrollHeight' in body, (
        'the Ways-in subtitle no longer measures itself, so it clips at any '
        'width where it wraps past the assumed height')
    assert not re.search(r"maxHeight\s*=\s*show\s*\?\s*'\d+px'", body), (
        'the subtitle height is a magic number again')
