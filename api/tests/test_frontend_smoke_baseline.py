"""The frontend page-family baseline must match the extractor, in ORDER.

⚠⚠ THIS EXISTS BECAUSE A CORRECT SET IN THE WRONG ORDER FAILED CI AND MY OWN
CHECK MISSED IT. Renaming /master-agreements to /agreements, I inserted the new
row where the old one sat rather than where the extractor emits it. The smoke
diffs line by line, so a row in the right set at the wrong position reads as one
deletion plus one insertion — and my local check piped BOTH sides through
`sort`, which makes an ordering defect invisible by construction. A probe that
normalises away the property under test cannot see it fail.

⚠ This checks the URL column only. The STATUS column is an observation of what
each page does on CI's empty database, and asserting those here would either
duplicate the smoke or encode this machine's data — see the baseline's own
header for why it is a diff rather than a list of expected values.
"""
import io
import os
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, 'scripts/frontend-smoke.sh')
BASELINE = os.path.join(ROOT, 'scripts/frontend-smoke-baseline.tsv')


def _baseline_urls():
    out = []
    for line in io.open(BASELINE, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line.strip() or line.startswith('#'):
            continue
        status, url = line.split('\t', 1)
        out.append((status, url))
    return out


def _extractor_urls():
    r = subprocess.run(['bash', SCRIPT, '--urls'], cwd=ROOT,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        pytest.skip(f'the smoke script could not list its URLs: {r.stderr[-300:]}')
    return [u for u in r.stdout.split('\n') if u.strip()]


def test_the_baseline_lists_exactly_the_urls_the_smoke_probes_in_the_same_order():
    """⚠ ORDER, not just membership. `sorted(a) == sorted(b)` passes on the
    defect this guard was written for."""
    rows = _baseline_urls()
    assert rows, 'the baseline has no rows — it would diff clean against anything'
    base = [u for _, u in rows]
    live = _extractor_urls()
    assert base == live, (
        'the baseline and the smoke script disagree.\n'
        f'  only in baseline: {[u for u in base if u not in live]}\n'
        f'  only in script:   {[u for u in live if u not in base]}\n'
        f'  first position that differs: '
        f'{next((i for i, (a, b) in enumerate(zip(base, live)) if a != b), "none")}')


def test_every_baseline_row_carries_a_plausible_status():
    """⚠ A row whose status is not a real HTTP code would make the diff pass
    against nothing forever."""
    for status, url in _baseline_urls():
        assert status.isdigit() and 100 <= int(status) <= 599, (status, url)


def test_a_renamed_path_keeps_a_row_for_its_redirect():
    """⚠⚠ THE OLD PATH MUST STAY PROBED. This section renames URLs and 302s the
    old ones — /expiring, /licenses and now /master-agreements — and each of
    those redirects is the only thing keeping existing links alive. Dropping the
    row would let a future change turn one into a 404 unnoticed."""
    rows = dict((u, s) for s, u in _baseline_urls())
    for old in ('/research/digital-reform/expiring',
                '/research/digital-reform/licenses',
                '/research/digital-reform/master-agreements'):
        assert rows.get(old) == '302', f'{old} is no longer recorded as a redirect'
