<?php

namespace App\Custom;

/**
 * How a district is NAMED for a reader — the one owner of a rule that had
 * THREE spellings.
 *
 * ⚠⚠ THE PREFIX MAP EXISTED IN THREE PLACES AND THEY DISAGREED, measured
 * 2026-09-10:
 *
 *   Schema::districtFromFile()      cc, cd, nta, sd          all four
 *   Organizations::sitemap()        cc, cd, nta              **no sd**
 *   districts.blade.php (JS)        cc, cd, nta, sd          all four
 *
 * Nothing was visibly broken by the disagreement — the sitemap iterates
 * `['cc','cd','nta']`, so its missing `sd` key is never read today. That is
 * exactly the shape this repo keeps paying for: a rule copied three times,
 * correct by luck in the one place the copies differ. All three now read this
 * class, and a guard fails the build if a fourth copy appears.
 *
 * ⭐ THE NAMES ARE NOT INVENTED — they are what the district's own page already
 * titles itself, verified by fetching all four:
 *
 *   /d/cc-22_district    City Council District 22
 *   /d/cd-107_district   Community District 107
 *   /d/sd-4_district     School District 4
 *   /d/nta-…_district    the NTA name itself
 *
 * Keeping them byte-identical is the point: a reader clicks a label and lands
 * on a page with that exact title. A prettier name here would be a second
 * spelling of the destination's identity.
 */
class DistrictName
{
    /**
     * The four boundary sets a capital project can be placed in, in the order
     * the site's own boundary menu lists them.
     *
     * ⚠ Declared, not derived from the rows a project has: a type with NOTHING
     * for this project still has to render. An omitted row and an empty one are
     * indistinguishable to a reader, and here the absence is often the finding.
     */
    const TYPES = ['cd', 'cc', 'sd', 'nta'];

    /** What precedes the id in a district's own published name. */
    const PREFIX = [
        'cc'  => 'City Council District ',
        'cd'  => 'Community District ',
        'sd'  => 'School District ',
        'nta' => '',
    ];

    /** The boundary SET, for a row label. Matches the site's boundary menu. */
    const PLURAL = [
        'cd'  => 'Community Districts',
        'cc'  => 'City Council Districts',
        'sd'  => 'School Districts',
        'nta' => 'Neighborhoods (NTA)',
    ];

    /** The unit, for a count: "4 community districts". */
    const UNIT = [
        'cd'  => ['community district', 'community districts'],
        'cc'  => ['council district', 'council districts'],
        'sd'  => ['school district', 'school districts'],
        'nta' => ['neighborhood', 'neighborhoods'],
    ];

    /**
     * ⚠⚠ THE BOROUGH IS A LOOKUP, NEVER A PARSE OF THE FIRST DIGIT.
     *
     * `DistDatasets::$cdAltName` is a curated map already in this repo, from
     * the three-digit community-district code to DCP's own borough-prefixed
     * short form (`107` -> `MN07`). It covers the **59 real community
     * districts** and nothing else — and that exclusion is the whole value of
     * using it. Measured over `capital_project_districts`, 27 of the 86 `cd`
     * codes present are NOT community districts:
     *
     *   100 200 300 400 500   4,370 rows — a borough with no district, written
     *                         in crosswalk form by the retired series
     *   164 226 227 228 355   DCP Joint Interest Areas (Central Park, Van
     *   356 480 481 482 483   Cortlandt Park, Prospect Park, …) — real places
     *   484 595               with names this repo does not hold
     *   213-218 199 299 …     codes the retired series publishes for which no
     *                         such community district exists
     *
     * A positional parse would confidently render `213` as "Bronx Community
     * District 13". The Bronx has twelve. So a code the curated map does not
     * carry gets NO borough — the name still renders, unqualified, which is
     * what the destination page shows too.
     */
    const BOROUGH = [
        'MN' => 'Manhattan',
        'BX' => 'the Bronx',
        'BK' => 'Brooklyn',
        'QN' => 'Queens',
        'SI' => 'Staten Island',
    ];

    /** The district's published name, byte-identical to its own page title. */
    public static function name($type, $id)
    {
        $type = strtolower((string) $type);
        return (self::PREFIX[$type] ?? '') . (string) $id;
    }

    /**
     * The borough, where a published source in this repo gives one.
     *
     * ⚠ `cc` and `sd` deliberately get none, and that is a finding rather than
     * an omission: this repo already measures council district 8 as Manhattan
     * 67% / Bronx 32% (East Harlem + Mott Haven), so a single borough on a
     * council district would be false. School districts likewise.
     */
    public static function borough($type, $id)
    {
        if (strtolower((string) $type) !== 'cd')
            return null;
        $alt = (new DistDatasets())->cdAltName[(string) $id] ?? null;
        return $alt ? (self::BOROUGH[substr($alt, 0, 2)] ?? null) : null;
    }

    /** The name plus its borough, where we have one. */
    public static function label($type, $id)
    {
        $name = self::name($type, $id);
        $boro = self::borough($type, $id);
        return $boro ? "{$name} ({$boro})" : $name;
    }

    /** "4 community districts" / "1 neighborhood". */
    public static function unit($type, $n)
    {
        $u = self::UNIT[strtolower((string) $type)] ?? ['district', 'districts'];
        return $n . ' ' . ($n == 1 ? $u[0] : $u[1]);
    }
}
