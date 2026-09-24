"""One owner for "how many records does source table T hold for scope S".

⚠⚠ THE PROBLEM THIS SOLVES IS A WRONG ZERO. The two scoped provenance panels —
`/projects/categories/{slug}` and `/projects/budget-lines/{code}` — render, per
dataset row, a PER-SCOPE record count. The shared component treats those three
outcomes as three different claims, correctly:

    a number   the scoped count
    0          this dataset holds nothing for this scope — a FINDING
    —          we could not ask, and must not imply 0

`/get/pstats-records_no-by_{category,budgetline}` returned **`0` for any table it
had no rule for**, so widening either panel to the spine's three current sources
published a confident, plausible, wrong zero about a dataset the page's own table
draws hundreds of projects from. That is why both panels were left NARROW, with
the reason recorded at each call site, and it is what this module exists to end.

⚠⚠ AND FIVE OF THE ELEVEN COLUMN MAPPINGS THOSE ENDPOINTS DECLARED NAMED A
COLUMN THAT DOES NOT EXIST — measured 2026-09-10, every one a live 500:

    by_budgetline   capprojectsbudgetsandschedule   "BUDGET_LINE"  -> is "Budget Line"
                    capprojectsbudgetandspend       "BUDGET_LINE"  -> no such column
                    capprojectsbudgetspendhistory   "BUDGET_LINE"  -> no such column
                    capprojectsschedulehistory      "BUDGET_LINE"  -> no such column
    by_category     capitalbudget      "Ten-Year Plan Category"    -> no such column

The component renders a 500 as `—`, so nothing published a wrong figure; but
"we could not ask" was standing in for "this table cannot carry that dimension",
which are different answers and only one of them is true. Every mapping here is
taken from `information_schema`, not from a plausible-looking name.

=== TWO WAYS TO COUNT, AND THE DIFFERENCE IS MEASURED

`own`        the table's OWN scope column matches.
`crosswalk`  the table has no such column, so its rows are counted through the
             project they belong to, via the spine.

⚠⚠ THEY ARE NOT INTERCHANGEABLE, AND THE GAP IS LARGE. Measured on `EP 0007`:

    capitalprojectscommitments   own "budgetline"      82 rows
                                 via the crosswalk    568 rows
    capprojectsbudgetsandschedule own "Budget Line"     33 rows
                                 via the crosswalk    405 rows

A project is funded through SEVERAL budget lines, so the crosswalk counts every
row of every project that touches this line — including its rows about other
lines. The panel's own sentence is *"counting the records in each budget line"*,
so `own` is the answer wherever a table has the column, and `crosswalk` is used
ONLY where it cannot be asked otherwise. The endpoint SERVES which method it
used, so two rows in one panel computed differently are distinguishable rather
than silently mixed.

=== THE SPINE JOINS ARE THE BUILDER'S OWN, AND THEY WERE CROSS-CHECKED

Each join is copied from `build_capital_projects.py`, which is where the identity
rule lives, never re-derived. Coverage, measured 2026-09-10:

    capitalprojectslist            12,929 of 12,929 rows join
    capitalprojectscommitments     41,277 of 41,277
    capprojectsbudgetsandschedule  56,525 of 56,525

⭐ AND THE CPDB JOIN IS VERIFIED AGAINST AN IDENTITY THE SPINE ALREADY PUBLISHES.
`capitalprojectslist` IS the current plan — 12,929 rows, exactly the spine's
`in_current_plan` count — so its crosswalked count for any category must equal
the spine's in-plan count for that category. Across all **138** category slugs:
**0 disagree**. A join that produced plausible numbers without that check would
be indistinguishable from a wrong one.

=== COST, MEASURED BEFORE SHIPPING

The panel fires one request per dataset row on page load (5 on the category
page, 6 on the budget-line page), in parallel. Warm, through the endpoint:

    capitalprojectslist            15ms   (crosswalk)
    capitalprojectscommitments     16ms   (crosswalk)
    capprojectsbudgetsandschedule  58ms   (own column, 56,525 rows)
    capitalprojectsdollarscomp     83ms   (own column, 72,437 rows + a slug)
    largest budget line, P-I001    23ms / 47ms

⭐ The CROSSWALKED paths are the CHEAPEST, which is worth knowing because the
instinct is the opposite: they filter the spine on an indexed scope first and
join 12,929 / 41,277 rows to that, where the own-column paths compute a slug or
a normalisation over every row of a 56k–72k-row table. So no index was added,
and that decision is recorded here rather than left to be re-derived.

⚠ `capitalprojectslist.typecategory` is NOT the Ten-Year taxonomy — it is CPDB's
coarse 3-value ASSET class, the same two-things-called-category ambiguity this
repo retired on `/get/capital/stats/category/...`. It is therefore NOT declared
as an `own` column for `ten_year_category`; that table goes through the
crosswalk.
"""
try:
    import budgetline
    import capitalslug
except ImportError:  # pragma: no cover - both import shapes are used in this repo
    from modules import budgetline, capitalslug


# The two scope dimensions these panels ask about, and what the caller must pass
# as `$1` for each. Declared rather than inferred, because passing a slug where a
# name is expected returns 0 and 0 is a claim.
#
#   ten_year_category  the SLUG, compared through `modules/capitalslug` on BOTH
#                      sides (invariant 3).
#                      ⚠⚠ COMPARING RESOLVED NAMES INSTEAD WAS TRIED AND IS
#                      WRONG — measured, not argued. Of the 138 spine category
#                      names, `capitalstrategy` spells only **5** the same way
#                      and **124** match only after case-folding (`ROUTINE
#                      RECONSTRUCTION` against `Routine Reconstruction`), so a
#                      name comparison returned **0** on that source for 124 of
#                      138 category pages. A wrong zero is the exact defect this
#                      module exists to remove, so it nearly reintroduced it in
#                      the fix. The Dashboard alone would have been safe (0
#                      case-only pairs), which is why measuring ONE source is
#                      not measuring the rule.
#   budget_line        the NORMALISED key, `budgetline.norm(...)`. Five sources
#                      punctuate one line five ways and a raw comparison joins
#                      nothing.
DIMENSIONS = ('ten_year_category', 'budget_line')

# ⚠ Every column name here was read out of `information_schema`, and the spelling
# is the whole point: `capprojectsbudgetsandschedule` has `Budget Line` and
# `Ten Year Plan Category` — no underscores, and NO HYPHEN in "Ten Year", unlike
# `capitalstrategy`'s `Ten-Year Plan Category`. The previous maps guessed and
# 500'd.
SOURCES = {
    'capitalprojectslist': {
        # ⚠ The builder's own key expressions, copied not re-derived.
        'join': ("lpad(btrim(t.magency),3,'0') = p.agency_key"
                 " AND upper(btrim(t.projectid)) = p.fms_id"),
        'own': {},   # `typecategory` is the ASSET class; no budget-line column
    },
    'capitalprojectscommitments': {
        # ⚠ `maprojid`, which is what `_attach_budget_lines` joins on.
        'join': "btrim(t.maprojid) = p.maprojid",
        'own': {'budget_line': 't.budgetline'},
    },
    'capprojectsbudgetsandschedule': {
        # ⚠ The Dashboard's `FMS ID` is BARE, so the agency comes from its
        # acronym through the same `agencymap` the builder derives from CPDB.
        # 24 of 25 acronyms resolve; the one that does not (EDC) keeps the
        # acronym as its key, in the builder and here, so a real project is not
        # lost to a lookup miss.
        'join': ("p.agency_key = coalesce(am.code, btrim(t.\"Managing Agency\"))"
                 " AND p.fms_id = upper(btrim(t.\"FMS ID\"))"),
        'needs_agencymap': True,
        'own': {'budget_line': 't."Budget Line"',
                'ten_year_category': 't."Ten Year Plan Category"'},
    },
    # ── the sources that carry the dimension and need no crosswalk ──────────
    # ⚠ These have no spine join declared, so they can only be counted on their
    # own column. Asking for a dimension they do not carry returns None — the
    # honest "we cannot scope this table", which the component renders as `—`.
    'capitalbudget': {
        'own': {'budget_line': 't."Budget Line"'},
    },
    'capitalcommitmentplan': {
        'own': {'budget_line': 't."Budget Line"'},
    },
    'capitalstrategy': {
        # ⚠ HYPHENATED here, and not in the Dashboard. Two publishers, two
        # spellings of one phrase.
        'own': {'ten_year_category': 't."Ten-Year Plan Category"'},
    },
    'capitalprojectsdollarscomp': {
        # ⚠⚠ THE SERIES NYC RETIRED 2023-10-26, and it is STILL a real source of
        # the spine — `build_capital_projects.py` reads it for scope text,
        # borough and the 2023 budgets — so counting it is accurate and naming
        # it in a provenance panel is correct. What is NOT correct is letting
        # its figure sit unlabelled beside four current sources: measured on
        # `/projects/categories/routine-reconstruction`, this row rendered
        # **2,671** next to 413 / 953 / 3,465 with a BLANK "Last Updated" and
        # nothing saying the series stops in October 2023. The reader forms a
        # ratio from adjacency, so the label travels with the row.
        'retired': '2023-10-26',
        'own': {'budget_line': 't."BUDGET_LINE"',
                'ten_year_category': 't."TYP_CATEGORY_NAME"'},
    },
    'capitalprojectsmilestones': {
        # ⚠ Retired in the same event. Declared here for the retirement fact
        # alone: it carries neither dimension and no join is declared, so it
        # answers "cannot be scoped" rather than 0 — which is true.
        'retired': '2023-10-26',
        'own': {},
    },
}

# ⚠ Derived from CPDB exactly as the builder derives it, so the Dashboard is
# keyed the same way in both places. 1:1 in this direction (0 acronyms map to
# more than one code), measured.
_AGENCYMAP = ("agencymap AS (SELECT DISTINCT btrim(magencyacro) AS acro,"
              " lpad(btrim(magency),3,'0') AS code FROM capitalprojectslist"
              " WHERE btrim(coalesce(magencyacro,'')) <> '')")

# The spine-side predicate for each dimension, used only on the crosswalk path.
_SPINE_PREDICATE = {
    # ⚠ Slugged on the spine side too, by the same owner, so the crosswalk and
    # the own-column paths compare the same key.
    'ten_year_category': (capitalslug.SLUG_SQL.format(col='p.ten_year_category')
                          + " = $1"),
    # ⚠ `unnest`, not `&&`: the array holds the RAW spelling, so a normalised
    # match cannot use the GIN index. Measured at page scale on the largest
    # line, which is why no normalised column exists.
    'budget_line': ("EXISTS (SELECT 1 FROM unnest(p.budget_lines) bl WHERE "
                    + budgetline.sql_norm('bl') + " = $1)"),
}


def _own_predicate(dimension, col):
    """How a table's OWN column is compared, per dimension.

    ⚠ Both dimensions go through the rule's ONE owner — `modules/budgetline` for
    the punctuation and `modules/capitalslug` for the slug — never a re-typed
    pattern. Every source spells both dimensions differently: five punctuations
    of a budget line, and 124 of 138 category names differing from the spine's
    by case alone.
    """
    if dimension == 'budget_line':
        return budgetline.sql_norm(col) + " = $1"
    return capitalslug.SLUG_SQL.format(col=col) + " = $1"


def count_sql(table, dimension):
    """SQL counting `table`'s records in one scope, plus HOW it was counted.

    Returns `(sql, via)` where `sql` takes exactly one parameter, or
    `(None, None)` when this table cannot answer for this dimension.

    ⚠⚠ `(None, None)` IS NOT ZERO, and the caller must not turn it into one.
    "This table carries no such dimension and belongs to no project we can
    resolve" and "this table holds no record for this scope" are different
    claims; the second is a finding and the first is an absence of one.
    """
    spec = SOURCES.get((table or '').lower())
    if not spec or dimension not in DIMENSIONS:
        return None, None

    own_col = (spec.get('own') or {}).get(dimension)
    if own_col:
        return ("SELECT count(*) AS res FROM %s t WHERE %s"
                % (_qualify(table), _own_predicate(dimension, own_col))), 'own'

    join = spec.get('join')
    if not join:
        return None, None

    prefix = ("WITH " + _AGENCYMAP + " ") if spec.get('needs_agencymap') else ""
    am = (" LEFT JOIN agencymap am ON am.acro = btrim(t.\"Managing Agency\")"
          if spec.get('needs_agencymap') else "")
    return (prefix
            + "SELECT count(*) AS res FROM %s t%s"
              " JOIN capital_projects p ON %s WHERE %s"
              % (_qualify(table), am, join, _SPINE_PREDICATE[dimension])
            ), 'crosswalk'


def _qualify(table):
    """The table name, validated as a plain identifier and quoted.

    ⚠ The table arrives from a URL path segment. It is only ever one of
    `SOURCES`' keys by the time this is called, but the identifier is still
    taken from the KEY rather than from the caller's string, so no request value
    reaches the SQL text — `CsvDataset.delete` is the precedent this repo already
    paid for.
    """
    key = (table or '').lower()
    if key not in SOURCES:
        raise KeyError(table)
    return '"%s"' % key


def retired(table):
    """The date NYC retired this publication, or None if it is current.

    ⚠ ONE OWNER for the retirement fact, so a scoped provenance panel can label
    a 2023-series figure the same way the record-mode panel does. A guard pins
    this against `capital_source_coverage`'s own `retired` flags — the same
    fact declared twice, in two shapes, is what this repo keeps paying for, and
    where it cannot be derived it must at least be checked.
    """
    return (SOURCES.get((table or '').lower()) or {}).get('retired')


def scopable(dimension):
    """Every table that can answer for this dimension, with how. For guards and
    for anyone widening a panel: a table absent from this list renders `—`."""
    out = {}
    for name in SOURCES:
        sql, via = count_sql(name, dimension)
        if sql:
            out[name] = via
    return out
