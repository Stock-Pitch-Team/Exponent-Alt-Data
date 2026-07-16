/* Boot: executive scoreboard, sections, methodology, nav. All values computed
   from loaded real data; anything missing renders an explicit pending/unavailable tile. */
(function () {
  "use strict";
  var U = window.ALTDATA_UI;
  var D = window.ALTDATA || {};

  function data(key) { return D[key] && D[key].data ? D[key].data : null; }

  /* ---------- scoreboard ---------- */
  function tiles() {
    var util = data("p7_utilization");
    if (util && util.series) {
      var us = util.series.filter(function (r) { return r.utilization; });
      if (us.length >= 5) {
        var cur = us[us.length - 1];
        var yearAgo = us[us.length - 5];
        var du = yearAgo ? cur.utilization - yearAgo.utilization : null;
        var hc = null;
        for (var i = us.length - 1; i >= 0 && !hc; i--) {
          if (us[i].headcount_growth_pct) hc = us[i];
        }
        U.tile("tiles", {
          label: "Utilization, company-stated (" + cur.quarter + ")",
          value: cur.utilization + "%",
          delta: (du !== null ? (du >= 0 ? "+" : "") + du + " pts vs year ago" : "") +
                 (hc ? " · headcount +" + hc.headcount_growth_pct + "% (" + hc.quarter + ")" : ""),
          dir: cur.utilization >= 76 ? "up" : cur.utilization <= 73 ? "down" : "flat",
          note: "Straight from SEC filings. Thesis triggers: 76%+ with headcount growth = bull confirmed; ~73% ceiling = bear. Currently in the bull zone.",
          href: "#sec-p1"
        });
      }
    }

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

    /* The bear case deserves a tile of its own, not a footnote. */
    var ai = data("p11_ai_exposure");
    if (ai && ai.years && ai.years.length >= 2) {
      var latest = ai.years[ai.years.length - 1];
      var prevYr = ai.years[ai.years.length - 2];
      var anch = ai.testimony_anchor;
      U.tile("tiles", {
        label: "AI-substitution risk (FY" + latest.fiscal_year + " 10-K)",
        value: latest.has_ai_demand_risk_factor ? "Newly flagged" : "Not flagged",
        delta: latest.ai_mentions + " AI mentions vs " + prevYr.ai_mentions + " a year earlier",
        /* management newly disclosing a demand risk cuts against the thesis */
        dir: latest.has_ai_demand_risk_factor && !prevYr.has_ai_demand_risk_factor ? "down" : "flat",
        note: "Exponent added a risk factor saying AI may reduce demand — new this year, and a real change to the story. Its own scoping puts the exposure on 'more standardized' offerings" +
              (anch ? "; testimony work needs a human under Rule 702." : "."),
        href: "#sec-p11"
      });
    }

    var p2 = data("p2_litigation_timeseries");
    if (p2 && p2.series) {
      // federal case files are the meaningful volume series; the newest ~2 years
      // read low from archive purchase lag, so anchor on year-3
      var recap = p2.series.filter(function (r) { return r.recap_per_100k !== null && r.recap_mentions > 0; });
      if (recap.length >= 7) {
        // last ~2-3 years read low from archive purchase lag; anchor 3 years back
        var anchor = recap[recap.length - 4];
        var prior3 = recap.slice(-7, -4);
        var avg3 = prior3.reduce(function (a, r) { return a + r.recap_per_100k; }, 0) / prior3.length;
        var dd = avg3 ? (anchor.recap_per_100k / avg3 - 1) * 100 : null;
        U.tile("tiles", {
          label: "Litigation footprint (" + anchor.year + ", lag-robust)",
          value: anchor.recap_per_100k + " /100k",
          delta: dd !== null ? (dd >= 0 ? "+" : "") + dd.toFixed(0) + "% vs prior 3-yr avg" : null,
          dir: dd > 5 ? "up" : dd < -5 ? "down" : "flat",
          note: "Federal cases naming Exponent near expert language, per 100k archived cases. Peaked 2021-22; newer years read low from archive lag. Stable franchise - not a growth signal.",
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
