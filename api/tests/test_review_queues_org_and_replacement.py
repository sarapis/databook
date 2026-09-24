"""Guards for the two queues added 2026-08-31 — org-vendors and license-replacements.

⚠ These are behavioural where they can be. `fetch()` needs a database, so the
predicates are pinned by reading the SQL the queue emits (the split this repo
already uses for the partial-index guard); everything downstream of an Item —
seed_key, seed_rows, already_decided — is exercised by calling it.
"""
import importlib.util
import io
import os
import re

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'modules', 'reviewqueue.py')


def _mod():
    """Load reviewqueue BY PATH.

    ⚠ conftest.py replaces the whole `modules` package with a MagicMock, so
    `from modules import reviewqueue` yields a mock that satisfies almost any
    assertion. This repo has paid for that twice.
    """
    spec = importlib.util.spec_from_file_location('_rq_under_test', SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert hasattr(m, 'REGISTRY'), 'the real module did not load'
    return m


def _item(mod, q, **kw):
    base = dict(queue=q.name, item_id='X', subject='X', proposal='P',
                proposal_value='v', confidence='low', why='w')
    base.update(kw)
    return mod.Item(**base)


def test_both_queues_are_registered():
    reg = _mod().REGISTRY
    assert 'org-vendors' in reg and 'license-replacements' in reg, (
        f'a queue class exists but is not in REGISTRY, so nothing serves it: '
        f'{sorted(reg)}')


def test_org_vendors_reports_itself_safe_and_the_replacement_queue_does_not():
    """⚠⚠ NOT COSMETIC — it tells the reviewer the blast radius of a mistake.

    org_vendor_crosswalk holds an unreviewed match in `candidate_supplier_id`
    while `passport_supplier_id` (the column consumers join on) stays NULL, so a
    join CANNOT publish a guess. license_replacement_candidate has no such
    column: routers/licenses.py selects it `WHERE tier = 'curated'`, so only the
    tier filter separates a guess from a published claim about a named City
    product. Claiming otherwise would be a false reassurance on the queue that
    needs care.
    """
    reg = _mod().REGISTRY
    assert reg['org-vendors'].safe_by_construction is True
    assert reg['license-replacements'].safe_by_construction is False, (
        'license-replacements claims to be safe by construction, but an '
        'unreviewed row sits in the same `candidate` column consumers read and '
        'only `WHERE tier = curated` separates them')


def test_the_replacement_queue_excludes_families_already_curated():
    """⚠⚠ `tier <> 'curated'` OVERSTATES THIS QUEUE BY 80%.

    Measured on prod 2026-08-31: 74 auto rows, but 33 of them name a family that
    ALREADY has a curated answer — the pass re-proposing what a human settled,
    usually under a spelling variant ("Limesurvey" for the curated "LimeSurvey",
    "NextCloud Server" for "Nextcloud"). 41 families are genuinely undecided.

    Counting the 33 would put a reviewer through answered questions and invite a
    contradictory second answer to a published finding — the exact defect the
    scope doc's §2 records being made three times in three days.
    """
    src = io.open(SRC, encoding='utf-8').read()
    body = src[src.index('class LicenseReplacementQueue'):]
    sql = body[body.index('await conn.fetch('):body.index('out = []')]
    norm = ' '.join(sql.split()).lower()
    assert 'not exists' in norm and "d.tier = 'curated'" in norm, (
        'the replacement queue no longer excludes families that already have a '
        'curated answer, so it re-asks settled questions')


def test_seed_key_is_the_org_id_for_org_vendors_and_the_name_elsewhere():
    """⚠⚠ THE BUG THIS METHOD EXISTS FOR, FOUND BY RUNNING A NEW QUEUE.

    routers/review.py compared `item.subject` against the seeded set. That is
    right for a seed keyed on the NAME and silently wrong for one keyed on an
    ID: `org_vendor_curated.csv` is keyed on `org_id`, deliberately, because an
    org's name is editable and its id is the join key. Every org-vendors item
    would have read as unseeded and its reviewer would be re-asked answered
    questions — invisibly, because "unseeded" is the normal state.
    """
    mod = _mod()
    ov, pn = mod.REGISTRY['org-vendors'], mod.REGISTRY['program-names']
    it = _item(mod, ov, item_id='170100266', subject='Carnegie Hall')
    assert ov.seed_key(it) == '170100266', (
        'org-vendors looks its seed up by name; the seed is keyed on org_id')
    it2 = _item(mod, pn, item_id='NG911', subject='NG911')
    assert pn.seed_key(it2) == 'ng911', 'the default seed_key changed behaviour'


def test_the_router_asks_the_queue_for_the_seed_key():
    """⚠ A queue can only own its key if the consumer uses it."""
    router = io.open(os.path.join(ROOT, 'routers', 'review.py'),
                     encoding='utf-8').read()
    assert 'q.seed_key(' in router, (
        'routers/review.py no longer asks the queue for its seed key')
    assert not re.search(r"i\.subject\.strip\(\)\.lower\(\) in seeded", router), (
        'the router compares subject against the seeded set again, which is '
        'wrong for any queue whose seed is keyed on an id')


def test_a_rejection_produces_a_row_in_the_shape_the_seed_already_uses():
    """⚠⚠ A REJECTION MUST BE A ROW, NOT SILENCE, or the next rebuild
    re-proposes it forever.

    Both shapes are the ones already in the seeds, not new inventions:
    org-vendors uses the `-` NO-MATCH marker the builder understands, and
    license-replacements uses the empty-candidate/`none` row that eight curated
    rows already carry — the Products page gives those their own band, because
    knowing a product has no substitute is a finding.
    """
    mod = _mod()

    ov = mod.REGISTRY['org-vendors']
    it = _item(mod, ov, item_id='170013103', proposal_value='1636874')
    acc = ov.seed_rows(it, mod.Decision(item_id=it.item_id, verb='accept',
                                        note='n', actor='d'))[0]
    rej = ov.seed_rows(it, mod.Decision(item_id=it.item_id, verb='reject',
                                        note='n', actor='d'))[0]
    assert acc[:2] == ['170013103', '1636874']
    assert rej[1] == '-', 'a rejected org-vendor pair does not write the NO-MATCH marker'

    lr = mod.REGISTRY['license-replacements']
    ev = (mod.Evidence('Kind', 'hosting-alt'),
          mod.Evidence('Proposed replacement', 'RapidPro'),
          mod.Evidence('Catalogue confidence', 'partial'),
          mod.Evidence('Open-source licence', 'AGPL-3.0'),
          mod.Evidence('Government adopters', '60'),
          mod.Evidence('Source', 'https://example.org'))
    it2 = _item(mod, lr, item_id='Everbridge', subject='Everbridge', evidence=ev)
    rej2 = lr.seed_rows(it2, mod.Decision(item_id='Everbridge', verb='reject',
                                          note='looked, found nothing', actor='d'))[0]
    assert len(rej2) == 8, f'the row has {len(rej2)} columns; the seed has 8'
    assert rej2[1] == '' and rej2[3] == 'none', (
        'a rejected replacement does not match the empty-candidate/none shape '
        'the eight existing curated rejections use')
    assert rej2[2] == 'hosting-alt', (
        'the rejection dropped the KIND; the existing rejection rows keep '
        'theirs, so the row still says what question was asked')


def test_amend_carries_the_reviewers_confidence_and_is_not_inert():
    """⚠ Verified against a DIFFERENT value than the item's own, because an
    amend that echoed the catalogue would look correct on any row whose
    confidence happened to match."""
    mod = _mod()
    lr = mod.REGISTRY['license-replacements']
    ev = (mod.Evidence('Proposed replacement', 'RapidPro'),
          mod.Evidence('Catalogue confidence', 'partial'),
          mod.Evidence('Kind', 'oss-replacement'))
    it = _item(mod, lr, item_id='Everbridge', subject='Everbridge', evidence=ev)
    acc = lr.seed_rows(it, mod.Decision(item_id='Everbridge', verb='accept',
                                        note='n', actor='d'))[0]
    assert acc[3] == 'partial', "accept did not carry the catalogue's confidence"
    for value in ('strong', 'adjacent'):
        row = lr.seed_rows(it, mod.Decision(item_id='Everbridge', verb='amend',
                                            value=value, note='n', actor='d'))[0]
        assert row[3] == value, (
            f'amend ignored the reviewer and wrote {row[3]!r}; the correction '
            'this queue exists for is a wrong CONFIDENCE')


def test_a_missing_seed_reports_nothing_settled_rather_than_raising():
    """⚠ The OPPOSITE of the export's rule, on purpose. A queue that cannot read
    its seed asks a question that may already be answered — annoying. The export
    silently truncating a committed seed destroys work, which is why that path
    raises. Same absent file, two correct answers."""
    mod = _mod()
    assert mod._seed_rows_of('api/seed/does_not_exist_at_all.csv') == ()


def test_the_seed_parser_skips_comment_headers():
    """⚠ Every file in api/seed carries a `#` header explaining its judgements,
    and the NYCHA seed's header once parsed as a VENDOR NAME (#320)."""
    mod = _mod()
    rows = mod._seed_rows_of('api/seed/org_vendor_curated.csv')
    assert rows, 'the curated org-vendor seed read as empty'
    assert not any(r and r[0].lstrip().startswith('#') for r in rows), (
        'a comment line was parsed as a data row')


# ⚠ ROOT here is the `api` directory, not the repo root — I assumed otherwise and
# got a FileNotFoundError, which at least fails loudly. The app tree is one level
# up.
REPO = os.path.realpath(os.path.join(ROOT, '..'))


def _read_view(name):
    with io.open(os.path.join(REPO, 'app/resources/views/review', name),
                 encoding='utf-8') as fh:
        return fh.read()


def _read_router():
    with io.open(os.path.join(ROOT, 'routers', 'review.py'), encoding='utf-8') as fh:
        return fh.read()


def test_no_queue_borrows_another_queues_button_wording():
    """⚠⚠ "Not a program" WAS ON THE REJECT BUTTON OF EVERY QUEUE.

    The item view hardcoded it, so `org-vendors` — which asks whether a civic
    organization is the same legal entity as a PASSPort vendor — offered "The
    Nation" vs "NATION GROUP INC" and a button reading *Not a program*. Reported
    by the owner looking at `/review/org-vendors/170013323`.

    A label that is correct on the queue it was written for and nonsense
    everywhere else is invisible to whoever writes it, which is why this is a
    guard and not a fix. Same family as the licence capability labels living in
    three Blade copies and being stale in all three.
    """
    mod = _mod()
    view = _read_view('item.blade.php')
    # every verb label the view can render must come from the payload
    assert "$vl['reject']" in view and "$vl['accept']" in view, (
        'the item view hardcodes a verb label again')
    for q in mod.REGISTRY.values():
        for verb, label in (q.verb_labels or {}).items():
            assert verb in q.verbs, (
                '%s labels a verb it does not accept: %s' % (q.name, verb))
    # and the one queue that legitimately says it must be the only one
    owners = [q.name for q in mod.REGISTRY.values()
              if 'not a program' in ' '.join((q.verb_labels or {}).values()).lower()]
    assert owners == ['program-names'], (
        'a queue other than program-names uses program-names wording: %s' % owners)


def test_a_match_queue_declares_what_to_call_each_side():
    """⚠⚠ THREE OF THE FOUR QUEUES ASK "IS A THE SAME AS B", AND THE ITEM VIEW WAS
    BUILT FOR THE ONE THAT DOES NOT.

    `program-names` judges a single token, so its layout makes the subject an
    <h1> and the proposal a small badge beside it. On a match queue that renders
    the two things being COMPARED at wildly different weights — one reads as a
    title, the other as a tag — which is what the owner reported.

    A comparing queue declares its two side labels; the view renders a pair only
    when they exist, so nothing is inferred from the question text.
    """
    mod = _mod()
    for name in ('org-vendors', 'nycha-vendors', 'license-replacements'):
        q = mod.REGISTRY[name]
        assert len(q.pair_labels) == 2, (
            '%s compares two named things and must label both sides' % name)
    assert not mod.REGISTRY['program-names'].pair_labels, (
        'program-names judges one token; giving it pair labels would render an '
        'empty second card')
    view = _read_view('item.blade.php')
    assert "count($pair) === 2" in view, (
        'the view no longer chooses its layout from the declared pair labels')


def test_the_labels_and_pair_reach_the_view_through_the_payload():
    """⚠ The API having a value proves nothing about the page receiving it — the
    Overview shipped a whole missing section that way."""
    router = _read_router()
    assert '"verb_labels"' in router, 'the item payload no longer serves verb labels'
    assert '"pair_labels"' in router, 'the item payload no longer serves pair labels'
    view = _read_view('item.blade.php')
    assert "$queue['verb_labels']" in view and "$queue['pair_labels']" in view, (
        'the view does not read the served labels')
