"""Guards for the local-dev seed scripts.

⚠⚠ THE PROPERTY WORTH PINNING IS THE PUBLIC-SYNC EXCLUSION, and this repo has a
recorded near-miss in exactly this category: `scripts/rotate-fastapi-key.sh` was
one sync from going public because it sat in a category the exclusion list
already claimed to cover. An exclusion list is a SNAPSHOT; new files land in old
categories. Any script that names the production host and shells into its
database belongs on that list the day it is written.

⚠ And a seed that loads nothing must not exit 0 — the oldest defect recorded in
this repo is a check whose zero is indistinguishable from never having run.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SEED = 'scripts/seed-local-derived.sh'


def _read(rel):
    with io.open(os.path.join(ROOT, rel), encoding='utf-8') as fh:
        return fh.read()


def _shell_code(src):
    """The script with `#` comment lines removed.

    ⚠ Own-prose guard, avoided in advance: this script's comments QUOTE the
    strings the scans below look for (they explain the traps), so a raw-text
    scan would pass for the wrong reason on a file that had lost the code.
    """
    out = []
    for line in src.split('\n'):
        stripped = line.lstrip()
        if stripped.startswith('#'):
            continue
        out.append(line.split(' #', 1)[0] if ' #' in line else line)
    return '\n'.join(out)


def test_every_script_that_reaches_production_is_excluded_from_the_public_sync():
    """⚠ Derived from the SCRIPTS, not from a list typed here — a hardcoded pair
    would pass while a third such script shipped unexcluded."""
    sync = _read('scripts/sync-public.sh')
    excluded = set(re.findall(r'"(scripts/[^"]+\.sh)"', sync))
    offenders = []
    for name in sorted(os.listdir(os.path.join(ROOT, 'scripts'))):
        if not name.endswith('.sh'):
            continue
        rel = f'scripts/{name}'
        body = _shell_code(_read(rel))
        # The signature: a default production SSH target it will shell into.
        if re.search(r'PROD_SSH.*root@\d+\.\d+\.\d+\.\d+', body) and 'ssh ' in body:
            if rel not in excluded:
                offenders.append(rel)
    assert not offenders, (
        f'{offenders} name the production host and shell into it, and are NOT in '
        f"sync-public.sh's EXCLUDE list — they would be published")
    # Non-vacuity: this must have actually found such scripts to check.
    assert SEED in excluded and 'scripts/make-local-seed.sh' in excluded


def test_the_derived_seed_refuses_an_empty_pull():
    """A seed that loads nothing and exits 0 is indistinguishable from one that
    never ran. Every table it takes is non-empty on prod, so an empty pull is a
    broken pull."""
    body = _shell_code(_read(SEED))
    assert 'failed=1' in body, 'the script has no failure path at all'
    assert re.search(r'pulled.*-eq 0|-eq 0.*pulled', body), \
        'the script no longer refuses a zero-row pull'
    assert 'exit 1' in body, 'a failed table no longer makes the script exit non-zero'


def test_the_derived_seed_verifies_what_arrived_against_what_was_pulled():
    """⚠ Loading without comparing is how a truncated COPY reads as success."""
    body = _shell_code(_read(SEED))
    assert '"$loaded" = "$pulled"' in body or '"$pulled" = "$loaded"' in body, \
        'the script no longer compares the loaded count against the pulled count'


def test_the_derived_seed_writes_only_to_the_local_stack():
    """⚠ It must be unable to run against anything but a dev checkout. The compose
    OVERRIDE is the structural guarantee: it exists in a checkout and never on the
    box, so requiring it is what makes 'local' true by construction."""
    body = _shell_code(_read(SEED))
    assert 'docker-compose.local.yml' in body, \
        'the local-only write path no longer goes through the compose override'
    assert re.search(r'-f .*docker-compose\.local\.yml.*\|\| \{|\[ -f .*docker-compose\.local\.yml \]', body), \
        'the script no longer refuses to run outside a dev checkout'


def test_the_seed_qualifies_its_statements_after_the_pg_dump_block():
    """⚠⚠ pg_dump emits `set_config('search_path','',false)`, so every statement
    after its schema block must be schema-qualified or it resolves to nothing.
    The second draft of this script failed all ten tables with `relation "x" does
    not exist` one line after creating it."""
    body = _shell_code(_read(SEED))
    assert 'COPY public.' in body, 'the COPY is no longer schema-qualified'
    assert 'SET search_path = public;' in body, \
        'the search_path pg_dump empties is no longer restored'


def test_the_seed_streams_data_rather_than_reading_a_host_path():
    """⚠⚠ psql runs INSIDE the container, so `\\copy FROM <host path>` cannot see
    the file. The first draft failed all ten tables on 'No such file or directory'."""
    body = _shell_code(_read(SEED))
    assert 'FROM stdin' in body, 'the load no longer streams the data on stdin'
    assert not re.search(r'\\\\copy [^\n]*FROM\s+[\'"]?\$TMP', body), \
        'the load reads a HOST path, which psql-in-the-container cannot see'

# --------------------------------------------------------------------------
# the public snapshot
# --------------------------------------------------------------------------

# ⚠ Assembled from parts so THIS FILE does not contain the literal it searches
# for. api/tests/ is published, so a test written the obvious way would match
# itself and then have to exempt itself — the own-prose guard failure this repo
# has recorded more than a dozen times, avoided in advance rather than patched.
PROD_HOST = '5.161.' + '232.100'


def _tracked_files():
    import subprocess
    out = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return [f for f in out.stdout.split('\n') if f]


def test_no_file_naming_the_prod_host_can_reach_the_public_snapshot():
    """⚠⚠ THE RULE IS DERIVED FROM THE TREE, NOT FROM A LIST TYPED HERE.

    On 2026-09-15 the secret scan blocked EVERY sync because two files named the
    prod host and were not excluded: `docs/CAPITAL-DEPLOY-RUNBOOK.md`, a deploy
    runbook written long after `deployment_guide.md` was excluded, and
    `REVIEW-databook-private-2026-08-28.md`, an internal SECURITY REVIEW — a map
    of this system's risk-bearing core and of which half went unread. Both sat in
    categories the list already claimed to cover. "An exclusion list is a
    SNAPSHOT; new files land in old categories."

    ⚠ TWO mechanisms keep a file out, and a guard that knows only one reports a
    false leak: EXCLUDE removes it, and PUBLIC_ONLY restores the public repo's
    own copy over it — which is how README.md names the prod host privately while
    the published README never has.
    """
    sync = _read('scripts/sync-public.sh')
    # ⚠⚠ Parse to the array's OWN closing line, with comment lines dropped.
    # Slicing to the first `)` stopped inside a comment ~50 lines in, so this
    # guard read 28 of the 71 entries (measured 2026-09-23) and reported every
    # file excluded below that point as a leak — or, worse, passed files it
    # never read. Bash itself ignores brackets in comments; only this parse
    # did not.
    lines = sync.split('\n')
    start = lines.index('EXCLUDE=(')
    end = lines.index(')', start)
    excluded = set(re.findall(r'"([^"]+)"', '\n'.join(
        l for l in lines[start + 1:end] if not l.lstrip().startswith('#'))))
    assert len(excluded) > 60, f'parsed only {len(excluded)} EXCLUDE entries — the parse is truncating'
    i = sync.index('PUBLIC_ONLY=(')
    public_only = set(re.findall(r'"([^"]+)"', sync[i:sync.index(')', i)]))
    assert excluded and public_only, 'could not parse the two lists out of sync-public.sh'

    def covered(path):
        if path in public_only:
            return True
        parts = path.split('/')
        return any('/'.join(parts[:n]) in excluded for n in range(1, len(parts) + 1))

    offenders = []
    checked = 0
    for f in _tracked_files():
        full = os.path.join(ROOT, f)
        if not os.path.isfile(full):
            continue
        try:
            with io.open(full, encoding='utf-8', errors='ignore') as fh:
                body = fh.read()
        except OSError:
            continue
        checked += 1
        if PROD_HOST in body and not covered(f):
            offenders.append(f)

    # ⚠ Any guard that walks the tree must assert it LOOKED — a scan of zero
    # files passes unconditionally, which is this repo's oldest defect.
    assert checked > 500, f'only scanned {checked} files — the walk is broken'
    assert not offenders, (
        f'{offenders} name the production host and are neither excluded nor '
        f'restored from public — the secret scan will block every sync')

def test_every_gitleaks_allowlist_stays_scoped_to_rule_path_and_token():
    """⚠⚠ THIS FILE LOOSENS THE GATE BETWEEN THE PRIVATE HISTORY AND A PUBLIC
    PUSH, and its own comments record both ways an entry silently stops being an
    allowlist and becomes a hole:

      * `regexTarget` defaulting to "match" tests the regex against the whole
        matched LINE, so a line containing the exempt token allowlists every
        other credential on it — measured 2026-07-31, a planted legacy Airtable
        key was swallowed.
      * `condition` defaulting to OR means the `paths` entry ALONE exempts the
        file, so every credential in it passes.

    Both are invisible in a passing scan: the entry looks scoped and is not.
    Derived from the file, so a THIRD entry is covered before it is written.
    """
    try:
        import tomllib
    except ImportError:  # py<3.11
        import tomli as tomllib
    with io.open(os.path.join(ROOT, 'scripts/gitleaks.toml'), 'rb') as fh:
        cfg = tomllib.load(fh)

    assert cfg.get('extend', {}).get('useDefault') is True, \
        'the config no longer EXTENDS the default ruleset — defining a config ' \
        'without it drops every built-in rule and the scan passes by finding nothing'

    rules = cfg.get('rules') or []
    assert len(rules) >= 2, f'only {len(rules)} rule allowlists found — the walk is broken'
    for r in rules:
        rid = r.get('id', '(unnamed)')
        al = r.get('allowlist')
        assert al, f'{rid}: a rule entry with no allowlist disables nothing and hides intent'
        assert al.get('condition') == 'AND', \
            f'{rid}: condition is {al.get("condition")!r}, not "AND" — with the default OR ' \
            f'the paths entry alone exempts every credential in those files'
        assert al.get('regexTarget') == 'secret', \
            f'{rid}: regexTarget is {al.get("regexTarget")!r}, not "secret" — against the ' \
            f'whole match, one exempt token allowlists every credential on its line'
        assert al.get('regexes'), f'{rid}: no regexes, so the allowlist is path-wide'
        assert al.get('paths'), f'{rid}: no paths, so the allowlist is tree-wide'

