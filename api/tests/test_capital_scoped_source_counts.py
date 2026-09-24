"""The per-scope record counts behind the two SCOPED provenance panels.

⚠⚠ THE DEFECT THIS REMOVES IS A WRONG ZERO, NOT A MISSING FEATURE.
`/get/pstats-records_no-by_{category,budgetline}` returned **`0`** for every
table it had no rule for, and the shared provenance component treats three
outcomes as three different claims:

    a number   the scoped count
    0          this dataset holds nothing for this scope — a FINDING
    —          we could not ask, and must not imply 0

So widening either panel to the spine's own current sources published a
confident, plausible zero about datasets the page's table draws hundreds of
projects from. Both panels were therefore left NARROW with the reason recorded
at each call site — the omission being the lesser defect — and that is the state
`modules/capitalsources` ends.

⚠⚠ AND FIVE OF THE ELEVEN COLUMN MAPPINGS BETWEEN THOSE TWO ENDPOINTS NAMED A
COLUMN THAT DOES NOT EXIST. Every one was a live 500, measured 2026-09-10
against `information_schema`:

    by_budgetline   capprojectsbudgetsandschedule  "BUDGET_LINE" -> "Budget Line"
                    capprojectsbudgetandspend      "BUDGET_LINE" -> absent
                    capprojectsbudgetspendhistory  "BUDGET_LINE" -> absent
                    capprojectsschedulehistory     "BUDGET_LINE" -> absent
    by_category     capitalbudget    "Ten-Year Plan Category"    -> absent

22 of 22 table×dimension combinations answer 200 now; 5 were 500.
"""
import ast
import importlib.util
import os
import re
import sys

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
MAIN = os.path.join(ROOT, 'api', 'main.py')
ROUTER = os.path.join(ROOT, 'api', 'routers', 'capital.py')
CTRL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Projects.php')
COMPONENT = os.path.join(ROOT, 'app', 'resources', 'views', 'components', 'db',
                         'data-provenance.blade.php')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _sources():
    """`capitalsources`, with its two bare-name imports satisfied.

    ⚠⚠ BY PATH, NEVER `from modules import capitalsources`. `conftest.py`
    replaces the whole `modules` package with a MagicMock, so the import yields
    a mock whose every attribute satisfies almost any assertion — and this
    file's assertions are about STRINGS and dict shapes, so a mock either raises
    `TypeError: 'in <string>' requires string as left operand` or, worse, passes
    silently. It bit on the first run of the budget-line guard this same
    session, which is why the load is ASSERTED below."""
    # ⚠⚠ `sys.modules` IS RESTORED, AND LEAVING IT DIRTY COST A WHOLE SUITE RUN.
    # `capitalsources` does `import budgetline` / `import capitalslug` by bare
    # name, so those have to be in `sys.modules` while it executes. An earlier
    # draft installed them and LEFT them there — which is global state for every
    # test that runs after this file, and `conftest.py` deliberately replaces the
    # `modules` package with a MagicMock. The suite went from ~200s to not
    # finishing, because code that had been mocked started doing real work.
    # Same family as the mock trap itself, in the opposite direction: a test that
    # changes what LATER tests measure.
    saved = {k: sys.modules.get(k) for k in ('budgetline', 'capitalslug')}
    try:
        for dep in ('budgetline', 'capitalslug'):
            path = os.path.join(ROOT, 'api', 'modules', dep + '.py')
            spec = importlib.util.spec_from_file_location(dep, path)
            dep_mod = importlib.util.module_from_spec(spec)
            sys.modules[dep] = dep_mod
            spec.loader.exec_module(dep_mod)
        path = os.path.join(ROOT, 'api', 'modules', 'capitalsources.py')
        spec = importlib.util.spec_from_file_location('_capitalsources_under_test',
                                                      path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    assert isinstance(mod.DIMENSIONS, tuple), 'capitalsources did not load for real'
    return mod


def _py_function_code(path, name):
    fn = next(n for n in ast.walk(ast.parse(_read(path)))
              if isinstance(n, (ast.AsyncFunctionDef, ast.FunctionDef))
              and n.name == name)
    stmts = list(fn.body)
    if (stmts and isinstance(stmts[0], ast.Expr)
            and isinstance(stmts[0].value, ast.Constant)
            and isinstance(stmts[0].value.value, str)):
        stmts = stmts[1:]
    return '\n'.join(ast.unparse(st) for st in stmts)


def _php_code_only(text):
    """⚠ Comments stripped. Every assertion below searches for a string this
    session's own comments quote — `0`, `capitalprojectslist`, `crosswalk`,
    `BUDGET_LINE`. Own-prose firings in this repo stand at 26."""
    text = re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'^\s*//.*$', '', text, flags=re.M)


def test_a_table_that_cannot_be_scoped_answers_null_and_never_zero():
    """⚠⚠ THE WHOLE DEFECT, IN ONE ASSERTION. `0` and `None` are different
    claims: one says this dataset holds no record for this scope — a finding —
    and the other says it was never asked. The code this replaces returned 0 for
    every unmapped table, which is why both panels had to stay narrow.
    """
    cs = _sources()
    # A table with no rule at all, and a real table asked for a dimension it
    # does not carry.
    for table, dim in (('nosuchtable', 'budget_line'),
                       ('capitalstrategy', 'budget_line'),
                       ('capitalbudget', 'ten_year_category')):
        sql, via = cs.count_sql(table, dim)
        assert sql is None and via is None, (
            '%s should not be scopable by %s; returning SQL here means a figure '
            'gets published for a dimension the table does not carry'
            % (table, dim))

    body = _py_function_code(MAIN, '_unscopable')
    assert "'res': None" in body, (
        "the unscopable answer no longer serves `res: None` — if it serves 0, "
        "the provenance component reads it as 'this dataset holds nothing for "
        "this scope', which is a claim we have not measured")
    assert not re.search(r"'res':\s*0\b", body), (
        'the unscopable answer serves a literal 0 again')

    # And both endpoints must route their unscopable case through it, rather
    # than each inventing an answer — which is how the two col_maps drifted.
    for fn in ('get_pstats_records_no_by_category_real',
               'get_pstats_records_no_by_budgetline_real'):
        code = _py_function_code(MAIN, fn)
        assert '_scoped_source_count(' in code, (
            '%s no longer delegates to the one owner' % fn)
        assert 'col_map' not in code, (
            '%s has its own table->column map again; there were two, and five '
            'of the eleven entries between them named a column that does not '
            'exist' % fn)


def test_every_declared_column_exists_and_is_spelled_as_the_publisher_spells_it():
    """⚠⚠ FIVE OF ELEVEN NAMED A COLUMN THAT DOES NOT EXIST, and the spellings
    are the point: `capprojectsbudgetsandschedule` has `Budget Line` and
    `Ten Year Plan Category` — no underscores, and NO HYPHEN in "Ten Year",
    unlike `capitalstrategy`'s `Ten-Year Plan Category`. Two publishers, two
    spellings of one phrase, and a plausible guess 500s.

    ⚠ This cannot check `information_schema` without a database, so it pins the
    spellings that WERE measured against it. A new entry has to be measured the
    same way — the dropped alternative is a guard that only checks the map is
    non-empty, which is what let the wrong names sit there.
    """
    cs = _sources()
    measured = {
        ('capprojectsbudgetsandschedule', 'budget_line'): '"Budget Line"',
        ('capprojectsbudgetsandschedule', 'ten_year_category'): '"Ten Year Plan Category"',
        ('capitalstrategy', 'ten_year_category'): '"Ten-Year Plan Category"',
        ('capitalbudget', 'budget_line'): '"Budget Line"',
        ('capitalcommitmentplan', 'budget_line'): '"Budget Line"',
        ('capitalprojectscommitments', 'budget_line'): 'budgetline',
        ('capitalprojectsdollarscomp', 'budget_line'): '"BUDGET_LINE"',
        ('capitalprojectsdollarscomp', 'ten_year_category'): '"TYP_CATEGORY_NAME"',
    }
    for (table, dim), col in measured.items():
        declared = (cs.SOURCES[table].get('own') or {}).get(dim)
        assert declared == 't.' + col, (
            '%s.%s is declared as %r; measured against information_schema it is '
            '%r' % (table, dim, declared, 't.' + col))

    # ⚠ And the three tables that carry NO budget-line column must not have one
    # declared — they were mapped to `"BUDGET_LINE"` and 500'd.
    for table in ('capprojectsbudgetandspend', 'capprojectsbudgetspendhistory',
                  'capprojectsschedulehistory'):
        assert table not in cs.SOURCES or not (
            cs.SOURCES[table].get('own') or {}).get('budget_line'), (
            '%s is declared as carrying a budget-line column; measured, it has '
            'none, and naming one 500s the endpoint' % table)


def test_the_slug_rule_has_one_owner_and_both_consumers_use_it():
    """⚠⚠ COMPARING RESOLVED NAMES INSTEAD OF SLUGS WAS TRIED AND IS WRONG —
    measured, not argued. Of the 138 spine category names, `capitalstrategy`
    spells only **5** the same way and **124** match only after case-folding
    (`ROUTINE RECONSTRUCTION` against `Routine Reconstruction`). A name
    comparison therefore returned **0** on that source for 124 of 138 category
    pages — the wrong zero this work exists to remove, nearly reintroduced by
    the fix. The Dashboard alone would have been safe (0 case-only pairs), which
    is why measuring ONE source is not measuring the rule.

    ⚠ So the rule moved to `modules/capitalslug` and BOTH consumers import it.
    The router keeps `_slug`/`_SLUG_SQL` bound to it so its own callers and
    guards are unchanged; what is gone is the second copy.
    """
    slug_mod = os.path.join(ROOT, 'api', 'modules', 'capitalslug.py')
    assert os.path.exists(slug_mod), 'the slug rule has no module owner'
    spec = importlib.util.spec_from_file_location('_capitalslug_under_test', slug_mod)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    # The two halves must agree, with the pattern parsed OUT of the SQL.
    got = re.search(r"regexp_replace\(lower\(\{col\}\), '([^']*)', '([^']*)'",
                    m.SLUG_SQL)
    assert got, 'SLUG_SQL is no longer a readable regexp_replace: %r' % m.SLUG_SQL
    pattern, repl = got.group(1), got.group(2)
    for value in ('Water Mains, Sources and Treatment', 'ROUTINE RECONSTRUCTION',
                  'Dept. of Information Technology & Telecomm',
                  '  Parks and Recreation  ', 'Large, Major and Regional Park'):
        sql_side = re.sub(pattern, repl, value.lower()).strip('-')
        assert sql_side == m.slug(value), (
            'the SQL and Python slug rules disagree on %r: %r vs %r'
            % (value, sql_side, m.slug(value)))

    # ⚠ The router must BIND to the module, not redefine the rule.
    router = _read(ROUTER)
    assert 'capitalslug.SLUG_SQL' in router and 'capitalslug.slug' in router, (
        'the router no longer takes the slug rule from its owner')
    assert not re.search(r"_SLUG_SQL\s*=\s*\"trim", router), (
        'the router declares its own copy of the slug SQL again — two spellings '
        'of this rule is how /projects/categories/{slug} came to be unable to '
        'match its own URLs')

    # ⚠ And `capitalsources` must slug BOTH sides through the same owner.
    cs = _sources()
    own_sql, _ = cs.count_sql('capitalstrategy', 'ten_year_category')
    xw_sql, via = cs.count_sql('capitalprojectslist', 'ten_year_category')
    assert via == 'crosswalk'
    for label, sql in (('own-column', own_sql), ('crosswalk', xw_sql)):
        assert "regexp_replace(lower(" in sql, (
            'the %s category path does not slug its side of the comparison: %s'
            % (label, sql))


def test_the_two_counting_methods_are_served_so_they_cannot_be_mixed():
    """⚠⚠ THEY ARE NOT INTERCHANGEABLE AND THE GAP IS LARGE. Measured on
    `EP 0007`: `capitalprojectscommitments` holds **82** rows naming that budget
    line and **568** rows belonging to projects that touch it, because a project
    is funded through several lines. The panel's own sentence is *"counting the
    records in each budget line"*, so a table's OWN column wins wherever it has
    one, and the crosswalk is used only where it cannot be asked otherwise.

    ⚠ Serving `via` is what stops two rows in one panel being read as one kind
    of figure, and the component badges the crosswalked ones.
    """
    cs = _sources()
    # Own column wins where the table has one.
    _, via = cs.count_sql('capitalprojectscommitments', 'budget_line')
    assert via == 'own', (
        'the commitments table has its own budget-line column and must be '
        'counted on it; the crosswalk gives 568 where 82 name the line')
    # Crosswalk only where there is none.
    _, via = cs.count_sql('capitalprojectslist', 'budget_line')
    assert via == 'crosswalk', (
        'capitalprojectslist carries no budget-line column, so the crosswalk is '
        'the only way to answer — and it must say so')
    # ⚠ `typecategory` is the ASSET class, not the Ten-Year taxonomy: two things
    # called category is the ambiguity retired on the stats endpoint.
    _, via = cs.count_sql('capitalprojectslist', 'ten_year_category')
    assert via == 'crosswalk', (
        "capitalprojectslist.typecategory is CPDB's 3-value ASSET class and must "
        'not be used as the Ten-Year category')

    body = _py_function_code(MAIN, '_scoped_source_count')
    assert "'via': via" in body, (
        'the endpoint no longer serves which method it used, so an own-column '
        'count and a crosswalked one become indistinguishable')

    view = _php_code_only(_read(COMPONENT))
    assert "d.via === 'crosswalk'" in view, (
        'the panel no longer marks a crosswalked count')
    # ⚠⚠ ANCHORED ON THE CONDITIONAL, and it took two tries to get here — both
    # failures being ones this repo has already paid for:
    #   `'d.retired' in view`      stayed GREEN against `if (d.retiredX)`, because
    #                              the mutated name CONTAINS the searched name.
    #                              Third prefix-match instance this session.
    #   `re.search(r'\bd\.retired\b')` ALSO stayed green, because `d.retired`
    #                              appears a second time inside the badge's
    #                              `title` string, which the mutation never
    #                              touched — "a guard anchored on the wrong
    #                              occurrence".
    # The property is that the BRANCH tests it, so that is what is asserted.
    assert re.search(r'if\s*\(\s*d\.retired\s*\)', view), (
        'the panel no longer labels a retired-series figure — the 2023 series '
        "sat at 2,671 beside four current sources with a BLANK 'Last Updated'")


def test_the_retirement_fact_has_one_owner_and_the_two_declarations_agree():
    """⚠ The same fact in two shapes must at least be checked. `capitalsources`
    declares a source TABLE's retirement so a scoped panel can label it;
    `capital_source_coverage` declares a PUBLICATION's for the record-mode
    panel. They are not derivable from one another (one is per table, one per
    publication), so they are pinned against each other here — the repo's own
    answer when a fact cannot have a single home.
    """
    cs = _sources()
    assert cs.retired('capitalprojectsdollarscomp'), (
        'the 2023 series is no longer marked retired, so its figure renders '
        'unlabelled beside current sources')
    assert cs.retired('capitalprojectsmilestones'), (
        'the 2023 milestones series is no longer marked retired')
    assert cs.retired('capitalprojectslist') is None, (
        'the current plan is marked retired, which would label a live figure '
        'as a 2023 statement')

    # ⚠ Read the record-mode rows out of the router and compare. A row naming
    # exactly one table we know about must agree with us about it.
    src = _read(ROUTER)
    rows = re.findall(r'"tables":\s*\[([^\]]*)\][^}]*?"retired":\s*(True|False)', src)
    assert len(rows) >= 5, (
        'the record-mode coverage rows are no longer readable here (%d found); '
        'this guard cannot compare what it cannot parse' % len(rows))
    checked = 0
    for tables, flag in rows:
        names = [t.strip().strip('"\'') for t in tables.split(',') if t.strip()]
        if len(names) != 1 or names[0] not in cs.SOURCES:
            continue
        checked += 1
        assert bool(cs.retired(names[0])) == (flag == 'True'), (
            'the two retirement declarations disagree about %s: '
            'capitalsources says %r, the record-mode row says %s'
            % (names[0], cs.retired(names[0]), flag))
    assert checked >= 1, (
        'no record-mode row names a table capitalsources knows, so this '
        'comparison checked nothing — the vacuous-pass failure this repo has '
        'paid for three times')


def test_both_panels_are_widened_to_the_spines_own_sources():
    """⚠ The fix has to reach a PAGE. A scoped count nothing asks for is the
    documented "a new module with a test and no consumer" defect — three Phase 1
    deliverables in this section were built and wired into nothing.
    """
    ctrl = _php_code_only(_read(CTRL))

    def _dslist(method):
        # ⚠⚠ SCOPED TO THE METHOD, NOT FORWARD FROM THE URL. The first form
        # anchored on `by_category/tblname` and searched forward for
        # `stats_data_sources(` — but `datasets` is passed BEFORE `tblStatsUrl`
        # in each of these methods, so it read the NEXT method's array and
        # failed on correct code. "Scope a guard to the statement", again.
        i = ctrl.index('function %s(' % method)
        end = ctrl.index('public function ', i + 10)
        assert 'stats_data_sources(' in ctrl[i:end], (
            '%s no longer builds a provenance dataset list' % method)
        j = ctrl.index('stats_data_sources(', i)
        assert j < end, '%s: the dataset list moved out of the method' % method
        k = ctrl.index('[', j)
        depth, n = 0, k
        while n < len(ctrl):
            if ctrl[n] == '[':
                depth += 1
            elif ctrl[n] == ']':
                depth -= 1
                if depth == 0:
                    break
            n += 1
        return ctrl[k:n + 1]

    cat = _dslist('category_a')
    bl = _dslist('budgetLine_a')
    for label, arr, want in (
            ('category', cat, ('capitalprojectslist', 'capitalprojectscommitments',
                               'capprojectsbudgetsandschedule')),
            ('budget line', bl, ('capitalprojectslist',
                                 'capprojectsbudgetsandschedule'))):
        for t in want:
            assert "'%s'" % t in arr, (
                "the %s panel does not name `%s`, so the scoped count it can "
                'now answer has no consumer' % (label, t))
