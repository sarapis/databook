"""Guards tying `app/composer.lock` to the PHP the app image actually runs.

⚠⚠ THE LOCK WAS A PHP 8 RESOLUTION WHILE THE IMAGE WAS PHP 7.4, AND THE BUILD
WORKED AROUND IT BY DELETING THE LOCK. Measured on the lock this replaced: 13 of
its 63 packages required php ^8.x only (`brick/math ^8.2`, `symfony/string >=8.1`,
`ramsey/uuid ^8.0`, …), so `composer install` refused it outright and
`app/Dockerfile` carried `RUN rm -f composer.lock` to re-resolve from scratch.

That made the image UNREPRODUCIBLE in a way no diff could show. With no lock,
`laravel/framework` resolves to the `8.x-dev` BRANCH TIP — so two builds a week
apart could ship different framework code from an identical git tree, and the
tracked lock meanwhile documented a version that was not deployed.

WHAT THIS FILE DOES AND DELIBERATELY DOES NOT DO
================================================
It does NOT check that the lock is in sync with composer.json. Composer already
does that, and it FAILS rather than warning — measured, `composer install` exits
**4** with "Required package ... is in the lock file as X but that does not
satisfy your constraint Y", which breaks the image build. Reimplementing
composer's `content-hash` here would be a second definition of one rule, which is
how a harness comes to measure a different system than the code does.

What the build genuinely cannot catch is the workaround coming BACK: a Dockerfile
that deletes the lock builds perfectly and silently returns to re-resolving. That
is this file's main assertion.
"""

import io
import json
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
DOCKERFILE = os.path.join(ROOT, 'app', 'Dockerfile')
LOCK = os.path.join(ROOT, 'app', 'composer.lock')
JSON = os.path.join(ROOT, 'app', 'composer.json')


def _dockerfile():
    with io.open(DOCKERFILE, encoding='utf-8') as fh:
        return fh.read()


def _code():
    """The Dockerfile with `#` comment lines removed.

    ⚠ Required, not tidiness. The comment above the install step EXPLAINS the
    `rm -f composer.lock` workaround by name, so a whole-file scan for it fires
    on its own explanation. This repo has paid for that mistake repeatedly.
    """
    return '\n'.join(l for l in _dockerfile().split('\n')
                     if not l.lstrip().startswith('#'))


def _base_php():
    """The (major, minor) of the image's PHP, from `FROM php:<tag>`."""
    m = re.search(r'(?m)^FROM\s+php:(\d+)\.(\d+)', _dockerfile())
    assert m, ('no `FROM php:<major>.<minor>` in app/Dockerfile — this guard is '
               'looking at the wrong file, and a guard that finds nothing passes')
    return int(m.group(1)), int(m.group(2))


# --------------------------------------------------------------------------
# A small composer-constraint evaluator.
#
# ⚠ It is pinned by test_the_constraint_matcher_is_not_vacuous below. A matcher
# that answers True for everything is the zero-files scanner wearing a new hat:
# every assertion built on it would pass while measuring nothing.
# --------------------------------------------------------------------------

def _parse(v):
    parts = [int(x) for x in re.findall(r'\d+', v)[:3]]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _term_ok(version, term):
    term = term.strip()
    if not term or term == '*':
        return True
    m = re.match(r'^(\^|~|>=|<=|!=|<|>|=)?\s*v?([\d][\d.]*)', term)
    if not m:
        # An unparseable term is never silently treated as satisfied.
        raise ValueError('cannot parse constraint term %r' % term)
    op, num = m.group(1) or '=', _parse(m.group(2))
    digits = len(re.findall(r'\d+', m.group(2)))
    if op == '^':
        upper = (num[0] + 1, 0, 0) if num[0] else (0, num[1] + 1, 0)
        return num <= version < upper
    if op == '~':
        upper = (num[0], num[1] + 1, 0) if digits >= 2 else (num[0] + 1, 0, 0)
        return num <= version < upper
    return {
        '>=': version >= num, '<=': version <= num, '<': version < num,
        '>': version > num, '=': version == num, '!=': version != num,
    }[op]


def _hyphen_ok(version, clause):
    """Composer's hyphenated range, e.g. `7.1 - 8.3`.

    ⚠ Found by this guard failing on the real lock: `nette/schema` declares
    `7.1 - 8.3`, which plainly includes 7.4, and the first draft of the matcher
    could not read it and reported the lock broken. A right bound with fewer
    than three digits is INCLUSIVE of that whole series — `- 8.3` means up to
    and including 8.3.x, not up to 8.3.0.
    """
    lo, hi = [s.strip() for s in clause.split('-', 1)]
    lo_v, hi_v = _parse(lo), _parse(hi)
    digits = len(re.findall(r'\d+', hi))
    if digits == 1:
        upper = (hi_v[0] + 1, 0, 0)
    elif digits == 2:
        upper = (hi_v[0], hi_v[1] + 1, 0)
    else:
        upper = (hi_v[0], hi_v[1], hi_v[2] + 1)
    return lo_v <= version < upper


def _satisfies(version, constraint):
    """True when `version` satisfies a composer constraint string."""
    for clause in re.split(r'\s*\|\|?\s*', constraint.strip()):
        clause = clause.strip()
        if not clause:
            continue
        if re.match(r'^[\d.]+\s+-\s+[\d.]+$', clause):
            if _hyphen_ok(version, clause):
                return True
            continue
        terms = [t for t in re.split(r'[,\s]+', clause.strip()) if t]
        if all(_term_ok(version, t) for t in terms):
            return True
    return False


def _admits_base(constraint):
    """True when the constraint admits ANY patch release of the image's PHP.

    ⚠ The tag gives only major.minor (`php:7.4-fpm`), never the patch, so this
    asks whether the whole minor series is excluded rather than pinning a patch
    the Dockerfile does not state.
    """
    major, minor = _base_php()
    return any(_satisfies((major, minor, p), constraint) for p in range(0, 100))


def test_the_constraint_matcher_is_not_vacuous():
    """Pin the evaluator itself, in BOTH directions.

    Every other assertion in this file is only as good as this function, so it
    is checked against constraints taken from the real lock — including the 13
    php-8-only ones that caused the defect this file guards.
    """
    yes = [
        ((7, 4, 33), '^7.3|^8.0'),
        ((7, 4, 33), '^7.2.5|^8.0'),
        ((7, 4, 33), '>=7.3'),
        ((7, 4, 33), '^7.4 || ^8.0'),
        ((7, 4, 0), '~7.4'),
        ((8, 2, 1), '^7.3|^8.0'),
        ((7, 4, 33), '>=5.3.0'),
        ((7, 4, 33), '*'),
        ((7, 4, 33), '7.1 - 8.3'),     # nette/schema, in the real lock
        ((8, 3, 9), '7.1 - 8.3'),      # a partial right bound includes 8.3.x
    ]
    no = [
        ((7, 4, 33), '^8.2'),                 # brick/math, in the replaced lock
        ((7, 4, 33), '>=8.1'),                # symfony/string, same lock
        ((7, 4, 33), '^8.0'),                 # ramsey/uuid, same lock
        ((7, 4, 33), '^8.0.2'),               # laravel 9's floor
        ((7, 4, 33), '>=8.0.0'),              # psr/log, same lock
        ((7, 4, 33), '~7.3'),                 # 7.3.x only
        ((7, 4, 33), '^6.0'),
        ((8, 0, 0), '^7.3'),
        ((8, 4, 0), '7.1 - 8.3'),      # past the inclusive right bound
        ((7, 0, 9), '7.1 - 8.3'),      # before the left bound
    ]
    for version, c in yes:
        assert _satisfies(version, c), 'matcher says %s does NOT satisfy %r' % (version, c)
    for version, c in no:
        assert not _satisfies(version, c), 'matcher says %s satisfies %r' % (version, c)

    # And it must refuse to guess rather than answering False on a shape it
    # cannot read — a silent False here would report a healthy lock as broken.
    try:
        _satisfies((7, 4, 0), 'dev-main')
    except ValueError:
        pass
    else:
        raise AssertionError('the matcher silently accepted an unparseable constraint')


def test_the_build_installs_from_the_lock_and_never_deletes_it():
    """The `rm -f composer.lock` workaround must not come back.

    This is the assertion the image build itself can never make: a Dockerfile
    that deletes the lock builds perfectly and silently returns to resolving
    every dependency afresh on every build — under Laravel 8 that meant the
    `8.x-dev` branch tip; under 13 it means whatever tag is newest that day.

    Verified by reintroducing the line and watching this fail.
    """
    assert os.path.exists(LOCK), (
        'app/composer.lock is not tracked. Without it the image re-resolves '
        'every dependency on every build, so the same git tree can ship '
        'different framework code. Generate it INSIDE the image:\n'
        '  docker run --rm -v "$PWD/app:/app" -w /app --entrypoint composer \\\n'
        '    databook-laravel:latest update --no-install')

    code = _code()
    bad = re.search(r'rm\s+(-\w+\s+)*composer\.lock', code)
    assert not bad, (
        'app/Dockerfile deletes composer.lock (%r). That was the workaround for '
        'a lock resolved under PHP 8 — 13 of 63 packages required php ^8.x — and '
        'it is no longer needed: the tracked lock is resolved under this image\'s '
        'PHP. Deleting it restores a build whose output is not determined by the '
        'git tree.' % bad.group(0))

    assert re.search(r'composer\s+install', code), (
        'app/Dockerfile no longer runs `composer install`. If it moved to '
        '`composer update`, the lock is decoration again — update resolves '
        'afresh and ignores what is pinned.')
    assert not re.search(r'(?m)^RUN\s+composer\s+update', code), (
        'app/Dockerfile runs `composer update`, which re-resolves at build time '
        'and makes the tracked lock decoration.')


def test_nothing_in_the_lock_excludes_the_images_php():
    """Neither the lock's platform nor any locked package may exclude this PHP.

    This is the exact defect that forced the workaround. Composer does check it
    ("Verifying lock file contents can be installed on current platform"), but
    only once someone builds the image; this says the same thing in the unit
    suite, where it is read in seconds and names the offending packages.
    """
    with io.open(LOCK, encoding='utf-8') as fh:
        lock = json.load(fh)

    major, minor = _base_php()
    platform = (lock.get('platform') or {}).get('php')
    assert platform, 'app/composer.lock records no platform php constraint'
    assert _admits_base(platform), (
        "app/composer.lock's platform php is %r, which admits no %d.%d release, "
        'but app/Dockerfile is `FROM php:%d.%d`. The lock was resolved on a '
        'different PHP — regenerate it inside the image.'
        % (platform, major, minor, major, minor))

    offenders = []
    packages = lock.get('packages', [])
    assert len(packages) > 40, (
        'app/composer.lock lists only %d packages — this guard is reading the '
        'wrong file, and a scan that finds nothing passes' % len(packages))
    for p in packages:
        c = (p.get('require') or {}).get('php')
        if c and not _admits_base(c):
            offenders.append('%s requires php %s' % (p['name'], c))
    assert not offenders, (
        'app/composer.lock pins %d package(s) that cannot run on php %d.%d, the '
        'app image\'s PHP:\n  %s\nThis is the state that made the lock '
        'uninstallable and forced `rm -f composer.lock`. Regenerate the lock '
        'inside the image rather than on a developer\'s PHP 8.'
        % (len(offenders), major, minor, '\n  '.join(offenders)))


def test_composer_json_admits_the_images_php():
    """A declared PHP range that excludes the image is a build that cannot work.

    Laravel 9 requires `^8.0.2` and Laravel 10 `^8.1`, so bumping the framework
    without moving the base image off 7.4 lands here first — with a message
    saying which of the two to change — rather than in a five-minute image build.
    """
    with io.open(JSON, encoding='utf-8') as fh:
        cj = json.load(fh)
    declared = cj['require']['php']
    major, minor = _base_php()
    assert _admits_base(declared), (
        'app/composer.json requires php %r, which admits no %d.%d release, but '
        'app/Dockerfile is `FROM php:%d.%d`. Move the base image or relax the '
        'constraint — they cannot disagree.'
        % (declared, major, minor, major, minor))


def test_the_lock_pins_a_released_framework_tag_never_a_branch():
    """The framework must come from a TAG, and stability must forbid branches.

    Laravel 8 could only resolve to the `8.x-dev` branch tip, because composer's
    advisory policy blocks every tagged 8.x release — so the image ran whatever
    that branch held on the day it was locked, not a release anyone published.
    Laravel 13 carries no known advisory, so `minimum-stability` is `stable` and
    the lock pins a real release. Loosening either quietly re-admits a branch.
    """
    with io.open(JSON, encoding='utf-8') as fh:
        cj = json.load(fh)
    assert cj.get('minimum-stability', 'stable') == 'stable', (
        'app/composer.json sets minimum-stability %r, which lets composer select '
        'a -dev branch instead of a released tag.' % cj.get('minimum-stability'))

    with io.open(LOCK, encoding='utf-8') as fh:
        lock = json.load(fh)
    fw = [p for p in lock.get('packages', []) if p['name'] == 'laravel/framework']
    assert fw, 'app/composer.lock has no laravel/framework — the guard reads the wrong file'
    version = fw[0]['version']
    assert re.fullmatch(r'v?\d+\.\d+\.\d+', version), (
        'app/composer.lock pins laravel/framework %r, which is not a released tag. '
        'A branch like 8.x-dev is whatever that branch held on the day the lock '
        'was written.' % version)
    dev = [p['name'] + ' ' + p['version'] for p in lock.get('packages', [])
           if 'dev' in p['version']]
    assert not dev, 'app/composer.lock pins -dev packages in production: %s' % dev
