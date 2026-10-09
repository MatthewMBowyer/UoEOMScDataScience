/* ==========================================================================
   guide-bot.js — the AMBIENT FACTS BOT runtime.

   A small character that lives on the site, drifts around the viewport and
   periodically surfaces a fact ABOUT THE PAGE THE VISITOR IS CURRENTLY ON. It is
   a tour guide, not a chatbot: it answers nothing and it never invents.

   Build time = Python (scripts/build_knowledge.py), which emits
   assets/data/facts.json keyed by page path, each fact carrying its source
   (cv | site | repo:<name>). Run time = this file, because Python cannot run in
   a browser and a static host serves no server-side code. Hard constraint.

   Guarantees:
     * No network request of any kind. The only value read from the document is
       the current pathname; nothing is sent anywhere.
     * A HARD minimum interval between facts (MIN_FACT_INTERVAL_MS). The first
       fact appears a few seconds after load; it COUNTS, so the next is not due
       until the floor has elapsed. Cadence never accelerates with time on page.
     * No sound, no modal, no focus stealing, one bubble at a time.
     * Facts never repeat within a visit (sessionStorage seen-set). A dismiss is
       respected for the whole session. Nothing personal is stored.
     * prefers-reduced-motion: the character does not animate its position, but
       facts still appear on the same cadence.
     * Honest labelling: no chat framing; it is a page guide, not an AI service.
   ========================================================================== */
(function () {
  "use strict";

  /* --- the ONE cadence constant (AC-100 / AC-109). Tunable in one place only. */
  var MIN_FACT_INTERVAL_MS = 45000;   // 45s HARD FLOOR between consecutive facts
                                      // (raised from 30s at the owner's request,
                                      // 2026-10-07: "page guide slower prompts")
  var FIRST_FACT_DELAY_MS = 5000;     // the single early fact, a few seconds in
  var INTRO_DELAY_MS = 1200;          // brief, one-time self-introduction

  var MOVE_EVERY_MS = 9000;           // positional drift rhythm (facts are NOT
                                      // tied to movement)
  var EDGE = 16;                      // keep this many px inside every edge
  var OBSTRUCTION_STEP = 16;          // px between candidate root positions

  var THROW_VELOCITY = 0.55;          // px/ms; a release above this is a throw
  var RUNBACK_MS = 1500;              // how long the character takes to run back
  var THROW_QUIET_MS = 300000;        // 5 minutes of quiet after a SECOND throw

  // Owner's wording (2026-10-09): the intro must say what to do to quiet the
  // guide AND how long it stays quiet. Two routes, two different durations, so
  // both are named: a SECOND throw buys 5 minutes, Escape hides it for the rest
  // of the visit. The owner's own draft said "click me ... to shut me up", which
  // is the opposite of what clicking does, so this states the real controls.
  var QUIET_HINT =
    "I'm just here to give facts about this page. Tap me for the next one. "
    + "To quiet me: drag me out of the way, or throw me twice and I go quiet "
    + "for 5 minutes. Escape hides me for the rest of this visit.";

  var FACTS_URL = "assets/data/facts.json";
  var FACT_SOURCES_NOTE =
    "The facts are generated offline from Matthew's CV and portfolio at build "
    + "time.";

  var SEEN_KEY = "epoGuideSeen";
  var DISMISS_KEY = "epoGuideDismissed";
  var INTRO_KEY = "epoGuideIntro";

  function currentPage() {
    var path = window.location.pathname || "";
    var name = path.substring(path.lastIndexOf("/") + 1);
    if (!name || name.indexOf(".") === -1) { name = "index.html"; }
    try { return decodeURIComponent(name); } catch (e) { return name; }
  }

  function loadPools() {
    if (typeof fetch !== "function") { return Promise.resolve({}); }
    // SAME-ORIGIN request for one of the site's own files. Not external.
    return fetch(FACTS_URL, { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .catch(function () { return {}; });
  }

  function readJSON(store, key) {
    if (!store) { return {}; }
    try { return JSON.parse(store.getItem(key) || "{}") || {}; } catch (e) { return {}; }
  }

  function writeJSON(store, key, obj) {
    if (!store) { return; }
    try { store.setItem(key, JSON.stringify(obj)); } catch (e) { /* full/blocked */ }
  }

  function hash(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return "f" + (h >>> 0).toString(36);
  }

  function monthName(m) {
    return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
            "Nov", "Dec"][m - 1] || "";
  }

  /* Compose a fact at RENDER time. An experience-bearing fact reads its figure
     from assets/js/experience.js, so it is never stored as a literal (AC-105). */
  function compose(fact, now) {
    if (fact.indexOf("{years}") === -1 && fact.indexOf("{career_start}") === -1) {
      return fact;
    }
    var exp = window.Experience || {};
    var at = now ? new Date(now) : new Date();
    var years = (typeof exp.yearsOfExperience === "function")
      ? exp.yearsOfExperience(at) : "";
    var start = exp.CAREER_START
      ? (monthName(exp.CAREER_START.month) + " " + exp.CAREER_START.year) : "";
    return fact.replace(/\{years\}/g, years).replace(/\{career_start\}/g, start);
  }

  function build() {
    var sessionStore = null;
    try { sessionStore = window.sessionStorage; } catch (e) { sessionStore = null; }

    var noMotion = !!(window.matchMedia
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

    var root = document.createElement("div");
    root.id = "guide-bot";
    root.className = "guide-bot";
    root.setAttribute("role", "complementary");
    root.setAttribute("aria-label", "Things worth knowing about this page");

    var bubble = document.createElement("p");
    bubble.className = "guide-bot__bubble";
    bubble.id = "guide-bot-fact";
    bubble.setAttribute("aria-live", "polite");
    bubble.hidden = true;

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "guide-bot__btn";
    btn.setAttribute("aria-label", "Show the next fact about this page");
    btn.title = "Show the next fact about this page (drag or throw me if you like)";
    /* A cooler figure, still restrained line art inside the existing design
       system: a rounded guide badge with a compass needle drawn in the site
       accent. No mascot, no gradient, no blanket shadow, no emoji. Drawn inline
       so it adds no request and no image asset. */
    btn.innerHTML =
      '<svg class="guide-bot__svg" viewBox="0 0 32 32" aria-hidden="true" ' +
      'focusable="false" fill="none" stroke="currentColor" stroke-width="1.5" ' +
      'stroke-linecap="round" stroke-linejoin="round">' +
      '<path class="guide-bot__badge" d="M10 3h12a7 7 0 0 1 7 7v12a7 7 0 0 1-7 7H10a7 7 0 0 1-7-7V10a7 7 0 0 1 7-7z"></path>' +
      '<path d="M21.5 10.5l-3.2 8.3-8.3 3.2 3.2-8.3z"></path>' +
      '<circle class="guide-bot__dot" cx="16" cy="16" r="1.6" stroke="none">' +
      '</circle></svg>';

    root.appendChild(bubble);
    root.appendChild(btn);
    document.body.appendChild(root);

    var s = {
      pools: {}, page: currentPage(),
      seen: readJSON(sessionStore, SEEN_KEY),
      dismissed: !!readJSON(sessionStore, DISMISS_KEY).dismissed,
      noMotion: noMotion,
      x: 0, y: 0,
      lastFactAt: 0, // epoch ms of the last shown fact (0 = none yet)
      factCount: 0, shownFacts: [], introShown: false,
      factTimer: null, moveTimer: null, quietTimer: null,
      quietUntil: 0,
      throwCount: 0, returning: false,
      dragging: false, dragStart: null, lastPointer: null, lastPointerAt: 0,
      anchor: null, longestText: "", withBubble: false
    };

    function viewport() {
      return { w: document.documentElement.clientWidth,
               h: document.documentElement.clientHeight };
    }

    /* Measure the widget as it is NOW: the bubble is measured with its current
       text, or with the longest text it may later carry when it is empty. A spot
       chosen for a short fact therefore cannot be overrun by a longer one, since
       every fact re-places before it is shown. Returns the full flex-row box
       (bubble + gap + character) and the character's own box. */
    function size() {
      var wasHidden = bubble.hidden;
      var wasText = bubble.textContent;
      if (!wasText) { bubble.textContent = s.longestText || "Warming up the page guide."; }
      bubble.hidden = false;
      var fullW = root.offsetWidth || 220;
      var fullH = root.offsetHeight || 40;
      var btnW = btn.offsetWidth || 54;
      var btnH = btn.offsetHeight || 54;
      bubble.textContent = wasText;
      bubble.hidden = wasHidden;
      return { w: fullW, h: fullH, btnW: btnW, btnH: btnH };
    }

    /* The REAL content the character and its bubble must never cover: the nav,
       the primary CTA rows, any form field, and every line of text and every
       meaningful image inside <main>. This is measured from the live DOM, not
       guessed from a selector list, so the widget cannot come to rest over the
       sentence the visitor is reading (AC-98 / AC-110 / INV-43 / INV-46).
       `withImages` adds the page's media; a spot clearing text but not a large
       banner is still preferred over one that clears neither, so the placement
       can always find room for a long fact (AC-102 / AC-108). */
    function contentRects(withImages) {
      var vp = viewport();
      var out = [];
      var add = function (r) {
        if (!r || r.width <= 1 || r.height <= 1) { return; }
        if (r.bottom < 0 || r.top > vp.h) { return; }
        out.push({ left: r.left, top: r.top, right: r.right, bottom: r.bottom });
      };
      var addEl = function (el) {
        if (!el) { return; }
        var st = window.getComputedStyle(el);
        if (st.display === "none" || st.visibility === "hidden"
            || parseFloat(st.opacity) < 0.05) { return; }
        add(el.getBoundingClientRect());
      };
      addEl(document.getElementById("titleBar"));
      addEl(document.getElementById("nav"));
      addEl(document.querySelector(".header-cta"));
      addEl(document.querySelector(".cta-row"));
      addEl(document.querySelector("form"));
      var fields = document.querySelectorAll(
        "form input, form textarea, form select, input, textarea, select");
      for (var i = 0; i < fields.length; i++) { addEl(fields[i]); }

      var main = document.querySelector("main") || document.body;
      var walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, null);
      var node;
      while ((node = walker.nextNode())) {
        var text = node.nodeValue;
        if (!text || !text.trim()) { continue; }
        if (node.parentElement
            && node.parentElement.closest("#guide-bot")) { continue; }
        var range = document.createRange();
        range.selectNodeContents(node);
        var rects = range.getClientRects();
        for (var j = 0; j < rects.length; j++) { add(rects[j]); }
      }
      if (withImages) {
        var visuals = main.querySelectorAll("img, figure, svg, video, canvas");
        for (var k = 0; k < visuals.length; k++) {
          if (visuals[k].closest("#guide-bot")) { continue; }
          addEl(visuals[k]);
        }
      }
      return out;
    }

    function intersects(a, b) {
      return a.left < b.right && a.right > b.left &&
             a.top < b.bottom && a.bottom > b.top;
    }

    /* The horizontal band the visitor actually reads. Placement is biased OUT
       of it (into the left/right margins or the bottom band) so the character
       settles on the outskirts of the page (AC-110). */
    function readingColumn() {
      var el = document.querySelector("main .wrap")
            || document.querySelector("main")
            || document.querySelector(".wrap");
      if (!el) { return null; }
      var r = el.getBoundingClientRect();
      if (r.width <= 0) { return null; }
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    }

    function applyPos() {
      root.style.transform = "translate(" + s.x + "px," + s.y + "px)";
    }

    /* Find a settled spot that clears real content, preferring the page
       outskirts. Two boxes are tested: the whole widget (bubble + character)
       and the character alone. Returns `{anchor, withBubble}` — when only the
       character fits, the bubble must stay hidden (AC-108 honest silence). */
    function safeAnchor() {
      var vp = viewport();
      var sz = size();
      var textContent = contentRects(false);       // nav + CTA + form + every text line
      var fullContent = contentRects(true);        // the above + page media
      var btnW = sz.btnW, btnH = sz.btnH;
      var col = readingColumn();
      var step = OBSTRUCTION_STEP;

      var free = function (content, x, y, w, h) {
        if (x < EDGE || y < EDGE) { return false; }
        if (x + w > vp.w - EDGE || y + h > vp.h - EDGE) { return false; }
        var rect = { left: x, top: y, right: x + w, bottom: y + h };
        for (var i = 0; i < content.length; i++) {
          if (intersects(rect, content[i])) { return false; }
        }
        return true;
      };
      // The visitor SEES the character; AC-110 is measured on the character's
      // own box, so that is what must sit on the outskirts. The character is the
      // right-hand element of the flex row.
      var charRect = function (rootX, y) {
        return { left: rootX + sz.w - btnW, top: y,
                 right: rootX + sz.w, bottom: y + btnH };
      };
      var offColumn = function (r) {
        if (!col || (col.right - col.left) >= vp.w - 2 * EDGE) { return false; }
        return r.right <= col.left + 1 || r.left >= col.right - 1;
      };

      /* Collect every spot where the widget (bubble + character) clears `content`
         AND the character alone clears it. `imgOk` records whether the spot also
         clears the page media, so a text-only fallback is only used when nothing
         else exists. */
      var scan = function (content) {
        var spots = [];
        for (var y = EDGE; y <= vp.h - sz.h - EDGE; y += step) {
          for (var x = EDGE; x <= vp.w - sz.w - EDGE; x += step) {
            if (!free(content, x, y, sz.w, sz.h)) { continue; }
            if (!free(content, x + sz.w - btnW, y, btnW, btnH)) { continue; }
            var cr = charRect(x, y);
            spots.push({ x: x, y: y, off: offColumn(cr),
                         score: outskirtsScore(cr, vp, col) });
          }
        }
        return spots;
      };

      // Prefer spots whose CHARACTER is off the reading column; fall back to all
      // only when no such spot clears the page content.
      var pickFrom = function (list) {
        var off = list.filter(function (c) { return c.off; });
        var pool = off.length ? off : list;
        pool.sort(function (a, b) { return b.score - a.score; });
        var k = Math.max(1, Math.ceil(pool.length * 0.15));
        return pool[Math.floor(Math.random() * k)];
      };

      // Tier 1: clear everything, media included. Tier 2: clear text + CTA even
      // if that means a large banner sits behind the widget (long facts have no
      // Tier-1 spot at all).
      var scored = scan(fullContent);
      if (!scored.length) { scored = scan(textContent); }
      if (scored.length) {
        var pick = pickFrom(scored);
        return { x: pick.x, y: pick.y, withBubble: true };
      }

      // No room for the bubble: settle the character alone on the outskirts.
      var charSpots = [];
      for (var cy = EDGE; cy <= vp.h - btnH - EDGE; cy += step) {
        for (var cx = EDGE; cx <= vp.w - btnW - EDGE; cx += step) {
          if (!free(textContent, cx, cy, btnW, btnH)) { continue; }
          charSpots.push({ x: cx, y: cy,
            off: offColumn({ left: cx, top: cy, right: cx + btnW, bottom: cy + btnH }),
            score: outskirtsScore({ left: cx, top: cy,
                                    right: cx + btnW, bottom: cy + btnH }, vp, col) });
        }
      }
      if (charSpots.length) {
        var cpick = pickFrom(charSpots);
        // With the bubble hidden the root collapses to the character's own box,
        // so the root origin IS the character's left edge (stays on screen).
        return { x: cpick.x, y: cpick.y, withBubble: false };
      }
      return null;
    }

    /* Higher = closer to the page margins/edges and off the reading column.
       Scored on the CHARACTER's rect, which is what the visitor sees. */
    function outskirtsScore(r, vp, col) {
      var cx = (r.left + r.right) / 2, cy = (r.top + r.bottom) / 2;
      var edge = (vp.w / 2 - Math.min(cx, vp.w - cx))
               + (vp.h / 2 - Math.min(cy, vp.h - cy));
      var colBonus = 0;
      if (col && (col.right - col.left) < vp.w - 2 * EDGE) {
        if (r.right <= col.left) { colBonus = col.left - r.right; }
        else if (r.left >= col.right) { colBonus = r.left - col.right; }
      }
      return colBonus * 4 + edge + cy * 0.5;
    }

    function hideBubble() {
      bubble.hidden = true;
    }

    function place() {
      if (s.dismissed || s.dragging) { return { x: s.x, y: s.y }; }
      var vp = viewport();
      var sz = size();
      var anchor = safeAnchor();
      if (!anchor) {
        // No spot clears the content: park the character at the bottom edge,
        // never the bubble.
        hideBubble();
        s.x = Math.max(EDGE, vp.w - sz.w - EDGE);
        s.y = Math.max(EDGE, vp.h - sz.h - EDGE);
        applyPos();
        return { x: s.x, y: s.y };
      }
      s.anchor = anchor;
      s.withBubble = anchor.withBubble;
      if (!anchor.withBubble) { hideBubble(); }
      s.x = anchor.x;
      s.y = anchor.y;
      applyPos();
      return { x: s.x, y: s.y };
    }

    function placeSafely() {
      // Deterministic fallback used only where randomness is undesirable.
      place();
      return { x: s.x, y: s.y };
    }

    /* --- quiet mode: the 5-minute bargain (AC-114) ------------------------- */
    function isQuiet() { return Date.now() < s.quietUntil; }

    /* The resumption path the quiet timer runs. Exposed to the harness so the
       mechanism can be proven without waiting five real minutes. */
    function resumeFromQuiet() {
      s.quietUntil = 0;
      if (s.dismissed) { return; }
      place();
      if (!s.noMotion) {
        s.moveTimer = setInterval(function () { place(); }, MOVE_EVERY_MS);
      }
      scheduleNextFact();
    }

    function enterQuiet() {
      s.quietUntil = Date.now() + THROW_QUIET_MS;
      if (s.factTimer) { clearTimeout(s.factTimer); s.factTimer = null; }
      if (s.moveTimer) { clearInterval(s.moveTimer); s.moveTimer = null; }
      if (s.quietTimer) { clearTimeout(s.quietTimer); s.quietTimer = null; }
      s.quietTimer = setTimeout(function () {
        s.quietTimer = null;
        resumeFromQuiet();
      }, THROW_QUIET_MS);
    }

    /* --- drag and throw (AC-112 / AC-113) ---------------------------------- */
    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

    function moveTo(x, y) {
      var vp = viewport();
      var sz = size();
      s.x = clamp(x, EDGE, Math.max(EDGE, vp.w - sz.w - EDGE));
      s.y = clamp(y, EDGE, Math.max(EDGE, vp.h - sz.h - EDGE));
      applyPos();
    }

    function say(text) {
      bubble.textContent = text;
      bubble.hidden = false;
      place();
    }

    /* After a throw the character RUNS BACK to its resting behaviour. */
    function runBack() {
      s.returning = true;
      var finish = function () { s.returning = false; place(); };
      if (s.noMotion) { finish(); return; }   // reduced motion: no travel
      setTimeout(finish, RUNBACK_MS);
    }

    /* Fling the character. The first throw sends it away and it runs back with
       the owner's line; a SECOND throw buys five minutes of quiet. */
    function throwBot(vx, vy) {
      if (s.dismissed) { return; }
      var vp = viewport();
      var mag = Math.sqrt(vx * vx + vy * vy) || 1;
      // Land near the edge in the direction of travel.
      var tx = s.x + (vx / mag) * vp.w * 0.6;
      var ty = s.y + (vy / mag) * vp.h * 0.6;
      moveTo(tx, ty);
      s.throwCount += 1;
      if (s.throwCount >= 2) {
        say("Right, that's twice. I'll be quiet for 5 minutes.");
        enterQuiet();
        return;
      }
      say("Wheee! Throw me again and I'll be quiet for 5 min.");
      runBack();
    }

    function endDrag(vx, vy) {
      if (!s.dragging) { return; }
      s.dragging = false;
      if (s.dismissed) { return; }
      if (Math.sqrt(vx * vx + vy * vy) >= THROW_VELOCITY) {
        throwBot(vx, vy);
      } else {
        place();
      }
    }

    btn.addEventListener("pointerdown", function (e) {
      if (e.button !== undefined && e.button !== 0) { return; }
      s.dragging = true;
      s.dragStart = { x: s.x, y: s.y, px: e.clientX, py: e.clientY };
      s.lastPointer = { x: e.clientX, y: e.clientY, t: Date.now() };
      s.lastPointerAt = Date.now();
      try { btn.setPointerCapture(e.pointerId); } catch (err) { /* older UA */ }
      e.preventDefault();
    });
    document.addEventListener("pointermove", function (e) {
      if (!s.dragging || s.dismissed) { return; }
      moveTo(s.dragStart.x + (e.clientX - s.dragStart.px),
             s.dragStart.y + (e.clientY - s.dragStart.py));
      s.lastPointer = { x: e.clientX, y: e.clientY, t: Date.now() };
    });
    document.addEventListener("pointerup", function (e) {
      if (!s.dragging) { return; }
      var vx = 0, vy = 0;
      if (s.lastPointer) {
        var dt = Math.max(1, Date.now() - s.lastPointerAt);
        vx = (e.clientX - s.lastPointer.x) / dt;
        vy = (e.clientY - s.lastPointer.y) / dt;
      }
      endDrag(vx, vy);
    });

    /* --- facts ------------------------------------------------------------- */
    function candidates() {
      var pool = s.pools[s.page] || [];
      var out = [];
      for (var i = 0; i < pool.length; i++) {
        var text = compose(pool[i].fact || "").trim();
        if (text && !s.seen[hash(text)]) { out.push(text); }
      }
      return out;
    }

    function takeFactFrom(list) {
      if (!list.length) { return null; }
      var text = list[Math.floor(Math.random() * list.length)];
      s.seen[hash(text)] = 1;
      writeJSON(sessionStore, SEEN_KEY, s.seen);
      return text;
    }

    function renderFact(now) {
      var list = candidates();
      // Prefer a fact that FITS without covering the page: try the shorter ones
      // first, so a long fact that cannot be placed never suppresses a shorter
      // one that can. A fact is only marked seen once it is actually shown.
      list.sort(function (a, b) { return a.length - b.length; });
      for (var i = 0; i < list.length; i++) {
        var text = list[i];
        bubble.textContent = text;
        bubble.hidden = false;
        var anchor = safeAnchor();
        if (anchor && anchor.withBubble) {
          s.anchor = anchor;
          s.withBubble = true;
          s.x = anchor.x;
          s.y = anchor.y;
          applyPos();
          s.seen[hash(text)] = 1;
          writeJSON(sessionStore, SEEN_KEY, s.seen);
          s.factCount++;
          s.shownFacts.push(text);
          s.lastFactAt = now;
          return text;
        }
      }
      // Nothing fits without covering content (e.g. a narrow phone): stay
      // SILENT and show only the character. Invent no filler (AC-108).
      hideBubble();
      s.withBubble = false;
      s.lastFactAt = now;
      return null;
    }

    function scheduleNextFact() {
      if (s.factTimer) { clearTimeout(s.factTimer); s.factTimer = null; }
      if (s.dismissed || isQuiet()) { return; }
      var due = s.lastFactAt + MIN_FACT_INTERVAL_MS;
      var delay = Math.max(0, due - Date.now());
      s.factTimer = setTimeout(function () {
        s.factTimer = null;
        if (!s.dismissed && !isQuiet()) { renderFact(Date.now()); place(); }
        scheduleNextFact();
      }, delay);
    }

    /* Manual advance: shown immediately and RE-ARMS the cadence, so the floor
       restarts from the manually requested fact. */
    function advance() {
      if (s.dismissed || isQuiet()) { return; }
      renderFact(Date.now());
      place();
      scheduleNextFact();
    }

    function showIntro() {
      s.introShown = true;
      writeJSON(sessionStore, INTRO_KEY, { seen: true });
      bubble.textContent = QUIET_HINT + " " + FACT_SOURCES_NOTE;
      bubble.hidden = false;
      place();
      if (!s.withBubble) { hideBubble(); }
    }

    function dismiss() {
      s.dismissed = true;
      if (s.factTimer) { clearTimeout(s.factTimer); s.factTimer = null; }
      if (s.moveTimer) { clearInterval(s.moveTimer); s.moveTimer = null; }
      if (s.quietTimer) { clearTimeout(s.quietTimer); s.quietTimer = null; }
      bubble.hidden = true;
      root.hidden = true;
      writeJSON(sessionStore, DISMISS_KEY, { dismissed: true });
    }

    btn.addEventListener("click", advance);
    btn.addEventListener("keydown", function (e) {
      var step = 24;
      if (e.key === "ArrowLeft") { moveTo(s.x - step, s.y); e.preventDefault(); }
      else if (e.key === "ArrowRight") { moveTo(s.x + step, s.y); e.preventDefault(); }
      else if (e.key === "ArrowUp") { moveTo(s.x, s.y - step); e.preventDefault(); }
      else if (e.key === "ArrowDown") { moveTo(s.x, s.y + step); e.preventDefault(); }
      else if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
        e.preventDefault();
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { dismiss(); }
    });
    window.addEventListener("resize", function () { place(); });

    var api = {
      root: root, bubble: bubble, btn: btn,
      MIN_FACT_INTERVAL_MS: MIN_FACT_INTERVAL_MS,
      FIRST_FACT_DELAY_MS: FIRST_FACT_DELAY_MS,
      THROW_QUIET_MS: THROW_QUIET_MS,
      THROW_VELOCITY: THROW_VELOCITY,
      reducedMotion: s.noMotion,
      page: s.page,
      setPools: function (p) {
        s.pools = p || {};
        var longest = "";
        var pool = s.pools[s.page] || [];
        for (var i = 0; i < pool.length; i++) {
          var text = compose(pool[i].fact || "").trim();
          if (text.length > longest.length) { longest = text; }
        }
        s.longestText = longest;
      },
      poolSize: function () { return (s.pools[s.page] || []).length; },
      longestText: function () { return s.longestText; },
      __dbg: function () { return { col: readingColumn(), anchor: safeAnchor(),
        vp: viewport(), sz: size(), nContent: contentRects(true).length }; },
      __contentRects: function () { return contentRects(true); },
      __fit: function (t) {
        bubble.textContent = t; bubble.hidden = false;
        var a = safeAnchor();
        bubble.hidden = true;
        return { fits: !!(a && a.withBubble), sz: size() };
      },
      factCount: function () { return s.factCount; },
      shownFacts: function () { return s.shownFacts.slice(); },
      advance: advance,
      dismiss: dismiss,
      isDismissed: function () { return s.dismissed; },
      moveTimerActive: function () { return !!s.moveTimer; },
      lastFactAt: function () { return s.lastFactAt; },
      nextDueAt: function () { return s.lastFactAt + MIN_FACT_INTERVAL_MS; },
      place: place,
      placeSafely: placeSafely,
      current: function () { return { x: s.x, y: s.y }; },
      hasSeen: function (t) { return !!s.seen[hash(t)]; },
      seenCount: function () { return Object.keys(s.seen).length; },
      bubbleVisible: function () { return !bubble.hidden; },
      // Drag / throw hooks. The real pointer handlers above are the shipped
      // path; these let the harness drive the same code deterministically.
      beginDrag: function (x, y) {
        s.dragging = true;
        s.dragStart = { x: s.x, y: s.y, px: x, py: y };
        s.lastPointer = { x: x, y: y, t: Date.now() };
        s.lastPointerAt = Date.now();
      },
      dragMove: function (x, y) {
        if (!s.dragging) { return; }
        moveTo(s.dragStart.x + (x - s.dragStart.px),
               s.dragStart.y + (y - s.dragStart.py));
        s.lastPointer = { x: x, y: y, t: Date.now() };
      },
      endDrag: function (vx, vy) { endDrag(vx || 0, vy || 0); },
      isDragging: function () { return s.dragging; },
      throwBot: function (vx, vy) { throwBot(vx || 0, vy || 0); },
      throwCount: function () { return s.throwCount; },
      isReturning: function () { return s.returning; },
      isQuiet: isQuiet,
      quietUntil: function () { return s.quietUntil; },
      // Test-only: run the quiet-period resumption without waiting 5 minutes.
      resumeFromQuiet: resumeFromQuiet,
      introShown: function () { return s.introShown; },
      introSeenInSession: function () { return !!readJSON(sessionStore, INTRO_KEY).seen; },
      // Clock-injected cadence probe: shows a fact at an explicit `now`, but
      // ONLY if the floor has elapsed since the last one. Returns the gap so a
      // test can prove the floor holds without waiting in real time.
      tick: function (now) {
        var gap = s.lastFactAt ? (now - s.lastFactAt) : null;
        if (gap !== null && gap < MIN_FACT_INTERVAL_MS) {
          return { fired: false, gap: gap };
        }
        renderFact(now);
        return { fired: true, gap: gap };
      },
      // Test-only: seed the clock so the cadence can be probed without waiting.
      setLastFactAt: function (t) { s.lastFactAt = t; },
      resetSeen: function () { s.seen = {}; writeJSON(sessionStore, SEEN_KEY, {}); },
      // Render-time composition of a fact template (used by the frozen-clock
      // test to prove the experience figure comes from experience.js).
      composeFact: function (t, now) { return compose(t, now); },
      start: function () {
        if (s.dismissed) { root.hidden = true; return; }
        // A page whose pool is EMPTY stays completely silent: no character, no
        // introduction, nothing invented (AC-108).
        if (this.poolSize() === 0) { root.hidden = true; return; }
        place();
        // Introduce exactly ONCE per session (AC-138 / INV-62).
        if (!readJSON(sessionStore, INTRO_KEY).seen) {
          setTimeout(function () { if (!s.dismissed && !s.introShown) { showIntro(); } },
                     INTRO_DELAY_MS);
        }
        s.lastFactAt = 0;
        s.factTimer = setTimeout(function () {
          s.factTimer = null;
          if (!s.dismissed) { renderFact(Date.now()); place(); }
          scheduleNextFact();
        }, FIRST_FACT_DELAY_MS);
        if (!s.noMotion) {
          s.moveTimer = setInterval(function () { place(); }, MOVE_EVERY_MS);
        }
      }
    };
    return api;
  }

  function start() {
    loadPools().then(function (pools) {
      if (document.getElementById("guide-bot")) { return; }
      var bot = build();
      window.__guideBot = bot;
      bot.setPools(pools);
      bot.start();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
