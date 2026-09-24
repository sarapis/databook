"""The two SCOPED provenance panels, verified on the RENDERED cells.

⚠⚠ THESE PANELS WERE LEFT NARROW BECAUSE WIDENING THEM PUBLISHED A WRONG ZERO.
`/get/pstats-records_no-by_{category,budgetline}` returned **0** for any table it
had no rule for, and the shared component treats 0 as a CLAIM — "this dataset
holds nothing for this scope, a finding" — distinct from `—`, "we could not
ask". So three of the spine's own sources would each have read `0` beside a
table drawing hundreds of projects from them.

This asserts the three states are three states:
  * a number   where the scope can be counted, agreeing with the endpoint
  * `—`        where the dataset carries no such dimension  (never 0)
  * a marker   where the count came through the project crosswalk rather than
               the table's own column, because those differ by 82 against 568
               on one budget line and must not read as one kind of figure

⚠ And it reads the CELLS, not the payload. The panel is filled by per-row AJAX
after load; a correct endpoint proves nothing about what the row shows — which
is this section's oldest lesson, and the reason five surfaces shipped with
correct payloads above wrong pages.
"""
from playwright.sync_api import sync_playwright
import json
import re
import sys
import urllib.parse
import urllib.request

CASES = [
    # (page, panel id, endpoint stem, scope as the page passes it, expected-scopable)
    ("/projects/categories/routine-reconstruction", "categoryADs",
     "by_category", "routine-reconstruction",
     {"capitalstrategy": "own", "capitalprojectsdollarscomp": "own",
      "capitalprojectslist": "crosswalk", "capitalprojectscommitments": "crosswalk",
      "capprojectsbudgetsandschedule": "own"}),
    ("/projects/budget-lines/" + urllib.parse.quote("EP 0007"), "budgetLineADs",
     "by_budgetline", "EP 0007",
     {"capitalbudget": "own", "capitalcommitmentplan": "own",
      "capitalprojectscommitments": "own", "capitalprojectsdollarscomp": "own",
      "capprojectsbudgetsandschedule": "own", "capitalprojectslist": "crosswalk"}),
]

ok = True
with sync_playwright() as p:
    b = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-gl=swiftshader"])
    for path, panel, stem, scope, expected in CASES:
        served, served_retired = {}, {}
        for tbl in expected:
            url = ("http://localhost:8581/get/pstats-records_no-%s/%s/%s"
                   % (stem, tbl, urllib.parse.quote(scope)))
            with urllib.request.urlopen(url) as f:
                d = json.load(f)
            served[tbl] = (d["rows"][0]["res"], d.get("via"))
            served_retired[tbl] = d.get("retired")

        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8580" + path, wait_until="load", timeout=90000)
        pg.wait_for_timeout(3000)
        # The panel is a collapse; open it so the cells are laid out as a reader
        # sees them, then wait for the per-row fetches.
        pg.evaluate("""(pid) => {
            var el = document.querySelector('#' + pid + ' button.social_btn');
            if (el) el.click();
        }""", panel)
        pg.wait_for_timeout(5000)
        cells = pg.evaluate("""() => {
            var out = {};
            document.querySelectorAll('[id^="stats_"]').forEach(function (e) {
                var badges = [...e.querySelectorAll('.db-badge')]
                    .map(function (b) { return b.textContent; });
                out[e.id.replace(/^stats_/, '')] = {
                    text: (e.textContent || '').trim(),
                    crosswalk_badge: badges.some(function (t) {
                        return /via project/.test(t); }),
                    retired_badge: badges.some(function (t) {
                        return /^retired /.test(t); }),
                };
            });
            var btn = document.querySelector('button.social_btn');
            return {cells: out, sentence: btn ? btn.innerText.trim() : null};
        }""")
        print(f"\n  {path}")
        print(f"    {cells['sentence']}")
        for tbl, want_via in expected.items():
            c = cells["cells"].get(tbl)
            res, via = served[tbl]
            shown = c["text"] if c else "(no cell)"
            print(f"      {tbl:32s} cell {shown:<18s} endpoint {res} via {via}")
            if not c:
                print(f"      FAIL {tbl} renders no cell — the panel was not widened")
                ok = False
                continue
            # ⚠ The cell carries the marker's text too, and `textContent`
            # concatenates it with NO separator ("413via project"), so a
            # `split()` on whitespace reads `413via`. Take the leading number.
            m_ = re.match(r"[\d,]+", c["text"] or "")
            num = m_.group(0).replace(",", "") if m_ else ""
            if via != want_via:
                print(f"      FAIL {tbl} counted via {via}, expected {want_via}")
                ok = False
            if str(res) != num:
                print(f"      FAIL {tbl} cell {c['text']!r} != endpoint {res}")
                ok = False
            # ⚠⚠ THE ASSERTION THAT CATCHES THE DEFECT THIS WORK REMOVED: a
            # source of the spine must never read 0 here.
            if num == "0":
                print(f"      FAIL {tbl} reads 0 — a source of this page's own "
                      f"table cannot hold nothing for its scope")
                ok = False
            if (via == "crosswalk") != c["crosswalk_badge"]:
                print(f"      FAIL {tbl} crosswalk badge={c['crosswalk_badge']} "
                      f"but via={via} — a crosswalked count must be "
                      f"distinguishable from an own-column one")
                ok = False
            # ⚠⚠ AND A RETIRED-SERIES FIGURE MUST BE LABELLED. Measured before
            # this work: the 2023 series' 2,671 sat beside 413 / 953 / 3,465
            # with a BLANK "Last Updated" and nothing naming the retirement.
            if bool(served_retired[tbl]) != c["retired_badge"]:
                print(f"      FAIL {tbl} retired badge={c['retired_badge']} but "
                      f"the endpoint says retired={served_retired[tbl]!r}")
                ok = False

        # ⚠ A table that genuinely cannot be scoped must render `—`, not 0.
        unscopable = pg.evaluate(r"""() => {
            var out = [];
            document.querySelectorAll('[id^="stats_"]').forEach(function (e) {
                // ⚠ Leading number only — a crosswalked cell reads
                // "413via project" because textContent concatenates the badge.
                var t = ((e.textContent || '').trim().match(/^[\d,]+/) || [''])[0];
                if (t === '0') out.push(e.id);
            });
            return out;
        }""")
        if unscopable:
            print(f"      FAIL these cells read 0: {unscopable}")
            ok = False
        if errs:
            print(f"      FAIL uncaught JS {errs[:2]}")
            ok = False
        pg.close()
    b.close()
print("\nSCOPED PROVENANCE OK" if ok else "\nSCOPED PROVENANCE FAILED")
sys.exit(0 if ok else 1)
