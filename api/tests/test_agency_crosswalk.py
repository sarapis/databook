"""The agency -> org rule has ONE owner, and it is `agencyalias.resolve_many`.

⚠⚠ WHY THIS FILE EXISTS. The rule had THREE spellings. `oce._resolve_org_id`
did exact-then-alias for one name; `modules/agencyalias` owned the curated tier;
and `/oce/agencies` carried its OWN inline correlated subquery against
`wegov_orgs` that never consulted the seed at all. So the curated rows mapping
DoITT -> OTI, DCASDIVISION -> DCAS and NEW YORK CITY POLICE DEPARTMENT ->
Police Department were bypassed on the surface consumers actually read, and
measured 2026-09-16 that is **7 of 182** master-agreement rows resolving with
every large agency missing.

⚠ The runtime half — that the batch path and the single-name path agree on every
stored agency string — needs a database and lives in
`scripts/headless/verify_agency_crosswalk.py`. Two SQL texts for one rule cannot
be pinned by looking alike.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(rel):
    return io.open(os.path.join(ROOT, rel), encoding='utf-8').read()


def _code(src):
    """Source with whole-line comments removed. ⚠ The comments here EXPLAIN the
    banned pattern and therefore contain it — an own-prose firing has already
    cost this repo a guard that passed against a re-typed fold."""
    return "\n".join(l for l in src.split("\n") if not l.strip().startswith('#'))


def test_no_endpoint_resolves_an_agency_to_an_org_with_its_own_sql():
    """⚠⚠ THE DEFECT ITSELF. An inline `SELECT ... FROM wegov_orgs` that matches
    on an agency name is a second rule, and the one that shipped skipped the
    curated seed entirely. Resolution goes through the module."""
    for rel in ('api/routers/oce.py', 'api/routers/licenses.py'):
        src = _code(_read(rel))
        # A name/alternate_name comparison against wegov_orgs, anywhere but the
        # module, is the banned shape.
        for m in re.finditer(r'FROM wegov_orgs\b', src):
            window = src[m.start():m.start() + 400]
            assert 'alternate_name' not in window or 'agency' not in window.lower(), \
                f'{rel} resolves an agency to an org with its own SQL near: ' \
                f'{window[:120]!r}'


def test_the_single_name_path_delegates_to_the_batch_owner():
    """⚠ `_resolve_org_id` must not keep its own copy of the two tiers, or the
    profile and the listing can disagree about the same agency."""
    src = _code(_read('api/routers/oce.py'))
    i = src.index('async def _resolve_org_ids')
    fn = src[i:src.index('\nasync def ', i + 10)]
    assert 'agencyalias.resolve_many' in fn, \
        'the batch resolver no longer delegates to the module that owns the rule'


def test_the_tier_order_puts_the_exact_match_first():
    """⚠⚠ LOAD-BEARING. The seed may only ADD resolution where there was none;
    if the alias tier ran first it could MOVE an agency that already resolved
    correctly, silently re-pointing a profile link."""
    src = _code(_read('api/modules/agencyalias.py'))
    i = src.index('async def resolve_many')
    fn = src[i:src.index('\ndef ', i)]
    exact = fn.index('by_upper.get(')
    alias = fn.index('org_id_for(')
    assert exact < alias, 'the curated alias tier now runs before the exact match'
    assert 'if hit is None' in fn, \
        'the alias tier no longer runs only where the exact match failed'


def test_the_seed_still_covers_the_agencies_exact_matching_cannot_reach():
    """⚠ These three are the measured reason the seed exists — together the
    largest unresolved strings in the corpus. Losing a row here silently
    un-links an agency holding billions."""
    seed = _read('api/seed/agency_org_aliases.csv')
    for name in ('DEPARTMENT OF INFORMATION TECHNOLOGY AND TELECOMMUNICATIONS',
                 'DCASDIVISION OF MUNICIPAL SUPPLY SERVICE',
                 'NEW YORK CITY POLICE DEPARTMENT'):
        assert name in seed, f'{name} lost its curated mapping'
    # ⚠ Non-vacuity: a seed that failed to parse would satisfy nothing above.
    rows = [l for l in seed.split('\n') if l.strip() and not l.startswith('#')]
    assert len(rows) >= 10, f'the alias seed has only {len(rows)} rows — did it fail to load?'


def test_the_agency_chart_serves_full_names():
    """⚠⚠ `[:40]` MADE THE CHART UNLINKABLE. It cut "DEPARTMENT OF INFORMATION
    TECHNOLOGY AND TELECOMMUNICATIONS" to "...AND", which matches no org name
    and no alias — and two long agency names became indistinguishable. Shortening
    for a legend is the CONSUMER's job, and the chart does it with a middle
    ellipsis that keeps the distinguishing tail."""
    src = _code(_read('api/routers/oce.py'))
    # ⚠ Scoped to the charts that CARRY org ids. `expiring_agencies` is still
    # truncated at the endpoint and is deliberately left alone: it feeds the
    # queue's own chart, nothing links it, and widening its labels is a visual
    # change to a surface this work was not about. Seen and left, not missed —
    # if it is ever linked, it needs the same treatment.
    #
    # ⚠⚠ EVERY SITE, NOT THE FIRST. There are TWO agency-chart builders in this
    # file and the first draft used `src.index(...)`, so it checked one and was
    # silent when a mutation truncated the OTHER. Measured by mutation; a guard
    # that inspects the first of N is a guard on 1/N of the property.
    #
    # ⚠ RE-EXPRESSED 2026-09-16, never relaxed. The builders no longer call
    # `_resolve_org_ids` directly — they call `agencyalias.group_by_org`, which
    # resolves through the SAME one owner and additionally merges the strings
    # that name one organisation. The anchor moved with the code; every
    # assertion below still holds and two more were added.
    sites = [m.start() for m in re.finditer(r'agencyalias\.group_by_org\(', src)]
    assert len(sites) >= 2, \
        f'expected both agency-chart builders to resolve org ids, found {len(sites)}'
    # ⚠ The /oce/agencies LISTING also calls group_by_org but is not a chart; its
    # window only ever passed the org_id check by borrowing the text of the
    # neighbouring `_resolve_org_id` function (found 2026-09-24, when four lines
    # of bound-parameter code pushed that neighbour out of range). The label
    # check still applies to it; the org_id check is for the charts.
    listing = src.index('async def list_agencies')
    listing_end = src.index('\n@router', listing)
    for i in sites:
        block = src[max(0, i - 900):i + 600]
        assert "[:40]" not in block, \
            'a linkable agency chart truncates its labels again — they cannot then resolve'
        if listing < i < listing_end:
            continue
        assert 'org_id' in block, 'a linkable agency chart no longer carries org ids'

    # ⚠⚠ AND EACH BUILDER'S OWN SPELLING, COUNTED. Two things defeated the
    # obvious checks, both found by mutation: `'org_ids' in block` is satisfied
    # by `org_idsX` (a substring check blind to a suffix rename — the second
    # time today), and the two builders' ±window OVERLAP, so one could borrow
    # the other's key and pass. Counting each exact spelling measures each
    # builder separately and cannot be satisfied by its neighbour.
    assert src.count("agencies['org_ids'].append(r.get('org_id'))") == 1, \
        'the append-form agency chart no longer carries org ids'
    assert src.count('"org_ids": [r.get(\'org_id\') for r in ag_rows]') == 1, \
        'the dict-form agency chart no longer carries org ids'
