"""Guards for CI's docs-only `paths-ignore`.

WHY IT EXISTS. Measured 2026-08-26: 293 workflow runs in August at ~5.1 min wall
each, and because three jobs run in parallel the billed total lands around
3,300-4,500 minutes against the **2,000 included on `wegovnyc`'s FREE plan** — so
the allowance ran out mid-month and every job began failing in 2 seconds with no
steps and no logs. On one day alone, 4 of 6 PRs were docs- or handoff-only and
every one still built Docker images and booted the full stack.

⚠ THE SAFETY PROPERTY. GitHub skips a run only when EVERY changed file matches an
ignore pattern, so a PR touching code *and* docs still runs in full. That is what
makes this a saving rather than a coverage hole — and #280's lesson ("a job you
always see skipping is not coverage") is why the list must stay narrow: prose and
planning notes only, never anything that can change behaviour.

⚠⚠ AND THE TRAP IF THE REPO MOVES ORGS. This is safe today only because the repo
has NO required status checks — branch protection needs Pro/Team and `wegovnyc` is
on Free (verified: the branch-protection API returns 403 "Upgrade to GitHub Pro").
A REQUIRED check that never runs leaves a PR unmergeable forever. The planned
migration to the `sarapis` org (which IS on Team) would enable branch protection,
so this must be revisited then. That is recorded here rather than only in a task,
because this file is what someone reads when the filter surprises them.
"""
import os
import re

import pytest

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
CI = os.path.join(ROOT, '.github', 'workflows', 'ci.yml')

# Anything matching one of these may be skipped. Anything that can change
# BEHAVIOUR must not be here.
EXPECTED = ['docs/**', 'handoffs/**', '**.md', 'LICENSE']


def _raw():
    with open(CI, encoding='utf-8') as fh:
        return fh.read()


def _parsed():
    yaml = pytest.importorskip('yaml')
    with open(CI, encoding='utf-8') as fh:
        return yaml.safe_load(fh)


def _on(doc):
    """PyYAML resolves the bare key `on:` to the boolean True."""
    return doc.get(True) if True in doc else doc.get('on')


def test_no_yaml_anchors_anywhere_in_the_workflow():
    """⚠⚠ THE MISTAKE THIS PREVENTS, made while writing the filter. GitHub's
    workflow parser does NOT support YAML anchors/aliases, so `&name` / `*name`
    is valid YAML that GitHub rejects outright — and with CI already down there
    was no way to discover that from a run. The list is duplicated instead, and
    the duplication is pinned by the test below.
    """
    raw = _raw()
    code = '\n'.join(l for l in raw.split('\n') if not l.lstrip().startswith('#'))
    offenders = re.findall(r'(?:^|\s)([&*][A-Za-z_][\w-]*)', code)
    assert not offenders, (
        f"YAML anchors/aliases found in ci.yml ({offenders}) — GitHub's parser "
        f"does not support them and will reject the workflow")


def test_both_triggers_ignore_exactly_the_same_paths():
    """The two lists are written out twice because anchors are unusable; this is
    what stops them drifting. A push-only filter would silently keep building on
    every PR, which is where most of the spend is."""
    on = _on(_parsed())
    push = on['push'].get('paths-ignore')
    pr = on['pull_request'].get('paths-ignore')
    assert push == EXPECTED, f"push paths-ignore drifted: {push}"
    assert pr == EXPECTED, f"pull_request paths-ignore drifted: {pr}"


def test_the_filter_never_covers_anything_that_changes_behaviour():
    """⚠ The list must not grow to include code, workflows, compose or deps. A
    filter that swallows a real change turns CI into the always-skipping job #280
    was about."""
    on = _on(_parsed())
    banned = ('api/', 'app/', 'scripts/', 'nginx/', '.github/', 'docker',
              '**.py', '**.php', '**.yml', '**.yaml', '**.sh', 'dependencies')
    for trigger in ('push', 'pull_request'):
        for pat in on[trigger].get('paths-ignore') or []:
            low = pat.lower()
            for b in banned:
                assert b not in low, (
                    f"{trigger} paths-ignore contains {pat!r}, which can hide a "
                    f"behaviour change from CI entirely")


def test_the_reason_is_recorded_in_the_workflow_itself():
    """Whoever hits a skipped run should find out why in the file, not by
    archaeology — including that this is unsafe once required checks exist."""
    raw = _raw()
    assert 'paths-ignore' in raw
    assert re.search(r'required status check', raw, re.I), \
        ("ci.yml no longer warns that a REQUIRED check which never runs leaves a "
         "PR unmergeable — the trap the sarapis migration will spring")
    assert re.search(r'EVERY changed file matches', raw), \
        "ci.yml no longer records the property that makes this safe"


def test_ci_compiles_every_blade_view():
    """⚠⚠ `php -l` ON A BLADE FILE PROVES NOTHING and the frontend baseline
    cannot cover this either: a view that fails to compile 500s, and on CI's
    empty database several pages 500 for DATA reasons, so "nothing moved" is
    satisfied by a broken view. Only compiling the views finds a directive glued
    to a word character, or an `@php` inside a comment pairing with the next real
    `@endphp` — both have shipped a 500 in this repo, the second on 2026-09-16.

    ⚠ `scripts/` is NOT in the app image (its build context is `app/`), so the
    step must copy the script in; exec'ing it from the repo path silently finds
    nothing."""
    import os
    raw = _raw()
    assert 'blade-lint.php' in raw, \
        'CI no longer compiles the Blade views — a 500-on-every-request view can ship green'
    assert 'docker compose cp scripts/blade-lint.php' in raw, \
        'the Blade lint is exec\'d without being copied into the app image, where scripts/ does not exist'
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = os.path.join(root, 'scripts', 'blade-lint.php')
    assert os.path.exists(script), 'scripts/blade-lint.php is missing — the CI step cannot run'
    src = open(script, encoding='utf-8').read()
    # ⚠ A lint that checked nothing passes. The script must refuse a short scan.
    assert 'REFUSED' in src and 'count($paths) < 100' in src, \
        'the Blade lint no longer refuses a scan that found almost no views'
