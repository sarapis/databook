{{-- The Products book's two pies (see products-book). Include inside a
     DOMContentLoaded handler, with slice-pies-js loaded in the same handler. --}}
    ovPie('ovFunctionChart',    @json($prodBlocks['functions'] ?? null));
    ovPie('ovRouteChart',       @json($prodBlocks['route'] ?? null));
    @if(($prodMiddle ?? 'families') === 'kind')
    ovPie('ovPurchaseKindChart',        @json($prodBlocks['kinds'] ?? null));
    @endif
