#!/usr/bin/env python3
"""Generate the review worksheet for the largest non-licence tech contracts.

⚠⚠ WHY THIS EXISTS. The Overview redesign's composition bar segments come from
`digital_contract_enrichment.function_category` — the classifier's free-text
bucket, with NO curation layer. Measured 2026-08-12: the "Data/analytics"
segment read $2,137M, of which $1,927M — 90% — was TWO misfiled contracts (a
$998M camera-enforcement program, and $929M of hotel management for homeless
services that is not technology at all). If one segment's top rows can hide a
$1.93B error, every segment's top rows are suspect until a human looks.

The top ~30 non-licence tech contracts by value dominate every segment, so this
worksheet is the composition bar's publication gate — the same
top-N-by-value discipline as the licence review, one grain down.
Licence-classified contracts are excluded: they already have family-grain
review.

⚠⚠ AND A GLOBAL TOP-N CANNOT SEE A SMALL SEGMENT'S OWN TOP ROWS — measured
2026-09-15: the default sheet draws **0 rows from 8 of the 14** non-licence
segments. Data/analytics, the segment this file's own preamble is about, is one
of them: correcting its top two rows took it $2,137M -> $209.0M and therefore
out of the global top 30 entirely, so the residual misclassification inside it
became unreachable by the gate that found the first one. **The gate worked so
well on that segment that the segment fell out of the gate.**

`--segment` is the answer: the same discipline applied WITHIN one segment, so
every segment's own top rows are reviewable regardless of how small the segment
is. Each segment writes its own sheet, because one shared path would silently
discard the decisions already made in another.

    docker compose exec -T api python build_contract_review_worksheet.py \
        --segment 'Data/analytics' --top 30

⚠ RE-RUNNING NEVER DISCARDS A DECISION. Existing verdicts are read back and
preserved, same rule as build_review_worksheet.py.

Decisions are applied via api/seed/contract_enrichment_curated.csv (see
seed_contract_enrichment.py) — the worksheet is where you DECIDE, the seed is
where the decision LIVES.

    docker compose exec -T api python build_contract_review_worksheet.py
    docker compose exec -T api python build_contract_review_worksheet.py --top 50
"""
import argparse
import asyncio
import csv
import os
import sys

from modules import autoload  # noqa: F401,E402
from postgrex import PostgresModelAsync  # noqa: E402

# ⚠ Shares production's query and enrichment — a harness that rebuilds them
# measures a different system (the org-crosswalk suffix-list lesson).
import classify_digital_contracts as clf  # noqa: E402
# ⚠ The one owner of what a segment IS. Re-deriving the predicate here would
# make the worksheet measure a different partition from the bar it gates.
from modules import techsegments  # noqa: E402

# ⚠ Same un-normalized-root trap note as build_review_worksheet.py: __file__ is
# "<stdin>" when piped; fall back to cwd (which is /app in the container).
_here = os.path.abspath(__file__) if os.path.exists(__file__) else os.path.abspath(os.getcwd() + "/x")
ROOT = os.environ.get("REVIEW_ROOT") or os.path.dirname(_here)
OUT = os.path.join(ROOT, "docs", "contract-review-worksheet.csv")


def sheet_path(segment: str) -> str:
    """Where this sheet lives. ⚠ A SEGMENT SHEET NEVER SHARES THE GLOBAL PATH:
    `read_existing` only carries forward decisions for contracts that are IN the
    new sheet, so writing a segment run over the global file would drop the
    decisions it does not contain — the worksheet's own "re-running never
    discards a decision" rule, broken by the file name rather than by the code."""
    if not segment:
        return OUT
    return os.path.join(ROOT, "docs",
                        f"contract-review-worksheet-{techsegments.slug(segment)}.csv")

FIELDS = ["rank", "contract_id", "value_usd", "contract_title", "vendor_name",
          "agency", "start_date", "end_date", "procurement_method",
          "ai_function_category", "ai_rationale",
          "contract_purpose", "main_commodity", "notice_description",
          # ⚠⚠ WHETHER THIS CONTRACT IS ALREADY DECIDED IN THE SEED. A SEGMENT
          # SHEET DOES NOT INHERIT THE GLOBAL SHEET'S VERDICTS — `read_existing`
          # reads one file — so a row settled by an earlier pass reappears blank
          # and a reviewer can re-decide or, worse, CONTRADICT it. Measured
          # 2026-09-15: the $998.5M and $537.6M camera-enforcement pair were
          # settled in August and showed up undecided in the Hardware sheet.
          # The seed remains the one home for a decision; this column only says
          # that one exists.
          "already_curated",
          # ---- decision columns (yours) ----
          "verdict",             # ok | wrong-function | not-tech | unsure
          "correct_tech_relevant",   # 0/1, only when verdict says so
          "correct_function_category",
          "note"]


def read_existing(path=None):
    path = path or OUT
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    return {r["contract_id"]: r for r in csv.DictReader(lines)
            if (r.get("verdict") or "").strip()}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--segment", default="",
                    help="review WITHIN one composition segment, e.g. 'Data/analytics'. "
                         "Writes its own sheet; omit for the global top-N.")
    args = ap.parse_args()

    out_path = sheet_path(args.segment)
    decided = read_existing(out_path)

    # The candidates: tech, not a licence, one row per contract, by value.
    # ⚠ The segment predicate is BOUND, never interpolated — these names are the
    # classifier's free text, not ours.
    seg_sql, seg_params = "NOT e.is_license", []
    if args.segment:
        pred = techsegments.sql_predicate(args.segment, 1)
        if pred is None:
            print("--segment cannot be blank", file=sys.stderr)
            return 2
        seg_sql, seg_params = pred
    rows = await PostgresModelAsync.select_safe(f"""
        WITH c AS (SELECT DISTINCT ON (contract_id) contract_id,
                          coalesce(current_amount, award_amount) AS val
                   FROM contracts WHERE contract_id IS NOT NULL
                   ORDER BY contract_id, coalesce(current_amount,0) DESC,
                            coalesce(award_amount,0) DESC)
        SELECT c.contract_id, c.val, e.function_category, e.rationale,
               coalesce(e.curated, false) AS curated
        FROM c JOIN digital_contract_enrichment e ON e.contract_id = c.contract_id
        WHERE e.tech_relevant AND {seg_sql}
        ORDER BY c.val DESC NULLS LAST
        LIMIT {int(args.top)}
    """, seg_params) or []

    # ⚠⚠ AN EMPTY SHEET IS A MISSPELLED SEGMENT, NOT A CLEAN ONE. The segment names
    # are free text from the classifier ("Data/analytics", "ERP/financials"), so a
    # near-miss binds fine and matches nothing — and a worksheet with no rows reads
    # exactly like "there is nothing here to review". Fail loudly and name the real
    # ones, rather than writing a file that says zero.
    if not rows:
        print(f"no contracts matched (segment={args.segment!r}) — nothing written",
              file=sys.stderr)
        if args.segment:
            known = await PostgresModelAsync.select_safe("""
                SELECT coalesce(nullif(trim(function_category),''),'(uncategorised)') AS seg,
                       count(*) AS n
                FROM digital_contract_enrichment
                WHERE tech_relevant AND NOT is_license
                GROUP BY 1 ORDER BY 2 DESC
            """) or []
            print("known segments: " + ", ".join(
                f"{r['seg']} ({r['n']})" for r in known), file=sys.stderr)
        return 3
    ids = [r["contract_id"] for r in rows]
    meta = {r["contract_id"]: r for r in rows}

    # Evidence, through the classifier's own fetch path.
    contracts = clf._dedup(await PostgresModelAsync.select_safe(
        clf.CONTRACT_SELECT.format(where="c.contract_id = ANY($1)"), [ids]))
    await clf.attach_notices(contracts)
    by_id = {c["contract_id"]: c for c in contracts}

    kept = 0
    out = []
    for i, cid in enumerate(ids, 1):
        c = by_id.get(cid, {})
        m = meta[cid]
        prior = decided.get(cid, {})
        if prior:
            kept += 1
        out.append({
            "rank": i, "contract_id": cid,
            "value_usd": int(m["val"] or 0),
            "contract_title": (c.get("contract_title") or "").replace("\n", " "),
            "vendor_name": c.get("vendor_name") or "",
            "agency": c.get("agency") or "",
            "start_date": c.get("start_date") or "", "end_date": c.get("end_date") or "",
            "procurement_method": c.get("procurement_method") or "",
            "ai_function_category": m.get("function_category") or "",
            "ai_rationale": (m.get("rationale") or "").replace("\n", " ")[:300],
            "contract_purpose": (c.get("contract_purpose") or "").replace("\n", " ")[:300],
            "main_commodity": c.get("main_commodity") or "",
            "notice_description": (c.get("notice_description") or "").replace("\n", " ")[:300],
            # ⚠ "yes" rather than True/1: this is read by a human in a spreadsheet,
            # and a bare 0/1 beside four text columns reads as a score.
            "already_curated": "yes" if m.get("curated") else "",
            "verdict": prior.get("verdict", ""),
            "correct_tech_relevant": prior.get("correct_tech_relevant", ""),
            "correct_function_category": prior.get("correct_function_category", ""),
            "note": prior.get("note", ""),
        })

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        scope = (f"SEGMENT '{args.segment}'" if args.segment
                 else "the composition bar's publication gate")
        fh.write(f"# CONTRACT-GRAIN REVIEW WORKSHEET — {scope}.\n"
                 "# Fill `verdict` (ok | wrong-function | not-tech | unsure); add the\n"
                 "# correction columns only when the verdict says something is wrong.\n"
                 "# Apply decisions via api/seed/contract_enrichment_curated.csv.\n")
        w = csv.DictWriter(fh, fieldnames=FIELDS, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(out)
    print(f"wrote {out_path} ({len(out)} contracts, {kept} prior decisions preserved)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
