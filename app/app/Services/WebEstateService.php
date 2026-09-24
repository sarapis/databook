<?php

namespace App\Services;

use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Log;

/**
 * The City Web Estate Explorer's observation feed, read for one licence family.
 *
 * ⚠⚠ THIS IS AN INDEPENDENT AUDIT'S INFERENCE, NOT OUR PROCUREMENT RECORD, and
 * the whole surface is shaped around keeping that distinction visible. The feed
 * publishes only four evidence grades - runtime, header, form-action, tag-src -
 * and deliberately omits weaker ones (cert co-tenancy, an inline mention, a CSP
 * ALLOWING a host), because a Content-Security-Policy permitting paypal.com is
 * not evidence anything loaded from it. PayPal is in their mapping file and
 * absent from the feed for exactly that reason.
 *
 * ⚠ FETCHED SERVER-SIDE, so the browser never touches a third origin, the page
 * CSP does not need widening, and an outage at their end degrades to "no panel"
 * rather than a console error on a public page.
 *
 * ⚠ FAILS SOFT AND LOGS ONCE. Every failure path returns null, which the view
 * renders as nothing. A panel that cannot load must not take a licence family
 * page down with it - the page's own content is the procurement record and is
 * the thing readers came for.
 */
class WebEstateService
{
    private const URL = 'https://nyc-web-estate.pages.dev/observed.json';
    private const CACHE_KEY = 'web_estate_observed';
    private const TTL = 3600;   // their own Cache-Control is max-age=3600

    /**
     * The whole feed, or null. Cached for an hour.
     */
    public function feed()
    {
        return Cache::remember(self::CACHE_KEY, self::TTL, function () {
            try {
                $ctx = stream_context_create(['http' => [
                    'timeout' => 6,
                    'header'  => "User-Agent: databook.nyc/1 (+https://databook.nyc)\r\n",
                ]]);
                $raw = @file_get_contents(self::URL, false, $ctx);
                if ($raw === false) {
                    Log::warning('[web-estate] feed unreachable');
                    return null;
                }
                $d = json_decode($raw, true);
                // ⚠ A parse failure is not an empty feed. Returning [] would make
                // "their JSON is broken" indistinguishable from "nothing observed",
                // which is this codebase's oldest defect wearing a new hat.
                if (!is_array($d) || !isset($d['components'])) {
                    Log::warning('[web-estate] feed did not parse to the expected shape');
                    return null;
                }
                return $d;
            } catch (\Throwable $e) {
                Log::warning('[web-estate] feed failed: ' . $e->getMessage());
                return null;
            }
        });
    }

    /**
     * The panel for one family slug, or null when there is nothing to say.
     *
     * Most families return null and that is correct - the scan covers 243 public
     * hosts, not the 814 families the City buys.
     */
    public function forSlug($slug)
    {
        $d = $this->feed();
        if (!$d || !$slug) {
            return null;
        }

        // ⚠ COMPONENTS ARE LISTED BY THEIR OWN NAMES because family grain is
        // COARSER than component grain: four Microsoft components (Azure, Entra,
        // IIS, Power BI) map to our one `microsoft` family, which carries every
        // Microsoft product the City buys. Collapsing them would let the panel
        // read as "Microsoft's $643.6M is observed on these hosts".
        $components = [];
        foreach (($d['components'] ?? []) as $name => $c) {
            if (($c['databook_slug'] ?? null) !== $slug) {
                continue;
            }
            $obs = array_values($c['observations'] ?? []);
            $components[] = [
                'name'  => $name,
                'total' => count($obs),
                // ⚠ COUNT BEFORE YOU CAP. Microsoft IIS alone carries 54
                // observations; the view states the true total beside the cap.
                'observations' => array_slice($obs, 0, 12),
            ];
        }
        if ($components) {
            usort($components, function ($a, $b) { return $b['total'] - $a['total']; });
            return [
                'kind'       => 'observed',
                'components' => $components,
                'total'      => array_sum(array_column($components, 'total')),
                'scanned'    => $d['scanned'] ?? null,
                'source'     => $d['source'] ?? null,
            ];
        }

        foreach (($d['bought_not_observed'] ?? []) as $b) {
            if (($b['databook_slug'] ?? null) === $slug) {
                return [
                    'kind'     => 'not-observed',
                    'strongest'=> $b['strongest_evidence'] ?? null,
                    'scanned'  => $d['scanned'] ?? null,
                    'source'   => $d['source'] ?? null,
                ];
            }
        }
        return null;
    }
}
