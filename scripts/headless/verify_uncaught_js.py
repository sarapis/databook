"""Uncaught JS across the site, because `script.js` is loaded on every page.

⚠⚠ THE DEFECT THIS EXISTS TO CATCH RAN ON EVERY ORG PROFILE. `fapireq`'s
success branch called back a BARE ARRAY when a payload had no `rows` key, and
DataTables' own ajax callback reads `.data.length` — so `.data` was `undefined`
and it threw `Cannot read properties of undefined (reading 'length')`. Measured
2026-09-10: **1 uncaught error on 5 of 5 org profiles**, from
`/get/orgs/section/{id}/nycjobs`, which returns a bare `[]`. Not an edge case
there — of that page's ~44 payloads, 14 carry `rows` and ~30 are bare lists.

⚠ It survived because "did this page throw?" was unanswerable while it threw:
one error per page load is indistinguishable from the page's normal noise unless
something asserts zero. This repo has made that argument before — the six
`/get/pstats-records_no/*` 404s were guarded for exactly this reason.

⚠⚠ AND ZERO ERRORS IS NOT ENOUGH ON ITS OWN. A fix that silenced the throw by
handing DataTables an empty set would pass an error-only check, so this also
records every DataTable's `recordsTotal` and fails if a page that had rows
stops having them. The baseline is measured, not guessed: it was taken with the
change and re-taken with it stashed, and the two agreed on every table.
"""
from playwright.sync_api import sync_playwright
import sys

# (path, {table id: expected recordsTotal}) — a table absent from the map is
# recorded but not asserted, so a new table does not fail this check.
# ⚠ These counts were A/B'd against the pre-fix build and were IDENTICAL; the
# only thing the fix changed was the error count.
PAGES = [
    ("/o/170010846-x", {"jobTable": 0, "myTable": 0}),
    ("/o/170020034-x", {"jobTable": 0, "myTable": 0}),
    ("/o/170010998-x", {}),
    ("/o/170011008-x", {}),
    ("/o/170010850-x", {}),
    ("/", {}),
    ("/districts", {}),
    ("/schools", {}),
    ("/procurement", {}),
    ("/organizations", {"orgsTable": 267}),
    ("/projects", {}),
    ("/p/826HED-545", {}),
    ("/projects/categories/routine-reconstruction", {"myTable": 447}),
    ("/projects/budget-lines/EP%200007", {"myTable": 60, "commDatatable": 82}),
    ("/notices/procurement", {}),
]

ok = True
with sync_playwright() as p:
    b = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-gl=swiftshader"])
    for path, expect in PAGES:
        pg = b.new_page(viewport={"width": 1440, "height": 1000})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:90]))
        try:
            pg.goto("http://localhost:8580" + path, wait_until="load", timeout=60000)
        except Exception as exc:
            print(f"  {path:46s} FAIL could not load: {exc}")
            ok = False
            pg.close()
            continue
        pg.wait_for_timeout(4500)
        tables = pg.evaluate("""() => {
          const out = {};
          if (window.jQuery && jQuery.fn.dataTable)
            jQuery('table').each(function () {
              if (jQuery.fn.dataTable.isDataTable(this))
                out[this.id] = jQuery(this).DataTable().page.info().recordsTotal;
            });
          return out;
        }""")
        print(f"  {path:46s} JS={len(errs)}  tables={tables}")
        if errs:
            print(f"      FAIL uncaught JS: {errs[:2]}")
            ok = False
        for tid, want in expect.items():
            got = tables.get(tid)
            if got is None:
                print(f"      FAIL table #{tid} is gone")
                ok = False
            elif got != want:
                print(f"      FAIL table #{tid} holds {got}, expected {want} — a "
                      f"silenced error that empties a table looks like a fix")
                ok = False
        pg.close()
    b.close()
print("\nUNCAUGHT JS OK" if ok else "\nUNCAUGHT JS FAILED")
sys.exit(0 if ok else 1)
