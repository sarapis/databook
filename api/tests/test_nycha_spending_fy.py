"""Guard: an out-of-range NYCHA fiscal_year is an empty result, never a 500.

⚠⚠ THE DEFECT THIS EXISTS FOR, measured on prod 2026-08-26. The spending lake is
the only NYCHA domain that is hive-PARTITIONED, so `read_parquet` on
`fiscal_year=2027/*.parquet` matches no files and DuckDB raises
`IO Error: No files found`. The handlers wrap that into an HTTPException, so a
crawler walking years produced HTTP 500s and Sentry issues DATABOOK-API-33 /
DATABOOK-API-34. Verified in both directions before the fix:

    fiscal_year=2027 -> HTTP 500
    fiscal_year=1999 -> HTTP 500
    fiscal_year=2025 -> HTTP 200

The budget / revenue / contracts domains are single files, so an unknown year
filters to zero rows there — which is why only spending was ever affected, and
why this guard is scoped to the spending endpoints.

⚠ The failure mode of the FIX matters as much: `_spending_years()` must degrade
OPEN. If it returned an empty list when it could not read the partition list,
EVERY year would look nonexistent and the explorer would serve "no data" for
real years — trading a loud 500 for a silent lie.
"""
import ast
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
NYCHA = os.path.join(ROOT, 'api/routers/nycha.py')


def _src():
    with open(NYCHA, encoding='utf-8') as fh:
        return fh.read()


def _fn(name):
    tree = ast.parse(_src())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name}() is gone — the guard cannot check what it cannot find")


def _code(node):
    """Function source with the docstring stripped.

    ⚠ `ast.unparse` INCLUDES the docstring, and these docstrings quote the very
    year literals and error strings the assertions look for. Ten guards in this
    repo have fired on their own prose.
    """
    stripped = ast.parse(ast.unparse(node)).body[0]
    body = getattr(stripped, 'body', None) or []
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        stripped.body = body[1:]
    return ast.unparse(stripped)


def test_the_partition_list_is_discovered_not_hardcoded():
    """A hardcoded year range goes stale the moment the monthly refresh adds a
    partition — and then a REAL year starts reading as missing."""
    code = _code(_fn('_spending_years'))
    assert 'DISTINCT fiscal_year' in code, \
        "the partition list is no longer discovered from the lake"
    years = re.findall(r'\b(19|20)\d{2}\b', code)
    assert not years, f"a hardcoded year literal appeared in the partition list: {years}"


def test_the_partition_list_degrades_open():
    """⚠ The fix's own failure mode. On error it must return something that makes
    `_spending_fy_missing` answer False, or every year reads as nonexistent and
    the explorer silently serves 'no data' for real years."""
    years_code = _code(_fn('_spending_years'))
    assert 'except' in years_code and 'return []' in years_code, \
        "no failure path — an unreadable partition list must not raise here"
    miss = _code(_fn('_spending_fy_missing'))
    assert re.search(r'if not years:\s*return False', miss), \
        ("_spending_fy_missing does not treat an empty/unreadable partition list "
         "as 'not missing', so a lake hiccup would empty every year")


def test_none_means_all_years_and_is_never_missing():
    miss = _code(_fn('_spending_fy_missing'))
    assert re.search(r'if fiscal_year is None:\s*return False', miss), \
        "fiscal_year=None means 'all years' and must never be treated as missing"


def test_every_fy_globbing_spending_endpoint_guards_the_year():
    """The three endpoints that glob on a CALLER-SUPPLIED fiscal_year must all
    check it. A new one added without the check reintroduces the 500."""
    src = _src()
    tree = ast.parse(src)
    guarded, unguarded = [], []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith('nycha_spending'):
            continue
        args = [a.arg for a in node.args.args]
        if 'fiscal_year' not in args:
            continue
        body = _code(node)
        (guarded if '_spending_fy_missing' in body else unguarded).append(node.name)
    assert len(guarded) >= 3, \
        (f"expected at least 3 guarded spending endpoints, found {guarded} — "
         f"the guard is not looking at what it thinks it is")
    assert not unguarded, (
        "these spending endpoints take a caller-supplied fiscal_year and glob on "
        "it without checking the partition exists, so an out-of-range year 500s: "
        + ", ".join(unguarded))


def test_the_empty_answer_is_distinguishable_from_a_broken_one():
    """`available: True` with no rows, and the real year list served beside it —
    a consumer must be able to tell 'no data for 2027' from 'we are broken'."""
    src = _src()
    hits = re.findall(r'_spending_fy_missing\(fiscal_year\):\s*\n\s*return \{([^}]*)\}', src)
    assert hits, "no endpoint returns the empty shape for a missing partition"
    for h in hits:
        assert "'available': True" in h or '"available": True' in h, \
            f"the empty answer claims the lake is unavailable: {h.strip()[:80]}"
        assert 'fiscal_years' in h, \
            f"the empty answer does not say which years DO exist: {h.strip()[:80]}"


def test_no_bare_exception_interpolation_in_the_export_handler():
    """`str()` on the commonest exceptions is the empty string — modules/errfmt."""
    code = _code(_fn('nycha_spending_records_export'))
    assert 'exc_str(exc)' in code, \
        "the export handler interpolates a bare exception, which can log nothing"
