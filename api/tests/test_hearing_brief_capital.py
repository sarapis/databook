"""Guard on the hearing brief's capital query, which was broken and silent.

⚠⚠ THE DEFECT. `routers/data_pipeline.py` queried `capitalprojectslist` with
FOUR column names that do not exist — `project_id`, `short_description`,
`total_plan_commtmts`, `man_agency_name`. Measured against the live database
2026-09-06 it raises `column "project_id" does not exist`, and the query sits
inside an `except Exception` that only prints. So **every hearing brief ever
generated has carried an empty capital section**, and nothing surfaced it.

That is this repo's oldest failure shape: a path that returns 200 with a
missing section is byte-identical, to every consumer, to one where there is
genuinely nothing to show. `/get/search`'s people group returned `[]` for eight
weeks the same way.

⚠ A test asserting the CORRECTED names are present would pass against a query
that names them and something else besides. This reads every column the SQL
actually references and checks it against the table's real schema, so a future
rename on either side fails the build rather than the brief.
"""
import ast
import os
import re

API = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
PIPELINE = os.path.join(API, 'routers', 'data_pipeline.py')

# ⚠ The real schema of `capitalprojectslist`, from information_schema on
# 2026-09-06. Only the columns this query needs are pinned; the table has many
# more and listing all of them would make this fail on unrelated source changes.
REAL_COLUMNS = {
    'projectid', 'description', 'plannedcommit_total', 'magencyname',
    'magency', 'magencyacro', 'maprojid', 'ccpversion',
}
# The names that were there, and must never come back.
BROKEN_COLUMNS = {
    'project_id', 'short_description', 'total_plan_commtmts', 'man_agency_name',
}


def _capital_sql():
    """The SQL string the hearing brief's capital block actually sends.

    ⚠ Read from the AST, not by line number: the block moves, and a scan of the
    raw file would also match this module's own prose naming the broken columns.
    """
    with open(PIPELINE, encoding='utf-8') as fh:
        tree = ast.parse(fh.read())
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            parts = [v.value for v in node.values
                     if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            text = ''.join(parts)
            if 'capitalprojectslist' in text and 'SELECT' in text.upper():
                found.append(text)
    assert found, 'the capital query was not found — has it moved or been deleted?'
    assert len(found) == 1, f'expected one capital query, found {len(found)}'
    return found[0]


def test_the_capital_query_names_no_column_that_does_not_exist():
    """⚠⚠ Verified in the failure direction against the live database, not
    inferred: the old form raises `column "project_id" does not exist`."""
    sql = _capital_sql().lower()

    # ⚠ Strip FUNCTION names structurally — an identifier followed by `(` — and
    # cast targets, rather than growing a keyword list. A list has to be edited
    # every time the query gains a function, and the edit is exactly when the
    # guard is most likely to be quietly widened past the defect. Adding a
    # numeric cast for the ordering bug immediately tripped the list version on
    # `nullif`, `btrim` and `numeric`.
    sql = re.sub(r'\b[a-z_]+\s*\(', '(', sql)
    sql = re.sub(r'::\s*[a-z_]+', '', sql)

    referenced = set(re.findall(r'\b[a-z_]{4,}\b', sql))
    keywords = {'select', 'from', 'where', 'order', 'desc', 'nulls', 'last',
                'limit', 'conditions', 'budget', 'capitalprojectslist', 'ilike'}
    columns = referenced - keywords
    unknown = columns - REAL_COLUMNS
    assert not unknown, (
        f'the hearing brief names column(s) that do not exist on '
        f'capitalprojectslist: {sorted(unknown)}')


def test_the_four_broken_names_never_return():
    sql = _capital_sql().lower()
    back = {c for c in BROKEN_COLUMNS if re.search(rf'\b{c}\b', sql)}
    assert not back, f'a column name that never existed is back: {sorted(back)}'


def test_the_result_is_read_with_the_same_names_the_query_selects():
    """⚠ THE HALF A COLUMN FIX MISSES. Correcting the SQL while still reading
    `r.get("project_id")` leaves the section rendering blanks — a silent
    failure replaced by a quieter one. The reader must use the selected names.
    """
    with open(PIPELINE, encoding='utf-8') as fh:
        src = fh.read()
    block = re.search(r'theme_result\["capital_projects"\]\.append\((.*?)\)\n',
                      src, re.S)
    assert block, 'the capital append block was not found'
    body = block.group(1)
    for selected in ('projectid', 'description'):
        assert re.search(rf'r\.get\("{selected}"', body), (
            f'the result is not read using the selected column {selected!r}: {body}')
    for broken in BROKEN_COLUMNS:
        assert f'r.get("{broken}"' not in body, (
            f'still reading the result by a name the query does not select: {broken}')


def test_the_money_column_is_cast_before_it_is_ordered():
    """⚠⚠ A SECOND DEFECT IN THE SAME QUERY, which fixing the column names alone
    would have shipped. `plannedcommit_total` is TEXT on `capitalprojectslist`,
    so `ORDER BY plannedcommit_total DESC` sorts lexicographically: measured on
    Parks + DOT, the brief would list $9,979,000 / $9,958,000 / $995,000 as the
    largest capital projects when the real top three are $1,841,855,000 /
    $1,676,169,000 / $1,077,436,000.

    Two orders of magnitude wrong, in a list whose whole purpose is "the
    biggest", and entirely plausible on the page.
    """
    sql = _capital_sql()
    order = re.search(r'ORDER BY(.*?)(?:LIMIT|$)', sql, re.S | re.I)
    assert order, f'no ORDER BY in the capital query: {sql}'
    clause = order.group(1)
    assert 'plannedcommit_total' in clause, 'the brief must order by the budget'
    assert '::numeric' in clause or 'cast(' in clause.lower(), (
        'the budget column is TEXT — ordering it without a numeric cast sorts '
        f'"995000" above "9979000": {clause.strip()!r}')
