"""Command-line entry point. Default operation is fully offline."""

import argparse
from pathlib import Path

from .charts import number, showcase
from .data import SAMPLE, load_analysis
from .report import write_report


def main():
    parser = argparse.ArgumentParser(description="Compare distributor cash cycles and replay retail ordering policies offline.")
    parser.add_argument("--output", type=Path, default=Path("output/report.html"))
    parser.add_argument("--sample-dir", type=Path, default=SAMPLE)
    parser.add_argument("--showcase", type=Path, help="Also generate three labeled PNG figures in this directory")
    parser.add_argument("--lead-days", type=int, default=7, help="Assumed supplier calendar days, >= 1")
    parser.add_argument("--safety-days", type=float, default=3, help="Assumed days of forecast demand, >= 0")
    parser.add_argument("--unit-cost", type=float, default=1.50, help="Assumed GBP unit cost, > 0; not retail selling price")
    args = parser.parse_args()
    try:
        analysis = load_analysis(args.sample_dir, args.lead_days, args.safety_days, args.unit_cost)
        path = write_report(analysis, args.output)
        if args.showcase:
            for image in showcase(analysis, args.showcase):
                print(f"Showcase: {image}")
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    print(f"Offline report: {path.resolve()}")
    for name, rows in analysis["companies"].items():
        row = rows[-1]
        release = (f"USD {number(row['release_5_days'] / 1e6)}m"
                   if row["release_5_days"] is not None else "unavailable")
        print(f"{name.title()} FY {row['end']}: CCC {number(row['ccc'])} days; "
              f"five-day inventory scenario {release}")
    for row in analysis["policies"]:
        fill = number(row["fill_rate"] * 100) if row["fill_rate"] is not None else "N/A"
        print(f"{row['policy'].title()}: avg {row['average_stock']:.1f} units; {row['orders']} orders; "
              f"fill {fill}%; cash GBP {row['cash_gbp']:,.2f}; {number(row['inventory_days'])} inventory days")


if __name__ == "__main__":
    main()
