"""An empty org-section table must say WHY it is empty.

⚠⚠ THE DEFECT. The org profile offers every section to every org, so a body the
dataset does not cover renders an empty table — which reads as "this organization
has none" rather than "this dataset does not list organizations like this one".
The reassuring direction, again.

THE WORKED EXAMPLE, measured 2026-09-02. `capitalprojectsdollarscomp` holds
72,437 rows across just 26 managing agencies — the bodies with their own capital
budget lines. The Economic Development Corporation is not one, and its Projects
tab was empty and silent about why. It is not a City agency: our own register
types it "Public Benefit or Development Organization", it appears 0 times as a
contracting agency, and its work reaches it as a VENDOR (24 contracts, $12.3B,
all from Small Business Services).

⚠ NOT a mapping failure, which was checked FIRST given the agency defects found
the same day: 0 rows in that table carry a null org id, all 26 managing agencies
resolve, and EDC appears nowhere in the source MANAGING_AGCY text.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
# ⚠⚠ AN EXPLICIT INVENTORY OF THE VIEWS THAT SERVE ORG SECTIONS. There is more
# than one, and the first attempt at this feature put everything in `orgsection`
# — which does NOT serve /projects. `orgProjectSection` renders
# `orgprojectsection.blade.php` through its own controller method, so the scope
# note shipped and never appeared on the very page that prompted it. Third time
# in one session that a similar-but-wrong org view was edited; naming them is the
# fix, exactly as _KNOWN_SURFACES did for the jobs note.
SECTION_VIEWS = (
    'orgsection.blade.php',        # /o/{id}/{section}
    'orgprojectsection.blade.php',  # /o/{id}/projects — its own controller method
)
VIEW = os.path.join(ROOT, 'app/resources/views/orgsection.blade.php')
CTRL = os.path.join(ROOT, 'app/app/Http/Controllers/Organizations.php')
MAIN = os.path.join(ROOT, 'api/main.py')

def _code_only(func_src):
    """A function's source with its DOCSTRING AND COMMENTS REMOVED.

    ⚠⚠ THIS REPO HAS NOW HAD AT LEAST NINE GUARDS FIRE ON THEIR OWN PROSE, and I
    added the ninth writing the test below: its docstring explains that
    `projects_no` is deliberately not returned, so a scan for `projects_no` found
    it in the explanation. A scanner that reads prose as code reports defects that
    are not there — and, worse, can be satisfied by a comment when the code is
    genuinely wrong.
    """
    body = func_src
    # drop the leading docstring
    m = re.search(r'^\s*(?:async\s+)?def [^\n]*\n(\s*)(r?["\']{3})', body)
    if m:
        q = m.group(2)[-3:]
        start = body.index(m.group(2)) + len(m.group(2))
        end = body.index(q, start)
        body = body[:body.index(m.group(2))] + body[end + 3:]
    # ⚠⚠ SQL `--` COMMENTS TOO, and that gap cost a false failure. `_code_only`
    # stripped Python `#` comments only, so a guard asserting the 2026 plan's
    # `mindate` is not used as a date fallback fired on the SQL comment INSIDE the
    # query that explains why it must not be. Eleventh own-prose guard failure in
    # this repo and a new organ: SQL comments live inside a Python string, so the
    # Python comment-stripper cannot see them.
    body = re.sub(r'#[^\n]*', '', body)
    return re.sub(r'--[^\n]*', '', body)


def _py_function_source(src, name):
    """Return a Python function's WHOLE source, from its `def` to the next
    top-level statement.

    ⚠⚠ REPLACES A FIXED-WIDTH `src[i:i + 2400]` WINDOW, WHICH SILENTLY STOPPED
    LOOKING. Lengthening one endpoint's docstring pushed its SQL past the window,
    and the word-boundary guard failed on code that still had its word
    boundaries — reporting a defect that was not there. The mirror failure is
    worse and just as easy: a window that ends early cannot see a boundary that
    was genuinely REMOVED, so the guard would have passed on the real bug. This
    repo has already paid for the same shape when counting rows inside a
    fixed-width slice of a page.
    """
    key = 'async def %s' % name
    i = src.index(key) if key in src else src.index('def %s' % name)
    m = re.search(r'\n(?=@app\.|(?:async )?def |[A-Za-z_]+ = )', src[i:])
    return src[i:i + m.start()] if m else src[i:]


def test_the_section_view_carries_the_scope_note():
    for v in SECTION_VIEWS:
        _assert_note(os.path.join(ROOT, 'app/resources/views', v))


def _assert_note(path):
    src = open(path, encoding='utf-8').read()
    assert 'section-scope-note' in src, "the empty-section scope note is gone"
    assert 'does not list this organization' in src, (
        "the note no longer explains what an empty table means")


def test_the_note_is_shown_only_when_the_table_is_genuinely_empty():
    """⚠ The two views legitimately differ now: `orgsection` shows the note when a
    section is empty, while `orgprojectsection` first tries the alternative capital
    projects and only falls back to the note. So assert the PROPERTY — the note is
    reachable only after a row-count check — not one spelling of it."""
    for v in SECTION_VIEWS:
        src = open(os.path.join(ROOT, 'app/resources/views', v), encoding='utf-8').read()
        show = src.index("$('#section-scope-note').show()")
        gate = min([m.start() for m in re.finditer(r'rows\.length', src)] or [len(src)])
        assert gate < show, f"{v}: the scope note is not gated on a row count"


def _assert_gated(path):
    """⚠ A note on a POPULATED section becomes wallpaper and stops meaning
    anything — the "worth consolidating?" badge landed on 26 of 46 rows for
    exactly this reason. It must be gated on a zero-length result."""
    src = open(path, encoding='utf-8').read()
    assert re.search(r'rows\.length\s*===?\s*0', src), \
        "the note is no longer gated on an empty result set"
    assert "style=\"display:none\"" in src or "style='display:none'" in src, \
        "the note renders by default instead of only on an empty table"


def test_the_controller_passes_every_key_the_section_view_reads():
    """⚠⚠ THE #247 SEAM. That PR served three payload keys, the Blade read them,
    every unit guard passed — and the controller's view-data array never passed
    them, so `$x ?? []` degraded politely and the section did not render. Only
    fetching the page found it. This is that guard for this view.
    """
    view = open(VIEW, encoding='utf-8').read()
    ctrl = open(CTRL, encoding='utf-8').read()
    # every $var the view interpolates through Blade's raw/escaped syntax
    read = set(re.findall(r'\{!!\s*\$([a-zA-Z_]\w*)', view))
    read |= set(re.findall(r'\{\{\s*\$([a-zA-Z_]\w*)', view))
    # ⚠ Names the VIEW binds itself are not controller keys — @foreach vars,
    # @php assignments. DERIVED from the view rather than a hardcoded ignore
    # list, which would drift the moment someone adds a loop: this guard flagged
    # `code` and `h` on its first run, both `@foreach ... as $h=>$f` variables,
    # and a guard with false positives is one people switch off.
    bound = set()
    for m in re.finditer(r'@foreach\s*\(.*?\bas\s+\$(\w+)\s*=>\s*\$(\w+)', view):
        bound |= {m.group(1), m.group(2)}
    for m in re.finditer(r'@foreach\s*\(.*?\bas\s+\$(\w+)\s*\)', view):
        bound.add(m.group(1))
    bound |= set(re.findall(r'\$(\w+)\s*=', view))          # @php assignments
    missing = [n for n in sorted(read - bound)
               if f"'{n}'" not in ctrl and f'"{n}"' not in ctrl]
    assert not missing, (
        f"orgsection.blade.php reads these but Organizations.php never passes them: "
        f"{missing}. They would be undefined at render.")


def test_the_coverage_endpoint_counts_the_datasets_own_universe():
    """⚠ DISTINCT mapped orgs, never a hardcoded list — a literal would go stale
    the moment an agency is added and would then misdescribe the dataset."""
    src = open(MAIN, encoding='utf-8').read()
    body = _py_function_source(src, 'get_section_org_coverage')
    assert 'count(DISTINCT "wegov-org-id")' in body, \
        "the coverage endpoint no longer measures the dataset's own universe"
    assert '_safe_table(' in body, "the table name is interpolated unvalidated"


# ---------------------------------------------------------------------------
# The other lens: work the org does as a VENDOR.
SEED = os.path.join(ROOT, 'api/seed/org_contract_vendors.csv')


def _load_ocv():
    """⚠ BY PATH — conftest replaces the `modules` package with a MagicMock."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        '_ocv_test', os.path.join(ROOT, 'api/modules/orgcontractvendors.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_seed_ships_and_maps_exact_vendor_names():
    m = _load_ocv()
    assert m.vendor_names_for(170010998) == ['NEW YORK CITY ECONOMIC DEVELOPMENT CORPORATION'], \
        "the EDC mapping is gone or is no longer the exact contracts vendor_name"
    assert m.vendor_names_for(170010846) == [], "an unmapped org must resolve to nothing"
    assert m.vendor_names_for(None) == []
    assert not any(v.startswith('#') for vs in m.rows().values() for v in vs), \
        "the comment header parsed as a data row"


def test_the_lookup_is_exact_and_never_a_substring():
    """⚠⚠ `%ECONOMIC DEVELOPMENT CORP%` matches SEVEN organizations — Women's
    Housing (53 contracts), South Bronx Overall (43), Staten Island (14), Queens
    (12), Central Brooklyn (9), Bronx Overall (8) — and NYCEDC is only 24 of those
    163 rows. A substring here would attribute another nonprofit's $31M to EDC."""
    src = open(MAIN, encoding='utf-8').read()
    body = _py_function_source(src, 'get_org_contract_work')
    assert 'ILIKE' not in body and "'%' ||" not in body, \
        "the contract-work lookup uses a pattern match; it must be exact"
    assert '= ANY($1)' in body, "the exact vendor-name match is gone"


def test_the_contract_work_query_dedupes_to_contract_grain():
    """⚠⚠ `contracts` holds ONE ROW PER AMENDMENT. Not deduping counts amendments
    as contracts — it has shipped twice here (#262, #278) — and I made the same
    mistake reporting EDC as 24 contracts / $12.3B before deduping. The true
    figures are 12 / $11,183.9M. The key is `coalesce(contract_id, ctid)`:
    contract_id ALONE collapses every NULL-id row into one."""
    src = open(MAIN, encoding='utf-8').read()
    body = _py_function_source(src, 'get_org_contract_work')
    assert 'DISTINCT ON' in body, "the contract-work query no longer dedupes"
    assert "coalesce(c.contract_id, 'row:' || c.ctid::text)" in body, \
        "the dedup key is not the established coalesce(contract_id, ctid) spelling"


def test_each_view_offers_its_own_alternative_only_when_empty():
    """An ALTERNATIVE, not an addition — beside a populated table it would imply the
    two are the same kind of thing.

    ⚠ The alternatives differ BY VIEW and that is deliberate: the projects page
    shows CAPITAL PROJECTS carried on another agency's budget (same columns, same
    /p/ links, which is what makes it read as the normal table), while a generic
    section falls back to the org's contract work.
    """
    alt = {
        'orgsection.blade.php': ('org-contract-work', 'contractWorkUrl'),
        'orgprojectsection.blade.php': ('alt-projects-note', 'altProjectsUrl'),
    }
    for v, (block, url_key) in alt.items():
        src = open(os.path.join(ROOT, 'app/resources/views', v), encoding='utf-8').read()
        assert block in src, f"{v}: the alternative block ({block}) is gone"
        gate = min([m.start() for m in re.finditer(r'rows\.length', src)] or [len(src)])
        assert src.index(url_key) > gate, \
            f"{v}: the alternative is fetched outside the empty-result branch"


# ---------------------------------------------------------------------------
# Capital projects carried on ANOTHER agency's budget.
PROJECT_VIEW = os.path.join(ROOT, 'app/resources/views/orgprojectsection.blade.php')


def test_a_failed_request_is_never_reported_as_missing_coverage():
    """⚠⚠ `fapireq` returns {data: [], error, status} on failure — its own comment
    says "A FAILED REQUEST IS NOT AN EMPTY RESULT". The first version of the scope
    note ignored that, so a 500 or a 429 would have rendered "this dataset does not
    list this organization": a confident claim about coverage produced by a broken
    request. That is the defect this whole area exists to remove, committed by the
    fix for it."""
    for v in SECTION_VIEWS:
        src = open(os.path.join(ROOT, 'app/resources/views', v), encoding='utf-8').read()
        assert 'payload.error' in src, (
            f"{v}: the note is not guarded against a FAILED request, so an error "
            f"would be reported as the dataset not covering this organization")


def test_the_capital_project_token_match_uses_a_word_boundary():
    """⚠⚠ `%EDC%` matches **INCLUDEDCITY** (INCLUDED + CITY run together in a DDC
    scope text): 26 projects by substring against 15 with `\\mEDC\\M`. A
    three-letter token is exactly the case this repo keeps paying for."""
    src = open(MAIN, encoding='utf-8').read()
    body = _py_function_source(src, 'get_org_capital_projects_via_text')
    assert "r'\\m'" in body and "r'\\M'" in body, \
        "the capital-project token match lost its word boundaries"
    assert 'ILIKE' not in body, "the match degraded to a LIKE"


def test_the_token_is_validated_alphanumeric_before_reaching_a_regex():
    """It is interpolated into a Postgres regex, so a metacharacter would either
    break the query or silently widen it to match far more than intended."""
    src = open(os.path.join(ROOT, 'api/modules/orgprojecttokens.py'), encoding='utf-8').read()
    assert '.isalnum()' in src, "a token carrying a regex metacharacter would be accepted"


def test_the_alternative_projects_table_is_gated_on_having_rows():
    """It replaces the empty table, so it must never show with nothing in it — and
    never beside a populated one."""
    src = open(PROJECT_VIEW, encoding='utf-8').read()
    assert 'alt-projects-note' in src, "the contracted-out note is gone"
    assert 'arows.length' in src, "the alternative table is not gated on having rows"
    i = src.index('arows.length')
    assert src.index("$('#alt-projects-note').show()") > i, \
        "the note shows before the row check"


def test_the_note_states_that_the_match_is_text_evidence():
    """⚠ It is the plan description NAMING the org — evidence of involvement, not
    a record of who holds the contract. The Plan publishes no contractor field, and
    the page must not imply otherwise."""
    src = open(PROJECT_VIEW, encoding='utf-8').read()
    assert 'names this organization' in src and 'no contractor field' in src, \
        "the note no longer discloses that the link is text evidence"


def test_the_projects_tab_shows_the_current_plan_not_only_the_retired_series():
    """⚠⚠ `capitalprojectsdollarscomp` was RETIRED BY NYC IN OCTOBER 2023 —
    is_active=false, no socrata_id, never ingested, newest PUB_DATE 20231026 — so
    every agency's Capital Projects tab showed ~3-year-old data with nothing
    saying so. The live successor (`capitalprojectslist`, ccpversion fisa_2026,
    ingested 2026-08-25) is bigger: 12,905 projects against 8,740, 28 orgs
    against 25.

    ⚠ It is ADDED, not swapped, and that is measured rather than cautious: the
    live table has NO LAT/LNG (the tab's map), no BORO, no SCOPE_TEXT, no
    BUDG_ORIG/CURR/DIFF and no START/END/DURATION _ORIG/_DIFF. Swapping would have
    silently deleted the map and five columns from 25 agency pages, and no other
    current table carries them either (capitalcommitmentplan,
    capitalcommitmentactuals and capitalstrategy were all checked).
    """
    src = open(PROJECT_VIEW, encoding='utf-8').read()
    assert 'current-plan-block' in src, "the current plan table is gone"
    assert 'currentPlanUrl' in src, "the current plan is not fetched"
    ctrl = open(CTRL, encoding='utf-8').read()
    assert "'currentPlanUrl'" in ctrl, "the controller does not pass currentPlanUrl"

    main = open(MAIN, encoding='utf-8').read()
    body = _py_function_source(main, 'get_org_current_capital_plan')
    assert 'capitalprojectslist' in body, "the endpoint no longer reads the live table"
    assert 'plannedcommit_total' in body, (
        "the headline money column is gone — measured, plannedcommit_total is the "
        "best populated (9,213 of 12,929 rows > 0, vs commit_total 5,158)")


def test_the_current_plan_table_counts_before_it_caps():
    """⚠ A truncated list presented as complete is a defect this repo has shipped
    more than once (by_vendor showed 25 of 88 under a heading implying all)."""
    src = open(PROJECT_VIEW, encoding='utf-8').read()
    assert 'CCP_CAP' in src, "the row cap is gone"
    assert 'ccp-capped' in src, "the cap is applied without being disclosed"
    assert 'rows.length > CCP_CAP' in src, "the disclosure is not gated on actually capping"


def test_the_retired_series_is_labelled_on_the_page():
    """The older table stays for its map and columns, but a reader must not take
    it for current."""
    src = open(PROJECT_VIEW, encoding='utf-8').read()
    assert 'October 2023' in src, "the page no longer says when the older series ended"


def _js_function_body(src, name):
    """Return the body of `var <name> = function (...) { ... }` by BALANCING
    BRACES — not by regex to the next `}`.

    ⚠ Scoping a guard to the statement rather than the word is a rule this repo
    has paid for at least four times (a guard satisfied by a print line beside
    the deleted statement, one satisfied by a different call site, one by the
    docstring explaining why the thing matters). A file-wide scan here would be
    actively wrong: this page legitimately calls `toFinShortK(v, 1000)` for a
    series that IS in thousands.
    """
    # ⚠ Both declaration forms are used on this page (`var x = function` and
    # `function x(...)`), and a helper that knows only one raises ValueError —
    # which reads as a missing feature rather than a blind guard.
    for key in ('var %s = function' % name, 'function %s(' % name):
        if key in src:
            i = src.index(key)
            break
    else:
        raise AssertionError('no JS function named %s()' % name)
    j = src.index('{', i)
    depth, k = 0, j
    while k < len(src):
        if src[k] == '{':
            depth += 1
        elif src[k] == '}':
            depth -= 1
            if depth == 0:
                return src[j:k + 1]
        k += 1
    raise AssertionError('unbalanced braces in %s()' % name)


def test_the_current_plan_renders_the_plans_money_as_DOLLARS_not_thousands():
    """⚠⚠ A UNITS ERROR IS OFF BY 1000x AND STILL LOOKS LIKE A NUMBER.

    The first version of this block divided by 1000 on the belief that the
    Capital Commitment Plan publishes thousands, and shipped Parks' plan as
    ``$9,799,856M`` — $9.8 TRILLION — beside a per-project ``$652,594M``.
    Both are plausible-looking strings, and every shape-checking test passed.

    Measured three ways, and the thousands reading makes all three impossible:
    one lump sum is 652594000 ($652.6M); Parks totals 9,818,811,000 ($9.82B);
    citywide planned commitment totals 201,809,204,000 ($201.8B) against NYC's
    ~$185-190B Ten-Year Capital Strategy.

    A guard cannot know a unit. It can stop the scaling silently coming back, so
    the decision is pinned at its ONE site.
    """
    body = _js_function_body(open(PROJECT_VIEW, encoding='utf-8').read(), 'money')
    assert re.search(r'toFinShortK\s*\(\s*n\s*,\s*1\s*\)', body), (
        "the current plan must format money with toFinShortK(n, 1) — the site's "
        "own formatter, multiplier 1, because the Plan publishes DOLLARS")
    scaled = re.findall(r'[/*]\s*1000\b|1e3\b', body)
    assert not scaled, (
        'the current-plan money helper must not scale the Plan\'s values; '
        'found %r' % (scaled,))


def test_a_literal_zero_in_the_plan_renders_as_money_not_as_missing_data():
    """⚠ AN EM DASH MEANS *NO DATA*. A literal 0 is the City's own claim.

    EDC's projects are future-dated lump sums starting 2026-2035, so they
    genuinely carry no commitment yet — that zero is a fact the City published,
    and an em dash asserts the opposite, that we do not know. This is the mirror
    of the crol rule (an empty string must NOT render ``$0.00``, which would be a
    claim the City did not make): the test is whether a value EXISTS, never
    whether it is large. My first draft returned the dash for both.
    """
    body = _js_function_body(open(PROJECT_VIEW, encoding='utf-8').read(), 'money')
    assert re.search(r"n\s*===?\s*0[^;]*\)\s*\{\s*return\s*'\$0'", body), (
        'a literal 0 must render as $0, not as an em dash')
    assert re.search(r"!\s*isFinite\s*\(\s*n\s*\)\s*\)\s*\{\s*return\s*'..u2014'"
                     .replace('..u2014', r'\\u2014'), body), (
        'the em dash must be returned only when the value is not a number')


def test_the_alternative_projects_are_a_UNION_of_both_plans_never_one():
    """⚠⚠ A SWAP WOULD HAVE SILENTLY DROPPED HALF THE PROJECTS.

    Measured for NYCEDC: the current plan names 10 projects, the retired series
    15, and only **5** are in both — union 20. So re-pointing this query at the
    live table alone hides 10, and leaving it on the retired table alone hides 5.
    Neither source is a superset, which is precisely why the answer is a union
    and not a migration.

    This is the same reasoning as #360's decision to ADD the current plan rather
    than swap it in, and it is worth pinning because "just point it at the new
    table" is the obvious-looking change that loses data quietly.
    """
    body = _py_function_source(open(MAIN, encoding='utf-8').read(),
                               'get_org_capital_projects_via_text')
    assert 'capitalprojectslist' in body, "the union no longer reads the CURRENT plan"
    assert 'capitalprojectsdollarscomp' in body, (
        "the union no longer reads the retired series — 10 of NYCEDC's 20 "
        "projects appear only there")
    assert 'FULL OUTER JOIN' in body, (
        "the two plans must be FULL OUTER JOINed; an inner or left join drops "
        "the rows that exist on only one side, which is most of them")


def test_the_retired_series_is_deduped_to_one_row_per_project():
    """⚠ The retired series republishes every project at each of its 14
    publication dates — 108 rows for NYCEDC's 15 projects. Without a dedup the
    page counts publication events as projects, which is the amendment-grain
    defect (#262/#278) in a different table."""
    body = _py_function_source(open(MAIN, encoding='utf-8').read(),
                               'get_org_capital_projects_via_text')
    assert 'DISTINCT ON (btrim("PROJECT_ID"))' in body, (
        "the retired side must dedupe to one row per project")
    assert re.search(r'ORDER BY btrim\("PROJECT_ID"\), "PUB_DATE" DESC', body), (
        "the surviving row must be the NEWEST publication; PUB_DATE is numeric "
        "so DESC is chronological")


def test_the_two_money_columns_are_normalised_once_and_never_added():
    """⚠⚠ DIFFERENT MEASURES *AND* DIFFERENT UNITS.

    `plannedcommit_total` is a planned commitment in DOLLARS; `BUDG_CURR` is a
    current budget in THOUSANDS (the retired dataset's own description says so,
    and the legacy renderer multiplies by 1000). Carrying one unit across to the
    other is exactly the 1000x defect this page shipped in #360 and fixed in
    #361, so the conversion happens ONCE, in SQL, and the keys are suffixed
    `_usd` so nothing downstream re-scales them.

    They are also never summed: a planned commitment is not a budget, the same
    call #261 settled for a ceiling against spend.
    """
    body = _py_function_source(open(MAIN, encoding='utf-8').read(),
                               'get_org_capital_projects_via_text')
    assert re.search(r'btrim\("BUDG_CURR"\)::numeric \* 1000', body), (
        "the retired series' thousands are no longer converted to dollars")
    assert re.search(r'"BUDG_ORIG" \* 1000', body), (
        "original cost is no longer converted from thousands to dollars")
    for key in ('planned_commit_usd', 'orig_cost_usd', 'budget_usd'):
        assert key in body, (
            "%s must be suffixed _usd so it resists being re-scaled" % key)

    view = open(PROJECT_VIEW, encoding='utf-8').read()
    alt = _js_function_body(view, 'altMoney')
    assert not re.findall(r'[/*]\s*1000\b', alt), (
        "the view must not re-scale money the endpoint already normalised")


def test_the_alternative_count_cannot_disagree_with_the_rows_it_describes():
    """⚠⚠ THE NOTE SAID 15 WHILE 9 ROWS SHOWED BENEATH IT.

    The old count was distinct projects across all 14 publication dates, while
    the table it pointed at was the retired series' DataTable filtering to the
    newest publication. Two independent computations of one number, twenty pixels
    apart — the defect this repo has now paid for on the licences page, the
    renewal calendar and here.

    The count is now `len(out)` by construction, over the same list the table
    renders, so the two cannot drift.
    """
    body = _py_function_source(open(MAIN, encoding='utf-8').read(),
                               'get_org_capital_projects_via_text')
    assert re.search(r'"projects":\s*len\(out\)', body), (
        "the count must be derived from the rows served, not computed separately")

    view = open(PROJECT_VIEW, encoding='utf-8').read()
    assert 'renderAltUnion(arows)' in view, (
        "the union must render the rows it counted")
    assert "$('#myTable_wrapper').hide()" in view, (
        "the retired series' own table must be hidden when the union renders, or "
        "the page shows two different answers at once")


def test_the_agency_column_never_renders_the_numeric_managing_agency_code():
    """⚠ `capitalprojectslist.magency` IS A CODE, NOT A NAME — a bare number on
    all 12,929 rows, while `magencyacro` is populated on every one. Reading the
    plausibly-named column put **"126"** in the Agency column of a $52M project on
    a live page. A column's name is not its contract; the first version of this
    query trusted it."""
    body = _py_function_source(open(MAIN, encoding='utf-8').read(),
                               'get_org_capital_projects_via_text')
    assert 'magencyacro' in body, "the agency name must come from the acronym column"
    assert not re.search(r"nullif\(magency\b|coalesce\(magency\b|\bmagency\s+AS\b", body), (
        "the numeric managing-agency code must not be rendered as an agency name")


def test_the_stat_tiles_are_populated_for_a_text_matched_org():
    """⚠⚠ EIGHT BLANK TILES, TWO INDEPENDENT REASONS, NEITHER VISIBLE.

    Every `pstats-*` endpoint reads `capitalprojectsdollarscomp WHERE
    "wegov-org-id" = $1 AND "PUB_DATE" = $2`. An org with no capital budget line
    of its own has zero rows under its id — AND the publication-date selector
    those tiles read their pubdate from is populated FROM that same empty table,
    so the pubdate is the empty string too. The tiles rendered blank, which reads
    as "no data" rather than "asked the wrong question".
    """
    main = open(MAIN, encoding='utf-8').read()
    body = _py_function_source(main, 'organization_projects_union_stats')
    assert 'orgprojecttokens' in body, "the union stats must use the same curated token"
    assert re.search(r"\\\\m' \+ token", body) or "r'\\m' + token" in body, (
        "the union stats must use the word-boundary match, not a substring")
    for key in ('orig_cost', 'curr_cost', 'over_budg_am', 'over_budg_no',
                'long_no', 'late_start_no', 'late_end_no'):
        assert key in body, "the union stats no longer serve %s" % key

    view = open(PROJECT_VIEW, encoding='utf-8').read()
    assert 'loadUnionStats(arows.length)' in view, (
        "the tiles are not filled when the union renders")
    ctrl = open(CTRL, encoding='utf-8').read()
    assert "'unionStatsUrl'" in ctrl, "the controller does not pass unionStatsUrl"


def test_the_union_stats_do_not_recompute_the_project_count():
    """⚠ ONE NUMBER, ONE OWNER. `projects_no` is the length of the union list the
    page just rendered. Computing it again server-side is exactly how the note
    came to say 15 above a table of 9 — two independent computations of one
    number, which this repo has now paid for three times."""
    body = _code_only(_py_function_source(open(MAIN, encoding='utf-8').read(),
                                          'organization_projects_union_stats'))
    assert 'projects_no' not in body, (
        "the stats endpoint must not compute the project count a second time")
    view = open(PROJECT_VIEW, encoding='utf-8').read()
    assert re.search(r"\$\('#projects_no'\)\.text\(unionRowCount", view), (
        "the tile must be filled from the rendered union list")


def test_the_stat_tiles_disclose_their_smaller_denominator():
    """⚠⚠ SEVEN OF THE EIGHT TILES COVER FEWER PROJECTS THAN THE COUNT BESIDE
    THEM. Budget and schedule variance exist only in the retired series — the
    current plan publishes no original-vs-current budget and no start/end
    variance — so for NYCEDC they describe 15 of 20. Unstated, a $397.8M
    "over budget" figure reads as covering every row in the table above it.

    This is the same discipline as counting before you cap: a partial figure
    presented without its denominator is a claim about the whole.
    """
    # ⚠ _code_only, because this function's own docstring names `budget_basis`
    # while explaining why it exists — the guard passed against a reintroduced bug
    # until this was added, which is the ninth time in this repo.
    body = _code_only(_py_function_source(open(MAIN, encoding='utf-8').read(),
                                          'organization_projects_union_stats'))
    assert 'budget_basis' in body, "the endpoint no longer reports its denominator"
    view = open(PROJECT_VIEW, encoding='utf-8').read()
    assert 'stats-basis' in view, "the denominator is no longer stated on the page"
    assert re.search(r"r\.budget_basis\s*<\s*unionRowCount", view), (
        "the disclosure must be gated on the denominators actually differing")


def test_nothing_but_loadunionstats_writes_the_union_figures():
    """⚠⚠ RE-EXPRESSED, NOT RELAXED — and this guard FAILED on the change that
    made it necessary, which is it doing its job.

    It used to require `if (unionStatsActive) { return; }` inside
    `loadFinStat()`'s response callback: that loop issued eight ASYNC requests,
    so suppressing only the INVOCATION left a reply already in flight free to
    land afterwards and blank the union's tiles with '-'. The flag had to be
    checked where the value was WRITTEN.

    That loop is now deleted — the capital tiles are server-rendered from the
    spine — so the flag had no reader and was removed with it. The PROPERTY it
    protected is unchanged and is asserted here directly at one level up: no
    function other than `loadUnionStats` may write these ids at all. That is
    strictly stronger than the flag (it forbids the second writer existing
    rather than requiring it to check a flag) and it does not depend on the
    mechanism, so it survives the next rewrite of how the tiles are filled.
    """
    view = open(PROJECT_VIEW, encoding='utf-8').read()
    view = re.sub(r'\{\{--.*?--\}\}', '', view, flags=re.S)
    view = re.sub(r'^\s*//.*$', '', view, flags=re.M)
    tiles = ('projects_no', 'orig_cost', 'curr_cost', 'long_no',
             'over_budg_no', 'late_start_no', 'late_end_no')
    union = _js_function_body(view, 'loadUnionStats')
    outside = view.replace(union, '')
    # ⚠ THE SELECTOR STRING, not `$('#id')`. loadUnionStats addresses six of the
    # seven through a `forEach` over `[['#orig_cost', r.orig_cost], …]`, so a
    # scan for the jQuery call form found only `#projects_no` and reported the
    # other six as unfilled — a guard measuring a different system than the one
    # it guards. Caught on the unmutated file.
    offenders = sorted({t for t in tiles if ("'#%s'" % t) in outside})
    assert not offenders, (
        'a second writer of the union figures is back outside loadUnionStats — '
        'a late reply from it lands on top of the union and there is no flag '
        'left to stop it: %s' % offenders)
    for t in tiles:
        assert ("'#%s'" % t) in union, (
            'loadUnionStats no longer fills %s, so that tile stays at the em '
            'dash for a text-matched org' % t)


def test_the_publication_date_selector_is_hidden_when_it_can_do_nothing():
    """⚠ It filters the retired series' table, which the union hides — and it is
    populated FROM that table, so it holds nothing but its own placeholder. A
    control that cannot do anything is worse than no control: it invites a reader
    to think the view is filtered."""
    view = open(PROJECT_VIEW, encoding='utf-8').read()
    # ⚠ The ROW, not just the select: the label "Publication Date" lives in a
    # SEPARATE <th>, so hiding only #pub_date_filter leaves a caption over an
    # empty box — a label for a control that is not there.
    assert re.search(r"\$\('#pub_date_row'\)\.hide\(\)", view), (
        "the publication-date ROW (label + selector) is no longer hidden")
    assert 'id="pub_date_row"' in view, "the row lost the id the hide depends on"


def test_the_stats_panel_opens_by_default_for_a_text_matched_org():
    """On this page the stat tiles are the most substantive thing above the
    table, and a reader has no reason to guess a collapsed panel is there. Scoped
    to the union branch: a normal agency page keeps the owner's existing
    collapsed default.

    ⚠ The toggle button's own state must move with the panel, or Bootstrap reads
    the first click as "already closed" and nothing happens.
    """
    view = open(PROJECT_VIEW, encoding='utf-8').read()
    assert re.search(r"\$\('#stats_collapse'\)\.addClass\('show'\)", view), (
        "the stats panel no longer opens by default")
    assert re.search(r"aria-expanded['\"]\s*,\s*['\"]true", view), (
        "the toggle button's state is not updated, so its first click is a no-op")


def test_the_project_core_query_cannot_have_its_org_id_shadowed_by_the_join():
    """⚠⚠ 2,433 OF 8,740 PROJECT PAGES (28%) COULD NEVER LOAD.

    `SELECT t1.*, t2.*` across a LEFT JOIN emits `wegov-org-id` and
    `wegov-org-name` TWICE — those are the only two columns the tables share —
    and `dict(record)` keeps the LAST. So for any project with no row in
    `capitalprojectslist`, the unmatched side's NULL silently overwrote the real
    org id.

    That id is what the project page resolves its organization from, so
    `fetchOrg()` aborted to the "Databook is briefly unavailable" view: a
    PERMANENT data condition wearing the costume of a transient outage, on a page
    that auto-retries forever. The user found it by clicking one link.

    ⚠ The guard asserts BOTH occurrences are fixed — the endpoint runs the same
    SELECT twice, once for the exact id and once for the stripped maprojid
    prefix, and fixing only the first leaves every map-popup link broken.
    """
    body = _code_only(_py_function_source(open(MAIN, encoding='utf-8').read(),
                                          'get_capital_project_core'))
    # ⚠ The SQL lives inside a double-quoted Python string, so the FILE BYTES
    # carry `\"` around every identifier. A regex written against the SQL as it
    # reads in a psql session matches nothing here and the guard passes on an
    # unfixed file — a scanner looking at the wrong representation, which is the
    # zero-files scanner in yet another costume. `Q` absorbs either form.
    Q = r'\\?"'
    stars = body.count('SELECT t1.*, t2.*')
    assert stars >= 1, "the core query no longer selects from both tables"
    fixes = len(re.findall(
        r'coalesce\(t2\.' + Q + r'wegov-org-id' + Q + r', t1\.' + Q +
        r'wegov-org-id' + Q + r'::text\)', body))
    assert fixes == stars, (
        "every `SELECT t1.*, t2.*` must re-emit the org id after the stars; "
        "found %d star selects but %d coalesces" % (stars, fixes))
    assert re.search(r'coalesce\(t2\.' + Q + r'wegov-org-name' + Q + r', t1\.' + Q +
                     r'wegov-org-name' + Q + r'\)', body), (
        "the org NAME is shadowed by the same mechanism and needs the same fix")


def test_the_project_core_fix_is_conservative_about_which_table_wins():
    """⚠⚠ t2 FIRST, AND IT IS THE MEASURED ANSWER, NOT JUST THE SAFE ONE.

    The two tables disagree about which agency runs a project on 2,786 of 59,652
    joining rows (525 distinct projects), and every disagreeing row disagrees on
    the agency NAME as well — so it was never an enrichment bug.
    `capitalprojectslist` (2026) is correct:

      · at the newest 2023 publication the disagreement is 232, not 525
      · agreement rises as the 2023 data gets newer: 5,792 of 6,323 at its oldest
        publication, 6,091 at its newest
      · of the 319 projects whose agency changed within the 2023 series' OWN
        publications, 307 (96%) ended up matching the 2026 plan; 8 moved away

    The residual is reassignment to construction-delivery bodies — DDC 110+,
    Brooklyn Navy Yard 48, Governors Island 19 — and DDC's managed portfolio
    grows 1,510 -> 2,202 between the datasets. Reversing this coalesce would
    re-attribute 525 project pages to the STALER answer.
    """
    body = _code_only(_py_function_source(open(MAIN, encoding='utf-8').read(),
                                          'get_capital_project_core'))
    assert not re.search(r'coalesce\(t1\.\\?"wegov-org-id', body), (
        "t1 must not win the coalesce — that re-attributes 2,786 pages")
    # the cast is required: t1 is numeric, t2 is text, and an uncast coalesce
    # raises `COALESCE types numeric and text cannot be matched` and 500s.
    assert '::text' in body, "the numeric->text cast is required or the query 500s"


def test_the_agency_column_is_a_normalized_org_name_linked_to_its_capital_page():
    """The plan's own agency strings are neither normalized nor consistent:
    `DEPT OF  SMALL BUSINESS SERVICES` (double space) from the retired series and
    a bare `SBS` from the 2026 plan name the same body. Resolving the org id
    through `wegov_orgs` gives one canonical name and, more usefully, a link to
    that agency's own capital-projects page.

    ⚠ The org id is resolved 2026-FIRST, which is the opposite of the raw display
    string beside it and deliberate: #366 measured `capitalprojectslist` as the
    correct side. A raw string is a label; an id is a claim about who runs the
    project AND a link a reader will follow, so it takes the authoritative source.
    """
    body = _code_only(_py_function_source(open(MAIN, encoding='utf-8').read(),
                                          'get_org_capital_projects_via_text'))
    assert 'LEFT JOIN wegov_orgs' in body, "the agency is no longer resolved to an org"
    assert 'coalesce(o.display_name, o.name)' in body, (
        "the normalized name must prefer display_name, as the rest of the site does")
    assert re.search(r"coalesce\(nullif\(c\.org_id, ''\), r\.org_id\)::int", body), (
        "the org id must resolve 2026-first (#366), and via ::int on the joined key")
    # ⚠ The list table's column is TEXT: without the regex guard one non-numeric
    # value aborts the whole query, so every row loses its agency at once.
    assert re.search(r"coalesce\(nullif\(c\.org_id, ''\), r\.org_id\) ~ '\^\[0-9\]\+\$'", body), (
        "the ::int cast is unguarded — one bad value would abort the query")


def test_an_unresolved_agency_still_renders_its_raw_name_unlinked():
    """⚠⚠ A RESOLUTION MISS MUST NOT BECOME MISSING DATA. If the org id does not
    resolve, the plan's own agency string still renders — unlinked. Dropping the
    cell would read as "the City did not say which agency", which is the failure
    this page has already made twice (a blank agency and an em dash for a real
    zero). The raw string is therefore still served alongside the resolved one."""
    body = _code_only(_py_function_source(open(MAIN, encoding='utf-8').read(),
                                          'get_org_capital_projects_via_text'))
    assert re.search(r"coalesce\(nullif\(r\.agency, ''\), c\.agency\)\s+AS agency", body), (
        "the raw agency string is no longer served as a fallback")
    cell = _js_function_body(open(PROJECT_VIEW, encoding='utf-8').read(), 'agencyCell')
    assert re.search(r"if \(!id \|\| !nm\) \{ return esc\(r\.agency\); \}", cell), (
        "the view no longer falls back to the raw agency string")
    assert '/projects' in cell, "the link no longer points at the agency's capital page"


def test_the_cost_columns_reconcile_to_the_stat_tiles():
    """The visible money columns are the 2023 series' ORIGINAL and CURRENT cost —
    the same `BUDG_ORIG` and `BUDG_CURR` the stat tiles above them total — so a
    reader can add a column and land on the tile. That only holds if the two
    endpoints guard the values identically.

    ⚠ The union's guard was `^[0-9.]+$` while the stats endpoint's was
    `^-?[0-9.]+$`, so a negative value would have been dropped from the column and
    counted in the tile. A no-op today, and measured rather than assumed: 0
    negative BUDG_CURR and 0 negative BUDG_ORIG across all 72,437 rows. Aligned
    anyway, because "currently equivalent" is not a property anything enforces.
    """
    src = open(MAIN, encoding='utf-8').read()
    union = _py_function_source(src, 'get_org_capital_projects_via_text')
    stats = _py_function_source(src, 'organization_projects_union_stats')
    for body, who in ((union, 'the union'), (stats, 'the stat tiles')):
        assert re.search(r'btrim\("BUDG_CURR"\) ~ \'\^-\?\[0-9\.\]\+\$\'', body) or \
               re.search(r'btrim\(coalesce\("BUDG_CURR", \'\'\)\) ~ \'\^-\?\[0-9\.\]\+\$\'', body), (
            "%s no longer guards BUDG_CURR the same way as the other" % who)


def test_rows_with_no_cost_figure_are_counted_and_explained():
    """⚠⚠ A BLANK MONEY CELL READS AS "NO MONEY". Projects that appear only in the
    2026 plan carry neither cost figure — that plan publishes no
    original-vs-current comparison — so both columns are empty for them. For
    NYCEDC that is 5 of 20 rows holding $71.5M of planned commitment, which the
    cost columns cannot show at all.

    The page therefore says how many rows they are and what they are worth,
    COUNTED FROM THE RENDERED ROWS rather than typed — the same rule that keeps
    the note's project count from drifting away from the table beneath it.
    """
    view = open(PROJECT_VIEW, encoding='utf-8').read()
    assert 'alt-nocost-note' in view, "the blank-cost rows are no longer explained"
    assert re.search(r"nocost\.length \+ ' of these ' \+ rows\.length", view), (
        "the count must be derived from the rendered rows, not typed")
    assert 'planned_commit_usd' in view, (
        "the planned commitment those rows DO carry must still be reported, or the "
        "swap silently deletes $71.5M from the page")


def test_the_money_note_does_not_still_claim_the_columns_are_incomparable():
    """⚠ A STALE DISCLOSURE IS THE TYPED-FIGURE DEFECT IN PROSE. The note used to
    say the two money columns came from DIFFERENT plans and must never be added.
    Both now come from the 2023 series and the gap between them is budget growth,
    so that sentence became false the moment the columns changed — exactly the
    trap #288's cap sentence documented."""
    view = open(PROJECT_VIEW, encoding='utf-8').read()
    assert 'come from different plans' not in view, (
        "the note still describes the previous two columns")
    assert 'budget growth' in view, (
        "the note no longer says what the difference between the columns means")


def test_the_union_tables_header_and_row_cell_counts_agree():
    """⚠⚠ A HEADER/CELL MISMATCH SILENTLY MISALIGNS EVERY COLUMN. The row HTML is
    built by string concatenation, so dropping a `<td>` without dropping its
    `<th>` shifts the whole table one place left — money under "In plan", dates
    under "Original cost" — and nothing errors. Removing the Category column
    touched both halves, which is exactly when this can go wrong.
    """
    src = open(PROJECT_VIEW, encoding='utf-8').read()
    i = src.index('function renderAltUnion')
    j = src.index("$('#alt-union-body').html(html)", i)
    cells = src[i:j].count('<td')
    header = re.search(r'<table id="alt-union-table".*?</thead>', src, re.S)
    assert header, "the union table's header is gone"
    ths = header.group(0).count('<th ')
    assert cells == ths, (
        "the union table has %d header cells and %d row cells — every column "
        "after the mismatch renders under the wrong heading" % (ths, cells))


def test_the_schedule_dates_come_from_one_side_only_and_never_coalesce():
    """⚠⚠ THE 2026 PLAN'S DATES ARE A DIFFERENT MEASURE, NOT A FALLBACK.
    `maxdate` falls on 06/01 for 12,408 of 12,929 rows — fiscal-year plan
    boundaries — where the 2023 series' `START_CURR` is on 06/01 only 16% of the
    time across 12 distinct month-days. They agree on an exact start for **51 of
    6,323** overlapping projects (0.8%). Coalescing them would put two different
    measures in one column, which is the defect the money columns were split to
    avoid, and I proposed exactly that before measuring it.

    ⚠ 1899/1900 is a spreadsheet-epoch sentinel — 703 rows in a single spike, one
    of them NYCEDC's GI-EDC — and is suppressed at the endpoint so there is one
    owner for the rule. Deliberately NOT a wider cutoff: the 1930-1939 cluster
    (138 rows) and the isolated 1983/86/88 dates may be real.
    """
    body = _code_only(_py_function_source(open(MAIN, encoding='utf-8').read(),
                                          'get_org_capital_projects_via_text'))
    assert 'START_CURR' in body and 'END_CURR' in body, "the schedule dates are gone"
    assert 'mindate' not in body and 'maxdate' not in body, (
        "the 2026 plan's fiscal-year dates must not be used as a schedule fallback")
    assert re.search(r"right\(btrim\(\"START_CURR\"\), 4\) >= '1901'", body), (
        "the 1899 sentinel is no longer suppressed")


def test_the_category_column_is_gone_because_its_vocabularies_do_not_overlap():
    """⚠ The 2023 series uses 150 category values, the 2026 plan uses 4, and they
    share ZERO. So one column was rendering two disjoint taxonomies — a reader saw
    "NEIGHBORHOOD REVITALIZATION" beside "Lump Sum" with nothing marking them as
    different systems. Removed rather than labelled, at the owner's call.

    ⚠ The API still SERVES `category`: the defect was showing two vocabularies in
    one column, not the data existing, and a consumer may want either.
    """
    src = open(PROJECT_VIEW, encoding='utf-8').read()
    i = src.index('<table id="alt-union-table"')
    j = src.index('</table>', i)
    assert 'Category' not in src[i:j], "the Category column is back in the union table"
    body = _code_only(_py_function_source(open(MAIN, encoding='utf-8').read(),
                                          'get_org_capital_projects_via_text'))
    assert 'AS category' in body, (
        "the API should still serve category; only the column was removed")
