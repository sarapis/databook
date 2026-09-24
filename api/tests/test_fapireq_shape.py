"""`fapireq` must always call back an OBJECT, and read both payload shapes.

⚠⚠ THE DEFECT: the success branch called back a BARE ARRAY when a payload had no
`rows` key, and DataTables' own ajax callback reads `.data.length` — so `.data`
was `undefined` and every org profile threw `Cannot read properties of undefined
(reading 'length')`. Measured 2026-09-10: **1 uncaught on 5 of 5 org profiles**,
from `/get/orgs/section/{id}/nycjobs`, which serves a bare `[]`.

⚠⚠ AND THE API GENUINELY SERVES TWO SHAPES, so handling one was the bug rather
than a preference: of an org profile's ~44 payloads, 14 carry `rows` and ~30 are
bare lists (`/get/orgs/stats-reg/{id}/{tbl}` serves `[{"count":0}]`).

⚠⚠ AND THE ERROR BRANCH HAD ALREADY BEEN FIXED, with a comment saying a failed
request is not an empty result. One branch returned `{data: …}` and the other an
array — the fixed-one-branch pattern this repo records for `_cached` in
`nycha.py`, where two sibling routers shared a defect and one had been treated.
Check the siblings when you fix a shared shape.

⚠ Behaviour is verified by `scripts/headless/verify_uncaught_js.py`, which
asserts zero uncaught errors AND every DataTable's row count — because a fix
that silenced the throw by handing DataTables an empty set would pass an
error-only check. This file pins the source so the shape cannot regress
silently.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SCRIPT = os.path.join(ROOT, 'app', 'public', 'js', 'script.js')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _fn_body(text, name):
    """One JS function's body, by walking balanced braces from its `{`.

    ⚠ SCOPED, not a file-wide scan: `script.js` holds several functions that
    mention `data` and `rows`, and this repo records seven guards that inspected
    a mention rather than the code under test.
    """
    i = text.index('function %s(' % name)
    j = text.index('{', i)
    depth, k = 0, j
    while k < len(text):
        if text[k] == '{':
            depth += 1
        elif text[k] == '}':
            depth -= 1
            if depth == 0:
                return text[j:k + 1]
        k += 1
    raise AssertionError('unbalanced braces in %s' % name)


def _code_only(text):
    """⚠ Comments stripped. Every assertion below searches for a string the
    comments recording this fix quote — `rows`, `data`, `unexpected`, and the
    bare-array shape itself. Own-prose firings in this repo stand at 26."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'^\s*//.*$', '', text, flags=re.M)


def test_fapireq_never_calls_back_a_bare_array():
    """⚠⚠ THE DEFECT ITSELF. `cb([])` gives DataTables an object with no `.data`,
    and it reads `.length` off that."""
    body = _code_only(_fn_body(_read(SCRIPT), 'fapireq'))
    bare = re.findall(r'cb\(\s*\[\s*\]\s*\)', body)
    assert not bare, (
        'fapireq calls back a bare array again: %s. DataTables reads '
        '`.data.length` off whatever it is handed, so this throws '
        "`Cannot read properties of undefined (reading 'length')` — one "
        'uncaught error on every page that has such a table' % bare)
    # Every `cb(` in this function must hand over an object literal.
    calls = re.findall(r'cb\(\s*(.)', body)
    assert calls, 'fapireq no longer calls its callback'
    assert all(c == '{' for c in calls), (
        'not every fapireq callback receives an object literal: first chars '
        '%s' % calls)


def test_fapireq_reads_both_payload_shapes_the_api_serves():
    """⚠ `{rows: [...]}` AND a bare list. Handling one was the bug: ~30 of an org
    profile's ~44 payloads are bare lists. A bare list is always DATA — FastAPI's
    own error payload is `{"detail": …}`, a dict — and a non-JSON body arrives as
    a string, which is neither shape."""
    body = _code_only(_fn_body(_read(SCRIPT), 'fapireq'))
    assert "data['rows']" in body or 'data.rows' in body, (
        'fapireq no longer reads the `rows` payload shape')
    assert 'Array.isArray(' in body, (
        'fapireq no longer reads a bare list as data, so every '
        '`/get/orgs/stats-reg/*` payload becomes an empty result')


def test_fapireq_keeps_its_three_states_distinct():
    """⚠⚠ THREE DIFFERENT CLAIMS, and `schoolStatTiles` already depends on
    telling them apart:

        {data: rows}              the request answered
        {data: [], unexpected}    it answered in a shape we do not read
        {data: [], error, status} we could not ask

    Collapsing `unexpected` into a plain empty result would make "the endpoint
    returned something we cannot read" indistinguishable from "the query matched
    nothing" — this repo's oldest defect, and the reason the error branch carries
    `status` at all.
    """
    body = _code_only(_fn_body(_read(SCRIPT), 'fapireq'))
    assert "'unexpected'" in body or 'unexpected:' in body, (
        'the unreadable-payload state no longer marks itself, so it reads as an '
        'empty result')
    assert "'error'" in body and "'status'" in body, (
        'the error branch no longer carries `error`/`status`, which is what '
        'separates "we could not ask" from "it answered with nothing"')

    # ⚠ And the consumer that relies on this must still be reading it.
    tiles = _code_only(_fn_body(_read(SCRIPT), 'schoolStatTiles'))
    assert 'resp.error' in tiles, (
        'schoolStatTiles no longer distinguishes a failed request from an empty '
        'one, so six blank tiles would read as a district with no schools')


def test_no_comment_still_describes_the_bare_array_shape():
    """⚠ A comment that outlives the thing it describes is a stale disclosure.
    `schoolStatTiles`' docstring documented the third shape as "a BARE ARRAY",
    which was accurate and is now the defect's description."""
    src = _read(SCRIPT)
    i = src.index('function schoolStatTiles(')
    doc = src[max(0, i - 2200):i]
    assert 'BARE ARRAY' not in doc or 'CORRECTED' in doc, (
        "schoolStatTiles' comment still presents the bare-array callback as "
        'current, with no note that it was corrected')
