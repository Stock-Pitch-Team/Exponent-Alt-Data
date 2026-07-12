/* Chart builders. Every card: real data in, chart + explainer + table + provenance out. */
window.ALTDATA_CHARTS = (function () {
  "use strict";
  var U = window.ALTDATA_UI;
  var THIS_YEAR = new Date().getFullYear();

  /* current calendar/fiscal year is in progress: star its axis label */
  function starYear(y) {
    return String(y) + (Number(String(y).replace(/\D/g, "").slice(-4)) >= THIS_YEAR ? "*" : "");
  }

  /* ================= P1 — headcount ================= */
  function p1Headcount() {
    U.card({
      mount: "mount-p1-headcount", datasetKey: "p1_headcount_timeseries",
      chartId: "p1_headcount_timeseries",
      title: "Consultant headcount, reconstructed from 20 years of web archives",
      sub: "Distinct consultant profile pages alive on exponent.com per year (Wayback Machine). Proxy for workforce size — read the trend, not the level.",
      build: function (elm, d) {
        var rows = d.series.filter(function (r) { return r.year >= 2016; });
        var years = rows.map(function (r) { return r.year; });
        return {
          option: {
            legend: { data: ["All profiles (deduplicated)", "Old site era", "Current site era"] },
            xAxis: { type: "category", data: years },
            yAxis: { type: "value", name: "profiles", nameTextStyle: { color: U.cssVar("--muted") } },
            series: [
              { name: "All profiles (deduplicated)", type: "line", smooth: false,
                lineStyle: { width: 2.5 }, symbolSize: 8, data: rows.map(function (r) { return r.active_profiles; }) },
              { name: "Old site era", type: "line", lineStyle: { width: 1.5 }, symbolSize: 6,
                data: rows.map(function (r) { return r.professionals_active || null; }) },
              { name: "Current site era", type: "line", lineStyle: { width: 1.5 }, symbolSize: 6,
                data: rows.map(function (r) { return r.people_active || null; }) }
            ]
          },
          table: {
            columns: [{ label: "Year" }, { label: "All profiles", num: true },
                      { label: "Old-era URLs", num: true }, { label: "Current-era URLs", num: true },
                      { label: "New profiles", num: true }, { label: "Disappeared", num: true }],
            rows: d.series.map(function (r) {
              var f = (d.flows || []).filter(function (x) { return x.year === r.year; })[0] || {};
              return [r.year, r.active_profiles, r.professionals_active, r.people_active,
                      f.new_profiles, f.disappeared_profiles];
            })
          }
        };
      }
    });
  }

  function p1Roster() {
    U.card({
      mount: "mount-p1-roster", datasetKey: "p1_current_roster",
      chartId: "p1_current_roster",
      title: "The bench today: 996 consultants by practice area",
      sub: "Live census from Exponent's own directory. Battery/thermal, chemical-regulation and electronics practices are the thesis-relevant muscle.",
      tall: true,
      build: function (elm, d) {
        var top = d.by_practice.filter(function (r) { return r.practice !== "Unlisted"; }).slice(0, 14).reverse();
        return {
          option: {
            grid: { left: 250, right: 60, top: 10, bottom: 30 },
            tooltip: { trigger: "item" },
            xAxis: { type: "value" },
            yAxis: { type: "category", data: top.map(function (r) { return r.practice; }),
                     axisLabel: { color: U.cssVar("--ink-2"), fontSize: 12.5, width: 235, overflow: "truncate" } },
            series: [{
              type: "bar", barMaxWidth: 18, data: top.map(function (r) { return r.count; }),
              itemStyle: { borderRadius: [0, 4, 4, 0] },
              label: { show: true, position: "right", color: U.cssVar("--ink-2"), fontSize: 12 }
            }]
          },
          table: {
            columns: [{ label: "Practice area" }, { label: "Consultants", num: true }],
            rows: d.by_practice.map(function (r) { return [r.practice, r.count]; })
          }
        };
      }
    });
  }

  function p7Utilization() {
    U.card({
      mount: "mount-p7-utilization", datasetKey: "p7_utilization", chartId: "p7_utilization",
      title: "Utilization: the thesis variable, from Exponent's own filings",
      sub: "Company-stated quarterly utilization from SEC-filed earnings releases and 10-Qs. Dashed lines mark the thesis triggers: ~73% = bear ceiling, 76%+ = bull confirmation. Chart shows 2016-present; ~20 years in the table.",
      build: function (elm, d) {
        var rows = d.series.filter(function (r) { return r.quarter >= "2016" && r.utilization; });
        return {
          option: {
            tooltip: {
              formatter: function (ps) {
                var r = rows[ps[0].dataIndex];
                return r.quarter + "<br>Utilization: <b>" + r.utilization + "%</b>" +
                  (r.headcount_growth_pct ? "<br>Headcount: +" + r.headcount_growth_pct + "% YoY (stated)" : "") +
                  "<br><span style='color:" + U.cssVar("--muted") + "'>" +
                  (r.source_form || "8-K") + " " + (r.accession || "") + "</span>";
              }
            },
            xAxis: { type: "category", data: rows.map(function (r) { return r.quarter; }),
                     axisLabel: { interval: 5 } },
            yAxis: { type: "value", min: 60, max: 82,
                     axisLabel: { formatter: "{value}%" } },
            series: [{
              type: "line", lineStyle: { width: 2.5 }, symbolSize: 7,
              data: rows.map(function (r) { return r.utilization; }),
              markLine: {
                symbol: "none", silent: true,
                lineStyle: { type: "dashed", width: 1 },
                label: { color: U.cssVar("--muted"), fontSize: 11, position: "insideEndTop" },
                data: [
                  { yAxis: 73, label: { formatter: "73% - bear ceiling" },
                    lineStyle: { color: U.cssVar("--s6") } },
                  { yAxis: 76, label: { formatter: "76% - bull zone" },
                    lineStyle: { color: U.cssVar("--s4") } }
                ]
              }
            }]
          },
          table: {
            columns: [{ label: "Quarter" }, { label: "Utilization", num: true },
                      { label: "Year-ago (as stated)", num: true },
                      { label: "Headcount growth (stated)", num: true },
                      { label: "Source filing" }],
            rows: d.series.map(function (r) {
              return [r.quarter, r.utilization != null ? r.utilization + "%" : "",
                      r.utilization_prior_year != null ? r.utilization_prior_year + "%" : "",
                      r.headcount_growth_pct != null ? "+" + r.headcount_growth_pct + "%" : "",
                      (r.source_form || "8-K") + " " + (r.accession || "")];
            })
          }
        };
      }
    });
  }

  function p7RealizedRate() {
    U.card({
      mount: "mount-p7-rate", datasetKey: "p7_realized_rate", chartId: "p7_realized_rate",
      title: "Pricing power, quantified: estimated realized rate per billable hour",
      sub: "Reported revenue ÷ (company-stated FTEs × utilization × available hours). Trend and YoY are the signal; the level depends on the hours convention.",
      build: function (elm, d) {
        var rows = d.series;
        return {
          option: {
            tooltip: {
              formatter: function (ps) {
                var r = rows[ps[0].dataIndex];
                return r.quarter + "<br>Est. rate: <b>$" + r.rate_est.toFixed(0) + "/hr</b>" +
                  (r.rate_yoy_pct != null ? " (" + (r.rate_yoy_pct >= 0 ? "+" : "") + r.rate_yoy_pct + "% YoY)" : "") +
                  "<br>Est. billable hours: " + U.fmt(r.billable_hours_est) +
                  "<br>Utilization " + r.utilization + "% · FTE " + U.fmt(r.fte, { dp: 0 });
              }
            },
            xAxis: { type: "category", data: rows.map(function (r) { return r.quarter; }),
                     axisLabel: { interval: 3 } },
            yAxis: { type: "value", axisLabel: { formatter: "${value}" }, min: 250 },
            series: [{ type: "line", lineStyle: { width: 2.5 }, symbolSize: 7,
                       data: rows.map(function (r) { return r.rate_est; }) }]
          },
          table: {
            columns: [{ label: "Quarter" }, { label: "Est. rate $/hr", num: true },
                      { label: "YoY", num: true }, { label: "Est. billable hours", num: true },
                      { label: "Utilization", num: true }, { label: "FTE", num: true }],
            rows: rows.map(function (r) {
              return [r.quarter, "$" + r.rate_est.toFixed(0),
                      r.rate_yoy_pct != null ? (r.rate_yoy_pct >= 0 ? "+" : "") + r.rate_yoy_pct + "%" : "",
                      r.billable_hours_est.toLocaleString(), r.utilization + "%", r.fte];
            })
          }
        };
      }
    });
  }

  function p9Hiring() {
    U.card({
      mount: "mount-p9-hiring", datasetKey: "p9_hiring", chartId: "p9_hiring",
      title: "Sponsored hiring: H-1B and green-card filings per quarter",
      sub: "Exponent's filings with the US Dept. of Labor — a public, quarterly slice of specialist hiring. * = newest quarters arrive with a reporting lag.",
      build: function (elm, d) {
        var rows = d.series;
        return {
          option: {
            legend: { data: ["H-1B applications (hiring intent)", "Green-card sponsorships (retention)"] },
            xAxis: { type: "category", data: rows.map(function (r, i) {
              return r.quarter + (i >= rows.length - 2 ? "*" : ""); }) },
            yAxis: { type: "value", minInterval: 1 },
            series: [
              { name: "H-1B applications (hiring intent)", type: "bar", stack: "h",
                barMaxWidth: 22, itemStyle: { borderColor: U.cssVar("--surface"), borderWidth: 2 },
                data: rows.map(function (r) { return r.lca; }) },
              { name: "Green-card sponsorships (retention)", type: "bar", stack: "h",
                barMaxWidth: 22, itemStyle: { borderColor: U.cssVar("--surface"), borderWidth: 2,
                                              borderRadius: [4, 4, 0, 0] },
                data: rows.map(function (r) { return r.perm; }) }
            ]
          },
          table: {
            columns: [{ label: "Quarter (filed)" }, { label: "H-1B", num: true },
                      { label: "PERM", num: true }, { label: "Certified", num: true }],
            rows: rows.map(function (r) { return [r.quarter, r.lca, r.perm, r.certified]; })
          }
        };
      }
    });
  }

  function p6Guidance() {
    U.card({
      mount: "mount-p6-guidance", datasetKey: "p6_rnd_guidance", chartId: "p6_rnd_guidance",
      title: "Clients' forward R&D guidance — in their own words",
      sub: "Verbatim forward-looking R&D sentences from the largest revealed clients' recent filings. Read the quotes; the labels are just a sort key.",
      build: function (elm, d) {
        elm.remove();
        return {
          custom: true,
          table: {
            columns: [{ label: "Client" }, { label: "Direction" }, { label: "Filed" },
                      { label: "What they said (verbatim)", wrap: true }],
            rows: (d.signals || []).map(function (s) {
              return [s.name + (s.ticker ? " (" + s.ticker + ")" : ""),
                      s.direction, s.filed, s.sentence];
            })
          }
        };
      }
    });
    var mount = document.getElementById("mount-p6-guidance");
    var wrap = mount && mount.querySelector(".tablewrap");
    if (wrap) wrap.classList.add("open");
  }

  function p10Nowcast() {
    U.card({
      mount: "mount-p10-nowcast", datasetKey: "p10_nowcast", chartId: "p10_nowcast",
      title: "Out-of-sample track record: predicted vs actual utilization change",
      sub: "Every point is a genuine walk-forward prediction made only with earlier data. The model barely edges naive persistence — which is itself the finding: utilization stays where it is.",
      build: function (elm, d) {
        var rows = d.backtest;
        var live = d.live_call;
        return {
          option: {
            legend: { data: ["Actual YoY change", "Model prediction", "Naive (persistence)"] },
            tooltip: { valueFormatter: function (v) { return v == null ? "–" : (v >= 0 ? "+" : "") + v + " pts"; } },
            xAxis: { type: "category", data: rows.map(function (r) { return r.quarter; }),
                     axisLabel: { interval: 5 } },
            yAxis: { type: "value", name: "utilization YoY, pts", nameTextStyle: { color: U.cssVar("--muted") } },
            series: [
              { name: "Actual YoY change", type: "line", lineStyle: { width: 2.5 }, symbolSize: 7,
                data: rows.map(function (r) { return r.actual_yoy; }) },
              { name: "Model prediction", type: "line", lineStyle: { width: 1.8 }, symbolSize: 5,
                color: U.cssVar("--s5"), data: rows.map(function (r) { return r.model_yoy; }) },
              { name: "Naive (persistence)", type: "line", lineStyle: { width: 1.2, opacity: 0.7 },
                symbolSize: 4, color: U.cssVar("--s3"),
                data: rows.map(function (r) { return r.naive_yoy; }) }
            ]
          },
          table: {
            columns: [{ label: "Quarter" }, { label: "Actual", num: true },
                      { label: "Model", num: true }, { label: "Naive", num: true }],
            rows: rows.map(function (r) { return [r.quarter, r.actual_yoy, r.model_yoy, r.naive_yoy]; })
          }
        };
      }
    });
    /* the live-call card */
    var d = (window.ALTDATA.p10_nowcast || {}).data;
    var mount = document.getElementById("mount-p10-call");
    if (mount && d && d.live_call) {
      var c = d.live_call;
      var el = U.el("div", "card");
      el.appendChild(U.el("h3", null, "The live call — " + U.esc(c.target_quarter) + " print"));
      el.appendChild(U.el("p", "sub", "A dated, falsifiable prediction, made " +
        new Date().toISOString().slice(0, 10) + " with the same walk-forward recipe as every backtest point."));
      var big = U.el("div", null,
        '<span style="font-size:34px;font-weight:600">' +
        (c.implied_utilization != null ? c.implied_utilization + "%" : "–") + "</span>" +
        '<span style="color:var(--ink-2)"> ± ' + c.mae_band_pts + ' pts · direction: <b>' +
        U.esc(c.direction) + "</b> vs year-ago " + c.year_ago_utilization + "%</span>");
      el.appendChild(big);
      el.appendChild(U.el("p", "sub",
        "Inputs: utilization momentum " + (c.inputs.utilization_yoy_pts >= 0 ? "+" : "") +
        c.inputs.utilization_yoy_pts + " pts YoY · Reactive Demand Index +" +
        c.inputs.reactive_index_yoy + " YoY · headcount +" + c.inputs.fte_yoy_pct +
        "% YoY. Model hit rate " + (d.model_hit_rate * 100).toFixed(0) + "% vs naive " +
        (d.naive_hit_rate * 100).toFixed(0) + "% over " + d.evaluated + " out-of-sample quarters — " +
        "utilization is persistent, and persistence at these levels is the bull case."));
      mount.appendChild(el);
    }
  }

  /* ================= P2 — litigation ================= */
  function p2Timeseries() {
    U.card({
      mount: "mount-p2-timeseries", datasetKey: "p2_litigation_timeseries",
      chartId: "p2_litigation_timeseries",
      title: "Exponent's courtroom footprint, normalized",
      sub: "Cases mentioning Exponent near expert-witness language, per 100,000 cases in the archive that year — corrects for archive growth. Chart shows 2010-present; full history in the table. * = year in progress (and the newest 1-2 years always read low from archive lag).",
      build: function (elm, d) {
        var rows = d.series.filter(function (r) { return r.year >= 2010; });
        return {
          option: {
            legend: { data: ["Court opinions (per 100k)", "Federal case files (per 100k)"] },
            xAxis: { type: "category", data: rows.map(function (r) { return starYear(r.year); }) },
            yAxis: { type: "value", name: "per 100k cases", nameTextStyle: { color: U.cssVar("--muted") } },
            series: [
              { name: "Court opinions (per 100k)", type: "line", lineStyle: { width: 2.5 },
                symbolSize: 7, connectNulls: true,
                data: rows.map(function (r) { return r.opinions_per_100k; }) },
              { name: "Federal case files (per 100k)", type: "line", lineStyle: { width: 2 },
                symbolSize: 7, connectNulls: true,
                data: rows.map(function (r) { return r.recap_per_100k; }) }
            ]
          },
          table: {
            columns: [{ label: "Year" }, { label: "Opinion mentions", num: true },
                      { label: "All opinions", num: true }, { label: "Per 100k", num: true },
                      { label: "Case-file mentions", num: true }, { label: "All case files", num: true },
                      { label: "Per 100k", num: true }],
            rows: d.series.map(function (r) {
              return [r.year, r.opinions_mentions, r.opinions_total, r.opinions_per_100k,
                      r.recap_mentions, r.recap_total, r.recap_per_100k];
            })
          }
        };
      }
    });
  }

  function p2Daubert() {
    U.card({
      mount: "mount-p2-daubert", datasetKey: "p2_daubert", chartId: "p2_daubert",
      title: "Expert-challenge outcomes: Exponent cases vs baseline",
      sub: "Rulings on motions to exclude expert testimony, classified from opinion text by identical software for both groups.",
      build: function (elm, d) {
        var order = ["admitted", "granted_in_part", "excluded", "mixed_signals", "unclassified"];
        var labels = { admitted: "Expert admitted", granted_in_part: "Partly excluded",
                       excluded: "Excluded", mixed_signals: "Mixed signals", unclassified: "Unclassified" };
        var groups = [
          { name: "Exponent-linked (n=" + ((d.exponent && d.exponent.cases) || []).length + ")", counts: d.exponent_outcome_counts || {} },
          { name: "Baseline (n=" + Object.values(d.baseline.outcome_counts || {}).reduce(function (a, b) { return a + b; }, 0) + ")", counts: d.baseline.outcome_counts || {} }
        ];
        var series = order.map(function (key, i) {
          return {
            name: labels[key], type: "bar", stack: "o", barMaxWidth: 24,
            itemStyle: { borderColor: U.cssVar("--surface"), borderWidth: 2 },
            color: [U.cssVar("--s2"), U.cssVar("--s3"), U.cssVar("--s6"), U.cssVar("--s7"), U.cssVar("--baseline")][i],
            data: groups.map(function (g) {
              var total = order.reduce(function (a, k) { return a + (g.counts[k] || 0); }, 0);
              return total ? +((g.counts[key] || 0) / total * 100).toFixed(1) : 0;
            })
          };
        });
        return {
          option: {
            grid: { left: 160, right: 30, top: 34, bottom: 30 },
            legend: {},
            tooltip: { trigger: "axis", valueFormatter: function (v) { return v + "%"; } },
            xAxis: { type: "value", max: 100, axisLabel: { formatter: "{value}%" } },
            yAxis: { type: "category", data: groups.map(function (g) { return g.name; }),
                     axisLabel: { color: U.cssVar("--ink-2") } },
            series: series
          },
          table: {
            columns: [{ label: "Case", wrap: true }, { label: "Expert" }, { label: "Practice", wrap: true },
                      { label: "Date" }, { label: "Outcome" },
                      { label: "Judge's language", wrap: true }, { label: "Link", link: true }],
            rows: ((d.exponent && d.exponent.cases) || []).map(function (c) {
              return [c.case_name, (c.expert || "").replace(" (former-roster match)", " †"),
                      c.expert_practice || "", c.date_filed, c.outcome,
                      c.evidence_quote || c.reason || "", { text: "opinion", href: c.url }];
            })
          }
        };
      }
    });
  }

  function p2Cases() {
    U.card({
      mount: "mount-p2-cases", datasetKey: "p2_matched_cases", chartId: "p2_matched_cases",
      title: "The evidence: most recent matched cases",
      sub: "Every row links to the primary court record on CourtListener.",
      build: function (elm, d) {
        elm.remove();
        return {
          custom: true,
          table: {
            columns: [{ label: "Case", wrap: true }, { label: "Court", wrap: true },
                      { label: "Filed" }, { label: "Type" },
                      { label: "Matched text", wrap: true }, { label: "Record", link: true }],
            rows: (d.cases || []).map(function (c) {
              return [c.case_name, c.court, c.date_filed,
                      c.type === "o" ? "Opinion" : "Case file",
                      (c.snippets || []).join(" … ").replace(/\s+/g, " ").slice(0, 220),
                      { text: "open", href: c.url }];
            })
          }
        };
      }
    });
    var mount = document.getElementById("mount-p2-cases");
    var wrap = mount && mount.querySelector(".tablewrap");
    if (wrap) wrap.classList.add("open");
  }

  /* ================= P3 — reactive index ================= */
  function p3Index() {
    U.card({
      mount: "mount-p3-index", datasetKey: "p3_reactive_index", chartId: "p3_reactive_index",
      title: "Reactive Demand Index: product failures reported to US regulators",
      sub: "Severity-weighted recalls, complaints and adverse events in Exponent-relevant categories. Each source indexed to its own 2012–2019 average = 100. Chart shows 2018-present; full history in the table.",
      build: function (elm, d) {
        var blended = d.blended_index.filter(function (r) { return r.quarter >= "2018"; });
        var quarters = blended.map(function (r) { return r.quarter; });
        var srcLabels = {
          nhtsa_recalls: "Vehicle recalls", nhtsa_complaints: "Vehicle complaints",
          cpsc_recalls: "Consumer-product recalls", fda_device_recalls: "Device recalls",
          fda_maude_events: "Device adverse events"
        };
        var series = [{
          name: "Blended index", type: "line", lineStyle: { width: 3 }, symbol: "none",
          z: 10, data: blended.map(function (r) { return r.index; })
        }];
        Object.keys(d.per_source_indexed || {}).forEach(function (src) {
          var idx = d.per_source_indexed[src];
          series.push({
            name: srcLabels[src] || src, type: "line", lineStyle: { width: 1.2, opacity: 0.75 },
            symbol: "none", emphasis: { focus: "series" },
            data: quarters.map(function (q) { return idx[q] !== undefined ? idx[q] : null; })
          });
        });
        return {
          option: {
            legend: {},
            grid: { top: 78 },  /* two-row legend needs extra headroom */
            xAxis: { type: "category", data: quarters,
                     axisLabel: { interval: 7 } },
            yAxis: { type: "value", name: "index (base = 100)", nameTextStyle: { color: U.cssVar("--muted") } },
            series: series
          },
          table: {
            columns: [{ label: "Quarter" }, { label: "Blended index", num: true }].concat(
              Object.keys(d.per_source_indexed || {}).map(function (s) {
                return { label: srcLabels[s] || s, num: true };
              })),
            rows: d.blended_index.map(function (r) {
              return [r.quarter, r.index].concat(
                Object.keys(d.per_source_indexed || {}).map(function (s) {
                  var v = d.per_source_indexed[s][r.quarter];
                  return v === undefined ? "" : v;
                }));
            })
          }
        };
      }
    });
  }

  function p3Lag() {
    var fin = window.ALTDATA.p6_expo_financials;
    var idxData = window.ALTDATA.p3_reactive_index;
    if (!fin || !fin.data || !idxData || !idxData.data) {
      U.card({ mount: "mount-p3-lag", datasetKey: "p3_missing_combo", chartId: "p3_lag_overlay",
               title: "Failures today, revenue later", sub: "", build: function () { return {}; } });
      return;
    }
    var shifts = [0, 1, 4, 8]; // quarters: 0, +3mo, +12mo, +24mo
    var labels = ["No shift", "+3 months", "+12 months", "+24 months"];
    var state = { shift: 2 };

    var controls = U.el("div", "controls");
    var chartRef = null;

    function quarterAdd(q, n) {
      var m = q.split("-Q"); var y = +m[0], k = +m[1] - 1 + n;
      return (y + Math.floor(k / 4)) + "-Q" + (k % 4 + 1);
    }
    function buildSeries() {
      var rev = fin.data.revenue_quarterly;
      var revBase = rev.filter(function (p) { return p.period >= "2018" && p.period < "2020"; });
      var mean = rev.reduce(function (a, p) { return a + p.value; }, 0) / rev.length;
      var revIdx = {};
      rev.forEach(function (p) { revIdx[p.period] = +(p.value / mean * 100).toFixed(1); });
      var idx = {};
      idxData.data.blended_index.forEach(function (r) {
        if (r.index !== null) idx[quarterAdd(r.quarter, shifts[state.shift])] = r.index;
      });
      var quarters = Object.keys(revIdx).sort();
      return {
        quarters: quarters,
        rev: quarters.map(function (q) { return revIdx[q]; }),
        idx: quarters.map(function (q) { return idx[q] !== undefined ? idx[q] : null; })
      };
    }
    labels.forEach(function (lb, i) {
      var b = U.el("button", i === state.shift ? "active" : null, lb);
      b.onclick = function () {
        state.shift = i;
        controls.querySelectorAll("button").forEach(function (x, j) {
          x.className = j === i ? "active" : "";
        });
        if (chartRef) {
          var s = buildSeries();
          chartRef.setOption({ xAxis: { data: s.quarters },
                               series: [{ data: s.rev }, { data: s.idx }] });
        }
      };
      controls.appendChild(b);
    });

    U.card({
      mount: "mount-p3-lag", datasetKey: "p3_reactive_index", chartId: "p3_lag_overlay",
      title: "Failures today, revenue later — test the lag yourself",
      sub: "Both lines indexed to their own average (=100) so they share one honest axis. Shift the failure index forward and see if peaks align with later revenue.",
      controls: controls,
      build: function (elm) {
        var s = buildSeries();
        return {
          option: {
            legend: { data: ["Exponent revenue (indexed)", "Reactive Demand Index (shifted)"] },
            xAxis: { type: "category", data: s.quarters, axisLabel: { interval: 3 } },
            yAxis: { type: "value", name: "index (avg = 100)", nameTextStyle: { color: U.cssVar("--muted") } },
            series: [
              { name: "Exponent revenue (indexed)", type: "line", lineStyle: { width: 2.5 },
                symbolSize: 7, data: s.rev },
              { name: "Reactive Demand Index (shifted)", type: "line",
                color: U.cssVar("--s6"), lineStyle: { width: 2 }, symbolSize: 6,
                connectNulls: false, data: s.idx }
            ]
          },
          onchart: function (c) { chartRef = c; },
          table: {
            columns: [{ label: "Quarter" }, { label: "Revenue (indexed)", num: true },
                      { label: "Failure index (shifted)", num: true }],
            rows: s.quarters.map(function (q, i) { return [q, s.rev[i], s.idx[i]]; })
          }
        };
      }
    });
  }

  /* ================= P4 — moat ================= */
  function p4Pubs() {
    U.card({
      mount: "mount-p4-pubs", datasetKey: "p4_publications_timeseries", chartId: "p4_publications",
      title: "Scientific publications by Exponent staff, 1967–present",
      sub: "Peer-reviewed output including the Failure Analysis Associates era — the moat, maintained in public. * = year in progress (new papers are also indexed with a lag).",
      build: function (elm, d) {
        var rows = d.series.filter(function (r) { return r.year >= 1970 && r.year <= new Date().getFullYear(); });
        return {
          option: {
            xAxis: { type: "category", data: rows.map(function (r) { return starYear(r.year); }),
                     axisLabel: { interval: 9 } },
            yAxis: { type: "value", name: "papers / year", nameTextStyle: { color: U.cssVar("--muted") } },
            series: [{ type: "bar", barCategoryGap: "25%",
                       itemStyle: { borderRadius: [3, 3, 0, 0] },
                       data: rows.map(function (r) { return r.works; }) }]
          },
          table: {
            columns: [{ label: "Year" }, { label: "Papers", num: true }, { label: "Citations to that year's papers", num: true }],
            rows: rows.map(function (r) { return [r.year, r.works, r.citations]; })
          }
        };
      }
    });
  }

  function p4Partners() {
    U.card({
      mount: "mount-p4-partners", datasetKey: "p4_partners_rolling", chartId: "p4_partners_rolling",
      title: "Unique corporate research partners (rolling 3-year window)",
      sub: "A public window into a confidential client base — 2025's window is the highest on record. Chart shows 2012-present; full history in the table.",
      build: function (elm, d) {
        var rows = d.series.filter(function (r) { return r.year >= 2012; });
        return {
          option: {
            legend: { data: ["Unique corporate partners", "Co-authored papers"] },
            xAxis: { type: "category", data: rows.map(function (r) { return r.year; }), axisLabel: { interval: 4 } },
            yAxis: { type: "value" },
            series: [
              { name: "Unique corporate partners", type: "line", lineStyle: { width: 2.5 },
                symbolSize: 7, color: U.cssVar("--s2"),
                data: rows.map(function (r) { return r.unique_partners; }) },
              { name: "Co-authored papers", type: "line", lineStyle: { width: 1.5 },
                symbolSize: 5, color: U.cssVar("--s1"),
                data: rows.map(function (r) { return r.coauthored_works; }) }
            ]
          },
          table: {
            columns: [{ label: "3-yr window ending" }, { label: "Unique partners", num: true }, { label: "Co-authored papers", num: true }],
            rows: d.series.map(function (r) { return [r.year, r.unique_partners, r.coauthored_works]; })
          }
        };
      }
    });
  }

  function p4Graph() {
    U.card({
      mount: "mount-p4-graph", datasetKey: "p4_collab_graph", chartId: "p4_collab_graph",
      title: "The collaboration network: 783 corporations, one consultancy",
      sub: "Drag to explore. Circle size = number of co-authored publications. Top 60 partners shown; the table lists all.",
      tall: true,
      build: function (elm, d) {
        var top = d.nodes.filter(function (n) { return !n.is_exponent; }).slice(0, 60);
        var keep = {};
        top.forEach(function (n) { keep[n.id] = true; });
        var maxW = Math.max.apply(null, top.map(function (n) { return n.works; }));
        var nodes = [{
          id: "exponent", name: "Exponent", symbolSize: 46, itemStyle: { color: U.cssVar("--s1") },
          label: { show: true, fontWeight: 600 }
        }].concat(top.map(function (n, i) {
          return {
            id: n.id, name: n.name.replace(/\s*\([^)]*\)$/, ""),
            symbolSize: 10 + 26 * Math.sqrt(n.works / maxW),
            itemStyle: { color: U.cssVar("--s2"), borderColor: U.cssVar("--surface"), borderWidth: 2 },
            label: { show: i < 14, fontSize: 11, color: U.cssVar("--ink-2") },
            value: n.works, topics: (n.top_topics || []).join(", "),
            years: (n.first_year || "?") + "–" + (n.last_year || "?")
          };
        }));
        var edges = d.edges.filter(function (e) { return keep[e.target]; }).map(function (e) {
          return { source: "exponent", target: e.target,
                   lineStyle: { width: Math.max(0.5, 3 * Math.sqrt(e.weight / maxW)), opacity: 0.35 } };
        });
        return {
          option: {
            tooltip: {
              trigger: "item",
              formatter: function (p) {
                if (!p.data || p.dataType !== "node" || p.data.id === "exponent") return p.name;
                return "<b>" + U.esc(p.name) + "</b><br>" + p.data.value +
                  " co-authored papers (" + p.data.years + ")<br><span style='color:" +
                  U.cssVar("--muted") + "'>" + U.esc(p.data.topics) + "</span>";
              }
            },
            legend: { show: false },
            grid: null, xAxis: { show: false }, yAxis: { show: false },
            series: [{
              type: "graph", layout: "force", roam: true, nodes: nodes, edges: edges,
              force: { repulsion: 170, gravity: 0.12, edgeLength: [40, 170],
                       layoutAnimation: false },
              emphasis: { focus: "adjacency" }, lineStyle: { color: U.cssVar("--baseline") }
            }]
          },
          table: {
            columns: [{ label: "Company" }, { label: "Co-authored papers", num: true },
                      { label: "Active" }, { label: "Main topics", wrap: true }],
            rows: d.nodes.filter(function (n) { return !n.is_exponent; }).map(function (n) {
              return [n.name, n.works, (n.first_year || "?") + "–" + (n.last_year || "?"),
                      (n.top_topics || []).join(", ")];
            })
          }
        };
      }
    });
  }

  /* ================= P5 — government ================= */
  function p5Awards() {
    U.card({
      mount: "mount-p5-awards", datasetKey: "p5_federal_awards", chartId: "p5_federal_awards",
      title: "Federal contract obligations to Exponent by fiscal year",
      sub: "Prime awards from USAspending.gov. The 2019–2025 recovery off the 2014–18 trough is itself a demand signal. * = fiscal year in progress (Oct–Sep; agencies also record awards with a lag).",
      build: function (elm, d) {
        var rows = d.by_fiscal_year;
        return {
          option: {
            tooltip: {
              trigger: "axis",
              formatter: function (ps) {
                var r = rows[ps[0].dataIndex];
                return "FY" + r.fy + "<br>" + U.fmt(r.obligations, { money: true }) +
                  " across " + r.awards + " awards";
              }
            },
            xAxis: { type: "category", data: rows.map(function (r) {
              return "FY" + String(r.fy).slice(2) + (r.fy >= THIS_YEAR ? "*" : ""); }) },
            yAxis: { type: "value", axisLabel: { formatter: function (v) { return "$" + v / 1e6 + "M"; } } },
            series: [{ type: "bar", barMaxWidth: 22, itemStyle: { borderRadius: [4, 4, 0, 0] },
                       data: rows.map(function (r) { return Math.round(r.obligations) ; }) }]
          },
          table: {
            columns: [{ label: "Fiscal year" }, { label: "Obligations", num: true }, { label: "Awards", num: true }],
            rows: rows.map(function (r) { return ["FY" + r.fy, U.fmt(r.obligations, { money: true }), r.awards]; })
          }
        };
      }
    });

    U.card({
      mount: "mount-p5-agencies", datasetKey: "p5_federal_awards", chartId: "p5_federal_awards",
      title: "Who in Washington hires Exponent",
      sub: "Total obligations FY2008–present by awarding agency.",
      build: function (elm, d) {
        var top = d.by_agency.slice(0, 8).reverse();
        return {
          option: {
            grid: { left: 210, right: 70, top: 10, bottom: 30 },
            tooltip: { trigger: "item", formatter: function (p) {
              var r = top[p.dataIndex];
              return U.esc(r.agency) + "<br>" + U.fmt(r.obligations, { money: true }) + " · " + r.awards + " awards";
            } },
            xAxis: { type: "value", axisLabel: { formatter: function (v) { return "$" + v / 1e6 + "M"; } } },
            yAxis: { type: "category", data: top.map(function (r) { return r.agency; }),
                     axisLabel: { color: U.cssVar("--ink-2"), width: 195, overflow: "truncate", fontSize: 12.5 } },
            series: [{ type: "bar", barMaxWidth: 18, itemStyle: { borderRadius: [0, 4, 4, 0] },
                       label: { show: true, position: "right", color: U.cssVar("--ink-2"), fontSize: 12,
                                formatter: function (p) { return U.fmt(p.value, { money: true }); } },
                       data: top.map(function (r) { return Math.round(r.obligations); }) }]
          },
          table: {
            columns: [{ label: "Agency" }, { label: "Obligations", num: true }, { label: "Awards", num: true }],
            rows: d.by_agency.map(function (r) { return [r.agency, U.fmt(r.obligations, { money: true }), r.awards]; })
          }
        };
      }
    });
  }

  function p5Regs() {
    U.card({
      mount: "mount-p5-regs", datasetKey: "p5_regulatory_mentions", chartId: "p5_regulatory_mentions",
      title: "Exponent inside federal rulemaking",
      sub: "Documents and public comments naming the firm, per year — with a rate normalized to the portal's own posting volume. * = year in progress.",
      build: function (elm, d) {
        var rows = d.yearly.filter(function (r) { return r.documents || r.comments; });
        function g(r, ep, k) { return r[ep] && r[ep][k] != null ? r[ep][k] : null; }
        return {
          option: {
            legend: { data: ["Documents naming Exponent", "Comments naming Exponent", "Docs per 10k posted (rate)"] },
            xAxis: { type: "category", data: rows.map(function (r) { return starYear(r.year); }) },
            yAxis: { type: "value" },
            series: [
              { name: "Documents naming Exponent", type: "bar", stack: "m", barMaxWidth: 20,
                itemStyle: { borderColor: U.cssVar("--surface"), borderWidth: 2 },
                data: rows.map(function (r) { return g(r, "documents", "strict"); }) },
              { name: "Comments naming Exponent", type: "bar", stack: "m", barMaxWidth: 20,
                itemStyle: { borderColor: U.cssVar("--surface"), borderWidth: 2, borderRadius: [4, 4, 0, 0] },
                data: rows.map(function (r) { return g(r, "comments", "strict"); }) },
              { name: "Docs per 10k posted (rate)", type: "line", lineStyle: { width: 2 },
                symbolSize: 6, color: U.cssVar("--s5"),
                data: rows.map(function (r) { return g(r, "documents", "strict_per_10k"); }) }
            ]
          },
          table: {
            columns: [{ label: "Year" }, { label: "Docs (strict)", num: true }, { label: "Docs (raw word)", num: true },
                      { label: "All docs posted", num: true }, { label: "Per 10k", num: true },
                      { label: "Comments (strict)", num: true }],
            rows: rows.map(function (r) {
              return [r.year, g(r, "documents", "strict"), g(r, "documents", "raw"),
                      g(r, "documents", "total_posted"), g(r, "documents", "strict_per_10k"),
                      g(r, "comments", "strict")];
            })
          }
        };
      }
    });
  }

  /* ================= P6 — client R&D + EXPO financials ================= */
  function p6ClientRnd() {
    U.card({
      mount: "mount-p6-rnd", datasetKey: "p6_client_rnd", chartId: "p6_client_rnd",
      title: "Revealed clients' R&D budgets vs the whole market",
      sub: "Combined annual R&D of documented Exponent-linked companies vs all SEC filers, both indexed to the first year = 100 so growth compares on one axis.",
      build: function (elm, d) {
        var agg = d.constant_sample_aggregate;
        var mkt = d.market_baseline;
        var aggBase = agg.length ? agg[0].total_rnd : null;
        var mktFirst = mkt.filter(function (m) { return m.total; })[0];
        var mktBase = mktFirst ? mktFirst.total : null;
        return {
          option: {
            legend: { data: ["Revealed-client sample (indexed)", "All SEC filers (indexed)"] },
            tooltip: {
              formatter: function (ps) {
                var r = agg[ps[0].dataIndex];
                var m = mkt.filter(function (x) { return x.year === r.year; })[0] || {};
                return r.year + "<br>Client sample: " + U.fmt(r.total_rnd, { money: true }) +
                  (r.yoy_pct != null ? " (" + (r.yoy_pct > 0 ? "+" : "") + r.yoy_pct + "% YoY)" : "") +
                  "<br>All filers: " + (m.total ? U.fmt(m.total, { money: true }) : "–");
              }
            },
            xAxis: { type: "category", data: agg.map(function (r) { return r.year; }) },
            yAxis: { type: "value", name: "index (first year = 100)",
                     nameTextStyle: { color: U.cssVar("--muted") } },
            series: [
              { name: "Revealed-client sample (indexed)", type: "line", lineStyle: { width: 2.5 }, symbolSize: 7,
                data: agg.map(function (r) { return aggBase ? +(r.total_rnd / aggBase * 100).toFixed(1) : null; }) },
              { name: "All SEC filers (indexed)", type: "line", lineStyle: { width: 2 }, symbolSize: 6,
                data: agg.map(function (r) {
                  var m = mkt.filter(function (x) { return x.year === r.year; })[0];
                  return (m && m.total && mktBase) ? +(m.total / mktBase * 100).toFixed(1) : null;
                }) }
            ]
          },
          table: {
            columns: [{ label: "Year" }, { label: "Client-sample R&D", num: true }, { label: "YoY", num: true },
                      { label: "Market R&D", num: true }, { label: "Market YoY", num: true }],
            rows: agg.map(function (r) {
              var m = mkt.filter(function (x) { return x.year === r.year; })[0] || {};
              return [r.year, U.fmt(r.total_rnd, { money: true }),
                      r.yoy_pct != null ? r.yoy_pct + "%" : "",
                      m.total ? U.fmt(m.total, { money: true }) : "",
                      m.yoy_pct != null ? m.yoy_pct + "%" : ""];
            })
          }
        };
      }
    });

    U.card({
      mount: "mount-p6-clients", datasetKey: "p6_client_rnd", chartId: "p6_client_rnd",
      title: "The revealed-client list itself",
      sub: "Every documented relationship, its evidence, and the company's latest reported R&D.",
      build: function (elm, d) {
        elm.remove();
        return {
          custom: true,
          table: {
            columns: [{ label: "Company" }, { label: "Ticker" }, { label: "Relationship" },
                      { label: "Evidence", wrap: true }, { label: "Latest R&D", num: true },
                      { label: "YoY", num: true }, { label: "Line item used", wrap: true }],
            rows: (d.clients || []).map(function (c) {
              var latest = c.rnd_annual ? c.rnd_annual[c.rnd_annual.length - 1] : null;
              var prev = (c.rnd_annual && c.rnd_annual.length > 1)
                ? c.rnd_annual[c.rnd_annual.length - 2] : null;
              var yoy = (latest && prev && prev.year === latest.year - 1 && prev.value)
                ? ((latest.value / prev.value - 1) * 100) : null;
              return [c.name, c.ticker || "", c.relationship, c.evidence || "",
                      latest ? U.fmt(latest.value, { money: true }) + " (" + latest.year + ")"
                             : (c.rnd_note || "n/a"),
                      yoy !== null ? (yoy >= 0 ? "+" : "") + yoy.toFixed(1) + "%" : "",
                      latest ? (c.rnd_is_standard ? "R&D expense (standard)"
                                                  : (c.rnd_tag || "")) : ""];
            })
          }
        };
      }
    });
    var mount = document.getElementById("mount-p6-clients");
    var wrap = mount && mount.querySelector(".tablewrap");
    if (wrap) wrap.classList.add("open");
  }

  function p6ExpoFin() {
    U.card({
      mount: "mount-p6-expofin", datasetKey: "p6_expo_financials", chartId: "p6_expo_financials",
      title: "Ground truth: Exponent's reported quarterly revenue and net income",
      sub: "Straight from SEC filings. Derived Q4 points (full year minus Q1–Q3) are marked in the table.",
      build: function (elm, d) {
        var rev = d.revenue_quarterly;
        var ni = {};
        (d.net_income_quarterly || []).forEach(function (p) { ni[p.period] = p.value; });
        return {
          option: {
            legend: { data: ["Revenue", "Net income"] },
            tooltip: { valueFormatter: function (v) { return v == null ? "–" : "$" + v + "M"; } },
            xAxis: { type: "category", data: rev.map(function (p) { return p.period; }), axisLabel: { interval: 3 } },
            yAxis: { type: "value", axisLabel: { formatter: "${value}M" } },
            series: [
              { name: "Revenue", type: "bar", barMaxWidth: 16, itemStyle: { borderRadius: [3, 3, 0, 0] },
                data: rev.map(function (p) { return +(p.value / 1e6).toFixed(1); }) },
              { name: "Net income", type: "line", lineStyle: { width: 2 }, symbolSize: 6,
                color: U.cssVar("--s4"),
                data: rev.map(function (p) { return ni[p.period] != null ? +(ni[p.period] / 1e6).toFixed(1) : null; }) }
            ]
          },
          table: {
            columns: [{ label: "Quarter" }, { label: "Revenue", num: true }, { label: "Net income", num: true }, { label: "Derived?" }],
            rows: rev.map(function (p) {
              return [p.period, U.fmt(p.value, { money: true }),
                      ni[p.period] != null ? U.fmt(ni[p.period], { money: true }) : "",
                      p.derived ? "yes (FY − Q1–Q3)" : ""];
            })
          }
        };
      }
    });
  }

  /* ================= P8 — peers ================= */
  function p8Pubs() {
    U.card({
      mount: "mount-p8-pubs", datasetKey: "p8_peers", chartId: "p8_pubs",
      title: "Scientific output vs peers: the moat, benchmarked",
      sub: "Peer-reviewed publications per year. FTI Consulting (6x Exponent's revenue) has no research-index record at all.",
      build: function (elm, d) {
        var firms = d.firms.filter(function (f) { return (f.publications || []).length; });
        var years = [];
        for (var y = 2012; y <= THIS_YEAR; y++) years.push(y);
        var noFootprint = d.firms.filter(function (f) { return f.publications_note; })
          .map(function (f) { return f.name.split(" (")[0]; });
        return {
          option: {
            legend: {},
            xAxis: { type: "category", data: years.map(starYear) },
            yAxis: { type: "value", name: "papers / year", nameTextStyle: { color: U.cssVar("--muted") } },
            series: firms.map(function (f, i) {
              var byYear = {};
              (f.publications || []).forEach(function (p) { byYear[p.year] = p.works; });
              return { name: f.name.split(" (")[0], type: "line",
                       lineStyle: { width: f.key === "EXPO" ? 3 : 1.8 },
                       symbolSize: f.key === "EXPO" ? 7 : 5,
                       data: years.map(function (y) { return byYear[y] !== undefined ? byYear[y] : 0; }) };
            }),
            graphic: noFootprint.length ? [{
              type: "text", right: 20, bottom: 60,
              style: { text: noFootprint.join(", ") + ": no research-index record (0)",
                       fill: U.cssVar("--muted"), fontSize: 12 }
            }] : []
          },
          table: {
            columns: [{ label: "Year" }].concat(d.firms.map(function (f) {
              return { label: f.name.split(" (")[0], num: true };
            })),
            rows: years.map(function (y) {
              return [y].concat(d.firms.map(function (f) {
                var hit = (f.publications || []).filter(function (p) { return p.year === y; })[0];
                return hit ? hit.works : (f.publications_note ? "not indexed" : 0);
              }));
            })
          }
        };
      }
    });
  }

  function p8Financials() {
    U.card({
      mount: "mount-p8-financials", datasetKey: "p8_peers", chartId: "p8_financials",
      title: "Operating margin vs peers: the moat's paycheck",
      sub: "Operating income as a share of revenue, from each firm's SEC filings. Exponent runs at roughly double every peer.",
      build: function (elm, d) {
        var years = [];
        for (var y = 2018; y <= THIS_YEAR - 1; y++) years.push(y);
        return {
          option: {
            legend: {},
            tooltip: { valueFormatter: function (v) { return v == null ? "–" : v + "%"; } },
            xAxis: { type: "category", data: years },
            yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
            series: d.firms.map(function (f) {
              var byYear = {};
              ((f.financials || {}).annual || []).forEach(function (r) { byYear[r.year] = r.op_margin_pct; });
              return { name: f.name.split(" (")[0], type: "line",
                       lineStyle: { width: f.key === "EXPO" ? 3 : 1.8 },
                       symbolSize: f.key === "EXPO" ? 7 : 5,
                       data: years.map(function (y) { return byYear[y] !== undefined ? byYear[y] : null; }) };
            })
          },
          table: {
            columns: [{ label: "Year" }].concat(d.firms.map(function (f) {
              return { label: f.name.split(" (")[0] + " margin / growth" };
            })),
            rows: years.map(function (y) {
              return [y].concat(d.firms.map(function (f) {
                var hit = ((f.financials || {}).annual || []).filter(function (r) { return r.year === y; })[0];
                if (!hit) return "";
                return (hit.op_margin_pct != null ? hit.op_margin_pct + "%" : "–") +
                       (hit.rev_growth_pct != null ? " / " + (hit.rev_growth_pct >= 0 ? "+" : "") + hit.rev_growth_pct + "%" : "");
              }));
            })
          }
        };
      }
    });
  }

  function p8Growth() {
    U.card({
      mount: "mount-p8-growth", datasetKey: "p8_peers", chartId: "p8_financials",
      title: "Revenue growth vs peers: the honest counterpoint",
      sub: "Year-over-year revenue growth from SEC filings. CRA has out-grown Exponent through the de-rating — the bull case needs the utilization recovery to close this gap.",
      build: function (elm, d) {
        var years = [];
        for (var y = 2019; y <= THIS_YEAR - 1; y++) years.push(y);
        return {
          option: {
            legend: {},
            tooltip: { valueFormatter: function (v) { return v == null ? "–" : (v >= 0 ? "+" : "") + v + "%"; } },
            xAxis: { type: "category", data: years },
            yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
            series: d.firms.map(function (f) {
              var byYear = {};
              ((f.financials || {}).annual || []).forEach(function (r) { byYear[r.year] = r.rev_growth_pct; });
              return { name: f.name.split(" (")[0], type: "line",
                       lineStyle: { width: f.key === "EXPO" ? 3 : 1.8 },
                       symbolSize: f.key === "EXPO" ? 7 : 5,
                       data: years.map(function (y) { return byYear[y] !== undefined ? byYear[y] : null; }) };
            })
          },
          table: {
            columns: [{ label: "Year" }].concat(d.firms.map(function (f) {
              return { label: f.name.split(" (")[0] + " growth", num: true };
            })),
            rows: years.map(function (y) {
              return [y].concat(d.firms.map(function (f) {
                var hit = ((f.financials || {}).annual || []).filter(function (r) { return r.year === y; })[0];
                return hit && hit.rev_growth_pct != null
                  ? (hit.rev_growth_pct >= 0 ? "+" : "") + hit.rev_growth_pct + "%" : "";
              }));
            })
          }
        };
      }
    });
  }

  function p8Courts() {
    var ds = window.ALTDATA.p8_peers;
    var firms = ds && ds.data ? ds.data.firms : [];
    var withCourts = firms.filter(function (f) { return f.courts; });
    // render only when EVERY firm has counts - a partial set would mislead
    if (withCourts.length !== firms.length || !firms.length) {
      var mount = document.getElementById("mount-p8-courts");
      if (mount) {
        var u = U.el("div", "unavailable");
        u.appendChild(U.el("span", "badge partial", "pending"));
        u.appendChild(U.el("h3", null, "Courtroom share vs peers"));
        u.appendChild(U.el("p", null, "Court-record counts for the peer set are fetched within the archive's free daily request quota and will appear on the next data refresh. Nothing is shown until the real counts are in."));
        mount.appendChild(u);
      }
      return;
    }
    U.card({
      mount: "mount-p8-courts", datasetKey: "p8_peers", chartId: "p8_courts",
      title: "Courtroom share: whose experts get named",
      sub: "Federal case files mentioning each firm near expert-witness language, per year. Newest 1-2 years read low from archive lag.",
      build: function (elm, d) {
        var years = Object.keys(withCourts[0].courts).map(Number).sort();
        return {
          option: {
            legend: {},
            xAxis: { type: "category", data: years.map(starYear) },
            yAxis: { type: "value", name: "cases / year", nameTextStyle: { color: U.cssVar("--muted") } },
            series: withCourts.map(function (f) {
              return { name: f.name.split(" (")[0], type: "line",
                       lineStyle: { width: f.key === "EXPO" ? 3 : 1.8 },
                       symbolSize: f.key === "EXPO" ? 7 : 5,
                       data: years.map(function (y) {
                         var c = f.courts[y] || f.courts[String(y)];
                         return c ? c.opinions + c.recap : null;
                       }) };
            })
          },
          table: {
            columns: [{ label: "Year" }].concat(withCourts.map(function (f) {
              return { label: f.name.split(" (")[0], num: true };
            })),
            rows: years.map(function (y) {
              return [y].concat(withCourts.map(function (f) {
                var c = f.courts[y] || f.courts[String(y)];
                return c ? c.opinions + c.recap : "";
              }));
            })
          }
        };
      }
    });
  }

  return {
    render: function () {
      p1Headcount(); p1Roster(); p7Utilization(); p7RealizedRate(); p9Hiring();
      p6Guidance(); p10Nowcast();
      p2Timeseries(); p2Daubert(); p2Cases();
      p3Index(); p3Lag();
      p4Pubs(); p4Partners(); p4Graph();
      p5Awards(); p5Regs();
      p6ClientRnd(); p6ExpoFin();
      p8Pubs(); p8Financials(); p8Growth(); p8Courts();
    }
  };
})();
