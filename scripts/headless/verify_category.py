"""The Ten-Year category page, verified on the RENDERED table.

⚠ A 200 says the page did not crash. It says nothing about whether the table
holds the spine's projects or the retired series' — which is the whole point of
this change. Read the DataTable's row count and its money, not the status code.
"""
from playwright.sync_api import sync_playwright
import sys, json, urllib.request
CASES = [("utility-relocation-for-se-and-wm-projects", 268),
         ("neighborhood-parks-playgrounds-and-ballfields", 1036),
         ("routine-reconstruction", 447)]
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])
    for slug, want in CASES:
        with urllib.request.urlopen(
            "http://localhost:8581/get/capital/projects/by-category/"+slug) as f:
            served=json.load(f)
        pg=b.new_page(viewport={"width":1440,"height":1000})
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8580/projects/categories/"+slug,
                wait_until="load", timeout=60000)
        pg.wait_for_timeout(4000)
        r=pg.evaluate("""() => {
          const t=$('table.dataTable').DataTable ? null : null;
          const api=window.jQuery && jQuery.fn.dataTable
            ? jQuery('table').filter((i,e)=>jQuery.fn.dataTable.isDataTable(e)) : [];
          let rows=null, first=[];
          let shown=null, colSearch=null;
          if (api.length) { const d=jQuery(api[0]).DataTable(); rows=d.page.info().recordsTotal;
            // ⚠⚠ `recordsDisplay` TOO. This verifier read only `recordsTotal` and
            // passed for weeks while the page rendered 409 rows of 447 — an
            // ungated `columns([1])` was filtering every category page to one
            // arbitrary agency, and `recordsTotal` is the count BEFORE the
            // search. The tiles above the table sum the SEARCHED rows, so the
            // page published that agency's totals under a category heading: a
            // Parks category read 1 project / $110K against 367 / $1.07B.
            shown=d.page.info().recordsDisplay;
            colSearch=d.columns().search().toArray().map((x,k)=>x?k+':'+x:null).filter(Boolean);
            first=d.row(0).data()? Object.values(d.row(0).data()).slice(0,3):[]; }
          const h1=document.querySelector('h2');
          return {rows, shown, colSearch, heading:h1?h1.innerText.trim():null,
                  tiles:[...document.querySelectorAll('.prj_stat')].map(e=>e.innerText.trim()),
                  blankTiles:[...document.querySelectorAll('.prj_stat')]
                    .filter(e=>!e.innerText.trim()).length,
                  money:[...document.querySelectorAll('td span[data-content]')]
                        .slice(0,3).map(e=>e.getAttribute('data-content'))};
        }""")
        print(f"\n  /projects/categories/{slug}")
        print(f"    endpoint {served['count']} | table {r['rows']} | expected ~{want}")
        print(f"    heading: {r['heading']}")
        print(f"    money (data-content): {r['money']}")
        print(f"    tiles: {r['tiles']}")
        if r['rows'] != served['count']:
            print(f"    FAIL table {r['rows']} != endpoint {served['count']}"); ok=False
        if r['shown'] != served['count']:
            print(f"    FAIL only {r['shown']} of {served['count']} rows shown "
                  f"— a filter is cutting the table: {r['colSearch']}"); ok=False
        # ⚠ A blank is not a zero and not an error. The five tiles are hydrated
        # by `loadFinStat()`, whose only caller once lived inside the
        # publication-date block — gating that block left all five reading
        # `&nbsp;` with zero requests and zero JS errors.
        if r['blankTiles']:
            print(f"    FAIL {r['blankTiles']} blank stat tiles — their "
                  f"hydration has lost its caller"); ok=False
        if served['count'] < want*0.9:
            print(f"    FAIL endpoint {served['count']} far below expected {want}"); ok=False
        # ⚠ THE UNIT TRAP: the spine is USD, the retired series was THOUSANDS. A
        # figure a thousand times too large looks entirely plausible.
        for m in r['money']:
            if m and m.startswith('$'):
                v=float(m[1:].replace(',',''))
                if v > 5e10:
                    print(f"    FAIL money {m} implausible — the x1000 multiplier is back"); ok=False
        if errs: print(f"    FAIL uncaught JS {errs[:2]}"); ok=False
        pg.close()
    b.close()
print("\nCATEGORY OK" if ok else "\nCATEGORY FAILED"); sys.exit(0 if ok else 1)
