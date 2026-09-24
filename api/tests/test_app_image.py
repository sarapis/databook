"""Guards for the app image's apt step.

⚠⚠ THE `Acquire::Check-Valid-Until=false` FLAG IS A STOPGAP AND MUST NOT OUTLIVE
ITS CAUSE. `app/Dockerfile` is `php:7.4-fpm`, i.e. Debian bullseye, whose LTS
ended 2026-08-31; on 2026-09-07 21:13:06Z the `bullseye-security` Release file's
Valid-Until lapsed and `apt-get update` began exiting 100, breaking the app image
build on every branch at once. The flag makes apt accept that expired index.

The whole risk with a flag like this is that it becomes permanent by accident and
nobody remembers it silently disabled a check. So its lifetime is pinned to the
thing that justifies it: while the base image is still PHP 7.4 the flag must be
present (or the build is broken), and the moment the base image moves off 7.4 the
flag must be gone.

Also pinned here: no `#` comment inside a `\`-continued RUN. A comment there
swallows the lines that follow and breaks the build — hit for real while writing
the CDN-retry work (#377), and this file's own fix sits next to that exact shape.
"""

import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
DOCKERFILE = os.path.join(ROOT, 'app', 'Dockerfile')
DROP = "sed -i '/debian-security/d' /etc/apt/sources.list"
SUITE = 'debian-security'


def _read():
    with io.open(DOCKERFILE, encoding='utf-8') as fh:
        return fh.read()


def _code():
    """The Dockerfile with `#` comment lines removed.

    ⚠ Required, not tidiness: the comment explaining this workaround NAMES
    `Acquire::Check-Valid-Until`, so a whole-file scan for that string fires on
    its own explanation. This repo has paid for that mistake several times.
    """
    return '\n'.join(l for l in _read().split('\n') if not l.lstrip().startswith('#'))


def _base_tag():
    m = re.search(r'(?m)^FROM\s+php:([^\s]+)', _read())
    assert m, 'no `FROM php:…` in app/Dockerfile — this guard is looking at the ' \
              'wrong file, and a guard that finds nothing passes'
    return m.group(1)


def _runs(text):
    """Each RUN instruction as its full logical line, continuations joined."""
    out, cur = [], None
    for raw in text.split('\n'):
        if cur is not None:
            cur.append(raw)
            if not raw.rstrip().endswith('\\'):
                out.append(cur)
                cur = None
        elif raw.startswith('RUN '):
            cur = [raw]
            if not raw.rstrip().endswith('\\'):
                out.append(cur)
                cur = None
    if cur:
        out.append(cur)
    assert len(out) >= 5, 'parsed only %d RUN instructions — the scanner is wrong' % len(out)
    return out


def test_the_retired_security_suite_is_dropped_while_the_base_image_needs_it():
    """`bullseye-security` must not be an apt source while the base is PHP 7.4.

    That suite is retired twice over — expired Release AND pruned pool — so
    leaving it in place fails the build either way. Dropping it is the whole
    fix: measured, 31 of 34 packages already come from `bullseye` main and
    bullseye-updates, which are not expired, so no Check-Valid-Until override
    is needed and none should creep back in.

    Verified by reintroducing each state: the drop removed, an
    Acquire::Check-Valid-Until override added back, and the base image bumped
    with the workaround left behind.
    """
    text = _read()
    tag = _base_tag()
    apt = [' '.join(r) for r in _runs(text)
           if re.search(r'apt-get\b[^&|]*\bupdate\b', ' '.join(r))]
    assert apt, 'no apt-get update RUN found in app/Dockerfile — the scanner is wrong'

    if tag.startswith('7.'):
        assert DROP in _code(), (
            'app/Dockerfile is still on php:%s, whose %s suite is retired: its '
            'Release file expired 2026-09-07 and its pool is pruned, so an '
            'apt-get update that still lists it cannot succeed. Drop it with:\n'
            '  %s' % (tag, SUITE, DROP))
        assert 'Acquire::Check-Valid-Until' not in _code(), (
            'app/Dockerfile disables the Release freshness check, which is not '
            'needed once %s is dropped — bullseye main and bullseye-updates are '
            'not expired. Remove the override rather than carrying a disabled '
            'signature check.' % SUITE)
    else:
        assert DROP not in _code() and 'Acquire::Check-Valid-Until' not in _code(), (
            'the base image is now php:%s, so the bullseye retirement that '
            'justified dropping %s no longer applies — delete the workaround '
            'and its comment. It was only ever a stopgap.' % (tag, SUITE))


def test_the_flag_is_never_left_without_its_explanation():
    """A silently-disabled check is the thing to prevent, not the flag itself."""
    text = _read()
    if DROP not in text:
        return
    for marker in ('bullseye', 'STOPGAP', 'pruned', 'base-image move'):
        assert marker.lower() in text.lower(), (
            'app/Dockerfile drops the %s suite without saying %r — the comment '
            'is what stops a workaround becoming permanent by accident, and what '
            'records that 3 libs now install at non-security versions.'
            % (SUITE, marker))


def test_no_comment_hides_inside_a_continued_run():
    """A `#` line inside a `\\`-continued RUN swallows the rest of the command.

    It reads perfectly to a human and silently drops the lines after it. Hit for
    real in #377; the expired-release fix sits directly above such a RUN, which
    is exactly where someone would put the next explanation.
    """
    # ⚠ run[1:], NOT run[:-1]. A comment line carries no trailing `\\`, so it is
    # what TERMINATES the parsed block and therefore lands LAST — the harmful
    # case is the one a `[:-1]` slice excludes. The first draft did exactly that
    # and passed against a real reintroduction of the bug.
    for run in _runs(_read()):
        for line in run[1:]:
            assert not line.lstrip().startswith('#'), (
                'a `#` comment sits inside a continued RUN and will swallow the '
                'lines after it:\n  %s\nMove it above the RUN.' % '\n  '.join(run))
