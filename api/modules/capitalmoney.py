"""One owner for what each capital money figure MEANS, and why they are not a funnel.

⚠⚠ THE DEFECT THIS PREVENTS. CPDB publishes six money columns that read like
successive stages of one pot — planned, adopted, allocated, committed, spent,
plus a Checkbook-derived spend. They are not. Adopted funding is more than twice
planned commitments; committed is a third of spent; and each column is populated
on a different subset of projects. Drawn as a funnel — which is what
docs/CAPITAL-SECTION-PLAN.md §5.3 originally proposed — this shows money
vanishing between stages that are not stages.

⚠ Owner decision, 2026-09-05: **show them as separate measures, each with its own
population, each with an info note, plus one note saying why they do not sum or
nest.** This module owns that copy so the endpoint and the page cannot drift —
the same reason `contractkind` owns whether an amount is money or a ceiling.

⚠⚠ THE FIGURES LIVE IN `MEASURES`, NOT IN THIS PROSE. An earlier draft of this
docstring carried the measured table, and two of its six totals had already
drifted from the machine-readable values a few lines below them — a hand-typed
figure sitting beside the one it was copied from, which is the defect #240
recorded and this file reproduced within a day. Every baseline now has exactly
one home in `MEASURES` (`baseline_total_usd`, `baseline_population`), and
`test_the_baselines_are_not_restated_in_prose` fails the build if a dollar
figure reappears here. Describe the RELATIONSHIPS; let the code carry the
numbers.

⚠⚠ THE DEFINITIONS ARE THE PUBLISHER'S, QUOTED, NOT OURS. Writing our own
explanation of what "allocated" means in NYC's capital budgeting would be
inventing authority we do not have. Where DCP's own wording is thin, it stays
thin and `source` says whose words they are. The one thing we assert in our own
voice is the ARITHMETIC — the totals and populations in `MEASURES` — because we
measured it, and `basis` marks it as ours.

⚠ `plannedcommit_total` is the one with a real published definition, from DCP's
CPDB documentation: a project is funded by many individual planned commitments,
and this is their sum.
"""

# Publisher attribution strings, so a reader can tell whose claim they are
# reading. ⚠ Never blend them — DCP documents the plan; the Comptroller
# publishes the payments.
_DCP = "NYC Department of City Planning, Capital Projects Database"
_CHECKBOOK = "Office of the Comptroller, Checkbook NYC (via CPDB)"

# ⚠ `baseline_*` are measured 2026-09-05 against `capital_program_stats`
# (scope_type='program'): 17,024 projects in the spine, of which the 12,929 in
# ccpversion fisa_2026 are the only ones carrying money columns at all. They are
# the DOCUMENTED baseline and are NEVER served — the live figure is computed per
# scope and served beside each measure, so a page can never show a hardcoded
# total. If a served number drifts far from its baseline the SOURCE changed
# shape, and this file should be re-measured rather than the page patched.
MEASURES = [
    {
        "key": "planned_usd",
        "column": "plannedcommit_total",
        "label": "Planned commitments",
        "definition": (
            "The sum of the individual planned commitments funding this "
            "project in the current Capital Commitment Plan. One project is "
            "funded by many commitments."
        ),
        "source": _DCP,
        "baseline_population": 9213,
        "baseline_total_usd": 201604000000.0,
    },
    {
        "key": "adopt_usd",
        "column": "adopt_total",
        "label": "Adopted",
        "definition": (
            "Sum of the total adopted funding associated with the project "
            "within the City's budget."
        ),
        "source": _DCP,
        "baseline_population": 11650,
        "baseline_total_usd": 427126000000.0,
    },
    {
        "key": "allocate_usd",
        "column": "allocate_total",
        "label": "Allocated",
        "definition": (
            "Sum of the total allocated funding associated with the project "
            "within the City's budget."
        ),
        "source": _DCP,
        "baseline_population": 10767,
        "baseline_total_usd": 308972000000.0,
    },
    {
        "key": "committed_usd",
        "column": "commit_total",
        "label": "Committed",
        "definition": (
            "Sum of the total committed funding associated with the project "
            "within the City's budget."
        ),
        "source": _DCP,
        "baseline_population": 5158,
        "baseline_total_usd": 30384000000.0,
    },
    {
        "key": "spent_usd",
        "column": "spent_total",
        "label": "Spent",
        "definition": (
            "Sum of the total funding spent associated with the project "
            "within the City's budget."
        ),
        "source": _DCP,
        "baseline_population": 7118,
        "baseline_total_usd": 87769000000.0,
    },
    {
        "key": "checkbook_usd",
        "column": "spent_total_checkbooknyc",
        "label": "Paid (Checkbook NYC)",
        "definition": (
            "Sum of check values from Checkbook NYC associated with the "
            "project — money the City has actually paid out."
        ),
        "source": _CHECKBOOK,
        "baseline_population": 6507,
        "baseline_total_usd": 70711000000.0,
    },
]

MEASURE_KEYS = [m["key"] for m in MEASURES]

# ⚠⚠ THE NOTE THAT MUST APPEAR WHEREVER MORE THAN ONE MEASURE IS SHOWN.
# Without it a reader subtracts two of these and reports a shortfall that is an
# artefact of the columns, not a fact about the project.
NOT_A_FUNNEL_NOTE = (
    "These are six separate measures, not stages of one pot, and they do not "
    "sum or nest. They cover different windows — committed funding is what was "
    "committed within the current plan period, while spent is cumulative over "
    "the project's whole life — and each is published for a different set of "
    "projects, shown beside it. Citywide, adopted funding is more than twice "
    "planned commitments and committed is a third of spent. Subtracting one "
    "from another does not give an amount outstanding."
)

# ⚠ THE SINGLE-PROJECT VARIANT. On one project there are no populations to show,
# so the citywide note's "shown beside it" clause would point at nothing. The
# argument is unchanged — the measures still cover different windows and still do
# not nest — but the evidence a reader can see is different, so the sentence that
# cites that evidence is different. ⚠ Do NOT serve the citywide note on a project
# page: it names a denominator that is not on the page.
NOT_A_FUNNEL_NOTE_PROJECT = (
    "These are six separate measures, not stages of one pot, and they do not "
    "sum or nest. They cover different windows — committed funding is what was "
    "committed within the current plan period, while spent is cumulative over "
    "the project's whole life. A measure shown as not published is one the City "
    "does not publish for this project, which is not the same as zero. "
    "Subtracting one from another does not give an amount outstanding."
)

# ⚠ The publisher's own limitation, quoted, because it is the reason a reader
# should not treat any single figure as complete.
PUBLISHER_CAVEAT = (
    "The Capital Projects Database is not a project or financial management "
    "system. Budgetary information may be incomplete since all monies "
    "committed to or spent on a project may not be captured."
)
PUBLISHER_CAVEAT_SOURCE = _DCP

# ⚠ The one measured claim in our own voice, marked as ours rather than the
# publisher's — see the module docstring.
BASIS = "measured by Databook against the published Capital Commitment Plan"


def measure(key):
    """One measure's metadata, or None."""
    for m in MEASURES:
        if m["key"] == key:
            return m
    return None


def payload(values=None, populations=None, scope="program"):
    """The money block an endpoint serves.

    `values` and `populations` are per-key dicts from the stats/spine row. A
    measure with no value still appears, carrying `value: None` — an absent
    figure is "not published for this project", which is information, and
    dropping it would make the set look smaller than it is.

    ⚠ `scope` selects the note, and the two are not interchangeable: the
    programme/scope note cites populations shown beside each measure, which a
    single project does not have. Anything other than "project" gets the
    citywide note.
    """
    values = values or {}
    populations = populations or {}
    note = NOT_A_FUNNEL_NOTE_PROJECT if scope == "project" else NOT_A_FUNNEL_NOTE
    return {
        "measures": [
            {
                "key": m["key"],
                "label": m["label"],
                "definition": m["definition"],
                "source": m["source"],
                "value": values.get(m["key"]),
                "population": populations.get(m["key"]),
            }
            for m in MEASURES
        ],
        "note": note,
        "publisher_caveat": PUBLISHER_CAVEAT,
        "publisher_caveat_source": PUBLISHER_CAVEAT_SOURCE,
        "basis": BASIS,
    }
