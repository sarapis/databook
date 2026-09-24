"""One owner for the capital slug rule, in Python AND in SQL.

⚠⚠ TWO SPELLINGS OF THIS ONE RULE IS HOW `/projects/categories/{slug}` CAME TO
BE UNABLE TO MATCH ITS OWN URLS. The endpoint compared `REPLACE(cat,' ','-')`
against a link built with Laravel's `Str::slug`, and **12 of 138** categories
carry a comma — so those pages fell through to a loose `ILIKE '%…%'`, which is
worse than missing: `sewers` also matches `COMBINED SEWERS AND WATER MAINS`, so
a category page could list another category's projects.

⚠⚠ AND A SECOND CONSUMER IS WHY THIS MOVED OUT OF `routers/capital.py`
(2026-09-10). `modules/capitalsources` counts a source table's records for one
scope, and for a Ten-Year category it must slug BOTH sides. The alternative
considered was to resolve the slug to the spine's canonical NAME once and
compare names — and it was MEASURED and rejected, because it is wrong:

    of the 138 spine category names, `capitalstrategy` spells only **5** the
    same way; **124** match only after case-folding (`ROUTINE RECONSTRUCTION`
    against `Routine Reconstruction`)

so a name comparison would have returned **0** on that source for 124 of 138
category pages — a confident, plausible, wrong zero, which is the exact defect
the scoped-count work exists to remove. Slug both sides, with one rule.

⚠ The router keeps `_slug` / `_SLUG_SQL` as names bound to these, so existing
callers and guards read the same values; what is gone is the second copy.
"""
import re

# ⚠ `{col}` is substituted by the caller with an already-quoted column
# expression. Kept as a format string rather than a function so a guard can read
# the character class straight out of it.
SLUG_SQL = "trim(both '-' from regexp_replace(lower({col}), '[^a-z0-9]+', '-', 'g'))"


def slug(value):
    """Laravel's `Str::slug`, in Python — and it MUST agree with `SLUG_SQL`.

    A guard runs this over the real category and family vocabularies and parses
    the character class OUT of `SLUG_SQL` to compare, rather than re-typing it:
    a guard that reimplements the thing it guards measures a different system.

    >>> slug('Water Mains, Sources and Treatment')
    'water-mains-sources-and-treatment'
    >>> slug('  Parks and Recreation  ')
    'parks-and-recreation'
    >>> slug(None), slug('')
    ('', '')
    """
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
