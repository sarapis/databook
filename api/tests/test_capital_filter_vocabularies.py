"""Guards on the `/projects` filter vocabularies — managing agency, and phase.

⚠⚠ THE AGENCY LIST WAS TWO VOCABULARIES IN ONE DROPDOWN. Measured 2026-09-10:
`capital_projects.agency_acro` is NULL on **4,095 of 17,024** rows, and that set
is EXACTLY the 4,095 projects outside the current Capital Commitment Plan — 0
in-plan rows lack it. The option value was `coalesce(agency_acro, agency_key)`,
so 20 agencies appeared twice:

    Department of Parks and Recreation   2,798    and  846  631
    Department of Design and Construction 2,202   and  850  814
    Department of Transportation           785    and  841  345

`850` was the THIRD-LARGEST entry in the list and named nothing. Choosing an
agency by name returned 82% of its projects. 55 options are now 31, and they sum
to the whole spine.

⚠⚠ AND THE MERGE IS CONDITIONAL, BECAUSE ONE KEY IS THREE ORGANISATIONS. `801`
carries SBS (809 rows, org 170010801), Brooklyn Navy Yard (71, org 112137138)
and the Trust for Governors Island (31, org 272683349). A `max(agency_acro)`
merge fuses them and attributes 121 unattributable rows to whichever name sorts
last. The uniqueness test is the load-bearing half of this fix.

⚠⚠ THE PHASE LIST MIXED 5 PHASES WITH 34 NON-PHASES, ordered by count, so
`(Pending)` at 1,854 led a control labelled "Phase or status". They are GROUPED
and never merged: `(Construction)` 18 is not `Construction` 825 — the brackets
are the publisher's mark that no schedule is required, and collapsing them would
be a judgement about what the City meant. Case is the only safe collapse and the
endpoint already does it.

⚠ The list/map/option agreement is behavioural and needs a database, so it lives
in `scripts/headless/verify_agency_options.py`, which asks the list endpoint and
the geojson endpoint for every option and demands the same number from both.
"""
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROOT = os.path.realpath(os.path.join(API, '..'))

ROUTER = os.path.join(API, 'routers', 'capital.py')
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'projects.blade.php')
VERIFIER = os.path.join(ROOT, 'scripts', 'headless', 'verify_agency_options.py')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _no_blade_comments(src):
    """⚠ Own-prose firings in this repo stand at 24. The comment beside each of
    these fixes quotes every string these guards search for."""
    return re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)


def _php_source(src):
    """Only the view's `@php` blocks and Blade directives — comments gone."""
    return _no_blade_comments(src)


# ============================================================ managing agency

def test_the_agency_filter_resolves_an_unnamed_project_to_its_agency():
    """⚠ The clause must look past `agency_acro` to the key's sole acronym.

    Without the second branch, `?agency=DPR` returns 2,798 of Parks' 3,429
    projects and the 631 others are reachable only under a bare `846`.
    """
    src = _read(ROUTER)
    m = re.search(r'_AGENCY_RESOLVE_SQL = """(.*?)"""', src, re.S)
    assert m, 'the agency resolution is no longer owned in one place'
    sql = m.group(1)
    assert 'agency_acro IS NULL' in sql, (
        'the clause no longer reaches the projects the City did not name, so an '
        'agency is split across two options again')
    assert 'p.agency_key = (' in sql, (
        'the unnamed rows are not matched by their key')


def test_a_key_is_resolved_only_when_it_carries_exactly_one_agency():
    """⚠⚠ THIS IS THE HALF THAT STOPS THREE ORGANISATIONS BECOMING ONE.

    `801` is SBS, Brooklyn Navy Yard and the Trust for Governors Island. Without
    the uniqueness test, asking for SBS also returns the other two's unnamed
    rows — 121 projects attributed to an organisation that may not own them.
    """
    src = _read(ROUTER)
    m = re.search(r'_AGENCY_RESOLVE_SQL = """(.*?)"""', src, re.S)
    sql = m.group(1)
    # ⚠ NOT ONE REGEX ACROSS THE WHOLE CLAUSE — the aggregate and its comparison
    # sit on different lines with the subquery's FROM between them, and a regex
    # assuming adjacency fails on correct SQL. Both halves are required, and
    # deleting the clause or loosening `= 1` removes one of them.
    assert re.search(r'count\(DISTINCT\s+\w+\.agency_acro\)', sql), (
        'the resolution no longer requires an agency key to carry exactly one '
        'acronym, so key 801 merges SBS, Brooklyn Navy Yard and the Trust for '
        "Governors Island into whichever name it happens to find")
    assert re.search(r'\)\s*=\s*1\b', sql), (
        'the uniqueness test no longer demands exactly one acronym, so a key '
        'carrying several resolves to one of them')


def test_the_option_list_and_the_filter_read_one_owner():
    """⚠ Two SQL texts for one rule is this repo's most-recorded defect. They
    cannot be pinned by looking alike — one resolves per row through a CTE, the
    other resolves the caller's value once — so they are pinned by both coming
    from named constants, and by the behavioural verifier.
    """
    src = _read(ROUTER)
    for name in ('_AGENCY_RESOLVE_SQL', '_AGENCY_VOCAB_CTE', '_AGENCY_VALUE_SQL'):
        assert re.search(r'^%s = ' % name, src, re.M), '%s is gone' % name
    body = src[src.index('async def capital_project_filters'):]
    body = body[:body.index('\n@router')] if '\n@router' in body else body
    assert '_AGENCY_VOCAB_CTE' in body and '_AGENCY_VALUE_SQL' in body, (
        'the option list spells the agency rule itself instead of reading the '
        'shared owner')
    filt = src[src.index('def _list_filters('):]
    nxt = re.search(r'\n(?:async )?def ', filt[5:])
    filt = filt[:nxt.start() + 5] if nxt else filt
    assert '_AGENCY_RESOLVE_SQL' in filt, (
        'the filter spells the agency rule itself')


def test_an_option_that_names_no_agency_says_so():
    """⚠ Invariant 7: a bare `801` in a list of agency names is a number
    pretending to be a label. Inventing a name would attribute 121 rows to an
    organisation that may not own them, so the option states what is true.
    ⚠ And only the LABEL moves — the filter matches on the value.
    """
    src = _read(ROUTER)
    m = re.search(r'def agency_rows\(res\):(.*?)\n    return \{', src, re.S)
    assert m, 'the unidentified-agency label is gone'
    fn = m.group(1)
    assert 'Not identified' in fn, 'an unnamed agency code renders as a bare number'
    assert 'isdigit()' in fn, (
        'the label is rewritten without testing that the value is a bare code, so '
        'a real acronym could be relabelled')
    assert not re.search(r'r\["value"\]\s*=', fn), (
        'the option VALUE is being rewritten — the filter matches on it, so the '
        'option would stop working')


def test_the_behavioural_agency_check_exists_and_asks_both_surfaces():
    """⚠ The rule's two SQL texts are only safe because something proves they
    agree against real data. The check asks the list AND the map, because
    `/get/capital/geojson` shares `_list_filters` and a divergence there draws
    pins for projects the list excludes.
    ⚠ And it must refuse to pass vacuously — an empty option list sums to 0 == 0.
    """
    src = _read(VERIFIER)
    assert 'capital/projects/filters' in src, 'it no longer reads the options'
    assert 'capital/projects?' in src, 'it no longer asks the list'
    assert 'geojson' in src and 'matching_filters' in src, (
        'it no longer asks the map, so the list and the map can disagree')
    assert re.search(r'len\(opts\)\s*<\s*\d+', src), (
        'it would pass on a truncated or empty option list')


# ==================================================================== phase

def test_the_phase_control_groups_the_two_vocabularies():
    """⚠ 5 phases and 34 non-phases in one flat list ordered by count put
    `(Pending)` 1,854 above `Construction` 825 under one label."""
    view = _php_source(_read(VIEW))
    i = view.index('id="fphase"')
    sel = view[i:view.index('</select>', i)]
    assert sel.count('<optgroup') == 2, (
        'the phase control no longer separates the phases from the statuses')
    assert 'is_standard' in view[:i][-2500:] or 'is_standard' in sel, (
        'the split is no longer read from the payload')


def test_the_phase_split_is_read_from_the_payload_not_re_derived():
    """⚠⚠ THE ENDPOINT OWNS `is_standard`. Re-deriving the split in the template
    from the brackets is a second spelling of one rule, and the two would
    disagree the moment the builder's own exact-match rule changes — it already
    flags 6 `Construction procurement` rows non-standard for a casing difference.
    """
    view = _php_source(_read(VIEW))
    i = view.index('id="fphase"')
    block = view[max(0, i - 3000):view.index('</select>', i)]
    assert re.search(r"\$p\['is_standard'\]", block), (
        'the phase grouping no longer reads is_standard from the payload')
    assert not re.search(r"(strpos|str_starts_with|substr|preg_match)\s*\(\s*\$p\[", block), (
        'the template is deriving the phase split from the label text instead of '
        'reading the payload')


def test_a_published_phase_label_is_never_rewritten():
    """⚠ The brackets are the publisher's own mark. The endpoint's comment says
    the label is a representative stored spelling and never a re-cased
    invention; stripping them here would be the page correcting a publisher it
    is quoting, and would make `(Construction)` indistinguishable from
    `Construction` — 18 projects against 825.
    """
    view = _php_source(_read(VIEW))
    i = view.index('id="fphase"')
    sel = view[i:view.index('</select>', i)]
    for m in re.finditer(r'\{\{(.*?)\}\}', sel, re.S):
        expr = m.group(1)
        if "'label'" in expr:
            assert not re.search(r'(str_replace|trim|rtrim|ltrim|preg_replace|ucfirst|ucwords|strtoupper)\s*\(',
                                 expr), (
                'a published phase label is being rewritten before display: %r'
                % expr.strip())
