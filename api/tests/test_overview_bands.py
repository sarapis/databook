"""Guards for the Digital Services Overview's five bands (owner redesign, 2026-09-16).

⚠ These read the SERVED shapes and the markup's structure. The part that only a
browser can answer — did the arcs draw, do the slices sum to what the endpoint
publishes — is `scripts/headless/verify_overview_bands.py`, because a canvas
element existing says nothing about a chart rendering, which this repo has
measured four times on capital maps.
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VIEW = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform.blade.php')
CTRL = os.path.join(ROOT, 'app/app/Http/Controllers/ProcurementController.php')
CHARTS = os.path.join(ROOT, 'app/public/js/db-charts.js')
NAV = os.path.join(ROOT, 'app/resources/views/sub/menubar.blade.php')

BANDS = ['s-contracts', 's-products', 's-data', 's-agreements', 's-vendors']


def _read(p):
    return io.open(p, encoding='utf-8').read()


def _expanded(p):
    """The view with every @include expanded IN PLACE — see bladeview.py. The
    Contracts band's charts and the pie factory live in partials the Contracts
    page shares, so a file-only read would measure less than the page renders."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'bladeview', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bladeview.py'))
    bv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bv)
    return bv.expand(p)


def _view_markup():
    """⚠ Blade comments stripped: this file's own comments quote the strings the
    scans below look for, and an own-prose firing is the single most common
    guard defect in this repo."""
    return re.sub(r'\{\{--.*?--\}\}', '', _expanded(VIEW), flags=re.S)


def _nav_code():
    """The menubar with whole-line comments removed — see the note in the rename
    guard for why the naive scan fired on a correct file."""
    src = re.sub(r'\{\{--.*?--\}\}', '', _read(NAV), flags=re.S)
    return "\n".join(l for l in src.split("\n") if not l.strip().startswith('//'))


def _band(view, bid):
    i = view.index(f'id="{bid}"')
    # ⚠ Sliced to the section's end, never a fixed window — a 3000-char slice
    # already reported a correct band as missing its @else.
    return view[i:view.index('</section>', i)]


def test_every_band_exists_and_links_to_the_page_it_summarises():
    """A band that summarises a page and does not link to it is a dead end, and
    the bands replaced cards whose whole job was the link."""
    view = _view_markup()
    routes = {
        's-contracts': 'research.digital-reform.contracts',
        's-products': 'research.digital-reform.products',
        's-data': 'research.digital-reform.data',
        's-agreements': 'research.digital-reform.agreements',
        's-vendors': 'research.digital-reform.vendors',
    }
    order = []
    for bid, route in routes.items():
        assert f'id="{bid}"' in view, f'band {bid} is gone'
        band = _band(view, bid)
        assert f"route('{route}')" in band, f'band {bid} no longer links to its page'
        assert '<h2' in band, f'band {bid} has no heading'
        order.append(view.index(f'id="{bid}"'))
    assert order == sorted(order), 'the bands no longer follow the submenu order'


def test_the_bands_follow_the_submenu_order():
    """⚠ The page and the nav must tell the same story about what this section
    contains. Two orders is how a reader learns to distrust both."""
    view, nav = _view_markup(), _read(NAV)
    pairs = [('s-contracts', 'contracts'), ('s-products', 'products'),
             ('s-data', 'data'), ('s-agreements', 'agreements'),
             ('s-vendors', 'vendors')]
    page = [view.index(f'id="{b}"') for b, _ in pairs]
    menu = [nav.index(f"route('research.digital-reform.{r}')") for _, r in pairs]
    assert page == sorted(page) and menu == sorted(menu), \
        'the page bands and the submenu disagree about order'


def test_call_centers_is_unlinked_but_its_route_still_exists():
    """⚠ OWNER DECISION: out of the submenu, NOT deleted — "let's return to it
    later". A route that 404s would lose the work; a nav entry would contradict
    the decision. Both halves are asserted, because doing one without the other
    is the failure in each direction."""
    nav = _read(NAV)
    assert "route('research.digital-reform.call-centers')" not in nav, \
        'call centers is back in the submenu'
    routes = _read(os.path.join(ROOT, 'app/routes/web.php'))
    assert "research.digital-reform.call-centers" in routes, \
        'the call-centers ROUTE was deleted — it is meant to be unlinked, not lost'


def test_the_agreements_rename_moved_the_label_and_the_url_together():
    """⚠ A label and a path that disagree is how a section ends up with two names
    for one page. The old path must 302 rather than 404: it is linked from the
    storyboard, the Products page and the queue."""
    routes = _read(os.path.join(ROOT, 'app/routes/web.php'))
    assert "'/research/digital-reform/agreements'" in routes
    assert "name('research.digital-reform.agreements')" in routes
    assert "'/research/digital-reform/master-agreements'" in routes and \
        "redirect()->route('research.digital-reform.agreements'" in routes, \
        'the old path no longer redirects — every existing link to it breaks'
    # ⚠⚠ OWN-PROSE FIRING, HIT WHILE WRITING THIS. The menubar comment RECORDING
    # the rename contains the exact string "Master Agreements", so the first
    # draft failed on a correct file. A mention is prose; a label is code.
    # ⚠ Only whole-line `//` comments are stripped — a bare `//` split would eat
    # the `https://` inside a URL, which is the refinement this repo already
    # paid for once.
    nav = _nav_code()
    assert "['Agreements'," in nav, 'the submenu label was not renamed'
    assert 'Master Agreements' not in nav, 'the old label is still rendered'


def test_a_pie_never_exceeds_the_validated_palette():
    """⚠⚠ FIVE HUES PLUS ONE NEUTRAL, AND THE CAP IS THE PALETTE'S SIZE, not a
    taste call. Measured with the dataviz validator: no ordering of the ten
    brand hues passes the lightness/chroma/CVD/contrast checks at six, so a
    sixth categorical wedge means a hue was cycled or invented."""
    ctrl = _read(CTRL)
    body = ctrl[ctrl.index('private static function _slices'):]
    body = body[:body.index('\n    /**', 1)]
    assert 'array_slice($clean, 0, 5)' in body, \
        'the fold no longer caps at five categorical slices'
    js = _read(CHARTS)
    hues = re.search(r'\n  slice: \[([^\]]*)\]', js)
    assert hues, 'DBChart.slice is gone'
    assert len(re.findall(r'#[0-9a-f]{6}', hues.group(1))) == 5, \
        'DBChart.slice no longer carries exactly five hues — re-run the validator'


def test_the_pies_do_not_use_the_site_wide_palette():
    """⚠ `DBChart.palette`'s first six FAIL three of the validator's checks —
    three read gray and one renders at 2.75:1. A bar chart with a legend
    survives that; a pie, whose slices touch, does not. And `palette` must stay
    as it is: every other chart on the site uses it."""
    view = _view_markup()
    # ⚠ RE-EXPRESSED 2026-09-18, never relaxed. The palette lookup moved OUT of
    # `ovPie` into `sliceColor()`, because the LEGEND is HTML now and paints its
    # own swatches — so the resolver has to be shared or the key and the wedge it
    # names could differ. The property is unchanged and now covers more: every
    # pie builder, and the swatch painter, resolve through one function.
    resolver = view[view.index('function sliceColor('):view.index('function paintLegends(')]
    assert 'DBChart.slice' in resolver and 'DBChart.sliceOther' in resolver
    assert 'DBChart.palette' not in resolver, \
        'the pies are back on the site-wide palette, which fails the colour checks'
    # Every builder goes through it — a second colour list is the defect.
    pies = view[view.index('function ovPie('):view.index('// ---- Section search')]
    assert pies.count('.map(sliceColor)') >= 2, \
        'a pie builds its colours without the shared resolver'
    assert 'DBChart.palette' not in pies, \
        'a pie reaches for the site-wide palette directly'
    assert "sliceColor(c)" in view[view.index('function paintLegends('):
                                   view.index('function ovPie(')], \
        'the legend swatches no longer come from the same resolver as the arcs'
    js = _read(CHARTS)
    assert "palette: ['#162e51', '#2491ff'" in js, \
        'the site-wide palette was edited — that repaints every chart on the site'


def test_the_remainder_is_named_counted_and_never_a_hue():
    """⚠ A capped list presented as a whole is the `by_vendor` defect (25 of 408
    under a heading implying all of them). The fold must SAY how many rows it
    folded, and the wedge must be the neutral: a remainder is the absence of an
    identity, not a category."""
    ctrl = _read(CTRL)
    body = ctrl[ctrl.index('private static function _slices'):]
    body = body[:body.index('\n    /**', 1)]
    assert "count($tail) . ' others'" in body, 'the remainder no longer names its size'
    assert "'other_count' => count($tail)" in body, 'the remainder count is not served'
    assert "$colors[] = 'OTHER';" in body, 'the remainder takes a categorical hue'
    assert "'UNKNOWN' : $i" in body, \
        'an abstention no longer gets its own marker — it would share the fold\'s grey'
    # ⚠ The slices must still SUM to the list's own total, or the pie silently
    # publishes less money than the page it links to.
    assert "$tailValue += $t['value']" in body, 'the folded tail is dropped, not summed'


def test_an_abstention_keeps_the_neutral_wherever_it_ranks():
    """⚠ "Function not identified", "Not yet tagged" and "Agency not recorded"
    are the absence of an answer. Giving one a categorical hue ranks it beside
    real categories — and `Function not identified` is $137M, so it ranks high
    enough to land in the head slices where it would get one."""
    ctrl = _read(CTRL)
    for label in ('Function not identified', 'Not yet tagged', 'Agency not recorded'):
        assert f"'{label}'" in ctrl, f'{label} is no longer sent to the neutral'
    body = ctrl[ctrl.index('private static function _slices'):]
    body = body[:body.index('\n    /**', 1)]
    assert "in_array($c['label'], $greyKeys, true)" in body, \
        'the grey-key list is no longer consulted when colouring a head slice'


def test_the_function_pie_states_its_coverage():
    """⚠⚠ MEASURED: `by_capability` reaches 1,432 of 1,601 contracts and
    $1,734.0M of $1,770.4M — 169 contracts have NO capability row at all, which
    is a different absence from the "Function not identified" wedge inside the
    chart. A chart covering 98% reads as covering all of it unless it says so,
    and the figures must be SERVED so they move with the data."""
    view = _view_markup()
    band = _band(view, 's-products')
    assert "$pb['fn_value']" in band and "$pb['fn_contracts']" in band, \
        'the coverage is typed or absent — it must come from the payload'
    assert 'carry no function' in band
    assert not re.search(r'\b1,?43[0-9]\b|\b169 contracts\b', band), \
        'a coverage figure is typed into the copy'


def test_the_segment_drill_down_survived_as_real_links():
    """⚠⚠ `techsegments.resolve_slug` and the `contract_segment` parameter have
    NO OTHER CONSUMER. The composition bar that carried the drill-down was
    folded into a pie, and losing the affordance would leave a whole filter
    built and wired to nothing — which this repo has shipped before.
    ⚠ ANCHORS, not a canvas click handler: a target painted on a canvas is
    invisible to the keyboard and to a screen reader."""
    view = _view_markup()
    band = _band(view, 's-contracts')
    assert "'contract_segment' => $it['slug']" in band, \
        'the segment drill-down is gone — contract_segment loses its only consumer'
    assert '<a href="{{ route(' in band
    assert 'onClick' not in band, 'the drill-down became a canvas click — not keyboard reachable'


def test_a_fold_and_an_abstention_are_different_greys():
    """⚠⚠ ONE VISUAL, ONE MEANING. Shipped first with a single neutral, and the
    screenshot showed "41 others" and "Function not identified" as two
    indistinguishable grey wedges in the same ring — real categories folded for
    space, and no answer at all, wearing one colour.

    ⚠ The abstention is the DARKER one deliberately: it is a FINDING (65% of the
    data lens carries no identified kind) and has to be legible, while the fold
    is housekeeping and recedes."""
    js = _read(CHARTS)
    fold = re.search(r"sliceOther:\s*'(#[0-9a-f]{6})'", js)
    unk = re.search(r"sliceUnknown:\s*'(#[0-9a-f]{6})'", js)
    assert fold and unk, 'one of the two neutrals is gone'
    assert fold.group(1) != unk.group(1), \
        'the fold and the abstention share one colour — two claims, one visual'

    def lum(h):
        def ch(c):
            c = int(h[c:c + 2], 16) / 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(1) + 0.7152 * ch(3) + 0.0722 * ch(5)

    # ⚠ The abstention must stay the more legible of the two, and must clear 3:1
    # against the surface — it is usually the largest wedge on its chart.
    assert lum(unk.group(1)) < lum(fold.group(1)), \
        'the abstention is now the fainter grey — it is a finding, not housekeeping'
    contrast = (lum(fold.group(1)) + 0.05) / (lum(unk.group(1)) + 0.05)
    assert contrast > 2.0, f'the two neutrals separate by only {contrast:.2f}'


def test_a_drill_down_row_never_links_an_abstention_or_an_empty_slug():
    """⚠⚠ A LINK THAT LANDS ON A 404 IS WORSE THAN PLAIN TEXT — three times in
    this repo already. Two rows under a pie must never become links: an
    ABSTENTION ("Function not identified", "Not yet tagged") which is the absence
    of an answer rather than a page, and any row whose slug is EMPTY because the
    endpoint has no key for it. Both render as plain <span>."""
    view = _view_markup()
    # ⚠ The rule lives in App\Custom\SliceLinks since 2026-09-23 — the Products
    # book is shared with the Products page, and one rule in two views is the
    # defect this guard exists for. The view only names it.
    fn = _read(os.path.join(ROOT, 'app/app/Custom/SliceLinks.php'))
    fn = fn[fn.index('public static function links('):]
    assert "!($it['grey'] ?? false)" in fn, 'an abstention can now become a link'
    assert "($it['slug'] ?? '') !== ''" in fn, 'an empty slug can now become a link'
    assert "'href'" in fn and 'null' in fn, 'the no-link case no longer yields null'
    # ⚠ And the renderer must actually BRANCH on it — a helper returning null
    # while the markup links unconditionally is the same defect one layer down.
    # ⚠ RE-EXPRESSED 2026-09-18: the `<span>` now carries the legend swatch, so
    # the old exact spelling `<span>{{ $l[` no longer appears. The property is
    # unchanged — an abstention and an empty slug still render as a span, not a
    # link — and the BRANCH is what is asserted, not the tag's attributes.
    # ⚠⚠ EVERY SITE, COUNTED. Three rows render through this helper, and a bare
    # `re.search` was satisfied by the two I had not mutated — the first draft
    # passed while one row linked unconditionally.
    branches = view.count("@if($l['href'])")
    assert branches >= 3, f'only {branches} drill-down rows branch on having a page'
    spans = re.findall(r'@else<span[^>]*>(?:<i class="ds-sw"></i>)?\{\{ \$l\[.label.\] \}\}</span>', view)
    assert len(spans) == branches, \
        f'{branches} drill-down rows branch but only {len(spans)} fall back to plain text'


def test_the_drill_downs_use_one_renderer():
    """⚠ Four link rows written four times is four chances for one to link an
    abstention. One closure, called with the route and the parameter."""
    view = _view_markup()
    # ⚠ The rule itself lives in App\Custom\SliceLinks since 2026-09-23 (the Products
    # and Data books are shared with their pages); a view may name it, never
    # restate it. ⚠ RE-EXPRESSED 2026-09-23: the Overview's `$segLinks` closure
    # lost its last caller when the Data band moved into a partial that calls the
    # class directly, so the count is of CALL SITES of the one rule, however named.
    assert 'SliceLinks::links(' in view, 'the Overview no longer uses the one link rule'
    callers = (view.count('SliceLinks::links(') - view.count('return \\App\\Custom\\SliceLinks::links(')
               + view.count('$bookLinks('))
    assert callers >= 3, f'the renderer lost callers ({callers})'
    # And no view restates the rule instead of calling it.
    P = os.path.join(ROOT, 'app/resources/views/procurement/partials')
    for vp in (VIEW, os.path.join(P, 'products-book.blade.php'), os.path.join(P, 'data-book.blade.php')):
        assert "$out[] = ['label' => $it['label']" not in _read(vp), \
            f'{os.path.basename(vp)} restates the drill-down rule'


def test_the_agreement_vendor_links_only_when_the_name_resolved_to_one_id():
    """⚠⚠ NEVER LINK A VENDOR BY NAME. `contracts` identifies a vendor only by
    free text and 48 names hold more than one row in `vendors`, so a link built
    from the name can point at an arbitrary one of two companies.
    `vendorids.unique_map` resolves only unambiguous names — 173 of 182 masters
    — and the rest stay plain text.

    ⚠ Asserted on BOTH surfaces. Linking only the Overview would make the
    summary out-link the page it summarises, which is the seam the bands exist
    to close."""
    router = _read(os.path.join(ROOT, 'api/routers/oce.py'))
    i = router.index('async def get_digital_reform_masters')
    fn = router[i:router.index('\n@router.', i)]
    # ⚠⚠ COMMENTS STRIPPED FIRST. The comment beside this code EXPLAINS the rule
    # and therefore contains `vendorids.key(` — so the first version of this
    # guard passed against a re-typed fold, because the token it looked for was
    # in the prose. Measured by mutation. A mention is prose; a call is code.
    code = "\n".join(l for l in fn.split("\n") if not l.strip().startswith('#'))
    assert 'vendorids.unique_map' in code, 'the masters endpoint resolves ids some other way'
    assert 'vendorids.key(' in code, \
        'the key is re-typed rather than taken from the module that owns it'
    assert '.strip().lower()' not in code, \
        'the vendor key is folded inline — it must come from vendorids.key()'
    assert 'JOIN vendors' not in code.upper().replace('LEFT JOIN VENDORS', 'JOIN VENDORS'), \
        'a name join is back — it duplicates the contract'
    for path in ('app/resources/views/procurement/digital-reform.blade.php',
                 'app/resources/views/procurement/digital-reform-agreements.blade.php'):
        # Includes expanded: the bands live in shared partials since 2026-09-23.
        v = _expanded(os.path.join(ROOT, path))
        # ⚠ RE-EXPRESSED 2026-09-18. The Overview's agreements band is two lists
        # now — vendors by running ceiling, and the agreements ending soonest —
        # so its vendor link moved from `$r['vendor_id']` to `$v['vendor_id']`.
        # The property is unchanged and is asserted on whichever spelling the
        # page uses: a vendor is linked only where the name resolved to one id.
        # ⚠⚠ COUNTED, NOT "PRESENT SOMEWHERE". The Overview links vendors in TWO
        # places now — the agreements band and the top-vendors table — so an
        # `or ... in v` was satisfied by the one I had not mutated while the
        # other linked unconditionally. The property is per LINK: every
        # `route('procurement.vendor')` sits inside a resolved-id branch.
        links = v.count("route('procurement.vendor'")
        guards = (v.count("@if(!empty($r['vendor_id']))")
                  + v.count("@if(!empty($v['vendor_id']))"))
        assert links and guards == links, \
            f'{path}: {links} vendor links but {guards} resolved-id branches'
        assert "route('procurement.vendor'" in v, f'{path} lost the vendor link'


# ---------------------------------------------------------------------------
# The 2026-09-18 redesign: one legend, an honest tooltip, and the Agreements band
# ---------------------------------------------------------------------------

def test_no_pie_draws_its_own_legend():
    """⚠⚠ THE PIES RENDERED THEIR LEGEND TWICE. Chart.js drew the five labels
    into the canvas and the `.ds-seglinks` list repeated them underneath as
    links — the same words in the same order, once unreachable by keyboard and
    once not. The canvas copy is the half that goes: it cannot be focused,
    clicked or read aloud, and it was the one that needed a middle-ellipsis
    truncation to fit.

    ⚠ Restoring `legend.display` would not merely duplicate — it would bring
    back the truncation that once rendered two long agency names as one string.
    """
    view = _view_markup()
    pies = view[view.index('function sliceColor('):view.index('// ---- Section search')]
    # ⚠⚠ EVERY chart in the region, counted — not "at least two". The region
    # holds THREE `new Chart(` calls and the first draft asserted `>= 2`, so
    # turning one legend back on left two and the guard passed. Measured by
    # mutation: a guard on N sites that accepts N-1 is a guard on none of them.
    assert pies.count('legend: { display: false }') == pies.count('new Chart('), \
        'a chart in the Overview draws its own legend again — the labels duplicate'
    assert 'generateLabels' not in pies, \
        'the canvas legend label generator is back, so the canvas is drawing a legend'


def test_every_wedge_has_a_legend_entry_including_the_fold():
    """⚠⚠ WITH THE CANVAS LEGEND OFF, AN ARC WITH NO ITEM IS AN ARC WITH NO KEY,
    and the always-present legend is the SECONDARY ENCODING the palette's
    colour-vision check requires — not decoration. `_slices` caps at five and
    folds the rest, so the fold has to become an item or the largest remainder
    wedge on the page would be nameless."""
    ctrl = _read(CTRL)
    body = ctrl[ctrl.index('private static function _slices'):]
    body = body[:body.index('\n    /**', 1)]
    # the fold is appended to `items`, not only to labels/values/colors
    tail = body[body.index('if ($tailValue > 0)'):]
    assert '$items[] =' in tail, \
        'the fold is no longer a legend item — that wedge would have no key'
    assert "'color' => 'OTHER'" in tail, 'the fold item lost its neutral'
    # and every head item carries one too, or its swatch cannot be painted
    assert "'color' => $grey ? 'UNKNOWN' : $i" in body, \
        'a slice item no longer carries the colour its swatch is painted from'


def test_a_pie_tooltip_does_not_repeat_the_slice_label():
    """⚠⚠ THE TITLE WAS THE LABEL AND SO WAS THE BODY. Chart.js defaults a
    doughnut's tooltip title to the slice label, and the body callback prepended
    `c.label` again — every hover read the name twice. The title now names the
    CHART, and it is READ FROM THE CARD rather than typed: a second copy of a
    title is a second vocabulary, which is how this section came to have two
    names for one segment."""
    view = _view_markup()
    # ⚠⚠ PER BUILDER. Both pie builders live in one region, so a region-wide
    # `in` was satisfied by the OTHER one — dropping `ovPie`'s title callback
    # left the guard green. Measured by mutation, twice in one sitting.
    for fn_name in ('function ovPie(', 'function ovVendorMethodPie('):
        i = view.index(fn_name)
        fn = view[i:view.index('\n    }', i)]
        assert 'title: () =>' in fn, \
            f'{fn_name} sets no tooltip title — Chart.js will default it to the slice label'
        assert "querySelector('.db-chart-title')" in fn, \
            f'{fn_name} types its tooltip title rather than reading the card that renders it'


def test_the_agreements_band_states_that_its_year_bars_do_not_add_up():
    """⚠⚠ AN AGREEMENT COUNTS IN EVERY YEAR OF ITS TERM, so the series sums to
    far more than the ceiling that exists (measured: $13.9B of bars against
    $3.2B on the books). A reader who adds them gets a number that means
    nothing, so the page says so rather than leaving it to be inferred — the
    same discipline as "these are ceilings, not spend"."""
    view = _view_markup()
    band = _band(view, 's-agreements')
    assert 'not added together' in band or 'do not sum' in band, \
        'the year chart no longer warns that its bars are not additive'
    assert 'ovAgrYearChart' in band


def test_the_agreements_band_never_renders_a_zero_for_an_untracked_drawdown():
    """⚠⚠ "Not tracked here", NEVER "$0". Measured 2026-09-18 against the
    spending lake itself: ZERO of the 182 agreements carry a payment under their
    own contract id, and only 8 carry any Checkbook figure at all. A rendered $0
    would assert the City has paid nothing against an agreement it may be drawing
    on heavily — it would invert this page's own finding."""
    view = _view_markup()
    band = _band(view, 's-agreements')
    assert "=== null" in band and 'Not tracked here' in band, \
        'an untracked drawdown no longer renders as "not tracked"'
    i = band.index('Not tracked here')
    assert "$r['spent']" in band[max(0, i - 400):i], \
        'the "not tracked" branch is no longer gated on the spend being absent'


def test_the_agreements_band_computes_nothing():
    """⚠ "The Overview computes nothing" — every figure is a key the Agreements
    page's own endpoint serves, so the two cannot disagree. Two independent
    computations of one number is what produced 243-vs-242 and 1,195-vs-690."""
    ctrl = _read(CTRL)
    # ⚠ RE-EXPRESSED 2026-09-23: the block moved into `_agreementsBookBlocks`, the
    # ONE builder the Overview's cache and the Agreements page both call. The
    # cache must delegate to it, and the builder must read the served keys.
    i = ctrl.index("'digital_reform_ov_agreements_v")
    assert 'self::_agreementsBookBlocks(' in ctrl[i:ctrl.index('});', i)], \
        'the Overview builds its Agreements band itself again'
    assert ctrl.count('self::_agreementsBookBlocks(') == 2, 'the Agreements book is built two ways'
    i = ctrl.index('private static function _agreementsBookBlocks(')
    blk = ctrl[i:ctrl.index('private static function', i + 10)]
    # ⚠⚠ COMMENTS STRIPPED. The comment inside that block NAMES the served keys
    # it reads, so the first draft passed against a block that had stopped
    # reading one of them — the own-prose guard failure, in a new organ.
    blk = "\n".join(l for l in blk.split("\n") if not l.strip().startswith('//'))
    for key in ('by_vendor_active', 'soonest', 'ceiling_by_year', 'active', 'drawdown'):
        assert key in blk, f'the agreements block no longer reads the served `{key}`'
    assert 'usort' not in blk, \
        'the agreements block sorts its own rows again — the endpoint serves the order'


def test_the_vendor_method_pie_is_a_count_of_vendors_not_money():
    """⚠⚠ THE TWO READINGS GIVE DIFFERENT CHARTS. By vendor count the head is
    small-purchase (242 vendors); by the value those vendors hold it is Renewal
    ($2.7B), with small-purchase sixth. The owner chose the count, so the wedge
    must fold on `vendors` — folding on `value` would silently answer the other
    question under the same heading.

    ⚠ And it has its OWN builder, because `ovPie` formats every value with
    `DBChart.money`: a vendor count rendered as dollars on a page where the
    other five pies really are money is a wrong number that looks right."""
    ctrl = _read(CTRL)
    assert "self::_slices($shared['vendor_methods']['items'] ?? [],\n" in ctrl
    i = ctrl.index("'vmSlices' =>")
    call = ctrl[i:i + 260]
    assert "'method', 'vendors'" in call, \
        'the vendor-method pie folds on something other than the vendor count'
    view = _view_markup()
    assert 'ovVendorMethodPie' in view, 'the count pie lost its own builder'
    assert 'vendors' in view[view.index('function ovVendorMethodPie('):
                             view.index('function ovVendorMethodPie(') + 1800], \
        'the count pie no longer says its slices are vendors'


def test_the_controller_names_vendor_methods_in_its_view_data():
    """⚠⚠ #247's SEAM, CAUGHT THREE LINES BELOW ITS OWN WARNING. The api served
    `vendor_methods`, the controller read `$shared['vendor_methods']`, and
    `digitalReformViewData` did not name it — so `_slices` folded an empty list,
    the band's `@if` was false and the pie simply was not on the page. No error,
    no failing test: the sibling guard reads the VIEW's keys, and this one is
    consumed in the CONTROLLER. Only rendering the page found it."""
    ctrl = _read(CTRL)
    i = ctrl.index('function digitalReformViewData')
    fn = ctrl[i:ctrl.index('\n    private function', i) if '\n    private function' in ctrl[i:] else len(ctrl)]
    assert "'vendor_methods' => $allData['vendor_methods']" in fn, \
        'vendor_methods is not named in the view data — the pie will vanish silently'


def test_the_agreements_page_leads_with_the_overviews_agreements_band():
    """2026-09-23: the Agreements page leads with the Overview's Agreements band,
    as Contracts, Products and Data lead with theirs — one partial for both."""
    page_p = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-agreements.blade.php')
    for p in (VIEW, page_p):
        src = _read(p)
        assert "@include('procurement.partials.agreements-book')" in src, f'{os.path.basename(p)} lost the book'
        assert "@include('procurement.partials.agreements-book-js')" in src, f'{os.path.basename(p)} no longer draws it'
    page = _read(page_p)
    assert page.index("@include('procurement.partials.agreements-book')") < page.index('db-stat-grid'), \
        'the band no longer leads the Agreements page'


def test_the_agreements_pies_are_built_server_side_and_close_on_the_ceiling():
    """The page's own two pies. ⚠ Ended is derived by SUBTRACTION from the served
    total, never a second predicate, so the two wedges close on the ceiling
    tile by construction. ⚠ Holders group on the RESOLVED org id, so one
    organisation under two published spellings is one wedge."""
    ctrl = _read(CTRL)
    i = ctrl.index('private static function _agreementsSlices(')
    fn = ctrl[i:ctrl.index('private static function', i + 10)]
    assert "$total - $active" in fn and "'total_ceiling'" in fn and "['active']['ceiling']" in fn
    assert "'org:' . $r['org_id']" in fn, 'holders no longer group on the resolved org'
    i = ctrl.index('public function digitalReformMasterAgreements(')
    body = ctrl[i:ctrl.index('public function', i + 10)]
    assert "'agrSlices' => self::_agreementsSlices($ma)" in body
    page = _read(os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-agreements.blade.php'))
    assert "ovPie('agrAgencyChart', @json($agrSlices['agency'] ?? null));" in page
    assert "ovPie('agrStatusChart', @json($agrSlices['status'] ?? null));" in page


def test_every_page_using_the_pie_factory_paints_its_legends():
    """⚠ The pies' legends are HTML, painted by `paintLegends()` from the colour
    resolver the arcs use. A page that includes the factory and never calls it
    renders every swatch grey, so the legend no longer says which wedge is which
    — shipped on the Data and Agreements pages on 2026-09-23 and found only by
    looking at a screenshot. After the last pie, so none is left unpainted."""
    views = os.path.join(ROOT, 'app/resources/views/procurement')
    found = 0
    for name in sorted(os.listdir(views)):
        if not name.endswith('.blade.php'):
            continue
        src = _read(os.path.join(views, name))
        if "@include('procurement.partials.slice-pies-js')" not in src:
            continue
        found += 1
        assert 'paintLegends();' in src, f'{name} draws pies and never paints their legends'
        last_pie = max(src.rfind("ovPie("), src.rfind("-book-js')"))
        assert src.rindex('paintLegends();') > last_pie, f'{name} paints its legends before its last pie'
    assert found >= 5, f'only {found} pages include the pie factory'


def test_the_vendors_page_leads_with_the_band_at_the_default_ranking():
    """2026-09-23: the Vendors page leads with the Overview's Vendors band.

    ⚠⚠ The band's list is headed "Largest by awarded value", so it must be the
    DEFAULT ranking however the reader has sorted, searched or paged the table
    below — otherwise page 2 sorted by name renders arbitrary vendors under a
    "largest" heading (the reason the old top-5 strip carried `$vIsTop`)."""
    page_p = os.path.join(ROOT, 'app/resources/views/procurement/digital-reform-vendors.blade.php')
    for p in (VIEW, page_p):
        src = _read(p)
        assert "@include('procurement.partials.vendors-book')" in src, f'{os.path.basename(p)} lost the book'
        assert "@include('procurement.partials.vendors-book-js')" in src, f'{os.path.basename(p)} no longer draws it'
    page = _read(page_p)
    assert page.index("@include('procurement.partials.vendors-book')") < page.index('id="digital-vendors"')
    ctrl = _read(CTRL)
    assert ctrl.count('self::_vendorsBookBlocks(') == 2, 'the Vendors book is built two ways'
    i = ctrl.index('public function digitalReformVendors(')
    body = ctrl[i:ctrl.index('public function', i + 10)]
    for k in ('vendor_q', 'vendor_page', 'vendor_sort', 'vendor_order'):
        assert f"'{k}'" in body, f'a {k} request would feed the band its own ranking'
    assert 'self::_vendorsBookBlocks($bandShared)' in body
    book = _read(os.path.join(ROOT, 'app/resources/views/procurement/partials/vendors-book.blade.php'))
    assert '$vendTop' in book and '$ovVendors' not in book
