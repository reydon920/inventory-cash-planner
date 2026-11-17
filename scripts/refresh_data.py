"""Download public inputs and rebuild small, auditable sample extracts.

Run: python -m scripts.refresh_data --sec-user-agent 'Research team contact URL'
Raw files stay in data/raw; only daily product totals leave the UCI workbook.
"""

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile

from openpyxl import load_workbook

from cash_planner.finance import TAGS, annual_metrics, period_days

ROOT = Path(__file__).resolve().parent.parent
RETAIL_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
COMPANIES = {"arrow": "0000007536", "avnet": "0000008858"}


def download(url, destination, user_agent, attempts=4):
    """One request at a time, below SEC limits; bounded retries honor Retry-After."""
    for attempt in range(attempts):
        time.sleep(0.25)
        try:
            request = Request(url, headers={"User-Agent": user_agent, "Accept": "*/*",
                                           "Accept-Encoding": "gzip"})
            with urlopen(request, timeout=60) as response:
                content = response.read()
            if content[:2] == b"\x1f\x8b":
                content = gzip.decompress(content)
            destination.write_bytes(content)
            metadata = {"url": url, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                        "sha256": hashlib.sha256(content).hexdigest()}
            destination.with_name(destination.name + ".metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            return content
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code not in {429, 500, 502, 503, 504}:
                raise RuntimeError(f"Download refused ({error.code}): {url}; bundled sample is unchanged") from error
            if attempt == attempts - 1:
                raise RuntimeError(f"Download failed: {url}; use the bundled sample") from error
            delay = error.headers.get("Retry-After", "") if isinstance(error, HTTPError) else ""
            time.sleep(float(delay) if delay.isdigit() else 2 ** attempt)


def financial_extract(company):
    metrics = annual_metrics(company)
    starts = {row["start"] for row in metrics}
    ends = {row["end"] for row in metrics}
    openings = {(date.fromisoformat(start) - timedelta(days=1)).isoformat() for start in starts}
    facts = {}
    for tag in dict.fromkeys(tag for options in TAGS.values() for tag in options):
        concept = company["facts"]["us-gaap"].get(tag)
        if not concept:
            continue
        rows = [fact for fact in concept["units"].get("USD", [])
                if fact.get("form") in {"10-K", "10-K/A"}
                and ((fact.get("start") in starts and fact["end"] in ends
                      and 330 <= period_days(fact["start"], fact["end"]) <= 380)
                     or ("start" not in fact and fact["end"] in ends | openings))]
        if rows:
            facts[tag] = {"label": concept.get("label", tag), "units": {"USD": rows}}
    return {"cik": company["cik"], "entityName": company["entityName"], "facts": {"us-gaap": facts}}


def retail_extract(archive):
    """Fixed product and time window, chosen for a readable one-SKU example.

    Cancelled invoices, nonpositive quantities/prices and other products are
    excluded. No customer, invoice or country identifiers are retained.
    """
    start, stop = date(2010, 12, 1), date(2011, 12, 9)
    daily = Counter()
    included_rows = 0
    with zipfile.ZipFile(archive) as bundle:
        names = [name for name in bundle.namelist() if name.endswith(".xlsx")]
        if len(names) != 1:
            raise ValueError("Expected one UCI workbook")
        with bundle.open(names[0]) as handle:
            workbook = load_workbook(io.BytesIO(handle.read()), read_only=True, data_only=True)
        try:
            sheet = workbook.active
            header = next(sheet.iter_rows(values_only=True))
            columns = {name: header.index(name) for name in ("InvoiceNo", "StockCode", "Quantity", "InvoiceDate", "UnitPrice")}
            for row in sheet.iter_rows(min_row=2, values_only=True):
                sku = str(row[columns["StockCode"]])
                invoice = str(row[columns["InvoiceNo"]])
                quantity, price, when = (row[columns[key]] for key in ("Quantity", "UnitPrice", "InvoiceDate"))
                if (sku != "85123A" or invoice.upper().startswith("C") or quantity <= 0 or price <= 0
                        or not isinstance(when, datetime) or not start <= when.date() <= stop):
                    continue
                daily[when.date()] += int(quantity)
                included_rows += 1
        finally:
            workbook.close()
    rows = []
    current = start
    while current <= stop:
        rows.append({"date": current.isoformat(), "units": daily[current]})
        current += timedelta(days=1)
    return rows, included_rows


def rebuild(raw, output, source_urls):
    """Build and validate all inputs before replacing the cached sample."""
    extracts = {name: financial_extract(json.loads((raw / f"{name}.json").read_bytes())) for name in COMPANIES}
    rows, count = retail_extract(raw / "retail.zip")
    cached_times = []
    for filename in ["arrow.json", "avnet.json", "retail.zip"]:
        path = raw / filename
        metadata = raw / (filename + ".metadata.json")
        if metadata.exists():
            receipt = json.loads(metadata.read_text(encoding="utf-8"))
            if receipt["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError(f"Raw cache no longer matches its download receipt: {filename}")
            cached_times.append(receipt["retrieved_at_utc"])
        else:
            cached_times.append(datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())
    manifest = {"retrieved_at_utc": min(cached_times),
                "timestamp_basis": "Oldest input download receipt, or cache modification time if no download receipt exists",
                "built_at_utc": datetime.now(timezone.utc).isoformat(), "financials": {}, "retail": {
        "url": RETAIL_URL, "landing_page": "https://archive.ics.uci.edu/dataset/352/online-retail",
        "citation": "Chen, D. (2015). Online Retail. UCI Machine Learning Repository. doi:10.24432/C5BW33",
        "license": "CC BY 4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "sku": "85123A", "description": "WHITE HANGING HEART T-LIGHT HOLDER",
        "start": rows[0]["date"], "end": rows[-1]["date"], "test_start": "2011-03-01",
        "included_transaction_rows": count,
        "transform": "Positive quantities and prices; cancellation invoices excluded; summed by day; missing dates zero-filled. Identifiers removed.",
        "raw_sha256": hashlib.sha256((raw / "retail.zip").read_bytes()).hexdigest()}}
    for name, extract in extracts.items():
        periods = annual_metrics(extract)
        if len(periods) != 5:
            raise ValueError(f"Expected five completed periods: {name}")
        manifest["financials"][name] = {"url": source_urls[name],
            "raw_sha256": hashlib.sha256((raw / f"{name}.json").read_bytes()).hexdigest(),
            "periods": [row["end"] for row in periods], "currency": "USD"}
    output.mkdir(parents=True, exist_ok=True)
    for name, extract in extracts.items():
        (output / f"{name}.json").write_text(json.dumps(extract, indent=2) + "\n", encoding="utf-8")
    with (output / "demand.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "units"])
        writer.writeheader()
        writer.writerows(rows)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Rebuilt {output}: {len(rows)} calendar days, {count} source rows, two five-year company extracts")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sec-user-agent", help="Real organization/project name and contact email or URL; never a secret")
    parser.add_argument("--from-cache", action="store_true", help="Rebuild using existing data/raw without network")
    args = parser.parse_args()
    raw = ROOT / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    urls = {name: f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json?source=inventory-cash-planner"
            for name, cik in COMPANIES.items()}
    if not args.from_cache:
        if not args.sec_user_agent or not any(value in args.sec_user_agent for value in ("@", "https://")):
            parser.error("Supply --sec-user-agent with your real project/organization and contact email or URL")
        for name, url in urls.items():
            download(url, raw / f"{name}.json", args.sec_user_agent)
        download(RETAIL_URL, raw / "retail.zip", args.sec_user_agent)
    rebuild(raw, ROOT / "data" / "sample", urls)


if __name__ == "__main__":
    main()
