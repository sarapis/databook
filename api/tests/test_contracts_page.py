"""The Contracts page leads with the Overview's Contracts band, and says ONE
figure for its renewal window (2026-09-23).

⚠⚠ ONE SET, TWO TOTALS. The queue summed each contract's ORIGINAL award
($1,990.8M) while the renewal calendar, over the SAME 634 contracts, summed
current-else-award ($2,107.4M) — and the Overview quoted the first. The
section's money rule is `digitalscope.value_sql`: coalesce(current, award).
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
OCE = os.path.join(ROOT, 'api/routers/oce.py')
CTRL = os.path.join(ROOT, 'app/app/Http/Controllers/ProcurementController.php')
VIEWS = os.path.join(ROOT, 'app/resources/views/procurement')
OVERVIEW = os.path.join(VIEWS, 'digital-reform.blade.php')
CONTRACTS = os.path.join(VIEWS, 'digital-reform-expiring.blade.php')
BOOK = os.path.join(VIEWS, 'partials/contracts-book.blade.php')


def _read(p):
    return io.open(p, encoding='utf-8').read()


def _code(src):
    """Python with comments removed — the comments here quote the old rule."""
    return '\n'.join(l.split('#', 1)[0] for l in src.split('\n'))


def test_the_queue_summary_sums_the_sections_money_rule():
    code = _code(_read(OCE))
    assert "filtered, amount=lambda e: e['value'])" in code, \
        "the queue's committed/ceiling split no longer sums the section's value rule"
    assert "'total_value': sum(e['value'] for e in filtered)" in code, \
        "the queue's total no longer sums the section's value rule"
    assert "filtered, amount=lambda e: e['award_amount'])" not in code, \
        "the queue is back to summing the original award — two totals for one set"


def test_the_row_value_is_coalesce_current_award_byte_for_byte():
    """`or` would treat a current amount of 0 as missing; SQL's coalesce keeps
    it. Measured against the rule as written, not a paraphrase of it."""
    code = _code(_read(OCE))
    m = re.search(r"'value': \(float\(r\['current_amount'\]\) if r\.get\('current_amount'\) is not None\s*"
                  r"else award_amt\)", code)
    assert m, "the queue row's value is not coalesce(current, award)"
    ds = _read(os.path.join(ROOT, 'api/modules/digitalscope.py'))
    assert 'coalesce({alias}.current_amount, {alias}.award_amount)' in ds, \
        "the section's value rule changed — the queue row must follow it"


def test_the_band_charts_have_one_owner():
    """The band is a preview of the Contracts page, so its charts are ONE
    partial both pages include, never two copies."""
    ov, ct, book = _read(OVERVIEW), _read(CONTRACTS), _read(BOOK)
    for name, src in (('Overview', ov), ('Contracts page', ct)):
        assert "@include('procurement.partials.contracts-book')" in src, \
            f"the {name} no longer renders the shared whole-book charts"
        assert "@include('procurement.partials.contracts-book-js')" in src, \
            f"the {name} no longer draws them"
        assert "@include('procurement.partials.slice-pies-js')" in src, \
            f"the {name} has no pie factory for them"
    for cid in ('ovAgencyChart', 'ovTypeChart', 'digitalStartYearChart'):
        assert f'id="{cid}"' in book, f"{cid} left the shared partial"
        for name, src in (('Overview', ov), ('Contracts page', ct)):
            assert f'id="{cid}"' not in src, \
                f"the {name} carries its own copy of {cid} — a second owner"


def test_both_pages_get_the_pies_from_one_fold():
    ctrl = _read(CTRL)
    assert ctrl.count('self::_contractsBookSlices($shared)') == 2, \
        "the Overview and the Contracts page no longer share one slice fold"
    assert ctrl.count("self::_slices($agRows") == 1, \
        "the agency pie is folded in more than one place"


def test_the_flag_mix_covers_every_flag_as_a_share_of_the_queue():
    """A count tile per flag hid saturation (no-rebid fired on 633 of 634). The
    mix renders EVERY flag key the filter offers, measured against the queue it
    describes, and links each into that filtered queue."""
    ct = _read(CONTRACTS)
    i = ct.index('$flagMix = [];')
    block = ct[i:ct.index('@endphp', i)]
    assert 'foreach ($flagOptions as $fk => $fl)' in block, \
        "the flag mix no longer walks the same flag list the filter offers"
    assert "$expCount > 0 ? 100 * $n / $expCount : 0" in block, \
        "the flag mix is not a share of the queue"
    assert "route('research.digital-reform.review', ['expiring_flag' => $fm['key']]) }}#expiring-contracts" in ct, \
        "a flag row no longer links into the filtered Renewal Review Queue"


def test_the_page_lead_is_one_sentence_again():
    """The lead was two drafts merged ("searchable below ... searchable below")."""
    ct = _read(CONTRACTS)
    lead = ct[ct.index('<p class="db-page-lead">'):]
    lead = lead[:lead.index('</p>')]
    assert lead.count('searchable below') == 0 and lead.count('.') == 1, lead


REVIEW = os.path.join(VIEWS, 'digital-reform-review.blade.php')


def test_renewing_soon_is_the_queues_first_ten_and_links_to_the_queue():
    """The Contracts page shows the ten soonest, read-only, and links to the
    queue's own page. ⚠ It must never carry the queue's filters: those URLs
    redirect to the queue, so "the ten soonest" is always the unfiltered head."""
    ct = _read(CONTRACTS)
    i = ct.index('id="renewing-soon"')
    block = ct[i:ct.index('</section>', i)]
    assert "array_slice($expiring['contracts'] ?? [], 0, 10)" in block, \
        "Renewing soon no longer shows the queue's first ten"
    assert "route('research.digital-reform.review')" in block, \
        "Renewing soon no longer links to the Renewal Review Queue"
    assert '<form' not in block and '<select' not in block, \
        "Renewing soon grew filters — the tool is the queue's own page"
    ctrl = _read(CTRL)
    assert "SECTION_PAGE = 10" in ctrl and "(int) $request->input('expiring_limit', self::SECTION_PAGE)" in ctrl, \
        "the queue's default page is no longer ten rows, so 'the ten soonest' is not ten"


def test_old_queue_urls_on_contracts_redirect_to_the_queue():
    """Queue filter URLs are shared in email and linked from the Products
    pages. On the Contracts page they would be silently ignored, so any of the
    queue's parameters sends the request to the queue with its query string."""
    ctrl = _read(CTRL)
    fn = ctrl[ctrl.index('public function digitalReformExpiring('):]
    fn = fn[:fn.index('\n    }\n')]
    assert 'self::QUEUE_PARAMS' in fn and "redirect()->route('research.digital-reform.review', $request->query())" in fn
    params = re.search(r"QUEUE_PARAMS = \[(.*?)\];", ctrl, re.S).group(1)
    form = _read(REVIEW)
    for name in set(re.findall(r'name="(expiring_[a-z]+)"', form)):
        assert f"'{name}'" in params, f"{name} is a queue control but not in QUEUE_PARAMS"


def test_the_queue_export_is_every_matching_row_and_says_when_it_is_not():
    ctrl = _read(CTRL)
    fn = ctrl[ctrl.index('public function digitalReformReviewExport('):]
    fn = fn[:fn.index('\n    }\n')]
    assert "$qs['expiring_limit'] = self::QUEUE_EXPORT_LIMIT" in fn
    assert 'count($rows) < $total' in fn, \
        "a truncated export would read as complete"
    oce = _read(OCE)
    assert 'expiring_limit = min(max(1, expiring_limit), 1000)' in oce, \
        "the API caps the queue below the export's page size"
    assert "request()->except(['expiring_page', 'expiring_limit'])" in _read(REVIEW), \
        "the export link no longer carries the current filters"


AGREEMENTS = os.path.join(VIEWS, 'digital-reform-agreements.blade.php')


def test_the_pipeline_on_agreements_comes_from_the_one_owner():
    """Awaiting registration moved to Agreements (2026-09-23). It must read the
    section's shared payload — `pipelinevehicles` is the one owner of that
    figure — never a second query."""
    ctrl = _read(CTRL)
    fn = ctrl[ctrl.index('public function digitalReformMasterAgreements('):]
    fn = fn[:fn.index("return view('procurement.digital-reform-agreements'")]
    assert "$this->digitalReformViewData($request)['pipeline']" in fn, \
        "the Agreements page no longer reads the shared pipeline figure"
    assert 'reqOCE' in fn and fn.count('reqOCE') == 1, \
        "the Agreements page makes a second request for the pipeline"


def test_a_pending_agreement_names_registered_ones_as_a_fact_not_a_successor():
    """0 of 2,427 unregistered EPINs match a registered master's, so nothing in
    PASSPort says which agreement a pending one replaces. The page may only say
    "registered with the same vendor and agency", and must link each one."""
    agr = _read(AGREEMENTS)
    assert 'Registered with the same vendor and agency' in agr
    assert '<tr id="ma-{{ $r[\'contract_id\'] }}">' in agr, \
        "registered rows lost the anchor a pending agreement links to"
    assert 'href="#ma-{{ $rg[\'contract_id\'] }}"' in agr
    for word in ('successor', 'replaces', 'renewal of'):
        body = re.sub(r'\{\{--.*?--\}\}', '', agr, flags=re.S)
        assert word not in body.lower(), f"the page asserts a {word!r} link the data cannot show"


def test_the_stale_badge_threshold_is_the_one_the_page_states():
    ctrl, agr = _read(CTRL), _read(AGREEMENTS)
    assert "Carbon::today()->subYears(2)" in ctrl
    assert 'more than two years past' in agr and 'over two years late' in agr, \
        "the page's stated threshold no longer matches the code's"


def test_the_index_agency_filter_is_bound_keyed_and_forwarded():
    """⚠⚠ A filter missing from the API's CACHE KEY serves the first agency's
    table to every agency — silently, and plausibly. So all three halves are
    pinned: the parameter is bound (never interpolated), it is in the key, and
    the controller forwards it (and so keys its own cache on it)."""
    oce = _code(_read(OCE))
    assert "contract_agency: str = ''" in oce
    assert '{contract_segment}:{contract_agency}:' in oce, \
        "contract_agency is not in the /all cache key — one agency's table serves all"
    assert 'filt += f" AND c.agency = ${len(params)}"' in oce, \
        "the agency filter is not a bound parameter"
    assert '"agencies": [r[\'a\'] for r in (ag or [])]' in oce, \
        "the Agency dropdown has no served options"
    ctrl = _read(CTRL)
    assert "'contract_agency' => $contractAgency," in ctrl, \
        "the controller does not forward (or cache-key) the agency filter"


def test_the_index_sits_above_the_renewals_and_filters_by_agency_and_kind():
    ct = _read(CONTRACTS)
    assert ct.index('id="all-digital-contracts"') < ct.index('id="renewals"'), \
        "the contracts index is no longer above What renews before 2030"
    form = ct[ct.index('id="all-digital-contracts"'):]
    form = form[:form.index('</form>')]
    for name in ('contract_q', 'contract_method', 'contract_agency', 'contract_segment'):
        assert f'name="{name}"' in form, f"the index lost its {name} control"
    # ⚠ The Kind options are the composition's own slugs — the same values the
    # type pie links with — never a typed list.
    assert "@foreach(($composition['segments'] ?? []) as $sg)" in form
    # And a control's own value must not ALSO ride along as a hidden input, or
    # changing it submits two values.
    hidden = form[form.index('request()->except('):form.index(') as $k => $v)')]
    for name in ('contract_agency', 'contract_segment'):
        assert f"'{name}'" in hidden, f"{name} is resubmitted as a hidden input"
    assert 'private const ALL_CONTRACTS_PAGE = 10;' in _read(CTRL)
