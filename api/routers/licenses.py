"""Software-licence analysis over AI-classified digital contracts.

Powers the (unlisted) Licenses page. Everything here reads
`digital_contract_enrichment` (populated by classify_digital_contracts.py) joined
to `contracts`, grouped by `license_family` (built by build_license_families.py).

⚠⚠ THREE MEASUREMENT TRAPS, each already paid for once:

1. `contracts` HOLDS MULTIPLE ROWS PER contract_id. A naive join returned 1,109
   rows for 950 licence contracts, inflating value ~6% and the expiring count
   ~18%. Every query here goes through the `_CONTRACTS` CTE, which is
   DISTINCT ON (contract_id). Do not join `contracts` directly.

2. `license_product` IS FREE TEXT AND FRAGMENTS. 525 distinct strings for 948
   contracts. Grouping is the `license_family` table, never the raw column.
   If that table is missing this module DEGRADES to the raw product rather than
   failing -- the page still renders, it is just ungrouped.

3. GENERIC VALUES ARE NOT PRODUCTS. `Various`, `Unknown`, `EHR System` etc. are
   flagged is_generic and must never be ranked as if they were software. They
   are reported as a single "(unidentified)" line so the reader can see how much
   is unclassified rather than having it silently blended in.

⚠ Everything here is AI-derived: is_license agreed only 92% between two models
on a 40-contract sample, and no row is human-curated. The page carries the
Analysis banner for this reason. Do not present these numbers as an inventory.
"""
import csv
import io
import asyncio
import logging
import os
import time

from fastapi import APIRouter, Query, Response
from postgrex import PostgresModelAsync

from modules import contractterm
from modules import licenseclass
from modules import licensewindow
# ⚠ ONE pipeline query for the section — see the module. The aggregate belongs to
# the Overview now; these rows are loaded only for the family-level title match.
from modules import pipelinevehicles
# ⚠ ONE owner for the "Bought through" merge (contract vendors + notice
# awarded-to, skeleton-deduped). The counts-vs-cap and no-suffix-stripping rules
# live there; do not reimplement the merge here.
from modules import resellers
from modules import agencyalias
from modules import vendorids
from modules.duckpool import to_duckdb_thread
from modules.errfmt import exc_str
# ⚠ IMPORTED, NOT REIMPLEMENTED. `_fy_of` is the site's one definition of the NYC
# fiscal year and `_persistent_spending_connection` / `get_spending_files` are how
# every other reader reaches the Checkbook lake. A second copy of any of the three
# would measure a different system and publish its answer as this one's — the
# suffix-list defect, in production code rather than in a harness.
from routers.oce import (COMPETITIVE_PROCUREMENT_METHODS, NONCOMPETITIVE_REVIEW_METHODS, _fy_of,
                         _persistent_spending_connection, get_spending_files)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/oce/licenses",
    tags=["Procurement (OCE)"],
    responses={404: {"description": "Not found"}},
)

_CACHE = {}
_CACHE_TTL = 60 * 60 * 6  # 6h; the underlying classification changes rarely.

# ⚠ One row per contract. See trap 1 in the module docstring.
_CONTRACTS = """
    SELECT DISTINCT ON (contract_id)
           contract_id, normalized_contract_id, epin, contract_title, agency,
           vendor_name, award_amount, current_amount, start_date, end_date,
           procurement_method, contract_type
    FROM contracts
    WHERE contract_id IS NOT NULL
    ORDER BY contract_id, coalesce(current_amount,0) DESC, coalesce(award_amount,0) DESC
"""

# Products whose family is a legacy/mainframe platform. Editorial, and kept here
# rather than in the curated CSV because it is a claim about the TECHNOLOGY ERA,
# not about which strings name the same product.
_LEGACY_FAMILIES = {
    "Broadcom (CA)", "LRS", "Information Builders (WebFOCUS)", "Rocket Software",
    "Attachmate", "PageCenter", "Micro Focus", "IBM",
}

# ⚠ `other` is NOT a vocabulary tag -- it is the classifier's ABSTENTION SENTINEL
# (classify_license_purchases.py builds its enum as `caps + ["other"]`). It has no
# catalogue category, so it cannot live in license_capability_vocab.csv, whose
# guard requires every row to map to a real catalogue category. Naming it once
# here keeps the string out of two templates and one rollup.
_OTHER_CAPABILITY = "other"
_OTHER_CAPABILITY_LABEL = "Function not identified"

# ⚠⚠ FAMILY-level consolidation thresholds — NOT the capability ones below. A family
# bought by this many agencies on this many separate contracts is a candidate for a
# single citywide agreement. Named because the page renders the rule (a threshold a
# reader cannot see is indistinguishable from an opinion) and because the per-row flag
# and the count must come from the same numbers: they used to be one inline expression
# feeding a separate table, and the table has now merged into the family table.
_FAMILY_FRAG_MIN_AGENCIES = 3
_FAMILY_FRAG_MIN_CONTRACTS = 3

# When a function is flagged as worth consolidating. ⚠ Both factors are required:
# office-productivity spans 18 agencies on 2 products, which is a citywide
# agreement working as intended, while network-security spans 18 agencies on 32
# products, which is the actual finding.
#
# ⚠ AND THE BADGE IS CAPPED. With only the product/agency floors, 26 of 46
# functions carried the flag -- more than half the table, which is not a signal, it
# is wallpaper. The value floor and the top-N cap exist so the badge keeps meaning
# "look at this one"; the page states the rule where the badge appears, because a
# threshold a reader cannot see is indistinguishable from an opinion.
_FRAG_MIN_PRODUCTS = 5
_FRAG_MIN_AGENCIES = 3
_FRAG_MIN_VALUE = 500_000
_FRAG_MAX_BADGED = 10

# Pipeline vehicles below this are noise on a page about $1.37B; the count and
# combined ceiling are still reported over the FULL set, so the cap is disclosed
# rather than hidden.
_PIPELINE_DISPLAY_FLOOR = 1_000_000

_CAP_LABELS = None


def _seed_path(name):
    """api/seed/<name>, from api/routers/licenses.py."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "seed", name)


def _capability_labels():
    """capability tag -> display label, read from the vocabulary seed.

    ⚠⚠ THE LABEL BELONGS WITH THE VOCABULARY, NOT IN A TEMPLATE MAP. Two Blade
    templates each carried their own partial copy of this mapping and both had
    fallen behind the seed: 18 of the 46 tags in use rendered as raw kebab-case
    keys (`project-tracking`, `hr-workforce`, `statistics-analysis`) beside
    properly labelled ones, on a published page. Labelling a new tag required
    editing two views nobody thought to open, so it never happened.

    ⚠ Degrades to the raw key rather than raising. A missing or malformed seed
    must leave the function view populated-but-plainly-labelled, never empty --
    the #146 shape, where a serving query silently returns nothing.
    """
    global _CAP_LABELS
    if _CAP_LABELS is not None:
        return _CAP_LABELS
    labels = {_OTHER_CAPABILITY: _OTHER_CAPABILITY_LABEL}
    try:
        path = _seed_path("license_capability_vocab.csv")
        with open(path, newline="", encoding="utf-8") as fh:
            lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
        for r in csv.DictReader(lines):
            cap = (r.get("capability") or "").strip()
            lab = (r.get("label") or "").strip()
            if cap and lab:
                labels[cap] = lab
    except Exception as exc:  # noqa: BLE001
        logger.warning("capability labels unavailable: %s", exc_str(exc))
    _CAP_LABELS = labels
    return labels


# ⚠⚠ THE MEMBERSHIP OF THE DATA LENS LIVES IN THE SEED, NOT HERE. The
# tempting derivation — catalogue_category == 'data-analytics' — drops
# `geospatial-gis`, the LARGEST member ($38.5M vs BI's $21.0M on prod
# 2026-09-14), because its catalogue home is `geospatial`. A rule that silently
# omits the biggest row is the "regex doing a semantic job" defect; the seed
# states membership and this reads it. A guard proves the router has no tuple
# of its own.
_DATA_LENS = "analyse"
_DATA_LENS_CAPS = None


def _data_lens_caps():
    """The capability tags that make up the "tools for working with data" lens.

    ⚠ Degrades to the EMPTY set rather than a hardcoded fallback. An empty lens
    renders a page that plainly has no tool rows, which is visibly broken; a
    silent fallback list would render a page that looks right and disagrees with
    the seed — the harder failure to notice, and the one this repo keeps finding.
    """
    global _DATA_LENS_CAPS
    if _DATA_LENS_CAPS is not None:
        return _DATA_LENS_CAPS
    caps = set()
    try:
        with open(_seed_path("license_capability_vocab.csv"), newline="",
                  encoding="utf-8") as fh:
            lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
        for r in csv.DictReader(lines):
            if (r.get("data_lens") or "").strip() == _DATA_LENS:
                cap = (r.get("capability") or "").strip()
                if cap:
                    caps.add(cap)
    except Exception as exc:  # noqa: BLE001
        logger.warning("data lens vocabulary unavailable: %s", exc_str(exc))
    _DATA_LENS_CAPS = caps
    return caps


# How many notices the family page lists. Matches oce._notices_for_epins, so the
# two notice panels on this site cap and link identically.
_NOTICE_CAP = 25


async def _notices_for_family(name: str) -> tuple:
    """City Record notices whose BODY names this product, from the offline
    crosswalk. Returns (rows, total).

    ⚠ NOT evidence of procurement activity, and the page must not imply it is. A
    notice naming a product may be a hearing agenda. The accurate id-based link
    is oce._notices_for_epins, which joins on the EPIN and is a different panel.

    ⚠ Read from `notice_product_links`, never matched live. Ranking a live body
    match makes the query O(matches) — measured, "construction" goes 150ms/7,893
    rows to 831ms/15,321 — and this page has no ranking need at all.

    Guarded: the table is absent until build_notice_product_links.py has run, and
    a family page must render perfectly well without the panel.
    """
    if not name:
        return [], 0
    try:
        rows = await PostgresModelAsync.select_safe(
            """
            SELECT request_id, title, agency, notice_type, start_date,
                   vendor, amount, pin, ctr_id,
                   count(*) OVER () AS total
            FROM notice_product_links
            WHERE family = $1
            ORDER BY amount DESC NULLS LAST, start_date DESC NULLS LAST, request_id
            LIMIT $2
            """,
            [name, _NOTICE_CAP],
        )
    except Exception as exc:  # noqa: BLE001
        # WARNING, not ERROR: an absent table is the legitimate state before the
        # first batch run, exactly as routers/search.py reasons about
        # UndefinedTableError. A malformed query here would be a code defect, but
        # this statement is static.
        logger.warning("[licenses] notice links unavailable: %s", exc_str(exc))
        return [], 0
    total = int(rows[0]["total"]) if rows else 0
    # ⚠ `vendor`/`amount` are SPARSE — only award-type notices carry them (531 of
    # 3,782 links when this shipped), so the view must render a blank cell rather
    # than imply zero. `amount` is already NULL for a blank or 0 source value; a
    # rendered "$0.00" would be a claim the data does not make.
    #
    # ⚠⚠ AMOUNT-BEARING NOTICES COME FIRST, AND THE CAP IS WHY. Ordered by date
    # alone, the informative rows fell off the end of a 25-row panel: Microsoft's
    # $67.5M ELA (Dell Marketing) sat at position **1,184 of 1,220**, and the
    # $57.0M citywide master at 396 — so the panel showed recent small notices
    # and hid every large award. Adding the column is what made that visible.
    #
    # Measured before choosing this ordering, because it is a trade: of the 430
    # families with links, **181 carry no amount at all** (so nothing changes for
    # them — every value is NULL and it falls through to date), **248 carry
    # between 1 and 25** (so ALL their awards fit inside the cap and recency
    # still fills the remaining slots), and exactly **ONE** — Microsoft, with 53 —
    # has more amounts than the cap and therefore loses recency. One family in
    # 430, and it is the family where the amounts are the point.
    #
    # ⚠ The page's cap sentence must describe THIS order. It said "the 25 most
    # recent of 1,220", which this ordering would make false.
    return [{
        "title": r.get("title") or "Notice",
        "type": r.get("notice_type") or "",
        "agency": r.get("agency") or "",
        "date": str(r.get("start_date") or "")[:10],
        "url": f"https://a856-cityrecord.nyc.gov/RequestDetail/{r['request_id']}",
        "vendor": r.get("vendor") or "",
        "amount": float(r["amount"]) if r.get("amount") is not None else None,
        "pin": r.get("pin") or "",
        # The resolved procurement record, when the notice's PIN matches a
        # registered contract. Lets a reader go product -> notice -> contract.
        "ctr_id": str(r.get("ctr_id")) if r.get("ctr_id") else "",
    } for r in rows], total


async def _notice_resellers() -> tuple:
    """Awarded-to vendors from City Record notices naming each product, grouped
    per family — the notice half of the family table's "Bought through" column.

    Returns (by_family, meta). `by_family` maps family -> vendor rows ranked by
    award amount (largest first, NULLs last) then notice count, matching the
    family page's own notice-panel ordering (#288). `meta` reports availability
    and the measured coverage, so the page can STATE its sources from served
    figures instead of hardcoding "531 notices" — the typed-figure defect.

    ⚠ WARNING, not ERROR, on failure: the table is legitimately absent until
    build_notice_product_links.py has first run (the same triage as
    _notices_for_family above). The column then serves contract vendors only,
    and meta["available"] is False so the VIEW can stop claiming notice
    coverage it does not have — a note describing a source that silently
    dropped out would be the stale-disclosure defect.
    """
    try:
        rows = await PostgresModelAsync.select_safe(
            """
            SELECT family, vendor, count(*) AS notices, max(amount) AS max_amount
            FROM notice_product_links
            WHERE vendor IS NOT NULL AND vendor <> ''
            GROUP BY family, vendor
            """)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[licenses] notice resellers unavailable: %s", exc_str(exc))
        return {}, {"available": False, "families": 0, "links": 0}
    by_fam = {}
    links = 0
    for r in rows or []:
        links += int(r["notices"] or 0)
        by_fam.setdefault(r["family"], []).append({
            "vendor": r["vendor"],
            "notices": int(r["notices"] or 0),
            "max_amount": float(r["max_amount"]) if r.get("max_amount") is not None else None,
        })
    for lst in by_fam.values():
        lst.sort(key=lambda v: (-(v["max_amount"] or 0), -v["notices"], v["vendor"]))
    return by_fam, {"available": True, "families": len(by_fam), "links": links}


async def _table_exists(name: str) -> bool:
    """Probe once per call. Same pattern as oce.py's enrichment guard: a missing
    derived table must degrade the page, never 500 it."""
    try:
        r = await PostgresModelAsync.select_safe(
            "SELECT to_regclass($1) AS t", [f"public.{name}"])
        return bool(r and r[0].get("t"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("license table probe failed: %s", exc_str(exc))
        return False


def _term_years(start, end):
    """Contract length in years, or None. ⚠ DELEGATES to modules/contractterm,
    which is the one owner now that the call-center lens needs the same rule.
    Kept as a thin alias so every call site in this file reads unchanged."""
    return contractterm.years(start, end)


def _is_expiring(end_date, today) -> bool:
    """Expiring == ends in the future but before the shared horizon.

    ⚠ The definition itself lives in modules/licensewindow.py, because the Renewal
    Queue expresses the same window in SQL. It used to be typed out here AND there
    — matching by coincidence, with nothing to keep them matching.
    """
    return licensewindow.is_expiring(end_date, today)


async def _load():
    """One pass over the joined set; every analysis is computed from it in
    Python. Cheaper and far easier to keep consistent than nine GROUP BYs that
    can drift apart on their filters."""
    have_family = await _table_exists("license_family")
    have_enr = await _table_exists("digital_contract_enrichment")
    if not have_enr:
        return {"available": False, "reason": "digital_contract_enrichment is missing"}

    fam_join = ("LEFT JOIN license_family lf ON lf.product_raw = e.license_product"
                if have_family else "")
    fam_sel = ("coalesce(lf.family, e.license_product) AS family, "
               "coalesce(lf.is_generic, false) AS is_generic, "
               "coalesce(lf.curated, false) AS fam_curated, "
               "coalesce(lf.slug, '') AS slug"
               if have_family else
               "e.license_product AS family, false AS is_generic, "
               "false AS fam_curated, '' AS slug")

    rows = await PostgresModelAsync.select_safe(f"""
        WITH c AS ({_CONTRACTS})
        SELECT c.contract_id, c.normalized_contract_id, c.epin, c.contract_title,
               c.agency, c.vendor_name,
               c.award_amount, c.current_amount, c.start_date, c.end_date,
               c.procurement_method, c.contract_type,
               e.license_product AS product, e.license_purpose AS purpose,
               e.build_vs_buy, e.model AS ai_model, {fam_sel}
        FROM digital_contract_enrichment e
        JOIN c ON c.contract_id = e.contract_id
        {fam_join}
        WHERE e.is_license
    """) or []

    # ⚠ HOW MUCH DOES THE DEDUP TIEBREAK DECIDE? 124 of these contracts have
    # more than one row in `contracts` (amendment history), and 117 of those
    # record MORE THAN ONE procurement_method. So the route breakdown -- and to
    # a lesser degree the value -- depends on which row we keep. Measured, not
    # assumed: picking a different row moved the top route's share 57% -> 61%.
    # The page must state this rather than present a resolved number as fact.
    amb = {}
    try:
        # ⚠ This probe deliberately does NOT dedup; see the marker on the join.
        arow = await PostgresModelAsync.select_safe("""
            WITH lic AS (SELECT DISTINCT contract_id FROM digital_contract_enrichment
                         WHERE is_license)
            SELECT
              count(*) FILTER (WHERE nrows > 1) AS multi_row,
              count(*) FILTER (WHERE nmethod > 1) AS multi_method,
              count(*) FILTER (WHERE namount > 1) AS multi_amount
            FROM (
              SELECT c.contract_id, count(*) AS nrows,
                     count(DISTINCT coalesce(c.procurement_method,'')) AS nmethod,
                     count(DISTINCT coalesce(c.current_amount,0)) AS namount
              -- RAW-CONTRACTS-JOIN-OK: counting the duplicate rows IS the point
              -- here, so this one must not go through the dedup CTE.
              FROM contracts c JOIN lic l ON l.contract_id = c.contract_id
              GROUP BY c.contract_id) q
        """)
        if arow:
            amb = {k: int(v or 0) for k, v in dict(arow[0]).items()}
    except Exception as exc:  # noqa: BLE001
        logger.warning("license ambiguity probe failed: %s", exc_str(exc))

    # Family -> one-line product summary (describe_license_families.py).
    # ⚠ Separate table because license_family is TRUNCATEd on every rebuild.
    # Absent table just means no summaries render.
    descriptions = {}
    try:
        drows = await PostgresModelAsync.select_safe(
            "SELECT family, summary, curated FROM license_family_description")
        descriptions = {d["family"]: {"summary": d["summary"],
                                      "curated": bool(d["curated"])}
                        for d in (drows or [])}
    except Exception as exc:  # noqa: BLE001
        logger.info("license descriptions unavailable: %s", exc_str(exc))

    # Public list prices for the benchmarkable hosting class.
    # ⚠ THIS SEED WAS INERT UNTIL NOW -- written, guarded by a test, and read by
    # nothing. A guard that validates a file proves the file is well-formed, not
    # that anything consumes it; the two failures look identical from the test
    # output. Same class as the never-called register_untracked_tables().
    rate_cards = {}
    try:
        import csv as _csv
        seed = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "seed", "license_rate_cards.csv")
        if os.path.exists(seed):
            with open(seed, newline="", encoding="utf-8") as fh:
                lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
            for r in _csv.DictReader(lines):
                fam = (r.get("family") or "").strip()
                if fam and (r.get("list_price_usd") or "").strip():
                    rate_cards[fam] = {
                        "unit": (r.get("unit") or "").strip(),
                        "list_price_usd": (r.get("list_price_usd") or "").strip(),
                        "source_url": (r.get("source_url") or "").strip(),
                        "as_of": (r.get("as_of") or "").strip(),
                        "note": (r.get("note") or "").strip(),
                    }
    except Exception as exc:  # noqa: BLE001
        logger.info("rate cards unavailable: %s", exc_str(exc))

    # Purchase class + curated replacement candidates + catalogue provenance.
    # ⚠ ONLY tier='curated' is read. Auto matches exist in the same table and must
    # never reach a page -- an unreviewed candidate rendering as a claim is the
    # #146 failure, made impossible here by the WHERE clause rather than by
    # remembering to filter.
    classes, candidates, cat_meta = {}, {}, {}
    try:
        crows = await PostgresModelAsync.select_safe(
            "SELECT family, class, lever, why, capability, tier FROM license_family_class")
        classes = {c["family"]: dict(c) for c in (crows or [])}
    except Exception as exc:  # noqa: BLE001
        logger.info("license classes unavailable: %s", exc_str(exc))
    # WHO MAKES IT. ⚠ Degrades to {} on an absent table, exactly like the maps
    # above, so a database where build_license_procurement.py has not yet run
    # renders "Maker not yet identified" rather than raising -- the #146 shape.
    makers = {}
    try:
        mrows = await PostgresModelAsync.select_safe(
            """SELECT family, maker, maker_kind, maker_vendor_id, parent, formerly,
                      hq, ticker, website, source_url, as_of, why
               FROM license_family_maker""")
        makers = {m["family"]: dict(m) for m in (mrows or [])}
    except Exception as exc:  # noqa: BLE001
        logger.info("license makers unavailable: %s", exc_str(exc))
    # PRODUCT-grain overrides of the family class. ⚠ Absent table or absent row
    # both mean "use the family answer", so this degrades to the previous
    # behaviour instead of emptying the class view — the #146 failure shape.
    prod_classes = {}
    try:
        prows = await PostgresModelAsync.select_safe(
            "SELECT product_norm, product, class, lever, why, tier FROM license_product_class")
        prod_classes = {p["product_norm"]: dict(p) for p in (prows or [])}
    except Exception as exc:  # noqa: BLE001
        logger.info("license product classes unavailable: %s", exc_str(exc))
    try:
        rrows = await PostgresModelAsync.select_safe(
            """SELECT family, candidate, candidate_kind, confidence, licence,
                      gov_adopters, url, why
               FROM license_replacement_candidate
               WHERE tier = 'curated'
               ORDER BY CASE confidence WHEN 'strong' THEN 0 WHEN 'partial' THEN 1
                                        WHEN 'adjacent' THEN 2 ELSE 3 END,
                        gov_adopters DESC NULLS LAST""")
        for r in (rrows or []):
            candidates.setdefault(r["family"], []).append(dict(r))
    except Exception as exc:  # noqa: BLE001
        logger.info("license candidates unavailable: %s", exc_str(exc))
    try:
        mrow = await PostgresModelAsync.select_safe(
            """SELECT generated_at, entries, mapped_products, known_gaps
               FROM license_catalogue_meta WHERE id = 1""")
        if mrow:
            cat_meta = dict(mrow[0])
            if isinstance(cat_meta.get("known_gaps"), str):
                import json as _json
                try:
                    cat_meta["known_gaps"] = _json.loads(cat_meta["known_gaps"])
                except ValueError:
                    cat_meta["known_gaps"] = {}
    except Exception as exc:  # noqa: BLE001
        logger.info("catalogue meta unavailable: %s", exc_str(exc))

    # Vendor name -> PASSPort supplier id, for profile links. ONLY where the name
    # resolves to EXACTLY ONE id (86 of 88 names on this set; ABSORB SOFTWARE INC
    # matches two supplier ids and stays unlinked).
    # ⚠ Moved to modules/vendorids.py so the Renewal Queue resolves ids the same
    # way. The queue was doing it with a LEFT JOIN, which DUPLICATED the Absorb
    # contract and is why its licence count read one higher than this page's.
    vendor_ids = await vendorids.unique_map(PostgresModelAsync, logger)

    # ⚠⚠ CONTRACTS THE ANALYSIS CANNOT SEE, AND WHY THEY MATTER.
    # Every query above goes through _CONTRACTS, which requires a contract_id --
    # so 2,546 rows worth $14.5B are invisible here, because PASSPort assigns a
    # contract id at REGISTRATION and these have not reached it yet (status In
    # Progress / Draft / Pending approval). Excluding them from the totals is
    # right: they are ceilings on unsigned paper, not spend, and counting them
    # would inflate every figure on the page.
    #
    # Saying nothing about them is NOT right. The page's whole argument is that
    # the City buys one product on many separate contracts and should consolidate
    # onto citywide agreements -- and the citywide agreements are sitting in this
    # bucket. Measured 2026-08-11: a $75M CITYWIDE SALESFORCE PURCHASING CONTRACT
    # and a $1.2B CITYWIDE IT PURCHASING CONTRACT, neither visible anywhere.
    #
    # ⚠ SCOPED BY A DERIVED VENDOR SET, NOT BY THE digital_services TAG. That tag
    # is a name/industry heuristic and is noisy at this end: it admits Inter-Con
    # SECURITY SYSTEMS (guards), NYS Industries for the Disabled (janitorial) and
    # Caddell Drydock (ship repair), so a tag-scoped list would put janitorial
    # services on a software page. Scoping to vendors who ALREADY SELL THE CITY
    # LICENSES in this very dataset is self-limiting and needs no new AI pass --
    # measured, it drops all three and keeps the IT vehicles.
    #
    # ⚠ KEYED ON EPIN, because contract_id is precisely what these lack.
    # ⚠ The vendor set is computed HERE, in Python, from the licence rows already
    # fetched above -- not by re-joining `contracts` in SQL. It is provably the
    # same set of vendors the page displays, and it costs the query one fewer
    # raw join into a table whose duplicate rows are the documented hazard.
    lic_vendors = sorted({(r.get("vendor_name") or "").strip() for r in rows
                          if (r.get("vendor_name") or "").strip()})
    # ⚠⚠ THE QUERY MOVED TO modules/pipelinevehicles (#247) — ONE definition for the
    # section. The AGGREGATE this page used to publish (121 agreements / $1.61B,
    # scoped to licence vendors) is no longer rendered here: the block's canonical
    # home is the Overview, where the same idea over the whole technology universe is
    # 257 / $3.22B. Two pages publishing two figures for one question is the defect
    # this section spent a week removing.
    # ⚠ The ROWS are still loaded, because the FAMILY pages use them for something
    # the Overview cannot do: a title match against one product family
    # (_pipeline_for_family). That is a different view, not a second total.
    pipeline_block = await pipelinevehicles.load(PostgresModelAsync, lic_vendors, logger)

    today = time.strftime("%Y-%m-%d")
    out = []
    for r in rows:
        d = dict(r)
        d["value"] = float(d.get("current_amount") or d.get("award_amount") or 0)
        d["award_amount"] = float(d.get("award_amount") or 0)
        d["current_amount"] = float(d.get("current_amount") or 0)
        d["expiring"] = _is_expiring(d.get("end_date"), today)
        method = (d.get("procurement_method") or "").strip().lower()
        d["competitive"] = method in COMPETITIVE_PROCUREMENT_METHODS
        # ⚠ "Non-competitive" on this page means SOLE SOURCE OR NEGOTIATED
        # ACQUISITION, the same rule as the Renewal Review Queue (owner,
        # 2026-09-24; see NONCOMPETITIVE_REVIEW_METHODS). `competitive` above stays
        # for the CSV's factual "competitively bid" column: no licence used sealed
        # bid or proposal, so "not competitive" was every row, and a count equal
        # to the row count told the reader nothing.
        d["no_competition"] = method in NONCOMPETITIVE_REVIEW_METHODS
        d["end_year"] = (str(d["end_date"]).strip()[-4:]
                         if d.get("end_date") and len(str(d["end_date"]).strip()) == 10 else "")
        d["vendor_id"] = vendor_ids.get(vendorids.key(d.get("vendor_name")))
        # ⚠ Cost per contract-YEAR is derivable; cost per SEAT is not, because no
        # seat or unit count exists anywhere in this data. Deriving the first and
        # refusing the second is the line between price context and invention.
        d["term_years"] = _term_years(d.get("start_date"), d.get("end_date"))
        d["per_year"] = (d["value"] / d["term_years"]) if d["term_years"] else None
        out.append(d)
    # ⚠ `pipeline` is returned ALONGSIDE `rows`, never merged into it. Every
    # aggregate on this page reads `rows`; a pipeline row entering that list would
    # silently add unregistered ceilings to the headline value. A test pins the
    # separation.
    # ⚠ `value` is carried alongside `ceiling` ONLY for the family pages, which
    # render `$pv['value']`. It is the same number under the name that view already
    # reads — renaming a key a template subscripts is how the licence column went
    # blank on prod in #235.
    pipe = []
    for r in (pipeline_block.get("rows") or []):
        d = dict(r)
        d["value"] = d.get("ceiling", 0.0)
        pipe.append(d)
    return {"available": True, "rows": out, "grouped": have_family,
            "ambiguity": amb, "descriptions": descriptions,
            "classes": classes, "product_classes": prod_classes,
            "makers": makers,
            "candidates": candidates, "catalogue": cat_meta,
            "rate_cards": rate_cards, "pipeline": pipe,
            "pipeline_block": pipeline_block}


def _agg(rows, key, keep_vendor_names=False):
    """{key: {contracts, value, agencies, vendors, expiring, expiring_value,
    non_competitive}} — one helper so every table on the page counts the same
    way. Divergent per-table aggregation is how two figures on one page end up
    disagreeing.

    `keep_vendor_names` additionally retains the FULL value-ranked vendor name
    list per group as `vendor_names`. The count and the names come from the one
    accumulator, so they cannot disagree; the names are kept full here and capped
    only at display time (the count-before-you-cap rule below applies to them
    too — the reseller merge needs the whole list to dedup against notice
    vendors, and a capped list would overcount the notice-only remainder)."""
    acc = {}
    for r in rows:
        k = r.get(key) or "(unknown)"
        a = acc.setdefault(k, {"key": k, "contracts": 0, "value": 0.0,
                               "agencies": set(), "vendors": {}, "products": set(),
                               "expiring": 0, "expiring_value": 0.0,
                               "non_competitive": 0, "is_generic": False,
                               "curated": False, "first_start": "", "last_end": "",
                               "vendor_id": None, "slug": ""})
        a["contracts"] += 1
        a["value"] += r["value"]
        a["agencies"].add(r.get("agency") or "")
        vn = r.get("vendor_name") or ""
        a["vendors"][vn] = a["vendors"].get(vn, 0.0) + r["value"]
        if r.get("product"):
            a["products"].add(r["product"])
        if r["expiring"]:
            a["expiring"] += 1
            a["expiring_value"] += r["value"]
        if r["no_competition"]:
            a["non_competitive"] += 1
        # First non-null wins; for a vendor group every row shares the id, and
        # for a family group it is unused.
        if r.get("vendor_id") and not a.get("vendor_id"):
            a["vendor_id"] = r["vendor_id"]
        if r.get("slug") and not a.get("slug"):
            a["slug"] = r["slug"]
        a["is_generic"] = a["is_generic"] or bool(r.get("is_generic"))
        a["curated"] = a["curated"] or bool(r.get("fam_curated"))
        sd, ed = (r.get("start_date") or ""), (r.get("end_date") or "")
        if sd and (not a["first_start"] or sd[-4:] < a["first_start"][-4:]):
            a["first_start"] = sd
        if ed and (not a["last_end"] or ed[-4:] > a["last_end"][-4:]):
            a["last_end"] = ed
    for a in acc.values():
        a["agencies"] = len([x for x in a["agencies"] if x])
        vend = {n: v for n, v in a["vendors"].items() if n}
        a["vendors"] = len(vend)
        if keep_vendor_names:
            a["vendor_names"] = [n for n, _ in
                                 sorted(vend.items(), key=lambda kv: -kv[1])]
        # ⚠ Count BEFORE capping. The list is truncated for display, and reading
        # len() off the capped list silently undercounts any agency with more
        # than 12 products -- a wrong number that looks like a measurement.
        a["product_count"] = len(a["products"])
        a["products"] = sorted(a["products"])[:12]
    return acc


@router.get("")
async def licenses():
    """Everything the Licenses page renders, in one payload."""
    now = time.time()
    hit = _CACHE.get("payload")
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]

    data = await _load()
    if not data.get("available"):
        return {"available": False, "reason": data.get("reason", "unavailable")}
    rows = data["rows"]

    fam = _agg(rows, "family", keep_vendor_names=True)
    descs = data.get("descriptions") or {}
    bvb_by_fam = {}
    for r in rows:
        k = (r.get("build_vs_buy") or "").strip().lower()
        if k:
            bvb_by_fam.setdefault(r.get("family") or "", {}) \
                      .update({k: bvb_by_fam.get(r.get("family") or "", {}).get(k, 0) + 1})
    for f in fam.values():
        f["summary"] = (descs.get(f["key"]) or {}).get("summary", "")
        counts = bvb_by_fam.get(f["key"], {})
        ranked = sorted(counts.items(), key=lambda kv: -kv[1])
        # ⚠ `mixed` matters as much as the rating: it says this product's own
        # contracts were rated inconsistently by the classifier.
        f["replaceability"] = ranked[0][0] if ranked else ""
        f["replaceability_mixed"] = len(counts) > 1
    families = sorted(fam.values(), key=lambda a: -a["value"])
    real = [f for f in families if not f["is_generic"]]
    # "Bought through": the family's contract vendors plus notice awarded-to
    # vendors (#287's column, rolled up per family). Merged against the FULL
    # vendor_names list, then the list is dropped from the payload — resellers
    # carries the capped display names with the full counts beside them.
    notice_res, resellers_meta = await _notice_resellers()
    for f in real:
        f["resellers"] = resellers.merge(f.get("vendor_names") or [],
                                         notice_res.get(f["key"]))
    for f in families:
        f.pop("vendor_names", None)
    # ⭐ KIND AND FUNCTION PER FAMILY, so the Products index can carry them as
    # columns on the one table instead of as two sections a reader scrolls to.
    # ⚠ FAMILY-level class, from the same `classes` map the class rollup reads --
    # not the product-grain dominant the family PAGE resolves through
    # licenseclass.mix(), which needs that family's rows and this rollup no
    # longer holds them. The two agree on every family without a product
    # override (811 of 814); on the three with one, the family page states the
    # mix and this column shows the family answer, which is what the seed says.
    # ⚠ Labels are SERVED from the vocabulary seed, never mapped in a view --
    # that map has been stale in three views at once before.
    cap_labels = _capability_labels()
    classes_map = data.get("classes") or {}
    for f in real:
        # ⚠ Editorial, not classifier-derived -- a claim about the technology ERA.
        # Surfaced per family so the separate "mainframe tail" table (which said
        # nothing the family row could not) could be retired.
        f["legacy"] = f["key"] in _LEGACY_FAMILIES
        fc = classes_map.get(f["key"]) or {}
        f["purchase_class"] = fc.get("class", "")
        f["class_tier"] = fc.get("tier", "")
        cap = fc.get("capability", "")
        f["capability"] = cap
        f["capability_label"] = (cap_labels.get(cap, cap) if cap and cap != _OTHER_CAPABILITY
                                 else (_OTHER_CAPABILITY_LABEL if cap else ""))

    total_value = sum(r["value"] for r in rows)
    by_year = _by_year(rows)
    award_by_year = _award_by_year(rows)
    spend_by_year = await _spend_by_year(rows)
    # ⚠ Every list below is computed IN FULL and sliced only where the payload is
    # capped, with the full length carried in `totals`. Reading a count off a
    # truncated list is the "count before you cap" defect this codebase already
    # paid for once in _agg.
    # ⚠ ONE rule, applied per row, with the count derived from the flags rather than
    # from a second expression. The page used to carry a separate "One product, many
    # separate contracts" table that was a filtered re-sort of this very list; it is
    # now a badge and a filter on the one table, so the two can no longer disagree
    # about which families qualify.
    for f in real:
        f["consolidation_candidate"] = (
            f["agencies"] >= _FAMILY_FRAG_MIN_AGENCIES
            and f["contracts"] >= _FAMILY_FRAG_MIN_CONTRACTS)
    frag_all = sorted([f for f in real if f["consolidation_candidate"]],
                      key=lambda a: (-a["agencies"], -a["contracts"]))
    methods_all = sorted(_agg(rows, "procurement_method").values(),
                         key=lambda a: -a["contracts"])
    agency_all = sorted(_agg(rows, "agency").values(), key=lambda a: -a["value"])
    vendor_all = sorted(_agg(rows, "vendor_name").values(), key=lambda a: -a["value"])
    caps_all = _capability_rollup(rows, data.get("classes") or {})
    # ⚠ Buying off an already-competed federal or state schedule. The page says so
    # in prose, and used to say it with a hardcoded "138" that had drifted to 149.
    intergov = sum(1 for r in rows
                   if (r.get("procurement_method") or "").strip().lower()
                   .startswith("intergovernmental"))
    # ⚠ Read from `data`, never merged into `rows`. See _load()'s pipeline note.
    pipe_rows = data.get("pipeline") or []

    payload = {
        "available": True,
        "grouped": data["grouped"],
        "summary": {
            "contracts": len(rows),
            "total_value": sum(r["value"] for r in rows),
            "expiring": sum(1 for r in rows if r["expiring"]),
            "expiring_value": sum(r["value"] for r in rows if r["expiring"]),
            "agencies": len({r.get("agency") for r in rows if r.get("agency")}),
            "vendors": len({r.get("vendor_name") for r in rows if r.get("vendor_name")}),
            "families": len(real),
            "generic_contracts": sum(1 for r in rows if r.get("is_generic")),
            "generic_value": sum(r["value"] for r in rows if r.get("is_generic")),
            "non_competitive": sum(1 for r in rows if r["no_competition"]),
            "ai_models": sorted({r.get("ai_model") for r in rows if r.get("ai_model")}),
            # ⚠ Contracts NOT known to have ended, derived by subtraction from the
            # calendar's own `ended` bucket rather than recomputed -- two
            # independent definitions of "active" on one page is how the two
            # expiring figures came to disagree. Rows with no usable end date
            # count as active here, and the page's label says so.
            "active_contracts": len(rows) - by_year["ended"]["contracts"],
            "active_value": total_value - by_year["ended"]["value"],
            # Hand-reviewed coverage, measured. See _reviewed().
            "reviewed": _reviewed(real, data.get("classes") or {}, total_value),
            "intergov_contracts": intergov,
            # See the ambiguity probe in _load(): how much the one-row-per-contract
            # choice is actually deciding.
            "ambiguity": data.get("ambiguity", {}),
        },
        # ⚠ Full length of every list the payload truncates, so the page can say
        # "top 25 of 88" instead of implying it shows everything. Computed from
        # the unsliced lists above.
        # The thresholds behind the consolidation badge, served so the page can state
        # the rule it is applying instead of hardcoding "3-agency, 3-contract".
        "consolidation_rule": {"min_agencies": _FAMILY_FRAG_MIN_AGENCIES,
                               "min_contracts": _FAMILY_FRAG_MIN_CONTRACTS},
        # The "Bought through" column's sources, measured — the page words its
        # note from these rather than typing "531 notices" as a literal. When
        # `available` is False the notice half never loaded and the view must
        # describe the column as contract vendors only.
        "resellers_meta": resellers_meta,
        "totals": {
            "families": len(real),
            # ⚠ Still served, and still measured on the unsliced list. The page no
            # longer renders `fragmented` as its own table — it renders this COUNT
            # beside the merged table and flags the rows — but an API consumer may
            # still want the shortlist.
            "fragmented": len(frag_all),
            "by_method": len(methods_all),
            "by_agency": len(agency_all),
            "by_vendor": len(vendor_all),
            "by_capability": len(caps_all),
        },
        # Concentration: what share of all licence value the top families hold.
        "concentration": _concentration(real, total_value),
        # ⚠ NOT capped. It was `real[:60]` of 434 while the section header said
        # "Product families by value" with no denominator, so 374 families simply
        # were not there. The page now paginates client-side instead.
        "families": real,
        "generic": next((f for f in families if f["is_generic"]), None),
        # Fragmentation: one product, many agencies, separate contracts. The
        # page's headline -- it is the question Checkbook cannot ask.
        # ⚠ Cut 30 -> 8. This table is a re-sorted subset of the family table
        # below it, duplicating its rows and its "bought as" lists; at 30 rows it
        # read as a second inventory rather than a shortlist. The family table is
        # now sortable, so the long version lives there and this stays a headline.
        "fragmented": frag_all[:8],
        "by_year": by_year,
        # Products with an open-source alternative, focused on what renews before
        # the horizon. TWO BANDS, never merged — only the curated one names a
        # replacement. See _oss_alternatives.
        "oss": _oss_alternatives(rows, real, data.get("candidates") or {},
                                 data.get("classes") or {},
                                 data.get("product_classes") or {}),
        # ⚠⚠ TWO SERIES, DELIBERATELY SEPARATE AND NEVER ADDED. `award_by_year` is
        # what the City COMMITTED, by the year a contract's term starts — lumpy, and
        # the only view in which the $573.8M Citywide Microsoft ELA appears at all.
        # `spend_by_year` is cash paid out, per fiscal year, and it is a FLOOR: a
        # master agreement carries no payments under its own id. Both carry what the
        # shared 10-year window dropped; see the docstrings.
        "award_by_year": award_by_year,
        "spend_by_year": spend_by_year,
        # ⚠ How licences are actually bought. This exists because the single
        # "not competitively bid" figure is 100% and that is TRUE but misleading:
        # no licence used competitive sealed bid/proposal, yet 57% went through
        # the small-purchase route and 138 rode an already-competed federal GSA
        # schedule. Showing the breakdown instead of the headline percentage is
        # the difference between informing and insinuating.
        # ⚠ THESE THREE ARE SERVED IN FULL, and the caps that were here are gone
        # deliberately (owner decision 2026-09-15). They were `[:15]`/`[:25]`/`[:25]`
        # over 19 methods / 39 agencies / 408 vendors, disclosed as "top 25 of 408".
        # The section's tables now sort on click, and a client-side sort over a
        # capped list sorts THE CAP -- ascending by value on "top 25 of 408" reads
        # as the smallest vendors when it is the 25 largest, smallest first. That is
        # the `by_vendor` defect arriving through a sort control instead of a
        # heading. Serving the whole list is what makes the sort mean what it looks
        # like it means; 408 rows is a rounding error against this payload.
        # ⚠ `totals` below is UNCHANGED and still measured on the unsliced lists --
        # it now equals the served length, which costs nothing and keeps the
        # denominator machinery in place for anything capped in future.
        "by_method": methods_all,
        # Spend grouped by what kind of purchase it is. ⚠ This is the view that
        # surfaces the money the replaceability rating hides: AWS is $6.80M rated
        # `low`, two thirds the size of the entire `high` set.
        "by_class": _class_rollup(rows, data.get("classes") or {},
                                  data.get("product_classes") or {}),
        # ⚠ THE CROSS-AGENCY FUNCTION VIEW. Grouping by product answers "what do we
        # buy"; grouping by FUNCTION answers "how many different things do we buy to
        # do one job, and in how many agencies" -- which is the consolidation
        # question, and is invisible in any per-product view. Ranked by distinct
        # PRODUCTS per function, not by agency count: 29 network-security products
        # across 16 agencies is the finding, while office-productivity spans 18
        # agencies on 2 products (one Microsoft agreement) and is not fragmented.
        "by_capability": caps_all,
        "catalogue": data.get("catalogue") or {},
        "candidate_count": sum(len(v) for v in (data.get("candidates") or {}).values()),
        "by_agency": agency_all,
        "by_vendor": vendor_all,
        # ⚠ RETAINED FOR API CONSUMERS, no longer its own table on the page: every
        # family row now carries `legacy`, and a second table listing the same
        # families with the same numbers was duplication, not emphasis.
        "legacy": [f for f in real if f["legacy"]],
        # ⚠⚠ NOT PART OF ANY TOTAL ABOVE. See the pipeline query in _load().
        # `ceiling` is deliberately named -- these are maximum values on
        # agreements that are not registered and in most cases cover far more
        # than software (the $1.2B SHI vehicle is all citywide IT purchasing).
        # Calling it "value" beside a page whose headline is $1.37B would invite
        # exactly the addition this section exists to prevent.
        # ⚠⚠ THE AGGREGATE MOVED TO THE OVERVIEW (#247) and this key now says so
        # rather than publishing a second, narrower figure. `moved_to` is deliberate:
        # a consumer that used to read `count`/`ceiling` here gets a KeyError and goes
        # looking, instead of silently reading a number that no longer means what the
        # section publishes. The rows stay for the family-level title match.
        "pipeline": {
            "moved_to": "/oce/digital-reform/all -> pipeline",
            "reason": ("scoped to licence vendors this was 121 agreements; the "
                       "section-level figure covers the whole technology universe"),
            "rows_for_family_matching": len(pipe_rows),
        },
    }
    # ⚠⚠ DO NOT CACHE A PENDING PAYLOAD. The paid series is scanned in the background
    # (see `_spend_by_year`), so the first payload after a restart has `pending: true`
    # — caching that for 6h would hide the chart for 6h even though the scan finishes
    # in seconds. Rebuilding for the ~20s the scan takes costs 1.9s a request and
    # removes the race entirely; the alternative (clearing the cache from the
    # background task) can land BEFORE this line and be overwritten.
    if not (payload.get("spend_by_year") or {}).get("pending"):
        _CACHE["payload"] = (now, payload)
    return payload


def _capability_rollup(rows, classes):
    """Function -> agencies, distinct products, contracts, value.

    ⚠ Generic-product families ARE included: the function is knowable from the
    contract text even when the product name is not, and excluding them hid the
    largest software-asset-management spend from this very view."""
    acc = {}
    for r in rows:
        cap = (classes.get(r.get("family") or "") or {}).get("capability") or ""
        if not cap:
            continue
        a = acc.setdefault(cap, {"key": cap, "contracts": 0, "value": 0.0,
                                 "agencies": set(), "products": set()})
        a["contracts"] += 1
        a["value"] += r["value"]
        if r.get("agency"):
            a["agencies"].add(r["agency"])
        if r.get("family"):
            a["products"].add(r["family"])
    labels = _capability_labels()
    out = []
    for a in acc.values():
        a["agencies"] = len(a["agencies"])
        a["products"] = len(a["products"])
        a["label"] = labels.get(a["key"], a["key"])
        # Fragmentation = many products for one job across many agencies. Both
        # factors matter: 2 products across 18 agencies is a citywide agreement,
        # 29 products across 16 agencies is a consolidation opportunity.
        # ⚠ `other` is excluded: it is the abstention bucket, and you cannot
        # consolidate the functions you failed to identify. It was carrying the
        # badge AND sorting first, so the loudest row on the table was the one
        # row that means "we do not know".
        a["fragmented"] = (a["products"] >= _FRAG_MIN_PRODUCTS
                           and a["agencies"] >= _FRAG_MIN_AGENCIES
                           and a["value"] >= _FRAG_MIN_VALUE
                           and a["key"] != _OTHER_CAPABILITY)
        out.append(a)
    # ⚠ Keep only the strongest _FRAG_MAX_BADGED flags. See the constant.
    for a in sorted([x for x in out if x["fragmented"]],
                    key=lambda x: (-x["products"], -x["value"]))[_FRAG_MAX_BADGED:]:
        a["fragmented"] = False
    # ⚠ `other` sorts LAST regardless of size, matching how the class table
    # isolates "Not yet classified". Ranked by distinct products otherwise.
    return sorted(out, key=lambda a: (a["key"] == _OTHER_CAPABILITY,
                                      -a["products"], -a["value"]))


def _class_rollup(rows, classes, product_classes=None):
    """Value by purchase class, with the lever each one implies.

    ⚠ Resolved at PRODUCT grain with a family fallback (modules/licenseclass), so
    a family holding two kinds of purchase contributes to both buckets. Before
    that, one class per family sent $68.9M of Microsoft support into
    `software-licence` and asked it about open-source substitutes.

    ⚠ Unclassified rows are reported as their own bucket rather than folded into
    software-licence, because quietly defaulting them would overstate how much has
    actually been assessed.

    ⚠ This docstring used to say "most of the inventory is unclassified today".
    That is stale: measured 2026-09-16, unclassified is **2 families / $10.5M /
    0.6%** of value — the AI pass covers 812 of 814 families. What is thin is not
    coverage but REVIEW, and those are different claims. Do not read this bucket
    as a review backlog.
    ⚠ The figures above were `3 families / $10.4M / 0.8%` of 431 families when
    written on 2026-08-11; the inventory has since nearly doubled and the SHARE
    fell rather than rose. A coverage figure needs its denominator beside it."""
    out, _ = licenseclass.mix(rows, product_classes or {}, classes)
    for a in out:
        a["families"] = len(a["families"])
        a["products"] = len(a["products"])
        # ⚠ `tiers` is a SET, and a set serialises in an order that varies between
        # processes — so this key flipped between ['auto','curated'] and
        # ['curated','auto'] on identical data. Harmless on the page (only `tier` is
        # rendered) but it makes a payload diff report differences that are not
        # changes, which is exactly the signal a diff exists to carry. Found while
        # diffing this payload before and after the vendor-id refactor: 14
        # "differences", all of them this.
        a["tiers"] = sorted(a["tiers"])
    return out


def _pipeline_for_family(family, pipeline):
    """Unregistered purchasing vehicles whose title names this product family.

    ⚠ A TITLE MATCH, and the page says so. These rows have no contract_id, so
    they never reached the classifier and carry no product identification at all
    -- the title is the only signal that exists. Showing the matched title beside
    the claim is what makes it checkable rather than asserted.

    ⚠ Requires 4+ characters to avoid matching an acronym inside an unrelated
    word, and the value is never added to the family's own total."""
    if not family or len(family) < 4:
        return []
    needle = family.upper()
    return [p for p in pipeline
            if needle in (p.get("contract_title") or "").upper()]


def _reviewed(families, classes, total):
    """Families whose purchase class was reviewed by hand, and their value share.

    ⚠⚠ COMPUTED, NEVER TYPED -- this exists because the typed version had already
    gone wrong on a live page. The note read "the largest 20 product families --
    88.0% of the value on this page -- have been reviewed by hand" as literal
    template text, while the page's OWN concentration strip, computed from the
    same payload, read 87.7% for the top 20 and the seed had grown to 38 curated
    rows. Three numbers in one paragraph, two of them stale, all of them
    presented with equal confidence.

    It also fixes what the sentence was actually claiming. "Top 20 families" is a
    proxy for "reviewed"; the real predicate is `tier='curated'` on the class
    row, which is the thing a version-controlled seed can evidence. Measuring the
    predicate directly means the claim cannot drift from the seed, and it grows
    truthfully as more families are curated.

    ⚠ Reads the FAMILY-level tier. Product-grain overrides refine a family that
    is already curated; they never make an unreviewed family reviewed."""
    curated = [f for f in families
               if (classes.get(f["key"]) or {}).get("tier") == "curated"]
    value = sum(f["value"] for f in curated)
    return {"families": len(curated), "value": value,
            "share": round(value / total * 100, 1) if total else 0.0}


def _concentration(families, total):
    """Top-N share of total value. Answers 'how much of this is one vendor'."""
    if not total:
        return {}
    running, out = 0.0, {}
    for i, f in enumerate(sorted(families, key=lambda a: -a["value"]), 1):
        running += f["value"]
        if i in (1, 3, 5, 10, 20):
            out[f"top{i}"] = round(running / total * 100, 1)
    return out


# The one purchase class for which "could we replace this with open source?" is
# the right question. Asking it of hosting or a support tier answers "no" and
# hides the money (#the AWS case: $6.80M rated `low`, invisible everywhere).
_SUBSTITUTION_CLASS = "software-licence"


def _oss_alternatives(rows, families, candidates, classes, product_classes):
    """Products with an open-source alternative, focused on what renews soonest.

    Two BANDS, never merged, because they carry completely different evidential
    weight — the same discipline as `same_vendor` vs `co_terminating` on the
    contract page:

      * `curated` — a hand-reviewed candidate from license_replacement_candidate
        (tier='curated'), with its citation and government-adopter count. This
        band NAMES a specific product to move to. Measured 2026-08-21: 19 families
        / 22 contracts / $75.0M with a contract ending before the horizon.
      * `review` — the classifier rated the purchase `build_vs_buy = high` but no
        human has picked a replacement. This band names NOTHING; it is a queue of
        products worth a look.

    ⚠⚠ ONLY THE CURATED BAND MAY NAME AN OSS PRODUCT. That is #146's rule made
    structural: an unreviewed candidate cannot reach a page by omission, because
    the query that loads them is already scoped to tier='curated' and the review
    band never reads that table at all.

    ⚠ THE RATING IS SHOWN ONLY FOR `software-licence` PURCHASES. Asking "could the
    City build this?" of hosting or a support tier answers "no" and hides the
    money — AWS sat at $6.80M rated `low` and appeared in no replaceability view,
    against a whole `high` set of $10.13M. modules/licenseclass owns the class;
    this never re-derives it.
    """
    by_family = {f["key"]: f for f in families}
    cur_rows, review_rows, no_alternative = [], [], []
    seen_review = set()

    # Per family: what is expiring, and when.
    exp = {}
    for r in rows:
        if not r.get("expiring"):
            continue
        f = r.get("family") or ""
        if not f:
            continue
        e = exp.setdefault(f, {"contracts": 0, "value": 0.0, "soonest": ""})
        e["contracts"] += 1
        e["value"] += float(r.get("value") or 0)
        ed = str(r.get("end_date") or "").strip()
        if len(ed) == 10 and (not e["soonest"] or ed[-4:] + ed[:5] < e["soonest"][-4:] + e["soonest"][:5]):
            e["soonest"] = ed

    for family, cands in (candidates or {}).items():
        f = by_family.get(family)
        e = exp.get(family)
        if not f or not e or e["contracts"] == 0:
            continue
        # ⚠⚠ A CURATED ROW CAN BE A REVIEWED *NEGATIVE*. 8 of 56 carry an empty
        # `candidate` with confidence 'none' — somebody looked and found no
        # credible open-source substitute. That is a real finding and is counted
        # below, but it must NOT sit in a table headed "with a named
        # alternative", where it renders as a blank cell and quietly breaks the
        # heading's promise. Shipped that way for one deploy; caught by reading
        # the rendered row rather than the payload.
        named = [c for c in cands if (c.get("candidate") or "").strip()]
        if not named:
            no_alternative.append({
                "family": family, "slug": f.get("slug", ""),
                "expiring_contracts": e["contracts"],
                "expiring_value": e["value"],
            })
            continue
        best = named[0]
        cur_rows.append({
            "family": family, "slug": f.get("slug", ""),
            "value": f["value"], "contracts": f["contracts"],
            "expiring_contracts": e["contracts"], "expiring_value": e["value"],
            "soonest_end": e["soonest"],
            "candidate": best.get("candidate", ""),
            "candidate_kind": best.get("candidate_kind", ""),
            "confidence": best.get("confidence", ""),
            "licence": best.get("licence", ""),
            "gov_adopters": best.get("gov_adopters"),
            "url": best.get("url", ""),
            "why": best.get("why", ""),
            "alternatives": len(cands),
        })

    for r in rows:
        family = r.get("family") or ""
        if not r.get("expiring") or family in (candidates or {}) or family in seen_review:
            continue
        if (r.get("build_vs_buy") or "").strip().lower() != "high":
            continue
        # ⚠ Class gate: see the docstring. modules/licenseclass is the ONE owner
        # of what kind of purchase a contract is — resolved at product grain with
        # a family fallback, never re-derived here.
        res = licenseclass.resolve(r.get("product"), r.get("family"),
                                   product_classes, classes)
        if (res.get("class") or "") != _SUBSTITUTION_CLASS:
            continue
        f = by_family.get(family)
        e = exp.get(family)
        if not f or not e:
            continue
        seen_review.add(family)
        review_rows.append({
            "family": family, "slug": f.get("slug", ""),
            "value": f["value"], "contracts": f["contracts"],
            "expiring_contracts": e["contracts"], "expiring_value": e["value"],
            "soonest_end": e["soonest"],
        })

    no_alternative.sort(key=lambda a: -a["expiring_value"])
    cur_rows.sort(key=lambda a: -a["expiring_value"])
    review_rows.sort(key=lambda a: -a["expiring_value"])
    return {
        "curated": cur_rows,
        "review": review_rows,
        "curated_total": {"families": len(cur_rows),
                          "contracts": sum(a["expiring_contracts"] for a in cur_rows),
                          "value": sum(a["expiring_value"] for a in cur_rows)},
        "review_total": {"families": len(review_rows),
                         "contracts": sum(a["expiring_contracts"] for a in review_rows),
                         "value": sum(a["expiring_value"] for a in review_rows)},
        # Reviewed, and no credible substitute found — a finding, not a gap in
        # the review. Counted so the page can say it rather than looking as if
        # these products were never looked at.
        "no_alternative": no_alternative,
        "no_alternative_total": {"families": len(no_alternative),
                                 "contracts": sum(a["expiring_contracts"] for a in no_alternative),
                                 "value": sum(a["expiring_value"] for a in no_alternative)},
        "horizon": licensewindow.HORIZON,
    }


def _by_year(rows):
    """Renewal calendar: licence contracts ending per year, future only.

    ⚠ Only counts rows with a parseable end date. `no_end_date` is reported
    alongside so a reader can see the denominator rather than assuming the
    calendar covers everything.

    ⚠⚠ AND `ended` IS REPORTED FOR THE SAME REASON, which is the bigger of the
    two. Contracts that already ended were dropped here in silence while still
    counting toward every headline figure on the page -- so a calendar showing
    262 contracts sat under a tile reading 948, and roughly three quarters of the
    inventory was invisible with nothing saying so. 72% of these contracts ended
    before 2026: this analysis is largely HISTORICAL, and a reader who takes the
    headline value as current exposure has been misled by an omission.

    The page renders `ended` as its own line. Both buckets plus `no_end_date`
    plus the year rows must sum to the contract count -- a test pins that, so a
    future filter cannot quietly drop rows into a gap again."""
    acc, missing = {}, 0
    ended_contracts, ended_value = 0, 0.0
    today_year = time.strftime("%Y")
    # year -> {family: value}, so each row can name its own largest line. The
    # 2030 row is 97% one Microsoft agreement; without this it reads as a
    # broad-based $646.7M cliff.
    fams = {}
    for r in rows:
        y = r["end_year"]
        if not y:
            missing += 1
            continue
        if y < today_year:
            ended_contracts += 1
            ended_value += r["value"]
            continue
        a = acc.setdefault(y, {"year": y, "contracts": 0, "value": 0.0, "expiring": 0})
        a["contracts"] += 1
        a["value"] += r["value"]
        if r["expiring"]:
            a["expiring"] += 1
        f = r.get("family") or ""
        if f:
            fy = fams.setdefault(y, {})
            fy[f] = fy.get(f, 0.0) + r["value"]
    for a in acc.values():
        ranked = sorted(fams.get(a["year"], {}).items(), key=lambda kv: -kv[1])
        a["top_family"] = ranked[0][0] if ranked else ""
        a["top_family_value"] = ranked[0][1] if ranked else 0.0
    return {"years": sorted(acc.values(), key=lambda a: a["year"]),
            "no_end_date": missing,
            "ended": {"contracts": ended_contracts, "value": ended_value}}


# ------------------------------------------------------- awarded and paid, by year
# ⚠ ONE window for both charts, so they cannot disagree about how far back the page
# looks: the last N COMPLETE years plus the year in progress, reported separately.
# Owner decision 2026-08-13. Both series carry what the window dropped, because a
# capped chart with no denominator is the defect this page already paid for in
# `by_vendor` (25 of 88 rows under a heading that implied all of them).
_WINDOW_YEARS = 10

# PASSPort id prefixes. ⚠ MEASURED, NOT ASSUMED: all 29 MA/MMA licence agreements
# carry ZERO payments under their own id ($727.4M), while 1,440 of 1,572 ordinary
# contracts do. A master is a VEHICLE -- agencies buy against it on their own
# purchase orders, which carry their own ids -- so this is not a matching failure
# and the money is not lost, it is filed elsewhere.
_MASTER_PREFIXES = ("MA", "MMA")


def _is_master(contract_id) -> bool:
    cid = str(contract_id or "").upper().lstrip()
    return cid.startswith(_MASTER_PREFIXES)


def _window(buckets: dict, current: int):
    """Split year buckets into (complete-in-window, in-progress, dropped-as-too-old).

    Exhaustive by construction: every bucket lands in exactly one of the three, so
    the three plus `no_date` always account for the whole row set. A test pins it.
    """
    inside, partial, dropped = [], [], []
    for y in sorted(buckets):
        rec = buckets[y]
        if rec["year"] >= current:
            partial.append(rec)
        elif rec["year"] >= current - _WINDOW_YEARS:
            inside.append(rec)
        else:
            dropped.append(rec)
    return inside, partial, dropped


def _award_by_year(rows: list) -> dict:
    """AWARDED value by the year each contract's term starts.

    ⚠⚠ THIS IS A COMMITMENT, NOT SPENDING, and the two must never be read as one
    series: 2025 reads $794.1M almost entirely because of a single $573.8M Microsoft
    renewal. That lumpiness is exactly why the paid series exists beside it -- and
    conversely this chart is the ONLY place the ELA appears at all, because a master
    agreement carries no payments under its own id.

    ⚠ `top_family` per year is served for the same reason the renewal calendar serves
    it: a $794.1M bar with no subject reads as a broad-based surge rather than as one
    agreement.
    """
    buckets, fams = {}, {}
    no_date_c, no_date_v = 0, 0.0
    for r in rows:
        sd = str(r.get("start_date") or "").strip()
        y = sd[-4:] if len(sd) == 10 and sd[-4:].isdigit() else ""
        v = float(r.get("value") or 0)
        if not y:
            no_date_c += 1
            no_date_v += v
            continue
        b = buckets.setdefault(int(y), {"year": int(y), "label": y, "contracts": 0,
                                        "value": 0.0})
        b["contracts"] += 1
        b["value"] += v
        f = r.get("family") or ""
        if f:
            fams.setdefault(int(y), {})
            fams[int(y)][f] = fams[int(y)].get(f, 0.0) + v
    for y, b in buckets.items():
        ranked = sorted(fams.get(y, {}).items(), key=lambda kv: -kv[1])
        b["top_family"] = ranked[0][0] if ranked else ""
        b["top_family_value"] = ranked[0][1] if ranked else 0.0

    current = int(time.strftime("%Y"))
    inside, partial, dropped = _window(buckets, current)
    return {
        "available": bool(inside or partial),
        "years": inside,
        "partial": partial,
        "total": sum(b["value"] for b in inside),
        "total_all": sum(b["value"] for b in buckets.values()) + no_date_v,
        # ⚠ What the window hides, so the page can say it rather than imply
        # completeness.
        "dropped": {"contracts": sum(b["contracts"] for b in dropped),
                    "value": sum(b["value"] for b in dropped),
                    "before": (current - _WINDOW_YEARS)},
        "no_date": {"contracts": no_date_c, "value": no_date_v},
        "window_years": _WINDOW_YEARS,
    }


# ---------------------------------------------------------------- actual spend
# The Checkbook lake refreshes weekly (Sun 02:00), so a day-long cache is already
# far tighter than the data moves. Kept separate from the 6h payload cache so the
# page can recompute its Postgres aggregates without re-running a lake scan.
_SPEND_CACHE = {"ts": 0.0, "data": None}
_SPEND_TTL = 60 * 60 * 24


def _scan_spend_by_year(norm_ids: list) -> tuple:
    """Payments recorded against these contract ids, grouped by NYC fiscal year.

    ⚠ MATCHED ON `upper(contract_id)`, NOT A NORMALIZING REGEX. Measured on this
    exact set: both forms return $885.2M over 8,273 rows, byte-identical, because
    the lake already stores ids un-dashed and uppercase — and wrapping the column
    in a function makes the predicate opaque to Parquet row-group statistics, which
    is the #160 defect that cost 10-34x on the contract page. This scan is 3.6s
    over all 18 fiscal years because the raw column can be pruned.

    ⚠ ONE materialized scan, aggregated three ways. The year series, the set of
    ids that were paid at all (needed for the coverage statement) and the newest
    real payment date are all the same rows; reading them separately would scan
    the lake three times.

    ⚠ `MAX(issue_date)` IS BOUNDED BY TODAY. The lake carries future-dated rows —
    measured, the FY2027 partition runs to 2027-03-27, seven months out — so an
    unbounded max would publish an "as of" date that has not happened yet.

    Blocking; must run under to_duckdb_thread. Returns (year_rows, paid_ids, as_of).
    """
    if not norm_ids:
        return [], [], None
    con = _persistent_spending_connection().cursor()
    files = get_spending_files(all_years=True)
    try:
        row = con.execute(
            f"WITH p AS MATERIALIZED ("
            f"  SELECT TRY_CAST(fiscal_year AS INT) AS fy, upper(contract_id) AS k, "
            f"         TRY_CAST(check_amount AS DOUBLE) AS amt, issue_date "
            f"  FROM read_parquet({files}) "
            f"  WHERE contract_id IS NOT NULL AND fiscal_year IS NOT NULL "
            f"    AND upper(contract_id) IN (SELECT unnest(?::VARCHAR[]))"
            f"), y AS ("
            f"  SELECT fy, COALESCE(SUM(amt), 0) AS paid, COUNT(*) AS payments, "
            f"         COUNT(DISTINCT k) AS contracts FROM p GROUP BY fy"
            f") SELECT "
            f"  (SELECT list({{'fy': fy, 'paid': paid, 'payments': payments, "
            f"                 'contracts': contracts}} ORDER BY fy) FROM y), "
            f"  (SELECT list(DISTINCT k) FROM p), "
            f"  (SELECT MAX(issue_date) FROM p WHERE issue_date <= ?)",
            [list(norm_ids), time.strftime("%Y-%m-%d")],
        ).fetchone()
    finally:
        con.close()
    return (list(row[0] or []), list(row[1] or []), row[2]) if row else ([], [], None)


_spend_populating = False


async def _spend_by_year(rows: list) -> dict:
    """NON-BLOCKING accessor. Returns the cached series when fresh, otherwise starts a
    one-shot background scan and reports `pending`.

    ⚠⚠ MEASURED, AND THE REASON THIS IS NOT AWAITED: with the scan on the request
    path, a cold `/oce/licenses` went **1.9s -> 17.8s** over HTTP — past the 15s
    timeout in `ProcurementController`, so the whole page would have fallen back to
    "License analysis is not available right now" on the first load after every
    restart (including the 04:00 cron). The in-process measurement was 4.9s and did
    NOT surface that: the api's persistent DuckDB connection, the 18-partition glob
    and the container's memory cap are all outside a bare `duckdb.connect()`.
    **Time the endpoint over HTTP, not the function.**

    Same shape as `oce._get_digital_spend_map`, for the same reason.
    """
    global _spend_populating
    c = _SPEND_CACHE
    if c["data"] is not None and (time.time() - c["ts"]) < _SPEND_TTL:
        return c["data"]
    if not _spend_populating:
        _spend_populating = True
        asyncio.create_task(_populate_spend_by_year(rows))
    # ⚠ `pending` is NOT the same as `available: false`: the page says the payments
    # are still loading rather than silently omitting a section, and the awarded
    # chart — pure Postgres — renders either way.
    return {"available": False, "pending": True,
            "reason": "the payment scan is still running"}


async def _populate_spend_by_year(rows: list) -> None:
    global _spend_populating
    try:
        out = await _build_spend_by_year(rows)
        if out.get("available"):
            _SPEND_CACHE["data"], _SPEND_CACHE["ts"] = out, time.time()
        logger.info("[licenses] spend-by-year ready (%d years)", len(out.get("years") or []))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[licenses] spend-by-year failed: %s", exc_str(exc))
    finally:
        _spend_populating = False


async def _build_spend_by_year(rows: list) -> dict:
    """What the City actually PAID against these licence contracts, per fiscal year.

    ⚠⚠ THIS IS A FLOOR, NOT THE LICENCE BILL, and the page has to say so. Payments
    are keyed on the contract id, and a CITYWIDE MASTER agreement is not what
    agencies pay against — they raise their own purchase orders, which carry their
    own ids. Measured: 161 of 1,601 contracts have no payment at all and they carry
    $749.3M (42%) of the awarded value, led by the **$573.8M Citywide Microsoft ELA
    at zero payments**, while the City has in fact paid DELL MARKETING $1,857.5M
    across 29,822 contract ids. The money is emphatically there; it is not under
    this id. `coverage` carries every figure needed to state that, and names the
    largest unmatched contract rather than leaving a reader to hunt for the reason
    a percentage is low.

    ⚠ SUM(check_amount) is deliberately NOT deduplicated. 666 of 8,273 rows are
    exact duplicates and an earlier draft of this work "corrected" for them —
    scored against `checkbook_contract_meta.spent_to_date`, which is CheckbookNYC's
    OWN per-contract figure, the plain sum matches on 159 of 183 contracts and
    every dedup rule tried is worse (155, 152, 104). The apparent duplication is
    how Checkbook accounts, and the plain sum is also what the contract page, the
    vendor profile and the queue's utilisation flag already publish — a different
    rule here would make this chart disagree with all three.

    ⚠ The current fiscal year is EXCLUDED from `years` and reported in `partial`,
    never dropped: a partial year renders as a collapse, and `_by_year` on this
    same page has already been through the version where rows fell into a gap
    nothing reconciled. `years` + `partial` + `dropped` == `total_all`, and a test
    pins it.

    ⚠ Runs in the BACKGROUND (see `_spend_by_year`), so it may take as long as the
    lake needs without touching the page's response time.
    """
    # ⚠ Keyed on the NORMALIZED id, which is what the lake can be matched on — and
    # two contract_ids can normalize together, so take the larger value rather than
    # adding them: `rows` is already one row per contract_id, so a sum here would
    # double a contract that merely dashes differently.
    value_of, row_of = {}, {}
    for r in rows:
        k = str(r.get("normalized_contract_id") or "").upper()
        if not k:
            continue
        v = float(r.get("value") or 0)
        if v >= value_of.get(k, -1):
            value_of[k], row_of[k] = v, r
    ids = sorted(value_of)

    try:
        year_rows, paid_ids, as_of = await to_duckdb_thread(_scan_spend_by_year, ids)
    except Exception as exc:  # noqa: BLE001
        # Degrade to a hidden section, never to a wrong series.
        logger.warning("[licenses] spend-by-year scan failed: %s", exc_str(exc))
        return {"available": False, "reason": "the spending lake could not be read"}

    cur_fy = _fy_of(time.strftime("%Y-%m-%d")) or 0
    buckets = {}
    for y in year_rows:
        fy = int(y["fy"])
        buckets[fy] = {"year": fy, "fy": fy, "label": f"FY{fy}",
                       "paid": float(y["paid"] or 0),
                       "payments": int(y["payments"] or 0),
                       "contracts": int(y["contracts"] or 0)}
    # ⚠ The SAME window helper and the same constant as the award series, so the two
    # charts on this page cannot disagree about how far back it looks. A fiscal year
    # is labelled by its END year, so FY2017 begins in calendar 2016 — the two charts
    # therefore start in the same calendar year despite the different labels.
    years, partial, dropped = _window(buckets, cur_fy)

    paid = {str(k).upper() for k in paid_ids}
    unmatched = [k for k in ids if k not in paid]
    # ⚠ Name the largest contract with no payment. A bare "58% of value" invites
    # the reader to assume a matching bug; the answer is one $573.8M citywide
    # master, and saying so is the difference between a caveat and a mystery.
    biggest = None
    if unmatched:
        top = max(unmatched, key=lambda k: value_of[k])
        biggest = {"value": value_of[top],
                   "vendor": row_of[top].get("vendor_name") or "",
                   "title": row_of[top].get("contract_title") or ""}

    # ⚠⚠ THE ANSWER TO "IS THIS A MATCHING FAILURE?", MEASURED AND SERVED. Split by
    # id kind, all 29 master agreements have zero payments under their own id while
    # 1,440 of 1,572 ordinary contracts have them — so the gap is not a failed join,
    # it is what a master agreement IS. Computed per row, never typed, because the
    # counts move whenever the inventory does.
    kinds = {}
    for k, v in value_of.items():
        cid = row_of[k].get("contract_id")
        b = kinds.setdefault("master" if _is_master(cid) else "contract",
                             {"kind": "master" if _is_master(cid) else "contract",
                              "contracts": 0, "value": 0.0, "paid_contracts": 0,
                              "paid_value": 0.0})
        b["contracts"] += 1
        b["value"] += v
        if k in paid:
            b["paid_contracts"] += 1
            b["paid_value"] += v

    total_value = sum(value_of.values())
    out = {
        "available": bool(years or partial),
        "years": years,
        # The fiscal year in progress. Reported, not rendered as a bar.
        "partial": partial,
        "total": sum(y["paid"] for y in years),
        "total_all": (sum(y["paid"] for y in years) + sum(y["paid"] for y in partial)
                      + sum(y["paid"] for y in dropped)),
        "dropped": {"paid": sum(y["paid"] for y in dropped),
                    "payments": sum(y["payments"] for y in dropped),
                    "before": (cur_fy - _WINDOW_YEARS)},
        "as_of": as_of,
        "current_fy": cur_fy,
        "window_years": _WINDOW_YEARS,
        "coverage": {
            "contracts": len(ids),
            "contracts_paid": len(paid & set(ids)),
            "value": total_value,
            "value_paid_contracts": sum(v for k, v in value_of.items() if k in paid),
            "unmatched_contracts": len(unmatched),
            "unmatched_value": sum(v for k, v in value_of.items() if k not in paid),
            "largest_unmatched": biggest,
            # master vs ordinary contract — the shape of the gap
            "by_kind": sorted(kinds.values(), key=lambda b: -b["value"]),
        },
    }
    # ⚠ The CACHE IS WRITTEN BY THE CALLER (`_populate_spend_by_year`), and only when
    # the scan actually produced years. Writing it here would cache an empty result
    # from a lake hiccup for a full day.
    return out


@router.get("/family/{slug}")
async def family(slug: str):
    """One product family, at its own stable URL.

    ⚠ Resolves by SLUG, not by display name. The slug is assigned at build time
    and is collision-free and order-stable, so a family URL keeps pointing at
    the same product across rebuilds. Matching on the display name would break
    every link the moment a curated rule renamed a family.
    """
    data = await _load()
    if not data.get("available"):
        return {"available": False, "reason": data.get("reason", "unavailable")}

    rows = [r for r in data["rows"] if (r.get("slug") or "") == slug]
    if not rows:
        # Fall back to matching the display name, so a link still resolves when
        # the family table is absent and every row carries an empty slug.
        rows = [r for r in data["rows"] if (r.get("family") or "") == slug]
    if not rows:
        return {"available": False, "reason": "no such family", "slug": slug}

    name = rows[0].get("family") or slug
    desc = (data.get("descriptions") or {}).get(name) or {}
    fam_class = (data.get("classes") or {}).get(name) or {}
    fam_cands = (data.get("candidates") or {}).get(name) or []

    # ⚠ THIS FAMILY'S OWN CLASS MIX, resolved at product grain. A family can hold
    # more than one kind of purchase — Microsoft is a $573.8M licence plus $68.9M
    # of support — and the header used to show only the family-level answer, which
    # asked the wrong question of the smaller part.
    prod_classes = data.get("product_classes") or {}
    class_mix, dominant = licenseclass.mix(rows, prod_classes, data.get("classes") or {})
    for a in class_mix:
        a["families"] = len(a["families"])
        a["products"] = sorted(a["products"])
        # `tiers` is a set and would not serialise; `tier` already summarises it.
        a.pop("tiers", None)
    # ⚠ Dominant by VALUE, not contract count: Microsoft's support tail is 16 of 23
    # contracts and 10.7% of the money, so counting rows would hand the headline
    # lever to the smaller purchase.
    dom = next((a for a in class_mix if a["key"] == dominant), None)
    # Per-contract class, so the page can show which rows carry which lever
    # instead of implying one applies to all of them.
    for r in rows:
        res = licenseclass.resolve(r.get("product"), r.get("family"),
                                   prod_classes, data.get("classes") or {})
        r["purchase_class"] = res["class"]
        r["purchase_lever"] = res["lever"]
        r["class_source"] = res["source"]
        r["class_tier"] = res["tier"]
    dom_source = next((r["class_source"] for r in rows
                       if r.get("purchase_class") == dominant), "")

    # ⚠ REPLACEABILITY IS THE WEAKEST FIELD ON THIS PAGE, so it is reported as a
    # DISTRIBUTION, never as a verdict. Two independent reasons:
    #   * cross-model agreement on build_vs_buy was only 75% (vs 98% for
    #     tech_relevant) on a 40-contract sample;
    #   * the classifier contradicts ITSELF -- 64 of 435 families carry more
    #     than one rating across their own contracts.
    # A single confident "Replaceability: HIGH" would hide both.
    bvb = {}
    for r in rows:
        k = (r.get("build_vs_buy") or "").strip().lower()
        if k:
            bvb[k] = bvb.get(k, 0) + 1
    ranked = sorted(bvb.items(), key=lambda kv: -kv[1])
    notice_rows, notice_total = await _notices_for_family(name)
    agencies = sorted(_agg(rows, "agency").values(), key=lambda a: -a["value"])
    vendors = sorted(_agg(rows, "vendor_name").values(), key=lambda a: -a["value"])
    products = sorted({r["product"] for r in rows if r.get("product")})

    # ⚠⚠ THE PAGE AND THE INDEX USED TO GIVE TWO ANSWERS UNDER ONE HEADING.
    # "Vendors selling it" here counted only the family's CONTRACT vendors --
    # Microsoft read 6 -- while the index's "Bought through" cell for the same
    # family read 32 (6 contract + 26 notice-only), because that column merges
    # the City Record awarded-to names in through modules/resellers. Both were
    # right about their own question and the reader could not tell.
    # ⭐ ONE OWNER, both surfaces: the same merge, so the two counts cannot drift.
    # A notice-only name is marked, never dropped -- it holds no contract in this
    # set, which is a weaker claim than a paid relationship and a real one.
    # ⚠⚠ THE TYPED "88.0%" WAS STILL LIVE ON THIS PAGE. `_reviewed()`'s own
    # docstring records that exact sentence as the defect it was written to
    # remove -- and it was removed from the INDEX and never swept here, so the
    # family view went on rendering "the largest 20 product families -- 88.0% of
    # the value in this analysis -- have been reviewed by hand" whenever a class
    # was unreviewed. Measured 2026-09-18: the top 20 are 76.0% of value and the
    # curated class seed covers 99 families carrying 90.6%. Wrong in both halves,
    # sitting beside figures this page computes. A guard that reads one file
    # measures one file.
    all_fams = [f for f in _agg(data["rows"], "family").values()
                if not f.get("is_generic")]
    reviewed = _reviewed(all_fams, data.get("classes") or {},
                         sum(f["value"] for f in all_fams))

    # ⭐ WHAT ELSE THE CITY BUYS FOR THIS JOB -- the families sharing this one's
    # function tag. This needs no new claim and no seed: the capability tag IS
    # the City's own observed alternative set, and it has been one click away
    # and unlabelled since the function view was built. A reader asking "what
    # else could we use?" was being sent to a generic link instead of shown the
    # answer.
    # ⚠ DERIVED from the same rows the capability page aggregates, so the two
    # cannot disagree -- verify_family_page reconciles the count against that
    # page. The family itself is excluded; peers_total counts BEFORE the cap.
    maker_row = (data.get("makers") or {}).get(name)

    # ⚠⚠ `other` IS AN ABSTENTION, NOT A FUNCTION, and rendering its members as
    # peers was measured before it shipped: LexisNexis is tagged `other`, so this
    # band would have offered **155 "other products that do this job"** led by a
    # call-centre service, a research subscription and a traffic-data feed. They
    # share no function with legal research and with each other; what they share
    # is that the classifier declined to name one. A family that abstains gets no
    # peers band at all -- we cannot say what else does a job we have not
    # identified, and a confident wrong list is worse than the omission.
    peers, peers_total = [], 0
    if fam_class.get("capability") and fam_class["capability"] != _OTHER_CAPABILITY:
        cap_key = fam_class["capability"]
        classes_all = data.get("classes") or {}
        peer_rows = [r for r in data["rows"]
                     if (classes_all.get(r.get("family") or "") or {})
                     .get("capability") == cap_key]
        others = [a for a in _agg(peer_rows, "family").values()
                  if a["key"] != name and not a.get("is_generic")]
        peers_total = len(others)
        peers = sorted(others, key=lambda a: -a["value"])[:10]

    # ⭐ OTHER FAMILIES BY THE SAME MAKER. The maker seed already knows that
    # Casebuilder and SoundThinking (ShotSpotter) are one company, and that the
    # City's AT&T Vehicle Tracking runs on the platform its separate Geotab
    # contracts buy -- and until now each page stated its own half and neither
    # pointed at the other. A reader comparing two lines had to hold the
    # relationship in their head.
    # ⚠ KEYED ON THE CURATED MAKER STRING, never on a name similarity. These
    # families stay UNMERGED on purpose -- merging would assert one product
    # identity the contract data does not carry -- so this is a cross-reference
    # and nothing sums across it.
    same_maker = []
    if maker_row and (maker_row.get("maker") or "").strip():
        mk = maker_row["maker"].strip()
        fam_by_slug = {f["key"]: f for f in all_fams}
        for other_fam, other_row in (data.get("makers") or {}).items():
            if other_fam == name:
                continue
            if (other_row.get("maker") or "").strip() != mk:
                continue
            f = fam_by_slug.get(other_fam)
            if not f:
                continue
            same_maker.append({
                "family": other_fam, "slug": f.get("slug", ""),
                "value": f["value"], "contracts": f["contracts"],
                # ⚠ The other family's OWN maker_kind, not this one's: AT&T
                # Vehicle Tracking is a `bundle` built on Geotab's product while
                # Geotab is the `company`, and the pair reads wrong if both
                # carry one label.
                "maker_kind": other_row.get("maker_kind") or "company",
            })
        same_maker.sort(key=lambda a: -a["value"])

    notice_res, _res_meta = await _notice_resellers()
    sellers = resellers.merge([v["key"] for v in vendors],
                              notice_res.get(name),
                              # ⚠ The index's NAME_CAP is a table CELL's cap. This
                              # is a section; folding 26 names into "+26 more"
                              # hides the finding the merge exists to surface.
                              cap=60)

    return {
        "available": True,
        "family": name,
        "slug": slug,
        "is_generic": bool(rows[0].get("is_generic")),
        "curated": bool(rows[0].get("fam_curated")),
        # The raw spellings merged into this family. Shown on the page so a
        # reader can see exactly what was combined and object if it is wrong --
        # the merge is a claim, and an unreviewable claim is the thing to avoid.
        "products": products,
        # What KIND of purchase this is, and therefore which question to ask.
        # ⚠ A `software-licence` class is the ONLY one for which build-vs-buy is a
        # meaningful question; everything else gets its lever instead.
        # ⚠ This is now the class that dominates the family BY VALUE, resolved at
        # product grain — not a single family-level label. `class_mix` carries the
        # rest, and `class_mixed` says whether one label is the whole story.
        "purchase_class": dominant or fam_class.get("class", ""),
        "capability": fam_class.get("capability", ""),
        # ⚠ Served, not mapped in the view -- this was the THIRD copy of the
        # capability label map. See _capability_labels().
        "capability_label": _capability_labels().get(
            fam_class.get("capability", ""), fam_class.get("capability", "")),
        "lever": (dom or {}).get("lever") or fam_class.get("lever", ""),
        "class_mix": class_mix,
        "class_mixed": len(class_mix) > 1,
        # Where the dominant class came from: a product override or the family.
        "class_source": dom_source,
        # ⚠ WAS IT REVIEWED? On a published page a reader must be able to tell a
        # hand-held classification from an automatic one, exactly as
        # `summary_curated` already does for the description. 'curated' | 'auto' |
        # 'mixed' | ''.
        "class_tier": (dom or {}).get("tier", ""),
        # ⚠ Shown BESIDE the spend, never divided into it: no seat/site count
        # exists, so the denominator would have to be invented.
        # ⚠ Unregistered purchasing vehicles whose TITLE names this product --
        # e.g. Salesforce reads $3.1M in licences here while a $75M "CITYWIDE
        # SALESFORCE PURCHASING CONTRACT" sits unregistered and invisible. A
        # title match is a weak but CHECKABLE link (the page shows the title it
        # matched), and it is the only link available: these rows have no
        # contract_id, so they were never classified and carry no product field.
        # Never added to this family's value.
        "pipeline_vehicles": _pipeline_for_family(name, data.get("pipeline") or []),
        "rate_card": (data.get("rate_cards") or {}).get(name),
        "class_why": fam_class.get("why", ""),
        "candidates": fam_cands,
        "catalogue": data.get("catalogue") or {},
        "summary_text": desc.get("summary", ""),
        "summary_curated": desc.get("curated", False),
        # The distinct purposes recorded on the contracts, shown under the
        # summary as the evidence it was generated from -- so a reader can
        # check the summary rather than take it on trust.
        "recorded_purposes": sorted({r["purpose"] for r in rows if r.get("purpose")}),
        "replaceability": {
            "counts": dict(bvb),
            "ranked": [{"rating": k, "contracts": v} for k, v in ranked],
            "top": ranked[0][0] if ranked else "",
            # True when this product's own contracts disagree.
            "mixed": len(bvb) > 1,
            "rated": sum(bvb.values()),
        },
        "summary": {
            "contracts": len(rows),
            "value": sum(r["value"] for r in rows),
            "expiring": sum(1 for r in rows if r["expiring"]),
            "expiring_value": sum(r["value"] for r in rows if r["expiring"]),
            "agencies": len(agencies),
            "vendors": len(vendors),
            "non_competitive": sum(1 for r in rows if r["no_competition"]),
            # Annualised, over only the contracts whose term is usable.
            "per_year": sum(r["per_year"] for r in rows if r.get("per_year")) or None,
            "per_year_basis": sum(1 for r in rows if r.get("per_year")),
        },
        "agencies": agencies,
        "vendors": vendors,
        # The merged seller rollup: contract vendors plus notice-only names, with
        # counts measured on the full sets. `vendors` above still carries the
        # per-vendor figures a contract vendor has and a notice-only name cannot.
        "sellers": sellers,
        # ⚠ Who makes it, or None. Curated only -- there is no automatic tier for
        # this claim, so an absent row means the page says "not yet identified"
        # rather than guessing at a named company.
        "maker": maker_row,
        # Other families this same company makes. A cross-reference, never a
        # merge: nothing on either page sums across it.
        "same_maker": same_maker,
        # The other products the City buys to do this family's job. `peers_total`
        # is measured on the unsliced set so the page can say "top N of M"
        # instead of presenting a capped list as the whole of it.
        "peers": peers,
        "peers_total": peers_total,
        # How much of the analysis has been hand-reviewed, COMPUTED. The page
        # states it when THIS family's class is not, so "not reviewed" reads as a
        # position in a programme rather than as neglect.
        "reviewed": reviewed,
        "by_year": _by_year(rows),
        "by_method": sorted(_agg(rows, "procurement_method").values(),
                            key=lambda a: -a["contracts"]),
        "contracts": sorted(rows, key=lambda r: -r["value"]),
        # City Record notices whose body names this product. ⚠ `notices_total` is
        # measured on the UNSLICED set, so the page can say "top N of M" instead
        # of presenting a capped list as the whole of it — the `by_vendor` defect
        # (25 of 88 rows under a heading implying all of them).
        "notices": notice_rows,
        "notices_total": notice_total,
    }


@router.get("/capability/{cap}")
async def capability(cap: str):
    """The products that do one job, and the agencies buying them.

    ⚠ This is the click the consolidation view was missing. Naming a function as
    fragmented and then dead-ending is worse than not naming it -- the reader
    cannot act on "32 network-security products" without seeing which 32."""
    data = await _load()
    if not data.get("available"):
        return {"available": False, "reason": data.get("reason", "unavailable")}
    classes = data.get("classes") or {}
    rows = [r for r in data["rows"]
            if (classes.get(r.get("family") or "") or {}).get("capability") == cap]
    if not rows:
        return {"available": False, "reason": "no such function", "capability": cap}

    fams = _agg(rows, "family")
    descs = data.get("descriptions") or {}
    for f in fams.values():
        f["summary"] = (descs.get(f["key"]) or {}).get("summary", "")
        f["purchase_class"] = (classes.get(f["key"]) or {}).get("class", "")
    return {
        "available": True,
        "capability": cap,
        # ⚠ Served, not mapped in the view. See _capability_labels().
        "label": _capability_labels().get(cap, cap),
        "summary": {
            "products": len(fams),
            "contracts": len(rows),
            "value": sum(r["value"] for r in rows),
            "agencies": len({r.get("agency") for r in rows if r.get("agency")}),
            "vendors": len({r.get("vendor_name") for r in rows if r.get("vendor_name")}),
        },
        "products": sorted(fams.values(), key=lambda a: -a["value"]),
        "agencies": sorted(_agg(rows, "agency").values(), key=lambda a: -a["value"]),
        "contracts": sorted(rows, key=lambda r: -r["value"])[:200],
    }


def _finish_tiers(rows):
    """Collapse each row's tier SET to one label, `mixed` when it holds more than
    one. Shared by the overlap rows so the rule has one spelling here too."""
    out = []
    for a in rows:
        b = dict(a)
        t = {x for x in (b.pop("tiers", None) or set()) if x}
        b["tier"] = (next(iter(t)) if len(t) == 1 else ("mixed" if t else ""))
        out.append(b)
    return out


_CONTENT_CLASS = "content-subscription"
_UNTAGGED_CAPABILITY_LABEL = "Not yet tagged"
# ⚠ A contract whose agency is blank is NOT an agency called "Other" — it is a
# row we cannot attribute. Named so a reader cannot mistake it for a body.
_UNNAMED_AGENCY = "Agency not recorded"


@router.get("/data")
async def data_lens():
    """"What data does the City buy?" — the section plan's §5c Phase A lens.

    TWO questions, deliberately never one total:

      A. what the City buys AS DATA — the `content-subscription` purchase class,
         i.e. somebody else's data or content, rented by subscription;
      B. what it buys to WORK WITH data — the capability tags the vocabulary
         marks `data_lens = analyse`.

    ⚠⚠ THEY OVERLAP, AND THE OVERLAP IS THE HEADLINE. Measured on prod
    2026-09-14: the section's own function table files **Cyclomedia ($20.00M)**
    and **Sanborn Maps ($3.12M)** under *Geospatial / GIS* — so **$23.1M of the
    $38.5M GIS figure, 60%, is aerial and street-level imagery the City BUYS,
    not a tool it licenses to analyse data.** The real GIS tool on that row,
    Esri ArcGIS, is $13.35M. The plan's own §5c would have published "$38.5M of
    licensed analytics platforms" and been wrong about three fifths of it.

    So every tool row carries TWO figures — `content_*` and `tool_*` — which sum
    to the SAME `value` the Products page's function table already publishes, and
    this payload serves NO key that adds the two halves together. That is #294's
    ceiling-vs-committed rule at a new surface: two columns, labelled, never
    added.

    ⚠ The class is resolved through modules/licenseclass at PRODUCT grain, the
    same one owner the rollup and the drill-down use. Re-deriving it here is how
    a lens comes to disagree with the table it was reached from.
    """
    data = await _load()
    if not data.get("available"):
        return {"available": False, "reason": data.get("reason", "unavailable")}
    rows = data["rows"]
    classes = data.get("classes") or {}
    prod_classes = data.get("product_classes") or {}
    labels = _capability_labels()
    lens = _data_lens_caps()

    def res(r):
        return licenseclass.resolve(r.get("product"), r.get("family"),
                                    prod_classes, classes)

    def cls(r):
        return res(r)["class"]

    def cap_of(r):
        return (classes.get(r.get("family") or "") or {}).get("capability") or ""

    # ---- A. bought as data/content -------------------------------------------
    crows = [r for r in rows if cls(r) == _CONTENT_CLASS]
    cfam = _agg(crows, "family")
    descs = data.get("descriptions") or {}
    for f in cfam.values():
        f["summary"] = (descs.get(f["key"]) or {}).get("summary", "")
        f["capability"] = ""
    # One family can only carry one capability tag (closed vocabulary), so read
    # it once per family rather than per row.
    for r in crows:
        f = cfam.get(r.get("family") or "")
        if f is not None and not f["capability"]:
            f["capability"] = cap_of(r)
    for f in cfam.values():
        f["capability_label"] = (labels.get(f["capability"], f["capability"])
                                 if f["capability"] else _UNTAGGED_CAPABILITY_LABEL)
    cvalue = sum(r["value"] for r in crows)

    # ⚠⚠ WHAT KIND OF CONTENT, because "content" is not "data". 42 of these 216
    # contracts are COURSE LIBRARIES (LinkedIn Learning, Pluralsight, Skillsoft),
    # which nobody asking "what data does the City buy?" means. By VALUE they are
    # 3% and by CONTRACT COUNT a fifth — both populations are served here rather
    # than one being implied, because the two answers differ by 7x.
    kinds = {}
    for r in crows:
        k = cap_of(r)
        a = kinds.setdefault(k, {"key": k, "contracts": 0, "value": 0.0,
                                 "families": set()})
        a["contracts"] += 1
        a["value"] += r["value"]
        a["families"].add(r.get("family") or "")
    for a in kinds.values():
        a["families"] = len(a["families"])
        a["label"] = (labels.get(a["key"], a["key"]) if a["key"]
                      else _UNTAGGED_CAPABILITY_LABEL)
    # ⚠ `other` and untagged sort LAST regardless of size, and they are kept
    # APART: "classified, function not identifiable" and "never classified" are
    # different claims, and folding them together would report an unanswered
    # question as an answered one.
    by_kind = sorted(kinds.values(),
                     key=lambda a: (a["key"] in ("", _OTHER_CAPABILITY),
                                    -a["value"]))

    # ⚠⚠ WHICH HALF THIS COUNTS IS THE WHOLE QUESTION, and it is the CONTENT
    # half — what the City buys AS data. The two halves of this lens OVERLAP by
    # design ($23.2M over 4 contracts), so an agency breakdown spanning both
    # would be the one sum this page exists to refuse. Built from `crows`, the
    # same rows `by_kind` and `content.value` are built from, so it closes on
    # `content.value` exactly rather than approximately.
    # ⚠ Served UNCAPPED, with its own total. A consumer that shows the top few
    # has to fold the rest into a labelled remainder and can then reconcile
    # against `content.value`; capping HERE would serve a subset under a name
    # that reads like the whole, which is the defect this section already paid
    # for on `by_vendor` (25 of 408 under a heading implying all of them).
    ag = {}
    for r in crows:
        name = (r.get("agency") or "").strip()
        a = ag.setdefault(name, {"key": name or _UNNAMED_AGENCY,
                                 "named": bool(name),
                                 "contracts": 0, "value": 0.0,
                                 "families": set()})
        a["contracts"] += 1
        a["value"] += r["value"]
        a["families"].add(r.get("family") or "")
    # ⚠ An unnamed agency sorts LAST however big it is, on the same reasoning as
    # `other` in by_kind: "we do not know whose spend this is" is not a peer of
    # a named agency and must not outrank one.
    # ⚠ THE SAME TWO-TIER RESOLVER the agency listing and the org profile use —
    # imported rather than re-spelled, because a third rule for "which org is
    # this agency" is exactly what left DoITT unresolved on one surface while it
    # resolved on another.
    # ⚠⚠ THE MODULE, IMPORTED AT MODULE LEVEL — never the other router, and never
    # a late import inside this function. A cross-router import couples the two
    # routers' test fixtures; and `conftest.py` replaces the whole `modules`
    # package with a MagicMock, so an import evaluated at CALL time binds the
    # MOCK and `await` raises. Both were measured here, in that order.
    # ⚠⚠ AND IT GROUPS BY THE ORGANISATION, NOT THE PUBLISHED STRING. DCAS is
    # filed under two spellings, so this list carried it twice — $34.70M in a
    # named wedge with $1.42M of the same organisation inside the remainder —
    # while both rows linked to one profile. `families` goes through `set_keys`
    # because a distinct count cannot be added; it becomes a length afterwards.
    # ⚠ The unnamed bucket is held OUT of the merge rather than trusted not to
    # resolve. Its key is prose ("Agency not recorded"), so it matching an org
    # name is only unlikely — and "we do not know whose spend this is" must never
    # be folded into an agency that is known.
    _unnamed = [a for a in ag.values() if not a["named"]]
    by_agency = await agencyalias.group_by_org(
        PostgresModelAsync, [a for a in ag.values() if a["named"]],
        "key", ["contracts", "value"], logger,
        label_key="value", set_keys=("families",))
    for a in _unnamed:
        a["org_id"] = None
        a["spellings"] = [a["key"]]
    by_agency = by_agency + _unnamed
    for a in by_agency:
        a["families"] = len(a["families"])
        a["contracts"] = int(a["contracts"])
    by_agency = sorted(by_agency, key=lambda a: (not a["named"], -a["value"]))

    # ---- B. bought to work with data -----------------------------------------
    tools = {}
    for r in rows:
        cap = cap_of(r)
        if cap not in lens:
            continue
        a = tools.setdefault(cap, {"key": cap, "label": labels.get(cap, cap),
                                   "contracts": 0, "value": 0.0,
                                   "content_contracts": 0, "content_value": 0.0,
                                   "tool_contracts": 0, "tool_value": 0.0,
                                   "agencies": set(), "products": set(),
                                   "families": {}})
        a["contracts"] += 1
        a["value"] += r["value"]
        side = "content" if cls(r) == _CONTENT_CLASS else "tool"
        a[f"{side}_contracts"] += 1
        a[f"{side}_value"] += r["value"]
        if r.get("agency"):
            a["agencies"].add(r["agency"])
        fam = r.get("family") or ""
        if fam:
            a["products"].add(fam)
            fa = a["families"].setdefault(fam, {"key": fam, "value": 0.0,
                                                "contracts": 0, "slug": r.get("slug") or "",
                                                "is_content": False})
            fa["value"] += r["value"]
            fa["contracts"] += 1
            fa["is_content"] = fa["is_content"] or side == "content"
    for a in tools.values():
        a["agencies"] = len(a["agencies"])
        a["products"] = len(a["products"])
        a["families"] = sorted(a["families"].values(), key=lambda f: -f["value"])[:6]
    tool_rows = sorted(tools.values(), key=lambda a: -a["value"])

    # ---- the overlap, named ---------------------------------------------------
    ov = [r for r in rows if cap_of(r) in lens and cls(r) == _CONTENT_CLASS]
    ofam = {}
    for r in ov:
        k = (r.get("family") or "", cap_of(r))
        a = ofam.setdefault(k, {"family": k[0], "capability": k[1],
                                "capability_label": labels.get(k[1], k[1]),
                                "slug": r.get("slug") or "",
                                "contracts": 0, "value": 0.0, "tiers": set()})
        a["contracts"] += 1
        a["value"] += r["value"]
        # ⚠⚠ THE PAGE'S STRONGEST CLAIM RESTS ON THESE ROWS, so it must say
        # whether a human made the judgement. Measured on prod 2026-09-14: the
        # two rows carrying $23.1M of the $23.2M overlap are BOTH `curated`, and
        # the third ($0.05M) is automatic. That is the difference between a
        # finding and a suggestion, and the section already carries a banner
        # saying which one this page is by default. ⚠ SERVED, never typed.
        a["tiers"].add(res(r)["tier"] or "")

    ov_rows = sorted(_finish_tiers(ofam.values()), key=lambda a: -a["value"])

    return {
        "available": True,
        "content": {
            "class": _CONTENT_CLASS,
            "contracts": len(crows),
            "value": cvalue,
            "families": len(cfam),
            "agencies": len({r.get("agency") for r in crows if r.get("agency")}),
            "vendors": len({r.get("vendor_name") for r in crows if r.get("vendor_name")}),
            "expiring": sum(1 for r in crows if r["expiring"]),
            "rows": sorted(cfam.values(), key=lambda a: -a["value"]),
            "by_kind": by_kind,
            # Who is buying it. See the note where this is built: CONTENT half
            # only, uncapped, and it sums to `value` above.
            "by_agency": by_agency,
            # ⚠ Reuses the page's own concentration helper so this figure cannot
            # disagree with the identical claim on the Products page.
            # ⚠ Reported in the helper's OWN buckets (1/3/5/10/20). A bespoke
            # "top 8" figure would be a second definition of the same claim, and
            # a constant nothing else consumes is how a seed comes to be inert.
            "concentration": _concentration(list(cfam.values()), cvalue),
            # ⚠⚠ THE PLAN'S §5c SAID "every row already tier-curated". MEASURED
            # ON PROD 2026-09-14 THAT IS FALSE: 11 of 100 families are curated,
            # carrying 87.5% of the value. Both halves of that are worth saying
            # and neither implies the other — by money this view is reviewed, by
            # product count 89% of it is automatic. Through the page's OWN
            # _reviewed() so the claim cannot drift from the seed, and so this
            # figure and the Products page's are one definition.
            "reviewed": _reviewed(list(cfam.values()), classes, cvalue),
        },
        "tools": {
            "rows": tool_rows,
            # ⚠⚠ TWO TOTALS, NEVER ONE, and no key here adds them. Their sum is
            # not a quantity anybody can act on: it counts imagery bought as data
            # alongside the licence to read it.
            "tool_contracts": sum(a["tool_contracts"] for a in tool_rows),
            "tool_value": sum(a["tool_value"] for a in tool_rows),
            "content_contracts": sum(a["content_contracts"] for a in tool_rows),
            "content_value": sum(a["content_value"] for a in tool_rows),
            "capabilities": sorted(lens),
        },
        "overlap": {
            "contracts": len(ov),
            "value": sum(r["value"] for r in ov),
            # ⚠ A row aggregating two tiers reports `mixed` rather than picking
            # one — claiming review for a partly-reviewed row is the harmful
            # direction, the same rule licenseclass.mix() already applies.
            # ⚠ ONE pass, reused. Calling _finish_tiers twice would be two
            # computations of one thing sitting in one dict literal, which is
            # the shape that lets a rendered list and its own total drift.
            "rows": ov_rows,
            "curated_value": sum(a["value"] for a in ov_rows
                                 if a["tier"] == "curated"),
        },
        # Provenance, on the page's own terms: this lens adds no new judgement,
        # it reads two curated layers the section already publishes.
        "provenance": {
            "class_source": "license_family_class / license_product_class (curated + auto)",
            "lens_source": "api/seed/license_capability_vocab.csv (data_lens)",
        },
    }

@router.get("/contracts")
async def contracts(family: str = "", agency: str = "", expiring: str = "",
                    purchase_class: str = Query("", alias="class"),
                    sort: str = "value", limit: int = 200):
    """Contract-level rows, optionally scoped to one family, agency or class.

    This is what a family row on the page links to, and every row carries the
    contract_id the frontend turns into a /procurement/contract/{id} link.

    ⚠ `class` is the purchase class, resolved through modules/licenseclass at
    PRODUCT grain with a family fallback -- the same resolver the rollup uses.
    Re-deriving it here (or worse, in SQL) would let the drill-down disagree with
    the table it was reached from, which is the entire reason that module exists.
    """
    data = await _load()
    if not data.get("available"):
        return {"available": False, "rows": [], "total": 0}
    rows = data["rows"]
    if family:
        rows = [r for r in rows if (r.get("family") or "") == family]
    if agency:
        rows = [r for r in rows if (r.get("agency") or "") == agency]
    if purchase_class:
        prod_classes = data.get("product_classes") or {}
        fam_classes = data.get("classes") or {}
        rows = [r for r in rows
                if licenseclass.resolve(r.get("product"), r.get("family"),
                                        prod_classes, fam_classes)["class"]
                == purchase_class]
    if expiring in ("1", "true", "yes"):
        rows = [r for r in rows if r["expiring"]]
    keys = {
        "value": lambda r: -r["value"],
        "end": lambda r: (r.get("end_date") or "")[-4:] or "9999",
        "agency": lambda r: (r.get("agency") or ""),
        "product": lambda r: (r.get("product") or ""),
    }
    rows = sorted(rows, key=keys.get(sort, keys["value"]))
    total = len(rows)
    return {
        "available": True, "total": total, "family": family, "agency": agency,
        "class": purchase_class,
        "value": sum(r["value"] for r in rows),
        # ⚠ Report the cap explicitly. A silently truncated list reads as a
        # complete one -- the "no silent caps" rule this codebase already has.
        "truncated": total > limit,
        "rows": rows[:limit],
    }


@router.get("/capabilities/export")
async def capabilities_export():
    """The cross-agency function view as CSV.

    ⚠ This is the most novel table on the page -- "how many different products do
    we buy to do one job, in how many agencies" is the consolidation question, and
    it is the one an advocate most wants to take away. Only the contract-level
    export existed, so the one view nobody else publishes was the one view you
    could not download.
    """
    data = await _load()
    if not data.get("available"):
        return Response("error,no license data\n", media_type="text/csv")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["function", "function_label", "distinct_products", "agencies",
                "contracts", "value", "flagged_worth_consolidating"])
    for a in _capability_rollup(data["rows"], data.get("classes") or {}):
        w.writerow([a["key"], a["label"], a["products"], a["agencies"],
                    a["contracts"], round(a["value"], 2),
                    "yes" if a["fragmented"] else "no"])
    return Response(
        buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="nyc-software-by-function.csv"'})


@router.get("/export")
async def export():
    """Contract-level CSV, matching what the page shows."""
    data = await _load()
    if not data.get("available"):
        return Response("error,no license data\n", media_type="text/csv")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["contract_id", "family", "product", "purpose", "agency", "vendor_name",
                "award_amount", "current_amount", "start_date", "end_date",
                "expiring_before_2030", "procurement_method", "competitively_bid",
                "ai_model", "unidentified_product"])
    for r in sorted(data["rows"], key=lambda x: -x["value"]):
        w.writerow([r.get("contract_id"), r.get("family"), r.get("product"),
                    r.get("purpose"), r.get("agency"), r.get("vendor_name"),
                    r.get("award_amount"), r.get("current_amount"),
                    r.get("start_date"), r.get("end_date"),
                    "yes" if r["expiring"] else "no", r.get("procurement_method"),
                    "yes" if r["competitive"] else "no", r.get("ai_model"),
                    "yes" if r.get("is_generic") else "no"])
    return Response(
        buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="nyc-software-licenses.csv"'})
