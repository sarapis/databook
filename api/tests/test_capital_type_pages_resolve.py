"""Every project-type surface slugs through the ONE owner, and the index gates.

⚠⚠ 18 REAL TYPE PAGES WERE UNREACHABLE, AND I FIRST DIAGNOSED IT WRONG. All four
type endpoints compared `LOWER(REGEXP_REPLACE(REPLACE(name, ' ', '-'), '-+',
'-', 'g'))` — a THIRD slug spelling that replaces SPACES ONLY, so an apostrophe,
ampersand, comma or slash survives into a slug no URL can carry:

    Department of Parks & Recreation         -> department-of-parks-&-recreation
    Children's Services                      -> children's-services
    DEP - Water Mains, Sources and Treatment -> …water-mains,-sources-and-treatment

Measured over all 236 distinct `Project Type Description` values: **18 slug
differently from `modules/capitalslug`, every one carries usable rows, and 212
usable rows were stranded.** `Department of Parks & Recreation` alone holds 76.

⚠ I had recorded these as casualties of the two defective `capitalstrategy`
vintages. **That was wrong** — the tell was that Parks is not a marginal
programme. Counting the rows rather than reasoning from a known nearby defect is
what separated them.

⭐ AND IT RECONCILES, which is why the split is trustworthy: a sweep of all 202
published names found **26** returning 404; 18 slug-defect + 8 genuinely-empty
= 26, and the 8 match the "228 types survive, 8 correctly 404" figure measured
independently on 2026-09-08. After the fix the same sweep reads **194 of 202**,
and the rendered index shows 531 rows — **523 links, every one 200, and exactly
those 8 rendered as TEXT**.

⚠ THE FOUR SURFACES MATTER TOGETHER. Fixing only the page endpoint would have
made 18 pages reachable and EMPTY: the budget-lines table, the commitments chart
and the provenance count each key on the same slug. Parks now reads 1,468
budget lines / 4,442 commitments / 76 records — that last figure matching the
usable-row count measured in the database, which is the cross-check that the
fourth fix is right.
"""
import ast
import importlib.util
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROOT = os.path.realpath(os.path.join(API, '..'))
MAIN = os.path.join(API, 'main.py')
MODULE = os.path.join(API, 'modules', 'capitalslug.py')
CTRL = os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Projects.php')
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'prjTypesA.blade.php')

# The four surfaces a type page depends on. All four key on the same slug.
TYPE_ENDPOINTS = ('get_pstats_categories_by_type', 'get_budglines_by_prjtype',
                  'get_commitments_by_prjtype', 'get_pstats_records_no_by_prjtype_real')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _fn_code(name):
    """One function's statements with the DOCSTRING dropped.

    ⚠ `ast.unparse` includes the docstring, and every one of these now explains
    the banned spelling by quoting it — own-prose firing, guaranteed, without
    this.
    """
    tree = ast.parse(_read(MAIN))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == name), None)
    assert fn is not None, 'type endpoint %s is gone' % name
    body = list(fn.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return '\n'.join(ast.unparse(st) for st in body)


def _fn_literals(name):
    """Every STRING LITERAL in one function, docstring excluded.

    ⚠⚠ THIS EXISTS BECAUSE `ast.unparse` ESCAPED THE QUOTES AND THE GUARD WENT
    BLIND. The SQL is a triple-quoted string containing both `"` and `'`, so
    unparse renders the inner single quotes as `\'` — and a scan for
    `REPLACE(col, ' ', '-')` over the unparsed source finds
    `REPLACE(col, \' \', \'-\')` and matches nothing. The mutation LANDED and
    the guard stayed green, which reads exactly like a useless guard.
    A cousin of the documented "unparse normalises double quotes to single" trap,
    and the same remedy: read the literals, whose `.value` is the real text.
    """
    tree = ast.parse(_read(MAIN))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == name), None)
    assert fn is not None, 'type endpoint %s is gone' % name
    body = list(fn.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    out = []
    for st in body:
        for node in ast.walk(st):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                out.append(node.value)
    assert out, 'no string literals read out of %s' % name
    return '\n'.join(out)


def _php_code(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'^[ \t]*(?://|#).*$', '', src, flags=re.M)


def _blade_code(src):
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'^[ \t]*//.*$', '', src, flags=re.M)


def test_no_type_endpoint_slugs_with_the_spaces_only_rule():
    """⚠ Reads each function's CODE, never the file: the spaces-only expression
    is quoted in three docstrings and four comments explaining why it is banned.
    """
    banned = re.compile(r"REPLACE\(\s*[^,]+,\s*' '\s*,\s*'-'\s*\)")
    for name in TYPE_ENDPOINTS:
        code = _fn_literals(name)
        assert not banned.search(code), (
            '%s slugs with the spaces-only rule again — that spelling leaves an '
            "apostrophe, ampersand, comma or slash in the slug, and it stranded "
            '18 real type pages with 212 usable rows' % name)


def test_every_type_endpoint_slugs_through_the_one_owner():
    """⚠ The mirror direction — the one that catches a THIRD spelling nobody has
    written yet. Banning the old expression does not require using the owner."""
    for name in TYPE_ENDPOINTS:
        code = _fn_code(name)
        assert 'capitalslug.SLUG_SQL' in code, (
            '%s no longer builds its slug from modules/capitalslug' % name)
        assert 'capitalslug.slug(' in code, (
            "%s does not normalise the CALLER's value; normalising one side only "
            'is the documented way to return nothing while looking careful' % name)


def test_the_served_slug_set_uses_the_pages_own_predicate():
    """⭐ The gate must measure the same thing it gates. The page 404s exactly
    when `"Ten-Year Total"` is absent, so the served set must test that and
    nothing else — a second rule here is the suffix-list defect."""
    code = _fn_code('get_capital_project_type_slugs')
    assert 'Ten-Year Total' in code, (
        'the served slug set no longer uses the money guard the page 404s on')
    assert 'capitalslug.SLUG_SQL' in code, (
        'the served slug set re-derives the slug instead of using the owner')
    # and it must serve the key the caller reads
    assert re.search(r"'slugs'|\"slugs\"", code), (
        'the endpoint no longer serves a `slugs` key')


def test_the_types_index_gates_its_link_and_degrades_open():
    """⚠⚠ DEGRADING OPEN IS THE LOAD-BEARING HALF. If the served set comes back
    empty because the lookup failed, treating that as "nothing resolves" would
    strip EVERY link from the page — a failure that looks exactly like a working
    gate. With no answer, behave as before."""
    php = _php_code(_read(CTRL))
    i = php.index('function prjTypes_a(')
    j = php.index('function ', i + 20)
    body = php[i:j]
    assert '/get/capitalprojects/type-slugs' in body, (
        'the types index no longer fetches the served slug set, so it is back to '
        'linking pages that cannot exist')
    assert re.search(r'empty\(\s*\$typeSlugs\s*\)', body), (
        'the gate does not degrade open on an empty served set — a failed '
        'lookup would strip every link on the page')
    assert re.search(r"'link'\s*=>\s*\$ok\s*\?", body), (
        'the link is no longer conditional on the served set')


def test_an_ungated_type_renders_as_text_not_as_a_dropped_row():
    """⚠ The type is REAL and its figures on this page are real; what is missing
    is a page of its own. Hiding the row would delete a published programme from
    an index that claims to list them."""
    view = _blade_code(_read(VIEW))
    # ⚠⚠ THE FALSE BRANCH ONLY. The first draft captured the whole ternary, and
    # the TRUE branch also renders `r['ptype_name']` — so the guard passed
    # against a mutation that replaced the false branch with `''`. "Anchored on
    # the wrong occurrence", which this repo has now paid for a third time.
    m = re.search(r"return r\['link'\]\s*\?(?P<yes>.*?):(?P<no>[^\n]*)",
                  view, flags=re.S)
    assert m, 'the types index no longer branches on `link`'
    branch = m.group('no')
    assert "r['ptype_name']" in branch, (
        'the ungated branch does not render the type NAME — a row that cannot '
        'link must still say what it is')


def test_the_python_and_sql_halves_of_the_slug_rule_still_agree():
    """⚠ A guard that re-types the rule measures a different system, so the
    character class is parsed back OUT of `SLUG_SQL` and applied."""
    spec = importlib.util.spec_from_file_location('_cs_under_test', MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    m = re.search(r"regexp_replace\([^,]+,\s*'([^']+)'\s*,\s*'([^']*)'", mod.SLUG_SQL)
    assert m, 'could not parse the pattern out of SLUG_SQL: %r' % mod.SLUG_SQL
    pattern, repl = m.group(1), m.group(2)
    for value in ("Children's Services", 'Department of Parks & Recreation',
                  'Reconstruction/Renovation of Court Facilities',
                  'Water Mains, Sources and Treatment'):
        from_sql = re.sub(pattern, repl, value.lower()).strip(repl)
        assert mod.slug(value) == from_sql, (
            'the python half and the SQL half disagree on %r: %r vs %r'
            % (value, mod.slug(value), from_sql))
