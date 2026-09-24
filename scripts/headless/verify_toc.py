"""Every TOC entry must resolve to an anchor that EXISTS on this page.

⚠ The page hides a section when the City publishes nothing for it, so a TOC
built from a second, hand-typed list would link to nowhere on exactly the
projects where the absence is the finding — a menu naming a section that is not
there. Checked on a rich page, a sparse one, and one with no org.
"""
from playwright.sync_api import sync_playwright
import sys
ok=True
CASES=["850GKOH15-01","037LN18ALELE","111PO111-17"]
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])
    for pid in CASES:
        pg=b.new_page(viewport={"width":1440,"height":900})
        pg.goto(f"http://localhost:8580/p/{pid}",wait_until="load",timeout=60000)
        pg.wait_for_timeout(1500)
        r=pg.evaluate("""() => {
          const links=[...document.querySelectorAll('.db-toc a')];
          const h2=[...document.querySelectorAll('h2[id]')].map(h=>h.id);
          const sticky=getComputedStyle(document.querySelector('.db-toc')||document.body).position;
          return {entries:links.map(a=>a.getAttribute('href').slice(1)),
                  headings:h2, sticky,
                  dead:links.map(a=>a.getAttribute('href').slice(1))
                       .filter(id=>!document.getElementById(id)),
                  orphan:h2.filter(id=>!links.some(a=>a.getAttribute('href')==='#'+id))};
        }""")
        print(f"  /p/{pid}: {len(r['entries'])} entries, {len(r['headings'])} h2 anchors, "
              f"position={r['sticky']}")
        if r['dead']: print(f"    FAIL dead links: {r['dead']}"); ok=False
        if r['orphan']: print(f"    FAIL sections missing from the TOC: {r['orphan']}"); ok=False
        if r['sticky']!='sticky': print(f"    FAIL .db-toc is not sticky"); ok=False
        pg.close()
    # ⚠ Mobile: the TOC is d-none d-md-block, so it must NOT render at 390 —
    # a sticky sidebar on a phone is 13 links of chrome above the content.
    pg=b.new_page(viewport={"width":390,"height":844})
    pg.goto("http://localhost:8580/p/850GKOH15-01",wait_until="load",timeout=60000)
    pg.wait_for_timeout(1500)
    vis=pg.evaluate("(()=>{const n=document.querySelector('.db-toc');"
                    "return n? n.getBoundingClientRect().height>0 : false;})()")
    print(f"  @390 TOC visible: {vis}")
    if vis: print("    FAIL the TOC renders on mobile"); ok=False
    b.close()
print("TOC OK" if ok else "TOC FAILED"); sys.exit(0 if ok else 1)
