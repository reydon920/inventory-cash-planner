"""Self-contained HTML and machine-readable exports from one calculation set."""

import base64
import csv
from html import escape
from io import BytesIO
import json
from pathlib import Path

from .charts import CAPTIONS, RENDERERS, number
from .finance import filing_url


STYLE = """
:root {color-scheme:light; --ink:#152e40; --teal:#087e86; --paper:#f3f5f2}
*{box-sizing:border-box} body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.65 system-ui,sans-serif}
header{background:var(--ink);color:white;padding:55px max(5vw,24px)}
header small{color:#a7d1d0;text-transform:uppercase;letter-spacing:.16em} h1{font-size:clamp(32px,5vw,58px);line-height:1.1;max-width:1000px}
main{max-width:1250px;margin:auto;padding:25px} h2{font-size:30px;margin-top:55px} a{color:var(--teal)}
nav{display:flex;gap:25px;flex-wrap:wrap;margin:10px 0 30px} figure{margin:30px 0} img{width:100%;height:auto;border:1px solid #d8e0df}
figcaption,.muted{color:#536977;font-size:15px} .note{border-left:5px solid var(--teal);padding:16px 22px;background:white}
.scroll{overflow:auto} table{width:100%;border-collapse:collapse;background:white;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:12px 15px;border-bottom:1px solid #d8e0df;white-space:nowrap} th{font-size:14px;text-transform:uppercase;letter-spacing:.03em}
.scenario{background:var(--ink);color:white;padding:28px;margin:25px 0}.scenario output{font-size:27px;color:#9fe0d4;display:block}
input{font:inherit;padding:6px;width:90px;margin:0 10px} .scenario-grid{display:flex;gap:80px;flex-wrap:wrap}
code{background:#e4e9e7;padding:3px 6px;color:#152e40} pre{white-space:pre-wrap} details{margin:20px 0} summary{cursor:pointer;font-weight:600}
footer{margin:45px 0 20px;padding-top:20px;border-top:1px solid #d8e0df;font-size:14px}
"""


def financial_table(analysis):
    rows = []
    for name, periods in analysis["companies"].items():
        for row in periods:
            values = [name.title(), row["end"], row["days"]] + [number(row[key]) for key in ("dio", "dso", "dpo", "ccc")]
            rows.append("<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in values) + "</tr>")
    headings = ["Company", "FY end", "Year days", "DIO / days", "DSO / days", "DPO* / days", "CCC / days"]
    return '<div class="scroll"><table><thead><tr>' + "".join(f"<th>{item}</th>" for item in headings) + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"


def audit_html(analysis):
    sections = []
    for name, periods in analysis["companies"].items():
        for row in periods:
            facts = []
            for label, fact in row["sources"].items():
                if fact is None:
                    facts.append(f"<li>{escape(label)}: missing</li>")
                    continue
                link = escape(filing_url(row["cik"], fact), quote=True)
                period = f"{fact.get('start', 'instant')} to {fact['end']}"
                facts.append(f'<li>{escape(label)}: <strong>{fact["val"]:,.0f} USD</strong>; '
                             f'{escape(fact["tag"])}; {period}; filed {fact["filed"]}; '
                             f'<a href="{link}">{escape(fact["accn"])}</a></li>')
            flags = "; ".join(row["flags"]) or "No missing or mixed-filing flags"
            sections.append(f'<details><summary>{name.title()} | {row["end"]}</summary><p>{escape(flags)}</p><ul>' + "".join(facts) + "</ul></details>")
    return "".join(sections)


def write_report(analysis, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    figures = []
    for name, factory in zip(CAPTIONS, RENDERERS, strict=True):
        buffer = BytesIO()
        factory(analysis).save(buffer, format="PNG", optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        caption = escape(CAPTIONS[name])
        figures.append(f'<figure><img alt="{caption}" src="data:image/png;base64,{encoded}"><figcaption>{caption}</figcaption></figure>')
    settings = analysis["assumptions"]
    manifest = analysis["manifest"]
    latest = [(name, periods[-1]) for name, periods in analysis["companies"].items()]
    scenario_cards = "".join(f'<p>{name.title()} | FY {row["end"]}<output id="{name}-release"></output></p>' for name, row in latest)
    daily_cost = {name: row["cost"] / row["days"] if row["cost"] and row["cost"] > 0 else None for name, row in latest}
    script_data = json.dumps(daily_cost, allow_nan=False)
    scenario_script = """
const costs = COSTS;
const input = document.getElementById('reduction');
function update() {
  const days = Number(input.value);
  Object.entries(costs).forEach(([name,cost]) => {
    document.getElementById(name+'-release').textContent = cost === null || !Number.isFinite(days) || days < 0 || days > 30
      ? 'Enter 0 to 30 days; missing facts remain unavailable'
      : new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(cost*days)+' estimated';
  });
}
input.addEventListener('input',update);update();
""".replace("COSTS", script_data)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inventory Cash Planner</title><style>{STYLE}</style></head><body>
<header><small>Inventory Cash Planner / offline decision lab</small>
<h1>How much cash does an ordering policy tie up?</h1>
<p>Follow the money through two distributors, then test the inventory trade-off on recorded retail sales.</p></header>
<main><nav><a href="#finance">Financials</a><a href="#policies">Ordering policies</a><a href="#cash">Cash scenarios</a><a href="#sources">Source audit</a></nav>
<p class="note">Company figures are financial-ratio estimates. Retail results are a simulation on a sales proxy.
The two parts illustrate the same working-capital idea; they do not describe the same supply chain.</p>
<p class="muted">Public input snapshot: {escape(manifest['retrieved_at_utc'])}. This report makes no network requests.</p>
<section id="finance"><h2>01 / Read the cash cycle</h2>
<p>Use average opening and closing balances and the actual fiscal-year length. The companies have different fiscal calendars;
each year-end is shown. Lower cash-cycle days can mean less cash committed to operations, subject to business mix and service needs.</p>
{figures[0]}{financial_table(analysis)}
<p><strong>DIO</strong> = average inventory / cost of sales × year days.<br>
<strong>DSO</strong> = average net current receivables / revenue × year days.<br>
<strong>DPO*</strong> = average current accounts payable / cost of sales × year days.<br>
<strong>CCC</strong> = DIO + DSO − DPO. *Payment days approximate purchases with cost of sales.
Receivables may include non-trade balances, and factoring can affect the comparison.</p></section>
<section id="policies"><h2>02 / Replay ordering decisions</h2>
<p>SKU {escape(manifest['retail']['sku'])}: {escape(manifest['retail']['description'])}. Training: 2010-12-01 through 2011-02-28
({settings['training_days']} calendar days). Test: 2011-03-01 through 2011-12-09 ({settings['testing_days']} days).
The fixed forecast is {settings['forecast_units_per_day']:.2f} units/day, calculated only from training sales.</p>
{figures[1]}<p class="note">Assumptions: {settings['lead_days']} calendar days supplier lead time;
{settings['safety_days']:g} days of forecast demand as safety stock; GBP {settings['unit_cost_gbp']:.2f} cost per unit.
These are user inputs, not observed supplier terms or actual product cost.</p>
<p>Both policies start with the same lead-time-plus-safety stock. Each day receives due orders, serves sales, loses unmet demand,
then reviews stock plus outstanding orders. Weekly ordering reviews every seven days, starting on the first test day, and orders up to
forecast × (lead + safety + 7). Reorder-point ordering reviews daily and orders to that same target when inventory position
is at or below forecast × (lead + safety). Targets and initial stock round up to whole units. Orders arrive before demand after the stated lead time.</p>
<p>Change assumptions and rebuild the entire experiment:</p>
<pre><code>python -m cash_planner --lead-days 14 --safety-days 5 --unit-cost 2.00 --output output/scenario.html</code></pre>
<p>Fill rate is simulated units served / recorded demand units. Closing stock is averaged across every test day, including zero-sale days.
There is no future-sales information in the ordering rules.</p></section>
<section id="cash"><h2>03 / Translate inventory into money</h2>{figures[2]}
<div class="scenario"><label>Company scenario: reduce inventory by <input id="reduction" type="number" min="0" max="30" step="1" value="5"> days</label>
<div class="scenario-grid">{scenario_cards}</div><p>Annual cost of sales / year days × selected days. All other conditions held constant.</p></div>
<p>Retail cash tied up = average closing units × assumed GBP unit cost. Retail inventory days = average units / average daily test sales.
Those days can be viewed beside company DIO, but corporate CCC also includes collections and payments. No currencies are converted or combined.</p></section>
<section id="sources"><h2>04 / Check the inputs</h2>
<p>Annual USD 10-K and 10-K/A facts only. Exact period dates are matched, including the day before each year starts for opening balances.
The latest filed eligible value wins; equal-date aliases use an explicit tag preference. Inputs from different filings are flagged below.
Missing balances or nonpositive denominators produce unavailable ratios, never zero-filled estimates.</p>
{audit_html(analysis)}
<p>Financial source: <a href="https://www.sec.gov/search-filings/edgar-application-programming-interfaces">SEC Company Facts API</a>.
Retail source: <a href="https://archive.ics.uci.edu/dataset/352/online-retail">Chen, D. (2015), Online Retail, UCI</a>,
<a href="https://doi.org/10.24432/C5BW33">doi:10.24432/C5BW33</a>, <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.
The retail extract sums positive non-cancelled sales for one product by day and removes identifiers.</p>
<h2>Limits to this experiment</h2><p>Recorded sales omit demand that was never fulfilled in the original shop. Zero recorded sales may reflect closure or missing demand,
not zero customer interest. This one gift product is not representative of semiconductor distribution.
The model omits stockout substitution, backorders, supplier variability, order costs, minimum quantities, stock aging, taxes, financing,
pipeline ownership and receipts after the test ends. Initial stock is assumed available; no warm-up is scored separately.
Two balance-sheet dates hide within-year seasonality. Consolidated XBRL tags can miss custom disclosures or definition changes;
the source audit needs human review before a real business decision.</p></section>
<footer>Inventory Cash Planner · Rohit Malla · MIT code license. Public data retains its source terms.
Exports beside this report: results.json, financials.csv, policy-daily.csv.</footer></main><script>{scenario_script}</script></body></html>"""
    output.write_text(html, encoding="utf-8")
    (output.parent / "results.json").write_text(json.dumps(analysis, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    keys = ["company", "start", "end", "days", "revenue", "cost", "dio", "dso", "dpo", "ccc", "release_5_days"]
    with (output.parent / "financials.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(row for rows in analysis["companies"].values() for row in rows)
    with (output.parent / "policy-daily.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["policy", *analysis["policies"][0]["daily"][0]])
        writer.writeheader()
        for policy in analysis["policies"]:
            writer.writerows(dict(day, policy=policy["policy"]) for day in policy["daily"])
    return output
