/* ALTDATA_UI — shared card/chart/table plumbing. Classic script (file:// safe). */
window.ALTDATA_UI = (function () {
  "use strict";

  var charts = [];

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  function palette() {
    return [cssVar("--s1"), cssVar("--s2"), cssVar("--s3"), cssVar("--s4"),
            cssVar("--s5"), cssVar("--s6"), cssVar("--s7"), cssVar("--s8")];
  }
  function baseOption() {
    return {
      color: palette(),
      textStyle: { fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif' },
      grid: { left: 54, right: 22, top: 52, bottom: 42, containLabel: false },
      tooltip: {
        trigger: "axis",
        backgroundColor: cssVar("--surface"),
        borderColor: cssVar("--grid"),
        textStyle: { color: cssVar("--ink"), fontSize: 12.5 },
        axisPointer: { type: "line", lineStyle: { color: cssVar("--baseline") } },
        confine: true
      },
      legend: {
        top: 2, left: 0, icon: "roundRect",
        itemWidth: 12, itemHeight: 12,
        textStyle: { color: cssVar("--ink-2"), fontSize: 12.5 }
      },
      xAxis: {
        axisLine: { lineStyle: { color: cssVar("--baseline") } },
        axisTick: { show: false },
        axisLabel: { color: cssVar("--muted"), fontSize: 12 },
        splitLine: { show: false }
      },
      yAxis: {
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: cssVar("--muted"), fontSize: 12 },
        splitLine: { lineStyle: { color: cssVar("--grid"), width: 1 } }
      }
    };
  }
  function merge(a, b) {
    for (var k in b) {
      if (b[k] && typeof b[k] === "object" && !Array.isArray(b[k]) && a[k] &&
          typeof a[k] === "object" && !Array.isArray(a[k])) merge(a[k], b[k]);
      else a[k] = b[k];
    }
    return a;
  }

  function fmt(n, opts) {
    opts = opts || {};
    if (n === null || n === undefined || isNaN(n)) return "–";
    var abs = Math.abs(n);
    if (opts.money) {
      if (abs >= 1e9) return "$" + (n / 1e9).toFixed(1) + "B";
      if (abs >= 1e6) return "$" + (n / 1e6).toFixed(1) + "M";
      if (abs >= 1e3) return "$" + (n / 1e3).toFixed(0) + "K";
      return "$" + n.toFixed(0);
    }
    if (abs >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (abs >= 1e4) return (n / 1e3).toFixed(0) + "K";
    return Number(n).toLocaleString("en-US", { maximumFractionDigits: opts.dp !== undefined ? opts.dp : 1 });
  }

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  /* ---- card factory -------------------------------------------------- */
  /* spec: {mount, datasetKey, chartId, title, sub, tall, controls?,
            build(chartEl, data, meta) -> {option | custom, table:{columns, rows}} } */
  function card(spec) {
    var mount = document.getElementById(spec.mount);
    if (!mount) return;
    var ds = window.ALTDATA[spec.datasetKey];
    var meta = ds && ds.metadata;
    var expl = (window.ALTDATA.explainers || {})[spec.chartId];

    if (!ds || !meta || meta.status === "unavailable" || !ds.data) {
      var reason = meta && meta.status_reason ? meta.status_reason : "dataset not generated";
      var u = el("div", "unavailable");
      u.appendChild(el("span", "badge unavail", "Data unavailable"));
      u.appendChild(el("h3", null, esc(spec.title)));
      u.appendChild(el("p", null, "No chart is shown because no real data was available. Reason: " +
        esc(reason) + ". Nothing on this page is ever simulated or estimated to fill a gap."));
      mount.appendChild(u);
      return;
    }

    var c = el("div", "card");
    var h = el("h3", null, esc(spec.title));
    if (meta.status === "partial") {
      h.appendChild(el("span", "badge partial", "partial data"));
      h.lastChild.style.marginLeft = "8px";
    }
    c.appendChild(h);
    c.appendChild(el("p", "sub", esc(spec.sub || "")));
    if (spec.controls) c.appendChild(spec.controls);
    var plot = el("div", "plot" + (spec.tall ? " tall" : ""));
    c.appendChild(plot);

    var result = spec.build(plot, ds.data, meta) || {};

    /* explainer */
    var explBox = null;
    if (expl) {
      explBox = el("div", "explainer");
      explBox.innerHTML =
        "<h4>What this shows</h4><p>" + esc(expl.what) + "</p>" +
        "<h4>How it was built</h4><p>" + esc(expl.how) + "</p>" +
        "<h4>Why it matters for the thesis</h4><p>" + esc(expl.thesis) + "</p>" +
        "<h4>Honest limitations</h4><ul>" +
        (expl.caveats || []).map(function (cv) { return "<li>" + esc(cv) + "</li>"; }).join("") +
        "</ul>";
      c.appendChild(explBox);
    }

    /* table view */
    var tableBox = null;
    if (result.table) {
      tableBox = el("div", "tablewrap");
      tableBox.appendChild(renderTable(result.table));
      c.appendChild(tableBox);
    }

    /* footer */
    var foot = el("div", "foot");
    if (explBox) {
      var eb = el("button", null, "How to read this chart");
      eb.onclick = function () { explBox.classList.toggle("open"); };
      foot.appendChild(eb);
    }
    if (tableBox) {
      var tb = el("button", null, "Table view");
      tb.onclick = function () { tableBox.classList.toggle("open"); resizeAll(); };
      foot.appendChild(tb);
    }
    foot.appendChild(el("span", "provenance", provenanceLine(meta)));
    c.appendChild(foot);
    mount.appendChild(c);

    if (result.option) {
      var chart = echarts.init(plot, null, { renderer: "canvas" });
      chart.setOption(merge(baseOption(), result.option), true);
      charts.push(chart);
      if (result.onchart) result.onchart(chart);
    } else if (!result.custom) {
      plot.remove();
    }
  }

  function provenanceLine(meta) {
    var s = (meta.sources && meta.sources[0]) || {};
    var bits = [];
    if (s.name) bits.push("Source: " + esc(s.name));
    if (s.records_matched != null) bits.push("N=" + Number(s.records_matched).toLocaleString());
    else if (s.records_scanned != null) bits.push("scanned " + Number(s.records_scanned).toLocaleString());
    if (meta.generated_at) bits.push("fetched " + esc(String(meta.generated_at).slice(0, 10)));
    return bits.join(" · ");
  }

  function renderTable(t) {
    var tbl = el("table", "data");
    var thead = el("thead");
    var tr = el("tr");
    t.columns.forEach(function (col) {
      tr.appendChild(el("th", col.num ? "num" : null, esc(col.label)));
    });
    thead.appendChild(tr);
    tbl.appendChild(thead);
    var tbody = el("tbody");
    t.rows.forEach(function (row) {
      var r = el("tr");
      t.columns.forEach(function (col, i) {
        var cell = row[i];
        var td = el("td", (col.num ? "num" : "") + (col.wrap ? " wrap" : ""));
        if (col.link && cell && cell.href) {
          td.innerHTML = '<a href="' + esc(cell.href) + '" target="_blank" rel="noopener">' + esc(cell.text) + "</a>";
        } else td.innerHTML = esc(cell);
        r.appendChild(td);
      });
      tbody.appendChild(r);
    });
    tbl.appendChild(tbody);
    return tbl;
  }

  /* ---- scoreboard tile ---------------------------------------------- */
  function tile(mountId, t) {
    var mount = document.getElementById(mountId);
    if (!mount) return;
    var a = el("a", "tile");
    a.href = t.href || "#";
    a.appendChild(el("div", "label", esc(t.label)));
    a.appendChild(el("div", "value", esc(t.value)));
    if (t.delta) {
      a.appendChild(el("div", "delta " + (t.dir || "flat"),
        (t.dir === "up" ? "▲ " : t.dir === "down" ? "▼ " : "") + esc(t.delta)));
    }
    a.appendChild(el("div", "note", esc(t.note || "")));
    mount.appendChild(a);
  }

  function resizeAll() { charts.forEach(function (c) { c.resize(); }); }
  window.addEventListener("resize", resizeAll);
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      location.reload(); /* palette + chart theme rebuild */
    });
  }

  return { card: card, tile: tile, fmt: fmt, esc: esc, el: el, cssVar: cssVar,
           palette: palette, renderTable: renderTable, resizeAll: resizeAll };
})();
