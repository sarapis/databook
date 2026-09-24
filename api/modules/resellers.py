"""One owner for the family table's "Bought through" merge — the vendors on a
family's own contracts plus the awarded-to vendors from City Record notices
naming the product, deduped across the two sources' spellings.

⚠ WHAT THIS IS, AND IS NOT. Contract vendors and resellers-via-notices are what
the data supports (measured 2026-08-22: 531 award notices carry a vendor, across
249 families). It is NOT sub-vendor / supply-chain coverage — the `sub_vendor`
column in `contracts` holds 2 distinct values and is a dud — and no consumer of
this module may present it as such. The notice half is the part contract data
cannot give at product grain: the Microsoft family holds 6 contract vendors and
30 distinct notice awardees, and the $67.5M ELA award names Dell Marketing,
where the family's own largest contract rows do too.

⚠ THE DEDUP IS A STRICT ALPHANUMERIC SKELETON, NEVER SUFFIX-STRIPPING. The two
sources spell one company three ways — contracts store "DELL MARKETING LP",
the notice feed writes "Dell Marketing L.P." and "Dell Marketing, LP" — and the
skeleton collapses exactly those. It deliberately does NOT strip legal suffixes:
"Mythics Inc" and "MYTHICS LLC" stay two names, because suffix-stripping is how
the NYCHA crosswalk once auto-linked different firms onto one record (#148).
The cost of the conservative miss is one duplicate name in a display list.

⚠ COUNTS ARE COMPUTED ON THE FULL SETS; ONLY `names` IS CAPPED. The caller must
pass the UNCAPPED contract vendor list — deduping notice vendors against a
display-capped list overcounts the notice-only remainder for any family with
more contract vendors than the cap, which is the count-before-you-cap defect at
a new surface.
"""
import re

# Names shown in the family table cell before "+N more". Display only — every
# count in merge()'s result is measured on the full sets.
NAME_CAP = 4


def norm_vendor(name):
    """Alphanumeric skeleton of a vendor name, uppercased. Punctuation, spacing
    and case are the only things that vary between the two sources' spellings of
    one company; legal suffixes are kept (see the module docstring)."""
    return re.sub(r"[^A-Z0-9]", "", (name or "").upper())


def merge(contract_names, notice_rows, cap=NAME_CAP):
    """One family's "Bought through" rollup.

    `contract_names`: the family's contract vendor names, FULL and value-ranked
    (they are the paid relationships, so they lead the list and keep their own
    spelling). `notice_rows`: [{"vendor": ...}, ...] in the caller's ranking —
    award amount first, matching the notice panel (#288).

    `cap` is DISPLAY ONLY and the caller chooses it, because the two consumers
    are different shapes: NAME_CAP=4 fits the index's table CELL, and the family
    PAGE has a section to fill, where "+26 more" is the whole finding hidden
    behind a number. ⚠ It must never reach the counts — they are measured on the
    full sets above the slice, which is what lets the page and the index agree
    on 32 while showing different numbers of names.

    Returns {"names": [{"name", "notice_only"}, ...] capped at NAME_CAP,
    "total", "contract", "notice_only"} — a notice_only name holds no contract
    in this set, and the view marks it so a reader can weigh the evidence.
    """
    seen = set()
    merged = []
    for n in contract_names or []:
        k = norm_vendor(n)
        if not k or k in seen:
            continue
        seen.add(k)
        merged.append({"name": n, "notice_only": False})
    contract_count = len(merged)
    notice_only = 0
    for v in notice_rows or []:
        k = norm_vendor(v.get("vendor"))
        if not k or k in seen:
            continue
        seen.add(k)
        notice_only += 1
        merged.append({"name": v["vendor"], "notice_only": True})
    return {
        "names": merged[:cap],
        "total": contract_count + notice_only,
        "contract": contract_count,
        "notice_only": notice_only,
    }
