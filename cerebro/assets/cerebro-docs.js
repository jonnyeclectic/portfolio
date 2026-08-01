/* Cerebro docs — progressive enhancement: scroll reveals, active-nav marker,
   and Mermaid initialized with the Aurora palette. Classic (deferred) script;
   loads after the Mermaid UMD bundle so `window.mermaid` is available. The page
   is fully readable if this never runs. */
(function () {
  "use strict";

  /* ---- active nav marker (match current file to a nav link) ---- */
  try {
    var here = location.pathname.split("/").pop() || "index.html";
    document.querySelectorAll(".nav ul a").forEach(function (a) {
      var href = (a.getAttribute("href") || "").split("/").pop();
      if (href === here) a.classList.add("here");
    });
  } catch (e) { /* non-fatal */ }

  /* ---- scroll reveal ---- */
  var reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && reveals.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.06 });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add("in"); });
  }

  /* ---- Mermaid, themed to Aurora ---- */
  if (window.mermaid) {
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      themeVariables: {
        darkMode: true,
        background: "transparent",
        primaryColor: "#141830",
        primaryBorderColor: "#40cbe3",
        primaryTextColor: "#d6d9e3",
        secondaryColor: "#1b1533",
        secondaryBorderColor: "#cc9eff",
        secondaryTextColor: "#d6d9e3",
        tertiaryColor: "#241428",
        tertiaryBorderColor: "#f58fd7",
        tertiaryTextColor: "#f6d9ee",
        lineColor: "#8b93c4",
        textColor: "#d6d9e3",
        mainBkg: "#141830",
        nodeBorder: "#40cbe3",
        clusterBkg: "#0f121d",
        clusterBorder: "#3a4168",
        edgeLabelBackground: "#0f121d",
        titleColor: "#d6d9e3",
        /* sequence diagram */
        actorBkg: "#141830",
        actorBorder: "#40cbe3",
        actorTextColor: "#d6d9e3",
        actorLineColor: "#4a5178",
        signalColor: "#aab1d6",
        signalTextColor: "#cdd3ea",
        labelBoxBkgColor: "#171a33",
        labelBoxBorderColor: "#cc9eff",
        labelTextColor: "#d6d9e3",
        loopTextColor: "#cdd3ea",
        activationBkgColor: "#243056",
        activationBorderColor: "#40cbe3",
        sequenceNumberColor: "#07080f",
        noteBkgColor: "#241428",
        noteBorderColor: "#f58fd7",
        noteTextColor: "#f6d9ee",
        /* state diagram */
        labelColor: "#d6d9e3",
        /* pie/other */
        pie1: "#40cbe3", pie2: "#cc9eff", pie3: "#f58fd7", pie4: "#38bdf8"
      },
      flowchart: { curve: "basis", htmlLabels: true, useMaxWidth: true, padding: 14 },
      sequence: { useMaxWidth: true, mirrorActors: false, showSequenceNumbers: true, wrap: true },
      state: { useMaxWidth: true }
    });
    var run = function () {
      try { window.mermaid.run({ querySelector: ".mermaid" }); }
      catch (e) { /* leave source text visible on failure */ }
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", run);
    } else { run(); }
  }
})();
