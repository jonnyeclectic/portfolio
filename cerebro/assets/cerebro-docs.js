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
        primaryBorderColor: "#22d3ee",
        primaryTextColor: "#e9ebf5",
        secondaryColor: "#1b1533",
        secondaryBorderColor: "#a855f7",
        secondaryTextColor: "#e9ebf5",
        tertiaryColor: "#241428",
        tertiaryBorderColor: "#f472d0",
        tertiaryTextColor: "#f6d9ee",
        lineColor: "#8b93c4",
        textColor: "#e9ebf5",
        mainBkg: "#141830",
        nodeBorder: "#22d3ee",
        clusterBkg: "rgba(255,255,255,.03)",
        clusterBorder: "#3a4168",
        edgeLabelBackground: "#0f1120",
        titleColor: "#e9ebf5",
        /* sequence diagram */
        actorBkg: "#141830",
        actorBorder: "#22d3ee",
        actorTextColor: "#e9ebf5",
        actorLineColor: "#4a5178",
        signalColor: "#aab1d6",
        signalTextColor: "#cdd3ea",
        labelBoxBkgColor: "#171a33",
        labelBoxBorderColor: "#a855f7",
        labelTextColor: "#e9ebf5",
        loopTextColor: "#cdd3ea",
        activationBkgColor: "#243056",
        activationBorderColor: "#22d3ee",
        sequenceNumberColor: "#07080f",
        noteBkgColor: "#241428",
        noteBorderColor: "#f472d0",
        noteTextColor: "#f6d9ee",
        /* state diagram */
        labelColor: "#e9ebf5",
        /* pie/other */
        pie1: "#22d3ee", pie2: "#a855f7", pie3: "#f472d0", pie4: "#38bdf8"
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
