"""The public snapshot never publishes the repo's internal status docs.

`scripts/sync-public.sh` removes every EXCLUDE entry (a glob, relative to the
repo root) from the staged public tree. CONTINUE.md and CONTINUE-CAPITAL.md were
written after the list was, and a 2026-09-24 dry run would have published both
for the first time. This expands the real list against the real tree.
"""

import fnmatch
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), '..', '..')


def _excludes():
    src = open(os.path.join(ROOT, 'scripts', 'sync-public.sh')).read()
    body = src[src.index('EXCLUDE=('):]
    body = body[:body.index('\n)\n')]
    body = '\n'.join(l.split('#', 1)[0] for l in body.splitlines())
    return re.findall(r'"([^"]+)"', body)


def _excluded(path):
    return any(fnmatch.fnmatch(path, p) for p in _excludes())


def test_every_top_level_status_doc_is_excluded():
    docs = [f for f in os.listdir(ROOT) if re.match(r'(CONTINUE|CLAUDE).*\.md$', f)]
    assert 'CONTINUE.md' in docs, 'non-vacuity: the repo has no CONTINUE.md to check'
    leaked = [d for d in docs if not _excluded(d)]
    assert not leaked, f'the public sync would publish internal status docs: {leaked}'


def test_the_list_parses():
    ex = _excludes()
    assert 'CLAUDE.md' in ex and 'app/.env.default' in ex, 'EXCLUDE failed to parse'
