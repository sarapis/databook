<?php

namespace App\Custom;

/**
 * Display names for the licence purchase classes — ONE owner.
 *
 * ⚠ The KEYS are data values from license_family_class.class and keep the
 * British spelling they were stored with (`software-licence`). Only the labels
 * are American. The Products page, the family page and the Products book's
 * "Value by kind" pie all read this map; two view-local copies of it is how a
 * label drifts between the pie and the table it drills into.
 */
class PurchaseClass
{
    const LABELS = [
        'software-licence'      => 'Software license',
        'managed-hosting'       => 'Managed hosting',
        'cloud-infrastructure'  => 'Cloud infrastructure',
        'oss-support-tier'      => 'Paid tier of open-source software',
        'content-subscription'  => 'Content subscription',
        'professional-services' => 'Professional services',
        'support-maintenance'   => 'Support and maintenance',
        '(unclassified)'        => 'Not yet classified',
    ];

    public static function label(string $key): string
    {
        return self::LABELS[$key] ?? $key;
    }
}
