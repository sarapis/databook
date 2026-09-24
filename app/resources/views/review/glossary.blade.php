@extends('layout')

@section('menubar')
    @include('sub.menubar', ['active' => 'about'])
@endsection

@section('content')
<div class="inner_container">
    <div class="container" style="padding-top: var(--db-space-3); padding-bottom: var(--db-space-5);">

        @php
            $sets = is_array($groups) ? $groups : [];
        @endphp

        <div class="mb-2"><a href="{{ route('review') }}">&larr; All queues</a></div>

        <div class="mb-4">
            <div class="db-eyebrow">Reference</div>
            <h1 class="mb-1">Glossary</h1>
            <p class="db-page-lead">
                What each term on these pages means. The kind definitions are the ones the
                classifier itself was given, word for word &mdash; so they describe the model
                that actually judged the candidate you are looking at.
            </p>
        </div>

        @foreach ($sets as $groupName => $terms)
            <h2 class="mb-3" style="font-size: var(--db-text-xl);">{{ $groupName }}</h2>
            <div class="db-card mb-4">
                <div class="db-card-body">
                    <dl class="mb-0">
                        @foreach ($terms as $t)
                            <dt style="font-family: var(--db-font-mono); font-size: var(--db-text-sm); color: var(--db-primary); font-weight: var(--db-weight-semibold); margin-top: var(--db-space-2);">{{ $t['term'] }}</dt>
                            <dd class="mb-0" style="font-size: var(--db-text-sm); color: var(--db-text);">{{ $t['definition'] }}</dd>
                        @endforeach
                    </dl>
                </div>
            </div>
        @endforeach

    </div>
</div>
@endsection
