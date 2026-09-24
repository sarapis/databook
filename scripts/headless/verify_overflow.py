"""No element on the page is CLIPPED by its own box.

⚠⚠ EVERY GEOMETRY AND DOM CHECK PASSED ON A VISIBLY CUT-OFF TILE. The Phase tile
read "Constructio / Procuremer" on screen while the element existed, was the
right size, and held the right text — overflow is invisible to all of those.
Found by LOOKING at the render. This is the check that would have caught it:
compare each element's scroll extent against its client extent, on ancestors
that actually clip (`overflow: hidden`).
"""
from playwright.sync_api import sync_playwright
import sys
# ⚠ The last four are the district section's worked examples, added 2026-09-10:
# 850HWCRCDB carries 94 NTAs / 46 cd / 45 cc / 30 sd — every one of them inside a
# `<details>` in a table cell, which is the shape most likely to clip; 826HED-545
# is the count case with three unanswerable sets; 801SKYPORT has geometry and a
# genuine zero; 801CONEYWACQ is one district of each, the default layout.
CASES=["850GKOH15-01","037LN18ALELE","111PO111-17",
       "850HWCRCDB","826HED-545","801SKYPORT","801CONEYWACQ"]
ok=True
with sync_playwright() as p:
    b=p.chromium.launch(args=["--enable-unsafe-swiftshader","--use-gl=swiftshader"])
    for pid in CASES:
        for w,h in ((1440,900),(390,844)):
            pg=b.new_page(viewport={"width":w,"height":h})
            pg.goto(f"http://localhost:8580/p/{pid}",wait_until="load",timeout=60000)
            pg.wait_for_timeout(2000)
            # ⚠⚠ OPEN EVERY DISCLOSURE FIRST. A closed `<details>` has nothing to
            # clip, so measuring the page as it loads would pass on a district
            # list that is unreadable the moment a reader opens it — the whole
            # point of this check is that a present, correctly-sized element can
            # still be cut off.
            pg.evaluate("() => document.querySelectorAll('.inner_container details')"
                        ".forEach(d => d.open = true)")
            pg.wait_for_timeout(400)
            bad=pg.evaluate("""() => {
              const out=[];
              const main=document.querySelector('.inner_container');
              for (const el of main.querySelectorAll('*')) {
                const cs=getComputedStyle(el);
                if (cs.overflow==='visible' && cs.overflowX==='visible' && cs.overflowY==='visible') continue;
                if (cs.overflowX==='auto'||cs.overflowX==='scroll') continue;   // scrolls on purpose
                if (cs.overflowY==='auto'||cs.overflowY==='scroll') continue;
                if (el.classList.contains('mapboxgl-map')||el.closest('.mapboxgl-map')) continue;
                if (el.id==='map'||el.id==='map_container') continue;           // mapbox positions absolutely
                const dx=el.scrollWidth-el.clientWidth, dy=el.scrollHeight-el.clientHeight;
                if (dx>1||dy>1) out.push({
                  sel: el.tagName+'.'+(el.className||'').toString().slice(0,32),
                  dx, dy, text:(el.innerText||'').trim().slice(0,44)});
              }
              return out;
            }""")
            print(f"  /p/{pid} @{w}: {len(bad)} clipped")
            for x in bad[:6]:
                print(f"      +{x['dx']}x{x['dy']}px  {x['sel']}  {x['text']!r}")
            if bad: ok=False
            pg.close()
    b.close()
print("NO CLIPPING" if ok else "CLIPPING FOUND"); sys.exit(0 if ok else 1)
