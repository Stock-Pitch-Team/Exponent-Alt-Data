"""P10: fusion nowcast - a walk-forward, out-of-sample directional call on next
quarter's utilization print, benchmarked against naive persistence.

Statistical honesty rules:
- Target is the YoY CHANGE in utilization (removes seasonality).
- Every prediction is out-of-sample: the model refits each quarter using only
  data available before that quarter (walk-forward).
- Reported next to a naive baseline (tomorrow's YoY change = today's). If the
  model can't beat naive, the output SAYS so.
- Tiny model (3 features, OLS) to limit overfitting on ~60 quarterly points.
"""
import logging
from datetime import datetime, timezone

from src.common import jsonio, provenance, quarters

log = logging.getLogger(__name__)

EVAL_START = "2016-Q1"   # walk-forward evaluation window


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _prev_quarter(q):
    y, n = q.split("-Q")
    y, n = int(y), int(n) - 1
    return f"{y - 1}-Q4" if n == 0 else f"{y}-Q{n}"


def _next_quarter(q):
    y, n = q.split("-Q")
    y, n = int(y), int(n) + 1
    return f"{y + 1}-Q1" if n == 5 else f"{y}-Q{n}"


def _year_ago(q):
    y, n = q.split("-Q")
    return f"{int(y) - 1}-Q{n}"


def _ols(X, y):
    """Ordinary least squares via normal equations (stdlib only; tiny system)."""
    k = len(X[0])
    xtx = [[sum(X[r][i] * X[r][j] for r in range(len(X))) for j in range(k)]
           for i in range(k)]
    xty = [sum(X[r][i] * y[r] for r in range(len(X))) for i in range(k)]
    # gaussian elimination with partial pivoting
    for col in range(k):
        pivot = max(range(col, k), key=lambda r: abs(xtx[r][col]))
        if abs(xtx[pivot][col]) < 1e-12:
            return None
        xtx[col], xtx[pivot] = xtx[pivot], xtx[col]
        xty[col], xty[pivot] = xty[pivot], xty[col]
        for r in range(col + 1, k):
            f = xtx[r][col] / xtx[col][col]
            for c in range(col, k):
                xtx[r][c] -= f * xtx[col][c]
            xty[r] -= f * xty[col]
    beta = [0.0] * k
    for r in range(k - 1, -1, -1):
        beta[r] = (xty[r] - sum(xtx[r][c] * beta[c] for c in range(r + 1, k))) / xtx[r][r]
    return beta


def _load_inputs():
    util_doc = jsonio.read_site_json("p7_utilization.json")
    util = {r["quarter"]: r for r in util_doc["data"]["series"]
            if r.get("utilization")}
    p3 = jsonio.read_site_json("p3_reactive_index.json")
    reactive = {r["quarter"]: r["index"] for r in p3["data"]["blended_index"]
                if r["index"] is not None}
    return util, reactive


def _features(q, util, reactive):
    """Feature vector known at end of quarter q, or None if inputs missing."""
    need = [q, _year_ago(q)]
    if not all(k in util for k in need):
        return None
    if q not in reactive or _year_ago(q) not in reactive:
        return None
    d_util = util[q]["utilization"] - util[_year_ago(q)]["utilization"]
    d_reactive = reactive[q] - reactive[_year_ago(q)]
    fte_now, fte_prior = util[q].get("fte"), util[_year_ago(q)].get("fte")
    d_fte_pct = ((fte_now / fte_prior - 1) * 100
                 if fte_now and fte_prior else 0.0)
    return [1.0, d_util, d_reactive / 10.0, d_fte_pct]


def run(step=None, use_cache=True):
    util, reactive = _load_inputs()
    qs = sorted((q for q in util), key=quarters.sort_key)

    # assemble (t -> features_t, target = YoY change at t+1)
    samples = []
    for q in qs:
        nq = _next_quarter(q)
        if nq not in util or _year_ago(nq) not in util:
            continue
        x = _features(q, util, reactive)
        if x is None:
            continue
        target = util[nq]["utilization"] - util[_year_ago(nq)]["utilization"]
        samples.append({"t": q, "predict_for": nq, "x": x, "y": target,
                        "naive": x[1]})  # naive: next YoY change = current

    # walk-forward evaluation
    rows, model_hits, naive_hits, model_err, naive_err = [], 0, 0, [], []
    evaluated = 0
    for i, s in enumerate(samples):
        if quarters.sort_key(s["predict_for"]) < quarters.sort_key(EVAL_START):
            continue
        train = samples[:i]
        if len(train) < 12:
            continue
        beta = _ols([t["x"] for t in train], [t["y"] for t in train])
        if beta is None:
            continue
        pred = sum(b * xi for b, xi in zip(beta, s["x"]))
        evaluated += 1
        model_err.append(abs(pred - s["y"]))
        naive_err.append(abs(s["naive"] - s["y"]))
        if pred * s["y"] > 0 or (abs(pred) < 0.5 and abs(s["y"]) < 0.5):
            model_hits += 1
        if s["naive"] * s["y"] > 0 or (abs(s["naive"]) < 0.5 and abs(s["y"]) < 0.5):
            naive_hits += 1
        rows.append({"quarter": s["predict_for"], "actual_yoy": round(s["y"], 1),
                     "model_yoy": round(pred, 1), "naive_yoy": round(s["naive"], 1)})

    # the live call: latest quarter with features -> next print
    live = None
    beta_full = _ols([s["x"] for s in samples], [s["y"] for s in samples])
    last = samples[-1] if samples else None
    latest_q = qs[-1]
    x_live = _features(latest_q, util, reactive)
    if beta_full and x_live:
        target_q = _next_quarter(latest_q)
        pred = sum(b * xi for b, xi in zip(beta_full, x_live))
        base = util.get(_year_ago(target_q), {}).get("utilization")
        mae = sum(model_err) / len(model_err) if model_err else None
        live = {
            "target_quarter": target_q,
            "predicted_yoy_change_pts": round(pred, 1),
            "implied_utilization": round(base + pred, 1) if base is not None else None,
            "year_ago_utilization": base,
            "direction": "up" if pred > 0.25 else "down" if pred < -0.25 else "flat",
            "mae_band_pts": round(mae, 1) if mae else None,
            "inputs": {"utilization_yoy_pts": round(x_live[1], 1),
                       "reactive_index_yoy": round(x_live[2] * 10, 1),
                       "fte_yoy_pct": round(x_live[3], 1)},
        }

    model_hit_rate = round(model_hits / evaluated, 2) if evaluated else None
    naive_hit_rate = round(naive_hits / evaluated, 2) if evaluated else None
    beats_naive = (model_hit_rate or 0) > (naive_hit_rate or 0)
    jsonio.write_site_json(
        "p10_nowcast.json",
        provenance.envelope(
            pipeline="p10_nowcast", output="nowcast",
            status="ok" if evaluated >= 20 else "partial",
            status_reason=None if evaluated >= 20 else f"only {evaluated} out-of-sample quarters",
            sources=[provenance.source(
                "Fusion of company-stated utilization/FTE (P7) + Reactive Demand Index (P3)",
                "derived", fetched_at=_now(), records_matched=evaluated,
                note="walk-forward OLS, 3 features, refit each quarter on prior data only")],
            coverage={"start": EVAL_START, "end": rows[-1]["quarter"] if rows else None},
            caveats=[
                f"EXPERIMENTAL. {evaluated} out-of-sample quarterly predictions is a small sample - read the direction and the error band, not the decimals.",
                f"Out-of-sample directional hit rate: model {model_hit_rate}, naive persistence {naive_hit_rate}. "
                + ("The model beats naive - modestly, not magically."
                   if beats_naive else
                   "The model does NOT beat naive persistence on this window - the honest conclusion is that utilization is highly persistent, which itself supports the 'sustained peaks' argument."),
                "Every prediction was made using only information available before the predicted quarter (walk-forward); the live call uses the same recipe.",
                "The mean absolute error band is shown with the call; a print inside the band is consistent with the model, not proof of it.",
            ],
            methodology_id="p10_nowcast"),
        {"backtest": rows, "evaluated": evaluated,
         "model_hit_rate": model_hit_rate, "naive_hit_rate": naive_hit_rate,
         "model_mae": round(sum(model_err) / len(model_err), 2) if model_err else None,
         "naive_mae": round(sum(naive_err) / len(naive_err), 2) if naive_err else None,
         "coefficients": {"intercept": round(beta_full[0], 3),
                          "utilization_yoy": round(beta_full[1], 3),
                          "reactive_yoy_per10": round(beta_full[2], 3),
                          "fte_yoy_pct": round(beta_full[3], 3)} if beta_full else None,
         "live_call": live},
    )
    log.info("P10: %d OOS quarters | model hit %s vs naive %s | live call: %s",
             evaluated, model_hit_rate, naive_hit_rate, live)
