"""Turn recorded review decisions into seed rows — Phase 1 of the review app.

    docker compose exec -T api python export_review_decisions.py program-names
    docker compose exec -T api python export_review_decisions.py program-names \
        --emit api/seed/program_curated.csv
    docker compose exec -T api python export_review_decisions.py program-names \
        --mark-exported api/seed/program_curated.csv

⚠ NO `> file` REDIRECT. `--emit` writes the seed itself — see below for why the
redirect was a data-loss bug rather than a style choice.

⚠⚠ WHY THIS IS A SCRIPT AND NOT A BUTTON. The box's deploy key is READ-ONLY —
measured, `git push --dry-run` on prod is refused. So the app cannot commit, and
that is the design rather than an obstacle (docs/REVIEW-APP-SCOPE.md §6.2): every
curated change still passes code review, and no web-facing process holds a
credential that can write to the repository. This writes the seed; a human reads
the diff and commits it.

HOW IT IS MEANT TO BE RUN, and the ORDER MATTERS
================================================
    1. ... --emit api/seed/program_curated.csv         WRITES that file
    2. git diff                                        read it
    3. commit, open a PR, merge
    4. ... --mark-exported api/seed/program_curated.csv   only now, and NAMING
                                                          the seed you exported

⚠⚠ STEP 4 IS PER-SEED, NOT PER-QUEUE. This queue writes accepts to
`program_curated.csv` and rejects to `program_name_rejected.csv`, and `--emit`
handles ONE file per run. A bare `--mark-exported` used to mark every pending
decision, so exporting one file and then marking would mark the OTHER file's
decisions exported without them ever being written — lost, and invisible,
because the queue then stops offering them. It now refuses when the pending
decisions span more than one seed, and tells you which.

⚠⚠ STEP 4 IS SEPARATE ON PURPOSE AND MUST NOT BE FOLDED INTO STEP 1. If a
decision were marked exported before the commit landed, a failed or abandoned
PR would leave it looking exported while absent from the seed — silently lost,
and invisible because the queue would stop offering it. Marking is therefore an
explicit second invocation, after the change is actually in git.

⚠ `--emit` REWRITES the seed in place: existing content byte-identical, with new
rows appended. It does not rewrite curated prose — an item that already has a row
is REFUSED with its name, because merging a changed decision into hand-written
reasoning is a judgement a script should not make.

⚠⚠ IT USED TO PRINT FOR A `> seed.csv` REDIRECT, AND THAT WAS A DATA-LOSS BUG.
`api/seed` was BAKED INTO THE IMAGE, so `--emit X > X` read the container's copy
and wrote the host's — two different files. The container's went stale the moment
rows were committed and stayed stale until the next api rebuild, so a SECOND
export would have silently dropped the first one's rows. The length guard could
not catch it either: it compared the output against the same stale copy it had
read. Fixed at both ends — `api/seed` is bind-mounted from the checkout
(docker-compose.yml) so there is one file, and the write goes to the file that
was read, atomically. Do not reintroduce the redirect.
"""
import argparse
import asyncio
import csv
import io
import os
import sys

import asyncpg

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules"))

try:
    import dbcreds
    import reviewqueue as rq
except ImportError:                                     # pragma: no cover
    from modules import dbcreds
    from modules import reviewqueue as rq

from config import Config

API_DIR = os.path.dirname(os.path.abspath(__file__))


def seed_full_path(rel_path):
    """Resolve a queue's declared seed path in BOTH layouts.

    ⚠⚠ THIS WAS THE WORST BUG IN THIS SCRIPT AND IT DESTROYED DATA IN TESTING.
    Queues declare their seed as a REPO-relative path (`api/seed/x.csv`), but in
    the api container the tree is rooted at `/app`, so there is no `/app/api`.
    The first version joined against `dirname(dirname(__file__))` — which inside
    the container is `/` — and looked for `/api/seed/program_curated.csv`. That
    does not exist, so the existing content read as EMPTY and `--emit` printed
    only the new rows: the documented `--emit … > seed.csv` would have replaced
    13 curated decisions and every comment block with two lines.

    It failed in the reassuring direction — no error, plausible output — which is
    this repo's oldest defect class. Strip a leading `api/` and resolve against
    the api directory, which is correct in the container and in a checkout.
    """
    rel = rel_path.replace("\\", "/")
    if rel.startswith("api/"):
        rel = rel[len("api/"):]
    return os.path.join(API_DIR, rel)


def _seed_lines(rel_path):
    """The seed file's existing lines, and the keys already present in it.

    ⚠ Read as TEXT, not parsed and rewritten. These files carry comment blocks
    that explain every judgement in them, and a csv round-trip would strip them.

    ⚠⚠ A MISSING FILE RAISES rather than returning empty. An empty read is
    indistinguishable from a correct one to a shell redirect, and the redirect is
    the documented usage — so "I could not find it" must never be able to look
    like "it had nothing in it".
    """
    full = seed_full_path(rel_path)
    if not os.path.exists(full):
        raise SystemExit(
            f"refusing to emit: {rel_path} was not found at {full}. Emitting "
            f"would print only the new rows, and the documented redirect would "
            f"then overwrite the seed with them.")
    text = io.open(full, encoding="utf-8").read()
    lines = text.splitlines()
    keys = set()
    for row in csv.reader(l for l in lines
                          if l.strip() and not l.lstrip().startswith("#")):
        if row and row[0].strip() and row[0].strip() not in ("name", "program_slug"):
            keys.add(row[0].strip().lower())
    return lines, keys


def _csv_line(row):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow([("" if c is None else str(c))
                                                 for c in row])
    return buf.getvalue()


async def collect(conn, queue_name):
    q = rq.REGISTRY.get(queue_name)
    if not q:
        raise SystemExit(f"unknown queue {queue_name!r}; "
                         f"expected one of {sorted(rq.REGISTRY)}")
    items = {i.item_id: i for i in await q.fetch(conn, limit=20000)}
    decisions = await rq.decisions_for(conn, queue_name)
    links = await rq.links_for(conn, queue_name)

    pending, skipped, orphans = [], [], []
    for item_id, d in sorted(decisions.items()):
        if d["exported"]:
            skipped.append((item_id, "already exported"))
            continue
        item = items.get(item_id)
        if item is None:
            # ⚠ A decision whose candidate no longer exists. NOT dropped
            # silently: the generator may have moved, and a decision the export
            # cannot place is exactly the thing that would vanish unnoticed.
            orphans.append(item_id)
            continue
        decision = rq.Decision(item_id=item_id, verb=d["verb"],
                               value=d["value"], note=d["note"] or "",
                               actor=d["actor"])
        # ⭐ ONLY FLAGGED LINKS BECOME Source CLAUSES. The reviewer picks; an
        # export that published every link would put leads behind a provenance
        # claim about a named City program.
        clauses = rq.source_clauses(links.get(item_id, []))
        rows = q.seed_rows(item, decision)
        if clauses:
            rows = [list(r) for r in rows]
            # The note is the LAST column in both seed shapes.
            for r in rows:
                note = (r[-1] or "").rstrip()
                r[-1] = (note + " " if note else "") + " ".join(clauses)
        pending.append({"item_id": item_id, "verb": d["verb"],
                        "path": q.seed_path_for(d["verb"]), "rows": rows,
                        "actor": d["actor"], "sources": len(clauses)})
    return q, pending, skipped, orphans


def marking_plan(pending, arg):
    """Which pending decisions a --mark-exported run may mark, or refuse.

    ⚠⚠ EXTRACTED SO IT CAN BE TESTED WITH REAL INPUTS. The bug this replaces —
    `--emit` is per-seed while marking was per-queue — was invisible to every
    source scan in test_review_export.py, because nothing about it shows up in a
    string the file contains. It is control flow, so it needs a callable.

    `arg` is True for a bare `--mark-exported`, or the seed path it names.
    Returns (to_mark, remaining, target); raises SystemExit to refuse.
    """
    paths = sorted({p["path"] for p in pending})
    target = arg if isinstance(arg, str) else None

    # ⚠⚠ REFUSE rather than guess. Marking every pending decision when only one
    # seed was exported is exactly how a decision ends up looking exported while
    # absent from the seed — lost, and invisible, because the queue then stops
    # offering it.
    if target is None and len(paths) > 1:
        detail = "\n".join(
            f"    {pa}   ({sum(1 for p in pending if p['path'] == pa)} "
            f"decision(s))" for pa in paths)
        raise SystemExit(
            "refusing to mark: these decisions span more than one seed, and "
            "--emit writes one at a time.\n" + detail +
            "\n  Export and commit each, then mark each: "
            "--mark-exported <that seed path>")
    if target is not None and target not in paths:
        raise SystemExit(
            f"refusing to mark: no pending decision belongs in {target!r}. "
            f"Pending seeds are: {', '.join(paths)}")

    to_mark = [p for p in pending if target is None or p["path"] == target]
    return to_mark, len(pending) - len(to_mark), target or paths[0]


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("queue")
    ap.add_argument("--emit", metavar="SEED",
                    help="print one seed file in full, with new rows appended")
    # ⚠⚠ TAKES THE SEED IT IS MARKING FOR, because `--emit` is PER-PATH and this
    # was not. A queue can write to more than one seed — program-names sends
    # accepts to program_curated.csv and rejects to program_name_rejected.csv —
    # so emitting one file, committing it, then running a bare --mark-exported
    # marked the OTHER file's decisions exported without them ever being
    # written. Silently lost, and invisible, because the queue then stops
    # offering them. That is the same failure the step-4 warning above
    # describes, one grain down: the ORDER was right and the SCOPE was wrong.
    ap.add_argument("--mark-exported", nargs="?", const=True, default=False,
                    metavar="SEED",
                    help="⚠ ONLY after the rows are committed and merged. Takes "
                         "the seed path you exported; required when the pending "
                         "decisions span more than one seed")
    args = ap.parse_args()

    conn = await asyncpg.connect(**dbcreds.settings(Config.db))
    try:
        q, pending, skipped, orphans = await collect(conn, args.queue)

        if args.emit:
            lines, present = _seed_lines(args.emit)
            new, refused = [], []
            for p in pending:
                if p["path"] != args.emit:
                    continue
                for r in p["rows"]:
                    if str(r[0]).strip().lower() in present:
                        refused.append((p["item_id"], r[0]))
                        continue
                    new.append(_csv_line(r))
            # ⚠ Refusals go to STDERR, historically because a `> seed.csv`
            # redirect would swallow them. The redirect is gone (see below) but
            # stderr is still right: a silent refusal is a decision quietly not
            # exported.
            for item_id, key in refused:
                print(f"REFUSED {item_id}: {key!r} already has a row in "
                      f"{args.emit} — merge it by hand", file=sys.stderr)
            if not new:
                print(f"no new rows for {args.emit}", file=sys.stderr)
            out_lines = lines + new
            # ⚠ Cheap assertion: an emit must be strictly LONGER than the file
            # it replaces. Kept, and it MEANS something now — before the write
            # went in place it compared the output against the same copy it had
            # read, which could be a stale image copy while the file actually
            # being replaced was the checkout's.
            if len(out_lines) < len(lines) or not lines:
                raise SystemExit(
                    f"refusing to emit: read {len(lines)} existing line(s) from "
                    f"{args.emit}, which cannot be right — writing this would "
                    f"truncate the seed.")

            # ⚠⚠ WRITES THE FILE IT READ, RATHER THAN PRINTING FOR A REDIRECT.
            # `--emit X > X` read X inside the container and wrote X on the
            # host, and those were DIFFERENT FILES: api/seed was baked into the
            # image, so the copy read went stale the moment rows were committed
            # and stayed stale until the next api rebuild. A second export would
            # then have silently dropped the first one's rows — and the length
            # guard above could not see it, because it compared against the same
            # stale copy. api/seed is now bind-mounted from the checkout
            # (docker-compose.yml) so there is ONE file; writing it in place is
            # what makes that structural rather than a convention.
            #
            # Atomic: same directory, so os.replace cannot leave a half-written
            # seed if this is interrupted.
            target = seed_full_path(args.emit)
            tmp = target + ".tmp"
            with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(out_lines) + "\n")
            os.replace(tmp, target)
            print(f"wrote {len(new)} new row(s) to {args.emit} "
                  f"({len(lines)} -> {len(out_lines)} lines). Read the diff, "
                  f"commit, THEN --mark-exported {args.emit}", file=sys.stderr)
            return 0

        # report mode
        print(f"[export] queue {q.name}")
        print(f"[export] {len(pending)} decision(s) ready, "
              f"{len(skipped)} already exported, {len(orphans)} orphaned")
        by_path = {}
        for p in pending:
            by_path.setdefault(p["path"], []).append(p)
        for path, ps in sorted(by_path.items()):
            print(f"\n  -> {path}   ({len(ps)} row group(s))")
            for p in ps:
                src = f"  +{p['sources']} source(s)" if p["sources"] else ""
                print(f"     {p['verb']:<7} {p['item_id']:<22} by {p['actor']}{src}")
                for r in p["rows"]:
                    print(f"       {_csv_line(r)[:150]}")
        if orphans:
            # ⚠ Loud, not a footnote: a decision the export cannot place is the
            # one that disappears without anyone noticing.
            print(f"\n  ⚠ {len(orphans)} decision(s) name a candidate that no "
                  f"longer exists: {orphans[:8]}")
        if not pending:
            print("\n  nothing to export.")
        else:
            print(f"\n  next: --emit <seed path> > <that file>, read the diff, "
                  f"commit, THEN --mark-exported")

        if args.mark_exported:
            if not pending:
                print("\n[export] nothing to mark.")
                return 0
            to_mark, remaining, where = marking_plan(pending, args.mark_exported)
            async with conn.transaction():
                for p in to_mark:
                    await conn.execute(
                        "UPDATE review_decision SET exported_at = now() "
                        " WHERE queue = $1 AND item_id = $2",
                        q.name, p["item_id"])
            print(f"\n[export] marked {len(to_mark)} decision(s) exported "
                  f"for {where}.")
            # ⚠ Say what is STILL unexported. A silent partial mark reads as a
            # completed export.
            if remaining:
                print(f"[export] {remaining} decision(s) in other seeds remain "
                      f"unexported.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":                              # pragma: no cover
    Config.load(file=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "env.yaml"))
    sys.exit(asyncio.run(main()) or 0)
