"""One organisation is ONE row: `agencyalias.group_by_org`, and its call sites.

⚠⚠ THE DEFECT. Every agency chart in the procurement section grouped on the
PUBLISHED STRING and then linked by the RESOLVED ORG — two identities, and the
City publishes more strings than it has agencies. Measured 2026-09-16 over all
46 distinct `contracts.agency` values, exactly two organisations carry two
strings each (DCAS and the Office of Criminal Justice), and the consequences
were visible on three surfaces: `/procurement/agencies` listed DCAS twice with
both rows linking to one profile, and the Overview's "Value by agency" pie took
its top 8 BEFORE merging, publishing DCAS at $190.7M with a further $109.9M of
the same organisation folded into the grey "3 others".

⚠ Loaded BY PATH: `conftest.py` replaces the whole `modules` package with a
MagicMock, so `from modules import agencyalias` measures nothing.
"""
import ast
import asyncio
import importlib.util
import os
import re

API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(os.path.dirname(API), rel), encoding='utf-8') as fh:
        return fh.read()


def _code(src):
    """Source with comments and docstrings blanked.

    ⚠ This file's own prose quotes the strings the scans below look for — the
    own-prose guard failure this repo has recorded more than a dozen times.
    Docstrings go by LINE RANGE, never by removing triple-quoted strings, since
    the SQL is triple-quoted too."""
    lines = src.split('\n')
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Module)):
            doc = ast.get_docstring(node, clean=False)
            if doc and node.body and isinstance(node.body[0], ast.Expr):
                e = node.body[0]
                for i in range(e.lineno - 1, getattr(e, 'end_lineno', e.lineno)):
                    lines[i] = ''
    return '\n'.join(l.split('#')[0] if l.lstrip().startswith('#') else l
                     for l in lines)


def _module():
    spec = importlib.util.spec_from_file_location(
        '_real_agencyalias', os.path.join(API, 'modules', 'agencyalias.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(getattr(mod, 'group_by_org', None)), \
        'the real agencyalias did not load — this file would measure a mock'
    return mod


def _with(orgs, names=None):
    """The real module with only its two DB calls answered from a dict."""
    mod = _module()

    async def _resolve_many(pg, agency_names, logger=None):
        return {n: orgs[n] for n in {(x or '').strip() for x in agency_names}
                if n in orgs}

    async def _org_names(pg, ids, logger=None):
        return dict(names or {})

    mod.resolve_many = _resolve_many
    mod.org_names = _org_names
    return mod


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# behaviour
# ---------------------------------------------------------------------------

def test_two_strings_naming_one_organisation_become_one_row():
    """The measured case, in miniature: DCAS's two published spellings."""
    mod = _with({'DCASDIVISION OF MUNICIPAL SUPPLY SERVICE': 170010856,
                 'DEPARTMENT OF CITYWIDE ADMINISTRATIVE SERVICES': 170010856},
                {170010856: 'Department of Citywide Administrative Services'})
    rows = [{'agency': 'DEPARTMENT OF TRANSPORTATION', 'total': 1708.5},
            {'agency': 'DCASDIVISION OF MUNICIPAL SUPPLY SERVICE', 'total': 109.9},
            {'agency': 'DEPARTMENT OF CITYWIDE ADMINISTRATIVE SERVICES', 'total': 190.7}]
    out = _run(mod.group_by_org(None, rows, 'agency', ['total']))
    assert len(out) == 2, f'expected one row per organisation, got {len(out)}'
    dcas = [r for r in out if r['org_id'] == 170010856]
    assert len(dcas) == 1
    assert round(dcas[0]['total'], 1) == 300.6, \
        f"the merged row does not carry both halves: {dcas[0]['total']}"
    assert sorted(dcas[0]['spellings']) == [
        'DCASDIVISION OF MUNICIPAL SUPPLY SERVICE',
        'DEPARTMENT OF CITYWIDE ADMINISTRATIVE SERVICES'], \
        'the merged row does not record which published strings it covers'


def test_a_merged_row_is_labelled_with_the_organisations_registered_name():
    """⚠⚠ NOT ONE OF ITS PARTS. Labelling a merged row with the larger half reads
    as if the smaller half had been left out, which is the opposite of what
    happened — and this repo already has the rule from the capital section: the
    label a reader clicks is the title they land on."""
    mod = _with({'OFFICE OF CRIMINAL JUSTICE (002)': 170011021,
                 'OFFICE OF CRIMINAL JUSTICE (128)': 170011021},
                {170011021: "Mayor's Office of Criminal Justice"})
    rows = [{'agency': 'OFFICE OF CRIMINAL JUSTICE (128)', 'total': 1986.4},
            {'agency': 'OFFICE OF CRIMINAL JUSTICE (002)', 'total': 1702.5}]
    out = _run(mod.group_by_org(None, rows, 'agency', ['total']))
    assert len(out) == 1
    assert out[0]['agency'] == "Mayor's Office of Criminal Justice", \
        f"a merged row still wears a budget code: {out[0]['agency']!r}"


def test_an_unmerged_row_keeps_the_publishers_own_string():
    """⚠ 44 of the 46 agencies must read exactly as they always have — this
    section keeps PASSPort's vocabulary, and a relabelling pass over every row
    would be a much larger editorial change than the defect warrants.

    ⚠⚠ THIS PROPERTY IS ENFORCED TWICE, so a single mutation cannot falsify it
    and reads as a blind guard: only merged groups are relabelled, AND the
    registered names are only fetched for merged ids, so dropping either
    condition alone leaves the other one holding. Measured — both single-half
    mutations landed and this test passed. Mutating the PAIR fires it. Recorded
    because "I mutated it and nothing happened" is otherwise the wrong
    conclusion to draw here."""
    mod = _with({'DEPARTMENT OF INFORMATION TECHNOLOGY AND TELECOMMUNICATIONS': 170010858},
                {170010858: 'Office of Technology and Innovation'})
    rows = [{'agency': 'DEPARTMENT OF INFORMATION TECHNOLOGY AND TELECOMMUNICATIONS',
             'total': 4933.9}]
    out = _run(mod.group_by_org(None, rows, 'agency', ['total']))
    assert out[0]['agency'] == \
        'DEPARTMENT OF INFORMATION TECHNOLOGY AND TELECOMMUNICATIONS', \
        'a single-spelling agency was relabelled — the merge is not supposed to rename'


def test_rows_that_resolve_to_nothing_are_never_merged_with_each_other():
    """⚠⚠ "We do not know which organisation this is" is not evidence that two
    such strings are the same one. Same discipline as `resolve_many` leaving an
    ambiguous name unlinked rather than pointing it at an arbitrary entity."""
    mod = _with({})
    rows = [{'agency': 'SOMETHING UNKNOWN', 'total': 5.0},
            {'agency': 'ANOTHER UNKNOWN', 'total': 3.0}]
    out = _run(mod.group_by_org(None, rows, 'agency', ['total']))
    assert len(out) == 2, 'two unresolved strings were folded into one row'
    assert all(r['org_id'] is None for r in out)


def test_a_distinct_count_is_unioned_and_not_added():
    """⚠⚠ A COUNT OF DISTINCT THINGS CANNOT BE ADDED. The data lens carries a
    per-agency count of product families; summing two groups' counts
    double-counts every family both halves buy."""
    mod = _with({'A': 1, 'B': 1}, {1: 'One Agency'})
    rows = [{'agency': 'A', 'v': 1.0, 'families': {'x', 'y'}},
            {'agency': 'B', 'v': 1.0, 'families': {'y', 'z'}}]
    out = _run(mod.group_by_org(None, rows, 'agency', ['v'],
                                set_keys=('families',)))
    assert len(out) == 1
    assert out[0]['families'] == {'x', 'y', 'z'}, \
        f"families were added rather than unioned: {out[0]['families']}"


def test_a_merge_moves_a_row_up_and_never_down():
    """⚠ Order is the caller's, but a group must take the highest position any of
    its parts held — otherwise a merged agency can sort BELOW a smaller one that
    was never split, which is the ranking defect wearing new clothes."""
    mod = _with({'B': 7, 'D': 7}, {7: 'Merged'})
    rows = [{'agency': 'A', 'v': 10.0}, {'agency': 'B', 'v': 6.0},
            {'agency': 'C', 'v': 5.0}, {'agency': 'D', 'v': 4.0}]
    out = _run(mod.group_by_org(None, rows, 'agency', ['v']))
    assert [r['agency'] for r in out] == ['A', 'Merged', 'C'], \
        f'the merged row did not take its largest part\'s place: {[r["agency"] for r in out]}'


# ---------------------------------------------------------------------------
# the call sites
# ---------------------------------------------------------------------------

def test_no_query_that_feeds_a_merge_caps_its_rows_in_sql():
    """⚠⚠ THE CAP MUST COME AFTER THE MERGE. A `LIMIT 8` in SQL cuts the split
    rows before anything can join them, so the merge can no longer see the tail
    — which is exactly how $109.9M of DCAS ended up inside "3 others" while the
    named wedge read $190.7M. Count before you cap.

    ⚠ Measured from each MERGE BACKWARDS to its own query, not by scanning every
    agency query in the file: two `expiring_agencies` queries and the section
    search's agencies arm are capped on purpose (nothing links them to an org),
    and a rule that flagged those would be switched off rather than obeyed."""
    for rel in ('api/routers/oce.py', 'api/routers/licenses.py'):
        src = _code(_read(rel))
        calls = [m.start() for m in re.finditer(r'agencyalias\.group_by_org\(', src)]
        assert calls, f'no merge site found in {rel} — this guard would measure nothing'
        for i in calls:
            sel = src.rfind('SELECT', 0, i)
            assert sel > 0, f'{rel}: a merge with no query above it'
            between = src[sel:i]
            assert not re.search(r'\bLIMIT\b', between, re.I), \
                (f'{rel}: the query feeding a merge caps in SQL — the merge '
                 f'cannot see what a LIMIT removed')


def test_both_agency_charts_and_the_listing_merge_by_organisation():
    """⚠ Each site COUNTED by its own exact spelling. A ±window around one call
    overlaps the next in this file, so a windowed check can be satisfied by its
    neighbour — measured here once already."""
    src = _code(_read('api/routers/oce.py'))
    assert src.count('agencyalias.group_by_org(') == 3, \
        ('expected three merge sites in oce.py — the two agency charts and the '
         f"listing — found {src.count('agencyalias.group_by_org(')}")
    lic = _code(_read('api/routers/licenses.py'))
    assert lic.count('agencyalias.group_by_org(') == 1, \
        'the data lens no longer groups its agency list by organisation'


def test_the_agency_listing_merges_before_it_paginates():
    """⚠⚠ MERGING AFTER PAGINATION CANNOT WORK — a group's two halves can fall on
    different pages, so the listing would show one of them and silently drop the
    other's value from both."""
    src = _code(_read('api/routers/oce.py'))
    i = src.index('async def list_agencies')
    fn = src[i:src.index('\n@router', i)]
    merge = fn.index('group_by_org(')
    assert 'LIMIT {limit} OFFSET {offset}' not in fn, \
        'the listing paginates in SQL again — that is before the merge'
    slice_at = fn.index('[offset:offset + limit]')
    assert merge < slice_at, 'the listing slices its page before merging'


def test_the_listings_top_vendor_is_asked_of_every_spelling():
    """⚠ A merged row's top vendor must be the largest across the WHOLE
    organisation. Querying only the label's string answers for one half of DCAS
    and reports it as DCAS's — a confident wrong answer about a named vendor,
    which is the worst shape this repo records."""
    src = _code(_read('api/routers/oce.py'))
    i = src.index('async def list_agencies')
    fn = src[i:src.index('\n@router', i)]
    assert "r.get('spellings')" in fn, \
        'the top-vendor lookup no longer reads the merged row\'s spellings'


def test_both_agency_charts_sort_after_merging_and_before_capping():
    """⚠⚠ A MERGE CHANGES THE RANKING, and the module deliberately leaves order
    to the caller. Measured on the SERVED payload before this was fixed: DCAS
    came back merged at $300.6M sitting BELOW Health and Mental Hygiene at
    $213.8M in a chart titled "Value by agency" — the merge was right and the
    chart still published a false ranking. Sort, then cap: capping first would
    cut the list on the pre-merge order and lose the tail again."""
    src = _code(_read('api/routers/oce.py'))
    for m in re.finditer(r"agencyalias\.group_by_org\(", src):
        block = src[m.start():m.start() + 700]
        if '_AGENCY_CHART_TOP' not in block:
            continue                      # the listing sorts by the caller's key
        sort_at = block.find('.sort(key=lambda r: -float(')
        cap_at = block.find('_AGENCY_CHART_TOP')
        assert sort_at > 0, 'an agency chart no longer re-sorts after merging'
        assert sort_at < cap_at, 'an agency chart caps before it sorts'
    assert src.count('_AGENCY_CHART_TOP') >= 3, \
        'the shared agency-chart cap lost a consumer — both charts must use one owner'
