"""Portable, offline PNG charts using Pillow; no browser or font downloads."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INK = "#152e40"
MUTED = "#536977"
TEAL = "#087e86"
ORANGE = "#bd571d"
PAPER = "#f3f5f2"
GRID = "#d8e0df"
WIDTH, HEIGHT = 1440, 940
COLORS = [TEAL, ORANGE]


def font(size=22, bold=False):
    filenames = (["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
                 if bold else ["C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    for filename in filenames:
        if Path(filename).exists():
            return ImageFont.truetype(filename, size)
    return ImageFont.load_default(size=size)


def text(draw, xy, value, size=22, color=INK, bold=False):
    draw.text(xy, str(value), fill=color, font=font(size, bold))


def sheet(section, title, subtitle):
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, 58), fill=INK)
    text(draw, (48, 15), "INVENTORY CASH PLANNER", 22, "white", True)
    text(draw, (1100, 18), section, 18, "#b7d6d6")
    text(draw, (48, 88), title, 36, bold=True)
    text(draw, (48, 145), subtitle, 22, MUTED)
    return image, draw


def number(value, digits=1):
    return "N/A" if value is None else f"{value:,.{digits}f}"


def line_chart(draw, box, series, labels, y_label):
    left, top, right, bottom = box
    values = [value for _, sequence, _ in series for value in sequence if value is not None]
    low = min(0, min(values, default=0))
    high = max(values, default=1)
    high = high * 1.12 if high > 0 else 1
    span = high - low or 1
    text(draw, (left, top - 37), y_label, 20, MUTED)
    for tick in range(5):
        value = low + span * tick / 4
        y = bottom - (value - low) / span * (bottom - top)
        draw.line((left, y, right, y), fill=GRID, width=1)
        text(draw, (left - 65, y - 12), f"{value:,.0f}", 18, MUTED)
    for i, label in labels:
        count = max(len(sequence) for _, sequence, _ in series)
        x = left + i / max(1, count - 1) * (right - left)
        text(draw, (x - 30, bottom + 15), label, 18, MUTED)
    for name, sequence, color in series:
        previous = None
        for index, value in enumerate(sequence):
            if value is None:
                previous = None
                continue
            point = (left + index / max(1, len(sequence) - 1) * (right - left),
                     bottom - (value - low) / span * (bottom - top))
            if previous is not None:
                draw.line((*previous, *point), fill=color, width=4)
            if len(sequence) < 12:
                draw.ellipse((point[0] - 5, point[1] - 5, point[0] + 5, point[1] + 5), fill=color)
            previous = point


def financial_chart(analysis):
    image, draw = sheet("01 / FINANCIALS", "How long is cash tied up?",
                        "Cash conversion cycle = inventory days + collection days - payment days (approx.)")
    companies = analysis["companies"]
    for i, (name, rows) in enumerate(companies.items()):
        x = 115 + 700 * i
        text(draw, (x, 207), name.title(), 28, COLORS[i], True)
        labels = [(j, row["end"][:4]) for j, row in enumerate(rows)]
        line_chart(draw, (x, 295, x + 510, 530),
                   [(name, [row["ccc"] for row in rows], COLORS[i])], labels, "Cash cycle / days")
        text(draw, (x, 586), "FY end", 21, bold=True)
        for k, heading in enumerate(["DIO", "DSO", "DPO*", "CCC"]):
            text(draw, (x + 140 + k * 100, 586), heading, 21, bold=True)
        for j, row in enumerate(rows):
            y = 630 + 36 * j
            text(draw, (x, y), row["end"][:4], 21)
            for k, key in enumerate(["dio", "dso", "dpo", "ccc"]):
                text(draw, (x + 140 + k * 100, y), number(row[key]), 21)
        text(draw, (x, 835), f"Latest year-end: {rows[-1]['end']} | {rows[-1]['days']} days", 19, MUTED)
    text(draw, (48, 888), "Source: SEC Company Facts, five annual periods per company. *DPO uses cost of sales, not purchases.", 20, MUTED)
    return image


def policy_chart(analysis):
    policies = analysis["policies"]
    settings = analysis["assumptions"]
    image, draw = sheet("02 / OPERATIONS", "Less stock can mean more missed sales",
                        f"UCI retail SKU 85123A | {settings['lead_days']}-day lead time | {settings['safety_days']:g} safety days | lost-sales model")
    for i, policy in enumerate(policies):
        x = 115 + i * 630
        draw.rectangle((x, 207, x + 33, 215), fill=COLORS[i])
        text(draw, (x + 45, 195), policy["policy"].title(), 24, COLORS[i], True)
    days = len(policies[0]["daily"])
    indexes = sorted({0, days // 3, 2 * days // 3, days - 1})
    labels = [(i, policies[0]["daily"][i]["date"][5:]) for i in indexes]
    line_chart(draw, (115, 310, 1350, 580),
               [(row["policy"], [day["stock"] for day in row["daily"]], color)
                for row, color in zip(policies, COLORS)], labels, "Closing on-hand stock / units")
    text(draw, (1200, 625), "Date / MM-DD", 18, MUTED)
    headings = [(115, "Policy"), (360, "Avg. units"), (570, "Orders"), (750, "Unit fill rate"), (1020, "Lost units")]
    for x, heading in headings:
        text(draw, (x, 687), heading, 22, bold=True)
    for i, row in enumerate(policies):
        y = 738 + i * 54
        values = [row["policy"].title(), number(row["average_stock"]), row["orders"],
                  number(row["fill_rate"] * 100) + "%" if row["fill_rate"] is not None else "N/A", row["lost"]]
        for (x, _), value in zip(headings, values):
            text(draw, (x, y), value, 25, COLORS[i])
    text(draw, (48, 877), "Test: 2011-03-01 to 2011-12-09. Forecast: earlier 90 calendar days only. Recorded sales are a demand proxy.", 20, MUTED)
    text(draw, (48, 908), "No supplier delivery records are available; delivery timing and safety stock are assumptions.", 18, MUTED)
    return image


def cash_chart(analysis):
    image, draw = sheet("03 / CASH", "Put a cash value on inventory days",
                        "Two scales, kept separate: company financials in USD; a retail policy experiment in GBP.")
    text(draw, (65, 215), "Five-day reduction scenario / USD millions", 27, bold=True)
    latest = [(name, rows[-1]) for name, rows in analysis["companies"].items()]
    maximum = max((row["release_5_days"] or 0) / 1e6 for _, row in latest) or 1
    for i, ((name, row), color) in enumerate(zip(latest, COLORS)):
        y = 300 + i * 150
        value = row["release_5_days"] / 1e6 if row["release_5_days"] is not None else None
        text(draw, (65, y - 37), f"{name.title()} | FY ended {row['end']}", 22)
        if value is not None:
            draw.rectangle((65, y, 65 + max(1, value / maximum * 660), y + 50), fill=color)
        text(draw, (750, y + 8), f"${number(value)}m" if value is not None else "N/A", 27, color, True)
    text(draw, (65, 572), "Annual cost of sales / fiscal-year days x 5", 24, MUTED)
    text(draw, (65, 613), "A sensitivity estimate; no claim that this cash was released.", 22, MUTED)
    text(draw, (970, 215), "Retail experiment", 27, bold=True)
    for i, row in enumerate(analysis["policies"]):
        y = 295 + i * 200
        text(draw, (970, y), row["policy"].title(), 24, COLORS[i], True)
        text(draw, (970, y + 42), f"GBP {number(row['cash_gbp'], 0)}", 36, COLORS[i], True)
        text(draw, (970, y + 92), f"{number(row['inventory_days'])} inventory days", 23)
    settings = analysis["assumptions"]
    text(draw, (65, 735), f"Retail cash = average closing units x assumed unit cost (GBP {settings['unit_cost_gbp']:.2f}).", 24)
    text(draw, (65, 780), "Retail days = average stock / average daily recorded demand in the test period.", 23, MUTED)
    text(draw, (65, 825), "Company DIO and retail days share a unit, but differ in business, period and measurement.", 23, MUTED)
    text(draw, (48, 894), "Sources: SEC annual USD facts and UCI Online Retail (CC BY 4.0). Excludes pipeline ownership and financing costs.", 20, MUTED)
    return image


CAPTIONS = {
    "cash-cycle.png": "Five annual periods show how inventory, collections and supplier payments combine into each distributor's cash cycle.",
    "ordering-policies.png": "The same recorded sales reveal the stock and simulated service trade-off between weekly and reorder-point ordering.",
    "cash-scenarios.png": "A five-day company scenario and a separate retail cost assumption put inventory days into money terms.",
}
RENDERERS = [financial_chart, policy_chart, cash_chart]


def showcase(analysis, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name, factory in zip(CAPTIONS, RENDERERS, strict=True):
        factory(analysis).save(destination / name, optimize=True)
    return [destination / name for name in CAPTIONS]
