"""Guards for the payroll lake refresh gate and the partial-fiscal-year split.

WHY THIS FILE EXISTS (measured 2026-09-09). `scripts/payroll-refresh.sh` sanity-checked
the rebuilt parquet with:

    fy = MAX(fiscal_year); ok = 20e9 <= SUM(gross) WHERE fiscal_year = fy <= 45e9

`current` mode always pulls the IN-PROGRESS fiscal year, so MAX is always a partial
year. On 2026-09-01 — the first scheduled payroll run that ever fired — the gate read
FY2027 at $6.85B (two months elapsed), scored it out of band and refused the swap,
while a COMPLETE, in-band FY2026 at $35.25B sat in the same merge. The lake stayed
frozen at FY2025 for 51 days. It is wrong in the other direction too: a partial year
climbs into the band around February, at which point the gate would wave an unfinished
year through as settled.

Nothing caught it. There were no tests over this script, the failure branch never
raised a Sentry EVENT, and it surfaced only when lake-staleness.sh crossed 40 days.

Every guard below was mutation-verified: the pre-fix expression was reintroduced and
each assertion was watched to fail.
"""
import ast
import datetime
import importlib.util
import io
import os
import re
import sys
import types

import pytest

API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(API)
SCRIPT = os.path.join(ROOT, "scripts", "payroll-refresh.sh")


def _script() -> str:
    return io.open(SCRIPT, encoding="utf-8").read()


def _sh_no_comments(text: str) -> str:
    """Strip shell comments. Without this every assertion below fires on the prose
    that EXPLAINS the defect — this repo has paid for that mistake more than a dozen
    times, and the comments here quote `MAX(fiscal_year)` verbatim."""
    out = []
    for line in text.splitlines():
        s = line.lstrip()
        if s.startswith("#"):
            continue
        out.append(line.split(" #")[0] if " #" in line else line)
    return "\n".join(out)


def _gate_source() -> str:
    """The gate's python, exactly as bash hands it to the interpreter."""
    m = re.search(
        r'ok=\$\(docker run [^\n]*python -c "\n(.*?)\n" 2>/dev/null \| tail -1\)',
        _script(), re.S)
    assert m, "could not locate the sanity gate in payroll-refresh.sh"
    return m.group(1).replace('\\"', '"').replace('\\$', '$')


# --------------------------------------------------------------------------- gate

def test_the_gate_never_scores_a_bare_max_fiscal_year():
    """The defect itself. `MAX(fiscal_year)` unqualified is always the in-progress FY."""
    gate = _gate_source()
    maxes = re.findall(r"MAX\(fiscal_year\)(.*?)'", gate)
    assert maxes, "the gate no longer selects a fiscal year at all"
    for tail in maxes:
        assert "WHERE" in tail.upper() and "fiscal_year <=" in tail, (
            "the gate selects MAX(fiscal_year) without bounding it to a COMPLETE "
            f"fiscal year: ...MAX(fiscal_year){tail}")


def test_the_gate_bounds_itself_by_the_scripts_complete_fy():
    """It must use COMPLETE_FY — the shell variable derived from the same clock as
    CLOCK_FY — rather than a literal year, which goes stale every July."""
    gate = _gate_source()
    assert "$COMPLETE_FY" in gate, "the gate does not reference $COMPLETE_FY"
    assert not re.search(r"fiscal_year <= 20\d\d", gate), \
        "the gate pins a hardcoded year instead of using $COMPLETE_FY"


def test_complete_fy_is_derived_from_clock_fy_not_respelled():
    """One spelling of the July boundary in this file. A second `python3 -c` deriving
    the fiscal year independently is how two halves of one script come to disagree."""
    body = _sh_no_comments(_script())
    assert re.search(r"COMPLETE_FY=\$\(\(\s*CLOCK_FY\s*-\s*1\s*\)\)", body), \
        "COMPLETE_FY is not derived arithmetically from CLOCK_FY"
    assert len(re.findall(r"month\s*>=\s*7", body)) == 1, \
        "the July fiscal-year boundary is spelled more than once in the script"


def test_a_merge_holding_no_complete_year_does_not_swap():
    """NULL from the bounded MAX means the merge holds only an in-progress year.
    Publishing that would replace a good lake with a part-year one."""
    gate = _gate_source()
    assert "is None" in gate, \
        "the gate does not handle a NULL latest-complete-FY, so it would compare None"


@pytest.mark.parametrize("spec,complete_fy,expect_ok,because", [
    ({2025: 33.39, 2026: 35.25, 2027: 6.85}, 2026, True,
     "the 2026-09-01 freeze: FY2026 is complete and in band; FY2027 is 2 months old"),
    ({2016: 25.16, 2023: 30.04, 2024: 34.47}, 2026, True,
     "a 2016-2024 backfill on a fresh box has no FY2026 — bound, don't pin"),
    ({2025: 33.39, 2026: 5.00, 2027: 30.00}, 2026, False,
     "the ~February trap: FY2027 has climbed into the band but has not ended"),
    ({2027: 6.85}, 2026, False,
     "only the in-progress year present"),
    ({2025: 33.39, 2026: 99.00}, 2026, False,
     "a complete year far outside the plausible band"),
])
def test_the_real_gate_against_real_shaped_data(tmp_path, spec, complete_fy, expect_ok, because):
    """Runs the gate EXTRACTED FROM THE SCRIPT — never a retyped copy, which would
    measure a different system — against parquets carrying the measured grosses."""
    duckdb = pytest.importorskip("duckdb")
    import subprocess
    p = tmp_path / "payroll.parquet"
    rows = ",".join(f"({y}, CAST({v * 1e9} AS DOUBLE))" for y, v in spec.items())
    con = duckdb.connect()
    con.execute(f"COPY (SELECT * FROM (VALUES {rows}) t(fiscal_year, gross)) "
                f"TO '{p}' (FORMAT PARQUET)")
    con.close()
    code = (_gate_source()
            .replace("/data/_payroll_tmp/payroll.parquet", str(p))
            .replace("$COMPLETE_FY", str(complete_fy)))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    verdict = (out.stdout.strip().splitlines() or [""])[-1]
    assert (verdict == "ok") is expect_ok, f"{because}: gate said {verdict!r}"
    if not expect_ok:
        assert verdict.startswith("bad"), f"a refusal must say why, got {verdict!r}"


def test_a_refusal_names_the_year_the_gate_examined():
    """The old line read `FY$FY sanity check failed` while never examining FY$FY. That
    misattribution cost a 3h20m manual re-pull of FY2026 on 2026-09-02 that could not
    have helped, because the gate was looking at FY2027."""
    body = _sh_no_comments(_script())
    m = re.search(r'if \[ "\$ok" != "ok" \]; then log "([^"]*)"', body)
    assert m, "could not find the refusal log line"
    line = m.group(1)
    assert "$ok" in line, "the refusal does not print the gate's own reason"
    assert not re.search(r"FY\$FY sanity", line), \
        "the refusal still attributes the failure to the loop's FY"


def test_the_gates_diagnostic_cannot_itself_fail_the_gate():
    """DuckDB returns Decimal for a DECIMAL column and Decimal/float raises, so an
    unguarded `g/1e9` in the message would refuse an otherwise-good swap."""
    gate = _gate_source()
    assert re.search(r"g\s*=\s*float\(", gate), \
        "SUM(gross) is not coerced to float before being formatted"


# ----------------------------------------------------------------- alerting path

def test_the_swapped_nothing_path_raises_a_sentry_event():
    """`fail()` covers the hard errors. A run that downloads 10M rows and then declines
    to publish them exits 0 through the else-branch, which had NO event — so it
    reported only via the cron check-in this script documents as silently discarded.
    That is why the 51-day freeze surfaced through lake-staleness.sh instead."""
    body = _sh_no_comments(_script())
    # ⚠ anchored to end-of-string, not `\nfi\n`: _sh_no_comments joins lines and so
    # drops the file's trailing newline, which silently made this never match.
    m = re.search(r"\nelse\n(.*?)\nfi\s*$", body, re.S)
    assert m, "could not find the outcome else-branch"
    branch = m.group(1)
    assert "sentry_checkin error" in branch, "sanity: wrong branch matched"
    assert "sentry_event" in branch, \
        "the swapped-nothing branch does not raise a Sentry error event"


def test_the_error_event_is_not_gated_to_current_mode():
    """checkin/hc_ping are gated because a backfill is not the scheduled job. An error
    event carries no schedule, and the 2026-09-02 backfill also silently swapped
    nothing — so gating it would re-create the blind spot for manual runs."""
    src = _script()
    m = re.search(r"sentry_event\(\)\s*\{(.*?)\n\}", src, re.S)
    assert m, "could not find sentry_event()"
    assert '[ "$MODE" = current ]' not in m.group(1), \
        "sentry_event is gated to `current`, so manual runs fail silently"


# ------------------------------------------------- the partial-fiscal-year split

def _payroll_router():
    """Load routers/payroll.py by path with a REAL `_fy_of` extracted from oce.py.

    ⚠ api/conftest.py replaces the whole `modules` package with a MagicMock, so a
    plain import yields mocks that satisfy almost any assertion. Importing routers.oce
    outright drags in the entire procurement router, so `_fy_of` is lifted out of it by
    AST — which also means this test breaks if that function is ever moved or renamed,
    rather than silently testing a stub."""
    oce_src = io.open(os.path.join(API, "routers", "oce.py"), encoding="utf-8").read()
    tree = ast.parse(oce_src)
    fn = next((n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == "_fy_of"), None)
    assert fn is not None, "routers.oce._fy_of has moved — payroll.py imports it"
    ns: dict = {}
    # `_fy_of` is annotated Optional[...]; annotations evaluate at def time, so the
    # exec namespace needs the same names oce.py has in scope.
    exec("import re\nfrom typing import Optional\n" + ast.unparse(fn), ns)

    oce_stub = types.ModuleType("routers.oce")
    oce_stub._fy_of = ns["_fy_of"]
    duckpool = types.ModuleType("modules.duckpool")
    async def _to_thread(fn_, *a, **k):
        return fn_(*a, **k)
    duckpool.to_duckdb_thread = _to_thread
    saved = {k: sys.modules.get(k) for k in ("routers.oce", "modules.duckpool")}
    sys.modules["routers.oce"] = oce_stub
    sys.modules["modules.duckpool"] = duckpool
    try:
        spec = importlib.util.spec_from_file_location(
            "_payroll_split_test", os.path.join(API, "routers", "payroll.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_payroll_imports_the_one_fiscal_year_definition():
    """A local copy of the July boundary would drift from every other chart."""
    src = io.open(os.path.join(API, "routers", "payroll.py"), encoding="utf-8").read()
    body = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert re.search(r"from routers\.oce import [^\n]*\b_fy_of\b", body), \
        "payroll.py does not import _fy_of from routers.oce"
    assert "def _fy_of" not in body, "payroll.py defines its own _fy_of"


def test_the_in_progress_year_is_excluded_from_the_bars_and_reported(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    mod = _payroll_router()
    cur_fy = mod._fy_of(datetime.date.today().isoformat())
    # one complete year, one in progress — whatever today's date is
    spec = {cur_fy - 1: 35.25e9, cur_fy: 6.85e9}
    p = tmp_path / "payroll.parquet"
    rows = ",".join(
        f"({y}, 'AGENCY', 'TITLE', 'X', CAST({v} AS DOUBLE), CAST({v} AS DOUBLE), "
        f"CAST(0 AS DOUBLE), CAST(0 AS DOUBLE), 100, CAST(0 AS DOUBLE), 0)"
        for y, v in spec.items())
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT * FROM (VALUES {rows}) t(fiscal_year, agency, title, payroll_type,"
        f" gross, base, overtime, other, records, salary_sum, salary_count))"
        f" TO '{p}' (FORMAT PARQUET)")
    con.close()

    mod._src = lambda: f"read_parquet('{p}')"
    out = mod._query_summary()

    drawn = {r["year"] for r in out["by_year"]}
    reported = {r["year"] for r in out["partial"]}
    assert cur_fy not in drawn, \
        f"the in-progress FY{cur_fy} is drawn as a bar beside complete years"
    assert reported == {cur_fy}, f"the in-progress year is not reported: {out['partial']}"
    assert drawn == {cur_fy - 1}

    # Closure: nothing may fall into an undisclosed gap.
    assert drawn | reported == set(spec), \
        "by_year + partial does not account for every year in the lake"
