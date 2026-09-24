"""No Blade directive may be glued to a preceding word character — in ANY view.

⚠⚠ THIS GUARD ALREADY EXISTED FOR ONE DIRECTORY, AND THE DEFECT SHIPPED IN
ANOTHER. `test_review_ui.py::test_no_blade_directive_is_glued_to_a_word_character`
scans `views/review/` only, while `procurement/transactions_search.blade.php`
wrote `...Emerging@endif` and `...</span>@endif@if(...)`. Measured on prod
2026-09-22: `/procurement/transactions/search` printed that raw Blade, PHP source
included — `@if(($tx['emerging_business'] ?? '') === 'Yes') · Emerging@endif` —
into the detail panel of all 50 rows on the page, on Laravel 7. A guard that
reads one directory measures one directory; this one reads the tree.

WHY THE RULE IS "ANY DIRECTIVE, PRECEDED BY A WORD CHARACTER"
============================================================
Blade's statement regex opens with `\\B@` (vendored `BladeCompiler::
compileStatements`), so `@name` compiles only when the character before the `@`
is a NON-word character. `}}@if(` and `</span>@endif` compile; `derived@if(` and
`Emerging@endif` do not, and nothing reports it: `php -l` passes because the
output is valid PHP either way, and the page either 500s on an unclosed `if` or,
worse, renders the source. Measured under both Laravel 8.83.29 and 13.33.0: the
compiler behaves identically, so this is not a version question.

WHAT IS STRIPPED BEFORE SCANNING, AND WHY
=========================================
- `{{-- --}}` comments — prose explaining this trap quotes it.
- `@php ... @endphp` blocks — Blade stores them before compiling directives, so a
  glued form inside one is a PHP comment, not a directive. Six such comments
  exist today, each explaining the trap; a scanner that read them would be red
  on correct code and get switched off.
"""

import glob
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
VIEWS = os.path.join(ROOT, 'app', 'resources', 'views')

# Directive names, followed by something that cannot continue a name or a
# domain, so `info@endless.org` or `x@php.net` in copy cannot match.
_DIRECTIVES = (
    'if|elseif|else|endif|unless|endunless|isset|endisset|empty|endempty|'
    'foreach|endforeach|forelse|endforelse|for|endfor|while|endwhile|switch|'
    'case|break|default|endswitch|php|endphp|include\\w*|each|yield|section|'
    'endsection|show|stop|push|endpush|prepend|endprepend|stack|extends|csrf|'
    'method|json|class|js|auth|endauth|guest|endguest|can|endcan|cannot|'
    'endcannot|env|endenv|production|endproduction|once|endonce|verbatim|'
    'endverbatim|component|endcomponent|slot|endslot|props|aware|continue|'
    'error|enderror|selected|checked|disabled|readonly|required|style|lang|'
    'choice'
)
GLUED = re.compile(r'\w@(?:' + _DIRECTIVES + r')(?![\w.-])')

_BLADE_COMMENT = re.compile(r'\{\{--.*?--\}\}', re.S)
# The BLOCK form only. `@php($x = 1)` is the inline form and has no @endphp.
_PHP_BLOCK = re.compile(r'@php\b(?!\s*\().*?@endphp', re.S)


def _blank(m):
    # Keep the newlines, so a reported line number is the SOURCE line.
    return '\n' * m.group(0).count('\n')


def _compiled_surface(src):
    """The part of a view Blade actually compiles directives in."""
    return _PHP_BLOCK.sub(_blank, _BLADE_COMMENT.sub(_blank, src))


def _scan(src):
    return [m.group(0) for m in GLUED.finditer(_compiled_surface(src))]


def test_the_scanner_is_not_vacuous():
    """Pin the scanner both ways — a pattern matching nothing passes everywhere."""
    for bad in ("x Emerging@endif", "</span>@endif@if($a)", "chart@if ($x)",
                "2030@else y", "value@foreach($r as $x)"):
        assert _scan(bad), 'scanner missed a real glued directive: %r' % bad
    for ok in ("{{ $a }}@if($b) x @endif", "</span>@endif", "@else{{ $x }}",
               "mail info@endless.org", "see x@php.net",
               "{{-- derived@if(...) --}}",
               "@php // `Emerging@endif` never compiled\n$x = 1; @endphp",
               "@elseif($a)"):
        assert not _scan(ok), 'scanner flagged correct Blade: %r' % ok


def test_no_view_glues_a_directive_to_a_word_character():
    files = sorted(glob.glob(os.path.join(VIEWS, '**', '*.blade.php'),
                             recursive=True))
    # ⚠ Assert it LOOKED. A guard that walks the tree and finds nothing passes.
    assert len(files) > 100, 'scanned only %d views — the root is wrong' % len(files)
    bad = []
    for f in files:
        with io.open(f, encoding='utf-8', errors='replace') as fh:
            src = fh.read()
        surface = _compiled_surface(src)
        for m in GLUED.finditer(surface):
            line = surface.count('\n', 0, m.start()) + 1
            bad.append('%s:%d: %r'
                       % (os.path.relpath(f, VIEWS), line, m.group(0)))
    assert not bad, (
        'A Blade directive is glued to a word character, so it will NOT compile '
        'and renders as raw text (or leaves an unclosed if):\n  %s\n'
        'Compose the conditional phrase in @php, or put a non-word character '
        'before the @.' % '\n  '.join(bad))
