<?php

namespace Database\Factories;

use App\User;
use Illuminate\Database\Eloquent\Factories\Factory;
use Illuminate\Support\Str;

/**
 * Laravel 8 replaced the closure-based `$factory->define(...)` form with
 * class-based factories. Nothing in this application calls a factory — the
 * measured count of `factory(` is zero, and there is no user system — so this
 * is the framework skeleton kept in its current form, not a live definition.
 *
 * ⚠ `$model` is declared explicitly rather than inferred from the class name.
 * Laravel's convention would look for `App\Models\UserFactory`'s model at
 * `App\Models\User`, and this application's User model is still at `App\User`
 * (referenced by config/auth.php). Declaring it keeps the model where it is.
 */
class UserFactory extends Factory
{
    /**
     * The name of the factory's corresponding model.
     *
     * @var string
     */
    protected $model = User::class;

    /**
     * Define the model's default state.
     *
     * @return array
     */
    public function definition()
    {
        return [
            'name' => $this->faker->name,
            'email' => $this->faker->unique()->safeEmail,
            'email_verified_at' => now(),
            'password' => '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', // password
            'remember_token' => Str::random(10),
        ];
    }
}
