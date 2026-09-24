"""Guards for the graduation-outcomes ingest (docs/GRADUATION-INGEST-PLAN.md).

⚠⚠ EVERY GUARD HERE READS AST STRING LITERALS, NEVER THE RAW FILE TEXT. The
code these pin is *explained* by comments that quote the very strings the guard
searches for — `main.py` carries "Report Category" and "School" in the comment
justifying the filter. A text scan would be satisfied by its own explanation,
which this repo has now paid for eight times.
"""
import ast
import os

API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tree(rel):
    with open(os.path.join(API, rel), encoding='utf-8') as fh:
        return ast.parse(fh.read()), fh


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def _code(node):
    """ast.unparse MINUS the docstring — the docstring is prose, not code."""
    clone = ast.parse(ast.unparse(node)).body[0]
    if (clone.body and isinstance(clone.body[0], ast.Expr)
            and isinstance(clone.body[0].value, ast.Constant)
            and isinstance(clone.body[0].value.value, str)):
        clone.body = clone.body[1:]
    return ast.unparse(clone)


def _assigned_literal(tree, name):
    """The literal value assigned to a module-level or nested name."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"no literal assignment for {name}")


# ── the registry path ───────────────────────────────────────────────────────

def test_graduation_is_registered_by_a_path_main_actually_calls():
    """⚠⚠ `UNTRACKED_TABLES` ALONE REGISTERS NOTHING ON PROD.

    `register_untracked_tables()` is reachable only from
    `populate_from_datasets_json`, which returns early without a dev-path
    `datasets.json`. Declaring a dataset there and nowhere else is how the
    capital rebuild "reported success and created none of the seven".

    So the dataset must be in `GRADUATION_DATASETS`, that list must be unioned
    into `EXPLICIT_DATASETS`, and `main()` must call the function that walks it.
    """
    tree, _ = _tree('setup_data_pipeline.py')

    assert 'graduationoutcomes' in _assigned_literal(tree, 'GRADUATION_DATASETS')

    # EXPLICIT_DATASETS is a concatenation, not a literal — read the operands.
    names = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'EXPLICIT_DATASETS'
                        for t in node.targets)):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Name):
                    names.add(sub.id)
    assert 'GRADUATION_DATASETS' in names, (
        'GRADUATION_DATASETS is declared but never unioned into '
        'EXPLICIT_DATASETS — the loop would not see it, which is the exact '
        'failure mode this function exists to avoid')

    loop_src = _code(_func(tree, 'register_explicit_datasets'))
    assert 'EXPLICIT_DATASETS' in loop_src

    main_src = _code(_func(tree, 'main'))
    assert 'register_explicit_datasets' in main_src, (
        'main() must call the registration function, or nothing registers')
    assert 'register_untracked_tables' not in main_src, (
        'register_untracked_tables must stay out of main() — promoting it '
        'would flip needs_normalization on 27 prod rows')


def test_the_dataset_is_declared_once_with_its_socrata_id_and_csv_url():
    tree, _ = _tree('setup_data_pipeline.py')
    untracked = _assigned_literal(tree, 'UNTRACKED_TABLES')
    corrections = _assigned_literal(tree, 'METADATA_CORRECTIONS')

    assert untracked['graduationoutcomes'][1:] == ('socrata', 'Schools')
    meta = corrections['graduationoutcomes']
    assert meta['socrata_id'] == 'mjm3-8dw8'
    # ⚠ The CSV, not the JSON API: /import-csv builds the table from the CSV
    # HEADER, which carries display names ("# Grads") and a `School Name`
    # column the JSON API does not expose.
    assert meta['source_url'].endswith('rows.csv?accessType=DOWNLOAD')
    assert 'mjm3-8dw8' in meta['source_url']


# ── the serving path ────────────────────────────────────────────────────────

def test_the_section_endpoint_filters_to_School_grain():
    """⚠⚠ ONE TABLE, SIX GRAINS, ONE KEY COLUMN — and the overlap is real.

    `mjm3-8dw8` stacks School / District / Borough / Charter School / Citywide /
    Transfer School rows in one table, all keyed on `Geographic Subdivision`.
    At School grain that value is a DBN — but a Transfer School row's is too.

    Measured 2026-09-21: of 497 School DBNs, **54 also appear under
    'Transfer School'**. Filtering on the DBN alone therefore returns both sets
    and double-counts 11% of high schools. (Charter School is DBN-shaped too —
    85 of them — but overlaps School on zero.)
    """
    tree, _ = _tree('main.py')
    fn = _func(tree, 'get_school_section')

    col_map = None
    fixed = None
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == 'col_map':
                    col_map = ast.literal_eval(node.value)
                if isinstance(t, ast.Name) and t.id == 'fixed_filters':
                    fixed = ast.literal_eval(node.value)

    assert col_map and col_map.get('graduationoutcomes') == 'Geographic Subdivision'
    assert fixed, 'get_school_section declares no fixed_filters map'
    assert fixed.get('graduationoutcomes') == ('Report Category', 'School'), (
        "graduationoutcomes must be pinned to Report Category='School'; without "
        "it, 54 of 497 schools also match their Transfer School rows")

    # And the filter must be USED, not merely declared. Read the emitted SQL
    # from the f-string's literal parts, never the comments around it.
    sql_parts = []
    for node in ast.walk(fn):
        if isinstance(node, ast.JoinedStr):
            sql_parts.append(''.join(
                v.value for v in node.values if isinstance(v, ast.Constant)))
    two_predicate = [q for q in sql_parts if '$1' in q and '$2' in q]
    assert two_predicate, (
        'no two-predicate query is emitted, so the fixed filter is declared '
        'and never applied')


def test_the_view_section_keys_on_the_DBN_not_the_building():
    """`Geographic Subdivision` holds a DBN (02M422), so the section must read
    `system_code`. `location_code` is the building (M422) and matches nothing.
    """
    path = os.path.join(API, '..', 'app', 'app', 'Custom', 'SchoolDatasets.php')
    src = open(os.path.normpath(path), encoding='utf-8').read()

    start = src.index("'graduation' => [")
    block = src[start:src.index("],", src.index("'DBNkey'", start))]
    assert "'table' => 'graduationoutcomes'" in block
    assert "'DBNkey' => 'system_code'" in block, (
        "the graduation section must key on system_code (the DBN)")
    assert "'location_code'" not in block


# ── the index ───────────────────────────────────────────────────────────────

# The CSV header, read from the live export 2026-09-21. Pinned as a constant on
# the `_CONTRACTS_COLS` precedent, because `recreate_table_indexes` SWALLOWS a
# failed CREATE INDEX — it prints ✗ and moves on — so an index naming a column
# that does not exist would never be created and nothing would raise.
_GRADUATION_COLS = {
    'Report Category', 'Geographic Subdivision', 'School Name', 'Category',
    'Cohort Year', 'Cohort', '# Total Cohort', '# Grads', '% Grads',
    '# Total Regents', '% Total Regents of Cohort', '% Total Regents of Grads',
    '# Advanced Regents', '% Advanced Regents of Cohort',
    '% Advanced Regents of Grads', '# Regents without Advanced',
    '% Regents without Advanced of Cohort',
    '% Regents without Advanced of Grads', '# Local', '% Local of Cohort',
    '% Local of Grads', '# Still Enrolled', '% Still Enrolled', '# Dropout',
    '% Dropout', '# SACC (IEP Diploma)', '% SACC (IEP Diploma) of Cohort',
    '# TASC (GED)', '% TASC (GED) of Cohort',
}


def test_the_declared_indexes_name_columns_that_exist():
    tree, _ = _tree('data_scheduler.py')
    table_indexes = _assigned_literal(tree, 'TABLE_INDEXES')
    entries = table_indexes['graduationoutcomes']

    declared = set()
    for entry in entries:
        for col in entry[1].split(','):
            declared.add(col.strip().strip('"'))

    unknown = declared - _GRADUATION_COLS
    assert not unknown, f'index declares columns absent from the CSV header: {unknown}'

    # The DBN index is what keeps the profile page off a 321,002-row seq scan.
    assert any('Geographic Subdivision' in e[1] for e in entries), (
        'no index on the column the section endpoint filters by')


def test_the_view_columns_all_exist_in_the_source():
    """A renamed or mistyped column renders an empty cell, not an error."""
    path = os.path.join(API, '..', 'app', 'app', 'Custom', 'SchoolDatasets.php')
    src = open(os.path.normpath(path), encoding='utf-8').read()
    start = src.index("'graduation' => [")
    block = src[start:src.index("'DBNkey'", start)]

    import re
    referenced = set(re.findall(r'r\["([^"]+)"\]', block))
    referenced |= {m for m in re.findall(r"'\"([^\"]+)\"'", block)}
    unknown = referenced - _GRADUATION_COLS
    assert not unknown, f'view reads columns absent from the source: {unknown}'


# ── the wiring that 500'd the page ──────────────────────────────────────────

_PHP = os.path.normpath(
    os.path.join(API, '..', 'app', 'app', 'Custom', 'SchoolDatasets.php'))


def _school_section_keys():
    """($dd keys, $list keys, flattened $menu entries) from SchoolDatasets."""
    import re
    src = open(_PHP, encoding='utf-8').read()

    def _block(decl):
        i = src.index(decl)
        depth, j = 0, src.index('[', i)
        start = j
        while True:
            if src[j] == '[':
                depth += 1
            elif src[j] == ']':
                depth -= 1
                if depth == 0:
                    return src[start:j + 1]
            j += 1

    dd = re.findall(r"^\t\t'([a-z0-9-]+)' => \[", _block('public $dd'), re.M)
    lst = re.findall(r"'([a-z0-9-]+)' => '", _block('public $list'))
    menu = re.findall(r"'([a-z0-9-]+)',", _block('public $menu'))
    return dd, lst, menu


def test_every_school_section_is_wired_into_list_and_menu():
    """⚠⚠ THREE STRUCTURES MUST AGREE, AND MISSING ONE IS A 500, NOT A GAP.

    A section needs an entry in `$dd`, `$list` AND `$menu`. `Districts.php:268`
    reads `$ds->list[$section]` unguarded, so a section present in `$dd` and
    absent from `$list` throws `Undefined index` and the page 500s.

    ⭐ Found exactly that way on 2026-09-21: the graduation section was added to
    `$dd` alone, every unit test passed, and the page 500'd. Only rendering
    found it — the documented lesson that a value existing server-side proves
    nothing about the page receiving it.

    ⚠ `schools` is the index listing, not a profile tab, so it is legitimately
    the one `$dd` key absent from `$menu`. Measured, not assumed.
    """
    dd, lst, menu = _school_section_keys()

    assert len(dd) > 10, f'parsed only {len(dd)} sections — the parser broke'

    assert set(dd) == set(lst), (
        f'$dd and $list disagree. Only in $dd: {sorted(set(dd) - set(lst))}; '
        f'only in $list: {sorted(set(lst) - set(dd))}. A section in $dd but '
        'not $list makes Districts.php:268 throw Undefined index.')

    assert set(dd) - set(menu) == {'schools'}, (
        f'$dd and $menu disagree beyond the index listing: '
        f'{sorted((set(dd) - set(menu)) - {"schools"})} would be unreachable '
        'from the school profile nav.')


def test_graduation_declares_an_empty_state_of_its_own():
    """⚠ "We hold no records" and "this school cannot have these records" are
    different claims. Only ~497 of 2,131 schools have a graduating cohort, so
    the shared "No data for this school" would invite every elementary-school
    reader to think something was missing.
    """
    src = open(_PHP, encoding='utf-8').read()
    start = src.index("'graduation' => [")
    block = src[start:src.index("'DBNkey'", start)]
    assert "'emptyText'" in block, (
        'the graduation section must override the default empty state')
    assert 'No graduating cohort' in block


# ── the DISTRICT panel (⚑ B) ────────────────────────────────────────────────

_DIST_PHP = os.path.normpath(
    os.path.join(API, '..', 'app', 'app', 'Custom', 'DistDatasets.php'))


def test_the_district_column_is_declared_server_side():
    """⚠ The districts endpoint falls back to `f`, a CLIENT-supplied column name,
    when `DISTRICT_COLUMNS` has no entry. Declaring it server-side means the
    column the query filters on is never something a caller chose.
    """
    tree, _ = _tree('main.py')
    cols = _assigned_literal(tree, 'DISTRICT_COLUMNS')
    assert cols.get('sd', {}).get('graduationoutcomes') == ['Geographic Subdivision']


def test_the_district_endpoint_pins_the_grain_and_actually_applies_it():
    """⚠⚠ ONE TABLE, SIX GRAINS, ONE KEY COLUMN — the District half.

    At District grain `Geographic Subdivision` is a bare number (1-32); every
    other grain is a DBN, a borough name or "Citywide", so measured 2026-09-21
    no district id collides and the filter changes no row today. The School half
    DOES collide (54 of 497 DBNs are also Transfer School), so the grain is
    pinned here to make it a guarantee rather than a coincidence.
    """
    tree, _ = _tree('main.py')
    fixed = _assigned_literal(tree, '_DISTRICT_FIXED_FILTERS')
    assert fixed.get('graduationoutcomes') == ('Report Category', 'District')

    fn = _func(tree, 'get_subdataset_by_administrative_district')

    # ⚠⚠ ASSERTING THE QUERY EXISTS IS NOT ASSERTING IT RUNS. The first draft
    # scanned the function's string literals for a two-predicate SELECT and was
    # SILENT on a mutation that set `fixed = None` — the literal was still
    # there, inside a branch nothing could enter. So this walks the guarding
    # `if` instead: the name it tests must be assigned FROM the map, and the
    # two-predicate query must live in that branch's body.
    gated = [n.targets[0].id for n in ast.walk(fn)
             if isinstance(n, ast.Assign)
             and isinstance(n.targets[0], ast.Name)
             and any(isinstance(sub, ast.Name)
                     and sub.id == '_DISTRICT_FIXED_FILTERS'
                     for sub in ast.walk(n.value))]
    assert gated, (
        'nothing in the endpoint reads _DISTRICT_FIXED_FILTERS, so the grain '
        'filter is declared and never applied')

    found = False
    for node in ast.walk(fn):
        if (isinstance(node, ast.If) and isinstance(node.test, ast.Name)
                and node.test.id in gated):
            body = ' '.join(
                n.value for n in ast.walk(node)
                if isinstance(n, ast.Constant) and isinstance(n.value, str))
            if '$1' in body and '$2' in body and body.count('"{}"') >= 2:
                found = True
    assert found, (
        'the branch guarded by _DISTRICT_FIXED_FILTERS does not emit a query '
        'filtering on the key AND the fixed column')


def test_no_fixed_filter_table_can_reach_an_early_returning_branch():
    """⚠⚠ THE FILTER IS APPLIED IN THE FINAL BRANCH, AND THREE BRANCHES RETURN
    BEFORE IT. `cd`/`cc` value-format special cases each `return` their own
    query, so a table listed in one of them would skip the grain filter
    silently. Today graduation is `sd`-only; this keeps that true.
    """
    tree, _ = _tree('main.py')
    fixed = set(_assigned_literal(tree, '_DISTRICT_FIXED_FILTERS'))
    for name in ('_CD_BOROUGH_FORMAT_TABLES', '_CD_BOARD_ONLY_TABLES',
                 '_CC_NYCC_PREFIX_TABLES'):
        early = set(_assigned_literal(tree, name))
        clash = fixed & early
        assert not clash, (
            f'{sorted(clash)} is in {name}, which returns before the fixed '
            'filter is applied — the grain filter would be silently skipped')


def test_the_district_section_is_reachable_only_from_a_school_district():
    """`DistDatasets::get()` returns null when a section has no `map` entry for
    the requested type, so a `map` of only `sd` is what keeps a graduation panel
    off community-board, council and NTA districts — where the key would mean
    something else entirely.
    """
    src = open(_DIST_PHP, encoding='utf-8').read()
    start = src.index("'graduation' => [")
    # ⚠ +2 to INCLUDE the map array's own closing bracket — without it the slice
    # ends mid-literal and the assertion below can never match. The guard caught
    # exactly that on first writing.
    block = src[start:src.index("],", src.index("'map'", start)) + 2]
    assert "'table' => 'graduationoutcomes'" in block
    assert "'map' => ['sd' => 'Geographic Subdivision']" in block, (
        'the district graduation section must map ONLY sd')
    for other in ("'cd' =>", "'cc' =>", "'nta' =>"):
        assert other not in block


def test_preselects_come_from_an_explicit_key_in_both_registries():
    """⚠⚠ THE LANDMINE THIS EXISTS FOR: a DORMANT value in `filters`.

    `filters` has documented `fld no => def value` since it was written and only
    the KEYS were ever read, so values there never did anything. Deriving
    preselects from them was inert for schools (all 15 other sections declare
    null) and would NOT have been for districts — `requests` carries
    `0 => '2020-07-01'`, a Publication Date, so the live Requests page would
    have been pinned to a single day by a line nobody wrote for that purpose.

    So both registries read an explicit `fltPreselect`, and neither may go back
    to deriving from `filters`.
    """
    school = open(_PHP, encoding='utf-8').read()
    dist = open(_DIST_PHP, encoding='utf-8').read()

    for name, src in (('SchoolDatasets', school), ('DistDatasets', dist)):
        assert "$dd['fltPreselect']" in src, f'{name} does not read fltPreselect'
        assert "array_filter($dd['filters']" not in src, (
            f'{name} derives preselects from `filters` again — a dormant value '
            'there would silently change its page')

    # And the dormant declaration is still dormant, not deleted or promoted.
    assert "'filters' => [0 => '2020-07-01'" in dist, (
        "requests' dormant filters value should be left exactly as found")
    assert "'fltPreselect'" not in dist[dist.index("'requests' => ["):
                                        dist.index("'facilities' => [")]


def test_the_district_view_columns_all_exist_in_the_source():
    import re
    src = open(_DIST_PHP, encoding='utf-8').read()
    start = src.index("'graduation' => [")
    block = src[start:src.index("'map'", start)]
    referenced = set(re.findall(r'r\["([^"]+)"\]', block))
    referenced |= set(re.findall(r"'\"([^\"]+)\"'", block))
    unknown = referenced - _GRADUATION_COLS
    assert not unknown, f'district view reads columns absent from the source: {unknown}'


def test_every_district_section_is_wired_into_list_and_menu():
    """The three-structure trap, measured for this registry: `DistDatasets`
    holds one menu PER TYPE, so the invariant is that `$dd` and `$list` agree
    exactly and every menu entry names a real section.
    """
    import re
    src = open(_DIST_PHP, encoding='utf-8').read()

    def _block(decl):
        i = src.index(decl)
        depth, j = 0, src.index('[', i)
        start = j
        while True:
            if src[j] == '[':
                depth += 1
            elif src[j] == ']':
                depth -= 1
                if depth == 0:
                    return src[start:j + 1]
            j += 1

    dd = re.findall(r"^\t\t'([a-z0-9-]+)' => \[", _block('public $dd'), re.M)
    lst = re.findall(r"'([a-z0-9-]+)' => '", _block('public $list'))
    menu = set(re.findall(r"'([a-z0-9-]+)',", _block('public $menu')))

    assert len(dd) > 5, f'parsed only {len(dd)} sections — the parser broke'
    assert set(dd) == set(lst), (
        f'$dd and $list disagree. Only in $dd: {sorted(set(dd) - set(lst))}; '
        f'only in $list: {sorted(set(lst) - set(dd))}')
    assert menu - set(dd) == set(), (
        f'$menu names sections that do not exist: {sorted(menu - set(dd))}')
    assert 'graduation' in menu, 'graduation is declared but unreachable from any nav'
