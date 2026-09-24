"""A URL in an org card must be able to break, or the PAGE scrolls sideways.

`/organizations` (which 302s to `/organizations/agencies`) rendered
`documentElement.scrollWidth` **1512** against an innerWidth of 1440, and the
innermost offender was a `.stat-val` holding one unbreakable Website URL —
`www1.nyc.gov/site/intergovernmental/federal/...` at 419px, ending exactly on
1512. It is the clipped-tile defect's family: the shared `.db-stat-value` got
`overflow-wrap: anywhere` during the profile redesign, and `.stat-val` is a
different, older class that never did.

⚠ THE GUARD DERIVES ITS VIEW SET rather than naming the two views, so a third
card view that starts rendering a URL tomorrow is covered before it exists —
the same shape as `test_capital_date_one_format`'s view derivation.

⚠ AND IT MUST BE `anywhere`, NOT `break-word`. Only `anywhere` reduces the
element's MIN-CONTENT size, which is what lets the flex item fit its column.
Measured on the real page: a `min-width: 0` rule beside `anywhere` was mutated
away and the page stayed at 1440 — inert, because `anywhere` had already
collapsed the min-content width. Under `break-word` the item's `min-width:auto`
floor is still the whole URL, so the scroll returns.
"""
import re
from pathlib import Path

VIEWS = Path(__file__).resolve().parents[2] / "app" / "resources" / "views"

# ⚠ Blade comments first: the comment in those very views EXPLAINS this rule and
# names both `break-word` and `min-width`, so a scan of the raw text would fire
# on its own prose — this repo's most repeated guard defect.
_BLADE_COMMENT = re.compile(r"\{\{--.*?--\}\}", re.S)


def _code(path: Path) -> str:
    return _BLADE_COMMENT.sub("", path.read_text(encoding="utf-8", errors="replace"))


def _views_putting_a_url_in_a_stat_val():
    """Views whose own code writes a URL-ish value into a `.stat-val`."""
    found = []
    for p in sorted(VIEWS.glob("*.blade.php")):
        code = _code(p)
        for line in code.splitlines():
            if "stat-val" not in line:
                continue
            # the emitting line builds the element AND names a url-bearing source
            if re.search(r"class=\"stat-val", line) and re.search(
                r"\bu\b|url|website|href", line, re.I
            ):
                found.append(p)
                break
    return found


def test_every_view_that_renders_a_url_in_a_stat_val_lets_it_break():
    views = _views_putting_a_url_in_a_stat_val()
    # non-vacuity: a guard that scans nothing passes, which is this repo's
    # oldest defect. The two known emitters are orgsAgencies + orgsDirectory.
    assert len(views) >= 2, f"scanned the views and found only {len(views)} URL emitters"
    names = {p.name for p in views}
    assert {"orgsAgencies.blade.php", "orgsDirectory.blade.php"} <= names, names

    for p in views:
        code = _code(p)
        rule = re.search(r"\.org-card-foot\s+\.stat-val\s*\{([^}]*)\}", code)
        assert rule, f"{p.name}: no `.org-card-foot .stat-val` rule to carry the wrap"
        body = rule.group(1)
        assert "overflow-wrap" in body, (
            f"{p.name}: `.stat-val` holds a URL and declares no overflow-wrap — "
            "the page will scroll sideways (measured 1512 against 1440)"
        )
        value = re.search(r"overflow-wrap\s*:\s*([a-z-]+)", body).group(1)
        assert value == "anywhere", (
            f"{p.name}: overflow-wrap is `{value}`. Only `anywhere` shrinks the "
            "min-content size; `break-word` leaves the flex item's min-width:auto "
            "floor at the whole URL and the sideways scroll returns."
        )
