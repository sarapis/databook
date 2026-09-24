"""Guards for `modules/sourcedupes` — the owner of "the publisher ships this
table with byte-exact duplicate rows".

`schoollocations` is the entry that put the module here: NYC Open Data
`wg9x-4ke6` publishes 2,190 rows for 2,131 schools, 59 of them repeated
identically across all 41 columns. Every read fanned that out — the citywide
schools tile said 2,190, and 21 of 32 district pages inflated their enrolment,
project counts, budgets and spending, district 18 by 752 students (+4.4%).

Two kinds of guard, because the defect has two shapes:

  * BEHAVIOURAL — the emitted relation must actually collapse the duplicate and
    actually stop a join fanning out. Run against DuckDB over a fixture built
    to prod's shape, so it measures the SQL rather than looking at it.
  * A BANNED-PATTERN SCAN — no query anywhere in `api/` may name the raw table
    in a FROM/JOIN. Checking the five sites we know about would not survive the
    sixth, which is how the cached `globstats` tile kept its wrong count after
    the endpoints were fixed.
"""
import ast
import importlib.util
import os

import pytest

duckdb = pytest.importorskip("duckdb")

_API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TABLE = "schoollocations"


def _load():
    """Load the module BY PATH.

    ⚠ `conftest.py` replaces the whole `modules` package with a MagicMock, so
    `from modules import sourcedupes` yields a mock whose `relation()` returns
    a MagicMock — which satisfies almost any assertion here. Assert it is the
    real thing before trusting a single result below.
    """
    spec = importlib.util.spec_from_file_location(
        "_sourcedupes_under_test", os.path.join(_API, "modules", "sourcedupes.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert isinstance(mod.EXACT_DUPLICATE_SOURCES, dict), "loaded a mock, not the module"
    assert isinstance(mod.relation(_TABLE), str), "loaded a mock, not the module"
    return mod


sourcedupes = _load()


# --------------------------------------------------------------------------
# Behavioural: the relation dedupes, and the dedupe is what stops the fan-out.
# --------------------------------------------------------------------------

def _fixture():
    """prod's shape in miniature: one school published twice, one published once.

    K066 carries 1,000 students and is duplicated; K067 carries 200 and is not.
    So the right district total is 1,200 and the fanned-out one is 2,200.
    """
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE schoollocations AS SELECT * FROM (VALUES
            ('K066', '18', '18K066'),
            ('K066', '18', '18K066'),
            ('K067', '18', '18K067')
        ) t(location_code, "Geographical_District_code", system_code)
    """)
    con.execute("""
        CREATE TABLE scaenrollmentcapacity AS SELECT * FROM (VALUES
            ('K066', 1000), ('K067', 200)
        ) t("Bldg ID", "Org Enroll")
    """)
    return con


def test_the_fixture_actually_reproduces_the_fan_out():
    """Assert the bug EXISTS here before asserting the fix removes it.

    A fixture that cannot produce a duplicate makes every assertion below
    vacuously true — the failure mode this repo has already paid for twice.
    """
    con = _fixture()
    assert con.execute(f"SELECT count(*) FROM {_TABLE}").fetchone()[0] == 3
    fanned = con.execute(f"""
        SELECT sum(t1."Org Enroll") FROM scaenrollmentcapacity t1
        JOIN {_TABLE} t2 ON t1."Bldg ID" = t2.location_code
        WHERE t2."Geographical_District_code" = '18'
    """).fetchone()[0]
    assert fanned == 2200, "fixture does not double-count; the guards below prove nothing"


def test_the_relation_collapses_the_duplicate_row():
    con = _fixture()
    rel = sourcedupes.relation(_TABLE)
    assert con.execute(f"SELECT count(*) FROM {rel}").fetchone()[0] == 2


def test_the_relation_stops_a_join_fanning_out():
    con = _fixture()
    rel = sourcedupes.relation(_TABLE, "t2")
    total = con.execute(f"""
        SELECT sum(t1."Org Enroll") FROM scaenrollmentcapacity t1
        JOIN {rel} ON t1."Bldg ID" = t2.location_code
        WHERE t2."Geographical_District_code" = '18'
    """).fetchone()[0]
    assert total == 1200, f"join still fans out: {total}"


def test_the_relation_keeps_rows_that_differ_in_any_single_column():
    """`SELECT DISTINCT *` is lossless BY CONSTRUCTION, and that is the reason
    it was chosen over `DISTINCT ON (location_code)`, which would guarantee one
    row per key and silently DROP a real school the day two schools share a
    building code. Two rows differing anywhere must both survive.
    """
    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE schoollocations AS SELECT * FROM (VALUES
            ('K066', '18', 'P.S. 66'),
            ('K066', '18', 'P.S. 66 ANNEX')
        ) t(location_code, "Geographical_District_code", location_name)
    """)
    rel = sourcedupes.relation(_TABLE)
    assert con.execute(f"SELECT count(*) FROM {rel}").fetchone()[0] == 2


def test_a_predicate_still_reaches_the_table_through_the_subquery():
    """Measured on prod (PostgreSQL 10.23): the filter is pushed INTO the
    subquery, so wrapping the table does not cost an index or a scan. Pinned
    here on the semantics — a WHERE on the wrapped relation must still filter.
    """
    con = _fixture()
    rel = sourcedupes.relation(_TABLE, "sl")
    rows = con.execute(
        f"SELECT count(*) FROM {rel} WHERE sl.location_code = 'K066'").fetchone()[0]
    assert rows == 1


# --------------------------------------------------------------------------
# The allowlist is an allowlist.
# --------------------------------------------------------------------------

def test_relation_is_byte_identical_to_the_bare_table_for_everything_else():
    """The property that makes it safe in front of the GENERIC district
    endpoint, which serves ~40 tables: for a table not in the allowlist the
    emitted text is exactly what the caller wrote before.

    ⚠ It must stay an allowlist. On a fact table two identical rows can be two
    real events — two identical payments on one day — so a default dedupe would
    destroy money.
    """
    for tbl in ("contracts", "crol", "scaenrollmentcapacity", "vendors", "payrolldata"):
        assert tbl not in sourcedupes.EXACT_DUPLICATE_SOURCES
        assert sourcedupes.relation(tbl) == tbl
        assert sourcedupes.relation(tbl, "t2") == f"{tbl} t2"
        assert not sourcedupes.is_duplicated(tbl)


def test_every_allowlisted_table_records_why_it_is_there():
    assert _TABLE in sourcedupes.EXACT_DUPLICATE_SOURCES
    for tbl, reason in sourcedupes.EXACT_DUPLICATE_SOURCES.items():
        assert isinstance(reason, str) and len(reason) > 60, (
            f"{tbl} is deduped with no measurement recorded; a table earns a "
            f"place here only once its duplicates have been shown to be a "
            f"publishing artefact")


def test_the_deduped_relation_always_carries_an_alias():
    """A subquery in FROM is a syntax error without one, and the failure would
    be at request time on a page nobody runs in CI.
    """
    for call in (sourcedupes.relation(_TABLE), sourcedupes.relation(_TABLE, "t2")):
        assert call.startswith("(SELECT DISTINCT * FROM ")
        assert not call.endswith(")"), f"no alias on {call!r}"


# --------------------------------------------------------------------------
# Banned pattern: nothing in api/ may read the raw table.
# --------------------------------------------------------------------------

# The owner declares it; the index DDL and the registry/display maps NAME it
# without reading rows from it.
_ALLOWED = {
    os.path.join("modules", "sourcedupes.py"),
    os.path.join("modules", "searchindexes.py"),
    "setup_data_pipeline.py",
    os.path.join("routers", "data_pipeline.py"),
    os.path.join("tests", "test_source_duplicate_rows.py"),
    os.path.join("tests", "test_search.py"),
}


def _sql_literals(tree):
    """Every string literal in the file, f-strings included.

    ⚠ AST literals, never the raw file text: this repo has had eight guards
    fire on their own docstring, because a comment explaining the trap contains
    the exact string the scanner looks for. An f-string's Constant parts are
    yielded separately, which is precisely what makes `JOIN {relation(...)}`
    pass and a reverted `JOIN schoollocations` fail.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def _offending(text):
    low = " ".join(text.split()).lower()
    hits = []
    for kw in ("from", "join"):
        needle = f"{kw} {_TABLE}"
        start = 0
        while True:
            i = low.find(needle, start)
            if i < 0:
                break
            # `FROM schoollocations` inside `(SELECT DISTINCT * FROM ...)` is
            # the owner's own emitted form and is the whole point.
            if not low[:i].rstrip().endswith("select distinct *"):
                hits.append(low[max(0, i - 40):i + 40])
            start = i + 1
    return hits


def test_no_query_in_api_reads_the_raw_school_locations_table():
    scanned, sites, problems = 0, 0, []
    for root, dirs, files in os.walk(_API):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", "node_modules"}]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, _API)
            scanned += 1
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            if _TABLE not in src:
                continue
            sites += 1
            if rel in _ALLOWED:
                continue
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            for lit in _sql_literals(tree):
                for hit in _offending(lit):
                    problems.append(f"{rel}: ...{hit}...")

    # ⚠ A guard that walks the tree must assert it LOOKED. A scan that reaches
    # zero files is indistinguishable from a clean one.
    assert scanned > 100, f"only scanned {scanned} files"
    assert sites >= 6, f"only {sites} files mention {_TABLE}; the scan lost its subject"
    assert not problems, (
        "these read `" + _TABLE + "` raw, so every joined figure doubles for the "
        "59 schools the City publishes twice — route them through "
        "modules/sourcedupes.relation():\n  " + "\n  ".join(problems))


def test_the_known_readers_all_route_through_the_owner():
    """The mirror of the scan above. The banned-pattern test passes if every
    reader is DELETED; this one counts that they still exist and still go
    through `relation()`, per file, so losing one cannot go quiet.
    """
    expected = {
        "main.py": 2,                             # the two shared relations
        os.path.join("routers", "search.py"): 1,  # the schools search arm
        "data_scheduler.py": 1,                   # the cached globstats tile
    }
    for rel, want in expected.items():
        src = open(os.path.join(_API, rel), encoding="utf-8").read()
        tree = ast.parse(src)
        got = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr == "relation" \
               and isinstance(fn.value, ast.Name) and fn.value.id == "sourcedupes" \
               and node.args and isinstance(node.args[0], ast.Constant) \
               and node.args[0].value == _TABLE:
                got += 1
        assert got == want, f"{rel}: {got} sourcedupes.relation('{_TABLE}') calls, expected {want}"

    # main.py must actually USE both relations it builds — a constant that is
    # computed and never interpolated is the shape of a fix that does nothing.
    main = open(os.path.join(_API, "main.py"), encoding="utf-8").read()
    assert main.count("{_SCHOOL_LOCATIONS_T2}") == 4, "the four district joins"
    assert main.count("{_SCHOOL_LOCATIONS}") == 5, "count, list, district count, 2 lookups"
