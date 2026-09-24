"""`contracts.agency` -> `wegov_orgs` id, for the strings exact matching cannot reach.

⚠⚠ WHY. `oce.py::_resolve_org_id` matches the agency string against
`wegov_orgs.name` / `alternate_name` by EXACT upper/trim equality, deliberately:
its own docstring says a fuzzy match "could deep-link an agency to the wrong org
profile". That caution is correct — see below — but it left 11 of 46 distinct
agency strings resolving to nothing: **3,838 contracts, $23,171.9M**, measured
2026-09-01. The consequence was worse than a missing hyperlink: querying an
agency by its CURRENT name returned "0 contracts" for agencies holding billions,
and a zero reads as "this agency has no contracts" rather than "your string did
not match ours".

⚠⚠ CURATED, NEVER FUZZY, AND THE MEASUREMENT IS THE ARGUMENT. Nearest-neighbour
trigram similarity gets the two LARGEST strings WRONG:

    0.44  DEPARTMENT OF INFORMATION TECHNOLOGY AND TELECOMMUNICATIONS ($7.4B)
          -> "Department of Records and Information Services"     ** different agency **
    0.52  DCASDIVISION OF MUNICIPAL SUPPLY SERVICE ($8.0B)
          -> "Municipal Division of Transitional Services"        ** different agency **

A threshold set anywhere useful would confidently misfile **$15.4B** — the two
biggest items. Eleven curated rows are a morning's work; a similarity score here
is a liability. Same rule as #148 and the DOS crosswalk: an ambiguous name stays
unlinked rather than pointing at an arbitrary entity.

⚠ This is a MAPPING layer. It must never rewrite `contracts.agency` — those are
the upstream PASSPort values and CheckbookNYC parity may depend on them.
"""
import csv
import os

_SEED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     'seed', 'agency_org_aliases.csv')

_rows = None
_by_agency = None


def key(agency_name) -> str:
    """The lookup key. Folded identically on both sides — a different folding
    here would silently resolve nothing, which is the defect this module exists
    to remove. Collapses internal whitespace so a double space cannot miss."""
    return ' '.join((agency_name or '').split()).upper()


def _load(logger=None):
    """⚠ Skips `#` comment lines — every file in api/seed/ carries a comment
    header, and a parser that does not expect one reads the header as a data row
    (that exact bug shipped once in the NYCHA seed)."""
    global _rows, _by_agency
    if _rows is not None:
        return _rows
    try:
        with open(_SEED, newline='', encoding='utf-8') as fh:
            rows = list(csv.DictReader(l for l in fh if not l.lstrip().startswith('#')))
    except Exception as exc:  # noqa: BLE001
        # ⚠ ERROR, not warning: an absent seed silently restores the $23.2B blind
        # spot, and an empty map is indistinguishable from "every agency resolves".
        # Degrade rather than raise — a missing seed must cost hyperlinks, never
        # take down every org profile.
        if logger:
            logger.error("agency alias seed unreadable (%s): %s", _SEED, exc)
        _rows, _by_agency = [], {}
        return _rows
    _rows = [r for r in rows if (r.get('agency') or '').strip()
             and str(r.get('wegov_org_id') or '').strip().isdigit()]
    _by_agency = {key(r['agency']): int(r['wegov_org_id']) for r in _rows}
    return _rows


def rows(logger=None):
    _load(logger)
    return list(_rows)


def org_id_for(agency_name, logger=None):
    """The org id a stored `contracts.agency` string names, or None."""
    _load(logger)
    return _by_agency.get(key(agency_name))


async def resolve_many(pg, agency_names, logger=None):
    """{stored agency string: org id} for MANY names — the WHOLE two-tier rule.

    ⚠⚠ THIS IS THE ONE OWNER, and it exists because a THIRD spelling had
    already shipped. `oce._resolve_org_id` did exact-then-alias for ONE name,
    this module did the alias tier, and `/oce/agencies` carried its OWN inline
    correlated subquery that never consulted the seed at all — so the curated
    rows mapping DoITT -> OTI, DCASDIVISION -> DCAS and NEW YORK CITY POLICE
    DEPARTMENT -> Police Department were bypassed on the surface consumers read.
    Measured 2026-09-16 before the fix: **7 of 182** master-agreement rows
    resolved, and every large agency missed.

    ⚠ TIER ORDER IS LOAD-BEARING: an exact match WINS, so the seed can only add
    resolution where there was none and can never move an agency that already
    resolved. Same order as the single-name path, which now delegates here.

    ⚠ ONE query, not one per name — callers resolve whole tables, and a per-row
    await is the correlated-subquery cost this repo measured at 1,165ms against
    4.9ms for the uncorrelated form.

    ⚠ `ORDER BY id` + `setdefault` so the LOWEST id wins, byte-identical to the
    single-name path's `ORDER BY id LIMIT 1`. Both `Public Design Commission`
    rows share a name and only the id ordering keeps the live one winning.
    """
    names = [n for n in {(x or "").strip() for x in (agency_names or [])} if n]
    if not names:
        return {}
    from modules import orgfilter
    live = await orgfilter.live_clause(lambda sql: pg.select_safe(sql, []), "AND", "")
    rows = await pg.select_safe(
        """
        SELECT id, UPPER(TRIM(name)) AS n, UPPER(TRIM(COALESCE("alternate_name",''))) AS a
        FROM wegov_orgs
        WHERE (UPPER(TRIM(name)) = ANY($1)
           OR UPPER(TRIM(COALESCE("alternate_name",''))) = ANY($1)){live}
        ORDER BY id
        """.replace("{live}", live),
        [[n.upper() for n in names]],
    ) or []
    by_upper = {}
    for r in rows:
        for k in (r.get("n"), r.get("a")):
            if k:
                by_upper.setdefault(k, r["id"])
    out = {}
    for n in names:
        hit = by_upper.get(n.upper())
        if hit is None:
            hit = org_id_for(n, logger)
        if hit is not None:
            out[n] = hit
    return out


def agency_strings_for_term(term, logger=None):
    """Stored `contracts.agency` strings a user's search TERM should also reach.

    This is the reverse direction, and it is what makes
    `search_contracts(agency="Technology and Innovation")` return the 1,381
    contracts filed under "DEPARTMENT OF INFORMATION TECHNOLOGY AND
    TELECOMMUNICATIONS" instead of zero.

    ⚠ TWO MATCHING RULES, and the split is deliberate. An acronym is matched
    EXACTLY against the `aka` list; only names of 4+ characters are matched as a
    substring. A substring match on a 3-letter token is not a measurement in this
    repo — `%UI%` matches BUILDING and `%ABA%` matches DATABASE — and "OTI" or
    "DCA" inside a longer word would drag in unrelated agencies.
    """
    _load(logger)
    t = ' '.join((term or '').split()).strip()
    if not t:
        return []
    tu = t.upper()
    out = []
    for r in _rows:
        akas = [a.strip().upper() for a in (r.get('aka') or '').split(';') if a.strip()]
        hit = tu in akas                                   # exact: acronyms
        if not hit and len(tu) >= 4:                       # substring: real names only
            hit = (tu in (r.get('org_name') or '').upper()
                   or tu in (r.get('agency') or '').upper())
        if hit:
            out.append(r['agency'])
    return out


# ---------------------------------------------------------------------------
# The OTHER shape: tables the normalizer has already mapped.
#
# ⭐ `nycjobs` and `payrolldata` need NO seed, and building one would have been
# the wrong fix. Both carry a `wegov-org-id` stamped at ingest, and measured
# 2026-09-02 it is complete and valid: 59/59 job agencies and 170/170 payroll
# agencies resolve to a LIVE org, 0 dangling. It even AGREES with the curated
# contracts map above — jobs "TECHNOLOGY & INNOVATION" -> 170010858, payroll
# "CONSUMER AFFAIRS" -> 170010866. `contracts` has no such column (it is an
# extractor table, not normalizer-processed), which is precisely why the seed
# above exists and this does not.
#
# ⚠⚠ THE GAP IS LARGER HERE THAN IN CONTRACTS, and in the same reassuring
# direction. Measured against each agency's own canonical org name:
#     nycjobs      36 of 59 agencies unreachable   2,075 of 2,923 postings (71%)
#     payrolldata 136 of 170 agencies unreachable  4,929,787 of 6,775,830 rows (73%)
# `DEPT OF ED PEDAGOGICAL` alone is 1,315,181 rows, and the Department of
# Education is split across FIVE payroll strings — so searching the canonical
# name missed nearly three million DOE rows.
#
# ⚠ IT ALSO UNIFIES, which is a real behaviour change and not a side effect:
# filtering by org id gathers those five DOE strings (and the CUNY community
# colleges) under one agency, so totals GROW. That is the intent — but a caller
# wanting one payroll sub-agency still gets it, because the raw ILIKE is kept.
_ORG_TERM_MAX = 12

_ORG_SQL = """
    SELECT id::text AS id FROM wegov_orgs
    WHERE retired_at IS NULL
      AND (upper(trim(coalesce(alternate_name, ''))) = upper(trim($1))
           OR (length(trim($1)) >= 4
               AND (name ILIKE $2 OR coalesce(display_name, '') ILIKE $2)))
    LIMIT 200
"""


async def org_ids_for_term(pg, term, logger=None):
    """Live org ids a search TERM names, for tables carrying `wegov-org-id`.

    ⚠ SAME TWO MATCHING RULES as agency_strings_for_term: an acronym matches
    EXACTLY against alternate_name, and only terms of 4+ characters match a name
    as a substring. A substring match on a short token is not a measurement here.

    ⚠⚠ CAPPED AT _ORG_TERM_MAX, AND THE CAP FAILS SAFE. A generic word is not an
    agency name: measured, "office" matches 117 live orgs and "department" 50,
    while real agency terms are small ("education" 10, "sanitation" 6). Above the
    cap this returns [] and the caller falls back to its raw ILIKE — i.e. exactly
    today's behaviour — so the cap can only ever reduce this feature's reach and
    can never broaden a search into nonsense or break one that already worked.
    """
    t = ' '.join((term or '').split())
    if not t:
        return []
    try:
        rows = await pg(_ORG_SQL, [t, f"%{t}%"])
    except Exception as exc:  # noqa: BLE001
        # Degrade to the raw ILIKE rather than raising: an org lookup failing must
        # cost the expansion, never the search. ERROR, not warning — silently
        # losing the expansion restores a 73% blind spot.
        if logger:
            logger.error("org id lookup failed for %r: %s", t, exc)
        return []
    ids = {r['id'] for r in (rows or []) if r.get('id')}

    # ⚠ THE SEED'S `aka` LIST FEEDS THIS ROUTE TOO, so a term that works on
    # contracts works on jobs and payroll. Measured: the register's
    # alternate_name for OTI is the LEGACY acronym "DOITT", so the exact-acronym
    # arm above resolves DOITT and NOT "OTI" -- the current one. Without this the
    # two mechanisms would disagree about the same agency, which is the shape of
    # defect this whole area exists to remove.
    ids |= {str(_by_agency[key(a)]) for a in agency_strings_for_term(term, logger)
            if key(a) in _by_agency}

    out = sorted(ids)
    return [] if len(out) > _ORG_TERM_MAX else out


# ---------------------------------------------------------------------------
# GROUPING: one organisation is one row.
#
# ⚠⚠ THE DEFECT THIS EXISTS FOR. Every agency chart in the procurement section
# groups on the PUBLISHED STRING and then links by the RESOLVED ORG — two
# identities, and the City publishes more strings than it has agencies. Measured
# 2026-09-16 over all 46 distinct `contracts.agency` values, exactly two
# organisations are carried by two strings each:
#
#     DCAS   "DCASDIVISION OF MUNICIPAL SUPPLY SERVICE"        1,111  $8,734.1M
#            "DEPARTMENT OF CITYWIDE ADMINISTRATIVE SERVICES"  1,322  $1,585.1M
#     MOCJ   "OFFICE OF CRIMINAL JUSTICE (128)"                  218  $1,986.4M
#            "OFFICE OF CRIMINAL JUSTICE (002)"                  531  $1,702.5M
#
# So `/procurement/agencies` listed DCAS twice, both rows linking to the SAME
# org profile and neither showing its total; and the Digital Services Overview's
# "Value by agency" pie took its top 8 BEFORE merging, which published DCAS at
# $190.7M (rank 8) with a further $109.9M of the same organisation folded into
# the grey "3 others" — a 36.6% understatement of the seventh-largest agency.
#
# ⭐ MERGING ADDS NO CLAIM. Both strings already resolve to one org id through
# the curated seed, and every one of these surfaces already links them to one
# profile — so the merge asserts exactly what the page asserts. NOT merging is
# what publishes a contradiction: two rows saying "two agencies" above two
# identical hyperlinks saying "one". The seed says so in its own words for the
# pair it curated: *"The AGENCY named is the same in both, which is the grain
# this map resolves."*
# ⭐ And this module's payroll half already settled the same question the other
# way round — "it ALSO UNIFIES, which is a real behaviour change and not a side
# effect ... totals GROW. That is the intent."
#
# ⚠ UNRESOLVED ROWS NEVER MERGE WITH EACH OTHER. A missing org id means "we do
# not know which organisation this is", which is not evidence that two such
# strings are the same one — the same discipline as `resolve_many` leaving an
# ambiguous name unlinked rather than pointing it at an arbitrary entity.
# ⚠ AND THE CAP MUST COME AFTER. A `LIMIT 8` in SQL cuts the split rows, so the
# merge can no longer see the tail it needs — which is how $109.9M ended up
# inside "3 others". Count before you cap, this repo's oldest display rule.


async def org_names(pg, org_ids, logger=None):
    """{org id: the name that org's OWN PAGE titles itself with}.

    ⚠ `coalesce(display_name, name)`, because that is `Organizations::dispName()`
    — so a merged row's label is byte-identical to the title a reader lands on.
    The capital section paid for this rule once already: a link whose label does
    not match its destination reads as a link to somewhere else.
    """
    ids = sorted({int(i) for i in (org_ids or []) if i is not None})
    if not ids:
        return {}
    rows_ = await pg.select_safe(
        "SELECT id, COALESCE(NULLIF(TRIM(COALESCE(display_name,'')),''), name) AS n "
        "FROM wegov_orgs WHERE id = ANY($1)", [ids]) or []
    return {r["id"]: r["n"] for r in rows_ if r.get("n")}


async def group_by_org(pg, rows_in, name_key, sum_keys, logger=None,
                       label_key=None, set_keys=()):
    """Merge agency rows that name ONE organisation. Returns NEW dicts.

    Each returned row carries `org_id` (may be None) and `spellings`, the list of
    published strings it covers — served so a consumer can disclose a merge and
    so a guard can see one happened.

    ⚠⚠ `set_keys` EXISTS BECAUSE A COUNT OF DISTINCT THINGS CANNOT BE ADDED. The
    data lens carries a per-agency count of product FAMILIES; summing two groups'
    counts double-counts every family both agencies buy. Pass the still-unreduced
    sets here, union them, and let the caller take the length afterwards.

    ⚠ THE LABEL RULE IS CONDITIONAL, and deliberately so. A group of ONE keeps
    the publisher's own string, so 44 of the 46 agencies read exactly as they
    always have and this section keeps PASSPort's vocabulary. Only a MERGED group
    is relabelled, with the organisation's registered name — because labelling a
    merged row with one of its parts would read as if the other part had been
    left out, which is the opposite of what happened.

    ⚠ SO A MERGED LABEL IS TITLE CASE among UPPERCASE ones, and that is left
    visible on purpose. PASSPort publishes its agency names in caps and the
    register does not; the case difference is the one honest marker that this row
    is ours rather than the publisher's, and shouting it to match would claim a
    published spelling that does not exist. `/procurement/agencies` names the
    covered spellings underneath; the chart legends rely on the label matching
    the org page's own title, which is the rule that matters more there.

    ⚠ ORDER IS THE CALLER'S. Rows come back in the input order of whichever row
    gave the group its size, because a merge can only move a row up and every
    caller sorts differently (`/oce/agencies` by name, count or amount).
    """
    rows_in = list(rows_in or [])
    if not rows_in:
        return []
    lk = label_key or (sum_keys[0] if sum_keys else None)
    omap = await resolve_many(pg, [r.get(name_key) for r in rows_in], logger)

    groups, order = {}, []
    for i, r in enumerate(rows_in):
        nm = (r.get(name_key) or "").strip()
        oid = omap.get(nm)
        # ⚠ An unresolved row is its OWN group, keyed on its position, so two
        # unknown strings can never be folded together.
        gk = ("org", oid) if oid is not None else ("row", i)
        g = groups.get(gk)
        if g is None:
            g = groups[gk] = {"rows": [], "org_id": oid, "pos": i, "best": None}
            order.append(gk)
        g["rows"].append(r)

    merged_ids = [g["org_id"] for g in groups.values()
                  if g["org_id"] is not None and len(g["rows"]) > 1]
    names = await org_names(pg, merged_ids, logger) if merged_ids else {}

    out = []
    for gk in order:
        g = groups[gk]
        members = g["rows"]
        best = max(members, key=lambda r: _num(r.get(lk))) if lk else members[0]
        row = dict(best)
        for k in (sum_keys or []):
            row[k] = sum(_num(r.get(k)) for r in members)
        for k in (set_keys or ()):
            u = set()
            for r in members:
                u |= set(r.get(k) or ())
            row[k] = u
        row["org_id"] = g["org_id"]
        row["spellings"] = [(r.get(name_key) or "").strip() for r in members]
        if len(members) > 1:
            row[name_key] = names.get(g["org_id"]) or best.get(name_key)
        out.append((g["pos"], row))
    out.sort(key=lambda t: t[0])
    return [r for _, r in out]


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0
