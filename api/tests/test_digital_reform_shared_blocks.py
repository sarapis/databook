"""The param-independent half of /oce/digital-reform/all is cached separately.

⚠⚠ WHY THIS EXISTS. On 2026-08-31 the whole site returned 504 for hours — 18,947
in one hour — because this endpoint costs 11-17s for a NOVEL parameter
combination and `pm.max_children` is 15. A distributed crawler (676 IPs, ~1.7
requests each) walking the legitimate filter space produced 2,854 distinct URLs
in 20 minutes, against a full-param cache capped at 256. The LRU thrashed, so
nearly every request paid full cost and every php-fpm worker blocked.

Seven of the ten payload blocks do not vary with ANY parameter. They were
recomputed every time anyway. Caching them under a key of the SCOPE MODE ALONE
takes a novel combination from ~11-17s to ~1.9-3.8s, measured, and that cache
holds one entry so it cannot thrash however many combinations arrive.

⚠⚠ THE DANGEROUS REGRESSION IS ADDING A PARAM-DEPENDENT BLOCK TO THE SHARED SET.
It would serve one reader another reader's filtered view — silently, and looking
perfectly plausible. That is what these guards are for.
"""
import ast
import io
import os

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'routers', 'oce.py')

# Verified 2026-08-31 by hashing every block across two wildly different
# parameter sets (different pages, sorts, search terms, years, agencies, licence
# flags, products, segments). These were byte-identical; the three below were not.
PARAM_INDEPENDENT = {
    'stats', 'charts', 'composition', 'contract_options',
    'pipeline', 'calendar', 'award_by_start_year',
}
PARAM_DEPENDENT = {'vendors', 'contracts', 'expiring'}


def _src():
    with io.open(SRC, encoding='utf-8') as fh:
        return fh.read()


def _fn(name):
    """One function's AST node, docstring stripped.

    ⚠ Docstring stripped because this file's own prose names the blocks it
    guards — the own-prose guard failure this repo has now paid for eleven
    times.
    """
    tree = ast.parse(_src())
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            body = n.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                body = body[1:]
            return '\n'.join(ast.unparse(x) for x in body)
    raise AssertionError(f'{name} not found in routers/oce.py')


def test_the_shared_cache_key_is_the_scope_mode_and_nothing_else():
    """⚠⚠ THE KEY IS THE WHOLE FIX. Keyed on any request parameter it becomes a
    second copy of the full-param cache — which thrashed at 2,854 distinct keys
    against a cap of 256, and is exactly why the site went down."""
    body = _fn('get_digital_reform_all')
    assert 'shared_key' in body, 'the shared-block cache is gone'
    line = [l for l in body.splitlines() if 'shared_key =' in l]
    assert line, 'shared_key is never assigned'
    key = line[0]
    assert 'digitalscope.mode()' in key and 'queue_mode()' in key, (
        'the shared key no longer names the scope mode; it must, or a tag-mode '
        'payload could be served as a derived one')
    for banned in ('contract_page', 'vendor_page', 'expiring_page', 'contract_q',
                   'vendor_q', 'expiring_year', 'expiring_agency', 'sort', 'order',
                   'expiring_product', 'contract_segment'):
        assert banned not in key, (
            f'the shared key includes {banned!r}, a request parameter. That '
            'makes it thrash exactly like the full-param cache it exists to '
            'sidestep, and the site went down when that cache thrashed.')


def test_only_verified_param_independent_blocks_are_shared():
    """⚠⚠ A PARAM-DEPENDENT BLOCK IN THE SHARED SET SERVES ONE READER ANOTHER'S
    FILTERED VIEW. Silently, and it looks entirely plausible.

    Membership is not a style choice: each of these was verified byte-identical
    across two wildly different parameter sets. Adding one means measuring it.
    """
    body = _fn('get_digital_reform_all')
    start = body.index('shared = {')
    shared_literal = body[start:body.index('}', start)]
    for dep in PARAM_DEPENDENT:
        assert f"'{dep}'" not in shared_literal and f'"{dep}"' not in shared_literal, (
            f'{dep!r} is in the shared cache but VARIES with request parameters '
            '— every reader would get whichever filter was computed first')
    for ind in PARAM_INDEPENDENT:
        assert f"'{ind}'" in shared_literal or f'"{ind}"' in shared_literal, (
            f'{ind!r} left the shared cache, so it is recomputed on every novel '
            'parameter combination again')


def test_the_param_dependent_blocks_are_still_computed_per_request():
    """⚠ The other half of the same property: these must NOT come from a cache
    keyed on the scope mode."""
    body = _fn('get_digital_reform_all')
    tail = body[body.index('shared = {'):]
    assert 'await asyncio.gather(_vendors(), _contracts(), _expiring())' in \
        ' '.join(tail.split()), (
        'the param-dependent blocks are no longer computed after the shared '
        'lookup; they must run per request')


def test_the_segment_drilldown_still_resolves_against_the_composition_shown():
    """⚠ `_contracts` closes over `composition_segments` and reads it at call
    time. If composition comes from the shared cache, that name must still be
    assigned BEFORE the gather, or the drill-down resolves against an empty
    partition and silently filters nothing."""
    body = _fn('get_digital_reform_all')
    assign = body.index('composition_segments =')
    # ⚠ Anchor on the GATHER STATEMENT, not on the first `_vendors()` in the
    # file — that one is the inner coroutine's own definition, 26,000 characters
    # earlier, and comparing against it passes no matter where the assignment
    # goes. The anchor-on-first-occurrence trap, caught by this guard failing on
    # correct code.
    gather = body.index('vendors, contracts, expiring_data = await')
    assert assign < gather, (
        'composition_segments is assigned after the gather that uses it, so the '
        'segment drill-down would resolve against nothing')


def test_the_shared_cache_cannot_grow_without_bound():
    """⚠ It holds one entry per scope mode today. A cap costs nothing and means
    a future key change cannot silently reintroduce unbounded growth — the
    property the full-param cache lost."""
    src = _src()
    body = src[src.index('def _dr_shared_set'):]
    body = body[:body.index('\n\n\n')] if '\n\n\n' in body else body
    assert 'while len(' in body and 'pop' in body, (
        '_dr_shared_set no longer bounds the cache')


def test_the_shared_blocks_are_invalidated_when_new_data_lands():
    """⚠⚠ #343 SHIPPED WITHOUT THIS, and it is the defect the split creates.

    `refresh_digital_reform_cache()` runs after the daily pipeline cycle
    (data_scheduler.py:1871), so new contract data has just landed. It cleared
    only the param cache. The shared blocks would then have stayed stale for up
    to their 24h TTL — so the Overview's headline count would disagree with the
    filtered table below it, which is exactly the class this section already paid
    for twice (#294's blended ceilings, the 243-vs-242 count).

    ⚠ The OTHER `_digital_reform_cache.clear()`, in the spend-map populator,
    deliberately does NOT clear the shared blocks: none of them reads the spend
    map (verified — both apparent references are the word "spent" in a
    docstring), and it fires ~60s after every restart, so clearing there would
    discard the just-warmed blocks and make the next novel request pay ~16s.
    """
    src = _src()
    body = src[src.index('async def refresh_digital_reform_cache'):]
    body = body[:body.index('@router.get')]
    assert '_dr_shared_cache.clear()' in body, (
        'the pre-warm/refresh no longer clears the shared blocks, so after a '
        'daily ingest the headline figures would be stale while the tables are '
        'fresh')

    # and the spend-map site must NOT clear them
    spend = src[src.index('_digital_spend_cache[\'data\'] = spend'):]
    spend = spend[:spend.index('finally:')]
    assert '_dr_shared_cache' not in spend, (
        'the spend-map populator clears the shared blocks; it fires ~60s after '
        'every restart and no shared block reads the spend map, so this only '
        'throws away the warm cache')
