"""Single resolver for "this table's PUBLISHER ships byte-exact duplicate rows".

A registry table should hold one row per thing. `schoollocations` does not: the
City publishes `wg9x-4ke6` with **2,190 rows for 2,131 schools** -- 59 rows
repeated exactly twice, identical across all 41 columns. Measured 2026-09-21
against the Socrata CSV itself, so this is the publisher's data and not
something our ingest introduced (the CSV downloads 2,190 data rows with 2,131
distinct whole rows, matching the table row for row).

⚠ The damage is not cosmetic. Every read fans the duplicate out:

  * `SELECT count(*)` reports 2,190 schools citywide, and 21 of the 32
    geographical districts over-count their own schools tile.
  * Every JOIN on `location_code` DOUBLES the joined rows for those 59
    buildings, so enrolment, project counts, project budgets and actual
    spending all inflate. District 18 read **17,803 students against a real
    17,051** -- 752 students that do not exist, +4.4%.

Why this is fixed at the READ and not at the ingest:

  * `schoollocations` arrives through the normalizer -> `/import-csv`, and that
    path runs post-ingest hooks for **`crol` only** (`main.py`, `if table_name
    == 'crol'`). A dedupe hook registered here would be the repo's documented
    "REGISTERED IS NOT RUNNING" defect -- present, correct, and never executed.
  * Even a hook that did fire would not fix production until the next ingest,
    and this table last ingested 2026-03-10. A read-side fix is correct the
    moment it deploys, in every environment, including a fresh one.
  * The stored table stays faithful to what the City published, which is what
    makes the duplication reportable to the publisher rather than quietly
    absorbed.

⚠ The rule is `SELECT DISTINCT *`, which removes ONLY byte-exact duplicate
rows. That is lossless by construction: a row it drops is indistinguishable
from one it keeps. It is deliberately NOT `DISTINCT ON (location_code)`, which
would guarantee one row per key and would silently DROP a real school the day
two different schools share a building code -- failing in the direction that
loses data rather than the direction that is visible.

⚠ And it is an ALLOWLIST, never a default. On a fact table two identical rows
can be two real events (two identical payments on one day), so deduping them
would destroy money. A table earns a place here only once its duplicates have
been measured and shown to be a publishing artefact.
"""
# ⚠⚠ THE API IMAGE IS `python:3.9-slim`, AND `str | None` IN A SIGNATURE IS
# EVALUATED AT DEF TIME — so without this line the module raises
# `TypeError: unsupported operand type(s) for |` and the api does not boot.
# It is invisible to the unit suite, which runs on the developer's own Python;
# only the Integration Smoke, which boots the real image, can see it. Every
# other PEP 604 user under api/ carries this same line.
from __future__ import annotations

# table name -> why it is here, with the measurement that put it there.
EXACT_DUPLICATE_SOURCES = {
    "schoollocations": (
        "NYC Open Data wg9x-4ke6 publishes 2,190 rows for 2,131 schools; the "
        "59 extras are byte-exact repeats across all 41 columns. Measured "
        "2026-09-21 against the source CSV and against prod."
    ),
}


def is_duplicated(table: str) -> bool:
    """True when this table's source is known to repeat whole rows."""
    return table in EXACT_DUPLICATE_SOURCES


def relation(table: str, alias: str | None = None) -> str:
    """The FROM/JOIN relation to read `table` through.

    For every table NOT in the allowlist this returns the caller's own text
    unchanged, so routing a generic endpoint through it cannot alter any other
    table's SQL. That property is what makes it safe to put in front of
    `/get/districts/{type}/{id}/{tbl}`, which serves ~40 tables.

    ⚠ A subquery in FROM must carry an alias, so the deduped form always emits
    one. Pass `alias` wherever the caller already names the relation.
    """
    if table not in EXACT_DUPLICATE_SOURCES:
        return table if alias is None else f"{table} {alias}"
    return f"(SELECT DISTINCT * FROM {table}) {alias or table}"
