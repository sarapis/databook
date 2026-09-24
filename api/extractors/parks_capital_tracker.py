"""NYC Parks Capital Project Tracker — the richest schedule data the City publishes.

⚠⚠ WHY PARKS IS WORTH A BESPOKE PATH. The Operations Dashboard publishes a
phase and a forecast completion date for 5,608 FMS ids. Parks publishes, for
2,244 of its own projects: **percent complete within the current phase**,
projected vs adjusted vs actual dates for design, procurement and construction
separately, the funding source attributed to the Mayor / Council / Borough
President, a project liaison, and a plain-language status update. Nothing else
in the City's capital data comes close, and 1,409 of those projects join CPDB.

⚠⚠ THE SOCRATA MIRROR WAS EMPTY, AND IS NOT ANY MORE — AND THAT REVERSAL IS WHY
BOTH SOURCES ARE WIRED. `4hcv-tc5r` returned **0 rows** when measured on
2026-09-03, every column `non_null = 0`, which is why this file originally read
the Parks JSON alone. Re-measured 2026-09-11: **2,785 rows / 2,271 distinct
TrackerID, every project-level column fully populated** — the same 2,271
projects the JSON feed carries, with **0 ids unique to either side**.

⚠⚠ AND THE JSON FEED IS NOW THE UNREACHABLE ONE, FROM PROD. NYC Parks IP-blocks
the server: measured both ways the same minute, `nycgovparks.org` answers **405
from prod** and **200 from a laptop**, user-agent independent. That absence took
`/get/capital/project/{id}` to 500 for **all 17,024 projects** on 2026-09-11
until `_select_optional` was added. So neither source can be relied on alone:
the JSON has been complete-but-blocked and Socrata empty-but-reachable, at
different times. This tries the JSON FIRST (it is the publisher's own, nested
and lossless) and falls back to Socrata, recording which answered in
`feed_source` — so a reader can always tell which shape produced a row.

⚠⚠ THE SOCRATA COPY IS FLAT, AND INGESTING IT RAW WOULD BE THE #262/#278 DEFECT.
It publishes one row per (project x location) — 2,785 rows for 2,271 projects —
and REPEATS the project's money on every one. Tracker `5072` is 27 rows all
reading `$4,806,000`. Raw, that shows one project 27 times in a panel that
serves a LIST, and makes any future `SUM(TotalFunding)` 27x too high. So the CSV
is re-normalised back to the feed's shape before anything downstream sees it.
⚠ Safe because it was measured: of 155 multi-row projects, **0** disagree on any
project-level column across their own rows.

⚠⚠ AND SOCRATA FABRICATES A DAY THAT THE PUBLISHER NEVER ASSERTS. Every schedule
date in the JSON feed is month precision (`08/2022`); Socrata renders it
`08/01/2022 12:00:00 AM`. Measured across all eight schedule columns: the feed is
**100% `MM/YYYY`** and Socrata supplies day `01` on **1,689 of 1,689**, with the
empty counts matching exactly either side. Left alone, `_label_dates` would
render "1 Aug 2022" where Parks said "August 2022" — precision we would be
inventing. They are demoted back to `MM/YYYY`; `LastUpdated` is genuinely
`MM/DD/YYYY` in the feed and only loses its appended midnight.

⚠⚠ AND THE MIRROR IS NOT A COMPLETE SUBSTITUTE — THREE COLUMNS ARE ABSENT FROM
IT. The Socrata export carries 29 columns and simply does not publish
`ContractID` (2,122 populated in the feed), `ProjectUpdate` (1,785) or
`VitalParksUnder400K` (2,271). `ProjectUpdate` is the plain-language status note
this docstring calls out as part of why Parks is worth a bespoke path, so this
is a real loss, not a formatting one. **None of the three is read by `_parks`**,
so the rendered panel is unaffected — but a row sourced from Socrata has them
empty, and `feed_source` is how you tell. When Parks unblocks the server the
JSON path resumes and they populate again.
⚠ Six values also differ by ENCODING — Socrata mojibakes the cedilla, so
`façade` arrives as `faÇade` on 4 summaries and 2 titles. Recorded rather than
"fixed": re-encoding a publisher's text on the way in is a translation layer,
and the spine is where names are normalised.
⚠ Funding and borough totals differ slightly between the two sources (3,441 vs
3,435 funders; 2,300 vs 2,334 boroughs). Those are the publishers disagreeing,
not a parse failure — the split round-trips on 2,268 of 2,271 projects.

⚠ THE FEED IS JSON, WHICH THE SCHEDULER'S CSV PATH CANNOT INGEST. Rather than
inventing a mechanism, this follows the precedent `contracts` already set: a
per-table import function branched from `process_extractor_dataset`, so the feed
lands on the SAME daily extractor schedule as everything else with no new
moving parts. ⚠ The extractor→S3→scheduler route the Checkbook extractors use is
not available: prod has had no AWS credentials since the data lake moved to
local disk.

⚠⚠ THE NESTED FIELDS ARE WRAPPED, AND ITERATING THE WRAPPER LOOKS LIKE SUCCESS.
They are not bare lists: the feed publishes

    "FundingSources": {"FundingSource": ["City Council"]}
    "Locations":      {"Location": [{"name": ..., "ParkID": ..., "Latitude": ...}]}
    "Boroughs":       {"Borough": ["Queens"]}

Iterating the dict directly yields its KEY, so the first draft here wrote the
literal string "FundingSource" once per project — 2,244 rows that looked exactly
like a working load — and produced 0 locations, because the key is not a dict.
Unwrap by name, and check the counts against something other than the project
count.

⚠ They are flattened into their own tables rather than joined into one row. A
project with five sites and three funders is not five rows of project.
"""
import csv
import io
import json
import re

import aiohttp

FEED_URL = "https://www.nycgovparks.org/bigapps/DPR_CapitalProjectTracker_001.json"

# The Socrata mirror of the same tracker — reachable from prod, where the
# Parks-hosted feed is IP-blocked. See the module docstring.
SOCRATA_ID = "4hcv-tc5r"
SOCRATA_CSV_URL = (
    "https://data.cityofnewyork.us/api/views/"
    f"{SOCRATA_ID}/rows.csv?accessType=DOWNLOAD")

# ⚠ Schedule dates the publisher gives at MONTH precision. Socrata renders each
# as `MM/DD/YYYY 12:00:00 AM` with a day it invents; these are demoted back.
# `LastUpdated` is deliberately NOT here — the feed really does publish a day
# for it, so it only loses the appended midnight.
_MONTH_PRECISION_COLS = (
    "DesignStart", "DesignProjectedCompletion", "DesignAdjustedCompletion",
    "DesignActualCompletion", "ProcurementStart",
    "ProcurementProjectedCompletion", "ProcurementAdjustedCompletion",
    "ProcurementActualCompletion", "ConstructionStart",
    "ConstructionProjectedCompletion", "ConstructionAdjustedCompletion",
    "ConstructionActualCompletion",
)

# ⚠ A CLOSED VOCABULARY, READ OFF THE AUTHORITATIVE FEED — not a guess. Socrata
# joins multiple funders with NO separator (`Borough PresidentMayoral`) and
# sometimes with a comma, so the only safe split is longest-match against the
# terms the publisher actually uses. Verified against the JSON feed: it
# round-trips on **2,268 of 2,271** projects, and the 3 that differ are Socrata
# carrying MORE funders than the feed, not a parse failure.
# ⚠ Anything it cannot parse yields NO rows for that project rather than a
# mangled one — a funding source we invented is worse than one we lack.
_FUNDING_TERMS = ("Borough President", "City Council", "Mayoral",
                  "Federal", "Private", "State")

TABLE = "parkscapitaltracker"
LOCATIONS_TABLE = "parkscapitallocations"
FUNDING_TABLE = "parkscapitalfunding"
BOROUGH_TABLE = "parkscapitalboroughs"

# ⚠ The feed's own field names, kept verbatim. Renaming them here would put a
# translation layer between the publisher and the reader for no gain — the
# spine is where names are normalised.
FIELDS = [
    "TrackerID", "FMSID", "Title", "Summary", "CurrentPhase",
    "DesignPercentComplete", "ProcurementPercentComplete",
    "ConstructionPercentComplete",
    "DesignStart", "DesignProjectedCompletion", "DesignAdjustedCompletion",
    "DesignActualCompletion",
    "ProcurementStart", "ProcurementProjectedCompletion",
    "ProcurementAdjustedCompletion", "ProcurementActualCompletion",
    "ConstructionStart", "ConstructionProjectedCompletion",
    "ConstructionAdjustedCompletion", "ConstructionActualCompletion",
    "TotalFunding", "ProjectLiaison", "LastUpdated", "ContractID",
    "ProjectUpdate", "VitalParksUnder400K",
]

DDL = f"""
CREATE TABLE {{staging}} (
    "TrackerID" text,
    "FMSID" text,
    "Title" text,
    "Summary" text,
    "CurrentPhase" text,
    "DesignPercentComplete" text,
    "ProcurementPercentComplete" text,
    "ConstructionPercentComplete" text,
    "DesignStart" text,
    "DesignProjectedCompletion" text,
    "DesignAdjustedCompletion" text,
    "DesignActualCompletion" text,
    "ProcurementStart" text,
    "ProcurementProjectedCompletion" text,
    "ProcurementAdjustedCompletion" text,
    "ProcurementActualCompletion" text,
    "ConstructionStart" text,
    "ConstructionProjectedCompletion" text,
    "ConstructionAdjustedCompletion" text,
    "ConstructionActualCompletion" text,
    "TotalFunding" text,
    "ProjectLiaison" text,
    "LastUpdated" text,
    "ContractID" text,
    "ProjectUpdate" text,
    "VitalParksUnder400K" text,
    feed_source text,
    feed_as_of text
);
"""

LOCATIONS_DDL = """
CREATE TABLE {staging} (
    "TrackerID" text,
    "FMSID" text,
    name text,
    "ParkID" text,
    latitude text,
    longitude text
);
"""

FUNDING_DDL = """
CREATE TABLE {staging} (
    "TrackerID" text,
    "FMSID" text,
    source text
);
"""

BOROUGH_DDL = """
CREATE TABLE {staging} (
    "TrackerID" text,
    "FMSID" text,
    borough text
);
"""


def _scalar(v):
    """Feed values are scalars, but a few nested fields arrive as lists."""
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v if x is not None) or None
    if isinstance(v, dict):
        return json.dumps(v)
    s = str(v).strip()
    return s or None


def _unwrap(value, inner_key):
    """Return the list inside a `{"<Inner>": [...]}` wrapper.

    ⚠ Tolerates a bare list too, so a future feed that drops the wrapper keeps
    working — but NEVER iterates the dict itself, which yields keys.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        inner = value.get(inner_key)
        if isinstance(inner, list):
            return inner
        if inner is not None:
            return [inner]
    return []


def _records(payload):
    """The feed is a bare list; tolerate a wrapper if Parks ever adds one."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("features", "records", "data", "projects"):
            if isinstance(payload.get(key), list):
                return payload[key]
        for v in payload.values():
            if isinstance(v, list):
                return v
    return []


def _demote_socrata_date(column, value):
    """Socrata's `MM/DD/YYYY 12:00:00 AM` back to the precision Parks published.

    ⚠ The day is FABRICATED on the schedule columns — measured, the feed is
    100% `MM/YYYY` there and Socrata supplies `01` on 1,689 of 1,689. Keeping it
    would let `_label_dates` render "1 Aug 2022" for a month the City never gave
    a day to.
    """
    if not value:
        return value
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})(?:\s+.*)?", value.strip())
    if not m:
        return value
    mm, dd, yyyy = m.groups()
    if column in _MONTH_PRECISION_COLS:
        return f"{mm}/{yyyy}"
    return f"{mm}/{dd}/{yyyy}"


def _split_funding(value):
    """Socrata's run-together funders, split on the publisher's own vocabulary.

    ⚠ RETURNS [] RATHER THAN GUESSING. `Borough PresidentMayoral` has no
    separator, so the only honest split is longest-match against terms the feed
    actually uses; anything left over means the vocabulary has moved and the
    right answer is no rows, not a mangled one.
    """
    rest = (value or "").strip()
    out = []
    terms = sorted(_FUNDING_TERMS, key=len, reverse=True)
    while rest:
        rest = rest.lstrip(", ").strip()
        if not rest:
            break
        for term in terms:
            if rest.startswith(term):
                out.append(term)
                rest = rest[len(term):]
                break
        else:
            return []
    return out


def _records_from_socrata_csv(text):
    """The flat Socrata export, re-normalised into the JSON feed's record shape.

    ⚠ One row per (project x location) becomes ONE record with nested
    `Locations` / `FundingSources` / `Boroughs`, so everything downstream — the
    swap, the refusals, the four tables — is byte-for-byte the same code path
    the JSON feed takes. Ingesting the flat form instead would put 27 identical
    rows on one project and repeat its money on every one.
    """
    rows = list(csv.DictReader(io.StringIO(text)))
    by_id = {}
    order = []
    for row in rows:
        tid = (row.get("TrackerID") or "").strip()
        if not tid:
            continue
        rec = by_id.get(tid)
        if rec is None:
            rec = {f: _demote_socrata_date(f, (row.get(f) or "").strip())
                   for f in FIELDS}
            rec["Locations"] = {"Location": []}
            rec["FundingSources"] = {
                "FundingSource": _split_funding(row.get("FundingSource"))}
            rec["Boroughs"] = {"Borough": [
                b.strip() for b in (row.get("Borough") or "").split(",")
                if b.strip()]}
            by_id[tid] = rec
            order.append(tid)
        # ⚠ Every CSV row of a project carries that project's own location. The
        # project-level columns repeat and are deliberately read from the FIRST
        # row only — measured: of 155 multi-row projects, 0 disagree on any of
        # them, so taking the first is not a choice between conflicting values.
        name = (row.get("name") or "").strip()
        park = (row.get("ParkID") or "").strip()
        if name or park:
            rec["Locations"]["Location"].append({
                "name": name or None,
                "ParkID": park or None,
                "Latitude": (row.get("Latitude") or "").strip() or None,
                "Longitude": (row.get("Longitude") or "").strip() or None,
            })
    return [by_id[t] for t in order]


async def fetch(session: aiohttp.ClientSession):
    """Fetch the tracker. Returns (records, source_label).

    ⚠⚠ TWO SOURCES, AND NEITHER HAS BEEN RELIABLE ALONE. The Parks JSON is the
    publisher's own and lossless, so it is tried first; Socrata is the fallback
    because it is the one prod can actually reach. Each has been the broken one
    at a different time — see the module docstring — and `feed_source` records
    which answered so a row's shape is never a mystery.

    ⚠ A source that answers with ZERO records is treated as a failure and the
    other is tried, because that is exactly how Socrata behaved on 2026-09-03
    while advertising a same-day refresh.
    """
    timeout = aiohttp.ClientTimeout(total=300, sock_read=120)
    errors = []

    try:
        async with session.get(FEED_URL, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"parks feed HTTP {resp.status}")
            # ⚠ The feed serves text/plain, so `resp.json()` refuses it on
            # content type. Read and parse explicitly rather than passing
            # content_type=None, which would also swallow an HTML error page as
            # if it were data.
            body = await resp.text()
        records = _records(json.loads(body))
        if records:
            return records, "parks_json"
        errors.append("parks_json returned 0 records")
    except Exception as exc:  # noqa: BLE001 - reported below, not swallowed
        errors.append(f"parks_json {type(exc).__name__}: {exc}")

    try:
        async with session.get(SOCRATA_CSV_URL, timeout=timeout) as resp:
            if resp.status != 200:
                raise RuntimeError(f"socrata HTTP {resp.status}")
            body = await resp.text()
        records = _records_from_socrata_csv(body)
        if records:
            return records, "parks_socrata"
        errors.append("parks_socrata returned 0 records")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"parks_socrata {type(exc).__name__}: {exc}")

    raise RuntimeError("; ".join(errors))


async def import_parks_tracker(conn, session: aiohttp.ClientSession) -> dict:
    """Replace the Parks tables from the live feed.

    ⚠ REFUSES ON ZERO RECORDS. The Socrata mirror of this very feed served 0
    rows while advertising a same-day refresh; a loader that accepts that
    silently replaces 2,244 real projects with nothing and reports success.
    """
    try:
        records, source = await fetch(session)
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        return {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}

    if not records:
        return {"status": "fail",
                "error": "feed returned 0 records — refusing to replace the table"}

    as_of = max((_scalar(r.get("LastUpdated")) or "" for r in records), default="")

    rows, locs, funds, boros = [], [], [], []
    for r in records:
        tid = _scalar(r.get("TrackerID"))
        fid = _scalar(r.get("FMSID"))
        rows.append(tuple([_scalar(r.get(f)) for f in FIELDS] + [source, as_of]))
        for loc in _unwrap(r.get("Locations"), "Location"):
            if isinstance(loc, dict):
                locs.append((tid, fid, _scalar(loc.get("name")),
                             _scalar(loc.get("ParkID")),
                             _scalar(loc.get("Latitude")),
                             _scalar(loc.get("Longitude"))))
        for fs in _unwrap(r.get("FundingSources"), "FundingSource"):
            val = _scalar(fs)
            if val:
                funds.append((tid, fid, val))
        for bo in _unwrap(r.get("Boroughs"), "Borough"):
            val = _scalar(bo)
            if val:
                boros.append((tid, fid, val))

    live = 0
    if await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", f"public.{TABLE}"):
        live = await conn.fetchval(f'SELECT count(*) FROM "{TABLE}"')
    if live > 0 and len(rows) < live * 0.5:
        return {"status": "fail",
                "error": f"refusing swap: {len(rows)} rows vs {live} live (>50% drop)"}

    async with conn.transaction():
        for table, ddl, data, cols in (
            (TABLE, DDL, rows, [f'"{f}"' for f in FIELDS] + ["feed_source", "feed_as_of"]),
            (LOCATIONS_TABLE, LOCATIONS_DDL, locs,
             ['"TrackerID"', '"FMSID"', "name", '"ParkID"', "latitude", "longitude"]),
            (FUNDING_TABLE, FUNDING_DDL, funds,
             ['"TrackerID"', '"FMSID"', "source"]),
            (BOROUGH_TABLE, BOROUGH_DDL, boros,
             ['"TrackerID"', '"FMSID"', "borough"]),
        ):
            staging = f"_staging_{table}"
            await conn.execute(f'DROP TABLE IF EXISTS "{staging}"')
            await conn.execute(ddl.format(staging=f'"{staging}"'))
            if data:
                await conn.copy_records_to_table(
                    staging, records=data,
                    columns=[c.strip('"') for c in cols])
            await conn.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE')
            await conn.execute(f'ALTER TABLE "{staging}" RENAME TO "{table}"')

        await conn.execute(
            f'CREATE INDEX IF NOT EXISTS idx_parks_tracker_fms ON "{TABLE}" ("FMSID")')

    return {"status": "success", "rows": len(rows),
            "locations": len(locs), "funding": len(funds),
            "boroughs": len(boros),
            "source": source, "as_of": as_of}
