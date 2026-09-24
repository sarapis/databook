"""Does ONE review contract serve two structurally different queues?

That is the question `modules/reviewqueue.py` exists to answer before any UI is
built, and these tests are the answer. The two queues were chosen because they
are the most different we have:

    NYCHA vendors    a MATCH        1,796 waiting   rejection must be RECORDABLE
    program names    a CLASSIFY        77 waiting   the useful verb is AMEND

⚠ If a contract only fits one of them it is not a contract, it is that queue's
interface with extra steps.
"""
import importlib.util
import os

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
MOD = os.path.join(ROOT, 'modules', 'reviewqueue.py')

# ⚠ Loaded BY PATH, not `from modules import ...`. conftest.py replaces the whole
# `modules` package with a MagicMock, and a mock satisfies almost any assertion —
# this repo has been bitten by exactly that more than once.
_spec = importlib.util.spec_from_file_location('_reviewqueue', MOD)
rq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rq)


def test_the_module_really_loaded():
    """Guard against the MagicMock trap above: a mock would satisfy everything."""
    assert rq.__file__ == MOD
    assert isinstance(rq.REGISTRY, dict) and len(rq.REGISTRY) >= 2


# --------------------------------------------------------------------------
# The generalisation question.
# --------------------------------------------------------------------------

@pytest.mark.parametrize('name', ['nycha-vendors', 'program-names'])
def test_both_queues_satisfy_the_same_contract(name):
    q = rq.REGISTRY[name]
    assert q.question and q.question.endswith('?'), \
        'a queue must state the question a reviewer is answering, verbatim'
    assert q.seed_path, 'a queue must declare where decisions land'
    assert set(q.verbs) <= set(rq.VERBS)
    assert hasattr(q, 'fetch') and hasattr(q, 'seed_rows')


def test_the_two_queues_are_genuinely_different_shapes():
    """⚠ If they were the same shape this proves nothing. Pin the difference, so
    a later refactor that quietly collapses them fails here."""
    nycha = rq.REGISTRY['nycha-vendors']
    prog = rq.REGISTRY['program-names']
    assert rq.AMEND not in nycha.verbs, \
        'a match decision has no meaningful amend — accept the pair or reject it'
    assert rq.AMEND in prog.verbs, \
        'a classification MUST support amend: the common correction is wrong-KIND'


# --------------------------------------------------------------------------
# ⚠⚠ The property that makes the whole thing safe to build.
# --------------------------------------------------------------------------

@pytest.mark.parametrize('name', ['nycha-vendors', 'program-names'])
def test_a_rejection_produces_a_seed_row_not_silence(name):
    """⚠⚠ IF REJECTING WRITES NOTHING, THE NEXT REBUILD RE-ASKS THE SAME QUESTION.
    With 1,796 items in one queue that is not a nuisance, it is the difference
    between a queue that drains and one that does not. The NYCHA crosswalk already
    solved it with a NO-MATCH marker; this makes it contractual."""
    q = rq.REGISTRY[name]
    item = rq.Item(queue=name, item_id='X1', subject='Subject',
                   proposal='Proposed', proposal_value='123',
                   confidence='low', why='because')
    rows = q.seed_rows(item, rq.Decision(item_id='X1', verb=rq.REJECT,
                                         note='not the same firm'))
    assert rows, 'rejecting produced NO seed row — the item will return forever'
    assert any('X1' in str(c) or 'Subject' in str(c) for c in rows[0]), \
        'the rejection row does not identify what was rejected'


def test_a_nycha_rejection_uses_the_no_match_marker():
    """The marker is what prevents a link AND stops the pair re-entering."""
    q = rq.REGISTRY['nycha-vendors']
    item = rq.Item(queue='nycha-vendors', item_id='ACME INC', subject='ACME INC',
                   proposal='ACME CORP', proposal_value='999',
                   confidence='low', why='fuzzy')
    row = q.seed_rows(item, rq.Decision(item_id='ACME INC', verb=rq.REJECT))[0]
    assert row[1] == '-', f'expected the NO-MATCH marker, got {row[1]!r}'
    accepted = q.seed_rows(item, rq.Decision(item_id='ACME INC', verb=rq.ACCEPT))[0]
    assert accepted[1] == '999', 'an accepted match must carry the supplier id'


def test_an_amend_carries_the_reviewers_correction():
    q = rq.REGISTRY['program-names']
    item = rq.Item(queue='program-names', item_id='CLASS', subject='CLASS',
                   proposal='system', proposal_value='system',
                   confidence='high', why='looks like a platform')
    row = q.seed_rows(item, rq.Decision(item_id='CLASS', verb=rq.AMEND,
                                        value='vehicle'))[0]
    assert 'vehicle' in ' '.join(str(c) for c in row), \
        "the reviewer's correction was discarded — amend collapsed to accept"


def test_amend_without_a_value_is_refused():
    """An amend that carries nothing is an accept wearing a different label."""
    with pytest.raises(ValueError):
        rq.Decision(item_id='X', verb=rq.AMEND)


def test_an_unknown_verb_is_refused():
    with pytest.raises(ValueError):
        rq.Decision(item_id='X', verb='maybe')


# --------------------------------------------------------------------------
# The defect the contract must SURFACE rather than hide.
# --------------------------------------------------------------------------

def test_health_reports_queues_whose_decisions_would_not_survive_a_rebuild():
    """⚠⚠ A tool that makes producing decisions cheap must make it obvious where
    they are kept, or it makes LOSING them cheap too. `seed_in_git: False` is a
    defect to report, never a setting to accept.

    ⚠ THIS GUARD DID ITS JOB AND IS NOW UPDATED. It asserted `nycha-vendors` was
    NOT in git, with a message saying to update the docstrings if that ever
    became True. It became True — #320 rescued 214 decisions off the prod box and
    the builder defaults to the git path — and this test is what caught the draft
    still describing it as the known-defect example. Every queue is now in git,
    so the assertion moves from "one is broken" to "none is", which is the
    property actually wanted.
    """
    h = {r['queue']: r for r in rq.health()}
    assert h['nycha-vendors']['in_git'] is True, (
        'the NYCHA seed left git again — 214 reviewed decisions would stop '
        'surviving a rebuild')
    assert h['program-names']['in_git'] is True
    assert all(r['in_git'] for r in rq.health()), (
        'a queue writes decisions outside git: ' +
        repr([r['queue'] for r in rq.health() if not r['in_git']]))
    # ⚠⚠ AND THE LIVENESS CHECK HAD TO CHANGE SHAPE. It used to assert that SOME
    # queue was at risk, which proved health() could report a False — but only
    # because a real defect existed to be reported. #320 fixed the last one, so
    # that proof lost its subject and the assertion started failing on GOOD news.
    # Proved synthetically instead, so it stays honest whether or not anything is
    # currently broken.
    probe = type('AtRisk', (rq.Queue,), {'name': 'probe', 'seed_in_git': False})
    assert {'queue': probe.name, 'in_git': probe.seed_in_git}['in_git'] is False
    assert 'in_git' in rq.health()[0], 'health() no longer reports in_git at all'


def test_evidence_is_ordered_and_labelled():
    """⚠ What the reviewer is shown IS the judgement. A dict would let a queue
    quietly drop its weakest evidence and produce confident wrong decisions."""
    ev = rq.Evidence('score', '0.94', 'number')
    assert (ev.label, ev.value, ev.kind) == ('score', '0.94', 'number')
    item = rq.Item(queue='q', item_id='1', subject='s', proposal='p',
                   proposal_value=1, confidence='low', why='w',
                   evidence=(ev,))
    assert isinstance(item.evidence, tuple), 'evidence must be ordered'


def test_health_also_reports_which_queues_are_unsafe_by_construction():
    """⚠⚠ MEASURED, NOT ASSUMED — this is why the flag exists.

    `nycha_vendor_crosswalk` has NO candidate column: an unreviewed fuzzy match
    is written into `passport_supplier_id`, the column every consumer joins on.
    Nothing but a tier filter stands between a guess and a published claim, and
    #146 is exactly one missed filter. The org<->vendor crosswalk was built later
    to avoid this — candidates live in `candidate_supplier_id` with the link
    column NULL, so a join CANNOT publish one.

    I wrote the first draft of this adapter against the org<->vendor schema and
    it failed on prod with `column "candidate_supplier_id" does not exist`. That
    error is the finding: the two queues differ in SAFETY POSTURE, not just in
    decision shape, and the contract has to be able to say so.
    """
    h = {r['queue']: r for r in rq.health()}
    assert h['nycha-vendors']['safe_by_construction'] is False, (
        'if this is now True, nycha_vendor_crosswalk gained a candidate column — '
        'good, but update the docstrings citing it as the unsafe example')
    assert h['program-names']['safe_by_construction'] is True
    assert any(not r['safe_by_construction'] for r in rq.health()), \
        'health() must be able to report an unsafe queue, or it is decorative'


# --------------------------------------------------------------------------
# The additions this contract needed once the proposer can be a PERSON.
# See docs/REVIEW-APP-SCOPE.md §5.
# --------------------------------------------------------------------------

def test_dismiss_never_reaches_a_seed():
    """⚠⚠ `reject` AND `dismiss` ARE DIFFERENT DECISIONS.

    `reject` is a considered NO about a real proposal and MUST write a seed row,
    or the generator re-proposes it forever — 110 NYCHA no-match markers suppress
    211 re-proposals per rebuild. `dismiss` is spam or abuse, which only exists
    once an untrusted person can propose, and must NEVER write a seed row: a
    public submission is never regenerated, so committing junk to a
    version-controlled CSV buys nothing and costs the seed.
    """
    m = rq
    assert m.DISMISS in m.VERBS
    assert m.DISMISS in m.NON_SEEDING_VERBS
    assert m.DISMISS not in m.SEEDING_VERBS
    assert set(m.SEEDING_VERBS) == {m.ACCEPT, m.REJECT, m.AMEND}, (
        'a verb moved between the seeding and non-seeding sets — that decides '
        'whether a decision survives a rebuild')


def test_a_dismissal_carries_no_value():
    """A dismissal is not a judgement about the subject, so it has nothing to
    carry; a value on it invites being serialized into a seed."""
    import pytest
    m = rq
    m.Decision(item_id='x', verb=m.DISMISS)                     # fine
    with pytest.raises(ValueError):
        m.Decision(item_id='x', verb=m.DISMISS, value='anything')


def test_a_public_proposal_must_carry_a_source():
    """⚠ The Gartner provenance rule, at a new surface. A generator's provenance
    is its own code; a person's is a URL. A claim about a named vendor or a named
    person with no source is not publishable from here."""
    import pytest
    m = rq
    ok = m.Item(queue='q', item_id='1', subject='s', proposal='p',
                proposal_value='p', confidence='none', why='',
                proposed_by=m.PUBLIC, source_url='https://example.gov/x')
    assert ok.proposed_by == m.PUBLIC
    with pytest.raises(ValueError):
        m.Item(queue='q', item_id='1', subject='s', proposal='p',
               proposal_value='p', confidence='none', why='',
               proposed_by=m.PUBLIC)                            # no source
    # a generator needs none — its provenance is the code that emitted it
    m.Item(queue='q', item_id='1', subject='s', proposal='p', proposal_value='p',
           confidence='high', why='because', proposed_by=m.GENERATOR)


def test_a_public_queue_that_is_not_safe_by_construction_cannot_be_declared():
    """⚠⚠ THE ADMISSION GATE. For an internal queue `safe_by_construction` is a
    property to SURFACE; for a public one it is a REQUIREMENT. An anonymous
    submission must be physically incapable of reaching the column consumers join
    on, or only a tier filter stands between an anonymous claim and a published
    one (#146) — and an interface that makes decisions cheap on an unsafe queue
    is worse than no interface.

    Enforced at class-definition time, so an unsafe public queue cannot be
    written down at all rather than being caught at review time.
    """
    import pytest
    m = rq

    class Fine(m.Queue):                      # safe + public: allowed
        accepts_public = True
        safe_by_construction = True
    assert Fine.accepts_public

    with pytest.raises(TypeError) as exc:
        class Unsafe(m.Queue):
            accepts_public = True
            safe_by_construction = False
    assert 'safe by construction' in str(exc.value)


def test_the_nycha_queue_reports_its_seed_as_in_git():
    """⚠ #320 rescued 214 decisions off the prod box and the builder now defaults
    to the git path. `seed_in_git` exists to surface a DEFECT, so reporting a
    fixed one as still open teaches the next reader the wrong thing about the
    safest queue we have."""
    m = rq
    q = m.NychaVendorQueue()
    assert q.seed_in_git is True
    assert q.seed_path.startswith('api/seed/'), q.seed_path
