"""Extract annual USD facts by actual period, never by the filing's FY label."""

from datetime import date, timedelta
import math


TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "cost": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "inventory": ["InventoryNet"],
    "receivables": ["AccountsReceivableNetCurrent"],
    "payables": ["AccountsPayableCurrent"],
}
ANNUAL_FORMS = {"10-K", "10-K/A"}


def period_days(start, end):
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def choose_fact(company, tags, end, start=None):
    """Latest filed eligible fact; tag order resolves equal-date aliases only.

    A missing USD fact remains missing. Conflicting values with identical
    filing provenance are rejected rather than selected by input ordering.
    """
    candidates = []
    for rank, tag in enumerate(tags):
        units = company["facts"]["us-gaap"].get(tag, {}).get("units", {})
        for fact in units.get("USD", []):
            if fact.get("form") not in ANNUAL_FORMS or fact.get("end") != end:
                continue
            if fact.get("start") != start:
                continue
            value = fact["val"]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid nonnegative USD fact: {tag} {end}")
            candidates.append((fact["filed"], -rank, fact["accn"], tag, fact))
    if not candidates:
        return None
    candidates.sort(key=lambda row: row[:4])
    latest = candidates[-1]
    values = {row[4]["val"] for row in candidates if row[:4] == latest[:4]}
    if len(values) != 1:
        raise ValueError(f"conflicting facts: {latest[3]} {end}")
    return dict(latest[4], tag=latest[3], unit="USD")


def annual_metrics(company, years=5):
    """Return the latest annual periods, oldest first, with all input receipts."""
    if years < 1:
        raise ValueError("years must be positive")
    periods = set()
    for tag in TAGS["revenue"] + TAGS["cost"]:
        for fact in company["facts"]["us-gaap"].get(tag, {}).get("units", {}).get("USD", []):
            start, end = fact.get("start"), fact.get("end")
            if fact.get("form") in ANNUAL_FORMS and start and 330 <= period_days(start, end) <= 380:
                periods.add((start, end))
    # Reject ambiguous overlapping annual definitions instead of doubling a year.
    ends = [end for _, end in periods]
    if len(ends) != len(set(ends)):
        raise ValueError("Conflicting annual period starts for one year-end")
    result = []
    for start, end in sorted(periods, key=lambda pair: pair[1])[-years:]:
        days = period_days(start, end)
        opening = (date.fromisoformat(start) - timedelta(days=1)).isoformat()
        sources = {name: choose_fact(company, TAGS[name], end, start)
                   for name in ("revenue", "cost")}
        for name in ("inventory", "receivables", "payables"):
            sources[f"opening {name}"] = choose_fact(company, TAGS[name], opening)
            sources[f"closing {name}"] = choose_fact(company, TAGS[name], end)
        flags = [f"Missing {name} USD fact" for name, fact in sources.items() if fact is None]
        if len({fact["accn"] for fact in sources.values() if fact}) > 1:
            flags.append("Inputs span filings; latest eligible restatements selected independently")
        values = {name: fact["val"] if fact else None for name, fact in sources.items()}
        row = {"company": company["entityName"].replace("\u00a0", " "), "cik": company["cik"],
               "start": start, "end": end, "days": days, "sources": sources,
               "revenue": values["revenue"], "cost": values["cost"]}
        for metric, balance, denominator in [("dio", "inventory", "cost"),
                                              ("dso", "receivables", "revenue"),
                                              ("dpo", "payables", "cost")]:
            first, last, flow = values[f"opening {balance}"], values[f"closing {balance}"], values[denominator]
            if flow is not None and flow <= 0:
                flags.append(f"Nonpositive {denominator} denominator")
            row[metric] = ((first + last) / 2 / flow * days
                           if first is not None and last is not None and flow and flow > 0 else None)
        row["ccc"] = (row["dio"] + row["dso"] - row["dpo"]
                      if all(row[key] is not None for key in ("dio", "dso", "dpo")) else None)
        row["release_5_days"] = row["cost"] / days * 5 if row["cost"] and row["cost"] > 0 else None
        row["flags"] = sorted(set(flags))
        result.append(row)
    if not result:
        raise ValueError("No eligible annual USD revenue periods")
    return result


def filing_url(cik, fact):
    accession = fact["accn"]
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{accession}-index.html"
