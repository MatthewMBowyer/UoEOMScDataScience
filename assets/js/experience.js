/* ==========================================================================
   experience.js — the single render-time experience computation.

   The owner's requirement: never hardcode an experience figure. Store the
   factual career start (Jan 2019, Smith Yong and Associates) and compute whole
   years of experience AT RENDER TIME, so the site reads a seven-then-eight
   figure as calendar years advance, with no edit.

   This module is loaded by every delivered page (and by the ambient bot) and
   is the ONLY place an experience figure is derived. It is intentionally
   dependency-free and works both in the browser and under Node so the frozen-
   clock unit tests exercise the SAME code the site uses.

   Facts (from inputs/CV_EXTRACTED_TEXT.md, the authoritative CV):
     - Career start: Jan 2019 (Data Analyst, Smith Yong and Associates).
     - Current role start: Jun 2024 (Manager: Data Analytics & Global Reporting).
     - MSc: Jan 2024 - Jun 2026, University of Essex Online, Merit.
   ========================================================================== */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.Experience = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  /* --- Factual dates. Stored as facts; the FIGURE is always computed. ------- */
  var CAREER_START = { year: 2019, month: 1 }; // Jan 2019 (Smith Yong)
  var CURRENT_ROLE_START = { year: 2024, month: 6 }; // Jun 2024 (Cartrack)
  var MSC_START = { year: 2024, month: 1 };
  var MSC_END = { year: 2026, month: 6 }; // Jun 2026 (completed, Merit)
  var BSC_START = { year: 2020, month: 3 };
  var BSC_END = { year: 2023, month: 7 };

  var MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /* Whole months elapsed between two {year, month} points. */
  function monthsBetween(from, to) {
    return (to.year - from.year) * 12 + (to.month - from.month);
  }

  function coerceDate(now) {
    if (now instanceof Date) return now;
    if (typeof now === "string" || typeof now === "number") return new Date(now);
    return new Date();
  }

  /* Whole completed years of experience at `now`, computed from CAREER_START. */
  function yearsOfExperience(now) {
    var d = coerceDate(now);
    var elapsed = monthsBetween(CAREER_START,
      { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1 });
    if (elapsed < 0) elapsed = 0;
    return Math.floor(elapsed / 12);
  }

  /* "N+ years" — the phrasing the site and the ambient bot render. Always computed. */
  function experienceLabel(now) {
    return yearsOfExperience(now) + "+ years";
  }

  /* "since Jun 2024" — tenure duration of the current role, computed, so the
     wording stays correct without an edit as time passes. */
  function currentRoleTenure(now) {
    var d = coerceDate(now);
    var elapsed = monthsBetween(CURRENT_ROLE_START,
      { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1 });
    if (elapsed < 0) elapsed = 0;
    var years = Math.floor(elapsed / 12);
    var months = elapsed % 12;
    var parts = [];
    if (years > 0) parts.push(years + (years === 1 ? " year" : " years"));
    if (months > 0) parts.push(months + (months === 1 ? " month" : " months"));
    if (parts.length === 0) parts.push("less than a month");
    return parts.join(" ");
  }

  function monthLabel(p) {
    return MONTH_NAMES[p.month - 1] + " " + p.year;
  }

  /* "completed 2026" — the MSc completion phrasing, computed from MSC_END. */
  function mscCompletion(now) {
    var d = coerceDate(now);
    if (d.getUTCFullYear() > MSC_END.year ||
        (d.getUTCFullYear() === MSC_END.year && d.getUTCMonth() + 1 >= MSC_END.month)) {
      return { completed: true, year: MSC_END.year,
               label: "completed " + MSC_END.year };
    }
    return { completed: false, year: MSC_END.year,
             label: "completing " + MSC_END.year };
  }

  /* Fill every element carrying a data-experience attribute with the computed,
     current figure. Called on DOMContentLoaded by every page. */
  function applyToDocument(doc, now) {
    doc = doc || (typeof document !== "undefined" ? document : null);
    if (!doc) return;
    var d = coerceDate(now);
    doc.querySelectorAll("[data-experience]").forEach(function (el) {
      var kind = el.getAttribute("data-experience");
      if (kind === "label") {
        el.textContent = experienceLabel(d);
      } else if (kind === "years") {
        el.textContent = String(yearsOfExperience(d));
      } else if (kind === "tenure") {
        el.textContent = "since " + monthLabel(CURRENT_ROLE_START);
      } else if (kind === "msc") {
        el.textContent = mscCompletion(d).label;
      }
    });
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", function () { applyToDocument(); });
    } else {
      applyToDocument();
    }
  }

  return {
    CAREER_START: CAREER_START,
    CURRENT_ROLE_START: CURRENT_ROLE_START,
    MSC_START: MSC_START,
    MSC_END: MSC_END,
    BSC_START: BSC_START,
    BSC_END: BSC_END,
    monthsBetween: monthsBetween,
    yearsOfExperience: yearsOfExperience,
    experienceLabel: experienceLabel,
    currentRoleTenure: currentRoleTenure,
    mscCompletion: mscCompletion,
    monthLabel: monthLabel,
    applyToDocument: applyToDocument
  };
});
