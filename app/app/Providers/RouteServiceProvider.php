<?php

namespace App\Providers;

use Illuminate\Foundation\Support\Providers\RouteServiceProvider as ServiceProvider;
use Illuminate\Support\Facades\Route;

class RouteServiceProvider extends ServiceProvider
{
    /**
     * ⚠⚠ THE CONTROLLER-NAMESPACE PREFIX IS GONE, AND IT IS NOW PROVABLY DEAD.
     * It existed to turn `'Titles@main'` into `App\Http\Controllers\Titles@main`.
     * #404 converted every string action in `routes/` to the array form, and
     * measured 2026-09-18 there are **0 string-form actions and 0 `action()`
     * helper calls** left in the tree — so the prefix has nothing to prefix.
     *
     * Laravel 8 deprecated this property and Laravel 9 REMOVES it, so leaving
     * it is a blocker for the framework move (#382) rather than a convenience.
     *
     * ⚠ The proof that this is inert is `php artisan route:list`, byte-identical
     * before and after: 140 registrations, same names, same resolved actions. A
     * count alone cannot see a route moving.
     */

    /**
     * The path to the "home" route for your application.
     *
     * @var string
     */
    public const HOME = '/home';

    /**
     * Define your route model bindings, pattern filters, etc.
     *
     * @return void
     */
    public function boot()
    {
        //

        parent::boot();
    }

    /**
     * Define the routes for the application.
     *
     * @return void
     */
    public function map()
    {
        $this->mapApiRoutes();

        $this->mapWebRoutes();

        //
    }

    /**
     * Define the "web" routes for the application.
     *
     * These routes all receive session state, CSRF protection, etc.
     *
     * @return void
     */
    protected function mapWebRoutes()
    {
        Route::middleware('web')
            ->group(base_path('routes/web.php'));
    }

    /**
     * Define the "api" routes for the application.
     *
     * These routes are typically stateless.
     *
     * @return void
     */
    protected function mapApiRoutes()
    {
        Route::prefix('api')
            ->middleware('api')
            ->group(base_path('routes/api.php'));
    }
}
