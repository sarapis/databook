#!/usr/bin/env python3
"""Find contracts the classifier answered BOTH ways — the same programme, in and
out of the technology universe at once.

⚠⚠ WHY THIS EXISTS, AND WHY IT IS NOT ANOTHER WORKSHEET. The review gate is
top-N-by-value, per segment since 2026-09-15. Measured across the five segments
reviewed that day, its yield fell away sharply — 4 corrections in 30 rows, then
0 in 50, 1 in 30, 0 in 30, 0 in 10 — because a top-N cut re-reads the same large,
well-understood contracts. Nine segments remain ungated, holding ~12% of value
and six of them under 1% between them. **Five more worksheets would cost more
than they can find.**

This asks a different question, and one that needs no judgement to pose: where
does our own data already contradict itself? A programme whose contracts are
classified `tech_relevant` in one row and not in the next is wrong in one of
them whatever the boundary is, so it is a defect independent of where the line
between "technology" and "a service delivered through technology" is drawn —
which is the part that is genuinely arguable and genuinely the owner's.

⚠⚠ IT DOES NOT SAY WHICH SIDE IS RIGHT, and must not be read as though it does.
It is TRIAGE: it names the pairs, and the decision still goes through
api/seed/contract_enrichment_curated.csv like every other correction.

⚠⚠ AND IT IS BLIND TO A MULTI-AWARD PANEL — a KNOWN limit, found 2026-09-15 by
reading a population rather than by running this. DCAS ran ONE telephonic
interpretation procurement with a PRIMARY and a SECONDARY award: Language Line
($18.57M) came back non-tech and Lionbridge ($18.66M) tech — same agency, same
procurement, same service, opposite answers, and **this scan cannot see it**,
because the key carries the VENDOR and the two awards have different vendors.
The same shape hid TotalCaption's two CART contracts. Catching it needs a
per-PROCUREMENT key (the EPIN root, which `notice_product_links` already uses to
join a notice to its contract) rather than a per-contract one. Not built: the
vendor is what makes the title claim mean "the same programme", so dropping it
would reintroduce the $612.9M of noise measured below. **Two keys, not a wider
one, if this is ever extended.**

⚠⚠ THE GROUPING KEY IS THE WHOLE INSTRUMENT, AND THE OBVIOUS ONE IS USELESS.
Measured 2026-09-15 over the full corpus:

    (agency, vendor)                      250 groups   $612.9M  ~all legitimate
    (agency, vendor, normalised title)     18 groups    $26.4M   ~all real

A vendor doing both technology and non-technology work for one agency is
NORMAL, not a defect — COMPULINK is 65 tech rows and 4 non-tech at DoITT, and
HAZEN & SAWYER is 2 tech against 40 at DEP, because it is an engineering firm.
Grouping on (agency, vendor) reports both as contradictions and buries the real
ones under $587M of noise. The title is what makes the claim "the same
PROGRAMME", and that is the claim worth making.

⚠ AND THE TITLE MUST BE NORMALISED, OR THE LARGEST CONTRADICTION IS INVISIBLE.
`NOISE` strips two different things, for one reason: renewal bookkeeping
(`Amendment #1`, `Renewal`, `FY25`, a bare id) and the PROCUREMENT VEHICLE
(`OGS`, `GSA`, `NAE`, `ACCO`, `piggyback`). Neither names what is being bought.
Measured: without the vehicle tokens, WEX BANK's `Fuel Card Services` and
`FUEL CARD SERVICES - OGS Extension` are two keys and the single largest
contradiction in the corpus ($21.1M) does not appear at all.

    docker compose exec -T api python scan_classifier_contradictions.py
    docker compose exec -T api python scan_classifier_contradictions.py --csv
"""
import argparse
import asyncio
import csv
import os
import re
import sys
from collections import defaultdict

from modules import autoload  # noqa: F401,E402
from postgrex import PostgresModelAsync  # noqa: E402
# ⚠ The carry-forward rule has ONE owner, in the segment-worksheet builder.
from build_contract_review_worksheet import read_existing as _read_existing  # noqa: E402

_here = os.path.abspath(__file__) if os.path.exists(__file__) else os.path.abspath(os.getcwd() + "/x")
ROOT = os.environ.get("REVIEW_ROOT") or os.path.dirname(_here)
# ⚠ NAMED INTO THE EXISTING EXCLUSION ON PURPOSE. `sync-public.sh` carries
# `docs/contract-review-worksheet*.csv` as a GLOB and its loop expands it, so a
# sheet named this way is kept out of the public snapshot by construction rather
# than by someone remembering to add a line. Invariant: curated decision SEEDS
# are published, worksheets are not — this is a worksheet.
OUT = os.path.join(ROOT, "docs", "contract-review-worksheet-contradictions.csv")

# ⚠ A bare `\b\d{4,}\b` also eats a four-digit year inside a real product name;
# that is accepted, because a year is bookkeeping here too. Single- and
# two-letter tokens are dropped by the `len > 2` filter below, so they need no
# entry — the same reasoning as the alias exclusions in the agency guard.
NOISE = re.compile(r"""(?ix)
    \b(amendment|renewal|extension|ext|nae|ace|acco|amd|amend|change\s*order|co)\b
  | \b(ogs|gsa|piggyback|req|pin|task\s*order)\b
  | \b(inc|llc|llp|ltd|corp|incorporated|company)\b
  | \#\s*\d+ | \bno\.?\s*\d+\b | \bfy\s*\d{2,4}\b | \b\d{4,}\b | \b\d+\s*(month|year)s?\b
  | [^a-z0-9 ]""")

# ⚠ A corpus this size cannot legitimately collapse to nothing. If the join or
# the enrichment table ever moves, the scan must fail loudly rather than report
# a clean bill of health — the oldest defect in this repo is a check whose zero
# is indistinguishable from never having run.
MIN_CORPUS = 5000

# ⚠ Legal-form and filler words carry no identity, so they must not count as
# "the vendor's own name appearing in its title" — otherwise `Services` in
# `FEDCAP REHABILITATION SERVICES INC` would strip the word from every title.
_VENDOR_STOP = {"the", "and", "for", "inc", "llc", "corp", "company",
                "national", "association", "of", "na"}

# ⚠⚠ A TITLE CAN BE A FORM NAME RATHER THAN A PROGRAMME NAME, and then the group
# means much less: it says "this vendor's paperwork at this agency", not "this
# thing the City buys". The discriminator is how many DIFFERENT vendors carry the
# same normalised title, and measured over the corpus it is cleanly BIMODAL with
# nothing in between — every genuine programme here is carried by exactly ONE
# vendor, while `260 Discretionary Contract` is carried by **999** and `decrease`
# by **51**. So the threshold needs no tuning and is not a judgement call; 3 is
# simply a value inside the empty gap.
# ⚠ Such groups are FLAGGED, never dropped: a vendor holding two discretionary
# contracts classified both ways may still be a real inconsistency. What is not
# supported is the claim that it is one programme. 4 groups / $1.0M of $26.4M.
GENERIC_TITLE_VENDORS = 3

# ⚠⚠ A ZERO ON THE SECOND AXIS IS MEANINGLESS UNLESS IT GATED ON SOMETHING.
# `unapplied_decisions` only looks where a human has already excluded a row, so
# with no curated exclusions loaded it returns [] for every corpus and reads as
# "every decision has been applied" — this repo's oldest defect, a check whose
# zero cannot be told from never having run. Deliberately far BELOW the real 21,
# because it exists only to catch the seed not being loaded at all.
MIN_DECIDED_PAIRS = 5

# ⚠ The agency CODE, not the agency STRING. Measured over the whole corpus:
# exactly two codes carry more than one agency string — 002 (six Mayoral
# offices) and 816 (DOHMH and OCME) — so the code is the coarser key, and on
# THIS axis that is what is wanted: TotalCaption's FY22 CART contract files
# under `OFFICE OF CRIMINAL JUSTICE (002)` while the FY23 row the owner excluded
# files under `MAYORALTY`, same code, same vendor, same $99,999 service.
# ⚠⚠ DO NOT PUSH THIS KEY BACK INTO `contradictions()`. There the code would
# FUSE DIFFERENT BODIES and assert they are one programme — the `801` defect the
# capital spine already records, where one FMS key carries three organisations.
# Here nothing is asserted: the pair is printed for a human to look at, and a
# cross-body pair is FLAGGED rather than hidden.
_ACODE = re.compile(r"^[A-Za-z]+[0-9]*-([0-9]+)-")

VALUES = """
WITH c AS (SELECT DISTINCT ON (contract_id) contract_id,
                  coalesce(current_amount, award_amount) AS val
           FROM contracts WHERE contract_id IS NOT NULL
           ORDER BY contract_id, coalesce(current_amount,0) DESC,
                    coalesce(award_amount,0) DESC)
"""


def _vendor_tokens(vendor: str) -> set:
    """What this vendor calls itself, including its own initialism.

    ⚠⚠ THE VENDOR IS ALREADY IN THE GROUP KEY, so repeating it inside the title
    adds nothing and only SPLITS keys. Measured: DOF's `General Banking Services
    - Bank of America` and `General Banking Services BOA NAE` are the same
    programme from the same vendor at the same agency, classified tech and
    non-tech respectively — and without this they are two keys, so the $6.9M
    contradiction is invisible. The initialism is what closes `BOA`."""
    words = [w for w in re.sub(r"[^a-z0-9 ]", " ", (vendor or "").lower()).split()]
    toks = {w for w in words if len(w) > 2} - _VENDOR_STOP
    core = [w for w in words if w not in ("inc", "llc", "corp", "na")]
    if len(core) >= 2:
        toks.add("".join(w[0] for w in core[:4]))
        toks.add("".join(w[0] for w in core if w not in ("of", "and", "the")))
    return toks


def norm_title(title: str, vendor: str = "") -> str:
    """The programme, with the paperwork and the vendor's own name removed.
    Sorted set of tokens, so `Fuel Card Services Amendment #1` and `FUEL CARD
    SERVICES - OGS Renewal #1` are one key and a reordered title does not split
    into two.

    ⚠⚠ THE FALLBACK IS LOAD-BEARING, NOT TIDINESS. Some titles ARE just the
    vendor's name — `First Data Amendment #1`, `SECUREWATCH24, LLC Renewal` —
    and stripping the vendor from those leaves nothing, which drops the group
    entirely. Measured: stripping without this fallback gains Bank of America
    ($6.9M) and LOSES First Data ($2.0M). Falling back to the unstripped key
    keeps both, and a title that is only a vendor name still groups that
    vendor's own rows, which is all it ever claimed to do."""
    plain = set(w for w in NOISE.sub(" ", (title or "").lower()).split() if len(w) > 2)
    stripped = plain - _vendor_tokens(vendor)
    return " ".join(sorted(stripped or plain))


async def load():
    rows = await PostgresModelAsync.select_safe(VALUES + """
        SELECT c.contract_id, c.val, e.tech_relevant, e.function_category,
               coalesce(e.curated, false) AS curated,
               ct.contract_title, ct.vendor_name, ct.agency
        FROM c
        JOIN digital_contract_enrichment e ON e.contract_id = c.contract_id
        JOIN contracts ct ON ct.contract_id = c.contract_id
        WHERE ct.vendor_name IS NOT NULL AND ct.agency IS NOT NULL
    """) or []
    # ⚠ contracts holds ONE ROW PER AMENDMENT, and the CTE picks one row per
    # contract_id — but the join back to `contracts` re-multiplies it. Dedupe
    # here or a single contract counts as its own contradiction.
    seen, out = set(), []
    for r in rows:
        if r["contract_id"] in seen:
            continue
        seen.add(r["contract_id"])
        out.append(r)
    return out


def contradictions(recs):
    groups = defaultdict(list)
    vendors_per_title = defaultdict(set)
    for r in recs:
        k = norm_title(r["contract_title"], r["vendor_name"])
        if k:                      # a title that normalises to nothing groups nothing
            groups[(r["agency"], r["vendor_name"], k)].append(r)
            # ⚠ COUNTED ON THE PLAIN TITLE, NOT THE GROUPING KEY. "Is this a form
            # name?" is a question about what the title SAYS; asking it of the
            # vendor-stripped residue answered a different question and reported
            # `Politico subscription` as generic because 22 vendors have the word
            # "subscription" somewhere in a title.
            vendors_per_title[norm_title(r["contract_title"])].add(r["vendor_name"])
    found = []
    for key, rows in groups.items():
        tech = [r for r in rows if r["tech_relevant"]]
        non = [r for r in rows if not r["tech_relevant"]]
        if not (tech and non):
            continue
        # Value at stake = what is still IN the universe and not already decided.
        stake = sum(float(r["val"] or 0) for r in tech if not r["curated"])
        # ⚠ A human having decided ONE side is a stronger signal than the model
        # disagreeing with itself, and it points at which way the pair resolves.
        n_vendors = len(vendors_per_title[norm_title(rows[0]["contract_title"])])
        found.append({"key": key, "tech": tech, "non": non, "stake": stake,
                      "human_decided": any(r["curated"] for r in rows),
                      "title_vendors": n_vendors,
                      "generic_title": n_vendors > GENERIC_TITLE_VENDORS})
    found.sort(key=lambda g: -g["stake"])
    return found


def _acode(contract_id: str) -> str:
    m = _ACODE.match(contract_id or "")
    return m.group(1) if m else ""


def _vkey(vendor: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (vendor or "").lower())


def unapplied_decisions(recs):
    """Rows still flagged tech where a human already excluded the SAME vendor at
    the SAME agency — a decision taken and not carried to its own siblings.

    ⚠⚠ THIS IS THE AXIS THE TITLE KEY CANNOT REACH, and it is why it exists.
    `contradictions()` groups on the normalised TITLE, so it is blind whenever a
    contract's title names the vendor's brand or its fiscal year instead of the
    service. Measured 2026-09-16, both found here and by neither the title key
    nor a title-word sweep on `(interpret|translat)`:

        CT1-056-20211407576  `Language Line Renewal Amendment #1`   $0.50M
        CT1-002-20228802334  `FY22 TotalCaption LLC Renewal #1`     $0.10M

    Each is the odd term out of a consecutive run of one service whose adjacent
    term the owner had already excluded. Of 26 Language Line rows across nine
    agencies exactly one was still flagged tech.

    ⚠ (agency, vendor) ALONE IS 250 GROUPS / $612.9M OF NOISE for the
    contradiction question — a vendor doing both kinds of work for one agency is
    normal. It is safe HERE only because it is gated on a human having already
    ruled on that pair, which the noise by definition is not: the same key over
    the same corpus yields 2 rows rather than 250 groups.

    ⚠ It is TRIAGE like the rest of this file. A human excluding one contract
    does not decide the next — the owner kept two interpretation contracts
    (tablets with video-relay software; translation OF a web platform) while
    excluding three, and a kept row carries no curated marker, so it correctly
    never gates anything here.

    Returns (rows, n_pairs_gated_on) so the caller can prove it looked."""
    decided = defaultdict(list)
    for r in recs:
        if r["curated"] and not r["tech_relevant"]:
            decided[(_acode(r["contract_id"]), _vkey(r["vendor_name"]))].append(r)
    out = []
    for r in recs:
        if not r["tech_relevant"] or r["curated"]:
            continue
        peers = decided.get((_acode(r["contract_id"]), _vkey(r["vendor_name"])))
        if peers:
            out.append({"row": r, "peers": peers,
                        "cross_body": all(p["agency"] != r["agency"] for p in peers)})
    out.sort(key=lambda d: -float(d["row"]["val"] or 0))
    return out, len(decided)


CSV_FIELDS = ["group", "stake_usd", "human_decided", "generic_title", "side",
              "contract_id", "value_usd", "function_category", "curated", "agency",
              "vendor_name", "contract_title", "verdict", "note"]


def csv_rows(found, path=None):
    """The sheet's rows, with any decision already recorded against a contract
    carried forward. READS THE SHEET ITSELF — see the last note.

    ⚠⚠ RE-RUNNING MUST NEVER DISCARD A DECISION, and this sheet destroyed one
    until 2026-09-16 — measured by writing a verdict into it and re-running:
    it came back blank. The columns exist and invite being filled, and a verdict
    of `ok` produces NO seed row, so THE WORKSHEET IS THE ONLY RECORD THAT A ROW
    WAS LOOKED AT AND FOUND RIGHT. The segment sheets already carry this rule;
    it was broken here by a writer that never read its own output.

    ⚠ ONE OWNER: `read_existing` is IMPORTED from the segment builder, never
    re-typed — two copies of a carry-forward rule is how two sheets come to
    disagree about what has been decided.

    ⚠ Split out of `main()` so it can be CALLED. Left inline it was reachable
    only with a database, which is how it went unguarded in the first place.

    ⚠⚠ AND IT TAKES A PATH, NOT A `decided` MAP, BECAUSE THE FIRST SPLIT LEFT
    THE HOLE OPEN. With the map injected, `csv_rows` was correct and the CALL
    SITE could still pass `{}` — reproducing the defect exactly — and the
    mutation proving it went SILENT past every guard, because the call lived in
    `main()` where only a database can reach it. Reading the sheet in here
    removes the shape instead of guarding it: there is no argument left to get
    wrong. A guard on a function is not a guard on its callers."""
    decided = _read_existing(path or OUT)
    out = []
    for i, g in enumerate(found, 1):
        for side, rows in (("tech", g["tech"]), ("non-tech", g["non"])):
            for r in rows:
                prev = decided.get(r["contract_id"], {})
                out.append({
                    "group": i, "stake_usd": int(g["stake"]),
                    "human_decided": "yes" if g["human_decided"] else "",
                    "generic_title": "yes" if g["generic_title"] else "",
                    "side": side, "contract_id": r["contract_id"],
                    "value_usd": int(float(r["val"] or 0)),
                    "function_category": r["function_category"] or "",
                    "curated": "yes" if r["curated"] else "",
                    "agency": r["agency"], "vendor_name": r["vendor_name"],
                    "contract_title": (r["contract_title"] or "").replace("\n", " "),
                    "verdict": (prev.get("verdict") or ""),
                    "note": (prev.get("note") or "")})
    return out


def write_sheet(found, path=None):
    """Write the sheet, carrying forward whatever is already recorded IN IT.

    ⚠⚠ ONE PATH, READ AND WRITTEN BY ONE FUNCTION, and that is the whole point.
    The first two attempts at this fix each left a hole a mutation walked
    straight through: passing the decisions in as an argument let the call site
    supply `{}`, and passing the PATH in let it supply a different file from the
    one being written — in both cases `csv_rows` was correct and the sheet still
    lost the decision. Neither mutation failed a test until the argument was
    removed. **A guard on a function is not a guard on its callers**; the only
    reliable fix is leaving the caller nothing to get wrong."""
    path = path or OUT
    rows = csv_rows(found, path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write("# PROGRAMMES THE CLASSIFIER ANSWERED BOTH WAYS. One group per\n"
                 "# (agency, vendor, normalised title); `side` says which way each row\n"
                 "# went. This sheet says they DISAGREE, never which side is right —\n"
                 "# record the decision in api/seed/contract_enrichment_curated.csv.\n"
                 "# ⚠ `verdict`/`note` are YOURS and are carried forward across runs;\n"
                 "# an `ok` verdict produces no seed row, so this is the only record\n"
                 "# that a row was looked at and found right.\n")
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return len(rows)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", action="store_true", help=f"also write {OUT}")
    args = ap.parse_args()

    recs = await load()
    if len(recs) < MIN_CORPUS:
        print(f"refusing to report: only {len(recs)} classified contracts, "
              f"expected >= {MIN_CORPUS}. The join or the enrichment table moved; "
              f"a zero here would read as 'no contradictions'.", file=sys.stderr)
        return 2

    found = contradictions(recs)
    total = sum(g["stake"] for g in found)
    print(f"scanned {len(recs)} classified contracts")
    gen = [g for g in found if g["generic_title"]]
    print(f"{len(found)} groups classified BOTH ways; "
          f"${total/1e6:,.1f}M still flagged tech inside them")
    print(f"  of which {len(gen)} rest on a FORM NAME rather than a programme "
          f"(${sum(g['stake'] for g in gen)/1e6:,.1f}M) — weaker, flagged below\n")
    for g in found:
        agency, vendor, _ = g["key"]
        flag = "  [a human has decided one side]" if g["human_decided"] else ""
        if g["generic_title"]:
            flag += (f"  [⚠ FORM NAME, not a programme — {g['title_vendors']} vendors"
                     f" share this title; the pair may still be real, 'one programme' is not]")
        print(f"--- ${g['stake']/1e6:,.1f}M | {vendor[:36]} @ {agency[:30]}{flag}")
        for r in g["tech"]:
            mark = " CURATED" if r["curated"] else ""
            print(f"      TECH     ${float(r['val'] or 0)/1e6:8,.1f}M {r['contract_id']:22}"
                  f"{mark} [{(r['function_category'] or '-')[:16]:16}] "
                  f"{(r['contract_title'] or '')[:48]}")
        for r in g["non"]:
            mark = " CURATED" if r["curated"] else ""
            print(f"      non-tech ${float(r['val'] or 0)/1e6:8,.1f}M {r['contract_id']:22}"
                  f"{mark} {'':19} {(r['contract_title'] or '')[:48]}")

    unapplied, n_pairs = unapplied_decisions(recs)
    if n_pairs < MIN_DECIDED_PAIRS:
        print(f"\nrefusing to report unapplied decisions: only {n_pairs} "
              f"(agency, vendor) pairs carry a curated exclusion, expected >= "
              f"{MIN_DECIDED_PAIRS}. The seed is not loaded; an empty result "
              f"here would read as 'every decision has been applied'.",
              file=sys.stderr)
        return 2
    print(f"\n== decisions not carried to their own siblings "
          f"({len(unapplied)} over {n_pairs} decided vendor/agency pairs) ==")
    if not unapplied:
        print("  none — every curated exclusion's vendor has no row still "
              "flagged tech at that agency.")
    for d in unapplied:
        r = d["row"]
        note = "  [⚠ different agency STRING under one code — check it is the "\
               "same body]" if d["cross_body"] else ""
        print(f"  ${float(r['val'] or 0)/1e6:8,.1f}M {r['contract_id']:22} "
              f"[{(r['function_category'] or '-')[:16]:16}] "
              f"{(r['vendor_name'] or '')[:28]:28} {(r['contract_title'] or '')[:40]}{note}")
        for p in d["peers"][:3]:
            print(f"            excluded already: {p['contract_id']:22} "
                  f"{(p['contract_title'] or '')[:40]}")

    if args.csv:
        write_sheet(found)
        print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
