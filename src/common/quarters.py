"""Date -> calendar-quarter bucketing helpers."""
from datetime import date


def to_quarter(d) -> str:
    """'2024-05-17' or date -> '2024-Q2'."""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def to_year(d) -> str:
    if isinstance(d, str):
        return d[:4]
    return str(d.year)


def quarter_range(start_year: int, end_year: int, end_quarter: int = 4):
    """Yield (label, start_iso, end_iso) for each quarter in range, inclusive."""
    starts = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}
    ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
    for year in range(start_year, end_year + 1):
        for q in range(1, 5):
            if year == end_year and q > end_quarter:
                return
            yield f"{year}-Q{q}", f"{year}-{starts[q]}", f"{year}-{ends[q]}"


def year_range(start_year: int, end_year: int):
    for year in range(start_year, end_year + 1):
        yield str(year), f"{year}-01-01", f"{year}-12-31"


def sort_key(label: str) -> tuple:
    """Sort '1998', '2016-Q3' chronologically together."""
    if "-Q" in label:
        y, q = label.split("-Q")
        return int(y), int(q)
    return int(label), 0
