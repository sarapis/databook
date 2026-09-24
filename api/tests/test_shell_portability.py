"""Shell scripts the TEST SUITE runs must work on bash 3.2.

⚠⚠ CI STRUCTURALLY CANNOT CATCH THIS CLASS, WHICH IS THE WHOLE REASON THIS
GUARD IS A STATIC SCAN AND NOT A RUN. CI is Ubuntu with bash 5, where every
construct below works fine. macOS ships **bash 3.2.57** — frozen at that version
since 2007 for licensing reasons — and it is what a developer's `bash` resolves
to. So a bash-4-only builtin merges green and breaks only on the machines the
work is actually done on.

That happened: `scripts/frontend-smoke.sh` used `mapfile` (a bash 4 builtin) and
died locally with

    mapfile: command not found
    URLS: unbound variable

leaving **two permanently-red tests on every local run** while CI stayed green.
A red signal nobody can act on is one people learn to scroll past — this repo
has paid for that with the permanently-red monitor, and this is the same defect
in the test suite.

⚠ Scope is DERIVED from which scripts the suite actually executes, not listed.
A script that only ever runs on the prod box (Ubuntu, bash 5) is legitimately
free to use bash 4 features, so a repo-wide ban would be wrong and would get
switched off.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
TESTS = os.path.dirname(os.path.realpath(__file__))

# Each is bash 4.0+. Named individually so a failure says WHICH and not merely
# "unportable".
BASH4 = {
    'mapfile': r'\bmapfile\b',
    'readarray': r'\breadarray\b',
    'associative array (declare -A)': r'\b(?:declare|local|typeset)\s+-[A-Za-z]*A\b',
    'case modification ${v^^} / ${v,,}': r'\$\{[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?(?:\^\^?|,,?)\}',
    'coproc': r'\bcoproc\b',
    '&>> append redirect': r'&>>',
}


def _shell_code_only(text):
    """Strip comments before scanning.

    ⚠ The comment in `frontend-smoke.sh` EXPLAINING why `mapfile` was removed
    names `mapfile` and `readarray` outright, so a raw scan fires on the very
    prose documenting the fix. That is own-prose firing 20 in this repo.
    ⚠ Line-level, and it deliberately keeps `#!` — a shebang is code.
    """
    out = []
    for line in text.splitlines():
        if line.startswith('#!'):
            out.append(line)
            continue
        out.append(re.sub(r'(?<!\$)#.*$', '', line))
    return '\n'.join(out)


def _scripts_the_suite_runs():
    """Every shell script a test invokes, read out of the tests themselves."""
    found = set()
    for name in os.listdir(TESTS):
        if not name.endswith('.py'):
            continue
        src = open(os.path.join(TESTS, name), encoding='utf-8').read()
        # ⚠⚠ STRIP PYTHON COMMENTS FIRST, AND THIS GUARD LEARNED IT THE HARD
        # WAY ON ITSELF. The first draft carried a comment showing the shape it
        # matches; the extractor read its OWN prose, "found" a script by that
        # example name, and failed on a correct tree. Own-prose firing 20 — in
        # the guard written to document own-prose firing 20.
        src = re.sub(r'(?<!["\'])#.*$', '', src, flags=re.M)
        if not re.search(r"subprocess\.run\(\s*\[\s*['\"]bash['\"]", src):
            continue
        for m in re.finditer(r"os\.path\.join\(\s*ROOT\s*,\s*'scripts'\s*,\s*'([^']+\.sh)'", src):
            found.add(m.group(1))
    return sorted(found)


def test_the_suite_runs_at_least_one_shell_script():
    """⚠ ANTI-VACUUM. A derived scope that resolves to nothing passes
    unconditionally — the failure this repo has paid for with the guard that
    scanned zero files and the audit that executed zero tools."""
    scripts = _scripts_the_suite_runs()
    assert scripts, (
        'no shell script was found to scan — either the suite stopped running '
        'one, or the extraction above no longer matches how tests invoke them')


def test_scripts_the_suite_runs_avoid_bash_4_only_constructs():
    scripts = _scripts_the_suite_runs()
    offenders = []
    for rel in scripts:
        path = os.path.join(ROOT, 'scripts', rel)
        assert os.path.exists(path), f'{rel} is invoked by a test but does not exist'
        code = _shell_code_only(open(path, encoding='utf-8').read())
        for line_no, line in enumerate(code.splitlines(), 1):
            for label, pattern in BASH4.items():
                if re.search(pattern, line):
                    offenders.append(f'{rel}:{line_no}: {label} — {line.strip()[:60]}')
    assert not offenders, (
        'these constructs need bash 4+, but the suite runs these scripts on '
        'developer machines where bash is 3.2 (macOS). CI runs bash 5 and will '
        'NOT catch this:\n  ' + '\n  '.join(offenders))
