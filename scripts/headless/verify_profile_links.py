"""Every link the project profile emits must resolve.

⚠ A link that lands on a 500 or a 404 is worse than plain text — that is the
rule this section settled for `sd` district badges, and the budget-line links
were shipping 500s under it. Follows every anchor the page emits, on three
representative projects.
"""
from playwright.sync_api import sync_playwright
import sys, urllib.request, collections
CASES=["850GKOH15-01","037LN18ALELE","111PO111-17"]
seen=collections.OrderedDict()
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])
    for pid in CASES:
        pg=b.new_page(viewport={"width":1440,"height":1000})
        pg.goto(f"http://localhost:8580/p/{pid}", wait_until="load", timeout=60000)
        pg.wait_for_timeout(2500)
        hrefs=pg.evaluate("""() => [...document.querySelectorAll('.inner_container a[href]')]
            .map(a=>a.href)
            .filter(h=>h.startsWith('http://localhost:8580'))""")
        for h in hrefs: seen.setdefault(h, pid)
        pg.close()
    b.close()
bad=[]
for h,pid in seen.items():
    req=urllib.request.Request(h, method='GET')
    try:
        with urllib.request.urlopen(req) as r: code=r.status
    except urllib.error.HTTPError as e: code=e.code
    except Exception as e: code=str(e)
    if code!=200: bad.append((code,h,pid))
print(f"  followed {len(seen)} distinct links from {len(CASES)} profiles")
for c,h,pid in bad: print(f"    {c}  {h}   (on /p/{pid})")
print("PROFILE LINKS OK" if not bad else f"{len(bad)} BROKEN")
sys.exit(0 if not bad else 1)
