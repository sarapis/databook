"""Guards for the review API — Phase 1 of docs/REVIEW-APP-SCOPE.md.

⚠ AST/source guards, not behavioural ones, for the reason this repo has paid for
repeatedly: `conftest.py` replaces the whole `modules` package with a MagicMock,
so an import-based assertion can pass against a mock that satisfies anything.
The contract module itself is loaded BY PATH where behaviour is asserted.
"""
import ast
import importlib.util
import io
import os

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
ROUTER = os.path.join(ROOT, 'routers', 'review.py')
MOD = os.path.join(ROOT, 'modules', 'reviewqueue.py')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


_spec = importlib.util.spec_from_file_location('_rq_api', MOD)
rq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rq)


def _fn(name):
    for n in ast.walk(ast.parse(_read(ROUTER))):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    raise AssertionError(f'{name} is gone from the review router')


def _code(node):
    b = node.body
    if b and isinstance(b[0], ast.Expr) and isinstance(b[0].value, ast.Constant):
        b = b[1:]
    return '\n'.join(ast.unparse(x) for x in b)


def test_the_module_really_loaded():
    """Guard against the MagicMock trap: a mock would satisfy everything."""
    assert rq.__file__ == MOD
    assert rq.SEEDING_VERBS == (rq.ACCEPT, rq.REJECT, rq.AMEND)


# --------------------------------------------------------------------------
# ⚠⚠ The property that makes serving candidates safe at all.
# --------------------------------------------------------------------------

def test_every_endpoint_authenticates():
    """⚠⚠ These endpoints serve UNREVIEWED model output that names City
    programs and assigns them money. #146's rule is that such rows never render
    publicly; a review tool must read them, and `require_editor` is the only
    thing standing between that and an unauthenticated GET.

    Asserted per ROUTE FUNCTION, not once for the file: a file-wide check passes
    while a single new endpoint forgets — the per-aggregate lesson from the
    by-year chart, at a different surface.
    """
    tree = ast.parse(_read(ROUTER))
    routes = [n for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
              and any(isinstance(d, ast.Call) and 'router' in ast.unparse(d)
                      for d in n.decorator_list)]
    assert len(routes) >= 3, f'only found {len(routes)} routes — scanner is wrong'
    missing = [n.name for n in routes if 'require_editor' not in _code(n)]
    assert not missing, (
        'review endpoints that do not authenticate, so unreviewed candidates '
        f'would be servable to the public: {missing}')


def test_a_decision_cannot_be_recorded_unattributed():
    """⚠ A shared account attributing two reviewers to one string is the defect
    the allowlist exists to prevent, and it is PERMANENT once written. Refused
    at the store, not just in the router, so a bulk script cannot bypass it."""
    with pytest.raises(ValueError):
        import asyncio
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            rq.record(None, 'program-names',
                      rq.Decision(item_id='x', verb=rq.ACCEPT, actor='   ')))


def test_the_router_offers_only_the_queues_own_verbs():
    """⚠ `dismiss` exists for untrusted public submissions. Offering it on a
    generator queue would invite recording 'spam' about our own extractor's
    output, and it must never reach a seed."""
    code = _code(_fn('record_decision'))
    assert 'verb not in q.verbs' in code, (
        'the router no longer validates against the QUEUE\'s verbs; the full '
        'contract set includes dismiss, which no generator queue accepts')


def test_settled_state_distinguishes_the_seed_from_a_pending_decision():
    """⚠⚠ TWO DIFFERENT SETTLED STATES, AND COLLAPSING THEM MISLEADS.
    `in_seed` was decided before this tool existed and is already published;
    `decision` is pending export. Measured 2026-08-30: 10 of 132 program-name
    candidates were already curated. A reviewer needs to tell "the project
    settled this" from "I just answered this"."""
    code = _code(_fn('list_items'))
    assert "'in_seed'" in code and "'decision'" in code, \
        'the items payload no longer separates seed state from a pending decision'


def test_a_broken_queue_reports_an_error_rather_than_zero():
    """⚠⚠ THIS REPO'S OLDEST DEFECT. "Nobody is called that" and "this query is
    broken" being byte-identical is how the people search returned nothing for
    eight weeks (#256). A queue whose table is absent must be visible as an
    error, never as a queue with nothing to do."""
    code = _code(_fn('list_queues'))
    assert "'error'" in code, 'a failing queue no longer reports an error'
    assert "'awaiting': None" in code, (
        'a failing queue reports a NUMBER for awaiting — a broken generator '
        'would read as a worked-through queue')


def test_the_actor_is_read_only_after_authenticating():
    """⚠⚠ THIS GUARD ORIGINALLY FORBADE THE ONLY MECHANISM THAT WORKS.

    It asserted the actor must NOT come from the payload. But the app calls this
    API server-to-server with ONE service token, so `require_editor` resolves to
    that token's user on every request regardless of who is at the keyboard —
    `/admin/orgs` accepts exactly that and documents it ("the API attributes the
    change to the token's user"). Tolerable for one editor; wrong for two
    reviewers, which is the entire point of this queue.

    So the app forwards the reviewer it authenticated, and the real property to
    guard is ORDERING: the forwarded value is trustworthy only because the
    endpoint has already authenticated, and because the app derives it from
    nginx's verified credential rather than from a form field.
    """
    code = _code(_fn('record_decision'))
    assert 'require_editor' in code and '_actor(' in code, \
        'the endpoint no longer authenticates or no longer resolves an actor'
    assert code.index('require_editor') < code.index('_actor('), (
        'the actor is resolved BEFORE authentication — a forwarded identity is '
        'only trustworthy once the caller is known')


def test_an_unattributed_decision_is_refused_at_the_store():
    """⚠ Not just in the router: a bulk script calling record() directly must
    not be able to write an unattributed decision either. Permanent once
    written, and the shared-account ambiguity is exactly what this avoids."""
    import asyncio
    with pytest.raises(ValueError):
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            rq.record(None, 'program-names',
                      rq.Decision(item_id='x', verb=rq.ACCEPT, actor='')))


# --------------------------------------------------------------------------
# Related links — the research trail, and the subset the reviewer publishes.
# --------------------------------------------------------------------------

def test_only_http_urls_can_be_stored_as_a_link():
    """⚠⚠ BLADE ESCAPING DOES NOT MAKE AN href SAFE. `{{ $url }}` escapes text,
    but inside `href="…"` a `javascript:` URL still executes — so the only place
    to stop one is before it is stored.

    An ALLOWLIST, never a blocklist: `data:`, `vbscript:` and every scheme
    nobody has thought of fail closed — including whitespace-prefixed ones, for
    free, since " javascript:…" does not start with http either.

    ⚠ Mutating the `.strip()` away does NOT fail this test, and that is correct
    rather than a gap: the allowlist already refuses a space-prefixed URL, so
    the strip is usability (accepting a paste with stray spaces), not the
    security property. The first version of this docstring said otherwise.
    """
    ok = ('https://www.nyc.gov/x', 'http://a.b/c?d=1#e')
    for u in ok:
        assert rq.clean_link_url(u) == u, f'a real URL was refused: {u!r}'

    hostile = ('javascript:alert(1)', ' javascript:alert(1)',
               'JavaScript:alert(1)', 'jAvAsCrIpT:alert(1)',
               'data:text/html,<script>x</script>', 'vbscript:x',
               'file:///etc/passwd', '//evil.example', 'ftp://x',
               'https://ok\nX', 'https://ok\tX', '', '   ')
    for u in hostile:
        assert rq.clean_link_url(u) == '', f'NOT refused: {u!r}'

    assert rq.clean_link_url('https://x/' + 'a' * 4000) == '', \
        'an over-long URL is not refused'


def test_a_refused_link_is_never_written():
    """⚠ Refused at the STORE, so a bulk script cannot bypass the router."""
    import asyncio
    for bad in ('javascript:alert(1)', ''):
        with pytest.raises(ValueError):
            asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
                rq.add_link(None, 'program-names', 'X', bad, 'n', 'devin'))


def test_only_flagged_links_become_source_clauses():
    """⭐⭐ THE OWNER'S CALL, MADE STRUCTURAL. A research trail and a published
    citation are not the same thing: five leads and one good source is the
    normal shape, and a seed row reads better with the one.

    So the export contract lives in ONE function, and it takes ONLY the links
    the reviewer flagged. An export that took every link would publish leads and
    half-read pages as provenance under "Source:" — on a row making a claim
    about a named City program or vendor, which is the Gartner lesson. One that
    took none would drop the citation the convention exists for.
    """
    links = [{'url': 'https://a', 'is_source': True},
             {'url': 'https://b', 'is_source': False},
             {'url': 'https://c', 'is_source': True}]
    assert rq.source_clauses(links) == ['Source: https://a', 'Source: https://c']
    assert rq.source_clauses([]) == []
    assert rq.source_clauses([{'url': 'https://x', 'is_source': False}]) == [], \
        'an unflagged link is being published as a source'


def test_a_link_is_independent_of_the_decision():
    """⚠ Many per item, accumulating BEFORE an answer — often they are why one is
    possible. Folding them into the decision row would lose them on a re-decide
    and stop a reviewer parking a link without deciding."""
    mod = ' '.join(_read(MOD).split())
    assert 'CREATE TABLE IF NOT EXISTS review_link' in mod, \
        'links no longer have their own table'
    assert 'PRIMARY KEY (queue, item_id)' in mod, \
        'the decision table lost its one-row-per-item key'
    cite = mod[mod.index('CREATE TABLE IF NOT EXISTS review_link'):]
    cite = cite[:cite.index('CREATE INDEX')]
    assert 'PRIMARY KEY (queue, item_id)' not in cite, (
        'links are keyed one-per-item — a reviewer could only ever record one')


def test_link_changes_are_scoped_to_their_queue():
    """⚠ Otherwise an id from one queue mutates another queue's link."""
    mod = ' '.join(_read(MOD).split())
    assert mod.count('WHERE id = $1 AND queue = $2') >= 2, (
        'delete and/or the source toggle is no longer scoped to the queue')
