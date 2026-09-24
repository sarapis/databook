"""One provenance shell, two modes — and the existing guarantees preserved.

⚠ The profile's sources table moved into `<x-db.data-provenance mode="record">`.
Its content is guard-pinned elsewhere (every source listed, absences named,
versions shown), so this asserts the MOVE did not lose any of it — the rows are
in the DOM behind the accordion, not dropped.
"""
from playwright.sync_api import sync_playwright
import sys, json, urllib.request
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])

    # ---- record mode, on the profile ----
    with urllib.request.urlopen("http://localhost:8581/get/capital/project/850GKOH15-01") as f:
        cov=json.load(f)['source_coverage']
    pg=b.new_page(viewport={"width":1440,"height":1000})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8580/p/850GKOH15-01",wait_until="load",timeout=60000)
    pg.wait_for_timeout(2500)
    r=pg.evaluate("""() => {
      const box=document.getElementById('prjSourcesBody');
      const rows=box? box.querySelectorAll('tbody tr').length : 0;
      const txt=box? box.innerText : '';
      const btn=document.querySelector('#prjSources .social_btn');
      return {rows, present:(txt.match(/Yes/g)||[]).length,
              absent:(txt.match(/Not published/g)||[]).length,
              summary: btn? btn.innerText.trim() : null,
              inDom: !!box, visible: box? box.getBoundingClientRect().height>0 : false,
              retiredBadges: box? box.querySelectorAll('.db-badge-warning').length : 0,
              grainBadges: box? box.querySelectorAll('.db-badge-info').length : 0};
    }""")
    print(f"  record mode: {r['rows']} rows (endpoint {len(cov['rows'])}) | "
          f"Yes {r['present']} / Not published {r['absent']}")
    print(f"    summary: {r['summary']}")
    print(f"    in DOM {r['inDom']} | visible before click {r['visible']} | "
          f"retired badges {r['retiredBadges']} | grain badges {r['grainBadges']}")
    if r['rows'] != len(cov['rows']):
        print(f"    FAIL {r['rows']} rows != endpoint {len(cov['rows'])} — a source was dropped"); ok=False
    if r['present'] != cov['sources_present']:
        print(f"    FAIL {r['present']} 'Yes' != sources_present {cov['sources_present']}"); ok=False
    if not r['inDom']:
        print("    FAIL the sources table is not in the DOM"); ok=False
    if str(cov['sources_present']) not in (r['summary'] or ''):
        print("    FAIL the summary does not state how many sources carry the record"); ok=False
    # ⚠ Every note must still render — they are the caveats, not decoration.
    body=pg.evaluate("(document.getElementById('prjSourcesBody')||{}).innerText||''")
    # These three DESCRIBE the table and live with it, inside the collapse.
    for key in ('note','grain_note','excluded_note'):
        v=(cov.get(key) or '').strip()
        if v and v[:40] not in body:
            print(f"    FAIL {key} is no longer rendered"); ok=False
    # THE RETIRED-SERIES NOTE MUST BE VISIBLE WITHOUT A CLICK. One of the three
    # load-bearing caveats; folding the table into the accordion took it inside.
    # A pytest guard caught that; this asserts the RENDERED result.
    rn=(cov.get('retired_note') or '').strip()
    if rn:
        vis=pg.evaluate("[...document.querySelectorAll('.db-note')]"
                        ".filter(e=>e.getBoundingClientRect().height>0)"
                        ".map(e=>e.innerText.trim()).join(' || ')")
        if rn[:40] not in vis:
            print("    FAIL retired_note is not VISIBLE without opening the accordion"); ok=False
        if rn[:40] in body:
            print("    FAIL retired_note is inside the collapsed body"); ok=False
    if errs: print(f"    FAIL uncaught JS {errs[:2]}"); ok=False
    pg.close()

    # ---- page mode, on /projects and the family page ----
    for u in ("/projects","/projects/budget-lines/families/sewers"):
        pg=b.new_page(viewport={"width":1440,"height":1000})
        e2=[]; pg.on("pageerror", lambda e: e2.append(str(e)))
        pg.goto("http://localhost:8580"+u,wait_until="load",timeout=60000)
        pg.wait_for_timeout(2500)
        q=pg.evaluate("""() => {
          const btn=[...document.querySelectorAll('.social_btn')]
            .find(b=>/normalized data from/.test(b.innerText));
          const box=btn? document.querySelector(btn.getAttribute('data-bs-target')) : null;
          return {summary: btn? btn.innerText.trim().replace(/\\s+/g,' ') : null,
                  rows: box? box.querySelectorAll('tbody tr').length : 0,
                  empty: box? /No data available/.test(box.innerText) : false};
        }""")
        print(f"\n  page mode {u}: {q['rows']} rows")
        print(f"    {q['summary']}")
        if not q['summary']: print("    FAIL no provenance accordion"); ok=False
        if q['rows'] == 0: print("    FAIL the dataset table is empty"); ok=False
        # ⚠ THE OLD DEFECT: rows rendered and then spliced away by a 404.
        if q['empty']: print("    FAIL 'No data available in table' — rows were deleted"); ok=False
        if e2: print(f"    FAIL uncaught JS {e2[:2]}"); ok=False
        pg.close()
    b.close()
print("\nPROVENANCE OK" if ok else "\nPROVENANCE FAILED"); sys.exit(0 if ok else 1)
