"""The home page's capital card, after the Phase 4 repoint.

⚠ Four things no source guard can see, and one this session nearly shipped:

1. **The figures come from the spine, not the retired series.** 5,128 and
   12,929 are both plausible numbers in a 3-slot card.
2. **The thousands multiplier is gone.** The retired series is denominated in
   THOUSANDS, the spine in USD. Carrying `data-multiplier="1000"` onto spine
   rows renders $201.6B as $201.6T — which still looks like money.
3. **Removing three tiles must not break the OTHER cards.** Their hydration
   URLs were deleted from the controller alongside them; `loadTableStat`
   throwing once would leave every remaining `prj_stat` tile blank, and this
   repo has shipped exactly that.
4. **Nothing is clipped.** `$201.6B` losing 4px is a wrong number, and the
   element is present, correctly sized and correctly texted either way.
"""
from playwright.sync_api import sync_playwright
import sys

BASE = "http://localhost:8580"
ok = True
with sync_playwright() as p:
    b = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-gl=swiftshader"])
    for width, label in ((1440, "desktop"), (390, "mobile")):
        pg = b.new_page(viewport={"width": width, "height": 1000})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE + "/", wait_until="load", timeout=60000)
        pg.wait_for_timeout(4500)

        r = pg.evaluate("""() => {
          const cards=[...document.querySelectorAll('.home-card')];
          const cap=cards.find(c=>/Current capital commitment plan/.test(c.innerText));
          if(!cap) return {missing:true};
          const tiles=[...cap.querySelectorAll('.col-4')].map(c=>{
            const lab=c.querySelector('div'), val=c.querySelector('strong');
            const vb=val.getBoundingClientRect();
            return {label:lab.innerText.trim(), value:val.innerText.trim(),
                    clipped: val.scrollWidth > val.clientWidth + 1,
                    w: Math.round(vb.width)};
          });
          // Every OTHER prj_stat tile on the page must still have hydrated.
          const others=[...document.querySelectorAll('.prj_stat')]
            .map(e=>({id:e.id, text:e.innerText.trim()}));
          return {tiles,
                  multiplier: !!cap.querySelector('[data-multiplier]'),
                  retired: ['projects_no','orig_cost','curr_cost']
                             .filter(i=>cap.querySelector('#'+i)),
                  othersBlank: others.filter(o=>o.text===''||o.text==='\\u00a0').map(o=>o.id),
                  othersTotal: others.length,
                  sideways: document.documentElement.scrollWidth > window.innerWidth + 1};
        }""")

        print(f"\n=== {label} ({width}px) ===")
        if r.get('missing'):
            print("  FAIL: the capital card did not render"); ok = False; continue

        expected = {"IN PLAN": "12,929", "TRACKED": "17,024", "PLANNED": "$201.6B"}
        for t in r['tiles']:
            key = t['label'].upper()
            want = expected.get(key)
            bad = (want is not None and t['value'] != want) or t['clipped']
            print(f"  {t['label']:9} {t['value']:10} w={t['w']:4}px "
                  f"clipped={t['clipped']} {'FAIL' if bad else 'ok'}")
            if bad: ok = False
        if r['multiplier']:
            print("  FAIL: a data-multiplier survives on the capital card"); ok = False
        if r['retired']:
            print(f"  FAIL: retired-series hooks still present: {r['retired']}"); ok = False
        if r['othersBlank']:
            print(f"  FAIL: {len(r['othersBlank'])} of {r['othersTotal']} other prj_stat "
                  f"tiles never hydrated: {r['othersBlank'][:8]}"); ok = False
        else:
            print(f"  other prj_stat tiles hydrated: {r['othersTotal']}/{r['othersTotal']} ok")
        if r['sideways']:
            print("  FAIL: the page scrolls sideways"); ok = False

        KNOWN = ('Bloodhound is not defined', 'setData', 'schools_no')
        new = [e for e in errs if not any(k in e for k in KNOWN)]
        print(f"  uncaught JS: {len(errs)} total, {len(new)} unknown")
        for e in new[:4]:
            print("   !", e[:150]); ok = False
    b.close()
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
