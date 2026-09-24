<?php

namespace App\Custom;

/**
 * The capital section's ONE date format, in PHP.
 *
 * ⚠⚠ THE SECTION PUBLISHED TWO DATE FORMATS AGAIN, ON THE SAME PAGE. The
 * project profile's redesign settled `23 Feb 2030` and implemented it at the
 * endpoint (`_mdy_label` in `routers/capital.py`), but the facet pages were
 * never covered. Measured 2026-09-10 on the rendered pages, inside
 * `.inner_container`:
 *
 *     /projects                          6 raw MM/DD/YYYY   sources table
 *     /projects/types                    3                  sources table
 *     /projects/categories               1                  inline note
 *     /projects/budget-lines             1                  inline note
 *     /projects/budget-lines/EP 0007    15                  10 commitments + 5 sources
 *     /p/826HED-545                      0                  (already fixed)
 *
 * ⚠ SCOPE WAS DECIDED BY MEASURING, not assumed. 23 views render a
 * `Last Updated` column, which looked site-wide and out of bounds — but
 * `ProjectsDatasets::stats_data_sources` is called **only from
 * `Projects.php`**; `DistDatasets` and `SchoolDatasets` carry their own copies.
 * So the capital section's sources table can be fixed without touching
 * districts or schools, and it had to be: leaving it raw while formatting the
 * commitments table would have put BOTH formats on one page, which is exactly
 * the defect the profile redesign removed.
 *
 * ⚠ A FOURTH LANGUAGE FOR ONE RULE IS A COST, and it is taken deliberately.
 * The alternative was formatting at `/get/datasets/all`, which districts and
 * schools also read — moving their dates as a side effect of a capital change.
 * `test_capital_date_one_format` pins this against the Python owner's output on
 * every shape measured in the data, so the two cannot drift silently.
 */
class CapitalDate
{
    /** Month spellings, byte-identical to `_MONTHS` in `routers/capital.py`. */
    const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    /**
     * `MM/DD/YYYY` (optionally followed by a clock time) as `5 Sep 2026`.
     *
     * ⚠ AN UNPARSEABLE VALUE FALLS THROUGH TO ITSELF, never to blank — the same
     * decision `_mdy_label` records. A value in an unfamiliar shape is still a
     * date the City published, and an empty cell reads as "not published",
     * which is a different claim.
     *
     * ⚠ The clock is DROPPED, and that is a content decision rather than a
     * formatting one: `Last Updated` arrives as `09/05/2026 22:10`, and the
     * inline note beside it already published the date alone
     * (`explode(' ', …)[0]`). Day granularity is what these pages already
     * asserted; this makes the table agree with the note rather than inventing
     * a new precision.
     */
    public static function label($value)
    {
        $raw = trim((string)($value ?? ''));
        if ($raw === '') {
            return '';
        }
        $head = substr($raw, 0, 10);
        if (strlen($raw) < 10 || $head[2] !== '/' || $head[5] !== '/') {
            return $raw;
        }
        $m = (int)substr($head, 0, 2);
        $d = (int)substr($head, 3, 2);
        $y = (int)substr($head, 6, 4);
        if ($m < 1 || $m > 12 || $d < 1 || $d > 31 || !checkdate($m, $d, $y)) {
            return $raw;
        }
        return $d . ' ' . self::MONTHS[$m - 1] . ' ' . $y;
    }
}
