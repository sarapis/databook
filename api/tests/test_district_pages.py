"""Guards for the district page's landing section.

⚠⚠ `projects` WAS HARDCODED AS THE LANDING SECTION FOR EVERY DISTRICT TYPE, AND
`sd` HAS NO `projects` SECTION AT ALL. A school district's sections are schools /
school-projects / enrollment; the CPDB commitment-plan dataset behind `projects`
carries no `sd` key in its map, so `DistDatasets::get('projects','sd')` returns
null and `Districts::projectSectionXHR` reaches its `abort(404)`. Both the bare
`/d/{type}-{id}-{dslug}` redirect and `Schema::district()`'s canonical url named
`projects` unconditionally, so every sd URL that did not spell out a section —
including each sd page's own canonical link — pointed at a guaranteed 404, while
`/d/sd-10-x/schools` served fine the whole time. Measured 2026-09-08: `sd` 1, 2,
10, 20 and 31 all 404 on `/projects`; `sd.geojson` contains every one of them, so
the id format was never the problem.

The property is therefore not "sd works" but "the section a district URL lands on
exists for that district type", asserted per routed type, which is what neither
layer checked.

These parse PHP as text rather than shelling out to `php`, so the guard stays
hermetic — and every parse asserts what it found, because a scanner that silently
matches nothing is indistinguishable from a codebase with no defect.
"""

import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
DS = os.path.join(ROOT, 'app', 'app', 'Custom', 'DistDatasets.php')
SCHEMA = os.path.join(ROOT, 'app', 'app', 'Custom', 'Schema.php')
WEB = os.path.join(ROOT, 'app', 'routes', 'web.php')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _prop_block(text, name):
    """The literal array assigned to `public $<name>`, brace-balanced."""
    m = re.search(r'public \$' + re.escape(name) + r'\s*=\s*\[', text)
    assert m, 'no `public $%s = [` in DistDatasets.php — this guard is looking at ' \
              'the wrong thing, and a guard that finds nothing passes' % name
    i = m.end() - 1
    depth = 0
    for j in range(i, len(text)):
        if text[j] == '[':
            depth += 1
        elif text[j] == ']':
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    raise AssertionError('unbalanced brackets in $%s' % name)


def _routed_types():
    """District types the /d/ routes actually accept, read from the constraint."""
    web = _read(WEB)
    found = set()
    for m in re.finditer(r"->where\('type',\s*'\^\(([a-z|]+)\)\$'\)", web):
        found.update(m.group(1).split('|'))
    assert len(found) >= 4, (
        'parsed %r from the district route constraints in routes/web.php — the '
        'scanner is wrong' % sorted(found))
    return sorted(found)


def _strip_php_comments(text):
    """`//` and `/* */` gone, quoted strings kept.

    ⚠ Line comments only outside a string, because a section's `description`
    legitimately contains a URL: `http://labs.council.nyc/districts/data/` is in
    `city-council-stat-cases`, and a naive `//` strip eats the rest of that line
    — which would delete the section's `'map'` and make the scanner report a
    section that has none.
    """
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    out, i, n = [], 0, len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote:
            if c == '\\' and i + 1 < n:
                out.append(text[i:i + 2]); i += 2; continue
            if c == quote:
                quote = None
            out.append(c); i += 1; continue
        if c in "'\"":
            quote = c; out.append(c); i += 1; continue
        if c == '/' and text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        out.append(c); i += 1
    return ''.join(out)


def _section_map_types():
    """{section: [district types its `map` admits]} — `get()`'s own 404 predicate.

    `DistDatasets::get($section,$type)` returns null, and every caller then
    404s, precisely when the section's `map` has no key for the type. So this
    reproduces that condition rather than a proxy for it.
    """
    # ⚠ Comments stripped for the same reason `_menu` strips them: a `'map'`
    # named inside a comment would be read as a section's real map.
    dd = _strip_php_comments(_prop_block(_read(DS), 'dd'))
    # Section keys sit at one indent inside $dd. ⚠ The trailing `[` may be
    # followed by a comment ('city-council-discretionary' has one), so do not
    # anchor the line end — doing so silently dropped that section.
    starts = [(m.start(), m.group(1))
              for m in re.finditer(r"(?m)^\t\t'([A-Za-z0-9-]+)' => \[", dd)]
    assert len(starts) >= 8, (
        'found only %r sections in $dd — the section scanner is wrong'
        % [n for _, n in starts])
    bounds = [p for p, _ in starts] + [len(dd)]
    out = {}
    for i, (_, name) in enumerate(starts):
        seg = dd[bounds[i]:bounds[i + 1]]
        m = re.search(r"'map' => \[(.*?)\]", seg, re.S)
        out[name] = re.findall(r"'([a-z]{2,3})' =>", m.group(1)) if m else []
    return out


def _menu():
    """{district type: [its section keys]}, group headings excluded.

    ⚠⚠ COMMENTS ARE STRIPPED FIRST — OWN-PROSE FIRING 24, and this one fired on
    a CORRECT file. The comment explaining why `projects` sits after `schools`
    in sd's menu names `defaultSection['sd']`, and `'sd'` followed by `]` rather
    than `=>` is exactly the shape this scanner reads as a section key. It was
    then reported as "menu section 'sd' was not parsed from $dd", i.e. as the
    non-vacuity assertion failing — a scanner reading prose as code, reporting a
    problem that is not there.
    """
    menu = _strip_php_comments(_prop_block(_read(DS), 'menu'))
    starts = [(m.start(), m.group(1))
              for m in re.finditer(r"(?m)^\t\t'([a-z]{2,3})' => \[", menu)]
    assert len(starts) >= 4, 'parsed %r from $menu — the scanner is wrong' % starts
    bounds = [p for p, _ in starts] + [len(menu)]
    out = {}
    for i, (_, t) in enumerate(starts):
        seg = menu[bounds[i]:bounds[i + 1]]
        # A quoted string followed by `=>` is a group heading ('Enrollment'),
        # not a section.
        out[t] = re.findall(r"'([A-Za-z0-9-]+)'(?!\s*=>)", seg)
        assert out[t], 'type %r parsed as an empty menu' % t
    return out


def _defaults():
    block = _prop_block(_read(DS), 'defaultSection')
    out = dict(re.findall(r"'([a-z]{2,3})'\s*=>\s*'([A-Za-z0-9-]+)'", block))
    assert out, 'parsed no entries from $defaultSection — the scanner is wrong'
    return out


def _districts_preset_calls(text):
    """Every `route('districtsPreset', …)` call, as its balanced argument list.

    ⚠ Scoped to the CALL, not the file and not the line: the prose explaining
    this defect names 'projects', so a whole-file scan would fire on its own
    explanation — and the redirect is a multi-line closure, so a line-scoped
    slice stops before the argument that matters.
    """
    # ⚠⚠ STRIP PHP COMMENTS FIRST — OWN-PROSE FIRING 23. The comment in
    # `web.php` explaining why the id/slug separator is an underscore quotes
    # `route('districtsPreset', …)` verbatim, so the scanner counted the prose
    # documenting the fix as a URL builder and the count assertion failed on a
    # correct file.
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'^\s*//.*$', '', text, flags=re.M)
    out = []
    for m in re.finditer(r"route\('districtsPreset'", text):
        i = text.index('(', m.start())
        depth = 0
        for j in range(i, len(text)):
            if text[j] == '(':
                depth += 1
            elif text[j] == ')':
                depth -= 1
                if depth == 0:
                    out.append(text[i:j + 1])
                    break
        else:
            raise AssertionError('unbalanced parens in a districtsPreset call')
    return out


def test_every_routed_district_type_has_a_landing_section_that_exists_for_it():
    """The section a district URL lands on must exist for that district type.

    Verified by reintroducing the bug: setting sd's default back to 'projects'
    fails here naming sd, because `projects`'s map carries only cd/cc/nta.
    """
    types = _routed_types()
    defaults = _defaults()
    maps = _section_map_types()
    menu = _menu()

    # Non-vacuity: every section the menus name must have been parsed out of
    # $dd, or a missed section would quietly skip its own check.
    named = {s for sections in menu.values() for s in sections}
    missing = sorted(named - set(maps))
    assert not missing, (
        'these menu sections were not parsed from $dd: %r — the parse regressed '
        'and the checks below would silently pass' % missing)

    for t in types:
        assert t in defaults, (
            'district type %r is routed but declares no landing section; add it '
            'to DistDatasets::$defaultSection. defaultSection() falls back to '
            'the first menu item so it cannot 404, but the choice must be '
            'explicit rather than incidental.' % t)
        d = defaults[t]
        assert d in maps, 'type %r lands on %r, which is not a section' % (t, d)
        assert t in maps[d], (
            "district type %r lands on section %r, but %r's map admits only %r "
            "— DistDatasets::get(%r,%r) returns null and every caller abort(404)s. "
            "This is the sd defect: %r has no sd key." % (
                t, d, d, maps[d], d, t, d))
        assert d in menu.get(t, []), (
            'type %r lands on %r, which is not in its own menu, so the page '
            'would render with no nav item marked active' % (t, d))


def test_no_district_url_hardcodes_the_landing_section():
    """Both places that build a section-less district URL must ask the owner.

    Two independent spellings of "the landing section" is what let a value that
    is invalid for one type be published as the default for all four. Verified
    by reintroducing each literal in turn: each names its own file and the
    section it pinned.
    """
    for path in (WEB, SCHEMA):
        calls = _districts_preset_calls(_read(path))
        # ⚠ AT LEAST ONE, AND EVERY ONE — not "exactly one". This used to pin the
        # count, which is an anti-vacuum check wearing the property's clothes: a
        # second LEGITIMATE builder was added when the district URL separator
        # became `_` (a legacy-shape redirect), and the count failed while the
        # property it guards still held on both calls. Asserting the property on
        # EVERY call is strictly stronger than asserting it on the only one.
        assert calls, (
            'no route(\'districtsPreset\', …) call found in %s — the scanner is '
            'wrong, or the URL builder moved' % os.path.basename(path))
        for call in calls:
            assert 'defaultSection' in call, (
                '%s builds a district URL without asking '
                'DistDatasets::defaultSection() for the section: %s'
                % (os.path.basename(path), ' '.join(call.split())))
            lit = re.search(r"'section'\s*=>\s*'([A-Za-z0-9-]+)'", call)
            assert not lit, (
                "%s hardcodes 'section' => %r. `projects` does not exist for sd, "
                "so a literal here 404s a whole district type." % (
                    os.path.basename(path), lit.group(1)))
