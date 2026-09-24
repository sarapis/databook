"""The stat-grid change is to a SHARED component — check the other consumers.

⚠ A fix to `databook-components.css` reaches every page that uses the class.
The capital profile is one of twelve views with a stat grid; measuring only the
page you were working on is how a local fix becomes a site-wide regression.
"""
from playwright.sync_api import sync_playwright
import sys
URLS = ["/projects","/organizations/agencies","/organizations","/titles","/styleguide",
        "/procurement","/districts/cc","/d/cc-38-x/projects"]
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])
    for u in URLS:
        for w in (1440, 390):
            pg=b.new_page(viewport={"width":w,"height":900})
            try:
                pg.goto("http://localhost:8580"+u, wait_until="load", timeout=60000)
            except Exception as e:
                print(f"  {u} @{w}: LOAD FAILED {e}"); pg.close(); continue
            pg.wait_for_timeout(2500)
            r=pg.evaluate("""() => {
              const stats=[...document.querySelectorAll('.db-stat')];
              const clipped=stats.filter(e=>e.scrollWidth-e.clientWidth>1||e.scrollHeight-e.clientHeight>1);
              return {n:stats.length, clipped:clipped.length,
                      pageX: document.documentElement.scrollWidth>window.innerWidth+1,
                      sample: clipped.slice(0,3).map(e=>(e.innerText||'').trim().slice(0,40))};
            }""")
            flag = ''
            if r['clipped'] or r['pageX']: flag=' <-- PROBLEM'; ok=False
            print(f"  {u:32} @{w}  stats={r['n']:<3} clipped={r['clipped']} pageScrollsX={r['pageX']}{flag}")
            if r['sample']: print(f"      {r['sample']}")
            pg.close()
    b.close()
print("SITEWIDE OK" if ok else "SITEWIDE REGRESSION"); sys.exit(0 if ok else 1)
