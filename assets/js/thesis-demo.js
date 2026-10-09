/* thesis-demo.js — interactive, fully offline stage reveal for the VLM demo.
   Reads window.THESIS_DEMO_DATA (shipped statically). Makes NO network request. */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", fn);
    } else {
      fn();
    }
  }

  ready(function () {
    var data = window.THESIS_DEMO_DATA;
    if (!data) { return; }
    var byId = {};
    data.scenarios.forEach(function (s) { byId[s.id] = s; });

    var buttons = Array.prototype.slice.call(
      document.querySelectorAll(".demo-scenario"));
    var stages = {
      telematics: document.querySelector('.demo-stage[data-stage="telematics"]'),
      vlm: document.querySelector('.demo-stage[data-stage="vlm"]'),
      llm: document.querySelector('.demo-stage[data-stage="llm"]'),
      score: document.querySelector('.demo-stage[data-stage="score"]')
    };
    var revealed = 0;
    var timers = [];

    function clearTimers() {
      timers.forEach(function (t) { clearTimeout(t); });
      timers = [];
    }

    function setStage(el, bodyHtml) {
      if (!el) { return; }
      var body = el.querySelector(".demo-stage-body");
      body.classList.remove("demo-stage-placeholder");
      body.innerHTML = bodyHtml;
      el.classList.add("is-revealed");
    }

    function telematicsHtml(s) {
      var rows = Object.keys(s.telematics).map(function (k) {
        return "<li><strong>" + k + ":</strong> " + s.telematics[k] + "</li>";
      }).join("");
      return "<ul class=\"role-bullets\">" + rows + "</ul>";
    }

    function disableStages() {
      Object.keys(stages).forEach(function (k) {
        var el = stages[k];
        if (!el) { return; }
        el.classList.remove("is-revealed");
        var body = el.querySelector(".demo-stage-body");
        body.classList.add("demo-stage-placeholder");
        body.textContent = "Select a scenario to reveal this stage.";
      });
    }

    /* The pipeline lives ABOVE the scenario picker, so selecting a scenario
       otherwise reveals four stages off-screen and the visitor sees nothing
       happen. Bring the first stage into view once it has content. */
    function scrollToPipeline() {
      var first = stages.telematics;
      if (!first) { return; }
      var reduce = window.matchMedia
        && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      first.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    }

    function reveal(s) {
      clearTimers();
      disableStages();
      revealed = 0;
      timers.push(setTimeout(function () {
        setStage(stages.telematics, telematicsHtml(s)); revealed = 1;
        scrollToPipeline();
      }, 0));
      timers.push(setTimeout(function () {
        setStage(stages.vlm, s.vlm); revealed = 2;
      }, 550));
      timers.push(setTimeout(function () {
        setStage(stages.llm, s.llm); revealed = 3;
      }, 1100));
      timers.push(setTimeout(function () {
        var delta = s.score_vlm - s.score_base;
        var sign = delta >= 0 ? "+" : "\u2212";
        setStage(stages.score,
          '<span class="demo-score">Telematics only ' + s.score_base +
          " \u2192 with the camera " + s.score_vlm + "</span> (" + sign +
          Math.abs(delta) + " points) &mdash; " + s.band +
          " risk band (illustrative). " + s.delta_note);
        revealed = 4;
      }, 1650));
    }

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        buttons.forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
        btn.setAttribute("aria-pressed", "true");
        var s = byId[btn.getAttribute("data-scenario")];
        if (s) { reveal(s); }
      });
    });

    /* Expose a tiny probe for the deterministic harness. */
    window.__thesisDemo = {
      isRevealed: function () { return revealed === 4; },
      revealedCount: function () { return revealed; },
      select: function (id) {
        var b = document.querySelector('.demo-scenario[data-scenario="' + id + '"]');
        if (b) { b.click(); }
      }
    };
  });
})();
