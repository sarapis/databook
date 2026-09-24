"""Propose candidate PROGRAM NAMES from contract titles, then have a model judge them.

    docker compose exec -T api python build_program_name_candidates.py            # extract + report
    docker compose exec -T api python build_program_name_candidates.py --judge    # + LLM pass
    docker compose exec -T api python build_program_name_candidates.py --judge --apply

WHY THIS EXISTS, AND WHY IT IS NOT THE WORKSHEET
================================================
`build_program_groups.py --worksheet` proposes groups from CO-TERMINATION, which
was measured at **19% precision** on the one worked example: for PASSPort it
offered 4 real members alongside 17 coincidences. That is a fine way to find the
members a name MISSES and a poor way to discover programs.

This inverts it. A program is a NAMED thing the City buys for, so look for the
name. Measured over the 4,397-contract technology universe:

  * a **vendor** name clusters with ONE vendor by definition, so excluding tokens
    that appear in their own contract's vendor name separates `PASSPort`
    (Ivalua + Accenture + Genesys + SVAM) from `MOTOROLA` (Motorola only);
  * a **generic** procurement word is diverse in vendors AND agencies — measured,
    `INTEGRATION`/`Security`/`Training` span 14-24 agencies, while `PASSPort`
    and `MyCity` span 2. Agency CONCENTRATION plus vendor DIVERSITY is the
    discriminator, and it cut 1,192 raw candidates to 430.

⚠⚠ AND THEN STATISTICS RUN OUT, WHICH IS WHY THE MODEL IS HERE. Three scoring
functions were tried and none separates signal from noise, because *"is this the
name of a thing the City runs?"* is a SEMANTIC judgement:
    by vendor spread          -> swamped by INTEGRATION, Security, Training
    by vendors-per-agency     -> promotes LABOR GRADES (SP3, PM3, PRG3): many
                                 bodies fill one grade at one agency
    by value                  -> `MyCity` lands between `Handling` and `DTR`,
                                 and PASSPort ranks #66 of 344
Two noise classes ARE removable from data and are removed here rather than by a
typed list: agency acronyms (from the org register) and grade codes (a pattern).
What survives needs a reader.

⚠⚠ THIS WRITES CANDIDATES, AND A CANDIDATE CAN NEVER REACH A PAGE. Rows land in
`program_name_candidates` and NOTHING renders them. A name becomes a program only
when a human copies it into `api/seed/program_curated.csv`, which
`build_program_groups.py` reads and which is the only source of the `curated`
tier. That is #146's rule — made structural for the fourth time in this codebase,
after licence families, the org<->vendor crosswalk and the programme grouping
itself.

⚠ THE EXTRACTOR IS TITLE-ONLY AND THEREFORE UNDERSTATES MONEY. PASSPort's
extracted figure is $4.87M against the program's real $67.3M, because Ivalua's
title is *"Inc Alias/DBA: Ivalua Inc Renewal #1"* and never says PASSPort. Names
find the program; co-termination finds the members the name misses. The two
signals are complementary and neither is sufficient — which is the same
conclusion docs/PROGRAM-GROUPING-SCOPE.md reached from the other direction.
"""

import argparse
import asyncio
import collections
import csv
import io
import json
import os
import re
import sys

import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

try:
    import dbcreds
except ImportError:                                    # pragma: no cover
    from modules import dbcreds

# ⚠ SAME MODEL AND PRICES AS classify_digital_contracts.py, on purpose. That
# choice is MEASURED, not argued: flash-lite scored 95.8% / 97.5% against
# adjudicated labels at 16.4x less cost than flash. Judging a one-word candidate
# is a strictly easier task than classifying a contract, so the cheaper model is
# if anything better justified here.
# ⚠ No `google_search` tool anywhere in this file, which also sidesteps the
# documented trap that a lite model handed a search tool answers from RECALL
# with no grounding metadata. This is a judgement about supplied text, not a
# lookup, so nothing should be grounded.
MODEL = "gemini-3.1-flash-lite"
PRICES = {                                             # $/1M tokens (in, out)
    "gemini-3.5-flash":      (1.50, 9.00),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.1-flash-lite": (0.25, 1.50),
}
BATCH_SIZE = 25
USAGE = []

# Candidate gates, all measured on the 4,397-contract technology universe.
MIN_CONTRACTS = 2        # a name that appears once is a contract, not a program
MIN_VENDORS = 3          # a program outlives one supplier
MAX_AGENCIES = 3         # generics span 14-24; PASSPort and MyCity span 2
DF_CEILING = 0.05        # a token in >5% of contracts is procurement vocabulary

# ⚠ Named so a reporter can enumerate the gates rather than only the ones that
# happened to fire. A gate that removed nothing and a gate that is not
# implemented look identical in a list of what was removed — this repo's oldest
# defect, and DF_CEILING is currently a live instance: it removes 0 names,
# because after STOP the commonest surviving token appears in 94 contracts
# against a ceiling of 219. Inert, not broken, and worth being able to see.
GATE_NAMES = ("MIN_CONTRACTS", "MIN_VENDORS", "MAX_AGENCIES", "DF_CEILING")

STOP = set("""the and for of to in a an with on by from at or as is are be
service services contract contracts agreement renewal amendment extension change
order task purchase citywide city new york nyc department office bureau division
system systems software hardware maintenance support technical professional
consulting consultant management managed program manager analyst engineer
developer specialist senior junior associate inc llc corp corporation company ltd
lp co group holdings solutions technologies technology tech data information
project projects phase increase capacity acco dba alias misc miscellaneous
equipment supplies supply products product license licenses licensing subscription
annual yearly monthly rate card per unit various other general related existing
continuation using help surge preventive handling seekers one-year
""".split())

TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9&\.\-]{2,}")
# ⚠⚠ THIS PATTERN ATE A REAL NAME AND THE FIX IS NARROWER THAN IT LOOKS.
# It was `^[A-Z0-9\-]*\d{3,}`, meant to strip contract numbers like `84124P0012`
# and `7-858-0031A`. It also matched **NYC311** — the City's own flagship service
# — because that is three digits after letters. Found by testing the extractor
# against web-confirmed program names, not by reading the regex.
# Every real id in this corpus either STARTS with a digit or carries a run of 4+,
# so requiring one of those keeps NYC311 and NYC3 while still stripping every id
# shape measured (verified on 14 cases, 0 disagreements).
# ⚠ Second time a pattern here has hidden a good answer — the grade regex nearly
# killed NYC3. Both failed in the direction that is invisible without a recall
# test, which is why eval_program_names.py now exists.
ID_LIKE = re.compile(r"^\d|\d{4,}")

# ⚠⚠ THERE IS DELIBERATELY NO GRADE-CODE REGEX, AND REMOVING ONE IS WHY.
# Labor grades (SP3, PM3, PRG3) score highest on vendors-per-agency — many bodies
# fill one staffing grade at one agency — so an early draft excluded them with
# `^[A-Z]{1,4}[0-9]{1,2}$`. That pattern also matches **NYC3**, a real City system
# this extractor had just surfaced, and a guard caught it killing a known-good
# name. The lesson is the same one that put the model here at all: separating a
# grade from a system is a SEMANTIC judgement, and a regex attempting it fails in
# the direction that hides good answers. The model has a `labor_code` kind for
# exactly this, so the codes are CLASSIFIED rather than silently dropped — which
# also leaves them visible in the report instead of vanishing.

# ⚠⚠ ONE OWNER FOR THE KIND VOCABULARY. It was written in THREE places — the
# JSON enum below, the prose block in INSTRUCTION, and (wrongly) a hardcoded
# list in a Blade template that omitted `labor_code`, `agency` and `unclear`,
# so a reviewer could not amend a candidate to two of the eight kinds actually
# in the data (22 labor_code, 15 agency). That is the licence-capability defect
# exactly — a label map copied into a view and stale there — so the enum, the
# prompt and the review UI now all read from here.
#
# ⚠ The definitions are the ones the model is given, verbatim. A glossary that
# paraphrased them would describe a different classifier than the one that ran.
REJECTED_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "seed", "program_name_rejected.csv")


def rejected_names(path=None):
    """Normalised names a reviewer has judged NOT to be a program.

    ⚠⚠ THIS IS WHAT MAKES A REJECTION STICK. Without it a rejected candidate
    returns on every regeneration and the reviewer answers the same question
    forever — the failure the NYCHA crosswalk fixed with 110 no-match markers
    (#155), and the reason `reject` is a first-class verb rather than "just do
    not accept".

    ⚠ Keyed on `norm()`, the extractor's own normaliser, so one rejection covers
    every spelling the extractor would merge ("Real Time" also suppresses
    "REALTIME"). A raw-string match would leave the variant coming back.
    """
    path = path or REJECTED_CSV
    out = set()
    if not os.path.exists(path):
        return out
    with io.open(path, newline="", encoding="utf-8") as fh:
        for row in csv.reader(fh):
            if not row or not (row[0] or "").strip():
                continue
            first = row[0].strip()
            if first.startswith("#") or first == "name":
                continue
            out.add(norm(first))
    return out


KINDS = collections.OrderedDict([
    ("program",    "a named City initiative or service people would recognise"),
    ("system",     "a named IT system or platform"),
    ("vehicle",    "a procurement construct, not a thing being run\n"
                   "             (e.g. a \"Class 3\" citywide integration vehicle, a GSA schedule)"),
    ("commodity",  "a category of goods/services (laptops, cabling, fuel, parking)"),
    ("labor_code", "a staffing grade or job title (SP3, PM3, Program Manager)"),
    ("agency",     "an agency, bureau or office name/abbreviation"),
    ("vendor",     "a supplier's name or brand"),
    ("generic",    "an ordinary procurement or English word"),
    ("unclear",    "genuinely cannot tell from the evidence supplied"),
])

# ⚠ Only these two mean "this is a program name" — the gate `_is_program`
# enforces, and the reason the model is told so explicitly.
PROGRAM_KINDS = ("program", "system")

SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "kind": {"type": "string", "enum": list(KINDS)},
            "is_program_name": {"type": "boolean"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "why": {"type": "string"},
        },
        "required": ["name", "kind", "is_program_name", "confidence", "why"],
    }}},
    "required": ["results"],
}

INSTRUCTION = """You are reviewing candidate tokens pulled from New York City
government technology contract titles. For each candidate decide whether it is
the NAME OF A PROGRAM OR SYSTEM the City runs.

A PROGRAM/SYSTEM name is a proper noun for a thing the City buys FOR, where
contracts exist because that thing exists. Examples of the shape:
PASSPort (procurement system), MyCity (benefits portal), NYC3 (cyber command),
SCADA (control system), EMSCAD (EMS dispatch).

Set is_program_name = true ONLY for `program` and `system`.

Use these kinds, and prefer the most specific that fits:
__KIND_BLOCK__

You are given, per candidate: the token, how many contracts and distinct vendors
and agencies it appears in, total value, and up to 5 example contract titles.

⚠ JUDGE ONLY FROM THE EVIDENCE SUPPLIED. Do not use outside knowledge to assert
that something exists; if the titles do not support it, say `unclear` with
confidence `low`. A wrong `program` here costs a human a review; a missed one
costs nothing, because co-termination catches members a name misses.

`why` must be one short sentence citing what in the evidence decided it."""


# ⚠ Built FROM `KINDS` so the prompt cannot drift from the enum. Asserted
# byte-identical to the hand-written block it replaced by
# test_program_name_candidates.py — a prompt change is a behaviour change.
INSTRUCTION = INSTRUCTION.replace(
    "__KIND_BLOCK__",
    "\n".join(f"  {k:<10} {v}" for k, v in KINDS.items()))


def norm(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", t).upper()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS program_name_candidates (
    name_key      text PRIMARY KEY,
    display       text NOT NULL,
    n_contracts   integer NOT NULL,
    n_vendors     integer NOT NULL,
    n_agencies    integer NOT NULL,
    total_value   double precision NOT NULL,
    examples      text,
    kind          text,
    is_program    boolean,
    confidence    text,
    why           text,
    judged_model  text,
    built_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_prog_name_cand_is_program
    ON program_name_candidates (is_program);
"""


def hard_drop(raw, k, vend):
    """Noise that no surrounding context can rescue.

    ⚠ ONE OWNER, applied to a unigram AND to every half of a bigram. A second
    copy of these predicates would let a harness report the reasoning of a
    system that is not the one that ran — the org-crosswalk suffix-list defect,
    which I reproduced while measuring this very change by writing
    `ID_LIKE.match` in a throwaway where production says `.search`.
    """
    return bool(not k or len(k) < 3 or raw.lower() in STOP or k.isdigit()
                or ID_LIKE.search(raw.upper()) or k in vend)


def agency_token(k, agencies):
    """Agency vocabulary: noise ALONE, signal INSIDE a phrase.

    ⚠⚠ THIS DISTINCTION IS WHY BIGRAMS EXIST HERE, and collapsing it hides real
    programs silently. `HRA` alone is the Human Resources Administration and
    must not become a candidate. `ACCESS HRA` is the City's benefits platform —
    5 contracts, 5 vendors, 2 agencies, comfortably past every gate — and was
    invisible for exactly that reason.

    Three policies for what a bigram half may be, measured rather than argued —
    numbers from the shipped predicates over the 4,397-contract universe, on a
    unigram baseline of 347 candidates:
        drop if EITHER half would drop as a unigram -> + 67 bigrams, ACCESS HRA MISSED
        drop on hard_drop only, agency allowed      -> +127 bigrams, ACCESS HRA FOUND
        drop only if BOTH halves would drop         -> +282 bigrams, stop words leak
                                                       ("Voice and", "III Renewal")
    The middle one ships. It also recovers `DOB NOW`, `Fair Fares`, `MWBE NG911`
    and `NYC3 Threat` — every one a name containing a token that is correctly
    noise on its own.

    ⚠ The third policy is NOT simply the loosest, which is worth knowing before
    anyone "simplifies" toward it: it still tests both halves for agency
    vocabulary, so it LOSES `DOB NOW` while admitting the stop-word noise. And
    the reason is a good advertisement for not trusting a vocabulary you did not
    curate — `NOW` is agency vocabulary here because the org register contains
    *National Organization for Women*, which has nothing to do with the
    Department of Buildings' filing system.
    """
    return k in agencies


async def fetch_rows(conn):
    return await conn.fetch("""
        SELECT DISTINCT ON (c.contract_id)
               c.contract_id, coalesce(c.contract_title,'') t,
               coalesce(c.vendor_name,'') v, coalesce(c.agency,'') a,
               coalesce(c.current_amount, c.award_amount, 0) val
          FROM contracts c
          JOIN digital_contract_enrichment e ON e.contract_id = c.contract_id
         WHERE e.tech_relevant IS TRUE AND c.contract_id IS NOT NULL
         ORDER BY c.contract_id, coalesce(c.current_amount,0) DESC,
                  coalesce(c.award_amount,0) DESC, c.ctr_id""")


async def agency_vocab(conn, rows):
    """⚠ AGENCY VOCABULARY COMES FROM THE ORG REGISTER, not a list I typed. DCAS,
    DOT, ITT and friends otherwise score highest on vendor-diversity, because an
    agency abbreviation appears in many vendors' contract titles at one agency —
    exactly the shape this is trying to find.
    """
    agencies = set()
    for o in await conn.fetch("""SELECT coalesce(name,'') n, coalesce(alternate_name,'') a
                                   FROM wegov_orgs WHERE retired_at IS NULL"""):
        for fld in (o["n"], o["a"]):
            for w in TOKEN.findall(fld or ""):
                if len(w) >= 3:
                    agencies.add(norm(w))
    for r in rows:
        for w in TOKEN.findall(r["a"] or ""):
            if len(w) >= 3:
                agencies.add(norm(w))
    return agencies


def tally(rows, agencies):
    """Every one- and two-word name with its stats, BEFORE the gates.

    Kept separate from the gating so a caller can ask what was thrown away and
    why. A filter that hides a good answer is invisible; this is what makes it
    answerable.

    ⚠ One `seen` set covers both widths deliberately. A unigram `DOBNOW` and the
    bigram `DOB NOW` normalise to the same key, which is right — one name spelled
    two ways — and `disp` keeps whichever spelling is commoner.
    """
    stat = collections.defaultdict(
        lambda: {"c": set(), "v": set(), "a": set(), "val": 0.0,
                 "disp": collections.Counter(), "ex": []})

    def add(k, display, r):
        s = stat[k]
        s["c"].add(r["contract_id"]); s["v"].add(r["v"]); s["a"].add(r["a"])
        s["val"] += float(r["val"] or 0)
        s["disp"][display] += 1
        if len(s["ex"]) < 5:
            s["ex"].append(r["t"][:90])

    for r in rows:
        vend = {norm(x) for x in TOKEN.findall(r["v"])}
        toks = TOKEN.findall(r["t"])
        keys = [norm(t) for t in toks]
        drop = [hard_drop(t, k, vend) for t, k in zip(toks, keys)]
        seen = set()
        for i, (raw, k) in enumerate(zip(toks, keys)):
            if not drop[i] and not agency_token(k, agencies) and k not in seen:
                seen.add(k)
                add(k, raw, r)
            if i + 1 < len(toks) and not drop[i] and not drop[i + 1]:
                bk = k + keys[i + 1]
                if bk not in seen:
                    seen.add(bk)
                    add(bk, f"{raw} {toks[i + 1]}", r)
    return stat


def gates(stat, n, reviewed_out=None):
    """Apply the candidate gates, returning survivors AND why each loss lost.

    ⚠ The rejections are not decoration. Every gate here is a threshold chosen
    from one worked example, and a threshold silently removing a real program
    looks identical to one that is working. `SYEP` is the standing example:
    3 contracts but only 2 distinct vendors, so MIN_VENDORS removes it.

    ⚠⚠ `reviewed_out` is the HUMAN's rejections, and it is a gate like any other
    — recorded with a reason rather than filtered out invisibly. A name a
    reviewer has already dismissed must not come back on the next run, and the
    count must be VISIBLE: an exclusion nobody can see is indistinguishable from
    a generator that simply stopped finding it.
    """
    reviewed_out = reviewed_out or set()
    keep, rejected = [], {}
    for k, s in stat.items():
        nc, nv, na = len(s["c"]), len(s["v"]), len(s["a"])
        why = []
        if k in reviewed_out:
            why.append("REVIEWED: a human rejected this name")
        if nc < MIN_CONTRACTS:
            why.append(f"MIN_CONTRACTS={MIN_CONTRACTS} (has {nc})")
        if nv < MIN_VENDORS:
            why.append(f"MIN_VENDORS={MIN_VENDORS} (has {nv})")
        if na > MAX_AGENCIES:
            why.append(f"MAX_AGENCIES={MAX_AGENCIES} (has {na})")
        if nc > n * DF_CEILING:
            why.append(f"DF_CEILING={DF_CEILING} (in {nc} of {n})")
        if why:
            rejected[k] = {"display": s["disp"].most_common(1)[0][0],
                           "why": "; ".join(why), "n_contracts": nc,
                           "n_vendors": nv, "n_agencies": na,
                           "total_value": s["val"]}
            continue
        keep.append({"name_key": k, "display": s["disp"].most_common(1)[0][0],
                     "n_contracts": nc, "n_vendors": nv, "n_agencies": na,
                     "total_value": s["val"], "examples": " | ".join(s["ex"])})
    keep.sort(key=lambda r: -r["total_value"])
    return keep, rejected


async def diagnose(conn):
    """extract(), plus everything it threw away. For the recall eval.

    ⚠ Human rejections are applied HERE, not in a caller, so the eval and the
    real run see the same candidate set. A recall figure measured against a
    different set than the one that ships is the harness-divergence defect this
    repo keeps paying for.
    """
    rows = await fetch_rows(conn)
    stat = tally(rows, await agency_vocab(conn, rows))
    keep, rejected = gates(stat, len(rows), rejected_names())
    return keep, rejected, len(rows)


async def extract(conn):
    """Candidate names from titles, with the vendor/agency/generic gates applied."""
    keep, _, n = await diagnose(conn)
    return keep, n


def _judge_batch(batch):
    """One model call. Builds its own client — batches may run concurrently."""
    from google import genai
    from google.genai import types
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY not set")
    cli = genai.Client(api_key=key)
    payload = [{
        "name": c["display"],
        "contracts": c["n_contracts"], "vendors": c["n_vendors"],
        "agencies": c["n_agencies"], "total_value_usd": round(c["total_value"]),
        "example_titles": c["examples"].split(" | "),
    } for c in batch]
    resp = cli.models.generate_content(
        model=MODEL,
        contents="Judge these candidate names:\n" + json.dumps(payload),
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCTION,
            response_mime_type="application/json",
            response_schema=SCHEMA,
            temperature=0,
        ),
    )
    u = getattr(resp, "usage_metadata", None)
    if u is not None:
        # ⚠ thoughts_token_count is None on models that do not think — coerce, or
        # the sum raises and takes the batch down over pure bookkeeping.
        USAGE.append((getattr(u, "prompt_token_count", 0) or 0,
                      getattr(u, "candidates_token_count", 0) or 0,
                      getattr(u, "thoughts_token_count", 0) or 0))
    return json.loads(resp.text).get("results", [])


PROGRAM_KINDS = ("program", "system")


def _is_program(j) -> bool:
    """True only when the flag AND the kind agree.

    ⚠ Trusting `is_program_name` alone admitted `PM3` (a staffing grade) and
    `SP2` at high confidence on the first real run. The model was told the flag
    is true only for `program`/`system` and set it anyway; a gate costs nothing
    and removes the need to trust that.
    """
    return bool(j.get("is_program_name")) and j.get("kind") in PROGRAM_KINDS


def _report_spend(n):
    """Print what the run actually spent.

    ⚠ Without this a run's cost becomes folklore: a "~$6" guess sat in these docs
    for six weeks unchecked and was wrong by ~2.4x in the expensive direction.
    Thinking tokens are billed as output and dominate, so a character-count
    estimate understates the bill.
    """
    if not USAGE:
        print("  no usage metadata returned — spend UNKNOWN (do not assume cheap)")
        return
    pin = sum(u[0] for u in USAGE)
    vis = sum(u[1] for u in USAGE)
    think = sum(u[2] for u in USAGE)
    print(f"  tokens over {len(USAGE)} batches: input {pin:,} · output {vis:,} "
          f"visible + {think:,} thinking = {vis + think:,} billed")
    price = PRICES.get(MODEL)
    if not price:
        print(f"  ⚠ no list price on file for {MODEL} — cost NOT computed")
        return
    cost = pin / 1e6 * price[0] + (vis + think) / 1e6 * price[1]
    print(f"  cost ${cost:.4f} at {MODEL} list price"
          + (f" (${cost/n:.5f}/candidate)" if n else ""))


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--judge", action="store_true",
                    help="run the model over the extracted candidates")
    ap.add_argument("--apply", action="store_true",
                    help="write program_name_candidates (default: report)")
    ap.add_argument("--limit", type=int, default=0, help="cap candidates (testing)")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = ap.parse_args()

    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=dbcreds.password(),
        database=os.environ.get("POSTGRES_DB", "databook"))
    failed = 0
    try:
        cands, scanned = await extract(conn)
        if args.limit:
            cands = cands[:args.limit]
        print(f"[names] {scanned} tech contracts scanned, {len(cands)} candidates "
              f"(>={MIN_CONTRACTS} contracts, >={MIN_VENDORS} vendors, "
              f"<={MAX_AGENCIES} agencies)\n")

        judged = {}
        if args.judge:
            batches = [cands[i:i + args.batch_size]
                       for i in range(0, len(cands), args.batch_size)]
            for i, b in enumerate(batches, 1):
                try:
                    for r in await asyncio.to_thread(_judge_batch, b):
                        judged[norm(r.get("name", ""))] = r
                    print(f"  batch {i}/{len(batches)} ok")
                except Exception as exc:                # noqa: BLE001
                    failed += 1
                    print(f"  batch {i}/{len(batches)} FAILED: {type(exc).__name__}: {exc}")
            # ⚠⚠ A RUN THAT CLASSIFIES NOTHING MUST NOT EXIT 0. The licence
            # classifier printed "Done. 0 classified" and exited 0 when the
            # Gemini account ran out of credit, and a cron with a dead-man's
            # switch would have pinged SUCCESS having done nothing.
            if batches and failed == len(batches):
                print("  ⚠⚠ EVERY batch failed — nothing judged")
            _report_spend(len(cands))
            print()

        hdr = f"  {'name':<24} {'kind':<11} {'prog':<5} {'conf':<7} {'v':>3} {'c':>4} {'a':>2} {'$M':>9}"
        print(hdr); print("  " + "-" * (len(hdr) - 2))
        for c in cands[:40]:
            j = judged.get(c["name_key"], {})
            print(f"  {c['display'][:24]:<24} {j.get('kind','-'):<11} "
                  f"{('YES' if j.get('is_program_name') else '-'):<5} "
                  f"{j.get('confidence','-'):<7} {c['n_vendors']:>3} "
                  f"{c['n_contracts']:>4} {c['n_agencies']:>2} "
                  f"{c['total_value']/1e6:>9.1f}")

        if judged:
            # ⚠⚠ THE MODEL CONTRADICTS ITSELF, MEASURED ON THE FIRST FULL RUN.
            # `PM3` and `SP2` came back kind=`labor_code` WITH
            # is_program_name=true — despite the instruction saying the flag is
            # true only for `program` and `system`. This repo already documents
            # the shape: a classifier's own rationale can refute the flag beside
            # it, so READ BOTH. The consistency rule is enforced HERE, in code,
            # because an instruction is a request and a gate is a guarantee.
            picks = [c for c in cands if _is_program(judged.get(c["name_key"], {}))]
            print(f"\n  === {len(picks)} judged a PROGRAM or SYSTEM ===")
            for c in picks:
                j = judged[c["name_key"]]
                print(f"  {c['display'][:22]:<22} {j['kind']:<8} {j['confidence']:<7} "
                      f"${c['total_value']/1e6:>8.1f}M  {j['why'][:76]}")

        if args.apply:
            for stmt in [s.strip() for s in SCHEMA_SQL.split(";") if s.strip()]:
                await conn.execute(stmt)
            async with conn.transaction():
                await conn.execute("DELETE FROM program_name_candidates")
                for c in cands:
                    j = judged.get(c["name_key"], {})
                    await conn.execute("""
                        INSERT INTO program_name_candidates
                          (name_key, display, n_contracts, n_vendors, n_agencies,
                           total_value, examples, kind, is_program, confidence,
                           why, judged_model, built_at)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12, now())""",
                        c["name_key"], c["display"], c["n_contracts"],
                        c["n_vendors"], c["n_agencies"], c["total_value"],
                        c["examples"], j.get("kind"), _is_program(j),
                        j.get("confidence"), j.get("why"),
                        MODEL if judged else None)
            print(f"\n[names] wrote {len(cands)} candidate row(s)")
            print("  ⚠ CANDIDATES ONLY — nothing here renders. Promote a name by "
                  "adding it to api/seed/program_curated.csv.")
        else:
            print("\n[names] nothing written. Re-run with --apply.")
    finally:
        await conn.close()
    return 1 if failed else 0


if __name__ == "__main__":                             # pragma: no cover
    sys.exit(asyncio.run(main()) or 0)
