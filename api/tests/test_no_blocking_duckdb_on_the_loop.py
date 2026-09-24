"""Guard: no `async def` in api/routers/ may run a DuckDB scan on the event loop.

⚠⚠ CLAUDE.md HAS CARRIED THIS RULE SINCE 2026-07-27 WITH THE NOTE "No test catches
this" — and on 2026-08-26, measured, **15 of routers/nycha.py's 19 endpoints were
breaking it**. They called that file's SYNC `_cached` straight from an `async def`,
so a 1.76-3.82s Parquet scan over the 21.9M-row NYCHA lake ran on the event-loop
thread and stalled every other request in the process:

    control (Postgres-only probe)   mean 0.027s   max 0.046s
    during ONE NYCHA search        mean 0.108s   max 0.976s   (3.7x / 21x)
    recovered                       mean 0.029s   max 0.046s
    1 / 2 / 4 concurrent searches   1.9s / 4.2s / 7.7s wall   -> EXACTLY 4x
    api container CPU during a scan: 99.55% = ONE core of eight

Perfect linear serialization at one core is the signature: every scan queueing on
one thread. `routers/budget_revenue.py` and `routers/payroll.py` had ALREADY been
fixed (their `_cached` is `async def` and offloads); nycha.py never got the same
treatment, and nothing noticed because nothing could.

TWO RULES, because the defect has two shapes:
  1. an async def calling a blocking sync helper directly, and
  2. an async def calling a SYNC cache wrapper that invokes fn() inline — which
     looks perfectly innocent at the call site, and is how all 15 hid.

⚠ The companion rule (`asyncio.to_thread` is banned in routers, use the dedicated
pool) is already covered by api/tests/test_duckpool.py. This is the other half.
"""
import ast
import os

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
ROUTERS = os.path.join(ROOT, 'api', 'routers')
# A sync function whose body mentions any of these is doing blocking lake work.
DUCK_MARKERS = ('duckdb', 'read_parquet', '_con()')
OFFLOADERS = ('to_duckdb_thread',)

# ⚠ DELIBERATELY EXEMPT, EACH WITH ITS MEASUREMENT, because a guard that flags
# everything is a guard someone switches off. All measured on prod 2026-08-26:
#
#     _available(budget)            cold 190.8ms   warm 0.005ms   (cached 300s)
#     _spending_available           cold 118.6ms   warm 0.005ms   (cached 300s)
#     _spending_years               cold 189.7ms   warm 0.004ms   (cached 300s)
#     _persistent_spending_connection    one-time INSTALL httpfs, then a global
#                                        return; its only inline caller is the
#                                        STARTUP pre-warm, not a request path
#
# The three probes DO block the loop briefly, on the first request per domain per
# 300s. That is a real instance of this class — but 10-20x smaller than the
# 1.76-3.82s scans the guard exists to prevent, and amortised over 300 seconds.
# Exempted knowingly rather than silently: if any of them grows (an http lake, a
# heavier probe), DELETE ITS EXEMPTION rather than raising a threshold.
EXEMPT = {'_available', '_spending_available', '_spending_years',
          '_persistent_spending_connection'}


def _modules():
    for name in sorted(os.listdir(ROUTERS)):
        if name.endswith('.py') and not name.startswith('__'):
            with open(os.path.join(ROUTERS, name), encoding='utf-8') as fh:
                yield name, fh.read()


def _analyse(src):
    """(blocking sync fn names, sync-cache names, [(async fn, offending call)])."""
    tree = ast.parse(src)
    top = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    blocking, sync_cache = set(), set()
    for n in top:
        if isinstance(n, ast.AsyncFunctionDef):
            continue
        body = ast.unparse(n)
        # ⚠ MENTIONING the lake is not doing work on it. `get_spending_files()`
        # merely BUILDS a read_parquet(...) path string and lists a directory —
        # flagging it was a false positive of the marker heuristic, and false
        # positives are how a guard gets deleted. The real signal is EXECUTING a
        # query, so require an .execute(/.fetch* call as well.
        runs_query = any(m in body for m in ('.execute(', '.fetchall(', '.fetchone('))
        if any(m in body for m in DUCK_MARKERS) and runs_query and n.name not in EXEMPT:
            blocking.add(n.name)
        # A SYNC cache wrapper that calls its fn() inline is blocking BY PROXY.
        if 'cached' in n.name and any(
                isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == 'fn'
                for c in ast.walk(n)):
            sync_cache.add(n.name)

    offences = []
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.AsyncFunctionDef):
            continue
        # Calls that sit inside a lambda are fine ONLY if the lambda is handed to an
        # offloader; a lambda handed to a sync cache wrapper is the shape that hid.
        lambda_calls = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Lambda):
                for c in ast.walk(node):
                    if isinstance(c, ast.Call):
                        lambda_calls.add(id(c))
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            name = node.func.id
            if name in sync_cache:
                offences.append((fn.name, f"calls the SYNC cache wrapper {name}()"))
            elif name in blocking and id(node) not in lambda_calls:
                offences.append((fn.name, f"calls blocking {name}() inline"))
    return blocking, sync_cache, offences


def test_no_router_runs_a_blocking_duckdb_call_on_the_event_loop():
    scanned, total_blocking, all_offences = 0, 0, []
    for name, src in _modules():
        blocking, sync_cache, offences = _analyse(src)
        scanned += 1
        total_blocking += len(blocking)
        all_offences += [(name, fn, why) for fn, why in offences]
    # ⚠ ASSERT IT LOOKED. A scanner that finds no routers, or no blocking helpers
    # to look for, passes vacuously — the zero-files-scanner defect.
    assert scanned >= 5, f"only {scanned} router modules scanned"
    assert total_blocking >= 8, \
        (f"only {total_blocking} blocking sync helpers identified across the "
         f"routers — the detector is not recognising lake code")
    assert not all_offences, (
        "these async handlers run a blocking DuckDB call on the event loop, which "
        "stalls EVERY other request in the process for its duration — use "
        "to_duckdb_thread (see modules/duckpool.py):\n  "
        + "\n  ".join(f"{m}::{fn} — {why}" for m, fn, why in all_offences))


def test_the_offloading_cache_wrapper_actually_offloads():
    """Each router's async cache wrapper must hand the miss to the pool. One that
    awaited nothing would satisfy the scan above while still blocking.

    ⚠ A NAME IS NOT A SIGNATURE. My first draft matched any async def whose name
    contained "cached" and fired on `data_pipeline.get_cached_glob_stats`, which
    reads a POSTGRES table and has nothing to do with DuckDB. A wrapper is
    identified by taking a callable and invoking it — not by its name.
    """
    checked = []
    for name, src in _modules():
        tree = ast.parse(src)
        for n in tree.body:
            if not isinstance(n, ast.AsyncFunctionDef) or 'cached' not in n.name:
                continue
            args = [a.arg for a in n.args.args]
            if 'fn' not in args:          # not a wrapper over a callable
                continue
            body = ast.unparse(n)
            assert any(o in body for o in OFFLOADERS), (
                f"{name}::{n.name} is an async cache wrapper over a callable that "
                f"does NOT offload to the DuckDB pool, so a miss blocks the loop")
            checked.append(f"{name}::{n.name}")
    assert len(checked) >= 3, \
        (f"expected at least 3 async DuckDB cache wrappers (nycha, budget_revenue, "
         f"payroll), found {checked} — the detector is not finding them")


def test_nycha_keeps_both_wrappers_and_they_are_used_correctly():
    """nycha.py needs BOTH: a sync one for helpers already running inside the pool
    (offloading again from there would queue on the same bounded executor), and an
    async one for handlers. Pin that both exist and stay distinct."""
    src = open(os.path.join(ROUTERS, 'nycha.py'), encoding='utf-8').read()
    tree = ast.parse(src)
    names = {n.name: type(n).__name__ for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and 'cached' in n.name}
    assert names.get('_cached') == 'FunctionDef', \
        "nycha._cached must stay SYNC — it serves callers already in the pool"
    assert names.get('_cached_async') == 'AsyncFunctionDef', \
        "nycha._cached_async must exist and be async"
    # And the sync one must only ever be reached from sync code.
    for n in ast.walk(tree):
        if isinstance(n, ast.AsyncFunctionDef):
            for c in ast.walk(n):
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) \
                        and c.func.id == '_cached':
                    raise AssertionError(
                        f"nycha::{n.name} calls the sync _cached from an async def")
