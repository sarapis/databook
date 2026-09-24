"""The Digital Services Overview's five bands, read as GEOMETRY and reconciled.

⚠⚠ THE PAGE HAVING A CANVAS PROVES NOTHING. This repo has measured four capital
maps drawing ZERO features while their tables were correct, and a stat tile that
existed, sat in the right place, held the right text and was CLIPPED. So this
reads each chart's own dataset off the Chart.js instance and checks:

  * every band is present and carries a link to its page;
  * every pie DREW slices, with as many arcs as it has values;
  * no pie exceeds SIX wedges — five validated hues plus one neutral remainder.
    `DBChart.slice` carries exactly five, so a sixth categorical wedge means a
    hue got cycled, which is the one thing the palette rules forbid;
  * a remainder or a "not identified" wedge is the NEUTRAL, never a hue — that
    distinction is the whole reason `sliceOther` exists;
  * each pie's slices SUM to the figure its own endpoint publishes, so a fold
    that silently dropped its tail cannot pass.

⚠ Chart.js animates from zero via requestAnimationFrame; in a pane that never
ticks rAF every arc reads 0 forever and correct data looks empty. Animation off
and `update('none')` before measuring — the trap `verify_chart.py` documents.
"""
import json
import sys
import urllib.request

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8580"
API = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8581"

BANDS = ["s-contracts", "s-products", "s-data", "s-agreements", "s-vendors"]
PIES = ["ovAgencyChart", "ovTypeChart", "ovFunctionChart",
        "ovRouteChart", "ovKindChart", "ovDataAgencyChart"]


def api(path):
    with urllib.request.urlopen(API + path, timeout=60) as f:
        return json.load(f)


def main():
    problems = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--enable-unsafe-swiftshader", "--use-gl=swiftshader"])
        pg = b.new_page(viewport={"width": 1400, "height": 1000})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE + "/research/digital-reform", wait_until="load", timeout=90000)
        pg.wait_for_timeout(1500)

        r = pg.evaluate("""(ids) => {
            const out = {bands: {}, charts: {}, other: null};
            for (const id of ['s-contracts','s-products','s-data','s-agreements','s-vendors']) {
                const el = document.getElementById(id);
                out.bands[id] = el ? {
                    present: true,
                    heading: (el.querySelector('h2') || {}).textContent.trim(),
                    // The way in. A band with no link is a dead end.
                    links: [...el.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))
                } : {present: false};
            }
            out.other = (window.DBChart && DBChart.sliceOther) || null;
            out.unknown = (window.DBChart && DBChart.sliceUnknown) || null;
            out.slice = (window.DBChart && DBChart.slice) || [];
            for (const id of ids) {
                const cv = document.getElementById(id);
                if (!cv) { out.charts[id] = {missing: true}; continue; }
                const c = Chart.getChart ? Chart.getChart(cv) : null;
                if (!c) { out.charts[id] = {noChart: true}; continue; }
                c.options.animation = false; c.update('none');
                const meta = c.getDatasetMeta(0);
                const box = cv.getBoundingClientRect();
                // ⚠⚠ THE LEGEND IS GENERATED, SO IT MUST BE READ. A custom
                // `generateLabels` that calls the wrong default collapses every
                // legend to one entry reading "undefined" — which HAPPENED here
                // 2026-09-16, and the geometry probe reported "fits", because a
                // collapsed legend is narrow. The measurement improved as the
                // thing broke; only the screenshot found it. This reads the
                // labels the legend will actually paint.
                const legend = c.options.plugins.legend.labels.generateLabels(c)
                    .map(i => String(i.text == null ? '' : i.text));
                out.charts[id] = {
                    legend: legend,
                    labels: c.data.labels,
                    values: c.data.datasets[0].data.map(Number),
                    colors: c.data.datasets[0].backgroundColor,
                    // ⚠ ARCS DRAWN, not values supplied. A dataset can be full
                    // while nothing renders -- that is the defect this file exists for.
                    arcs: meta.data.length,
                    drawn: meta.data.filter(a => (a.outerRadius || 0) > 0).length,
                    box: [Math.round(box.width), Math.round(box.height)]
                };
            }
            return out;
        }""", PIES)

        for bid in BANDS:
            band = r["bands"][bid]
            if not band.get("present"):
                problems.append(f"band {bid} is missing")
                continue
            if not band["links"]:
                problems.append(f"band {bid} has no link to its page")
            print(f"  {bid:14} {band['heading']:12} {len(band['links'])} link(s)")

        for cid in PIES:
            c = r["charts"][cid]
            if c.get("missing") or c.get("noChart"):
                problems.append(f"{cid}: no chart instance")
                continue
            n = len(c["values"])
            if c["drawn"] == 0:
                problems.append(f"{cid}: {n} values but ZERO arcs drawn")
            if c["arcs"] != n:
                problems.append(f"{cid}: {n} values but {c['arcs']} arcs")
            if n > 6:
                problems.append(f"{cid}: {n} wedges — the palette has 5 hues + 1 neutral")
            if min(c["box"]) < 80:
                problems.append(f"{cid}: canvas {c['box']} is too small to read")
            # ⚠ TWO NEUTRALS, AND THEY MUST NOT BE SWAPPED. A fold ("41 others")
            # is real categories collapsed for space; an abstention ("Function
            # not identified") is no answer at all. One grey for both put two
            # meanings on one wedge colour, which is how this was shipped first.
            neutrals = {r["other"], r["unknown"]}
            for lab, col in zip(c["labels"], c["colors"]):
                low = str(lab).lower()
                is_fold = low.endswith("others")
                is_unknown = ("not identified" in low or "not recorded" in low
                              or "not yet tagged" in low)
                if is_fold and col != r["other"]:
                    problems.append(f"{cid}: the fold '{lab}' is {col}, not {r['other']}")
                if is_unknown and col != r["unknown"]:
                    problems.append(f"{cid}: the abstention '{lab}' is {col}, "
                                    f"not {r['unknown']}")
                if not (is_fold or is_unknown) and col in neutrals:
                    problems.append(f"{cid}: real category '{lab}' wears a neutral")
            if r["other"] == r["unknown"]:
                problems.append("the fold and the abstention share one colour — "
                                "two claims, one visual")
            # ⚠ The legend is identity. Without it a pie is colour-alone, which
            # the accessibility rule forbids outright.
            leg = c.get("legend") or []
            if len(leg) != n:
                problems.append(f"{cid}: {n} wedges but {len(leg)} legend entries")
            bad = [t for t in leg if not t.strip() or t.strip().lower() == "undefined"]
            if bad:
                problems.append(f"{cid}: legend entries are empty/undefined: {bad}")
            # ⚠ A TRUNCATION THAT MAKES TWO LABELS IDENTICAL IS WORSE THAN A LONG
            # ONE — two wedges, one name. The middle ellipsis keeps the tail
            # precisely so this cannot happen; this asserts it.
            if len(set(leg)) != len(leg):
                problems.append(f"{cid}: truncation collapsed two labels into one: {leg}")
            print(f"  {cid:20} {n} wedges, {c['drawn']} drawn, {c['box']}, "
                  f"{len(leg)} legend entries")

        # ---- every link on the page resolves ---------------------------------
        # ⚠⚠ A LINK THAT LANDS ON A 404 IS WORSE THAN PLAIN TEXT, and this repo
        # has shipped that three times (sd districts, the profile's type row, the
        # budget-lines index). The bands are mostly navigation, so the links ARE
        # the feature; checking they exist is not the same as checking they work.
        import urllib.error
        hrefs = pg.evaluate("""() => {
            const out = new Set();
            for (const id of ['s-contracts','s-products','s-data','s-agreements','s-vendors']) {
                document.getElementById(id).querySelectorAll('a[href]')
                    .forEach(a => out.add(a.href));
            }
            document.querySelectorAll('.db-stat a[href], #ceilingNote a[href]')
                .forEach(a => out.add(a.href));
            return [...out]; }""")
        # ⚠ Non-vacuity: a page that rendered no bands passes a zero-link crawl.
        if len(hrefs) < 40:
            problems.append(f"only {len(hrefs)} links on the page — the bands may not have rendered")
        broken = []
        for h in hrefs:
            try:
                req = urllib.request.Request(h, method="HEAD")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status not in (200, 302):
                        broken.append((h, resp.status))
            except urllib.error.HTTPError as e:
                if e.code not in (200, 302):
                    broken.append((h, e.code))
            except Exception as e:                                  # pragma: no cover
                broken.append((h, repr(e)[:40]))
        print(f"  links: {len(hrefs)} distinct, {len(broken)} broken")
        for h, c in broken[:5]:
            problems.append(f"broken link {c}: {h}")

        # ---- reconciliation: each pie sums to what its own endpoint publishes --
        lic = api("/oce/licenses")
        dat = api("/oce/licenses/data")
        checks = [
            ("ovFunctionChart", sum(x["value"] for x in lic["by_capability"])),
            ("ovRouteChart", sum(x["value"] for x in lic["by_method"])),
            ("ovKindChart", sum(x["value"] for x in dat["content"]["by_kind"])),
            ("ovDataAgencyChart", dat["content"]["value"]),
        ]
        for cid, served in checks:
            got = sum(r["charts"][cid]["values"])
            # float32 accumulation upstream, so compare relatively.
            close = served > 0 and abs(got - served) / served < 1e-4
            print(f"  {cid:20} chart ${got/1e6:,.1f}M vs served ${served/1e6:,.1f}M "
                  f"{'OK' if close else 'MISMATCH'}")
            if not close:
                problems.append(f"{cid}: folds to ${got:,.0f} but its endpoint serves ${served:,.0f}")

        # ---- the storyboard's fixed rail must not paint over the bands -------
        # ⚠⚠ MEASURED 2026-09-18: it did, at EVERY width below 1600, and it was
        # VISIBLE AT 1440 — an orange dot sat on the word "by" in the Data
        # band's lead. Nothing caught it: it is position:fixed, so no flow
        # measurement moves, no element is clipped, no link breaks, and a probe
        # asking "is a dot over a text-bearing element" read 0 of 9 because at
        # 1440 the dots land in a card's left PADDING rather than on a glyph.
        # Only the screenshot showed it. So the assertion is the blunt one: at
        # each band's own scroll position the rail is not painted at all.
        #
        # ⚠ Checked at TWO widths deliberately. The rail's box is a constant
        # [26, 35] at every viewport, so a single width cannot distinguish "the
        # gate works" from "this width happens to have room".
        for width in (1440, 390):
            pg.set_viewport_size({"width": width, "height": 900})
            pg.wait_for_timeout(400)
            for bid in BANDS:
                # ⚠ Re-read the band's position AFTER the scroll settles: the
                # storyboard's sticky stage re-fits and the document height
                # moves under you, so a target computed once lands elsewhere.
                # An earlier probe of mine reported the rail visible over a band
                # purely from measuring a page that had not settled.
                for _ in range(2):
                    pg.evaluate(
                        "(id) => { const e = document.getElementById(id);"
                        " window.scrollTo(0, e.getBoundingClientRect().top + scrollY + 150); }",
                        bid)
                    pg.wait_for_timeout(500)
                shown = pg.evaluate("""() => {
                    const d = document.querySelector('[data-rail-dot]');
                    if (!d) return null;
                    const nav = d.parentElement;
                    const b = nav.getBoundingClientRect();
                    const sb = document.getElementById('dsStoryboard').getBoundingClientRect();
                    return {painted: getComputedStyle(nav).display !== 'none' && b.width > 0,
                            storyOnScreen: sb.bottom > 0 && sb.top < window.innerHeight};
                }""")
                if shown and shown["painted"] and not shown["storyOnScreen"]:
                    problems.append(
                        f"the storyboard rail is painted over {bid} at {width}px, "
                        "with the storyboard itself off screen")
        pg.set_viewport_size({"width": 1400, "height": 1000})

        if errs:
            problems.append(f"uncaught JS: {errs[:3]}")
        b.close()

    print()
    if problems:
        print("PROBLEMS:")
        for p_ in problems:
            print("  -", p_)
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
