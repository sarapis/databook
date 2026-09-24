"""Measure the RECALL of the program-name extractor against known City programs.

    docker compose exec -T api python eval_program_names.py

WHY THIS EXISTS
===============
`build_program_name_candidates.py` was presented as a strong result — 346
candidates, 77 judged program/system. That reported PRECISION and said nothing
about RECALL, and the first five-name check against externally-verified programs
found it missing two of the three that exist in the corpus:

    MyCity      90 contracts   FOUND
    NYC311       7 contracts   MISSED  <- killed by the ID_LIKE regex
    ACCESS HRA   5 contracts   MISSED  <- multi-word, single-token extractor
    LinkNYC      0 contracts   absent from the corpus, not a miss
    Big Apple    0 contracts   absent from the corpus, not a miss

Both of those misses have since been fixed and the fixes were OPPOSITE in kind,
which is the argument for the diagnosis this now prints. NYC311's cause was a
regex; ACCESS HRA's was that the extractor could not form the name at all, and
the bigram pass that fixed it had to ALLOW an agency token inside a phrase while
still rejecting one on its own. Reported as a bare "MISSED", the two were
indistinguishable, and the second sat behind the first looking like the same
problem for a session.

⚠⚠ THE `absent` DISTINCTION IS THE WHOLE POINT. A name the City runs but never
names in a contract title cannot be found from titles, and counting that as a
recall failure measures the CORPUS while looking like it measures the extractor.
Conflating the two makes the score worse than reality AND hides the real misses
underneath it. So every seed row declares whether it SHOULD be findable, and the
three outcomes are reported separately.

⚠ SHARES PRODUCTION'S DEFINITIONS — it imports and runs the real `extract()`
rather than reimplementing the tokeniser. A harness that rebuilds the thing it
measures reports the accuracy of a different system; this repo already paid for
that with the org-crosswalk suffix list.

⚠ This measures the EXTRACTOR only, not the model's judgement. A name can be
extracted and then judged `generic`; that is a separate failure and is reported
separately, because the fixes are different — one is a tokeniser change, the
other a prompt or gate change.
"""

import asyncio
import csv
import io
import os
import sys

import asyncpg

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

try:
    import dbcreds
except ImportError:                                    # pragma: no cover
    from modules import dbcreds

import build_program_name_candidates as bpn            # noqa: E402

KNOWN_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "seed", "program_names_known.csv")


def load_known():
    rows = []
    with io.open(KNOWN_CSV, encoding="utf-8") as fh:
        for r in csv.reader(fh):
            if not r or not r[0].strip() or r[0].lstrip().startswith("#"):
                continue
            if r[0].strip().lower() == "name":
                continue
            rows.append({"name": r[0].strip(),
                         "expect": (r[1] if len(r) > 1 else "unknown").strip(),
                         "source": (r[2] if len(r) > 2 else "").strip(),
                         "note": (r[3] if len(r) > 3 else "").strip()})
    return rows


async def corpus_hits(conn, name):
    """How many tech contracts MENTION this name at all — a loose substring count.

    ⚠ This is what separates "the extractor missed it" from "it is not in the
    data". Without it a zero is unattributable.

    ⚠⚠ AND IT IS DELIBERATELY `ILIKE '%name%'`, AGAINST THIS REPO'S STANDING
    RULE, because measurement showed the rule inverts here. The rule exists to
    stop a short token matching something unrelated — `%311%` matching the
    contract number 7-858-0311A. But applied to NG911 a word boundary returns
    **69 where the substring returns 72**, and the 3 it drops are
    `NG911CALLHANDLING- EVANS E-ARMS` and its two siblings: real NG911
    contracts written with no separator. A blanket boundary rule is itself a
    filter that hides good answers.

    So this stays loose ON PURPOSE, and it is safe to be loose because the only
    decision it drives is zero-vs-non-zero. `reachable` is the precise number,
    computed from the tokeniser itself rather than from a second regex that
    could disagree with it.

    ⚠ A THIRD NUMBER IS THE ONE THAT MATTERS, and neither of the first two is
    it. NG911 is 72 mentions, 69 word-boundary, **66 reachable** — the extra
    gap being `NG911-CAD`-style hyphen fusion, which the tokeniser keeps as ONE
    token because `-` is legal inside a token. The seed note had said 66 from
    the start; I called it stale because it matched neither figure I had
    measured, when it was answering the question I had not measured yet.
    **A number that disagrees with your measurement may be answering a
    different question — find out which before correcting it.**
    """
    return await conn.fetchval("""
        SELECT count(DISTINCT c.contract_id)
          FROM contracts c
          JOIN digital_contract_enrichment e ON e.contract_id = c.contract_id
         WHERE e.tech_relevant IS TRUE AND c.contract_title ILIKE $1""",
        f"%{name}%") or 0


async def main():
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=dbcreds.password(),
        database=os.environ.get("POSTGRES_DB", "databook"))
    try:
        known = load_known()
        cands, rejected, scanned = await bpn.diagnose(conn)
        keys = {c["name_key"] for c in cands}

        # ⚠ `reachable` comes from the TOKENISER, not a second regex. It is the
        # number of contracts in which the name was actually formed as a token
        # or a bigram — i.e. the most contracts the extractor could ever find it
        # in. Where it is below `mentions`, the gap is a tokenisation limit that
        # no gate change can close: NG911 reads 72 mentions against 69 reachable,
        # the 3 being `NG911CALLHANDLING-…`, where the name is fused to the next
        # word and is simply not a token.
        reach = {c["name_key"]: c["n_contracts"] for c in cands}
        reach.update({k: v["n_contracts"] for k, v in rejected.items()
                      if k not in reach})

        print(f"[eval] {scanned} tech contracts, {len(cands)} candidates, "
              f"{len(known)} known names\n")
        print(f"  {'name':<32} {'expect':<8} {'mentions':>8} {'reachable':>9} "
              f"{'extracted':>9}  verdict")
        print("  " + "-" * 76)

        found = missed = absent = 0
        misses = []
        for k in known:
            hits = await corpus_hits(conn, k["name"])
            key = bpn.norm(k["name"])
            got = key in keys
            if k["expect"] == "absent" or hits == 0:
                verdict, absent = "not in corpus", absent + 1
            elif got:
                verdict, found = "FOUND", found + 1
            else:
                verdict, missed = "MISSED", missed + 1
                misses.append((k["name"], hits))
            print(f"  {k['name']:<32} {k['expect']:<8} {hits:>8} "
                  f"{reach.get(key, 0):>9} {('yes' if got else 'no'):>9}  {verdict}")

        findable = found + missed
        print(f"\n  findable in corpus: {findable}   found {found}   missed {missed}")
        if findable:
            print(f"  RECALL over findable names: {found}/{findable} = "
                  f"{100.0 * found / findable:.0f}%")
        print(f"  ⚠ {absent} name(s) are NOT in the corpus — excluded from recall, "
              "because their absence measures the data, not the extractor.")
        if misses:
            # ⚠⚠ A MISS MUST NAME WHAT REMOVED IT. "MISSED" alone sends the next
            # reader to re-derive the cause, and the causes need OPPOSITE fixes:
            # a gate threshold is a judgement call about precision, while a name
            # the tokeniser cannot even form is a tokeniser bug. Reporting them
            # as one number is how ACCESS HRA sat behind NG911's fix looking
            # like the same problem.
            print("\n  MISSES, with the reason each one was removed:")
            for n, h in misses:
                k = bpn.norm(n)
                if k in rejected:
                    r = rejected[k]
                    why = f"gate: {r['why']}"
                else:
                    words = len(n.split())
                    why = ("never tokenised: %d words, extractor forms 1-2 word "
                           "names" % words) if words > 2 else \
                          "never tokenised: hard_drop (stop word, id-like, or "\
                          "the contract's own vendor name)"
                print(f"    {n:<32} {h:>3} contract(s)  {why}")
        # ⚠ The seed is 13 names, so it can only ever speak for names somebody
        # thought to list. This block speaks for the rest: the biggest thing each
        # gate removed, so a reader can see whether a gate is eating something it
        # should not without having to guess the name in advance.
        # ⚠ SEEDED WITH EVERY GATE, so one that fired zero times still prints a
        # row. A gate absent from this list and a gate that removed nothing are
        # otherwise identical to a reader — the same confusion as an empty search
        # group and a broken query. DF_CEILING is the live example: it removes 0.
        counts = {g: 0 for g in bpn.GATE_NAMES}
        biggest = {}
        for r in rejected.values():
            for clause in r["why"].split("; "):
                g = clause.split("=")[0]
                counts[g] = counts.get(g, 0) + 1
                if g not in biggest or r["total_value"] > biggest[g]["total_value"]:
                    biggest[g] = r
        print("\n  WHAT THE GATES REMOVED (largest casualty of each):")
        for g in sorted(counts):
            r = biggest.get(g)
            if r is None:
                print(f"    {g:<14} removed {0:>5} name(s)   "
                      f"(inert on this corpus — nothing reached it)")
                continue
            print(f"    {g:<14} removed {counts[g]:>5} name(s)   largest: "
                  f"{r['display'][:26]:<26} ${r['total_value']/1e6:>7.1f}M "
                  f"({r['n_contracts']}c {r['n_vendors']}v {r['n_agencies']}a)")

        # ⚠ Deliberately does NOT exit non-zero on a miss. This is a MEASUREMENT,
        # not a gate: recall below 100% is the expected state while the extractor
        # is single-token, and a red check nobody can fix becomes a red check
        # nobody reads — the permanently-red monitor this repo already paid for.
        # The number is the output; acting on it is a decision.
    finally:
        await conn.close()


if __name__ == "__main__":                             # pragma: no cover
    asyncio.run(main())
