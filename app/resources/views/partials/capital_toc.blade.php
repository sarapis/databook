{{-- The project profile's table of contents.
     ⚠ Extracted to a partial because it now renders in one of TWO places: beside
     the About row on a project with no map, and below it on one with a map.
     Duplicating five lines of markup would have been the cheaper edit and the
     one that drifts. --}}
<nav class="db-toc">
	<div class="db-toc-title">Contents</div>
	@foreach($toc as $t)<a href="#{{ $t[0] }}">{{ $t[1] }}</a>@endforeach
</nav>
