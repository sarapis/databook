<?php

namespace App\Custom;

/**
 * The drill-down rows under a Digital Services pie — ONE owner.
 *
 * Every pie in the section renders its legend as a list of links built from a
 * `_slices` block. Written once per view it was four chances for one copy to
 * link an abstention, or to emit a link for a slice whose slug is empty and land
 * on a 404; with the Products book shared by two pages it would be two copies of
 * the rule, so the rule lives here and the views call it.
 */
class SliceLinks
{
    /**
     * @param array  $block  a `_slices` block ({items: [{label, color, grey, slug}]})
     * @param string $route  the route each linkable slice opens
     * @param string $param  the route parameter the slice's slug fills
     * @param string $fragment  an anchor to land on, without the '#' ('' for none)
     * @return array [{label, color, href|null}]
     */
    public static function links($block, string $route, string $param, string $fragment = ''): array
    {
        $out = [];
        foreach ((is_array($block) ? ($block['items'] ?? []) : []) as $it) {
            // ⚠ `grey` marks an abstention and an empty slug means the row has no
            // page — neither may become a link.
            $out[] = ['label' => $it['label'],
                      // The colour rides along because these entries ARE the
                      // legend — the canvas legend is off.
                      'color' => $it['color'] ?? 'UNKNOWN',
                      'href'  => (!($it['grey'] ?? false) && ($it['slug'] ?? '') !== '')
                          ? route($route, [$param => $it['slug']]) . ($fragment !== '' ? '#' . $fragment : '')
                          : null];
        }
        return $out;
    }
}
