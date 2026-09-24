"""The crol import must never drop the live table.

⚠⚠ THE DEFECT. `import_crol_async` used to `DROP TABLE crol` and then spend the
whole import rebuilding it — 1.1M rows / 789 MB of COPY plus TWO full table
rewrites (`ALTER COLUMN ... TYPE DATE` and the event_date_parsed UPDATE). For
that entire window every consumer saw either:

  * `relation "crol" does not exist` — Sentry DATABOOK-API-31, 3 events at
    04:15:0x on three different days; or
  * ⚠ a PARTIALLY POPULATED table, which is worse because it does not raise: a
    notices panel silently renders fewer notices than exist and a count reads
    low. That is this repo's empty-reads-as-data defect at ingest grain.

Consumers: oce.py::_notices_for_epins and related_notices (the contract page's
panel), routers/search.py::_notices (global search + typeahead), the notice
pages, notice_product_links' builder, and the classifier's CROL tier.

⚠ WHY INDEXES ARE REBUILT AFTER THE RENAME, not before. Index names are
schema-unique and declared explicitly in data_scheduler.TABLE_INDEXES, so
creating them on `_staging_crol` would collide with the live table's. Naming
them here to dodge that would give crol a FOURTH index declaration site — the
sprawl #252 removed. So the remaining window is "complete but briefly
unindexed", which is strictly better than "missing or partial" and no worse than
the old code, which also only indexed at the end.
"""
import ast
import os

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
MAIN = os.path.join(ROOT, 'api/main.py')


def _fn(name):
    src = open(MAIN, encoding='utf-8').read()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return ast.get_source_segment(src, n)
    raise AssertionError(f"{name} not found in api/main.py")


def _sql_literals(body):
    """SQL the function actually EMITS, from string literals only.

    ⚠ AST literals, never the raw text — this file's own comments quote
    `DROP TABLE crol` while explaining the bug, and a scanner that reads prose as
    code reports problems that are not there. Eight guards in this repo have
    already fired on their own explanation.
    """
    out = []
    for n in ast.walk(ast.parse(body)):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append(n.value)
        elif isinstance(n, ast.JoinedStr):  # f-string
            out.append(''.join(p.value for p in n.values
                               if isinstance(p, ast.Constant) and isinstance(p.value, str)))
    return out


# ⚠ BOTH importers, not just crol. The generic /import-csv path serves 52 active
# datasets including payrolldata (1787 MB) and civillist (725 MB) — both LARGER
# than crol — and civillist backs people search, person profiles and the org
# Employees tab. Fixing one and leaving the other is the "check the siblings"
# lesson this repo has paid for twice (nycha.py vs budget_revenue/payroll).
IMPORTERS = ('import_crol_async', 'import_csv_async')


def test_no_importer_uses_time_without_importing_it():
    """⚠ main.py imports `time` only inside functions, and defines NO module-level
    logger. My first draft of each of these used `time.time()` without the local
    import and `logger.info(...)` with no logger — both NameErrors that would only
    surface during a real ingest, days later. Caught twice; pinned now."""
    src = open(MAIN, encoding='utf-8').read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = ast.get_source_segment(src, node) or ''
        if 'time.time()' not in body:
            continue
        has = any(isinstance(x, ast.Import) and any(a.name == 'time' for a in x.names)
                  for x in ast.walk(ast.parse(body)))
        assert has, f"{node.name} calls time.time() without importing time — NameError at ingest"


def test_both_importers_share_one_swap():
    """Two copies of the swap would be two chances to get it subtly different.

    ⚠⚠ AST, NOT A SUBSTRING — and this is the FOURTH time in this one file. Both
    importers carry a COMMENT naming `_swap_staging_into_place` ("see
    _swap_staging_into_place for why ANALYZE happens before the swap"), so
    `'_swap_staging_into_place' in body` is satisfied by the prose alone: deleting
    the actual call left this guard green. Verified by reintroducing exactly that.
    The rule this repo keeps re-learning: a guard that reads prose as code reports
    problems that are not there, and — worse — reports success for code you have
    deleted.
    """
    for fn in IMPORTERS:
        tree = ast.parse(_fn(fn))
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == '_swap_staging_into_place']
        assert calls, f"{fn} does not CALL the shared swap helper"


def test_the_import_builds_into_a_staging_table():
    for fn in IMPORTERS:
        _assert_builds_into_staging(fn)


def _assert_builds_into_staging(fn):
    body = _fn(fn)
    sql = ' | '.join(_sql_literals(body))
    assert '_staging_name(' in body and 'staging' in body, (
        f"{fn} no longer builds into a staging table — it is dropping the live one "
        f"and rebuilding in place, which is the outage this guard exists for")
    assert 'CREATE TABLE ' in sql
    # the COPY must target staging, never the live table
    assert 'staging, records' in body, f"{fn} COPYs rows somewhere other than staging"
    assert "copy_records_to_table('crol'" not in body and \
           'copy_records_to_table("crol"' not in body and \
           'copy_records_to_table(\n                            table_name' not in body, \
        f"{fn} COPYs rows straight into the live table"


def test_the_swap_is_atomic():
    """⚠ DDL is transactional in Postgres, so DROP + RENAME in one transaction
    means no reader can observe the moment between them: they see the old table
    or the new one, never neither. That is the entire point of the change."""
    body = _fn('_swap_staging_into_place')
    assert 'db.transaction()' in body, "the swap is no longer in a transaction"
    tx = body.index('db.transaction()')
    after = body[tx:tx + 400]
    assert 'RENAME TO' in after, "the rename is not inside the transaction"
    assert 'DROP TABLE IF EXISTS' in after, "the drop is not inside the transaction"
    # and neither importer may drop the live table itself — only the shared
    # helper does, inside the transaction
    for fn in IMPORTERS:
        imp = _fn(fn)
        assert 'DROP TABLE IF EXISTS crol' not in imp, \
            f"{fn} drops the live table directly — the original defect"
        assert 'DROP TABLE IF EXISTS "{table_name}"' not in imp, \
            f"{fn} drops the live table directly — the original defect"


def test_the_staging_table_is_analyzed_before_the_swap():
    """⚠ pg_statistic is keyed on the relation OID and RENAME preserves it, so
    stats gathered on staging SURVIVE the swap and the table is never
    live-without-statistics. Without this the planner treats 1.1M rows as empty
    until the post-ingest ANALYZE — the #199 defect, where the hook reports
    success while every lookup still seq-scans."""
    body = _fn('_swap_staging_into_place')
    tree = ast.parse(body)

    # ⚠⚠ AST LINE NUMBERS, NOT body.index(). The first draft compared
    # `body.index('ANALYZE')` against the transaction and PASSED when ANALYZE was
    # moved after the swap — because the word ANALYZE also appears in this
    # function's own COMMENT ("until the post-ingest ANALYZE"), which sits before
    # the transaction. Verified by reintroducing the bug and watching it slip
    # through. Same trap as the hook-ordering guard below, in the same file.
    analyzes = [n.lineno for n in ast.walk(tree)
                if isinstance(n, (ast.Constant, ast.JoinedStr))
                and 'ANALYZE' in ''.join(
                    [n.value] if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    else [p.value for p in getattr(n, 'values', [])
                          if isinstance(p, ast.Constant) and isinstance(p.value, str)])]
    assert analyzes, "the staging table is no longer analyzed"

    txs = [n.lineno for n in ast.walk(tree)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
           and n.func.attr == 'transaction']
    assert txs, "the swap transaction is gone"
    assert min(analyzes) < min(txs), \
        "ANALYZE runs after the swap, so the window it exists to remove is back"


def test_a_failed_run_cannot_leave_a_full_size_orphan():
    """A run that dies mid-build leaves a complete copy of the table behind —
    789 MB at current volumes. After a successful swap the cleanup is a no-op,
    because the staging table no longer exists under that name."""
    for fn in IMPORTERS:
        _assert_cleans_up_staging(fn)


def _assert_cleans_up_staging(fn):
    body = _fn(fn)

    # ⚠ Read the Try node's finalbody, not text after the word "finally". The
    # first draft searched `body[body.rindex('finally:'):]` for "staging" and
    # PASSED with the cleanup deleted, because the explanatory COMMENT above it
    # contains that word. Verified by reintroducing the bug.
    def _drops_staging(nodes):
        for node in nodes:
            for n in ast.walk(node):
                txt = ''
                if isinstance(n, ast.Constant) and isinstance(n.value, str):
                    txt = n.value
                elif isinstance(n, ast.JoinedStr):
                    txt = ''.join(p.value for p in n.values
                                  if isinstance(p, ast.Constant) and isinstance(p.value, str))
                if 'DROP TABLE IF EXISTS' in txt and 'crol' not in txt:
                    return True   # the staging name is an interpolated variable
        return False

    tries = [n for n in ast.walk(ast.parse(body)) if isinstance(n, ast.Try) and n.finalbody]
    assert tries, "the import no longer has a finally block"
    assert any(_drops_staging(t.finalbody) for t in tries), \
        "no staging cleanup in a finally block — a run that dies mid-build leaves "\
        "a full-size copy of the table behind (789 MB at current volumes)"


def test_the_indexes_are_rebuilt_through_the_one_owner_after_the_swap():
    """⚠ Not a direct recreate_table_indexes call: crol's hooks were registered,
    correctly ordered and verified present in the live process for a month while
    never firing, because this importer bypassed the scheduler. It must call the
    HOOK RUNNER, whose hook[0] is the index rebuild, so anything else registered
    on crol actually runs."""
    body = _fn('import_crol_async')
    tree = ast.parse(body)

    # ⚠ ANCHOR ON THE AST, NOT THE TEXT. The first textual occurrence of
    # `run_post_ingest_hooks` in this function is inside a COMMENT explaining the
    # hook history, 2,000 characters before the real call — so a raw
    # `body.index(...)` ordering check fails on correct code. This guard's first
    # draft did exactly that, which is the trap its own sibling docstring warns
    # about, at the ninth occurrence in this repo.
    calls = [n.lineno for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == 'run_post_ingest_hooks']
    assert calls, "the importer no longer CALLS crol's hook runner"

    renames = [n.lineno for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == '_swap_staging_into_place']
    assert renames, "the importer no longer calls the shared swap helper"
    assert min(renames) < min(calls), \
        "hooks run before the swap, so indexes would be built on the staging name"
