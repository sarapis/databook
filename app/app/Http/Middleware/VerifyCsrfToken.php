<?php

namespace App\Http\Middleware;

use Illuminate\Foundation\Http\Middleware\PreventRequestForgery as Middleware;

/*
 * Laravel 13 renamed the framework class to PreventRequestForgery and kept
 * VerifyCsrfToken as a DEPRECATED alias. Measured through the real web stack,
 * the two behave identically here on all seven cases probed, including the
 * new origin check: a tokenless POST carrying `Sec-Fetch-Site: same-origin`
 * is ACCEPTED (Laravel 8 answered 419), and a tokenless cross-site POST is
 * still refused. Browsers set that header and scripts cannot, so it is not a
 * way round CSRF. The class name here stays VerifyCsrfToken because
 * app/Http/Kernel.php and any exclusion refer to it.
 */

class VerifyCsrfToken extends Middleware
{
    /**
     * The URIs that should be excluded from CSRF verification.
     *
     * @var array
     */
    protected $except = [
        //
    ];
}
