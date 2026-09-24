"""Vendor name -> PASSPort supplier id, for profile links. ONE owner.

⚠⚠ WHY THIS EXISTS — A JOIN THAT DUPLICATED CONTRACTS. Every digital-reform
query resolved the supplier id with

    LEFT JOIN vendors v ON LOWER(c.vendor_name) = LOWER(v."Vendor Name")

and **48 vendor names hold more than one row in `vendors`** (measured
2026-08-12), so a matching contract came back TWICE. On the Renewal Queue it
inflated exactly one row — `CT1-017-20248805602`, Absorb Software's LMS, whose
name resolves to supplier ids 1871820 and 2073456 — which is why the queue
reported **243** expiring licences where the Licenses page reported **242**.
A one-row error, but the two pages disagreeing about the same set is the defect,
not the size of it.

⚠ The Licenses page never had it, because it never joined: it built this map in
Python and accepted a name ONLY where the name resolves to exactly one supplier
id. That rule is the whole point and it is the same one the DOS crosswalk uses
(`confidence='ambiguous'` -> NULL, never a guess): linking an ambiguous name
sends a reader to an arbitrary one of two companies, which is worse than leaving
the name unlinked.

⚠ A map cannot duplicate a row. That is the structural reason to prefer it over
a `HAVING`-filtered join here — the failure mode is "no link", never "two rows".
"""
import time

from modules.errfmt import exc_str

# ⚠ `HAVING count(DISTINCT ...) = 1` IS THE GUARD, not an optimisation. Dropping
# it (or replacing it with `min(...)` alone) makes the map start guessing between
# two companies. A test pins this clause.
#
# ⚠ PUBLIC, because not every caller has a PostgresModelAsync. The daily briefing
# runs all of its queries on one dedicated connection, so it fetches with SQL +
# from_rows() instead of unique_map(). Exposing the query beats letting a second
# caller write its own: two spellings of `lower(trim(...))` is how the folding
# drifts and the map silently resolves nothing.
SQL = """
    SELECT lower(trim("Vendor Name")) AS nm,
           min("PASSPort Supplier-ID") AS vendor_id
    FROM vendors
    WHERE coalesce(trim("Vendor Name"), '') <> ''
    GROUP BY lower(trim("Vendor Name"))
    HAVING count(DISTINCT "PASSPort Supplier-ID") = 1
"""


def key(vendor_name) -> str:
    """The map's key for a contracts.vendor_name. Folded identically on both
    sides — a different folding here would silently resolve nothing."""
    return (vendor_name or "").strip().lower()


def from_rows(rows) -> dict:
    """Build the map from rows already fetched with SQL, for a caller that owns its
    own connection. The keying lives here so it cannot differ between callers."""
    return {r["nm"]: r["vendor_id"] for r in (rows or [])}


# ⚠⚠ CACHED, AND THIS WAS THE SINGLE LARGEST COST IN /digital-reform/all.
# Profiled on prod 2026-09-01 by wrapping the REAL select_safe (never by
# replicating the SQL — a harness that rebuilds a query measures a different
# system). Of a 2.221s cold request, the top THREE queries were all THIS one:
# 778 + 767 + 577 = 2.12s, because `_vendors`, `_contracts` and `_expiring` each
# built the map independently. Nothing else was close — _stats 223ms,
# _charts:agencies 212ms, _award_by_start_year 251ms.
#
# ⭐ AND IT SAT ON THE WRONG SIDE OF THE OTHER CACHE. Those three are the
# PARAM-DEPENDENT blocks, so this ran on every miss of the full-param cache —
# i.e. on every novel crawler URL, not merely at cold start. Within each block it
# is SERIAL (`own queries -> await unique_map`), so it was ~60-75% of that path's
# wall time. The blocks that WERE proposed for optimisation (stats, charts) live
# in `_dr_shared_cache` and run about twice a day.
#
# ⚠⚠ DEDUPLICATING THE THREE CALLS WOULD NOT HAVE FIXED IT, and that is why this
# is a cache rather than a hoist to one call before the gather. The three blocks
# are `asyncio.gather`ed, so the calls ALREADY overlap. Measured on prod:
#     one call, uncontended      573-649 ms   (map size 36,563)
#     three concurrent, as-was   754-793 ms wall
# so computing it once saves only ~181ms of WALL. It does remove ~1.65s of
# Postgres work per request, which is worth having — but the ~750ms comes off the
# critical path only by not running the query at all.
#
# ⚠ TTL *AND* the post-ingest hook, deliberately, not either alone. `vendors`
# ingests daily and `invalidate()` is registered on that ingest — but the
# "daily" extractor ingest is measured to run ~16 days in 21 (a `.days < 1`
# guard; see the scheduler task), so the hook is NOT a dependable sole
# invalidator. The TTL bounds staleness to an hour even if the hook never fires.
_CACHE_TTL = 3600  # seconds

_cache = None      # the map, or None when empty. ⚠ SHARED INSTANCE — see below.
_cache_ts = 0.0


def invalidate() -> None:
    """Drop the cached map, so the next caller rebuilds it.

    Registered as a `vendors` post-ingest hook: that table is DROP+RENAMEd on
    every ingest, so the moment it changes is exactly when this map is stale.
    """
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0.0


async def unique_map(pg, logger=None) -> dict:
    """{lower(trim(name)): supplier_id} for names resolving to EXACTLY ONE id.

    `pg` is PostgresModelAsync, passed in so this module stays importable without
    the DB stack (the same reason digitalscope takes it as an argument).

    ⚠ Degrades to `{}` rather than raising: an unresolvable supplier id must cost
    a hyperlink, never a page.

    ⚠⚠ THE RETURNED DICT IS THE CACHED INSTANCE, NOT A COPY. Callers read it
    (`vendor_ids.get(key(name))`) and must never mutate it, or they corrupt every
    later caller's map. Copying 36,563 entries on each of three calls per request
    would give back a slice of what the cache just saved, so the sharing is
    deliberate and a guard pins that no call site writes to it.
    """
    global _cache, _cache_ts
    if _cache is not None and (time.time() - _cache_ts) < _CACHE_TTL:
        return _cache
    try:
        fresh = from_rows(await pg.select_safe(SQL))
    except Exception as exc:  # noqa: BLE001
        if logger:
            logger.warning("vendor id lookup failed: %s", exc_str(exc))
        # ⚠⚠ A FAILURE IS NEVER CACHED. Caching `{}` here would turn one blip
        # into an hour with no vendor hyperlink anywhere on the site, and it
        # would look exactly like "no name resolves" — the empty-result-reads-as-
        # data failure this repo keeps paying for. Leave the cache alone so the
        # next caller retries.
        return {}
    _cache = fresh
    _cache_ts = time.time()
    return _cache
