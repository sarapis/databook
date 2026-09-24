<?php
/**
 * Compile every Blade view and lint the OUTPUT.
 *
 *   docker compose exec -T app php /var/www/../scripts/blade-lint.php
 *   (in CI: see .github/workflows/ci.yml, "Blade views compile")
 *
 * ⚠⚠ `php -l` ON A BLADE FILE PROVES NOTHING — the file is valid PHP either way,
 * so a view that 500s on every request passes it. Only COMPILING it finds the
 * two traps this repo has paid for:
 *
 *   1 a directive glued to a word character (`expire before 2030@else`) — only
 *     the `@endif` compiles, and the page dies on an unclosed `if`;
 *   2 ⚠⚠ an `@php` INSIDE A BLADE COMMENT, which pairs with the next REAL
 *     `@endphp` anywhere below it. Measured 2026-09-16 with the vendored
 *     compiler: `compileRawPhp` runs BEFORE comments are stripped, so
 *     `{{-- … @php … --}}` + a later `@php $x = 1; @endphp` compiles to
 *     `{{-- … <?php … --}} @php $x = 1; ?>` and the comment's PROSE becomes
 *     code. **Alone it is harmless** — which is why 36 Blade comments in this
 *     tree mention a directive and only one combination broke — and it is fatal
 *     the moment a real `@php` block follows. `@if` in a comment is safe.
 *
 * ⚠ Laravel must be BOOTSTRAPPED, not just the compiler constructed: a view using
 * an `<x-db.*>` component tag resolves the view Factory out of the container, and
 * a bare BladeCompiler dies on "Target [...View\Factory] is not instantiable".
 */
$root = '/var/www';
require $root . '/vendor/autoload.php';
$app = require_once $root . '/bootstrap/app.php';
$app->make(Illuminate\Contracts\Console\Kernel::class)->bootstrap();
$blade = $app->make('blade.compiler');

$paths = array_slice($argv, 1);
if (!$paths) {
    $it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root . '/resources/views'));
    foreach ($it as $f) {
        if (substr($f->getFilename(), -10) === '.blade.php') $paths[] = $f->getPathname();
    }
    sort($paths);
}

$bad = 0;
foreach ($paths as $path) {
    try {
        $out = $blade->compileString(file_get_contents($path));
    } catch (Throwable $e) {
        $bad++; echo "COMPILE $path :: " . $e->getMessage() . "\n"; continue;
    }
    $tmp = tempnam(sys_get_temp_dir(), 'bl') . '.php';
    file_put_contents($tmp, $out);
    $o = []; $rc = 0; exec('php -l ' . escapeshellarg($tmp) . ' 2>&1', $o, $rc);
    unlink($tmp);
    if ($rc !== 0) {
        $bad++;
        echo "LINT    " . str_replace($root . '/', '', $path) . " :: "
             . trim(preg_replace('/\s+/', ' ', implode(' ', $o))) . "\n";
    }
}
// ⚠ A lint that checked nothing passes — assert it looked.
if (count($paths) < 100) { echo "REFUSED: only " . count($paths) . " views scanned\n"; exit(2); }
echo "checked " . count($paths) . " views, " . $bad . " broken\n";
exit($bad ? 1 : 0);
