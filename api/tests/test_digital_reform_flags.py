"""Renewal Review Queue flag heuristics (api/routers/oce.py)."""
from routers.oce import (
    _build_your_own_reason,
    _review_flags,
    COMPETITIVE_PROCUREMENT_METHODS,
    NONCOMPETITIVE_REVIEW_METHODS,
)


def _keys(row, days):
    return {f["key"] for f in _review_flags(row, days)}


def test_build_your_own_matches_website_keyword():
    assert _build_your_own_reason("Citywide WEBSITE redesign") == "Website / CMS / portal"
    assert _build_your_own_reason("Chatbot for 311 triage").startswith("Chatbot")


def test_build_your_own_ignores_unrelated_hardware():
    assert _build_your_own_reason("Bulk laptop and server hardware purchase") is None


def test_noncompetitive_flag_set_for_sole_source():
    keys = _keys({"procurement_method": "Sole Source", "award_amount": 5000}, 900)
    assert "non_competitive" in keys


def test_competitive_method_not_flagged():
    for method in COMPETITIVE_PROCUREMENT_METHODS:
        keys = _keys({"procurement_method": method.title(), "award_amount": 5000}, 900)
        assert "non_competitive" not in keys


def test_noncompetitive_means_sole_source_or_negotiated_only():
    """Owner, 2026-09-24: the flag sat on 605 of 634 renewals because it counted
    M/WBE small purchases, GSA/OGS piggybacks and renewals as non-competition.
    Those routes are shown by method; only no-competition-at-all is flagged."""
    assert NONCOMPETITIVE_REVIEW_METHODS == {"sole source", "negotiated acquisition"}
    for method in ("Negotiated Acquisition", "Sole Source"):
        assert "non_competitive" in _keys({"procurement_method": method, "award_amount": 5000}, 900)
    for method in ("MWBE Non Competitive Small Purchase", "Intergovernmental GSA",
                   "Intergovernmental OGS", "Renewal", "Amendment", "Subscription",
                   "Micropurchase", "Line Item Appropriation"):
        assert "non_competitive" not in _keys({"procurement_method": method, "award_amount": 5000}, 900), method


def test_no_open_solicitation_is_no_longer_a_flag():
    """Retired 2026-09-24: it searched the expiring contract's OWN PIN for a
    rebid that is always issued under a new one (flagged 633 of 634). The
    dossier states whether a successor is on record instead."""
    import inspect
    from routers import oce
    assert "has_rebid" not in inspect.signature(_review_flags).parameters
    for method in ("Competitive Sealed Bid", "Renewal", ""):
        assert "no_rebid" not in _keys({"procurement_method": method, "award_amount": 5000}, 900)
    assert "no_rebid" in oce.RETIRED_REVIEW_FLAGS, "an old expiring_flag=no_rebid link would empty the queue"


def test_scope_growth_flag():
    row = {"procurement_method": "Competitive Sealed Bid",
           "award_amount": 100_000, "current_amount": 300_000}
    assert "scope_growth" in _keys(row, 900)
    # No growth → no flag.
    row2 = {"procurement_method": "Competitive Sealed Bid",
            "award_amount": 100_000, "current_amount": 100_000}
    assert "scope_growth" not in _keys(row2, 900)


def test_high_value_near_term_flag():
    row = {"procurement_method": "Competitive Sealed Bid", "award_amount": 2_000_000}
    assert "high_value_near_term" in _keys(row, 100)      # ≤365 days
    assert "high_value_near_term" not in _keys(row, 800)  # far out
    # Small contract expiring soon → not flagged.
    small = {"procurement_method": "Competitive Sealed Bid", "award_amount": 5000}
    assert "high_value_near_term" not in _keys(small, 100)


def test_build_your_own_flag_appears_in_review_flags():
    row = {"procurement_method": "Competitive Sealed Bid", "award_amount": 5000,
           "contract_title": "Public-facing WEBSITE and portal maintenance"}
    assert "build_your_own" in _keys(row, 900)


def test_vendor_lock_in_flag_thresholds():
    row = {"procurement_method": "Competitive Sealed Bid", "award_amount": 5000}
    # Many contracts → lock-in.
    assert "vendor_lock_in" in _keys2(row, {"cnt": 25, "agencies": 1, "total": 1_000_000})
    # Many agencies → lock-in.
    assert "vendor_lock_in" in _keys2(row, {"cnt": 2, "agencies": 6, "total": 1_000})
    # High total → lock-in.
    assert "vendor_lock_in" in _keys2(row, {"cnt": 1, "agencies": 1, "total": 160_000_000})
    # Moderate footprint (below all thresholds) → no flag.
    assert "vendor_lock_in" not in _keys2(row, {"cnt": 10, "agencies": 4, "total": 80_000_000})


def _keys2(row, vendor_stats):
    return {f["key"] for f in _review_flags(row, 900, vendor_stats)}


def _flags(row, **kw):
    return {f["key"] for f in _review_flags(
        row, kw.get("days", 900),
        kw.get("vendor_stats"), kw.get("va_stats"),
        kw.get("spent"), kw.get("days_since_start"))}


def test_underused_flag_when_low_spend():
    row = {"procurement_method": "Competitive Sealed Bid", "award_amount": 2_000_000,
           "start_year": "2023"}
    # Big, active 600 days, only 5% spent → shelfware.
    assert "underused" in _flags(row, spent=100_000, days_since_start=600)
    # Healthy spend → not flagged.
    assert "underused" not in _flags(row, spent=1_500_000, days_since_start=600)
    # Spend predates the scan window (started 2020) → suppressed to avoid false positive.
    old = {**row, "start_year": "2020"}
    assert "underused" not in _flags(old, spent=100_000, days_since_start=600)
    # No spend data at all → not flagged.
    assert "underused" not in _flags(row, spent=None, days_since_start=600)


def _flags_enr(row, enrich):
    return {f["key"] for f in _review_flags(row, 900, None, None, None, None, enrich)}


def test_build_your_own_uses_ai_rating_when_present():
    row = {"procurement_method": "Competitive Sealed Bid", "award_amount": 5000,
           "contract_title": "Public website redesign"}  # heuristic would match
    # AI says high → flagged.
    assert "build_your_own" in _flags_enr(row, {"build_vs_buy": "high", "rationale": "Simple site."})
    # AI says medium/low → NOT flagged, and AI overrides the keyword heuristic.
    assert "build_your_own" not in _flags_enr(row, {"build_vs_buy": "medium", "rationale": "x"})
    assert "build_your_own" not in _flags_enr(row, {"build_vs_buy": "low", "rationale": "x"})


def test_build_your_own_falls_back_to_heuristic_without_enrichment():
    row = {"procurement_method": "Competitive Sealed Bid", "award_amount": 5000,
           "contract_title": "Citywide website and portal"}
    assert "build_your_own" in _flags_enr(row, {})  # no build_vs_buy → heuristic


def test_renewal_chain_flag():
    # Renewal procurement method → flagged.
    assert "renewal_chain" in _flags(
        {"procurement_method": "Renewal", "award_amount": 5000, "agency": "DOITT"})
    # Competitive but many contracts with same vendor+agency → flagged.
    assert "renewal_chain" in _flags(
        {"procurement_method": "Competitive Sealed Bid", "award_amount": 5000, "agency": "DOITT"},
        va_stats={"cnt": 5, "since": "2016", "total": 9_000_000})
    # Competitive, only a couple contracts → not flagged.
    assert "renewal_chain" not in _flags(
        {"procurement_method": "Competitive Sealed Bid", "award_amount": 5000, "agency": "DOITT"},
        va_stats={"cnt": 2, "since": "2022", "total": 1_000})


def test_digital_reform_views_keep_php_block_strings_entity_free():
    """⚠ THE REGRESSION THIS EXISTS FOR.

    The Build-vs-buy filter read literally, in the live dropdown:
        High &mdash; easily replaceable
    because `$buildbuyOptions` held `&mdash;` in a PHP string that the template
    echoes through Blade's escaping (`{{ $bl }}`), which turns `&` into `&amp;`.

    It was introduced BY a sweep — #66 converted raw em-dashes to entities to
    keep these pages ASCII-safe, correctly for literal HTML, but this array is
    echoed escaped. The commit even moved the sort-arrow ternaries into
    `{!! !!}` for the same reason, so the mechanism was known; this array was
    just missed. A future ASCII/entity sweep is the likeliest way it recurs.

    Scope is deliberately these two views: every `@php` string in them is
    echoed escaped, so "no entities in a @php block" is exactly right here.
    `nycha_cards.blade.php` legitimately holds `&amp;` in a `@php` string and
    renders it with `{!! !!}`, which is why this is not a tree-wide rule —
    a guard that has to guess the echo mechanism would be worse than none.
    """
    import os
    import re

    root = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
    views = [
        os.path.join(root, 'app/resources/views/procurement/digital-reform-expiring.blade.php'),
        os.path.join(root, 'app/resources/views/procurement/digital-reform.blade.php'),
        os.path.join(root, 'app/resources/views/procurement/digital-reform-licenses.blade.php'),
    ]

    entity = re.compile(r'&(?:[a-zA-Z][a-zA-Z0-9]{1,10}|#[0-9]{2,6});')
    # ⚠ Strip comments first, or this fires on the prose that documents the fix.
    # ⚠⚠ TWO patterns, and the line one must NOT be DOTALL. A single combined
    # `//.*$|/\*.*?\*/` under `MULTILINE | DOTALL` makes `//.*` swallow the whole
    # rest of the block — the first draft did exactly that, blanked line 63 along
    # with everything after it, and passed with the bug reintroduced.
    line_comment = re.compile(r'//[^\n]*')
    block_comment = re.compile(r'/\*.*?\*/', re.DOTALL)

    scanned, offenders = 0, []
    for path in views:
        assert os.path.exists(path), f"guard points at a missing view: {path}"
        src = open(path, encoding='utf-8').read()
        # Every @php ... @endphp block, with real line numbers preserved.
        for block in re.finditer(r'@php(.*?)@endphp', src, re.DOTALL):
            scanned += 1
            base = src[:block.start()].count('\n') + 1
            body = line_comment.sub('', block_comment.sub('', block.group(1)))
            for i, line in enumerate(body.split('\n')):
                hit = entity.search(line)
                if hit:
                    offenders.append(f"{os.path.basename(path)}:{base + i}: {hit.group(0)} in {line.strip()[:80]}")

    # ⚠ A guard that scans nothing passes. Both views carry a @php block.
    assert scanned >= 2, f"scanned only {scanned} @php blocks — the guard stopped looking"
    assert not offenders, (
        "HTML entity in a @php string that Blade will escape (renders literally):\n  "
        + "\n  ".join(offenders))


def test_products_counts_non_competitive_by_the_queues_rule():
    """Owner, 2026-09-24: the Products page's "Non-competitive" column follows the
    queue — sole source or negotiated acquisition. Under the old rule it counted
    every licence, because none used competitive sealed bid or proposal, so the
    column equalled the contract count and said nothing."""
    import os
    src = open(os.path.join(os.path.dirname(__file__), '..', 'routers', 'licenses.py'),
               encoding='utf-8').read()
    assert 'd["no_competition"] = method in NONCOMPETITIVE_REVIEW_METHODS' in src
    assert src.count('if r["no_competition"]') == 3, 'a Products count no longer follows the queue rule'
    assert 'not r["competitive"]' not in src, 'a count still treats every non-sealed-bid route as non-competitive'
