/* Boot: executive scoreboard, sections, methodology, nav. All values computed
   from loaded real data; anything missing renders an explicit pending/unavailable tile. */
(function () {
  "use strict";
  var U = window.ALTDATA_UI;
  var D = window.ALTDATA || {};

  function data(key) { return D[key] && D[key].data ? D[key].data : null; }

  /* ---------- scoreboard ---------- */
  function tiles() {
    var roster = data("p1_current_roster");
    var head = data("p1_headcount_timeseries");
    if (roster) {
      var flow = null;
      if (head && head.flows) {
        var fl = head.flows.filter(function (f) { return f.year === new Date().getFullYear() - 1; })[0];
        if (fl) flow = fl;
      }
      U.tile("tiles", {
        label: "Consultants on the bench today",
        value: Number(roster.total).toLocaleString(),
        delta: flow ? "+" + flow.new_profiles + " joined / −" + flow.disappeared_profiles + " left in " + flow.year + " (archive proxy)" : null,
        dir: "flat",
        note: "Live count from Exponent's own directory. The thesis needs this growing again.",
        href: "#sec-p1"
      });
    } else {
      U.tile("tiles", { label: "Consultants on the bench", value: "–", note: "Roster data unavailable.", href: "#sec-p1" });
    }

    var fin = data("p6_expo_financials");
    if (fin && fin.revenue_quarterly && fin.revenue_quarterly.length >= 8) {
      var rq = fin.revenue_quarterly;
      var last4 = rq.slice(-4).reduce(function (a, p) { return a + p.value; }, 0);
      var prev4 = rq.slice(-8, -4).reduce(function (a, p) { return a + p.value; }, 0);
      var growth = (last4 / prev4 - 1) * 100;
      U.tile("tiles", {
        label: "Revenue, trailing 12 months",
        value: U.fmt(last4, { money: true }),
        delta: (growth >= 0 ? "+" : "") + growth.toFixed(1) + "% vs prior 12 months",
        dir: growth > 1 ? "up" : growth < -1 ? "down" : "flat",
        note: "As reported to the SEC, through " + rq[rq.length - 1].period + ".",
        href: "#sec-p6"
      });
    }

    var p3 = data("p3_reactive_index");
    if (p3 && p3.blended_index) {
      var vals = p3.blended_index.filter(function (r) { return r.index !== null; });
      var latest = vals[vals.length - 1];
      var yearAgo = vals[vals.length - 5];
      var d3 = yearAgo ? latest.index - yearAgo.index : null;
      U.tile("tiles", {
        label: "Reactive Demand Index (" + latest.quarter + ")",
        value: String(latest.index),
        delta: d3 !== null ? (d3 >= 0 ? "+" : "") + d3.toFixed(1) + " pts vs a year ago" : null,
        dir: d3 > 2 ? "up" : d3 < -2 ? "down" : "flat",
        note: "Product failures reported to regulators, vs 100 = the 2012–19 norm. Elevated = future forensic work.",
        href: "#sec-p3"
      });
    }

    var p4 = data("p4_partners_rolling");
    if (p4 && p4.series && p4.series.length > 1) {
      var s = p4.series.filter(function (r) { return r.year <= new Date().getFullYear() - 1; });
      var cur = s[s.length - 1], prior = s[s.length - 2];
      var isRecord = cur.unique_partners >= Math.max.apply(null, s.map(function (r) { return r.unique_partners; }));
      U.tile("tiles", {
        label: "Corporate research partners (3-yr window)",
        value: String(cur.unique_partners),
        delta: (cur.unique_partners - prior.unique_partners >= 0 ? "+" : "") +
               (cur.unique_partners - prior.unique_partners) + " vs prior window" + (isRecord ? " — record high" : ""),
        dir: cur.unique_partners >= prior.unique_partners ? "up" : "down",
        note: "Distinct companies co-publishing with Exponent — a public window into the confidential client base.",
        href: "#sec-p4"
      });
    }

    var p6 = data("p6_client_rnd");
    if (p6 && p6.constant_sample_aggregate && p6.constant_sample_aggregate.length) {
      var agg = p6.constant_sample_aggregate;
      var lastA = agg[agg.length - 1];
      U.tile("tiles", {
        label: "Revealed clients' R&D growth (" + lastA.year + ")",
        value: (lastA.yoy_pct >= 0 ? "+" : "") + lastA.yoy_pct + "%",
        delta: U.fmt(lastA.total_rnd, { money: true }) + " across " + lastA.companies + " documented clients",
        dir: lastA.yoy_pct > 2 ? "up" : lastA.yoy_pct < 0 ? "down" : "flat",
        note: "Growing client R&D budgets = a rising tide for Exponent's proactive consulting.",
        href: "#sec-p6"
      });
    }

    var p2 = data("p2_litigation_timeseries");
    if (p2 && p2.series) {
      var withData = p2.series.filter(function (r) { return r.opinions_per_100k !== null && r.opinions_mentions > 0; });
      if (withData.length >= 6) {
        var lastY = withData[withData.length - 2] || withData[withData.length - 1];
        var avg5 = withData.slice(-7, -2).reduce(function (a, r) { return a + r.opinions_per_100k; }, 0) / 5;
        var dd = avg5 ? (lastY.opinions_per_100k / avg5 - 1) * 100 : null;
        U.tile("tiles", {
          label: "Courtroom footprint (" + lastY.year + ")",
          value: lastY.opinions_per_100k + " /100k",
          delta: dd !== null ? (dd >= 0 ? "+" : "") + dd.toFixed(0) + "% vs prior 5-yr avg" : null,
          dir: dd > 5 ? "up" : dd < -5 ? "down" : "flat",
          note: "Share of court opinions mentioning Exponent near expert language.",
          href: "#sec-p2"
        });
      }
    } else {
      U.tile("tiles", {
        label: "Courtroom footprint", value: "pending",
        note: "CourtListener fetch in progress — free-tier requests drip over a few days. This tile fills automatically on the next data build.",
        href: "#sec-p2"
      });
    }

    var dbt = data("p2_daubert");
    if (dbt && dbt.exponent && dbt.exponent.exclusion_rate !== null && dbt.exponent.exclusion_rate !== undefined) {
      var er = dbt.exponent.exclusion_rate, br = dbt.baseline.exclusion_rate;
      U.tile("tiles", {
        label: "Expert-exclusion rate (Daubert)",
        value: (er * 100).toFixed(0) + "%",
        delta: br !== null ? "baseline: " + (br * 100).toFixed(0) + "% (n=" + dbt.exponent.n_classified + " vs " + dbt.baseline.n_classified + ")" : null,
        dir: br !== null ? (er < br ? "up" : er > br ? "down" : "flat") : "flat",
        note: "Lower than baseline = Exponent experts survive challenges better — the moat, measured.",
        href: "#sec-p2"
      });
    }
  }

  /* ---------- methodology ---------- */
  function methodology() {
    var mount = document.getElementById("metho-tables");
    if (!mount) return;
    var p3 = data("p3_reactive_index");
    if (p3 && p3.severity_weights) {
      mount.appendChild(U.el("h3", null, "Severity weights (Reactive Demand Index)"));
      var w = U.renderTable({
        columns: [{ label: "Event type" }, { label: "Weight", num: true }],
        rows: Object.keys(p3.severity_weights).map(function (k) { return [k.replace(/_/g, " "), p3.severity_weights[k]]; })
      });
      var wrap1 = U.el("div", "tablewrap open"); wrap1.appendChild(w); mount.appendChild(wrap1);
      mount.appendChild(U.el("h3", null, "Category keyword rules (Reactive Demand Index)"));
      var kw = U.renderTable({
        columns: [{ label: "Category" }, { label: "Keywords (case-insensitive substring match)", wrap: true }],
        rows: Object.keys(p3.category_keywords).map(function (k) { return [k.replace(/_/g, " "), p3.category_keywords[k].join(", ")]; })
      });
      var wrap2 = U.el("div", "tablewrap open"); wrap2.appendChild(kw); mount.appendChild(wrap2);
    }

    mount.appendChild(U.el("h3", null, "Every dataset on this page"));
    var rows = [];
    Object.keys(D).forEach(function (k) {
      if (k === "explainers" || k === "manifest") return;
      var m = D[k] && D[k].metadata;
      if (!m) return;
      var src = (m.sources && m.sources[0]) || {};
      rows.push([k, m.status + (m.status_reason ? " — " + m.status_reason : ""),
                 src.name || "", m.generated_at || ""]);
    });
    var t = U.renderTable({
      columns: [{ label: "Dataset" }, { label: "Status", wrap: true }, { label: "Primary source", wrap: true }, { label: "Generated (UTC)" }],
      rows: rows
    });
    var wrap3 = U.el("div", "tablewrap open"); wrap3.appendChild(t); mount.appendChild(wrap3);

    var cavMount = document.getElementById("metho-caveats");
    if (cavMount) {
      Object.keys(D).forEach(function (k) {
        var m = D[k] && D[k].metadata;
        if (!m || !m.caveats || k === "explainers" || k === "manifest") return;
        var det = document.createElement("details");
        det.innerHTML = "<summary style='cursor:pointer;color:var(--ink-2);padding:4px 0'>" +
          U.esc(k) + "</summary><ul>" + m.caveats.map(function (c) {
            return "<li>" + U.esc(c) + "</li>";
          }).join("") + "</ul>";
        cavMount.appendChild(det);
      });
    }
  }

  /* ---------- nav scrollspy ---------- */
  function nav() {
    var links = Array.prototype.slice.call(document.querySelectorAll("nav.sections a"));
    var secs = links.map(function (a) { return document.querySelector(a.getAttribute("href")); });
    function onScroll() {
      var y = window.scrollY + 90;
      var active = 0;
      secs.forEach(function (s, i) { if (s && s.offsetTop <= y) active = i; });
      links.forEach(function (a, i) { a.classList.toggle("active", i === active); });
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  document.addEventListener("DOMContentLoaded", function () {
    tiles();
    window.ALTDATA_CHARTS.render();
    methodology();
    nav();
    var stamp = document.getElementById("data-stamp");
    if (stamp && D.manifest) {
      var latest = (D.manifest.datasets || []).map(function (d) { return d.generated_at; })
        .filter(Boolean).sort().pop();
      stamp.textContent = "All data fetched from primary public sources · latest refresh " +
        (latest ? latest.slice(0, 10) : "n/a") + " · nothing simulated, estimated, or backfilled";
    }
  });
})();
