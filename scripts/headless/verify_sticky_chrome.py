"""The site chrome actually pins, and the analysis section still pins only its bar.

⚠⚠ THIS IS THE CHECK THAT WAS MISSING FOR THIRTEEN MONTHS. `.db-header` and
`.db-submenu` have declared `position: sticky` since the design system landed and
NEITHER EVER STUCK: layout.blade.php wrapped them in a <header> exactly their
combined height, and a sticky box can only travel inside its parent. The CSS
said one thing and the page did another, on every page, and nothing noticed —
because "is the rule present?" is a different question from "does it do
anything?", and only the second one is worth asking.

⚠⚠ AND A PAGE THAT CANNOT SCROLL PROVES NOTHING. /notices is 906px against a
900px viewport, so `scrollTo(0,1200)` moves it SIX pixels and the header sits
near the top looking perfectly pinned. A naive probe reported it as the one page
where sticky worked, on a build where sticky worked nowhere. Every case here
asserts the scroll it actually ACHIEVED before reading a position.

Two behaviours, deliberately different:
  * ordinary pages  -- the whole chrome pins: header at 0, submenu at 56.
  * analysis pages  -- VARIANT B: the wrapper is pinned at minus the two upper
    bars, so the masthead and Procurement bar scroll away and only the 41px
    analysis bar is left, sitting at 0.

    python3 scripts/headless/verify_sticky_chrome.py [--base http://localhost:8580]
"""
from playwright.sync_api import sync_playwright
import argparse
import sys

# ⚠ Ordinary pages must be TALL ENOUGH TO SCROLL past the chrome; a short one
# would pass vacuously. Each is checked for that, so a page that gets shorter
# fails loudly rather than quietly stopping being evidence.
ORDINARY = ["/", "/organizations", "/procurement", "/projects", "/titles",
            "/schools", "/o/170020034-new-york-city-housing-authority", "/p/826HED-545"]
ANALYSIS = ["/research/digital-reform", "/research/digital-reform/contracts",
            "/research/digital-reform/products"]

SCROLL_TO = 1200
MIN_SCROLL = 200          # below this the page cannot demonstrate anything

PROBE = """() => {
  const q = s => document.querySelector(s);
  const top = e => { const b = e && e.getBoundingClientRect(); return b ? Math.round(b.top) : null; };
  const bar = q('.db-analysis-bar');
  return {
    y: Math.round(window.scrollY),
    header: top(q('.db-header')),
    submenu: top(q('.db-submenu')),
    bar: bar && !bar.hasAttribute('hidden') ? top(bar) : null,
    hscroll: document.documentElement.scrollWidth > window.innerWidth,
  };
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8580")
    args = ap.parse_args()

    problems = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--enable-unsafe-swiftshader"])
        for width, height in ((1440, 900), (390, 844)):
            for url in ORDINARY + ANALYSIS:
                page = b.new_page(viewport={"width": width, "height": height})
                try:
                    page.goto(args.base + url, wait_until="load", timeout=60000)
                    page.wait_for_timeout(1200)
                    page.evaluate(f"window.scrollTo(0,{SCROLL_TO})")
                    page.wait_for_timeout(400)
                    r = page.evaluate(PROBE)
                    where = f"{url} @{width}"

                    # ⚠ THE NON-VACUITY GATE, FIRST. Without it a short page reads
                    # as a pass on a build where nothing pins at all.
                    if r["y"] < MIN_SCROLL:
                        problems.append(f"{where}: only scrolled {r['y']}px — cannot "
                                        f"demonstrate anything; the page got shorter")
                        continue

                    if url in ANALYSIS:
                        # ⚠ `is None` on purpose: the bar's top is 0 when correct,
                        # and `not r['bar']` would read that as absent.
                        if r["bar"] is None:
                            problems.append(f"{where}: analysis bar absent, so variant B "
                                            f"cannot be what is being measured")
                        elif not (-1 <= r["bar"] <= 2):
                            problems.append(f"{where}: analysis bar at {r['bar']}, expected 0")
                        elif r["header"] is not None and r["header"] > -50:
                            problems.append(f"{where}: masthead at {r['header']} — it should "
                                            f"have scrolled away with the wrapper (variant B)")
                    else:
                        if r["header"] is None:
                            problems.append(f"{where}: no .db-header")
                        elif r["header"] < -1:
                            problems.append(f"{where}: masthead at {r['header']} — the chrome "
                                            f"is not pinning; the wrapper's sticky is inert again")
                        if r["submenu"] is not None and not (50 <= r["submenu"] <= 62):
                            problems.append(f"{where}: submenu at {r['submenu']}, expected ~56 "
                                            f"(stacked under the masthead)")
                    if r["hscroll"]:
                        problems.append(f"{where}: page scrolls sideways")
                except Exception as exc:                       # pragma: no cover
                    problems.append(f"{url} @{width}: {exc}")
                finally:
                    page.close()

    checked = len(ORDINARY + ANALYSIS) * 2
    for line in problems:
        print("  ✗ " + line)
    print(f"{checked} page/width combinations checked")
    if problems:
        print(f"STICKY CHROME BROKEN ({len(problems)} problems)")
        return 1
    print("STICKY CHROME OK — chrome pins site-wide, analysis pages pin only their bar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
