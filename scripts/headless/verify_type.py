"""The project-type page: an honest PLAN page, no fabricated project figures.

⚠ It used to LEFT JOIN the retired series for a project count and cost, on a
(publication date, CATEGORY) key — attributing a whole category's projects to
one type. Two thirds of rows got zeros. Those columns are gone; this asserts
they stay gone AND that the page still renders its plan amounts.
"""
from playwright.sync_api import sync_playwright
import sys, json, urllib.request
CASES=["access-for-the-handicapped","animal-care","administration","police-facilities"]
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])
    for t in CASES:
        with urllib.request.urlopen("http://localhost:8581/get/pstats-categories_by_type/"+t) as f:
            served=json.load(f)['rows']
        pg=b.new_page(viewport={"width":1440,"height":1000})
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8580/projects/types/"+t, wait_until="load", timeout=60000)
        pg.wait_for_timeout(3500)
        r=pg.evaluate("""() => {
          const t=document.getElementById('project_type_data');
          const heads=[...t.querySelectorAll('thead th')].map(e=>e.innerText.trim());
          const rows=t.querySelectorAll('tbody tr').length;
          const links=[...t.querySelectorAll('tbody a')].map(a=>a.getAttribute('href'));
          const empty=t.querySelector('tbody .dataTables_empty');
          return {heads, rows: empty?0:rows, links: links.slice(0,2),
                  money:[...t.querySelectorAll('tbody td')].map(e=>e.innerText.trim())
                        .filter(x=>x.startsWith('$')).slice(0,3)};
        }""")
        print(f"\n  /projects/types/{t}")
        print(f"    served {len(served)} | table {r['rows']} rows")
        print(f"    headers: {r['heads']}")
        print(f"    money: {r['money']} | category links: {r['links']}")
        banned = [h for h in r['heads'] if h in
                  ('Amount of Projects','Planned Project Cost','Current Project Cost')]
        if banned: print(f"    FAIL retired-series columns back: {banned}"); ok=False
        if r['rows'] != len(served):
            print(f"    FAIL table {r['rows']} != served {len(served)}"); ok=False
        if r['links'] and not all(l.startswith('/projects/categories/') for l in r['links']):
            print(f"    FAIL category links do not point at the live route"); ok=False
        # ⚠⚠ NO FUNDING TYPE MAY BE RENDERED AS A LINKED CATEGORY. Two vintages
        # publish City/Federal/State/Private in the category column, and this
        # cell used to link them to /projects/categories/city — a page built
        # from a funding type.
        bad_links=[l for l in r['links'] if l.rsplit('/',1)[-1] in
                   ('city','federal','state','private')]
        if bad_links: print(f"    FAIL funding type linked as a category: {bad_links}"); ok=False
        if errs: print(f"    FAIL uncaught JS {errs[:2]}"); ok=False
        pg.close()
    b.close()
print("\nTYPE PAGE OK" if ok else "\nTYPE PAGE FAILED"); sys.exit(0 if ok else 1)
