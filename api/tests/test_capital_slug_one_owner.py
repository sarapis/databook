"""The capital slug rule has ONE owner across THREE languages.

⚠⚠ IT HAD TWO OWNERS THAT DISAGREED, AND A REAL PAGE WAS UNREACHABLE FROM ITS
OWN INDEX. The api matches with `modules/capitalslug` (`slug()` / `SLUG_SQL`);
the frontend minted its hrefs with Laravel's `Str::slug`. Those are different
functions — `Str::slug` DELETES characters outside `[\\pL\\pN\\s-]` and only then
collapses whitespace, so a separator inside a word disappears, while
`capitalslug` replaces each non-alphanumeric RUN with `-`.

Measured across both live vocabularies (202 project types, 186 Ten-Year
categories), not sampled:

    Children's Services                            Str::slug childrens-services
                                                   ours      children-s-services
    Reconstruction/Renovation of Court Facilities   Str::slug reconstructionrenovation-…
                                                   ours      reconstruction-renovation-…

⭐ AND THE RENDERED PAGES SETTLED WHICH HALF WAS WRONG:
`/projects/categories/reconstruction-renovation-of-court-facilities` -> **200**,
the `Str::slug` spelling the index actually linked to -> **404**. So that
category row was a dead link, and the fix is the frontend adopting our rule
rather than the module adopting Laravel's.

⚠ THE DISTINCTION THAT KEEPS THIS GUARD NARROW, and it is the whole reason it
does not ban `Str::slug` outright: a capital TAXONOMY slug IS the lookup key, so
it must come from the one owner. An org, project, school or district slug is
DECORATION beside an id that carries identity (`/o/{id}-{slug}`,
`/p/{prjId}_{prjslug}`) — those may use anything, and 20-odd call sites do.
Banning the function everywhere would be a large, pointless change and would
fail on code that is correct.
"""
import importlib.util
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
API = os.path.realpath(os.path.join(HERE, '..'))
ROOT = os.path.realpath(os.path.join(API, '..'))
MODULE = os.path.join(API, 'modules', 'capitalslug.py')
PHP = os.path.join(ROOT, 'app', 'app', 'Custom', 'CapitalSlug.php')

# Every place a capital TAXONOMY slug is minted. A slug here is the KEY.
KEY_MINTS = (
    os.path.join(ROOT, 'app', 'app', 'Http', 'Controllers', 'Projects.php'),
    os.path.join(ROOT, 'app', 'app', 'Custom', 'Breadcrumbs.php'),
)
# The route parameters whose value IS the lookup key, not decoration.
KEY_PARAMS = ('tslug', 'cslug', 'category-slug', 'fslug')


def _read(p):
    with open(p, encoding='utf-8') as fh:
        return fh.read()


def _php_code(src):
    """PHP/Blade with comments removed — the new class's docstring quotes both
    `Str::slug` and the exact spellings this guard searches for, which is
    own-prose firing territory in a brand-new organ."""
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    src = re.sub(r'^[ \t]*(?://|#).*$', '', src, flags=re.M)
    return src


def _module():
    spec = importlib.util.spec_from_file_location('_capitalslug_under_test', MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert isinstance(mod.slug('x'), str), 'capitalslug did not load as the real module'
    return mod


def test_the_php_rule_is_derived_from_the_sql_rule_not_retyped():
    """⚠⚠ A GUARD THAT REIMPLEMENTS THE THING IT GUARDS MEASURES A DIFFERENT
    SYSTEM — this repo has paid for that twice. So the character class is PARSED
    OUT of `SLUG_SQL` and compared with the one the PHP file uses, rather than
    both being typed here."""
    mod = _module()
    # ⚠ The quantifier lives INSIDE the quoted pattern (`'[^a-z0-9]+'`), so a
    # capture that stops at the `]` matches nothing and this guard reported
    # "could not parse" against a perfectly good rule.
    m = re.search(r"regexp_replace\([^,]+,\s*'([^']+)'", mod.SLUG_SQL)
    assert m, 'could not parse the character class out of SLUG_SQL: %r' % mod.SLUG_SQL
    sql_class = m.group(1)

    php = _php_code(_read(PHP))
    pm = re.search(r"preg_replace\(\s*'/([^/]+)/'", php)
    assert pm, 'CapitalSlug.php no longer builds its slug with a character class'
    php_class = pm.group(1)
    assert php_class == sql_class, (
        'the PHP slug rule uses %s while SLUG_SQL uses %s — the two halves have '
        'drifted, which is how a real page became unreachable from its index'
        % (php_class, sql_class))
    assert 'trim(' in php and 'mb_strtolower(' in php, (
        'the PHP rule must lower-case and trim the separator like SLUG_SQL does')


def test_the_php_rule_agrees_with_the_python_rule_on_the_shapes_that_broke():
    """The three real values that disagreed, plus the shapes around them.

    ⚠ Not a live-vocabulary test — that needs a database. These are the exact
    strings measured off the running endpoints, kept as the regression they are.
    """
    mod = _module()
    php = _php_code(_read(PHP))
    pm = re.search(r"preg_replace\(\s*'/(\[[^/]+\]\+?)/'\s*,\s*'([^']*)'", php)
    assert pm, 'could not read the PHP substitution'
    cls, repl = pm.group(1), pm.group(2)
    if not cls.endswith('+'):
        cls += '+'

    def php_slug(v):
        return re.sub(cls, repl, (v or '').lower()).strip(repl or '-')

    for value, expected in (
            ("Children's Services", 'children-s-services'),
            ('Reconstruction/Renovation of Court Facilities',
             'reconstruction-renovation-of-court-facilities'),
            ('Water Mains, Sources and Treatment',
             'water-mains-sources-and-treatment'),
            ('Department of Parks & Recreation', 'department-of-parks-recreation'),
            ('  Parks and Recreation  ', 'parks-and-recreation'),
    ):
        assert mod.slug(value) == expected, (
            'the python rule moved: %r -> %r' % (value, mod.slug(value)))
        assert php_slug(value) == expected, (
            'the PHP rule disagrees on %r: %r vs %r'
            % (value, php_slug(value), expected))


def test_no_capital_taxonomy_slug_is_minted_with_laravels_str_slug():
    """⚠ Scoped to the KEY parameters, deliberately. `Str::slug` stays correct
    for the ~20 decorative org/project/school/district slugs, where an id beside
    the slug carries identity — banning it everywhere would fail on code that is
    right and would bury this finding in a rename."""
    scanned, bad = 0, []
    for path in KEY_MINTS:
        src = _php_code(_read(path))
        scanned += 1
        for m in re.finditer(r'Str::slug\s*\(', src):
            # the surrounding statement, so the parameter name is visible
            start = src.rfind('\n', 0, m.start())
            end = src.find('\n', m.end())
            stmt = src[start:end if end > 0 else len(src)]
            if any(p in stmt for p in KEY_PARAMS):
                bad.append('%s: %s' % (os.path.basename(path), stmt.strip()[:100]))
    assert scanned == len(KEY_MINTS), 'the scan did not read every mint site'
    assert not bad, (
        'a capital taxonomy slug is minted with Str::slug, which spells 3 of '
        'the 388 live names differently from the rule the api matches on: %s'
        % bad)


def test_every_key_mint_site_uses_the_one_owner():
    """⚠ The mirror direction, which is the one that catches the code nobody has
    written yet: a NEW taxonomy link that mints its slug some third way would
    pass the ban above by simply not calling `Str::slug`."""
    for path in KEY_MINTS:
        src = _php_code(_read(path))
        for m in re.finditer(r"'(%s)'\s*(?:=>|\])" % '|'.join(
                re.escape(p) for p in KEY_PARAMS), src):
            start = src.rfind('\n', 0, m.start())
            end = src.find('\n', m.end())
            stmt = src[start:end if end > 0 else len(src)]
            if '$' not in stmt:            # a literal slug needs no rule
                continue
            # ⚠ FORWARDING a slug is not MINTING one. `'cslug' => $cslug` hands
            # on the value the request already carried — correct, and the first
            # draft of this guard failed on it. Only a value DERIVED from a NAME
            # needs the rule.
            if re.search(r"=>\s*\$[A-Za-z_]*slug\b", stmt):
                continue
            assert 'CapitalSlug::make(' in stmt, (
                'a capital taxonomy slug is built without the one owner in %s: %s'
                % (os.path.basename(path), stmt.strip()[:100]))
