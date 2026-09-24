"""Guards for the 2026-08-21 five-page reorg (docs/DIGITAL-REFORM-REORG-PLAN.md).

Phase 1 moved content without building: /expiring -> /contracts, /licenses* ->
/products*, the pipeline block to the Contracts page, the vendors table to its
own page, and a new Master Agreements index. What can silently regress:
the redirects (family pages are linked from every vendor profile), the nav, and
the masters endpoint's grain and ceiling-naming discipline.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))


def _read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def test_every_old_url_redirects_to_its_new_home():
    """⚠ The redirects are load-bearing, not courtesy: family pages are linked
    from every vendor profile's Software Products section, and queue filter URLs
    are shared around. A dropped redirect 404s them all silently."""
    routes = _read('app/routes/web.php')
    for old, target in (
        # /expiring WAS the queue, so it goes to the queue's own page (2026-09-23).
        ("'/research/digital-reform/expiring'", 'research.digital-reform.review'),
        ("'/research/digital-reform/licenses'", 'research.digital-reform.products'),
        ("'/research/digital-reform/licenses/function/{cap}'", 'research.digital-reform.product-capability'),
        ("'/research/digital-reform/licenses/{slug}'", 'research.digital-reform.product-family'),
    ):
        i = routes.find(old)
        assert i >= 0, f'the old path {old} has no route at all — old links 404'
        window = routes[i:i + 400]
        assert 'redirect()' in window and target in window, \
            f'{old} does not redirect to {target}'
    # ⚠ Laravel matches in declaration order: the function/{cap} redirect must be
    # declared before the {slug} redirect or it is swallowed by it.
    assert routes.index("'/research/digital-reform/licenses/function/{cap}'") \
         < routes.index("'/research/digital-reform/licenses/{slug}'"), \
        'the capability redirect is declared after the slug redirect, which swallows it'


def test_the_nav_keeps_the_reorg_order_with_vendors_last():
    """⚠ Named for the PROPERTY, not the count. This was
    `..._has_all_five_pages_...` and the section gained a sixth (Data,
    2026-09-14) the day after; a name that encodes a number goes stale the
    moment the thing it counts moves. The assertion below has always been about
    ORDER, which is what the owner decision actually was."""
    nav = _read('app/resources/views/sub/menubar.blade.php')
    order = ['research.digital-reform.contracts', 'research.digital-reform.products',
             'research.digital-reform.agreements', 'research.digital-reform.vendors']
    idx = [nav.index(f"route('{r}')") for r in order]
    assert idx == sorted(idx), 'the submenu order changed — Vendors last is an owner decision'


def _masters_fn():
    src = _read('api/routers/oce.py')
    body = src[src.index('async def get_digital_reform_masters'):]
    return body[:body.index('\n@router.')]


def test_the_masters_index_is_contract_grain_and_kind_safe():
    """⚠⚠ The two defects this repo has shipped before, pinned at the new
    surface: `contracts` is one row per AMENDMENT (dedup on
    coalesce(contract_id, ctid), never ctr_id — #262/#278), and the MA/MMA test
    is a leading-alpha run, never a prefix (startswith('MA') is False for MMA —
    #261). contractkind.sql_is_master is the one owner of the second."""
    fn = _masters_fn()
    assert "DISTINCT ON (coalesce(c.contract_id, 'row:' || c.ctid::text))" in fn, \
        'the masters index no longer dedupes at contract grain — every amendment reads as an agreement'
    assert 'contractkind.sql_is_master' in fn, \
        'the MA/MMA test is no longer contractkind — a prefix match misclassifies MMA'
    assert 'ORDER BY coalesce(c.contract_id' in fn and 'current_amount DESC NULLS LAST' in fn, \
        'the surviving amendment row is no longer the largest restated total'


def test_the_masters_payload_money_is_named_ceiling_never_value():
    """⚠ #261's key-naming discipline: a master's figure is a CEILING. A key
    named value/total/spend invites summing it into money that was spent."""
    fn = _masters_fn()
    assert '"ceiling"' in fn and '"total_ceiling"' in fn, \
        'the ceiling keys are gone from the masters payload'
    for banned in ('"value"', '"total_value"', '"spend"', '"paid"'):
        assert banned not in fn, \
            f'the masters payload carries a {banned} key — a ceiling is not spend'


# --------------------------------------------------- Phase 2: the renewal calendar

def _calendar_fn():
    src = _read('api/routers/oce.py')
    body = src[src.index('    async def _calendar():'):]
    return body[:body.index('\n    async def ', 10)]


def test_the_calendar_splits_ended_from_future_on_the_FULL_DATE():
    """⚠⚠ A YEAR TEST PUTS ALREADY-ENDED CONTRACTS IN THE FUTURE BUCKET. My first
    draft split on `year < this_year`, which counted contracts that ended earlier
    THIS year as still to come: the calendar reported 1,195 renewing before the
    horizon against the queue's 690 — a second answer to the page's own headline
    question, which is the defect this move exists to prevent. Measured after
    switching to the full-date comparison: 692 against 690, the remaining two
    being the derived table's contract_id dedup."""
    fn = _calendar_fn()
    # ⚠ Scope to the SQL, not the whole function: the comment ABOVE the payload
    # key also says "licensewindow.sql_clause", and the first draft of this guard
    # matched that comment and passed with the real predicate replaced by a
    # hardcoded year. Sixth time this repo has paid for a scanner reading prose
    # as code.
    sql = fn[fn.index('select_safe(f"""'):fn.index('""") or []')]
    assert 'TO_DATE(c.end_date' in sql and 'CURRENT_DATE' in sql, \
        'the ended/future split is no longer a full-date comparison'
    assert 'licensewindow.sql_clause' in sql, \
        "the calendar no longer counts the queue's window with the queue's own " \
        "predicate, so the two figures can drift apart"


def test_the_calendar_reads_the_same_row_set_as_every_other_figure():
    """⚠ It must query `sc.table()`, not raw `contracts` with its own dedup. The
    derived table dedups on contract_id and drops NULL-id rows; a second dedup
    keyed on coalesce(contract_id, ctid) kept them and disagreed by 2 contracts.
    One row set for the whole payload, by construction."""
    fn = _calendar_fn()
    assert 'FROM {sc.table()} c' in fn, \
        'the calendar builds its own row set instead of the shared scope table'
    assert "DISTINCT ON (coalesce(c.contract_id" not in fn, \
        'the calendar re-dedupes on top of the scope table — two grains, one figure'


def test_the_calendar_discloses_all_three_buckets():
    """⚠ years + ended + no_end_date must be reported, and the page must state
    them. A calendar that silently drops rows reads as the whole inventory —
    exactly how a table summing to 262 sat under a tile reading 948."""
    fn = _calendar_fn()
    for key in ('"no_end_date"', '"ended"', '"total_contracts"'):
        assert key in fn, f'the calendar payload no longer reports {key}'
    view = _read('app/resources/views/procurement/digital-reform-expiring.blade.php')
    assert 'have already' in view and 'ended' in view, \
        'the Contracts page no longer states how many contracts already ended'
    assert '$cal' in view, 'the Contracts page does not read the calendar payload'


def test_the_calendar_has_exactly_one_home():
    """⚠ The Products page must POINT at it, never render a second one."""
    lic = _read('app/resources/views/procurement/digital-reform-licenses.blade.php')
    assert 'digital-reform.contracts' in lic and '#calendar' in lic, \
        'the Products page lost its pointer to the calendar'
    assert '$years' not in lic.split('Renewal calendar: MOVED')[-1][:2000], \
        'the Products page renders calendar year rows again'
    ctrl = _read('app/app/Http/Controllers/ProcurementController.php')
    assert "'calendar' =>" in ctrl, \
        'the controller does not pass calendar, so the section renders as nothing'


def test_the_calendar_never_blends_ceilings_into_committed_money():
    """⚠⚠ I SHIPPED THIS BLEND AND IT DISAGREED WITH THE QUEUE BY $165M.

    Phase 2's calendar summed one `value` per year across every contract,
    including master agreements — whose figure is a CEILING, the most that may be
    bought, with 0% carrying a payment under their own id. On the same 690
    contracts the calendar read $3,802M against the queue's $3,637.6M: two
    figures for one thing, on one page, which is the defect this reorg exists to
    remove. #261's rule is that the two never share a column.
    """
    fn = _calendar_fn()
    sql = fn[fn.index('select_safe(f"""'):fn.index('""") or []')]
    assert 'contractkind.sql_is_master' in sql, \
        'the calendar no longer identifies master agreements, so their ceilings ' \
        'are being summed as committed money'
    assert '"committed"' in fn and '"ceiling"' in fn, \
        'the calendar payload no longer splits committed money from ceilings'
    assert '"value": val' not in fn and 'a["value"]' not in fn, \
        'a single blended value key is back in the calendar'

    # ⚠ The calendar is a CHART since 2026-09-23 (the table drew the same rows
    # the by-year chart above it already drew). Same property, re-expressed:
    # committed money and ceilings are two SEPARATE datasets, never stacked.
    view = _read('app/resources/views/procurement/digital-reform-expiring.blade.php')
    js = view[view.index("getElementById('renewalCliffChart')"):]
    js = js[:js.index('new Chart(') + 4000]
    assert 'data: calYears.map(d => d.committed)' in js, \
        'the renewal chart no longer draws committed money as its own series'
    assert 'data: calYears.map(d => d.ceiling)' in js, \
        'the renewal chart no longer draws the ceiling as a separate series'
    assert 'stacked' not in js and 'stack:' not in js, \
        ('the renewal chart stacks ceilings onto committed money — undrawn '
         'headroom drawn as money owed (#294)')
    assert 'd.committed + d.ceiling' not in js and 'd.ceiling + d.committed' not in js, \
        'the renewal chart adds a ceiling to committed money'


# --------------------------------------------------- Phase 3: open-source alternatives

def _oss():
    """The real builder, loaded by path. ⚠ By path, not `from routers import
    licenses`: conftest replaces the `modules` package with a MagicMock whose
    attributes satisfy almost any assertion, so an import would test the mock."""
    import importlib.util
    import sys
    import types
    api = os.path.join(ROOT, 'api')
    for pth in (api, os.path.join(api, 'modules')):
        if pth not in sys.path:
            sys.path.insert(0, pth)
    spec = importlib.util.spec_from_file_location(
        '_lic_oss', os.path.join(api, 'routers/licenses.py'))
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:                      # heavy deps absent in the unit env
        return None

    # ⚠⚠ INJECT THE REAL licenseclass. conftest.py replaces the whole `modules`
    # package with a MagicMock, so `from modules import licenseclass` inside the
    # router yields a mock whose resolve() returns a mock — and every row then
    # fails the class gate, making the review band silently empty. The first
    # version of these guards "failed" for exactly that reason and would have
    # "passed" just as meaninglessly had the assertion been weaker. This repo has
    # paid for that mock twice already.
    real = importlib.util.spec_from_file_location(
        '_real_licenseclass', os.path.join(api, 'modules/licenseclass.py'))
    lc = importlib.util.module_from_spec(real)
    real.loader.exec_module(lc)
    mod.licenseclass = lc
    assert lc.resolve('p', 'f', {}, {'f': {'class': 'software-licence'}})['class'] \
        == 'software-licence', 'the real licenseclass did not load'
    return mod


def _row(**kw):
    base = {'family': 'F', 'product': 'P', 'value': 1_000_000.0,
            'expiring': True, 'end_date': '06/30/2027', 'build_vs_buy': 'high'}
    base.update(kw)
    return base


def test_only_the_curated_band_ever_names_an_alternative():
    """⚠⚠ #146's rule, made structural. An unreviewed candidate must not reach a
    page by omission — so the review band carries NO candidate field at all,
    rather than a blank one a template might render."""
    mod = _oss()
    if mod is None:
        import pytest
        pytest.skip('router deps unavailable in this environment')

    rows = [_row(family='Curated'), _row(family='Unreviewed')]
    families = [{'key': 'Curated', 'slug': 'curated', 'value': 1e6, 'contracts': 1},
                {'key': 'Unreviewed', 'slug': 'unreviewed', 'value': 1e6, 'contracts': 1}]
    candidates = {'Curated': [{'candidate': 'PostgreSQL', 'candidate_kind': 'product',
                               'confidence': 'strong', 'licence': 'PostgreSQL',
                               'gov_adopters': 12, 'url': 'https://x', 'why': 'w'}]}
    classes = {'Curated': {'class': 'software-licence'},
               'Unreviewed': {'class': 'software-licence'}}

    out = mod._oss_alternatives(rows, families, candidates, classes, {})
    cur = {r['family'] for r in out['curated']}
    rev = out['review']
    assert cur == {'Curated'}, f'the curated band is wrong: {cur}'
    assert [r['family'] for r in rev] == ['Unreviewed'], \
        'the unreviewed product is not in the review band'
    for r in rev:
        assert 'candidate' not in r, \
            'a review-band row carries a candidate field — an unreviewed ' \
            'judgement must never name a replacement (#146)'


def test_the_review_band_is_gated_to_software_licences():
    """⚠ Asking "could the City build this?" of hosting answers no and hides the
    money: AWS sat at $6.80M rated `low` and appeared in no replaceability view,
    against a whole `high` set of $10.13M. Only outright licences qualify."""
    mod = _oss()
    if mod is None:
        import pytest
        pytest.skip('router deps unavailable in this environment')

    rows = [_row(family='Hosted'), _row(family='Licensed')]
    families = [{'key': 'Hosted', 'slug': 'h', 'value': 1e6, 'contracts': 1},
                {'key': 'Licensed', 'slug': 'l', 'value': 1e6, 'contracts': 1}]
    classes = {'Hosted': {'class': 'managed-hosting'},
               'Licensed': {'class': 'software-licence'}}

    out = mod._oss_alternatives(rows, families, {}, classes, {})
    got = [r['family'] for r in out['review']]
    assert got == ['Licensed'], \
        f'the class gate is not holding — hosting reached the review band: {got}'


def test_only_expiring_contracts_count_toward_the_bands():
    """The section's whole premise is that a renewal is when a switch costs
    least, so a product with nothing expiring does not belong in either band."""
    mod = _oss()
    if mod is None:
        import pytest
        pytest.skip('router deps unavailable in this environment')

    # ⚠⚠ THE EXPIRING PROPERTY IS ENFORCED TWICE and a SINGLE mutation cannot
    # falsify it: the review loop checks `r['expiring']`, and `exp` is built only
    # from expiring rows so `if not e: continue` gates it again. Removing either
    # alone changes nothing — verified, and recorded here so a future reader does
    # not read that pass as a useless guard. Both must be removed together, and
    # then this test fails as it should.
    #
    # ⚠ BOTH BANDS MUST BE EXERCISED. The first version used only a CURATED
    # family, so deleting the review loop's expiring check changed nothing and
    # the mutation went uncaught — the review band skips a curated family
    # anyway. Two families now, one down each band's path.
    rows = [_row(family='LaterCurated', expiring=False),
            _row(family='LaterReview', expiring=False)]
    families = [{'key': 'LaterCurated', 'slug': 'x', 'value': 1e6, 'contracts': 1},
                {'key': 'LaterReview', 'slug': 'y', 'value': 1e6, 'contracts': 1}]
    out = mod._oss_alternatives(
        rows, families,
        {'LaterCurated': [{'candidate': 'X', 'gov_adopters': 1}]},
        {'LaterCurated': {'class': 'software-licence'},
         'LaterReview': {'class': 'software-licence'}}, {})
    assert out['curated'] == [], 'a curated product with nothing expiring reached a band'
    assert out['review'] == [], (
        'a review-band product with nothing expiring reached a band — the whole '
        'premise is that a renewal is when a switch costs least')


def test_a_reviewed_negative_never_sits_in_the_named_table():
    """⚠⚠ SHIPPED WRONG FOR ONE DEPLOY. 8 of 56 curated rows are reviewed
    NEGATIVES — an empty `candidate` with confidence 'none', meaning somebody
    looked and found no substitute. They rendered as a blank cell in a table
    headed "with a named alternative", quietly breaking that heading's promise.

    Caught by reading a rendered row (Pantheon), not the payload. They are a
    finding worth stating, so they get their own band rather than being dropped.
    """
    mod = _oss()
    if mod is None:
        import pytest
        pytest.skip('router deps unavailable in this environment')

    rows = [_row(family='Named'), _row(family='LookedAndFoundNothing')]
    families = [{'key': 'Named', 'slug': 'n', 'value': 1e6, 'contracts': 1},
                {'key': 'LookedAndFoundNothing', 'slug': 'l', 'value': 1e6, 'contracts': 1}]
    candidates = {
        'Named': [{'candidate': 'Moodle', 'confidence': 'strong', 'gov_adopters': 9}],
        'LookedAndFoundNothing': [{'candidate': '', 'confidence': 'none',
                                   'gov_adopters': None}],
    }
    out = mod._oss_alternatives(rows, families, candidates,
                                {'Named': {'class': 'software-licence'},
                                 'LookedAndFoundNothing': {'class': 'software-licence'}}, {})
    assert [r['family'] for r in out['curated']] == ['Named'], \
        'a curated row with no candidate is in the named-alternative table'
    for r in out['curated']:
        assert (r['candidate'] or '').strip(), \
            'a named-alternative row has a blank candidate — the heading promises one'
    assert [r['family'] for r in out['no_alternative']] == ['LookedAndFoundNothing'], \
        'the reviewed negative was dropped instead of reported — knowing a ' \
        'product has no substitute is a finding'


# --------------------------------------------------- Phase 4: the drawdown signal

def test_an_untracked_master_is_never_rendered_as_zero_spend():
    """⚠⚠ THE PAGE'S WHOLE POINT. Of 186 registered masters only 22 carry a
    Checkbook record and 8 show any spend, against $3,337.4M of ceiling — because
    agencies buy against a master on purchase orders carrying their OWN contract
    ids, so the money is filed elsewhere rather than missing.

    A rendered "$0" would therefore be a claim the data does not support, and on
    this page it would invert the finding: Dell Marketing holds $1.86bn of
    payments across 29,822 ids while its $573.8M Citywide Microsoft agreement
    shows zero under its own.
    """
    fn = _masters_fn()
    assert 'spent = float(spent) if spent is not None else None' in fn, \
        'an absent Checkbook figure is being coerced to a number — null and zero ' \
        'are different claims here'
    view = _read('app/resources/views/procurement/digital-reform-agreements.blade.php')
    assert "=== null" in view, \
        'the view no longer distinguishes an untracked agreement from a zero one'
    assert 'not tracked here' in view, \
        'the untracked case lost its wording and will read as zero'


def test_the_masters_drawdown_lookup_cannot_duplicate_an_agreement():
    """⚠ checkbook_contract_meta is keyed on a normalized id; a plain join that
    matched twice would duplicate the agreement and double its ceiling. Same rule
    as #287's notice lookup."""
    fn = _masters_fn()
    assert 'LEFT JOIN LATERAL (' in fn and 'LIMIT 1' in fn, \
        'the drawdown lookup is no longer a bounded lateral'
    assert 'JOIN checkbook_contract_meta' not in fn, \
        'a direct join against checkbook_contract_meta has appeared'


def test_the_page_states_the_mechanism_rather_than_asserting_it():
    """The numbers must come from the payload, not be typed into the copy — the
    typed-figure defect this repo has paid for repeatedly."""
    view = _read('app/resources/views/procurement/digital-reform-agreements.blade.php')
    assert "$maDraw['drawn']" in view and "$maDraw['tracked']" in view, \
        'the mechanism section types its figures instead of reading them'
    fn = _masters_fn()
    assert '"drawdown"' in fn, 'the payload no longer carries the drawdown counts'


# --------------------------------------------------- Phase 6: the section search

def _search_fn():
    src = _read('api/routers/oce.py')
    body = src[src.index('async def digital_reform_search'):]
    return body[:body.index('\n@router.')]


def test_the_search_returns_every_group_including_empty_ones():
    """⚠⚠ #256's DEFECT, DESIGNED OUT. `/get/search` appends a group only `if
    res`, so a builder returning [] is omitted from the payload entirely and the
    response is still 200 — which is how the people group returned nothing on
    every search for eight weeks. "Nobody is called that" and "this query is
    broken" were byte-identical to every consumer.

    Here all four groups are constructed up front and always returned with a
    `count`, so the two states are distinguishable."""
    fn = _search_fn()
    assert 'groups = {k: {"key": k, "label": lbl, "rows": [], "count": 0}' in fn, \
        'groups are no longer pre-constructed, so an empty arm can vanish silently'
    assert 'out["groups"] = list(groups.values())' in fn, \
        'the payload no longer returns the full group set'
    # ⚠ A third assertion here searched the function text for "if res" to catch a
    # conditional append. It fired on THIS FUNCTION'S OWN DOCSTRING, which quotes
    # `if res` while explaining #256 — the seventh time in this repo that a
    # scanner has read prose as code. Dropped rather than patched: the two
    # assertions above already pin the property behaviourally, and a guard that
    # needs comment-stripping to express a weaker version of what is already
    # pinned is not worth its own failure mode.


def test_each_search_arm_degrades_alone():
    """One broken arm must not sink the others — the federated-search rule. Each
    arm has its own try/except, and the level is WARNING because an absent
    derived table is a legitimate fresh-environment state here."""
    fn = _search_fn()
    assert fn.count('except Exception as exc:') >= 4, \
        'the search arms no longer degrade independently'
    assert fn.count('logger.warning') >= 4, \
        'a failing search arm is silent'


def test_the_search_resolves_vendors_through_unique_map():
    """⚠ A vendor NAME is not an identifier — 48 names resolve to more than one
    supplier id. An ambiguous name must render WITHOUT a link rather than point
    at an arbitrary company (#244)."""
    # ⚠ Past the docstring: it NAMES modules/vendorids.unique_map while
    # explaining the rule, and the first draft matched that prose and passed with
    # the real call replaced by an empty dict. Eighth time in this repo.
    fn = _search_fn()
    _q = chr(34) * 3          # the docstring delimiter, built not typed
    body = fn[fn.index(_q, fn.index(_q) + 3) + 3:]
    assert 'vendorids.unique_map(' in body, \
        'the search resolves vendor links some other way — see #244'
    assert 'else ""' in body, \
        'an ambiguous vendor name no longer degrades to an unlinked row'


def test_the_search_is_scoped_to_the_section():
    """⚠ Not /get/search: that federates the whole site and is not scope-aware,
    so it returns notices, people and schools — none of which this section is
    about. Every arm must be constrained by the shared digital scope."""
    fn = _search_fn()
    assert fn.count("sc.where('c')") >= 3, \
        'a search arm is no longer constrained to the technology universe'
    view = _read('app/resources/views/procurement/digital-reform.blade.php')
    assert "route('research.digital-reform.search')" in view, \
        'the Overview search box does not call the scoped endpoint'
    assert 'get/search' not in view, \
        'the Overview search box calls the site-wide endpoint'
