"""Guards for program grouping — task `2eba1fce` (b), shape B.

⚠⚠ THE PROPERTY EVERYTHING ELSE RESTS ON: only `tier = 'curated'` renders.
A program asserts that several contracts are one thing the City is doing.
The contract page's co-termination block, twenty inches below it, explicitly
refuses to make that claim from the same evidence ("a shared end date is not
evidence that they are"). So an unreviewed grouping must not be able to reach a
page by omission — #146's rule, made structural for a third time.

⚠ MEASURED CONTEXT for the numbers asserted below (prod, 2026-08-27):
  * the PASSPort program is 11 contracts / 9 vendors / 2 agencies /
    $67,288,364, and the union of the two signals recovers exactly that;
  * the title token finds 10 of the 11 and misses the LARGEST — Ivalua's
    $37.9M platform, whose title is `Inc Alias/DBA: Ivalua Inc Renewal #1`;
  * co-termination finds that one and cannot find the other 6 that end on
    06/30, the boundary this repo excludes;
  * 1 of the 11 is `tech_relevant = false`, which is why membership is not
    tech-gated.
"""
import ast
import io
import os
import sys

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
API = os.path.join(ROOT, 'api')
BUILDER = os.path.join(API, 'build_program_groups.py')
SEED = os.path.join(API, 'seed', 'program_curated.csv')
OCE = os.path.join(API, 'routers', 'oce.py')
CTRL = os.path.join(ROOT, 'app/app/Http/Controllers/ProcurementController.php')
VIEW = os.path.join(ROOT, 'app/resources/views/procurement/contract_profile.blade.php')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _sql_units(node):
    """Every SQL string in `node`, ONE ENTRY PER QUERY.

    ⚠ An f-string is a `JoinedStr` whose constant pieces are SPLIT at each
    `{...}`, so walking for `ast.Constant` hands back fragments: in the member
    lookup, `DISTINCT ON (c.contract_id)` and `JOIN contracts` land in different
    pieces. Asserting both against one fragment fails on correct code (it did),
    and asserting them against the concatenation of ALL literals in the function
    would pass even when they belong to two different queries — the
    query-wide-assertion defect #301 already paid for. So each JoinedStr is
    reassembled as one unit, and plain Constants are units of their own.
    """
    units, seen = [], set()
    for n in ast.walk(node):
        if isinstance(n, ast.JoinedStr):
            seen.add(id(n))
            units.append(''.join(
                v.value for v in n.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)))
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            if not any(n is v for u in ast.walk(node)
                       if isinstance(u, ast.JoinedStr) and id(u) in seen
                       for v in u.values):
                units.append(n.value)
    return [u for u in units if u.strip()]


def _load_builder():
    """Load the builder BY PATH.

    ⚠⚠ `conftest.py` replaces the whole `modules` package with a MagicMock via
    `sys.modules.setdefault`, so a plain import here would give the builder a
    mock `contractkind` whose `is_master` returns a truthy MagicMock — making
    EVERY contract a master and every committed total zero, silently. Load the
    real module by path and assert it loaded.
    """
    import importlib.util
    ck_spec = importlib.util.spec_from_file_location(
        'ck_real', os.path.join(API, 'modules', 'contractkind.py'))
    ck = importlib.util.module_from_spec(ck_spec)
    ck_spec.loader.exec_module(ck)
    assert ck.is_master('MMA1-858-20268803269') is True, \
        'the real contractkind did not load; a mock would pass almost anything'
    assert ck.is_master('CT1-002-20228801501') is False

    spec = importlib.util.spec_from_file_location('bpg_real', BUILDER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['bpg_real'] = mod
    mod.contractkind = ck                      # inject the REAL module
    spec.loader.exec_module(mod)
    mod.contractkind = ck                      # and again, past any re-import
    return mod


# The worked example, at the grain the builder sees (one row per contract).
PASSPORT_ROWS = [
    {'contract_id': 'CT1-002-20228801501', 'ctr_id': '4509900', 'val': 37908500.0,
     'vendor_name': 'Ivalua Inc', 'agency': 'OFFICE OF CONTRACT SERVICES',
     'end_date': '04/27/2027', 'contract_title': 'Inc Alias/DBA: Ivalua Inc Renewal #1'},
    {'contract_id': 'CT1-002-20248805109', 'ctr_id': '5068301', 'val': 24006800.0,
     'vendor_name': 'ACCENTURE LLP', 'agency': 'OFFICE OF CONTRACT SERVICES',
     'end_date': '04/27/2027', 'contract_title': '00224N0001-PASSPort Maintenance Services'},
    {'contract_id': 'CT1-850-20228801595', 'ctr_id': '5100001', 'val': 1500000.0,
     'vendor_name': 'SVAM INTERNATIONAL INC', 'agency': 'DEPARTMENT OF DESIGN AND CONSTRUCTION',
     'end_date': '12/31/2025', 'contract_title': 'MWBE PassPort Integration'},
    {'contract_id': 'CT1-002-20268801915', 'ctr_id': '5100002', 'val': 498500.0,
     'vendor_name': 'IN OUR SHOES LLC', 'agency': 'OFFICE OF CONTRACT SERVICES',
     'end_date': '06/30/2026',
     'contract_title': 'DISCRETIONARY SUPPORT SERVICES FOR THE ADOPTION OF PASSPORT'},
    # A contract that must NOT join: no token, different end date.
    {'contract_id': 'CT1-002-99999999999', 'ctr_id': '5100003', 'val': 9000000.0,
     'vendor_name': 'SOMEONE ELSE LLC', 'agency': 'OFFICE OF CONTRACT SERVICES',
     'end_date': '01/02/2030', 'contract_title': 'Janitorial services'},
]


# ---------------------------------------------------------------------------
# The seed and the resolver
# ---------------------------------------------------------------------------

def test_the_seed_parses_as_real_quoted_csv_with_prose_notes():
    """⚠ Notes here are prose and contain commas. Splitting on commas mangled
    47 of 212 rows in the NYCHA review (#155), so the loader must use csv."""
    bpg = _load_builder()
    progs = bpg.load_curated(SEED)
    assert 'passport' in progs, 'the PASSPort program is gone from the seed'
    p = progs['passport']
    assert p['tokens'] == ['passport']
    assert 'CT1-002-20228801501' in p['contracts'], \
        "Ivalua's platform licence must be named explicitly — no title search finds it"
    note = p['notes'].get('CT1-002-20228801501', '')
    assert ',' in note and 'Ivalua' in note, \
        'the note was truncated at a comma, which is the #155 defect'


def test_the_token_expands_and_the_explicit_contract_covers_what_it_misses():
    """⚠⚠ THE WHOLE REASON BOTH RULES EXIST. The token finds 10 of 11 members
    at zero false positives, and misses the LARGEST — Ivalua's $37.9M platform,
    titled `Inc Alias/DBA: Ivalua Inc Renewal #1`. Either rule alone loses the
    program: without the token it is one contract, without the explicit
    contract it is missing 56% of the money."""
    bpg = _load_builder()
    progs = bpg.load_curated(SEED)
    members = bpg.resolve_members(progs, PASSPORT_ROWS)['passport']

    assert 'CT1-002-20228801501' in members, 'the platform licence was lost'
    assert members['CT1-002-20228801501'] == 'curated', \
        'the platform is found ONLY by being named; no token matches its title'
    assert members['CT1-002-20248805109'] == 'token'
    assert 'CT1-002-99999999999' not in members, \
        'an unrelated contract at the same agency joined the program'

    # The non-tech member. A tech-gated membership pass drops it.
    assert 'CT1-002-20268801915' in members, (
        'IN OUR SHOES LLC is classified tech_relevant=false and is still a real '
        'member — adoption support for the system. Membership must not be '
        'tech-gated; only the discovery worksheet is.')


def test_an_exclusion_wins_over_a_token_match():
    """⚠ A token rule is broad by construction, so the seed must be able to say
    'not that one' — and a rejection a rebuild can overturn is not a rejection
    (#155). Applied LAST, so ordering cannot defeat it."""
    bpg = _load_builder()
    progs = {'passport': {'name': 'PASSPort', 'contracts': [], 'notes': {},
                          'tokens': ['passport'],
                          'excludes': ['CT1-002-20248805109']}}
    members = bpg.resolve_members(progs, PASSPORT_ROWS)['passport']
    assert 'CT1-002-20248805109' not in members, \
        'an excluded contract survived a token match'
    assert 'CT1-850-20228801595' in members, 'the exclusion removed too much'


def test_committed_money_and_master_ceilings_are_never_added():
    """⚠⚠ #261, #294 AND #301 EACH FOUND THIS DEFECT. A program total is
    exactly the kind of figure it corrupts: a master's amount is headroom
    agencies buy against, not money spent."""
    bpg = _load_builder()
    rows = PASSPORT_ROWS + [
        {'contract_id': 'MMA1-858-20268803269', 'ctr_id': '5100004',
         'val': 50000000.0, 'vendor_name': 'BIG VEHICLE INC',
         'agency': 'OFFICE OF CONTRACT SERVICES', 'end_date': '04/27/2027',
         'contract_title': 'PASSPort citywide vehicle'},
    ]
    progs = bpg.load_curated(SEED)
    members = bpg.resolve_members(progs, rows)['passport']
    s = bpg.summarize(members, rows)

    assert s['ceiling'] == pytest.approx(50000000.0), \
        'the master agreement was not recognised as a ceiling'
    assert s['value'] == pytest.approx(63913800.0), (
        "the master's $50M ceiling was summed into committed money; "
        f"got {s['value']}")
    assert s['value'] != pytest.approx(s['value'] + s['ceiling'])


def test_the_worked_examples_figures_close():
    """The four seeded members present here total what prod reports for them,
    so a change to the resolver that quietly drops one is visible as money."""
    bpg = _load_builder()
    progs = bpg.load_curated(SEED)
    members = bpg.resolve_members(progs, PASSPORT_ROWS)['passport']
    s = bpg.summarize(members, PASSPORT_ROWS)
    assert s['contracts'] == 4
    assert s['agencies'] == 2, 'the DDC contract is the second agency'
    assert s['value'] == pytest.approx(63913800.0)
    assert s['ceiling'] == 0.0


# ---------------------------------------------------------------------------
# Grain, scope and the noise rules
# ---------------------------------------------------------------------------

def test_the_builder_dedupes_at_contract_grain_never_ctr_id():
    """⚠⚠ #262/#278, third surface. `contracts` holds one row per amendment and
    every amendment carries its own ctr_id, so `DISTINCT ON (ctr_id)` collapses
    nothing. Keying on contract_id ALONE loses the 2,546 rows that have none."""
    src = _read(BUILDER)
    assert "coalesce(contract_id, 'row:' || ctid::text)" in src, \
        'the builder no longer dedupes at contract grain'
    assert 'DISTINCT ON (ctr_id)' not in src, \
        'ctr_id cannot dedupe amendments — each amendment has its own'


def test_both_dedups_break_ties_deterministically():
    """⚠⚠ WITHOUT A FINAL TIEBREAK, `DISTINCT ON` RETURNS A DIFFERENT ANSWER
    BETWEEN RUNS, and both inputs to this feature are affected.

    Measured on prod 2026-08-27: 92 contract_ids have a TIE for the winning
    amendment row (equal current_amount AND award_amount). Of those, **61 tied
    rows disagree on `end_date`** and **86 disagree on `contract_title`** — so
    which end date feeds the co-termination worksheet, and which title a token
    is matched against, were both being decided arbitrarily by Postgres row
    order.

    This is not hypothetical: two runs of the same worksheet minutes apart
    returned 59 and 60 groups, and the scope doc's 2,179 co-termination groups
    re-measured as 2,178. Neither query was wrong; the ordering was unstable.

    ⚠ `ctr_id`, not `ctid` — ctid is a physical row pointer and the extractor
    DROP+RENAMEs `contracts` daily, so it is stable only within a single run.
    """
    ordering = ('coalesce(current_amount, 0) DESC, coalesce(award_amount, 0) DESC,\n'
                '          ctr_id')
    assert ordering in _read(BUILDER), (
        'the builder dedup has no deterministic final tiebreak; 61 contracts '
        'can silently change end_date and 86 can change title between runs')

    tree = ast.parse(_read(OCE))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == '_program_for_contract')
    member_sql = [u for u in _sql_units(fn) if 'JOIN contracts' in u]
    assert len(member_sql) == 1
    assert 'coalesce(c.award_amount, 0) DESC, c.ctr_id' in member_sql[0], (
        'the member query picks which amendment to DISPLAY with no final '
        'tiebreak, so a program row can change its title and end date '
        'between requests')


def test_the_worksheet_keeps_both_noise_rules():
    """⚠ Without them co-termination is almost pure noise: the largest 06/30
    group is 4,721 contracts, and EVERY oversized group lands on that date.

    ⚠ ASSERTS THE EXECUTABLE SQL, NOT THE PROSE. This module's docstring
    explains the 06/30 rule at length, and eight guards in this repo have now
    fired on their own explanation. Read the string literal the function emits.
    """
    tree = ast.parse(_read(BUILDER))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == 'worksheet')
    body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                           and isinstance(fn.body[0].value, ast.Constant)) else fn.body
    sql = ' '.join(
        n.value for n in ast.walk(ast.Module(body=body, type_ignores=[]))
        if isinstance(n, ast.Constant) and isinstance(n.value, str))
    assert sql.strip(), 'the worksheet query has no SQL literal to check'
    assert "NOT LIKE '06/30/%'" in sql, \
        'the fiscal-year-boundary exclusion is gone from the worksheet QUERY'
    assert '_WORKSHEET_MAX_GROUP' in sql or 'BETWEEN 2 AND' in sql, \
        'the group-size cap is no longer applied in the worksheet query'


def test_only_the_worksheet_is_tech_scoped_and_membership_is_not():
    """⚠⚠ A TECH-GATED MEMBERSHIP PASS SILENTLY DROPS A REAL MEMBER, measured:
    `CT1-002-20268801915` (IN OUR SHOES LLC, $498,500, adoption support for
    PASSPort) is `tech_relevant = false`, and gating membership on it takes the
    program from 11 contracts / $67.29M to 10 / $66.79M.

    So `digital_contract_enrichment` may appear in the worksheet query and
    nowhere else in this builder.

    ⚠⚠ THIS GUARD'S FIRST DRAFT SCANNED ONLY FUNCTION BODIES AND MISSED THE
    REAL MUTATION. The membership query lives in `_DEDUP`, a MODULE-LEVEL
    constant, so tech-gating it there was invisible to a per-function walk —
    the guard passed while the defect it exists to catch was live. Caught by
    reintroducing the bug, which is the only reason it was caught at all.
    The scan is now whole-module, minus `worksheet` and minus docstrings.

    ⚠ Docstrings must be excluded or this fires on its own explanation: this
    module's prose names `digital_contract_enrichment` several times, and the
    builder's does too. Ninth own-prose guard trap in this repo.
    """
    tree = ast.parse(_read(BUILDER))

    ws = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == 'worksheet')
    exempt = {id(n) for n in ast.walk(ws)}

    # Every docstring node: the module's, and each function's/class's first
    # statement when it is a bare string.
    for scope in [tree] + [n for n in ast.walk(tree) if isinstance(
            n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]:
        body = getattr(scope, 'body', [])
        if body and isinstance(body[0], ast.Expr) and \
                isinstance(body[0].value, ast.Constant) and \
                isinstance(body[0].value.value, str):
            exempt.add(id(body[0].value))

    offenders = [n.value for n in ast.walk(tree)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str)
                 and id(n) not in exempt
                 and 'digital_contract_enrichment' in n.value]
    assert not offenders, (
        'membership is being tech-gated outside the worksheet — that drops '
        'IN OUR SHOES LLC and $498,500 from the PASSPort program:\n'
        + '\n'.join(o.strip()[:160] for o in offenders))

    ws = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == 'worksheet')
    ws_sql = ' '.join(n.value for n in ast.walk(ws)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str))
    assert 'digital_contract_enrichment' in ws_sql, \
        'the worksheet lost its tech scope, which is what keeps it to 59 groups'


# ---------------------------------------------------------------------------
# The serving seam — only curated renders, and the page actually receives it
# ---------------------------------------------------------------------------

def test_the_endpoint_serves_only_curated_programs():
    """⚠⚠ #146 MADE STRUCTURAL. An unreviewed grouping must not reach a page by
    omission. Both queries in the resolver are scoped, so adding an `auto` row
    to the table cannot publish it.

    ⚠ Reads the STRING LITERALS the function emits, not its text — this file's
    own docstrings quote `tier = 'curated'` repeatedly.
    """
    tree = ast.parse(_read(OCE))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == '_program_for_contract')
    body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                           and isinstance(fn.body[0].value, ast.Constant)) else fn.body
    sqls = [n.value for n in ast.walk(ast.Module(body=body, type_ignores=[]))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and 'contract_program' in n.value]
    assert len(sqls) == 2, (
        f'expected both program queries to read contract_program, found {len(sqls)}')
    for sql in sqls:
        assert "tier = 'curated'" in sql, (
            'a program query is not scoped to curated rows; an unreviewed '
            'grouping could render: ' + sql)


def test_the_member_lookup_dedupes_the_contracts_side():
    """⚠ `contract_program` is keyed on contract_id so it cannot multiply rows,
    but `contracts` still holds one row per amendment — the join needs the
    dedup or a contract with 5 amendments appears 5 times in its own program
    (#278's phantom-rows defect, at a new surface)."""
    tree = ast.parse(_read(OCE))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.AsyncFunctionDef) and n.name == '_program_for_contract')
    # ⚠ Per QUERY, not per fragment and not per function — see _sql_units.
    joins = [u for u in _sql_units(fn) if 'JOIN contracts' in u]
    assert len(joins) == 1, \
        f'expected exactly one query joining contracts, found {len(joins)}'
    assert 'DISTINCT ON (c.contract_id)' in joins[0], \
        ('the query that joins contracts does not dedupe amendments; a contract '
         'with 5 amendments would appear 5 times in its own program')


def test_the_controller_passes_the_program_to_the_view():
    """⚠⚠ THE #247 DEFECT. This controller NAMES each key, so a new payload key
    silently never arrives and `?? null` degrades politely — the Overview
    rendered without its composition bar for exactly this reason, with every
    unit guard green."""
    ctrl = _read(CTRL)
    assert "'program' => $data['program']" in ctrl, \
        'the controller does not pass program; the panel renders nothing'
    assert '$program' in _read(VIEW), 'the view no longer reads the key'


def test_the_endpoint_serves_the_key():
    assert '"program": await _program_for_contract(' in _read(OCE), \
        'the contract endpoint no longer serves the program'


def test_the_page_states_that_membership_is_reviewed_by_hand():
    """⚠ THE STANDING RULE, and this panel makes a STRONGER claim than the
    co-termination block below it, whose own copy refuses to infer a program
    from a shared end date. It must say where its membership comes from."""
    view = _read(VIEW)
    assert 'reviewed by hand' in view, \
        'the panel no longer says its membership is curated'
    assert 'not inferred from a shared end date' in view, \
        'the panel no longer distinguishes itself from the co-termination block'


def test_the_panel_renders_every_figure_from_the_payload():
    """⚠ No typed counts or percentages. A documented rollup is a snapshot, not
    a measurement — this repo has published three stale ones."""
    view = _read(VIEW)
    seg = view[view.index("Part of the {{ $pg['name'] }}"):]
    seg = seg[:seg.index('Other contracts worth seeing')]
    for key in ("$pg['contracts']", "$pg['vendors']", "$pg['agencies']",
                "$pgMoney($pg['value'])"):
        assert key in seg, f'the panel stopped rendering {key} from the payload'
    assert '$pg[\'ceiling\']' in seg, \
        'the panel no longer discloses a master ceiling separately'


def test_the_hook_is_registered_on_contracts():
    """⚠ Registered is not running — but unregistered certainly is not. The
    docstring records how it was verified that this table's hooks fire at all
    (all seven declared indexes present after a DROP+RENAME ingest)."""
    src = _read(os.path.join(API, 'data_scheduler.py'))
    tree = ast.parse(src)
    assigned = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, 'id', '') == 'POST_INGEST_HOOKS' for t in node.targets):
            assigned = node.value
    assert assigned is not None, 'POST_INGEST_HOOKS is gone'
    keys = [k.value for k in assigned.keys if isinstance(k, ast.Constant)]
    assert 'contracts' in keys, 'no hook is registered on the contracts table'
    idx = keys.index('contracts')
    names = [getattr(e, 'id', '') for e in assigned.values[idx].elts]
    assert 'derive_program_groups_hook' in names, \
        'the program rebuild is not registered on the contracts ingest'


# --------------------------------------------------------------------------
# A curated decision that does not apply must SAY SO.
#
# ⚠⚠ This file's whole purpose is applying human judgement, so losing a piece
# of it quietly is the worst failure available to it. Three ways a seed rule
# can match nothing, all previously silent, all now reported.
# --------------------------------------------------------------------------

def _log():
    out = []
    return out, out.append


def test_a_curated_contract_that_matches_nothing_is_reported():
    """⚠⚠ `if cid in by_id` DROPPED THE ID AND SAID NOTHING. The id may be a
    typo, or the contract may have left the technology universe, or an ingest
    may have removed it — and the program then renders with fewer members than
    the curator chose.

    `verify()` cannot catch this. It checks rows that WERE written for orphans,
    which is the opposite direction: it can see a row naming a missing
    contract, never a curated id that never became a row.
    """
    bpg = _load_builder()
    msgs, log = _log()
    progs = {'p': {'name': 'P', 'contracts': ['CT1-REAL', 'CT1-TYPO'],
                   'tokens': [], 'excludes': [], 'notes': {}}}
    rows = [{'contract_id': 'CT1-REAL', 'contract_title': 'a real one'}]
    members = bpg.resolve_members(progs, rows, log=log)['p']
    assert members == {'CT1-REAL': 'curated'}
    joined = ' '.join(msgs)
    assert 'CT1-TYPO' in joined and 'MATCHED NOTHING' in joined, \
        f'the unresolved curated id was dropped silently: {msgs}'
    assert 'CT1-REAL' not in joined, 'the resolved id should not be reported'


def test_an_exclude_that_removes_nothing_is_reported():
    """⚠ A typo in an exclude is WORSE than one in a contract rule: the
    contract it was meant to remove stays IN. A rejection that does not happen
    must not be silent (#155)."""
    bpg = _load_builder()
    msgs, log = _log()
    progs = {'p': {'name': 'P', 'contracts': [], 'tokens': ['widget'],
                   'excludes': ['CT1-NOTAMEMBER'], 'notes': {}}}
    rows = [{'contract_id': 'CT1-A', 'contract_title': 'widget services'}]
    members = bpg.resolve_members(progs, rows, log=log)['p']
    assert members == {'CT1-A': 'token'}
    assert any('CT1-NOTAMEMBER' in m and 'removed NOTHING' in m for m in msgs), \
        f'a no-op exclusion was silent: {msgs}'


def test_a_token_matching_no_title_is_reported():
    """A token rule that matches nothing is a program with no members from it —
    usually a spelling that does not appear in any title."""
    bpg = _load_builder()
    msgs, log = _log()
    progs = {'p': {'name': 'P', 'contracts': [], 'tokens': ['nosuchthing'],
                   'excludes': [], 'notes': {}}}
    rows = [{'contract_id': 'CT1-A', 'contract_title': 'widget services'}]
    assert bpg.resolve_members(progs, rows, log=log)['p'] == {}
    assert any('nosuchthing' in m and 'matched 0 titles' in m for m in msgs), \
        f'a token matching nothing was silent: {msgs}'


def test_an_unparseable_seed_line_is_reported(tmp_path):
    """⚠ Every `continue` in load_curated discards a line a human wrote. A rule
    column reading `contracts` instead of `contract` used to vanish in silence —
    the NYCHA seed-header defect in a new place."""
    bpg = _load_builder()
    seed = tmp_path / 'seed.csv'
    seed.write_text(
        '# a comment header, which every seed in api/seed/ has\n'
        'program_slug,program_name,rule,value,note\n'
        'good,Good,contract,CT1-A,fine\n'
        'typo,Typo,contracts,CT1-B,the rule column is misspelled\n'
        'short,Short,contract\n', encoding='utf-8')
    bpg = _load_builder()
    msgs, log = _log()
    progs = bpg.load_curated(str(seed), log=log)
    assert set(progs) == {'good'}, f'unexpected programs parsed: {sorted(progs)}'
    joined = ' '.join(msgs)
    assert "rule='contracts'" in joined or 'contracts' in joined, \
        f'the misspelled rule was skipped silently: {msgs}'
    assert 'SKIPPED' in joined and joined.count('SKIPPED') == 2, \
        f'expected exactly 2 skipped lines to be reported: {msgs}'


def test_the_builder_passes_its_log_into_both_seed_readers():
    """⚠ The reporting above is useless if `build()` does not pass `log` — a
    default of None makes every warning a no-op while every unit test still
    passes. This is the no-op-ping defect: the code is present and inert."""
    import inspect
    bpg = _load_builder()
    src = inspect.getsource(bpg.build)
    assert 'load_curated(log=log)' in src, 'build() no longer passes log to the seed reader'
    assert 'resolve_members(progs, rows, log=log)' in src, \
        'build() no longer passes log to the resolver, so no rule warning can fire'


def test_curated_reasoning_never_restates_the_programs_own_scope():
    """⚠⚠ THE #240 DEFECT, AND I REINTRODUCED IT HERE BEFORE THIS GUARD EXISTED.

    The program block renders contracts / vendors / agencies / committed value
    LIVE, computed from the database, and the curated `why` renders directly
    beneath it. So a scope figure typed into the note is the same number twice,
    one of which cannot update — and this is a table rebuilt on every contracts
    ingest, so it moves.

    My first draft of the ten curated rows opened each one with exactly that:
    "72 contracts / 28 vendors / $173.6M". Worse, the figures were WRONG when
    written, because I had measured them over the 4,397-contract tech universe
    while membership is scoped to all 38,967 — HERRC read 11 contracts / $1.6M
    against a real 17 / $77.7M. Both problems, one rule.

    ⚠ Figures the page CANNOT derive stay allowed and wanted: a single
    contract's role within the program, an external fact, a published price.
    What is banned is the self-describing scope clause.

    Mirrors test_curated_reasoning_never_restates_the_familys_own_scope in
    test_license_families.py — same defect, different seed.
    """
    import csv
    import io as _io
    import re as _re
    with _io.open(SEED, encoding='utf-8') as fh:
        rows = [r for r in csv.reader(fh)
                if r and r[0].strip() and not r[0].lstrip().startswith('#')
                and r[0].strip() != 'program_slug']
    assert len(rows) >= 10, f'only {len(rows)} curated rows — did the seed shrink?'

    lead = _re.compile(r'^\s*\$[\d,]+\.?\d*[MK]?\b')
    scope = _re.compile(r'\b(?:over|across|spanning)\s+\d+\s+(?:contracts?|vendors?|agencies)\b', _re.I)
    tally = _re.compile(r'\b\d+\s+contracts?\s*/\s*\d+\s+vendors?\b', _re.I)
    offenders = []
    for r in rows:
        slug, why = r[0].strip(), (r[4] if len(r) > 4 else '')
        if lead.match(why):
            offenders.append(f'{slug}: opens with its own value — {why[:44]!r}')
        for pat, what in ((scope, 'restates its own scope'),
                          (tally, 'restates its own contracts/vendors tally')):
            m = pat.search(why)
            if m:
                offenders.append(f'{slug}: {what} — {m.group(0)!r}')
    assert not offenders, (
        'curated reasoning restates figures the program block already renders '
        'live, so it goes stale on the next ingest:\n  ' + '\n  '.join(offenders))


def test_every_curated_token_row_carries_a_reason():
    """⚠ A token admits every contract whose title contains it, which is the
    broadest rule in this seed and the only one that can silently grow. The seed
    header demands the author run --report and read what it admits; an
    unexplained token is evidence nobody did."""
    import csv
    import io as _io
    with _io.open(SEED, encoding='utf-8') as fh:
        rows = [r for r in csv.reader(fh)
                if r and r[0].strip() and not r[0].lstrip().startswith('#')
                and r[0].strip() != 'program_slug']
    thin = [r[0] for r in rows
            if r[2].strip().lower() == 'token' and len((r[4] if len(r) > 4 else '').strip()) < 40]
    assert not thin, f'token rows with no real reasoning: {thin}'


def test_a_contract_claimed_by_two_programs_is_named_not_a_key_violation():
    """⚠⚠ contract_program is PRIMARY KEY (contract_id), so one contract in two
    programs aborts the whole rebuild inside its transaction. That was
    impossible while there was a single curated program and became possible the
    moment there were ten.

    ⚠ And the post-ingest hook SWALLOWS exceptions — "hook failed (non-fatal)" —
    so without this the visible outcome is a warning plus a table silently
    holding yesterday's membership. The failure must name the contract and both
    programs, because the fix is a human `exclude` row.
    """
    bpg = _load_builder()
    progs = {
        'a': {'name': 'A', 'contracts': [], 'tokens': ['widget'], 'excludes': [], 'notes': {}},
        'b': {'name': 'B', 'contracts': [], 'tokens': ['gadget'], 'excludes': [], 'notes': {}},
    }
    rows = [{'contract_id': 'CT1-BOTH', 'contract_title': 'widget and gadget services'}]

    # the fixture must actually collide, or everything below is vacuous
    resolved = bpg.resolve_members(progs, rows)
    owners = sorted(slug for slug, members in resolved.items() if 'CT1-BOTH' in members)
    assert owners == ['a', 'b'], f'the fixture no longer collides: {owners}'

    # and build() must detect it BEFORE the dry-run return, so --report sees it
    import inspect
    src = inspect.getsource(bpg.build)
    assert 'COLLISION' in src and 'raise ValueError' in src, (
        'build() no longer detects a contract claimed by two programs; it will '
        'surface as a raw duplicate-key error swallowed by the hook')
    assert src.index('collisions') < src.index('if not apply'), \
        'the collision check runs after the dry-run return, so --report cannot see it'
