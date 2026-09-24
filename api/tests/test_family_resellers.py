"""Guards for the family table's "Bought through" column — the per-family
reseller rollup: contract vendors + the notice panel's awarded-to (#287),
merged by modules/resellers.

The ways this can go wrong are specific, and each test names its bug:

1. the two sources spell one company differently ("DELL MARKETING LP" vs
   "Dell Marketing L.P."), so a naive union double-lists real vendors;
2. an over-eager dedup (suffix-stripping) collapses DIFFERENT firms onto one —
   the #148 crosswalk defect;
3. the counts get read off the display-capped list — the count-before-you-cap
   defect — or the overlap dedup runs against a capped list and overcounts the
   notice-only remainder;
4. the router stops passing vendor names into the merge, and every family
   silently reads as having zero contract vendors while the page still renders;
5. the view's sources note claims notice coverage when the notice half never
   loaded — the stale-disclosure defect.

⚠ conftest.py replaces the whole `modules` package with a MagicMock, so the
module under test is loaded BY PATH, and _load() asserts it produced a real
function — a MagicMock would satisfy almost any behavioural assertion here.
"""
import importlib.util
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
MODULE = os.path.join(ROOT, 'api', 'modules', 'resellers.py')
ROUTER = os.path.join(ROOT, 'api', 'routers', 'licenses.py')
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'procurement',
                    'digital-reform-licenses.blade.php')


def _load():
    spec = importlib.util.spec_from_file_location("_resellers_under_test", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # ⚠ Not a MagicMock: the conftest mock would "provide" merge() too.
    assert callable(mod.merge) and mod.__file__ == MODULE
    return mod


def _view():
    with open(VIEW, encoding='utf-8') as fh:
        return fh.read()


def _router():
    with open(ROUTER, encoding='utf-8') as fh:
        return fh.read()


# ---------------------------------------------------------------- the merge

def test_spelling_variants_of_one_vendor_merge_across_sources():
    """The measured case: contracts store "DELL MARKETING LP", the notice feed
    writes "Dell Marketing L.P." and "Dell Marketing, LP" — one company, three
    spellings. The merge must list it ONCE, under the contract spelling."""
    m = _load()
    out = m.merge(["DELL MARKETING LP"],
                  [{"vendor": "Dell Marketing L.P."},
                   {"vendor": "Dell Marketing, LP"},
                   {"vendor": "SHI International Corp."}])
    assert out["total"] == 2
    assert out["contract"] == 1
    assert out["notice_only"] == 1
    assert out["names"][0] == {"name": "DELL MARKETING LP", "notice_only": False}
    assert out["names"][1] == {"name": "SHI International Corp.", "notice_only": True}


def test_legal_suffixes_are_never_stripped():
    """"Mythics Inc" and "MYTHICS LLC" must stay TWO names. Suffix-stripping is
    how the NYCHA crosswalk once auto-linked different firms onto one record
    (#148); the conservative cost here is only a duplicate name in a list."""
    m = _load()
    out = m.merge(["MYTHICS LLC"], [{"vendor": "Mythics Inc"}])
    assert out["total"] == 2
    assert out["notice_only"] == 1


def test_counts_are_full_while_names_are_capped():
    """Count before you cap: 6 contract + 3 notice-only vendors must report
    total 9 while showing NAME_CAP names."""
    m = _load()
    out = m.merge([f"VENDOR {i}" for i in range(6)],
                  [{"vendor": f"Notice Vendor {i}"} for i in range(3)])
    assert out["total"] == 9
    assert out["contract"] == 6
    assert out["notice_only"] == 3
    assert len(out["names"]) == m.NAME_CAP


def test_the_overlap_dedup_sees_past_the_display_cap():
    """The defect the full-list requirement exists for: a notice vendor matching
    a contract vendor BEYOND the display cap must still dedup, not count as
    notice-only. With a capped contract list, "Vendor 5" (position 6) would be
    invisible to the dedup and its notice spelling would double-count."""
    m = _load()
    contract = [f"VENDOR {i}" for i in range(6)]        # positions 0-5, cap is 4
    out = m.merge(contract, [{"vendor": "vendor 5"},     # spelling of position 6
                             {"vendor": "Genuinely New LLC"}])
    assert out["notice_only"] == 1, "the past-the-cap overlap was double-counted"
    assert out["total"] == 7


def test_duplicate_skeletons_within_one_source_collapse():
    """Two spellings of one vendor INSIDE the contract list are one vendor.
    (Measured 2026-08-22: zero families currently have this, so the Vendors
    column and `contract` agree exactly — this pins the behaviour that keeps
    the merge correct if a source ever grows a second spelling.)"""
    m = _load()
    out = m.merge(["MYTHICS LLC", "MYTHICS, LLC."], [])
    assert out["contract"] == 1
    assert out["total"] == 1


def test_empty_and_missing_inputs_degrade_cleanly():
    m = _load()
    out = m.merge([], None)
    assert out == {"names": [], "total": 0, "contract": 0, "notice_only": 0}
    # A blank name must never occupy a slot or a count.
    out = m.merge(["", None], [{"vendor": ""}])
    assert out["total"] == 0


# ---------------------------------------------------------------- the router

def test_the_family_agg_call_keeps_vendor_names():
    """Bug 4: without keep_vendor_names=True the merge receives an empty list
    for every family, contract counts read 0 across the table, and nothing
    raises. Walk balanced parens FROM THE CALL SITE, excluding the def — a
    regex over raw text once matched the function's own signature and stayed
    green with the argument deleted from the real call."""
    src = _router()
    sites = []
    for mm in re.finditer(r'_agg\(', src):
        # Exclude the definition.
        if src[max(0, mm.start() - 20):mm.start()].rstrip().endswith('def'):
            continue
        depth, i = 1, mm.end()
        while depth and i < len(src):
            depth += {'(': 1, ')': -1}.get(src[i], 0)
            i += 1
        sites.append(src[mm.start():i])
    assert len(sites) > 5, "the _agg call sites moved; re-anchor this guard"
    fam_calls = [s for s in sites if '"family"' in s]
    assert fam_calls, "no _agg(rows, \"family\") call found"
    # Exactly the licenses() rollup keeps names; the family() endpoint's own
    # _agg('family') (if any) is matched too, so require at least one keeper.
    assert any('keep_vendor_names=True' in s for s in fam_calls), \
        "the family rollup no longer keeps vendor names — the merge gets []"


def test_the_router_merges_through_the_one_owner():
    """The merge rules (skeleton dedup, no suffix-stripping, full-set counts)
    live in modules/resellers. A second inline merge is how two tables end up
    disagreeing about who sells a product."""
    src = _router()
    assert 'resellers.merge(' in src
    assert 'def _merge_resellers' not in src


# ------------------------------------------------------------------ the view

def _family_table(view):
    """The licFamilyTable block, thead through the end of its tbody."""
    m = re.search(r'<table class="db-table" id="licFamilyTable">.*?</table>',
                  view, re.DOTALL)
    assert m, "licFamilyTable is gone — re-anchor this guard"
    return m.group(0)


def test_the_view_renders_the_column_with_its_sort_key():
    """The cell's visible text is names — not monotonic in the count — so it
    needs data-order (#248). Anchor on the CELL STATEMENT, not the first
    mention of the variable: a cap-sentence guard once matched an assignment in
    a @php block and passed against a stale sentence."""
    tbl = _family_table(_view())
    # ⚠ RE-EXPRESSED 2026-09-18, never relaxed. The column was renamed "Sellers"
    # and now renders the merged COUNT rather than the names -- the names cost
    # the table its width (Microsoft's cell ran to "+28 more") and every one is
    # on the family page under "Who sells it". The property this guard protects
    # is unchanged: the cell exists and sorts on the merged total.
    assert '<th class="lic-num">Sellers</th>' in tbl
    cell = re.search(
        r'<td[^>]*data-order="\{\{ \(int\) \(\$res\[.total.\] \?\? 0\) \}\}"',
        tbl)
    assert cell, "the Bought through cell lost its data-order sort key"


def test_every_row_shape_matches_the_header():
    """Defect 3 of the reorg phases: a moved table shipped with a structural
    hole and nothing failed. Count <th> in the header and <td> per row template
    — the family row and the generic row must both carry one cell per column."""
    tbl = _family_table(_view())
    n_th = len(re.findall(r'<th[ >]', tbl))
    body = tbl.split('</thead>', 1)[1]
    fam_row = body.split('@foreach($fams as $f)', 1)[1].split('@endforeach', 1)[0]
    n_fam_td = len(re.findall(r'<td[ >]', fam_row))
    assert n_fam_td == n_th, f"family row has {n_fam_td} cells for {n_th} columns"
    gen_row = body.split('@if($generic)', 1)[1].split('@endif', 1)[0]
    n_gen_td = len(re.findall(r'<td[ >]', gen_row))
    assert n_gen_td == n_th, f"generic row has {n_gen_td} cells for {n_th} columns"


def test_the_notice_claim_only_renders_when_the_notice_half_loaded():
    """Defect 5: if notice_product_links never built, the column serves contract
    vendors only — and a note still describing notice coverage would be the
    stale-disclosure defect. The sentence naming City Record notices must sit
    inside the @if($resNotice) branch, and the note must never type the
    measured figures as literals (the typed-figure defect: it renders the
    served counts)."""
    view = _view()
    # ⚠ RE-EXPRESSED 2026-09-18: the note's heading follows the column's rename to
    # "Sellers". Same note, same branch on notice availability.
    note = re.search(r'<strong>Sellers</strong>.*?</p>', view, re.DOTALL)
    assert note, "the sources note is gone"
    note = note.group(0)
    m = re.search(r'@if\(\$resNotice\)(.*?)@else(.*?)@endif', note, re.DOTALL)
    assert m, "the note no longer branches on notice availability"
    inside, fallback = m.group(1), m.group(2)
    assert 'City Record notice' in inside
    assert 'City Record notice' not in fallback
    # Figures come from the payload, never typed: no bare number that could be
    # the stale "531" sits in the prose (digits inside {{ }} are fine).
    prose = re.sub(r'\{\{.*?\}\}', '', note, flags=re.DOTALL)
    assert not re.search(r'\b\d{2,}\b', prose), \
        "a typed figure crept into the sources note — serve it instead"
