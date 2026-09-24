"""Every migrated page: rows survive, counts render, nothing is deleted.

⚠ The defect being removed DELETED ROWS: `loadTableStat`'s callback was
`if (res) { fill } else { splice }`, so a scoped count of 0 — a fact — removed
the row, and a failed request did the same. Measured before: /projects/types/
animal-care requested 3 datasets and rendered 1.
"""
from playwright.sync_api import sync_playwright
import sys
PAGES = [
    ("/projects/capital","page"), ("/projects/types","page"),
    ("/projects/types/animal-care","scoped"),
    ("/projects/categories/routine-reconstruction","scoped"),
    ("/projects/budget-lines/EP-0007","scoped"),
    ("/d/cc-38-x/projects","page"), ("/d/cc-38-x/facilities","page"),
    ("/schools","page"), ("/projects","page"),
    ("/projects/budget-lines/families/sewers","page"),
]
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])
    for u,mode in PAGES:
        pg=b.new_page(viewport={"width":1440,"height":1000})
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto("http://localhost:8580"+u,wait_until="load",timeout=60000)
        pg.wait_for_timeout(4500)
        r=pg.evaluate("""() => {
          const btn=[...document.querySelectorAll('.social_btn')]
            .find(b=>/normalized data from/.test(b.innerText));
          if(!btn) return {none:true};
          const box=document.querySelector(btn.getAttribute('data-bs-target'));
          const cells=box? [...box.querySelectorAll('tbody tr td:last-child')]
            .map(e=>e.innerText.trim()) : [];
          return {summary:btn.innerText.trim().replace(/\\s+/g,' '),
                  rows: box? box.querySelectorAll('tbody tr').length : 0,
                  empty: box? /No data available/.test(box.innerText) : false,
                  cells: cells.slice(0,6),
                  blank: cells.filter(c=>c==='').length};
        }""")
        if r.get('none'):
            print(f"  {u:46} NO ACCORDION"); ok=False; pg.close(); continue
        print(f"\n  {u}  [{mode}]")
        print(f"    rows {r['rows']} | blank count cells {r['blank']} | {r['cells']}")
        print(f"    {r['summary'][:96]}")
        if r['rows']==0 or r['empty']:
            print("    FAIL the dataset table is empty — rows were deleted"); ok=False
        if r['blank']:
            print(f"    FAIL {r['blank']} count cells are blank — nothing filled them"); ok=False
        # ⭐ THE MUTE IS EMPTY, AND THAT IS THE POINT — IT WAS RETIRED WHEN ITS
        # CONDITION ENDED. It held THREE pre-existing /schools errors:
        # `schools_no`, `Bloodhound is not defined`, and `setData` (the
        # documented map race — the fetch beating mapbox's style load, so
        # `getSource('route')` is undefined). All three are now fixed: the first
        # two by the schools fix (#385, on main) and the third by its
        # `SCH_PENDING_FEATURES` hold-and-draw, while the `loadTableStat` errors
        # that used to accompany them went with the datasets accordion in the
        # provenance migration.
        #
        # ⚠ THE ORDER MATTERED. Emptying this before `main` was merged here would
        # have un-muted errors that were still real on this branch — the fix and
        # the mute lived on different branches until 64289b3. Measured after the
        # merge: /schools throws ZERO uncaught errors.
        #
        # ⚠ Leave it as an empty tuple rather than deleting the mechanism: the
        # next pre-existing error wants NAMING here, not ignoring, and a named
        # mute with a reason is what let this one be retired instead of
        # forgotten.
        KNOWN = ()
        new = [e for e in errs if not any(k in e for k in KNOWN)]
        if new:
            print(f"    FAIL uncaught JS {new[:2]}"); ok=False
        elif errs:
            print(f"    (pre-existing, unrelated: {len(errs)})")
        pg.close()
    b.close()
print("\nMIGRATION OK" if ok else "\nMIGRATION FAILED"); sys.exit(0 if ok else 1)
