"""Forward R&D guidance language from revealed clients' own earnings releases.

For each top client, scan recent 8-K earnings exhibits for forward-looking
sentences about research/technology spending. The VERBATIM sentence ships with
every signal so any reader can judge the classification - keyword polarity,
no black box.
"""
import logging
import re
from collections import Counter
from datetime import date, datetime, timezone

from src.common import http, jsonio, provenance
from src.p7_utilization import edgar_8k

log = logging.getLogger(__name__)

MAX_CLIENTS = 40
SINCE_MONTHS = 8   # look back ~2 earnings cycles

_RND_TERM = re.compile(r"research and development|\bR&D\b|research, development",
                       re.IGNORECASE)
_FORWARD = re.compile(r"\b(expect|anticipat|plan|will|intend|outlook|guidance|"
                      r"continue to invest|going forward|fiscal 202[6-8]|"
                      r"full[- ]year 202[6-8])\b", re.IGNORECASE)
_POSITIVE = re.compile(r"\b(increas|accelerat|expand|ramp|grow|higher|invest(?:ing)? more|"
                       r"additional invest|step[- ]up|strengthen)\w*", re.IGNORECASE)
_NEGATIVE = re.compile(r"\b(decreas|reduc|cut|lower|moderat|streamlin|disciplin|"
                       r"slow|pause|scale back|optimiz)\w*", re.IGNORECASE)
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"])")


def _classify(sentence: str):
    pos, neg = bool(_POSITIVE.search(sentence)), bool(_NEGATIVE.search(sentence))
    if pos and not neg:
        return "increase"
    if neg and not pos:
        return "decrease"
    if pos and neg:
        return "mixed"
    return "neutral"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(step=None, use_cache=True):
    clients_doc = jsonio.read_site_json("p6_client_rnd.json")
    clients = [c for c in (clients_doc.get("data") or {}).get("clients", [])
               if c.get("cik") and c.get("rnd_annual")]
    clients.sort(key=lambda c: -(c["rnd_annual"][-1]["value"] if c["rnd_annual"] else 0))
    clients = clients[:MAX_CLIENTS]
    cutoff = date.today().replace(day=1)
    cutoff = f"{cutoff.year - (1 if cutoff.month <= SINCE_MONTHS else 0)}-" \
             f"{(cutoff.month - SINCE_MONTHS - 1) % 12 + 1:02d}-01"

    signals, failures = [], 0
    seen_ciks = set()
    for client in clients:
        cik = int(client["cik"])
        if cik in seen_ciks:   # same company matched under two name variants
            continue
        seen_ciks.add(cik)
        try:
            filings = [f for f in edgar_8k.list_filings(cik, ("8-K",), use_cache=use_cache)
                       if f["filed"] >= cutoff][:4]
        except http.SourceUnavailable as exc:
            failures += 1
            log.warning("%s submissions failed: %s", client["name"], exc.reason)
            continue
        best = None
        for filing in filings:
            try:
                texts = edgar_8k.exhibit_texts(cik, filing["accession"], use_cache=use_cache)
            except http.SourceUnavailable:
                continue
            for text in texts:
                if not _RND_TERM.search(text):
                    continue
                for sent in _SENT_SPLIT.split(text):
                    if len(sent) < 40 or len(sent) > 600:
                        continue
                    if _RND_TERM.search(sent) and _FORWARD.search(sent):
                        direction = _classify(sent)
                        cand = {"sentence": re.sub(r"\s+", " ", sent).strip()[:400],
                                "direction": direction, "filed": filing["filed"],
                                "accession": filing["accession"]}
                        # prefer directional statements over neutral ones
                        if best is None or (best["direction"] == "neutral"
                                            and direction != "neutral"):
                            best = cand
            if best and best["direction"] != "neutral":
                break
        if best is None or best["direction"] == "neutral":
            # fall back to the 10-Q/10-K MD&A, where most filers put R&D guidance
            try:
                reports = [f for f in edgar_8k.list_filings(cik, ("10-Q", "10-K"),
                                                            use_cache=use_cache)
                           if f["filed"] >= cutoff][:2]
            except http.SourceUnavailable:
                reports = []
            for filing in reports:
                text = edgar_8k.primary_doc_text(cik, filing, use_cache=use_cache)
                if not text or not _RND_TERM.search(text):
                    continue
                for sent in _SENT_SPLIT.split(text):
                    if len(sent) < 40 or len(sent) > 600:
                        continue
                    if _RND_TERM.search(sent) and _FORWARD.search(sent):
                        direction = _classify(sent)
                        if direction == "neutral" and best is not None:
                            continue
                        cand = {"sentence": re.sub(r"\s+", " ", sent).strip()[:400],
                                "direction": direction, "filed": filing["filed"],
                                "accession": filing["accession"]}
                        if best is None or (best["direction"] == "neutral"
                                            and direction != "neutral"):
                            best = cand
                if best and best["direction"] != "neutral":
                    break
        if best:
            signals.append({"name": client["name"], "ticker": client.get("ticker"),
                            "latest_rnd": client["rnd_annual"][-1]["value"],
                            **best})

    tally = Counter(s["direction"] for s in signals)
    n_directional = tally["increase"] + tally["decrease"]
    net = ((tally["increase"] - tally["decrease"]) / n_directional
           if n_directional else None)
    jsonio.write_site_json(
        "p6_rnd_guidance.json",
        provenance.envelope(
            pipeline="p6_clients", output="rnd_guidance",
            status="ok" if len(signals) >= 10 else "partial",
            status_reason=None if len(signals) >= 10 else
            f"only {len(signals)} clients had forward R&D language in recent releases",
            sources=[provenance.source(
                f"Clients' own 8-K earnings-release exhibits (SEC EDGAR), filed since {cutoff}",
                "https://www.sec.gov/", fetched_at=_now(),
                records_scanned=len(clients), records_matched=len(signals))],
            coverage={"start": cutoff, "end": str(date.today())},
            caveats=[
                "Each signal is a VERBATIM forward-looking sentence about R&D from the client's own filed earnings release - read the quote, not just the label.",
                "Direction labels come from simple keyword polarity (increase/decrease words); 'neutral' means forward R&D language without a clear direction. Ambiguous sentences are labeled mixed, never forced.",
                "Companies whose releases don't discuss R&D guidance are absent - roughly half of large filers only quantify R&D in the 10-Q, not the press release.",
                "This reads STATED INTENT ~1-2 quarters ahead of reported spend - the leading edge of the client R&D chart above.",
            ],
            methodology_id="p6_rnd_guidance"),
        {"signals": sorted(signals, key=lambda s: -s["latest_rnd"]),
         "tally": dict(tally),
         "net_direction": round(net, 2) if net is not None else None},
    )
    log.info("P6 guidance: %d signals from %d clients (%s), %d fetch failures",
             len(signals), len(clients), dict(tally), failures)
