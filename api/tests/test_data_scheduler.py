"""Tests for the CSV import helpers in data_scheduler.

Regression coverage for the `contracts` ingest, whose source
(mocs-contracts.csv) ships a 26-column header with two spurious trailing
`wegov-org-name`/`wegov-org-id` duplicates while its data rows carry only 24
fields. That combination first crashed CREATE TABLE with Postgres
`column "wegov-org-name" specified more than once`, and once dedupe was added,
the strict row-length check dropped every row as "Empty CSV".
"""

from data_scheduler import dedupe_columns, conform_row


class TestDedupeColumns:
    def test_no_duplicates_unchanged(self):
        assert dedupe_columns(["a", "b", "c"]) == ["a", "b", "c"]

    def test_suffixes_duplicates(self):
        assert dedupe_columns(["x", "x", "x"]) == ["x", "x_1", "x_2"]

    def test_mocs_contracts_header(self):
        header = (
            ["c%d" % i for i in range(22)]
            + ["wegov-org-name", "wegov-org-id",
               "wegov-org-name", "wegov-org-id"]
        )
        out = dedupe_columns(header)
        assert len(out) == 26
        # First pair keeps the canonical names the API/frontend query.
        assert out[22] == "wegov-org-name"
        assert out[23] == "wegov-org-id"
        # Trailing duplicates get suffixed instead of colliding.
        assert out[24] == "wegov-org-name_1"
        assert out[25] == "wegov-org-id_1"


class TestConformRow:
    def test_exact_unchanged(self):
        assert conform_row(["x", "y"], 2) == ("x", "y")

    def test_pads_short_rows(self):
        assert conform_row(["a"], 3) == ("a", "", "")

    def test_truncates_long_rows(self):
        assert conform_row(["a", "b", "c"], 2) == ("a", "b")

    def test_blank_row_skipped(self):
        assert conform_row([], 5) is None

    def test_contracts_24_into_26(self):
        # 24 real fields align to the leading columns; the two spurious
        # duplicate columns are padded empty — no data loss.
        data = ["v%d" % i for i in range(24)]
        row = conform_row(data, 26)
        assert row == tuple(data) + ("", "")
        assert row[22] == "v22"  # wegov-org-name value preserved


class _FakeConn:
    """Minimal asyncpg-shaped stub for the unmapped sweep."""

    def __init__(self, datasets):
        self._datasets = datasets

    async def fetch(self, *_a, **_k):
        return []

    async def fetchval(self, *_a, **_k):
        return None

    async def execute(self, *_a, **_k):
        return "INSERT 0 1"


class TestUnmappedScanSweep:
    """The sweep must run independently of what was ingested this cycle.

    scan_unmapped_entities used to be called only as a post-step inside the
    ingest functions, so in production it never ran: normalizer-driven datasets
    are ingested by the normalizer's own sweep via /import-csv (which does not
    scan), and the api scheduler then sees "up to date" and returns before its
    scan call. Measured on prod 2026-07-29: 18 unmapped values across 9
    scannable datasets, and unmapped_entities held 0 rows.
    """

    def _run(self, datasets, monkeypatch):
        import asyncio
        import data_scheduler as sched

        seen, alerts = [], []

        async def fake_scan(conn, ds):
            seen.append(ds['table_name'])
            return ds.get('_fake_new', [])

        async def fake_alert(table, col, new, nid):
            alerts.append((table, len(new)))

        async def fake_get_active(conn):
            return datasets

        monkeypatch.setattr(sched, "scan_unmapped_entities", fake_scan)
        monkeypatch.setattr(sched, "send_unmapped_alert", fake_alert)
        monkeypatch.setattr(sched, "get_active_datasets", fake_get_active)
        asyncio.run(sched._run_unmapped_scan(_FakeConn(datasets)))
        return seen, alerts

    def test_scans_without_any_ingest_having_happened(self, monkeypatch):
        """The whole point: no ingest occurred this cycle, scan anyway."""
        ds = [{"table_name": "crol", "needs_normalization": True,
               "entity_column": "AgencyName", "_fake_new": ["NEW AGENCY"]}]
        seen, alerts = self._run(ds, monkeypatch)
        assert seen == ["crol"]
        assert alerts == [("crol", 1)]

    def test_skips_datasets_that_cannot_be_scanned(self, monkeypatch):
        ds = [
            {"table_name": "flag_off", "needs_normalization": False,
             "entity_column": "Agency"},
            {"table_name": "no_entity_col", "needs_normalization": True,
             "entity_column": ""},
            {"table_name": "ok", "needs_normalization": True,
             "entity_column": "Agency"},
        ]
        seen, _ = self._run(ds, monkeypatch)
        assert seen == ["ok"]

    def test_no_alert_when_nothing_new(self, monkeypatch):
        ds = [{"table_name": "clean", "needs_normalization": True,
               "entity_column": "Agency", "_fake_new": []}]
        seen, alerts = self._run(ds, monkeypatch)
        assert seen == ["clean"]
        assert alerts == []

    def test_one_failing_table_does_not_abort_the_sweep(self, monkeypatch):
        import asyncio
        import data_scheduler as sched
        seen = []

        async def fake_scan(conn, ds):
            if ds['table_name'] == "boom":
                raise RuntimeError("column vanished")
            seen.append(ds['table_name'])
            return []

        async def fake_get_active(conn):
            return ds_list

        ds_list = [
            {"table_name": "boom", "needs_normalization": True,
             "entity_column": "Agency"},
            {"table_name": "after", "needs_normalization": True,
             "entity_column": "Agency"},
        ]
        monkeypatch.setattr(sched, "scan_unmapped_entities", fake_scan)
        monkeypatch.setattr(sched, "get_active_datasets", fake_get_active)
        asyncio.run(sched._run_unmapped_scan(_FakeConn(ds_list)))
        assert seen == ["after"], "sweep must continue past a failing table"


class TestUnmappedScanIsWiredIntoTheCycle:
    def test_cycle_calls_the_sweep(self):
        """Assert the CALL, not the substring — `async def _run_unmapped_scan(
        conn)` also contains the bare name, so a looser check passes even with
        the call deleted (which it did, first time round)."""
        import inspect
        import data_scheduler as sched
        src = inspect.getsource(sched)
        assert "await _run_unmapped_scan(conn)" in src, (
            "the scheduler cycle must call _run_unmapped_scan — otherwise the "
            "unmapped-entity check silently never runs, and /pipeline/health "
            "reports total_alerts: 0 from a check that never executed."
        )


class TestProcurementTableIndexes:
    """The three PASSPort tables (`contracts`, `vendors`, `solicitations`) had
    ZERO indexes on prod — measured 2026-08-04, `pg_indexes` returned no rows
    for any of them, so /oce/contract/{id} opened with a seq scan over 55,806
    rows (`Rows Removed by Filter: 55805`).

    They cannot be fixed by hand: the extractor path COPYs into
    `_staging_<table>`, DROPs the real table and RENAMEs the staging one over
    it, and the staging table has no indexes — so any manually created index is
    destroyed on the next ingest. TABLE_INDEXES + the post-ingest hook is the
    only durable declaration point.
    """

    def test_contracts_indexes_are_declared(self):
        from data_scheduler import TABLE_INDEXES
        cols = {c for _n, c in TABLE_INDEXES.get("contracts", [])}
        # Each of these backs a measured equality predicate in the request path.
        assert {"ctr_id", "contract_id", "epin", "vendor_name"} <= cols

    def test_vendors_and_solicitations_indexes_are_declared(self):
        from data_scheduler import TABLE_INDEXES
        assert {c for _n, c in TABLE_INDEXES.get("vendors", [])} >= {
            '"PASSPort Supplier-ID"', '"Vendor Name"'}
        assert {c for _n, c in TABLE_INDEXES.get("solicitations", [])} == {
            '"EPIN"'}

    def test_declared_contracts_columns_exist_in_the_ddl(self):
        """The real failure mode. recreate_table_indexes SWALLOWS a failed
        CREATE INDEX (prints an x and moves on), so an index naming a column
        that does not exist would never be created and nothing would raise —
        the same 'declared but silently never runs' shape as the unreachable
        register_untracked_tables(). Pin the declared columns to the DDL the
        ingest actually creates.
        """
        from data_scheduler import TABLE_INDEXES, _CONTRACTS_COLS
        for idx_name, col in TABLE_INDEXES["contracts"]:
            assert col in _CONTRACTS_COLS, (
                f"{idx_name} indexes contracts.{col}, which is not in "
                f"_CONTRACTS_DDL — CREATE INDEX would fail and be swallowed"
            )

    def test_every_indexed_table_has_the_hook_registered(self):
        """An index declared for a table with no hook is never recreated."""
        from data_scheduler import TABLE_INDEXES, POST_INGEST_HOOKS
        for tbl in TABLE_INDEXES:
            assert POST_INGEST_HOOKS.get(tbl), f"{tbl} has no post-ingest hook"

    def test_index_hook_runs_before_the_other_hooks(self):
        """`vendors` carries three enrichment hooks that query it by name, so
        the index rebuild must come first or they seq-scan an unindexed table.

        ⚠ The second assertion pins the exact hook LIST, not just its length. It
        was `len(...) == 4` and correctly failed when the vendor-id-map
        invalidation was added 2026-09-01 — a guard failing because you changed
        the thing it guards is it working, so it is updated rather than relaxed.
        Naming the hooks is strictly stronger than counting them: a swap that
        keeps the count is now caught too.
        """
        from data_scheduler import POST_INGEST_HOOKS
        hooks = POST_INGEST_HOOKS["vendors"]
        assert hooks[0].__name__ == "<lambda>", (
            "the index-recreation lambda must be first in vendors' hook list"
        )
        assert [h.__name__ for h in hooks[1:]] == [
            "derive_vendor_enrichment_hook",
            "derive_doing_business_hook",
            "derive_org_vendor_hook",
            # Drops the cached vendorids map — `vendors` is DROP+RENAMEd on every
            # ingest, so this is the moment that map goes stale.
            "invalidate_vendor_id_map_hook",
        ], f"vendors' hook list changed: {[h.__name__ for h in hooks]}"

    def test_recreate_creates_each_index_then_analyzes(self):
        """A brand-new index on a just-renamed table is ignored by the planner
        until the table has statistics, so the ANALYZE is load-bearing: without
        it this hook can report success while every lookup still seq-scans."""
        import asyncio
        from data_scheduler import recreate_table_indexes

        run = []

        class _Conn:
            async def execute(self, sql, *_a):
                run.append(" ".join(sql.split()))
                return "CREATE INDEX"

        asyncio.run(recreate_table_indexes(_Conn(), "contracts"))
        # ⚠ COUNTED FROM THE DECLARATIONS, not pinned to a literal. This asserted
        # `== 4` and fired when the hook took on the GIN half — correctly, because
        # the count changed; but a magic number here just has to be re-guessed every
        # time an index is added. Both families, from their own sources.
        from data_scheduler import TABLE_INDEXES, searchindexes
        expected = len(TABLE_INDEXES["contracts"]) + len(searchindexes.for_table("contracts"))
        assert sum("CREATE INDEX" in s for s in run) == expected
        assert 'CREATE INDEX IF NOT EXISTS idx_contracts_ctr_id ON "contracts"(ctr_id)' in run
        # The GIN half must go through too — this is the half that was missing on
        # prod entirely, because nothing reapplied it after the extractor ingest.
        assert any("gin (contract_title gin_trgm_ops)" in s for s in run), \
            "the search indexes are no longer recreated by the hook"
        assert run[-1] == 'ANALYZE "contracts"', "ANALYZE must run after the indexes"

    def test_a_failed_index_does_not_abort_the_rest(self):
        """Fail-soft: one bad index must not cost the others, and must not take
        down the ingest that triggered the hook."""
        import asyncio
        from data_scheduler import recreate_table_indexes

        run = []

        class _Conn:
            async def execute(self, sql, *_a):
                if "idx_contracts_epin" in sql:
                    raise RuntimeError("boom")
                run.append(" ".join(sql.split()))
                return "CREATE INDEX"

        asyncio.run(recreate_table_indexes(_Conn(), "contracts"))
        from data_scheduler import TABLE_INDEXES, searchindexes
        _all = len(TABLE_INDEXES["contracts"]) + len(searchindexes.for_table("contracts"))
        assert sum("CREATE INDEX" in s for s in run) == _all - 1
        assert run[-1] == 'ANALYZE "contracts"'


# --------------------------------------------------------------------------
# The ingest guard: a CALENDAR DAY, not a 24-hour delta.
# --------------------------------------------------------------------------

def test_the_14_second_skip_that_cost_a_days_ingest():
    """⚠⚠ THE REGRESSION THIS EXISTS TO PREVENT, with the real timestamps.

    Observed on prod 2026-08-29: the cycle ran at 04:01:10.468 while contracts'
    stamp was 04:01:24.742 the previous day — 23:59:45.726 apart, so the old
    `.days < 1` test skipped contracts, solicitations and vendors by FOURTEEN
    SECONDS, and no ingest happened that day at all.
    """
    from datetime import datetime, timezone
    from data_scheduler import already_ingested_today
    last = datetime(2026, 8, 28, 4, 1, 24, 742212, tzinfo=timezone.utc)
    now = datetime(2026, 8, 29, 4, 1, 10, 468579, tzinfo=timezone.utc)
    assert (now - last).days < 1, 'the old delta test would have skipped'  # the bug
    assert already_ingested_today(last, now) is False, (
        'a different calendar day is being reported as "already ingested today" — '
        'this is the 14-second skip returning')


def test_a_second_cycle_on_the_same_day_still_skips():
    """The guard's real job: a deploy-triggered cycle must not re-ingest a
    55,806-row table minutes after the scheduled one did."""
    from datetime import datetime, timezone
    from data_scheduler import already_ingested_today
    last = datetime(2026, 8, 29, 4, 1, 24, tzinfo=timezone.utc)
    for hour in (4, 11, 23):
        now = datetime(2026, 8, 29, hour, 30, tzinfo=timezone.utc)
        assert already_ingested_today(last, now) is True, f'{hour}:30 re-ingested'


def test_the_accepted_price_a_cycle_just_after_midnight_re_ingests():
    """⚠ RECORDED, NOT AVOIDED. A calendar test re-ingests when a cycle runs
    shortly after midnight on something ingested late the evening before. That
    is one extra ingest, occasionally, and it is the price of removing the
    coupling to what time of day the previous ingest happened to occur.

    Asserted so the trade-off is visible and a future change to it is a
    deliberate decision rather than a surprise."""
    from datetime import datetime, timezone
    from data_scheduler import already_ingested_today
    last = datetime(2026, 8, 28, 23, 50, tzinfo=timezone.utc)
    now = datetime(2026, 8, 29, 0, 5, tzinfo=timezone.utc)
    assert already_ingested_today(last, now) is False


def test_a_future_stamp_does_not_re_ingest_forever():
    """⚠ `>=`, not `==`. A clock skew or a restored backup can leave a stamp in
    the future; with `==` that would re-ingest on every single cycle."""
    from datetime import datetime, timezone
    from data_scheduler import already_ingested_today
    last = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    now = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)
    assert already_ingested_today(last, now) is True


def test_no_stamp_means_never_ingested():
    from datetime import datetime, timezone
    from data_scheduler import already_ingested_today
    now = datetime(2026, 8, 29, 4, 1, tzinfo=timezone.utc)
    assert already_ingested_today(None, now) is False


def test_the_day_delta_guard_does_not_come_back():
    """⚠ A source guard, because the defect is a one-line revert away and its
    symptom — a dataset quietly not ingesting — is invisible for days."""
    import ast
    import io
    import os
    src = os.path.join(os.path.dirname(__file__), '..', 'data_scheduler.py')
    with io.open(src, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    # strip docstrings, or this fires on the prose explaining the trap
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            b = node.body
            if (b and isinstance(b[0], ast.Expr)
                    and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                node.body = b[1:]
    code = ast.unparse(tree)
    assert '.days < 1' not in code, (
        'the 24-hour delta guard is back; it skips a whole day whenever the '
        'previous ingest happened later in the day than the current cycle')
    assert 'already_ingested_today' in code, 'the calendar-day helper is gone'
    # and prove the scanner is reading real code, not an empty tree
    assert 'process_extractor_dataset' in code, 'the scanner is not seeing the module'
