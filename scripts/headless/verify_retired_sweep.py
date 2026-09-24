"""Sweep every live capital surface — page TEXT and every Chart.js SERIES LABEL.

⚠⚠ THE TEXT SCAN ALONE MISSED A SURFACE. Chart.js draws its legend into the
canvas, so the org profile plotted `Amount Over Budget` over 14 publication dates
while a scan of `document.body.innerText` reported the page clean. This version
reads `Chart.instances`' dataset labels too.
"""
from playwright.sync_api import sync_playwright
import time

URLS = [
 "/", "/projects", "/projects/about", "/projects/types",
 "/projects/types/police-facilities", "/projects/categories",
 "/projects/categories/routine-reconstruction", "/projects/budget-lines",
 "/projects/budget-lines/EP-0007", "/projects/budget-lines/families/sewers",
 "/projects/commitments", "/capital/minor-projects", "/p/826HED-545",
 "/procurement", "/o/170010846-x", "/o/170010846-x/projects",
 "/o/170010998-x/projects", "/o/170020034-x",
 "/d/cc-38-x/projects", "/d/cd-301-x/projects",
]
print(f"{'url':44} {'text':5} {'chart':6} {'blank':6} js  chart series carrying the label")
bad = 0
with sync_playwright() as p:
    b = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-gl=swiftshader"])
    for u in URLS:
        pg = b.new_page(viewport={"width": 1440, "height": 1200})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e).split("\n")[0]))
        try:
            pg.goto("http://localhost:8580" + u, wait_until="load", timeout=60000)
        except Exception:
            print(f"{u:44} GOTO FAIL"); pg.close(); continue
        time.sleep(7)
        r = pg.evaluate("""() => {
          const labels=[];
          const reg = (window.Chart && Chart.instances) ? Object.values(Chart.instances) : [];
          reg.forEach(c=>{try{(c.data.datasets||[]).forEach(d=>labels.push(d.label||''));}catch(e){}});
          ['chart1','chart2','chart3','chart4'].forEach(k=>{
            const c=window[k]; if(c&&c.data) try{c.data.datasets.forEach(d=>labels.push(d.label||''));}catch(e){}});
          const blank=[...document.querySelectorAll('.prj_stat')]
            .filter(e=>e.innerText.replace(/\\u00a0/g,'').trim()==='').map(e=>e.id||'(anon)');
          // ⚠⚠ CASE-INSENSITIVE, AND THE CASE-SENSITIVE FORM WAS A HOLE IN THIS
          // GUARD. `innerText` returns text AS RENDERED, so it applies
          // text-transform — and `.db-stat-label` and `.db-table th` are
          // `text-transform: uppercase` site-wide. Proved 2026-09-14 by
          // injecting a `.db-stat-label` reading "Amount Over Budget" into
          // /projects: innerText gave "AMOUNT OVER BUDGET" and this test
          // reported the page CLEAN — on exactly the tile shape it was written
          // to catch (the org tab's eight blank tiles, one so labelled). The
          // chart arm below was already /i; only this half was exposed.
          return {text:/Amount Over Budget/i.test(document.body.innerText),
                  chartLabels:[...new Set(labels)].filter(l=>/Over Budget/i.test(l)),
                  allLabels:[...new Set(labels)].length, blank};
        }""")
        flag = r['text'] or r['chartLabels'] or r['blank'] or len(errs) > 1
        if flag: bad += 1
        print(f"{u:44} {'AOB' if r['text'] else '-':5} "
              f"{'AOB' if r['chartLabels'] else '-':6} "
              f"{len(r['blank']):<6} {len(errs)}   {r['chartLabels'] or ''}"
              f"{'  <<<' if flag else ''}")
        pg.close()
    b.close()
print(f"\nflagged: {bad} of {len(URLS)}")
