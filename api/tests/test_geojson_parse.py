"""Guards for how the frontend parses a GEO_JSON string served by the API.

⚠⚠ THE BUG THIS EXISTS TO STOP. Callers historically did
`JSON.parse(s.replaceAll('""', '"'))`, undoing CSV quote-doubling. The API serves
clean JSON straight from Postgres, so that replace is unnecessary — and on
correctly-escaped JSON it CORRUPTS the value. A project named  Plaza"A"  is
stored with its quotes escaped as  \\"A\\" , and the replace collapses the
trailing  \\""  into  \\" , which unterminates the string.

Measured 2026-09-04 over every capital project carrying geometry in the newest
publication (`capitalprojectsdollarscomp`, PUB_DATE 20231026): **all 3,082 parse
as served, and exactly one fails after the replace** — `P-1PELHAM`, "Pelham
Parkway Malls-Plaza"A"" (Parks). Each call site wraps the parse in a per-row
try/catch, so the project was SILENTLY ABSENT from the map rather than erroring:
5,337 features drawn where there should be 5,338.

⚠ The fallback is deliberately kept in `parseGeoJSON`. It can only widen what
parses, never narrow it, so a genuinely quote-doubled source still works.

⚠ Scope: the views that render CAPITAL project geometry. ⚠ Corrected
2026-09-09: this said "the FOUR views" and the guard hardcoded them.
`projects.blade.php` was rewritten onto the capital spine and now fetches
`/get/capital/geojson` directly, so it parses no GEO_JSON string and the list
failed on correct code. Scope is derived from the token now; the
banned-pattern guard still scans all four.

⚠⚠ Corrected again 2026-09-10: **all four** capital views now fetch
`/get/capital/geojson`, so NONE of them parses a GEO_JSON string. The last two
(`categoryA`, `orgprojectsection`) were measured drawing **0 map features** —
their tables had been migrated to the spine while their map code went on
reading a column the spine does not serve. The helper guard therefore inverted
into `test_no_capital_view_consumes_geojson_any_more` rather than having its
anti-vacuum floor lowered to zero, and the derived scope is now computed from
the CODE (comments stripped): a view whose comments merely EXPLAIN that it no
longer reads GEO_JSON is not a consumer, and reading the raw file pulled one
back into scope and failed it (own-prose firing 25). `schools`,
`schoolSection` and `districts` carry the same pattern over data that has NOT
been measured, and `districts` applies a second, different replace
(`.replaceAll('\\\\"', '"')`). They are left alone on purpose; extending the fix
there needs its own measurement, not an assumption.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SCRIPT = os.path.join(ROOT, 'app/public/js/script.js')
VIEWS = os.path.join(ROOT, 'app/resources/views')

# The views whose GEO_JSON comes from the capital tables measured above.
CAPITAL_VIEWS = [
    'projects.blade.php',
    'orgprojectsection.blade.php',
    'categoryA.blade.php',
    'budgetLineA.blade.php',
]

# The banned shape: replacing doubled quotes in a GEO_JSON value.
BANNED = re.compile(r"""GEO_JSON'\]\s*(?:=[^\n]*)?\.replaceAll\(\s*'""'""")


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def test_the_helper_exists_and_tries_the_raw_value_first():
    """`parseGeoJSON` must attempt the value AS SERVED before any replace.

    ⚠ Order is the whole fix. A helper that replaces first and falls back to raw
    would still corrupt the Pelham row, because the corrupted text does not
    throw in a way the fallback can distinguish — it simply parses differently
    or fails. Asserting the raw parse is inside the `try` pins the direction.
    """
    src = _read(SCRIPT)
    m = re.search(r'function parseGeoJSON\(s\)\s*\{(.*?)\n\}', src, re.S)
    assert m, 'parseGeoJSON() is missing from app/public/js/script.js'
    body = m.group(1)

    try_part, _, catch_part = body.partition('catch')
    assert 'JSON.parse(s)' in try_part, (
        'parseGeoJSON must parse the value AS SERVED first; found: ' + try_part.strip())
    assert "replaceAll('\"\"'" not in try_part, (
        'the un-doubling replace must be the FALLBACK, never the first attempt')
    assert "replaceAll('\"\"'" in catch_part, (
        'the fallback must keep the un-doubling replace so a genuinely '
        'quote-doubled source still parses')


def test_capital_views_do_not_undouble_quotes_in_geojson():
    """No capital view may re-introduce the corrupting replace.

    ⚠ Asserts it actually SCANNED the files. A guard that walks nothing passes
    unconditionally — this repo has paid for that twice.
    """
    scanned = 0
    offenders = []
    for name in CAPITAL_VIEWS:
        path = os.path.join(VIEWS, name)
        assert os.path.exists(path), f'{name} moved or was renamed; update this guard'
        text = _read(path)
        scanned += 1
        for line_no, line in enumerate(text.splitlines(), 1):
            if BANNED.search(line):
                offenders.append(f'{name}:{line_no}: {line.strip()}')

    assert scanned == len(CAPITAL_VIEWS), f'scanned {scanned} views, expected {len(CAPITAL_VIEWS)}'
    assert not offenders, (
        'GEO_JSON must be parsed with parseGeoJSON(), which tries the raw value '
        'first. These sites un-double quotes and silently drop any project whose '
        'name contains an escaped quote:\n  ' + '\n  '.join(offenders))


def _code_only(text):
    """Blade, block and line comments stripped.

    ⚠⚠ ADDED 2026-09-10, BECAUSE A MENTION IS NOT A CONSUMPTION. `budgetLineA`
    was migrated to the capital spine and its map now fetches
    `/get/capital/geojson`, exactly as `projects.blade.php` does — but the
    comments recording that migration QUOTE `GEO_JSON` five times, explaining
    that the spine serves no such column. The raw-token scope therefore pulled
    the view back in and then failed it for not calling a parser it has no
    reason to call. Own-prose firing 25 in this repo, and the second one in a
    single session.
    """
    text = re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'^\s*//.*$', '', text, flags=re.M)


def _views_that_consume_geojson():
    """The subset of CAPITAL_VIEWS whose CODE still reads a served `GEO_JSON`.

    ⚠⚠ SCOPE IS DERIVED, NOT LISTED, AND THE LIST IS WHY. `projects.blade.php`
    was rewritten onto the capital spine and now fetches real GeoJSON from
    `/get/capital/geojson` — it contains no `GEO_JSON` at all, so requiring it
    to call a GEO_JSON parser asserted something that had stopped being true.
    The hardcoded list failed on correct code.

    Deriving it is STRICTER than editing the list would have been: a view that
    starts consuming GEO_JSON is covered the moment it does, with nobody having
    to remember to add it.

    ⚠ And it is derived from the CODE, not the file — see `_code_only`. Three
    states exist now, not two: a view that parses GEO_JSON, a view that never
    mentions it, and a view that only mentions it in a comment saying why it
    does not.
    """
    return [n for n in CAPITAL_VIEWS
            if 'GEO_JSON' in _code_only(_read(os.path.join(VIEWS, n)))]


def test_no_capital_view_consumes_geojson_any_more():
    """⚠⚠ THE SCOPE OF THIS GUARD IS NOW EMPTY, AND THAT IS THE FINDING — so the
    assertion inverts rather than the floor dropping.

    This was `test_capital_views_use_the_helper`: every view still parsing a
    served `GEO_JSON` had to call `parseGeoJSON()`, with a floor of 3 (then 2)
    consumers so a silently-emptying scope could not pass unconditionally. On
    2026-09-10 the last two left — `categoryA` and `orgprojectsection`, whose
    maps were measured drawing **0 features** because their tables had been
    migrated to the capital spine while their map code went on reading a column
    the spine does not serve. All four capital views now fetch
    `/get/capital/geojson`, which is real GeoJSON needing no parser at all.

    ⚠ A floor of 0 would be vacuous, which is the failure this repo has paid for
    three times (the guard that scanned zero files, the audit that executed zero
    tools). So the property becomes the stronger one: NO capital view may
    consume GEO_JSON, and the guard asserts it looked at all of them.

    ⚠ What still carries the original concern:
      * `test_no_capital_view_replaces_doubled_quotes` scans every one of
        CAPITAL_VIEWS for the corrupting `replaceAll('""', '"')`, whether or not
        the view reads GEO_JSON;
      * `test_a_view_that_left_scope_really_left_it` asserts each of them
        actually fetches the spine's geojson endpoint, so a view cannot leave
        scope by hiding the token while still drawing from its table;
      * `parseGeoJSON` itself is unchanged and still used by the non-capital
        views (`schools`, `districts`, `mProject`, …), which are deliberately
        out of this file's scope.
    """
    scanned = 0
    offenders = []
    for name in CAPITAL_VIEWS:
        path = os.path.join(VIEWS, name)
        assert os.path.exists(path), '%s moved or was renamed' % name
        scanned += 1
        if 'GEO_JSON' in _code_only(_read(path)):
            offenders.append(name)
    # ⚠ ANTI-VACUUM: the list itself must not empty out.
    assert scanned == len(CAPITAL_VIEWS) and scanned >= 4, (
        'scanned %d capital views, expected all %d'
        % (scanned, len(CAPITAL_VIEWS)))
    assert not offenders, (
        'these capital views read GEO_JSON in live code again: %s. Their tables '
        'are the capital spine, which serves no such column, so the map draws '
        'nothing — with a sized container, a loaded style and an empty console.'
        % offenders)

def test_a_view_that_left_scope_really_left_it():
    """⚠ The one way a derived scope could be abused: a view drops the literal
    `GEO_JSON` token, keeps parsing served geometry another way, and so escapes
    the helper requirement. So every view out of scope must be able to say what
    IS drawing its map.

    ⚠⚠ GENERALISED 2026-09-10, from a hardcoded `== ['projects.blade.php']`. A
    second view left scope that day (`budgetLineA`, migrated to the spine) and
    the list form failed on correct code — the same way this file's original
    hardcoded CAPITAL_VIEWS list did when `projects.blade.php` was rewritten.
    A guard that has to be edited every time the thing it guards improves is
    measuring the edit, not the property. The property is: out of scope means
    fetching the spine's geojson endpoint.
    """
    out_of_scope = [n for n in CAPITAL_VIEWS
                    if n not in _views_that_consume_geojson()]
    # ⚠ ANTI-VACUUM, the mirror of the consumers floor: if NOTHING is out of
    # scope this assertion has nothing to check and would pass silently.
    assert out_of_scope, (
        'no capital view is out of GEO_JSON scope, so this guard is vacuous — '
        'projects.blade.php at least should be')
    for name in out_of_scope:
        # ⚠⚠ COMMENT-STRIPPED, and this one was caught by MUTATION rather than
        # by a failure. The first form read the raw file, and `budgetLineA`'s
        # comments explaining the migration name `/get/capital/geojson` — so
        # pointing the fetch at a dead URL left the guard GREEN. Own-prose
        # firing 26, the third in one session, and the only one of the three
        # that a red test would never have revealed.
        text = _code_only(_read(os.path.join(VIEWS, name)))
        assert ('capital/geojson' in text) or ('CAP_GEOJSON_URL' in text) \
            or ('capGeojsonUrl' in text), (
            '%s no longer reads GEO_JSON but does not fetch the spine geojson '
            'endpoint either — what is drawing its map?' % name)


def test_script_js_busts_its_cache_on_filemtime():
    """The layout must version script.js by filemtime, not a fixed string.

    ⚠ WHY THIS IS PART OF THE FIX AND NOT HOUSEKEEPING. The tag was
    `/js/script.js?v=2`, a constant. Editing script.js changes the file but not
    the URL, so any browser holding a cached copy keeps the OLD script and the
    fix does not ship — indistinguishable, from the outside, from a fix that
    does not work. Every other first-party asset in this layout already busts on
    filemtime.
    """
    layout = _read(os.path.join(VIEWS, 'layout.blade.php'))
    tags = [l for l in layout.splitlines() if 'js/script.js' in l]
    assert tags, 'layout.blade.php no longer references js/script.js'
    for tag in tags:
        assert 'filemtime' in tag, (
            'script.js must be cache-busted with filemtime, or an edit never '
            'reaches a cached browser; found: ' + tag.strip())
