"""Load bundled data and make a training/test split without looking ahead."""

import csv
from datetime import date, timedelta
import json
from pathlib import Path
from statistics import mean

from .finance import annual_metrics
from .simulation import simulate

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


def read_demand(path, retail):
    """Reject gaps and bad quantities rather than silently changing day weights."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    start, end = (date.fromisoformat(retail[key]) for key in ("start", "end"))
    if len(rows) != (end - start).days + 1:
        raise ValueError("Demand sample must contain every calendar day in its declared range")
    for index, row in enumerate(rows):
        when = date.fromisoformat(row["date"])
        if when != start + timedelta(days=index):
            raise ValueError("Demand dates must be unique, consecutive and chronological")
        quantity = int(row["units"])
        if quantity < 0:
            raise ValueError("Daily sales units must be nonnegative integers")
        row["units"] = quantity
    return rows


def load_analysis(sample=SAMPLE, lead_days=7, safety_days=3, unit_cost=1.50):
    sample = Path(sample)
    manifest = json.loads((sample / "manifest.json").read_text(encoding="utf-8"))
    companies = {name: annual_metrics(json.loads((sample / f"{name}.json").read_text(encoding="utf-8")))
                 for name in ("arrow", "avnet")}
    rows = read_demand(sample / "demand.csv", manifest["retail"])
    training = [int(row["units"]) for row in rows if row["date"] < manifest["retail"]["test_start"]]
    testing = [row for row in rows if row["date"] >= manifest["retail"]["test_start"]]
    if not training or not testing:
        raise ValueError("Demand sample needs both training and testing periods")
    forecast = mean(training)
    policies = []
    for policy in ("weekly", "reorder"):
        result = simulate([int(row["units"]) for row in testing], forecast,
                          lead_days, safety_days, unit_cost, policy)
        for source, day in zip(testing, result["daily"], strict=True):
            day["date"] = source["date"]
        policies.append(result)
    return {"manifest": manifest, "companies": companies, "policies": policies,
            "assumptions": {"lead_days": lead_days, "safety_days": safety_days,
                            "unit_cost_gbp": unit_cost, "forecast_units_per_day": forecast,
                            "training_days": len(training), "testing_days": len(testing)}}
