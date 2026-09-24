"""Guards on the capital datasets' Pipeline registration.

⚠⚠ THE TRAP THIS SESSION WALKED INTO. Adding a dataset to `UNTRACKED_TABLES` and
`METADATA_CORRECTIONS` registers NOTHING: `register_untracked_tables()` is
reachable only from `populate_from_datasets_json`, which returns early unless a
`datasets.json` exists at a dev path that is not on the box. The first attempt
here declared all seven, ran the seed, saw it print "Done." — and created none of
them. That is this repo's oldest defect class (a step that reports success
without having any effect), and the fix is a function `main()` actually calls.

⚠ Promoting the whole of `register_untracked_tables` is NOT the answer — it was
measured previously to flip `needs_normalization` on 27 prod rows and register
four unrelated fire datasets. Hence a NAMED set.
"""
import importlib.util
import os
import ast
import re

API = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
SETUP = os.path.join(API, 'setup_data_pipeline.py')
SCHEDULER = os.path.join(API, 'data_scheduler.py')

# The datasets the capital rebuild adds, with the row count each returned from a
# real Pipeline ingest on 2026-09-05. The counts are here so a future reader can
# tell "the source shrank" from "our ingest broke".
# ⚠ `parkscapitaltracker` carries NO socrata id on purpose: its Socrata mirror
# (4hcv-tc5r) served 0 rows while advertising a same-day refresh, so it is an
# extractor reading the Parks feed. See test_parks_capital_tracker.py.
EXTRACTOR_ONLY = {'parkscapitaltracker': 2244}

EXPECTED = {
    'cpdb_geometry_points':   ('h2ic-zdws', 2776),
    'cpdb_geometry_polygons': ('9jkp-n57r', 1784),
    'climatebudgeting':       ('c99a-c5ux', 259491),
    'councilcapitalbudget':   ('t474-a92g', 11503),
    'capitalfundingsource':   ('4utb-pisg', 188),
    'capitalcashflow':        ('4xfc-mzbg', 2356),
    'sogrneeds':              ('vck7-ujai', 43063),
}


def _src(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _load_setup():
    spec = importlib.util.spec_from_file_location('setup_data_pipeline', SETUP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


setup = _load_setup()


def test_every_capital_dataset_is_declared_with_its_socrata_id():
    for table in EXTRACTOR_ONLY:
        assert table in setup.UNTRACKED_TABLES, f'{table} is not declared'
        assert setup.METADATA_CORRECTIONS.get(table, {}).get('socrata_id') is None, (
            f'{table} must NOT carry a socrata id — its mirror serves 0 rows')
    for table, (sid, _) in EXPECTED.items():
        assert table in setup.UNTRACKED_TABLES, f'{table} is not declared'
        assert table in setup.METADATA_CORRECTIONS, f'{table} has no socrata id'
        assert setup.METADATA_CORRECTIONS[table]['socrata_id'] == sid, (
            f'{table} should be {sid}')


def test_the_capital_set_is_registered_by_something_main_calls():
    """⚠⚠ The whole point. Declaring is not registering."""
    assert hasattr(setup, 'CAPITAL_DATASETS'), 'CAPITAL_DATASETS is missing'
    assert set(setup.CAPITAL_DATASETS) == set(EXPECTED) | set(EXTRACTOR_ONLY), (
        'CAPITAL_DATASETS must name exactly the datasets this rebuild adds')

    # ⚠ EXPRESSED AS THE PROPERTY, NOT A FUNCTION NAME. This asserted the
    # literal `register_capital_datasets(` until 2026-09-21, when the graduation
    # ingest made that function register more than capital and it was renamed
    # `register_explicit_datasets`. The guard fired, correctly — the rename was
    # real. But a name is not the property: what must hold is that main() calls
    # a registration function AND that the list it walks still includes
    # CAPITAL_DATASETS. Stated that way, a future rename cannot break it while
    # the property holds, and DROPPING capital from the union breaks it even if
    # the name never moves. Strengthened, not relaxed.
    src = _src(SETUP)
    m = re.search(r'async def main\(\):(.*?)\nif __name__', src, re.S)
    assert m, 'main() not found'
    body = m.group(1)

    called = re.findall(r'\b(register_\w*datasets)\s*\(', body)
    assert called, (
        'main() calls no register_*_datasets() function. Adding rows to '
        'UNTRACKED_TABLES alone registers nothing — register_untracked_tables() '
        'is unreachable in production.')

    tree = ast.parse(src)

    def _names_in(assigned):
        """Every Name referenced by the literal assigned to `assigned`."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == assigned
                    for t in node.targets):
                return {n.id for n in ast.walk(node.value)
                        if isinstance(n, ast.Name)}
        return set()

    covered = False
    for fname in called:
        fn = next((n for n in ast.walk(tree)
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and n.name == fname), None)
        if fn is None:
            continue
        walked = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        # directly, or through one level of union (EXPLICIT_DATASETS = A + B)
        if 'CAPITAL_DATASETS' in walked:
            covered = True
        for candidate in walked:
            if 'CAPITAL_DATASETS' in _names_in(candidate):
                covered = True
    assert covered, (
        f'main() calls {called}, but none of them walks a list that includes '
        'CAPITAL_DATASETS — the capital set would be declared and never '
        'registered, which is the exact failure this guard exists to catch.')


def test_capitalbudget_is_reactivated_and_no_longer_dated():
    """⚠ Two halves, and one without the other does nothing.

    Removing it from DATED_DATASETS stops it being re-deactivated; only an
    explicit UPDATE flips the `is_active=false` already stored on the row.
    """
    assert 'capitalbudget' not in setup.DATED_DATASETS, (
        'capitalbudget is not dated — NYC published the Adopted FY2027 budget '
        'on 2026-07-13 (46m8-77gv)')
    assert 'capitalbudget' in setup.REACTIVATE_DATASETS, (
        'capitalbudget needs an explicit reactivation; deleting it from '
        'DATED_DATASETS leaves is_active=false untouched')


def test_the_retired_series_stays_deactivated():
    """The rebuild demotes it to history — it must not come back on."""
    for table in ('capitalprojectsdollarscomp', 'capitalprojectsdollars',
                  'capitalprojectsmilestones'):
        assert table in setup.DATED_DATASETS, (
            f'{table} is the retired 2023 series and must stay deactivated')
        assert table not in getattr(setup, 'REACTIVATE_DATASETS', []), (
            f'{table} must never be reactivated')


def test_the_csv_field_limit_is_raised_for_large_geometry():
    """⚠⚠ Python's csv module caps a field at 131,072 bytes, and a CPDB
    MultiPolygon exceeds it. Without this, `cpdb_geometry_polygons` fails with
    "field larger than field limit (131072)" — measured, while the points set
    ingested fine, so the failure looks dataset-specific rather than structural.

    ⚠ Not `sys.maxsize`: it overflows the C long the module casts to.
    """
    src = _src(SCHEDULER)
    m = re.search(r'csv\.field_size_limit\(([^)]*)\)', src)
    assert m, (
        'data_scheduler must raise the csv field size limit, or any dataset '
        'with a cell over 128 KB (CPDB geometry) cannot be ingested')
    assert 'maxsize' not in m.group(1), (
        'sys.maxsize overflows the C long csv casts to; use a bounded value')


def test_geometry_is_registered_because_nothing_else_carries_it():
    """CPDB's tabular projects have no geometry at all.

    Both sets are needed: measured 2026-09-05 they are disjoint and together
    cover 4,560 projects — 2,776 points + 1,784 polygons — every one of which
    joins the spine on (agency, project id).
    """
    assert 'cpdb_geometry_points' in setup.CAPITAL_DATASETS
    assert 'cpdb_geometry_polygons' in setup.CAPITAL_DATASETS
