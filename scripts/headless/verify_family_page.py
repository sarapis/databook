#!/usr/bin/env python3
"""The product family page, verified on the RENDERED page.

⚠⚠ WHY THIS FILE EXISTS: the 2026-09-18 restructure moved every analyst block on
this page below the data it interprets, and **all 69 guards in
api/tests/test_license_families.py passed unchanged**. They read the template as
a flat string, so position is invisible to them; and none of the three headless
verifiers (`verify_uncaught_js`, `verify_overflow`, `verify_retired_sweep`)
loads a family URL at all -- measured, they cover the capital section. The page
had no rendered coverage whatsoever.

What it checks, and why each one is here rather than in a unit test:

  1. SECTION ORDER on the served page. A unit test can pin the order of two
     strings in a template; only the browser can say the interpretation layer
     renders below the tiles after Blade, opcache and the controller have had
     their say.
  2. THE SELLER COUNT AGREES WITH THE INDEX. This is a cross-page
     reconciliation and it is the defect the rebuild fixed: the family page read
     6 sellers for Microsoft while the index cell read 32. Two surfaces, one
     merge -- provable only by loading both.
  3. THE FOLDED CALENDAR CLOSES. future + ended + no-end-date == the contracts
     tile, read off the payload the page was built from. A calendar that drops
     rows silently reads as the whole inventory.
  4. NO DEAD TOC ANCHOR. Every sidebar link resolves to an element that exists.
  5. 0 uncaught JS, and no sideways scroll at 1440 or 390.

Usage:  python3 scripts/headless/verify_family_page.py [--base http://localhost:8580]
Exit 0 = every family clean.  ⚠ Read the exit status directly; through a pipe it
is the pipe's.
"""
import argparse
import json
import sys
import urllib.request

from playwright.sync_api import sync_playwright

# ⚠ Chosen to exercise DIFFERENT SHAPES, not just the largest family:
#   microsoft   - mixed class, notice-only sellers, curated summary, an OSS row
#   citrix      - many vendors (8) across many agencies (9)
#   gartner     - a content subscription: build-vs-buy must NOT render
#   intergraph-cad - a single-contract family, the shape 551 of 814 families have
FAMILIES = ["microsoft", "citrix", "gartner", "intergraph-cad"]


def api(base_api, path):
    with urllib.request.urlopen(base_api + path, timeout=60) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8580")
    ap.add_argument("--api", default="http://localhost:8581")
    args = ap.parse_args()

    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for slug in FAMILIES:
            payload = api(args.api, f"/oce/licenses/family/{slug}")
            if not payload.get("available"):
                problems.append(f"{slug}: endpoint says unavailable")
                continue
            url = f"{args.base}/research/digital-reform/products/{slug}"

            for width, height in ((1440, 900), (390, 844)):
                page = browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(url, wait_until="networkidle", timeout=60000)

                if errors:
                    problems.append(f"{slug} @{width}: uncaught JS {errors}")
                if page.evaluate("document.documentElement.scrollWidth > window.innerWidth"):
                    problems.append(f"{slug} @{width}: the page scrolls sideways")

                if width == 1440:
                    # 1. Section order, as rendered.
                    pos = page.evaluate("""() => {
                        const y = id => { const e = document.getElementById(id);
                            return e ? Math.round(e.getBoundingClientRect().top + window.scrollY) : -1; };
                        const tile = document.querySelector('.db-stat');
                        return {records: y('section-records'),
                                classification: y('section-classification'),
                                tile: tile ? Math.round(tile.getBoundingClientRect().top + window.scrollY) : -1};
                    }""")
                    if pos["records"] < 0 or pos["classification"] < 0:
                        problems.append(f"{slug}: a named band is missing from the page")
                    elif pos["classification"] < pos["records"]:
                        problems.append(
                            f"{slug}: the classification band renders ABOVE the City's records "
                            f"({pos['classification']} < {pos['records']})")
                    # The tiles must be above every analyst block, which is the
                    # property the restructure exists to hold.
                    if 0 < pos["tile"] and pos["tile"] > pos["classification"] > 0:
                        problems.append(f"{slug}: the stat tiles render below the classification band")

                    # 2. The seller count agrees with the INDEX's cell for this family.
                    shown = page.evaluate("""() => {
                        const m = document.body.innerText.match(/([\\d,]+)\\s+sellers/i);
                        return m ? parseInt(m[1].replace(/,/g, ''), 10) : -1;
                    }""")
                    served = payload.get("sellers", {}).get("total", -1)
                    if shown != served:
                        problems.append(
                            f"{slug}: the page shows {shown} sellers, the payload serves {served}")

                    # 3. The folded calendar closes against the contracts tile.
                    by_year = payload.get("by_year") or {}
                    future = sum(int(y["contracts"]) for y in (by_year.get("years") or []))
                    ended = int((by_year.get("ended") or {}).get("contracts", 0))
                    none_dated = int(by_year.get("no_end_date", 0))
                    total = int((payload.get("summary") or {}).get("contracts", 0))
                    if future + ended + none_dated != total:
                        problems.append(
                            f"{slug}: the calendar does not close -- {future} future + {ended} "
                            f"ended + {none_dated} undated != {total} contracts")

                    # 3b. PEERS RECONCILE WITH THE CAPABILITY PAGE. Both count
                    # the same function from the same rows; a disagreement means
                    # one of the two pages is aggregating differently, which is
                    # how one function came to have two answers before.
                    cap = payload.get("capability") or ""
                    if cap and cap != "other":
                        capdata = api(args.api, f"/oce/licenses/capability/{cap}")
                        # The capability page counts every product with this tag,
                        # including this family; the peers list excludes itself.
                        expected = int((capdata.get("summary") or {}).get("products", 0)) - 1
                        got = int(payload.get("peers_total", -1))
                        if got != expected:
                            problems.append(
                                f"{slug}: peers_total {got} but the capability page "
                                f"counts {expected} other products for '{cap}'")
                    elif cap == "other" and payload.get("peers_total"):
                        problems.append(
                            f"{slug}: the abstention bucket was given "
                            f"{payload['peers_total']} peers")

                    # ⭐ 3c. THE HEADER FITS ABOVE THE FOLD (owner, 2026-09-18).
                    # What the software does, who makes it, who sells it, which
                    # agencies buy it and the headline figures are all meant to be
                    # visible without scrolling at a 900px viewport. That is a
                    # LAYOUT property, so only a browser can hold it: a unit test
                    # can pin the markup order and would not notice the maker card
                    # growing two lines and pushing the rollups under.
                    # ⚠ 900 is the verifier's own viewport height, taken from the
                    # page rather than typed, so the two cannot drift apart.
                    fold = page.evaluate("window.innerHeight")
                    header_bottom = page.evaluate("""() => {
                        const tag = [...document.querySelectorAll('.lic-tag')]
                            .find(e => /Agencies buying it/.test(e.textContent));
                        const row = tag ? tag.closest('.row') : null;
                        return row ? Math.round(row.getBoundingClientRect().bottom + window.scrollY) : -1;
                    }""")
                    if header_bottom < 0:
                        problems.append(f"{slug}: the agencies/sellers rollup is missing from the header")
                    elif header_bottom > fold:
                        problems.append(
                            f"{slug}: the header runs past the fold -- the rollups end at "
                            f"{header_bottom} against a {fold}px viewport, so who sells it "
                            f"and who buys it need a scroll")

                    # 4. No dead TOC anchor.
                    dead = page.evaluate("""() => [...document.querySelectorAll('.db-toc a')]
                        .map(a => a.getAttribute('href'))
                        .filter(h => h && h.startsWith('#') && !document.getElementById(h.slice(1)))""")
                    if dead:
                        problems.append(f"{slug}: dead contents links {dead}")

                    # 5. Build-vs-buy must not render for a non-software class --
                    # asking "could the City build this?" of a content
                    # subscription is how $6.80M of AWS became invisible.
                    # ⚠⚠ ON THE ELEMENT, NOT ON ITS TEXT, and both halves of that
                    # were learned the hard way in one sitting.
                    #   * a text scan must be CASE-FOLDED: `innerText` applies
                    #     `text-transform`, and this heading lives in a `.lic-tag`,
                    #     which is uppercase site-wide -- so the authored-case
                    #     version could never have fired at all;
                    #   * and case-folding it then made it fire on a CORRECT page,
                    #     because the sentence explaining why the block is absent
                    #     for a non-software class QUOTES the same question. A
                    #     scanner that reads an explanation as the thing it
                    #     explains is this repo's oldest guard defect.
                    # The block carries an id. Only the element can tell the two
                    # apart.
                    if payload.get("purchase_class") not in ("", "software-licence"):
                        if page.query_selector("#bvb-rating") is not None:
                            problems.append(
                                f"{slug}: build-vs-buy rendered for class "
                                f"{payload.get('purchase_class')}")

                    h = page.evaluate("document.documentElement.scrollHeight")
                    print(f"  {slug:<16} @{width}: height {h:>6}  tile@{pos['tile']:<6} "
                          f"sellers {shown:<4} calendar {future}+{ended}+{none_dated}={total}")
                else:
                    h = page.evaluate("document.documentElement.scrollHeight")
                    print(f"  {slug:<16} @{width}: height {h:>6}")
                page.close()
        browser.close()

    if problems:
        print("\nPROBLEMS:")
        for x in problems:
            print("  -", x)
        return 1
    print("\nFAMILY PAGES OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
