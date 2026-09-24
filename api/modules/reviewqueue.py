"""DRAFT — one review contract for every human-judgement queue in this repo.

⚠ THIS IS A PROPOSAL. Nothing imports it yet and no UI exists. It is here to
answer one question before anything is built: can a SINGLE contract serve queues
whose decisions have genuinely different shapes? It is drafted against the two
most different ones we have.

THE PROBLEM IT IS FOR
=====================
Measured on prod 2026-08-29, each queue with ITS OWN predicate, **225 items are
awaiting human judgement**:

    program_name_candidates        132   is_program IS TRUE
    license_replacement_candidate   74   tier <> 'curated'
    org_vendor_crosswalk            19   candidate id set, link column NULL
    nyc_org_crosswalk                0   306 of 306 OTI records are linked
    nycha_vendor_crosswalk           0   fully worked in #155

⚠⚠ THIS DRAFT FIRST SAID 2,909, AND THE CORRECTION IS THE ARGUMENT FOR THE
CONTRACT. That figure counted `curated IS NOT TRUE` everywhere, which conflates
AUTO-DECIDED with AWAITING REVIEW — NYCHA alone contributed 1,796 of it against a
true queue of 0. A second pass said 312, carrying 142 for OTI, which measures 0
today. Three figures in three days, and the queues barely moved: the predicate
was being re-invented at each measurement, which is exactly what this contract
exists to stop. **A queue's awaiting-review predicate must live in code, once,
owned by the queue.** See docs/REVIEW-APP-SCOPE.md §2.

They share a shape — a generator emits candidates with evidence, a human decides,
the decision lands in a version-controlled seed, and ONLY `curated` renders — but
they share no vocabulary. The schema spells the same idea six ways (`match_tier`,
`tier`, `curated`, `is_program`, `confidence`, `candidate_supplier_id`) across 26
columns. That is why there is no review UI: there is nothing common to build one
against. **The contract is the work; the interface is easy afterwards.**

THE FACTORING, AND WHY IT IS THIS ONE
=====================================
The contract owns the REVIEW PROTOCOL. Each queue owns its SERIALIZATION. That
split is forced by the data: the two queues drafted here are not variations of
one decision, they are different decisions.

    NYCHA vendors    "is this NYCHA vendor the same firm as this PASSPort
                     vendor?"  -> a MATCH, whose rejection must be recordable
                     (a curated NO-MATCH) or the same 1,796 questions return on
                     every rebuild
    program names    "is this token the name of a program the City runs?"
                     -> a CLASSIFICATION, where the useful decision is often
                     AMEND (kind: system -> vehicle), not accept/reject

A contract that only had accept/reject would fit the first and mangle the second.
Hence three verbs, and an `amend` that carries a value.

⚠⚠ THE SEED PATH IS PART OF THE CONTRACT. Every queue must declare
`seed_in_git`, because a review tool that writes decisions somewhere they can be
lost is worse than no tool: it makes losing them cheap.

⚠ This draft first reported the NYCHA seed as NOT in git, holding 212 decisions
on the prod box alone. **That was already fixed by #320**, which rescued them:
`api/seed/nycha_curated_xwalk.csv` is version-controlled, holds 214 rows, and the
builder defaults to it. Corrected here because `seed_in_git` exists to surface a
defect, and reporting a FIXED defect as open teaches the next reader the wrong
thing about the safest queue we have.
"""

import dataclasses
import io
import os
import sys
import typing

# ⚠ This module is loaded BY PATH in tests (conftest.py replaces the `modules`
# package with a MagicMock, so a package import would yield a mock that
# satisfies anything). Adding its own directory makes a sibling import resolve
# in both worlds.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import contractkind
except ImportError:                                     # pragma: no cover
    from modules import contractkind


# The four verbs. `amend` carries a value; the others do not.
#
# ⚠⚠ `reject` AND `dismiss` ARE NOT THE SAME DECISION, and collapsing them
# breaks in one of two ways. `reject` is a considered NO about a real proposal:
# it MUST write a seed row, or the generator re-proposes it forever — the NYCHA
# NO-MATCH marker is why 110 rejections suppress 211 re-proposals per rebuild.
# `dismiss` is for spam, abuse or off-topic input, which only exists once an
# untrusted person can propose: it must NEVER write a seed row, because a public
# submission is never regenerated and committing spam to a version-controlled
# CSV would be actively wrong.
#
# Get it wrong and you either pollute the seed with junk or re-surface the same
# junk forever. See docs/REVIEW-APP-SCOPE.md §5.3.
ACCEPT, REJECT, AMEND, DISMISS = "accept", "reject", "amend", "dismiss"
VERBS = (ACCEPT, REJECT, AMEND, DISMISS)

# Verbs that MUST produce a seed row, and verbs that must NOT.
SEEDING_VERBS = (ACCEPT, REJECT, AMEND)
NON_SEEDING_VERBS = (DISMISS,)


@dataclasses.dataclass(frozen=True)
class Evidence:
    """One labelled fact shown to the reviewer.

    ⚠ Ordered and explicit rather than a free dict: the reviewer's job is to
    judge, and what they are shown IS the judgement. A queue that hides its
    weakest evidence produces confident wrong decisions.
    """
    label: str
    value: str
    kind: str = "text"          # text | number | money | link | code
    href: str = ""              # ⚠ set only when it resolves UNAMBIGUOUSLY


# Who proposed this, which is what sets the review bar.
#
# ⚠⚠ THE CONTRACT ORIGINALLY MODELLED WHAT WAS PROPOSED AND NOT WHO PROPOSED IT.
# For a generator that is implicit — it is always us. The moment a person can
# submit through the front end it becomes the most important field on the record:
# `confidence` and `why` are a generator's self-assessment and mean nothing
# coming from an anonymous submitter, who instead owes a SOURCE.
GENERATOR, PUBLIC = "generator", "public"
PROPOSERS = (GENERATOR, PUBLIC)


@dataclasses.dataclass(frozen=True)
class Item:
    """One thing awaiting a decision."""
    queue: str
    item_id: str                # stable within the queue, survives a rebuild
    subject: str                # what is being decided ABOUT
    proposal: str               # what the generator suggests, for display
    proposal_value: typing.Any  # ...and machine-readable
    confidence: str             # high | medium | low | none
    why: str                    # the generator's own reasoning, one sentence
    evidence: typing.Sequence[Evidence] = ()
    # ⚠ A TABLE, not more Evidence. `Evidence` is one labelled FACT; the records
    # a candidate matched are rows with shared columns, and squeezing them into
    # labelled facts would lose the alignment that makes a table readable. The
    # queue owns what its records are and what the columns mean; the view owns
    # rendering them, so a second queue can show its own records with no view
    # change.
    records: typing.Sequence[dict] = ()
    record_columns: typing.Sequence[tuple] = ()   # (key, label, align)
    records_note: str = ""
    proposed_by: str = GENERATOR
    source_url: str = ""        # ⚠ REQUIRED for a public proposal — see below

    def __post_init__(self):
        if self.proposed_by not in PROPOSERS:
            raise ValueError(
                f"unknown proposer {self.proposed_by!r}; expected {PROPOSERS}")
        # ⚠ A claim about a named vendor or a named person with no provenance is
        # not publishable here — the Gartner rule. A generator's provenance is
        # its own code; a person's is a URL.
        if self.proposed_by == PUBLIC and not self.source_url:
            raise ValueError(
                "a public proposal must carry a source_url: an unsourced claim "
                "about a named vendor or person cannot be published from here")


@dataclasses.dataclass(frozen=True)
class Decision:
    item_id: str
    verb: str                   # one of VERBS
    value: typing.Any = None    # required for AMEND, ignored otherwise
    note: str = ""
    actor: str = ""

    def __post_init__(self):
        if self.verb not in VERBS:
            raise ValueError(f"unknown verb {self.verb!r}; expected one of {VERBS}")
        if self.verb == AMEND and self.value is None:
            raise ValueError("an amend decision must carry a value")
        # ⚠ A dismissal is not a judgement about the subject, so it has nothing
        # to carry. Allowing a value invites it being serialized into a seed.
        if self.verb == DISMISS and self.value is not None:
            raise ValueError(
                "a dismiss decision carries no value; it is database-only and "
                "must never reach a seed")


class Queue:
    """What a queue must provide to be reviewable.

    ⚠ Deliberately NOT an ORM or a base class with behaviour. A queue already has
    a builder that owns its SQL, its tiers and its seed format; this describes
    what a reviewer needs from it and nothing else. Subclassing anything richer
    would mean re-implementing invariants in a second place, which is the defect
    `/admin/orgs` exists to avoid ("a pure consumer of the API — no invariant is
    re-implemented in the UI").
    """

    name: str = ""
    question: str = ""          # the question a reviewer is answering, verbatim
    seed_path: str = ""         # where accepted decisions must land
    # ⚠⚠ A REJECTION OFTEN BELONGS IN A DIFFERENT FILE, and the draft got this
    # wrong. Its seed_rows emitted rule="rejected" into the curated seed — a
    # rule `load_curated` does not accept, so the row was SKIPPED and the
    # rejection did nothing while looking recorded. A curated seed says what a
    # program IS; a rejection says what a candidate is NOT, and the thing that
    # must read it is the candidate GENERATOR, not the membership builder.
    reject_seed_path: str = ""  # "" means rejections go to seed_path
    seed_in_git: bool = False   # ⚠ False is a DEFECT to surface, not a setting
    # ⚠⚠ Does an UNREVIEWED candidate sit in the column consumers join on?
    # If False, safety depends on every consumer remembering to filter the tier —
    # and one missed filter publishes an unreviewed match (#146). Surfaced for
    # the same reason as seed_in_git: a review tool that makes decisions cheap
    # must make their blast radius visible.
    safe_by_construction: bool = True
    verbs: typing.Sequence[str] = (ACCEPT, REJECT)

    # ⚠⚠ THE BUTTON LABELS BELONG TO THE QUEUE, and hardcoding them in the view
    # put "Not a program" — program-names' wording — on the reject button of
    # EVERY queue. On org-vendors, where the question is whether a civic
    # organization is the same legal entity as a PASSPort vendor, the answer to
    # "The Nation vs NATION GROUP INC" was offered as "Not a program".
    #
    # ⚠ The default is deliberately GENERIC. A default borrowed from any one
    # queue is how this happened: it reads correctly on the queue it came from
    # and is nonsense everywhere else, which is invisible to whoever wrote it.
    verb_labels: typing.Mapping[str, str] = {}

    # ⚠⚠ THREE OF THE FOUR QUEUES ASK "IS A THE SAME AS B", AND THE ITEM VIEW WAS
    # BUILT FOR THE ONE THAT DOES NOT. `program-names` judges a token, so its
    # layout makes the subject an <h1> and the proposal a small badge beside it —
    # which, on a match queue, renders the two things being COMPARED at wildly
    # different weights, one looking like a title and the other like a tag.
    #
    # A queue that compares two named things declares what to call each side.
    # The view then renders them as a pair; queues that leave this empty keep the
    # single-subject layout, so nothing is guessed from the question text.
    pair_labels: typing.Sequence[str] = ()
    # ⚠⚠ Does this queue accept proposals from the PUBLIC? If so
    # `safe_by_construction` stops being a property to report and becomes an
    # ADMISSION GATE: an anonymous submission must be physically incapable of
    # reaching the column consumers join on, which is the org_vendor_crosswalk
    # pattern (candidate id set, link column NULL). A public queue that is not
    # safe by construction must not be admitted at all — an interface that makes
    # decisions cheap on an unsafe queue is worse than no interface.
    accepts_public: bool = False

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if getattr(cls, "accepts_public", False) and not getattr(
                cls, "safe_by_construction", False):
            raise TypeError(
                f"{cls.__name__} accepts public proposals but is not safe by "
                f"construction: an unreviewed submission would sit in the column "
                f"consumers join on, so only a tier filter would stand between "
                f"an anonymous claim and a published one (#146)")

    async def fetch(self, conn, limit: int = 50) -> typing.Sequence[Item]:
        raise NotImplementedError

    def seed_path_for(self, verb: str) -> str:
        """Which seed a decision of this verb belongs in."""
        if verb == REJECT and self.reject_seed_path:
            return self.reject_seed_path
        return self.seed_path

    def seed_key(self, item: "Item") -> str:
        """The string to look up in `already_decided()` for this item.

        ⚠⚠ FOUND BY EXERCISING A NEW QUEUE, NOT BY READING THE CODE. The router
        used to compare `item.subject` against the seeded set, which is right
        for a queue whose seed is keyed on the NAME (program-names) and silently
        wrong for one keyed on an ID. org-vendors keys `org_vendor_curated.csv`
        on `org_id` — deliberately, because an org's NAME is editable and its id
        is the join key — so every item would have read as unseeded and a
        reviewer would be re-asked questions the seed already answers.

        Defaults to the subject so no existing queue changes behaviour; the
        queue that knows its seed's key overrides it.
        """
        return (item.subject or "").strip().lower()

    async def already_decided(self, conn) -> typing.AbstractSet[str]:
        """item_ids this queue's SEED already settles.

        ⚠⚠ "DECIDED" HAS TWO SOURCES AND A REVIEW TOOL MUST HONOUR BOTH.
        `review_decision` holds what a reviewer has just chosen and not yet
        exported; the SEED holds what was settled before — including decisions
        made by hand, outside any tool. Measured 2026-08-30: 10 of the 132
        program-name candidates were already curated into
        `program_curated.csv`. A queue that reported 132 undecided would put a
        reviewer through ten questions the project has already answered, and
        invite a contradictory second answer.

        Default empty: a queue that cannot tell says so rather than guessing.
        """
        return frozenset()

    def seed_rows(self, item: Item, decision: Decision) -> typing.Sequence[list]:
        """Serialize ONE decision into the queue's seed CSV row(s).

        ⚠⚠ A REJECTION MUST PRODUCE A ROW, NOT SILENCE. If rejecting writes
        nothing, the next rebuild re-proposes the same candidate and the reviewer
        answers the same 1,796 questions forever. The NYCHA crosswalk already
        solved this with a NO-MATCH marker (`-`), and that precedent is why
        `reject` is a first-class verb here rather than "just don't accept".
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# QUEUE 1 — a MATCH decision, with a recordable rejection.
# ---------------------------------------------------------------------------

class NychaVendorQueue(Queue):
    name = "nycha-vendors"
    verb_labels = {ACCEPT: "Yes \u2014 same firm",
                   REJECT: "No \u2014 different firms"}
    pair_labels = ("NYCHA vendor", "PASSPort vendor")
    question = "Is this NYCHA vendor the same firm as this PASSPort vendor?"
    # ✅ IN GIT since #320 rescued 214 decisions off the prod box; the builder
    # defaults to this path. This draft first reported it as not in git.
    seed_path = "api/seed/nycha_curated_xwalk.csv"
    seed_in_git = True
    # ⚠⚠ FALSE, AND MEASURED: `nycha_vendor_crosswalk` has NO candidate column.
    # An unreviewed fuzzy match is written straight into `passport_supplier_id`,
    # the column every consumer joins on, so nothing but a tier filter stands
    # between a guess and a published claim. The org<->vendor crosswalk was built
    # later precisely to avoid this — it holds candidates in
    # `candidate_supplier_id` with the link column NULL, so a join CANNOT go
    # wrong. This queue is the reason that pattern exists.
    safe_by_construction = False
    verbs = (ACCEPT, REJECT)

    async def fetch(self, conn, limit=50):
        rows = await conn.fetch("""
            SELECT nycha_vendor_name, passport_supplier_id, passport_vendor_name,
                   confidence, match_score
              FROM nycha_vendor_crosswalk
             WHERE curated IS NOT TRUE AND confidence = 'fuzzy-review'
             ORDER BY match_score DESC NULLS LAST
             LIMIT $1""", limit)
        out = []
        for r in rows:
            # ⚠ There is no candidate column — see safe_by_construction above.
            sid = r["passport_supplier_id"]
            out.append(Item(
                queue=self.name,
                item_id=r["nycha_vendor_name"],
                subject=r["nycha_vendor_name"],
                proposal=r["passport_vendor_name"] or "(no candidate)",
                proposal_value=sid,
                confidence="medium" if (r["match_score"] or 0) >= 0.9 else "low",
                why=f"{r['confidence']} match, score {r['match_score'] or 0:.3f}",
                evidence=(
                    Evidence("NYCHA name", r["nycha_vendor_name"]),
                    Evidence("PASSPort name", r["passport_vendor_name"] or "—"),
                    Evidence("score", f"{r['match_score'] or 0:.3f}", "number"),
                    Evidence("supplier id", str(sid or "—"), "code"),
                )))
        return out

    def seed_rows(self, item, decision):
        # ⚠ THE NO-MATCH MARKER IS THE WHOLE POINT of a reject row: it both
        # prevents linking AND stops the pair returning to the queue forever.
        sid = "-" if decision.verb == REJECT else str(item.proposal_value or "-")
        return [[item.item_id, sid, decision.note]]


# ---------------------------------------------------------------------------
# QUEUE 2 — a CLASSIFICATION, where AMEND is the useful verb.
# ---------------------------------------------------------------------------

class ProgramNameQueue(Queue):
    name = "program-names"
    # ⚠ Its existing wording, kept verbatim — this queue is where "Not a program"
    # is correct, and it is the only one.
    verb_labels = {ACCEPT: "Accept", REJECT: "Not a program",
                   AMEND: "Amend to the kind above"}
    question = "Is this token the name of a program or system the City runs?"
    seed_path = "api/seed/program_curated.csv"
    # ⚠ Read by `build_program_name_candidates`, which EXCLUDES these names from
    # the candidate list. That is what makes a rejection stick: the membership
    # builder has no use for one, and without a reader the file would be the
    # "seed nothing reads" defect this repo has already paid for.
    reject_seed_path = "api/seed/program_name_rejected.csv"
    seed_in_git = True
    # ⚠ AMEND matters here in a way it does not for a match: the common correction
    # is not "wrong" but "wrong KIND" — a `system` that is really a `vehicle`.
    # Collapsing that to reject would discard the reviewer's actual finding.
    verbs = (ACCEPT, REJECT, AMEND)

    async def _title_rows(self, conn, titles):
        """{title: /procurement/contract/<ctr_id>} for titles that resolve to ONE
        contract.

        ⚠ ONE QUERY FOR THE WHOLE PAGE, not one per item: this runs for every
        candidate on the list view, and 132 round trips to decorate evidence
        would be a self-inflicted N+1 on a page that already works.

        ⚠⚠ AN AMBIGUOUS TITLE IS LEFT UNLINKED, deliberately. `contracts` holds
        one row per AMENDMENT and each carries its own `ctr_id`, so a repeated
        title has several. Linking to an arbitrary one of them sends a reviewer
        to a contract that is not the one the evidence meant — the DOS-crosswalk
        rule, where an ambiguous name stays unlinked rather than resolving to a
        guess. Measured on the NG911 set: 126 distinct titles, 0 ambiguous, so
        this costs nothing today and cannot mislead later.
        """
        if not titles:
            return {}
        try:
            rows = await conn.fetch(
                """SELECT contract_title,
                          min(ctr_id::text)          AS ctr,
                          count(DISTINCT ctr_id)     AS n,
                          min(agency)                AS agency,
                          min(contract_id)           AS contract_id,
                          max(start_date)            AS start_date,
                          max(end_date)              AS end_date,
                          max(coalesce(current_amount, award_amount, 0)) AS amount
                     FROM contracts
                    WHERE contract_title = ANY($1::text[])
                      AND ctr_id IS NOT NULL
                    GROUP BY contract_title""", list(titles))
        except Exception:                               # noqa: BLE001
            # ⚠ WARNING, not an error: the panel degrades to plain titles, which
            # is what it was before this existed. A missing link must not cost a
            # reviewer the evidence itself.
            return {}
        out = {}
        for r in rows:
            if r["n"] != 1:
                continue                    # ambiguous — see the docstring
            amount = float(r["amount"] or 0)
            # ⚠⚠ A CEILING IS NOT SPEND. A master agreement's figure is headroom
            # agencies buy against, drawn down under other ids — #261/#294/#301,
            # the same defect found three times. The row says WHICH, and the two
            # are never added, because a reviewer eyeballing a column of numbers
            # would otherwise read a $400M undrawn ceiling as money spent.
            master = contractkind.is_master(r["contract_id"])
            start = str(r["start_date"] or "")[:10]
            end = str(r["end_date"] or "")[:10]
            # ⚠ Composed server-side so the view stays dumb, and with a plain
            # ASCII hyphen rather than an en dash — these pages follow the
            # repo's ASCII rule (#66), and an entity would trip the
            # entity-free guard other views carry.
            term = f"{start} - {end}" if (start and end) else (start or end)
            out[r["contract_title"]] = {
                "href": f"/procurement/contract/{r['ctr']}",
                "agency": r["agency"] or "",
                "start": start,
                "end": end,
                "term": term,
                "amount": amount,
                "is_ceiling": master,
            }
        return out

    async def fetch(self, conn, limit=50):
        rows = await conn.fetch("""
            SELECT name_key, display, kind, confidence, why, examples,
                   n_contracts, n_vendors, n_agencies, total_value
              FROM program_name_candidates
             WHERE is_program IS TRUE
             ORDER BY total_value DESC
             LIMIT $1""", limit)
        wanted = set()
        for r in rows:
            for t in (r["examples"] or "").split(" | ")[:5]:
                if t.strip():
                    wanted.add(t.strip())
        links = await self._title_rows(conn, wanted)
        out = []
        for r in rows:
            ev = [Evidence("contracts", str(r["n_contracts"]), "number"),
                  Evidence("vendors", str(r["n_vendors"]), "number"),
                  Evidence("agencies", str(r["n_agencies"]), "number"),
                  Evidence("value", f"${(r['total_value'] or 0)/1e6:,.1f}M", "money")]
            recs = []
            for t in (r["examples"] or "").split(" | ")[:5]:
                t = t.strip()
                if not t:
                    continue
                row = dict(links.get(t) or {})
                row["title"] = t
                recs.append(row)
            out.append(Item(
                queue=self.name, item_id=r["name_key"], subject=r["display"],
                proposal=r["kind"] or "unclear", proposal_value=r["kind"],
                confidence=r["confidence"] or "none", why=r["why"] or "",
                evidence=tuple(ev),
                records=tuple(recs),
                record_columns=(("title", "Contract", "left"),
                                ("agency", "Agency", "left"),
                                ("term", "Term", "left"),
                                ("amount", "Amount", "right")),
                # ⚠ Says it is a SAMPLE. The extractor stores up to 5 examples,
                # and a table of five under a heading reading "contracts it
                # matched" would imply the name matched five.
                records_note="Up to five examples of the contracts this name "
                             "matched, not the full set."))
        return out

    async def already_decided(self, conn):
        """Names whose token rule is already in the curated seed.

        ⚠ Matched on the TOKEN value, not the slug, and that is exact rather
        than lucky: `seed_rows` below writes the token as the lowercased name,
        so `ACCESS HRA` -> `access hra` is the same string on both sides. Slugs
        are not (`access-hra`), and a fuzzy name match would be a guess.
        """
        try:
            from build_program_groups import load_curated
        except ImportError:                             # pragma: no cover
            return frozenset()
        tokens = set()
        for p in load_curated().values():
            tokens.update(t.strip().lower() for t in p.get("tokens", []) if t.strip())
        return frozenset(tokens)

    def seed_rows(self, item, decision):
        # ⚠ A program row is a RULE that generates membership, not a link — so an
        # accepted name becomes a `token` rule. This is why serialization belongs
        # to the queue: the NYCHA row above is a pair, and this is a rule.
        slug = item.item_id.lower()
        if decision.verb == REJECT:
            # ⚠⚠ A DIFFERENT FILE AND A DIFFERENT SHAPE. This used to emit
            # rule="rejected" into the curated seed, which `load_curated`
            # refuses — so the row was skipped and the rejection did nothing
            # while looking recorded. It now goes to reject_seed_path, whose
            # columns are (name, reason, decided_by), and the candidate builder
            # reads it. Same reasoning as the NYCHA NO-MATCH marker: a rejection
            # recorded as silence comes back every rebuild.
            return [[item.subject,
                     decision.note or "not the name of a program or system",
                     decision.actor]]
        kind = decision.value if decision.verb == AMEND else item.proposal_value
        return [[slug, item.subject, "token", item.item_id.lower(),
                 decision.note or f"kind={kind}"]]


# ---------------------------------------------------------------------------
# QUEUE 3 — a MATCH decision, on the pattern the NYCHA queue wishes it had.
# ---------------------------------------------------------------------------

class OrgVendorQueue(Queue):
    name = "org-vendors"
    question = "Is this civic organization the same entity as this PASSPort vendor?"
    verb_labels = {ACCEPT: "Yes \u2014 same entity",
                   REJECT: "No \u2014 different entities"}
    pair_labels = ("Civic organization", "PASSPort vendor")
    seed_path = "api/seed/org_vendor_curated.csv"
    seed_in_git = True
    # ⭐ TRUE, and this table is why the property is worth reporting at all.
    # An unreviewed match sits in `candidate_supplier_id` while the column every
    # consumer joins on — `passport_supplier_id` — stays NULL, so a join CANNOT
    # publish a guess. `routers/oce.py`'s vendor-profile reverse lookup runs
    # `WHERE passport_supplier_id = $1` with NO tier filter and is correct
    # anyway. That is the contrast with nycha-vendors above, where safety rests
    # entirely on every consumer remembering to filter.
    safe_by_construction = True
    verbs = (ACCEPT, REJECT)

    async def fetch(self, conn, limit=50):
        rows = await conn.fetch("""
            SELECT org_id, org_name, matched_variant, candidate_supplier_id,
                   vendor_name, match_tier, match_score
              FROM org_vendor_crosswalk
             WHERE candidate_supplier_id IS NOT NULL
               AND passport_supplier_id IS NULL
             ORDER BY match_score DESC NULLS LAST, org_name
             LIMIT $1""", limit)
        out = []
        for r in rows:
            score = r["match_score"] or 0
            out.append(Item(
                queue=self.name,
                item_id=str(r["org_id"]),
                subject=r["org_name"] or str(r["org_id"]),
                proposal=r["vendor_name"] or "(no candidate)",
                proposal_value=r["candidate_supplier_id"],
                # ⚠ The GENERATOR's self-assessment, never a measurement. A
                # `suffix-review` match scoring 1.000 is still a guess about
                # two legal names, which is the whole reason these are held.
                confidence="medium" if score >= 0.95 else "low",
                why=f"{r['match_tier']} match, score {score:.3f}",
                evidence=(
                    Evidence("Org name", r["org_name"] or "—"),
                    Evidence("Name the match used", r["matched_variant"] or "—"),
                    Evidence("PASSPort vendor", r["vendor_name"] or "—"),
                    Evidence("Match tier", r["match_tier"] or "—"),
                    Evidence("Score", f"{score:.3f}", "number"),
                    Evidence("Supplier id", str(r["candidate_supplier_id"] or "—"),
                             "code"),
                    Evidence("Org page", f"/o/{r['org_id']}", "link",
                             f"/o/{r['org_id']}"),
                )))
        return out

    def seed_key(self, item):
        # ⚠ The seed is keyed on org_id, not the org name: a name is editable
        # (display_name exists precisely because renaming one breaks joins) and
        # the id is what the builder writes.
        return item.item_id.strip().lower()

    async def already_decided(self, conn):
        """org_ids the curated seed already settles — links AND rejections.

        ⚠ A rejection in this seed is an id of `-`, and it must count as
        decided: it exists precisely so the pair never returns to the queue.
        Reading only the linked rows would re-ask every question a human has
        already answered NO to, which is the 110 NYCHA no-match markers'
        lesson at a second table.
        """
        settled = set()
        for row in _seed_rows_of(self.seed_path):
            if row and row[0].strip():
                settled.add(row[0].strip().lower())
        return frozenset(settled)

    def seed_rows(self, item, decision):
        # ⚠ `-` is the NO-MATCH marker the builder already understands: it
        # records the rejection AND stops the pair being re-proposed. A
        # rejection that writes nothing comes back every rebuild.
        sid = "-" if decision.verb == REJECT else str(item.proposal_value or "-")
        return [[item.item_id, sid, decision.note]]


# ---------------------------------------------------------------------------
# QUEUE 4 — a JUDGEMENT about a substitute, where the rejection is a FINDING.
# ---------------------------------------------------------------------------

class LicenseReplacementQueue(Queue):
    name = "license-replacements"
    verb_labels = {ACCEPT: "Yes \u2014 viable replacement",
                   REJECT: "No \u2014 not a replacement",
                   AMEND: "Amend to the candidate above"}
    pair_labels = ("Licensed product", "Open-source candidate")
    question = ("Is this open-source product a viable replacement for the "
                "licensed product the City buys?")
    seed_path = "api/seed/license_replacement_candidates.csv"
    seed_in_git = True
    # ⚠⚠ FALSE, and measured: `routers/licenses.py` selects this table
    # `WHERE tier = 'curated'`, so an unreviewed row sits in the same
    # `candidate` column consumers read and only the tier filter separates a
    # guess from a published claim about a named City product (#146). Reported
    # rather than fixed here: adding a candidate column is a builder change.
    safe_by_construction = False
    # ⚠ AMEND matters here for the same reason it does for program names: the
    # common correction is not "wrong product" but "wrong CONFIDENCE" — a
    # `strong` that is really `partial`. Collapsing that into reject would
    # discard the reviewer's actual finding and lose a real substitute.
    verbs = (ACCEPT, REJECT, AMEND)

    async def fetch(self, conn, limit=50):
        # ⚠⚠ NOT `tier <> 'curated'`. 33 of the 74 auto rows name a family that
        # ALREADY has a curated answer — the pass re-proposing what a human
        # settled, usually under a spelling variant ("Limesurvey" for the
        # curated "LimeSurvey", "NextCloud Server" for "Nextcloud"). Counting
        # those as awaiting overstates the queue by 80% and invites a
        # contradictory second answer to a published finding. Measured
        # 2026-08-31: 74 auto rows, 41 genuinely undecided families.
        rows = await conn.fetch("""
            SELECT c.family, c.candidate, c.candidate_kind, c.confidence,
                   c.licence, c.gov_adopters, c.url, c.why
              FROM license_replacement_candidate c
             WHERE c.tier <> 'curated'
               AND NOT EXISTS (SELECT 1 FROM license_replacement_candidate d
                                WHERE d.family = c.family AND d.tier = 'curated')
             ORDER BY c.gov_adopters DESC NULLS LAST, c.family
             LIMIT $1""", limit)
        out = []
        for r in rows:
            adopters = r["gov_adopters"]
            out.append(Item(
                queue=self.name,
                item_id=r["family"],
                subject=r["family"],
                proposal=r["candidate"] or "(no replacement found)",
                proposal_value=r["confidence"],
                confidence=("high" if r["confidence"] == "strong"
                            else "medium" if r["confidence"] == "partial"
                            else "low"),
                why=r["why"] or "",
                evidence=(
                    Evidence("Licensed product", r["family"]),
                    Evidence("Proposed replacement", r["candidate"] or "—"),
                    Evidence("Kind", r["candidate_kind"] or "—"),
                    Evidence("Catalogue confidence", r["confidence"] or "—"),
                    Evidence("Open-source licence", r["licence"] or "—"),
                    # ⚠ The catalogue's strongest signal, and the one the OSS
                    # work already leans on: QGIS won on 69 government
                    # adopters. Shown as a number so it cannot read as a rank.
                    Evidence("Government adopters",
                             "—" if adopters is None else str(adopters), "number"),
                    Evidence("Source", r["url"] or "—", "link", r["url"] or ""),
                ),
                source_url=r["url"] or ""))
        return out

    async def already_decided(self, conn):
        """Families the curated seed already answers.

        ⚠ Keyed on the FAMILY, not the candidate, and that is deliberate: a
        family with a curated answer is settled whatever the auto pass now
        proposes for it. The 33 overlapping families are exactly this case.

        ⚠ An empty `candidate` with confidence `none` is a curated answer too —
        somebody looked and found no substitute. That is a FINDING, and the
        Products page gives it its own band rather than hiding it, so it must
        count as decided here as well.
        """
        settled = set()
        for row in _seed_rows_of(self.seed_path):
            if row and row[0].strip() and row[0].strip().lower() != "family":
                settled.add(row[0].strip().lower())
        return frozenset(settled)

    def seed_rows(self, item, decision):
        ev = {e.label: e.value for e in item.evidence}

        def _val(label):
            v = ev.get(label, "")
            return "" if v == "—" else v

        if decision.verb == REJECT:
            # ⚠⚠ A REJECTION IS A ROW IN THE SAME SEED, NOT A SEPARATE FILE and
            # NOT SILENCE. Eight curated rows already carry an empty candidate
            # with confidence `none` — "somebody looked and found nothing" — and
            # the Products page renders them in their own band, because knowing
            # a product has no substitute is a finding. The KIND is kept, as
            # those rows keep theirs (`hosting-alt`), so the row still says what
            # kind of question was asked.
            return [[item.item_id, "", _val("Kind") or "oss-replacement",
                     "none", "", "", "",
                     decision.note or "reviewed: no viable replacement found"]]

        confidence = decision.value if decision.verb == AMEND else _val(
            "Catalogue confidence")
        return [[item.item_id, _val("Proposed replacement"),
                 _val("Kind") or "oss-replacement", confidence,
                 _val("Open-source licence"), _val("Government adopters"),
                 _val("Source"), decision.note or item.why]]


def _seed_rows_of(rel_path):
    """Parsed rows of a seed file, comments skipped, or () if it is absent.

    ⚠ Every file in api/seed carries a `#` comment header explaining its
    judgements — the NYCHA seed's header once parsed as a VENDOR NAME because a
    parser did not skip them (#320). Skip them here, once, rather than in each
    queue.

    ⚠ Absent is not an error HERE, unlike in the export: a queue that cannot
    read its seed reports nothing settled, which asks a reviewer a question they
    may have answered — annoying. The export's silent truncation destroys
    committed work, which is why that path raises instead.
    """
    import csv as _csv
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rel = rel_path[4:] if rel_path.startswith("api/") else rel_path
    full = os.path.join(here, rel)
    if not os.path.exists(full):
        return ()
    with io.open(full, encoding="utf-8") as fh:
        lines = [l for l in fh.read().splitlines()
                 if l.strip() and not l.lstrip().startswith("#")]
    return list(_csv.reader(lines))


REGISTRY = {q.name: q for q in (NychaVendorQueue(), ProgramNameQueue(),
                                OrgVendorQueue(), LicenseReplacementQueue())}


def health():
    """⚠ Report every queue whose decisions would NOT survive a rebuild.

    This exists because the failure it names is silent and expensive. A review
    tool that makes it cheap to produce decisions must make it obvious where they
    are kept, or it makes LOSING them cheap too.

    ⚠ The original example — 214 NYCHA decisions living only on the prod box — is
    FIXED (#320 rescued them into api/seed/). Every queue currently reports
    in_git, so this returns no findings today. That is the desired state, not a
    reason to delete the check: the next queue somebody adds is the one it is for.
    """
    return [{"queue": q.name, "seed": q.seed_path, "in_git": q.seed_in_git,
             "safe_by_construction": q.safe_by_construction}
            for q in REGISTRY.values()]


# ---------------------------------------------------------------------------
# Where a decision lands BEFORE it reaches a seed.
# ---------------------------------------------------------------------------

# ⚠⚠ THE APP CANNOT COMMIT, SO THIS TABLE IS THE FIRST STOP, NOT THE LAST.
# Measured on prod 2026-08-29: `git push --dry-run` on the box is refused — the
# deploy key is read-only. Decisions therefore land here, attributably, and a
# human exports them to the version-controlled seed as a pull request. That is
# the design (docs/REVIEW-APP-SCOPE.md §6.2), not a limitation to route around:
# every curated change still passes code review, and no web-facing process holds
# a credential that can write to the repository.
SCHEMA = """
CREATE TABLE IF NOT EXISTS review_decision (
    queue       text        NOT NULL,
    item_id     text        NOT NULL,
    verb        text        NOT NULL,
    value       text,
    note        text,
    actor       text        NOT NULL,
    decided_at  timestamptz NOT NULL DEFAULT now(),
    exported_at timestamptz,
    PRIMARY KEY (queue, item_id)
);
CREATE INDEX IF NOT EXISTS idx_review_decision_queue ON review_decision (queue);
CREATE INDEX IF NOT EXISTS idx_review_decision_export ON review_decision (exported_at);
"""


async def ensure_schema(conn):
    for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
        await conn.execute(stmt)


async def record(conn, queue_name: str, decision: Decision):
    """Persist ONE decision. Re-deciding an item replaces the earlier answer.

    ⚠ A reviewer changing their mind is normal and must not create a second row:
    the export reads this table, and two rows for one item would be an ambiguity
    nothing downstream could resolve. `exported_at` resets to NULL on a change,
    so a revised decision is exported again.

    ⚠ `actor` is NOT NULL and is never defaulted here. An unattributed decision
    is the shared-account defect this table exists to avoid; the caller supplies
    it from the authenticated session.
    """
    if not (decision.actor or "").strip():
        raise ValueError("a decision must carry an actor; refusing to record it "
                         "unattributed")
    await ensure_schema(conn)
    await conn.execute(
        """INSERT INTO review_decision
                (queue, item_id, verb, value, note, actor, decided_at, exported_at)
           VALUES ($1,$2,$3,$4,$5,$6, now(), NULL)
           ON CONFLICT (queue, item_id) DO UPDATE
              SET verb = EXCLUDED.verb, value = EXCLUDED.value,
                  note = EXCLUDED.note, actor = EXCLUDED.actor,
                  decided_at = now(), exported_at = NULL""",
        queue_name, decision.item_id, decision.verb,
        None if decision.value is None else str(decision.value),
        decision.note or "", decision.actor.strip())


async def decisions_for(conn, queue_name: str) -> dict:
    """{item_id: {verb, value, note, actor, decided_at, exported}} for a queue."""
    await ensure_schema(conn)
    rows = await conn.fetch(
        """SELECT item_id, verb, value, note, actor, decided_at, exported_at
             FROM review_decision WHERE queue = $1""", queue_name)
    return {r["item_id"]: {"verb": r["verb"], "value": r["value"],
                           "note": r["note"], "actor": r["actor"],
                           "decided_at": r["decided_at"].isoformat()
                           if r["decided_at"] else None,
                           "exported": r["exported_at"] is not None}
            for r in rows}


# ---------------------------------------------------------------------------
# The glossary.
# ---------------------------------------------------------------------------

# ⚠⚠ DEFINED WHERE THE TERM IS OWNED, NOT COPIED HERE. The verbs come from
# VERBS above, and the KIND vocabulary comes from the classifier's own enum
# (build_program_name_candidates.KINDS) with the definitions the MODEL was
# given, verbatim. A glossary that paraphrased those would describe a different
# classifier than the one that ran — and a second copy of a vocabulary is the
# licence-capability defect this repo has already paid for twice.
#
# What lives here is only what this contract itself owns: the review protocol.
PROTOCOL_GLOSSARY = (
    ("accept", "The proposal is right. Writes a seed row."),
    ("amend", "The name is right but the detail is wrong — most often the KIND. "
              "Carries a value, and writes a seed row."),
    ("reject", "A considered no. Writes a seed row too, so the generator stops "
               "re-proposing it; a rejection recorded as silence comes back "
               "every rebuild."),
    ("dismiss", "Spam, abuse or off-topic. Database only, NEVER a seed row — a "
                "public submission is never regenerated, so there is nothing to "
                "suppress, and committing junk to a version-controlled seed "
                "would cost the seed. Offered only on queues that accept public "
                "proposals."),
    ("awaiting", "Neither decided in this tool nor already settled by the seed."),
    ("in seed", "Already curated and published before this tool existed. "
                "Deciding again here does not remove it — edit the seed."),
    ("decided", "You (or another reviewer) answered it. Pending export; "
                "re-deciding replaces the answer."),
    ("evidence", "The labelled facts the decision is made from. Ordered and "
                 "explicit: what the reviewer is shown IS the judgement, so a "
                 "queue cannot quietly drop its weakest evidence."),
    ("confidence", "The GENERATOR's own self-assessment, not a measurement. "
                   "High confidence is not a reason to skip reading the "
                   "evidence."),
    ("seed in git", "Decisions for this queue land in a version-controlled file. "
                    "If false, that is a DEFECT to fix, not a setting — 214 "
                    "NYCHA decisions once lived only on the prod box."),
    ("safe by construction",
     "An unreviewed candidate physically cannot reach the column consumers "
     "join on. Where false, only a tier filter stands between a guess and a "
     "published claim, and one missed filter publishes it."),
    ("export", "Turning recorded decisions into a seed commit. A human step: "
               "the box's deploy key is read-only, so every curated change "
               "still passes code review."),
)


def glossary():
    """Every term the interface shows, each from the place that owns it."""
    out = [{"term": t, "definition": d, "group": "How a review works"}
           for t, d in PROTOCOL_GLOSSARY]
    try:
        from build_program_name_candidates import KINDS, PROGRAM_KINDS
    except ImportError:                                 # pragma: no cover
        return out
    for k, v in KINDS.items():
        # ⚠ The model's own wording, with its prompt indentation unwrapped.
        text = " ".join(v.split())
        if k in PROGRAM_KINDS:
            text += "  (one of the two kinds that count as a program name)"
        out.append({"term": k, "definition": text,
                    "group": "Kinds a candidate can be"})
    return out


# ---------------------------------------------------------------------------
# Related links — the research trail, and the subset that become citations.
# ---------------------------------------------------------------------------

# ⚠⚠ WHY THIS IS NOT PART OF THE DECISION. A decision is ONE answer per item;
# links are MANY, and they accumulate BEFORE the answer — often they are why a
# reviewer can answer at all. Attaching them to the decision would lose them on
# a re-decide, and would stop a reviewer parking a link without committing to a
# verdict.
#
# ⚠ NAMED `review_link`, NOT `review_citation`. The first version called it a
# citation and the section "Citations", which was wrong: most links a reviewer
# wants here are leads, context or things to come back to, and a store whose
# name asserts they are all citations misdescribes its own contents — "dead and
# wrong is worse than duplicated". Renamed while unmerged and while the only row
# was a test one; doing it after data accumulates is the #235 key-rename defect.
#
# ⭐ `is_source` IS THE REVIEWER'S CALL, and that is the point. Every curated
# program row in this repo ends "Source: https://…", and the Gartner row is the
# standing lesson that a claim about a named vendor needs provenance. But a
# research trail and a published citation are not the same thing: five leads and
# one good source is the normal shape, and a seed row reads better with the one.
# So ONLY links flagged `is_source` become Source clauses on export — the
# reviewer picks, nothing is promoted automatically.
LINK_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_link (
    id        bigserial   PRIMARY KEY,
    queue     text        NOT NULL,
    item_id   text        NOT NULL,
    url       text        NOT NULL,
    note      text        NOT NULL DEFAULT '',
    is_source boolean     NOT NULL DEFAULT false,
    actor     text        NOT NULL,
    added_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_review_link_item ON review_link (queue, item_id);
"""

# ⚠⚠ SCHEME ALLOWLIST. This is the one place a reviewer's typing reaches an
# `href`, and Blade escaping does NOT make that safe: `{{ $url }}` escapes text,
# but inside href a `javascript:` URL still executes. Allowlist, never a
# blocklist, so `data:`, `vbscript:`, `file:` and every scheme nobody has
# thought of fail closed.
ALLOWED_LINK_SCHEMES = ("http://", "https://")
MAX_LINK_URL = 2048
MAX_LINK_NOTE = 2000


def clean_link_url(url: str) -> str:
    """The URL to store, or "" if it is not one we will ever render in an href.

    ⚠ THE ALLOWLIST IS THE SECURITY PROPERTY; the strip is only usability.
    An earlier version of this docstring claimed the strip was what stopped
    " javascript:…", which is wrong and worth recording: with an allowlist a
    space-prefixed URL fails closed on its own, because it does not start with
    http. The strip exists so " https://x " — a paste with stray spaces — is
    accepted rather than silently refused. Found by mutating the strip away and
    watching the guard correctly NOT fire.
    """
    u = (url or "").strip()
    if not u or len(u) > MAX_LINK_URL:
        return ""
    low = u.lower()
    if not any(low.startswith(s) for s in ALLOWED_LINK_SCHEMES):
        return ""
    # ⚠ A control character can break out of an attribute even after escaping.
    if any(ord(c) < 32 or ord(c) == 127 for c in u):
        return ""
    return u


async def ensure_link_schema(conn):
    for stmt in [s.strip() for s in LINK_SCHEMA.split(";") if s.strip()]:
        await conn.execute(stmt)


async def add_link(conn, queue_name, item_id, url, note, actor,
                   is_source=False):
    """Attach one link + note to an item. Returns the stored row id."""
    clean = clean_link_url(url)
    if not clean:
        raise ValueError(
            "a link must be an http:// or https:// URL; anything else is "
            "refused rather than stored, because it would be rendered in a link")
    if not (actor or "").strip():
        raise ValueError("a link must carry an actor")
    await ensure_link_schema(conn)
    return await conn.fetchval(
        """INSERT INTO review_link (queue, item_id, url, note, actor, is_source)
           VALUES ($1,$2,$3,$4,$5,$6) RETURNING id""",
        queue_name, item_id, clean,
        (note or "").strip()[:MAX_LINK_NOTE], actor.strip(), bool(is_source))


async def remove_link(conn, queue_name, link_id) -> bool:
    """⚠ Scoped to the queue, so an id from one queue cannot delete another's."""
    await ensure_link_schema(conn)
    row = await conn.fetchrow(
        "DELETE FROM review_link WHERE id = $1 AND queue = $2 RETURNING id",
        int(link_id), queue_name)
    return row is not None


async def set_link_source(conn, queue_name, link_id, is_source) -> bool:
    """Mark or unmark a link as one of the item's Source clauses.

    ⚠ The reviewer's decision, never inferred. Promoting every link
    automatically would put leads and half-read pages into a published seed row
    under "Source:", which is a provenance claim about a named vendor.
    """
    await ensure_link_schema(conn)
    row = await conn.fetchrow(
        """UPDATE review_link SET is_source = $3
            WHERE id = $1 AND queue = $2 RETURNING id""",
        int(link_id), queue_name, bool(is_source))
    return row is not None


async def links_for(conn, queue_name: str) -> dict:
    """{item_id: [ {id, url, note, is_source, actor, added_at}, ... ]}.

    ⚠ Sources first, then by age: the ones a reviewer chose to stand behind
    should be the ones they see first when they come back to the item.
    """
    await ensure_link_schema(conn)
    rows = await conn.fetch(
        """SELECT id, item_id, url, note, is_source, actor, added_at
             FROM review_link WHERE queue = $1
            ORDER BY is_source DESC, added_at""", queue_name)
    out = {}
    for r in rows:
        out.setdefault(r["item_id"], []).append({
            "id": r["id"], "url": r["url"], "note": r["note"],
            "is_source": r["is_source"], "actor": r["actor"],
            "added_at": r["added_at"].isoformat() if r["added_at"] else None})
    return out


def source_clauses(links) -> list:
    """The `Source:` clauses an export should write for one item.

    ⚠⚠ THE EXPORT CONTRACT, DEFINED HERE SO IT CANNOT BE GUESSED LATER. Only
    links the reviewer flagged become Source clauses. An export that took every
    link would publish leads as provenance; one that took none would drop the
    citation the seed convention exists for.
    """
    return [f"Source: {l['url']}" for l in (links or []) if l.get("is_source")]
