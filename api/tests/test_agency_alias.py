"""Agency strings that resolve to no org — the curated map, and the rules it must keep.

⚠⚠ THE DEFECT. `contracts.agency` stores legacy names, orthographic variants,
malformed strings and City budget codes, so an exact match against `wegov_orgs`
missed 11 of 46 distinct agency strings — **3,838 contracts, $23,171.9M**,
measured 2026-09-01. The user-visible shape was the dangerous one: searching an
agency by its CURRENT canonical name returned "0 contracts" for agencies holding
billions, and a zero reads as "no contracts" rather than "no string match".

    agency="Technology and Innovation"  ->     0
    agency="INFORMATION TECHNOLOGY"     -> 1,381 contracts / $6,778,323,968

⚠⚠ WHY CURATED AND NOT FUZZY. Trigram nearest-neighbour gets the two LARGEST
strings wrong — the $7.4B DoITT string's nearest live org is "Department of
Records and Information Services" (0.44) and the $8.0B DCAS one's is "Municipal
Division of Transitional Services" (0.52), both different agencies. A threshold
would confidently misfile $15.4B.
"""
import ast
import re
import importlib.util
import os
import sys

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
API = os.path.join(ROOT, 'api')


def _load():
    """⚠ BY PATH — conftest.py replaces the whole `modules` package with a
    MagicMock, which would satisfy every assertion below."""
    spec = importlib.util.spec_from_file_location(
        '_agencyalias_test', os.path.join(API, 'modules', 'agencyalias.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_seed_ships_and_parses():
    """⚠ An absent or unparsed seed silently restores the $23.2B blind spot, and
    an empty map is indistinguishable from "every agency already resolves". The
    floor is deliberately below the real 11 so it catches an empty/truncated read
    rather than tracking curation."""
    a = _load()
    rows = a.rows()
    assert len(rows) >= 11, f"only {len(rows)} alias rows parsed — did the seed ship?"
    for r in rows:
        assert r['wegov_org_id'].isdigit(), f"non-numeric org id: {r}"
        assert r['org_name'].strip(), f"row without an org name: {r}"
        assert r['why'].strip(), f"row without a reason: {r['agency']}"


def test_the_comment_header_is_not_read_as_a_row():
    """Every file in api/seed/ carries a `#` header; a parser that does not expect
    one reads it as a data row. That bug shipped once already, in the NYCHA seed."""
    a = _load()
    assert not any(r['agency'].lstrip().startswith('#') for r in a.rows())


def test_a_stored_string_resolves_to_its_org():
    a = _load()
    assert a.org_id_for('DEPARTMENT OF INFORMATION TECHNOLOGY AND TELECOMMUNICATIONS') == 170010858
    assert a.org_id_for('DEPT. OF CONSUMER & WORKER PROTECTION') == 170010866
    # folding is identical on both sides, incl. collapsed whitespace and case
    assert a.org_id_for('  department of  information technology and telecommunications ') == 170010858
    assert a.org_id_for('SOMETHING THAT IS NOT AN AGENCY') is None
    assert a.org_id_for(None) is None


def test_current_name_legacy_name_and_both_acronyms_all_reach_the_same_contracts():
    """The reporter's acceptance check. All three spellings must reach the string
    the contracts are actually filed under."""
    a = _load()
    target = 'DEPARTMENT OF INFORMATION TECHNOLOGY AND TELECOMMUNICATIONS'
    for term in ('Technology and Innovation', 'OTI', 'DOITT', 'oti'):
        assert target in a.agency_strings_for_term(term), f"{term!r} does not reach it"
    # and DCWP by its canonical CURRENT name, not the stored DEPT./& form
    assert 'DEPT. OF CONSUMER & WORKER PROTECTION' in \
        a.agency_strings_for_term('Consumer and Worker Protection')


def test_a_short_token_is_never_substring_matched():
    """⚠ `%UI%` matches BUILDING and `%ABA%` matches DATABASE — a substring match
    on a short token is not a measurement in this repo. Acronyms are matched
    EXACTLY against `aka`; only names of 4+ chars are matched as substrings."""
    a = _load()
    for tok in ('IT', 'OF', 'A', 'CE'):
        assert a.agency_strings_for_term(tok) == [], \
            f"short token {tok!r} substring-matched — it would drag in unrelated agencies"
    # ...but a 3-letter ACRONYM still works, because that path is exact
    assert a.agency_strings_for_term('TLC'), "an exact acronym match must still resolve"


def test_no_stored_string_maps_to_two_different_orgs():
    """A string resolving to two orgs would make the answer depend on row order —
    the ambiguity this map exists to remove."""
    a = _load()
    seen = {}
    for r in a.rows():
        k = a.key(r['agency'])
        if k in seen:
            assert seen[k] == r['wegov_org_id'], \
                f"{r['agency']!r} maps to both {seen[k]} and {r['wegov_org_id']}"
        seen[k] = r['wegov_org_id']


def _fn_src(path, name):
    src = open(path, encoding='utf-8').read()
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return ast.get_source_segment(src, n)
    raise AssertionError(f"{name} not found in {path}")


def test_the_resolver_uses_the_alias_only_as_a_fallback():
    """⚠ Order is the safety property. The exact query must still be tried FIRST,
    so this can add resolution where there was none and can never move an agency
    that already resolved."""
    # ⚠⚠ RE-EXPRESSED 2026-09-16, NOT RELAXED. The two tiers moved INTO this
    # module as `resolve_many`, because the rule had three spellings and the one
    # `/oce/agencies` used skipped the alias map entirely. The property is
    # unchanged and is asserted where the rule now lives; `_resolve_org_id` is
    # checked below to delegate, so it cannot grow a fourth copy.
    body = _fn_src(os.path.join(API, 'modules/agencyalias.py'), 'resolve_many')
    assert 'org_id_for' in body, "the resolver no longer consults the alias map"
    exact = body.index('by_upper.get(')
    alias = body.index('org_id_for(')
    assert exact < alias, "the alias map is consulted BEFORE the exact match — it must be a fallback"
    assert 'if hit is None' in body, \
        "the alias tier no longer runs only where the exact match failed"

    # ⚠ And the single-name path must DELEGATE rather than keep its own copy —
    # two spellings is how the listing and the profile came to disagree.
    one = _fn_src(os.path.join(API, 'routers/oce.py'), '_resolve_org_id')
    assert '_resolve_org_ids' in one, "_resolve_org_id no longer delegates"
    assert 'FROM wegov_orgs' not in one, "_resolve_org_id grew its own SQL again"


def test_the_mcp_keeps_the_raw_ilike_so_the_change_can_only_add_rows():
    body = _fn_src(os.path.join(API, 'mcp_server.py'), '_passport_agency_condition')
    assert 'ILIKE' in body, "the raw ILIKE was replaced rather than OR-ed"
    assert 'ANY(' in body, "the alias expansion is gone"
    assert ' OR ' in body, "the two arms are no longer OR-ed — some agencies would stop matching"


def test_the_jobs_and_payroll_tools_do_not_use_the_passport_map():
    """⚠⚠ MEASURED, not assumed. `nycjobs."Agency"` is a THIRD vocabulary —
    abbreviated ("DEPT OF CITYWIDE ADMIN SVCS", "TECHNOLOGY & INNOVATION") — and
    only 6 rows match any of the eleven. Reusing the PASSPort map there would be a
    map that looks applicable and silently answers a different question.
    """
    src = open(os.path.join(API, 'mcp_server.py'), encoding='utf-8').read()
    tree = ast.parse(src)
    for name in ('search_jobs', 'get_salary_stats', 'get_top_salaries'):
        body = _fn_src(os.path.join(API, 'mcp_server.py'), name)
        assert '_passport_agency_condition' not in body, (
            f"{name} filters a non-PASSPort agency column through the PASSPort alias map")
    # and the two that SHOULD use it, do
    for name in ('search_contracts', 'get_contract_stats', 'search_solicitations'):
        body = _fn_src(os.path.join(API, 'mcp_server.py'), name)
        assert '_passport_agency_condition' in body, f"{name} lost its alias expansion"


def test_the_normalizer_mapped_tools_resolve_through_wegov_org_id():
    """⚠⚠ TWO MECHANISMS, AND USING THE WRONG ONE IS A SILENT WRONG ANSWER.

    `contracts`/`solicitations` carry no org id, so they need the curated seed.
    `nycjobs`/`payrolldata` DO carry `wegov-org-id`, stamped at ingest and
    measured complete and valid (59/59 and 170/170 agencies resolve to a live
    org, 0 dangling), so a seed there would duplicate a mapping that exists and
    then drift from it.

    The gap this closes is the larger of the two: 36 of 59 job agencies and 136
    of 170 payroll agencies were unreachable by their own canonical org name —
    4,929,787 payroll rows, 73%.
    """
    for name in ('search_jobs', 'get_salary_stats', 'get_top_salaries'):
        body = _fn_src(os.path.join(API, 'mcp_server.py'), name)
        assert '_org_mapped_agency_condition' in body, (
            f"{name} no longer resolves its agency through wegov-org-id — it is "
            f"back to matching a raw string that 73% of rows do not carry")
    # ...and the PASSPort tools must NOT use the org-id route: those tables have
    # no such column, so the condition would reference a column that isn't there.
    for name in ('search_contracts', 'get_contract_stats', 'search_solicitations'):
        body = _fn_src(os.path.join(API, 'mcp_server.py'), name)
        assert '_org_mapped_agency_condition' not in body, (
            f"{name} queries a table with no wegov-org-id column")


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def test_the_org_expansion_is_capped_so_a_generic_word_cannot_broaden_a_search():
    """⚠ A generic word is not an agency name: measured, "office" matches 117 live
    orgs and "department" 50, against "education" 10 and "sanitation" 6. Above the
    cap the expansion returns [] and the caller falls back to its raw ILIKE — i.e.
    exactly today's behaviour — so the cap can only reduce reach, never break a
    search that already worked."""
    a = _load()

    async def fake(sql, params, n):
        return [{'id': str(i)} for i in range(n)]

    ids = _run(a.org_ids_for_term(lambda s, p: fake(s, p, a._ORG_TERM_MAX), 'education'))
    assert len(ids) == a._ORG_TERM_MAX, "a term at the cap should still expand"
    ids = _run(a.org_ids_for_term(lambda s, p: fake(s, p, a._ORG_TERM_MAX + 1), 'office'))
    assert ids == [], "a term matching more orgs than the cap must not expand"


def test_the_org_expansion_degrades_to_the_raw_ilike_on_failure():
    """An org lookup failing must cost the expansion, never the search."""
    a = _load()

    async def boom(sql, params):
        raise RuntimeError("db down")

    assert _run(a.org_ids_for_term(boom, 'education')) == []
    assert _run(a.org_ids_for_term(lambda s, p: boom(s, p), '')) == []


def test_the_org_query_keeps_both_matching_rules():
    """The same discipline as the seed side: acronyms match EXACTLY, only 4+ char
    names match as substrings. A substring match on a short token is not a
    measurement in this repo."""
    a = _load()
    assert 'alternate_name' in a._ORG_SQL, "the acronym (exact) arm is gone"
    assert 'length(trim($1)) >= 4' in a._ORG_SQL, "the short-token guard is gone"
    assert 'retired_at IS NULL' in a._ORG_SQL, "a retired org could now capture a search"


def test_the_mcp_image_ships_every_seed_its_modules_read():
    """⚠⚠ A MISSING `COPY` IS A SILENT WRONG ANSWER, NOT A BUILD ERROR.

    `Dockerfile.mcp` copies `modules/` but originally not `seed/`, so
    `modules/agencyalias.py` found no seed inside the mcp container, built an
    empty map, and `search_contracts(agency="Technology and Innovation")` still
    returned 0 contracts for an agency holding $6.78B — the exact defect the seed
    exists to remove, reintroduced by a missing line in a different Dockerfile.

    The api image ships seed/ via `COPY . .`, so the SAME CODE behaved
    differently in the two containers. Found on prod minutes after deploy, and
    only because agencyalias logs the unreadable path at ERROR instead of
    degrading quietly — an empty map is otherwise indistinguishable from "every
    agency already resolves".
    """
    mods = os.path.join(API, 'modules')
    readers = []
    for fn in sorted(os.listdir(mods)):
        if not fn.endswith('.py'):
            continue
        src = open(os.path.join(mods, fn), encoding='utf-8').read()
        tree = ast.parse(src)
        # a module that builds a path containing the 'seed' segment needs the dir
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == 'seed':
                readers.append(fn)
                break
    assert readers, "no module resolves a seed path — has agencyalias been removed?"
    df = open(os.path.join(API, 'Dockerfile.mcp'), encoding='utf-8').read()
    copies = [l.strip() for l in df.splitlines()
              if l.strip().startswith('COPY') and not l.strip().startswith('#')]
    assert any(re.match(r'COPY\s+seed/?\s', c) for c in copies), (
        f"Dockerfile.mcp does not COPY seed/, but these modules read one: {readers}. "
        f"The mcp container would build an empty map and answer 0 instead of failing. "
        f"COPY lines present: {copies}")
