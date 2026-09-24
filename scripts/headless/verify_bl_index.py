"""The budget-lines index: family grouping, and links only where a page exists.

⚠ The grouping was DEAD — `rowGroup.dataSrc` named `wegov-prjtype-name`, a key
the payload has never carried, so all 749 rows sat under one "No group" header.
⚠ And the group names come from `capitalbudget` (41 values) while the family
pages come from the spine (39); only 25 slugs match, so a link is emitted only
when the served slug set contains it.
"""
from playwright.sync_api import sync_playwright
import sys, urllib.request, json
ok=True
with urllib.request.urlopen("http://localhost:8581/get/capital/families") as f:
    slugs=set(json.load(f)['slugs'])
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])
    pg=b.new_page(viewport={"width":1440,"height":1000})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://localhost:8580/projects/budget-lines",wait_until="load",timeout=60000)
    pg.wait_for_timeout(5000)
    r=pg.evaluate("""() => {
      const g=[...document.querySelectorAll('tr.dtrg-group')];
      const slug=x=>x.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
      return g.map(e=>{
        const name=e.innerText.replace(/\\s*\\(\\d+\\)\\s*$/,'').trim();
        const a=e.querySelector('a');
        return {name, slug:slug(name), href:a?a.getAttribute('href'):null};
      });
    }""")
    print(f"  groups rendered: {len(r)}   (a dead grouping renders exactly 1: 'No group')")
    if len(r) < 2: print("    FAIL the family grouping is dead again"); ok=False
    linked=[x for x in r if x['href']]
    print(f"  linked {len(linked)} / plain {len(r)-len(linked)}")
    for x in r:
        should = x['slug'] in slugs
        if should and not x['href']:
            print(f"    FAIL {x['name']} has a family page and is not linked"); ok=False
        if x['href'] and not should:
            print(f"    FAIL {x['name']} is linked but has no family page"); ok=False
    import subprocess
    for x in linked[:8]:
        c=subprocess.run(['curl','-s','-o','/dev/null','-w','%{http_code}',
                          'http://localhost:8580'+x['href']],capture_output=True,text=True).stdout
        if c!='200': print(f"    FAIL {x['href']} -> {c}"); ok=False
    # ⚠⚠ THE CHART ROW IS ONE LINE, AND IT IS A LAYOUT CLAIM ONLY THE RENDER CAN
    # CHECK. The project-type legend is an unsized inline-block whose longest row
    # is "WATER MAINS, SOURCES AND TREATMENT: $1.06B (3.6 %)"; in the ~400px
    # column it used to share with the funding-source pie it did not fit beside a
    # 285px canvas, so the pie wrapped BELOW its own legend. Nothing in the DOM or
    # the chart data can see that — only the boxes can.
    lay=pg.evaluate("""() => {
      const box=e=>{const r=e.getBoundingClientRect();return {x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width)}};
      const ft=document.getElementById('ftChart');
      const pie=document.getElementById('byPrgTypeChart');
      const leg=document.querySelector('.byPrgTypeChart .pie_legend');
      return {ft:ft?box(ft):null, pie:pie?box(pie):null, leg:leg?box(leg):null,
              fund: !!document.getElementById('byFundSourceChart'),
              sideways: document.documentElement.scrollWidth - window.innerWidth};
    }""")
    if lay['fund']:
        print("    FAIL the funding-source pie is back — its data is the line chart's own"); ok=False
    for k in ('ft','pie','leg'):
        if not lay[k]: print(f"    FAIL #{k} is missing from the chart row"); ok=False
    if lay['ft'] and lay['pie'] and lay['leg']:
        if lay['pie']['x'] <= lay['leg']['x']:
            print("    FAIL the pie is not right of its legend"); ok=False
        if abs(lay['pie']['y']-lay['leg']['y']) > 40:
            print(f"    FAIL the pie wrapped below its legend (legend y={lay['leg']['y']}, pie y={lay['pie']['y']})"); ok=False
        if abs(lay['ft']['y']-lay['pie']['y']) > 40:
            print(f"    FAIL the two charts are not on one line (ft y={lay['ft']['y']}, pie y={lay['pie']['y']})"); ok=False
        print(f"  chart row @1440: ft x={lay['ft']['x']} | legend x={lay['leg']['x']} | pie x={lay['pie']['x']}  (all y~{lay['pie']['y']})")
    # ⚠ This view has already shipped a 40px sideways scroll from this very row.
    if lay['sideways'] > 0:
        print(f"    FAIL the page scrolls sideways by {lay['sideways']}px"); ok=False
    if errs: print(f"    FAIL uncaught JS {errs[:2]}"); ok=False
    b.close()
print("BL INDEX OK" if ok else "BL INDEX FAILED"); sys.exit(0 if ok else 1)
