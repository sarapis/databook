"""The app image must not carry a .env, and must not cache config at build.

⚠⚠ `COPY . /var/www` copied the box's app/.env — APP_KEY and FAPI_KEY — into an
image layer. Measured on prod 2026-09-23: the image's /var/www/.env was
byte-identical to the host file. Every compose file bind-mounts ./app/.env at
runtime, so the copy bought nothing and leaked the credentials to anyone who can
read the image.

The two halves are coupled, which is why one file guards both: once the image
has no .env, a build-time `artisan config:cache` bakes Laravel's DEFAULTS (no
APP_KEY, `fapi_entry` 127.0.0.1), and a cached config outranks the runtime .env
AND the container's environment. Excluding .env without dropping the cache would
ship an app that cannot reach its API.
"""

import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
APP = os.path.join(ROOT, 'app')


def _lines(path):
    with io.open(path, encoding='utf-8') as fh:
        return [l.strip() for l in fh if l.strip() and not l.lstrip().startswith('#')]


def test_the_build_context_excludes_every_env_file():
    rules = _lines(os.path.join(APP, '.dockerignore'))
    assert '.env' in rules, 'app/.dockerignore must exclude .env'
    assert '.env.*' in rules, 'app/.dockerignore must exclude .env.* (.env.default once held a live APP_KEY)'
    # A negation would re-include what the rules above exclude.
    assert not [r for r in rules if r.startswith('!') and '.env' in r], rules


def test_the_image_does_not_cache_config_at_build():
    code = '\n'.join(_lines(os.path.join(APP, 'Dockerfile')))
    assert 'COPY . /var/www' in code, 'guard is reading the wrong Dockerfile'
    assert 'view:cache' in code, 'guard is reading the wrong Dockerfile'
    assert not re.search(r'artisan\s+config:cache', code), (
        'the image has no .env, so a build-time config:cache bakes DEFAULTS that '
        'outrank the runtime .env and FAPI_ENTRY')


def test_every_compose_file_that_runs_the_app_mounts_its_env():
    """The runtime mount is what makes excluding .env from the image safe."""
    with io.open(os.path.join(ROOT, 'docker-compose.yml'), encoding='utf-8') as fh:
        compose = fh.read()
    block = compose.split('\n  app:', 1)[1].split('\n  api:', 1)[0]
    assert './app/.env:/var/www/.env' in block, 'the app service no longer mounts app/.env'


def test_no_committed_env_template_carries_a_real_app_key():
    """app/.env.default held prod's live APP_KEY from 2026-02-11 (8fe908e8) until
    2026-09-23, and README told every setup to copy it. A template must ship an
    EMPTY key; `php artisan key:generate` makes a real one per install."""
    for name in ('.env.default', '.env.example'):
        with io.open(os.path.join(APP, name), encoding='utf-8') as fh:
            keys = [l.split('=', 1)[1].split('#')[0].strip()
                    for l in fh if l.startswith('APP_KEY=')]
        assert keys, f'{name} has no APP_KEY line; the guard is reading the wrong file'
        assert all(k in ('', '""') or not k.startswith('base64:') for k in keys), (
            f'{name} carries a real APP_KEY; ship it empty and let key:generate make one')
