"""Group contracts into PROGRAMMES — task `2eba1fce` (b), shape B.

    docker compose exec -T api python build_program_groups.py              # report
    docker compose exec -T api python build_program_groups.py --worksheet  # review queue
    docker compose exec -T api python build_program_groups.py --apply      # write

WHAT THIS IS FOR
================
NYC's PASSPort procurement system is **11 contracts, 9 vendors, 2 agencies,
$67.29M** (measured on prod 2026-08-27) and nothing in the product connects
them. The renewal queue shows Ivalua's $37.9M platform licence as one row, with
no indication that Accenture's $24.0M maintenance contract for the same system
expires on the same day. A program is the missing grain.

⚠⚠ MEMBERSHIP IS A CURATED DECISION. ONLY `curated` ROWS RENDER.
================================================================
This is #146 made structural for a third time, and it is the whole safety
argument. `contract_program` also stores `auto` candidate rows so the review
worksheet has something to propose — but a consumer joins on `tier='curated'`
and therefore *cannot* publish an unreviewed grouping by omission.

A program page makes a far stronger claim than the contract page's
co-termination block does. That block's own copy is the standard this must meet:

    "Contracts that expire together are often one program — but a shared end
     date is not evidence that they are."

So co-termination may PROPOSE a program and may never ASSERT one.

⚠⚠ THE TWO SIGNALS HAVE DIFFERENT JOBS, AND THE SCOPE DOC ONLY MEASURED ONE
===========================================================================
`docs/PROGRAM-GROUPING-SCOPE.md` measured both signals as *expanders* against
the worked example, and concluded they are complementary. Re-measured here as
*discoverers* on 2026-08-27, and the asymmetry is much sharper than that:

  signal          as EXPANDER (given the program)   as DISCOVERER (unprompted)
  title token     10/11 members, ZERO false pos       1,767 candidates, useless
  co-termination   1/11 members (the platform)        59 reviewable groups

**The title token cannot discover.** Gated to 3-40 contracts, >=2 vendors and
>=$5M it still admits 1,767 tokens, and ranked by value the head of that list is
`QFAC` `MFAC` `MARITIME` `COMMERCIAL` `HOTELS` `CAMERA` `ENHANCED` `COST` —
generic nouns and abbreviation fragments. `PASSPORT` (10 contracts, 8 vendors,
$29.4M) sits far below them with nothing to distinguish it. There is no ranking
that floats the real program above the noise, so an unsupervised token pass
would hand a reviewer 1,767 rows to find one answer in.

**Co-termination cannot expand**, because 6 of the 11 PASSPort contracts end on
06/30 — the fiscal-year boundary this repo excludes outright, for the reason
`_related_contracts` documents (the largest 06/30 group is 4,721 contracts).

So the roles are split, and each signal is used only where it was measured
strong:

    DISCOVERY  = the co-termination worksheet   (--worksheet, 59 groups)
    EXPANSION  = a curated `token` rule          (zero measured false positives)
    MEMBERSHIP = the seed, always

⚠ SCOPE: DISCOVERY IS TECH-ONLY, MEMBERSHIP IS NOT
==================================================
The worksheet is scoped to `digital_contract_enrichment.tech_relevant` because
that is the universe the section covers and it is what makes 59 groups the size
of the queue rather than thousands.

**Membership must NOT be tech-gated**, and the worked example is the proof:
`CT1-002-20268801915` (IN OUR SHOES LLC, $498,500, *"DISCRETIONARY SUPPORT
SERVICES FOR THE ADOPTION OF PASSPORT"*) is classified `tech_relevant = false`.
It is unambiguously part of the PASSPort program — adoption support for the
system — and a tech-gated membership pass silently drops it, taking the
program from 11 contracts / $67.29M to 10 / $66.79M. A program is a thing
the City is doing, not a classification of its contracts.

⚠ GRAIN — the #262/#278 key, third surface
==========================================
`contracts` holds ONE ROW PER AMENDMENT (55,806 rows for 36,421 contract_ids)
and every amendment carries its own `ctr_id`. Everything here dedupes on
`coalesce(contract_id, 'row:' || ctid::text)`, byte-identical to the key those
two PRs established. Amendments RESTATE a contract's total rather than adding to
it, so a program's value sums the deduped survivors — summing rows is exactly
the double-count that turned $61.9M into a reported $78.1M.

⚠ MONEY — committed and ceiling are never added
===============================================
`modules.contractkind` splits them, and the keys are named `value` and `ceiling`
so the second resists being summed into the first. This is #261/#294/#301 — the
same defect found three times — and a program total is precisely the kind of
figure it would corrupt. No master appears in the PASSPort program today
(all 11 are `CT`), so the split is currently 11/$67.29M committed and 0 ceiling;
it is computed anyway, because the first master to join must not silently land
in a figure captioned as spend.
"""

import argparse
import asyncio
import collections
import csv
import os
import re
import sys

import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

try:
    import contractkind
    import dbcreds
except ImportError:                                    # pragma: no cover
    from modules import contractkind, dbcreds

CURATED_CSV = os.environ.get(
    "PROGRAM_CURATED_CSV",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "seed", "program_curated.csv"))

# ⚠ THE DEDUP KEY. Not `ctr_id` — see the module docstring. Keying on
# `contract_id` alone would collapse every NULL-id row into one, and 2,546 rows
# carry no contract_id.
_CONTRACT_KEY = "coalesce(contract_id, 'row:' || ctid::text)"

# One row per contract, largest amendment surviving — the licences-page dedup
# (digitalscope._DERIVED_TABLE's semantics), plus one thing that rule is missing.
#
# ⚠⚠ THE FINAL `ctr_id` TIEBREAK IS NOT TIDINESS — WITHOUT IT THIS QUERY IS
# NON-DETERMINISTIC AND THE ANSWER MOVES BETWEEN RUNS. `DISTINCT ON` keeps the
# first row of each group and Postgres may order tied rows however it likes.
# Measured on prod 2026-08-27: **92 contract_ids have a TIE for the winning
# amendment row**, and of those
#     61 tied rows disagree on `end_date`
#     86 tied rows disagree on `contract_title`
#      0 disagree on `agency`
# So which end date and which title a contract "has" was being decided
# arbitrarily — and both are inputs here: the title drives token expansion and
# the end date drives the co-termination worksheet.
#
# This was found, not theorised. Two ad-hoc measurements of the SAME worksheet
# minutes apart returned **59 and 60 groups** (and 2,178 against the scope doc's
# 2,179 co-termination groups). The off-by-one was not a mistake in either
# query; it was this.
#
# ⚠ `ctr_id` rather than `ctid`: ctid is a physical row pointer and the
# extractor DROP+RENAMEs this table daily, so it is stable only within one run.
#
# ⚠ THE SAME SHAPE IS IN `digitalscope._DERIVED_TABLE` AND IN
# `oce._related_contracts`, both of which order by amount with no final
# tiebreak. Deliberately NOT changed here — they feed published figures across
# the whole Digital Services section and moving them belongs in its own change
# with its own before/after.
_DEDUP = f"""
SELECT DISTINCT ON ({_CONTRACT_KEY})
       contract_id, ctr_id, contract_title, vendor_name, agency,
       start_date, end_date,
       coalesce(current_amount, award_amount, 0) AS val
  FROM contracts
 ORDER BY {_CONTRACT_KEY},
          coalesce(current_amount, 0) DESC, coalesce(award_amount, 0) DESC,
          ctr_id
"""

# ── worksheet gates ────────────────────────────────────────────────────────
# Each is the rule `_related_contracts` already applies on the contract page,
# reused so the worksheet proposes only groups the product would be willing to
# show. Measured on prod 2026-08-27 over the tech universe:
#     2,178 non-06/30 (agency, end_date) groups
#       365 within the size cap
#       340 of those multi-vendor
#        59 of those over the value floor   <- the review queue
_WORKSHEET_MAX_GROUP = 10        # a program is a handful; 4,721 is a calendar
_WORKSHEET_MIN_VENDORS = 2       # single-vendor groups are already served by
                                 # `same_vendor` on the contract page
_WORKSHEET_MIN_VALUE = 5_000_000  # 59 groups; the licence work's "review 10, not
                                  # 432" discipline at a new grain

SCHEMA = """
CREATE TABLE IF NOT EXISTS contract_program (
    contract_id   text        NOT NULL,
    program_slug  text        NOT NULL,
    program_name  text        NOT NULL,
    tier          text        NOT NULL,
    signal        text,
    note          text,
    built_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (contract_id)
);
CREATE INDEX IF NOT EXISTS idx_contract_program_slug ON contract_program (program_slug);
CREATE INDEX IF NOT EXISTS idx_contract_program_tier ON contract_program (tier);
"""


def slugify(name: str) -> str:
    """Program name -> URL segment, matching build_license_families.slugify."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "unnamed"


def load_curated(path=None, log=None):
    """The seed, as {slug: {"name", "contracts", "tokens", "excludes", "notes"}}.

    ⚠ Parsed with `csv.reader`, never by splitting on commas: notes here are
    prose and contain them.

    ⚠⚠ A ROW THIS CANNOT PARSE USED TO VANISH IN SILENCE. Every `continue`
    below discards a line a human wrote on purpose — a rule column reading
    `contracts` instead of `contract`, a row truncated to three fields — and the
    curator's decision then simply does not apply, with nothing said. That is
    the seed-header defect from the NYCHA crosswalk in a new place: this file's
    whole purpose is applying human judgement, so losing one quietly is the
    worst thing it can do. Pass `log` and every skipped line is named.
    """
    path = path or CURATED_CSV
    progs = {}
    if not os.path.exists(path):
        if log:
            log(f"[program] ⚠ no curated seed at {path}")
        return progs
    with open(path, newline="", encoding="utf-8") as fh:
        for lineno, row in enumerate(csv.reader(fh), start=1):
            if not row or not (row[0] or "").strip():
                continue
            if row[0].lstrip().startswith("#") or row[0].strip() == "program_slug":
                continue
            if len(row) < 4:
                if log:
                    log(f"[program] ⚠ seed line {lineno} SKIPPED — only "
                        f"{len(row)} field(s), need 4: {row!r}")
                continue
            slug = (row[0] or "").strip()
            name = (row[1] or "").strip()
            rule = (row[2] or "").strip().lower()
            value = (row[3] or "").strip()
            note = (row[4] if len(row) > 4 else "").strip()
            if not slug or not value or rule not in ("contract", "token", "exclude"):
                if log:
                    log(f"[program] ⚠ seed line {lineno} SKIPPED — "
                        f"slug={slug!r} rule={rule!r} value={value!r}; rule must "
                        f"be one of contract/token/exclude")
                continue
            p = progs.setdefault(slug, {"name": name or slug, "contracts": [],
                                        "tokens": [], "excludes": [], "notes": {}})
            if name:
                p["name"] = name
            if rule == "contract":
                p["contracts"].append(value)
            elif rule == "token":
                p["tokens"].append(value.lower())
            else:
                p["excludes"].append(value)
            if note:
                p["notes"][value] = note
    return progs


def resolve_members(progs, rows, log=None):
    """Expand each program's rules over the deduped contract rows.

    Returns {slug: {contract_id: signal}} where signal is 'curated' (named
    explicitly), 'token' (matched a curated token) or 'both'.

    ⚠ EXCLUSIONS ARE APPLIED LAST AND WIN. A token rule is broad by
    construction, so the seed must be able to say "not that one" — and a
    rejection that a rebuild can overturn is not a rejection (#155).

    ⚠⚠ AND A RULE THAT MATCHES NOTHING IS REPORTED, because the two ways this
    can happen are both silent and both wrong:
      * a CURATED CONTRACT ID that is not in `rows` is dropped by
        `if cid in by_id`. The id may be a typo, or the contract may have left
        the technology universe, or an ingest may have removed it — and the
        program then renders with fewer members than the curator chose, with
        nothing said. `verify()` cannot see this: it checks rows that WERE
        written for orphans, which is the opposite direction.
      * an EXCLUDE that removes nothing is a rejection that is not happening.
        A typo there is worse than a typo in a contract rule, because the
        contract it was meant to remove stays IN.
    """
    by_id = {r["contract_id"]: r for r in rows if r.get("contract_id")}
    out = {}
    for slug, p in progs.items():
        members = {}
        for cid in p["contracts"]:
            if cid in by_id:
                members[cid] = "curated"
            elif log:
                log(f"[program] ⚠ {slug}: curated contract {cid} MATCHED NOTHING "
                    f"— it is not in the contract set, so this decision is not "
                    f"being applied")
        for tok in p["tokens"]:
            hits = 0
            for cid, r in by_id.items():
                if tok in (r.get("contract_title") or "").lower():
                    members[cid] = "both" if members.get(cid) == "curated" else "token"
                    hits += 1
            if not hits and log:
                log(f"[program] ⚠ {slug}: token {tok!r} matched 0 titles")
        for cid in p["excludes"]:
            if members.pop(cid, None) is None and log:
                log(f"[program] ⚠ {slug}: exclude {cid} removed NOTHING — the "
                    f"contract it names is not a member, so if that id is a typo "
                    f"the intended one is still included")
        out[slug] = members
    return out


def summarize(members, rows):
    """A program's published figures.

    ⚠ `value` and `ceiling` are separate keys and are NEVER added. See the
    module docstring: this is the defect #261, #294 and #301 each found.
    """
    by_id = {r["contract_id"]: r for r in rows if r.get("contract_id")}
    sel = [by_id[c] for c in members if c in by_id]
    committed, ceiling, n_c, n_ceil = contractkind.split_amounts(
        sel, amount=lambda r: r.get("val"),
        contract_id=lambda r: r.get("contract_id"))
    return {
        "contracts": len(sel),
        "vendors": len({(r.get("vendor_name") or "").strip() for r in sel if r.get("vendor_name")}),
        "agencies": len({(r.get("agency") or "").strip() for r in sel if r.get("agency")}),
        "value": committed,
        "ceiling": ceiling,
        "n_committed": n_c,
        "n_ceiling": n_ceil,
    }


async def fetch_rows(conn):
    return [dict(r) for r in await conn.fetch(_DEDUP)]


async def worksheet(conn, limit=60):
    """The DISCOVERY queue: co-terminating multi-vendor groups worth reviewing.

    ⚠ Scoped to the tech universe, unlike membership. See the module docstring
    for why those two scopes differ and what a tech-gated membership pass costs.

    ⚠ Already-curated contracts are NOT filtered out of the group listing: a
    partially-curated group is exactly what a reviewer needs to see, because the
    interesting question is which of its members are still unclaimed.
    """
    return [dict(r) for r in await conn.fetch(f"""
        WITH d AS ({_DEDUP}),
        tech AS (
            SELECT d.* FROM d
              JOIN digital_contract_enrichment e ON e.contract_id = d.contract_id
             WHERE e.tech_relevant IS TRUE
        )
        SELECT agency, end_date,
               count(*) AS nc,
               count(DISTINCT vendor_name) AS nv,
               sum(val::numeric) AS tv,
               array_agg(DISTINCT vendor_name) AS vendors
          FROM tech
         WHERE end_date IS NOT NULL AND end_date <> ''
           AND end_date NOT LIKE '06/30/%'
         GROUP BY agency, end_date
        HAVING count(*) BETWEEN 2 AND {_WORKSHEET_MAX_GROUP}
           AND count(DISTINCT vendor_name) >= {_WORKSHEET_MIN_VENDORS}
           AND sum(val::numeric) >= {_WORKSHEET_MIN_VALUE}
         ORDER BY sum(val::numeric) DESC
         LIMIT {int(limit)}
    """)]


async def build(conn, apply=False, log=print):
    progs = load_curated(log=log)
    rows = await fetch_rows(conn)
    log(f"[program] {len(rows)} contracts (deduped), "
        f"{len(progs)} curated program(s) from {CURATED_CSV}")
    if not progs:
        log("[program] no curated programs — nothing renders. This is the "
            "legitimate empty state, not a failure.")

    resolved = resolve_members(progs, rows, log=log)
    records = []
    for slug, members in sorted(resolved.items()):
        p = progs[slug]
        s = summarize(members, rows)
        log(f"[program] {slug} ({p['name']}): {s['contracts']} contracts / "
            f"{s['vendors']} vendors / {s['agencies']} agencies / "
            f"${s['value']:,.0f} committed"
            + (f" + ${s['ceiling']:,.0f} ceiling" if s["ceiling"] else ""))
        for cid, signal in sorted(members.items()):
            records.append((cid, slug, p["name"], "curated", signal,
                            p["notes"].get(cid) or p["notes"].get(slug)))

    # ⚠⚠ ONE CONTRACT, ONE PROGRAM — contract_program is PRIMARY KEY
    # (contract_id), so a contract claimed by two programs violates it and the
    # whole rebuild aborts inside its transaction. That was impossible while
    # there was a single curated program and became possible the moment there
    # were ten, so it is checked here rather than discovered as a raw
    # duplicate-key error deep in an insert loop.
    #
    # ⚠ It matters more than an ordinary crash because the post-ingest hook
    # SWALLOWS exceptions ("hook failed (non-fatal)"), so the visible outcome
    # would be a warning plus a contract_program table that silently keeps
    # yesterday's membership. Naming the two programs and the contract is what
    # turns that into something a curator can fix — with an `exclude` row.
    claimed = {}
    collisions = []
    for cid, slug, *_ in records:
        if cid in claimed and claimed[cid] != slug:
            collisions.append(f"{cid} is claimed by both {claimed[cid]!r} and {slug!r}")
        claimed[cid] = slug
    if collisions:
        for c in collisions:
            log(f"[program] ⚠⚠ COLLISION: {c}")
        raise ValueError(
            f"{len(collisions)} contract(s) claimed by more than one program; a "
            f"contract can belong to only one. Add an `exclude` row to whichever "
            f"program should not own it. First: {collisions[0]}")

    if not apply:
        log("[program] nothing written. Re-run with --apply.")
        return records, resolved

    # ⚠ THE DDL IS INSIDE THE TRANSACTION WITH THE WRITES. A dry run that
    # creates its own table is not dry — a documented lesson in this repo that
    # was then reproduced by the usage rollup, so it is spelled out here.
    async with conn.transaction():
        for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
            await conn.execute(stmt)
        # Curated membership is fully described by the seed, so a rebuild
        # REPLACES it rather than upserting — otherwise a contract removed from
        # the seed keeps its program forever, which is the NYCHA generator's
        # upsert-only defect (#149).
        await conn.execute("DELETE FROM contract_program")
        for rec in records:
            await conn.execute(
                "INSERT INTO contract_program "
                "(contract_id, program_slug, program_name, tier, signal, note, built_at) "
                "VALUES ($1,$2,$3,$4,$5,$6, now())", *rec)
    log(f"[program] wrote {len(records)} membership row(s)")
    return records, resolved


async def verify(conn, log=print):
    log("\n=== verification ===")
    leak = await conn.fetchval(
        "SELECT count(*) FROM contract_program WHERE tier <> 'curated'") or 0
    log(f"rows that are not curated: {leak}  (must be 0 — only curated renders)")
    orphan = await conn.fetchval("""
        SELECT count(*) FROM contract_program p
         WHERE NOT EXISTS (SELECT 1 FROM contracts c WHERE c.contract_id = p.contract_id)
    """) or 0
    log(f"rows naming a contract that does not exist: {orphan}  (must be 0)")
    for r in await conn.fetch(
            "SELECT program_slug, count(*) n FROM contract_program GROUP BY 1 ORDER BY 2 DESC"):
        log(f"    {r['program_slug']:<24} {r['n']}")


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write (default: report)")
    ap.add_argument("--worksheet", action="store_true",
                    help="print the co-termination review queue and exit")
    ap.add_argument("--show", action="store_true", help="list every member")
    args = ap.parse_args()

    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=dbcreds.password(),
        database=os.environ.get("POSTGRES_DB", "databook"))
    try:
        if args.worksheet:
            ws = await worksheet(conn)
            print(f"[program] {len(ws)} co-terminating groups to review "
                  f"(<= {_WORKSHEET_MAX_GROUP} contracts, >= {_WORKSHEET_MIN_VENDORS} "
                  f"vendors, >= ${_WORKSHEET_MIN_VALUE:,})\n")
            print(f"{'agency':<44} {'ends':<12} {'n':>3} {'vend':>4} {'$M':>9}")
            for g in ws:
                print(f"{(g['agency'] or '')[:43]:<44} {g['end_date']:<12} "
                      f"{g['nc']:>3} {g['nv']:>4} {float(g['tv'])/1e6:>9,.1f}")
            return
        print(f"[program] mode: {'APPLY' if args.apply else 'REPORT (pass --apply)'}\n")
        records, resolved = await build(conn, apply=args.apply)
        if args.show:
            rows = {r["contract_id"]: r for r in await fetch_rows(conn)}
            print("\n=== members ===")
            for cid, slug, _name, _tier, signal, _note in sorted(records, key=lambda x: x[1]):
                r = rows.get(cid, {})
                print(f"  {slug:<12} {signal:<8} {cid:<22} "
                      f"{float(r.get('val') or 0)/1e6:>8,.2f}M  "
                      f"{(r.get('vendor_name') or '')[:28]:<28} "
                      f"{(r.get('contract_title') or '')[:42]}")
        if args.apply:
            await verify(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())


async def derive_program_groups_hook(conn):
    """Rebuild program membership after a `contracts` ingest.

    Registered on `contracts` in data_scheduler.POST_INGEST_HOOKS. Membership is
    resolved against contract titles and ids, so it must be rebuilt whenever the
    contract table is — the extractor DROP+RENAMEs it daily.

    ⚠ VERIFIED THAT THIS TABLE'S HOOKS ACTUALLY RUN, rather than assuming it.
    A hook can be registered, correctly ordered and present in the live process
    and still never fire — that is what happened to crol for a month, because
    its importer bypasses the scheduler. Measured on prod 2026-08-27 the durable
    way, since the api log had rotated past the ingest: all seven declared
    indexes on `contracts` were present after the 04:01 DROP+RENAME, and
    `recreate_table_indexes` (hook[0] on this table) is the only thing that
    restores them. Their existence IS the evidence the hook ran.

    ⚠ Guarded end to end and ordered AFTER the index hook. This is additive —
    the contract page must render without it — so a failure logs and returns
    rather than failing the ingest that triggered it.
    """
    try:
        await build(conn, apply=True, log=lambda m: print(m))
    except Exception as exc:  # noqa: BLE001
        print(f"[program] hook failed (non-fatal): {exc}")
