{{-- The Data book's two pies (see data-book). Include inside a
     DOMContentLoaded handler, with slice-pies-js loaded in the same handler. --}}
    ovPie('ovKindChart',        @json($dataBlocks['kind'] ?? null));
    ovPie('ovDataAgencyChart',  @json($dataBlocks['agency'] ?? null));
