"""Deterministic single-SKU, lost-sales inventory simulation."""

from collections import defaultdict
import math


def simulate(demand, forecast, lead_days=7, safety_days=3, unit_cost=1,
             policy="weekly", initial_stock=None):
    """Receive, serve demand, then order using inventory position each day.

    Weekly reviews every seven days to a lead + review + safety target.
    Daily reorder reviews at a lead + safety threshold, ordering up to a
    lead + safety + seven-day target. Same target makes review timing visible.
    Stock is measured at the close of each day. Unfilled demand is lost.
    """
    if policy not in {"weekly", "reorder"}:
        raise ValueError("policy must be weekly or reorder")
    if isinstance(lead_days, bool) or not isinstance(lead_days, int) or lead_days < 1:
        raise ValueError("lead_days must be an integer >= 1")
    if any(not math.isfinite(x) or x < 0 for x in (forecast, safety_days, unit_cost)) or unit_cost == 0:
        raise ValueError("forecast and safety_days must be nonnegative; unit_cost must be positive")
    demand = list(demand)
    if not demand or any(not math.isfinite(x) or x < 0 or int(x) != x for x in demand):
        raise ValueError("demand must contain nonnegative integer daily quantities")
    target = math.ceil(forecast * (lead_days + safety_days + 7))
    threshold = math.ceil(forecast * (lead_days + safety_days))
    stock = math.ceil(forecast * (lead_days + safety_days)) if initial_stock is None else initial_stock
    if not math.isfinite(stock) or stock < 0 or int(stock) != stock:
        raise ValueError("initial_stock must be a nonnegative integer")
    initial = stock
    pipeline = defaultdict(int)
    daily = []
    orders = 0
    for day, units in enumerate(demand):
        received = pipeline.pop(day, 0)
        stock += received
        served = min(stock, units)
        stock -= served
        position = stock + sum(pipeline.values())
        review = day % 7 == 0 if policy == "weekly" else position <= threshold
        ordered = max(0, target - position) if review else 0
        if ordered:
            pipeline[day + lead_days] += ordered
            orders += 1
        daily.append(dict(day=day, demand=units, received=received, served=served,
                          lost=units - served, stock=stock, ordered=ordered,
                          pipeline=sum(pipeline.values())))
    total = sum(demand)
    average = sum(row["stock"] for row in daily) / len(daily)
    served = sum(row["served"] for row in daily)
    return {"policy": policy, "initial_stock": initial, "daily": daily, "orders": orders,
            "demand": total, "served": served, "lost": total - served,
            "fill_rate": served / total if total else None, "average_stock": average,
            "cash_gbp": average * unit_cost, "inventory_days": average / (total / len(daily)) if total else None,
            "ending_pipeline": sum(pipeline.values()), "target": target, "threshold": threshold}
