"""The Products page leads with the Overview's Products band, and its tables
became charts where a chart says more (2026-09-23).

⚠ The page's own order is the OWNER's (2026-09-18: the family table is the
spine) and is pinned in test_license_families; these guards pin what was added
around it.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
CTRL = os.path.join(ROOT, 'app/app/Http/Controllers/ProcurementController.php')
VIEWS = os.path.join(ROOT, 'app/resources/views/procurement')
OVERVIEW = os.path.join(VIEWS, 'digital-reform.blade.php')
PRODUCTS = os.path.join(VIEWS, 'digital-reform-licenses.blade.php')
BOOK = os.path.join(VIEWS, 'partials/products-book.blade.php')
LINKS = os.path.join(ROOT, 'app/app/Custom/SliceLinks.php')


def _read(p):
    return io.open(p, encoding='utf-8').read()


def test_the_products_band_charts_have_one_owner():
    ov, pr, book, ctrl = _read(OVERVIEW), _read(PRODUCTS), _read(BOOK), _read(CTRL)
    for name, src in (('Overview', ov), ('Products page', pr)):
        assert "@include('procurement.partials.products-book')" in src, f"the {name} lost the Products book"
        assert "@include('procurement.partials.products-book-js')" in src, f"the {name} no longer draws it"
    for cid in ('ovFunctionChart', 'ovRouteChart'):
        assert f'id="{cid}"' in book
        assert f'id="{cid}"' not in ov and f'id="{cid}"' not in pr, f"a second copy of {cid}"
    assert ctrl.count('self::_productsBookBlocks($lic)') == 2, \
        "the Overview and the Products page no longer fold the band through one helper"
    # The book sits ABOVE the family table (it previews the page); the owner's
    # family-first order governs everything below it.
    assert pr.index("@include('procurement.partials.products-book')") < pr.index('id="families"')


def test_the_drill_down_link_rule_has_one_owner():
    src = _read(LINKS)
    fn = src[src.index('public static function links('):]
    assert "!($it['grey'] ?? false)" in fn and "($it['slug'] ?? '') !== ''" in fn
    # ⚠ The Overview's pie links now all render inside the shared books (the Data
    # band moved into `data-book` on 2026-09-23), so the books are what must
    # call the one rule.
    for vp in (BOOK, os.path.join(VIEWS, 'partials/data-book.blade.php')):
        assert 'SliceLinks::links(' in _read(vp), f"{os.path.basename(vp)} restates the link rule"


def test_the_fragmentation_map_leaves_out_the_abstention_and_derives_nothing_client_side():
    ctrl = _read(CTRL)
    fn = ctrl[ctrl.index('private static function _fragPoints('):]
    fn = fn[:fn.index('\n    }\n')]
    assert "!== 'other'" in fn, "the abstention is plotted as a function"
    assert "sqrt(" in fn, "bubble AREA no longer carries value"
    assert "'fragPoints' => self::_fragPoints($lic['by_capability'] ?? [])" in ctrl
    pr = _read(PRODUCTS)
    js = pr[pr.index("getElementById('licFragChart')"):]
    js = js[:js.index('})();')]
    assert '@json($fragPoints' in js and '.filter(' not in js and '.map(' not in js, \
        "the fragmentation chart derives its own points"


def test_agencies_and_vendors_are_linked_bars_with_the_full_table_one_click_away():
    pr = _read(PRODUCTS)
    for head, rows in (('By agency</h2>', '$byAg'), ('By vendor</h2>', '$byVen')):
        i = pr.index(head)
        block = pr[i:pr.index('</table>', i)]
        assert f"@foreach(array_slice({rows}, 0, 10) as $bx)" in block
        assert 'class="ds-bar-row" href=' in block, "a bar is not a link"
        assert '<details' in block and '<table class="db-table db-dt">' in block, \
            "the full table is no longer one click away"


def test_the_pointers_go_to_where_the_blocks_live_now():
    pr = _read(PRODUCTS)
    i = pr.index('id="pipeline"')
    ptr = pr[i:pr.index('</p>', i)]
    assert "route('research.digital-reform.agreements') }}#awaiting-registration" in ptr, \
        "the pipeline pointer no longer goes to the Agreements page, where the block lives"
    assert "route('research.digital-reform.contracts') }}#calendar" in ptr
    assert 'id="calendar"' in ptr, "old #calendar links lost their anchor"


def test_every_section_page_starts_with_its_layout():
    """⚠ A `str.replace('', X, 1)` — an edit whose search text came back empty —
    PREPENDS X to the file. It put a chart script above `@extends` on this page,
    where Blade rendered it as visible text at the top, and every other check
    (compile lint, render 200, the unit suite) stayed green."""
    import glob
    views = glob.glob(os.path.join(VIEWS, 'digital-reform*.blade.php'))
    assert len(views) >= 8, 'the glob found too few section views to mean anything'
    for vp in views:
        first = _read(vp).lstrip('﻿').lstrip().split('\n', 1)[0]
        assert first.startswith("@extends("), \
            f"{os.path.basename(vp)} has content before its @extends: {first[:60]!r}"


def test_products_swaps_the_largest_families_list_for_value_by_kind():
    """Owner, 2026-09-23: on the PRODUCTS page the book's middle chart is value by
    kind of purchase; the Overview's band keeps the largest-families list.

    ⚠ The switch is passed by the Products controller method ONLY, so the shared
    partial stays one owner. The kind labels come from App\\Custom\\PurchaseClass,
    the same map the class table below reads, so the pie and the table it drills
    into cannot name a kind two ways.
    """
    ctrl = _read(CTRL)
    lic = ctrl[ctrl.index('public function digitalReformLicenses('):]
    lic = lic[:lic.index('public function', 10)]
    assert "'prodMiddle' => 'kind'" in lic, "Products no longer asks for the kind pie"
    assert ctrl.count("'prodMiddle'") == 1, "another page switched the book's middle chart"
    book = _read(BOOK)
    assert "($prodMiddle ?? 'families') === 'kind'" in book
    assert 'Value by kind' in book and 'Largest product families' in book
    # The kind links land on the class drill-down, through the one link owner.
    assert "SliceLinks::links($pb['kinds'] ?? null, 'research.digital-reform.products', 'class', 'family-detail')" in book
    blocks = ctrl[ctrl.index('private static function _productsBookBlocks'):]
    blocks = blocks[:blocks.index('private static function', 10)]
    assert "'kinds'" in blocks and 'PurchaseClass::label' in blocks
    # One label map: neither view restates it.
    for v in (PRODUCTS, os.path.join(VIEWS, 'digital-reform-license-family.blade.php')):
        assert "'software-licence' => 'Software license'" not in re.sub(r'\s+', ' ', _read(v)), \
            f"{os.path.basename(v)} restates the purchase-class labels"
