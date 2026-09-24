/**
 * Digital Services Analysis — Overview storyboard.
 *
 * Scroll-reveal / draw / grow / widen / count animations (data-reveal,
 * data-draw, data-grow, data-widen, data-count), the beat-07 "Ways in"
 * pinned interactive sequence, the left progress rail, and the "Skip story"
 * control that collapses the storyboard for returning visitors.
 *
 * Ported from the design handoff's prototype (design_handoff_digital_services_
 * storyboard/design/Digital Services Storyboard.dc.html). The one structural
 * change: the prototype's beat 07 made its own <section> the scroll container
 * because the design tool's html/body do not scroll. Here the window scrolls,
 * so beat 07 uses ordinary page-level position:sticky and reads window.scrollY
 * instead of a port element's scrollTop.
 */
(function () {
    var SKIP_KEY = 'dsStorySkipped';

    function qa(root, sel) { return Array.prototype.slice.call(root.querySelectorAll(sel)); }

    function initSkip(root) {
        var full = root.querySelector('[data-ds-full]');
        var collapsed = root.querySelector('[data-ds-collapsed]');
        var skipBtn = root.querySelector('[data-ds-skip]');
        var replayBtn = root.querySelector('[data-ds-replay]');
        if (!full || !collapsed) return;

        // Both bars are normal document flow (no position:fixed, no
        // relocating them elsewhere in the DOM) -- they read as one more row
        // of the site's own nav, which is itself position:static, and scroll
        // away with the page exactly the same way. That also means no
        // runtime position/clearance math: the browser already places each
        // one correctly relative to whatever's around it.

        var COLLAPSE_MS = 480;
        var EASE = 'cubic-bezier(.22,.8,.3,1)';

        function persist(skipped) {
            try {
                if (skipped) localStorage.setItem(SKIP_KEY, '1');
                else localStorage.removeItem(SKIP_KEY);
            } catch (e) { /* storage unavailable — still works for this visit */ }
        }

        // No transition -- used once, for the state a returning visitor lands
        // on. Animating on page load (before the reader has done anything)
        // would just be a delay, not a cue.
        function setInitial(skipped) {
            full.hidden = skipped;
            collapsed.hidden = !skipped;
            if (skipBtn) skipBtn.hidden = skipped;
            if (replayBtn) replayBtn.hidden = !skipped;
            persist(skipped);
        }

        // Animated collapse: the story shrinks to nothing rather than
        // vanishing instantly. Because it's a normal block element, the page
        // content that follows rises to fill the space as it shrinks -- the
        // same effect as scrolling quickly past it, without actually moving
        // the reader's scroll position. The bar swap itself is immediate
        // (not tied to the animation), since it's a location both states
        // share rather than two separate controls.
        function collapse() {
            if (full.hidden) return;
            if (skipBtn) skipBtn.hidden = true;
            if (replayBtn) replayBtn.hidden = false;
            var startHeight = full.scrollHeight;
            full.style.height = startHeight + 'px';
            full.style.overflow = 'hidden';
            // Force a reflow so the browser registers the explicit start
            // height before switching to the end state, or there is nothing
            // to transition from and it just jumps.
            void full.offsetHeight;
            full.style.transition = 'height ' + COLLAPSE_MS + 'ms ' + EASE + ', opacity ' + Math.round(COLLAPSE_MS * 0.7) + 'ms ease';
            full.style.height = '0px';
            full.style.opacity = '0';
            setTimeout(function () {
                full.hidden = true;
                full.style.transition = '';
                full.style.height = '';
                full.style.overflow = '';
                full.style.opacity = '';
                collapsed.hidden = false;
            }, COLLAPSE_MS);
            persist(true);
        }

        // Mirrors collapse(): grows back from 0 to its natural height.
        function expand() {
            if (!full.hidden) return;
            if (skipBtn) skipBtn.hidden = false;
            if (replayBtn) replayBtn.hidden = true;
            collapsed.hidden = true;
            full.hidden = false;
            full.style.height = 'auto';
            var targetHeight = full.scrollHeight;
            full.style.height = '0px';
            full.style.overflow = 'hidden';
            full.style.opacity = '0';
            void full.offsetHeight;
            full.style.transition = 'height ' + COLLAPSE_MS + 'ms ' + EASE + ', opacity ' + COLLAPSE_MS + 'ms ease';
            full.style.height = targetHeight + 'px';
            full.style.opacity = '1';
            setTimeout(function () {
                full.style.transition = '';
                full.style.height = '';
                full.style.overflow = '';
                full.style.opacity = '';
            }, COLLAPSE_MS);
            persist(false);
        }

        var skippedBefore = false;
        try { skippedBefore = localStorage.getItem(SKIP_KEY) === '1'; } catch (e) { /* default to showing the story */ }
        setInitial(skippedBefore);

        if (skipBtn) skipBtn.addEventListener('click', collapse);
        if (replayBtn) replayBtn.addEventListener('click', expand);
    }

    function initReveals(root, motion) {
        var reveals = qa(root, '[data-reveal]');
        var draws = qa(root, '[data-draw]');
        var widens = qa(root, '[data-widen]');
        var grows = qa(root, '[data-grow]');
        var counts = qa(root, '[data-count]');

        if (motion) {
            reveals.forEach(function (el) {
                el.style.opacity = '0';
                el.style.transform = 'translateY(20px)';
                el.style.transition = 'opacity .75s cubic-bezier(.22,.8,.3,1), transform .75s cubic-bezier(.22,.8,.3,1)';
                el.style.transitionDelay = (el.getAttribute('data-delay') || 0) + 'ms';
            });
            draws.forEach(function (el) {
                var len = 0;
                try { len = el.getTotalLength(); } catch (e) { len = 0; }
                if (!len) return;
                el.style.strokeDasharray = len;
                el.style.strokeDashoffset = len;
                el.style.transition = 'stroke-dashoffset 1.1s ease';
                el.style.transitionDelay = (el.getAttribute('data-delay') || 0) + 'ms';
                el.setAttribute('data-drawable', '1');
            });
            widens.forEach(function (el) {
                el.style.width = '0%';
                el.style.overflow = 'hidden';
                el.style.transition = 'width 1s cubic-bezier(.22,.8,.3,1)';
                el.style.transitionDelay = (el.getAttribute('data-delay') || 0) + 'ms';
            });
            grows.forEach(function (el) {
                el.style.height = '0px';
                el.style.transition = 'height .95s cubic-bezier(.22,.8,.3,1)';
                el.style.transitionDelay = (el.getAttribute('data-delay') || 0) + 'ms';
            });
        } else {
            widens.forEach(function (el) { el.style.width = el.getAttribute('data-widen') + '%'; });
            grows.forEach(function (el) { el.style.height = el.getAttribute('data-grow') + 'px'; });
            counts.forEach(function (el) { runCount(el, true); });
        }

        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var el = entry.target;
                if (el.hasAttribute('data-reveal')) { el.style.opacity = '1'; el.style.transform = 'none'; }
                if (el.hasAttribute('data-drawable')) el.style.strokeDashoffset = '0';
                if (el.hasAttribute('data-widen')) el.style.width = el.getAttribute('data-widen') + '%';
                if (el.hasAttribute('data-grow')) el.style.height = el.getAttribute('data-grow') + 'px';
                if (el.hasAttribute('data-count')) runCount(el, false);
                io.unobserve(el);
            });
        }, { threshold: 0.2, rootMargin: '0px 0px -8% 0px' });

        if (motion) reveals.concat(draws, widens, counts).forEach(function (el) { io.observe(el); });

        // Zero-height/zero-width targets never reach a fractional threshold at
        // the default observer, so they get a second one at threshold 0.
        var zio = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (!entry.isIntersecting) return;
                var el = entry.target;
                if (el.hasAttribute('data-grow')) el.style.height = el.getAttribute('data-grow') + 'px';
                if (el.hasAttribute('data-widen')) el.style.width = el.getAttribute('data-widen') + '%';
                zio.unobserve(el);
            });
        }, { threshold: 0, rootMargin: '0px 0px -6% 0px' });
        if (motion) grows.concat(widens).forEach(function (el) { zio.observe(el); });
    }

    function runCount(el, immediate) {
        if (el.getAttribute('data-counted')) return;
        el.setAttribute('data-counted', '1');
        var target = parseFloat(el.getAttribute('data-count'));
        var dec = +(el.getAttribute('data-dec') || 0);
        var pre = el.getAttribute('data-pre') || '';
        var post = el.getAttribute('data-post') || '';
        if (immediate) {
            el.textContent = pre + target.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + post;
            return;
        }
        var t0 = performance.now(), dur = 1100;
        function step(now) {
            var p = Math.min(1, (now - t0) / dur);
            var v = target * (1 - Math.pow(1 - p, 3));
            el.textContent = pre + v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + post;
            if (p < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    // The rail is position:fixed, so nothing in the document flow can push it
    // out of the way: it paints wherever it is told to until something hides
    // it. Measured 2026-09-18 -- it was painting over the Overview's own data
    // cards at EVERY width below 1600 (card left edge 24px against the rail's
    // right edge of 35px), and over the story's own body copy below 768.
    // Visible at 1440, the width every verification here has used: an orange
    // dot sat on the word "by" in the Data band's lead. Geometry checks read
    // it clean, because at 1440 the dots land in a card's left PADDING rather
    // than on a glyph -- only the screenshot showed it.
    var RAIL_MIN_WIDTH = 768;   // measured crossover; at 620 the gap is 2px

    function initRail(root) {
        var dots = qa(root, '[data-rail-dot]');
        var beats = qa(root, '[data-beat]');
        if (!dots.length || !beats.length) return;
        var nav = dots[0].parentElement;

        // Two conditions, and both are about whether the rail has a job and a
        // place to do it. Past the storyboard it is indicating progress
        // through something the reader has left; below RAIL_MIN_WIDTH there is
        // no gutter for it to sit in.
        function place() {
            var r = root.getBoundingClientRect();
            var onScreen = r.bottom > 0 && r.top < window.innerHeight;
            var room = window.innerWidth >= RAIL_MIN_WIDTH;
            nav.style.display = (onScreen && room) ? 'flex' : 'none';
        }
        place();
        window.addEventListener('scroll', place, { passive: true });
        window.addEventListener('resize', place);

        function setActive(i) {
            dots.forEach(function (d, n) {
                var on = n === i;
                d.style.background = on ? '#ff941f' : '#c9ced3';
                d.style.width = on ? '9px' : '7px';
                d.style.height = on ? '9px' : '7px';
            });
        }
        var sio = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) setActive(+entry.target.getAttribute('data-beat'));
            });
        }, { threshold: 0.5 });
        beats.forEach(function (s) { sio.observe(s); });
    }

    // Beat 07, "Ways in". Page-level sticky: the window is the scrollport (the
    // prototype's own document didn't scroll, so it made a <section> the
    // scrollport instead — that doesn't apply here). The active row is whichever
    // cue block's rect straddles the viewport midpoint; the stage sticks while
    // its track (560vh) scrolls past underneath it.
    function initWaysIn(root, motion) {
        var track = root.querySelector('[data-x7]');
        if (!track) return;
        var stage = track.querySelector('[data-x7-stage]');
        var inner = track.querySelector('[data-x7-inner]');
        var rows = qa(track, '[data-x7-row]');
        var cues = qa(track, '[data-x7-cue]');
        var thumb = track.querySelector('[data-x7-thumb]');

        function set(row, open, dim) {
            var panel = row.querySelector('[data-x7-panel]');
            var sub = row.querySelector('[data-x7-sub]');
            row.style.opacity = dim ? '0.36' : '1';
            row.style.maxHeight = '1200px';
            if (sub) {
                var show = open || !dim;
                // ⚠ This was a hardcoded 80px, which is two lines at desktop
                // type. At 390 the same sentence wraps to four or five, so the
                // last line was sliced through the middle of its glyphs --
                // "plus the searchable ind" with the rest of the word cut off.
                // A clipped line is a wrong line. The panel beside it already
                // measures itself; the subtitle now does the same, so it fits
                // at every width by construction rather than by a number that
                // was right for one.
                sub.style.maxHeight = show ? (sub.scrollHeight + 'px') : '0px';
                sub.style.opacity = show ? '1' : '0';
                sub.style.marginTop = show ? '6px' : '0px';
            }
            panel.style.maxHeight = open ? panel.scrollHeight + 'px' : '0px';
            panel.style.opacity = open ? '1' : '0';
        }

        if (!motion) {
            track.style.height = 'auto';
            stage.style.position = 'static';
            stage.style.height = 'auto';
            stage.style.padding = '110px 0';
            rows.forEach(function (r) { set(r, true, false); });
            return;
        }

        function fit() {
            inner.style.transform = 'none';
            var avail = stage.clientHeight - 28;
            var need = inner.scrollHeight;
            var k = need > avail ? Math.max(0.6, avail / need) : 1;
            inner.style.transform = k < 1 ? 'scale(' + k + ')' : 'none';
        }

        var current;
        function apply(idx) {
            if (idx === current) return;
            current = idx;
            rows.forEach(function (r, i) { set(r, i === idx, idx > -1 && i !== idx); });
            fit();
            setTimeout(function () { fit(); progress(); }, 640);
        }

        function resolve() {
            var mid = window.innerHeight / 2;
            for (var i = 0; i < cues.length; i++) {
                var r = cues[i].getBoundingClientRect();
                if (r.top <= mid && r.bottom > mid) { apply(+cues[i].getAttribute('data-x7-cue')); return; }
            }
        }
        function progress() {
            if (!thumb) return;
            var trackRect = track.getBoundingClientRect();
            var max = track.scrollHeight - window.innerHeight;
            var scrolled = -trackRect.top;
            var p = max > 0 ? Math.min(1, Math.max(0, scrolled / max)) : 0;
            var rail = thumb.parentElement.clientHeight;
            thumb.style.transform = 'translateY(' + (p * (rail - thumb.offsetHeight)) + 'px)';
        }

        window.addEventListener('scroll', function () { resolve(); progress(); }, { passive: true });
        window.addEventListener('resize', function () { current = null; resolve(); });
        requestAnimationFrame(resolve);
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { current = null; resolve(); });
    }

    function init() {
        var root = document.getElementById('dsStoryboard');
        if (!root) return;
        initSkip(root);

        var reduce = false;
        try { reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { /* assume motion is fine */ }
        var motion = !reduce;

        initReveals(root, motion);
        initRail(root);
        initWaysIn(root, motion);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
