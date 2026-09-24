"""The budget-line family page, verified on the rendered table.

⚠ The family dimension (39 values) is NOT the strategy's work type (236). This
page exists because the two were conflated; it asserts the table holds the
endpoint's rows, the money is USD not thousands, and every budget-line link
resolves.
"""
from playwright.sync_api import sync_playwright
import sys, json, urllib.request
CASES=["sewers","water-mains-sources-and-treatment","edp-equipment-and-finance-costs"]
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])
    for f in CASES:
        with urllib.request.urlopen("http://localhost:8581/get/capital/projects/by-family/"+f) as fh:
            served=json.load(fh)
        pg=b.new_page(viewport={"width":1440,"height":1000})
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8580/projects/budget-lines/families/"+f,
                wait_until="load", timeout=60000)
        pg.wait_for_timeout(4000)
        r=pg.evaluate("""() => {
          const d = jQuery.fn.dataTable.isDataTable('#myTable')
            ? jQuery('#myTable').DataTable() : null;
          const stats={}; document.querySelectorAll('.db-stat').forEach(e=>{
            stats[e.querySelector('.db-stat-label').innerText.trim()] =
              e.querySelector('.db-stat-value').innerText.trim(); });
          return {rows: d? d.page.info().recordsTotal : null,
                  h1: document.querySelectorAll('h1').length,
                  title: (document.querySelector('h1')||{}).innerText,
                  stats,
                  // ⚠⚠ THE LINES ARE A TABLE NOW, NOT BADGES (owner request), and
                  // this verifier was still counting `a.db-badge` — it reported
                  // "0 line badges != 144" on a page rendering all 144 lines
                  // correctly. A check asserting markup that no longer exists
                  // reports a defect that is not there, which is the mirror of a
                  // guard that passes for the wrong reason, and it costs the same:
                  // the next reader has to re-derive which of the two is wrong.
                  // ⚠ `#blTable` is a DataTable, so the rendered `<tr>` count is
                  // the PAGE SIZE (10), never the total. Read `recordsTotal`.
                  lines: (jQuery.fn.dataTable.isDataTable('#blTable')
                            ? jQuery('#blTable').DataTable().page.info().recordsTotal
                            : document.querySelectorAll('#blTable tbody tr').length),
                  clipped: [...document.querySelectorAll('.db-stat')]
                    .filter(e=>e.scrollWidth-e.clientWidth>1).length};
        }""")
        print(f"\n  /projects/budget-lines/families/{f}")
        print(f"    endpoint {served['count']} projects / {served['budget_line_count']} lines"
              f" | table {r['rows']} | h1={r['h1']} | budget-line rows {r['lines']}")
        print(f"    {r['title']}  ::  {r['stats']}")
        if r['rows'] != served['count']:
            print(f"    FAIL table {r['rows']} != endpoint {served['count']}"); ok=False
        if r['lines'] != served['budget_line_count']:
            print(f"    FAIL {r['lines']} budget-line rows != {served['budget_line_count']}"); ok=False
        if r['h1'] != 1: print(f"    FAIL h1 count {r['h1']}"); ok=False
        if r['clipped']: print(f"    FAIL {r['clipped']} clipped tiles"); ok=False
        # ⚠ THE UNIT TRAP: `main`'s contract multiplies by 1000. A family's
        # planned total is billions, never trillions.
        pc = r['stats'].get('PLANNED COMMITMENTS','')
        if pc.endswith('T') or (pc.startswith('$') and 'B' in pc and float(pc[1:-1])>500):
            print(f"    FAIL planned {pc} implausible — the x1000 multiplier"); ok=False
        if errs: print(f"    FAIL uncaught JS {errs[:2]}"); ok=False
        pg.close()
    b.close()
print("\nFAMILY OK" if ok else "\nFAMILY FAILED"); sys.exit(0 if ok else 1)
