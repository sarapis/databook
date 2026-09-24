"""The review app's API — the half a screen consumes.

Phase 1 of docs/REVIEW-APP-SCOPE.md. 225 items across five queues have been
awaiting human judgement with no interface, because the six generators that
produce them share a shape but no vocabulary. `modules/reviewqueue` is the
contract that gave them one; this serves it.

BUILT API-FIRST, DELIBERATELY — the same call as the org register's #186/#187.
The UI is a separate change and a PURE CONSUMER: every invariant below must hold
for any client (a screen, a curl, a bulk script), so it lives here rather than
in a form. `/admin/orgs` is the precedent, and its rule is the rule here: no
invariant is re-implemented in the UI.

⚠⚠ EVERY ENDPOINT AUTHENTICATES, AND THAT IS LOAD-BEARING RATHER THAN ROUTINE.
These endpoints serve `program_name_candidates` and its siblings — UNREVIEWED
model output that names City programs and assigns them money. #146's rule is
that such rows never render publicly; allowing a review tool to read them (which
it must, or no interface is possible) opens exactly one hole, and
`require_editor` is what closes it. `test_no_router_serves_the_review_queue_
without_authenticating` fails the build if a router imports the queue without
calling it.

⚠ DECISIONS LAND IN POSTGRES, NOT IN GIT. The box's deploy key is read-only
(measured: `git push --dry-run` is refused), so a human exports to the
version-controlled seed as a pull request. See the scope doc §6.2 — that is the
design, not a workaround: every curated change still passes code review and no
web-facing process holds a credential that can write to the repository.
"""
import os
import sys

from fastapi import APIRouter, Body, HTTPException, Request

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "modules"))

# ⚠ The file's own idiom, not `from modules import ...`: conftest.py replaces the
# whole `modules` package with a MagicMock, and a mock satisfies almost any
# assertion. This form loads the real module in both environments.
try:
    import dbcreds
    import reviewqueue as rq
except ImportError:                                     # pragma: no cover
    from modules import dbcreds
    from modules import reviewqueue as rq

from routers.org_admin import require_editor

import asyncpg

from config import Config

router = APIRouter(prefix="/review", tags=["Review queues"])


async def _conn():
    return await asyncpg.connect(**dbcreds.settings(Config.db))


def _actor(user: dict, payload: dict) -> str:
    """Who is deciding — the forwarded reviewer, else the calling token.

    ⚠⚠ THE FORWARDED ACTOR IS LOAD-BEARING, AND THE EXISTING ADMIN SHOWS WHY.
    The app calls this API SERVER-TO-SERVER with one service token, so
    `require_editor` resolves to that token's user on every request no matter
    who is at the keyboard. `/admin/orgs` accepts exactly that and says so —
    "the API attributes the change to the token's user, which is the durable
    record; this is only the label on screen". That is tolerable for one editor
    and WRONG here: two reviewers attributed to one string is the defect this
    whole queue exists to avoid, and it is permanent once written.

    So the app forwards the reviewer it authenticated, and this prefers it.

    ⚠ WHY THAT IS NOT A FORGEABLE ACTOR, precisely — the distinction matters:
      * the endpoint has ALREADY authenticated before this is read, so a
        stranger cannot reach it at all;
      * the browser never supplies this value. The app derives it server-side
        from nginx's VERIFIED credential (`PHP_AUTH_USER`), not from a form
        field, so a reviewer cannot claim to be the other reviewer;
      * what it does NOT defend against is a holder of the service token
        calling this directly with any actor they like — but that holder
        already has full write access, so the audit trail is not the weak link.

    ⚠ It falls back to the token's identity rather than refusing, so a direct
    scripted call is still attributed to something real. `record()` refuses the
    empty case outright, so nothing lands unattributed either way.

    ⚠ ONE SEAM: when magic-link sessions land (scope doc §6.1) the app forwards
    a session email instead of a basic-auth username and nothing here changes.
    """
    forwarded = ((payload or {}).get("actor") or "").strip()
    if forwarded:
        return forwarded[:120]
    return ((user or {}).get("email") or "").strip()


@router.get("/queues")
async def list_queues(request: Request):
    """Every queue, its question, how many await judgement, and its safety."""
    await require_editor(request)
    conn = await _conn()
    try:
        out = []
        for q in rq.REGISTRY.values():
            try:
                items = await q.fetch(conn, limit=10000)
                seeded = await q.already_decided(conn)
                decided = await rq.decisions_for(conn, q.name)
            except Exception as exc:                    # noqa: BLE001
                # ⚠ A queue whose generator table is absent is a legitimate
                # fresh-environment state, not a failure of the whole page — but
                # it must be VISIBLE, not silently a zero. "Nobody is called
                # that" and "this query is broken" being byte-identical is this
                # repo's oldest defect (#256).
                out.append({"queue": q.name, "question": q.question,
                            "awaiting": None, "error": type(exc).__name__,
                            "seed": q.seed_path, "in_git": q.seed_in_git,
                            "safe_by_construction": q.safe_by_construction,
                            "verbs": list(q.verbs)})
                continue
            # ⚠ `q.seed_key(i)`, never `i.subject` — a queue whose seed is
            # keyed on an ID (org-vendors) would otherwise never read as
            # settled, and its reviewer would be re-asked answered questions.
            settled = {i.item_id for i in items
                       if i.item_id in decided or q.seed_key(i) in seeded}
            out.append({"queue": q.name, "question": q.question,
                        "total": len(items),
                        "awaiting": len(items) - len(settled),
                        "decided": len(settled),
                        "seed": q.seed_path, "in_git": q.seed_in_git,
                        "safe_by_construction": q.safe_by_construction,
                        "verbs": list(q.verbs)})
        return {"queues": out}
    finally:
        await conn.close()


@router.get("/queues/{name}/items")
async def list_items(name: str, request: Request, limit: int = 200):
    """One queue's items, each carrying its evidence and any decision made."""
    await require_editor(request)
    q = rq.REGISTRY.get(name)
    if not q:
        raise HTTPException(404, f"unknown queue {name!r}")
    conn = await _conn()
    try:
        items = await q.fetch(conn, limit=max(1, min(int(limit), 2000)))
        seeded = await q.already_decided(conn)
        decided = await rq.decisions_for(conn, q.name)
        links = await rq.links_for(conn, q.name)
        out = []
        for i in items:
            d = decided.get(i.item_id)
            out.append({
                "item_id": i.item_id, "subject": i.subject,
                "proposal": i.proposal, "proposal_value": i.proposal_value,
                "confidence": i.confidence, "why": i.why,
                "proposed_by": i.proposed_by, "source_url": i.source_url,
                "evidence": [{"label": e.label, "value": e.value,
                              "kind": e.kind, "href": e.href}
                             for e in i.evidence],
                # ⚠ A table the queue defines and the view renders blind: the
                # columns come from the queue, so a second queue can show its
                # own records without a view change.
                "records": [dict(r) for r in i.records],
                "record_columns": [list(c) for c in i.record_columns],
                "records_note": i.records_note,
                "links": links.get(i.item_id, []),
                # ⚠ Served so the UI can show the reviewer exactly what an export
                # would write, rather than leaving them to infer it.
                "source_clauses": rq.source_clauses(links.get(i.item_id, [])),
                "decision": d,
                # ⚠ Two DIFFERENT settled states, never collapsed into one flag.
                # `in_seed` was decided before this tool existed and is already
                # published; `decision` is pending export. A reviewer needs to
                # tell them apart — the first is not theirs to redo casually.
                "in_seed": q.seed_key(i) in seeded,
            })
        return {"queue": q.name, "question": q.question,
                # ⚠ SERVED, never typed into the view. The view hardcoded the
                # reject label and put program-names' "Not a program" on every
                # queue — the same defect as the licence capability labels, which
                # lived in three Blade copies and were stale in all three.
                "verb_labels": {v: q.verb_labels.get(v, v.title()) for v in q.verbs},
                "pair_labels": list(q.pair_labels),
                "verbs": list(q.verbs), "seed": q.seed_path,
                "in_git": q.seed_in_git,
                "safe_by_construction": q.safe_by_construction,
                "total": len(out), "items": out}
    finally:
        await conn.close()


@router.post("/queues/{name}/decisions")
async def record_decision(name: str, request: Request, payload: dict = Body(...)):
    """Record ONE decision. Re-deciding an item replaces the earlier answer."""
    user = await require_editor(request)
    q = rq.REGISTRY.get(name)
    if not q:
        raise HTTPException(404, f"unknown queue {name!r}")

    # ⚠ Read AFTER require_editor above — never before. The forwarded value is
    # only trustworthy because the caller is already authenticated.
    actor = _actor(user, payload)
    if not actor:
        raise HTTPException(400, "no actor on the request; refusing to record an "
                                 "unattributed decision")
    item_id = (payload.get("item_id") or "").strip()
    verb = (payload.get("verb") or "").strip()
    if not item_id:
        raise HTTPException(400, "item_id is required")
    # ⚠ The queue's OWN verb list, not the contract's full set. `dismiss` exists
    # for untrusted public submissions and must not be offered on a generator
    # queue, where "spam" is not a thing that can happen.
    if verb not in q.verbs:
        raise HTTPException(
            400, f"{verb!r} is not a verb this queue accepts; expected one of "
                 f"{list(q.verbs)}")
    try:
        decision = rq.Decision(item_id=item_id, verb=verb,
                               value=payload.get("value"),
                               note=(payload.get("note") or "").strip(),
                               actor=actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    conn = await _conn()
    try:
        await rq.record(conn, q.name, decision)
    finally:
        await conn.close()
    return {"ok": True, "queue": q.name, "item_id": item_id,
            "verb": verb, "actor": actor}


@router.get("/glossary")
async def glossary(request: Request):
    """Every term the interface shows, each from the place that owns it.

    ⚠ Served rather than written into a template, for the reason the licence
    capability labels were: a vocabulary copied into a view goes stale there and
    nobody looks. The KIND definitions are the classifier's own, verbatim — a
    paraphrase would describe a different classifier than the one that ran.
    """
    await require_editor(request)
    return {"terms": rq.glossary()}


@router.post("/queues/{name}/links")
async def add_link(name: str, request: Request, payload: dict = Body(...)):
    """Attach a related link + note to an item.

    ⚠ Many per item and independent of the decision: they accumulate BEFORE an
    answer and survive a re-decide. ⭐ Only the ones the REVIEWER flags become
    `Source:` clauses on export — a research trail and a published citation are
    not the same thing.
    """
    user = await require_editor(request)
    q = rq.REGISTRY.get(name)
    if not q:
        raise HTTPException(404, f"unknown queue {name!r}")
    item_id = (payload.get("item_id") or "").strip()
    if not item_id:
        raise HTTPException(400, "item_id is required")
    conn = await _conn()
    try:
        lid = await rq.add_link(conn, q.name, item_id,
                               payload.get("url"), payload.get("note"),
                               _actor(user, payload),
                               bool(payload.get("is_source")))
    except ValueError as exc:
        # ⚠ Returned verbatim: it names WHY the URL was rejected, which is the
        # difference between fixing a typo and retyping the same bad link.
        raise HTTPException(400, str(exc))
    finally:
        await conn.close()
    return {"ok": True, "id": lid}


@router.post("/queues/{name}/links/{link_id}/delete")
async def delete_link(name: str, link_id: int, request: Request):
    """Remove one link. ⚠ Scoped to the queue, so an id cannot cross queues."""
    await require_editor(request)
    q = rq.REGISTRY.get(name)
    if not q:
        raise HTTPException(404, f"unknown queue {name!r}")
    conn = await _conn()
    try:
        gone = await rq.remove_link(conn, q.name, link_id)
    finally:
        await conn.close()
    if not gone:
        raise HTTPException(404, "no such link on this queue")
    return {"ok": True}


@router.post("/queues/{name}/links/{link_id}/source")
async def flag_link_source(name: str, link_id: int, request: Request,
                           payload: dict = Body(default={})):
    """Mark or unmark a link as one of this item's Source clauses.

    ⚠ THE REVIEWER PICKS. Promoting every link automatically would publish leads
    and half-read pages as provenance under "Source:", on a seed row making a
    claim about a named City program or vendor.
    """
    await require_editor(request)
    q = rq.REGISTRY.get(name)
    if not q:
        raise HTTPException(404, f"unknown queue {name!r}")
    want = bool((payload or {}).get("is_source", True))
    conn = await _conn()
    try:
        ok = await rq.set_link_source(conn, q.name, link_id, want)
    finally:
        await conn.close()
    if not ok:
        raise HTTPException(404, "no such link on this queue")
    return {"ok": True, "is_source": want}
