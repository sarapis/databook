"""The vendor name -> supplier id map is CACHED, and the cache has three rules.

⚠⚠ WHY IT EXISTS. Profiled on prod 2026-09-01 by wrapping the real
`select_safe` (never by replicating the SQL). Of a 2.221s cold
`/digital-reform/all`, the top THREE queries were all `vendorids.SQL`:
778 + 767 + 577 = 2.12s, because `_vendors`, `_contracts` and `_expiring` each
built the map independently. `_stats` was 223ms and `_charts` 212ms — the two
blocks that had been proposed for optimisation, and which live in the shared
cache and run about twice a day.

⭐ The map sat on the PARAM-DEPENDENT path, so it ran on every novel crawler URL,
serially inside each block — ~60-75% of that path's wall time.

⚠ Deduplicating the three calls was NOT the fix: they are `asyncio.gather`ed, so
they already overlap (one uncontended 573-649ms, three concurrent 754-793ms
wall). Computing it once saves ~181ms of wall; not running the query saves ~750ms.
"""
import asyncio
import ast
import importlib.util
import os
import sys
import types

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
API = os.path.join(ROOT, 'api')

_ROWS = [{"nm": "absorb software inc", "vendor_id": "1871820"},
         {"nm": "ivalua inc", "vendor_id": "1622239"}]


def _load_vendorids():
    """⚠ BY PATH. conftest.py replaces the whole `modules` package with a
    MagicMock, so `from modules import vendorids` yields a mock that would
    satisfy every assertion below. Each call returns a FRESH module, so the
    module-level cache cannot leak between tests."""
    errfmt = types.ModuleType('modules.errfmt')
    errfmt.exc_str = lambda e: f"{type(e).__name__}: {e}"
    sys.modules.setdefault('modules.errfmt', errfmt)
    spec = importlib.util.spec_from_file_location(
        '_vendorids_cache_test', os.path.join(API, 'modules', 'vendorids.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _PG:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    async def select_safe(self, sql, dd=[]):
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return list(_ROWS)


def test_the_map_is_cached_so_repeated_callers_do_not_requery():
    vi = _load_vendorids()
    pg = _PG()
    a = asyncio.run(vi.unique_map(pg))
    b = asyncio.run(vi.unique_map(pg))
    c = asyncio.run(vi.unique_map(pg))
    assert pg.calls == 1, (
        f"three calls issued {pg.calls} queries — the cache is not holding, which "
        "is the ~750ms this change exists to remove")
    assert a == b == c == {"absorb software inc": "1871820", "ivalua inc": "1622239"}


def test_invalidate_forces_the_next_caller_to_rebuild():
    """The `vendors` post-ingest hook calls this; without it the map would serve
    a pre-ingest answer for up to the TTL."""
    vi = _load_vendorids()
    pg = _PG()
    asyncio.run(vi.unique_map(pg))
    assert pg.calls == 1
    vi.invalidate()
    asyncio.run(vi.unique_map(pg))
    assert pg.calls == 2, "invalidate() did not clear the cache"


def test_an_expired_entry_is_rebuilt():
    """⚠ The TTL is the real staleness bound, not the hook: the "daily" extractor
    ingest is measured to run ~16 days in 21, so the hook can silently not fire."""
    vi = _load_vendorids()
    pg = _PG()
    asyncio.run(vi.unique_map(pg))
    vi._cache_ts -= (vi._CACHE_TTL + 1)
    asyncio.run(vi.unique_map(pg))
    assert pg.calls == 2, "an entry older than the TTL was served"


def test_a_failure_is_never_cached():
    """⚠⚠ THE ONE THAT MATTERS MOST. Caching `{}` would turn a single blip into an
    hour with no vendor hyperlink anywhere — and it would look exactly like "no
    name resolves", the empty-result-reads-as-data failure this repo keeps paying
    for. A failure must return {} AND leave the cache untouched so the next
    caller retries."""
    vi = _load_vendorids()
    bad = _PG(fail=True)
    assert asyncio.run(vi.unique_map(bad)) == {}
    assert vi._cache is None, "a failed lookup was cached"
    good = _PG()
    assert asyncio.run(vi.unique_map(good)) == {
        "absorb software inc": "1871820", "ivalua inc": "1622239"}, \
        "the next caller did not retry after a failure"


def test_the_uniqueness_rule_survived_the_caching_change():
    """The cache must not have been bought by relaxing the guard that makes the
    map safe — `HAVING count(DISTINCT ...) = 1` is why an ambiguous name goes
    unlinked instead of pointing at an arbitrary one of two companies."""
    import re
    vi = _load_vendorids()
    assert re.search(r'HAVING\s+count\(DISTINCT\s+"PASSPort Supplier-ID"\)\s*=\s*1',
                     vi.SQL), "the map now guesses between two companies"


def _hooks_for(table):
    """The registered hook names for `table`, read from the AST of the
    POST_INGEST_HOOKS assignment.

    ⚠ AST, not a substring scan: this file and data_scheduler both discuss
    `invalidate_vendor_id_map_hook` in prose, and a text search would match the
    docstring that explains the hook rather than the registration. Eight guards
    in this repo have already fired on their own comments.
    """
    src = open(os.path.join(API, 'data_scheduler.py'), encoding='utf-8').read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == 'POST_INGEST_HOOKS'
                   for t in node.targets):
            continue
        for k, v in zip(node.value.keys, node.value.values):
            if isinstance(k, ast.Constant) and k.value == table:
                return [e.id for e in v.elts if isinstance(e, ast.Name)]
    return None


def test_the_vendors_ingest_invalidates_the_map():
    """⚠ A cache with no invalidation on the ingest that changes its data is the
    stale-figure defect this section has paid for repeatedly."""
    hooks = _hooks_for('vendors')
    assert hooks, "POST_INGEST_HOOKS has no 'vendors' entry any more"
    assert 'invalidate_vendor_id_map_hook' in hooks, (
        "the vendors ingest no longer invalidates the cached vendor id map, so "
        f"it would serve a pre-ingest answer for up to the TTL. Registered: {hooks}")


def test_no_caller_mutates_the_shared_map():
    """⚠⚠ `unique_map` returns the CACHED INSTANCE, not a copy — deliberately,
    since copying 36,563 entries three times per request gives back a slice of
    what the cache just saved. That makes a mutating caller corrupt every later
    caller's map, so nothing may write to it.
    """
    offenders = []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(API):
        parts = set(os.path.relpath(dirpath, API).split(os.sep))
        if parts & {'tests', '__pycache__', 'seed', 'node_modules'}:
            continue
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            path = os.path.join(dirpath, fn)
            try:
                tree = ast.parse(open(path, encoding='utf-8').read())
            except SyntaxError:
                continue
            scanned += 1
            # names bound from `await vendorids.unique_map(...)`
            bound = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Await):
                    call = node.value.value
                    if (isinstance(call, ast.Call)
                            and isinstance(call.func, ast.Attribute)
                            and call.func.attr == 'unique_map'):
                        for t in node.targets:
                            if isinstance(t, ast.Name):
                                bound.add(t.id)
            if not bound:
                continue
            for node in ast.walk(tree):
                # d[k] = v  /  del d[k]
                if isinstance(node, (ast.Assign, ast.AugAssign, ast.Delete)):
                    tgts = (node.targets if isinstance(node, ast.Assign)
                            else [node.target] if isinstance(node, ast.AugAssign)
                            else node.targets)
                    for t in tgts:
                        if (isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)
                                and t.value.id in bound):
                            offenders.append(f"{os.path.relpath(path, ROOT)}: writes {t.value.id}[...]")
                # d.update(...) / d.pop(...) / d.clear() / d.setdefault(...)
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in bound
                        and node.func.attr in {'update', 'pop', 'clear', 'setdefault', 'popitem'}):
                    offenders.append(
                        f"{os.path.relpath(path, ROOT)}: calls {node.func.value.id}.{node.func.attr}()")
    assert scanned > 40, f"the scan only walked {scanned} files — it is not looking"
    assert not offenders, (
        "a caller mutates the shared cached map: " + "; ".join(offenders))
