"""Headless verification of the restructured /p/{id} against the plan's targets.

⚠ Reads GEOMETRY and DOM, never a screenshot. The map is read as its container's
own bounding box PLUS what it renders — reading `getSource()._data` is reading
the INPUT, which is how a 0px-wide map passed every check once.
"""
import re, sys, json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8580"
# rich (all sections) · sparse (few) · no wegov_org_id (the 4,568-project case)
CASES = ["850GKOH15-01", "037LN18ALELE", "111PO111-17"]
MDY = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')

def measure(pg):
    return pg.evaluate("""() => {
      const main = document.querySelector('.inner_container') || document.body;
      const stat = document.querySelector('.db-stat-value');
      // ⚠⚠ THE FIRST ANSWER IS NOT ALWAYS THE FIRST TILE ANY MORE. Phase and
      // forecast completion moved out of the tile strip into the header
      // (owner, 2026-09-10), so at 390 the reader now meets them ~60px EARLIER
      // than the old first tile while the first MONEY tile sits lower. A check
      // anchored on `.db-stat-value` alone reads that as a regression when it
      // is the opposite — so both are measured: the first answer of any kind,
      // and the point the money begins.
      const meta = document.querySelector('.db-profile-meta');
      const tables = [...main.querySelectorAll('table')];
      // ⚠ A TABLE WIDER THAN ITS BOX IS FINE IF THE BOX SCROLLS — that is what
      // `.table-responsive` is for, and a 7-column table cannot be made to fit
      // 390px without deleting columns. What must never happen is the PAGE
      // scrolling sideways, which is the thing a reader actually experiences.
      // The first draft of this verifier asserted the former and reported four
      // correctly-scrolling tables as failures.
      const unscrollable = tables.filter(t => {
        const box = t.closest('.table-responsive');
        if (!box) return t.scrollWidth > t.parentElement.clientWidth + 1;
        return getComputedStyle(box).overflowX === 'visible';
      }).length;
      const widest = tables.length ? Math.max(...tables.map(t => t.scrollWidth)) : 0;
      const widestUnboxed = Math.max(0, ...tables
        .filter(t => !t.closest('.table-responsive'))
        .map(t => t.scrollWidth));
      const pageScrollsX = document.documentElement.scrollWidth > window.innerWidth + 1;
      const taps = [...main.querySelectorAll('.db-tap')]
        .map(e => Math.round(e.getBoundingClientRect().height));
      // Text as a reader sees it: scripts and <details> summaries included,
      // but never <script> bodies.
      const clone = main.cloneNode(true);
      clone.querySelectorAll('script').forEach(s => s.remove());
      return {
        height: Math.round(document.documentElement.scrollHeight),
        h1: document.querySelectorAll('h1').length,
        h2: main.querySelectorAll('h2').length,
        h3plus: main.querySelectorAll('h4,h5,h6').length,
        h3: main.querySelectorAll('h3').length,
        firstStat: stat ? Math.round(stat.getBoundingClientRect().top + window.scrollY) : null,
        firstMeta: meta ? Math.round(meta.getBoundingClientRect().top + window.scrollY) : null,
        fold: window.innerHeight,
        tables: tables.length,
        tablesUnscrollable: unscrollable,
        widestUnboxed: widestUnboxed,
        pageScrollsX: pageScrollsX,
        widestTable: widest,
        viewport: window.innerWidth,
        badgeNeutral: main.querySelectorAll('.db-badge-neutral').length,
        badgeWarning: main.querySelectorAll('.db-badge-warning').length,
        badgeInfo: main.querySelectorAll('.db-badge-info').length,
        badgeNavy: main.querySelectorAll('.db-badge-navy').length,
        thNoScope: [...main.querySelectorAll('thead th')].filter(t => !t.hasAttribute('scope')).length,
        taps: taps,
        text: clone.innerText,
      };
    }""")

fails = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-gl=swiftshader"])
    for pid in CASES:
        for w, h in ((1440, 900), (390, 844)):
            pg = b.new_page(viewport={"width": w, "height": h})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(f"{BASE}/p/{pid}", wait_until="load", timeout=60000)
            pg.wait_for_timeout(2500)
            m = measure(pg)
            tag = f"/p/{pid} @{w}"
            print(f"\n=== {tag}")
            print(f"  height {m['height']}px | first .db-stat-value top "
                  f"{m['firstStat']} | h1={m['h1']} h2={m['h2']} h3={m['h3']} h4-h6={m['h3plus']}")
            print(f"  tables {m['tables']} widest {m['widestTable']}px "
                  f"unscrollable {m['tablesUnscrollable']} widest-unboxed {m['widestUnboxed']}px "
                  f"| page scrolls X: {m['pageScrollsX']} | th missing scope {m['thNoScope']}")
            print(f"  badges neutral={m['badgeNeutral']} warning={m['badgeWarning']} "
                  f"info={m['badgeInfo']} navy={m['badgeNavy']}")
            mdy = sorted(set(MDY.findall(m['text'])))
            print(f"  MM/DD/YYYY in rendered copy: {len(mdy)} {mdy[:4]}")
            if w == 390 and m['taps']:
                print(f"  .db-tap heights: min {min(m['taps'])} n={len(m['taps'])}")

            if m['h1'] != 1: fails.append(f"{tag}: h1 count {m['h1']} != 1")
            if m['h3plus']: fails.append(f"{tag}: {m['h3plus']} h4-h6 headings")
            # ⚠⚠ RE-EXPRESSED, NOT RELAXED — and this check FIRED on the change
            # that made it necessary. It asserted the first `.db-stat-value`
            # sits above 600px, because the tile strip WAS the first answer.
            # Phase and forecast now live in the header, so at 390 on the rich
            # case the first answer arrives at 521px (was 581) while the first
            # money tile sits at 649. Keeping the old anchor would have called
            # a 60px improvement a regression, and moving the number to 700
            # would have stopped checking anything.
            answers = [v for v in (m['firstStat'], m['firstMeta']) if v is not None]
            if not answers: fails.append(f"{tag}: no answer above the fold at all")
            elif min(answers) >= 600:
                fails.append(f"{tag}: the first answer is at {min(answers)}px >= 600")
            # ⚠ AND THE MONEY MUST STILL BEGIN ON THE FIRST SCREEN. Without this
            # the header could grow without limit and push every figure below
            # the fold, one line at a time, with the check above still green.
            if m['firstStat'] is None: fails.append(f"{tag}: no .db-stat-value")
            elif m['firstStat'] >= m['fold']:
                fails.append(f"{tag}: the money tiles begin at {m['firstStat']}px, "
                             f"below the {m['fold']}px fold")
            if m['tablesUnscrollable']: fails.append(f"{tag}: {m['tablesUnscrollable']} tables overflow with no scroll container")
            if m['pageScrollsX']: fails.append(f"{tag}: the PAGE scrolls horizontally ({m['widestUnboxed']}px unboxed)")
            if m['thNoScope']: fails.append(f"{tag}: {m['thNoScope']} <th> without scope")
            if mdy: fails.append(f"{tag}: MM/DD/YYYY still rendered: {mdy[:3]}")
            if errs: fails.append(f"{tag}: UNCAUGHT JS {errs[:2]}")
            if w == 390 and m['taps'] and min(m['taps']) < 32:
                fails.append(f"{tag}: .db-tap min height {min(m['taps'])} < 32")
            if w == 1440 and pid == "850GKOH15-01" and m['height'] > 5000:
                fails.append(f"{tag}: height {m['height']} > 5000 target")
            if w == 390 and pid == "850GKOH15-01" and m['height'] > 9000:
                fails.append(f"{tag}: height {m['height']} > 9000 target")
            pg.close()
    b.close()

print("\n" + ("FAIL:\n  " + "\n  ".join(fails) if fails else "ALL TARGETS MET"))
sys.exit(1 if fails else 0)
