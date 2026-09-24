"""A RATCHET on colour drift in the site's CSS.

⚠ WHY A RATCHET AND NOT A ONE-TIME CLEANUP. `app/public/css/style.css` accumulated 51
distinct off-palette colours over years — Bootstrap greys, Tailwind slates, ad-hoc
blues — beside a fully tokenized design system. A cleanup fixes that once; this repo's
own history says the snapshot is what fails ("an exclusion list is a snapshot; new
files land in old categories"). So the count is PINNED and may only go down: the
cleanup can land in reviewable batches, each lowering the ceiling, and when it reaches
zero this becomes the permanent "no new drift" invariant with no further work.

⚠ THE PALETTE IS PARSED FROM DECLARATIONS, NOT FROM THE FILE'S TEXT. `databook-tokens.css`
documents the values it replaced in comments — `--db-gray-100: #f0f2f4;  /* was #f0f0f0 */`
— so a naive hex scan of that file reads HISTORICAL values as current palette. I made
exactly that mistake while sizing this work and reported `#f0f0f0` and `#4299e1` as
"already token values"; they are drift, and the handoff had them right.

⚠ 3-DIGIT SHORTHAND COUNTS. The handoff's proposed check was
`grep -oE '#[0-9a-fA-F]{6}'`, which cannot see `#fff` (32 occurrences) or `#000` (13).
A check that cannot see half the problem is the guard-that-scanned-zero-files pattern.
"""
import os
import re
from collections import Counter

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
TOKENS = os.path.join(ROOT, 'app/public/css/databook-tokens.css')
STYLE = os.path.join(ROOT, 'app/public/css/style.css')

# The ratchet. Lower these as batches land; never raise them.
# ⚠ ZERO. The ratchet has reached its floor, so this is no longer "drift may only
# shrink" — it is "no literal colour in style.css, full stop". 99 -> 60 (the 39
# near-identical values) -> 16 (deleting 78 fossil rule blocks whose selectors cannot
# match) -> 0 (the 16 that genuinely render).
MAX_OFF_PALETTE_HEX = 0
MIN_TOKEN_REFERENCES = 134        # var(--db-*) uses, so a swap cannot be undone.
                                  # Fell 143 -> 118 deleting the fossil rules
                                  # (they used tokens too), then rose to 134.


def _norm(h):
    h = h.lower()
    return '#' + ''.join(c * 2 for c in h[1:]) if len(h) == 4 else h


def _palette():
    """Every colour a token actually declares."""
    src = open(TOKENS, encoding='utf-8').read()
    decl = re.findall(r'(--db-[a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})\s*;', src)
    assert len(decl) > 30, f"only {len(decl)} token declarations parsed -- palette is vacuous"
    palette = {_norm(v) for _, v in decl}
    # ⚠⚠ A TOO-WIDE PALETTE DEFEATS THE RATCHET SILENTLY, and an empty one does not:
    # widening makes drift count as compliant, so the count falls and every assertion
    # passes. Found by mutation — pointing this parser at every hex in the file (the
    # mistake I made by hand) was NOT caught until this check existed. These three
    # values appear ONLY in the token file's "(was #…)" comments, so their presence
    # proves the parser has started reading prose as palette.
    for historical in ('#f0f0f0', '#f9f9f9', '#1a3a5c'):
        assert historical in src, f"{historical} is no longer in the token comments -- pick another canary"
        assert historical not in palette, (
            f"the palette parser is reading the token file's COMMENTS: {historical} is a "
            f"historical value, not a declaration. That silently widens the palette and "
            f"makes the drift ratchet vacuous.")
    return palette


def _strip_css_comments(css):
    """⚠ A COMMENT IS NOT A PAINTED COLOUR, and this guard fired on its own prose the
    moment style.css gained a comment quoting the values it had removed — the same
    trap as reading the token file's "(was #f0f0f0)" notes as palette. Strip first."""
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def _off_palette(css):
    palette = _palette()
    return [h for h in re.findall(r'#[0-9a-fA-F]{3,8}\b', _strip_css_comments(css))
            if _norm(h) not in palette]


def test_the_ratchet_states_what_it_does_not_cover():
    """⚠ ZERO HEX IS NOT ZERO LITERALS, and claiming otherwise would be the kind of
    reassuring measurement this repo keeps paying for. Still in style.css and NOT
    counted: 15 named colours (`white`, `red`, `green`, `orange`) and 41 rgb()/rgba()
    values — most of the latter are alpha overlays that no hex token can express, which
    is why they were left rather than forced onto the palette. This test exists so the
    limit is written down beside the ceiling, not discovered later.
    """
    css = _strip_css_comments(open(STYLE, encoding='utf-8').read())
    named = re.findall(r'(?<![-\w#])(white|black|red|blue|green|orange)\b(?!\s*[-\w])', css, re.I)
    rgba = re.findall(r'\brgba?\([^)]*\)', css)
    assert len(named) <= 15, (
        f"named colour literals grew to {len(named)} from 15 -- the hex ratchet does "
        f"not see these, so they need their own decision, not silent growth")
    assert len(rgba) <= 41, f"rgb()/rgba() literals grew to {len(rgba)} from 41"


def test_colour_drift_in_style_css_only_ever_goes_down():
    css = open(STYLE, encoding='utf-8').read()
    assert len(css) > 10_000, "style.css looks truncated -- the scan would be vacuous"
    off = _off_palette(css)
    assert len(off) <= MAX_OFF_PALETTE_HEX, (
        f"colour drift went UP: {len(off)} off-palette literals against a ceiling of "
        f"{MAX_OFF_PALETTE_HEX}. Use a token from databook-tokens.css, or lower the "
        f"ceiling in the same commit if you are fixing drift. Most common now: "
        f"{Counter(_norm(h) for h in off).most_common(5)}")


def test_the_mechanical_token_swap_cannot_be_undone():
    """101 literals that were provably identical to a token became `var()` references.
    Swapping any back would not raise the off-palette count (they are ON palette), so
    the ratchet above cannot see it — this floor can."""
    css = open(STYLE, encoding='utf-8').read()
    refs = len(re.findall(r'var\(--db-', _strip_css_comments(css)))
    assert refs >= MIN_TOKEN_REFERENCES, (
        f"token references dropped to {refs} from {MIN_TOKEN_REFERENCES} -- a var() "
        f"was replaced with a literal")


def test_the_ceiling_is_zero_so_the_ratchet_cannot_go_slack():
    """⚠ A ceiling above the real count is a ratchet that has stopped ratcheting: drift
    could double and still pass. It is now 0, which is the only value that needs no
    maintenance — every literal is a failure, so there is nothing to keep in step."""
    assert MAX_OFF_PALETTE_HEX == 0, (
        "the ceiling was raised. Colour drift in style.css reached zero on 2026-08-14; "
        "raising it re-opens the door instead of using a token.")
    assert not _off_palette(open(STYLE, encoding='utf-8').read())


def test_style_css_never_redeclares_a_design_token():
    """⚠⚠ A SECOND DECLARATION SITE, one layer down from the ones this repo fixed in
    the API today. `style.css` opened with a `:root` block redeclaring 15 `--db-*`
    tokens, NINE of them with the same name and a different value — its own
    `--db-shadow-sm: rgba(0,0,0,0.05)` against the canonical `rgba(11,31,58,0.06)`,
    `--db-transition: 0.2s` against `0.18s`.

    Every one was dead: `databook-tokens.css` loads later and won every collision,
    measured on the live site. Dead and WRONG is worse than duplicated — anyone
    reading style.css saw values the site does not use. The canonical file is the only
    place a token may be declared.
    """
    css = open(STYLE, encoding='utf-8').read()
    decls = re.findall(r'(?m)^\s*(--db-[a-z0-9-]+)\s*:', css)
    assert not decls, (
        f"style.css declares design tokens again: {sorted(set(decls))}. Tokens live in "
        f"databook-tokens.css; this file may only reference them with var().")
    # …and it must still be USING them, or "no declarations" is trivially satisfied by
    # a file that went back to literals.
    assert len(re.findall(r'var\(--db-', _strip_css_comments(css))) >= MIN_TOKEN_REFERENCES


# ---------------------------------------------------------------------------
# ⚠⚠ CONTRAST: every -fg must clear WCAG AA on its own -bg.
#
# THE DEFECT THIS EXISTS FOR (found 2026-09-01, by measuring the pairs rather
# than looking at them). The Analysis (orange) surface failed AA on every light
# fill it used — `--db-brand` #ff941f as TEXT on `--db-brand-bg` #fff3e6 is
# **2.02:1**, and on `--db-brand-wash` #fff8f0 **2.10:1**, against the 4.5:1 that
# 13px bold needs (WCAG large text starts at 18.66px bold, so the badge does not
# qualify for 3:1).
#
# ⭐ THE CAUSE WAS A MISSING TOKEN, NOT FIVE BAD VALUES. Every other semantic
# family shipped a -fg beside its -bg; the brand family shipped -bg and -wash and
# no -fg, so an author wanting "orange text on the orange fill" had exactly one
# token to reach for and it was the saturated identity colour meant for borders
# and text on NAVY. Five rules independently made that same reasonable choice.
# Adding the token is what stops the sixth.
#
# ⚠ IT WAS STRUCTURAL, NOT A ONE-OFF: themes/wegov-theme.css overrides only the
# brand slots per docs/THEMING.md and inherited the same bug for free (2.91 and
# 3.14). So this guard reads the THEMES too — a future sibling brand that
# supplies a -bg without a -fg fails here rather than in someone's audit.
_AA_NORMAL = 4.5


def _rel_luminance(hex_colour):
    h = hex_colour.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    r, g, b = f(r), f(g), f(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _rel_luminance(a), _rel_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _token_hexes(path):
    """{token name: #hex} for tokens declared with a literal hex in this file."""
    css = _strip_css_comments(open(path, encoding='utf-8').read())
    return {m.group(1): m.group(2)
            for m in re.finditer(r'(--db-[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;', css)}


def _theme_files():
    out = [TOKENS]
    tdir = os.path.join(ROOT, 'app/public/css/themes')
    if os.path.isdir(tdir):
        out += [os.path.join(tdir, f) for f in sorted(os.listdir(tdir)) if f.endswith('.css')]
    return out


def test_every_foreground_token_clears_aa_on_its_own_background():
    checked = 0
    failures = []
    for path in _theme_files():
        toks = _token_hexes(path)
        for name, fg in toks.items():
            if not name.endswith('-fg'):
                continue
            family = name[:-3]
            # a family's fills: -bg always, plus -wash where it has one (brand does)
            for suffix in ('-bg', '-wash'):
                bg = toks.get(family + suffix)
                if not bg:
                    continue
                checked += 1
                ratio = _contrast(fg, bg)
                if ratio < _AA_NORMAL:
                    failures.append(
                        f"{os.path.basename(path)}: {name} {fg} on {family + suffix} {bg} "
                        f"= {ratio:.2f}:1 (AA needs {_AA_NORMAL})")
    # ⚠ A guard that checks zero pairs passes. This repo's oldest defect.
    assert checked >= 5, f"only {checked} fg/bg pairs checked — the parser is not finding them"
    assert not failures, "contrast failures:\n  " + "\n  ".join(failures)


def test_a_family_with_a_light_fill_also_ships_a_foreground():
    """⚠ THE ROOT CAUSE, pinned. A family offering a -bg but no -fg leaves an
    author only the saturated identity colour to put on it — which is exactly how
    five Analysis rules landed at 2.02:1. Applies to the themes too, so a sibling
    brand cannot inherit the bug by overriding only the fills.
    """
    missing = []
    for path in _theme_files():
        toks = _token_hexes(path)
        for name in toks:
            if not name.endswith('-bg'):
                continue
            family = name[:-3]
            # themes legitimately override a subset; only complain when the theme
            # redefines the FILL, since that is what makes the inherited fg wrong.
            if family + '-fg' not in toks:
                missing.append(f"{os.path.basename(path)}: {family}-bg has no {family}-fg")
    assert not missing, (
        "a light fill without a foreground token:\n  " + "\n  ".join(missing))


def test_no_rule_puts_the_identity_colour_as_text_on_a_brand_fill():
    """⚠ The token guard above fixes the CAUSE; this one catches the SHAPE.

    A new rule could still write `color: var(--db-brand)` alongside
    `background: var(--db-brand-bg)` — which is precisely the five-rule defect,
    at 2.02:1. So scan declaration blocks: any block that sets a brand fill as
    its background must not also set --db-brand as its colour.

    ⚠ `--db-brand` on DARK stays correct and is untouched by this — the wordmark
    is 6.16:1 on the header navy and the Analysis toggle 5.16:1 on navy-600.
    Those blocks set no brand background, so they never match.
    """
    css = _strip_css_comments(
        open(os.path.join(ROOT, 'app/public/css/databook-components.css'),
             encoding='utf-8').read())
    offenders = []
    blocks = 0
    for m in re.finditer(r'([^{}]+)\{([^{}]*)\}', css):
        selector, body = m.group(1).strip(), m.group(2)
        blocks += 1
        fills_brand = re.search(r'background\s*:\s*[^;]*var\(--db-brand-(bg|wash)\)', body)
        text_brand = re.search(r'(?<!-)\bcolor\s*:\s*var\(--db-brand\)\s*;', body)
        if fills_brand and text_brand:
            offenders.append(selector.replace('\n', ' ')[:90])
    assert blocks > 200, f"only {blocks} rule blocks parsed — the scan is not looking"
    assert not offenders, (
        "--db-brand used as TEXT on a brand fill (2.02:1 — use --db-brand-fg):\n  "
        + "\n  ".join(offenders))


def test_a_clipping_box_never_holds_an_unwrappable_value():
    """⚠⚠ A CLIPPED NUMBER IS A WRONG NUMBER, AND EVERY DOM AND GEOMETRY CHECK
    PASSES ON ONE. `.db-stat` is `overflow: hidden`, so a value too wide for its
    grid column is simply CUT — measured on the capital project profile:
    `Construction Procurement` rendered as "Constructio / Procuremer",
    `Not published` lost 8px and `$105.7M` lost 4px. The element existed, was the
    right size, and contained the right text in all three cases; it was found by
    looking at the render, not by a check.

    Two properties keep it from recurring, and BOTH are needed — the wrap alone
    still looks wrong at a very narrow column, and the width alone still clips a
    long phase name:
      * `.db-stat-value` must allow a long value to WRAP rather than vanish;
      * `.db-stat-grid`'s column minimum must be at least 160px.
    """
    css = _strip_css_comments(
        open(os.path.join(ROOT, 'app/public/css/databook-components.css'),
             encoding='utf-8').read())

    stat = re.search(r'\.db-stat\s*\{([^}]*)\}', css)
    assert stat, '.db-stat is gone'
    clips = 'overflow' in stat.group(1) and 'hidden' in stat.group(1)

    value = re.search(r'\.db-stat-value\s*\{([^}]*)\}', css)
    assert value, '.db-stat-value is gone'
    wraps = re.search(r'overflow-wrap\s*:\s*(anywhere|break-word)', value.group(1))
    assert not clips or wraps, (
        '.db-stat clips its overflow and .db-stat-value cannot wrap, so a long '
        'value is silently cut off rather than wrapped')

    grid = re.search(r'\.db-stat-grid\s*\{([^}]*)\}', css)
    assert grid, '.db-stat-grid is gone'
    mm = re.search(r'minmax\(\s*(\d+)px', grid.group(1))
    assert mm, f'the stat grid declares no column minimum: {grid.group(1).strip()}'
    assert int(mm.group(1)) >= 160, (
        f'the stat grid column minimum is {mm.group(1)}px — measured, 150px '
        f'clips `$105.7M` at 30px bold')
