"""The org chart's sibling order must not depend on PHP's comparison rules.

⚠⚠ MEASURED 2026-09-22, building prod's 318 chart rows through the real
`App\\Custom\\OrgChart::build()` under both images: the same 228 nodes, and 2 of
36 sibling groups in a DIFFERENT ORDER under PHP 8.4 than under 7.4 —
`Borough Boards` fell from first to last under the Bronx Borough President, and
`NYC311` jumped from last to first under OTI.

The comparator turned a branch name into its index, any name containing a digit
into the integer of all its digits, and left every other name a string, then
returned `$a <=> $b` ACROSS those types. PHP 7 cast the string to 0 for that;
PHP 8 casts the int to a string ("saner string to number comparisons"), so
`"311"` sorts before `"Cyber Command"`. A mixed-type `<=>` is not a total order
under either version, which is why nothing about it looked wrong until the
version moved.

`OrgChart::siblingKey()` returns `[group, number, name]`, compared int-to-int and
then with `strcmp`, and reproduces the chart's existing order on every sibling
group under BOTH PHP versions (verified on prod's rows, both chart views). This
guard pins that the comparator goes through it. It reads the source because the
unit suite runs no PHP; the behavioural proof is recorded above and in the
method's own docblock.
"""

import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'app', 'app', 'Custom', 'OrgChart.php')


def _code():
    """OrgChart.php with comments removed — the docblock quotes the old shape."""
    with io.open(SRC, encoding='utf-8') as fh:
        src = fh.read()
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'(?m)//.*$', '', src)


def _comparator(code):
    m = re.search(r'uksort\(\s*\$kids\s*,\s*function\s*\(\$a,\s*\$b\)\s*\{(.*?)\}\s*\);',
                  code, re.S)
    assert m, 'no uksort($kids, function ($a, $b) {...}) in OrgChart.php — the guard is stale'
    return m.group(1)


def test_the_sibling_comparator_goes_through_a_typed_key():
    body = _comparator(_code())
    assert 'siblingKey(' in body, (
        'the org chart sibling sort no longer uses OrgChart::siblingKey(). The '
        'key exists because the previous comparator compared ints with strings, '
        'which PHP 7 and PHP 8 resolve differently.')
    assert 'strcmp(' in body, (
        'names must be compared with strcmp, never <=>, so two numeric-looking '
        'names cannot be compared as numbers')
    # The defect's own shape: comparing the raw (possibly mixed-type) values.
    assert not re.search(r'return\s+\$a\s*<=>\s*\$b', body), (
        'the comparator returns `$a <=> $b` on raw keys again — under PHP 8 an '
        'int and a string compare as strings, and the chart reorders')


def _top_level_split(expr):
    """Split on commas at bracket depth 0 — `preg_replace('~\\D~', '', $name)`
    carries commas of its own, and a naive split reads it as three elements."""
    parts, depth, cur = [], 0, ''
    for ch in expr:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(cur.strip()); cur = ''
        else:
            cur += ch
    parts.append(cur.strip())
    return parts


def test_the_key_keeps_every_position_single_typed():
    code = _code()
    m = re.search(r'function\s+siblingKey\s*\(\s*string\s+\$name\s*\)\s*:\s*array\s*\{(.*?)\n\t\}',
                  code, re.S)
    assert m, 'OrgChart::siblingKey(string $name): array is missing'
    # ⚠ Non-greedy to the first `];` — a key may itself index an array
    # (`$branch[$name]`), so a `[^\]]*` body stops inside it.
    returns = re.findall(r'return\s*\[(.*?)\]\s*;', m.group(1), re.S)
    assert len(returns) == 3, 'expected three key shapes, found %d' % len(returns)
    for r in returns:
        parts = _top_level_split(r)
        assert len(parts) == 3 and parts[2] == '$name', (
            'every key must be [group, number, $name] so position 3 is always the '
            'string name: %r' % r)
        assert re.fullmatch(r'\d', parts[0]), 'the group must be an int literal: %r' % r
