"""Which silent degradations in `oce.py` are allowed to stay silent.

⚠⚠ THE DEFECT CLASS. Every `except` in `oce.py` returns degraded data with HTTP
200 — a missing panel, a blank column, a flag that never sets. That is correct
behaviour: one broken enrichment must not take a page down. The problem is that
it is also **indistinguishable from the truth**. A page with no AI flags looks
exactly like a page whose contracts have no flags to show.

Logging alone does not fix it, and #249 measured why:

    sentry_sdk's LoggingIntegration is auto-enabled with an EventHandler at
    ERROR (40) and a BreadcrumbHandler at INFO (20). So `logger.error` raises a
    Sentry EVENT, while `logger.warning` produces a BREADCRUMB — and a breadcrumb
    ships only if an ERROR follows IN THE SAME request scope. No `oce.py`
    degradation path raises, so no error ever follows, so the breadcrumb is
    discarded when the scope closes.

Confirmed against Sentry's own history: across 90 days, ZERO issues in
`databook-api` match any of these messages, while all 17 warning-level issues
come from shell scripts calling `capture_message(level='warning')`.

So the LEVEL is the whole decision, and it is a judgement about blast radius:

  ERROR   — the failure removes a whole SECTION or a queue-wide SIGNAL for every
            user, from a table that exists on prod. Silence here publishes a
            wrong answer, so it should raise a Sentry event.
  WARNING — the failure degrades ONE row, ONE entity's optional enrichment, or a
            link; or it is a cache/probe path that self-heals on the next
            request. Absence is a normal outcome here, so an event would be
            noise and the alert would be muted within a week.

⚠ THIS FILE'S JOB IS THE DIRECTION THAT CATCHES CODE NOBODY HAS WRITTEN YET. A
new `except` added to `oce.py` fails here until someone states which of the two
it is. Left alone it would default to WARNING — invisible — which is exactly how
the current set accumulated.

⚠ It reads the AST, not the text: a `logger.warning` quoted inside a comment or
docstring is prose, not a call site, and a scanner that cannot tell them apart
reports problems that are not there.
"""

import ast
import os

import pytest

_API_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_OCE = os.path.join(_API_DIR, "routers", "oce.py")

# skeleton of the logged message -> (required level, why it is that level)
#
# The skeleton is the f-string's literal parts with `{}` where an interpolation
# was; it is stable across renaming a variable and unique per site.
INVENTORY = {
    # ---- WARNING: the precomputed read paths, which have a live fallback ----
    # ⚠ These two are WARNING precisely because failing them costs NOTHING
    # visible: both fall back to the DuckDB scan they replaced. An absent table is
    # also the legitimate state before build_contract_timeline.py has ever run, so
    # ERROR here would alert on a correct fresh environment. The thing that WOULD
    # deserve an event — the spend map failing outright — is already declared
    # below as "[contracts] spend-map build failed".
    "[contracts] precomputed spend map unavailable: {}":
        ("warning", "falls back to the live background DuckDB scan; the page is "
                    "slower, not wrong, and an absent table is the pre-build state"),
    # ⚠ The call-center lens's membership seed. A WARNING because the endpoint
    # returns `available: false` and the PAGE says the lens is unavailable —
    # nothing else in the section reads this seed, and the failure removes one
    # page rather than corrupting a figure. ⚠⚠ The alternative would be far
    # worse: degrading to a text pattern would repopulate the lens with the
    # over-matches that made this a curated list in the first place (a
    # geotechnical contract number, a shelter's street address, crisis
    # shelters), and a half-wrong lens reads exactly like a right one.
    "[oce] call-center seed unreadable: %s":
        ("warning", "the call-center lens reports itself unavailable and the "
                    "page says so; no other surface reads this seed, and the "
                    "only worse option is silently falling back to a pattern"),
    "[contract {}] related-contracts lookup failed: {}":
        ("warning", "the Related contracts block disappears from ONE contract "
                    "page; every other section still renders, and the block is "
                    "navigational rather than a figure anyone quotes"),
    "[contract] precomputed detail unavailable: {}":
        ("warning", "falls back to _query_contract_detail for that one contract; "
                    "identical output, just scanned instead of read"),
    # ⚠ WARNING for the SAME reason as the related-contracts line above, plus a
    # stronger one: an absent `contract_program` is the legitimate state before
    # build_program_groups.py has ever run, and only 11 contracts are in any
    # program today, so ERROR would alert on a correct fresh environment on
    # every request. The panel is additive — no figure elsewhere on the page
    # depends on it, and its disappearance cannot make another number wrong.
    "[contract {}] program lookup failed: {}":
        ("warning", "the program panel disappears from ONE contract page; an "
                    "absent contract_program table is the pre-build state, and "
                    "no other figure on the page is derived from it"),
    # ---- ERROR: a whole section or a queue-wide signal, gone for everyone ----
    "[oce] notices-for-epins query failed: {}":
        ("error", "the City Record notices panel on solicitation/contract/vendor "
                  "pages disappears for every user; crol exists on prod"),
    "[oce] PASSPort sub-table probe failed: {}":
        ("error", "the probe gates the ENTIRE PASSPort block — principals, "
                  "ratings, entity summary — for every vendor profile"),
    "[contracts] spend-map build failed: {}":
        ("error", "no spend or utilization on any contract, and 'no spend data' "
                  "renders the same as '$0 spent'"),
    "[contracts] meta join failed: {}":
        ("error", "purpose and expense_category go silently blank on every "
                  "contract row"),
    "[oce] digital spend scan failed: {}":
        ("error", "disables the `underused` flag queue-wide; a missing spend "
                  "figure is indistinguishable from a real one"),
    "[oce] composition unavailable: {}":
        ("error", "the Overview's whole composition bar; `available: False` "
                  "renders as nothing at all"),
    "[oce] expiring successor lookup failed: {}":
        ("warning", "one dossier line per row degrades to 'none on record'; "
                    "nothing is flagged on it (the flag it replaced was retired "
                    "2026-09-24)"),
    "[oce] vendor concentration lookup failed: {}":
        ("error", "queue-wide signal — every row silently loses its lock-in flag"),
    "[oce] vendor+agency lookup failed: {}":
        ("error", "queue-wide signal — every row silently loses its "
                  "renewal-chain flag"),
    "[oce] enrichment lookup failed (table missing?): {}":
        ("error", "EVERY AI flag on the page. The message asks 'table missing?' "
                  "because that is the fresh-env cause, but Sentry runs only "
                  "where the table exists, so firing means broken, not fresh"),
    "[oce] pipeline vendor set unavailable: {}":
        ("error", "the whole pipeline block returns an empty shell that a reader "
                  "cannot distinguish from 'there are no vehicles'"),
    # ⚠ The four section-search arms are WARNING, not ERROR, and the reasoning is
    # the same split routers/search.py::_rows already makes: each arm degrades
    # ALONE (its own try/except), so one failing costs its group and leaves the
    # other three answering — a per-group loss, not a page-wide one. And the
    # likeliest cause is a derived table absent in a fresh environment, which this
    # repo deliberately treats as a legitimate state rather than an incident.
    # ⚠ What makes the silence acceptable HERE and not in #256 is that the payload
    # always returns every group with a count, so an empty arm is visible in the
    # response instead of being indistinguishable from "no matches".
    "[oce] section search: products arm failed: {}":
        ("warning", "one search group loses its rows; the other three still "
                    "answer, and an absent license_family is a fresh-env state"),
    "[oce] section search: vendors arm failed: {}":
        ("warning", "one search group only — see the products arm"),
    "[oce] section search: agencies arm failed: {}":
        ("warning", "one search group only — see the products arm"),
    "[oce] section search: contracts arm failed: {}":
        ("warning", "one search group only — see the products arm"),
    "[oce] renewal calendar unavailable: {}":
        ("error", "the Contracts page's renewal calendar disappears entirely, and "
                  "an absent calendar reads as 'nothing renews' on the page whose "
                  "whole subject is what renews when — the permanently-red "
                  "monitor's shape, inverted"),
    "[oce] award-by-start-year failed: {}":
        ("error", "the Overview's whole by-year chart goes, and it is the only "
                  "view in which the section's value is broken out over time — "
                  "same reasoning as the composition bar above. The page states "
                  "'unavailable' rather than rendering nothing, so the reader can "
                  "tell a failure from an empty universe, but nobody would be "
                  "alerted at WARNING"),
    # pre-existing ERRORs, pinned so a future edit cannot quietly demote them
    "[cache] transactions pre-warm failed: {}":
        ("error", "pre-existing — the outer warm failed entirely, not one widget"),
    "OCE stats query failed: {}":
        ("error", "pre-existing — the homepage procurement stats"),
    "[cache] Failed to refresh dashboard stats: {}":
        ("error", "pre-existing — the dashboard's cached stats"),
    "[cache] Failed to warm digital reform cache: {}":
        ("error", "pre-existing — the digital-reform cache never builds"),

    # ---- WARNING: one row, one entity, or a self-healing path ----
    "[spending] could not apply pragma {}: {}":
        ("warning", "a DuckDB performance pragma; costs speed, not correctness"),
    "[cache] dashboard warm '{}' failed: {}":
        ("warning", "one widget's warm; the request path recomputes it"),
    "[oce] SBS lookup failed for {}: {}":
        ("warning", "one vendor's SBS panel — 46% of vendors legitimately have no "
                    "SBS row, so absence is a normal outcome"),
    "[oce] PASSPort sub-table query failed for {}: {}":
        ("warning", "one sub-query within an already-probed block; the probe "
                    "above it is the ERROR that means the block is gone"),
    "[oce] DOS lookup failed for {}: {}":
        ("warning", "one vendor's legal-entity card; 57% of vendors have none"),
    "[oce] Doing Business lookup failed for {}: {}":
        ("warning", "one vendor's LL34 panel; most vendors have no row"),
    "[oce] Doing Business entity lookup failed: {}":
        ("warning", "the entity half of one vendor's LL34 panel"),
    "[oce] NYCHA vendor activity lookup failed for {}: {}":
        ("warning", "one vendor's NYCHA block; only crosswalked vendors have one"),
    "[oce] org crosswalk lookup failed for {}: {}":
        ("warning", "one vendor's civic-record link; 53 of 1,248 orgs are vendors"),
    "[filter-options] expense_category list failed: {}":
        ("warning", "one dropdown's options; the page and its data still render"),
    "[contract {}] detail query failed: {}":
        ("warning", "one contract's payment timeline"),
    "[contract {}] evaluations lookup failed: {}":
        ("warning", "one contract's MOCS ratings; 72% of contracts have none"),
    "[oce] related-notices query failed for {}: {}":
        ("warning", "one solicitation's notices"),
    "[oce] expiring notices lookup failed: {}":
        ("warning", "per-row notice enrichment on the queue page; the rows and "
                    "every flag still render"),
    "[oce] org vendor-activity lookup failed for {}: {}":
        ("warning", "one org's procurement block, and it returns an explicit "
                    "`available: False` the page can react to"),
    "[spending] schema probe failed; assuming base columns: {}":
        ("warning", "has a declared fallback — it assumes the base column set "
                    "and says so"),
    "[transactions] vendor id resolution failed: {}":
        ("warning", "deep links only; the payee names still render truthfully"),
    "[transactions] contract id resolution failed: {}":
        ("warning", "deep links only; the contract ids still render truthfully"),
    "[spending/top] vendor id resolution failed: {}":
        ("warning", "deep links on the Top Payees cards; the names and the "
                    "dollar figures are unaffected"),
    "[spending/top] contract id resolution failed: {}":
        ("warning", "deep links on the Top Contracts cards; the ids still render "
                    "as text"),
    "[subvendors] vendor id resolution failed: {}":
        ("warning", "deep links on the sub-vendor table; prime and payee names "
                    "still render"),
}


def _skeleton(call):
    """The literal parts of the logged message, with `{}` per interpolation."""
    arg = call.args[0] if call.args else None
    if isinstance(arg, ast.JoinedStr):
        out = []
        for v in arg.values:
            out.append(v.value if isinstance(v, ast.Constant)
                       and isinstance(v.value, str) else "{}")
        return "".join(out).strip()
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value.strip()
    return None


def _sites():
    """(level, skeleton, lineno) for every logger.warning/error inside an except."""
    with open(_OCE, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    found = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler):
            continue
        for node in ast.walk(handler):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("warning", "error")
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "logger"):
                sk = _skeleton(node)
                if sk:
                    found.append((node.func.attr, sk, node.lineno))
    return found


def test_every_degradation_site_has_a_declared_level():
    sites = _sites()
    # ⚠ Assert the scan LOOKED, or an AST change silently empties this guard.
    assert len(sites) > 25, (
        f"only found {len(sites)} degradation sites in oce.py -- the walk found "
        "almost nothing and this guard would pass vacuously"
    )

    untriaged = [f"L{ln}: {sk!r} (currently {lvl})"
                 for lvl, sk, ln in sites if sk not in INVENTORY]
    assert not untriaged, (
        "new degradation site(s) in oce.py with no declared level. Decide which "
        "this is and add it to INVENTORY:\n"
        "  ERROR   -> a whole section or queue-wide signal is gone for everyone\n"
        "  WARNING -> one row/entity/link, or a path that self-heals\n"
        "Left undeclared it defaults to WARNING, which reaches Sentry as a "
        "breadcrumb only and therefore alerts nobody:\n  " + "\n  ".join(untriaged)
    )


def test_no_site_has_drifted_from_its_declared_level():
    wrong = []
    for lvl, sk, ln in _sites():
        want = INVENTORY.get(sk)
        if want and want[0] != lvl:
            wrong.append(f"L{ln}: {sk!r} is logger.{lvl}, declared {want[0]} "
                         f"-- {want[1]}")
    assert not wrong, (
        "a degradation site's level no longer matches its declared blast "
        "radius:\n  " + "\n  ".join(wrong)
    )


def test_the_inventory_has_no_stale_entries():
    """The other direction: an entry for a site that no longer exists is a lie
    about what is covered, and hides that the real site went untriaged."""
    live = {sk for _, sk, _ in _sites()}
    stale = sorted(set(INVENTORY) - live)
    assert not stale, (
        "INVENTORY names sites that no longer exist in oce.py -- remove them, "
        "and check the code they described did not simply move:\n  "
        + "\n  ".join(repr(s) for s in stale)
    )


def test_every_entry_states_a_reason():
    """A level with no reason is an opinion, and the next person cannot tell
    whether it was measured or assumed."""
    thin = [sk for sk, (_, why) in INVENTORY.items() if len(why.strip()) < 20]
    assert not thin, (
        "these INVENTORY entries declare a level with no real reason:\n  "
        + "\n  ".join(repr(s) for s in thin)
    )


def test_both_levels_are_actually_used():
    """Guards against a future 'simplification' that promotes or demotes
    everything -- either would make the distinction meaningless."""
    levels = {lvl for lvl, _ in INVENTORY.values()}
    assert levels == {"error", "warning"}, (
        f"INVENTORY uses only {levels} -- if every degradation is the same "
        "severity then the classification has stopped saying anything"
    )
