<?php

namespace App\Custom;

/**
 * The capital section's slug rule — the THIRD language of one owner.
 *
 * ⚠⚠ THIS EXISTS BECAUSE THE RULE HAD TWO OWNERS THAT DISAGREED, AND THE
 * DISAGREEMENT MADE A REAL PAGE UNREACHABLE FROM ITS OWN INDEX. The api matches
 * on `modules/capitalslug` (`slug()` / `SLUG_SQL`), while the controller minted
 * URLs with Laravel's `Str::slug`. Those two are not the same function:
 *
 *   Str::slug DELETES every character outside [\pL\pN\s-] and only then
 *   collapses whitespace, so a separator INSIDE a word vanishes;
 *   capitalslug replaces every non-alphanumeric RUN with '-'.
 *
 * Measured across both live vocabularies (202 project types, 186 Ten-Year
 * categories) rather than sampled — the category page's earlier slug defect was
 * 12 of 138, which a sample of five would have missed:
 *
 *   Children's Services                            Str::slug childrens-services
 *                                                  ours      children-s-services
 *   Reconstruction/Renovation of Court Facilities  Str::slug reconstructionrenovation-…
 *                                                  ours      reconstruction-renovation-…
 *
 * ⭐ AND THE DIRECTION OF THE FIX WAS SETTLED BY MEASURING, not by preference.
 * `/projects/categories/reconstruction-renovation-of-court-facilities` serves
 * **200**; the `Str::slug` spelling the index linked to serves **404**. So the
 * page already lives at OUR spelling and the href was the wrong half — and
 * `reconstructionrenovation` welds two words together, which is a worse slug for
 * a reader as well as a broken one.
 *
 * ⚠ DO NOT "simplify" this to `Str::slug`. That is the defect, and it is silent:
 * every other name in both vocabularies agrees, so 3 values out of 388 are the
 * entire visible symptom.
 */
class CapitalSlug
{
    /**
     * Byte-compatible with `modules/capitalslug.slug` and with the character
     * class inside `SLUG_SQL`. A guard parses that class out of the module and
     * applies it to this function's output, so the three cannot drift apart —
     * re-typing the rule here is what a guard has to be able to falsify.
     */
    public static function make($value)
    {
        $s = mb_strtolower((string)($value ?? ''), 'UTF-8');
        return trim(preg_replace('/[^a-z0-9]+/', '-', $s), '-');
    }
}
