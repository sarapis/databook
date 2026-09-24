FROM php:8.4-fpm

# Install system dependencies
RUN apt-get update \
 && apt-get install -y \
    git \
    curl \
    libpng-dev \
    libonig-dev \
    libxml2-dev \
    zip \
    unzip

# Clear cache
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Install PHP extensions (including OPcache for production performance)
RUN docker-php-ext-install pdo_mysql mbstring exif pcntl bcmath gd opcache

# OPcache production config — ~13x faster page loads
RUN echo "opcache.enable=1\n\
opcache.memory_consumption=128\n\
opcache.interned_strings_buffer=16\n\
opcache.max_accelerated_files=10000\n\
opcache.revalidate_freq=60\n\
opcache.fast_shutdown=1\n\
opcache.enable_cli=0\n\
opcache.save_comments=1" > /usr/local/etc/php/conf.d/opcache-recommended.ini

# PHP-FPM worker tuning for traffic (3.7GB RAM server, ~30MB per worker)
RUN sed -i 's/pm.max_children = 5/pm.max_children = 15/' /usr/local/etc/php-fpm.d/www.conf && \
    sed -i 's/pm.start_servers = 2/pm.start_servers = 5/' /usr/local/etc/php-fpm.d/www.conf && \
    sed -i 's/pm.min_spare_servers = 1/pm.min_spare_servers = 3/' /usr/local/etc/php-fpm.d/www.conf && \
    sed -i 's/pm.max_spare_servers = 3/pm.max_spare_servers = 8/' /usr/local/etc/php-fpm.d/www.conf

# Per-request timing + slow-request stack traces (app/docker/php-fpm-timing.conf).
COPY docker/php-fpm-timing.conf /usr/local/etc/php-fpm.d/zz-timing.conf

# Composer, pinned to its MAJOR. `composer:latest` would let a Composer 3 land
# on the next rebuild with no diff here — the unpinned-dependency shape that
# took the MCP server down for 16.5 hours when `mcp` shipped 2.0.
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer

# Set working directory
WORKDIR /var/www

# Copy existing application directory contents
COPY . /var/www

# Install dependencies from the committed lock.
#
# ⚠⚠ THE LOCK MUST BE RESOLVED UNDER THIS IMAGE'S PHP. For a long time it was
# not — a PHP 8 resolution in a PHP 7.4 image, so the build ran
# `rm -f composer.lock` and re-resolved every time, which made the image
# unreproducible with no diff to show it (#421 fixed that).
#
# It now pins `laravel/framework` v13.33.0 — a released TAG. Laravel 8 could only
# resolve to the `8.x-dev` branch tip, because composer's advisory policy blocks
# every tagged 8.x release; 13.x carries no known advisory, so
# `minimum-stability` is `stable` and a branch tip can never be selected.
# `composer install` verifies the platform itself and FAILS on a stale or
# mismatched lock (measured: exit 4), which is the right mechanism.
#
# ⚠ Regenerate it INSIDE this image, never on a developer's machine, whose PHP
# may be newer than this image's and resolve packages it cannot run:
#   docker run --rm -v "$PWD/app:/app" -w /app --entrypoint composer \
#     databook-laravel:latest update --no-install
# ⚠ If `update` ever refuses a version "affected by security advisories", that is
# the policy working, not a broken command. Move to the patched 13.x release;
# never reach for `policy.advisories.ignore-id`, which silences real ones too.
#
# A guard (api/tests/test_app_composer.py) fails the build if the lock's platform
# php stops admitting this image's php, or if this RUN goes back to deleting a
# tracked lock.
RUN composer install --no-interaction --optimize-autoloader --no-dev

# Pre-compile Blade templates for production.
#
# ⚠⚠ NO `config:cache` HERE. The image carries no .env (app/.dockerignore), so a
# build-time cache would bake Laravel's DEFAULTS — no APP_KEY, and
# `fapi_entry` = 127.0.0.1 — and a cached config OUTRANKS both the bind-mounted
# .env and the container's own FAPI_ENTRY. Before .env was excluded it baked
# whatever .env sat in the build tree instead, which locally meant the retired
# staging API and the "run config:clear after every rebuild" trap. Prod already
# runs uncached (every deploy's `config:clear` deletes the file; measured
# 2026-09-23: no bootstrap/cache/config.php), so this changes nothing there.
RUN php artisan view:cache || true

# Change current user to www
RUN chown -R www-data:www-data /var/www

# Expose port 9000 and start php-fpm server
EXPOSE 9000
CMD ["php-fpm"]
