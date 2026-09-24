<?php

namespace App\Http\Controllers;

use App\Custom\DatabookAPI;
use Illuminate\Http\Request;

/**
 * The curation review app — Phase 1 of docs/REVIEW-APP-SCOPE.md.
 *
 * A PURE CONSUMER of /review/*, on the /admin/orgs precedent: no invariant is
 * re-implemented here. Which verbs a queue accepts, whether a decision may be
 * recorded, what counts as already-decided — all of that is the API's, so it
 * holds for a curl and a bulk script too, not only for this screen.
 *
 * ⚠⚠ THE ACTOR IS SENT, NOT JUST DISPLAYED — and that is the one place this
 * deliberately differs from OrgAdmin, whose own comment says the API attributes
 * a change to the token's user and that its actor() is "only the label on
 * screen". The app calls the API server-to-server with ONE service token, so
 * without forwarding, two reviewers would be recorded as the same string,
 * permanently. Attribution is the whole point of this queue.
 *
 * ⚠ The value comes from the server var nginx sets from the VERIFIED basic-auth
 * credential — never from a form field, which a reviewer could edit to claim to
 * be the other reviewer. When magic-link sessions land (scope doc §6.1) this is
 * the one method that changes.
 */
class Review extends Controller
{
	public function index(Request $request)
	{
		list($status, $body) = DatabookAPI::adminReq('/review/queues');
		if ($status !== 200)
			return $this->unavailable($status, $body);
		return view('review.index', [
			'pagetitle' => 'Review queues',
			'queues'    => $body['queues'] ?? [],
			'editor'    => $this->actor($request),
		]);
	}

	public function queue(Request $request, $queue)
	{
		list($status, $body) = DatabookAPI::adminReq(
			'/review/queues/' . rawurlencode($queue) . '/items?limit=500');
		if ($status !== 200)
			return $this->unavailable($status, $body);
		return view('review.queue', [
			'pagetitle' => $body['queue'] ?? $queue,
			'queue'     => $body,
			'editor'    => $this->actor($request),
		]);
	}

	public function item(Request $request, $queue, $item)
	{
		list($status, $body) = DatabookAPI::adminReq(
			'/review/queues/' . rawurlencode($queue) . '/items?limit=2000');
		if ($status !== 200)
			return $this->unavailable($status, $body);

		$items = $body['items'] ?? [];
		// ⚠ Position is computed from the SAME list the queue page shows, so
		// "3 of 132" and the order you move through cannot disagree with it.
		$idx = null;
		foreach ($items as $i => $row) {
			if (($row['item_id'] ?? null) === $item) { $idx = $i; break; }
		}
		if ($idx === null)
			abort(404);

		// ⚠ The kind vocabulary comes from the API, which takes it from the
		// classifier's own enum. A list typed into the view omitted three of
		// the nine kinds — see the view's comment.
		list($gstatus, $gbody) = DatabookAPI::adminReq('/review/glossary');
		$kinds = [];
		foreach (($gbody['terms'] ?? []) as $t) {
			if (($t['group'] ?? '') === 'Kinds a candidate can be')
				$kinds[] = $t['term'];
		}

		return view('review.item', [
			'pagetitle' => ($items[$idx]['subject'] ?? $item),
			'queue'     => $body,
			'item'      => $items[$idx],
			'position'  => $idx + 1,
			'total'     => count($items),
			'nextId'    => $this->nextUndecided($items, $idx),
			'kinds'     => $kinds,
			'editor'    => $this->actor($request),
		]);
	}

	public function glossary(Request $request)
	{
		list($status, $body) = DatabookAPI::adminReq('/review/glossary');
		if ($status !== 200)
			return $this->unavailable($status, $body);
		// ⚠ Grouped for display only. The definitions are served, never written
		// here — the KIND ones are the classifier's own words, and a paraphrase
		// in a template would describe a different classifier than the one that
		// produced the candidate on screen.
		$groups = [];
		foreach (($body['terms'] ?? []) as $t) {
			$groups[$t['group'] ?? 'Terms'][] = $t;
		}
		return view('review.glossary', [
			'pagetitle' => 'Glossary',
			'groups'    => $groups,
			'editor'    => $this->actor($request),
		]);
	}

	public function addLink(Request $request, $queue, $item)
	{
		list($status, $body) = DatabookAPI::adminReq(
			'/review/queues/' . rawurlencode($queue) . '/links', 'post', [
				'item_id'   => $item,
				'url'       => (string)$request->input('url'),
				'note'      => (string)$request->input('note', ''),
				// ⚠ The reviewer may flag it as a source when adding, or later.
				// Nothing promotes a link automatically.
				'is_source' => (bool)$request->input('is_source', false),
				'actor'     => $this->actor($request),
			]);
		// ⚠ The API's refusal is passed through, never replaced. It names WHY a
		// URL was rejected, which is what lets a reviewer fix a typo instead of
		// retyping the same unusable link.
		$back = redirect()->route('review.item', [$queue, $item]);
		return $status === 200 ? $back
			: $back->with('error', $body['detail'] ?? 'the link was not saved');
	}

	public function deleteLink(Request $request, $queue, $item, $link)
	{
		list($status, $body) = DatabookAPI::adminReq(
			'/review/queues/' . rawurlencode($queue) . '/links/'
			. (int)$link . '/delete', 'post', []);
		$back = redirect()->route('review.item', [$queue, $item]);
		return $status === 200 ? $back
			: $back->with('error', $body['detail'] ?? 'the link was not removed');
	}

	public function flagLink(Request $request, $queue, $item, $link)
	{
		list($status, $body) = DatabookAPI::adminReq(
			'/review/queues/' . rawurlencode($queue) . '/links/'
			. (int)$link . '/source', 'post',
			['is_source' => (bool)$request->input('is_source', true)]);
		$back = redirect()->route('review.item', [$queue, $item]);
		return $status === 200 ? $back
			: $back->with('error', $body['detail'] ?? 'the link was not updated');
	}

	public function decide(Request $request, $queue, $item)
	{
		$payload = [
			'item_id' => $item,
			'verb'    => (string)$request->input('verb'),
			'value'   => $request->input('value'),
			'note'    => (string)$request->input('note', ''),
			// ⚠ THE LINE THAT MAKES ATTRIBUTION TRUE. See the class docstring.
			'actor'   => $this->actor($request),
		];
		list($status, $body) = DatabookAPI::adminReq(
			'/review/queues/' . rawurlencode($queue) . '/decisions', 'post', $payload);

		if ($status !== 200) {
			// ⚠ The API's own refusal is shown, never a generic failure — it
			// names the verb a queue accepts, which is the useful half.
			return redirect()->route('review.item', [$queue, $item])
				->with('error', $body['detail'] ?? 'the decision was not recorded');
		}
		$next = (string)$request->input('next', '');
		if ($next !== '')
			return redirect()->route('review.item', [$queue, $next]);
		return redirect()->route('review.queue', [$queue])
			->with('recorded', $item);
	}

	/** The next item with no decision and not already settled by the seed. */
	private function nextUndecided(array $items, int $from)
	{
		for ($i = $from + 1; $i < count($items); $i++) {
			$row = $items[$i];
			if (empty($row['decision']) && empty($row['in_seed']))
				return $row['item_id'];
		}
		return null;
	}

	private function unavailable($status, $body)
	{
		return response()->view('admin.orgs.unavailable', [
			'pagetitle' => 'Review unavailable',
			'status'    => $status,
			'detail'    => $body['detail'] ?? $body,
		], $status === 0 ? 503 : 502);
	}

	/**
	 * Who is reviewing, per the origin's basic-auth gate.
	 *
	 * ⚠ Unlike OrgAdmin::actor(), this value is SENT to the API and becomes the
	 * durable record. It must therefore come from the server var nginx sets
	 * from the verified credential — never from anything the browser supplies.
	 */
	private function actor(Request $request)
	{
		return $request->server('PHP_AUTH_USER')
			?: $request->server('REMOTE_USER')
			?: null;
	}
}
