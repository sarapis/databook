{{--
    "Observed running on the public web" - the City Web Estate Explorer's scan,
    joined to this licence family.

    ⚠⚠ THE WORDING IS THE LOAD-BEARING PART. "Observed", never "uses" or "runs
    on": a header means the server named itself, a tag means a resource was
    referenced. Both are strong; neither is "this agency uses this product".

    ⚠ Rendered in the Analysis identity because it is an interpretation layer,
    like the rest of this section - not a procurement record. The procurement
    record is the page around it.

    ⚠ `finding_class` is deliberately NOT rendered. It is their taxonomy, and its
    class B means "no purchase record found" - a judgement about OUR data that
    this page is itself the evidence for.
--}}
@if(!empty($webEstate))
    @php
        $we = $webEstate;
        // ⚠ Grades map to badge tone, strongest first. Precomputed here because a
        // @if glued to a word character is not compiled by Blade - a trap this
        // repo has already paid for on this very page family.
        $tone = [
            'runtime'     => 'db-badge-success',
            'header'      => 'db-badge-success',
            'form-action' => 'db-badge-info',
            'tag-src'     => 'db-badge-navy',
        ];
    @endphp
    <div class="db-table-wrap mb-3" id="web-estate">
        <div class="px-3 pt-3">
            <h2 class="lic-h2"><i class="bi bi-broadcast"></i> Observed running on the public web</h2>
            @if($we['kind'] === 'observed')
                <p class="lic-sub mb-0">
                    An independent scan of 243 public City hosts found this product
                    named in {{ number_format($we['total']) }}
                    {{ $we['total'] === 1 ? 'place' : 'places' }}.
                    Observed, not confirmed in use &mdash; a response header means the
                    server named itself and a tag means a resource was referenced.
                </p>
            @else
                <p class="lic-sub mb-0">
                    The City holds contracts for this family; the scan of 243 public
                    hosts found no publishable-grade evidence of it running.
                </p>
            @endif
        </div>

        @if($we['kind'] === 'observed')
            @foreach($we['components'] as $c)
                <div class="px-3 pt-3">
                    {{-- ⚠ The COMPONENT name, not the family name. Four Microsoft
                         components map to our one `microsoft` family, and without
                         naming them the panel reads as a claim about the whole
                         family's spend. --}}
                    <h3 class="lic-h3 mb-1">{{ $c['name'] }}</h3>
                </div>
                <table class="db-table db-dt">
                    <thead><tr><th>Host</th><th>Evidence</th><th>Detail</th></tr></thead>
                    <tbody>
                    @foreach($c['observations'] as $o)
                        <tr>
                            <td><a href="https://{{ $o['host'] }}" rel="nofollow noopener external" target="_blank">{{ $o['host'] }}</a></td>
                            <td><span class="db-badge {{ $tone[$o['evidence']] ?? 'db-badge-navy' }}">{{ $o['evidence'] }}</span></td>
                            <td><code class="lic-mono">{{ $o['detail'] ?? '' }}</code></td>
                        </tr>
                    @endforeach
                    </tbody>
                </table>
                @if($c['total'] > count($c['observations']))
                    {{-- ⚠ COUNT BEFORE YOU CAP. Microsoft IIS alone carries 54. --}}
                    <p class="lic-sub px-3 pb-2 mb-0">
                        Showing {{ count($c['observations']) }} of {{ number_format($c['total']) }}.
                    </p>
                @endif
            @endforeach
        @elseif(!empty($we['strongest']))
            <p class="lic-sub px-3 pb-2 mb-0">Seen only at {{ $we['strongest'] }}, which is below the publishable bar.</p>
        @endif

        <p class="lic-sub px-3 pb-3 mb-0">
            {{-- ⚠⚠ ABSENCE FROM THE SCAN IS NOT ABSENCE OF USE, and saying so is
                 not hedging: 49 of the 243 hosts do not answer a public request at
                 all and 33 refuse automated ones. Without this line an empty or
                 short list reads as a finding about the City rather than about
                 the scan. --}}
            Scanned {{ $we['scanned'] }} by the
            <a href="https://nyc-web-estate.pages.dev/" rel="noopener" target="_blank">City Web Estate Explorer</a>,
            an independent audit by Sarapis. Absence from this scan is not evidence
            a product is unused &mdash; 49 of the 243 hosts do not answer a public
            request at all and 33 refuse automated ones.
        </p>
    </div>
@endif
